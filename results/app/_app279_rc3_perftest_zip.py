#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app279_rc3_perftest_zip.py —— APP-072 §1：打 MiniMVP rc3 的**性能测试 zip**。

## 做什么

用现有 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc3`
打 `Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest.zip`，放
`C:\Users\Trekker-PTL\shared\minimvp\`。

## 纪律（reviewer 原文）

* **不改 rc3 目录内容**（本脚本只读 rc3；README_perftest.txt 与 NOTICE
  补丁是上一脚本落的，已在打包前完成）。
* **不覆盖已有任何目录/zip** ⇒ 目标 zip 若已存在 ⇒ 直接 FAIL，不覆盖。
* **无用 TTS IR 这次不删**（reviewer 明文：留到下一版）⇒ 本脚本**不删任何
  模型文件**，只按 `pkg_exclude` 的规则**在 zip 里排除**（babelvox 示例音色
  8 个文件 + scipy 测试音频 22 个文件）—— 与 v2.2 zip 的口径一致。
* **打包是磁盘作业不占设备** ⇒ 不取 MACHINE_LOCK；但**用低优先级**
  （BELOW_NORMAL）⇒ 别拖慢正在持锁的 TTS/ASR 作业。
* **打包前必须先 `--dry-run`**（打包闸门：写死客户包路径 / U+FFFD 乱码）。

## 打包口径

zip 内**顶层就是** `Confucius4_LiveCaption_MiniMVP_v1.0-rc3/`（与 v2.2 zip
同结构：zip 内第一层是包名目录）⇒ 用户解压后直接得到该目录。

## 用法

```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe \
    results/app/_app279_rc3_perftest_zip.py --dry-run
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe \
    results/app/_app279_rc3_perftest_zip.py --run
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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
sys.path.insert(0, REPO)

PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3'
PKG = os.path.join(HOME, PKG_NAME)
OUT_DIR = os.path.join(HOME, 'shared', 'minimvp')
ZIP_NAME = PKG_NAME + '_perftest.zip'
ZIP = os.path.join(OUT_DIR, ZIP_NAME)
SEVENZ = r'C:\Program Files\7-Zip\7z.exe'
REPORT = os.path.join(HERE, 'app279_rc3_perftest_zip_evidence.json')

#: zip 内的顶层目录名（**必须**与源目录名一致 ⇒ 解压后是 `PKG_NAME/`）
TOP = PKG_NAME


def sha256_file(path: str, chunk=4 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def build_listfile(pkg: str) -> tuple:
    """按 `pkg_exclude` 口径产出**要进 zip 的文件清单**（含顶层目录前缀）。"""
    import pkg_exclude as PE
    rows = []
    total = 0
    for rel, size in PE.iter_package_files(pkg):
        rows.append(TOP + '/' + rel)
        total += size
    return rows, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if not (a.dry_run or a.run):
        ap.error('必须给 --dry-run 或 --run')

    out = {
        'pkg': PKG, 'zip': ZIP, 'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'mode': 'run' if a.run else 'dry-run',
    }

    # ── 闸门①：源目录存在 / 目标 zip 不存在（不覆盖）──────────────
    if not os.path.isdir(PKG):
        out['verdict'] = 'FAIL'
        out['reason'] = f'源包目录不存在：{PKG}'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1
    if os.path.exists(ZIP):
        out['verdict'] = 'FAIL'
        out['reason'] = f'目标 zip 已存在 ⇒ **不覆盖**（APP-055）：{ZIP}'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1
    if not os.path.isfile(SEVENZ):
        out['verdict'] = 'FAIL'
        out['reason'] = f'找不到 7z：{SEVENZ}'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── 闸门②：README_perftest.txt 必须存在（reviewer 明确要求）──
    rpt = os.path.join(PKG, 'README_perftest.txt')
    out['readme_perftest'] = {
        'exists': os.path.isfile(rpt),
        'bytes': os.path.getsize(rpt) if os.path.isfile(rpt) else None,
    }
    if not out['readme_perftest']['exists']:
        out['verdict'] = 'FAIL'
        out['reason'] = '包内缺 README_perftest.txt'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    # ── 清单 ────────────────────────────────────────────────────
    rows, total = build_listfile(PKG)
    listfile = os.path.join(HERE, '_app279_zip_listfile.txt')
    with open(listfile, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(rows) + '\n')
    out['n_files'] = len(rows)
    out['src_bytes'] = total
    out['src_gb'] = round(total / (1024 ** 3), 3)
    out['listfile'] = listfile

    # ── 闸门③：清单里不得有 U+FFFD / 乱码 / 绝对路径 ───────────────
    bad = [r for r in rows if '\ufffd' in r]
    out['listfile_ufffd'] = len(bad)
    if bad:
        out['verdict'] = 'FAIL'
        out['reason'] = f'清单里有 {len(bad)} 条含 U+FFFD'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    if a.dry_run:
        out['verdict'] = 'DRY_RUN_OK'
        out['cmd'] = [SEVENZ, 'a', '-tzip', '-mx=5', '-mmt=on',
                      '-bso0', '-bsp0', ZIP, '-i@' + listfile]
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    # ── 实跑：7z 低优先级（BELOW_NORMAL）────────────────────────
    cmd = [SEVENZ, 'a', '-tzip', '-mx=5', '-mmt=on',
           '-bso0', '-bsp0', ZIP, '-i@' + listfile]
    out['cmd'] = cmd
    t0 = time.time()
    # 🔴 低优先级：不影响正在持 MACHINE_LOCK 的 ASR/TTS 作业
    CREATE_NO_WINDOW = 0x08000000
    proc = subprocess.Popen(
        cmd, cwd=HOME, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW)
    # 降优先级：BELOW_NORMAL
    try:
        import ctypes
        BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, proc.pid)
        if h:
            ctypes.windll.kernel32.SetPriorityClass(
                h, BELOW_NORMAL_PRIORITY_CLASS)
            ctypes.windll.kernel32.CloseHandle(h)
            out['priority'] = 'BELOW_NORMAL'
        else:
            out['priority'] = 'OPENPROCESS_FAILED'
    except Exception as e:
        out['priority'] = f'ERR {e!r}'
    out['pid'] = proc.pid
    o, e = proc.communicate()
    out['rc'] = proc.returncode
    out['wall_s'] = round(time.time() - t0, 2)
    out['stdout_tail'] = (o or b'').decode('utf-8', 'replace')[-800:]
    if proc.returncode != 0:
        out['verdict'] = 'FAIL'
        out['reason'] = f'7z rc={proc.returncode}'
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    # ── 验收：zip 的条目数 / 大小 / SHA256 ──────────────────────
    import zipfile
    z = zipfile.ZipFile(ZIP)
    names = z.namelist()
    out['zip_entries'] = len(names)
    out['zip_bytes'] = os.path.getsize(ZIP)
    out['zip_gb'] = round(out['zip_bytes'] / (1024 ** 3), 3)
    out['zip_sha256'] = sha256_file(ZIP)
    out['zip_top_dirs'] = sorted({n.split('/')[0] for n in names})
    out['has_readme_perftest'] = any(
        n.endswith('/README_perftest.txt') for n in names)
    out['has_notice'] = any(n.endswith('/NOTICE') for n in names)
    out['n_mismatch'] = len(names) - len(rows)
    out['verdict'] = 'PASS'
    out['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
