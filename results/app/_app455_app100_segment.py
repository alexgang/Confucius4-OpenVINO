# -*- coding: utf-8 -*-
r"""_app455_app100_segment.py — APP-100「10 分钟片段口径」**唯一事实来源**（App 侧）。

## APP-100 原文（status/app/CORRECTIONS_APP.md，2026-11-11 10:38）
> 「以后凡是要求"全长 / 61 分钟 / SPE 全集"的 WER/CER 或 RTF 长跑，一律改用
> **同一段固定的 10 分钟片段**。片段起止秒写进脚本和结果 json，所有臂、所有版本
> 都用这同一段，保证可比。建议取 SPE 的 0–600 s；如果开头有长静音或纯音乐，
> 就顺延到第一段语音开始，并写明起点。」
> 「已下发、还没做完的纠偏（例如 ASR-053 第 3 项、APP-099）里的长跑，也按本条执行。」

## 🔴 本模块修掉的那个**假前提**（§175 遗留）
`_app437_app099_device_jobs.py`（2026-11-11 12:28 落盘）里写着：
> 「本机只有 ``SPE_0000_0500.wav``（实测 **300.0 s**），无法直接取 0–600 s 原始片段
> ⇒ 固定片段 = **0–300 s**，`--loop` 播 **2 次** = 600 s 音频时间线」

**该前提经实测证伪**（三条独立证据）：
1. 本仓库 `test_audio/260902_SPE_audio.wav` 实测 **3671.189 s**（16 kHz mono）
   —— 全长素材**一直在 App 仓库自己的 `test_audio/` 里**；
   `shared/SPE_0000_0500.wav` 只是它的**前 300 s 拷贝**（实测 SHA256 与源前 300 s
   逐字节相同 ⇒ 它是**截断件**，不是"本机唯一素材"）。
2. ASR 侧 canonical clip `qwen3asr_06b/dev/asr044_evalset/clip_10min_0_600.wav`
   实测 mtime **2026-11-11 10:52:30** —— 比 App GPU 作业开工（**11:32:08**）**早 40 分钟**
   ⇒ §175 当时**就能**拿到 canonical 片段，只是没去找。
3. §175 用的「0–300 s ×2 循环」与 ASR 的「0–600 s 连续」**内容不同**
   ⇒ 违反 APP-100「所有臂、所有版本都用这同一段，保证可比」。

⇒ 本模块提供 canonical 片段的**唯一切片 + 校验**入口，长跑脚本与判据脚本都从这里取。

## 契约（可复核）
* 源：`REPO/test_audio/260902_SPE_audio.wav`（3671.189 s / 16 kHz / mono）
* 片段：**0.0 – 600.0 s**（起点**不顺延** ⇒ 见 `START_REASON`）
* 产物：`REPO/test_audio/clip_10min_0_600.wav`（**gitignored**，与本仓库其它 wav 一致）
* 校验：**payload** SHA256（语义契约，写法无关）
  = `EXPECTED_PAYLOAD_SHA256`；**文件** SHA256 另记 `EXPECTED_FILE_SHA256`
  （实测与 ASR 侧 canonical clip **逐字节相同** ⇒ 跨模块同段）
* 起点判定依据：ASR-054 `asr137_make_10min_clip.py` 实测逐 10 s 窗 RMS/peak，
  首窗 rms=0.035654 / peak=0.351379 ⇒ 开头即语音 ⇒ 起点 = 0.0 s

## 纪律
* 只读素材、只写 `test_audio/`（gitignored）；不改任何默认值、不改判据阈值。
* `ensure_clip()` **幂等**：已存在且校验通过 ⇒ 直接复用；缺失 ⇒ 从源切；
  存在但内容不符 ⇒ **报错不覆盖**（不静默改判据）。
"""
from __future__ import annotations

import hashlib
import json
import os
import wave

#: App 仓库根
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
#: 全长 SPE 素材（**一直在本仓库** ⇒ §175 的"本机只有 300 s"是假前提）
SOURCE_WAV = os.path.join(REPO, 'test_audio', '260902_SPE_audio.wav')
#: canonical 10 分钟片段（本仓库内；gitignored）
CLIP_WAV = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')

#: APP-100 固定片段边界（秒）
START_S = 0.0
END_S = 600.0
TIMELINE_S = END_S - START_S      # 600.0 s 连续（**不循环**）

#: 起点不顺延的依据（实测 RMS/peak，见 ASR-054 asr137_make_10min_clip.py）
START_REASON = (
    '开头即语音（首 10 s 窗 rms=0.035654 / peak=0.351379，远高于静音判据）'
    '⇒ 起点取 0.0 s，不顺延')

#: 片段 payload（纯 PCM 数据，不含 wav 头）SHA256 —— **语义契约**
EXPECTED_PAYLOAD_SHA256 = (
    '2f02e4c0b172bd952e5ba20018eeaeeb91673c0e778fa85c4a6305edf62fd54e')
#: 片段**整个文件** SHA256（实测与 ASR 侧 canonical clip 逐字节相同）
EXPECTED_FILE_SHA256 = (
    'd412f00af6b792ce033d5d36c71f9c0a0efd1da19d0643107a56336e16f378d0')
#: ASR 侧 canonical clip（跨模块同段核对用）
ASR_CANONICAL_CLIP = (
    r'C:\Users\Trekker-PTL\qwen3asr_06b\dev\asr044_evalset'
    r'\clip_10min_0_600.wav')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def wav_payload_sha256(path):
    """只哈希 **PCM payload**（不含 44 B 头）⇒ 与 wav 写法无关的语义契约。"""
    with wave.open(path, 'rb') as w:
        payload = w.readframes(w.getnframes())
    return hashlib.sha256(payload).hexdigest()


def wav_info(path):
    with wave.open(path, 'rb') as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        bits = w.getsampwidth() * 8
        frames = w.getnframes()
    return {'sr': sr, 'channels': ch, 'bits': bits, 'frames': frames,
            'duration_s': round(frames / float(sr), 6)}


def source_payload_sha256_0_600():
    """从**全长源**现算前 600 s 的 payload SHA256（判据的独立复算路径）。"""
    with wave.open(SOURCE_WAV, 'rb') as w:
        sr = w.getframerate()
        payload = w.readframes(int(END_S * sr))
    return hashlib.sha256(payload).hexdigest()


def cut_clip(dst=CLIP_WAV):
    """从全长源切 [0.0, 600.0) s 写 dst。返回 dst 路径。"""
    with wave.open(SOURCE_WAV, 'rb') as r:
        sr, ch, sw = r.getframerate(), r.getnchannels(), r.getsampwidth()
        data = r.readframes(int(END_S * sr))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with wave.open(dst, 'wb') as w:
        w.setnchannels(ch)
        w.setsampwidth(sw)
        w.setframerate(sr)
        w.writeframes(data)
    return dst


def ensure_clip(dst=CLIP_WAV, repair=False):
    """保证 canonical 片段存在且内容正确。

    * 缺失 ⇒ 从全长源切（幂等）。
    * 存在但 payload SHA256 不符 ⇒ **报错**（`repair=False`），
      只有显式 `repair=True` 才覆盖（不静默改判据）。
    """
    if not os.path.isfile(SOURCE_WAV):
        raise FileNotFoundError('全长源缺失：%s' % SOURCE_WAV)
    if not os.path.isfile(dst):
        cut_clip(dst)
    payload_sha = wav_payload_sha256(dst)
    if payload_sha != EXPECTED_PAYLOAD_SHA256:
        if not repair:
            raise ValueError(
                'canonical 片段内容不符：payload_sha=%s != 期望 %s（拒绝静默覆盖）'
                % (payload_sha, EXPECTED_PAYLOAD_SHA256))
        cut_clip(dst)
        payload_sha = wav_payload_sha256(dst)
    return dst


def segment_meta(dst=CLIP_WAV):
    """返回**写进结果 json** 的片段元信息（APP-100：起止秒要写进脚本和结果 json）。"""
    info = wav_info(dst)
    meta = {
        'caliber': '10 分钟片段口径',
        'app100': True,
        'audio': dst,
        'source_wav': SOURCE_WAV,
        'source_duration_s': wav_info(SOURCE_WAV)['duration_s'],
        'start_s': START_S,
        'end_s': END_S,
        'loops': 1,
        'timeline_s': TIMELINE_S,
        'continuous': True,
        'start_reason': START_REASON,
        'duration_s': info['duration_s'],
        'sr': info['sr'],
        'channels': info['channels'],
        'bits': info['bits'],
        'payload_sha256': wav_payload_sha256(dst),
        'expected_payload_sha256': EXPECTED_PAYLOAD_SHA256,
        'file_sha256': sha256_file(dst),
        'expected_file_sha256': EXPECTED_FILE_SHA256,
        'bytes': os.path.getsize(dst),
    }
    return meta


def verify_segment(dst=CLIP_WAV):
    """行为级校验：返回 (ok, checks, meta)。**不是**正则匹配，是真读真算。"""
    checks = {}
    meta = {}
    ok = True

    def _ck(name, cond, detail=''):
        nonlocal ok
        checks[name] = bool(cond)
        if not cond:
            ok = False
        checks[name + '_detail'] = detail
        return bool(cond)

    try:
        ensure_clip(dst)
        _ck('clip_exists', True, dst)
    except Exception as e:
        _ck('clip_exists', False, repr(e))
        return False, checks, meta

    meta = segment_meta(dst)
    _ck('duration_600s', abs(meta['duration_s'] - 600.0) < 1e-3,
        'duration_s=%s' % meta['duration_s'])
    _ck('payload_sha_matches', meta['payload_sha256'] == EXPECTED_PAYLOAD_SHA256,
        'payload_sha=%s' % meta['payload_sha256'])
    _ck('file_sha_matches', meta['file_sha256'] == EXPECTED_FILE_SHA256,
        'file_sha=%s' % meta['file_sha256'])
    _ck('start_is_0_no_shift', meta['start_s'] == 0.0, 'start_s=%s' % meta['start_s'])
    _ck('end_is_600', meta['end_s'] == 600.0, 'end_s=%s' % meta['end_s'])
    _ck('loops_is_1_continuous', meta['loops'] == 1 and meta['continuous'],
        'loops=%s continuous=%s' % (meta['loops'], meta['continuous']))

    # 独立复算：从全长源现算前 600 s 的 payload SHA256
    try:
        recomputed = source_payload_sha256_0_600()
        _ck('recomputed_from_source', recomputed == EXPECTED_PAYLOAD_SHA256,
            'recomputed=%s' % recomputed)
    except Exception as e:
        _ck('recomputed_from_source', False, repr(e))

    # 跨模块同段：与 ASR 侧 canonical clip 逐字节相同
    if os.path.isfile(ASR_CANONICAL_CLIP):
        same = sha256_file(ASR_CANONICAL_CLIP) == meta['file_sha256']
        _ck('byte_identical_to_asr_canonical', same,
            'asr=%s' % sha256_file(ASR_CANONICAL_CLIP))
    else:
        _ck('byte_identical_to_asr_canonical', False,
            'ASR 侧 clip 缺失：%s' % ASR_CANONICAL_CLIP)

    return ok, checks, meta


if __name__ == '__main__':
    ok, checks, meta = verify_segment()
    print(json.dumps({'pass': ok, 'checks': checks, 'segment': meta},
                     ensure_ascii=False, indent=1))
    raise SystemExit(0 if ok else 1)
