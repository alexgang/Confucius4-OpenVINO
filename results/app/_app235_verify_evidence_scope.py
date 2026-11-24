#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-235 轮 · **行为级**独立复核 `sync_pkg_identity.py` 的「证据作用域」修复。

## 背景（APP-235 轮实测到的真缺陷，**生产路径**，不是 harness）

`live_caption/sync_pkg_identity.py` 原先**无条件**把 app170 闸门证据写到
**规范路径** `results/app/app170_version_identity_gate_evidence.json`
⇒ 在**任何**影子包 / 临时目录上跑一次，就会把「**交付包**的闸门记录」
**覆盖成影子包的结果**。

实测后果（APP-234 轮遗留的工作区改动）：
- 规范证据的 `pkg` 字段 = `%TEMP%\\app234_id_klh3m45v\\Confucius4_LiveCaption_v2.10`
  （**跑完即删** ⇒ reviewer **无法复算**）
- `pass` 从 **19** 变 **20**
- 真实包那两条**真实 advisory**（I1b / D4）**消失** ⇒ **审计链断**

## 修法

- **交付候选包** ⇒ 闸门证据写**规范文件**（与 pack_v13 的既定约定一致）
- **非交付包**（影子包 / `%TEMP%` 临时目录）⇒ 闸门证据写**临时文件**并在
  用完后删除 ⇒ ① **绝不覆盖**交付包的规范记录 ② **零仓库污染**

## 本脚本的判据

[A] 生产路径行为级：影子包 ⇒ 规范证据**逐字节不变** ＋ **零新增文件**
    ＋ 闸门**确实跑了**（不是空跑）
[B] `_is_delivery_pkg` 单元行为
[C] **反证组**：把「无条件写规范路径」的**旧行为**注入工具副本
    ⇒ 规范证据**必须**被改 ⇒ 证明 [A1] 有鉴别力（不是恒 PASS）
[D] **「非空洞」检查**：对**交付候选目录名**的包 ⇒ 规范证据**必须**被更新
    ⇒ 否则 [A1] 可能只是「因为工具根本不写规范证据」而恒 PASS
[E] 收尾：规范证据**用真实交付包重刷**并逐字节复核 ＋ 真包 4 个身份文件未变

**真包只读**：全程不写 `Confucius4_LiveCaption_v2.6` 一个字节。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
TOOL = os.path.join(REPO, 'live_caption', 'sync_pkg_identity.py')
REAL = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.6'
EVID_DIR = os.path.join(REPO, 'results', 'app')
CANON = os.path.join(EVID_DIR, 'app170_version_identity_gate_evidence.json')
GATE = os.path.join(EVID_DIR, 'app170_version_identity_gate.py')
WATCH = ('README_zh.md', 'README_en.md', 'NOTICE', 'app/MANIFEST.json')
CL_ZH = os.path.join(REPO, 'live_caption', '_app129_changelog_2.6_zh.md')
CL_EN = os.path.join(REPO, 'live_caption', '_app129_changelog_2.6_en.md')

FAILS = []
N = [0]


def chk(name, ok, detail=''):
    N[0] += 1
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('   ' + detail) if detail else ''))
    if not ok:
        FAILS.append((name, detail))


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def read(p):
    return open(p, 'rb').read().decode('utf-8')


def snap_watch(pkg):
    d = {}
    for rel in WATCH:
        p = os.path.join(pkg, rel.replace('/', os.sep))
        if os.path.isfile(p):
            d[rel] = sha(p)
    return d


def evid_files():
    """results/app 下所有 app170 闸门证据文件名（排序）。"""
    return sorted(f for f in os.listdir(EVID_DIR)
                  if f.startswith('app170_version_identity_gate_evidence'))


def make_shadow(dst):
    """复制真包的 4 个身份文件到影子目录（目录名 ⇒ 目标版本）。"""
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.join(dst, 'app'), exist_ok=True)
    for rel in WATCH:
        s = os.path.join(REAL, rel.replace('/', os.sep))
        d = os.path.join(dst, rel.replace('/', os.sep))
        if os.path.isfile(s):
            shutil.copy2(s, d)
    return dst


def run_tool(tool, pkg, extra=None):
    cmd = [sys.executable, tool, '--pkg', pkg,
           '--changelog-zh', CL_ZH, '--changelog-en', CL_EN]
    cmd += (extra or [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    return p.returncode, p.stdout, p.stderr


def main() -> int:
    print('=== APP-235 行为级复核：sync_pkg_identity 的「证据作用域」修复 ===')
    print('真包（只读）：%s' % REAL)

    try:
        ast.parse(read(TOOL))
        chk('被检脚本 ast.parse 通过', True)
    except SyntaxError as e:
        chk('被检脚本 ast.parse 通过', False, repr(e))
        return 1

    real_before = snap_watch(REAL)
    canon_before = sha(CANON)
    files_before = evid_files()

    tmp = tempfile.mkdtemp(prefix='app235_scope_')
    probe_dir = os.path.join(REPO, 'live_caption', '_app235_probe_pkg')
    old_tool = os.path.join(REPO, 'live_caption',
                            '_app235_sync_pkg_identity_OLD.py')
    try:
        # ══ [A] 影子包（%TEMP%）⇒ 规范证据必须不被覆盖 ══════════════
        print('\n[A] 影子包（%%TEMP%%\\...\\Confucius4_LiveCaption_v2.7）')
        shadow = make_shadow(os.path.join(
            tmp, 'Confucius4_LiveCaption_v2.7'))
        rc, out, err = run_tool(TOOL, shadow)
        chk('A0 工具在影子上跑通（rc=0）', rc == 0, 'rc=%d %s' % (rc, err[-200:]))
        chk('A1 规范证据**逐字节未变**（影子不得覆盖交付包记录）',
            sha(CANON) == canon_before,
            'before=%s after=%s' % (canon_before[:12], sha(CANON)[:12]))
        chk('A2 **零仓库污染**：results/app 下证据文件集合未变',
            evid_files() == files_before,
            '%s' % (evid_files(),))
        chk('A3 闸门**确实跑了**（stdout 有 app170 闸门结果）',
            'app170' in out and 'PASS=' in out,
            'has_app170=%s' % ('app170' in out))
        zh = read(os.path.join(shadow, 'README_zh.md'))
        chk('A4 影子确实被同步（README_zh 标题版本号 == 2.7）',
            'v2.7' in zh.split('\n')[0], repr(zh.split('\n')[0][:60]))

        # ══ [B] `_is_delivery_pkg` 单元行为 ═══════════════════════════
        print('\n[B] _is_delivery_pkg 单元行为')
        spec_src = read(TOOL)
        ns = {'__file__': TOOL, '__name__': 'spi_probe'}
        exec(compile(spec_src.replace('if __name__ ==',
                                      'if False and __name__ =='),
                     TOOL, 'exec'), ns)
        is_del = ns['_is_delivery_pkg']
        b_cases = [
            (REAL, True),
            (r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.10', True),
            (os.path.join(tmp, 'Confucius4_LiveCaption_v2.7'), False),
            (os.path.join(os.environ.get('TEMP', r'C:\Temp'),
                          'app235_x', 'Confucius4_LiveCaption_v2.7'), False),
            (r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.1.1',
             False),
            (r'C:\Users\Trekker-PTL\confucius4-openvino\scratch', False),
        ]
        for path, exp in b_cases:
            got = bool(is_del(path))
            chk('B _is_delivery_pkg(%s) == %s' % (os.path.basename(path), exp),
                got == exp, 'got=%s' % got)

        # ══ [C] 反证组：注入旧行为（无条件写规范路径）════════════════
        print('\n[C] 反证组：注入「无条件写规范路径」的旧行为')
        marker = ("            tmp_ev_dir = tempfile.mkdtemp("
                  "prefix='app235_gate_ev_')")
        hit = spec_src.count(marker)
        chk('C0 旧行为注入点唯一命中', hit == 1, 'hit=%d' % hit)
        if hit == 1:
            old_src = spec_src.replace(
                marker,
                "            tmp_ev_dir = None")
            old_src = old_src.replace(
                "            ev_path = os.path.join(\n"
                "                tmp_ev_dir, "
                "'app170_version_identity_gate_evidence.json')",
                "            ev_path = os.path.join(\n"
                "                REPO, 'results', 'app',\n"
                "                'app170_version_identity_gate_evidence.json')")
            chk('C0b 旧行为改写后仍能 ast.parse',
                _ast_ok(old_src))
            with open(old_tool, 'w', encoding='utf-8', newline='') as f:
                f.write(old_src)
            shadow2 = make_shadow(os.path.join(
                tmp, 'Confucius4_LiveCaption_v2.8'))
            rc2, out2, err2 = run_tool(old_tool, shadow2)
            canon_after_old = sha(CANON)
            chk('C1 旧实现**确实覆盖了**规范证据 ⇒ [A1] 判据有鉴别力',
                canon_after_old != canon_before,
                'rc=%d changed=%s err=%s' % (
                    rc2, canon_after_old != canon_before, err2[-200:]))
            # 还原规范证据
            _refresh_canon()
            chk('C2 反证组后规范证据已还原（逐字节）', sha(CANON) == canon_before)

        # ══ [D] 「非空洞」检查：交付候选目录名 ⇒ 规范证据**必须**被更新 ══
        print('\n[D] 非空洞检查（交付候选目录名 ⇒ 规范证据会被更新）')
        probe = os.path.join(probe_dir, 'Confucius4_LiveCaption_v2.99')
        make_shadow(probe)
        canon_pre_d = sha(CANON)
        rc3, out3, err3 = run_tool(TOOL, probe)
        chk('D0 工具在交付候选目录名上跑通（rc=0）', rc3 == 0,
            'rc=%d %s' % (rc3, err3[-200:]))
        chk('D1 交付候选包 ⇒ 规范证据**确实被更新**（A1 不是空洞恒 PASS）',
            sha(CANON) != canon_pre_d)
        ev2 = json.loads(read(CANON))
        chk('D2 更新后的规范证据 pkg == 交付候选目录',
            os.path.abspath(ev2.get('pkg', '')) == os.path.abspath(probe),
            'pkg=%s' % ev2.get('pkg'))
        chk('D3 同样**零额外文件**（只有规范文件被更新）',
            evid_files() == files_before, '%s' % (evid_files(),))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(probe_dir, ignore_errors=True)
        if os.path.isfile(old_tool):
            os.remove(old_tool)

    # ══ 收尾：规范证据**必须**逐字节还原成真实交付包的记录 ══════════
    print('\n[E] 收尾：规范证据还原 + 真包隔离')
    _refresh_canon()
    ev3 = json.loads(read(CANON))
    chk('E1 规范证据 pkg == 真实交付包',
        os.path.abspath(ev3.get('pkg', '')) == os.path.abspath(REAL),
        'pkg=%s' % ev3.get('pkg'))
    chk('E2 规范证据 pass==19 / fail==0（与 HEAD 记录一致）',
        ev3.get('pass') == 19 and ev3.get('fail') == 0,
        'pass=%s fail=%s' % (ev3.get('pass'), ev3.get('fail')))
    chk('E3 真实包那两条 advisory 仍在（I1b / D4）',
        len(ev3.get('advisories', [])) == 2
        and any('I1b' in a.get('name', '') for a in ev3['advisories'])
        and any('D4' in a.get('name', '') for a in ev3['advisories']),
        'n_adv=%d' % len(ev3.get('advisories', [])))
    chk('E4 真包 4 个身份文件逐字节未变', snap_watch(REAL) == real_before)
    chk('E5 results/app 下证据文件集合未变', evid_files() == files_before,
        '%s' % (evid_files(),))

    print('\nPASS=%d / FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
    print('结论：%s' % ('PASS' if not FAILS else 'FAIL'))
    return 0 if not FAILS else 1


def _ast_ok(src):
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        return False


def _refresh_canon():
    """用**真实交付包**重刷规范证据（只读真包）。"""
    p = subprocess.run(
        [sys.executable, GATE, '--pkg', REAL, '--expect-version', '2.6',
         '--json', CANON], capture_output=True, text=True, timeout=900)
    return p.returncode


if __name__ == '__main__':
    sys.exit(main())
