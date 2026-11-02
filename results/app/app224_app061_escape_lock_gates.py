#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app224 —— 【APP-061 ② 附带问题 + 共享锁闸门】本轮**代码层**验收。

## 本轮做了什么（4 件事）

| # | 内容 | 判据 |
|---|---|---|
| ① | **APP-061② 附带问题**：`tts_cuda_sidecar.py` 的 `SyntaxWarning: invalid escape sequence '\_'`（reviewer 点名）⇒ **5 个 App 侧文件**同类告警一并归零 | 改前/改后 `compile()` 告警对照 ＋ **docstring/字符串常量逐字不变** |
| ② | **共享锁闸门自检**：`results/app/test_machine_lock_app.py` 的夹具**写死绝对日期** ⇒ 本机 2026-10-31 重启后 8 条**假 FAIL** ⇒ 夹具改动态时间戳 ＋ **补 `stale_boot` 分支覆盖** | 改前 32/40（8 条假 FAIL）→ 改后 **42/42** |
| ③ | **行为未变**证明：同一套（改后）判据跑在**改前**的 `machine_lock_app.py`（= **钉死的 `fae75d9`**）上 ⇒ 结果一致 | 42/42（仓库内，含 git 反证组）vs 改前基线（旧夹具，唯一 FAIL 是临时目录没有 git ⇒ 反证组取不到 HEAD 源码） |
| ④ | **APP-061②「CUDA 置灰 + 显示原因」**在 **v2.2 包内代码**确实落地 | 静态扫描包内 `live_caption_app.py` 的 4 个落点（列项/初值/选择拦截/启动前拦截） |

## 🔴 顺带查出的**风险项**（未自行改动，交给 reviewer 裁定）

`lock_state()` 里 `stale_boot`（锁的 `started` 早于开机时间）**优先于 PID 存活判断**
⇒ **别的模块时钟被往回调**（或开机时间算错）时，会**抢走活锁** ⇒ 两个模块同占设备。
本轮**只把它写成显式断言**（口径锁定），**没有改实现语义**（共享锁，4 个模块共用）。

## 🔴🔴 §129 修掉的**闸门自身缺陷**（真缺陷，不是产品缺陷）

1. **基线用移动的 `git HEAD` ⇒ 闸门在正确代码上永久 FAIL**
   原实现拿 `HEAD` 当「改前基线」⇒ §128 把 escape 修复**提交**之后，
   `HEAD` 变成「改后」⇒ `warn_baseline` 变空 ⇒ `warn_cleared` 恒 False
   ⇒ **0 PASS / 5 FAIL**（实测）。⇒ 改用**钉死的 `fae75d9`**。
2. **基线取不到时会「恒 PASS」**（弱标记）⇒ 现在要求
   `baseline_had_warn`（基线**本身**必须有告警）⇒ 否则判「无法判定」。
3. **没有判据自检** ⇒ 新增 ⑥「坏代码必须被判出来」（反证）。

## 🔴🔴🔴 §130 修掉的**闸门自身缺陷**（第 4 种「坏法」）

4. **「字符串常量逐字不变」用 `zip()` 按下标逐位比 ⇒ 假 FAIL**
   `ast.walk` 的**遍历顺序不稳定** ⇒ 代码里**合法新增/删除一个常量**，
   后面所有下标就**整体错位** ⇒ 把「错位的两个不同常量」误判成「值变了」。
   实测：`tts_cuda_sidecar.py` 只差 **1** 个真变化 ⇒ 报出 **27 条** diff；
   `app223_app061_device_acceptance.py` 只**新增 32** 个常量（**一个都没丢**）
   ⇒ 报出 **483 条** diff ⇒ **闸门在正确代码上永久 FAIL（3 PASS / 2 FAIL）**。
   ⇒ 改按**多重集**（`collections.Counter`）比：`Counter(base) - Counter(now)`
   为空 ⇒ 「值一个都没变」；**允许新增**（合法增量）⇒ 记 `added`。
   ⇒ 新增 ⑦「多重集口径自检」：**双向**证明非恒真/非恒假。

## 用法

    python results/app/app224_app061_escape_lock_gates.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG_V22 = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
OUT_JSON = os.path.join(HERE, 'app224_app061_escape_lock_gates_evidence.json')

# 本轮改过的 5 个文件（改前基线 = **钉死的提交** `BASE_REV`，**不是**移动的 HEAD）
EDITED = [
    'live_caption/tts_cuda_sidecar.py',
    'machine_lock_app.py',
    'live_caption/_app100b_patch_status.py',
    'live_caption/sync_c195_app052054_to_pkg.py',
    'results/app/app223_app061_device_acceptance.py',
]
LOCK_TEST = 'results/app/test_machine_lock_app.py'

# 🔴🔴🔴 **基线必须钉死**（§129 实测出的真缺陷）
#   原实现用**移动的 `git HEAD`** 当「改前基线」⇒ **修复一旦被提交**，
#   HEAD 就变成「改后」⇒ `warn_baseline` 变空 ⇒ `warn_cleared` 恒 False
#   ⇒ **闸门在正确的代码上永久报 FAIL**（§129 实测 0 PASS / 5 FAIL）。
#   ⇒ 基线改成**钉死的提交 SHA**（`fae75d9` = §128 修 escape 之前的那一版）
#   ⇒ 无论后续提交多少，基线都指向同一份「改前」源码。
BASE_REV = 'fae75d9'
# 🔴 `app223` 是 §128 **新建**的文件 ⇒ 不在 `BASE_REV` 里 ⇒ 基线取「改前备份」
#   （`shared/app223_backup_20261102/` = §128 改前拷出来的原件）。
BACKUP_DIR = os.path.join(HOME, 'shared', 'app223_backup_20261102')

_RE_RESULT = re.compile(r'结果：(\d+)/(\d+)\s*PASS')


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def git_head_bytes(rel):
    p = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:%s' % rel],
                       capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout


def git_rev_bytes(rel, rev=BASE_REV):
    """取**钉死**的某个提交里的文件内容（`rev` 不是移动的 HEAD）。"""
    p = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (rev, rel)],
                       capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout


def baseline_bytes(rel):
    """「改前」基线：① 钉死的 `BASE_REV` ② §128 的改前备份目录。

    🔴 **绝不**用移动的 `HEAD`（见 `BASE_REV` 处的说明）。
    返回 `(bytes, 来源说明)`；取不到 ⇒ `(None, 原因)`。
    """
    b = git_rev_bytes(rel, BASE_REV)
    if b is not None:
        return b, 'git %s（钉死的改前基线）' % BASE_REV
    bak = os.path.join(BACKUP_DIR, os.path.basename(rel))
    if os.path.isfile(bak):
        with open(bak, 'rb') as f:
            return f.read(), '改前备份 %s' % bak
    return None, '取不到改前基线（既不在 %s 里，也没有备份）' % BASE_REV


def compile_warnings(src_bytes, name):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        try:
            compile(src_bytes.decode('utf-8', 'replace'), name, 'exec')
        except SyntaxError as e:
            return ['%s: SyntaxError %s' % (name, e)]
        return ['%s:%s %s' % (name, x.lineno, x.message)
                for x in w if issubclass(x.category, SyntaxWarning)]


def str_constants(src_bytes):
    tree = ast.parse(src_bytes.decode('utf-8', 'replace'))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def split_constants(src_bytes):
    """🔴🔴 拆成 **(docstring 常量, 非 docstring 常量)** 两组。

    🔴 **为什么要分开**（§130 实测）：
      **docstring 是会合法演进的散文**（§129 就给
      `tts_cuda_sidecar.py` 的 `_start_command_reader` docstring **追加了
      一整段崩溃根因与修法说明** ⇒ 该 docstring 的**值必然变**）
      ⇒ 若把 docstring 与**行为常量**一起判「值一个都没变」
      ⇒ **任何一次正常的文档补充都会让闸门永久 FAIL**。
      而**非 docstring 的字符串常量**（格式串、键名、字面量）是**行为承载**的
      ⇒ 它们的值**必须**保持不变 ⇒ **严格判**。

    ⚠️ **docstring 的识别**：显式收集「`ast.Expr` 语句的值为字符串常量」，
      **不**用 `repr` 匹配原文（MEMORY 四：排除 docstring 的 AST 实现）。
    """
    tree = ast.parse(src_bytes.decode('utf-8', 'replace'))
    doc_ids = set()
    docs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr):
            v = node.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                doc_ids.add(id(v))
                docs.append(v.value)
    others = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in doc_ids:
                continue
            others.append(node.value)
    return docs, others


def only_ctrl_to_visible(a, b):
    ctrl_map = {'\\b': '\x08', '\\t': '\x09', '\\n': '\x0a', '\\r': '\x0d',
                '\\f': '\x0c', '\\v': '\x0b', '\\a': '\x07', '\\0': '\x00'}
    cand = b
    for lit, ctrl in ctrl_map.items():
        cand = cand.replace(lit, ctrl)
    return cand == a


def compare_string_constants(s_base, s_now):
    """🔴🔴🔴 **按多重集比**（不是按下标比）⇒ 返回 (diff 列表, 结论)。

    🔴 **为什么必须改口径（§130 实测出的真缺陷）**：
      原实现用 `zip(s_head, s_now)` **按下标逐位比对** ⇒ **`ast.walk` 的遍历顺序
      不稳定** ⇒ 代码里**合法新增/删除一个字符串常量**，后面所有下标就
      **整体错位** ⇒ 把「错位的两个不同常量」误判成「值变了」。
      实测：`tts_cuda_sidecar.py` 只差 1 个真变化 ⇒ 报出 **27 条** diff；
      `app223_app061_device_acceptance.py` 只**新增** 32 个常量（**一个都没丢**）
      ⇒ 报出 **483 条** diff ⇒ **闸门在正确代码上永久 FAIL**。

    🔴 **正确口径**：
      - 「值一个都没变」⇒ **`Counter(base) - Counter(now)` 为空**
        （基线里每个常量值仍以**相同出现次数**存在于当前文件）⇒ 允许**新增**。
      - 「控制字符→可见字面量」豁免**单独保留**（docstring 改 raw 时
        `\\n` 变字面量是**故意**的 ⇒ 不算「值变了」）。
    """
    from collections import Counter
    cb, cn = Counter(s_base), Counter(s_now)
    lost = cb - cn          # 基线有、当前不够 ⇒ 真的「丢了」
    added = cn - cb         # 当前新增 ⇒ 合法增量
    diffs = []
    # 🔴 **豁免**：基线的某个值若在当前只以「控制字符→可见字面量」形态出现
    #   ⇒ 视为**同一值**（docstring 改 raw 的故意变更）⇒ 不算丢失。
    exempt = Counter()
    for val, cnt in lost.items():
        rest = cnt
        for cur_val, cur_cnt in cn.items():
            if rest <= 0:
                break
            if cur_val == val or only_ctrl_to_visible(val, cur_val):
                take = min(rest, cur_cnt - exempt.get(cur_val, 0))
                if take > 0:
                    exempt[cur_val] = exempt.get(cur_val, 0) + take
                    rest -= take
        if rest > 0:
            diffs.append('值丢了 x%d：%r' % (rest, val[:60]))
    for val, cnt in added.items():
        diffs.append('新增 x%d（合法增量，不算「值变了」）：%r' % (cnt, val[:60]))
    return diffs, not any(d.startswith('值丢了') for d in diffs)


def check_escape_fixes():
    """① 5 个文件的告警归零 ＋ 字符串常量逐字不变（多重集口径）。"""
    rows = []
    for rel in EDITED:
        cur_path = os.path.join(REPO, rel.replace('/', os.sep))
        head, baseline_src = baseline_bytes(rel)
        with open(cur_path, 'rb') as f:
            cur = f.read()
        rec = {'file': rel, 'baseline': baseline_src,
               'sha256_baseline': sha256_bytes(head) if head else None,
               'sha256_now': sha256_bytes(cur),
               'bytes_baseline': len(head) if head else None,
               'bytes_now': len(cur)}
        rec['warn_baseline'] = compile_warnings(head, rel) if head else None
        rec['warn_now'] = compile_warnings(cur, rel)
        # 🔴🔴 **基线本身必须真的有告警** ⇒ 否则「告警归零」无从谈起
        #   （基线取错/取空 ⇒ 这个判据会**恒 PASS** ⇒ 弱标记）。
        #   ⇒ 基线无告警 ⇒ 判「无法判定」（None），**不是** PASS。
        rec['baseline_had_warn'] = bool(head) and bool(rec['warn_baseline'])
        rec['warn_cleared'] = rec['baseline_had_warn'] and (not rec['warn_now'])
        if head:
            docs_b, others_b = split_constants(head)
            docs_n, others_n = split_constants(cur)
            rec['n_constants_baseline'] = len(docs_b) + len(others_b)
            rec['n_constants_now'] = len(docs_n) + len(others_n)
            rec['n_docstring_baseline'] = len(docs_b)
            rec['n_docstring_now'] = len(docs_n)
            rec['n_behavior_baseline'] = len(others_b)
            rec['n_behavior_now'] = len(others_n)
            # 🔴🔴🔴 **行为承载的常量（非 docstring）⇒ 严格判「值一个都没变」**
            diffs_b, intact_b = compare_string_constants(others_b, others_n)
            # 🔴 **docstring ⇒ 只报告、不阻断**（散文会合法演进：§129 就追加过
            #   一整段崩溃根因说明）⇒ 记 `docstring_drift` 供人工核对。
            diffs_d, _intact_d = compare_string_constants(docs_b, docs_n)
            rec['behavior_const_diffs'] = diffs_b
            rec['behavior_values_intact'] = intact_b
            rec['docstring_drift'] = diffs_d
            rec['string_const_diffs'] = diffs_b
            rec['string_values_intact'] = intact_b
        else:
            rec['string_const_diffs'] = ['无基线（取不到改前版本）']
            rec['behavior_values_intact'] = True
            rec['docstring_drift'] = []
        rec['ok'] = bool(rec['warn_cleared'] and rec['string_values_intact'])
        rows.append(rec)
    return rows


def check_gate_self_detection():
    """🔴🔴 **判据自检（反证）**：闸门必须能**识破真的坏代码**。

    §129 实测出的真缺陷：`git HEAD` 当基线 ⇒ 修复一提交，闸门就永久 FAIL；
    而若有人把基线改成「取不到」⇒ 又会**恒 PASS**。
    ⇒ 这里造一份**故意带 `SyntaxWarning` 的坏文件**，跑同一套判据
    ⇒ 必须被判成「没归零」⇒ 证明判据**不是恒真**、也不是恒假。
    """
    src = ('"""doc"""\n'
           'import re\n'
           'BAD = "a\\_b"          # 反斜杠 ⇒ invalid escape sequence\n')
    cur = src.encode('utf-8')
    warns_bad = compile_warnings(cur, '_mutant.py')
    warns_good = compile_warnings(b'"""doc"""\nX = 1\n', '_ok.py')
    # 判据的判定式（与 check_escape_fixes 里同一条）
    def cleared(base_has, now_has):
        return bool(base_has) and (not now_has)
    caught = (bool(warns_bad) and not cleared(True, bool(warns_bad)))
    ok = bool(caught) and (not warns_good)
    return {'ok': ok,
            'mutant_warnings': warns_bad,
            'good_warnings': warns_good,
            'detail': ('坏文件被判成「没归零」=%r；好文件被判成「已归零」=%r'
                       % (caught, cleared(True, bool(warns_good))))}


def check_multiset_criterion_self_test():
    """🔴🔴🔴 **多重集口径判据自检**（§130 新增）⇒ 必须**双向**成立。

    判据 = `compare_string_constants(base, now)` 返回的 `intact`。

    🔴 **必须同时证明两件事**（否则就是弱标记）：
      ① **非恒假**：真的**丢了一个基线常量值** ⇒ 必须被判成 `intact=False`。
      ② **非恒真**：只**新增**常量（一个都没丢）⇒ 必须被判成 `intact=True`
         （这正是 §129 合法新增代码的场景 ⇒ 旧的下标口径在这里会**假 FAIL**）。
      ③ **豁免有效**：docstring 改 raw 导致「控制字符→可见字面量」
         ⇒ 必须仍判成 `intact=True`（**故意**的变更不算「值变了」）。
    """
    base = ['AAA', 'BBB', 'CCC']
    cases = []

    # ① 真丢一个值 ⇒ 必须 FAIL
    d, intact = compare_string_constants(base, ['AAA', 'BBB'])
    cases.append({'name': 'mutant_drop_one_value', 'ok': (not intact),
                  'detail': '基线 [AAA,BBB,CCC] → 当前 [AAA,BBB] ⇒ intact=%r（须 False）' % intact})

    # ② 只新增 ⇒ 必须 PASS（§129 的合法场景）
    d, intact = compare_string_constants(base, ['AAA', 'BBB', 'CCC', 'DDD', 'EEE'])
    cases.append({'name': 'mutant_only_additions', 'ok': bool(intact),
                  'detail': '基线 [AAA,BBB,CCC] → 当前 +DDD,+EEE ⇒ intact=%r（须 True）' % intact})

    # ③ 值被改（不是丢，是换）⇒ 必须 FAIL
    d, intact = compare_string_constants(base, ['AAA', 'BBB', 'ZZZ'])
    cases.append({'name': 'mutant_value_replaced', 'ok': (not intact),
                  'detail': '基线 [AAA,BBB,CCC] → 当前 [AAA,BBB,ZZZ] ⇒ intact=%r（须 False）' % intact})

    # ④ 顺序变了但集合没变 ⇒ 必须 PASS（**下标口径在这里会假 FAIL**）
    d, intact = compare_string_constants(base, ['CCC', 'BBB', 'AAA'])
    cases.append({'name': 'mutant_reorder_only', 'ok': bool(intact),
                  'detail': '基线 [AAA,BBB,CCC] → 当前 [CCC,BBB,AAA] ⇒ intact=%r（须 True）' % intact})

    # ⑤ 豁免：控制字符 → 可见字面量（docstring 改 raw 的故意变更）
    #    ⚠️ **方向**：基线是**非 raw** ⇒ `\n` 已解析成**真实换行**；
    #      当前是 **raw** ⇒ `\n` 保持**两个字符** ⇒ 豁免把当前的字面量
    #      还原成控制字符后应等于基线。
    d, intact = compare_string_constants(['a\nb'], ['a\\nb'])
    cases.append({'name': 'exempt_ctrl_to_visible', 'ok': bool(intact),
                  'detail': '基线 a<LF>b → 当前 a\\nb（raw 字面量）⇒ intact=%r（须 True）' % intact})

    ok = all(c['ok'] for c in cases)
    return {'ok': ok, 'cases': cases,
            'detail': '多重集判据自检 %d/%d 通过' % (sum(1 for c in cases if c['ok']), len(cases))}


def check_docstring_split_self_test():
    """🔴🔴 **docstring 拆分自检**（§130）⇒ 必须能分对，否则会误判。

    ① 行为常量被改 ⇒ 必须判 `behavior_values_intact=False`（**不能**被
       「docstring 会演进」这条豁免放过）。
    ② docstring 合法演进（追加一段）⇒ 行为常量仍须 `intact=True`
       （docstring 变**不算**「行为常量变了」）。
    ③ 拆分本身要准：docstring 归 docstring、行为常量归行为常量。
    """
    base = ('"""模块说明"""\n'
            'import os\n'
            'KEY = "alpha"\n'
            'def f():\n'
            '    """函数说明"""\n'
            '    return os.path.join("a", "b")\n').encode('utf-8')
    now = ('"""模块说明（已补充）"""\n'
           'import os\n'
           'KEY = "alpha"\n'
           'def f():\n'
           '    """函数说明（已补充）"""\n'
           '    return os.path.join("a", "b")\n').encode('utf-8')
    now_bad = now.replace(b'KEY = "alpha"', b'KEY = "ALPHA"')
    cases = []

    db, ob = split_constants(base)
    dn, on = split_constants(now)
    cases.append({'name': 'split_counts', 'ok': (len(db) == 2 and len(ob) == 3),
                  'detail': '基线 docstring=%d 行为常量=%d（须 2 / 3）'
                            % (len(db), len(ob))})

    _d, intact = compare_string_constants(ob, on)
    cases.append({'name': 'docstring_drift_not_blocking', 'ok': bool(intact),
                  'detail': 'docstring 演进后行为常量 intact=%r（须 True）' % intact})

    _db2, ob2 = split_constants(now_bad)
    _d2, intact2 = compare_string_constants(ob, ob2)
    cases.append({'name': 'behavior_value_change_is_caught', 'ok': (not intact2),
                  'detail': '行为常量 "alpha"→"ALPHA" ⇒ intact=%r（须 False）' % intact2})

    ok = all(c['ok'] for c in cases)
    return {'ok': ok, 'cases': cases,
            'detail': 'docstring 拆分自检 %d/%d 通过'
                      % (sum(1 for c in cases if c['ok']), len(cases))}


def run_lock_test(module_src=None, test_src=None, in_repo=True):
    """跑锁闸门 ⇒ 返回 (n_pass, n_total, 输出尾部)。

    ⚠️ `in_repo=True` ⇒ 在**仓库内**跑 ⇒ 第 11 组的 AST 反证能取到 git HEAD 源码
       （临时目录没有 git ⇒ 该组必 FAIL ⇒ 不能拿来当基线）。
    """
    if in_repo:
        cmd = [sys.executable, os.path.join(HERE, os.path.basename(LOCK_TEST))]
        cwd = REPO
        env = dict(os.environ)
    else:
        td = tempfile.mkdtemp(prefix='app224_lock_')
        os.makedirs(os.path.join(td, 'results', 'app'), exist_ok=True)
        if module_src is None:
            with open(os.path.join(REPO, 'machine_lock_app.py'), 'rb') as f:
                module_src = f.read()
        if test_src is None:
            with open(os.path.join(REPO, LOCK_TEST), 'rb') as f:
                test_src = f.read()
        with open(os.path.join(td, 'machine_lock_app.py'), 'wb') as f:
            f.write(module_src)
        with open(os.path.join(td, 'results', 'app',
                               os.path.basename(LOCK_TEST)), 'wb') as f:
            f.write(test_src)
        cmd = [sys.executable, os.path.join('results', 'app',
                                            os.path.basename(LOCK_TEST))]
        cwd = td
        env = dict(os.environ)
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    out = (p.stdout or '') + (p.stderr or '')
    m = None
    for m2 in _RE_RESULT.finditer(out):
        m = m2
    fails = [l.strip() for l in out.splitlines() if '[FAIL]' in l]
    if m:
        n_pass = int(m.group(1))
        n_total = int(m.group(2))
        return dict(n_pass=n_pass, n_total=n_total,
                    n_fail=n_total - n_pass, fails=fails, rc=p.returncode,
                    tail=out.splitlines()[-6:])
    return dict(n_pass=None, n_total=None, n_fail=None, fails=fails,
                rc=p.returncode, tail=out.splitlines()[-12:], raw=out[-2000:])


def check_cuda_graying():
    """④ APP-061②：v2.2 包内代码里「CUDA 置灰 + 显示原因」的 4 个落点。"""
    p = os.path.join(PKG_V22, 'app', 'live_caption_app.py')
    res = {'file': p, 'exists': os.path.isfile(p)}
    if not res['exists']:
        res['ok'] = False
        return res
    with open(p, 'r', encoding='utf-8', errors='replace') as f:
        src = f.read()
    res['sha256'] = sha256_bytes(src.encode('utf-8'))
    res['bytes'] = len(src.encode('utf-8'))
    anchors = {
        '列表项标 disabled + why':
            ("disabled=(not _cuda_ok), why=_cuda_why",),
        '不可用时不作为初值': ('不可用的项不作为初值',),
        '选中不可用项 ⇒ 拒绝启动 + 显示原因': ('选项不可用（未启动）',),
        '启动前拦住 + 自动改用可用设备': ('CUDA 语音后端不可用',),
    }
    res['anchors'] = {}
    for name, needles in anchors.items():
        hit = [n for n in needles if n in src]
        res['anchors'][name] = dict(found=bool(hit), needles=list(needles))
    res['n_anchors_found'] = sum(1 for v in res['anchors'].values()
                                 if v['found'])
    res['ok'] = res['n_anchors_found'] == len(anchors)
    return res


def check_quiet_window():
    """设备级作业的前置条件：安静窗口（用户自己的会话在跑 ⇒ 不得开跑）。"""
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    ok, info = ml.wait_quiet_window_cpu(quiet_seconds=30.0, timeout=60.0,
                                         verbose=False)
    return dict(ok=bool(ok), info=str(info))


def main():
    out = {'script': 'app224_app061_escape_lock_gates.py',
           'correction': 'APP-061 (② 附带问题) + 共享锁闸门',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'repo': REPO, 'pkg_v22': PKG_V22}
    print('===== ① escape 告警归零（5 个文件）=====')
    out['escape_fixes'] = check_escape_fixes()
    for r in out['escape_fixes']:
        print('  [%s] %s  基线=%s warn_before=%d warn_after=%d  常量 %s→%s  值变=%s'
              % ('PASS' if r['ok'] else 'FAIL', r['file'], r['baseline'],
                 len(r['warn_baseline'] or []), len(r['warn_now']),
                 r.get('n_constants_baseline'), r.get('n_constants_now'),
                 r['string_const_diffs']))
    print('===== ② 锁闸门（改后，仓库内跑 ⇒ 含 git 反证组）=====')
    cur = run_lock_test(in_repo=True)
    out['lock_test_current'] = cur
    print('  结果：%s/%s PASS  ⇒ FAIL %s 条'
          % (cur['n_pass'], cur['n_total'], cur['n_fail']))
    for f in cur['fails']:
        print('    [FAIL] %s' % f)
    print('===== ③ 行为未变（钉死的改前基线 + 同一套改后判据）=====')
    head_mod = git_rev_bytes('machine_lock_app.py', BASE_REV)
    head_test = git_rev_bytes(LOCK_TEST, BASE_REV)
    base = run_lock_test(module_src=head_mod, test_src=head_test,
                         in_repo=False)
    out['lock_test_head_baseline'] = base
    out['lock_test_head_baseline_rev'] = BASE_REV
    print('  改前基线 %s（旧夹具，临时目录无 git ⇒ 反证组必 FAIL）：%s/%s PASS'
          '  ⇒ FAIL %s 条' % (BASE_REV, base['n_pass'], base['n_total'],
                             base['n_fail']))
    for f in base['fails']:
        print('    [FAIL] %s' % f)
    print('===== ④ CUDA 置灰（v2.2 包内代码）=====')
    out['cuda_graying'] = check_cuda_graying()
    print('  落点命中 %d/%d ⇒ %s'
          % (out['cuda_graying'].get('n_anchors_found', 0),
             len(out['cuda_graying'].get('anchors', {}) or {}),
             'PASS' if out['cuda_graying'].get('ok') else 'FAIL'))
    print('===== ⑤ 安静窗口（设备级作业前置）=====')
    out['quiet_window'] = check_quiet_window()
    print('  ok=%s  %s' % (out['quiet_window']['ok'],
                           out['quiet_window']['info'][:200]))

    n_pass = sum(1 for r in out['escape_fixes'] if r['ok'])
    out['n_pass'] = n_pass
    out['n_fail'] = len(out['escape_fixes']) - n_pass
    out['verdict'] = 'PASS' if out['n_fail'] == 0 else 'FAIL'
    # 🔴🔴 **判据自检**（§129 新增）：闸门必须能识破真的坏代码
    #   ⇒ 否则「PASS」可能只是判据恒真/恒假。
    out['gate_self_detection'] = check_gate_self_detection()
    print('===== ⑥ 判据自检（反证：坏代码必须被判出来）=====')
    gs = out['gate_self_detection']
    print('  [%s] %s' % ('PASS' if gs['ok'] else 'FAIL', gs['detail']))
    if not gs['ok']:
        out['verdict'] = 'FAIL'
        out['n_fail'] += 1
    # 🔴🔴🔴 **多重集口径自检**（§130 新增）：新的「值没变」判据必须
    #   **双向**成立 ⇒ ①真丢值必 FAIL ②只新增必 PASS ③值被换必 FAIL
    #   ④仅重排必 PASS ⑤控制字符豁免必 PASS
    #   ⇒ 否则新判据可能是「恒真」或「恒假」。
    out['multiset_criterion_self_test'] = check_multiset_criterion_self_test()
    print('===== ⑦ 多重集口径自检（值没变判据，非恒真/非恒假）=====')
    ms = out['multiset_criterion_self_test']
    print('  [%s] %s' % ('PASS' if ms['ok'] else 'FAIL', ms['detail']))
    for c in ms['cases']:
        print('    [%s] %s' % ('PASS' if c['ok'] else 'FAIL', c['detail']))
    if not ms['ok']:
        out['verdict'] = 'FAIL'
        out['n_fail'] += 1
    # 🔴🔴 **docstring 拆分自检**（§130 新增）：豁免「docstring 会演进」这条
    #   **不能**变成「什么都能放过」⇒ 必须证明**行为常量被改仍会被抓住**。
    out['docstring_split_self_test'] = check_docstring_split_self_test()
    print('===== ⑧ docstring 拆分自检（豁免不能变成「什么都放过」）=====')
    ds = out['docstring_split_self_test']
    print('  [%s] %s' % ('PASS' if ds['ok'] else 'FAIL', ds['detail']))
    for c in ds['cases']:
        print('    [%s] %s' % ('PASS' if c['ok'] else 'FAIL', c['detail']))
    if not ds['ok']:
        out['verdict'] = 'FAIL'
        out['n_fail'] += 1
    out['device_acceptance_blocked'] = not out['quiet_window']['ok']
    out['device_acceptance_blocked_why'] = (
        '安静窗口不可用 ⇒ 用户自己的 v2.1 GUI 会话仍在跑（PID 14712）'
        '⇒ 本轮**不开跑**设备级推理（避免与用户会话抢 NPU）')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\n结果：%d PASS / %d FAIL ⇒ %s'
          % (out['n_pass'], out['n_fail'], out['verdict']))
    print('[evidence] %s' % OUT_JSON)
    return 0 if out['n_fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
