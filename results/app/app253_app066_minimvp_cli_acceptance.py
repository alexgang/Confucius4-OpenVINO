#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app253 — **APP-066 3(a)**：MiniMVP 最小客户包的 CLI 设备级验收。

> 3(a) CLI 跑 SPE 英文 5 分钟片段，走英→中、带配音的完整链路，记录以下指标：
>   - 用时 ≤ 音频长度 + 3 s；
>   - 最大积压 ≤ 2 s；
>   - ASR/MT/TTS 各自的 RTF 和延迟中位数、P95；
>   - 系统 CPU 的峰值和均值。
>   配音输出的 wav 放到 `shared\\app_listen\\minimvp_v1.0\\`，附上每段对应的译文。

## 口径
* 音频 = `shared/SPE_0000_0500.wav`（**项目通用的「SPE 前 5 分钟切片」**
  ⇒ 与 APP-027/APP-061 的历次实测**同一把尺**）。
* 包 = `Confucius4_LiveCaption_MiniMVP_v1.0-rc1`（APP-066 的 7 闸门全绿版本）。
* CPU 采样 = **进程树**（主进程 + TTS worker 子进程），psutil，1 s 间隔。
* 判据**三态**：True / False / None。

## 用法
```
.venv/Scripts/python.exe results/app/app253_app066_minimvp_cli_acceptance.py --run
```
（🔴 必须用**仓库 .venv**：本机默认 python **没有 psutil**。）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc1')
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUT_DIR = os.path.join(HOME, 'shared', 'app_listen', 'minimvp_v1.0')
WORK = os.path.join(HERE, 'app253_minimvp_out')
OUT_JSON = os.path.join(HERE, 'app253_app066_minimvp_cli_evidence.json')

_RE_SUMMARY = re.compile(
    r'\[(?P<engine>[^\]]+)\]\s*音频\s+(?P<audio>[0-9.]+)s\s*'
    r'墙钟\s+(?P<wall>[0-9.]+)s\s*'
    r'RTF\(计算\)\s+(?P<rtf>[0-9.]+)\s*'
    r'出字延迟中位\s+(?P<lat>[0-9.]+|None)\s*ms\s*'
    r'最大积压\s+(?P<backlog>[0-9.]+)s\s*'
    r'段\s+(?P<segs>[0-9]+)')


def parse_summary(text):
    m = None
    for m in _RE_SUMMARY.finditer(text):
        pass
    if not m:
        return {}
    d = m.groupdict()
    for k in ('audio', 'wall', 'rtf', 'backlog'):
        try:
            d[k] = float(d[k])
        except (TypeError, ValueError):
            d[k] = None
    try:
        d['lat_ms'] = float(d.pop('lat')) if d.get('lat') not in (None, 'None') \
            else None
    except (TypeError, ValueError):
        d['lat_ms'] = None
    try:
        d['segs'] = int(d.get('segs'))
    except (TypeError, ValueError):
        d['segs'] = None
    return d


class CpuSampler(threading.Thread):
    """采样**进程树**的 CPU 占用（%）。"""

    def __init__(self, proc, interval=1.0):
        super().__init__(daemon=True)
        self.proc = proc
        self.interval = interval
        self.samples = []
        self.stop_flag = False

    def run(self):
        import psutil
        try:
            root = psutil.Process(self.proc.pid)
        except Exception:
            return
        while not self.stop_flag:
            tot = 0.0
            n = 0
            try:
                procs = [root] + root.children(recursive=True)
                for p in procs:
                    try:
                        tot += p.cpu_percent(interval=None)
                        n += 1
                    except Exception:
                        pass
                self.samples.append({'t': time.time(),
                                     'cpu_pct': round(tot, 2),
                                     'n_procs': n})
            except Exception:
                pass
            time.sleep(self.interval)

    def stop(self):
        self.stop_flag = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--wav', default=SPE)
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    out = {'script': 'app253_app066_minimvp_cli_acceptance.py',
           'correction': 'APP-066 3(a)',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args), 'checks': []}

    def add(name, verdict, detail, why=''):
        out['checks'].append({'name': name, 'verdict': verdict,
                              'detail': detail, 'why': why})
        print('  [%s] %s%s' % ({True: 'PASS', False: 'FAIL',
                                None: 'NONE'}[verdict], name,
                               ('  ' + json.dumps(detail, ensure_ascii=False))
                               if detail else ''))

    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    py = os.path.join(args.pkg, 'python', 'python.exe')
    app = os.path.join(args.pkg, 'app', 'live_caption_app.py')
    out_wav = os.path.join(WORK, 'minimvp_tts.wav')
    jsonl = os.path.join(WORK, 'minimvp.tts.jsonl')
    txt = os.path.join(WORK, 'minimvp.txt')
    log_path = os.path.join(WORK, 'minimvp.log')
    cmd = [py, app,
           '--cli', '--file', args.wav, '--engine', 'gpu_int8',
           '--translate', 'zh',
           '--tts', 'on', '--tts-voice', 'A', '--speaker', 'off',
           '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
           '--tts-device', 'NPU',
           # 🔴 APP-066 1：MT 用 **INT4** ⇒ 显式指定（'auto' 在本机会挑开发机的 INT8）
           '--mt-engine', 'gpu_int4cw',
           '--max-seconds', str(args.duration),
           '--tts-out', out_wav,
           '--tts-jsonl', jsonl,
           '--out', txt]
    out['cmd'] = cmd
    print('命令：\n  %s' % ' '.join(cmd))
    if args.dry_run:
        print('（--dry-run：没有跑设备作业）')
        return 0
    if not args.run:
        print('（未加 --run ⇒ 不跑设备作业）')
        return 0

    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未取得机器锁 ⇒ 退出')
        out['verdict'] = 'LOCK_BUSY'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3
    print('[lock] 已取得：%r' % (payload,))
    try:
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        env['LIVECAP_PKG'] = args.pkg
        # 🔴🔴 **必须钉住 MT 模型**（APP-066 1：MT 用 **INT4**）：
        #   `translator.DEFAULT_MODEL` 的 'auto' 候选顺序是
        #   「包内 INT8 → 包内 INT8 → **开发机 ~/hy_bench/ov 的 INT8** → 包内 INT4 …」
        #   ⇒ **本机** `~/hy_bench/ov/mt2-int8sym-cw-q` 存在 ⇒ auto 会挑**开发机的 INT8**
        #   ⇒ 实测首轮就是这样（log: 「INT8-CW 模型（默认）」⇒ **量的不是 INT4**）。
        #   ⇒ 客户机没有 hy_bench ⇒ 会落到包内 INT4 ⇒ 但**验收必须量的就是 INT4**
        #   ⇒ 用 `LIVECAP_MT_MODEL` 显式钉住包内 INT4 目录。
        mt_dir = os.path.join(args.pkg, 'models', 'mt', 'mt2-int4sym-cw-q')
        if os.path.isdir(mt_dir):
            env['LIVECAP_MT_MODEL'] = mt_dir
            out['mt_model_pinned'] = mt_dir
            print('MT 模型已钉住：%s' % mt_dir)
        else:
            out['mt_model_pinned'] = None
            print('!! 找不到包内 INT4 MT 目录：%s ⇒ 量的可能不是 INT4' % mt_dir)
        t0 = time.perf_counter()
        with open(log_path, 'wb') as lf:
            proc = subprocess.Popen(cmd, env=env, stdout=lf,
                                    stderr=subprocess.STDOUT)
        sampler = CpuSampler(proc)
        sampler.start()
        rc = proc.wait()
        wall = time.perf_counter() - t0
        sampler.stop()
        time.sleep(1.2)
        out['rc'] = rc
        out['runner_wall_s'] = round(wall, 2)
        out['cpu_samples'] = sampler.samples
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        out['log_bytes'] = len(text.encode('utf-8', 'replace'))
        summ = parse_summary(text)
        out['summary'] = summ
        print('汇总行：', json.dumps(summ, ensure_ascii=False))

        # ── CPU 峰值 / 均值 ────────────────────────────────────
        cpus = [s['cpu_pct'] for s in sampler.samples]
        cpu_peak = max(cpus) if cpus else None
        cpu_mean = round(statistics.fmean(cpus), 2) if cpus else None
        out['cpu'] = {'peak_pct': cpu_peak, 'mean_pct': cpu_mean,
                      'n_samples': len(cpus)}
        print('CPU：峰值 %s %% / 均值 %s %%（%d 个采样）'
              % (cpu_peak, cpu_mean, len(cpus)))

        # ── 逐句 jsonl ⇒ TTS RTF / 延迟 ───────────────────────
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

        def pct(vals, p):
            if not vals:
                return None
            s = sorted(vals)
            k = (len(s) - 1) * (p / 100.0)
            lo = int(k)
            hi = min(lo + 1, len(s) - 1)
            return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)

        synth_rtfs = [float(r['synth_rtf']) for r in okr
                      if isinstance(r.get('synth_rtf'), (int, float))]
        fps = [float(r['t_first_packet']) for r in okr
               if isinstance(r.get('t_first_packet'), (int, float))]
        out['tts'] = {
            'n_rows': len(rows), 'n_ok': len(okr),
            'n_dropped': sum(1 for r in rows if r.get('dropped')),
            'n_error': sum(1 for r in rows if r.get('error')),
            'synth_rtf_median': pct(synth_rtfs, 50),
            'synth_rtf_p95': pct(synth_rtfs, 95),
            'synth_rtf_mean': (round(statistics.fmean(synth_rtfs), 4)
                               if synth_rtfs else None),
            'first_packet_s_median': pct(fps, 50),
            'first_packet_s_p95': pct(fps, 95),
            'voice_kind_counts': {},
        }
        kinds = {}
        for r in okr:
            k = r.get('voice_kind') or 'unknown'
            kinds[k] = kinds.get(k, 0) + 1
        out['tts']['voice_kind_counts'] = kinds

        # ── 判据 ───────────────────────────────────────────────
        audio_s = summ.get('audio')
        wall_s = summ.get('wall')
        backlog = summ.get('backlog')
        add('③(a)-① 用时 ≤ 音频长度 + 3 s',
            (wall_s is not None and audio_s is not None
             and wall_s <= audio_s + 3.0),
            {'audio_s': audio_s, 'wall_s': wall_s,
             'limit_s': (audio_s + 3.0) if audio_s else None})
        add('③(a)-② 最大积压 ≤ 2 s', (backlog is not None and backlog <= 2.0),
            {'max_backlog_s': backlog, 'limit_s': 2.0})
        add('③(a)-③ ASR RTF 有实测值', summ.get('rtf') is not None,
            {'rtf': summ.get('rtf')})
        add('③(a)-③ TTS RTF 中位/P95 有实测值',
            (out['tts']['synth_rtf_median'] is not None
             and out['tts']['synth_rtf_p95'] is not None),
            {'median': out['tts']['synth_rtf_median'],
             'p95': out['tts']['synth_rtf_p95']})
        add('③(a)-③ 出字延迟中位/P95 有实测值',
            (out['tts']['first_packet_s_median'] is not None
             and out['tts']['first_packet_s_p95'] is not None),
            {'median_s': out['tts']['first_packet_s_median'],
             'p95_s': out['tts']['first_packet_s_p95']})
        add('③(a)-④ CPU 峰值/均值有实测值',
            (cpu_peak is not None and cpu_mean is not None),
            {'peak_pct': cpu_peak, 'mean_pct': cpu_mean})
        add('③(a) 配音 wav 已落盘', os.path.isfile(out_wav),
            {'path': out_wav,
             'bytes': os.path.getsize(out_wav) if os.path.isfile(out_wav)
             else None})

        # ── 交付：配音 wav + 每段译文 → shared/app_listen/minimvp_v1.0/ ──
        import shutil
        dst_wav = os.path.join(OUT_DIR, 'minimvp_v1.0_tts.wav')
        if os.path.isfile(out_wav):
            shutil.copy2(out_wav, dst_wav)
            out['deliverable_wav'] = {'path': dst_wav,
                                      'bytes': os.path.getsize(dst_wav)}
        # 逐句 原文/译文（供 reviewer 回转写 + 用户抽听）
        trans_path = os.path.join(OUT_DIR, 'minimvp_v1.0_transcript.tsv')
        n = 0
        with open(trans_path, 'w', encoding='utf-8') as f:
            f.write('id\tt_submit\tdur_s\tvoice_kind\ttext\n')
            for r in sorted(rows, key=lambda x: x.get('id') or 0):
                f.write('%s\t%s\t%s\t%s\t%s\n'
                        % (r.get('id'), r.get('t_submit'), r.get('dur_s'),
                           r.get('voice_kind'),
                           (r.get('text') or '').replace('\t', ' ')))
                n += 1
        out['deliverable_transcript'] = {'path': trans_path, 'n_rows': n,
                                         'bytes': os.path.getsize(trans_path)}
        # 原始定稿文本（ASR 原文 + 译文）
        if os.path.isfile(txt):
            shutil.copy2(txt, os.path.join(OUT_DIR, 'minimvp_v1.0_final.txt'))
            out['deliverable_final_txt'] = {
                'path': os.path.join(OUT_DIR, 'minimvp_v1.0_final.txt'),
                'bytes': os.path.getsize(txt)}
        add('③(a) 每段译文已落盘', n > 0, {'path': trans_path, 'n_rows': n})
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % (e,))
    n_pass = sum(1 for c in out['checks'] if c['verdict'] is True)
    n_fail = sum(1 for c in out['checks'] if c['verdict'] is False)
    n_none = sum(1 for c in out['checks'] if c['verdict'] is None)
    out['n_pass'], out['n_fail'], out['n_none'] = n_pass, n_fail, n_none
    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\n结果：%d PASS / %d FAIL / %d NONE ⇒ %s'
          % (n_pass, n_fail, n_none, out['verdict']))
    print('[evidence] %s' % args.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
