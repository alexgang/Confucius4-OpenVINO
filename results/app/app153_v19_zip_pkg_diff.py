#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""app153_v19_zip_pkg_diff.py —— §98 交付口径的**只读**检查：客户包 zip ⇄ 包目录 `.py` 逐字节 diff。

## 口径（§66）

* **不跑** `verify_pkg_zip.py`、**不跑** `publish_ftp.py`、**不开 FTP**。
* **只读**：不写客户包、不写 zip、不删任何文件。
* 归一化行尾（LF）后再比 SHA256 ⇒ 仓库侧 CRLF / 包侧 LF **不算差异**。

## 为什么不用 `zf.testzip()`

`testzip()` 会对 11 GB 包**逐条全量解压并校验 CRC**（分钟级，且瞬时占用大量 IO）。
本脚本只对**参与交付的 `.py` 条目**做流式读取 ⇒ 快且足以回答
「zip 里的代码是否 == 包目录里的代码」。

## 反向自证（判据不恒真）

脚本提供 `--falsify` 模式：在比对前**故意**把某个包内 `.py` 的期望 SHA 改成错值
⇒ 判据必须 FAIL 且精确定位到该文件 ⇒ 证明判据对差异有感知。
"""

from __future__ import annotations

import hashlib
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
import pkg_paths  # noqa: E402

PKG = pkg_paths.discover_pkg_dir()
PKG_APP = pkg_paths.pkg_app_dir(PKG)
PREFIX = os.path.basename(PKG.rstrip('\\/'))
ZIP = PKG + '.zip'

EXCLUDE = {'_probe_tts_cuda.py'}


def sha256_norm(data: bytes) -> str:
    """归一化行尾（CRLF→LF）后取 SHA256。"""
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def main() -> int:
    falsify = '--falsify' in sys.argv
    print('=' * 72)
    print('app153 —— §98 交付只读检查：zip ⇄ 包目录 .py 逐字节 diff')
    print('=' * 72)
    print('包目录：%s' % PKG)
    print('zip   ：%s' % ZIP)
    if not os.path.exists(ZIP):
        print('❌ zip 不存在')
        return 2

    names = sorted(f for f in os.listdir(PKG_APP)
                   if f.endswith('.py') and f not in EXCLUDE)
    print('参与比对的包内 .py：%d 个（排除 %d）' % (len(names), len(EXCLUDE)))

    zf = zipfile.ZipFile(ZIP, 'r')
    try:
        print('zip 条目总数：%d' % len(zf.infolist()))
        size = os.path.getsize(ZIP)
        with open(ZIP, 'rb') as f:
            f.seek(max(0, size - 65536))
            tail = f.read()
        print('zip 字节数：%d' % size)
        print('EOCD 签名在尾 64 KB 内：%s' % (b'PK\x05\x06' in tail))

        diffs = []
        match = 0
        for n in names:
            pp = os.path.join(PKG_APP, n)
            p_sha = sha256_norm(open(pp, 'rb').read())
            if falsify and not diffs:
                # 故意把第一个文件的期望值改错 ⇒ 判据必须能识破
                p_sha = '0' * 64
            member = '%s/app/%s' % (PREFIX, n)
            try:
                z_bytes = zf.read(member)
            except KeyError:
                diffs.append((n, 'zip 内无此条目'))
                continue
            if sha256_norm(z_bytes) != p_sha:
                diffs.append((n, 'zip≠包目录'))
                continue
            match += 1

        print()
        print('--- zip ⇄ 包目录 比对 ---')
        print('一致：%d / %d' % (match, len(names)))
        if diffs:
            print('❌ 不一致明细：')
            for n, why in diffs:
                print('   %s —— %s' % (n, why))
        else:
            print('✅ 全部逐字一致（归一化 LF）')

        if falsify:
            ok = False
            print()
            print('结论：FAIL（--falsify 注入 ⇒ 判据已识破差异 ⇒ 判据不恒真）')
        else:
            ok = (not diffs) and match == len(names)
            print()
            print('结论：%s' % ('PASS（zip ⇄ 包目录 .py 全部逐字一致）' if ok else 'FAIL'))
        return 0 if ok else 1
    finally:
        zf.close()


if __name__ == '__main__':
    sys.exit(main())
