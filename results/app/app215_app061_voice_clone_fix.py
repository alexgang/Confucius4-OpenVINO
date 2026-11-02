#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-061 判据：①②④⑤ 的**代码层**验收（CUDA 无声 / 克隆链路 / 定时采集）。

🔴🔴 **判据纪律（本项目铁律）**：
  1. **判据 PASS ≠ 判据正确** ⇒ 每条判据都配**反证**（把缺陷重新注入
     变异体 ⇒ 判据必须 FAIL）⇒ 判据非恒真。
  2. **反证基线必须是「当前被测对象」** ⇒ 这里用**同一份源码**做定点变异
     （不是拿旧版本当基线）。
  3. **判据三态**：True / False / **None（无法判定）** ⇒ None **不**记 FAIL，
     只在证据里标注「无法判定」。
  4. **不 import 被测模块到主进程** ⇒ 行为观测在**子进程**里做
     （`_app215_probe.py`）⇒ 模块级状态不串。

用法：
    python app215_app061_voice_clone_fix.py --target live_caption --out results/app/app215_app061_voice_clone_evidence.json
    python app215_app061_voice_clone_fix.py --pkg "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v2.1\\app"
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PROBE = os.path.join(HERE, '_app215_probe.py')

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


# ──────────────────────────────────────────────────────────────
# 静态判据（live_caption_app.py）
# ──────────────────────────────────────────────────────────────

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


def _docstring_nodes(tree):
    """🔴 返回**所有 docstring 节点**（Module / FunctionDef / ClassDef 的第一条语句）。"""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            body = getattr(n, 'body', None) or []
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _user_strings(src: str):
    """🔴 返回**用户可见的字符串常量**（**排除 docstring**）⇒ 注释不参与判定。"""
    tree = ast.parse(src)
    docs = _docstring_nodes(tree)
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if id(n) in docs:
                continue
            out.append(n.value)
    return out


def static_checks(app_src: str) -> dict:
    """返回 {判据名: (bool|None, detail)}。"""
    tree = ast.parse(app_src)
    out = {}

    # ── ②a：CUDA 选项**恒列出**且带 `disabled` ───────────────────
    fn = _fn(tree, 'build_tts_options')
    if fn is None:
        out['2a_cuda_option_always_listed'] = (None, '找不到 build_tts_options')
    else:
        has_insert = False
        has_disabled = False
        guarded = False
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr == 'insert' \
                    and n.args and isinstance(n.args[0], ast.Constant) \
                    and n.args[0].value == 0:
                has_insert = True
                # 🔴 **按 AST 关键字判定**（不能用文本匹配 ⇒ 注释里也会出现
                #   `disabled=True` ⇒ 文本匹配会**恒真**）。
                for a in n.args[1:]:
                    if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) \
                            and a.func.id == 'dict':
                        has_disabled = any(kw.arg == 'disabled'
                                           for kw in a.keywords)
            if isinstance(n, ast.If):
                test = _src_of(app_src, n.test)
                body = ''.join(_src_of(app_src, s) for s in n.body)
                if 'out.insert(0, dict(' in body and '_cuda_tts_available' in test:
                    guarded = True
        out['2a_cuda_option_always_listed'] = (
            bool(has_insert and not guarded and has_disabled),
            'insert=%s guarded=%s disabled_kw=%s'
            % (has_insert, guarded, has_disabled))

    # ── ②b：`_on_tts_combo_changed` 拒绝 disabled 项 ──────────────
    fn = _fn(tree, '_on_tts_combo_changed')
    if fn is None:
        out['2b_disabled_option_rejected'] = (None, '找不到 _on_tts_combo_changed')
    else:
        seg = _src_of(app_src, fn)
        out['2b_disabled_option_rejected'] = (
            bool("get('disabled')" in seg and 'return' in seg),
            "get('disabled')=%s" % ("get('disabled')" in seg))

    # ── ②c：启动前拦截 CUDA 不可用 ───────────────────────────────
    fn = _fn(tree, '_on_tts_toggled')
    if fn is None:
        out['2c_cuda_preflight_block'] = (None, '找不到 _on_tts_toggled')
    else:
        seg = _src_of(app_src, fn)
        out['2c_cuda_preflight_block'] = (
            bool('_cuda_tts_available' in seg
                 and '_cuda_tts_unavailable_reason' in seg),
            'avail=%s reason=%s' % ('_cuda_tts_available' in seg,
                                    '_cuda_tts_unavailable_reason' in seg))

    # ── ④a：定时采集器**恒关**（**只看代码**，注释不算） ───────────
    fn = _fn(tree, '_collect_clone_pcm')
    if fn is None:
        out['4a_timer_collector_disabled'] = (None, '找不到 _collect_clone_pcm')
    else:
        assigns = []
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Attribute) and t.attr == 'enabled':
                        assigns.append(_src_of(app_src, n.value))
        new = any(a.strip() == 'False' for a in assigns)
        old = any('self._clone_enabled' in a for a in assigns)
        out['4a_timer_collector_disabled'] = (
            bool(new and not old),
            'assigns=%r' % (assigns,))

    # ── ④b：用户可见文案里不再承诺「每 30 s 或累计 ≥6 s」 ─────────
    #   🔴 **只看字符串常量**（排除 docstring）⇒ 注释不参与判定。
    olds = [s for s in _user_strings(app_src) if '每 30 s 或累计 ≥6 s' in s]
    out['4b_no_30s_promise_in_user_text'] = (
        bool(not olds), '命中=%d %r' % (len(olds), olds[:1]))

    # ── ⑤a：GUI 构造 TTSService 传 `clone=` ─────────────────────
    #   🔴 **必须定位到 GUI 那次调用**（`_on_tts_toggled` 里的）⇒
    #     不能拿 CLI 那次（CLI 一直传 `clone=_want_clone`）当证据。
    gui_call = None
    fn = _fn(tree, '_on_tts_toggled')
    if fn is None:
        out['5a_gui_passes_clone'] = (None, '找不到 _on_tts_toggled')
    else:
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id == 'TTSService':
                gui_call = n
                break
        if gui_call is None:
            out['5a_gui_passes_clone'] = (None, '_on_tts_toggled 里没有 TTSService 调用')
        else:
            # 🔴 **按 AST 关键字判定**（注释里出现 `clone=` 会让文本匹配恒真）
            has_clone = any(kw.arg == 'clone' for kw in gui_call.keywords)
            out['5a_gui_passes_clone'] = (
                bool(has_clone),
                'clone kw=%s' % has_clone)

    # ── ⑤b：`_retry_spk_labels` 接住 `is_new` 并排队取样 ─────────
    for tag, fname in (('5b_gui_retry_is_new', '_retry_spk_labels'),
                       ('5b_cli_retry_is_new', '_cli_retry_spk_labels')):
        fn = _fn(tree, fname)
        if fn is None:
            out[tag] = (None, '找不到 %s' % fname)
            continue
        seg = _src_of(app_src, fn)
        got = ('note_final(' in seg
               and '_is_new' in seg
               and '_spk_pending_embed.append' in seg)
        out[tag] = (bool(got),
                    'note_final=%s _is_new=%s append=%s'
                    % ('note_final(' in seg, '_is_new' in seg,
                       '_spk_pending_embed.append' in seg))

    return out


def static_checks_worker(w_src: str) -> dict:
    tree = ast.parse(w_src)
    out = {}

    # ①a：CUDA 分支设置 `_preset_name`
    fn = _fn(tree, '_setup_babelvox_voice')
    if fn is None:
        out['1a_preset_name_set'] = (None, '找不到 _setup_babelvox_voice')
    else:
        found = False
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if (isinstance(t, ast.Attribute)
                            and t.attr == '_preset_name'
                            and isinstance(t.value, ast.Name)
                            and t.value.id == 'self'):
                        found = True
        out['1a_preset_name_set'] = (bool(found), 'assign _preset_name=%s' % found)

    # ①b：`_fallback_to_preset` 的 CUDA 分支**不清空** speaker_name
    #   🔴 **按 AST 定位到 `USES_REF_AUDIO` 分支内部**：
    #     旧实现里 CUDA 分支**根本没有** speaker_name 的赋值
    #     （赋值在分支之前，统一走 `self.speaker_name = self._preset_name`）
    #     ⇒ 必须要求「CUDA 分支内部**自己**给 speaker_name 赋值」。
    fn = _fn(tree, '_fallback_to_preset')
    if fn is None:
        out['1b_cuda_fallback_keeps_name'] = (None, '找不到 _fallback_to_preset')
    else:
        cuda_branch = None
        for n in ast.walk(fn):
            if isinstance(n, ast.If) and 'USES_REF_AUDIO' in _src_of(w_src, n.test):
                cuda_branch = n
                break
        if cuda_branch is None:
            out['1b_cuda_fallback_keeps_name'] = (None, 'CUDA 分支找不到')
        else:
            # 🔴🔴🔴 §130：**只看 CUDA 分支的 body**（`ast.walk(If)` 会把
            #   **else 分支**（BabelVox 路线）也遍历进去 ⇒ 语义被污染）
            #   ⇒ 再按需**跟随委派**进 `_fallback_to_preset_ref_cuda()`
            #   ⇒ **鉴别力必须不变**（v2.1 形态：两处都没有 ⇒ FAIL）。
            def _collect(body):
                got = []
                for stmt in body:
                    for n in ast.walk(stmt):
                        if isinstance(n, ast.Assign):
                            for t in n.targets:
                                if (isinstance(t, ast.Attribute)
                                        and t.attr == 'speaker_name'):
                                    got.append((n, _src_of(w_src, n.value)))
                return got

            body_assigns = _collect(cuda_branch.body)
            has_boolop = any(isinstance(n.value, ast.BoolOp)
                             for n, _s in body_assigns)
            scope_assigns = body_assigns
            delegated = False
            if not has_boolop:
                # CUDA 分支 body 里没有 BoolOp 赋值 ⇒ 可能是 §130 的委派形态
                # 🔴 **在 AST 上直接找调用**（不用源码片段：
                #   `ast.get_source_segment` 需要节点有位置信息 ⇒ 合成节点取不到）
                def _calls_helper(stmts):
                    for stmt in stmts:
                        for n in ast.walk(stmt):
                            if isinstance(n, ast.Call):
                                f = n.func
                                if isinstance(f, ast.Attribute) and \
                                        f.attr == '_fallback_to_preset_ref_cuda':
                                    return True
                                if isinstance(f, ast.Name) and \
                                        f.id == '_fallback_to_preset_ref_cuda':
                                    return True
                    return False

                helper = _fn(tree, '_fallback_to_preset_ref_cuda')
                if helper is not None and _calls_helper(cuda_branch.body):
                    delegated = True
                    h_assigns = _collect(helper.body)
                    scope_assigns = h_assigns
                    has_boolop = any(isinstance(n.value, ast.BoolOp)
                                     for n, _s in h_assigns)
            assigns = [s for _n, s in scope_assigns]
            ok = bool(assigns) and has_boolop
            out['1b_cuda_fallback_keeps_name'] = (
                bool(ok),
                'CUDA 分支内 speaker_name 赋值=%r（委派共用出口=%r）'
                % (assigns, delegated))

    # ①c：synth 的音色闸门走 `_has_ref_audio`
    fn = _fn(tree, 'synth')
    if fn is None:
        out['1c_synth_gate_uses_ref_audio'] = (None, '找不到 synth')
    else:
        seg = _src_of(w_src, fn)
        out['1c_synth_gate_uses_ref_audio'] = (
            bool('_has_ref_audio' in seg and 'USES_REF_AUDIO' in seg),
            '_has_ref_audio=%s' % ('_has_ref_audio' in seg))

    # ⑤c：`spk_pending⇒keep_last`
    fn = _fn(tree, '_log_keep_last_clone')
    if fn is None:
        out['5c_keep_last_helper'] = (None, '找不到 _log_keep_last_clone')
    else:
        seg = _src_of(w_src, fn)
        out['5c_keep_last_helper'] = (
            bool('spk_pending' in seg and 'keep_last' in seg),
            'keyword=%s' % ('spk_pending' in seg and 'keep_last' in seg))

    # ⑤c：synth 的 spk=None 分支**调用**了 keep_last
    fn = _fn(tree, 'synth')
    seg = _src_of(w_src, fn) if fn else ''
    out['5c_synth_calls_keep_last'] = (
        bool('_log_keep_last_clone' in seg),
        'call=%s' % ('_log_keep_last_clone' in seg))

    return out


# ──────────────────────────────────────────────────────────────
# 变异体（反证）
# ──────────────────────────────────────────────────────────────

def _mutate(src: str, old: str, new: str, label: str):
    n = src.count(old)
    if n != 1:
        raise SystemExit('[ABORT] 变异点 %r 命中 %d 次（需恰好 1）' % (label, n))
    return src.replace(old, new)


MUT_W_1A_OLD = """            self._preset_name = 'A'
"""
MUT_W_1A_NEW = """            # MUTANT: 不缓存 _preset_name（= v2.1 的真实缺陷）
"""

# 🔴🔴🔴 §130：这段代码被搬进了新方法 `_fallback_to_preset_ref_cuda()`
#   ⇒ **只改缩进**（12 → 8 空格），**语义一字不变**
#   ⇒ 反证仍然在测同一件事：「回落把 speaker_name 恢复成 _preset_name」
MUT_W_1B_OLD = """        self.speaker_embed = None
        self.speaker_name = self._preset_name or 'A'
        ref = self._preset_ref_path
"""
MUT_W_1B_NEW = """        self.speaker_embed = self._preset_embed
        self.speaker_name = self._preset_name
        ref = self._preset_ref_path
"""

MUT_W_1C_OLD = """            if getattr(self.engine, 'USES_REF_AUDIO', False):
                if not self._has_ref_audio():
                    emit({'kind': 'error',
                          'message': '没有可用的音色（CUDA 参考音频缺失）',
                          'id': jid})
                    return
            elif self.speaker_embed is None and not self.speaker_name:
"""
MUT_W_1C_NEW = """            if self.speaker_embed is None and not self.speaker_name:
"""

MUT_APP_5B_OLD = """                _is_new = self._spk_voices.note_final(seg, spk, clean_ranges)
                if _is_new:
                    self._spk_pending_embed.append((seg, spk))
                    self._ui_log('[spk] 标签补到：第 %d 段 = %s（新说话人，已排队取样）'
                                 % (seg, spk))
                else:
                    self._ui_log('[spk] 标签补到：第 %d 段 = %s' % (seg, spk))
"""
MUT_APP_5B_NEW = """                self._spk_voices.note_final(seg, spk, clean_ranges)
                self._ui_log('[spk] 标签补到：第 %d 段 = %s' % (seg, spk))
"""


def run_probe(py: str, target_dir: str):
    """在**子进程**里跑探针，返回解析后的 JSON（或 None）。"""
    try:
        p = subprocess.run([py, PROBE, target_dir], capture_output=True,
                           timeout=180)
    except Exception as e:
        return None, 'probe failed: %r' % e
    txt = (p.stdout or b'').decode('utf-8', 'replace').strip()
    if not txt:
        return None, 'probe 无输出；stderr=%s' % (
            (p.stderr or b'').decode('utf-8', 'replace')[-400:])
    try:
        return json.loads(txt.splitlines()[-1]), None
    except Exception as e:
        return None, 'probe 输出不可解析: %r / %s' % (e, txt[-300:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', default=os.path.join(REPO, 'live_caption'),
                    help='被测目录（含 live_caption_app.py / tts_worker.py）')
    ap.add_argument('--pkg', default=None, help='客户包 app 目录（覆盖 --target）')
    ap.add_argument('--out', default=os.path.join(HERE, 'app215_app061_voice_clone_evidence.json'))
    ap.add_argument('--python', default=sys.executable)
    args = ap.parse_args()

    target = os.path.abspath(args.pkg or args.target)
    app_py = os.path.join(target, 'live_caption_app.py')
    worker_py = os.path.join(target, 'tts_worker.py')
    for p in (app_py, worker_py):
        if not os.path.isfile(p):
            print('[FAIL] 找不到 %s' % p)
            return 2

    app_src = open(app_py, encoding='utf-8').read()
    w_src = open(worker_py, encoding='utf-8').read()

    print('== 被测对象 ==')
    print('  target = %s' % target)
    print('  live_caption_app.py sha256=%s (%d B)' % (sha256_file(app_py),
                                                     os.path.getsize(app_py)))
    print('  tts_worker.py       sha256=%s (%d B)' % (sha256_file(worker_py),
                                                     os.path.getsize(worker_py)))

    # ── 静态判据 ────────────────────────────────────────────────
    print('\n== 静态判据 ==')
    st = {}
    st.update(static_checks(app_src))
    st.update(static_checks_worker(w_src))
    for k, (ok, detail) in st.items():
        check(k, ok, detail, group='static')

    # ── 行为判据（正常体） ──────────────────────────────────────
    print('\n== 行为判据（正常体） ==')
    res, err = run_probe(args.python, target)
    if res is None:
        check('behaviour_probe', None, err or '探针失败', group='behaviour')
        res = {}
    else:
        check('behaviour_probe', True, '探针可用', group='behaviour')

    check('1a_preset_name_after_setup_is_A',
          res.get('preset_name_after_setup') == 'A',
          'preset_name_after_setup=%r' % res.get('preset_name_after_setup'),
          group='behaviour')
    check('1b_speaker_name_survives_fallback',
          bool(res.get('speaker_name_after_fallback')),
          'speaker_name_after_fallback=%r' % res.get('speaker_name_after_fallback'),
          group='behaviour')
    # 🔴 **旧状态强制**（模拟 v2.1：`_preset_name` 从未被设置）
    check('1b_old_state_fallback_keeps_name',
          bool(res.get('old_state_speaker_name_after_fallback')),
          'old_state speaker_name=%r gate_tripped=%r'
          % (res.get('old_state_speaker_name_after_fallback'),
             res.get('old_state_voice_gate_tripped')),
          group='behaviour')
    check('1c_old_state_no_voice_error',
          res.get('old_state_synth_voice_error') is False,
          'old_state messages=%r' % res.get('old_state_synth_messages'),
          group='behaviour')
    check('1c_no_voice_error_when_ref_present',
          res.get('synth_with_ref_voice_error') is False,
          'messages=%r' % res.get('synth_with_ref_messages'),
          group='behaviour')
    check('1c_voice_error_when_ref_missing',
          res.get('synth_without_ref_voice_error') is True,
          'messages=%r' % res.get('synth_without_ref_messages'),
          group='behaviour')
    kla = res.get('keep_last') or {}
    check('5c_has_clone_voice_true_only_with_clone',
          kla.get('no_clone') is False and kla.get('clone_kind') is True
          and kla.get('clone_active') is True,
          'no_clone=%r clone_kind=%r clone_active=%r'
          % (kla.get('no_clone'), kla.get('clone_kind'), kla.get('clone_active')),
          group='behaviour')
    check('5c_keep_last_logs_keyword',
          bool(kla.get('keep_last_log')),
          'log=%r' % (kla.get('keep_last_log') or []),
          group='behaviour')

    # ── 反证（变异体） ──────────────────────────────────────────
    print('\n== 反证（变异体必须 FAIL） ==')
    muts = []

    tmp = tempfile.mkdtemp(prefix='app215_mut_')
    try:
        # M1：①a —— 去掉 CUDA 分支的 `_preset_name = 'A'`
        #   信号：`_setup_babelvox_voice()` 之后 `_preset_name` 不再是 'A'
        d1 = os.path.join(tmp, 'm1')
        shutil.copytree(target, d1, dirs_exist_ok=True)
        p1 = os.path.join(d1, 'tts_worker.py')
        s1 = open(p1, encoding='utf-8').read()
        s1 = _mutate(s1, MUT_W_1A_OLD, MUT_W_1A_NEW, 'M1 去掉 _preset_name')
        open(p1, 'w', encoding='utf-8').write(s1)
        r1, e1 = run_probe(args.python, d1)
        ok1 = bool(r1) and r1.get('preset_name_after_setup') != 'A'
        check('M1_1a_mutant_is_caught', ok1,
              'mutant preset_name=%r%s'
              % (r1.get('preset_name_after_setup') if r1 else None,
                 (' err=%s' % e1) if e1 else ''), group='counterproof')
        muts.append({'id': 'M1', 'what': 'CUDA 分支不设 _preset_name',
                     'caught': ok1})

        # M2：①b —— 回落路径恢复旧形态（把 speaker_name 清成 _preset_name）
        #   信号：**旧状态**回落之后 `speaker_name` 不再是真值
        d2 = os.path.join(tmp, 'm2')
        shutil.copytree(target, d2, dirs_exist_ok=True)
        p2 = os.path.join(d2, 'tts_worker.py')
        s2 = open(p2, encoding='utf-8').read()
        s2 = _mutate(s2, MUT_W_1B_OLD, MUT_W_1B_NEW, 'M2 恢复旧回落')
        open(p2, 'w', encoding='utf-8').write(s2)
        r2, e2 = run_probe(args.python, d2)
        ok2 = bool(r2) and not r2.get('old_state_speaker_name_after_fallback')
        check('M2_1b_mutant_is_caught', ok2,
              'mutant old_state speaker_name=%r%s'
              % (r2.get('old_state_speaker_name_after_fallback') if r2 else None,
                 (' err=%s' % e2) if e2 else ''), group='counterproof')
        muts.append({'id': 'M2', 'what': '回落恢复旧形态（清空 speaker_name）',
                     'caught': ok2})

        # M3：① —— **恢复 v2.1 的完整旧形态**（①a + ①b + ①c 三处一起退）
        #   🔴 **为什么必须三处一起退**：v2.1 的真实故障是三处**叠加**：
        #     ①a `_preset_name` 从未设置 ⇒ ①b 回落把 `speaker_name` 清成 None
        #     ⇒ ①c 的旧闸门 `speaker_embed is None and not speaker_name` 命中
        #     ⇒ 每句报「没有可用的音色」。
        #   ⇒ 只退其中一处 ⇒ **另外两处会把它盖住** ⇒ 判据抓不到
        #     （这不是判据失效，而是「单点修复也足以消除症状」）。
        #   ⇒ 本反证要求三处一起退 ⇒ 必须复现 v2.1 的症状。
        d3 = os.path.join(tmp, 'm3')
        shutil.copytree(target, d3, dirs_exist_ok=True)
        p3 = os.path.join(d3, 'tts_worker.py')
        s3 = open(p3, encoding='utf-8').read()
        s3 = _mutate(s3, MUT_W_1A_OLD, MUT_W_1A_NEW, 'M3-a 去掉 _preset_name')
        s3 = _mutate(s3, MUT_W_1B_OLD, MUT_W_1B_NEW, 'M3-b 恢复旧回落')
        s3 = _mutate(s3, MUT_W_1C_OLD, MUT_W_1C_NEW, 'M3-c 恢复旧音色闸门')
        open(p3, 'w', encoding='utf-8').write(s3)
        r3, e3 = run_probe(args.python, d3)
        ok3 = bool(r3) and r3.get('old_state_synth_voice_error') is True
        check('M3_1abc_mutant_is_caught', ok3,
              'mutant old_state voice_error=%r%s'
              % (r3.get('old_state_synth_voice_error') if r3 else None,
                 (' err=%s' % e3) if e3 else ''), group='counterproof')
        muts.append({'id': 'M3', 'what': '恢复 v2.1 的 ①a+①b+①c 三处叠加',
                     'caught': ok3})

        # M4：⑤a —— GUI 不传 clone=
        d4 = os.path.join(tmp, 'm4')
        shutil.copytree(target, d4, dirs_exist_ok=True)
        p4 = os.path.join(d4, 'live_caption_app.py')
        s4 = open(p4, encoding='utf-8').read()
        s4 = _mutate(s4, "                clone=self._clone_enabled,\n", '',
                     'M4 GUI 不传 clone')
        open(p4, 'w', encoding='utf-8').write(s4)
        st4 = static_checks(s4)
        ok4 = st4.get('5a_gui_passes_clone', (None,))[0] is False
        check('M4_5a_mutant_is_caught', ok4,
              'mutant 5a=%r' % (st4.get('5a_gui_passes_clone'),),
              group='counterproof')
        muts.append({'id': 'M4', 'what': 'GUI 不传 clone=', 'caught': ok4})

        # M5：⑤b —— GUI 的 _retry_spk_labels 丢掉 is_new
        d5 = os.path.join(tmp, 'm5')
        shutil.copytree(target, d5, dirs_exist_ok=True)
        p5 = os.path.join(d5, 'live_caption_app.py')
        s5 = open(p5, encoding='utf-8').read()
        s5 = _mutate(s5, MUT_APP_5B_OLD, MUT_APP_5B_NEW, 'M5 GUI retry 丢 is_new')
        open(p5, 'w', encoding='utf-8').write(s5)
        st5 = static_checks(s5)
        ok5 = st5.get('5b_gui_retry_is_new', (None,))[0] is False
        check('M5_5b_mutant_is_caught', ok5,
              'mutant 5b=%r' % (st5.get('5b_gui_retry_is_new'),),
              group='counterproof')
        muts.append({'id': 'M5', 'what': 'GUI _retry_spk_labels 丢 is_new',
                     'caught': ok5})

        # M6：④ —— 恢复定时采集器
        d6 = os.path.join(tmp, 'm6')
        shutil.copytree(target, d6, dirs_exist_ok=True)
        p6 = os.path.join(d6, 'live_caption_app.py')
        s6 = open(p6, encoding='utf-8').read()
        s6 = _mutate(s6, "        col.enabled = False\n",
                     "        col.enabled = bool(self._clone_enabled)\n",
                     'M6 恢复定时采集器')
        open(p6, 'w', encoding='utf-8').write(s6)
        st6 = static_checks(s6)
        ok6 = st6.get('4a_timer_collector_disabled', (None,))[0] is False
        check('M6_4a_mutant_is_caught', ok6,
              'mutant 4a=%r' % (st6.get('4a_timer_collector_disabled'),),
              group='counterproof')
        muts.append({'id': 'M6', 'what': '恢复定时克隆采集器', 'caught': ok6})

        # M7：② —— CUDA 选项回到「不可用就不列」（没有 disabled 字段）
        d7 = os.path.join(tmp, 'm7')
        shutil.copytree(target, d7, dirs_exist_ok=True)
        p7 = os.path.join(d7, 'live_caption_app.py')
        s7 = open(p7, encoding='utf-8').read()
        s7 = _mutate(s7, "        disabled=(not _cuda_ok), why=_cuda_why,\n", '',
                     'M7 去掉 CUDA 的 disabled 字段')
        open(p7, 'w', encoding='utf-8').write(s7)
        st7 = static_checks(s7)
        ok7 = st7.get('2a_cuda_option_always_listed', (None,))[0] is False
        check('M7_2a_mutant_is_caught', ok7,
              'mutant 2a=%r' % (st7.get('2a_cuda_option_always_listed'),),
              group='counterproof')
        muts.append({'id': 'M7', 'what': 'CUDA 选项不再带 disabled 字段',
                     'caught': ok7})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ── 汇总 ────────────────────────────────────────────────────
    n_fail = len(FAILS)
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    ev = {
        'task': 'APP-061 ①②④⑤ 代码层判据',
        'target': target,
        'python': args.python,
        'files': {
            'live_caption_app.py': {'sha256': sha256_file(app_py),
                                    'bytes': os.path.getsize(app_py)},
            'tts_worker.py': {'sha256': sha256_file(worker_py),
                              'bytes': os.path.getsize(worker_py)},
        },
        'static': {k: {'result': ('PASS' if v[0] is True else
                                  'FAIL' if v[0] is False else 'NONE'),
                       'detail': v[1]} for k, v in st.items()},
        'behaviour_probe': res,
        'counterproofs': muts,
        'n_pass': len(PASSES),
        'n_fail': n_fail,
        'n_none': len(NONE_),
        'checks': PASSES + FAILS + NONE_,
        'verdict': verdict,
        'note': ('三态判据：None = 无法判定（不记 FAIL）。'
                 '反证 = 把缺陷重新注入变异体，判据必须 FAIL。'),
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n== 结果 ==')
    print('  PASS=%d  FAIL=%d  NONE=%d  verdict=%s'
          % (len(PASSES), n_fail, len(NONE_), verdict))
    print('  证据：%s' % args.out)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
