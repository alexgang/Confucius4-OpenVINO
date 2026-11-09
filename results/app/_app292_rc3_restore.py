#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app292_rc3_restore.py —— **修复 rc3 被硬链接污染的 3 个文件**。

## 事故经过（本脚本存在的原因）

`_app291_build_minimvp_rc4.py` 用 `shutil.copytree(..., copy_function=os.link)`
把 **rc3 目录**复制成 rc4 ⇒ **rc4 的每个文件与 rc3 共享 inode**。
随后「把 rc4 的版本号从 rc3 改成 rc4」用**原地写**（`open(p,'w')`）
⇒ **写穿硬链接 ⇒ rc3 的同名文件被一起改了**。

实测（inode 核对）：
    NOTICE      rc3 ino 2533274791881735 == rc4 ino 2533274791881735  ← 同 inode
    README_zh.md rc3 ino 5348024558336868 == rc4 ino 5348024558336868  ← 同 inode
    README_en.md rc3 ino 2533274792475657 == rc4 ino 2533274792475657  ← 同 inode

⇒ rc3 的这 3 个文件被改成「rc4」字样 ⇒ **违反「不改已交付的 rc3」**。

## 修复方式（**用已交付 zip 里的权威字节**）

权威源 = `shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip`
里的同名条目 ⇒ **就是 rc3 交付时的字节**（zip 是不可变交付物）。

步骤：
1. 读 zip 内的 3 个条目字节；
2. **先解除硬链接**（`os.unlink` 后重写 ⇒ rc3 拿到自己的 inode，
   **rc4 的副本不受影响**、仍保持 rc4 字样）；
3. 写回 rc3；
4. **复核**：rc3 三文件与 zip 逐字节相同；rc3/rc4 inode **不同**；
   rc4 三文件仍含 rc4 字样。

## 🔴 同时修 rc4 的构建器（根因）

`_app291` 的 `copy_tree` 改成：**先硬链接复制，随后对「要改写的文件」
解除链接再写**（`unlink` + 写新文件）⇒ 不会再写穿到 rc3。
（模型目录**不写**，保持硬链接省空间；只有文档需要改 ⇒ 只对文档断链。）

用法：
    .venv/Scripts/python.exe results/app/_app292_rc3_restore.py --dry-run
    .venv/Scripts/python.exe results/app/_app292_rc3_restore.py --run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
RC3 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
RC4 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
ZIP = os.path.join(HOME, 'shared', 'minimvp',
                   'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip')
EVID = os.path.join(HERE, 'app292_rc3_restore_evidence.json')

#: 🔴 被污染的 3 个文件（rc3 目录下的相对路径）
AFFECTED = ('NOTICE', 'README_zh.md', 'README_en.md')


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: str) -> str:
    with open(p, 'rb') as f:
        return sha_bytes(f.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    args = ap.parse_args()

    res = {'script': os.path.basename(__file__), 'zip': ZIP,
           'rc3': RC3, 'rc4': RC4, 'affected': list(AFFECTED),
           'dry_run': not args.run}
    if not os.path.isfile(ZIP):
        res['verdict'] = 'ZIP_MISSING'
        print('!! 权威 zip 不存在：%s' % ZIP)
        _write(res)
        return 2

    z = zipfile.ZipFile(ZIP)
    prefix = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3/'
    plan = []
    for rel in AFFECTED:
        nm = prefix + rel
        try:
            data = z.read(nm)
        except KeyError:
            print('!! zip 内无 %s' % nm)
            res['verdict'] = 'ZIP_ENTRY_MISSING'
            _write(res)
            return 2
        p3 = os.path.join(RC3, rel)
        p4 = os.path.join(RC4, rel)
        cur = open(p3, 'rb').read() if os.path.isfile(p3) else b''
        ino3 = os.stat(p3).st_ino if os.path.isfile(p3) else None
        ino4 = os.stat(p4).st_ino if os.path.isfile(p4) else None
        plan.append({
            'rel': rel,
            'zip_bytes': len(data), 'zip_sha256': sha_bytes(data),
            'rc3_now_bytes': len(cur), 'rc3_now_sha256': sha_bytes(cur),
            'rc3_matches_zip': (cur == data),
            'rc3_ino': ino3, 'rc4_ino': ino4,
            'shared_inode': (ino3 is not None and ino3 == ino4),
            'rc4_has_rc4_word': (b'rc4' in open(p4, 'rb').read())
            if os.path.isfile(p4) else None,
        })
    res['plan'] = plan
    print('== 受影响文件 ==')
    for p in plan:
        print('  %-16s rc3==zip? %-5s 共享inode? %-5s  rc4 含 rc4? %s'
              % (p['rel'], p['rc3_matches_zip'], p['shared_inode'],
                 p['rc4_has_rc4_word']), flush=True)

    if args.dry_run:
        res['verdict'] = 'DRY_RUN'
        _write(res)
        print(json.dumps({'verdict': 'DRY_RUN'}, ensure_ascii=False))
        return 0

    # ── 修复：断链 + 从 zip 权威字节重写 rc3 ──────────────────
    fixed = []
    for rel in AFFECTED:
        nm = prefix + rel
        data = z.read(nm)
        p3 = os.path.join(RC3, rel)
        p4 = os.path.join(RC4, rel)
        # ① rc4 侧：断链（让 rc4 保留自己的 inode 与 rc4 内容）
        if os.path.isfile(p4):
            tmp = p4 + '.app292.tmp'
            with open(p4, 'rb') as f:
                d4 = f.read()
            with open(tmp, 'wb') as f:
                f.write(d4)
            os.replace(tmp, p4)
        # ② rc3 侧：断链 + 写权威字节
        tmp3 = p3 + '.app292.tmp'
        with open(tmp3, 'wb') as f:
            f.write(data)
        os.replace(tmp3, p3)
        fixed.append(rel)
        print('✔ 已修复：%s' % rel, flush=True)

    # ── 复核 ─────────────────────────────────────────────────
    checks = []
    ok = True
    for rel in AFFECTED:
        p3 = os.path.join(RC3, rel)
        p4 = os.path.join(RC4, rel)
        zdata = z.read(prefix + rel)
        c3 = open(p3, 'rb').read()
        ino3 = os.stat(p3).st_ino
        ino4 = os.stat(p4).st_ino
        chk = {
            'rel': rel,
            'rc3_equals_zip': (c3 == zdata),
            'rc3_sha256': sha_bytes(c3),
            'rc4_sha256': sha_file(p4),
            'inode_differ': (ino3 != ino4),
            'rc3_has_rc3_word': (b'rc3' in c3),
            'rc4_has_rc4_word': (b'rc4' in open(p4, 'rb').read()),
        }
        chk['pass'] = (chk['rc3_equals_zip'] and chk['inode_differ']
                       and chk['rc3_has_rc3_word'] and chk['rc4_has_rc4_word'])
        ok = ok and chk['pass']
        checks.append(chk)
        print('  %-16s pass=%s  rc3==zip:%s inode分离:%s'
              % (rel, chk['pass'], chk['rc3_equals_zip'],
                 chk['inode_differ']), flush=True)

    res['fixed'] = fixed
    res['checks'] = checks
    res['verdict'] = 'RESTORED_OK' if ok else 'RESTORE_FAILED'
    _write(res)
    print('★ %s' % res['verdict'])
    return 0 if ok else 1


def _write(obj: dict) -> None:
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    raise SystemExit(main())
