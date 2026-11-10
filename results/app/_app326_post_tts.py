#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app326_post_tts.py —— **APP-097 §2-3 的「撞帧上限」口径复核 + 端到端汇总**。

## 为什么需要这个后处理（重要）

**`end_reason` 的真实来源**（读码定案）：

* `tts_worker._synth_babelvox()` 在合成完一句后做：
  `_er = getattr(self.engine, '_last_end_reason', None)` ⇒ `self._last_end_reason = _er`
* 引擎是 **babelvox 的 `Pipeline` 对象** ⇒ **它没有 `_last_end_reason` 属性**
  ⇒ `_er` 恒为 `None` ⇒ worker 恒为 `None`
* worker 落盘时做归一化：`tel['end_reason'] = self._last_end_reason or 'eos'`
  ⇒ **App 的 jsonl 里恒是 `'eos'`**
* `'cap'` **只可能**由 **CUDA 边车**回报（该引擎对象有 `_last_end_reason`）
  ⇒ **当前交付配置（全 NPU / babelvox）下 `end_reason='cap'` 恒不可达**

⇒ 所以「撞帧上限次数」不能只看 `end_reason`（那是**结构性恒 eos**，不是测量值）
⇒ 必须**独立**用「实际产出帧数 vs 本句传给引擎的帧数上限」判定：
  `frames_out >= max_new_tokens` ⇒ 本句被帧数上限截断。

🔴 **两个口径都写进 json**，并**说明各自的来源**：
  1. `end_reason_dist`（App jsonl 的原文字段）⇒ 结构性恒 `eos`
  2. `n_hit_frame_cap_frames`（本脚本算）⇒ 字段来源 `tts.jsonl.frames_out` vs
     `tts.jsonl.max_new_tokens`

🔴🔴 **反证组（必做）**：把某几行的 `frames_out` 改成 `>= max_new_tokens`
⇒ 计数**必须**增加 ⇒ 证明这个判据**不是恒 0**（否则「撞上限=0」没有说服力）。
"""
from __future__ import annotations

import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'app326_app097_lang_out')
TTS_JSONL = os.path.join(OUT, 'tts.jsonl')
TTS_JSON = os.path.join(OUT, 'tts.json')
MT_JSON = os.path.join(OUT, 'mt.json')
REPORT = os.path.join(HERE, 'app326_tts_post.json')


def load_jsonl(path):
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


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    i = int(q * (len(s) - 1))
    return round(s[i], 4)


def main():
    rows = load_jsonl(TTS_JSONL)
    tts = json.load(open(TTS_JSON, encoding='utf-8')) if os.path.exists(TTS_JSON) else {}
    mt = json.load(open(MT_JSON, encoding='utf-8')) if os.path.exists(MT_JSON) else {}

    ev = {
        'n_rows': len(rows),
        'end_reason_field': 'tts.jsonl.end_reason（App worker 归一化：None⇒eos）',
        'cap_criterion': 'frames_out >= max_new_tokens（tts.jsonl 两个字段）',
        'end_reason_dist': {},
        'n_hit_frame_cap_end_reason': 0,
        'n_hit_frame_cap_frames': 0,
        'per_lang': {},
        'neg_control': {},
        'notes': [],
    }

    if not rows:
        ev['verdict'] = 'NO_ROWS'
        _dump(ev)
        print('!! 没有 TTS 行')
        return 3

    # ── end_reason 分布（App 原文字段）──
    for r in rows:
        k = str(r.get('end_reason'))
        ev['end_reason_dist'][k] = ev['end_reason_dist'].get(k, 0) + 1
    ev['n_hit_frame_cap_end_reason'] = ev['end_reason_dist'].get('cap', 0)

    # ── 独立判定：frames_out vs max_new_tokens ──
    hit = 0
    margins = []
    for r in rows:
        fo = r.get('frames_out')
        mnt = r.get('max_new_tokens')
        if isinstance(fo, (int, float)) and isinstance(mnt, (int, float)) and mnt > 0:
            marg = mnt - fo
            margins.append(marg)
            if fo >= mnt:
                hit += 1
    ev['n_hit_frame_cap_frames'] = hit
    ev['frame_cap_margin_p50'] = pct(margins, 0.50)
    ev['frame_cap_margin_min'] = round(min(margins), 3) if margins else None
    ev['n_rows_with_frames_and_cap'] = len(margins)

    # ── 逐语种 × 音色 ──
    for lang in sorted({r.get('lang') for r in rows if r.get('lang')}):
        per = {}
        for voice in ('preset', 'clone'):
            sub = [r for r in rows
                   if r.get('lang') == lang and r.get('voice') == voice]
            if not sub:
                continue
            durs = [r.get('out_dur_s') for r in sub
                    if isinstance(r.get('out_dur_s'), (int, float))]
            rtfs = [r.get('synth_rtf') for r in sub
                    if isinstance(r.get('synth_rtf'), (int, float))]
            spc = [r['out_dur_s'] / r['n_chars'] for r in sub
                   if r.get('n_chars') and r.get('out_dur_s')]
            ratio = [r['out_dur_s'] / r['src_dur_s'] for r in sub
                     if r.get('src_dur_s') and r.get('out_dur_s')]
            ers = {}
            for r in sub:
                k = str(r.get('end_reason'))
                ers[k] = ers.get(k, 0) + 1
            per[voice] = {
                'n': len(sub),
                'n_empty': sum(1 for r in sub if not r.get('out_dur_s')),
                'out_dur_p50': pct(durs, 0.50),
                'rtf_p50': pct(rtfs, 0.50),
                'rtf_p95': pct(rtfs, 0.95),
                'n_hit_frame_cap_frames': sum(
                    1 for r in sub
                    if isinstance(r.get('frames_out'), (int, float))
                    and isinstance(r.get('max_new_tokens'), (int, float))
                    and r['frames_out'] >= r['max_new_tokens']),
                'end_reason_dist': ers,
                'sec_per_char_p50': round(st.median(spc), 6) if spc else None,
                'sec_per_char_p25': (round(sorted(spc)[int(0.25 * (len(spc) - 1))], 6)
                                     if spc else None),
                'sec_per_char_p75': (round(sorted(spc)[int(0.75 * (len(spc) - 1))], 6)
                                     if spc else None),
                'src_dur_ratio_p50': round(st.median(ratio), 4) if ratio else None,
                'n_with_src_dur': len(ratio),
            }
        ev['per_lang'][lang] = per

    # ── 🔴 反证组：把前 3 行的 frames_out 改成 >= max_new_tokens ──
    tampered = [dict(r) for r in rows]
    for r in tampered[:3]:
        if isinstance(r.get('max_new_tokens'), (int, float)):
            r['frames_out'] = int(r['max_new_tokens'])
    t_hit = sum(
        1 for r in tampered
        if isinstance(r.get('frames_out'), (int, float))
        and isinstance(r.get('max_new_tokens'), (int, float))
        and r['frames_out'] >= r['max_new_tokens'])
    ev['neg_control'] = {
        'base_hit': hit,
        'tampered_hit': t_hit,
        'n_tampered_rows': min(3, len(rows)),
        'pass': (t_hit > hit),
        'note': ('🔴 反证：把前 3 行的 frames_out 抬到 max_new_tokens '
                 '⇒ 计数必须增加 ⇒ 证明判据能触发（否则「撞上限=0」无说服力）'),
    }

    ev['verdict'] = 'RAN'
    if mt:
        ev['mt_rows'] = len(mt.get('rows', []))
    if tts:
        ev['tts_exec_devices'] = tts.get('exec_devices')
        ev['tts_engine'] = {
            'preset_embed_shape': tts.get('preset_embed_shape'),
            'clone_embed_shape': tts.get('clone_embed_shape'),
            'preset_wav': tts.get('preset_wav'),
            'clone_ref_wav': tts.get('clone_ref_wav'),
        }
    _dump(ev)
    return 0


def _dump(ev):
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT)


if __name__ == '__main__':
    raise SystemExit(main())
