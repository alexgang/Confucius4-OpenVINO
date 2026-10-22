# C-069j 的根因修法：把序列长度做成**导出期参数**
#
# 根因：`ov_model.reshape()` 只能改输入端口形状，改不了**图内**已被常量固化的
# RoPE position_ids 索引（实测报错）：
#     f32[1,4,1,512,128] -> Broadcast -> f32[1,8,2,512,128]
#     "Broadcast incorrect target shape. Expecting either 1 or 4. Got 8"
# 所以只有原始长度 512 能编译，改成 256/1024 全失败。
#
# 正确做法：**导出时就用目标长度跑一次 trace**，
# 让图内所有常量按那个长度固化。这里一次导出多个长度变体，
# 用于量化「缩短重算序列」这条路到底能救回多少。
#
# 关键问题：序列长 = 模板(13) + 音频 token + 前缀(<=100) + 已生成 token
#   典型段 16.36 s → 音频约 208 token，已生成约 65 → 约 386
#   所以要试的长度是 256 / 320 / 384 / 512，而不是任意值。
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
LOG = os.path.join(ROOT, 'reports/c069k_export_variants.json')

H = 2048
LENS = (256, 320, 384, 512)      # 覆盖典型段的实际需求区间

info = {'note': ('按目标序列长度分别导出，让 RoPE position_ids 在导出期正确固化。'
                 '用途：验证「缩短重算序列」能否救回无 cache 方案。'),
        'hidden': H, 'lens': list(LENS), 'variants': {}}


def main():
    import torch
    import openvino as ov
    from qwen_asr.core.transformers_backend import (
        Qwen3ASRForConditionalGeneration)

    full = Qwen3ASRForConditionalGeneration.from_pretrained(
        HF, dtype=torch.float32)
    text_model = full.thinker.model
    lm_head = full.thinker.lm_head

    class Exportable(torch.nn.Module):
        def __init__(self, tm, head):
            super().__init__()
            self.tm = tm
            self.head = head

        def forward(self, inputs_embeds):
            out = self.tm(inputs_embeds=inputs_embeds, use_cache=False)
            return self.head(out.last_hidden_state[:, -1:, :])

    net = Exportable(text_model, lm_head).eval()

    for L in LENS:
        rec = {'len': L}
        t0 = time.time()
        try:
            ex = torch.zeros(1, L, H, dtype=torch.float32)
            ex[:, :8, :] = torch.randn(8, H) * 0.02
            ep = torch.export.export(net, (ex,))
            # ⚠️ 从 ExportedProgram 转换时**不能**再传 `input=` tensor 描述
            # （会报 "Incorrect input parameters provided... Got unknown object: tensor"）。
            # 直接 convert_model(ep) 让它用导出时的静态 shape。
            ov_m = ov.convert_model(ep)
            ports = [(i.get_any_name(), str(i.get_partial_shape()))
                     for i in ov_m.inputs]
            # 若仍是动态，冻结到目标形状
            if '?' in ports[0][1]:
                ret = ov_m.reshape({ov_m.input(0): ov.PartialShape([1, L, H])})
                ov_m = ret if ret is not None else ov_m
                ports = [(i.get_any_name(), str(i.get_partial_shape()))
                         for i in ov_m.inputs]

            out_dir = os.path.join(ROOT, f'models/ov-dec-embed-L{L}')
            os.makedirs(out_dir, exist_ok=True)
            ov.save_model(ov_m, os.path.join(out_dir,
                                             'openvino_decoder_model.xml'),
                          compress_to_fp16=True)
            sz = sum(os.path.getsize(os.path.join(out_dir, f))
                     for f in os.listdir(out_dir))
            rec.update({'ok': True, 'seconds': round(time.time() - t0, 1),
                        'mib': round(sz / 1048576, 1),
                        'inputs': [(i.get_any_name(),
                                    str(i.get_partial_shape()))
                                   for i in ov_m.inputs],
                        'outputs': [str(o.get_partial_shape())
                                    for o in ov_m.outputs],
                        'dir': out_dir})
            print(f'[{L}] OK {rec["seconds"]}s {rec["mib"]} MiB '
                  f'{rec["inputs"]}', flush=True)
        except Exception as e:
            rec.update({'ok': False, 'seconds': round(time.time() - t0, 1),
                        'error': f'{type(e).__name__}: {e}'[:1500]})
            print(f'[{L}] FAIL {type(e).__name__}: {str(e)[:250]}', flush=True)
        info['variants'][str(L)] = rec

    with open(LOG, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print('\nwrote', LOG)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
    finally:
        with open(LOG, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
