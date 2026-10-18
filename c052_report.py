"""c052_report.py — 生成 OpenVINO vs CUDA 对比报告（HTML / ECharts / 深色主题）

数据来自 `c052_ov_vs_cuda.py` 的产物（`reports/c052_ov_vs_cuda/{c320,c640}/`）。
CUDA 侧引用 `C:\\Users\\Trekker-PTL\\confucius4-r2t2\\stream_metrics.csv` 与
该目录下 `stream_report.html` 的分块明细表。

版式沿用 CUDA 版报告，便于两版并排阅读。

用法：
    .venv/Scripts/python.exe c052_report.py
    .venv/Scripts/python.exe c052_report.py --out reports/OV_VS_CUDA.html
"""
import os
import csv
import json
import argparse
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
MEAS_DIR = os.path.join(ROOT, 'reports', 'c052_ov_vs_cuda')
CUDA_CSV = r'C:\Users\Trekker-PTL\confucius4-r2t2\stream_metrics.csv'

# ── CUDA 侧：来自 confucius4-r2t2/stream_report.html 的分块明细表（逐字抄录）
#    (chunk, 编码 ms, Decoder Prefill ms, 合计 ms, 增量文本)
CUDA_CHUNKS = [
    (1, 167.6, 96.9, 264.5, '之前'),
    (2, 16.0, 25.6, 41.6, '之前有'),
    (3, 20.5, 25.0, 45.5, '之前有顾客'),
    (4, 18.7, 26.3, 45.0, '之前有顾客自己带'),
    (5, 12.6, 26.8, 39.4, '之前有顾客自己带酒'),
    (6, 6.9, 31.0, 37.9, '之前有顾客自己带酒水'),
    (7, 23.1, 29.2, 52.3, '之前有顾客自己带酒水'),
    (8, 16.3, 32.2, 48.5, '之前有顾客自己带酒水'),
    (9, 13.0, 33.1, 46.1, '之前有顾客自己带酒水'),
    (10, 7.7, 30.2, 37.9, '之前有顾客自己带酒水也没'),
    (11, 24.6, 39.9, 64.5, '之前有顾客自己带酒水也没加收'),
    (12, 13.0, 37.2, 50.2, '之前有顾客自己带酒水也没加收钱'),
    (13, 30.1, 34.1, 64.2, '之前有顾客自己带酒水也没加收钱'),
    (14, 25.1, 35.6, 60.7, '之前有顾客自己带酒水也没加收钱或者'),
    (15, 27.6, 41.2, 68.8, '之前有顾客自己带酒水也没加收钱或者不让'),
    (16, 32.4, 42.0, 74.4, '之前有顾客自己带酒水也没加收钱或者不让喝。'),
    (17, 24.3, 40.8, 65.1, '之前有顾客自己带酒水也没加收钱或者不让喝。'),
    (18, 20.6, 37.1, 57.7, '之前有顾客自己带酒水也没加收钱或者不让喝。'),
    (19, 20.2, 36.4, 56.6, '之前有顾客自己带酒水也没加收钱或者不让喝。'),
    (20, 29.7, 40.0, 69.7, '-'),
    (21, 24.8, 41.4, 66.2, '-'),
    (22, 27.0, 45.8, 72.8, '-'),
]

# 61-min 英文会议集（<redacted>.wav）WER —— 来自 STATUS.md / C-047 / C-045
WER_ROWS = [
    ('OV 流式 · 修复前（固定 max_new_tokens=32）', 17.87, 901, 52, 1025, 0.687,
     '无', 'C-047 定位：错译官方自适应预算'),
    ('OV 流式 · C-047 自适应单遍（交付）', 7.88, 455, 54, 363, 0.639,
     '无', '已是当前交付配置'),
    ('OV 段级离线 INT8（C-045 两遍式第二遍）', 7.84, 433, 73, 362, 0.72,
     '3 秒', '已废弃'),
    ('Hybrid 离线（torch encoder + OV INT8 decoder）', 8.65, 436, 73, 448, None,
     '—', '反例：证明 INT8 decoder 非主因'),
    ('CUDA 流式（audio.cpp GGUF Q8_0，reviewer 实测）', 7.69, None, None, None,
     None, '—', '上界参考'),
]

# 三套 60-min 测试集 MER（OV 自适应口径，全局对齐）
MER_ROWS = [
    ('zh_60min', 3.18, 189, 6, 141, 10557, 903, 0.590, 0.635, 0.669,
     'AISHELL-1 官方 test，人工转写'),
    ('en_60min', 5.13, 175, 171, 150, 9673, 146, 0.599, 0.637, 0.672,
     'LibriSpeech test-clean，官方转写'),
    ('mix_60min', 7.78, 185, 455, 113, 9679, 348, 0.601, 0.646, 0.772,
     '段落级语言交替，约 25 s 一块'),
]

# 三套 60-min 的分语言拆分
MER_SPLIT = [
    ('mix_60min · 中文为主段', 6.77, 119, 34, 97, 3694),
    ('mix_60min · 英文为主段', 14.05, 194, 325, 79, 4255),
]


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def load_csv(p):
    with open(p, encoding='utf-8-sig', errors='replace') as f:
        return list(csv.DictReader(f))


def f1(v):
    try:
        return round(float(v), 1)
    except Exception:
        return 0.0


def fmt(v, nd=3):
    return f'{v:.{nd}f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        ROOT, 'reports', 'OV_VS_CUDA.html'))
    args = ap.parse_args()

    m320 = load_json(os.path.join(MEAS_DIR, 'c320', 'summary.json'))
    m640 = load_json(os.path.join(MEAS_DIR, 'c640', 'summary.json'))
    cuda_ref = m320['cuda_ref']

    # CUDA 逐块聚合（数据源：stream_report.html 的分块明细表）
    _n = len(CUDA_CHUNKS)
    cuda_mean = sum(c[3] for c in CUDA_CHUNKS) / _n
    cuda_steady = sum(c[3] for c in CUDA_CHUNKS[1:]) / (_n - 1)
    cuda_enc = sum(c[1] for c in CUDA_CHUNKS) / _n
    cuda_pre = sum(c[2] for c in CUDA_CHUNKS) / _n

    def pick(m, key):
        for r in m['ov']:
            if r['key'] == key:
                return r
        raise SystemExit(f'缺少 {key} 结果')

    ig320, ig640 = pick(m320, 'ov_igpu'), pick(m640, 'ov_igpu')
    cp320, cp640 = pick(m320, 'ov_cpu'), pick(m640, 'ov_cpu')

    # ── CUDA 资源时间线（stream_metrics.csv）
    cuda_rows = load_csv(CUDA_CSV) if os.path.exists(CUDA_CSV) else []
    cuda_tl = {
        't': [r['timestamp'] for r in cuda_rows],
        'ws': [f1(r['ws_mb']) for r in cuda_rows],
        'priv': [f1(r['private_mb']) for r in cuda_rows],
        'cpu': [f1(r['cpu_pct']) for r in cuda_rows],
        'gpu': [f1(r['gpu_util_pct']) for r in cuda_rows],
        'gpumem': [f1(r['gpu_mem_mb']) for r in cuda_rows],
    }

    def proc_tl(tag, key):
        p = os.path.join(MEAS_DIR, tag, f'proc_{key}.csv')
        rows = load_csv(p) if os.path.exists(p) else []
        return {
            't': [round(f1(r['t_s']), 2) for r in rows],
            'ws': [f1(r['ws_mb']) for r in rows],
            'priv': [f1(r['private_mb']) for r in rows],
            'cpu': [f1(r['cpu_pct']) for r in rows],
            'gpu': [f1(r.get('gpu_util_pct', 0)) for r in rows],
            'gpumem': [f1(r.get('gpu_mem_mb', 0)) for r in rows],
        }

    def chunks_tl(tag, key):
        p = os.path.join(MEAS_DIR, tag, f'chunks_{key}.csv')
        rows = load_csv(p) if os.path.exists(p) else []
        return [{'chunk': int(f1(r['chunk'])), 'enc': f1(r['enc_ms']),
                 'prefill': f1(r['prefill_ms']), 'dec': f1(r['decode_ms']),
                 'total': f1(r['total_ms']), 'delta': r.get('delta', '')}
                for r in rows]

    # CUDA 侧统一成与 OV 相同的结构，便于表格 / 图表共用一份渲染逻辑
    cuda_sum = {
        'key': 'cuda',
        'device_name': cuda_ref['device'],
        'chunk_ms': cuda_ref['chunk_ms'],
        'n_chunks': cuda_ref['n_chunks'],
        'wall_s': cuda_ref['wall_s'],
        'rtf': cuda_ref['rtf'],
        # 与 OV 同口径：稳态块（去掉首块）耗时之和 / 音频时长；cuda_steady 单位是 ms
        'rtf_steady': round(
            cuda_steady * (_n - 1) / 1000.0 / cuda_ref['audio_s'], 3),
        'per_chunk_ms_mean': round(cuda_mean, 1),
        'per_chunk_ms_steady': round(cuda_steady, 1),
        'per_chunk_ms_first': cuda_ref['per_chunk_ms_first'],
        'enc_ms_mean': round(cuda_enc, 1),
        'prefill_ms_mean': round(cuda_pre, 1),
        'decode_ms_mean': None,   # CUDA 报告未拆分逐 token 生成
        'ws_mb_peak': round(max(cuda_tl['ws'], default=0), 1),
        'private_mb_peak': round(max(cuda_tl['priv'], default=0), 1),
        'cpu_pct_peak': round(max(cuda_tl['cpu'], default=0), 1),
        'gpu_util_pct_peak': round(max(cuda_tl['gpu'], default=0), 1),
        'gpu_mem_mb_peak': round(max(cuda_tl['gpumem'], default=0), 1),
        'text': cuda_ref['text'],
    }

    data = {
        'cuda': {
            'chunks': [{'chunk': c, 'enc': e, 'prefill': p, 'total': t,
                        'delta': d} for c, e, p, t, d in CUDA_CHUNKS],
            'tl': cuda_tl,
            'sum': cuda_sum,
        },
        'ig320': {'sum': ig320, 'tl': proc_tl('c320', 'ov_igpu'),
                  'chunks': chunks_tl('c320', 'ov_igpu')},
        'ig640': {'sum': ig640, 'tl': proc_tl('c640', 'ov_igpu'),
                  'chunks': chunks_tl('c640', 'ov_igpu')},
        'cp320': {'sum': cp320, 'tl': proc_tl('c320', 'ov_cpu'),
                  'chunks': chunks_tl('c320', 'ov_cpu')},
        'cp640': {'sum': cp640, 'tl': proc_tl('c640', 'ov_cpu'),
                  'chunks': chunks_tl('c640', 'ov_cpu')},
    }

    def occ(ms, chunk):
        return ms / chunk

    rep = {
        '__GEN__': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        # 核心指标卡
        '__IG320_RTF__': fmt(ig320['rtf']),
        '__IG640_RTF__': fmt(ig640['rtf']),
        '__CUDA_RTF__': fmt(cuda_ref['rtf']),
        '__IG320_WALL__': fmt(ig320['wall_s'], 2),
        '__IG640_WALL__': fmt(ig640['wall_s'], 2),
        '__IG320_COMPILE__': fmt(ig320['compile_s'], 1),
        '__CHUNKGAIN__': '-{:.0f}%'.format(
            (1 - ig640['wall_s'] / ig320['wall_s']) * 100),
        '__PERCHUNKGAIN__': '{:.0f}'.format(
            (1 - ig320['per_chunk_ms_mean'] / ig640['per_chunk_ms_mean'])
            * 100),
        '__TOTALRATIO__': '{:.2f}'.format(ig320['wall_s'] / ig640['wall_s']),
        '__TOTALGAIN__': '+{:.0f}%'.format(
            (ig320['wall_s'] / ig640['wall_s'] - 1) * 100),
        # 吞吐归一化指标：块长不同时唯一可比的「能否追上音频」的量
        '__IG640_SSRTF__': fmt(ig640['rtf_steady'], 3),
        '__IG640_THR__': '{:.2f}'.format(1.0 / ig640['rtf_steady']),
        '__CUDA_SSRTF__': fmt(cuda_steady * (_n - 1) / 1000.0
                              / cuda_ref['audio_s'], 3),
        '__CUDA_THR__': '{:.2f}'.format(
            cuda_ref['audio_s'] * 1000.0 / (cuda_steady * (_n - 1))),
        '__THRRATIO__': '{:.2f}'.format(
            (cuda_ref['audio_s'] * 1000.0 / (cuda_steady * (_n - 1)))
            / (1.0 / ig640['rtf_steady'])),
        '__IG320_MEAN__': fmt(ig320['per_chunk_ms_mean'], 1),
        '__CUDA_MEAN__': fmt(cuda_mean, 1),
        '__CUDA_STEADY__': fmt(cuda_steady, 1),
        '__IG320_OCC__': fmt(occ(ig320['per_chunk_ms_mean'], 320) * 100, 0) + '%',
        '__IG640_OCC__': fmt(occ(ig640['per_chunk_ms_steady'], 640) * 100, 0) + '%',
        '__CUDA_OCC__': fmt(occ(cuda_steady, 320) * 100, 0) + '%',
        '__RATIO__': fmt(ig320['per_chunk_ms_steady'] / cuda_steady, 2),
        # 解读区
        '__IG320_FIRST__': fmt(ig320['per_chunk_ms_first'], 1),
        '__IG320_STEADY__': fmt(ig320['per_chunk_ms_steady'], 1),
        '__IG640_MEAN__': fmt(ig640['per_chunk_ms_mean'], 1),
        '__IG640_FIRST__': fmt(ig640['per_chunk_ms_first'], 1),
        '__IG640_STEADY__': fmt(ig640['per_chunk_ms_steady'], 1),
        '__CUDA_FIRST__': fmt(cuda_ref['per_chunk_ms_first'], 1),
        '__IG320_ENC__': fmt(ig320['enc_ms_mean'], 1),
        '__IG320_PRE__': fmt(ig320['prefill_ms_mean'], 1),
        '__IG320_DEC__': fmt(ig320['decode_ms_mean'], 1),
        '__IG640_ENC__': fmt(ig640['enc_ms_mean'], 1),
        '__IG640_PRE__': fmt(ig640['prefill_ms_mean'], 1),
        '__IG640_DEC__': fmt(ig640['decode_ms_mean'], 1),
        '__CPU320_RTF__': fmt(cp320['rtf'], 2),
        '__CPU640_RTF__': fmt(cp640['rtf'], 2),
        '__CPU320_MEAN__': fmt(cp320['per_chunk_ms_mean'], 0),
        '__CPU640_MEAN__': fmt(cp640['per_chunk_ms_mean'], 0),
        '__IG320_WS__': fmt(ig320['ws_mb_peak'], 0),
        '__IG640_WS__': fmt(ig640['ws_mb_peak'], 0),
        '__IG640_GM__': fmt(ig640.get('gpu_mem_mb_peak', 0), 0),
        '__CUDA_WS__': fmt(cuda_ref['ws_mb_peak'], 0),
        '__IG320_GM__': fmt(ig320.get('gpu_mem_mb_peak', 0), 0),
        '__CUDA_GM__': fmt(cuda_ref['gpu_mem_mb_peak'], 0),
    }

    html = TEMPLATE
    for k, v in rep.items():
        html = html.replace(k, v)
    html = html.replace('__DATA__', json.dumps(data, ensure_ascii=False))
    html = html.replace('// noqa', '')

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[c052] 报告已生成 -> {args.out}')


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Confucius4-R2T2 流式推理：OpenVINO vs CUDA 对比报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; background: #0f1115; color: #e4e6eb; }
.wrap { max-width: 1280px; margin: 0 auto; padding: 32px 24px; }
h1 { font-size: 28px; margin: 0 0 8px; color: #fff; }
h2 { font-size: 20px; margin: 32px 0 16px; padding-left: 12px; border-left: 3px solid #4f8cff; color: #fff; }
.subtitle { color: #8a8f99; margin-bottom: 24px; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.card { background: #1a1d24; border: 1px solid #2a2e38; border-radius: 10px; padding: 18px 20px; }
.card .label { color: #8a8f99; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.card .value { font-size: 26px; font-weight: 600; color: #fff; margin-top: 6px; }
.card .unit { font-size: 14px; color: #8a8f99; margin-left: 4px; }
.card .note { font-size: 11px; color: #8a8f99; margin-top: 6px; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart { background: #1a1d24; border: 1px solid #2a2e38; border-radius: 10px; padding: 16px; }
.chart-title { color: #fff; font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.chart-sub { color: #8a8f99; font-size: 12px; margin-bottom: 12px; }
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
.footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid #2a2e38; color: #8a8f99; font-size: 12px; }
.kv { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a2e38; font-size: 13px; }
.kv:last-child { border-bottom: none; }
.kv .k { color: #8a8f99; }
.kv .v { color: #fff; font-family: Consolas, monospace; }
.headline { background: #1a1d24; border: 1px solid #2a2e38; border-left: 3px solid #4f8cff; border-radius: 10px; padding: 18px 22px; line-height: 1.9; color: #cbd0d8; }
.headline b { color: #fff; }
.warn { background: #3a2e1e; color: #fbbf24; padding: 1px 6px; border-radius: 3px; font-family: Consolas, monospace; }
.ok { background: #1e3a2e; color: #4ade80; padding: 1px 6px; border-radius: 3px; font-family: Consolas, monospace; }
</style>
</head>
<body>
<div class="wrap">
<h1>Confucius4-R2T2 流式推理：OpenVINO vs CUDA 对比报告</h1>
<p class="subtitle">测量时间 __GEN__ ｜ 同一台机器、同一段音频 <code>test.wav</code>（6.74 s / 16 kHz / mono / PCM16）｜ OV 2026.4.1（segment-encoder FP16 + INT8-past stateful） vs CUDA 13.3 / audio.cpp v0.9.1（GGUF Q8_0）</p>

<h2>一句话结论</h2>
<div class="headline">
<span class="tag tag-green">精度追平</span>61-min 英文会议集上，OV 流式 WER <b>7.88%</b> vs CUDA 官方流式 <b>7.69%</b>，差 <b>+0.19 pp</b>。修复自适应生成预算（C-047）之前的 <span class="warn">17.87%</span> 是 OV 端口自身的 bug，不是精度差距。<br>
<span class="tag tag-blue">OV 以交付配置（640 ms 块）即可流式</span>
同机同音频下 OV iGPU RTF <b>__IG640_RTF__</b>（&lt; 1，实时可跑），CUDA RTF <b>__CUDA_RTF__</b>。
稳态吞吐 OV <b>__IG640_THR__× 实时</b> vs CUDA <b>__CUDA_THR__× 实时</b>，差 <b>__THRRATIO__×</b>。<br>
<span class="tag tag-amber">代价是块长差一倍</span>OV 用 <b>640 ms</b> 块才换来 RTF &lt; 1；CUDA 在 <b>320 ms</b> 块就有大量余量。
若强行把 OV 也降到 320 ms 块，RTF 会涨到 <span class="warn">__IG320_RTF__</span>，<b>失去实时性</b> —— 这正是本报告把 640 ms 作为主轴的原因。<br>
<span class="tag tag-blue">已被端到端验证</span>交付的 `mic_asr_app.py` 走的就是 640 ms 这套：麦克风 16 kHz → 在线 VAD（12–20 s 切段）→ 增量解码 → GUI 上屏。60 s 连续实测 RTF <b>0.650</b>、5 段定稿、文本连贯无跨段重复。
</div>

<h2>核心指标</h2>
<div class="cards">
<div class='card'><div class='label'>OV iGPU · RTF（640 ms 块，交付）</div><div class='value'>__IG640_RTF__</div><div class='note'><span class="ok">&lt; 1 · 实时可跑</span>｜ 61-min 全长实测 0.639</div></div>
<div class='card'><div class='label'>CUDA dGPU · RTF（320 ms 块）</div><div class='value'>__CUDA_RTF__</div><div class='note'>含约 2.2 s 一次性模型加载</div></div>
<div class='card'><div class='label'>OV iGPU · 稳态吞吐</div><div class='value'>__IG640_THR__<span class='unit'>× 实时</span></div><div class='note'>稳态 RTF __IG640_SSRTF__</div></div>
<div class='card'><div class='label'>CUDA · 稳态吞吐</div><div class='value'>__CUDA_THR__<span class='unit'>× 实时</span></div><div class='note'>稳态 RTF __CUDA_SSRTF__</div></div>
</div>
<p class="subtitle" style="margin-top:-8px">⚠️ <b>两边块长不同（OV 640 ms / CUDA 320 ms），所以主指标用 RTF / 稳态吞吐比较，不用每块毫秒数比较</b> —— 后者在块长不同时无意义。同块长（都 320 ms）的严格对照见下节。</p>

<div class="headline" style="border-left-color:#fbbf24">
<b style="color:#fbbf24">⚠️ 先回答一个问题：为什么本报告主轴是 640 ms，而不是和 CUDA 一样的 320 ms？</b><br>
<b>因为 640 ms 才是交付口径。</b>此前所有 61-min 数据、交付的 <code>mic_asr_app.py</code> 端到端验证，用的都是 <code>640 ms</code> 块；
本次为与 CUDA 报告严格对照，额外补测了一组 <code>320 ms</code>。
同一脚本、同一模型、同一段音频，只改一个 <code>--chunk-ms</code>：
<b>两个 RTF 都是真的，差异全部来自块长，不是性能回归。</b>

<table style="margin-top:12px"><thead><tr>
<th>块长</th><th>块数</th><th>墙钟 (s)</th><th>RTF</th><th>每块均值 (ms)</th><th>对照</th>
</tr></thead><tbody>
<tr><td class='num'>640 ms</td><td class='num'>11</td><td class='num'>__IG640_WALL__</td><td class='num'><span class="ok">__IG640_RTF__</span></td><td class='num'>__IG640_MEAN__</td><td><b>本报告主轴 · 交付口径</b>｜与 61-min 全长实测 <code>0.639</code> 一致</td></tr>
<tr><td class='num'>320 ms</td><td class='num'>22</td><td class='num'>__IG320_WALL__</td><td class='num'><span class="warn">__IG320_RTF__</span></td><td class='num'>__IG320_MEAN__</td><td>仅为与 CUDA 做同块长对照（CUDA 侧即 320 ms）</td></tr>
</tbody></table>

<b style="color:#fbbf24">为什么块长减半，RTF 几乎翻倍？</b>
因为每块的成本里<b>大头是"与块长无关的固定开销"</b>：segment encoder 每个 chunk 都要
<b>把整段累积音频重新编码一遍</b>（无 window cache），decoder 也要对<b>整个已生成前缀</b>做一次 prefill。
块长从 640 → 320 ms，每块成本只从 <b>__IG640_MEAN__ ms</b> 降到 <b>__IG320_MEAN__ ms</b>
（省 <b>__PERCHUNKGAIN__%</b>），但块数从 11 涨到 22（翻倍）——
净结果是总处理时间 <b>__IG640_WALL__ s → __IG320_WALL__ s，涨 __TOTALGAIN__（×__TOTALRATIO__）</b>。
换句话说：<b>块长减半只省下 11% 的单块成本，却要付 2 倍的块数</b>——
短块买不到等比例的性能，只买到了更细的增量粒度。<br>
<b>所以本报告的读法：</b>主指标（RTF / 稳态吞吐）看 <b>640 ms</b> 那一行 —— 那是交付配置；
<b>320 ms</b> 那一行只用于回答"和 CUDA 同块长时谁更快"这一个问题。
</div>

<h2>精度对比</h2>
<div class="row">
<div class="chart">
<div class="chart-title">61-min 英文会议集 WER</div>
<div class="chart-sub">越低越好 ｜ 参考文本统一为 MiniMax 云端 asr-1.0（11066 词）</div>
<div id="chart-wer" class="chart-box"></div>
</div>
<div class="chart">
<div class="chart-title">三套 60-min 测试集 MER（中文按字 / 英文按词）</div>
<div class="chart-sub">OV 自适应口径 ｜ 误差拆分为 替换 S / 删除 D / 插入 I</div>
<div id="chart-mer" class="chart-box"></div>
</div>
</div>
<table><thead><tr>
<th>方案</th><th>WER</th><th>S</th><th>D</th><th>I</th><th>RTF</th><th>段尾延迟</th><th>说明</th>
</tr></thead><tbody>
<tr><td>OV 流式 · 修复前（固定 max_new_tokens=32）</td><td class='num'>17.87%</td><td class='num'>901</td><td class='num'>52</td><td class='num'>1025</td><td class='num'>0.687</td><td>无</td><td>C-047 定位：错译官方自适应预算</td></tr>
<tr><td><b>OV 流式 · C-047 自适应单遍（交付）</b></td><td class='num'><b>7.88%</b></td><td class='num'>455</td><td class='num'>54</td><td class='num'>363</td><td class='num'><b>0.639</b></td><td>无</td><td>已追平两遍式 7.84%，无额外延迟</td></tr>
<tr><td>OV 段级离线 INT8（C-045 两遍式第二遍）</td><td class='num'>7.84%</td><td class='num'>433</td><td class='num'>73</td><td class='num'>362</td><td class='num'>0.72</td><td><b>3 秒</b></td><td>已废弃</td></tr>
<tr><td>Hybrid 离线（torch encoder + OV INT8 decoder）</td><td class='num'>8.65%</td><td class='num'>436</td><td class='num'>73</td><td class='num'>448</td><td class='num'>—</td><td>—</td><td>反例：证明 INT8 decoder 非主因</td></tr>
<tr><td><b>CUDA 流式（audio.cpp GGUF Q8_0，reviewer 实测）</b></td><td class='num'><b>7.69%</b></td><td class='num'>—</td><td class='num'>—</td><td class='num'>—</td><td class='num'>—</td><td>—</td><td>上界参考</td></tr>
</tbody></table>

<h3 style="color:#cbd0d8;font-size:15px;margin:24px 0 12px;">三套 60-min 测试集（人工转写参考，与上一表不同量纲）</h3>
<table><thead><tr>
<th>测试集</th><th>整体 MER</th><th>S</th><th>D</th><th>I</th><th>n_ref</th><th>重复 4-gram</th><th>RTF</th><th>P95</th><th>max</th><th>说明</th>
</tr></thead><tbody>
<tr><td><b>zh_60min</b></td><td class='num'><b>3.18%</b></td><td class='num'>189</td><td class='num'>6</td><td class='num'>141</td><td class='num'>10557</td><td class='num'>903</td><td class='num'>0.590</td><td class='num'>0.635</td><td class='num'>0.669</td><td>AISHELL-1 官方 test</td></tr>
<tr><td><b>en_60min</b></td><td class='num'><b>5.13%</b></td><td class='num'>175</td><td class='num'>171</td><td class='num'>150</td><td class='num'>9673</td><td class='num'>146</td><td class='num'>0.599</td><td class='num'>0.637</td><td class='num'>0.672</td><td>LibriSpeech test-clean</td></tr>
<tr><td><b>mix_60min</b></td><td class='num'><b>7.78%</b></td><td class='num'>185</td><td class='num'>455</td><td class='num'>113</td><td class='num'>9679</td><td class='num'>348</td><td class='num'>0.601</td><td class='num'>0.646</td><td class='num'>0.772</td><td>段落级语言交替</td></tr>
<tr><td>├ 中文为主段</td><td class='num'>6.77%</td><td class='num'>119</td><td class='num'>34</td><td class='num'>97</td><td class='num'>3694</td><td class='num'>—</td><td class='num'>—</td><td class='num'>—</td><td class='num'>—</td><td></td></tr>
<tr><td>└ 英文为主段</td><td class='num'>14.05%</td><td class='num'>194</td><td class='num'>325</td><td class='num'>79</td><td class='num'>4255</td><td class='num'>—</td><td class='num'>—</td><td class='num'>—</td><td class='num'>—</td><td></td></tr>
</tbody></table>
<p class="subtitle" style="margin-top:12px">⚠️ <b>两张表不可横向比较</b>：上一表参考文本是 MiniMax 云端 asr-1.0；下一表用的是官方人工转写。
⚠️ 且 <code>CUDA 7.69%</code> 对归一化口径敏感：本机脚本在「保留数字 / 去数字」两种设置下分别给出
<code>7.62%</code> 与 <code>7.51%</code>。三者落在 7.5–7.7% 区间，与 OV 的 7.88% 差 0.2–0.4 pp。</p>

<h2>资源占用（峰值）</h2>
<div class="cards">
<div class='card'><div class='label'>工作集 · OV iGPU（640 ms 块）</div><div class='value'>__IG640_WS__<span class='unit'>MB</span></div><div class='note'>320 ms 块：<code>__IG320_WS__</code> MB</div></div>
<div class='card'><div class='label'>工作集 · CUDA</div><div class='value'>__CUDA_WS__<span class='unit'>MB</span></div><div class='note'>私有内存 <code>4.8 GB</code></div></div>
<div class='card'><div class='label'>GPU 显存 · OV iGPU（640 ms 块）</div><div class='value'>__IG640_GM__<span class='unit'>MB</span></div><div class='note'>iGPU 为 UMA 共享内存，与进程内存重叠</div></div>
<div class='card'><div class='label'>GPU 显存 · CUDA</div><div class='value'>__CUDA_GM__<span class='unit'>MB</span></div><div class='note'>8 GB 显存中占 41%</div></div>
</div>
<table><thead><tr>
<th>配置</th><th>块长</th><th>墙钟 (s)</th><th>RTF</th><th>稳态 RTF</th><th>每块均值 (ms)</th><th>工作集峰值 (MB)</th><th>Private 峰值 (MB)</th><th>CPU 峰值 (%)</th><th>GPU 占用峰值 (%)</th><th>GPU 内存峰值 (MB)</th>
</tr></thead><tbody id="tbody-res"></tbody></table>
<p class="subtitle" style="margin-top:12px">⚠️ iGPU 为统一内存架构（UMA），「GPU 内存」来自系统共享内存，与进程内存高度重叠 —— <b>不应把 OV iGPU 的 GPU 内存与 CUDA 的专用显存直接相加或对比</b>。</p>

<h2>推理延迟拆解</h2>
<div class="row">
<div class="chart">
<div class="chart-title">交付口径逐块构成（OV iGPU · 640 ms / 块 · 11 块）</div>
<div class="chart-sub">堆叠：蓝 = 音频编码，紫 = Decoder Prefill，青 = 逐 token 生成 ｜ 红色虚线 = 640 ms 块预算 ｜ 稳态每块 __IG640_STEADY__ ms，占用预算 __IG640_OCC__%</div>
<div id="chart-latency640" class="chart-box"></div>
</div>
<div class="chart">
<div class="chart-title">块长对 OV iGPU 的影响（同一段 6.74 s 音频）</div>
<div class="chart-sub">左：每块成本几乎不随块长缩放（固定开销主导）｜ 右：总处理时间随块数近乎线性增长</div>
<div id="chart-chunk" class="chart-box"></div>
</div>
</div>
<div class="row">
<div class="chart">
<div class="chart-title">同块长严格对照：OV vs CUDA 逐块（都 320 ms / 块 · 22 块）</div>
<div class="chart-sub">OV 堆叠：蓝 = 音频编码，紫 = Decoder Prefill，青 = 逐 token 生成 ｜ CUDA 堆叠：橙 = 音频编码，绿 = Decoder Prefill ｜ 红色虚线 = 320 ms 块预算</div>
<div id="chart-latency" class="chart-box"></div>
</div>
<div class="chart">
<div class="chart-title">每块预算占用率（稳态每块毫秒 ÷ 块长）</div>
<div class="chart-sub">&gt; 100% 即追不上实时流 ｜ 只有 640 ms 配置有余量 ｜ 红色虚线 = 100% 实时线</div>
<div id="chart-occ" class="chart-box"></div>
</div>
</div>

<h2>资源时间线</h2>
<div class="row">
<div class="chart">
<div class="chart-title">进程内存（WorkingSet 实线 / Private 虚线）</div>
<div class="chart-sub">单位 MB ｜ 蓝 = OV iGPU，橙 = OV CPU，绿 = CUDA</div>
<div id="chart-mem" class="chart-box"></div>
</div>
<div class="chart">
<div class="chart-title">GPU 显存 / 共享内存占用</div>
<div class="chart-sub">单位 MB ｜ 蓝 = OV iGPU（UMA 共享），绿 = CUDA 专用显存</div>
<div id="chart-gpumem" class="chart-box"></div>
</div>
</div>
<div class="chart">
<div class="chart-title">GPU 占用率</div>
<div class="chart-sub">单位 % ｜ 250 ms 采样间隔</div>
<div id="chart-gpuutil" class="chart-box"></div>
</div>

<h2>分块延迟明细（OV 640 ms / 块 · 交付口径）</h2>
<table><thead><tr>
<th>Chunk</th><th>OV@640 编码</th><th>OV@640 Prefill</th><th>OV@640 生成</th><th>OV@640 合计</th><th>OV@640 增量文本</th><th>OV@320 合计</th><th>CUDA 编码</th><th>CUDA Prefill</th><th>CUDA 合计</th>
</tr></thead><tbody id="tbody-chunks"></tbody></table>
<p class="subtitle" style="margin-top:12px">⚠️ <b>行号是块序号，不是时间对齐</b>：OV@640 第 <i>i</i> 块覆盖音频 <code>[640(i-1), 640i)</code> ms，OV@320 / CUDA 第 <i>i</i> 块覆盖 <code>[320(i-1), 320i)</code> ms —— 同一行里 OV@640 与 CUDA 覆盖的音频区间相差一倍，只能纵向看各自趋势，不能横向逐行比大小。
OV@640 共 11 块（第 11 块为尾 flush，耗时 0），故后 11 行 OV@640 列为空属正常。CUDA 侧报告未拆分逐 token 生成。</p>

<h2>关键指标解读</h2>
<div class="chart">
<div class='kv'><span class='k'>音频时长 / 采样</span><span class='v'>6.74 s（16 kHz mono 16-bit）</span></div>
<div class='kv'><span class='k'>块大小 / 块数</span><span class='v'>640 ms → 11 块（含尾 flush）｜ 320 ms → 22 块</span></div>
<div class='kv'><span class='k'>OV iGPU 每块（640 ms · 交付）</span><span class='v'>均值 __IG640_MEAN__ ms ｜ 首块 __IG640_FIRST__ ms ｜ 稳态 __IG640_STEADY__ ms</span></div>
<div class='kv'><span class='k'>OV iGPU 每块（320 ms · 对照）</span><span class='v'>均值 __IG320_MEAN__ ms ｜ 首块 __IG320_FIRST__ ms ｜ 稳态 __IG320_STEADY__ ms</span></div>
<div class='kv'><span class='k'>CUDA 每块（320 ms）</span><span class='v'>均值 __CUDA_MEAN__ ms ｜ 首块 __CUDA_FIRST__ ms（含 CUDA Graph 预热）｜ 稳态 __CUDA_STEADY__ ms</span></div>
<div class='kv'><span class='k'>稳态吞吐（各自块长，能否追上实时）</span><span class='v'>CUDA __CUDA_THR__× vs OV __IG640_THR__× —— 差 <b>__THRRATIO__×</b></span></div>
<div class='kv'><span class='k'>单块速度比（同 320 ms 块，OV ÷ CUDA 稳态）</span><span class='v'>__RATIO__×</span></div>
<div class='kv'><span class='k'>OV iGPU 延迟构成（640 ms）</span><span class='v'>编码 __IG640_ENC__ ms ｜ Prefill __IG640_PRE__ ms ｜ 生成 __IG640_DEC__ ms</span></div>
<div class='kv'><span class='k'>OV iGPU 延迟构成（320 ms）</span><span class='v'>编码 __IG320_ENC__ ms ｜ Prefill __IG320_PRE__ ms ｜ 生成 __IG320_DEC__ ms</span></div>
<div class='kv'><span class='k'>块长 320 → 640 ms 的收益</span><span class='v'>总处理时间 __IG320_WALL__ s → __IG640_WALL__ s（__CHUNKGAIN__）</span></div>
<div class='kv'><span class='k'>纯 CPU 参考（320 ms / 640 ms）</span><span class='v'>RTF __CPU320_RTF__ / __CPU640_RTF__ ｜ 每块 __CPU320_MEAN__ ms / __CPU640_MEAN__ ms</span></div>
<div class='kv'><span class='k'>识别结果（三档一致）</span><span class='v'>之前有顾客自己带酒水也没加收钱或者不让喝。</span></div>
</div>

<h2>口径与局限（请 reviewer 重点看）</h2>
<div class="chart"><p style="line-height:1.9;color:#cbd0d8">
<b>1. 速度对比是「iGPU vs dGPU」，不是「同硬件上的运行时对比」。</b>
本机 <code>GPU.1</code> 恰好就是 RTX 5050 Laptop，我们本想让 OpenVINO 也跑在这块卡上，
从而把「运行时/量化差异」与「硬件差异」分开。<b>但这条路走不通</b>：OV 2026.4 的 intel_gpu 插件
能枚举到 GPU.1（能力报 FP32 / BIN / INT8，不含 FP16），而 encoder IR 的常量是 FP16；
编译到 <code>convert:Convert_23531</code> 这个 F16→F32 reorder 节点时 kernel_selector
找不到可用实现，<code>compile_model</code> 直接抛 RuntimeError。
f32 / f16 / 默认 / HETERO 四种配置全部失败。
所以表中 <b>__RATIO__×</b> 的差距里<b>同时包含</b>「iGPU 算力弱于 dGPU」和「OV 运行时开销」两部分，
本报告无法进一步拆分。<br>

<b>2. CUDA 侧只引用、未重跑。</b>audio.cpp 是独立二进制，不在本仓库构建链路内；
CUDA 数字来自 <code>confucius4-r2t2/stream_report.html</code> 与 <code>stream_metrics.csv</code>
（2026-10-08 测）。两侧采样间隔统一 250 ms、字段同名同单位；
但进程内存口径 RSS/USS vs Windows WorkingSet/Private 是<b>近似对应</b>——趋势可比，绝对值不可逐字节比。<br>

<b>3. 6.74 s 是极短样本，墙钟里的一次性开销占大头。</b>
CUDA 的 3.67 s 墙钟中约 2.2 s 是模型加载 + CUDA Graph 预热；
OV 侧我们把编译（约 __IG320_COMPILE__ s）与预热排除在计时之外。
因此直接比 RTF 对 CUDA 不公平。更干净的指标是<b>稳态每块延迟</b>：
CUDA <b>__CUDA_STEADY__ ms</b> vs OV iGPU <b>__IG320_STEADY__ ms</b>（同为 320 ms 块）。
交付口径（640 ms）下 OV 稳态每块 <b>__IG640_STEADY__ ms</b>、预算占用 <b>__IG640_OCC__%</b>，
换算成吞吐为 <b>__IG640_THR__× 实时</b>。<br>

<b>4. 精度对比的参考不是人工转写。</b>61-min 集的 reference 是 MiniMax 云端 asr-1.0，
故 7.88% / 7.69% 都是「相对云端 ASR」的误差，不等于相对人工转写的绝对 WER。<br>

<b>5. 混合集 MER 混了两种尺度。</b><code>mix_60min</code> 的 7.78% 里中文按字、英文按词，
是 CER 与 WER 的混合；英文侧 14.05% 与中文侧 6.77% 不能直接相减。
</p></div>

<h2>结论</h2>
<div class="chart"><p style="line-height:1.9;color:#cbd0d8">
<span class="tag tag-green">精度 · OV 7.88% vs CUDA 7.69%</span>
差距 <b>0.19 pp</b>，落在归一化口径波动（7.51–7.69%）范围内，可视为<b>已追平</b>。
关键结论：此前的 17.87% 并非 OV 精度问题，而是 <code>max_new_tokens</code> 被固定为 32、
错译了官方的自适应预算逻辑（C-047）。<br>

<span class="tag tag-amber">速度 · iGPU 需要 640 ms 块才实时</span>
交付口径（640 ms）下 OV iGPU RTF <b>__IG640_RTF__</b>、稳态 <b>__IG640_THR__× 实时</b>，61-min 全长实测 RTF 0.639、P95 0.675，<b>满足 ≤0.8 验收线</b>。
CUDA 在 320 ms 块下稳态 <b>__CUDA_THR__× 实时</b>，是 OV 的 <b>__THRRATIO__×</b>。
若强行把 OV 也降到 320 ms 块，每块 <b>__IG320_MEAN__ ms</b>、RTF <b>__IG320_RTF__</b>，<b>反而追不上实时流</b>。
即：iGPU 方案成立的前提是接受 640 ms 的增量粒度。<br>

<span class="tag tag-blue">实时性已被端到端验证</span>
交付的 `mic_asr_app.py` 走的就是这套 640 ms 配置：麦克风 16 kHz 采集 → 在线 VAD
（12–20 s 切段、切点对齐 chunk 边界）→ 增量解码 → GUI 实时上屏。60 s 连续实测
RTF <b>0.650</b>、5 段定稿、文本连贯无跨段重复。也就是说上表的 RTF 不是
「离线跑批换算出来的理论值」，而是真实麦克风通路里跑出来的。<br>

<span class="tag tag-blue">部署建议</span>
- 有 NVIDIA 独显 → 继续用 CUDA / audio.cpp：每块 55–65 ms，余量充足，且不切段可到 240–300 s。<br>
- 只有 Intel iGPU / CPU → OV 方案可用，但必须用 <b>640 ms 块 + 12–20 s VAD 切段</b>；
  纯 CPU 推理 RTF 5–11，<b>仅适合离线批处理</b>。<br>
- 两者<b>都需要调用方自己做 VAD 切句</b>：CUDA 超过 240–300 s、OV 旧 IR 超过 120 s 都会 OOM / 超上限。
</p></div>

<div class='footer'>
OpenVINO 侧数据来源：<code>reports/c052_ov_vs_cuda/{c320,c640}/summary.json</code>、<code>chunks_*.csv</code>、<code>proc_*.csv</code>（生成脚本 <code>c052_ov_vs_cuda.py</code>）｜
CUDA 侧数据来源：<code>C:\Users\Trekker-PTL\confucius4-r2t2\stream_metrics.csv</code>、<code>stream_report.html</code>｜
采样间隔 250 ms ｜ 模型：<code>models/ov-encoder-segment-reviewer</code> + <code>models/ov-int8-past</code>
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

// ── 1. WER 对比 ───────────────────────────────────────────
echarts.init(document.getElementById('chart-wer')).setOption({
  backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
  grid:{left:70, right:30, top:20, bottom:80}, tooltip:TT,
  xAxis:{type:'category',
    data:['OV 修复前\n(固定 32)', 'OV 交付\n(自适应)', 'OV 两遍式\n(7.84)', 'CUDA 官方\n流式'],
    axisLabel:{color:'#8a8f99', fontSize:11, lineHeight:16},
    axisLine:{lineStyle:{color:'#2a2e38'}}},
  yAxis:Object.assign({type:'value', name:'WER %', max:20,
    nameTextStyle:{color:'#8a8f99'}}, AX),
  series:[{
    type:'bar', barWidth:'45%',
    data:[{value:17.87, itemStyle:{color:C_RED}},
          {value:7.88, itemStyle:{color:C_BLUE}},
          {value:7.84, itemStyle:{color:C_PURPLE}},
          {value:7.69, itemStyle:{color:C_GREEN}}],
    label:{show:true, position:'top', color:'#fff', formatter:'{c}%'}
  }]
});

// ── 2. MER 三套 ──────────────────────────────────────────
echarts.init(document.getElementById('chart-mer')).setOption({
  backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
  legend:LG, grid:{left:60, right:20, top:40, bottom:40}, tooltip:TT,
  xAxis:{type:'category', data:['zh_60min','en_60min','mix_60min'],
    axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}},
  yAxis:Object.assign({type:'value', name:'MER %',
    nameTextStyle:{color:'#8a8f99'}}, AX),
  series:[
    {name:'整体 MER', type:'bar', data:[3.18, 5.13, 7.78],
     itemStyle:{color:C_BLUE},
     label:{show:true, position:'top', color:'#fff', formatter:'{c}%'}},
    {name:'中文为主段', type:'bar', data:[3.18, null, 6.77],
     itemStyle:{color:C_PURPLE}},
    {name:'英文为主段', type:'bar', data:[null, 5.13, 14.05],
     itemStyle:{color:C_AMBER}}
  ]
});

// ── 3. 交付口径逐块构成（OV iGPU · 640 ms）───────────────
(function(){
  const ci = D.ig640.chunks;
  const xs = ci.map(c => c.chunk);
  echarts.init(document.getElementById('chart-latency640')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:60, right:20, top:45, bottom:30}, tooltip:TT,
    xAxis:{type:'category', data:xs, name:'Chunk',
      nameTextStyle:{color:'#8a8f99'},
      axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'ms', max:700,
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'音频编码', type:'bar', stack:'ov640',
       data:ci.map(c => c.enc), itemStyle:{color:C_BLUE}},
      {name:'Decoder Prefill', type:'bar', stack:'ov640',
       data:ci.map(c => c.prefill), itemStyle:{color:C_PURPLE}},
      {name:'逐 token 生成', type:'bar', stack:'ov640',
       data:ci.map(c => c.dec), itemStyle:{color:C_CYAN},
       label:{show:true, position:'inside', color:'#fff', fontSize:10,
              formatter:'{c}'}},
      {name:'640 ms 块预算', type:'line', data:xs.map(() => 640),
       symbol:'none', lineStyle:{color:C_RED, type:'dashed', width:1.5}}
    ]
  });
})();

// ── 3a. 同块长严格对照（OV 320 vs CUDA 320）──────────────
(function(){
  const cc = D.cuda.chunks, ci = D.ig320.chunks;
  const xs = cc.map(c => c.chunk);
  echarts.init(document.getElementById('chart-latency')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:60, right:20, top:45, bottom:30}, tooltip:TT,
    xAxis:{type:'category', data:xs, name:'Chunk',
      nameTextStyle:{color:'#8a8f99'},
      axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'ms',
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'OV 音频编码', type:'bar', stack:'ov',
       data:ci.map(c => c.enc), itemStyle:{color:C_BLUE}},
      {name:'OV Decoder Prefill', type:'bar', stack:'ov',
       data:ci.map(c => c.prefill), itemStyle:{color:C_PURPLE}},
      {name:'OV 逐 token 生成', type:'bar', stack:'ov',
       data:ci.map(c => c.dec), itemStyle:{color:C_CYAN}},
      {name:'CUDA 音频编码', type:'bar', stack:'cu',
       data:cc.map(c => c.enc), itemStyle:{color:C_ORANGE}},
      {name:'CUDA Decoder Prefill', type:'bar', stack:'cu',
       data:cc.map(c => c.prefill), itemStyle:{color:C_GREEN}},
      {name:'320 ms 块预算', type:'line', data:xs.map(() => 320),
       symbol:'none', lineStyle:{color:C_RED, type:'dashed', width:1.5}}
    ]
  });
})();

// ── 3b. 块长 → 每块成本 / 总耗时 ──────────────────────────
(function(){
  const a = D.ig320.sum, b = D.ig640.sum;
  echarts.init(document.getElementById('chart-chunk')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, tooltip:TT,
    grid:[{left:60, right:'55%', top:45, bottom:30},
          {left:'58%', right:20, top:45, bottom:30}],
    xAxis:[
      {gridIndex:0, type:'category', data:['320 ms','640 ms'],
       axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}},
      {gridIndex:1, type:'category', data:['320 ms','640 ms'],
       axisLabel:{color:'#8a8f99'}, axisLine:{lineStyle:{color:'#2a2e38'}}}
    ],
    yAxis:[
      Object.assign({gridIndex:0, type:'value', name:'每块 ms', max:450,
        nameTextStyle:{color:'#8a8f99'}}, AX),
      Object.assign({gridIndex:1, type:'value', name:'总墙钟 s', max:9,
        nameTextStyle:{color:'#8a8f99'}}, AX)
    ],
    series:[
      {name:'音频编码', type:'bar', stack:'p', xAxisIndex:0, yAxisIndex:0,
       data:[a.enc_ms_mean, b.enc_ms_mean], itemStyle:{color:C_BLUE}},
      {name:'Decoder Prefill', type:'bar', stack:'p', xAxisIndex:0,
       yAxisIndex:0, data:[a.prefill_ms_mean, b.prefill_ms_mean],
       itemStyle:{color:C_PURPLE}},
      {name:'逐 token 生成', type:'bar', stack:'p', xAxisIndex:0,
       yAxisIndex:0, data:[a.decode_ms_mean, b.decode_ms_mean],
       itemStyle:{color:C_CYAN},
       label:{show:true, position:'top', color:'#fff',
              formatter:'每块 {c} ms'}},
      {name:'总墙钟（标 RTF）', type:'bar', xAxisIndex:1, yAxisIndex:1,
       barWidth:'45%',
       data:[{value:a.wall_s, itemStyle:{color:C_RED}},
             {value:b.wall_s, itemStyle:{color:C_GREEN}}],
       label:{show:true, position:'top', color:'#fff',
              formatter:function(p){
                return (p.dataIndex === 0 ? a.rtf : b.rtf).toFixed(3)
                       + ' RTF · ' + p.value.toFixed(2) + 's';
              }}}
    ]
  });
})();

// ── 3c. 每块预算占用率 ──────────────────────────────────
(function(){
  const LEGS = [
    {name:'OV iGPU\n@640 ms（交付）', d:D.ig640, chunk:640},
    {name:'OV iGPU\n@320 ms', d:D.ig320, chunk:320},
    {name:'CUDA dGPU\n@320 ms', d:D.cuda, chunk:320}
  ];
  const occ = LEGS.map(L => +(L.d.sum.per_chunk_ms_steady / L.chunk * 100)
                              .toFixed(1));
  echarts.init(document.getElementById('chart-occ')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, tooltip:TT,
    grid:{left:55, right:20, top:45, bottom:45},
    xAxis:{type:'category', data:LEGS.map(L => L.name),
      axisLabel:{color:'#8a8f99', fontSize:11, lineHeight:16},
      axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'%', max:130,
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'稳态每块 ÷ 块长', type:'bar', barWidth:'45%',
       data:occ.map(v => ({value:v,
         itemStyle:{color: v > 100 ? C_RED : (v > 80 ? C_AMBER : C_GREEN)}})),
       label:{show:true, position:'top', color:'#fff', formatter:'{c}%'}},
      {name:'100% 实时线', type:'line', data:LEGS.map(() => 100),
       symbol:'none', lineStyle:{color:C_RED, type:'dashed', width:1.5}}
    ]
  });
})();

// ── 4. 进程内存时间线（交付口径 640 ms）──────────────────
(function(){
  const a = D.ig640.tl, b = D.cp640.tl, c = D.cuda.tl;
  const n = Math.max(a.t.length, b.t.length, c.t.length);
  const xs = [];
  for (let i = 0; i < n; i++) xs.push(c.t[i] !== undefined ? c.t[i] : String(i));
  echarts.init(document.getElementById('chart-mem')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:70, right:20, top:40, bottom:60}, tooltip:TT,
    xAxis:{type:'category', data:xs,
      axisLabel:{color:'#8a8f99', rotate:35, fontSize:10,
                 interval:Math.max(0, Math.floor(n/12))},
      axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'MB',
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'OV iGPU WorkingSet', type:'line', showSymbol:false,
       data:a.ws, itemStyle:{color:C_BLUE}},
      {name:'OV iGPU Private', type:'line', showSymbol:false,
       data:a.priv, itemStyle:{color:C_BLUE}, lineStyle:{type:'dashed'}},
      {name:'OV CPU WorkingSet', type:'line', showSymbol:false,
       data:b.ws, itemStyle:{color:C_ORANGE}},
      {name:'CUDA WorkingSet', type:'line', showSymbol:false,
       data:c.ws, itemStyle:{color:C_GREEN}},
      {name:'CUDA Private', type:'line', showSymbol:false,
       data:c.priv, itemStyle:{color:C_GREEN}, lineStyle:{type:'dashed'}}
    ]
  });
})();

// ── 5. GPU 显存时间线（交付口径 640 ms）──────────────────
(function(){
  const a = D.ig640.tl, c = D.cuda.tl;
  const n = Math.max(a.t.length, c.t.length);
  const xs = [];
  for (let i = 0; i < n; i++) xs.push(c.t[i] !== undefined ? c.t[i] : String(i));
  echarts.init(document.getElementById('chart-gpumem')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:70, right:20, top:40, bottom:60}, tooltip:TT,
    xAxis:{type:'category', data:xs,
      axisLabel:{color:'#8a8f99', rotate:35, fontSize:10,
                 interval:Math.max(0, Math.floor(n/12))},
      axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'MB', max:8150,
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'OV iGPU（UMA 共享）', type:'line', showSymbol:false,
       data:a.gpumem, itemStyle:{color:C_BLUE}, areaStyle:{opacity:0.12}},
      {name:'CUDA 专用显存', type:'line', showSymbol:false,
       data:c.gpumem, itemStyle:{color:C_GREEN}, areaStyle:{opacity:0.12}}
    ]
  });
})();

// ── 6. GPU 占用率（交付口径 640 ms）──────────────────────
(function(){
  const a = D.ig640.tl, c = D.cuda.tl;
  const n = Math.max(a.t.length, c.t.length);
  const xs = [];
  for (let i = 0; i < n; i++) xs.push(c.t[i] !== undefined ? c.t[i] : String(i));
  echarts.init(document.getElementById('chart-gpuutil')).setOption({
    backgroundColor:'transparent', textStyle:{color:'#e4e6eb'},
    legend:LG, grid:{left:60, right:20, top:40, bottom:60}, tooltip:TT,
    xAxis:{type:'category', data:xs,
      axisLabel:{color:'#8a8f99', rotate:35, fontSize:10,
                 interval:Math.max(0, Math.floor(n/12))},
      axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:Object.assign({type:'value', name:'%', max:100,
      nameTextStyle:{color:'#8a8f99'}}, AX),
    series:[
      {name:'OV iGPU', type:'line', showSymbol:false, data:a.gpu,
       itemStyle:{color:C_BLUE}, areaStyle:{opacity:0.12}},
      {name:'CUDA dGPU', type:'line', showSymbol:false, data:c.gpu,
       itemStyle:{color:C_GREEN}, areaStyle:{opacity:0.12}}
    ]
  });
})();

// ── 资源对照表 ───────────────────────────────────────────
(function(){
  const LEGS = [
    {name:'OV · Intel Xe3 iGPU @640 ms（交付默认）', d:D.ig640, chunk:640},
    {name:'CUDA · RTX 5050 Laptop (dGPU)', d:D.cuda, chunk:D.cuda.sum.chunk_ms},
    {name:'OV · Intel Xe3 iGPU @320 ms（与 CUDA 同块长）', d:D.ig320, chunk:320},
    {name:'OV · Core Ultra 7 356H (CPU) @640 ms', d:D.cp640, chunk:640},
    {name:'OV · Core Ultra 7 356H (CPU) @320 ms', d:D.cp320, chunk:320}
  ];
  const n = v => (v === null || v === undefined) ? '-' : v.toFixed(1);
  let html = '';
  LEGS.forEach(function(L){
    const s = L.d.sum;
    const ratio = (s.per_chunk_ms_steady / L.chunk);
    html += '<tr><td>' + L.name + '</td>'
      + '<td class="num">' + L.chunk + '</td>'
      + '<td class="num">' + s.wall_s.toFixed(2) + '</td>'
      + '<td class="num"><b>' + s.rtf.toFixed(3) + '</b></td>'
      + '<td class="num">' + s.rtf_steady.toFixed(3) + '</td>'
      + '<td class="num">' + n(s.per_chunk_ms_mean) + '</td>'
      + '<td class="num">' + s.ws_mb_peak.toFixed(0) + '</td>'
      + '<td class="num">' + s.private_mb_peak.toFixed(0) + '</td>'
      + '<td class="num">' + n(s.cpu_pct_peak) + '</td>'
      + '<td class="num">' + n(s.gpu_util_pct_peak) + '</td>'
      + '<td class="num">' + n(s.gpu_mem_mb_peak) + '</td>'
      + '</tr>';
  });
  document.getElementById('tbody-res').innerHTML = html;
})();

// ── 分块明细表（OV@640 主轴 + OV@320 / CUDA 对照）────────
(function(){
  const tb = document.getElementById('tbody-chunks');
  let html = '';
  D.cuda.chunks.forEach((c, i) => {
    const o = D.ig640.chunks[i] || {};    // 640 ms 仅 11 行有值
    const o3 = D.ig320.chunks[i] || {};
    const n = v => (v === undefined || v === null) ? '-' : v.toFixed(1);
    html += '<tr><td class="num">' + c.chunk + '</td>'
      + '<td class="num">' + n(o.enc) + '</td>'
      + '<td class="num">' + n(o.prefill) + '</td>'
      + '<td class="num">' + n(o.dec) + '</td>'
      + '<td class="num"><b>' + n(o.total) + '</b></td>'
      + '<td>' + (o.delta || '-') + '</td>'
      + '<td class="num">' + n(o3.total) + '</td>'
      + '<td class="num">' + n(c.enc) + '</td>'
      + '<td class="num">' + n(c.prefill) + '</td>'
      + '<td class="num"><b>' + n(c.total) + '</b></td></tr>';
  });
  tb.innerHTML = html;
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
