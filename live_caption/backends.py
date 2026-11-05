"""backends.py — C-006 step2/3：与流式循环解耦的 ASR 后端

两个 backend 都实现同一接口 `generate_with_prefix(prompt_raw, audio_accum,
prefix_text, max_new_tokens) -> gen_text`，让 streaming_asr.py 的 LSP 主循环
（C-001：原样抄自 third_party/Confucius4-R2T2/r2t2/r2t2_asr.py 第 302-578 行）
对两个 backend 完全一致，是 C-006 step3 的 parity 前提。

- TorchBackend：qwen_asr Qwen3ASRModel（backend='transformers'，CPU FP32），
  作 per-chunk golden。
- OVBackend：optimum-intel 导出的 `models/ov-fp16-past` IR（stateful decoder
  with past KV cache），作生产推理路径。
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

import numpy as np


# ── 共享：特征提取（C-010 #1） ──────────────────────────────────────
def _qwen3_get_feat_extract_output_lengths(input_lengths):
    """直接复制 qwen_asr 的同名函数，避免依赖 qwen_asr 包。"""
    input_lengths_leave = input_lengths % 100
    feat_lengths = (input_lengths_leave - 1) // 2 + 1
    output_lengths = ((feat_lengths - 1) // 2 + 1 - 1) // 2 + 1 + (input_lengths // 100) * 13
    return output_lengths


def extract_audio_features(fe, audio: np.ndarray, *, return_torch: bool = False):
    """统一特征提取：不补齐到 30s，返回真实长度的 mel。

    Parameters
    ----------
    fe : WhisperFeatureExtractor
    audio : np.ndarray, shape (T,) float32
    return_torch : bool
        True  → input_features / feature_attention_mask 用 torch.tensor (TorchBackend)
        False → input_features 用 np.ndarray，feature_attention_mask=None (OVBackend
                编码器只接受 input_features，attention 在外部按真实帧数切片)

    Returns
    -------
    input_features, feature_attention_mask, n_real_frames, N_audio
        n_real_frames : 真实 mel 帧数（=1 + len(audio)//hop_length）
        N_audio : 编码器输出的 audio token 数（=qwen3 公式的真实值）
    """
    # C-010 #1：padding='do_not_pad' 避免 30s 填充；truncation=False；attention_mask=True
    out = fe(
        list(audio), sampling_rate=SAMPLE_RATE,
        return_tensors="np",
        padding="do_not_pad", truncation=False, return_attention_mask=True,
    )
    feats = out["input_features"]            # (1, 128, T_mel)
    mask = out["attention_mask"]              # (1, T_mel)
    n_real = int(mask[0].sum())              # 真实有效帧数
    # 切到真实长度（与 qwen_asr 内部 audio_tower 处理一致）
    feats_real = feats[:, :, :n_real]
    # qwen_asr 公式：audio_tower 内 CNN 下采样后的 audio token 数
    N_audio = int(_qwen3_get_feat_extract_output_lengths(np.array([n_real]))[0])

    if return_torch:
        # 🔴🔴🔳 APP-069⑤ 清理项 1：torch 实现已搬到 `backends_torch.py`
        #   （**开发专用**；客户包不含 torch）⇒ 这里**懒加载**，
        #   找不到 torch 时报**清楚的错误**（而不是裸 ModuleNotFoundError）。
        from backends_torch import extract_audio_features_torch
        return extract_audio_features_torch(fe, audio, n_real, N_audio)
    return (feats_real.astype(np.float32),
            mask[:, :n_real].astype(np.int64),
            n_real, N_audio)


# ── 常量 ──────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
AUDIO_START = 151669  # <|audio_start|>
AUDIO_END   = 151670  # <|audio_end|>
AUDIO_PAD   = 151676  # <|audio_pad|>
EOS_IDS = [151643, 151645]

# 流式生成参数组 A（与 audio.cpp spec 一致：320ms / 2 / 5 / 32）
DEFAULT_PARAMS = dict(
    chunk_size_sec=0.32,
    unfixed_chunk_num=2,
    unfixed_token_num=5,
    max_new_tokens=32,
    rollback_punctuation=False,
)


@dataclass
class ASRStreamingState:
    """与官方 r2t2/ASRStreamingState 同名字段（去 vLLM-only 字段）。"""
    unfixed_chunk_num: int
    unfixed_token_num: int
    chunk_size_sec: float
    chunk_size_samples: int

    chunk_id: int = 0
    buffer: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float32))
    audio_accum: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float32))

    prompt_raw: str = ""
    force_language: Optional[str] = None
    context: str = ""

    language: str = ""
    text: str = ""
    _raw_decoded: str = ""


# ── Backend 接口 ──────────────────────────────────────────────────────
class ASRBackend:
    """流式 ASR 后端接口（C-001 + C-006 step3 的核心抽象）。"""

    name: str = "abstract"

    def init_streaming_state(self, *, context: str = "",
                             language: Optional[str] = None,
                             unfixed_chunk_num: int,
                             unfixed_token_num: int,
                             chunk_size_sec: float) -> ASRStreamingState:
        raise NotImplementedError

    def generate_with_prefix(self, state: ASRStreamingState,
                             audio_accum: np.ndarray,
                             prefix_text: str,
                             max_new_tokens: int) -> str:
        """跑一次 greedy：prompt = state.prompt_raw + prefix_text，全量 audio。
        返回 vLLM 风格的生成文本（不含 prefix 部分）。"""
        raise NotImplementedError

    def finish_streaming_transcribe(self, state: ASRStreamingState,
                                    audio_accum: np.ndarray,
                                    prefix_text: str,
                                    max_new_tokens: int) -> str:
        """最后一次刷新（音频累积到 buffer 的剩余尾段，无 padding）。"""
        return self.generate_with_prefix(state, audio_accum, prefix_text, max_new_tokens)


# ── TorchBackend：per-chunk golden ────────────────────────────────────
class TorchBackend(ASRBackend):
    """🔴🔴🔳 APP-069⑤ 清理项 1：**薄壳**（实现体在 `backends_torch.py`）。

    🔴 `backends_torch.py` 是**只给开发用**的模块（**不进客户包**）：
    客户包不含 torch ⇒ 选 torch 后端时在这里得到**清楚的错误**
    （提示改用 OpenVINO 后端），而不是 `ModuleNotFoundError`。
    """

    name = "torch"

    def __init__(self, model_dir: str = "models/hf"):
        try:
            from backends_torch import TorchBackend as _Impl
        except ImportError as e:
            raise RuntimeError(
                '需要 PyTorch 后端，但当前环境没有 backends_torch.py'
                '（客户包**不含** torch ⇒ MiniMVP 只带 OpenVINO IR）。\n'
                '请改用 OpenVINO 后端（--engine gpu_int8 / openvino）。'
                '（原始错误：%s）' % e) from e
        self._impl = _Impl(model_dir=model_dir)
        for _k in ('model', 'processor', 'tokenizer', '_torch',
                   '_hop', '_n_mels', '_prompt_template_ids'):
            setattr(self, _k, getattr(self._impl, _k, None))

    def init_streaming_state(self, **kw):
        return self._impl.init_streaming_state(**kw)

    def _build_prompt_template_ids(self):
        return self._impl._build_prompt_template_ids()

    def _build_text_prompt(self, **kw):
        return self._impl._build_text_prompt(**kw)

    def generate_with_prefix(self, state, prefix_text: str,
                             max_new_tokens: int = 256) -> str:
        return self._impl.generate_with_prefix(state, prefix_text,
                                               max_new_tokens)

    def finish_streaming_transcribe(self, state) -> str:
        return self._impl.finish_streaming_transcribe(state)


class OVBackend(ASRBackend):
    name = "openvino"

    def __init__(self, model_dir: str = "models/ov-fp16-past",
                 device: str = "GPU.0", precision: str = "f16",
                 cache_dir: str = "./ov_cache"):
        import openvino as ov
        from transformers import AutoTokenizer, WhisperFeatureExtractor
        import qwen_asr  # noqa: F401  触发 qwen3_asr 注册（preprocessor config 解析用）

        self.cfg_model_dir = model_dir
        self.cfg_device = device
        self.cfg_precision = precision

        # 设备 Intel 断言（C-002）
        core = ov.Core()
        full_name = core.get_property(device, "FULL_DEVICE_NAME")
        assert "Intel" in full_name, f"device {device} not Intel: {full_name}"
        core.set_property({"CACHE_DIR": cache_dir})
        prop = {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": precision}

        self.enc = core.compile_model(
            os.path.join(model_dir, "openvino_encoder_model.xml"),
            device, prop,
        )
        self.dec = core.compile_model(
            os.path.join(model_dir, "openvino_decoder_model.xml"),
            device, prop,
        )
        self.enc_infer = self.enc.create_infer_request()
        self.dec_infer = self.dec.create_infer_request()

        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, fix_mistral_regex=True)
        self.tokenizer.chat_template = open(
            os.path.join(model_dir, "chat_template.jinja"), encoding="utf-8",
        ).read()
        self.feature_extractor = WhisperFeatureExtractor.from_pretrained(model_dir)

        # 预构造 prompt 模板（不含 audio_pad 部分；中间插入 N 个 AUDIO_PAD）
        self._prompt_template_ids = self._build_prompt_template_ids()

    def _build_prompt_template_ids(self) -> Tuple[List[int], List[int]]:
        msgs = [
            {"role": "system", "content": ""},
            {"role": "user", "content": [{"type": "audio", "audio": ""}]},
        ]
        text = self.tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        text_left, text_right = text.split("<|audio_start|><|audio_pad|><|audio_end|>")
        ids_left = self.tokenizer.encode(text_left, add_special_tokens=False)
        ids_right = self.tokenizer.encode(text_right, add_special_tokens=False)
        return ids_left, ids_right

    def init_streaming_state(self, *, context: str = "",
                             language: Optional[str] = None,
                             unfixed_chunk_num: int,
                             unfixed_token_num: int,
                             chunk_size_sec: float) -> ASRStreamingState:
        chunk_size_samples = max(1, int(round(chunk_size_sec * SAMPLE_RATE)))
        prompt_raw = self._build_text_prompt(context=context, force_language=language)
        return ASRStreamingState(
            unfixed_chunk_num=unfixed_chunk_num,
            unfixed_token_num=unfixed_token_num,
            chunk_size_sec=chunk_size_sec,
            chunk_size_samples=chunk_size_samples,
            prompt_raw=prompt_raw,
            force_language=language,
            context=context,
        )

    def _build_text_prompt(self, *, context: str, force_language: Optional[str]) -> str:
        msgs: List[dict] = [{"role": "system", "content": context or ""},
                            {"role": "user", "content": [{"type": "audio", "audio": ""}]}]
        text = self.tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        if force_language:
            text = text + f"language {force_language}<asr_text>"
        return text

    # ── encoder + stateful greedy（C-006 step2） ────────────────────────
    def encode_audio(self, wav: np.ndarray):
        """C-010：返回 (encoder_hidden_states, n_real_frames, N_audio)。
        encoder 只接受 input_features（无 attention_mask），我们按真实长度切好再喂。"""
        feats_real, _, n_real, N_audio = extract_audio_features(
            self.feature_extractor, wav, return_torch=False,
        )
        out = self.enc({"input_features": feats_real})
        return out["last_hidden_state"], n_real, N_audio  # [1, N_audio, 2048]

    def greedy_decode_with_prefix(self, encoder_hidden_states: np.ndarray,
                                  prefix_ids: List[int],
                                  max_new_tokens: int,
                                  force_language=None) -> List[int]:
        """stateful decoder：reset_state → prefill 整条 prompt → 1 token/step。

        C-009 #2：stateful decoder cross-attention 在 prefill 时已把 ehs 存到 past 状态；
        decode 步可以传任意形状的 ehs（IR 端口要求存在），但实际不参与计算。实测
        `tiny ehs (1,1,2048)` 与 full ehs 输出完全一致，且 ~5% 速度优势。

        force_language：语种提示要进模型输入，所以按语种取 prompt 模板
        （语种后缀编码在 ids_right 末尾）。None = 自动检测，用静态模板。
        """
        ids_left, ids_right = self._build_prompt_template_ids_for(force_language)
        N_audio = int(encoder_hidden_states.shape[1])
        full_ids = list(ids_left) + [AUDIO_PAD] * N_audio + list(ids_right) + list(prefix_ids)

        # 1) reset stateful KV
        self.dec_infer.reset_state()

        # 2) prefill：把整条 prompt 喂一次，logits 取最后一个位置
        self.dec_infer.infer({
            "encoder_hidden_states": encoder_hidden_states,
            "input_ids": np.array([full_ids], dtype=np.int64),
            "beam_idx": np.array([0], dtype=np.int32),
        })
        logits = self.dec_infer.get_output_tensor(0).data  # [1, T, vocab]
        next_id = int(np.argmax(logits[0, -1]))
        out_tokens: List[int] = [next_id]
        if next_id in EOS_IDS:
            return out_tokens

        # 3) incremental decode：每次只喂新 1 个 token
        # C-009 #2：stateful cross-attention 缓存了 ehs；用 tiny ehs 占位
        ehs_dummy = np.zeros((1, 1, 2048), dtype=np.float32)
        for _ in range(max_new_tokens - 1):
            self.dec_infer.infer({
                "encoder_hidden_states": ehs_dummy,
                "input_ids": np.array([[next_id]], dtype=np.int64),
                "beam_idx": np.array([0], dtype=np.int32),
            })
            logits = self.dec_infer.get_output_tensor(0).data
            next_id = int(np.argmax(logits[0, -1]))
            if next_id in EOS_IDS:
                break
            out_tokens.append(next_id)
        return out_tokens

    def generate_with_prefix(self, state: ASRStreamingState,
                             audio_accum: np.ndarray,
                             prefix_text: str,
                             max_new_tokens: int) -> str:
        ehs, n_real, N_audio = self.encode_audio(audio_accum)
        prefix_ids = self.tokenizer.encode(prefix_text, add_special_tokens=False) if prefix_text else []
        out_ids = self.greedy_decode_with_prefix(
            ehs, prefix_ids, max_new_tokens,
            force_language=getattr(state, 'force_language', None))
        gen_text = self.tokenizer.decode(out_ids, skip_special_tokens=True)
        return gen_text


# ── HybridBackend：C-021 修复 — torch audio_tower encoder + OV stateful decoder ──
# OV IR 的 audio encoder 被 optimum-intel 的 Qwen3ASRModelPatcher 把 chunking/cu_seqlens
# 干掉了，patched 后的 encoder 用单次 1D conv + 标准 attention，与 torch 的"100-mel 分块
# CNN + cu_seqlens 窗口 attention"输出不同（cos 0.3-0.5）。OV 单 chunk 100-mel 输入时
# 与 torch 完全一致（cos=1.0），但跨 chunk 注意力丢失，导致 226 段离线 12% 循环/撞墙。
#
# 修复：编码器换回 torch model.thinker.audio_tower（CPU FP32, eager attn）拿正确 ehs；
# 解码器仍用 OV stateful with-past（GPU, 性能不变）。encoder 单次 ~700ms / 16s 音频
# （含 mel + CNN + 24 层 + proj），OV decoder 8s/60s，比纯 OV 离线慢 ~30%，但 WER
# 应回到与 torch offline / CUDA 一致。
class HybridBackend(ASRBackend):
    """🔴🔴🔳 APP-069⑤ 清理项 1：**薄壳**（实现体在 `backends_torch.py`）。

    🔴 同 `TorchBackend`：客户包不含 torch ⇒ 报**清楚的错误**。
    """

    name = "hybrid"

    def __init__(self, **kw):
        try:
            from backends_torch import HybridBackend as _Impl
        except ImportError as e:
            raise RuntimeError(
                '需要 PyTorch 混合后端，但当前环境没有 backends_torch.py'
                '（客户包**不含** torch）。请改用 OpenVINO 后端。'
                '（原始错误：%s）' % e) from e
        self._impl = _Impl(**kw)

    def init_streaming_state(self, **kw):
        return self._impl.init_streaming_state(**kw)

    def _build_prompt_template_ids(self):
        return self._impl._build_prompt_template_ids()

    def _build_text_prompt(self, **kw):
        return self._impl._build_text_prompt(**kw)

    def encode_audio(self, wav):
        return self._impl.encode_audio(wav)

    def greedy_decode_with_prefix(self, *a, **kw):
        return self._impl.greedy_decode_with_prefix(*a, **kw)

    def generate_with_prefix(self, state, prefix_text: str,
                             max_new_tokens: int = 256) -> str:
        return self._impl.generate_with_prefix(state, prefix_text,
                                               max_new_tokens)


def make_backend(name: str, **kw) -> ASRBackend:
    name = name.lower()
    if name == "torch":
        return TorchBackend(**kw)
    if name == "openvino":
        return OVBackend(**kw)
    if name == "hybrid":
        return HybridBackend(**kw)
    raise ValueError(f"unknown backend: {name}")
