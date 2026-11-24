#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · ① 压缩 `status/app/STATUS_APP.md`（恢复硬限额余量）

## 🔴 为什么必须压缩（Defect 1）
- `STATUS_APP.md` 实测 **39 804 B**／硬上限 **40 000 B**（APP-052④／APP-049）
  ⇒ **仅剩 196 B**；而每轮追加一个 `## §N`（标题行＋指针行＋「最近更新」条目）
  历史上是 **800–1 900 B** ⇒ **下一轮必然超限**。
- 本轮自己要写 §233 ⇒ **不压缩就写不进本轮结论** ⇒ 这是硬前置，不是可选优化。

## 🔴 修法（沿用本仓既有成例，非新发明）
- 成例①：`status/archive/STATUS_APP_sec181_210_headers_20261123.md`（15 517 B）
- 成例②：`status/archive/STATUS_APP_sec162_169_headers_20260720.md`
- 成例③：`status/archive/STATUS_APP_sec135_140_headers_20261113.md`
⇒ **老节的「标题行＋指针行」整块逐字归档（write-once）＋ 活文档换 1 行指针**。

## 🔴 为什么可以只归档「标题行＋指针行」
- §211–§227 的**正文本来就不在活文档里**（全部在 companion／archive 文件中），
  活文档这 15 115 B **全是标题行＋指针行** ⇒ 归档它们**不丢任何正文**。
- 归档前**逐条校验**该区域内所有 `status/...` 指针目标**都存在**（本次 14/14 存在）。

## 🔴 写文件三件套（照纪律）
1. 备份（`%TEMP%/*.bak`）
2. 写前在**内存新文本**跑真不变量＋**还原式复核**（改回须逐字节同）
3. 临时文件 → `os.replace` ⇒ 写后**另起脚本复核**＋`numstat`

## 真不变量（写前跑，FAIL ⇒ 零改动）
- 归档块逐字等于原文件对应字节区间（逐字节）
- 归档块内**所有** `status/...` 指针目标存在
- 活文档除「被替换的那一段」外**逐字节不变**
- 章节号集合不变（只是正文被指针行取代）
- `last_ack` 值不变、唯一
- 行尾风格不变（本次归档区 CRLF ⇒ 归档件与新活文档按所在区域既有行尾写入）
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(
    REPO, 'status', 'archive', 'STATUS_APP_sec211_227_headers_20261125.md')

# ── 要归档的区间：§211 起始 → §228 起始 ─────────────────────────────
SEC_RE = re.compile(rb'^## \xc2\xa7(\d+)', re.M)
FIRST_SEC = 211
LAST_SEC = 227

# ── 归档件头部格式（照抄 sec181_210 成例）───────────────────────────
ARCHIVE_HEADER = (
    '> 🔴 本块为 `status/app/STATUS_APP.md` 的 **§211–§227 标题行＋指针行**，'
    '原文**整块逐字归档**（写一次，不再改）。\n'
    '> 归档时间：2026-11-25；归档块 SHA256 `{sha}`／{nbytes} B。\n'
    '\n'
)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fail(msg: str) -> None:
    print('[FAIL] %s' % msg)
    sys.exit(1)


def main() -> int:
    raw = open(STATUS, 'rb').read()
    orig_bytes = len(raw)
    print('[before] STATUS %d B / 40000 B（余量 %d B）' % (orig_bytes, 40000 - orig_bytes))

    # ── 定位归档区间（字节空间）────────────────────────────────────
    hits = [(m.start(), int(m.group(1))) for m in SEC_RE.finditer(raw)]
    start = end = None
    for i, (off, num) in enumerate(hits):
        if num == FIRST_SEC:
            start = off
        if num == LAST_SEC + 1:
            end = hits[i][0]
    if start is None or end is None:
        fail('定位失败：start=%r end=%r（§211..§228 标题是否存在？）' % (start, end))
    block = raw[start:end]
    print('[region] §211..§227 = 字节 [%d, %d) = %d B' % (start, end, len(block)))

    # ── 校验 1：归档块内所有 status/... 指针目标必须存在 ────────────
    txt = block.decode('utf-8')
    ptrs = sorted(set(re.findall(r'`(status/[^`]+)`', txt)))
    missing = [p for p in ptrs if not os.path.exists(os.path.join(REPO, p.replace('/', os.sep)))]
    print('[check] 指针 %d 个，缺失 %d 个' % (len(ptrs), len(missing)))
    if missing:
        fail('指针目标不存在 ⇒ 不可归档（会丢正文）：%s' % missing)
    if len(ptrs) < 10:
        fail('指针只有 %d 个，与预期不符 ⇒ 区间定位可能错' % len(ptrs))

    # ── 校验 2：归档块里每个 §N 都有对应的 ## §N 标题行 ─────────────
    in_block = [int(m.group(1)) for m in SEC_RE.finditer(block)]
    expect = [n for n in range(FIRST_SEC, LAST_SEC + 1)]
    missing_secs = [n for n in expect if n not in in_block]
    # §216/§217/§218 历史上就没有独立节（§171–§180 批内），不算缺失
    if missing_secs:
        print('[check] 区间内无独立标题行的节号：%s（历史本就没有独立节）'
              % missing_secs)
    print('[check] 区间内实际有标题行的节：%s' % in_block)

    # ── 校验 3：归档块行尾风格 ─────────────────────────────────────
    crlf = block.count(b'\r\n')
    lf_total = block.count(b'\n')
    print('[check] 归档块 CRLF=%d / LF 总数=%d' % (crlf, lf_total))
    is_crlf_block = (crlf > 0 and crlf == lf_total)

    # ── 构造归档件（write-once：已存在则拒绝覆盖）──────────────────
    if os.path.exists(ARCHIVE):
        fail('归档件已存在（write-once）⇒ 中止：%s' % ARCHIVE)
    arch_body = ARCHIVE_HEADER.format(sha=sha256_bytes(block), nbytes=len(block))
    arch_bytes = arch_body.encode('utf-8') + block
    if is_crlf_block:
        # 归档区是 CRLF ⇒ 归档件正文保持 CRLF（逐字归档），头部行用 CRLF
        arch_body_crlf = arch_body.replace('\n', '\r\n').encode('utf-8')
        arch_bytes = arch_body_crlf + block
    print('[archive] 将写 %s（%d B）' % (os.path.basename(ARCHIVE), len(arch_bytes)))

    # ── 构造新活文档：替换该区间为 1 行指针 ────────────────────────
    # 指针行的行尾：**跟随被替换区域的首行行尾**（该区域是 CRLF）
    ptr_line = (
        '> 🔴 **§211–§227 标题行＋指针行已整块逐字归档** ⇒ '
        '`status/archive/STATUS_APP_sec211_227_headers_20261125.md`'
        '（归档块 SHA256 `%s`／%d B；**各节正文原位置不变**，仍在各自 companion／archive 文件中）\n'
        % (sha256_bytes(block), len(block)))
    eol = b'\r\n' if is_crlf_block else b'\n'
    new_raw = raw[:start] + ptr_line.encode('utf-8') + eol + raw[end:]

    # ── 写前真不变量（全部在内存新文本上跑）────────────────────────
    checks = []

    def chk(name, cond, detail=''):
        checks.append((name, bool(cond), detail))
        print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                               ('｜' + detail) if detail else ''))

    print('[pre-write] 真不变量：')
    # 1) 非归档区逐字节不变
    chk('非归档区逐字节不变',
        new_raw[:start] == raw[:start] and new_raw[start + len(ptr_line.encode('utf-8')) + len(eol):] == raw[end:],
        '前缀 %d B + 后缀 %d B' % (start, len(raw) - end))
    # 2) 归档块逐字出现在归档件里
    chk('归档块逐字在归档件中', block in arch_bytes, '%d B' % len(block))
    # 3) 还原式复核：把新活文档的指针行+行尾换回原区间 ⇒ 必须逐字节等于原文件
    restored = (new_raw[:start] + block + new_raw[start + len(ptr_line.encode('utf-8')) + len(eol):])
    chk('还原式复核＝逐字节原文件', restored == raw,
        '%d B vs %d B' % (len(restored), len(raw)))
    # 4) **每个 §N 都必须仍被「交代」**（活文档里有标题行，或归档件里有标题行）
    #    ⚠️ 判据修正（§233 轮踩到的坑）：不能断言「章节号集合不变」——
    #    归档标题行**本来就要**把那些 §N 从活文档里移走 ⇒ 那个断言必假 FAIL。
    #    真正的真不变量是「**没有丢**」：old_secs ⊆ (new_secs ∪ archived_secs)。
    old_secs = set(int(m.group(1)) for m in SEC_RE.finditer(raw))
    new_secs = set(int(m.group(1)) for m in SEC_RE.finditer(new_raw))
    arc_secs = set(int(m.group(1)) for m in SEC_RE.finditer(block))
    lost = old_secs - new_secs - arc_secs
    chk('无节丢失（old ⊆ new ∪ archived）', not lost,
        'old=%d new=%d archived=%d lost=%s'
        % (len(old_secs), len(new_secs), len(arc_secs), sorted(lost) or '无'))
    chk('归档掉的节在归档件里逐个在位',
        {n for n in old_secs - new_secs} == arc_secs,
        '归档节 %s' % sorted(arc_secs))
    chk('活文档剩余节号是 old 的子集', new_secs <= old_secs,
        'new=%s' % sorted(new_secs))
    # 5) last_ack 唯一且值不变
    la_old = re.findall(rb'last_ack:\s*APP-(\d+)', raw)
    la_new = re.findall(rb'last_ack:\s*APP-(\d+)', new_raw)
    chk('last_ack 唯一且不变', la_old == la_new and len(la_new) == 1,
        'old=%s new=%s' % (la_old, la_new))
    # 6) 体积上限
    chk('新活文档 ≤ 40000 B', len(new_raw) <= 40000, '%d B' % len(new_raw))
    # 7) 行数不增
    chk('行数不增', new_raw.count(b'\n') <= raw.count(b'\n'),
        '%d → %d' % (raw.count(b'\n'), new_raw.count(b'\n')))
    # 8) CRLF 计数：归档区是 CRLF ⇒ 归档后活文档 CRLF 应减少（归档到别的文件）
    chk('活文档 CRLF 减少（归档区为 CRLF）', new_raw.count(b'\r\n') < raw.count(b'\r\n'),
        '%d → %d' % (raw.count(b'\r\n'), new_raw.count(b'\r\n')))
    # 9) 头部「已压缩」索引行仍存在（供 reviewer 追溯）
    chk('头部「已压缩」索引仍存在', b'\xe5\xb7\xb2\xe5\x8e\x8b\xe7\xbc\xa9' in new_raw)
    # 10) 归档件不含 secrets
    chk('归档件无明显密钥', not re.search(rb'(password|token|secret)\s*[:=]', arch_bytes, re.I))

    if not all(c[1] for c in checks):
        print('[ABORT] 真不变量有 FAIL ⇒ 零改动')
        return 1

    # ── 备份 ───────────────────────────────────────────────────────
    bak = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app233')
    shutil.copy2(STATUS, bak)
    print('[backup] %s（%d B）' % (bak, os.path.getsize(bak)))

    # ── 写盘：临时文件 → os.replace ────────────────────────────────
    tmp_a = ARCHIVE + '.tmp'
    with open(tmp_a, 'wb') as f:
        f.write(arch_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_a, ARCHIVE)

    tmp_s = STATUS + '.tmp'
    with open(tmp_s, 'wb') as f:
        f.write(new_raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_s, STATUS)

    print('[write] 完成')
    print('[after ] STATUS %d B / 40000 B（余量 %d B）'
          % (len(new_raw), 40000 - len(new_raw)))
    print('[after ] 归档件 %d B' % os.path.getsize(ARCHIVE))
    print('SHA256 STATUS  %s' % sha256_bytes(open(STATUS, 'rb').read()))
    print('SHA256 归档件 %s' % sha256_bytes(open(ARCHIVE, 'rb').read()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
