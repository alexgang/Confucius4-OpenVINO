"""ov_r2t2.py — OpenVINO 版的 R2T2 流式 ASR
直接对接 optimum-intel 导出的两个 IR（encoder + decoder），自己管理 prompt / 自回归解码 / 回滚。
与官方 qwen_asr.streaming_transcribe 同样的算法。
"""
from __future__ import annotations
import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import openvino as ov
import soundfile as sf
import qwen_asr  # 触发 qwen3_asr model_type 注册
from transformers import AutoTokenizer

# ── 常量 ──────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
AUDIO_START = 151669  # <|audio_start|>
AUDIO_END   = 151670  # <|audio_end|>
AUDIO_PAD   = 151676  # <|audio_pad|>
EOS_IDS = [151643, 151645]


@dataclass
class OVConfig:
    model_dir: str
    device: str = "GPU.0"
    precision: str = "f16"
    cache_dir: str = "./ov_cache"


@dataclass
class ASRStreamingState:
    """模仿 qwen_asr.inference.ASRStreamingState 的字段"""
    chunk_size_sec: float = 0.32        # 默认 320ms（与 audio.cpp spec 一致）
    unfixed_chunk_num: int = 2
    unfixed_token_num: int = 5
    chunk_id: int = 0
    buffer: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float32))
    audio_accum: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float32))
    prompt_raw_ids: List[int] = field(default_factory=list)
    text: str = ""                       # 累计 raw text）
    final_text: str = ""                 # last step 中文输出
    _raw_decoded: str = ""               # 会话用过的 raw


class OVR2T2ASR:
    """OpenVINO 版 Confucius4-R2T2 推理。

    关键设计：
    - 每次 chunk：full audio_accum 重跑 encoder（mwheel 全量重编码，与 audio.cpp 日志一致）
    - Prompt：state.prompt_raw_ids + audio_pad × num_audio + prefix_text_ids
    - Decoder 一次 prefill（一次性过完 prompt 全部 input_ids），然后无 KV cache 的自回归
      每次重新 feed 全部 prefix + 当前 decode 后的 token 序列
    - 文本回滚：unfixed_token_num 个 token 回滚后取未 split（qwen_asr 源码）
    """

    def __init__(self, cfg: OVConfig):
        self.cfg = cfg
        self.tokenizer = AutoTokenizer.from_pretrained(cfg.model_dir)

        # 加载 IR
        core = ov.Core()
        core.set_property({'CACHE_DIR': cfg.cache_dir})
        prop = {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PINT_HINT': cfg.precision} \
            if False else {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': cfg.precision}
        self.enc = core.compile_model(
            os.path.join(cfg.model_dir, 'openvino_encoder_model.xml'),
            cfg.device, prop,
        )
        self.dec = core.compile_model(
            os.path.join(cfg.model_dir, 'openvino_decoder_model.xml'),
            cfg.device, prop,
        )
        # 加载 mel feature_extractor
        from transformers import AutoProcessor
        self.processor = AutoProcessor.from_pretrained(cfg.model_dir)
        self.feature_extractor = self.processor.feature_extractor

        # build prompt template once
        self._prompt_template_ids = self._build_prompt_template()

    def _build_prompt_template(self) -> List[int]:
        """构造 chat_template 后的 token 序列（不含 audio_pad 部分）

        在 chat_template.jinja 里，输入在 await 中遇 audio_payload 会被换成 `<|audio_start|><|audio_pad|><|audio_end|>`。
        但实际这里需要 audio_pad 个 token 来表示 N_audio audio frames。所以这里构造
        [system + user(不含 audio tokens) + assistant marker] 的 token 序列
        并人工拆分成 [prefix_ids] + [audio_pad × N] + [suffix_ids] 三段
        """
        # 依据 qwen_asr._build_text_prompt 调用方式构造
        msgs = [
            {'role': 'system', 'content': ''},
            {'role': 'user',   'content': [{'type': 'audio', 'audio': ''}]},
        ]
        text = self.processor.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        # 在文本中查找 audio tokens 出现的位置
        text_left = text.split('<|audio_start|><|audio_pad|><|audio_end|>')[0]
        text_right = text.split('<|audio_start|><|audio_pad|><|audio_end|>')[1]
        ids_left = self.tokenizer.encode(text_left, add_special_tokens=False)
        ids_right = self.tokenizer.encode(text_right, add_special_tokens=False)
        return ids_left, ids_right

    def encode_audio(self, wav: np.ndarray) -> np.ndarray:
        """wav: 16kHz mono float32, shape (N,) → encoder_hidden_states [1, T, 2048]"""
        # featurize → input_features [1, 128, T_frames]
        fea = self.feature_extractor(wav, sampling_rate=SAMPLE_RATE, return_tensors='np')
        x = fea['input_features'].astype(np.float32)
        out = self.enc({'input_features': x})
        return out['last_hidden_state']  # [1, T_audio, 2048]

    def _greedy_decode_one_chunk(self, encoder_hidden_states: np.ndarray,
                                 prefix_ids: List[int], max_new_tokens: int = 32) -> List[int]:
        """单 chunk 解码：
        - 输入：encoder_hidden_states [1, T_audio, 2048]、prefix_ids（不含 audio pad）
        - 输出：生成的 token 列表（不含 prompt 部分）
        """
        ids_left, ids_right = self._prompt_template_ids
        N_audio = encoder_hidden_states.shape[1]
        # full input_ids: [ids_left] + [audio_pad] * N_audio + [ids_right] + [prefix_ids]
        input_ids_list = list(ids_left) + [AUDIO_PAD] * N_audio + list(ids_right) + list(prefix_ids)
        input_ids = np.array([input_ids_list], dtype=np.int64)

        out_tokens: List[int] = []
        for step in range(max_new_tokens):
            logits = self.dec({'input_ids': input_ids, 'encoder_hidden_states': encoder_hidden_states})['logits']
            next_id = int(np.argmax(logits[0, -1]))
            if next_id in EOS_IDS:
                break
            out_tokens.append(next_id)
            input_ids = np.concatenate([input_ids, np.array([[next_id]], dtype=np.int64)], axis=1)
        return out_tokens

    def init_streaming_state(self, chunk_size_sec: float = 0.32,
                             unfixed_chunk_num: int = 2,
                             unfixed_token_num: int = 5) -> ASRStreamingState:
        return ASRStreamingState(
            chunk_size_sec=chunk_size_sec,
            unfixed_chunk_num=unfixed_chunk_num,
            unfixed_token_num=unfixed_token_num,
        )

    def streaming_transcribe(self, pcm16k: np.ndarray, state: ASRStreamingState,
                             max_new_tokens: int = 32) -> ASRStreamingState:
        """与 qwen_asr.streaming_transcribe 语义一致。"""
        x = np.asarray(pcm16k).reshape(-1).astype(np.float32, copy=False)
        if x.shape[0] > 0:
            state.buffer = np.concatenate([state.buffer, x])

        chunk_samples = int(round(state.chunk_size_sec * SAMPLE_RATE))
        while state.buffer.shape[0] >= chunk_samples:
            chunk = state.buffer[: chunk_samples]
            state.buffer = state.buffer[chunk_samples:]
            state.audio_accum = np.concatenate([state.audio_accum, chunk])

            # 构造 prefix（qwen_asr 源码语义）
            if state.chunk_id < state.unfixed_chunk_num:
                prefix_ids: List[int] = []
            else:
                cur_ids = self.tokenizer.encode(state._raw_decoded, add_special_tokens=False)
                k = state.unfixed_token_num
                while True:
                    end_idx = max(0, len(cur_ids) - k)
                    prefix = self.tokenizer.decode(cur_ids[:end_idx]) if end_idx > 0 else ''
                    if '\ufffd' not in prefix:
                        break
                    if end_idx == 0:
                        prefix = ''
                        break
                    k += 1
                prefix_ids = list(cur_ids[:end_idx])

            # encoder
            ehs = self.encode_audio(state.audio_accum)

            # decoder greedy
            out_tokens = self._greedy_decode_one_chunk(ehs, prefix_ids, max_new_tokens)
            gen_text = self.tokenizer.decode(out_tokens, skip_special_tokens=False)
            # 拼接 raw
            prefix_text = self.tokenizer.decode(prefix_ids, skip_special_tokens=False) if prefix_ids else ''
            state._raw_decoded = (prefix_text + gen_text) if prefix_text else gen_text
            state.text = state._raw_decoded
            state.chunk_id += 1

        return state

    def finish_streaming_transcribe(self, state: ASRStreamingState, max_new_tokens: int = 64) -> ASRStreamingState:
        """flush 尾部音频"""
        if state.buffer.shape[0] == 0:
            return state
        tail = state.buffer
        state.buffer = np.zeros((0,), dtype=np.float32)
        state.audio_accum = np.concatenate([state.audio_accum, tail])

        if state.chunk_id < state.unfixed_chunk_num:
            prefix_ids: List[int] = []
        else:
            cur_ids = self.tokenizer.encode(state._raw_decoded, add_special_tokens=False)
            end_idx = max(1, len(cur_ids) - state.unfixed_token_num)
            prefix_ids = list(cur_ids[:end_idx])

        ehs = self.encode_audio(state.audio_accum)
        out_tokens = self._greedy_decode_one_chunk(ehs, prefix_ids, max_new_tokens)
        gen_text = self.tokenizer.decode(out_tokens, skip_special_tokens=False)
        prefix_text = self.tokenizer.decode(prefix_ids, skip_special_tokens=False) if prefix_ids else ''
        state._raw_decoded = (prefix_text + gen_text) if prefix_text else gen_text
        state.text = state._raw_decoded
        return state


# ── 离线 one-shot 测试（验证 encoder + decoder + prompt 构造） ────────
def offline_transcribe(model: OVR2T2ASR, wav_path: str, max_new_tokens: int = 256) -> dict:
    audio, _ = sf.read(wav_path)
    audio = audio.astype(np.float32)
    ehs = model.encode_audio(audio)
    print(f'[offline] encoder output: {ehs.shape}')
    t0 = time.perf_counter()
    out_tokens = model._greedy_decode_one_chunk(ehs, prefix_ids=[], max_new_tokens=max_new_tokens)
    elapsed = time.perf_counter() - t0
    text = model.tokenizer.decode(out_tokens, skip_special_tokens=False)
    return {'tokens': out_tokens, 'text': text, 'elapsed_s': elapsed, 'audio_dur': len(audio) / SAMPLE_RATE}


if __name__ == '__main__':
    cfg = OVConfig(model_dir='models/ov-fp16', device='GPU.0')
    print('loading...')
    asr = OVR2T2ASR(cfg)
    print('loaded.')
    res = offline_transcribe(asr, 'C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
    print(f'[offline] text={res["text"]!r}')
    print(f'[offline] {res["audio_dur"]:.2f}s audio, decode={res["elapsed_s"]:.2f}s, RTF={res["elapsed_s"]/res["audio_dur"]:.3f}')