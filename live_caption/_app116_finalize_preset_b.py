#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §2：把生成的候选男声**裁成合规的参考音频** `preset_B.wav`。

reviewer 规格：24 kHz · 单声道 · 干净无噪 · 约 8–12 s。

处理：
  ① 去**首尾静音**（帧级 RMS 阈值）
  ② 裁到 **10.0 s**（落在 8–12 s 区间中位）
  ③ 峰值归一到 **−3 dBFS**（0.70795），不改变音色，只统一响度
  ④ 输出 PCM_16 单声道 24 kHz
  ⑤ 逐项校验（采样率/声道/时长/削波/直流偏置）⇒ 落盘 manifest

来源（license 允许分发）：
  模型：Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice（Apache-2.0）
  speaker：Uncle_Fu（中文男声·成熟沉稳）
  🔴 **没有任何真人素材**：不是录音 / 同事音色 / 克隆音色 / babelvox 样本。
"""
import hashlib
import json
import os
import sys
import datetime

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GEN = os.path.join(REPO, 'results', 'app', 'app116_preset_b_gen')
CAND = os.path.join(GEN, 'preset_B_candidate_Uncle_Fu.wav')
# dev 树里引擎找参考音频的位置（`model_root()/voices/`）
DEV_VOICES = os.path.join(REPO, 'models', 'qwen3tts', 'voices')
# 客户包里的参考音频（用于**基准**与将来的随包分发）
PKG_VOICES = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4\models\qwen3tts\voices'

TARGET_SR = 24000
TARGET_CH = 1
TARGET_DUR = 10.0
PEAK_DBFS = -3.0
SILENCE_DBFS = -45.0


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def trim_silence(w, sr):
    """返回 (去掉首尾静音后的波形, 起始秒数)。"""
    frame = int(sr * 0.02)
    n = (len(w) // frame) * frame
    if n == 0:
        return w, 0.0
    frames = w[:n].reshape(-1, frame)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1)) + 1e-12
    thr = 10 ** (SILENCE_DBFS / 20.0)
    loud = np.where(rms > thr)[0]
    if loud.size == 0:
        return w, 0.0
    a = int(loud[0]) * frame
    b = int(loud[-1] + 1) * frame
    return w[a:b], a / float(sr)


def main():
    os.makedirs(DEV_VOICES, exist_ok=True)
    w, sr = sf.read(CAND, always_2d=False)
    if w.ndim > 1:
        w = w[:, 0]
    src_dur = len(w) / float(sr)
    w2, onset = trim_silence(w, sr)
    dur2 = len(w2) / float(sr)
    need = int(TARGET_DUR * sr)
    if len(w2) < need:
        raise SystemExit('去静音后不足 %.1f s（只有 %.2f s）' % (TARGET_DUR, dur2))
    # 取**前** 10 s（语音刚起、状态最稳；末尾合成尾音有渐弱）
    out = w2[:need].astype(np.float64)
    peak = float(np.max(np.abs(out)))
    if peak > 0:
        out = out * ((10 ** (PEAK_DBFS / 20.0)) / peak)
    # 🔴 直流偏置去除（干净无噪的一步）
    out = out - float(np.mean(out))
    # 🔴 边界淡入淡出 10 ms（去掉可能的咔哒声）
    fade = int(sr * 0.01)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade)
        out[:fade] *= ramp
        out[-fade:] *= ramp[::-1]

    dst = os.path.join(DEV_VOICES, 'preset_B.wav')
    sf.write(dst, out.astype(np.float32), TARGET_SR, subtype='PCM_16')

    info = sf.info(dst)
    rd, _ = sf.read(dst, always_2d=False)
    rms = float(np.sqrt(np.mean(rd.astype(np.float64) ** 2)))
    checks = {
        'sample_rate_24k': bool(info.samplerate == TARGET_SR),
        'mono': bool(info.channels == TARGET_CH),
        'duration_8_to_12s': bool(8.0 <= (len(rd) / info.samplerate) <= 12.0),
        'no_clipping': bool(float(np.max(np.abs(rd))) < 0.999),
        'not_silent': bool(rms > 10 ** (-40 / 20.0)),
        'dc_offset_small': bool(abs(float(np.mean(rd))) < 1e-3),
        'peak_normalized': bool(abs(20 * np.log10(float(np.max(np.abs(rd))) + 1e-12)
                                      - PEAK_DBFS) < 1.0),
    }
    man = {
        'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'asset': 'preset_B.wav（预设 B · 男声）',
        'source_model': 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
        'source_license': 'apache-2.0',
        'source_url': 'https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
        'download_mirror': 'https://hf-mirror.com/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
        'method': 'model.generate_custom_voice(text=..., language="Chinese", speaker="Uncle_Fu")',
        'speaker': 'Uncle_Fu（Seasoned male voice, mellow timbre）',
        'source_text': ('你好，这是一段用于生成预设音色的参考音频。'
                        '声音清晰平稳，没有背景噪音，语速适中，'
                        '像平常说话一样朗读这段文字。'),
        'no_human_material': True,
        'candidate': {'path': CAND, 'sha256': sha256(CAND),
                      'duration_s': round(src_dur, 3)},
        'processing': {
            'trim_silence': '首尾静音（帧 RMS < %d dBFS 视为静音）' % SILENCE_DBFS,
            'onset_s': round(onset, 3),
            'trimmed_to_s': TARGET_DUR,
            'peak_normalized_dbfs': PEAK_DBFS,
            'dc_offset_removed': True,
            'fade_ms': 10,
            'container': 'PCM_16',
        },
        'output': {'path': dst, 'sha256': sha256(dst),
                   'bytes': os.path.getsize(dst),
                   'sample_rate': info.samplerate, 'channels': info.channels,
                   'duration_s': round(len(rd) / info.samplerate, 3),
                   'peak': round(float(np.max(np.abs(rd))), 5),
                   'rms_dbfs': round(20 * np.log10(rms + 1e-12), 2)},
        'checks': checks,
        'all_checks_pass': all(checks.values()),
        'not_packaged_yet': True,
        'not_packaged_reason': ('reviewer APP-116 §2 明文：「**用户点头前不进包**」'
                                 '⇒ 抽听通过前，客户包里**不含** preset_B.wav；'
                                 '⇒ 客户机上的音色下拉也**不会**列出「预设 B（男声）」。'),
    }
    out_json = os.path.join(GEN, 'preset_B_manifest.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=2)

    # 供开发树自测用：把包的 preset_A.wav 也放进 dev 的 voices 目录
    # （models/ 已被 .gitignore 忽略 ⇒ 不会进仓库）
    a_src = os.path.join(PKG_VOICES, 'preset_A.wav')
    a_dst = os.path.join(DEV_VOICES, 'preset_A.wav')
    if os.path.isfile(a_src) and not os.path.exists(a_dst):
        import shutil
        shutil.copyfile(a_src, a_dst)
        man['dev_preset_A_copied'] = {
            'src': a_src, 'dst': a_dst, 'sha256': sha256(a_dst),
            'bytes': os.path.getsize(a_dst)}
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(man, f, ensure_ascii=False, indent=2)

    print('=== APP-116 §2 preset_B.wav 定稿 ===')
    print('  源候选 : %s（%.2f s）' % (os.path.basename(CAND), src_dur))
    print('  去静音起点: %.3f s' % onset)
    print('  输出   : %s' % dst)
    print('  规格   : %d Hz / %d ch / %.3f s / peak %.4f / rms %.1f dBFS'
          % (info.samplerate, info.channels, len(rd) / info.samplerate,
             float(np.max(np.abs(rd))), man['output']['rms_dbfs']))
    print('  SHA256 : %s' % man['output']['sha256'])
    for k, v in checks.items():
        print('  [%s] %s' % ('PASS' if v else 'FAIL', k))
    print('  manifest: %s' % out_json)
    return 0 if man['all_checks_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
