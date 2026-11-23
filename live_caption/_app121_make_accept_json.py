#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §4：**从验收证据生成 README 的注入数据**（`accept` json）。

## 为什么要有这一步
README 里的「A 机实测」数字**必须来自结果文件**（不能手抄、不能编造）⇒
本脚本从 `app591_acceptance_app121_v111_default_run*.json` ＋ 对应 run 的
**原始日志**里取数，生成 `results/app/app121_readme_accept.json`，
再交给 `_app121_write_readme.py` 注入。

## 取的数（逐条指到来源）
| 字段 | 来源 |
|---|---|
| `subtitle_first_token_ms` | run 日志里的 `[gpu_int8] … 出字延迟中位 N ms`（**识别**侧） |
| `tts_first_packet_s` | run 日志里的 `[TTS] 首包 N.NNs`（**配音**侧，与上面**不是一个数**） |
| `synth_rtf_median/p90` | 验收 json 的 `speed_histogram` / `telemetry` |
| `backlog_peak_s/final_s` | 验收 json 的 `play_lag_max` / `play_lag_end` |
| `n_sentences/n_played/n_dropped` | 验收 json 的 `sentence_counts` |
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--acc', default=os.path.join(
        RESULTS, 'app591_acceptance_app121_v111_default_run20261123-1000.json'))
    ap.add_argument('--out', default=os.path.join(
        RESULTS, 'app121_readme_accept.json'))
    args = ap.parse_args()
    with io.open(args.acc, 'r', encoding='utf-8') as f:
        acc = json.load(f)

    log_path = os.path.join(
        RESULTS, '_app591_app121_v111_default_run20261123-1000.log')
    text = ''
    if os.path.isfile(log_path):
        with io.open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()

    m = re.search(r'出字延迟中位\s+(\d+)\s*ms', text)
    subtitle_ms = int(m.group(1)) if m else None
    m = re.search(r'\[TTS\]\s*首包\s+([0-9.]+)s', text)
    tts_first = float(m.group(1)) if m else None

    sh = acc.get('speed_histogram') or {}
    tel = acc.get('telemetry') or {}
    sc = acc.get('sentence_counts') or {}

    def pick(*keys):
        for k in keys:
            if isinstance(tel, dict) and tel.get(k) is not None:
                return tel[k]
            if isinstance(sh, dict) and sh.get(k) is not None:
                return sh[k]
        return None

    data = {
        'chain': {
            'device_combo': 'ASR=GPU.0 / MT=GPU.0 / TTS=NPU（出厂默认）',
            'subtitle_first_token_ms': subtitle_ms,
            'subtitle_first_token_src':
                'run 日志 `[gpu_int8] … 出字延迟中位 %s ms`（**识别**侧）'
                % subtitle_ms,
            'tts_first_packet_s': tts_first,
            'tts_first_packet_src':
                'run 日志 `[TTS] 首包 %ss`（**配音**侧，与字幕出字延迟**不是一个数**）'
                % tts_first,
            'synth_rtf_median': pick('synth_rtf_p50'),
            'synth_rtf_p90': pick('synth_rtf_p90'),
            'backlog_peak_s': pick('play_lag_max'),
            'backlog_final_s': pick('play_lag_end'),
            'n_sentences': sc.get('n_translations'),
            'n_played': pick('n_played'),
            'n_dropped': sc.get('n_drop_total_any_reason'),
        },
        'source_acc': args.acc,
        'source_log': log_path,
        'timing_valid': acc.get('timing_valid'),
        'timing_invalid_reason': acc.get('timing_invalid_reason'),
        'zip_bytes': None,
    }
    tmp = args.out + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.out)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print('→ %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
