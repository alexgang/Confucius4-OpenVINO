#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP §15：把仓库 `tts_worker.py` 的 import 死锁修复同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）。

## 要同步的变更（唯一一处）

在 `main()` 里 `args = ap.parse_args()` 之后、`w = TTSWorker(...)` 之前，
插入「主线程预导入 numpy / scipy.linalg」。

### 为什么必须修（不是可选优化）

worker 经 `tts_service.TTSService`（`Popen(stdout=PIPE)`）起时：
- 模型加载跑在**后台线程**（`threading.Thread(target=self._safe_load)`），
  它要 import 的 **numpy / scipy 是 C 扩展** ⇒ import 期间持有 importlib 的
  **模块级锁**；
- 与此同时主线程阻塞在 `for line in sys.stdin`（首次迭代触发
  io/textiobuffer 加载），同样要这把锁
  ⇒ **互相等待的 import 死锁**。

faulthandler 实测栈（`/tmp/g3.log`）：
    `numpy/_core/multiarray.py:11 in create_module`

后果：worker **一行输出都不发** ⇒ 主进程永远 `state=loading`
⇒ drain 超时、**0 句播完** ⇒ 端到端 ABBA 的 TTS 侧完全无数据。

修法：把重依赖 import 提到**主线程**、且在**任何后台线程启动之前**
（实测预导入 0.3 s；修复后 worker 9.4 s 正常 emit `ready`）。

## 用法
    python live_caption/sync_c137_to_pkg.py            # 执行
    python live_caption/sync_c137_to_pkg.py --check    # 只校验不写
"""
import argparse
import hashlib
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PKG_APP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app'

REPO_FILE = os.path.join(REPO, 'live_caption', 'tts_worker.py')
PKG_FILE = os.path.join(PKG_APP, 'tts_worker.py')

# ── 锚点：客户包里**必须存在且唯一**的那一行 ────────────────────────────
ANCHOR_OLD = (
    "    args = ap.parse_args()\n"
    "\n"
    "    w = TTSWorker(device=args.device, voice=args.voice, out_device=args.out_device,\n"
)

# ── 替换成：预导入 + 原文 ────────────────────────────────────────────────
ANCHOR_NEW = (
    "    args = ap.parse_args()\n"
    "\n"
    "    # \U0001f534\U0001f534 [APP-FIX-20261023] 主线程**预导入**重依赖（numpy / scipy.linalg）\n"
    "    #\n"
    "    # 症状：worker 经 `tts_service.TTSService`（`Popen(stdout=PIPE)`）起时\n"
    "    #      **stdout 一行都不输出**，主进程永远停在 `state=loading`，\n"
    "    #      drain 超时、0 句播完（见 status/app/STATUS_APP.md §15）。\n"
    "    #\n"
    "    # 根因：模型加载跑在**后台线程**（`threading.Thread(target=self._safe_load)`），\n"
    "    #      而它要 import 的 numpy / scipy 是 **C 扩展** ⇒ import 期间持有\n"
    "    #      importlib 的**模块级锁**；与此同时主线程正阻塞在\n"
    "    #      `for line in sys.stdin`（首次迭代会触发 io/textiobuffer 的加载），\n"
    "    #      同样需要这把锁 ⇒ **互相等待的 import 死锁**。\n"
    "    #      faulthandler 实测栈：后台线程停在\n"
    "    #      `numpy/_core/multiarray.py:11 in create_module`。\n"
    "    #\n"
    "    # 为什么之前没暴露：`import tts_engine`（纯 python）不触发 C 扩展加载，\n"
    "    #      单独测 worker 一切正常 ⇒ 只有「Popen + 后台加载 + stdin 阻塞」\n"
    "    #      三者同时成立才复现。\n"
    "    #\n"
    "    # 修法：把重依赖的 import 提到**主线程**、且在**任何后台线程启动之前**。\n"
    "    #      实测预导入耗时 0.3 s，修复后 worker 9.4 s 正常 emit `ready`。\n"
    "    try:\n"
    "        import numpy  # noqa: F401\n"
    "        import scipy.linalg  # noqa: F401\n"
    "    except Exception:\n"
    "        # 预导入失败不致命：退回旧行为（下游仍会在 import 处报错，但有 traceback）\n"
    "        pass\n"
    "\n"
    "    w = TTSWorker(device=args.device, voice=args.voice, out_device=args.out_device,\n"
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_text(path, text):
    # newline='' ⇒ 保留原文换行符（不把 CRLF 改写成 LF）
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只校验不写')
    args = ap.parse_args()

    if not os.path.isfile(REPO_FILE):
        print('找不到仓库文件：', REPO_FILE)
        return 2
    if not os.path.isfile(PKG_FILE):
        print('找不到客户包文件：', PKG_FILE)
        return 2

    repo_txt = read_text(REPO_FILE)
    pkg_txt = read_text(PKG_FILE)

    # 仓库必须**已经**含修复（否则说明仓库没改，脚本无意义）
    if 'APP-FIX-20261023' not in repo_txt:
        print('❌ 仓库文件里没有 APP-FIX-20261023 标记 ⇒ 仓库侧未修复')
        return 3

    n_new = pkg_txt.count(ANCHOR_NEW)
    n_old = pkg_txt.count(ANCHOR_OLD)
    print('客户包命中：新块 %d 次 / 旧锚点 %d 次' % (n_new, n_old))

    if n_new == 1 and n_old == 0:
        print('✅ 客户包已是修复版（幂等 no-op）')
        print('   仓库 SHA256 :', sha256(REPO_FILE))
        print('   客户包 SHA256:', sha256(PKG_FILE))
        return 0

    if n_old != 1:
        print('❌ 旧锚点命中 %d 次（应为 1）⇒ 客户包与预期不符，**中止**' % n_old)
        return 4

    if args.check:
        print('--check：命中唯一旧锚点，未写入')
        return 0

    before = sha256(PKG_FILE)
    new_txt = pkg_txt.replace(ANCHOR_OLD, ANCHOR_NEW)
    # 🔴 唯一命中断言
    assert new_txt.count(ANCHOR_NEW) == 1, '替换后新块应恰好 1 次'
    assert new_txt.count(ANCHOR_OLD) == 0, '替换后旧锚点应消失'
    write_text(PKG_FILE, new_txt)
    after = sha256(PKG_FILE)

    # 逐字节校验：客户包文件必须与仓库文件完全一致（本轮改动只在这一个文件）
    same = sha256(PKG_FILE) == sha256(REPO_FILE)
    print('✅ 已同步')
    print('   客户包 SHA256 before:', before)
    print('   客户包 SHA256 after :', after)
    print('   仓库   SHA256       :', sha256(REPO_FILE))
    print('   与仓库逐字节一致   :', same)
    return 0 if same else 5


if __name__ == '__main__':
    sys.exit(main())
