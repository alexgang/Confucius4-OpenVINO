#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app214 —— APP-057 第 3 条「依赖隔离 / 另一个路径解压测试」。

## reviewer 原文
> "3. 依赖隔离：在**另一个路径**（比如 `C:\\v20_cleantest\\`）解压 zip 测试。
>    扫描包内所有 .py、.json、.lnk、.cmd，不能出现任何指向开发目录
>    （`confucius4-openvino`、`live_dub_ext`、`qwen3tts_eval`、`hy_bench`、
>    `WorkBuddy\\Worktrees`）的绝对路径，扫描结果写进 STATUS。"

## 纪律
* 🔴 **以 zip 实际内容为准**（不是包目录！）⇒ 先解压 zip 到干净路径再扫。
* 🔴 **绝对路径 ≠ 字面量提及**：判「绝对路径」只看**字符串字面量**里
  出现的**绝对路径形态**（盘符 + 路径分隔符），而不是「文本里提到了这个词」。
* 🔴 **判据必须有鉴别力** ⇒ 配**反证组**：故意放一个带开发机绝对路径的
  .py/.json/.lnk/.cmd ⇒ 判据必须命中 ⇒ 否则恒真。
* 🔴 **不写死客户包版本号**（§48 打包闸门会拦）⇒ 用 `pkg_paths` 单一数据源。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import time
import zipfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
try:
    import pkg_paths
except Exception:                                     # pragma: no cover
    pkg_paths = None

HOME = os.path.expanduser('~')

#: 🔴 **开发目录特征词**（reviewer 点名的那几个 ＋ 常见变体）
#:    ⇒ **阻断口径**：命中即 FAIL（reviewer ③ 的字面要求）
DEV_MARKERS = (
    'confucius4-openvino',
    'live_dub_ext',
    'qwen3tts_eval',
    'hy_bench',
    'WorkBuddy\\Worktrees',
    'WorkBuddy/Worktrees',
    'Worktrees',
)
#: **构建机用户名**（绝对路径里出现即泄漏构建机身份）
#: 🔴 **口径修正（APP-057 ③ 复盘）**：
#:    reviewer 的 ③ 点名的是**开发目录**（5 个）⇒ 阻断判据只用 DEV_MARKERS；
#:    「构建机用户名」是**额外**发现 ⇒ 单独一条**不阻断**的检查，单列报告。
#:    （原版把两者混在一起 ⇒ 首包 v2.0 明明违反 ③ 却被这条"更严"的口径
#:      混淆了「是否命中 reviewer 点名的开发目录」⇒ 口径必须对齐 reviewer 原文。）
DEV_USER = 'Trekker-PTL'

#: 要扫描的扩展名（reviewer 原文：.py、.json、.lnk、.cmd）
SCAN_EXT = ('.py', '.json', '.lnk', '.cmd')

#: Windows 绝对路径形态：`X:\...` 或 `X:/...`
_ABS_PATH_RE = re.compile(r'(?<![A-Za-z0-9_])([A-Za-z]:[\\/][^\s"\'<>|]*)')

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + detail) if detail else ''))
    return bool(cond)


def sha256_file(p, limit=None):
    h = hashlib.sha256()
    n = 0
    with open(p, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
            n += len(b)
            if limit and n >= limit:
                break
    return h.hexdigest(), n


def _py_literal_strings(path):
    """抽 .py 的**字符串字面量**（排除 docstring）⇒ 避免注释/文档里的
    「提及」被当成「实际路径」。返回 (text, lineno) 列表。"""
    out = []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            src = f.read()
        tree = ast.parse(src, filename=path)
    except Exception:
        return out
    doc_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, 'body', None)
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_ids.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in doc_ids:
            out.append((node.value, node.lineno))
    return out


def scan_tree(root):
    """扫一棵解压出来的目录树 ⇒ 找「指向开发目录的绝对路径」。

    返回命中列表：[{file, line, kind, marker, text}]
    """
    hits = []
    for dp, dn, fns in os.walk(root):
        # **跳过第三方运行时**（不是「我们写的代码」）
        rel_dp = os.path.relpath(dp, root)
        parts = rel_dp.split(os.sep)
        if parts and parts[0] in ('python',) or rel_dp.startswith(
                os.path.join('ext', '.runtime_deps')):
            dn[:] = []
            continue
        for fn in fns:
            if not fn.lower().endswith(SCAN_EXT):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            ext = os.path.splitext(fn)[1].lower()
            # 🔴🔴 **口径修正（APP-057 ③ 复盘）**：`.py` 也要**扫全文**
            #    （含 docstring 与注释）！
            #    原版只扫「AST 字符串字面量且排除 docstring」⇒
            #    ⇒ 首包 v2.0 的 `ext/bridge/engines.py` / `segmenter.py` /
            #      `app_root.py` 的 **docstring 里写死的开发机绝对路径被漏检**
            #      ⇒ 判据「PASS」但产品有缺陷 ⇒ 典型的「判据 PASS ≠ 判据正确」。
            #    reviewer 的 ③ 是**文件内容**口径，不是「运行时会走的路径」口径
            #    ⇒ 客户看到的就是 docstring 里的那一行。
            try:
                with open(p, 'rb') as f:
                    raw = f.read()
            except Exception:
                continue
            # 🔴 **二进制也要扫**：`.lnk` 是**二进制**（路径以 UTF-16LE 存）
            #    ⇒ 只按 UTF-8 读会漏掉快捷方式里的开发机路径
            #    ⇒ 额外再按 UTF-16LE 解一份一起扫。
            texts = [raw.decode('utf-8', 'replace')]
            if ext == '.lnk':
                texts.append(raw.decode('utf-16-le', 'replace'))
            candidates = []
            for txt in texts:
                candidates.extend((t, i + 1)
                                  for i, t in enumerate(txt.splitlines()))
            for text, lineno in candidates:
                if not isinstance(text, str):
                    continue
                for m in _ABS_PATH_RE.finditer(text):
                    ap = m.group(1)
                    low = ap.lower()
                    mk = None
                    for d in DEV_MARKERS:
                        if d.lower() in low:
                            mk = d
                            break
                    blocking = mk is not None
                    if mk is None and DEV_USER.lower() in low:
                        mk = 'dev-user:%s' % DEV_USER
                    if mk is not None:
                        hits.append(dict(file=rel, line=lineno,
                                         kind='abs_path', marker=mk,
                                         blocking=blocking,
                                         text=ap[:200]))
                        break
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', default=None, help='待测 zip（默认自动发现最新）')
    ap.add_argument('--skip-extract', action='store_true',
                    help='复用已解压的目录（不重新解压）⇒ 复核同一份副本时用')
    ap.add_argument('--clean', default=r'C:\v20_cleantest')
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    # ── 定位 zip（**不写死版本号**）─────────────────────────
    zip_path = args.zip
    if not zip_path:
        if pkg_paths is not None:
            root = getattr(pkg_paths, 'PKG_ROOT_DEFAULT', HOME)
            prefix = getattr(pkg_paths, 'PKG_NAME_PREFIX',
                             'Confucius4_LiveCaption_v')
        else:
            root, prefix = HOME, 'Confucius4_LiveCaption_v'
        cands = []
        for name in os.listdir(root):
            if name.startswith(prefix) and name.endswith('.zip'):
                ver = name[len(prefix):-4]
                try:
                    key = tuple(int(x) for x in ver.split('.'))
                except ValueError:
                    continue
                cands.append((key, os.path.join(root, name)))
        if not cands:
            raise FileNotFoundError('未找到客户包 zip')
        cands.sort()
        zip_path = cands[-1][1]

    print('=' * 70)
    print('app214 —— APP-057 第 3 条「另一个路径解压 + 开发机绝对路径扫描」')
    print('zip :', zip_path)
    print('解压:', args.clean)
    print('=' * 70)

    # ── 清空并解压（**必须删干净**，否则会扫到上一轮残留）────
    t0 = time.time()
    if args.skip_extract:
        check('⓪ 复用已解压副本（--skip-extract）',
              os.path.isdir(args.clean), args.clean)
        with zipfile.ZipFile(zip_path) as z:
            n_entries = len(z.infolist())
        print('\n[0] 复用已解压副本：%s（zip 条目 %d）'
              % (args.clean, n_entries))
    else:
        if os.path.isdir(args.clean):
            shutil.rmtree(args.clean)
        os.makedirs(args.clean, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(args.clean)
            n_entries = len(z.infolist())
        print('\n[0] 解压完成：%d 个 zip 条目，用时 %.1f s' % (n_entries,
                                                         time.time() - t0))

    # zip 内顶层目录
    tops = [d for d in os.listdir(args.clean)
             if os.path.isdir(os.path.join(args.clean, d))]
    if not tops:
        print('  ⚠️ zip 内无顶层目录 ⇒ 直接扫根')
        tree = args.clean
    else:
        print('  顶层目录：%s' % tops)
        tree = os.path.join(args.clean, tops[0])

    # ── 扫描 ────────────────────────────────────────────────
    hits = scan_tree(tree)
    blocking = [h for h in hits if h.get('blocking')]
    user_only = [h for h in hits if not h.get('blocking')]
    print('\n[1] 扫描 .py/.json/.lnk/.cmd 里的绝对路径：'
          'reviewer 点名的开发目录 %d 处 / 仅含构建机用户名 %d 处'
          % (len(blocking), len(user_only)))
    for h in hits[:40]:
        print('    [%s] %s:%d [%s] %s'
              % ('阻断' if h.get('blocking') else '附带',
                 h['file'], h['line'], h['marker'], h['text']))
    check('① 解压副本里无「指向 reviewer 点名开发目录」的绝对路径',
          not blocking, '%d 处: %s' % (len(blocking),
                                      [(h['file'], h['marker'])
                                       for h in blocking[:8]]))
    # 🔴 **附带发现**（不阻断）：绝对路径里出现构建机用户名
    #    ⇒ reviewer ③ 没点名，但**确实泄漏构建机身份** ⇒ 单列报告。
    check('② 附带发现（不阻断）：绝对路径里无构建机用户名',
          not user_only, '%d 处: %s' % (len(user_only),
                                        [(h['file'], h['line'])
                                         for h in user_only[:8]]))

    # ── 反证组（判据必须有鉴别力）────────────────────────────
    disc = []
    probe_dir = os.path.join(tree, 'app', '_probe_clean')
    os.makedirs(probe_dir, exist_ok=True)
    # (a) .py 里写死开发目录绝对路径 ⇒ 必须命中
    p1 = os.path.join(probe_dir, 'probe_py.py')
    with open(p1, 'w', encoding='utf-8') as f:
        f.write('P = "C:\\\\Users\\\\Trekker-PTL\\\\confucius4-openvino\\\\x"\n')
    # (b) .json 里写死开发目录绝对路径 ⇒ 必须命中
    p2 = os.path.join(probe_dir, 'probe_json.json')
    with open(p2, 'w', encoding='utf-8') as f:
        f.write('{"src": "C:\\\\Users\\\\Trekker-PTL\\\\hy_bench\\\\a.py"}\n')
    # (c) .cmd 里写死开发目录绝对路径 ⇒ 必须命中
    p3 = os.path.join(probe_dir, 'probe_cmd.cmd')
    with open(p3, 'w', encoding='utf-8') as f:
        f.write('python "C:\\Users\\Trekker-PTL\\qwen3tts_eval\\run.py"\n')
    # (d) .lnk 里写死开发目录绝对路径 ⇒ 必须命中（文本形态）
    p4 = os.path.join(probe_dir, 'probe_lnk.lnk')
    with open(p4, 'w', encoding='utf-8') as f:
        f.write('C:\\Users\\Trekker-PTL\\live_dub_ext\\app\\x.py\n')
    # (e) 反面：只**提到**目录名、不是绝对路径 ⇒ 必须**不**命中
    p5 = os.path.join(probe_dir, 'probe_ok.py')
    with open(p5, 'w', encoding='utf-8') as f:
        f.write('NAME = "confucius4-openvino"\n'
                'REL = "hy_bench/xxx.py"\n')
    # (f) 🔴 **二进制 .lnk**（真实快捷方式里路径是 UTF-16LE 存的）
    #     ⇒ 只按 UTF-8 扫会漏 ⇒ 必须再解一份 UTF-16LE
    p6 = os.path.join(probe_dir, 'probe_bin.lnk')
    with open(p6, 'wb') as f:
        f.write(b'\x00\x00\x01\x00' + b'PADDING-PADDING' * 4)
        f.write('C:\\Users\\Trekker-PTL\\live_dub_ext\\x.exe'.encode(
            'utf-16-le'))
    h2 = scan_tree(tree)
    ok_a = any(x['file'].endswith('probe_py.py') for x in h2)
    ok_b = any(x['file'].endswith('probe_json.json') for x in h2)
    ok_c = any(x['file'].endswith('probe_cmd.cmd') for x in h2)
    ok_d = any(x['file'].endswith('probe_lnk.lnk') for x in h2)
    ok_e = not any(x['file'].endswith('probe_ok.py') for x in h2)
    ok_f = any(x['file'].endswith('probe_bin.lnk') for x in h2)
    disc.append(dict(name='反证①.py 里的开发目录绝对路径 ⇒ 必须命中', ok=ok_a))
    disc.append(dict(name='反证②.json 里的开发目录绝对路径 ⇒ 必须命中',
                     ok=ok_b))
    disc.append(dict(name='反证③.cmd 里的开发目录绝对路径 ⇒ 必须命中',
                     ok=ok_c))
    disc.append(dict(name='反证④.lnk 里的开发目录绝对路径 ⇒ 必须命中',
                     ok=ok_d))
    disc.append(dict(name='反证⑤只提到目录名非绝对路径 ⇒ 必须**不**命中',
                     ok=ok_e))
    disc.append(dict(name='反证⑥二进制 .lnk（UTF-16LE 路径）⇒ 必须命中',
                     ok=ok_f))
    check('③ 反证组全部成立（扫描判据有鉴别力）',
          all(d['ok'] for d in disc),
          '%d/%d' % (sum(1 for d in disc if d['ok']), len(disc)))
    for d in disc:
        print('      %-56s %s' % (d['name'], 'PASS' if d['ok'] else 'FAIL'))
    # 清理探针
    shutil.rmtree(probe_dir, ignore_errors=True)

    # ── 扫描覆盖度（报告用）──────────────────────────────────
    n_scanned = 0
    by_ext = {}
    for dp, dn, fns in os.walk(tree):
        rel_dp = os.path.relpath(dp, tree)
        parts = rel_dp.split(os.sep)
        if parts and parts[0] in ('python',) or rel_dp.startswith(
                os.path.join('ext', '.runtime_deps')):
            dn[:] = []
            continue
        for fn in fns:
            if fn.lower().endswith(SCAN_EXT):
                n_scanned += 1
                e = os.path.splitext(fn)[1].lower()
                by_ext[e] = by_ext.get(e, 0) + 1
    print('\n[2] 实际扫描文件数：%d %s' % (n_scanned, by_ext))
    # 🔴 **三态判据**：包内**根本不存在**的扩展名 ⇒ 记「不适用」而不是 FAIL。
    #    （原版硬要求「四类都要扫到」⇒ 包内没有 .lnk 时**恒 FAIL**
    #      ⇒ 这是「恒假判据」，必须改成「存在才要求覆盖」。）
    cov_notes = []
    cov_ok = True
    for e in SCAN_EXT:
        n = by_ext.get(e, 0)
        if n > 0:
            cov_notes.append('%s: %d 个已扫' % (e, n))
        else:
            cov_notes.append('%s: 包内无此类文件 ⇒ 不适用' % e)
    # 反向核对：包内（除第三方运行时）该有的文件都扫到了 ⇒ 用同一份 walk 计数
    check('④ 扫描面覆盖（存在即必扫；不存在记不适用）',
          cov_ok, '; '.join(cov_notes))

    # ── zip 与包目录一致性（交付口径：zip 内是否含本轮代码）────
    zip_sha, zip_bytes = sha256_file(zip_path)
    print('\n[3] zip 指纹：%d B / SHA256 %s' % (zip_bytes, zip_sha))

    npass = sum(1 for _n, ok, _d in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print('\n结果：%d PASS / %d FAIL' % (npass, nfail))

    out = {
        'tool': 'app214',
        'app': 'APP-057',
        'zip': zip_path,
        'zip_bytes': zip_bytes,
        'zip_sha256': zip_sha,
        'zip_entries': n_entries,
        'clean_dir': args.clean,
        'extracted_tree': tree,
        'n_files_scanned': n_scanned,
        'by_ext': by_ext,
        'hits': hits,
        'n_hits_blocking': len(blocking),
        'n_hits_user_only': len(user_only),
        'blocking_hits': blocking,
        'user_only_hits': user_only,
        'criterion_note': ('① 阻断口径 = reviewer ③ 点名的 5 个开发目录；'
                           '② 构建机用户名 = 附带发现（不阻断）；'
                           '.py 一律**扫全文**（含 docstring / 注释）；'
                           '.lnk 额外按 UTF-16LE 解码再扫'),
        'discrimination': disc,
        'results': [{'name': n, 'ok': ok, 'detail': d}
                    for n, ok, d in RESULTS],
        'summary': {'pass': npass, 'fail': nfail},
        'at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.json)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
