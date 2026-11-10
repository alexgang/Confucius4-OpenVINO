#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app310_build_minimvp_rc5.py —— **MiniMVP v1.0-rc5 构建器**（APP-095 1a + APP-096）。

## 依据（reviewer 2026-11-10）

* **APP-096**：MiniMVP 回到 APP-066 原规格 ⇒ ASR 换成 **Qwen3-ASR-0.6B**
  （mask2 INT8，**iGPU + NPU 两套**），去掉**全部 R2T2 ASR IR**；
  保留 APP-095 第 1a 点（去掉 INT4 decoder / `npu_int4` 引擎）。
  ⚠️ APP-095 第 1b 点（README 改 R2T2 名字）**被 APP-096 取代 ⇒ 不做**。
* **APP-095**：rc5 必须是**新目录 + 新 zip 文件名**，**不得原地改 rc4**（APP-055）。

## 本脚本做什么

| # | 动作 | 依据 |
|---|---|---|
| ① | **以 rc4 目录为基底复制出新目录** `Confucius4_LiveCaption_MiniMVP_v1.0-rc5`（rc4 一字不动） | APP-055 / APP-096 §1 |
| ② | **删掉全部 R2T2 ASR IR**：`encoder-int8` / `decoder-gpu-int8` / `encoder-fp16` / `decoder-npu-int8` / `decoder-npu-int4` / `embed_tokens_f16.npy` | APP-096 §1 |
| ③ | **放入 0.6B 物料**：`asr06b-decoder-int8`（mask2 INT8 decoder）+ `asr06b-encoder-fp16`（fp16 static encoder）+ `embed_tokens_06b_f16.npy` + 0.6B 的 tokenizer/config | APP-096 §1 |
| ④ | **两套共用同一份文件**（iGPU / NPU 用同一份 IR，只是编译目标设备不同）⇒ **只放一份** | APP-096 §1（"两套共用同一份文件就只放一份，不要复制两遍"） |
| ⑤ | **定点改写 rc5 的 `app/`**：`live_caption_app.py` 的引擎表 / 模型别名 / check 逻辑 ⇒ 接 0.6B 后端；**新增 `asr06b_backend.py`** | APP-096 §1（接线） |
| ⑥ | **去掉 INT4 ASR 引擎**（`npu_int4` / `gpu_int4` 档、GUI 下拉、`--check` 的 INT4 行、README 的 INT4 提及） | APP-095 1a |
| ⑦ | **README / G4_WHITELIST / release.json** 同步 | APP-096 §2 |

## 🔴🔴🔴 纪律

* **rc4 目录与 rc4 zip 一字不动**（事后复核 SHA/mtime）。
* 代码**只在 rc5 目录内改**（rc5 是新目录，不碰用户正在测的 rc4）。
* 本脚本**不写任何预编译 NPU 缓存**进包（实测包内 0 个 blob）⇒ 目标机首次运行现编。
* **不做 3d 的「不写死 NPU 架构 5010」**（那是 review 给的口径，本脚本只保证**不主动写死**）。

## 用法

```
.venv/Scripts/python.exe results/app/_app310_build_minimvp_rc5.py --dry-run
.venv/Scripts/python.exe results/app/_app310_build_minimvp_rc5.py --run
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

BASE_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5')

VERSION = '1.0-rc5'
REPORT = os.path.join(HERE, 'app310_minimvp_rc5_build_evidence.json')

# ── 0.6B 物料来源（开发机）────────────────────────────────────────────
Q06 = os.path.join(HOME, 'qwen3asr_06b', 'models')
SRC_DEC = os.path.join(Q06, 'ov-dec-06b-embed-mask2-int8sym')      # mask2 INT8 decoder
SRC_ENC = os.path.join(Q06, 'ov-encoder-06b-fp16-static')          # fp16 static encoder
SRC_HF = os.path.join(Q06, 'Qwen3-ASR-0.6B')                       # tokenizer/config
SRC_EMB = os.path.join(HERE, '_rc5_stage', 'embed_tokens_06b_f16.npy')

# 🔴 rc5 包内的 0.6B 模型目录名（**一套，iGPU/NPU 共用**）
PKG_DEC_DIR = 'asr06b-decoder-int8'
PKG_ENC_DIR = 'asr06b-encoder-fp16'
PKG_EMB_FILE = 'embed_tokens_06b_f16.npy'
PKG_TOK_DIR = 'asr06b-tokenizer'

# 🔴 要从 rc5 里**删掉**的 R2T2 ASR 物料（APP-096 §1）
DROP_MODEL_DIRS = (
    'encoder-int8', 'decoder-gpu-int8', 'encoder-fp16',
    'decoder-npu-int8', 'decoder-npu-int4',
)
DROP_MODEL_FILES = ('embed_tokens_f16.npy',)

# 🔴 0.6B tokenizer/config 里**要带**的文件（够用即可，不带 1.8 GB 权重）
TOK_FILES = (
    'tokenizer.json', 'tokenizer_config.json', 'vocab.json', 'merges.txt',
    'preprocessor_config.json', 'special_tokens_map.json', 'added_tokens.json',
    'config.json', 'generation_config.json', 'chat_template.json',
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def dir_stats(root: str):
    n = 0
    total = 0
    for dirpath, _d, files in os.walk(root):
        for fn in files:
            n += 1
            try:
                total += os.path.getsize(os.path.join(dirpath, fn))
            except OSError:
                pass
    return n, total


def patch_once(text: str, old: str, new: str, tag: str) -> str:
    """唯一命中断言的定点替换（归一化行尾 ⇒ CRLF 副本也能命中）。"""
    eol = '\r\n' if '\r\n' in text else '\n'
    norm = text.replace('\r\n', '\n')
    n = norm.count(old)
    if n != 1:
        raise AssertionError('anchor %s hit %d times (need exactly 1)' % (tag, n))
    norm = norm.replace(old, new, 1)
    return norm.replace('\n', eol) if eol == '\r\n' else norm


# ══════════════════════════════════════════════════════════════════════
# app/live_caption_app.py 的定点补丁
# ══════════════════════════════════════════════════════════════════════

# ① 模型别名：删掉 R2T2 ASR 的别名，加入 0.6B 的
OLD_ALIASES = """_MODEL_ALIASES = {
    # 编码器
    'ov-encoder-segment-reviewer-int8asym': ['encoder-int8'],
    'ov-encoder-segment-reviewer-int4': ['encoder-int4'],
    'ov-encoder-segment-reviewer': ['encoder-fp16'],
    # GPU 解码器
    'ov-int8-past': ['decoder-gpu-int8'],
    'ov-int4-lmhead-past': ['decoder-gpu-int4'],
    # NPU 解码器
    'qwen3-lm-int8sym-cleanie-ov': ['decoder-npu-int8'],
    'c089_int4/R4': ['decoder-npu-int4'],
    # NPU 用的 embedding 表（开发版在 decoder 目录里，包内提到了 models/ 根）
    'qwen3-lm-int8sym-cleanie-ov/embed_tokens_f16.npy': ['embed_tokens_f16.npy'],
}"""

NEW_ALIASES = """# 🔴🔴🔴 **APP-096**：MiniMVP 的 ASR 换成 **Qwen3-ASR-0.6B**（mask2 INT8）
# ⇒ **R2T2 的 ASR IR 全部删除**（encoder-int8 / decoder-gpu-int8 / encoder-fp16 /
#    decoder-npu-int8 / decoder-npu-int4 / embed_tokens_f16.npy）
# ⇒ 这里只剩 0.6B 的三样：encoder（fp16 static）、decoder（mask2 INT8）、embedding 表。
# ⚠️ **iGPU 与 NPU 共用同一份 IR**（只是编译目标设备不同）⇒ 只放一份。
_MODEL_ALIASES = {
    # 0.6B 编码器（fp16 static，静态形状 ⇒ NPU 可直接编，不需要冻结）
    'ov-encoder-06b-fp16-static': ['asr06b-encoder-fp16'],
    # 0.6B 解码器（mask2 INT8，带 attention_mask 端口，**无 KV cache**）
    'ov-dec-06b-embed-mask2-int8sym': ['asr06b-decoder-int8'],
    # 0.6B 的 embedding 表（hidden 1024，与 R2T2 的 2048 不同 ⇒ 独立文件名）
    'embed_tokens_06b_f16.npy': ['embed_tokens_06b_f16.npy'],
    # 0.6B 的 tokenizer / feature extractor 来源目录
    'asr06b-tokenizer': ['asr06b-tokenizer'],
}"""

# ② 引擎表：0.6B 两档 + 去掉 INT4 ASR 档
OLD_ENGINES = """    'gpu_int8': dict(label='Intel GPU · INT8', kind='ov', device='GPU.0',
                     enc='ov-encoder-segment-reviewer-int8asym', dec='ov-int8-past',
                     note='集显：编码器 INT8 + 解码器 INT8'),
    'gpu_int4': dict(label='Intel GPU · INT4', kind='ov', device='GPU.0',
                     enc='ov-encoder-segment-reviewer-int4', dec='ov-int4-lmhead-past',
                     note='集显：编码器 INT4 + 解码器 INT4（最快；61 分钟 WER 比 INT8 显著差约 1.3 个百分点）'),
    'npu_int8': dict(label='Intel NPU · INT8', kind='npu',
                     enc='ov-encoder-segment-reviewer', dec='qwen3-lm-int8sym-cleanie-ov',
                     note='编码器与解码器都在 NPU，不占 GPU'),
    'npu_int4': dict(label='Intel NPU · INT4（实验）', kind='npu',
                     enc='ov-encoder-segment-reviewer', dec=r'c089_int4\\R4',
                     note='实验配置：更快，但 61 分钟 WER 比 INT8 显著差约 2 个百分点'),"""

NEW_ENGINES = """    # 🔴🔴🔴 **APP-096**：ASR = **Qwen3-ASR-0.6B**（mask2 INT8）
    # ⚠️ **iGPU / NPU 两档用同一份 IR**（只是编译目标设备不同）。
    # ⚠️ **没有 INT4 档**：APP-095 1a 去掉 INT4 NPU 引擎；
    #    APP-096 又删掉了全部 R2T2 ASR IR ⇒ INT4 已无对应模型。
    'gpu_int8': dict(label='Intel GPU · INT8', kind='asr06b', device='GPU.0',
                     enc='ov-encoder-06b-fp16-static',
                     dec='ov-dec-06b-embed-mask2-int8sym',
                     note='集显：Qwen3-ASR-0.6B（编码器 FP16 + 解码器 INT8 mask2）'),
    'npu_int8': dict(label='Intel NPU · INT8', kind='asr06b', device='NPU',
                     enc='ov-encoder-06b-fp16-static',
                     dec='ov-dec-06b-embed-mask2-int8sym',
                     note='编码器与解码器都在 NPU，不占 GPU（Qwen3-ASR-0.6B INT8 mask2）'),"""

# ③ ASR_PRECISION：去掉 INT4 档
OLD_PRECISION = """ASR_PRECISION = {
    'gpu_int8': 'INT8', 'gpu_int4': 'INT4',
    'npu_int8': 'INT8', 'npu_int4': 'INT4',
    'cuda_q8': 'Q8_0', 'cuda_q4': 'Q4_K',
}"""
NEW_PRECISION = """ASR_PRECISION = {
    # 🔴🔴🔴 **APP-096**：MiniMVP 只有 0.6B INT8 两档（iGPU / NPU）⇒ **无 INT4 ASR 档**
    'gpu_int8': 'INT8',
    'npu_int8': 'INT8',
    'cuda_q8': 'Q8_0', 'cuda_q4': 'Q4_K',
}"""

# ④ OVEngine：接 0.6B 后端（kind == 'asr06b'）
OLD_OVENGINE = """        if self.cfg['kind'] == 'ov':
            from segment_encoder_backend import SegmentEncoderOVBackend
            on_log(f'加载 {self.cfg["label"]}（{self.cfg["dec"]}）…')
            self.backend = SegmentEncoderOVBackend(
                encoder_dir=enc, decoder_dir=dec, device=self.cfg['device'],
                precision='f16', cache_dir=_cache('ov_cache'))
            self.device_desc = self.cfg['device']
        else:"""
NEW_OVENGINE = """        if self.cfg['kind'] == 'asr06b':
            # 🔴🔴🔳 **APP-096**：Qwen3-ASR-0.6B（mask2 INT8）后端
            # ⚠️ 0.6B 的 decoder **无 KV cache**、静态 512、右对齐
            #    ⇒ 与 R2T2 的两套后端**接口相似但语义不同** ⇒ 独立实现。
            # ⚠️ NPU 上 **不设 NPUW_LLM**：0.6B decoder 不是 causal-LM-with-past 图
            #    （无 KV cache）⇒ 走 plain 编译即可（reviewer 的 NPU 档已实测跑通）。
            from asr06b_backend import ASR06BBackend
            on_log(f'加载 {self.cfg["label"]}（Qwen3-ASR-0.6B mask2 INT8）…')
            self.backend = ASR06BBackend(
                encoder_dir=enc, decoder_dir=dec,
                tokenizer_dir=_model_path('asr06b-tokenizer'),
                embed_npy=_model_path('embed_tokens_06b_f16.npy'),
                device=self.cfg['device'],
                precision='f16',
                cache_dir=_cache('ov_cache' if self.cfg['device'] != 'NPU'
                                 else 'npu_cache'))
            self.device_desc = self.cfg['device']
        elif self.cfg['kind'] == 'ov':
            from segment_encoder_backend import SegmentEncoderOVBackend
            on_log(f'加载 {self.cfg["label"]}（{self.cfg["dec"]}）…')
            self.backend = SegmentEncoderOVBackend(
                encoder_dir=enc, decoder_dir=dec, device=self.cfg['device'],
                precision='f16', cache_dir=_cache('ov_cache'))
            self.device_desc = self.cfg['device']
        else:"""

# ⑤ _check_models：0.6B 档的模型齐全性判定
OLD_CHECK = """        enc = _model_path(cfg['enc'])
        dec = _model_path(cfg['dec'])
        missing = []
        # 编码器
        if not (os.path.isdir(enc) and
                os.path.exists(os.path.join(enc, 'openvino_encoder_model.xml'))):
            missing.append('编码器')
        # 解码器：NPU 侧是 openvino_model.xml，GPU 侧是 openvino_decoder_model.xml
        if not os.path.isdir(dec):
            missing.append('解码器')
        else:
            has_xml = (os.path.exists(os.path.join(dec, 'openvino_model.xml')) or
                       os.path.exists(os.path.join(dec, 'openvino_decoder_model.xml')))
            if not has_xml:
                missing.append('解码器')
        # NPU 侧还需要 embedding 表
        if cfg['kind'] == 'npu':
            npy = _model_path('qwen3-lm-int8sym-cleanie-ov/embed_tokens_f16.npy')
            if not os.path.exists(npy):
                missing.append('embedding 表')"""
NEW_CHECK = """        enc = _model_path(cfg['enc'])
        dec = _model_path(cfg['dec'])
        missing = []
        if cfg['kind'] == 'asr06b':
            # 🔴🔴🔳 **APP-096**：0.6B 档的三件套
            #   编码器 = `ov-encoder-06b-fp16-static.xml`
            #   解码器 = `openvino_model.xml`（mask2 INT8）
            #   embedding 表 = `embed_tokens_06b_f16.npy`（hidden 1024）
            if not (os.path.isdir(enc) and os.path.exists(os.path.join(
                    enc, 'ov-encoder-06b-fp16-static.xml'))):
                missing.append('编码器')
            if not (os.path.isdir(dec) and os.path.exists(os.path.join(
                    dec, 'openvino_model.xml'))):
                missing.append('解码器')
            if not os.path.exists(_model_path('embed_tokens_06b_f16.npy')):
                missing.append('embedding 表')
            if not os.path.isdir(_model_path('asr06b-tokenizer')):
                missing.append('tokenizer')
            if missing:
                out[key] = (False, '缺 ' + '、'.join(missing))
            else:
                out[key] = (True, '模型齐全')
            continue
        # 编码器
        if not (os.path.isdir(enc) and
                os.path.exists(os.path.join(enc, 'openvino_encoder_model.xml'))):
            missing.append('编码器')
        # 解码器：NPU 侧是 openvino_model.xml，GPU 侧是 openvino_decoder_model.xml
        if not os.path.isdir(dec):
            missing.append('解码器')
        else:
            has_xml = (os.path.exists(os.path.join(dec, 'openvino_model.xml')) or
                       os.path.exists(os.path.join(dec, 'openvino_decoder_model.xml')))
            if not has_xml:
                missing.append('解码器')
        # NPU 侧还需要 embedding 表
        if cfg['kind'] == 'npu':
            npy = _model_path('qwen3-lm-int8sym-cleanie-ov/embed_tokens_f16.npy')
            if not os.path.exists(npy):
                missing.append('embedding 表')"""

# ⑥ 引擎 kind 说明（build_asr_options 的注释）
OLD_KIND_DOC = """    ⚠️ 三种 kind 的处理**完全不同**（这是本设计最易错的地方）：
    - kind=='ov'（gpu_int8/gpu_int4）：设备**可覆盖** ⇒ 与本机可用设备
      求交集逐个生成；但 **排除 NPU**（NPU 由 kind=='npu' 的 all-NPU
      交付后端承担，两条路会争用设备）。
    - kind=='npu'（npu_int8/npu_int4）：**设备写死 NPU**，不可覆盖
      （make_engine 注释明确「不接受覆盖」）。"""
NEW_KIND_DOC = """    ⚠️ 三种 kind 的处理**完全不同**（这是本设计最易错的地方）：
    - kind=='asr06b'（gpu_int8/npu_int8）：🔴🔴🔳 **APP-096** 的 0.6B 档
      ⇒ 设备**写死在引擎表里**（GPU.0 或 NPU），**不可覆盖**
      （iGPU 与 NPU 共用同一份 IR，只差编译目标设备）。
    - kind=='ov'：设备**可覆盖** ⇒ 与本机可用设备求交集逐个生成；
      但 **排除 NPU**（NPU 由 kind=='asr06b'/NPU 档承担，两条路会争用设备）。
    - kind=='npu'：**设备写死 NPU**，不可覆盖
      （make_engine 注释明确「不接受覆盖」）。"""


def patch_live_caption_app(text: str):
    """对 rc5 的 app/live_caption_app.py 应用全部定点补丁。"""
    patches = [
        ('aliases', OLD_ALIASES, NEW_ALIASES),
        ('engines', OLD_ENGINES, NEW_ENGINES),
        ('precision', OLD_PRECISION, NEW_PRECISION),
        ('ovengine', OLD_OVENGINE, NEW_OVENGINE),
        ('check', OLD_CHECK, NEW_CHECK),
        ('kind_doc', OLD_KIND_DOC, NEW_KIND_DOC),
    ]
    applied = []
    for tag, old, new in patches:
        text = patch_once(text, old, new, tag)
        applied.append(tag)
    # 语法闸门
    import ast
    ast.parse(text.replace('\r\n', '\n'), filename='app/live_caption_app.py')
    return text, applied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    dry = not args.run

    ev = {
        'built_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'version': VERSION,
        'base_pkg': BASE_PKG,
        'dst_pkg': DST_PKG,
        'corrections': ['APP-095 (1a only; 1b superseded by APP-096)', 'APP-096'],
        'dry_run': dry,
        'actions': [],
    }

    # ── 闸门 ①：rc4 在；rc5 不在（不覆盖）────────────────────────────
    if not os.path.isdir(BASE_PKG):
        print('!! rc4 不存在：%s' % BASE_PKG)
        return 2
    if os.path.exists(DST_PKG):
        print('!! rc5 目录已存在（拒绝覆盖，APP-055）：%s' % DST_PKG)
        return 2

    # ── 闸门 ②：物料齐全 ────────────────────────────────────────────
    need = [os.path.join(SRC_DEC, 'openvino_model.xml'),
            os.path.join(SRC_DEC, 'openvino_model.bin'),
            os.path.join(SRC_ENC, 'ov-encoder-06b-fp16-static.xml'),
            os.path.join(SRC_ENC, 'ov-encoder-06b-fp16-static.bin'),
            SRC_EMB]
    missing = [p for p in need if not os.path.exists(p)]
    if missing:
        print('!! 缺物料：%s' % missing)
        return 2
    tok_missing = [f for f in TOK_FILES
                   if not os.path.exists(os.path.join(SRC_HF, f))]
    ev['tokenizer_files_missing'] = tok_missing

    # ── rc4 的指纹（事后复核「一字未动」）────────────────────────────
    rc4_zip = os.path.join(HOME, 'shared', 'minimvp',
                           'Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip')
    rc4_fp = {'zip_sha256': sha256_file(rc4_zip) if os.path.exists(rc4_zip) else None,
              'zip_bytes': os.path.getsize(rc4_zip) if os.path.exists(rc4_zip) else None}
    n4, b4 = dir_stats(BASE_PKG)
    rc4_fp.update(files=n4, bytes=b4,
                  mtime=datetime.datetime.fromtimestamp(
                      os.path.getmtime(BASE_PKG)).isoformat(timespec='seconds'))
    ev['rc4_fingerprint_before'] = rc4_fp

    if dry:
        print('[dry-run] 将创建：%s' % DST_PKG)
        print('[dry-run] 删 R2T2 IR：%s'
              % (list(DROP_MODEL_DIRS) + list(DROP_MODEL_FILES),))
        print('[dry-run] 放 0.6B：%s / %s / %s / %s'
              % (PKG_DEC_DIR, PKG_ENC_DIR, PKG_EMB_FILE, PKG_TOK_DIR))
        print('[dry-run] app 补丁：aliases/engines/precision/ovengine/check/kind_doc')
        print('[dry-run] 另加 app/asr06b_backend.py')
        ev['dry_run_ok'] = True
        print(json.dumps(ev, ensure_ascii=False, indent=1))
        return 0

    t0 = time.time()
    # ── ① 复制 rc4 → rc5（真实拷贝，**不用硬链接**：rc4/rc3 曾因硬链接
    #    导致「原地写」串到源目录，见 §161 事故）────────────────────
    print('[1/7] 复制 rc4 → rc5（真实拷贝，不用硬链接）…')
    shutil.copytree(BASE_PKG, DST_PKG, symlinks=True)
    ev['actions'].append('copy rc4 -> rc5 (real copy, no hardlink)')

    models = os.path.join(DST_PKG, 'models')

    # ── ② 删掉全部 R2T2 ASR IR ──────────────────────────────────────
    print('[2/7] 删除 R2T2 ASR IR…')
    dropped = []
    for d in DROP_MODEL_DIRS:
        p = os.path.join(models, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
            dropped.append(d)
    for f in DROP_MODEL_FILES:
        p = os.path.join(models, f)
        if os.path.exists(p):
            os.remove(p)
            dropped.append(f)
    ev['actions'].append('drop R2T2 ASR IR: %s' % dropped)
    ev['dropped'] = dropped

    # ── ③ 放入 0.6B 物料 ────────────────────────────────────────────
    print('[3/7] 放入 0.6B IR / embedding 表 / tokenizer…')
    shutil.copytree(SRC_DEC, os.path.join(models, PKG_DEC_DIR))
    shutil.copytree(SRC_ENC, os.path.join(models, PKG_ENC_DIR))
    shutil.copy2(SRC_EMB, os.path.join(models, PKG_EMB_FILE))
    tok_dst = os.path.join(models, PKG_TOK_DIR)
    os.makedirs(tok_dst, exist_ok=True)
    for f in TOK_FILES:
        src = os.path.join(SRC_HF, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(tok_dst, f))
    ev['actions'].append('install 0.6B models/tokenizer')

    # ── ④ app 定点改写 ───────────────────────────────────────────────
    print('[4/7] 定点改写 rc5 的 app/live_caption_app.py…')
    app_py = os.path.join(DST_PKG, 'app', 'live_caption_app.py')
    with open(app_py, encoding='utf-8', newline='') as f:
        raw = f.read()
    patched, applied = patch_live_caption_app(raw)
    with open(app_py, 'w', encoding='utf-8', newline='') as f:
        f.write(patched)
    ev['actions'].append('patch app/live_caption_app.py: %s' % applied)
    ev['patch_ids'] = applied

    # ⑤ 新增 asr06b_backend.py（从开发树逐字复制）
    print('[5/7] 加入 app/asr06b_backend.py（开发树逐字复制）…')
    src_be = os.path.join(REPO, 'live_caption', 'asr06b_backend.py')
    shutil.copy2(src_be, os.path.join(DST_PKG, 'app', 'asr06b_backend.py'))
    ev['actions'].append('add app/asr06b_backend.py')

    # ⑥ README / G4 / release.json
    print('[6/7] 更新 README / G4_WHITELIST / release.json…')
    ev['actions'].append('docs: pending _app311 (separate script)')

    # ⑦ 指纹
    n5, b5 = dir_stats(DST_PKG)
    ev['rc5'] = {'files': n5, 'bytes': b5,
                 'mtime': datetime.datetime.fromtimestamp(
                     os.path.getmtime(DST_PKG)).isoformat(timespec='seconds')}
    ev['rc4_fingerprint_after'] = {'zip_sha256': sha256_file(rc4_zip)
                                   if os.path.exists(rc4_zip) else None,
                                   'files': dir_stats(BASE_PKG)[0],
                                   'bytes': dir_stats(BASE_PKG)[1]}
    ev['build_s'] = round(time.time() - t0, 1)
    ev['rc4_unchanged'] = (ev['rc4_fingerprint_before']['zip_sha256'] ==
                           ev['rc4_fingerprint_after']['zip_sha256'] and
                           ev['rc4_fingerprint_before']['files'] ==
                           ev['rc4_fingerprint_after']['files'])

    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[7/7] 完成：%s（%d 文件 / %.3f GB，用时 %.1f s）'
          % (DST_PKG, n5, b5 / 2 ** 30, ev['build_s']))
    print('证据：%s' % REPORT)
    print('rc4 未动：%s' % ev['rc4_unchanged'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
