#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app217 —— 【APP-057 ③】建 **v2.1** 包目录（修复 v2.0 首包的「开发机绝对路径」违规）。

## 为什么要有 v2.1（不是重打 v2.0）

reviewer 原话（APP-057 ①）：

> 「任何旧版本目录和 zip 都不覆盖、不删除。不用 --same-version。」

v2.0 的 zip（2026-11-01 17:49）虽然在本轮内产生，但它**已经违反 APP-057 ③**
（`ext/bridge/{engines,segmenter,app_root}.py` 的 docstring/注释里写死了
`C:\\Users\\Trekker-PTL\\confucius4-openvino` 等开发机绝对路径）⇒
**不能当交付物** ⇒ 只能**另起新版本号**（v2.0 目录与 zip 原样保留，不删不改）。

## 本脚本做 6 件事

1. `v2.0` → `v2.1`：**models/ 与 python/ 用硬链接**（只读资产，零拷贝），
   其余（app/、ext/、docs/、results/、根文件）**真实复制**
   （🔴 代码要改 ⇒ 绝不能用硬链接，否则会连带改 v2.0）。
2. **脱敏**：把包内自有代码/文档里的**构建机家目录字面量**
   （`C:\\Users\\Trekker-PTL` / `C:\Users\Trekker-PTL` / `C:/Users/Trekker-PTL`）
   统一替换成 `<HOME>` 占位（🔴 与 APP-052 ③ 的 docstring 脱敏同一口径）。
   ⚠️ **不碰** `ACCEPTED.json`（由 app211 重签，写 `<HOME>` 形态的 pkg_dir）。
   ⚠️ **不碰** `python/`、`ext/.runtime_deps/`、`models/`（第三方运行时 / 只读资产）。
3. **同步 App 侧开发目录的修复**：`live_caption/speaker_assets.py`（APP-052 ③
   的注释里也写了开发机真家目录 ⇒ 本轮一并脱敏）⇒ 从**开发目录**复制进包
   （🔴 只在开发目录改代码；同步进包 = 走「新版本目录」这条唯一合法路径）。
4. **版本号预同步**：包内 `MANIFEST.json` / `app/MANIFEST.json` 的 `version`
   ⇒ `2.1`（否则 app211 会按旧版本号签 ACCEPTED）。
5. **重签 ACCEPTED**：调用 app211（`--pkg <v2.1>`）⇒ `pkg_dir` 记 `<HOME>` 形态。
6. **自检**：脱敏后重扫 ⇒ 构建机家目录字面量必须 **0**（不含 ACCEPTED.json）。

## 纪律

* 🔴 **不覆盖任何已存在的目录**（`v2.1` 存在即中止）。
* 🔴 **只写自己该写的**：`v2.1` 新目录 + 开发目录里的 `speaker_assets.py`
  与 `release_notes/v2.1_{zh,en}.md`；**不碰** `v2.0`、**不碰** v1.x、**不碰**
  `CORRECTIONS_APP.md`。
* 🔴 **写文件先写临时文件再原子替换**（中途异常不会把目标清空）。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = r'C:\Users\Trekker-PTL'

SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.0')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_v2.1')
VERSION = '2.1'

#: 硬链接（只读资产，零拷贝）
HARDLINK_DIRS = ('models', 'python')
#: 脱敏时**跳过**的目录（第三方运行时 / 只读资产）
SANITIZE_SKIP_DIRS = ('python', os.path.join('ext', '.runtime_deps'), 'models')
#: 脱敏时**跳过**的文件（ACCEPTED.json 由 app211 重签）
SANITIZE_SKIP_FILES = ('ACCEPTED.json',)
#: 参与脱敏的扩展名
SANITIZE_EXT = ('.py', '.json', '.md', '.cmd', '.bat', '.txt', '.lnk', '.cfg',
                '.ini', '.yaml', '.yml')
#: 构建机家目录的三种写法（docstring 里通常是**双反斜杠**）
HOME_PATTERNS = (
    'C:\\\\Users\\\\Trekker-PTL',
    'C:\\Users\\Trekker-PTL',
    'C:/Users/Trekker-PTL',
)
PLACEHOLDER = '<HOME>'

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + detail) if detail else ''))
    return bool(cond)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def atomic_write(path, data, encoding='utf-8'):
    tmp = path + '.app217_tmp'
    with open(tmp, 'wb') as f:
        f.write(data if isinstance(data, bytes) else data.encode(encoding))
    os.replace(tmp, path)


def copy_tree_link_first(src, dst):
    """models/ 与 python/ 走硬链接；其余真实复制。返回统计。"""
    n_link = n_copy = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tgt_dir = os.path.join(dst, rel) if rel != '.' else dst
        os.makedirs(tgt_dir, exist_ok=True)
        top = rel.split(os.sep)[0] if rel != '.' else ''
        use_link = top in HARDLINK_DIRS
        for fn in files:
            s = os.path.join(root, fn)
            d = os.path.join(tgt_dir, fn)
            if os.path.exists(d):
                continue
            if use_link:
                try:
                    os.link(s, d)
                    n_link += 1
                    continue
                except OSError:
                    pass
            shutil.copy2(s, d)
            n_copy += 1
    return n_link, n_copy


def sanitize_tree(root):
    """把包内自有代码/文档里的构建机家目录字面量替换成 `<HOME>`。"""
    changed = []
    total = 0
    for dp, dns, fns in os.walk(root):
        rel_dp = os.path.relpath(dp, root)
        parts = rel_dp.split(os.sep)
        skip = False
        for sk in SANITIZE_SKIP_DIRS:
            sk_parts = sk.split(os.sep)
            if parts[:len(sk_parts)] == sk_parts:
                skip = True
                break
        if skip:
            dns[:] = []
            continue
        for fn in sorted(fns):
            if not fn.lower().endswith(SANITIZE_EXT):
                continue
            if fn in SANITIZE_SKIP_FILES:
                continue
            p = os.path.join(dp, fn)
            try:
                raw = open(p, 'rb').read()
            except Exception:
                continue
            if b'\x00' in raw[:4096]:
                continue
            try:
                txt = raw.decode('utf-8')
            except UnicodeDecodeError:
                continue
            new = txt
            n = 0
            for pat in HOME_PATTERNS:
                c = new.count(pat)
                if c:
                    new = new.replace(pat, PLACEHOLDER)
                    n += c
            if n:
                atomic_write(p, new.encode('utf-8'))
                changed.append({'file': os.path.relpath(p, root), 'n': n})
                total += n
    return changed, total


def scan_home_literals(root, skip_files=()):
    hits = []
    for dp, dns, fns in os.walk(root):
        rel_dp = os.path.relpath(dp, root)
        parts = rel_dp.split(os.sep)
        for sk in SANITIZE_SKIP_DIRS:
            sk_parts = sk.split(os.sep)
            if parts[:len(sk_parts)] == sk_parts:
                dns[:] = []
                break
        else:
            for fn in fns:
                if fn in skip_files or not fn.lower().endswith(SANITIZE_EXT):
                    continue
                p = os.path.join(dp, fn)
                try:
                    raw = open(p, 'rb').read()
                except Exception:
                    continue
                if b'\x00' in raw[:4096]:
                    continue
                txt = raw.decode('utf-8', 'replace')
                for i, line in enumerate(txt.splitlines(), 1):
                    for pat in HOME_PATTERNS:
                        if pat in line:
                            hits.append({'file': os.path.relpath(p, root),
                                         'line': i, 'text': line.strip()[:160]})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--dst', default=DST)
    ap.add_argument('--json', default=os.path.join(
        HERE, 'app217_app057_v21_stage_evidence.json'))
    args = ap.parse_args()

    print('=' * 70)
    print('app217 —— APP-057 ③：建 v2.1（脱敏后的 V2.0 交付包）')
    print('源：', args.src)
    print('新：', args.dst)
    print('=' * 70)

    check('① 源目录存在', os.path.isdir(args.src), args.src)
    check('② 新目录不存在（不覆盖任何旧目录）',
          not os.path.exists(args.dst), args.dst)
    if not os.path.isdir(args.src) or os.path.exists(args.dst):
        print('\n前置条件不满足 ⇒ 中止')
        return 2

    t0 = time.time()
    n_link, n_copy = copy_tree_link_first(args.src, args.dst)
    print('\n[1] 复制完成：硬链接 %d 个 / 真实复制 %d 个（%.1f s）'
          % (n_link, n_copy, time.time() - t0))

    changed, total = sanitize_tree(args.dst)
    print('\n[2] 脱敏：%d 处（%d 个文件）' % (total, len(changed)))
    for c in changed:
        print('    %s  x%d' % (c['file'], c['n']))

    # ── 3) App 侧开发目录的修复同步进包 ───────────────────────
    dev_spk = os.path.join(REPO, 'live_caption', 'speaker_assets.py')
    pkg_spk = os.path.join(args.dst, 'app', 'speaker_assets.py')
    spk_diff = []
    if os.path.isfile(dev_spk) and os.path.isfile(pkg_spk):
        a = open(dev_spk, encoding='utf-8').read().splitlines()
        b = open(pkg_spk, encoding='utf-8').read().splitlines()
        spk_diff = [d for d in difflib.unified_diff(b, a, 'pkg', 'dev',
                                                    lineterm='', n=0)
                    if d.startswith(('+', '-')) and not d.startswith(
                        ('+++', '---'))]
        atomic_write(pkg_spk, open(dev_spk, 'rb').read())
    check('③ speaker_assets.py 已从开发目录同步（脱敏注释）',
          bool(spk_diff), '%d 行差异' % len(spk_diff))
    check('③b 同步后与开发目录逐字节一致',
          os.path.isfile(pkg_spk) and sha256_file(pkg_spk) == sha256_file(dev_spk),
          sha256_file(pkg_spk)[:16] if os.path.isfile(pkg_spk) else 'n/a')

    # ── 4) 版本号预同步 ───────────────────────────────────────
    for rel in ('MANIFEST.json', os.path.join('app', 'MANIFEST.json')):
        p = os.path.join(args.dst, rel)
        if not os.path.isfile(p):
            continue
        try:
            data = json.load(open(p, encoding='utf-8'))
        except Exception as e:
            print('    ⚠️ %s 解析失败：%s' % (rel, e))
            continue
        if 'version' in data:
            data['version'] = VERSION
            atomic_write(p, (json.dumps(data, ensure_ascii=False, indent=2)
                             + '\n').encode('utf-8'))
            print('    %s version ⇒ %s' % (rel, VERSION))

    # ── 5) 重签 ACCEPTED（app211）─────────────────────────────
    app211 = os.path.join(HERE, 'app211_app057_v20_resign_accepted.py')
    r = subprocess.run([sys.executable, app211, '--pkg', args.dst],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    print('\n[3] app211 重签：rc=%d' % r.returncode)
    tail = (r.stdout or '').strip().splitlines()[-12:]
    for line in tail:
        print('    ' + line)
    check('④ ACCEPTED.json 重签成功', r.returncode == 0,
          (r.stderr or '')[-200:] if r.returncode else '')

    # ── 6) 自检：脱敏后重扫 ───────────────────────────────────
    left = scan_home_literals(args.dst, skip_files=('ACCEPTED.json',))
    print('\n[4] 脱敏后自检：剩余构建机家目录字面量 %d 处' % len(left))
    for h in left[:10]:
        print('    %s:%d %s' % (h['file'], h['line'], h['text']))
    check('⑤ 自有代码/文档里已无构建机家目录字面量', not left,
          '%d 处' % len(left))

    acc = os.path.join(args.dst, 'ACCEPTED.json')
    acc_pkg = ''
    if os.path.isfile(acc):
        try:
            acc_pkg = json.load(open(acc, encoding='utf-8')).get('pkg_dir', '')
        except Exception:
            pass
    check('⑥ ACCEPTED.json 的 pkg_dir 用 `<HOME>` 形态（不泄漏构建机家目录）',
          acc_pkg.startswith(PLACEHOLDER), acc_pkg)

    npass = sum(1 for _n, ok, _d in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print('\n结果：%d PASS / %d FAIL' % (npass, nfail))
    out = {
        'tool': 'app217',
        'app': 'APP-057',
        'src': args.src,
        'dst': args.dst,
        'version': VERSION,
        'copied': {'hardlink': n_link, 'copy': n_copy},
        'sanitized': changed,
        'n_sanitized': total,
        'speaker_assets_diff_lines': len(spk_diff),
        'left_home_literals': left,
        'accepted_pkg_dir': acc_pkg,
        'results': [{'name': n, 'ok': ok, 'detail': d}
                    for n, ok, d in RESULTS],
        'summary': {'pass': npass, 'fail': nfail},
        'elapsed_s': round(time.time() - t0, 1),
        'at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('证据已写:', args.json)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
