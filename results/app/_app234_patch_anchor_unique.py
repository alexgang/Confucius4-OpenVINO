#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-234 轮 · 修 `sync_c172` 的**插入锚点唯一性**（真缺陷，阻断下一版成包）。

## 缺陷（🔴 实测，阻断 v2.7）

`build_blocks()` 用**行锚定正则**挑插入锚点（`_ZH_SEC_RE` / `_EN_SEC_RE`），
而 `apply_file()` 的唯一性判据用的是 **`text.count(old)`（子串计数）**。
两者在**历史包遗留的重复标题**上不一致 ⇒ 插入直接 FAIL：

- 真包 v2.6 的 `README_zh.md` 里 `## v2.6 改动说明` **出现 2 次**
  （第 1 次是**空段**、第 2 次才是正文段 —— 这正是 APP-233 登记的缺陷②，
  真包按 APP-055 未动）；
- **真实 v2.7 成包路径**是 `robocopy v2.6 ⇒ v2.7` ⇒ v2.7 的 README
  **原样继承**这两个标题；
- 于是 v2.7 插入 `## v2.7 改动说明` 时，锚点 = `## v2.6 改动说明` ⇒
  `text.count(anchor) == 2` ⇒ **报「命中 2 次（要求恰好 1 次）」**
  ⇒ **整个身份同步失败** ⇒ v2.7 的「改动说明」段**根本插不进去**。

### 为什么 APP-233 的 23/23 复核没抓到

它的影子包是「**把整段 v2.6 内容切掉**」⇒ 锚点落在 `## v2.5 改动说明`
（该串在影子包里**唯一**）⇒ 走的是**另一条路径**。
⇒ **判据覆盖不到真实路径**（与本项目反复踩的
「修了 harness ≠ 修了产品」同型）。

## 修法（窄口径：只扩展锚点，**不改任何既有章节标题**）

`sync_c172` 的既定原则是「**绝不**重写 / 重命名「## vX.Y 改动说明」这类
章节标题」⇒ 本次**不动**既有内容：只把锚点**逐行向后扩展**到在全文中
**恰好出现 1 次**为止（扩展部分是**既有原文**，会原样保留）。

- 锚点本来就唯一 ⇒ **一个字节都不改**（幂等，零影响）；
- 锚点不唯一 ⇒ 逐行扩展（空行 → 下一个标题行）⇒ 扩展后唯一即停。

## 定点写入三件套

1. 备份 `%TEMP%/sync_c172.py.bak_app234`；
2. 写前在**内存新文本**上跑真不变量（唯一命中断言 + AST + 行尾风格不变
   + 旧正文逐字未变）+ **还原式复核**；
3. 临时文件 → `os.replace` ⇒ 写后**另起脚本**独立复核。

⚠️ 目标文件是**纯 LF**（实测 470 LF / 0 CRLF）⇒ 按 LF 写。
"""
from __future__ import annotations

import ast
import io
import os
import shutil
import sys


def find_repo():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.isdir(os.path.join(d, 'live_caption')):
            return d
        d = os.path.dirname(d)
    raise SystemExit('[FAIL] 找不到仓库根')


REPO = find_repo()
TARGET = os.path.join(REPO, 'live_caption',
                      'sync_c172_version_identity_to_pkg.py')
BACKUP = os.path.join(os.environ.get('TEMP', '/tmp'),
                      'sync_c172.py.bak_app234')


def main() -> int:
    raw0 = open(TARGET, 'rb').read()
    text0 = raw0.decode('utf-8')
    n_lf0 = text0.count('\n')
    n_crlf0 = text0.count('\r\n')
    print('写前：%d B；LF %d；CRLF %d' % (len(raw0), n_lf0, n_crlf0))
    if n_crlf0 != 0:
        print('[FAIL] 目标文件含 CRLF ⇒ 需人工确认行尾策略')
        return 2

    shutil.copy2(TARGET, BACKUP)
    print('备份：%s' % BACKUP)

    # ── 锚点 1：插入辅助函数（放在 strip_leading_heading 之前）────
    anchor_fn = 'def strip_leading_heading(body, ver, heading):'
    assert text0.count(anchor_fn) == 1, 'strip_leading_heading 锚点不唯一'

    helper = (
        'def unique_anchor(text, anchor, pos):\n'
        '    """把插入锚点扩展成在 `text` 中**恰好出现 1 次**的字符串。\n'
        '\n'
        '    🔴 背景（APP-234 轮实测到的**阻断**缺陷）\n'
        '    `build_blocks()` 用**行锚定正则**挑锚点，而 `apply_file()` 的\n'
        '    唯一性判据用的是 **`text.count(old)`（子串计数）** ⇒ 两者口径\n'
        '    不一致。历史包（如 v2.6）的 README 里同一版本的章节标题会出现\n'
        '    **两次**（一次是**空段**、一次才是正文段 —— APP-233 登记的\n'
        '    缺陷②，真包按 APP-055 未动）；而**下一版**是 robocopy 上一版\n'
        '    ⇒ 原样继承 ⇒ 锚点 `## v2.6 改动说明` 命中 **2 次**\n'
        '    ⇒ `apply_file` 报「命中 2 次」⇒ **插入失败**。\n'
        '\n'
        '    🔴 修法（**窄口径**：只扩展锚点，**不改任何既有章节标题**）\n'
        '    本脚本的既定原则是「**绝不**重写 / 重命名「## vX.Y 改动说明」\n'
        '    这类章节标题」⇒ 本函数**不动**既有内容：只把锚点**逐行向后\n'
        '    扩展**（扩展部分是**既有原文**，会原样保留）到全文中恰好出现\n'
        '    **1 次**为止。\n'
        '    - 锚点本来就唯一 ⇒ **一个字节都不改**（幂等、零影响）；\n'
        '    - 锚点不唯一 ⇒ 逐行扩展（先空行、再下一个标题行）⇒ 唯一即停。\n'
        '\n'
        '    返回扩展后的锚点（**原样回填**，故正文一字不变）。\n'
        '    """\n'
        '    if text.count(anchor) == 1:\n'
        '        return anchor\n'
        '    ext = pos + len(anchor)\n'
        '    acc = anchor\n'
        '    # 逐行向后扩展（最多 60 行 ⇒ 足够覆盖空行 + 下一个标题行）\n'
        '    for ln in text[ext:].split(\'\\n\')[:60]:\n'
        '        acc = acc + ln + \'\\n\'\n'
        '        if text.count(acc) == 1:\n'
        '            return acc\n'
        '    return anchor\n'
        '\n'
        '\n')

    # ── 锚点 2/3：ZH 与 EN 的锚点取用处 ─────────────────────────
    zh_old = (
        '            anchor_m = best[1]\n'
        '            anchor = anchor_m.group(0)\n')
    zh_new = (
        '            anchor_m = best[1]\n'
        '            anchor = unique_anchor(zh, anchor_m.group(0),\n'
        '                                   anchor_m.start())\n')

    en_old = (
        '        if best:\n'
        '            anchor = best[1].group(0)\n')
    en_new = (
        '        if best:\n'
        '            anchor = unique_anchor(en, best[1].group(0),\n'
        '                                   best[1].start())\n')

    for a in (zh_old, en_old):
        assert text0.count(a) == 1, '锚点不唯一：%r' % a[:40]

    text1 = text0.replace(anchor_fn, helper + anchor_fn, 1)
    text1 = text1.replace(zh_old, zh_new, 1)
    text1 = text1.replace(en_old, en_new, 1)

    # ══ 真不变量（写前，内存新文本）═══════════════════════════════
    checks = []
    checks.append(('unique_anchor 已定义且唯一',
                   text1.count('def unique_anchor(text, anchor, pos):') == 1))
    checks.append(('ZH 锚点已改用 unique_anchor',
                   text1.count('anchor = unique_anchor(zh,') == 1))
    checks.append(('EN 锚点已改用 unique_anchor',
                   text1.count('anchor = unique_anchor(en,') == 1))
    try:
        ast.parse(text1)
        checks.append(('ast.parse 通过', True))
    except SyntaxError as e:
        checks.append(('ast.parse 通过（%r）' % (e,), False))
    checks.append(('行尾风格不变（纯 LF）',
                   text1.count('\n') == text1.count('\r\n') + text1.count('\n')
                   and text1.count('\r\n') == 0))
    # 还原式复核：去掉新增内容后应逐字节等于原文
    back = text1.replace(helper + anchor_fn, anchor_fn, 1)
    back = back.replace(zh_new, zh_old, 1)
    back = back.replace(en_new, en_old, 1)
    checks.append(('还原式复核：改回后逐字节同原文', back == text0))
    for keep in ('def build_blocks(texts, ver, changelogs):',
                 'def apply_file(path: str, blocks, dry_run: bool):',
                 'def strip_leading_heading(body, ver, heading):',
                 'def sync_manifest_version(pkg_dir: str, ver: str,'
                 ' dry_run: bool):'):
        checks.append(('旧内容保留：%s' % keep[:44], keep in text1))
    raw1 = text1.encode('utf-8')
    expect = (len(helper.encode('utf-8'))
              + (len(zh_new) - len(zh_old))
              + (len(en_new) - len(en_old)))
    checks.append(('字节增量 == 新增内容字节数（delta=%d）'
                   % (len(raw1) - len(raw0)),
                   len(raw1) - len(raw0) == expect))

    for name, ok in checks:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', name))
    if not all(ok for _, ok in checks):
        print('\n[FAIL] 真不变量未全过 ⇒ **零改动**（不写盘）')
        return 1

    tmp = TARGET + '.tmp_app234'
    with open(tmp, 'wb') as f:
        f.write(raw1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, TARGET)
    print('\n写入完成：%d B → %d B（delta %+d）'
          % (len(raw0), len(raw1), len(raw1) - len(raw0)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
