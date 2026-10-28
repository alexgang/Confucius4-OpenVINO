# -*- coding: utf-8 -*-
"""app119 — APP-027 的 **V1（CUDA 连续实时）** 实测（真实播放路径 · CLI 回放）。

## 为什么需要本脚本（§81.11 第 4 条的缺口）

APP-027 明文要求四个验收段：

| 段 | 内容 | 状态（§81 时） |
|---|---|---|
| V1 | **CUDA 连续实时**（SPE 前 5 分钟 / `--speed 1` / 持锁 / 用户启动方式） | ⛔ **未跑** |
| V2 | NPU 连续实时 + 争用定量 ABBA | ✅ §81 已跑 |
| V3 | 克隆（MiniMax 回转写 + CAMPPlus） | ⛔ 未跑（reviewer 侧做） |
| V4 | 用户实听 | ⛔ 等用户 |

⇒ 本脚本补 **V1**：**CUDA 后端**的连续实时实测。

## 🔴🔴🔴 本脚本继承 app114 的三条硬约束（不能重犯的错）

1. **不传 `--tts-out`** ⇒ 走**真实播放路径** ⇒ `underflow_in_sentence` /
   `queue_peak_s` 才不是结构性恒 0（app112 的缺陷①）。
2. **不传 `--translate off` 来造「无 MT」臂**（app112 的缺陷②）⇒
   `--tts-source asr` 才是正规做法。
3. 🔴 **不整目录删除**（§81.5 缺陷①：`shutil.rmtree` ⇒ 52 个文件 ⇒
   触发宿主**批量删除保护** ⇒ **进程被杀** ⇒ 整轮白跑）
   ⇒ 本脚本用**带时间戳的 `run_<YYYYmmdd_HHMMSS>/` 子目录**，**0 次删除**。

## 🔴🔴 V1 的验收判据（reviewer APP-027 V1 明文）

> **V1 CUDA 连续实时**：260902_SPE **前 5 分钟固定切片（00:00–05:00）**，
> `--speed 1`，GUI 实时模式，持机器锁（**同时没有其他模块的计时作业**）。
> 逐句报 `queued_s`、`synth_first_s`、`synth_rtf`、`prebuffer_s`、
> `underflow_in_sentence`（次数/毫秒），以及丢句数（分成"未合成就丢"和
> "已写入被丢"两类，**后者必须为 0**），还有"没有产出音频"的次数
> （**必须为 0**）、看门狗触发次数（必须为 0，或者有原因说明）、
> 积压随时间的曲线（每 5 s 一点，用 csv）。
> 5 分钟全程**不能出现超过 30 s 没有合成的空窗**。
> 另外开 `--tts-dump-dir` 落盘逐句 wav，抽 10 句交给 reviewer 回转写，
> **核对 wav 与译文按 id 一一对应（防止错位）**。

## 边界（诚实声明）

- ⚠️ **本脚本是 CLI 回放 + 真实播放路径（走声卡），不是 GUI** ⇒
  **不等于用户启动方式**（§63 L4：桌面快捷方式 → pythonw.exe）
  ⇒ **不得据此写「用户听得到」**。
- ⚠️ **V3（MiniMax + CAMPPlus）与 V4（用户实听）不在本脚本范围内**
  （APP-027 明文：V3 归 reviewer；V4 归用户）。
- ⚠️ **不在 CPU 上跑推理**：TTS 走 **CUDA 边车**（torch cu128 / RTX 5050），
  ASR 走 **GPU.0**。
- ⚠️ **不自己调用 MiniMax**（`quota.py` 在 reviewer 本机 ⇒ 见 APP-033 第 1 条）。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUT_DIR = os.path.join(HOME, 'app027_v1')

#: 🔴 **CUDA 边车的解释器**（APP-033 第 2 条明文：按 tts_cuda 实际使用的
#:   边车解释器做，**不要**以「主 python 无 CUDA torch」为由跳过）。
CUDA_PY = os.environ.get(
    'LIVECAP_CUDA_PY', r'C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe')


def _pct(vals, p):
    if not vals:
        return None
    i = int(len(vals) * p)
    if i >= len(vals):
        i = len(vals) - 1
    return vals[i]


def _num(r, *keys):
    for k in keys:
        if k in r and r[k] is not None:
            return r[k]
    return None


def _lock():
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    return ml


def _probe_cuda():
    """**只读**探测 CUDA 边车解释器（不加载模型）。

    ⇒ 用来把「CUDA 组客观做不了」这类错误结论彻底钉死（§78/§79 的教训）。
    """
    if not os.path.isfile(CUDA_PY):
        return dict(ok=False, py=CUDA_PY, error='解释器不存在')
    try:
        p = subprocess.run(
            [CUDA_PY, '-c',
             'import torch,sys;'
             'sys.stdout.write("%s|%s|%s|%s" % (torch.__version__,'
             ' torch.version.cuda, torch.cuda.is_available(),'
             ' torch.cuda.get_device_name(0) if torch.cuda.is_available()'
             ' else ""))'],
            capture_output=True, timeout=180)
        out = (p.stdout or b'').decode('utf-8', 'replace').strip()
        if p.returncode != 0:
            return dict(ok=False, py=CUDA_PY,
                        error=(p.stderr or b'').decode('utf-8', 'replace')[-300:])
        parts = (out.split('|') + ['', '', '', ''])[:4]
        return dict(ok=(parts[2] == 'True'), py=CUDA_PY,
                    torch=parts[0], cuda=parts[1],
                    cuda_available=parts[2], device=parts[3])
    except Exception as e:
        return dict(ok=False, py=CUDA_PY,
                    error='%s: %s' % (type(e).__name__, e))


def run_one(duration, translate, out_device, tag_suffix=''):
    """跑 **CUDA 后端**的连续实时 ⇒ 返回该次实测的逐句统计与判据。"""
    # 🔴🔴 **不要 `shutil.rmtree` 清目录**（§81.5 缺陷①：52 个文件 ⇒
    #   触发批量删除保护 ⇒ **进程被杀** ⇒ 整轮实测白跑）
    #   ⇒ 用**带时间戳的独立子目录** ⇒ 0 次删除 ⇒ 旧产物原样保留。
    _stamp = time.strftime('%Y%m%d_%H%M%S')
    os.makedirs(OUT_DIR, exist_ok=True)
    run_dir = os.path.join(OUT_DIR, 'cuda%s_run_%s' % (tag_suffix, _stamp))
    os.makedirs(run_dir, exist_ok=True)
    jsonl_path = os.path.join(run_dir, 'v1_cuda.tts.jsonl')
    log_path = os.path.join(run_dir, 'v1_cuda_cli.log')
    dump_dir = os.path.join(run_dir, 'dump')
    os.makedirs(dump_dir, exist_ok=True)
    csv_path = os.path.join(run_dir, 'v1_cuda_backlog_curve.csv')
    rep_path = os.path.join(run_dir, 'v1_cuda_report.json')

    py = os.path.join(PKG_ROOT, 'python', 'python.exe')
    app_py = os.path.join(PKG_ROOT, 'app', 'live_caption_app.py')
    cmd = [py, app_py, '--cli', '--file', SPE,
           '--speed', '1.0', '--max-seconds', str(duration),
           '--tts', 'on',
           # 🔴🔴🔴 **V1 = CUDA 后端**（APP-027 V1 明文）
           '--tts-device', 'CUDA',
           '--tts-dump-dir', dump_dir,
           '--tts-jsonl', jsonl_path,
           '--out', os.path.join(run_dir, 'subtitles.txt')]
    if out_device:
        cmd += ['--tts-out-device', out_device]
    # 🔴 CUDA 组：ASR 走 GPU.0（集显）；MT 走 GPU.0（APP-028① 默认摆放）
    cmd += ['--asr-device', 'GPU.0']
    cmd += ['--mt-device', 'GPU.0']
    cmd += ['--translate', translate]

    print('\n' + '=' * 70)
    print('[cfg] v1_cuda  cmd=%s' % ' '.join(cmd))
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
    rc = proc.wait()
    wall = time.time() - t0
    print('[cfg] v1_cuda 退出码=%s 墙钟=%.1f s' % (rc, wall))

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

    # ── 逐句 jsonl ─────────────────────────────────────────────
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

    # 🔴 丢句分类（reviewer 明文：**"未合成就丢"** vs **"已写入被丢"**）
    n_drop_unbuilt = 0
    n_drop_written = 0
    for r in rows:
        if r.get('dropped') is True:
            if _num(r, 'n_samples'):
                n_drop_written += 1
            else:
                n_drop_unbuilt += 1
    n_no_audio = sum(1 for r in rows if not (_num(r, 'n_samples') or 0)
                     and r.get('dropped') is not True)
    n_err = sum(1 for r in rows if r.get('error'))
    n_cap = sum(1 for r in rows if str(r.get('end_reason')) == 'cap')
    n_runaway = sum(1 for r in rows if str(r.get('end_reason')) == 'runaway')

    # 🔴🔴 **真实播放证据**
    n_consumed = sum(1 for r in rows if r.get('consumed') is True)
    n_not_consumed = sum(1 for r in rows if r.get('consumed') is False)
    n_read_ok = sum(1 for r in rows
                    if (_num(r, 'read_delta') or 0) >= (_num(r, 'n_samples') or 0)
                    and (_num(r, 'n_samples') or 0) > 0)
    cb_delta_max = max([_num(r, 'cb_delta') or 0 for r in rows] or [0])
    read_delta_max = max([_num(r, 'read_delta') or 0 for r in rows] or [0])

    n_watchdog = sum(1 for l in lines if '看门狗' in l and ('触发' in l or '超时' in l))
    n_watchdog_restart = sum(1 for l in lines if '看门狗' in l and '重启' in l)
    n_player_err = sum(1 for l in lines
                       if '播放设备打开失败' in l or '播放器不可用' in l
                       or '播放写入失败' in l or '播放缓冲写满' in l)

    uf = [_num(r, 'underflow_in_sentence') or 0 for r in rows]
    uf.sort()
    uf_ms = [_num(r, 'underflow_in_sentence_ms') or 0 for r in rows]
    uf_ms.sort()
    uf_pre = [_num(r, 'underflow_pre_sentence') or 0 for r in rows]
    uf_pre.sort()
    rtfs = [_num(r, 'synth_rtf') for r in rows]
    rtfs = [x for x in rtfs if isinstance(x, (int, float))]
    rtfs.sort()
    pb = [_num(r, 'prebuffer_s') for r in rows]
    pb = [x for x in pb if isinstance(x, (int, float))]
    pb.sort()
    qpk_s = max([_num(r, 'queue_peak_s') or 0 for r in rows] or [0])
    qpk_mb = max([_num(r, 'queue_peak_mb') or 0 for r in rows] or [0])
    qlag_max = max([_num(r, 'queue_lag_s') or 0 for r in rows] or [0])

    # 🔴 APP-027 V1 明文：**逐句报 `queued_s` / `synth_first_s`**
    #   `queued_s`     = t_dequeue − t_submit（排队等待）
    #   `synth_first_s` = t_first_chunk − t_dequeue（合成首包）
    queued = []
    synth_first = []
    for r in rows:
        td = _num(r, 't_dequeue')
        ts = _num(r, 't_submit')
        tf = _num(r, 't_first_chunk')
        if td is not None and ts is not None:
            queued.append(round(td - ts, 4))
        if tf is not None and td is not None:
            synth_first.append(round(tf - td, 4))
    queued.sort()
    synth_first.sort()

    # 合成空窗（相邻两句合成完成时刻间隔）
    ts_last = sorted([_num(r, 't_last_chunk') for r in rows
                      if isinstance(_num(r, 't_last_chunk'), (int, float))])
    gaps = [b - a for a, b in zip(ts_last, ts_last[1:])]
    max_gap = max(gaps) if gaps else None

    # ── 积压曲线 csv（每 5 s 一点）───────────────────────────
    with open(csv_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('t_s,stat_line\n')
        for t, s in curve:
            f.write('%s,"%s"\n' % (t, s.replace('"', "'")))

    # 🔴🔴 **wav 与译文按 id 一一对应**（reviewer V1 明文：防止错位）
    #   dump 的文件名是 `seg_<jid>_<seq>.wav` ⇒ 抽 10 句，
    #   把 jid ↔ 文本 ↔ wav 路径列成表 ⇒ reviewer 可直接核对。
    id_to_text = {}
    for r in rows:
        if r.get('id') is not None:
            id_to_text[int(r['id'])] = (r.get('text') or '')
    wav_by_jid = {}
    if os.path.isdir(dump_dir):
        for fn in sorted(os.listdir(dump_dir)):
            if not fn.endswith('.wav'):
                continue
            stem = fn[:-4]
            parts = stem.split('_')
            try:
                jid = int(parts[1])
            except Exception:
                continue
            wav_by_jid.setdefault(jid, []).append(
                os.path.join(dump_dir, fn))
    align_rows = []
    for jid in sorted(wav_by_jid):
        if len(align_rows) >= 10:
            break
        align_rows.append(dict(id=jid,
                               text=id_to_text.get(jid, ''),
                               wavs=wav_by_jid[jid]))
    align_path = os.path.join(run_dir, 'v1_cuda_wav_text_alignment.json')
    with open(align_path, 'w', encoding='utf-8') as f:
        json.dump(dict(run_dir=run_dir, rows=align_rows,
                       n_jid_with_wav=len(wav_by_jid),
                       n_jid_in_jsonl=len(id_to_text)),
                  f, ensure_ascii=False, indent=2)

    # ── 判据（reviewer APP-027 V1 明文）─────────────────────────
    checks = [
        dict(id='V1-0a', name='🔴 真实播放证据：至少 1 句 consumed=True',
             ok=(n_consumed > 0), got=n_consumed, want='>0'),
        dict(id='V1-0b', name='🔴 真实播放证据：read_delta ≥ n_samples 的句数 > 0',
             ok=(n_read_ok > 0), got=n_read_ok, want='>0'),
        dict(id='V1-0c', name='🔴 无播放器故障（设备打不开 / 写入失败 / 缓冲写满）',
             ok=(n_player_err == 0), got=n_player_err, want=0),
        dict(id='V1-1', name='"已写入被丢" = 0',
             ok=(n_drop_written == 0), got=n_drop_written, want=0),
        dict(id='V1-2', name='"没有产出音频" = 0',
             ok=(n_no_audio == 0), got=n_no_audio, want=0),
        dict(id='V1-3', name='看门狗触发次数 = 0',
             ok=(n_watchdog == 0), got=n_watchdog, want=0),
        dict(id='V1-4', name='无 >30 s 合成空窗',
             ok=(max_gap is None or max_gap <= 30.0), got=max_gap, want='<=30'),
        dict(id='V1-5', name='不变式 n_played + n_dropped == n_submitted',
             ok=(None not in (n_played, n_dropped, n_submitted)
                 and n_played + n_dropped == n_submitted),
             got=(None if n_played is None else n_played + (n_dropped or 0)),
             want=n_submitted),
        dict(id='V1-6', name='worker 重启次数 = 0',
             ok=(n_restart == 0), got=n_restart, want=0),
        dict(id='V1-7', name='撞帧上限 cap = 0',
             ok=(n_cap == 0), got=n_cap, want=0),
        dict(id='V1-8', name='失控 runaway = 0',
             ok=(n_runaway == 0), got=n_runaway, want=0),
        dict(id='V1-9', name='逐句 error 非空 = 0',
             ok=(n_err == 0), got=n_err, want=0),
        dict(id='V1-10', name='🔴 无 consumed=False 的句子（音频没被播完）',
             ok=(n_not_consumed == 0), got=n_not_consumed, want=0),
        dict(id='V1-11', name='句内 underflow_in_sentence P95 = 0（只允许句前等待）',
             ok=(_pct(uf, 0.95) == 0), got=_pct(uf, 0.95), want=0),
        dict(id='V1-12', name='逐句 wav 落盘 ≥ 10 句（供 reviewer 回转写）',
             ok=(len(wav_by_jid) >= 10), got=len(wav_by_jid), want='>=10'),
        # ⚠️ reviewer 明文：「RTF > 1 导致的丢句**只记录、不判失败**」
        dict(id='V1-13', name='（只记录）synth_rtf P95 —— 不判失败',
             ok=True, got=_pct(rtfs, 0.95), want='只记录'),
        dict(id='V1-14', name='（只记录）合成首包 P95 —— 不判失败',
             ok=True, got=_pct(synth_first, 0.95), want='只记录'),
        dict(id='V1-15', name='（只记录）排队等待 P95 —— 不判失败',
             ok=True, got=_pct(queued, 0.95), want='只记录'),
    ]
    n_pass = sum(1 for c in checks if c['ok'])

    report = dict(
        ts=time.strftime('%Y-%m-%d %H:%M:%S'),
        cfg='v1_cuda', asr_device='GPU.0', mt_device='GPU.0',
        tts_device='CUDA', duration=duration, translate=translate,
        out_device=out_device,
        wall_s=round(wall, 1), rc=rc,
        cli_stat_line=stat_line,
        n_submitted=n_submitted, n_played=n_played, n_dropped=n_dropped,
        n_restart=n_restart,
        n_drop_unbuilt=n_drop_unbuilt, n_drop_written=n_drop_written,
        n_no_audio=n_no_audio, n_err_jsonl=n_err,
        n_watchdog=n_watchdog, n_watchdog_restart=n_watchdog_restart,
        n_player_err=n_player_err,
        n_consumed=n_consumed, n_not_consumed=n_not_consumed,
        n_read_ok=n_read_ok, cb_delta_max=cb_delta_max,
        read_delta_max=read_delta_max,
        first_packet_s=first_packet, max_backlog_s=max_backlog,
        end_lag_s=end_lag,
        synth_rtf_p50=_pct(rtfs, 0.50), synth_rtf_p95=_pct(rtfs, 0.95),
        queued_s_p50=_pct(queued, 0.50), queued_s_p95=_pct(queued, 0.95),
        synth_first_s_p50=_pct(synth_first, 0.50),
        synth_first_s_p95=_pct(synth_first, 0.95),
        prebuffer_s_p50=_pct(pb, 0.50), prebuffer_s_p95=_pct(pb, 0.95),
        underflow_in_sentence_p95=_pct(uf, 0.95),
        underflow_in_sentence_ms_p95=_pct(uf_ms, 0.95),
        underflow_pre_sentence_p95=_pct(uf_pre, 0.95),
        queue_peak_s=qpk_s, queue_peak_mb=qpk_mb,
        queue_lag_max_s=qlag_max,
        max_synth_gap_s=max_gap,
        n_jsonl_rows=len(rows),
        n_dump_wav=len(wav_by_jid),
        n_align_rows=len(align_rows),
        checks=checks, pass_count=n_pass, fail_count=len(checks) - n_pass,
        artifacts=dict(jsonl=jsonl_path, csv=csv_path,
                       cli_log=log_path, dump_dir=dump_dir,
                       alignment=align_path),
        note='APP-027 V1 CUDA 连续实时（CLI 回放 + **真实播放路径** + '
             'CUDA 边车）；**非 GUI / 非用户启动方式 / 非用户实听**；'
             'V3（MiniMax+CAMPPlus）与 V4（用户实听）不在本脚本范围',
    )
    with open(rep_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    for c in checks:
        print('  [%s] %-7s %-52s got=%r want=%r'
              % ('PASS' if c['ok'] else 'FAIL', c['id'], c['name'],
                 c['got'], c['want']))
    print('  SUMMARY: PASS=%d FAIL=%d' % (n_pass, len(checks) - n_pass))
    print('  报告：%s' % rep_path)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--translate', default='zh')
    ap.add_argument('--out-device', default=None)
    ap.add_argument('--quiet-timeout', type=float, default=900.0)
    ap.add_argument('--lock-timeout', type=float, default=3600.0)
    ap.add_argument('--tag-suffix', default='')
    ap.add_argument('--probe-only', action='store_true',
                    help='只做 CUDA 边车只读探测（不取锁、不跑推理）')
    args = ap.parse_args()

    print('[probe] CUDA 边车解释器探测 …')
    probe = _probe_cuda()
    print('[probe] %r' % (probe,))
    if not probe.get('ok'):
        print('!! CUDA 组客观不可做 ⇒ 如实写明原因，退出')
        return 2
    if args.probe_only:
        return 0

    if not os.path.exists(SPE):
        print('!! 找不到 SPE 切片：%s' % SPE)
        return 2
    os.makedirs(OUT_DIR, exist_ok=True)

    ml = _lock()
    print('[lock] 申请共享机器锁 …')
    ok_lock, payload = ml.acquire(module='app', timeout=args.lock_timeout,
                                   poll=20, verbose=True)
    if not ok_lock:
        print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
        return 3
    print('[lock] 已取得：%r' % (payload,))
    try:
        print('[lock] 等安静窗口 …')
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                    timeout=args.quiet_timeout,
                                                    verbose=True)
        print('[lock] 安静窗口 ok=%s info=%r' % (ok_quiet, qinfo))
        if not ok_quiet:
            print('[lock] !! 没有安静窗口 ⇒ 退出')
            return 4

        rep = run_one(args.duration, args.translate, args.out_device,
                      args.tag_suffix)
        # ── 汇总 ──────────────────────────────────────────────
        summary = dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'),
                       cfg='v1_cuda', device='CUDA',
                       duration=args.duration, translate=args.translate,
                       cuda_probe=probe,
                       synth_rtf_p50=rep['synth_rtf_p50'],
                       synth_rtf_p95=rep['synth_rtf_p95'],
                       queued_s_p95=rep['queued_s_p95'],
                       synth_first_s_p95=rep['synth_first_s_p95'],
                       underflow_in_sentence_p95=rep['underflow_in_sentence_p95'],
                       queue_peak_s=rep['queue_peak_s'],
                       queue_peak_mb=rep['queue_peak_mb'],
                       max_backlog_s=rep['max_backlog_s'],
                       end_lag_s=rep['end_lag_s'],
                       n_submitted=rep['n_submitted'],
                       n_played=rep['n_played'],
                       n_dropped=rep['n_dropped'],
                       n_drop_unbuilt=rep['n_drop_unbuilt'],
                       n_drop_written=rep['n_drop_written'],
                       n_no_audio=rep['n_no_audio'],
                       n_watchdog=rep['n_watchdog'],
                       n_consumed=rep['n_consumed'],
                       max_synth_gap_s=rep['max_synth_gap_s'],
                       n_dump_wav=rep['n_dump_wav'],
                       pass_count=rep['pass_count'],
                       fail_count=rep['fail_count'],
                       artifacts=rep['artifacts'],
                       note='APP-027 V1 CUDA 连续实时（CLI + 真实播放）')
        sum_path = os.path.join(OUT_DIR, 'app027_v1_summary.json')
        with open(sum_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print('\n[SUMMARY] V1 CUDA：P/F=%d/%d  rtf_p50=%s  rtf_p95=%s  '
              'uf_p95=%s  丢句=%s  已写入被丢=%s  无音频=%s  看门狗=%s  '
              'consumed=%s'
              % (rep['pass_count'], rep['fail_count'], rep['synth_rtf_p50'],
                 rep['synth_rtf_p95'], rep['underflow_in_sentence_p95'],
                 rep['n_dropped'], rep['n_drop_written'], rep['n_no_audio'],
                 rep['n_watchdog'], rep['n_consumed']))
        print('[SUMMARY] 汇总已写入：%s' % sum_path)
        return 0
    finally:
        try:
            ml.release(payload)
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
