#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **MiniMVP rc3 的 3(a) 设备级验收**（APP-069① + APP-069⑦）。

## 与 app253（rc2）的差别

| 项 | app253（rc2） | 本脚本（rc3） |
|---|---|---|
| 包 | `MiniMVP_v1.0-rc2` | `MiniMVP_v1.0-rc3` |
| **内容判据** | ❌ 无（只查「wav 已落盘」＋「tsv 有 76 行」） | ✅ **APP-068/069①(c) 的 4 条硬判据**（`app268`） |
| 逐句 wav 指标 | ❌ 无 | ✅ `wav_t0`/`wav_t1`/`peak`/`rms_db`/`speed` 进 tsv |
| tsv 列 | `id/t_submit/dur_s/voice_kind/text` | + **`wav_t0`/`wav_t1`/`peak`/`rms_db`/`speed`**（reviewer ①(b) 明文） |
| 判据**反证** | ❌ 无 | ✅ 用 rc2 旧 wav 跑同一判据 **必须 FAIL（24 句）** |

## 🔴 设备纪律

* 本脚本**自己**取机器锁（`machine_lock_app`）⇒ 与别的模块互斥；
* 跑的是 **NPU TTS + GPU.0 ASR/MT** ⇒ **占设备** ⇒ 必须持锁；
* **不通知用户、不放桌面快捷方式、不发出去**（APP-069⑦ 原文）。

## 用法
```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe results/app/_app271_minimvp_rc3_cli_acceptance.py --run
```
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

WORK = os.path.join(HERE, 'app271_rc3_out')
OUT_DIR = os.path.join(HOME, 'shared', 'app_listen', 'minimvp_v1.0')
DEFAULT_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')

# 🔴 APP-069①(c) 的判据（复用 app268 的实现，避免两处漂移）
import app268_app069_content_criterion as CRIT  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--wav', default=SPE)
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--out', default=os.path.join(
        HERE, 'app271_app069_rc3_cli_evidence.json'))
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    out = {'pkg': a.pkg, 'wav': a.wav, 'duration': a.duration,
           'started_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    py = os.path.join(a.pkg, 'python', 'python.exe')
    app = os.path.join(a.pkg, 'app', 'live_caption_app.py')
    out_wav = os.path.join(WORK, 'minimvp_tts.wav')
    jsonl = os.path.join(WORK, 'minimvp.tts.jsonl')
    txt = os.path.join(WORK, 'minimvp.txt')
    log_path = os.path.join(WORK, 'minimvp.log')

    cmd = [py, app,
           '--cli', '--file', a.wav, '--engine', 'gpu_int8',
           '--translate', 'zh',
           '--tts', 'on', '--tts-voice', 'A', '--speaker', 'off',
           '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
           '--tts-device', 'NPU',
           # 🔴 APP-066 1：MT 用 **INT4** ⇒ 显式指定（'auto' 在开发机会挑 INT8）
           '--mt-engine', 'gpu_int4cw',
           '--max-seconds', str(a.duration),
           '--tts-out', out_wav,
           '--tts-jsonl', jsonl,
           '--out', txt]
    out['cmd'] = cmd
    print('命令：\n  %s' % ' '.join(cmd))
    if a.dry_run or not a.run:
        print('（未加 --run ⇒ 不跑设备作业）')
        return 0

    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未取得机器锁 ⇒ 退出')
        out['verdict'] = 'LOCK_BUSY'
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3
    print('[lock] 已取得：%r' % (payload,))
    try:
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        env['LIVECAP_PKG'] = a.pkg
        # 🔴 必须钉住**包内 INT4** MT（'auto' 在本机会挑开发机的 INT8）
        mt_dir = os.path.join(a.pkg, 'models', 'mt', 'mt2-int4sym-cw-q')
        if os.path.isdir(mt_dir):
            env['LIVECAP_MT_MODEL'] = mt_dir
            out['mt_model_pinned'] = mt_dir
            print('MT 模型已钉住：%s' % mt_dir)
        else:
            out['mt_model_pinned'] = None
            print('!! 找不到包内 INT4 MT 目录：%s' % mt_dir)
        t0 = time.perf_counter()
        with open(log_path, 'wb') as lf:
            proc = subprocess.Popen(cmd, env=env, stdout=lf,
                                    stderr=subprocess.STDOUT)
        rc = proc.wait()
        wall = time.perf_counter() - t0
        out['rc'] = rc
        out['wall_s'] = round(wall, 2)
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        out['log_bytes'] = len(text)
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % (e,))

    # ── 逐句 jsonl ──────────────────────────────────────────────────
    rows = []
    if os.path.isfile(jsonl):
        with open(jsonl, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    okr = [r for r in rows if not r.get('dropped')]
    out['n_rows'] = len(rows)
    out['n_ok'] = len(okr)

    def pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        k = (len(s) - 1) * (p / 100.0)
        lo = int(k)
        hi = min(lo + 1, len(s) - 1)
        return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)

    rtfs = [r.get('synth_rtf') for r in okr if r.get('synth_rtf')]
    fpk = [r.get('first_packet_s') for r in okr if r.get('first_packet_s')]
    out['tts'] = {
        'synth_rtf_median': pct(rtfs, 50), 'synth_rtf_p95': pct(rtfs, 95),
        'first_packet_s_median': pct(fpk, 50),
        'first_packet_s_p95': pct(fpk, 95),
    }

    # ── 🔴🔴🔳 APP-069①(c)：**内容判据**（4 条）────────────────────
    crit = CRIT.evaluate(out_wav, jsonl, 'rc3_fixed_dump') \
        if os.path.isfile(out_wav) and os.path.isfile(jsonl) else None
    out['content_criterion'] = crit

    # ── 🔴 反证：rc2 旧 wav 跑**同一**判据必须 FAIL（24 句）──────────
    rc2_wav = os.path.join(HERE, 'app253_minimvp_out', 'minimvp_tts.wav')
    rc2_jsonl = os.path.join(HERE, 'app253_minimvp_out', 'minimvp.tts.jsonl')
    if os.path.isfile(rc2_wav) and os.path.isfile(rc2_jsonl):
        cp = CRIT.evaluate(rc2_wav, rc2_jsonl, 'rc2_old_counterproof')
        out['counter_proof'] = {
            'verdict': cp['verdict'],
            'n_damaged_sentences': cp['n_damaged_sentences'],
            'C2_zero_runs_ge_0p3': cp['C2_zero_runs_ge_0p3'],
        }
        print('[反证] rc2 旧 wav：verdict=%s ｜ 受损句=%d'
              % (cp['verdict'], cp['n_damaged_sentences']))

    # ── 交付：wav + **带 wav 指标的 tsv** ─────────────────────────
    dst_wav = os.path.join(OUT_DIR, 'minimvp_v1.0_rc3_tts.wav')
    if os.path.isfile(out_wav):
        shutil.copy2(out_wav, dst_wav)
        out['deliverable_wav'] = {'path': dst_wav,
                                  'bytes': os.path.getsize(dst_wav)}
    trans_path = os.path.join(OUT_DIR, 'minimvp_v1.0_rc3_transcript.tsv')
    n = 0
    with open(trans_path, 'w', encoding='utf-8') as f:
        # 🔴 reviewer ①(b)：tsv 每行加 wav_t0/wav_t1/peak/rms_db/speed
        f.write('id\tt_submit\tdur_s\tvoice_kind\twav_t0\twav_t1\t'
                'peak\trms_db\tspeed\ttext\n')
        for r in sorted(rows, key=lambda x: x.get('id') or 0):
            f.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n'
                    % (r.get('id'), r.get('t_submit'), r.get('dur_s'),
                       r.get('voice_kind'),
                       r.get('wav_t0'), r.get('wav_t1'),
                       r.get('wav_peak'), r.get('wav_rms_db'),
                       r.get('speed'),
                       (r.get('text') or '').replace('\t', ' ')))
            n += 1
    out['deliverable_transcript'] = {'path': trans_path, 'n_rows': n,
                                     'bytes': os.path.getsize(trans_path)}

    # ── 汇总判据 ────────────────────────────────────────────────────
    checks = []

    def add(name, ok, detail):
        checks.append({'name': name, 'verdict': bool(ok), 'detail': detail})
        print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name,
                                 json.dumps(detail, ensure_ascii=False)[:220]))

    add('③(a) 配音 wav 已落盘', os.path.isfile(out_wav),
        {'path': out_wav, 'bytes': os.path.getsize(out_wav)
         if os.path.isfile(out_wav) else None})
    add('③(a) 每段译文已落盘（含 wav 指标列）', n > 0,
        {'path': trans_path, 'n_rows': n})
    if crit:
        add('①(c) 内容判据 C1（逐句 rms_db>-45 且 peak>0.05 比例 100%）',
            crit['C1_ok'], {'n_bad': crit['C1_n_bad']})
        add('①(c) 内容判据 C2（wav 全零段 ≥0.3 s 的个数 == 0）',
            crit['C2_ok'],
            {'n_zero_runs': crit['C2_zero_runs_ge_0p3'],
             'total_s': crit['C2_zero_run_total_s']})
        add('①(c) 内容判据 C3（wav_t0/wav_t1 齐备且互不重叠）',
            crit['C3_ok'], {'n_spans': crit['C3_n_spans'],
                            'n_overlaps': crit['C3_n_overlaps'],
                            'n_missing': len(crit['C3_missing_spans'])})
        add('①(c) 内容判据 C4（按 wav_t0/wav_t1 切段后幅度达标）',
            crit['C4_ok'], {'n_bad': crit['C4_n_bad']})
        add('①(c) 内容判据总判定 == PASS', crit['verdict'] == 'PASS',
            {'verdict': crit['verdict']})
    if 'counter_proof' in out:
        cp = out['counter_proof']
        add('①(c) 反证：rc2 旧 wav 跑同一判据必须 FAIL（24 句）',
            cp['verdict'] == 'FAIL' and cp['n_damaged_sentences'] == 24,
            cp)
    add('TTS RTF 中位/P95 有实测值',
        out['tts']['synth_rtf_median'] is not None, out['tts'])

    n_pass = sum(1 for c in checks if c['verdict'] is True)
    n_fail = sum(1 for c in checks if c['verdict'] is False)
    out['checks'] = checks
    out['n_pass'], out['n_fail'] = n_pass, n_fail
    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    out['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[evidence] %s' % a.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
