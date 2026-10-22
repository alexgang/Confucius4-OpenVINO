"""c085a_smoke_all_npu.py — C-085#0：先确认「enc@NPU + dec@NPU」能跑通再谈端到端。

用户场景：**完全无 GPU 的台式机，只有 CPU + NPU**。这是C-082/C-083 矩阵里
标为「不跑」的那一格，但矩阵里的不跑理由是「省 GPU 的上界只有 7.37 pp」
—— 那个前提在「一个 GPU 都没有」的机器上不成立，所以本格必须重新实测。

## 为什么这个脚本能直接把 encoder 也放上 NPU

`SegmentEncoderOVBackend.encode_audio` 的输入本来就是**静态形状**：
    enc_in(1, 128, 2400) f32  ← 补零到 MAX_FRAMES
    n_valid   (1,)int32     ← 真实有效长度
这正是 C-069c 验证过的「冻结形状」形态（原始动态版 NPU 编译报
`Reshape 'aten::view/Reshape' expected exactly 1 dynamic output bound dimension, got 3`）。
所以只需把 `device` 传成 `"NPU"`，不需要重新导出 IR。

## 这一步只做 smoke，不做端到端

按 C-080 的教训：compile 成功是假阳性，必须实跑。三件事：
  1. encoder 编译到 NPU 并实跑，看输出形状 (1, N_audio, 2048)；
  2. 与 CPU 上的同一段对比 cosine（验证 NPU encoder 数值正确）；
  3. 转写是否是人话 —— 这是唯一能立刻暴露接线错误的信号。

输出：reports/c085a_smoke_all_npu.json
"""
import json
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

SR = 16000
START_SEC = 720
SEG_SEC = 13.0
OUT = 'reports/c085a_smoke_all_npu.json'


def make_all_npu_backend(encoder_dir, decoder_dir, aux_dir='models/ov-int8-past'):
    """构造 enc@NPU + dec@NPU 的 backend。

    C-085 踩到的坑：直接 `compile_model(enc_model, 'NPU')` 会报
    `IE.Reshape doesn't support dynamic shapes` —— 生产 encoder IR 的
    `input_features` 在 XML 里是**动态维** `[?,?,?]`，而实际喂的却是补零后的
    `[1,128,2400]`。C-069c 处理单输入 IR 时用
    `model.reshape({model.input(0): ov.PartialShape([1,128,2400])})` 冻结成功；
    本生产 IR 是**双输入**（+ `n_valid`），**两个端口都要冻**。

    实现方式：先用父类正常构造（device='CPU'，只为拿到 tokenizer / 特征提取器 /
    prompt 模板 / embedding 表这些与设备无关的部分），随后把 encoder 与decoder
    各自重新编译到 NPU 并替换。不改动共享的 `segment_encoder_backend.py`。
    """
    import openvino as ov
    from npu_embeds_backend import (
        NPUEmbedsDecoderBackend, _load_embed_table)
    from segment_encoder_backend import SegmentEncoderOVBackend, MAX_FRAMES

    # 1) 父类构造：设备无关的部分（tokenizer/特征提取器/模板/embedding 表）
    be = NPUEmbedsDecoderBackend.__new__(NPUEmbedsDecoderBackend)
    SegmentEncoderOVBackend.__init__(
        be, encoder_dir=encoder_dir, decoder_dir=aux_dir, device='CPU')
    be._dec_dir = decoder_dir
    # embedding 表 + 模板 embedding（父类构造不做这两件事）
    be._W = _load_embed_table()
    assert be._W.shape == (151936, 2048), be._W.shape
    ids_left, ids_right = be._prompt_template_ids
    be._emb_left = np.ascontiguousarray(be._W[ids_left], dtype=np.float32)
    be._emb_right = np.ascontiguousarray(be._W[ids_right], dtype=np.float32)
    be.probe = {'enc_ms': [], 'prefill_ms': [], 'decode_ms': [],
                'n_decode': [], 'prompt_len': [], 'n_audio': [],
                'budget': [], 'out_tokens': []}

    core = ov.Core()
    core.set_property({'CACHE_DIR': './reports/npu_cache'})

    # 2) encoder：冻结两个端口的形状后编到 NPU
    enc_model = core.read_model(
        model=os.path.join(encoder_dir, 'openvino_encoder_model.xml'),
        weights=os.path.join(encoder_dir, 'openvino_encoder_model.bin'))
    smap = {
        enc_model.input(0): ov.PartialShape([1, 128, MAX_FRAMES]),
        enc_model.input(1): ov.PartialShape([1]),
    }
    frozen = enc_model.reshape(smap)
    if frozen is None:            # OV 有时原地修改并返回 None
        frozen = enc_model
    print('  冻结后 encoder 端口:',
          [(p.get_any_name(), str(p.get_partial_shape()))
           for p in frozen.inputs], flush=True)
    t0 = time.perf_counter()
    be.enc = core.compile_model(frozen, 'NPU',
                                {'CACHE_DIR': './reports/npu_cache'})
    be.npu_enc_compile_s = round(time.perf_counter() - t0, 1)
    be.enc_infer = be.enc.create_infer_request()
    be._device = 'NPU'

    # 3) decoder：cleanie INT8 编到 NPU（NPUW）
    props = {'NPU_USE_NPUW': 'YES', 'NPUW_LLM': 'YES',
             'NPUW_LLM_MAX_PROMPT_LEN': '512',
             'NPUW_LLM_MIN_RESPONSE_LEN': '64',
             'CACHE_DIR': './reports/npu_cache'}
    be._npu_props = props
    xml = os.path.join(decoder_dir, 'openvino_model.xml')
    t0 = time.perf_counter()
    be.dec = core.compile_model(xml, 'NPU', props)
    be.npu_compile_s = round(time.perf_counter() - t0, 1)
    be.dec_xml = xml
    be._port_names = {p.get_any_name() for p in be.dec.inputs}
    return be


def main():
    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    a = audio[SR * START_SEC:SR * (START_SEC + int(SEG_SEC))]

    rep = {'note': 'C-085#0 smoke：enc@NPU + dec@NPU（完全无 GPU 形态）。',
           'slice': [START_SEC, int(START_SEC + SEG_SEC)],
           'seg_dur_s': SEG_SEC}

    # ── 1) CPU 上的 encoder 参照（数值对照用）──────────────────────
    print('[c085a] 先在 CPU 上取一份 encoder 参照...', flush=True)
    from segment_encoder_backend import SegmentEncoderOVBackend
    be_cpu = SegmentEncoderOVBackend(device='CPU')
    t0 = time.perf_counter()
    ehs_cpu, n_real, N_audio = be_cpu.encode_audio(a)
    rep['cpu_encode_ms'] = round((time.perf_counter() - t0) * 1000, 1)
    rep['cpu_encoder_output_shape'] = list(ehs_cpu.shape)
    rep['n_audio'] = int(N_audio)
    print(f'  CPU: {rep["cpu_encode_ms"]} ms, shape={ehs_cpu.shape}, '
          f'N_audio={N_audio}', flush=True)

    # ── 2) NPU 上的 encoder + decoder（cleanie INT8）────────────────
    print('\n[c085a] 现在编 NPU encoder + NPU cleanie decoder...', flush=True)
    t0 = time.perf_counter()
    be = make_all_npu_backend('models/ov-encoder-segment-reviewer',
                             'models/qwen3-lm-int8sym-cleanie-ov')
    rep['backend_init_s'] = round(time.perf_counter() - t0, 1)
    rep['npu_encoder_compile_s'] = be.npu_enc_compile_s
    rep['npu_decoder_compile_s'] = be.npu_compile_s
    rep['encoder_device'] = be._device
    rep['decoder_device'] = 'NPU'
    print(f'  backend 初始化 {rep["backend_init_s"]}s '
          f'(enc 编译 {be.npu_enc_compile_s}s / dec 编译 {be.npu_compile_s}s)',
          flush=True)

    # ── 3) NPU encoder 实跑 + 与 CPU cosine ───────────────────────
    for _ in range(2):        # warmup（NPU 首次调用含额外开销）
        be.encode_audio(a)
    t0 = time.perf_counter()
    ehs_npu, _, N2 = be.encode_audio(a)
    npu_ms = (time.perf_counter() - t0) * 1000
    rep['npu_encode_ms'] = round(npu_ms, 1)
    rep['npu_encoder_output_shape'] = list(ehs_npu.shape)
    print(f'  NPU encoder: {npu_ms:.1f} ms, shape={ehs_npu.shape}', flush=True)

    a_flat = np.asarray(ehs_cpu).reshape(-1).astype(np.float64)
    b_flat = np.asarray(ehs_npu).reshape(-1).astype(np.float64)
    cos = float(a_flat @ b_flat / (np.linalg.norm(a_flat) * np.linalg.norm(b_flat)))
    rep['cpu_vs_npu_encoder_cosine'] = round(cos, 6)
    rep['encoder_npu_correct'] = bool(cos > 0.99)
    print(f'  CPU vs NPU encoder cosine = {cos:.6f}', flush=True)

    # ── 4) 转写是不是人话 ─────────────────────────────────────────
    from seg_stream import SegmentedStreamer
    segs = SegmentedStreamer(
        None, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64)._plan_segments(a)
    w = a[segs[0][0]:segs[0][1]]
    for k in ('enc_ms', 'prefill_ms', 'decode_ms', 'out_tokens'):
        be.probe[k].clear()
    t0 = time.perf_counter()
    text, out_segs = SegmentedStreamer(
        be, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
        unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
        finish_budget='max64', enable_hallucination_reset=False).run(w)
    wall = time.perf_counter() - t0
    rep['smoke_text'] = text[:600]
    rep['smoke_wall_s'] = round(wall, 2)
    rep['smoke_rtf'] = round(wall / (len(w) / SR), 3)
    rep['looks_like_speech'] = bool(
        any(c.isalpha() for c in text) and len(text) > 20)
    for k in ('enc_ms', 'prefill_ms', 'decode_ms'):
        v = be.probe[k]
        if v:
            rep[k + '_median'] = round(float(np.median(v)), 1)
            rep[k + '_n'] = len(v)
    print('\n' + '=' * 70)
    print(f'SMOKE RTF={rep["smoke_rtf"]} wall={rep["smoke_wall_s"]}s '
          f'人话={rep["looks_like_speech"]}')
    for k in ('enc_ms', 'prefill_ms', 'decode_ms'):
        if k + '_median' in rep:
            print(f'  {k:10s} 中位 {rep[k+"_median"]:>8} ms  (n={rep[k+"_n"]})')
    print('TRANSCRIPT:', text[:500])
    print('=' * 70, flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('saved ->', OUT)
    ok = rep['looks_like_speech'] and rep['encoder_npu_correct']
    print('\n[c085a]', 'PASS —— 可以进端到端' if ok else 'FAIL —— 先修，别跑端到端')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
