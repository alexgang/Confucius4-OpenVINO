#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app135_probe_gencfg.py — **APP-135 §2 的关键探针：GenAI 会不会吃模型默认值**。

## reviewer APP-135 §2 原文
> **解码参数必须显式设**：MT3 目录里的 `generation_config.json` 默认
> `do_sample=true`、`temperature 0.7`、`top_k 20`、`top_p 0.8`。
> App 要继续显式用现在的口径（**贪心** + `repetition_penalty 1.05` +
> 现有 `max_new_tokens`），**不能吃模型默认值**。
> 用**单测断言实际生效的是贪心**。

## 本探针回答的问题（**只读，不改任何东西**）

`openvino_genai.LLMPipeline` 有 `get_generation_config()`。
🔴 **要查清**：`LLMPipeline(model_dir, ...)` 构造后，
`pipeline.get_generation_config()` 里的 `do_sample` 到底是
① **True**（吃到了模型 `generation_config.json` 的 `do_sample=true`）
还是 ② **False**（GenAI 自己的默认）。

⇒ 这决定 App 侧「显式设 `do_sample=False`」是**必需**还是**多余**，
也决定**只测 `og.GenerationConfig()` 的默认值够不够**。

## 🔴 纪律
* **只读**：只加载模型、读配置，**不生成**、**不写**任何文件；
* 用**包内 python**（APP-120 血泪：判「包能否用」用客户解释器）；
* MT3 模型在**开发机**（`hy_bench/ov/mt3-int8sym-cw-q`）⇒ 不动任何客户包。

## 用法
```
<pkg>\python\python.exe live_caption\_app135_probe_gencfg.py \
    --model C:\Users\Trekker-PTL\hy_bench\ov\mt3-int8sym-cw-q
```
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True, help='MT 模型目录')
    ap.add_argument('--device', default='GPU.0')
    ap.add_argument('--out', default='', help='证据 json 落盘路径')
    args = ap.parse_args()

    import openvino_genai as og

    ev = {
        'script': '_app135_probe_gencfg.py',
        'task': 'APP-135 §2：探针「GenAI 会不会吃模型 generation_config.json 的默认值」',
        'model': args.model,
        'device': args.device,
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    # ① 模型自带的 generation_config.json
    gcfg_path = os.path.join(args.model, 'generation_config.json')
    if os.path.isfile(gcfg_path):
        with open(gcfg_path, encoding='utf-8') as fh:
            ev['model_generation_config'] = json.load(fh)
    else:
        ev['model_generation_config'] = None

    # ② `og.GenerationConfig()` 的**裸默认**
    raw = og.GenerationConfig()
    ev['raw_generation_config'] = {
        k: (list(getattr(raw, k)) if isinstance(getattr(raw, k, None), set)
            else getattr(raw, k, '<no attr>'))
        for k in ('do_sample', 'temperature', 'top_k', 'top_p',
                  'repetition_penalty', 'max_new_tokens', 'apply_chat_template')}

    # ③ 🔴 **承重**：加载模型后 `pipeline.get_generation_config()` 的实际值
    ev['pipeline_get_generation_config'] = None
    ev['pipeline_error'] = None
    t0 = time.time()
    try:
        pipe = og.LLMPipeline(args.model, args.device,
                              PERFORMANCE_HINT='LATENCY',
                              CACHE_DIR=os.path.join(
                                  os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'),
                                  'Confucius4LiveCaption', 'mt_cache'))
        ev['pipeline_load_s'] = round(time.time() - t0, 2)
        g = pipe.get_generation_config()
        ev['pipeline_get_generation_config'] = {
            k: (list(getattr(g, k)) if isinstance(getattr(g, k, None), set)
                else getattr(g, k, '<no attr>'))
            for k in ('do_sample', 'temperature', 'top_k', 'top_p',
                      'repetition_penalty', 'max_new_tokens',
                      'apply_chat_template')}
    except Exception as e:
        ev['pipeline_error'] = repr(e)

    # ④ 结论（**自动判定**，不靠人读）
    g = ev['pipeline_get_generation_config']
    if g is None:
        ev['verdict'] = 'UNKNOWN（pipeline 加载失败 ⇒ 不下结论）'
    else:
        ev['verdict'] = (
            'PIPELINE_PICKS_UP_MODEL_DEFAULTS' if g.get('do_sample') is True
            else 'PIPELINE_DOES_NOT_PICK_UP_MODEL_DEFAULTS')
        ev['app_must_set_do_sample_false'] = (g.get('do_sample') is True)

    print(json.dumps(ev, ensure_ascii=False, indent=1))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        tmp = args.out + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(ev, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, args.out)
        print('证据：%s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
