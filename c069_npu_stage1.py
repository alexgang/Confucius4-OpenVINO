# C-066 阶段 1：编码器上 NPU
# C-069：允许本机使用 torch；但实测 torch 被应用控制策略拦截（WinError 4551），
#       故改用 OpenVINO reshape 冻结输入签名 —— 不需要 torch 重导出。
# 铁律：与所有计时作业串行；不改驱动/系统安全设置；不做 CUDA 测试。
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
ENC = os.path.join(ROOT, 'models/ov-encoder-segment-reviewer/openvino_encoder_model.xml')
CACHE = os.path.join(ROOT, 'reports/npu_cache')
OUT = os.path.join(ROOT, 'reports/c069_npu_stage1.json')

# 冻结后的输入签名：与图内静态输出一致（312 audio token ≈ 24 s）
FIXED = ov.PartialShape([1, 128, 2400])

res = {
    'note': ('C-066 阶段 1。torch 在目标机被应用控制拦截，改用 openvino reshape '
             '冻结输入签名（不需要重导出）。判据沿用 reviewer 的 9 个长度：'
             '0.64–23.9 s，cosine mean>=0.999 / min>=0.99。'),
    'torch_available': None,
    'torch_error': None,
    'attempts': [],
    'cosine': None,
    'latency': None,
}

# ── torch 可用性（C-069 要求记录，不绕过） ────────────────────────────
try:
    import torch  # noqa
    res['torch_available'] = True
except Exception as e:  # noqa
    res['torch_available'] = False
    res['torch_error'] = f'{type(e).__name__}: {e}'

core = ov.Core()
core.set_property({'CACHE_DIR': CACHE})
# ⚠️ 不要给 core 设全局 LOG_LEVEL：HETERO 会把它透传给子插件并报
#    "Property was not found: LOG_LEVEL"（见 hetero_fp16 尝试）。

model = core.read_model(ENC)
ports = [(i.get_any_name(), str(i.get_partial_shape())) for i in model.inputs]
outputs = []
for o in model.outputs:
    try:
        nm = o.get_any_name()
    except Exception:
        nm = '<unnamed>'
    outputs.append([nm, str(o.get_partial_shape())])
res['original_input_ports'] = ports
res['output_ports'] = outputs


def try_compile(name, mdl, device, with_cache=True):
    rec = {'name': name, 'device': device, 'ok': False}
    t0 = time.time()
    try:
        props = {}
        if with_cache:
            props['CACHE_DIR'] = CACHE
        cm = core.compile_model(mdl, device, props)
        rec['ok'] = True
        rec['seconds'] = round(time.time() - t0, 1)
        rec['n_ops_compiled'] = len(cm.get_ops())
    except Exception as e:
        msg = str(e)
        rec['seconds'] = round(time.time() - t0, 1)
        rec['error'] = msg[:6000]
        rec['error_type'] = type(e).__name__
        res['attempts'].append(rec)
    print(f"[{name}] {device} ok={rec['ok']} {rec.get('seconds')}s "
          f"{rec.get('error', '')[:160]}")
    return rec


# ── 1) 原始动态 IR 直接编译（记录基线失败） ──────────────────────────
try_compile('raw_dynamic_fp16', model, 'NPU')

# ── 2) reshape 冻结输入签名后编译 ────────────────────────────────────
# ⚠️ 两个 OpenVINO 2026.4 的坑：
#   1) Model.reshape() 是**原地修改并返回 None**，不是返回新模型；
#   2) 必须冻结**全部**动态输入 —— 只冻结 input_features 时 n_valid 仍是 [?]，
#      NPU 报错会从「IE.Reshape doesn't support dynamic shapes」变成
#      「Missing upper bound for one or more nodes.」
frozen = None
try:
    shape_map = {m.get_any_name(): ov.PartialShape(s) for m, s in (
        (model.input(0), [1, 128, 2400]),
        (model.input(1), [1]),
    )}
    ret = model.reshape(shape_map)
    frozen = ret if ret is not None else model
    res['reshape_returned_none'] = (ret is None)
    res['frozen_input_ports'] = [(i.get_any_name(), str(i.get_partial_shape()))
                                 for i in frozen.inputs]
    print('reshape ok ->', res['frozen_input_ports'])
except Exception as e:
    res['reshape_error'] = f'{type(e).__name__}: {e}'[:800]
    print('reshape FAILED:', e)

if frozen is not None:
    rec = try_compile('frozen_fp16', frozen, 'NPU')
    if not rec['ok']:
        try_compile('frozen_fp16_hetero', frozen, 'HETERO:NPU,GPU')

# ── 3) 若 NPU 编译成功，做精度与延迟验收 ────────────────────────────
if frozen is not None and any(a['ok'] and 'frozen' in a['name']
                              and a['device'] == 'NPU' for a in res['attempts']):
    # 复用 c039 的零填充口径（内联实现，避免顶层 import torch）
    import soundfile as sf
    from transformers import WhisperFeatureExtractor

    def aftercnn_len(n):
        leave = n % 100
        feat = (leave - 1) // 2 + 1
        return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + (n // 100) * 13

    def total_aftercnn_len(frames):
        if frames <= 0:
            return 0
        n_full = frames // 100
        leave = frames - n_full * 100
        return n_full * 13 if leave == 0 else n_full * 13 + aftercnn_len(leave)

    LENS = (0.64, 4, 7.68, 8, 9.6, 12.8, 16, 20, 23.9)
    fe = WhisperFeatureExtractor.from_pretrained(os.path.join(ROOT, 'models/hf'))
    audio, sr = sf.read(os.path.join(ROOT, 'test_audio/<redacted>.wav'),
                        dtype='float32')
    seg = audio[2812 * sr: 2812 * sr + int(24.0 * sr)]

    def build(sec):
        clip = seg[: int(sec * sr)]
        out = fe([clip], sampling_rate=16000, return_tensors='np',
                 padding='do_not_pad', truncation=False, return_attention_mask=True)
        mel = out['input_features'][0]
        n_real = int(out['attention_mask'][0].sum())
        mel = mel[:, :n_real]
        assert mel.shape[1] <= 2400, f'too long {mel.shape[1]}'
        x = np.zeros((1, 128, 2400), dtype=np.float32)
        x[0, :, : mel.shape[1]] = mel
        nv = np.array([total_aftercnn_len(mel.shape[1])], dtype=np.int32)
        return x, nv

    npu_cm = None
    for dev in ('NPU', 'HETERO:NPU,GPU'):
        try:
            npu_cm = core.compile_model(frozen, dev, {'CACHE_DIR': CACHE})
            print('acceptance device =', dev)
            res['acceptance_device'] = dev
            break
        except Exception:
            pass
    gpu_cm = core.compile_model(frozen, 'GPU')
    rows = []
    for sec in LENS:
        x, nv = build(sec)
        feeds = [x, nv] if len(npu_cm.inputs) > 1 else [x]
        feeds_g = [x, nv] if len(gpu_cm.inputs) > 1 else [x]
        t0 = time.time()
        a = gpu_cm(feeds_g)[0]
        g_ms = (time.time() - t0) * 1000
        t0 = time.time()
        b = npu_cm(feeds)[0]
        n_ms = (time.time() - t0) * 1000
        av, bv = a.reshape(-1), b.reshape(-1)
        cos = float(np.dot(av, bv) /
                    (np.linalg.norm(av) * np.linalg.norm(bv)))
        rel = float(np.abs(av - bv).max() / (np.abs(av).max() + 1e-12))
        rows.append({'sec': sec, 'cosine': round(cos, 6),
                     'max_rel_diff': round(rel, 6),
                     'gpu_ms_first': round(g_ms, 1), 'npu_ms_first': round(n_ms, 1)})
        print(f'  {sec:5.2f}s cos={cos:.6f} rel={rel:.2e}')
    cos_list = [r['cosine'] for r in rows]
    res['cosine'] = {
        'rows': rows,
        'mean': round(float(np.mean(cos_list)), 6),
        'min': round(float(np.min(cos_list)), 6),
        'pass': bool(np.mean(cos_list) >= 0.999 and np.min(cos_list) >= 0.99),
    }

    # 预热后单次调用延迟，>=20 次中位数
    x, nv = build(12.0)
    feeds = [x, nv] if len(npu_cm.inputs) > 1 else [x]
    feeds_g = [x, nv] if len(gpu_cm.inputs) > 1 else [x]
    for _ in range(5):
        npu_cm(feeds); gpu_cm(feeds_g)
    lat = {}
    for tag, cm, fd in (('npu', npu_cm, feeds), ('gpu', gpu_cm, feeds_g)):
        ts = []
        for _ in range(20):
            t0 = time.time()
            cm(fd)
            ts.append((time.time() - t0) * 1000)
        ts.sort()
        lat[tag] = {'median_ms': round(ts[len(ts) // 2], 2),
                    'min_ms': round(ts[0], 2), 'max_ms': round(ts[-1], 2)}
    lat['speedup_gpu_over_npu'] = round(
        lat['gpu']['median_ms'] / max(lat['npu']['median_ms'], 1e-9), 3)
    res['latency'] = lat
    print('latency:', json.dumps(lat, ensure_ascii=False))

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print('\nwrote', OUT)
print('NPU compile succeeded:',
      any(a['ok'] and 'frozen' in a['name'] and a['device'] == 'NPU'
          for a in res['attempts']))
