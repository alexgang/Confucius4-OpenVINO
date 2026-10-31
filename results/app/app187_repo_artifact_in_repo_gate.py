#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app187 —— **「STATUS 引用的产物是否都已入库」闸门**（把 §104 的教训变成可执行判据）。

🔴🔴🔴 **为什么必须有这个闸门（真实事故，2026-10-30 §104 与 2026-11-01 §118）**：

  §104 已经因为「commit message 自述『均已普通 push』但**配套证据 JSON 一个都没进去**」
  被迫**补交**过一次。那次的教训被写成了散文，但**没有任何机制阻止它复发**。

  2026-11-01 的 §117 又**复发了一次**，而且规模更大：

  | 产物 | §117 的结论 | 实际入库状态 |
  |---|---|---|
  | `results/app/app186_app051_acceptance_gate.py`（总闸门） | 「已入库」 | ✅ TRACKED |
  | `results/app/app183_app042_formula_evidence.json` | 「已入库」 | ✅ TRACKED |
  | `results/app/app185_app048_gui_layout_pkg_evidence.json` | 「已入库」 | ✅ TRACKED |
  | `results/app/app175_app043_clone_acceptance_evidence.json` | 「子项②的证据」 | ❌ **UNTRACKED** |
  | `results/app/app179_app042_gui_accel_evidence.json` | 「子项③的证据」 | ❌ **UNTRACKED** |
  | `results/app/app181_pythonw_coldstart_v2_evidence.json` | 「子项①的证据」 | ❌ **UNTRACKED** |
  | `results/app/app184_app051_accel_listen_manifest.json` | 「子项⑤的清单」 | ✅ TRACKED |
  | 以及 7 个**生成这些证据的脚本**（app175/177/178/179/180/181/182） | 未提及 | ❌ **UNTRACKED** |

  ⇒ 🔴 **总闸门 `app186` 自己在库，但它校验的 5 个上游证据的「生产者」不在库**
  ⇒ 🔴 **换一台机器 clone 仓库 ⇒ 跑 `app186` ⇒ 找不到证据文件 ⇒ 报 FAIL**
  ⇒ 🔴 **「已交付」在别人机器上不成立** ⇒ 这正是 §104「半交付第 ④ 层」的定义。

  ⇒ **本闸门的作用**：**扫 STATUS_APP.md 里引用的每一个产物路径，逐个核对
  `git ls-files` 是否在册** ⇒ 任何「结论写在 STATUS 里但产物没进库」当场暴露。

判据设计（三条硬性要求）
------------------------
① **只查「仓库内相对路径」** —— STATUS 里大量引用**包外绝对路径**
   （`C:\\Users\\Trekker-PTL\\...`）和**共享目录**（`shared/...`）
   ⇒ 那不是仓库产物，**不在本闸门职责内** ⇒ 明确跳过并计数（不是静默）。
② **只查「看起来像产物」的引用** —— STATUS 里也引用**源码文件**
   （如 `live_caption/tts_engine.py`、`pkg_paths.py`）
   ⇒ 源码也应当在库 ⇒ 一并查；但要**排除纯示意性引用**
   （`…/v1.4` 这种**举例**用的路径、Markdown 表格里的占位）。
③ 🔴 **判据必须能识破「已知有缺陷的旧产物」** ⇒ 提供 `--status <路径>` 参数，
   可对**任意一份 STATUS 文本**跑本闸门 ⇒ **鉴别力测试**只需造一份
   「引用了未入库文件」的 STATUS 副本即可 ⇒ 不依赖真实仓库状态。

🔴 **本脚本不修改任何文件**（只读 `git ls-files` + 读 STATUS）⇒ 可安全反复跑。
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

#: 默认被扫的 STATUS 文本（仓库内相对路径）
DEFAULT_STATUS = os.path.join('status', 'app', 'STATUS_APP.md')

#: 只关心这些目录前缀下的引用（仓库内产物）
REPO_PREFIXES = (
    'results/',
    'live_caption/',
    'status/',
    'shared/',
)

#: 明确排除的文件名（不是产物：闸门/工具自身、归档占位等）
EXCLUDE_NAMES = frozenset((
    'CORRECTIONS_APP.md',      # reviewer 独占写入文件，**永远不会入库**（故意的）
))

#: 示意性引用（文档举例用）—— 目录形式且带省略号或明显占位
PLACEHOLDER_MARKERS = ('...', '…', '<', '>', 'X', '*')


def _run_git(args):
    """跑 git 并返回 stdout 文本（失败时返回空串）。"""
    try:
        p = subprocess.run(
            ['git'] + list(args), cwd=REPO,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except (OSError, ValueError):
        return ''
    if p.returncode != 0:
        return ''
    return p.stdout.decode('utf-8', 'replace')


def tracked_set():
    """仓库内**已入库**的文件集合（相对路径，POSIX 分隔符）。"""
    out = _run_git(['ls-files'])
    return set(x for x in out.split('\n') if x.strip())


def untracked_set():
    """仓库内**已跟踪但有改动**或**完全未跟踪**的文件集合。

    🔴 「有改动的已入库文件」也算**未入库到当前内容** ——
    因为 STATUS 里引用的 SHA256 对应的是**工作区的内容**，
    而别人 clone 拿到的是**HEAD 的内容** ⇒ 两者不一致 ⇒ 一样不可复现。
    """
    out = _run_git(['ls-files', '--modified', '--others', '--exclude-standard'])
    return set(x for x in out.split('\n') if x.strip())


def ignored_set(paths):
    """被 `.gitignore` 命中的那一部分（**按约定**不入库的日志等）。

    🔴 **为什么要单列一档**：本项目**约定** `results/app/*.log` 不入库
    （`.gitignore` 第 19 行 `*.log`）⇒ 判据**不能**把它算成「漏交」
    ⇒ 否则闸门会**恒 FAIL** ⇒ 判据一旦恒 FAIL 就等于没有判据。
    ⇒ 但它**仍然不是可复现的** ⇒ 单列为「约定忽略」档，供 STATUS 记录口径。
    """
    ig = set()
    for p in paths:
        r = subprocess.run(
            ['git', 'check-ignore', '-q', '--', p], cwd=REPO,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if r.returncode == 0:
            ig.add(p)
    return ig


#: 🔴🔴🔴 「写死仓库根」的两种形态（§118 实测的同类根因）
#:   ① 绝对路径写死：  REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
#:   ② 拼 HOME 写死：  REPO = os.path.join(HOME, 'confucius4-openvino')
#: ⇒ 后果：脚本搬到别处（fresh clone / 别人机器）时**仍读原仓库**
#: ⇒ 「在 clone 上验收通过」是**假象** ⇒ 证据不可复现。
#:
#: 🔴🔴 **必须用 AST 而不是正则** —— 正则会命中
#:    ① **docstring 里引用的别人源码**（实测 `live_caption/speaker_assets.py`
#:       的 docstring 正引用 ASR 侧 `REPO = r'...confucius4-openvino'`）
#:    ② 注释里的举例
#:    ⇒ 那是**散文**，不是可执行代码 ⇒ 报出来就是**假阳性**
#:    ⇒ 假阳性会让闸门恒 FAIL ⇒ 闸门一旦恒 FAIL 就等于没有闸门。
#: ⇒ AST 只看**真实的赋值语句**（`Assign` / `AnnAssign`）⇒ 零误伤。
_HARDCODED_REPO_LITERAL = re.compile(r'confucius4-openvino', re.IGNORECASE)


def _is_repo_literal(node):
    """判断一个 AST 节点是否是「写死仓库根」的常量表达式。"""
    try:
        val = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return False
    return isinstance(val, str) and bool(_HARDCODED_REPO_LITERAL.search(val))


def scan_hardcoded_repo(repo_files):
    """扫出**写死仓库根**的脚本（AST 判定，只看真实赋值语句）。

    🔴 排除项：
      * `status/` `docs/` 下的说明文档（是**散文**，不是可执行脚本）；
      * `_*.py` 开头的**一次性写入器**（历史脚本，不参与验收）；
      * docstring / 注释（AST 天然不覆盖 ⇒ 零误伤）。
    """
    hits = []
    for p in repo_files:
        if not p.endswith('.py'):
            continue
        if os.path.basename(p).startswith('_'):
            continue
        if p.startswith(('status/', 'docs/')):
            continue
        fp = os.path.join(REPO, p)
        try:
            with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                src = f.read()
        except OSError:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            targets = []
            value = None
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            if value is None:
                continue
            # ① 直接字符串字面量
            if _is_repo_literal(value):
                pass
            # ② os.path.join(X, 'confucius4-openvino')
            elif (isinstance(value, ast.Call)
                  and isinstance(value.func, ast.Attribute)
                  and value.func.attr == 'join'
                  and value.args
                  and any(_is_repo_literal(a) for a in value.args)):
                pass
            else:
                continue
            for t in targets:
                tname = getattr(t, 'id', None) or getattr(t, 'attr', None) or ''
                if tname and tname.upper() in ('REPO', 'REPO_ROOT', 'REPO_DIR'):
                    hits.append({'file': p, 'line': node.lineno,
                                 'text': src.splitlines()[node.lineno - 1].strip()[:120]})
    return hits


#: 从反引号 / Markdown 链接 / 裸路径里提取「仓库内相对路径」
_PATH_RE = re.compile(
    r'`([A-Za-z0-9_./\\-]+\.(?:py|json|md|txt|log|patch|sh|bat|yaml|yml|csv))`'
)
_LINK_RE = re.compile(r'\]\(([^)\s]+?)\)')
_BARE_RE = re.compile(r'(?<![\w/\\])([A-Za-z0-9_.-]+/[A-Za-z0-9_./\\-]+\.(?:py|json|md|txt|log|patch|sh|bat))')


def extract_candidates(text):
    """从 STATUS 文本里抽出**候选仓库内相对路径**。

    返回 ``(candidates, skipped_abs, skipped_placeholder)``：
      * ``candidates`` —— 归一化后的相对路径集合
      * ``skipped_abs`` —— 因「包外绝对路径」而跳过的数量
      * ``skipped_placeholder`` —— 因「示意性占位」而跳过的数量
    """
    cands = set()
    skipped_abs = 0
    skipped_placeholder = 0

    raw = set()
    for rx in (_PATH_RE, _LINK_RE, _BARE_RE):
        for m in rx.finditer(text):
            raw.add(m.group(1))

    for p in raw:
        # 统一分隔符
        q = p.replace('\\', '/')
        # 包外绝对路径 ⇒ 跳过（不是仓库产物）
        if re.match(r'^[A-Za-z]:/', q) or q.startswith('//'):
            skipped_abs += 1
            continue
        # 示意性占位 ⇒ 跳过
        if any(mk in q for mk in PLACEHOLDER_MARKERS):
            skipped_placeholder += 1
            continue
        # 只关心仓库内产物目录
        if not q.startswith(REPO_PREFIXES):
            continue
        # 去掉前导 `./`
        while q.startswith('./'):
            q = q[2:]
        cands.add(q)

    return cands, skipped_abs, skipped_placeholder


def check_status(status_text, status_label, tracked, dirty):
    """对一份 STATUS 文本做入库完整性核对。"""
    cands, skipped_abs, skipped_placeholder = extract_candidates(status_text)

    missing = []      # 引用了但**完全没入库**（连 HEAD 都没有）
    dirty_refs = []   # 引用了但**工作区内容 ≠ HEAD 内容**（别人 clone 拿不到）
    ignored = []      # 引用了但**按 .gitignore 约定不入库**（如 *.log）
    ok = []

    for p in sorted(cands):
        if os.path.basename(p) in EXCLUDE_NAMES:
            continue
        if p in tracked:
            if p in dirty:
                dirty_refs.append(p)
            else:
                ok.append(p)
        else:
            missing.append(p)

    ignored = sorted(ignored_set(missing))
    # 「约定忽略」不算漏交
    missing = [p for p in missing if p not in set(ignored)]

    # 🔴🔴🔴 追加检查：**写死仓库根**的脚本（§118 实测的同类根因）
    #   ⇒ 这类脚本搬到别处时**仍读原仓库** ⇒ 证据不可复现。
    #   ⚠️ 全仓有**大量历史一次性脚本**带这个写法 ⇒ 若把它们也算进 FAIL
    #      ⇒ 闸门**恒 FAIL** ⇒ 恒 FAIL 的闸门等于没有闸门（§四纪律）。
    #   ⇒ 因此**只对「STATUS 引用的脚本」**判 FAIL；
    #      其余**全量列出**当**存量清单**（供后续逐批清理，不阻断）。
    hardcoded_all = scan_hardcoded_repo(sorted(tracked | dirty))
    cited = set(cands)
    hardcoded_fail = [h for h in hardcoded_all if h['file'] in cited]
    hardcoded_backlog = [h for h in hardcoded_all if h['file'] not in cited]

    return {
        'status': status_label,
        'n_candidates': len(cands),
        'n_tracked': len(ok),
        'n_missing': len(missing),
        'n_dirty': len(dirty_refs),
        'n_ignored_by_convention': len(ignored),
        'n_skipped_abs': skipped_abs,
        'n_skipped_placeholder': skipped_placeholder,
        'n_hardcoded_repo': len(hardcoded_fail),
        'n_hardcoded_repo_backlog': len(hardcoded_backlog),
        'missing': missing,
        'dirty': dirty_refs,
        'ignored_by_convention': ignored,
        'hardcoded_repo': hardcoded_fail,
        'hardcoded_repo_backlog': hardcoded_backlog,
        'ok': ok,
    }


def main():
    ap = argparse.ArgumentParser(description='§118 入库完整性闸门')
    ap.add_argument('--status', default=DEFAULT_STATUS,
                    help='被扫的 STATUS 文本（仓库内相对路径或绝对路径）')
    ap.add_argument('--out', default='', help='证据 JSON 输出路径（默认打印到 stdout）')
    args = ap.parse_args()

    # 读取 STATUS 文本
    sp = args.status
    if not os.path.isabs(sp):
        sp = os.path.join(REPO, sp)
    if not os.path.isfile(sp):
        print('ERROR: STATUS 文本不存在: %s' % sp)
        return 2
    with open(sp, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    tracked = tracked_set()
    dirty = untracked_set()

    res = check_status(text, os.path.basename(sp), tracked, dirty)

    # 🔴 判据：**引用了但没入库** ⇒ FAIL；**引用了但内容与 HEAD 不一致** ⇒ FAIL
    #    **写死仓库根** ⇒ FAIL（§118 实测：这类脚本搬走后会读原仓库 ⇒ 证据不可复现）
    n_fail = res['n_missing'] + res['n_dirty'] + res['n_hardcoded_repo']
    res['n_fail'] = n_fail
    res['n_pass'] = res['n_tracked']
    res['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    res['ts'] = time.strftime('%Y-%m-%d %H:%M:%S')
    res['repo'] = REPO
    res['script'] = os.path.basename(__file__)
    res['purpose'] = ('§104/§118：STATUS 里引用的产物必须已入库（git ls-files 在册）'
                      '且内容与 HEAD 一致 ⇒ 否则「已交付」在别人机器上不成立')

    print('== 入库完整性闸门（STATUS 引用 ⇒ git ls-files 在册）==')
    print('  STATUS          : %s' % res['status'])
    print('  候选路径        : %d' % res['n_candidates'])
    print('  已入库且一致    : %d' % res['n_tracked'])
    print('  ❌ 完全未入库    : %d' % res['n_missing'])
    print('  ❌ 入库但内容有改动: %d' % res['n_dirty'])
    print('  ❌ 写死仓库根的脚本: %d' % res['n_hardcoded_repo'])
    print('  (按 .gitignore 约定不入库: %d)' % res['n_ignored_by_convention'])
    print('  (跳过包外绝对路径 %d / 示意占位 %d)' % (res['n_skipped_abs'],
                                                    res['n_skipped_placeholder']))
    for p in res['missing']:
        print('    MISSING  %s' % p)
    for p in res['dirty']:
        print('    DIRTY    %s' % p)
    for h in res['hardcoded_repo']:
        print('    HARDCODED  %s:%d  %s' % (h['file'], h['line'], h['text']))
    for p in res['ignored_by_convention']:
        print('    IGNORED  %s' % p)
    print('  结论: %s（PASS %d / FAIL %d）' % (res['verdict'], res['n_pass'], res['n_fail']))

    if args.out:
        outp = args.out if os.path.isabs(args.out) else os.path.join(REPO, args.out)
        d = os.path.dirname(outp)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(outp, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print('  证据已落盘: %s' % outp)

    return 0 if res['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
