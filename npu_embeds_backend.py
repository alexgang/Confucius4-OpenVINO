"""npu_embeds_backend.py — C-080: GPU encoder + NPU cleanie decoder backend.

为什么这个 backend 存在
----------------------
生产路径（`SegmentEncoderOVBackend`）用一个**自回归 cross-attention decoder**
（`models/ov-int8-past`），音频通过 `encoder_hidden_states` 端口进图。那种 decoder
的 IR 不能被 NPUW 吃（C-070~C-072 已经证伪了手写静态 KV 图那条路）。

C-079/c079b 找到的可行形态是**另一种 decoder**：纯 `full_attention` 的因果 LM
（28 层全部 `full_attention`，`Qwen3ForCausalLM`），音频不再是 cross-attention 的
key/value，而是按 `Qwen3ASRThinkerForConditionalGeneration.forward` 的
`masked_scatter` 语义**直接铺进 token embedding 序列**：

    inputs_embeds = embed_tokens(input_ids)
    inputs_embeds = inputs_embeds.masked_scatter(audio_mask, audio_features)

也就是说，音频位置上的 embedding **就是** encoder 的输出。没有任何 cross-attention，
没有任何额外的投影。所以：

    inputs_embeds = [ emb(ids_left)
                     , ehs[0]                      <-- 音频直接铺在这里
                     , emb(ids_right)
                     , emb(prefix_ids) ]

这正是 C-080#1 要求的「prompt 拼接（模板 token 的 embedding + 音频嵌入 + 前缀
token 的 embedding）在 Python 里完成」。

端口（`models/qwen3-lm-{int8sym,int4sym}-cleanie-ov`）
---------------------------------------------------
    attention_mask  [?,?]      i64
    position_ids    [?,?]      i64
    beam_idx        [?]        i32
    inputs_embeds   [1, 1..512, 2048]  f32
    logits          [?,?,151936]

⚠️ prompt 长度上界 512 是 IR 里写死的 `ov.Dimension(1, 512)`。VAD 段最长 20 s，
音频 token 数 `aftercnn_len` 最多 ~312，加模板 13 + 前缀若干，最坏情况会顶到 512。
本 backend 在拼完 prompt 后显式检查 `T <= 512`，超了直接抛错而不是静默截断
（静默截断会产出一段"看起来正常"的错误转写，比崩掉更糟）。

`position_ids`
-------------
Qwen3-ASR 的 thinker 用的是 MRoPE，`get_rope_index` 对全 1 的 attention_mask
返回三条**完全相同**的 0..T−1 序列（`unsqueeze(0).expand(3, -1, -1)`），
所以 1D 的 `arange(T)` 与 MRoPE 等价。这一点 C-079 已在 CPU/NPU 上实测过
（prefill cosine 0.99991 / 0.999731）。IR 的 `position_ids` 端口是 rank 2
（genai 契约写的是 rank 3，但对这个 IR 形状是 `[T]`），保持 C-079 已验证的用法。

每个 chunk 的生命周期（与生产完全一致）
--------------------------------------
`seg_stream._run_one_segment` 以 40 ms 步长喂音频，`streaming_asr` 每凑满
`chunk_size_sec`（640 ms）调一次 `generate_with_prefix`。每次调用都是
**reset_state() + 全量 prefill**，与 C-069m 实测的生产画像一致。
⚠️ 同一个 InferRequest 上二次 `reset_state()` 会抛
`sub-views are not implemented`（OV 2026.4.1），所以每次调用新建请求；
但**一次调用内部**的 prefill + N 步 decode 共用同一个请求，这才是
"会话内多步中位"口径（C-075#2：104 ms vs 57 ms 那类双倍开销的来源）。
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

import numpy as np

from backends import ASRBackend, ASRStreamingState, SAMPLE_RATE
from segment_encoder_backend import (
    SegmentEncoderOVBackend, aftercnn_len, MAX_FRAMES,
)

# cleanie IR 里写死的上界
MAX_PROMPT_TOK = 512
HIDDEN = 2048
EOS_IDS = {151643, 151645}


class NPUEmbedsDecoderBackend(SegmentEncoderOVBackend):
    """GPU encoder + NPU(cleanie LM) decoder。

    encoder 完全复用 `SegmentEncoderOVBackend.encode_audio`（同一个
    `models/ov-encoder-segment-reviewer` IR、同一套补零/取前 n_valid 逻辑），
    这样分项耗时里的 encoder 数字与生产 A 配置直接可比。
    """

    name = "npu_embeds"

    def __init__(self,
                 encoder_dir: str = "models/ov-encoder-segment-reviewer",
                 decoder_dir: str = "models/qwen3-lm-int4sym-cleanie-ov",
                 aux_dir: str = "models/ov-int8-past",
                 device: str = "GPU.0",
                 precision: str = "f16",
                 npu_max_prompt_len: int = MAX_PROMPT_TOK,
                 npu_min_response_len: int = 64,
                 cache_dir: str = "./reports/npu_cache",
                 strict_intel: bool = True):
        import openvino as ov
        from transformers import AutoTokenizer, WhisperFeatureExtractor

        # ── 父类只负责 encoder + tokenizer/特征提取器 ────────────────
        # decoder_dir 指向生产 ASR 目录（含 preprocessor_config.json /
        # chat_template.jinja），cleanie 目录里没有这两个文件。
        super().__init__(encoder_dir=encoder_dir, decoder_dir=aux_dir,
                         device=device, precision=precision,
                         cache_dir=cache_dir, strict_intel=strict_intel)
        self._dec_dir = decoder_dir

        core = ov.Core()
        self._core = core
        props = {
            "NPU_USE_NPUW": "YES",
            "NPUW_LLM": "YES",
            "NPUW_LLM_MAX_PROMPT_LEN": str(npu_max_prompt_len),
            "NPUW_LLM_MIN_RESPONSE_LEN": str(npu_min_response_len),
            "CACHE_DIR": cache_dir,
        }
        self._npu_props = props
        xml = os.path.join(decoder_dir, "openvino_model.xml")
        t0 = __import__("time").perf_counter()
        self.dec = core.compile_model(xml, "NPU", props)
        self.npu_compile_s = round(__import__("time").perf_counter() - t0, 1)
        self.dec_xml = xml

        # 端口名以 IR 为准，不靠猜
        self._port_names = {p.get_any_name() for p in self.dec.inputs}

        # ── embedding 表：来自 HF 权重的 embed_tokens，f32 ───────────
        self._W = _load_embed_table()
        assert self._W.shape == (151936, HIDDEN), self._W.shape

        # 模板 embedding 预计算（不变部分）
        ids_left, ids_right = self._prompt_template_ids
        self._emb_left = np.ascontiguousarray(self._W[ids_left], dtype=np.float32)
        self._emb_right = np.ascontiguousarray(self._W[ids_right], dtype=np.float32)

        # 分项计时（本作业专用；每段由 harness 逐段清空）
        self.probe = {"enc_ms": [], "prefill_ms": [], "decode_ms": [],
                      "n_decode": [], "prompt_len": [], "n_audio": [],
                      "budget": [], "out_tokens": []}

    # ── prompt 拼接 ────────────────────────────────────────────────
    def build_inputs_embeds(self, ehs: np.ndarray,
                            prefix_ids: List[int]) -> np.ndarray:
        """emb(模板左) + 音频嵌入 + emb(模板右) + emb(前缀)。

        音频段直接用 encoder 输出的 `ehs[0]`（N_audio, 2048），不做任何变换，
        这与 `masked_scatter(audio_mask, audio_features)` 的语义完全一致：
        audio_mask 覆盖的位置 embedding 被 audio_features 整体替换。
        """
        audio = np.asarray(ehs[0], dtype=np.float32)
        assert audio.ndim == 2 and audio.shape[1] == HIDDEN, audio.shape
        # 顺序必须是 left + audio + right + prefix（与生产 input_ids 拼接一致）
        parts = [self._emb_left, audio, self._emb_right]
        if prefix_ids:
            parts.append(np.ascontiguousarray(self._W[list(prefix_ids)],
                                              dtype=np.float32))
        emb = np.concatenate(parts, axis=0)[None, :, :].astype(np.float32)
        if emb.shape[1] > MAX_PROMPT_TOK:
            raise ValueError(
                f"prompt {emb.shape[1]} tok > IR 上界 {MAX_PROMPT_TOK}；"
                "静默截断会产出看似正常的错误转写，必须显式失败")
        return np.ascontiguousarray(emb)

    # ── NPU 解码 ───────────────────────────────────────────────────
    def greedy_decode_with_prefix(self, encoder_hidden_states: np.ndarray,
                                  prefix_ids: List[int],
                                  max_new_tokens: int) -> List[int]:
        """reset_state → 全量 prefill → 逐步 decode，全部在一个 InferRequest 内。

        返回 out_ids（含可能的 EOS，与生产一致：生产把首 token 也放进
        generated，然后在循环里检查 EOS，所以 EOS 本身会留在列表里）。
        """
        import time

        W = self._W
        emb = self.build_inputs_embeds(encoder_hidden_states, prefix_ids)
        T = int(emb.shape[1])
        self.probe['prompt_len'].append(T)
        self.probe['n_audio'].append(int(encoder_hidden_states.shape[1]))
        self.probe['budget'].append(int(max_new_tokens))

        # ⚠️ 每次调用新建 InferRequest：同一请求二次 reset_state() 会抛
        # "sub-views are not implemented"（OV 2026.4.1）。
        req = self.dec.create_infer_request()
        t0 = time.perf_counter()
        out = req.infer({
            "attention_mask": np.ones((1, T), dtype=np.int64),
            "position_ids": np.arange(T, dtype=np.int64)[None, :],
            "beam_idx": np.zeros(1, dtype=np.int32),
            "inputs_embeds": emb,
        })
        self.probe['prefill_ms'].append((time.perf_counter() - t0) * 1000)
        logits = np.ascontiguousarray(
            np.array(out[self._logits_port()].data)[0, -1]).copy()

        nxt = int(np.argmax(logits))
        generated = [nxt]
        if nxt in EOS_IDS or self.tokenizer.eos_token_id == nxt:
            self.probe['decode_ms'].append(0.0)
            self.probe['n_decode'].append(0)
            self.probe['out_tokens'].append(len(generated))
            del req
            return generated

        n_dec = 0
        td = time.perf_counter()
        for _ in range(max_new_tokens - 1):
            past = T + n_dec
            out = req.infer({
                "attention_mask": np.ones((1, past + 1), dtype=np.int64),
                "position_ids": np.array([[past]], dtype=np.int64),
                "beam_idx": np.zeros(1, dtype=np.int32),
                # 刚采样出的那个 token 的 embedding —— 喂最后一次 prompt
                # embedding 是一个「看起来能跑」的错误，会产出貌似合理的乱码
                "inputs_embeds": np.ascontiguousarray(
                    W[nxt][None, None, :], dtype=np.float32),
            })
            logits = np.ascontiguousarray(
                np.array(out[self._logits_port()].data)[0, -1]).copy()
            nxt = int(np.argmax(logits))
            n_dec += 1
            if nxt in EOS_IDS or self.tokenizer.eos_token_id == nxt:
                break
            generated.append(nxt)
        self.probe['decode_ms'].append((time.perf_counter() - td) * 1000)
        self.probe['n_decode'].append(n_dec)
        self.probe['out_tokens'].append(len(generated))
        del req
        return generated

    def _logits_port(self) -> str:
        for o in self.dec.outputs:
            return o.get_any_name()
        raise RuntimeError('decoder has no outputs')


def _load_embed_table() -> np.ndarray:
    """从 HF 权重取 embed_tokens（f32）。

    优先用 safetensors 直读（不 import torch 时也能走），
    否则回退到 torch。
    """
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "models", "hf-qwen3-lm-lastlogit")
    idx = os.path.join(d, "model.safetensors.index.json")
    if os.path.exists(idx):
        from safetensors import safe_open
        shard = json.load(open(idx))["weight_map"]["model.embed_tokens.weight"]
        with safe_open(os.path.join(d, shard), framework="numpy") as f:
            return np.asarray(f.get_tensor("model.embed_tokens.weight"),
                              dtype=np.float32)
    single = os.path.join(d, "model.safetensors")
    if os.path.exists(single):
        from safetensors import safe_open
        with safe_open(single, framework="numpy") as f:
            return np.asarray(f.get_tensor("model.embed_tokens.weight"),
                              dtype=np.float32)
    import torch
    sd = torch.load(os.path.join(d, "model.safetensors"), map_location="cpu")
    for k in sd:
        if k.endswith("embed_tokens.weight"):
            return sd[k].detach().to(torch.float32).numpy()
    raise FileNotFoundError(d)
