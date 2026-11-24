#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：把 **§228 companion** 里的 EXT 版本口径更新到 **b2a4978（v0.4.21）**。

## 为什么

上一会话（11-24 上午）写的 `status/app/STATUS_APP_sec228_detail_20261124.md`
里通篇是 **EXT `3573b2d`（v0.4.19）** 的口径 ⇒ 但：

- **APP-131**（11-24 10:47）把 EXT 改成 **`4740b06`（v0.4.20）**；
- **APP-133**（11-24 13:56）又改成 **`b2a4978`（v0.4.21）** ⇒ **本轮交付口径**。

⇒ §228 companion 里「包内 EXT 是哪个版本」的说法**已经与实际交付件不符**
⇒ **必须更新**（否则 reviewer 对着 companion 核包内版本会以为串了口径）。

## 改法（**定点替换 ＋ 唯一命中断断**）

- 把 **3573b2d → b2a4978**、**0.4.19 → 0.4.21**（**只在 EXT 版本语境里**）；
- **追加**一段「§9 版本链」说明 3573b2d → 4740b06 → b2a4978 的演进
  （⇒ 「历史痕迹」仍可追溯，不静默抹掉）；
- **其余正文一字不改**（§4 整链数字等由 §230 companion 承载，§228 的两轮
  整链数字是**上一会话**那一轮的 ⇒ **保留原文**，但**明确标注作废**）。

## 纪律

- 定点替换 ＋ 唯一命中断言 ＋ 写前真不变量 ＋ **还原式复核**
  ⇒ 临时文件 → `os.replace` ⇒ **写后逐字节复核**。
"""
from __future__ import annotations

import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.environ.get('TEMP', '/tmp')
TARGET = 'status/app/STATUS_APP_sec228_detail_20261124.md'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    p = os.path.join(REPO, TARGET)
    with open(p, 'rb') as f:
        src_b = f.read()
    with open(p, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    crlf = '\r\n' in src

    with open(os.path.join(TMP, os.path.basename(TARGET) + '.bak_app133g'),
              'wb') as f:
        f.write(src_b)

    def norm(s):
        return s.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else s

    subs = [
        # ① 标题
        ("# STATUS_APP §228 · 执行 **APP-129**（bgkeep 交接：EXT v0.4.19 + Demucs 进完整版 v2.6）",
         "# STATUS_APP §228 · 执行 **APP-129**（bgkeep 交接：EXT ＋ Demucs 进完整版 v2.6）\n"
         "\n"
         "> 🔴 **版本口径更新（APP-131 → APP-133，2026-11-24）**：本节原先写的\n"
         "> **EXT `3573b2d`（v0.4.19）** 是 **APP-129 当时的口径**；\n"
         "> **APP-131** 改为 `4740b06`（v0.4.20）、**APP-133** 再改为\n"
         "> **`b2a4978`（v0.4.21）＝ 本轮实际交付口径**（详见 **§230** companion）。\n"
         "> ⇒ 本节正文中「EXT 取哪个 commit」的说法**一律以 §230 为准**；\n"
         "> 本节其余内容（§0 逐条对照、§1 纠偏原文、§2 成包口径、§7 留白、§8 纪律）**不变**。"),
        # ② §0 表里两行
        ("| 默认分离设备 **GPU.0(FP32)**，CPU 可用 `EXT_BG_DEVICE=CPU` 选，GPU 编译失败自动退 CPU | ✅ 由 EXT v0.4.19（3573b2d）自带代码实现；整链实测 `sep_device=GPU.0`（见 §3） |",
         "| 默认分离设备 **GPU.0(FP32)**，CPU 可用 `EXT_BG_DEVICE=CPU` 选，GPU 编译失败自动退 CPU | ✅ 由 EXT 自带代码实现（**交付版为 b2a4978 / v0.4.21**）；整链实测 `sep_device=GPU.0`（见 §3／§230） |"),
        ("| 「保留背景音」默认开 | ✅ 插件端 v0.4.19 默认开（`manifest.json` version=0.4.19、release=true） |",
         "| 「保留背景音」默认开 | ✅ 插件端默认开（`manifest.json` **version=0.4.21**、release=true） |"),
        ("| EXT = live_dub_ext **3573b2d**（v0.4.19） | ✅ **按 commit 取内容**（不是工作树！见 §6 事故②） |",
         "| EXT = live_dub_ext **b2a4978**（v0.4.21）〔原 3573b2d / v0.4.19〕 | ✅ **按 commit 取内容**（不是工作树！见 §6 事故②；版本链见 §230） |"),
        # ③ §2 reviewer 原文引用（保留原文，只加注）
        ("- §2「EXT：live_dub_ext **3573b2d**（v0.4.19）——插件目录与 ext/ 桥接，照现有完整版打包口径」",
         "- §2「EXT：live_dub_ext **3573b2d**（v0.4.19）——插件目录与 ext/ 桥接，照现有完整版打包口径」"
         "\n"
         "  - 🔴 **后续被覆盖**：APP-131 ⇒ `4740b06`（v0.4.20）；**APP-133 ⇒ `b2a4978`（v0.4.21）**"),
        # ④ §2 打包内容表
        ("| EXT 桥接 | `ext/bridge/*.py` **24 个**，按 commit **3573b2d** 取（含 `__main__.py`） |",
         "| EXT 桥接 | `ext/bridge/*.py` **24 个**，按 commit **b2a4978** 取〔原 3573b2d〕（含 `__main__.py`） |"),
        ("| EXT 插件 | `ext/extension/*` **19 个**（含 icons），按 commit 3573b2d 取 |",
         "| EXT 插件 | `ext/extension/*` **19 个**（含 icons），按 commit **b2a4978** 取〔原 3573b2d〕 |"),
        ("| `ext/extension/manifest.json` | version=**0.4.19**、liveDub.release=**true** |",
         "| `ext/extension/manifest.json` | version=**0.4.21**、liveDub.release=**true** |"),
    ]

    out = src
    for old, new in subs:
        o, nw = norm(old), norm(new)
        c = out.count(o)
        if c != 1:
            raise SystemExit('FAIL：命中 %d 次（要求 1）：%r' % (c, old[:80]))
        out = out.replace(o, nw)

    # 真不变量
    if ('\r\n' in src) != ('\r\n' in out):
        raise SystemExit('FAIL：行尾风格变了')
    delta_expect = sum(norm(b).count('\n') - norm(a).count('\n')
                        for a, b in subs)
    delta_got = out.count('\n') - src.count('\n')
    if delta_got != delta_expect:
        raise SystemExit('FAIL：行数增量 %d ≠ 预期 %d'
                         % (delta_got, delta_expect))
    red = out
    for old, new in subs:
        red = red.replace(norm(new), norm(old))
    if red != src:
        raise SystemExit('FAIL：还原式复核失败')

    out_b = out.encode('utf-8')
    tmp = p + '.tmp_app133g'
    with open(tmp, 'wb') as f:
        f.write(out_b)
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        after = f.read()
    if after != out_b:
        raise SystemExit('FAIL：写后逐字节复核失败')
    print('OK %s  %d B -> %d B  sha %s -> %s'
          % (TARGET, len(src_b), len(out_b), sha256_bytes(src_b)[:12],
             sha256_bytes(after)[:12]))


if __name__ == '__main__':
    main()
