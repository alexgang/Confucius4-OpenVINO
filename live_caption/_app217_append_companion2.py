#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 §7.6（预设 B 的 CER/WER + 抽听样本）**追加**到 §217 companion。"""
import hashlib
import os
import shutil
import sys
import tempfile

COMP = (r'C:\Users\Trekker-PTL\confucius4-openvino\status\app'
        r'\STATUS_APP_sec217_detail_20261120.md')

ADD = """
### 7.6 🟢 APP-116 §2 的最后一块：**预设 B（男声）**的 CER/WER 与抽听样本

**来源（reviewer 明文要求「写清来源模型、生成文本、参数和许可证」）**：
| 项 | 值 |
|---|---|
| 来源模型 | `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`（**Apache-2.0**，HF `cardData.license`） |
| 下载 | `https://hf-mirror.com/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` |
| 生成方法 | `model.generate_custom_voice(text=…, language="Chinese", speaker="Uncle_Fu")` |
| speaker | `Uncle_Fu`（Seasoned male voice, mellow timbre）——**模型自带音色**，非真人素材 |
| 生成文本 | 「你好，这是一段用于生成预设音色的参考音频。声音清晰平稳，没有背景噪音，语速适中，像平常说话一样朗读这段文字。」 |
| 后处理 | 首尾静音裁剪（RMS < −45 dBFS）→ onset 0.52 s → 截到 **10.0 s** → 峰值归一 **−3.0 dBFS** → 去直流 → 10 ms 淡入淡出 → PCM_16 |
| 成品 | `models/qwen3tts/voices/preset_B.wav` **480 044 B / 24 kHz / 单声道 / 10.0 s / peak 0.70798 / RMS −21.69 dBFS**／SHA256 `ad8e3e80fbada9f4…` |
| 合规自检 | 24 kHz ✓／单声道 ✓／8–12 s ✓／不削波 ✓／非静音 ✓／直流小 ✓／峰值归一 ✓ ⇒ **all_checks_pass=true** |
| 真人素材 | **无**（`no_human_material=true`）：不来自录音／同事音色／克隆音色／babelvox 样本 |

**回转写对比（OV ASR `models/ov-int8-past` / GPU.0，**逐句按句 id 配对**）**：
`results/app/app116_preset_eval/preset_eval.json` →

| 音色 | CER（中文，按字） | WER（英文，按词） | 打分句数 |
|---|---|---|---|
| **A（女声）** | **0.0048** | **0.0000** | 20 |
| **B（男声）** | **0.0048** | **0.0000** | 20 |

⇒ **预设 B 与预设 A 同一水平（逐项相等）** ⇒ 满足 reviewer「与 preset_A 同一水平」的要求。
（zh 20 句里 1 句 1 个字差；en 20 句**全对**。）

**抽听样本（用户点头前不进包）**：`results/app/app116_preset_b_listen/`（4 个）

| 文件 | 句 id | 语种 | 该句 err_rate | 字节 | SHA256 |
|---|---|---|---|---|---|
| `presetB_zh_01.wav` | 1 | zh | **0.0000** | 184 364 | `851e54cc8614f373…` |
| `presetB_zh_02.wav` | 2 | zh | **0.0000** | 199 724 | `777c8fcff5175969…` |
| `presetB_en_11.wav` | 11 | en | **0.0000** | 203 564 | `deb938847ec8e89c…` |
| `presetB_en_12.wav` | 12 | en | **0.0000** | 172 844 | `adc32a37d5e764a8…` |

🔴 **`preset_B.wav` 仍**未进包**（`preset_B_manifest.json` → `not_packaged_yet=true`）
⇒ 客户包 `Confucius4_LiveCaption_v2.5/models/qwen3tts/voices/` 里**只有** `preset_A.wav`
⇒ 客户机音色下拉**不会**列出「预设 B（男声）」⇒ **等用户抽听点头**。

🔴 **本轮在这条上踩的 3 个「脚本自身」坑**（都造出假 FAIL，且都**已修**）：
1. `backends.py` 里 `import qwen_asr` ⇒ 该包在 **ASR 线程的 vendor 目录**
   （`C:\\Users\\Trekker-PTL\\qwen3asr_06b\\vendor`）⇒ 不加路径 ⇒
   `ModuleNotFoundError: No module named 'qwen_asr'`；
2. `qwen_asr` 又要 **torch** ⇒ 客户包 python **没有 torch** ⇒ 改用
   `C:\\Users\\Trekker-PTL\\qwen3asr_06b\\.venv\\Scripts\\python.exe`
   （torch 2.11.0+cu128 ＋ openvino 2026.4.1 ＋ soundfile ＋ transformers 全齐）；
3. 🔴🔴 **`--dump-dir` 每句会落 1～2 个文件**（主段 `seg_<id>_<seq>.wav` ＋ 变速段
   `seg_<id>_<seq>_acc110.wav`）⇒ **20 句落 30 个文件** ⇒ 旧写法
   `sorted(os.listdir())` 取 `items[i]` 会**整段错位** ⇒ 改成
   **按句 id 匹配 `seg_<id>_*.wav` 且排除 `_acc110`**，参考文本也从 worker 的
   `synth_*.jsonl` 按 id 取（不再靠手写列表）。
⇒ 另加了 `--reuse-synth`（复用已落盘的合成结果，避免重跑 6 分钟 TTS）。
"""


def main():
    orig = open(COMP, encoding='utf-8').read()
    if '### 7.6' in orig:
        print('ABORT: companion 里已有 §7.6')
        return 1
    bak = os.path.join(tempfile.gettempdir(), 'STATUS_APP_sec217.bak2.md')
    shutil.copyfile(COMP, bak)
    new = orig + ADD
    checks = [
        ('新文本以原文为前缀', new.startswith(orig)),
        ('旧正文长度未变', len(orig) == len(open(bak, encoding='utf-8').read())),
        ('含 7.6 标题', '### 7.6' in new),
        ('含 CER 0.0048', '0.0048' in new),
        ('含抽听文件名', 'presetB_zh_01.wav' in new),
        ('含 Apache-2.0', 'Apache-2.0' in new),
    ]
    bad = [n for n, ok in checks if not ok]
    if bad:
        print('写前自检 FAIL：%s ⇒ 源文件零改动' % bad)
        return 1
    print('写前自检 %d/%d PASS' % (len(checks), len(checks)))
    tmp = COMP + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, COMP)
    back = open(COMP, encoding='utf-8').read()
    post = [
        ('旧正文逐字未变', back.startswith(orig)),
        ('字节数一致', len(back.encode('utf-8')) == len(new.encode('utf-8'))),
        ('§7.6 存在', '### 7.6' in back),
    ]
    bad = [n for n, ok in post if not ok]
    if bad:
        print('写后复核 FAIL：%s' % bad)
        return 1
    print('写后复核 %d/%d PASS' % (len(post), len(post)))
    print('companion：%d B → %d B（SHA %s）'
          % (len(orig.encode('utf-8')), len(back.encode('utf-8')),
             hashlib.sha256(back.encode('utf-8')).hexdigest()[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
