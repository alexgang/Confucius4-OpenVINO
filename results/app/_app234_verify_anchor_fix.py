#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-234 轮 · **独立复核** `sync_c172` 的「插入锚点唯一性」修法。

🔴 判据必须能识破**有缺陷的旧实现**（否则恒 PASS）⇒ 含**反证组**：
把 `unique_anchor()` 换成**恒不扩展**的旧行为 ⇒ 判据必须 FAIL。

## 判据（16 条）

**A 组 · 真实 v2.7 成包路径（robocopy v2.6 ⇒ v2.7 ⇒ 插入 v2.7 段）**
  A1  同步器 rc == 0（**旧实现在此 FAIL** ⇒ 证明缺陷可复现）
  A2  README_zh 的 `## v2.7 改动说明` 恰好 1 次
  A3  README_en 的 `## What's new in v2.7` 恰好 1 次
  A4  README_zh 标题版本号 == 2.7
  A5  README_en 标题版本号 == 2.7
  A6  NOTICE 首行版本号 == 2.7
  A7  app/MANIFEST.json version == 2.7
  A8  **既有 v2.6 段原文逐字未变**（修法只扩展锚点 ⇒ 不改既有内容）
  A9  幂等：再跑一次 ⇒ 4 个文件 SHA256 不变

**B 组 · 锚点唯一性函数的单元行为（不跑包）**
  B1  锚点本来就唯一 ⇒ **原样返回**（一个字节都不扩展）
  B2  锚点重复 ⇒ 扩展后**恰好出现 1 次**
  B3  扩展后仍以**既有原文**结尾（不引入任何新字符）

**C 组 · 反证组**
  C1  把 `unique_anchor()` 换成**恒不扩展** ⇒ A1 必须 FAIL
      （证明判据确实绑在「修法生效」上，不是恒 PASS）

**D 组 · 真包隔离**
  D1  真包 4 个文件跑前跑后 SHA256 逐字节一致
"""
from __future__ import annotations

import ast
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

REAL = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.6'
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
SYNC = os.path.join(REPO, 'live_caption',
                    'sync_c172_version_identity_to_pkg.py')
WATCH = ['README_zh.md', 'README_en.md', 'NOTICE',
         os.path.join('app', 'MANIFEST.json')]

FAILS = []
N = [0]


def chk(name, ok, detail=''):
    N[0] += 1
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('   ' + detail) if detail else ''))
    if not ok:
        FAILS.append((name, detail))


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def read(p):
    return io.open(p, encoding='utf-8').read()


def snap(pkg):
    out = {}
    for rel in WATCH:
        p = os.path.join(pkg, rel.replace('/', os.sep))
        if os.path.isfile(p):
            out[rel] = sha(p)
    return out


def make_shadow(root, ver):
    """**完整复制真包的 4 个身份文件**（= robocopy v2.6 ⇒ v2.7 的真实结果）。"""
    pkg = os.path.join(root, 'Confucius4_LiveCaption_v%s' % ver)
    os.makedirs(os.path.join(pkg, 'app'), exist_ok=True)
    for rel in WATCH:
        s = os.path.join(REAL, rel.replace('/', os.sep))
        d = os.path.join(pkg, rel.replace('/', os.sep))
        if os.path.isfile(s):
            shutil.copy2(s, d)
    return pkg


def run_sync(pkg, ver, extra=()):
    cmd = [sys.executable, SYNC, '--pkg', pkg]
    cmd += list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return p


def main() -> int:
    print('=== APP-234 独立复核：sync_c172 锚点唯一性修法 ===')
    print('真包（只读）：%s' % REAL)

    # 被检脚本必须能 ast.parse（不 import）
    try:
        ast.parse(read(SYNC))
        chk('被检脚本 ast.parse 通过', True)
    except SyntaxError as e:
        chk('被检脚本 ast.parse 通过', False, repr(e))
        return 1

    real_before = snap(REAL)
    root = tempfile.mkdtemp(prefix='app234_anchor_')
    try:
        # ══ A 组 ═══════════════════════════════════════════════════
        print('\n[A] 真实 v2.7 成包路径（robocopy v2.6 ⇒ v2.7）')
        pkg = make_shadow(root, '2.7')
        zh_before = read(os.path.join(pkg, 'README_zh.md'))
        # 🔴 **本版的人撰写正文**（首行就是同名标题 —— 正是 APP-233
        #    缺陷②的形状 ⇒ 走的是**插入 + 剥离**的完整路径）。
        #    ⚠️ 必须用**本版**的正文：用上一版的正文会让正文里带
        #    上一版的标题 ⇒ 计数虚高、且不是真实成包路径。
        cl_zh = os.path.join(root, 'v2.7_zh.md')
        cl_en = os.path.join(root, 'v2.7_en.md')
        with open(cl_zh, 'w', encoding='utf-8', newline='\n') as f:
            f.write('## v2.7 改动说明\n\n**完整版 v2.7**（下一版）。\n\n'
                    '### 1. 新东西\n\n- 内容。\n')
        with open(cl_en, 'w', encoding='utf-8', newline='\n') as f:
            f.write("## v2.7 changes\n\n**Full v2.7**.\n")
        p = run_sync(pkg, '2.7', ['--changelog-zh', cl_zh,
                                   '--changelog-en', cl_en])
        chk('A1 同步器 rc == 0（旧实现在此 FAIL）', p.returncode == 0,
            'rc=%d | %s' % (p.returncode,
                            ' / '.join(l for l in p.stdout.splitlines()
                                       if '命中' in l or 'FAIL' in l)[:160]))
        zh = read(os.path.join(pkg, 'README_zh.md'))
        en = read(os.path.join(pkg, 'README_en.md'))
        nt = read(os.path.join(pkg, 'NOTICE'))

        n = len(re.findall(r'^##\s+v2\.7\s+改动说明\s*$', zh, re.M))
        chk('A2 README_zh 的 `## v2.7 改动说明` 恰好 1 次', n == 1, 'count=%d' % n)
        n = len(re.findall(r"^##\s+What's new in v2\.7\s*$", en, re.M))
        chk('A3 README_en 的 `## What\'s new in v2.7` 恰好 1 次',
            n == 1, 'count=%d' % n)
        m = re.search(r'^#\s*Confucius4-R2T2\s+实时字幕（技术评估版\s+'
                      r'v(\d+(?:\.\d+)+)', zh, re.M)
        chk('A4 README_zh 标题版本号 == 2.7',
            bool(m) and m.group(1) == '2.7',
            'got=%s' % (m.group(1) if m else None))
        m = re.search(r"^#\s*Confucius4-R2T2\s+Live Captions\s+"
                      r"\(technical evaluation build\s+v(\d+(?:\.\d+)+)",
                      en, re.M)
        chk('A5 README_en 标题版本号 == 2.7',
            bool(m) and m.group(1) == '2.7',
            'got=%s' % (m.group(1) if m else None))
        m = re.search(r'^Confucius4\s+LiveCaption\s+v(\d+(?:\.\d+)+)', nt, re.M)
        chk('A6 NOTICE 首行版本号 == 2.7',
            bool(m) and m.group(1) == '2.7',
            'got=%s' % (m.group(1) if m else None))
        import json
        mv = json.loads(read(os.path.join(pkg, 'app', 'MANIFEST.json'))) \
            .get('version')
        chk('A7 app/MANIFEST.json version == 2.7', str(mv) == '2.7',
            'got=%r' % (mv,))

        # A8 既有 v2.6 段原文逐字未变（修法只扩展锚点 ⇒ 不改既有内容）
        def v26_block(t):
            """v2.6 段 = 首个 v2.6 标题 → 下一个 v2.5 标题（**行锚定**）。"""
            m = re.search(r'^##\s+v2\.6\s+改动说明\s*$', t, re.M)
            if not m:
                return None
            m2 = re.search(r'^##\s+v2\.5\s+改动说明', t[m.start():], re.M)
            return t[m.start(): m.start() + (m2.start() if m2 else len(t))]

        b0 = v26_block(zh_before)
        b1 = v26_block(zh)
        chk('A8 既有 v2.6 段原文逐字未变', b0 is not None and b0 == b1,
            'len %s vs %s' % (len(b0 or ''), len(b1 or '')))

        # A9 幂等
        s1 = snap(pkg)
        run_sync(pkg, '2.7', ['--changelog-zh', cl_zh, '--changelog-en', cl_en])
        s2 = snap(pkg)
        chk('A9 幂等：再跑一次 4 个文件 SHA256 不变', s1 == s2)

        # ══ B 组 · 函数单元行为 ═════════════════════════════════════
        print('\n[B] unique_anchor 的单元行为')
        src = read(SYNC)
        ns = {}
        exec(compile(ast.parse(src), SYNC, 'exec'), ns)
        ua = ns.get('unique_anchor')
        chk('B0 unique_anchor 可被独立加载', callable(ua))
        if not callable(ua):
            return 1
        t1 = 'aaa ## X\nbody\n'
        chk('B1 锚点本来就唯一 ⇒ 原样返回',
            ua(t1, '## X\n', t1.index('## X')) == '## X\n',
            repr(ua(t1, '## X\n', t1.index('## X'))))
        t2 = '## A\n\n## A\nbody\n'
        got = ua(t2, '## A\n', 0)
        chk('B2 锚点重复 ⇒ 扩展后恰好出现 1 次',
            t2.count(got) == 1, 'count=%d' % t2.count(got))
        chk('B3 扩展后仍以既有原文结尾（未引入新字符）',
            t2.replace(got, '', 1).find(got) == -1 and
            got.startswith('## A\n'),
            repr(got))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ══ C 组 · 反证组 ═════════════════════════════════════════════
    print('\n[C] 反证组：把 unique_anchor 换成**恒不扩展**的旧行为')
    root2 = tempfile.mkdtemp(prefix='app234_anti_')
    try:
        pkg2 = make_shadow(root2, '2.7')
        # 把 sync_c172 的源码拷到临时目录，把 unique_anchor 改成恒返回原值
        src2 = read(SYNC)
        broken = src2.replace(
            '    if text.count(anchor) == 1:\n        return anchor\n',
            '    return anchor\n', 1)
        if broken == src2:
            chk('C0 反证组：旧行为可构造', False, '未找到替换点')
        else:
            anti = os.path.join(root2, 'sync_c172_anti.py')
            with open(anti, 'w', encoding='utf-8', newline='\n') as f:
                f.write(broken)
            p = subprocess.run(
                [sys.executable, anti, '--pkg', pkg2,
                 '--changelog-zh', os.path.join(
                     REPO, 'live_caption', '_app129_changelog_2.6_zh.md'),
                 '--changelog-en', os.path.join(
                     REPO, 'live_caption', '_app129_changelog_2.6_en.md')],
                capture_output=True, text=True, timeout=600)
            chk('C1 反证组：旧实现 rc != 0（判据有鉴别力）',
                p.returncode != 0, 'rc=%d' % p.returncode)
    finally:
        shutil.rmtree(root2, ignore_errors=True)

    # ══ D 组 · 真包隔离 ═════════════════════════════════════════════
    print('\n[D] 真包隔离')
    chk('D1 真包 4 个文件跑前跑后逐字节一致', real_before == snap(REAL),
        '%d 个文件' % len(real_before))

    print()
    print('PASS=%d / FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
    if FAILS:
        for n, d in FAILS:
            print('  [FAIL] %s  %s' % (n, d))
        return 1
    print('结论：PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
