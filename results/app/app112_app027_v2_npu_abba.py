# -*- coding: utf-8 -*-
"""app112 — APP-027 的 **V2（NPU 连续实时）** 实测 ＋ **「争用定量」ABBA**。

🔴🔴🔴 **必须持机器锁**（推理作业）⇒ 本脚本**自己取锁**（`machine_lock_app`，fail-closed）。
🔴 **不在 CPU 上跑推理** —— 设备固定 **NPU**（本机无 CUDA 运行时，见 §78.6）。
🔴 **不自己调用 MiniMax**（reviewer 侧 `quota.py` 不存在 ⇒ 不绕过）。

## reviewer APP-027 V2 明文验收

> **V2 NPU 连续实时**：同一素材和条件，并附上上面"争用定量"的四种配置 ABBA。报同样的字段。
> 验收：句内 `underflow_in_sentence` P95 = 0（只允许句前等待），丢句率与 RTF 一起报告。
> **RTF > 1 导致的丢句只记录、不判失败，但必须如实写出来。**

「同样的字段」= V1 的字段集：
`queued_s`、`synth_first_s`、`synth_rtf`、`prebuffer_s`、`underflow_in_sentence`（次数/毫秒）、
丢句数（**分成"未合成就丢"和"已写入被丢"两类，后者必须为 0**）、
**"没有产出音频"的次数（必须为 0）**、**看门狗触发次数（必须为 0，或有原因说明）**、
**积压随时间的曲线（每 5 s 一点，用 csv）**、
5 分钟全程**不能出现超过 30 s 没有合成的空窗**。

## 「争用定量」ABBA 四种配置（reviewer 明文）

1. TTS 单独（ASR/MT 不跑）⇒ 只跑 TTS，量**引擎基线 RTF**
2. TTS + ASR(GPU.0)
3. TTS + ASR(GPU.0) + MT(NPU)
4. TTS + ASR(GPU.0) + MT(GPU.0)

⇒ 每种报 `synth_rtf` P50/P95 ⇒ 若 MT 在 NPU 时明显更差，**记录**（App 侧不自己改模型）。

## ⛔ 本脚本**不做**的事

- **V1（CUDA 连续实时）** —— 本机无 CUDA 运行时 ⇒ **需 reviewer 裁定执行环境**；
- **V3（克隆验收的 MiniMax 回转写 / CAMPPlus 相似度）** —— reviewer 侧做，本脚本只**落盘 wav**；
- **V4（用户实听）** —— 用户本人确认前不得写"能出声"。

## 用法

    <pkg>/python/python.exe results/app/app112_app027_v2_npu_abba.py \
        --duration 300 --configs abba
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUT_DIR = os.path.join(HOME, 'app027_v2')

# 🔴「争用定量」四种配置（reviewer 明文）
CONFIGS = {
    'tts_only': dict(asr=None, mt=None),
    'tts_asr': dict(asr='GPU.0', mt=None),
    'tts_asr_mt_npu': dict(asr='GPU.0', mt='NPU'),
    'tts_asr_mt_gpu0': dict(asr='GPU.0', mt='GPU.0'),
}


def _lock():
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    return ml


def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    i = int(len(sorted_vals) * p)
    if i >= len(sorted_vals):
        i = len(sorted_vals) - 1
    return sorted_vals[i]


def run_one(cfg_name, cfg, duration, translate, ml, quiet_ok):
    """跑一种配置 ⇒ 返回该配置的逐句统计与判据。"""
    tag = os.path.join(OUT_DIR, cfg_name)
    os.makedirs(tag, exist_ok=True)
    wav_path = os.path.join(tag, 'v2_%s.wav' % cfg_name)
    jsonl_path = wav_path + '.tts.jsonl'
    log_path = os.path.join(tag, 'v2_%s_cli.log' % cfg_name)
    dump_dir = os.path.join(tag, 'dump')
    os.makedirs(dump_dir, exist_ok=True)
    csv_path = os.path.join(tag, 'v2_%s_backlog_curve.csv' % cfg_name)
    rep_path = os.path.join(tag, 'v2_%s_report.json' % cfg_name)

    py = os.path.join(PKG_ROOT, 'python', 'python.exe')
    app_py = os.path.join(PKG_ROOT, 'app', 'live_caption_app.py')
    cmd = [py, app_py, '--cli', '--file', SPE,
           '--speed', '1.0', '--max-seconds', str(duration),
           '--tts', 'on', '--tts-device', 'NPU',
           '--tts-out', wav_path, '--tts-dump-dir', dump_dir,
           '--out', os.path.join(tag, 'subtitles.txt')]
    if cfg['asr']:
        cmd += ['--asr-device', cfg['asr']]
    if cfg['mt']:
        cmd += ['--mt-device', cfg['mt']]
    else:
        # MT 关掉 ⇒ 不翻译（保持与"TTS 单独"一致）
        cmd += ['--translate', 'off']
    if cfg['mt']:
        cmd += ['--translate', translate]

    print('\n' + '=' * 70)
    print('[cfg] %s  cmd=%s' % (cfg_name, ' '.join(cmd)))
    print('=' * 70)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=PKG_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
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
                if '[TTS]' in txt and ('积压' in txt or '滞后' in txt):
                    curve.append((round(time.time() - t0, 1), txt))
                    print('  | ' + txt)
    rc = proc.wait()
    wall = time.time() - t0
    print('[cfg] %s 退出码=%s 墙钟=%.1f s' % (cfg_name, rc, wall))

    # ── CLI 收尾统计行 ────────────────────────────────────────
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

    # ── 逐句「排队等待 / 合成首包」 ───────────────────────────
    seg_queue, seg_synth = [], []
    for l in lines:
        if '首包分段' in l and '排队' in l:
            mq = re.search(r'排队\s+([0-9.]+)\s*s', l)
            ms = re.search(r'合成\s+([0-9.]+)\s*s', l)
            if mq:
                seg_queue.append(float(mq.group(1)))
            if ms:
                seg_synth.append(float(ms.group(1)))
    seg_queue.sort()
    seg_synth.sort()

    # ── 逐句 jsonl ───────────────────────────────────────────
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

    # 🔴 丢句分类（reviewer 明文：**"未合成就丢"** vs **"已写入被丢"**，后者必须为 0）
    #   判据：jsonl 行 `dropped=True` 且 **没有 n_samples** ⇒ 未合成就丢；
    #         `dropped=True` 且 **有 n_samples**（已写进缓冲）⇒ 已写入被丢。
    n_drop_unbuilt = 0   # 未合成就丢
    n_drop_written = 0   # 已写入被丢（必须为 0）
    for r in rows:
        if r.get('dropped') is True:
            if num(r, 'n_samples'):
                n_drop_written += 1
            else:
                n_drop_unbuilt += 1

    n_no_audio = sum(1 for r in rows if not (num(r, 'n_samples') or 0)
                     and r.get('dropped') is not True)
    n_err = sum(1 for r in rows if r.get('error'))
    n_cap = sum(1 for r in rows if str(r.get('end_reason')) == 'cap')
    n_runaway = sum(1 for r in rows if str(r.get('end_reason')) == 'runaway')
    # 🔴 看门狗触发次数：worker 侧的 15/60 s 看门狗
    n_watchdog = sum(1 for l in lines if '看门狗' in l and ('触发' in l or '超时' in l))
    n_watchdog_restart = sum(1 for l in lines if '看门狗' in l and '重启' in l)

    uf = [num(r, 'underflow_in_sentence') or 0 for r in rows]
    uf.sort()
    uf_ms = [num(r, 'underflow_in_sentence_ms') or 0 for r in rows]
    uf_ms.sort()
    rtfs = [num(r, 'synth_rtf') for r in rows]
    rtfs = [x for x in rtfs if isinstance(x, (int, float))]
    rtfs.sort()
    pb = [num(r, 'prebuffer_s') for r in rows]
    pb = [x for x in pb if isinstance(x, (int, float))]
    pb.sort()
    qpk_s = max([num(r, 'queue_peak_s') or 0 for r in rows] or [0])
    qpk_mb = max([num(r, 'queue_peak_mb') or 0 for r in rows] or [0])

    # 🔴 合成空窗（相邻两句合成完成时刻间隔）
    ts = sorted([num(r, 't_last_chunk') for r in rows
                 if isinstance(num(r, 't_last_chunk'), (int, float))])
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    max_gap = max(gaps) if gaps else None

    # ── 积压曲线 csv（每 5 s 一点）───────────────────────────
    with open(csv_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('t_s,stat_line\n')
        for t, s in curve:
            f.write('%s,"%s"\n' % (t, s.replace('"', "'")))

    # ── 判据（V2 明文）────────────────────────────────────────
    checks = [
        dict(id='V2-1', name='句内 underflow_in_sentence P95 = 0（只允许句前等待）',
             ok=(_pct(uf, 0.95) == 0), got=_pct(uf, 0.95), want=0),
        dict(id='V2-2', name='「已写入被丢」= 0',
             ok=(n_drop_written == 0), got=n_drop_written, want=0),
        dict(id='V2-3', name='「没有产出音频」= 0',
             ok=(n_no_audio == 0), got=n_no_audio, want=0),
        dict(id='V2-4', name='看门狗触发次数 = 0',
             ok=(n_watchdog == 0), got=n_watchdog, want=0),
        dict(id='V2-5', name='无 >30 s 合成空窗',
             ok=(max_gap is None or max_gap <= 30.0), got=max_gap, want='<=30'),
        dict(id='V2-6', name='不变式 n_played + n_dropped == n_submitted',
             ok=(None not in (n_played, n_dropped, n_submitted)
                 and n_played + n_dropped == n_submitted),
             got=(None if n_played is None else n_played + (n_dropped or 0)),
             want=n_submitted),
        dict(id='V2-7', name='worker 重启次数 = 0',
             ok=(n_restart == 0), got=n_restart, want=0),
        dict(id='V2-8', name='撞帧上限 cap = 0',
             ok=(n_cap == 0), got=n_cap, want=0),
        dict(id='V2-9', name='失控 runaway = 0',
             ok=(n_runaway == 0), got=n_runaway, want=0),
        dict(id='V2-10', name='逐句 error 非空 = 0',
             ok=(n_err == 0), got=n_err, want=0),
        # ⚠️ reviewer 明文：「RTF > 1 导致的丢句**只记录、不判失败**，但必须如实写出来」
        dict(id='V2-11', name='（只记录）synth_rtf P95 —— 不判失败',
             ok=True, got=_pct(rtfs, 0.95), want='只记录'),
    ]
    n_pass = sum(1 for c in checks if c['ok'])

    report = dict(
        ts=time.strftime('%Y-%m-%d %H:%M:%S'),
        cfg=cfg_name, asr_device=cfg['asr'], mt_device=cfg['mt'],
        tts_device='NPU', duration=duration, translate=translate,
        wall_s=round(wall, 1), rc=rc,
        cli_stat_line=stat_line,
        n_submitted=n_submitted, n_played=n_played, n_dropped=n_dropped,
        n_restart=n_restart,
        n_drop_unbuilt=n_drop_unbuilt, n_drop_written=n_drop_written,
        n_no_audio=n_no_audio, n_err_jsonl=n_err,
        n_watchdog=n_watchdog, n_watchdog_restart=n_watchdog_restart,
        first_packet_s=first_packet, max_backlog_s=max_backlog,
        end_lag_s=end_lag,
        queued_s_p50=_pct(seg_queue, 0.50), queued_s_p95=_pct(seg_queue, 0.95),
        queued_s_max=(seg_queue[-1] if seg_queue else None),
        synth_first_s_p50=_pct(seg_synth, 0.50), synth_first_s_p95=_pct(seg_synth, 0.95),
        synth_first_s_max=(seg_synth[-1] if seg_synth else None),
        prebuffer_s_p50=_pct(pb, 0.50), prebuffer_s_p95=_pct(pb, 0.95),
        synth_rtf_p50=_pct(rtfs, 0.50), synth_rtf_p95=_pct(rtfs, 0.95),
        underflow_in_sentence_p95=_pct(uf, 0.95),
        underflow_in_sentence_ms_p95=_pct(uf_ms, 0.95),
        queue_peak_s=qpk_s, queue_peak_mb=qpk_mb,
        max_synth_gap_s=max_gap,
        n_jsonl_rows=len(rows),
        n_dump_wav=len([f for f in os.listdir(dump_dir) if f.endswith('.wav')])
        if os.path.isdir(dump_dir) else 0,
        checks=checks, pass_count=n_pass, fail_count=len(checks) - n_pass,
        artifacts=dict(wav=wav_path, jsonl=jsonl_path, csv=csv_path,
                       cli_log=log_path, dump_dir=dump_dir),
        note='工程侧等价实测（CLI 回放 + NPU）；非 GUI/非 CUDA/非用户实听',
    )
    with open(rep_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    for c in checks:
        print('  [%s] %-7s %-52s got=%r want=%r'
              % ('PASS' if c['ok'] else 'FAIL', c['id'], c['name'],
                 c['got'], c['want']))
    print('  SUMMARY[%s]: PASS=%d FAIL=%d' % (cfg_name, n_pass,
                                              len(checks) - n_pass))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--translate', default='zh')
    ap.add_argument('--configs', default='abba',
                    help='逗号分隔的配置名；abba = 四种「争用定量」配置各跑一次')
    ap.add_argument('--order', default=None,
                    help='显式配置顺序（逗号分隔）；默认按 ABBA 顺序')
    args = ap.parse_args()

    if not os.path.exists(SPE):
        print('!! 找不到 SPE 切片：%s' % SPE)
        return 2
    os.makedirs(OUT_DIR, exist_ok=True)

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

        if args.order:
            names = [x.strip() for x in args.order.split(',') if x.strip()]
        elif args.configs == 'abba':
            names = list(CONFIGS.keys())
        else:
            names = [x.strip() for x in args.configs.split(',') if x.strip()]

        reports = []
        for n in names:
            if n not in CONFIGS:
                print('!! 未知配置：%s' % n)
                return 5
            reports.append(run_one(n, CONFIGS[n], args.duration,
                                   args.translate, ml, ok_quiet))

        # ── 汇总（争用定量对照表）─────────────────────────────
        summary = dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'),
                       device='NPU', duration=args.duration,
                       translate=args.translate,
                       abba=[dict(cfg=r['cfg'],
                                  asr_device=r['asr_device'],
                                  mt_device=r['mt_device'],
                                  synth_rtf_p50=r['synth_rtf_p50'],
                                  synth_rtf_p95=r['synth_rtf_p95'],
                                  queued_s_p95=r['queued_s_p95'],
                                  prebuffer_s_p95=r['prebuffer_s_p95'],
                                  underflow_in_sentence_p95=r['underflow_in_sentence_p95'],
                                  n_drop_unbuilt=r['n_drop_unbuilt'],
                                  n_drop_written=r['n_drop_written'],
                                  n_no_audio=r['n_no_audio'],
                                  n_watchdog=r['n_watchdog'],
                                  max_synth_gap_s=r['max_synth_gap_s'],
                                  n_submitted=r['n_submitted'],
                                  n_played=r['n_played'],
                                  n_dropped=r['n_dropped'],
                                  pass_count=r['pass_count'],
                                  fail_count=r['fail_count'])
                               for r in reports],
                       note='APP-027 V2 NPU 连续实时 + 争用定量 ABBA（工程侧 CLI 回放）')
        sum_path = os.path.join(OUT_DIR, 'app027_v2_abba_summary.json')
        with open(sum_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print('\n' + '=' * 70)
        print('[ABBA] 争用定量对照：')
        print('  %-18s %-10s %-10s %-10s %-10s'
              % ('cfg', 'rtf_p50', 'rtf_p95', 'uf_p95', 'dropped'))
        for r in summary['abba']:
            print('  %-18s %-10s %-10s %-10s %-10s'
                  % (r['cfg'], r['synth_rtf_p50'], r['synth_rtf_p95'],
                     r['underflow_in_sentence_p95'], r['n_dropped']))
        print('  汇总已写入：%s' % sum_path)
        print('=' * 70)
        return 0
    finally:
        try:
            ml.release(payload)
            print('[lock] 已释放')
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
