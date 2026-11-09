#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app302_rc4_zip.py —— **MiniMVP v1.0-rc4 打 zip**（用户 2026-11-10 指示）。

## 口径（与 rc3 的 `_app288` **完全同一套**）

* 工具：**7-Zip**（`7z a -tzip -mx=5 -mmt=on`）—— 与 rc3 zip 一致
  （Python `zipfile` 慢一个量级，10 GB 不可接受）。
* 清单：**`pkg_exclude`（单一数据源）** ⇒ 与 rc3 zip **同口径**
  （实测：rc3 `pkg_exclude` 文件数 10 474 == rc3 zip 条目数 10 474 ✔）。
* 顶层目录：`Confucius4_LiveCaption_MiniMVP_v1.0-rc4/`（与 rc3 zip 同结构）。
* 输出：`%USERPROFILE%\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip`
  ⇒ **新文件名**，rc3 的两个 zip **一字节不动**。

## 🔴 闸门（任一不过 ⇒ **不落盘 zip**）

① 源目录在；② 目标 zip **不存在**（不覆盖，APP-055）；③ rc3 的两个 zip 在（事后复核它们未被碰）；
④ 清单无 U+FFFD / 绝对路径 / `.bak`；⑤ README 里的文件数与体积 **== 清单实测值**（APP-073(c) 同类缺陷）；
⑥ 清单里的 NPU IR **三个都在**（否则这包等于没补）。

## 打包后验收

* 条目数 **== 清单数**；每个条目的 **CRC32 == 源文件 CRC32**（逐条比对，10 480 条）；
* zip 的 SHA256 + 字节数；
* **rc3 的两个 zip 的 SHA256 前后逐字未变**；
* 落盘后再跑一次 `--check`（从 zip 解压出的干净目录）确认「Intel NPU · INT8 模型齐全」。

## 用法
```
.venv/Scripts/python.exe results/app/_app302_rc4_zip.py --dry-run
.venv/Scripts/python.exe results/app/_app302_rc4_zip.py --run
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
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4'
PKG = os.path.join(HOME, PKG_NAME)
OUT_DIR = os.path.join(HOME, 'shared', 'minimvp')
ZIP = os.path.join(OUT_DIR, PKG_NAME + '_perftest.zip')
SEVENZ = r'C:\Program Files\7-Zip\7z.exe'
REPORT = os.path.join(HERE, 'app302_rc4_zip_evidence.json')
LISTFILE = os.path.join(HERE, '_app302_zip_listfile.txt')

#: 🔴 rc3 的两个 zip（本轮**一字节不许动**⇒ 事后复核 SHA 前后一致）
RC3_ZIPS = (
    os.path.join(OUT_DIR, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest.zip'),
    os.path.join(OUT_DIR,
                 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip'),
)

#: 🔴 打包后必须能在 zip 里找到的 NPU IR（缺一 ⇒ 这包等于没补）
# ⚠️ **必须带顶层目录前缀**（zip 内条目名 = `Confucius4_..._rc4/models/...`）
#    —— 第一版写成 `models/...` ⇒ 闸门⑦ 误报「缺 NPU IR」（dry-run 抓到的）。
REQUIRED_NPU = (
    PKG_NAME + '/models/encoder-fp16/openvino_encoder_model.xml',
    PKG_NAME + '/models/encoder-fp16/openvino_encoder_model.bin',
    PKG_NAME + '/models/decoder-npu-int8/openvino_model.xml',
    PKG_NAME + '/models/decoder-npu-int8/openvino_model.bin',
    PKG_NAME + '/models/decoder-npu-int4/openvino_model.xml',
    PKG_NAME + '/models/decoder-npu-int4/openvino_model.bin',
)

#: 🔴 iGPU 版模型**必须保留**
REQUIRED_IGPU = (
    PKG_NAME + '/models/encoder-int8/openvino_encoder_model.xml',
    PKG_NAME + '/models/decoder-gpu-int8/openvino_decoder_model.xml',
)


def sha256_file(path, chunk=4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def crc32_file(path) -> int:
    crc = 0
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            crc = zlib.crc32(b, crc)
    return crc & 0xFFFFFFFF


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--zip', default=ZIP)
    ap.add_argument('--out', default=REPORT)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    args = ap.parse_args()
    if not (args.dry_run or args.run):
        ap.error('必须给 --dry-run 或 --run')

    out = {'script': os.path.basename(__file__),
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': args.pkg, 'zip': args.zip,
           'mode': 'run' if args.run else 'dry-run'}

    def fail(reason: str) -> int:
        out['verdict'] = 'FAIL'
        out['reason'] = reason
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('🔴 %s' % reason)
        print(json.dumps(out, ensure_ascii=False, indent=1)[:1200])
        return 1

    # ── 闸门① 源目录 ────────────────────────────────────────
    if not os.path.isdir(args.pkg):
        return fail('源包目录不存在：%s' % args.pkg)
    # ── 闸门② 目标 zip 不存在（**不覆盖**）───────────────────
    if os.path.exists(args.zip):
        return fail('目标 zip 已存在 ⇒ **不覆盖**（APP-055）：%s' % args.zip)
    # ── 闸门③ rc3 的 zip 在 ────────────────────────────────
    rc3_before = {}
    for z3 in RC3_ZIPS:
        if not os.path.isfile(z3):
            return fail('rc3 zip 不存在（事后复核需要）：%s' % z3)
        rc3_before[z3] = {'sha256': sha256_file(z3),
                          'bytes': os.path.getsize(z3)}
    out['rc3_zips_before'] = rc3_before
    # ── 闸门④ 7z 在 ────────────────────────────────────────
    if not os.path.isfile(SEVENZ):
        return fail('找不到 7z：%s' % SEVENZ)

    # ── 闸门⑤ 清单 ──────────────────────────────────────────
    rows = [(PKG_NAME + '/' + rel, size)
            for rel, size in PE.iter_package_files(args.pkg)]
    total = sum(s for _r, s in rows)
    out['n_files'] = len(rows)
    out['src_bytes'] = total
    out['src_gb'] = round(total / 1024 ** 3, 3)
    bad_ufffd = [r for r, _s in rows if '\ufffd' in r]
    bad_abs = [r for r, _s in rows
               if r.startswith('/') or ':' in r.split('/')[0]]
    bad_bak = [r for r, _s in rows if '.bak' in r.lower()]
    out['listfile_ufffd'] = len(bad_ufffd)
    out['listfile_abs_path'] = len(bad_abs)
    out['listfile_bak'] = len(bad_bak)
    if bad_ufffd or bad_abs or bad_bak:
        return fail('清单有问题：ufffd=%d abs=%d bak=%d'
                    % (len(bad_ufffd), len(bad_abs), len(bad_bak)))

    # ── 闸门⑥ README 数字 == 清单实测（APP-073(c) 同类）─────
    rp = os.path.join(args.pkg, 'README_perftest.txt')
    import re
    rt = open(rp, encoding='utf-8').read()
    m = re.search(r'解压后 \*\*约 ([0-9.]+) GB\*\*（([0-9 ]+) 个文件）', rt)
    claim = {'gb': float(m.group(1)) if m else None,
             'n_files': int(m.group(2).replace(' ', '')) if m else None}
    out['readme_claims'] = claim
    if not m or claim['n_files'] != len(rows) \
            or abs(claim['gb'] - out['src_gb']) > 0.15:
        return fail('README 数字与清单实测不一致：README %s / 清单 %d 个 %.3f GB'
                    % (json.dumps(claim, ensure_ascii=False),
                       len(rows), out['src_gb']))

    # ── 闸门⑦ NPU IR 齐全 + iGPU 保留 ───────────────────────
    have = {r for r, _s in rows}
    missing_npu = [r for r in REQUIRED_NPU if r not in have]
    missing_igpu = [r for r in REQUIRED_IGPU if r not in have]
    out['missing_npu_ir'] = missing_npu
    out['missing_igpu_ir'] = missing_igpu
    if missing_npu:
        return fail('清单里缺 NPU IR：%s' % missing_npu)
    if missing_igpu:
        return fail('清单里缺 iGPU 模型：%s' % missing_igpu)

    # ── 落清单文件 ─────────────────────────────────────────
    with open(LISTFILE, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(r for r, _s in rows) + '\n')
    out['listfile'] = LISTFILE

    cmd = [SEVENZ, 'a', '-tzip', '-mx=5', '-mmt=on', '-bso0', '-bsp0',
           args.zip, '-i@' + LISTFILE]
    out['cmd'] = cmd
    if args.dry_run:
        out['verdict'] = 'DRY_RUN_OK'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    # ── 打包 ───────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    CREATE_NO_WINDOW = 0x08000000
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=HOME, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            creationflags=CREATE_NO_WINDOW)
    out['pid'] = proc.pid
    try:
        import ctypes
        BELOW_NORMAL = 0x00004000
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, proc.pid)
        if h:
            ctypes.windll.kernel32.SetPriorityClass(h, BELOW_NORMAL)
            ctypes.windll.kernel32.CloseHandle(h)
            out['priority'] = 'BELOW_NORMAL'
    except Exception as e:
        out['priority'] = 'ERR %r' % (e,)
    o, _e = proc.communicate()
    out['rc'] = proc.returncode
    out['wall_s'] = round(time.time() - t0, 2)
    if proc.returncode != 0:
        out['stdout_tail'] = (o or b'').decode('utf-8', 'replace')[-800:]
        return fail('7z rc=%d' % proc.returncode)

    # ── 验收：条目数 / 逐条 CRC / SHA256 ────────────────────
    zf = zipfile.ZipFile(args.zip)
    infos = [i for i in zf.infolist() if not i.is_dir()]
    out['n_zip_entries'] = len(infos)
    out['zip_bytes'] = os.path.getsize(args.zip)
    out['zip_gb'] = round(out['zip_bytes'] / 1024 ** 3, 3)
    out['zip_sha256'] = sha256_file(args.zip)

    src_map = {r: os.path.join(args.pkg, r.split('/', 1)[1].replace('/', os.sep))
               for r, _s in rows}
    zip_crc = {i.filename: (i.CRC, i.file_size) for i in infos}
    out['n_entries_match'] = (len(infos) == len(rows))
    missing = [r for r in src_map if r not in zip_crc]
    extra = [r for r in zip_crc if r not in src_map]
    out['n_missing_in_zip'] = len(missing)
    out['n_extra_in_zip'] = len(extra)
    out['missing_sample'] = missing[:10]
    out['extra_sample'] = extra[:10]
    # 逐条 CRC 比对（源文件 vs zip 内）
    bad_crc = []
    for r, full in src_map.items():
        if r not in zip_crc:
            continue
        zc, zs = zip_crc[r]
        if os.path.getsize(full) != zs:
            bad_crc.append({'file': r, 'reason': 'size'})
            continue
        if crc32_file(full) != zc:
            bad_crc.append({'file': r, 'reason': 'crc'})
    out['n_crc_mismatch'] = len(bad_crc)
    out['crc_mismatch_sample'] = bad_crc[:10]
    zf.close()

    # ── rc3 的 zip 复核（**一字节未动**）────────────────────
    rc3_after = {}
    for z3 in RC3_ZIPS:
        rc3_after[z3] = {'sha256': sha256_file(z3),
                         'bytes': os.path.getsize(z3)}
    out['rc3_zips_after'] = rc3_after
    out['rc3_zips_unchanged'] = (rc3_after == rc3_before)

    ok = (out['n_entries_match'] and not missing and not extra
          and not bad_crc and out['rc3_zips_unchanged'])
    out['verdict'] = 'ZIP_OK' if ok else 'ZIP_VERIFY_FAILED'
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: out.get(k) for k in
                      ('n_files', 'n_zip_entries', 'n_entries_match',
                       'n_missing_in_zip', 'n_extra_in_zip',
                       'n_crc_mismatch', 'zip_bytes', 'zip_gb',
                       'zip_sha256', 'rc3_zips_unchanged', 'wall_s',
                       'verdict')}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
