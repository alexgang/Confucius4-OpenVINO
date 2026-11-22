#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §220：**「最近更新」段加一条**（执行轮 ⇒ 必须写；待命轮不写）。

## 为什么需要这个脚本
🔴 活文档逼近 **40 000 B** 限额（写完 §220 后 39 799 B ⇒ **只剩 201 B**）
   ⇒ 新增一条「最近更新」必须**先把较旧那条整块逐字归档**（APP-052④ 纪律：
   **归档件 write-once；原文一字未删、未改**；活文档换**指针行**）。

## 两步归档
1. 「最近更新」段第 1 条（当前最新 = APP-119）⇒
   `status/archive/STATUS_APP_recent_updates_20261122.md`；
2. 若仍超限 ⇒ 再把 **§213** 的正文整块归档到
   `status/app/STATUS_APP_sec213_20261122.md`（腾地方）。

## 纪律
- 🔴 **只动「最近更新」段 ＋ §213**；其余章节一字不改；
- 🔴 **写前还原式复核**（逐条**逆向撤销编辑** ⇒ 反推回原件**逐字节相同**）＋ 真不变量；
- 🔴 写前算字节：超 40 000 B ⇒ **fail-closed 不落盘**；
- 🔴 **临时文件 → `os.replace`**（绝不 `open(p,'w')` 截断）；
- 🔴 归档件 **write-once**（已存在 ⇒ 报错，不覆盖）。

## 用法
```
python live_caption/_app120_recent_update.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_RU = os.path.join(REPO, 'status', 'archive',
                       'STATUS_APP_recent_updates_20261122.md')
ARCH_213 = os.path.join(REPO, 'status', 'app',
                        'STATUS_APP_sec213_20261122.md')
LIMIT_BYTES = 40000

#: 新的「最近更新」条目（**正文事实全部来自本轮证据 json**）
#: 🔴 **长度纪律**：活文档逼近 40 000 B ⇒ 本条目只放**结论 + 关键数字**，
#:   逐条明细在 companion `status/app/STATUS_APP_sec220_detail_20261122.md`。
NEW_ENTRY = (
    '> 🔴 2026-11-22 16:54 ｜ **执行 APP-120**（last_ack=APP-119 → **APP-120**）：'
    '🟢 **§0 ASR-065/066 四问逐项回答完毕**（pml=320＋前缀左截断默认开／'
    '`asr_enc_tiers` 默认 off＋分档失败退回 2400／`max_new≤64`＋段长 20 s＋'
    '`base_len>pml` 报错）；**包内 python** 跑 §86 三素材 ⇒ **NPU md5 逐字节等于参照**'
    '（RTF 0.2754/0.2483/0.2416），**GPU.0 md5 不同**（RTF 0.2126/0.1829/0.1722）'
    '⇒ 已用 **ASR 模块自己的 GPU.0 基准**（asr162）**实证**「与 App 接入零回归」｜'
    '🟢 **§1 MiniMVP v1.1 从 v2.5 全集裁剪**（ASR 只 0.6B／MT 只 INT8-CW／TTS 只 OV／'
    '只预设 A／无克隆／10 语种／出厂默认 GPU.0·GPU.0·NPU）｜'
    '🟢 **§2 验收全过**：洁净度 **0 违规**＋模型身份 17/17＋**整链 14/14 PASS**'
    '（164 句、**丢弃 0**、语速 max **1.3917**、**积压峰值 43.1 s**（v2.5 臂 88.8 s）／'
    '收尾 29.9 s（v2.5 69.6 s）、首包 0.39 s）＋**10 语种 10/10**＋设备切换 6/6＋'
    '迁移 3/3｜'
    '🟢 **已签 `ACCEPTED.json`（v1.1，闸门⑤ PASS）＋已打 zip**'
    '（**5 212 356 737 B / 4.854 GiB**，10 881 文件）｜'
    '🔴 **`timing_valid=false`**（synth_rtf P90 **0.9412**>0.75 ⇒ 计时类不作数；'
    '计数类成立）｜🔴 **修掉 3 处真缺陷**＋**如实登记 2 处事故**（详见 companion）｜'
    '**本条需等 reviewer 复核**\n'
)


def log(*a):
    print(*a, flush=True)


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Editor:
    """按行号做区间替换，并记录**可逆快照**（撤销 ⇒ 逐字节还原）。"""

    def __init__(self, lines):
        self.lines = list(lines)
        self.undo_stack = []

    def replace(self, a, b, rep):
        old = self.lines[a:b]
        # 🔴 记下**替换区间的长度**（`len(rep)`），撤销时按它定位
        #   （**不是** `len(old)`：替换前后行数可以不同 ⇒ 用 len(old) 会错位）。
        self.undo_stack.append((a, len(rep), old))
        self.lines[a:b] = rep

    def undo_all(self):
        out = list(self.lines)
        for a, n_rep, old in reversed(self.undo_stack):
            out[a:a + n_rep] = old
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    with open(STATUS, 'rb') as f:
        orig = f.read()
    lines = orig.decode('utf-8').splitlines(keepends=True)

    # ── 定位「最近更新」段 ───────────────────────────────────────
    s = None
    for i, l in enumerate(lines):
        if l.startswith('## 最近更新'):
            s = i
            break
    if s is None:
        log('FAIL: 找不到「最近更新」段')
        return 2
    e = len(lines)
    for j in range(s + 1, len(lines)):
        if lines[j].startswith('## '):
            e = j
            break
    ru_body = lines[s + 1:e]
    if not ru_body or not ru_body[0].startswith('> 🔴 '):
        log('FAIL: 「最近更新」第 1 条不是条目行')
        return 2
    first = ru_body[0]

    for p in (ARCH_RU, ARCH_213):
        if os.path.exists(p):
            log('FAIL: 归档件已存在（write-once）%s' % p)
            return 2

    arch_ru_text = first
    arch_ru_sha = sha(arch_ru_text.encode('utf-8'))
    ptr_ru = ('> 🔴 本节 1 条较旧「最近更新」条目（🔴 2026-11-21 04:34:48'
              '「执行 APP-119」）原文已**整块逐字归档** ⇒ '
              '`status/archive/STATUS_APP_recent_updates_20261122.md`'
              '（%d B／块 SHA256 `%s`）；**原文一字未删、未改**。'
              '活文档本节只留本行 ＋ 最新 1 条。\n'
              % (len(arch_ru_text.encode('utf-8')), arch_ru_sha))
    log('归档「最近更新」第 1 条（%d B，SHA %s）'
        % (len(arch_ru_text.encode('utf-8')), arch_ru_sha[:16]))

    ed = Editor(lines)

    # ── 编辑 ①：「最近更新」段 ──────────────────────────────────
    ed.replace(s + 1, e, [NEW_ENTRY, ptr_ru] + ru_body[1:])
    new_text = ''.join(ed.lines)
    new_bytes = new_text.encode('utf-8')

    # ── 编辑 ②：若仍超限 ⇒ 归档 §213 正文 ───────────────────────
    arch_213_text = None
    if len(new_bytes) > LIMIT_BYTES:
        log('仍超限（%d B）⇒ 再归档 §213 正文腾地方' % len(new_bytes))
        cur = ed.lines
        s2 = None
        for i, l in enumerate(cur):
            if l.startswith('## §213 '):
                s2 = i
                break
        if s2 is None:
            log('FAIL: 找不到 §213')
            return 2
        e2 = len(cur)
        for j in range(s2 + 1, len(cur)):
            if cur[j].startswith('## '):
                e2 = j
                break
        title213 = cur[s2]
        body213 = cur[s2 + 1:e2]
        arch_213_text = title213 + ''.join(body213)
        sha213 = sha(arch_213_text.encode('utf-8'))
        ptr213 = ('> 🔴 本节正文已**整块逐字归档** ⇒ `status/app/'
                  'STATUS_APP_sec213_20261122.md`（%d B／SHA256 `%s`）；'
                  '**原文一字未删、未改**。活文档本节只留本行。\n'
                  % (len(arch_213_text.encode('utf-8')), sha213))
        ed.replace(s2 + 1, e2, [ptr213])
        new_text = ''.join(ed.lines)
        new_bytes = new_text.encode('utf-8')
        log('归档 §213：%d B ⇒ %s'
            % (len(arch_213_text.encode('utf-8')), ARCH_213))

    # ── 写前复核（**逆向撤销编辑** ⇒ 逐字节还原）────────────────
    checks = []

    def chk(name, cond, detail=''):
        checks.append((name, bool(cond), str(detail)[:300]))
        return cond

    undo_bytes = ''.join(ed.undo_all()).encode('utf-8')
    chk('还原式：反推回原件逐字节相同', undo_bytes == orig,
        'undo %d B vs orig %d B' % (len(undo_bytes), len(orig)))
    chk('字节 ≤ %d' % LIMIT_BYTES, len(new_bytes) <= LIMIT_BYTES,
        '%d B' % len(new_bytes))
    chk('行数不增', len(ed.lines) <= len(lines),
        '%d vs %d' % (len(ed.lines), len(lines)))
    chk('CRLF 数不变（LF-only）',
        orig.count(b'\r\n') == new_bytes.count(b'\r\n'),
        '%d vs %d' % (orig.count(b'\r\n'), new_bytes.count(b'\r\n')))
    chk('UTF-8 往返一致',
        new_bytes.decode('utf-8').encode('utf-8') == new_bytes, '')
    chk('新条目在段首', NEW_ENTRY in ed.lines[s + 1], '')
    chk('原 APP-119 条目已不在活文档', first not in new_text, '')
    chk('§220 标题仍在', '## §220' in new_text, '')
    chk('last_ack 仍 = APP-120', new_text.count('last_ack: APP-120') == 1, '')
    if arch_213_text:
        chk('§213 标题行保留',
            any(l.startswith('## §213 ') for l in ed.lines), '')

    for n, ok, d in checks:
        log('  [%s] %s%s' % ('PASS' if ok else 'FAIL', n,
                             '' if ok else ' :: ' + d))
    if not all(ok for _n, ok, _d in checks):
        log('!! 写前复核 FAIL ⇒ **不落盘**（源文件零改动）')
        return 1

    if not args.apply:
        log('（dry-run：未写任何文件）')
        return 0

    # ── 落盘（归档件 write-once ＋ STATUS 原子替换）──────────────
    for path, text in ((ARCH_RU, arch_ru_text), (ARCH_213, arch_213_text)):
        if not text:
            continue
        tmp_a = path + '.tmp'
        with open(tmp_a, 'wb') as f:
            f.write(text.encode('utf-8'))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_a, path)
        log('归档件已写：%s（%d B）' % (path, os.path.getsize(path)))

    tmp = STATUS + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(new_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)
    log('STATUS 已写：%d B（原 %d B）' % (len(new_bytes), len(orig)))

    # ── 写后独立复核 ────────────────────────────────────────────
    after = open(STATUS, 'rb').read()
    at = after.decode('utf-8')
    post = [
        ('字节 ≤ %d' % LIMIT_BYTES, len(after) <= LIMIT_BYTES, len(after)),
        ('last_ack = APP-120', at.count('last_ack: APP-120') == 1, ''),
        ('§220 存在', '## §220' in at, ''),
        ('新条目在段首',
         at.find('2026-11-22 16:54') < at.find('2026-11-21 04:34:48'), ''),
        ('归档指针存在', 'STATUS_APP_recent_updates_20261122.md' in at, ''),
        ('归档件逐字节 == 被替换的原文',
         open(ARCH_RU, 'rb').read().decode('utf-8') == arch_ru_text, ''),
        ('CRLF 数不变', orig.count(b'\r\n') == after.count(b'\r\n'), ''),
    ]
    if arch_213_text:
        post.append(('§213 归档件逐字节 == 原文',
                     open(ARCH_213, 'rb').read().decode('utf-8') == arch_213_text, ''))
        post.append(('§213 指针存在', 'STATUS_APP_sec213_20261122.md' in at, ''))
    ok_all = True
    for n, ok, d in post:
        log('  [%s] %s%s' % ('PASS' if ok else 'FAIL', n,
                             '' if ok else ' :: %s' % d))
        ok_all = ok_all and ok
    log('写后复核：%s' % ('ALL PASS' if ok_all else 'FAIL'))
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
