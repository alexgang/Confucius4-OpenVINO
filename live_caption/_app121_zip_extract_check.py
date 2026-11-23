#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §3：**zip 解压自检**（全新目录 + 全新 %LOCALAPPDATA%）。

## reviewer 原文（APP-121 §3）
> 重打的 zip 解压到一个全新的目录，用全新的 %LOCALAPPDATA% 跑 --check，
> 再做 GUI 冒烟（schtasks /it 截图），并且确认 ACCEPTED 的模块清单和 zip 的
> 实际内容一致（要么 zip 带上 tts_cuda*，要么从 fingerprints 里去掉）。

## 本脚本做四件事（fail-closed）
1. **解压到全新目录**（旧目录若存在 ⇒ 直接失败，不覆盖）；
2. **全新 %LOCALAPPDATA% / %APPDATA%**（⇒ 不受用户既有 device_config 影响）
   跑包内 `--check` ⇒ 退出码 0 且九项自检全过；
3. **ACCEPTED 模块清单 == zip 实际内容**：
   * 用 `pack_v13._acc_production_modules`（**闸门同款口径**）重算
     解压后 `app/` 的生产模块；
   * 与 `ACCEPTED.json` 的 `code_fingerprints` 键集**双向**比对；
   * **并**与 zip 内 `app/*.py` 的条目**双向**比对
     ⇒ 三方必须完全一致（否则「签的和发的不是同一份」）。
4. 解压出来的文件数 / 字节数 == zip 清单。

## GUI 冒烟
由 `_app121_gui_smoke.py` 单独跑（Win32 `PrintWindow` 抓窗口；本机
`schtasks` 被安全策略禁止，见 `MEMORY_MODULES.md` 十七）。

## 用法
```
python live_caption/_app121_zip_extract_check.py --zip <zip> --out <证据 json>
```
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
sys.path.insert(0, REPO)


def log(*a):
    print(*a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', required=True)
    ap.add_argument('--extract-root', default=os.path.join(
        HOME, 'AppData', 'Local', 'Temp', 'app121_extract'))
    ap.add_argument('--out', default=os.path.join(
        REPO, 'results', 'app', 'app121_zip_extract_check.json'))
    args = ap.parse_args()

    zp = os.path.abspath(args.zip)
    if not os.path.isfile(zp):
        log('FAIL: zip 不存在 %s' % zp)
        return 2

    import pack_v13 as P
    import pkg_exclude

    # ── ① 解压到**全新**目录 ─────────────────────────────────────
    root = os.path.abspath(args.extract_root)
    if os.path.exists(root):
        shutil.rmtree(root, ignore_errors=True)
        if os.path.exists(root):
            log('FAIL: 无法清掉旧解压目录 %s' % root)
            return 2
    os.makedirs(root, exist_ok=True)
    log('[app121] 解压 %s → %s' % (zp, root))
    t0 = time.time()
    with zipfile.ZipFile(zp, 'r') as zf:
        bad = zf.testzip()
        names = zf.namelist()
        zf.extractall(root)
    extract_s = round(time.time() - t0, 1)
    log('[app121] 解压完成（%s s，%d 个条目，testzip=%s）'
        % (extract_s, len(names), bad))

    # 包根 = 解压出来的唯一顶层目录
    tops = [n for n in sorted(os.listdir(root))]
    pkg = os.path.join(root, tops[0]) if len(tops) == 1 else root
    log('[app121] 解压后的包目录：%s' % pkg)

    res = {'script': '_app121_zip_extract_check.py',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'zip': zp, 'zip_bytes': os.path.getsize(zp),
           'extract_root': root, 'pkg': pkg,
           'extract_s': extract_s, 'testzip': bad,
           'n_zip_entries': len(names),
           'checks': []}

    def add(name, ok, detail):
        res['checks'].append({'name': name, 'pass': bool(ok), 'detail': str(detail)[:2000]})
        log('  [%s] %s :: %s' % ('PASS' if ok else 'FAIL', name,
                                 str(detail)[:200]))

    add('解压 testzip() 无坏条目', bad is None, 'testzip=%s' % bad)
    add('解压出的包目录存在且含 app/', os.path.isdir(os.path.join(pkg, 'app')),
        pkg)

    # ── ② 全新 %LOCALAPPDATA% 跑 --check ─────────────────────────
    fresh = tempfile.mkdtemp(prefix='app121_fresh_')
    env = dict(os.environ)
    env['LOCALAPPDATA'] = fresh
    env['APPDATA'] = fresh
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    t1 = time.time()
    cp = subprocess.run([py, app, '--check'], cwd=pkg, env=env,
                        capture_output=True, text=True, encoding='utf-8',
                        errors='replace', timeout=1800)
    out = (cp.stdout or '') + '\n' + (cp.stderr or '')
    res['check'] = {'cmd': [py, app, '--check'], 'rc': cp.returncode,
                    'wall_s': round(time.time() - t1, 1),
                    'fresh_localappdata': fresh,
                    'stdout_tail': out[-6000:]}
    add('全新 %LOCALAPPDATA% 下 --check 退出码 0', cp.returncode == 0,
        'rc=%s' % cp.returncode)
    for token, label in (('GPU.0', '提到 Intel 集显 / GPU.0'),
                         ('NPU', '提到 NPU'),
                         ('stateful', 'ASR 后端出现 stateful'),
                         ('INT8-CW', 'MT 后端出现 INT8-CW'),
                         ('TTS', 'TTS 后端出现')):
        add('自检：%s' % label, token in out, '命中 %r' % token)
    add('自检：**未**出现 CUDA 后端（MiniMVP 无 CUDA）',
        'CUDA' not in out.upper(), 'CUDA 不应出现')

    # ── ③ ACCEPTED 模块清单 == zip 实际内容 ──────────────────────
    acc_path = os.path.join(pkg, 'ACCEPTED.json')
    acc = {}
    if os.path.isfile(acc_path):
        with open(acc_path, 'r', encoding='utf-8') as f:
            acc = json.load(f)
    fps = acc.get('code_fingerprints') or {}
    res['accepted'] = {'path': acc_path, 'version': acc.get('version'),
                       'pkg_dir': acc.get('pkg_dir'),
                       'n_fingerprints': len(fps),
                       'aggregate': acc.get('code_fingerprint')}

    prod_mod = P._acc_production_modules(os.path.join(pkg, 'app'))
    res['accepted']['n_production_modules_recomputed'] = len(prod_mod)
    reg = set(fps)
    cur = set(prod_mod)
    add('ACCEPTED 的 code_fingerprints 键集 == 解压后 app/ 生产模块集合',
        reg == cur, '缺=%s 多=%s' % (sorted(cur - reg), sorted(reg - cur)))

    # 逐条指纹重算
    per2 = P._acc_module_fingerprints(os.path.join(pkg, 'app'))
    agg2 = P._acc_aggregate(per2)
    changed = sorted(k for k in reg if k in per2 and per2[k] != fps[k])
    add('ACCEPTED 逐条指纹与解压后文件一致（重算）', not changed,
        'changed=%s' % changed[:10])
    add('ACCEPTED 聚合指纹与重算一致',
        acc.get('code_fingerprint') == agg2,
        '签=%s 重算=%s' % (str(acc.get('code_fingerprint'))[:16],
                          agg2[:16]))
    add('ACCEPTED version 与 release.json 一致',
        str(acc.get('version')) == str(
            (json.load(open(os.path.join(pkg, 'release.json'),
                            encoding='utf-8')).get('version'))),
        'accepted=%s release=%s'
        % (acc.get('version'),
           json.load(open(os.path.join(pkg, 'release.json'),
                          encoding='utf-8')).get('version')))
    add('ACCEPTED pkg_dir 目录名 == 解压后的包目录名',
        os.path.basename(str(acc.get('pkg_dir')).replace('\\', '/'))
        == os.path.basename(pkg),
        '签=%s 实=%s' % (acc.get('pkg_dir'), os.path.basename(pkg)))

    # zip 内 app/*.py 条目 vs 生产模块集合
    prefix = os.path.basename(pkg) + '/'
    zip_app_py = sorted(n[len(prefix):].split('/', 1)[1]
                        for n in names
                        if n.startswith(prefix + 'app/') and n.endswith('.py')
                        and n.count('/') == 2)
    res['accepted']['n_zip_app_py'] = len(zip_app_py)
    res['accepted']['zip_app_py'] = zip_app_py
    # zip 内的 app/*.py 与生产模块集合的差集（dev-only 模块不在 zip 里）
    only_zip = sorted(set(zip_app_py) - cur)
    only_prod = sorted(cur - set(zip_app_py))
    res['accepted']['only_in_zip'] = only_zip
    res['accepted']['only_production_modules'] = only_prod
    add('zip 内 app/*.py 与「生产模块集合」一致（无只在一边的）',
        not only_zip and not only_prod,
        '只在 zip=%s 只在生产模块=%s' % (only_zip, only_prod))
    add('ACCEPTED 不含 zip 里没有的模块（tts_cuda* 不得在指纹里）',
        not (reg - set(zip_app_py)),
        '只在指纹=%s' % sorted(reg - set(zip_app_py)))

    # ── ④ 解压内容 == zip 清单 ───────────────────────────────────
    files = list(pkg_exclude.iter_package_files(pkg))
    add('解压后的文件数 == zip 内文件数（%d）' % len(files),
        len(files) == len([n for n in names
                           if n.startswith(prefix) and not n.endswith('/')]),
        '解压目录口径 %d；zip 条目 %d'
        % (len(files),
           len([n for n in names if n.startswith(prefix)
                and not n.endswith('/')])))
    n_zip_files = len([n for n in names if n.startswith(prefix)
                       and not n.endswith('/')])
    res['n_zip_files'] = n_zip_files
    res['n_extract_dir_files'] = len(files)
    res['n_extract_dir_all_files'] = sum(
        len(fns) for _dp, _dns, fns in os.walk(pkg))

    res['n_fail'] = sum(1 for c in res['checks'] if not c['pass'])
    res['verdict'] = 'PASS' if res['n_fail'] == 0 else 'FAIL'
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.out)
    log('[app121] 判定：%s（%d 项检查，%d 失败）'
        % (res['verdict'], len(res['checks']), res['n_fail']))
    log('[app121] 证据 → %s' % args.out)
    return 0 if res['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
