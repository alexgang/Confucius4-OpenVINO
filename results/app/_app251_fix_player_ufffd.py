#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_fix_player_ufffd.py —— §251：修掉 EXT `extension/player.js` 里的 **3×U+FFFD**。

🔴 **为什么必须修（真缺陷，不是误报）**
   `ext/extension/player.js` 里 `每段配音都要能算???同步误差` 有 **3 个 U+FFFD**
   ⇒ `check_internal_material.py --pkg <包目录>` 判 **FAIL**
   ⇒ `pack_v13.py` 的打包前闸门 `check_internal_material(PKG)` 也会 FAIL
   ⇒ **下一次出包直接被拦死**（§236 同类问题的复发）。

🔴 **根因（已定位到具体 commit）**
   EXT `9bd09dd`（§27 EXT-034/035 交卷，2026-11-02 21:56）引入。
   该行是**注释行**，3 个 U+FFFD ＝ **1 个 3 字节 UTF-8 汉字**被逐字节替换
   （ASCII 解码 with errors='replace' 的典型形态）。
   ⇒ **历史上从未有过干净版本**（`1686bf8` 及其后每个 commit 都是 3 个 U+FFFD）
   ⇒ **不能靠 git 回滚恢复**，只能按语义 + 仓库惯用词复原。

🔴 **复原依据（为什么是「出」）**
   ① 同文件 **1631 行**用同一动词族：`否则 player 端算不出「有符号同步误差」的对齐对象。`
   ② 全 EXT 仓库 `算出` **17** 次、`算准` **0** 次、`算得` 1 次
   ③ 语义：`每段配音都要能**算出**同步误差`（"能算出" = 能把数算出来）✔
   ⇒ 原字符 = **出**（UTF-8 `e5 87 ba`）。

🔴 **安全约束**
   * 只改**这 1 处 9 字节**；文件其余部分**逐字节不变**（写前在内存里断言）。
   * **不写客户包**、不写 `Confucius4_LiveCaption_v*`（版本纪律 APP-055）。
   * 备份在 `live_dub_ext/.tmp/app251/`（**不在** `extension/` 下 ⇒ 不会被成包脚本带进包）。
   * 临时文件 → `os.replace` 原子落盘。
   * 写后**另起脚本**复核（不靠本脚本自证）。
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys

EXT = r'C:\Users\Trekker-PTL\live_dub_ext'
TARGET = os.path.join(EXT, 'extension', 'player.js')
BAK_DIR = os.path.join(EXT, '.tmp', 'app251')
BAK = os.path.join(BAK_DIR, 'player.js.bak_app251_ufffd')

#: 3 个连续的 U+FFFD（UTF-8 编码各 3 字节 ⇒ 共 9 字节）
MOJIBAKE = b'\xef\xbf\xbd' * 3
#: 复原后的原字符（UTF-8 3 字节）
ORIGINAL = '出'.encode('utf-8')

#: 复原后必须能读通的一整句（**唯一命中断言**的锚点）
ANCHOR_BEFORE = '每段配音都要能算'.encode('utf-8')
ANCHOR_AFTER = '同步误差'.encode('utf-8')


def main() -> int:
    with io.open(TARGET, 'rb') as f:
        raw = f.read()
    before_len = len(raw)
    before_sha = hashlib.sha256(raw).hexdigest()

    # ── 判据①：待修片段**恰好 1 处**（多处 ⇒ 说明根因判断错了 ⇒ fail-closed）──
    n = raw.count(MOJIBAKE)
    print('待修片段出现次数 = %d' % n)
    if n != 1:
        print('!! 不是恰好 1 处 ⇒ 中止（不写）')
        return 2

    # ── 判据②：锚点邻接（确保改的是**那一行**，不是别处）──
    i = raw.find(MOJIBAKE)
    ctx_before = raw[max(0, i - 60):i]
    ctx_after = raw[i + len(MOJIBAKE):i + len(MOJIBAKE) + 60]
    if not ctx_before.endswith(ANCHOR_BEFORE):
        print('!! 前锚点不匹配 ⇒ 中止')
        return 2
    if not ctx_after.startswith(ANCHOR_AFTER):
        print('!! 后锚点不匹配 ⇒ 中止')
        return 2
    print('锚点匹配 ✔  前=…%s  后=%s…'
          % (ctx_before[-12:].decode('utf-8'), ctx_after[:12].decode('utf-8')))

    # ── 判据③：在**内存**里做替换 + 逐字节复核（写盘前）──
    new = raw[:i] + ORIGINAL + raw[i + len(MOJIBAKE):]

    # ③a 除该 9 字节外，其余**逐字节不变**
    assert new[:i] == raw[:i], '前缀变了'
    assert new[i + len(ORIGINAL):] == raw[i + len(MOJIBAKE):], '后缀变了'
    # ③b 只差这 9→3 字节
    assert len(new) == before_len - 6, '长度差异常'
    # ③c 复原后 U+FFFD 归零
    assert new.count(b'\xef\xbf\xbd') == 0, '仍有 U+FFFD'
    # ③d 复原后是**合法 UTF-8** 且含完整句子
    t = new.decode('utf-8')                      # 不许抛
    assert '每段配音都要能算出同步误差' in t, '复原后的句子不对'
    # ③e **还原式复核**：把新字节里的 `出` 换回 3×U+FFFD ⇒ 必须与原文件逐字节相等
    assert t.replace('每段配音都要能算出同步误差',
                     '每段配音都要能算' + '�' * 3 + '同步误差'
                     ).encode('utf-8') == raw, '还原式复核失败（还原后 != 原文件）'
    print('内存复核 5/5 PASS（逐字节不变 / 长度 -6 / U+FFFD 归零 / 合法 UTF-8 / 还原式相等）')

    # ── 备份（写到 .tmp ⇒ 不会被成包脚本带进包）──
    if not os.path.isdir(BAK_DIR):
        os.makedirs(BAK_DIR)
    if not os.path.exists(BAK):
        shutil.copy2(TARGET, BAK)
        print('备份：%s' % BAK)
    else:
        bak = io.open(BAK, 'rb').read()
        assert hashlib.sha256(bak).hexdigest() == before_sha, '既有备份与当前文件不一致 ⇒ 中止'
        print('备份已存在且一致 ✔')

    # ── 原子落盘 ──
    tmp = TARGET + '.tmp_app251'
    with io.open(tmp, 'wb') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, TARGET)

    after_len = os.path.getsize(TARGET)
    print('已写入：%d B → %d B（-6）' % (before_len, after_len))
    print('sha256 before=%s' % before_sha[:16])
    print('sha256 after =%s' % hashlib.sha256(io.open(TARGET, 'rb').read()).hexdigest()[:16])
    return 0


if __name__ == '__main__':
    sys.exit(main())
