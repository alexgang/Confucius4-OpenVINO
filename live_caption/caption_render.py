r"""caption_render.py —— 字幕渲染层（APP-015 方案 C 的 App 侧实现）。

====================================================================
🔴 为什么单独成模块
====================================================================
渲染层要做两件事：
  ① **草稿 → 正式稿的原地替换**（方案 C，MT 通知 9 §9.1.2）；
  ② 按**句单元**取译文（而不是「一行 = 一个 ASR 段」聚合）。
这两件事的逻辑**不依赖任何模型**，纯字符串/字典运算 ⇒ 可以**离线验收**
（不起进程、不 import numpy、不跑推理、不占 GPU、不取机器锁）
⇒ 符合「先正确性、后性能」。

把逻辑从 `live_caption_app.py`（170 KB，顶部 import numpy/openvino）里抽出来，
还有一个好处：离线验收脚本**只 import 这个纯 stdlib 模块**
⇒ 不会在 import 阶段 abort。

====================================================================
方案 C（APP-015 / H-016 / H-017 / MT 通知 9，用户已决定）的接口约定
====================================================================
MT 侧 outbox 是 `(kind, key, text)` 三元组：

| kind    | 含义                  | 字幕                | TTS |
|---------|-----------------------|---------------------|-----|
| 'draft' | 跨段尾句的**草稿**    | ✅ 显示（**浅色**） | ❌ 不念 |
| 'final' | **正式稿**（完整句）  | ✅ 显示（正常色）   | ✅ 念 |

🔴 **草稿与正式稿的 key 不同**（草稿 = `DRAFT::` + 半句 key，
   正式稿 = 整句 key）⇒ **不能**用 key 直接覆盖。
⇒ **替换关系靠 `src` 的包含关系建立**：草稿的 `src` 是正式稿 `src` 的
   前缀/子串（MT 实测 122/135 = 90.4%）。

====================================================================
🔴🔴 关键语义：**「原地替换」= 正式稿显示在草稿那一行**
====================================================================
段归属实测（MT 方案 C 的实现）：
  - 草稿单元的 `seg` = **段尾半句所在的那一段**（如段 5）；
  - 正式稿单元的 `seg` = **凑齐后提交的那一段**（如段 6）
    （因为跨段句要等下一段才凑成完整句）。

⇒ 若照 `seg` 正常聚合，**完整句译文会显示在段 6 下面**，
   而用户在段 5 看到的那行浅色草稿**留在原地不变**
   ⇒ 「同一句话在屏幕上出现两次」。

⇒ MT 通知 9 §9.1.2 要求的是 **「用 final 的内容覆盖它 ⇒ 字幕上那一行
   原地变成正式稿」** ⇒ 本模块的实现是：
   **被关联的正式稿，其译文渲染在「草稿那一行」的位置**，
   并且**从该段的正常聚合里剔除**（避免重复）。

====================================================================
⚠️ 与 §26.6 的关系（**撤回 §26.6 的「等 reviewer 裁定」**）
====================================================================
§26.6 记的是：把字幕从「按 ASR 段」改成「按完整句」属**产品行为变更**
（总行数 436 → 1424，3.3×）⇒ 当时**提请 reviewer 裁定**，未自行改动。

🔴 现在 §26.6 的**三问**里：
  - 第①问（**字幕粒度**：一行一句 vs 一行一段）⇒ **至今没人回答**
    （APP-015 / H-016 / H-017 / 通知 9 讲的是**草稿/正式稿的分工**，
    **没有**要求改粒度）⇒ **本模块默认保持现状 `'seg'`**；
  - 第②问（重复句「字幕显示 2 次 / 语音播 1 次」）⇒ 未回答 ⇒ 不动；
  - 第③问（`flush()` 补翻的 `seg=None` 单元挂哪）⇒ 未回答 ⇒ 不动。

⇒ 本模块**同时支持两种粒度**（`granularity='seg' | 'unit'`），
  **默认 `'seg'`** ⇒ **不擅自改字幕粒度**。
  ⇒ 这样**落地了方案 C（草稿替换 + 浅色）**，**又不越权改产品行为**。

====================================================================
不变式（写进验收断言）
====================================================================
1. **原文守恒**：所有 `kind=='src'` 的 `text` 拼接 == `blocks` 的原文拼接
   （去空白口径）⇒ 渲染层**不丢字、不加字**。
2. **替换不重复**：被正式稿替换掉的草稿**不单独出行**；
   被替换的正式稿**只出现在草稿那一行**（不从段聚合里重复出现）。
3. **未被替换的草稿保留**：正式稿没到 ⇒ 草稿**仍然显示**（浅色）。
4. **同一句译文在一屏里只出现一次**（草稿行 + 正式稿行不能同时在）。
"""

from __future__ import annotations

import re

# ── 归一化（用于 `src` 包含匹配）────────────────────────────────────
# 🔴 **不用 `norm_key`（translator.py 的）**：那是 MT 内部的**翻译去重键**
#    ⇒ **重复句会撞键** ⇒ 不能用来判「是不是同一句话」。
#
# ⚠️ **归一化必须去掉标点**：草稿是半句（**没有**句末标点），
#   正式稿是整句（**有**句末标点）⇒ 若保留标点，'we should go'
#   与 'we should go now.' 归一化后**不相同** ⇒ 包含匹配会失败。
#   ⇒ 归一化 = 去标点 + 折叠空白 + 小写 + 去首尾空白。

_PUNCT_RE = re.compile(r'[^\w\s]', re.UNICODE)
_WS_RE = re.compile(r'\s+', re.UNICODE)


def norm_src(s: str) -> str:
    """把原文归一化成「可做子串包含比较」的形式。

    - 去所有标点（中英文）；
    - 空白折叠成单个空格；
    - 转小写；
    - 去首尾空格。

    ⇒ 「草稿 src」归一化后应是「正式稿 src」归一化后的**子串**。
    """
    if not s:
        return ''
    t = _PUNCT_RE.sub('', s)
    return _WS_RE.sub(' ', t).strip().lower()


def is_substring(needle: str, haystack: str) -> bool:
    """`needle` 归一化后是否为 `haystack` 归一化后的子串。"""
    n, h = norm_src(needle), norm_src(haystack)
    if not n or not h:
        return False
    return n in h


def strip_ws(s: str) -> str:
    """去所有空白（用于「原文守恒」的口径对齐）。"""
    return _WS_RE.sub('', s or '')


# ── 草稿 ↔ 正式稿 的关联 ───────────────────────────────────────────
def match_draft_to_final(drafts, finals):
    """把**草稿**关联到**正式稿**（`src` 包含匹配）。

    参数
    ----
    drafts : [{'src': str, ...}, ...]   草稿单元（`src` = 半句原文）
    finals : [{'src': str, ...}, ...]   正式稿单元（`src` = 整句原文）

    返回
    ----
    {draft_index: final_index} —— **一对一**（一个正式稿只被一个草稿占）。

    =====================================================================
    🔴 判据（2026-10-25 修订，与 MT 修正口径对齐）
    =====================================================================
    **三级关系**（归一化后比较，`norm_src` = 去标点 + 折叠空白 + 小写）：

    | rank | 关系 | 含义 |
    |------|------|------|
    | 0 | **完全相等** | 草稿就是这句（定稿只补了句末标点） |
    | 1 | **正式稿以草稿为前缀**（且更长） | 草稿是整句的**前半截**（方案 C 主场景） |
    | 2 | **草稿嵌在正式稿中间**（且**不是**反向） | 放宽兜底 |

    🔴🔴 **反向一律拒绝**：若「正式稿以草稿为**前缀**」且正式稿**更短**
       （即 `草稿 = 正式稿 + 续写`）⇒ 那个正式稿其实是**更早**的单元
       ⇒ 不是「草稿被正式稿替换」⇒ 拒绝。
       （与 MT 修正口径 `c111_metrics_fixed.py::draft_to_final_gap_fixed`
       的「修正 B：**方向性**」一致。）

    **排序键**（升序，先命中先占）：

        `(rank, -len(draft_norm), len(final_norm), draft_idx, final_idx)`

      ① `rank` 升序 ⇒ 相等 > 前缀 > 子串（越确定越优先）；
      ② `-len(draft_norm)` 升序 ⇒ **草稿更长优先**（更具体的草稿先配）
         ⇒ 防止短草稿抢走正式稿；
      ③ `len(final_norm)` 升序 ⇒ **最短剩余正式稿优先**
         （MT 修正口径的核心启发式：同一个草稿若有多个候选正式稿，
          取**最短**那个 ⇒ 最贴切）；
      ④ 下标 ⇒ 保证**确定性**（同样的输入永远同样的输出）。

    **全局一对一**：一个正式稿只被一个草稿占 ⇒ 避免同一句译文在字幕里
    出现两次（渲染层不变式 4）。

    =====================================================================
    🔴 为什么**不抄** MT 的 `min_len=10` 过滤
    =====================================================================
    MT 修正口径里 `min_len=10` 是**评测口径**（草稿太短 ⇒ 替换间隔
    没有统计意义）⇒ 会**主动放弃**「So great」这类短草稿的配对。
    🔴 **渲染层不能这么做**：短草稿只要**确实**有正式稿以它为前缀，
    就应该被替换（否则用户看到浅色草稿**永远不被替换**）。
    ⇒ 渲染层**保留**短草稿的配对能力，`min_len` 只在评测侧生效。

    ⚠️ **与 MT 评测口径的已知差异（不是 bug，是用途不同）**：
    MT 的评测脚本算的是「替换间隔 / 语义一致性」，允许**一个正式稿
    被多个草稿关联**（因为它不关心「同一句译文显示几次」）；
    渲染层**必须**一对一（否则同一句译文在屏幕上出现多次 ⇒ 违反不变式 4）。
    ⇒ 两边的配对数**天然不会完全相同**，不可直接互相引用。
    """
    cands = []
    for di, d in enumerate(drafts):
        dn = norm_src(d.get('src', ''))
        if not dn:
            continue
        for fi, f in enumerate(finals):
            fn = norm_src(f.get('src', ''))
            if not fn:
                continue
            if dn == fn:
                rank = 0                     # 完全相等（最确定）
            elif fn.startswith(dn) and len(fn) > len(dn):
                rank = 1                     # 方向性前缀（主场景）
            elif dn in fn:
                # 🔴 这里**不可能**是反向：反向要求 `fn` 是 `dn` 的真前缀
                #   ⇒ `len(fn) < len(dn)` ⇒ `dn` 不可能是 `fn` 的子串
                #   ⇒ 与 `dn in fn` **天然互斥**（无需再判）。
                rank = 2                     # 草稿嵌在正式稿中间（放宽）
            else:
                # 🔴 反向（正式 ⊂ 草稿）或无包含关系 ⇒ 一律不配
                continue
            cands.append((rank, -len(dn), len(fn), di, fi))
    cands.sort()
    out = {}
    used_final = set()
    for _rank, _neglen, _finlen, di, fi in cands:
        if di in out or fi in used_final:
            continue
        out[di] = fi
        used_final.add(fi)
    return out


# ── 渲染 ────────────────────────────────────────────────────────────
def render_lines(blocks, units, drafts=None, granularity='seg',
                 seg_carry=None, show_pending=False):
    """把「ASR 段 + 句单元 + 草稿」渲染成显示行。

    参数
    ----
    blocks : [str, ...]        ASR 段原文（按段序）
    units  : [{'key','src','seg','mt','kind'?}, ...]
             句单元。**`kind=='draft'` 的单元归入草稿**（MT 方案 C 合入后
             `translator.py` 的 `units` 会这样登记）；
             其余（无 kind / kind=='final'）归入正式稿。
    drafts : [{'key','src','mt','seg'?}, ...]
             **额外**的草稿单元（可选）—— 由调用方从 outbox 的
             `('draft', key, text)` 收集（提供 `src` 才有原文）。
    granularity : 'seg' | 'unit'
        'seg'  —— **现状**：一行 = 一个 ASR 段（该段的句单元译文拼在一行）
        'unit' —— 一行 = 一个句单元（§26.6 第①问，**尚未被裁定** ⇒ 默认 'seg'）
    seg_carry : {seg: bool}   该段是否承接上一段的半句（加 '…' 前缀）
    show_pending : bool
        True ⇒ 该段译文**还在途**（且承接了上一段的半句）时，
        输出一行「（译文生成中…）」⇒ **保持 `_save_text()` 的旧行为**
        （旧实现有这个提示行，屏幕渲染没有 ⇒ 用它把两者区分开）。

    返回
    ----
    [{'kind': 'src'|'mt'|'mt_draft', 'text': str, 'seg': int|None,
      'draft': bool}, ...]

    🔴 **不变式 1（原文守恒）**：所有 `kind=='src'` 的 `text` 拼接
       == `blocks` 的拼接（去空白口径）。
    🔴 **不变式 2（替换不重复）**：被关联的正式稿，其译文**只**出现在
       「草稿那一行」的位置，不在段聚合里重复出现。
    """
    seg_carry = seg_carry or {}
    extra_drafts = list(drafts or [])

    # ── 拆分「正式稿单元」与「草稿单元」──────────────────────────────
    final_units = []
    draft_units = []
    for u in units or []:
        if (u.get('kind') or 'final') == 'draft':
            draft_units.append(u)
        else:
            final_units.append(u)
    # 外部补的草稿（outbox 来的）优先带上 `src`
    seen_draft_keys = {d.get('key') for d in draft_units if d.get('key')}
    for d in extra_drafts:
        if d.get('key') and d.get('key') in seen_draft_keys:
            # 同一 key：补上 `src`（outbox 只有译文，原文在 units 里）
            for u in draft_units:
                if u.get('key') == d.get('key') and not u.get('src'):
                    u['src'] = d.get('src') or ''
            continue
        draft_units.append(d)

    # 只保留有原文的草稿（没有原文 ⇒ 无法建立替换关系 ⇒ 不参与匹配，
    # 但**仍然要显示** ⇒ 走「未关联草稿」那条路）
    matchable = [d for d in draft_units if (d.get('src') or '').strip()]
    m2f = match_draft_to_final(matchable, final_units)
    # matchable 的下标 → draft_units 的下标
    idx_map = {}
    for i, d in enumerate(draft_units):
        for j, m in enumerate(matchable):
            if m is d:
                idx_map[j] = i
    draft_to_final = {idx_map[j]: fi for j, fi in m2f.items() if j in idx_map}
    matched_final_idx = set(draft_to_final.values())
    matched_draft_idx = set(draft_to_final.keys())

    # ── 'unit'：一行 = 一个句单元（§26.6 第①问，**未被裁定**）──────
    if granularity == 'unit':
        lines = []
        for u in final_units:
            lines.append({'kind': 'src', 'text': u.get('src', ''),
                          'seg': u.get('seg'), 'draft': False})
            if u.get('mt'):
                lines.append({'kind': 'mt', 'text': u.get('mt'),
                              'seg': u.get('seg'), 'draft': False})
        for i, d in enumerate(draft_units):
            if i in matched_draft_idx:
                continue
            if d.get('mt'):
                lines.append({'kind': 'mt_draft', 'text': d.get('mt'),
                              'seg': d.get('seg'), 'draft': True})
        return lines

    # ── 'seg'：现状粒度（默认）────────────────────────────────────
    # 正式稿的译文按段聚合；**被草稿替换的正式稿不参与聚合**
    # （它显示在草稿那一行）。
    #
    # 🔴🔴 **关键修正（2026-10-25）**：只有当**正式稿的译文已经就绪**
    #   （`mt` 非空）时，才把它从段聚合里剔除并「搬到」草稿那一行。
    #   ⚠️ 若正式稿**还在途**（`mt` 为 None）却提前剔除 ⇒
    #   该句在这一轮渲染里**译文彻底消失**（既不在草稿行、也不在段聚合）
    #   ⇒ 屏幕上「有原文、没译文」⇒ 用户以为翻译丢了。
    #   ⇒ 正确做法：正式稿还在途 ⇒ **仍留在段聚合里**（等 mt 到了自然出现），
    #   草稿那一行**照常显示浅色草稿**；下一轮渲染时正式稿就绪 ⇒
    #   它被搬到草稿那一行（原地替换）⇒ 段聚合里就不再有它。
    matched_final_ready = set()
    for di, fi in draft_to_final.items():
        if final_units[fi].get('mt'):
            matched_final_ready.add(fi)
    mt_by_seg = {}
    for j, u in enumerate(final_units):
        if j in matched_final_ready:
            continue
        seg = u.get('seg')
        txt = u.get('mt')
        if not txt:
            continue
        mt_by_seg.setdefault(seg, []).append(txt)

    # 草稿分两类：
    #   ① 正式稿就绪 ⇒ **原地**显示正式稿译文（正常色），草稿不再显示
    #   ② 正式稿还在途 / 没匹配上 ⇒ 显示草稿译文（浅色）
    replaced_at = {}      # seg -> [(位置序, 正式稿文本)]
    unmatched_draft = {}  # seg -> [草稿单元]
    for i, d in enumerate(draft_units):
        seg = d.get('seg')
        fi = draft_to_final.get(i)
        if fi is not None and fi in matched_final_ready:
            replaced_at.setdefault(seg, []).append((i, final_units[fi]['mt']))
            continue
        if d.get('mt'):
            unmatched_draft.setdefault(seg, []).append(d)

    lines = []
    for i, src in enumerate(blocks):
        lines.append({'kind': 'src', 'text': src, 'seg': i, 'draft': False})
        parts = mt_by_seg.get(i) or []
        if parts:
            txt = ' '.join(parts)
            if seg_carry.get(i):
                txt = '…' + txt
            lines.append({'kind': 'mt', 'text': txt, 'seg': i, 'draft': False})
        elif show_pending and seg_carry.get(i):
            # 旧行为：承接了上一段半句、但译文还在途 ⇒ 给一行提示
            lines.append({'kind': 'mt_pending', 'text': '（译文生成中…）',
                          'seg': i, 'draft': False})
        # 原地替换：草稿那一行变成正式稿（正常色）
        for _pos, txt in replaced_at.get(i) or []:
            lines.append({'kind': 'mt', 'text': txt, 'seg': i, 'draft': False})
        # 未替换的草稿：浅色
        for d in unmatched_draft.get(i) or []:
            lines.append({'kind': 'mt_draft', 'text': d.get('mt') or '',
                          'seg': i, 'draft': True})
    return lines


def collect_drafts(outbox, src_lookup=None):
    """从 outbox 的 `('draft', key, text)` 三元组收集草稿的**译文**。

    🔴 **为什么要 `src_lookup`**：outbox 的草稿**只有 key 和译文**，
    **没有原文** ⇒ 无法做 `src` 包含匹配（通知 9 §9.1.2 的核心判据）。
    ⇒ 调用方提供「key → 原文」的映射（来自 `mt_units()` 里的草稿单元）。

    🔴 **拿不到 `src` 时** ⇒ 这里**照常返回译文**，但 `src` 为空
    ⇒ `render_lines()` 会把它当「未关联草稿」⇒ **只显示、不替换**
    ⇒ **绝不猜、不乱配**。

    参数
    ----
    outbox     : [(kind, key, text), ...]
    src_lookup : {key: src}  可选

    返回
    ----
    [{'key','src','mt'}, ...]
    """
    out = []
    for item in outbox or []:
        if not item or len(item) < 3:
            continue
        kind, key, text = item[0], item[1], item[2]
        if kind != 'draft':
            continue
        src = ''
        if src_lookup:
            src = src_lookup.get(key) or ''
        out.append({'key': key, 'src': src, 'mt': text})
    return out


def summarize(lines):
    """给出渲染结果的统计（供验收断言）。"""
    n_src = sum(1 for l in lines if l['kind'] == 'src')
    n_mt = sum(1 for l in lines if l['kind'] == 'mt')
    n_draft = sum(1 for l in lines if l['kind'] == 'mt_draft')
    src_chars = sum(len(strip_ws(l['text'])) for l in lines
                    if l['kind'] == 'src')
    mt_texts = [l['text'] for l in lines if l['kind'] in ('mt', 'mt_draft')]
    dup_mt = len(mt_texts) - len(set(mt_texts))
    return {'n_src': n_src, 'n_mt': n_mt, 'n_draft': n_draft,
            'n_lines': len(lines), 'src_chars': src_chars,
            'n_mt_texts': len(mt_texts), 'n_dup_mt_texts': dup_mt}