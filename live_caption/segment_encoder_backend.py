"""segment_encoder_backend.py — C-039: 整段全局注意力 encoder backend

设计（per reviewer 验证）:
- 用 models/ov-encoder-segment-reviewer 整段 IR
  - 输入: input_features [1, 128, 2400] float32（24 个 100 帧块, 补零在右）
  - 输入: n_valid [1] int32（有效 encoder token 数 = aftercnn_len(frames)）
  - 输出: hidden [1, 312, 2048]（取前 n_valid 行）
- 用 models/ov-int8-past OV stateful decoder 做解码
- **不做任何窗口缓存**（全局注意力下无法复用）
- 每段最大 2400 帧 ≈ 23.9 s 音频（VAD max 20 s + flush 余量）；超出会 assert
"""
from __future__ import annotations
import os
import time
from typing import List, Optional, Tuple

import numpy as np
import openvino as ov

from backends import (
    ASRBackend, ASRStreamingState, SAMPLE_RATE,
    extract_audio_features, _qwen3_get_feat_extract_output_lengths,
)


CHUNK = 100       # mel frames per conv chunk (n_window * 2)
TOK = 13          # tokens per full chunk after the 3 stride-2 convs
MAX_CHUNKS = 24   # 24 * 100 = 2400 frames
MAX_FRAMES = MAX_CHUNKS * CHUNK  # 2400
MAX_TOKENS = MAX_CHUNKS * TOK    # 312


def aftercnn_len(n: int) -> int:
    """torch reference (modeling_qwen3_asr.py): 3 stride-2 convs over per-chunk input.
    For a single chunk of `n` mel frames (n>0), return the per-chunk token count.
    Uses closed-form: leave = n % 100; feat = (leave-1)//2 + 1;
                       ((feat-1)//2 + 1 - 1)//2 + 1 + (n//100) * 13
    """
    if n == 0:
        return 0
    leave = n % CHUNK
    feat = (leave - 1) // 2 + 1
    return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + (n // CHUNK) * TOK


def total_aftercnn_len(frames: int) -> int:
    """Total valid token count for full audio of `frames` mel frames.
    Per-chunk: each full chunk yields 13; the last partial chunk yields aftercnn_len(leave).
    """
    if frames <= 0:
        return 0
    n_full = frames // CHUNK
    leave = frames - n_full * CHUNK
    if leave == 0:
        return n_full * TOK
    return n_full * TOK + aftercnn_len(leave)


class SegmentEncoderOVBackend(ASRBackend):
    """OV 整段全局注意力 encoder + OV INT8-past stateful decoder"""

    name = "segment_ov"

    def __init__(self,
                 encoder_dir: str = "models/ov-encoder-segment-reviewer",
                 decoder_dir: str = "models/ov-int8-past",
                 device: str = "GPU.0",
                 precision: str = "f16",
                 cache_dir: str = "./ov_cache",
                 strict_intel: bool = True):
        from transformers import AutoTokenizer, WhisperFeatureExtractor

        # 设备 Intel 断言（C-002）
        # strict_intel=False 仅供 C-052「同卡对照」实验使用：本机 GPU.1 是
        # NVIDIA RTX 5050 Laptop，OpenVINO 也能在上面跑，用来把「运行时差异」
        # 和「硬件差异」分开。交付路径不受影响（默认仍要求 Intel）。
        core = ov.Core()
        full_name = core.get_property(device, "FULL_DEVICE_NAME")
        if strict_intel:
            assert "Intel" in full_name, f"device {device} not Intel: {full_name}"
        core.set_property({"CACHE_DIR": cache_dir})
        prop = {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": precision}

        # 加载 segment encoder (固定 [1,128,2400] + [1] int32)
        self._core = core
        self._prop = prop
        self._device = device
        enc_model = core.read_model(
            model=os.path.join(encoder_dir, "openvino_encoder_model.xml"),
            weights=os.path.join(encoder_dir, "openvino_encoder_model.bin"),
        )
        self.enc = core.compile_model(enc_model, device, prop)
        self.enc_infer = self.enc.create_infer_request()

        # 加载 decoder
        dec_model = core.read_model(
            model=os.path.join(decoder_dir, "openvino_decoder_model.xml"),
            weights=os.path.join(decoder_dir, "openvino_decoder_model.bin"),
        )
        self.dec = core.compile_model(dec_model, device, prop)
        self.dec_infer = self.dec.create_infer_request()

        # tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(decoder_dir, fix_mistral_regex=True)
        self.tokenizer.chat_template = open(
            os.path.join(decoder_dir, "chat_template.jinja"), encoding="utf-8",
        ).read()
        self.feature_extractor = WhisperFeatureExtractor.from_pretrained(decoder_dir)

        # 预构造 prompt 模板
        self._prompt_template_ids = self._build_prompt_template_ids()
        self._audio_pad_id = self._get_audio_pad_id()

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

    def _build_prompt_template_ids_for(self, force_language: Optional[str]
                                       ) -> Tuple[List[int], List[int]]:
        """按语种构造 prompt 模板 ids。

        **为什么需要这个**：语种提示是拼在 prompt **末尾**的
        （``text + "language {lang}<asr_text>"``），而 audio 占位符
        (``<|audio_start|><|audio_pad|><|audio_end|>``) 在 user 段中间。
        所以语种后缀落在「模板右半部分」的末尾，也就是 assistant 起始之后。

        之前 ids_right 来自**不含语种**的静态模板，导致 state.prompt_raw
        里的语种提示根本没进模型输入 —— 模型仍然自动判定语种，而解析层
        却按 force_language 处理，输出被 ``language None<asr_text>`` 之类的
        元信息污染（实测强制 English 时整段文本前面堆了 16 个该前缀）。

        这里把语种后缀直接编码进 ids_right，保证它真的进入模型。
        """
        ids_left, ids_right = self._build_prompt_template_ids()
        if not force_language:
            return ids_left, ids_right
        suffix = self.tokenizer.encode(
            f"language {force_language}<asr_text>", add_special_tokens=False)
        return ids_left, list(ids_right) + list(suffix)

    def _get_audio_pad_id(self) -> int:
        vocab = self.tokenizer.get_vocab()
        return vocab.get("<|audio_pad|>", vocab.get("<|audio_bos|>", 151646))

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

    def encode_audio(self, wav: np.ndarray):
        """整段全局注意力：补零到 2400 帧 → 一次调用 → 取前 n_valid 行
        Returns: (ehs [1, N_audio, 2048], n_real_frames, N_audio)
        """
        # 1) 提特征
        feats_real, _, n_real, N_audio = extract_audio_features(
            self.feature_extractor, wav, return_torch=False,
        )
        # feats_real: (1, 128, T_mel_real)
        mel = feats_real[0]  # (128, T_mel_real)
        mel_len = mel.shape[1]
        assert mel_len <= MAX_FRAMES, (
            f"segment too long: {mel_len} > {MAX_FRAMES} mel frames "
            f"(≈{mel_len*160/16000:.1f}s); VAD max 20s + flush 余量"
        )
        if mel_len == 0:
            return np.zeros((1, 0, 2048), dtype=np.float32), 0, 0

        # 2) 补零到 2400 帧
        enc_in = np.zeros((1, 128, MAX_FRAMES), dtype=np.float32)
        enc_in[0, :, :mel_len] = mel

        # 3) n_valid
        n_valid = np.array([N_audio], dtype=np.int32)
        # N_audio from extract_audio_features matches total_aftercnn_len(mel_len)
        assert int(N_audio) == total_aftercnn_len(mel_len), (
            f"N_audio mismatch: feature_extractor says {N_audio}, "
            f"closed-form says {total_aftercnn_len(mel_len)}"
        )

        # 4) 一次调用
        result = self.enc_infer.infer([enc_in, n_valid])
        out = result[0]  # (1, 312, 2048)
        ehs = out[:, :N_audio, :]  # (1, N_audio, 2048)
        return ehs, n_real, N_audio

    def greedy_decode_with_prefix(self, encoder_hidden_states: np.ndarray,
                                  prefix_ids: List[int],
                                  max_new_tokens: int,
                                  force_language: Optional[str] = None) -> List[int]:
        """OV stateful decoder：reset_state → prefill → 1 token/step

        force_language：语种提示要进模型输入，所以这里按语种取 prompt 模板
        （语种后缀编码在 ids_right 末尾）。None = 自动检测，用静态模板。
        """
        self.dec_infer.reset_state()

        if force_language:
            ids_left, ids_right = self._build_prompt_template_ids_for(force_language)
        else:
            ids_left, ids_right = self._prompt_template_ids
        N_audio = encoder_hidden_states.shape[1]
        # 拼 [left + audio_pad*N + right + prefix]
        audio_pad_ids = [self._audio_pad_id] * N_audio
        full_ids = ids_left + audio_pad_ids + ids_right + list(prefix_ids)
        input_ids = np.array([full_ids], dtype=np.int64)

        # 第一次 prefill：给 input_ids 和 encoder_hidden_states
        out = self.dec_infer.infer({
            "input_ids": input_ids,
            "encoder_hidden_states": encoder_hidden_states,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        logits = out["logits"] if isinstance(out, dict) else out[0]
        next_id = int(np.argmax(logits[0, -1, :]))
        generated = [next_id]

        eos_ids = {151643, 151645, self.tokenizer.eos_token_id}
        for _ in range(max_new_tokens - 1):
            if next_id in eos_ids:
                break
            out = self.dec_infer.infer({
                "input_ids": np.array([[next_id]], dtype=np.int64),
                "beam_idx": np.array([0], dtype=np.int32),
            }, share_inputs=True)
            logits = out["logits"] if isinstance(out, dict) else out[0]
            next_id = int(np.argmax(logits[0, -1, :]))
            generated.append(next_id)

        return generated

    def generate_with_prefix(self, state: ASRStreamingState,
                             audio_accum: np.ndarray,
                             prefix_text: str,
                             max_new_tokens: int) -> str:
        """流式：编码全量 audio_accum（无 window cache）→ greedy decode"""
        # 编码
        ehs, n_real, N_audio = self.encode_audio(audio_accum)
        # 拼 prefix ids（用 state.prompt_raw + prefix_text）
        prompt_with_prefix = state.prompt_raw + (prefix_text or "")
        prefix_ids = self.tokenizer.encode(prompt_with_prefix, add_special_tokens=False)
        # 去掉 prompt_raw 部分（已包含在 ids_left + audio_pad + ids_right）
        raw_ids = self.tokenizer.encode(state.prompt_raw, add_special_tokens=False)
        if state.prompt_raw and len(prefix_ids) > len(raw_ids):
            extra_prefix_ids = prefix_ids[len(raw_ids):]
        else:
            extra_prefix_ids = []
        out_ids = self.greedy_decode_with_prefix(
            ehs, extra_prefix_ids, max_new_tokens,
            force_language=state.force_language)
        return self.tokenizer.decode(out_ids, skip_special_tokens=True)
