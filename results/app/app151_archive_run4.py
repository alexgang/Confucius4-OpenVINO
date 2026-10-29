# -*- coding: utf-8 -*-
"""app151 — 把 APP-042 **worker 侧定速修复后**的真机实测（run4）产物只读归档进仓库。

🔴 **只读复制**：不移动、不删除 `C:\\Users\\Trekker-PTL\\app042_soak\\` 里的任何文件
（那是 OUT_DIR，属于实测脚本的产物目录；删它会触发批量删除保护）。
🔴 **零推理、零 NPU、零锁**：纯文件拷贝 + SHA256。
🔴 **新旧判别（防把旧产物当新产物）**：report 的 `ts` 必须晚于 **run3（23:26）**，
   否则拒绝归档 ⇒ 保证归档的一定是「worker 侧定速修复后」这一轮。

🔴 **额外判别（防半交付）**：`app042_soak.wav.tts.jsonl` 里必须出现新遥测字段
   `speed_lag_s`（这是本次修复新增的字段）；若整份 jsonl 都没有 ⇒
   那不是修复后的产物 ⇒ 拒绝归档。

用法：
    python results/app/app151_archive_run4.py --out results/app/app042_soak_run4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
OUT_DIR = r'C:\Users\Trekker-PTL\app042_soak'
# run3 产物 report 的 mtime（2026-10-29 23:26），run4 必须更新
RUN3_MTIME = time.mktime(time.strptime('2026-10-29 23:26:00', '%Y-%m-%d %H:%M:%S'))

WANT = [
    'app042_soak_report.json',
    'app042_soak.wav.tts.jsonl',
    'app042_lag_curve.csv',
    'app042_speed_distribution.csv',
    'app042_soak_cli.log',
    'app042_subtitles.txt',
    'app042_subtitles.mt.txt',
    'clips_1p2_to_1p3',
]

NEW_TELEMETRY_KEY = 'speed_lag_s'


def sha256(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out or os.path.join(
        REPO, 'results', 'app', 'app042_soak_run4'))

    rep = os.path.join(OUT_DIR, 'app042_soak_report.json')
    if not os.path.exists(rep):
        print('[FAIL] 找不到 report：%s ⇒ 实测还没跑完' % rep)
        return 2
    rep_mtime = os.path.getmtime(rep)
    if rep_mtime <= RUN3_MTIME:
        print('[FAIL] report mtime=%s 不晚于 run3(23:26) ⇒ 这不是 run4 产物，'
              '拒绝归档' % time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(rep_mtime)))
        return 3

    with open(rep, 'r', encoding='utf-8') as f:
        report = json.load(f)
    ts = str(report.get('ts') or '')

    try:
        tts = time.mktime(time.strptime(ts, '%Y-%m-%d %H:%M:%S'))
    except Exception:
        tts = 0.0
    if tts <= RUN3_MTIME:
        print('[FAIL] report.ts=%r 不晚于 run3 ⇒ 拒绝归档' % ts)
        return 4

    # 🔴 新遥测字段判别：必须是「worker 侧定速修复后」的产物
    jl = os.path.join(OUT_DIR, 'app042_soak.wav.tts.jsonl')
    if not os.path.exists(jl):
        print('[FAIL] 找不到 jsonl：%s' % jl)
        return 5
    n_rows = 0
    n_with_key = 0
    speeds = []
    lags = []
    with open(jl, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            n_rows += 1
            if NEW_TELEMETRY_KEY in o:
                n_with_key += 1
            if o.get('speed') is not None:
                try:
                    speeds.append(float(o['speed']))
                except Exception:
                    pass
            if o.get('speed_lag_s') is not None:
                try:
                    lags.append(float(o['speed_lag_s']))
                except Exception:
                    pass
    if n_rows == 0:
        print('[FAIL] jsonl 无有效行 ⇒ 拒绝归档')
        return 6
    if n_with_key == 0:
        print('[FAIL] jsonl 里 0 行含新遥测字段 %r ⇒ 这不是 worker 侧定速修复后的'
              '产物，拒绝归档（jsonl 共 %d 行）' % (NEW_TELEMETRY_KEY, n_rows))
        return 7

    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)

    items = []
    for rel in WANT:
        src = os.path.join(OUT_DIR, rel)
        if not os.path.exists(src):
            items.append(dict(rel=rel, kind='missing'))
            continue
        dst = os.path.join(out_dir, rel)
        if os.path.isdir(src):
            if not args.dry_run:
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            files = []
            base = dst if not args.dry_run else src
            for root, _, fs in os.walk(base):
                for fn in fs:
                    fp = os.path.join(root, fn)
                    files.append(dict(
                        path=os.path.relpath(fp, base),
                        bytes=os.path.getsize(fp),
                        sha256=sha256(fp)))
            items.append(dict(rel=rel, kind='dir', n_files=len(files),
                              files=files))
        else:
            if not args.dry_run:
                shutil.copy2(src, dst)
            items.append(dict(rel=rel, kind='file',
                              bytes=os.path.getsize(src),
                              sha256=sha256(src)))

    manifest = dict(
        ts=time.strftime('%Y-%m-%d %H:%M:%S'),
        source_dir=OUT_DIR,
        out_dir=out_dir,
        run='run4',
        parent_run='run3',
        report_ts=ts,
        report_mtime=time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(rep_mtime)),
        new_telemetry_key=NEW_TELEMETRY_KEY,
        jsonl_rows=n_rows,
        jsonl_rows_with_new_key=n_with_key,
        jsonl_speed_max=(max(speeds) if speeds else None),
        jsonl_speed_n_1p0=sum(1 for s in speeds if abs(s - 1.0) < 1e-6),
        jsonl_speed_n_1p2_to_1p3=sum(1 for s in speeds
                                     if 1.2 <= s <= 1.3),
        jsonl_speed_lag_s_max=(max(lags) if lags else None),
        report=report,
        items=items,
    )
    if not args.dry_run:
        mp = os.path.join(out_dir, 'MANIFEST.json')
        with open(mp, 'w', encoding='utf-8', newline='') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print('[MANIFEST] %s (%d B)' % (mp, os.path.getsize(mp)))

    print('== 归档清单 ==')
    for it in items:
        if it['kind'] == 'missing':
            print('  MISSING  %s' % it['rel'])
        elif it['kind'] == 'dir':
            print('  DIR      %s  (%d 文件)' % (it['rel'], it['n_files']))
            for fi in it['files']:
                print('      %-46s %10d B  %s'
                      % (fi['path'], fi['bytes'], fi['sha256'][:16]))
        else:
            print('  FILE     %-46s %10d B  %s'
                  % (it['rel'], it['bytes'], it['sha256'][:16]))

    print('\n== jsonl 原始字段统计（直接来自 telemetry 行）==')
    print('  rows                      = %d' % n_rows)
    print('  rows with %-14s = %d' % (NEW_TELEMETRY_KEY, n_with_key))
    print('  speed_max                 = %r' % (max(speeds) if speeds else None))
    print('  speed==1.0 句数           = %d'
          % sum(1 for s in speeds if abs(s - 1.0) < 1e-6))
    print('  speed in [1.2,1.3] 句数   = %d'
          % sum(1 for s in speeds if 1.2 <= s <= 1.3))
    print('  speed_lag_s max           = %r' % (max(lags) if lags else None))

    print('\n== report 关键字段 ==')
    for k in ('ts', 'device', 'duration', 'wall_s', 'rc',
              'n_submitted', 'n_played', 'n_dropped', 'n_restart',
              'n_telemetry', 'lag_start_s', 'lag_peak_s', 'lag_end_s',
              'lag_median_s', 'max_backlog_s', 'first_packet_s',
              'pass_count', 'fail_count'):
        if k in report:
            print('  %-16s = %r' % (k, report[k]))
    for c in report.get('checks', []):
        print('  [%s] %-46s ok=%-5s got=%r want=%r'
              % (c.get('id'), c.get('name'), c.get('ok'),
                 c.get('got'), c.get('want')))
    if 'clips' in report:
        print('  clips = %r' % (report['clips'],))
    return 0


if __name__ == '__main__':
    sys.exit(main())
