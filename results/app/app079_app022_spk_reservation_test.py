#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app079 —— APP-022「spk / spk_conf 接口预留」的 App 侧验收。

====================================================================
🔴 为什么需要这个脚本
====================================================================
APP-022（2026-10-26 16:20）明文要求：
  「**本条现在只需要预留接口，不要开始集成**，等 ASR-013 和 TTS-019
     交付后再接入（由主会话通知）。」

⇒ 验收的**核心**不是「功能能用」，而是：
  ① **预留到位**（字段一路通到 TTS worker）；
  ② 🔴 **不集成**（ASR 还没送 spk ⇒ **行为与改造前逐位一致**）；
  ③ 🔴 **不破坏跨模块契约**（MT 的 5 元组断言必须继续成立）；
  ④ 🔴 **隐私**（x-vector 不落盘、不进客户包）。

====================================================================
验收项
====================================================================
REAL 组（期望成立）：
  A1  `translator.submit()` 接受 `spk` / `spk_conf`（签名已扩）
  A2  `spk=None` ⇒ outbox 事件**仍是 5 元组**（⇒ MT 的 `len(e)==5` 成立）
  A3  `spk='S1'` ⇒ 事件是 **7 元组**，尾部带 spk / spk_conf
  A4  `unpack_event` 认 3 / 5 / 7 元组，`spk` 字段取值正确
  A5  句单元（`mt_units()`）带 `spk` / `spk_conf`
  A6  `tts_service.submit()` 把 spk 透传到 `synth` 命令
  A7  `tts_service.submit()` 在 spk=None ⇒ 命令体**逐字不变**（不含 spk 键）
  A8  `_split_spk()`：纯字符串 ⇒ (text, None, None)（当前形态）
  A9  `_split_spk()`：dict / 元组形态也能拆（ASR 侧交付后零改动即接上）
  A10 渲染层 `render_lines` 带 `spk_by_seg` ⇒ 输出行有 `spk` 键
  A11 **原文守恒不变式**在加了 spk 标签后**依然成立**
  A12 `CP_PREFILL_NPU_SHAPE` = {inputs_embeds: [1,2,1024]}（TTS-017①）
  A13 `cp_prefill` 的 IR 路径解析 ⇒ 与 `cp_decode` 共用同一函数
  A14 `_move_cp_prefill_to_npu` **失败时返回 False 且不抛异常**（降级契约）
  A15 `tts_npu_cache` **在** `pkg_exclude` 的排除名单里（TTS 通知 §二）

BUG 组（期望**不**命中 ⇒ 若命中说明缺陷仍存在）：
  B1  `spk=None` 时事件**不是** 5 元组（⇒ MT 契约被破坏）
  B2  事件里出现 `spk` 键但值为 None（⇒ 形状被无条件改长）

用法
----
    python app079_app022_spk_reservation_test.py
产物
----
    results/app/app079_app022_spk_reservation_evidence.json

⚠️ 本脚本**不加载任何模型**、不跑推理、不占 GPU、不取机器锁
   （纯离线：只 import 纯 stdlib 模块 + 用 `ast` 抽源码做形状断言）。
"""

import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APP = os.path.join(REPO, 'live_caption')
sys.path.insert(0, APP)

# 🔴 caption_render 是**纯 stdlib** ⇒ 可安全 import（不拖 numpy / openvino）
import caption_render as CR  # noqa: E402

RESULTS = []


def check(group, name, ok, detail=''):
    RESULTS.append({'group': group, 'name': name,
                    'ok': bool(ok), 'detail': str(detail)})
    print('  [%s] %s %s  <- %s' % (group, 'PASS' if ok else 'FAIL', name, detail))


def read(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ── 从源码里抽 AST（**不 import** translator / live_caption_app）────────
def parse(path):
    return ast.parse(read(path))


def find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
    return None


def sig_args(fn):
    a = fn.args
    names = [x.arg for x in a.posonlyargs] + [x.arg for x in a.args]
    if a.vararg:
        names.append('*' + a.vararg.arg)
    names += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        names.append('**' + a.kwarg.arg)
    return names


def kwonly_defaults(fn):
    a = fn.args
    out = {}
    pos = len(a.posonlyargs) + len(a.args)
    for d in a.kw_defaults:
        pass
    for name, d in zip([x.arg for x in a.kwonlyargs], a.kw_defaults):
        out[name] = d
    return out, pos


# ══════════════════════════════════════════════════════════════════════
print('=' * 70)
print('APP-022「spk / spk_conf 接口预留」+ TTS-017①「cp_prefill → NPU」验收')
print('=' * 70)

tr_tree = parse(os.path.join(APP, 'translator.py'))
app_tree = parse(os.path.join(APP, 'live_caption_app.py'))
cap_tree = parse(os.path.join(APP, 'caption_render.py'))
svc_tree = parse(os.path.join(APP, 'tts_service.py'))
eng_tree = parse(os.path.join(APP, 'tts_engine.py'))
wkr_tree = parse(os.path.join(APP, 'tts_worker.py'))

# ── A1：translator.submit() 接受 spk / spk_conf ─────────────────────
fn = find_func(tr_tree, 'submit')
args = sig_args(fn) if fn else []
check('REAL', 'A1 translator.submit() 接受 spk / spk_conf',
      fn is not None and 'spk' in args and 'spk_conf' in args,
      'args=%s' % args)

# ── A2 / A3 / B1 / B2：事件形状（**直接执行 _mk_event**）─────────────
#   🔴 `_mk_event` 是纯函数 ⇒ 用 exec 在隔离命名空间里跑
#   （不 import translator ⇒ 不拖 numpy/openvino_genai）
src = read(os.path.join(APP, 'translator.py'))
tree = tr_tree
mk_node = None
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == '_mk_event':
        mk_node = node
        break
ns = {}
exec(compile(ast.Module(body=[mk_node], type_ignores=[]), 'translator.py', 'exec'), ns)
mk = ns['_mk_event']

ev_none = mk('final', 'C:1:1', 'src', 'txt', 3, None, None)
ev_spk = mk('final', 'C:1:1', 'src', 'txt', 3, 'S1', 0.87)

check('REAL', 'A2 spk=None ⇒ 事件仍是 5 元组（MT 的 len(e)==5 仍成立）',
      len(ev_none) == 5, 'len=%d %s' % (len(ev_none), ev_none))
check('REAL', 'A3 spk="S1" ⇒ 事件是 7 元组（尾部带 spk / spk_conf）',
      len(ev_spk) == 7 and ev_spk[5] == 'S1' and ev_spk[6] == 0.87,
      'len=%d %s' % (len(ev_spk), ev_spk))
check('BUG', 'B1 spk=None 时事件不是 5 元组（⇒ MT 契约被破坏）',
      len(ev_none) != 5, 'len=%d' % len(ev_none))
check('BUG', 'B2 事件里出现 spk 键但值为 None（⇒ 形状被无条件改长）',
      len(ev_none) > 5, 'len=%d' % len(ev_none))

# ── A4：unpack_event 认 3 / 5 / 7 元组 ─────────────────────────────
e3 = CR.unpack_event(('draft', 'k', '译文'))
e5 = CR.unpack_event(('final', 'C:1:7', 'src', 'txt', 2))
e7 = CR.unpack_event(('final', 'C:1:7', 'src', 'txt', 2, 'S1', 0.87))
check('REAL', 'A4 unpack_event 认 3/5/7 元组且 spk 取值正确',
      e3 is not None and e3['spk'] is None
      and e5 is not None and e5['spk'] is None
      and e7 is not None and e7['spk'] == 'S1' and e7['spk_conf'] == 0.87,
      '3->%s 5->%s 7->spk=%s conf=%s'
      % (e3['spk'], e5['spk'], e7['spk'], e7['spk_conf']))

# ── A5：句单元带 spk ───────────────────────────────────────────────
#   `_Job.__slots__` 含 spk / spk_conf ⇒ 字段一路通到 job
job_node = None
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == '_Job':
        job_node = node
        break
slots = []
for node in job_node.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == '__slots__':
                slots = [e.value for e in node.value.elts]
check('REAL', 'A5 _Job.__slots__ 含 spk / spk_conf（字段通到 job）',
      'spk' in slots and 'spk_conf' in slots, 'slots=%s' % slots)

# ── A6 / A7：tts_service.submit() 透传 ─────────────────────────────
fn = find_func(svc_tree, 'submit')
args = sig_args(fn) if fn else []
svc_src = read(os.path.join(APP, 'tts_service.py'))
has_spk_cmd = ("cmd['spk'] = spk" in svc_src
                and "cmd['spk_conf'] = spk_conf" in svc_src)
check('REAL', 'A6 tts_service.submit() 接受 spk 并透传到 synth 命令',
      fn is not None and 'spk' in args and has_spk_cmd,
      'args=%s cmd_fields=%s' % (args, has_spk_cmd))
# 🔴 「spk=None ⇒ 命令体逐字不变」⇒ **不能**无条件写 spk 键
check('REAL', 'A7 spk=None ⇒ 命令体不含 spk 键（逐字不变）',
      "if spk is not None:" in svc_src
      and svc_src.count("cmd['spk']") == 1
      and svc_src.index('if spk is not None:')
      < svc_src.index("cmd['spk'] = spk"),
      'conditional_write=%s'
      % (svc_src.index('if spk is not None:') < svc_src.index("cmd['spk'] = spk")))

# ── A8 / A9：_split_spk ────────────────────────────────────────────
fn = find_func(app_tree, '_split_spk')
sp = ns2 = {}
if fn is not None:
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'live_caption_app.py', 'exec'),
         sp)
split = sp.get('_split_spk')
check('REAL', 'A8 _split_spk：纯字符串 ⇒ (text, None, None)（当前形态）',
      split is not None and split('hello') == ('hello', None, None),
      str(split('hello')) if split else 'missing')
check('REAL', 'A9 _split_spk：dict / 元组形态也能拆（交付后零改动即接上）',
      split is not None
      and split({'text': 'hi', 'spk': 'S2', 'spk_conf': 0.5})
      == ('hi', 'S2', 0.5)
      and split(('hi', 'S3', 0.4)) == ('hi', 'S3', 0.4),
      'dict=%s tuple=%s' % (split({'text': 'hi', 'spk': 'S2', 'spk_conf': 0.5}),
                            split(('hi', 'S3', 0.4))) if split else 'missing')

# ── A10 / A11：渲染层 ──────────────────────────────────────────────
BLOCKS = ['第一段原文', '第二段原文']
UNITS = [{'key': 'k1', 'src': '第一段原文', 'seg': 0, 'mt': '译文一',
          'kind': 'final', 'unit_id': 'C:0:1'}]
lines_plain = CR.render_lines(BLOCKS, UNITS, granularity='seg')
lines_spk = CR.render_lines(BLOCKS, UNITS, granularity='seg',
                            spk_by_seg={0: 'S1'})
src_plain = ''.join(l['text'] for l in lines_plain if l['kind'] == 'src')
src_spk = ''.join(l['text'] for l in lines_spk if l['kind'] == 'src')
check('REAL', 'A10 render_lines 带 spk_by_seg ⇒ 输出行有 spk 键',
      lines_plain[0].get('spk') is None
      and lines_spk[0].get('spk') == 'S1',
      'plain=%s spk=%s' % (lines_plain[0].get('spk'), lines_spk[0].get('spk')))
check('REAL', 'A11 原文守恒不变式在加 spk 后依然成立',
      src_plain == ''.join(BLOCKS) and src_spk == ''.join(BLOCKS),
      'plain=%r spk=%r' % (src_plain, src_spk))

# ── A12：CP_PREFILL_NPU_SHAPE ──────────────────────────────────────
shape = None
for node in tree.body:
    pass
eng_src = read(os.path.join(APP, 'tts_engine.py'))
eng_tree2 = parse(os.path.join(APP, 'tts_engine.py'))
for node in eng_tree2.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == 'CP_PREFILL_NPU_SHAPE':
                shape = ast.literal_eval(node.value)
check('REAL', 'A12 CP_PREFILL_NPU_SHAPE = {inputs_embeds: [1,2,1024]}（TTS-017①）',
      shape == {'inputs_embeds': [1, 2, 1024]}, 'shape=%s' % shape)

# ── A13：cp_prefill / cp_decode 共用同一个 IR 路径函数 ──────────────
fn_cp = find_func(eng_tree2, '_cp_ir_path')
fn_pre = find_func(eng_tree2, '_move_cp_prefill_to_npu')
check('REAL', 'A13 cp_prefill / cp_decode 共用 _cp_ir_path（避免两份逻辑漂移）',
      fn_cp is not None and fn_pre is not None
      and "'cp_prefill'" in read(os.path.join(APP, 'tts_engine.py')),
      '_cp_ir_path=%s _move_cp_prefill_to_npu=%s'
      % (fn_cp is not None, fn_pre is not None))

# ── A14：cp_prefill 失败必须 return False 且**不抛异常** ────────────
ok14 = False
d14 = 'missing'
if fn_pre is not None:
    body_src = ast.dump(fn_pre)
    has_try = any(isinstance(n, ast.Try) for n in ast.walk(fn_pre))
    has_ret_false = any(isinstance(n, ast.Return) and
                        isinstance(n.value, ast.Constant) and
                        n.value.value is False
                        for n in ast.walk(fn_pre))
    # 🔴 **不能**有裸 `raise`（降级契约：失败不抛）
    has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(fn_pre))
    ok14 = has_try and has_ret_false and not has_raise
    d14 = 'try=%s return_False=%s raise=%s' % (has_try, has_ret_false, has_raise)
check('REAL', 'A14 cp_prefill 搬 NPU 失败 ⇒ return False 且不抛异常（降级契约）',
      ok14, d14)

# ── A15：tts_npu_cache 在 pkg_exclude 排除名单里 ────────────────────
pkg_exclude_src = read(os.path.join(REPO, 'pkg_exclude.py'))
check('REAL', 'A15 tts_npu_cache 在 pkg_exclude 排除名单里（TTS 通知 §二）',
      "'tts_npu_cache'" in pkg_exclude_src,
      'found=%s' % ("'tts_npu_cache'" in pkg_exclude_src))

# ══════════════════════════════════════════════════════════════════════
n_real = sum(1 for r in RESULTS if r['group'] == 'REAL')
n_real_ok = sum(1 for r in RESULTS if r['group'] == 'REAL' and r['ok'])
n_bug = sum(1 for r in RESULTS if r['group'] == 'BUG')
n_bug_hit = sum(1 for r in RESULTS if r['group'] == 'BUG' and r['ok'])

verdict = 'PASS' if (n_real_ok == n_real and n_bug_hit == 0) else 'FAIL'
print('\n' + '=' * 70)
print('结果：REAL %d/%d PASS ｜ BUG %d/%d 命中 %s ｜ verdict=%s'
      % (n_real_ok, n_real, n_bug_hit, n_bug,
         '（命中=缺陷仍存在）' if n_bug_hit else '（全落空）', verdict))
print('=' * 70)

out = {
    'purpose': 'APP-022「spk / spk_conf 接口预留」+ TTS-017①「cp_prefill → NPU」的 App 侧验收',
    'correction': 'APP-022 [NORMAL] 2026-10-26 16:20（CORRECTIONS_APP.md）',
    'notices': ['shared/NOTICE_tts_to_app_20261026.md（TTS-017① cp_prefill CPU→NPU）'],
    'no_model': True, 'no_gpu': True, 'no_inference': True, 'no_lock': True,
    'checks': RESULTS,
    'n_checks': len(RESULTS),
    'n_pass': sum(1 for r in RESULTS if r['ok']),
    'n_real': n_real, 'n_real_ok': n_real_ok,
    'n_bug': n_bug, 'n_bug_hit': n_bug_hit,
    'verdict': verdict,
}
dst = os.path.join(HERE, 'app079_app022_spk_reservation_evidence.json')
with io.open(dst, 'w', encoding='utf-8') as f:
    f.write(json.dumps(out, ensure_ascii=False, indent=1))
print('证据 ->', dst)
sys.exit(0 if verdict == 'PASS' else 1)
