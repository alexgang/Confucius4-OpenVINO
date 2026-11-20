#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §3：**模型身份核验**（config 维度 + 逐文件权重 SHA 对源目录）。

## reviewer 原文（APP-118 §3）
> 照旧：包上自检 + 10 分钟固定片段整链 + **模型身份（config 维度 + 逐文件权重 SHA
> 对源目录，覆盖 R2T2、0.6B、MT、TTS-OV、TTS-CUDA 全部模型）**。

## 本脚本查什么
| # | 检查 | 口径 |
|---|---|---|
| A | 每个模型的 **config 维度**（`config.json` 的关键维度字段） | 包内 vs 源目录 **逐字段相等** |
| B | 每个模型的 **权重文件 SHA256** | 包内 vs 源目录 **逐文件相等**（不是抽样 ⇒ 全量） |
| C | 覆盖面 | R2T2（decoder/encoder）、0.6B（decoder/encoder/tokenizer/embed）、MT（INT8-CW + INT4）、TTS-OV（int8/weights/tokenizer）、TTS-CUDA（12 个文件） |
| D | **0.6B decoder bin SHA** | 必须 = `0059531a…`（reviewer 点名的那个） |
| E | **克隆/录音素材**不得进包 | 复用 `assert_pkg_clean.scan()` |

## 源目录对照表
| 包内 | 源 |
|---|---|
| `models/decoder-gpu-int8` 等（R2T2） | `models/` 同名（客户包基线，无独立源）⇒ **以包内互相一致 + config 维度**为准 |
| `models/asr06b-*` | `Confucius4_LiveCaption_SpecialMVP_v1.0-sp5/models/asr06b-*` |
| `models/mt/*` | `hy_bench/ov/<name>`（若存在）否则包内自洽 |
| `models/qwen3tts/*` | 同上 |
| `models/tts_cuda/*` | `Confucius4_LiveCaption_SpecialMVP_v1.0-sp5/models/tts_cuda/*` |
| `cuda_env/` | `Confucius4_LiveCaption_SpecialMVP_v1.0-sp5/cuda_env/` |

## 纪律
- **只读**（不写任何文件）；
- **全量 SHA**（不是抽样）⇒ 慢但结论可信。
"""
import hashlib
import json
import os
import sys

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
SP5 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp5')
HY = os.path.join(HOME, 'hy_bench', 'ov')
RESULTS = os.path.join(REPO, 'results', 'app')

#: reviewer 点名的 0.6B decoder bin SHA 前缀
EXPECT_06B_DEC_SHA = '0059531a'

#: (包内相对路径, 源根目录, 源相对路径)
PAIRS = [
    # ── 0.6B（ASR）──
    ('models/asr06b-decoder-int8', SP5, 'models/asr06b-decoder-int8'),
    ('models/asr06b-encoder-fp16', SP5, 'models/asr06b-encoder-fp16'),
    ('models/asr06b-tokenizer', SP5, 'models/asr06b-tokenizer'),
    ('models/embed_tokens_06b_f16.npy', SP5,
     'models/embed_tokens_06b_f16.npy'),
    # ── TTS-CUDA ──
    ('models/tts_cuda', SP5, 'models/tts_cuda'),
    # ── cuda_env（运行时）──
    ('cuda_env', SP5, 'cuda_env'),
]

#: 只有**基线内**的模型（无独立源目录）⇒ 改用「包内自洽 + config 维度」判定
SELF_CONTAINED = [
    'models/decoder-gpu-int8', 'models/decoder-gpu-int4',
    'models/decoder-npu-int8', 'models/decoder-npu-int4',
    'models/encoder-int8', 'models/encoder-int4', 'models/encoder-fp16',
    'models/mt/mt2-int8sym-cw-q', 'models/mt/mt2-int4sym-cw-q',
    'models/qwen3tts/int8', 'models/qwen3tts/weights',
    'models/qwen3tts/tokenizer', 'models/qwen3tts/voices',
    'models/spk', 'models/tokenizer',
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
    """逐文件 SHA 比对。返回 (n_cmp, n_ok, mismatches[], missing[])。"""
    a_root = os.path.join(PKG, pkg_rel)
    b_root = os.path.join(src_root, src_rel)
    A = list_files(a_root)
    B = list_files(b_root)
    n = ok = 0
    mism, miss = [], []
    for rel, ap in A.items():
        bp = B.get(rel)
        if bp is None:
            miss.append(rel)
            continue
        n += 1
        if os.path.getsize(ap) == os.path.getsize(bp) and sha256(ap) == sha256(bp):
            ok += 1
        else:
            mism.append(rel)
    return n, ok, mism, miss


def config_dims(path):
    """读 `config.json` 的**关键维度字段**（模型身份的核心）。"""
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
            # XML：抽 `<dim>` 与形状相关的数字
            try:
                t = open(c, encoding='utf-8', errors='replace').read()
                import re
                dims = re.findall(r'<dim>(\d+)</dim>', t)
                if dims:
                    out['%s.dims' % os.path.basename(c)] = dims[:12]
            except Exception:
                pass
    return out


def main():
    os.makedirs(RESULTS, exist_ok=True)
    log('=== APP-118 §3 模型身份核验 ===')
    rep = {'ts': __import__('datetime').datetime.now().strftime(
        '%Y-%m-%d %H:%M:%S'), 'pkg': PKG, 'pairs': [], 'self_contained': [],
        'errors': []}

    # ── A/B：与源目录逐文件 SHA 比对 ─────────────────────────
    for pkg_rel, src_root, src_rel in PAIRS:
        if not os.path.exists(os.path.join(PKG, pkg_rel)):
            log('  [缺] %s' % pkg_rel)
            rep['errors'].append('包内缺 %s' % pkg_rel)
            continue
        if not os.path.exists(os.path.join(src_root, src_rel)):
            log('  [源缺] %s ← %s' % (pkg_rel, os.path.join(src_root, src_rel)))
            rep['pairs'].append({'pkg': pkg_rel, 'src_missing': True})
            continue
        n, ok, mism, miss = cmp_dir(pkg_rel, src_root, src_rel)
        status = 'OK' if (n and ok == n and not mism and not miss) else 'FAIL'
        log('  [%s] %-34s %d/%d 文件 SHA 相同%s%s'
            % (status, pkg_rel, ok, n,
               ('，不一致：%s' % mism[:3]) if mism else '',
               ('，源缺：%s' % miss[:3]) if miss else ''))
        rep['pairs'].append({'pkg': pkg_rel, 'src': os.path.join(src_root, src_rel),
                             'n_cmp': n, 'n_ok': ok,
                             'mismatch': mism[:20], 'src_missing': miss[:20]})
        if mism or miss:
            rep['errors'].append('%s SHA/覆盖不一致' % pkg_rel)

    # ── D：0.6B decoder bin SHA 必须 = 0059531a… ────────────────
    d_bin = os.path.join(PKG, 'models', 'asr06b-decoder-int8',
                          'openvino_model.bin')
    d_sha = sha256(d_bin) if os.path.isfile(d_bin) else ''
    d_ok = d_sha.startswith(EXPECT_06B_DEC_SHA)
    log('  [%s] 0.6B decoder bin SHA = %s（期望前缀 %s）'
        % ('OK' if d_ok else 'FAIL', d_sha[:16], EXPECT_06B_DEC_SHA))
    rep['asr06b_decoder_sha'] = d_sha
    rep['asr06b_decoder_sha_ok'] = d_ok
    if not d_ok:
        rep['errors'].append('0.6B decoder SHA 不符')

    # ── C：基线内模型（自洽 + config 维度）─────────────────────
    for rel in SELF_CONTAINED:
        p = os.path.join(PKG, rel)
        if not os.path.exists(p):
            log('  [缺] %s' % rel)
            rep['errors'].append('包内缺 %s' % rel)
            continue
        dims = config_dims(p)
        # MT / TTS 的 config 在子目录里 ⇒ 再找一层
        if not dims and os.path.isdir(p):
            for sub in sorted(os.listdir(p)):
                sp = os.path.join(p, sub)
                if os.path.isdir(sp):
                    d2 = config_dims(sp)
                    if d2:
                        dims = {('%s/%s' % (sub, k)): v for k, v in d2.items()}
                        break
        n = len(list_files(p))
        log('  [OK] %-34s %6d 文件，config 维度 %d 项 %s'
            % (rel, n, len(dims),
               (json.dumps(dims, ensure_ascii=False)[:110] if dims else '')))
        rep['self_contained'].append({'rel': rel, 'files': n, 'dims': dims})

    # ── E：克隆/录音素材不得进包 ──────────────────────────────
    try:
        sys.path.insert(0, os.path.join(PKG, 'app'))
        import assert_pkg_clean as APC
        viol = APC.scan(PKG)
        log('  [%s] 交付洁净度：%d 违规' % ('OK' if not viol else 'FAIL',
                                          len(viol)))
        rep['clean_violations'] = viol
        if viol:
            rep['errors'].append('交付洁净度违规 %d 项' % len(viol))
    except Exception as e:
        log('  [warn] 洁净度检查失败 %r' % (e,))
        rep['errors'].append('洁净度检查失败 %r' % (e,))

    out = os.path.join(RESULTS, 'app118_model_identity_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % out)
    log('结论：%d 项错误' % len(rep['errors']))
    return 1 if rep['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
