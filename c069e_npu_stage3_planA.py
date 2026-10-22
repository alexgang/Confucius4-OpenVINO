# C-066 阶段 3 · 方案 A：现有 stateful 解码器 IR 直接 NPUW
#
# C-067 明确要求：「方案 A 请照常试一次，把错误全文记下来」。
# 已知必失败（动态形状 + 57 个 ReadValue/Assign 状态变量 + 图内形状计算），
# 本脚本的目的是产出**确定性交付物**：完整报错全文 + 障碍清单。
#
# 不做 CUDA 测试、不改驱动/系统安全设置、不使用 torch。
import os
os.environ['USE_TORCH'] = '0'
os.environ['USE_TF'] = '0'
os.environ['USE_FLAX'] = '0'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

import json
import time
import openvino as ov

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, 'reports/npu_cache')
OUT = os.path.join(ROOT, 'reports/c069e_npu_planA.json')

DECODERS = {
    'decoder_INT8': 'models/ov-int8-past/openvino_decoder_model.xml',
    'decoder_INT4_full': 'models/ov-int4-lmhead-past/openvino_decoder_model.xml',
}

NPUW_PROPS = {
    'NPU_USE_NPUW': 'YES',
    'NPUW_LLM': 'YES',
    'NPUW_LLM_MAX_PROMPT_LEN': '512',
    'NPUW_LLM_MIN_RESPONSE_LEN': '1',
    'CACHE_DIR': CACHE,
}


def op_stats(model):
    hist = {}
    for op in model.get_ops():
        t = op.get_type_name()
        hist[t] = hist.get(t, 0) + 1
    return hist


def main():
    core = ov.Core()
    res = {
        'note': ('C-066 阶段 3 方案 A：现有 stateful 解码器 IR 直接 NPUW。'
                 '按 C-067 照常试一次并记录报错全文。预期失败（动态形状 + '
                 '状态变量 + 图内形状计算），本文件即为该失败的交付物。'),
        'npuw_props': NPUW_PROPS,
        'decoders': {},
    }

    for tag, rel in DECODERS.items():
        rec = {'ir': rel}
        path = os.path.join(ROOT, rel)
        try:
            model = core.read_model(path)
        except Exception as e:
            rec['read_error'] = str(e)[:2000]
            res['decoders'][tag] = rec
            print(tag, 'READ FAILED', str(e)[:150])
            continue

        rec['input_ports'] = [(i.get_any_name(), str(i.get_partial_shape()))
                              for i in model.inputs]
        rec['n_states'] = len(model.get_state()) if hasattr(model, 'get_state') \
            else None
        hist = op_stats(model)
        rec['n_ops'] = sum(hist.values())
        # C-067 点名的三类障碍
        rec['barriers'] = {
            'ReadValue': hist.get('ReadValue', 0),
            'Assign': hist.get('Assign', 0),
            'ShapeOf': hist.get('ShapeOf', 0),
            'Range': hist.get('Range', 0),
            'CumSum': hist.get('CumSum', 0),
            'GatherElements': hist.get('GatherElements', 0),
            'ScatterNDUpdate': hist.get('ScatterNDUpdate', 0),
            'ScaledDotProductAttention': hist.get('ScaledDotProductAttention', 0),
        }
        rec['n_dynamic_inputs'] = sum(
            1 for i in model.inputs if '?' in str(i.get_partial_shape()))
        rec['has_encoder_hidden_states'] = any(
            'encoder_hidden_states' in i.get_any_name()
            or 'encoder_hidden_states' in str(i.get_names())
            for i in model.inputs)
        print(f"\n=== {tag} ===")
        print('  ops:', rec['n_ops'], ' dynamic inputs:',
              rec['n_dynamic_inputs'])
        print('  barriers:', json.dumps(rec['barriers']))
        print('  inputs:', rec['input_ports'][:4])

        # 尝试 1：原始 IR + NPUW
        for label, mdl, props in (
            ('raw_npuw', model, NPUW_PROPS),
            ('plain_npu', model, {'CACHE_DIR': CACHE}),
        ):
            t0 = time.time()
            try:
                core.compile_model(mdl, 'NPU', props)
                rec[label] = {'ok': True, 'seconds': round(time.time() - t0, 1)}
                print(f'  {label}: OK ({rec[label]["seconds"]}s)')
            except Exception as e:
                msg = str(e)
                rec[label] = {'ok': False,
                              'seconds': round(time.time() - t0, 1),
                              'error': msg[:6000],
                              'error_type': type(e).__name__}
                tail = ' | '.join(l.strip() for l in msg.strip().splitlines()
                                  if l.strip())[-400:]
                print(f'  {label}: FAILED — {tail}')

        # 尝试 2：能否靠 reshape 抢救？（预期不行：状态变量仍在）
        try:
            smap = {}
            for idx, i in enumerate(model.inputs):
                p = i.get_partial_shape()
                smap[i] = ov.PartialShape([1 if d == '?' or d.is_dynamic else d
                                           for d in p])
            ret = model.reshape(smap)
            mm = ret if ret is not None else model
            rec['reshape_frozen_ports'] = [
                (i.get_any_name(), str(i.get_partial_shape())) for i in mm.inputs]
            t0 = time.time()
            try:
                core.compile_model(mm, 'NPU', NPUW_PROPS)
                rec['reshaped_npuw'] = {'ok': True,
                                        'seconds': round(time.time() - t0, 1)}
                print('  reshaped_npuw: OK')
            except Exception as e:
                rec['reshaped_npuw'] = {'ok': False,
                                        'seconds': round(time.time() - t0, 1),
                                        'error': str(e)[:6000]}
                tail = ' | '.join(l.strip() for l in str(e).strip().splitlines()
                                  if l.strip())[-300:]
                print(f'  reshaped_npuw: FAILED — {tail}')
        except Exception as e:
            rec['reshape_error'] = f'{type(e).__name__}: {e}'[:1500]
            print('  reshape FAILED:', str(e)[:150])

        res['decoders'][tag] = rec

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
