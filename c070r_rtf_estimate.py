"""c070r_rtf_estimate.py — C-070/C-071：用倍数法估端到端 RTF

reviewer 指定的估法（不用 token 数绝对外推）：
    「用你的倍数法估端到端 RTF（prefill 25.2%、decode 57.7%、encoder 17.2%）」

倍数法：RTF_new = RTF_baseline × Σ(share_i × ratio_i)
  - share_i  = c069m 实测的各环节时间占比（decode 57.7% / prefill 25.2% / enc 17.2%）
  - ratio_i  = NPU 该环节延迟 / GPU 同环节基线
  - encoder 在 NPU 上另有实测（c069d：47.68 / 31.70 = 1.504）

输出：reports/c070r_rtf_estimate.json
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'reports/c070r_rtf_estimate.json')

# c069m 实测：各环节时间占比
SHARE = {'decode': 0.577, 'prefill': 0.252, 'encoder': 0.172}
# C-070 实测延迟（ms，≥20 次中位数）
NPU = {'prefill': 137.44, 'decode': 75.96}
# GPU 生产 stateful 基线（c069m）
GPU_STATEFUL = {'prefill': 94.0, 'decode': 28.8}
# encoder：c069d 生产 encoder 实测
GPU_ENC, NPU_ENC = 31.70, 47.68
# 当前交付基线 RTF（ABBA 配置 A）
RTF_BASE = 0.5783

info = {
    'note': 'C-070/C-071 倍数法 RTF 估计。share 来自 c069m 实测画像，'
            'ratio 来自 c070p（prefill/decode）与 c069d（encoder）实测。',
    'shares': SHARE,
    'measured_ms': {'gpu_stateful': GPU_STATEFUL, 'npu': NPU,
                    'encoder': {'gpu': GPU_ENC, 'npu': NPU_ENC}},
    'rtf_baseline': RTF_BASE,
}


def estimate(npu_prefill, npu_decode, label):
    r = {
        'prefill': npu_prefill / GPU_STATEFUL['prefill'],
        'decode': npu_decode / GPU_STATEFUL['decode'],
        'encoder': NPU_ENC / GPU_ENC,
    }
    factor = (SHARE['prefill'] * r['prefill']
              + SHARE['decode'] * r['decode']
              + SHARE['encoder'] * r['encoder'])
    return {
        'label': label,
        'ratios': {k: round(v, 3) for k, v in r.items()},
        'weighted_factor': round(factor, 3),
        'rtf': round(RTF_BASE * factor, 3),
        'rtf_ok': RTF_BASE * factor <= 1.0,
    }


info['scenarios'] = [
    estimate(NPU['prefill'], NPU['decode'], 'NPU plain（实测）'),
    estimate(NPU['prefill'], GPU_STATEFUL['decode'],
             '假设 decode 能做到与 GPU 持平（乐观下界）'),
    estimate(GPU_STATEFUL['prefill'], NPU['decode'],
             '假设 prefill 做到与 GPU 持平（只换 decode）'),
]
best = min(info['scenarios'], key=lambda s: s['rtf'])
measured = info['scenarios'][0]
decode_parity = next(s for s in info['scenarios'] if 'decode 能做到' in s['label'])
info['verdict'] = {
    'measured_rtf': measured['rtf'],
    'measured_rtf_ok': measured['rtf_ok'],
    'decode_parity_rtf': decode_parity['rtf'],
    'best_rtf': best['rtf'],
    'feasible_rtf_le_1': any(s['rtf_ok'] for s in info['scenarios']),
    'conclusion': (
        f"当前实测（NPU plain、无 NPUW）RTF ≈ {measured['rtf']} > 1，"
        f"**不满足实时流式**；瓶颈是 decode（{measured['ratios']['decode']}×）。"
        f"若 decode 能压到与 GPU 持平，RTF 可降到 {decode_parity['rtf']} ≤ 1 —— "
        f"**decode 是唯一决定性环节**。"),
    'caveat': (
        '本估计基于**我手写的 stateful 导出**（静态 cache 恒扫 512 槽、'
        '额外 170 个 Gather）。它不等于 NPUW LLM 分块缓存流水线，'
        '而 NPUW_LLM 在本图上编译失败（见 c070p），'
        '因此**无法测到 NPUW 真正的 prefill 分块收益**。'
        '这些数字只能说明「当前这条无 NPUW 的路走不通」，'
        '不能说明 NPUW 一定不行。'),
}

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(info, f, ensure_ascii=False, indent=2)
print(json.dumps(info, ensure_ascii=False, indent=2))
