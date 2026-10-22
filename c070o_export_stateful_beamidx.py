# C-070 步骤 1：导出 **stateful + beam_idx** 的 inputs_embeds 解码器
#
# 目标（reviewer C-070#1）：让 NPUW 的 `StatefulToStateless` 能识别本模型，
# 从而走静态 KV 分块缓存路径。之前方案 B 失败的唯一原因是**缺 beam_idx**。
#
# 设计要点
# --------
# 1. **不构造标准 Qwen3ForCausalLM**，直接用源模块 thinker.model + thinker.lm_head
#    （沿用 c069g 的结论：结构 100% 保真、零权重重映射）。
# 2. **自己实现带显式 KV cache 的 forward**，把 past_key/past_value 显式做成
#    输入/输出张量，再交给 optimum 的 `fuse_cache_reorder`（加 beam_idx + Gather）
#    与 `make_stateful`（把 KV in/out 变成 ReadValue/Assign 变量）。
#    这是 optimum `-with-past` 导出的标准做法。
# 3. **静态 cache + 常量写入位置**：cache 固定 512 槽，写入位置 `write_pos`
#    是**导出期常量**（Python int），用常量切片拼装 → 全静态形状，
#    且**不是滑窗近似**（`cat([past[:w], new, past[w+1:]])`）。
# 4. **常量 additive mask**：未写入的槽必须屏蔽，否则 K=0 会让 softmax 拿到
#    exp(0)=1 的权重而污染结果。mask 随 write_pos 一起烘成常量。
# 5. **RoPE 绝对位置**也按 write_pos 烘成常量，保证多步解码位置正确。
#
# 导出三张图：
#   prefill : T=384, write_pos=0     （写满 0..383）
#   decode0 : T=1,   write_pos=384   （第 1 个生成 token）
#   decode1 : T=1,   write_pos=385   （第 2 个生成 token，用于验证多步正确性）
#
# 本脚本只导出+自检，不计时。按 C-069 启用 torch，绝不与计时作业并发。
import os
os.environ.setdefault('USE_TORCH', '1')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

import json
import time
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
HF = os.path.join(ROOT, 'models/hf')
LOG = os.path.join(ROOT, 'reports/c070o_export_stateful_beamidx.json')

HIDDEN = 2048
MAX_LEN = 512          # 静态 cache 槽数
PREFILL_T = 384        # 实测 prompt 最长 339，取 384 向上够用
NEG = -1e4             # additive mask 的屏蔽值（fp16/fp32 都安全）

info = {
    'note': ('C-070#1：导出 stateful + beam_idx 的 inputs_embeds 解码器。'
             '显式 KV cache → fuse_cache_reorder(beam_idx) → make_stateful。'
             '静态 cache(512) + 导出期常量写入位置，非滑窗近似。'),
    'config': {'hidden': HIDDEN, 'max_len': MAX_LEN, 'prefill_T': PREFILL_T},
    'graphs': [],
    'steps': [],
}


def step(name, fn):
    t0 = time.time()
    try:
        r = fn()
        info['steps'].append({'name': name, 'ok': True,
                              'seconds': round(time.time() - t0, 1),
                              'detail': str(r)[:1200]})
        print(f'[OK] {name} ({time.time()-t0:.1f}s) {str(r)[:300]}', flush=True)
        return r
    except Exception as e:
        info['steps'].append({'name': name, 'ok': False,
                              'seconds': round(time.time() - t0, 1),
                              'error': f'{type(e).__name__}: {e}'[:2500],
                              'tb': traceback.format_exc()[-1500:]})
        print(f'[FAIL] {name}: {type(e).__name__}: {str(e)[:500]}', flush=True)
        raise


def main():
    import torch
    import torch.nn as nn
    import openvino as ov
    from optimum.exporters.openvino.stateful import (
        fuse_cache_reorder, make_stateful)
    from qwen_asr.core.transformers_backend import (
        Qwen3ASRForConditionalGeneration)

    full = step('load_full_asr',
                lambda: Qwen3ASRForConditionalGeneration.from_pretrained(
                    HF, dtype=torch.float32))
    thinker = full.thinker
    tm = thinker.model
    lm_head = thinker.lm_head
    cfg = tm.config
    info['modules'] = {
        'text_model': type(tm).__name__, 'lm_head': type(lm_head).__name__,
        'n_layers': len(tm.layers), 'hidden': cfg.hidden_size,
        'vocab': cfg.vocab_size,
    }
    print('  modules:', info['modules'], flush=True)

    n_layers = len(tm.layers)
    n_kv_heads = cfg.num_key_value_heads
    n_heads = cfg.num_attention_heads
    head_dim = getattr(cfg, 'head_dim', None) or cfg.hidden_size // n_heads
    info['modules'].update({'n_kv_heads': n_kv_heads, 'n_heads': n_heads,
                            'head_dim': head_dim})
    print('  kv/head:', info['modules'], flush=True)

    class StatefulEmbedDecoder(nn.Module):
        """inputs_embeds + 显式 past_key/past_value → logits + 新 past。

        `write_pos` 是**导出期常量**，决定新 KV 写进 cache 的哪一槽，
        同时决定 RoPE 的绝对位置与 additive mask。这样每张图都是纯静态形状，
        且语义精确（不是滑窗近似）。
        """

        def __init__(self, tm, head, n_layers, n_kv_heads, head_dim,
                     max_len, write_pos, seq_len):
            super().__init__()
            self.tm, self.head = tm, head
            self.n_layers = n_layers
            self.n_kv_heads = n_kv_heads
            self.head_dim = head_dim
            self.max_len = max_len
            self.write_pos = write_pos
            self.seq_len = seq_len

        def forward(self, inputs_embeds, *kv):
            # kv 是 2*n_layers 个张量，交替 past_key0, past_value0, past_key1...
            assert len(kv) == 2 * self.n_layers, (
                f'expected {2*self.n_layers} kv tensors, got {len(kv)}')
            past_key = kv[0::2]
            past_value = kv[1::2]

            tm = self.tm
            B, T, _ = inputs_embeds.shape

            # 绝对位置：write_pos .. write_pos+T-1（常量）
            pos = torch.arange(self.write_pos, self.write_pos + T,
                               dtype=torch.long)
            # rotary_emb 需要 [3, B, T] 的 position_ids（源模型 expand(3,...)）
            pos3 = pos.view(1, 1, -1).expand(3, B, -1)
            cos, sin = tm.rotary_emb(inputs_embeds, pos3)

            from qwen_asr.core.transformers_backend.modeling_qwen3_asr import (
                apply_rotary_pos_emb)

            h = inputs_embeds
            new_keys, new_values = [], []
            n_rep = n_heads // n_kv_heads

            for li, layer in enumerate(tm.layers):
                attn = layer.self_attn
                residual = h
                x = layer.input_layernorm(h)
                bsz, t, _ = x.shape
                q = attn.q_norm(attn.q_proj(x).view(bsz, t, -1, head_dim)
                                ).transpose(1, 2)
                k_new = attn.k_norm(attn.k_proj(x).view(bsz, t, -1, head_dim)
                                    ).transpose(1, 2)
                v_new = attn.v_proj(x).view(bsz, t, -1, head_dim).transpose(1, 2)

                q, k_new = apply_rotary_pos_emb(q, k_new, cos, sin)

                # 写入常量位置 write_pos（精确，非滑窗）
                if T == self.max_len or self.write_pos + T <= self.max_len:
                    w = self.write_pos
                    k_cat = torch.cat(
                        [past_key[li][:, :, :w], k_new,
                         past_key[li][:, :, w + T:]], dim=2)
                    v_cat = torch.cat(
                        [past_value[li][:, :, :w], v_new,
                         past_value[li][:, :, w + T:]], dim=2)
                else:
                    raise ValueError('write overflow')

                k = k_cat
                v = v_cat
                # GQA: 扩展 kv 头
                if n_rep > 1:
                    k = k.repeat_interleave(n_rep, dim=1)
                    v = v.repeat_interleave(n_rep, dim=1)

                scores = torch.matmul(q, k.transpose(2, 3)) * attn.scaling
                # 常量 additive mask，一个 `where` 同时管两件事：
                #  (1) 屏蔽未写入的 cache 槽 —— 否则 K=0 会让 softmax 拿到
                #      exp(0)=1 的权重而污染结果；
                #  (2) 屏蔽未来位置（query i 不能看 j>i）—— **prefill 必须是
                #      因果掩码**。v1 只做了 (1)，prefill 变成双向注意力，
                #      cosine 掉到 0.958、decode 步直接错（见 c070q 报告）。
                #      v2 用 `mask[..., bool_tensor] = NEG` 又炸在
                #      `OpConversionFailure`（布尔索引不可导出），
                #      v3 改成 torch.where —— 纯张量运算，可导出。
                kj = torch.arange(self.max_len)
                qi = torch.arange(T) + self.write_pos
                allowed = kj.unsqueeze(0) <= qi.unsqueeze(1)   # [T, max_len]
                add = torch.where(
                    allowed,
                    torch.zeros((), dtype=scores.dtype),
                    torch.full((), NEG, dtype=scores.dtype))
                scores = scores + add
                w_ = torch.softmax(scores, dim=-1, dtype=torch.float32
                                   ).to(q.dtype)
                ctx = torch.matmul(w_, v).transpose(1, 2).reshape(bsz, t, -1)
                h = residual + attn.o_proj(ctx)

                residual = h
                x = layer.post_attention_layernorm(h)
                h = residual + layer.mlp(x)

                new_keys.append(k_cat)
                new_values.append(v_cat)

            h = tm.norm(h)
            logits = self.head(h[:, -1:, :])
            return (logits, *new_keys, *new_values)

    def make_and_convert(tag, seq_len, write_pos):
        net = StatefulEmbedDecoder(tm, lm_head, n_layers, n_kv_heads,
                                   head_dim, MAX_LEN, write_pos,
                                   seq_len).eval()
        ex = torch.zeros(1, seq_len, HIDDEN, dtype=torch.float32)
        ex[:, :min(8, seq_len), :] = torch.randn(
            min(8, seq_len), HIDDEN) * 0.02
        pkv = [torch.zeros(1, n_kv_heads, MAX_LEN, head_dim)
               for _ in range(2 * n_layers)]
        args = (ex, *pkv)

        # 先用 eager 跑一次，确认数值路径通；这里**不要 suppress**，
        # 否则真实报错会被吞掉，只剩一个 UnboundLocalError（v1 踩过）。
        with torch.no_grad():
            out = net(*args)
        print(f'  [{tag}] torch forward ok, out0={tuple(out[0].shape)}',
              flush=True)

        ep = torch.export.export(net, args)
        ovm = ov.convert_model(ep)
        # torch.export 默认给动态维；NPU 必须静态
        shape_map = {ovm.input(0): ov.PartialShape([1, seq_len, HIDDEN])}
        for i in range(2 * n_layers):
            shape_map[ovm.input(1 + i)] = ov.PartialShape(
                [1, n_kv_heads, MAX_LEN, head_dim])
        ret = ovm.reshape(shape_map)
        ovm = ret if ret is not None else ovm
        return ovm, net, ex, pkv

    graphs = {}
    for tag, T, wp in (('prefill', PREFILL_T, 0),
                       ('decode0', 1, PREFILL_T),
                       ('decode1', 1, PREFILL_T + 1)):
        def _one(tag=tag, T=T, wp=wp):
            ovm, net, ex, pkv = make_and_convert(tag, T, wp)
            return ovm
        graphs[tag] = step(f'export_{tag}', _one)

    # ── fuse_cache_reorder + make_stateful ────────────────────────
    def _stateful(tag):
        ovm = graphs[tag]
        # torch.export 把 2*n_layers 个 KV 张量命名成 kv_0..kv_{2L-1}，
        # 必须**先重命名**成 past_key.{li} / past_value.{li}，
        # 否则 fuse_cache_reorder / make_stateful 按名字找不到端口。
        kv_in, kv_out = [], []
        for li in range(n_layers):
            kv_in += [f'past_key.{li}', f'past_value.{li}']
            kv_out += [f'present_key.{li}', f'present_value.{li}']
        for idx, nm in enumerate(kv_in):
            ovm.input(1 + idx).get_tensor().set_names({nm})
        for idx, nm in enumerate(kv_out):
            ovm.output(1 + idx).get_tensor().set_names({nm})
        ovm.validate_nodes_and_infer_types()
        got_in = [ovm.input(nm).get_any_name() for nm in kv_in]
        got_out = [ovm.output(nm).get_any_name() for nm in kv_out]
        assert got_in == kv_in, f'rename in failed: {got_in[:3]}'
        assert got_out == kv_out, f'rename out failed: {got_out[:3]}'

        # `not_kv_inputs` 是**节点对象**（optimum 内部会调 get_partial_shape /
        # set_partial_shape，并原地 append beam_idx 节点），不是字符串。
        # 与 optimum 一致：同一个 list 先过 fuse_cache_reorder 再过 make_stateful，
        # 这样 beam_idx 节点会一起进入 make_stateful 的定形流程。
        not_kv_inputs = [ovm.input(0)]
        fuse_cache_reorder(
            ovm,
            not_kv_inputs=not_kv_inputs,
            key_value_input_names=kv_in,
            gather_dim=0,          # batch 维（greedy batch=1）
        )
        make_stateful(
            ovm,
            not_kv_inputs=not_kv_inputs,
            key_value_input_names=kv_in,
            key_value_output_names=kv_out,
            batch_dim=0,
            num_beams_and_batch=1,
        )
        ins = [(i.get_any_name(), str(i.get_partial_shape())) for i in ovm.inputs]
        outs = [(o.get_any_name(), str(o.get_partial_shape()))
                for o in ovm.outputs]
        h = {}
        for op in ovm.get_ops():
            h[op.get_type_name()] = h.get(op.get_type_name(), 0) + 1
        rec = {
            'tag': tag, 'inputs': ins, 'outputs': outs,
            'has_beam_idx': any(n == 'beam_idx' for n, _ in ins),
            'n_ops': sum(h.values()),
            'ReadValue': h.get('ReadValue', 0), 'Assign': h.get('Assign', 0),
            'Gather': h.get('Gather', 0),
        }
        info['graphs'].append(rec)
        print(f"  [{tag}] beam_idx={rec['has_beam_idx']} "
              f"ReadValue={rec['ReadValue']} Assign={rec['Assign']} "
              f"Gather={rec['Gather']} n_ops={rec['n_ops']} "
              f"n_in={len(ins)}", flush=True)
        return ovm

    statefuls = {}
    for tag in ('prefill', 'decode0', 'decode1'):
        statefuls[tag] = step(f'make_stateful_{tag}', lambda t=tag: _stateful(t))

    # ── 保存 ─────────────────────────────────────────────────────
    def _save():
        outs = {}
        for tag, ovm in statefuls.items():
            d = os.path.join(ROOT, f'models/ov-dec-stateful-{tag}')
            os.makedirs(d, exist_ok=True)
            ov.save_model(ovm, os.path.join(d, 'openvino_decoder_model.xml'),
                          compress_to_fp16=True)
            sz = sum(os.path.getsize(os.path.join(d, f))
                     for f in os.listdir(d))
            outs[tag] = {'dir': d, 'mib': round(sz / 1048576, 1)}
            print(f'  [{tag}] saved {sz/1048576:.1f} MiB -> {d}', flush=True)
        return outs

    info['saved'] = step('save_ir', _save)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    finally:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print('\nwrote', LOG)
