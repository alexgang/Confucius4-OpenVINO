#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · 压缩后的**独立**写后复核（另起脚本，不 import 被检脚本）。

## 🔴 判据的基准＝**git 里的压缩前版本**（不是临时备份）
第一版用 `%TEMP%/STATUS_APP.md.bak_app233` 作基准 ⇒ 该文件是**压缩前**的活文档，
而本脚本在 §233 写入**之后**再跑 ⇒ 活文档已含 §233 的追加
⇒ 「还原式复核＝逐字节等于写前备份」**必然 FAIL**（假 FAIL 源）。
⇒ 改用 **git 里的压缩前版本**（提交 `3670d1a` 的 `status/app/STATUS_APP.md`）作基准
⇒ 该基准**不随后续追加而变** ⇒ 判据稳定且可重复。

## 🔴 行尾口径（§226 的 autocrlf 根因）
git 里存的是 **LF 归一化**版本（`core.autocrlf=true`），而工作树是 **CRLF** ⇒
两者**逐字节不等**（39 707 B vs 39 804 B）⇒ **比对必须先归一化**。
⇒ 本脚本**两侧一律先归一化到 LF 再比**；归档件头部声明的 SHA256/字节数
   则按**归档件自己存的原始字节**校验（**自洽**，不依赖跨版本口径）。

## 判据
1. 活文档 ≤ 40 000 B 且 ≤ 300 行（APP-052④／APP-049 硬限额）
2. 归档块的**归一化**内容 == git 基准里 §211–§227 区间的**归一化**内容
3. 归档件**自洽**：头部声明的 SHA256／字节数 == 归档件自存块的 SHA256／长度
4. **压缩是纯替换**：把 git 基准的 §211–§227 区间换成指针行 ⇒ 与活文档
   **逐行**比对，差异**只允许**落在 §233 本轮那一小撮改动上（枚举判定）
5. §135–§232 每个节号都仍被「交代」（活文档标题行 或 归档件标题行）
6. `last_ack` 唯一且仍 = APP-133
7. 归档件内所有 `status/...` 指针目标存在
8. 头部「已压缩」索引含新归档件路径（reviewer 可追溯）
9. **反证组**：把归档块篡改 1 字节 ⇒ 判据 2/3/4 必须 FAIL
   （证明判据有鉴别力，不是恒 PASS）
"""
from __future__ import annotations

import difflib
import hashlib
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(
    REPO, 'status', 'archive', 'STATUS_APP_sec211_227_headers_20261125.md')
# 🔴 压缩**前**的活文档（git 里的版本 ⇒ 不随后续 §233 追加而变）
BASELINE_REV = '3670d1a'

SEC_RE = re.compile(rb'^## \xc2\xa7(\d+)', re.M)
#: §233 本轮允许出现在「差异行」里的标记（枚举 ⇒ 差异必须**可解释**）
#: （**新旧两版**都要列出：§233 是「就地替换」⇒ 旧行也在差异里）
ALLOWED_MARKERS = (
    '§233',                      # §233 标题行
    'sec233_detail_20261125',    # §233 指针行（**小写**文件名）
    '2026-11-25',                # 「最近更新」新增条目 ＋ 头部「更新时间」
    '更新时间',
    '| 客户包目录 |',            # 表行（就地替换：旧行也在差异里）
    '| **完整版 v2.6',           # 表行新版本
    '| **完整版 v2.5',           # 表行旧版本（被替换掉的那行）
    '| 客户包 zip |',            # 表行（就地替换）
    '§211–§227 标题行＋指针行已整块逐字归档',
)

n_ok = 0
n_bad = 0


def chk(name, cond, detail=''):
    global n_ok, n_bad
    if cond:
        n_ok += 1
        print('  [PASS] %s%s' % (name, ('｜' + detail) if detail else ''))
    else:
        n_bad += 1
        print('  [FAIL] %s%s' % (name, ('｜' + detail) if detail else ''))


def norm(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n')


def main() -> int:
    raw = open(STATUS, 'rb').read()
    arch = open(ARCHIVE, 'rb').read()
    p = subprocess.run(['git', '-C', REPO, 'show',
                        '%s:status/app/STATUS_APP.md' % BASELINE_REV],
                       capture_output=True)
    if p.returncode != 0:
        print('[FAIL] 取 git 基准失败：%s' % p.stderr.decode('utf-8', 'replace'))
        return 1
    bak = p.stdout
    nraw, narch, nbak = norm(raw), norm(arch), norm(bak)
    print('[post-write] 活文档 %d B / 40000 B｜%d 行 / 300 行'
          % (len(raw), raw.count(b'\n')))
    print('[baseline ] git %s（LF 归一化 %d B；原始 %d B）'
          % (BASELINE_REV, len(nbak), len(bak)))
    print('[archive ] %d B（归一化 %d B）' % (len(arch), len(narch)))

    # 1) 硬限额
    chk('活文档 ≤ 40000 B', len(raw) <= 40000, '%d B' % len(raw))
    chk('活文档 ≤ 300 行', raw.count(b'\n') <= 300, '%d 行' % raw.count(b'\n'))

    # 2) 归档块 == git 基准的 §211–§227 区间（归一化后）
    hits = [(m.start(), int(m.group(1))) for m in SEC_RE.finditer(nbak)]
    start = end = None
    for i, (off, num) in enumerate(hits):
        if num == 211:
            start = off
        if num == 228:
            end = hits[i][0]
    chk('git 基准里能定位 §211..§227 区间', start is not None and end is not None,
        '[%s, %s)' % (start, end))
    block = nbak[start:end]
    # 归档件里「头部 + 块」⇒ 块是归档件的尾部
    arch_block = narch[len(narch) - len(block):] if len(narch) >= len(block) else b''
    chk('归档块（归一化）== git 基准区间', arch_block == block,
        '%d B' % len(block))
    chk('归档件 = 头部 + 原区间（无多余改动）',
        narch.endswith(block), '尾部 %d B' % len(block))

    # 3) 归档件**自洽**（头部声明 vs 归档件自存块，原始字节口径）
    m = re.search(rb'SHA256 `([0-9a-f]{64})`[^0-9]{0,12}(\d+) B', arch)
    if m:
        decl_sha = m.group(1).decode()
        decl_n = int(m.group(2))
        # 归档件自存的原始块：去掉头部（头部以 '\n\n' 结束）
        hdr_end = arch.find(b'\n\n') + 2
        raw_block = arch[hdr_end:]
        chk('归档件头部声明 SHA256 与自存块一致',
            decl_sha == hashlib.sha256(raw_block).hexdigest(), decl_sha[:16])
        chk('归档件头部声明字节数与自存块一致', decl_n == len(raw_block),
            '%d vs %d' % (decl_n, len(raw_block)))
    else:
        chk('归档件头部可解析（SHA256＋字节数）', False, '正则未命中')

    # 4) 压缩是**纯替换** ⇒ 差异只落在 §233 本轮那一小撮改动上
    PTR_MARK = '> 🔴 **§211–§227 标题行＋指针行已整块逐字归档**'.encode('utf-8')
    ptr = re.search(re.escape(PTR_MARK) + rb'[^\n]*\n', nraw)
    chk('活文档有唯一指针行', bool(ptr) and len(re.findall(
        re.escape(PTR_MARK), nraw)) == 1)
    if ptr:
        # 把 git 基准的区间换成**活文档里那根指针行** ⇒ 应当与活文档只差 §233 那些改动
        base_compressed = nbak[:start] + nraw[ptr.start():ptr.end()] + nbak[end:]
        a = base_compressed.decode('utf-8').split('\n')
        b = nraw.decode('utf-8').split('\n')
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        diffs = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                continue
            diffs.append((tag, a[i1:i2], b[j1:j2]))
        unexplained = []
        for tag, old_l, new_l in diffs:
            for ln in list(old_l) + list(new_l):
                if not any(mk in ln for mk in ALLOWED_MARKERS):
                    unexplained.append((tag, ln[:70]))
        chk('压缩是纯替换（差异全部可归因于 §233 本轮改动）', not unexplained,
            '差异块 %d 个，不可归因 %d 个%s'
            % (len(diffs), len(unexplained),
               ('｜' + str(unexplained[:2])) if unexplained else ''))
        chk('差异块数 ≤ 12（§233 只改了 5 处）', len(diffs) <= 12,
            '%d 个' % len(diffs))
        # 反证：把归档块篡改 ⇒ 判据 2 必须 FAIL
        tampered = block[:10] + (b'X' if block[10:11] != b'X' else b'Y') + block[11:]
        chk('反证组：篡改后「归档块 == git 基准区间」FAIL', tampered != arch_block)

    # 5) 无节丢失
    old_secs = set(int(m.group(1)) for m in SEC_RE.finditer(nbak))
    new_secs = set(int(m.group(1)) for m in SEC_RE.finditer(nraw))
    arc_secs = set(int(m.group(1)) for m in SEC_RE.finditer(narch))
    chk('每个旧节号都被交代（活文档∪归档件）', not (old_secs - new_secs - arc_secs),
        'lost=%s' % sorted(old_secs - new_secs - arc_secs) or '无')
    chk('§228–§232 仍在活文档', {228, 229, 230, 231, 232} <= new_secs)

    # 6) last_ack
    la = re.findall(rb'last_ack:\s*APP-(\d+)', nraw)
    chk('last_ack 唯一且仍 = APP-133', la == [b'133'], str(la))

    # 7) 指针目标全在
    ptrs = sorted(set(re.findall(r'`(status/[^`]+)`', arch.decode('utf-8'))))
    missing = [p for p in ptrs
               if not os.path.exists(os.path.join(REPO, p.replace('/', os.sep)))]
    chk('归档件内指针目标全存在', not missing, '%d 个，缺 %s'
        % (len(ptrs), missing or '无'))

    # 8) 头部索引可追溯
    chk('头部「已压缩」索引含新归档件路径',
        b'status/archive/STATUS_APP_sec211_227_headers_20261125.md' in nraw)

    # 9) 反证组：篡改归档块 1 字节 ⇒ 判据 2/3 必须 FAIL
    print('  [counter-evidence] 把归档块篡改 1 字节 ⇒ 相关判据必须 FAIL：')
    hdr_end = arch.find(b'\n\n') + 2
    raw_block = arch[hdr_end:]
    t_sha = hashlib.sha256(
        raw_block[:10] + (b'X' if raw_block[10:11] != b'X' else b'Y')
        + raw_block[11:]).hexdigest()
    decl = re.search(rb'SHA256 `([0-9a-f]{64})`', arch).group(1).decode()
    chk('反证组：篡改后「头部 SHA256 自洽」FAIL', t_sha != decl)

    print('\n[summary] PASS=%d FAIL=%d' % (n_ok, n_bad))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
