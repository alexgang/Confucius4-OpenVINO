# -*- coding: utf-8 -*-
r"""_app495 — **dev 树 ⇒ 客户包 app/ 的定点同步**（逐文件 + 逐字节复核）。

🔴 **不是整目录覆盖**（仓库 ⇄ 客户包 是两份独立副本）：
  * 一次只同步**点名的几个文件**；
  * 写入用 **LF 归一**（`core.autocrlf=true` ⇒ clone 是 CRLF、原字节是 LF）；
  * 写完**逐字节复核**（包内文件 == dev 文件（LF 归一后））；
  * 记录同步前后 SHA256 / 字节数 ⇒ 证据落盘。

用法：
    python results/app/_app495_sync_pkg_app.py <pkg> <file1> [file2 ...]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
DEV = os.path.join(REPO, 'live_caption')
REPORT = os.path.join(HERE, 'app495_sync_pkg_app.json')


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    if len(sys.argv) < 3:
        print('usage: app495 <pkg> <file...>')
        return 2
    pkg = os.path.abspath(sys.argv[1])
    names = sys.argv[2:]
    rows = []
    for name in names:
        src = os.path.join(DEV, name)
        dst = os.path.join(pkg, 'app', name)
        if not os.path.isfile(src):
            raise RuntimeError('dev 树缺文件：%s' % src)
        if not os.path.isfile(dst):
            raise RuntimeError('包内缺文件：%s' % dst)
        before = open(dst, 'rb').read()
        data = open(src, 'rb').read().replace(b'\r\n', b'\n')
        with open(dst, 'wb') as f:
            f.write(data)
        after = open(dst, 'rb').read()
        dev_norm = open(src, 'rb').read().replace(b'\r\n', b'\n')
        rows.append({
            'file': name,
            'dev_sha256': sha256_bytes(dev_norm),
            'pkg_sha256_before': sha256_bytes(before),
            'pkg_sha256_after': sha256_bytes(after),
            'pkg_bytes_before': len(before),
            'pkg_bytes_after': len(after),
            'changed': before != after,
            'byte_identical_to_dev': after == dev_norm,
            'bare_cr': after.count(b'\r'),
        })
    ev = {'pkg': pkg, 'rows': rows,
          'n_fail': sum(1 for r in rows
                        if not r['byte_identical_to_dev'] or r['bare_cr']),
          'n_pass': sum(1 for r in rows
                        if r['byte_identical_to_dev'] and not r['bare_cr'])}
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
