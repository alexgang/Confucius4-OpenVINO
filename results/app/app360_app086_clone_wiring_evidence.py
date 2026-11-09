"""APP-086(2) 接线验收：**判据 + 反证组**（纯 CPU，不加载任何模型）。

每个判据组都必须能被**反证组**（人为破坏后的副本）识破
⇒ 「PASS」不等于「正确」（MEMORY §四：PASS ≠ 正确）。

判据组：
  G1 worker 结构性兜底：「沿用上一句音色」分支**必须**被 `not _bound` 守住
     （按句绑定模式 ⇒ `spk=None` ⇒ 回落预设 A ⇒ 绝不沿用上一句的克隆音色）。
  G2 晚到标签通道**没被堵死**：提交命令的 `spk` 对无标签句必须是空的
     （`voice_for_sentence(...) or None`）⇒ worker 的 `if not spk` 分支可达
     ⇒ 官方标签后到时能覆盖「最近说话人」。
  G3 **只有一份旁路**：App 必须把**既有的** `SpeakerBridge`/`SpeakerVoiceTable`
     注入策略层 ⇒ 不双跑 wespeaker/pyannote。
  G4 策略层推送规则（**行为级**）：官方标签优先 / 该说话人没音色不推 /
     cos < 0.25 不推 / 推且只推一次。
  G5 f（克隆工作移出 ASR/音频线程）：`on_segment` 只入队，嵌入只在策略线程。
  G6 不产生第二条登记路径：策略层**不**调用 `register_spk_voice`。

用法：python app360_app086_clone_wiring_evidence.py
产物：results/app/app360_app086_clone_wiring_evidence.json
"""
from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LC = os.path.join(ROOT, 'live_caption')
APP = os.path.join(LC, 'live_caption_app.py')
WRK = os.path.join(LC, 'tts_worker.py')
CLN = os.path.join(LC, 'clone_voice.py')
OUT = os.path.join(ROOT, 'results', 'app',
                   'app360_app086_clone_wiring_evidence.json')


def read(p):
    return open(p, encoding='utf-8', newline='').read()


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


# ── G1 ───────────────────────────────────────────────────────────────
def g1_worker_guard(src):
    """worker 侧：`elif self._has_clone_voice():` 必须带 `and not _bound`。"""
    if 'elif self._has_clone_voice() and not _bound:' not in src:
        return False, '未找到受 `not _bound` 守护的「沿用上一句音色」分支'
    if 'elif self._has_clone_voice():' in src:
        return False, '仍存在未受守护的 `elif self._has_clone_voice():` 分支'
    return True, 'OK'


# ── G2 ───────────────────────────────────────────────────────────────
def _submit_calls(tree):
    """所有 `tts.submit(...)` 调用（AST 精确，不靠文本计数）。

    ⚠️ 必须同时覆盖 `tts.submit(...)`（CLI）与 `self.tts.submit(...)`（GUI）
    ⇒ 否则 GUI 那个提交点会**逃过检查**（反证组就识破不了）。
    """
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'submit'):
            continue
        v = n.func.value
        if isinstance(v, ast.Name) and v.id == 'tts':
            out.append(n)
        elif isinstance(v, ast.Attribute) and v.attr == 'tts':
            out.append(n)
    return out


def g2_late_label_channel(app, wrk):
    """提交命令对无标签句必须留空 `spk`；worker 的晚到标签分支必须仍在。"""
    if 'if not spk and seg is not None:' not in wrk:
        return False, 'worker 的晚到标签分支 `if not spk and seg is not None:` 不存在'
    if '_resolve_clone_spk' in app:
        return False, 'App 仍在提交期解析音色 ⇒ 会堵死晚到标签通道'
    tree = ast.parse(app)
    calls = _submit_calls(tree)
    if len(calls) < 3:
        return False, 'tts.submit 调用点只有 %d 个（应 ≥3：GUI 1 + CLI 3）' % len(calls)
    for c in calls:
        kw = [k for k in c.keywords if k.arg == 'spk']
        if not kw:
            return False, '有一个 tts.submit 没有传 spk（口径不一致）'
        v = kw[0].value
        # 必须是 `voice_for_sentence(...) or None` ⇒ 无标签句 ⇒ None
        if not (isinstance(v, ast.BoolOp) and isinstance(v.op, ast.Or)):
            return False, '有一个 tts.submit 的 spk 不是 `... or None` 形式'
        src = ast.get_source_segment(app, v.values[0]) or ''
        if 'voice_for_sentence(' not in src:
            return False, '有一个 tts.submit 的 spk 不是 voice_for_sentence(...)：%r' % src
    return True, 'OK（%d 个 tts.submit 全部是 `voice_for_sentence(...) or None`）' % len(calls)


# ── G3 ───────────────────────────────────────────────────────────────
def g3_single_bypass(app, cln):
    """App 必须注入既有旁路/音色表；策略层自身不得再建旁路（注入时）。"""
    if 'bridge=self._spk_bridge, table=self._spk_voices,' not in app:
        return False, 'App 未把既有旁路/音色表注入策略层'
    if 'bridge=_spk_bridge, table=_spk_voices,' not in app:
        return False, 'CLI 未把既有旁路/音色表注入策略层'
    tree = ast.parse(cln)
    cls = None
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == 'CloneVoices':
            cls = n
    if cls is None:
        return False, 'clone_voice.CloneVoices 不存在'
    init = None
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == '__init__':
            init = n
    if init is None:
        return False, 'CloneVoices.__init__ 不存在'
    src_seg = ast.get_source_segment(cln, init) or ''
    if 'if self.br is None:' not in src_seg:
        return False, 'CloneVoices.__init__ 没有「未注入才自建旁路」的守卫'
    if 'SpeakerBridge(' not in src_seg:
        return False, 'CloneVoices.__init__ 里找不到自建旁路的代码（口径不符）'
    return True, 'OK'


# ── G4（行为级）──────────────────────────────────────────────────────
class _FakeTable:
    def __init__(self, labelled=(), voiced=()):
        self._labelled = set(labelled)
        self._voiced = set(voiced)

    def spk_of(self, seg):
        return 'S1' if seg in self._labelled else ''

    def has_voice(self, spk):
        return spk in self._voiced

    def voice_for_sentence(self, seg):
        return ''


class _FakeTracker:
    class _Enc:
        def embed(self, pcm, sr):
            import numpy as np
            return np.ones(192, dtype='float32')

    class _Clu:
        centroids = [(1.0,) * 192]

        def _label(self, k):
            return 'S2'

    def __init__(self):
        self._enc = self._Enc()
        self._clu = self._Clu()
        self._lock = __import__('threading').Lock()


class _FakeBridge:
    def __init__(self):
        self._tracker = _FakeTracker()


def _run_policy(cln_path, table, cos_ok=True):
    """在**指定副本**上导入策略层并触发一次推送判定。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location('cln_probe', cln_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pushed = []
    import numpy as np
    pol = mod.CloneVoices(
        on_log=lambda m: None, bridge=_FakeBridge(), table=table,
        pcm_getter=lambda: (np.zeros(16000 * 40, dtype='float32'), 0.0),
        span_getter=lambda seg: (0.0, 2.0),
        on_nearest=lambda seg, spk, sim: pushed.append((seg, spk, sim)))
    try:
        pol._nearest[3] = ('S2', 0.9 if cos_ok else 0.10)
        pol._try_push(3)
        # 再推一次（应被去重）
        pol._try_push(3)
        return pushed, mod
    finally:
        try:
            pol.close()
        except Exception:
            pass


def g4_policy_rules(cln_path):
    # ① 官方标签优先 ⇒ 不推
    pushed, _ = _run_policy(cln_path, _FakeTable(labelled=[3], voiced=['S2']))
    if pushed:
        return False, '有官方标签时仍推了最近说话人：%r' % (pushed,)
    # ② 该说话人没登记音色 ⇒ 不推
    pushed, _ = _run_policy(cln_path, _FakeTable(labelled=[], voiced=[]))
    if pushed:
        return False, '该说话人没有音色时仍推了：%r' % (pushed,)
    # ③ 有音色 + cos 足够 ⇒ 推，且**只推一次**
    pushed, _ = _run_policy(cln_path, _FakeTable(labelled=[], voiced=['S2']))
    if len(pushed) != 1:
        return False, '应恰好推 1 次，实际 %d 次：%r' % (len(pushed), pushed)
    # ④ cos < 0.25 ⇒ 不推
    pushed, _ = _run_policy(cln_path, _FakeTable(labelled=[], voiced=['S2']),
                            cos_ok=False)
    if pushed:
        return False, 'cos 不足时仍推了：%r' % (pushed,)
    return True, 'OK'


# ── G5 ───────────────────────────────────────────────────────────────
def g5_off_thread(cln):
    """`on_segment` 只入队；嵌入只在策略线程（`_embed`）里做。"""
    tree = ast.parse(cln)
    cls = None
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == 'CloneVoices':
            cls = n
    fns = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}

    def calls_in(fn):
        out = []
        for n in ast.walk(fn):
            if isinstance(n, ast.Call):
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else \
                    (f.id if isinstance(f, ast.Name) else '')
                out.append(name)
        return out

    on_calls = calls_in(fns['on_segment'])
    if 'embed' in on_calls or '_embed' in on_calls:
        return False, 'on_segment 里做了嵌入（阻塞 ASR/音频线程）：%r' % on_calls
    if 'put' not in on_calls:
        return False, 'on_segment 没有入队'
    if 'embed' not in calls_in(fns['_embed']):
        return False, '_embed 里没有嵌入调用'
    if '_embed' not in calls_in(fns['_worker']):
        return False, '策略线程没有调用 _embed'
    return True, 'OK'


# ── G6 ───────────────────────────────────────────────────────────────
def g6_no_second_registration(cln, app):
    """策略层**不得**登记音色（AST 精确：只看真正的调用，不看文档字符串）。"""
    tree = ast.parse(cln)
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else \
                (f.id if isinstance(f, ast.Name) else '')
            if name in ('register_spk_voice', 'mark_embedded',
                        'mark_registered', 'registration_ticket'):
                bad.append(name)
    if bad:
        return False, '策略层出现了登记类调用（第二条登记路径）：%r' % bad
    if 'self.tts.register_spk_voice(' not in app:
        return False, 'App 的登记路径不见了'
    return True, 'OK'


# ── 反证组 ───────────────────────────────────────────────────────────
def mutate(src, old, new, label):
    assert src.count(old) >= 1, label
    return src.replace(old, new, 1)


def build_counterexamples():
    """每组一个「人为破坏」的副本 ⇒ 判据必须 FAIL。"""
    app0, wrk0, cln0 = read(APP), read(WRK), read(CLN)
    cex = {}

    # G1 反证：去掉 `and not _bound` ⇒ 判据必须失败
    cex['G1'] = ('G1', dict(
        app=app0,
        wrk=mutate(wrk0, 'elif self._has_clone_voice() and not _bound:',
                   'elif self._has_clone_voice():', 'G1 cex'),
        cln=cln0))

    # G2 反证：提交期硬塞 spk ⇒ 判据必须失败
    cex['G2'] = ('G2', dict(
        app=mutate(app0,
                   'spk=(self._spk_voices.voice_for_sentence(',
                   "spk=('S2' or self._spk_voices.voice_for_sentence(",
                   'G2 cex'),
        wrk=wrk0, cln=cln0))

    # G3 反证：App 不注入旁路 ⇒ 判据必须失败
    cex['G3'] = ('G3', dict(
        app=mutate(app0, 'bridge=self._spk_bridge, table=self._spk_voices,',
                   'bridge=None, table=None,', 'G3 cex'),
        wrk=wrk0, cln=cln0))

    # G4 反证：把 cos 门槛降到 0 ⇒ 「cos 不足不推」必须失败
    cex['G4'] = ('G4', dict(
        app=app0, wrk=wrk0,
        cln=mutate(cln0, 'MIN_SIM_NEAREST = 0.25', 'MIN_SIM_NEAREST = 0.0',
                   'G4 cex')))

    # G5 反证：把嵌入搬进 on_segment ⇒ 判据必须失败
    cex['G5'] = ('G5', dict(
        app=app0, wrk=wrk0,
        cln=mutate(cln0, '        self._q.put(seg)',
                   '        self._embed(seg)\n        self._q.put(seg)',
                   'G5 cex')))

    # G6 反证：策略层里加一条登记 ⇒ 判据必须失败
    cex['G6'] = ('G6', dict(
        app=app0, wrk=wrk0,
        cln=mutate(cln0, '    def _cached(self, seg_id):',
                   '    def _reg(self):\n        self.tts.register_spk_voice('
                   "'S2', None)\n\n    def _cached(self, seg_id):",
                   'G6 cex')))
    return cex


def run_group(name, app, wrk, cln, cln_path):
    if name == 'G1':
        return g1_worker_guard(wrk)
    if name == 'G2':
        return g2_late_label_channel(app, wrk)
    if name == 'G3':
        return g3_single_bypass(app, cln)
    if name == 'G4':
        return g4_policy_rules(cln_path)
    if name == 'G5':
        return g5_off_thread(cln)
    if name == 'G6':
        return g6_no_second_registration(cln, app)
    raise KeyError(name)


def main() -> int:
    app, wrk, cln = read(APP), read(WRK), read(CLN)
    results = {}
    for name in ('G1', 'G2', 'G3', 'G4', 'G5', 'G6'):
        ok, msg = run_group(name, app, wrk, cln, CLN)
        results[name] = {'pass': bool(ok), 'msg': msg}

    # 反证组：把「被测对象」换成破坏副本 ⇒ 判据必须 FAIL
    cex_results = {}
    tmp = tempfile.mkdtemp(prefix='app360_cex_')
    try:
        for key, (name, m) in build_counterexamples().items():
            p = os.path.join(tmp, key + '_clone_voice.py')
            shutil.copyfile(CLN, p)
            if m['cln'] != cln:
                open(p, 'w', encoding='utf-8', newline='').write(m['cln'])
            ok, msg = run_group(name, m['app'], m['wrk'], m['cln'], p)
            cex_results[key] = {'must_fail': True, 'failed_as_expected': (not ok),
                                'msg': msg}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n_pass = sum(1 for v in results.values() if v['pass'])
    n_fail = len(results) - n_pass
    cex_ok = sum(1 for v in cex_results.values() if v['failed_as_expected'])
    out = {
        'task': 'APP-086(2) 接线验收',
        'groups': results,
        'n_pass': n_pass, 'n_fail': n_fail,
        'counterexamples': cex_results,
        'n_cex_detected': cex_ok, 'n_cex': len(cex_results),
        'files': {os.path.basename(p): {'sha256': sha(p),
                                         'bytes': os.path.getsize(p)}
                  for p in (APP, WRK, CLN)},
    }
    out['verdict'] = 'PASS' if (n_fail == 0 and cex_ok == len(cex_results)) \
        else 'FAIL'
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
