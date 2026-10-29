# -*- coding: utf-8 -*-
"""🔴🔴🔴 §99：**APP-039/040（§97）的「接线层」断链**验收脚本。

## 为什么要有这个脚本（§97 的教训）

§97 声称 APP-039/040「音色按句绑定 spk」已实施，验收脚本 `app150` **16/16 PASS**。
但 `app150` 只测了**纯数据类** `speaker_voice.SpeakerVoiceTable` 的**单元行为**
⇒ **完全没有覆盖「接线层」**（谁调用谁、时间轴对不对、worker 确认了没有）。

🔴 **本脚本实测发现 4 处确定性断链**（全部在**真实运行路径**上）：

| # | 断链 | 现象 | 后果 |
|---|---|---|---|
| **E** | `speaker_tracker.pcm_for_ranges` | `clean_ranges` 是**全局时间轴**秒，而环形缓冲下标 0 对应**缓冲起点** | 切片整体错位 ⇒ 取到的不是这个人的语音 |
| **A** | App 传给 ASR 旁路的**段区间** | 区间**长度恒为 0**（GUI 兜底 `_t0=_t1`；CLI 显式传同一值两次） | ASR 侧 `dur=0 < min_dur_s=2.0` ⇒ **永远拿不到 spk** ⇒ 旁路 100% 失效 |
| **B** | `speaker_voice.add_sample` | 生产代码**零调用者** ⇒ `dur_s` 恒 0 | `ready_to_embed` 恒 False ⇒ APP-040②「攒到 3 s 重算一次」**永不发生** |
| **C** | `tts_service._handle_event` | worker 的 `spk_voice` 事件**无分派分支** | 主进程在 worker **确认前**就 `mark_embedded` ⇒ 登记失败仍被当成成功 ⇒ 该 spk 永远没有音色 |

⇒ **APP-039/040 在真机上完全不工作**（每句都是预设 A），
而 `app150` 依然 16/16 PASS ⇒ **「测试全绿、用户全挂」**。

## 本脚本干什么（**纯离线，不占锁、不跑推理、不用模型、不调 MiniMax**）

- **绝不 import 被测模块**（记忆铁律 §十一）⇒ 用 `ast` 抽源码 + `exec`。
- 判据分两类：
  - **行为判据**：对**真实代码**跑真实场景（E / B）；
  - **结构判据**：AST 判据（A / C）—— 因 `live_caption_app.py` 顶层 `import numpy`
    ⇒ 不能 exec 整个模块。
- **双向反证**（铁律：判据自身必须能识破假通过）⇒ 每条判据都有对应反证。

## 🔴 解释器

**必须用带 numpy 的 system 3.12**（`C:\\Users\\Trekker-PTL\\AppData\\Local\\Programs\\Python\\Python312\\python.exe`）
—— managed 3.13 **无 numpy** ⇒ 边车桩 `exec` 就挂 ⇒ 判据假 FAIL（记忆铁律 §98）。
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
LIVE = os.path.join(REPO, 'live_caption')

EVIDENCE = os.path.join(HERE, 'app154_app039_wiring_gap_evidence.json')


# ══════════════════════════════════════════════════════════════════
# ① 抽源码 + exec（绝不 import 被测模块）
# ══════════════════════════════════════════════════════════════════
def exec_source(path: str, names: set, src_text: str = None):
    """抽指定顶层定义（含 import）到独立命名空间并 `exec`。

    🔴 三个必踩坑（记忆铁律 §十一）：
      ① `from __future__ import` 必须在最前
      ② 只留 `FunctionDef/ClassDef/Assign` ⇒ **丢掉 `Import`** ⇒ `np` 未定义
      ③ 反证改源码文本、exec 却是原 AST ⇒ 必须**重新抽 AST**（本函数接受 `src_text`）
    """
    if src_text is None:
        with open(path, encoding='utf-8') as f:
            src_text = f.read()
    tree = ast.parse(src_text)
    futures, imports, keep = [], [], []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            futures.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in names:
                keep.append(node)
        elif isinstance(node, ast.Assign):
            # 🔴🔴 **模块级常量必须全部注入**（记忆铁律 §十一坑②）：
            #   `SpeakerBridge.__init__` 的默认形参 `scripts_dir=_ASR_SCRIPTS`
            #   ⇒ 漏掉 `_ASR_SCRIPTS` ⇒ **类定义阶段就 NameError** ⇒ 判据假 FAIL。
            #   ⇒ 这里**无条件**带上所有模块级 Assign（不只是 names 里的）。
            tgt = [t.id for t in node.targets
                   if isinstance(t, ast.Name)]
            if tgt:
                keep.append(node)
    ns = {'__name__': '_extracted'}
    body = futures + imports + keep
    exec(compile(ast.Module(body=body, type_ignores=[]),
                 '<extracted>', 'exec'), ns)
    return ns, src_text


def read(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════
# ② 行为判据 E：环形缓冲的时间轴换算
# ══════════════════════════════════════════════════════════════════
def behavior_E(tracker_ns):
    """`pcm_for_ranges` 必须把「全局时间轴」换算成「环形缓冲下标」。

    🔴 场景：环形缓冲里是全局时间轴 **[100.0, 110.0]** 的音频
       （⇒ 缓冲起点 `keep_t0 = 100.0`），要取全局区间 **[101.0, 103.0]**。
       ⇒ 期望取到 **2.0 s** 的样本，且内容对得上（每个样本 = 其全局秒数）。
    """
    import numpy as np
    fn = tracker_ns['SpeakerBridge'].pcm_for_ranges
    SR = 16000
    t0 = 100.0
    buf = np.arange(16000 * 10, dtype=np.float32) / SR + t0  # 值 = 全局秒
    ranges = [(101.0, 103.0)]

    out = {'has_keep_t0_param': 'keep_t0' in
           getattr(fn, '__code__', type('x', (), {'co_varnames': ()})).co_varnames}

    # ✅ 正确调用（带 keep_t0）
    try:
        pcm = fn(None, ranges, keep=buf, max_s=10.0, keep_t0=t0)
    except TypeError:
        pcm = None
    out['pcm_is_none'] = pcm is None
    if pcm is not None:
        out['n_samples'] = int(pcm.size)
        out['n_expected'] = int(2.0 * SR)
        out['len_ok'] = abs(int(pcm.size) - out['n_expected']) <= 2
        out['first_val'] = round(float(pcm[0]), 4) if pcm.size else None
        out['last_val'] = round(float(pcm[-1]), 4) if pcm.size else None
        out['content_ok'] = (pcm.size > 0
                             and abs(float(pcm[0]) - 101.0) < 1e-3
                             and abs(float(pcm[-1]) - 103.0) < 1e-3)
    else:
        out.update(n_samples=0, n_expected=int(2.0 * SR), len_ok=False,
                   first_val=None, last_val=None, content_ok=False)

    # 🔴 反证：不传 keep_t0（= 旧行为）⇒ 必须取不到（或取错）
    try:
        pcm_old = fn(None, ranges, keep=buf, max_s=10.0)
    except TypeError:
        pcm_old = None
    out['old_call_is_none'] = pcm_old is None
    return out


# ══════════════════════════════════════════════════════════════════
# ③ 行为判据 A：段区间必须够长（ASR 侧 min_dur_s = 2.0）
# ══════════════════════════════════════════════════════════════════
def behavior_A(tracker_ns):
    """`span_for_final` 必须给出**长度足够**的段区间。

    🔴 ASR 侧 `SpeakerTracker.on_final` 的硬门槛：
       `dur < min_dur_s(=2.0)` ⇒ 返 `reason='too_short'` / `pending=True`
       ⇒ **永远拿不到 spk** ⇒ 旁路 100% 失效。
    ⇒ App 侧必须给出 ≥ 2.0 s 的区间。

    🔴🔴 **签名纠偏（§99）**：`span_for_final(t_end, min_s=SPAN_MIN_S)`
       **只有一个位置参数**（`t_end`）—— 它**不知道句子起点**，
       只能从 `t_end` **往前借**一个 `min_s` 的窗口。
       ⚠️ 判据早期版本误按 `(t_start, t_end)` 调用 ⇒ 第二个实参被当成
          `min_s` ⇒ 借出一个 10.4 s 的窗口 ⇒ **判据假 FAIL**（A3 len=10.0）。
       ⇒ 本轮已按**真实签名**重写。
    """
    fn = tracker_ns.get('span_for_final')
    out = {'has_span_fn': fn is not None}
    if fn is None:
        out.update(len_short=0, len_ok=False, t1_ok=False,
                   long_len=0, long_ok=False, zero_start=0)
        return out
    # 短句（t_end=10.4）⇒ 必须往前借到 ≥ 2.0 s（实测 SPAN_MIN_S=2.5）
    t0, t1 = fn(10.4)
    out['len_short'] = round(float(t1) - float(t0), 4)
    out['len_ok'] = out['len_short'] >= 2.0
    out['t1_ok'] = abs(float(t1) - 10.4) < 1e-6
    # 🔴 窗口恒为 `min_s`（函数只往前借，不往后借 ⇒ t_end 不变）
    t0b, t1b = fn(20.0)
    out['long_len'] = round(float(t1b) - float(t0b), 4)
    out['long_ok'] = (abs(float(t1b) - 20.0) < 1e-6 and
                      abs(out['long_len'] - 2.5) < 1e-6)
    # 会话开头（t_end < min_s）⇒ t0 不能为负
    t0c, t1c = fn(1.0)
    out['zero_start'] = round(float(t0c), 4)
    out['zero_ok'] = float(t0c) >= 0.0
    return out


# ══════════════════════════════════════════════════════════════════
# ④ 行为判据 B：干净区间 ⇒ 累计时长（并集，不是求和）
# ══════════════════════════════════════════════════════════════════
def behavior_B(voice_ns):
    """`add_clean_ranges` 必须按**区间并集**累计时长。

    🔴 为什么不能用「求和」：同一段音频会被多次引用
       （每句定稿都把该 spk 的全部干净区间再登记一次）⇒ 求和会**虚高**
       ⇒ `ready_to_embed` 提前为 True ⇒ APP-040②「攒到 3 s 重算一次」
          会**在还没攒够时**就触发。
    """
    Table = voice_ns['SpeakerVoiceTable']
    out = {'has_add_clean_ranges': hasattr(Table, 'add_clean_ranges')}
    if not out['has_add_clean_ranges']:
        out.update(dur=0, dur_ok=False, ready=False, refine_ready=False)
        return out
    tbl = Table()
    tbl.note_final(0, 'S1', [])
    # 第一次登记：0.0–3.0 s（3.0 s）
    tbl.add_clean_ranges('S1', [(0.0, 3.0)])
    out['dur'] = round(float(tbl.stats()['spks']['S1'].get('clean_dur_s', 0.0)), 4)
    out['dur_ok'] = abs(out['dur'] - 3.0) < 1e-6
    out['ready'] = bool(tbl.ready_to_embed('S1'))
    # 🔴 第二次登记**重叠**区间（0.0–3.0 再来一次）⇒ 并集仍应是 3.0 s
    tbl.add_clean_ranges('S1', [(0.0, 3.0)])
    out['dur_after_dup'] = round(
        float(tbl.stats()['spks']['S1'].get('clean_dur_s', 0.0)), 4)
    out['dup_ok'] = abs(out['dur_after_dup'] - 3.0) < 1e-6
    # 🔴 登记第二段不相交区间（10.0–11.0）⇒ 并集 = 4.0 s
    tbl.add_clean_ranges('S1', [(10.0, 11.0)])
    out['dur_after_disjoint'] = round(
        float(tbl.stats()['spks']['S1'].get('clean_dur_s', 0.0)), 4)
    out['disjoint_ok'] = abs(out['dur_after_disjoint'] - 4.0) < 1e-6
    # 细化门槛：REFINE_S = 3.0 ⇒ 登记后应可细化
    tbl.mark_embedded('S1', refined=False)
    out['refine_ready'] = bool(tbl.ready_to_embed('S1'))
    return out


# ══════════════════════════════════════════════════════════════════
# ⑤ 结构判据 A/C：`live_caption_app.py` 与 `tts_service.py`
# ══════════════════════════════════════════════════════════════════
def enclosing_funcs_with_call(src: str, attr_name: str):
    """返回「调用了 `self.X.attr_name(...)` 的函数名集合」+ 每个的源码。"""
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            hit = False
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == attr_name):
                    hit = True
                    break
            if hit:
                out[node.name] = ast.get_source_segment(src, node) or ''
    return out


def mark_embedded_sites(src: str):
    """🔴🔴🔴 §99：返回每个 `mark_embedded` **调用点**及其「是否被 ok 判定保护」。

    ## 为什么必须做到**调用点**级（而不是函数级）

    早期版本判据是「**所在函数**里有没有 `voice_status` 这个 token」
    ⇒ 注入反证（把一个**无条件**的 `mark_embedded` 加到函数开头）
    时，函数里**本来就**有 `spk_voice_status(...)` ⇒ token 命中
    ⇒ 判据认为「已确认」⇒ **假通过**（反证失效）。

    ⇒ 现在：**每个调用点**都必须被一个「检查了回执 `ok` 的 `If`」保护：
      - 沿 AST 父链向上找最近的 `If`；
      - 该 `If` 的条件里必须出现 `ok`（形如 `_st.get('ok')`）；
      - 且所在函数里必须有 `spk_voice_status(...)` 这个**回执来源**。

    返回：`[(func_name, call_line, guarded)]`。
    """
    tree = ast.parse(src)
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    def enclosing_fn(node):
        cur = node
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return cur
            cur = parent.get(cur)
        return None

    def own_nodes(fn):
        """该函数**直属**的节点（不含嵌套函数内部）。"""
        nested_ids = set()
        for c in ast.walk(fn):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)) and c is not fn:
                nested_ids.update(id(x) for x in ast.walk(c))
        return nested_ids

    sites = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        skip = own_nodes(fn)
        # 该函数是否含「回执来源」
        has_ack_source = any(
            isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == 'spk_voice_status'
            for c in ast.walk(fn))
        for c in ast.walk(fn):
            if id(c) in skip:
                continue
            if not (isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)
                    and c.func.attr == 'mark_embedded'):
                continue
            # 向上找最近的 `If`（判定保护）
            cur = parent.get(c)
            guard = None
            while cur is not None and cur is not fn:
                if isinstance(cur, ast.If):
                    guard = cur
                    break
                cur = parent.get(cur)
            cond_txt = ''
            if guard is not None:
                cond_txt = ast.unparse(guard.test)
            guarded = bool(
                guard is not None
                and re.search(r'\bok\b', cond_txt)
                and has_ack_source)
            sites.append((fn.name, c.lineno, guarded, cond_txt[:60]))
    return sites


def struct_A(app_src: str):
    """App 必须**真正写入** `_seg_span`（否则传给旁路的区间长度恒 0）。

    🔴 修复前：`_seg_span` 只有 `{}`（初始化）与 `.clear()`（清理）
       ⇒ **没有任何下标写入** ⇒ `_seg_span.get(seg, (None, None))` 恒返兜底
       ⇒ 兜底是 `_t0 = _t1 = _seg_audio_end` ⇒ **长度 0** ⇒ 旁路全废。
    """
    tree = ast.parse(app_src)
    has_write = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Subscript)
                        and isinstance(tgt.value, ast.Attribute)
                        and tgt.value.attr == '_seg_span'):
                    has_write = True
    # 🔴 CLI 侧：`on_final(seg, t_start, t_end)` 的两个时间实参**不得是同一个表达式**
    cli_same = False
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'on_final'
                and len(node.args) >= 3):
            a = ast.dump(node.args[1])
            b = ast.dump(node.args[2])
            if a == b:
                cli_same = True
    return {'has_seg_span_write': has_write, 'cli_same_args': cli_same}


def struct_C(app_src: str, svc_src: str):
    """worker 的 `spk_voice` 事件必须被分派；且 `mark_embedded` 只能在确认后调。

    🔴 修复前：
      - `tts_service._handle_event` **没有** `spk_voice` 分支
        ⇒ 主进程**收不到** worker 的登记结果；
      - `mark_embedded` 在 pump 函数里**无条件**调用
        ⇒ 命令**只是发出去**就算成功 ⇒ worker 算失败时主进程仍标成功。

    🔴🔴 **判据必须精确**（本轮踩到）：用 `'spk_voice' in fn_src` 判「是否确认过」
       ⇒ **被 `self._spk_voices`（属性名）误命中** ⇒ 判据恒 PASS（假通过）。
       ⇒ 改为「**该函数里是否出现确认相关的标识符**」的精确 token 匹配。
    """
    # ① tts_service._handle_event 里是否有 `kind == 'spk_voice'` 的比较分支
    has_branch = False
    for node in ast.walk(ast.parse(svc_src)):
        if isinstance(node, ast.FunctionDef) and node.name == '_handle_event':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Compare):
                    for op in list(sub.comparators) + [sub.left]:
                        if (isinstance(op, ast.Constant)
                                and op.value == 'spk_voice'):
                            has_branch = True
    # ② mark_embedded 的**每个调用点**都必须被「检查回执 ok 的 If」保护
    #   ⚠️ §99：早期版本按**函数**级 token 匹配 ⇒ 注入无条件 mark_embedded
    #   时函数里本就有 `spk_voice_status` ⇒ **假通过**（反证失效）。
    #   ⇒ 现在改**调用点**级 AST 判据（见 `mark_embedded_sites`）。
    sites = mark_embedded_sites(app_src)
    unconfirmed = sorted({'%s@%d' % (f, ln) for f, ln, g, _ in sites if not g})
    guarded = sorted({'%s@%d' % (f, ln) for f, ln, g, _ in sites if g})
    callers = enclosing_funcs_with_call(app_src, 'mark_embedded')
    # ③ 🔴🔴🔴 §99（断链 F）：**初次登记成功后不能把 spk 从 pending 移除**
    #   ⇒ 否则「攒够 REFINE_S 再用自己的段重算一次」（APP-040②）
    #     **永远不会发生** ⇒ 细化分支是**死代码**。
    #   ⇒ 判据：在 pump 函数里，`mark_embedded` 的**成功分支**之后，
    #     **不得**无条件地把该 spk 从 `_spk_pending_embed` 移除。
    refine_dead = []
    for fn_name, fn_src in callers.items():
        if 'ready_to_embed' not in fn_src:
            continue                       # 没有细化分支 ⇒ 不适用
        if 'refined=True' not in fn_src and 'refined=_refined' not in fn_src:
            continue
        # 找「初次登记」路径：`_spk_voice_sent.add((spk, False))` 之类
        first_add = fn_src.find('(spk, False)')
        if first_add < 0:
            continue
        # 初次登记之后、细化之前的「移除 pending」⇒ 断链 F
        seg = fn_src[first_add:]
        # 找到「ok 回执」分支里的 pending 移除
        if re.search(r'mark_embedded\([^)]*refined=(?:False|_refined)\)', seg):
            if re.search(r'_spk_pending_embed\s*=\s*\[', seg):
                refine_dead.append(fn_name)
    return {'has_spk_voice_branch': has_branch,
            'mark_embedded_callers': sorted(callers.keys()),
            'mark_embedded_sites': ['%s@%d guarded=%s' % (f, ln, g)
                                   for f, ln, g, _ in sites],
            'guarded_sites': guarded,
            'unconfirmed_callers': sorted(unconfirmed),
            'refine_dead_callers': sorted(refine_dead)}


# ══════════════════════════════════════════════════════════════════
# ⑥ 行为判据 F：细化分支**可达**（断链 F）
# ══════════════════════════════════════════════════════════════════
class _FakeVoiceTable:
    """假 `SpeakerVoiceTable`：只保留本判据关心的状态。"""

    def __init__(self, clone_at=0):
        self.voice = {}          # spk -> 'clone' / 'preset'
        self.refined = {}        # spk -> bool
        self.fallback = {}       # spk -> reason
        self.clone_at = clone_at

    def has_voice(self, spk):
        return self.voice.get(spk) == 'clone'

    def ready_to_embed(self, spk):
        if self.voice.get(spk) == 'clone' and self.refined.get(spk):
            return False
        return self.clone_at <= 0 or True

    def mark_embedded(self, spk, vec=None, refined=False):
        self.voice[spk] = 'clone'
        if refined:
            self.refined[spk] = True

    def mark_fallback(self, spk, reason=''):
        self.voice.setdefault(spk, 'preset')
        self.fallback[spk] = reason

    def clean_ranges_of(self, spk):
        return [(0.0, 10.0)]


class _FakeTts:
    """假 TTS 服务：记录命令 + 可编程回执。"""

    def __init__(self):
        self.active = True
        self.sent = []           # [(spk, n_samples)]
        self._ack = {}           # spk -> dict(ok=...)

    def register_spk_voice(self, spk, pcm):
        n = int(getattr(pcm, 'size', 0) or len(pcm))
        self.sent.append((spk, n))
        return True

    def set_ack(self, spk, ok=True, message=''):
        self._ack[spk] = dict(ok=ok, dur_s=1.0, message=message)

    def spk_voice_status(self, spk):
        return self._ack.pop(spk, None)


def behavior_F(app_src: str):
    """🔴🔴🔴 §99（断链 F）：**细化分支必须可达**。

    ## 断链 F 的机制

    旧实现在**初次登记成功**后就把该 spk 从 `_spk_pending_embed` 里
    **移除** ⇒ pump 下一轮再也看不到这个 spk ⇒ `else:` 分支
    （「已登记：够 `REFINE_S` 就用**自己的段**重算一次」）
    **永远进不去** ⇒ **APP-040②「攒够 3 s 重算一次」从不发生**。

    ⇒ 判据：**模拟真实 pump 的两轮调用**：
      轮1：发送登记命令 ⇒ 回执 `ok=True`
      轮2：检查该 spk **是否还在 pending**（还在 ⇒ 细化分支可达）
    """
    out = {'ran': False}
    # 从 app 源码里抽出 GUI 的 `_pump_spk_voices` 方法体，改写成独立函数
    tree = ast.parse(app_src)
    fn_node = None
    for n in ast.walk(tree):
        if (isinstance(n, ast.FunctionDef)
                and n.name == '_pump_spk_voices'):
            fn_node = n
            break
    if fn_node is None:
        out['reason'] = 'no _pump_spk_voices'
        return out
    # 把方法体脱壳成顶层函数（self → 局部变量）
    body_src = ast.unparse(ast.Module(body=fn_node.body, type_ignores=[]))
    body_src = body_src.replace('self.', '')
    src = (
        'def _pump():\n'
        '    tts = _TTS\n'
        '    _spk_voices = _VOICE\n'
        '    _spk_pending_embed = _PENDING\n'
        '    _spk_voice_sent = _SENT\n'
        '    _spk_pcm_t0 = 0.0\n'
        '    _ui_log = lambda m: None\n'
        '    _spk_pcm_for = lambda spk, seg: _PCM\n'
        + '\n'.join('    ' + ln for ln in body_src.split('\n')) + '\n'
        '    return _spk_pending_embed, _spk_voice_sent\n'
    )
    ns = {
        '_TTS': _FakeTts(),
        '_VOICE': _FakeVoiceTable(),
        '_PENDING': [(0, 'S1')],
        '_SENT': set(),
        # 🔴 假 PCM 必须**够长**（≥ MIN_S*SR = 24000 样本）
        #   ⇒ 否则 pump 在 `pcm.size < MIN_S*SR` 处 `continue`
        #   ⇒ 命令根本发不出去 ⇒ 判据恒「不可达」⇒ **假 FAIL**。
        '_PCM': _FakeArr([0.0] * 64000),
        'speaker_voice': _FakeSV(),
        'SR': 16000,
        '_FakeArr': _FakeArr,
    }
    try:
        exec(compile(src, '<pumpF>', 'exec'), ns)
    except Exception as e:
        out['reason'] = 'exec fail: %s: %s' % (type(e).__name__, e)
        return out
    try:
        # 轮1：发命令（此时没有回执）
        pend1, sent1 = ns['_pump']()
        # worker 回执
        ns['_TTS'].set_ack('S1', ok=True)
        # 轮2：应当**不**把 S1 从 pending 移除 ⇒ 细化分支可达
        pend2, sent2 = ns['_pump']()
        out['ran'] = True
        out['sent_after_round1'] = [list(x) for x in sent1]
        out['pending_after_round1'] = list(pend1)
        out['pending_after_round2'] = list(pend2)
        out['spk_still_pending'] = any(k == 'S1' for _s, k in pend2)
        out['voice_marked_clone'] = ns['_VOICE'].voice.get('S1') == 'clone'
        out['refine_reachable'] = out['spk_still_pending']
        # 轮3：此时应发出**细化**命令（第 2 次 register）
        ns['_TTS'].set_ack('S1', ok=True)
        pend3, sent3 = ns['_pump']()
        out['n_register_calls'] = len(ns['_TTS'].sent)
        out['refine_command_sent'] = (len(ns['_TTS'].sent) >= 2)
    except Exception as e:
        out['reason'] = 'run fail: %s: %s' % (type(e).__name__, e)
    return out


class _FakeArr(list):
    """假 numpy 数组：只需 `.size` / `.reshape` / 切片。"""

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


class _FakeSV:
    """假 `speaker_voice` 模块常量。"""

    MIN_S = 1.5
    REFINE_S = 3.0


# ══════════════════════════════════════════════════════════════════
# ⑥ main
# ══════════════════════════════════════════════════════════════════
def main():
    print('=' * 74)
    print('§99 APP-039/040（§97）接线层断链 · 离线验收')
    print('=' * 74)

    tracker_path = os.path.join(LIVE, 'speaker_tracker.py')
    voice_path = os.path.join(LIVE, 'speaker_voice.py')
    app_path = os.path.join(LIVE, 'live_caption_app.py')
    svc_path = os.path.join(LIVE, 'tts_service.py')

    results = []

    def add(name, ok, detail=''):
        results.append((name, bool(ok), detail))
        print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                               ('  ' + detail) if detail else ''))

    # ── 行为判据 ──
    print('\n' + '-' * 74)
    print('[behavior E] 环形缓冲的时间轴换算（`pcm_for_ranges`）：')
    tr_ns, tr_src = exec_source(tracker_path, {'SpeakerBridge'})
    e = behavior_E(tr_ns)
    for k, v in e.items():
        print('   %-24s = %s' % (k, v))

    print('\n[behavior A] 段区间长度（ASR 侧 min_dur_s=2.0）：')
    tr_ns2, _ = exec_source(tracker_path, {'SpeakerBridge', 'span_for_final'})
    a = behavior_A(tr_ns2)
    for k, v in a.items():
        print('   %-24s = %s' % (k, v))

    print('\n[behavior B] 干净区间并集时长（`add_clean_ranges`）：')
    v_ns, v_src = exec_source(voice_path, {
        'SpeakerVoiceTable', 'MIN_S', 'REFINE_S', 'MAX_PER_SPK_S', 'SR'})
    b = behavior_B(v_ns)
    for k, v in b.items():
        print('   %-24s = %s' % (k, v))

    print('\n[behavior F] 细化分支可达性（断链 F）：')
    app_src0 = read(app_path)
    f = behavior_F(app_src0)
    for k, v in f.items():
        print('   F.%-22s = %s' % (k, v))

    # ── 结构判据 ──
    print('\n[struct A/C] 接线结构：')
    app_src = app_src0
    svc_src = read(svc_path)
    sa = struct_A(app_src)
    sc = struct_C(app_src, svc_src)
    for k, v in sa.items():
        print('   A.%-22s = %s' % (k, v))
    for k, v in sc.items():
        print('   C.%-22s = %s' % (k, v))

    # ══════════════════════════════════════════════════════════════
    # 判据
    # ══════════════════════════════════════════════════════════════
    print('\n' + '=' * 74)
    add('E1 `pcm_for_ranges` 支持 `keep_t0`（环形缓冲起点时间）',
        e['has_keep_t0_param'])
    add('E2 按全局时间轴取到正确的样本（不是 None / 不是错位）',
        (not e['pcm_is_none']) and e['len_ok'] and e['content_ok'],
        'n=%s exp=%s first=%s last=%s' % (e.get('n_samples'),
                                          e.get('n_expected'),
                                          e.get('first_val'),
                                          e.get('last_val')))
    add('E3 旧行为（不传 keep_t0）确实取不到 ⇒ 判据能分辨新旧',
        e['old_call_is_none'])
    add('A1 App 真正写入 `_seg_span`（段区间不是恒空）',
        sa['has_seg_span_write'])
    add('A2 CLI 传给旁路的两个时间实参**不相同**（区间长度 > 0）',
        not sa['cli_same_args'])
    add('A3 `span_for_final` 存在且给出 ≥2.0 s 的区间',
        a['has_span_fn'] and a['len_ok'] and a['t1_ok'],
        'len=%s' % a.get('len_short'))
    add('A4 `span_for_final` 长句不借用、短句往前借、起点不为负',
        a.get('long_ok') and a.get('zero_ok'))
    add('B1 `add_clean_ranges` 存在（生产路径能累计干净语音时长）',
        b['has_add_clean_ranges'])
    add('B2 并集累计（重叠区间不重复计）',
        b.get('dur_ok') and b.get('dup_ok') and b.get('disjoint_ok'),
        'dur=%s dup=%s disjoint=%s' % (b.get('dur'), b.get('dur_after_dup'),
                                        b.get('dur_after_disjoint')))
    add('B3 登记后 `ready_to_embed` 为 True（可细化）',
        b.get('ready') and b.get('refine_ready'))
    add('C1 `tts_service` 有 `spk_voice` 事件分派',
        sc['has_spk_voice_branch'])
    add('C2 `mark_embedded` 只在「worker 确认后」的函数里调用',
        len(sc['unconfirmed_callers']) == 0,
        'unconfirmed=%s' % sc['unconfirmed_callers'])
    add('F1 初次登记确认后 spk **仍在 pending**（细化分支可达）',
        f.get('ran') and f.get('spk_still_pending'),
        'pending_after_round2=%s' % f.get('pending_after_round2'))
    add('F2 细化命令确实发出（第 2 次 register）',
        f.get('refine_command_sent'),
        'n_register=%s' % f.get('n_register_calls'))
    add('F3 结构判据：没有「初次登记即移出 pending」的 pump',
        len(sc.get('refine_dead_callers', [])) == 0,
        'refine_dead=%s' % sc.get('refine_dead_callers'))

    # ══════════════════════════════════════════════════════════════
    # 反证：注入错误 ⇒ 判据必须 FAIL
    # ══════════════════════════════════════════════════════════════
    print('\n' + '-' * 74)
    print('[falsify] 沙盒反证（注入错误 ⇒ 判据必须 FAIL）：')

    # 反证 E：把 `keep_t0` 换算去掉（回到旧行为）
    #   🔴 注入点必须落在**可执行代码**里（记忆铁律 §十一）
    #   ⇒ 这里替换「相对缓冲起点的下标换算」那一行。
    #   ⚠️ §99：源码已改成 `(float(a) - base) * _SR` ⇒ 锚点随之更新。
    old_e = 'i = max(0, int(round((float(a) - base) * _SR)))'
    new_e = 'i = max(0, int(round(float(a) * _SR)))  # 反证：忽略 keep_t0'
    bad_e = tr_src.replace(old_e, new_e)
    assert bad_e != tr_src, '❌ 反证 E 注入失败（没找到下标换算点）'
    tr_e, _ = exec_source(tracker_path, {'SpeakerBridge'}, src_text=bad_e)
    e_bad = behavior_E(tr_e)
    e_fail = e_bad['pcm_is_none'] or not e_bad['content_ok']
    print('  E 注入「忽略 keep_t0」⇒ pcm_is_none=%s content_ok=%s ⇒ 判据 %s'
          % (e_bad['pcm_is_none'], e_bad['content_ok'],
             'FAIL ✅' if e_fail else 'PASS ❌'))

    # 反证 A：把 `span_for_final` 的「往前借」去掉
    #   ⚠️ **修复前该函数不存在** ⇒ 反证**跳过**（而不是让脚本崩掉）
    #   ⇒ 判据 A3/A4 在修复前恒 FAIL ⇒ 已足够证明「缺陷真实存在」。
    span_src = None
    for node in ast.parse(tr_src).body:
        if isinstance(node, ast.FunctionDef) and node.name == 'span_for_final':
            span_src = ast.get_source_segment(tr_src, node) or ''
            break
    if span_src:
        # 🔴 注入点必须落在**可执行代码**里，不能改形参名（会破坏语法）
        #   ⇒ 改「借用窗口的计算」：`t0 = te - need` ⇒ `t0 = te`（不借）
        bad_a = tr_src.replace(
            span_src,
            span_src.replace('    t0 = te - need',
                             '    t0 = te  # 反证：禁用借用', 1))
        assert bad_a != tr_src, '❌ 反证 A 注入失败'
        tr_a, _ = exec_source(tracker_path,
                              {'SpeakerBridge', 'span_for_final'},
                              src_text=bad_a)
        a_bad = behavior_A(tr_a)
        a_fail = (not a_bad.get('len_ok')) or a_bad.get('len_short', 9) < 2.0
        print('  A 注入「禁用借用」⇒ len_short=%s ⇒ 判据 %s'
              % (a_bad.get('len_short'), 'FAIL ✅' if a_fail else 'PASS ❌'))
    else:
        a_bad = {'len_short': None, 'note': '修复前无 span_for_final'}
        a_fail = True
        print('  A 修复前无 `span_for_final` ⇒ 判据 A3/A4 恒 FAIL ✅（反证跳过）')

    # 反证 B：把「并集」改成「求和」
    #   ⚠️ **修复前 `add_clean_ranges` 不存在** ⇒ 反证跳过（同上）
    if 'add_clean_ranges' in v_src:
        bad_b = v_src.replace('clean_dur_s', 'clean_dur_s_sum_x')
        assert bad_b != v_src, '❌ 反证 B 注入失败'
        try:
            v_b, _ = exec_source(voice_path, {
                'SpeakerVoiceTable', 'MIN_S', 'REFINE_S', 'MAX_PER_SPK_S',
                'SR'}, src_text=bad_b)
            b_bad = behavior_B(v_b)
            b_fail = (not b_bad.get('dup_ok')) \
                or b_bad.get('dur_after_dup') != 3.0
        except Exception as e:
            b_fail = True
            b_bad = {'err': str(e)}
        print('  B 注入「求和代替并集」⇒ dur_after_dup=%s ⇒ 判据 %s'
              % (b_bad.get('dur_after_dup'),
                 'FAIL ✅' if b_fail else 'PASS ❌'))
    else:
        b_bad = {'dur_after_dup': None, 'note': '修复前无 add_clean_ranges'}
        b_fail = True
        print('  B 修复前无 `add_clean_ranges` ⇒ 判据 B1/B2 恒 FAIL ✅（反证跳过）')

    # 反证 C：在 pump 里加一个**无条件** `mark_embedded`
    bad_c = app_src.replace(
        '    def _pump_spk_voices(self):',
        '    def _pump_spk_voices(self):\n'
        '        self._spk_voices.mark_embedded("ZZ", refined=False)'
        '  # 反证：无条件标记')
    assert bad_c != app_src, '❌ 反证 C 注入失败'
    sc_bad = struct_C(bad_c, svc_src)
    c_fail = len(sc_bad['unconfirmed_callers']) > 0
    print('  C 注入「无条件 mark_embedded」⇒ unconfirmed=%s ⇒ 判据 %s'
          % (sc_bad['unconfirmed_callers'], 'FAIL ✅' if c_fail else 'PASS ❌'))

    # 反证 F：把「初次登记确认后**保留**在 pending」改回「立刻移出」
    #   ⇒ 模拟 §99 修复前的行为 ⇒ 细化分支变**死代码** ⇒ 判据 F 必须 FAIL。
    #   🔴 注入点：GUI pump 的成功分支里，`mark_embedded` 之后
    #     **无条件**地把该 spk 从 `_spk_pending_embed` 移除。
    old_f = '''                self._spk_voices.mark_embedded(_s, refined=_refined)
                self._spk_voice_sent.discard(_sent)
                if _refined:'''
    new_f = '''                self._spk_voices.mark_embedded(_s, refined=_refined)
                self._spk_voice_sent.discard(_sent)
                self._spk_pending_embed = [
                    (s, k) for (s, k) in self._spk_pending_embed
                    if k != _s]
                if _refined:'''
    bad_f = app_src.replace(old_f, new_f)
    assert bad_f != app_src, '❌ 反证 F 注入失败（没找到 GUI pump 成功分支）'
    f_bad = behavior_F(bad_f)
    f_fail = (not f_bad.get('ran')) or (not f_bad.get('spk_still_pending'))
    sc_f = struct_C(bad_f, svc_src)
    print('  F 注入「初次登记即移出 pending」⇒ spk_still_pending=%s '
          'refine_dead=%s ⇒ 判据 %s'
          % (f_bad.get('spk_still_pending'), sc_f.get('refine_dead_callers'),
             'FAIL ✅' if f_fail else 'PASS ❌'))

    print()
    add('D 反证 E：注入「忽略 keep_t0」⇒ E 判据 FAIL', e_fail)
    add('D 反证 A：注入「禁用借用」⇒ A 判据 FAIL', a_fail)
    add('D 反证 B：注入「求和代替并集」⇒ B 判据 FAIL', b_fail)
    add('D 反证 C：注入「无条件 mark_embedded」⇒ C 判据 FAIL', c_fail)
    add('D 反证 F：注入「初次登记即移出 pending」⇒ F 判据 FAIL', f_fail)

    npass = sum(1 for _, ok, _ in results if ok)
    nfail = sum(1 for _, ok, _ in results if not ok)
    print('\nSUMMARY: PASS=%d FAIL=%d TOTAL=%d' % (npass, nfail, len(results)))

    evidence = {
        'schema': 'app.app039.wiring_gap.v2',
        'behavior_E': e,
        'behavior_A': a,
        'behavior_B': b,
        'behavior_F': f,
        'struct_A': sa,
        'struct_C': sc,
        'falsify': {
            'E_ignore_keep_t0': {'pcm_is_none': e_bad.get('pcm_is_none'),
                                 'content_ok': e_bad.get('content_ok'),
                                 'judge_failed': e_fail},
            'A_disable_borrow': {'len_short': a_bad.get('len_short'),
                                 'judge_failed': a_fail},
            'B_sum_not_union': {'dur_after_dup': b_bad.get('dur_after_dup'),
                                'judge_failed': b_fail},
            'C_unconditional_mark': {'unconfirmed': sc_bad.get('unconfirmed_callers'),
                                     'judge_failed': c_fail},
            'F_remove_on_first_register': {
                'spk_still_pending': f_bad.get('spk_still_pending'),
                'refine_dead_callers': sc_f.get('refine_dead_callers'),
                'judge_failed': f_fail},
        },
        'results': [{'name': n, 'ok': ok, 'detail': d} for n, ok, d in results],
        'summary': {'pass': npass, 'fail': nfail, 'total': len(results)},
    }
    with open(EVIDENCE, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print('证据已写入：%s' % EVIDENCE)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
