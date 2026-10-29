#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""app132_s91_threeway_check.py —— §91 交付口径的**独立只读三方复核**。

## 为什么要有这个脚本（铁律）

「打包脚本自己说 PASS」**不等于**交付闭环。本脚本**独立**直读 zip 内字节，
把三方放在一起比：

    仓库 live_caption/<f>  ⇄  客户包 v1.6/app/<f>  ⇄  zip 内 <prefix>/app/<f>

## 判定口径

* **归一化行尾（LF）后再比 SHA256** ⇒ 仓库侧 CRLF vs 包侧 LF **不算差异**
  （差值字节数 == 行数 是这个特征）。
* 分母 = **实际参与比对的文件集合**（包内 `.py` 减去 `pkg_exclude` 排除项）。
* zip 侧用 `zipfile` 流式读取**单个条目**、**不整体解压**（11 GB 包不能进内存）。

## 只读

本脚本**只读**：不写客户包、不写 zip、不删任何文件。
"""

from __future__ import annotations

import hashlib
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_APP = os.path.join(REPO, 'live_caption')

# 🔴 §48 闸门：**不写死包路径/版本号** ⇒ 用 `pkg_paths`（单一数据源）自动发现。
sys.path.insert(0, REPO)
import pkg_paths  # noqa: E402

PKG = pkg_paths.discover_pkg_dir()
PKG_APP = pkg_paths.pkg_app_dir(PKG)
PREFIX = os.path.basename(PKG.rstrip('\\/'))
ZIP = PKG + '.zip'

#: 包内但**不参与交付**的文件（打包时排除项 / 探针脚本）
EXCLUDE = {'_probe_tts_cuda.py'}


def sha256_norm(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def main() -> int:
    print('=' * 72)
    print('app132 —— §91 交付口径的独立只读三方复核（仓库 ⇄ 包目录 ⇄ zip）')
    print('=' * 72)

    # ── 1. 列出参与比对的文件集合 ──
    names = sorted(f for f in os.listdir(PKG_APP)
                   if f.endswith('.py') and f not in EXCLUDE)
    print('参与比对的包内 .py：%d 个（已排除 %d 个排除项）'
          % (len(names), len(EXCLUDE)))

    # ── 2. 打开 zip（只读，不整体解压）──
    zf = zipfile.ZipFile(ZIP, 'r')
    try:
        infos = zf.infolist()
        total_entries = len(infos)
        print('zip 条目总数：%d' % total_entries)

        bad = zf.testzip()
        print('zip.testzip() = %s' % (bad if bad else 'None（无损坏条目）'))

        # EOCD 签名在尾 64 KB 内
        with open(ZIP, 'rb') as f:
            f.seek(max(0, os.path.getsize(ZIP) - 65536))
            tail = f.read()
        has_eocd = b'PK\x05\x06' in tail
        print('EOCD 签名在尾 64 KB 内：%s' % has_eocd)

        repo_match = pkg_match = zip_match = 0
        mismatches = []
        for n in names:
            rp = os.path.join(REPO_APP, n)
            pp = os.path.join(PKG_APP, n)
            if not os.path.exists(rp):
                mismatches.append((n, '仓库缺文件'))
                continue
            if not os.path.exists(pp):
                mismatches.append((n, '包目录缺文件'))
                continue

            r_bytes = open(rp, 'rb').read()
            p_bytes = open(pp, 'rb').read()
            r_sha = sha256_norm(r_bytes)
            p_sha = sha256_norm(p_bytes)
            if r_sha != p_sha:
                mismatches.append((n, '仓库≠包目录'))
                continue
            repo_match += 1
            pkg_match += 1

            member = '%s/app/%s' % (PREFIX, n)
            try:
                z_bytes = zf.read(member)
            except KeyError:
                mismatches.append((n, 'zip 内无此条目'))
                continue
            if sha256_norm(z_bytes) != p_sha:
                mismatches.append((n, '包目录≠zip'))
                continue
            zip_match += 1

        print()
        print('--- 三方比对结果 ---')
        print('仓库 ⇄ 包目录 一致：%d / %d' % (repo_match, len(names)))
        print('包目录 ⇄ zip   一致：%d / %d' % (zip_match, len(names)))
        if mismatches:
            print('❌ 不一致明细：')
            for n, why in mismatches:
                print('   %s —— %s' % (n, why))
        else:
            print('✅ 全部逐字一致（归一化 LF）')

        # ── 3. 关键交付文件的精确指纹 ──
        print()
        print('--- 关键文件在 zip 内的指纹 ---')
        for n in ('tts_cuda.py', 'tts_cuda_sidecar.py'):
            rp = os.path.join(REPO_APP, n)
            member = '%s/app/%s' % (PREFIX, n)
            r_sha = sha256_norm(open(rp, 'rb').read())
            z_sha = sha256_norm(zf.read(member))
            same = r_sha == z_sha
            print('  %-22s 仓库=%s zip=%s ⇒ %s'
                  % (n, r_sha[:16], z_sha[:16], 'MATCH' if same else 'DIFF'))

        ok = (not mismatches) and repo_match == len(names) and zip_match == len(names)
        print()
        print('结论：%s' % ('PASS（三方全部逐字一致）' if ok else 'FAIL'))
        return 0 if ok else 1
    finally:
        zf.close()


if __name__ == '__main__':
    sys.exit(main())
