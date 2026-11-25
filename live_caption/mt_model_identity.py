#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mt_model_identity.py — **翻译模型的唯一事实来源**（APP-135）。

## 为什么单独一个模块

reviewer APP-135 §4 要求：打包清单/MANIFEST 生成脚本里，MT 条目的
**模型名、来源、safetensors SHA 与 IR bin SHA** 都要改成 MT3 的。
🔴 若这些值**散落在多个脚本里各写一份** ⇒ 换模型时必然漏改一处
⇒ **本模块把它们收到一处**，打包清单与 README 脚本都**从这里引用**。

## MT3 身份（**APP-135 轮实测**，与 reviewer 给的值逐字一致）

| 项 | 值 |
|---|---|
| 模型名 | `Hy-MT3-1.8B` |
| 来源 | `ModelScope Tencent-Hunyuan/Hy-MT3-1.8B` |
| 源 safetensors SHA256 | `60f9eeed302c887606f4fee9e96a3113b751123a5132651fdcfd39f2a82bf9f6`（3 582 202 056 B） |
| IR bin SHA256 | `ce1911275929d30612cddbde27f707aac8498f58df9f1c47dcf38d2ca5db1285`（1 792 991 738 B） |
| 包内目录名 | `mt3-int8sym-cw-q`（INT8 对称**按通道**，与 MT2 同口径） |

## 🔴 切回 MT2 的开关
环境变量 `LIVECAP_MT_VARIANT=mt2`（默认 `mt3`）——
**实现见 `translator.py` 的 `_MT_VARIANT` / `_MT_DIR`**（本模块只提供**元数据**）。

## 为什么不放「设备/速度」这类性能数
性能数会随机器/驱动变 ⇒ **不进本模块**（进 `results/app/` 的实测证据）。
"""
from __future__ import annotations

#: 当前**默认**变体（APP-135：默认 MT3）
DEFAULT_VARIANT = 'mt3'

#: 两个变体的元数据（**按 `LIVECAP_MT_VARIANT` 选**，默认 `mt3`）
MT_VARIANTS = {
    'mt3': {
        'name': 'Hy-MT3-1.8B',
        'source': 'ModelScope Tencent-Hunyuan/Hy-MT3-1.8B',
        'dir_name': 'mt3-int8sym-cw-q',
        'quantization': 'INT8_SYM per-channel（按通道）',
        'src_safetensors_sha256':
            '60f9eeed302c887606f4fee9e96a3113b751123a5132651fdcfd39f2a82bf9f6',
        'src_safetensors_bytes': 3582202056,
        'ir_bin_sha256':
            'ce1911275929d30612cddbde27f707aac8498f58df9f1c47dcf38d2ca5db1285',
        'ir_bin_bytes': 1792991738,
        'hidden_size': 2048,
        'num_hidden_layers': 32,
        'note': ('MT3 与 MT2 的 xml / tokenizer.json / chat_template.jinja / '
                 'tokenizer IR **逐字节相同** ⇒ 现有 tokenizer/模板代码可直接用，'
                 '**只换模型目录**。'),
    },
    'mt2': {
        'name': 'Hy-MT2-1.8B',
        'source': 'ModelScope Tencent-Hunyuan/Hy-MT2-1.8B',
        'dir_name': 'mt2-int8sym-cw-q',
        'quantization': 'INT8_SYM per-channel（按通道）',
        'src_safetensors_sha256': None,
        'src_safetensors_bytes': None,
        'ir_bin_sha256': None,
        'ir_bin_bytes': None,
        'hidden_size': 2048,
        'num_hidden_layers': 32,
        'note': '切回开关 `LIVECAP_MT_VARIANT=mt2` 用的旧变体（APP-135 保留）。',
    },
}


def current_variant() -> str:
    """按 `LIVECAP_MT_VARIANT` 返回当前变体（未知取值 ⇒ 默认 `mt3`）。"""
    import os
    v = (os.environ.get('LIVECAP_MT_VARIANT') or DEFAULT_VARIANT).strip().lower()
    return v if v in MT_VARIANTS else DEFAULT_VARIANT


def identity(variant: str = None) -> dict:
    """返回该变体的**元数据**（含模型名/来源/两个 SHA）。"""
    v = variant or current_variant()
    return dict(MT_VARIANTS.get(v, MT_VARIANTS[DEFAULT_VARIANT]))


def describe() -> dict:
    d = identity()
    d['variant'] = current_variant()
    d['default_variant'] = DEFAULT_VARIANT
    return d


if __name__ == '__main__':
    import json as _json
    print(_json.dumps(describe(), ensure_ascii=False, indent=1))
