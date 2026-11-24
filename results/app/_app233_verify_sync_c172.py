#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · `sync_c172_version_identity_to_pkg.py` 双标题根因修复的**行为级**复核。

## 🔴 为什么必须行为级真跑（§「判据改成行为级真跑才是定论」）
本轮的缺陷是「**产出的 README 结构不对**」⇒ 判据必须真的**跑一遍产出**，
再检查产出文本；不能只 grep 源码里的字面量。

## 判据
### A. 主判据（正向）
1. **ZH**：喂「正文自带 `## v2.6 改动说明`」⇒ 产出 README_zh 里
   `## v2.6 改动说明` **恰好 1 次**，且**不含空标题段**。
2. **EN**：喂「正文自带 `## v2.6 changes`」⇒ 产出 README_en 里
   `## What's new in v2.6` **恰好 1 次**，且 `## v2.6 changes` **不再出现**。
3. **幂等**：正文**不带**标题时 ⇒ 产出与旧行为**逐字节相同**（不回归）。
4. **不误伤**：正文首行是 `### 1. xxx`（三级标题＝正文小节）⇒ **必须保留**。
5. **正文一字不动**：剥离后剩下的正文与原正文（除首行标题外）**逐字相同**。

### B. 反证组（判据有鉴别力，不是恒 PASS）
把被测模块的 `strip_leading_heading` **换成恒不剥离的旧实现**
⇒ 判据 1/2 **必须 FAIL** ⇒ 证明判据能识破有缺陷的旧代码。

## 🔴 不 import 被检脚本的兄弟脚本污染
本脚本**直接 import** `sync_c172_version_identity_to_pkg`（它没有 import 期副作用：
模块级只有常量与函数定义），但**判据 4/5 用的是纯函数**，
判据 1/2 走的是**真实的 `build_blocks`**（生产同款调用路径）。
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
MOD = os.path.join(REPO, 'live_caption', 'sync_c172_version_identity_to_pkg.py')

n_ok = n_bad = 0


def chk(name, cond, detail=''):
    global n_ok, n_bad
    if cond:
        n_ok += 1
        print('  [PASS] %s%s' % (name, ('｜' + detail) if detail else ''))
    else:
        n_bad += 1
        print('  [FAIL] %s%s' % (name, ('｜' + detail) if detail else ''))


def load():
    spec = importlib.util.spec_from_file_location('sync_c172_under_test', MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ── 最小可用的 README 样本（结构与真实包一致）────────────────────
ZH_README = (
    '# Confucius4-R2T2 实时字幕（技术评估版 v2.5）\n\n'
    '## v2.5 改动说明\n\n旧内容。\n\n'
    '## v2.4 改动说明\n\n更旧内容。\n'
)
EN_README = (
    '# Confucius4-R2T2 Live Captions (technical evaluation build v2.5)\n\n'
    "## What's new in v2.5\n\nOld content.\n\n"
    "## What's new in v2.4\n\nOlder content.\n"
)
NOTICE = (
    'Confucius4 LiveCaption v2.5 — 第三方组件归属与许可证\n'
    '=====================================================\n\n'
    '内容。\n'
)

ZH_BODY_WITH_HEAD = (
    '## v2.6 改动说明\n\n'
    '**完整版 v2.6**（MiniMVP / SpecialMVP 不带此包）。\n\n'
    '### 1. 保留背景音（bgkeep）进完整版\n\n'
    '正文内容。\n'
)
EN_BODY_WITH_HEAD = (
    '## v2.6 changes\n\n'
    '**Full edition v2.6** (not included in MiniMVP / SpecialMVP).\n\n'
    '### 1. Keep background audio (bgkeep) in the full edition\n\n'
    'Body content.\n'
)
ZH_BODY_NO_HEAD = (
    '**完整版 v2.6**（MiniMVP / SpecialMVP 不带此包）。\n\n'
    '### 1. 保留背景音（bgkeep）进完整版\n\n'
    '正文内容。\n'
)
ZH_BODY_H3_FIRST = (
    '### 1. 保留背景音（bgkeep）进完整版\n\n'
    '正文内容。\n'
)


def apply_blocks(mod, texts, blocks):
    """按 `build_blocks` 的契约做替换（生产同款调用路径）。"""
    out = dict(texts)
    for fn, blist in blocks.items():
        t = out[fn]
        for old, new, desc, _want in blist:
            if old not in t:
                raise AssertionError('替换锚点未命中：%s｜%s' % (fn, desc))
            t = t.replace(old, new, 1)
        out[fn] = t
    return out


def run_case(mod, zh_body, en_body):
    texts = {'README_zh.md': ZH_README, 'README_en.md': EN_README, 'NOTICE': NOTICE}
    changelogs = {'README_zh.md': zh_body, 'README_en.md': en_body}
    blocks, adv = mod.build_blocks(texts, '2.6', changelogs)
    return apply_blocks(mod, texts, blocks)


def main() -> int:
    print('=== 被测模块：%s ===' % os.path.basename(MOD))
    mod = load()

    # ── A1 / A2：主判据（正文自带标题）────────────────────────────
    print('\n[A] 主判据（正文自带标题 ⇒ 不应产生第二个标题）')
    out = run_case(mod, ZH_BODY_WITH_HEAD, EN_BODY_WITH_HEAD)
    zh = out['README_zh.md']
    en = out['README_en.md']
    n_zh = len(re.findall(r'^## v2\.6 改动说明\s*$', zh, re.M))
    n_en = len(re.findall(r"^## What's new in v2\.6\s*$", en, re.M))
    n_old = len(re.findall(r'^## v2\.6 changes\s*$', en, re.M))
    chk('ZH：## v2.6 改动说明 恰好 1 次', n_zh == 1, 'count=%d' % n_zh)
    chk('ZH：不含空标题段（标题后紧跟非标题行）',
        not re.search(r'^## v2\.6 改动说明\s*\n\s*##', zh, re.M))
    chk("EN：## What's new in v2.6 恰好 1 次", n_en == 1, 'count=%d' % n_en)
    chk('EN：## v2.6 changes 不再出现', n_old == 0, 'count=%d' % n_old)
    chk("EN：不含空标题段", not re.search(
        r"^## What's new in v2\.6\s*\n\s*##", en, re.M))

    # ── A5：正文一字不动 ─────────────────────────────────────────
    # 插入块结构 = `## v2.6 改动说明\n\n<body>\n\n<anchor>`
    # ⇒ 正文之后还跟着**锚点标题**（那是原 README 的既有内容，不是本函数产物）
    def body_part(text, head):
        tail = text.split(head + '\n\n', 1)[1]
        # 插入块末尾跟着**锚点标题**（原 README 的既有内容）⇒ 取**第一个**
        # `\n\n## ` 之前的内容作为正文（用 rsplit 会切到最后那个锚点 ⇒ 取错）
        return tail.split('\n\n## ', 1)[0].strip('\n')

    zh_expect = ZH_BODY_WITH_HEAD.split('\n', 1)[1].strip('\n')
    chk('ZH：剥离后正文逐字等于原正文（除首行标题）',
        body_part(zh, '## v2.6 改动说明') == zh_expect,
        '%r' % body_part(zh, '## v2.6 改动说明')[:40])
    chk('ZH：正文小节 ### 1. 保留背景音 仍在',
        '### 1. 保留背景音（bgkeep）进完整版' in zh)
    en_expect = EN_BODY_WITH_HEAD.split('\n', 1)[1].strip('\n')
    chk('EN：剥离后正文逐字等于原正文（除首行标题）',
        body_part(en, "## What's new in v2.6") == en_expect,
        '%r' % body_part(en, "## What's new in v2.6")[:40])

    # ── A3：幂等（正文不带标题 ⇒ 产出不变）───────────────────────
    print('\n[B] 幂等（正文不带标题 ⇒ 不该改动正文）')
    out2 = run_case(mod, ZH_BODY_NO_HEAD, EN_BODY_WITH_HEAD)
    zh2 = out2['README_zh.md']
    chk('ZH：正文不带标题时正文原样插入',
        body_part(zh2, '## v2.6 改动说明') == ZH_BODY_NO_HEAD.strip('\n'),
        '%r' % body_part(zh2, '## v2.6 改动说明')[:40])
    chk('ZH：正文不带标题时标题仍恰好 1 次',
        len(re.findall(r'^## v2\.6 改动说明\s*$', zh2, re.M)) == 1)

    # ── A4：不误伤（### 三级标题是正文小节）──────────────────────
    print('\n[C] 不误伤（正文首行是 ### 小节 ⇒ 必须保留）')
    out3 = run_case(mod, ZH_BODY_H3_FIRST, EN_BODY_WITH_HEAD)
    zh3 = out3['README_zh.md']
    chk('ZH：### 1. 小节被保留',
        '### 1. 保留背景音（bgkeep）进完整版' in zh3)
    chk('ZH：三级标题没被误剥（标题后紧跟小节）',
        re.search(r'^## v2\.6 改动说明\n\n### 1\.', zh3, re.M) is not None)

    # ── B：反证组（换成恒不剥离的旧实现）────────────────────────
    print('\n[D] 反证组：把剥离函数换成恒不剥离的旧实现 ⇒ 判据 1/2 必须 FAIL')
    orig = mod.strip_leading_heading
    try:
        mod.strip_leading_heading = lambda body, ver, heading: (
            body.strip('\n') if body else body, False, None)
        out_old = run_case(mod, ZH_BODY_WITH_HEAD, EN_BODY_WITH_HEAD)
        zho = out_old['README_zh.md']
        eno = out_old['README_en.md']
        n_zh_old = len(re.findall(r'^## v2\.6 改动说明\s*$', zho, re.M))
        n_en_old = len(re.findall(r"^## What's new in v2\.6\s*$", eno, re.M))
        n_old_old = len(re.findall(r'^## v2\.6 changes\s*$', eno, re.M))
        chk('反证组：旧实现下 ZH 标题数 > 1（判据能识破）', n_zh_old > 1,
            'count=%d' % n_zh_old)
        chk('反证组：旧实现下 EN 残留 ## v2.6 changes（判据能识破）',
            n_old_old > 0, 'count=%d' % n_old_old)
    finally:
        mod.strip_leading_heading = orig

    # ── E：真实包 README 上的同款缺陷可被本函数复现并修掉 ───────
    print('\n[E] 用真实 v2.6 包 README 的实际问题复现')
    real_zh = os.path.join(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.6',
                            'README_zh.md')
    if os.path.isfile(real_zh):
        t = open(real_zh, encoding='utf-8').read()
        before = len(re.findall(r'^## v2\.6 改动说明\s*$', t, re.M))
        stripped, did, line = mod.strip_leading_heading(
            ZH_BODY_WITH_HEAD, '2.6', '## v2.6 改动说明')
        chk('真实包 README_zh 里 v2.6 标题确实有 2 个（缺陷可复现）',
            before == 2, 'count=%d' % before)
        chk('对真实正文剥离成功', did and stripped.startswith('**完整版 v2.6'),
            '剥离行=%r' % line)
    else:
        chk('真实包 README_zh 存在（用于复现）', False, real_zh)

    print('\n[summary] PASS=%d FAIL=%d' % (n_ok, n_bad))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
