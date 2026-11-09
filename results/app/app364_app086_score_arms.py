"""APP-086(2)：给 before / after 两臂**打分**（机器可算的数字）。

🔴 输入（全部来自**落盘产物**，不重新推理）：
  * `truth.json`（reviewer 的真值：`[[t0, t1, "A"], ...]`，源音频时间轴）
  * `spk_seg.jsonl`（App 的 `--spk-seg-jsonl`：`{seg, t0, t1, spk, spk_conf, spk_source}`）
  * `mix.wav.tts.jsonl`（worker 的逐句遥测：`seg` / `voice_spk` / `voice_kind` / `wav_t0`…）
  * `dump/seg_*.wav`（逐句 wav ⇒ 交 reviewer 回转写/抽听）

🔴 指标（APP-086② 验收原文）：
  ① 「用对了说话人音色的句子占比」
     = 用了**克隆音色**且该音色属于**正确说话人**的句子数 ÷ 用了克隆音色的句子数
     （另报：全部句子里「用对音色」的占比、回落预设 A 的占比）
  ② 「换人后切到正确音色的延迟（秒）」
     = 真值里的每次换人 ⇒ 到「第一句用上新说话人音色」之间的**源时间**差
     （报 中位数 / P95 / 最大 / 永远没切过去的次数）

用法：python app364_app086_score_arms.py <truth.json> <runs_root>
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys


def load_truth(p):
    d = json.load(open(p, encoding='utf-8'))
    out = []
    for item in d:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            out.append((float(item[0]), float(item[1]), str(item[2])))
    return sorted(out)


def load_jsonl(p):
    rows = []
    if not os.path.exists(p):
        return rows
    for line in open(p, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def truth_of(truth, t0, t1):
    """按**时间重叠最大**判真值说话人（与 reviewer 的 `tspk` 同口径）。"""
    ov = collections.Counter()
    for a, b, sp in truth:
        o = min(b, t1) - max(a, t0)
        if o > 0:
            ov[sp] += o
    if not ov:
        return None, 0.0
    sp, best = ov.most_common(1)[0]
    return sp, best / max(1e-6, sum(ov.values()))


def pct(vals, q):
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return round(v[int(k)], 3)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 3)


def score_arm(arm_dir, truth):
    seg_rows = load_jsonl(os.path.join(arm_dir, 'spk_seg.jsonl'))
    tts_rows = load_jsonl(os.path.join(arm_dir, 'mix.wav.tts.jsonl'))
    if not tts_rows:
        tts_rows = load_jsonl(os.path.join(arm_dir, 'tts.jsonl'))
    seg_by_id = {}
    for r in seg_rows:
        try:
            seg_by_id[int(r['seg'])] = r
        except Exception:
            pass

    n_total = n_clone = n_clone_ok = n_any_ok = n_preset = n_unlabeled = 0
    per_sent = []
    for r in tts_rows:
        seg = r.get('seg')
        if seg is None:
            continue
        srow = seg_by_id.get(int(seg))
        if not srow:
            continue
        t0, t1 = float(srow.get('t0', 0.0)), float(srow.get('t1', 0.0))
        if t1 <= t0:
            continue
        tsp, pur = truth_of(truth, t0, t1)
        if tsp is None:
            continue
        used = r.get('voice_spk')
        kind = r.get('voice_kind') or 'preset'
        n_total += 1
        if kind == 'clone' and used:
            n_clone += 1
            if str(used) == tsp:
                n_clone_ok += 1
                n_any_ok += 1
        else:
            n_preset += 1
        if not srow.get('spk'):
            n_unlabeled += 1
        per_sent.append({'seg': int(seg), 't0': t0, 't1': t1,
                         'truth': tsp, 'purity': round(pur, 2),
                         'app_spk': srow.get('spk'),
                         'used_spk': used, 'voice_kind': kind,
                         'late': r.get('end_lag_s')})

    # ── 换人延迟：真值里的每次换人 → 第一句用上新说话人音色 ──
    changes = []
    for i in range(1, len(truth)):
        if truth[i][2] != truth[i - 1][2]:
            changes.append((truth[i][0], truth[i][2]))
    delays, never = [], 0
    for ct, new_sp in changes:
        hit = None
        for s in per_sent:
            if s['t0'] >= ct - 0.01 and s['used_spk'] == new_sp \
                    and s['voice_kind'] == 'clone':
                hit = s['t0']
                break
        if hit is None:
            never += 1
        else:
            delays.append(round(hit - ct, 3))

    wavs = []
    dd = os.path.join(arm_dir, 'dump')
    if os.path.isdir(dd):
        wavs = sorted(f for f in os.listdir(dd) if f.endswith('.wav'))

    return {
        'arm_dir': arm_dir,
        'n_tts_rows': len(tts_rows), 'n_seg_rows': len(seg_rows),
        'n_scored': n_total,
        'n_clone': n_clone, 'n_clone_correct': n_clone_ok,
        'n_preset': n_preset, 'n_unlabeled_seg': n_unlabeled,
        'ratio_clone_correct': (round(n_clone_ok / n_clone, 4)
                                if n_clone else None),
        'ratio_any_correct': (round(n_any_ok / n_total, 4)
                               if n_total else None),
        'ratio_preset': (round(n_preset / n_total, 4) if n_total else None),
        'n_speaker_changes': len(changes),
        'n_never_switched': never,
        'switch_delay_s': {'median': pct(delays, 0.5), 'p95': pct(delays, 0.95),
                           'max': max(delays) if delays else None,
                           'n': len(delays)},
        'n_dump_wav': len(wavs),
        'per_sentence': per_sent,
    }


def main() -> int:
    truth_path = sys.argv[1]
    runs_root = sys.argv[2]
    truth = load_truth(truth_path)
    out = {'truth': truth_path, 'n_truth_segments': len(truth), 'arms': {}}
    for arm in ('before', 'after'):
        d = os.path.join(runs_root, arm)
        if os.path.isdir(d):
            out['arms'][arm] = score_arm(d, truth)
    b = out['arms'].get('before') or {}
    a = out['arms'].get('after') or {}
    if b and a:
        out['delta'] = {
            'ratio_clone_correct': (
                None if b.get('ratio_clone_correct') is None
                or a.get('ratio_clone_correct') is None else
                round(a['ratio_clone_correct'] - b['ratio_clone_correct'], 4)),
            'ratio_any_correct': (
                None if b.get('ratio_any_correct') is None
                or a.get('ratio_any_correct') is None else
                round(a['ratio_any_correct'] - b['ratio_any_correct'], 4)),
            'ratio_preset': (
                None if b.get('ratio_preset') is None
                or a.get('ratio_preset') is None else
                round(a['ratio_preset'] - b['ratio_preset'], 4)),
            'switch_delay_median_s': (
                None if (b.get('switch_delay_s') or {}).get('median') is None
                or (a.get('switch_delay_s') or {}).get('median') is None else
                round(a['switch_delay_s']['median'] - b['switch_delay_s']['median'], 3)),
            'n_never_switched': (a.get('n_never_switched', 0)
                                 - b.get('n_never_switched', 0)),
        }
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'app364_app086_score_evidence.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    slim = {k: v for k, v in out.items() if k != 'arms'}
    slim['arms'] = {k: {kk: vv for kk, vv in v.items()
                         if kk != 'per_sentence'}
                    for k, v in out['arms'].items()}
    print(json.dumps(slim, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
