#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §2：**MiniMVP v1.1 的模型身份核验 +「不该有的东西」清单**。

reviewer 原文（APP-120 §2 第 1 条）：
> 包上自检 + 洁净度闸门 0 违规；模型身份逐文件核对（0.6B、MT INT8-CW、
> TTS-OV 的 config 维度 + 权重 SHA 对源目录）；包内不含录音、同事音色、
> 克隆音色、babelvox 样本，也不含 CUDA。

## 本脚本做三件事
A. **逐文件 SHA 对源目录**（不是抽样）：
   - 0.6B（decoder / encoder / tokenizer / embed 表）← sp5 包
   - MT INT8-CW ← `hy_bench/ov/mt2-int8sym-cw-q`
   - TTS-OV（int8 / weights / tokenizer / voices）← sp5 包
B. **config 维度**（`config.json` 关键字段 + OV XML 的 `<dim>`）逐项比对；
C. **「不该有的东西」清单**（存在即 FAIL）：
   CUDA / R2T2 模型 / MT INT4 / 预设 B / 克隆音色 / babelvox 示例音色 /
   bridge_token / *.pid / *.log / 录音与同事音色 / 说话人旁路模型。

## 纪律
🔴 **只读**（不写、不删任何文件）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1')
SP5 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp5')
HY = os.path.join(HOME, 'hy_bench', 'ov')
RESULTS = os.path.join(REPO, 'results', 'app')
OUT = os.path.join(RESULTS, 'app120_model_identity_v11.json')

#: reviewer 点名的 0.6B decoder bin SHA 前缀（APP-118 §3 D）
EXPECT_06B_DEC_SHA = '0059531a'

#: (包内相对路径, 源根目录, 源相对路径)
PAIRS = [
    # ── 0.6B（ASR）──
    ('models/asr06b-decoder-int8', SP5, 'models/asr06b-decoder-int8'),
    ('models/asr06b-encoder-fp16', SP5, 'models/asr06b-encoder-fp16'),
    ('models/asr06b-tokenizer', SP5, 'models/asr06b-tokenizer'),
    ('models/embed_tokens_06b_f16.npy', SP5,
     'models/embed_tokens_06b_f16.npy'),
    # ── MT（只 INT8-CW）──
    ('models/mt/mt2-int8sym-cw-q', HY, 'mt2-int8sym-cw-q'),
    # ── TTS（只 OpenVINO 版）──
    ('models/qwen3tts/int8', SP5, 'models/qwen3tts/int8'),
    ('models/qwen3tts/weights', SP5, 'models/qwen3tts/weights'),
    ('models/qwen3tts/tokenizer', SP5, 'models/qwen3tts/tokenizer'),
    ('models/qwen3tts/voices', SP5, 'models/qwen3tts/voices'),
]

#: 🔴 **「不该有的东西」**（存在即 FAIL；路径或 glob 片段）
FORBIDDEN = [
    ('cuda_env', 'CUDA 运行时（MiniMVP 不带）'),
    ('models/tts_cuda', 'CUDA TTS 模型（MiniMVP 不带）'),
    ('models/decoder-gpu-int4', 'R2T2 1.7B（MiniMVP 只带 0.6B）'),
    ('models/decoder-gpu-int8', 'R2T2 1.7B（MiniMVP 只带 0.6B）'),
    ('models/decoder-npu-int4', 'R2T2 1.7B（MiniMVP 只带 0.6B）'),
    ('models/decoder-npu-int8', 'R2T2 1.7B（MiniMVP 只带 0.6B）'),
    ('models/encoder-int4', 'R2T2 1.7B encoder'),
    ('models/encoder-int8', 'R2T2 1.7B encoder'),
    ('models/encoder-fp16', 'R2T2 1.7B encoder'),
    ('models/embed_tokens_f16.npy', 'R2T2 1.7B embed 表'),
    ('models/tokenizer', 'R2T2 1.7B tokenizer'),
    ('models/mt/mt2-int4sym-cw-q', 'MT INT4（MiniMVP 只带 INT8-CW）'),
    ('models/spk', '说话人旁路模型（MiniMVP 不带）'),
    ('preset_B', '预设 B（用户未抽听，不进包）'),
    ('bridge_token', 'EXT 鉴权 token（不得进包）'),
]
#: 目录级禁止
FORBIDDEN_DIRS = ['cuda_env', 'models/tts_cuda', 'models/spk']
#: 文件名级禁止（正则）
FORBIDDEN_FILE_RE = [
    (re.compile(r'(?i)^bridge_token.*$'), 'bridge_token*'),
    (re.compile(r'(?i)\.pid$'), '*.pid'),
    (re.compile(r'(?i)\.log$'), '*.log'),
    (re.compile(r'(?i)(^|/)voices/.*clone.*\.(wav|npz)$'), '克隆音色'),
    (re.compile(r'(?i)(^|/)v23_clone[^/]*/.*\.(wav|npz)$'), '克隆产物目录'),
    (re.compile(r'(?i)babelvox/data/speakers/(cindy|lou|phil|steve)\.(json|npy)$'),
     'babelvox 示例音色'),
    (re.compile(r'(?i)(^|/).*(_clone_test|_test)\.wav$'), '测试 wav'),
]


def log(m):
    print(m, flush=True)


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def list_files(root):
    out = {}
    if os.path.isfile(root):
        return {os.path.basename(root): root}
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            out[os.path.relpath(p, root).replace('\\', '/')] = p
    return out


def cmp_dir(pkg_rel, src_root, src_rel):
    a_root = os.path.join(PKG, pkg_rel)
    b_root = os.path.join(src_root, src_rel)
    A = list_files(a_root)
    B = list_files(b_root)
    n = ok = 0
    mism, miss, extra = [], [], []
    for rel, ap in A.items():
        bp = B.get(rel)
        if bp is None:
            extra.append(rel)
            continue
        n += 1
        if os.path.getsize(ap) == os.path.getsize(bp) and sha256(ap) == sha256(bp):
            ok += 1
        else:
            mism.append(rel)
    for rel in B:
        if rel not in A:
            miss.append(rel)
    return {'pkg_rel': pkg_rel, 'src': os.path.join(src_root, src_rel),
            'n_pkg_files': len(A), 'n_src_files': len(B),
            'n_compared': n, 'n_identical': ok,
            'mismatches': mism, 'missing_in_pkg': miss,
            'extra_in_pkg': extra,
            'all_identical': (not mism and not miss and n == len(A) == len(B))}


def config_dims(path):
    cands = []
    if os.path.isdir(path):
        cands = [os.path.join(path, 'config.json'),
                 os.path.join(path, 'openvino_model.xml')]
    elif path.lower().endswith('.json'):
        cands = [path]
    out = {}
    for c in cands:
        if not os.path.isfile(c):
            continue
        if c.endswith('.json'):
            try:
                d = json.load(open(c, encoding='utf-8'))
            except Exception:
                continue
            for k in ('hidden_size', 'num_hidden_layers', 'num_attention_heads',
                      'num_key_value_heads', 'intermediate_size',
                      'vocab_size', 'max_position_embeddings',
                      'num_mel_bins', 'd_model', 'encoder_layers',
                      'decoder_layers', 'num_codebooks', 'sampling_rate'):
                if k in d:
                    out['%s.%s' % (os.path.basename(c), k)] = d[k]
        else:
            try:
                t = open(c, encoding='utf-8', errors='replace').read()
                dims = re.findall(r'<dim>(\d+)</dim>', t)
                if dims:
                    out['%s.dims' % os.path.basename(c)] = dims[:12]
            except Exception:
                pass
    return out


def main():
    if not os.path.isdir(PKG):
        print('FAIL: 包目录不存在 %s' % PKG)
        return 2
    os.makedirs(RESULTS, exist_ok=True)
    log('=== APP-120 §2 模型身份核验（MiniMVP v1.1）===')
    rep = {'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'pkg': PKG,
           'pairs': [], 'dims': [], 'forbidden': [], 'errors': [],
           'checks': []}

    def check(name, cond, detail=''):
        rep['checks'].append({'name': name, 'pass': bool(cond),
                              'detail': str(detail)[:600]})
        if not cond:
            rep['errors'].append('%s :: %s' % (name, str(detail)[:300]))
        log('  %s %s' % ('PASS' if cond else 'FAIL', name))
        return cond

    # ── A. 逐文件 SHA 对源目录 ─────────────────────────────────────
    for pkg_rel, src_root, src_rel in PAIRS:
        if not os.path.exists(os.path.join(PKG, pkg_rel)):
            check('A %s 存在' % pkg_rel, False, '包内缺失')
            continue
        if not os.path.exists(os.path.join(src_root, src_rel)):
            check('A %s 源目录存在' % pkg_rel, False,
                  '源缺失 %s' % os.path.join(src_root, src_rel))
            continue
        r = cmp_dir(pkg_rel, src_root, src_rel)
        rep['pairs'].append(r)
        check('A %s 逐文件 SHA 一致（%d/%d）'
              % (pkg_rel, r['n_identical'], r['n_pkg_files']),
              r['all_identical'],
              'mismatch=%s missing=%s extra=%s' % (r['mismatches'][:5],
                                                    r['missing_in_pkg'][:5],
                                                    r['extra_in_pkg'][:5]))

    # ── B. config 维度 ─────────────────────────────────────────────
    for pkg_rel, src_root, src_rel in PAIRS:
        a = os.path.join(PKG, pkg_rel)
        b = os.path.join(src_root, src_rel)
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        da, db = config_dims(a), config_dims(b)
        same = bool(da) and da == db
        rep['dims'].append({'pkg_rel': pkg_rel, 'pkg_dims': da,
                            'src_dims': db, 'same': same})
        if da:
            check('B %s config 维度一致（%d 字段）' % (pkg_rel, len(da)),
                  same, 'pkg=%s src=%s' % (da, db))

    # ── C. 0.6B decoder bin SHA ─────────────────────────────────────
    dec_dir = os.path.join(PKG, 'models', 'asr06b-decoder-int8')
    dec_bins = [f for f in (os.listdir(dec_dir) if os.path.isdir(dec_dir) else [])
                if f.endswith('.bin')]
    dec_sha = {}
    for f in dec_bins:
        dec_sha[f] = sha256(os.path.join(dec_dir, f))
    rep['06b_decoder_bins'] = dec_sha
    check('C 0.6B decoder bin SHA 前缀 = %s' % EXPECT_06B_DEC_SHA,
          any(v.startswith(EXPECT_06B_DEC_SHA) for v in dec_sha.values()),
          json.dumps(dec_sha, ensure_ascii=False)[:300])

    # ── D. 「不该有的东西」──────────────────────────────────────────
    pkg_files = list_files(PKG)
    rels = sorted(pkg_files)
    hits = []
    for rel in rels:
        low = rel.lower()
        for rx, label in FORBIDDEN_FILE_RE:
            if rx.search('/' + low):
                hits.append({'rel': rel, 'why': label})
        for frag, label in FORBIDDEN:
            if frag in ('bridge_token', 'preset_B'):
                if frag.lower() in low:
                    hits.append({'rel': rel, 'why': label})
            elif low.startswith(frag.lower() + '/') or low == frag.lower():
                hits.append({'rel': rel, 'why': label})
    rep['forbidden'] = hits
    check('D 「不该有的东西」0 命中（扫 %d 文件）' % len(rels), not hits,
          json.dumps(hits[:10], ensure_ascii=False))

    # ── E. 目录级禁止（顶层/二级）──────────────────────────────────
    dir_hits = []
    for d in FORBIDDEN_DIRS:
        if os.path.exists(os.path.join(PKG, d)):
            dir_hits.append(d)
    check('E 禁止目录不存在（%s）' % ', '.join(FORBIDDEN_DIRS), not dir_hits,
          str(dir_hits))

    # ── F. 应当存在的关键文件 ──────────────────────────────────────
    must = [
        'models/asr06b-decoder-int8/openvino_model.xml',
        'models/asr06b-encoder-fp16/ov-encoder-06b-fp16-static.xml',
        'models/embed_tokens_06b_f16.npy',
        'models/mt/mt2-int8sym-cw-q',
        'models/qwen3tts/int8',
        'models/qwen3tts/voices/preset_A.wav',
        'app/device_config.py', 'app/live_caption_app.py',
        'app/asr06b_stateful_backend.py', 'package_profile.json',
        'README_zh.md', 'README_en.md',
    ]
    missing = [m for m in must if not os.path.exists(os.path.join(PKG, m))]
    check('F 关键文件齐全（%d 项）' % len(must), not missing, str(missing))

    # ── G. 音色只有预设 A ──────────────────────────────────────────
    voices = os.path.join(PKG, 'models', 'qwen3tts', 'voices')
    vfiles = sorted(os.listdir(voices)) if os.path.isdir(voices) else []
    rep['voices'] = vfiles
    check('G 音色只有 preset_A.wav', vfiles == ['preset_A.wav'], str(vfiles))

    rep['result'] = 'PASS' if not rep['errors'] else 'FAIL'
    rep['n_checks'] = len(rep['checks'])
    rep['n_fail'] = len(rep['errors'])
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)
    log('=== %s（%d/%d 通过）→ %s'
        % (rep['result'], rep['n_checks'] - rep['n_fail'], rep['n_checks'], OUT))
    return 0 if rep['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
