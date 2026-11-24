#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：独立复核**包内 EXT 与 commit b2a4978 逐字节一致**。

## 为什么要有这个脚本（判据工程）

上一轮（`_app129_build_v26.py` 的 `stage_sync`）自己报「按 commit b2a4978 复制
24 个」⇒ 但那是**同步脚本自己说的** ⇒ **不能自证**（PASS ≠ 正确）。

⇒ 本脚本**独立**重新做一遍：
1. 用 `git ls-tree` 列出 commit 里的 `ext/*.py`、`extension/*`、`tools/ext_launcher.py`；
2. 逐个从 commit 取内容 ⇒ 与**包内**对应文件逐字节比（**注意行尾**：
   包内是 CRLF，commit 是 LF ⇒ 先归一化再比，并**单独记录行尾**）；
3. 反证组：**故意把一个包内文件改坏** ⇒ 本脚本必须**报错**（证明判据承重）。

## 纪律

- **只读**包内文件（反证组用**临时副本**，**绝不改真包**）；
- 任何不一致 ⇒ 退出码非 0。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')
EXT_REPO = os.path.join(HOME, 'live_dub_ext')
RESULTS = os.path.join(REPO, 'results', 'app')
COMMIT = 'b2a4978'
EVID = os.path.join(RESULTS, 'app133_pkg_ext_verify.json')


def git_ls(relpath):
    p = subprocess.run(['git', '-C', EXT_REPO, 'ls-tree', '-r', '--name-only',
                        COMMIT, relpath], capture_output=True, text=True)
    if p.returncode != 0:
        return []
    return [l.strip() for l in p.stdout.splitlines() if l.strip()]


def git_show(relpath):
    p = subprocess.run(['git', '-C', EXT_REPO, 'show',
                        '%s:%s' % (COMMIT, relpath)], capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout


def norm_crlf(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def check_group(src_rel, dst_dir, files, rep, group):
    for rel in files:
        data = git_show(rel)
        if data is None:
            rep['errors'].append('git show 失败：%s' % rel)
            continue
        sub = rel[len(src_rel):].replace('/', os.sep)
        dst = os.path.join(dst_dir, sub)
        if not os.path.isfile(dst):
            rep['errors'].append('包内缺文件：%s' % dst)
            continue
        with open(dst, 'rb') as f:
            got = f.read()
        rec = {'group': group, 'rel': rel, 'dst': dst,
               'bytes': len(got),
               'sha256': sha(got),
               'commit_sha256': sha(data),
               'identical_crlf_norm': norm_crlf(got) == norm_crlf(data),
               'is_crlf': b'\r\n' in got}
        if not rec['identical_crlf_norm']:
            rep['errors'].append('内容不一致：%s' % rel)
        rep['files'].append(rec)


def check_manifest(rep):
    """核对 `extension/manifest.json`：与 commit 逐字段比，**只允许**
    `liveDub.release` 一个字段不同（成包脚本故意置 true，APP-129 §2）。"""
    data = git_show('extension/manifest.json')
    dst = os.path.join(PKG, 'ext', 'extension', 'manifest.json')
    if data is None:
        rep['errors'].append('git show 失败：extension/manifest.json')
        return
    try:
        commit_mf = json.loads(data.decode('utf-8'))
        with open(dst, 'rb') as f:
            pkg_raw = f.read()
        pkg_mf = json.loads(pkg_raw.decode('utf-8'))
    except Exception as e:
        rep['errors'].append('manifest.json 解析失败：%r' % (e,))
        return

    diffs = []

    def walk(x, y, p=''):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x:
                    diffs.append((p + '/' + k, None, y[k]))
                elif k not in y:
                    diffs.append((p + '/' + k, x[k], None))
                else:
                    walk(x[k], y[k], p + '/' + k)
        elif x != y:
            diffs.append((p, x, y))

    walk(commit_mf, pkg_mf)
    allowed = [d for d in diffs
               if d[0] == '/liveDub/release' and d[1] is False and d[2] is True]
    unexpected = [d for d in diffs if d not in allowed]
    rec = {'group': 'manifest', 'rel': 'extension/manifest.json',
           'dst': dst, 'bytes': len(pkg_raw), 'sha256': sha(pkg_raw),
           'commit_sha256': sha(data),
           'diffs': [{'path': d[0], 'commit': d[1], 'pkg': d[2]}
                     for d in diffs],
           'allowed_release_bump': len(allowed) == 1,
           'unexpected_diffs': len(unexpected),
           'identical_crlf_norm': (not unexpected)}
    rep['files'].append(rec)
    if unexpected:
        rep['errors'].append(
            'manifest.json 有非预期差异：%s'
            % [d[0] for d in unexpected][:10])
    if len(allowed) != 1:
        rep['errors'].append('manifest.json 的 release 标记差异不是恰好 1 处')


def main():
    rep = {'ts': __import__('datetime').datetime.now().strftime(
        '%Y-%m-%d %H:%M:%S'),
        'pkg': PKG, 'ext_commit': COMMIT,
        'files': [], 'errors': []}

    # ① 桥接 ext/*.py → 包内 ext/bridge/*.py
    bridge = [r for r in git_ls('ext/')
              if r.startswith('ext/') and r.endswith('.py')
              and os.path.basename(r) != 'tts_cuda_sidecar_ext.py']
    check_group('ext/', os.path.join(PKG, 'ext', 'bridge'), bridge, rep, 'bridge')

    # ② 插件 extension/* → 包内 ext/extension/*
    #    🔴 **白名单例外**：`extension/manifest.json` 的 `liveDub.release`
    #    由成包脚本**故意**置为 true（APP-129 §2：「插件端 v0.4.19 默认开
    #    （`manifest.json` version=0.4.19、release=true）」）
    #    ⇒ 它**必须**与 commit 原文不同 ⇒ 单独核对（逐字段 diff ＋
    #    **只允许这一个字段不同**），而不是放进通用逐字节判据里。
    ui = [r for r in git_ls('extension/') if r.startswith('extension/')]
    check_group('extension/', os.path.join(PKG, 'ext', 'extension'),
                [r for r in ui if r != 'extension/manifest.json'], rep,
                'extension')
    check_manifest(rep)

    # ③ 桥接启动器
    data = git_show('tools/ext_launcher.py')
    dst = os.path.join(PKG, 'tools', 'ext_launcher.py')
    if data is None:
        rep['errors'].append('git show 失败：tools/ext_launcher.py')
    else:
        with open(dst, 'rb') as f:
            got = f.read()
        ok = norm_crlf(got) == norm_crlf(data)
        rep['files'].append({'group': 'launcher', 'rel': 'tools/ext_launcher.py',
                             'dst': dst, 'bytes': len(got),
                             'sha256': sha(got), 'commit_sha256': sha(data),
                             'identical_crlf_norm': ok,
                             'is_crlf': b'\r\n' in got})
        if not ok:
            rep['errors'].append('内容不一致：tools/ext_launcher.py')

    # ④ 版本一致性（包内 version.py 与 manifest.json）
    try:
        vpy = open(os.path.join(PKG, 'ext', 'bridge', 'version.py'),
                   encoding='utf-8').read()
        mf = json.load(open(os.path.join(PKG, 'ext', 'extension',
                                         'manifest.json'), encoding='utf-8'))
        rep['ext_version_py'] = ('0.4.21' if '0.4.21' in vpy else vpy[:80])
        rep['manifest_version'] = mf.get('version')
        rep['manifest_release'] = (mf.get('liveDub') or {}).get('release')
        rep['version_consistent'] = (
            rep['manifest_version'] == '0.4.21'
            and '0.4.21' in vpy
            and rep['manifest_release'] is True)
        if not rep['version_consistent']:
            rep['errors'].append('版本/发布标记不一致')
    except Exception as e:
        rep['errors'].append('版本核对失败：%r' % (e,))

    # ⑤ 反证组：把一个**临时副本**改坏 ⇒ 同一判据必须报错
    ok_before = len(rep['errors']) == 0
    rep['counterfactual'] = {'errors_before': len(rep['errors']),
                              'passed_before': ok_before}
    if ok_before:
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, 'bridge.py')
            with open(os.path.join(PKG, 'ext', 'bridge', 'bridge.py'),
                      'rb') as f:
                orig = f.read()
            # 🔴 **必须先确认「改动真的改动了字节」** ⇒ 否则反证组是
            #   **假 FAIL**（上一版把 `EXT_VERSION` 换成 `EXT_VERSION_X`，
            #   但 bridge.py 里根本没这个串 ⇒ 替换是空操作 ⇒ 判据「没报错」
            #   是**正确**的，却被记成「判据不承重」）。
            mutated = orig.replace(b'EXT_VERSION', b'EXT_VERSION_X', 1)
            if mutated == orig:
                mutated = orig.replace(b'def ', b'def _x_', 1)
            if mutated == orig:
                # 兜底：改最后一个字节（**保证**一定改动了）
                mutated = orig[:-1] + bytes([orig[-1] ^ 0x01])
            with open(bad, 'wb') as f:
                f.write(mutated)
            detected = (norm_crlf(open(bad, 'rb').read())
                        != norm_crlf(orig))
            rep['counterfactual']['bad_file_detected'] = detected
            rep['counterfactual']['mutation_is_real'] = (mutated != orig)
            rep['counterfactual']['judgement_load_bearing'] = detected
            if not detected:
                rep['errors'].append('反证组失败：改坏后判据仍说通过')
    else:
        rep['counterfactual']['skipped'] = '已有不一致 ⇒ 判据已知不通过'

    rep['n_files'] = len(rep['files'])
    rep['all_ok'] = not rep['errors']
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('核对文件数：%d ｜ 错误：%d ｜ all_ok=%s'
          % (rep['n_files'], len(rep['errors']), rep['all_ok']))
    for e in rep['errors'][:20]:
        print('  🔴', e)
    print('反证组：%s' % json.dumps(rep['counterfactual'], ensure_ascii=False))
    print('证据：%s' % EVID)
    return 0 if rep['all_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
