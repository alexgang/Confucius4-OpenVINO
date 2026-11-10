#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app418_tts_worker.py —— **在包内 python 下**跑 TTS 合成，落 wav + json。

## 🔴 参数链（**与 `tts_worker._synth_babelvox` 逐项一致**）

APP-097 §2-3 明文要求的顺序：
`map_language` → `language_supported` → `split_long_text`
→ `clamp_max_new_tokens` → `estimate_sec` → `stream`

本文件**严格按此顺序**执行（注释标了行号对照）⇒ 与 App 真实链路同口径。

## 🔴 纪律
* 用**包内 python** 跑 ⇒ `import tts_engine` 命中**包内**代码（真包代码）。
* 音色 = **预设 A**（MiniMVP 无克隆 ⇒ `speaker_embed` 取自包内
  `models/qwen3tts/voices/preset_A.wav`）。
* **不调 MiniMax**。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import wave


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--lang', required=True)
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--out', required=True)
    ap.add_argument('--texts', required=True)
    a = ap.parse_args()

    PKG = os.path.abspath(a.pkg)
    sys.path.insert(0, os.path.join(PKG, 'app'))

    import numpy as np
    import tts_engine as TE

    texts = json.loads(a.texts)
    outdir = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(outdir, exist_ok=True)

    log_lines = []

    def log(msg):
        line = str(msg)
        log_lines.append(line)
        try:
            print(line, flush=True)
        except Exception:
            pass

    # ── 引擎 ──────────────────────────────────────────────────────
    eng = TE.make_engine(device=a.device, on_log=log)
    # 🔴 音色：预设 A（包内 voices/preset_A.wav）
    ref = TE.preset_voice_path()
    log('预设音色路径：%s' % ref)
    spk_embed = TE.speaker_embedding(eng, ref_wav=ref, on_log=log)

    wavs = []
    end_reasons = []
    for i, text in enumerate(texts):
        # ① map_language（唯一映射表）
        blang = TE.map_language(a.lang)
        # ② language_supported（已知但不支持 ⇒ 告警，不静默回落）
        if not TE.language_supported(blang):
            log('🔴 目标语言 %r → %r 不在引擎支持列表' % (a.lang, blang))
        # ③ 中文数字正则化（只在 Chinese 时；与 worker 同一口径）
        if blang == 'Chinese':
            text = TE.normalize_zh_numbers(text)
        # ④ 长句切分（保守上限 478 帧）
        parts = TE.split_long_text(text)
        for j, p in enumerate(parts):
            # ⑤ 按段算帧数上限
            _mnt = TE.clamp_max_new_tokens(p, a.lang)
            # ⑥ 预计音频秒数（第二道闸的输入）
            _est = TE.estimate_sec(p, a.lang)
            buf = []
            sr_out = 24000
            # ⑦ 流式合成
            for wav_chunk, sr in TE.stream(
                    eng, p, language=blang,
                    speaker_embed=spk_embed,
                    speaker=None,
                    cancel_event=None,
                    max_new_tokens=_mnt,
                    est_sec=_est,
                    on_log=log):
                buf.append(np.asarray(wav_chunk, dtype=np.float32).reshape(-1))
                sr_out = int(sr)
            try:
                _er = getattr(eng, '_last_end_reason', None)
            except Exception:
                _er = None
            end_reasons.append(_er)
            if not buf:
                log('🔴 段 %d/%d 无音频' % (i, j))
                continue
            w = np.concatenate(buf)
            path = os.path.join(outdir, '%s_%02d_%02d.wav' % (a.lang, i, j))
            with wave.open(path, 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(sr_out)
                pcm = np.clip(w * 32767.0, -32768, 32767).astype(np.int16)
                f.writeframes(pcm.tobytes())
            wavs.append({'path': path, 'sr': sr_out,
                          'samples': int(len(w)),
                          'dur_s': round(len(w) / sr_out, 3),
                          'text': p, 'end_reason': _er})
            log('落盘：%s（%.2f s，end_reason=%s）'
                % (os.path.basename(path), len(w) / sr_out, _er))

    json.dump({'lang': a.lang, 'device': a.device, 'wavs': wavs,
               'end_reasons': end_reasons,
               'log_tail': log_lines[-40:]},
              open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('OK wavs=%d' % len(wavs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
