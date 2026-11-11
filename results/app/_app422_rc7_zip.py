#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app422_rc7_zip.py —— **MiniMVP v1.0-rc6 打 zip**（APP-098）。

## 口径（与 rc5 的 `_app318` **完全同一套**）

* 工具：**7-Zip**（`7z a -tzip -mx=5 -mmt=on`）
* 清单：**`pkg_exclude`（单一数据源）** ⇒ 与 rc5 zip 同口径
* 顶层目录：`Confucius4_LiveCaption_MiniMVP_v1.0-rc7/`
* 输出：`%USERPROFILE%\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc7_perftest.zip`
  ⇒ **新文件名**，rc3/rc4/rc5 的 zip **一字节不动**。

## 🔴🔴🔳 APP-098 新增/沿用的闸门

* zip 清单里 **R2T2 的 ASR IR 出现次数 = 0**（沿用 rc5）
* zip 清单里 **`decoder-npu-int4` 出现次数 = 0**（沿用 rc5）
* zip 清单里 **0.6B 物料齐全**（沿用 rc5）
* zip 清单里 **R2T2 的 `models/tokenizer/` 出现次数 = 0**（**APP-098 二.2 新增**）
* zip 清单里 **CUDA / torch 相关文件数 = 0**（**APP-098 一.1 新增**）
* zip 清单里 **`app/` 下有 `package_profile.json` 的形态标记**
  （**APP-098 新增**：它决定「无 CUDA / 无克隆音色」）
* **README 的体积/文件数 == 清单实测值**（沿用 rc5；APP-098 二.5 改过口径）
* **rc3 / rc4 / rc5 的 zip SHA256 前后逐字未变**

## 用法

```
.venv/Scripts/python.exe results/app/_app422_rc7_zip.py --dry-run
.venv/Scripts/python.exe results/app/_app422_rc7_zip.py --run
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc7'
PKG = os.path.join(HOME, PKG_NAME)
OUT_DIR = os.path.join(HOME, 'shared', 'minimvp')
ZIP = os.path.join(OUT_DIR, PKG_NAME + '_perftest.zip')
SEVENZ = r'C:\Program Files\7-Zip\7z.exe'
REPORT = os.path.join(HERE, 'app422_rc7_zip_evidence.json')
LISTFILE = os.path.join(HERE, '_app422_zip_listfile.txt')

#: 🔴 **必须为 0 次**的条目（R2T2 ASR IR + INT4 decoder）
FORBIDDEN = (
    'models/encoder-int8/',
    'models/decoder-gpu-int8/',
    'models/encoder-fp16/',
    'models/decoder-npu-int8/',
    'models/decoder-npu-int4/',
    'models/embed_tokens_f16.npy',
    # 🔴🔴🔳 **APP-098 二.2**：R2T2 的 tokenizer（hidden 2048）**没人引用**
    #    （0.6B 读的是 `models/asr06b-tokenizer/`）⇒ 必须 0 个。
    'models/tokenizer/',
)

#: 🔴🔴🔳 **APP-098 一.1：CUDA / torch 相关文件**必须为 0**
#:   ⚠️ **判据范围很重要（第一版写宽了，误伤了第三方运行时）**：
#:      `python/Lib/site-packages/openvino/.../frontend/pytorch/*.hpp`
#:      是 **OpenVINO 官方发行版自带的 C++ 头文件**（不是 App 引入的 torch）
#:      ⇒ 全仓 grep「cuda|torch」会**误报** ⇒ 判据必须**限定在 App 自己拥有的路径**：
#:        ① `app/` 下的文件（App 代码）
#:        ② `models/` 下的文件（模型资产）
#:        ③ 包根的 CUDA 运行时目录（`cuda/`、`_fq3tts_env/`）
#:           ＝ APP-088 明令**不随包分发**的那些
#:      ⇒ 第三方 `python/`（OV / transformers / numpy …）**不在判据范围内**。
FORBIDDEN_APP_PATHS = ('app/', 'models/')
FORBIDDEN_ROOT_DIRS = ('cuda/', '_fq3tts_env/', 'faster_qwen3/')
FORBIDDEN_SUBSTR = ('cuda', 'torch')

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

#: 🔴 **必须存在**的 APP-098 产物
REQUIRED_APP098 = (
    'package_profile.json',
    'README_perftest.txt',
    'app/package_profile.py',
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
           'correction': 'APP-098',
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
    for z in (os.path.join(OUT_DIR, n) for n in (
            'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest.zip',
            'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip',
            'Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip',
            'Confucius4_LiveCaption_MiniMVP_v1.0-rc5_perftest.zip')):
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
    # 🔴 **GB 口径**（1e9）—— README 里写的是 GB ⇒ 判据必须用**同一个口径**
    out['total_gb_dec'] = round(total_bytes / 1e9, 3)

    # ── 闸门④ 清单洁净 ───────────────────────────────────────────
    bad = [r for r in rels if '\ufffd' in r or r.startswith('/')
           or ':' in r[:3] or r.endswith('.bak')]
    if bad:
        return fail('清单含非法条目：%s' % bad[:5])

    # ── 闸门⑤ README 的体积/文件数 == 实测（APP-073(c) 同类缺陷）──
    # 🔴 APP-098 二.5：README 已改成「解压后 X GB（N 个文件）」的新口径
    readme = os.path.join(PKG, 'README_perftest.txt')
    txt = open(readme, encoding='utf-8', errors='replace').read()
    m = re.search(r'解压后\*\*：(\d+) 个文件 / \*\*([\d.]+) GB\*\*', txt)
    if not m:
        return fail('README_perftest 里找不到「解压后：N 个文件 / X GB」'
                    '（APP-098 二.5 新口径）')
    r_n, r_gb = int(m.group(1)), float(m.group(2))
    if abs(r_gb - out['total_gb_dec']) > 0.15:
        return fail('README 体积 %.3f GB 与实测 %.3f GB 不符'
                    % (r_gb, out['total_gb_dec']))
    if r_n != len(files):
        return fail('README 文件数 %d 与清单 %d 不符' % (r_n, len(files)))
    out['readme_numbers_match'] = True
    out['readme_n_files'] = r_n
    out['readme_gb'] = r_gb

    # ── 闸门⑥ R2T2 / INT4 / tokenizer 计数必须为 0 ─────────────
    counts = {}
    for pat in FORBIDDEN:
        counts[pat] = sum(1 for r in rels if pat in r)
    out['forbidden_counts'] = counts
    nz = {k: v for k, v in counts.items() if v}
    if nz:
        return fail('zip 清单里仍有应删除的条目：%s' % nz)

    # ── 闸门⑦ CUDA / torch 相关文件数必须为 0（APP-098 一.1）────
    #    判据**限定在 App 自己拥有的路径**（见 FORBIDDEN_APP_PATHS 的说明）
    cuda_hits = []
    for r in rels:
        in_app = r.startswith(FORBIDDEN_APP_PATHS)
        in_root_dir = any(r.startswith(d) for d in FORBIDDEN_ROOT_DIRS)
        if not (in_app or in_root_dir):
            continue
        low = os.path.basename(r).lower()
        if any(s in low for s in FORBIDDEN_SUBSTR):
            cuda_hits.append(r)
    out['cuda_torch_hits'] = cuda_hits[:50]
    out['n_cuda_torch'] = len(cuda_hits)
    out['cuda_torch_scope'] = list(FORBIDDEN_APP_PATHS) + list(FORBIDDEN_ROOT_DIRS)
    if cuda_hits:
        return fail('zip 清单里含 CUDA/torch 相关文件（App 自有路径）：%s'
                    % cuda_hits[:5])

    # ── 闸门⑧ 0.6B 物料齐全 ─────────────────────────────────────
    prefix = PKG_NAME + '/'
    missing = [r for r in REQUIRED_06B if not any(
        x.endswith(r) or x == prefix + r for x in rels)]
    if missing:
        return fail('0.6B 物料缺失：%s' % missing)
    out['required_06b_present'] = True

    # ── 闸门⑨ APP-098 产物齐全（形态标记等）──────────────────────
    missing98 = [r for r in REQUIRED_APP098 if not any(
        x.endswith(r) or x == prefix + r for x in rels)]
    if missing98:
        return fail('APP-098 产物缺失：%s' % missing98)
    out['required_app098_present'] = True

    # ── 闸门⑩ 无预编译 NPU blob（目标机现编）─────────────────────
    blobs = [r for r in rels if r.endswith('.blob')]
    out['n_blob'] = len(blobs)
    if blobs:
        return fail('包内含预编译 blob：%s' % blobs[:5])

    # ── 写清单文件（给 7z 用）───────────────────────────────────
    with open(LISTFILE, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join('%s/%s' % (PKG_NAME, r.replace('\\', '/'))
                          for r, _s in files) + '\n')

    if args.dry_run:
        out['verdict'] = 'DRY_RUN_OK'
        print(json.dumps({k: out[k] for k in
                          ('n_entries', 'total_gb', 'forbidden_counts',
                           'n_cuda_torch', 'readme_numbers_match', 'n_blob')},
                         ensure_ascii=False, indent=1))
        print('[dry-run] 未打包')
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 0

    # ── 打包（**两遍**：第一遍量 zip 体积 ⇒ 写回 README ⇒ 第二遍定稿）──
    # 🔴🔴🔳 **为什么要两遍**（APP-098 二.5：README 要写**实测**的 zip 体积）：
    #   「zip 体积」只有**打完**才知道 ⇒ 而写回 README 又会**改变 zip**
    #   ⇒ 严格自洽是**不可能的**（改了 README ⇒ zip 变了 ⇒ 写的数又不对）。
    #   ⇒ **工程上唯一诚实的做法**：两遍 + **明确标注精度**：
    #     ① 第一遍：量出 zip_bytes ⇒ 写进 README（**2 位小数 = 10 MB 粒度**）
    #     ② 第二遍：定稿（README 只变了**几十字节** ⇒ zip 只差**几 KB**
    #        ⇒ **2 位小数下**第一遍的数与第二遍的数**必然相同** ⇒ 无矛盾）
    #     ③ 复核：|第二遍实测 − README 写的| ≤ 1 MB ⇒ 不通过就 FAIL。
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    def do_zip():
        if os.path.exists(ZIP):
            os.remove(ZIP)
        cmd = [SEVENZ, 'a', '-tzip', '-mx=5', '-mmt=on', '-bso0', '-bsp0',
               ZIP, '-i@' + LISTFILE]
        print('[zip] %s' % ' '.join(cmd))
        return subprocess.run(cmd, capture_output=True, text=True, cwd=HOME)

    # 🔴🔴 APP-099 四.4：**打包前逐项与源目录比对，任何一项不一致就终止**。
    #   共用实现在 live_caption/manifest_gen.py（与 _app420 同一份）。
    #   ⚠️ 放在第 1 遍 do_zip() **之前** ⇒ 不一致时连 zip 都不会生成。
    _dev = os.path.join(REPO, 'live_caption')
    if _dev not in sys.path:
        sys.path.insert(0, _dev)
    import manifest_gen
    try:
        manifest_gen.verify_or_die(PKG)
        out['app099_manifest_verify'] = 'PASS'
        print('[manifest] 逐项与源目录一致 ⇒ 允许打包')
    except manifest_gen.ManifestMismatch as e:
        out['app099_manifest_verify'] = 'FAIL'
        print('🔴 %s' % e)
        return 1

    print('[zip] 第 1 遍（量体积）…')
    p1 = do_zip()
    out['zip_rc_pass1'] = p1.returncode
    if p1.returncode != 0:
        out['zip_stderr'] = p1.stderr[-2000:]
        return fail('7z 第 1 遍退出码 %d' % p1.returncode)
    pass1_bytes = os.path.getsize(ZIP)
    out['zip_bytes_pass1'] = pass1_bytes
    print('[zip] 第 1 遍完成：%d 字节' % pass1_bytes)

    # 写回 README（把实测 zip 体积写进去）
    try:
        from _app421_rc7_readme import write_readme as _wr
        ev2 = json.load(open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'app410_minimvp_rc6_build_evidence.json'), encoding='utf-8'))
        _wr(PKG, ev2.get('model_identity', {}), ev2, zip_bytes=pass1_bytes)
        out['readme_zip_bytes_written'] = pass1_bytes
    except Exception as e:
        out['readme_zip_write_error'] = repr(e)
        return fail('把 zip 体积写回 README 失败：%r' % e)

    print('[zip] 第 2 遍（定稿）…')
    p = do_zip()
    pack_s = round(time.time() - t0, 1)
    out['pack_s'] = pack_s
    out['zip_rc'] = p.returncode
    if p.returncode != 0:
        out['zip_stderr'] = p.stderr[-2000:]
        return fail('7z 退出码 %d' % p.returncode)

    out['zip_bytes'] = os.path.getsize(ZIP)
    out['zip_sha256'] = sha256_file(ZIP)
    out['zip_gb'] = round(out['zip_bytes'] / 10 ** 9, 3)
    out['zip_mtime'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                     time.localtime(os.path.getmtime(ZIP)))
    # 🔴 复核：README 里写的 zip 体积与**最终** zip 的差 ≤ 1 MB
    out['zip_bytes_delta_vs_readme'] = abs(out['zip_bytes'] - pass1_bytes)
    if out['zip_bytes_delta_vs_readme'] > 1024 * 1024:
        return fail('两遍 zip 体积差 %d 字节（>1 MB）⇒ README 的数字会自相矛盾'
                    % out['zip_bytes_delta_vs_readme'])

    # ── 逐条 CRC32 比对 ─────────────────────────────────────────
    n_ok = 0
    mismatch = []
    missing_in_zip = []
    with zipfile.ZipFile(ZIP, 'r') as zf:
        names = set(zf.namelist())
        for r, _s in files:
            entry = '%s/%s' % (PKG_NAME, r.replace('\\', '/'))
            if entry not in names:
                missing_in_zip.append(r)
                continue
            try:
                c = zf.getinfo(entry).CRC
            except KeyError:
                missing_in_zip.append(r)
                continue
            if c == crc32_file(os.path.join(PKG, r)):
                n_ok += 1
            else:
                mismatch.append(r)
    out['crc_ok'] = n_ok
    out['crc_mismatch'] = mismatch[:20]
    out['missing_in_zip'] = missing_in_zip[:20]
    out['n_missing_in_zip'] = len(missing_in_zip)
    out['n_crc_mismatch'] = len(mismatch)
    if mismatch or missing_in_zip:
        return fail('逐条 CRC32 比对失败：mismatch=%d missing=%d'
                    % (len(mismatch), len(missing_in_zip)))

    # ── 前代 zip 未被动过 ───────────────────────────────────────
    prior_after = {}
    for z in (os.path.join(OUT_DIR, n) for n in prior_before):
        prior_after[os.path.basename(z)] = sha256_file(z)
    out['prior_zips_after'] = prior_after
    out['prior_zips_unchanged'] = (prior_before == prior_after)
    if prior_before != prior_after:
        return fail('前代 zip 的 SHA 变了（rc3/rc4/rc5 必须一字节不动）')

    out['verdict'] = 'PASS'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[zip] 完成：%s' % ZIP)
    print('  条目 %d ／ %.3f GB（zip）／ CRC32 逐条一致 %d 条'
          % (out['n_entries'], out['zip_gb'], n_ok))
    print('  前代 zip 未动：%s' % out['prior_zips_unchanged'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
