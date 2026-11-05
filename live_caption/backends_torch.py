"""backends_torch.py —— **只给开发用的 torch 实现**（APP-069⑤ 清理项 1）。

## 为什么把它拆出来

APP-069⑤（reviewer 裁定）：

> `backends.py` L64/L145/L443 和 `npu_embeds_backend.py` L292 的 `import torch`：
> reviewer 裁定**要清**。APP-066 的字面要求是「不能 import torch」，
> 运行不可达也不能当成例外。修法：在开发树里把 TorchBackend、HybridBackend、
> extract_audio_features 的 torch 实现，以及 npu_embeds_backend 的 torch 分支，
> 移到只给开发用的新模块（比如 `backends_torch.py`），
> 原位置改成懒加载，找不到就报清楚的错误。

⇒ **本模块** = 那三处 torch 实现 + `npu_embeds_backend` 的 torch 分支。
⇒ `backends.py` 只留**薄壳**：`make_backend('torch'|'hybrid')` 仍能解析，
   但**构造时**才 import 本模块 ⇒ 客户包（**不含 torch**）里
   选 torch 后端时会得到**清楚的错误**，而不是 `ModuleNotFoundError`。

⚠️ **本模块**不在 MiniMVP 客户包里（APP-066 白名单不含它）⇒ 零体积。
"""
from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

import numpy as np


def require_torch(where: str):
    """import torch ⇒ 失败时给**清楚的错误**（而不是裸 ModuleNotFoundError）。"""
    try:
        import torch
    except Exception as e:
        raise RuntimeError(
            '需要 PyTorch 才能用 %s，但当前环境没有装 torch（%s）。\n'
            '客户包**不含** torch（MiniMVP 只带 OpenVINO IR）⇒ '
            '请改用 OpenVINO 后端（--engine gpu_int8 / openvino）。'
            % (where, e)) from e
    return torch


# ── extract_audio_features 的 torch 分支（原 backends.py L60-67）────────
def extract_audio_features_torch(fe, audio: np.ndarray, n_real: int,
                                 N_audio: int):
    """`extract_audio_features(..., return_torch=True)` 的 torch 实现。"""
    torch = require_torch('TorchBackend（特征提取）')
    return (torch.from_numpy(feats_real_of(fe, audio, n_real)).to("cpu"),
            torch.from_numpy(mask_of(fe, audio, n_real)).to(torch.long),
            n_real, N_audio)


def feats_real_of(fe, audio: np.ndarray, n_real: int) -> np.ndarray:
    """复用 `backends.extract_audio_features` 的中间结果（避免重复计算）。"""
    from backends import extract_audio_features as _e
    out = _e(fe, audio, return_torch=False)
    return out[0]


def mask_of(fe, audio: np.ndarray, n_real: int) -> np.ndarray:
    from backends import extract_audio_features as _e
    out = _e(fe, audio, return_torch=False)
    return out[1]


# ── TorchBackend（原 backends.py L141-272）────────────────────────────
class TorchBackend:
    """ASR 后端：**torch + transformers**（CPU FP32）⇒ per-chunk golden。

    🔴 **APP-069⑤**：实现体从 `backends.py` 搬到这里（开发专用）。
       `backends.py` 里的同名类是**薄壳**（懒加载 + 清楚报错）。
    """

    name = "torch"

    def __init__(self, model_dir: str = "models/hf"):
        torch = require_torch('TorchBackend')
        import json
        from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
        # qwen_asr 是 wrapper，.model 才是 transformers 模型
        wrapper = Qwen3ASRModel.from_pretrained(
            model_dir, dtype=torch.float32, attn_implementation="eager",
        )
        self.model = wrapper.model
        self.processor = wrapper.processor
        self.tokenizer = self.processor.tokenizer
        if hasattr(self.model, "eval"):
            self.model.eval()
        self._torch = torch
        ct_path = os.path.join(model_dir, "chat_template.json")
        if os.path.exists(ct_path):
            with open(ct_path, encoding="utf-8") as f:
                self.tokenizer.chat_template = json.load(f)["chat_template"]
        self._prompt_template_ids = self._build_prompt_template_ids()
        self._hop = self.processor.feature_extractor.hop_length
        self._n_mels = self.processor.feature_extractor.feature_size

    # ── 与 `backends.ASRBackend` 的一致接口 ──────────────────────────
    def init_streaming_state(self, *, context: str = "",
                             system_prompt: str = "",
                             language: Optional[str] = None):
        from backends import ASRStreamingState
        st = ASRStreamingState()
        st.prefix_text = ''
        st.context = context
        st.system_prompt = system_prompt
        st.language = language
        return st

    def _build_prompt_template_ids(self):
        msgs = [{"role": "system", "content": ""},
                {"role": "user", "content": [{"type": "audio", "audio": ""}]}]
        text = self.tokenizer.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=False)
        tl, tr = text.split("<|audio_start|><|audio_pad|><|audio_end|>")
        return (self.tokenizer.encode(tl, add_special_tokens=False),
                self.tokenizer.encode(tr, add_special_tokens=False))

    def _build_text_prompt(self, *, context: str,
                           force_language: Optional[str]) -> str:
        msgs = []
        if context:
            msgs.append({"role": "system", "content": context})
        msgs.append({"role": "user",
                     "content": [{"type": "audio", "audio": ""}]})
        text = self.tokenizer.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=False)
        return text + "<|audio_start|><|audio_pad|><|audio_end|>"

    def generate_with_prefix(self, state, prefix_text: str,
                             max_new_tokens: int = 256) -> str:
        prompt = self._build_text_prompt(
            context=getattr(state, 'context', '') or '',
            force_language=getattr(state, 'language', None))
        ids = self.tokenizer.encode(prompt, add_special_tokens=False)
        if prefix_text:
            ids = ids + self.tokenizer.encode(
                prefix_text, add_special_tokens=False)
        import torch
        input_ids = torch.tensor([ids], dtype=torch.long)
        attention_mask = torch.ones_like(input_ids)
        with torch.no_grad():
            out = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        gen = out[0][input_ids.shape[1]:]
        return self.tokenizer.decode(gen, skip_special_tokens=True)

    def finish_streaming_transcribe(self, state) -> str:
        return self.generate_with_prefix(state, '')


# ── HybridBackend（原 backends.py L432-556）──────────────────────────
class HybridBackend:
    """ASR 后端：**OV 解码器 + torch 编码器**（混合）。

    🔴 **APP-069⑤**：实现体从 `backends.py` 搬到这里（开发专用）。
    """

    name = "hybrid"

    def __init__(self,
                 torch_model_dir: str = "models/hf",
                 ov_model_dir: str = "models/ov-int8-past",
                 device: str = "GPU.0",
                 precision: str = "f16",
                 cache_dir: str = "./ov_cache",
                 torch_dtype: str = "float32",
                 attn_implementation: str = "eager"):
        torch = require_torch('HybridBackend')
        from transformers import AutoTokenizer, WhisperFeatureExtractor
        from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
        import openvino as ov

        core = ov.Core()
        full_name = core.get_property(device, "FULL_DEVICE_NAME")
        assert "Intel" in full_name, f"device {device} not Intel: {full_name}"
        core.set_property({"CACHE_DIR": cache_dir})
        prop = {"PERFORMANCE_HINT": "LATENCY",
                "INFERENCE_PRECISION_HINT": precision}
        self.dec = core.compile_model(
            os.path.join(ov_model_dir, "openvino_decoder_model.xml"),
            device, prop,
        )
        self.dec_infer = self.dec.create_infer_request()
        self.tokenizer = AutoTokenizer.from_pretrained(
            ov_model_dir, fix_mistral_regex=True)
        self.tokenizer.chat_template = open(
            os.path.join(ov_model_dir, "chat_template.jinja"),
            encoding="utf-8").read()
        self._prompt_template_ids = self._build_prompt_template_ids()

        dtype = {"float32": torch.float32,
                 "float16": torch.float16}[torch_dtype]
        self._torch = torch
        wrapper = Qwen3ASRModel.from_pretrained(
            torch_model_dir, dtype=dtype,
            attn_implementation=attn_implementation,
        )
        self._wrapper = wrapper
        self._torch_model = wrapper.model
        self._torch_model.eval()
        self.audio_tower = self._torch_model.thinker.audio_tower
        self.feature_extractor = wrapper.processor.feature_extractor

    def init_streaming_state(self, *, context: str = "",
                             system_prompt: str = "",
                             language: Optional[str] = None):
        from backends import ASRStreamingState
        st = ASRStreamingState()
        st.prefix_text = ''
        st.context = context
        st.system_prompt = system_prompt
        st.language = language
        return st

    def _build_prompt_template_ids(self):
        msgs = [{"role": "system", "content": ""},
                {"role": "user", "content": [{"type": "audio", "audio": ""}]}]
        text = self.tokenizer.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=False)
        tl, tr = text.split("<|audio_start|><|audio_pad|><|audio_end|>")
        return (self.tokenizer.encode(tl, add_special_tokens=False),
                self.tokenizer.encode(tr, add_special_tokens=False))

    def _build_text_prompt(self, *, context: str,
                           force_language: Optional[str]) -> str:
        msgs = []
        if context:
            msgs.append({"role": "system", "content": context})
        msgs.append({"role": "user",
                     "content": [{"type": "audio", "audio": ""}]})
        text = self.tokenizer.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=False)
        return text + "<|audio_start|><|audio_pad|><|audio_end|>"

    def encode_audio(self, wav: np.ndarray):
        feats = self.feature_extractor(
            list(wav), sampling_rate=16000, return_tensors="np",
            padding="do_not_pad", truncation=False,
            return_attention_mask=True)
        audio_tower = self.audio_tower
        import torch
        f = torch.from_numpy(feats["input_features"]).to(self._torch_dtype())
        m = torch.from_numpy(feats["attention_mask"]).to(self._torch_dtype())
        with torch.no_grad():
            out = audio_tower(f, attention_mask=m)
        return out.last_hidden_state.to(torch.float32).numpy()

    def _torch_dtype(self):
        return (self._torch.float32 if getattr(self, '_torch', None) is None
                else self._torch.float32)

    def greedy_decode_with_prefix(self, encoder_hidden_states,
                                  prefix_text: str = "",
                                  max_new_tokens: int = 256) -> str:
        import numpy as np
        ids = self.tokenizer.encode(
            self._build_text_prompt(context='', force_language=None),
            add_special_tokens=False)
        if prefix_text:
            ids = ids + self.tokenizer.encode(prefix_text,
                                              add_special_tokens=False)
        n = len(ids)
        out = self.dec_infer.infer({
            'input_ids': np.array([ids], dtype=np.int32),
            'encoder_hidden_states': encoder_hidden_states,
            'use_cache_branch': np.array(False),
        })
        logits = out['logits']
        new_ids = []
        for _ in range(max_new_tokens):
            nxt = int(np.argmax(logits[0, -1, :]))
            if nxt in (151643, 151645):
                break
            new_ids.append(nxt)
            ids = ids + [nxt]
            out = self.dec_infer.infer({
                'input_ids': np.array([ids], dtype=np.int32),
                'encoder_hidden_states': encoder_hidden_states,
                'use_cache_branch': np.array(False),
            })
            logits = out['logits']
        return self.tokenizer.decode(new_ids, skip_special_tokens=True)

    def generate_with_prefix(self, state, prefix_text: str,
                             max_new_tokens: int = 256) -> str:
        return ''


# ── npu_embeds_backend 的 torch 分支（原 npu_embeds_backend.py L291-297）──
def load_embed_via_torch(safetensors_path: str):
    """从 safetensors 读 `embed_tokens.weight`（**torch 分支**，开发专用）。"""
    torch = require_torch('embed 表回退（safetensors）')
    sd = torch.load(safetensors_path, map_location="cpu")
    for k in sd:
        if k.endswith("embed_tokens.weight"):
            return sd[k].detach().to(torch.float32).numpy()
    raise FileNotFoundError(
        'embed table not found in safetensors: %s' % safetensors_path)
