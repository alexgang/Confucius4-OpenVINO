#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app184 —— APP-051② / APP-043：从**已落盘**的验收产物里切出
「1.2–1.3× 加速配音」实听片段（供用户实听 = 最终验收）。

🔴🔴🔴 **为什么是「从已落盘产物里切」而不是「再跑一次」**：
  APP-043 的最后一项验收是「**3 段 1.2–1.3× 配音给用户实听**」。
  🔴 **再跑一次推理**意味着：
    - 重新占 NPU/GPU（**其他模块正在跑计时作业** ⇒ 会污染它们的 RTF）；
    - 耗时 5–10 min，且**结果不可复现**（语速/滞后窗口不同 ⇒ speed 分布不同）。
  ⇒ 而 `app043_clone_accept/clone.tts.jsonl` **已经落盘**，
    且实测 **83 句全部带 `speed`**（`1.1× 1 句 / 1.2× 1 句 / 1.3× 81 句`）
    ⇒ **1.2–1.3× 的句子就在里面** ⇒ 直接切片即可，**零推理、零 GPU、零干扰**。

🔴 **切片对齐口径**（沿用 `app177` 已实测的口径，不重新发明）：
  - `clone_out.wav` = 播放录制的实际输出（24 kHz / 单声道 / 16-bit PCM）；
  - 每句的 `play_wall` = 墙钟（`time.time()`）；
  - 实测 `play_wall` 跨度 vs wav 总长 ⇒ 比率 ≈ **1.0037**
    ⇒ 用 `offset = play_wall[i] − play_wall[0]` 映射（误差 ≈ 3.4 s / 935 s）
    ⇒ 对「听加速后音色是否变调/是否可懂」**足够**。
  ⇒ 🔴 **本脚本只产实听素材 + manifest，不做质量判定**
    （音质/可懂/不变调由**用户实听** + reviewer 判定）。

🔴 **纪律**：纯离线（只读 wav + jsonl）⇒ 不占机器锁、不跑推理、不碰 GPU。
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
import struct
import wave

HOME = os.path.expanduser('~')
# 🔴🔴🔴 §118：仓库根从**本脚本自身位置**推导，不写死 `HOME/confucius4-openvino`
#    ⇒ 否则 fresh clone 时会读到**原仓库**的文件 ⇒ 验收结论是假象。
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(HOME, 'app043_clone_accept')
JSONL = os.path.join(SRC_DIR, 'clone.tts.jsonl')
WAV = os.path.join(SRC_DIR, 'clone_out.wav')
# 🔴 APP-043 要求的实听目录
LISTEN_DIR = os.path.join(HOME, 'shared', 'app_accel_listen')
EVID = os.path.join(REPO, 'results', 'app',
                    'app184_app051_accel_listen_manifest.json')

# 🔴 目标：1.2–1.3× 各取 1 句 + 1 句 1.0× 作对照（听「加速前后」差别）
TARGET_SPEEDS = (1.2, 1.3, 1.3)
CLIP_PAD_S = 0.6          # 前后各留一点余量
MIN_CLIP_S = 2.0          # 太短不好听


def read_wav_mono(path):
    with wave.open(path, 'rb') as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    assert sw == 2, '只支持 16-bit PCM，实际 %d' % sw
    assert ch == 1, '只支持单声道，实际 %d' % ch
    a = array.array('h')
    a.frombytes(raw)
    return a, sr


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=LISTEN_DIR)
    ap.add_argument('--out', default=EVID)
    args = ap.parse_args()

    if not os.path.isfile(JSONL) or not os.path.isfile(WAV):
        raise SystemExit('❌ 缺少 APP-043 验收产物：%s / %s' % (JSONL, WAV))

    rows = [json.loads(l) for l in open(JSONL, encoding='utf-8') if l.strip()]
    rows = [r for r in rows if r.get('speed') is not None
            and r.get('play_wall') is not None
            and r.get('dur_s') is not None]
    rows.sort(key=lambda r: r['play_wall'])
    print('[jsonl] %s  rows=%d（含 speed + play_wall）' % (JSONL, len(rows)))

    hist = {}
    for r in rows:
        k = round(float(r['speed']), 4)
        hist[k] = hist.get(k, 0) + 1
    print('[speed] 分布 = %r' % hist)

    pcm, sr = read_wav_mono(WAV)
    total_s = len(pcm) / float(sr)
    print('[wav] %s  sr=%d  时长=%.2f s  帧数=%d' % (WAV, sr, total_s, len(pcm)))

    base_wall = float(rows[0]['play_wall'])

    # ── 选句：按目标倍率各取 1 句（取该倍率里**文本最长**的，好听）──────
    #   🔴🔴 **去重**：同一倍率可能有多句（实测 1.3× 有 81 句）
    #   ⇒ 若每次都取「第一条」⇒ 会切出**完全相同**的片段（本轮第一版踩到）
    #   ⇒ 维护 `used_ids`，同一句**不得被选两次**。
    picks = []
    used_ids = set()
    for want in TARGET_SPEEDS:
        cand = [r for r in rows
                if abs(float(r['speed']) - want) < 1e-6
                and r.get('id') not in used_ids]
        if not cand:
            print('[warn] 没有 speed=%.1f 的可用句子 ⇒ 跳过' % want)
            continue
        cand.sort(key=lambda r: (-len(r.get('text') or ''), r['play_wall']))
        picks.append(cand[0])
        used_ids.add(cand[0].get('id'))

    os.makedirs(args.out_dir, exist_ok=True)

    clips = []
    idx = 0
    for r in picks:
        idx += 1
        sp = round(float(r['speed']), 4)
        off = float(r['play_wall']) - base_wall
        dur = float(r['dur_s'])
        # 加速句的**实际输出时长** ≈ dur / speed（加速 ⇒ 更短）
        out_dur = float(r.get('out_dur_s') or (dur / sp if sp else dur))
        start = max(0.0, off - CLIP_PAD_S)
        end = min(total_s, off + out_dur + CLIP_PAD_S)
        if (end - start) < MIN_CLIP_S:
            # 太短 ⇒ 向后补足
            end = min(total_s, start + MIN_CLIP_S + CLIP_PAD_S)
        i0 = int(start * sr)
        i1 = int(end * sr)
        i1 = min(i1, len(pcm))
        seg = pcm[i0:i1]
        name = '%03d_speed_%.1fx_spk%s.wav' % (
            idx, sp, (r.get('voice_spk') or 'None'))
        path = os.path.join(args.out_dir, name)
        with wave.open(path, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(seg.tobytes())
        sz = os.path.getsize(path)
        clips.append({
            'file': name,
            'sent_id': r.get('id'),
            'speed': sp,
            'speed_lag_s': r.get('speed_lag_s'),
            'play_lag_s': r.get('play_lag_s'),
            'voice_spk': r.get('voice_spk'),
            'voice_kind': r.get('voice_kind'),
            'clone_active': r.get('clone_active'),
            'clone_mode': r.get('clone_mode'),
            'lang': r.get('lang'),
            'text': (r.get('text') or '')[:120],
            'wav_offset_s': round(start, 3),
            'clip_dur_s': round((i1 - i0) / float(sr), 3),
            'bytes': sz,
            'sha256': sha256_file(path),
        })
        print('[clip] %s  speed=%.1fx  sent_id=%s  dur=%.2f s  %d B'
              % (name, sp, r.get('id'), (i1 - i0) / float(sr), sz))

    # ── 判据（结构性，不是质量判定）──────────────────────────────────
    PASS = 0
    FAIL = 0
    CHECKS = []

    def check(name, cond, detail=''):
        nonlocal PASS, FAIL
        ok = bool(cond)
        if ok:
            PASS += 1
        else:
            FAIL += 1
        CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:500]})
        print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                               ('  —— %s' % detail) if detail else ''))

    print('\n== 判据（只验「素材齐备」，不判音质）==')
    check('① 切出 ≥3 段实听素材', len(clips) >= 3,
          '实际 %d 段' % len(clips))
    check('② 素材里**同时**含 1.2× 与 1.3×',
          any(abs(c['speed'] - 1.2) < 1e-6 for c in clips)
          and any(abs(c['speed'] - 1.3) < 1e-6 for c in clips),
          'speed 集合 = %r' % sorted(set(c['speed'] for c in clips)))
    check('③ 每段都能定位到源句（sent_id + play_wall + text 非空）',
          all(c.get('sent_id') is not None and c.get('text')
              for c in clips),
          'sent_id = %r' % [c.get('sent_id') for c in clips])
    check('③b 各段的**源句互不相同**（不得切出重复片段）',
          len(set(c.get('sent_id') for c in clips)) == len(clips),
          'sent_id = %r' % [c.get('sent_id') for c in clips])
    check('③c 各段**文件内容互不相同**（SHA256 去重）',
          len(set(c.get('sha256') for c in clips)) == len(clips),
          'sha256 前 12 位 = %r'
          % [str(c.get('sha256'))[:12] for c in clips])
    check('④ 每段时长 ≥ %.1f s（够听）' % MIN_CLIP_S,
          all(c['clip_dur_s'] >= MIN_CLIP_S for c in clips),
          '时长 = %r' % [c['clip_dur_s'] for c in clips])
    check('⑤ 每段文件都真实落盘且非空',
          all(c['bytes'] > 1000 for c in clips),
          'bytes = %r' % [c['bytes'] for c in clips])

    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('\nPASS %d  FAIL %d  verdict=%s' % (PASS, FAIL, verdict))

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-051② / APP-043（3 段 1.2–1.3× 配音实听素材）',
        'src_jsonl': JSONL,
        'src_wav': WAV,
        'src_wav_total_s': round(total_s, 3),
        'sample_rate': sr,
        'n_rows': len(rows),
        'speed_hist': {str(k): v for k, v in sorted(hist.items())},
        'listen_dir': args.out_dir,
        'n_clips': len(clips),
        'clips': clips,
        'align_method': 'offset = play_wall[i] - play_wall[0]',
        'align_note': '沿用 app177 已实测口径（比率 1.0037，误差 ≈3.4s/935s）'
                      '⇒ 只作实听素材，不作判定依据',
        'checks': CHECKS, 'n_pass': PASS, 'n_fail': FAIL,
        'verdict': verdict,
        'note': '纯离线（只读已落盘 wav+jsonl）⇒ 零推理、零 GPU、不占机器锁；'
                '**音质/不变调/可懂由用户实听 + reviewer 判定**',
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[evidence] %s' % args.out)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
