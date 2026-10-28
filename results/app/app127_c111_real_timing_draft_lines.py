#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app127 —— 补齐 MT notice 15 §3.4 的「真实时序下不残留草稿行」端到端证据。

====================================================================
🔴 为什么需要这个脚本（背景）
====================================================================
MT 通知 15（`shared/NOTICE_mt_to_app_20261027_notice15.md`）§3.4 结论：

  ⚠️ **仍缺端到端实跑证据**（§75.2 的「真实时序下不残留草稿行」）——
  本轮是**纯离线纯函数**验证、不依赖任何时序采样 ⇒ **该验收项仍待 App 侧
  在真实时序下补跑**（建议下次跑批附带「草稿行计数」，正式稿到达后
  `n_draft_lines` 应归零）。

⇒ **本脚本就是那份「下次跑批」的附件**。

====================================================================
🔴🔴 为什么 MT 侧的离线验收（46/46）**不足以**证明这一点
====================================================================
MT 侧验的是**纯函数契约**：`submit()` / `flush()` 的 `_used_uids` 护栏、
事件 5 元组、守恒逻辑。

但「草稿行归零」是**渲染层 + 事件流**的**联合**性质，需要三件事同时成立：
  ① **translator 侧**：草稿与正式稿**共用同一个单元 id**
     （`C:<起始段>:<序号>`）—— MT 侧验了；
  ② **App 事件消费侧**：outbox 的 `draft` 事件必须**真的到达**消费者，
     且消费者**按同一个 id** 存下译文（`ev['id']` ↔ 单元的 `unit_id`）
     —— ⚠️ 这一段 MT 侧**验不到**；
  ③ **渲染层侧**：`render_lines()` 必须用**同一个 id** 把草稿行**原地替换**成
     正式稿行，且**不残留** `kind=='mt_draft'` 的行。

⇒ 本脚本把 ①②③ **串成一条真实的时序链**：
   真实 `TranslationService`（真队列 + 真工作线程 + 真锁 + 真 outbox）
   → 真实 `App._pump_tts` 式的 outbox 消费
   → 真实 `caption_render.render_lines()`。

====================================================================
🔴🔴 关键：**真实时序**怎么来的
====================================================================
**不用「假的时间」**：真 `TranslationService` 的工作线程**真的按顺序**从
`queue.Queue` 取 job、真的把结果写进 `svc.done` / `svc.outbox`。
本脚本用**桩翻译器**（`StubTranslator`）顶替 `HunyuanTranslator`：
  · 它有**可控的延迟** ⇒ 能制造「草稿先到、正式稿后到」的真实时序；
  · 它**不加载任何模型** ⇒ **不跑推理、不占 GPU/NPU、不取机器锁**；
  · 🔴 **每次调用产出唯一译文**（附调用序号）⇒ 否则「草稿译文」与
    「正式稿译文」文本相同 ⇒ 「草稿是否单独残留」这条判据**测不出来**
    （本轮首跑就踩到了：首版桩译文 = `'译文:' + src` ⇒ 草稿与正式稿
    同文 ⇒ R5 假 FAIL）。

真实性的来源是**真实线程 + 真实队列 + 真实锁 + 真实事件顺序**，
**不是**「把结果直接塞进 outbox」。

====================================================================
🔴🔴 本脚本验的是**完整生命周期**，不是只看终态
====================================================================
每次 `submit()` 之后**立刻**取一次快照（**不等队列排空**）⇒ 拿到
「草稿已到、正式稿还没到」的**中间态**。于是能同时验：
  · **中间态**：草稿行**必须可见且有译文**（否则用户看到「有原文、没译文」）；
  · **终态**：草稿行**必须归零**（正式稿原地替换它）。

只验终态会漏掉「草稿**从来没显示过**」这类缺陷 —— 那同样是坏的。

====================================================================
验收项
====================================================================
REAL 组（期望成立）：
  R1  真实时序跑完后**正式稿全部就绪**（`done` 覆盖所有 final 单元）
  R2  **终态 `n_draft_lines == 0`**（★ notice 15 §3.4 要的那一格）
  R3  **原文守恒**：渲染出的 `src` 行拼接 == 提交的原文拼接
  R4  **正式稿译文守恒**：每个 final 单元的译文都出现在渲染结果里
      （不丢、不重；**忽略** `…` 承接前缀 —— 那是**已文档化**的渲染规则）
  R5  **草稿译文不单独残留**：终态里任何草稿译文都不单独出现
  R6  **同 id 替换**：每个草稿 `unit_id` 恰有一条正式单元
  R7  **事件层守恒**：`final` 事件的 `src` 拼接 == 提交的原文拼接
  R8  **中间态草稿可见且有译文**
  R9  **中间态不丢已就绪的正式稿**（§47 的老坑：提前剔除 ⇒ 译文整轮消失）
  R10 **全程没有 `text=None` 的行**（GUI 拼接 `'〔译〕' + text` 会崩）

BUG 组（期望**不**命中 ⇒ 若命中说明缺陷仍存在）：
  B1  同一 `unit_id` 不得出现在**两条**正式单元里
  B2  正式稿**还在途**时 ⇒ 草稿行照常显示、正式稿**不被提前剔除**
  B3  渲染层**不得**把「已就绪的正式稿」既放进草稿行**又**放进段聚合

反证组（期望**命中** ⇒ 证明判据确实能抓出缺陷；**不是** PASS 项）：
  D1  **抽掉渲染层的「同 id 原地替换」** ⇒ 终态 `n_draft_lines > 0`
  D2  **抽掉「正式稿就绪才剔除」** ⇒ 中间态出现 `text=None` 的行
  D3  **App 消费者按「翻译去重键」存草稿译文**（`DRAFT::` 前缀，
      即 §53 之前的旧键）⇒ 中间态草稿**取不到译文**（空行）

基线组（期望成立）：
  E1  **纯函数口径在 D3 缺陷下依然全绿** ⇒ 证明 notice 15 §3.4 的缺口是**真实的**
      （MT 的 46/46 在这个场景下**依然全绿**）

产物
----
    results/app/app127_c111_real_timing_draft_lines_evidence.json

用法
----
    python app127_c111_real_timing_draft_lines.py
"""

import json
import os
import sys
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APP_DIR = os.path.join(REPO, 'live_caption')
sys.path.insert(0, APP_DIR)

# 🔴🔴 **验收脚本一律不 import 被测模块的顶层重依赖**：
#   `translator.py` 顶层 import numpy（managed 3.13 无 numpy ⇒ import 阶段 abort）
#   ⇒ **必须用 Python 3.12**（系统版有 numpy）。
#   `caption_render.py` 是纯 stdlib ⇒ 可直接 import。
import caption_render as CR  # noqa: E402

OUT = os.path.join(HERE, 'app127_c111_real_timing_draft_lines_evidence.json')

_results = []


def check(group, name, ok, detail=''):
    _results.append({'group': group, 'name': name,
                      'ok': bool(ok), 'detail': str(detail)})
    print('  [%s] %s %s  %s' % (group, 'PASS' if ok else 'FAIL',
                                name, ('<- ' + str(detail)) if detail else ''))
    return bool(ok)


# ══════════════════════════════════════════════════════════════════════
# 语料：三种真实形态的「跨段尾句」链
# ══════════════════════════════════════════════════════════════════════
CORPORA = {
    # ① 链自然闭合（段尾有句号）
    'chain_close': [
        'Good morning everyone and welcome to the quarterly review meeting.',
        'We have three agenda items today. The first one is the market expansion',
        'plan for the second quarter of next year across the whole region',
        'and we will review the numbers in detail.',
        'That concludes the first agenda item for today.',
    ],
    # ② 链被强制切出（跨段数 ≥ PEND_MAX_SEGS=3 且超 N 字）
    'forced_cut': [
        'First we will discuss the overall strategy for the coming year and how the',
        'team should align on the priorities across all three regions including the',
        'budget for the second half of the year and the hiring plan for engineering',
        'and finally we will review the timeline with the executive staff before the',
        'board meeting next month.',
    ],
    # ③ 链由 `flush()` 收尾补翻（末段无标点）
    'flush_close': [
        'Welcome to the meeting today. Let us start with the numbers',
        'from the last quarter and then move to the roadmap discussion',
    ],
}

# 🔴 §53 之前 App 侧 `_draft_mt` 用的旧键 = **翻译去重键**（带 `DRAFT::` 前缀）
DRAFT_KEY_PREFIX = 'DRAFT::'


class StubTranslator(object):
    """桩翻译器：可控延迟、**不加载任何模型**、**每次调用唯一译文**。

    🔴 **延迟的作用**：让「draft 事件」与「final 事件」在**不同的时间点**
       到达 ⇒ 制造真实的「草稿先显示、正式稿后到达」时序。
       —— 这正是生产路径的顺序（`_run_jobs` 里 `svc.done[job.key] = r['text']`
       **先于** `svc.outbox.append(...)`）。
    🔴 **唯一译文的作用**：草稿与正式稿的译文必须**可区分**
       ⇒ 否则「草稿是否单独残留」这条判据**测不出来**。
    """

    load_s = 0.01

    def __init__(self, delay_s=0.004, on_log=print):
        self.device = 'GPU.0'
        self.n_calls = 0
        self._lock = threading.Lock()
        self.calls = []
        self.delay_s = delay_s

    def translate(self, text, tgt, on_token=None, ctx=None, glossary=None):
        time.sleep(self.delay_s)
        with self._lock:
            self.n_calls += 1
            n = self.n_calls
        self.calls.append(text)
        return dict(text='译文#%d:%s' % (n, text), lat_ms=1.0, ttft_ms=0.5,
                    n_in=1, n_out=1, skipped=False)

    def close(self):
        pass


# ══════════════════════════════════════════════════════════════════════
# 真实时序驱动
# ══════════════════════════════════════════════════════════════════════
def _load_translator_module(src_text=None, name='_app127_translator'):
    """加载 `translator.py`（可指定源码 ⇒ 用于跑历史基线）。"""
    if src_text is None:
        path = os.path.join(APP_DIR, 'translator.py')
        with open(path, 'rb') as f:
            src_text = f.read().decode('utf-8')
    mod = types.ModuleType(name)
    mod.__file__ = '<app127-translator>'
    exec(compile(src_text, '<app127-translator>', 'exec'), mod.__dict__)
    return mod


def _load_caption_render_from_source(src_text):
    """用源码**独立**重建一个 `caption_render`（不碰 `sys.modules` 里的）。"""
    mod = types.ModuleType('_app127_cr')
    mod.__file__ = '<app127-caption_render>'
    exec(compile(src_text, '<app127-caption_render>', 'exec'), mod.__dict__)
    return mod


def _drive(mod, cr_mod, segments, consumer_key='id', delay_s=0.004):
    """按**真实时序**驱动一遍「翻译 → 事件消费 → 渲染」，返回完整时间线。

    参数
    ----
    consumer_key : 'id' | 'dedup'
        App 消费者存草稿译文时用的键。
        `'id'`   = **生产口径**（`live_caption_app.py::_pump_tts` 用 `ev['id']`）；
        `'dedup'` = **突变口径**（用**翻译去重键** `DRAFT::<uid>`）
                   ⇒ 与单元的 `unit_id` 对不上 ⇒ 草稿译文取不到
                   ⇒ 中间态草稿**显示为空**（D3 反证用）。
    """
    svc = mod.TranslationService(target='zh', device='GPU.0', auto=False,
                                 on_log=lambda m: None)
    svc.tr = StubTranslator(delay_s=delay_s)
    svc.state = 'ready'
    svc.load_s = 0.01

    th = threading.Thread(target=lambda: mod._run_jobs(svc, svc.tr),
                          daemon=True)
    th.start()

    # ── App 侧 outbox 消费者（**真代码路径**：`unpack_event` + 按 id 存草稿）
    draft_mt = {}          # 键 -> 草稿译文（与 GUI 的 `_draft_mt` 同口径）
    final_events = []
    state = dict(n_draft_seen=0)

    def consume():
        """消费 outbox（**真代码路径**）。返回本次消费到的草稿事件数。"""
        n = 0
        for item in svc.pop_outbox():
            ev = cr_mod.unpack_event(item)
            if ev is None:
                continue
            if ev['kind'] == 'final':
                final_events.append(ev)
            elif ev['kind'] == 'draft':
                k = (ev['id'] if consumer_key == 'id'
                     else DRAFT_KEY_PREFIX + str(ev['id']))
                draft_mt[k] = ev['txt']
                n += 1
        state['n_draft_seen'] += n
        return n

    def snapshot(tag):
        """取一次渲染快照（**真实**的 `mt_units()` + `render_lines()`）。"""
        units = svc.mt_units()
        # 🔴 **GUI 侧给草稿单元补译文的真实做法**（`live_caption_app.py`
        #    `_render_lines` 里那段）：按 `unit_id` 查 `draft_mt`。
        for u in units:
            if (u.get('kind') or 'final') == 'draft':
                uid = u.get('unit_id') or u.get('key')
                t = draft_mt.get(uid)
                if t:
                    u['mt'] = t
        lines = cr_mod.render_lines(segments, units, granularity='seg',
                                    show_pending=False,
                                    seg_carry=getattr(svc, 'seg_carry',
                                                      None) or {})
        return dict(tag=tag, units=[dict(u) for u in units],
                    lines=lines,
                    n_draft_lines=sum(1 for l in lines
                                      if l['kind'] == 'mt_draft'),
                    n_draft_nonempty=sum(1 for l in lines
                                         if l['kind'] == 'mt_draft'
                                         and (l['text'] or '').strip()),
                    n_mt_lines=sum(1 for l in lines if l['kind'] == 'mt'),
                    n_none_text=sum(1 for l in lines
                                    if l['kind'] in ('mt', 'mt_draft')
                                    and l['text'] is None))

    snapshots = []
    try:
        for i, seg in enumerate(segments):
            svc.submit(seg, seg=i)
            # 🔴🔴 **等草稿事件到达**（最多 400 ms）⇒ 拿到真实的中间态
            #    （草稿已到、其正式稿**还没到** ⇒ 正式稿在**下一段**才产生）
            deadline = time.perf_counter() + 0.4
            while time.perf_counter() < deadline:
                if consume() > 0:
                    break
                time.sleep(0.002)
            consume()
            snapshots.append(snapshot('after_submit_%d' % i))
            deadline = time.perf_counter() + 5.0
            while svc.pending and time.perf_counter() < deadline:
                time.sleep(0.002)
            consume()
        # ── 收尾：`flush()`（C-099①）—— 最后一条尾巴当完整句翻一次
        svc.flush(seg=len(segments) - 1)
        deadline = time.perf_counter() + 5.0
        while svc.pending and time.perf_counter() < deadline:
            time.sleep(0.002)
        consume()
        final_snap = snapshot('final')
    finally:
        svc.q.put(None)
        th.join(timeout=3)

    return dict(svc=svc, snapshots=snapshots, final=final_snap,
                draft_mt=draft_mt, final_events=final_events)


# ══════════════════════════════════════════════════════════════════════
# 统计
# ══════════════════════════════════════════════════════════════════════
def _norm_mt(t):
    """去掉渲染层的 `…` 承接前缀（**已文档化**的规则：`seg_carry`）。

    🔴 **为什么必须去**：跨段承接的段，其译文行**带 `…` 前缀**
       （`caption_render.render_lines` 里 `txt = '…' + txt`）
       ⇒ 直接做字符串比对会把**正确的**渲染判成「译文丢失」。
    """
    if t is None:
        return None
    return t[1:] if t.startswith('…') else t


def _stats(segments, run):
    """从一次运行里算出各项判据用的原始数字。"""
    svc = run['svc']
    final = run['final']
    units = final['units']
    lines = final['lines']

    finals = [u for u in units if (u.get('kind') or 'final') != 'draft']
    drafts = [u for u in units if (u.get('kind') or 'final') == 'draft']
    not_ready = [u for u in finals if not u.get('mt')]

    # ── 原文守恒 ────────────────────────────────────────────────────
    src_rendered = ''.join(l['text'] for l in lines if l['kind'] == 'src')
    src_norm = ''.join(src_rendered.split())
    src_sub_norm = ''.join(''.join(segments).split())

    # ── 正式稿译文守恒（忽略 `…` 前缀）──────────────────────────────
    # 🔴🔴🔴 **口径修正（app128 模糊测试自查抓出）**：
    #   渲染层 `caption_render.render_lines()` 对**同一 seg 的多个翻译单元**
    #   用 `txt = ' '.join(parts)` **拼成一行**
    #   （`caption_render.py` 里 `mt_by_seg` → `' '.join(parts)`）
    #   ⇒ 一行里可能有 **N 条**正式单元的译文
    #   ⇒ 「单元译文 == 整行」的**精确相等**口径 ⇒ **假 FAIL**
    #   （实测：随机语料 120 组里 **42 组**因此报 `missing_final_mt`，
    #     逐案复现后确认译文**全部在行内、只是被 join 了**）
    #   ⇒ 正确口径 = **子串包含**（与 join 语义一致）。
    mt_texts = [_norm_mt(l['text']) for l in lines
                if l['kind'] in ('mt', 'mt_draft') and l['text'] is not None]
    missing = [u.get('mt') for u in finals
               if u.get('mt') and not any(u['mt'] in t for t in mt_texts)]
    # 重复：某条单元译文出现在**多于一行**、或在同一行里出现**多于一次**
    counts = {}
    for t in mt_texts:
        counts[t] = counts.get(t, 0) + 1
    dup_final = {t: c for t, c in counts.items() if c > 1}
    for u in finals:
        mt = u.get('mt')
        if not mt:
            continue
        n_lines = sum(1 for t in mt_texts if mt in t)
        if n_lines > 1:
            dup_final.setdefault(mt, n_lines)
        else:
            for t in mt_texts:
                if mt in t and t.count(mt) > 1:
                    dup_final.setdefault(mt, t.count(mt))

    # ── 草稿译文是否单独残留 ──────────────────────────────────────
    #    🔴 同上：草稿行也是**独立成行**（`unmatched_draft` ⇒ 每条一行），
    #    所以这里用**精确相等**是对的（草稿行不会被 join）。
    draft_texts = [u.get('mt') for u in drafts if u.get('mt')]
    residual = [t for t in draft_texts if t in mt_texts]

    # ── 同 id 关系 ─────────────────────────────────────────────────
    final_by_uid = {}
    for u in finals:
        final_by_uid.setdefault(u.get('unit_id'), []).append(u)
    draft_uids = [u.get('unit_id') for u in drafts]
    same_id_ok = all(len(final_by_uid.get(uid, [])) == 1 for uid in draft_uids)
    matched = sum(1 for uid in draft_uids if final_by_uid.get(uid))

    # ── 事件层守恒 ─────────────────────────────────────────────────
    ev_src = ''.join(e['src'] for e in run['final_events'])

    # ── 一个 id 至多一条正式单元 ───────────────────────────────────
    ambiguous = {uid: len(v) for uid, v in final_by_uid.items() if len(v) > 1}

    # ── 中间态：草稿行可见 **且** 其正式稿**还没就绪**（缺失或 mt 为空）──
    mid = None
    for snap in run['snapshots']:
        if snap['n_draft_lines'] <= 0:
            continue
        s_units = snap['units']
        s_drafts = [u for u in s_units
                    if (u.get('kind') or 'final') == 'draft']
        s_finals = [u for u in s_units
                    if (u.get('kind') or 'final') != 'draft']
        ready_txt = set(u.get('mt') for u in s_finals if u.get('mt'))
        pending_uids = set()
        for d in s_drafts:
            uid = d.get('unit_id')
            f = next((u for u in s_finals if u.get('unit_id') == uid), None)
            if f is None or not f.get('mt'):
                pending_uids.add(uid)
        if pending_uids:
            mid = snap
            break

    # ── 中间态：已就绪的正式稿**是否还在渲染里**（§47 老坑）──────────
    #    🔴 同上口径修正：正式稿行可能被 join ⇒ 用**子串包含**判「还在不在」。
    mid_missing_ready = []
    mid_none_text = 0
    if mid is not None:
        mid_none_text = mid['n_none_text']
        mid_txts = [_norm_mt(l['text']) for l in mid['lines']
                    if l['kind'] in ('mt', 'mt_draft') and l['text'] is not None]
        for u in mid['units']:
            if (u.get('kind') or 'final') != 'draft' and u.get('mt'):
                if not any(u['mt'] in t for t in mid_txts):
                    mid_missing_ready.append(u.get('mt'))

    # ── 全程是否有 `text=None` 的行 ─────────────────────────────────
    n_none_text_total = sum(s['n_none_text'] for s in run['snapshots'])
    n_none_text_total += final['n_none_text']

    return dict(n_draft_lines=final['n_draft_lines'],
                n_mt_lines=final['n_mt_lines'],
                n_units=len(units), n_finals=len(finals), n_drafts=len(drafts),
                n_final_events=len(run['final_events']),
                n_not_ready=len(not_ready),
                src_ok=(src_norm == src_sub_norm),
                missing_final_mt=missing, dup_final_mt=dup_final,
                residual_draft_mt=residual,
                same_id_ok=same_id_ok,
                n_draft_uids_matched=matched, n_draft_uids=len(draft_uids),
                ev_src_ok=(''.join(ev_src.split()) == src_sub_norm),
                ambiguous_uid=ambiguous,
                draft_uids=draft_uids,
                final_uids=[u.get('unit_id') for u in finals],
                n_snapshots=len(run['snapshots']),
                n_mid_snapshots=sum(1 for s in run['snapshots']
                                    if s['n_draft_lines'] > 0),
                mid_found=mid is not None,
                # 🔴 **本语料是否「应当」出现中间态**：
                #   若从头到尾**没有任何快照带草稿行** ⇒ 该语料**没有草稿单元**
                #   （例如只有 1 段、立即成稿）⇒ 「找不到中间态」是**语料形态**
                #   **决定的**、不是缺陷 ⇒ 不能按 FAIL 记。
                mid_expected=any(s['n_draft_lines'] > 0
                                 for s in run['snapshots']),
                mid_n_draft_lines=(mid['n_draft_lines'] if mid else 0),
                mid_n_draft_nonempty=(mid['n_draft_nonempty'] if mid else 0),
                mid_missing_ready=mid_missing_ready,
                mid_none_text=mid_none_text,
                n_none_text_total=n_none_text_total)


# ══════════════════════════════════════════════════════════════════════
# 源码突变（**不改动工作区文件**）
# ══════════════════════════════════════════════════════════════════════
def _mutate(src_text, old, new):
    assert src_text.count(old) == 1, '突变锚点不唯一: %r' % old
    return src_text.replace(old, new)


def main():
    print('=' * 70)
    print('app127 —— MT notice 15 §3.4：真实时序下「无残留草稿行」端到端证据')
    print('=' * 70)

    mod = _load_translator_module()
    cr_path = os.path.join(APP_DIR, 'caption_render.py')
    with open(cr_path, 'rb') as f:
        cr_src = f.read().decode('utf-8')

    # ══════════════════════════════════════════════════════════════
    # REAL 组
    # ══════════════════════════════════════════════════════════════
    print('\n--- REAL 组 ---')
    all_stats = {}
    runs = {}
    for name, segs in CORPORA.items():
        run = _drive(mod, CR, segs)
        runs[name] = run
        all_stats[name] = _stats(segs, run)
        print('\n  【语料：%s】' % name)
        for k in ('n_units', 'n_finals', 'n_drafts', 'n_final_events',
                  'n_draft_uids', 'n_draft_uids_matched', 'n_draft_lines',
                  'n_mt_lines', 'n_snapshots', 'n_mid_snapshots', 'mid_found',
                  'mid_n_draft_nonempty', 'n_none_text_total'):
            print('    %-26s = %s' % (k, all_stats[name][k]))

    def _all(fn):
        return all(fn(all_stats[n]) for n in CORPORA)

    check('REAL', 'R1 真实时序跑完后正式稿全部就绪',
          _all(lambda s: s['n_not_ready'] == 0 and s['n_final_events'] > 0),
          '; '.join('%s: not_ready=%d ev=%d'
                    % (n, all_stats[n]['n_not_ready'],
                       all_stats[n]['n_final_events']) for n in CORPORA))

    check('REAL', 'R2 ★ 终态 n_draft_lines == 0（notice 15 §3.4 要的那一格）',
          _all(lambda s: s['n_draft_lines'] == 0),
          '; '.join('%s: %d' % (n, all_stats[n]['n_draft_lines'])
                    for n in CORPORA))

    check('REAL', 'R3 原文守恒（渲染 src 拼接 == 提交原文拼接）',
          _all(lambda s: s['src_ok']),
          '; '.join('%s: %s' % (n, all_stats[n]['src_ok']) for n in CORPORA))

    check('REAL', 'R4 正式稿译文守恒（不丢不重，已忽略 `…` 承接前缀）',
          _all(lambda s: not s['missing_final_mt'] and not s['dup_final_mt']),
          '; '.join('%s: miss=%d dup=%d'
                    % (n, len(all_stats[n]['missing_final_mt']),
                       len(all_stats[n]['dup_final_mt'])) for n in CORPORA))

    check('REAL', 'R5 草稿译文不单独残留',
          _all(lambda s: not s['residual_draft_mt']),
          '; '.join('%s: %d' % (n, len(all_stats[n]['residual_draft_mt']))
                    for n in CORPORA))

    check('REAL', 'R6 同 id 替换（每个草稿 id 恰有一条正式单元）',
          _all(lambda s: s['same_id_ok']
               and s['n_draft_uids_matched'] == s['n_draft_uids']
               and s['n_draft_uids'] > 0),
          '; '.join('%s: ok=%s matched=%d/%d'
                    % (n, all_stats[n]['same_id_ok'],
                       all_stats[n]['n_draft_uids_matched'],
                       all_stats[n]['n_draft_uids']) for n in CORPORA))

    check('REAL', 'R7 事件层守恒（final 事件 src 拼接 == 提交原文拼接）',
          _all(lambda s: s['ev_src_ok']),
          '; '.join('%s: %s' % (n, all_stats[n]['ev_src_ok'])
                    for n in CORPORA))

    check('REAL', 'R8 中间态草稿可见**且有译文**',
          _all(lambda s: (s['mid_found'] and s['mid_n_draft_nonempty'] > 0)
               if s['mid_expected'] else (not s['mid_found'])),
          '; '.join('%s: mid=%s nonempty=%d expect=%s'
                    % (n, all_stats[n]['mid_found'],
                       all_stats[n]['mid_n_draft_nonempty'],
                       all_stats[n]['mid_expected']) for n in CORPORA))

    check('REAL', 'R9 中间态不丢已就绪的正式稿（§47 老坑）',
          _all(lambda s: not s['mid_missing_ready']),
          '; '.join('%s: missing=%d'
                    % (n, len(all_stats[n]['mid_missing_ready']))
                    for n in CORPORA))

    check('REAL', 'R10 全程没有 text=None 的行（GUI 拼接会崩）',
          _all(lambda s: s['n_none_text_total'] == 0),
          '; '.join('%s: %d' % (n, all_stats[n]['n_none_text_total'])
                    for n in CORPORA))

    # ══════════════════════════════════════════════════════════════
    # BUG 组（期望不命中）
    # ══════════════════════════════════════════════════════════════
    print('\n--- BUG 组（期望不命中）---')
    check('BUG', 'B1 一个 unit_id 至多一条正式单元',
          _all(lambda s: not s['ambiguous_uid']),
          '; '.join('%s: %s' % (n, all_stats[n]['ambiguous_uid'])
                    for n in CORPORA))

    # B2：正式稿还在途 ⇒ 草稿行照常显示、正式稿不被提前剔除
    b2_ok = True
    b2_detail = []
    for name, segs in CORPORA.items():
        run = runs[name]
        units = [dict(u) for u in run['final']['units']]
        for u in units:
            if (u.get('kind') or 'final') != 'draft':
                u['mt'] = None
        lines = CR.render_lines(segs, units, granularity='seg',
                                show_pending=False,
                                seg_carry=getattr(run['svc'], 'seg_carry',
                                                  None) or {})
        nd = sum(1 for l in lines if l['kind'] == 'mt_draft')
        nm = sum(1 for l in lines if l['kind'] == 'mt')
        b2_detail.append('%s: draft=%d mt=%d' % (name, nd, nm))
        if nd <= 0:
            b2_ok = False
    check('BUG', 'B2 正式稿还在途 ⇒ 草稿行照常显示、正式稿不被提前剔除',
          b2_ok, '; '.join(b2_detail))

    # B3：已就绪的正式稿不得重复显示
    b3_ok = True
    b3_detail = []
    for name in CORPORA:
        texts = [_norm_mt(l['text']) for l in runs[name]['final']['lines']
                 if l['kind'] in ('mt', 'mt_draft')]
        b3_detail.append('%s: n=%d uniq=%d'
                         % (name, len(texts), len(set(texts))))
        if len(texts) != len(set(texts)):
            b3_ok = False
    check('BUG', 'B3 已就绪的正式稿不重复显示', b3_ok, '; '.join(b3_detail))

    # ══════════════════════════════════════════════════════════════
    # 反证组（期望命中 ⇒ 证明判据能抓出缺陷）
    # ══════════════════════════════════════════════════════════════
    print('\n--- 反证组（期望命中）---')

    # D1：抽掉渲染层的「同 id 原地替换」⇒ 终态草稿行残留
    cr_d1 = _load_caption_render_from_source(_mutate(
        cr_src,
        """        fj = final_idx_by_id.get(uid)
        if fj is not None:
            draft_to_final[i] = fj""",
        """        fj = None
        if fj is not None:
            draft_to_final[i] = fj"""))
    d1_res = {}
    for name, segs in CORPORA.items():
        d1_res[name] = _stats(segs, _drive(mod, cr_d1, segs))
    check('D1', 'D1 抽掉「同 id 原地替换」⇒ 终态 n_draft_lines > 0（判据能抓出缺陷）',
          all(d1_res[n]['n_draft_lines'] > 0 for n in CORPORA),
          '; '.join('%s: %d' % (n, d1_res[n]['n_draft_lines'])
                    for n in CORPORA))

    # D2：抽掉「正式稿就绪才剔除」⇒ 中间态出现 text=None 的行
    #    （正式稿还在途却被提前剔除 ⇒ 它的译文被搬到草稿行，而 mt 是 None）
    cr_d2 = _load_caption_render_from_source(_mutate(
        cr_src,
        """    matched_final_ready = set()
    for di, fi in draft_to_final.items():
        if final_units[fi].get('mt'):
            matched_final_ready.add(fi)""",
        """    matched_final_ready = set()
    for di, fi in draft_to_final.items():
        if True:
            matched_final_ready.add(fi)"""))
    d2_res = {}
    for name, segs in CORPORA.items():
        d2_res[name] = _stats(segs, _drive(mod, cr_d2, segs))
    #    ⚠️ **该突变只在「草稿已配到正式单元、但该正式单元的译文还没就绪」
    #       的那个快照上生效** ⇒ 只有**部分**语料会命中
    #       ⇒ 判据按「**至少一个语料命中**」计（并逐语料列出明细），
    #       **不**要求三个语料全中（那会把「突变不适用」误判成「判据失效」）。
    d2_hit = {n: d2_res[n]['n_none_text_total'] for n in CORPORA
              if d2_res[n]['n_none_text_total'] > 0}
    check('D2', 'D2 抽掉「正式稿就绪才剔除」⇒ 出现 text=None 的行（判据能抓出缺陷）',
          len(d2_hit) >= 1 and all(v == 0 for v in
                                   [all_stats[n]['n_none_text_total']
                                    for n in CORPORA]),
          '突变命中语料: %s ‖ 未突变时各语料 n_none_text_total: %s'
          % (d2_hit or '无',
             {n: all_stats[n]['n_none_text_total'] for n in CORPORA}))

    # D3：App 消费者按「翻译去重键」（`DRAFT::` 前缀）存草稿译文
    #    ⇒ 与单元的 `unit_id` 对不上 ⇒ 中间态草稿**取不到译文**（空行）
    d3_res = {}
    for name, segs in CORPORA.items():
        d3_res[name] = _stats(segs, _drive(mod, CR, segs, consumer_key='dedup'))
    check('D3', 'D3 App 消费者按翻译去重键存草稿 ⇒ 中间态草稿取不到译文',
          all(d3_res[n]['mid_n_draft_nonempty'] == 0 for n in CORPORA),
          '; '.join('%s: nonempty=%d'
                    % (n, d3_res[n]['mid_n_draft_nonempty'])
                    for n in CORPORA))

    # ══════════════════════════════════════════════════════════════
    # 基线组：证明 notice 15 §3.4 的缺口是**真实的**
    # ══════════════════════════════════════════════════════════════
    print('\n--- 基线组 ---')
    pure_ok = True
    pure_detail = []
    for name, segs in CORPORA.items():
        # 纯函数口径：只测「渲染层本身」，用**手工构造**的 units
        #   （**完全绕开** 事件流与消费者）
        units = [dict(u) for u in runs[name]['final']['units']]
        for u in units:
            if (u.get('kind') or 'final') == 'draft':
                u['mt'] = '手工草稿译文:' + (u.get('src') or '')
        lines = CR.render_lines(segs, units, granularity='seg',
                                show_pending=False,
                                seg_carry=getattr(runs[name]['svc'], 'seg_carry',
                                                  None) or {})
        nd = sum(1 for l in lines if l['kind'] == 'mt_draft')
        pure_detail.append('%s: n_draft_lines=%d' % (name, nd))
        if nd != 0:
            pure_ok = False
    check('E', 'E1 纯函数口径在 D3 缺陷下**依然全绿** ⇒ 46/46 证明不了这一格',
          pure_ok,
          '纯函数口径: ' + '; '.join(pure_detail)
          + '  ‖  真实时序口径(D3): '
          + '; '.join('%s: mid_nonempty=%d' % (n, d3_res[n]['mid_n_draft_nonempty'])
                      for n in CORPORA))

    # ══════════════════════════════════════════════════════════════
    # 汇总
    # ══════════════════════════════════════════════════════════════
    n_pass = sum(1 for r in _results if r['ok'])
    n_fail = sum(1 for r in _results if not r['ok'])
    print('\n' + '=' * 70)
    print('PASS %d / FAIL %d' % (n_pass, n_fail))
    print('=' * 70)

    evidence = dict(
        script='app127_c111_real_timing_draft_lines.py',
        purpose='MT notice 15 §3.4 真实时序「无残留草稿行」端到端证据',
        generated_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        python=sys.version,
        corpora=CORPORA,
        real_run=all_stats,
        counter_evidence_d1=d1_res,
        counter_evidence_d2=d2_res,
        counter_evidence_d3=d3_res,
        n_pass=n_pass, n_fail=n_fail,
        checks=_results,
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print('证据已写 %s' % OUT)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
