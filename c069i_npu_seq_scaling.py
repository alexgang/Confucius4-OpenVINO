# C-066 阶段 3 · 关键问题：编解码**全部**上 NPU 可行吗？
#
# 核心矛盾：
#   现有生产解码器是 stateful（KV cache）：prefill 425 tok 一次，之后每步只算 1 tok。
#   方案 B 导出的 inputs_embeds 版**无 KV cache**：每生成 1 个 token 都要重算整条 512 序列。
#   → 若无 cache 的单步成本远高于 1-token 解码，端到端 RTF 会爆炸。
#
# 本脚本用实测回答，不靠推断：
#   1) 同一模型上量「不同序列长度」的单次推理延迟（NPU vs GPU）
#   2) 据此推算端到端 RTF，与现有 GPU stateful 基线（0.5783）对比
import os
os.environ['USE_TORCH'] = '0'
os.environ['USE_TF'] = '0'
os.environ['USE_FLAX'] = '0'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

import json
import time
import numpy as np
import openvino as ov

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, 'reports/npu_cache')
OUT = os.path.join(ROOT, 'reports/c069i_npu_seq_scaling.json')
IR = os.path.join(ROOT, 'models/ov-dec-embed-fp16/openvino_decoder_model.xml')
STATEFUL_IR = os.path.join(ROOT, 'models/ov-int8-past/openvino_decoder_model.xml')

H = 2048
VOCAB = 151936
LENS = (128, 256, 512)


def median_ms(fn, warmup=3, reps=10):
    for _ in range(warmup):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return round(ts[len(ts) // 2], 2)


def main():
    core = ov.Core()
    core.set_property({'CACHE_DIR': CACHE})
    res = {'note': ('量化「编解码全部上 NPU」的可行性：inputs_embeds 版无 KV cache，'
                    '单步成本随序列长度线性增长。本脚本实测延迟-长度曲线并外推端到端 RTF。'),
           'lens': list(LENS)}

    # ── A. 方案 B（inputs_embeds，静态 512）只能跑固定长度 ────────────
    # 它是静态图，只能测 512。但我们用「填充不同有效长度」看是否可复用同一图 ——
    # 静态图下填充不影响计算量，所以只测 512。
    res['plan_b'] = {}
    for tag, dev, props in (
        ('gpu', 'GPU', {'PERFORMANCE_HINT': 'LATENCY',
                        'INFERENCE_PRECISION_HINT': 'f16'}),
        ('npu', 'NPU', {'CACHE_DIR': CACHE}),
    ):
        try:
            cm = core.compile_model(IR, dev, props)
            x = np.zeros((1, 512, H), dtype=np.float32)
            res['plan_b'][tag] = median_ms(lambda: cm([x]))
            print(f'plan_b {tag}: {res["plan_b"][tag]} ms @512', flush=True)
        except Exception as e:
            res['plan_b'][tag] = {'error': str(e)[:600]}
            print(f'plan_b {tag}: FAILED {str(e)[:150]}', flush=True)

    # ── B. 现有 stateful 解码器：prefill vs 1-token decode 步 ──────────
    # 这是关键对照：它有 KV cache，能真正做增量解码。
    res['stateful_gpu'] = {}
    try:
        cm = core.compile_model(STATEFUL_IR, 'GPU', {
            'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f16'})
        req = cm.create_infer_request()

        # prefill：完整 prompt 约 425 token
        pf_ehs = np.zeros((1, 312, 2048), dtype=np.float32)
        pf_ids = np.zeros((1, 425), dtype=np.int64)
        pf_bm = np.array([0], dtype=np.int32)
        req.reset_state()
        req.infer({'encoder_hidden_states': pf_ehs, 'input_ids': pf_ids,
                   'beam_idx': pf_bm})

        def do_pf():
            req.reset_state()
            req.infer({'encoder_hidden_states': pf_ehs, 'input_ids': pf_ids,
                       'beam_idx': pf_bm})

        res['stateful_gpu']['prefill_425_ms'] = median_ms(do_pf, warmup=2, reps=5)

        # decode 步：只喂 1 个 token（KV 已在图内状态里）
        d_ehs = np.zeros((1, 1, 2048), dtype=np.float32)
        d_ids = np.array([[1]], dtype=np.int64)

        def do_dec():
            req.infer({'encoder_hidden_states': d_ehs, 'input_ids': d_ids,
                       'beam_idx': pf_bm})

        res['stateful_gpu']['decode_1tok_ms'] = median_ms(do_dec, warmup=3, reps=20)
        print(f"stateful GPU: prefill(425)={res['stateful_gpu']['prefill_425_ms']}ms "
              f"decode(1tok)={res['stateful_gpu']['decode_1tok_ms']}ms", flush=True)
    except Exception as e:
        res['stateful_gpu'] = {'error': f'{type(e).__name__}: {e}'[:800]}
        print('stateful GPU FAILED:', str(e)[:200], flush=True)

    # ── C. 端到端外推 ────────────────────────────────────────────────
    # 实测基线（ABBA 第一轮）：900 s 音频 / 55 段 / 523.8 s wall, RTF 0.582
    # 平均段长 16.36 s，平均每段输出词数 2733/55 ≈ 49.7 词 ≈ 约 65 token。
    AVG_SEG_SEC = 16.36
    AVG_OUT_TOK = 65
    PROMPT = 425

    dec_1tok = res['stateful_gpu'].get('decode_1tok_ms')
    pf = res['stateful_gpu'].get('prefill_425_ms')
    planb = res['plan_b'].get('npu')
    planb_gpu = res['plan_b'].get('gpu')

    proj = {}
    if isinstance(dec_1tok, (int, float)) and isinstance(pf, (int, float)):
        seg_ms = pf + AVG_OUT_TOK * dec_1tok
        proj['current_gpu_stateful'] = {
            'per_seg_ms': round(seg_ms, 1),
            'rtf': round(seg_ms / 1000 / AVG_SEG_SEC, 4),
            'note': 'KV cache：prefill 一次 + 每 token 1 步',
        }
    if isinstance(planb, (int, float)):
        seg_ms = pf + AVG_OUT_TOK * planb if isinstance(pf, (int, float)) \
            else AVG_OUT_TOK * planb
        proj['plan_b_npu_no_cache'] = {
            'per_seg_ms': round(seg_ms, 1),
            'rtf': round(seg_ms / 1000 / AVG_SEG_SEC, 4),
            'note': ('无 KV cache：每个输出 token 都要重算整条 512 序列 '
                     f'({planb} ms)'),
        }
    if isinstance(planb_gpu, (int, float)) and isinstance(pf, (int, float)):
        seg_ms = pf + AVG_OUT_TOK * planb_gpu
        proj['plan_b_gpu_no_cache'] = {
            'per_seg_ms': round(seg_ms, 1),
            'rtf': round(seg_ms / 1000 / AVG_SEG_SEC, 4),
            'note': '同样无 cache，跑在 GPU 上',
        }
    if 'plan_b_npu_no_cache' in proj and 'current_gpu_stateful' in proj:
        a = proj['current_gpu_stateful']['rtf']
        b = proj['plan_b_npu_no_cache']['rtf']
        proj['regression_factor'] = round(b / a, 2) if a else None
        proj['verdict'] = (
            'inputs_embeds 无 cache 版端到端 RTF 比现有 GPU stateful 基线差 '
            f'{b/a:.1f}× —— 不可用作交付方案，只能作为可行性验证'
            if a and b / a > 2 else '可接受')
    proj['assumptions'] = {
        'avg_seg_sec': AVG_SEG_SEC, 'avg_out_tokens': AVG_OUT_TOK,
        'prompt_len': PROMPT,
        'measured_baseline_rtf': 0.582,
        'measured_baseline_wall_s': 523.8,
    }
    res['projection'] = proj
    print('\nprojection:', json.dumps(proj, ensure_ascii=False, indent=2),
          flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
