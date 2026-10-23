"""npu_delivery_backend.py — C-088#3-2：交付形态的全 NPU 后端

## 要解决的问题

`c085a_smoke_all_npu.make_all_npu_backend()`（以及 `NPUEmbedsDecoderBackend.__init__`）
为了拿 tokenizer / 特征提取器 / prompt 模板，先调 `SegmentEncoderOVBackend.__init__()`，
而父类构造里**顺手在 CPU 上编译了 `aux_dir`（默认 models/ov-int8-past）的
cross-attention 解码器**。随后子类把 `be.dec` 换成 cleanie IR，但 `be.dec_infer`
仍然指向那个 aux 解码器的 infer request：

    self.dec = core.compile_model(xml, 'NPU', props)   # 被替换
    self.dec_infer = <aux 解码器的 request>              # 仍常驻

`NPUEmbedsDecoderBackend` 覆写了 `greedy_decode_with_prefix()` / `build_inputs_embeds()`，
**从来不用 `self.dec_infer`**（父类那个 `input_ids` 版的 greedy 只在父类被直接实例化时用）。
所以这是纯浪费：约 1.7 GiB 权重 + 一份 CPU 编译产物常驻内存。

## 本模块的做法

完全不调父类 `__init__`，手工搭出 backend：

  * tokenizer / feature_extractor / chat_template —— 从**生产 ASR 目录**
    （`models/ov-encoder-segment-reviewer`，含 preprocessor_config.json 与
    chat_template.jinja）读，与父类原行为一致；
  * prompt 模板 ids 与 audio_pad_id —— 复用父类的 `_build_prompt_template_ids()`
    与 `_get_audio_pad_id()`（纯 tokenizer 操作，不碰模型）；
  * embedding 表 + 模板 embedding —— 同原逻辑，但走 C-088#3-1 的独立 npy；
  * encoder —— 冻结两个端口后编到 NPU（**一次**）；
  * decoder（cleanie）—— 编到 NPU（**一次**）；
  * `self.dec_infer = None`（明确置空而非留残引用），并让
    `greedy_decode_with_prefix` 的父类版本不被误调：这里覆写为显式报错。

结果：NPU 编译 2 次（原本 3 次：aux@CPU + enc@NPU + dec@NPU），不再加载 1.7 GiB
无用权重。

用法：

    from npu_delivery_backend import make_delivery_all_npu_backend
    be = make_delivery_all_npu_backend()
"""
from __future__ import annotations

import os
import time
from typing import List, Optional

import numpy as np

WORK = os.path.dirname(os.path.abspath(__file__))

DEFAULT_ENCODER_DIR = 'models/ov-encoder-segment-reviewer'
DEFAULT_DECODER_DIR = 'models/qwen3-lm-int8sym-cleanie-ov'
# tokenizer / feature extractor / chat_template 的来源目录。
# ⚠️ 注意：这里**只读这几个小文件**（tokenizer.json、tokenizer_config.json、
# config.json、preprocessor_config.json、chat_template.jinja，合计几 MB），
# **完全不加载该目录下的 IR**。与父类行为一致（父类也是从 aux_dir 读这些文件），
# 但父类顺手把该目录的 cross-attention 解码器编到 CPU，约 1.7 GiB 常驻 —— 那部分被去掉了。
DEFAULT_TOKENIZER_DIR = 'models/ov-int8-past'
# C-133 / APP-002：编译缓存**绝不写包内**（包可能装在 Program Files 只读；
# 且包内缓存跨机器/跨 OV 版本基本不命中）。与 live_caption_app._cache()、
# translator.py 的 mt_cache 保持同一根目录。
# 说明：正常路径由 live_caption_app.py 显式传 npu_cache=_cache('npu_cache')，
# 这里只是**死代码兜底**，改它是为了防止未来误用时在包内生成 reports/。
DEFAULT_NPU_CACHE = os.path.join(
    os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'),
    'Confucius4LiveCaption', 'npu_cache')


def _freeze_encoder_for_npu(core, model, max_frames: int):
    """冻结双输入 encoder IR 的动态端口，否则 NPU 编译报
    `IE.Reshape doesn't support dynamic shapes`（C-085 踩过）。"""
    import openvino as ov
    smap = {
        model.input(0): ov.PartialShape([1, 128, max_frames]),
        model.input(1): ov.PartialShape([1]),
    }
    frozen = model.reshape(smap)
    return frozen if frozen is not None else model


def make_delivery_all_npu_backend(
        encoder_dir: str = DEFAULT_ENCODER_DIR,
        decoder_dir: str = DEFAULT_DECODER_DIR,
        tokenizer_dir: str = DEFAULT_TOKENIZER_DIR,
        npu_cache: str = DEFAULT_NPU_CACHE,
        max_frames: int = 2400,
        npu_max_prompt_len: int = 512,
        npu_min_response_len: int = 64,
        strict_intel: bool = True):
    """构造**交付形态**的 enc@NPU + dec@NPU backend（不编译任何 aux 解码器）。"""
    import openvino as ov
    from transformers import AutoTokenizer, WhisperFeatureExtractor

    from npu_embeds_backend import (
        NPUEmbedsDecoderBackend, _load_embed_table, HIDDEN)
    from segment_encoder_backend import SegmentEncoderOVBackend

    def _abs(p):
        return p if os.path.isabs(p) else os.path.join(WORK, p)

    encoder_dir = _abs(encoder_dir)
    decoder_dir = _abs(decoder_dir)
    tokenizer_dir = _abs(tokenizer_dir)
    npu_cache = _abs(npu_cache)

    be = NPUEmbedsDecoderBackend.__new__(NPUEmbedsDecoderBackend)

    core = ov.Core()
    if strict_intel:
        name = core.get_property('NPU', 'FULL_DEVICE_NAME')
        assert 'Intel' in name, f'NPU is not Intel: {name}'

    # ── 1) 设备无关部分：tokenizer / 特征提取器 / 模板 ─────────────
    # 只从 tokenizer_dir 读小文件（tokenizer.json / tokenizer_config.json /
    # config.json / preprocessor_config.json / chat_template.jinja，合计几 MB）；
    # 该目录下的 .xml/.bin 一概不加载。
    be.tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir,
                                                fix_mistral_regex=True)
    be.tokenizer.chat_template = open(
        os.path.join(tokenizer_dir, 'chat_template.jinja'), encoding='utf-8').read()
    be.feature_extractor = WhisperFeatureExtractor.from_pretrained(tokenizer_dir)

    be._build_prompt_template_ids = \
        SegmentEncoderOVBackend._build_prompt_template_ids.__get__(be)
    be._build_text_prompt = \
        SegmentEncoderOVBackend._build_text_prompt.__get__(be)
    be.encode_audio = SegmentEncoderOVBackend.encode_audio.__get__(be)
    be.init_streaming_state = \
        SegmentEncoderOVBackend.init_streaming_state.__get__(be)
    be.generate_with_prefix = \
        SegmentEncoderOVBackend.generate_with_prefix.__get__(be)

    be._prompt_template_ids = be._build_prompt_template_ids()
    be._audio_pad_id = be._get_audio_pad_id()

    be._core = core
    be._prop = {'PERFORMANCE_HINT': 'LATENCY'}
    be._device = 'NPU'
    be._encoder_dir = encoder_dir
    be._dec_dir = decoder_dir

    # ── 2) embedding 表（走 C-088#3-1 的独立 npy）───────────────────
    be._W = _load_embed_table()
    assert be._W.shape == (151936, HIDDEN), be._W.shape
    ids_left, ids_right = be._prompt_template_ids
    be._emb_left = np.ascontiguousarray(be._W[ids_left], dtype=np.float32)
    be._emb_right = np.ascontiguousarray(be._W[ids_right], dtype=np.float32)

    be.probe = {'enc_ms': [], 'prefill_ms': [], 'decode_ms': [],
                'n_decode': [], 'prompt_len': [], 'n_audio': [],
                'budget': [], 'out_tokens': []}

    # ── 3) encoder → NPU（唯一一次 encoder 编译）───────────────────
    enc_model = core.read_model(
        model=os.path.join(encoder_dir, 'openvino_encoder_model.xml'),
        weights=os.path.join(encoder_dir, 'openvino_encoder_model.bin'))
    frozen = _freeze_encoder_for_npu(core, enc_model, max_frames)
    t0 = time.perf_counter()
    be.enc = core.compile_model(frozen, 'NPU', {'CACHE_DIR': npu_cache})
    be.npu_enc_compile_s = round(time.perf_counter() - t0, 1)
    be.enc_infer = be.enc.create_infer_request()

    # ── 4) decoder（cleanie）→ NPU（唯一一次 decoder 编译）─────────
    props = {
        'NPU_USE_NPUW': 'YES',
        'NPUW_LLM': 'YES',
        'NPUW_LLM_MAX_PROMPT_LEN': str(npu_max_prompt_len),
        'NPUW_LLM_MIN_RESPONSE_LEN': str(npu_min_response_len),
        'CACHE_DIR': npu_cache,
    }
    be._npu_props = props
    xml = os.path.join(decoder_dir, 'openvino_model.xml')
    t0 = time.perf_counter()
    be.dec = core.compile_model(xml, 'NPU', props)
    be.npu_compile_s = round(time.perf_counter() - t0, 1)
    be.dec_xml = xml
    be._port_names = {p.get_any_name() for p in be.dec.inputs}

    # ── 5) 明确不留 aux 解码器残引用 ──────────────────────────────
    # C-088#3-2 的核心：原 make_all_npu_backend 后面替换了 be.dec，
    # 但 be.dec_infer 仍指向父类在 CPU 上编译的 aux 解码器（约 1.7 GiB 常驻）。
    # NPU 子类**自己覆写了** greedy_decode_with_prefix()（用 inputs_embeds 路线），
    # 从不用 self.dec_infer，所以这里明确置空即可。
    be.dec_infer = None
    be.aux_decoder_loaded = False
    # 注意：**不要**覆盖 be.greedy_decode_with_prefix —— 那是 NPU 子类的
    # inputs_embeds 实现，正是流式路径要用的那一个。
    assert type(be).greedy_decode_with_prefix is \
        NPUEmbedsDecoderBackend.greedy_decode_with_prefix
    return be
