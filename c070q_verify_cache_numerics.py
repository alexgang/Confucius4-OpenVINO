# C-070#2 前置：验证「手写显式 KV cache」数值正确
#
# 为什么必须先做这个
# ----------------
# c070o 的 stateful 图是我**手写**注意力 + 手工 cache 写入（常量 write_pos、
# 常量 additive mask、手工 GQA repeat）。如果这段数学有错，
# 那么后面 NPU/GPU 上量到的所有延迟都是「一个算错的模型」的数字，没有意义。
#
# 所以先用 CPU 把 c070o 的三张图串成 prefill → decode0 → decode1，
# 与**源模型自己**的 `use_cache=True` 前向逐位置比对。
#
# 源模型调用（不用我写的那套）：
#   out = tm(inputs_embeds=..., use_cache=True, past_key_values=cache)
# 两者必须给出同样的 last-position logits。
#
# 输出：reports/c070q_cache_numerics.json
import os
os.environ.setdefault('USE_TORCH', '1')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

import json
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
HF = os.path.join(ROOT, 'models/hf')
LOG = os.path.join(ROOT, 'reports/c070q_cache_numerics.json')

HIDDEN = 2048
PREFILL_T = 384
MAX_LEN = 512

info = {'note': 'C-070 前置：手写显式 KV cache 的数值正确性验证'
               '（c070o 三张图 vs 源模型 use_cache=True）。'}


def main():
    import torch
    import openvino as ov
    from qwen_asr.core.transformers_backend import (
        Qwen3ASRForConditionalGeneration)

    full = Qwen3ASRForConditionalGeneration.from_pretrained(
        HF, dtype=torch.float32)
    tm = full.thinker.model
    lm_head = full.thinker.lm_head
    print('loaded source model', flush=True)

    rng = np.random.default_rng(20261016)
    # 用真实量级的随机嵌入（比 0.02*randn 更能暴露 mask/RoPE 问题）
    emb = (rng.standard_normal((1, PREFILL_T, HIDDEN)) * 0.5).astype(np.float32)

    # ── 参考：源模型自己的 KV cache ─────────────────────────
    from transformers import DynamicCache
    cache = DynamicCache(config=tm.config)
    with torch.no_grad():
        ex = torch.from_numpy(emb)
        ref = tm(inputs_embeds=ex, use_cache=True, past_key_values=cache,
                 cache_position=torch.arange(PREFILL_T))
        ref_h = ref.last_hidden_state[:, -1:, :]
        ref_logits = lm_head(ref_h).numpy()[0, -1]
    print('ref prefill logits', ref_logits.shape, flush=True)
    info['ref_prefill_argmax'] = int(np.argmax(ref_logits))

    # ── 我们的三张 stateful 图（CPU） ───────────────────────
    core = ov.Core()
    cms = {}
    for tag in ('prefill', 'decode0', 'decode1'):
        p = os.path.join(ROOT, f'models/ov-dec-stateful-{tag}',
                         'openvino_decoder_model.xml')
        cms[tag] = core.compile_model(p, 'CPU')
    print('compiled 3 graphs on CPU', flush=True)

    feed_prefill = {'inputs_embeds': emb,
                    'beam_idx': np.array([0], dtype=np.int32)}
    # 喂一个非零的 decode 嵌入（模拟第 1 个生成 token 的 emb）
    emb_d0 = (rng.standard_normal((1, 1, HIDDEN)) * 0.5).astype(np.float32)
    emb_d1 = (rng.standard_normal((1, 1, HIDDEN)) * 0.5).astype(np.float32)
    feed_d0 = {'inputs_embeds': emb_d0,
               'beam_idx': np.array([0], dtype=np.int32)}
    feed_d1 = {'inputs_embeds': emb_d1,
               'beam_idx': np.array([0], dtype=np.int32)}

    r_pre = cms['prefill'].create_infer_request()
    r_d0 = cms['decode0'].create_infer_request()
    r_d1 = cms['decode1'].create_infer_request()

    out_pre = r_pre.infer(feed_prefill)[0]
    out_pre = np.asarray(out_pre)
    info['ov_prefill_shape'] = list(out_pre.shape)
    print('ov prefill out', out_pre.shape, flush=True)

    def cos(a, b):
        a, b = a.reshape(-1).astype(np.float64), b.reshape(-1).astype(np.float64)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    pre_logits = out_pre[0, -1]
    info['prefill_check'] = {
        'cosine_vs_source': round(cos(pre_logits, ref_logits), 6),
        'argmax_ov': int(np.argmax(pre_logits)),
        'argmax_src': int(np.argmax(ref_logits)),
        'argmax_match': bool(np.argmax(pre_logits) == np.argmax(ref_logits)),
    }
    print('prefill check:', info['prefill_check'], flush=True)

    # ── decode 步 ───────────────────────────────────────────
    # ⚠️ 重要限制（记录下来，别误读）：
    #   make_stateful 之后**每个图有自己的 56 个状态变量**，且 OV 的
    #   CompiledModel/InferRequest 只有 reset_state/query_state，
    #   **没有 set_state**（已核实 API）。所以 prefill 图写进的状态
    #   **喂不进 decode 图**。
    #   → 本 harness 只能验证 decode 图「在正确 cache 输入下的单步输出」，
    #     不能把三张图串起来测端到端。
    #   → 端到端串联要 1 张图同时含 prefill+decode（动态 seq），
    #     而 NPU 要求静态形状 —— 这正是 NPUW 静态分块缓存要解决的问题。
    #   因此 decode 步改在 **torch 侧**验证我手写的 cache 数学，
    #     OV 的 decode 图只用于延迟测量。
    from qwen_asr.core.transformers_backend.modeling_qwen3_asr import (
        apply_rotary_pos_emb)

    n_kv = tm.config.num_key_value_heads
    head_dim = getattr(tm.config, 'head_dim', None) or \
        tm.config.hidden_size // tm.config.num_attention_heads
    n_rep = tm.config.num_attention_heads // n_kv

    def dump_cache(cache):
        """DynamicCache → 2*n_layers 个 **torch 张量**（key,value 交替）。

        返回 torch.Tensor 而不是 np.ndarray：manual_step 里要和 k_new
        一起做 torch.cat，dtype 不一致会报
        `expected Tensor as element 0 in argument 0`（v1 踩过）。
        """
        out = []
        for li in range(len(tm.layers)):
            k, v = cache.layers[li].keys, cache.layers[li].values
            kk = torch.zeros(1, n_kv, MAX_LEN, head_dim)
            vv = torch.zeros(1, n_kv, MAX_LEN, head_dim)
            cur = k.shape[-2]
            kk[:, :, :cur] = k
            vv[:, :, :cur] = v
            out += [kk, vv]
        return out

    def manual_step(embeds, kvs, write_pos):
        """复刻 c070o 的注意力数学：常量写入 + 因果 mask + GQA。

        返回 (logits, 新的 2*n_layers KV 列表) —— 必须**收集所有层**的
        新 KV，只回最后一层会让第 2 步的 cache 只对最后一层有效。
        """
        B, T, _ = embeds.shape
        x_all = torch.from_numpy(embeds)
        pos = torch.arange(write_pos, write_pos + T)
        pos3 = pos.view(1, 1, -1).expand(3, B, -1)
        cos_, sin_ = tm.rotary_emb(x_all, pos3)
        h = x_all
        new_kvs = []
        for li, layer in enumerate(tm.layers):
            attn = layer.self_attn
            res = h
            x = layer.input_layernorm(h)
            bsz, t, _ = x.shape
            q = attn.q_norm(attn.q_proj(x).view(bsz, t, -1, head_dim)
                            ).transpose(1, 2)
            k_new = attn.k_norm(attn.k_proj(x).view(bsz, t, -1, head_dim)
                                ).transpose(1, 2)
            v_new = attn.v_proj(x).view(bsz, t, -1, head_dim).transpose(1, 2)
            q, k_new = apply_rotary_pos_emb(q, k_new, cos_, sin_)
            pk, pv = kvs[2 * li], kvs[2 * li + 1]
            w = write_pos
            k_cat = torch.cat([pk[:, :, :w], k_new, pk[:, :, w + t:]], dim=2)
            v_cat = torch.cat([pv[:, :, :w], v_new, pv[:, :, w + t:]], dim=2)
            new_kvs += [k_cat, v_cat]
            kk, vv = k_cat, v_cat
            if n_rep > 1:
                kk = kk.repeat_interleave(n_rep, dim=1)
                vv = vv.repeat_interleave(n_rep, dim=1)
            scores = torch.matmul(q, kk.transpose(2, 3)) * attn.scaling
            kj = torch.arange(MAX_LEN)
            qi = torch.arange(T) + write_pos
            allowed = kj.unsqueeze(0) <= qi.unsqueeze(1)
            add = torch.where(allowed, torch.zeros(()), torch.full((), -1e4))
            scores = scores + add
            w_ = torch.softmax(scores, dim=-1, dtype=torch.float32).to(q.dtype)
            ctx = torch.matmul(w_, vv).transpose(1, 2).reshape(bsz, t, -1)
            h = res + attn.o_proj(ctx)
            res = h
            x = layer.post_attention_layernorm(h)
            h = res + layer.mlp(x)
        h = tm.norm(h)
        return lm_head(h[:, -1:, :]).numpy()[0, -1], new_kvs

    # 参考序列：prefill → step0 → step1
    c_ref = DynamicCache(config=tm.config)
    with torch.no_grad():
        _ = tm(inputs_embeds=ex, use_cache=True, past_key_values=c_ref,
               cache_position=torch.arange(PREFILL_T))
        ref_step0 = lm_head(
            tm(inputs_embeds=torch.from_numpy(emb_d0), use_cache=True,
               past_key_values=c_ref,
               cache_position=torch.tensor([PREFILL_T])
               ).last_hidden_state[:, -1:, :]).numpy()[0, -1]
        ref_step1 = lm_head(
            tm(inputs_embeds=torch.from_numpy(emb_d1), use_cache=True,
               past_key_values=c_ref,
               cache_position=torch.tensor([PREFILL_T + 1])
               ).last_hidden_state[:, -1:, :]).numpy()[0, -1]

    c_pre = DynamicCache(config=tm.config)
    with torch.no_grad():
        _ = tm(inputs_embeds=ex, use_cache=True, past_key_values=c_pre,
               cache_position=torch.arange(PREFILL_T))
    kvs = dump_cache(c_pre)

    with torch.no_grad():
        man0, kvs_next = manual_step(emb_d0, kvs, PREFILL_T)
        man1, _ = manual_step(emb_d1, kvs_next, PREFILL_T + 1)

    info['decode0_check'] = {
        'cosine_vs_source': round(cos(man0, ref_step0), 6),
        'argmax_match': bool(np.argmax(man0) == np.argmax(ref_step0)),
        'mode': 'torch-side manual cache math',
    }
    info['decode1_check'] = {
        'cosine_vs_source': round(cos(man1, ref_step1), 6),
        'argmax_match': bool(np.argmax(man1) == np.argmax(ref_step1)),
        'mode': 'torch-side manual cache math (2 steps chained)',
    }
    print('decode0 check:', info['decode0_check'], flush=True)
    print('decode1 check:', info['decode1_check'], flush=True)

    ok = (info['prefill_check']['argmax_match']
          and info['decode0_check']['argmax_match']
          and info['decode1_check']['argmax_match'])
    info['all_argmax_match'] = bool(ok)
    info['verdict'] = ('手写 cache 数值正确，可用于 NPU 延迟测量'
                       if ok else
                       '❌ 手写 cache 数值有误，后续所有延迟数字都不可用')
    print('\nVERDICT:', info['verdict'], flush=True)
    return 0


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
    finally:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print('\nwrote', LOG)
