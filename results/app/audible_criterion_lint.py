# -*- coding: utf-8 -*-
"""audible_criterion_lint.py —— 「**弱判据**」这一类缺陷的**扫描器单一来源**。

🔴🔴 **为什么需要这个模块（2026-10-27 §62）**：

APP-021（`status/app/CORRECTIONS_APP.md` L256）**明文**要求：

> 「app071 的判据改成：`n_read` 增量 ≥ 本句样本数，并且本句峰值 > 1e-2。」
> 「不要用 "played ≥ 1" 或者假 service 的冒烟结果来宣称"能出声"。」

⇒ **实测该要求从未被执行**（`app071`/`app074`/`app075`/`app077`/`app039`
至今仍用 `n_played >= 1`）⇒ ⇒ **这一类缺陷会复发**（§36 同源教训：
「修掉一处」≠「这一类不会再来」）⇒ **必须把它变成闸门**。

## 🔴 闸门规则（本模块是**唯一定义处**）

**违规形态**：`n_played`（事件计数）与**整数常量 0 / 1** 做比较。

| 形态 | 是否违规 | 理由 |
|---|---|---|
| `st.get('n_played', 0) >= 1` | ✅ 违规 | APP-021 点名作废的弱判据 |
| `st.get('n_played', 0) > 0` | ✅ 违规 | 等价写法，同一缺陷 |
| `st.get('n_played', 0) == 1` | ✅ 违规 | 等价写法，同一缺陷 |
| `st.get('n_played', 0) > played_before` | ❌ 不违规 | **相对增量** ⇒ 不会把「别的句子的计数」当本句证据 |
| `self.n_played += 1`（service 内部记账） | ❌ 不违规 | `self.n_played` 是 Attribute，不是常量 ⇒ 规则不命中 |
| `ev2.get('n_played', 0) + ev2.get('n_dropped', 0) == ev2.get('n_submitted', -1)` | ❌ 不违规 | **守恒不变式**（丢句记账）⇒ 左值是**和式**，不是「等一个事件」 ⇒ 不构成 APP-021 点名的弱判据 |

🔴🔴 **2026-11-01 §121 实测修正（E9 误报，根因是 AST 拆解过粗）**：

原实现用 `ast.walk(cmp)` 找比较器里的整数常量 ⇒ 把
`ev2.get('n_submitted', -1)` 里的 **`-1`** 拆成
`UnaryOp(USub, Constant(1))` ⇒ `Constant(1)` 命中 `VIOLATION_CONSTS` ⇒
**把「守恒不变式」误判成弱判据**（实测命中 `app186_app051_acceptance_gate.py: L174`）。

⇒ **修法**：比较器里的常量必须**是该比较器子树的最外层常量**
（`ast.Constant` 直接是 comparator 本身，或 comparator 是
`UnaryOp` 且其 operand 是 `Constant`）⇒ **负数 `-1` 仍然算常量 `-1`**，
不会因为「`ast.walk` 拆掉了负号」而被当成 `1`。
⇒ 同时：**左值必须是「计数本身」而不是「和式」** ⇒
`n_played + n_dropped == n_submitted` 这种**守恒式**不命中。

⇒ **「等一个事件」必须写成相对增量**（和提交前的快照比），
   **「判是否出声」必须走 `tts_audible_criterion.evaluate_audible()`**。
   两者**物理分离** ⇒ 扫描器不必去猜作者的意图。

## 🔴🔴 两条实现纪律（都是踩过的坑）

1. **不要剥注释**：Python 的 `ast.parse` **本来就不含注释节点**
   ⇒ 第一版闸门「剥掉注释行」是**多余**的，而且**破坏了多行字符串**
   （`re.findall(rb'^## §', ...)` 这类 bytes 字面量被撕开 ⇒ `SyntaxError`
   ⇒ 6 个文件解析失败 ⇒ 扫描覆盖面悄悄缩水）。
2. **解析失败必须判 FAIL（闸门自己失效）**，绝不能当成「无违规」
   ⇒ 第一版 `except SyntaxError: return []` ⇒ **闸门永远 PASS**
   ⇒ **假通过**（比缺陷本身更危险）。

## 🔴 未跟踪文件的处理

历史遗留的**未跟踪**脚本（如 `app010_append_status.py`，其 `rb'^## §'`
是真正的语法错误）不属于本次闸门的责任范围 ⇒ 记入 `skipped`、
**在报告里列出来**，但**不判 FAIL**；
**已跟踪**文件解析失败 ⇒ 一律判 FAIL（闸门失效必须暴露）。

## 用法

```python
from audible_criterion_lint import scan_file, scan_dir

rep = scan_file('results/app/app071_tts_worker_error_probe.py')
if rep.parse_failed:      # ⇒ 闸门失效
    ...
if rep.violations:        # ⇒ 有弱判据
    ...
```
"""
from __future__ import annotations

import ast
import os
import subprocess
from typing import Dict, List, Optional

# 🔴 关注的键名（只查字符串常量 ⇒ `self.n_played` 这种 Attribute 不命中）
TARGET_KEY = 'n_played'

# 🔴 违规的比较运算符
#   GtE/Gt/Eq/NotEq 都算 ⇒ `>= 1` / `> 0` / `== 1` / `!= 1` 全部命中
VIOLATION_OPS = (ast.GtE, ast.Gt, ast.Eq, ast.NotEq)

# 🔴 违规的整数常量（`>= 1` / `> 0` ⇒ 计数阈值）
VIOLATION_CONSTS = (1, 0)


class ScanReport(object):
    """单个文件的扫描结果。"""

    def __init__(self, path: str, tracked: bool = True):
        self.path = path
        self.tracked = tracked
        self.parse_failed = False
        self.parse_error = ''
        self.violations: List[str] = []

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def to_dict(self) -> Dict[str, object]:
        return dict(path=self.path, tracked=self.tracked,
                    parse_failed=self.parse_failed,
                    parse_error=self.parse_error,
                    violations=list(self.violations))

    def __repr__(self) -> str:
        return '<ScanReport %s violations=%d parse_failed=%s>' % (
            self.name, len(self.violations), self.parse_failed)


def _comparator_int_value(cmp_node: ast.AST) -> Optional[int]:
    """取「比较器本身」的整数值（**不拆解子树**）。

    🔴🔴 **为什么不能 `ast.walk`（§121 实测修正）**：
    `ast.walk` 会把 `ev2.get('n_submitted', -1)` 拆成
    `Call` → `Constant('n_submitted')` + `UnaryOp(USub, Constant(1))`
    ⇒ 其中 `Constant(1)` 命中 `VIOLATION_CONSTS` ⇒
    **`-1` 被当成 `1`** ⇒ 把「守恒不变式」误判成弱判据。

    ⇒ **正确口径**：只认 comparator **本身**就是整数常量
    （`Constant` 直接是 comparator），或 comparator 是
    `UnaryOp(USub/USub)` 且 operand 是整数常量 ⇒ **负数按其真实值算**
    （`-1` ⇒ `-1`，不在 `VIOLATION_CONSTS` ⇒ 不命中）。

    ⚠️ 其它形态（`get('n_played', 0)` 这种**调用里的默认参数**、
    算术表达式、变量名）**一律不算「阈值常量」** ⇒ 不命中。
    """
    if isinstance(cmp_node, ast.Constant):
        v = cmp_node.value
        if isinstance(v, int) and not isinstance(v, bool):
            return v
        return None
    if isinstance(cmp_node, ast.UnaryOp) and isinstance(cmp_node.op, ast.USub):
        operand = cmp_node.operand
        if isinstance(operand, ast.Constant):
            v = operand.value
            if isinstance(v, int) and not isinstance(v, bool):
                return -v
        return None
    return None


def _is_conservation_form(left: ast.AST) -> bool:
    """左值是否是「**守恒式**」（和式 / 差式）⇒ 不是「等一个事件」。

    🔴 **形态**：`n_played + n_dropped == n_submitted`
    ⇒ 这是**丢句记账守恒不变式**（§60 `_drop_one()` 建立的口径），
    **不是** APP-021 点名的「用 `n_played >= 1` 判定出声」⇒ 不算违规。
    """
    return isinstance(left, (ast.BinOp,))


def find_weak_criteria(code: str) -> Optional[List[str]]:
    """找出「用 `n_played` 与常量 0/1 比较」的代码行（**AST 级**）。

    🔴 **返回 `None` 表示源码无法解析**（不是空列表！）
    ⇒ 调用方据此判定「**闸门自己失效了**」⇒ 必须判 FAIL。
    ⚠️ 旧实现 `except SyntaxError: return []` ⇒ 解析失败被当成「无违规」
    ⇒ 闸门**永远 PASS** ⇒ **假通过**（§62 记录的真实案例）。

    ⚠️ **不要剥注释**：`ast.parse` 本来就不含注释节点；
       手工剥行会**破坏多行字符串**（bytes 字面量）⇒ 解析失败。

    🔴🔴 **§121 实测修正**：比较器常量**只认 comparator 本身**
    （见 `_comparator_int_value`）⇒ 不再把 `-1` 拆成 `1`；
    左值若是**和式**（守恒不变式）⇒ 不命中（见 `_is_conservation_form`）。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    out: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        # 左值里出现字符串常量 'n_played'
        has_np = any(isinstance(n, ast.Constant) and n.value == TARGET_KEY
                     for n in ast.walk(node.left))
        if not has_np:
            continue
        # 🔴 左值是**和式/差式** ⇒ 守恒不变式 ⇒ 不是弱判据
        if _is_conservation_form(node.left):
            continue
        for op, cmp in zip(node.ops, node.comparators):
            if not isinstance(op, VIOLATION_OPS):
                continue
            val = _comparator_int_value(cmp)
            if val is not None and val in VIOLATION_CONSTS:
                out.append('L%d: %s' % (node.lineno, ast.unparse(node)))
                break
    return out


def scan_file(path: str, tracked: Optional[bool] = None) -> ScanReport:
    """扫描单个文件。"""
    if tracked is None:
        tracked = is_tracked(path)
    rep = ScanReport(path, tracked=tracked)
    try:
        code = open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        rep.parse_failed = True
        rep.parse_error = '读取失败: %r' % (e,)
        return rep
    hits = find_weak_criteria(code)
    if hits is None:
        rep.parse_failed = True
        rep.parse_error = '源码无法解析（SyntaxError）⇒ 闸门失效'
        return rep
    rep.violations = hits
    return rep


def scan_dir(root: str, pattern: str = '.py') -> List[ScanReport]:
    """扫描一个目录下的所有 `.py`（**按文件名排序** ⇒ 报告稳定）。"""
    out: List[ScanReport] = []
    if not os.path.isdir(root):
        return out
    for fn in sorted(os.listdir(root)):
        if not fn.endswith(pattern):
            continue
        out.append(scan_file(os.path.join(root, fn)))
    return out


def is_tracked(rel_or_abs: str) -> bool:
    """该文件是否已被 git 跟踪（**未跟踪** ⇒ 记 skipped，不判 FAIL）。"""
    try:
        r = subprocess.run(['git', 'ls-files', '--error-unmatch', rel_or_abs],
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        return r.returncode == 0
    except Exception:
        return False


def summarize(reports: List[ScanReport]) -> Dict[str, object]:
    """把扫描结果汇总成可写进证据文件的字典。"""
    violations = []
    parse_fail_tracked = []
    skipped = []
    for rep in reports:
        if rep.parse_failed:
            if rep.tracked:
                parse_fail_tracked.append('%s（已跟踪 ⇒ 闸门失效）'
                                          % rep.name)
            else:
                skipped.append('%s（未跟踪历史遗留）: %s'
                               % (rep.name, rep.parse_error[:60]))
            continue
        for v in rep.violations:
            violations.append('%s: %s' % (rep.name, v))
    return dict(
        n_scanned=len(reports),
        n_violations=len(violations),
        violations=violations,
        parse_fail_tracked=parse_fail_tracked,
        skipped=skipped,
        # 🔴 闸门是否**自身失效**（已跟踪文件解析失败）⇒ 必须 FAIL
        gate_valid=not parse_fail_tracked,
    )


if __name__ == '__main__':
    import json
    import sys
    roots = sys.argv[1:] or ['results/app']
    all_reps: List[ScanReport] = []
    for rt in roots:
        all_reps.extend(scan_dir(rt))
    rep = summarize(all_reps)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    sys.exit(0 if (rep['n_violations'] == 0 and rep['gate_valid']) else 1)
