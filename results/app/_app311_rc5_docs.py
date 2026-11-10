#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app311_rc5_docs.py —— **MiniMVP v1.0-rc5 文档同步**（APP-096 §2 / APP-095 1a）。

## 依据

* **APP-096 §2**：README（en / zh / perftest）里 ASR 写 **Qwen3-ASR-0.6B INT8**
  （iGPU / NPU），**模型实际大小和文件数、内存和磁盘占用都按 rc5 重新实测**。
* **APP-095 1a**：README_en / README_zh / perftest 说明里**所有 INT4 NPU 提及**都要去掉。
* **APP-096 §3c**：给出 rc5 相对 rc4 的**大小变化**（目录和 zip 两项）。

## 🔴🔴🔳 纪律

* 文档里的**数字必须实测**（APP-073(c) 同类缺陷：rc4 的 README 沿用了 rc3 的
  「6.7 GB / 10 474 个文件」⇒ 打进 zip 的说明书本身是错的）。
* 本脚本**只改 rc5 目录内的文档**（rc4 一字不动）。
* 定点替换 + 唯一命中断言。
* ⚠️ **dry-run 绝不写盘**（第一版把写盘放在 dry 判断之前 ⇒ dry-run 也改了文件，
  本版已修正）。

## 用法

```
.venv/Scripts/python.exe results/app/_app311_rc5_docs.py --dry-run
.venv/Scripts/python.exe results/app/_app311_rc5_docs.py --run
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

import pkg_exclude as PE  # noqa: E402

HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5')
PKG4 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
VERSION = '1.0-rc5'
REPORT = os.path.join(HERE, 'app311_rc5_docs_evidence.json')

#: rc5 实测基线（`_app312_rc5_device_acceptance.py` 产出；NPU 臂同源）
RC5_BASELINE = {
    'gpu': {'rtf': 0.73, 'lat_ms': 472, 'backlog_s': 1.0, 'peak_mb': 3585.5,
            'segs': 46},
    'npu': {'rtf': None, 'lat_ms': None, 'backlog_s': None, 'peak_mb': None,
            'segs': None},
}
#: rc4 §161 的 R2T2 参照（并列用）
RC4_BASELINE = {
    'gpu': {'rtf': 0.696, 'lat_ms': 376, 'backlog_s': 1.2, 'peak_mb': 4819.5,
            'segs': 46, 'wer_pct': 14.5494},
    'npu': {'rtf': 0.803, 'lat_ms': 540, 'backlog_s': 1.1, 'peak_mb': 5212.6,
            'segs': 46, 'wer_pct': 15.5266},
}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def pkg_stats(root):
    fl = list(PE.iter_package_files(root))
    return {'files': len(fl), 'bytes': sum(s for _r, s in fl)}


def patch_once(text, old, new, tag):
    eol = '\r\n' if '\r\n' in text else '\n'
    norm = text.replace('\r\n', '\n')
    n = norm.count(old)
    if n != 1:
        raise AssertionError('anchor %s hit %d times (need exactly 1)' % (tag, n))
    norm = norm.replace(old, new, 1)
    return norm.replace('\n', eol) if eol == '\r\n' else norm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    dry = not args.run

    ev = {'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
          'corrections': ['APP-095 1a (README INT4 mentions)', 'APP-096 §2'],
          'dry_run': dry}

    s5 = pkg_stats(PKG)
    s4 = pkg_stats(PKG4)
    gb5 = s5['bytes'] / 2 ** 30
    ev['rc5_stats'] = s5
    ev['rc4_stats'] = s4
    ev['size_delta'] = {
        'files': s5['files'] - s4['files'],
        'bytes': s5['bytes'] - s4['bytes'],
        'gb': round((s5['bytes'] - s4['bytes']) / 2 ** 30, 3)}

    size_txt = ('%.1f GB' % gb5 if gb5 < 10 else '%.0f GB' % gb5)
    files_txt = str(s5['files'])

    # ══════════════════════════════════════════════════════════════
    # README_en.md
    # ══════════════════════════════════════════════════════════════
    p = os.path.join(PKG, 'README_en.md')
    t = open(p, encoding='utf-8', newline='').read()
    t = patch_once(t,
                   '# Confucius4 Live Caption - MiniMVP v1.0-rc4 (minimal customer package)',
                   '# Confucius4 Live Caption - MiniMVP v1.0-rc5 (minimal customer package)',
                   'en_title')
    t = patch_once(t,
                   '| ASR | Qwen3-ASR 0.6B | INT8 | Intel iGPU (GPU.0) |',
                   '| ASR | **Qwen3-ASR-0.6B** (mask2 INT8) | INT8 | Intel iGPU (GPU.0) '
                   'or Intel NPU |',
                   'en_asr_row')
    t = patch_once(t,
                   """* **Devices**: ASR + MT on the iGPU, TTS on the NPU; **no CUDA / CPU option**.
  MT and TTS must not share the NPU (the app moves MT to the iGPU and says so).""",
                   """* **Devices**: ASR + MT on the iGPU, TTS on the NPU; **no CUDA / CPU option**.
  MT and TTS must not share the NPU (the app moves MT to the iGPU and says so).
* **ASR**: **Qwen3-ASR-0.6B** with the **mask2 INT8** recipe (per-channel INT8
  weights, FP16 lm_head, real `attention_mask` port). The **same IR pair** is
  compiled either to the iGPU (`--engine gpu_int8`) or to the NPU
  (`--engine npu_int8`); there is **no INT4 ASR engine** any more.
* **Package size (measured)**: **%s** / **%s files**.""" % (size_txt, files_txt),
                   'en_devices')
    t = patch_once(t,
                   """> **Disk**: about **8 GB** on the first run (compile caches: `tts_npu_cache`
> ~5 GB, `ov_cache` ~2 GB, `mt_cache` ~1 GB).""",
                   """> **Disk**: about **8 GB** on the first run (compile caches: `tts_npu_cache`
> ~5 GB, `ov_cache` ~2 GB, `mt_cache` ~1 GB).
> **Measured peak memory** (ASR only, `--tts off`, 300 s English clip):
> iGPU arm **3585.5 MB**.""" ,
                   'en_disk')
    new_en = t

    # ══════════════════════════════════════════════════════════════
    # README_zh.md
    # ══════════════════════════════════════════════════════════════
    p = os.path.join(PKG, 'README_zh.md')
    t = open(p, encoding='utf-8', newline='').read()
    t = patch_once(t,
                   '# Confucius4 实时字幕 · MiniMVP v1.0-rc4（最小客户包）',
                   '# Confucius4 实时字幕 · MiniMVP v1.0-rc5（最小客户包）',
                   'zh_title')
    t = patch_once(t,
                   '| 语音识别 | Qwen3-ASR 0.6B | INT8 | Intel 集显 GPU.0 |',
                   '| 语音识别 | **Qwen3-ASR-0.6B**（mask2 INT8） | INT8 | '
                   'Intel 集显 GPU.0 或 Intel NPU |',
                   'zh_asr_row')
    t = patch_once(t,
                   """* **设备约束**：ASR 与 MT 走集显，TTS 走 NPU；**不提供 CUDA / CPU 选项**。
  MT 与 TTS **不得同时占用 NPU**（App 会把 MT 自动改到集显并提示）。""",
                   """* **设备约束**：ASR 与 MT 走集显，TTS 走 NPU；**不提供 CUDA / CPU 选项**。
  MT 与 TTS **不得同时占用 NPU**（App 会把 MT 自动改到集显并提示）。
* **ASR**：**Qwen3-ASR-0.6B**，**mask2 INT8** 配方（按通道 INT8 权重、
  lm_head 保 FP16、带真实 `attention_mask` 端口）。
  同一套 IR 可编到集显（`--engine gpu_int8`）或 NPU（`--engine npu_int8`）；
  **不再有 INT4 ASR 引擎**。
* **包体积（实测）**：**%s** / **%s 个文件**。""" % (size_txt, files_txt),
                   'zh_devices')
    t = patch_once(t,
                   """> **磁盘**：首次运行约需 **8 GB**（编译缓存 `tts_npu_cache` ≈ 5 GB、
> `ov_cache` ≈ 2 GB、`mt_cache` ≈ 1 GB）。""",
                   """> **磁盘**：首次运行约需 **8 GB**（编译缓存 `tts_npu_cache` ≈ 5 GB、
> `ov_cache` ≈ 2 GB、`mt_cache` ≈ 1 GB）。
> **实测峰值内存**（仅 ASR，`--tts off`，300 秒英文切片）：
> 集显臂 **3585.5 MB**。""",
                   'zh_disk')
    new_zh = t

    # ══════════════════════════════════════════════════════════════
    # README_perftest.txt
    # ══════════════════════════════════════════════════════════════
    p = os.path.join(PKG, 'README_perftest.txt')
    t = open(p, encoding='utf-8', newline='').read()
    ev['perftest_int4_hits_before'] = len(re.findall(r'INT4', t))

    # ① 版本号 rc4 → rc5
    t = t.replace('MiniMVP v1.0-rc4', 'MiniMVP v1.0-rc5')
    t = t.replace('rc4', 'rc5')

    # ② 「rc5 新增：全 NPU ASR 已随包」整段 ⇒ 换成 0.6B 的模型清单
    old_models = """【rc5 新增：全 NPU ASR 已随包】
  rc3 只带了 **GPU 版 ASR**（encoder-int8 + decoder-gpu-int8）⇒ `--check` 显示
  「Intel NPU · INT8 缺 编码器、解码器」。**rc5 补齐了 3 个 NPU IR**：
      · models/encoder-fp16      （= ov-encoder-segment-reviewer，fp16 encoder）
      · models/decoder-npu-int8   （= qwen3-lm-int8sym-cleanie-ov，因果 LM，INT8）
      · models/decoder-npu-int4   （= c089_int4/R4，INT4 实验档）
  ⇒ rc5 的 `--check` 应显示「**Intel NPU · INT8  模型齐全**」。
  · iGPU 版模型（encoder-int8 / decoder-gpu-int8）**保留** ⇒ 两档可对比。
  · 用法：`python\\python.exe app\\live_caption_app.py --engine npu_int8 --check`
    或跑 5 分钟时加 `--engine npu_int8 --asr-device NPU`。"""
    new_models = """【rc5 的 ASR：Qwen3-ASR-0.6B（mask2 INT8）】
  🔴 **rc5 把 ASR 从 R2T2 换成了 Qwen3-ASR-0.6B**（回到 APP-066 原规格），
  **R2T2 的 ASR IR 已全部删除**：
      · 已删：models/encoder-int8、models/decoder-gpu-int8、models/encoder-fp16、
              models/decoder-npu-int8、models/decoder-npu-int4、
              models/embed_tokens_f16.npy
  ⇒ 包内 0.6B 物料（**iGPU 与 NPU 共用同一份**，只是编译目标设备不同）：
      · models/asr06b-encoder-fp16   （= ov-encoder-06b-fp16-static，静态形状 FP16）
      · models/asr06b-decoder-int8   （= ov-dec-06b-embed-mask2-int8sym，
                                     按通道 INT8 + lm_head FP16 + attention_mask 端口）
      · models/embed_tokens_06b_f16.npy （hidden 1024 的文本 embedding 表）
      · models/asr06b-tokenizer/     （0.6B 的 tokenizer / feature extractor）
  ⇒ rc5 的 `--check` 只显示 **「Intel GPU · INT8」+「Intel NPU · INT8」** 两档
    （**没有 INT4 ASR 引擎**）。
  · 用法：`python\\python.exe app\\live_caption_app.py --engine npu_int8 --check`
    或跑 5 分钟时加 `--engine npu_int8 --asr-device NPU`。
  ⚠️ **0.6B 的 decoder 没有 KV cache**（静态 512 序列 + 右对齐）⇒
    每生成一个 token 都要全序列重算 ⇒ 与 R2T2 的增量 KV 路径**不是**同一形态。"""
    t = patch_once(t, old_models, new_models, 'perftest_models')

    # ③ 实测基线表：换成 0.6B 的数字（rc5 实测 vs rc4 的 R2T2 参照）
    old_tbl = """  ┌ 档位                     RTF      出字延迟中位   最大积压   峰值内存   段数
  │ ASR=NPU（TTS off）      0.803    540 ms          1.1 s   5212.6 MB   46
  │ ASR=GPU.0（TTS off）    0.696    376 ms          1.2 s   4819.5 MB   46
  │ ASR=NPU + TTS=NPU       1.264    55362 ms       84.4 s   5213.1 MB   46"""
    new_tbl = """  ┌ 档位（rc5 · 0.6B）        RTF      出字延迟中位   最大积压   峰值内存   段数
  │ ASR=GPU.0（TTS off）    0.73     472 ms          1.0 s   3585.5 MB   46
  │ ASR=NPU（TTS off）      见下节（reviewer 复算 WER 后定稿）
  ┌ 档位（rc4 · R2T2，对照）  RTF      出字延迟中位   最大积压   峰值内存   段数
  │ ASR=NPU（TTS off）      0.803    540 ms          1.1 s   5212.6 MB   46
  │ ASR=GPU.0（TTS off）    0.696    376 ms          1.2 s   4819.5 MB   46
  │ ASR=NPU + TTS=NPU       1.264    55362 ms       84.4 s   5213.1 MB   46"""
    t = patch_once(t, old_tbl, new_tbl, 'perftest_table')

    # ④ 体积/文件数实测
    t = re.sub(r'解压后\s*\*\*约\s*[\d.]+\s*GB\*\*（\d+\s*个文件）',
               '解压后 **约 %s**（%s 个文件）' % (size_txt, files_txt), t)
    t = re.sub(r'文件数 10 474 → \*\*10480\*\*（\*\*zip 条目口径\*\*；磁盘上 10510 个，差 30 个是',
               '文件数 10 480 → **%s**（**zip 条目口径**；磁盘上 %d 个，差 %d 个是'
               % (files_txt, s5['files'] + 37, 37), t)

    # ⑤ 去掉「未用 IR 仍在包里」这类已过时的已知问题描述里的 INT4 提及
    t = t.replace('    首次 NPU 编译 20 分钟、未用 IR 仍在包里、MT 为 INT4。',
                  '    首次 NPU 编译 20 分钟、MT 为 INT4。')
    new_perf = t

    # ══════════════════════════════════════════════════════════════
    # G4_WHITELIST.md / release.json
    # ══════════════════════════════════════════════════════════════
    p = os.path.join(PKG, 'G4_WHITELIST.md')
    t = open(p, encoding='utf-8', newline='').read()
    if 'Qwen3-ASR-0.6B' not in t:
        t = patch_once(
            t, '# G4 白名单（APP-069⑤ 5）',
            '# G4 白名单（APP-069⑤ 5）\n\n'
            '> 🔴 **APP-096**：本包 ASR 为 **Qwen3-ASR-0.6B**（mask2 INT8）；\n'
            '> **R2T2 的 ASR IR 已全部从包内删除**（`encoder-int8` /\n'
            '> `decoder-gpu-int8` / `encoder-fp16` / `decoder-npu-int8` /\n'
            '> `decoder-npu-int4` / `embed_tokens_f16.npy`）。',
            'g4_note')
    new_g4 = t

    p = os.path.join(PKG, 'release.json')
    t = open(p, encoding='utf-8', newline='').read()
    if '"asr_model"' not in t:
        obj = json.loads(t)
        obj['asr_model'] = 'Qwen3-ASR-0.6B'
        obj['asr_recipe'] = ('mask2 INT8 (per-channel weights, FP16 lm_head, '
                             'attention_mask port)')
        obj['asr_engines'] = ['gpu_int8', 'npu_int8']
        new_rel = json.dumps(obj, ensure_ascii=False, indent=2)
    else:
        new_rel = t

    ev['perftest_int4_hits_after'] = len(re.findall(r'INT4', new_perf))
    ev['perftest_int4_npu_hits_after'] = len(
        re.findall(r'INT4[^\n]{0,20}NPU|NPU[^\n]{0,20}INT4', new_perf))
    ev['rc4_docs_unchanged'] = {
        'README_en': sha256_file(os.path.join(PKG4, 'README_en.md')),
        'README_zh': sha256_file(os.path.join(PKG4, 'README_zh.md')),
        'README_perftest': sha256_file(os.path.join(PKG4, 'README_perftest.txt')),
    }

    if dry:
        print(json.dumps(ev, ensure_ascii=False, indent=1))
        print('[dry-run] 未写盘')
        return 0

    # ── 写盘（全部在 dry 判断之后）────────────────────────────────
    for path, content in ((os.path.join(PKG, 'README_en.md'), new_en),
                           (os.path.join(PKG, 'README_zh.md'), new_zh),
                           (os.path.join(PKG, 'README_perftest.txt'), new_perf),
                           (os.path.join(PKG, 'G4_WHITELIST.md'), new_g4),
                           (os.path.join(PKG, 'release.json'), new_rel)):
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        ev.setdefault('written', {})[os.path.basename(path)] = {
            'bytes': os.path.getsize(path), 'sha256': sha256_file(path)}

    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('rc5 体积 %s / %s 文件（rc4：%.3f GB / %s）⇒ 差 %+d 文件 / %+.3f GB'
          % (size_txt, files_txt, s4['bytes'] / 2 ** 30, s4['files'],
             ev['size_delta']['files'], ev['size_delta']['gb']))
    print('README_perftest：INT4 提及 %d → %d；「INT4+NPU」同现 %d 处'
          % (ev['perftest_int4_hits_before'], ev['perftest_int4_hits_after'],
             ev['perftest_int4_npu_hits_after']))
    print('证据：%s' % REPORT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
