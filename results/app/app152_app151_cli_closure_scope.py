# -*- coding: utf-8 -*-
"""app152 — §97：**CLI 闭包变量作用域缺陷**（`UnboundLocalError`）的验收。

🔴 **真缺陷**（run4 真机实测发现，run4 直接死因）：
  `run_cli` 里的嵌套闭包 `_cli_on_audio_span` / `_cli_pump_spk_voices`
  对外层变量 `_spk_pcm_buf` / `_spk_pending_embed` 做了**赋值**
  ⇒ Python 静态判定它们是**本函数的局部变量**
  ⇒ 读取时未绑定 ⇒ `UnboundLocalError`
     - `_cli_pump_spk_voices`：**CLI 启动即崩**（run4 栈顶在 4601 行）
     - `_cli_on_audio_span`：被 `except Exception: pass` **静默吞掉**
       ⇒ PCM 环形缓冲永远为空 ⇒ 音色永远登记不上（APP-039/040 CLI 失效）

🔴 **铁律遵守**：
  - **绝不 `import` 被测模块**（顶层 numpy 会让 import 阶段 abort）
    ⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间
  - **双向反证**：① 修正前原文（git HEAD）**必须 FAIL**
                     ② 当前实文件**必须 PASS**
                     ③ 沙盒注入错误**必须 FAIL**
  - 结论必须引用**结果文件中的原始字段**

用法：
    python results/app/app152_app151_cli_closure_scope.py
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
TARGET = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
EVID = os.path.join(REPO, 'results', 'app',
                    'app152_app151_cli_closure_scope_evidence.json')
GIT_REL = 'live_caption/live_caption_app.py'

# 🔴🔴🔴 §99：`run_cli` 里**闭包与外层约定共享**的状态变量名单。
#   ⇒ 静态判据只针对这批变量（否则会因「同名但互不相干」而误报）。
SHARED_STATE_VARS = frozenset({
    '_spk_pcm_buf',        # PCM 环形缓冲
    '_spk_pending_embed',  # 待取样的 spk 队列
    '_spk_voice_sent',     # 已发出、等 worker 回执的 spk
    '_spk_audio_end',      # 已消费秒数
})


# ═════════════════════════════════════════════════════════════
# 判据 1：**精确**的「读取先于绑定」扫描
#   CPython 语义：函数 G 内若出现对 X 的绑定，G 内所有 X 都是**局部**；
#   若 G 内**第一次读 X** 出现在**第一次绑定 X 之前** ⇒ 读时未赋值
#   ⇒ `UnboundLocalError`（若 X 同时是外层已绑定变量 ⇒ 是**真 bug**，
#      否则只是「先用后赋」的普通局部变量，无害）。
#   ⚠️ 排除：`nonlocal` / `global` 声明；参数名。
# ═════════════════════════════════════════════════════════════
def find_rebound_outer_vars(fn: ast.FunctionDef, outer_bound: set) -> list:
    """🔴🔴🔴 §99 **静态判据纠偏**：真正的缺陷不是「读在绑之前」。

    ## 真实语义（CPython）

    在函数 G 内**给 X 赋值** ⇒ G 内所有 X 都是 **G 的局部变量**
    ⇒ 即使 G 是闭包、外层已经绑定了 X，**G 里的 X 也是新的局部**
    ⇒ 若 G 里**先读** X（读的是那个尚未赋值的局部）⇒ `UnboundLocalError`。

    ⚠️ 早先判据写的是「读在绑之前」⇒ 只覆盖了「读**早于**赋值」这一种顺序。
    ⇒ 而真实源码里常见的是「**先读后赋**」（例如
       `for seg, spk in list(_spk_pending_embed):` 之后才 `_spk_pending_embed = [...]`）
    ⇒ 早先判据**检不出** ⇒ 反证恒 PASS（**判据假通过**）。

    ⇒ 现在：**只要 G 内对 X 有绑定，且 X 也被外层绑定，且 G 没有
       `nonlocal X` 声明** ⇒ 就是「重绑」缺陷候选
       （⇒ 运行时要么 UnboundLocalError，要么**静默写局部副本**）。

    返回：`[{name, bind_line}]`。
    """
    nested_ids = set()
    for c in ast.walk(fn):
        if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)) and c is not fn:
            nested_ids.update(id(x) for x in ast.walk(c))

    binds = {}
    for c in ast.walk(fn):
        if id(c) in nested_ids:
            continue
        if isinstance(c, ast.Assign):
            for t in c.targets:
                if isinstance(t, ast.Name):
                    binds.setdefault(t.id, t.lineno)
        elif isinstance(c, (ast.AugAssign, ast.AnnAssign)):
            if isinstance(c.target, ast.Name):
                binds.setdefault(c.target.id, c.target.lineno)
        elif isinstance(c, (ast.For, ast.AsyncFor)):
            for nm in ast.walk(c.target):
                if isinstance(nm, ast.Name):
                    binds.setdefault(nm.id, nm.lineno)
        elif isinstance(c, ast.withitem) and c.optional_vars is not None:
            for nm in ast.walk(c.optional_vars):
                if isinstance(nm, ast.Name):
                    binds.setdefault(nm.id, nm.lineno)
        elif isinstance(c, ast.NamedExpr):
            if isinstance(c.target, ast.Name):
                binds.setdefault(c.target.id, c.target.lineno)
    declared = set()
    for c in ast.walk(fn):
        if isinstance(c, (ast.Nonlocal, ast.Global)):
            declared.update(c.names)
    reads = {}
    for c in ast.walk(fn):
        if id(c) in nested_ids:
            continue
        if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Load):
            reads.setdefault(c.id, c.lineno)
    out = []
    for name, ln in binds.items():
        if name in declared:
            continue
        if name not in outer_bound:
            continue
        if name not in reads:
            continue          # 只写不读 ⇒ 正常局部变量
        # 🔴🔴🔴 §99 **三次纠偏**：光靠「同名 + 有读」仍会**误报**
        #   （例：`_st` 在 `run_cli` 直属也有一处绑定，与闭包**互不相干**）
        #   ⇒ 只保留**真正的共享状态变量**（闭包与外层**约定**要共用的那批）。
        if name not in SHARED_STATE_VARS:
            continue
        out.append(dict(name=name, bind_line=ln, read_line=reads[name]))
    return out


def find_unbound_reads(fn: ast.FunctionDef) -> list:
    """返回 [{name, read_line, bind_line}]：本函数内「读在绑之前」的变量。"""
    # 收集事件序列（按源码行号排序）
    binds = {}   # name -> 最早绑定行
    reads = {}   # name -> 最早读取行
    for c in ast.walk(fn):
        if isinstance(c, ast.Assign):
            for t in c.targets:
                if isinstance(t, ast.Name):
                    binds.setdefault(t.id, t.lineno)
        elif isinstance(c, (ast.AugAssign, ast.AnnAssign)):
            if isinstance(c.target, ast.Name):
                binds.setdefault(c.target.id, c.target.lineno)
        elif isinstance(c, (ast.For, ast.AsyncFor)):
            for nm in ast.walk(c.target):
                if isinstance(nm, ast.Name):
                    binds.setdefault(nm.id, nm.lineno)
        elif isinstance(c, ast.withitem) and c.optional_vars is not None:
            for nm in ast.walk(c.optional_vars):
                if isinstance(nm, ast.Name):
                    binds.setdefault(nm.id, nm.lineno)
        elif isinstance(c, ast.NamedExpr):
            if isinstance(c.target, ast.Name):
                binds.setdefault(c.target.id, c.target.lineno)
    for c in ast.walk(fn):
        if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Load):
            reads.setdefault(c.id, c.lineno)

    params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
    if fn.args.vararg:
        params.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        params.add(fn.args.kwarg.arg)
    declared = set()
    for c in ast.walk(fn):
        if isinstance(c, (ast.Nonlocal, ast.Global)):
            declared.update(c.names)

    out = []
    for name, rl in reads.items():
        if name in params or name in declared:
            continue
        bl = binds.get(name)
        if bl is not None and rl < bl:
            out.append(dict(name=name, read_line=rl, bind_line=bl))
    return out


def scan_run_cli(src: str) -> list:
    """扫 `run_cli` 及其嵌套闭包：找「**重绑**外层变量却没有 `nonlocal` 声明」。

    🔴🔴🔴 §99：判据语义已从「读在绑之前」改成「**重绑外层变量**」
       （理由见 `find_rebound_outer_vars` 的 docstring）。
    """
    tree = ast.parse(src)
    rc = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'run_cli':
            rc = n
            break
    if rc is None:
        return []

    def outer_bound_of(fn):
        """🔴🔴🔴 §99 **纠偏**：`ast.walk` 会**走进嵌套闭包**
        ⇒ 闭包自己的临时变量（`a`/`pcm`/`seg`…）也被算成「外层绑定」
        ⇒ 误报一堆「重绑」⇒ 判据恒 FAIL。
        ⇒ 现在：**只看 `run_cli` 直属的绑定**（排除嵌套函数内部）。
        """
        nested_ids = set()
        for c in ast.walk(fn):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)) and c is not fn:
                nested_ids.update(id(x) for x in ast.walk(c))
        out = set()
        for c in ast.walk(fn):
            if id(c) in nested_ids:
                continue
            if isinstance(c, ast.Assign):
                for t in c.targets:
                    if isinstance(t, ast.Name):
                        out.add(t.id)
            elif isinstance(c, (ast.AugAssign, ast.AnnAssign)):
                if isinstance(c.target, ast.Name):
                    out.add(c.target.id)
            elif isinstance(c, (ast.For, ast.AsyncFor)):
                for nm in ast.walk(c.target):
                    if isinstance(nm, ast.Name):
                        out.add(nm.id)
            elif isinstance(c, ast.withitem) and c.optional_vars is not None:
                for nm in ast.walk(c.optional_vars):
                    if isinstance(nm, ast.Name):
                        out.add(nm.id)
            elif isinstance(c, ast.NamedExpr):
                if isinstance(c.target, ast.Name):
                    out.add(c.target.id)
        return out

    ob = outer_bound_of(rc)
    bad = []
    for c in ast.walk(rc):
        if isinstance(c, ast.FunctionDef) and c is not rc:
            for u in find_rebound_outer_vars(c, ob):
                bad.append(dict(func=c.name, **u))
    return bad


# ═════════════════════════════════════════════════════════════
# 判据 2：**真实运行**探针
#   🔴 把两个闭包放进**真正的外层函数**里（`nonlocal` 才合法）
#   🔴 假 numpy：只需 `.asarray` / `.concatenate` / 切片 / `.size`
# ═════════════════════════════════════════════════════════════
FAKE_PRELUDE = '''
import threading

class _FakeArr(list):
    @property
    def size(self):
        return len(self)

    def reshape(self, *a):
        return self

    def __getitem__(self, k):
        r = list.__getitem__(self, k)
        if isinstance(k, slice):
            return _FakeArr(r)
        return r


class _FakeNP:
    @staticmethod
    def asarray(x, dtype=None):
        if x is None:
            return _FakeArr()
        try:
            return _FakeArr(list(x))
        except Exception:
            return _FakeArr([0.0] * 160)

    @staticmethod
    def concatenate(arrs):
        out = []
        for a in arrs:
            out.extend(list(a))
        return _FakeArr(out)

np = _FakeNP()
np.float32 = float
np.float64 = float
SR = 16000


class _FakeTts:
    active = True

    def register_spk_voice(self, spk, pcm):
        return True


def _probe_outer():
    _spk_pcm_buf = _FakeArr()
    _spk_pending_embed = []
    _spk_audio_end = [0.0]
    _spk_pcm_lock = threading.Lock()
    _spk_voices = None
    _spk_bridge = None
    tts = _FakeTts()
'''


# 🔴🔴🔴 §99：探针的**模块级**变量。
#   闭包源码里的 `nonlocal X` 在探针里必须改写成 `global X`
#   （否则 `SyntaxError: no binding for nonlocal 'X' found` ⇒ 脚本崩）。
#   ⇒ `global` 指向**模块级** ⇒ 这几个变量必须**提到模块级**
#     （不能只放在 `_probe_outer` 的局部作用域里）。
#   ⚠️ 每个探针运行前必须**重置**（见 `_reset_probe_globals`）。
PROBE_GLOBALS = '''
_spk_pcm_buf = _FakeArr()
_spk_pending_embed = []
_spk_audio_end = [0.0]
_spk_pcm_lock = threading.Lock()
_spk_voices = None
_spk_bridge = None
_spk_voice_sent = set()
tts = _FakeTts()


def _reset_probe_globals():
    global _spk_pcm_buf, _spk_pending_embed, _spk_audio_end
    global _spk_voices, _spk_bridge, _spk_voice_sent, tts
    _spk_pcm_buf = _FakeArr()
    _spk_pending_embed = []
    _spk_audio_end = [0.0]
    _spk_pcm_lock = threading.Lock()
    _spk_voices = None
    _spk_bridge = None
    _spk_voice_sent = set()
    tts = _FakeTts()
'''


def _build_probe(src: str, span_only: bool = False) -> dict:
    """把 `run_cli` 的闭包抽出来，放进 `_probe_outer()` 里执行。"""
    tree = ast.parse(src)
    rc = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'run_cli':
            rc = n
            break
    if rc is None:
        return dict(error='no run_cli')
    want = ('_cli_on_audio_span', '_cli_pump_spk_voices')
    picked = {}
    for c in ast.walk(rc):
        if isinstance(c, ast.FunctionDef) and c.name in want:
            picked[c.name] = c
    if len(picked) != 2:
        return dict(error='missing closures: %r' % list(picked))

    body = []
    if span_only:
        fn = ast.parse(ast.unparse(picked['_cli_on_audio_span'])).body[0]
        body.append(fn)
        call = '_cli_on_audio_span([0.1] * 320, 0.0, 1.5)'
    else:
        fn = ast.parse(ast.unparse(picked['_cli_pump_spk_voices'])).body[0]
        body.append(fn)
        call = '_cli_pump_spk_voices()'

    # 🔴 §99：闭包源码里的 `nonlocal X` 声明**原样保留**
    #   （§99 之前把它改写成 `global` ⇒ 反证时语义被抹平 ⇒ **判据恒 PASS**）。
    #   ⇒ 现在闭包嵌在**外层函数**里 ⇒ `nonlocal` 指向外层的局部 ⇒ 合法。

    pre = ast.parse(FAKE_PRELUDE).body
    # 取出 _probe_outer 的函数体，塞进闭包 + 调用 + return
    outer = None
    for st in pre:
        if isinstance(st, ast.FunctionDef) and st.name == '_probe_outer':
            outer = st
            break
    if outer is None:
        return dict(error='no _probe_outer')
    tail_src = (
        'def _tail_holder():\n'
        '    %s\n'
        '    return dict(outer_buf_len=len(list(_spk_pcm_buf)),'
        ' audio_end=list(_spk_audio_end))\n' % call
    )
    tail_body = ast.parse(tail_src).body[0].body

    # 🔴🔴🔴 §99 **探针重构**：闭包必须**嵌在一个外层函数里**，
    #   且那些共享变量绑定在**外层函数体内** ⇒ 闭包里的 `nonlocal X`
    #   才是**合法且语义正确**的（指向外层函数的局部）。
    #   ⇒ 这样**不需要**把 `nonlocal` 改写成 `global`
    #     ⇒ 反证（删掉 `nonlocal`）时，赋值**真的**退化成局部
    #     ⇒ UnboundLocalError ⇒ **判据能识破**。
    #   ⚠️ `FAKE_PRELUDE` 里的 `_probe_outer` **整个丢弃**
    #     （它自带局部变量声明，但不含 `_spk_voice_sent`）。
    pre = [st for st in pre
           if not (isinstance(st, ast.FunctionDef)
                   and st.name == '_probe_outer')]

    # 外层函数：绑定共享变量 + 嵌入闭包 + 调用 + 读回
    outer_src = (
        'def _probe_outer():\n'
        '    _spk_pcm_buf = _FakeArr()\n'
        '    _spk_pending_embed = []\n'
        '    _spk_audio_end = [0.0]\n'
        '    _spk_pcm_lock = threading.Lock()\n'
        '    _spk_voices = None\n'
        '    _spk_bridge = None\n'
        '    _spk_voice_sent = set()\n'
        '    tts = _FakeTts()\n'
    )
    outer_fn = ast.parse(outer_src).body[0]
    # 嵌入选中的闭包
    outer_fn.body = list(outer_fn.body) + body
    # 调用 + 读回
    outer_fn.body += ast.parse(tail_src).body[0].body

    mod = ast.Module(body=pre + [outer_fn] + [
        ast.parse('def _run():\n    return _probe_outer()').body[0]],
        type_ignores=[])
    ast.fix_missing_locations(mod)

    ns = {}
    try:
        exec(compile(mod, '<probe>', 'exec'), ns)
        r = ns['_run']()
        return dict(error=None, result=r)
    except Exception as e:
        return dict(error='%s: %s' % (type(e).__name__, e), result=None)


def git_head_src() -> str:
    try:
        out = subprocess.run(
            ['git', 'show', 'HEAD:' + GIT_REL],
            cwd=REPO, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=60)
        if out.returncode == 0 and out.stdout:
            return out.stdout
    except Exception:
        pass
    return ''


def main() -> int:
    src = open(TARGET, 'r', encoding='utf-8').read()
    checks = []

    def chk(cid, name, ok, got, want):
        checks.append(dict(id=cid, name=name, ok=bool(ok),
                           got=got, want=want))
        print('  [%s] %-54s ok=%-5s got=%r want=%r'
              % ('PASS' if ok else 'FAIL', name, ok, got, want))

    print('== A 组：当前实文件（修后）==')
    conflicts = scan_run_cli(src)
    chk('A1', 'run_cli 内无「重绑外层变量却没有 nonlocal」的闭包',
        len(conflicts) == 0, conflicts, [])

    has_pump = 'nonlocal _spk_pending_embed' in src
    has_span = 'nonlocal _spk_pcm_buf' in src
    chk('A2', '两个闭包均显式 nonlocal 声明关键变量',
        has_pump and has_span,
        dict(pump=has_pump, span=has_span),
        dict(pump=True, span=True))

    p_pump = _build_probe(src, span_only=False)
    chk('A3', '真实调用 _cli_pump_spk_voices() 不抛 UnboundLocalError',
        p_pump['error'] is None, p_pump['error'], None)

    p_span = _build_probe(src, span_only=True)
    ok_a4 = (p_span['error'] is None and
             isinstance(p_span.get('result'), dict) and
             (p_span['result'].get('outer_buf_len') or 0) > 0)
    chk('A4', '_cli_on_audio_span 写入对**外层作用域**可见（非局部副本）',
        ok_a4, p_span, dict(error=None, outer_buf_len_gt_0=True))

    print('\n== 反证①：修正前源码（去掉本次新增的 nonlocal）必须 FAIL ==')
    # 🔴 **git HEAD 不能当基线**：APP-039/040 的 CLI 接线是**本轮新增且未入库**
    #   ⇒ HEAD 里根本没有这两个闭包 ⇒ 用 HEAD 反证无意义。
    #   ⇒ 正确基线 = **修复前源码**（本次修复只新增了 `nonlocal` 声明）。
    # 🔴🔴🔴 §99 **注入方式纠偏**：源码里现在是
    #   `nonlocal _spk_pending_embed, _spk_voice_sent`（**一行两个**）
    #   ⇒ 早先用「整行文本替换」会**匹配不到**（反证静默失效）
    #   ⇒ 改用 **AST 删除 `Nonlocal` 节点**（与源码形态无关）。
    def drop_nonlocal(src_text: str, names) -> str:
        """🔴 **AST 级**删除 `nonlocal` 声明里的指定名字。

        ⚠️ 早先版本有 bug：在**另一个** tree 上改 `node.names`，
           后面却按「names 为空」去删节点 ⇒ **永远删不掉** ⇒
           反证静默失效（判据恒 PASS）。
        ⇒ 现在：**同一个 tree** 上改 names + 删空声明。
        """
        tree = ast.parse(src_text)
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node
        drop_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Nonlocal):
                keep = [n for n in node.names if n not in names]
                if len(keep) == len(node.names):
                    continue
                if keep:
                    node.names = keep
                else:
                    drop_nodes.append(node)
        for node in drop_nodes:
            p = parent.get(node)
            if p is not None and isinstance(p, ast.FunctionDef):
                p.body = [st for st in p.body if st is not node]
                p.body.insert(0, ast.Pass())
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
        return out

    pre_fix = drop_nonlocal(src, {'_spk_pending_embed', '_spk_voice_sent'})
    pre_fix_differs = (pre_fix != src)
    hc = scan_run_cli(pre_fix)
    hp = _build_probe(pre_fix, span_only=False)
    hs = _build_probe(pre_fix, span_only=True)
    fails = pre_fix_differs and (len(hc) > 0) and \
            (hp['error'] is not None and
             'UnboundLocalError' in str(hp['error']))
    chk('B1', '修正前源码（去 nonlocal）静态+运行时判据均 FAIL',
        fails,
        dict(n_conflicts=len(hc), pump_error=hp['error'],
             span_probe=hs, git_head_has_closures=bool(
                 git_head_src() and '_cli_pump_spk_voices' in git_head_src())),
        'conflicts>0 且 pump 抛 UnboundLocalError')

    print('\n== 反证①b：git HEAD 现状说明（不作为判据）==')
    h = git_head_src()
    print('  git HEAD 含 _cli_pump_spk_voices = %r'
          % (('_cli_pump_spk_voices' in h) if h else None))

    print('\n== 反证②：沙盒注入错误必须 FAIL ==')
    inj_pump = drop_nonlocal(src, {'_spk_pending_embed'})
    ip = _build_probe(inj_pump, span_only=False)
    ic = scan_run_cli(inj_pump)
    ok2 = (ip['error'] is not None and
           'UnboundLocalError' in str(ip['error'])) and len(ic) > 0
    chk('B2', '注入① 删 nonlocal(_spk_pending_embed) ⇒ A1/A3 FAIL',
        ok2, dict(n_conflicts=len(ic), error=ip['error']),
        'conflicts>0 且 error 含 UnboundLocalError')

    inj_span = drop_nonlocal(src, {'_spk_pcm_buf'})
    isp = _build_probe(inj_span, span_only=True)
    outer_ok = (isp.get('result') or {}).get('outer_buf_len')
    ok3 = ((outer_ok or 0) == 0)
    chk('B3', '注入② 删 nonlocal(_spk_pcm_buf) ⇒ A4 FAIL',
        ok3, dict(error=isp['error'],
                  outer_buf_len=(outer_ok or 0)),
        dict(outer_buf_len=0))

    npass = sum(1 for c in checks if c['ok'])
    nfail = len(checks) - npass
    out = dict(
        ts=time.strftime('%Y-%m-%d %H:%M:%S'),
        target=TARGET,
        target_bytes=os.path.getsize(TARGET),
        target_mtime=time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(os.path.getmtime(TARGET))),
        defect='run_cli 闭包 _spk_pcm_buf/_spk_pending_embed 重绑 ⇒ '
               'UnboundLocalError',
        pass_count=npass, fail_count=nfail, total=len(checks),
        checks=checks,
        static_conflicts=conflicts,
        runtime_probe_pump=p_pump,
        runtime_probe_span=p_span,
        git_head_check=dict(has_closures=bool(git_head_src() and "_cli_pump_spk_voices" in git_head_src())),
    )
    with open(EVID, 'w', encoding='utf-8', newline='') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\nSUMMARY: PASS=%d FAIL=%d TOTAL=%d' % (npass, nfail, len(checks)))
    print('证据：%s (%d B)' % (EVID, os.path.getsize(EVID)))
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
