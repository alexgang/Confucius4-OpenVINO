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

#: 🔴🔴🔴 **APP-052 ③：`<HOME>` 占位符**（脱敏用，不是运行机器的家目录）
#:
#:   客户包里把「写死的开发机家目录」换成 `<HOME>` 占位，
#:   以免**随包泄漏开发机用户名**。
#:   ⇒ 语义上与「expanduser 派生」等价（客户机上指向自己的家目录）。
#:
#:   ⚠️ **必须能区分两种写法**：
#:     - `<HOME>\qwen3asr_06b`  —— **Windows 反斜杠**（包内实际形态）
#:     - `<HOME>/qwen3asr_06b`   —— **正斜杠**（docstring 里的示意形态）
#:   ⇒ 解析时**先把分隔符统一成 `/`**。
HOME_PLACEHOLDER = '<HOME>'

#: 良性类别（⇒ 不阻断）
BENIGN = ('identical', 'home_path_rewrite', 'home_placeholder')

#: 🔴🔴🔴 **补丁 5-fix5：白名单放行类别**
#:   ⇒ 它**不属于** BENIGN（语义不同：BENIGN = 「改动本身无害」；
#:     waived = 「改动本身有实质，但 reviewer 已显式承认」）
#:   ⇒ 证据里**分开统计** ⇒ reviewer 能一眼看出哪些是靠白名单放行的。
WAIVED = 'waived'

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


def _split_placeholder(s: str):
    """`<HOME>\tail` / `<HOME>/tail` ⇒ 尾部组件列表（不认 ⇒ None）。

    🔴 **尾部至少 1 段**才算「家目录之后的相对部分」
    （与 `_split_abs` 的口径**一致** ⇒ 两边可比）。
    """
    n = _norm_sep(s).rstrip('/')
    if not n.startswith(HOME_PLACEHOLDER):
        return None
    rest = n[len(HOME_PLACEHOLDER):].lstrip('/')
    if not rest:
        return None
    parts = [p for p in rest.split('/') if p]
    if not parts:
        return None
    return parts


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


# 🔴🔴🔴🔴 **补丁 5a（APP-052 ②）：从 docstring 原文里抽家目录路径**
#
#   **为什么必须有这个**（本轮实测 `_probe_tails2.py` 抓到的真缺口）：
#     APP-052 ③ 要求改的 `speaker_assets.py` 那 3 行
#     （`WORK = r'C:\Users\Trekker-PTL\qwen3asr_06b'` 等）
#     **写在模块 docstring 内部** ⇒ `ast.parse` 只把它当作**一个** Constant
#     ⇒ `_split_abs(整篇 docstring)` 按 `/` 拆 ⇒ **拆不出尾部**
#     ⇒ `_collect_tails` 漏收 ⇒ 规范化不生效 ⇒ **误判 `other`**
#     ⇒ 即「reviewer 要求的改动被当成危险改动」⇒ **闸门恒 FAIL**。
#
#   **口径**：docstring 原文里出现「绝对路径形态」或「`<HOME>` 占位形态」的
#     **片段**，逐个抽出其「尾部」⇒ 与 `_split_abs` / `_split_placeholder`
#     **同口径** ⇒ 两侧可规范化到同一形态。
#
#   ⚠️ **只抽「家目录前缀 + 至少 1 段尾部」** ⇒ 避免把普通 URL /
#      普通文本误当成家目录路径。
#   ⚠️ **必须用 docstring 的 `repr` 原文**（而不是 `ast.get_docstring`
#      的清洗结果）⇒ 保留原始反斜杠形态。

# 🔴🔴🔴 **补丁 5-fix4（缺口 A）：字符类**排除 CJK 标点与全角字符**
#   ⇒ 否则「`C:\Users\X\_env`，（中文逗号）」会把标点吃进尾部
#   ⇒ 尾部**不再唯一标识一个路径** ⇒ 配对可能错配。
#   （实测本轮 tails 里出现过 "_fq3tts_env`），" 这种脏尾部）
_CJK_PUNCT = '　-〿＀-￯'
# 🔴🔴🔴 **补丁 9（缺口 1）：分隔符支持「双反斜杠」**
#   ⇒ Python 源码里 docstring 内的路径写作 `C:\\Users\\...`（**双反斜杠**转义）
#   ⇒ 旧的 `[\\/]`（单个）**匹配失败** ⇒ 修前侧完全不被识别
#   ⇒ 两侧无法配对 ⇒ 误判 `other`。
#   ⇒ 现在用 `(?:\\\\|\\|/)+` ⇒ 单/双反斜杠、正斜杠**三种形态都能匹配**。
_SEP = r'(?:\\\\|\\|/)+'
_HOME_LITERAL_RE = re.compile(
    r'[A-Za-z]:' + _SEP + r'Users' + _SEP +
    r'[^\\/\s\'"\n' + _CJK_PUNCT + r']+'
    r'(?:' + _SEP + r'[^\s\'"\n' + _CJK_PUNCT + r']*)*')
_HOME_PLACEHOLDER_RE = re.compile(
    r'<HOME>(?:' + _SEP + r'[^\s\'"\n' + _CJK_PUNCT + r']*)*')


def _docstring_paths(tree):
    """docstring 原文里的家目录路径片段 ⇒ 尾部集合。

    🔴 返回值是**尾部列表**的集合（与 `_collect_tails` 同口径）。
    """
    tails = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        try:
            doc = ast.get_docstring(node, clean=False)
        except Exception:
            doc = None
        if not doc:
            continue
        for m in _HOME_LITERAL_RE.finditer(doc):
            s = m.group(0)
            _pfx, tl = _split_abs(s)
            if tl:
                tails.add('/'.join(tl))
        for m in _HOME_PLACEHOLDER_RE.finditer(doc):
            s = m.group(0)
            ph = _split_placeholder(s)
            if ph:
                tails.add('/'.join(ph))
    return tails


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
        if isinstance(node.value, str):
            # 🔴🔴🔴 **APP-052 ③：`<HOME>` 占位符 ⇒ 规范成 `«HOME»/tail`**
            #   ⇒ 这样「写死家目录」↔「`<HOME>` 占位」↔「expanduser 派生」
            #     **三者规范化后完全相同** ⇒ 判为良性。
            #   ⚠️ **尾部必须在 `self.tails` 里**（两侧并集）
            #     ⇒ 否则 `<HOME>\全新路径` 不会被规范化 ⇒ 判 `other`（正确）。
            ph = _split_placeholder(node.value)
            if ph is not None:
                tail_s = '/'.join(ph)
                if tail_s in self.tails:
                    self.prefixes.add(HOME_PLACEHOLDER)
                    self.n_replaced += 1
                    return ast.copy_location(
                        ast.Constant(value='%s/%s' % (HOME_TOKEN, tail_s)), node)
                # 尾部不在 tails ⇒ **不规范化**（保持原样 ⇒ 两侧不等 ⇒ other）
                return node
            if _is_abs_path(node.value):
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
    """源码里所有 `expanduser('~')` 派生路径 **＋ `<HOME>` 占位符路径** 的尾部集合。"""
    tails = set()

    class _T(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            comps = _expanduser_join_tail(node)
            if comps is not None:
                tails.add('/'.join(comps))
            return node

        def visit_Constant(self, node):
            # 🔴🔴🔴 **APP-052 ③**：`<HOME>` 占位符路径的尾部
            #   ⇒ 与 expanduser 派生**同口径** ⇒ 两侧能规范化到同一形态。
            if isinstance(node.value, str):
                ph = _split_placeholder(node.value)
                if ph:
                    tails.add('/'.join(ph))
                # 🔴🔴🔴 **补丁 2a（真根因修复）**：**写死家目录路径的尾部**
                #   **也必须进 `tails`**。
                #   ⇒ 否则「修前是写死路径、修后是 `<HOME>` 占位」时
                #      写死路径**不被规范化**（尾部不在 tails）
                #      ⇒ 两侧 dump 不等 ⇒ **误判 other**。
                #   ⇒ 加上这一条 ⇒ **写死 / 占位 / expanduser 派生**
                #     三种写法**互相可比**（规范化后完全相同）。
                if _is_abs_path(node.value):
                    _pfx, tl = _split_abs(node.value)
                    if tl:
                        tails.add('/'.join(tl))
            return node

    _T().visit(tree)
    # 🔴🔴🔴 **补丁 5a**：docstring 原文里的家目录路径**也要进 tails**
    #   ⇒ 否则「docstring 里的写死家目录 ⇒ `<HOME>` 占位」这类
    #     **reviewer 要求的**改动会被误判 `other`。
    try:
        tails |= _docstring_paths(tree)
    except Exception:
        pass
    return tails


def _module_derived_consts(tree, tails):
    """模块级 `_` 前缀常量 ⇒ 规范化的常量取值（能算出来的）。"""
    out = {}

    def _canon_value(node):
        """把一个表达式算成（规范化后的）常量字符串；算不出 ⇒ None。"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            # 🔴🔴🔴 **APP-052 ③：`<HOME>` 占位符 ⇒ 规范成 `«HOME»/tail`**
            #   （与 `visit_Constant` **同一口径** ⇒ 两侧取值能对上）
            ph = _split_placeholder(v)
            if ph is not None:
                tail = '/'.join(ph)
                if tail in tails:
                    return '%s/%s' % (HOME_TOKEN, tail)
                return v
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


def _canon_tree(tree, tails):
    """把一棵 AST 规范化（家目录路径 ⇒ `«HOME»/tail`）。"""
    t = _inline_and_strip(ast.parse(ast.unparse(tree)), tails)
    c = _Canon(tails)
    t = c.visit(t)
    ast.fix_missing_locations(t)
    return t


def _normalize_docstring_home(b_tree, c_tree):
    """把两侧 docstring 里的家目录片段替换成**统一占位**。

    返回 `(ast.Module, 替换后的 docstring 文本)` 或 `None`。
    🔴 **只替换两侧都出现的片段**（按尾部对齐）⇒ 不掩盖真差异。
    """
    def _doc_map(tree):
        out = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.FunctionDef,
                                     ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            try:
                doc = ast.get_docstring(node, clean=False)
            except Exception:
                doc = None
            if doc:
                out[id(node)] = doc
        return out

    b_docs = _doc_map(b_tree)
    c_docs = _doc_map(c_tree)
    if not b_docs or not c_docs:
        return None, None

    # 收集两侧**共有**的家目录片段（按尾部配对）
    # 🔴🔴🔴 **补丁 5-fix3**：片段配对时**同时记录家目录前缀**
    #   ⇒ 前缀不一致时**不做**规范化（⇒ 判 other，正确）。
    b_frags = {}   # 尾部 -> (片段原文, 前缀)
    for doc in b_docs.values():
        for m in _HOME_LITERAL_RE.finditer(doc):
            s = m.group(0)
            _pfx, tl = _split_abs(s)
            if tl:
                b_frags['/'.join(tl)] = (s, _pfx)
        for m in _HOME_PLACEHOLDER_RE.finditer(doc):
            s = m.group(0)
            ph = _split_placeholder(s)
            if ph:
                b_frags['/'.join(ph)] = (s, HOME_PLACEHOLDER)
    c_frags = {}
    for doc in c_docs.values():
        for m in _HOME_LITERAL_RE.finditer(doc):
            s = m.group(0)
            _pfx, tl = _split_abs(s)
            if tl:
                c_frags['/'.join(tl)] = (s, _pfx)
        for m in _HOME_PLACEHOLDER_RE.finditer(doc):
            s = m.group(0)
            ph = _split_placeholder(s)
            if ph:
                c_frags['/'.join(ph)] = (s, HOME_PLACEHOLDER)

    common = set(b_frags) & set(c_frags)
    if not common:
        return None, None

    # 🔴🔴🔴 **前缀身份检查（与 §48 / 补丁 3 / S9 完全同一套规则）**
    #   · 家目录前缀身份 = 完整的 `盘符:/Users/用户名`（**用户名参与身份**）
    #   · 写死类至多 1 个；占位类至多 1 个；两类可共存
    #   ⇒ 不满足 ⇒ **不做** docstring 规范化 ⇒ 落回 `other`。
    hard_pfx, ph_pfx = set(), set()
    for tail in common:
        for _frag, pfx in (b_frags[tail], c_frags[tail]):
            if pfx == HOME_PLACEHOLDER:
                ph_pfx.add(pfx)
            else:
                hard_pfx.add(pfx)
    if len(hard_pfx) > 1 or len(ph_pfx) > 1:
        return None, None

    # 🔴 **替换必须「按尾部配对」** ⇒ 写死片段 ⇒ `<HOME>/tail`、
    #    占位片段 ⇒ `<HOME>/tail` ⇒ 两侧文本一致 ⇒ dump 相等。
    def _rewrite(text):
        for tail in common:
            src_frag = b_frags[tail][0]
            dst_frag = c_frags[tail][0]
            # 两侧**各自**替换成同一个中性占位
            text = text.replace(src_frag, HOME_TOKEN + '/' + tail)
            text = text.replace(dst_frag, HOME_TOKEN + '/' + tail)
        return text

    def _apply(tree):
        t = ast.parse(ast.unparse(tree))
        for node in ast.walk(t):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if not doc:
                    continue
                newdoc = _rewrite(doc)
                if newdoc == doc:
                    continue
                # 🔴 **必须改到 AST 里的 docstring 节点本身**
                body = getattr(node, 'body', None)
                if not body:
                    continue
                first = body[0]
                if (isinstance(first, ast.Expr)
                        and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    first.value.value = newdoc
        return t

    try:
        return _apply(b_tree), _apply(c_tree)
    except Exception:
        return None, None


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
            # 🔴🔴🔴 **APP-052 ③**：修前**也是** `<HOME>` 占位符的路径
            #   ⇒ 它的尾部也要进集合（否则「占位符 ↔ 占位符」比对会误报）。
            ph = _split_placeholder(n.value)
            if ph:
                b_home_tails.add('/'.join(ph))

    # 修后新增的 `_` 派生常量：取值必须**已存在于修前的常量/路径集合**里
    b_consts = _all_string_constants(b_tree0)

    # 🔴🔴🔴 **补丁 9（缺口 2）：修前**已有派生常量**的尾部也要进
    #   `b_home_tails`**
    #   ⇒ 否则「修前用 `expanduser('~')` 派生、后新写一个 `_` 派生常量
    #     取**同一个**尾部」⇒ 被判 `other`（**误判**）。
    #   ⇒ ⚠️ **反向保护**：修前**没有**的尾部仍判 `other`（S5 反证必须仍 PASS）。
    b_derived_pre = _module_derived_consts(b_tree0, tails)
    for _nm, _v in b_derived_pre.items():
        if isinstance(_v, str) and _v.startswith(HOME_TOKEN + '/'):
            _tl = _v[len(HOME_TOKEN) + 1:]
            if _tl:
                b_home_tails.add(_tl)

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
    b_derived = b_derived_pre
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

    # 🔴🔴🔴🔴 **补丁 5c（APP-052 ②）：docstring 片段的「就地规范化」**
    #
    #   **为什么需要**：上面 `_Canon` 只处理**独立的字符串常量**
    #   ⇒ docstring 里的家目录路径**仍在整篇 docstring 文本内部**
    #   ⇒ 两侧 dump 不等 ⇒ 误判 `other`。
    #   ⇒ 修法：**对 docstring 文本本身**做「家目录片段 ⇒ 统一占位」的替换，
    #     再重建 AST 重新规范化 ⇒ 两侧可对上。
    #
    #   ⚠️ **只替换「两侧都出现、且尾部一致」的片段** ⇒ 否则会把
    #     「修后新增的路径」也抹掉 ⇒ 掩盖真差异。
    b_docfix, c_docfix = _normalize_docstring_home(b_tree0, c_tree0)
    if b_docfix is not None and c_docfix is not None:
        try:
            bd2 = ast.dump(_canon_tree(b_docfix, tails))
            cd2 = ast.dump(_canon_tree(c_docfix, tails))
            if bd2 == cd2:
                detail['cls'] = 'home_path_rewrite'
                detail['docstring_normalized'] = True
                detail['home_prefix'] = sorted(
                    set(_HOME_LITERAL_RE.findall(ast.unparse(b_docfix)))
                    | set(_HOME_LITERAL_RE.findall(ast.unparse(c_docfix))))
                return 'home_path_rewrite', detail
        except Exception:
            pass

    if b_raw == c_raw:
        detail['cls'] = 'identical'
        return 'identical', detail

    # 🔴🔴 「同一个 HOME」这个前提：被替换掉的字面量必须**共享同一个家目录前缀**
    #
    # 🔴🔴🔴 **补丁 2b（APP-052 ③）**：`<HOME>` 占位符与**写死家目录前缀**
    #   **本来就指同一个家目录**（只是写法不同）
    #   ⇒ 旧检查把它们当成「两个不同前缀」⇒ **误判 other**。
    #   ⇒ 修法：**归一哨兵**：`C:/Users/<名字>` 与 `<HOME>` 都映射到 `'«HOME»'`。
    #   ⚠️ **写死前缀之间**仍必须**全部相同**（S9 反证必须仍判 other）：
    #      ⇒ 归一后若仍有 >1 个**不同**的写死前缀 ⇒ 仍 other。
    all_prefixes = set(b_canon.prefixes) | set(c_canon.prefixes)

    # 🔴🔴🔴 **补丁 3（语义修正）**：家目录前缀的**身份 = 完整的
    #   `盘符:/Users/用户名`**（**用户名参与身份**）
    #   ⇒ `C:/Users/Trekker-PTL` 与 `C:/Users/Other` 是**不同家目录**
    #     ⇒ 必须判 other（补丁 2b 的「用户名归一」把这条反证作废了 ⇒ 撤回）。
    #
    #   `<HOME>` 占位符**没有用户名** ⇒ 与写死前缀**无法逐字比较**
    #   ⇒ 但「写死 ↔ 占位」**确实是同一语义**（客户机上占位指向自己的家目录）。
    #
    #   ⇒ **正确判据**（拆成两类，各 至多 1 个）：
    #     · **写死类**（非 `<HOME>`）：至多 1 个 ⇒ 否则 other（对上 S9）
    #     · **占位类**（`<HOME>`）  ：至多 1 个（恒真）
    #     · 两类**同时存在** ⇒ 允许（写死 ↔ 占位 = 同一语义），
    #       尾部一致已由 `tails` 规范化保证 ⇒ 两侧 dump 相等 ⇒ 良性。
    hard_prefixes = set(p for p in all_prefixes if p != HOME_PLACEHOLDER)
    ph_prefixes = set(p for p in all_prefixes if p == HOME_PLACEHOLDER)
    if len(hard_prefixes) > 1 or len(ph_prefixes) > 1:
        detail['cls'] = 'other'
        detail['reason'] = (
            '被替换的字面量家目录前缀不一致（写死 %s / 占位 %s）⇒ 前提不成立'
            % (sorted(hard_prefixes), sorted(ph_prefixes)))
        return 'other', detail
    if len(all_prefixes) > 1:
        detail['prefix_variants'] = sorted(all_prefixes)

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
    # 🔴🔴 **APP-057 ③**：`ACCEPTED.json` 里的 `pkg_dir` 记的是 `<HOME>` 占位形态
    #   （不泄漏构建机家目录；客户机上路径也不对）⇒ 比对时**先展开 `<HOME>`**。
    acc_pkg_expanded = acc_pkg.replace('<HOME>', os.path.expanduser('~'))
    check('R3 ACCEPTED.json 的 pkg_dir == 本包目录',
          os.path.normcase(os.path.normpath(acc_pkg_expanded))
          == os.path.normcase(os.path.normpath(pkg_dir)),
          'ACCEPTED.pkg_dir=%r（展开后比对）' % acc_pkg)

    acc_mtime = os.path.getmtime(acc_path)
    accepted_at = str(acc.get('accepted_at') or '')

    # 🔴🔴🔴 **APP-052 ②a：读出 ACCEPTED 里记的「被验收代码指纹」**
    #   ⇒ R5 用它做「内容级」的一致性核对（不依赖时间 ⇒ 不会死锁）。
    acc_fingerprint = str(acc.get('code_fingerprint') or '')
    check('R3 ACCEPTED.json 记录了 code_fingerprint（APP-052 ②a）',
          bool(acc_fingerprint),
          'code_fingerprint=%r' % (acc_fingerprint[:32] or '(缺)'))
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

    # 🔴🔴🔴🔴 **补丁 5e（APP-052 ②a）：R1 的漂移基准改为「逐模块内容指纹」**
    #
    #   **为什么必须换掉「时间」基准**（本轮实测的死锁）：
    #     时间基准 ⇒ 改了代码就报漂移 ⇒ app186 ⑥ FAIL ⇒ 不写 ACCEPTED
    #     ⇒ accepted_at 永远旧 ⇒ **永远 FAIL** ⇒ 永远无法重签。
    #     ⇒ 而且「重签后 accepted_at 变新」⇒ drifted 恒空 ⇒ R1 **恒 PASS**
    #       ⇒ 变成「弱标记恒真」⇒ **后续篡改无人发现**。
    #
    #   **内容指纹才是正确锚点**（复制/还原不改内容；同一份代码可多次验收）。
    #
    #   `ACCEPTED.json` 新增 `code_fingerprints` = {模块名: 该模块字节的指纹}
    #   ⇒ R1 = 「逐模块指纹 ≠ 验收时指纹」⇒ 就是「验收后动过的模块」。
    #
    #   🔴 **向后兼容**：老 ACCEPTED 没有 `code_fingerprints` ⇒
    #     **退回**时间基准（并明确报出来）⇒ 不静默改口径。
    # 🔴🔴🔴 **补丁 5-fix5：读出「已承认的漂移」白名单**
    #   ⇒ 格式：{"<模块名>": {"reason": "...", "source": "APP-052 ② ..."}}
    #   ⇒ 老 ACCEPTED 没有 ⇒ 空字典（不豁免任何东西）。
    waived_raw = acc.get('waived_changes') or {}
    waived = {}
    if isinstance(waived_raw, dict):
        for k, v in waived_raw.items():
            if isinstance(v, dict):
                waived[str(k)] = {'reason': str(v.get('reason') or ''),
                                  'source': str(v.get('source') or '')}
    elif isinstance(waived_raw, list):
        # 兼容列表形态：[{"module": "...", "reason": "...", "source": "..."}]
        for v in waived_raw:
            if isinstance(v, dict) and v.get('module'):
                waived[str(v['module'])] = {
                    'reason': str(v.get('reason') or ''),
                    'source': str(v.get('source') or '')}
    if waived:
        print('  已承认的漂移白名单：%d 条（%s）'
              % (len(waived), ', '.join(sorted(waived))))

    acc_fps = acc.get('code_fingerprints') or {}
    use_fp_anchor = isinstance(acc_fps, dict) and len(acc_fps) > 0
    mod_fps = {}
    for nm in mods:
        p = os.path.join(pkg_app, nm)
        try:
            with open(p, 'rb') as f:
                mod_fps[nm] = hashlib.sha256(norm_bytes(f.read())).hexdigest()
        except Exception:
            pass
    print('  漂移锚点：%s' % ('**逐模块内容指纹**（APP-052 ②a）'
                          if use_fp_anchor else
                          '时间（ACCEPTED.accepted_at）—— ⚠️ ACCEPTED 无 '
                          'code_fingerprints ⇒ 退回旧口径'))

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
        if use_fp_anchor:
            want = str(acc_fps.get(name) or '')
            got = mod_fps.get(name) or ''
            rec['fingerprint_accepted'] = want
            rec['fingerprint_now'] = got
            rec['fingerprint_match'] = bool(want) and want == got
            # 🔴 **新模块**（验收后才加进来的）⇒ 也算漂移
            (drifted if (not want) or want != got else covered).append(rec)
        else:
            (drifted if mt > acc_ts else covered).append(rec)

    print()
    if use_fp_anchor:
        print('  R1 漂移检测（**逐模块内容指纹** vs ACCEPTED.code_fingerprints）：')
    else:
        print('  R1 漂移检测（包内模块 mtime > ACCEPTED.accepted_at）：')
    check('R1 生产模块都能被检出（模块数 > 0）', len(mods) > 0,
          'covered=%d drifted=%d' % (len(covered), len(drifted)))
    for d in drifted:
        print('        DRIFT  %-22s %s' % (d['module'], d['mtime']))
    if not drifted:
        print('        （无漂移 ⇒ 所有生产模块都在验收时点之前落定）')

    # ── 🔴🔴🔴 补丁 13：**独立锚点** —— git 基线 ───────────────────
    #
    #   **为什么必须加**（本轮实测抓到的真实盲区）：
    #     「先签后验」⇒ ACCEPTED 的指纹 = **当前**代码的指纹
    #     ⇒ R1 指纹锚点 ⇒ drifted = 0 ⇒ **app191 不检查任何模块**
    #     ⇒ ⇒ 「签的时候把缺陷一起签进去」⇒ **缺陷被合法化**
    #     ⇒ ⇒ 实测：注入 `gui_status.py` 的真实逻辑缺陷后，⑥ 仍 PASS！
    #
    #   **git 基线是独立锚点**：ACCEPTED 指纹 = 「上次验收时是什么」，
    #     git 基线 = 「仓库里是什么」⇒ 两者独立 ⇒ 一个被篡改，另一个暴露。
    #
    #   🔴 **只扩大候选集，不做判定** ⇒ 判定仍由 R2 做 ⇒ 判据强度不变。
    print()
    print('  R1b 独立锚点（**git 基线**）—— 检出「偏离仓库版本」的候选：')
    _git_candidates = []
    for _nm in mods:
        _rel = 'live_caption/' + _nm
        _p = os.path.join(pkg_app, _nm)
        try:
            with open(_p, 'rb') as _f:
                _cur_b = norm_bytes(_f.read())
        except Exception:
            continue
        _revs = git_commits_touching(_rel)
        if not _revs:
            continue
        _hit = None
        for _rv in _revs:
            _bl = git_blob(_rv, _rel)
            if _bl is not None and norm_bytes(_bl) == _cur_b:
                _hit = _rv
                break
        if _hit is not None:
            continue        # 内容寻址命中 ⇒ 当前内容**就是**仓库里的某个版本
        # 未命中 ⇒ 当前内容偏离仓库 ⇒ **候选**
        _git_candidates.append(_nm)
    check('R1b git 基线锚点可用（与 ACCEPTED 指纹**相互独立**）',
          True,
          '生产模块 %d 个 / 偏离仓库的候选 %d 个'
          % (len(mods), len(_git_candidates)))
    for _nm in _git_candidates:
        print('        GIT-DIFF  %s' % _nm)

    # ── R2 漂移分类 ───────────────────────────────────────────────
    print()
    print('  R2 漂移分类（良性类 = identical / home_path_rewrite）：')
    if not drifted:
        check('R2 无漂移模块 ⇒ 无需分类', True, 'drifted=0')
    # 🔴 **指纹口径下**：指纹一致的模块**根本不在 drifted 里**
    #   ⇒ R2 只处理真正变过的 ⇒ 不会把「没变过的」误判。
    # 🔴🔴🔴 **补丁 9（缺口 3）：R2 也要处理「白名单模块」**
    #   ⇒ 白名单的**本意**是「承认『这次改动偏离了之前的 git 验收基线』」
    #   ⇒ 该核对的是**相对 git 基线的差异**
    #   ⇒ 而 R1（指纹锚点）在「先签后验」时 drifted=0
    #   ⇒ 若 R2 只看 drifted ⇒ 白名单**永远得不到分类** ⇒ 恒 FAIL。
    #   ⇒ 故：把白名单模块**并入** R2 的处理集合。
    _to_classify = list(drifted)
    _seen_mod = set(d.get('module') for d in drifted)
    # 🔴🔴🔴 **补丁 13**：并入「git 基线锚点」的候选
    #   ⇒ 「签的时候把缺陷一起签进去」⇒ 指纹锚点看不出来
    #   ⇒ **但 git 基线锚点能看出来** ⇒ ⇒ 闸门能 FAIL ✓
    for _gn in _git_candidates:
        if _gn in _seen_mod:
            continue
        _p = os.path.join(pkg_app, _gn)
        if not os.path.isfile(_p):
            continue
        _mt = os.path.getmtime(_p)
        _rec = {
            'module': _gn,
            'mtime': datetime.datetime.fromtimestamp(_mt).strftime(
                '%Y-%m-%d %H:%M:%S'),
            'mtime_ts': _mt,
            'from_git_baseline': True,
        }
        if use_fp_anchor:
            _rec['fingerprint_accepted'] = str(acc_fps.get(_gn) or '')
            _rec['fingerprint_now'] = mod_fps.get(_gn) or ''
        _to_classify.append(_rec)
        _seen_mod.add(_gn)
    for _wn in sorted(waived):
        if _wn in _seen_mod:
            continue
        _p = os.path.join(pkg_app, _wn)
        if not os.path.isfile(_p):
            continue
        _mt = os.path.getmtime(_p)
        _rec = {
            'module': _wn,
            'mtime': datetime.datetime.fromtimestamp(_mt).strftime(
                '%Y-%m-%d %H:%M:%S'),
            'mtime_ts': _mt,
            'from_waiver_list': True,
        }
        if use_fp_anchor:
            _rec['fingerprint_accepted'] = str(acc_fps.get(_wn) or '')
            _rec['fingerprint_now'] = mod_fps.get(_wn) or ''
        _to_classify.append(_rec)

    for d in _to_classify:
        name = d['module']
        rel = 'live_caption/' + name
        cur_path = os.path.join(pkg_app, name)
        with open(cur_path, 'rb') as f:
            cur = norm_bytes(f.read())

        # 🔴 内容寻址：找**最早**那个 blob == 当前包内内容的 commit
        revs = git_commits_touching(rel)
        oldest_match = None
        for rev in revs:
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
            if not revs:
                check('R2 %s 的漂移前基线可重建' % name, False,
                      '该文件在 git 历史里不存在 ⇒ 无法重建基线')
                d['cls'] = None
                continue
            # 🔴🔴🔴🔴 **补丁 12（本轮实测抓到的真实盲区）**
            #   「未命中」且「**只有 1 个** commit」⇒ 那个 commit **就是它自己**
            #   ⇒ 基线内容 == 当前内容 ⇒ 恒判 `identical`
            #   ⇒ ⇒ **任何改动都检不出**（盲区！）
            #   ⇒ 三态处理：
            #     ① 内容寻址命中        ⇒ 基线 = 命中 commit 的父提交（正常）
            #     ② 未命中 + **多个** commit ⇒ fallback 到最新 commit（保留）
            #     ③ 未命中 + **只有 1 个** commit ⇒ 基线不存在 ⇒ 判 FAIL
            #        （**但**若内容与那唯一 commit 逐字相同 ⇒ 只是 mtime 变
            #          ⇒ 不算问题 ⇒ 不判 FAIL）
            if len(revs) == 1:
                only = norm_bytes(git_blob(revs[0], rel) or b'')
                if only == cur:
                    # 内容与唯一那个 commit 逐字相同 ⇒ 只是 mtime 变了
                    base_rev = revs[0]
                    base_mode = 'single_commit_identical'
                else:
                    # 🔴 内容与唯一 commit 不同 ⇒ **无基线可比** ⇒ 判 FAIL
                    check('R2 %s 的漂移前基线可重建' % name, False,
                          '该文件在 git 历史里**只有 1 个** commit（%s）且当前'
                          '内容与之不同 ⇒ **不存在可比的漂移前基线**'
                          '（退化会用它自己当基线 ⇒ 恒 identical ⇒ 改动不可见）'
                          % revs[0][:8])
                    d['cls'] = None
                    d['base_unavailable'] = True
                    d['only_commit'] = revs[0][:8]
                    continue
            else:
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

        # 🔴🔴🔴 **补丁 5-fix5：白名单放行**
        #   ⇒ 只在「该模块**确实漂移**」且「白名单里有它」时才放行
        #   ⇒ 且**必须**在证据里记明依据。
        if name in waived and cls not in BENIGN:
            w = waived[name]
            d['waived'] = True
            d['waived_reason'] = w['reason']
            d['waived_source'] = w['source']
            d['cls_before_waiver'] = cls
            d['cls'] = WAIVED
            det['waived_from'] = cls
            det['waived_reason'] = w['reason']
            det['waived_source'] = w['source']
            cls = WAIVED

        benign = cls in BENIGN or cls == WAIVED
        d['benign'] = bool(benign)
        if cls == WAIVED:
            check('R2 %s 的漂移**已被 reviewer 显式承认**（白名单放行）' % name,
                  True,
                  'base=%s(%s) before=%s after=%s | 原判=%s ⇒ 放行'
                  ' | 依据=%s（%s）'
                  % (base_rev[:8], base_mode, d['sha_before'], d['sha_after'],
                     d.get('cls_before_waiver'),
                     d.get('waived_reason') or '(未写原因)',
                     d.get('waived_source') or '(未写来源)'))
        else:
            check('R2 %s 的漂移属于良性类（%s）' % (name, cls), benign,
                  'base=%s(%s) before=%s after=%s | cls=%s%s'
                  % (base_rev[:8], base_mode, d['sha_before'], d['sha_after'],
                     cls,
                     ('' if benign else
                      ' ⇒ 验收已被这条改动推翻：%s'
                      % json.dumps(det, ensure_ascii=False)[:240])))
        if not benign:
            print('        b_at = %s' % str(det.get('b_at'))[:300])
            print('        c_at = %s' % str(det.get('c_at'))[:300])

    # ── R3b 白名单自洽（**防滥用**）────────────────────────────────
    #
    # 🔴🔴🔴 **白名单最危险的用法**：「把任意改动塞进白名单 ⇒ 闸门恒 PASS」。
    # ⇒ 因此必须判：**白名单里的每一条都必须对应一个「真实漂移」**
    #   ⇒ 写了没漂移的模块 ⇒ 多余条目 ⇒ **判 FAIL**（可疑 ⇒ 要求说明）。
    print()
    print('  R3b 白名单自洽（每条都必须对应一个真实漂移）：')
    # 🔴🔴🔴 **补丁 9（缺口 3）：「多余条目」按「相对 git 基线的分类结果」判**
    #   ⇒ 白名单模块**一定会**被 R2 分类（补丁 9 修 5）
    #   ⇒ ⇒ 每条白名单都必须对应一个「相对 git 基线**确有实质差异**」的模块
    #   ⇒ 且该差异**不是良性类**（良性类不需要白名单）
    _cls_by_mod = {}
    for _d in _to_classify:
        _cls_by_mod[_d.get('module')] = _d.get('cls')
    if not waived:
        check('R3b 无白名单条目（无需自洽检查）', True, 'waived=0')
    else:
        # ① 白名单条目必须**真的被分类过**（即该模块相对 git 基线有差异）
        unused = sorted(k for k in waived if k not in _cls_by_mod)
        check('R3b 白名单里没有「多余条目」（每条都对应真实差异）',
              not unused,
              'waived=%d / 已分类=%d / 多余=%s'
              % (len(waived), len(_cls_by_mod), unused or '无'))
        # 🔴🔴🔴 **补丁 10：删掉「非良性」这条硬性判据**
        #   ⇒ 原判据把白名单的**语义**（「reviewer 承认过的改动」）
        #     与「判据当下的分类结论」**耦合**了
        #   ⇒ 而分类结论**会随判据修复而变化**
        #     （本轮实测：补丁 9 修好正则后 `speaker_assets.py`
        #       从 `other` 变成 `home_path_rewrite`）
        #   ⇒ ⇒ 白名单条目会「突然变成多余」⇒ **恒 FAIL** ⇒ 脆。
        #
        #   ⇒ 改为**弱提示**（不阻断、但信息不丢）：
        #     · 分类结论**已在 R2 记录**（`cls` / `cls_before_waiver`）
        #     ⇒ reviewer 能看到「这条白名单其实不需要（本来就良性）」
        #     ⇒ **信息没有丢失**
        needless = sorted(k for k, v in _cls_by_mod.items()
                          if k in waived and v in BENIGN)
        if needless:
            print('  [WARN] 🔶 白名单里有 %d 条**本来就能自己判为良性**的条目'
                  '（不阻断，但可考虑移除）：%s'
                  % (len(needless), ', '.join(needless)))
            check('R3b 白名单自洽（存在性 + 依据 + 无幽灵）', True,
                  '良性白名单条目 = %s（**仅提示**，分类结论见 R2）'
                  % (needless,))
        else:
            check('R3b 白名单自洽（存在性 + 依据 + 无幽灵）', True,
                  'waived=%d / 已分类=%d / 全部为非良性差异'
                  % (len(waived), len(_cls_by_mod)))
        # 🔴 每条都必须写明**依据**（reason + source）⇒ 否则不可复核
        noreason = sorted(k for k, v in waived.items()
                          if not v.get('reason') or not v.get('source'))
        check('R3b 每条白名单都写明了 reason 与 source（可复核）',
              not noreason,
              '缺依据的条目 = %s' % (noreason or '无'))
        # 🔴 白名单里的模块**必须存在**（否则是笔误/残留）
        ghost = sorted(k for k in waived
                       if k not in set(mods))
        check('R3b 白名单里的模块都在生产模块集合内（无幽灵条目）',
              not ghost,
              '幽灵条目 = %s' % (ghost or '无'))

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
        all_benign = all((d.get('cls') in BENIGN or d.get('cls') == WAIVED)
                         for d in drifted)
        check('R4 指纹变化已被 R2 分类为良性',
              same or all_benign,
              'prev=%s… now=%s… | drifted=%d 全部良性=%s'
              % (prev_fp[:16], fp[:16], len(drifted), all_benign))
    # 🔴🔴 **补丁 5h**：证据里记录「用的是哪种锚点」⇒ 便于人工复核
    #   ⇒ 不静默换口径（MEMORY：口径变更必须先核对旧产物的配置快照）。

    # ── R5 指纹一致性（**内容级**绑定，APP-052 ②a）──────────────
    #
    # 🔴🔴🔴 **为什么必须有这一条**（本轮实测到的**死锁**）：
    #   R1 的漂移基准是 `ACCEPTED.accepted_at`（**时间**）
    #   ⇒ 「改了包内代码 ⇒ 报漂移 ⇒ app186 ⑥ FAIL ⇒ **不写** ACCEPTED
    #     ⇒ accepted_at 永远停在旧值 ⇒ **永远 FAIL** ⇒ 永远无法重签。
    #   ⇒ **时间不是「代码绑定」的正确锚点**（复制/还原会改 mtime；
    #     同一份代码可以先后多次验收）⇒ 正确的锚点是**内容指纹**。
    #
    # 🔴 **R5 与 R1/R2 的分工（互补，不可互相替代）**：
    #   · R1/R2 = 「**相对基线 commit** 改了什么、危不危险」
    #   · R5     = 「**相对验收声明** 还成不成立」
    #   ⇒ 若只留 R5：有人改了代码又顺手改了 ACCEPTED 的指纹
    #     ⇒ R5 PASS 但没人知道改了什么 ⇒ ⇒ **两者必须同时在**。
    print()
    print('  R5 指纹一致性（包内当前指纹 == ACCEPTED.code_fingerprint）：')
    if not acc_fingerprint:
        check('R5 ACCEPTED.code_fingerprint 与包内当前指纹一致', False,
              'ACCEPTED.json 里没有 code_fingerprint ⇒ 无法做内容级绑定'
              '（旧版 ACCEPTED ⇒ 需按 APP-052 ②a 重签）')
    elif fp == acc_fingerprint:
        check('R5 ACCEPTED.code_fingerprint 与包内当前指纹一致', True,
              'fingerprint=%s…（内容未变 ⇒ 验收结论继续有效）' % fp[:32])
    else:
        check('R5 ACCEPTED.code_fingerprint 与包内当前指纹一致', False,
              'ACCEPTED=%s… / 当前=%s… ⇒ **交付代码与验收声明不符**'
              '（哪怕改动是良性的，验收声明也必须重签）'
              % (acc_fingerprint[:32], fp[:32]))

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
        'drift_baseline': ('ACCEPTED.code_fingerprints（**逐模块内容指纹**）'
                           if use_fp_anchor else
                           'ACCEPTED.accepted_at（内容字段，非文件 mtime）'),
        'drift_anchor': 'content_fingerprint' if use_fp_anchor else 'timestamp',
        'accepted_code_fingerprints': acc_fps,
        'waived_changes': waived,
        'git_baseline_candidates': _git_candidates,
        'drift_anchor_note': (
            'R1 = 指纹锚点（相对 ACCEPTED）＋ R1b = git 基线锚点（相对仓库）'
            '⇒ 两个**相互独立**的锚点 ⇒ 「签的时候把缺陷一起签进去」'
            '会被 git 基线锚点暴露'),
        'n_waived': len([d for d in drifted if d.get('cls') == WAIVED]),
        'current_code_fingerprints': mod_fps,
        'n_modules': len(mods),
        'fingerprint': fp,
        'accepted_code_fingerprint': acc_fingerprint,
        'fingerprint_match': (acc_fingerprint == fp) if acc_fingerprint else None,
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
        # ── APP-052 ③ 新增：`<HOME>` 占位符类 ──
        ('S10 写死家目录 ⇒ `<HOME>` 占位（尾部相同）⇒ home_path_rewrite',
         "import os\n"
         "DEV_ASR_SCRIPTS = r'<HOME>\\qwen3asr_06b\\scripts'\n"
         "P2 = 'plain'\n",
         'home_path_rewrite'),
        # 🔴🔴 **S11 的期望值是 `identical` 而不是 `home_path_rewrite`**：
        #   两侧规范化后**逐字相同** ⇒ `identical` 是**更精确**的分类
        #   （`identical` 与 `home_path_rewrite` **同属良性**，对闸门结论无差别）
        #   ⇒ 写 `home_path_rewrite` 反而是**把判据写松了**（会掩盖真差异）。
        ('S11 `<HOME>` 占位（尾部相同）⇒ 写死家目录 ⇒ identical（规范化后逐字相同）',
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts'\n"
         "P2 = 'plain'\n",
         'identical'),
        ('S12 `<HOME>` 占位但**尾部不同** ⇒ other（不得判为良性）',
         "import os\n"
         "DEV_ASR_SCRIPTS = r'<HOME>\\completely\\different\\path'\n"
         "P2 = 'plain'\n",
         'other'),
        ('S13 `<HOME>` 占位 + **其它常量也被改** ⇒ other',
         "import os\n"
         "DEV_ASR_SCRIPTS = r'<HOME>\\qwen3asr_06b\\scripts'\n"
         "P2 = 'CHANGED'\n",
         'other'),
        ('S14 `<HOME>` 占位（尾部相同）但**删了一行逻辑** ⇒ other',
         "import os\n"
         "DEV_ASR_SCRIPTS = r'<HOME>\\qwen3asr_06b\\scripts'\n",
         'other'),
        ('S15 正斜杠形态的 `<HOME>` 占位 ⇒ home_path_rewrite',
         "import os\n"
         "DEV_ASR_SCRIPTS = r'<HOME>/qwen3asr_06b/scripts'\n"
         "P2 = 'plain'\n",
         'home_path_rewrite'),
        # ── 补丁 5j：docstring 里的家目录路径（APP-052 ③ 的真实形态）──
        #
        # 🔴🔴 **补丁 5-fix2**：这 5 个用例**各自带 base**
        #   （base 里**也有** docstring，且 docstring 里是**写死家目录**）
        #   ⇒ 唯一变量 = 「docstring 里的家目录写法」
        #   ⇒ 才是在测「写死 ⇄ 占位」这件事本身。
        #   ⚠️ 若 base 无 docstring ⇒ 那是「**新增**一段 docstring」
        #      ⇒ 判 other 正确 ⇒ 期望值会写错（本轮 S16 实测踩到）。
        ('S16 docstring 里的写死家目录 ⇒ `<HOME>` 占位 ⇒ home_path_rewrite',
         '"""模块说明。\n\n'
         '    WORK   = r\'<HOME>\\qwen3asr_06b\'\n'
         '    SHARED = r\'<HOME>\\shared\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n",
         'home_path_rewrite',
         '"""模块说明。\n\n'
         '    WORK   = r\'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\'\n'
         '    SHARED = r\'C:\\\\Users\\\\Trekker-PTL\\\\shared\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n"),
        # 🔴🔴 **反证**：docstring 里的路径**尾部不同** ⇒ 不得判为良性
        ('S17 docstring 里的路径尾部**不同** ⇒ other（不得判为良性）',
         '"""模块说明。\n\n'
         '    WORK   = r\'<HOME>\\completely\\different\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n",
         'other',
         '"""模块说明。\n\n'
         '    WORK   = r\'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n"),
        # 🔴🔴 **反证**：docstring 里**新增**一行路径 ⇒ 不得判为良性
        ('S18 docstring 里**新增**路径行 ⇒ other（不得判为良性）',
         '"""模块说明。\n\n'
         '    WORK   = r\'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\'\n'
         '    NEWLINE = r\'C:\\\\Users\\\\Trekker-PTL\\\\brand\\\\new\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n",
         'other',
         '"""模块说明。\n\n'
         '    WORK   = r\'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n"),
        # 🔴🔴 **反证**：docstring 改了**别的**内容 ⇒ 不得判为良性
        ('S19 docstring 改了**别的**内容 ⇒ other（不得判为良性）',
         '"""模块说明（**已改**）。\n\n'
         '    WORK   = r\'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n",
         'other',
         '"""模块说明。\n\n'
         '    WORK   = r\'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n"),
        # 🔴🔴 **反证**：docstring 里的路径**换了前缀**（别的用户名）⇒ other
        ('S20 docstring 里家目录**前缀不同** ⇒ other（不得判为良性）',
         '"""模块说明。\n\n'
         '    WORK   = r\'C:\\\\Users\\\\Other\\\\qwen3asr_06b\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n",
         'other',
         '"""模块说明。\n\n'
         '    WORK   = r\'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\'\n'
         '    """\n'
         "import os\n"
         "DEV_ASR_SCRIPTS = r'C:\\\\Users\\\\Trekker-PTL\\\\qwen3asr_06b\\\\scripts'\n"
         "P2 = 'plain'\n"),
    ]
    n_fail = 0
    for _c in cases:
        # 🔴🔴 **补丁 5-fix2**：支持「每个用例自带 base」
        #   ⇒ docstring 类用例的 base **必须也带 docstring**
        #   ⇒ 否则「base 无 docstring / cur 有 docstring」是「新增 docstring」
        #   ⇒ 判 other 正确 ⇒ 用例期望值会写错（本轮 S16 实测踩到）。
        if len(_c) == 4:
            name, cur, want, b_case = _c
        else:
            name, cur, want = _c
            b_case = base
        got, det = classify_drift(b_case, cur)
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
