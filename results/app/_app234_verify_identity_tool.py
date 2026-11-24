#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-234 轮 · **行为级**复核 `live_caption/sync_pkg_identity.py`。

🔴 纪律：验收脚本**不 import** 被检脚本 ⇒ 用 `ast` + `exec` 独立跑；
🔴 真包（`Confucius4_LiveCaption_v2.6`）**只读** ⇒ 一切写操作在
`%TEMP%` 的**影子包**上做；跑完逐字节核对真包 4 个文件未变。

## 判据（12 条）

**A 组 · 影子包（把 v2.6 复制到 %TEMP% 并改名 ⇒ 目标版本 v2.7）**
  A1  真跑：README_zh 标题版本号 2.6 → **2.7**
  A2  真跑：README_en 标题版本号 2.6 → **2.7**
  A3  真跑：NOTICE 首行版本号 2.6 → **2.7**
  A4  真跑：`app/MANIFEST.json` 的 version 2.5 → **2.7**
  A5  真跑：README_zh 的 `## v2.7 改动说明` **恰好 1 次**
  A6  真跑：README_en 的 `## What's new in v2.7` **恰好 1 次**
  A7  `--dry-run` ⇒ **一个字节都不写**
  A8  **幂等**：再跑一次 ⇒ 4 个文件 SHA256 不变
  A9  **反证组**：把「改动说明」正文改成**不带标题**⇒ 标题仍恰好 1 次
      （证明不是靠正文自带的标题凑出来的）

**B 组 · 安全护栏**
  B1  对「已签 ACCEPTED 且 version == 目标版本」的包 ⇒ **拒绝改写**
      （rc=3，文件逐字节未变）⇒ APP-055
  B2  对「ACCEPTED.json 的 version 是**上一版**」的包（升版场景）⇒ **放行**
      ⇒ 证明护栏不会误伤正常的升版流程

**C 组 · 真包隔离**
  C1  真包 4 个文件（README_zh / README_en / NOTICE / app/MANIFEST.json）
      跑前跑后 SHA256 **逐字节一致**
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REAL = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.6'
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
TOOL = os.path.join(REPO, 'live_caption', 'sync_pkg_identity.py')
SYNC_C172 = os.path.join(REPO, 'live_caption',
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


def snap(pkg):
    out = {}
    for rel in WATCH:
        p = os.path.join(pkg, rel.replace('/', os.sep))
        if os.path.isfile(p):
            out[rel] = sha(p)
    return out


def run_tool(pkg, extra=()):
    cmd = [sys.executable, TOOL, '--pkg', pkg] + list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return p.returncode, p.stdout, p.stderr


def read(p):
    return open(p, 'rb').read().decode('utf-8')


def make_shadow(dst, ver):
    """复制真包的 4 个身份文件到影子目录（目录名 ⇒ 目标版本）。"""
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.join(dst, 'app'), exist_ok=True)
    for rel in WATCH:
        s = os.path.join(REAL, rel.replace('/', os.sep))
        d = os.path.join(dst, rel.replace('/', os.sep))
        if os.path.isfile(s):
            shutil.copy2(s, d)
    return dst


def main() -> int:
    print('=== APP-234 行为级复核：sync_pkg_identity（影子包，真包只读）===')
    print('真包（只读）：%s' % REAL)

    # ── 被检脚本必须能 ast.parse（不 import）──────────────────────
    try:
        ast.parse(read(TOOL))
        chk('被检脚本 ast.parse 通过', True)
    except SyntaxError as e:
        chk('被检脚本 ast.parse 通过', False, repr(e))
        return 1

    real_before = snap(REAL)

    tmp = tempfile.mkdtemp(prefix='app234_id_')
    try:
        # ══ A 组 ═══════════════════════════════════════════════════
        print('\n[A] 影子包（v2.6 内容 ⇒ 目标 v2.7）')
        pkg = make_shadow(os.path.join(
            tmp, 'Confucius4_LiveCaption_v2.7'), '2.7')
        # 改动说明正文：沿用真实的人撰写正文（**首行就是同名标题**
        # ⇒ 这正是 v2.6 双标题的根因 ⇒ 修好之后应恰好 1 次）
        cl_zh = os.path.join(REPO, 'live_caption',
                             '_app129_changelog_2.6_zh.md')
        cl_en = os.path.join(REPO, 'live_caption',
                             '_app129_changelog_2.6_en.md')
        chk('人撰写的改动说明正文存在（入库件）',
            os.path.isfile(cl_zh) and os.path.isfile(cl_en))

        # A7 dry-run：一个字节都不写
        before = snap(pkg)
        rc, out, err = run_tool(pkg, ['--dry-run',
                                      '--changelog-zh', cl_zh,
                                      '--changelog-en', cl_en])
        after = snap(pkg)
        chk('A7 --dry-run 一个字节都不写', before == after,
            'rc=%d' % rc)
        chk('A7b --dry-run 返回 0', rc == 0, 'rc=%d' % rc)

        # 真跑
        rc, out, err = run_tool(pkg, ['--changelog-zh', cl_zh,
                                      '--changelog-en', cl_en])
        print('\n--- sync_pkg_identity 关键输出 ---')
        for line in out.splitlines():
            if ('[PASS]' in line or '[FAIL]' in line
                    or '结论' in line or 'APPROVED' in line):
                print('    ' + line)
        chk('A0 真跑返回 0', rc == 0, 'rc=%d err=%s' % (rc, err[-300:]))

        zh = read(os.path.join(pkg, 'README_zh.md'))
        en = read(os.path.join(pkg, 'README_en.md'))
        nt = read(os.path.join(pkg, 'NOTICE'))
        mf = json.loads(read(os.path.join(pkg, 'app', 'MANIFEST.json')))

        # 🔴 与 sync_c172 同口径：**全角括号、且「字幕」与「（」之间无空格**
        m = re.search(r'^#\s*Confucius4-R2T2\s+实时字幕（技术评估版\s+'
                      r'v(\d+(?:\.\d+)+)', zh, re.M)
        chk('A1 README_zh 标题版本号 == 2.7',
            bool(m) and m.group(1) == '2.7',
            'got=%s' % (m.group(1) if m else None))
        m = re.search(r"^#\s*Confucius4-R2T2\s+Live Captions\s+"
                      r"\(technical evaluation build\s+v(\d+(?:\.\d+)+)",
                      en, re.M)
        chk('A2 README_en 标题版本号 == 2.7',
            bool(m) and m.group(1) == '2.7',
            'got=%s' % (m.group(1) if m else None))
        m = re.search(r'^Confucius4\s+LiveCaption\s+v(\d+(?:\.\d+)+)',
                      nt, re.M)
        chk('A3 NOTICE 首行版本号 == 2.7',
            bool(m) and m.group(1) == '2.7',
            'got=%s' % (m.group(1) if m else None))
        chk('A4 app/MANIFEST.json version == 2.7',
            str(mf.get('version')) == '2.7',
            'got=%r' % (mf.get('version'),))
        n_zh = len(re.findall(r'^##\s+v2\.7\s+改动说明\s*$', zh, re.M))
        chk('A5 README_zh 的 `## v2.7 改动说明` 恰好 1 次',
            n_zh == 1, 'count=%d' % n_zh)
        n_en = len(re.findall(r"^##\s+What's new in v2\.7\s*$", en, re.M))
        chk('A6 README_en 的 `## What\'s new in v2.7` 恰好 1 次',
            n_en == 1, 'count=%d' % n_en)

        # A8 幂等
        s1 = snap(pkg)
        rc, out2, err2 = run_tool(pkg, ['--changelog-zh', cl_zh,
                                        '--changelog-en', cl_en])
        s2 = snap(pkg)
        chk('A8 幂等：再跑一次 4 个文件 SHA256 不变',
            s1 == s2 and rc == 0, 'rc=%d' % rc)

        # A9 反证组：正文**不带**标题 ⇒ 标题仍恰好 1 次
        pkg2 = make_shadow(os.path.join(
            tmp, 'Confucius4_LiveCaption_v2.8'), '2.8')
        cl2 = os.path.join(tmp, 'cl_noheading_zh.md')
        with open(cl2, 'w', encoding='utf-8', newline='\n') as f:
            f.write('这一版**没有**自带标题（反证组）。\n\n'
                    '正文内容。\n')
        rc, out3, err3 = run_tool(pkg2, ['--changelog-zh', cl2])
        zh2 = read(os.path.join(pkg2, 'README_zh.md'))
        n_zh2 = len(re.findall(r'^##\s+v2\.8\s+改动说明\s*$', zh2, re.M))
        chk('A9 反证组：正文不带标题 ⇒ 标题仍恰好 1 次',
            n_zh2 == 1, 'count=%d rc=%d' % (n_zh2, rc))

        # ══ B 组 · 安全护栏 ═══════════════════════════════════════
        print('\n[B] 安全护栏（APP-055）')
        # B1 已签同版本 ⇒ 拒绝
        pkg3 = make_shadow(os.path.join(
            tmp, 'Confucius4_LiveCaption_v2.9'), '2.9')
        with open(os.path.join(pkg3, 'ACCEPTED.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'accepted': True, 'version': '2.9'}, f)
        before = snap(pkg3)
        rc, out4, err4 = run_tool(pkg3, ['--changelog-zh', cl_zh])
        after = snap(pkg3)
        chk('B1 已签 ACCEPTED 的同版本包 ⇒ 拒绝改写（rc=3）',
            rc == 3, 'rc=%d' % rc)
        chk('B1b 拒绝时 4 个文件逐字节未变', before == after)

        # B2 升版场景：ACCEPTED.json 是**上一版** ⇒ 放行
        pkg4 = make_shadow(os.path.join(
            tmp, 'Confucius4_LiveCaption_v2.10'), '2.10')
        with open(os.path.join(pkg4, 'ACCEPTED.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'accepted': True, 'version': '2.9'}, f)
        rc, out5, err5 = run_tool(pkg4, ['--changelog-zh', cl_zh])
        chk('B2 升版场景（ACCEPTED 是上一版）⇒ 放行（rc=0）',
            rc == 0, 'rc=%d' % rc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ══ C 组 · 真包隔离 ═══════════════════════════════════════════
    print('\n[C] 真包隔离')
    real_after = snap(REAL)
    chk('C1 真包 4 个文件跑前跑后逐字节一致',
        real_before == real_after,
        '%d 个文件' % len(real_before))
    for rel in WATCH:
        p = os.path.join(REAL, rel.replace('/', os.sep))
        if os.path.isfile(p):
            print('    %-28s %s' % (rel, sha(p)[:16]))

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
