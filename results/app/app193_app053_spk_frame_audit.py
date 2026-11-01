# -*- coding: utf-8 -*-
r"""app193_app053_spk_frame_audit.py — APP-053 ①(c) 的**离线**证据闸门。

## 它回答什么

APP-053 ①(c)：「pyannote 自己的覆盖：同一 5 分钟/Q&A 切片上，pyannote 离线给出
标签的句子占比（以 ASR-029 的接口输出或同切片离线跑 spk 得出）；与 App 实际打标
比例对比，差距即为 App 侧丢失量。」

⇒ 本脚本用 **ASR 侧已经跑完并落盘的缓存**（`results/pyannote_seg/_asr050_cache/`：
`frames.npz` = 离线整段跑的帧级 `p_speech`/`p_dom`；`segs.json` = 同一条 App 断句
路径产出的 207 个定稿段）**离线复算**：

* ① 参考段在**切片内**的分布、换人点；
* ② 每个参考段按 **App 现在的取值规则**（`span_for_final` = 段尾往前借 2.5 s）
    与按**参考口径**（段自身 [t_start, t_end]）分别算
    `clean_ratio` / `overlap_ratio`，再套 ASR-029 的两道门槛
    （`min_clean_ratio=0.8`、`overlap_ratio_max=0.02`）
    ⇒ 得到「pyannote 有标签的句子比例」（= App 侧的理论上限）；
* ③ 与 App 实测打标比例（`app175_app043_clone_acceptance_evidence.json`
    的 `spk_label_coverage_pct`）对比 ⇒ **App 侧丢失量**。

## 🔴 口径纪律

* **纯离线**：只读 numpy `.npz` + json，**不加载任何模型、不跑推理、不计时**
  ⇒ 不占 GPU、不占 CPU 算力 ⇒ **不需要持机器锁**。
* 时间轴：缓存的 `frames.npz` / `segs.json` 都是 **QA 段局部坐标**（QA 起点 2280 s）
  ⇒ 本脚本统一换算到**全局坐标**再与参考标注 `shared/spe_qa_spk.json` 对齐。
* 门槛常量**从 ASR 侧源码现读**（`asr052_speaker_tracker_api.py` 的构造默认值）
  ⇒ 不手抄、不推算。

## 产物

`results/app/app193_app053_spk_frame_audit.json`
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

import numpy as np

HOME = os.path.expanduser('~')
REPO = os.path.join(HOME, 'confucius4-openvino')
ASR_WORK = os.path.join(HOME, 'qwen3asr_06b')
CACHE = os.path.join(ASR_WORK, 'results', 'pyannote_seg', '_asr050_cache')
SHARED = os.path.join(HOME, 'shared')
OUT = os.path.join(REPO, 'results', 'app',
                   'app193_app053_spk_frame_audit.json')

QA_START_S = 2280.0            # ASR-028：Q&A 起点（全局秒）
SLICE_START_S = 3291.6        # densest_5min
SLICE_END_S = 3591.6
FPS = 58.9                     # asr052_spk_runtime.FPS（10 s 窗 589 帧）


def read_asr_gates():
    """从 ASR 侧源码现读门槛默认值（不手抄）。"""
    p = os.path.join(ASR_WORK, 'scripts', 'asr052_speaker_tracker_api.py')
    src = open(p, encoding='utf-8').read()
    out = {}
    for key in ('min_clean_ratio', 'overlap_ratio_max', 'min_dur_s',
                'stride_ms'):
        # 🔴 形如 `min_clean_ratio: float = 0.8,` ⇒ 允许中间有类型标注
        m = re.search(r'%s\s*(?::\s*[A-Za-z_][\w\[\], ]*)?=\s*([0-9.]+)'
                      % key, src)
        out[key] = float(m.group(1)) if m else None
    return out, p


def frame_index(t_s, n_frames):
    """全局秒 → 帧下标（与 ASR `_seg_slice` 同口径：i1 = min(len, round(t*FPS))）。"""
    i0 = max(0, int(round(t_s * FPS)))
    i1 = min(n_frames, int(round(t_s * FPS)))
    return i0, i1


def slice_stats(p_speech, p_dom, t0, t1):
    """段区间的 clean_ratio / overlap_ratio（与 ASR-029 `on_final` 同口径）。"""
    n = len(p_speech)
    i0 = max(0, int(round(t0 * FPS)))
    i1 = min(n, int(round(t1 * FPS)))
    if i1 <= i0:
        return None
    ps = p_speech[i0:i1]
    pd = p_dom[i0:i1]
    clean_f = (ps >= 0.5)
    clean_ratio = float(clean_f.mean())
    if getattr(pd, 'ndim', 1) >= 2 and pd.shape[1] > 1:
        overlap_ratio = float((pd[:, 1:].sum(axis=1) > 1.05).mean())
    else:
        overlap_ratio = 0.0
    return dict(n_frames=int(i1 - i0), clean_ratio=round(clean_ratio, 4),
                overlap_ratio=round(overlap_ratio, 4))


def main():
    gates, gate_src = read_asr_gates()
    p_speech = np.load(os.path.join(CACHE, 'frames.npz'))['p_speech']
    p_dom = np.load(os.path.join(CACHE, 'frames.npz'))['p_dom']
    segs = json.load(open(os.path.join(CACHE, 'segs.json'), encoding='utf-8'))
    ref = json.load(open(os.path.join(SHARED, 'spe_qa_spk.json'), encoding='utf-8'))

    n_frames = len(p_speech)
    # 缓存覆盖的音频时长（帧级）
    cached_audio_s = n_frames / FPS

    # 切片在 QA 局部坐标里的范围
    q0 = SLICE_START_S - QA_START_S
    q1 = SLICE_END_S - QA_START_S

    # ① 参考标注（全局坐标）里落在切片内的段
    ref_segs = [s for s in ref['segments']
                if s['t_end'] > SLICE_START_S and s['t_start'] < SLICE_END_S]
    ref_labeled = [s for s in ref_segs if s.get('spk')]

    # ② 缓存段（ASR 侧用同一条断句路径产出）落在切片内的段
    cache_segs = []
    for s in segs:
        g0 = s['start_s'] + QA_START_S
        g1 = s['end_s'] + QA_START_S
        if g1 > SLICE_START_S and g0 < SLICE_END_S:
            cache_segs.append(dict(id=len(cache_segs), t_start=g0, t_end=g1,
                                   dur_s=round(g1 - g0, 3),
                                   text=(s.get('text') or '')[:40]))
    cache_segs.sort(key=lambda x: x['t_start'])

    # 参考标注里、同一时间窗的段（用于与缓存段一一对照）
    rows = []
    for s in cache_segs:
        g0, g1 = s['t_start'], s['t_end']
        # App 现在的取值规则：段尾往前借 2.5 s（span_for_final）
        app_t0, app_t1 = max(0.0, g1 - 2.5), g1
        st_app = slice_stats(p_speech, p_dom, app_t0 - QA_START_S, app_t1 - QA_START_S)
        st_ref = slice_stats(p_speech, p_dom, g0 - QA_START_S, g1 - QA_START_S)
        # 参考标注给出的 spk（伪真值）
        rs = None
        for r in ref_segs:
            if abs(r['t_start'] - g0) < 0.35 and abs(r['t_end'] - g1) < 0.35:
                rs = r
                break
        row = dict(
            seg_id=s['id'], t_start=round(g0, 3), t_end=round(g1, 3),
            dur_s=s['dur_s'],
            ref_spk=(rs or {}).get('spk'),
            ref_skip=(rs or {}).get('skip'),
            app_span=[round(app_t0, 3), round(app_t1, 3)],
            app_span_stats=st_app,
            ref_span_stats=st_ref,
        )
        rows.append(row)

    def passes(st, dur):
        if st is None or st['n_frames'] == 0:
            return False
        if dur < gates['min_dur_s']:
            return False
        if st['clean_ratio'] < gates['min_clean_ratio']:
            return False
        if st['overlap_ratio'] > gates['overlap_ratio_max']:
            return False
        return True

    n = len(rows)
    app_pass = sum(1 for r in rows
                   if passes(r['app_span_stats'], r['app_span_stats'] and
                             (r['app_span_stats']['n_frames'] / FPS) or 0))
    ref_pass = sum(1 for r in rows
                   if passes(r['ref_span_stats'], r['dur_s']))
    app_pass_any = sum(1 for r in rows
                       if r['app_span_stats'] and
                       r['app_span_stats']['clean_ratio'] >=
                       gates['min_clean_ratio'] and
                       r['app_span_stats']['overlap_ratio'] <=
                       gates['overlap_ratio_max'])
    # 原因分布
    def reason(st, dur):
        if st is None or st['n_frames'] == 0:
            return 'no_frames'
        if dur < gates['min_dur_s']:
            return 'too_short'
        if st['clean_ratio'] < gates['min_clean_ratio']:
            return 'not_clean_speech'
        if st['overlap_ratio'] > gates['overlap_ratio_max']:
            return 'overlap'
        return 'ok'

    app_reason = Counter(reason(r['app_span_stats'],
                                (r['app_span_stats']['n_frames'] / FPS)
                                if r['app_span_stats'] else 0) for r in rows)
    ref_reason = Counter(reason(r['ref_span_stats'], r['dur_s']) for r in rows)

    # ③ App 实测打标比例
    ev_path = os.path.join(REPO, 'results', 'app',
                           'app175_app043_clone_acceptance_evidence.json')
    ev = json.load(open(ev_path, encoding='utf-8'))
    app_measured_pct = ev.get('spk_label_coverage_pct')
    app_measured_tagged = ev.get('n_spk_tagged_lines')

    out = dict(
        script='app193_app053_spk_frame_audit.py',
        purpose='APP-053 ①(c)：pyannote 离线覆盖率 vs App 实测打标率（离线复算）',
        offline_only=True,
        ran_model=False,
        used_cache=dict(
            frames_npz=os.path.join(CACHE, 'frames.npz'),
            segs_json=os.path.join(CACHE, 'segs.json'),
            ref_json=os.path.join(SHARED, 'spe_qa_spk.json'),
            n_frames=int(n_frames),
            cached_audio_s=round(cached_audio_s, 3),
            fps=FPS,
            qa_start_s=QA_START_S,
        ),
        gates_from_asr_source=dict(path=gate_src, **gates),
        slice=dict(start_s=SLICE_START_S, end_s=SLICE_END_S,
                   dur_s=round(SLICE_END_S - SLICE_START_S, 3)),
        ref_annotation=dict(
            n_segments_in_slice=len(ref_segs),
            n_labeled=len(ref_labeled),
            labeled_pct=round(100.0 * len(ref_labeled) / max(1, len(ref_segs)), 2),
            spk_hist=dict(Counter(s.get('spk') for s in ref_segs)),
            skip_hist=dict(Counter(s.get('skip') for s in ref_segs)),
            n_switch_ref=len(ref['densest_5min']['switch_times_s']),
        ),
        cache_segs_in_slice=len(cache_segs),
        pyannote_offline=dict(
            app_span_rule_pass=app_pass,
            app_span_rule_pass_pct=round(100.0 * app_pass / max(1, n), 2),
            app_span_rule_pass_ignoring_dur=app_pass_any,
            app_span_rule_reason=dict(app_reason),
            ref_span_rule_pass=ref_pass,
            ref_span_rule_pass_pct=round(100.0 * ref_pass / max(1, n), 2),
            ref_span_rule_reason=dict(ref_reason),
            note=('app_span_rule = App 现在的 span_for_final（段尾往前借 2.5 s）；'
                  'ref_span_rule = 参考口径（段自身 [t_start,t_end]）'),
        ),
        app_measured=dict(
            evidence=ev_path,
            spk_label_coverage_pct=app_measured_pct,
            n_spk_tagged_lines=app_measured_tagged,
            n_spk_reference=ev.get('n_spk_reference'),
            n_switch_points=ev.get('n_switch_points'),
            n_embed_updates=ev.get('n_embed_updates'),
        ),
        rows=rows,
    )
    loss = None
    if app_measured_pct is not None:
        loss = round(out['pyannote_offline']['app_span_rule_pass_pct']
                     - app_measured_pct, 2)
        out['app_side_loss_pp'] = loss
        out['loss_note'] = (
            'pyannote 离线在同一切片、同一断句下本应给标签的比例 − App 实测打标比例'
            '（单位：百分点）')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('=== APP-053 ①(c) 离线复算 ===')
    print('切片 %.1f ~ %.1f s（%.1f s）' % (SLICE_START_S, SLICE_END_S,
                                            SLICE_END_S - SLICE_START_S))
    print('ASR 门槛（源码现读）: %s' % gates)
    print('缓存帧 %d（覆盖 %.1f s），切片内断句段 %d 个'
          % (n_frames, cached_audio_s, n))
    print('参考标注：切片内 %d 段，%d 段有标签（%.2f%%），换人点 %d 个'
          % (len(ref_segs), len(ref_labeled),
             100.0 * len(ref_labeled) / max(1, len(ref_segs)),
             len(ref['densest_5min']['switch_times_s'])))
    print('pyannote 离线（App 取值规则 2.5 s 借用）可打标 %d/%d = %.2f%%  原因=%s'
          % (app_pass, n, 100.0 * app_pass / max(1, n), dict(app_reason)))
    print('pyannote 离线（参考口径 段自身区间）  可打标 %d/%d = %.2f%%  原因=%s'
          % (ref_pass, n, 100.0 * ref_pass / max(1, n), dict(ref_reason)))
    print('App 实测打标 = %s%%（%s 行）'
          % (app_measured_pct, app_measured_tagged))
    if loss is not None:
        print('⇒ App 侧丢失 = %.2f 个百分点' % loss)
    print('产物 = %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
