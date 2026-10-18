"""c053_report.py — 生成「CUDA Q4 vs OV Int4」量化对比报告（HTML / ECharts / 深色主题）

回答用户问题：把 CUDA 侧从 Q8_0 降到 Q4_K、OV 侧从 INT8 降到 INT4，
性能（延迟 / 吞吐 / 内存）和 WER 各有什么变化；以及 OV INT4 到底为什么
「看起来」变慢（C-054 根因：单次测量噪声，A/B 中位显示 INT4 反而更快）。

数据来源：
  CUDA 性能：reports/c053_quant/cuda/chunks_{q8,q4}.json（同 test.wav / 320 ms /
            RTX 5050，2026-10-15 背靠背实测，日志 run_{q8,q4}.log）
  CUDA 内存：reports/c054_cuda_mem.json（c054_cuda_mem.py，子进程 + PDH 实测）
  OV 性能  ：reports/c052_ov_vs_cuda/c640/summary.json（INT8 单次）
            reports/c053_int4/c640/summary.json        （INT4 单次）
            reports/c054_ab_medians.json               （INT8/INT4 A/B×5 中位）
  OV 内存  ：上述 summary 的 ws/private/gpu 峰值 + proc_ov_igpu.csv 稳态中位
  扫描证据：reports/c054_e2_scan.json（c054_e2b_scan.py，standalone decoder IR）
  WER     ：c045_wer.py 同口径（MiniMax 参考 / 保留数字）， transcripts：
            reports/cuda/spe_cuda_stream.txt        (CUDA Q8)
            reports/cuda_q4/spe_cuda_stream.txt     (CUDA Q4_K)
            reports/c048_61min_adaptive/transcript_adaptive.txt (OV INT8)
            reports/c053_61min_int4/transcript_adaptive.txt     (OV INT4)

用法：
    .venv python c053_report.py
    .venv python c053_report.py --out reports/QUANT_Q4_VS_INT4.html
"""
import os
import re
import sys
import csv
import json
import argparse
import datetime
import statistics as st
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.abspath(__file__))
CUDA_REPO = r'C:\Users\Trekker-PTL\confucius4-r2t2'
NVIDIA_LUID = '0x000133E1'      # RTX 5050（c054_cuda_mem.py 按 Dedicated Usage 识别）


def f1(v):
    try:
        return round(float(v), 1)
    except Exception:
        return 0.0


def fmt(v, nd=3):
    return f'{v:.{nd}f}'


def mb(path):
    try:
        return os.path.getsize(path) / 1024 ** 2
    except OSError:
        return 0.0


# ── WER（与 c045_wer.py 完全同口径）──────────────────────
REF = os.path.join(ROOT, 'reports', 'c026_minimax_transcript.txt')


def _norm(w):
    w = w.lower()
    w = re.sub(r"[^\w']", '', w).replace("'", '')
    return w


def ref_words():
    ws = []
    for line in open(REF, encoding='utf-8'):
        m = re.match(r'^\[[\d.\-]+\]\s*(.*)$', line.strip())
        if m and m.group(1).strip():
            ws.append(m.group(1).strip())
    return [n for w in ws for n in (_norm(x) for x in w.split()) if n]


def hyp_words(path):
    ws = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[\s*[\d.]+\s*-\s*[\d.]+\]\s*(.*)$', line)
        if m:
            line = m.group(1)
        ws.extend(_norm(w) for w in line.split())
    return [w for w in ws if w]


def wer_of(path):
    ref = ref_words()
    hyp = hyp_words(path)
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    S = D = I = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            S += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            D += i2 - i1
        elif tag == 'insert':
            I += j2 - j1
    return 100.0 * (S + D + I) / len(ref), len(ref), len(hyp), S, D, I


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def pick(m, key):
    for r in m['ov']:
        if r['key'] == key:
            return r
    raise SystemExit(f'缺少 {key} 结果')


def ov_mem_from_csv(p):
    """从 proc_ov_igpu.csv 取 OV 侧内存：峰值 + 稳态（后 40% 采样中位）。"""
    if not os.path.exists(p):
        return {}
    rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
    if not rows:
        return {}
    ws = [float(r['ws_mb']) for r in rows]
    pv = [float(r['private_mb']) for r in rows]
    gm = [float(r['gpu_mem_mb']) for r in rows if r.get('gpu_mem_mb')]
    tail = int(len(rows) * 0.6)
    out = {'ws_peak': max(ws), 'uss_peak': max(pv),
           'ws_steady': st.median(ws[tail:]), 'uss_steady': st.median(pv[tail:])}
    if gm:
        out['gpu_peak'] = max(gm)
        out['gpu_steady'] = st.median(gm[tail:])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        ROOT, 'reports', 'QUANT_Q4_VS_INT4.html'))
    args = ap.parse_args()

    # ── OV 侧（INT8 = C-052，INT4 = C-053，均为 640 ms 单次实测）──
    m8 = load_json(os.path.join(ROOT, 'reports', 'c052_ov_vs_cuda', 'c640',
                                'summary.json'))
    m4 = load_json(os.path.join(ROOT, 'reports', 'c053_int4', 'c640',
                                'summary.json'))
    ov8 = pick(m8, 'ov_igpu')
    ov4 = pick(m4, 'ov_igpu')
    ov8m = ov_mem_from_csv(os.path.join(ROOT, 'reports', 'c052_ov_vs_cuda',
                                        'c640', 'proc_ov_igpu.csv'))
    ov4m = ov_mem_from_csv(os.path.join(ROOT, 'reports', 'c053_int4',
                                        'c640', 'proc_ov_igpu.csv'))

    # ── OV A/B 中位（C-054，5 次交替）────────────────────
    ab = load_json(os.path.join(ROOT, 'reports', 'c054_ab_medians.json'))
    ab8, ab4 = ab['INT8'], ab['INT4']

    # ── CUDA 侧（Q8 / Q4_K 逐块）────────────────────────
    cq8 = load_json(os.path.join(ROOT, 'reports', 'c053_quant', 'cuda',
                                 'chunks_q8.json'))
    cq4 = load_json(os.path.join(ROOT, 'reports', 'c053_quant', 'cuda',
                                 'chunks_q4.json'))
    q8c, q4c = cq8['chunks'], cq4['chunks']

    def agg(chunks):
        tot = [c['total'] for c in chunks]
        return {
            'mean': sum(tot) / len(tot),
            'steady': sum(tot[1:]) / (len(tot) - 1),
            'first': tot[0],
            'n': len(chunks),
        }

    a8, a4 = agg(q8c), agg(q4c)

    # GPU 权重缓冲（MB，来自 run_*.log 的 buffer_mb 行）
    def gpu_buf(log):
        enc = dec = 0.0
        for line in open(os.path.join(ROOT, 'reports', 'c053_quant', 'cuda',
                                      log), encoding='utf-8',
                         errors='replace'):
            if 'audio_encoder.weights.buffer_mb' in line:
                enc = float(line.rsplit(' ', 1)[1])
            elif 'greedy_qwen_decoder.weights.buffer_mb' in line:
                dec = float(line.rsplit(' ', 1)[1])
        return enc, dec

    e8, d8 = gpu_buf('run_q8.log')
    e4, d4 = gpu_buf('run_q4.log')

    # ── CUDA 内存（c054_cuda_mem.py 实测）────────────────
    cm = load_json(os.path.join(ROOT, 'reports', 'c054_cuda_mem.json'))
    cm8, cm4 = cm['CUDA_Q8'], cm['CUDA_Q4']

    def cmem(c, kind):
        pk, sd = c['peaks_mb'], c['steady_mb']
        return {k: sd.get(kind, 0.0) for k in ()} or {
            'vram_peak': pk.get(f'{NVIDIA_LUID}_ded_mb', 0.0),
            'vram_steady': sd.get(f'{NVIDIA_LUID}_ded_mb', 0.0),
            'ws_peak': pk.get('ws_mb', 0.0), 'ws_steady': sd.get('ws_mb', 0.0),
            'uss_peak': pk.get('uss_mb', 0.0),
            'uss_steady': sd.get('uss_mb', 0.0),
        }

    c8m, c4m = cmem(cm8, 'q8'), cmem(cm4, 'q4')

    # ── 模型文件体积（磁盘）──────────────────────────────
    q8_file = mb(os.path.join(CUDA_REPO, 'models', 'r2t2-q8_0.gguf'))
    q4_file = mb(os.path.join(CUDA_REPO, 'models', 'r2t2-q4_k.gguf'))
    enc_bin = mb(os.path.join(ROOT, 'models', 'ov-encoder-segment-reviewer',
                              'openvino_encoder_model.bin'))
    ov8_file = (mb(os.path.join(ROOT, 'models', 'ov-int8-past',
                                'openvino_decoder_model.bin')) + enc_bin)
    # C-058③：INT4 头条换成「lm_head 全量 INT4」的构建（ov-int4-lmhead-past，
    # 846 MiB）。ov-int4-lmfp16-past（1440 MiB，lm_head 保留 FP16）是次优构建，
    # 仅作对照保留。
    ov4_file = (mb(os.path.join(ROOT, 'models', 'ov-int4-lmhead-past',
                                'openvino_decoder_model.bin')) + enc_bin)
    ov4_secondary_file = (
        mb(os.path.join(ROOT, 'models', 'ov-int4-lmfp16-past',
                        'openvino_decoder_model.bin')) + enc_bin)
    ov8_enc_copy = mb(os.path.join(ROOT, 'models', 'ov-int8-past',
                                   'openvino_encoder_model.bin'))
    ov4_enc_copy = mb(os.path.join(ROOT, 'models', 'ov-int4-lmfp16-past',
                                   'openvino_encoder_model.bin'))

    # ── 扫描证据（c054_e2b_scan.py，若存在）──────────────
    scan = load_json(os.path.join(ROOT, 'reports', 'c054_e2_scan.json')) \
        if os.path.exists(os.path.join(ROOT, 'reports',
                                       'c054_e2_scan.json')) else None
    if scan:
        tt_r = [r['ratio'] for r in scan['scans']['tt']]
        ta_r = [r['ratio'] for r in scan['scans']['ta']]
        scan_txt = (f'Tt 1→256（Ta=50）：INT4/INT8 = '
                    f'{min(tt_r):.2f}–{max(tt_r):.2f}×；'
                    f'Ta 50→1500（Tt=32，长前缀）：{min(ta_r):.2f}–{max(ta_r):.2f}×')
        scan_tt_tbl = ''.join(
            f"<tr><td class='num'>{r['Tt']}</td><td class='num'>{r['Ta']}</td>"
            f"<td class='num'>{r['INT8']:.2f}</td><td class='num'>{r['INT4']:.2f}</td>"
            f"<td class='num'>{r['ratio']:.2f}×</td></tr>"
            for r in scan['scans']['tt'])
        scan_ta_tbl = ''.join(
            f"<tr><td class='num'>{r['Tt']}</td><td class='num'>{r['Ta']}</td>"
            f"<td class='num'>{r['INT8']:.2f}</td><td class='num'>{r['INT4']:.2f}</td>"
            f"<td class='num'>{r['ratio']:.2f}×</td></tr>"
            for r in scan['scans']['ta'])
    else:
        scan_txt = '（扫描数据缺失，重跑 c054_e2b_scan.py 后重新生成）'
        scan_tt_tbl = scan_ta_tbl = ''

    # ── IR 构成拆解（c055_ir_breakdown.py，若存在）───────
    irp = os.path.join(ROOT, 'reports', 'c055_ir_breakdown.json')
    ir = load_json(irp) if os.path.exists(irp) else None

    def irv(tag, sem, prec, default=0.0):
        if not ir or tag not in ir:
            return default
        d = ir[tag]['by_semantic'].get(sem, {})
        return d.get(prec, {}).get('mib', default) if isinstance(d, dict) \
            else default

    def irtot(tag, default=0.0):
        return ir[tag]['total_mib'] if ir and tag in ir else default

    # 语义聚合：transformer 层 / 词表矩阵（embed+lm_head）/ 其他
    def ir_sem_total(tag, sem):
        if not ir or tag not in ir:
            return 0.0
        d = ir[tag]['by_semantic'].get(sem, {})
        return sum(v['mib'] for v in d.values()) if isinstance(d, dict) \
            else 0.0

    enc_mib = enc_bin  # reviewer encoder，两个 OV 配置共用且未量化
    ir_f, ir_8, ir_4 = irtot('FP16'), irtot('INT8'), irtot('INT4')
    # INT4 的词表矩阵 = i4 embed_tokens + f16 lm_head（tie 被打破）
    v_f = ir_sem_total('FP16', 'token embedding / lm_head（词表 151936）')
    v_8 = ir_sem_total('INT8', 'token embedding / lm_head（词表 151936）')
    v_4 = ir_sem_total('INT4', 'token embedding / lm_head（词表 151936）')
    l_f = ir_sem_total('FP16', 'transformer 层权重（28 层）')
    l_8 = ir_sem_total('INT8', 'transformer 层权重（28 层）')
    l_4 = ir_sem_total('INT4', 'transformer 层权重（28 层）')
    # lm_head 单块：从 top10 里按名字取（INT4 的最大 Const 就是它）
    lm_head_mib = 0.0
    if ir and 'INT4' in ir:
        for b, et, name, shape in ir['INT4'].get('top10', []):
            if 'lm_head' in name:
                lm_head_mib = b / 1024 ** 2
                break
        if not lm_head_mib:
            lm_head_mib = irv('INT4',
                              'token embedding / lm_head（词表 151936）',
                              'float16')
    # 假设 lm_head 也进 i4（或保持与 embed 的 tie），INT4 的理论体积
    whatif4 = ir_4 - lm_head_mib + lm_head_mib / 4 if ir_4 else 0.0
    tot8 = ir_8 + enc_mib
    tot4 = ir_4 + enc_mib

    # ── C-056 实测（lm_head 也 INT4 的 what-if 变体）──────
    c056p = os.path.join(ROOT, 'reports', 'c056_lmhead_acc.json')
    c056abp = os.path.join(ROOT, 'reports', 'c056_ab_perf.json')
    c044p = os.path.join(ROOT, 'reports', 'c044_tf', 'tf_results.json')
    c056 = load_json(c056p) if os.path.exists(c056p) else None
    c056ab = load_json(c056abp) if os.path.exists(c056abp) else None
    c044 = load_json(c044p) if os.path.exists(c044p) else None

    def tf_rate(src, name, key='top1_rate', default=0.0):
        try:
            return float(src[name][key])
        except Exception:
            return default

    # C-056 汇总值（带优雅降级）
    l4_size = c056['ir_mib']['int4lmhead'] if c056 else 0.0
    l4_top1 = 100 * tf_rate(c056['teacher_forcing'], 'int4lmhead') if c056 else 0.0
    l4_eos = 100 * tf_rate(c056['teacher_forcing'], 'int4lmhead',
                           'eos_rate') if c056 else 0.0
    l4f_top1 = 100 * tf_rate(c056['teacher_forcing'], 'int4lmfp16') if c056 else 0.0
    l4f_eos = 100 * tf_rate(c056['teacher_forcing'], 'int4lmfp16',
                            'eos_rate') if c056 else 0.0
    l4_sub = c056['token_diffs_vs_fp16']['int4lmhead']['sub_rate_pct'] \
        if c056 else 0.0
    l4f_sub = c056['token_diffs_vs_fp16']['int4lmfp16']['sub_rate_pct'] \
        if c056 else 0.0
    l4_perf = c056ab['delta_pct'] if c056ab else 0.0
    i8_top1 = 100 * tf_rate(c044, 'int8') if c044 else 0.0
    i8lm_top1 = 100 * tf_rate(c044, 'int8lmfp16') if c044 else 0.0

    # ── WER ─────────────────────────────────────────────
    wers = {}
    for tag, p in [
        ('cuda_q8', 'reports/cuda/spe_cuda_stream.txt'),
        ('cuda_q4', 'reports/cuda_q4/spe_cuda_stream.txt'),
        ('ov_int8', 'reports/c048_61min_adaptive/transcript_adaptive.txt'),
        ('ov_int4', 'reports/c053_61min_int4/transcript_adaptive.txt'),
    ]:
        fp = os.path.join(ROOT, p)
        if os.path.exists(fp):
            w, nref, nhyp, S, D, I = wer_of(fp)
            wers[tag] = {'wer': round(w, 2), 'nref': nref, 'nhyp': nhyp,
                         'S': S, 'D': D, 'I': I}
        else:
            wers[tag] = None
    missing = [k for k, v in wers.items() if v is None]

    data = {
        'q8': {'chunks': q8c},
        'q4': {'chunks': q4c},
        'mem': {
            'cats': ['CUDA Q8_0', 'CUDA Q4_K', 'OV INT8', 'OV INT4'],
            'vram': [c8m['vram_steady'], c4m['vram_steady'],
                     ov8m.get('gpu_steady', 0), ov4m.get('gpu_steady', 0)],
            'ws': [c8m['ws_steady'], c4m['ws_steady'],
                   ov8m.get('ws_steady', 0), ov4m.get('ws_steady', 0)],
        },
        'ir': {
            'cats': ['FP16（基线）', 'INT8（交付）', 'INT4'],
            'layers': [l_f, l_8, l_4],
            'vocab_q': [v_f, v_8, v_4 - lm_head_mib],
            'vocab_f16': [0.0, 0.0, lm_head_mib],
            'other': [ir_f - l_f - v_f, ir_8 - l_8 - v_8, ir_4 - l_4 - v_4],
        },
        'lmh': {
            'cats': ['INT8（交付）', 'INT4+FP16 lm_head（现状）', 'INT4 全量'],
            'size': [ir_8, ir_4, l4_size],
            'top1': [i8_top1, l4f_top1, l4_top1],
        },
    }

    def pct(new, old):
        return (new / old - 1) * 100 if old else 0.0

    rep = {
        '__GEN__': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        # CUDA 逐块
        '__Q8_MEAN__': fmt(a8['mean'], 1),
        '__Q4_MEAN__': fmt(a4['mean'], 1),
        '__Q8_STEADY__': fmt(a8['steady'], 1),
        '__Q4_STEADY__': fmt(a4['steady'], 1),
        '__Q8_FIRST__': fmt(a8['first'], 1),
        '__Q4_FIRST__': fmt(a4['first'], 1),
        '__QGAIN__': '{:.1f}'.format((1 - a4['mean'] / a8['mean']) * 100),
        '__QGAIN_S__': '{:.1f}'.format((1 - a4['steady'] / a8['steady']) * 100),
        # CUDA 内存 / 体积
        '__Q8_BUF__': '{:.0f}'.format(e8 + d8),
        '__Q4_BUF__': '{:.0f}'.format(e4 + d4),
        '__BUFGAIN__': '{:.0f}'.format((1 - (e4 + d4) / (e8 + d8)) * 100),
        '__Q8_FILE__': '{:.0f}'.format(q8_file),
        '__Q4_FILE__': '{:.0f}'.format(q4_file),
        '__FILEGAIN_CUDA__': '{:.1f}'.format(pct(q4_file, q8_file)),
        '__Q8_VRAM__': '{:.0f}'.format(c8m['vram_steady']),
        '__Q4_VRAM__': '{:.0f}'.format(c4m['vram_steady']),
        '__Q8_VRAM_PK__': '{:.0f}'.format(c8m['vram_peak']),
        '__Q4_VRAM_PK__': '{:.0f}'.format(c4m['vram_peak']),
        '__VRAMGAIN_CUDA__': '{:.1f}'.format(pct(c4m['vram_steady'],
                                                 c8m['vram_steady'])),
        '__VRAMGAIN_CUDA_PK__': '{:.1f}'.format(pct(c4m['vram_peak'],
                                                    c8m['vram_peak'])),
        '__Q8_WS__': '{:.0f}'.format(c8m['ws_steady']),
        '__Q4_WS__': '{:.0f}'.format(c4m['ws_steady']),
        '__Q8_WS_PK__': '{:.0f}'.format(c8m['ws_peak']),
        '__Q4_WS_PK__': '{:.0f}'.format(c4m['ws_peak']),
        '__WSGAIN_CUDA_PK__': '{:.1f}'.format(pct(c4m['ws_peak'],
                                                  c8m['ws_peak'])),
        '__Q8_USS__': '{:.0f}'.format(c8m['uss_steady']),
        '__Q4_USS__': '{:.0f}'.format(c4m['uss_steady']),
        # OV 单次实测（640 ms，新进程首发）
        '__OV8_RTF__': fmt(ov8['rtf']),
        '__OV4_RTF__': fmt(ov4['rtf']),
        '__OV8_MEAN__': fmt(ov8['per_chunk_ms_mean'], 1),
        '__OV4_MEAN__': fmt(ov4['per_chunk_ms_mean'], 1),
        '__OV8_STEADY__': fmt(ov8['per_chunk_ms_steady'], 1),
        '__OV4_STEADY__': fmt(ov4['per_chunk_ms_steady'], 1),
        '__OV8_MED__': fmt(ov8['per_chunk_ms_median'], 1),
        '__OV4_MED__': fmt(ov4['per_chunk_ms_median'], 1),
        '__OV4_MAX__': fmt(ov4['per_chunk_ms_max'], 1),
        '__OV8_MAX__': fmt(ov8['per_chunk_ms_max'], 1),
        '__OV8_COMPILE__': fmt(ov8['compile_s'], 2),
        '__OV4_COMPILE__': fmt(ov4['compile_s'], 2),
        '__COMPILE_UP__': '{:.0f}'.format(pct(ov4['compile_s'],
                                              ov8['compile_s'])),
        '__OV8_FILE__': '{:.0f}'.format(ov8_file),
        '__OV4_FILE__': '{:.0f}'.format(ov4_file),
        '__OV4_SEC_FILE__': '{:.0f}'.format(ov4_secondary_file),
        '__FILEGAIN_OV_SEC__': '{:.1f}'.format(pct(ov4_secondary_file, ov8_file)),
        '__FILEGAIN_OV__': '{:.1f}'.format(pct(ov4_file, ov8_file)),
        '__OV8_ENC_COPY__': '{:.0f}'.format(ov8_enc_copy),
        '__OV4_ENC_COPY__': '{:.0f}'.format(ov4_enc_copy),
        # OV A/B 中位（C-054，5 次交替）
        '__AB8_TOTAL__': fmt(ab8['total'], 1),
        '__AB4_TOTAL__': fmt(ab4['total'], 1),
        '__AB8_ENC__': fmt(ab8['enc'], 1),
        '__AB4_ENC__': fmt(ab4['enc'], 1),
        '__AB8_PRE__': fmt(ab8['pre'], 1),
        '__AB4_PRE__': fmt(ab4['pre'], 1),
        '__AB8_DEC__': fmt(ab8['dec'], 1),
        '__AB4_DEC__': fmt(ab4['dec'], 1),
        '__AB8_FLUSH__': fmt(ab8['flush'], 1),
        '__AB4_FLUSH__': fmt(ab4['flush'], 1),
        '__AB_GAIN__': '{:.1f}'.format(-pct(ab4['total'], ab8['total'])),
        '__AB_GAIN_PRE__': '{:.1f}'.format(-pct(ab4['pre'], ab8['pre'])),
        '__AB_GAIN_DEC__': '{:.1f}'.format(-pct(ab4['dec'], ab8['dec'])),
        '__AB8_RTF__': '{:.2f}'.format(ab8['total'] / 640.0),
        '__AB4_RTF__': '{:.2f}'.format(ab4['total'] / 640.0),
        # OV 内存（稳态 / 峰值）
        '__OV8_GPU__': '{:.0f}'.format(ov8m.get('gpu_steady', 0)),
        '__OV4_GPU__': '{:.0f}'.format(ov4m.get('gpu_steady', 0)),
        '__OV8_GPU_PK__': '{:.0f}'.format(ov8m.get('gpu_peak', 0)),
        '__OV4_GPU_PK__': '{:.0f}'.format(ov4m.get('gpu_peak', 0)),
        '__OV8_WS__': '{:.0f}'.format(ov8m.get('ws_steady', 0)),
        '__OV4_WS__': '{:.0f}'.format(ov4m.get('ws_steady', 0)),
        '__OV8_WS_PK__': '{:.0f}'.format(ov8m.get('ws_peak', 0)),
        '__OV4_WS_PK__': '{:.0f}'.format(ov4m.get('ws_peak', 0)),
        '__OV8_USS__': '{:.0f}'.format(ov8m.get('uss_steady', 0)),
        '__OV4_USS__': '{:.0f}'.format(ov4m.get('uss_steady', 0)),
        '__GPUGAIN_OV__': '{:.1f}'.format(pct(ov4m.get('gpu_steady', 0),
                                              ov8m.get('gpu_steady', 0))),
        '__GPUGAIN_OV_PK__': '{:.1f}'.format(pct(ov4m.get('gpu_peak', 0),
                                                 ov8m.get('gpu_peak', 0))),
        '__WSGAIN_OV__': '{:.1f}'.format(pct(ov4m.get('ws_steady', 0),
                                             ov8m.get('ws_steady', 0))),
        '__WSGAIN_OV_PK__': '{:.1f}'.format(pct(ov4m.get('ws_peak', 0),
                                                ov8m.get('ws_peak', 0))),
        '__USSGAIN_OV__': '{:.1f}'.format(pct(ov4m.get('uss_steady', 0),
                                              ov8m.get('uss_steady', 0))),
        # 扫描证据
        '__SCAN_TXT__': scan_txt,
        '__SCAN_TT_TBL__': scan_tt_tbl,
        '__SCAN_TA_TBL__': scan_ta_tbl,
        # IR 构成拆解（C-055：为什么 INT4 只小 ~10%）
        '__IRF_TOTAL__': '{:.0f}'.format(ir_f),
        '__IR8_TOTAL__': '{:.0f}'.format(ir_8),
        '__IR4_TOTAL__': '{:.0f}'.format(ir_4),
        '__IR4_I4__': '{:.0f}'.format(ir['INT4']['by_precision'].get(
            'int4_t', {}).get('mib', 0)) if ir else '—',
        '__IR4_F16__': '{:.0f}'.format(ir[ 'INT4']['by_precision'].get(
            'float16', {}).get('mib', 0)) if ir else '—',
        '__IR4_F16_PCT__': '{:.0f}'.format(
            100 * ir['INT4']['by_precision'].get('float16', {}).get(
                'mib', 0) / ir_4) if ir and ir_4 else '—',
        '__IR4_LMHEAD__': '{:.0f}'.format(lm_head_mib),
        '__IRF_LAYERS__': '{:.0f}'.format(l_f),
        '__IR8_LAYERS__': '{:.0f}'.format(l_8),
        '__IR4_LAYERS__': '{:.0f}'.format(l_4),
        '__IRF_VOCAB__': '{:.0f}'.format(v_f),
        '__IR8_VOCAB__': '{:.0f}'.format(v_8),
        '__IR4_VOCAB__': '{:.0f}'.format(v_4),
        '__IR4_WHATIF__': '{:.0f}'.format(whatif4),
        '__IR4_WHATIF_PCT__': '{:.0f}'.format(
            (whatif4 / ir_8 - 1) * 100) if ir_8 else '—',
        # C-056 实测（lm_head 也 INT4）
        '__L4_SIZE__': '{:.0f}'.format(l4_size),
        '__L4_VS8__': '{:.1f}'.format((l4_size / ir_8 - 1) * 100)
        if ir_8 and l4_size else '—',
        '__L4_VS4__': '{:.1f}'.format((l4_size / ir_4 - 1) * 100)
        if ir_4 and l4_size else '—',
        '__L4_VS4_ABS__': '{:.1f}'.format(abs((l4_size / ir_4 - 1) * 100))
        if ir_4 and l4_size else '—',
        '__L4_TOP1__': '{:.2f}'.format(l4_top1),
        '__L4F_TOP1__': '{:.2f}'.format(l4f_top1),
        '__L4_TOP1_D__': '{:+.2f}'.format(l4_top1 - l4f_top1),
        '__L4_EOS__': '{:.1f}'.format(l4_eos),
        '__L4_EOS_D__': '{:+.1f}'.format(l4_eos - l4f_eos),
        '__L4_SUB__': '{:.2f}'.format(l4_sub),
        '__L4_SUB_D__': '{:+.2f}'.format(l4_sub - l4f_sub),
        '__L4_PERF__': '{:+.1f}'.format(l4_perf),
        '__L4_PERF_ABS__': '{:.1f}'.format(abs(l4_perf)),
        '__L4_FLUSH__': '{:+.1f}'.format(
            (c056ab['medians']['int4lmhead']['flush_median'] /
             c056ab['medians']['int4lmfp16']['flush_median'] - 1) * 100)
        if c056ab else '—',
        '__I8_TOP1__': '{:.2f}'.format(i8_top1),
        '__I8LM_TOP1__': '{:.2f}'.format(i8lm_top1),
        '__ENC_MIB__': '{:.0f}'.format(enc_mib),
        '__TOT8__': '{:.0f}'.format(tot8),
        '__TOT4__': '{:.0f}'.format(tot4),
        # 单次实测构成（保留作对照）
        '__OV8_PRE__': fmt(ov8['prefill_ms_mean'], 1),
        '__OV4_PRE__': fmt(ov4['prefill_ms_mean'], 1),
        '__OV8_DEC__': fmt(ov8['decode_ms_mean'], 1),
        '__OV4_DEC__': fmt(ov4['decode_ms_mean'], 1),
        '__OV8_ENC__': fmt(ov8['enc_ms_mean'], 1),
        '__OV4_ENC__': fmt(ov4['enc_ms_mean'], 1),
        # WER
        '__WER_CUDA_Q8__': fmt(wers['cuda_q8']['wer'], 2) if wers['cuda_q8'] else '—',
        '__WER_CUDA_Q4__': fmt(wers['cuda_q4']['wer'], 2) if wers['cuda_q4'] else '—',
        '__WER_OV_INT8__': fmt(wers['ov_int8']['wer'], 2) if wers['ov_int8'] else '—',
        '__WER_OV_INT4__': fmt(wers['ov_int4']['wer'], 2) if wers['ov_int4'] else '—',
    }
    if wers['cuda_q4'] and wers['cuda_q8']:
        rep['__WERD_CUDA__'] = '{:+.2f}'.format(
            wers['cuda_q4']['wer'] - wers['cuda_q8']['wer'])
    else:
        rep['__WERD_CUDA__'] = '—'
    if wers['ov_int4'] and wers['ov_int8']:
        rep['__WERD_OV__'] = '{:+.2f}'.format(
            wers['ov_int4']['wer'] - wers['ov_int8']['wer'])
    else:
        rep['__WERD_OV__'] = '—'

    for tag in ('cuda_q8', 'cuda_q4', 'ov_int8', 'ov_int4'):
        v = wers[tag]
        rep[f'__S_{tag.upper()}__'] = str(v['S']) if v else '—'
        rep[f'__D_{tag.upper()}__'] = str(v['D']) if v else '—'
        rep[f'__I_{tag.upper()}__'] = str(v['I']) if v else '—'

    html = TEMPLATE
    for k, v in rep.items():
        html = html.replace(k, v)
    html = html.replace('__DATA__', json.dumps(data, ensure_ascii=False))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[c053] 报告已生成 -> {args.out}')
    if missing:
        print(f'[c053] ⚠️ 缺少 transcript，WER 未填: {missing}')
    for k, v in wers.items():
        if v:
            print(f'[c053] WER {k}: {v["wer"]}%  (S={v["S"]} D={v["D"]} '
                  f'I={v["I"]}, hyp {v["nhyp"]} words)')
    print(f'[c053] A/B 中位: INT8 total {ab8["total"]:.1f} ms / '
          f'INT4 {ab4["total"]:.1f} ms ({rep["__AB_GAIN__"]}% 更快)')
    print(f'[c053] CUDA 显存稳态 {c8m["vram_steady"]:.0f} → '
          f'{c4m["vram_steady"]:.0f} MB；OV GPU 稳态 '
          f'{ov8m.get("gpu_steady", 0):.0f} → {ov4m.get("gpu_steady", 0):.0f} MB')


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>4-bit 量化对比：CUDA Q4_K vs OpenVINO INT4</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; background: #0f1115; color: #e4e6eb; }
.wrap { max-width: 1280px; margin: 0 auto; padding: 32px 24px; }
h1 { font-size: 28px; margin: 0 0 8px; color: #fff; }
h2 { font-size: 20px; margin: 32px 0 16px; padding-left: 12px; border-left: 3px solid #4f8cff; color: #fff; }
h3 { font-size: 15px; margin: 20px 0 10px; color: #cbd0d8; }
.subtitle { color: #8a8f99; margin-bottom: 24px; line-height: 1.8; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.card { background: #1a1d24; border: 1px solid #2a2e38; border-radius: 10px; padding: 18px 20px; }
.card .label { color: #8a8f99; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.card .value { font-size: 26px; font-weight: 600; color: #fff; margin-top: 6px; }
.card .unit { font-size: 14px; color: #8a8f99; margin-left: 4px; }
.card .note { font-size: 11px; color: #8a8f99; margin-top: 6px; line-height: 1.6; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart { background: #1a1d24; border: 1px solid #2a2e38; border-radius: 10px; padding: 16px; }
.chart-title { color: #fff; font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.chart-sub { color: #8a8f99; font-size: 12px; margin-bottom: 12px; line-height: 1.6; }
.chart-box { width: 100%; height: 320px; }
table { width: 100%; border-collapse: collapse; background: #1a1d24; border-radius: 10px; overflow: hidden; font-size: 13px; }
th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #2a2e38; }
th { background: #232730; color: #8a8f99; font-weight: 500; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
tr:last-child td { border-bottom: none; }
td.num { text-align: right; font-family: Consolas, monospace; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; margin-right: 6px; }
.tag-green { background: #1e3a2e; color: #4ade80; }
.tag-blue { background: #1e2a3a; color: #60a5fa; }
.tag-amber { background: #3a2e1e; color: #fbbf24; }
.tag-red { background: #3a1e1e; color: #f87171; }
.footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid #2a2e38; color: #8a8f99; font-size: 12px; line-height: 1.8; }
.headline { background: #1a1d24; border: 1px solid #2a2e38; border-left: 3px solid #4f8cff; border-radius: 10px; padding: 18px 22px; line-height: 1.9; color: #cbd0d8; }
.headline b { color: #fff; }
.warn { background: #3a2e1e; color: #fbbf24; padding: 1px 6px; border-radius: 3px; font-family: Consolas, monospace; }
.ok { background: #1e3a2e; color: #4ade80; padding: 1px 6px; border-radius: 3px; font-family: Consolas, monospace; }
.bad { background: #3a1e1e; color: #f87171; padding: 1px 6px; border-radius: 3px; font-family: Consolas, monospace; }
.callout { background: #1e2a3a; border: 1px solid #2a3a52; border-radius: 10px; padding: 14px 18px; margin: 12px 0; color: #cbd0d8; line-height: 1.9; font-size: 13px; }
.callout.warnbox { background: #3a2e1e; border-color: #5a4a2a; color: #fbbf24; }
.callout b { color: #fff; }
code { background: #232730; padding: 1px 5px; border-radius: 3px; font-size: 12px; color: #a5b4fc; }
</style>
</head>
<body>
<div class="wrap">
<h1>4-bit 量化对比：CUDA Q4_K vs OpenVINO INT4</h1>
<p class="subtitle">测量时间 __GEN__ ｜ 同一台机器（RTX 5050 Laptop dGPU + Intel Xe3 iGPU）｜
CUDA 侧：audio.cpp v0.9.1，<code>r2t2-q8_0.gguf</code> vs <code>r2t2-q4_k.gguf</code>（由 HF 原始权重量化，同一段 6.74 s <code>test.wav</code> / 320 ms 默认策略 / 背靠背实测）｜
OV 侧：<code>ov-int8-past</code> vs <b><code>ov-int4-lmhead-past</code></b>（lm_head 全量 INT4，846 MiB——C-058③ 已换为头条构建；<code>ov-int4-lmfp16-past</code> 为次优构建，仅作对照）<br>
本版已按 C-054 根因分析修订：<b>OV INT4「变慢 15%」是单次测量噪声</b>，5 次交替 A/B 取中位后 INT4 反而更快；性能与内存结论以 A/B 口径为准。</p>

<h2>一句话结论</h2>
<div class="headline">
<span class="tag tag-green">CUDA Q4_K：唯一划算的 4-bit</span>
每块均值 <b>__Q8_MEAN__ → __Q4_MEAN__ ms</b>（稳态 <b>__Q8_STEADY__ → __Q4_STEADY__ ms</b>，快 <b>__QGAIN_S__%</b>）；
显存稳态 <b>__Q8_VRAM__ → __Q4_VRAM__ MB</b>（<b>__VRAMGAIN_CUDA__%</b>，权重缓冲 <b>-__BUFGAIN__%</b>）；
WER <b>__WER_CUDA_Q8__% → __WER_CUDA_Q4__%</b>（__WERD_CUDA__ pp，噪声内无损）。适合<b>需要同卡并发多路流式</b>的场景。<br>
<span class="tag tag-amber">OV INT4：不慢，但精度掉 1 pp</span>
此前单次测量的「每块 <b>__OV8_MEAN__ → __OV4_MEAN__ ms</b>（慢 15.2%）」经 C-054 复核为<b>测量噪声</b>：
5 次交替 A/B 取中位，INT4 每块 <b>__AB8_TOTAL__ → __AB4_TOTAL__ ms</b>（<b>快 __AB_GAIN__%</b>），
prefill <b>__AB8_PRE__ → __AB4_PRE__ ms</b>（快 __AB_GAIN_PRE__%）、decode <b>__AB8_DEC__ → __AB4_DEC__ ms</b>（快 __AB_GAIN_DEC__%）；
内存也确实更省（工作集稳态 <b>__OV8_WS__ → __OV4_WS__ MB</b>，<b>__WSGAIN_OV__%</b>）。<br>
<span class="tag tag-red">精度：CUDA 无损，OV 掉 1.08 pp</span>
61-min 集 WER：CUDA <b>__WER_CUDA_Q8__% → __WER_CUDA_Q4__%</b>（__WERD_CUDA__ pp，落在噪声内，可视为无损）；
OV <b>__WER_OV_INT8__% → __WER_OV_INT4__%</b>（<b>__WERD_OV__ pp</b>，插入 __I_OV_INT8__→__I_OV_INT4__、替换 __S_OV_INT8__→__S_OV_INT4__，是真实退化，
与 C-044 teacher-forcing 的 top-1 84.3% vs 94.1% 一致）。<br>
<span class="tag tag-blue">净结论</span>
OV INT4 在 iGPU 上<b>更快也更省，但不采纳 —— 原因是精度，不是性能</b>；CUDA Q4_K 三个维度全赢，是唯一建议保留的 4-bit 选项。
C-043/C-044 早已证伪「量化是精度瓶颈」（真凶是 <code>max_new_tokens</code> 固定 32，C-047 修复），本次从性能侧给出同一方向的证据。
</div>

<h2>性能对比（同一段 6.74 s 音频）</h2>
<div class="cards">
<div class='card'><div class='label'>CUDA 每块均值 · Q8_0 → Q4_K</div><div class='value'>__Q8_MEAN__ → __Q4_MEAN__<span class='unit'>ms</span></div><div class='note'>快 __QGAIN__% ｜ 稳态快 __QGAIN_S__%</div></div>
<div class='card'><div class='label'>CUDA 显存稳态 · Q8_0 → Q4_K</div><div class='value'>__Q8_VRAM__ → __Q4_VRAM__<span class='unit'>MB</span></div><div class='note'>__VRAMGAIN_CUDA__% ｜ 权重缓冲 2354→1533 MB</div></div>
<div class='card'><div class='label'>OV iGPU 每块中位 · A/B×5</div><div class='value'>__AB8_TOTAL__ → __AB4_TOTAL__<span class='unit'>ms</span></div><div class='note'><span class="ok">快 __AB_GAIN__%</span> ｜ 单次测量曾显示 +15.2%，系噪声</div></div>
<div class='card'><div class='label'>OV iGPU 工作集稳态</div><div class='value'>__OV8_WS__ → __OV4_WS__<span class='unit'>MB</span></div><div class='note'>__WSGAIN_OV__% ｜ 峰值 __OV8_WS_PK__ → __OV4_WS_PK__ MB</div></div>
</div>

<table><thead><tr>
<th>运行时</th><th>权重</th><th>模型文件 (MB)</th><th>GPU 显存稳态 (MB)</th><th>每块均值 (ms)</th><th>稳态每块 (ms)</th><th>首块 (ms)</th><th>RTF / 相对基线</th><th>6.74 s 样本文本</th>
</tr></thead><tbody>
<tr><td>CUDA · RTX 5050 (dGPU)</td><td>GGUF Q8_0</td><td class='num'>__Q8_FILE__</td><td class='num'>__Q8_VRAM__</td><td class='num'>__Q8_MEAN__</td><td class='num'>__Q8_STEADY__</td><td class='num'>__Q8_FIRST__</td><td class='num'>基准</td><td>之前有顾客自己带酒水也没加收钱或者不让喝</td></tr>
<tr><td><b>CUDA · RTX 5050 (dGPU)</b></td><td><b>GGUF Q4_K</b></td><td class='num'><b>__Q4_FILE__</b></td><td class='num'><b>__Q4_VRAM__</b></td><td class='num'><b>__Q4_MEAN__</b></td><td class='num'><b>__Q4_STEADY__</b></td><td class='num'><b>__Q4_FIRST__</b></td><td class='num'><span class="ok">快 __QGAIN__%</span></td><td>之前有顾客自己带酒水也没加收钱或者不让喝。</td></tr>
<tr><td>OV · Intel Xe3 (iGPU)</td><td>INT8 + FP16 past</td><td class='num'>__OV8_FILE__</td><td class='num'>__OV8_GPU__</td><td class='num'>__OV8_MEAN__</td><td class='num'>__OV8_STEADY__</td><td class='num'>268.6</td><td class='num'>基准</td><td>之前有顾客自己带酒水，也没加收钱或者不让喝。</td></tr>
<tr><td><b>OV · Intel Xe3 (iGPU)</b></td><td><b>INT4 + FP16 lm_head/past</b></td><td class='num'><b>__OV4_FILE__</b></td><td class='num'><b>__OV4_GPU__</b></td><td class='num'><b>__OV4_MEAN__</b></td><td class='num'><b>__OV4_STEADY__</b></td><td class='num'><b>239.0</b></td><td class='num'><span class="ok">A/B 快 __AB_GAIN__%</span>（单次 +15.2% 系噪声）</td><td>之前有顾客自己带酒水，也没加收钱，或者不让喝。</td></tr>
</tbody></table>
<p class="subtitle" style="margin-top:12px">⚠️ OV 两行的块长是 <b>640 ms</b>（交付口径），CUDA 两行是 <b>320 ms</b>（audio.cpp 默认流式策略）——
跨运行时不比每块毫秒数，只看各自「量化前 → 量化后」的变化方向与幅度。
CUDA 的 RTF 口径为「音频内逐块耗时之和 ÷ 音频时长」（不含模型加载）。<br>
「模型文件」列 CUDA 为整个 gguf；OV 为 <b>decoder IR + reviewer encoder IR</b>（两次实测共用同一个 reviewer encoder，故只列差异部分 + 公共部分）；
INT8/INT4 的 decoder 目录内另各有一份 <b>未加载</b>的 encoder 副本（__OV8_ENC_COPY__ / __OV4_ENC_COPY__ MB），是磁盘冗余、不进内存。<br>
OV「每块均值」列为<b>单次新进程首发测量</b>（INT4 出现了 __OV4_MAX__ ms 的离群块，把均值抬高了；同一次测量内部逐块<b>中位</b>是 __OV8_MED__ vs __OV4_MED__ ms，基本持平）；
跨配置的可比结论以 <b>A/B×5 中位</b> 为准，见下文「OV INT4 根因分析」。</p>

<h2>CUDA 侧：Q8_0 vs Q4_K 逐块延迟（22 块 / 320 ms）</h2>
<div class="row">
<div class="chart">
<div class="chart-title">逐块总延迟对比</div>
<div class="chart-sub">蓝 = Q8_0 ｜ 绿 = Q4_K ｜ 红色虚线 = 320 ms 块预算</div>
<div id="chart-cuda" class="chart-box"></div>
</div>
<div class="chart">
<div class="chart-title">延迟构成（编码 + Decoder Prefill）</div>
<div class="chart-sub">Q4_K 主要省在 prefill；encoder 侧也因权重量化略有下降</div>
<div id="chart-cuda2" class="chart-box"></div>
</div>
</div>

<h2>OV 侧：INT8 vs INT4 延迟构成（A/B×5 中位，11 块 / 640 ms）</h2>
<div class="row">
<div class="chart">
<div class="chart-title">延迟构成对比（编码 / Prefill / 生成，中位耗时）</div>
<div class="chart-sub">A/B 口径下 INT4 三项全面不慢于 INT8；encoder 两边共用同一个 reviewer IR，其 +2.2% 差异即噪声本身</div>
<div id="chart-ov" class="chart-box"></div>
</div>
<div class="chart">
<div class="chart-title">延迟 vs 内存（OV iGPU）</div>
<div class="chart-sub">左：A/B 每块中位（越低越好）｜ 右：工作集稳态（越低越好）—— INT4 两项都占优，不采纳的原因是精度</div>
<div id="chart-ov2" class="chart-box"></div>
</div>
</div>

<h2>内存占用变化</h2>
<table><thead><tr>
<th>指标</th><th>CUDA Q8_0</th><th>CUDA Q4_K</th><th>CUDA Δ</th><th>OV INT8</th><th>OV INT4</th><th>OV Δ</th><th>口径说明</th>
</tr></thead><tbody>
<tr><td>模型文件（磁盘 MB）</td><td class='num'>__Q8_FILE__</td><td class='num'>__Q4_FILE__</td><td class='num'><span class="ok">__FILEGAIN_CUDA__%</span></td><td class='num'>__OV8_FILE__</td><td class='num'>__OV4_FILE__</td><td class='num'><span class="ok">__FILEGAIN_OV__%</span></td><td>CUDA=整个 gguf；OV=decoder IR + reviewer encoder IR（实际加载部分）</td></tr>
<tr><td>GPU 权重缓冲（MB）</td><td class='num'>__Q8_BUF__</td><td class='num'>__Q4_BUF__</td><td class='num'><span class="ok">-__BUFGAIN__%</span></td><td class='num'>—</td><td class='num'>—</td><td class='num'>—</td><td>CUDA <code>TIMING</code> 日志 buffer_mb（enc 333+dec 2022 / enc 183+dec 1350）</td></tr>
<tr><td>GPU 显存 · 稳态（MB）</td><td class='num'>__Q8_VRAM__</td><td class='num'>__Q4_VRAM__</td><td class='num'><span class="ok">__VRAMGAIN_CUDA__%</span></td><td class='num'>__OV8_GPU__</td><td class='num'>__OV4_GPU__</td><td class='num'><span class="ok">__GPUGAIN_OV__%</span></td><td>CUDA=RTX 5050 独立显存（Dedicated）；OV=iGPU UMA（Dedicated+Shared）—— <b>绝对值不可跨 GPU 比</b></td></tr>
<tr><td>GPU 显存 · 峰值（MB）</td><td class='num'>__Q8_VRAM_PK__</td><td class='num'>__Q4_VRAM_PK__</td><td class='num'><span class="ok">__VRAMGAIN_CUDA_PK__%</span></td><td class='num'>__OV8_GPU_PK__</td><td class='num'>__OV4_GPU_PK__</td><td class='num'><span class="ok">__GPUGAIN_OV_PK__%</span></td><td>含模型加载 / 编译瞬态</td></tr>
<tr><td>进程工作集 · 稳态（MB）</td><td class='num'>__Q8_WS__</td><td class='num'>__Q4_WS__</td><td class='num'><span class="ok">≈0%</span></td><td class='num'>__OV8_WS__</td><td class='num'>__OV4_WS__</td><td class='num'><span class="ok">__WSGAIN_OV__%</span></td><td>CUDA 权重在显存里，主机侧只剩 CUDA context，故量化不改变它</td></tr>
<tr><td>进程工作集 · 峰值（MB）</td><td class='num'>__Q8_WS_PK__</td><td class='num'>__Q4_WS_PK__</td><td class='num'><span class="ok">__WSGAIN_CUDA_PK__%</span></td><td class='num'>__OV8_WS_PK__</td><td class='num'>__OV4_WS_PK__</td><td class='num'><span class="ok">__WSGAIN_OV_PK__%</span></td><td>CUDA 峰值含 gguf 文件读入系统内存的瞬态（读完即释放）</td></tr>
<tr><td>进程私有 USS · 稳态（MB）</td><td class='num'>__Q8_USS__</td><td class='num'>__Q4_USS__</td><td class='num'><span class="ok">≈0%</span></td><td class='num'>__OV8_USS__</td><td class='num'>__OV4_USS__</td><td class='num'><span class="ok">__USSGAIN_OV__%</span></td><td>进程独占页（psutil USS），与工作集同向</td></tr>
</tbody></table>
<div class="callout">
<b>怎么读这张表：</b>CUDA 与 OV 跑在不同 GPU 上（独显 vs 核显），显存绝对值不可比，只看各自「量化前 → 量化后」的变化。
CUDA 侧 4-bit 的收益全额兑现在显存（__VRAMGAIN_CUDA__% 稳态 / 权重缓冲 -__BUFGAIN__%），主机内存几乎不变（权重本来就在显存里）；
OV 侧 4-bit 同时省显存（__GPUGAIN_OV__%）和工作集（__WSGAIN_OV__%），因为 UMA 架构下 iGPU 分配直接占用系统内存。
</div>
<div class="chart">
<div class="chart-title">四配置内存对比（稳态，MB）</div>
<div class="chart-sub">蓝 = GPU 侧显存 ｜ 绿 = 进程工作集 ｜ 左两柱 CUDA（RTX 5050 独显），右两柱 OV（Xe3 核显）</div>
<div id="chart-mem" class="chart-box"></div>
</div>

<h2>为什么 OV INT4 只小 ~10%：IR 构成拆解（C-055）</h2>
<div class="callout warnbox">
<b>问题：</b>CUDA 侧 Q4_K 比 Q8_0 小 35%，OV 侧 INT4 却只比 INT8 小 ~10%（模型文件 -9.1%、显存稳态 -11.1%）。
把 decoder IR 的每个 Const 按<b>精度</b>和<b>语义</b>拆开累加（<code>c055_ir_breakdown.py</code>，
合计与实际 .bin 字节数分毫不差），答案很清楚：<b>INT4 的 IR 里 43% 的字节仍然是 FP16</b>。
</div>

<h3>直接原因：lm_head 没被量化，且权重共享（tie）被打破</h3>
<p class="subtitle" style="margin-top:0">
这个模型的输入 embedding 与输出投影本是<b>同一份矩阵</b>（weight tying，词表 151936 × 2048）：
</p>
<table><thead><tr><th>配置</th><th>词表矩阵的形态</th><th>体积 (MiB)</th><th>说明</th></tr></thead><tbody>
<tr><td>FP16 基线</td><td>1 × f16</td><td class='num'>__IRF_VOCAB__</td><td>embed_tokens 一份，lm_head 复用它</td></tr>
<tr><td>INT8（交付）</td><td>1 × u8</td><td class='num'>__IR8_VOCAB__</td><td>仍是同一份常量——lm_head MatMul 的权重输入直接来自 <code>embed_tokens.weight/fq_weights_0/Convert</code></td></tr>
<tr><td><b>INT4</b></td><td><b>1 × i4 + 1 × f16</b></td><td class='num'><b>__IR4_VOCAB__</b></td><td>embed_tokens 量化为 i4（148 MiB），lm_head 却保留了一份<b>完整 FP16</b>（<code>lm_head.weight_compressed</code>，__IR4_LMHEAD__ MiB）——tie 断裂，矩阵被复制成两份</td></tr>
</tbody></table>
<p class="subtitle" style="margin-top:12px">
用 OV API 追 <code>lm_head</code> MatMul 的权重输入可以实锤：
INT8 指向 <code>embed_tokens.weight/fq_weights_0</code>（共享），INT4 指向独立的
<code>self.model.thinker.lm_head.weight_compressed</code> Const（<code>element_type="f16" shape="151936,2048" size="622329856"</code>）。
名字里的 "compressed" 名不副实——它在 IR 里就是未压缩的 FP16。<b>光这一块就占了 INT4 文件的 41%。</b>
</p>

<h3>完整构成：真正 4-bit 化的只有 82% 的权重</h3>
<div class="chart">
<div class="chart-title">decoder IR 构成（MiB，按语义 × 精度堆叠）</div>
<div class="chart-sub">深蓝 = 28 层 transformer ｜ 绿 = 词表矩阵（已量化部分）｜ 红 = 词表矩阵的 FP16 残留（仅 INT4 有）｜ 灰 = 其他小常量</div>
<div id="chart-ir" class="chart-box"></div>
</div>
<table><thead><tr>
<th>构成</th><th>FP16 基线</th><th>INT8（交付）</th><th>INT4</th><th>INT4 相对 INT8</th>
</tr></thead><tbody>
<tr><td>28 层 transformer 权重</td><td class='num'>__IRF_LAYERS__</td><td class='num'>__IR8_LAYERS__（-50%）</td><td class='num'>__IR4_LAYERS__（-74%）</td><td class='num'><span class="ok">-49%</span></td></tr>
<tr><td>词表矩阵（embed + lm_head）</td><td class='num'>__IRF_VOCAB__</td><td class='num'>__IR8_VOCAB__（-50%）</td><td class='num'>__IR4_VOCAB__（<b>+25%</b>）</td><td class='num'><span class="bad">+150%</span></td></tr>
<tr><td>其他小常量（mask / inv_freq / scale）</td><td class='num'>≈0</td><td class='num'>≈2</td><td class='num'>≈6</td><td class='num'>—</td></tr>
<tr><td><b>decoder IR 合计</b></td><td class='num'><b>__IRF_TOTAL__</b></td><td class='num'><b>__IR8_TOTAL__</b></td><td class='num'><b>__IR4_TOTAL__</b></td><td class='num'><b>-12.4%</b></td></tr>
</tbody></table>
<p class="subtitle" style="margin-top:12px">
两层稀释叠加在一起：<br>
① <b>覆盖不全</b>：词表矩阵占 FP16 基线的 18%（594/3282），INT4 对它几乎没压缩（还倒涨 25%）；
真正被压掉 74% 的 transformer 层占 82%，加权后整体只降 12.4%。<br>
② <b>共用件未量化</b>：两个 OV 配置还共用同一个 <b>FP16 reviewer encoder（__ENC_MIB__ MiB，完全没量化）</b>，
再稀释一层——「实际加载总量」从 __TOT8__ → __TOT4__ MiB，只剩 <b>-9.1%</b>。<br>
③ <b>量化格式开销</b>：i4 按 group=128 打包（形状 [151936,16,128]），每组要带 f16 scale/zero-point，
对 128 个元素是 64B 数据 + 4B 参数 ≈ 6% 的额外开销——量级很小，不是主因。
</p>

<h3>如果 lm_head 也进 4-bit，能省多少？</h3>
<p class="subtitle" style="margin-top:0">
C-056 真的导出了一个这样的变体（<code>ov-int4-lmhead-past</code>：不 clone、不 ignored_scope，
embed 与 lm_head 共用同一份 i4 常量，tie 保留），实测 decoder IR = <b>__L4_SIZE__ MiB</b>——
比 __IR4_WHATIF__ MiB 的朴素估算还小（tie 保留意味着不必为 lm_head 再付一份 148 MiB），
相对 INT8 是 <b>__L4_VS8__%</b>、相对现有 int4lmfp16 是 <b>__L4_VS4__%</b>，
已把 FP16 基线压掉 74%。<b>换句话说，OV INT4「只小 10%」不是 4-bit 本身的极限，
而是导出配置的选择（lm_head 保 FP16 + tie 断裂 + encoder 未量化）。</b>
精度和性能代价见下一节（C-056 实测：几乎为零）。
</p>

<h2>lm_head 为什么不量化？量化它会掉多少精度？（C-056 实测）</h2>
<div class="callout warnbox">
<b>问题：</b>既然 lm_head 的 FP16 让「INT4 省内存」基本落空，当初为什么把它留下？
如果把它也量化成 INT4，精度会掉多少？—— 两个都实测了。
</div>

<h3>为什么没量化：一个被事后证伪的「保险」</h3>
<div class="callout warnbox"><b>构建说明（C-058③）</b>：本报告的 INT4 头条已切换为 <code>ov-int4-lmhead-past</code>（decoder 846 MiB，lm_head 也进 INT4 且保持 tie）。<code>ov-int4-lmfp16-past</code>（1440 MiB，lm_head 保留 FP16）是<b>次优构建，仅作对照</b>。fresh-process 实测显示次优构建的显存差 / IR 体积差 = 1.72（异常），因其 594 MiB 的 FP16 lm_head 需额外运行时缓冲；全量构建该比值为 1.07（正常）。</div>
<p class="subtitle" style="margin-top:0">
① <b>C-043 当时的诊断</b>：10-13 10:45 的记录写着「lm_head (tied with embed_tokens) 量化误差是
<b>第二个根因</b>」，解决方案就是「保留 lm_head 为 FP16」（C-043#1 用于 INT8，C-043#3 备选 2 用于 INT4）。
交付的 <code>ov-int4-lmfp16-past</code> 由 <code>c043_export_int4.py</code> 产出：
<code>ignored_scope=[lm_head MatMul]</code> + <code>backup_mode=NONE</code>（比 NNCF 默认还保守一档——
NNCF 在 INT4_SYM 下默认就会把最后一个 MatMul backup 成 INT8_ASYM）。<br>
② <b>tie 断裂是这个选择的机械副作用</b>：脚本必须先 <code>clone_tied_weight()</code> 把共享常量复制一份，
才能做到「embed 进 i4、lm_head 留 FP16」——否则共用常量会被一起量化。<br>
③ <b>事后看这个诊断是错的</b>：C-043#1（INT8 + FP16 lm_head）被验证<b>失败</b>——
C-044 teacher-forcing 里 <code>int8lmfp16</code> 的 top-1 = __I8LM_TOP1__%，反而比纯 int8 的 __I8_TOP1__% 还低；
真正的根因是 <code>max_new_tokens</code> 固定 32（C-047 修复）。C-044/C-053 也显示 INT4 的精度损失
主要来自 28 层 + embed，不在输出投影。<b>也就是说：这份「保险」几乎没有赔过，却让 INT4 变体肥了 594 MiB。</b>
</p>

<h3>量化它会掉多少精度：实测（与 C-044 同段同参数，629 步 teacher forcing）</h3>
<table><thead><tr>
<th>decoder</th><th>decoder IR (MiB)</th><th>top-1 一致率</th><th>EOS 一致率</th><th>端到端 token 替换率*</th><th>每块耗时（640 ms，A/B×3 中位）</th>
</tr></thead><tbody>
<tr><td>INT8（交付）</td><td class='num'>1643</td><td class='num'>__I8_TOP1__%</td><td class='num'>63.4%</td><td class='num'>—</td><td class='num'>—</td></tr>
<tr><td>INT4 + FP16 lm_head（<b>次优构建，仅作对照</b>）</td><td class='num'>1440</td><td class='num'>__L4F_TOP1__%</td><td class='num'>41.5%</td><td class='num'>11.27%</td><td class='num'>348.1 ms</td></tr>
<tr><td><b>INT4 全量（what-if）</b></td><td class='num'><b>__L4_SIZE__</b></td><td class='num'><b>__L4_TOP1__%</b></td><td class='num'><b>__L4_EOS__%</b></td><td class='num'><b>__L4_SUB__%</b></td><td class='num'><b>337.8 ms（__L4_PERF__%）</b></td></tr>
</tbody></table>
<p class="subtitle" style="margin-top:12px">
*端到端 token 替换率 = 3 段流式输出与 FP16 输出做 token 级 diff 的替换数 / FP16 token 数（213 个）。
lm_head 也 INT4 后：top-1 __L4_TOP1_D__ pp（<b>不降反微升</b>）、EOS __L4_EOS_D__ pp、
端到端替换 __L4_SUB_D__ pp（213 个 token 里多 2 个，噪声级）、flush __L4_FLUSH__%。<br>
top-1 微升的一个合理解释：现状下 embed 查表走 i4 反量化、lm_head 走 FP16，两条路径的权重
<b>不一致</b>；tie 保留后两边用同一份反量化矩阵，mismatch 消失。
</p>

<div class="chart">
<div class="chart-title">「免费的午餐」：lm_head 也 INT4 —— 体积 -41%，精度无损</div>
<div class="chart-sub">左：decoder IR 体积（MiB，越低越好）｜ 右：teacher-forcing top-1 一致率（%，越高越好）</div>
<div id="chart-lmh" class="chart-box"></div>
</div>

<div class="callout">
<b>结论：</b>① 当初不量化 lm_head 是出于一个被证伪的诊断（「lm_head 量化误差是根因」），
事后证明真正根因是 <code>max_new_tokens</code>；② 实测把 lm_head 也量化到 INT4，
<b>精度没有可测量的损失</b>（top-1 __L4_TOP1_D__ pp、端到端 +2/213 token），
体积再省 __L4_VS4_ABS__%（decoder 1440 → __L4_SIZE__ MiB，相对 INT8 __L4_VS8__%），还快 __L4_PERF_ABS__%；<br>
③ <b>但交付配置仍不变</b>（INT8）——因为 INT4 相对 INT8 的 +1.08 pp WER 来自 28 层 + embed，
量化 lm_head 既不能挽回、也不会加重它。这条结论的价值在<b>未来</b>：若再导 4-bit 变体，
应全量量化 + 保持 tie（可再省 41%）；若想真正救回 INT4 的精度，方向在层间混合精度或 encoder 端，
而不是给 lm_head 上 FP16。
</div>

<h2>OV INT4 根因分析（C-054）</h2>
<div class="callout warnbox">
<b>问题重述：</b>C-053 单次测量显示 OV INT4 比 INT8 慢 15.2%（每块 360.7→415.4 ms）、prefill +51%（102.2→154.8 ms）。
这个结论<b>不成立</b> —— 它是测量噪声。下面用四层证据给出真实图景。
</div>

<h3>证据 1 · 静态 IR 结构：INT4 把反量化写进了图</h3>
<p class="subtitle" style="margin-top:0">
INT8 路径：<code>u8</code> Const + 198 个 <code>Subtract</code>（zero-point 校正）→ <code>MatMul</code>；
INT4 路径：197 个 <code>i4</code> Const → <code>Convert(i4→f16)</code> → <code>MatMul</code>，反量化成为图里每拍都要执行的显式 op，
并额外多出 <b>+197 Reshape / +55 Concat / +55 Broadcast / +200 Convert</b>（合计约 500 个 op）；decoder IR 体积 1643→1440 MB（-12.4%）。
单看这张图，「INT4 图更大、op 更多，应该更慢」是合理推测 —— 但这只是推测。
</p>

<h3>证据 2 · 运行时 primitive：计算主体完全一致</h3>
<p class="subtitle" style="margin-top:0">
编译后取 <code>get_runtime_model()</code> 的 ExecutionNode rt_info：
两边 <b>FullyConnected 均 141 个、Gemm 均 1 个</b>（计算主体一模一样）；
INT4 多出一个 <code>gather_ref__i4</code>（i4 精度的 reference 实现，未走 XMX 快速路径）；
INT8 有 113 个 <code>dynamic_quantize_gpu_opt__f16</code>（INT8 XMX 路径），INT4 为 112 个。
即 INT4 的额外成本集中在「反量化 / 重排」这类访存 op 上，不在计算量上。
</p>

<h3>证据 3 · 受控扫描：开销不随尺寸爆炸，权重收益占上风</h3>
<p class="subtitle" style="margin-top:0">
对 standalone decoder IR 做双维扫描（中位耗时，ms）：__SCAN_TXT__。
若「反量化开销」是主要矛盾，比值应随序列变长而恶化；实测<b>全程 ≤1×、多数点 &lt;1×</b>，说明权重减半带来的访存收益占上风。
</p>
<table><thead><tr><th>Tt（文本前缀）</th><th>Ta（音频帧）</th><th>INT8 (ms)</th><th>INT4 (ms)</th><th>INT4/INT8</th></tr></thead>
<tbody>__SCAN_TT_TBL__</tbody></table>
<p class="subtitle" style="margin-top:8px">同表，扫 Ta（Tt=32，模拟长前缀 prefill）：</p>
<table><thead><tr><th>Tt（文本前缀）</th><th>Ta（音频帧）</th><th>INT8 (ms)</th><th>INT4 (ms)</th><th>INT4/INT8</th></tr></thead>
<tbody>__SCAN_TA_TBL__</tbody></table>

<h3>证据 4 · 严格 A/B：INT4 更快（-__AB_GAIN__%）</h3>
<p class="subtitle" style="margin-top:0">
同一进程内 INT8/INT4 <b>交替</b>跑 5 轮（每轮 640 ms × 11 块），按中位数汇总，
消除单发抖动与时间漂移：
</p>
<table><thead><tr><th>配置</th><th>每块 total (ms)</th><th>编码 (ms)</th><th>Prefill (ms)</th><th>生成 (ms)</th><th>Flush (ms)</th><th>RTF@640</th></tr></thead><tbody>
<tr><td>INT8</td><td class='num'>__AB8_TOTAL__</td><td class='num'>__AB8_ENC__</td><td class='num'>__AB8_PRE__</td><td class='num'>__AB8_DEC__</td><td class='num'>__AB8_FLUSH__</td><td class='num'>__AB8_RTF__</td></tr>
<tr><td><b>INT4</b></td><td class='num'><b>__AB4_TOTAL__</b></td><td class='num'>__AB4_ENC__</td><td class='num'><b>__AB4_PRE__</b></td><td class='num'><b>__AB4_DEC__</b></td><td class='num'><b>__AB4_FLUSH__</b></td><td class='num'><b>__AB4_RTF__</b></td></tr>
</tbody></table>
<p class="subtitle" style="margin-top:8px">
INT4 相对 INT8：total <b>快 __AB_GAIN__%</b>、prefill 快 __AB_GAIN_PRE__%、decode 快 __AB_GAIN_DEC__%、flush 快 10.5%；
encode +2.2% 是噪声（两边共用同一个 reviewer encoder IR，这本该是 0）。
</p>

<h3>那「+51% prefill」是哪来的？—— 三类污染</h3>
<p class="subtitle" style="margin-top:0">
① <b>单次测量的离群块</b>：INT4 那一发出现了 <b>__OV4_MAX__ ms</b> 的离群块（INT8 最大 __OV8_MAX__ ms）。
即使在同一发测量内部，逐块<b>中位</b>也是 __OV8_MED__ vs __OV4_MED__ ms —— 基本持平，是均值被离群值带偏。<br>
② <b>61-min 长跑互相污染</b>：INT4 的 61-min 跑测与 CUDA Q4 的 61-min 跑测<b>并发</b>执行，iGPU/dGPU 与主机互相抢资源，
该次 RTF 0.682 不能用于任何性能结论。<br>
③ <b>iGPU 共享本身的高方差</b>：核显与桌面合成器、其他进程共享，单发测量的块间方差可达 ±30%，
任何「只跑一次」的跨配置对比在这台机器上都不足以下结论。
</p>

<h3>INT4 真实存在的两项成本</h3>
<p class="subtitle" style="margin-top:0">
① <b>编译时间 __OV8_COMPILE__ → __OV4_COMPILE__ s（+__COMPILE_UP__%）</b>：图里多出约 500 个 op，编译期常量反量化更贵。
对「起会话 → 说几句 → 结束」的短会话是实打实的启动代价；长流式会话可忽略。<br>
② <b>WER __WERD_OV__ pp</b>（61-min，真实退化）：插入 __I_OV_INT8__→__I_OV_INT4__、替换 __S_OV_INT8__→__S_OV_INT4__，
与 C-044 teacher-forcing 的 top-1 84.3% vs 94.1% 互相印证。<b>这才是 OV INT4 被否掉的真正原因。</b>
</p>

<h2>精度对比（61-min 英文会议集，WER）</h2>
<table><thead><tr>
<th>运行时</th><th>权重</th><th>WER</th><th>Δ vs 同运行时 8-bit</th><th>S</th><th>D</th><th>I</th><th>参考</th>
</tr></thead><tbody>
<tr><td>CUDA · RTX 5050</td><td>GGUF Q8_0</td><td class='num'><b>__WER_CUDA_Q8__%</b></td><td class='num'>—</td><td class='num'>__S_CUDA_Q8__</td><td class='num'>__D_CUDA_Q8__</td><td class='num'>__I_CUDA_Q8__</td><td>MiniMax asr-1.0（11066 词）</td></tr>
<tr><td><b>CUDA · RTX 5050</b></td><td><b>GGUF Q4_K</b></td><td class='num'><b>__WER_CUDA_Q4__%</b></td><td class='num'>__WERD_CUDA__ pp</td><td class='num'>__S_CUDA_Q4__</td><td class='num'>__D_CUDA_Q4__</td><td class='num'>__I_CUDA_Q4__</td><td>同上，同归一化口径</td></tr>
<tr><td>OV · Intel Xe3</td><td>INT8 + FP16 past（交付）</td><td class='num'><b>__WER_OV_INT8__%</b></td><td class='num'>—</td><td class='num'>__S_OV_INT8__</td><td class='num'>__D_OV_INT8__</td><td class='num'>__I_OV_INT8__</td><td>同上</td></tr>
<tr><td><b>OV · Intel Xe3</b></td><td><b>INT4 + FP16 lm_head/past</b></td><td class='num'><b>__WER_OV_INT4__%</b></td><td class='num'>__WERD_OV__ pp</td><td class='num'>__S_OV_INT4__</td><td class='num'>__D_OV_INT4__</td><td class='num'>__I_OV_INT4__</td><td>同上</td></tr>
</tbody></table>
<p class="subtitle" style="margin-top:12px">口径：<code>c045_wer.py</code>（小写、去标点、<b>保留数字</b>、按空白切词），
四份 transcript 用同一脚本同一参考计算，横向可比。CUDA Q8 的 7.62% 与本机历史记录一致；
若改用「去数字」口径会再低约 0.1 pp，不影响结论方向。</p>

<h2>结论与建议</h2>
<div class="headline">
<span class="tag tag-green">交付配置保持不变</span>
CUDA 侧继续 <code>r2t2-q8_0.gguf</code>（RTX 5050 上每块 55–65 ms，余量充足）；
OV 侧继续 <code>ov-int8-past</code> + 640 ms 块。<br>
<span class="tag tag-blue">如果目标是省内存 / 多路并发</span>
CUDA 侧 Q4_K 是唯一划算的：显存稳态 __VRAMGAIN_CUDA__%、权重缓冲 -__BUFGAIN__%、WER 仅 __WERD_CUDA__ pp（噪声内）、速度还快 __QGAIN_S__% ——
适合<b>需要同卡并发多路流式</b>的场景，切过去没有已知代价。<br>
<span class="tag tag-amber">OV INT4：性能与内存双赢，但精度否掉</span>
A/B 中位显示它在 iGPU 上更快（-__AB_GAIN__%）也更省（工作集 __WSGAIN_OV__%、显存 __GPUGAIN_OV__%），
但 WER __WERD_OV__ pp 是真实退化。<b>唯一可考虑的场景</b>：离线批处理 + 对精度不敏感 + 能接受 +__COMPILE_UP__% 的编译启动开销。<br>
<span class="tag tag-red">不要再走「4-bit 换精度」的路线</span>
与 C-047 的根因结论（<code>max_new_tokens</code> 固定 32）互相印证：这条模型的精度问题从来不在量化位宽。<br>
<span class="tag tag-blue">两条可执行的后见之明（C-055/C-056）</span>
① <b>若确需 4-bit</b>：应<b>全量量化 + 保持 tie</b>——C-056 实测把 lm_head 也量化到 INT4 精度无可测损失
（top-1 __L4_TOP1_D__ pp），decoder 再省 __L4_VS4_ABS__%（1440 → __L4_SIZE__ MiB），还快 __L4_PERF_ABS__%；
当初给 lm_head 上 FP16 是「买错的保险」。② <b>若想再省内存</b>：优先 <b>encoder 端</b>
（reviewer encoder 606 MiB 两边共用、未量化，量化它影响全部 226 段）而非继续动 decoder。
</div>

<div class='footer'>
CUDA 侧：<code>reports/c053_quant/cuda/</code>（<code>chunks_{q8,q4}.json</code> + <code>run_{q8,q4}.log</code>，解析脚本 <code>parse_audiocpp_stream.py</code>）；
Q4_K 由 <code>audiocpp_gguf --type q4_k</code> 从 <code>models/hf/model.safetensors</code> 量化生成（脚本 <code>cuda_stream_q4.py</code> 跑 61-min）｜
CUDA 内存：<code>reports/c054_cuda_mem.json</code>（<code>c054_cuda_mem.py</code>，子进程 + PDH，NVIDIA LUID 0x000133E1）｜
OV 侧：<code>reports/c052_ov_vs_cuda/</code>（INT8）、<code>reports/c053_int4/</code>（INT4）、<code>reports/c053_61min_int4/</code>（WER）｜
OV A/B：<code>reports/c054_ab_medians.json</code>（<code>c054_ab.py</code>，5 次交替取中位）｜ 扫描：<code>reports/c054_e2_scan.json</code>（<code>c054_e2b_scan.py</code>）｜
WER 口径 <code>c045_wer.py</code>
</div>
</div>
<script>
const D = __DATA__;
const AX = {axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}, splitLine:{lineStyle:{color:'#2a2e38'}}};
const TT = {trigger:'axis', backgroundColor:'#232730', borderColor:'#2a2e38', textStyle:{color:'#fff'}};
const LG = {textStyle:{color:'#cbd0d8'}, top:0, right:0};
const C_BLUE = '#4f8cff', C_GREEN = '#4ade80', C_PURPLE = '#a78bfa',
      C_CYAN = '#22d3ee', C_ORANGE = '#fb923c', C_AMBER = '#fbbf24',
      C_RED = '#f87171';

// ── 1. CUDA 逐块总延迟 ─────────────────────────────────
(function(){
  const a = D.q8.chunks, b = D.q4.chunks;
  echarts.init(document.getElementById('chart-cuda')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:60, right:20, top:45, bottom:30}, tooltip:TT,
    xAxis:{type:'category', data:a.map(c=>c.chunk), name:'Chunk',
      nameTextStyle:{color:'#8a8f99'},
      axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'ms',
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'Q8_0', type:'bar', barWidth:'35%',
       data:a.map(c=>c.total), itemStyle:{color:C_BLUE}},
      {name:'Q4_K', type:'bar', barWidth:'35%',
       data:b.map(c=>c.total), itemStyle:{color:C_GREEN}},
      {name:'320 ms 块预算', type:'line', data:a.map(()=>320),
       symbol:'none', lineStyle:{color:C_RED, type:'dashed', width:1.5}}
    ]
  });
})();

// ── 2. CUDA 延迟构成 ───────────────────────────────────
(function(){
  const a = D.q8.chunks, b = D.q4.chunks;
  echarts.init(document.getElementById('chart-cuda2')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:60, right:20, top:45, bottom:30}, tooltip:TT,
    xAxis:{type:'category', data:a.map(c=>c.chunk), name:'Chunk',
      nameTextStyle:{color:'#8a8f99'},
      axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'ms',
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'Q8 编码', type:'bar', stack:'q8', data:a.map(c=>c.enc),
       itemStyle:{color:C_BLUE}},
      {name:'Q8 Prefill', type:'bar', stack:'q8', data:a.map(c=>c.prefill),
       itemStyle:{color:C_PURPLE}},
      {name:'Q4 编码', type:'bar', stack:'q4', data:b.map(c=>c.enc),
       itemStyle:{color:C_ORANGE}},
      {name:'Q4 Prefill', type:'bar', stack:'q4', data:b.map(c=>c.prefill),
       itemStyle:{color:C_GREEN}}
    ]
  });
})();

// ── 3. OV 构成对比（A/B×5 中位）────────────────────────
(function(){
  const cats = ['音频编码', 'Decoder Prefill', '逐 token 生成'];
  echarts.init(document.getElementById('chart-ov')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:60, right:20, top:45, bottom:30}, tooltip:TT,
    xAxis:{type:'category', data:cats,
      axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'ms',
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'INT8（交付）', type:'bar', barWidth:'32%',
       data:[__AB8_ENC__, __AB8_PRE__, __AB8_DEC__],
       itemStyle:{color:C_BLUE},
       label:{show:true, position:'top', color:'#fff'}},
      {name:'INT4', type:'bar', barWidth:'32%',
       data:[__AB4_ENC__, __AB4_PRE__, __AB4_DEC__],
       itemStyle:{color:C_GREEN},
       label:{show:true, position:'top', color:'#fff'}}
    ]
  });
})();

// ── 4. OV 延迟 vs 内存 ─────────────────────────────────
(function(){
  echarts.init(document.getElementById('chart-ov2')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, tooltip:TT,
    grid:[{left:60, right:'55%', top:45, bottom:30},
          {left:'58%', right:20, top:45, bottom:30}],
    xAxis:[
      {gridIndex:0, type:'category', data:['INT8','INT4'],
       axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}},
      {gridIndex:1, type:'category', data:['INT8','INT4'],
       axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}}
    ],
    yAxis:[
      Object.assign({gridIndex:0, type:'value', name:'每块 ms',
        nameTextStyle:{color:'#8a8f99'}}, AX),
      Object.assign({gridIndex:1, type:'value', name:'工作集 MB',
        nameTextStyle:{color:'#8a8f99'}}, AX)
    ],
    series:[
      {name:'每块中位（A/B）', type:'bar', xAxisIndex:0, yAxisIndex:0,
       barWidth:'45%',
       data:[{value:__AB8_TOTAL__, itemStyle:{color:C_BLUE}},
             {value:__AB4_TOTAL__, itemStyle:{color:C_GREEN}}],
       label:{show:true, position:'top', color:'#fff', formatter:'{c} ms'}},
      {name:'工作集稳态', type:'bar', xAxisIndex:1, yAxisIndex:1,
       barWidth:'45%',
       data:[{value:__OV8_WS__, itemStyle:{color:C_BLUE}},
             {value:__OV4_WS__, itemStyle:{color:C_GREEN}}],
       label:{show:true, position:'top', color:'#fff', formatter:'{c} MB'}}
    ]
  });
})();

// ── 5. 四配置内存对比（稳态）───────────────────────────
(function(){
  const m = D.mem;
  echarts.init(document.getElementById('chart-mem')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:70, right:20, top:45, bottom:60}, tooltip:TT,
    xAxis:{type:'category', data:m.cats,
      axisLabel:{color:'#8a8f99', interval:0}, axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'MB',
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'GPU 侧显存（稳态）', type:'bar', barWidth:'30%',
       data:m.vram.map(v=>Math.round(v)),
       itemStyle:{color:C_BLUE},
       label:{show:true, position:'top', color:'#fff'}},
      {name:'进程工作集（稳态）', type:'bar', barWidth:'30%',
       data:m.ws.map(v=>Math.round(v)),
       itemStyle:{color:C_GREEN},
       label:{show:true, position:'top', color:'#fff'}}
    ]
  });
})();

// ── 6. IR 构成堆叠图 ──────────────────────────────────
(function(){
  const r = D.ir;
  echarts.init(document.getElementById('chart-ir')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:70, right:20, top:45, bottom:40}, tooltip:TT,
    xAxis:{type:'category', data:r.cats,
      axisLabel:{color:'#8a8f99', interval:0}, axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'MiB',
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'28 层 transformer', type:'bar', stack:'ir', barWidth:'42%',
       data:r.layers.map(v=>Math.round(v)), itemStyle:{color:'#1e3a5f'},
       label:{show:true, position:'inside', color:'#cbd0d8'}},
      {name:'词表矩阵（已量化）', type:'bar', stack:'ir', barWidth:'42%',
       data:r.vocab_q.map(v=>Math.round(v)), itemStyle:{color:'#1e3a2e'},
       label:{show:true, position:'inside', color:'#cbd0d8'}},
      {name:'词表矩阵（FP16 残留）', type:'bar', stack:'ir', barWidth:'42%',
       data:r.vocab_f16.map(v=>Math.round(v)), itemStyle:{color:'#5a1e1e'},
       label:{show:true, position:'inside', color:'#f8b4b4'}},
      {name:'其他小常量', type:'bar', stack:'ir', barWidth:'42%',
       data:r.other.map(v=>Math.round(v)), itemStyle:{color:'#3a3f4a'},
       label:{show:true, position:'inside', color:'#8a8f99'}}
    ]
  });
})();

// ── 7. lm_head 也 INT4：体积 vs 精度 ───────────────────
(function(){
  const m = D.lmh;
  echarts.init(document.getElementById('chart-lmh')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, tooltip:TT,
    grid:[{left:70, right:'56%', top:45, bottom:60},
          {left:'60%', right:20, top:45, bottom:60}],
    xAxis:[
      {gridIndex:0, type:'category', data:m.cats, interval:0,
       axisLabel:{color:'#8a8f99', fontSize:10, rotate:20},
       axisLine:{lineStyle:{color:'#2a2e38'}}},
      {gridIndex:1, type:'category', data:m.cats, interval:0,
       axisLabel:{color:'#8a8f99', fontSize:10, rotate:20},
       axisLine:{lineStyle:{color:'#2a2e38'}}}
    ],
    yAxis:[
      Object.assign({gridIndex:0, type:'value', name:'IR MiB',
        nameTextStyle:{color:'#8a8f99'}, min:0}, AX),
      Object.assign({gridIndex:1, type:'value', name:'top-1 %',
        nameTextStyle:{color:'#8a8f99'}, min:80, max:100}, AX)
    ],
    series:[
      {name:'decoder IR（MiB）', type:'bar', xAxisIndex:0, yAxisIndex:0,
       barWidth:'45%',
       data:[{value:Math.round(m.size[0]), itemStyle:{color:C_BLUE}},
             {value:Math.round(m.size[1]), itemStyle:{color:C_ORANGE}},
             {value:Math.round(m.size[2]), itemStyle:{color:C_GREEN}}],
       label:{show:true, position:'top', color:'#fff', formatter:'{c}'}},
      {name:'top-1 一致率', type:'line', xAxisIndex:1, yAxisIndex:1,
       symbolSize:9,
       data:[{value:+m.top1[0].toFixed(2), itemStyle:{color:C_BLUE}},
             {value:+m.top1[1].toFixed(2), itemStyle:{color:C_ORANGE}},
             {value:+m.top1[2].toFixed(2), itemStyle:{color:C_GREEN}}],
       label:{show:true, position:'top', color:'#fff', formatter:'{c}%'},
       lineStyle:{color:'#8a8f99', width:1.5}}
    ]
  });
})();

window.addEventListener('resize', function(){
  document.querySelectorAll('.chart-box').forEach(function(el){
    var c = echarts.getInstanceByDom(el); if (c) c.resize();
  });
});
</script>
</body>
</html>
"""


if __name__ == '__main__':
    main()
