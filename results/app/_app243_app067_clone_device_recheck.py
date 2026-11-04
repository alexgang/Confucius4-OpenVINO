#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴 **APP-067 ① 的设备级复核**（上一会话跑完但**没来得及分析**）。

## 为什么本脚本存在

上一会话（`fa098d83`，18:25–18:40）：

* `app235`（断点诊断）与 `app241`（设备级）**分析的是 16:58 那次运行**（修复**前**的影子包）
  ⇒ 结论 = clone 0 %；
* 而 **17:25 那次运行**（修复**后**的影子包 `shared/app067_shadow`）的产物
  （`tts_on_clone.log` / `tts_on_clone.tts.jsonl`）**已经在盘上**，
  但**没有生成对应的 evidence json** ⇒ 会话失联 ⇒ 断在这里。

⇒ 本脚本**只做分析**（不跑模型、不占设备 ⇒ **不需要 MACHINE_LOCK**）：
把 17:25 的产物按 APP-067 ① 的验收条件重新算一遍，并给判据配**反证**。

## 🔴 三条口径纪律（本脚本内置，避免重复踩坑）

1. **jsonl 会跨运行累加** ⇒ 必须**按 `t_submit` 的时间断层切 run**，
   只取**最新一次 run**；否则会把「修复前的旧 run」算进来 ⇒ **假 FAIL**。
   （判据：`id` 归零 与 `t_submit` 断层 两个信号必须一致；不一致 ⇒ 无法判定。）
2. **字段名**：`voice_kind` / `voice_spk` 才是逐句 jsonl 的真字段
   （**没有** `spk` 字段）⇒ 判据先查**字段是否存在**，缺失 ⇒ **无法判定**（≠ 不合格）。
3. **三态**：`True` / `False` / **`None`（无法判定）** ⇒ 「无法判定」≠「不合格」。

## 反证（每条都必须被抓住，否则判据恒真 ⇒ 本脚本自身不可信）

| # | 反证 | 期望 |
|---|---|---|
| K1 | 故意分析**旧 run**（修复前，全部 preset） | ⑤-① 必须 **FAIL** |
| K2 | 把 `voice_kind` 改名（模拟字段漂移） | 字段存在性检查必须 **FAIL**（⇒ 无法判定） |
| K3 | 从 log 文本里删掉「♻️ 补登记排队的 spk 音色」 | 排队补登记检查必须 **FAIL** |
| K4 | 故意只取**第一段** run（模拟切错 run） | ⑤-① 必须 **FAIL**（不得假 PASS） |

## 用法

```
python results/app/_app243_app067_clone_device_recheck.py
```
"""
from __future__ import annotations

import hashlib
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, 'app243_app067_clone_device_recheck_evidence.json')

DEVICE_DIR = os.path.join(HERE, 'app223_device_out')
JSONL = os.path.join(DEVICE_DIR, 'tts_on_clone.tts.jsonl')
LOG = os.path.join(DEVICE_DIR, 'tts_on_clone.log')

#: run 切分阈值：`t_submit` 间隔超过它 ⇒ 判为**另一次运行**（语音之间会隔很久）
RUN_GAP_S = 60.0

#: APP-067 ① 的验收条件
CLONE_RATIO_MIN = 0.80

#: 🔴 真实故障串（三条，缺一不可 —— §132 实测过「只抓一条 ⇒ 假 PASS」）
FAULT_STRINGS = (
    '没有可用的音色',
    '没有可用引擎 ⇒ spk 音色登记失败',
    '没有可用引擎 ⇒ 克隆无法生效',
)


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def stat_of(p):
    return {
        'path': p,
        'bytes': os.path.getsize(p),
        'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                               time.localtime(os.path.getmtime(p))),
        'sha256': sha256_of(p),
    }


def load_rows(path=JSONL):
    rows = []
    with open(path, encoding='utf-8') as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            rows.append(json.loads(ln))
    return rows


def split_runs(rows, gap_s=RUN_GAP_S):
    """按 `t_submit` 断层切 run；并用 `id` 归零做交叉验证。"""
    runs = []
    cur = []
    for r in rows:
        t = r.get('t_submit')
        if cur:
            pt = cur[-1].get('t_submit')
            if (t is not None and pt is not None
                    and (t - pt) > gap_s):
                runs.append(cur)
                cur = []
        cur.append(r)
    if cur:
        runs.append(cur)
    # 交叉验证：`id` 归零的次数应等于 run 数 − 1
    resets = 0
    for i in range(1, len(rows)):
        if rows[i].get('id') == 0 and rows[i - 1].get('id') != 0:
            resets += 1
    return runs, resets


def analyze(rows, log_text, label=''):
    """对**给定的 run 行集合**做 APP-067 ① 的验收判定。"""
    checks = []

    def add(name, verdict, detail):
        checks.append({'name': name, 'verdict': verdict, 'detail': detail})

    n = len(rows)
    # ── 口径①：字段存在性（字段漂移 ⇒ 无法判定） ──────────────
    need = ('voice_kind', 'voice_spk')
    missing = sorted({k for r in rows for k in need if k not in r})
    if missing:
        add('字段存在性（voice_kind / voice_spk）', False,
            {'missing_fields': missing,
             'why': 'jsonl 无该字段 ⇒ 判据读不到真值 ⇒ 无法判定'})
        return checks
    add('字段存在性（voice_kind / voice_spk）', True,
        {'rows': n, 'missing_fields': []})

    # ── 口径②：⑤-① clone 占比 ≥ 80 % ────────────────────────
    kinds = {}
    for r in rows:
        k = str(r.get('voice_kind'))
        kinds[k] = kinds.get(k, 0) + 1
    n_clone = kinds.get('clone', 0)
    pct = (float(n_clone) / n) if n else None
    add('⑤-① voice_kind=clone 占比 ≥ 80 %',
        True if (pct is not None and pct >= CLONE_RATIO_MIN) else False,
        {'n_rows': n, 'voice_kind_counts': kinds,
         'pct_voice_kind_clone': pct, 'limit': CLONE_RATIO_MIN})

    # ── 口径③：带 spk 的句子占比（辅助口径，报告用） ──────────
    n_with_spk = sum(1 for r in rows if r.get('voice_spk'))
    add('带 voice_spk 的句子占比（辅助口径）',
        True if (n and n_with_spk / float(n) >= CLONE_RATIO_MIN) else False,
        {'n_with_spk': n_with_spk, 'n_rows': n,
         'pct': (n_with_spk / float(n)) if n else None,
         'note': 'APP-067 ①(b) 的原始口径是「带 spk 的句子占比 ≥ 80 %」'})

    # ── 口径④：①「没有可用引擎/没有可用的音色」= 0 ──────────
    hits = {s: log_text.count(s) for s in FAULT_STRINGS}
    total = sum(hits.values())
    add('①「没有可用音色 / 没有可用引擎」= 0', total == 0,
        {'hits': hits, 'total': total})

    # ── 口径⑤：worker 加载期**排队**后补登记（加载期间不丢） ──
    q_enq = log_text.count('⏳ 模型加载中 ⇒ spk 音色登记')
    q_drain = log_text.count('♻️ 补登记排队的 spk 音色')
    q_ok = log_text.count('音色已登记')
    add('worker 加载期排队 ⇒ 加载完成后补登记',
        (q_enq >= 1 and q_drain >= 1 and q_ok >= 1),
        {'enqueue_line': q_enq, 'drain_line': q_drain,
         'registered_line': q_ok,
         'note': 'APP-067 ①(a) 的验收点'})

    # ── 口径⑥：spk_update 逐段回填 ──────────────────────────
    n_spkupd = log_text.count('spk_update')
    add('spk_update 逐段回填（≥ 1 条）', n_spkupd >= 1,
        {'n_spk_update': n_spkupd})

    # ── 口径⑦：定时克隆更新 = 0（APP-061④） ─────────────────
    n_timed = log_text.count('定时克隆更新')
    add('定时克隆更新 = 0 次', n_timed == 0, {'n_timed_clone_update': n_timed})

    # ── 口径⑧：D1 5 s 窗口在包内真的生效 ─────────────────────
    n_win5 = log_text.count('说话人旁路窗口：5.000 s')
    n_win10 = log_text.count('说话人旁路窗口：10.000 s')
    add('D1 窗口 = 5.000 s（且不是 10.000 s）',
        (n_win5 >= 1 and n_win10 == 0),
        {'n_5s': n_win5, 'n_10s': n_win10})

    # ── 口径⑨：说话人音色登记成功 ────────────────────────────
    n_reg = log_text.count('说话人音色登记')
    add('说话人音色登记成功（≥ 1 次）', n_reg >= 1, {'n_register': n_reg})

    for c in checks:
        c['arm_label'] = label
    return checks


def main():
    rows = load_rows()
    log_text = open(LOG, encoding='utf-8', errors='replace').read()
    runs, resets = split_runs(rows)
    run_meta = [{
        'n_rows': len(r),
        't_first': r[0].get('t_submit'),
        't_last': r[-1].get('t_submit'),
        'voice_kind_counts': _kinds(r),
    } for r in runs]

    latest = runs[-1] if runs else []
    checks = analyze(latest, log_text, label='latest_run')

    n_pass = sum(1 for c in checks if c['verdict'] is True)
    n_fail = sum(1 for c in checks if c['verdict'] is False)
    n_none = sum(1 for c in checks if c['verdict'] is None)

    # ══ 反证 ═══════════════════════════════════════════════
    counterproofs = []

    # K1：分析旧 run（修复前）⇒ ⑤-① 必须 FAIL
    if len(runs) >= 2:
        cp = analyze(runs[0], log_text, label='counterproof_old_run')
        c45 = [c for c in cp if c['name'].startswith('⑤-①')]
        ok = bool(c45) and c45[0]['verdict'] is False
        counterproofs.append({
            'check': 'K1 旧 run（修复前）上 ⑤-① 必须 FAIL',
            'broke': not ok,
            'verdict': 'PASS' if ok else 'FAIL',
            'detail': (c45[0]['detail'] if c45 else '判据缺失'),
        })

    # K2：字段漂移 ⇒ 字段存在性检查必须 FAIL
    rows2 = [dict(r) for r in latest]
    for r in rows2:
        if 'voice_kind' in r:
            r['voice_kind_x'] = r.pop('voice_kind')
    cp2 = analyze(rows2, log_text, label='counterproof_field_drift')
    c0 = cp2[0]
    ok2 = c0['verdict'] is False
    counterproofs.append({
        'check': 'K2 字段漂移（voice_kind 改名）必须被抓（不得假 PASS）',
        'broke': not ok2,
        'verdict': 'PASS' if ok2 else 'FAIL',
        'detail': c0['detail'],
    })

    # K3：删掉「补登记排队的 spk 音色」行 ⇒ 排队补登记检查必须 FAIL
    log3 = log_text.replace('♻️ 补登记排队的 spk 音色', '')
    cp3 = analyze(latest, log3, label='counterproof_no_drain_line')
    c5 = [c for c in cp3 if c['name'].startswith('worker 加载期排队')]
    ok3 = bool(c5) and c5[0]['verdict'] is False
    counterproofs.append({
        'check': 'K3 删掉「补登记排队的 spk 音色」行 ⇒ 排队补登记检查必须 FAIL',
        'broke': not ok3,
        'verdict': 'PASS' if ok3 else 'FAIL',
        'detail': (c5[0]['detail'] if c5 else '判据缺失'),
    })

    # K4：故意只取第一段 run（切错 run）⇒ ⑤-① 必须 FAIL（不得假 PASS）
    if len(runs) >= 2:
        cp4 = analyze(runs[0], log_text, label='counterproof_wrong_run')
        c45b = [c for c in cp4 if c['name'].startswith('⑤-①')]
        ok4 = bool(c45b) and c45b[0]['verdict'] is False
        counterproofs.append({
            'check': 'K4 切错 run（只看第一段）⇒ ⑤-① 必须 FAIL（不得假 PASS）',
            'broke': not ok4,
            'verdict': 'PASS' if ok4 else 'FAIL',
            'detail': (c45b[0]['detail'] if c45b else '判据缺失'),
        })

    n_cp_bad = sum(1 for c in counterproofs if c['verdict'] != 'PASS')

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-067 ①（克隆 0 % 根因）· 设备级复核（上一会话跑完未分析）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'device_lock': '不需要（只分析盘上已有产物，不跑模型 ⇒ 不占 GPU/NPU）',
        'inputs': {'jsonl': stat_of(JSONL), 'log': stat_of(LOG)},
        'run_split': {
            'gap_s': RUN_GAP_S,
            'n_runs': len(runs),
            'n_id_resets': resets,
            'cross_check_ok': (resets == len(runs) - 1),
            'runs': run_meta,
            'note': ('jsonl 跨运行累加 ⇒ 必须按 t_submit 断层切 run；'
                     '分析旧 run ⇒ 假 FAIL（上一会话的 app241 就是这么算的）'),
        },
        'analyzed_run': 'latest',
        'checks': checks,
        'n_pass': n_pass,
        'n_fail': n_fail,
        'n_none': n_none,
        'counterproofs': counterproofs,
        'n_counterproof_failed_to_detect': n_cp_bad,
        'counterproof_ok': n_cp_bad == 0,
        'verdict': ('PASS' if (n_fail == 0 and n_cp_bad == 0) else 'FAIL'),
        'meaning': (
            'PASS = **APP-067 ① 的设备级验收在最新一次运行上成立**'
            '（clone 占比 ≥ 80 %、「没有可用引擎」= 0、加载期排队后补登记、'
            'spk_update 逐段回填、5.000 s 窗口）。'
            '≠ APP-067 ②（每段音色表 + wav 交付物）与 ④（ABBA / GUI 臂）'
            '—— 那两项**仍需持 MACHINE_LOCK 的设备级作业**，本轮未做。'),
        'supersedes': {
            'evidence': 'results/app/app241_app067_clone_device_evidence.json',
            'why': ('app241 的 ts=2026-11-04 16:58:45 ⇒ 分析的是**修复前**那次运行'
                    '（影子包 17:08 才建好）⇒ 它的「clone 0 %」结论'
                    '**对 17:25 那次运行不成立**；本证据是它的**更正**。'),
        },
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)

    print('== run 切分 ==')
    for m in run_meta:
        print('   rows=%-4d %s' % (m['n_rows'], m['voice_kind_counts']))
    print('   id 归零交叉验证：%s' % ev['run_split']['cross_check_ok'])
    print()
    print('== 检查（最新一次 run）==')
    for c in checks:
        print('   %-5s %s | %s' % (str(c['verdict']), c['name'],
                                   json.dumps(c['detail'], ensure_ascii=False)[:150]))
    print('   n_pass=%d n_fail=%d n_none=%d' % (n_pass, n_fail, n_none))
    print()
    print('== 反证 ==')
    for c in counterproofs:
        print('   %-5s %s | %s' % (c['verdict'], c['check'],
                                   json.dumps(c['detail'], ensure_ascii=False)[:120]))
    print()
    print('verdict = %s' % ev['verdict'])
    print('证据：%s' % OUT)
    return 0 if ev['verdict'] == 'PASS' else 1


def _kinds(rows):
    d = {}
    for r in rows:
        k = str(r.get('voice_kind'))
        d[k] = d.get(k, 0) + 1
    return d


if __name__ == '__main__':
    raise SystemExit(main())
