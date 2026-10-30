#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""sync_c172_version_identity_to_pkg.py —— **通用**版「版本标识同步」到客户包。

🔴🔴🔴 要修的缺陷（**已复现**，不是推演）
------------------------------------------
`pack_v13.py` 升版时只做两件事：
  ① `os.rename` 改源目录名（`Confucius4_LiveCaption_v1.12` ⇒ `..._v1.13`，L691-702）；
  ② `refresh_manifest()` 写 `app/MANIFEST.json` 的 `version`（L395）。

⇒ **README_zh.md / README_en.md / NOTICE 三个文件的版本号一个都没动**
⇒ 而这三个文件**只存在于客户包里**（仓库里没有）⇒ **没有任何脚本会改它们**
⇒ ⇒ **每打一个新版本号，这三个文件就自动落后一版**

🔴 **实测证据**：交付 zip `Confucius4_LiveCaption_v1.12.zip`（11:20 生成）内
  `README_zh.md` 首行 =「技术评估版 **v1.6**」
  `NOTICE`    首行 =「Confucius4 LiveCaption **v1.6**」
⇒ **客户拿到的 v1.12 包自称 v1.6**（APP-007 的原始教训复发）。

🔴🔴 为什么要有「通用版」（而不是 `sync_c171`）
---------------------------------------------
`sync_c171_version_identity_to_pkg.py` 把**旧版本号 v1.6 写死**在替换块里
⇒ 只能把「自称 v1.6」修成「自称 1.12」，**再升一版就完全用不了**。

⇒ 本脚本**不写死任何版本号**：
  * 目标版本 = **包目录名解析**（`Confucius4_LiveCaption_vX.Y`）；
  * 旧版本号 = **从文件内容读**（标题行 / 首行）⇒ 任意版本都能升。

🔴🔴🔴 核心纪律：**只改「身份行」，绝不改「内容」**
-------------------------------------------------
本脚本**只重写**这三处**身份标识**：
  * `README_zh.md` L1 标题里的版本号；
  * `README_en.md` L1 标题里的版本号；
  * `NOTICE` L1 的版本号。

🔴 **绝不**重写 / 重命名「## vX.Y 改动说明」这类**章节标题**，也**绝不**改写
   章节**正文**（含「本节汇总 **v1.7 ~ v1.12**」这种范围行 —— 它**属于**
   某个具体版本的章节内容）。
   ⇒ 理由：章节内容是**人工撰写**的**某个版本**的功能说明；
     把 v1.6 的章节标题改成 v1.13 ⇒ **把 v1.6 的内容贴上 v1.13 的标签**
     ⇒ **比「版本号落后」更严重（内容失真）**。
   ⇒ 正确做法：**由人撰写新版本的改动说明段**，用 `--changelog-zh/en`
     把该段**插入**到客户包 README（脚本只做**插入**，不改正文）。

🔴 **行尾无关**：脚本**自动探测并保持原行尾**（LF / CRLF 都支持）。

🔴 **幂等**：每块带一个 `marker`（**只出现在 NEW 里**的短串）
⇒ 判幂等看 `marker in text`，**不**看「OLD 是否还在」
（追加型替换块满足 OLD ⊂ NEW ⇒ 用 OLD 判会重复插入）。
⚠️ **什么都没改 ⇒ 不写盘**（否则白改客户包的 mtime ⇒ 指纹凭空变化）。

用法
----
    python live_caption/sync_c172_version_identity_to_pkg.py --pkg <包目录>
    python live_caption/sync_c172_version_identity_to_pkg.py --pkg <包目录> --dry-run

    # 同时插入本版本的「改动说明」段（内容由人撰写）
    python live_caption/sync_c172_version_identity_to_pkg.py --pkg <包目录> \
        --changelog-zh notes/v1.13_zh.md --changelog-en notes/v1.13_en.md
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

#: 包目录名的版本号匹配（`1.12` / `1.9` / `1.10`）
_VER_RE = re.compile(r'_v(\d+(?:\.\d+)+)\s*$')

#: README_zh 标题行：`# Confucius4-R2T2 实时字幕（技术评估版 vX.Y）`
_ZH_TITLE_RE = re.compile(r'^(#\s*Confucius4-R2T2\s+实时字幕（技术评估版\s+)v(\d+(?:\.\d+)+)(）)\s*$',
                          re.M)
#: README_en 标题行
_EN_TITLE_RE = re.compile(r"^(#\s*Confucius4-R2T2\s+Live Captions\s+\(technical evaluation build\s+)v(\d+(?:\.\d+)+)(\))\s*$",
                          re.M)
#: NOTICE 首行：`Confucius4 LiveCaption vX.Y — 第三方组件归属与许可证`
_NOTICE_RE = re.compile(r'^(Confucius4 LiveCaption\s+)v(\d+(?:\.\d+)+)(\s+—\s+第三方组件归属与许可证)\s*$',
                        re.M)
#: README_zh 改动说明段标题：`## vX.Y 改动说明`
_ZH_SEC_RE = re.compile(r'^##\s+v(\d+(?:\.\d+)+)\s+改动说明\s*$', re.M)
#: README_en 改动说明段标题：`## What's new in vX.Y`
_EN_SEC_RE = re.compile(r"^##\s+What's new in v(\d+(?:\.\d+)+)\s*$", re.M)


def detect_version(pkg_dir: str) -> str:
    """从包目录名解析版本号（`..._v1.12` ⇒ `1.12`）。"""
    base = os.path.basename(os.path.normpath(pkg_dir))
    m = _VER_RE.search(base)
    if not m:
        raise SystemExit('[FAIL] 包目录名不含版本号：%s' % base)
    return m.group(1)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm(text: str) -> str:
    return text.replace('\r\n', '\n')


def _ver_tuple(v):
    try:
        return tuple(int(x) for x in v.split('.'))
    except ValueError:
        return None


def section_versions(text, rx):
    """返回该文件里所有「改动说明段」的版本号（按出现顺序）。"""
    out = []
    for m in rx.finditer(text):
        k = _ver_tuple(m.group(1))
        if k:
            out.append((k, m.group(1)))
    return out


def build_blocks(texts, ver, changelogs):
    """按**文件当前内容**派生替换块（不写死任何版本号）。

    `texts`     = {'README_zh.md': text, 'README_en.md': text, 'NOTICE': text}
    `changelogs` = {'README_zh.md': 正文 or None, 'README_en.md': 正文 or None}
    返回 (blocks, advisories)
    """
    blocks = {}
    advisories = {}

    # ── README_zh.md ──
    zh = texts['README_zh.md']
    b = []
    m = _ZH_TITLE_RE.search(zh)
    if not m:
        raise SystemExit('[FAIL] README_zh.md 找不到标题版本号（格式已变？）')
    old_ver = m.group(2)
    b.append((m.group(0),
              m.group(1) + 'v' + ver + m.group(3),
              'README_zh 标题版本号 %s -> %s' % (old_ver, ver),
              '技术评估版 v%s）' % ver))

    secs = section_versions(zh, _ZH_SEC_RE)
    zh_secs = [v for _, v in secs]
    body = changelogs.get('README_zh.md')
    if body and ver not in zh_secs:
        # 🔴 **插入**新章节：用**最新的现有章节标题**当锚点（块外上下文）
        #    ⇒ 章节按「新→旧」顺序排列 ⇒ 新章节插在**最前面**。
        if secs:
            anchor_m = None
            for mm in _ZH_SEC_RE.finditer(zh):
                anchor_m = mm          # 最后一个匹配 = 版本号最大的那个？
            # 🔴 取**版本号最大**的那一个（文件顺序未必与版本顺序一致）
            best = None
            for mm in _ZH_SEC_RE.finditer(zh):
                k = _ver_tuple(mm.group(1))
                if k and (best is None or k > best[0]):
                    best = (k, mm)
            anchor_m = best[1]
            anchor = anchor_m.group(0)
            new = ('## v%s 改动说明\n\n%s\n\n%s' % (ver, body.strip('\n'), anchor))
            b.append((anchor,
                      new,
                      'README_zh 插入 v%s 改动说明段（内容由人撰写）' % ver,
                      '## v%s 改动说明' % ver))
    blocks['README_zh.md'] = b
    advisories['README_zh.md'] = (
        [] if ver in zh_secs else
        ['README_zh.md **没有 v%s 改动说明段**（现有段：%s）'
         % (ver, '、v'.join(zh_secs) or '无')])

    # ── README_en.md ──
    en = texts['README_en.md']
    b = []
    m = _EN_TITLE_RE.search(en)
    if not m:
        raise SystemExit('[FAIL] README_en.md 找不到标题版本号（格式已变？）')
    old_ver = m.group(2)
    b.append((m.group(0),
              m.group(1) + 'v' + ver + m.group(3),
              'README_en 标题版本号 %s -> %s' % (old_ver, ver),
              'evaluation build v%s)' % ver))

    secs = section_versions(en, _EN_SEC_RE)
    en_secs = [v for _, v in secs]
    body = changelogs.get('README_en.md')
    if body and ver not in en_secs:
        best = None
        for mm in _EN_SEC_RE.finditer(en):
            k = _ver_tuple(mm.group(1))
            if k and (best is None or k > best[0]):
                best = (k, mm)
        if best:
            anchor = best[1].group(0)
            new = ("## What's new in v%s\n\n%s\n\n%s"
                   % (ver, body.strip('\n'), anchor))
            b.append((anchor,
                      new,
                      "README_en 插入 'What's new in v%s' 段（内容由人撰写）" % ver,
                      "## What's new in v%s" % ver))
    blocks['README_en.md'] = b
    advisories['README_en.md'] = (
        [] if ver in en_secs else
        ["README_en.md **has no 'What's new in v%s' section** (existing: %s)"
         % (ver, ', v'.join(en_secs) or 'none')])

    # ── NOTICE ──
    nt = texts['NOTICE']
    m = _NOTICE_RE.search(nt)
    if not m:
        raise SystemExit('[FAIL] NOTICE 首行格式已变（找不到版本号）')
    old_ver = m.group(2)
    blocks['NOTICE'] = [(
        m.group(0),
        m.group(1) + 'v' + ver + m.group(3),
        'NOTICE 首行版本号 %s -> %s' % (old_ver, ver),
        'LiveCaption v%s — 第三方组件归属与许可证' % ver),
    ]
    advisories['NOTICE'] = []

    return blocks, advisories


def apply_file(path: str, blocks, dry_run: bool):
    """对单个文件应用其全部替换块。

    每块是 `(old, new, why, marker)` 四元组。
    返回 (状态, 明细)。状态 ∈ {'APPLIED', 'ALREADY', 'FAIL'}。
    """
    raw = open(path, 'rb').read()
    had_crlf = b'\r\n' in raw
    text = norm(raw.decode('utf-8'))

    applied, already, failed = [], [], []
    for old, new, why, marker in blocks:
        # 🔴 **幂等守卫优先**：marker 已在 ⇒ 已改过 ⇒ 跳过（不重复替换）
        if marker in text:
            already.append((why, 'marker 已存在'))
            continue
        n = text.count(old)
        if n == 0:
            failed.append((why, 'OLD 不存在（文本漂移？）'))
            continue
        if n > 1:
            failed.append((why, '命中 %d 次（要求恰好 1 次）' % n))
            continue
        text = text.replace(old, new, 1)
        applied.append((why, ''))

    if failed:
        return 'FAIL', {'applied': applied, 'already': already, 'failed': failed}

    out = text.replace('\n', '\r\n') if had_crlf else text
    data = out.encode('utf-8')
    # 🔴 **什么都没改 ⇒ 不写盘**（否则白改客户包的 mtime ⇒
    #    「已交付」的指纹凭空变化 ⇒ 看起来像改过包）
    if not dry_run and applied:
        with open(path, 'wb') as f:
            f.write(data)
    return ('APPLIED' if applied else 'ALREADY'), {
        'applied': applied, 'already': already, 'failed': [],
        'bytes_before': len(raw), 'bytes_after': len(data),
        'sha256_before': sha256_bytes(raw), 'sha256_after': sha256_bytes(data),
        'crlf_preserved': had_crlf,
    }


def read_changelog(path):
    if not path:
        return None
    if not os.path.isfile(path):
        raise SystemExit('[FAIL] 改动说明文件不存在：%s' % path)
    return norm(open(path, 'rb').read().decode('utf-8'))


def main() -> int:
    ap = argparse.ArgumentParser(
        description='**通用**定点同步版本标识到客户包（不写死任何版本号）')
    ap.add_argument('--pkg', required=True, help='客户包目录（不含 .zip）')
    ap.add_argument('--changelog-zh', default=None,
                    help='本版本「改动说明」正文文件（中文）⇒ 插入到 README_zh.md')
    ap.add_argument('--changelog-en', default=None,
                    help="本版本 'What\'s new' 正文文件（英文）⇒ 插入到 README_en.md")
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    pkg = args.pkg
    if not os.path.isdir(pkg):
        print('[FAIL] 包目录不存在：%s' % pkg)
        return 2
    ver = detect_version(pkg)
    print('包目录版本号（目标）：%s' % ver)

    files = ('README_zh.md', 'README_en.md', 'NOTICE')
    texts = {}
    for fn in files:
        p = os.path.join(pkg, fn)
        if not os.path.isfile(p):
            print('[FAIL] 文件不存在：%s' % p)
            return 2
        texts[fn] = norm(open(p, 'rb').read().decode('utf-8'))

    changelogs = {
        'README_zh.md': read_changelog(args.changelog_zh),
        'README_en.md': read_changelog(args.changelog_en),
    }

    blocks, advisories = build_blocks(texts, ver, changelogs)

    rc = 0
    for fn in files:
        path = os.path.join(pkg, fn)
        status, detail = apply_file(path, blocks.get(fn, []), args.dry_run)
        print('\n[%s] %s' % (status, fn))
        for why, note in detail['applied']:
            print('  APPLIED  %s %s' % (why, note))
        for why, note in detail['already']:
            print('  ALREADY  %s %s' % (why, note))
        for why, note in detail['failed']:
            print('  FAIL     %s —— %s' % (why, note))
            rc = 1
        if status != 'FAIL':
            print('  字节 %d -> %d ；行尾 %s ；SHA256 %s -> %s'
                  % (detail['bytes_before'], detail['bytes_after'],
                     'CRLF（保持）' if detail['crlf_preserved'] else 'LF（保持）',
                     detail['sha256_before'][:16], detail['sha256_after'][:16]))
        for adv in advisories.get(fn, []):
            print('  [提醒] %s' % adv)

    print()
    print('结论：%s' % ('FAIL' if rc else ('DRY-RUN OK' if args.dry_run else 'OK')))
    if rc == 0 and not args.dry_run:
        print()
        print('⚠️ 提醒：本脚本只同步**版本标识**（标题 / NOTICE）。')
        print('   「改动说明」章节**正文由人撰写** ⇒ 脚本只负责**插入**，不改正文。')
        print('   若本版本有新功能，请用 --changelog-zh / --changelog-en 插入对应章节。')
        print('   验收：python results/app/app170_version_identity_gate.py --pkg "%s"' % pkg)
    return rc


if __name__ == '__main__':
    sys.exit(main())
