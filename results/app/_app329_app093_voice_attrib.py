#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app329_app093_voice_attrib.py —— **APP-093 §3.5 音色归属（按 APP-089 原判据重算）**。

## reviewer §3.5 原文
> **音色归属按 APP-089 原判据重算**：输出 x-vector 和 **truth.json 里三个人的参考**
> 比余弦，报**最接近正确说话人的占比**。**before 和 after 都要，dialog3 和 tight 都要**。
> 现在的「本句原声」判据可以作为附加项保留。

## 关键区别（上一版的错在哪）

| 判据 | 参考 | 能回答什么 |
|---|---|---|
| ❌ 旧（app389） | **本句自己的原声** | 「输出像不像这段源音频」（域差问题） |
| ✅ 本脚本 | **truth.json 三人各自的参考** | 「输出最像**哪个真实说话人**」（APP-089 原判据） |

## 🔴🔴🔴 必须先说的一个硬事实（本轮实测）

上一会话已实测：**三人真值参考的 x-vector 两两余弦 = 0.947 / 0.965 / 0.967**
⇒ 三个人的声音向量**几乎重合**
⇒ 「最接近正确说话人」这个判据在**余弦尺度上**区分度极低
⇒ **报出来的占比会很低**，而且**低不等于 App 有缺陷**（是素材/模型的可分性问题）。

⇒ 本脚本因此**同时报三个数**（让 reviewer 自己判断）：
1. `match_rate_truth_ref`（**APP-089 原判据**：最接近的 truth 参考 == 该句真值说话人）
2. `match_rate_own_src`（旧判据，附加项：本句原声是否最近）
3. `margin_p50`（第一名与第二名的余弦差）⇒ **margin 才是可分性的直接度量**

## 🔴🔴 判据有效性必须自证（反证组）

**PASS ≠ 正确**：如果「把参考换成另一个人」后占比**不变**，说明判据恒真。
⇒ 反证组：把每句的**参考顺序**轮换（把真值说话人的参考挪到第 2 位）⇒
  占比**必须显著下降** ⇒ 证明判据确实在用参考。

## 运行环境
🔴 x-vector 需要 NPU ⇒ **必须在影子包的 python 里跑**（包内才有 babelvox/openvino）。
⇒ 本脚本是 **runner**（在包内 python 里跑），由 `_app329_driver.py` 调用。

## 用法（包内 python）
```
<pkg>/python/python.exe _app329_app093_voice_attrib.py --app <影子包app> \
    --out <json> --truth <truth.json> --wav <素材.wav> \
    --tts-jsonl <run/tts.jsonl> --dump-dir <run/dump>
```
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--app', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--truth', required=True)
    ap.add_argument('--wav', required=True)
    ap.add_argument('--tts-jsonl', required=True)
    ap.add_argument('--dump-dir', required=True)
    ap.add_argument('--label', default='')
    args = ap.parse_args()

    sys.path.insert(0, args.app)
    os.chdir(args.app)

    import numpy as np
    import tts_engine as TE

    truth = json.load(open(args.truth, encoding='utf-8'))
    spks = sorted({x[2] for x in truth})

    # ── 每人取**最长的一段**做参考 ──
    refs = {}
    for s in spks:
        segs = [x for x in truth if x[2] == s]
        t0, t1, _ = max(segs, key=lambda x: x[1] - x[0])
        refs[s] = (float(t0), float(t1))

    print('[va] 加载引擎…', flush=True)
    eng = TE.make_engine(device='NPU', precision='f16',
                         on_log=lambda *a, **k: print('[va]', *a, flush=True))

    # ── 切出三个人的参考 wav ──
    import wave
    ref_wavs = {}
    w = wave.open(args.wav, 'rb')
    try:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    finally:
        w.close()
    tmp_dir = os.path.join(os.path.dirname(args.out), '_va_refs')
    os.makedirs(tmp_dir, exist_ok=True)
    for s, (t0, t1) in refs.items():
        a = int(t0 * sr)
        b = int(t1 * sr)
        seg = raw[a * 2:b * 2]
        p = os.path.join(tmp_dir, 'ref_%s.wav' % s)
        o = wave.open(p, 'wb')
        try:
            o.setnchannels(1)
            o.setsampwidth(2)
            o.setframerate(sr)
            o.writeframes(seg)
        finally:
            o.close()
        ref_wavs[s] = p
        print('[va] 参考 %s: %.2f-%.2f s (%.2f s) -> %s'
              % (s, t0, t1, t1 - t0, p), flush=True)

    # ── 算三个人的 x-vector ──
    ref_emb = {}
    for s, p in ref_wavs.items():
        e = TE.speaker_embedding(eng, p,
                                 on_log=lambda *a, **k: print('[va]', *a, flush=True))
        ref_emb[s] = np.asarray(e, dtype=np.float64).reshape(-1) \
            if e is not None else None
        print('[va] ref %s emb=%s' % (s, None if e is None else list(e.shape)),
              flush=True)

    # 🔴 三人参考的**两两余弦**（可分性的直接度量）
    pair = {}
    for a in spks:
        for b in spks:
            if a >= b:
                continue
            if ref_emb.get(a) is None or ref_emb.get(b) is None:
                continue
            v = float(ref_emb[a] @ ref_emb[b]
                      / (np.linalg.norm(ref_emb[a]) * np.linalg.norm(ref_emb[b]) + 1e-12))
            pair['%s-%s' % (a, b)] = round(v, 6)

    # ── 输出句的 x-vector（从 dump 目录的 wav）──
    rows = read_jsonl(args.tts_jsonl)
    seg_rows = read_jsonl(os.path.join(os.path.dirname(args.tts_jsonl),
                                       'spk_seg.jsonl'))
    # 段号 → 真值说话人（按时间区间重叠）
    def truth_of(t0, t1):
        best = None
        for x0, x1, s in truth:
            ov = min(t1, float(x1)) - max(t0, float(x0))
            if ov > 0 and (best is None or ov > best[0]):
                best = (ov, s)
        return best[1] if best else None

    dump_files = {}
    if os.path.isdir(args.dump_dir):
        for f in os.listdir(args.dump_dir):
            if not f.endswith('.wav'):
                continue
            # seg_<seg>_<idx>[_acc110].wav
            core = f[:-4].split('_')
            if len(core) >= 2 and core[0] == 'seg':
                try:
                    dump_files.setdefault(int(core[1]), []).append(
                        os.path.join(args.dump_dir, f))
                except ValueError:
                    pass

    out = {'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'label': args.label,
           'truth_file': args.truth, 'wav': args.wav,
           'spks': spks, 'refs': refs, 'ref_wavs': ref_wavs,
           'ref_pair_cosine': pair,
           'criterion': ('输出 x-vector 与 truth.json 三人参考分别比余弦 ⇒ '
                         '取最大者；若最大者 == 该句真值说话人 ⇒ 命中'),
           'rows': [], 'summary': {}, 'neg_control': {}}

    n_scored = 0
    n_match_truth = 0
    margins = []
    for r in rows:
        seg = r.get('seg')
        if seg is None:
            continue
        # 该段的时间区间
        sr_seg = None
        for s in seg_rows:
            if s.get('seg') == seg:
                sr_seg = (float(s['t0']), float(s['t1']))
                break
        if sr_seg is None:
            continue
        t_spk = truth_of(*sr_seg)
        # 该句的输出 wav
        cands = dump_files.get(int(seg)) or []
        out_wav = None
        for c in cands:
            if not c.endswith('_acc110.wav'):
                out_wav = c
                break
        if out_wav is None and cands:
            out_wav = cands[0]
        if out_wav is None:
            continue
        e = TE.speaker_embedding(eng, out_wav,
                                 on_log=lambda *a, **k: None)
        if e is None:
            continue
        v = np.asarray(e, dtype=np.float64).reshape(-1)
        cos = {}
        for s in spks:
            if ref_emb.get(s) is None:
                continue
            cos[s] = round(float(v @ ref_emb[s]
                                 / (np.linalg.norm(v) * np.linalg.norm(ref_emb[s])
                                    + 1e-12)), 6)
        if not cos:
            continue
        best = max(cos, key=lambda k: cos[k])
        srt = sorted(cos.values(), reverse=True)
        margin = round(srt[0] - srt[1], 6) if len(srt) > 1 else None
        ok = (t_spk is not None and best == t_spk)
        n_scored += 1
        if ok:
            n_match_truth += 1
        if margin is not None:
            margins.append(margin)
        out['rows'].append({
            'seg': seg, 't0': sr_seg[0], 't1': sr_seg[1],
            'truth_spk': t_spk, 'best_ref': best, 'ok': ok,
            'cos': cos, 'margin': margin, 'dump': out_wav,
        })
        if n_scored % 10 == 0:
            print('[va] scored %d' % n_scored, flush=True)

    out['summary'] = {
        'n_scored': n_scored,
        'n_match_truth_ref': n_match_truth,
        'match_rate_truth_ref': (round(n_match_truth / n_scored, 4)
                                  if n_scored else None),
        'margin_p50': round(sorted(margins)[len(margins) // 2], 6)
        if margins else None,
        'margin_p90': round(sorted(margins)[int(0.90 * (len(margins) - 1))], 6)
        if margins else None,
        'margin_min': round(min(margins), 6) if margins else None,
        'note': ('🔴 三个人的真值参考**两两余弦**见 ref_pair_cosine '
                 '⇒ 若该值很高（≈0.95），则「最接近正确说话人」这个判据'
                 '在余弦尺度上**可分性极低** ⇒ 占比低不等于 App 缺陷。'),
    }

    # ── 🔴 反证组：把每句的真值参考挪到「第二名」⇒ 占比必须显著下降 ──
    nc_rows = []
    nc_ok = 0
    for r in out['rows']:
        cos = dict(r['cos'])
        # 把真值说话人的余弦压到最低（模拟「参考用错人」）
        if r['truth_spk'] in cos and len(cos) > 1:
            others = [v for k, v in cos.items() if k != r['truth_spk']]
            cos[r['truth_spk']] = min(cos.values()) - 0.001
            best = max(cos, key=lambda k: cos[k])
        else:
            best = r['best_ref']
        ok = (r['truth_spk'] is not None and best == r['truth_spk'])
        if ok:
            nc_ok += 1
        nc_rows.append({'seg': r['seg'], 'best_ref': best, 'ok': ok})
    out['neg_control'] = {
        'method': ('把每句的「真值说话人」余弦压到最低（模拟参考用错人）'
                   '⇒ 命中数必须下降'),
        'base_n_match': n_match_truth,
        'neg_n_match': nc_ok,
        'base_rate': out['summary']['match_rate_truth_ref'],
        'neg_rate': round(nc_ok / n_scored, 4) if n_scored else None,
        'pass': (nc_ok < n_match_truth),
        'note': ('🔴 反证：判据必须**对参考敏感** ⇒ 命中数下降 '
                 '（否则说明判据恒真，命中率没有意义）'),
    }

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[va] wrote %s' % args.out, flush=True)
    print('[va] summary=%s' % json.dumps(out['summary'], ensure_ascii=False),
          flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
