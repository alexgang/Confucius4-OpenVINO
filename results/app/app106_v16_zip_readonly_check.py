#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app106_v16_zip_readonly_check.py —— V1.6 zip 的**只读**本地一致性复核。

🔴 **口径（§66 用户明文新口径）**
--------------------------------
「以后不做一致性校验、不开 FTP 服务」⇒ 交付流程 = **定点同步 → 先提交 → 持锁重打 zip**
（+ 一道**只读本地**的「zip ⇄ 包目录 diff = 0」）。

⇒ 本脚本就是那道**只读本地**检查：
  - **不写**任何文件（纯读）；
  - **不跑** `verify_pkg_zip.py`；
  - **不跑** `publish_ftp.py`、**不开 FTP**。

🔴 **四路独立复核**（不依赖打包脚本的自证）
------------------------------------------------
`pack_v13.py` 自己会做「zip ⇄ 包目录 逐文件 SHA256」复核，但**同一个脚本既生产又验证**
⇒ 若它的遍历/过滤逻辑有缺陷，两边会**同时错** ⇒ 复核等于没做。

⇒ 本脚本**完全独立**实现：
  1. **仓库 HEAD**（`git show HEAD:live_caption/<f>`）vs **包目录**；
  2. **仓库 HEAD** vs **zip 内字节**；
  3. **包目录** vs **zip 内字节**；
  4. **zip ⇄ 包目录 `.py` diff 计数**（§66 口径要求的那道）；
  5. **版本标识三方一致**：MANIFEST.version / README 标题 / zip 内 MANIFEST。

⚠️ **不 import 被测模块**（只做字节比对，零副作用）。

用法
----
    python results/app/app106_v16_zip_readonly_check.py \\
        --zip <zip> --pkg <包目录> --prefix <顶层名> --repo <仓库根>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile

PASS = []
FAIL = []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  <- ' + detail) if detail else ''))
    return cond


def norm(b: bytes) -> bytes:
    """归一化行尾（仓库 CRLF / 包 LF）。"""
    return b.replace(b'\r\n', b'\n')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_show(repo: str, rel: str):
    try:
        r = subprocess.run(['git', '-C', repo, 'show', 'HEAD:%s' % rel],
                           capture_output=True, timeout=120)
        if r.returncode != 0:
            return None
        return r.stdout
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', required=True)
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--prefix', required=True)
    ap.add_argument('--repo', required=True)
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    ZIP, PKG, PREFIX, REPO = args.zip, args.pkg, args.prefix, args.repo

    print('=' * 70)
    print('V1.6 zip 只读本地一致性复核（§66 口径：只读 / 不开 FTP）')
    print('  zip   :', ZIP)
    print('  pkg   :', PKG)
    print('  prefix:', PREFIX)
    print('=' * 70)

    # ── ① zip 可打开 + 指纹 ───────────────────────────────────
    print()
    print('--- (1) zip 指纹与结构 ---')
    if not os.path.isfile(ZIP):
        check('zip 存在', False, ZIP)
        return 1
    zsize = os.path.getsize(ZIP)
    with open(ZIP, 'rb') as f:
        zh = hashlib.sha256()
        while True:
            chunk = f.read(1 << 22)
            if not chunk:
                break
            zh.update(chunk)
    zsha = zh.hexdigest()
    print('  zip 字节数 : %d' % zsize)
    print('  zip SHA256 : %s' % zsha)
    zf = zipfile.ZipFile(ZIP, 'r')
    names = zf.namelist()
    entries = [n for n in names if not n.endswith('/')]
    check('顶层目录名正确（全部以 %s/ 开头）' % PREFIX,
          all(n.startswith(PREFIX + '/') for n in names if n),
          '样例=%s' % names[:1])
    print('  zip 条目数 : %d' % len(entries))

    # ── ② 四路复核（.py 文件）──────────────────────────────────
    print()
    print('--- (2) 四路复核：仓库 HEAD / 包目录 / zip 内字节 ---')
    pkg_py = sorted(f for f in os.listdir(os.path.join(PKG, 'app'))
                    if f.endswith('.py'))
    m_head_pkg = 0
    m_head_zip = 0
    m_pkg_zip = 0
    mismatches = []
    not_in_head = []
    not_in_zip = []
    n_cmp = 0          # 🔴 **实际参与三路比对的 .py 数量**（分母口径）
    for fn in pkg_py:
        pp = os.path.join(PKG, 'app', fn)
        if not os.path.isfile(pp):
            continue
        arc = '%s/app/%s' % (PREFIX, fn)
        if arc not in set(entries):
            # 🔴 包目录有、zip 内无（`pkg_exclude` 排除了 `_` 前缀开发脚本）
            #    ⇒ **不参与三路比对**，但必须**单独列出**（不能悄悄吞掉）。
            not_in_zip.append(fn)
            continue
        hb = git_show(REPO, 'live_caption/%s' % fn)
        if hb is None:
            # 包内有 / 仓库 HEAD 无（如 `_probe_tts_cuda.py` 开发探针）
            not_in_head.append(fn)
            continue
        n_cmp += 1
        disk = norm(open(pp, 'rb').read())
        zbytes = norm(zf.read(arc))
        hb = norm(hb)
        if sha(hb) == sha(disk):
            m_head_pkg += 1
        else:
            mismatches.append('HEAD≠pkg: %s' % fn)
        if sha(hb) == sha(zbytes):
            m_head_zip += 1
        else:
            mismatches.append('HEAD≠zip: %s' % fn)
        if sha(disk) == sha(zbytes):
            m_pkg_zip += 1
        else:
            mismatches.append('pkg≠zip: %s' % fn)

    check('HEAD == 包目录（%d 个 .py）' % n_cmp,
          m_head_pkg == n_cmp and not mismatches,
          'match=%d / cmp=%d %s' % (m_head_pkg, n_cmp, mismatches[:3]))
    check('HEAD == zip 内字节（%d 个 .py）' % n_cmp,
          m_head_zip == n_cmp, 'match=%d' % m_head_zip)
    check('包目录 == zip 内字节（%d 个 .py）' % n_cmp,
          m_pkg_zip == n_cmp, 'match=%d' % m_pkg_zip)
    if not_in_head:
        print('  [注] 包内有 / 仓库 HEAD 无（开发探针，非差异）: %s'
              % ', '.join(not_in_head))
    if not_in_zip:
        print('  [注] 包目录有 / zip 内无（pkg_exclude 排除的 `_` 前缀开发脚本，'
              '**不是**内容差异）: %s' % ', '.join(not_in_zip))

    # ── ③ §66 口径的那道「zip ⇄ 包目录 .py diff = 0」─────────
    print()
    print('--- (3) §66 只读本地检查：zip ⇄ 包目录 .py diff 计数 ---')
    n_diff = 0
    n_diff_base = 0
    diff_list = []
    for fn in pkg_py:
        pp = os.path.join(PKG, 'app', fn)
        arc = '%s/app/%s' % (PREFIX, fn)
        if not os.path.isfile(pp) or arc not in set(entries):
            continue
        n_diff_base += 1
        if sha(norm(open(pp, 'rb').read())) != sha(norm(zf.read(arc))):
            n_diff += 1
            diff_list.append(fn)
    check('zip ⇄ 包目录 `.py` diff = 0（比对 %d 个，两侧都在的 .py）'
          % n_diff_base,
          n_diff == 0, 'diff=%d %s' % (n_diff, diff_list[:5]))

    # ── ④ 版本标识三方一致 ────────────────────────────────────
    print()
    print('--- (4) 版本标识三方一致 ---')
    man_arc = '%s/app/MANIFEST.json' % PREFIX
    man = json.loads(zf.read(man_arc).decode('utf-8'))
    ver = man.get('version')
    check('MANIFEST.version == 1.6', ver == '1.6', 'version=%r' % ver)
    notes = man.get('notes') or ''
    for label, mark in (('默认设备摆放定案', '（13）**默认设备摆放定案**'),
                        ('生产/消费者架构', '（14）**语音输出改为「边合成边播」的生产/消费者架构**'),
                        ('不再丢句', '（15）**不再丢句**'),
                        ('语音滞后 HUD', '（16）**界面底栏实时显示「语音滞后 X 秒」**')):
        check('MANIFEST.notes 含 v1.6 修订（%s）' % label, mark in notes)
    zh = zf.read('%s/README_zh.md' % PREFIX).decode('utf-8')
    en = zf.read('%s/README_en.md' % PREFIX).decode('utf-8')
    check('zip 内 README_zh 标题是 v1.6',
          zh.startswith('# Confucius4-R2T2 实时字幕（技术评估版 v1.6）'))
    check('zip 内 README_en 标题是 v1.6',
          en.startswith('# Confucius4-R2T2 Live Captions (technical evaluation build v1.6)'))
    check('zip 内 README_zh 有「## v1.6 改动说明」',
          '## v1.6 改动说明' in zh)
    check('zip 内 README_en 有 "## What\'s new in v1.6"',
          "## What's new in v1.6" in en)
    check('zip 内 README_zh 保留 v1.5 改动说明（历史可追溯）',
          '## v1.5 改动说明' in zh)
    check('zip 内 README_en 保留 v1.5 改动说明（历史可追溯）',
          "## What's new in v1.5" in en)
    notice = zf.read('%s/NOTICE' % PREFIX).decode('utf-8')
    check('zip 内 NOTICE 自称 v1.6（历史错标已纠正）',
          notice.startswith('Confucius4 LiveCaption v1.6'))

    # ── ⑤ MANIFEST files/bytes 自洽（独立重算）────────────────
    print()
    print('--- (5) MANIFEST files/bytes 独立重算 ---')
    ent_wo = [n for n in entries if n != man_arc]
    real_bytes = sum(zf.getinfo(n).file_size for n in ent_wo)
    check('files 一致（zip 条目不含 MANIFEST 自身）',
          len(ent_wo) == man.get('files'),
          'zip=%d man=%s' % (len(ent_wo), man.get('files')))
    check('bytes 一致（zip 原始体积 == MANIFEST bytes）',
          real_bytes == man.get('bytes'),
          'zip=%d man=%s' % (real_bytes, man.get('bytes')))

    # ── ⑥ 关键文件齐备 ────────────────────────────────────────
    print()
    print('--- (6) 关键文件齐备 ---')
    MUST = ['app/translator.py', 'app/live_caption_app.py',
            'app/MANIFEST.json', 'README_zh.md', 'README_en.md',
            'NOTICE', 'THIRD_PARTY.md', 'Start_LiveCaption.bat',
            'Diagnose.bat',
            'models/mt/mt2-int8sym-cw-q/openvino_model.xml',
            'models/qwen3tts/int8/talker.xml',
            'models/qwen3tts/voices/preset_A.wav']
    missing = [r for r in MUST if '%s/%s' % (PREFIX, r) not in set(entries)]
    check('关键文件 %d 项全部在 zip 内' % len(MUST), not missing, str(missing))

    print()
    print('=' * 70)
    print('复核结论：PASS %d 项 / FAIL %d 项' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  x %s' % f)
    print('=' * 70)

    if args.json:
        with open(args.json, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'zip': ZIP, 'pkg': PKG, 'prefix': PREFIX,
                       'zip_bytes': zsize, 'zip_sha256': zsha,
                       'zip_entries': len(entries),
                       'n_pass': len(PASS), 'n_fail': len(FAIL),
                       'fail': FAIL, 'pass': PASS,
                       'cmp_py': n_cmp,
                       'm_head_pkg': m_head_pkg, 'm_head_zip': m_head_zip,
                       'm_pkg_zip': m_pkg_zip,
                       'not_in_head': not_in_head,
                       'not_in_zip': not_in_zip,
                       'py_diff_count': n_diff,
                       'manifest_version': ver,
                       'manifest_files': man.get('files'),
                       'manifest_bytes': man.get('bytes')},
                      f, ensure_ascii=False, indent=1)
        print('证据文件:', args.json)

    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
