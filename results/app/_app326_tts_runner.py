#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app326_tts_runner.py —— **APP-097 §2-3 / §2-4 TTS 逐语种**（包内 python）。

🔴 口径：**完全照抄 `tts_worker._synth_babelvox()` 的参数链**
（`map_language` → `language_supported` → `normalize_zh_numbers`(仅 Chinese)
→ `split_long_text` → `clamp_max_new_tokens` → `estimate_sec` → `stream`)
⇒ 跑的是**真实代码路径**。

🔴 **两种音色各一遍**（reviewer §2-3）：
  * `preset` ＝ 预设 A（`models/qwen3tts/voices/preset_A.wav` → x-vector）
  * `clone`  ＝ 克隆音色（**x-vector**：从 `dialog3_tight.wav` 切一段真人声
    → `tts_engine.speaker_embedding()`）⇒ 与 App 运行时**同一口径**。

🔴 **「撞帧上限次数」的字段来源**（reviewer 要求写明）：
  * `end_reason == 'cap'`（**引擎回报**）⇒ 撞生成帧数上限（被截断）
  * 另报 `max_new_tokens`（**传给引擎的帧数上限**）与 `est_frames`（**估计帧数**）
  * `frames` 字段在 App 的 jsonl 里恒为空 ⇒ 本脚本**自己数输出帧数**
    （`n_samples / (sr/12)`，12 fps）⇒ 记作 `frames_out`
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--app', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--mt', required=True)
    ap.add_argument('--langs', required=True)
    ap.add_argument('--wav-dir', required=True)
    ap.add_argument('--clone-ref', required=True)
    ap.add_argument('--jsonl', default=None,
                    help='🔴 增量落盘路径（每句一行）⇒ 父进程被杀也不丢已跑结果')
    args = ap.parse_args()

    sys.path.insert(0, args.app)
    os.chdir(args.app)

    import numpy as np
    import tts_engine as TE

    mt = json.load(open(args.mt, encoding='utf-8'))
    langs = [x for x in args.langs.split(',') if x]
    os.makedirs(args.wav_dir, exist_ok=True)

    out = {'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'app': args.app, 'langs': langs, 'per_lang': {},
           'device': 'NPU', 'precision': 'f16',
           'end_reason_field': "engine._last_end_reason（'eos'/'cap'/'runaway'）",
           'frames_out_formula': 'n_samples / (sr/12)（12 fps）',
           'notes': []}

    # ══ 引擎（一次加载，NPU，f16）══
    print('[tts] 加载引擎…', flush=True)
    eng = TE.make_engine(device='NPU', precision='f16',
                         on_log=lambda *a, **k: print('[tts]', *a, flush=True))
    out['exec_devices'] = TE.execution_devices(eng, on_log=lambda *a, **k: None)
    print('[tts] EXECUTION_DEVICES=%s' % json.dumps(out['exec_devices'])[:300],
          flush=True)

    # ══ 两种音色的 x-vector ══
    preset_wav = TE.preset_voice_path()
    out['preset_wav'] = preset_wav
    preset_emb = TE.speaker_embedding(eng, preset_wav,
                                      on_log=lambda *a, **k: print('[tts]', *a, flush=True))
    out['preset_embed_shape'] = list(preset_emb.shape) if preset_emb is not None else None

    # 🔴 克隆音色：从 `dialog3_tight.wav` 切 5.63 s（truth 的第一段 A）
    clone_wav = os.path.join(args.wav_dir, '_clone_ref_A.wav')
    _cut_wav(args.clone_ref, clone_wav, 0.0, 5.63)
    clone_emb = TE.speaker_embedding(eng, clone_wav,
                                     on_log=lambda *a, **k: print('[tts]', *a, flush=True))
    out['clone_ref_wav'] = clone_wav
    out['clone_embed_shape'] = list(clone_emb.shape) if clone_emb is not None else None

    if preset_emb is None or clone_emb is None:
        out['notes'].append('🔴 音色向量缺失 ⇒ 本臂无效')

    # ══ 逐语种合成 ══
    # 🔴🔴 增量落盘：每句写一行 jsonl ⇒ 父进程被杀**不丢已跑结果**
    jf = None
    if args.jsonl:
        jf = open(args.jsonl, 'w', encoding='utf-8')

    for lang in langs:
        # 取该语种的**英文源句译文**（§2-3：「用上一步的译文」）
        rows_mt = [r for r in mt['rows']
                   if r['tgt'] == lang and r['src_label'] == 'en'
                   and not r['empty'] and not r['error']]
        per = {}
        for voice, emb in (('preset', preset_emb), ('clone', clone_emb)):
            recs = []
            t_all = time.perf_counter()
            for i, r in enumerate(rows_mt):
                text = r['out']
                blang = TE.map_language(lang)
                supported = TE.language_supported(blang)
                t2 = text
                if blang == 'Chinese':
                    t2 = TE.normalize_zh_numbers(text)
                parts = TE.split_long_text(t2)
                n_chunks = 0
                samples = []
                sr = 24000
                end_reason = None
                mnt = None
                t0 = time.perf_counter()
                for p in parts:
                    mnt = TE.clamp_max_new_tokens(p, lang)
                    est = TE.estimate_sec(p, lang)
                    for wav_chunk, s2 in TE.stream(
                            eng, p, language=blang,
                            speaker_embed=emb,
                            speaker=None if emb is not None else 'A',
                            max_new_tokens=mnt, est_sec=est):
                        samples.append(np.asarray(wav_chunk, dtype=np.float32).reshape(-1))
                        sr = int(s2)
                        n_chunks += 1
                    er = getattr(eng, '_last_end_reason', None)
                    if er:
                        end_reason = er
                wall = time.perf_counter() - t0
                arr = (np.concatenate(samples) if samples
                       else np.zeros(0, dtype=np.float32))
                dur = len(arr) / float(sr) if sr else 0.0
                wav_path = os.path.join(args.wav_dir,
                                        '%s_%s_%02d.wav' % (lang, voice, i))
                if len(arr):
                    _write_wav(wav_path, arr, sr)
                frames_out = int(len(arr) / (sr / 12.0)) if sr else 0
                rec = {
                    'lang': lang,
                    'voice': voice,
                    'i': i,
                    'src': r['src'],
                    'text': text,
                    'n_chars': len([c for c in text if not c.isspace()]),
                    'src_dur_s': r.get('src_dur_s'),   # 🔴 英文源段时长（MT 侧带下来）
                    'out_dur_s': round(dur, 4),
                    'wall_s': round(wall, 4),
                    'synth_rtf': (round(wall / dur, 4) if dur > 0 else None),
                    'end_reason': end_reason,
                    'hit_frame_cap': (end_reason == 'cap'),
                    'max_new_tokens': mnt,
                    'est_frames': TE.estimate_frames(text, lang),
                    'frames_out': frames_out,
                    'n_chunks': n_chunks,
                    'n_parts': len(parts),
                    'wav': wav_path,
                    'language_supported': supported,
                    'blang': blang,
                }
                recs.append(rec)
                if jf:
                    jf.write(json.dumps(rec, ensure_ascii=False) + '\n')
                    jf.flush()
                    os.fsync(jf.fileno())
                print('[tts] %s/%s #%d dur=%.2f rtf=%s er=%s'
                      % (lang, voice, i, dur,
                         rec['synth_rtf'], end_reason), flush=True)
            wall_all = time.perf_counter() - t_all
            rtfs = [x['synth_rtf'] for x in recs
                    if isinstance(x.get('synth_rtf'), (int, float))]
            ers = {}
            for x in recs:
                ers[str(x.get('end_reason'))] = ers.get(str(x.get('end_reason')), 0) + 1
            per[voice] = {
                'n': len(recs),
                'rows': recs,
                'wall_total_s': round(wall_all, 2),
                'rtf_p50': (round(sorted(rtfs)[len(rtfs) // 2], 4) if rtfs else None),
                'rtf_p95': (round(sorted(rtfs)[int(0.95 * (len(rtfs) - 1))], 4)
                            if rtfs else None),
                'n_hit_frame_cap': sum(1 for x in recs if x['hit_frame_cap']),
                'end_reason_dist': ers,
            }
        out['per_lang'][lang] = per
        print('[tts] %s 完成：preset rtf_p50=%s cap=%s ｜ clone rtf_p50=%s cap=%s'
              % (lang, per['preset']['rtf_p50'], per['preset']['n_hit_frame_cap'],
                 per['clone']['rtf_p50'], per['clone']['n_hit_frame_cap']), flush=True)

    if jf:
        jf.close()
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[tts] wrote %s' % args.out, flush=True)
    return 0


def _cut_wav(src, dst, t0, t1):
    w = wave.open(src, 'rb')
    try:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    finally:
        w.close()
    a = int(t0 * sr)
    b = int(t1 * sr)
    seg = raw[a * 2:b * 2]
    o = wave.open(dst, 'wb')
    try:
        o.setnchannels(1)
        o.setsampwidth(2)
        o.setframerate(sr)
        o.writeframes(seg)
    finally:
        o.close()
    return dst


def _write_wav(path, samples, sr):
    # 🔴🔴 `np` 必须在**函数内**取（`import numpy as np` 只在 `main()` 里）
    #    ⇒ 上一版报 `NameError: name 'np' is not defined`（TTS 首句就崩）
    import numpy as np
    a = np.asarray(samples, dtype=np.float32).reshape(-1)
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype('<i2')
    w = wave.open(path, 'wb')
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())
    finally:
        w.close()


if __name__ == '__main__':
    raise SystemExit(main())
