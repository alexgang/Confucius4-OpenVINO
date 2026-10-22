# C-066 阶段 3 · 方案 B：导出 `inputs_embeds` 版解码器（FP16 打通链路）
#
# 目标：把 stateful 解码器（57 对 ReadValue/Assign，NPU 不支持图内状态）
# 改成 `inputs_embeds` 单输入、无状态、静态形状 → 可上 NPUW。
#
# ⚠️ 关键设计决策（踩坑后修正）：
#   源模型的文本主干是**自研** `Qwen3ASRThinkerTextModel`，不是标准 `Qwen3ForCausalLM`。
#   若构造标准类再做权重名映射，风险很高（自定义 RMSNorm/Attention/RoPE 结构易错配）。
#   **改为直接导出源模块** —— 它本身已原生接受 `inputs_embeds`
#   （见 modeling_qwen3_asr.py:986 的 forward 签名），结构 100% 保真、零权重重映射。
#
# 本脚本**只导出、不计时**；按 C-069 启用 torch，但绝不与计时作业并发。
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
OUT_DIR = os.path.join(ROOT, 'models/ov-dec-embed-fp16')
LOG = os.path.join(ROOT, 'reports/c069g_export_stage3.json')

MAX_PROMPT_LEN = 512
HIDDEN = 2048

info = {
    'note': ('C-066 阶段 3 方案 B：inputs_embeds 版解码器（FP16）。'
             '直接导出源 Qwen3ASRThinkerTextModel + thinker.lm_head，'
             '零权重重映射；无状态、无 beam_idx、静态形状。'),
    'spec': {'input': 'inputs_embeds', 'shape': [1, MAX_PROMPT_LEN, HIDDEN],
             'MAX_PROMPT_LEN': MAX_PROMPT_LEN,
             'keep_beam_idx': False, 'use_cache': False},
    'steps': [],
}


def step(name, fn):
    t0 = time.time()
    try:
        r = fn()
        info['steps'].append({'name': name, 'ok': True,
                              'seconds': round(time.time() - t0, 1),
                              'detail': str(r)[:1500]})
        print(f'[OK] {name} ({time.time()-t0:.1f}s) {str(r)[:300]}', flush=True)
        return r
    except Exception as e:
        info['steps'].append({'name': name, 'ok': False,
                              'seconds': round(time.time() - t0, 1),
                              'error': f'{type(e).__name__}: {e}'[:2500],
                              'tb': traceback.format_exc()[-2000:]})
        print(f'[FAIL] {name}: {type(e).__name__}: {str(e)[:400]}', flush=True)
        raise


def main():
    import torch
    from transformers import AutoTokenizer
    from qwen_asr.core.transformers_backend import (
        Qwen3ASRForConditionalGeneration)

    full = step('load_full_asr',
                lambda: Qwen3ASRForConditionalGeneration.from_pretrained(
                    HF, dtype=torch.float32))
    thinker = full.thinker
    info['thinker_children'] = [n for n, _ in thinker.named_children()]
    print('  thinker children:', info['thinker_children'], flush=True)

    text_model = thinker.model          # Qwen3ASRThinkerTextModel
    lm_head = thinker.lm_head           # nn.Linear(2048 -> vocab)
    info['modules'] = {
        'text_model': type(text_model).__name__,
        'lm_head': type(lm_head).__name__,
        'n_layers': len(text_model.layers),
        'hidden': text_model.config.hidden_size,
        'vocab': text_model.config.vocab_size,
    }
    print('  modules:', info['modules'], flush=True)

    class Exportable(torch.nn.Module):
        """把「文本主干 + lm_head」打包成单输入 inputs_embeds 的静态图。

        两个刻意的设计（都是为 NPU 服务）：

        1. **只取最后位置的 logits**
           全序列输出是 `[1, 512, 151936]` 的 f32 = 1.24 GiB，既撑爆内存又让 NPU 不可行。
           贪心解码只关心最后一个位置 → `lm_head(h[:, -1:, :])` → `[1,1,151936]`（0.6 MB）。

        2. **不用 KV cache**（use_cache=False）
           图内不产生 ReadValue/Assign，这正是方案 A 失败、方案 B 可行的关键差别。

           ⚠️ 代价：无 cache 意味着无法自回归，需要在**图外**逐 token 整段重算，
           或用 NPUW 自己做分块缓存。这属于 NPUW 的职责范围，见接口规格。
        """

        def __init__(self, tm, head):
            super().__init__()
            self.tm = tm
            self.head = head

        def forward(self, inputs_embeds):
            out = self.tm(inputs_embeds=inputs_embeds, use_cache=False)
            h = out.last_hidden_state
            return self.head(h[:, -1:, :])

    net = Exportable(text_model, lm_head).eval()
    ex = torch.zeros(1, MAX_PROMPT_LEN, HIDDEN, dtype=torch.float32)
    ex[:, :8, :] = torch.randn(8, HIDDEN) * 0.02   # 给非零输入，便于自检

    def _sd():
        # 确认没有 stateful 相关模块混进来
        names = [n for n, _ in net.named_parameters()]
        bad = [n for n in names if any(
            k in n for k in ('past_key_value', 'cache', 'beam_idx'))]
        info['param_count'] = len(names)
        info['stateful_param_names'] = bad[:20]
        return f'{len(names)} params, stateful-looking={len(bad)}'

    step('inspect_params', _sd)

    def _convert():
        """优先 torch.export（OpenVINO 2026.4 原生支持）。

        TorchScript 路径会失败：transformers 的 forward 带
        `**kwargs` 与 keyword-only 默认参数，而 `torch.jit.script`
        不接受（实测报错 configuration_qwen3_asr.py:401 的 **kwargs）。
        torch.export 走 dynamo/AOT，无此限制。
        """
        import openvino as ov
        try:
            ep = torch.export.export(net, (ex,))
            return ov.convert_model(ep), 'torch.export'
        except Exception as e_export:
            print('  torch.export failed:', str(e_export)[:300], flush=True)
            info['torch_export_error'] = str(e_export)[:2000]
            try:
                with torch.no_grad():
                    return ov.convert_model(net, input=[('inputs_embeds', ex)]), \
                        'convert_model-direct'
            except Exception as e_direct:
                raise RuntimeError(
                    f'both paths failed. torch.export: {e_export} | '
                    f'convert_model: {e_direct}')

    ov_model, how = step('convert_to_openvino', _convert)
    info['conversion_path'] = how
    print('  conversion path:', how, flush=True)

    # torch.export 会把输入标成 [?,?,?]（dynamic=None 的默认行为）。
    # NPU 必须静态 —— 用 reshape 冻结。注意 2026.4 的 reshape 是**原地修改返回 None**。
    def _freeze():
        ret = ov_model.reshape({ov_model.input(0):
                                ov.PartialShape([1, MAX_PROMPT_LEN, HIDDEN])})
        frozen = ret if ret is not None else ov_model
        ports = [(i.get_any_name(), str(i.get_partial_shape()))
                 for i in frozen.inputs]
        info['reshape_returned_none'] = (ret is None)
        info['frozen_ports'] = ports
        print('  frozen ports:', ports, flush=True)
        return frozen          # 返回模型对象本身，供下一步使用

    import openvino as ov
    # ⚠️ 2026.4 的 reshape 是**原地修改返回 None**，所以模型对象没变。
    # 这里不依赖 step() 的返回值，直接沿用 ov_model。
    ov_model = _freeze()
    info['steps'].append({'name': 'freeze_input_shape', 'ok': True,
                          'detail': str(info.get('frozen_ports'))})

    def _ports():
        ins = [(i.get_any_name(), str(i.get_partial_shape())) for i in ov_model.inputs]
        outs = [(o.get_any_name(), str(o.get_partial_shape()))
                for o in ov_model.outputs]
        info['ov_ports'] = {'inputs': ins, 'outputs': outs}
        return f'in={ins} out={outs}'

    step('inspect_ports', _ports)

    def _ops():
        hist = {}
        for op in ov_model.get_ops():
            t = op.get_type_name()
            hist[t] = hist.get(t, 0) + 1
        info['op_hist'] = dict(sorted(hist.items(), key=lambda x: -x[1])[:20])
        stateful = {k: v for k, v in hist.items()
                    if k in ('ReadValue', 'Assign', 'ShapeOf', 'Range',
                             'ScatterNDUpdate', 'GatherElements', 'CumSum')}
        info['npuw_hazard_ops'] = stateful
        return f'ops={sum(hist.values())} hazards={stateful}'

    step('inspect_ops', _ops)

    def _save():
        import openvino as ov
        os.makedirs(OUT_DIR, exist_ok=True)
        ov.save_model(ov_model,
                      os.path.join(OUT_DIR, 'openvino_decoder_model.xml'),
                      compress_to_fp16=True)
        sz = sum(os.path.getsize(os.path.join(OUT_DIR, f))
                 for f in os.listdir(OUT_DIR))
        info['saved'] = {'dir': OUT_DIR, 'mib': round(sz / 1048576, 1)}
        return info['saved']

    step('save_fp16_ir', _save)

    def _verify():
        import openvino as ov
        core = ov.Core()
        cm = core.compile_model(
            os.path.join(OUT_DIR, 'openvino_decoder_model.xml'), 'CPU')
        ov_out = cm([ex.numpy()])[0]
        with torch.no_grad():
            t_out = net(ex).numpy()
        a, b = ov_out.reshape(-1), t_out.reshape(-1)
        cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        info['selfcheck_cpu'] = {
            'cosine': round(cos, 6),
            'max_abs_diff': round(float(np.abs(a - b).max()), 6),
            'ov_shape': list(ov_out.shape), 'torch_shape': list(t_out.shape),
            'argmax_match': bool(np.argmax(a) == np.argmax(b)),
        }
        return (f"cos={cos:.6f} ov{tuple(ov_out.shape)} "
                f"argmax_match={np.argmax(a) == np.argmax(b)}")

    step('selfcheck_cpu_fp16', _verify)

    tok = step('tokenizer', lambda: AutoTokenizer.from_pretrained(
        HF, fix_mistral_regex=True))
    info['tokenizer_vocab'] = len(tok)
    info['audio_pad_id'] = 151676
    info['eos_ids'] = [151643, 151645]


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    finally:
        with open(LOG, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print('\nwrote', LOG)
