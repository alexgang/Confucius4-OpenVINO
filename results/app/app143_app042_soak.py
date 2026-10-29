# -*- coding: utf-8 -*-
"""app143 — APP-042 的**真机实测**（SPE 前 5 分钟、默认设备摆放、持锁）。

🔴🔴🔴 **必须持机器锁**（推理作业）⇒ 本脚本**自己取锁**（`machine_lock_app`，fail-closed）。
🔴 **不在 CPU 上跑推理** —— 设备固定 **NPU**（本机无 CUDA 运行时，见 §78.6）。
🔴 **不自己调用 MiniMax**（reviewer 侧 `quota.py` 不在本机）。
🔴 **不开/不重发 FTP**（APP-035：FTP 已永久关闭）。

## reviewer APP-042 明文验收

> **验收**：SPE 前 5 分钟，默认设备摆放，持锁。报告滞后随时间的曲线（起点、峰值、结尾）
> 和各倍率的时间占比，**丢句 = 0**；挑 3 段 1.2–1.3× 的配音落盘，供用户抽听，
> 确认不变调、可懂；reviewer 做回转写，确认加速后错误率不明显上升。

## 本脚本做哪一段、哪一段不做

✅ **做（工程侧）**：
- SPE 前 5 分钟固定切片（`shared/SPE_0000_0500.wav`）按 `--speed 1` **实时回放**；
- 设备 = **NPU**；持机器锁 + 等安静窗口；
- 采集逐句遥测（`x.tts.jsonl`：`speed` / `play_lag_s` / `out_dur_s` / `in_dur_s` /
  `speed_gain` / `queued_s` / `synth_rtf` / `queue_peak_s` / `end_reason` …）；
- 判 **丢句数 = 0** + 不变式 `n_played + n_dropped == n_submitted`；
- 落盘 **滞后随时间曲线 csv**（起点 / 峰值 / 结尾）＋ **各倍率时间占比 csv**；
- **挑 3 段 1.2–1.3× 的句子**，把对应音频**切出来落盘**（供用户抽听）。

⛔ **不做（不能替代）**：
- **用户实听判断**（用户本人确认前不得写「不变调、可懂」）；
- **reviewer 的 MiniMax 回转写**（错误率对比由 reviewer 做）；
- **GUI 模式**（本脚本走 **CLI 回放**，工程等价但**不等于**用户启动方式）。

## 用法

    <pkg>/python/python.exe results/app/app143_app042_soak.py --duration 300 --device NPU
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.8')
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUT_DIR = os.path.join(HOME, 'app042_soak')


def _lock():
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    return ml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--translate', default='zh')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = args.out or os.path.join(OUT_DIR, 'app042_soak_report.json')
    wav_path = os.path.join(OUT_DIR, 'app042_soak.wav')
    jsonl_path = wav_path + '.tts.jsonl'
    lag_csv = os.path.join(OUT_DIR, 'app042_lag_curve.csv')
    spd_csv = os.path.join(OUT_DIR, 'app042_speed_distribution.csv')
    log_path = os.path.join(OUT_DIR, 'app042_soak_cli.log')
    clip_dir = os.path.join(OUT_DIR, 'clips_1p2_to_1p3')

    if not os.path.exists(SPE):
        print('!! 找不到 SPE 切片：%s' % SPE)
        return 2

    ml = _lock()
    print('[lock] 申请共享机器锁 …')
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
        return 3
    print('[lock] 已取得：%r' % (payload,))
    try:
        print('[lock] 等安静窗口 …')
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                    timeout=900.0, verbose=True)
        print('[lock] 安静窗口 ok=%s info=%r' % (ok_quiet, qinfo))
        if not ok_quiet:
            print('[lock] !! 没有安静窗口 ⇒ 退出')
            return 4

        py = os.path.join(PKG_ROOT, 'python', 'python.exe')
        app_py = os.path.join(PKG_ROOT, 'app', 'live_caption_app.py')
        cmd = [
            py, app_py,
            '--cli',
            '--file', SPE,
            '--speed', str(args.speed),
            '--max-seconds', str(args.duration),
            '--tts', 'on',
            '--tts-device', args.device,
            '--translate', args.translate,
            '--tts-out', wav_path,
            '--out', os.path.join(OUT_DIR, 'app042_subtitles.txt'),
        ]
        print('[run] ' + ' '.join(cmd))
        t0 = time.time()
        proc = subprocess.Popen(cmd, cwd=PKG_ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        lines = []
        with open(log_path, 'wb') as lf:
            while True:
                raw = proc.stdout.readline()
                if not raw:
                    break
                lf.write(raw)
                lf.flush()
                txt = raw.decode('utf-8', 'replace').rstrip()
                if txt:
                    lines.append(txt)
                    print('  | ' + txt)
        rc = proc.wait()
        wall = time.time() - t0
        print('[run] 退出码=%s  墙钟=%.1f s' % (rc, wall))

        # ── 解析 CLI 收尾统计行 ────────────────────────────────
        stat_line = None
        for l in reversed(lines):
            if '[TTS]' in l and '提交' in l and '丢弃' in l:
                stat_line = l
                break

        def pick(key, default=None):
            if not stat_line:
                return default
            toks = stat_line.replace(']', ' ').split()
            for i, t in enumerate(toks):
                if t == key and i + 1 < len(toks):
                    v = toks[i + 1].rstrip('s')
                    try:
                        return float(v) if '.' in v else int(v)
                    except ValueError:
                        return default
            return default

        n_submitted = pick('提交')
        n_played = pick('播完')
        n_dropped = pick('丢弃')
        n_restart = pick('重启')
        max_backlog = pick('最大')
        first_packet = pick('首包')
        end_lag = pick('当前')

        # ── 解析逐句 jsonl ──────────────────────────────────────
        rows = []
        if os.path.exists(jsonl_path):
            with open(jsonl_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass

        def num(r, *keys):
            for k in keys:
                if k in r and r[k] is not None:
                    return r[k]
            return None

        # ── APP-042：滞后曲线 + 各倍率时间占比 ───────────────────
        lag_rows = []
        for r in rows:
            lag = num(r, 'play_lag_s')
            sp = num(r, 'speed')
            if lag is None and sp is None:
                continue
            lag_rows.append(dict(
                jid=r.get('id'),
                t_s=num(r, 't_start', 't_submit'),
                lag_s=lag,
                speed=sp,
                in_dur_s=num(r, 'in_dur_s'),
                out_dur_s=num(r, 'out_dur_s'),
                speed_gain=num(r, 'speed_gain'),
                end_reason=r.get('end_reason'),
            ))
        # 按开播时刻排序 ⇒ 曲线是「滞后随时间」
        lag_rows.sort(key=lambda d: (d['t_s'] is None, d['t_s']))
        lags = [d['lag_s'] for d in lag_rows if isinstance(d['lag_s'], (int, float))]
        speeds = [d['speed'] for d in lag_rows if isinstance(d['speed'], (int, float))]

        lag_start = lags[0] if lags else None
        lag_peak = max(lags) if lags else None
        lag_end = lags[-1] if lags else None
        lag_peak_idx = lags.index(lag_peak) if lags else None
        lag_at_peak_t = (lag_rows[lag_peak_idx]['t_s']
                         if lag_peak_idx is not None else None)

        # 各倍率的**音频秒数**占比（用 out_dur_s；缺失时退回 1.0×句长估算）
        spd_time = {}
        spd_n = {}
        for d in lag_rows:
            sp = d['speed']
            if not isinstance(sp, (int, float)):
                continue
            key = round(float(sp), 1)
            dur = d['out_dur_s']
            if not isinstance(dur, (int, float)):
                dur = 0.0
            spd_time[key] = spd_time.get(key, 0.0) + float(dur)
            spd_n[key] = spd_n.get(key, 0) + 1
        tot_dur = sum(spd_time.values()) or 1.0

        with open(lag_csv, 'w', encoding='utf-8', newline='\n') as f:
            f.write('t_s,lag_s,speed,in_dur_s,out_dur_s,speed_gain,end_reason\n')
            for d in lag_rows:
                f.write('%s,%s,%s,%s,%s,%s,%s\n' % (
                    d['t_s'], d['lag_s'], d['speed'], d['in_dur_s'],
                    d['out_dur_s'], d['speed_gain'], d['end_reason']))
        with open(spd_csv, 'w', encoding='utf-8', newline='\n') as f:
            f.write('speed,n_sent,out_dur_s,ratio\n')
            for k in sorted(spd_time):
                f.write('%s,%s,%s,%.4f\n' % (k, spd_n[k], round(spd_time[k], 3),
                                             spd_time[k] / tot_dur))

        # ── 挑 3 段 1.2–1.3× 的配音落盘（供用户抽听）──────────────
        os.makedirs(clip_dir, exist_ok=True)
        clips = []
        if os.path.exists(wav_path):
            # 用遥测里 out_dur_s 的累计位置对齐 wav 的采样点
            try:
                with wave.open(wav_path, 'rb') as wf:
                    sr = wf.getframerate()
                    nch = wf.getnchannels()
                    sw = wf.getsampwidth()
                    total = wf.getnframes()
                    wf.readframes(0)
                    pos = 0
                    for d in lag_rows:
                        sp = d['speed']
                        if not isinstance(sp, (int, float)):
                            continue
                        if not (1.2 - 1e-6 <= float(sp) <= 1.3 + 1e-6):
                            continue
                        dur = d['out_dur_s']
                        if not isinstance(dur, (int, float)) or dur <= 0:
                            continue
                        nframes = int(dur * sr)
                        start = pos
                        end = min(pos + nframes, total)
                        if end <= start:
                            continue
                        wf.setpos(start)
                        data = wf.readframes(end - start)
                        out_wav = os.path.join(
                            clip_dir, 'clip_jid%s_speed%s.wav'
                            % (d['jid'], sp))
                        with wave.open(out_wav, 'wb') as of:
                            of.setnchannels(nch)
                            of.setsampwidth(sw)
                            of.setframerate(sr)
                            of.writeframes(data)
                        clips.append(dict(jid=d['jid'], speed=sp,
                                          lag_s=d['lag_s'],
                                          out_dur_s=dur, path=out_wav,
                                          bytes=os.path.getsize(out_wav)))
                        pos = end
                        if len(clips) >= 3:
                            break
            except Exception as e:
                print('[clip] 切片段异常：%r' % (e,))

        # ── 判据 ────────────────────────────────────────────────
        n_dropped_jsonl = sum(1 for r in rows if r.get('dropped') is True)
        n_err = sum(1 for r in rows if r.get('error'))
        n_no_audio = sum(1 for r in rows if not (num(r, 'n_samples') or 0))
        n_cap = sum(1 for r in rows if str(r.get('end_reason')) == 'cap')
        n_runaway = sum(1 for r in rows if str(r.get('end_reason')) == 'runaway')
        n_restart_jsonl = sum(1 for r in rows if r.get('restart'))

        checks = [
            dict(id='B1', name='丢句数 = 0（CLI 统计行）',
                 ok=(n_dropped == 0), got=n_dropped, want=0),
            dict(id='B2', name='逐句 jsonl dropped = 0（独立来源交叉验证）',
                 ok=(n_dropped_jsonl == 0), got=n_dropped_jsonl, want=0),
            dict(id='B3', name='逐句 jsonl error = 0',
                 ok=(n_err == 0), got=n_err, want=0),
            dict(id='B4', name='不变式 n_played + n_dropped == n_submitted',
                 ok=(None not in (n_played, n_dropped, n_submitted)
                     and n_played + n_dropped == n_submitted),
                 got=(None if n_played is None else n_played + (n_dropped or 0)),
                 want=n_submitted),
            dict(id='B5', name='「没有产出音频」= 0',
                 ok=(n_no_audio == 0), got=n_no_audio, want=0),
            dict(id='B6', name='worker 重启 = 0',
                 ok=(n_restart == 0 and n_restart_jsonl == 0),
                 got=(n_restart, n_restart_jsonl), want=(0, 0)),
            dict(id='B7', name='cap / runaway = 0',
                 ok=(n_cap == 0 and n_runaway == 0),
                 got=(n_cap, n_runaway), want=(0, 0)),
            dict(id='B8', name='APP-042 遥测有 speed 字段（加速链路真的生效）',
                 ok=(len(speeds) > 0), got=len(speeds), want='>0'),
            dict(id='B9', name='APP-042 遥测有 play_lag_s（滞后口径可算）',
                 ok=(len(lags) > 0), got=len(lags), want='>0'),
            dict(id='B10', name='至少 1 句被加速（speed > 1.0）',
                 ok=(any(s > 1.0 + 1e-9 for s in speeds)),
                 got=max(speeds) if speeds else None, want='>1.0'),
            dict(id='B11', name='倍率不超上限 1.30',
                 ok=(all(s <= 1.30 + 1e-6 for s in speeds)),
                 got=max(speeds) if speeds else None, want='<=1.30'),
            dict(id='B12', name='倍率不低于下限 1.0',
                 ok=(all(s >= 1.0 - 1e-6 for s in speeds)),
                 got=min(speeds) if speeds else None, want='>=1.0'),
            dict(id='B13', name='已落盘 3 段 1.2–1.3× 配音（供用户抽听）',
                 ok=(len(clips) >= 3), got=len(clips), want=3),
        ]
        n_pass = sum(1 for c in checks if c['ok'])

        report = dict(
            ts=time.strftime('%Y-%m-%d %H:%M:%S'),
            device=args.device, duration=args.duration, speed=args.speed,
            translate=args.translate, wall_s=round(wall, 1), rc=rc,
            cli_stat_line=stat_line,
            n_submitted=n_submitted, n_played=n_played, n_dropped=n_dropped,
            n_restart=n_restart,
            n_dropped_jsonl=n_dropped_jsonl, n_err_jsonl=n_err,
            first_packet_s=first_packet, max_backlog_s=max_backlog,
            end_lag_s=end_lag,
            n_jsonl_rows=len(rows),
            app042=dict(
                n_telemetry=len(lag_rows),
                lag_start_s=lag_start, lag_peak_s=lag_peak, lag_end_s=lag_end,
                lag_peak_at_t_s=lag_at_peak_t,
                lag_min_s=min(lags) if lags else None,
                lag_median_s=(sorted(lags)[len(lags) // 2] if lags else None),
                speed_min=min(speeds) if speeds else None,
                speed_max=max(speeds) if speeds else None,
                speed_time_s={k: round(v, 3) for k, v in sorted(spd_time.items())},
                speed_ratio={k: round(v / tot_dur, 4)
                             for k, v in sorted(spd_time.items())},
                speed_n_sent={k: spd_n[k] for k in sorted(spd_n)},
            ),
            clips=clips,
            checks=checks, pass_count=n_pass,
            fail_count=len(checks) - n_pass,
            artifacts=dict(wav=wav_path, jsonl=jsonl_path, lag_csv=lag_csv,
                           speed_csv=spd_csv, cli_log=log_path,
                           clip_dir=clip_dir),
            note='工程侧等价实测（CLI 回放 + NPU）；非 GUI / 非 CUDA / 非用户实听 / 非 MiniMax 回转写',
        )
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print('\n' + '=' * 68)
        print(json.dumps({k: v for k, v in report.items()
                          if k not in ('checks',)}, ensure_ascii=False, indent=2))
        for c in checks:
            print('  [%s] %-4s %-46s got=%r want=%r'
                  % ('PASS' if c['ok'] else 'FAIL', c['id'], c['name'],
                     c['got'], c['want']))
        print('SUMMARY: PASS=%d FAIL=%d TOTAL=%d'
              % (n_pass, len(checks) - n_pass, len(checks)))
        print('报告已写入：%s' % out_json)
        print('=' * 68)
        return 0 if n_pass == len(checks) else 1
    finally:
        try:
            ml.release(payload)
            print('[lock] 已释放')
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
