#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app299_rc4_make_payload.py —— 生成 §161 的 STATUS payload（MiniMVP rc4）。

「更新时间」用 **Get-Date 实测值**（`--updated` 参数传入，禁止推算）。
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'app299_rc4_status_payload.json')

BODY = """
## §161 MiniMVP rc4：补打包全 NPU ASR 模型（用户直驱，2026-11-10）

**本条不是 reviewer 纠偏**（`last_ack` 仍是 **APP-088**）⇒ 纠偏链 **APP-089…092 未动**（那 4 条是上一轮读到的，见下「⑥ 遗留」）。

### ① 交付物
* **新目录** `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_MiniMVP_v1.0-rc4`（**rc3 一字未改**，见「④ 事故与修复」）。
* 补 3 个 NPU IR（源 = `Confucius4_LiveCaption_v2.4/models/`，与 v2.2 **逐字节同 SHA**）：

| 包内目录 | 逻辑名（`_MODEL_ALIASES`） | 文件 | 字节 |
|---|---|---|---|
| `models/encoder-fp16` | `ov-encoder-segment-reviewer` | 2 | 635 969 904 |
| `models/decoder-npu-int8` | `qwen3-lm-int8sym-cleanie-ov` | 2 | 1 724 957 980 |
| `models/decoder-npu-int4` | `c089_int4/R4` | 2 | 1 165 047 365 |

* **iGPU 版模型保留**：`encoder-int8` / `decoder-gpu-int8` 均在（`app291` 证据 `igpu_models_kept`）。
* **体积**：rc3 **6.68 GB** → rc4 **9.97 GB**（**+3.28 GB**／`delta_bytes=3525975249`）；文件数 10 474 → **10 510**。

### ② `--check` 验收（干净目录 `C:\\minimvp_rc4_clean\\`，用**包内 python**）
`[ OK ] **Intel NPU · INT8  模型齐全**` ／ `[ OK ] Intel NPU · INT4（实验）  模型齐全`
⇒ **用户要求 2 达成**（证据 `results/app/app298_rc4_check_output.txt`）。

### ③ 设备级验收（5 min 英文 SPE `shared/SPE_0000_0500.wav` 300.0 s）
* **实际执行设备（OpenVINO `EXECUTION_DEVICES` 直证，`app296`）**：
  `encoder = NPU` ／ `decoder = NPU` ⇒ **两者的实际执行设备都是 NPU**（`verdict=EXEC_ON_NPU_OK`）。
* **WER / RTF / 延迟 / 内存**（参考 = 同一段音频的离线转写 921 词，**非人工校对稿** ⇒ 两档可比）：

| 档 | RTF | 出字延迟中位 | 最大积压 | 峰值内存 | WER vs 参考 | NPU-vs-iGPU |
|---|---|---|---|---|---|---|
| ASR=NPU（TTS off） | **0.803** | 540 ms | 1.1 s | 5 212.6 MB | **15.5266 %**（143 编辑/819 词） | **2.5610 %**（21 编辑） |
| ASR=GPU.0（TTS off） | **0.696** | 376 ms | 1.2 s | 4 819.5 MB | **14.5494 %**（134 编辑/820 词） | — |
| ASR=NPU + TTS=NPU | 1.264 | 55 362 ms | 84.4 s | 5 213.1 MB | — | — |

⇒ **NPU 档质量与 iGPU 档基本一致**（两档直接只差 2.56 %）；**NPU 比 iGPU 慢 ~15 %**（RTF 0.803 vs 0.696）、峰值内存多 ~393 MB。
🔴 **第三行不是 ASR 慢**：ASR 与 TTS **抢同一个 NPU** ⇒ 积压 84.4 s ⇒ **全 NPU 家家桶当前不可用于实时字幕**（TTS 需走 iGPU）。
* **素材可自证**：`SPE_0000_0500.wav` 与 `test_audio/260902_SPE_audio.wav` 前 300 s **逐样本相关系数 1.000000**。

### ④ 🔴 事故与修复（必须记录）
* **事故**：`_app291` 用 `copytree(copy_function=os.link)` 把 rc3 复制成 rc4 ⇒ **rc4 与 rc3 共享 inode**；随后「原地写」改版本号 ⇒ **写穿 ⇒ rc3 的 `NOTICE`/`README_zh.md`/`README_en.md` 被一起改成 rc4 字样**（违反「不改已交付的 rc3」）。
* **修复**：`_app292` 用**已交付 zip** `shared/minimvp/..._perftest_rev2.zip` 里的权威字节**断链重写** rc3 ⇒ rc3 三文件与 zip **逐字节相同**（复核 PASS）；rc4 保留 rc4 字样、inode 已分离。
* **根因修法**：`_app291` 的 `patch_text`／`MANIFEST` 写入改为 **`unlink_then_write`（断链后写）** ⇒ 不会再写穿。
* 🔴 **教训**：**硬链接复制 ⇒ 任何原地写都会波及源**。凡「要改写的文件」必须先断链。

### ⑤ 🔴 Meteor Lake（Ultra 7 155H）可移植性（用户要求 4）
* **包内预编译缓存 = 0 个**（`app291.precompiled_cache_in_pkg=[]`）⇒ **不带任何 Panther Lake 专属 blob**；编译缓存写在 `%LOCALAPPDATA%\\Confucius4LiveCaption\\npu_cache` ⇒ **目标机首次运行现编**。
* 🔴 **NPU decoder 必须用 NPUW**（`app290` 实测四臂）：

| 臂 | 结果 | 原因 |
|---|---|---|
| decoder + `NPU_USE_NPUW`+`NPUW_LLM` | ✅ 10.7 s，EXEC=NPU | |
| decoder + 仅 `NPU_USE_NPUW` | ❌ | `to_shape was called on a dynamic shape` |
| decoder + 完全不开 NPUW | ❌ | 同上 |
| encoder **冻结形状后** + plain（**不开 NPUW**） | ✅ 25.3 s，EXEC=NPU | 冻结前 ❌ `IE.Reshape doesn't support dynamic shapes` |

⇒ **decoder 没有「不开 NPUW」的回落路径** ⇒ 若目标机 NPUW 不可用，**NPU ASR 起不来**（encoder 不受影响）。
⇒ 已把该风险与「先用 iGPU 档验收」写进 rc4 的 `README_perftest.txt`。
⚠️ **未自行改属性口径**（改属性＝改行为，需 reviewer 裁定）。

### ⑥ 遗留 / 未做
* **纠偏 APP-089…092 仍未执行**（上一轮读到 4 条新纠偏：APP-089 ICL 去除＋self_ref＋换人切段／APP-090 EXT v0.3.4＋各项移植／APP-091 用户三项决定／APP-092 方案 B＋EXT v0.3.5）⇒ **本轮用户改任务为 MiniMVP rc4，故未动**；`last_ack` 保持 **APP-088**。
* **未打 rc4 zip**（本轮只建目录；zip 待用户确认，遵循「不主动打包」纪律）。
* **未提交 git**（本条脚本/证据待与 APP-089 侧改动一并处理，避免混入别的模块未提交改动）。
"""

RECENT = ('> 🔴 2026-11-10 ｜ **MiniMVP rc4 已建**：补 `encoder-fp16`／'
          '`decoder-npu-int8`／`decoder-npu-int4`（+3.28 GB）⇒ `--check` 显示「**Intel NPU · '
          'INT8 模型齐全**」；设备级：EXEC_DEVICES encoder=NPU／decoder=NPU、WER 15.53 %'
          '（iGPU 14.55 %，两档直接差 2.56 %）、RTF 0.803（iGPU 0.696）、峰值内存 5 212.6 MB；'
          '**包内 0 个预编译 blob** ⇒ 目标机现编；🔴 rc3 曾被硬链接写穿，已用已交付 zip '
          '权威字节**逐字节复原**并复核 PASS。')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--updated', required=True,
                    help='Get-Date 实测值（禁止推算）')
    args = ap.parse_args()
    payload = {
        'last_ack': 'APP-088',
        'updated': args.updated,
        'current_task': (
            '**MiniMVP rc4 已建**（补 3 个 NPU ASR IR，+3.28 GB）＋ `--check` 显示「Intel NPU '
            '· INT8 模型齐全」＋ 设备级验收完成（EXEC_DEVICES 双 NPU；WER 15.53 % vs iGPU '
            '14.55 %；RTF 0.803 vs 0.696；峰值内存 5 212.6 MB）⇒ **等用户确认是否打 rc4 zip**'),
        'blocked': (
            '**用户确认**：① 是否打 rc4 zip（未打，遵循「不主动打包」）② Meteor Lake 目标机：'
            'decoder **必须** NPUW（无回落路径，`app290` 实测）⇒ 若目标机 NPUW 不可用需改用 '
            'iGPU 档 ③ **纠偏 APP-089…092 仍未执行**（本轮用户改任务为 MiniMVP rc4）'),
        'recent_line': RECENT,
        'sec_body': BODY,
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print('payload written: %s (sec_body %d B)'
          % (OUT, len(BODY.encode('utf-8'))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
