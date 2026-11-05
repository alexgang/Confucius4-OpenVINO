#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app288_rc3_perftest_zip_rev2.py —— APP-073(c) / APP-074：**perftest zip 重打（README 修正版）**。

## 背景

reviewer 在 APP-073 指出 README 里的文件数与 zip 条目数不符：

> 2. README 磁盘写"10 503 个文件/约6.7GB"与 zip 10 474 条目不符（小问题）。

APP-074 末尾（**A 不依赖 babelvox 示例音色**分支 ⇒ 本脚本适用）：

> 如果 A 不依赖这 4 个文件，冒烟 PASS 后按 APP-073 (c) 收口，
> **并把 README 的文件数改成 10 474**。

README 在 zip **里面** ⇒ 改完必须重打 ⇒ 新 SHA ⇒ 这就是 (c) 里的「**最终 SHA**」。

## 🔴 版本纪律（APP-055）

* **不覆盖任何旧 zip** ⇒ 本脚本打**新文件名**（`*_rev2.zip`），
  旧 `*_perftest.zip` **一字节不动**（收尾会复核它的 SHA256 逐字未变）。
* **不原地改用户正在测试的安装目录**（`Confucius4_LiveCaption_v*`）
  ⇒ 只动 MiniMVP rc3 **构建源**目录里的 README（`app284` 已做）。
* **打包前必须先 `--dry-run`**（闸门：U+FFFD 乱码 / 绝对路径 / 数量漂移）。

## 🔴 一致性对账（本脚本最有价值的部分）

拿**旧 zip 的每个条目 CRC32** 与**新源目录对应文件的 CRC32** 逐条比：

* 期望：**恰好 1 个文件不同**（`README_perftest.txt`），
  其余 10 473 个文件**逐条 CRC 相同**，且**无增无减**。
* ⇒ 这一条闸门同时证明了三件事：
  ① 没有把被排除的第三方素材偷偷放回去；
  ② 没有漏掉/多打文件；
  ③ 本轮**除了 README 那个数字，别的什么都没动**。

## 用法

```
.venv/Scripts/python.exe results/app/_app288_rc3_perftest_zip_rev2.py --dry-run
.venv/Scripts/python.exe results/app/_app288_rc3_perftest_zip_rev2.py --run
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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
sys.path.insert(0, REPO)

PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3'
PKG = os.path.join(HOME, PKG_NAME)
OUT_DIR = os.path.join(HOME, 'shared', 'minimvp')
OLD_ZIP = os.path.join(OUT_DIR, PKG_NAME + '_perftest.zip')
ZIP = os.path.join(OUT_DIR, PKG_NAME + '_perftest_rev2.zip')
SEVENZ = r'C:\Program Files\7-Zip\7z.exe'
REPORT = os.path.join(HERE, 'app288_rc3_perftest_zip_rev2_evidence.json')
LISTFILE = os.path.join(HERE, '_app288_zip_listfile.txt')

TOP = PKG_NAME

#: 本轮**唯一**允许与旧 zip 不同的文件（README 数字修正）
EXPECTED_DIFF = 'README_perftest.txt'

#: README 里必须出现的**新**数字 / 必须**消失**的旧数字
README_NEW = '10 474'
README_OLD = '10 503'


def sha256_file(path, chunk=4 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def crc32_file(path):
    import zlib
    crc = 0
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            crc = zlib.crc32(b, crc)
    return crc & 0xFFFFFFFF


def build_listfile(pkg):
    import pkg_exclude as PE
    rows = []
    total = 0
    for rel, size in PE.iter_package_files(pkg):
        rows.append(TOP + '/' + rel)
        total += size
    return rows, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--old-zip', default=OLD_ZIP)
    ap.add_argument('--zip', default=ZIP)
    ap.add_argument('--out', default=REPORT)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if not (a.dry_run or a.run):
        ap.error('必须给 --dry-run 或 --run')

    out = {'script': '_app288_rc3_perftest_zip_rev2.py',
           'correction': 'APP-073(c) + APP-074（README 文件数修正 ⇒ 重打 ⇒ 最终 SHA）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': a.pkg, 'zip': a.zip, 'old_zip': a.old_zip,
           'mode': 'run' if a.run else 'dry-run'}

    # ── 闸门①：源目录在 / 新 zip 不存在（**不覆盖**）/ 旧 zip 在 ──────
    if not os.path.isdir(a.pkg):
        out['verdict'] = 'FAIL'
        out['reason'] = '源包目录不存在：%s' % a.pkg
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1
    if os.path.exists(a.zip):
        out['verdict'] = 'FAIL'
        out['reason'] = '目标 zip 已存在 ⇒ **不覆盖**（APP-055）：%s' % a.zip
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1
    if not os.path.isfile(a.old_zip):
        out['verdict'] = 'FAIL'
        out['reason'] = '旧 zip 不存在（一致性对账需要它）：%s' % a.old_zip
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1
    if not os.path.isfile(SEVENZ):
        out['verdict'] = 'FAIL'
        out['reason'] = '找不到 7z：%s' % SEVENZ
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    old_sha_before = sha256_file(a.old_zip)
    out['old_zip_sha256_before'] = old_sha_before
    out['old_zip_bytes'] = os.path.getsize(a.old_zip)

    # ── 闸门②：README 已是修正版（旧的数字必须消失）─────────────────
    readme = os.path.join(a.pkg, 'README_perftest.txt')
    rb = open(readme, 'rb').read()
    out['readme'] = {'bytes': len(rb), 'sha256': hashlib.sha256(rb).hexdigest(),
                     'n_new': rb.count(README_NEW.encode('utf-8')),
                     'n_old': rb.count(README_OLD.encode('utf-8'))}
    if out['readme']['n_new'] != 1 or out['readme']['n_old'] != 0:
        out['verdict'] = 'FAIL'
        out['reason'] = ('README 未处于修正态（新数字命中 %d 次、旧数字命中 %d 次）'
                         % (out['readme']['n_new'], out['readme']['n_old']))
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    # ── 闸门③：清单（数量 / U+FFFD / 绝对路径 / 备份文件）────────────
    rows, total = build_listfile(a.pkg)
    with open(LISTFILE, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(rows) + '\n')
    out['n_files'] = len(rows)
    out['src_bytes'] = total
    out['src_gb'] = round(total / (1024 ** 3), 3)
    out['listfile'] = LISTFILE
    bad_ufffd = [r for r in rows if '\ufffd' in r]
    bad_abs = [r for r in rows if r.startswith('/') or ':' in r.split('/')[0]]
    bad_bak = [r for r in rows if '.bak' in r.lower()]
    out['listfile_ufffd'] = len(bad_ufffd)
    out['listfile_abs_path'] = len(bad_abs)
    out['listfile_bak'] = len(bad_bak)
    if bad_ufffd or bad_abs or bad_bak:
        out['verdict'] = 'FAIL'
        out['reason'] = ('清单有问题：ufffd=%d abs=%d bak=%d'
                         % (len(bad_ufffd), len(bad_abs), len(bad_bak)))
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    # ── 闸门④：与旧 zip 的 CRC32 一致性对账 ────────────────────────
    #   期望：恰好 1 个文件不同（README），其余逐条相同，无增无减。
    zf = zipfile.ZipFile(a.old_zip)
    old_crc = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        # 🔴 zip 内条目名**带顶层目录前缀**（`Confucius4_..._rc3/app/x.py`）
        #   ⇒ 统一剥掉 `TOP + '/'` 再比对，否则两边对不上（首轮 dry-run 踩过）。
        name = info.filename
        pref = TOP + '/'
        if name.startswith(pref):
            name = name[len(pref):]
        old_crc[name] = (info.CRC, info.file_size)
    zf.close()
    out['old_zip_entries'] = len(old_crc)

    new_map = {}
    for rel in rows:
        name = rel.split('/', 1)[1]
        full = os.path.join(a.pkg, name.replace('/', os.sep))
        new_map[name] = full

    added = sorted(set(new_map) - set(old_crc))
    removed = sorted(set(old_crc) - set(new_map))
    common = sorted(set(new_map) & set(old_crc))
    changed = []
    for name in common:
        c_old, s_old = old_crc[name]
        full = new_map[name]
        if os.path.getsize(full) != s_old:
            changed.append({'file': name, 'reason': 'size',
                            'old': s_old, 'new': os.path.getsize(full)})
            continue
        c_new = crc32_file(full)
        if c_new != c_old:
            changed.append({'file': name, 'reason': 'crc',
                            'old_crc': c_old, 'new_crc': c_new})
    out['crc_audit'] = {
        'n_common': len(common),
        'n_added': len(added), 'added': added[:20],
        'n_removed': len(removed), 'removed': removed[:20],
        'n_changed': len(changed), 'changed': changed[:20],
        'expected_diff': EXPECTED_DIFF,
        'changed_is_expected_only': (
            len(changed) == 1
            and changed[0]['file'].endswith(EXPECTED_DIFF)),
    }
    if not (out['crc_audit']['changed_is_expected_only']
            and not added and not removed):
        out['verdict'] = 'FAIL'
        out['reason'] = ('一致性对账失败：changed=%d added=%d removed=%d'
                         % (len(changed), len(added), len(removed)))
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    cmd = [SEVENZ, 'a', '-tzip', '-mx=5', '-mmt=on', '-bso0', '-bsp0',
           a.zip, '-i@' + LISTFILE]
    out['cmd'] = cmd
    if a.dry_run:
        out['verdict'] = 'DRY_RUN_OK'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    CREATE_NO_WINDOW = 0x08000000
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=HOME, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            creationflags=CREATE_NO_WINDOW)
    try:
        import ctypes
        BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, proc.pid)
        if h:
            ctypes.windll.kernel32.SetPriorityClass(h, BELOW_NORMAL_PRIORITY_CLASS)
            ctypes.windll.kernel32.CloseHandle(h)
            out['priority'] = 'BELOW_NORMAL'
        else:
            out['priority'] = 'OPENPROCESS_FAILED'
    except Exception as e:
        out['priority'] = 'ERR %r' % (e,)
    out['pid'] = proc.pid
    o, e = proc.communicate()
    out['rc'] = proc.returncode
    out['wall_s'] = round(time.time() - t0, 2)
    if proc.returncode != 0:
        out['verdict'] = 'FAIL'
        out['reason'] = '7z rc=%d' % proc.returncode
        out['stdout_tail'] = (o or b'').decode('utf-8', 'replace')[-800:]
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    # ── 验收：新 zip 的条目数 / 大小 / SHA256 / README 内容 ─────────
    zf = zipfile.ZipFile(a.zip)
    names = [n for n in zf.namelist() if not n.endswith('/')]
    rname = TOP + '/README_perftest.txt'
    in_readme = zf.read(rname).decode('utf-8')
    speakers = [n for n in names if 'babelvox/data/speakers/' in n]
    zf.close()
    out['zip_entries'] = len(names)
    out['zip_bytes'] = os.path.getsize(a.zip)
    out['zip_gb'] = round(out['zip_bytes'] / (1024 ** 3), 3)
    out['zip_sha256'] = sha256_file(a.zip)
    out['zip_mtime'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                     time.localtime(os.path.getmtime(a.zip)))
    out['n_mismatch'] = len(names) - len(rows)
    out['readme_in_zip'] = {
        'bytes': len(in_readme.encode('utf-8')),
        'sha256': hashlib.sha256(in_readme.encode('utf-8')).hexdigest(),
        'n_new': in_readme.count(README_NEW),
        'n_old': in_readme.count(README_OLD),
    }
    out['n_babelvox_speakers_in_zip'] = len(speakers)
    out['n_babelvox_speakers_in_zip_list'] = speakers[:10]

    # ── 闸门⑤：旧 zip 一字节未动（APP-055「不覆盖、不删除」）─────────
    old_sha_after = sha256_file(a.old_zip)
    out['old_zip_sha256_after'] = old_sha_after
    out['old_zip_untouched'] = (old_sha_after == old_sha_before)

    checks = [
        ('① 新 zip 条目数 == 清单条数（10 474）',
         len(names) == len(rows) == 10474,
         {'entries': len(names), 'list': len(rows)}),
        ('② 新 zip 内 README 已是修正态（新=1 次 / 旧=0 次）',
         out['readme_in_zip']['n_new'] == 1
         and out['readme_in_zip']['n_old'] == 0,
         out['readme_in_zip']),
        ('③ 新 zip 内无 babelvox 示例音色',
         len(speakers) == 0,
         {'n': len(speakers)}),
        ('④ 与旧 zip 的 CRC 对账：只 README 1 个文件不同、无增无减',
         out['crc_audit']['changed_is_expected_only']
         and not added and not removed,
         out['crc_audit']),
        ('⑤ 旧 zip 一字节未动（SHA256 逐字相同）',
         out['old_zip_untouched'],
         {'before': old_sha_before, 'after': old_sha_after}),
        ('⑥ 清单无 U+FFFD / 绝对路径 / 备份文件',
         not bad_ufffd and not bad_abs and not bad_bak,
         {'ufffd': len(bad_ufffd), 'abs': len(bad_abs), 'bak': len(bad_bak)}),
    ]
    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_fail = len(checks) - n_pass
    out['checks'] = [{'name': n, 'verdict': ok, 'detail': d}
                     for n, ok, d in checks]
    out['n_pass'] = n_pass
    out['n_fail'] = n_fail
    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    out['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for n, ok, d in checks:
        print('  [%s] %s  %s' % ('PASS' if ok else 'FAIL', n,
                                  json.dumps(d, ensure_ascii=False)))
    print('\n结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[新 zip] %s\n  bytes=%s  sha256=%s' % (a.zip, out['zip_bytes'],
                                                  out['zip_sha256']))
    print('[evidence] %s' % a.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
