#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""app136_s92_threeway_check.py —— §92 交付口径的**独立只读三方复核**。

## 为什么要有这个脚本（铁律）

「打包脚本自己说 PASS」**不等于**交付闭环。本脚本**独立**直读 zip 内字节，
把三方放在一起比：

    仓库 live_caption/<f>  ⇄  客户包 v1.6/app/<f>  ⇄  zip 内 <prefix>/app/<f>

## 判定口径

* **归一化行尾（LF）后再比 SHA256** ⇒ 仓库侧 CRLF vs 包侧 LF **不算差异**
  （差值字节数 == 行数 是这个特征）。
* 分母 = **实际参与比对的文件集合**（包内 `.py` 减去 `pkg_exclude` 排除项）。
* zip 侧用 `zipfile` 流式读取**单个条目**、**不整体解压**（11 GB 包不能进内存）。
* zip 完整性：`testzip()`（**只读**，不解压到磁盘）。

## 只读

本脚本**只读**：不写客户包、不写 zip、不删任何文件。
唯一写入 = 本目录下的 evidence JSON。
"""

from __future__ import annotations

import datetime
import hashlib
import json
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
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app136_s92_threeway_check_evidence.json')

#: 包内但**不参与交付**的文件（打包时排除项 / 探针脚本）
EXCLUDE = {'_probe_tts_cuda.py'}

#: §92 本轮改动的 3 个文件（必须单独列指纹）
S92_FILES = ('tts_worker.py', 'tts_service.py', 'live_caption_app.py')


def sha256_norm(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def sha256_file(path: str) -> str:
    return sha256_norm(open(path, 'rb').read())


def main() -> int:
    print('=' * 72)
    print('app136 —— §92 交付口径的独立只读三方复核（仓库 ⇄ 包目录 ⇄ zip）')
    print('=' * 72)

    ev = {
        'script': os.path.basename(__file__),
        'zip': ZIP,
        'prefix': PREFIX,
        'repo_app': REPO_APP,
        'pkg_app': PKG_APP,
    }

    # ── 1. zip 文件级指纹 ──
    zs = os.stat(ZIP)
    zbytes = open(ZIP, 'rb').read()
    ev['zip_file'] = {
        'bytes': len(zbytes),
        'mtime': datetime.datetime.fromtimestamp(zs.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'sha256': hashlib.sha256(zbytes).hexdigest(),
    }
    print('zip: %d B / mtime %s' % (ev['zip_file']['bytes'], ev['zip_file']['mtime']))
    print('zip SHA256 = %s' % ev['zip_file']['sha256'])

    # ── 2. 参与比对的文件集合 ──
    names = sorted(f for f in os.listdir(PKG_APP)
                   if f.endswith('.py') and f not in EXCLUDE)
    ev['n_compare'] = len(names)
    ev['exclude'] = sorted(EXCLUDE)
    print('参与比对的包内 .py：%d 个（已排除 %d 个排除项）' % (len(names), len(EXCLUDE)))

    # ── 3. 打开 zip（只读）──
    zf = zipfile.ZipFile(ZIP, 'r')
    try:
        infos = zf.infolist()
        ev['zip_entries'] = len(infos)

        mismatches = []
        repo_match = 0
        pkg_match = 0
        per_file = []

        for n in names:
            rp = os.path.join(REPO_APP, n)
            pp = os.path.join(PKG_APP, n)
            if not os.path.exists(rp):
                mismatches.append((n, '仓库内无此文件'))
                continue
            r_sha = sha256_file(rp)
            p_sha = sha256_file(pp)

            member = '%s/app/%s' % (PREFIX, n)
            z_sha = None
            try:
                z_sha = sha256_norm(zf.read(member))
            except KeyError:
                mismatches.append((n, 'zip 内无此条目'))
                continue

            r_ok = (r_sha == p_sha)
            p_ok = (p_sha == z_sha)
            if r_ok:
                repo_match += 1
            else:
                mismatches.append((n, '仓库≠包目录'))
            if p_ok:
                pkg_match += 1
            else:
                mismatches.append((n, '包目录≠zip'))
            per_file.append({
                'name': n,
                'repo_sha16': r_sha[:16],
                'pkg_sha16': p_sha[:16],
                'zip_sha16': z_sha[:16],
                'repo_eq_pkg': r_ok,
                'pkg_eq_zip': p_ok,
            })

        ev['n_repo_eq_pkg'] = repo_match
        ev['n_pkg_eq_zip'] = pkg_match
        ev['mismatches'] = [{'name': n, 'why': w} for n, w in mismatches]
        ev['per_file'] = per_file

        print()
        print('--- 三方比对结果 ---')
        print('仓库 ⇄ 包目录 一致：%d / %d' % (repo_match, len(names)))
        print('包目录 ⇄ zip   一致：%d / %d' % (pkg_match, len(names)))
        if mismatches:
            print('❌ 不一致明细：')
            for n, why in mismatches:
                print('   %s —— %s' % (n, why))
        else:
            print('✅ 全部逐字一致（归一化 LF）')

        # ── 4. §92 本轮 3 个文件的精确指纹（仓库 ⇄ 包 ⇄ zip）──
        print()
        print('--- §92 本轮改动的 3 个文件（三方指纹）---')
        s92 = []
        for n in S92_FILES:
            rp = os.path.join(REPO_APP, n)
            member = '%s/app/%s' % (PREFIX, n)
            r_sha = sha256_file(rp)
            p_sha = sha256_file(os.path.join(PKG_APP, n))
            z_sha = sha256_norm(zf.read(member))
            same = (r_sha == p_sha == z_sha)
            s92.append({
                'name': n,
                'repo_sha256': r_sha,
                'pkg_sha256': p_sha,
                'zip_sha256': z_sha,
                'all_equal': same,
                'repo_bytes': os.path.getsize(rp),
                'pkg_bytes': os.path.getsize(os.path.join(PKG_APP, n)),
            })
            print('  %-20s 仓库=%s 包=%s zip=%s ⇒ %s'
                  % (n, r_sha[:16], p_sha[:16], z_sha[:16],
                     'MATCH' if same else 'DIFF'))
        ev['s92_files'] = s92

        # ── 5. zip 完整性（只读 testzip）──
        print()
        print('--- zip 完整性（testzip，只读）---')
        bad = zf.testzip()
        ev['testzip_bad'] = bad
        print('testzip() = %s' % (bad if bad else 'OK（无损坏条目）'))

        ok = (not mismatches
              and repo_match == len(names)
              and pkg_match == len(names)
              and bad is None
              and all(x['all_equal'] for x in s92))
        ev['verdict'] = 'PASS' if ok else 'FAIL'
        print()
        print('结论：%s' % ('PASS（三方全部逐字一致 + zip 完整）' if ok else 'FAIL'))

        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        print('evidence → %s' % OUT)
        return 0 if ok else 1
    finally:
        zf.close()


if __name__ == '__main__':
    sys.exit(main())
