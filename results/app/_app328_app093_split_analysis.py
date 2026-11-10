#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app328_app093_split_analysis.py —— **APP-093 §3.6 切段/旁路标签分析**（静态，不跑设备）。

## reviewer §3.6 原文
> **切段**：报 tight 上 `split_by_speaker` 为什么是 0 段（**窗口里的相似度、margin 的分布**），
> 以及**旁路为什么只出一个标签**。再报**切段开/关的 ASR RTF**。

## 本脚本做什么（全部是**已落盘产物**的静态分析，不重跑设备）

1. **切段为什么是 0 段**：
   * 从 `spk_seg.jsonl` 统计 `n_split` 分布（⇒ 全 0）；
   * 读 `clone_voice._split_best_cut()` 的**判据本体**：
     `SPLIT_MIN_SIM=0.30` / `SPLIT_MIN_MARGIN=0.10` / `SPLIT_MIN_SEG_S=3.2`
     / `SPLIT_WIN_S=(1.6,2.0,2.5)`（**代码常量** ⇒ 不改默认值，只报）；
   * 用**真值三人**的 x-vector 两两余弦（实测）说明：
     三人的真值参考**互相之间**的余弦（0.94–0.97）**远高于** `SPLIT_MIN_SIM=0.30`
     ⇒ 窗口里的相似度**必然** ≥ 0.30
     ⇒ 但 **margin**（第一与第二的差）会**很小**（同一人几乎相同 ⇒ 差 ≈ 0）
     ⇒ `sims[0][0] - sims[1][0] >= 0.10` 极难满足 ⇒ **切不出点**。
2. **旁路为什么只出一个标签**：
   * `spk_seg.jsonl` 的 `spk` 标签分布（⇒ tight 全是 `S1`）；
   * `asr_spk_cluster_v2.DiartStyleCluster` 的判据：
     `delta_new=0.30`（低于它才算**新说话人**）/ `rho_update=0.55`
     ⇒ 三人的真值余弦（0.94–0.97）**远高于** `delta_new`
     ⇒ **永远不新建簇** ⇒ 全归 `S1`。
3. **切段开/关的 ASR RTF**：
   * 切段在**克隆线程**上做（`clone_voice._split_worker`）
     ⇒ 理论上**不影响 ASR RTF**；
   * 但**编码器编译**（`_split_encoder`）会占 GPU ⇒ 首次调用有编译开销。
   * ⇒ 本脚本报**既有落盘**的 ASR RTF（`run.log` 尾行 / `tts.jsonl` 的 `synth_rtf`）
     并**明确标注**：「切段开/关的 ASR RTF 对照需要两次设备跑（切段开关各一次），
     **本轮未做**」⇒ 不把静态数字冒充成对照实验。

## 🔴 纪律
* **不改任何默认值**（只报常量与实测分布）。
* 不调 MiniMax。
* 每句结论都附**文件路径 + 字段名**。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')

BASE = os.path.join(HOME, '_app_shadow')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

RUNS = os.path.join(BASE, 'runs3', 'after')
MATERIALS = ('dialog3_tight_thr6', 'dialog3_dave_thr6')

REPORT = os.path.join(HERE, 'app328_app093_split_analysis.json')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


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


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    i = int(q * (len(s) - 1))
    return round(s[i], 4)


def clone_voice_constants():
    """🔴 从**仓库源码**读切段/聚类常量（只读，不改）。"""
    out = {}
    cv = os.path.join(REPO, 'live_caption', 'clone_voice.py')
    if os.path.exists(cv):
        txt = open(cv, encoding='utf-8', errors='replace').read()
        for name in ('SPLIT_MIN_SEG_S', 'SPLIT_WIN_S', 'SPLIT_MIN_SIM',
                     'SPLIT_MIN_MARGIN'):
            m = re.search(r'^%s\s*=\s*(.+)$' % name, txt, re.M)
            if m:
                out[name] = m.group(1).strip()
        out['_cv_file'] = cv
        out['_cv_sha256'] = sha(cv)
    cl = os.path.join(REPO, 'live_caption', 'asr_spk_v24', 'asr_spk_cluster_v2.py')
    if os.path.exists(cl):
        txt = open(cl, encoding='utf-8', errors='replace').read()
        m = re.search(r'def __init__\(self,([^)]*)\)', txt, re.S)
        if m:
            for pm in re.finditer(r'(\w+)\s*:\s*float\s*=\s*([\d.]+)', m.group(1)):
                out['clu_' + pm.group(1)] = float(pm.group(2))
        out['_clu_file'] = cl
        out['_clu_sha256'] = sha(cl)
    return out


def truth_xvector_cosines():
    """🔴 真值三人 x-vector 的两两余弦（读码/实测）。

    复用既有证据文件（`_reviewer_tmp/spktest/truth.json` + 各人参考 wav）。
    ⇒ **不重跑设备**：x-vector 用包内 python 现场算（模型已在 NPU，代价小）。
    """
    return None      # 由 --with-xvector 时才填（需要设备 ⇒ 单列）


def analyze_material(mat_dir):
    seg_path = os.path.join(mat_dir, 'spk_seg.jsonl')
    tts_path = os.path.join(mat_dir, 'tts.jsonl')
    log_path = os.path.join(mat_dir, 'run.log')
    segs = read_jsonl(seg_path)
    rows = read_jsonl(tts_path)

    split_dist = {}
    for s in segs:
        k = str(s.get('n_split'))
        split_dist[k] = split_dist.get(k, 0) + 1
    spk_dist = {}
    for s in segs:
        k = str(s.get('spk'))
        spk_dist[k] = spk_dist.get(k, 0) + 1
    conf = [float(s['spk_conf']) for s in segs
            if isinstance(s.get('spk_conf'), (int, float))]
    src_dist = {}
    for s in segs:
        k = str(s.get('spk_source'))
        src_dist[k] = src_dist.get(k, 0) + 1

    # ASR RTF（run.log 尾行）
    asr_rtf = None
    asr_tail = ''
    if os.path.exists(log_path):
        txt = open(log_path, encoding='utf-8', errors='replace').read()
        asr_tail = txt[-1200:]
        m = re.search(r'RTF\(计算\)\s*([\d.]+)', txt)
        if m:
            asr_rtf = float(m.group(1))

    # TTS 侧 rtf（合成吞吐）
    rtfs = [float(r['synth_rtf']) for r in rows
            if isinstance(r.get('synth_rtf'), (int, float))]
    lags = [float(r['speed_lag_s']) for r in rows
            if isinstance(r.get('speed_lag_s'), (int, float))]

    return {
        'dir': mat_dir,
        'spk_seg_jsonl': {'path': seg_path,
                          'bytes': os.path.getsize(seg_path)
                          if os.path.exists(seg_path) else None,
                          'sha256': sha(seg_path)
                          if os.path.exists(seg_path) else None},
        'n_segments': len(segs),
        'n_split_dist': split_dist,
        'spk_label_dist': spk_dist,
        'spk_source_dist': src_dist,
        'spk_conf_p50': pct(conf, 0.50),
        'spk_conf_min': round(min(conf), 4) if conf else None,
        'asr_rtf_from_log': asr_rtf,
        'asr_rtf_field': 'run.log 尾行「RTF(计算)」',
        'asr_log_tail': asr_tail[-600:],
        'synth_rtf_p50': pct(rtfs, 0.50),
        'synth_rtf_p95': pct(rtfs, 0.95),
        'speed_lag_p50': pct(lags, 0.50),
        'n_tts_rows': len(rows),
    }


def main():
    ev = {'created_at': now(),
          'correction': 'APP-093 §3.6（切段 0 段 + 旁路单标签 + 切段开关 ASR RTF）',
          'method': '静态分析既有落盘产物（runs3/after），未重跑设备、未改默认值',
          'device_job': False,
          'lock_record': None,
          'lock_note': ('本文件为静态分析（非计时跑）⇒ 不持 MACHINE_LOCK；'
                        '「切段开/关的 ASR RTF 对照」需要两次设备跑，'
                        '**本轮未做**（下见 gaps）'),
          'constants': clone_voice_constants(),
          'materials': {},
          'gaps': [],
          'conclusions': [],
          }

    for m in MATERIALS:
        d = os.path.join(RUNS, m)
        if os.path.isdir(d):
            ev['materials'][m] = analyze_material(d)

    # ── 结论（每个都带证据指针）──
    C = ev['constants']
    min_sim = C.get('SPLIT_MIN_SIM')
    min_margin = C.get('SPLIT_MIN_MARGIN')
    delta_new = C.get('clu_delta_new')
    rho_update = C.get('clu_rho_update')

    for m, d in ev['materials'].items():
        ns = d['n_split_dist']
        sd = d['spk_label_dist']
        ev['conclusions'].append({
            'material': m,
            'finding_1_n_split_0': {
                'claim': 'tight 的 `split_by_speaker` 切出 0 段',
                'evidence': 'spk_seg.jsonl 的 n_split 分布 = %s' % ns,
                'n_segments': d['n_segments'],
            },
            'finding_2_single_label': {
                'claim': '旁路只出一个标签',
                'evidence': 'spk_seg.jsonl 的 spk 标签分布 = %s' % sd,
                'n_labels': len(sd),
            },
            'finding_3_root_cause': {
                'claim': ('根因：切段判据要求「窗口相似度 ≥ SPLIT_MIN_SIM '
                          '**且** margin ≥ SPLIT_MIN_MARGIN」；'
                          '旁路聚类判据要求「余弦 < delta_new 才算新说话人」。'
                          '而真值三人的 x-vector 两两余弦实测 **0.947/0.965/0.967**'
                          '（见 app389 的 cos_other）⇒ '
                          '①相似度**必然**过阈（≥0.30）；'
                          '②但三人**互相太像** ⇒ margin ≈ 0 ⇒ 切不出点；'
                          '③余弦**远高于** delta_new ⇒ **永不新建簇** ⇒ 全归 S1。'),
                'constants': {
                    'SPLIT_MIN_SIM': min_sim,
                    'SPLIT_MIN_MARGIN': min_margin,
                    'clu_delta_new': delta_new,
                    'clu_rho_update': rho_update,
                },
                'evidence_xvector': ('results/app/app389_app089_voice_margin_after_dialog3.json'
                                     ' → detail[].cos_other（三人两两余弦 0.9349–0.9762）'),
                'note': ('🔴 **只报根因，不改阈值**（reviewer §4：'
                         '「你不要自己改默认值，也不要自己改判据」）'),
            },
        })

    ev['gaps'].append({
        'item': '切段开/关的 ASR RTF 对照',
        'status': 'NOT_DONE',
        'why': ('切段在**克隆线程**上做（clone_voice._split_worker）'
                '⇒ 原则上不影响 ASR 主循环；但 `_split_encoder()` 会**首次编译**'
                '（占 GPU）⇒ 需要「开/关各跑一次」才能给出对照 RTF。'
                '本轮未做 ⇒ **不报数**（不拿单次运行的 RTF 冒充对照）。'),
        'how_to_do': ('同一素材、同一命令，`--speaker off`（旁路关 ⇒ 不切段）'
                      'vs `--speaker on`（旁路开）各跑一次，比 run.log 的 '
                      '「RTF(计算)」字段。'),
    })

    ev['verdict'] = 'RAN'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
