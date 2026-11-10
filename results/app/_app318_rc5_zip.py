#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app318_rc5_zip.py —— **MiniMVP v1.0-rc5 打 zip**（APP-095 / APP-096）。

## 口径（与 rc4 的 `_app302` **完全同一套**）

* 工具：**7-Zip**（`7z a -tzip -mx=5 -mmt=on`）
* 清单：**`pkg_exclude`（单一数据源）** ⇒ 与 rc4 zip 同口径
* 顶层目录：`Confucius4_LiveCaption_MiniMVP_v1.0-rc5/`
* 输出：`%USERPROFILE%\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc5_perftest.zip`
  ⇒ **新文件名**，rc3/rc4 的三个 zip **一字节不动**。

## 🔴🔴🔳 APP-096 §2/§3b 的新增闸门

* zip 清单里 **R2T2 的 ASR IR 出现次数 = 0**
  （`encoder-int8` / `decoder-gpu-int8` / `encoder-fp16` / `decoder-npu-int8` /
  `embed_tokens_f16.npy`）
* zip 清单里 **`decoder-npu-int4` 出现次数 = 0**（APP-095 1a）
* zip 清单里 **0.6B 物料齐全**（`asr06b-encoder-fp16` / `asr06b-decoder-int8` /
  `embed_tokens_06b_f16.npy` / `asr06b-tokenizer`）
* **README 的体积/文件数 == 清单实测值**（APP-073(c) 同类缺陷）
* **rc3 / rc4 的 zip SHA256 前后逐字未变**

## 用法

```
.venv/Scripts/python.exe results/app/_app318_rc5_zip.py --dry-run
.venv/Scripts/python.exe results/app/_app318_rc5_zip.py --run
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

import pkg_exclude as PE  # noqa: E402

HOME = os.path.expanduser('~')
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5'
PKG = os.path.join(HOME, PKG_NAME)
OUT_DIR = os.path.join(HOME, 'shared', 'minimvp')
ZIP = os.path.join(OUT_DIR, PKG_NAME + '_perftest.zip')
SEVENZ = r'C:\Program Files\7-Zip\7z.exe'
REPORT = os.path.join(HERE, 'app318_rc5_zip_evidence.json')
LISTFILE = os.path.join(HERE, '_app318_zip_listfile.txt')

#: 🔴 rc3 / rc4 的 zip（本轮**一字节不许动**⇒ 事后复核 SHA 前后一致）
PRIOR_ZIPS = (
    os.path.join(OUT_DIR, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest.zip'),
    os.path.join(OUT_DIR,
                 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip'),
    os.path.join(OUT_DIR, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip'),
)

#: 🔴 **必须为 0 次**的条目（R2T2 ASR IR + INT4 decoder）
FORBIDDEN = (
    'models/encoder-int8/',
    'models/decoder-gpu-int8/',
    'models/encoder-fp16/',
    'models/decoder-npu-int8/',
    'models/decoder-npu-int4/',
    'models/embed_tokens_f16.npy',
)

#: 🔴 **必须存在**的 0.6B 物料
REQUIRED_06B = (
    'models/asr06b-encoder-fp16/ov-encoder-06b-fp16-static.xml',
    'models/asr06b-encoder-fp16/ov-encoder-06b-fp16-static.bin',
    'models/asr06b-decoder-int8/openvino_model.xml',
    'models/asr06b-decoder-int8/openvino_model.bin',
    'models/embed_tokens_06b_f16.npy',
    'models/asr06b-tokenizer/tokenizer_config.json',
    'models/asr06b-tokenizer/vocab.json',
    'models/asr06b-tokenizer/merges.txt',
    'models/asr06b-tokenizer/preprocessor_config.json',
)


def sha256_file(path, chunk=4 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def crc32_file(path):
    crc = 0
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            crc = zlib.crc32(b, crc)
    return crc & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    args = ap.parse_args()
    if not (args.dry_run or args.run):
        ap.error('必须给 --dry-run 或 --run')

    out = {'script': os.path.basename(__file__),
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': PKG, 'zip': ZIP,
           'mode': 'run' if args.run else 'dry-run'}

    def fail(reason):
        out['verdict'] = 'FAIL'
        out['reason'] = reason
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('🔴 %s' % reason)
        return 1

    # ── 闸门① 源目录 ────────────────────────────────────────────
    if not os.path.isdir(PKG):
        return fail('源包目录不存在：%s' % PKG)
    # ── 闸门② 目标 zip 不存在（不覆盖，APP-055）──────────────────
    if os.path.exists(ZIP):
        return fail('目标 zip 已存在（拒绝覆盖，APP-055）：%s' % ZIP)
    # ── 闸门③ 前代 zip 在（事后复核它们未被碰）──────────────────
    prior_before = {}
    for z in PRIOR_ZIPS:
        if not os.path.exists(z):
            return fail('前代 zip 不存在：%s' % z)
        prior_before[os.path.basename(z)] = sha256_file(z)
    out['prior_zips_before'] = prior_before

    # ── 清单（pkg_exclude 单一数据源）────────────────────────────
    files = list(PE.iter_package_files(PKG))
    rels = [r for r, _s in files]
    total_bytes = sum(s for _r, s in files)
    out['n_entries'] = len(files)
    out['total_bytes'] = total_bytes
    out['total_gb'] = round(total_bytes / 2 ** 30, 3)

    # ── 闸门④ 清单洁净 ───────────────────────────────────────────
    bad = [r for r in rels if '\ufffd' in r or r.startswith('/')
           or ':' in r[:3] or r.endswith('.bak')]
    if bad:
        return fail('清单含非法条目：%s' % bad[:5])

    # ── 闸门⑤ README 的体积/文件数 == 实测（APP-073(c) 同类缺陷）──
    readme = os.path.join(PKG, 'README_perftest.txt')
    txt = open(readme, encoding='utf-8', errors='replace').read()
    import re
    m = re.search(r'解压后\s*\*\*约\s*([\d.]+)\s*GB\*\*（(\d+)\s*个文件）', txt)
    if not m:
        return fail('README_perftest 里找不到「解压后 约 X GB（N 个文件）」')
    r_gb, r_n = float(m.group(1)), int(m.group(2))
    if abs(r_gb - out['total_gb']) > 0.15:
        return fail('README 体积 %.1f GB 与实测 %.3f GB 不符' % (r_gb, out['total_gb']))
    if r_n != len(files):
        return fail('README 文件数 %d 与清单 %d 不符' % (r_n, len(files)))
    out['readme_numbers_match'] = True

    # ── 闸门⑥ R2T2 / INT4 计数必须为 0 ───────────────────────────
    counts = {}
    for pat in FORBIDDEN:
        counts[pat] = sum(1 for r in rels if pat in r)
    out['forbidden_counts'] = counts
    nz = {k: v for k, v in counts.items() if v}
    if nz:
        return fail('zip 清单里仍有应删除的条目：%s' % nz)

    # ── 闸门⑦ 0.6B 物料齐全 ─────────────────────────────────────
    prefix = PKG_NAME + '/'
    missing = [r for r in REQUIRED_06B if not any(
        x.endswith(r) or x == prefix + r for x in rels)]
    if missing:
        return fail('0.6B 物料缺失：%s' % missing)
    out['required_06b_present'] = True

    # ── 闸门⑧ 无预编译 NPU blob（目标机现编）─────────────────────
    blobs = [r for r in rels if r.endswith('.blob')]
    out['n_blob'] = len(blobs)
    if blobs:
        return fail('包内含预编译 blob：%s' % blobs[:5])

    # ── 写清单文件（给 7z 用）───────────────────────────────────
    # 🔴🔴🔳 **口径照抄 rc4 的 `_app302`**：
    #    清单里写的是**相对路径 + 顶层目录前缀**（`PKG_NAME/xxx`）
    #    ⇒ 7z 的工作目录 = **包的父目录** ⇒ zip 条目名自带顶层目录。
    #    ⚠️ 第一版写了**绝对路径** ⇒ ①顶层目录名丢失
    #    ②7z 报「Duplicate filename on disk」（`.f2py_f2cmap`）
    #       —— 同一文件被重复收录（绝对路径 + `-i` 过滤器语义不匹配）。
    with open(LISTFILE, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join('%s/%s' % (PKG_NAME, r.replace('\\', '/'))
                          for r, _s in files) + '\n')

    if args.dry_run:
        out['verdict'] = 'DRY_RUN_OK'
        print(json.dumps({k: out[k] for k in
                          ('n_entries', 'total_gb', 'forbidden_counts',
                           'readme_numbers_match', 'n_blob')},
                         ensure_ascii=False, indent=1))
        print('[dry-run] 未打包')
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 0

    # ── 打包 ─────────────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    cmd = [SEVENZ, 'a', '-tzip', '-mx=5', '-mmt=on', '-bso0', '-bsp0',
           ZIP, '-i@' + LISTFILE]
    print('[zip] %s' % ' '.join(cmd))
    # 🔴 工作目录 = **包的父目录**（清单是相对路径 + 顶层目录前缀）
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=HOME)
    pack_s = round(time.time() - t0, 1)
    out['pack_s'] = pack_s
    out['zip_rc'] = p.returncode
    if p.returncode != 0:
        out['zip_stderr'] = p.stderr[-2000:]
        return fail('7z 退出码 %d' % p.returncode)

    out['zip_bytes'] = os.path.getsize(ZIP)
    out['zip_sha256'] = sha256_file(ZIP)
    out['zip_mtime'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                     time.localtime(os.path.getmtime(ZIP)))

    # ── 逐条 CRC32 比对 ─────────────────────────────────────────
    n_ok = 0
    mismatch = []
    missing_in_zip = []
    with zipfile.ZipFile(ZIP, 'r') as zf:
        names = set(zf.namelist())
        for r, _s in files:
            # 🔴 zip 条目名用**正斜杠**（rc4 zip 实测：`has backslash: 0`）
            entry = prefix + r.replace('\\', '/')
            if entry not in names:
                missing_in_zip.append(entry)
                continue
            src = os.path.join(PKG, r)
            if zf.getinfo(entry).CRC == crc32_file(src):
                n_ok += 1
            else:
                mismatch.append(entry)
    out['crc32_ok'] = n_ok
    out['crc32_mismatch'] = mismatch[:10]
    out['n_missing_in_zip'] = len(missing_in_zip)
    out['missing_in_zip'] = missing_in_zip[:10]
    if mismatch or missing_in_zip:
        return fail('CRC32 不符 %d / 缺失 %d' % (len(mismatch),
                                                len(missing_in_zip)))

    # ── 前代 zip SHA 复核 ────────────────────────────────────────
    prior_after = {os.path.basename(z): sha256_file(z) for z in PRIOR_ZIPS}
    out['prior_zips_after'] = prior_after
    out['prior_zips_unchanged'] = (prior_before == prior_after)
    if not out['prior_zips_unchanged']:
        return fail('前代 zip 的 SHA 变了！')

    out['verdict'] = 'PASS'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('zip：%s' % ZIP)
    print('大小 %d B / SHA256 %s / 条目 %d（CRC32 全对 %d）'
          % (out['zip_bytes'], out['zip_sha256'], out['n_entries'], n_ok))
    print('前代 zip 未动：%s' % out['prior_zips_unchanged'])
    print('证据：%s' % REPORT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
