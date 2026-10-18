# C-066 阶段 3 · 方案 A 的运行时验证
#
# ⚠️ 为什么必须实测：`c069e` 里 decoder 的 `reshaped_npuw` 报 **OK**，
# 但那是把动态维度强行冻结成 **1** 得到的假象：
#     encoder_hidden_states [1,1,2048]   input_ids [1,1]   beam_idx [1]
# 流式解码的 prefill 需要**整条 prompt**（约 425 token，见 C069_STAGE3_INTERFACE_SPEC.md），
# decode 步才是 1 token。`[1,1]` 既装不下 prompt，也丢掉了 KV 缓存的序列维度。
# 所以「编译通过」≠「可用」。本脚本实际喂真实形状的推理，验证它到底能不能跑。
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
OUT = os.path.join(ROOT, 'reports/c069f_npu_decoder_runtime.json')
DEC = 'models/ov-int8-past/openvino_decoder_model.xml'

# prefill 的真实规模：模板前缀 + 音频占位 + 引导前缀（规格文件里的预算）
PREFILL_LEN = 425


def try_run(cm, feeds, label):
    t0 = time.time()
    try:
        r = cm(feeds)
        outs = [np.asarray(o).shape for o in r.values()] \
            if hasattr(r, 'values') else [np.asarray(r[0]).shape]
        return {'ok': True, 'seconds': round(time.time() - t0, 2),
                'outputs': [str(o) for o in outs]}
    except Exception as e:
        msg = str(e)
        tail = ' | '.join(l.strip() for l in msg.strip().splitlines()
                          if l.strip())[-500:]
        return {'ok': False, 'seconds': round(time.time() - t0, 2),
                'error': msg[:4000], 'error_tail': tail}


def main():
    core = ov.Core()
    core.set_property({'CACHE_DIR': CACHE})
    res = {'note': ('阶段 3 方案 A 运行时验证：证明「冻结成 [1,1] 编译通过」是假阳性，'
                    '真实 prefill 形状无法在 NPU 上推理。'),
           'prefill_len': PREFILL_LEN, 'ir': DEC, 'runs': []}

    model = core.read_model(os.path.join(ROOT, DEC))
    res['original_ports'] = [(i.get_any_name(), str(i.get_partial_shape()))
                             for i in model.inputs]

    # 场景 1：按 c069e 的方式冻结成 [1,1]
    m1 = core.read_model(os.path.join(ROOT, DEC))
    smap = {i: ov.PartialShape([1 if (d == '?' or d.is_dynamic) else d
                                for d in i.get_partial_shape()])
            for i in m1.inputs}
    ret = m1.reshape(smap)
    m1 = ret if ret is not None else m1
    res['frozen_1_ports'] = [(i.get_any_name(), str(i.get_partial_shape()))
                            for i in m1.inputs]

    cm = None
    try:
        cm = core.compile_model(m1, 'NPU', {
            'NPU_USE_NPUW': 'YES', 'NPUW_LLM': 'YES',
            'NPUW_LLM_MAX_PROMPT_LEN': '512',
            'NPUW_LLM_MIN_RESPONSE_LEN': '1', 'CACHE_DIR': CACHE})
        res['compile_ok'] = True
        print('compile OK with [1,1] freeze')
    except Exception as e:
        res['compile_ok'] = False
        res['compile_error'] = str(e)[:3000]
        print('compile FAILED:', str(e)[-200:])

    # 场景 1a：用冻结后的形状真的跑一次 decode 步（1 token）
    if cm is not None:
        feeds = {
            'encoder_hidden_states': np.zeros((1, 1, 2048), dtype=np.float32),
            'input_ids': np.array([[151646]], dtype=np.int64),
            'beam_idx': np.array([0], dtype=np.int32),
        }
        try:
            cm.reset_state()
        except Exception:
            pass
        rec = try_run(cm, feeds, 'frozen1_decode')
        res['runs'].append({'case': 'frozen_[1,1]_decode_step', **rec})
        print('frozen [1,1] decode:', json.dumps(rec, ensure_ascii=False)[:300])

    # 场景 2：按真实 prefill 长度重新冻结并编译 —— 这才是流式需要的
    m2 = core.read_model(os.path.join(ROOT, DEC))
    try:
        smap2 = {
            m2.input(0): ov.PartialShape([1, 312, 2048]),   # 音频 token 上界
            m2.input(1): ov.PartialShape([1, PREFILL_LEN]),  # 整条 prompt
            m2.input(2): ov.PartialShape([1]),
        }
        ret2 = m2.reshape(smap2)
        m2 = ret2 if ret2 is not None else m2
        res['frozen_real_ports'] = [(i.get_any_name(), str(i.get_partial_shape()))
                                   for i in m2.inputs]
        print('\nre-froze with real prefill ->', res['frozen_real_ports'])
    except Exception as e:
        res['refreeze_error'] = f'{type(e).__name__}: {e}'[:1500]
        print('re-freeze FAILED:', str(e)[:200])

    # 场景 3：即使编译过了，实际推理是否可用
    cm2 = None
    if 'frozen_real_ports' in res:
        try:
            cm2 = core.compile_model(m2, 'NPU', {
                'NPU_USE_NPUW': 'YES', 'NPUW_LLM': 'YES',
                'NPUW_LLM_MAX_PROMPT_LEN': '512',
                'NPUW_LLM_MIN_RESPONSE_LEN': '1', 'CACHE_DIR': CACHE})
            res['real_compile_ok'] = True
            print('compile OK with real prefill shape')
        except Exception as e:
            res['real_compile_ok'] = False
            res['real_compile_error'] = str(e)[:4000]
            tail = ' | '.join(l.strip() for l in str(e).strip().splitlines()
                              if l.strip())[-400:]
            print('real-shape compile FAILED:', tail)

            cm2 = None

    if cm2 is not None:
        try:
            cm2.reset_state()
        except Exception:
            pass
        feeds2 = {
            'encoder_hidden_states': np.zeros((1, 312, 2048), dtype=np.float32),
            'input_ids': np.zeros((1, PREFILL_LEN), dtype=np.int64),
            'beam_idx': np.array([0], dtype=np.int32),
        }
        rec = try_run(cm2, feeds2, 'real_prefill')
        res['runs'].append({'case': 'real_prefill_425tok', **rec})
        print('real prefill run:', json.dumps(rec, ensure_ascii=False)[:400])

        # 第二次调用：验证 KV 状态是否可用（流式必须能多步）
        rec2 = try_run(cm2, feeds2, 'real_prefill_2nd')
        res['runs'].append({'case': 'real_prefill_2nd_call', **rec2})
        print('2nd call:', json.dumps(rec2, ensure_ascii=False)[:300])

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
