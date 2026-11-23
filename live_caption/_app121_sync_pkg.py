#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §5：把 dev 树的修复**定点同步**到 v2.5 全集包 + MiniMVP v1.1.1 包。

## 为什么不用「整文件覆盖」
🔴 `live_caption/`（dev 树）与各客户包的 `app/` 是**两份独立副本**
   ⇒ 禁止整目录覆盖同步 ⇒ 只能用「精确字符串替换 + 唯一命中断言」。

## 本脚本的做法（与 `_app120_sync_v25.py` 同口径，更严一点）
1. 断言**目标文件 == 写前备份**（dev 树改动前的原件）⇒ 前提唯一；
2. 用 `difflib` 从 (原件 → 新 dev 文件) **自动导出**改写块（不手抄字符串）；
3. 每个块在目标文本里**唯一命中**才替换（0 次或 >1 次 ⇒ fail-closed）；
4. 写盘后断言**目标文件与新 dev 文件逐字节相同**；
5. 写前**还原式复核**（把结果反推回原件应逐字节相同）⇒ 通过才落盘；
6. 临时文件 → `os.replace`（**不截断原文件**）。

## 用法
```
python live_caption/_app121_sync_pkg.py --backup-dir <原件备份目录> [--apply]
```
（默认同步到 `Confucius4_LiveCaption_v2.5/app` 与
  `Confucius4_LiveCaption_MiniMVP_v1.1.1/app`）
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)

DEV = HERE

#: 本轮改动的文件（相对 dev 根 / 包内 app 根同名）
FILES = [
    'asr06b_stateful_backend.py',
    'live_caption_app.py',
]

#: 默认同步目标（包内 app 目录）
DEFAULT_TARGETS = [
    os.path.join(HOME, 'Confucius4_LiveCaption_v2.5', 'app'),
    os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1.1', 'app'),
]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def hunks(old: str, new: str, context: int = 4):
    """导出 (old_chunk, new_chunk) 改写块（**带上下文行**⇒ old_chunk 非空且唯一）。"""
    ol = old.splitlines(keepends=True)
    nl = new.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, ol, nl, autojunk=False)
    out = []
    for grp in sm.get_grouped_opcodes(context):
        i1, i2 = grp[0][1], grp[-1][2]
        j1, j2 = grp[0][3], grp[-1][4]
        o = ''.join(ol[i1:i2])
        n = ''.join(nl[j1:j2])
        if o == n:
            continue
        out.append((o, n, 'group'))
    return out


def apply_to(target_app: str, name: str, backup_bytes: bytes, new_bytes: bytes,
             apply: bool):
    tgt_path = os.path.join(target_app, name)
    res = {'file': name, 'target_app': target_app, 'target_path': tgt_path}
    if not os.path.isfile(tgt_path):
        res['FAIL'] = '目标文件不存在：%s' % tgt_path
        return res
    with open(tgt_path, 'rb') as f:
        tgt_bytes = f.read()
    res['sha_before'] = sha(tgt_bytes)
    res['bytes_before'] = len(tgt_bytes)

    if tgt_bytes != backup_bytes:
        res['FAIL'] = ('目标文件 != 写前备份（前提不唯一）：tgt=%s backup=%s'
                       % (sha(tgt_bytes)[:12], sha(backup_bytes)[:12]))
        return res
    res['precond_ok'] = True

    tgt_text = tgt_bytes.decode('utf-8')
    hs = hunks(backup_bytes.decode('utf-8'), new_bytes.decode('utf-8'))
    res['n_hunks'] = len(hs)
    cur = tgt_text
    for i, (o, n, tag) in enumerate(hs):
        cnt = cur.count(o)
        if cnt != 1:
            res['FAIL'] = ('块 %d（%s）命中 %d 次 ⇒ 唯一命中断言失败'
                           % (i, tag, cnt))
            return res
        cur = cur.replace(o, n, 1)
    new_text_bytes = cur.encode('utf-8')
    if new_text_bytes != new_bytes:
        res['FAIL'] = '同步结果 != 新 dev 文件 ⇒ 逐字节复核失败'
        return res

    # 🔴 还原式复核：按 hunks 反推回原件，应逐字节相同
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

    tmp = tgt_path + '.app121.tmp'
    with open(tmp, 'wb') as f:
        f.write(new_text_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, tgt_path)
    with open(tgt_path, 'rb') as f:
        after = f.read()
    if after != new_bytes:
        res['FAIL'] = '写后逐字节复核失败'
        return res
    res['written'] = True
    res['sha_after'] = sha(after)
    res['bytes_after'] = len(after)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backup-dir', required=True,
                    help='写前备份目录（含同名文件）')
    ap.add_argument('--target', action='append', default=None,
                    help='包内 app 目录（可多次；默认 v2.5 + MiniMVP v1.1.1）')
    ap.add_argument('--apply', action='store_true', help='真正写盘（默认 dry-run）')
    ap.add_argument('--out', default=os.path.join(
        REPO, 'results', 'app', 'app121_sync_pkg_evidence.json'))
    args = ap.parse_args()

    targets = args.target or DEFAULT_TARGETS
    all_ok = True
    rows = []
    for target in targets:
        print('=== 目标：%s ===' % target)
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
                print('  SKIP %s（与备份相同 ⇒ 无需同步）' % name)
                continue
            r = apply_to(target, name, backup_bytes, new_bytes, args.apply)
            rows.append(r)
            if 'FAIL' in r:
                all_ok = False
                print('  FAIL %s：%s' % (name, r['FAIL']))
            else:
                print('  PASS %s  hunks=%s  undo=%s  %s  sha_after=%s'
                      % (name, r.get('n_hunks'), r.get('undo_check'),
                         '已写盘' if r.get('written') else 'dry-run',
                         (r.get('sha_after') or '')[:16]))

    ev = {'script': '_app121_sync_pkg.py', 'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
          'applied': bool(args.apply), 'targets': targets, 'files': FILES,
          'rows': rows, 'all_ok': all_ok}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.out)
    print('证据 → %s' % args.out)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
