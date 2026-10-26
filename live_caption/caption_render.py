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
MT 侧 outbox 的事件格式在**方案 C 合入时**变了（MT H-019 移交说明）：

| 格式 | 事件 | 含义 |
|------|------|------|
| 旧（3 元组） | `(kind, key, text)` | `key` = **翻译去重键**，草稿与正式稿**不同** |
| **新（5 元组）** | `(kind, id, src, txt, seg)` | `id` = **单元 id**，草稿与正式稿**共用** |

| kind    | 含义                  | 字幕                | TTS |
|---------|-----------------------|---------------------|-----|
| 'draft' | 跨段尾句的**草稿**    | ✅ 显示（**浅色**） | ❌ 不念 |
| 'final' | **正式稿**（完整句）  | ✅ 显示（正常色）   | ✅ 念 |

🔴🔴 **替换关系改用「同 id 原位替换」**（**不再用原文包含关系**）：

- 草稿与它的正式稿**共用同一个单元 id**（`C:<起始段>:<序号>`）
  ⇒ App 按 id 直接配对 ⇒ 零歧义。
- 🔴 **为什么必须改**：MT §73 实测「双向包含 + 取最短」的 src 匹配
  会把草稿 `'That'` 配到 `"That's where we are today."`
  （**跨 85 段**）⇒ 正式稿译文被搬到**错误的段**（用户可见）。
  ⇒ 「包含/前缀」只保留作**诊断统计**口径，**不再用于渲染替换**。
- ⇒ 本模块**保留**旧的 src 包含匹配，但**只作为「没有 id 时」的兜底**
  （旧格式 3 元组的事件没有 id）。

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
                 seg_carry=None, show_pending=False, spk_by_seg=None):
    """把「ASR 段 + 句单元 + 草稿」渲染成显示行。

    参数
    ----
    blocks : [str, ...]        ASR 段原文（按段序）
    units  : [{'key','src','seg','mt','kind'?,'unit_id'?}, ...]
             句单元。**`kind=='draft'` 的单元归入草稿**（MT 方案 C 合入后
             `translator.py` 的 `units` 会这样登记）；
             其余（无 kind / kind=='final'）归入正式稿。
             🔴 **`unit_id` = 方案 C 的单元 id** ⇒ 草稿与正式稿靠它配对
             （**不要再用 src 包含关系**做替换，见模块 docstring）。
    drafts : [{'key','id'?,'src','mt','seg'?}, ...]
             **额外**的草稿单元（可选）—— 由调用方从 outbox 收集
             （`collect_drafts()`，兼容 3 元组与 5 元组）。
    granularity : 'seg' | 'unit'
        'seg'  —— **现状**：一行 = 一个 ASR 段（该段的句单元译文拼在一行）
        'unit' —— 一行 = 一个句单元（§26.6 第①问，**尚未被裁定** ⇒ 默认 'seg'）
    seg_carry : {seg: bool}   该段是否承接上一段的半句（加 '…' 前缀）
    show_pending : bool
        True ⇒ 该段译文**还在途**（且承接了上一段的半句）时，
        输出一行「（译文生成中…）」⇒ **保持 `_save_text()` 的旧行为**
        （旧实现有这个提示行，屏幕渲染没有 ⇒ 用它把两者区分开）。
    spk_by_seg : {seg: spk_id}   **可选**（APP-022 接口预留）
        该段的说话人 id。⚠️ **当前恒为空**（ASR 侧还没交付 spk）
        ⇒ 输出行会多带一个 `'spk'` 键（**值为 None**）
        ⇒ **不影响 `text` / `kind` / `seg`** ⇒ 现有渲染逻辑零影响。

    返回
    ----
    [{'kind': 'src'|'mt'|'mt_draft', 'text': str, 'seg': int|None,
      'draft': bool, 'spk': str|None}, ...]

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

    # ── 🔴🔴 方案 C：**同 id 原位替换**（唯一可靠口径）───────────────
    #   草稿与它的正式稿**共用同一个单元 id**（MT H-019 移交说明）
    #   ⇒ 直接按 id 配对，**不再用原文包含关系**。
    #
    #   🔴 为什么必须这样：MT §73 实测「双向包含 + 取最短」会把草稿
    #     `'That'` 配到 `"That's where we are today."`（**跨 85 段**）
    #     ⇒ 正式稿译文被搬到**错误的段**（用户可见）。
    #   ⇒ 有 id 就用 id；**没有 id 才回退**到旧的 src 包含匹配。
    #
    #   判据：**同一个 id 最多一条正式单元**（MT 侧保证）⇒ 配对无歧义。
    final_idx_by_id = {}
    for j, u in enumerate(final_units):
        uid = u.get('unit_id') or u.get('id')
        if uid and uid not in final_idx_by_id:
            final_idx_by_id[uid] = j
    id_matched_draft_idx = set()
    id_matched_final_idx = set()
    for i, d in enumerate(draft_units):
        uid = d.get('unit_id') or d.get('id')
        if not uid:
            continue
        fj = final_idx_by_id.get(uid)
        if fj is None:
            continue
        id_matched_draft_idx.add(i)
        id_matched_final_idx.add(fj)

    # 只保留有原文的草稿（没有原文 ⇒ 无法建立替换关系 ⇒ 不参与匹配，
    # 但**仍然要显示** ⇒ 走「未关联草稿」那条路）
    #
    # 🔴🔴 **id 配对优先** ⇒ 已经按 id 配上的草稿与正式稿
    #   **不再参加 src 包含匹配** ⇒ 否则 src 匹配可能给同一个草稿找到
    #   **另一个**「看起来更合适」的正式稿 ⇒ 又回到「跨 85 段错配」的老问题。
    cand_draft = [(i, d) for i, d in enumerate(draft_units)
                  if (d.get('src') or '').strip() and i not in id_matched_draft_idx]
    cand_final = [j for j in range(len(final_units))
                  if j not in id_matched_final_idx]
    m2f = match_draft_to_final([d for _i, d in cand_draft],
                               [final_units[j] for j in cand_final])
    # （cand_draft / cand_final 的下标 → draft_units / final_units 的下标）
    draft_to_final = {}
    for k, fj_pos in m2f.items():
        if k >= len(cand_draft):
            continue
        di = cand_draft[k][0]
        fj = cand_final[fj_pos]
        draft_to_final[di] = fj
    # id 配对**优先写入**（覆盖同一条草稿的 src 配对）
    for i, d in enumerate(draft_units):
        uid = d.get('unit_id') or d.get('id')
        if not uid:
            continue
        fj = final_idx_by_id.get(uid)
        if fj is not None:
            draft_to_final[i] = fj
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
        lines.append({'kind': 'src', 'text': src, 'seg': i, 'draft': False,
                      'spk': (spk_by_seg or {}).get(i)})
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


def unpack_event(item):
    """把 outbox 事件**解包**成统一结构（🔴 兼容 3 / 5 / 7 元组）。

    =====================================================================
    🔴🔴 事件格式在方案 C 里变了（MT H-019 移交说明）
    =====================================================================
    | 格式 | 事件 | 含义 |
    |------|------|------|
    | 旧（3 元组） | `(kind, key, text)` | `key` = **翻译去重键**，草稿与正式稿**不同** |
    | **新（5 元组）** | `(kind, id, src, txt, seg)` | `id` = **单元 id**，草稿与正式稿**共用** |
    | **7 元组**（APP-022） | `(kind, id, src, txt, seg, spk, spk_conf)` | 追加说话人信息 |

    🔴 **为什么必须按 id 替换、不能按原文包含关系**：
    MT §73 实测「双向包含 + 取最短」会把草稿 `'That'` 配到
    `"That's where we are today."`（**跨 85 段**）⇒ 正式稿译文被搬到
    **错误的段**（用户可见）。⇒ 方案 C 的「同 id 原位替换」是**唯一**可靠口径。

    🔴🔴 **7 元组是「按需加长」**（APP-022）：
    `spk is None`（当前常态）⇒ 事件**仍是 5 元组** ⇒ 与改造前逐位一致
    ⇒ MT 侧的 `len(e) == 5` 断言（`12_event_is_5tuple` / `ev_5tuple`）
    **继续成立**，不需要等 MT 改。

    返回
    ----
    {'kind','id','key','src','txt','seg','spk','spk_conf'}
      · `id`  —— 单元 id（新格式有；旧格式退回 `key`）
      · `key` —— 翻译去重键（旧格式有；新格式用 `DRAFT::`+id 派生）
      · `src` —— 原文（新格式有；旧格式为空）
      · `seg` —— ASR 段号（新格式有；旧格式为 None）
      · `spk` —— 全局说话人 id（**7 元组才有**；否则 None）
      · `spk_conf` —— 说话人置信度（**7 元组才有**；否则 None）
    """
    if not item:
        return None
    kind = item[0] if len(item) > 0 else ''
    if len(item) >= 7:
        kind, uid, src, txt, seg = item[0], item[1], item[2], item[3], item[4]
        return {'kind': kind, 'id': uid, 'key': uid,
                'src': src or '', 'txt': txt or '', 'seg': seg,
                'spk': item[5], 'spk_conf': item[6]}
    if len(item) >= 5:
        kind, uid, src, txt, seg = item[0], item[1], item[2], item[3], item[4]
        return {'kind': kind, 'id': uid, 'key': uid,
                'src': src or '', 'txt': txt or '', 'seg': seg,
                'spk': None, 'spk_conf': None}
    if len(item) >= 3:
        kind, key, text = item[0], item[1], item[2]
        return {'kind': kind, 'id': key, 'key': key,
                'src': '', 'txt': text or '', 'seg': None,
                'spk': None, 'spk_conf': None}
    return None


def collect_drafts(outbox, src_lookup=None):
    """从 outbox 收集草稿的**译文**（🔴 兼容 3 元组与 5 元组）。

    🔴 **为什么要 `src_lookup`**：旧格式（3 元组）的草稿**只有 key 和译文**，
    **没有原文** ⇒ 无法做 `src` 包含匹配。
    ⇒ 调用方提供「key → 原文」的映射（来自 `mt_units()` 里的草稿单元）。

    🔴 **新格式（5 元组）自带 `src`** ⇒ **不再需要** `src_lookup`，
    而且**这是正确性关键**：草稿的原文由 MT 侧**权威给出**
    ⇒ App 不必再靠「猜」来配对。

    🔴 **拿不到 `src` 时** ⇒ 这里**照常返回译文**，但 `src` 为空
    ⇒ `render_lines()` 会把它当「未关联草稿」⇒ **只显示、不替换**
    ⇒ **绝不猜、不乱配**。

    参数
    ----
    outbox     : [(kind, id, src, txt, seg), ...] 或 [(kind, key, text), ...]
    src_lookup : {key: src}  可选（仅旧格式需要）

    返回
    ----
    [{'key','id','src','mt','seg'?}, ...]
    """
    out = []
    for item in outbox or []:
        ev = unpack_event(item)
        if ev is None or ev['kind'] != 'draft':
            continue
        src = ev['src']
        if not src and src_lookup:
            src = src_lookup.get(ev['key']) or ''
        d = {'key': ev['key'], 'id': ev['id'], 'src': src, 'mt': ev['txt']}
        if ev['seg'] is not None:
            d['seg'] = ev['seg']
        out.append(d)
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