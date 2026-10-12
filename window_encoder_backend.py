"""window_encoder_backend.py — C-024#3: 流式 window cache 优化 backend

设计：
- 用 models/ov-encoder-window 单窗 IR（800 mel 固定输入）做编码
- 用 models/ov-int8-past OV stateful decoder 做解码
- window cache：每段 VAD 切句内，full 800-mel 窗口的 ehs 缓存；只重算最后一个未满窗口
- 接口与 OVBackend/HybridBackend 一致（encode_audio + greedy_decode_with_prefix + generate_with_prefix）

Qwen3-ASR audio encoder 是 per-window 独立（cu_seqlens [0, 104] 单窗口内 attention），
所以已填满的窗口输出可以缓存，不必重算。
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


def aftercnn_len(n: int) -> int:
    """3 stride-2 conv: 100 mel → 13 aftercnn"""
    x = n
    for _ in range(3):
        x = (x + 1) // 2
    return x


class WindowEncoderOVBackend(ASRBackend):
    """OV 单窗 encoder + OV INT8-past stateful decoder + window cache"""

    name = "window_ov"

    def __init__(self,
                 encoder_dir: str = "models/ov-encoder-window",
                 decoder_dir: str = "models/ov-int8-past",
                 device: str = "GPU.0",
                 precision: str = "f16",
                 cache_dir: str = "./ov_cache"):
        from transformers import AutoTokenizer, WhisperFeatureExtractor

        # 设备 Intel 断言
        core = ov.Core()
        full_name = core.get_property(device, "FULL_DEVICE_NAME")
        assert "Intel" in full_name, f"device {device} not Intel: {full_name}"
        core.set_property({"CACHE_DIR": cache_dir})
        prop = {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": precision}

        # 加载 window encoder
        self._core = core
        self._prop = prop
        self._device = device
        enc_model = core.read_model(
            model=os.path.join(encoder_dir, "openvino_encoder_model.xml"),
            weights=os.path.join(encoder_dir, "openvino_encoder_model.bin"),
        )
        # 静态 shape
        for inp in enc_model.inputs:
            if 'feature' in inp.any_name.lower() or 'input' in inp.any_name.lower():
                enc_model.reshape({inp.any_name: [1, 128, 800]})
            else:
                enc_model.reshape({inp.any_name: [2]})
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

        # window cache：full 800-mel 窗 ehs 列表 + last 帧数
        self._window_cache_ehs: List[np.ndarray] = []  # list of (1, valid_aftercnn, 2048)
        self._window_cache_mel_cum: int = 0  # 已缓存窗口累计 mel 数

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
        # 新段时清空 window cache
        self._window_cache_ehs = []
        self._window_cache_mel_cum = 0
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

    def _encode_window(self, win_mel: np.ndarray, valid_mel_in_window: int) -> np.ndarray:
        """调用 OV 单窗 IR，返回 (1, valid_aftercnn, 2048)"""
        # win_mel: (128, valid_mel_in_window) — 必须 <= 800
        if win_mel.shape[1] < 800:
            pad = np.zeros((128, 800 - win_mel.shape[1]), dtype=win_mel.dtype)
            win_mel = np.concatenate([win_mel, pad], axis=1)
        win_in = win_mel[np.newaxis, :, :].astype(np.float32)  # (1, 128, 800)

        # 算 valid_aftercnn
        win_n_100 = (valid_mel_in_window + 99) // 100
        if valid_mel_in_window % 100 == 0:
            valid_aftercnn = win_n_100 * 13
        else:
            valid_aftercnn = (win_n_100 - 1) * 13 + aftercnn_len(
                valid_mel_in_window - (win_n_100 - 1) * 100
            )
        cu_in = np.array([0, valid_aftercnn], dtype=np.int32)

        result = self.enc_infer.infer([win_in, cu_in])
        out = result[0]  # (1, 104, 2048)
        return out[:, :valid_aftercnn, :]

    def encode_audio(self, wav: np.ndarray):
        """window cache 编码：只重算最后未满窗口
        Returns: (ehs [1, N_audio, 2048], n_real_frames, N_audio)
        """
        # 1) 提特征
        feats_real, _, n_real, N_audio = extract_audio_features(
            self.feature_extractor, wav, return_torch=False,
        )
        # feats_real: (1, 128, T_mel_real)
        mel = feats_real[0]  # (128, T_mel_real)

        # C-033#1 修：按 mel 帧数向下取整，不要用 n_100_blocks//8
        # 原 bug：当 mel 在 (700, 800) 区间时，n_100_blocks 向上取整为 8，n_full_windows = 1
        # 但实际 mel < 800，无满窗口，代码把不满窗口当满窗口并缓存，导致后续 step 命中
        # 错误的 cache，永久偏离。
        mel_len = mel.shape[1]
        n_full_windows = mel_len // 800  # 按帧数向下取整: 只算真正满 800 帧的窗口
        n_full_mel = n_full_windows * 800
        # 其余全部作为 partial 窗口，传入真实有效帧数

        out_chunks = []

        # 2) 完整窗口：cache 命中则复用，否则重算并缓存
        # 因 w < n_full_windows = mel_len//800，自动保证 mel_len >= (w+1)*800（无 STFT 边界问题）
        for w in range(n_full_windows):
            if w < len(self._window_cache_ehs):
                # 命中
                out_chunks.append(self._window_cache_ehs[w])
            else:
                # 未命中：编码并缓存
                win_mel = mel[:, w*800:(w+1)*800]
                ehs = self._encode_window(win_mel, 800)  # (1, 104, 2048)
                self._window_cache_ehs.append(ehs)
                out_chunks.append(ehs)
        self._window_cache_mel_cum = n_full_mel

        # 3) 最后一个 partial 窗口（如果有）：永远重算
        partial_mel_len = mel_len - n_full_mel
        if partial_mel_len > 0:
            partial_mel = mel[:, n_full_mel:]  # (128, partial_mel_len)
            valid_in_partial = partial_mel_len
            ehs = self._encode_window(partial_mel, valid_in_partial)
            out_chunks.append(ehs)

        if not out_chunks:
            # 完全空音频
            return np.zeros((1, 0, 2048), dtype=np.float32), 0, 0

        ehs = np.concatenate(out_chunks, axis=1)  # (1, N_audio, 2048)
        return ehs, n_real, ehs.shape[1]

    def greedy_decode_with_prefix(self, encoder_hidden_states: np.ndarray,
                                  prefix_ids: List[int],
                                  max_new_tokens: int) -> List[int]:
        """OV stateful decoder：reset_state → prefill → 1 token/step"""
        self.dec_infer.reset_state()

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
        """流式：编码全量 audio_accum（用 window cache）→ greedy decode"""
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
        out_ids = self.greedy_decode_with_prefix(ehs, extra_prefix_ids, max_new_tokens)
        return self.tokenizer.decode(out_ids, skip_special_tokens=True)
