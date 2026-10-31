#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app189b —— **定点替换** `status/app/STATUS_APP.md` 里的 **§119 章节**（§118 及以前一字不动）。

🔴🔴🔴 **为什么需要这个脚本**
--------------------------
§119 是**本轮自己的**章节，已随 `006d801` 提前入库；
但本轮在 §119 入库**之后**又补了两节新内容（§5.5 `sync_c136` 修复 /
§5.6 行尾转换留档）⇒ 需要把 §119 的正文**整段换掉**。

🔴 **纪律**（与 §118/§119 写入器一致）：
  * **只替换** `### §119` 起始行**到文件末尾**这一段；
  * §109…§118 及头部**一个字节都不动**（写后逐字节自检）；
  * 章节数**不变**（仍是 +1 相对 HEAD 之前的状态）；
  * **绝不碰** `status/app/CORRECTIONS_APP.md`。
"""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BODY = os.path.join(HERE, '_sec119_body.md')

SEC = '§119'


def read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    nl = '\r\n' if b'\r\n' in raw else '\n'
    return raw.decode('utf-8'), nl


def main():
    text, nl = read_text(STATUS)

    # ── 1. 备份 ──
    bak = os.path.join(tempfile.gettempdir(),
                       'STATUS_APP_before_sec119_repl_%d.md' % os.getpid())
    shutil.copy2(STATUS, bak)
    print('[bak] %s' % bak)

    # ── 2. 定位 §119 章节起点（**必须唯一命中**）──
    hits = list(re.finditer(r'(?m)^### %s\b' % re.escape(SEC), text))
    assert len(hits) == 1, '§%s 章节锚点命中 %d 次（应为 1）' % (SEC, len(hits))
    i_sec = hits[0].start()

    prefix = text[:i_sec]           # §109…§118 ＋ 头部 ⇒ **一字不动**
    old_sec = text[i_sec:]

    # ── 3. 组装新章节（用 `_sec119_body.md`）──
    with open(BODY, 'r', encoding='utf-8') as f:
        new_body = f.read().rstrip('\n')
    assert new_body.startswith('### %s' % SEC), '正文文件首行不是 §%s' % SEC

    out = prefix.rstrip('\n') + '\n\n' + new_body + '\n'

    # ── 4. 写回（保持原换行风格）──
    with open(STATUS, 'wb') as f:
        f.write(out.replace('\n', nl).encode('utf-8'))

    # ── 5. 自检 ──
    check, _ = read_text(STATUS)
    # ① 前缀（头部 ＋ §109…§118）**逐字未变**
    assert prefix.rstrip('\n') in check, '§%s 之前的正文被改动！' % SEC
    # ② §119 之前的部分与写入前**完全一致**
    i_new = list(re.finditer(r'(?m)^### %s\b' % re.escape(SEC), check))
    assert len(i_new) == 1, '写后 §%s 锚点命中 %d 次' % (SEC, len(i_new))
    assert check[:i_new[0].start()].rstrip('\n') == prefix.rstrip('\n'), \
        '§%s 之前的内容与写入前不一致' % SEC
    # ③ 章节数不变
    n_before = len(re.findall(r'(?m)^### §', text))
    n_after = len(re.findall(r'(?m)^### §', check))
    assert n_after == n_before, '章节数 %d ⇒ %d（应不变）' % (n_before, n_after)
    # ④ 旧 §119 内容**确实**被换掉了（且是新内容）
    assert old_sec.rstrip('\n') not in check, '旧 §%s 内容仍在（新旧同文？）' % SEC
    for must in ('#### 5.5', '#### 5.6', 'app188'):
        assert must in check, '新 §%s 内容缺少 %r' % (SEC, must)
    # ⑤ 头部字段各 1 次
    for k in ('last_ack', '更新时间'):
        c = len(re.findall(r'(?m)^%s:' % re.escape(k), check))
        assert c == 1, '头部字段 %r 出现 %d 次' % (k, c)
    print('[ok] §%s 已定点替换；§109…§118 与头部逐字未变；章节数 %d ⇒ %d；字节 %d'
          % (SEC, n_before, n_after, len(check.encode('utf-8'))))


if __name__ == '__main__':
    sys.exit(main())
