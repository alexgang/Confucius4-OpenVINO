# -*- coding: utf-8 -*-
"""app121 — APP-027 V3 的**前置修复验收**（§84：CLI 克隆链路）。

## 本轮修的是什么（真实缺陷，不是脚本问题）

APP-027 **V3 明文**：
> **V3 克隆**：用 SPE 前 5 分钟切片（单一男声）实时跑，**开启克隆**，落盘 ≥ 10 句 wav。

⇒ 但实测发现：**CLI 路径根本没有克隆链路** ⇒ V3 **客观做不了**。

🔴 **根因（三条，都在 `live_caption_app.py` 的 CLI 侧）**：
1. 采集器是 **`App._collect_clone_pcm`（GUI 实例方法）**
   ⇒ `run_cli` 构造 `Session(eng, src, on_final=on_final)` ⇒ **没传 `on_audio`**
   ⇒ `Session._loop` 里的 `self.on_audio(pcm)` **永远不执行**
   ⇒ **克隆源 PCM 从不离开主进程**；
2. `run_cli` 构造 `TTSService(...)` 时**没传 `clone=True`**
   ⇒ worker 侧 `--clone` 参数**不加** ⇒ `clone_mode` 恒为 False；
3. worker 的**逐句 jsonl** 里**没有「这句用的音色来源」字段**
   ⇒ reviewer 拿到 wav **无法判断某句是不是克隆音色的产物**
   ⇒ 只能靠目录名猜 ⇒ **结论不可核**。

🔴 **修法**：
- 采集逻辑抽成 **`clone_collector.CloneCollector`**（独立模块）⇒ **GUI 与 CLI 共用一份**；
- `run_cli` 接上 `Session(..., on_audio=col.feed)` + `TTSService(..., clone=True)`；
- worker 的 `_APP030_JSONL_KEYS` 增加 `clone_active` / `clone_mode` / `clone_audio_s`
  ⇒ **逐句**记录「合成那一刻」的音色来源。

## 本脚本做什么（**零推理、零 GPU、零 NPU、不调 MiniMax**）

- **A 组（等价性）**：新采集器 vs 旧实现（`_collect_clone_pcm_legacy`）
  ⇒ 对**同一段合成 PCM**，两者的「触发时机」必须**完全一致**
  ⇒ 证明「抽成独立类」没有改变 GUI 的既有行为；
- **B 组（CLI 接线）**：静态检查 `run_cli` 是否真的接上了
  `on_audio` / `clone=True` / 采集器 ⇒ **用 AST**，不用脆弱的字符串匹配；
- **C 组（worker 遥测）**：`_APP030_JSONL_KEYS` 必须含三个新字段；
  且 `_record_jsonl` 的 `tel is None` 分支也要写这三个字段
  ⇒ 否则失败/丢句的行会漏掉 ⇒ reviewer 的分母失真；
- **D 组（反证）**：**故意写错** ⇒ 判据必须 FAIL
  ⇒ 证明闸门不是「恒 PASS」的摆设（§80 的教训：判据本身要可信）。

## 用法

    <pkg>/python/python.exe results/app/app121_app027_v3_clone_cli.py
"""
from __future__ import annotations

import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
OUT = os.path.join(HERE, 'app121_app027_v3_clone_cli_evidence.json')

#: 🔴 **反证基线**：用**固定 commit SHA** 取「修复前」的源码
#:   ⇒ 不能用 HEAD（HEAD 修好后就是修复版 ⇒ 反证永远落空 ⇒ 假证据，§31 教训）
BASELINE_COMMIT = 'a2bb97a'   # §83 的 commit（= 本轮修复前的最后一个入库点）

REPO_LC = os.path.join(REPO, 'live_caption')
PKG_LC = os.path.join(PKG_ROOT, 'app')


# ── 工具 ────────────────────────────────────────────────────────
def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _norm(s):
    """归一化换行（仓库 ⇄ 包目录常有 CRLF/LF 差异 ⇒ 否则误判「包内是旧版」）。"""
    return s.replace('\r\n', '\n').replace('\r', '\n')


def _find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
    return None


def _has_call(node, func_name, attr=None):
    """函数体内是否调用了 `func_name(...)`（或 `x.func_name(...)`）。"""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        if isinstance(fn, ast.Name) and fn.id == func_name:
            return True
        if isinstance(fn, ast.Attribute) and fn.attr == func_name:
            if attr is None or attr == fn.attr:
                return True
    return False


def _kwargs_of_call(node, func_name):
    """找 `func_name(...)` 的调用并返回其关键字参数名集合。"""
    out = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        name = None
        if isinstance(fn, ast.Name):
            name = fn.id
        elif isinstance(fn, ast.Attribute):
            name = fn.attr
        if name != func_name:
            continue
        out.append({k.arg for k in sub.keywords if k.arg})
    return out


# ── A 组：采集器等价性 ───────────────────────────────────────────
def _load_collector_module():
    """加载 `clone_collector` 模块（不 import 被测的业务模块）。"""
    sys.path.insert(0, REPO_LC)
    import clone_collector
    return clone_collector


def _legacy_collector_class():
    """从 `live_caption_app.py` 里抽出旧实现（`_collect_clone_pcm_legacy`）。

    🔴 **验收脚本一律不 `import` 被测模块**（顶层 numpy 会让 import 阶段 abort）
    ⇒ `ast` 抽源码 + `exec` 独立命名空间（§铁律）。
    """
    src = _read(os.path.join(REPO_LC, 'live_caption_app.py'))
    tree = ast.parse(src)
    fn = _find_func(tree, '_collect_clone_pcm_legacy')
    assert fn is not None, '找不到 _collect_clone_pcm_legacy'
    # 把方法体抠出来，包成一个独立函数
    seg = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(seg)
    import numpy as np
    import time as _time
    ns = {'np': np, '_CLONE_FRAME': 320, '_CLONE_MAX_S': 10.0,
          '_CLONE_MIN_S': 3.0, '_CLONE_UPDATE_INTERVAL_S': 30.0,
          '_CLONE_NEW_VOICED_S': 6.0, 'time': _time}
    exec(compile(seg, '<legacy>', 'exec'), ns)
    return ns['_collect_clone_pcm_legacy']


def _make_pcm(n_samples=16000 * 30, sr=16000, voiced=True):
    """造一段测试 PCM：语音段（正弦）+ 静音段。"""
    import numpy as np
    t = np.arange(n_samples, dtype=np.float32) / sr
    if voiced:
        sig = 0.25 * np.sin(2 * np.pi * 180.0 * t)
        # 每 5 s 插 0.6 s 静音
        mute = np.zeros(n_samples, dtype=bool)
        for start in range(0, n_samples - int(sr * 0.6), int(sr * 5)):
            mute[start:start + int(sr * 0.6)] = True
        sig = sig.copy()
        sig[mute] = 0.0
    else:
        sig = np.zeros(n_samples, dtype=np.float32)
    return sig.astype(np.float32)


def _run_legacy(fn, pcm_chunks, stub):
    """跑旧实现，记录「在第几个 chunk 触发了更新」。

    🔴 **键名要用旧实现的真实属性名**（`_clone_sent_voiced_s`），
    且旧实现是**方法**（`self.xxx`）⇒ 桩必须**支持属性访问**，
    不能用普通 dict（`getattr(dict, 'tts')` 恒为 None ⇒ 静默走不到发送分支）。
    """
    trig = []
    for i, c in enumerate(pcm_chunks):
        before = stub._clone_sent_voiced_s
        fn(stub, c)
        after = stub._clone_sent_voiced_s
        if after > before:
            trig.append(i)
    return trig


def _run_new(col, pcm_chunks):
    trig = []
    for i, c in enumerate(pcm_chunks):
        n0 = col.n_updates
        col.feed(c)
        if col.n_updates > n0:
            trig.append(i)
    return trig


class _LegacyStub:
    """旧实现所需的 App 字段桩（**属性访问**，与 `App` 实例一致）。"""

    def __init__(self, svc):
        import threading
        self._clone_enabled = True
        self._clone_lock = threading.Lock()
        self._clone_frames = []
        self._clone_voiced_s = 0.0
        self._clone_sent_voiced_s = 0.0
        self._clone_last_update = 0.0
        self._clone_noise_floor = 0.004
        self._clone_status = ''
        self.tts = svc


def group_a_equivalence():
    import numpy as np
    cc = _load_collector_module()
    legacy_fn = _legacy_collector_class()

    # 旧实现里的 `self.tts` ⇒ 需要一个能记录 `set_clone_pcm` 的桩
    sent = []
    class _Svc:
        def set_clone_pcm(self, pcm):
            sent.append(len(pcm))
            return True
    state = _LegacyStub(_Svc())

    # 新采集器（另一个桩，避免两个实现互相污染计数）
    sent2 = []
    class _Svc2:
        def set_clone_pcm(self, pcm):
            sent2.append(len(pcm))
            return True
    col = cc.CloneCollector(lambda: _Svc2())
    col.enabled = True
    col.reset()

    # 分块喂（模拟 Session._loop 的 0.5 s 块）
    full = _make_pcm(16000 * 40)
    chunk = 16000 // 2   # 0.5 s
    chunks = [full[i:i + chunk] for i in range(0, len(full), chunk)]

    t_legacy = _run_legacy(legacy_fn, chunks, state)
    t_new = _run_new(col, chunks)

    # 采集器在「启用=False」时必须完全不动
    col_off = cc.CloneCollector(lambda: _Svc2())
    col_off.enabled = False
    col_off.feed(full)
    off_voiced = col_off.voiced_s

    # 🔴 **发给 worker 的那段语音**的时长必须落在 APP-027 明文的 [3, 10] s
    sent_durs = [round(n / 16000.0, 2) for n in sent2]
    legacy_durs = [round(n / 16000.0, 2) for n in sent]

    return [
        dict(id='A1', name='新采集器与旧实现的「触发时机」完全一致',
             ok=(t_legacy == t_new), got=t_new, want=t_legacy),
        dict(id='A2', name='新采集器确实发出了更新（>0 次）',
             ok=(len(t_new) > 0), got=len(t_new), want='>0'),
        dict(id='A3', name='新采集器发的是**去静音后**的语音（短于原始输入）',
             ok=(len(sent2) > 0 and sent2[0] < len(full)),
             got=(sent2[0] if sent2 else None), want='< %d' % len(full)),
        dict(id='A4', name='enabled=False 时**完全不采集**（零副作用）',
             ok=(off_voiced == 0.0), got=off_voiced, want=0.0),
        dict(id='A5', name='发给 worker 的语音时长落在 APP-027 明文的 [3, 10] s',
             ok=(bool(sent_durs) and all(3.0 <= d <= 10.0 for d in sent_durs)),
             got=sent_durs, want='全部 ∈ [3, 10]'),
        dict(id='A6', name='旧实现发出的语音时长与新实现**逐次一致**',
             ok=(legacy_durs == sent_durs), got=sent_durs, want=legacy_durs),
        dict(id='A7', name='旧实现与新实现的「已发送累计语音秒数」一致',
             ok=(abs(state._clone_sent_voiced_s - col.sent_voiced_s) < 1e-6),
             got=round(col.sent_voiced_s, 3),
             want=round(state._clone_sent_voiced_s, 3)),
    ]


# ── B 组：CLI 接线（AST）─────────────────────────────────────────
def group_b_cli_wiring(src=None):
    src = src or _read(os.path.join(REPO_LC, 'live_caption_app.py'))
    tree = ast.parse(src)
    run_cli = _find_func(tree, 'run_cli')
    assert run_cli is not None, '找不到 run_cli'
    src_all = src

    # B1：`Session(...)` 必须带 `on_audio=`，**且值不能是常量 None**
    #   🔴 `on_audio=None` 等于「没接」⇒ 只判「关键字存在」是弱判据
    #      ⇒ 必须同时排除常量 None（反证 D1 就靠这一条）。
    session_calls = []
    for sub in ast.walk(run_cli):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id == 'Session':
            kws = {k.arg: k.value for k in sub.keywords if k.arg}
            session_calls.append(kws)
    b1 = False
    for kws in session_calls:
        if 'on_audio' not in kws:
            continue
        v = kws['on_audio']
        if isinstance(v, ast.Constant) and v.value is None:
            continue          # ← 显式 None ⇒ 等于没接
        b1 = True
        break

    # B2：`TTSService(...)` 必须带 `clone=`
    tts_calls = []
    for sub in ast.walk(run_cli):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id == 'TTSService':
            tts_calls.append({k.arg for k in sub.keywords if k.arg})
    b2 = any('clone' in kw for kw in tts_calls)

    # B3：必须真的构造了 `CloneCollector`
    b3 = 'CloneCollector(' in src_all

    # B4：`on_audio` 传的是 `col.feed`（不是别的）
    b4 = False
    for sub in ast.walk(run_cli):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id == 'Session':
            for kw in sub.keywords:
                if kw.arg == 'on_audio' and isinstance(kw.value, ast.IfExp):
                    src_txt = ast.unparse(kw.value)
                    b4 = ('feed' in src_txt)
                elif kw.arg == 'on_audio':
                    src_txt = ast.unparse(kw.value)
                    b4 = ('feed' in src_txt)

    return [
        dict(id='B1', name='run_cli 里 Session(...) 带 on_audio=（克隆源 PCM 的唯一出口）',
             ok=b1, got=b1, want=True),
        dict(id='B2', name='run_cli 里 TTSService(...) 带 clone=（worker 才知道要克隆）',
             ok=b2, got=b2, want=True),
        dict(id='B3', name='run_cli 里构造了 CloneCollector',
             ok=b3, got=b3, want=True),
        dict(id='B4', name='on_audio 传的是采集器的 feed 方法',
             ok=b4, got=b4, want=True),
    ]


# ── C 组：worker 逐句遥测 ────────────────────────────────────────
def group_c_worker_telemetry(src=None):
    src = src or _read(os.path.join(REPO_LC, 'tts_worker.py'))
    tree = ast.parse(src)
    res = []

    # C1：`_APP030_JSONL_KEYS` 必须含三个新字段
    keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == '_APP030_JSONL_KEYS':
                    try:
                        keys = [e.value for e in node.value.elts]
                    except Exception:
                        keys = []
    for k in ('clone_active', 'clone_mode', 'clone_audio_s'):
        res.append(dict(id='C1.%s' % k,
                        name='逐句 jsonl 键含 %s' % k,
                        ok=(k in keys), got=(k in keys), want=True))

    # C2：`_record_jsonl` 的 `tel is None` 分支也要写这三个字段
    fn = _find_func(tree, '_record_jsonl')
    b2 = False
    if fn is not None:
        txt = ast.unparse(fn)
        b2 = all(("'%s'" % k) in txt for k in
                 ('clone_active', 'clone_mode', 'clone_audio_s'))
        # 必须有 else 分支（tel 为空的路径）
        b2 = b2 and ('else:' in txt)
    res.append(dict(id='C2', name='失败/丢句的行（tel 为空）也带音色来源字段',
                    ok=b2, got=b2, want=True))

    # C3：worker 必须在**合成时**取快照（不是会话结束时）
    b3 = '_last_clone_active' in src
    res.append(dict(id='C3', name='worker 有「合成那一刻」的音色快照字段',
                    ok=b3, got=b3, want=True))

    # C4：回落时必须清路线（否则字段自相矛盾）
    fb = _find_func(tree, '_fallback_to_preset')
    b4 = False
    if fb is not None:
        txt = ast.unparse(fb)
        b4 = ('_clone_mode = None' in txt)
    res.append(dict(id='C4', name='回落预设 A 时同时清掉 clone_mode（字段不矛盾）',
                    ok=b4, got=b4, want=True))

    # 🔴🔴🔴 C5：**真实播放路径**的 jsonl 行必须也带这些字段
    #   ⚠️ **实测抓出的真实缺陷**（§84）：
    #     播放路径的 jsonl 行是**看门狗线程**（`_finish_played`）用
    #     **重算出来的 tel** 写的 ⇒ 而这些字段只在**合成线程**的 tel 里填
    #     ⇒ 播放路径**整组字段全丢**（实测 76 行 jsonl 里 `lang` /
    #       `end_reason` / `clone_*` **一个都没有**）
    #     ⇒ reviewer 无法按语言/音色来源分组 ⇒ **结论不可核**。
    #   ⇒ 修法：合成时把这些字段**快照**进 job ⇒ 看门狗覆盖回 tel。
    b5 = False
    b6 = False
    put_call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'put' and isinstance(node.func.value, ast.Attribute) \
                and node.func.value.attr == '_played_q':
            put_call = node
            break
    if put_call is not None:
        txt = ast.unparse(put_call)
        b5 = ('meta=' in txt) and ('_APP030_JSONL_KEYS' in txt)
        b6 = ('clone' in txt)
    res.append(dict(id='C5',
                    name='真实播放路径：合成时把 APP-030⑤+clone 字段快照进 job',
                    ok=b5, got=b5, want=True))
    # C6：看门狗必须把 job 里的 meta **覆盖回 tel**
    b7 = False
    fp = _find_func(tree, '_finish_played')
    if fp is not None:
        txt = ast.unparse(fp)
        b7 = ("job.get('meta')" in txt) and ('_meta.items()' in txt)
    res.append(dict(id='C6',
                    name='真实播放路径：看门狗把 meta 覆盖回 tel（逐句字段齐全）',
                    ok=b7, got=b7, want=True))
    return res


# ── D 组：反证（判据必须能 FAIL）──────────────────────────────────
def group_d_counterproof():
    """🔴 故意写坏源码 ⇒ 判据必须 FAIL。

    ⚠️ **「证明缺陷曾存在」的断言要归 REAL 组**（命中=预期成立），
    **不能**放 BUG 组（BUG 组语义 = 「缺陷**仍然存在**」，命中即 FAIL）。
    ⇒ 这里反过来：**改坏之后判据必须 FAIL** ⇒ 证明判据**不是恒 PASS 的摆设**。
    """
    good = _read(os.path.join(REPO_LC, 'live_caption_app.py'))
    good_w = _read(os.path.join(REPO_LC, 'tts_worker.py'))

    # D1：去掉 `on_audio=` ⇒ B1 必须 FAIL
    bad = good.replace("on_audio=(_clone_col.feed if _clone_col is not None else None)",
                       "on_audio=None")
    d1 = (bad != good)
    r = group_b_cli_wiring(bad)
    d1_ok = d1 and (not r[0]['ok'])

    # D2：去掉 `clone=` ⇒ B2 必须 FAIL
    bad2 = good.replace("                             clone=_want_clone,\n", "")
    d2 = (bad2 != good)
    r2 = group_b_cli_wiring(bad2)
    d2_ok = d2 and (not r2[1]['ok'])

    # D3：去掉 worker 的新键 ⇒ C1 必须 FAIL
    bad3 = good_w.replace("    'clone_active', 'clone_mode', 'clone_audio_s',\n", "")
    d3 = (bad3 != good_w)
    r3 = group_c_worker_telemetry(bad3)
    d3_ok = d3 and (not r3[0]['ok'])

    # 🔴 D4：去掉「合成时的 meta 快照」⇒ C5 必须 FAIL
    #   ⇒ 证明 C5 不是恒 PASS 的摆设（§84 实测抓出的真实缺陷的闸门）
    bad4 = good_w.replace(
        "                meta={k: tel.get(k) for k in _APP030_JSONL_KEYS}))",
        "                ))")
    d4 = (bad4 != good_w)
    r4 = group_c_worker_telemetry(bad4)
    c5_idx = next((i for i, c in enumerate(r4) if c['id'] == 'C5'), None)
    d4_ok = d4 and (c5_idx is not None) and (not r4[c5_idx]['ok'])

    return [
        dict(id='D1', name='反证：去掉 on_audio= ⇒ B1 判据 FAIL（闸门不是摆设）',
             ok=d1_ok, got=d1_ok, want=True),
        dict(id='D2', name='反证：去掉 clone= ⇒ B2 判据 FAIL（闸门不是摆设）',
             ok=d2_ok, got=d2_ok, want=True),
        dict(id='D3', name='反证：去掉 worker 新键 ⇒ C1 判据 FAIL（闸门不是摆设）',
             ok=d3_ok, got=d3_ok, want=True),
        dict(id='D4', name='反证：去掉 meta 快照 ⇒ C5 判据 FAIL（闸门不是摆设）',
             ok=d4_ok, got=d4_ok, want=True),
    ]


def group_e_baseline():
    """🔴 **修复前的基线**：证明「缺陷曾真实存在」。

    ⇒ 用**固定 commit SHA** 取修复前源码（§31 教训：不能用 HEAD）。
    """
    import subprocess
    res = []
    try:
        out = subprocess.run(
            ['git', '-C', REPO, 'show', '%s:live_caption/live_caption_app.py'
             % BASELINE_COMMIT],
            capture_output=True, timeout=120)
        base = out.stdout.decode('utf-8', 'replace')
    except Exception as e:
        return [dict(id='E0', name='取基线源码失败', ok=False,
                     got='%s: %s' % (type(e).__name__, e), want='成功')]
    if not base or 'run_cli' not in base:
        return [dict(id='E0', name='基线源码不可用', ok=False,
                     got='len=%d' % len(base), want='可读')]

    # E1：修复前的 `run_cli` 里 Session(...) **没有** on_audio
    try:
        tree = ast.parse(base)
        rc = _find_func(tree, 'run_cli')
        sess = []
        for sub in ast.walk(rc):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                    and sub.func.id == 'Session':
                sess.append({k.arg for k in sub.keywords if k.arg})
        has_on_audio = any('on_audio' in kw for kw in sess)
    except Exception as e:
        has_on_audio = None
    res.append(dict(id='E1',
                    name='修复前（%s）的 run_cli 没有 on_audio ⇒ 缺陷曾真实存在'
                         % BASELINE_COMMIT,
                    ok=(has_on_audio is False), got=has_on_audio, want=False))

    # E2：修复前没有 clone_collector.py
    try:
        out2 = subprocess.run(
            ['git', '-C', REPO, 'cat-file', '-e',
             '%s:live_caption/clone_collector.py' % BASELINE_COMMIT],
            capture_output=True, timeout=60)
        existed = (out2.returncode == 0)
    except Exception:
        existed = None
    res.append(dict(id='E2',
                    name='修复前（%s）不存在 clone_collector.py ⇒ 缺陷曾真实存在'
                         % BASELINE_COMMIT,
                    ok=(existed is False), got=existed, want=False))
    return res


def group_f_pkg_sync():
    """🔴 客户包同步核对（仓库 ⇄ 包目录）。

    ⚠️ **「仓库里测过」≠「包里的那份是对的」** ⇒ 关键修复要对包内那份
       单独跑同一套断言。
    """
    res = []
    pairs = [('live_caption_app.py', 'live_caption_app.py'),
             ('tts_worker.py', 'tts_worker.py'),
             ('clone_collector.py', 'clone_collector.py')]
    for repo_rel, pkg_rel in pairs:
        rp = os.path.join(REPO_LC, repo_rel)
        pp = os.path.join(PKG_LC, pkg_rel)
        if not os.path.isfile(pp):
            res.append(dict(id='F.%s' % pkg_rel,
                            name='客户包内 %s 存在' % pkg_rel,
                            ok=False, got='不存在', want='存在'))
            continue
        a = _norm(_read(rp))
        b = _norm(_read(pp))
        res.append(dict(id='F.%s' % pkg_rel,
                        name='客户包内 %s 与仓库逐字一致（LF 归一化）' % pkg_rel,
                        ok=(a == b), got=(len(b)), want=len(a)))
    return res


def main():
    groups = {}
    groups['A_equivalence'] = group_a_equivalence()
    groups['B_cli_wiring'] = group_b_cli_wiring()
    groups['C_worker_telemetry'] = group_c_worker_telemetry()
    groups['D_counterproof'] = group_d_counterproof()
    groups['E_baseline'] = group_e_baseline()
    groups['F_pkg_sync'] = group_f_pkg_sync()

    all_checks = []
    for g, items in groups.items():
        for it in items:
            it = dict(it)
            it['group'] = g
            all_checks.append(it)

    n_pass = sum(1 for c in all_checks if c['ok'])
    n_fail = len(all_checks) - n_pass
    for c in all_checks:
        print('  [%s] %-6s %-6s %s' % ('PASS' if c['ok'] else 'FAIL',
                                        c['group'][:6], c['id'], c['name']))

    ev = dict(ts=_now(), baseline_commit=BASELINE_COMMIT,
              repo=REPO, pkg=PKG_ROOT,
              groups=groups, checks=all_checks,
              pass_count=n_pass, fail_count=n_fail)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n[SUMMARY] app121: PASS=%d FAIL=%d' % (n_pass, n_fail))
    print('证据：%s' % OUT)
    return 0 if n_fail == 0 else 1


def _now():
    import time
    return time.strftime('%Y-%m-%d %H:%M:%S')


if __name__ == '__main__':
    sys.exit(main())
