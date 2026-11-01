#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app191 —— 「验收证据 ↔ 被验收代码」绑定闸门。

## 为什么要有这个脚本（真实缺陷，不是假想）

`app186`（§117）是 APP-051② 的**真机验收总闸门**，它逐项核对：

    证据存在 + verdict=PASS + 指向 v%s 包

🔴🔴🔴 **但它从来没有核对「这份证据所验收的代码 == 现在交付的代码」**。

⇒ **实测到的真实脱钩**（2026-11-01，本轮）：

| 时点 | 事件 |
|---|---|
| 00:43:32 | `ACCEPTED.json` 写入（`accepted=true`）⇒ 桌面快捷方式据此指向 v1.13 |
| 05:56:10 | §120 **改写客户包 5 个生产模块**（`speaker_assets` / `speaker_tracker` / `tts_cuda` / `tts_engine` / `tts_worker`） |
| 06:08:44 | 重打 v1.13 zip（14 213 文件）⇒ **交付 zip 里是改后的代码** |

⇒ **交付物里的代码 ≠ 被验收的代码**，而 `ACCEPTED.json` 仍写着 `accepted=true`
⇒ **「验收通过」这句话在交付物上已经不再成立**，而**没有任何闸门会发现**。

🔴🔴 **「§120 的改动无害」不能靠「感觉」**：
§120 把 5 处写死的开发机家目录改成 `os.path.join(os.path.expanduser('~'), ...)`
⇒ 在「HOME == 那段字面量前缀」的机器上取值相同、在别的机器上**指向不同的路径**。
⇒ 这属于**一类特定的改动**（家目录路径改写），**不是**「任意代码改动」。
⇒ 本闸门的作用就是把漂移**分类**：只允许「良性类」悄悄通过，**任意其它改动 ⇒ 阻断**。

## 本闸门做什么（四条判据）

* **R1 漂移检测（🔴 阻断）**：客户包 `app/` 下每个**生产模块**的**文件 mtime**
  与 `ACCEPTED.json` 的 mtime 比较 ⇒ 晚于它 ⇒ **该模块未被任何验收覆盖**。
  🔴 用**包目录自身的 mtime**（交付物自己的时间线）而**不是 git commit 日期**
  —— 实测：commit 日期会**滞后**于工作区（`live_caption_app.py` 的改动 10-31 21:04
  就在工作区里，但直到 11-01 01:08 才提交）⇒ 用 commit 日期会**漏报**。

* **R2 漂移分类（🔴 阻断）**：对每个漂移模块，
  * **基线** = **内容寻址**：在 git 历史里找到「**最早**那个 blob == 当前包内内容」的
    commit `C`，取 `C^` 的 blob 作**漂移前内容**（⇒ 覆盖「验收后至今的全部改动」）。
  * **分类**（把两侧源码规范化后比较 `ast.dump`）：
    | 类别 | 含义 | 处置 |
    |---|---|---|
    | `identical` | 逐字节等价 | ✅ 良性 |
    | `home_path_rewrite` | **只有**家目录路径写法不同（字面量 ↔ `expanduser('~')` 派生） | ✅ 良性（§120 那一类） |
    | `other` | **其它任何改动** | 🔴 **阻断** ⇒ 验收已被推翻 |
  * **不 import 被测模块**（项目铁律）⇒ 只用 `ast` + 节点改写。
  * 🔴 规范化时把「字面量家目录路径」与「`expanduser('~')` 派生路径」统一成
    `«HOME»/tail` ⇒ 只有**尾部**相同才算对应；且要求被替换的字面量**共享同一个
    家目录前缀**（否则「同一个 HOME」这个前提不成立 ⇒ 不得判为良性）。

* **R3 验收声明自洽（🔴 阻断）**：`ACCEPTED.json` 的 `accepted` / `version` / `pkg_dir`
  必须与**本次验收的包**一致 ⇒ 否则是「拿了别的包的验收结论」。

* **R4 指纹连续性（🔴 阻断）**：记录「客户包生产模块集合的内容指纹」
  ⇒ 与**上一次**本闸门证据里的指纹比较 ⇒ 若变了，**必须**已被 R2 分类为良性
  ⇒ 防止「漂移检测本身被绕过」。

## 🔴 纪律

* **纯离线**：只读 git 历史 + 只读包目录 + 只读 `ACCEPTED.json`
  ⇒ 不占机器锁、不跑推理、不测速、不碰 GPU。
* **不 import 被测模块** ⇒ 只用 `ast`。
* **不写死仓库根**（§118/§119 铁律）⇒ 从 `__file__` **向上查找**仓库根；
  找不到就**抛异常**，绝不「用 cwd 猜」。
* **不写死包版本**（§48 铁律）⇒ 走 `pkg_paths` 自动发现最大版本。
* 证据落 `results/app/app191_acceptance_code_binding_evidence.json`。

## 鉴别力自检（`--selftest`）

🔴 **「判据 PASS」≠「判据正确」** ⇒ 自检构造已知状态：

| 组 | 构造 | 期望类别 |
|---|---|---|
| S1 | 纯家目录路径改写（字面量 → `expanduser` 派生） | `home_path_rewrite` |
| S2 | 常量**取值被改** | `other` |
| S3 | 新增 `_` 派生量（取值来自旧值） | `home_path_rewrite` |
| S4 | 新增**非** `_` 前缀的名字 | `other` |
| S5 | 派生量取值**全新**（旧值集合里没有） | `other` |
| S6 | 修前 == 修后 | `identical` |
| S7 | 修后改了**函数体内**的路径常量 | `other` |
| S8 | 改后**引入新逻辑**（多一个函数调用） | `other` |
| S9 | 两处字面量**家目录前缀不同** | `other`（不得判为良性） |

用法
----
    python results/app/app191_acceptance_code_binding_gate.py
    python results/app/app191_acceptance_code_binding_gate.py --selftest
    python results/app/app191_acceptance_code_binding_gate.py --json <out.json>
"""

from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 🔴🔴 §118/§119：仓库根从 `__file__` **向上查找**，不写死 `HOME/confucius4-openvino`。
#    写死的后果（实测）：fresh clone 到别处时判据仍读**原仓库** ⇒ 验收是假象。
#    找不到 ⇒ **抛异常**，绝不「用 cwd 猜」（宁可拒绝运行，也不给「指错对象」的假结论）。
def _find_repo_root(start: str) -> str:
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError(
                'app191: 无法从 %s 向上找到仓库根（缺 live_caption/ 与 pkg_paths.py）'
                % start)
        cur = parent


REPO = _find_repo_root(HERE)

if REPO not in sys.path:
    sys.path.insert(0, REPO)
import pkg_paths as _pkg_paths  # noqa: E402  §48 单一数据源

#: 家目录占位符（**不是**运行机器的家目录 ⇒ 判据与机器无关）
HOME_TOKEN = '«HOME»'

#: 良性类别（⇒ 不阻断）
BENIGN = ('identical', 'home_path_rewrite')

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:800]})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  —— %s' % detail) if detail else ''))
    return ok


# ══════════════════════════════════════════════════════════════════════
# 家目录路径的规范化
# ══════════════════════════════════════════════════════════════════════
def _norm_sep(s: str) -> str:
    return s.replace('\\', '/')


def _is_abs_path(s: str) -> bool:
    n = _norm_sep(s)
    return bool(re.match(r'^[A-Za-z]:/', n)) or n.startswith('//')


def _split_abs(s: str):
    """绝对路径字面量 ⇒ (家目录前缀, 尾部组件列表)。

    形如 `C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts`
    ⇒ 前缀 `C:/Users/Trekker-PTL`、尾部 `['qwen3asr_06b','scripts']`
    ⇒ **尾部至少 1 段**才算「家目录之后的相对部分」。
    """
    n = _norm_sep(s).rstrip('/')
    parts = [p for p in n.split('/') if p]
    if len(parts) < 2:
        return None, []
    if re.match(r'^[A-Za-z]:$', parts[0]):
        prefix = parts[0]
        rest = parts[1:]
    else:
        prefix = parts[0]
        rest = parts[1:]
    if not rest:
        return None, []
    # 🔴 家目录前缀 = 盘符 + 前两段（`Users/<name>`）—— 常见布局
    if re.match(r'^[A-Za-z]:$', prefix) and len(rest) >= 2:
        home_prefix = '/'.join([prefix, rest[0], rest[1]])
        tail = rest[2:]
    else:
        home_prefix = prefix
        tail = rest
    if not tail:
        return None, []
    return home_prefix, tail


def _expanduser_join_tail(node):
    """识别 `os.path.join(os.path.expanduser('~'), <const>...)` ⇒ 尾部组件列表。"""
    if not isinstance(node, ast.Call):
        return None
    fn = node.func
    if not (isinstance(fn, ast.Attribute) and fn.attr == 'join'):
        return None
    if not (isinstance(fn.value, ast.Attribute) and fn.value.attr == 'path'):
        return None
    if not node.args:
        return None
    first = node.args[0]
    if not (isinstance(first, ast.Call)
            and isinstance(first.func, ast.Attribute)
            and first.func.attr == 'expanduser'):
        return None
    if not first.args or not isinstance(first.args[0], ast.Constant):
        return None
    if first.args[0].value != '~':
        return None
    comps = []
    for a in node.args[1:]:
        if not (isinstance(a, ast.Constant) and isinstance(a.value, str)):
            return None
        comps.append(a.value)
    return comps


class _Canon(ast.NodeTransformer):
    """把家目录相关路径统一替换成 `«HOME»/tail` 常量。

    `tails` = 已知尾部集合（两侧**并集**）；
    `prefixes` = 被替换掉的字面量其**家目录前缀**集合（用于一致性检查）。
    """

    def __init__(self, tails):
        self.tails = set(tails)
        self.prefixes = set()
        self.n_replaced = 0

    def visit_Call(self, node):
        # 🔴🔴 **必须先判形态、再 generic_visit** ——
        #    否则内层的 `os.path.expanduser('~')` 会先被换成 `Constant(HOME_TOKEN)`
        #    ⇒ 外层的 `os.path.join(...)` 就不再匹配「expanduser 派生」的形态
        #    ⇒ **派生路径永远不被规范化**（S1/S3 判不出来的真根因）。
        comps = _expanduser_join_tail(node)
        if comps is not None:
            self.generic_visit(node)
            tail = '/'.join(comps)
            self.n_replaced += 1
            return ast.copy_location(
                ast.Constant(value='%s/%s' % (HOME_TOKEN, tail)), node)
        fn = node.func
        if (isinstance(fn, ast.Attribute) and fn.attr == 'expanduser'
                and isinstance(fn.value, ast.Attribute)
                and fn.value.attr == 'path'
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == '~'):
            self.n_replaced += 1
            return ast.copy_location(ast.Constant(value=HOME_TOKEN), node)
        self.generic_visit(node)
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, str) and _is_abs_path(node.value):
            prefix, tail = _split_abs(node.value)
            if prefix is not None:
                tail_s = '/'.join(tail)
                if tail_s in self.tails:
                    self.prefixes.add(prefix)
                    self.n_replaced += 1
                    return ast.copy_location(
                        ast.Constant(value='%s/%s' % (HOME_TOKEN, tail_s)), node)
        return node


def _collect_tails(tree):
    """源码里所有 `expanduser('~')` 派生路径的尾部集合。"""
    tails = set()

    class _T(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            comps = _expanduser_join_tail(node)
            if comps is not None:
                tails.add('/'.join(comps))
            return node

    _T().visit(tree)
    return tails


def _module_derived_consts(tree, tails):
    """模块级 `_` 前缀常量 ⇒ 规范化的常量取值（能算出来的）。"""
    out = {}

    def _canon_value(node):
        """把一个表达式算成（规范化后的）常量字符串；算不出 ⇒ None。"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            # 🔴 家目录路径字面量 ⇒ 规范成 `«HOME»/tail`
            #    （否则「修前是字面量、修后是派生」两侧取值对不上 ⇒ 误判不等价）
            if _is_abs_path(v):
                _prefix, tl = _split_abs(v)
                if tl:
                    tail = '/'.join(tl)
                    if tail in tails:
                        return '%s/%s' % (HOME_TOKEN, tail)
            return v
        if isinstance(node, ast.Name) and node.id in out:
            return out[node.id]
        comps = _expanduser_join_tail(node)
        if comps is not None:
            tail = '/'.join(comps)
            if tail in tails:
                return '%s/%s' % (HOME_TOKEN, tail)
            return None
        if isinstance(node, ast.Call):
            fn = node.func
            if (isinstance(fn, ast.Attribute) and fn.attr == 'expanduser'
                    and isinstance(fn.value, ast.Attribute)
                    and fn.value.attr == 'path'
                    and len(node.args) == 1
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == '~'):
                return HOME_TOKEN
        return None

    for node in tree.body:
        targets = []
        val = None
        if isinstance(node, ast.Assign):
            val = node.value
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            val = node.value
            targets = [node.target.id] if isinstance(node.target, ast.Name) else []
        if not targets or val is None:
            continue
        for t in targets:
            if not t.startswith('_'):
                continue
            v = _canon_value(val)
            if v is not None:
                out[t] = v
    return out


def _all_string_constants(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def _inline_and_strip(tree, mapping):
    """把 `mapping` 里的名字**内联**成常量，并**删除**它们的模块级赋值。"""

    class _Inline(ast.NodeTransformer):
        def visit_Name(self, node):
            # 🔴🔴 **只替换「读」的位置（ctx=Load）** —— 若连**赋值目标**（Store）
            #    也替换掉 ⇒ 目标的 `ast.Name` 变成 `ast.Constant`
            #    ⇒ 后面 `_Strip` 认不出这个名字 ⇒ **派生常量的赋值删不掉**
            #    ⇒ 两侧 AST 不可能相等 ⇒ S3 判不出来的真根因。
            if isinstance(node.ctx, ast.Load) and node.id in mapping:
                return ast.copy_location(ast.Constant(value=mapping[node.id]), node)
            return node

    tree = _Inline().visit(tree)

    class _Strip(ast.NodeTransformer):
        def visit_Assign(self, node):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if names and all(n in mapping for n in names):
                return None
            return node

    tree = _Strip().visit(tree)
    ast.fix_missing_locations(tree)
    return tree


def classify_drift(baseline_src: str, current_src: str):
    """把「漂移前 vs 漂移后」**分类**。

    返回 `(cls, detail)`，其中 `cls` ∈ {`identical`, `home_path_rewrite`, `other`}。
    """
    try:
        b_tree0 = ast.parse(baseline_src)
        c_tree0 = ast.parse(current_src)
    except SyntaxError as e:
        return 'other', {'error': 'SyntaxError: %s' % e}

    tails = _collect_tails(b_tree0) | _collect_tails(c_tree0)

    # 修前**未**规范化的 dump（用于判「逐字相同」）
    b_raw = ast.dump(b_tree0)
    c_raw = ast.dump(c_tree0)

    # 🔴 修前源码里**所有家目录路径字面量**的「尾部」集合
    #    ⇒ 修后新增的派生常量，其尾部必须**已在这个集合里**
    #    ⇒ 才算「只是把同一个路径换了个写法」（而不是引入了新路径）。
    b_home_tails = set()
    for n in ast.walk(b_tree0):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if _is_abs_path(n.value):
                _prefix, tl = _split_abs(n.value)
                if tl:
                    b_home_tails.add('/'.join(tl))

    # 修后新增的 `_` 派生常量：取值必须**已存在于修前的常量/路径集合**里
    b_consts = _all_string_constants(b_tree0)
    derived = _module_derived_consts(c_tree0, tails)
    bad_derived = []
    for name, val in derived.items():
        if val in b_consts or val == HOME_TOKEN:
            continue
        if val.startswith(HOME_TOKEN + '/'):
            tail = val[len(HOME_TOKEN) + 1:]
            if tail in b_home_tails:
                continue          # ✅ 只是把已有路径换了个写法
            bad_derived.append({'name': name, 'value': val,
                                'reason': '派生路径的尾部在修前不存在',
                                'tail': tail,
                                'b_home_tails': sorted(b_home_tails)})
            continue
        bad_derived.append({'name': name, 'value': val,
                            'reason': '取值在修前不存在'})
    if bad_derived:
        return 'other', {
            'cls': 'other', 'reason': '新增派生常量的取值在修前不存在',
            'bad_derived': bad_derived, 'tails': sorted(tails),
            'b_home_tails': sorted(b_home_tails),
        }

    # 规范化两侧
    # 🔴🔴🔴 **内联+剥离必须对两侧「对称」地做** ——
    #    只对「修后」做 ⇒ 修前保留着 `_CN_DIGITS` 的赋值、修后被剥掉
    #    ⇒ 两侧 AST 必然不等 ⇒ **误判不等价**（本轮实测 3 个假 FAIL 的真根因）。
    b_derived = _module_derived_consts(b_tree0, tails)
    b_tree = _inline_and_strip(ast.parse(baseline_src), b_derived)
    b_canon = _Canon(tails)
    b_tree = b_canon.visit(b_tree)
    ast.fix_missing_locations(b_tree)
    b_dump = ast.dump(b_tree)

    c_tree = _inline_and_strip(ast.parse(current_src), derived)
    c_canon = _Canon(tails)
    c_tree = c_canon.visit(c_tree)
    ast.fix_missing_locations(c_tree)
    c_dump = ast.dump(c_tree)

    detail = {
        'tails': sorted(tails),
        'b_prefixes': sorted(b_canon.prefixes),
        'c_prefixes': sorted(c_canon.prefixes),
        'n_replaced_before': b_canon.n_replaced,
        'n_replaced_after': c_canon.n_replaced,
        'n_derived_inlined': len(derived),
        'derived': dict(derived),
        'bad_derived': bad_derived,
        'b_raw_len': len(b_raw),
        'c_raw_len': len(c_raw),
        'b_dump_len': len(b_dump),
        'c_dump_len': len(c_dump),
    }

    if b_raw == c_raw:
        detail['cls'] = 'identical'
        return 'identical', detail

    # 🔴🔴 「同一个 HOME」这个前提：被替换掉的字面量必须**共享同一个家目录前缀**
    all_prefixes = set(b_canon.prefixes) | set(c_canon.prefixes)
    if len(all_prefixes) > 1:
        detail['cls'] = 'other'
        detail['reason'] = '被替换的字面量家目录前缀不一致（%s）⇒ 前提不成立' \
            % sorted(all_prefixes)
        return 'other', detail

    if b_dump == c_dump:
        detail['cls'] = 'home_path_rewrite'
        detail['home_prefix'] = sorted(all_prefixes)
        return 'home_path_rewrite', detail

    detail['cls'] = 'other'
    i = 0
    while i < min(len(b_dump), len(c_dump)) and b_dump[i] == c_dump[i]:
        i += 1
    detail['first_diff_at'] = i
    detail['b_at'] = b_dump[max(0, i - 140):i + 220]
    detail['c_at'] = c_dump[max(0, i - 140):i + 220]
    return 'other', detail


# ══════════════════════════════════════════════════════════════════════
# git / 包目录 只读工具
# ══════════════════════════════════════════════════════════════════════
def _git(args):
    r = subprocess.run(['git'] + args, cwd=REPO, capture_output=True)
    return r.returncode, r.stdout


def git_blob(rev: str, path: str):
    rc, out = _git(['show', '%s:%s' % (rev, path)])
    if rc != 0:
        return None
    return out


def git_commits_touching(path: str):
    """改动过 `path` 的 commit（新 → 旧）。"""
    rc, out = _git(['log', '--format=%H', '--', path])
    if rc != 0:
        return []
    return [s for s in out.decode('utf-8', 'replace').split() if s]


def git_commit_parent(rev: str):
    rc, out = _git(['rev-parse', '%s^' % rev])
    if rc != 0:
        return None
    s = out.decode('utf-8', 'replace').strip()
    return s or None


def norm_bytes(b: bytes) -> bytes:
    """归一化行尾（§119 铁律：`core.autocrlf=true` ⇒ clone 后 LF→CRLF）。"""
    return b.replace(b'\r\n', b'\n')


def sha16(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def _pkg_version_of(pkg_dir: str) -> str:
    """从**包目录名**取版本号（不依赖全局自动发现 ⇒ 判「本次被验收的那个包」）。"""
    base = os.path.basename(os.path.normpath(pkg_dir))
    m = re.search(r'_v(\d+(?:\.\d+)*)$', base)
    if m:
        return m.group(1)
    # 退化：从包内 MANIFEST.json 读
    for cand in (os.path.join(pkg_dir, 'MANIFEST.json'),
                 os.path.join(pkg_dir, 'app', 'MANIFEST.json')):
        if os.path.isfile(cand):
            try:
                with open(cand, encoding='utf-8') as f:
                    return str(json.load(f).get('version') or '')
            except Exception:
                pass
    return ''


def pkg_production_modules(pkg_app: str):
    """客户包 `app/` 下的**生产模块**（排除开发专用）。"""
    import pkg_exclude
    out = []
    for n in sorted(os.listdir(pkg_app)):
        if not n.endswith('.py'):
            continue
        try:
            if pkg_exclude.is_app_dev_only('app/' + n):
                continue
        except Exception:
            pass
        out.append(n)
    return out


def package_fingerprint(pkg_app: str, mods):
    """客户包生产模块集合的**内容指纹**（归一化行尾后按名字排序）。"""
    h = hashlib.sha256()
    for n in mods:
        p = os.path.join(pkg_app, n)
        with open(p, 'rb') as f:
            data = norm_bytes(f.read())
        h.update(n.encode('utf-8'))
        h.update(b'\0')
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════
def run(pkg_dir: str, prev_evidence: str = None):
    pkg_app = os.path.join(pkg_dir, 'app')
    acc_path = os.path.join(pkg_dir, 'ACCEPTED.json')

    print('=' * 70)
    print('app191 —— 验收证据 ↔ 被验收代码 绑定闸门（目标包 %s）'
          % os.path.basename(pkg_dir))
    print('=' * 70)

    # ── R3 验收声明自洽 ───────────────────────────────────────────
    if not os.path.isfile(acc_path):
        check('R3 ACCEPTED.json 存在', False, acc_path)
        return {'verdict': 'FAIL', 'n_pass': PASS, 'n_fail': FAIL,
                'checks': CHECKS}
    with open(acc_path, encoding='utf-8') as f:
        acc = json.load(f)
    check('R3 ACCEPTED.json 存在且 accepted=true',
          bool(acc.get('accepted')), 'accepted=%r' % acc.get('accepted'))
    # 🔴🔴 **版本必须取「本次被验收的那个包」的版本**，不能取全局自动发现的版本 ——
    #    否则显式 `--pkg v1.12` 时会拿 v1.13 的版本号来比 ⇒ **误报 FAIL**
    #    （本轮鉴别力实测 D4 实测踩到：影子包 v1.99 vs 全局最大 v1.13 ⇒ 假 FAIL）。
    m = _pkg_version_of(pkg_dir)
    acc_ver = str(acc.get('version') or '')
    check('R3 ACCEPTED.json 的 version == 本包版本',
          acc_ver == m, 'ACCEPTED.version=%r / 本包=%r' % (acc_ver, m))
    acc_pkg = str(acc.get('pkg_dir') or '')
    check('R3 ACCEPTED.json 的 pkg_dir == 本包目录',
          os.path.normcase(os.path.normpath(acc_pkg))
          == os.path.normcase(os.path.normpath(pkg_dir)),
          'ACCEPTED.pkg_dir=%r' % acc_pkg)

    acc_mtime = os.path.getmtime(acc_path)
    accepted_at = str(acc.get('accepted_at') or '')
    # 🔴🔴🔴 **漂移判定必须用「内容里的时间戳」而不是「文件 mtime」**。
    #    实测本轮踩到：`ACCEPTED.json` 从 zip 还原后 **mtime 变成还原时刻**
    #    ⇒ 5 个真实漂移模块被误判成「无漂移」⇒ **闸门假 PASS**。
    #    ⇒ `accepted_at` 是**内容字段** ⇒ 复制/还原都不会改它 ⇒ 稳健。
    #    ⚠️ 模块侧的 mtime 仍用文件系统时间：模块一旦被重新同步/重打包，
    #       mtime 就会更新 ⇒ **正确地**被判为「验收后又动过」。
    acc_ts = None
    try:
        acc_ts = datetime.datetime.strptime(
            accepted_at, '%Y-%m-%d %H:%M:%S').timestamp()
    except Exception:
        acc_ts = acc_mtime
    print('  ACCEPTED.json mtime = %s（accepted_at = %s ⇒ 漂移判定基准 = %s）'
          % (datetime.datetime.fromtimestamp(acc_mtime).strftime('%Y-%m-%d %H:%M:%S'),
             accepted_at,
             datetime.datetime.fromtimestamp(acc_ts).strftime('%Y-%m-%d %H:%M:%S')))

    mods = pkg_production_modules(pkg_app)
    print('  客户包生产模块：%d 个' % len(mods))

    # ── R1 漂移检测（按**包目录自身的 mtime**）────────────────────
    drifted, covered = [], []
    for name in mods:
        p = os.path.join(pkg_app, name)
        mt = os.path.getmtime(p)
        rec = {
            'module': name,
            'mtime': datetime.datetime.fromtimestamp(mt).strftime(
                '%Y-%m-%d %H:%M:%S'),
            'mtime_ts': mt,
        }
        (drifted if mt > acc_ts else covered).append(rec)

    print()
    print('  R1 漂移检测（包内模块 mtime > ACCEPTED.accepted_at）：')
    check('R1 生产模块都能被检出（模块数 > 0）', len(mods) > 0,
          'covered=%d drifted=%d' % (len(covered), len(drifted)))
    for d in drifted:
        print('        DRIFT  %-22s %s' % (d['module'], d['mtime']))
    if not drifted:
        print('        （无漂移 ⇒ 所有生产模块都在验收时点之前落定）')

    # ── R2 漂移分类 ───────────────────────────────────────────────
    print()
    print('  R2 漂移分类（良性类 = identical / home_path_rewrite）：')
    if not drifted:
        check('R2 无漂移模块 ⇒ 无需分类', True, 'drifted=0')
    for d in drifted:
        name = d['module']
        rel = 'live_caption/' + name
        cur_path = os.path.join(pkg_app, name)
        with open(cur_path, 'rb') as f:
            cur = norm_bytes(f.read())

        # 🔴 内容寻址：找**最早**那个 blob == 当前包内内容的 commit
        oldest_match = None
        for rev in git_commits_touching(rel):
            b = git_blob(rev, rel)
            if b is not None and norm_bytes(b) == cur:
                oldest_match = rev
                break
        base_rev = git_commit_parent(oldest_match) if oldest_match else None
        base_mode = 'content_addressed'
        if not base_rev:
            # 🔴 兜底：当前内容**不在 git 历史里**（例如工作区里未提交的改动、
            #    或鉴别力测试注入的缺陷）⇒ 退而用「**最近**一次改过它的 commit」
            #    作为基线 ⇒ 仍然能判定「相对仓库版本漂移了什么」。
            revs = git_commits_touching(rel)
            if not revs:
                check('R2 %s 的漂移前基线可重建' % name, False,
                      '该文件在 git 历史里不存在 ⇒ 无法重建基线')
                d['cls'] = None
                continue
            base_rev = revs[0]
            base_mode = 'fallback_latest_commit'
        blob = norm_bytes(git_blob(base_rev, rel) or b'')
        if not blob:
            check('R2 %s 的漂移前基线可重建' % name, False, '基线 blob 取不到')
            d['cls'] = None
            continue
        cls, det = classify_drift(blob.decode('utf-8', 'replace'),
                                   cur.decode('utf-8', 'replace'))
        d['base_commit'] = base_rev
        d['base_mode'] = base_mode
        d['sha_before'] = sha16(blob)
        d['sha_after'] = sha16(cur)
        d['cls'] = cls
        d['detail'] = det
        benign = cls in BENIGN
        check('R2 %s 的漂移属于良性类（%s）' % (name, cls), benign,
              'base=%s(%s) before=%s after=%s | cls=%s%s'
              % (base_rev[:8], base_mode, d['sha_before'], d['sha_after'], cls,
                 ('' if benign else
                  ' ⇒ 验收已被这条改动推翻：%s'
                  % json.dumps(det, ensure_ascii=False)[:240])))
        if not benign:
            print('        b_at = %s' % str(det.get('b_at'))[:300])
            print('        c_at = %s' % str(det.get('c_at'))[:300])

    # ── R4 指纹连续性 ────────────────────────────────────────────
    print()
    print('  R4 指纹连续性（生产模块集合内容指纹）：')
    fp = package_fingerprint(pkg_app, mods)
    print('        当前指纹 = %s' % fp[:32])
    prev_fp = None
    if prev_evidence and os.path.isfile(prev_evidence):
        try:
            with open(prev_evidence, encoding='utf-8') as f:
                prev = json.load(f)
            prev_fp = prev.get('fingerprint')
        except Exception:
            prev_fp = None
    if prev_fp is None:
        check('R4 指纹连续性（首次运行 ⇒ 建立基线）', True,
              '上次证据里没有指纹 ⇒ 本次建立基线')
    else:
        same = (prev_fp == fp)
        all_benign = all((d.get('cls') in BENIGN) for d in drifted)
        check('R4 指纹变化已被 R2 分类为良性',
              same or all_benign,
              'prev=%s… now=%s… | drifted=%d 全部良性=%s'
              % (prev_fp[:16], fp[:16], len(drifted), all_benign))

    ok_all = (FAIL == 0)
    print()
    print('=' * 70)
    print('PASS %d  FAIL %d  verdict=%s'
          % (PASS, FAIL, 'PASS' if ok_all else 'FAIL'))
    print('=' * 70)

    return {
        'script': 'app191_acceptance_code_binding_gate.py',
        'pkg_dir': pkg_dir,
        'pkg_version': m,
        'accepted_at': accepted_at,
        'accepted_mtime': datetime.datetime.fromtimestamp(
            acc_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'accepted_ts': acc_ts,
        'drift_baseline': 'ACCEPTED.accepted_at（内容字段，非文件 mtime）',
        'n_modules': len(mods),
        'fingerprint': fp,
        'covered': covered,
        'drifted': drifted,
        'n_pass': PASS,
        'n_fail': FAIL,
        'verdict': 'PASS' if ok_all else 'FAIL',
        'checks': CHECKS,
    }


def _selftest():
    """🔴🔴🔴 鉴别力实测：**判据必须能识破「不是家目录路径改写」的改动**。"""
    print('=' * 70)
    print('app191 --selftest —— 鉴别力自检')
    print('=' * 70)
    base = (
        "import os\n"
        "DEV_ASR_SCRIPTS = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts'\n"
        "P2 = 'plain'\n"
    )
    cases = [
        ('S1 纯家目录路径改写 ⇒ home_path_rewrite',
         "import os\n"
         "DEV_ASR_SCRIPTS = os.path.join(os.path.expanduser('~'), 'qwen3asr_06b', 'scripts')\n"
         "P2 = 'plain'\n",
         'home_path_rewrite'),
        ('S2 常量取值被改 ⇒ other',
         "import os\n"
         "DEV_ASR_SCRIPTS = os.path.join(os.path.expanduser('~'), 'qwen3asr_06b', 'SCRIPTS')\n"
         "P2 = 'plain'\n",
         'other'),
        ('S3 新增 `_` 派生量（取值来自旧值）⇒ home_path_rewrite',
         "import os\n"
         "_D = os.path.join(os.path.expanduser('~'), 'qwen3asr_06b', 'scripts')\n"
         "DEV_ASR_SCRIPTS = _D\n"
         "P2 = 'plain'\n",
         'home_path_rewrite'),
        ('S4 新增非 `_` 前缀的名字 ⇒ other',
         "import os\n"
         "NEW = 'brand-new'\n"
         "DEV_ASR_SCRIPTS = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts'\n"
         "P2 = 'plain'\n",
         'other'),
        ('S5 派生量取值全新（旧值集合里没有）⇒ other',
         "import os\n"
         "_D = os.path.join(os.path.expanduser('~'), 'other', 'path')\n"
         "DEV_ASR_SCRIPTS = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts'\n"
         "P2 = 'plain'\n",
         'other'),
        ('S6 修前 == 修后 ⇒ identical',
         base, 'identical'),
        ('S7 修后改了**函数体内**的路径常量 ⇒ other',
         "import os\n"
         "def f():\n"
         "    return r'C:\\Users\\Trekker-PTL\\confucius4-tts'\n"
         "DEV_ASR_SCRIPTS = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts'\n"
         "P2 = 'plain'\n",
         'other'),
        ('S8 修后**引入新逻辑** ⇒ other',
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts'\n"
         "P2 = 'plain'\n"
         "EXTRA = len([1, 2, 3])\n",
         'other'),
        ('S9 两处字面量家目录前缀不同 ⇒ other（不得判为良性）',
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\Users\\Other\\qwen3asr_06b\\scripts'\n"
         "P2 = 'plain'\n",
         'other'),
    ]
    n_fail = 0
    for name, cur, want in cases:
        got, det = classify_drift(base, cur)
        ok = (got == want)
        if not ok:
            n_fail += 1
        print('  [%s] %s —— 判为 %s（期望 %s）'
              % ('PASS' if ok else 'FAIL', name, got, want))
        if not ok:
            print('        detail = %s' % json.dumps(det, ensure_ascii=False)[:400])
    print()
    print('  结论: %s（PASS %d / FAIL %d）'
          % ('PASS' if n_fail == 0 else 'FAIL', len(cases) - n_fail, n_fail))
    return n_fail == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None,
                    help='客户包目录（默认由 pkg_paths 自动发现**最大版本**的包）')
    ap.add_argument('--json', default=None, help='证据输出路径')
    ap.add_argument('--selftest', action='store_true', help='只跑鉴别力自检')
    args = ap.parse_args()

    if args.selftest:
        return 0 if _selftest() else 1

    pkg_dir = _pkg_paths.resolve_pkg_dir(args.pkg)
    if not os.path.isdir(os.path.join(pkg_dir, 'app')):
        print('!! 客户包目录无效（缺 app/）：%s' % pkg_dir)
        return 2

    out = args.json or os.path.join(
        HERE, 'app191_acceptance_code_binding_evidence.json')
    if not os.path.isabs(out):
        out = os.path.join(REPO, out)

    res = run(pkg_dir, prev_evidence=out)
    res['ts'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('[evidence] %s' % out)
    return 0 if res['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
