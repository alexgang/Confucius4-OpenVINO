r"""app046_match_rule_probe.py —— 草稿↔正式稿关联规则的**离线规则比对**（v2）。

====================================================================
为什么要做这件事
====================================================================
`live_caption/caption_render.py` 的 `match_draft_to_final()` 用
「rank(equal/prefix/substring) + 草稿更长优先」；
MT 侧有**两套**口径：
  - **旧口径**（`diag_c111_variants2.py` / `_bak_variants2_before_xseg.py`）：
    `dt in ft or ft in dt`（**双向包含**）+ 取**最短**正式句 ⇒ 无方向性、无 min_len；
  - **修正口径**（`c111_metrics_fixed.py::draft_to_final_gap_fixed`）：
    `norm_tight`（只去空白）+ **方向性前缀** + **反向拒绝** + 最短正式稿优先
    + `min_len=10`。

⇒ 两套口径在 MT 产物里给出**不同的配对数**（109 vs 90）⇒ App 侧不能盲从任一套。

====================================================================
本脚本的判定方法（**不依赖任何一套规则的输出**）
====================================================================
🔴 **独立判据 = 段号单调性**：方案 C 的物理语义是
   「草稿是**段 N 的尾半句**，正式稿是**凑齐后（段 N 或更晚）**的整句」
   ⇒ 正确的替换关系**必须**满足 `final.seg >= draft.seg`
   （`seg=None` 的单元 = `flush()` 补翻 ⇒ 不参与该判据）。
   ⇒ 该判据来自**产品语义**，不是来自任何一套匹配规则 ⇒ 可作裁判。

====================================================================
纪律
====================================================================
🔴 **不 import 被测模块**（`live_caption_app.py` 顶部 import numpy/openvino
   ⇒ import 阶段就可能 abort）⇒ 本脚本**不 import 任何模型模块**；
   `caption_render.py` 是**纯 stdlib** ⇒ 可安全 import。
🔴 **不跑推理 / 不测速 / 不占 GPU / 不取机器锁 / 不调 MiniMax**
🔴 本脚本**只读** MT 产物，**不写** MT 目录。
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

import caption_render as CR  # noqa: E402  纯 stdlib

MT_ART = r'C:\Users\Trekker-PTL\hy_bench\runs\c111_half\c111_v5_ts10_nopunct.json'
OUT = os.path.join(HERE, 'app046_match_rule_probe_evidence.json')


def norm_tight(s):
    """MT 口径：只去所有空白（**保留标点与大小写**）。"""
    return re.sub(r'\s+', '', s or '')


# ══════════════════════════════════════════════════════════════════════
# 四套候选规则
# ══════════════════════════════════════════════════════════════════════
def rule_current(drafts, finals):
    """现版 `caption_render.match_draft_to_final`（逐字复刻）。"""
    cands = []
    for di, d in enumerate(drafts):
        dn = CR.norm_src(d.get('src', ''))
        if not dn:
            continue
        for fi, f in enumerate(finals):
            fn = CR.norm_src(f.get('src', ''))
            if not fn:
                continue
            if dn == fn:
                rank = 0
            elif fn.startswith(dn):
                rank = 1
            elif dn in fn:
                rank = 2
            else:
                continue
            cands.append((rank, -len(dn), di, fi))
    cands.sort()
    out, used = {}, set()
    for _r, _n, di, fi in cands:
        if di in out or fi in used:
            continue
        out[di] = fi
        used.add(fi)
    return out


def rule_mt_old(drafts, finals):
    """MT **旧口径**：`dt in ft or ft in dt` + 最短正式句（不强制一对一）。"""
    out = {}
    for di, d in enumerate(drafts):
        dt = norm_tight(d.get('src', ''))
        if not dt:
            continue
        best = None
        for fi, f in enumerate(finals):
            ft = norm_tight(f.get('src', ''))
            if not ft:
                continue
            if dt in ft or ft in dt:
                if best is None or len(ft) < len(best[1]):
                    best = (fi, ft)
        if best is not None:
            out[di] = best[0]
    return out


def rule_mt_fixed(drafts, finals, min_len=10):
    """MT **修正口径**：方向性前缀 + 反向拒绝 + 最短正式稿优先（不强制一对一）。"""
    out = {}
    for di, d in enumerate(drafts):
        dt = norm_tight(d.get('src', ''))
        if len(dt) < min_len:
            continue
        best = None
        for fi, f in enumerate(finals):
            ft = norm_tight(f.get('src', ''))
            if not ft:
                continue
            if ft.startswith(dt) and len(ft) > len(dt):
                cand = len(ft)
            elif dt.startswith(ft) and len(dt) > len(ft):
                continue          # 反向 ⇒ 拒绝
            else:
                continue
            if best is None or cand < best[1]:
                best = (fi, cand)
        if best is not None:
            out[di] = best[0]
    return out


def rule_minimal(drafts, finals):
    """**最小改动版**（拟落地）：在现版规则上，**同一草稿的候选里取最短的正式稿**。

    与现版的唯一差别 = 排序键从 `(rank, -len(dn), di, fi)`
    改成 `(rank, -len(dn), len(fn), di, fi)`
    ⇒ 即在「草稿更长优先」不变的前提下，补上 **「最短剩余正式稿优先」**。
    """
    cands = []
    for di, d in enumerate(drafts):
        dn = CR.norm_src(d.get('src', ''))
        if not dn:
            continue
        for fi, f in enumerate(finals):
            fn = CR.norm_src(f.get('src', ''))
            if not fn:
                continue
            if dn == fn:
                rank = 0
            elif fn.startswith(dn):
                rank = 1
            elif dn in fn:
                rank = 2
            else:
                continue
            cands.append((rank, -len(dn), len(fn), di, fi))
    cands.sort()
    out, used = {}, set()
    for _r, _n, _fl, di, fi in cands:
        if di in out or fi in used:
            continue
        out[di] = fi
        used.add(fi)
    return out


def rule_proposed(drafts, finals, min_len=10):
    """**拟实现的新规则**（App 侧）：

    ① **方向性前缀优先**（rank 0/1）：正式稿归一化后以草稿归一化为前缀且更长
       ⇒ 草稿是整句的前半截（方案 C 主场景）；
    ② **完全相等**（rank 0）：定稿只补了句末标点；
    ③ **子串放宽**（rank 2）：**仅对前缀匹配不上的草稿**兜底
       （草稿嵌在正式稿中间）；
    ④ **反向拒绝**：草稿以正式稿为前缀（正式 ⊂ 草稿）⇒ 那是更早的单元 ⇒ 拒绝；
    ⑤ **最短剩余正式稿优先**（同 rank 内按正式稿长度**升序**）；
    ⑥ **全局一对一**：一个正式稿只被一个草稿占；
    ⑦ **草稿更长优先**（同 rank 同长度时，更具体的草稿先配）。
    """
    # 第一阶段：严格方向性
    strict = {}
    for di, d in enumerate(drafts):
        dn = CR.norm_src(d.get('src', ''))
        if not dn or len(norm_tight(d.get('src', ''))) < min_len:
            continue
        for fi, f in enumerate(finals):
            fn = CR.norm_src(f.get('src', ''))
            if not fn:
                continue
            if dn == fn:
                strict.setdefault(di, []).append((0, len(fn), fi))
            elif fn.startswith(dn) and len(fn) > len(dn):
                strict.setdefault(di, []).append((1, len(fn), fi))
    # 第二阶段：子串兜底（只对第一阶段没配上的草稿）
    loose = {}
    for di, d in enumerate(drafts):
        if di in strict:
            continue
        dn = CR.norm_src(d.get('src', ''))
        if not dn:
            continue
        for fi, f in enumerate(finals):
            fn = CR.norm_src(f.get('src', ''))
            if not fn:
                continue
            if dn.startswith(fn) and len(dn) > len(fn):
                continue          # 反向 ⇒ 拒绝
            if dn in fn:
                loose.setdefault(di, []).append((2, len(fn), fi))

    out, used = {}, set()
    # 严格优先 → 草稿更长优先 → 最短正式稿优先
    for pool in (strict, loose):
        items = []
        for di, lst in pool.items():
            if di in out:
                continue
            for rank, flen, fi in lst:
                items.append((rank, -len(norm_tight(drafts[di].get('src', ''))),
                              flen, di, fi))
        items.sort()
        for _r, _dl, _fl, di, fi in items:
            if di in out or fi in used:
                continue
            out[di] = fi
            used.add(fi)
    return out


# ══════════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    art = json.load(io.open(MT_ART, encoding='utf-8'))
    arm = art['results']['C_draft']
    units = arm['units']

    drafts = [u for u in units if (u.get('kind') or 'final') == 'draft']
    finals = [u for u in units if (u.get('kind') or 'final') != 'draft']

    maps = {
        'current': rule_current(drafts, finals),
        'minimal': rule_minimal(drafts, finals),
        'mt_old': rule_mt_old(drafts, finals),
        'mt_fixed': rule_mt_fixed(drafts, finals),
        'proposed': rule_proposed(drafts, finals),
    }

    def seg_of(u):
        s = u.get('seg')
        return s if isinstance(s, int) else None

    def judge(name, m):
        """用**独立判据**（段号单调性）评判一套规则。"""
        n_paired = len(m)
        n_violate = 0        # final.seg < draft.seg ⇒ 时间倒流 ⇒ 必错
        n_final_seg_none = 0
        n_unpaired = len(drafts) - n_paired
        viol = []
        used = {}
        for di, fi in m.items():
            ds, fs = seg_of(drafts[di]), seg_of(finals[fi])
            if fs is None:
                n_final_seg_none += 1
                continue
            if ds is None:
                continue
            if fs < ds:
                n_violate += 1
                viol.append({'draft_key': drafts[di].get('key'),
                             'draft_seg': ds, 'final_seg': fs,
                             'draft_src': (drafts[di].get('src') or '')[:90],
                             'final_src': (finals[fi].get('src') or '')[:90]})
            used.setdefault(fi, []).append(di)
        n_dup_final = sum(1 for fi, ds in used.items() if len(ds) > 1)
        return {
            'n_paired': n_paired,
            'n_unpaired_draft': n_unpaired,
            'coverage_rate': round(n_paired / float(len(drafts)), 4),
            'n_seg_violation': n_violate,       # 🔴 段号倒流条数（越少越好）
            'n_final_seg_none': n_final_seg_none,
            'n_final_used_by_multi_draft': n_dup_final,
            'violations_sample': viol[:15],
        }

    judged = {k: judge(k, v) for k, v in maps.items()}

    # 规则两两一致度（以 key 对为单位）
    def keyset(m):
        return {(drafts[di].get('key'), finals[fi].get('key'))
                for di, fi in m.items()}

    ks = {k: keyset(v) for k, v in maps.items()}
    agree = {}
    names = list(ks)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            agree[f'{a}|{b}'] = {
                'common': len(ks[a] & ks[b]),
                'only_a': len(ks[a] - ks[b]),
                'only_b': len(ks[b] - ks[a]),
            }

    # MT 产物自报的配对数（旧口径）
    mt_gap = arm.get('draft_gap') or {}

    payload = {
        'task': '草稿↔正式稿关联规则的离线规则比对（v2：四套规则 × 独立判据）',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'discipline': {
            'no_model_import': True, 'no_inference': True, 'no_benchmark': True,
            'no_gpu': True, 'no_machine_lock': True, 'no_minimax': True,
            'mt_artifact_readonly': True,
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
                                      ('n_pairs', 'n_with_gap')},
        },
        'independent_criterion': {
            'name': '段号单调性（final.seg >= draft.seg）',
            'rationale': '方案 C 的物理语义：草稿=段 N 的尾半句，正式稿=凑齐后（段 N 或更晚）的整句'
                         '⇒ 时间倒流的配对必错。该判据来自产品语义，不依赖任何一套匹配规则。',
        },
        'judged': judged,
        'pairwise_agreement': agree,
        'elapsed_s': None,
    }
    payload['elapsed_s'] = round(time.time() - t0, 3)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"语料：n_draft={len(drafts)} n_final={len(finals)} "
          f"| MT 产物自报 draft_gap.n_pairs={mt_gap.get('n_pairs')}（旧口径）\n")
    hdr = ('规则', '配对数', '覆盖率', '段号倒流', 'final被多草稿共用', '未配对草稿')
    print('%-12s %8s %8s %10s %18s %12s' % hdr)
    for k in ('current', 'minimal', 'mt_old', 'mt_fixed', 'proposed'):
        j = judged[k]
        print('%-12s %8d %8.3f %10d %18d %12d'
              % (k, j['n_paired'], j['coverage_rate'], j['n_seg_violation'],
                 j['n_final_used_by_multi_draft'], j['n_unpaired_draft']))
    print('\n=== 两两一致度 ===')
    for k, v in agree.items():
        print(f'  {k:24s} common={v["common"]:4d} only_first={v["only_a"]:4d} '
              f'only_second={v["only_b"]:4d}')
    print('\n=== proposed 的段号倒流样例（前 10）===')
    for x in judged['proposed']['violations_sample'][:10]:
        print('  ', x)
    print('\n=== current 的段号倒流样例（前 10）===')
    for x in judged['current']['violations_sample'][:10]:
        print('  ', x)
    print(f'\nevidence -> {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
