#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-061 ③ 判据：**卡顿**相关改动的**代码层**验收。

覆盖 reviewer APP-061③ 的 (a)(b)(c)(d)：

- **(a) 遥测**：把 underflow 拆成 `uf_in_sentence`（句内 = 听得见的断音）
  与 `uf_idle`（句间空闲 = 首块前空等），并换算成**欠载总时长（ms）**；
  GUI 会话日志**每 30 s** 打一行
  `asr_rtf / asr_backlog_s / mt_lat_p50 / tts_synth_rtf / uf_in_sentence_ms`。
- **(b) 预缓冲**：不是首块一到就开播；已缓冲音频 ≥ 句长 ×(1 − 1/(r·speed))
  才开播；`r·speed ≤ 1` 时退化为首块即播。
- **(c) 倍速封顶**：`speed ≤ 1/r_recent`（用户定的 1.30× 上限不变）。
- **(d) NPU 共用**：MT/ASR 与 TTS 同在 NPU ⇒ 黄色提示「语音可能卡顿」
  （**只提示、不禁止** —— D4 待用户/reviewer 决定）。

🔴🔴 **判据纪律（本项目铁律）**：
  1. **判据 PASS ≠ 判据正确** ⇒ 每条关键判据都配**反证**
     （把缺陷重新注入变异体 ⇒ 判据必须 FAIL）⇒ 判据非恒真。
  2. **反证基线必须是「当前被测对象」** ⇒ 用**同一份源码**做定点变异。
  3. **判据三态**：True / False / **None（无法判定）** ⇒ None 不记 FAIL。
  4. **不 import 被测模块**（顶层 numpy/torch/openvino ⇒ import 阶段 abort）
     ⇒ 用 `ast` 抽函数源码 + `exec` 到**独立命名空间**做行为观测。

用法：
    python app220_app061_stutter.py --target live_caption \
        --out results/app/app220_app061_stutter_evidence.json
    python app220_app061_stutter.py --pkg "C:\\...\\Confucius4_LiveCaption_v2.2\\app"
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

PASSES = []
FAILS = []
NONE_ = []


def check(name, cond, detail='', group=''):
    """🔴 三态登记。"""
    cond = True if cond is True else (False if cond is False else None)
    rec = {'name': name, 'group': group, 'detail': detail,
           'result': {True: 'PASS', False: 'FAIL', None: 'NONE'}[cond]}
    (PASSES if cond is True else FAILS if cond is False else NONE_).append(rec)
    print('  [%s] %s %s' % (rec['result'], name, ('- ' + detail) if detail else ''))
    return cond


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ── AST 小工具 ────────────────────────────────────────────────

def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _src_of(src, node):
    try:
        return ast.get_source_segment(src, node) or ''
    except Exception:
        return ''


def _user_strings(src: str):
    """🔴 用户可见字符串常量（**排除 docstring**）⇒ 注释不参与判定。"""
    tree = ast.parse(src)
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            body = getattr(n, 'body', None) or []
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if id(n) not in docs:
                out.append(n.value)
    return out


def _exec_methods(src: str, names):
    """🔴 把指定方法（`self` 之外的函数体）抽出来 `exec` 到独立命名空间。

    🔴 **为什么不用 import**：被测模块顶层 `import numpy/torch/openvino`
      ⇒ import 阶段就 abort（而且会起后台线程）。
    """
    tree = ast.parse(src)
    ns = {}
    for name in names:
        node = _fn(tree, name)
        if node is None:
            return None, 'method not found: %s' % name
        mod = ast.Module(body=[node], type_ignores=[])
        try:
            ast.fix_missing_locations(mod)
            code = compile(mod, '<extract:%s>' % name, 'exec')
        except Exception as e:
            return None, 'compile failed: %r' % (e,)
        try:
            exec(code, ns)
        except Exception as e:
            return None, 'exec failed: %r' % (e,)
    return ns, ''


class _FakeWorker:
    """🔴 行为探针用的**最小替身**（只要被抽出的方法用到的东西）。"""

    def __init__(self, rtf):
        self._rtf_ewma = rtf
        self._estimate_dur_s = lambda text: 4.0
        self.sr = 22050

    _compute_prebuffer_s = None
    _speed_cap_by_rtf = None


def _probe(src: str, rtf, speed):
    """🔴 跑一次行为探针 ⇒ 返回 (prebuffer_s, cap, err)。"""
    ns, err = _exec_methods(src, ('_compute_prebuffer_s', '_speed_cap_by_rtf'))
    if ns is None:
        return None, None, err
    w = _FakeWorker(rtf)
    try:
        pre = ns['_compute_prebuffer_s'](w, '测试句子', speed=speed)
    except TypeError:
        # 旧签名（没有 speed 参数）⇒ 退化调用
        try:
            pre = ns['_compute_prebuffer_s'](w, '测试句子')
        except Exception as e:
            return None, None, repr(e)
    except Exception as e:
        return None, None, repr(e)
    try:
        cap = ns['_speed_cap_by_rtf'](w)
    except Exception as e:
        return pre, None, repr(e)
    return pre, cap, ''


# ──────────────────────────────────────────────────────────────
# 判据
# ──────────────────────────────────────────────────────────────

def run(target_dir, out_path):
    worker_p = os.path.join(target_dir, 'tts_worker.py')
    app_p = os.path.join(target_dir, 'live_caption_app.py')
    svc_p = os.path.join(target_dir, 'tts_service.py')
    for p in (worker_p, app_p, svc_p):
        if not os.path.isfile(p):
            print('缺少文件：%s' % p)
            return 2

    w_src = open(worker_p, encoding='utf-8').read()
    a_src = open(app_p, encoding='utf-8').read()
    s_src = open(svc_p, encoding='utf-8').read()
    w_tree = ast.parse(w_src)
    a_tree = ast.parse(a_src)

    ev = {
        'task': 'APP-061 ③ 卡顿判据（a 遥测 / b 预缓冲 / c 倍速封顶 / d NPU 提示）',
        'target': target_dir,
        'python': sys.executable,
        'files': {os.path.basename(p): {'sha256': sha256_file(p),
                                        'bytes': os.path.getsize(p)}
                  for p in (worker_p, app_p, svc_p)},
    }

    print('\n== 静态判据 ==')

    # ── ③(a)-1：worker 侧 `uf_*` 字段 ─────────────────────────
    fn = _fn(w_tree, '_fill_app027_telemetry')
    fs = _src_of(w_src, fn) if fn is not None else ''
    for key in ('uf_in_sentence', 'uf_in_sentence_ms', 'uf_idle', 'uf_idle_ms',
                'uf_total_ms'):
        check('3a_worker_emits_%s' % key,
              ("tel['%s']" % key) in fs,
              'found=%s' % (("tel['%s']" % key) in fs), group='3a')

    # ── ③(a)-2：tts_service 侧累计 + 暴露 ─────────────────────
    check('3a_service_accumulates_uf_total',
          'uf_in_sentence_ms_total' in s_src and
          'uf_idle_ms_total' in s_src and
          'n_sent_uf_zero' in s_src,
          'accumulators+exposed', group='3a')
    check('3a_service_exposes_stats',
          'uf_in_sentence_ms_total=int(' in s_src,
          'stats() 暴露累计值', group='3a')

    # ── ③(a)-3：app 侧 30 s 遥测行（字段名齐）─────────────────
    fn = _fn(a_tree, '_log_telemetry_30s')
    fs = _src_of(a_src, fn) if fn is not None else ''
    need = ('asr_rtf', 'asr_backlog_s', 'mt_lat_p50', 'tts_synth_rtf',
            'uf_in_sentence_ms')
    miss = [k for k in need if k not in fs]
    check('3a_app_30s_line_fields', not miss,
          'missing=%s' % (miss or '无'), group='3a')
    check('3a_app_30s_interval', ('30.0' in fs),
          '间隔常量 30.0 s', group='3a')
    check('3a_app_calls_30s_in_poll',
          '_log_telemetry_30s()' in _src_of(a_src, _fn(a_tree, '_poll')),
          '_poll 里调用', group='3a')

    # ── ③(b)：预缓冲公式含 speed ──────────────────────────────
    fn = _fn(w_tree, '_compute_prebuffer_s')
    fs = _src_of(w_src, fn) if fn is not None else ''
    check('3b_prebuffer_accepts_speed',
          'speed' in ([a.arg for a in fn.args.args] if fn is not None else []),
          'args=%s' % ([a.arg for a in fn.args.args] if fn is not None else []),
          group='3b')
    check('3b_prebuffer_uses_r_times_speed',
          ('rs' in fs and '* sp' in fs) or ('rtf) * sp' in fs),
          'rs = rtf × speed', group='3b')
    check('3b_prebuffer_degenerates_when_le1',
          'rs <= 1.0' in fs or 'rs <= 1' in fs,
          'r·speed ≤ 1 ⇒ 0.3 s 底线', group='3b')
    # 调用点：真实值要用本句倍率重算
    check('3b_prebuffer_recomputed_with_speed',
          '_compute_prebuffer_s(text, speed=_sp)' in w_src,
          'synth() 里按 _sp 重算', group='3b')

    # ── ③(c)：倍速封顶 ───────────────────────────────────────
    fn = _fn(w_tree, '_speed_cap_by_rtf')
    fs = _src_of(w_src, fn) if fn is not None else ''
    check('3c_cap_helper_exists', fn is not None,
          'found=%s' % (fn is not None), group='3c')
    check('3c_cap_is_one_over_r',
          '1.0 / r' in fs or '1.0/r' in fs,
          'cap = 1/r', group='3c')
    check('3c_cap_respects_user_1_30',
          '1.30' in fs,
          '用户定的 1.30× 上限仍在', group='3c')
    check('3c_cap_applied_in_synth',
          '_speed_cap_by_rtf()' in w_src and
          ('_sp = float(_cap)' in w_src),
          'synth() 里应用封顶', group='3c')
    # 封顶必须**在** `self._last_speed = _sp` 之前（否则下一句拿到的是被封顶前的值）
    ok_order = False
    try:
        i_cap = w_src.index('_sp = float(_cap)')
        i_set = w_src.index('self._last_speed = _sp', i_cap - 400)
        ok_order = i_cap < i_set
    except Exception:
        ok_order = False
    check('3c_cap_before_last_speed_update', ok_order,
          '封顶在 `self._last_speed = _sp` 之前', group='3c')

    # 🔴🔴 **封顶必须对「两条路径」都生效**（本轮实测抓到的真缺陷）
    #   路径①：有 `target_wall`（worker 自己按 lag 定速）
    #   路径②：**没有** `target_wall`（用主进程下发的 `speed`）
    #   ⚠️ GUI 的按句提交**确实有 `target_play_at=None` 的路径**
    #     （`live_caption_app.py` 的 `_seg_target_wall.get(...)` 取不到时）
    #   ⇒ 旧写法（封顶写在 ① 里面）⇒ 路径② **不封顶** ⇒ 漏。
    #   ⇒ 判据：**结构上**封顶语句不能落在任何
    #     「条件里带 `_target_wall` 的 if」的 body 里。
    def _cap_is_conditional_on_targetwall(src, tree):
        """封顶调用是否被**条件依赖 `_target_wall`** 的 if 包住。"""
        fn_syn = _fn(tree, 'synth')
        if fn_syn is None:
            return None
        # 找到封顶调用所在的赋值节点
        cap_nodes = [n for n in ast.walk(fn_syn)
                     if isinstance(n, ast.Assign)
                     and isinstance(n.value, ast.Call)
                     and isinstance(n.value.func, ast.Attribute)
                     and n.value.func.attr == '_speed_cap_by_rtf']
        if not cap_nodes:
            return None
        cap_ids = {id(n) for n in cap_nodes}
        for node in ast.walk(fn_syn):
            if not isinstance(node, ast.If):
                continue
            cond = _src_of(src, node.test)
            if '_target_wall' not in cond:
                continue
            # 封顶调用是否在这个 if 的 body（含嵌套）里
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if id(sub) in cap_ids:
                        return True
        return False

    cap_in_if = _cap_is_conditional_on_targetwall(w_src, w_tree)
    check('3c_cap_applies_to_both_paths', cap_in_if is False,
          ('封顶不在任何「条件依赖 _target_wall」的 if 里 ⇒ 两条路径都生效'
           if cap_in_if is False else
           '🔴 封顶被关在「有 target_wall」分支里 ⇒ 另一条路径不封顶'),
          group='3c')

    # ── ③(d)：NPU 共用提示（**只提示、不禁止**）─────────────────
    fn = _fn(a_tree, '_npu_conflict_note')
    fs = _src_of(a_src, fn) if fn is not None else ''
    check('3d_npu_conflict_helper_exists', fn is not None,
          'found=%s' % (fn is not None), group='3d')
    check('3d_npu_detects_mt_and_asr',
          "'mt'" in fs and "'asr'" in fs and 'NPU' in fs,
          '检测 MT/ASR 与 TTS 同在 NPU', group='3d')
    fn2 = _fn(a_tree, '_fill_tts_strip')
    fs2 = _src_of(a_src, fn2) if fn2 is not None else ''
    check('3d_npu_shown_in_strip_as_warn',
          '_npu_conflict_note()' in fs2 and "level='warn'" in fs2,
          '语音区状态条标黄', group='3d')
    # **不得禁止**（D4 未决）：不允许出现 raise / disable 组合
    check('3d_npu_not_forbidden',
          'raise ' not in fs and 'disabled' not in fs,
          '只提示、不禁止（D4 待决）', group='3d')

    # ──────────────────────────────────────────────────────────
    print('\n== 行为判据 ==')
    # ③(b)：speed 越大 ⇒ 需要的预缓冲越多
    pre_s1, cap_s1, err = _probe(w_src, 1.31, 1.0)
    check('3b_probe_ok', err == '',
          'err=%s' % (err or '无'), group='behaviour')
    pre_s13, cap_s13, err2 = _probe(w_src, 1.31, 1.30)
    check('3b_probe_speed_ok', err2 == '',
          'err=%s' % (err2 or '无'), group='behaviour')
    if pre_s1 is not None and pre_s13 is not None:
        check('3b_speed_increases_prebuffer',
              pre_s13 > pre_s1 + 1e-9,
              'speed=1.0 ⇒ %.3f s；speed=1.30 ⇒ %.3f s'
              % (pre_s1, pre_s13), group='behaviour')
    else:
        check('3b_speed_increases_prebuffer', None,
              '探针无法判定', group='behaviour')

    # ③(c)：r=1.31 ⇒ cap = 1.0（不许加速）；r=0.5 ⇒ cap = 1.30（用户上限）
    if cap_s1 is not None:
        check('3c_cap_no_accel_when_slow',
              abs(cap_s1 - 1.0) < 1e-9,
              'r=1.31 ⇒ cap=%.4f（=1.0 ⇒ 不加速）' % cap_s1, group='behaviour')
    else:
        check('3c_cap_no_accel_when_slow', None, '探针无法判定', group='behaviour')
    _, cap_fast, _ = _probe(w_src, 0.5, 1.0)
    if cap_fast is not None:
        check('3c_cap_capped_by_user_1_30',
              abs(cap_fast - 1.30) < 1e-9,
              'r=0.50 ⇒ cap=%.4f（用户上限 1.30）' % cap_fast, group='behaviour')
    else:
        check('3c_cap_capped_by_user_1_30', None, '探针无法判定', group='behaviour')
    # 没有实测 RTF ⇒ 不封顶
    _, cap_none, _ = _probe(w_src, None, 1.0)
    check('3c_no_rtf_no_cap', cap_none is None,
          '第一句（无实测 RTF）⇒ 不封顶（cap=%s）' % (cap_none,),
          group='behaviour')

    # ──────────────────────────────────────────────────────────
    print('\n== 反证（变异体必须被抓住）==')

    def mutant_caught(name, src_mut, expect_diff):
        """🔴 变异体：改坏源码 ⇒ 判据必须「不再通过」。"""
        pre_m, cap_m, err_m = _probe(src_mut, 1.31, 1.30)
        caught = False
        detail = ''
        if expect_diff == 'prebuffer':
            pre_ref, _, _ = _probe(w_src, 1.31, 1.30)
            caught = (pre_m is not None and pre_ref is not None
                      and abs(pre_m - pre_ref) > 1e-9)
            detail = 'mutant pre=%.3f vs 原 %.3f' % (pre_m or -1, pre_ref or -1)
        elif expect_diff == 'cap':
            _, cap_ref, _ = _probe(w_src, 1.31, 1.0)
            # 🔴 变异体可能把 cap 变成 **None**（= 不封顶）⇒ 必须算「不同」
            if cap_m is None or cap_ref is None:
                caught = (cap_m is None) != (cap_ref is None)
            else:
                caught = abs(cap_m - cap_ref) > 1e-9
            detail = 'mutant cap=%s vs 原 %s' % (cap_m, cap_ref)
        return check(name, caught, detail, group='counterproof')

    # M1：预缓冲公式去掉 speed 因子
    m1 = w_src.replace('rs = float(rtf) * sp', 'rs = float(rtf)')
    check('M1_mutation_applied', m1 != w_src,
          '替换命中=%s' % (m1 != w_src), group='counterproof')
    mutant_caught('M1_prebuffer_without_speed_is_caught', m1, 'prebuffer')

    # M2：去掉倍速封顶（恢复成不封顶）
    m2 = w_src.replace('return float(cap)', 'return None')
    check('M2_mutation_applied', m2 != w_src,
          '替换命中=%s' % (m2 != w_src), group='counterproof')
    mutant_caught('M2_no_speed_cap_is_caught', m2, 'cap')

    # M2b：把封顶**关回**「有 target_wall」分支里（⇒ 另一条路径不封顶）
    #   ⇒ 判据 3c_cap_applies_to_both_paths 必须 FAIL（变异体必须被抓住）
    #   ⚠️ 变异体必须是**合法 Python**（否则 ast.parse 直接炸 ⇒ 测不到判据）
    _mut = None
    _lines = w_src.split('\n')
    try:
        _i = next(k for k, l in enumerate(_lines)
                  if l.strip().startswith('_cap = self._speed_cap_by_rtf()'))
        _j = next(k for k in range(_i, len(_lines))
                  if '_last_speed = _sp' in _lines[k])
        _block = _lines[_i:_j]
        while _block and not _block[-1].strip():
            _block.pop()
        _new = ['        if _target_wall is not None:']
        for l in _block:
            _new.append(('    ' + l) if l.strip() else l)
        _mut = '\n'.join(_lines[:_i] + _new + [''] + _lines[_j:])
        ast.parse(_mut)          # 🔴 变异体必须能解析
    except Exception as e:
        _mut = None
        print('    [warn] M2b 变异体构造失败：%r' % (e,))
    check('M2b_mutation_applied', bool(_mut) and _mut != w_src,
          '变异体构造=%s（合法 Python）' % (bool(_mut) and _mut != w_src),
          group='counterproof')
    if _mut:
        _bad = _cap_is_conditional_on_targetwall(_mut, ast.parse(_mut))
        check('M2b_cap_inside_branch_is_caught', _bad is True,
              '变异体把封顶关回分支内 ⇒ 判据 3c_cap_applies_to_both_paths 会 FAIL',
              group='counterproof')
    else:
        check('M2b_cap_inside_branch_is_caught', None,
              '无法构造变异体', group='counterproof')

    # M3：uf_* 字段被删（静态判据必须挂）
    m3 = w_src.replace("tel['uf_in_sentence']", "tel['xx_in_sentence']")
    fn_m3 = _fn(ast.parse(m3), '_fill_app027_telemetry')
    fs_m3 = _src_of(m3, fn_m3) if fn_m3 is not None else ''
    caught3 = ("tel['uf_in_sentence']" not in fs_m3)
    check('M3_uf_fields_removed_is_caught', caught3,
          '静态判据不再命中', group='counterproof')

    # M4：30 s 遥测行被删（静态判据必须挂）
    #   ⚠️ 用**注释**而不是 `pass` ⇒ `self._log_telemetry_30s()` 整行被注释掉
    #     （`pass` 会变成 `self.pass` ⇒ SyntaxError ⇒ 测不到判据）
    m4 = a_src.replace('self._log_telemetry_30s()', '# mutated: 30s 遥测行被删')
    fn_m4 = _fn(ast.parse(m4), '_poll')
    fs_m4 = _src_of(m4, fn_m4) if fn_m4 is not None else ''
    caught4 = ('_log_telemetry_30s()' not in fs_m4)
    check('M4_30s_line_removed_is_caught', caught4,
          '静态判据不再命中', group='counterproof')

    # M5：NPU 提示改成「禁止」（D4 未决 ⇒ 不许自己决定）
    m5 = a_src.replace("level='warn'", "level='error'")
    fn_m5 = _fn(ast.parse(m5), '_fill_tts_strip')
    fs_m5 = _src_of(m5, fn_m5) if fn_m5 is not None else ''
    caught5 = ("level='warn'" not in fs_m5)
    check('M5_npu_downgraded_to_error_is_caught', caught5,
          '静态判据不再命中', group='counterproof')

    # ── 汇总 ───────────────────────────────────────────────────
    n_pass = len(PASSES)
    n_fail = len(FAILS)
    n_none = len(NONE_)
    verdict = ('PASS' if n_fail == 0 else 'FAIL')
    ev['static_and_behaviour'] = PASSES + FAILS + NONE_
    ev['n_pass'] = n_pass
    ev['n_fail'] = n_fail
    ev['n_none'] = n_none
    ev['verdict'] = verdict
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n== 结果 ==')
    print('  PASS=%d  FAIL=%d  NONE=%d  verdict=%s'
          % (n_pass, n_fail, n_none, verdict))
    print('  证据：%s' % out_path)
    return 0 if verdict == 'PASS' else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', default=os.path.join(REPO, 'live_caption'))
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--out', default=os.path.join(HERE,
                                                  'app220_app061_stutter_evidence.json'))
    a = ap.parse_args()
    target = os.path.join(a.pkg, 'app') if a.pkg else a.target
    return run(target, a.out)


if __name__ == '__main__':
    sys.exit(main())
