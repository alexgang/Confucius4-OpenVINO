#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §4：**重写 MiniMVP v1.1.1 的中/英 README**（面向客户，去内部编号）。

## reviewer 原文（APP-121 §4）
1. README 写「解压后 10 904 个文件 / 6 702 027 740 B」⇒ 要改成
   **zip 解压后的实际数字**（zip 里的文件清单，不是目录里的）；
2. 面向客户的 README **去掉内部编号和研发用语**：
   APP-119/120、ASR-065/066、「v2.5 全集」、「R2T2」、「handoff」；
3. 已知问题**加一条**：讲话密集时配音会比原声滞后（10 分钟实测最大约 43 s、
   结束时约 30 s），然后会自动加速追上，最高 1.7×；
4. 「怎么改设备」的示例在第 1 条修好之前不要用 ASR=NPU；修好后可以保留；
5. 「首字延迟 0.39 s」其实是 **TTS 状态行里的首包**；
   **字幕出字延迟中位 303 ms**（来自 log 的 `[gpu_int8]` 行）⇒ 两个数分开写。

## 纪律
- **文件数/字节数取自 zip 清单**（`pkg_exclude.iter_package_files`）
  ⇒ 与 zip 内实际内容一致；
- 🔴 **自指大小迭代到不动点**（README 自己进包 ⇒ 改 README 会改总字节数）
  ⇒ 迭代写盘直到「写进去的字节数 == 磁盘实测的字节数」；
- 验收数字（若已有证据 json）**自动注入**；没有就写「待实测」⇒ **不编造**；
- 只写 `README_zh.md` / `README_en.md` 两个文件，**不动其它任何文件**。

## 用法
```
python live_caption/_app121_write_readme.py --pkg <v1.1.1 目录> --accept <验收证据 json>
```
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
sys.path.insert(0, REPO)

import pkg_exclude                                                  # noqa: E402

PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1.1')
VERSION = '1.1.1'
PKG_TITLE = 'MiniMVP v%s' % VERSION


def fmt_int(n):
    return '{:,}'.format(int(n)).replace(',', ' ')


def zip_content_stats(pkg):
    """🔴 **按 zip 清单**统计文件数 / 字节数 / 顶层构成（不是目录 walk）。"""
    files = list(pkg_exclude.iter_package_files(pkg))
    top = {}
    models = {}
    for rel, size in files:
        key = rel.split('/')[0] if '/' in rel else '(根文件)'
        top[key] = top.get(key, 0) + size
        if rel.startswith('models/'):
            mk = '/'.join(rel.split('/')[:2]) if rel.count('/') >= 1 else rel
            models[mk] = models.get(mk, 0) + size
    return {'files': len(files), 'bytes': sum(s for _r, s in files),
            'top': dict(sorted(top.items(), key=lambda kv: -kv[1])),
            'models': dict(sorted(models.items(), key=lambda kv: -kv[1]))}


def top_level(pkg):
    return [n for n in sorted(os.listdir(pkg)) if not n.startswith('.')]


def load_accept(path):
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def build_zh(st, tops, acc):
    L = []
    A = L.append
    A('# Confucius4 实时字幕 · %s（最小客户包）' % PKG_TITLE)
    A('')
    A('**本包是独立于其它版本的新产品线（MiniMVP），版本号单独编号。**')
    A('')
    A('## 里面有什么')
    A('')
    A('| 模块 | 模型 | 精度 | 默认设备 |')
    A('|---|---|---|---|')
    A('| 语音识别 | **Qwen3-ASR-0.6B**（stateful INT8（KV cache）） | INT8 '
      '| Intel 集显 GPU.0（Intel iGPU） |')
    A('| 翻译 | **Hy-MT2-1.8B**（**INT8-CW**） | **INT8**（对称 · 按通道 weight） '
      '| Intel 集显 GPU.0（Intel iGPU） |')
    A('| 语音输出 | **Qwen3-TTS 0.6B**（INT8 权重 · FP16 计算） | INT8/FP16 '
      '| Intel NPU |')
    A('')
    A('* **包含**：实时翻译配音**插件与桥接服务**（`ext/` 目录），'
      '桌面/命令行启动脚本（`Start_LiveCaption.bat` / `Start_Bridge.bat`）。')
    A('* **不含**：NVIDIA/CUDA 与 torch 相关内容（**无 `cuda_env/`、无 '
      '`models/tts_cuda/`**）、其它识别模型、MT 的 INT4 量化、'
      '开发与测试脚本、会议录音、**克隆音色**（本产品线禁用 ⇒ 只有内置预设音色 A）、'
      '说话人旁路模型。')
    A('* **音色**：只有**预设 A**（`models/qwen3tts/voices/preset_A.wav`）。'
      '预设 B 尚未定稿，**不进本包**。')
    A('* **目标语言**：10 种。')
    A('* **出厂默认设备**：**ASR=Intel 集显 GPU.0，MT=Intel 集显 GPU.0，'
      'TTS=Intel NPU**（唯一事实来源 = `app/device_config.py` 的 '
      '`DEFAULT_DEVICES`）。')
    A('  🔴 **推理设备完全由你自由配置**：三个模块可以放在任意加速器上，'
      '**没有「不能同时放在 NPU」的限制**。')
    A('  ⚠️ 若本机 `%LOCALAPPDATA%\\Confucius4LiveCaption\\device_config.json` '
      '是**旧版本**（本包之前写的），App 会**忽略**其中的设备项并改用出厂默认，'
      '并在日志里写明忽略了哪些旧值（配置文件**不会被删除**）。')
    A('')
    A('### 识别模型配方')
    A('')
    A('* **Qwen3-ASR-0.6B**，**stateful INT8（KV cache）**（按通道 INT8 权重、'
      'lm_head 保 FP16、带真实 `attention_mask` 端口）。同一套 IR 可编到集显'
      '（`--engine gpu_int8`）或 NPU（`--engine npu_int8`）。')
    A('* **NPU 上的 prompt 上界 = 320**（比集显的 512 更小）⇒ 出字延迟与 RTF 更低。')
    A('* **超长前缀按 token 从左截断**（保留右端＝最近的内容）：'
      '计数写在日志字段 `prefix_truncations` 里，**不抛错、不回退 512**。')
    A('* **段长前提**：单段 ≤ **20 s**（`MAX_SEG_SEC`）；'
      '若「模板 + 音频 token」本身就超过 320 ⇒ **显式报错**（不会静默出错）。')
    A('* **单段解码出错不会中断整条识别**：App 会记录日志与计数并**跳过该段继续**'
      '（日志关键字 `[asr-loop]`，运行结束时会打印累计次数）。')
    A('* **encoder 分档是可选开关，默认关闭**（`--asr-enc-tiers on/off`）：'
      '开启后运行时构建 400/800/1600/2400 四档，**任一档构建失败自动退回 '
      '2400 单档**（不残留半截分档）。默认关闭时行为与优化前完全一致。')
    A('')
    A('### 翻译模型配方')
    A('')
    A('* **Hy-MT2-1.8B**，**INT8-CW**（**INT8_SYM · 按通道**，'
      '`mt2-int8sym-cw-q`；hidden_size 2048 / 32 层）'
      '⇒ **本包只带 INT8-CW，不带 INT4**；翻译设备默认 **GPU.0**。')
    A('')
    A('### 包体积（实测）')
    A('')
    A('解压后 **%s 个文件 / %s B（%.3f GiB）**。'
      % (fmt_int(st['files']), fmt_int(st['bytes']), st['bytes'] / 1024 ** 3))
    if acc.get('zip_bytes'):
        A('打包成 zip 后 **%s B（%.3f GiB）**。'
          % (fmt_int(acc['zip_bytes']), acc['zip_bytes'] / 1024 ** 3))
    else:
        A('（zip 大小见发布说明。）')
    A('')
    A('顶层目录体积构成（实测，**只统计真正进包的文件**）：')
    A('')
    A('| 顶层目录 | 字节 |')
    A('|---|---|')
    for k, v in st['top'].items():
        A('| `%s` | %s |' % (k, fmt_int(v)))
    A('')
    A('## 怎么启动')
    A('')
    A('双击 `Start_LiveCaption.bat`（GUI），或在命令行里'
      '（**不传设备参数**即可用出厂默认）：')
    A('')
    A('```')
    A('python\\python.exe app\\live_caption_app.py')
    A('```')
    A('')
    A('## 怎么改设备')
    A('')
    A('**图形界面**：顶栏下方有**三个分区**——「ASR 识别」「翻译」「语音输出」，'
      '每个分区各有一个**设备 + 精度**组合下拉，改完等状态栏显示「就绪 ready」'
      '即可。三个模块互相独立，**可以都放 NPU，也可以任意组合**。')
    A('')
    A('**命令行**（等价参数）：')
    A('')
    A('| 参数 | 作用 |')
    A('|---|---|')
    A('| `--asr-device` | 识别设备（`GPU.0` / `NPU`） |')
    A('| `--mt-device` | 翻译设备（`GPU.0` / `NPU`） |')
    A('| `--tts-device` | 语音输出设备（`GPU.0` / `NPU`） |')
    A('| `--engine` | 识别后端（`gpu_int8` / `npu_int8`；不给则按设备自动选） |')
    A('| `--asr-enc-tiers` | 识别 encoder 分档开关（默认 **off**） |')
    A('')
    A('例如「配音走集显、其余走 NPU」：')
    A('')
    A('```')
    A('python\\python.exe app\\live_caption_app.py --asr-device NPU '
      '--mt-device NPU --tts-device GPU.0')
    A('```')
    A('')
    A('## 已知问题')
    A('')
    A('1. 🔴 **Meteor Lake 等部分机型上，用 NPU 配音可能出现杂音。**'
      ' ⇒ **请把「语音输出」改成 GPU.0（Intel 集显）**。'
      '识别与翻译留在 NPU 不受影响。')
    A('2. ⚠️ **讲话密集时，配音会比原声滞后。**'
      ' 10 分钟连续讲话实测：滞后最大约 **43 s**、讲完收尾时约 **30 s**。'
      '这是因为 NPU 上的合成速度接近实时、追不上密集的语速。'
      'App 会**自动加速追赶**（最高 **1.7×**），追平后恢复正常速度；'
      '积压没追平前字幕仍会持续输出，不会丢句。')
    A('3. ⚠️ **首次启动 NPU 需要现编译模型**（本包**不带编译缓存 blob**）'
      '⇒ 第一次启动明显更慢（缓存写在 `%LOCALAPPDATA%\\Confucius4LiveCaption`，'
      '首次约需数 GB 磁盘）。之后走缓存，几秒内即可加载。')
    A('4. ⚠️ **EXT 的 ASR 在本版不可用**（详见下一节）。'
      '实时字幕 App **自带的语音输出不受影响**。')
    A('')
    if acc.get('chain'):
        c = acc['chain']
        A('### A 机实测（每个数字都注明设备组合）')
        A('')
        A('* 设备组合 **%s**' % c.get('device_combo', '（见验收记录）'))
        if c.get('subtitle_first_token_ms') is not None:
            A('* **字幕出字延迟中位 %s ms**（识别引擎状态行）'
              % c.get('subtitle_first_token_ms'))
        if c.get('tts_first_packet_s') is not None:
            A('* **配音首包 %s s**（语音输出状态行的「首包」，'
              '**与上面的字幕出字延迟是两个不同的数**）'
              % c.get('tts_first_packet_s'))
        if c.get('synth_rtf_median') is not None:
            A('* 配音合成速度 `synth_rtf` 中位 **%s** / P90 **%s**'
              '（≤1 表示合成快于实时；越小积压越少）'
              % (c.get('synth_rtf_median'), c.get('synth_rtf_p90')))
        if c.get('backlog_peak_s') is not None:
            A('* 配音积压峰值 **%s s** / 收尾积压 **%s s**（**积压随机器负载浮动**：'
              '另一次同配置实测峰值约 43 s；积压大时**字幕仍持续输出、不会丢句**，'
              '并会自动加速追赶）'
              % (c.get('backlog_peak_s'), c.get('backlog_final_s')))
        if c.get('n_sentences') is not None:
            A('* 10 分钟固定片段：**%s 句进配音、%s 句播完、丢弃 %s 句**'
              % (c.get('n_sentences'), c.get('n_played'),
                 c.get('n_dropped')))
        A('')
    A('## 配音桥接（EXT）')
    A('')
    A('> ⚠️ **本版（%s）里 EXT 的 ASR 不可用** —— 插件侧的引擎接线目前只支持'
      '另一种识别模型，而本包只有 **Qwen3-ASR-0.6B（stateful）** '
      '⇒ 启动桥接后日志会报引擎构造失败、预热不完整，'
      '**不会出现** `真实引擎已接线` 与 `TTS 就绪` '
      '⇒ **待插件侧适配 0.6B**（插件侧进行中；本包不等它）。'
      % PKG_TITLE)
    A('> ⇒ **本包不要用浏览器插件这条链路**；实时字幕 App **自带的语音输出**'
      '（Qwen3-TTS，预设音色 A）**不受影响**。')
    A('')
    A('## 许可与归属')
    A('')
    A('见 `NOTICE`（Qwen3-ASR / Qwen3-TTS / Hy-MT2 / OpenVINO / **babelvox** / '
      '**djwarf** 等的归属与许可证）与 `THIRD_PARTY.md`。')
    A('')
    A('## 本包顶层目录')
    A('')
    A('`%s`' % '`, `'.join(tops))
    A('')
    return '\n'.join(L)


def build_en(st, tops, acc):
    L = []
    A = L.append
    A('# Confucius4 Live Caption - %s (minimal customer package)' % PKG_TITLE)
    A('')
    A('**Independent product line (MiniMVP), versioned separately.**')
    A('')
    A('## What is inside')
    A('')
    A('| Module | Model | Precision | Default device |')
    A('|---|---|---|---|')
    A('| Speech recognition | **Qwen3-ASR-0.6B** (stateful INT8 (KV cache)) '
      '| INT8 | Intel iGPU (GPU.0) |')
    A('| Translation | **Hy-MT2-1.8B** (**INT8-CW**) '
      '| **INT8** (symmetric, per-channel weight) | Intel iGPU (GPU.0) |')
    A('| Speech output | **Qwen3-TTS 0.6B** (INT8 weights, FP16 compute) '
      '| INT8/FP16 | Intel NPU |')
    A('')
    A('* **Included**: the real-time dubbing plugin & bridge service '
      '(folder `ext/`), plus the launch scripts '
      '(`Start_LiveCaption.bat` / `Start_Bridge.bat`).')
    A('* **Not included**: NVIDIA/CUDA & torch content '
      '(**no `cuda_env/`, no `models/tts_cuda/`**), other recognition models, '
      'the MT INT4 quantization, dev & test scripts, meeting recordings, '
      '**cloned voices** (disabled in this product line => preset voices '
      'only), speaker-bypass models.')
    A('* **Voice**: **preset A only** '
      '(`models/qwen3tts/voices/preset_A.wav`). Preset B is not final and is '
      '**not shipped**.')
    A('* **Target languages**: 10.')
    A('* **Factory default devices**: **ASR=Intel iGPU (GPU.0), MT=Intel iGPU '
      '(GPU.0), TTS=Intel NPU** (single source of truth = `DEFAULT_DEVICES` '
      'in `app/device_config.py`).')
    A('  🔴 **You are free to place every module on any accelerator** '
      '=> **no "cannot share the NPU" restriction**.')
    A('  ⚠️ If a **stale** `device_config.json` (written by an earlier build) is '
      'present in `%LOCALAPPDATA%\\Confucius4LiveCaption`, the app **ignores** '
      'its device entries and falls back to the factory defaults, logging '
      'which old values were ignored (the file itself is **never deleted**).')
    A('')
    A('### Recognition recipe')
    A('')
    A('* **Qwen3-ASR-0.6B**, **stateful INT8 (KV cache)** (per-channel INT8 '
      'weights, FP16 lm_head, real `attention_mask` port). The same IR pair '
      'is compiled either to the iGPU (`--engine gpu_int8`) or to the NPU '
      '(`--engine npu_int8`).')
    A('* **Prompt bound on the NPU = 320** (smaller than the 512 used on the '
      'iGPU) => lower latency and RTF.')
    A('* **Over-long prefixes are left-truncated by token** (keeping the right '
      'end = the most recent text): counted in the log field '
      '`prefix_truncations`; **it never raises and never falls back to 512**.')
    A('* **Segment length precondition**: a segment must be <= **20 s** '
      '(`MAX_SEG_SEC`); if "template + audio tokens" alone exceeds 320 the '
      'app **reports an explicit error** (it never fails silently).')
    A('* **A failed single segment never stops the whole recognition**: the '
      'app logs it, counts it and **skips that segment** (log keyword '
      '`[asr-loop]`; the total is printed when the run ends).')
    A('* **Encoder tiering is an optional switch, OFF by default** '
      '(`--asr-enc-tiers on/off`): when on, the 400/800/1600/2400 tiers are '
      'built at runtime and **any failing tier falls back to the single 2400 '
      'tier** (no half-built tier set is left behind). With the switch off '
      'the behaviour is exactly as before the optimization.')
    A('')
    A('### Translation recipe')
    A('')
    A('* **Hy-MT2-1.8B**, **INT8-CW** (**INT8_SYM, per-channel**, '
      '`mt2-int8sym-cw-q`; hidden_size 2048 / 32 layers) => **this package '
      'ships INT8-CW only, INT4 is gone**; default translation device: '
      '**GPU.0**.')
    A('')
    A('### Package size (measured)')
    A('')
    A('Unpacked **%s files / %s B (%.3f GiB)**.'
      % (fmt_int(st['files']), fmt_int(st['bytes']), st['bytes'] / 1024 ** 3))
    if acc.get('zip_bytes'):
        A('Packed as a zip: **%s B (%.3f GiB)**.'
          % (fmt_int(acc['zip_bytes']), acc['zip_bytes'] / 1024 ** 3))
    else:
        A('(See the release notes for the zip size.)')
    A('')
    A('Top-level size breakdown (measured, **only the files that are really '
      'shipped**):')
    A('')
    A('| Top-level entry | Bytes |')
    A('|---|---|')
    for k, v in st['top'].items():
        A('| `%s` | %s |' % (k, fmt_int(v)))
    A('')
    A('## Run')
    A('')
    A('Double-click `Start_LiveCaption.bat`, or (no device flags needed):')
    A('')
    A('```')
    A('python\\python.exe app\\live_caption_app.py')
    A('```')
    A('')
    A('## How to change the devices')
    A('')
    A('**GUI**: below the top bar there are **three sections** - "ASR", '
      '"Translate" and "Speech output" - each with its own **device + '
      'precision** drop-down. They are independent: **all three may sit on '
      'the NPU, or any combination**.')
    A('')
    A('**Command line** (equivalent flags):')
    A('')
    A('| Flag | Meaning |')
    A('|---|---|')
    A('| `--asr-device` | recognition device (`GPU.0` / `NPU`) |')
    A('| `--mt-device` | translation device (`GPU.0` / `NPU`) |')
    A('| `--tts-device` | speech output device (`GPU.0` / `NPU`) |')
    A('| `--engine` | recognition backend (`gpu_int8` / `npu_int8`; picked '
      'from the device when omitted) |')
    A('| `--asr-enc-tiers` | encoder tiering switch (default **off**) |')
    A('')
    A('Example - dubbing on the iGPU, the rest on the NPU:')
    A('')
    A('```')
    A('python\\python.exe app\\live_caption_app.py --asr-device NPU '
      '--mt-device NPU --tts-device GPU.0')
    A('```')
    A('')
    A('## Known issues')
    A('')
    A('1. 🔴 **On some machines such as Meteor Lake, dubbing on the NPU may '
      'produce noise.** => **Please switch "Speech output" to GPU.0 (Intel '
      'iGPU).** Recognition and translation on the NPU are unaffected.')
    A('2. ⚠️ **When speech is dense, the dubbing lags behind the original '
      'voice.** A 10-minute continuous-speech measurement showed a peak lag '
      'of about **43 s** and about **30 s** still left at the end. This is '
      'because the NPU synthesis speed is close to real time and cannot keep '
      'up with dense speech. The app **accelerates automatically to catch up** '
      '(up to **1.7x**) and then returns to normal speed; subtitles keep '
      'being produced meanwhile and no sentence is dropped.')
    A('3. ⚠️ **The NPU compiles the models on the first start** (this package '
      '**ships no blob cache**) => the first start is noticeably slower (the '
      'cache lives in `%LOCALAPPDATA%\\Confucius4LiveCaption` and needs a few '
      'GB of disk). Later starts use the cache and load in seconds.')
    A('4. ⚠️ **The EXT ASR does not work in this build** (see the next '
      'section). The caption app\'s **own speech output is not affected**.')
    A('')
    if acc.get('chain'):
        c = acc['chain']
        A('### Measured on machine A (every number states its device '
          'combination)')
        A('')
        A('* Device combination **%s**' % c.get('device_combo',
                                                 '(see acceptance record)'))
        if c.get('subtitle_first_token_ms') is not None:
            A('* **Subtitle first-token latency: median %s ms** '
              '(recognition engine status line)'
              % c.get('subtitle_first_token_ms'))
        if c.get('tts_first_packet_s') is not None:
            A('* **Dubbing first packet: %s s** (speech-output status line; '
              '**a different number from the subtitle first-token latency '
              'above**)' % c.get('tts_first_packet_s'))
        if c.get('synth_rtf_median') is not None:
            A('* Dubbing synthesis speed `synth_rtf` median **%s** / P90 **%s** '
              '(<=1 means faster than real time)'
              % (c.get('synth_rtf_median'), c.get('synth_rtf_p90')))
        if c.get('backlog_peak_s') is not None:
            A('* Dubbing backlog peak **%s s** / final backlog **%s s**'
              % (c.get('backlog_peak_s'), c.get('backlog_final_s')))
        if c.get('n_sentences') is not None:
            A('* 10-minute fixed clip: **%s sentences submitted, %s played, '
              '%s dropped**'
              % (c.get('n_sentences'), c.get('n_played'), c.get('n_dropped')))
        A('')
    A('## Dubbing bridge (EXT)')
    A('')
    A('> ⚠️ **In this build (%s) the EXT ASR does NOT work** -- the plugin\'s '
      'engine wiring currently supports a different recognition model, while '
      'this package only ships **Qwen3-ASR-0.6B (stateful)** => starting the '
      'bridge logs an engine construction failure and an incomplete warm-up, '
      'and `真实引擎已接线` / `TTS 就绪` **never appear** '
      '=> **waiting for the plugin side to support 0.6B** '
      '(in progress on the plugin side; this package does not wait for it).'
      % PKG_TITLE)
    A('> => **Do not use the browser-plugin path in this package**; the '
      'caption app\'s **own speech output** (Qwen3-TTS, preset voice A) is '
      '**not affected**.')
    A('')
    A('## Licenses')
    A('')
    A('See `NOTICE` and `THIRD_PARTY.md`.')
    A('')
    A('## Top level of this package')
    A('')
    A('`%s`' % '`, `'.join(tops))
    A('')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--accept', default='')
    ap.add_argument('--json', default=os.path.join(
        REPO, 'results', 'app', 'app121_write_readme_evidence.json'))
    args = ap.parse_args()
    if not os.path.isdir(args.pkg):
        print('FAIL: 包目录不存在 %s' % args.pkg)
        return 2
    acc = load_accept(args.accept)
    tops = top_level(args.pkg)

    # 🔴 **自指大小迭代到不动点**（README 自己进包 ⇒ 写 README 会改总字节数）
    iters = []
    prev = None
    for it in range(8):
        st = zip_content_stats(args.pkg)
        bodies = {'README_zh.md': build_zh(st, tops, acc),
                  'README_en.md': build_en(st, tops, acc)}
        for fn, body in bodies.items():
            p = os.path.join(args.pkg, fn)
            tmp = p + '.tmp'
            with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
                f.write(body)
            os.replace(tmp, p)
        st2 = zip_content_stats(args.pkg)
        iters.append({'iter': it, 'files': st['files'], 'bytes_used': st['bytes'],
                      'bytes_on_disk': st2['bytes'],
                      'stable': (st['bytes'] == st2['bytes'])})
        print('  迭代 %d：写进 README 的 %d 文件 / %d B ⇒ 磁盘实测 %d B %s'
              % (it, st['files'], st['bytes'], st2['bytes'],
                 '（不动点 ✔）' if st['bytes'] == st2['bytes'] else '（继续）'))
        if st['bytes'] == st2['bytes']:
            prev = (st, st2)
            break
        prev = (st, st2)

    st, st2 = prev
    ev = {'script': '_app121_write_readme.py',
          'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
          'pkg': args.pkg, 'version': VERSION,
          'accept': args.accept,
          'n_files_zip_content': st2['files'],
          'bytes_zip_content': st2['bytes'],
          'iterations': iters,
          'fixed_point': bool(iters and iters[-1]['stable']),
          'readme_zh_bytes': os.path.getsize(
              os.path.join(args.pkg, 'README_zh.md')),
          'readme_en_bytes': os.path.getsize(
              os.path.join(args.pkg, 'README_en.md')),
          'top': st2['top'],
          'zip_bytes': acc.get('zip_bytes'),
      }
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    tmp = args.json + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.json)
    print('最终：%d 个文件 / %d B（zip 清单口径）；不动点=%s'
          % (st2['files'], st2['bytes'], ev['fixed_point']))
    print('证据 → %s' % args.json)
    return 0 if ev['fixed_point'] else 1


if __name__ == '__main__':
    sys.exit(main())
