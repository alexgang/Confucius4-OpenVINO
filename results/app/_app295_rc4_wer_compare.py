#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app295_rc4_wer_compare.py —— **rc4 两臂 WER / 性能对照汇总**。

## 输入（都是 app294 跑出来的，**不重跑**）

* `results/app/app294_rc4_npu_out/npu/transcript.txt`  ← `--engine npu_int8`
* `results/app/app294_rc4_npu_out/igpu/transcript.txt` ← `--engine gpu_int8`

## WER 的**参考文本**用哪份？

**`reports/spe_61min_transcript.txt` 的前 300 s**。

理由（可自证）：
* 素材 `shared/SPE_0000_0500.wav` **就是** `test_audio/260902_SPE_audio.wav`
  的**前 300.000 s**（实测逐样本相关系数 **1.000000**，见证据）。
* `reports/spe_61min_transcript.txt` 是那份 61 min 音频的**离线转写**
  （`[起-止] 文本` 逐段格式）⇒ 取 `t0 < 300` 的段 ⇒ 就是同一段音频的参考。

⚠️ **口径声明（必须如实说）**：这份参考**不是人工逐字校对稿**，
而是**同模型族的离线转写**。⇒
* 它**能**回答「NPU 档 vs iGPU 档 谁的输出更接近同一份参考」；
* 它**不能**替代「对人工真值的绝对 WER」——
  绝对 WER 仍需 reviewer 用人工校对稿（或其既定 MiniMax 回转写流程）判定。
⇒ 本脚本**两个数都给**：
  ① `wer_vs_ref`：两臂各自对参考的 WER（**可比**）；
  ② `wer_npu_vs_igpu`：NPU 臂直接对 iGPU 臂的 WER（**纯对照，不依赖参考**）。

## 其它指标（都从 app294 的原始字段取，不推算）

* RTF / 首字延迟：从 App 自己打的 summary（`app294` 已解析进 `parsed`）。
* 峰值内存：app294 外部采样的 RSS 峰值。
* 实际执行设备：从日志抓（`EXECUTION_DEVICES` / `设备 NPU`）。

用法：
    .venv/Scripts/python.exe results/app/_app295_rc4_wer_compare.py
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
OUTROOT = os.path.join(HERE, 'app294_rc4_npu_out')
REF_61MIN = os.path.join(REPO, 'reports', 'spe_61min_transcript.txt')
EVID = os.path.join(HERE, 'app295_rc4_wer_compare_evidence.json')
EVID294 = os.path.join(HERE, 'app294_rc4_npu_acceptance_evidence.json')
DUR_S = 300.0


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9'\s]", ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def wer(ref: str, hyp: str) -> dict:
    r = norm(ref).split()
    h = norm(hyp).split()
    if not r:
        return {'wer': None, 'why': '参考为空'}
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev = d[0]
        d[0] = i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1,
                       prev + (0 if r[i - 1] == h[j - 1] else 1))
            prev = cur
    n = d[len(h)]
    return {'wer': round(n / len(r), 6), 'n_edits': n,
            'n_ref_words': len(r), 'n_hyp_words': len(h),
            'wer_pct': round(100.0 * n / len(r), 4)}


def ref_text() -> dict:
    """取 61 min 离线转写里 t0 < 300 s 的段，拼成参考文本。"""
    txt = open(REF_61MIN, encoding='utf-8', errors='replace').read()
    segs = re.findall(r'\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.+)', txt)
    sel = [(float(a), float(b), c.strip()) for a, b, c in segs if float(a) < DUR_S]
    body = ' '.join(c for _a, _b, c in sel)
    return {'src': REF_61MIN, 'n_segments_total': len(segs),
            'n_segments_used': len(sel),
            'first_seg_t0': sel[0][0] if sel else None,
            'last_seg_t1': sel[-1][1] if sel else None,
            'text': body}


def arm_text(arm: str) -> str:
    p = os.path.join(OUTROOT, arm, 'transcript.txt')
    if not os.path.isfile(p):
        return ''
    return open(p, encoding='utf-8', errors='replace').read()


def main() -> int:
    ev = {'script': os.path.basename(__file__),
          'ref': ref_text(),
          'note': ('参考 = reports/spe_61min_transcript.txt 前 300 s'
                   '（同模型族离线转写，**非人工逐字校对稿**）'
                   '⇒ wer_vs_ref 是两臂**可比**指标；'
                   '绝对 WER 仍需 reviewer 判定。')}
    ev['ref'].pop('text', None)

    hyp = {a: arm_text(a) for a in ('npu', 'igpu')}
    ev['arms'] = {}
    for a, h in hyp.items():
        d = {'transcript_bytes': len(h.encode('utf-8')),
             'n_words': len(norm(h).split())}
        ev['arms'][a] = d
    # 参考文本
    ref = ref_text()['text']

    # ① 两臂各自对参考
    for a, h in hyp.items():
        ev['arms'][a]['wer_vs_ref'] = wer(ref, h) if h else None
    # ② NPU 直接对 iGPU（不依赖参考）
    if hyp['npu'] and hyp['igpu']:
        ev['wer_npu_vs_igpu'] = wer(hyp['igpu'], hyp['npu'])
    else:
        ev['wer_npu_vs_igpu'] = None

    # ③ 性能（从 app294 的原始字段取）
    if os.path.isfile(EVID294):
        e294 = json.load(open(EVID294, encoding='utf-8'))
        perf = {}
        for a, d in e294.get('arms', {}).items():
            perf[a] = {
                'engine': d.get('engine'), 'asr_device': d.get('asr_device'),
                'rc': d.get('rc'), 'wall_s': d.get('wall_s'),
                'rtf_wall_over_audio': round(d.get('wall_s', 0) / DUR_S, 4),
                'peak_mem_mb': d.get('peak_mem_mb'),
                'mem_samples': d.get('mem_samples'),
                'parsed': d.get('parsed'),
                'transcript_bytes': d.get('transcript_bytes'),
                'log': d.get('log'),
            }
        ev['perf'] = perf
        ev['perf_source'] = EVID294
        ev['audio_s'] = DUR_S

    # ④ 体积增量
    bp = os.path.join(HERE, 'app291_minimvp_rc4_build_evidence.json')
    if os.path.isfile(bp):
        b = json.load(open(bp, encoding='utf-8'))
        ev['size'] = {'base_bytes': b.get('base_bytes'),
                      'dst_bytes': b.get('dst_bytes'),
                      'delta_bytes': b.get('delta_bytes'),
                      'delta_gb': round((b.get('delta_bytes') or 0) / 1073741824.0,
                                        4),
                      'base_gb': round((b.get('base_bytes') or 0) / 1073741824.0,
                                       4),
                      'dst_gb': round((b.get('dst_bytes') or 0) / 1073741824.0,
                                      4),
                      'n_files': b.get('n_files'),
                      'src': bp}

    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)

    print('== WER ==')
    for a in ('npu', 'igpu'):
        w = ev['arms'][a].get('wer_vs_ref')
        print('  %-5s wer_vs_ref = %s' % (a, json.dumps(w, ensure_ascii=False)
                                           if w else None))
    print('  npu_vs_igpu =', json.dumps(ev.get('wer_npu_vs_igpu'),
                                       ensure_ascii=False))
    print('== 性能 ==')
    for a, d in (ev.get('perf') or {}).items():
        print('  %-5s wall=%.1fs rtf=%.4f peak_mem=%s MB engine=%s dev=%s'
              % (a, d['wall_s'], d['rtf_wall_over_audio'], d['peak_mem_mb'],
                 d['engine'], d['asr_device']))
        if d.get('parsed'):
            print('        parsed:', json.dumps(d['parsed'], ensure_ascii=False)[:220])
    print('== 体积 ==')
    print(' ', json.dumps(ev.get('size'), ensure_ascii=False)[:400])
    print('\n证据：%s' % EVID)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
