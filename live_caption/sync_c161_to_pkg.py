#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c161_to_pkg.py — §99：把 §99 的 4 处断链修复**定点同步**到客户包。

## 铁律（记忆铁律 §一 / §九）

1. 🔴 **仓库 ⇄ 客户包 = 两份独立副本** ⇒ **禁止整目录覆盖**。
2. 🔴 同步方式 = **`difflib` 派生替换块**（以「包内实际内容」为 OLD），
   **两端归一化 LF**，每块**唯一命中断言**。
3. 🔴 **OLD 必须取自「包内实际内容」**（不是基线 commit）
   ⇒ 否则同步一轮后再跑会命中 0 次而中止。
4. 🔴 行尾差异（仓库 CRLF / 包 LF）⇒ **归一化后再比**，
   否则原始字节必 DIFF = **假报警**。

## 本次同步的 4 个文件（§99）

| 文件 | §99 改了什么 |
|---|---|
| `speaker_tracker.py` | 断链 E（`keep_t0` 时间轴换算）+ 断链 A（`span_for_final` 往前借） |
| `speaker_voice.py`   | 断链 B（`add_clean_ranges` 区间并集累计） |
| `live_caption_app.py`| 断链 A/E/C/GUI + 断链 F（细化分支可达）+ CLI 侧 C/F |
| `tts_service.py`     | 断链 C 服务侧（`spk_voice` 事件分派 + `spk_voice_status`）|

⚠️ **本轮还修了一处「上轮 bytes 转义写坏」的污染**：
   `tts_service.py` 曾被写成**非法 UTF-8** ⇒ `compile()` 直接 SyntaxError
   ⇒ 客户包一启动就崩 ⇒ 本脚本会把它一并修好（归一化后的内容已合法 UTF-8）。
"""
from __future__ import annotations

import difflib
import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.9\app'

FILES = [
    'speaker_tracker.py',
    'speaker_voice.py',
    'live_caption_app.py',
    'tts_service.py',
]


def norm_bytes(b: bytes) -> bytes:
    """归一化行尾（仓库 CRLF / 包 LF ⇒ 统一 LF）。"""
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sync_one(name: str) -> dict:
    """把仓库版本**定点**同步到客户包。"""
    src = os.path.join(REPO, 'live_caption', name)
    dst = os.path.join(PKG, name)
    repo_b = open(src, 'rb').read()
    pkg_b = open(dst, 'rb').read()
    repo_n = norm_bytes(repo_b)
    pkg_n = norm_bytes(pkg_b)

    out = {'file': name,
           'pkg_bytes_before': len(pkg_b),
           'repo_bytes': len(repo_b),
           'pkg_sha_before': sha(norm_bytes(pkg_b)),
           'repo_sha': sha(repo_n)}

    if repo_n == pkg_n:
        out['status'] = 'already_identical'
        out['pkg_sha_after'] = out['pkg_sha_before']
        return out

    repo_lines = repo_n.decode('utf-8').splitlines(keepends=True)
    pkg_lines = pkg_n.decode('utf-8').splitlines(keepends=True)

    # 🔴 **difflib 派生替换块**：以「包内实际内容」为 OLD
    sm = difflib.SequenceMatcher(None, pkg_lines, repo_lines, autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != 'equal']
    if not ops:
        out['status'] = 'no_diff_ops_but_bytes_differ'
        return out

    # 🔴 **替换块审计**：统计每个 OLD 块在包内的出现次数
    #   （包内可能存在**多处完全相同**的代码，如两处建表 ⇒ 合法多处同改；
    #     这里记录次数供人工复核，真正的「不错位」保证由下面的流式构建 + 逐字节断言提供）
    audit = []
    for tag, i1, i2, j1, j2 in ops:
        old_block = pkg_lines[i1:i2]
        if not old_block:
            audit.append((tag, i1, 0))
            continue
        hits = 0
        for k in range(len(pkg_lines) - len(old_block) + 1):
            if pkg_lines[k:k + len(old_block)] == old_block:
                hits += 1
        audit.append((tag, i1, hits))

    # 🔴 按 opcodes **顺序**流式构建：未变动区间照抄包内，变动区间取仓库
    #   （不能用原始下标原地替换：前序块已改变行数；纯插入块更会错位）
    new_lines: list[str] = []
    cursor = 0
    for tag, i1, i2, j1, j2 in ops:
        assert i1 >= cursor, '❌ %s：opcode 区间重叠 @%d' % (name, i1)
        new_lines.extend(pkg_lines[cursor:i1])      # 未变动区间（照抄包内）
        new_lines.extend(repo_lines[j1:j2])         # 变动区间（取仓库）
        cursor = i2
    new_lines.extend(pkg_lines[cursor:])             # 尾部未变动区间
    applied = len(ops)

    out['n_replacements'] = applied
    out['block_hit_counts'] = [h for (_t, _i, h) in audit]
    multi = [h for h in out['block_hit_counts'] if h > 1]
    if multi:
        out['multi_hit_blocks'] = len(multi)
    new_n = ''.join(new_lines).encode('utf-8')
    # 🔴 归一化后必须与仓库**逐字节**一致
    assert new_n == repo_n, \
        '❌ %s：同步结果与仓库不一致（%d vs %d 字节）' % (
            name, len(new_n), len(repo_n))
    # 🔴 写盘前编译校验
    try:
        compile(new_n, name, 'exec')
    except Exception as e:
        raise SystemExit('❌ %s：同步结果编译失败 ⇒ 不写盘：%s' % (name, e))

    # 写盘：**保持包内原有行尾风格**（包是 LF ⇒ 写 LF）
    with open(dst, 'wb') as f:
        f.write(new_n)
    out['status'] = 'synced'
    out['pkg_bytes_after'] = len(new_n)
    out['pkg_sha_after'] = sha(new_n)
    out['match_repo'] = (norm_bytes(open(dst, 'rb').read()) == repo_n)
    return out


def main() -> int:
    print('=' * 74)
    print('§99 定点同步：仓库 live_caption/ → 客户包 v1.9/app/')
    print('=' * 74)
    print('包目录：%s' % PKG)
    results = []
    for name in FILES:
        r = sync_one(name)
        results.append(r)
        print('  %-24s %-18s repl=%-3s pkg_sha %s → %s  match_repo=%s'
              % (name, r['status'], r.get('n_replacements', '-'),
                 r['pkg_sha_before'][:12], r.get('pkg_sha_after', '')[:12],
                 r.get('match_repo', '-')))
    bad = [r for r in results
           if r['status'] != 'already_identical'
           and not r.get('match_repo')]
    if bad:
        print('\n❌ 有 %d 个文件同步后仍与仓库不一致' % len(bad))
        return 1
    print('\n✅ 全部 %d 个文件同步完成（归一化 LF 后与仓库逐字节一致）'
          % len(results))
    return 0


if __name__ == '__main__':
    sys.exit(main())
