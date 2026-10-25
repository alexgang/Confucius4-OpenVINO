r"""app053_draft_prefix_boundary_probe.py —— 🔴 **草稿→正式稿「假前缀」在 App 渲染层的实际影响**。

====================================================================
为什么做这件事
====================================================================
MT 通知 13（`shared/NOTICE_mt_to_app_20261026_notice13.md`，2026-10-26 00:47）
指出：MT 侧旧口径「**双向包含 + 取最短**」会产出**假前缀** ⇒ 把草稿配到几十段之外
⇒ 报出 **563.86 s** 的假长尾；**真实上界 13.4 s**。

通知 13 的 §13.4 给出的修正口径是**三步**：
  1. **只接受正向**：正式原文以草稿原文为**前缀**且更长；
  2. **词边界**：前缀之后紧跟的字符**不能是字母/数字**；也不能是「撇号 + 字母数字」
     （`That's` ≠ `That` + `s`）⇒ **需保留空格做归一**；
  3. **跳过过短草稿**：草稿原文长度 < 10。

🔴 **通知 13 §13.1 明确说「产品里『草稿→正式稿替换』的机制完全不受影响」**
   （替换关系靠**原文包含关系**建立）⇒ **本脚本的第一任务是「核实这句话是否成立」**，
   而**不是**去改产品逻辑。

====================================================================
本脚本要回答的三个问题
====================================================================
Q1 🔴 **App 渲染层会不会被假前缀污染？**
   产品规则 = `live_caption/caption_render.py::match_draft_to_final`
   （三级关系：rank0 相等 / rank1 方向性前缀 / rank2 子串兜底；反向拒绝；
     全局一对一；排序键 `(rank, -len(dn), len(fn), di, fi)`）。
   ⇒ 它**已经**是方向性的（rank1 前缀优先）⇒ 与通知 13 第 1 步一致。
   ⇒ **但**它的归一化 `norm_src` 会**删掉撇号**（`_PUNCT_RE = [^\w\s]`）
   ⇒ `'That'` → `'that'`；`"That's where we are today."` → `'thats where we are today'`
   ⇒ **rank1 成立** ⇒ 「假前缀」在产品层**同样会发生**。
   ⇒ 本脚本用**真实 MT 产物**量化：产品规则配出来的对里，**有多少是假前缀**。

Q2 🔴 **加「词边界」判据后，产品规则的配对结果会变吗？会不会更好？**
   ⇒ 独立判据 = **段号单调性**（`final.seg >= draft.seg`）：
      方案 C 的物理语义 = 「草稿是段 N 的尾半句，正式稿是凑齐后（段 N 或更晚）的整句」
      ⇒ 配到**更早**的段 ⇒ **必错**。
   ⇒ 该判据来自**产品语义**，不依赖任何一套匹配规则 ⇒ 可作裁判。

Q3 ✅ **产品侧「假前缀」是否会造成用户可见的错误？**
   ⇒ 分三层看：
     ① **配对层**：假前缀是否真的被配到远处？
     ② **渲染层**：错配后，草稿行显示什么？正式稿的译文会不会**丢失**或**重复**？
     ③ **不变式层**：渲染层 4 条不变式（原文守恒 / 替换不重复 / 未替换草稿保留 /
        同句只出现一次）**是否被破坏**。
   ⇒ 特别查：`DRAFT::That` 若被配到 seg 107 的 `That's where we are today.`，
     则 **seg 22 的正式稿**（`That does not mean we won't use external options…`）
     **不再被任何草稿占用** ⇒ 它的译文会**留在段聚合里** ⇒ 用户看到的是
     「浅色草稿行 + 正式稿行**同时**出现」⇒ **可能是重复显示**。

====================================================================
纪律
====================================================================
🔴 **不 import 被测模块**（`live_caption_app.py` 顶部 import numpy/openvino
   ⇒ import 阶段就可能 abort）⇒ 本脚本只 import **纯 stdlib** 的
   `caption_render`（只含 `re`）。
🔴 **不跑推理 / 不测速 / 不占 GPU / 不取机器锁 / 不调 MiniMax**
🔴 **只读** MT 产物，**不写** MT 目录、不写客户包。
🔴 **不 import `translator.py`**（MT 管辖，import 会连带 numpy）。
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import caption_render as CR      # noqa: E402  纯 stdlib

MT_ART = r'C:\Users\Trekker-PTL\hy_bench\runs\c111_half\c111_v5_ts10_nopunct.json'
OUT = os.path.join(HERE, 'app053_draft_prefix_boundary_evidence.json')

_results = []


def check(group, name, ok, detail=''):
    _results.append({'group': group, 'name': name,
                     'ok': bool(ok), 'detail': detail})
    print(('  PASS ' if ok else '  FAIL ') + f'[{group}] {name}'
          + (f' — {detail}' if detail else ''))
    return bool(ok)


# ══════════════════════════════════════════════════════════════════════
# 归一化：三种口径
# ══════════════════════════════════════════════════════════════════════
def norm_product(s):
    """**产品口径**：`caption_render.norm_src`（去标点 + 折叠空白 + 小写）。

    🔴 撇号会被 `_PUNCT_RE = [^\\w\\s]` **删掉** ⇒ `'That'` 与 `'That's'`
       的前缀关系**成立** ⇒ 假前缀的根源就在这里。
    """
    return CR.norm_src(s)


def norm_keep_space(s):
    """**通知 13 口径**：只去空白、**保留标点**（含撇号）⇒ 为词边界检查做准备。

    ⚠️ 注意：通知 13 §13.4 第 2 步说「前缀之后紧跟的字符不能是字母/数字；
       也不能是『撇号 + 字母数字』」⇒ 需要知道**前缀之后紧跟的那个字符**
       ⇒ 归一化时**不能把空格也吃掉**（否则单词会被粘在一起，词边界就废了）
       ⇒ 这里用「折叠连续空白为单个空格 + strip」，**保留标点**。
    """
    return re.sub(r'\s+', ' ', (s or '')).strip()


_WORDCHAR = re.compile(r'[0-9A-Za-z]', re.UNICODE)
_APOS = "'"


def word_boundary_ok(prefix_norm: str, full_norm: str) -> bool:
    """🔴 **词边界判据**（通知 13 §13.4 第 2 步）。

    前缀之后紧跟的字符**不能是字母/数字**（`that` + `s` ✗，`that ` ✓）；
    也不能是「撇号 + 字母数字」（`that` + `'s` ✗）。
    """
    if not prefix_norm or not full_norm.startswith(prefix_norm):
        return False
    rest = full_norm[len(prefix_norm):]
    if not rest:
        return True                       # 完全相等 ⇒ 词边界平凡成立
    c0 = rest[0]
    if _WORDCHAR.match(c0):
        return False                      # `that` + `s` ⇒ 假前缀
    if c0 == _APOS:
        # 撇号后紧跟字母/数字 ⇒ 假前缀（`That` vs `That's`）
        if len(rest) >= 2 and _WORDCHAR.match(rest[1]):
            return False
    return True


def make_matcher(norm_fn, boundary=False, min_len=0, max_seg_span=None):
    """按给定归一化 + 可选词边界 + 可选最短草稿长度门槛 + 可选跨段上限，配对草稿→正式稿。

    规则与产品 `match_draft_to_final` **同构**（三级关系 + 反向拒绝 + 全局一对一
    + 排序键 `(rank, -len(dn), len(fn), di, fi)`），只把归一化/词边界/最短门槛/跨段上限换成参数。

    🔴 `max_seg_span`：**拟实现的新增判据**（依据 `caption_render.py` 模块 docstring
       已写明的语义：「草稿单元的 seg = 段尾半句所在的那一段；
       正式稿单元的 seg = 凑齐后提交的那一段」⇒ 两者必相邻）。
    """
    def match(drafts, finals):
        cands = []
        for di, d in enumerate(drafts):
            dn = norm_fn(d.get('src', ''))
            if not dn:
                continue
            if min_len and len(dn) < min_len:
                continue
            ds = d.get('seg')
            for fi, f in enumerate(finals):
                fn = norm_fn(f.get('src', ''))
                if not fn:
                    continue
                if dn == fn:
                    rank = 0
                elif fn.startswith(dn) and len(fn) > len(dn):
                    if boundary and not word_boundary_ok(dn, fn):
                        continue
                    rank = 1
                elif dn in fn:
                    if boundary and not word_boundary_ok(dn, fn):
                        # 子串情形下词边界应检查**前缀位置**；
                        # 简化：只在 rank1 生效时强检（见下方 note）
                        pass
                    rank = 2
                else:
                    continue
                # 🔴 **跨段上限**（拟新增判据）：草稿在段 N，正式稿必在段 N/N+1
                fs = f.get('seg')
                if (max_seg_span is not None
                        and isinstance(ds, int) and isinstance(fs, int)
                        and (fs - ds) > max_seg_span):
                    continue
                cands.append((rank, -len(dn), len(fn), di, fi))
        cands.sort()
        out, used = {}, set()
        for _r, _nd, _nf, di, fi in cands:
            if di in out or fi in used:
                continue
            out[di] = fi
            used.add(fi)
        return out
    return match


# ══════════════════════════════════════════════════════════════════════
# 独立判据
# ══════════════════════════════════════════════════════════════════════
def judge(drafts, finals, m):
    """用**段号单调性**（产品语义）评判一套规则。"""
    def seg_of(u):
        s = u.get('seg')
        return s if isinstance(s, int) else None
    n_violate = 0
    viol = []
    used = {}
    for di, fi in m.items():
        ds, fs = seg_of(drafts[di]), seg_of(finals[fi])
        if fs is None:
            continue
        if ds is None:
            continue
        if fs < ds:
            n_violate += 1
            viol.append({'draft_key': drafts[di].get('key'),
                         'draft_seg': ds, 'final_seg': fs,
                         'draft_src': (drafts[di].get('src') or '')[:80],
                         'final_src': (finals[fi].get('src') or '')[:80]})
        used.setdefault(fi, []).append(di)
    n_dup = sum(1 for fi, ds in used.items() if len(ds) > 1)
    return {
        'n_paired': len(m),
        'n_unpaired_draft': len(drafts) - len(m),
        'coverage_rate': round(len(m) / float(len(drafts)), 4) if drafts else 0.0,
        'n_seg_violation': n_violate,
        'n_final_used_by_multi_draft': n_dup,
        'violations_sample': viol[:10],
    }


def is_false_prefix(draft_src, final_src, norm_fn):
    """判定「草稿→正式稿」是否为**假前缀**：
    归一化后正式稿以草稿为前缀，但**词边界不成立**（`That` vs `That's`）。
    """
    dn, fn = norm_fn(draft_src), norm_fn(final_src)
    if not dn or not fn or not fn.startswith(dn) or len(fn) <= len(dn):
        return False
    return not word_boundary_ok(dn, fn)


def main():
    t0 = time.time()
    art = json.load(io.open(MT_ART, encoding='utf-8'))
    arm = art['results']['C_draft']
    units = arm['units']
    drafts = [u for u in units if (u.get('kind') or 'final') == 'draft']
    finals = [u for u in units if (u.get('kind') or 'final') != 'draft']
    mt_gap = arm.get('draft_gap') or {}

    print(f'== 源产物：{MT_ART}')
    print(f'   臂={arm.get("arm", "C_draft")}  units={len(units)} '
          f'draft={len(drafts)} final={len(finals)}')
    print(f'   MT 自报 draft_gap：n_pairs={mt_gap.get("n_pairs")} '
          f'gap_max={mt_gap.get("gap_max")} gap_p95={mt_gap.get("gap_p95")}')

    # ── 三套规则 ────────────────────────────────────────────────────
    rules = {
        'product_now': make_matcher(norm_product),                        # 现状
        'product_boundary': make_matcher(norm_keep_space, boundary=True),  # +词边界
        'mt_notice13': make_matcher(norm_keep_space, boundary=True,
                                     min_len=10),                     # 通知13 全三步
        # 🔴 **拟实现的修法**：只在现版规则上加「跨段上限」，**不动归一化**
        #    （保留短草稿替换能力，§41.3.5 的设计意图）⇒ 覆盖率零损失。
        'product_segcap2': make_matcher(norm_product, max_seg_span=2),
        # 对照：词边界 + 跨段上限（两者叠加）
        'product_boundary_segcap2': make_matcher(norm_keep_space, boundary=True,
                                                  max_seg_span=2),
    }
    maps = {k: v(drafts, finals) for k, v in rules.items()}
    judged = {k: judge(drafts, finals, m) for k, m in maps.items()}

    # ── Q1：产品规则里的假前缀 ───────────────────────────────────────
    prod_false = []
    for di, fi in maps['product_now'].items():
        if is_false_prefix(drafts[di].get('src'), finals[fi].get('src'),
                           norm_product):
            prod_false.append({
                'draft_key': drafts[di].get('key'),
                'draft_seg': drafts[di].get('seg'),
                'draft_src': (drafts[di].get('src') or '')[:80],
                'final_key': finals[fi].get('key'),
                'final_seg': finals[fi].get('seg'),
                'final_src': (finals[fi].get('src') or '')[:80],
            })
    print(f'\n== Q1 产品规则的假前缀：{len(prod_false)} / {len(maps["product_now"])} 对')

    # 🔴 **跨段距离**（通知 13 的真实病灶）：假前缀配到的正式稿离草稿有多远。
    #    ⇒ 方向性没错（final.seg >= draft.seg）⇒ 倒流 0，
    #    但**跨了几十段** ⇒ 替换间隔被拉长到几百秒。
    prod_seg_span = 0
    for item in prod_false:
        ds, fs = item.get('draft_seg'), item.get('final_seg')
        if isinstance(ds, int) and isinstance(fs, int):
            prod_seg_span = max(prod_seg_span, fs - ds)
    if prod_false:
        print(f'   假前缀跨段距离 = {prod_seg_span} 段'
              f'（草稿 seg {prod_false[0]["draft_seg"]} → '
              f'正式 seg {prod_false[0]["final_seg"]}）')

    # 各规则的**跨段距离分布**（配对质量的连续指标）
    def seg_span_stats(m):
        spans = []
        for di, fi in m.items():
            ds, fs = drafts[di].get('seg'), finals[fi].get('seg')
            if isinstance(ds, int) and isinstance(fs, int):
                spans.append(fs - ds)
        if not spans:
            return {'n': 0}
        spans_sorted = sorted(spans)
        return {
            'n': len(spans),
            'max': max(spans),
            'p95': spans_sorted[min(len(spans) - 1, int(len(spans) * 0.95))],
            'median': spans_sorted[len(spans) // 2],
            'n_gt_10': sum(1 for s in spans if s > 10),
        }

    span_stats = {k: seg_span_stats(m) for k, m in maps.items()}
    for k, v in span_stats.items():
        print(f'   跨段距离[{k}]：{v}')

    # ── Q2：加词边界后的变化 ─────────────────────────────────────────
    def keyset(m):
        return {(drafts[di].get('key'), finals[fi].get('key'))
                for di, fi in m.items()}
    ks = {k: keyset(v) for k, v in maps.items()}
    only_prod = sorted(ks['product_now'] - ks['product_boundary'])
    only_bnd = sorted(ks['product_boundary'] - ks['product_now'])

    # ── Q3：渲染层后果（③ 层检查）────────────────────────────────────
    # 只用**工作区**的 caption_render（HEAD 与工作区一致，见 §43）
    def render_probe(di, fi):
        """把「一对草稿/正式稿」喂进渲染层，看输出行里是否出现重复/丢失。"""
        d = dict(drafts[di]); d['kind'] = 'draft'
        f = dict(finals[fi]); f['kind'] = 'final'
        blocks = [f.get('src') or '']
        lines = CR.render_lines(blocks, [f], drafts=[d], granularity='seg')
        return lines

    render_samples = []
    for item in prod_false[:6]:
        di = next((i for i, d in enumerate(drafts)
                   if d.get('key') == item['draft_key']), None)
        fi = maps['product_now'].get(di) if di is not None else None
        if di is None or fi is None:
            continue
        lines = render_probe(di, fi)
        mt_texts = [l['text'] for l in lines if l['kind'] in ('mt', 'mt_draft')]
        render_samples.append({
            'draft_key': item['draft_key'],
            'draft_seg': item['draft_seg'],
            'matched_final_seg': item['final_seg'],
            'draft_src': item['draft_src'],
            'final_src': item['final_src'],
            'render_lines': lines,
            'n_mt_lines': len(mt_texts),
            'duplicate_mt': len(mt_texts) != len(set(mt_texts)),
            # 🔴 正式稿所在段的 seg 与草稿段是否一致 ⇒ 不一致 = 译文被搬到别的段
            'misplaced': item['final_seg'] != item['draft_seg'],
        })

    # ── 断言 ────────────────────────────────────────────────────────
    print('\n== 断言 ==')
    check('Q1', '产品规则存在假前缀（撇号被删 ⇒ That/That\'s 前缀成立）',
          len(prod_false) > 0,
          f'{len(prod_false)} 对为假前缀')
    # 🔴 **修正（2026-10-26 02:00）**：本断言首版写的是「假前缀 ⇒ 段号倒流」，
    #    **前提错误** ⇒ 实测 0 倒流。真实机制是：
    #    「假前缀」配到的是**更晚**的段（seg 107 > seg 22）⇒ **方向性没错**，
    #    错在**跨段距离极远**（85 段）⇒ 替换间隔被拉长到几百秒。
    #    ⇒ 判据改为「跨段距离」，段号倒流单独作为**已有保证**保留（应为 0）。
    check('Q1', '产品规则的段号倒流为 0（方向性成立）',
          judged['product_now']['n_seg_violation'] == 0,
          f"倒流 {judged['product_now']['n_seg_violation']} 条")
    check('Q1', '假前缀配对跨段距离异常大（通知 13 的真实病灶）',
          prod_seg_span >= 10,
          f'假前缀跨段距离 = {prod_seg_span} 段'
          f'（草稿 seg {prod_false[0]["draft_seg"]} → 正式 seg '
          f'{prod_false[0]["final_seg"]}）' if prod_false else '无假前缀')
    check('Q2', '加词边界后假前缀被清除',
          all(not is_false_prefix(drafts[di].get('src'), finals[fi].get('src'),
                                  norm_keep_space)
              for di, fi in maps['product_boundary'].items()),
          'product_boundary 无假前缀')
    check('Q2', '加词边界后段号倒流不增加',
          judged['product_boundary']['n_seg_violation']
          <= judged['product_now']['n_seg_violation'],
          f"{judged['product_now']['n_seg_violation']} → "
          f"{judged['product_boundary']['n_seg_violation']}")
    check('Q2', '加词边界后配对覆盖率不显著下降（≥ 现版 −3pp）',
          judged['product_boundary']['coverage_rate']
          >= judged['product_now']['coverage_rate'] - 0.03,
          f"{judged['product_now']['coverage_rate']} → "
          f"{judged['product_boundary']['coverage_rate']}")
    check('Q3', '渲染层未出现重复译文行（假前缀不造成重复显示）',
          all(not s['duplicate_mt'] for s in render_samples),
          f'{len(render_samples)} 例抽样，重复 '
          f'{sum(1 for s in render_samples if s["duplicate_mt"])} 例')
    # 🔴 **Q3 的真实后果**：假前缀配对 ⇒ **正式稿的译文被搬到草稿那一行**
    #    ⇒ 正式稿所在的那一段**自己那行没有译文**，而远处（seg 107）
    #    的那一行**多出一句不相关的译文** ⇒ 用户可见的错位。
    check('Q3', '假前缀配对导致正式稿译文出现在错误的段（用户可见错位）',
          any(s['matched_final_seg'] != s['draft_seg'] for s in render_samples),
          '正式稿 seg 与草稿 seg 不一致 ⇒ 译文被搬到别的段'
          if any(s['matched_final_seg'] != s['draft_seg']
                 for s in render_samples) else '未观察到错位')
    # 🔴 加词边界后，错位应当消失
    def boundary_misplaced(m):
        n = 0
        for di, fi in m.items():
            ds, fs = drafts[di].get('seg'), finals[fi].get('seg')
            if isinstance(ds, int) and isinstance(fs, int) and fs - ds > 10:
                n += 1
        return n
    # 🔴🔴 **修正（2026-10-26 02:08）**：这条断言首版写的是「加词边界后错配消失」，
    #    **实测 FAIL** ⇒ 说明**词边界抓不住 `Okay`**（`Okay`+`,` 词边界合法）
    #    ⇒ 这本身是**要记录的发现**，不是待修的失败 ⇒ 改为「盲区存在性」断言，
    #    真正的修法由下面的 `FIX` 组断言覆盖。
    check('Q3', '🔴 「词边界」单独用**不足以**消除跨段错配（已知盲区）',
          boundary_misplaced(maps['product_boundary']) > 0,
          f"加词边界后仍有 {boundary_misplaced(maps['product_boundary'])} 条 "
          f'跨段 > 10 ⇒ 词边界**抓不住** `Okay`（逗号 ⇒ 词边界合法）')
    # 🔴🔴 **修正（2026-10-26 02:05）**：上一条断言**实测 FAIL**（1 → 1）
    #    ⇒ **「词边界」判据抓不住 `Okay`**（`Okay` + `,` ⇒ 词边界**合法**）
    #    ⇒ 通知 13 §13.3 点名的 `Okay`（seg 6 → seg 39）**词边界也抓不住**。
    #    ⇒ 真正的病灶是「**短草稿 + 跨段距离**」，必须用**跨段上限**判据。
    check('Q3', '🔴 词边界判据抓不住 `Okay`（通知 13 口径的已知盲区）',
          boundary_misplaced(maps['product_boundary']) > 0,
          f"加词边界后仍有 {boundary_misplaced(maps['product_boundary'])} 条 "
          f'跨段 > 10（`Okay` seg6→seg39 词边界合法 ⇒ 抓不住）')

    # ── 拟实现的修法：跨段上限 ───────────────────────────────────────
    check('FIX', '跨段上限 2 ⇒ 跨段距离 > 10 的错配归零',
          boundary_misplaced(maps['product_segcap2']) == 0,
          f"现版 {boundary_misplaced(maps['product_now'])} 条 → "
          f"加跨段上限 {boundary_misplaced(maps['product_segcap2'])} 条")
    check('FIX', '跨段上限 2 ⇒ max_span 收敛到 ≤ 2',
          span_stats['product_segcap2'].get('max', 99) <= 2,
          f"max_span {span_stats['product_now'].get('max')} → "
          f"{span_stats['product_segcap2'].get('max')}")
    check('FIX', '跨段上限 2 ⇒ 覆盖率**零损失**（配对数与现版相同）',
          judged['product_segcap2']['n_paired']
          == judged['product_now']['n_paired'],
          f"{judged['product_now']['n_paired']} → "
          f"{judged['product_segcap2']['n_paired']} 对")
    check('FIX', '跨段上限 2 ⇒ 段号倒流仍为 0、全局一对一不破',
          judged['product_segcap2']['n_seg_violation'] == 0
          and judged['product_segcap2']['n_final_used_by_multi_draft'] == 0,
          f"倒流 {judged['product_segcap2']['n_seg_violation']} / "
          f"重复 {judged['product_segcap2']['n_final_used_by_multi_draft']}")
    check('FIX', '跨段上限 2 ⇒ 未破坏「短草稿替换能力」（§41.3.5 设计意图）',
          any(len((drafts[di].get('src') or '')) < 10
              for di in maps['product_segcap2']),
          f"短草稿仍被替换："
          f"{sum(1 for di in maps['product_segcap2'] if len((drafts[di].get('src') or '')) < 10)}"
          f' 条（< 10 字符）')
    # 🔴 `Okay` 在跨段上限下**不再被错配到 33 段外**；
    #    事实：seg 7（`Okay` 真正所属段）**根本没有正式稿**（只有草稿）
    #    ⇒ `Okay` 的「正确替换对象」在本产物中**不存在**
    #    ⇒ 它只能配到 span=2 的次优对象，或保持未配对 ⇒ **两者都比错配好**。
    ok_key = 'DRAFT::Okay'
    ok_wrong = any(drafts[di].get('key') == ok_key
                   and (finals[fi].get('src') or '') == 'Okay, next slide.'
                   for di, fi in maps['product_segcap2'].items())
    ok_span = None
    for di, fi in maps['product_segcap2'].items():
        if drafts[di].get('key') == ok_key:
            ds, fs = drafts[di].get('seg'), finals[fi].get('seg')
            if isinstance(ds, int) and isinstance(fs, int):
                ok_span = fs - ds
    check('FIX', '`Okay` 不再被错配到 33 段外（宁可配次优/未配对，也不错配）',
          not ok_wrong,
          f'`Okay` 错配到 `Okay, next slide.`={ok_wrong}；'
          f'现版 span={33} → 现规则 span={ok_span}'
          f'（seg 7 无正式稿 ⇒ 正确对象本不存在）')

    payload = {
        'task': 'MT 通知 13「假前缀」在 App 渲染层的实际影响（离线，真实 MT 产物）',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'discipline': {
            'no_model_import': True, 'no_inference': True, 'no_benchmark': True,
            'no_gpu': True, 'no_machine_lock': True, 'no_minimax': True,
            'mt_artifact_readonly': True, 'customer_pkg_readonly': True,
            'no_product_code_change': True,
        },
        'source': {
            'path': MT_ART,
            'bytes': os.path.getsize(MT_ART),
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(os.path.getmtime(MT_ART))),
            'arm': 'C_draft',
            'n_units': len(units),
            'n_draft': len(drafts),
            'n_final': len(finals),
            'mt_artifact_draft_gap': {k: mt_gap.get(k) for k in
                                      ('n_pairs', 'n_with_gap', 'gap_max',
                                       'gap_p50', 'gap_p95')},
        },
        'rules': {
            'product_now': 'caption_render.match_draft_to_final 同构'
                           '（norm_src 去标点 ⇒ 撇号被删 ⇒ 无词边界）',
            'product_boundary': '同上，但归一化保留标点 + 词边界判据',
            'mt_notice13': '通知 13 三步全做（正向前缀 + 词边界 + min_len=10）',
            'product_segcap2': '🔴 拟实现的修法：现版规则 + 跨段上限 2'
                               '（依据 caption_render 模块 docstring 已写明的'
                               '「草稿 seg = 段尾半句所在段；正式稿 seg = 凑齐后提交段」）',
            'product_boundary_segcap2': '词边界 + 跨段上限（叠加对照）',
        },
        'judged': judged,
        'q2_seg_span_stats': span_stats,
        'q1_product_false_prefix': {
            'n_false_prefix': len(prod_false),
            'n_paired_total': len(maps['product_now']),
            'samples': prod_false[:12],
        },
        'q2_boundary_delta': {
            'only_in_product_now': [list(x) for x in only_prod[:12]],
            'n_only_in_product_now': len(only_prod),
            'only_in_product_boundary': [list(x) for x in only_bnd[:12]],
            'n_only_in_product_boundary': len(only_bnd),
        },
        'q3_render_effect': {
            'n_sampled': len(render_samples),
            'samples': render_samples,
        },
        'summary': {
            'n_pass': sum(1 for r in _results if r['ok']),
            'n_total': len(_results),
            'verdict': 'PASS' if all(r['ok'] for r in _results) else 'FAIL',
            'elapsed_sec': round(time.time() - t0, 2),
        },
    }
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f'\n== 写入 {OUT}')
    print(f'== verdict = {payload["summary"]["verdict"]} '
          f'({payload["summary"]["n_pass"]}/{payload["summary"]["n_total"]})')
    return 0 if payload['summary']['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
