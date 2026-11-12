#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""manifest_gen.py — 从**源目录**生成 / 校验 ``app/MANIFEST.json``（APP-099 四.4）。

## APP-099 §2c / §4.4 原文
> 「APP-098 §3.6 缺 MANIFEST：rc7 包根只有 Diagnose.bat…**没有任何 MANIFEST**。
>  app417 只拿 rc6 和 rc5 对比，``models[].source`` 全为 None，也没有读 config 维度。」
> 「打包脚本从**源目录**生成 ``MANIFEST.json``。每个模型目录写明源路径、
>  每个权重文件的 SHA256、config 的维度（hidden_size / 层数）。
>  MT、TTS：写明实际的源目录。**打包时要逐个和源目录比对，任何一项不一致就终止**。」

## 设计（共用代码只写一份）
* 本模块在 dev 树 ``live_caption/`` 里；MiniMVP 构建脚本与完整版 ``pack_v13.py``
  **都调用同一份** ``build_manifest`` / ``verify_or_die`` ⇒ 不会各写一份副本。
* MANIFEST 里每个模型目录含：
  ``source_path`` / ``source_model`` / ``config``（hidden_size、层数等）
  / ``files``（包内每个文件的 name、bytes、sha256、source_sha256、match）。
* ``verify_or_die()`` 在打包前**重新读源目录**逐项比对（不信任 MANIFEST 里
  已存的 SHA），任何一项不一致就抛 ``ManifestMismatch`` ⇒ 调用方终止打包。

## 🔴 源目录（人工核对，APP-099 §4.4 / APP-098 六.5）
ASR 三个目录来自 ``qwen3asr_06b/models``；MT 来自 ``hy_bench/ov`` 的 OV IR
导出目录；TTS 运行时目录用 v2.4 交付包内同名目录作逐字节对拍基线
（reviewer APP-099 §1 已复核 MT/TTS 身份），原始导出件见各条 note。

⚠️ 本模块**不自行发起打包**；只在被调用时生成/校验。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from collections import OrderedDict

MANIFEST_REL = os.path.join('app', 'MANIFEST.json')
SOURCE_ROOT = r'C:\Users\Trekker-PTL'

#: 🔴 源目录映射：包内 models/ 下的相对路径 → 源（绝对路径 + 模型名 + 说明）
#:   ⚠️ 这是**人工核对**的映射（APP-099 §4.4 要求「写明实际的源目录」）；
#:      改这里必须同步改 STATUS 的「模型身份」表。
MODEL_SOURCES = OrderedDict([
    ('asr06b-decoder-int8', {
        'source_path': r'qwen3asr_06b\models\ov-dec-06b-stateful-int8sym',
        'source_model': 'Qwen3-ASR-0.6B',
        'note': 'APP-101/102/103：OV IR，stateful INT8（KV cache）；decoder bin SHA256 应为 0059531a2b4ccd4ceb3f4c1dc3519e68421a310a262baba4dc55e603b600d6a3'}),
    ('asr06b-encoder-fp16', {
        'source_path': r'qwen3asr_06b\models\ov-encoder-06b-fp16-static',
        'source_model': 'Qwen3-ASR-0.6B',
        'note': 'OV IR，FP16 静态形状；encoder bin 应与 B 机 rc5 实测 0B7463D6F952DD64… 一致'}),
    ('asr06b-tokenizer', {
        'source_path': r'qwen3asr_06b\models\Qwen3-ASR-0.6B',
        'source_model': 'Qwen3-ASR-0.6B',
        'note': 'HF 目录（未导出 OV）；config.json 里 text hidden 1024 / 28 层、audio d_model 896 / 18 层'}),
    ('embed_tokens_06b_f16.npy', {
        'source_path': r'qwen3asr_06b\b_kit_stateful\assets\embed_tokens.npy',
        'source_model': 'Qwen3-ASR-0.6B',
        'note': 'APP-103：B-kit 导出的 fp16 文本 embedding 表 [151936, 1024]（免 torch）；'
                'SHA256 e8d4448c57626ff9a6396b06f05f0e2c2d9ca4fa2436988f012c171e9f861f2c，'
                '与 rc5 暂存区的 embed_tokens_06b_f16.npy 逐字节同一份'}),
    ('mt/mt2-int4sym-cw-q', {
        'source_path': r'hy_bench\ov\mt2-int4sym-cw-q',
        'source_model': 'Hy-MT2-1.8B',
        'note': 'OV IR，INT4 对称按通道（INT4-CW）；bin 与 v2.4 相同（667CD34D77F637CA…）'}),
    ('qwen3tts', {
        'source_path': r'Confucius4_LiveCaption_v2.4\models\qwen3tts',
        'source_model': 'Qwen3-TTS',
        'note': 'BabelVox 运行时目录（权重/声码器/tokenizer/voices）。原始导出件是 '
                r'shared\ovms_qwen3_tts\ovms_qwen3_tts_1.1.zip；'
                '此处用 v2.4 真包内同名目录作逐字节对拍基线（APP-099 §1 已复核）'}),
])

#: config.json 里要抽的「维度」键（APP-099 §4.4：hidden_size / 层数）
DIM_KEYS = ('hidden_size', 'num_hidden_layers', 'd_model', 'encoder_layers',
            'decoder_layers', 'num_attention_heads', 'num_key_value_heads',
            'intermediate_size', 'vocab_size', 'max_position_embeddings',
            'num_mel_bins', 'd_model_audio')


class ManifestMismatch(RuntimeError):
    """打包前逐项比对失败 ⇒ 调用方必须终止打包。"""


def sha256_file(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def abs_source(rel_path, source_root=SOURCE_ROOT):
    return os.path.normpath(os.path.join(source_root, rel_path))


def _walk_dims(obj, prefix='', out=None, depth=0):
    if out is None:
        out = {}
    if depth > 6 or not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        key = (prefix + '.' + k) if prefix else k
        if k in DIM_KEYS and isinstance(v, (int, float)):
            out[key] = v
        elif isinstance(v, dict):
            _walk_dims(v, key, out, depth + 1)
    return out


def config_dims(path):
    """读源目录里的 config.json，抽出 hidden_size / 层数等维度。

    ⚠️ 支持嵌套（``thinker_config.text_config.hidden_size`` 这类）；
       找不到 config.json 时返回空 dict（**不猜**），调用方如实记 ``None``。
    """
    candidates = []
    if os.path.isfile(path):
        candidates.append(path)
    elif os.path.isdir(path):
        for dp, _dn, fn in os.walk(path):
            for f in fn:
                if f == 'config.json':
                    candidates.append(os.path.join(dp, f))
    out = {}
    for c in candidates:
        try:
            j = json.load(open(c, 'r', encoding='utf-8'))
        except Exception:
            continue
        d = _walk_dims(j)
        for k, v in d.items():
            rel = os.path.relpath(c, path if os.path.isdir(path)
                                  else os.path.dirname(path)).replace('\\', '/')
            out.setdefault(rel, {}).update({k: v})
    return out


def scan_files(path):
    """列出目录（或单文件）里的每个文件 → {name, bytes}（不算 SHA）。"""
    out = []
    if os.path.isfile(path):
        return [{'name': os.path.basename(path), 'bytes': os.path.getsize(path)}]
    if not os.path.isdir(path):
        return out
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            fp = os.path.join(dp, f)
            try:
                out.append({'name': os.path.relpath(fp, path).replace('\\', '/'),
                            'bytes': os.path.getsize(fp)})
            except OSError:
                pass
    return sorted(out, key=lambda x: x['name'])


def build_manifest(pkg_models_root, source_root=SOURCE_ROOT, compute_sha=True):
    """从**源目录**生成 MANIFEST 的内容字典。

    ``compute_sha=False`` 只用于接口级自测（不读大文件）；正式打包必须 True。
    """
    models = OrderedDict()
    mismatches = []
    for rel, meta in MODEL_SOURCES.items():
        src = abs_source(meta['source_path'], source_root)
        dst = os.path.join(pkg_models_root, *rel.split('/'))
        entry = {
            'source_path': src,
            'source_model': meta['source_model'],
            'note': meta['note'],
            'source_exists': os.path.exists(src),
            'pkg_exists': os.path.exists(dst),
            'config': config_dims(src) or None,
            'files': [],
        }
        if not entry['source_exists']:
            mismatches.append('%s: 源目录不存在 %s' % (rel, src))
        if not entry['pkg_exists']:
            mismatches.append('%s: 包内路径不存在 %s' % (rel, dst))
        for item in scan_files(dst):
            sfile = (src if os.path.isfile(src)
                     else os.path.join(src, *item['name'].split('/')))
            row = dict(item)
            row['source_path'] = sfile
            row['source_exists'] = os.path.isfile(sfile)
            if compute_sha:
                # 🔴 dst 本身可能是**单文件模型**（embed_tokens_06b_f16.npy）：
                #    scan_files() 对它只返回 basename 一行，不能再把 name 拼到
                #    dst 后面（会得到 ...\xxx.npy\xxx.npy ⇒ FileNotFoundError）。
                #    app443 的接口级自测用临时目录，没覆盖这一形态。
                pkgfile = (dst if os.path.isfile(dst)
                           else os.path.join(dst, *item['name'].split('/')))
                row['sha256'] = sha256_file(pkgfile)
                if row['source_exists']:
                    row['source_sha256'] = sha256_file(sfile)
                    row['match'] = (row['sha256'] == row['source_sha256'])
                    if not row['match']:
                        mismatches.append('%s/%s: SHA 与源目录不一致' % (rel, item['name']))
                else:
                    row['source_sha256'] = None
                    row['match'] = False
                    mismatches.append('%s/%s: 源目录里没有同名文件' % (rel, item['name']))
            entry['files'].append(row)
        models[rel] = entry
    return {
        'schema': 'app099-manifest-v1',
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source_root': source_root,
        'pkg_models_root': os.path.abspath(pkg_models_root),
        'n_models': len(models),
        'models': models,
        'computed_sha': bool(compute_sha),
        'n_mismatches': len(mismatches),
        'mismatches': mismatches,
        'all_match': (len(mismatches) == 0),
    }


def manifest_path(pkg_root):
    return os.path.join(pkg_root, MANIFEST_REL)


def write_manifest(pkg_root, manifest=None):
    """生成并写出 ``<pkg_root>/app/MANIFEST.json``（只写文件，不打包）。"""
    p = manifest_path(pkg_root)
    m = manifest if manifest is not None else build_manifest(
        os.path.join(pkg_root, 'models'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    return p


def verify_manifest(pkg_root, source_root=SOURCE_ROOT):
    """打包前**重新读源目录**逐项比对；返回 ``(ok, mismatches)``。

    ⚠️ 不信任 MANIFEST 里已存的 SHA：重新算两边 ⇒ 源目录被换掉也能抓到。
    """
    p = manifest_path(pkg_root)
    if not os.path.isfile(p):
        return False, ['缺 MANIFEST：%s' % p]
    try:
        m = json.load(open(p, 'r', encoding='utf-8'))
    except Exception as e:
        return False, ['MANIFEST 不可解析：%r' % e]
    if m.get('schema') != 'app099-manifest-v1':
        return False, ['MANIFEST schema 不符：%r' % m.get('schema')]
    fresh = build_manifest(os.path.join(pkg_root, 'models'), source_root)
    bad = list(fresh['mismatches'])
    old = m.get('models') or {}
    if set(old.keys()) != set(fresh['models'].keys()):
        bad.append('模型目录清单与 MANIFEST 不一致')
    for rel, e in fresh['models'].items():
        o = old.get(rel) or {}
        if o.get('source_path') != e['source_path']:
            bad.append('%s: source_path 与 MANIFEST 不一致' % rel)
        if o.get('config') != e['config']:
            bad.append('%s: config 维度与 MANIFEST 不一致' % rel)
        for fr in e['files']:
            hit = next((x for x in (o.get('files') or [])
                        if x.get('name') == fr['name']), None)
            if not hit:
                bad.append('%s/%s: MANIFEST 里缺该文件' % (rel, fr['name']))
            elif hit.get('sha256') != fr.get('sha256'):
                bad.append('%s/%s: 包内文件 SHA 与 MANIFEST 不一致' % (rel, fr['name']))
    return (len(bad) == 0), bad


def verify_or_die(pkg_root, source_root=SOURCE_ROOT):
    """打包前闸门：任何一项不一致 **终止**（APP-099 §4.4 原文）。"""
    ok, bad = verify_manifest(pkg_root, source_root)
    if not ok:
        raise ManifestMismatch('MANIFEST 与源目录不一致，终止打包：\n  - '
                               + '\n  - '.join(bad))
    return True


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True, help='包根（含 models/ 与 app/）')
    ap.add_argument('--write', action='store_true', help='生成并写 MANIFEST')
    ap.add_argument('--verify', action='store_true', help='逐项比对（不写）')
    a = ap.parse_args()
    if a.write:
        p = write_manifest(a.pkg)
        print('WROTE', p)
    if a.verify or not a.write:
        ok, bad = verify_manifest(a.pkg)
        print('VERIFY', 'OK' if ok else 'FAIL')
        for x in bad:
            print(' -', x)
        raise SystemExit(0 if ok else 1)
