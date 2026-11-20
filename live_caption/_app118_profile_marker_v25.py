#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §1：**写 v2.5 的包形态标记** `package_profile.json`（完整版 = 全集）。

## 为什么要有这个文件（reviewer APP-118 §2）
> 「`package_profile.json` 新增 `full`（allow_cuda=True、allow_clone_voice=True、
> asr 两种、10 语种），**作为默认配置**。」

🔴 **这个文件放包根**（与 `release.json` 同级），**不是** `app/` 下
  ⇒ `app/` 下的文件会被同步脚本逐个改写 ⇒ 标记放那里容易被覆盖。

## 内容（**与 `live_caption/package_profiles.py` 的 `PROFILE_RULES['full']['marker']` 一致**）
| 字段 | 值 | 含义 |
|---|---|---|
| `profile` | `"full"` | 包形态（`package_profile.PROFILE`） |
| `allow_cuda` | `true` | **允许** CUDA TTS 档（完整版自带 `cuda_env/`） |
| `allow_clone_voice` | `true` | **提供**音色克隆（完整版保留） |
| `target_langs` | `10` | 目标语言种数 |

🔴 **写前必须先验**：包里**没有**旧的 `package_profile.json`
  ⇒ **不是覆盖**（万一有 ⇒ 停下报告，不静默覆盖）。

## 纪律
- **只写这一个文件**（包根）⇒ 不碰 `app/`、不碰 `models/`；
- 写盘走 **临时文件 → `os.replace`**（不截断）；
- 写后**回读复核**（JSON 可解析 + 四个字段逐个相等）。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
MARKER = os.path.join(PKG, 'package_profile.json')

MARKER_CONTENT = {
    'profile': 'full',
    'allow_cuda': True,
    'allow_clone_voice': True,
    'target_langs': 10,
    'note': ('用户 2026-11-20 决定（APP-118）：**完整版 = 默认「全集」环境** —— '
             '含 CUDA TTS（cuda_env/ + models/tts_cuda/）、Qwen3-ASR 0.6B stateful '
             'INT8（作为可选项，默认仍是 R2T2 1.7B）、10 语种、EXT v0.4.18。'
             'MiniMVP / SpecialMVP 以后都从本包按 profile 裁剪。'),
}


def main():
    if not os.path.isdir(PKG):
        print('FAIL: 包目录不存在 %s' % PKG)
        return 2
    if os.path.exists(MARKER):
        print('🔴 目标已存在（不静默覆盖）：%s' % MARKER)
        try:
            print('  现有内容：%s' % open(MARKER, encoding='utf-8').read()[:400])
        except Exception:
            pass
        return 1
    tmp = MARKER + '.tmp_app118'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(MARKER_CONTENT, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, MARKER)
    # 写后复核
    got = json.load(open(MARKER, encoding='utf-8'))
    ok = all(got.get(k) == v for k, v in MARKER_CONTENT.items()
             if k in ('profile', 'allow_cuda', 'allow_clone_voice',
                      'target_langs'))
    print('已写：%s（%d B）' % (MARKER, os.path.getsize(MARKER)))
    print('复核：%s' % ('PASS' if ok else 'FAIL'))
    if not ok:
        print('  实际：%s' % got)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
