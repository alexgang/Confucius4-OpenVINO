# -*- coding: utf-8 -*-
"""APP-028 —— **闸门自身可信度**（app103 的补充：反证组 + 假通过修复）。

🔴🔴 纪律（§36 / §62 / MEMORY §六）：
  **闸门自身的假通过比缺陷更危险** ⇒ 必须有**反证组**：
  故意写错 ⇒ 判据**必须 FAIL**；若仍 PASS ⇒ 判据本身是坏的。

🔴🔴 本脚本**不 import 被测模块**（`tts_service.py` / `tts_worker.py`
   顶部 import numpy / sounddevice ⇒ import 阶段就可能 abort）
   ⇒ 全部用 `ast` 抽源码 + `exec` 到独立命名空间。

## 本脚本的三组判据

### D 组（REAL，源码结构 —— 修 app103 的 A6 假通过）
- D1 `FALLBACK_ORDER` 能被**真正**解析出来（`AnnAssign` + `Assign` 都认）
      ⇒ app103 的 A6 用的是「只认 `Assign`」的旧写法 ⇒ 对
        `FALLBACK_ORDER: Dict[str, List[str]] = {...}`（**AnnAssign**）
        解析失败 ⇒ 异常被 `except` 吞掉 ⇒ `asr_npu/mt_npu` 保持 `False`
        ⇒ **判据永远 PASS（假通过）**。
- D2 「NPU 独占给 TTS」：ASR / MT 的**回退链**里**没有** NPU
      ⇒ 本条是**真判据**（解析成功才判）；若源码里真含 NPU ⇒ FAIL。
- D3 `DEFAULT_DEVICES` 里只有 TTS 用 NPU。

### E 组（🔴 反证组 —— 故意写错 ⇒ 判据必须 FAIL）
- E1 往「ASR 回退链」里塞 NPU ⇒ D2 判据必须 FAIL
      （证：不是「解析失败 ⇒ 默认 False ⇒ PASS」）
- E2 往「MT 回退链」里塞 NPU ⇒ D2 判据必须 FAIL
- E3 把 `DEFAULT_DEVICES` 的 ASR 改成 NPU ⇒ D3 判据必须 FAIL
- E4 把 `FALLBACK_ORDER` 换成**非字典**（列表）⇒ D1 判据必须 FAIL
      （证：解析失败**必须**被当成 FAIL，而不是「没 NPU ⇒ PASS」）
- E5 给 `AudioQueue` 加回**有界截断**（写满丢弃）⇒ B3/C3 判据必须 FAIL
- E6 给 `_update_backlog` 加回**丢句分支**（下发 cancel）⇒ B8 判据必须 FAIL
- E7 让 `_emit_synth_state` 重新用 `min(3.0, ...)` 截断 ⇒ B7 判据必须 FAIL

### F 组（REAL —— app103 缺口补齐）
- F1 `AudioQueue.write` 是**追加**语义：写 10× 容量后 `n_written` 增量
      **等于**写入总量（真·无界，行为级）
- F2 队列**保序**：多句多块写入 ⇒ 读出顺序 == 写入顺序
- F3 队列空 ⇒ `read()` 返回空（播放回调补静音 + 计欠载）
- F4 `peak_lag_s` 保留峰值（供 APP-028「队列峰值（秒 / MB）」）
- F5 `lag_s()` == 队列剩余样本 / sr
- F6 **无界队列不会因 `capacity` 名义值而丢样本**
      （`capacity=sr*3` 只是遥测名义值 ⇒ 写 100× 也不截断）

用法：
  python results/app/app105_app028_gate_selftest.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
WRK = os.path.join(ROOT, 'live_caption', 'tts_worker.py')
SVC = os.path.join(ROOT, 'live_caption', 'tts_service.py')
DEV = os.path.join(ROOT, 'live_caption', 'device_config.py')
APP = os.path.join(ROOT, 'live_caption', 'live_caption_app.py')
EVID = os.path.join(HERE, 'app105_app028_gate_selftest_evidence.json')

N_PASS = 0
N_FAIL = 0
FAILURES = []
EVIDENCE = {}


def check(name, cond, detail='', group='REAL'):
    global N_PASS, N_FAIL
    if cond:
        N_PASS += 1
        print('  [PASS] %s' % name)
    else:
        N_FAIL += 1
        FAILURES.append({'group': group, 'name': name, 'detail': detail})
        print('  [FAIL] %s  %s' % (name, detail))
    return bool(cond)


def src_of(path):
    with io.open(path, encoding='utf-8') as f:
        return f.read()


def find_class(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def find_func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return n
    return None


def seg_of(src, node):
    if node is None:
        return ''
    try:
        return ast.get_source_segment(src, node) or ''
    except Exception:
        return ''


def module_assign(tree, name):
    """🔴🔴 取**模块级**赋值的节点（`Assign` 与 `AnnAssign` **都**认）。

    🔴 教训：`DEFAULT_DEVICES: Dict[str, str] = {...}` 是 **AnnAssign**
       ⇒ 只认 `Assign` 就取不到 ⇒ 判据「取不到 ⇒ 保持默认 ⇒ PASS」
       ⇒ **假通过**。
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return n
        elif isinstance(n, ast.AnnAssign):
            if isinstance(n.target, ast.Name) and n.target.id == name:
                return n
    return None


def literal_of(node):
    """取字面量值；**失败必须抛异常**（不许静默吞）。"""
    if node is None:
        raise ValueError('节点不存在')
    return ast.literal_eval(node.value)


# ══════════════════════════════════════════════════════════════════════
# 判据函数（**接受源码文本**作为入参 ⇒ 反证组可喂「故意写错的源码」）
# ══════════════════════════════════════════════════════════════════════


def judge_npu_exclusive(dev_src_text):
    """判「NPU 独占给 TTS」。

    返回 (ok: bool, detail: str)。

    🔴🔴 **解析失败 ⇒ ok=False**（不是 True！）：
       「解析不出来」绝不能被当成「没有 NPU ⇒ 通过」。
    """
    try:
        tree = ast.parse(dev_src_text)
    except Exception as e:
        return False, '源码解析失败：%s' % str(e)[:80]
    node = module_assign(tree, 'FALLBACK_ORDER')
    if node is None:
        return False, '找不到 FALLBACK_ORDER'
    try:
        fb = literal_of(node)
    except Exception as e:
        return False, 'FALLBACK_ORDER 解析失败：%s' % str(e)[:80]
    if not isinstance(fb, dict):
        return False, 'FALLBACK_ORDER 不是字典（实际 %s）' % type(fb).__name__
    asr_npu = 'NPU' in (fb.get('asr') or [])
    mt_npu = 'NPU' in (fb.get('mt') or [])
    tts_npu = 'NPU' in (fb.get('tts') or [])
    ok = (not asr_npu) and (not mt_npu) and tts_npu
    return ok, ('asr_has_npu=%s mt_has_npu=%s tts_has_npu=%s'
                % (asr_npu, mt_npu, tts_npu))


def judge_default_npu_only(dev_src_text):
    """判「`DEFAULT_DEVICES` 里只有 TTS 用 NPU」。"""
    try:
        tree = ast.parse(dev_src_text)
    except Exception as e:
        return False, '源码解析失败：%s' % str(e)[:80]
    node = module_assign(tree, 'DEFAULT_DEVICES')
    if node is None:
        return False, '找不到 DEFAULT_DEVICES'
    try:
        dd = literal_of(node)
    except Exception as e:
        return False, 'DEFAULT_DEVICES 解析失败：%s' % str(e)[:80]
    if not isinstance(dd, dict):
        return False, 'DEFAULT_DEVICES 不是字典'
    if dd.get('tts') != 'NPU':
        return False, 'DEFAULT_DEVICES[tts]=%r' % dd.get('tts')
    if dd.get('asr') == 'NPU' or dd.get('mt') == 'NPU':
        return False, 'ASR/MT 也用了 NPU：%r' % dd
    return True, repr(dd)


def judge_no_truncation(wrk_src_text):
    """判「`AudioQueue.write` 不截断 / 不因写满丢弃」。"""
    tree = ast.parse(wrk_src_text)
    node = find_class(tree, 'AudioQueue')
    if node is None:
        return False, '找不到 AudioQueue'
    write_node = None
    for n in ast.walk(node):
        if isinstance(n, ast.FunctionDef) and n.name == 'write':
            write_node = n
    if write_node is None:
        return False, 'AudioQueue 没有 write()'
    wsrc = seg_of(wrk_src_text, write_node)
    # 🔴 只看 **write() 的代码行**（去掉注释行）⇒ 注释里的历史叙述不算
    code = '\n'.join(ln for ln in wsrc.splitlines()
                     if not ln.strip().startswith('#'))
    bad_marks = ('queue.Full', 'BlockingIOError',
                 'del self._chunks[',
                 'self._chunks.pop(',      # 写满丢最旧的块 = 截断
                 'self._chunks = []',
                 'self._chunks.clear()')
    hits = [m for m in bad_marks if m in code]
    return (not hits), ('write() 里出现截断/丢弃语义：%s' % hits if hits else '')


def judge_no_drop_branch(svc_src_text):
    """判「`_update_backlog` 里没有任何丢句分支」。"""
    tree = ast.parse(svc_src_text)
    node = find_func(tree, '_update_backlog')
    if node is None:
        return False, '找不到 _update_backlog'
    src = seg_of(svc_src_text, node)
    bad_kw = ('real_drop' in src
              or "'cmd': 'cancel'" in src
              or '"cmd": "cancel"' in src
              or 'n_dropped +=' in src
              or 'BACKLOG_MAX_S' in src)
    return (not bad_kw), ('_update_backlog 仍含丢句关键字' if bad_kw else '')


def judge_no_min_trunc(wrk_src_text):
    """判「`_emit_synth_state` 不用 `min(3.0, ...)` 截断水位」。"""
    tree = ast.parse(wrk_src_text)
    node = find_func(tree, '_emit_synth_state')
    if node is None:
        return False, '找不到 _emit_synth_state'
    src = seg_of(wrk_src_text, node)
    # 🔴 只看**代码行**（去掉注释行）⇒ 注释里提到 min(3.0) 不算
    code_lines = [ln for ln in src.splitlines()
                  if not ln.strip().startswith('#')]
    code = '\n'.join(code_lines)
    bad = 'min(3.0' in code
    return (not bad), ('_emit_synth_state 代码里仍有 min(3.0, ...) 截断'
                       if bad else '')


# ══════════════════════════════════════════════════════════════════════
# D 组（REAL —— 修 app103 的 A6 假通过）
# ══════════════════════════════════════════════════════════════════════
print('=== D 组（真判据：NPU 独占给 TTS）===')

dev_src = src_of(DEV)
wrk_src = src_of(WRK)
svc_src = src_of(SVC)

d2_ok, d2_detail = judge_npu_exclusive(dev_src)
check('D2 ASR / MT 的回退链里没有 NPU（TTS 独占 NPU）', d2_ok, d2_detail)
EVIDENCE['D2'] = d2_detail

d3_ok, d3_detail = judge_default_npu_only(dev_src)
check('D3 DEFAULT_DEVICES 里只有 TTS 用 NPU', d3_ok, d3_detail)
EVIDENCE['D3'] = d3_detail

# D1：**结构性证明** app103 的 A6 判据对 `AnnAssign` 无效（假通过的根因）
#   🔴 不能依赖「源码当前是否含 NPU」（缺陷修好后就没法证明了）
#   ⇒ 直接**复现 app103 的解析写法**对 `AnnAssign` 节点的行为：
#     app103 只在 `isinstance(n, ast.Assign)` 分支里找 `FALLBACK_ORDER`
#     ⇒ 对 `AnnAssign` 节点**找不到** ⇒ `seg` 为空串
#     ⇒ `ast.literal_eval('')` 抛异常 ⇒ 被 `except` 吞掉
#     ⇒ `asr_npu`/`mt_npu` 保持 `False` ⇒ 判据**永远 PASS**（假通过）。
app103 = os.path.join(HERE, 'app103_app028_no_drop_unbounded_queue.py')
app103_a6_broken = None
app103_a6_detail = ''
if os.path.isfile(app103):
    a103_src = src_of(app103)
    # ① 事实核对：`FALLBACK_ORDER` 在源码里是 AnnAssign（带注解）
    try:
        _t = ast.parse(dev_src)
        _node = module_assign(_t, 'FALLBACK_ORDER')
        _is_ann = isinstance(_node, ast.AnnAssign)
    except Exception as e:
        _is_ann = None
        app103_a6_detail = '解析异常 %s' % str(e)[:60]
    # ② app103 的写法**确实只认 Assign**（源码里找那段循环）
    only_assign = ('isinstance(n, ast.Assign)' in a103_src
                   and "t.id == 'FALLBACK_ORDER'" in a103_src
                   and 'ast.AnnAssign' not in
                   a103_src.split("t.id == 'FALLBACK_ORDER'")[0]
                   .split('dev_tree.body')[-1])
    # ③ 复现：把 app103 的查找逻辑跑一遍，看能不能取到段
    seg_app103 = ''
    try:
        for n in ast.parse(dev_src).body:
            if isinstance(n, ast.Assign):          # ← app103 的写法
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id == 'FALLBACK_ORDER':
                        seg_app103 = seg_of(dev_src, n)
    except Exception:
        pass
    old_asr_npu = False
    try:
        fb = ast.literal_eval(seg_app103.split('=', 1)[1].strip())
        old_asr_npu = 'NPU' in (fb.get('asr') or [])
    except Exception:
        pass
    app103_a6_broken = bool(_is_ann and only_assign
                            and seg_app103 == ''
                            and old_asr_npu is False)
    app103_a6_detail = ('FALLBACK_ORDER 是 AnnAssign=%s；app103 只认 Assign=%s；'
                        'app103 取到的段为空=%s；旧判据的 asr_npu=%s'
                        % (_is_ann, only_assign, seg_app103 == '', old_asr_npu))
else:
    app103_a6_detail = 'app103 不存在'

check('D1 app103 的 A6 判据对 AnnAssign 无效（结构性证明假通过根因）',
      app103_a6_broken is True, app103_a6_detail)
EVIDENCE['D1_app103_a6_false_pass'] = app103_a6_broken
EVIDENCE['D1_detail'] = app103_a6_detail

# ══════════════════════════════════════════════════════════════════════
# E 组（🔴 反证组 —— 故意写错 ⇒ 判据必须 FAIL）
# ══════════════════════════════════════════════════════════════════════
print('=== E 组（反证组：故意写错 ⇒ 判据必须 FAIL）===')

# ── 反证注入工具（**不依赖当前源码的具体写法**）──────────────────────
# 🔴🔴 反证必须对**任何**源码都成立：
#   若用「匹配旧串再替换」，源码一改（缺陷修好了）反证就**静默失效**
#   ⇒ 反证「通过」毫无意义（本轮就踩到过：修好 D2 后 E1/E2 匹配不到）。
#   ⇒ 现在：先用 AST 定位节点，再**重建**一个含缺陷的等价源码。


def inject_npu_into_fallback(src_text, role):
    """重建 `FALLBACK_ORDER`，把 `role` 的链里**加上 NPU**。"""
    tree = ast.parse(src_text)
    node = module_assign(tree, 'FALLBACK_ORDER')
    if node is None:
        return None
    fb = dict(literal_of(node))
    fb[role] = list(fb.get(role) or []) + ['NPU']
    ann = None
    if isinstance(node, ast.AnnAssign) and node.annotation is not None:
        ann = ast.get_source_segment(src_text, node.annotation)
    return ast.unparse(ast.AnnAssign(
        target=ast.Name(id='FALLBACK_ORDER', ctx=ast.Store()),
        value=ast.Dict(
            keys=[ast.Constant(value=k) for k in fb],
            values=[ast.List(elts=[ast.Constant(value=x) for x in v],
                             ctx=ast.Load()) for v in fb.values()]),
        annotation=(ast.parse(ann).body[0] if ann else None),
        simple=1))


def _replace_func_src(src_text, func_name, new_body_src):
    """把 `func_name` 的函数体替换成 `new_body_src`（整函数重建）。"""
    tree = ast.parse(src_text)
    target = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == func_name:
            target = n
    if target is None:
        return None
    new_fn = ast.parse('def %s(self):\n%s'
                       % (func_name,
                          '\n'.join('    ' + ln
                                    for ln in new_body_src.splitlines()))).body[0]
    new_tree = ast.parse(src_text)
    for n in ast.walk(new_tree):
        if isinstance(n, ast.FunctionDef) and n.name == func_name:
            n.body = new_fn.body
            n.args = target.args
            n.decorator_list = target.decorator_list
            n.returns = target.returns
    return ast.unparse(new_tree)


def inject_truncation_into_write(src_text):
    """给 `AudioQueue.write` 加回**有界截断**（写满丢最旧的块）。"""
    tree = ast.parse(src_text)
    node = find_class(tree, 'AudioQueue')
    if node is None:
        return None
    for n in ast.walk(node):
        if isinstance(n, ast.FunctionDef) and n.name == 'write':
            body_src = ('if len(self._chunks) > 3:\n'
                        '    self._chunks.pop(0)\n'
                        'self._chunks.append((arr, jid, int(offset)))')
            return _replace_func_src(src_text, 'write', body_src)
    return None


def inject_drop_branch_into_update_backlog(src_text):
    """给 `_update_backlog` 加回**丢句分支**（下发 cancel）。"""
    body = ('with self.lock:\n'
            '    pending_map = dict(self.pending)\n'
            "if pending_map and 'cancel' in {'cmd': 'cancel'}:\n"
            "    self._send({'cmd': 'cancel', 'id': 0})\n"
            '    self.n_dropped += 1\n'
            'self.backlog_s = 0.0')
    return _replace_func_src(src_text, '_update_backlog', body)


def inject_min_trunc_into_emit(src_text):
    """给 `_emit_synth_state` 加回 `min(3.0, ...)` 截断。"""
    body = ('ring_s = min(3.0, 1.0)\n'
            "emit({'kind': 'synth_state', 'ring_backlog_s': ring_s})")
    return _replace_func_src(src_text, '_emit_synth_state', body)


# E1：往 ASR 回退链塞 NPU
bad1 = inject_npu_into_fallback(dev_src, 'asr')
check('E1a 反证前提：E1 注入成功（AST 重建含 NPU 的 FALLBACK_ORDER）',
      bad1 is not None and "'NPU'" in bad1, '注入失败')
e1_ok, e1_detail = judge_npu_exclusive(bad1 or '')
check('E1 反证：ASR 回退链含 NPU ⇒ 判据必须 FAIL', (not e1_ok), e1_detail)
EVIDENCE['E1'] = e1_detail

# E2：往 MT 回退链塞 NPU
bad2 = inject_npu_into_fallback(dev_src, 'mt')
check('E2a 反证前提：E2 注入成功（AST 重建含 NPU 的 FALLBACK_ORDER）',
      bad2 is not None and "'NPU'" in bad2, '注入失败')
e2_ok, e2_detail = judge_npu_exclusive(bad2 or '')
check('E2 反证：MT 回退链含 NPU ⇒ 判据必须 FAIL', (not e2_ok), e2_detail)
EVIDENCE['E2'] = e2_detail

# E3：把 DEFAULT_DEVICES 的 ASR 改成 NPU（**AST 重建**，不依赖写法）
bad3 = dev_src.replace("'asr': 'GPU.0',", "'asr': 'NPU',", 1)
if bad3 == dev_src:
    _tree3 = ast.parse(dev_src)
    _n3 = module_assign(_tree3, 'DEFAULT_DEVICES')
    _dd3 = dict(literal_of(_n3))
    _dd3['asr'] = 'NPU'
    bad3 = ast.unparse(ast.AnnAssign(
        target=ast.Name(id='DEFAULT_DEVICES', ctx=ast.Store()),
        value=ast.Dict(keys=[ast.Constant(value=k) for k in _dd3],
                       values=[ast.Constant(value=v) for v in _dd3.values()]),
        annotation=ast.parse('Dict[str, str]').body[0], simple=1))
check('E3a 反证前提：E3 的改动真的写进了源码',
      bad3 != dev_src, '注入失败')
e3_ok, e3_detail = judge_default_npu_only(bad3)
check('E3 反证：DEFAULT_DEVICES[asr]=NPU ⇒ 判据必须 FAIL',
      (not e3_ok), e3_detail)
EVIDENCE['E3'] = e3_detail

# E4：把 FALLBACK_ORDER 换成非字典（解析失败必须判 FAIL）
_E4_OLD = "FALLBACK_ORDER: Dict[str, List[str]] = {"
_E4_NEW = "FALLBACK_ORDER: Dict[str, List[str]] = ["
bad4 = dev_src.replace(_E4_OLD, _E4_NEW)
check('E4a 反证前提：E4 的改动真的写进了源码',
      bad4 != dev_src, '未匹配到 %r' % _E4_OLD)
e4_ok, e4_detail = judge_npu_exclusive(bad4)
check('E4 反证：FALLBACK_ORDER 解析失败 ⇒ 判据必须 FAIL（不许默认 PASS）',
      (not e4_ok), e4_detail)
EVIDENCE['E4'] = e4_detail

# E5：给 AudioQueue.write 加回有界截断（**AST 注入**，不依赖写法）
_bad5_src = inject_truncation_into_write(wrk_src)
check('E5a 反证前提：E5 注入成功（AST 重建带截断的 AudioQueue.write）',
      _bad5_src is not None and 'pop' in _bad5_src, '注入失败')
e5_ok, e5_detail = judge_no_truncation(_bad5_src or '')
check('E5 反证：AudioQueue.write 有截断 ⇒ 判据必须 FAIL',
      (not e5_ok), e5_detail)
EVIDENCE['E5'] = e5_detail

# E6：给 _update_backlog 加回丢句分支
#   🔴 用 **AST 重建**整个函数体（不依赖当前源码的具体写法）
bad6 = inject_drop_branch_into_update_backlog(svc_src)
check('E6a 反证前提：E6 注入成功（AST 重建带 cancel 的 _update_backlog）',
      bad6 is not None and "'cancel'" in bad6, '注入失败')
e6_ok, e6_detail = judge_no_drop_branch(bad6 or '')
check('E6 反证：_update_backlog 有丢句分支 ⇒ 判据必须 FAIL',
      (not e6_ok), e6_detail)
EVIDENCE['E6'] = e6_detail

# E7：让 _emit_synth_state 重新用 min(3.0, ...) 截断
bad7 = inject_min_trunc_into_emit(wrk_src)
check('E7a 反证前提：E7 注入成功（AST 重建带 min(3.0, ...) 的 _emit_synth_state）',
      bad7 is not None and 'min(3.0' in bad7, '注入失败')
e7_ok, e7_detail = judge_no_min_trunc(bad7 or '')
check('E7 反证：_emit_synth_state 有 min(3.0, ...) 截断 ⇒ 判据必须 FAIL',
      (not e7_ok), e7_detail)
EVIDENCE['E7'] = e7_detail

# ══════════════════════════════════════════════════════════════════════
# F 组（REAL —— app103 缺口补齐：行为级「真·无界 / 保序 / 欠载 / 峰值」）
# ══════════════════════════════════════════════════════════════════════
print('=== F 组（行为级：真·无界 / 保序 / 欠载 / 峰值）===')

aq_src = ''
tree = ast.parse(wrk_src)
aq_node = find_class(tree, 'AudioQueue')
if aq_node is not None:
    aq_src = seg_of(wrk_src, aq_node)

# 🔴🔴 `exec` 时必须**注入依赖的全局名**：
#   `AudioQueue.__init__` 的默认参数 `capacity: int = SR * 30` 在**类体求值**时
#   就需要模块级 `SR` ⇒ 不注入 ⇒ `NameError: name 'SR' is not defined`
#   ⇒ 判据本身崩溃（**闸门假失败**）。
#   （app055 早已踩过同一个坑：extra={'SR': 22050, ...}）
ns = {'SR': 22050, 'CHUNK_SAMPLES': 1024, 'threading': threading}
try:
    exec(compile(aq_src, '<AudioQueue>', 'exec'), ns)
    AudioQueue = ns['AudioQueue']
except Exception as e:
    AudioQueue = None
    EVIDENCE['F_exec_error'] = repr(e)

check('F0 AudioQueue 类能被 exec 出（依赖齐全）', AudioQueue is not None,
      'exec 失败' if AudioQueue is None else '')

if AudioQueue is not None:
    SR = 22050

    # F1：真·无界（写 100× 容量也不丢）
    q = AudioQueue(capacity=SR * 3, timeout_s=30.0)
    total = 0
    try:
        for i in range(100):
            blk = [0.1] * (SR * 3)      # 3 s 一块，共 300 s
            q.write(blk, jid=i, offset=0)
            total += len(blk)
        f1 = (q.n_written == total)
        f1_detail = 'n_written=%d 期望=%d' % (q.n_written, total)
    except Exception as e:
        f1 = False
        f1_detail = repr(e)
    check('F1 队列真·无界（写 100× 名义容量后 n_written == 写入总量）',
          f1, f1_detail)
    EVIDENCE['F1'] = f1_detail

    # F6：名义 capacity 不参与截断
    q2 = AudioQueue(capacity=1024, timeout_s=30.0)
    try:
        for i in range(10):
            q2.write([0.2] * 4096, jid=i, offset=0)
        f6 = (q2.n_written == 10 * 4096)
        f6_detail = 'capacity=1024 时 n_written=%d 期望=%d' % (
            q2.n_written, 10 * 4096)
    except Exception as e:
        f6 = False
        f6_detail = repr(e)
    check('F6 名义 capacity 不导致截断（capacity=1024 仍写进 40960 样本）',
          f6, f6_detail)
    EVIDENCE['F6'] = f6_detail

    # F2：保序（多句多块 ⇒ 读出顺序 == 写入顺序）
    q3 = AudioQueue(capacity=SR, timeout_s=30.0)
    order_written = []
    for s in range(3):
        for b in range(4):
            val = float(s * 10 + b)
            order_written.append(val)
            try:
                q3.write([val] * 8, jid=s, offset=b * 8)
            except Exception:
                pass
    order_read = []
    try:
        # 🔴 `read()` 返回的是 **numpy 数组** ⇒ `if not got` 判的是
        #   「数组是否含 0 个元素」而不是「是否为空」⇒ 不能靠 `not got` 循环。
        #   ⇒ 改成「按样本数累计，读够总块数就停」。
        _want = len(order_written) * 8
        _got = 0
        while _got < _want:
            _chunk = q3.read(8)
            _n = len(_chunk)
            if _n == 0:
                break
            order_read.append(float(_chunk[0]))
            _got += _n
    except Exception:
        pass
    f2 = (order_read == order_written)
    f2_detail = '写入 %d 块 / 读出 %d 块 / 顺序一致=%s' % (
        len(order_written), len(order_read), order_read == order_written)
    check('F2 队列保序（句间不交叉、句内不乱序）', f2, f2_detail)
    EVIDENCE['F2'] = f2_detail

    # F3：队空 ⇒ read 返回空（播放回调补静音 + 计欠载）
    q4 = AudioQueue(capacity=SR, timeout_s=30.0)
    f3 = (q4.read(1024) == [])
    check('F3 队空时 read() 返回空（由播放回调补静音 + 计欠载）', f3,
          'read()=%r' % (q4.read(1024),))
    EVIDENCE['F3'] = 'empty_read=%s' % f3

    # F5：lag_s == 剩余样本 / sr
    q5 = AudioQueue(capacity=SR, timeout_s=30.0)
    try:
        q5.write([0.1] * SR, jid=0, offset=0)      # 1 s
        f5 = abs(q5.lag_s(SR) - 1.0) < 1e-6
        f5_detail = 'lag_s=%r 期望=1.0' % q5.lag_s(SR)
    except Exception as e:
        f5 = False
        f5_detail = repr(e)
    check('F5 lag_s() == 队列剩余样本 / sr', f5, f5_detail)
    EVIDENCE['F5'] = f5_detail

    # F4：peak_lag_s 保留峰值
    q6 = AudioQueue(capacity=SR, timeout_s=30.0)
    try:
        q6.write([0.1] * (SR * 2), jid=0, offset=0)   # 2 s
        peak = q6.peak_lag_s
        q6.read(SR)                                    # 读走 1 s
        f4 = (abs(peak - 2.0) < 1e-6 and q6.peak_lag_s >= peak)
        f4_detail = 'peak_lag_s=%r（读后仍=%r）' % (peak, q6.peak_lag_s)
    except Exception as e:
        f4 = False
        f4_detail = repr(e)
    check('F4 peak_lag_s 保留峰值（供「队列峰值（秒/MB）」报告）',
          f4, f4_detail)
    EVIDENCE['F4'] = f4_detail

# ══════════════════════════════════════════════════════════════════════
# 汇总
# ══════════════════════════════════════════════════════════════════════
EVIDENCE['summary'] = {'pass': N_PASS, 'fail': N_FAIL,
                        'failures': FAILURES,
                        'ts': time.strftime('%Y-%m-%d %H:%M:%S')}
with io.open(EVID, 'w', encoding='utf-8') as f:
    json.dump(EVIDENCE, f, ensure_ascii=False, indent=2)

print('\n' + '=' * 68)
print('PASS=%d  FAIL=%d' % (N_PASS, N_FAIL))
if FAILURES:
    print('--- 失败明细 ---')
    for g, n, d in [(x['group'], x['name'], x['detail']) for x in FAILURES]:
        print('  [%s] %s  %s' % (g, n, d))
print('证据已写入：%s' % EVID)
print('=' * 68)
sys.exit(1 if N_FAIL else 0)
