#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app106_upgrade_pkg_to_v16.py —— 把客户包从 v1.5 升到 v1.6（版本标识升级）。

🔴 **为什么用定点替换而不是整目录覆盖**（继承 §34/§47/§72 的纪律）
------------------------------------------------------------------
仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**；本脚本只动**客户包根目录
的文本文件**（README_zh.md / README_en.md / NOTICE），**不碰** `app/` 下的代码
（代码同步由 `sync_*.py` 定点脚本负责）⇒ 绝无「整目录覆盖」的风险。

🔴 **唯一命中断言**：每个替换块在目标文件里必须**恰好命中 1 次**。
   命中 0 次 ⇒ 说明版本号已经改过（脚本可重跑，幂等）或文本漂移 ⇒ **报错退出**，
   绝不静默跳过（静默跳过 = 改了一半 = 交付出「半升版」包）。

用法
----
    python results/app/app106_upgrade_pkg_to_v16.py --pkg <v1.6 包目录>
    python results/app/app106_upgrade_pkg_to_v16.py --pkg <dir> --check
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys

# ── 版本标识替换块（(文件, 旧串, 新串) 三元组）──────────────────────
# ⚠️ 每个旧串都必须是**唯一**的整行/整段锚点。
# ⚠️ 历史版本的说明段**保留**（可追溯），只改**标题**与**新增 v1.6 段**。

ZH_V16_SECTION = """## v1.6 改动说明

本轮重点改的是**语音输出（朗读译文）的播放方式**：以前合成一句要**等这句播完**
才去合成下一句，句子之间白白串行等待、越积越慢；而且一旦积压超过阈值，
程序会**直接中止已经合成好的句子** —— 说过的内容会凭空消失。

### ① 默认设备摆放定案（三个模块各走各的加速器）

| 模块 | 默认设备 | 说明 |
|---|---|---|
| 语音识别（ASR） | Intel 集显（GPU.0） | 走集显，不与语音输出抢 NPU |
| 实时翻译 | Intel 集显（GPU.0） | 同上 |
| **语音输出（TTS）** | **Intel NPU** | **NPU 只给语音输出独占使用** |

> ⚠️ ASR / 翻译的**回退链里不再有 NPU** —— 避免两者和语音输出抢同一个
> 加速器，导致三边互相拖慢。CUDA **不是默认值**。

### ② 语音输出改为「边合成边播」（生产 / 消费者架构）

现在合成线程把一句音频写进队列就**立刻**返回去合成下一句，
播放由独立的看门狗线程按**原顺序**取出：

- **句内、句间严格保序** —— 不会出现后一句盖到前一句上面；
- 队列为空时输出静音并**计入欠载次数**（而不是悄悄丢掉内容）。

### ③ 不再丢句

旧实现在语音积压超阈值时会「中止已写入的句子」，导致**说过的内容直接消失**。
本版**删除该丢句逻辑**（含所有「中止已写入句子」的路径）：
积压只做提示，不再丢内容。「取消」改为把整句从队列里**摘除**。

> ⚠️ 本条**只保证代码已实现**；「丢句数为 0」的实听验收需由使用方
> 在真实会话中确认（见「已知限制」）。

### ④ 界面底栏实时显示「语音滞后 X 秒」

底栏会实时显示当前语音输出的积压秒数 —— 合成跟不跟得上，**看一眼就知道**，
不必猜。

"""

EN_V16_SECTION = """## What's new in v1.6

This round changes **how spoken translations are played**. Previously the
synthesis thread had to wait for a sentence to **finish playing** before it
started the next one, so the sentences were serialized with dead waiting time
in between, and the backlog kept growing. On top of that, once the backlog
passed a threshold the program would **abort sentences that had already been
synthesized** — content you had already spoken simply disappeared.

### ① The default device layout is now fixed (each module gets its own accelerator)

| Module | Default device | Why |
|---|---|---|
| Speech recognition (ASR) | Intel integrated GPU (GPU.0) | Runs on the iGPU, does not compete with speech output for the NPU |
| Real-time translation | Intel integrated GPU (GPU.0) | Same |
| **Speech output (TTS)** | **Intel NPU** | **The NPU is used exclusively by speech output** |

> ⚠️ The **fallback chains for ASR and translation no longer include the NPU**
> — otherwise all three would compete for the same accelerator and slow each
> other down. CUDA is **not** a default.

### ② Speech output now synthesizes and plays at the same time (producer / consumer)

The synthesis thread now returns as soon as it has written a sentence's audio
into the queue and moves on to the next sentence, while an independent
watchdog thread takes the audio out **in the original order**:

- **Strict order within and across sentences** — a later sentence never
  overlaps an earlier one;
- when the queue is empty the output is silent and the underrun is
  **counted**, instead of quietly dropping content.

### ③ No more dropped sentences

The old implementation aborted already-synthesized sentences once the speech
backlog exceeded the threshold, so **spoken content simply vanished**. This
version **removes that dropping logic** (including every "abort an
already-written sentence" path): the backlog is only reported, nothing is
dropped. "Cancel" now removes the whole sentence from the queue.

> ⚠️ This item only guarantees the **code is implemented**; the "zero dropped
> sentences" acceptance still has to be confirmed by listening in a real
> session (see "Known limitations").

### ④ The status bar now shows "speech lag: N seconds" live

The bottom bar shows the current speech-output backlog in seconds — whether
synthesis keeps up is now visible at a glance instead of a guess.

"""

#: (相对路径, 旧串, 新串, 说明, guard)
#:
#: 🔴 **guard 的必要性**（本脚本第一版实测踩到的坑）
#: --------------------------------------------------
#: 「插入 v1.6 段」的旧串是 `## v1.5 改动说明\n` —— 这个锚点在**插入之后依然存在**
#: （v1.5 段按「历史可追溯」要求保留）⇒ 脚本重跑时旧串**仍然命中 1 次**
#: ⇒ 会**再插一份 v1.6 段** ⇒ 交付出「重复段」的坏包。
#: 同理「首段补 v1.6 一句」是**前缀插入**，原句保留 ⇒ 重跑也会重复。
#:
#: ⇒ 每个替换块带一个 **guard**（本次插入产生的**特征串**）：
#:    **guard 已存在 ⇒ 该块视为已完成 ⇒ SKIP（幂等）**。
#:    guard 必须是**本次插入独有的串**（不能是旧串本身）。
REPLACEMENTS = [
    ('README_zh.md',
     '# Confucius4-R2T2 实时字幕（技术评估版 v1.5）\n',
     '# Confucius4-R2T2 实时字幕（技术评估版 v1.6）\n',
     '标题版本号 v1.5 → v1.6',
     '# Confucius4-R2T2 实时字幕（技术评估版 v1.6）'),

    ('README_zh.md',
     '## v1.5 改动说明\n',
     ZH_V16_SECTION + '## v1.5 改动说明\n',
     '插入 v1.6 改动说明段（保留 v1.5 段）',
     '## v1.6 改动说明'),

    ('README_zh.md',
     '**v1.5 起设备列表按本机真实硬件显示',
     '**v1.6 起语音输出改为「边合成边播」、不再丢句，'
     '默认设备摆放定案（ASR/翻译走集显、语音输出独占 NPU）**。'
     '**v1.5 起设备列表按本机真实硬件显示',
     '首段简介补 v1.6 一句',
     '**v1.6 起语音输出改为「边合成边播」'),

    ('README_en.md',
     '# Confucius4-R2T2 Live Captions (technical evaluation build v1.5)\n',
     '# Confucius4-R2T2 Live Captions (technical evaluation build v1.6)\n',
     '标题版本号 v1.5 → v1.6',
     '# Confucius4-R2T2 Live Captions (technical evaluation build v1.6)'),

    ('README_en.md',
     "## What's new in v1.5\n",
     EN_V16_SECTION + "## What's new in v1.5\n",
     "插入 v1.6 段（保留 v1.5 段）",
     "## What's new in v1.6"),

    ('README_en.md',
     '**In v1.5 the device list reflects the hardware actually present',
     '**In v1.6 speech output synthesizes and plays at the same time and no '
     'longer drops sentences, and the default device layout is fixed (ASR and '
     'translation on the iGPU, speech output with exclusive use of the NPU)**. '
     '**In v1.5 the device list reflects the hardware actually present',
     '首段简介补 v1.6 一句',
     '**In v1.6 speech output synthesizes and plays at the same time'),

    # 🔴 NOTICE 自称 v1.4 —— 这是**历史遗留错标**（v1.5 打包时没改），
    #    客户按 NOTICE 核对版本会得到错误结论 ⇒ 本轮一并纠正到 v1.6。
    ('NOTICE',
     'Confucius4 LiveCaption v1.4 — 第三方组件归属与许可证\n',
     'Confucius4 LiveCaption v1.6 — 第三方组件归属与许可证\n',
     'NOTICE 标题版本号 v1.4 → v1.6（历史错标纠正）',
     'Confucius4 LiveCaption v1.6 — 第三方组件归属与许可证'),
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True, help='客户包目录（V1.6）')
    ap.add_argument('--check', action='store_true',
                    help='只检查（不写盘）：报告每个替换块的命中次数')
    ap.add_argument('--json', default=None, help='把结果写成 JSON 证据文件')
    args = ap.parse_args()

    PKG = args.pkg
    if not os.path.isdir(PKG):
        print('!! 包目录不存在: %s' % PKG)
        return 1

    # 先把所有文件读进来（一次读，避免改一个文件后另一个文件读不到）
    contents = {}
    for rel, _old, _new, _desc, _guard in REPLACEMENTS:
        if rel not in contents:
            path = os.path.join(PKG, rel.replace('/', os.sep))
            if not os.path.isfile(path):
                print('!! 缺少文件: %s' % path)
                return 1
            with open(path, 'rb') as f:
                contents[rel] = f.read()

    results = []
    n_hit = 0
    n_miss = 0
    n_skip = 0

    for rel, old, new, desc, guard in REPLACEMENTS:
        raw = contents[rel]
        # 统一按 LF 处理（换行归一化），写盘时恢复原风格
        crlf = raw.count(b'\r\n') > 0
        text = raw.replace(b'\r\n', b'\n').decode('utf-8')

        # 🔴 **guard 优先**：guard 已存在 ⇒ 本块已完成 ⇒ 幂等跳过
        if guard in text:
            results.append({'file': rel, 'desc': desc, 'hits': -1,
                            'status': 'SKIP(guard已存在=已完成)'})
            print('  [SKIP] %s —— %s（guard 已存在）' % (rel, desc))
            n_skip += 1
            continue

        cnt = text.count(old)
        if cnt == 0:
            # 🔴 命中 0 次：锚点漂移（不是「已改过」）⇒ **报错退出**，
            #    绝不静默跳过（静默跳过 = 改了一半 = 交付出「半升版」包）。
            print('!! [FAIL] %s: 旧串命中 0 次 ⇒ 锚点漂移，拒绝修改' % rel)
            print('     旧串: %r' % old[:80])
            return 1
        elif cnt > 1:
            print('!! [FAIL] %s: 旧串命中 %d 次（要求恰好 1 次）⇒ 拒绝修改'
                  % (rel, cnt))
            print('     旧串: %r' % old[:80])
            return 1
        else:
            status = 'HIT(唯一)'
            n_hit += 1
            if not args.check:
                text = text.replace(old, new, 1)
                data = text.replace('\n', '\r\n').encode('utf-8') if crlf \
                    else text.encode('utf-8')
                path = os.path.join(PKG, rel.replace('/', os.sep))
                with io.open(path, 'wb') as f:
                    f.write(data)
                contents[rel] = data
        results.append({'file': rel, 'desc': desc, 'hits': cnt,
                        'status': status})
        print('  [%s] %s —— %s' % ('HIT ' if cnt == 1 else 'SKIP',
                                    rel, desc))

    print()
    print('替换块: 唯一命中 %d / 未命中(幂等跳过) %d' % (n_hit, n_skip))

    if args.check:
        print('--check 模式：未写盘')
    else:
        for rel in sorted(set(r['file'] for r in results)):
            path = os.path.join(PKG, rel.replace('/', os.sep))
            b = open(path, 'rb').read()
            print('  %-16s %8d B  SHA256 %s' % (rel, len(b),
                                                sha256_bytes(b)[:16]))

    if args.json:
        with io.open(args.json, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'pkg': PKG, 'check': args.check,
                       'n_hit': n_hit, 'n_skip': n_skip,
                       'replacements': results}, f,
                      ensure_ascii=False, indent=1)
        print('证据文件:', args.json)

    return 0


if __name__ == '__main__':
    sys.exit(main())
