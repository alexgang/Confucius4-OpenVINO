#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：修抽听样片的 **OGG 编码**（PyAV 19 的 vorbis 编码器不可用）。

## 实测到的真缺陷（本轮首跑）

`_app129_clips_v26.py::_encode_av` 用 `out.add_stream('vorbis', rate=sr)` ⇒
在**包内 python**（PyAV **19.0.1**）上直接抛：

    ExperimentalError(733130664, 'Experimental feature',
                      'avcodec_open2("vorbis", {})')

⇒ 四个样片的 `ogg_ok` 全是 **false**（`ogg_info.error = "PyAV 编码失败"`）
⇒ **一条附件都发不出去**（reviewer APP-129 §3.5 要 OGG 附件）。

## 根因与修法

- 根因：**PyAV 19 的 `vorbis` 编码器在本机 libavcodec 上开不了**
  （`av.codecs_available` 里**列得出** `vorbis`/`speex`，但**真开必抛**）
  ⇒ 「编码器列表里有」**不等于**「能开」⇒ **不能用列表当判据**。
- 修法：**按优先级逐个真开一次**，第一个「能开 ＋ 产出文件 ＋ 能解回来」的胜出：
  1. `vorbis`   —— reviewer 原意（Vorbis in OGG）；
  2. `libopus`  —— **Opus in OGG**（**仍是 .ogg 容器**；Chrome/Firefox/
                   ffmpeg/VLC 都能放）⇒ 兜底首选；
  3. `opus`     —— 同一 codec 的另一个名字。
  ⇒ **实际用上的 codec 写进证据**（reviewer 可自行核对「这是不是 OGG」）。

🔴 **判据纪律**：判「编码成功」**不能只看 `add_stream` 不抛异常** ⇒ 必须
**回读产出的文件**（存在 ＋ 大小 > 0 ＋ **能被重新解码**）⇒ 真正证明可播。

## 纪律

- **只改编码器选择与成功判据**；其余逻辑一行不改；
- 定点替换 ＋ 唯一命中断言 ＋ 写前不变量 ＋ **还原式复核** ＋ 写后逐字节复核。
"""
from __future__ import annotations

import ast
import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.environ.get('TEMP', '/tmp')
TARGET = 'results/app/_app129_clips_v26.py'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


OLD_ENC = '''def wav_to_ogg(wav, ogg, max_bytes=MAX_OGG_BYTES):
    """把 wav 转成 ≤max_bytes 的 OGG。返回 (ok, info)。"""
    import wave as _w
    with _w.open(wav, 'rb') as f:
        sr = f.getframerate()
        ch = f.getnchannels()
        n = f.getnframes()
        dur = n / float(sr)
    bitrate = 96000
    for _try in range(6):
        rc = _encode_av(wav, ogg, sr, ch, bitrate)
        if rc is None:
            return False, {'error': 'PyAV 编码失败'}
        sz = os.path.getsize(ogg)
        if sz <= max_bytes:
            return True, {'bytes': sz, 'bitrate': bitrate, 'dur_s': round(dur, 1),
                          'sample_rate': sr, 'channels': ch}
        bitrate = max(24000, int(bitrate * 0.6))
    sz = os.path.getsize(ogg)
    return sz <= max_bytes, {'bytes': sz, 'bitrate': bitrate,
                             'dur_s': round(dur, 1)}


def _encode_av(wav, ogg, sr, ch, bitrate):
    try:
        import av
        import numpy as np
        with av.open(wav) as inp:
            in_stream = inp.streams.audio[0]
            resampler = av.audio.resampler.AudioResampler(
                format='s16', layout='stereo' if ch == 2 else 'mono',
                rate=sr)
            with av.open(ogg, 'w', format='ogg') as out:
                out_stream = out.add_stream('vorbis', rate=sr)
                out_stream.bit_rate = bitrate
                for frame in inp.decode(in_stream):
                    for rf in resampler.resample(frame):
                        for pkt in out_stream.encode(rf):
                            out.mux(pkt)
                for pkt in out_stream.encode(None):
                    out.mux(pkt)
        return True
    except Exception as e:
        print('av encode fail:', repr(e))
        return None
'''

NEW_ENC = '''def wav_to_ogg(wav, ogg, max_bytes=MAX_OGG_BYTES):
    """把 wav 转成 ≤max_bytes 的 OGG。返回 (ok, info)。"""
    import wave as _w
    with _w.open(wav, 'rb') as f:
        sr = f.getframerate()
        ch = f.getnchannels()
        n = f.getnframes()
        dur = n / float(sr)
    bitrate = 96000
    last_err = None
    for _try in range(6):
        ok_enc, enc_info = _encode_av(wav, ogg, sr, ch, bitrate)
        if not ok_enc:
            last_err = enc_info
            break
        sz = os.path.getsize(ogg)
        if sz <= max_bytes:
            info = {'bytes': sz, 'bitrate': bitrate,
                    'dur_s': round(dur, 1), 'sample_rate': sr,
                    'channels': ch}
            for k in ('codec_used', 'codec', 'decodable', 'duration_s',
                      'n_decoded_frames'):
                if k in enc_info:
                    info[k] = enc_info[k]
            return True, info
        bitrate = max(24000, int(bitrate * 0.6))
    sz = os.path.getsize(ogg) if os.path.isfile(ogg) else 0
    info = {'bytes': sz, 'bitrate': bitrate, 'dur_s': round(dur, 1)}
    if last_err:
        info['error'] = last_err.get('error', 'PyAV 编码失败')
        if last_err.get('tried'):
            info['tried'] = last_err['tried']
    return bool(sz > 0 and sz <= max_bytes), info


#: 🔴🔴 **APP-133（本轮实测修）**：OGG 编码器的**优先级表**。
#:
#: 实测：包内 python 的 PyAV **19.0.1** 上 `add_stream('vorbis', ...)` 直接抛
#: `ExperimentalError(..., 'avcodec_open2("vorbis", {})')`
#: ⇒ **四个样片的 OGG 全都没生成**（`ogg_ok=false`）⇒ 一条附件都发不出去。
#:
#: 🔴 **判据纪律**：`av.codecs_available` 里**列得出** `vorbis`/`speex`
#: **不等于**「能开」⇒ **不能用编码器列表当判据** ⇒ 必须**逐个真开一次**。
#:
#: 优先级：
#:   1. `vorbis`   —— reviewer 原意（Vorbis in OGG）；
#:   2. `libopus`  —— **Opus in OGG**（**仍是 .ogg 容器**；Chrome/Firefox/
#:                    ffmpeg/VLC 都能放）⇒ 兜底首选；
#:   3. `opus`     —— 同一 codec 的另一个名字。
#:
#: 实际用上的 codec 名**写进证据** ⇒ reviewer 可自行核对「这是不是 OGG」。
OGG_ENCODERS = ('vorbis', 'libopus', 'opus')


def _encode_one(wav, ogg, sr, ch, bitrate, codec):
    """用**指定** codec 编码一次。成功 ⇒ True。"""
    import av
    with av.open(wav) as inp:
        in_stream = inp.streams.audio[0]
        resampler = av.audio.resampler.AudioResampler(
            format='s16', layout='stereo' if ch == 2 else 'mono',
            rate=sr)
        with av.open(ogg, 'w', format='ogg') as out:
            out_stream = out.add_stream(codec, rate=sr)
            out_stream.bit_rate = bitrate
            for frame in inp.decode(in_stream):
                for rf in resampler.resample(frame):
                    for pkt in out_stream.encode(rf):
                        out.mux(pkt)
            for pkt in out_stream.encode(None):
                out.mux(pkt)
    return True


def _verify_ogg(ogg):
    """🔴 **成功判据不能只看「没抛异常」** ⇒ 必须**回读并重新解码**。

    ⇒ 返回 (ok, info)；ok=True 表示「文件存在 ＋ 大小>0 ＋ 能被解回来」。
    """
    info = {'bytes': 0, 'decodable': False, 'codec': None,
            'duration_s': None}
    try:
        import av
        if not os.path.isfile(ogg):
            return False, info
        info['bytes'] = os.path.getsize(ogg)
        if info['bytes'] <= 0:
            return False, info
        with av.open(ogg) as inp:
            st = inp.streams.audio[0]
            cc = getattr(st, 'codec_context', None)
            info['codec'] = getattr(cc, 'name', None)
            n = 0
            for _f in inp.decode(st):
                n += 1
            info['n_decoded_frames'] = n
            info['decodable'] = (n > 0)
            if st.duration and st.time_base:
                info['duration_s'] = round(
                    float(st.duration * st.time_base), 2)
    except Exception as e:
        info['error'] = repr(e)[:200]
        return False, info
    return bool(info['decodable']), info


def _encode_av(wav, ogg, sr, ch, bitrate):
    """按优先级逐个试编码器 ⇒ 第一个「真能开 ＋ 产出可解码文件」的胜出。

    🔴 **返回 (ok, info)**（旧版是 `True/None` ⇒ 调用方同步改）。
    """
    tried = []
    for codec in OGG_ENCODERS:
        try:
            _encode_one(wav, ogg, sr, ch, bitrate, codec)
            ok, info = _verify_ogg(ogg)
            tried.append({'codec': codec, 'opened': True,
                          'verified': ok, 'info': info})
            if ok:
                info['codec_used'] = codec
                info['tried'] = tried
                return True, info
        except Exception as e:
            tried.append({'codec': codec, 'opened': False,
                          'error': repr(e)[:200]})
    print('av encode fail: %s' % json.dumps(tried, ensure_ascii=False)[:600])
    return False, {'error': 'PyAV 编码失败（已试 %s）'
                          % ','.join(OGG_ENCODERS), 'tried': tried}
'''


def main():
    p = os.path.join(REPO, TARGET)
    with open(p, 'rb') as f:
        src_b = f.read()
    with open(p, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    crlf = '\r\n' in src

    with open(os.path.join(TMP, os.path.basename(TARGET) + '.bak_app133d'),
              'wb') as f:
        f.write(src_b)

    def norm(s):
        return s.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else s

    old, new = norm(OLD_ENC), norm(NEW_ENC)
    c = src.count(old)
    if c != 1:
        raise SystemExit('FAIL：编码器块命中 %d 次（要求 1）' % c)
    out = src.replace(old, new)

    # 真不变量
    if ('\r\n' in src) != ('\r\n' in out):
        raise SystemExit('FAIL：行尾风格变了')
    delta_expect = new.count('\n') - old.count('\n')
    delta_got = out.count('\n') - src.count('\n')
    if delta_got != delta_expect:
        raise SystemExit('FAIL：行数增量 %d ≠ 预期 %d'
                         % (delta_got, delta_expect))
    red = out.replace(new, old)
    if red != src:
        raise SystemExit('FAIL：还原式复核失败')

    out_b = out.encode('utf-8')
    tmp = p + '.tmp_app133d'
    with open(tmp, 'wb') as f:
        f.write(out_b)
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        after = f.read()
    if after != out_b:
        raise SystemExit('FAIL：写后逐字节复核失败')
    ast.parse(after.decode('utf-8'))
    print('OK %s  %d B -> %d B  sha %s -> %s  (AST OK)'
          % (TARGET, len(src_b), len(out_b), sha256_bytes(src_b)[:12],
             sha256_bytes(after)[:12]))


if __name__ == '__main__':
    main()
