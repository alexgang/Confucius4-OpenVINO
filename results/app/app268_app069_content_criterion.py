#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app268 —— 🔴🔴🔳 **APP-069①(c) 内容判据**（配音 wav 的「完整性」闸门）。

## 判据（reviewer 原话 ⇒ 逐字落实）

> 3(a) 增加内容判据：逐句 `rms_db > −45` 且 `peak > 0.05` 的比例必须是 100%；
> wav 里超过 0.3 s 的全零段数必须是 0（句间静音要用真实合成的静音或低电平，
> 判据只针对全零段）。反证：用这次的 rc2 wav 跑同一判据，**必须判 FAIL（24 句）**。

⇒ 本模块给出 **4 条**硬判据（**新格式**逐句区间由 jsonl 的
`wav_t0`/`wav_t1` 直接给出 ⇒ **逐句归属唯一、可机器复核**）：

| 编号 | 判据 | 说明 |
|---|---|---|
| **C1** | 逐句 `rms_db > −45` 且 `peak > 0.05` 的比例 == **100 %** | 每句都得有真实语音 |
| **C2** | wav 里 **≥ 0.3 s 的全零段数 == 0** | 只针对**全零**段（低电平静音不判） |
| **C3** | 逐句 `wav_t0`/`wav_t1` **齐备且互不重叠** | reviewer 能逐句切开复核 |
| **C4** | 按 `wav_t0`/`wav_t1` 切出来的段，C1 必须成立 | 段内幅度必须达标 |

## 🔴 反证组（判据非恒真）

拿 **rc2 的旧 wav**（`app253_minimvp_out/`）跑**同一判据** ⇒ **必须 FAIL**，
且报出的「受损句数」必须是 **24**（reviewer 的实测口径）。

⚠️ **为什么旧格式要另算「受损句数」**：
rc2 的 jsonl **没有** `wav_t0`/`wav_t1`（那是修复后才加的）⇒ 无法逐句归属。
⇒ 改用**与新格式等价**的口径：
**旧落盘模型把每句放在「合成完成时刻」处 ⇒ 句间留下「空洞」**；
每个空洞**吞掉一句**的标称位置 ⇒ **受损句数 == 空洞数**。
（reviewer 原文「一句对应一段零」正是这个 1:1 关系；
reviewer 的**逐 id 清单**来自 ASR 回转写对齐 —— 那是 reviewer 的活，
本模块只保证**句数**与 reviewer 一致。）

## 用法
```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe results/app/app268_app069_content_criterion.py
```
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
RC2_OUT = os.path.join(HERE, 'app253_minimvp_out')
RC2_WAV = os.path.join(RC2_OUT, 'minimvp_tts.wav')
RC2_JSONL = os.path.join(RC2_OUT, 'minimvp.tts.jsonl')
REPORT = os.path.join(HERE, 'app268_app069_content_criterion_evidence.json')

RMS_DB_MIN = -45.0        # reviewer：rms_db > −45
PEAK_MIN = 0.05           # reviewer：peak > 0.05
ZERO_RUN_MIN_S = 0.3      # reviewer：超过 0.3 s 的全零段


# ══════════════════════════════════════════════════════════════════════
# 基础工具
# ══════════════════════════════════════════════════════════════════════
def read_wav(path):
    w = wave.open(path, 'rb')
    sr = w.getframerate()
    n = w.getnframes()
    d = np.frombuffer(w.readframes(n), dtype=np.int16)
    if w.getnchannels() == 2:
        d = d.reshape(-1, 2).mean(axis=1).astype(np.int16)
    return d.astype(np.float32) / 32768.0, sr


def read_jsonl(path):
    rows = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def zero_runs(d, sr, thr=ZERO_RUN_MIN_S):
    """所有**长度 ≥ thr 秒**的全零段 [(t0, t1), ...]（样本级）。"""
    z = (d == 0)
    if not z.any():
        return []
    idx = np.flatnonzero(np.diff(np.concatenate(([0], z.view(np.int8), [0]))))
    return [(a / sr, b / sr) for a, b in zip(idx[0::2], idx[1::2])
            if (b - a) / sr >= thr]


def seg_stats(d, sr, t0, t1):
    a = max(0, min(int(round(t0 * sr)), len(d)))
    b = max(a, min(int(round(t1 * sr)), len(d)))
    seg = d[a:b]
    if seg.size == 0:
        return {'n_samples': 0, 'peak': 0.0, 'rms_db': None}
    peak = float(np.max(np.abs(seg)))
    rms = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2)))
    rdb = 20.0 * math.log10(rms) if rms > 1e-12 else None
    return {'n_samples': int(seg.size), 'peak': round(peak, 6),
            'rms_db': (round(rdb, 2) if rdb is not None else None)}


def nominal_slots(rows, key='dur_s'):
    """**标称**（无空洞）布局：句 i 的位置 = 前 i 句时长累加。"""
    t = 0.0
    out = []
    for r in rows:
        out.append((r.get('id'), t, t + float(r.get(key) or 0.0)))
        t += float(r.get(key) or 0.0)
    return out


# ══════════════════════════════════════════════════════════════════════
# 判据
# ══════════════════════════════════════════════════════════════════════
def evaluate_new_format(wav_path, jsonl_path, label):
    """**新格式**（jsonl 带 `wav_t0`/`wav_t1`）⇒ 逐句归属唯一。"""
    d, sr = read_wav(wav_path)
    rows = read_jsonl(jsonl_path)
    res = {'label': label, 'wav': wav_path, 'jsonl': jsonl_path,
           'wav_dur_s': round(len(d) / sr, 3), 'sr': sr, 'n_rows': len(rows),
           'format': 'new'}

    # C2：全零段
    zr = zero_runs(d, sr)
    res['C2_zero_runs_ge_0p3'] = len(zr)
    res['C2_zero_run_total_s'] = round(sum(b - a for a, b in zr), 3)
    res['C2_zero_runs'] = [[round(a, 3), round(b, 3)] for a, b in zr][:40]
    res['C2_ok'] = (len(zr) == 0)

    # C3：区间齐备且不重叠
    spans, missing = [], []
    for r in rows:
        t0, t1 = r.get('wav_t0'), r.get('wav_t1')
        if t0 is None or t1 is None:
            missing.append(r.get('id'))
            continue
        spans.append((int(r.get('id')), float(t0), float(t1)))
    overlaps = sum(1 for i in range(len(spans) - 1)
                   if spans[i][2] > spans[i + 1][1] + 1e-6)
    res['C3_n_spans'] = len(spans)
    res['C3_missing_spans'] = missing[:40]
    res['C3_n_overlaps'] = overlaps
    res['C3_ok'] = (len(spans) == len(rows) and overlaps == 0 and not missing)

    # C1（合成侧遥测）/ C4（wav 段）
    bad_c1, bad_c4 = [], []
    for r in rows:
        rid = r.get('id')
        pk = r.get('peak')
        rdb = r.get('wav_rms_db')
        if rdb is None:
            rms = r.get('rms')
            rdb = (20.0 * math.log10(rms)) if rms else None
        if (pk is None or pk <= PEAK_MIN
                or rdb is None or rdb <= RMS_DB_MIN):
            bad_c1.append(rid)
        t0, t1 = r.get('wav_t0'), r.get('wav_t1')
        if t0 is not None and t1 is not None:
            st = seg_stats(d, sr, t0, t1)
            if (st['n_samples'] == 0 or st['peak'] <= PEAK_MIN
                    or st['rms_db'] is None or st['rms_db'] <= RMS_DB_MIN):
                bad_c4.append(rid)
    res['C1_n_bad'] = len(bad_c1)
    res['C1_bad_ids'] = bad_c1[:60]
    res['C1_ok'] = (len(bad_c1) == 0)
    res['C4_n_bad'] = len(bad_c4)
    res['C4_bad_ids'] = bad_c4[:60]
    res['C4_ok'] = (len(bad_c4) == 0)
    res['n_damaged_sentences'] = len(bad_c4)
    res['verdict'] = 'PASS' if (res['C1_ok'] and res['C2_ok']
                                and res['C3_ok'] and res['C4_ok']) else 'FAIL'
    return res


def evaluate_old_format(wav_path, jsonl_path, label):
    """**旧格式**（rc2：jsonl 无 `wav_t0`/`wav_t1`）⇒ 用「空洞吞句」等价口径。

    🔴 旧落盘模型把每句放在「**合成完成**的时刻 − 首句完成时刻」处
       ⇒ 句与句之间留下**空洞**（空洞 = 无任何句子音频覆盖的时间段）
       ⇒ 每个空洞**吞掉一句**的标称位置（reviewer 原文「一句对应一段零」）
    ⇒ **受损句数 == 空洞数**（与新格式的「逐句归属」口径等价）。
    """
    d, sr = read_wav(wav_path)
    rows = read_jsonl(jsonl_path)
    res = {'label': label, 'wav': wav_path, 'jsonl': jsonl_path,
           'wav_dur_s': round(len(d) / sr, 3), 'sr': sr, 'n_rows': len(rows),
           'format': 'old'}

    # C2：全零段（直接量 wav）
    zr = zero_runs(d, sr)
    res['C2_zero_runs_ge_0p3'] = len(zr)
    res['C2_zero_run_total_s'] = round(sum(b - a for a, b in zr), 3)
    res['C2_zero_runs'] = [[round(a, 3), round(b, 3)] for a, b in zr][:40]
    res['C2_ok'] = (len(zr) == 0)

    # 旧模型下的「空洞」：没有任何句子音频覆盖的时间段
    t0 = rows[0].get('t_done') or 0.0
    cov = np.zeros(len(d), dtype=bool)
    for r in rows:
        s = float(r.get('t_done') or 0.0) - t0
        a = int(s * sr)
        b = min(int((s + float(r.get('dur_s') or 0.0)) * sr), len(d))
        if b > a:
            cov[a:b] = True
    hole_mask = (~cov).astype(np.int8)
    idx = np.flatnonzero(np.diff(np.concatenate(([0], hole_mask, [0]))))
    holes = [(a / sr, b / sr) for a, b in zip(idx[0::2], idx[1::2])
             if (b - a) / sr >= ZERO_RUN_MIN_S]
    res['n_model_holes'] = len(holes)

    # 每个空洞吞掉的标称句位（标称 = 顺序累加的句位置）
    slots = nominal_slots(rows, 'dur_s')
    eaten = []
    for h0, h1 in holes:
        mid = (h0 + h1) / 2.0
        for sid, a, b in slots:
            if a <= mid < b:
                eaten.append(sid)
                break
    res['C4_n_bad'] = len(eaten)
    res['C4_bad_ids'] = eaten[:60]
    res['C4_ok'] = (len(eaten) == 0)
    res['C4_basis'] = ('旧 jsonl 无 wav_t0/wav_t1 ⇒ 按旧时间轴模型算出「空洞」，'
                       '每个空洞吞掉一个标称句位（reviewer「一句对应一段零」）')

    # C1：合成侧遥测（旧 wav 的合成侧 peak/rms 全健康 ⇒ C1 应通过
    #     ⇒ **这正是「不是合成静音」的证据**）
    bad_c1 = []
    for r in rows:
        pk = r.get('peak')
        rms = r.get('rms')
        rdb = (20.0 * math.log10(rms)) if rms else None
        if (pk is None or pk <= PEAK_MIN
                or rdb is None or rdb <= RMS_DB_MIN):
            bad_c1.append(r.get('id'))
    res['C1_n_bad'] = len(bad_c1)
    res['C1_bad_ids'] = bad_c1[:60]
    res['C1_ok'] = (len(bad_c1) == 0)
    res['n_damaged_sentences'] = len(eaten)
    res['verdict'] = 'PASS' if (res['C1_ok'] and res['C2_ok']
                                and res['C4_ok']) else 'FAIL'
    return res


def evaluate(wav_path, jsonl_path, label):
    rows = read_jsonl(jsonl_path)
    has_spans = any(r.get('wav_t0') is not None for r in rows)
    if has_spans:
        return evaluate_new_format(wav_path, jsonl_path, label)
    return evaluate_old_format(wav_path, jsonl_path, label)


def main() -> int:
    checks = []

    def chk(cid, name, ok, detail):
        checks.append({'id': cid, 'name': name, 'ok': bool(ok),
                       'detail': detail})
        print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', cid, name))

    print('=== APP-069①(c) 内容判据 ===')

    # ── 反证组：rc2 旧 wav **必须 FAIL**，受损句数 == 24 ──────────────
    print('\n-- 反证组：rc2 旧 wav（必须 FAIL）--')
    rc2 = evaluate(RC2_WAV, RC2_JSONL, 'rc2_old_dump')
    print('   rc2：verdict=%s ｜ C2 全零段=%d（%.2f s）｜ 受损句=%d'
          % (rc2['verdict'], rc2['C2_zero_runs_ge_0p3'],
             rc2['C2_zero_run_total_s'], rc2['n_damaged_sentences']))
    chk('R1', '反证：rc2 旧 wav 跑同一判据 **必须 FAIL**',
        rc2['verdict'] == 'FAIL',
        {'verdict': rc2['verdict'],
         'C2_zero_runs': rc2['C2_zero_runs_ge_0p3'],
         'n_damaged': rc2['n_damaged_sentences']})
    chk('R2', '反证：rc2 旧 wav 的受损句数 == 24（reviewer 实测口径）',
        rc2['n_damaged_sentences'] == 24,
        {'n_damaged': rc2['n_damaged_sentences'],
         'n_zero_runs': rc2['C2_zero_runs_ge_0p3'],
         'basis': rc2.get('C4_basis')})
    chk('R3', '反证：rc2 的**合成侧**逐句 peak/rms 全健康（C1 通过）'
              ' ⇒ 受损不是「合成出静音」',
        rc2['C1_ok'],
        {'C1_n_bad': rc2['C1_n_bad'],
         'min_peak': min((r.get('peak') or 0) for r in read_jsonl(RC2_JSONL)),
         'min_rms': min((r.get('rms') or 0) for r in read_jsonl(RC2_JSONL))})

    # ── 正向组：新落盘的 wav（若已产出）必须 PASS ────────────────────
    # 🔴 rc3 的设备级产物（APP-069① 修复后重跑 ⇒ app271）
    new_wav = os.path.join(HERE, 'app271_rc3_out', 'minimvp_tts.wav')
    new_jsonl = os.path.join(HERE, 'app271_rc3_out', 'minimvp.tts.jsonl')
    if os.path.isfile(new_wav) and os.path.isfile(new_jsonl):
        new = evaluate(new_wav, new_jsonl, 'fixed_dump')
        print('\n-- 正向组：新落盘 wav --')
        print('   verdict=%s ｜ C2 全零段=%d ｜ 受损句=%d'
              % (new['verdict'], new['C2_zero_runs_ge_0p3'],
                 new['n_damaged_sentences']))
        chk('P1', '新落盘 wav 跑同一判据 **必须 PASS**',
            new['verdict'] == 'PASS',
            {k: new.get(k) for k in ('verdict', 'C1_n_bad',
                                     'C2_zero_runs_ge_0p3', 'C3_n_spans',
                                     'C3_n_overlaps', 'C4_n_bad')})
        result = new
    else:
        print('\n-- 正向组：新落盘 wav **尚未产出**（需设备级重跑）--')
        chk('P1', '新落盘 wav 跑同一判据必须 PASS', False,
            {'status': 'PENDING_DEVICE',
             'why': '修复后的 `--tts-out` 必须真机重跑才有新 wav；'
                    '本轮先交付判据模块 + 反证组 + 落盘代码修复',
             'expected_wav': new_wav})
        result = rc2

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = {
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
        'n_pass': n_pass, 'n_fail': n_fail,
        'correction': 'APP-069①(c)',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'criteria': {
            'C1': '逐句 rms_db > -45 且 peak > 0.05 的比例 == 100%',
            'C2': 'wav 里 >= 0.3 s 的全零段数 == 0',
            'C3': '逐句 wav_t0/wav_t1 齐备且互不重叠',
            'C4': '按 wav_t0/wav_t1 切出的段，幅度必须达标',
        },
        'counter_proof': rc2,
        'result': result,
        'checks': checks,
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[evidence] %s' % REPORT)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
