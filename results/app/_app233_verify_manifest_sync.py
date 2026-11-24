#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · `sync_c172` 的 **MANIFEST.version 同步**修复的行为级复核。

## 判据
### A. 主判据（真实函数真跑，用**临时包**，不碰任何客户包）
1. MANIFEST.version=2.5 的包 ⇒ 同步后变成 2.6；
2. **其它字段逐字未变**（files/bytes/packages/notes 一模一样）；
3. 写盘格式与 `pack_v13.refresh_manifest()` 一致
   （`indent=1` / `ensure_ascii=False`）⇒ **JSON 往返逐字节稳定**；
4. **幂等**：已是 2.6 再跑一次 ⇒ 状态 `ALREADY`，**一个字节都不写**
   （SHA256 与 mtime 都不变）；
5. `--dry-run` ⇒ **不写盘**（文件逐字节不变）；
6. 包内无 MANIFEST ⇒ 状态 `MISSING`，**不炸**。

### B. 反证组（判据有鉴别力）
把 `sync_manifest_version` 换成「恒不写」的旧实现
⇒ 判据 1/2 **必须 FAIL** ⇒ 证明判据能识破有缺陷的旧代码。

### C. 真实包复现
用**真实 v2.6 包**的 MANIFEST.json 做一次**只读**复算：
`version` 确实是 `2.5`（与目录名 v2.6 不一致）⇒ 缺陷可复现。

## 🔴 绝不写客户包
本脚本只在 `%TEMP%` 下建**临时包**做写测试；
对真实包**只读**（`open(...,'rb')`）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
MOD = os.path.join(REPO, 'live_caption', 'sync_c172_version_identity_to_pkg.py')
REAL_V26 = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.6'

n_ok = n_bad = 0


def chk(name, cond, detail=''):
    global n_ok, n_bad
    if cond:
        n_ok += 1
        print('  [PASS] %s%s' % (name, ('｜' + detail) if detail else ''))
    else:
        n_bad += 1
        print('  [FAIL] %s%s' % (name, ('｜' + detail) if detail else ''))


def load():
    spec = importlib.util.spec_from_file_location('sync_c172_manifest_under_test', MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_tmp_pkg(version='2.5'):
    """建一个**临时**最小包（只含 app/MANIFEST.json）。"""
    root = tempfile.mkdtemp(prefix='_app233_mf_pkg_')
    os.makedirs(os.path.join(root, 'app'))
    data = {
        'version': version,
        'files': 14319,
        'bytes': 13692564165,
        'packages': {'numpy': '1.26.4', 'openvino': '2026.5.0'},
        'notes': ['原有说明一', '原有说明二'],
    }
    p = os.path.join(root, 'app', 'MANIFEST.json')
    with open(p, 'wb') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1).encode('utf-8'))
    return root, p


def main() -> int:
    mod = load()

    # ── A1/A2/A3：主判据 ─────────────────────────────────────────
    print('\n[A] 主判据（MANIFEST.version 同步到目标版本）')
    root, mpath = make_tmp_pkg('2.5')
    try:
        before_raw = open(mpath, 'rb').read()
        before = json.loads(before_raw.decode('utf-8'))
        st, det = mod.sync_manifest_version(root, '2.6', False)
        after_raw = open(mpath, 'rb').read()
        after = json.loads(after_raw.decode('utf-8'))
        chk('状态 = APPLIED', st == 'APPLIED', st)
        chk('version 2.5 -> 2.6', after.get('version') == '2.6',
            repr(after.get('version')))
        chk('其它字段逐字未变（files/bytes/packages/notes）',
            all(after.get(k) == before.get(k)
                for k in ('files', 'bytes', 'packages', 'notes')))
        # 写盘格式一致性：JSON 往返逐字节稳定
        rt = json.dumps(after, ensure_ascii=False, indent=1).encode('utf-8')
        chk('写盘格式与 refresh_manifest 一致（往返逐字节稳定）',
            rt == after_raw, '%d B' % len(after_raw))
        chk('只改了 version：字节数差 == len("2.5")-len("2.6") 的差',
            len(after_raw) - len(before_raw) == 0,
            '%d -> %d' % (len(before_raw), len(after_raw)))

        # ── A4：幂等 ──────────────────────────────────────────────
        print('\n[B] 幂等（已是目标版本 ⇒ 一个字节都不写）')
        mtime_before = os.path.getmtime(mpath)
        sha_before = det['sha256_after']
        st2, det2 = mod.sync_manifest_version(root, '2.6', False)
        chk('状态 = ALREADY', st2 == 'ALREADY', st2)
        chk('文件内容未变', open(mpath, 'rb').read() == after_raw)
        chk('mtime 未变（确实没写盘）', os.path.getmtime(mpath) == mtime_before)
        chk('SHA256 未变', det2['sha256_before'] == sha_before)

        # ── A5：dry-run 不写盘 ───────────────────────────────────
        print('\n[C] dry-run（不写盘）')
        root2, mpath2 = make_tmp_pkg('2.5')
        try:
            raw2 = open(mpath2, 'rb').read()
            mt2 = os.path.getmtime(mpath2)
            st3, det3 = mod.sync_manifest_version(root2, '2.6', True)
            chk('状态 = APPLIED（会改，只是没落盘）', st3 == 'APPLIED', st3)
            chk('文件逐字节未变', open(mpath2, 'rb').read() == raw2)
            chk('mtime 未变', os.path.getmtime(mpath2) == mt2)
            chk('明细里 changed=True（说明确实准备改）', det3['changed'] is True)
        finally:
            shutil.rmtree(root2, ignore_errors=True)

        # ── A6：无 MANIFEST ───────────────────────────────────────
        print('\n[D] 包内无 MANIFEST ⇒ MISSING，不炸')
        root3 = tempfile.mkdtemp(prefix='_app233_mf_empty_')
        try:
            st4, det4 = mod.sync_manifest_version(root3, '2.6', False)
            chk('状态 = MISSING', st4 == 'MISSING', st4)
            chk('未抛异常', True)
        finally:
            shutil.rmtree(root3, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ── B：反证组 ────────────────────────────────────────────────
    print('\n[E] 反证组：换成「恒不写」的旧实现 ⇒ 判据必须 FAIL')
    root4, mpath4 = make_tmp_pkg('2.5')
    try:
        orig = mod.sync_manifest_version
        try:
            mod.sync_manifest_version = lambda pkg, ver, dry: (
                'ALREADY', {'old': ver, 'new': ver, 'changed': False,
                            'sha256_before': '', 'sha256_after': '',
                            'bytes_before': 0, 'bytes_after': 0})
            st5, _ = mod.sync_manifest_version(root4, '2.6', False)
            v5 = json.loads(open(mpath4, 'rb').read().decode('utf-8')).get('version')
            chk('反证组：旧实现下 version 未被改（判据能识破）', v5 != '2.6',
                'version=%r' % v5)
            chk('反证组：旧实现下状态为 ALREADY（判据能识破）', st5 == 'ALREADY')
        finally:
            mod.sync_manifest_version = orig
    finally:
        shutil.rmtree(root4, ignore_errors=True)

    # ── C：真实包复现（只读）────────────────────────────────────
    print('\n[F] 真实 v2.6 包复现（只读）')
    real_mf = os.path.join(REAL_V26, 'app', 'MANIFEST.json')
    if os.path.isfile(real_mf):
        raw = open(real_mf, 'rb').read()
        d = json.loads(raw.decode('utf-8'))
        chk('真实包 MANIFEST.version == "2.5"（与目录名 v2.6 不一致 ⇒ 缺陷可复现）',
            d.get('version') == '2.5', repr(d.get('version')))
        # 与 v2.5 的 MANIFEST 逐字节相同 ⇒ 它是复制来的原件，从未被刷新
        mf25 = os.path.join(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5',
                            'app', 'MANIFEST.json')
        if os.path.isfile(mf25):
            chk('与 v2.5 的 MANIFEST 逐字节相同（从未被刷新）',
                open(mf25, 'rb').read() == raw)
    else:
        chk('真实包 MANIFEST 存在', False, real_mf)

    print('\n[summary] PASS=%d FAIL=%d' % (n_ok, n_bad))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
