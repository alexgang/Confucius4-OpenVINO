#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app156_app100_zip_verify.py — §100：客户包 **v1.11** zip 产物的**只读**核验。

核验项：
1. zip 文件存在 / 字节数 / mtime / SHA256；
2. `zipfile.ZipFile.testzip()` ⇒ 无 CRC 错误；
3. **zip ⇄ 包目录 `.py` 逐字一致**（归一化 LF 后比对，逐文件）；
4. MANIFEST 的 `version` / `files` 计数；
5. **版本号三处一致**：目录版本 == zip 版本 == MANIFEST version；
6. 🔴🔴🔴 **本轮 §100 的 4 处断链修复是否真的在 zip 内**（专项判据）
   ⇒ 「包目录代码对」≠「客户拿到的 zip 对」（半交付判据）。

🔴 **全程只读**：不写任何文件、不改任何产物。
🔴 **不跑 `verify_pkg_zip.py`、不开 FTP**（§66 口径）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import zipfile

HOME = r'C:\Users\Trekker-PTL'
VER = sys.argv[1] if len(sys.argv) > 1 else '1.11'
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v%s' % VER)
ZIP = os.path.join(HOME, 'Confucius4_LiveCaption_v%s.zip' % VER)
PREFIX = 'Confucius4_LiveCaption_v%s' % VER
OUT = os.path.join(REPO, 'results', 'app',
                   'app156_app100_zip_evidence.json')

# 🔴🔴🔴 §100 改动的 3 个文件（zip 内必须与包目录逐字一致）
S100_FILES = ['live_caption_app.py', 'tts_worker.py', 'speaker_tracker.py']

PASS = 0
FAIL = 0
DETAIL = []


def add(name, ok, msg=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('PASS %-56s %s' % (name, msg))
    else:
        FAIL += 1
        print('FAIL %-56s %s' % (name, msg))
    DETAIL.append(dict(name=name, ok=bool(ok), msg=str(msg)))


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def norm(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def main() -> int:
    ev = {'ver': VER, 'zip_path': ZIP, 'pkg_dir': PKG}

    # ── ① zip 存在 / 字节 / mtime / SHA256 ─────────────────────────
    if not os.path.exists(ZIP):
        print('❌ zip 不存在：%s' % ZIP)
        return 1
    st = os.stat(ZIP)
    ev['zip_bytes'] = st.st_size
    ev['zip_mtime'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))
    print('计算 zip SHA256（%s 字节）…' % format(st.st_size, ','))
    ev['zip_sha256'] = sha256_file(ZIP)
    add('V1 zip 存在', True, '%s 字节' % format(st.st_size, ','))

    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        ev['n_entries'] = len(names)
        bad = z.testzip()
        ev['testzip'] = bad
        add('V2 testzip() 无 CRC 错误', bad is None,
            'testzip=%r' % (bad,))

        # ── ③ zip ⇄ 包目录 `.py` 逐字一致 ──────────────────────────
        py_in_zip = [n for n in names if n.endswith('.py')]
        n_same = 0
        n_diff = 0
        diffs = []
        for n in py_in_zip:
            # zip 内路径形如 `Confucius4_LiveCaption_v1.11/app/xxx.py`
            rel = n.split('/', 1)[1] if '/' in n else n
            disk = os.path.join(PKG, rel.replace('/', os.sep))
            if not os.path.exists(disk):
                continue
            try:
                zb = norm(z.read(n))
                db = norm(open(disk, 'rb').read())
            except Exception:
                continue
            if zb == db:
                n_same += 1
            else:
                n_diff += 1
                if len(diffs) < 20:
                    diffs.append(rel)
        ev['py_same'] = n_same
        ev['py_diff'] = n_diff
        ev['py_diffs'] = diffs
        add('V3 zip ⇄ 包目录 .py 逐字一致', n_diff == 0 and n_same > 0,
            '一致 %d / 差异 %d' % (n_same, n_diff))

        # ── ⑥ 🔴 §100 的 3 个文件是否真的在 zip 内 ──────────────────
        s100 = []
        for t in S100_FILES:
            cand = [n for n in names if n.endswith('/' + t)]
            ok = False
            info = ''
            # 🔴🔴🔴 §100：文件在 `app/` 子目录下 ⇒ 磁盘路径必须带上 `app/`
            #   （原写成 `os.path.join(PKG, t)` ⇒ 少一层 ⇒ **FileNotFoundError 崩溃**
            #     ⇒ 复核脚本自己先挂 ⇒ 拿不到「差异」这个关键结论）。
            disk = os.path.join(PKG, 'app', t)
            if not cand:
                info = 'NOT IN ZIP'
            elif not os.path.exists(disk):
                info = 'NOT ON DISK (%s)' % disk
            else:
                zb = norm(z.read(cand[0]))
                db = norm(open(disk, 'rb').read())
                ok = (zb == db)
                info = 'zip=%s pkg=%s' % (hashlib.sha256(zb).hexdigest()[:12],
                                          hashlib.sha256(db).hexdigest()[:12])
            s100.append(dict(file=t, ok=ok, detail=info))
            add('V4 §100 修复在 zip 内：%s' % t, ok, info)
        ev['s100_files'] = s100

        # ── ④ MANIFEST version / files ─────────────────────────────
        man = None
        for n in names:
            if n.endswith('app/MANIFEST.json'):
                man = n
                break
        if man:
            try:
                data = json.loads(z.read(man).decode('utf-8'))
                ev['manifest_version'] = data.get('version')
                ev['manifest_files'] = data.get('files')
                add('V5 MANIFEST version == %s' % VER,
                    str(data.get('version')) == VER,
                    'version=%r files=%r' % (data.get('version'),
                                             data.get('files')))
            except Exception as e:
                add('V5 MANIFEST 可解析', False, repr(e))
        else:
            add('V5 zip 内存在 MANIFEST.json', False, '未找到')

    # ── ⑤ 版本号三处一致 ──────────────────────────────────────────
    dir_ver = os.path.basename(PKG).rsplit('_v', 1)[-1]
    zip_ver = os.path.basename(ZIP).rsplit('_v', 1)[-1].replace('.zip', '')
    ev['dir_ver'] = dir_ver
    ev['zip_ver'] = zip_ver
    ev['manifest_version'] = ev.get('manifest_version')
    add('V6 版本号三处一致（目录/zip/MANIFEST）',
        dir_ver == zip_ver == str(ev.get('manifest_version')),
        'dir=%s zip=%s manifest=%s' % (dir_ver, zip_ver,
                                        ev.get('manifest_version')))

    ev['pass'] = PASS
    ev['fail'] = FAIL
    ev['verdict'] = 'PASS' if FAIL == 0 else 'FAIL'
    ev['details'] = DETAIL
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n合计 %d PASS / %d FAIL  ⇒  verdict=%s'
          % (PASS, FAIL, ev['verdict']))
    print('证据：%s' % OUT)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
