"""c045_export_variants.py — C-045: decoder 量化候选变体导出（per-layer 混合 / AWQ / GPTQ / 敏感度混合 / per-group）

背景 (C-044 结论):
- ov-int8-past 已是 weight-only INT8 (IR 无 FakeQuantize), top-1 94.12% / EOS 63.41%
- 只有 FP16 达标 (top-1 100%) 但 RTF 1.166 > 0.8
- C-044 认为做不到的 (d)/(e) 其实可用 compress_weights 的 IgnoredScope(patterns=)
  和 ratio+sensitivity_metric 实现; AWQ/GPTQ 也从未试过

候选 (全部从 models/ov-fp16-past 导出):
  mix4      INT8_ASYM, 层 0,1,26,27 保 FP16            (RTF 预期 ~0.74)
  mix8      INT8_ASYM, 层 0-3,24-27 保 FP16            (RTF 预期 ~0.84, 看实测)
  awq8      INT8_ASYM + AWQ + 校准集                   (RTF ~0.65)
  gptq8     INT8_ASYM + GPTQ + 校准集                  (RTF ~0.65)
  sens10    INT8_ASYM + ratio=0.10 + 权重误差敏感度     (自动 per-layer 混合, RTF ~0.71)
  pergroup8 INT8_ASYM per-group g128 all_layers        (c043_export_pergroup 输出不存在, 重试)
  int4awq   INT4_SYM per-group g128 + AWQ              (RTF ~0.59, INT4+AWQ 看能否救回精度)

校准集: 3 个真实段 (seg118/161/163) × 4 个 chunk 位置的 (input_ids, ehs), ehs 由
models/ov-encoder-segment-reviewer 编码 (与验收配置一致)。

用法:
  .venv python c045_export_variants.py                 # 全部
  .venv python c045_export_variants.py --variants mix4 awq8
"""
import os, sys, time, json, shutil, argparse, re, traceback
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import openvino as ov
import nncf
from nncf import IgnoredScope
from nncf.data.dataset import Dataset

SRC_DIR = 'models/ov-fp16-past'
ENC_DIR = 'models/ov-encoder-segment-reviewer'
LOG_DIR = 'status/logs'

CHUNK_SIZE_SEC = 0.64
# 与 c044 teacher-force 相同的 3 个代表段
CALIB_SEGMENTS = [
    (1925.4, 1939.5, 'seg118_1925_1940'),
    (2622.2, 2640.4, 'seg161_2622_2640'),
    (2656.8, 2675.9, 'seg163_2657_2676'),
]
CALIB_CHUNK_IDS = [0, 1, 2, -1]   # 每段取 4 个 chunk 位置

LAYER_MM_PREFIX = r'__module\.model\.thinker\.model\.layers\.'


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- 校准集
def build_calibration():
    """3 段 × 4 chunk → (input_ids, ehs, beam_idx) 样本列表."""
    import soundfile as sf
    from transformers import AutoTokenizer, WhisperFeatureExtractor
    from backends import extract_audio_features

    core = ov.Core()
    core.set_property({'CACHE_DIR': './ov_cache'})
    enc_model = core.read_model(
        model=os.path.join(ENC_DIR, 'openvino_encoder_model.xml'),
        weights=os.path.join(ENC_DIR, 'openvino_encoder_model.bin'),
    )
    enc = core.compile_model(enc_model, 'GPU.0',
                             {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f16'})

    tok = AutoTokenizer.from_pretrained(SRC_DIR, fix_mistral_regex=True)
    fe = WhisperFeatureExtractor.from_pretrained(SRC_DIR)

    msgs = [{'role': 'system', 'content': ''},
            {'role': 'user', 'content': [{'type': 'audio', 'audio': ''}]}]
    text = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    ids_left, ids_right = text.split('<|audio_start|><|audio_pad|><|audio_end|>')
    ids_left = tok.encode(ids_left, add_special_tokens=False)
    ids_right = tok.encode(ids_right, add_special_tokens=False)
    vocab = tok.get_vocab()
    pad_id = vocab.get('<|audio_pad|>', 151646)

    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == 16000

    samples = []
    for start, end, label in CALIB_SEGMENTS:
        seg = audio[int(start * sr):int(end * sr)]
        chunk_samples = int(CHUNK_SIZE_SEC * sr)
        n_chunks = (len(seg) + chunk_samples - 1) // chunk_samples
        for ci in CALIB_CHUNK_IDS:
            c = ci if ci >= 0 else n_chunks + ci
            e = min((c + 1) * chunk_samples, len(seg))
            audio_accum = seg[:e]
            feats_real, _, n_real, N_audio = extract_audio_features(fe, audio_accum, return_torch=False)
            mel = feats_real[0]
            mel_len = mel.shape[1]
            assert mel_len <= 2400, f'{label} chunk {c}: mel_len {mel_len} > 2400'
            enc_in = np.zeros((1, 128, 2400), dtype=np.float32)
            enc_in[0, :, :mel_len] = mel
            n_valid = np.array([N_audio], dtype=np.int32)
            out = enc.create_infer_request().infer([enc_in, n_valid])
            ehs = out[0][:, :N_audio, :]
            ids = list(ids_left) + [pad_id] * N_audio + list(ids_right)
            samples.append({
                'input_ids': np.array([ids], dtype=np.int64),
                'encoder_hidden_states': ehs,
                'beam_idx': np.array([0], dtype=np.int32),
            })
            log(f'  [calib] {label} chunk {c}: N_audio={N_audio} ids_len={len(ids)}')
    log(f'[calib] {len(samples)} samples')
    return Dataset(samples)


# ---------------------------------------------------------------- 工具
def find_matmul_names_by_layer(model):
    """返回 {layer_idx: [MatMul friendly names]} (只数 transformer 层的 linear)."""
    per_layer = {}
    for op in model.get_ops():
        if op.get_type_name() != 'MatMul':
            continue
        name = op.get_friendly_name()
        m = re.match(LAYER_MM_PREFIX + r'(\d+)\.', name)
        if m:
            per_layer.setdefault(int(m.group(1)), []).append(name)
    return per_layer


def make_ignore_pattern(layers):
    """re.match 锚定开头; 匹配层号在 layers 中的 MatMul."""
    nums = '|'.join(str(i) for i in sorted(layers))
    return LAYER_MM_PREFIX + f'({nums})\\.'


def verify_ignored(model, ignored_names, per_layer_before):
    """压缩后检查被忽略的 MatMul 权重是否仍为 FP16 (未量化)."""
    n_fp16 = 0
    n_int8 = 0
    bad = []
    for op in model.get_ops():
        name = op.get_friendly_name()
        if name not in ignored_names:
            continue
        # 权重输入: 沿来源向上找 Constant
        node = None
        try:
            src = op.input(1).get_source_output()
            node = src.get_node()
            # DQ 格式: Constant(i8) -> Convert -> Subtract -> Multiply
            # FP16 格式: Constant(f16) -> Convert(f16)
            for _ in range(3):
                if node is None:
                    break
                if node.get_type_name() == 'Constant':
                    dt = node.data.dtype
                    if dt in (np.int8, np.uint8, np.int32):
                        n_int8 += 1
                        bad.append(name)
                    else:
                        n_fp16 += 1
                    break
                # 继续向上
                try:
                    src = node.input(0).get_source_output()
                    node = src.get_node()
                except Exception:
                    break
        except Exception:
            pass
    return n_fp16, n_int8, bad


# ---------------------------------------------------------------- 变体定义
VARIANTS = {
    'mix4': dict(
        desc='INT8_ASYM + 层 0,1,26,27 FP16',
        kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM),
        ignore_layers=[0, 1, 26, 27],
    ),
    'mix8': dict(
        desc='INT8_ASYM + 层 0-3,24-27 FP16',
        kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM),
        ignore_layers=[0, 1, 2, 3, 24, 25, 26, 27],
    ),
    'awq8': dict(
        desc='INT8_ASYM + AWQ + 校准集',
        kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM,
                    awq=True, subset_size=12),
        need_calib=True,
    ),
    'gptq8': dict(
        desc='INT8_ASYM + GPTQ + 校准集',
        kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM,
                    gptq=True, subset_size=12),
        need_calib=True,
    ),
    'sens10': dict(
        desc='INT8_ASYM + ratio=0.10 + 权重误差敏感度 (自动 per-layer)',
        kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM,
                    ratio=0.10, subset_size=12,
                    sensitivity_metric=nncf.SensitivityMetric.WEIGHT_QUANTIZATION_ERROR),
    ),
    'pergroup8': dict(
        desc='INT8_ASYM per-group g128',
        kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM,
                    group_size=128),
    ),
    'int4awq': dict(
        desc='INT4_SYM per-group g128 + AWQ',
        kwargs=dict(mode=nncf.CompressWeightsMode.INT4_SYM,
                    group_size=128, all_layers=True,
                    awq=True, subset_size=12),
        need_calib=True,
    ),
    'int4awqmix': dict(
        desc='INT4_SYM per-group g128 + AWQ + 层 0,1,26,27 FP16',
        kwargs=dict(mode=nncf.CompressWeightsMode.INT4_SYM,
                    group_size=128, all_layers=True,
                    awq=True, subset_size=12),
        ignore_layers=[0, 1, 26, 27],
        need_calib=True,
    ),
    # ---- 敏感度画像: 前/后 N 层单独保 FP16, 用于定位最敏感的位置 ----
    'mixf2': dict(desc='INT8_ASYM + 前 2 层 FP16 (0,1)', ignore_layers=[0, 1],
                  kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM)),
    'mixl2': dict(desc='INT8_ASYM + 后 2 层 FP16 (26,27)', ignore_layers=[26, 27],
                  kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM)),
    'mixf4': dict(desc='INT8_ASYM + 前 4 层 FP16 (0-3)', ignore_layers=[0, 1, 2, 3],
                  kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM)),
    'mixl4': dict(desc='INT8_ASYM + 后 4 层 FP16 (24-27)', ignore_layers=[24, 25, 26, 27],
                  kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM)),
    'mixf8': dict(desc='INT8_ASYM + 前 8 层 FP16 (0-7)', ignore_layers=list(range(0, 8)),
                  kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM)),
    'mixl8': dict(desc='INT8_ASYM + 后 8 层 FP16 (20-27)', ignore_layers=list(range(20, 28)),
                  kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM)),
    # ---- 精度天花板探测 (RTF 可能 > 0.8, 仅供取舍参考) ----
    'mix12': dict(desc='INT8_ASYM + 12 层 FP16 (0-5, 22-27)',
                  ignore_layers=list(range(0, 6)) + list(range(22, 28)),
                  kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM)),
    'mix16': dict(desc='INT8_ASYM + 16 层 FP16 (0-7, 20-27)',
                  ignore_layers=list(range(0, 8)) + list(range(20, 28)),
                  kwargs=dict(mode=nncf.CompressWeightsMode.INT8_ASYM)),
}


def export_variant(name, spec, calib):
    dst = f'models/ov-{name}-past'
    log('')
    log(f'=== [{name}] {spec["desc"]} ===')
    log(f'  dst: {dst}')
    t0 = time.perf_counter()

    log('  loading FP16 decoder IR ...')
    model = ov.Core().read_model(f'{SRC_DIR}/openvino_decoder_model.xml')

    per_layer = find_matmul_names_by_layer(model)
    n_layers = len(per_layer)
    counts = {li: len(v) for li, v in sorted(per_layer.items())}
    log(f'  layers found: {n_layers}, MatMuls/layer: {sorted(set(counts.values()))}')
    if n_layers != 28:
        log(f'  WARN: expected 28 layers, got {n_layers}')

    kwargs = dict(spec['kwargs'])
    ignored_names = set()
    if spec.get('ignore_layers'):
        pat = make_ignore_pattern(spec['ignore_layers'])
        for li in spec['ignore_layers']:
            ignored_names.update(per_layer.get(li, []))
        log(f'  ignore pattern: {pat}')
        log(f'  ignored MatMuls: {len(ignored_names)} '
            f'(layers {spec["ignore_layers"]} × {sorted(set(counts.values()))})')
        kwargs['ignored_scope'] = IgnoredScope(patterns=[pat])
    if spec.get('need_calib'):
        kwargs['dataset'] = calib

    log('  compress_weights ...')
    t1 = time.perf_counter()
    compressed = nncf.compress_weights(model, **kwargs)
    log(f'  compression took {time.perf_counter()-t1:.1f}s')

    if ignored_names:
        n_fp16, n_int8, bad = verify_ignored(compressed, ignored_names, per_layer)
        log(f'  verify ignored: fp16={n_fp16} int8={n_int8} (expect int8=0)')
        if bad:
            log(f'  !! BAD (still quantized): {bad[:5]}')

    os.makedirs(dst, exist_ok=True)
    log('  saving IR ...')
    t2 = time.perf_counter()
    ov.save_model(compressed, f'{dst}/openvino_decoder_model.xml')
    log(f'  save took {time.perf_counter()-t2:.1f}s')

    for f in os.listdir(SRC_DIR):
        if f.startswith('openvino_decoder_model.'):
            continue
        src = os.path.join(SRC_DIR, f)
        if os.path.isfile(src) and not os.path.exists(os.path.join(dst, f)):
            shutil.copy2(src, os.path.join(dst, f))

    bin_mb = os.path.getsize(f'{dst}/openvino_decoder_model.bin') / 1024 / 1024
    log(f'  DONE [{name}] IR {bin_mb:.1f} MB, total {time.perf_counter()-t0:.1f}s')
    return dict(variant=name, desc=spec['desc'], ir_mb=round(bin_mb, 1),
                wall_s=round(time.perf_counter() - t0, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variants', nargs='*', default=list(VARIANTS.keys()))
    args = ap.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    log(f'[c045-export] variants: {args.variants}')
    log(f'[c045-export] updated: {time.strftime("%Y-%m-%d %H:%M")}')

    calib = None
    if any(VARIANTS[v].get('need_calib') for v in args.variants):
        log('[c045-export] building calibration set ...')
        t0 = time.perf_counter()
        calib = build_calibration()
        log(f'[c045-export] calibration done in {time.perf_counter()-t0:.1f}s')

    results = []
    for v in args.variants:
        spec = VARIANTS[v]
        try:
            results.append(export_variant(v, spec, calib))
        except Exception as e:
            log(f'  !! [{v}] FAILED: {type(e).__name__}: {e}')
            log(traceback.format_exc())
            results.append(dict(variant=v, desc=spec['desc'], error=f'{type(e).__name__}: {e}'))

    out = 'reports/c045_export/results.json'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log(f'[c045-export] → {out}')
    log('[c045-export] ALL DONE')


if __name__ == '__main__':
    main()
