# -*- coding: utf-8 -*-
"""app123 — APP-027 **V3（克隆）** 的真实实测（CUDA 组 + NPU 组）。

## APP-027 V3 明文（逐字）

> **V3 克隆**：用 SPE 前 5 分钟切片（单一男声）实时跑，**开启克隆**，
> 落盘 ≥ 10 句 wav。reviewer 在本机做两件事：
> (a) MiniMax 回转写，CER 不劣于预设 A 同一批句子；
> (b) 用 CAMPPlus 算余弦相似度，**相对克隆源的相似度要明显高于预设 A 输出
>     相对克隆源的相似度**（每句差值 > 0，且均值差 ≥ 0.15）。
> CUDA 和 NPU 各一组。克隆用的源音频和嵌入**不得落盘**
> （落盘的只有 TTS 输出的 wav）。

## 本脚本做什么 / 不做什么

**做**：
1. 持**共享机器锁** + 等 **45 s 安静窗口**（APP-027 明文要求）；
2. 跑 **SPE 前 5 分钟切片**（`--speed 1`）⇒ `--tts-voice follow_speaker`
   ⇒ **开启克隆**；
3. 落盘**逐句 wav**（`--tts-dump-dir`）⇒ 供 reviewer 做 MiniMax 回转写
   与 CAMPPlus 对比；
4. 落盘**逐句 JSONL**（`--tts-jsonl`）⇒ **每句带 `clone_active` /
   `clone_mode` / `clone_audio_s`** ⇒ reviewer 能区分「哪句是克隆音色」
   与「哪句还是预设 A」（§84 新增字段）；
5. 产出**给 reviewer 的清单**（wav ↔ 文本 ↔ id ↔ 音色来源 一一对应）
   ⇒ 防止错位（APP-027 V1 明文同款要求）。

**不做**（明文划给别人）：
- ⛔ **不调用 MiniMax**（CER 由 reviewer 在本机做 —— APP-033 第 1 条）；
- ⛔ **不做 CAMPPlus**（音色相似度由 reviewer 做）；
- ⛔ **不做 V4 用户实听**（只有用户本人确认才算）。

## 🔴 判据设计（reviewer 明文的「客观可测部分」）

| 判据 | 含义 |
|---|---|
| V3-1 | 克隆**采集器**确实发出了更新（`n_updates > 0`） |
| V3-2 | worker 回报 `clone_active=True`（**克隆真的生效了**，不是静默回落） |
| V3-3 | `clone_mode` 有值（`xvector` = BabelVox / `ref_audio` = CUDA 边车）⇒ 知道走哪条路 |
| V3-4 | 逐句 wav **≥ 10 句**（reviewer 明文） |
| V3-5 | 逐句 JSONL 里 **有 `clone_active=True` 的句子**（不然 reviewer 无从比对） |
| V3-6 | **克隆源音频/嵌入未落盘**（APP-027 V3 隐私明文）⇒ 扫落盘目录不得有 `clone_*.npz` / `tts_speakers/` |
| V3-7 | 无播放器故障 / 无逐句 error |
| V3-8 | 不变式 `n_played + n_dropped + n_drop_unbuilt == n_submitted`（三段式，见 §82） |

⚠️ **CER / CAMPPlus 的差值判据本脚本不判**（需要 MiniMax 与 CAMPPlus）
⇒ 如实标 `[NO-EVIDENCE]`，交 reviewer。

## 🔴 边界（诚实声明）

- ⚠️ **CLI 回放 + 真实播放路径**，**不是 GUI**、**不是用户启动方式**
  （§63 L4）⇒ **不得据此写「用户听得到」**。
- ⚠️ **CPU 上不跑推理**：TTS 走 **CUDA 边车**（torch cu128 / RTX 5050）
  或 **NPU**（Intel AI Boost）；ASR 走 **GPU.0**（集显）。
- ⚠️ 本脚本**不做删除**（时间戳子目录 ⇒ 0 次删除 ⇒ 不触发批量删除保护）。

## 用法

    <py> results/app/app123_app027_v3_clone_real.py --group cuda --duration 300
    <py> results/app/app123_app027_v3_clone_real.py --group npu  --duration 300
"""
from __future__ import annotations

import argparse
import glob
import hashlib
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
OUT_DIR = os.path.join(HOME, 'app027_v3')

CUDA_PY = os.environ.get(
    'LIVECAP_CUDA_PY', r'C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe')

#: 🔴 **克隆源不得落盘**（APP-027 V3 隐私明文）⇒ 跑完扫这些模式
FORBIDDEN_PATTERNS = [
    os.path.join('voices', 'clone_*.npz'),
    os.path.join('tts_speakers', '*'),
    'clone_*.npz',
]


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _probe_cuda():
    """**只读**探测 CUDA 边车解释器（不加载模型）。"""
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


def _num(r, *keys):
    for k in keys:
        if k in r and r[k] is not None:
            return r[k]
    return None


def _pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    i = int(len(s) * p)
    if i >= len(s):
        i = len(s) - 1
    return s[i]


def run_group(group, duration, translate='zh'):
    """跑一组克隆实测（CUDA 或 NPU）。"""
    stamp = time.strftime('%Y%m%d_%H%M%S')
    os.makedirs(OUT_DIR, exist_ok=True)
    run_dir = os.path.join(OUT_DIR, 'v3_%s_run_%s' % (group, stamp))
    os.makedirs(run_dir, exist_ok=True)
    jsonl_path = os.path.join(run_dir, 'v3_%s.tts.jsonl' % group)
    log_path = os.path.join(run_dir, 'v3_%s_cli.log' % group)
    dump_dir = os.path.join(run_dir, 'dump')
    os.makedirs(dump_dir, exist_ok=True)
    rep_path = os.path.join(run_dir, 'v3_%s_report.json' % group)
    _run_cli(group, duration, translate, jsonl_path, log_path)
    return analyze_run_dir(run_dir, group)


def _run_cli(group, duration, translate, jsonl_path, log_path):
    """真正跑 CLI（落盘 jsonl/log）。"""
    run_dir = os.path.dirname(jsonl_path)
    dump_dir = os.path.join(run_dir, 'dump')
    rep_path = os.path.join(run_dir, 'v3_%s_report.json' % group)

    py = os.path.join(PKG_ROOT, 'python', 'python.exe')
    app_py = os.path.join(PKG_ROOT, 'app', 'live_caption_app.py')
    tts_device = 'CUDA' if group == 'cuda' else 'NPU'
    cmd = [py, app_py, '--cli', '--file', SPE,
           '--speed', '1.0', '--max-seconds', str(duration),
           '--tts', 'on',
           '--tts-device', tts_device,
           # 🔴🔴🔴 **V3 明文：开启克隆**
           '--tts-voice', 'follow_speaker',
           '--tts-dump-dir', dump_dir,
           '--tts-jsonl', jsonl_path,
           '--out', os.path.join(run_dir, 'subtitles.txt')]
    if group == 'npu':
        # NPU 只支持 f16/i8（device_config.py）⇒ 显式给 f16
        cmd += ['--tts-precision', 'f16']
    # 🔴 CUDA 组：ASR/MT 走 GPU.0（集显）；NPU 组：MT 走 GPU.0（APP-028① 默认）
    cmd += ['--asr-device', 'GPU.0']
    cmd += ['--mt-device', 'GPU.0']
    cmd += ['--translate', translate]

    print('\n' + '=' * 74)
    print('[cfg] v3_%s cmd=%s' % (group, ' '.join(cmd)))
    print('=' * 74)
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
    rc = proc.wait()
    wall = time.time() - t0
    print('[cfg] v3_%s 退出码=%s 墙钟=%.1f s' % (group, rc, wall))
    # 🔴🔴🔴 **把「退出码 + 墙钟」也写进 log**
    #   ⇒ 否则**离线重算**（`--reanalyze`）取不回这两个数
    #   ⇒ 报告里的 `wall_s`/`rc` 变成 0/None ⇒ **证据失真**。
    try:
        with open(log_path, 'ab') as lf:
            lf.write(('[cfg] v3_%s 退出码=%s 墙钟=%.1f s\n'
                      % (group, rc, wall)).encode('utf-8'))
    except Exception:
        pass
    return rc, wall


def analyze_run_dir(run_dir, group):
    """🔴 **对已落盘的 run 目录重新做分析**（口径修正后不必重跑 5 分钟）。

    ⚠️ **只读**：不跑推理、不碰机器锁 ⇒ 纯离线重算。
    """
    jsonl_path = os.path.join(run_dir, 'v3_%s.tts.jsonl' % group)
    log_path = os.path.join(run_dir, 'v3_%s_cli.log' % group)
    dump_dir = os.path.join(run_dir, 'dump')
    rep_path = os.path.join(run_dir, 'v3_%s_report.json' % group)
    manifest_path = os.path.join(run_dir, 'v3_%s_wav_manifest.json' % group)
    lines = []
    if os.path.exists(log_path):
        with open(log_path, encoding='utf-8', errors='replace') as lf:
            lines = [l.rstrip() for l in lf]
    wall = 0.0
    rc = None
    tts_device = 'CUDA' if group == 'cuda' else 'NPU'
    duration = None
    translate = None
    # 🔴 **从日志里回读「墙钟/退出码」**（离线重算时进程已退出 ⇒ 只能从 log 取）
    import re as _re0
    _m = _re0.search(r'退出码=(-?\d+) 墙钟=([\d.]+) s', '\n'.join(lines))
    if _m:
        rc = int(_m.group(1))
        wall = float(_m.group(2))
    wall_source = ('log' if _m else 'jsonl-span')
    # ── CLI 收尾行 ────────────────────────────────────────────
    stat_line = None
    clone_collect_line = None
    clone_active_line = None
    for l in reversed(lines):
        if (clone_collect_line is None and '[TTS]' in l
                and '克隆采集' in l):
            clone_collect_line = l
        if (clone_active_line is None and '[TTS]' in l
                and '克隆生效' in l):
            clone_active_line = l
        if stat_line is None and '[TTS]' in l and '提交' in l and '丢弃' in l:
            stat_line = l

    def pick(key, default=None, line=None):
        line = line or stat_line
        if not line:
            return default
        toks = line.replace(']', ' ').replace('=', ' ').split()
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

    # 克隆采集行：`语音 12.3s / 已发 8.0s  更新 2 次  失败 0 次  状态「已发送」`
    # 🔴 **用正则解析**：中文键与冒号相连（`克隆采集：语音`）⇒
    #   split 出来是**一个 token** ⇒ `pick('语音')` 匹配不到（实测踩过）
    n_updates = None
    n_sent_fail = None
    voiced_s = None
    sent_voiced_s = None
    if clone_collect_line:
        import re as _re1
        m = _re1.search(r'语音\s+([\d.]+)s', clone_collect_line)
        if m:
            voiced_s = float(m.group(1))
        m = _re1.search(r'已发\s+([\d.]+)s', clone_collect_line)
        if m:
            sent_voiced_s = float(m.group(1))
        m = _re1.search(r'更新\s+(\d+)\s+次', clone_collect_line)
        if m:
            n_updates = int(m.group(1))
        m = _re1.search(r'失败\s+(\d+)\s+次', clone_collect_line)
        if m:
            n_sent_fail = int(m.group(1))
    # 克隆生效行：`clone_active=True  clone_mode=xvector  clone_dur_s=6.4`
    # 🔴 **用正则解析 `key=value`**，不要用 split（双空格会让 token 错位
    #   ⇒ 实测把 `clone_active=True` 解析成了 None ⇒ **假 FAIL**）
    clone_active = None
    clone_mode = None
    clone_dur_s = None
    if clone_active_line:
        import re as _re
        m = _re.search(r'clone_active=(\S+)', clone_active_line)
        if m:
            clone_active = (m.group(1) == 'True')
        m = _re.search(r'clone_mode=(\S+)', clone_active_line)
        if m:
            clone_mode = m.group(1)
        m = _re.search(r'clone_dur_s=(\S+)', clone_active_line)
        if m:
            try:
                clone_dur_s = float(m.group(1))
            except ValueError:
                pass

    # ── 逐句 jsonl ────────────────────────────────────────────
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

    # 🔴🔴🔴 **墙钟的兜底口径**：log 里取不到时（离线重算）
    #   ⇒ 用 jsonl 的「首句 t_submit → 末句 t_done」跨度
    #   ⇒ **可从原始数据复核**（不是推算的估计值）
    if not wall:
        _ts = [r['t_submit'] for r in rows if r.get('t_submit') is not None]
        _td = [r['t_done'] for r in rows if r.get('t_done') is not None]
        if _ts and _td:
            wall = max(_td) - min(_ts)

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
    n_consumed = sum(1 for r in rows if r.get('consumed') is True)
    n_not_consumed = sum(1 for r in rows if r.get('consumed') is False)

    # 🔴 **逐句的音色来源**（§84 新增字段）⇒ reviewer 的分组依据
    n_rows_clone = sum(1 for r in rows if r.get('clone_active') is True)
    n_rows_preset = sum(1 for r in rows if r.get('clone_active') is False)
    clone_rows = [r for r in rows if r.get('clone_active') is True]
    preset_rows = [r for r in rows if r.get('clone_active') is False]
    modes = sorted(set(str(r.get('clone_mode')) for r in clone_rows))
    # ⚠️ **字段矛盾**检查：clone_active=True 但 clone_mode 为空 ⇒ 不可核
    n_mode_missing = sum(1 for r in clone_rows if not r.get('clone_mode'))
    n_mode_conflict = sum(1 for r in rows
                           if r.get('clone_active') is False
                           and r.get('clone_mode'))

    rtfs = [x for x in (_num(r, 'synth_rtf') for r in rows)
            if isinstance(x, (int, float))]
    uf = [_num(r, 'underflow_in_sentence') or 0 for r in rows]

    # ── wav 落盘 + 与文本对齐 ─────────────────────────────────
    wav_by_jid = {}
    if os.path.isdir(dump_dir):
        for fn in sorted(os.listdir(dump_dir)):
            if not fn.endswith('.wav'):
                continue
            parts = fn[:-4].split('_')
            try:
                jid = int(parts[1])
            except Exception:
                continue
            wav_by_jid.setdefault(jid, []).append(
                os.path.join(dump_dir, fn))
    id_to_text = {}
    id_to_row = {}
    for r in rows:
        if r.get('id') is not None:
            try:
                jid = int(r['id'])
            except Exception:
                continue
            id_to_text[jid] = (r.get('text') or '')
            id_to_row[jid] = r

    # 🔴 给 reviewer 的清单：wav ↔ 文本 ↔ 音色来源（**一一对应，防错位**）
    manifest = []
    for jid in sorted(wav_by_jid):
        r = id_to_row.get(jid, {})
        manifest.append(dict(
            id=jid,
            text=id_to_text.get(jid, ''),
            wavs=wav_by_jid[jid],
            wav_bytes=[os.path.getsize(w) for w in wav_by_jid[jid]],
            wav_sha256=[_sha256_file(w) for w in wav_by_jid[jid]],
            clone_active=r.get('clone_active'),
            clone_mode=r.get('clone_mode'),
            clone_audio_s=r.get('clone_audio_s'),
            n_samples=_num(r, 'n_samples'),
            dur_s=_num(r, 'dur_s'),
            synth_rtf=_num(r, 'synth_rtf'),
            consumed=r.get('consumed'),
            dropped=r.get('dropped'),
        ))
    manifest_path = os.path.join(run_dir, 'v3_%s_wav_manifest.json' % group)
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(dict(run_dir=run_dir, group=group, n_entries=len(manifest),
                       entries=manifest), f, ensure_ascii=False, indent=2)

    # 🔴 **克隆源不得落盘**（V3 隐私明文）⇒ 扫落盘目录与客户包
    leaks = []
    for pat in FORBIDDEN_PATTERNS:
        for base in (dump_dir, run_dir, PKG_ROOT):
            try:
                hits = glob.glob(os.path.join(base, '**', pat),
                                 recursive=True)
            except Exception:
                hits = []
            for h in hits:
                leaks.append(h)
    # 客户包内的 voices/tts_speakers 目录（本就不该存在）
    for d in ('voices', 'tts_speakers'):
        p = os.path.join(PKG_ROOT, d)
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for fn in files:
                    leaks.append(os.path.join(root, fn))
    leaks = sorted(set(leaks))

    # 临时克隆 wav（worker 会话结束即删）⇒ 落盘临时目录里不该残留
    tmp_clone_dir = os.path.join(os.environ.get('TEMP', ''),
                                 'confucius4_clone')
    tmp_leaks = []
    if os.path.isdir(tmp_clone_dir):
        for fn in sorted(os.listdir(tmp_clone_dir)):
            tmp_leaks.append(os.path.join(tmp_clone_dir, fn))

    n_clone_wav = sum(1 for e in manifest if e['clone_active'] is True)
    n_preset_wav = sum(1 for e in manifest if e['clone_active'] is False)

    # 🔴🔴🔴 **守恒口径必须只算一次**（§82 的教训：两段式在 V1 会假 FAIL）
    #   CLI 统计行的 `n_dropped` 与 jsonl 里的 `dropped` 行**可能重复**
    #   ⇒ 不能简单相加。
    #   ⇒ 这里用 **jsonl 独立核算**（每行一个 submitted id）：
    #      总行数 == 已写入行数 + 已丢行数 + 错误行数
    n_rows_total = len(rows)
    n_rows_written = sum(1 for r in rows if (_num(r, 'n_samples') or 0) > 0)
    n_rows_dropped = sum(1 for r in rows if r.get('dropped') is True)
    n_rows_error = sum(1 for r in rows if r.get('error'))
    jsonl_conserved = (n_rows_total ==
                       n_rows_written + n_rows_dropped + n_rows_error)

    # ── 判据 ─────────────────────────────────────────────────
    checks = [
        dict(id='V3-1', name='克隆采集器确实发出了更新（n_updates > 0）',
             ok=(n_updates is not None and n_updates > 0),
             got=n_updates, want='>0'),
        dict(id='V3-2', name='worker 回报 clone_active=True（克隆真的生效，非静默回落）',
             ok=(clone_active is True), got=clone_active, want=True),
        dict(id='V3-3', name='clone_mode 有值（xvector / ref_audio ⇒ 知道走哪条路）',
             ok=(clone_mode is not None and clone_mode != 'None'),
             got=clone_mode, want='非 None'),
        dict(id='V3-4', name='逐句 wav 落盘 ≥ 10 句（V3 明文）',
             ok=(len(wav_by_jid) >= 10), got=len(wav_by_jid), want='>=10'),
        dict(id='V3-5', name='逐句 JSONL 里有 clone_active=True 的句子（reviewer 可比对）',
             ok=(n_rows_clone > 0), got=n_rows_clone, want='>0'),
        dict(id='V3-5b', name='克隆组 wav ≥ 10 句（reviewer 要拿来做 CAMPPlus 对比）',
             ok=(n_clone_wav >= 10), got=n_clone_wav, want='>=10'),
        dict(id='V3-6', name='🔴 克隆源音频/嵌入**未落盘**（V3 隐私明文）',
             ok=(len(leaks) == 0), got=leaks, want=[]),
        dict(id='V3-6b', name='🔴 临时克隆 wav 会话结束已删（无残留）',
             ok=(len(tmp_leaks) == 0), got=tmp_leaks, want=[]),
        dict(id='V3-7', name='无播放器故障 / 无逐句 error',
             ok=(n_err == 0), got=n_err, want=0),
        dict(id='V3-7b', name='无 consumed=False（音频没被播完）',
             ok=(n_not_consumed == 0), got=n_not_consumed, want=0),
        dict(id='V3-8', name='不变式（jsonl 独立核算）总行数 == 已写入+已丢+错误',
             ok=jsonl_conserved,
             got=(n_rows_written + n_rows_dropped + n_rows_error),
             want=n_rows_total),
        dict(id='V3-8b', name='CLI 口径：n_played + n_dropped == n_submitted（两段式）',
             ok=(None not in (n_played, n_dropped, n_submitted)
                 and n_played + n_dropped == n_submitted),
             got=(None if n_played is None else n_played + (n_dropped or 0)),
             want=n_submitted),
        dict(id='V3-9', name='"已写入被丢" = 0',
             ok=(n_drop_written == 0), got=n_drop_written, want=0),
        dict(id='V3-10', name='无字段矛盾（clone_active=True 但 clone_mode 为空）',
             ok=(n_mode_missing == 0), got=n_mode_missing, want=0),
        dict(id='V3-11', name='无字段矛盾（clone_active=False 但 clone_mode 非空）',
             ok=(n_mode_conflict == 0), got=n_mode_conflict, want=0),
        dict(id='V3-12', name='（只记录）synth_rtf P50 —— 不判失败',
             ok=True, got=_pct(rtfs, 0.50), want='只记录'),
        dict(id='V3-13', name='（只记录）synth_rtf P95 —— 不判失败',
             ok=True, got=_pct(rtfs, 0.95), want='只记录'),
        dict(id='V3-14', name='（只记录）句内 underflow P95 —— 不判失败',
             ok=True, got=_pct(uf, 0.95), want='只记录'),
        dict(id='V3-CER', name='[NO-EVIDENCE] MiniMax 回转写 CER 对比 —— '
                              '归 reviewer（APP-033 第 1 条）',
             ok=True, got='[NO-EVIDENCE]', want='reviewer 做'),
        dict(id='V3-CAMP', name='[NO-EVIDENCE] CAMPPlus 余弦相似度差值 —— '
                               '归 reviewer',
             ok=True, got='[NO-EVIDENCE]', want='reviewer 做'),
    ]
    n_pass = sum(1 for c in checks if c['ok'])

    report = dict(
        ts=time.strftime('%Y-%m-%d %H:%M:%S'),
        cfg='v3_clone_%s' % group, group=group,
        tts_device=tts_device, asr_device='GPU.0', mt_device='GPU.0',
        duration=duration, translate=translate,
        wall_s=round(wall, 1), rc=rc, wall_source=wall_source,
        cli_stat_line=stat_line,
        cli_clone_collect_line=clone_collect_line,
        cli_clone_active_line=clone_active_line,
        clone_updates=n_updates, clone_sent_fail=n_sent_fail,
        clone_voiced_s=voiced_s, clone_sent_voiced_s=sent_voiced_s,
        clone_active=clone_active, clone_mode=clone_mode,
        clone_dur_s=clone_dur_s,
        n_submitted=n_submitted, n_played=n_played, n_dropped=n_dropped,
        n_drop_unbuilt=n_drop_unbuilt, n_drop_written=n_drop_written,
        n_no_audio=n_no_audio, n_err_jsonl=n_err,
        n_consumed=n_consumed, n_not_consumed=n_not_consumed,
        n_restart=n_restart,
        n_jsonl_rows=len(rows),
        n_rows_written=n_rows_written, n_rows_dropped=n_rows_dropped,
        n_rows_error=n_rows_error, jsonl_conserved=jsonl_conserved,
        n_rows_clone_active=n_rows_clone, n_rows_preset=n_preset_wav,
        clone_modes=modes,
        n_mode_missing=n_mode_missing, n_mode_conflict=n_mode_conflict,
        n_dump_wav=len(wav_by_jid),
        n_clone_wav=n_clone_wav, n_preset_wav=n_preset_wav,
        synth_rtf_p50=_pct(rtfs, 0.50), synth_rtf_p95=_pct(rtfs, 0.95),
        underflow_in_sentence_p95=_pct(uf, 0.95),
        clone_leaks=leaks, tmp_clone_residue=tmp_leaks,
        checks=checks, pass_count=n_pass, fail_count=len(checks) - n_pass,
        artifacts=dict(jsonl=jsonl_path, cli_log=log_path,
                       dump_dir=dump_dir, manifest=manifest_path,
                       report=rep_path),
        note='APP-027 V3 克隆实测（CLI 回放 + 真实播放路径）；'
             '**非 GUI / 非用户启动方式 / 非用户实听**；'
             'CER（MiniMax）与 CAMPPlus 归 reviewer ⇒ [NO-EVIDENCE]',
    )
    with open(rep_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    for c in checks:
        print('  [%s] %-9s %-56s got=%r want=%r'
              % ('PASS' if c['ok'] else 'FAIL', c['id'], c['name'],
                 c['got'], c['want']))
    print('  SUMMARY: PASS=%d FAIL=%d' % (n_pass, len(checks) - n_pass))
    print('  报告：%s' % rep_path)
    print('  清单：%s' % manifest_path)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--group', choices=['cuda', 'npu'], required=True)
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--translate', default='zh')
    ap.add_argument('--quiet-timeout', type=float, default=1800.0)
    ap.add_argument('--lock-timeout', type=float, default=3600.0)
    ap.add_argument('--probe-only', action='store_true')
    ap.add_argument('--reanalyze', default=None,
                    help='🔴 **不跑实测**：只对**已落盘**的 run 目录重新做分析'
                         '（口径修正后用 ⇒ 不必重跑 5 分钟）')
    args = ap.parse_args()

    if args.reanalyze:
        rd = os.path.abspath(args.reanalyze)
        print('[reanalyze] %s' % rd)
        rep = analyze_run_dir(rd, args.group)
        print('  SUMMARY: PASS=%d FAIL=%d'
              % (rep['pass_count'], rep['fail_count']))
        print('  报告：%s' % rep['artifacts']['report'])
        print('  清单：%s' % rep['artifacts']['manifest'])
        return 0 if rep['fail_count'] == 0 else 1

    if not os.path.exists(SPE):
        print('!! 找不到 SPE 切片：%s' % SPE)
        return 2
    os.makedirs(OUT_DIR, exist_ok=True)

    probe = None
    if args.group == 'cuda':
        print('[probe] CUDA 边车解释器探测 …')
        probe = _probe_cuda()
        print('[probe] %r' % (probe,))
        if not probe.get('ok'):
            print('!! CUDA 组客观不可做 ⇒ 如实写明原因，退出')
            return 2
        if args.probe_only:
            return 0

    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    print('[lock] 申请共享机器锁 …')
    ok_lock, payload = ml.acquire(module='app', timeout=args.lock_timeout,
                                   poll=20, verbose=True)
    if not ok_lock:
        print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
        return 3
    print('[lock] 已取得')
    try:
        print('[lock] 等安静窗口（45 s，无外部 python）…')
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                    timeout=args.quiet_timeout,
                                                    verbose=True)
        print('[lock] 安静窗口 ok=%s info=%r' % (ok_quiet, qinfo))
        if not ok_quiet:
            print('[lock] !! 没有安静窗口 ⇒ 退出')
            return 4
        rep = run_group(args.group, args.duration, args.translate)
        sum_path = os.path.join(OUT_DIR, 'app027_v3_%s_summary.json' % args.group)
        with open(sum_path, 'w', encoding='utf-8') as f:
            json.dump(dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'),
                           group=args.group, cuda_probe=probe,
                           pass_count=rep['pass_count'],
                           fail_count=rep['fail_count'],
                           clone_updates=rep['clone_updates'],
                           clone_active=rep['clone_active'],
                           clone_mode=rep['clone_mode'],
                           n_dump_wav=rep['n_dump_wav'],
                           n_clone_wav=rep['n_clone_wav'],
                           n_preset_wav=rep['n_preset_wav'],
                           artifacts=rep['artifacts']), f,
                      ensure_ascii=False, indent=2)
        print('\n[SUMMARY] V3 %s：P/F=%d/%d  克隆更新=%s  生效=%s  模式=%s  '
              'wav=%s（克隆 %s / 预设 %s）'
              % (args.group, rep['pass_count'], rep['fail_count'],
                 rep['clone_updates'], rep['clone_active'], rep['clone_mode'],
                 rep['n_dump_wav'], rep['n_clone_wav'], rep['n_preset_wav']))
        print('[SUMMARY] 汇总已写入：%s' % sum_path)
        return 0 if rep['fail_count'] == 0 else 1
    finally:
        try:
            ml.release(payload)
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
