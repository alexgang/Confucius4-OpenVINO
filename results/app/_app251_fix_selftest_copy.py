#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_fix_selftest_copy.py —— §251：修 app049 闸门**自检脚本的磁盘炸弹**。

🔴 **事故（§251 本轮实测）**
   `results/app/app049_gate_selftest.py` 用 `shutil.copytree` 整树复制
   `results/app` + `live_caption` 到临时目录。
   🔴 `copytree` **会跟随 Windows junction**（`os.walk` 不跟随，但 copytree 跟随）
   ⇒ `results/app/app526_app107_rc11_acceptance/iso_localappdata/Confucius4LiveCaption/`
   下的 **16 个 junction** 全部被**展开成真实副本**
   （指向 `C:\\Users\\Trekker-PTL\\AppData\\Local\\Confucius4LiveCaption\\*` 的真实缓存）
   ⇒ 实测复制出 **160 GB** ⇒ 把 C: 盘写满到 **100%（仅剩 2.1 G）**
   ⇒ 脚本随后以 `WinError 112 磁盘空间不足` 崩溃 ⇒ **自检永远跑不完**
   ⇒ 留下 160 GB 临时垃圾（已在本轮清理，C: 恢复到 146 G 可用）。

🔴 **修法（最小、最保守）**：**只复制 `*.py`**
   * 闸门**只判 `.py` 文件**（`if not fn.endswith('.py'): continue`）
     ⇒ 只复制 `.py` **不改变闸门行为**；
   * 副本从 160 GB 降到 **几 MB**（实测 1 585 个 `.py`）；
   * **不再跟随 junction** ⇒ 不会撑爆磁盘、不会碰 AppData 的真实缓存。

🔴 **为什么不用 `ignore_patterns` 排除那几个 junction 目录**
   ⇒ junction 目录名会变、也可能新增 ⇒ 「按名字排除」是**易腐的清单**；
   ⇒ 而「只复制 `.py`」是**按闸门自己的判定范围**收窄 ⇒ **结构性正确**、不会腐。

纪律：写前备份 → 写后在内存跑**真不变量** → 临时文件 → `os.replace` 原子落盘。
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'app049_gate_selftest.py')

#: 旧实现（整树 copytree ⇒ 跟随 junction ⇒ 160 GB）
OLD = """        # 只复制闸门扫描需要的两个根（省时间）
        for rel in ('results/app', 'live_caption'):
            src = os.path.join(REPO, rel.replace('/', os.sep))
            dst = os.path.join(tmp, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copytree(src, dst, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__'))
"""

#: 新实现（只复制 .py ⇒ 不跟随 junction ⇒ 副本几 MB）
NEW = """        # 🔴 §251：**只复制 `*.py`**（不整树 copytree）。
        #   原因：`shutil.copytree` **会跟随 Windows junction** ⇒
        #   `results/app/**/iso_localappdata/Confucius4LiveCaption/` 下的
        #   16 个 junction 会被展开成真实副本 ⇒ 实测 **160 GB** ⇒ C: 盘写满到
        #   100% ⇒ 自检以 `WinError 112 磁盘空间不足` 崩溃 ⇒ 自检永远跑不完。
        #   🔴 闸门**只判 `.py` 文件** ⇒ 只复制 `.py` **不改变闸门行为**。
        for rel in ('results/app', 'live_caption'):
            src = os.path.join(REPO, rel.replace('/', os.sep))
            dst = os.path.join(tmp, rel.replace('/', os.sep))
            os.makedirs(dst, exist_ok=True)
            for dirpath, dirnames, filenames in os.walk(src):
                dirnames[:] = [d for d in dirnames
                               if d not in ('__pycache__', '.git')]
                rel_dir = os.path.relpath(dirpath, src)
                out_dir = (dst if rel_dir == '.'
                           else os.path.join(dst, rel_dir))
                for fn in filenames:
                    if not fn.endswith('.py'):
                        continue
                    os.makedirs(out_dir, exist_ok=True)
                    shutil.copy2(os.path.join(dirpath, fn),
                                 os.path.join(out_dir, fn))
"""


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

    # ── 锚点唯一命中断言（用实际行尾构造 ⇒ CRLF/LF 都不踩坑）──
    old_block = OLD.replace('\n', nl)
    if text.count(old_block) != 1:
        print('!! 旧实现块命中 %d 次（须恰好 1 次）⇒ 零改动'
              % text.count(old_block))
        return 1

    new_block = NEW.replace('\n', nl)
    new_text = text.replace(old_block, new_block, 1)

    # ── 写前真不变量 ──
    errs = []
    # ① 既有正文逐字未变（去掉替换块后必须与原文完全相同）
    if new_text.replace(new_block, '', 1) != text.replace(old_block, '', 1):
        errs.append('既有正文被改动')
    # ② 替换块只出现一次
    if new_text.count(new_block) != 1:
        errs.append('新块命中 %d 次（须 1 次）' % new_text.count(new_block))
    # ③ 旧的危险调用必须**已消失**（只查**可执行代码行**⇒ docstring 里对
    #    copytree 的**引述**不算；用 ast 判定 ⇒ 精确排除注释与文档字符串）
    import ast
    try:
        tree = ast.parse(new_text)
    except SyntaxError as e:
        errs.append('新文本语法错误：%r' % e)
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if (isinstance(f, ast.Attribute) and f.attr == 'copytree'):
                    errs.append('可执行代码里仍有 shutil.copytree 调用'
                                '（磁盘炸弹未除）')
    # ④ 必须仍只判 .py（不能改闸门的判定范围）
    if "if not fn.endswith('.py'):" not in new_text:
        errs.append('.py 过滤条件缺失')
    # ⑤ 反证：必须**没有**引入 junction 跟随（shutil.copy2 逐文件 + os.walk 不跟随）
    if 'os.symlink' in new_text or 'os.link' in new_text:
        errs.append('引入了链接跟随风险')
    if errs:
        print('!! 写前真不变量未过 ⇒ 零改动：')
        for e in errs:
            print('   - %s' % e)
        return 1
    print('写前真不变量：%d 项全 PASS' % 5)

    # ── 原子落盘 ──
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
    import ast as _ast
    try:
        _tree = _ast.parse(after.decode('utf-8'))
    except SyntaxError:
        print('!! 写后语法错误')
        return 1
    for _n in _ast.walk(_tree):
        if isinstance(_n, _ast.Call) and isinstance(_n.func, _ast.Attribute)                 and _n.func.attr == 'copytree':
            print('!! 磁盘炸弹调用仍在')
            return 1
    print('写后复核：行尾风格不变 / copytree 已消除 ⇒ PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
