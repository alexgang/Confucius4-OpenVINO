#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app466_rejudge.py —— 对**已完成**的两臂设备证据**重新判定**（不重跑设备）。

## 为什么需要
§177 的两臂**已经跑完且都自然退出**（`exit=0`），但收尾写报告时脚本报错
⇒ `app461_app100_device.json` 的 `verdict` 停在 `PENDING`、
且 `checks.asr_nonempty=False`（**假 FAIL**）。

假 FAIL 的根因（§177 自踩）：本轮启动时 `--outroot` 传的是**相对路径**
⇒ 被测程序以 `cwd=pkg` 运行 ⇒ `--out` / `--tts-out` 落进 **rc7 包目录内**
⇒ 判据按（相对仓库根的）`out_path` 去读 ⇒ 读不到 ⇒ `asr_nonempty=False`。
⇒ 脚本已修（`os.path.abspath`），且**产物已逐字节抢救回**仓库证据目录。

## 本脚本做什么
**只重新判定 + 重算 verdict**，不碰设备、不跑推理、不改任何产物：
1. 从**仓库内**证据目录读两臂的 log / txt / mt.txt / wav / jsonl；
2. 用**与 `_app437` 完全相同**的 `judge_arm()` 重新判定各组件
   ⇒ 与主脚本同一套口径（不是另写一套判据）；
3. 重算 `verdict`（期望臂数按本轮实际跑的臂数）；
4. 落盘 `results/app/app466_app100_device_rejudge.json`；
5. **不改** `app461_app100_device.json`（write-once 的原始证据）。

## 纪律
* 不占 GPU/NPU、**不取机器锁**（不跑设备作业）；
* 不调 MiniMax；质量判定交 reviewer；
* 不改任何产品默认值/阈值；
* 原始证据 json **只读不改**。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for p in (REPO, os.path.join(REPO, 'live_caption'), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

#: 真 import 主脚本（拿到**同一套** judge_arm / ARM 定义）
_spec = importlib.util.spec_from_file_location(
    '_app437_mod', os.path.join(HERE, '_app437_app099_device_jobs.py'))
MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MOD)

ORIG_REPORT = os.path.join(HERE, 'app461_app100_device.json')
OUT_REPORT = os.path.join(HERE, 'app466_app100_device_rejudge.json')
EVIDENCE = os.path.join(HERE, 'app461_app100_device')


def main():
    if not os.path.isfile(ORIG_REPORT):
        print('!! 找不到原始报告 %s' % ORIG_REPORT)
        return 2
    orig = json.load(open(ORIG_REPORT, 'r', encoding='utf-8'))

    out = dict(orig)
    out['rejudge_note'] = (
        '§177：两臂设备跑已完成（都 exit=0 自然退出），但收尾写报告时脚本报错 '
        '⇒ 原报告 verdict 停在 PENDING、checks.asr_nonempty=False（假 FAIL，'
        '根因是本轮 --outroot 用了相对路径 ⇒ 产物落进 rc7 包内；'
        '产物已逐字节抢救回仓库证据目录）。本文件用**同一套** judge_arm() '
        '对仓库内证据重新判定并重算 verdict；**不改**原报告。')
    out['rejudged_at'] = None

    new_gpu = []
    for a in orig.get('gpu_arms', []):
        name = a['arm']
        opts = a.get('opts', [])
        log_path = os.path.join(EVIDENCE, name + '.log')
        out_path = os.path.join(EVIDENCE, name + '.txt')
        wav_path = os.path.join(EVIDENCE, name + '.wav')
        rec = MOD.judge_arm(name, opts, MOD.read_txt(log_path), log_path,
                            out_path, wav_path, None)
        # 保留**原报告**里的运行期事实（退出码/耗时/采样/命令行）
        for k in ('exit_code', 'seconds', 'cmd', 'pass_components_only',
                  'terminated_by_harness', 'crash', 'crash_at_s',
                  'natural_exit', 'sampling', 'app100_segment'):
            if k in a:
                rec[k] = a[k]
        rec['pass_components_only'] = rec['pass']
        rec['pass'] = bool(rec['pass'] and rec.get('exit_code') == 0)
        rec['terminated_by_harness'] = (rec.get('exit_code') == -9)
        rec['crash'] = (rec.get('exit_code') not in (0, -9, None))
        rec['natural_exit'] = (rec.get('exit_code') == 0)
        new_gpu.append(rec)

    out['gpu_arms'] = new_gpu
    out['gpu_arms_rejudged'] = True

    ok_gpu = sum(1 for a in new_gpu if a['pass'] and a.get('exit_code') == 0)
    out['n_gpu_arms'] = len(new_gpu)
    out['n_gpu_arms_ok'] = ok_gpu
    all_arms = out.get('arms', []) + new_gpu
    non_natural = [a['arm'] for a in all_arms if a.get('exit_code') != 0]
    out['timing_valid'] = (len(non_natural) == 0)
    out['timing_notes'] = ([] if not non_natural else
                            ['非自然退出臂：%s' % ', '.join(non_natural)])
    want_gpu = [a['arm'] for a in new_gpu]
    out['n_arms'] = len(out.get('arms', []))
    out['want_arms'] = out['n_arms']
    out['want_gpu_arms'] = len(want_gpu)
    out['want_arm_names'] = [a['arm'] for a in out.get('arms', [])] + want_gpu
    ok_arms = sum(1 for a in out.get('arms', [])
                  if a['pass'] and a.get('exit_code') == 0)
    out['verdict'] = ('PASS' if out['n_arms'] == out['want_arms']
                      and ok_arms == out['want_arms']
                      and out['n_gpu_arms'] == out['want_gpu_arms']
                      and ok_gpu == out['want_gpu_arms']
                      and out['timing_valid'] else 'PARTIAL')

    with open(OUT_REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('verdict = %s' % out['verdict'])
    print('timing_valid = %s' % out['timing_valid'])
    for a in new_gpu:
        print('  %-20s exit=%s %ss natural=%s pass=%s checks=%s'
              % (a['arm'], a.get('exit_code'), a.get('seconds'),
                 a.get('natural_exit'), a['pass'], a['checks']))
        print('      asr=%s' % a['asr'])
        print('      tts=%s' % a['tts'])
        s = a.get('sampling', {})
        print('      sampling n=%s ok=%s shared=%s MB rss=%s MB'
              % (s.get('n_samples'), s.get('sampling_ok'),
                 s.get('peak_gpu_shared_mb'), s.get('peak_proc_rss_mb')))
    print('evidence: %s' % OUT_REPORT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
