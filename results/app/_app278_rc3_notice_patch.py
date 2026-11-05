#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app278_rc3_notice_patch.py —— APP-072 闸门②：**NOTICE 补许可证署名**。

## 为什么需要这个脚本

APP-072 §2 闸门②：

> NOTICE 含 Qwen3-ASR、Qwen3-TTS、Hy-MT2、OpenVINO 许可证署名。

实测 rc3 的 `NOTICE`（9 643 B / 152 行，与 v2.2 逐字同源）**只有 Qwen3-TTS**，
**缺 Qwen3-ASR 与 Hy-MT2**（grep 0 命中）⇒ 闸门②**当前不满足**。

⇒ 本脚本做**定点字符串替换**（唯一命中断言），在 `NOTICE` 的
「模型与推理框架」节里补三条署名，并把首行版本号对齐到 MiniMVP v1.0-rc3
（§113 闸门：README_zh / README_en / NOTICE 三处版本号必须一致；
`README_zh.md` 首行已是 `MiniMVP v1.0-rc3`，`NOTICE` 首行还是 `v2.2`）。

## 许可依据（2026-11-05 实查，来源写进 STATUS）

| 模型 | 许可 | 依据 |
|---|---|---|
| Qwen3-ASR-0.6B | Apache-2.0 | Qwen3-ASR 技术报告（arXiv 2601.21337）明文「release these models under the Apache 2.0 license」；HF `Qwen/Qwen3-ASR-0.6B` cardData.license = apache-2.0 |
| Hy-MT2-1.8B | Apache-2.0 | HF `tencent/Hy-MT2-1.8B` cardData.license = apache-2.0（llm-explorer / surfmind / Arm 派生模型页三方一致，均标注 `apache-2.0`） |
| Qwen3-TTS-12Hz-0.6B-Base | Apache-2.0 | 已在原 NOTICE 中 |
| OpenVINO 2026.4.1 | Apache-2.0 | 已在依赖表；本脚本在「模型与推理框架」节补一条 runtime 署名 |

⚠️ **不声称随包附有模型许可证全文**（包内**没有**这三个模型的 LICENSE 文件）
⇒ 措辞只写「归属 + 许可 + 官方链接」，**不写**「许可证全文随包分发」。

## 用法
```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe results/app/_app278_rc3_notice_patch.py [--pkg <目录>] [--dry-run]
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
DEFAULT_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
REPORT = os.path.join(HERE, 'app278_rc3_notice_patch_evidence.json')
VERSION = 'MiniMVP v1.0-rc3'

# ── 定点替换块（**唯一命中**；每块都带前后锚点）─────────────────────
# ① 首行版本号：v2.2 → MiniMVP v1.0-rc3（§113 版本一致性闸门）
OLD_TITLE = ('Confucius4 LiveCaption v2.2 — '
              '第三方组件归属与许可证\n'
              '=====================================================\n')
NEW_TITLE = ('Confucius4 LiveCaption ' + VERSION +
             ' — 第三方组件归属与许可证\n'
             '=====================================================\n')

# ② Qwen3-ASR 署名（插在 Qwen3-TTS 段之后）
OLD_TTS_BLOCK = (
    'Qwen3-TTS-12Hz-0.6B-Base\n'
    '  Copyright Alibaba Cloud\n'
    '  模型权重，Apache-2.0\n'
    '  https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base\n'
    '\n'
)
NEW_TTS_BLOCK = OLD_TTS_BLOCK + (
    'Qwen3-ASR-0.6B\n'
    '  Copyright Alibaba Cloud\n'
    '  语音识别模型权重，Apache-2.0\n'
    '  https://huggingface.co/Qwen/Qwen3-ASR-0.6B\n'
    '  本包内形态：OpenVINO INT8 IR（models/encoder-int8/ 与\n'
    '                models/decoder-gpu-int8/）\n'
    '\n'
)

# ③ Hy-MT2 + OpenVINO runtime 署名（插在 Amphion 段之后）
OLD_AMPHION_BLOCK = (
    'Amphion（metis prompt.wav — 预设音色 A 的参考音频来源）\n'
    '  Amphion project，Apache-2.0\n'
    '  https://github.com/open-mmlab/Amphion\n'
    '\n'
)
NEW_AMPHION_BLOCK = OLD_AMPHION_BLOCK + (
    'Hy-MT2-1.8B\n'
    '  Copyright Tencent Hunyuan\n'
    '  翻译模型权重，Apache-2.0\n'
    '  https://huggingface.co/tencent/Hy-MT2-1.8B\n'
    '  本包内形态：OpenVINO INT4 IR（models/mt/mt2-int4sym-cw-q/）\n'
    '\n'
    'OpenVINO 2026.4.1（推理运行时）\n'
    '  Copyright Intel Corporation\n'
    '  Apache-2.0（另含 oneDNN / oneTBB 第三方条款，见\n'
    '                python/Lib/site-packages/openvino-2026.4.1.dist-info/licensing/）\n'
    '  https://github.com/openvinotoolkit/openvino\n'
    '\n'
)

BLOCKS = (
    ('title_version', OLD_TITLE, NEW_TITLE),
    ('qwen3_asr', OLD_TTS_BLOCK, NEW_TTS_BLOCK),
    ('hymt2_openvino', OLD_AMPHION_BLOCK, NEW_AMPHION_BLOCK),
)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    notice = os.path.join(a.pkg, 'NOTICE')
    before = open(notice, 'rb').read()
    out = {
        'pkg': a.pkg, 'notice': notice,
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'before': {'sha256': sha256_bytes(before), 'bytes': len(before)},
        'blocks': [],
    }

    text = before.decode('utf-8')
    for name, old, new in BLOCKS:
        n = text.count(old)
        out['blocks'].append({'name': name, 'hits': n})
        if n != 1:
            out['verdict'] = 'FAIL'
            out['reason'] = f'锚点「{name}」命中 {n} 次（要求恰好 1 次）'
            print(json.dumps(out, ensure_ascii=False, indent=1))
            return 1
    if a.dry_run:
        out['verdict'] = 'DRY_RUN_OK'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    for name, old, new in BLOCKS:
        text = text.replace(old, new, 1)

    after = text.encode('utf-8')
    if b'\r\n' in before:
        after = after.replace(b'\n', b'\r\n')
    with open(notice, 'wb') as f:
        f.write(after)

    # 写后复核：行尾、必含项
    chk = open(notice, 'rb').read()
    t = chk.decode('utf-8')
    out['after'] = {'sha256': sha256_bytes(chk), 'bytes': len(chk)}
    out['crlf_preserved'] = (b'\r\n' in before) == (b'\r\n' in chk)
    out['contains'] = {k: (k in t) for k in (
        'Qwen3-ASR-0.6B', 'Qwen3-TTS-12Hz-0.6B-Base', 'Hy-MT2-1.8B',
        'OpenVINO 2026.4.1', 'BabelVox', 'babelvox-openvino-int8')}
    out['title_line1'] = t.split('\n', 1)[0]
    ok = all(out['contains'].values()) and out['crlf_preserved']
    out['verdict'] = 'PASS' if ok else 'FAIL'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
