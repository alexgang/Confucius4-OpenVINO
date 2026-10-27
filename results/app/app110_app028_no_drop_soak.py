# -*- coding: utf-8 -*-
"""app110 — APP-028② 的**不丢句实测**（工程侧等价实测，SPE 前 5 分钟切片）。

🔴🔴🔴 **必须持机器锁**（推理作业）⇒ 本脚本**自己取锁**（`machine_lock_app`）。
🔴 **不在 CPU 上跑推理** —— 设备固定 **NPU**（本机无 CUDA 运行时，见 §78.6）。
🔴 **不自己调用 MiniMax**（reviewer 侧 `quota.py` 不存在 ⇒ 不绕过）。

## reviewer APP-028 明文验收

> **验收**（用户启动方式，SPE 前 5 分钟 `--speed 1`，持锁，默认摆放）：报告逐句排队等待、
> 合成首包、RTF、句内欠载次数，队列峰值，**丢句数必须为 0**，以及结尾时的滞后。
> 之后再用 CUDA 跑一次作对照。最后由用户实听。

## 本脚本做哪一段、哪一段不做

✅ **做（工程侧）**：
- SPE 前 5 分钟固定切片（`shared/SPE_0000_0500.wav`）按 `--speed 1` **实时回放**；
- 设备 = **NPU**（默认摆放的 TTS 位）；持机器锁 + 等安静窗口；
- 采集**逐句**遥测（`x.tts.jsonl`：`queued_s`/`synth_rtf`/`prebuffer_s`/
  `underflow_in_sentence`/`queue_peak_s`/`queue_peak_mb`/`lang`/`end_reason` …）；
- 判 **丢句数 = 0**、`n_played + n_dropped == n_submitted`（不变式）、
  **「没有产出音频」= 0**、**看门狗触发 = 0**、**5 分钟内无 >30 s 的合成空窗**；
- 落盘**积压随时间曲线 csv**（每 5 s 一点）。

⛔ **不做（不能替代）**：
- **CUDA 对照组**（本机无 CUDA 运行时）；
- **V4 用户实听**（用户本人确认前不得写「能出声」）；
- **GUI 模式**（本脚本走 **CLI 回放**，工程等价但**不等于**用户启动方式）。

## 用法

    <pkg>/python/python.exe results/app/app110_app028_no_drop_soak.py \
        --duration 300 --device NPU
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUT_DIR = os.path.join(HOME, 'app028_soak')


def _lock():
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    return ml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=300.0,
                    help='回放秒数（APP-028 = 前 5 分钟）')
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--translate', default='zh',
                    help='翻译目标代号（zh/en/ja/ko）—— APP-028 默认摆放下的目标语言')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = args.out or os.path.join(OUT_DIR, 'app028_soak_report.json')
    wav_path = os.path.join(OUT_DIR, 'app028_soak.wav')
    jsonl_path = wav_path + '.tts.jsonl'
    csv_path = os.path.join(OUT_DIR, 'app028_backlog_curve.csv')
    log_path = os.path.join(OUT_DIR, 'app028_soak_cli.log')

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
            '--out', os.path.join(OUT_DIR, 'app028_subtitles.txt'),
        ]
        print('[run] ' + ' '.join(cmd))
        t0 = time.time()
        proc = subprocess.Popen(cmd, cwd=PKG_ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        # 🔴 逐行收 stdout，同时把曲线每 5 s 记一点
        curve = []
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
                    if '[TTS]' in txt and ('积压' in txt or '滞后' in txt):
                        curve.append((round(time.time() - t0, 1), txt))
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
            """从 CLI 收尾统计行里取「键 值」。

            ⚠️ CLI 输出形如：
              `[TTS] 首包 0.42s  积压 当前 0.00s / 最大 22.80s  提交 17  播完 17  丢弃 0  重启 0  state=ready`
            ⇒ 键和值是**相邻的两个空白分隔 token**
            ⇒ 🔴 **不能**用 `part[len(key):]`（中文键的 len 与 token 不等）
            ⇒ 必须**取下一个 token**。
            """
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
        # 🔴 reviewer APP-028 明文要「结尾时的滞后」⇒ 收尾统计行里的
        #   「积压 当前 X」= **收尾那一刻的积压**（= 尾部滞后）。
        end_lag = pick('当前')

        # ── 逐句「排队等待 / 合成首包」（reviewer 明文要求项）────────
        # CLI 输出形如：
        #   `[TTS] 首包分段 id=0：排队 6.100 s + 合成 0.834 s`
        seg_queue, seg_synth = [], []
        for l in lines:
            if '首包分段' in l and '排队' in l:
                m_q = re.search(r'排队\s+([0-9.]+)\s*s', l)
                m_s = re.search(r'合成\s+([0-9.]+)\s*s', l)
                if m_q:
                    seg_queue.append(float(m_q.group(1)))
                if m_s:
                    seg_synth.append(float(m_s.group(1)))
        seg_queue_sorted = sorted(seg_queue)
        seg_synth_sorted = sorted(seg_synth)

        def _pct(v, p):
            if not v:
                return None
            i = int(len(v) * p)
            if i >= len(v):
                i = len(v) - 1
            return v[i]

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

        # ── 曲线 csv（每 5 s 一点）──────────────────────────────
        with open(csv_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('t_s,stat_line\n')
            for t, s in curve:
                f.write('%s,"%s"\n' % (t, s.replace('"', "'")))

        # ── 判据 ────────────────────────────────────────────────
        def num(r, *keys):
            for k in keys:
                if k in r and r[k] is not None:
                    return r[k]
            return None

        n_no_audio = sum(1 for r in rows if not (num(r, 'n_samples') or 0))
        # 🔴 逐句级丢句标记（jsonl `dropped` 字段）⇒ 与 CLI 统计行**互相独立**
        #   ⇒ 两个来源都为 0 才算「丢句数 = 0」（防单侧统计漏记）。
        n_dropped_jsonl = sum(1 for r in rows if r.get('dropped') is True)
        n_err = sum(1 for r in rows if r.get('error'))
        n_cap = sum(1 for r in rows if str(r.get('end_reason')) == 'cap')
        n_runaway = sum(1 for r in rows if str(r.get('end_reason')) == 'runaway')
        uf = [num(r, 'underflow_in_sentence') or 0 for r in rows]
        uf_sorted = sorted(uf)
        uf_p95 = uf_sorted[int(len(uf_sorted) * 0.95)] if uf_sorted else 0
        rtfs = [num(r, 'synth_rtf') for r in rows]
        rtfs = [x for x in rtfs if isinstance(x, (int, float))]
        rtfs_sorted = sorted(rtfs)
        rtf_p50 = rtfs_sorted[len(rtfs_sorted) // 2] if rtfs_sorted else None
        rtf_p95 = rtfs_sorted[int(len(rtfs_sorted) * 0.95)] if rtfs_sorted else None
        qpk_s = max([num(r, 'queue_peak_s') or 0 for r in rows] or [0])
        qpk_mb = max([num(r, 'queue_peak_mb') or 0 for r in rows] or [0])
        # 合成空窗：相邻两句的 t_last_chunk 间隔 > 30 s
        gaps = []
        ts = sorted([num(r, 't_last_chunk') for r in rows
                     if isinstance(num(r, 't_last_chunk'), (int, float))])
        for a, b in zip(ts, ts[1:]):
            gaps.append(b - a)
        max_gap = max(gaps) if gaps else None

        checks = [
            dict(id='A1', name='丢句数 = 0', ok=(n_dropped == 0),
                 got=n_dropped, want=0),
            dict(id='A1b', name='逐句 jsonl dropped 标记 = 0（独立来源交叉验证）',
                 ok=(n_dropped_jsonl == 0), got=n_dropped_jsonl, want=0),
            dict(id='A1c', name='逐句 jsonl error 非空 = 0',
                 ok=(n_err == 0), got=n_err, want=0),
            dict(id='A2', name='不变式 n_played + n_dropped == n_submitted',
                 ok=(None not in (n_played, n_dropped, n_submitted)
                     and n_played + n_dropped == n_submitted),
                 got=(None if n_played is None else n_played + (n_dropped or 0)),
                 want=n_submitted),
            dict(id='A3', name='「没有产出音频」次数 = 0',
                 ok=(n_no_audio == 0), got=n_no_audio, want=0),
            dict(id='A4', name='worker 重启次数 = 0',
                 ok=(n_restart == 0), got=n_restart, want=0),
            dict(id='A5', name='撞帧上限(cap) = 0', ok=(n_cap == 0),
                 got=n_cap, want=0),
            dict(id='A6', name='失控(runaway) = 0', ok=(n_runaway == 0),
                 got=n_runaway, want=0),
            dict(id='A7', name='句内欠载 P95 = 0', ok=(uf_p95 == 0),
                 got=uf_p95, want=0),
            dict(id='A8', name='无 >30 s 合成空窗',
                 ok=(max_gap is None or max_gap <= 30.0),
                 got=max_gap, want='<=30'),
        ]
        n_pass = sum(1 for c in checks if c['ok'])

        report = dict(
            ts=time.strftime('%Y-%m-%d %H:%M:%S'),
            device=args.device, duration=args.duration, speed=args.speed,
            translate=args.translate, wall_s=round(wall, 1), rc=rc,
            cli_stat_line=stat_line,
            n_submitted=n_submitted, n_played=n_played,
            n_dropped=n_dropped, n_restart=n_restart,
            n_dropped_jsonl=n_dropped_jsonl, n_err_jsonl=n_err,
            first_packet_s=first_packet, max_backlog_s=max_backlog,
            end_lag_s=end_lag,
            seg_queue_p50=_pct(seg_queue_sorted, 0.50),
            seg_queue_p95=_pct(seg_queue_sorted, 0.95),
            seg_queue_max=(seg_queue_sorted[-1] if seg_queue_sorted else None),
            seg_synth_p50=_pct(seg_synth_sorted, 0.50),
            seg_synth_p95=_pct(seg_synth_sorted, 0.95),
            seg_synth_max=(seg_synth_sorted[-1] if seg_synth_sorted else None),
            n_seg_queue=len(seg_queue), n_seg_synth=len(seg_synth),
            n_jsonl_rows=len(rows),
            synth_rtf_p50=rtf_p50, synth_rtf_p95=rtf_p95,
            underflow_in_sentence_p95=uf_p95,
            queue_peak_s=qpk_s, queue_peak_mb=qpk_mb,
            max_synth_gap_s=max_gap,
            checks=checks, pass_count=n_pass,
            fail_count=len(checks) - n_pass,
            artifacts=dict(wav=wav_path, jsonl=jsonl_path, csv=csv_path,
                           cli_log=log_path),
            note='工程侧等价实测（CLI 回放 + NPU）；非 GUI/非 CUDA/非用户实听',
        )
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print('\n' + '=' * 68)
        print(json.dumps({k: v for k, v in report.items()
                          if k not in ('checks',)}, ensure_ascii=False, indent=2))
        for c in checks:
            print('  [%s] %-4s %-42s got=%r want=%r'
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
