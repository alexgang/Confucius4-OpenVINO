#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_app251_fix_app049_whitelist.py —— §251：修 app049 打包闸门回归（**定点写入**）。

🔴 **根因（§236 的修法从未入库 ⇒ 已丢失）**
   §236（2026-11-25 07:38）发现并修了同一个闸门：当时 9 个一次性历史诊断脚本
   被 `ACTIVE_RE` 判成「活跃验收脚本」⇒ 闸门 exit=1 ⇒ `pack_v13.py` 拒绝打包。
   §236 的修法（按既有白名单口径放行 ＋ 理由逐条写明）**只改了工作树**，
   **从未 `git add`／commit** ⇒ 该修法在后续提交里**不存在**。
   ⇒ 本轮实测：闸门再次 exit=1（10 处违规）⇒ **v2.7 依然打不出来**。
   （HEAD 的闸门脚本最后一次改动是 7bea9fb / 2026-11-24 18:34 ⇒ 早于 §236。）

🔴 **本脚本只做「白名单增补」这一个动作**
   * 不改 `ACTIVE_RE`、不改判定逻辑、不放宽任何类别；
   * 类别 B（会进包的生产模块）**实测 0 违规** ⇒ 不削弱交付保证；
   * 每条白名单**写明理由**（哪个 APP 轮次、核对的是哪个版本、为什么必须写死）；
   * 写前备份 → 写后在内存跑**真不变量**（行数/行尾/字节等长以外的既有内容逐字未变）
     → 临时文件 → `os.replace` 原子落盘。
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys

GATE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'results', 'app',
    'app049_pkg_path_hardcode_gate.py')

#: 🔴 新增白名单条目：**每条都写明理由**（哪个 APP 轮次 / 核对哪个版本 / 为什么必须写死）。
#:   口径与既有 11 条先例**完全一致**（一次性历史诊断脚本 ⇒ 写死当时版本是**有意的**）。
NEW_ENTRIES = [
    ("results/app/_app133_verify_pkg.py",
     "一次性历史诊断（APP-133 轮：核对 v2.6 包内 EXT 与 commit b2a4978 逐字节一致），"
     "基准就是当时的 v2.6，有意写死；不进包"),
    ("results/app/_app233_verify_manifest_sync.py",
     "一次性历史诊断（§233 轮：sync_c172 的 MANIFEST.version 同步修复复核），"
     "基准就是当时的 v2.5/v2.6，有意写死；不进包"),
    ("results/app/_app233_verify_sec233.py",
     "一次性历史诊断（§233 轮：§233 写入后的独立复核），"
     "断言的就是当时 STATUS 里写死的 v2.6/v2.1 字面量，有意写死；不进包"),
    ("results/app/_app233_verify_sync_c172.py",
     "一次性历史诊断（§233 轮：sync_c172 双标题根因修复的行为级复核），"
     "基准就是当时的 v2.6，有意写死；不进包"),
    ("results/app/_app233_verify_sync_c172_e2e.py",
     "一次性历史诊断（§233 轮：sync_c172 两处修复的端到端复核，用影子包），"
     "基准就是当时的 v2.6，有意写死；不进包"),
    ("results/app/_app234_probe_anchor.py",
     "一次性历史诊断（§234 轮：定位「锚点命中 2 次」的精确机制的探针），"
     "基准就是当时的 v2.5/v2.6，有意写死；不进包"),
    ("results/app/_app234_verify_anchor_fix.py",
     "一次性历史诊断（§234 轮：sync_c172「插入锚点唯一性」修法的独立复核），"
     "基准就是当时的 v2.6，有意写死；不进包"),
    ("results/app/_app234_verify_identity_tool.py",
     "一次性历史诊断（§234 轮：sync_pkg_identity.py 的行为级复核），"
     "基准就是当时的 v2.6/v2.7/v2.8，有意写死；不进包"),
    ("results/app/_app235_verify_evidence_scope.py",
     "一次性历史诊断（§235 轮：sync_pkg_identity.py「证据作用域」修复的行为级复核），"
     "基准就是当时的 v2.6/v2.7，有意写死；不进包"),
    ("live_caption/_app137_candidate_check.py",
     "一次性历史诊断（APP-137 §3 的包内容核对，离线只读），"
     "基准就是当时的 v2.6，有意写死；不进包"),
]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    src = GATE
    if not os.path.isfile(src):
        print('!! 找不到闸门脚本：%s' % src)
        return 2

    raw = open(src, 'rb').read()
    orig_sha = sha256(raw)
    orig_lines = raw.count(b'\n')
    orig_crlf = raw.count(b'\r\n')
    print('写前：bytes=%d sha256=%s lines=%d crlf=%d'
          % (len(raw), orig_sha[:16], orig_lines, orig_crlf))

    # ── 备份（定点写入三件套 ①）──
    bak = src + '.bak_app251'
    shutil.copy2(src, bak)
    print('备份 → %s' % bak)

    text = raw.decode('utf-8')

    # 🔴 该文件是 **CRLF**（crlf == lf_total）⇒ 锚点必须按**实际行尾**构造，
    #   否则命中 0 次（§236 坑：锚点错位 ⇒ 假 FAIL）。
    nl = '\r\n' if orig_crlf == orig_lines and orig_lines else '\n'

    # ── 定位白名单字典的**结束括号**（唯一命中断言）──
    anchor = nl + '}' + nl + nl + nl + 'def code_lines_with_pkg_name(path):'
    if text.count(anchor) != 1:
        print('!! 锚点锚文本命中 %d 次（须恰好 1 次）⇒ 零改动'
              % text.count(anchor))
        return 1

    # ── 生成新增条目文本（缩进与既有条目一致：4 空格）──
    block = []
    for path, reason in NEW_ENTRIES:
        if "'%s'" % path in text:
            print('  （已在白名单，跳过）%s' % path)
            continue
        # 理由可能较长 ⇒ 按 88 列折行，风格与既有条目一致
        head = "    '%s':%s" % (path, nl)
        body = "        '%s',%s" % (reason, nl)
        block.append(head + body)
    if not block:
        print('无需新增白名单条目')
        return 0

    new_text = text.replace(anchor, nl + ''.join(block) + anchor, 1)

    # ── 写前真不变量（内存里跑）──
    def invariants(t: str) -> list:
        errs = []
        # ① 行数增量：插入块本身 N 行 ＋ 替换处**多出的 1 个行尾**（anchor 自带行尾
        #    被原样保留 ⇒ 净增 = N + 1）。
        expect_delta = sum(b.count('\n') for b in block) + 1
        if t.count('\n') - orig_lines != expect_delta:
            errs.append('行数增量不符：期望 %d 实得 %d'
                        % (expect_delta, t.count('\n') - orig_lines))
        # ② 既有正文逐字未变（去掉新增块后必须与原文完全相同）
        stripped = new_text.replace(nl + ''.join(block), '', 1)
        if stripped != text:
            errs.append('既有正文被改动（去新增块后与原文不等）')
        # ③ 新增条目每个都只出现一次
        for path, _ in NEW_ENTRIES:
            if new_text.count("'%s'" % path) != 1:
                errs.append('白名单条目 %s 命中 %d 次（须 1 次）'
                            % (path, new_text.count("'%s'" % path)))
        # ④ 不得改动 ACTIVE_RE / 判定逻辑
        for token in ("ACTIVE_RE = re.compile(r'(^test_|_gate|_check|_verify|_probe)', re.I)",
                      "cat = 'B' if is_pkg_mod else 'A'"):
            if token not in new_text:
                errs.append('判定逻辑被改动：%r 不在' % token)
        return errs

    errs = invariants(new_text)
    if errs:
        print('!! 写前真不变量未过 ⇒ 零改动：')
        for e in errs:
            print('   - %s' % e)
        return 1
    print('写前真不变量：%d 项全 PASS' % 4)

    # ── 原子落盘（临时文件 → os.replace）──
    new_bytes = new_text.encode('utf-8')
    tmp = src + '.tmp_app251'
    with io.open(tmp, 'wb') as f:
        f.write(new_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, src)

    # ── 写后复核（另起进程读盘）──
    after = open(src, 'rb').read()
    print('写后：bytes=%d sha256=%s lines=%d crlf=%d'
          % (len(after), sha256(after)[:16], after.count(b'\n'),
             after.count(b'\r\n')))
    # 🔴 行尾判据＝**风格一致性**（crlf == lf_total ⇒ 全 CRLF），
    #    **不是**绝对 crlf 个数（新增 21 行 ⇒ crlf 必然 +21）。
    if after.count(b'\r\n') != after.count(b'\n'):
        print('!! 行尾风格变了（crlf=%d lf=%d，不再全 CRLF）⇒ 需人工介入'
              % (after.count(b'\r\n'), after.count(b'\n')))
        return 1
    if after.count(b'\r\n') - orig_crlf != sum(b.count('\n') for b in block) + 1:
        print('!! crlf 增量与新增行数不符')
        return 1
    if after.count(b'\n') - orig_lines != sum(b.count('\n') for b in block) + 1:
        print('!! 行数增量不符')
        return 1
    print('写后复核：行尾风格不变 / 行数增量符合 ⇒ PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
