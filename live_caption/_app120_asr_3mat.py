#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §0-4：**用包内 python 跑 ASR §86 的 3 个素材**（SPE / EN / ZH）。

## reviewer 原文（APP-120 §0 第 4 条）
> 用包内 python 跑 ASR §86 的 3 个素材（SPE/EN/ZH），转写 md5 必须 =
> `cd67417e` / `ed3f52aa` / `d93062a6`，并报告 NPU 和 GPU.0 两种设备的 RTF。

## 本脚本做什么
1. **用 MiniMVP v1.1 包内的 python**（OV **2026.4.1-22982**，与 §86 参照同版本
   ⇒ handoff §七「口径警告」要求用 2.4.1，否则 md5 会变）；
2. **用包内的 0.6B 模型 IR**（`models/asr06b-encoder-fp16` /
   `models/asr06b-decoder-int8`）＋ **包内的 embed 表**
   （`models/embed_tokens_06b_f16.npy`，已与 kit 的 `embed_tokens.npy`
   **逐字节相同**（SHA256 `e8d4448c…`））；
3. 跑 ASR-065 的**同一套 decode 流程**（`bk_run.run_stream` ＋
   `asr065_backend.Asr065Runner`，**pml=320 / mrl=64 / use_tier=False**
   ⇒ 与 App 侧接入后的口径一致）；
4. 逐素材写 `transcript.txt` ⇒ md5 ⇒ **与参照 md5 逐位比对**；
5. 报 **RTF**（wall / covered_s，**不含编译**，与 §86 同口径）。

## 口径纪律
- RTF **不含编译**；编译耗时单列；
- **全程持 MACHINE_LOCK**（`asr_lock_common`，含 ctypes 存活探测）；
- 素材与参照产物：
  - `qwen3asr_06b/results/asr165_ov241/normal/{spe_en,fleurs_en,fleurs_zh}/transcript.txt`
  - SPE 素材 = `qwen3asr_06b/b_kit_stateful/assets/clip_10min_0_600.wav`（10 分钟）
  - EN/ZH 素材 = `_reviewer_tmp/bench/data/asr_{en,zh}.wav`
- `prompt.json` / `mel_filters.npy` / `tokenizer/` 取自 kit 的 assets
  （**特征常量与分词器**，不是模型产物；kit 的 `tokenizer.json` 与包内
  `asr06b-tokenizer/` 的 HF 形态不同 ⇒ 用 kit 的以保证与参照同输入）。

## 用法
```
<包内 python> live_caption/_app120_asr_3mat.py --device NPU
<包内 python> live_caption/_app120_asr_3mat.py --device GPU.0
```
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1')
ASR_WORK = os.path.join(HOME, 'qwen3asr_06b')
KIT = os.path.join(ASR_WORK, 'b_kit_stateful')
KIT_ASSETS = os.path.join(KIT, 'assets')
RESULTS = os.path.join(REPO, 'results', 'app')
TMP = os.path.join(HOME, 'AppData', 'Local', 'Temp', 'app120')

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

SR = 16000


def log(*a):
    print(*a, flush=True)


def md5_of(path):
    h = hashlib.md5()
    with io.open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sha_of(path):
    h = hashlib.sha256()
    with io.open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def build_assets(dst):
    """构造 assets 目录：**embed 表用包内的**，其余取 kit 的。"""
    os.makedirs(dst, exist_ok=True)
    # ① embed 表 ← **包内** `models/embed_tokens_06b_f16.npy`
    src_embed = os.path.join(PKG, 'models', 'embed_tokens_06b_f16.npy')
    dst_embed = os.path.join(dst, 'embed_tokens.npy')
    shutil.copy2(src_embed, dst_embed)
    embed_sha_pkg = sha_of(src_embed)
    embed_sha_kit = sha_of(os.path.join(KIT_ASSETS, 'embed_tokens.npy'))
    # ② prompt.json / mel_filters.npy ← kit（特征常量）
    for fn in ('prompt.json', 'mel_filters.npy'):
        shutil.copy2(os.path.join(KIT_ASSETS, fn), os.path.join(dst, fn))
    # ③ tokenizer/ ← kit（`tokenizer.json` 形态与包内 HF 目录不同）
    tdir = os.path.join(dst, 'tokenizer')
    if not os.path.isdir(tdir):
        shutil.copytree(os.path.join(KIT_ASSETS, 'tokenizer'), tdir)
    return {
        'embed_source': src_embed,
        'embed_sha256_pkg': embed_sha_pkg,
        'embed_sha256_kit': embed_sha_kit,
        'embed_identical': embed_sha_pkg == embed_sha_kit,
        'kit_assets_used': ['prompt.json', 'mel_filters.npy', 'tokenizer/'],
    }


def set_lang_prompt(runner, lang):
    """与 `asr165_bench.py` / `asr065_trunc_test.py` 同口径（幂等）。"""
    base = runner.prompt_raw
    want = 'language Chinese<asr_text>' if lang == 'zh' else \
        'language English<asr_text>'
    other = 'language English<asr_text>' if lang == 'zh' else \
        'language Chinese<asr_text>'
    if want in base:
        return
    if other not in base:
        raise RuntimeError('prompt_raw 里找不到语种标记：%r' % base[:200])
    runner.prompt_raw = base.replace(other, want)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', required=True, choices=('NPU', 'GPU.0'))
    ap.add_argument('--pml', type=int, default=320,
                    help='NPUW MAX_PROMPT_LEN（默认 320＝App 接入后的值）；'
                         '512 = ASR-065 之前的基线（用于「跨加速器数值差异」对照）')
    ap.add_argument('--out-dir', default='')
    ap.add_argument('--pkg', default=PKG)
    args = ap.parse_args()

    for p in (os.path.join(args.pkg, 'models', 'asr06b-encoder-fp16',
                           'ov-encoder-06b-fp16-static.xml'),
              os.path.join(args.pkg, 'models', 'asr06b-decoder-int8',
                           'openvino_model.xml'),
              os.path.join(args.pkg, 'models', 'embed_tokens_06b_f16.npy')):
        if not os.path.isfile(p):
            print('FAIL: 包内模型缺失 %s' % p)
            return 2

    out_dir = args.out_dir or os.path.join(
        TMP, 'asr_3mat_%s_pml%d' % (args.device.replace('.', ''), args.pml))
    os.makedirs(out_dir, exist_ok=True)

    for p in (os.path.join(ASR_WORK, 'b_kit_stateful', 'scripts'),
              os.path.join(ASR_WORK, 'scripts', '_asr065'),
              os.path.join(ASR_WORK, 'scripts')):
        if p not in sys.path:
            sys.path.insert(0, p)

    from bk_run import run_stream                                  # noqa: E402
    import asr065_backend                                           # noqa: E402
    from asr065_backend import Asr065Runner                        # noqa: E402
    from asr_lock_common import (CANON_LOCK, LockProbe, acquire,   # noqa: E402
                                 release_lock_if_owner)

    # ── 取锁 ─────────────────────────────────────────────────────────
    lock_pid = acquire(CANON_LOCK, task='app120_asr_3mat_%s' % args.device,
                       module='app')
    if lock_pid is None:
        log('🔴 未取得 MACHINE_LOCK ⇒ 终止')
        return 2
    log('[app120] 已取锁 pid=%d' % lock_pid)
    probe = LockProbe(expect_pid=lock_pid)

    res = {
        'script': '_app120_asr_3mat.py',
        'task': 'APP-120 §0-4：包内 python 跑 §86 三素材（SPE/EN/ZH）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'device': args.device,
        'pml': args.pml,
        'pkg': args.pkg,
        'python': sys.executable,
        'lock_pid': lock_pid,
        'ref_md5': REF_MD5,
        'materials': [],
    }
    try:
        import openvino as ov
        import transformers
        res['env'] = {
            'python_version': sys.version.split()[0],
            'ov_version': ov.__version__,
            'transformers': transformers.__version__,
        }
        log('[app120] OV=%s  python=%s'
            % (ov.__version__, sys.version.split()[0]))

        assets_dir = os.path.join(TMP, 'asr_assets')
        res['assets'] = build_assets(assets_dir)
        log('[app120] assets=%s  embed 与 kit 逐字节相同=%s'
            % (assets_dir, res['assets']['embed_identical']))

        enc_ir = os.path.join(args.pkg, 'models', 'asr06b-encoder-fp16',
                              'ov-encoder-06b-fp16-static.xml')
        dec_ir = os.path.join(args.pkg, 'models', 'asr06b-decoder-int8',
                              'openvino_model.xml')

        t_build = time.perf_counter()
        runner = Asr065Runner(enc_ir, dec_ir, args.device, assets_dir,
                              mode='stateful', mel_mode='fft',
                              max_prompt_len=args.pml,
                              min_response_len=64,
                              use_tier=False)
        runner._recompile()
        res['startup'] = {
            'enc_compile_s': runner.t_enc_compile,
            'dec_compile_s': runner.t_dec_compile,
            'build_total_s': round(time.perf_counter() - t_build, 2),
            'pml': args.pml, 'min_response_len': 64, 'use_tier': False,
            'enc_ir': enc_ir, 'dec_ir': dec_ir,
        }
        log('[app120] 编译 enc=%.2fs dec=%.2fs（**不计入 RTF**）'
            % (runner.t_enc_compile, runner.t_dec_compile))

        for tag, lang, wav, ref_tp in MATS:
            set_lang_prompt(runner, lang)
            runner.reset_probe()
            runner.reset_trunc()
            probe.check()
            mat_dir = os.path.join(out_dir, tag)
            t0 = time.perf_counter()
            summary = run_stream(runner, mat_dir, wav, 0.0)
            wall = time.perf_counter() - t0
            tp = os.path.join(mat_dir, 'transcript.txt')
            md5 = md5_of(tp) if os.path.exists(tp) else None
            ref_md5 = md5_of(ref_tp)
            ref_bytes = os.path.getsize(ref_tp)
            same_bytes = (os.path.exists(tp)
                          and open(tp, 'rb').read() == open(ref_tp, 'rb').read())
            info = {
                'material': tag, 'lang': lang, 'wav': wav,
                'wall_s': round(wall, 2),
                'rtf': summary.get('rtf'),
                'rtf_note': 'wall / covered_s（**不含编译**；与 §86 同口径）',
                'covered_s': summary.get('covered_s'),
                'n_segs': summary.get('n_segs'),
                'transcript_md5': md5,
                'ref_md5': ref_md5,
                'ref_path': ref_tp,
                'md5_match': (md5 == ref_md5),
                'bytes_identical': bool(same_bytes),
                'transcript_bytes': (os.path.getsize(tp)
                                     if os.path.exists(tp) else 0),
                'ref_bytes': ref_bytes,
                'prefix_truncations': getattr(runner, 'prefix_truncations', None),
                'enc_tiers_fallback_reason':
                    getattr(runner, 'enc_tiers_fallback_reason', None),
            }
            res['materials'].append(info)
            log('[app120] %-4s wall=%7.1f rtf=%.4f md5=%s match=%s identical=%s'
                % (tag, wall, info['rtf'] or -1, (md5 or '')[:10],
                   info['md5_match'], info['bytes_identical']))

        probe.check()
        res['lock_probe'] = {
            'lock_probe_checks': probe.n_checks,
            'lock_probe_stolen': probe.n_stolen,
            'lock_probe_stolen_at': probe.first_stolen_at,
            'lock_probe_reason': probe.last_reason,
            'note': ('持锁方逐条自检：锁被删/被换写 ⇒ timing_valid=false。'
                     '本次%s。' % ('未发现锁被抢'
                                  if not probe.n_stolen else '发现锁被抢')),
        }
        res['all_md5_match'] = all(m['md5_match'] for m in res['materials'])
        res['timing_valid'] = (probe.n_stolen == 0)
    finally:
        try:
            release_lock_if_owner(CANON_LOCK, expect_pid=lock_pid)
            log('[app120] 已释放锁')
        except Exception as e:
            log('[app120] 释放锁异常：%s' % e)

    os.makedirs(RESULTS, exist_ok=True)
    op = os.path.join(RESULTS, 'app120_asr_3mat_%s_pml%d.json'
                       % (args.device.replace('.', ''), args.pml))
    tmp = op + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    os.replace(tmp, op)
    log('[app120] 证据 → %s' % op)
    log('[app120] all_md5_match=%s timing_valid=%s'
        % (res.get('all_md5_match'), res.get('timing_valid')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
