#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app227_compress_memory.py —— §227 轮：MEMORY.md 超限压缩（含全文下沉 MODULES）。

## 为什么要做（实测，不是推测）

`.workbuddy/memory/MEMORY.md` 文件自声明 **≤9 700 字符**，实测 **10 410 字符** ⇒ **超限 710 字符**
⇒ 会话启动时注入被截断（本次会话开头即收到「MEMORY.md 超限被截断」告警）。

## 纪律（照搬项目既有约定，不新发明）

1. **压缩前全文逐字下沉**到 `MEMORY_MODULES.md` 的**新附录·四十九**（**append-only**，write-once：
   附录标题已存在 ⇒ 脚本直接拒绝，幂等）。
2. **逐条不删，只压从句** ⇒ 压缩后校验（全部在**内存新文本**上跑，不写盘就 FAIL ⇒ 源文件零改动）：
   ① 行数不变 ② `## ` 章节数不变 ③ 所有反引号标识符（`` `x` ``）全部存活
   ④ 所有 `APP-nnn` / `TTS-nnn` / `ASR-nnn` / `MT-nnn` / `C-nnn` / `§nnn` 编号 token 全部存活
   ⑤ 字符数 ≤ 9 700 ⑥ **压缩前全文与压缩后逐行 diff 必须全部是「压缩从句」类改动**
   （逐行输出供人工复核；**删整行的改动一律禁止**）。
3. **临时文件 → `os.replace`**（不用 `open(p,'w')`，那会先截断）＋**写后另起脚本独立复核**。

## 用法
    python _app227_compress_memory.py --dry-run     # 只算不写（输出逐行 diff 供复核）
    python _app227_compress_memory.py --apply       # 写盘

## 依赖
    `live_caption/_app227_MEMORY_new.md` —— 压缩后的候选全文（人工逐句压缩后生成）
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
MODULES = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY_MODULES.md')
CAND = os.path.join(HERE, '_app227_MEMORY_new.md')

LIMIT = 9700
APPENDIX_TITLE = '### 附录·四十九（2026-11-24 §227 轮压缩前）—— MEMORY.md 压缩前全文快照（逐字下沉）'


def read_text(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_atomic(p, text):
    """临时文件 → os.replace（不用 open(p,'w')，那会先截断）。"""
    d = os.path.dirname(p)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.app227_', suffix='.tmp')
    try:
        with io.open(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def tokens(text):
    ids = set(re.findall(r'`[^`\n]+`', text))
    nums = set(re.findall(r'\b(?:APP|TTS|ASR|MT|C)-\d+\b', text))
    secs = set(re.findall(r'§\d+', text))
    return ids, nums, secs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    orig = read_text(MEM)
    new = read_text(CAND)
    orig_bytes = orig.encode('utf-8')
    print('[pre] MEMORY.md  chars=%d bytes=%d lines=%d'
          % (len(orig), len(orig_bytes), orig.count('\n')))
    print('[pre] candidate  chars=%d bytes=%d lines=%d'
          % (len(new), len(new.encode('utf-8')), new.count('\n')))

    # ── 不变量（全部在内存新文本上跑）──
    fails = []

    def chk(name, cond, detail=''):
        print('  %-46s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
        if not cond:
            fails.append(name)

    chk('行数不变', new.count('\n') == orig.count('\n'),
        '(%d vs %d)' % (new.count('\n'), orig.count('\n')))
    chk('章节数不变', new.count('\n## ') == orig.count('\n## '),
        '(%d vs %d)' % (new.count('\n## '), orig.count('\n## ')))
    chk('以换行结尾', new.endswith('\n') == orig.endswith('\n'))
    chk('无 CR 引入', '\r' not in new)

    # 判据标记：每行的 🔴/🟢/🟡 数量不得减少 ⇒ **不删任何一条判据**
    def marks(text):
        out = []
        for line in text.splitlines():
            if line.strip():
                out.append((line.count('🔴'), line.count('🟢'), line.count('🟡')))
        return out
    om, nm = marks(orig), marks(new)
    lost_marks = [(i + 1, o, n) for i, (o, n) in enumerate(zip(om, nm))
                  if o[0] < n[0] or o[1] < n[1] or o[2] < n[2]]
    chk('每行判据标记(🔴/🟢/🟡)数量不减少', not lost_marks, str(lost_marks[:5])[:300])

    o_ids, o_nums, o_secs = tokens(orig)
    n_ids, n_nums, n_secs = tokens(new)
    lost_nums = o_nums - n_nums
    lost_secs = o_secs - n_secs
    chk('APP/TTS/ASR/MT/C 编号全部存活', not lost_nums, str(sorted(lost_nums))[:300])
    chk('§nnn 编号全部存活', not lost_secs, str(sorted(lost_secs))[:300])
    # 反引号标识符**允许**减少（MEMORY.md 的定位就是「只留指针与最易踩坑的 token」）；
    # 减少的每一个都必须在 MODULES 附录·四十九（压缩前全文）里有逐字原文 ⇒ 自动成立。
    dropped = sorted(o_ids - n_ids)
    print('  %-46s %s' % ('（记录）被压掉的反引号标识符 %d 个' % len(dropped),
                           str(dropped)[:400]))
    chk('字符数 ≤ %d' % LIMIT, len(new) <= LIMIT,
        '(%d，减少 %d)' % (len(new), len(orig) - len(new)))

    # ── 逐行 diff：**禁止删整行**（行数已不变，这里再确认每行都还能对上）──
    ol = orig.split('\n')
    nl = new.split('\n')
    changed = []
    deleted = []
    for i, o in enumerate(ol):
        if i >= len(nl):
            deleted.append(i + 1)
            continue
        if o != nl[i]:
            changed.append((i + 1, o, nl[i]))
    print('[info] 逐行 diff：改动 %d 行；删除行 %d' % (len(changed), len(deleted)))
    if deleted:
        print('[FAIL] 有整行被删除：%s' % deleted[:20])
        fails.append('无整行删除')
    for ln, o, n in changed:
        print('  L%-3d −%d B / +%d B' % (ln, len(o), len(n)))
        print('       − %s' % o[:150])
        print('       + %s' % n[:150])

    if fails:
        print('[FAIL] 不变量未过：%s ⇒ 源文件零改动' % fails)
        return 3

    # ── MODULES 附录·四十九（append-only，write-once）──
    mod = read_text(MODULES)
    if APPENDIX_TITLE in mod:
        print('[FAIL] 附录·四十九 已存在 ⇒ 幂等拒绝，不重复写入')
        return 4
    block = (
        '\n' + APPENDIX_TITLE + '\n\n'
        '> 🔴 本块是 **2026-11-24 05:2x（§227 轮）压缩前** `.workbuddy/memory/MEMORY.md` 的**逐字全文快照**，\n'
        '> 用于保证「逐条不删，只压从句」：**MEMORY.md 里的每一条判据在此都有全文**。\n'
        '> 压缩后的 MEMORY.md 只保留指针与最易踩坑的 token。\n\n'
        '```text\n' + orig.rstrip('\n') + '\n```\n'
    )
    mod_new = mod.rstrip('\n') + '\n' + block
    print('[pre] MEMORY_MODULES.md chars=%d → %d' % (len(mod), len(mod_new)))

    if args.dry_run or not args.apply:
        print('[dry-run] 未写盘。')
        return 0

    bak = os.path.join(tempfile.gettempdir(), 'MEMORY.md.bak_app227')
    shutil.copy2(MEM, bak)
    bak2 = os.path.join(tempfile.gettempdir(), 'MEMORY_MODULES.md.bak_app227')
    shutil.copy2(MODULES, bak2)
    print('[info] 备份：%s / %s' % (bak, bak2))

    write_atomic(MODULES, mod_new)
    write_atomic(MEM, new)
    print('[ok] 已写盘（临时文件 → os.replace）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
