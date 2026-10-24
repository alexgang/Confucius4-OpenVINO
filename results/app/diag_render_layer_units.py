# -*- coding: utf-8 -*-
"""
APP §26 诊断：UNIT 机制下 App 渲染层的三处缺口（MT 通知 4.3 点名）的**离线量化**。

🔴 铁律：
  - **不 import 被测模块**（`import translator` ⇒ 连带 numpy/OpenBLAS ⇒ 内存占满时 import 阶段就 abort）
    ⇒ 本脚本只**读 MT 已落盘的 v4 产物 JSON**，不碰 `translator.py` / `live_caption_app.py`。
  - **不跑推理、不跑测速、不占 GPU、不取共享机器锁**（纯读文件 + 纯算术）。
  - 参照语料：MT 的 `hy_bench/runs/c111_half/c111_variants_v4_SPE.json` 的 **BASE_unit 臂**
    （真实 61 分钟会议回放，225 段 / 712 句单元 / chrF 89.7225 / 守恒 41895/41895）。

要回答的问题（MT 通知 4.3 表里的三处 + 一个 App 侧自查）：
  Q1 `_mt_of(seg)` = `mt_of_seg(seg)` 在 UNIT 下会不会让某段**永远没有〔译〕行**？
  Q2 `_save_text()`（原文行 + 〔译〕行）按段渲染 ⇒ 「一句原文对一句译文」拿不到，
     实际输出里「原文行数 : 译文行数」是多少？
  Q3 屏幕字幕 overlay 的「最近 3 段译文」在 UNIT 下取到几段？
  Q4 TTS 链：outbox 里 kind=='final' 的条目数 vs 句单元数（确认「要朗读的译文必须以 'final' 出 outbox」成立）

输出：`results/app/render_layer_units_diag.json`（原始字段全部保留）
"""
import json
import os
import sys
from collections import Counter, defaultdict

PROD = r'C:\Users\Trekker-PTL\hy_bench\runs\c111_half\c111_variants_v4_SPE.json'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\render_layer_units_diag.json'


def load():
    with open(PROD, encoding='utf-8') as f:
        return json.load(f)


def main():
    rep = {'source_product': PROD, 'product_mtime': os.path.getmtime(PROD),
           'product_bytes': os.path.getsize(PROD)}
    d = load()
    rep['product_top_keys'] = list(d.keys())
    rep['corpus'] = d.get('corpus')
    rep['n_seg'] = d.get('n_seg')
    rep['arms_available'] = list(d.get('results', {}).keys())

    b = d['results'].get('BASE_unit')
    if b is None:
        rep['verdict'] = 'BASE_unit 臂尚未落盘 ⇒ 无法量化'
        dump(rep)
        return

    units = b.get('units') or []
    outbox = b.get('outbox') or []
    rep['base_arm_raw'] = {k: b[k] for k in (
        'n_units', 'n_formal', 'n_outbox', 'kinds', 'n_translate_calls',
        'n_final', 'n_draft', 'miss_rate', 'n_unit_missing', 'n_timeout',
        'src_chars', 'orig_chars', 'src_kept', 'n_partial')}
    rep['base_arm_coverage_raw'] = b.get('coverage')
    rep['base_arm_quality_raw'] = {k: v for k, v in (b.get('quality') or {}).items()
                                   if k != 'pairs'}
    rep['n_units_actual'] = len(units)
    rep['n_outbox_actual'] = len(outbox)

    # ---------- 单元结构 ----------
    u0 = units[0] if units else {}
    rep['unit_sample_keys'] = list(u0.keys()) if isinstance(u0, dict) else None
    rep['unit_sample'] = {k: u0.get(k) for k in ('key', 'seg', 'src', 'mt')} if isinstance(u0, dict) else None

    def useg(u, k, d=None):
        return u.get(k, d) if isinstance(u, dict) else d

    segs = [useg(u, 'seg') for u in units]
    srcs = [useg(u, 'src') or '' for u in units]
    mts = [useg(u, 'mt') for u in units]
    keys = [useg(u, 'key') for u in units]

    # ---------- Q1：mt_of_seg(seg) 能否为空 ----------
    # 复刻 translator.py::mt_of_seg 的语义：seg_keys[seg] = 该段提交的句单元 key 列表
    # （单位只登记**提交它的那一段**，见 translator.py L1091-1105）
    # 🔴 实测：product 的 `seg` 字段是**字符串**（'0' / '1' / ...）⇒ 统一转 int 排序
    def norm_seg(s):
        try:
            return int(s)
        except (TypeError, ValueError):
            return s

    seg_keys = defaultdict(list)
    for u in units:
        s = norm_seg(useg(u, 'seg'))
        k = useg(u, 'key')
        if s is not None and k is not None and k not in seg_keys[s]:
            seg_keys[s].append(k)
    # done 字典 = 有译文（有 mt）的 key
    done = {useg(u, 'key') for u in units if useg(u, 'mt') is not None}

    def mt_of_seg(seg):
        ks = seg_keys.get(seg)
        if not ks:
            return None
        parts = [('X' if k in done else '') for k in ks]
        out = ' '.join(p for p in parts if p).strip()
        return out or None

    all_segs = sorted(set(s for s in (norm_seg(x) for x in segs) if s is not None))
    n_seg_units = len(all_segs)
    seg_with_units = len(seg_keys)
    empty_segs = [s for s in all_segs if not seg_keys.get(s)]
    seg_no_mt = [s for s in all_segs if seg_keys.get(s) and mt_of_seg(s) is None]
    n_seg_product = d.get('n_seg')
    n_seg_without_any_unit = (n_seg_product - seg_with_units) if isinstance(n_seg_product, int) else None
    rep['Q1_mt_of_seg'] = {
        'product_n_seg': n_seg_product,
        'n_unique_segments_in_units': n_seg_units,
        'n_segments_with_units': seg_with_units,
        'n_segments_without_any_unit': n_seg_without_any_unit,
        'n_segments_empty_seg_keys': len(empty_segs),
        'empty_seg_examples': empty_segs[:10],
        'n_segments_where_mt_of_seg_is_none': len(seg_no_mt),
        'seg_no_mt_examples': seg_no_mt[:10],
        'note': '① seg 字段实测是字符串，已转 int；'
                '② 「本段没有句单元」= 该段原文整段是半句 ⇒ 它的文字被并入**下一段**的句单元 '
                '⇒ 该段在 _save_text()/_render() 里**永远不输出〔译〕行**（= 少一行译文）；'
                '③ 全部句单元的 src 拼接仍覆盖 41895 字（守恒成立）⇒ 不是丢原文，是**渲染层没把'
                '「跨段合成的句子」按句拆出来显示**',
    }

    # ---------- Q2：_save_text 的「原文行 : 〔译〕行」配比 ----------
    n_orig_lines = len(all_segs)
    n_mt_lines = sum(1 for s in all_segs if mt_of_seg(s) is not None)
    rep['Q2_save_text_ratio'] = {
        'n_original_lines': n_orig_lines,
        'n_translation_lines': n_mt_lines,
        'lines_without_translation': n_orig_lines - n_mt_lines,
        'ratio_translation_per_original': round(n_mt_lines / n_orig_lines, 4) if n_orig_lines else None,
        'n_units_total': len(units),
        'units_not_represented_as_own_line': len(units) - n_mt_lines,
        'note': '旧 _save_text() 按**段**输出 ⇒ 译文行数 ≤ 段数；UNIT 下句单元数 %d '
                '⇒ 「一句原文对一句译文」拿不到（MT 通知 4.3 表 L2351-2366）' % len(units),
    }

    # ---------- Q3：overlay 最近 3 段 ----------
    tail = all_segs[-3:]
    tail_with_mt = [s for s in tail if mt_of_seg(s) is not None]
    rep['Q3_overlay_tail3'] = {
        'tail_segments': tail,
        'tail_segments_with_translation': tail_with_mt,
        'n_tail_with_translation': len(tail_with_mt),
        'note': 'overlay 取「最近 3 段的译文」（live_caption_app.py L2499-2502）'
                '⇒ UNIT 下若最近 3 段里有整段半句 ⇒ 屏幕字幕译文更少',
    }

    # ---------- Q4：outbox 的 kind / final ----------
    kd = Counter()
    ok = []
    for o in outbox:
        if isinstance(o, dict):
            k = o.get('kind')
        elif isinstance(o, (list, tuple)) and o:
            k = o[0]          # 实测：outbox 是三元列表 [kind, src, mt]
        else:
            k = None
        kd[k] += 1
        if k == 'final':
            ok.append(o)
    rep['Q4_outbox_kind'] = {
        'kind_counter': {str(k): v for k, v in kd.items()},
        'n_final': kd.get('final', 0),
        'n_units': len(units),
        'n_final_vs_units_gap': len(units) - kd.get('final', 0),
        'outbox_shape': 'list of [kind, src, mt]（实测）' if outbox and isinstance(outbox[0], (list, tuple)) else None,
        'n_non_final': len(outbox) - kd.get('final', 0),
        'note': 'TTS 链只提交 kind==\'final\'（live_caption_app.py L2314）⇒ '
                '「要朗读的译文必须以 final 出 outbox」在 UNIT 下成立',
    }

    # ---------- 附：units 里 mt 为 None 的单元（还在翻译） ----------
    n_none = sum(1 for m in mts if m is None)
    rep['units_without_mt'] = {
        'n': n_none,
        'n_total': len(units),
        'note': 'mt 为 None = 该句单元还没出译文（翻译在途）',
    }

    # ---------- 附：src 守恒（去空白口径）----------
    def strip_ws(s):
        return ''.join((s or '').split())
    tot_src = sum(len(strip_ws(s)) for s in srcs)
    rep['src_conservation'] = {
        'sum_src_chars_no_ws': tot_src,
        'product_orig_chars': b.get('orig_chars'),
        'product_src_chars': b.get('src_chars'),
        'match_orig_chars': tot_src == b.get('orig_chars'),
        'note': '原文守恒用「去空白字符数」口径（MEMORY 铁律：否则空白差异被误报成丢失）',
    }

    # ---------- 附：重复句（同一句在多个段出现）⇒ 显示层会重复显示 ----------
    # 🔴 MEMORY 铁律：「翻译去重」≠「显示去重」⇒ 同一句翻一次，但**每次出现都要建显示单元**
    by_src = defaultdict(list)
    for u in units:
        by_src[useg(u, 'src') or ''].append(norm_seg(useg(u, 'seg')))
    dup_srcs = {s: v for s, v in by_src.items() if len(v) > 1}
    rep['duplicate_units'] = {
        'n_unique_src': len(by_src),
        'n_units': len(units),
        'n_src_appearing_more_than_once': len(dup_srcs),
        'n_extra_display_units_from_duplicates': len(units) - len(by_src),
        'max_repeat_of_one_src': max((len(v) for v in by_src.values()), default=0),
        'examples': [{'src': (s[:60] + '…') if len(s) > 60 else s, 'segs': v}
                     for s, v in list(dup_srcs.items())[:5]],
        'note': '翻译调用 674 < 句单元 712 ⇒ 38 个显示单元复用已有译文（= MT §56 缺陷①的修复方向）；'
                '⇒ 渲染层若**按 src 去重显示**就会丢这 38 次出现 ⇒ 必须按 units 逐条显示',
    }

    n_dup_extra = len(units) - len(by_src)
    rep['verdict'] = {
        'Q1_segments_without_any_unit': n_seg_without_any_unit,
        'Q1_segments_with_no_translation_line': len(seg_no_mt),
        'Q2_lines_translation_per_original': rep['Q2_save_text_ratio']['ratio_translation_per_original'],
        'Q2_units_merged_into_other_lines': len(units) - n_mt_lines,
        'Q4_final_count': kd.get('final', 0),
        'Q4_display_units_beyond_translate_calls': n_dup_extra,
        'src_conservation_ok': tot_src == b.get('orig_chars'),
        'conclusion': '渲染层三处（_mt_of / _save_text / CLI run_cli）仍是「按段」粒度：'
                      '① %d 段在 UNIT 下拿不到任何句单元 ⇒ 永远没有〔译〕行；'
                      '② %d 个句单元被挤进 %d 行译文（平均 %.1f 句/行）⇒ 「一句原文对一句译文」拿不到；'
                      '③ %d 个显示单元复用已有译文（翻译调用 674）⇒ 渲染层若按 src 去重显示会丢这 %d 次出现；'
                      '④ 原文守恒 %s ⇒ 不是丢原文，是渲染层粒度问题'
                      % (n_seg_without_any_unit, len(units) - n_mt_lines, n_mt_lines,
                         (len(units) / n_mt_lines) if n_mt_lines else 0,
                         n_dup_extra, n_dup_extra,
                         'OK(41895/41895)' if tot_src == b.get('orig_chars') else 'FAIL'),
    }

    dump(rep)


def dump(rep):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('written:', OUT, os.path.getsize(OUT), 'B')
    print(json.dumps(rep.get('verdict', {}), ensure_ascii=False, indent=2))
    for k in ('Q1_mt_of_seg', 'Q2_save_text_ratio', 'Q3_overlay_tail3', 'Q4_outbox_kind',
              'src_conservation', 'units_without_mt'):
        print('\n==', k, '==')
        print(json.dumps(rep.get(k, {}), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.exit(main())
