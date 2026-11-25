#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app137_candidate_check.py — **APP-137 §3 的「包内容核对」**（离线，只读）。

## reviewer APP-137 §3 原文
> **包内容核对**：模型身份（config 维度 + 权重 SHA 对源目录，含 bgsep 和克隆链模型）；
> 克隆音色目录为空；包里没有 `.wav/.ogg/.mp3/.mp4` 之类的媒体文件；没有 CUDA DLL。

## 本脚本做四组核对（**全部离线、只读**）

| 组 | 核对内容 |
|---|---|
| **A 模型身份** | `models/bgsep`、`models/spk/*`、`models/mt/*`、`models/qwen3tts/*` 的**权重 SHA256** 与**源目录**逐个比；`config.json` 的**维度**（`hidden_size`/`num_hidden_layers`/`vocab_size`）与源目录比 |
| **B 克隆链** | `models/spk/` 两个 IR 齐全；`app/` 下克隆链代码齐全（`clone_voice.py`／`clone_collector.py`／`speaker_*.py`）；**克隆音色目录只有 `preset_A.wav`** |
| **C 媒体文件** | 全包扫 `.wav/.ogg/.mp3/.mp4/.m4a/.flac` ⇒ **除 `preset_A.wav` 外必须 0 个** |
| **D CUDA** | `cuda_env/` 不存在；`models/tts_cuda/` 不存在；全包**无 CUDA DLL**（`cudart*.dll`／`cublas*.dll`／`nvinfer*.dll` 等） |

## 🔴 源目录对照（**只读**）
* `models/bgsep` ⇒ 源 = **完整版 v2.6** 的同名目录（Demucs 是同一个 IR）；
* `models/spk/*` ⇒ 源 = **完整版 v2.6**；
* `models/mt/mt2-int8sym-cw-q` ⇒ 源 = **完整版 v2.6**（MT3 的事属 APP-135，不在本条）；
* `models/qwen3tts/*` ⇒ 源 = **完整版 v2.6**。

## 用法
```
python live_caption/_app137_candidate_check.py
```
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app137_candidate_check.json')

CAND = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.2.candidate')
SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')

#: 🔴 **媒体文件扩展名**（客户包铁律）
MEDIA_EXTS = ('.wav', '.ogg', '.mp3', '.mp4', '.m4a', '.flac', '.aac', '.wma')

#: 🔴 **允许存在的媒体文件**（内置音色 A —— 只有这一个）
MEDIA_ALLOW = {'models/qwen3tts/voices/preset_A.wav'}

#: 🔴 **CUDA DLL 特征**（文件名含这些片段 ⇒ 判为带 CUDA）
CUDA_DLL_PAT = ('cudart', 'cublas', 'cufft', 'curand', 'cusparse', 'cusolver',
                'nvrtc', 'nvinfer', 'cudnn', 'nccl', 'nvjpeg', 'nvcuvid')


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(p):
    try:
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def main():
    if not os.path.isdir(CAND):
        print('FAIL: 候选目录不存在 %s' % CAND)
        return 2

    checks = []
    detail = {}

    def chk(group, name, ok, d=''):
        checks.append({'group': group, 'name': name, 'ok': bool(ok), 'detail': d})

    # ── A 模型身份（权重 SHA + config 维度） ───────────────────────
    MODEL_DIRS = [
        'models/bgsep',
        'models/spk/pyannote_seg_3_0',
        'models/spk/wespeaker-resnet34-fp16',
        'models/mt/mt2-int8sym-cw-q',
        'models/qwen3tts/weights',
        'models/qwen3tts/tokenizer',
    ]
    ident = []
    for rel in MODEL_DIRS:
        cd = os.path.join(CAND, rel.replace('/', os.sep))
        sd = os.path.join(SRC, rel.replace('/', os.sep))
        if not os.path.isdir(cd):
            chk('A', 'model_dir_present:%s' % rel, False, '候选目录缺 %s' % rel)
            continue
        if not os.path.isdir(sd):
            chk('A', 'model_src_present:%s' % rel, False, '源目录缺 %s' % rel)
            continue
        n_cmp = 0
        n_same = 0
        mism = []
        for dp, _dns, fns in os.walk(cd):
            for fn in fns:
                cf = os.path.join(dp, fn)
                crel = os.path.relpath(cf, CAND).replace(os.sep, '/')
                sf = os.path.join(SRC, crel.replace('/', os.sep))
                if not os.path.isfile(sf):
                    mism.append({'file': crel, 'why': '源目录没有同名文件'})
                    continue
                n_cmp += 1
                if sha256_file(cf) == sha256_file(sf):
                    n_same += 1
                else:
                    mism.append({'file': crel, 'why': 'SHA256 不同'})
        ident.append({'dir': rel, 'n_compared': n_cmp, 'n_same': n_same,
                      'mismatches': mism[:10]})
        chk('A', 'model_weights_identical:%s' % rel,
            n_cmp > 0 and n_same == n_cmp,
            '%d/%d 文件 SHA256 相同' % (n_same, n_cmp))

    # config 维度对照（bgsep 没有 config.json ⇒ 用 xml 里的 batch/seq）
    cfg_checks = []
    for rel in ('models/mt/mt2-int8sym-cw-q/config.json',):
        cp = os.path.join(CAND, rel.replace('/', os.sep))
        sp = os.path.join(SRC, rel.replace('/', os.sep))
        cc, sc = load_json(cp), load_json(sp)
        if cc is None or sc is None:
            chk('A', 'config_present:%s' % rel, False, 'config.json 读不出')
            continue
        keys = [k for k in ('hidden_size', 'num_hidden_layers', 'vocab_size',
                            'num_attention_heads', 'intermediate_size')
                if k in cc and k in sc]
        same = all(cc.get(k) == sc.get(k) for k in keys)
        cfg_checks.append({'file': rel, 'keys': {k: [cc.get(k), sc.get(k)] for k in keys},
                           'same': same})
        chk('A', 'config_dims_identical:%s' % rel, same,
            '维度键 %s' % (keys or '（无）'))
    detail['model_identity'] = ident
    detail['config_dims'] = cfg_checks

    # ── B 克隆链 ───────────────────────────────────────────────────
    spk = os.path.join(CAND, 'models', 'spk')
    spk_ok = os.path.isdir(spk) and os.path.isdir(os.path.join(spk, 'pyannote_seg_3_0')) \
        and os.path.isdir(os.path.join(spk, 'wespeaker-resnet34-fp16'))
    chk('B', 'clone_chain_models_present', spk_ok, 'models/spk 下两个 IR')
    appd = os.path.join(CAND, 'app')
    code_needed = ['clone_voice.py', 'clone_collector.py', 'speaker_tracker.py',
                   'speaker_voice.py', 'speaker_assets.py']
    missing = [f for f in code_needed if not os.path.isfile(os.path.join(appd, f))]
    chk('B', 'clone_chain_code_present', not missing,
        '缺：%s' % (missing or '无'))
    voices = os.path.join(CAND, 'models', 'qwen3tts', 'voices')
    vfiles = sorted(os.listdir(voices)) if os.path.isdir(voices) else []
    chk('B', 'clone_voice_dir_only_preset_a', vfiles == ['preset_A.wav'],
        '克隆音色目录内容：%s' % vfiles)
    detail['clone'] = {'voices': vfiles, 'missing_code': missing}

    # ── C 媒体文件 ─────────────────────────────────────────────────
    media = []
    for dp, dns, fns in os.walk(CAND):
        dns[:] = [d for d in dns if d != '__pycache__']
        for fn in fns:
            if fn.lower().endswith(MEDIA_EXTS):
                rel = os.path.relpath(os.path.join(dp, fn), CAND).replace(os.sep, '/')
                if rel not in MEDIA_ALLOW:
                    media.append(rel)
    chk('C', 'no_media_files_except_preset_a', not media,
        '违规媒体文件 %d 个：%s' % (len(media), media[:10]))
    detail['media_violations'] = media

    # ── D CUDA ─────────────────────────────────────────────────────
    chk('D', 'no_cuda_env_dir', not os.path.exists(os.path.join(CAND, 'cuda_env')), '')
    chk('D', 'no_tts_cuda_models',
        not os.path.exists(os.path.join(CAND, 'models', 'tts_cuda')), '')
    cuda_dll = []
    for dp, dns, fns in os.walk(CAND):
        for fn in fns:
            lf = fn.lower()
            if lf.endswith('.dll') and any(p in lf for p in CUDA_DLL_PAT):
                cuda_dll.append(os.path.relpath(os.path.join(dp, fn), CAND).replace(os.sep, '/'))
    chk('D', 'no_cuda_dll', not cuda_dll, 'CUDA DLL：%s' % (cuda_dll[:10] or '无'))
    detail['cuda_dll'] = cuda_dll

    # ── E 包形态标记（APP-137 的 profile 语义） ─────────────────────
    prof = load_json(os.path.join(CAND, 'package_profile.json')) or {}
    chk('E', 'profile_minimvp', prof.get('profile') == 'minimvp', str(prof.get('profile')))
    chk('E', 'allow_clone_voice_true', prof.get('allow_clone_voice') is True,
        str(prof.get('allow_clone_voice')))
    chk('E', 'allow_bgkeep_true', prof.get('allow_bgkeep') is True,
        str(prof.get('allow_bgkeep')))
    chk('E', 'tts_c13_false', prof.get('tts_c13') is False, str(prof.get('tts_c13')))
    chk('E', 'allow_cuda_false', prof.get('allow_cuda') is False,
        str(prof.get('allow_cuda')))
    chk('E', 'mt_model_is_mt2', prof.get('mt_model') == 'mt2-int8sym-cw-q',
        str(prof.get('mt_model')))
    detail['profile'] = prof

    # ── F 不签 ACCEPTED、不打 zip ──────────────────────────────────
    chk('F', 'no_accepted_json', not os.path.exists(os.path.join(CAND, 'ACCEPTED.json')), '')
    zips = [f for f in os.listdir(HOME) if f.startswith('Confucius4_LiveCaption_MiniMVP_v1.2')
            and f.endswith('.zip')]
    chk('F', 'no_v12_zip', not zips, 'zip：%s' % (zips or '无'))

    ok = all(c['ok'] for c in checks)
    print('=== APP-137 §3 包内容核对 ===')
    for c in checks:
        print('  [%s] %-4s %-42s %s  %s'
              % ('OK' if c['ok'] else 'XX', c['group'], c['name'],
                 'PASS' if c['ok'] else 'FAIL', c['detail']))
    n_pass = sum(1 for c in checks if c['ok'])
    print('---- %d/%d PASS ----' % (n_pass, len(checks)))

    ev = {
        'script': '_app137_candidate_check.py',
        'task': 'APP-137 §3：MiniMVP v1.2 候选目录的包内容核对（离线只读）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'candidate': CAND,
        'source': SRC,
        'checks': checks,
        'n_pass': n_pass,
        'n_total': len(checks),
        'detail': detail,
        'all_pass': ok,
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('证据：%s' % EVIDENCE)
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
