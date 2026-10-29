# -*- coding: utf-8 -*-
"""app144 —— APP-042 的**逐句 jsonl 字段缺失**缺陷的回归闸门。

🔴🔴🔴 **缺陷（2026-10-29 21:29 真机实测抓到）**：
  `_record_jsonl()` 只把 `_APP027/030/036` 三个**白名单**里的字段拷进 row
  ⇒ APP-042 的 `speed` / `play_lag_s` / `out_dur_s` / `in_dur_s` /
    `speed_gain` / `target_wall` / `play_wall` **只写进了 `tel`**
    （`tel` 只进**会话日志**）⇒ **逐句 jsonl 里一个都没有**。
  ⇒ 后果：`app143` 真机实测 `n_telemetry=0` ⇒ 滞后曲线/倍率占比**无法算**
    ⇒ APP-042 的验收判据 B8/B9/B10/B13 直接 FAIL。

🔴 **通用教训（写进闸门的理由）**：
  **「遥测写进了会话日志」≠「遥测落进了逐句 jsonl」**
  ⇒ 凡是「reviewer 要机器可算的逐句指标」，字段**必须登记进白名单**。
  ⇒ 闸门 = 「白名单存在 + 白名单真的被拷贝 + 关键字段一个不缺」。

本脚本：
  - **静态**：`_APP042_JSONL_KEYS` 存在且含 7 个关键字段；
  - **静态**：`_record_jsonl` 里真的遍历了 `_APP042_JSONL_KEYS`；
  - **静态**：看门狗 meta 快照也带了 `_APP042_JSONL_KEYS`；
  - **行为**：把 `_record_jsonl` 抽出来跑一遍（用 `ast` + `exec`，
    **不 import 被测模块** ⇒ 避免顶层 numpy 依赖导致 import 阶段 abort），
    喂一个带 `tel` 的调用 ⇒ 断言 row 里 7 个字段**都在**；
  - **反证**：把白名单拷贝那段**整块删掉**（带上下文的正则）⇒ 判据必须 FAIL
    ⇒ 证明判据不恒真。
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
TARGET = os.path.join(REPO, 'live_caption', 'tts_worker.py')

KEYS = ('speed', 'in_dur_s', 'out_dur_s', 'speed_gain',
        'target_wall', 'play_wall', 'play_lag_s')


def rec(results, name, ok, detail=''):
    results.append(dict(name=name, ok=bool(ok), detail=str(detail)[:400]))
    return bool(ok)


def extract_record_jsonl(src, mod_name='_tw'):
    """用 ast 抽出 `_record_jsonl` 与相关常量，独立命名空间执行。

    ⚠️ **不 import 被测模块** ⇒ 顶层 numpy 依赖不会让 import 阶段 abort。
    """
    tree = ast.parse(src)
    ns = {'__name__': mod_name}
    # 1) 模块级常量赋值
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id.startswith('_APP'):
                try:
                    consts[t.id] = ast.literal_eval(node.value)
                except Exception:
                    pass
    # 2) `_record_jsonl` 方法
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_record_jsonl':
            fn = node
            break
    assert fn is not None, '找不到 _record_jsonl'
    fn_src = ast.get_source_segment(src, fn)
    ns.update(consts)
    # 依赖：json / time / self
    ns['json'] = json
    ns['time'] = time
    exec(compile(ast.Module(body=[fn], type_ignores=[]), TARGET, 'exec'), ns)
    return ns['_record_jsonl'], consts


def run_checks(src, results, tag='REAL'):
    consts = {}
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id.startswith('_APP'):
                try:
                    consts[t.id] = ast.literal_eval(node.value)
                except Exception:
                    pass

    # ── 静态 1：白名单存在且字段齐全 ────────────────────────────
    rec(results, '[%s] 静态: _APP042_JSONL_KEYS 存在' % tag,
        '_APP042_JSONL_KEYS' in consts,
        'consts=%s' % sorted(consts))
    if '_APP042_JSONL_KEYS' not in consts:
        return False
    wl = tuple(consts['_APP042_JSONL_KEYS'])
    missing = [k for k in KEYS if k not in wl]
    rec(results, '[%s] 静态: 白名单含 7 个关键字段' % tag,
        not missing, 'missing=%s' % missing)

    # ── 静态 2：`_record_jsonl` 真的遍历了白名单 ──────────────────
    fn_src = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_record_jsonl':
            fn_src = ast.get_source_segment(src, node)
            break
    rec(results, '[%s] 静态: _record_jsonl 遍历了 _APP042_JSONL_KEYS' % tag,
        fn_src and '_APP042_JSONL_KEYS' in fn_src, '')

    # ── 静态 3：看门狗 meta 快照也带白名单 ────────────────────────
    has_meta = bool(re.search(r'_APP042_JSONL_KEYS', src)) and \
        bool(re.search(r'meta=\{k: tel\.get\(k\)', src))
    rec(results, '[%s] 静态: 看门狗 meta 快照带 _APP042_JSONL_KEYS' % tag,
        has_meta, '')

    # ── 行为：跑一遍 `_record_jsonl` ─────────────────────────────
    try:
        fn, _ = extract_record_jsonl(src)
    except Exception as e:
        rec(results, '[%s] 行为: 抽出 _record_jsonl' % tag, False, repr(e))
        return False

    class FakeRing:
        def lag_s(self, sr):
            return 0.0

    class FakePlayer:
        ring = FakeRing()

    class FakeSelf:
        player = FakePlayer()
        sr = 24000
        _jsonl_rows = []
        _jsonl_path = None
        _last_lang = 'zh'
        _last_lang_src = 'explicit'
        _last_end_reason = 'eos'
        _last_clone_active = False
        _last_clone_mode = None
        _last_clone_audio_s = 0.0

    fake = FakeSelf()
    tel = {k: 1.25 if k == 'speed' else 2.5 for k in KEYS}
    tel['speed'] = 1.25
    tel['play_lag_s'] = 12.34
    fn(fake, 7, '测试句', 100.0, dur_s=1.0, t_first=100.5, tel=tel)
    row = fake._jsonl_rows[-1]
    absent = [k for k in KEYS if k not in row]
    rec(results, '[%s] 行为: row 里 7 个 APP-042 字段齐全' % tag,
        not absent, 'absent=%s row_keys=%s' % (absent, sorted(row)))
    rec(results, '[%s] 行为: row["speed"] 值正确' % tag,
        row.get('speed') == 1.25, row.get('speed'))
    rec(results, '[%s] 行为: row["play_lag_s"] 值正确' % tag,
        row.get('play_lag_s') == 12.34, row.get('play_lag_s'))
    return not absent


def main():
    src = open(TARGET, encoding='utf-8').read()
    results = []
    real_ok = run_checks(src, results, 'REAL')

    # ── 反证：把白名单拷贝那段**整块**删掉 ⇒ 判据必须 FAIL ──────
    # 🔴 **必须删整块**（只删 `if` 行会留下孤立语句块 ⇒ IndentationError）
    pat = re.compile(
        r'[ \t]*# 🔴🔴🔴 APP-042：\*\*自适应加速\*\*的逐句遥测（倍率 / 滞后）\n'
        r'[ \t]*for k in _APP042_JSONL_KEYS:\n'
        r'[ \t]*if k in tel:\n'
        r'[ \t]*row\[k\] = tel\[k\]\n')
    mutated, n = pat.subn('', src)
    rec(results, '[反证准备] 注入「白名单拷贝整块被删」', n == 1, 'n=%d' % n)
    if n == 1:
        try:
            run_checks(mutated, results, '反证')
            # 判据不恒真：反证组必须至少 FAIL 一项
            bug_fail = any(not r['ok'] for r in results
                           if r['name'].startswith('[反证]'))
            rec(results, '[反证] 删掉拷贝后判据 FAIL（判据不恒真）',
                bug_fail, '')
        except SyntaxError as e:
            rec(results, '[反证] 删掉拷贝后判据 FAIL（判据不恒真）', True,
                '脚本自身语法错：%r' % e)
    else:
        rec(results, '[反证] 删掉拷贝后判据 FAIL（判据不恒真）', False,
            '未命中替换模式（判据可能已失效）')

    n_pass = sum(1 for r in results if r['ok'])
    n_fail = len(results) - n_pass
    # 🔴 **分组计分**：REAL 组必须全 PASS；
    #    反证组的 FAIL 是**预期**（证明判据不恒真）⇒ 不计入 verdict。
    real_items = [r for r in results if r['name'].startswith('[REAL]')]
    real_fail = sum(1 for r in real_items if not r['ok'])
    bug_items = [r for r in results if r['name'].startswith('[反证')]
    bug_hit = sum(1 for r in bug_items if not r['ok'])
    report = dict(
        script='app144_app042_jsonl_keys.py',
        correction='APP-042',
        target=TARGET,
        python=sys.version.split()[0],
        total=len(results), n_pass=n_pass, n_fail=n_fail,
        real_total=len(real_items), real_fail=real_fail,
        bug_total=len(bug_items), bug_hit=bug_hit,
        results=results,
        verdict=bool(real_ok and real_fail == 0 and bug_hit > 0),
    )
    out = os.path.join(HERE, 'app144_app042_jsonl_keys_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    for r in results:
        print('  [%s] %-62s %s'
              % ('PASS' if r['ok'] else 'FAIL', r['name'], r['detail'][:90]))
    print('SUMMARY: PASS=%d FAIL=%d TOTAL=%d'
          % (n_pass, n_fail, len(results)))
    print('证据：%s' % out)
    return 0 if report['verdict'] else 1


if __name__ == '__main__':
    sys.exit(main())
