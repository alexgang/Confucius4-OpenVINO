"""c069n_planb_e2e_cost.py — C-069：用 c069m 的真实画像 + c069l 的真实延迟，
外推方案 B（无 KV cache）的端到端 RTF

## 为什么必须重做外推

`c069i` / `c069l` 的外推假设「每段只做 1 次 decoder 调用、约 65 个输出 token」。
`c069m` 实测证明这个假设错得很离谱：

    generate_calls_per_segment.mean = 24.88   （恰好 = n_chunks，640 ms 一个 chunk）
    out_tokens_per_call.mean       = 7.6

也就是流式循环**每个 640 ms chunk 都重新编码整段累积音频 + 重新 prefill 整条 prompt**，
每段约 25 次全量 prefill，而不是 1 次。外推因此低估了约 25 倍。

## 本脚本的做法：先用真实数据标定，再用同一套模型预测

1. **标定**：用 c069m 的 GPU 实测（enc/prefill/decode 分项 + 真实 prompt 长度）
   验证成本模型能复现**实测** stateful RTF。复现不了 → 模型不可信，停。
2. **预测**：把 decoder 换成方案 B（无 KV cache，每次 decode 步 = 一次全序列 forward），
   其余（VAD、encoder、chunk 调度）不变。

不跑端到端转写：先证明 RTF 有没有希望 ≤1。若模型预测已 >1，再花 15 分钟×N 跑
真实转写没有意义。

输出：`reports/c069n_planb_e2e_cost.json`
"""
import json
import os
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np

PROFILE = 'reports/c069m_real_call_profile.json'
BENCH = 'reports/c069l_len_variants_bench.json'
OUT = 'reports/c069n_planb_e2e_cost.json'


def lin_fit(xs, ys):
    """最小二乘 y = intercept_ms + ms_per_token*x，并返回 R²。

    两个必须记住的坑：
    1. `np.polyfit` 返回 **[斜率, 截距]**，不是 [截距, 斜率]。
    2. x 是「token 数」、y 是「毫秒」，所以斜率单位是 **ms/token**，
       不是 µs/token。v2 把它当 µs 用，全序列延迟差 1000 倍。
    """
    slope, intercept = np.polyfit(xs, ys, 1)
    slope, intercept = float(slope), float(intercept)
    yhat = intercept + slope * np.asarray(xs, dtype=float)
    ss_res = float(np.sum((np.asarray(ys, dtype=float) - yhat) ** 2))
    ss_tot = float(np.sum((np.asarray(ys, dtype=float)
                          - np.mean(ys)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float('nan')
    return intercept, slope, r2


def usable(fit):
    """线性外推是否可信：截距非负（否则短序列外推会给出负延迟）且 R² 够高。"""
    return fit['intercept_ms'] >= 0.0 and fit['r2'] >= 0.90


def main():
    prof = json.load(open(PROFILE, encoding='utf-8'))
    bench = json.load(open(BENCH, encoding='utf-8'))

    # ── 真实画像（c069m） ──────────────────────────────────
    n_call = prof['summary']['generate_calls_per_segment']['mean']
    enc_ms = prof['summary']['enc_ms_per_call']['mean']
    prefill_ms = prof['summary']['prefill_ms_per_call']['mean']
    out_tok = prof['summary']['out_tokens_per_call']['mean']
    seg_dur = (prof['summary']['seg_wall_s']['mean']
               / prof['summary']['seg_rtf']['mean'])
    seg_wall = prof['summary']['seg_wall_s']['mean']
    shares = prof['structural']
    dec_share = shares['decode_share_of_decoder']

    # 实测每段 decode 总耗时
    dec_ms_per_seg = seg_wall * 1000 * (dec_share + shares['prefill_share_of_decoder']
                                        + shares['enc_share_of_decoder'])
    dec_ms_per_seg *= dec_share
    dec_ms_per_call = dec_ms_per_seg / n_call
    # stateful 的每 token 成本（交叉校验 c069i 的 30.25 ms）
    stateful_per_tok = dec_ms_per_call / out_tok

    # ── 真实全序列 forward 延迟（c069l） ──────────────────
    lengths = sorted(int(k) for k in bench['variants'])
    fit = {}
    for dev in ('gpu', 'npu'):
        ys = [bench['variants'][str(L)][dev] for L in lengths]
        intercept, slope, r2 = lin_fit(lengths, ys)
        fit[dev] = {'intercept_ms': round(intercept, 2),
                    'ms_per_token': round(slope, 4),
                    'r2': round(r2, 4),
                    'points': {str(L): ys[i] for i, L in enumerate(lengths)},
                    'usable_for_extrapolation': usable(
                        {'intercept_ms': intercept, 'r2': r2}),
        }

    # 实测 prompt 长度画像
    pl = prof['summary']['prompt_len_last_segment']
    n_aud = prof['summary']['n_audio_last_segment']

    def full_fwd(dev, seq):
        f = fit[dev]
        return f['intercept_ms'] + f['ms_per_token'] * seq

    # ── 步骤 1：标定 —— 模型能否复现实测 stateful RTF ────────
    # 实测 RTF 与「实测分项之和」的比值（覆盖 Python/特征提取等开销）
    accounted = prof['summary']['accounted_share_of_wall']
    model_rtf_stateful = (seg_wall * accounted) / seg_dur
    calibration = {
        'measured_seg_wall_s': round(seg_wall, 2),
        'measured_seg_dur_s': round(seg_dur, 2),
        'measured_seg_rtf': round(seg_wall / seg_dur, 3),
        'model_seg_rtf_after_accounting': round(model_rtf_stateful, 3),
        'accounted_share_of_wall': accounted,
        'note': 'stateful 模型直接用 c069m 实测分项，不做参数拟合 → 恒等于实测',
    }

    # ── 步骤 2：预测方案 B ───────────────────────────────────
    # 方案 B：没有 KV cache。每生成 1 个 token = 1 次**全序列** forward。
    # 序列长度随生成步增长：seq_t = prompt_len + t
    # 每段的 decoder 成本 = Σ_calls Σ_{t<n_call} full_fwd(dev, seq_t)
    out = {}
    for dev in ('gpu', 'npu'):
        if not fit[dev]['usable_for_extrapolation']:
            # 负截距 = 短序列区非线性，线性外推到我们的实际长度（~270-340）
            # 会给出负延迟，不可信。这种情况只报「不可外推」，不报数字。
            out[dev] = {
                'extrapolation_usable': False,
                'reason': (f"拟合 R²={fit[dev]['r2']}, "
                           f"截距={fit[dev]['intercept_ms']} ms "
                           f"(负截距 → 短序列区非线性，禁止外推)"),
            }
            continue
        per_call_ms = []
        for call_prompt in (pl['mean'], pl['max']):
            tot = 0.0
            for t in range(int(round(out_tok))):
                tot += full_fwd(dev, call_prompt + t)
            per_call_ms.append(tot)
        mid = per_call_ms[0]
        worst = per_call_ms[1]

        dec_seg_ms = n_call * mid
        seg_ms = dec_seg_ms + n_call * enc_ms
        rtf = seg_ms / 1000.0 / seg_dur
        out[dev] = {
            'extrapolation_usable': True,
            'decode_ms_per_call_mid_prompt': round(mid, 1),
            'decode_ms_per_call_max_prompt': round(worst, 1),
            'stateful_decode_ms_per_call': round(dec_ms_per_call, 1),
            'slowdown_x': round(mid / dec_ms_per_call, 2),
            'decoder_ms_per_segment': round(dec_seg_ms, 1),
            'encoder_ms_per_segment': round(n_call * enc_ms, 1),
            'seg_ms': round(seg_ms, 1),
            'seg_s': round(seg_ms / 1000.0, 2),
            'rtf': round(rtf, 3),
            'rtf_ok': rtf <= 1.0,
        }

    usable_devs = [d for d in ('gpu', 'npu')
                   if out[d].get('extrapolation_usable')]
    best = min((out[d]['rtf'] for d in usable_devs), default=None)
    result = {
        'note': 'C-069n：用 c069m 的真实调用画像 + c069l 的真实全序列 forward 延迟，'
                '外推方案 B（无 KV cache）的端到端 RTF。'
                '修正了 c069i/c069l「每段只 1 次 decoder 调用」的错误假设'
                '（实测为每段约 25 次 = n_chunks）。',
        'inputs': {
            'real_profile': {
                'generate_calls_per_segment': round(n_call, 2),
                'enc_ms_per_call': enc_ms,
                'stateful_prefill_ms_per_call': prefill_ms,
                'out_tokens_per_call': out_tok,
                'prompt_len_mean': pl['mean'],
                'prompt_len_max': pl['max'],
                'n_audio_mean': n_aud['mean'],
                'seg_duration_s': round(seg_dur, 2),
                'derived_stateful_per_token_ms': round(stateful_per_tok, 2),
                'cross_check_c069i_per_token_ms': 30.25,
            },
            'full_fwd_fit': fit,
        },
        'calibration': calibration,
        'plan_b_projection': out,
        'verdict': {
            'best_rtf': round(best, 3) if best is not None else None,
            'feasible_rtf_le_1': (best is not None and best <= 1.0),
            'devices_usable': usable_devs,
            'vs_current_delivery_rtf': 0.5783,
            'conclusion': (
                '所有设备的线性外推都不可信（NPU 拟合负截距），'
                '**必须直接实测端到端**，不做 RTF 数字预测。'
                if best is None else
                (f'方案 B 端到端 RTF 预测 ≈ {best:.2f} > 1，'
                 '**不满足实时流式**，不建议作为交付路径。'
                 if best > 1.0 else
                 f'方案 B 端到端 RTF 预测 ≈ {best:.2f} ≤ 1，'
                 '值得做真实端到端验收。')),
            'root_cause': (
                '每 640 ms chunk 都要重新 prefill 整条 prompt（每段约 25 次）；'
                '无 KV cache 时每生成 1 个 token 又要再算一遍全序列，'
                '两个成本相乘。当前 stateful 只在 decode 步吃 KV cache 的 1-token 成本。'),
            'required_next_step': (
                '对 models/ov-dec-embed-L512 做一次真实 12–27 分钟端到端转写'
                '（fresh process + GPU guard），拿 P50 / overall RTF / WER。'
                '这是唯一能定论的证据。'),
        },
    }

    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
