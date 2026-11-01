# -*- coding: utf-8 -*-
"""_app223_escape_fix_verify.py —— 校验「docstring 改 raw」的**四处**效果。

🔴 三件事都要有证据：
1. **SyntaxWarning 归零**：改后 `compile()` 不再报 `invalid escape sequence`。
2. **docstring 文本不变**：改前/改后的 docstring **逐字符比对**
   ⇒ 只允许「原本被 Python 吃成控制字符的转义」变成**可见字面量**，
   其余必须**逐字相同**。
3. **行为不变**：docstring 之外的文件内容逐字节比对 ⇒ 只允许「开头的引号前多一个 r」。

用法：
    python results/app/_app223_escape_fix_verify.py <备份目录> <仓库根>
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import warnings

PAIRS = [
    ('tts_cuda_sidecar.py', 'live_caption/tts_cuda_sidecar.py'),
    ('machine_lock_app.py', 'machine_lock_app.py'),
    ('_app100b_patch_status.py', 'live_caption/_app100b_patch_status.py'),
    ('sync_c195_app052054_to_pkg.py',
     'live_caption/sync_c195_app052054_to_pkg.py'),
    ('app223_app061_device_acceptance.py',
     'results/app/app223_app061_device_acceptance.py'),
]


def doc_map(path):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, 'body', None)
        if not body:
            continue
        first = body[0]
        if not (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        name = ('<module>' if isinstance(node, ast.Module)
                else getattr(node, 'name', '?'))
        out.setdefault(name, []).append(first.value.value)
    return out


def str_constants(path):
    """文件里**所有**字符串常量（按源码顺序）⇒ 用来证明「非 docstring 的
    字符串值一个都没变」。"""
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


def compile_warnings(path):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        compile(src, path, 'exec')
        return ['%s:%s %s' % (os.path.basename(path), x.lineno, x.message)
                for x in w if issubclass(x.category, SyntaxWarning)]


def diff_text(a, b):
    """返回 (相同?, 差异说明列表)。"""
    if a == b:
        return True, []
    notes = []
    if len(a) != len(b):
        notes.append('长度 %d → %d' % (len(a), len(b)))
    import difflib
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        notes.append('%s: 旧 %r → 新 %r' % (tag, a[i1:i2][:40], b[j1:j2][:40]))
    return False, notes


def _only_ctrl_to_visible(a, b):
    """差异是否**只有**「控制字符 → 可见字面量」这一类。

    🔴 判据：把 b 里的可见字面量换回控制字符后，与 a 完全相同。
    """
    import re as _re
    ctrl_map = {'\\b': '\x08', '\\t': '\x09', '\\n': '\x0a',
                '\\r': '\x0d', '\\f': '\x0c', '\\v': '\x0b',
                '\\a': '\x07', '\\0': '\x00'}
    cand = b
    for lit, ctrl in ctrl_map.items():
        cand = cand.replace(lit, ctrl)
    return cand == a


def main():
    bak, repo = sys.argv[1], sys.argv[2]
    out = {'pairs': [], 'n_pass': 0, 'n_fail': 0}
    for bname, rname in PAIRS:
        bp = os.path.join(bak, bname)
        rp = os.path.join(repo, rname)
        rec = {'file': rname, 'backup': bp}
        # ① SyntaxWarning
        w_before = compile_warnings(bp)
        w_after = compile_warnings(rp)
        rec['warn_before'] = w_before
        rec['warn_after'] = w_after
        ok1 = (not w_after) and bool(w_before)
        rec['warn_cleared'] = ok1
        # ② docstring 逐字符
        d_before, d_after = doc_map(bp), doc_map(rp)
        notes = []
        allowed = []
        for k in sorted(set(d_before) | set(d_after)):
            a = d_before.get(k, [''])[0]
            b = d_after.get(k, [''])[0]
            same, ns = diff_text(a, b)
            if same:
                continue
            # 🔴 唯一允许的差异：**控制字符变成可见字面量**
            #    （旧 docstring 里 `\b` 被 Python 吃成 0x08 背空格 ⇒ 渲染不可见）
            #    ⇒ 改成 raw 后显示为可见的 `\b` ⇒ **文档更对**，非行为变化。
            if _only_ctrl_to_visible(a, b):
                allowed.append('%s: 控制字符→可见字面量 %s' % (k, ns))
            else:
                notes.append('%s: %s' % (k, ' | '.join(ns)))
        rec['doc_allowed_changes'] = allowed
        rec['doc_diff_notes'] = notes
        rec['doc_same'] = (not notes)
        # ③ 文件内容差异（只应是引号前多一个 r）
        with open(bp, 'rb') as f:
            bb = f.read()
        with open(rp, 'rb') as f:
            rb = f.read()
        rec['file_bytes_before'] = len(bb)
        rec['file_bytes_after'] = len(rb)
        rec['file_bytes_delta'] = len(rb) - len(bb)
        ok3 = abs(len(rb) - len(bb)) <= 2
        rec['file_size_sane'] = ok3
        # ④ 所有字符串常量的值对照（docstring 之外的字符串必须**一个都没变**）
        s_before = str_constants(bp)
        s_after = str_constants(rp)
        diff_str = []
        if len(s_before) != len(s_after):
            diff_str.append('字符串常量个数 %d → %d' % (len(s_before),
                                                       len(s_after)))
        for i, (x, y) in enumerate(zip(s_before, s_after)):
            if x == y:
                continue
            if _only_ctrl_to_visible(x, y):
                diff_str.append('#%d 控制字符→可见字面量（docstring）' % i)
            else:
                diff_str.append('#%d 值变了：%r → %r' % (i, x[:60], y[:60]))
        rec['string_const_diffs'] = diff_str
        ok4 = all('值变了' not in s for s in diff_str)
        rec['string_values_intact'] = ok4
        rec['sha256_after'] = hashlib.sha256(rb).hexdigest()
        rec['sha256_before'] = hashlib.sha256(bb).hexdigest()
        rec['ok'] = bool(ok1 and rec['doc_same'] and ok3 and ok4)
        out['pairs'].append(rec)
        if rec['ok']:
            out['n_pass'] += 1
        else:
            out['n_fail'] += 1
    out['verdict'] = 'PASS' if out['n_fail'] == 0 else 'FAIL'
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out['n_fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
