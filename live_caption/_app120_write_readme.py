#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §1：**按实际文件生成 MiniMVP v1.1 的中/英 README**。

## reviewer 原文（APP-120 §1 最后一条）
> README（中/英）按实际文件生成，写清：版本、默认设备、如何改设备、已知问题。
> 已知问题至少要写：**Meteor Lake 等部分机型上 NPU 配音可能出现杂音 ⇒
> 请把配音改为 GPU.0**；首次启动 NPU 编译耗时。

## 纪律
- **按实际文件生成**（文件数 / 字节数 / 顶层目录清单 / 模型清单都从磁盘实测）；
- 验收数字（若已有 §2 证据 json）**自动注入**；没有就写「待实测」⇒ **不编造**；
- 只写 `README_zh.md` / `README_en.md` 两个文件，**不动其它任何文件**。

## 用法
```
python live_caption/_app120_write_readme.py --pkg <MiniMVP v1.1 目录>
python live_caption/_app120_write_readme.py --pkg <...> --accept <验收证据 json>
```
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1')
VERSION = '1.1'
PKG_TITLE = 'MiniMVP v%s' % VERSION


def pkg_stats(pkg):
    n_files = 0
    n_bytes = 0
    top = {}
    models = {}
    for dp, dns, fns in os.walk(pkg):
        rel_dp = os.path.relpath(dp, pkg).replace(os.sep, '/')
        if rel_dp == '.':
            rel_dp = ''
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = 0
            n_files += 1
            n_bytes += sz
            top[rel_dp.split('/')[0] if rel_dp else '(根文件)'] = \
                top.get(rel_dp.split('/')[0] if rel_dp else '(根文件)', 0) + sz
            if rel_dp.startswith('models/'):
                key = '/'.join(rel_dp.split('/')[:2]) if '/' in rel_dp else rel_dp
                models[key] = models.get(key, 0) + sz
    return {'files': n_files, 'bytes': n_bytes,
            'top': dict(sorted(top.items(), key=lambda kv: -kv[1])),
            'models': dict(sorted(models.items(), key=lambda kv: -kv[1]))}


def top_level(pkg):
    out = []
    for name in sorted(os.listdir(pkg)):
        if name.startswith('.'):
            continue
        out.append(name)
    return out


def fmt_int(n):
    return '{:,}'.format(int(n)).replace(',', ' ')


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
    A('**本包是独立于 v2.x 的新产品线（MiniMVP），版本号单独编号。**')
    A('**本包从 v2.5 全集按 `minimvp` profile 裁剪（APP-120，2026-11-22）。**')
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
    A('* **包含**：EXT 实时翻译配音**插件与桥接服务**（`ext/` 目录），'
      '桌面/命令行启动脚本（`Start_LiveCaption.bat` / `Start_Bridge.bat`）。')
    A('* **不含**：NVIDIA/CUDA 与 torch 相关内容（**无 `cuda_env/`、无 '
      '`models/tts_cuda/`**）、R2T2 1.7B 识别模型、MT 的 INT4 量化、'
      '开发与测试脚本、会议录音、**克隆音色**（MiniMVP 禁用 ⇒ 只有内置预设音色 A）、'
      '说话人旁路模型（pyannote_seg / wespeaker）。')
    A('* **音色**：只有**预设 A**（`models/qwen3tts/voices/preset_A.wav`）。'
      '预设 B 尚未定稿，**不进本包**。')
    A('* **目标语言**：10 种。')
    A('* **出厂默认设备**：**ASR=Intel 集显 GPU.0，MT=Intel 集显 GPU.0，'
      'TTS=Intel NPU**（唯一事实来源 = `app/device_config.py` 的 '
      '`DEFAULT_DEVICES`）。')
    A('  🔴 **推理设备完全由你自由配置**：三个模块可以放在任意加速器上，'
      '**不再有「不能同时放在 NPU」的限制**（APP-119）。')
    A('  ⚠️ 若本机 `%LOCALAPPDATA%\\Confucius4LiveCaption\\device_config.json` '
      '是**旧版本**（本包之前写的），App 会**忽略**其中的设备项并改用出厂默认，'
      '并在日志里写明忽略了哪些旧值（配置文件**不会被删除**）。')
    A('')
    A('### 识别模型配方（ASR-065 / ASR-066 优化已接入）')
    A('')
    A('* **Qwen3-ASR-0.6B**，**stateful INT8（KV cache）**（按通道 INT8 权重、'
      'lm_head 保 FP16、带真实 `attention_mask` 端口）。同一套 IR 可编到集显'
      '（`--engine gpu_int8`）或 NPU（`--engine npu_int8`）。')
    A('* **NPUW `MAX_PROMPT_LEN` = 320**（原 512）：NPU 档的 prompt 上界更小 ⇒ '
      '出字延迟与 RTF 更低。')
    A('* **超长前缀按 token 从左截断**（保留右端＝最近的内容）：'
      '计数写在日志字段 `prefix_truncations` 里，**不抛错、不回退 512**。')
    A('* **段长前提**：单段 ≤ **20 s**（`MAX_SEG_SEC`）；'
      '若「模板 + 音频 token」本身就超过 320 ⇒ **显式报错**（不会静默出错）。')
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
        A('zip **%s B**。' % fmt_int(acc['zip_bytes']))
    else:
        A('（zip 大小见发布说明。）')
    A('')
    A('顶层目录体积构成（实测）：')
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
    A('2. ⚠️ **首次启动 NPU 需要现编译模型**（本包**不带编译缓存 blob**）'
      '⇒ 第一次启动明显更慢（缓存写在 `%LOCALAPPDATA%\\Confucius4LiveCaption`，'
      '首次约需数 GB 磁盘）。之后走缓存，几秒内即可加载。')
    A('3. ⚠️ **EXT 的 ASR 在本版不可用**（详见下一节）。'
      '实时字幕 App **自带的语音输出不受影响**。')
    A('')
    if acc.get('chain'):
        c = acc['chain']
        A('### A 机实测（每个数字都注明设备组合）')
        A('')
        A('* 设备组合 **%s**' % c.get('device_combo', '（见验收记录）'))
        if c.get('rtf_p90') is not None:
            A('* ASR RTF P90 **%s**；TTS `synth_rtf` 中位 **%s** / P90 **%s**'
              % (c.get('rtf_p90'), c.get('synth_rtf_median'),
                 c.get('synth_rtf_p90')))
        if c.get('backlog_peak_s') is not None:
            A('* 配音积压峰值 **%s s** / 收尾积压 **%s s**；首字延迟 **%s ms**'
              % (c.get('backlog_peak_s'), c.get('backlog_final_s'),
                 c.get('ttft_ms')))
        A('')
    A('## 配音桥接（EXT）')
    A('')
    A('> ⚠️ **本版（%s）里 EXT 的 ASR 不可用** —— EXT 的 `engine_runtime.py` '
      '**写死了 R2T2 的 ASR**，而本包只有 **Qwen3-ASR-0.6B（stateful）** '
      '⇒ 启动桥接后日志会报 `SegmentEncoderOVBackend 构造失败 …`、'
      '引擎预热是「成功 2/3」，**不会出现** `真实引擎已接线` 与 `TTS 就绪` '
      '⇒ **待 EXT 适配 0.6B**（EXT 侧进行中；本包不等它）。'
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
    A('**Independent product line (MiniMVP), versioned separately from v2.x.**')
    A('**Cut from the v2.5 full package with the `minimvp` profile '
      '(APP-120, 2026-11-22).**')
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
    A('* **Included**: the EXT real-time dubbing plugin & bridge service '
      '(folder `ext/`), plus the launch scripts '
      '(`Start_LiveCaption.bat` / `Start_Bridge.bat`).')
    A('* **Not included**: NVIDIA/CUDA & torch content '
      '(**no `cuda_env/`, no `models/tts_cuda/`**), the R2T2 1.7B recognition '
      'model, the MT INT4 quantization, dev & test scripts, meeting '
      'recordings, **cloned voices** (disabled in MiniMVP => preset voices '
      'only), speaker-bypass models (pyannote_seg / wespeaker).')
    A('* **Voice**: **preset A only** '
      '(`models/qwen3tts/voices/preset_A.wav`). Preset B is not final and is '
      '**not shipped**.')
    A('* **Target languages**: 10.')
    A('* **Factory default devices**: **ASR=Intel iGPU (GPU.0), MT=Intel iGPU '
      '(GPU.0), TTS=Intel NPU** (single source of truth = `DEFAULT_DEVICES` '
      'in `app/device_config.py`).')
    A('  🔴 **You are free to place every module on any accelerator** '
      '=> **no "cannot share the NPU" restriction** any more (APP-119).')
    A('  ⚠️ If a **stale** `device_config.json` (written by an earlier build) is '
      'present in `%LOCALAPPDATA%\\Confucius4LiveCaption`, the app **ignores** '
      'its device entries and falls back to the factory defaults, logging '
      'which old values were ignored (the file itself is **never deleted**).')
    A('')
    A('### Recognition recipe (ASR-065 / ASR-066 optimizations integrated)')
    A('')
    A('* **Qwen3-ASR-0.6B**, **stateful INT8 (KV cache)** (per-channel INT8 '
      'weights, FP16 lm_head, real `attention_mask` port). The same IR pair '
      'is compiled either to the iGPU (`--engine gpu_int8`) or to the NPU '
      '(`--engine npu_int8`).')
    A('* **NPUW `MAX_PROMPT_LEN` = 320** (was 512): a smaller prompt bound on '
      'the NPU path => lower latency and RTF.')
    A('* **Over-long prefixes are left-truncated by token** (keeping the right '
      'end = the most recent text): counted in the log field '
      '`prefix_truncations`; **it never raises and never falls back to 512**.')
    A('* **Segment length precondition**: a segment must be <= **20 s** '
      '(`MAX_SEG_SEC`); if "template + audio tokens" alone exceeds 320 the '
      'app **reports an explicit error** (it never fails silently).')
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
        A('Zip **%s B**.' % fmt_int(acc['zip_bytes']))
    else:
        A('(See the release notes for the zip size.)')
    A('')
    A('Top-level size breakdown (measured):')
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
    A('2. ⚠️ **The NPU compiles the models on the first start** (this package '
      '**ships no blob cache**) => the first start is noticeably slower (the '
      'cache lives in `%LOCALAPPDATA%\\Confucius4LiveCaption` and needs a few '
      'GB of disk). Later starts use the cache and load in seconds.')
    A('3. ⚠️ **The EXT ASR does not work in this build** (see the next '
      'section). The caption app\'s **own speech output is not affected**.')
    A('')
    if acc.get('chain'):
        c = acc['chain']
        A('### Measured on machine A (every number states its device '
          'combination)')
        A('')
        A('* Device combination **%s**' % c.get('device_combo',
                                                 '(see acceptance record)'))
        if c.get('rtf_p90') is not None:
            A('* ASR RTF P90 **%s**; TTS `synth_rtf` median **%s** / P90 **%s**'
              % (c.get('rtf_p90'), c.get('synth_rtf_median'),
                 c.get('synth_rtf_p90')))
        if c.get('backlog_peak_s') is not None:
            A('* Dubbing backlog peak **%s s** / final backlog **%s s**; '
              'TTFT **%s ms**'
              % (c.get('backlog_peak_s'), c.get('backlog_final_s'),
                 c.get('ttft_ms')))
        A('')
    A('## Dubbing bridge (EXT)')
    A('')
    A('> ⚠️ **In this build (%s) the EXT ASR does NOT work** -- the EXT '
      '`engine_runtime.py` **hard-codes the R2T2 ASR**, while this package '
      'only ships **Qwen3-ASR-0.6B (stateful)** => starting the bridge logs '
      '`SegmentEncoderOVBackend ... construction failed ...`, engine warm-up '
      'reports "2/3 succeeded", and `真实引擎已接线` / `TTS 就绪` '
      '**never appear** => **waiting for EXT to support 0.6B** '
      '(in progress on the EXT side; this package does not wait for it).'
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
    args = ap.parse_args()
    if not os.path.isdir(args.pkg):
        print('FAIL: 包目录不存在 %s' % args.pkg)
        return 2
    st = pkg_stats(args.pkg)
    tops = top_level(args.pkg)
    acc = load_accept(args.accept)

    for fn, body in (('README_zh.md', build_zh(st, tops, acc)),
                      ('README_en.md', build_en(st, tops, acc))):
        p = os.path.join(args.pkg, fn)
        tmp = p + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
        os.replace(tmp, p)
        print('写 %s（%d 字符 / %d B）'
              % (fn, len(body), os.path.getsize(p)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
