#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app177 — 从 APP-043 验收产物切出「换人前后」的配音片段（供用户实听）。

🔴 **为什么需要它**（APP-039 验收原文）：
  「挑几段换人前后的配音放进 `shared/app_clone_listen/`，
    由 reviewer 拉回给用户实听。**用户实听是最终验收。**」
  ⇒ 本脚本产出**实听素材**（不是判据），并附一份 manifest 记录
    每段来自哪一句、哪个 spk、用的是克隆还是预设。

🔴 **对齐口径（实测得出）**：
  - `clone_out.wav` 是**播放录制的实际输出**（24 kHz / 单声道）；
  - 每句的 `play_wall` 是**墙钟**（`time.time()`）；
  - 实测 `play_wall` 跨度 932.22 s vs wav 总长 935.65 s ⇒ 比率 **1.0037**
    ⇒ 用 `offset = play_wall[i] − play_wall[0]` 映射，误差 ≈ 3.4 s / 935 s
    ⇒ 对「听音色是否换了」这个用途**足够**；
  - 🔴 **判据不做这件事**（切片对齐有误差）⇒ 只作实听素材，不作判定依据。

## 用法
    python results/app/app177_clone_listen_extract.py
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import wave

HOME = os.path.expanduser('~')
# 🔴🔴🔴 §118：仓库根从**本脚本自身位置**推导，不写死 `HOME/confucius4-openvino`
#    ⇒ 否则 fresh clone 时会读到**原仓库**的文件 ⇒ 验收结论是假象。
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(HOME, 'app043_clone_accept')
JSONL = os.path.join(SRC_DIR, 'clone.tts.jsonl')
WAV = os.path.join(SRC_DIR, 'clone_out.wav')
# 🔴 APP-039 原文指定的目录
LISTEN_DIR = os.path.join(HOME, 'shared', 'app_clone_listen')
EVID = os.path.join(REPO, 'results', 'app',
                    'app177_clone_listen_manifest.json')


def read_wav_mono(path):
    """读 wav ⇒ (float 列表, sr)。只处理 16-bit PCM（产品输出即此）。"""
    with wave.open(path, 'rb') as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    assert sw == 2, '只支持 16-bit PCM，实际 %d' % sw
    assert ch == 1, '只支持单声道，实际 %d' % ch
    import array
    a = array.array('h')
    a.frombytes(raw)
    if struct.pack('h', 1) == struct.pack('=h', 1):
        pass
    return a, sr


def main():
    rows = [json.loads(l) for l in open(JSONL, encoding='utf-8') if l.strip()]
    if not os.path.isfile(WAV):
        print('!! 找不到 %s' % WAV)
        return 2

    samples, sr = read_wav_mono(WAV)
    total_s = len(samples) / float(sr)
    print('[wav] %d 样本 / %d Hz = %.2f s' % (len(samples), sr, total_s))

    base = min(r['play_wall'] for r in rows if r.get('play_wall') is not None)

    # ── 找换人点：voice_spk 发生变化 ──
    pts = []
    prev = object()
    for r in rows:
        k = r.get('voice_spk')
        if k in (None, '', -1):
            continue
        k = str(k)
        if k != prev:
            pts.append((r, k))
            prev = k
    print('[switch] 换人点 = %d 个' % len(pts))

    # ── 每个换人点切「前一句（旧音色）+ 后一句（新音色）」──
    by_id = {r.get('id'): r for r in rows}
    segs = []
    for idx, (r, spk) in enumerate(pts):
        rid = r.get('id')
        # 前一句：同 spk 之前的最后一句（任意 spk）
        prev_r = None
        for rr in rows:
            if (rr.get('id') or -1) < (rid or -1) and rr.get('play_wall'):
                prev_r = rr
        if prev_r is None:
            continue
        segs.append(('BEFORE', prev_r))
        segs.append(('AFTER', r))

    if not segs:
        print('!! 没有可切的换人点')
        return 3

    os.makedirs(LISTEN_DIR, exist_ok=True)

    # 🔴 只保留本轮产物（旧的 00:00 文件属于历史轮次 ⇒ 另存归档目录）
    archive = os.path.join(LISTEN_DIR, '_archive_pre_app052')
    if os.path.isdir(LISTEN_DIR):
        for fn in os.listdir(LISTEN_DIR):
            if fn.endswith('.wav'):
                os.makedirs(archive, exist_ok=True)
                shutil.move(os.path.join(LISTEN_DIR, fn),
                            os.path.join(archive, fn))
                print('[archive] 旧素材已归档：%s' % fn)

    manifest = []
    for n, (tag, r) in enumerate(segs, 1):
        off = float(r['play_wall']) - base
        dur = float(r.get('out_dur_s') or 0.0)
        if dur <= 0:
            dur = 2.0
        # 🔴 前后各留 0.6 s 余量，便于耳朵听出切换点
        pad = 0.6
        s0 = max(0, int((off - pad) * sr))
        s1 = min(len(samples), int((off + dur + pad) * sr))
        if s1 <= s0:
            continue
        spk = r.get('voice_spk') or 'None'
        name = '%03d_%s_%s_%s.wav' % (
            n, tag, spk, r.get('id'))
        path = os.path.join(LISTEN_DIR, name)
        with wave.open(path, 'wb') as o:
            o.setnchannels(1)
            o.setsampwidth(2)
            o.setframerate(sr)
            o.writeframes(samples[s0:s1].tobytes())
        sz = os.path.getsize(path)
        item = {
            'file': name,
            'role': tag,
            'sent_id': r.get('id'),
            'voice_spk': r.get('voice_spk'),
            'voice_kind': r.get('voice_kind'),
            'clone_active': r.get('clone_active'),
            'clone_mode': r.get('clone_mode'),
            'wav_offset_s': round(off, 3),
            'clip_dur_s': round((s1 - s0) / float(sr), 3),
            'bytes': sz,
            'sha256': __import__('hashlib').sha256(
                open(path, 'rb').read()).hexdigest(),
        }
        manifest.append(item)
        print('[clip] %-40s role=%-6s spk=%-5s kind=%-7s %.2f s  %d B'
              % (name, tag, spk, r.get('voice_kind'),
                 item['clip_dur_s'], sz))

    ev = {
        'source_wav': WAV,
        'source_wav_total_s': round(total_s, 3),
        'sample_rate': sr,
        'jsonl': JSONL,
        'n_rows': len(rows),
        'n_switch_points': len(pts),
        'align_method': 'offset = play_wall[i] - play_wall[0]',
        'align_note': ('play_wall 跨度 932.22 s vs wav 935.65 s ⇒ 比率 1.0037；'
                       '本脚本只产实听素材，不作判定依据'),
        'listen_dir': LISTEN_DIR,
        'archive_dir': archive,
        'n_clips': len(manifest),
        'clips': manifest,
    }
    os.makedirs(os.path.dirname(EVID), exist_ok=True)
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('证据已写：%s' % EVID)
    print('实听素材目录：%s（%d 段）' % (LISTEN_DIR, len(manifest)))
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
