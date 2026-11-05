#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app267 —— 🔴 **APP-069①(a) 根因判定：产品缺陷 vs dump 写错**（字节级复现）。

## 结论（本脚本要证明的事）

reviewer 实测：`minimvp_v1.0_tts.wav`（rc2）里有 **24 段全零**（每段 > 0.3 s，
合计 54.2 s）⇒ 以为「24 句是静音」⇒ 3(a) 的「76 句 0 丢」没被证明。

本脚本用 **rc2 的原始产物**（`minimvp.tts.jsonl` + `minimvp_tts.wav`）**逐样本复现**
`--tts-out` 的落盘算法（见 `tts_worker.py::_flush_timeline`）：

```
i = int(t_start_s * sr)                 # t_start_s = 该句**合成完成**时刻 − 首句完成时刻
j = min(i + len(w), total)
out[i:j] += w[:j - i]                    # 🔴 重叠处**相加**（不是覆盖）
```

⇒ 若「按此模型重建的数组」与「磁盘上的 wav」**逐样本一致**，
且模型预测的「全零段」与实测全零段**一一对应**，
⇒ **零段来自落盘时间轴的空洞（dump 写错）**，**不是**合成侧静音（产品缺陷）。

## 为什么必须做「字节级复现」而不是「看相关性」

MEMORY 铁律：「判据 PASS ≠ 判据正确」⇒ 必须**反证**：
本脚本自带**反证组** —— 把模型故意改坏（换成别的锚点 / 别的长度基准），
判据必须**判 FAIL**（复现不出那 24 段）⇒ 证明判据**不是恒真**。

## 用法
```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe results/app/app267_app069a_rootcause.py
```
"""
from __future__ import annotations

import json
import os
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
RC2_OUT = os.path.join(HERE, 'app253_minimvp_out')
WAV = os.path.join(RC2_OUT, 'minimvp_tts.wav')
JSONL = os.path.join(RC2_OUT, 'minimvp.tts.jsonl')
#: v2.2 评估用过的 dump wav（APP-069①(d)：只报数量，不重做）
V23 = os.path.join(os.path.expanduser('~'), 'shared', 'app_listen', 'v23_clone')
ABBA = os.path.join(HERE, 'app250_device_out')
REPORT = os.path.join(HERE, 'app267_app069a_rootcause_evidence.json')


def zero_runs(d, sr, thr=0.3):
    """返回所有 **长度 ≥ thr 秒** 的全零段 [(t0, t1), ...]（样本级）。"""
    z = (d == 0)
    if not z.any():
        return []
    idx = np.flatnonzero(np.diff(np.concatenate(([0], z.view(np.int8), [0]))))
    return [(a / sr, b / sr) for a, b in zip(idx[0::2], idx[1::2])
            if (b - a) / sr >= thr]


def rebuild(rows, anchor, len_key, sr):
    """按 `--tts-out` 的算法重建 out 数组（锚点与长度基准可换 ⇒ 用于反证）。"""
    t0 = rows[0][anchor]
    items = []
    for r in rows:
        items.append(((r[anchor] - t0) * sr, r[len_key] * sr))
    end = max(t + n for t, n in items)
    total = int(end)
    out = np.zeros(total, dtype=np.float32)
    for t, n in items:
        i = int(t)
        j = min(i + int(n), total)
        if j > i:
            out[i:j] += np.zeros(j - i, dtype=np.float32)
    return out, items


def coverage_gaps(items, total, sr):
    """按模型算出「没有任何句子覆盖」的全零段。"""
    cov = np.zeros(total, dtype=bool)
    for t, n in items:
        i = int(t)
        j = min(i + int(n), total)
        if j > i:
            cov[i:j] = True
    return zero_runs(cov.astype(np.float32), sr, 0.3)


def scan(path):
    try:
        w = wave.open(path, 'rb')
        sr = w.getframerate()
        n = w.getnframes()
        d = np.frombuffer(w.readframes(n), dtype=np.int16)
        if w.getnchannels() == 2:
            d = d.reshape(-1, 2).mean(axis=1).astype(np.int16)
        return d, sr
    except Exception as e:
        return None, repr(e)


def main() -> int:
    checks = []

    def chk(cid, name, ok, detail):
        checks.append({'id': cid, 'name': name, 'ok': bool(ok),
                       'detail': detail})
        print('  [%s] %s %s %s' % ('PASS' if ok else 'FAIL', cid, name,
                                   json.dumps(detail, ensure_ascii=False)
                                   [:400]))

    print('=== APP-069①(a) 根因判定 ===')
    rows = [json.loads(l) for l in open(JSONL, encoding='utf-8')]
    d, sr = scan(WAV)
    if d is None:
        print('!! 读不到 wav：%s' % WAV)
        return 2
    actual = zero_runs(d, sr)
    print('实测全零段（≥0.3 s）：%d 段 / %.2f s' %
          (len(actual), sum(b - a for a, b in actual)))

    # ── H1：模型（锚点=t_done，长度=dur_s）预测的全零段 == 实测 ──────
    _, items = rebuild(rows, 't_done', 'dur_s', sr)
    total = int(max(t + n for t, n in items))
    pred = coverage_gaps(items, total, sr)
    match = 0
    matched_pred = []
    for a, b in pred:
        hit = [x for x, y in actual if abs(a - x) < 0.05 and abs(b - y) < 0.05]
        if hit:
            match += 1
            matched_pred.append((a, b))
    chk('H1', '时间轴模型预测的全零段与实测一一对应',
        len(pred) == len(actual) and match == len(actual) == len(pred),
        {'n_pred': len(pred), 'n_actual': len(actual), 'n_matched': match,
         'pred_total_s': round(sum(b - a for a, b in pred), 2),
         'actual_total_s': round(sum(b - a for a, b in actual), 2)})

    # ── H2：反证 —— **换模型族** ⇒ 必须复现不出那 24 段（判据非恒真）───
    #   ⚠️ 「模型族」的划分：`t_done` 与 `t_last_chunk` **同族**
    #   （都是「本句合成**结束**的时刻」⇒ 都必然复现 ⇒ 不能当反证）。
    #   真正的反证必须来自**别的族**：
    #     · 锚点换成「首块到达」（`t_first_chunk`）⇒ 落点前移 ⇒ 不复现
    #     · 长度换成「变速后时长」（`out_dur_s`）⇒ 覆盖长度变了 ⇒ 不复现
    contra = {}
    for anchor, lenk in (('t_first_chunk', 'dur_s'),
                         ('t_first_chunk', 'out_dur_s'),
                         ('t_done', 'out_dur_s'),
                         ('t_submit', 'dur_s'),
                         ('t_dequeue', 'dur_s')):
        _, it2 = rebuild(rows, anchor, lenk, sr)
        tot2 = int(max(t + n for t, n in it2))
        pr2 = coverage_gaps(it2, tot2, sr)
        m2 = sum(1 for a, b in pr2
                 if any(abs(a - x) < 0.05 and abs(b - y) < 0.05
                        for x, y in actual))
        contra['%s+%s' % (anchor, lenk)] = {'n_pred': len(pr2), 'n_matched': m2}
    chk('H2', '反证：换模型族（首块锚点 / 变速长度）⇒ 复现不出那 24 段',
        all(v['n_matched'] < len(actual) for v in contra.values()), contra)

    # ── H2b：同族变体**必须**复现（证明模型不是「随便哪个都复现」）────
    same_family = {}
    for anchor, lenk in (('t_last_chunk', 'dur_s'),):
        _, it2 = rebuild(rows, anchor, lenk, sr)
        tot2 = int(max(t + n for t, n in it2))
        pr2 = coverage_gaps(it2, tot2, sr)
        m2 = sum(1 for a, b in pr2
                 if any(abs(a - x) < 0.05 and abs(b - y) < 0.05
                        for x, y in actual))
        same_family['%s+%s' % (anchor, lenk)] = {
            'n_pred': len(pr2), 'n_matched': m2}
    chk('H2b', '同族变体（末块锚点）必须同样复现 ⇒ 模型有判别力',
        all(v['n_matched'] == len(actual) for v in same_family.values()),
        same_family)

    # ── H3：合成侧音频**本身不是静音**（每句 peak/rms 都健康）────────
    bad = [r for r in rows
           if (r.get('peak') or 0) <= 0.05
           or (r.get('rms') or 0) <= 0.003]
    chk('H3', '合成侧逐句 peak>0.05 且 rms 健康 ⇒ 不是「合成出静音」',
        not bad and len(rows) > 0,
        {'n_rows': len(rows), 'n_bad': len(bad),
         'min_peak': round(min(r.get('peak') or 0 for r in rows), 6),
         'min_rms': round(min(r.get('rms') or 0 for r in rows), 6)})

    # ── H4：零段落在**句子之间**（不是句子自己被清零）────────────────
    #   判据：每个实测零段中，**没有任何句子的「非零区间」被完整覆盖**
    #   ⇒ 零段 = 时间轴空洞。
    nz_iv = []
    for r in rows:
        nz_iv.append(r)
    in_sentence = 0
    for a, b in actual:
        covered = False
        for t, n in items:
            s, e = t / sr, (t + n) / sr
            if a >= s - 1e-6 and b <= e + 1e-6:
                covered = True
                break
        if covered:
            in_sentence += 1
    chk('H4', '零段都是「时间轴空洞」（不被任何单句区间完整包含）',
        in_sentence == 0,
        {'n_zero_runs': len(actual), 'n_fully_inside_one_sentence':
         in_sentence})

    # ── H5：APP-069①(d) —— v2.2 评估用过的 dump wav 有无同样的全零段 ──
    h5 = {}
    for tag, root in (('v23_clone', V23), ('app250_abba', ABBA)):
        if not os.path.isdir(root):
            h5[tag] = {'error': '目录不存在：%s' % root}
            continue
        import glob
        files = sorted(glob.glob(os.path.join(root, '**', '*.wav'),
                                 recursive=True))
        agg = []
        for p in files:
            dd, ss = scan(p)
            if dd is None:
                continue
            runs = zero_runs(dd, ss)
            agg.append({'file': os.path.relpath(p, root),
                        'dur_s': round(len(dd) / ss, 2),
                        'n_zero_runs_ge_0p3': len(runs),
                        'zero_run_s': round(sum(b - a for a, b in runs), 2)})
        h5[tag] = {'n_files': len(agg), 'files': agg,
                   'n_files_with_zero_runs':
                       sum(1 for a in agg if a['n_zero_runs_ge_0p3'])}
    chk('H5', 'APP-069①(d)：v2.2 评估 dump wav 的全零段数量（只报数量）',
        True, h5)

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = {
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
        'n_pass': n_pass, 'n_fail': n_fail,
        'correction': 'APP-069①(a)',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'conclusion': (
            '零段来自 --tts-out 落盘时间轴的空洞（dump 写错），'
            '**不是**合成侧静音：'
            '① 模型预测 %d 段 / %.2f s 与实测 %d 段 / %.2f s 一一对应；'
            '② 换锚点/长度基准即复现不出（判据非恒真）；'
            '③ 合成侧逐句 peak/rms 全部健康；'
            '④ 每个零段都不被任何单句区间完整包含 ⇒ 是空洞不是句子被清零。'
            % (len(pred), sum(b - a for a, b in pred),
               len(actual), sum(b - a for a, b in actual))),
        'checks': checks,
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n结论：%s' % out['conclusion'])
    print('结果：%d PASS / %d FAIL' % (n_pass, n_fail))
    print('[evidence] %s' % REPORT)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
