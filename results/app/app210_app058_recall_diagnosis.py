#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app210 —— APP-058 判据④（换人点召回）的**鉴别力诊断**。

## 为什么需要这个脚本（铁律：判据 FAIL 先怀疑判据/环境）

APP-058 的 8 条判据里 **④ 换人点召回率 FAIL（实测 33.33 %，要求 ≥60 %）**。

第一反应是「旁路漏检」。但先看两个事实：

| 事实 | 值 | 含义 |
|---|---|---|
| 参照段数 | **46** | 来自 ASR 缓存 `segs.json`（离线跑、同一条断句规则） |
| 实测段数 | **48** | 来自 V2.0 包**实时**断句 |

⇒ **两侧分段边界不同**（48 ≠ 46）⇒ **段下标不可直接比**。
   差 2 段 ⇒ 中段起全部错位 1–2 个 ⇒ 逐点命中被系统性压低。

⇒ 本脚本做**鉴别力诊断**（不是重新判一次）：

* **口径 A（原判据）**：段下标直接比 ⇒ 复核应当复现 33.33 %（若不复现 ⇒ 判据本身不稳）
* **口径 B（文本对齐）**：用 **difflib 序列对齐**把实测的 48 行与参照的 46 行
  按**文本内容**对齐 ⇒ 得到「实测行 ↔ 参照段」的映射 ⇒ 在**对齐后的对应关系**上
  重新算换人点召回
  ★ 这是**真正公平**的口径：换人点是**时间/内容上的事件**，不是「第几行」

★ **本脚本不重跑推理**（复用 app208 已落盘的两臂 txt）⇒ 不占机器锁、不碰 GPU。

## 铁律

* **不改判据、不粉饰**：口径 B 若也不达标 ⇒ 照实报 FAIL。
* 每个数字都指到**源文件 + 字段**。
* 三态：True / False / None（无法判定）——「无法判定」≠「判定为不合格」。
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re

HOME = os.path.expanduser('~')
REPO = os.path.join(HOME, 'confucius4-openvino')
APP208 = os.path.join(REPO, 'results', 'app',
                      'app208_app058_spk_retest_evidence.json')
APP193 = os.path.join(REPO, 'results', 'app',
                      'app193_app053_spk_frame_audit.json')
CACHE_SEGS = os.path.join(HOME, 'qwen3asr_06b', 'results', 'pyannote_seg',
                          '_asr050_cache', 'segs.json')
SLICE_START_S = 3291.6
SLICE_END_S = 3591.6
QA_START_S = 2280.0

_RE_TAG = re.compile(r'^\[([^\]]+)\]\s*(.*)$')


def norm_text(s: str) -> str:
    """归一化：去标签、去空白、小写、只留字母数字（ASR 文本有细微差异）。"""
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    return s


def load():
    with open(APP208, encoding='utf-8') as f:
        d208 = json.load(f)
    with open(APP193, encoding='utf-8') as f:
        d193 = json.load(f)
    with open(CACHE_SEGS, encoding='utf-8') as f:
        segs = json.load(f)
    return d208, d193, segs


def cache_slice_texts(segs):
    """参照侧：切片内的段文本（**带参照说话人**）。

    app193 的 `rows` 来自同一个 `segs.json`（全局坐标 = QA 起点 + 局部）。
    ⇒ 这里直接用 app193 的 rows（它已算好 t_start/t_end 与 ref_spk）。
    """
    rows = json.loads(json.dumps(json.load(open(APP193, encoding='utf-8'))['rows']))
    return rows


def align(ref_texts, meas_lines):
    """口径 B：把「实测行」对齐到「参照段」。

    🔴 **为什么不用 SequenceMatcher 的整序列匹配**：两侧**断句边界不同**
       （实测 48 行 / 参照 46 段；实测切得更细 ⇒ 一行参照可能对应 2–3 行实测）
       ⇒ 整序列匹配几乎必然全盘失配（实测相似度 0.0）。
    ⇒ 改用**「内容重叠」贪心对齐**：
       对每个参照段，找与它**内容重叠最大**的实测行（按词级 Jaccard 相似度）
       ⇒ 一对参照段 ↔ 一行实测（取最相似的一行）⇒ 得到映射表。

    Parameters
    ----------
    ref_texts : list[str]
        参照段的文本（**从 ASR 缓存 `segs.json` 取**，app193 的 rows 不带 text）。

    Returns
    -------
    list[(ref_idx, meas_idx)], float
        对齐上的对；相似度均值。
    """
    a = [norm_text(t) for t in ref_texts]
    b = [norm_text(t) for t in meas_lines]
    aw = [set(x.split()) for x in a]
    bw = [set(x.split()) for x in b]

    pairs = []
    sims = []
    used = set()
    for ri in range(len(a)):
        if not aw[ri]:
            continue
        best_m = None
        best_s = 0.0
        for mi in range(len(b)):
            if mi in used or not bw[mi]:
                continue
            inter = len(aw[ri] & bw[mi])
            if inter == 0:
                continue
            s = inter / float(len(aw[ri] | bw[mi]))
            if s > best_s:
                best_s = s
                best_m = mi
        if best_m is not None and best_s >= 0.15:
            pairs.append((ri, best_m))
            used.add(best_m)
            sims.append(best_s)
    avg = (sum(sims) / len(sims)) if sims else 0.0
    return pairs, avg


def switch_points(seq):
    """seq = [(idx, label)] ⇒ 换人点 = label 发生变化的下标（记为前一段的下标）。"""
    out = []
    for k in range(1, len(seq)):
        a, b = seq[k - 1][1], seq[k][1]
        if a is None or b is None:
            continue
        if a != b:
            out.append(seq[k - 1][0])
    return out


def recall_analysis(ref_seq, meas_seq, tol=1):
    """ref_seq / meas_seq = [(idx, label)]（各自的下标空间）。

    换人点召回： meas 的换人点 p 与 ref 的换人点 q 若 |p-q| ≤ tol ⇒ 命中。
    """
    r_sw = switch_points(ref_seq)
    m_sw = switch_points(meas_seq)
    hits, used = [], set()
    for p in m_sw:
        best = None
        for qi, q in enumerate(r_sw):
            if qi in used:
                continue
            d = abs(p - q)
            if d <= tol and (best is None or d < abs(p - r_sw[best])):
                best = qi
        if best is not None:
            used.add(best)
            hits.append((p, r_sw[best]))
    fp = [p for p in m_sw if p not in [h[0] for h in hits]]
    recall = (len(hits) / len(r_sw)) if r_sw else None
    return {
        'n_ref_switches': len(r_sw),
        'ref_switches': r_sw,
        'n_meas_switches': len(m_sw),
        'meas_switches': m_sw,
        'n_hit': len(hits),
        'hits': hits,
        'n_false_positive': len(fp),
        'false_positives': fp,
        'recall': recall,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    d208, d193, segs = load()
    rows = d193['rows']
    ref_spk = d208['ref_spk']
    meas = d208['arms']['on']
    meas_labels = meas['labels']
    cli_file = meas['cli_file']

    # 实测的 48 行文本（带标签前缀）
    meas_lines = []
    with open(cli_file, encoding='utf-8', errors='replace') as f:
        for line in f.read().splitlines():
            if not line.strip():
                continue
            m = _RE_TAG.match(line)
            meas_lines.append(m.group(2) if m else line)

    # 参照的段文本（app193 的 rows 没存 text ⇒ 从 segs.json 按 t_start 对齐取）
    ref_texts = []
    for r in rows:
        t = None
        for s in segs:
            g0 = QA_START_S + s['start_s']
            g1 = QA_START_S + s['end_s']
            if abs(g0 - r['t_start']) < 0.05 and abs(g1 - r['t_end']) < 0.05:
                t = s.get('text') or ''
                break
        ref_texts.append(t)

    n_text = sum(1 for t in ref_texts if t)
    print('参照段 %d（有文本 %d） / 实测行 %d'
          % (len(rows), n_text, len(meas_lines)))

    out = {
        'tool': 'app210',
        'purpose': 'APP-058 判据④ 召回率的鉴别力诊断（口径 A vs 口径 B）',
        'src_app208': APP208,
        'src_app193': APP193,
        'src_segs_json': CACHE_SEGS,
        'cli_file': cli_file,
        'n_ref_segments': len(rows),
        'n_ref_segments_with_text': n_text,
        'n_measured_lines': len(meas_lines),
    }

    # ── 口径 A：段下标直接比（**与 app208 完全同一口径**）────────
    #   ⚠️ 参照换人点用 app208 的 `ref_switches`（**人工标注的 12 个**，
    #      来自 spe_qa_spk.json 的 switch_times_s）⇒ 不是「参照标签自身跳变」。
    seqA_ref = [(i, ref_spk[i]) for i in range(len(ref_spk))]
    seqA_meas = [(i, meas_labels[i]) for i in range(len(meas_labels))]
    det = []
    for i in range(1, len(meas_labels)):
        a_, b_ = meas_labels[i - 1], meas_labels[i]
        if a_ and b_ and a_ != b_:
            det.append(i)
    rs_A = d208['measured']['switch_analysis']['ref_switches']
    hitA = []
    usedA = set()
    for r in rs_A:
        cands = [x for x in det if abs(x - r) <= 1 and x not in usedA]
        if cands:
            usedA.add(cands[0])
            hitA.append((r, cands[0]))
    recallA = (len(hitA) / len(rs_A)) if rs_A else None
    a = {
        'n_detected_switches': len(det),
        'detected_switches': det,
        'n_ref_switches': len(rs_A),
        'ref_switches': rs_A,
        'n_hit': len(hitA),
        'hits': hitA,
        'recall': recallA,
        'n_false_positive': len([x for x in det if x not in usedA]),
        'false_positives': [x for x in det if x not in usedA],
    }
    out['method_A_index'] = a
    print('\n口径 A（段下标直接比，与 app208 同口径）：recall=%s  hit=%d/%d  fp=%d'
          % ('None' if recallA is None else '%.4f' % recallA,
             len(hitA), len(rs_A), a['n_false_positive']))
    print('  复现 app208 的 0.3333 ⇒ %s'
          % (recallA is not None
             and abs(recallA - 0.3333333333333333) < 1e-9))

    # ── 口径 B：文本对齐后比（把实测换人点**映回参照空间**再比）────
    pairs, ratio = align(ref_texts, meas_lines)
    print('\n口径 B（文本重叠对齐）：对齐对 %d / 参照 %d，平均相似度 %.4f'
          % (len(pairs), len(rows), ratio))

    m2r = {mi: ri for ri, mi in pairs}      # 实测行下标 → 参照段下标
    # 实测换人点（在**参照空间**里表述）
    meas_sw_meas = []
    for i in range(1, len(meas_labels)):
        a_, b_ = meas_labels[i - 1], meas_labels[i]
        if a_ and b_ and a_ != b_:
            meas_sw_meas.append(i)
    # 把「实测换人点」映射到参照空间：换人发生在 meas i-1 → i 之间
    # ⇒ 若 i 在参照空间对应 ri，边界落在 ri-1 与 ri 之间 ⇒ 记为 ri-1
    meas_sw_ref = []
    for i in meas_sw_meas:
        if i in m2r:
            ri = m2r[i]
            meas_sw_ref.append(ri - 1 if ri > 0 else ri)
        elif (i - 1) in m2r:
            ri = m2r[i - 1]
            meas_sw_ref.append(ri)
        else:
            continue
    meas_sw_ref = sorted(set(meas_sw_ref))

    rs = d208['measured']['switch_analysis']['ref_switches']
    hit = []
    used = set()
    for r in rs:
        cands = [x for x in meas_sw_ref if abs(x - r) <= 1 and x not in used]
        if cands:
            used.add(cands[0])
            hit.append((r, cands[0]))
    recall_b = (len(hit) / len(rs)) if rs else None
    fp = [x for x in meas_sw_ref if x not in [h[1] for h in hit]]

    b = {
        'n_ref_switches': len(rs),
        'ref_switches': rs,
        'n_meas_switches': len(meas_sw_ref),
        'meas_switches_refspace': meas_sw_ref,
        'meas_switches_meas_space': meas_sw_meas,
        'n_hit': len(hit),
        'hits': hit,
        'recall': recall_b,
        'n_false_positive': len(fp),
        'false_positives': fp,
    }
    out['method_B_text_aligned'] = b
    out['alignment'] = {
        'n_pairs': len(pairs),
        'avg_similarity': round(ratio, 4),
        'n_ref_unmatched': len(rows) - len(pairs),
        'n_meas_unmatched': len(meas_lines) - len(pairs),
        'meas_to_ref_map': {str(k): v for k, v in sorted(m2r.items())},
    }
    print('  recall=%s  hit=%d/%d  fp=%d'
          % ('None' if recall_b is None else '%.4f' % recall_b,
             len(hit), len(rs), len(fp)))
    print('  ref 换人点(参照空间): %s' % rs)
    print('  meas 换人点(映到参照空间): %s' % meas_sw_ref)
    print('  命中: %s' % hit)
    print('  误报: %s' % fp)

    # ── 口径 C：**参照自身**的自洽性（判据可信度的关键）─────────
    #   人工标注的 12 个换人点 vs 参照 46 段标签序列自身的跳变
    #   ⇒ 若二者交集很小 ⇒ **「12 个换人点」与「参照标签跳变」不是同一件事**
    #      （人工标注记的是**物理换人事件**；参照标签是**聚类后的 ID**，
    #        同一物理人被拆成两个簇 ⇒ 标签不跳）
    ref_label_sw = switch_points(seqA_ref)
    inter = sorted(set(ref_label_sw) & set(rs))
    only_manual = sorted(set(rs) - set(ref_label_sw))
    out['reference_self_consistency'] = {
        'n_ref_label_switches': len(ref_label_sw),
        'ref_label_switches': ref_label_sw,
        'n_manual_switches': len(rs),
        'manual_switches': rs,
        'n_intersection': len(inter),
        'intersection': inter,
        'manual_only': only_manual,
        'n_manual_only': len(only_manual),
        'n_ref_label_none': sum(1 for x in ref_spk if x is None),
    }
    print('\n口径 C（参照自洽性）：参照 46 段标签自身跳变 %d 次；'
          '人工标注换人点 %d 个；交集 %d 个；仅人工有 %d 个'
          % (len(ref_label_sw), len(rs), len(inter), len(only_manual)))
    print('  参照标签跳变: %s' % ref_label_sw)
    print('  仅人工标注(参照标签不跳): %s' % only_manual)

    # ── 参照自身的「换人点数」自检（口径是否可信）────────────────
    print('\n参照中 label=None 的段：%d'
          % sum(1 for x in ref_spk if x is None))

    # 口径 B 下「覆盖率」重算（分子分母都在**对齐后**的同一段集合上）
    n_aligned = len(pairs)
    n_aligned_tagged = sum(1 for _ri, mi in pairs
                            if meas_labels[mi] if mi < len(meas_labels))
    out['coverage_aligned'] = {
        'n_aligned_pairs': n_aligned,
        'n_aligned_tagged': n_aligned_tagged,
        'coverage_pct': round(100.0 * n_aligned_tagged / max(1, n_aligned), 2),
    }
    print('\n对齐后覆盖率 = %d/%d = %.2f %%'
          % (n_aligned_tagged, n_aligned,
             out['coverage_aligned']['coverage_pct']))

    out['verdict_note'] = (
        '口径 A 是 app208 的原判据（FAIL）；口径 B 是文本对齐后的口径。'
        '两者都照实报，不粉饰。')

    npass = sum(1 for v in (a, b) if v['recall'] is not None
                and v['recall'] >= 0.60)
    print('\n两种口径达到 ≥60 %% 的个数：%d / 2' % npass)
    print('（口径 A = app208 原判据；口径 B = 文本对齐后把实测换人点'
          '映回参照空间再比）')

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
