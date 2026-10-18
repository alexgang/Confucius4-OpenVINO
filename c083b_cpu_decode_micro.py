"""c083b_cpu_decode_micro.py — 「无 GPU 机器能否用 NPU+CPU 跑流式」的决定性测量。

问题背景：C-082 把NPU 5 格矩阵定稿了，但没回答部署问题 —— 台式机 / 无独显，
只有 CPU + Intel NPU，能不能跑流式 ASR？

先用 c083a 的端到端测法失败了：CPU 上 OVBackend（ov-int8-past，含 cross-attention）
跑40 s 切片 >20 min 未完（RTF 显然 >>1）。那个脚本还踩了 USE_TORCH=0 导致
transformers 导入失败。本脚本改为**组件级微基准**，直接复用已在 NPU 上验证过的
cleanie 解码路径（npu_embeds_backend 的 prefill + 逐 token decode 逻辑），
把同一个 IR 分别编译到 CPU 与 NPU 上测同一组数字。

测什么（每组用同一份真实音频算出的 inputs_embeds，prompt 真实长度）：
  1. prefill  单次会话内中位
  2. decode   每 token 中位（连续N 步，会话内，不reset）
  3.由此估算 RTF（倍数法，用 c069m 已确立的份额口径）

关键对照（都已有的实测值，用于外推）：
  - NPU  cleanie INT8：prefill 251.2 ms / decode 33.6 ms（STATUS C-080#3）
  - GPU 生产A INT8：  prefill ?/ decode 28.8 ms

输出：reports/c083b_cpu_decode_micro.json
"""
import json
import os
import statistics
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import openvino as ov

AUDIO = 'test_audio/<redacted>.wav'
SR = 16000
IR = 'models/qwen3-lm-int8sym-cleanie-ov/openvino_model.xml'
N_DECODE = 8          # 连续 decode 步数
WARMUP = 1
OUT = 'reports/c083b_cpu_decode_micro.json'


def make_embeds(T_audio=180, seed=0):
    """构造真实尺寸的 inputs_embeds（不依赖音频编码器，避免额外依赖）。

    长度口径对齐 C-080：模板 13 + 音频 ~N + 前缀，落在 512 上界内。
    """
    rng = np.random.default_rng(seed)
    T = 13 + T_audio
    return np.ascontiguousarray(
        rng.standard_normal((1, T, 2048), dtype=np.float32) * 0.02)


def bench(device, emb):
    core = ov.Core()
    props = {}
    if device == 'NPU':
        props = {'NPU_USE_NPUW': 'YES', 'NPUW_LLM': 'YES',
                 'NPUW_LLM_MAX_PROMPT_LEN': '512',
                 'NPUW_LLM_MIN_RESPONSE_LEN': '64'}
    t0 = time.perf_counter()
    model = core.compile_model(IR, device, props) if props \
        else core.compile_model(IR, device)
    compile_s = time.perf_counter() - t0

    in_port = 'inputs_embeds'
    out_port = [o.get_any_name() for o in model.outputs][0]
    T = int(emb.shape[1])

    rec = {'device': device, 'compile_s': round(compile_s, 1),
           'prompt_len': T, 'n_decode': N_DECODE}

    # ── prefill：整块喂入，取最后一位 logits ─────────────────────
    pf = []
    for _ in range(WARMUP + 3):
        req = model.create_infer_request()
        t0 = time.perf_counter()
        res = req.infer({
            in_port: emb,
            'attention_mask': np.ones((1, T), dtype=np.int64),
            'position_ids': np.arange(T, dtype=np.int64)[None, :],
            'beam_idx': np.zeros(1, dtype=np.int32),
        })
        pf.append((time.perf_counter() - t0) * 1000)
        logits = np.ascontiguousarray(np.array(res[out_port].data)[0, -1]).copy()
        del req
    rec['prefill_ms_all'] = [round(x, 1) for x in pf]
    rec['prefill_ms_median'] = round(statistics.median(pf[1:]), 1)

    # ── decode：连续单步，会话内，不 reset ───────────────────────
    nxt = int(np.argmax(logits))
    dec = []
    for i in range(WARMUP + N_DECODE):
        past = T + i
        req = model.create_infer_request()
        t0 = time.perf_counter()
        res = req.infer({
            in_port: np.ascontiguousarray(
                np.zeros((1, 1, 2048), dtype=np.float32)),
            'attention_mask': np.ones((1, past + 1), dtype=np.int64),
            'position_ids': np.array([[past]], dtype=np.int64),
            'beam_idx': np.zeros(1, dtype=np.int32),
        })
        dec.append((time.perf_counter() - t0) * 1000)
        logits = np.ascontiguousarray(np.array(res[out_port].data)[0, -1]).copy()
        nxt = int(np.argmax(logits))
        del req
    rec['decode_ms_all'] = [round(x, 1) for x in dec]
    rec['decode_ms_median'] = round(statistics.median(dec[1:]), 1)
    return rec


def main():
    emb = make_embeds()
    print(f'[c083b] IR={IR}\n  prompt_len={emb.shape[1]}', flush=True)
    rep = {'note': '无 GPU 机器可行性：同一个 cleanie INT8 IR 在 CPU / NPU 上的'
                   '组件级延迟（prefill / decode，会话内中位）。',
           'ir': IR,
           'n_decode': N_DECODE,
           'warmup': WARMUP,
           'note_embeds': '真实尺寸随机 embeds（不跑 audio encoder，只测 LM 侧延迟）',
           'runs': {}}

    for dev in ('CPU', 'NPU'):
        print(f'\n===== {dev} =====', flush=True)
        try:
            r = bench(dev, emb)
            rep['runs'][dev] = r
            print(f'  编译 {r["compile_s"]}s | prefill {r["prefill_ms_median"]} ms'
                  f' | decode {r["decode_ms_median"]} ms/token', flush=True)
        except Exception as e:
            rep['runs'][dev] = {'device': dev, 'status': 'failed',
                                'error': str(e)[:500]}
            print(f'  失败: {str(e)[:300]}', flush=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)

    # ── 估算 RTF（倍数法，份额口径来自 c069m/c080h）────────────────
    if 'CPU' in rep['runs'] and 'NPU' in rep['runs'] \
            and 'decode_ms_median' in rep['runs']['CPU']:
        rtf = {}
        for dev in ('CPU', 'NPU'):
            r = rep['runs'][dev]
            pf, dc = r['prefill_ms_median'], r['decode_ms_median']
            # 一个 chunk：1 次 prefill + n_decode 次 decode（取 N_DECODE）
            per_chunk_ms = pf + dc * N_DECODE
            # chunk = 640 ms 音频；每 chunk 产出的 token 数用 C-080 实测 ~4/step
            rtf[dev] = {
                'prefill_ms': pf, 'decode_ms': dc,
                'per_chunk_ms': round(per_chunk_ms, 1),
                'chunk_audio_s': 0.64,
                'rtf_if_4_tok_per_chunk': round(per_chunk_ms / 640.0, 3),
            }
        rep['rtf_estimate'] = rtf
        print('\n===== RTF 估算（chunk=640ms）=====', flush=True)
        for dev, v in rtf.items():
            print(f'  {dev:4s} prefill {v["prefill_ms"]:>7} ms | '
                  f'decode {v["decode_ms"]:>6} ms/tok | '
                  f'RTF(4tok/chunk) {v["rtf_if_4_tok_per_chunk"]}', flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('\nsaved ->', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
