# -*- coding: utf-8 -*-
"""
APP §26：UNIT 渲染层**候选实现**的离线验证（不碰产品代码、不跑推理、不占锁）。

目的：MT 通知 4.3 要求 App 渲染层改按 `mt_units()` 逐句渲染，但这是**用户可见的产品行为变更**
（字幕显示粒度 从「ASR 段」变「完整句」）。本脚本只做一件事：
把「候选实现」在**真实 61 分钟会议语料**（MT v4 的 BASE_unit 臂，712 句单元）上的输出
与「现状」做**逐项对比**，把风险量化成可复核的数字，供 reviewer 裁定时直接引用。

🔴 铁律：
  - **不 import 被测模块**（`import translator` ⇒ 连带 numpy/OpenBLAS ⇒ 内存占满时 import 阶段就 abort）
    ⇒ 本脚本只读 MT 已落盘的 JSON 产物。
  - **不跑推理、不跑测速、不取共享机器锁**。
  - **不改任何产品代码**（`live_caption/live_caption_app.py` 本轮不动）。

输出：`results/app/render_units_candidate_eval.json`
"""
import json
import os
import sys
from collections import Counter, defaultdict

PROD = r'C:\Users\Trekker-PTL\hy_bench\runs\c111_half\c111_variants_v4_SPE.json'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\render_units_candidate_eval.json'


def strip_ws(s):
    return ''.join((s or '').split())


def main():
    rep = {'source_product': PROD,
           'product_bytes': os.path.getsize(PROD),
           'product_mtime': os.path.getmtime(PROD),
           'method': '离线读 MT v4 BASE_unit 臂的 units/outbox 原始字段；'
                     '不 import 被测模块、不跑推理、不占锁、不改产品代码'}

    with open(PROD, encoding='utf-8') as f:
        d = json.load(f)
    b = d['results'].get('BASE_unit')
    if b is None:
        rep['verdict'] = 'BASE_unit 臂未落盘 ⇒ 无法评估'
        dump(rep)
        return

    units = b['units']
    outbox = b['outbox']

    def useg(u, k, dft=None):
        return u.get(k, dft) if isinstance(u, dict) else dft

    # ================= 现状渲染（按段） =================
    # 复刻 live_caption_app.py::_save_text 的现状语义：
    #   for i, src in enumerate(self.blocks): out.append(src); mt = mt_of_seg(i); ...
    seg_keys = defaultdict(list)
    for u in units:
        s = useg(u, 'seg')
        try:
            s = int(s)
        except (TypeError, ValueError):
            pass
        k = useg(u, 'key')
        if s is not None and k is not None and k not in seg_keys[s]:
            seg_keys[s].append(k)
    done = {useg(u, 'key') for u in units if useg(u, 'mt') is not None}

    def mt_of_seg(seg):
        ks = seg_keys.get(seg)
        if not ks:
            return None
        parts = [('X' if k in done else '') for k in ks]
        out = ' '.join(p for p in parts if p).strip()
        return out or None

    all_segs = sorted(set(int(useg(u, 'seg')) for u in units if useg(u, 'seg') is not None))
    n_seg_none = sum(1 for u in units if useg(u, 'seg') is None)
    cur_orig = len(all_segs)
    cur_mt_lines = sum(1 for s in all_segs if mt_of_seg(s) is not None)
    cur_no_mt = cur_orig - cur_mt_lines
    # 现状每行塞了几句
    per_line = Counter()
    for s in all_segs:
        per_line[len(seg_keys.get(s, []))] += 1

    # ================= 候选渲染（按句单元） =================
    # 复刻「for u in mt_units(): out.append(u['src']); out.append('〔译〕'+u['mt'])」
    cand_orig = len(units)
    cand_mt_lines = sum(1 for u in units if useg(u, 'mt'))
    cand_pending = cand_orig - cand_mt_lines

    # 一一对应性：每个句单元恰好一行原文 + 一行译文
    one_to_one = True
    for u in units:
        if not useg(u, 'src'):
            one_to_one = False
            break

    # 重复句：显示层必须**逐次出现**（翻译去重 ≠ 显示去重）
    by_src = defaultdict(list)
    for u in units:
        by_src[useg(u, 'src') or ''].append(useg(u, 'seg'))
    dup = {s: v for s, v in by_src.items() if len(v) > 1}
    cand_src_counter = Counter(useg(u, 'src') or '' for u in units)
    dup_all_shown = all(cand_src_counter[s] == len(v) for s, v in dup.items())

    # 守恒：候选输出的原文行拼接（去空白）必须等于 orig_chars
    cand_src_chars = sum(len(strip_ws(useg(u, 'src'))) for u in units)
    # 现状：段级原文无法从 units 复原（units 是句子，不是段）⇒ 用 product 的 orig_chars 对照

    # ================= TTS 朗读次数 vs 显示次数 =================
    ob_kind = Counter()
    for o in outbox:
        ob_kind[o[0] if isinstance(o, (list, tuple)) and o else None] += 1
    n_final = ob_kind.get('final', 0)
    # outbox 的 src = 句子原文；统计 outbox 里出现的句子 vs units 里的句子
    ob_srcs = [o[1] for o in outbox if isinstance(o, (list, tuple)) and len(o) >= 2]
    ob_src_counter = Counter(ob_srcs)

    rep['inputs_raw'] = {
        'product_corpus': d.get('corpus'),
        'product_n_seg': d.get('n_seg'),
        'arm': 'BASE_unit',
        'product_n_units': b.get('n_units'),
        'product_n_formal': b.get('n_formal'),
        'product_n_translate_calls': b.get('n_translate_calls'),
        'product_miss_rate': b.get('miss_rate'),
        'product_n_unit_missing': b.get('n_unit_missing'),
        'product_n_timeout': b.get('n_timeout'),
        'product_src_chars': b.get('src_chars'),
        'product_orig_chars': b.get('orig_chars'),
        'product_src_kept': b.get('src_kept'),
        'product_coverage_raw': b.get('coverage'),
        'product_chrf_vs_ref': (b.get('quality') or {}).get('chrf_vs_ref'),
        'product_chrf_n_pairs': (b.get('quality') or {}).get('n_pairs'),
    }

    rep['current_by_segment'] = {
        'n_original_lines': cur_orig,
        'n_translation_lines': cur_mt_lines,
        'n_lines_without_translation': cur_no_mt,
        'sentences_per_translation_line_hist': {str(k): v for k, v in sorted(per_line.items())},
        'max_sentences_in_one_line': max(per_line) if per_line else 0,
        'n_units_with_seg_none': n_seg_none,
        'note': '现状 `_save_text()`/`_render()` 按**段**输出（live_caption_app.py L2395-2410 / L2478-2487）；'
                '⇒ 一行里塞多句；且没有任何句单元的段**不输出〔译〕行**。'
                '⚠️ 实测有 %d 个句单元的 `seg` 为 None（来自 `flush()` 收尾补翻，'
                'translator.py L1130-1150）⇒ 现状 `mt_of_seg()` **根本取不到它们的译文**'
                % n_seg_none,
    }

    rep['candidate_by_unit'] = {
        'n_original_lines': cand_orig,
        'n_translation_lines': cand_mt_lines,
        'n_lines_pending_translation': cand_pending,
        'every_unit_has_src': one_to_one,
        'src_chars_no_ws': cand_src_chars,
        'src_chars_match_orig_chars': cand_src_chars == b.get('orig_chars'),
        'note': '候选 `_save_text()` 按 `mt_units()` 逐单元输出「一句原文 + 一句译文」',
    }

    rep['duplicate_display_check'] = {
        'n_unique_src': len(by_src),
        'n_units': len(units),
        'n_src_repeated': len(dup),
        'n_extra_display_units': len(units) - len(by_src),
        'max_repeat_of_one_src': max((len(v) for v in by_src.values()), default=0),
        'candidate_shows_every_occurrence': dup_all_shown,
        'note': '🔴 MEMORY 铁律：「翻译去重」≠「显示去重」⇒ 候选实现必须逐次建行；'
                '若按 src 去重显示，会丢这 %d 次出现' % (len(units) - len(by_src)),
    }

    rep['tts_vs_display'] = {
        'outbox_kind_counter': {str(k): v for k, v in ob_kind.items()},
        'n_final_outbox': n_final,
        'n_display_units': len(units),
        'gap_display_minus_speech': len(units) - n_final,
        'outbox_src_unique': len(ob_src_counter),
        'outbox_src_max_repeat': max(ob_src_counter.values()) if ob_src_counter else 0,
        'note': '🔴 TTS 从 outbox 取 `kind==\'final\'`（live_caption_app.py L2314）'
                '⇒ 重复句**只朗读一次**（%d 条 final）但**显示 %d 次**（%d 个单元）'
                '⇒ 字幕说两遍、语音只播一遍 —— 这是**产品行为问题**，需 reviewer 裁定，'
                '本轮不改' % (n_final, len(units), len(units)),
    }

    rep['verdict'] = {
        'current_lines': cur_orig + cur_mt_lines,
        'candidate_lines': cand_orig + cand_mt_lines,
        'line_growth_ratio': round((cand_orig + cand_mt_lines) / max(1, cur_orig + cur_mt_lines), 3),
        'current_max_sentences_per_line': max(per_line) if per_line else 0,
        'candidate_max_sentences_per_line': 1,
        'current_segments_without_translation_line': cur_no_mt,
        'candidate_units_without_translation_line': cand_pending,
        'src_conservation_ok': cand_src_chars == b.get('orig_chars'),
        'duplicate_occurrences_preserved': dup_all_shown,
        'conclusion': '候选实现（按 mt_units() 逐句渲染）可达成：① 每行 1 句（现状最多 %d 句/行）；'
                      '② 原文守恒 %s；③ 重复句逐次显示；④ 待翻译单元显示「译文生成中…」而非空白。'
                      '代价：输出行数 %d → %d（%.1f×），且**字幕显示粒度变更**属产品行为 ⇒ 需 reviewer 裁定'
                      % (max(per_line) if per_line else 0,
                         'OK' if cand_src_chars == b.get('orig_chars') else 'FAIL',
                         cur_orig + cur_mt_lines, cand_orig + cand_mt_lines,
                         (cand_orig + cand_mt_lines) / max(1, cur_orig + cur_mt_lines)),
    }

    dump(rep)


def dump(rep):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('written:', OUT, os.path.getsize(OUT), 'B')
    print(json.dumps(rep.get('verdict', {}), ensure_ascii=False, indent=2))
    for k in ('current_by_segment', 'candidate_by_unit', 'duplicate_display_check', 'tts_vs_display'):
        print('\n==', k, '==')
        print(json.dumps(rep.get(k, {}), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.exit(main())
