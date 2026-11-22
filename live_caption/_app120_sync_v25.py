#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §0：把 dev 树的 ASR-065 补齐改动**定点同步**到 v2.5 全集包。

## 为什么不用「整文件覆盖」
🔴 `live_caption/`（dev 树）与 `Confucius4_LiveCaption_v2.5/app/`（客户包）
   是**两份独立副本** ⇒ 禁止整目录覆盖同步 ⇒ 只能用
   「精确字符串替换 + 唯一命中断言」。

## 本脚本的做法（更严）
1. 断言 **v2.5 目标文件 == 写前备份**（dev 树改动前的原件）⇒ 前提唯一；
2. 用 `difflib` 从 (原件 → 新 dev 文件) **自动导出**改写块（不手抄字符串）；
3. 每个块在 v2.5 文本里**唯一命中**才替换（0 次或 >1 次 ⇒ fail-closed）；
4. 写盘后断言 **v2.5 目标文件与新 dev 文件逐字节相同**；
5. 写前**还原式复核**（把 v2.5 文本反推回原件应逐字节相同）⇒ 通过才落盘。

## 用法
```
python live_caption/_app120_sync_v25.py --backup-dir <原件备份目录> --apply
```
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)

DEV = HERE
V25 = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5', 'app')

#: 本轮改动的文件（相对 dev 根 / 包内 app 根同名）
FILES = [
    'asr06b_stateful_backend.py',
    'live_caption_app.py',
]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def hunks(old: str, new: str, context: int = 4):
    """导出 (old_chunk, new_chunk) 改写块（**带上下文行**⇒ old_chunk 非空且唯一）。

    🔴 **必须带上下文**：纯 insert/delete 的块 old_chunk 为空串
    ⇒ ``text.count('')` == len(text)+1 ⇒ 唯一命中断言永远失败。
    ⇒ 用 `get_grouped_opcodes(n=context)` 把改动块与左右上下文合并。
    """
    ol = old.splitlines(keepends=True)
    nl = new.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, ol, nl, autojunk=False)
    out = []
    for grp in sm.get_grouped_opcodes(context):
        i1 = grp[0][1]
        i2 = grp[-1][2]
        j1 = grp[0][3]
        j2 = grp[-1][4]
        o = ''.join(ol[i1:i2])
        n = ''.join(nl[j1:j2])
        if o == n:
            continue
        out.append((o, n, 'group'))
    return out


def apply_to_v25(name: str, backup_bytes: bytes, new_bytes: bytes, apply: bool):
    v25_path = os.path.join(V25, name)
    with open(v25_path, 'rb') as f:
        v25_bytes = f.read()
    res = {'file': name, 'v25_path': v25_path}

    if v25_bytes != backup_bytes:
        res['FAIL'] = ('v2.5 目标文件 != 写前备份（前提不唯一）'
                       '：v25=%s backup=%s'
                       % (sha(v25_bytes)[:12], sha(backup_bytes)[:12]))
        return res
    res['precond_ok'] = True

    v25_text = v25_bytes.decode('utf-8')
    hs = hunks(backup_bytes.decode('utf-8'), new_bytes.decode('utf-8'))
    res['n_hunks'] = len(hs)
    cur = v25_text
    for i, (o, n, tag) in enumerate(hs):
        cnt = cur.count(o)
        if cnt != 1:
            res['FAIL'] = ('块 %d（%s）在 v2.5 中命中 %d 次 ⇒ 唯一命中断言失败'
                           % (i, tag, cnt))
            return res
        cur = cur.replace(o, n, 1)
    new_text_bytes = cur.encode('utf-8')

    if new_text_bytes != new_bytes:
        res['FAIL'] = '同步结果 != 新 dev 文件 ⇒ 逐字节复核失败'
        return res

    # 🔴 还原式复核：把结果按 hunks 反推回原件，应逐字节相同
    undo = new_text_bytes.decode('utf-8')
    for o, n, tag in reversed(hs):
        cnt = undo.count(n)
        if cnt != 1:
            res['FAIL'] = '还原式复核：块命中 %d 次 ⇒ FAIL' % cnt
            return res
        undo = undo.replace(n, o, 1)
    if undo.encode('utf-8') != backup_bytes:
        res['FAIL'] = '还原式复核：还原后 != 原件 ⇒ FAIL'
        return res
    res['undo_check'] = 'PASS'

    if not apply:
        res['dry_run'] = 'PASS（未写盘）'
        return res

    # 临时文件 → os.replace（不截断原文件）
    tmp = v25_path + '.app120.tmp'
    with open(tmp, 'wb') as f:
        f.write(new_text_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, v25_path)
    with open(v25_path, 'rb') as f:
        after = f.read()
    if after != new_bytes:
        res['FAIL'] = '写后逐字节复核失败'
        return res
    res['written'] = True
    res['sha_after'] = sha(after)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backup-dir', required=True,
                    help='写前备份目录（含同名文件）')
    ap.add_argument('--apply', action='store_true', help='真正写盘（默认 dry-run）')
    args = ap.parse_args()

    all_ok = True
    for name in FILES:
        dev_new = os.path.join(DEV, name)
        bak = os.path.join(args.backup_dir, name)
        if not os.path.isfile(bak):
            print('FAIL: 备份不存在 %s' % bak)
            return 2
        with open(dev_new, 'rb') as f:
            new_bytes = f.read()
        with open(bak, 'rb') as f:
            backup_bytes = f.read()
        if new_bytes == backup_bytes:
            print('SKIP %s（与备份相同 ⇒ 无需同步）' % name)
            continue
        r = apply_to_v25(name, backup_bytes, new_bytes, args.apply)
        if 'FAIL' in r:
            all_ok = False
            print('FAIL %s：%s' % (name, r['FAIL']))
        else:
            print('PASS %s  hunks=%s  undo=%s  %s'
                  % (name, r.get('n_hunks'), r.get('undo_check'),
                     r.get('written') and '已写盘' or 'dry-run'))
            if r.get('written'):
                print('     sha256=%s' % r['sha_after'])
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
