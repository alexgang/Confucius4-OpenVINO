#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app102_app027_metrics_selftest.py —— `app101` 指标计算器的**自测 + 反证**

🔴🔴 **为什么必须自测指标计算器**（§62 的教训：「闸门自身的假通过比缺陷更危险」）：
  APP-027 的 V1/V2 判据全是**数字阈值**
  ⇒ 如果计算器本身算错（例如把「已写入被丢」算成「未合成就丢」）
  ⇒ **真缺陷会被判成 PASS** ⇒ 比没有验收更危险。

⇒ 本脚本用**合成 jsonl**（不跑推理、不占 GPU、不取机器锁）验证：
  A 组：正常场景 → 各判据的**期望值**
  B 组：**反证** —— 故意注入缺陷 ⇒ 对应判据**必须 FAIL**

🔴 **不 import 被测模块** ⇒ 只 `exec` `app101` 的源码到独立命名空间。
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# 🔴🔴 APP-027⑥：隔离 LOCALAPPDATA（本脚本不跑推理，但保持一致）
_TMP_LA = tempfile.mkdtemp(prefix='app102_localappdata_')
os.environ['LOCALAPPDATA'] = _TMP_LA

NP = 0
NF = 0
FAILED = []


def check(name, cond, detail=''):
    global NP, NF
    if cond:
        NP += 1
        print('  [PASS] %s' % name)
    else:
        NF += 1
        FAILED.append(name)
        print('  [FAIL] %s  %s' % (name, detail))


def load_app101():
    """把 `app101` 的源码 exec 到独立命名空间（**不 import**）。"""
    src = open(os.path.join(HERE, 'app101_app027_v1v2_metrics.py'),
               'r', encoding='utf-8').read()
    # 🔴 去掉 `if __name__ == '__main__': main()` 段（exec 时不会触发）
    tree = ast.parse(src)
    body = [n for n in tree.body
            if not (isinstance(n, ast.If)
                    and ast.dump(n.test).find("__main__") >= 0)]
    mod = ast.Module(body=body, type_ignores=[])
    ns = {'__name__': 'app101_ns', '__file__': os.path.join(
        HERE, 'app101_app027_v1v2_metrics.py')}
    exec(compile(mod, 'app101', 'exec'), ns)
    return ns


def write_jsonl(rows):
    p = os.path.join(tempfile.mkdtemp(prefix='app102_'), 'x.tts.jsonl')
    with open(p, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return p


def good_rows(n=20):
    """一组**完全正常**的句子行。"""
    rows = []
    t = 0.0
    for i in range(n):
        dur = 3.0
        rows.append(dict(
            id=i, text='测试句 %d' % i,
            t_submit=round(t, 4),
            t_first_packet=round(dur * 0.4, 4),
            t_done=round(t + dur, 4),
            dur_s=dur,
            dropped=False, error=None,
            t_dequeue=round(t + 0.05, 4),
            t_first_chunk=round(t + 0.5, 4),
            t_last_chunk=round(t + dur * 0.45, 4),
            synth_rtf=0.5,
            prebuffer_s=0.3,
            prebuffer_short=False,
            rtf_ewma=0.5,
            underflow_in_sentence=0,
            underflow_in_sentence_ms=0.0,
            underflow_pre_sentence=1,
            underflow_pre_sentence_ms=120.0,
            n_samples=72000, n_parts=3, peak=0.4, rms=0.1, consumed=True))
        t += 4.0
    return rows


def main():
    print('=' * 66)
    print('A 组 · 正常场景（各判据的期望值）')
    print('=' * 66)
    ns = load_app101()
    pct = ns['pct']
    analyze = ns['analyze_jsonl']
    verdict = ns['verdict']

    rows = good_rows(20)
    p = write_jsonl(rows)
    a = analyze(p)

    check('A1 句子行数正确', a['n_rows'] == 20, '实际 %d' % a['n_rows'])
    check('A2 synth_rtf P50 = 0.5', abs(pct(a['rtf'], 50) - 0.5) < 1e-6,
          '实际 %s' % pct(a['rtf'], 50))
    check('A3 synth_rtf P95 = 0.5', abs(pct(a['rtf'], 95) - 0.5) < 1e-6,
          '实际 %s' % pct(a['rtf'], 95))
    check('A4 未合成就丢 = 0', a['n_dropped_before_synth'] == 0,
          '实际 %d' % a['n_dropped_before_synth'])
    check('A5 已写入被丢 = 0', a['n_dropped_after_write'] == 0,
          '实际 %d' % a['n_dropped_after_write'])
    check('A6 没有产出音频 = 0', a['n_no_audio'] == 0,
          '实际 %d' % a['n_no_audio'])
    check('A7 句内 underflow P95 = 0', pct(a['underflow_in_sentence'], 95) == 0,
          '实际 %s' % pct(a['underflow_in_sentence'], 95))
    check('A8 句前空等被单列统计（不判失败）',
          a['underflow_pre_sentence'] and
          len(a['underflow_pre_sentence']) == 20,
          '实际 %d' % len(a['underflow_pre_sentence']))
    check('A9 最大合成空窗 ≤ 30 s', a['max_idle_gap_s'] <= 30.0,
          '实际 %.1f' % a['max_idle_gap_s'])

    log_a = {'n_watchdog': 0, 'n_log_lines': 100}
    checks, overall = verdict(a, log_a, 'TEST')
    check('A10 正常场景总体 PASS', overall is True, str(checks))

    print()
    print('=' * 66)
    print('B 组 · 反证（注入缺陷 ⇒ 对应判据必须 FAIL）')
    print('=' * 66)

    # B1 —— 注入「已写入被丢」⇒ 必须 FAIL 且被算进 n_dropped_after_write
    bad = good_rows(20)
    bad[7]['dropped'] = True
    bad[7]['error'] = '音频未被播放完（剩余 0.2 s）'
    a1 = analyze(write_jsonl(bad))
    check('B1a 「音频未被播放完」被归到「已写入被丢」',
          a1['n_dropped_after_write'] == 1
          and a1['n_dropped_before_synth'] == 0,
          'after=%d before=%d' % (a1['n_dropped_after_write'],
                                  a1['n_dropped_before_synth']))
    c1, o1 = verdict(a1, log_a, 'T')
    check('B1b 注入「已写入被丢」⇒ 总体 FAIL', o1 is False)
    hit = [c for c in c1 if '已写入被丢' in c['name']]
    check('B1c 「已写入被丢 = 0」判据 FAIL',
          hit and hit[0]['pass'] is False, str(hit))

    # B2 —— 注入「未合成就丢」⇒ **不**判 FAIL（reviewer 只要求「已写入被丢」为 0）
    bad2 = good_rows(20)
    bad2[3]['dropped'] = True
    bad2[3]['error'] = '句子 id=3 已被丢弃，跳过合成'
    a2 = analyze(write_jsonl(bad2))
    check('B2a 「未合成就丢」被正确分类',
          a2['n_dropped_before_synth'] == 1
          and a2['n_dropped_after_write'] == 0,
          'before=%d after=%d' % (a2['n_dropped_before_synth'],
                                  a2['n_dropped_after_write']))
    c2, o2 = verdict(a2, log_a, 'T')
    # 🔴🔴🔴 APP-028②：口径已变 ——
    #   旧口径（APP-027）：「未合成就丢」**不**导致总体 FAIL
    #      （明文只卡「已写入被丢」）。
    #   新口径（APP-028②）：**丢句数必须为 0**（取消了积压丢句）
    #      ⇒ 「未合成就丢」也**是**硬性失败。
    check('B2b APP-028②：「未合成就丢」**也**导致总体 FAIL'
          '（APP-028 明文「丢句数必须为 0」）',
          o2 is False, str(c2))

    # B3 —— 注入「没有产出音频」⇒ FAIL
    bad3 = good_rows(20)
    bad3[9]['error'] = '引擎没有产出任何音频（本句无内容可播）'
    a3 = analyze(write_jsonl(bad3))
    check('B3a 「没有产出音频」被计数', a3['n_no_audio'] == 1,
          '实际 %d' % a3['n_no_audio'])
    c3, o3 = verdict(a3, log_a, 'T')
    check('B3b 注入「没有产出音频」⇒ 总体 FAIL', o3 is False)

    # B4 —— 注入看门狗触发 ⇒ FAIL
    c4, o4 = verdict(a, {'n_watchdog': 2, 'n_log_lines': 10}, 'T')
    check('B4 注入看门狗触发 2 次 ⇒ 总体 FAIL', o4 is False, str(c4))

    # B5 —— 注入大空窗 ⇒ FAIL
    bad5 = good_rows(20)
    for r in bad5[10:]:
        r['t_submit'] += 60.0
    a5 = analyze(write_jsonl(bad5))
    check('B5a 大空窗被检出', a5['max_idle_gap_s'] > 30.0,
          '实际 %.1f' % a5['max_idle_gap_s'])
    c5, o5 = verdict(a5, log_a, 'T')
    check('B5b 注入 >30s 空窗 ⇒ 总体 FAIL', o5 is False)

    # B6 —— 注入句内欠载 ⇒ P95 判据 FAIL
    bad6 = good_rows(20)
    for r in bad6[10:]:
        r['underflow_in_sentence'] = 3
    a6 = analyze(write_jsonl(bad6))
    p95 = pct(a6['underflow_in_sentence'], 95)
    check('B6a 句内欠载 P95 > 0 被检出', p95 and p95 > 0, '实际 %s' % p95)
    c6, o6 = verdict(a6, log_a, 'T')
    check('B6b 注入句内欠载 ⇒ 「P95 = 0」判据 FAIL',
          [c for c in c6 if 'P95 = 0' in c['name']][0]['pass'] is False)
    check('B6c 注入句内欠载 ⇒ 总体 FAIL', o6 is False)

    # B7 —— 缺会话日志 ⇒ 看门狗判据 SKIP（**不**判 FAIL，但必须显式标注）
    #   🔴 **正确语义**：「没证据」≠「通过」⇒ overall **不**为 True，
    #     但也**不**是「判 FAIL」⇒ 由 `has_none` 单独表达。
    c7, o7 = verdict(a, {'n_watchdog': None, 'n_log_lines': 0,
                         'note': '无'}, 'T')
    wd = [c for c in c7 if '看门狗' in c['name']][0]
    check('B7a 缺会话日志 ⇒ 看门狗判据标 SKIP（pass=None）',
          wd['pass'] is None, str(wd))
    check('B7b 缺会话日志 ⇒ 总体**不**判 PASS（没证据不能宣称通过）',
          o7 is False, 'overall=%s' % o7)
    check('B7c 缺会话日志 ⇒ 其余判据仍全是 True（没有被连累）',
          all(c['pass'] is True for c in c7
              if '看门狗' not in c['name']
              and '句前空等' not in c['name']), str(c7))
    # B7d —— 补上会话日志 ⇒ 立刻判 PASS（证明是「缺证据」而非「有缺陷」）
    c7d, o7d = verdict(a, {'n_watchdog': 0, 'n_log_lines': 10}, 'T')
    check('B7d 补上会话日志（看门狗 0 次）⇒ 总体 PASS',
          o7d is True, str(c7d))

    print()
    print('=' * 66)
    print('PASS=%d  FAIL=%d' % (NP, NF))
    if FAILED:
        print('失败项: ' + ', '.join(FAILED))
    print('=' * 66)

    try:
        import shutil
        shutil.rmtree(_TMP_LA, ignore_errors=True)
    except Exception:
        pass
    sys.exit(1 if NF else 0)


if __name__ == '__main__':
    main()
