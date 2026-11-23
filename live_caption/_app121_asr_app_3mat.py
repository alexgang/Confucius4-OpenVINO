#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §2：**用 App 的后端**跑 §86 三素材（SPE / EN / ZH），报 transcript md5 与
`prefix_truncations`。

## reviewer 原文（APP-121 §2）
> 请在 STATUS 里撤回这两句。
> 修完第 1 条后补一组：**用 App 的后端（`StreamingEngine` 加
> `ASR06BStatefulBackend`）跑 §86 的三段素材**，NPU 和 GPU.0 各一次，
> 报 transcript md5 和 prefix_truncations。
> NPU 和参照不一致的话，要逐段解释原因（比如截断口径、切段器不同），
> 不要求硬凑一致。

## 本脚本做什么（与 `_app120_asr_3mat.py` 的**关键差别**）
🔴 `_app120_asr_3mat.py` 走的是 **ASR 模块**的 `bk_run.run_stream` ＋
   `asr065_backend.Asr065Runner` ⇒ **没有经过 App 的代码**。
🔴 **本脚本走 App 的真实调用路径**：包内 `app/live_caption_app.py` 的
   **`OVEngine`**（= `StreamingEngine` 包装 + `ASR06BStatefulBackend`）
   ⇒ 段尾定稿走 App 的 `_finalize()`（`reserve=64`），
   流式块走 App 的 `_st()`（`max_new_tokens=32`），
   **切段走 App 自己的 `Segmenter`** ⇒ 与 ASR 模块的切段器**不同**
   ⇒ 转写**可能**与参照不同（reviewer 明确：不要求硬凑一致）。

## 纪律
- **用包内 python**（OV 2.4.1，与 §86 参照同版本 ⇒ handoff §七口径要求）；
- **用包内的模型 IR + 包内的 embed 表**；
- **全程持 MACHINE_LOCK**（`machine_lock_app`，锁被抢 ⇒ timing_valid=false）；
- transcript 落盘为**与参照同格式**（`[%8.1f-%8.1f] text`）⇒ md5 可直接比对。

## 用法
```
<包内 python> live_caption/_app121_asr_app_3mat.py --pkg <v1.1.1> --device NPU
<包内 python> live_caption/_app121_asr_app_3mat.py --pkg <v1.1.1> --device GPU.0
```
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
import wave

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1.1')
ASR_WORK = os.path.join(HOME, 'qwen3asr_06b')
KIT_ASSETS = os.path.join(ASR_WORK, 'b_kit_stateful', 'assets')
RESULTS = os.path.join(REPO, 'results', 'app')
TMP = os.path.join(HOME, 'AppData', 'Local', 'Temp', 'app121')

SR = 16000
CHUNK_SEC = 0.64

#: §86 参照 md5（ASR-062/063 base 臂；ASR-065 §七 验收表同值）
REF_MD5 = {
    'spe': 'cd67417e64ae6009c0b703453f7c5316',
    'en': 'ed3f52aaf1415ca01d785da4e3a78cb4',
    'zh': 'd93062a686fc1e647b34f4a813bad01d',
}
REF_DIR = os.path.join(ASR_WORK, 'results', 'asr165_ov241', 'normal')

#: (标签, 语种, 素材 wav, 参照 transcript)
MATS = [
    ('spe', 'en', os.path.join(KIT_ASSETS, 'clip_10min_0_600.wav'),
     os.path.join(REF_DIR, 'spe_en', 'transcript.txt')),
    ('en', 'en', os.path.join(HOME, '_reviewer_tmp', 'bench', 'data',
                              'asr_en.wav'),
     os.path.join(REF_DIR, 'fleurs_en', 'transcript.txt')),
    ('zh', 'zh', os.path.join(HOME, '_reviewer_tmp', 'bench', 'data',
                              'asr_zh.wav'),
     os.path.join(REF_DIR, 'fleurs_zh', 'transcript.txt')),
]


def log(*a):
    print(*a, flush=True)


def md5_of(path):
    h = hashlib.md5()
    with io.open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_wav_i16(path):
    with wave.open(path, 'rb') as w:
        assert w.getframerate() == SR, '采样率 %d != %d' % (w.getframerate(), SR)
        assert w.getnchannels() == 1, '声道 %d != 1' % w.getnchannels()
        assert w.getsampwidth() == 2, '位宽 %d != 2' % w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    import numpy as np
    return np.frombuffer(raw, dtype='<i2')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--device', required=True, choices=('NPU', 'GPU.0'))
    ap.add_argument('--out-dir', default='')
    ap.add_argument('--json', default='')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    app_dir = os.path.join(pkg, 'app')
    if not os.path.isdir(app_dir):
        log('FAIL: 包内 app/ 不存在：%s' % app_dir)
        return 2
    for rel in (('models', 'asr06b-encoder-fp16',
                 'ov-encoder-06b-fp16-static.xml'),
                ('models', 'asr06b-decoder-int8', 'openvino_model.xml'),
                ('models', 'embed_tokens_06b_f16.npy')):
        p = os.path.join(pkg, *rel)
        if not os.path.isfile(p):
            log('FAIL: 包内模型缺失 %s' % p)
            return 2

    out_dir = args.out_dir or os.path.join(
        TMP, 'app_backend_%s' % args.device.replace('.', ''))
    os.makedirs(out_dir, exist_ok=True)

    # ── 取共享机器锁（App 侧口径）────────────────────────────────────
    sys.path.insert(0, REPO)
    import machine_lock_app
    ok, payload = machine_lock_app.acquire(module='app', timeout=3600, poll=20,
                                           verbose=True)
    if not ok:
        log('🔴 未取得 MACHINE_LOCK ⇒ 终止')
        return 2
    log('[app121] 已取锁：%s' % payload)

    res = {
        'script': '_app121_asr_app_3mat.py',
        'task': 'APP-121 §2：用 **App 的后端**（OVEngine=StreamingEngine+'
                'ASR06BStatefulBackend）跑 §86 三素材',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'device': args.device,
        'pkg': pkg,
        'python': sys.executable,
        'app_path': app_dir,
        'ref_md5': REF_MD5,
        'materials': [],
    }
    try:
        import numpy as np
        # 🔴 **App 的真实调用路径**：包内 app/ 必须在 sys.path 最前
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        import live_caption_app as L
        res['live_caption_app_file'] = L.__file__
        res['backend_class'] = ('%s.%s'
                                 % (L.__file__,
                                    'asr06b_stateful_backend.ASR06BStatefulBackend'))
        import openvino as ov
        res['env'] = {'python_version': sys.version.split()[0],
                      'ov_version': ov.__version__}

        # ── 选引擎 key（**只用 App 自己的表**）──────────────────────
        table = L.active_asr_engines()
        res['engine_keys'] = sorted(table)
        cands = [(k, c) for k, c in table.items()
                 if c.get('kind') == 'asr06b' and c.get('device') == args.device]
        if not cands:
            log('FAIL: App 引擎表里没有 kind=asr06b / device=%s 的条目：%s'
                % (args.device, sorted(table)))
            return 2
        key = sorted(cands)[0][0]
        res['engine_key'] = key
        log('[app121] 引擎 key=%s  OV=%s  python=%s'
            % (key, ov.__version__, sys.version.split()[0]))

        for tag, lang, wav, ref_tp in MATS:
            log('[app121] ── 素材 %s（%s）%s' % (tag, lang, wav))
            eng = L.OVEngine(key, on_log=lambda *a: None,
                             force_language=lang, device=args.device)
            segs = []
            state = {'fed_s': 0.0}
            orig_close = eng._close_segment

            def _close_rec():
                acc = eng.state.audio_accum
                dur = (float(acc.shape[0]) / SR) if acc is not None else 0.0
                end_s = state['fed_s']
                txt = orig_close()
                segs.append({'start_s': round(end_s - dur, 3),
                             'end_s': round(end_s, 3),
                             'duration_s': round(dur, 3), 'text': txt})
                return txt
            eng._close_segment = _close_rec

            audio = read_wav_i16(wav)
            step = int(SR * CHUNK_SEC)
            t0 = time.perf_counter()
            n_blocks = 0
            for i in range(0, len(audio) - step + 1, step):
                blk = audio[i:i + step]
                state['fed_s'] += len(blk) / float(SR)
                eng.feed(blk, time.perf_counter())
                n_blocks += 1
            # 尾部不足一块的余料也喂进去
            rem = len(audio) % step
            if rem:
                blk = audio[len(audio) - rem:]
                state['fed_s'] += len(blk) / float(SR)
                eng.feed(blk, time.perf_counter())
                n_blocks += 1
            tail = eng.flush()
            if tail:
                segs.append({'start_s': round(state['fed_s'], 3),
                             'end_s': round(state['fed_s'], 3),
                             'duration_s': 0.0, 'text': tail})
            wall = time.perf_counter() - t0
            audio_s = len(audio) / float(SR)

            mat_dir = os.path.join(out_dir, tag)
            os.makedirs(mat_dir, exist_ok=True)
            tp = os.path.join(mat_dir, 'transcript.txt')
            with io.open(tp, 'w', encoding='utf-8', newline='\n') as f:
                for r in segs:
                    f.write('[%8.1f-%8.1f] %s\n'
                            % (r['start_s'], r['end_s'], r['text']))
            md5 = md5_of(tp)
            ref_md5 = md5_of(ref_tp) if os.path.isfile(ref_tp) else None
            same = (os.path.isfile(ref_tp)
                    and io.open(tp, 'rb').read() == io.open(ref_tp, 'rb').read())
            probe = getattr(eng.backend, 'probe', {}) or {}
            info = {
                'material': tag, 'lang': lang, 'wav': wav,
                'n_blocks': n_blocks,
                'audio_s': round(audio_s, 3),
                'wall_s': round(wall, 2),
                'rtf': round(wall / audio_s, 4) if audio_s else None,
                'rtf_note': 'wall / audio_s（**含编译**；与 §86 口径不同，'
                            '仅作量级参考）',
                'n_segs': len(segs),
                'transcript_path': tp,
                'transcript_md5': md5,
                'ref_md5': ref_md5,
                'ref_path': ref_tp,
                'md5_match': (md5 == ref_md5),
                'bytes_identical': bool(same),
                'prefix_truncations': int(probe.get('prefix_truncations', 0)),
                'truncations': int(probe.get('truncations', 0)),
                'probe_keys': sorted(probe.keys()),
                'segments': segs[:400],
            }
            res['materials'].append(info)
            log('[app121] %-4s wall=%7.1f rtf=%.4f segs=%d md5=%s match=%s '
                'identical=%s prefix_trunc=%d'
                % (tag, wall, info['rtf'] or -1, info['n_segs'], md5[:10],
                   info['md5_match'], info['bytes_identical'],
                   info['prefix_truncations']))
            try:
                eng.close()
            except Exception:
                pass

        # ── 与参照的差异解释 ─────────────────────────────────────────
        expl = []
        for m in res['materials']:
            if m['md5_match']:
                expl.append({'material': m['material'],
                             'verdict': '与 §86 参照逐字节相同'})
                continue
            ref_segs = []
            if os.path.isfile(m['ref_path']):
                with io.open(m['ref_path'], 'r', encoding='utf-8') as f:
                    for line in f:
                        if '] ' in line:
                            ref_segs.append(line.split('] ', 1)[1].rstrip('\n'))
            app_segs = [s['text'] for s in m['segments']]
            n_diff = sum(1 for a, b in zip(app_segs, ref_segs) if a != b)
            expl.append({
                'material': m['material'],
                'verdict': '与 §86 参照不同（**不要求硬凑一致**）',
                'n_segs_app': len(app_segs),
                'n_segs_ref': len(ref_segs),
                'n_segs_text_differ': n_diff,
                'first_diff_idx': next((i for i, (a, b) in
                                        enumerate(zip(app_segs, ref_segs))
                                        if a != b), None),
                'reasons': [
                    '**切段器不同**：App 用自己的 `Segmenter`（MIN_SEG_SEC=6 / '
                    'MAX_SEG_SEC=20 / 静音规则），参照用 ASR 模块 bk_run 的 '
                    '`Segmenter` ⇒ 段边界与段数本就不一致。',
                    '**解码入口不同**：App 的流式块 `max_new_tokens=32`、段尾 '
                    '`_finalize()` `max_new_tokens=64`（两处都走 '
                    '`ASR06BStatefulBackend.build_inputs_embeds`）；参照走 '
                    '`bk_run.run_stream` + `Asr065Runner`。',
                    '**语种 prompt 注入路径不同**：App 走 '
                    '`force_language` → `_right_ids()` 追加语种 id；参照走 '
                    '`set_lang_prompt()` 直接改 `prompt_raw`。',
                ],
            })
        res['ref_diff_explanation'] = expl
        res['all_md5_match'] = all(m['md5_match'] for m in res['materials'])
        res['note'] = ('本组数字是 **App 侧接入后** 的真实口径；'
                       '§0④ 的旧结论（App 侧 NPU 逐字节复现参照 / 对 GPU.0 '
                       '零回归）已按 APP-121 §2 撤回。')
    finally:
        try:
            machine_lock_app.release(payload, verbose=True)
            log('[app121] 已释放锁')
        except Exception as e:
            log('[app121] 释放锁异常：%r' % e)

    os.makedirs(RESULTS, exist_ok=True)
    op = args.json or os.path.join(
        RESULTS, 'app121_asr_app_3mat_%s.json' % args.device.replace('.', ''))
    tmp = op + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    os.replace(tmp, op)
    log('[app121] 证据 → %s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
