#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP-045② 验收：**桌面快捷方式**更新（含 .lnk 字节正确性 + 验收门）。

🔴 **为什么必须验 .lnk 的字节正确性**：
  我们**不能**用 COM（`WScript.Shell` 被安全策略拦截）⇒ 自己按 MS-SHLLINK
  拼字节 ⇒ **字节拼错 ⇒ 桌面出现一个打不开的图标** ⇒ 比不建更糟。
  ⇒ 判据必须能**独立解析**我们写出的字节，并还原出目标路径。

🔴 **判据**：
  ① `.lnk` 字节自洽：按 MS-SHLLINK 结构解出 Header/StringData，
     **能还原出目标路径**（`...\\Start_LiveCaption.bat`）；
  ② **只保留一个**：更新后桌面**有且仅有 1 个**「Confucius4 实时字幕*」快捷方式；
  ③ **名称带版本号**：文件名形如 `Confucius4 实时字幕 v1.13.lnk`；
  ④ **旧的被清理**：旧的「Confucius4 实时字幕.lnk」（无版本号）消失；
  ⑤ **幂等**：再跑一次 ⇒ 不重复重建（内容不变）；
  ⑥ 🔴 **未通过真机验收 ⇒ 不指过去**（删掉 `ACCEPTED.json` ⇒
     快捷方式**保持原样**，不改动）；
  ⑦ **反证**：把验收门判据改成「恒真」⇒ 判据⑥ 必须 FAIL
     ⇒ 证明判据⑥ 不是恒真。

🔴 **执行纪律**：本脚本**只动沙箱桌面目录**（把 `desktop_dir()` 换掉）
  ⇒ **绝不碰用户真实桌面**。

用法：
    python app163_app045_shortcut_update.py
    python app163_app045_shortcut_update.py --falsify
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MOD_PY = os.path.join(REPO, 'shortcut_update.py')


def _build_ns(src_text, mod_name='shortcut_update'):
    """抽模块源码 + exec（**不 import 被测模块**）。"""
    tree = ast.parse(src_text)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            keep.append(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    keep.append(node)
                    break
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            keep.append(node)
    mod = ast.Module(body=keep, type_ignores=[])
    ns = {'__file__': MOD_PY, '__name__': mod_name}
    exec(compile(mod, '<extracted>', 'exec'), ns)
    return ns


def parse_lnk_strings(data: bytes):
    """独立解析 .lnk 的 StringData（**不复用被测代码** ⇒ 真判据）。"""
    out = []
    # 🔴 MS-SHLLINK：Header 共 **76 字节**（**含** LinkFlags）
    #    ⇒ StringData 从偏移 **76** 开始（不是 80！）
    off = 76
    # StringData：NameString / RelativePath / WorkingDir / Arguments / IconLocation
    #   每项 = 2 字节字符数 + UTF-16LE（**无终止符**）
    for _ in range(5):
        if off + 2 > len(data):
            break
        (nchars,) = struct.unpack_from('<H', data, off)
        off += 2
        nb = nchars * 2
        if nb == 0 or off + nb > len(data):
            break
        out.append(data[off:off + nb].decode('utf-16-le', errors='replace'))
        off += nb
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--falsify', action='store_true')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    results = []

    def rec(name, ok, detail):
        results.append(dict(name=name, ok=bool(ok), detail=detail))
        print(('  PASS  ' if ok else '  FAIL  ') + name + ' :: ' + detail)

    print('=' * 74)
    print('APP-045② 桌面快捷方式更新 —— 验收')
    print('  falsify =', args.falsify)
    print('=' * 74)

    src = open(MOD_PY, 'r', encoding='utf-8').read()
    if args.falsify:
        # 🔴 反证：把**整个** `is_accepted` 改成**恒真**（假装已验收）
        #   ⚠️ 不能只改第一道门 —— 后面的 `json.load` 异常分支仍会
        #      `return False` ⇒ 反证**不生效** ⇒ 判据恒 PASS（假通过）。
        #   ⇒ 必须**整函数替换**。
        i = src.find('def is_accepted(pkg_dir: str) -> bool:')
        j = src.find('\ndef ', i + 10)
        assert i > 0 and j > i, '未找到 is_accepted 函数边界'
        src = (src[:i]
               + 'def is_accepted(pkg_dir: str) -> bool:\n'
                 '    return True  # [反证] 验收门恒真\n'
               + src[j:])
        print('  [反证] 已注入：is_accepted 恒真（整函数替换）')

    ns = _build_ns(src)

    # ── 沙箱：假桌面 + 假包目录 ────────────────────────────────────
    sandbox = tempfile.mkdtemp(prefix='app163_sandbox_')
    desk = os.path.join(sandbox, 'Desktop')
    pkg = os.path.join(sandbox, 'Confucius4_LiveCaption_v1.13')
    os.makedirs(desk)
    os.makedirs(pkg)
    bat = os.path.join(pkg, 'Start_LiveCaption.bat')
    with open(bat, 'w', encoding='utf-8') as f:
        f.write('@echo off\n')
    os.makedirs(os.path.join(pkg, 'python'), exist_ok=True)
    with open(os.path.join(pkg, 'python', 'pythonw.exe'), 'wb') as f:
        f.write(b'MZ')

    # 🔴 把桌面目录换成沙箱（**绝不碰真实桌面**）
    ns['desktop_dir'] = lambda: desk

    # ── 预置「旧的」无版本号快捷方式（模拟 v1.5 现状）──────────────
    legacy = os.path.join(desk, 'Confucius4 实时字幕.lnk')
    with open(legacy, 'wb') as f:
        f.write(ns['build_lnk'](target=r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\Start_LiveCaption.bat',
                                workdir=r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5',
                                icon=r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\python\pythonw.exe',
                                description='v1.5 客户包 / Intel GPU / NPU / NVIDIA CUDA',
                                name='Confucius4 实时字幕'))

    # ── 判据 ⑥ 前置：**没有** ACCEPTED.json ⇒ 不该更新 ────────────
    r0 = ns['update_desktop_shortcut'](pkg, '1.13')
    lnks_after0 = sorted(f for f in os.listdir(desk) if f.lower().endswith('.lnk'))
    rec('判据⑥a 未验收 ⇒ 不更新（保持原样）',
        (not r0.get('ok')) and lnks_after0 == ['Confucius4 实时字幕.lnk'],
        'ret.ok=%r 桌面=%r' % (r0.get('ok'), lnks_after0))

    # ── 写入验收标记 ───────────────────────────────────────────────
    with open(os.path.join(pkg, ns['ACCEPTED_MARKER']), 'w', encoding='utf-8') as f:
        json.dump({'accepted': True, 'version': '1.13'}, f)

    # ── 执行更新 ───────────────────────────────────────────────────
    r1 = ns['update_desktop_shortcut'](pkg, '1.13')
    rec('判据⑥b 已验收 ⇒ 更新成功', bool(r1.get('ok')),
        'reason=%r' % r1.get('reason'))

    # ── 判据 ②：只保留一个 ────────────────────────────────────────
    lnks = sorted(f for f in os.listdir(desk) if f.lower().endswith('.lnk')
                  and f.startswith('Confucius4 实时字幕'))
    rec('判据② 只保留一个快捷方式', len(lnks) == 1,
        '桌面=%r' % (lnks,))

    # ── 判据 ③：名称带版本号 ──────────────────────────────────────
    rec('判据③ 名称带版本号', lnks == ['Confucius4 实时字幕 v1.13.lnk'],
        '实际=%r' % (lnks,))

    # ── 判据 ④：旧的被清理 ────────────────────────────────────────
    rec('判据④ 旧的无版本号快捷方式已删除', not os.path.isfile(legacy),
        'legacy 存在=%r' % os.path.isfile(legacy))

    # ── 判据 ①：.lnk 字节自洽（独立解析）──────────────────────────
    new_lnk = os.path.join(desk, lnks[0]) if lnks else ''
    if new_lnk and os.path.isfile(new_lnk):
        data = open(new_lnk, 'rb').read()
        strs = parse_lnk_strings(data)
        target = strs[1] if len(strs) > 1 else ''
        rec('判据①a .lnk 头部长度正确（76 字节）',
            len(data) > 76 and struct.unpack_from('<I', data, 0)[0] == 0x4C,
            'HeaderSize=%r 实际字节=%d' % (struct.unpack_from('<I', data, 0)[0],
                                          len(data)))
        rec('判据①b 独立解析能还原目标路径',
            target.endswith('Start_LiveCaption.bat')
            and 'v1.13' in target and os.path.isfile(target),
            '还原目标=%r' % target)
        rec('判据①c 名称串正确', bool(strs) and strs[0] == 'Confucius4 实时字幕 v1.13',
            'name=%r' % (strs[0] if strs else None))
        # 反解函数也要能读出来（幂等判据依赖它）
        back = ns['lnk_target_of'](new_lnk)
        rec('判据①d lnk_target_of 反解一致',
            os.path.normcase(back) == os.path.normcase(target),
            '反解=%r 期望=%r' % (back, target))
    else:
        rec('判据① .lnk 字节自洽', False, '快捷方式文件不存在')

    # ── 判据 ⑤：幂等 ──────────────────────────────────────────────
    before = os.path.getmtime(new_lnk) if os.path.isfile(new_lnk) else 0
    with open(new_lnk, 'rb') as f:
        content_before = f.read()
    r2 = ns['update_desktop_shortcut'](pkg, '1.13')
    with open(new_lnk, 'rb') as f:
        content_after = f.read()
    rec('判据⑤ 幂等（重复执行不改内容）',
        content_before == content_after and '幂等' in (r2.get('reason') or ''),
        'reason=%r 内容相同=%r' % (r2.get('reason'), content_before == content_after))

    # ── 汇总 ────────────────────────────────────────────────────────
    shutil.rmtree(sandbox, ignore_errors=True)
    npass = sum(1 for r in results if r['ok'])
    nfail = len(results) - npass
    verdict = 'PASS' if nfail == 0 else 'FAIL'
    print('-' * 74)
    print('PASS=%d FAIL=%d verdict=%s' % (npass, nfail, verdict))

    out = dict(schema='app.app045.shortcut_update.v1',
               pass_=npass, fail=nfail, verdict=verdict,
               falsify=bool(args.falsify), checks=results)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.out)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
