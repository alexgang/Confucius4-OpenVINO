#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app578 —— 把 `_app573_write_status_sec208.py` 改成「**活文档速查从 companion 读**」。

🔴 **为什么**：§208 的活文档正文曾被硬编码在写手脚本里 ⇒ 改一次正文要改两处
   （易漂移），且撞过「压紧脚本把 `r'''` 开引号一起替换掉」的坑。
   ⇒ 改成：**companion 文件是唯一事实来源**（含「速查段」＋「完整正文段」两个标记），
   写手脚本**按标记切分**⇒ 改正文只改 companion 一处。

🔴 **纪律**：全部用**行号/正则**定位，不依赖长字符串精确匹配；
   反斜杠一律用 `chr(92)` 构造（🔴 heredoc／shell 会吃掉 `\\n` ⇒ 上轮踩过）。
"""
from __future__ import annotations

import ast
import os
import re
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, '_app573_write_status_sec208.py')
BS = chr(92)


def atomic_write(path, text):
    data = text.encode('utf-8')
    ast.parse(text)
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
    os.close(fd)
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main():
    with open(TARGET, 'rb') as f:
        text = f.read().decode('utf-8')

    # ── ① 去掉硬编码的 SEC208_BODY（改由 companion 提供）──
    t2 = re.sub(r"SEC208_BODY = r'''.*?'''\n",
                 "SEC208_BODY = None  # 活文档速查**从 companion 读**（唯一事实来源）\n",
                 text, count=1, flags=re.S)
    if t2 == text:
        print('[skip] 硬编码 SEC208_BODY 未找到（可能已改过）')
    text = t2

    lines = text.split('\n')

    # ── ② 还原式复核那两行（可能已被上轮 regex 改坏）──
    for k, l in enumerate(lines):
        nxt = lines[k + 1] if k + 1 < len(lines) else ''
        if 'SEC208_TITLE + SEC208_BODY' in l and 'restored' in l:
            lines[k:k + 2] = ["    restored = restored.replace('" + BS
                              + "n' + SEC208_TITLE + SEC208_BODY, '', 1)"]
            break
        # 🔴 坏形态：`.replace('` 与下一行被换行符劈开 ⇒ 两条一起换掉
        if l.rstrip().endswith(".replace('") and 'SEC208_TITLE' in nxt:
            lines[k:k + 2] = ["    restored = restored.replace('" + BS
                              + "n' + SEC208_TITLE + SEC208_BODY, '', 1)"]
            break
    text = '\n'.join(lines)

    # ── ③ companion 解析块：改成「速查段 / 完整正文段」两个标记 ──
    lines = text.split('\n')
    i = [k for k, l in enumerate(lines) if l.strip().startswith("sep = ")]
    if len(i) == 1:
        i = i[0]
        j = [k for k, l in enumerate(lines)
             if l.strip().startswith("comp_new = ")]
        assert len(j) == 1, j
        j = j[0]
        NL = BS + 'n'
        NEW = [
            "    LIVE_MARK = ('---- 活文档速查（以下 6 行＝**唯一事实来源**；'",
            "                 'writer 按此**原样**追加到活文档）----')",
            "    FULL_MARK = ('---- 完整正文（以下逐字；**正文块 SHA256 ＝ '",
            "                 '本分隔线之后的全部内容**）----')",
            "    if LIVE_MARK not in comp_text or FULL_MARK not in comp_text:",
            "        fail('companion 缺「速查 / 完整正文」分隔标记')",
            "    head, rest = comp_text.split(LIVE_MARK, 1)",
            "    live_txt, body = rest.split(FULL_MARK, 1)",
            "    live_txt = live_txt.strip('" + NL + "')",
            "    body = body.strip('" + NL + "') + '" + NL + "'",
            "    if '<FILLED_BY_WRITER>' not in head:",
            "        fail('companion 占位符缺失')",
            "    body_sha = sha(body.encode('utf-8'))",
            "    body_bytes = len(body.encode('utf-8'))",
            "    head = head.replace('<FILLED_BY_WRITER>', '%s（%d B）'",
            "                      % (body_sha, body_bytes))",
            "    comp_new = (head + LIVE_MARK + live_txt + '" + NL + "' + FULL_MARK",
            "                + body).encode('utf-8')",
            "    # 速查行：把 {cbytes} / {csha} 占位符**就地**填上（不用 .format",
            "    # ⇒ 正文里的花括号不会炸）",
            "    SEC208_BODY = (live_txt.replace('{cbytes}', str(body_bytes))",
            "                   .replace('{csha}', body_sha) + '" + NL + "')",
            "    print('[pre] 速查 %d B｜完整正文 %d B'",
            "          % (len(SEC208_BODY.encode('utf-8')), body_bytes))",
        ]
        lines = lines[:i] + NEW + lines[j + 1:]
        text = '\n'.join(lines)
        print('[ok] companion 解析块已换成「速查 / 完整正文」两标记')

    # ── ④ 追加段 + 还原式复核里的 `.format(...)` 调用 ──
    text = re.sub(r"SEC208_BODY\.format\(cbytes=body_bytes,\s*csha=body_sha\)",
                  "SEC208_BODY", text)
    print('[ok] `.format(...)` 调用已去除')

    atomic_write(TARGET, text)
    print('[ok] 已写入｜文件 %d B' % len(text.encode('utf-8')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
