#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §2：生成**模型生成的男声**参考音频 `preset_B.wav`。

来源（license 允许分发）：
  模型：Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice（Apache-2.0，HF cardData.license）
  下载：https://hf-mirror.com/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
  ���法：`model.generate_custom_voice(text=..., language='Chinese', speaker=...)`
  speaker：Uncle_Fu（中文男声·成熟沉稳）／Dylan（中文男声·北京口音）作备选
  🔴 **没有用任何真人素材**：不是录音、不是同事音色、不是克隆音色、不是 babelvox 样本。

输出规格（reviewer APP-116 §2）：
  24 kHz · 单声道 · 干净无噪 · 约 8–12 s

跑法（需 CUDA torch）：
    "C:/Users/Trekker-PTL/qwen3tts_eval/.venv-cuda/Scripts/python.exe" \
        live_caption/_app116_gen_preset_b.py
"""
import json
import os
import sys
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODEL_DIR = r'C:\Users\Trekker-PTL\qwen3tts_genai\preset_b_src\Qwen3-TTS-12Hz-0.6B-CustomVoice'
OUT_DIR = os.path.join(REPO, 'results', 'app', 'app116_preset_b_gen')
os.makedirs(OUT_DIR, exist_ok=True)

# 🔴 中性、无情绪、可长��朗读的中文文本（约 52 字 ≈ 11–13 s）
TEXT = ('你好，这是一段用于生成预设音色的参考音频。'
        '声音清晰平稳，没有背景噪音，语速适中，'
        '像平常说话一样朗读这段文字。')

SPEAKERS = [
    ('Uncle_Fu', '成熟男声（中文）'),
    ('Dylan', '青年男声（中文·北京口音）'),
]


def main():
    import torch
    import soundfile as sf
    import numpy as np
    from qwen_tts import Qwen3TTSModel

    # 🔴 设备选择：默认 CPU。
    #   理由：MACHINE_LOCK 可能被别的模块占着（跨模块不同时占设备）；
    #   本脚本只是**离线生成一个资产**（不是产品推理、也不是测速）
    #   ⇒ 不需要机器锁 ⇒ 用 CPU 更安全（不与他人抢 GPU）。
    #   传 `--cuda` 可改用 GPU（**必须先确认 MACHINE_LOCK 空闲**）。
    use_cuda = ('--cuda' in sys.argv)
    if use_cuda:
        dev, dtype = 'cuda:0', torch.bfloat16
    else:
        dev, dtype = 'cpu', torch.float32
    print('torch %s  cuda=%s  device=%s  dtype=%s'
          % (torch.__version__, torch.cuda.is_available(), dev, dtype),
          flush=True)
    t0 = time.time()
    model = Qwen3TTSModel.from_pretrained(
        MODEL_DIR, device_map=dev, dtype=dtype)
    print('模型加载完成 %.1f s' % (time.time() - t0), flush=True)

    report = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              'model': 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
              'license': 'apache-2.0',
              'source_url': 'https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
              'download_mirror': 'https://hf-mirror.com/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
              'method': 'generate_custom_voice(text, language="Chinese", speaker=...)',
              'text': TEXT,
              'no_human_material': True,
              'outputs': []}

    for spk, desc in SPEAKERS:
        print('\n--- 生成：%s（%s）' % (spk, desc), flush=True)
        t1 = time.time()
        try:
            wavs, sr = model.generate_custom_voice(
                text=TEXT, language='Chinese', speaker=spk)
        except Exception as e:
            print('  生成失败：%r' % (e,), flush=True)
            report['outputs'].append({'speaker': spk, 'ok': False,
                                      'error': repr(e)})
            continue
        dt = time.time() - t1
        w = np.asarray(wavs[0]).reshape(-1)
        path = os.path.join(OUT_DIR, 'preset_B_candidate_%s.wav' % spk)
        sf.write(path, w, sr, subtype='PCM_16')
        info = sf.info(path)
        peak = float(np.max(np.abs(w))) if w.size else 0.0
        rms = float(np.sqrt(np.mean(w.astype(np.float64) ** 2))) if w.size else 0.0
        clipped = int(np.sum(np.abs(w) >= 0.999))
        dur = len(w) / float(sr)
        rec = {'speaker': spk, 'desc': desc, 'ok': True, 'path': path,
               'sr': int(sr), 'channels': int(info.channels),
               'duration_s': round(dur, 3), 'bytes': os.path.getsize(path),
               'peak': round(peak, 5), 'rms': round(rms, 6),
               'rms_dbfs': round(20 * float(np.log10(rms + 1e-12)), 2),
               'n_clipped_samples': clipped, 'gen_s': round(dt, 1),
               'in_range_8_12s': 8.0 <= dur <= 12.0,
               'mono': int(info.channels) == 1,
               'sr_ok': int(sr) == 24000}
        report['outputs'].append(rec)
        print('  sr=%s ch=%s dur=%.2fs peak=%.4f rms=%.1f dBFS clip=%d  %.1fs'
              % (sr, info.channels, dur, peak, rec['rms_dbfs'], clipped, dt),
              flush=True)

    out = os.path.join(OUT_DIR, 'gen_report.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('\n报告：%s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
