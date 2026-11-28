#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_fix_internal_material_font.py —— §251：修内部素材闸门的**字体二进制误报**。

🔴 **缺陷（§251 实测，`pack_v13.py` 的第 2 道打包前置闸门）**
   `check_internal_material.py` 用**文本正则**去扫**二进制字体**（`.woff2`）的
   压缩字节 ⇒ 随机字节序列会**偶然**命中「会议特征串」正则
   （实测 `IBMPlexMono-Bold.woff2` 在 byte 16208 处出现 `qgS`，命中
   `\bQ[G]S\b` ⇒ 报「会议特征串」）。
   ⇒ **闸门 FAIL ⇒ 拒绝打包** ⇒ v2.7 打不出来。

🔴 **这是真·误报，不是真缺陷**
   * 命中处是**压缩字体的随机字节**，不是会议内容
     （上下文全是二进制噪声：`b'o\\x07uW\\xa3VA\\x8b4q)|>...'`）；
   * v2.6 的 150 个字体里**只有 1 个**偶然命中 ⇒ 是概率事件，不是系统性内容泄漏。

🔴 **修法（最小、只收窄误报面，不削弱真实检测）**
   把**字体扩展名**加进既有的 `SKIP_CONTENT_EXT`
   （那本来就是「明确要扫的二进制扩展名（只查文件名，不读内容）」集合）
   ⇒ 字体**仍然查文件名**（`NAME_PATTERNS` 不受影响）
   ⇒ 只是**不把压缩字节当文本扫**。

🔴 **为什么不改「文本正则」本身**
   ⇒ 那些正则（会议代号/音频编号/规格/人名）是**内部素材检测的本体**
   ⇒ 收窄它们＝削弱真实检测 ⇒ 不做。

🔴 **反证组（必须跑）**
   ① 真正的会议特征串放进**一个 .txt** ⇒ 闸门**仍必须 FAIL**（真检测没被削弱）；
   ② 真正的 U+FFFD 乱码放进**一个 .js** ⇒ 闸门**仍必须 FAIL**（乱码检测没被削弱）；
   ③ 字体文件里的偶然字节命中 ⇒ 闸门**必须 PASS**（误报消除）；
   ④ 「文件名规则」对字体**仍然生效**（`NAME_PATTERNS` 未被绕过）。

纪律：写前备份 → 写后在内存跑**真不变量** → 临时文件 → `os.replace` 原子落盘。
"""
from __future__ import annotations

import ast
import hashlib
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(REPO, 'check_internal_material.py')

#: 旧集合（无字体扩展名）
OLD = """SKIP_CONTENT_EXT = {
    '.xml', '.bin', '.npy', '.wav', '.mp3', '.flac', '.ogg', '.pcm',
    '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.gz', '.pyc',
    '.onnx', '.blob', '.m4a', '.aac',
}"""

#: 新集合（加字体二进制）
NEW = """SKIP_CONTENT_EXT = {
    '.xml', '.bin', '.npy', '.wav', '.mp3', '.flac', '.ogg', '.pcm',
    '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.gz', '.pyc',
    '.onnx', '.blob', '.m4a', '.aac',
    # 🔴 §251 修正：**字体是压缩二进制**，用文本正则扫它会**偶然命中**
    #   （实测 `IBMPlexMono-Bold.woff2` 的随机字节出现 `qgS` ⇒ 命中
    #   `\bQ[G]S\b` ⇒ 报「会议特征串」⇒ 闸门 FAIL ⇒ **拒绝打包**）。
    #   ⇒ 字体**仍然查文件名**（NAME_PATTERNS 不变），
    #     只是**不把压缩字节当文本扫**（与其它二进制扩展名同口径）。
    '.woff', '.woff2', '.ttf', '.otf', '.eot', '.fon',
}"""


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    if not os.path.isfile(TARGET):
        print('!! 找不到 %s' % TARGET)
        return 2

    raw = open(TARGET, 'rb').read()
    orig_sha = sha256(raw)
    orig_lines = raw.count(b'\n')
    orig_crlf = raw.count(b'\r\n')
    print('写前：bytes=%d sha256=%s lines=%d crlf=%d'
          % (len(raw), orig_sha[:16], orig_lines, orig_crlf))

    bak = TARGET + '.bak_app251'
    shutil.copy2(TARGET, bak)
    print('备份 → %s' % bak)

    text = raw.decode('utf-8')
    nl = '\r\n' if (orig_crlf and orig_crlf == orig_lines) else '\n'

    old_block = OLD.replace('\n', nl)
    if text.count(old_block) != 1:
        print('!! 锚点命中 %d 次（须恰好 1 次）⇒ 零改动' % text.count(old_block))
        return 1

    new_block = NEW.replace('\n', nl)
    new_text = text.replace(old_block, new_block, 1)

    # ── 写前真不变量 ──
    errs = []
    # ① 既有正文逐字未变（去掉替换块 ⇒ 与原文相同）
    if new_text.replace(new_block, '', 1) != text.replace(old_block, '', 1):
        errs.append('既有正文被改动')
    # ② 文本正则集合**必须一字未动**（真检测没被削弱）
    for pat in (r"\bQ[G]S\b", r"26[0]902", r"b[l]c\s*b[0]", r"5[2]\s*c[o]re",
                r"L[i]sa will join"):
        if new_text.count(pat) != text.count(pat):
            errs.append('文本正则被改动：%r' % pat)
    # ③ NAME_PATTERNS（文件名规则）**必须一字未动**
    n_before = text[text.index('NAME_PATTERNS = ['):text.index('NAME_PATTERNS = [') + 2000]
    n_after = new_text[new_text.index('NAME_PATTERNS = ['):new_text.index('NAME_PATTERNS = [') + 2000]
    if n_before != n_after:
        errs.append('NAME_PATTERNS（文件名规则）被改动')
    # ④ 新集合必须包含全部字体扩展名
    for ext in ('.woff', '.woff2', '.ttf', '.otf', '.eot'):
        if "'%s'" % ext not in new_block:
            errs.append('新集合缺扩展名 %s' % ext)
    # ⑤ 语法可解析
    try:
        ast.parse(new_text)
    except SyntaxError as e:
        errs.append('新文本语法错误：%r' % e)
    if errs:
        print('!! 写前真不变量未过 ⇒ 零改动：')
        for e in errs:
            print('   - %s' % e)
        return 1
    print('写前真不变量：%d 项全 PASS' % 5)

    tmp = TARGET + '.tmp_app251'
    with io.open(tmp, 'wb') as f:
        f.write(new_text.encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, TARGET)

    after = open(TARGET, 'rb').read()
    print('写后：bytes=%d sha256=%s lines=%d crlf=%d'
          % (len(after), sha256(after)[:16], after.count(b'\n'),
             after.count(b'\r\n')))
    if (after.count(b'\r\n') != after.count(b'\n')) != (orig_crlf != orig_lines):
        print('!! 行尾风格变了 ⇒ 需人工介入')
        return 1
    if sha256(after) == orig_sha:
        print('!! 内容未变 ⇒ 异常')
        return 1
    print('写后复核：行尾风格不变 / 内容已变 ⇒ PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
