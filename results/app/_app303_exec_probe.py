# -*- coding: utf-8 -*-
"""app303 执行设备直证（跑在**从 zip 解出来的包**里）。"""
import json, os, sys
PKG = os.environ.get('APP303_PKG')
CACHE = os.environ.get('APP303_NPU_CACHE')
sys.path.insert(0, os.path.join(PKG, 'app'))
os.chdir(os.path.join(PKG, 'app'))
import numpy as np
import openvino as ov
import npu_embeds_backend
from npu_delivery_backend import make_delivery_all_npu_backend
npy = os.path.join(PKG, 'models', 'embed_tokens_f16.npy')
npu_embeds_backend._load_embed_table = lambda: np.asarray(np.load(npy), dtype=np.float32)
AL = {'ov-encoder-segment-reviewer': ['encoder-fp16'],
      'qwen3-lm-int8sym-cleanie-ov': ['decoder-npu-int8'],
      'ov-int8-past': ['decoder-gpu-int8']}
def mp(logical):
    m = os.path.join(PKG, 'models')
    for a in AL.get(logical, []):
        p = os.path.join(m, *a.split('/'))
        if os.path.exists(p):
            return p
    return os.path.join(m, *logical.split('/'))
be = make_delivery_all_npu_backend(
    encoder_dir=mp('ov-encoder-segment-reviewer'),
    decoder_dir=mp('qwen3-lm-int8sym-cleanie-ov'),
    tokenizer_dir=mp('ov-int8-past'), npu_cache=CACHE)
def ed(cm):
    try:
        d = cm.get_property('EXECUTION_DEVICES')
        return list(d) if isinstance(d, (list, tuple)) else str(d)
    except Exception as e:
        return 'ERR:%s' % e
def only(v):
    parts = [x.strip() for x in v.split(',')] if isinstance(v, str) else [str(x) for x in v]
    return len(parts) > 0 and all(p.upper().startswith('NPU') for p in parts)
enc = ed(be.enc); dec = ed(be.dec)
res = {'encoder_exec_devices': enc, 'decoder_exec_devices': dec,
       'encoder_on_npu_only': only(enc), 'decoder_on_npu_only': only(dec),
       'ov_version': ov.__version__, 'cache': CACHE,
       'npu_enc_compile_s': getattr(be, 'npu_enc_compile_s', None),
       'npu_dec_compile_s': getattr(be, 'npu_compile_s', None)}
res['verdict'] = ('EXEC_ON_NPU_OK' if res['encoder_on_npu_only']
                   and res['decoder_on_npu_only'] else 'EXEC_NOT_ALL_NPU')
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'app303_exec_probe_out.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
