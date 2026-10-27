#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-028① —— 把 **`device_config.py` 的「NPU 独占给 TTS」**定点同步到客户包。

🔴🔴 纪律（`MEMORY.md` 一.1）：
  - 仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本** ⇒ **禁止整目录覆盖**；
  - 替换块**从 git 自动派生**（不手抄任何代码）⇒ 抄错的风险归零；
  - 每个块在目标文件里**唯一命中**（`count == 1`）⇒ 否则 FAIL，不猜、不 fuzzy；
  - 🔴🔴 **换行归一化**（§65 铁律）：仓库 .py 是 CRLF、客户包是 LF（现状是**混合**）
    ⇒ 派生前必须把**两端**都归一化为 LF，否则裸 diff 把整文件当一块。
  - 🔴🔴 **difflib 用 `get_grouped_opcodes(n=3)`**（裸 `get_opcodes` 的纯新增块
    old 为空串 ⇒ `count('')=len+1` ⇒ 假命中）。

## 为什么单独一个脚本
`sync_s70_app028_to_pkg.py`（同一轮的另一个脚本）同步的是
`tts_worker.py` / `tts_service.py` / `live_caption_app.py` / `offline_reader.py`
**四个**文件，**不含** `device_config.py`
⇒ 本脚本**只**处理 `device_config.py`，**两者不重叠**（避免同文件双写）。

## 基线 commit
🔴 不用 `HEAD`（本轮提交后 HEAD 就是新版本 ⇒ 无法派生替换块）
⇒ 用**同步前的固定 commit** `5e2aef7`（= §69 的客户包同步提交；
  已用 SHA256 逐文件核对：包内 `device_config.py` 与该 commit **逐字一致**）。

用法：
    python results/app/sync_s70_device_config_to_pkg.py --check   # 只查差异
    python results/app/sync_s70_device_config_to_pkg.py            # 同步
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import os
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PKG_DEFAULT = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
BASE_COMMIT = '5e2aef7'
REL = 'device_config.py'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_show(rev: str, rel: str) -> str:
    out = subprocess.run(['git', 'show', '%s:%s' % (rev, rel)],
                         cwd=REPO, capture_output=True)
    if out.returncode != 0:
        raise SystemExit('git show 失败: %s (%s)'
                         % (rel, out.stderr.decode('utf-8', 'replace')))
    # 🔴 原始串含 CRLF ⇒ 归一化为 LF（§65）
    return out.stdout.decode('utf-8').replace('\r', '')


def derive_blocks(old: str, new: str):
    """old→new 派生「精确替换块」（带 n=3 上下文），每个块唯一命中。

    🔴🔴 必须用 `get_grouped_opcodes(n=3)`：裸 `get_opcodes()` 会让「纯新增块」
    的 old 变空串 ⇒ `str.count('') == len+1` ⇒ 误导性「命中 N 次」+ 静默跳过真块。
    """
    a = old.splitlines(keepends=True)
    b = new.splitlines(keepends=True)
    blocks = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for group in sm.get_grouped_opcodes(n=3):
        o, n = [], []
        for tag, i1, i2, j1, j2 in group:
            o.append(''.join(a[i1:i2]))
            n.append(''.join(b[j1:j2]))
        ob, nb = ''.join(o), ''.join(n)
        if ob != nb:
            blocks.append((ob, nb))
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true',
                    help='只查差异，不写盘')
    ap.add_argument('--pkg', default=PKG_DEFAULT)
    args = ap.parse_args()
    pkg_root = args.pkg
    dst = os.path.join(pkg_root, 'app', REL)
    if not os.path.isfile(dst):
        print('❌ 客户包没有 %s ⇒ 退出' % dst)
        return 1

    print('=' * 74)
    print('APP-028① 定点同步：device_config.py（NPU 独占给 TTS）')
    print('客户包根 = %s' % pkg_root)
    print('基线     = %s' % BASE_COMMIT)
    print('模式     = %s' % ('CHECK（只读）' if args.check else '写入'))
    print('=' * 74)

    base = git_show(BASE_COMMIT, 'live_caption/' + REL)
    # 🔴 包文件用通用换行读（自动去 \r）⇒ 已是 LF
    cur = io.open(dst, encoding='utf-8').read()
    print('\n基线与包内是否逐字一致 = %s'
          % ('YES' if base == cur else 'NO（包内已有其它改动）'))

    # 目标 = 仓库**工作区**当前内容（LF 归一化）
    target = io.open(os.path.join(REPO, 'live_caption', REL),
                     encoding='utf-8').read().replace('\r', '')

    # 🔴🔴 **以「包当前」为起点派生**（不是以基线为起点）：
    #   以基线派生 ⇒ 已同步后重跑，替换块的 old 段**在包里已不存在**
    #   ⇒ 「命中 0 次」⇒ **不幂等**（每次重跑都报错）。
    #   以包当前派生 ⇒ 已同步 ⇒ 无块 ⇒ no-op（**幂等**）。
    blocks = derive_blocks(cur, target)
    print('派生替换块 = %d（包当前 → 仓库工作区）' % len(blocks))
    if not blocks:
        print('（无改动，已 == 仓库工作区 ⇒ 幂等 no-op）')
        return 0

    out = cur
    fail = 0
    for i, (ob, nb) in enumerate(blocks, 1):
        cnt = out.count(ob)
        if cnt != 1:
            print('  ❌ 块 %d: 命中 %d 次（要求恰好 1，否则跳过）' % (i, cnt))
            fail += 1
            continue
        out = out.replace(ob, nb, 1)
        print('  ✅ 块 %d: 唯一命中并替换（-%d/+%d 行）'
              % (i, ob.count('\n'), nb.count('\n')))

    if fail:
        print('\n⚠️ 有 %d 块未应用 ⇒ **不写盘**' % fail)
        return 1

    # 🔴🔴 验证：替换后必须 == 仓库工作区（LF 归一化）
    if out != target:
        print('\n❌ 替换后 != 仓库工作区（差 %d 行）⇒ 不写盘'
              % abs(out.count('\n') - target.count('\n')))
        return 1

    if args.check:
        print('\n[CHECK] 将写入 %d → %d 字节（LF）' % (len(cur), len(out)))
        return 0

    # 🔴 写盘保留包内原有的换行风格（本包 CRLF）
    orig_has_crlf = b'\r\n' in io.open(dst, 'rb').read()
    data = (out.replace('\n', '\r\n') if orig_has_crlf else out).encode('utf-8')
    io.open(dst, 'wb').write(data)
    h = sha256_bytes(data)
    print('\n💾 已写入: %s' % dst)
    print('   字节数 = %d' % len(data))
    print('   sha256 = %s' % h)
    return 0


if __name__ == '__main__':
    sys.exit(main())
