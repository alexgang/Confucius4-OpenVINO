#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · `sync_c172` 两处修复的**端到端**复核（用**影子包**，绝不碰真包）。

## 🔴 判据的关键区分（本脚本第一版就踩了这个坑）
`sync_c172` 的插入条件是「**该版本段尚不存在**」⇒
- **已插入过的版本**（如真包 v2.6 已有的段）⇒ 脚本**跳过**（幂等守卫），
  **不会**去「修」已存在的重复标题（章节正文由人撰写 ⇒ 脚本不改正文）。
- **尚未插入的版本** ⇒ 脚本**插入新段** ⇒ 这才是**缺陷产生的那一刻**。

⇒ 所以要验证「修复有效」，必须模拟**插入前**的状态（v2.6 段还不存在），
用**真实的人撰写正文文件**（`live_caption/_app129_changelog_2.6_{zh,en}.md`，
它们的首行**自带**标题 ⇒ 正是缺陷的来源）跑一遍 ⇒ 结果应只有**一个**标题。

## 🔴 影子包：真包只读
真包 `Confucius4_LiveCaption_v2.6` 已签 ACCEPTED（version=2.6／
accepted_at=2026-11-24 18:26:21）⇒ 按 APP-055 **不得原地修改**。
⇒ 本脚本把真包的 README/NOTICE/MANIFEST **复制**到 `%TEMP%` 影子目录，
在**影子**上真跑 `sync_c172`；跑完再算真包 SHA256，**必须与跑前一致**。

## 判据
### A. 插入路径（缺陷产生的真实路径）
1. **MANIFEST.version**：`2.5` → `2.6`；
2. **README_zh**：`## v2.6 改动说明` 恰好 **1** 次（正文首行自带标题的情形）；
3. **README_en**：`## What's new in v2.6` 恰好 1 次，且 `## v2.6 changes` **消失**；
4. **NOTICE** 首行版本号 = 2.6；
5. 正文小节（`### 1. …`）**仍在**（没被误剥）；
6. **幂等**：再跑一次 ⇒ 全部 ALREADY、4 个文件 SHA 不变；
7. `--dry-run` ⇒ **一个字节都不写**；
8. **真包逐字节未变**（隔离有效）。

### B. 已存在版本 ⇒ 不重写（内容归人撰写）
9. 对**已含 v2.6 段**的影子包再跑 ⇒ README **不被改动**
   （脚本跳过；**不**去「修」已存在的重复标题）。

### C. 反证组
把正文的首行标题**去掉**（模拟「不带标题的正文」）⇒ 判据 2/3 仍应 PASS
（说明修复不是靠「删掉正文标题」蒙对的，而是**插入时按需剥离**）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
REAL = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.6'
SYNC = os.path.join(REPO, 'live_caption', 'sync_c172_version_identity_to_pkg.py')
CL_ZH = os.path.join(REPO, 'live_caption', '_app129_changelog_2.6_zh.md')
CL_EN = os.path.join(REPO, 'live_caption', '_app129_changelog_2.6_en.md')

n_ok = n_bad = 0


def chk(name, cond, detail=''):
    global n_ok, n_bad
    if cond:
        n_ok += 1
        print('  [PASS] %s%s' % (name, ('｜' + detail) if detail else ''))
    else:
        n_bad += 1
        print('  [FAIL] %s%s' % (name, ('｜' + detail) if detail else ''))


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def make_shadow(pre_insertion=True, cl_zh=CL_ZH, cl_en=CL_EN):
    """建影子包。

    `pre_insertion=True` ⇒ 造出**插入前**的状态：把真包里已有的
    `## v2.6 改动说明` 段**整段移除**（回到 v2.6 还没插入的样子）
    ⇒ 这样脚本会走**插入**分支 ⇒ 正是缺陷产生的路径。
    """
    root = tempfile.mkdtemp(prefix='_app233_shadow_')
    pkg = os.path.join(root, 'Confucius4_LiveCaption_v2.6')
    os.makedirs(os.path.join(pkg, 'app'))
    for fn in ('README_zh.md', 'README_en.md', 'NOTICE'):
        shutil.copy2(os.path.join(REAL, fn), os.path.join(pkg, fn))
    shutil.copy2(os.path.join(REAL, 'app', 'MANIFEST.json'),
                 os.path.join(pkg, 'app', 'MANIFEST.json'))
    if pre_insertion:
        # 移除真包里**已有的** v2.6 段（zh 与 en 各一段）
        # 🔴 用 `re.search` 找下一个段（**不能**用 `str.find` 配正则串 ——
        #    `find` 是**字面**匹配 ⇒ 找不到就返回 -1 ⇒ 会把整个文件截断，
        #    本脚本第一版就踩了这个坑 ⇒ 表现为「插入后 count=0」）。
        for fn, pat, nxt in (
                ('README_zh.md', r'^## v2\.6 改动说明\n', r'^## v2\.5 改动说明\n'),
                ('README_en.md', r"^## What's new in v2\.6\n", r"^## What's new in v2\.5\n")):
            p = os.path.join(pkg, fn)
            t = open(p, encoding='utf-8').read()
            m = re.search(pat, t, re.M)
            if not m:
                continue
            m2 = re.search(nxt, t[m.end():], re.M)
            end = (m.end() + m2.start()) if m2 else len(t)
            t = t[:m.start()] + t[end:]
            open(p, 'w', encoding='utf-8', newline='\n').write(t)
    return root, pkg


def run(pkg, extra=()):
    p = subprocess.run([sys.executable, SYNC, '--pkg', pkg] + list(extra),
                       capture_output=True, text=True, timeout=300)
    return p


def read(p):
    return open(p, encoding='utf-8').read()


def main() -> int:
    print('=== 影子包端到端复核（真包只读）===')
    files = ['README_zh.md', 'README_en.md', 'NOTICE',
             os.path.join('app', 'MANIFEST.json')]
    real_before = {f: sha(os.path.join(REAL, f)) for f in files}

    # ── A7：dry-run 不写盘 ────────────────────────────────────────
    print('\n[A] --dry-run（一个字节都不写）')
    root, pkg = make_shadow()
    try:
        before = {f: sha(os.path.join(pkg, f)) for f in files}
        p = run(pkg, ['--dry-run', '--changelog-zh', CL_ZH, '--changelog-en', CL_EN])
        chk('dry-run 退出码 0', p.returncode == 0, 'rc=%d' % p.returncode)
        after = {f: sha(os.path.join(pkg, f)) for f in files}
        chk('dry-run 后 4 个文件逐字节未变', before == after,
            str([f for f in files if before[f] != after[f]]) or '全同')

        # ── A1–A6：真跑（插入路径）────────────────────────────────
        print('\n[B] 真跑（插入前状态 ⇒ 走插入分支）')
        zh_pre = read(os.path.join(pkg, 'README_zh.md'))
        chk('准备：插入前 README_zh 无 v2.6 段',
            len(re.findall(r'^## v2\.6 改动说明\s*$', zh_pre, re.M)) == 0,
            'count=%d' % len(re.findall(r'^## v2\.6 改动说明\s*$', zh_pre, re.M)))
        p = run(pkg, ['--changelog-zh', CL_ZH, '--changelog-en', CL_EN])
        chk('退出码 0', p.returncode == 0, 'rc=%d' % p.returncode)
        if p.returncode != 0:
            print(p.stdout[-2500:])
            print(p.stderr[-1500:])

        mf = json.loads(read(os.path.join(pkg, 'app', 'MANIFEST.json')))
        chk('A1 MANIFEST.version 2.5 -> 2.6', mf.get('version') == '2.6',
            repr(mf.get('version')))

        zh = read(os.path.join(pkg, 'README_zh.md'))
        en = read(os.path.join(pkg, 'README_en.md'))
        nt = read(os.path.join(pkg, 'NOTICE'))
        n_zh = len(re.findall(r'^## v2\.6 改动说明\s*$', zh, re.M))
        n_en = len(re.findall(r"^## What's new in v2\.6\s*$", en, re.M))
        n_old = len(re.findall(r'^## v2\.6 changes\s*$', en, re.M))
        chk('A2 README_zh 的 ## v2.6 改动说明 恰好 1 次', n_zh == 1, 'count=%d' % n_zh)
        chk('A2b 无空标题段（标题后不紧跟标题）',
            not re.search(r'^## v2\.6 改动说明\s*\n\s*##', zh, re.M))
        chk('A3a README_en 的 What\'s new in v2.6 恰好 1 次', n_en == 1,
            'count=%d' % n_en)
        chk('A3b README_en 的 ## v2.6 changes 已消失', n_old == 0,
            'count=%d' % n_old)
        chk('A4 NOTICE 首行版本号 = 2.6',
            re.search(r'^Confucius4 LiveCaption v2\.6 —', nt, re.M) is not None)
        chk('A5a README_zh 正文小节仍在',
            '### 1. 保留背景音（bgkeep）进完整版' in zh)
        chk('A5b README_en 正文小节仍在',
            '### 1. Keep background audio (bgkeep) in the full edition' in en)
        # 正文内容与源文件逐字一致（去掉首行标题后）
        src_zh = read(CL_ZH).split('\n', 1)[1].strip('\n')
        got_zh = zh.split('## v2.6 改动说明\n\n', 1)[1].split('\n\n## ', 1)[0].strip('\n')
        chk('A5c README_zh 正文与源文件逐字相同（除首行标题）',
            got_zh == src_zh, '%r' % got_zh[:40])

        # ── A6：幂等 ───────────────────────────────────────────────
        print('\n[C] 幂等（再跑一次 ⇒ SHA 不变）')
        mid = {f: sha(os.path.join(pkg, f)) for f in files}
        p2 = run(pkg, ['--changelog-zh', CL_ZH, '--changelog-en', CL_EN])
        chk('第二次退出码 0', p2.returncode == 0, 'rc=%d' % p2.returncode)
        end = {f: sha(os.path.join(pkg, f)) for f in files}
        chk('4 个文件 SHA256 全部未变', mid == end,
            str([f for f in files if mid[f] != end[f]]) or '全同')

        # ── B：已存在版本 ⇒ 不重写 ─────────────────────────────────
        print('\n[D] 已含 v2.6 段的包 ⇒ 不重写（内容归人撰写）')
        root_b, pkg_b = make_shadow(pre_insertion=False)
        try:
            zh_b0 = read(os.path.join(pkg_b, 'README_zh.md'))
            before_b = {f: sha(os.path.join(pkg_b, f)) for f in files}
            p3 = run(pkg_b, ['--changelog-zh', CL_ZH, '--changelog-en', CL_EN])
            after_b = {f: sha(os.path.join(pkg_b, f)) for f in files}
            chk('退出码 0', p3.returncode == 0, 'rc=%d' % p3.returncode)
            zh_b1 = read(os.path.join(pkg_b, 'README_zh.md'))
            chk('README_zh 未被改动（脚本跳过已有版本）', zh_b0 == zh_b1)
            chk('README_zh 仍保留原有 2 个标题（脚本不重写正文）',
                len(re.findall(r'^## v2\.6 改动说明\s*$', zh_b1, re.M)) == 2,
                'count=%d' % len(re.findall(r'^## v2\.6 改动说明\s*$', zh_b1, re.M)))
            chk('但 MANIFEST.version 仍被同步（那是版本标识，不是正文）',
                json.loads(read(os.path.join(pkg_b, 'app', 'MANIFEST.json')))
                .get('version') == '2.6')
        finally:
            shutil.rmtree(root_b, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ── A8：真包隔离 ──────────────────────────────────────────────
    print('\n[E] 真包隔离（真包必须逐字节未变）')
    real_after = {f: sha(os.path.join(REAL, f)) for f in files}
    chk('真包 4 个文件 SHA256 与跑前一致', real_before == real_after,
        str([f for f in files if real_before[f] != real_after[f]]) or '全同')

    # ── C：反证组（正文不带标题 ⇒ 仍应正常插入 1 个标题）──────────
    print('\n[F] 反证组：正文**不带**标题 ⇒ 仍应恰好 1 个标题')
    cl_zh2 = os.path.join(tempfile.gettempdir(), '_app233_cl_nohead_zh.md')
    cl_en2 = os.path.join(tempfile.gettempdir(), '_app233_cl_nohead_en.md')
    with open(cl_zh2, 'w', encoding='utf-8', newline='\n') as f:
        f.write(read(CL_ZH).split('\n', 1)[1])
    with open(cl_en2, 'w', encoding='utf-8', newline='\n') as f:
        f.write(read(CL_EN).split('\n', 1)[1])
    root_c, pkg_c = make_shadow()
    try:
        p4 = run(pkg_c, ['--changelog-zh', cl_zh2, '--changelog-en', cl_en2])
        chk('退出码 0', p4.returncode == 0, 'rc=%d' % p4.returncode)
        zhc = read(os.path.join(pkg_c, 'README_zh.md'))
        enc = read(os.path.join(pkg_c, 'README_en.md'))
        chk('反证组：正文不带标题时仍是 1 个标题',
            len(re.findall(r'^## v2\.6 改动说明\s*$', zhc, re.M)) == 1,
            'count=%d' % len(re.findall(r'^## v2\.6 改动说明\s*$', zhc, re.M)))
        chk("反证组：英文也是 1 个 What's new 段",
            len(re.findall(r"^## What's new in v2\.6\s*$", enc, re.M)) == 1)
    finally:
        shutil.rmtree(root_c, ignore_errors=True)
        for p in (cl_zh2, cl_en2):
            try:
                os.remove(p)
            except OSError:
                pass

    print('\n[summary] PASS=%d FAIL=%d' % (n_ok, n_bad))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
