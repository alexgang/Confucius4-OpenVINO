#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §1 验收②：**ASR=NPU + ≥20 s 不停顿连续语音** ⇒ 不再抛 ValueError。

## reviewer 原文（APP-121 §1「验收 ②」）
> 用包内 python 跑 ASR=NPU：一段 ≥20 s 不停顿的连续语音（可以把 SPE 里的
> 停顿压掉后拼接），日志里要有**强制切段**、**没有 ValueError**、
> **字幕持续输出到结束**。

## 本脚本做什么
1. **造素材**：从 SPE（`clip_10min_0_600.wav`）里把**静音段压到 0.20 s**
   （< 静音超时阈值 0.8 s ⇒ 段尾规则 2 不触发 ⇒ 段只能累积到
   `MAX_SEG_SEC=20 s` 被**强制切段**）⇒ 造出「≥20 s 不停顿连续语音」；
2. **跑产品同款调用路径**：`<包内 python> <包内 app>/live_caption_app.py --cli
   --file <wav> --asr-device NPU --translate off --tts off --out <txt>`
   ⇒ 解析日志：`ValueError` / 字幕行数 / 收尾是否到达素材末尾；
3. **跑段长探针**（同包、同设备、同素材）：逐段记录段长
   ⇒ **证明存在 ≥19.9 s 的段**（= `MAX_SEG_SEC` 强制切段的产物）；
4. **反证组**：同一素材跑**修复前的包**（磁盘上的 MiniMVP v1.1 = 旧代码）
   ⇒ **必须**出现 `ValueError` 且字幕**中途停掉**
   ⇒ 证明本判据能识破该缺陷。

## 用法
```
<包内 python> live_caption/_app121_asr_npu_longseg.py --pkg <包目录> --out <json>
```
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import wave

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
ASR_WORK = os.path.join(HOME, 'qwen3asr_06b')
SPE_WAV = os.path.join(ASR_WORK, 'b_kit_stateful', 'assets',
                        'clip_10min_0_600.wav')
TMP = os.path.join(HOME, 'AppData', 'Local', 'Temp', 'app121')
RESULTS = os.path.join(REPO, 'results', 'app')

SR = 16000
FRAME_SEC = 0.02
#: 把静音段压到这么长（**必须 < SILENCE_CUT_SEC=0.8** ⇒ 规则2 不触发）
SIL_KEEP_SEC = 0.20
#: 造出来的素材总长（秒）—— 要 > MAX_SEG_SEC(20) 才能逼出强制切段
TARGET_SEC = 26.0


def log(*a):
    print(*a, flush=True)


def read_wav_i16(path):
    with wave.open(path, 'rb') as w:
        assert w.getframerate() == SR
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        raw = w.readframes(w.getnframes())
    import numpy as np
    return np.frombuffer(raw, dtype='<i2').copy()


def write_wav_i16(path, arr):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(arr.astype('<i2').tobytes())


def build_continuous_wav(out_path, src=SPE_WAV, target_sec=TARGET_SEC, pkg=None):
    """🔴 造「≥20 s 不停顿连续语音」：把 SPE 里**App 自己认得的静音**整段抠掉。

    🔴 **必须用 App 的判据**（`live_caption_app._frame_db_series` ＋
       `seg_stream.find_silence_in_range`，frame 30 ms / hop 10 ms，
       相对门限 `p90 − 12 dB`，`min_silence_ms=300`）
       ⇒ 抠完之后**用同一个判据复核**：没有 ≥300 ms 的静音
       ⇒ 规则1（≥6 s 且近 3 s 内有 ≥300 ms 静音）**不触发**、
         规则2（段尾 ≥0.8 s 静音）**不触发**
       ⇒ 段只能一路累积到 `MAX_SEG_SEC=20 s` ⇒ **被强制切段**。
    """
    import numpy as np
    app_dir = os.path.join(pkg, 'app')
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import live_caption_app as L
    from seg_stream import find_silence_in_range

    a = read_wav_i16(src).astype(np.float32) / 32768.0
    fdb = L._frame_db_series(a)          # App 自己的帧能量序列
    p90 = float(np.percentile(fdb, 90))
    hop = 10                             # ms（App 的 hop）
    min_sil_frames = int(300 / hop)      # 30 帧 = 300 ms

    need = int(target_sec * SR)
    attempts = []
    thr = p90 - float(L.SIL_REL_DROP_DB)
    arr = None
    for it in range(6):
        is_sil = fdb < thr
        # 找 ≥300 ms 的静音 run ⇒ 整段抠掉
        keep_idx = np.ones(fdb.shape[0], dtype=bool)
        runs = []
        i = 0
        n = fdb.shape[0]
        while i < n:
            if is_sil[i]:
                j = i
                while j < n and is_sil[j]:
                    j += 1
                if (j - i) >= min_sil_frames:
                    keep_idx[i:j] = False
                    runs.append((i, j))
                i = j
            else:
                i += 1
        # 帧 → 采样
        n_fr = int(30 * SR / 1000)
        h_fr = int(hop * SR / 1000)
        mask = np.ones(a.shape[0], dtype=bool)
        for (i0, i1) in runs:
            s0 = max(0, i0 * h_fr)
            s1 = min(a.shape[0], i1 * h_fr)
            mask[s0:s1] = False
        arr = a[mask][:need]
        # 🔴 **用 App 的判据复核**
        sil_db = float(np.percentile(L._frame_db_series(arr), 90)) - \
            float(L.SIL_REL_DROP_DB)
        cut = find_silence_in_range(arr, start_sample=0,
                                    end_sample=int(arr.shape[0]),
                                    silence_db=sil_db, min_silence_ms=300)
        attempts.append({'iter': it, 'thr_db': round(thr, 2),
                         'n_runs_cut': len(runs),
                         'duration_s': round(arr.shape[0] / SR, 3),
                         'verify_silence_cut_sample': cut,
                         'verify_ok': cut is None})
        if cut is None and arr.shape[0] >= need:
            break
        thr -= 2.0                        # 更激进一点再抠

    write_wav_i16(out_path, (np.clip(arr, -1.0, 1.0) * 32767.0).astype('<i2'))
    fdb2 = L._frame_db_series(arr)
    info = {
        'src': src, 'out': out_path,
        'bytes': os.path.getsize(out_path),
        'samples': int(arr.shape[0]),
        'duration_s': round(arr.shape[0] / SR, 3),
        'p90_db': round(p90, 2),
        'sil_rel_drop_db': float(L.SIL_REL_DROP_DB),
        'detector': ('App 自己的 live_caption_app._frame_db_series + '
                     'seg_stream.find_silence_in_range（30 ms/10 ms，'
                     '相对门限 p90−12 dB，min_silence_ms=300）'),
        'attempts': attempts,
        'n_sil_runs_cut': attempts[-1]['n_runs_cut'] if attempts else 0,
        'verify_no_300ms_silence': bool(attempts and attempts[-1]['verify_ok']),
        'max_silence_run_note': ('没有 ≥300 ms 的静音 ⇒ 规则1/规则2 都不触发 '
                                 '⇒ 段只能累积到 MAX_SEG_SEC(20) 被强制切段'),
        'sha256': _sha(out_path),
    }
    return info


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def run_cli(pkg, wav, tag):
    """🔴 **产品同款调用路径**：包内 python + 包内 app 的 CLI。"""
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    py = os.path.join(pkg, 'python', 'python.exe')
    out_txt = os.path.join(TMP, 'longseg_%s.txt' % tag)
    # 🔴 **先删旧产物**（CLI 是增量写 ⇒ 上一次残留会污染本轮的「字幕行数」）
    for _p in (out_txt, os.path.join(TMP, 'longseg_%s.log' % tag)):
        if os.path.isfile(_p):
            os.remove(_p)
    cmd = [py, app, '--cli', '--file', wav, '--asr-device', 'NPU',
           '--translate', 'off', '--tts', 'off', '--out', out_txt]
    log('[app121] CLI：%s' % ' '.join(cmd))
    t0 = time.time()
    cp = subprocess.run(cmd, cwd=pkg, capture_output=True, text=True,
                        encoding='utf-8', errors='replace', timeout=3600)
    wall = time.time() - t0
    combined = (cp.stdout or '') + '\n' + (cp.stderr or '')
    log_path = os.path.join(TMP, 'longseg_%s.log' % tag)
    with io.open(log_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(combined)
    txt = ''
    if os.path.isfile(out_txt):
        with io.open(out_txt, 'r', encoding='utf-8', errors='replace') as f:
            txt = f.read()
    lines = [l for l in txt.splitlines() if l.strip()]
    return {
        'cmd': cmd, 'cwd': pkg, 'rc': cp.returncode, 'wall_s': round(wall, 1),
        'log_path': log_path, 'out_txt': out_txt,
        'has_valueerror': ('ValueError' in combined),
        'valueerror_lines': [l for l in combined.splitlines()
                              if 'ValueError' in l][:10],
        'has_audio_too_long': ('音频过长' in combined),
        'n_final_lines': len(lines),
        'n_chars': len(txt),
        'first_line': (lines[0][:120] if lines else ''),
        'last_line': (lines[-1][:200] if lines else ''),
        'stdout_tail': (cp.stdout or '')[-3000:],
        'stderr_tail': (cp.stderr or '')[-3000:],
    }


def run_segment_probe(pkg, wav, device='NPU'):
    """🔴 段长探针：逐段记录段长 ⇒ 证明「强制切段」确实发生了。"""
    import numpy as np
    app_dir = os.path.join(pkg, 'app')
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import live_caption_app as L
    table = L.active_asr_engines()
    cands = [(k, c) for k, c in table.items()
             if c.get('kind') == 'asr06b' and c.get('device') == device]
    if not cands:
        return {'FAIL': '没有 kind=asr06b / device=%s 的引擎' % device}
    key = sorted(cands)[0][0]
    eng = L.OVEngine(key, on_log=lambda *a: None, force_language=None,
                     device=device)
    segs = []
    state = {'fed_s': 0.0}
    forced = []
    max_seg_sec = float(L.MAX_SEG_SEC)
    orig_close = eng._close_segment
    orig_due = eng.seg.due

    def due_rec(acc):
        dur = float(acc.shape[0]) / L.SR
        r = orig_due(acc)
        if r and dur >= max_seg_sec - 0.05:
            forced.append(round(dur, 3))
        return r
    eng.seg.due = due_rec

    def close_rec():
        acc = eng.state.audio_accum
        dur = (float(acc.shape[0]) / L.SR) if acc is not None else 0.0
        end_s = state['fed_s']
        txt = orig_close()
        segs.append({'start_s': round(end_s - dur, 3), 'end_s': round(end_s, 3),
                     'duration_s': round(dur, 3), 'n_chars': len(txt),
                     'text_head': txt[:80]})
        return txt
    eng._close_segment = close_rec

    audio = read_wav_i16(wav)
    step = int(L.CHUNK_SEC * L.SR)
    err = None
    t0 = time.perf_counter()
    try:
        for i in range(0, len(audio) - step + 1, step):
            blk = audio[i:i + step]
            state['fed_s'] += len(blk) / float(L.SR)
            eng.feed(blk, time.perf_counter())
        tail = eng.flush()
        if tail:
            segs.append({'start_s': round(state['fed_s'], 3),
                         'end_s': round(state['fed_s'], 3),
                         'duration_s': 0.0, 'n_chars': len(tail),
                         'text_head': tail[:80]})
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    wall = time.perf_counter() - t0
    probe = getattr(eng.backend, 'probe', {}) or {}
    out = {
        'engine_key': key, 'device': device,
        'max_seg_sec': max_seg_sec,
        'n_segs': len(segs),
        'seg_durations_s': [s['duration_s'] for s in segs],
        'max_seg_duration_s': max([s['duration_s'] for s in segs], default=0),
        'n_forced_cuts': len(forced),
        'forced_cut_durations_s': forced,
        'prefix_truncations': int(probe.get('prefix_truncations', 0)),
        'truncations': int(probe.get('truncations', 0)),
        'exception': err,
        'wall_s': round(wall, 2),
        'segments': segs[:60],
    }
    try:
        eng.close()
    except Exception:
        pass
    return out


def analyze_wav(pkg, wav):
    """🔴 用 **App 自己的判据**复核素材（复用时也要留证据）。"""
    import numpy as np
    app_dir = os.path.join(pkg, 'app')
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import live_caption_app as L
    from seg_stream import find_silence_in_range
    a = read_wav_i16(wav).astype(np.float32) / 32768.0
    fdb = L._frame_db_series(a)
    p90 = float(np.percentile(fdb, 90))
    sil_db = p90 - float(L.SIL_REL_DROP_DB)
    cut = find_silence_in_range(a, start_sample=0, end_sample=int(a.shape[0]),
                                silence_db=sil_db, min_silence_ms=300)
    return {'out': wav, 'bytes': os.path.getsize(wav),
            'duration_s': round(a.shape[0] / SR, 3),
            'p90_db': round(p90, 2),
            'sil_rel_drop_db': float(L.SIL_REL_DROP_DB),
            'detector': ('App 自己的 live_caption_app._frame_db_series + '
                         'seg_stream.find_silence_in_range（30 ms/10 ms，'
                         '相对门限 p90−12 dB，min_silence_ms=300）'),
            'verify_no_300ms_silence': cut is None,
            'verify_silence_cut_sample': cut,
            'sha256': _sha(wav)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--wav', default='')
    ap.add_argument('--skip-cli', action='store_true')
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    os.makedirs(TMP, exist_ok=True)
    # 🔴 写 PID 文件（供 session_lease.py addpid 用 ⇒ 新会话不会重复启动）
    op = args.out or os.path.join(RESULTS, 'app121_asr_npu_longseg_%s.json'
                                  % args.tag)
    os.makedirs(RESULTS, exist_ok=True)
    with open(op + '.pid', 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    wav = args.wav or os.path.join(TMP, 'longseg_continuous.wav')
    if not os.path.isfile(wav):
        log('[app121] 造「≥20 s 不停顿连续语音」素材…')
        wav_info = build_continuous_wav(wav, pkg=pkg)
    else:
        wav_info = analyze_wav(pkg, wav)
        wav_info['reused'] = True
    log('[app121] 素材：%s（%s s）' % (wav, wav_info.get('duration_s')))

    res = {'script': '_app121_asr_npu_longseg.py',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': pkg, 'tag': args.tag, 'wav': wav_info}

    # ── 取锁（占 NPU ⇒ 必须持共享机器锁）───────────────────────────
    sys.path.insert(0, REPO)
    import machine_lock_app
    ok, payload = machine_lock_app.acquire(module='app', timeout=3600, poll=20,
                                           verbose=True)
    if not ok:
        log('🔴 未取得 MACHINE_LOCK ⇒ 终止')
        return 2
    log('[app121] 已取锁：%s' % payload)
    try:
        if not args.skip_cli:
            res['cli'] = run_cli(pkg, wav, args.tag)
        res['segment_probe'] = run_segment_probe(pkg, wav, device='NPU')
    finally:
        try:
            machine_lock_app.release(payload, verbose=True)
            log('[app121] 已释放锁')
        except Exception as e:
            log('[app121] 释放锁异常：%r' % e)

    op = args.out or os.path.join(RESULTS, 'app121_asr_npu_longseg_%s.json'
                                  % args.tag)
    os.makedirs(RESULTS, exist_ok=True)
    tmp = op + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    os.replace(tmp, op)
    log('[app121] 证据 → %s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
