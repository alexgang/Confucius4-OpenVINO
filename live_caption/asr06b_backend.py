r"""asr06b_backend.py — **APP-096**：Qwen3-ASR-0.6B（mask2 INT8）的 OV 后端。

## 为什么需要这个模块（与现有两套后端都不同）

| | R2T2 `SegmentEncoderOVBackend` | R2T2 `NPUEmbedsDecoderBackend` | **本模块（0.6B）** |
|---|---|---|---|
| decoder 图 | `ov-int8-past`（cross-attn + KV stateful） | `qwen3-lm-int8sym-cleanie-ov`（inputs_embeds 因果 LM，**有** KV） | `ov-dec-06b-embed-mask2-int8sym`（**无 KV cache**，静态 512，**右对齐**） |
| 音频进图 | `encoder_hidden_states` 端口 | `inputs_embeds` 端口 | `inputs_embeds` 端口（音频 embedding 直接铺进 token 序列） |
| hidden | 2048 | 2048 | **1024** |
| 长度 | 变长 | 变长（≤512） | **恒 512**（右对齐 + attention_mask 标 padding） |
| 端口 | input_ids / beam_idx / past | attention_mask / position_ids / beam_idx / inputs_embeds | **inputs_embeds + attention_mask**（只有两个） |

🔴 **0.6B 的 decoder 没有 KV cache** ⇒ 每生成一个 token 都要**全序列重算** 512 位
⇒ 这是 `p3_ov_app.py::OVRunner` 已验证过的形态（`results/p3_diag_align.json`：
左对齐 vs 右对齐的 logits cos = **-0.154** ⇒ 两者语义完全不同 ⇒ **必须右对齐**）。

## 口径来源（全部照搬，不另造新图）

* 图与输入构造：`C:\Users\Trekker-PTL\qwen3asr_06b\scripts\p3_ov_app.py::OVRunner`
  * `build_embeds`：官方 `masked_scatter(audio_mask, audio_features)` 语义
    ⇒ 文本 embedding 表 + 音频 embedding **按位置铺进同一条序列**。
  * `decode_logits`：**右对齐**（内容放末尾，位置 511 = 最后一个真实 token）
    + 真实 `attention_mask`（前 512-L 位是 padding ⇒ 0）。
* prompt 字符串：`qwen_asr` 的 `Qwen3ASRModel._build_text_prompt`
  ⇒ `〈|im_start|〉system\n〈|im_end|〉\n〈|im_start|〉user\n〈|audio_start|〉〈|audio_pad|〉〈|audio_end|〉〈|im_end|〉\n〈|im_start|〉assistant\n`
  （context='' 时是**常量**）⇒ 这里**硬编码**，不依赖 jinja 模板。
  `force_language` 时追加 `language {lang}<asr_text>`。

## 🔴🔴🔴 包内**没有 torch** ⇒ 文本 embedding 必须来自 .npy

`models/embed_tokens_06b_f16.npy` = `thinker.model.embed_tokens.weight`
（形状 `[151936, 1024]`，磁盘 BF16 ⇒ 导出时统一转 **fp16** 存盘，
加载时再转 **fp32** 与 IR 的 f32 输入对齐）。
⚠️ 磁盘 dtype 是 BF16，而 `safetensors` 的 **numpy** 后端**不支持 bfloat16**
⇒ 导出必须走 torch 侧（或 `ml_dtypes`）⇒ 见 `_app3xx` 构建脚本。

## 音频 token 数

`n_audio = total_aftercnn_len(mel_frames)`，`mel_frames = n_samples / 160`
（`WhisperFeatureExtractor` 的 `padding='do_not_pad'` ⇒ 帧数 = 真实时长）。
该闭式公式与官方 `_get_feat_extract_output_lengths` **逐帧一致**（实测 0 差异）。

## 与 App 流式接口的适配

App 的 `streaming_asr.streaming_transcribe` 每 640 ms 调一次
`backend.generate_with_prefix(state, audio_accum, prefix, budget)`
⇒ 本模块把「全量 audio + prefix 文本」重新拼成一条 512 序列做 greedy
⇒ **每 chunk 全量重算**（0.6B 无 KV 的固有代价；61 分钟 GPU 臂实测 RTF 0.683
⇒ 可接受，但**不能**照搬 R2T2 的「增量 KV」假设）。
"""
from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple

import numpy as np

from backends import ASRBackend, ASRStreamingState, SAMPLE_RATE, extract_audio_features

# ── IR 与常量 ───────────────────────────────────────────────────────────
#: 0.6B 的 decoder 静态序列长度（右对齐 ⇒ 恒 512）
DEC_PROMPT_LEN = 512
#: 0.6B 的 encoder 静态 mel 帧数
ENC_MAX_FRAMES = 2400
#: 0.6B hidden
HIDDEN = 1024
#: 0.6B vocab
VOCAB = 151936
#: 特殊 token
AUDIO_START = 151669
AUDIO_PAD = 151676
AUDIO_END = 151670
EOS_IDS = {151643, 151645}

#: prompt 模板（`context=''` 时官方 `_build_text_prompt` 的**确切常量**）
#: ⚠️ 用 \u3008/\u3009 全角括号**只是注释可读性**；实际字符串是半角 `<|...|>`
_PROMPT_LEFT = ('<|im_start|>system\n<|im_end|>\n'
                '<|im_start|>user\n<|audio_start|>')
_PROMPT_RIGHT = ('<|audio_end|><|im_end|>\n'
                 '<|im_start|>assistant\n')


def total_aftercnn_len(frames: int) -> int:
    """音频 token 数（与官方 `_get_feat_extract_output_lengths` 逐帧一致）。

    3 次 stride-2 conv over 100-frame chunk ⇒ 每满 chunk 13 token。
    """
    if frames <= 0:
        return 0
    n_full = frames // 100
    leave = frames - n_full * 100
    if leave == 0:
        return n_full * 13
    feat = (leave - 1) // 2 + 1
    return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + n_full * 13


class ASR06BBackend(ASRBackend):
    """Qwen3-ASR-0.6B（mask2 INT8）OV 后端：**无 torch**、**无 KV cache**、右对齐。"""

    name = "asr06b"

    def __init__(self,
                 encoder_dir: str,
                 decoder_dir: str,
                 tokenizer_dir: str,
                 embed_npy: str,
                 device: str = "GPU.0",
                 precision: str = "f32",
                 cache_dir: Optional[str] = None,
                 strict_intel: bool = True):
        import openvino as ov
        from transformers import AutoTokenizer, WhisperFeatureExtractor

        core = ov.Core()
        if strict_intel:
            full_name = core.get_property(device, "FULL_DEVICE_NAME")
            assert "Intel" in full_name, f"device {device} not Intel: {full_name}"
        if cache_dir:
            try:
                os.makedirs(cache_dir, exist_ok=True)
                core.set_property({"CACHE_DIR": cache_dir})
            except OSError:
                pass

        prop = {"PERFORMANCE_HINT": "LATENCY"}
        if precision:
            prop["INFERENCE_PRECISION_HINT"] = precision

        # ── encoder：静态 [1,128,2400] + n_valid[1] ─────────────────
        enc_xml = self._find(encoder_dir, ('ov-encoder-06b-fp16-static.xml',
                                           'openvino_encoder_model.xml'))
        self.enc = core.compile_model(enc_xml, device, prop)
        self.enc_infer = self.enc.create_infer_request()

        # ── decoder：静态 [1,512,1024] + attention_mask[1,512] ───────
        dec_xml = self._find(decoder_dir, ('openvino_model.xml',
                                           'openvino_decoder_model.xml'))
        self.dec = core.compile_model(dec_xml, device, prop)
        self.dec_infer = self.dec.create_infer_request()
        self._logits_port = self.dec.outputs[0].get_any_name()

        # 🔴🔴🔳 **APP-098 二.3：编译完 encoder+decoder 后打印 EXECUTION_DEVICES**
        #   reviewer 原话：「asr06b_backend 编译完 encoder 和 decoder 后，
        #   要打印 EXECUTION_DEVICES。」
        #   🔴 **为什么必须打印**：`device='GPU.0'` **只是「请求的设备」**，
        #      **不等于「实际落点」** ⇒ OV 可能悄悄回落到 CPU
        #      （实测 NPU 档 `EXECUTION_DEVICES` 返回**字符串** `'NPU'`，
        #        CPU 档返回**列表** `['CPU']` ⇒ 绝不逐字符拆！）
        #      ⇒ 只有打印出来才能证明「ASR 真的跑在 NPU 上」。
        #   🔴 **归一化**：OV 返回的可能是**字符串**（`'NPU'`）
        #      ⇒ `list('NPU')` 会拆成 `['N','P','U']` ⇒ **误读**。
        #      ⇒ 这里**字符串按单个设备名**处理（逗号分隔可多个）。
        self.exec_devices = {}
        for _role, _model in (('encoder', self.enc), ('decoder', self.dec)):
            self.exec_devices[_role] = self._read_exec_devices(_model)
        _dev_txt = '，'.join(
            '%s=%s' % (_r, ('/'.join(_d) if _d else '?'))
            for _r, _d in self.exec_devices.items())
        print('[asr06b] EXECUTION_DEVICES：%s（请求设备 %s）'
              % (_dev_txt, device), flush=True)

        # ── tokenizer（0.6B 的那一份）────────────────────────────────
        # ⚠️ `chat_template.json` 是 **Processor 专用**（transformers legacy 约定）
        #    ⇒ `AutoTokenizer` 拿不到 chat_template ⇒ 这里**不依赖模板**，
        #    prompt 直接硬编码（见 `_PROMPT_LEFT/_PROMPT_RIGHT`）。
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir,
                                                      fix_mistral_regex=True)
        self.feature_extractor = WhisperFeatureExtractor.from_pretrained(tokenizer_dir)

        # ── 文本 embedding 表（fp32）──────────────────────────────────
        self._W = np.asarray(np.load(embed_npy), dtype=np.float32)
        if self._W.shape != (VOCAB, HIDDEN):
            raise RuntimeError(
                f"embed table shape {self._W.shape} != {(VOCAB, HIDDEN)}；"
                f"这是 R2T2(2048) 的表而不是 0.6B(1024) 的表")

        # ── prompt 模板 ids（左 / 右）────────────────────────────────
        self._ids_left, self._ids_right = self._build_prompt_ids()
        self._ids_right_en = self.tokenizer.encode(
            'language English<asr_text>', add_special_tokens=False)
        self._ids_right_zh = self.tokenizer.encode(
            'language Chinese<asr_text>', add_special_tokens=False)

        # 分项计时（验收用）
        self.probe = {"enc_ms": [], "decode_ms": [], "n_decode": [],
                      "prompt_len": [], "n_audio": [], "out_tokens": []}

    # ── 小工具 ───────────────────────────────────────────────────────
    @staticmethod
    def _find(d: str, names: Tuple[str, ...]) -> str:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
        raise FileNotFoundError(
            f"none of {names} found in {d}")

    @staticmethod
    def _read_exec_devices(model) -> List[str]:
        """读 `EXECUTION_DEVICES` 并**归一化**成设备名列表（APP-098 二.3）。

        🔴🔴🔳 **绝不能逐字符拆字符串**（实测，OV 2026.4.1）：
          - NPU 档 ⇒ 返回**字符串** `'NPU'`
          - CPU 档 ⇒ 返回**列表** `['CPU']`
        ⇒ `list('NPU')` = `['N','P','U']` ⇒ **误读成「三个设备」**
        ⇒ 正确：**字符串按「单个设备名」**处理（逗号分隔可多个）。

        🔴 **「属性不存在」≠「跑在 CPU 上」** ⇒ 读不到就返回**空列表**
           （调用方据此说「落点未知」，**不猜**）。
        """
        try:
            raw = model.get_property('EXECUTION_DEVICES')
        except Exception:
            return []
        if raw is None:
            return []
        if isinstance(raw, str):
            parts = [p.strip() for p in raw.split(',')]
            return [p for p in parts if p]
        try:
            return [str(x).strip() for x in raw if str(x).strip()]
        except Exception:
            return []

    def _build_prompt_ids(self) -> Tuple[List[int], List[int]]:
        ids_left = self.tokenizer.encode(_PROMPT_LEFT, add_special_tokens=False)
        ids_right = self.tokenizer.encode(_PROMPT_RIGHT, add_special_tokens=False)
        # 硬编码常量必须与官方一致：<|audio_start|> 结尾 / <|audio_end|> 开头
        assert ids_left[-1] == AUDIO_START, ids_left[-5:]
        assert ids_right[0] == AUDIO_END, ids_right[:5]
        return ids_left, ids_right

    def _right_ids(self, force_language: Optional[str]) -> List[int]:
        if not force_language:
            return self._ids_right
        low = str(force_language).lower()
        if low.startswith('zh') or low.startswith('ch'):
            return list(self._ids_right) + list(self._ids_right_zh)
        if low.startswith('en'):
            return list(self._ids_right) + list(self._ids_right_en)
        # 其它语种：官方口径是拼进 prompt 末尾
        extra = self.tokenizer.encode(
            f"language {force_language}<asr_text>", add_special_tokens=False)
        return list(self._ids_right) + list(extra)

    # ── ASRBackend 接口 ─────────────────────────────────────────────
    def init_streaming_state(self, *, context: str = "",
                             language: Optional[str] = None,
                             unfixed_chunk_num: int,
                             unfixed_token_num: int,
                             chunk_size_sec: float) -> ASRStreamingState:
        chunk_size_samples = max(1, int(round(chunk_size_sec * SAMPLE_RATE)))
        return ASRStreamingState(
            unfixed_chunk_num=unfixed_chunk_num,
            unfixed_token_num=unfixed_token_num,
            chunk_size_sec=chunk_size_sec,
            chunk_size_samples=chunk_size_samples,
            prompt_raw=self._build_text_prompt(context, language),
            force_language=language,
            context=context,
        )

    def _build_text_prompt(self, context: str, force_language: Optional[str]) -> str:
        base = _PROMPT_LEFT + _PROMPT_RIGHT
        if force_language:
            base = base + f"language {force_language}<asr_text>"
        return base

    # ── encoder ─────────────────────────────────────────────────────
    def encode_audio(self, wav: np.ndarray):
        """返回 (audio_embeds [N_audio, 1024], n_real_frames, N_audio)。

        ⚠️ 与 R2T2 后端**不同**：这里返回的是**音频 embedding 本身**
        （不是 `encoder_hidden_states` 端口用的 2048 维 hidden），
        因为 0.6B 的 decoder 直接吃 `inputs_embeds`。
        """
        feats_real, _, n_real, N_audio = extract_audio_features(
            self.feature_extractor, wav, return_torch=False)
        mel = feats_real[0]
        mel_len = int(mel.shape[1])
        if mel_len <= 0:
            return np.zeros((0, HIDDEN), dtype=np.float32), 0, 0
        if mel_len > ENC_MAX_FRAMES:
            raise ValueError(
                f"segment too long: {mel_len} mel frames > {ENC_MAX_FRAMES} "
                f"(≈{mel_len * 160 / 16000:.1f}s)")
        enc_in = np.zeros((1, 128, ENC_MAX_FRAMES), dtype=np.float32)
        enc_in[0, :, :mel_len] = mel
        n_valid = np.array([N_audio], dtype=np.int32)
        assert int(N_audio) == total_aftercnn_len(mel_len), (
            f"N_audio mismatch: {N_audio} vs {total_aftercnn_len(mel_len)}")
        out = self.enc_infer.infer([enc_in, n_valid])
        h = np.asarray(out[0])[0, :N_audio, :]      # (N_audio, 1024)
        return h.astype(np.float32), n_real, N_audio

    # ── embeds 拼装（照搬 p3_ov_app.py::build_embeds）───────────────
    def build_inputs_embeds(self, audio_emb: np.ndarray,
                            prefix_ids: List[int],
                            force_language: Optional[str] = None) -> np.ndarray:
        """left_ids + [audio] + right_ids(+语种) + prefix_ids。

        🔴 **顺序不可换**：官方 `masked_scatter` 语义是「音频 embedding 铺在
        `<|audio_pad|>` 展开出来的 n 个位置上」⇒ 文本左段、音频、右段、
        prefix 的相对顺序必须与 token 序列完全一致。
        """
        parts = [np.ascontiguousarray(self._W[list(self._ids_left)], dtype=np.float32),
                 np.asarray(audio_emb, dtype=np.float32),
                 np.ascontiguousarray(self._W[self._right_ids(force_language)],
                                      dtype=np.float32)]
        if prefix_ids:
            parts.append(np.ascontiguousarray(self._W[list(prefix_ids)],
                                              dtype=np.float32))
        emb = np.concatenate(parts, axis=0)
        if emb.shape[0] > DEC_PROMPT_LEN:
            raise ValueError(
                f"sequence {emb.shape[0]} > IR static length {DEC_PROMPT_LEN}；"
                "0.6B decoder 无 KV cache ⇒ 静默截断会产出看似正常的错误转写，"
                "必须显式失败")
        return emb

    # ── greedy（无 KV ⇒ 每步全序列重算，右对齐）───────────────────
    def greedy_decode_with_prefix(self, audio_emb: np.ndarray,
                                  prefix_ids: List[int],
                                  max_new_tokens: int,
                                  force_language: Optional[str] = None) -> List[int]:
        emb = self.build_inputs_embeds(audio_emb, prefix_ids, force_language)
        L = int(emb.shape[0])
        self.probe['prompt_len'].append(L)
        self.probe['n_audio'].append(int(audio_emb.shape[0]))

        # ★ 右对齐：内容放末尾 ⇒ IR 恒取位置 511 = 最后一个真实 token
        buf = np.zeros((DEC_PROMPT_LEN, HIDDEN), dtype=np.float32)
        buf[DEC_PROMPT_LEN - L:] = emb
        am = np.zeros((1, DEC_PROMPT_LEN), dtype=np.int64)
        am[0, DEC_PROMPT_LEN - L:] = 1

        import time
        t0 = time.perf_counter()
        out = self.dec_infer.infer([buf[None, :, :], am])
        logits = np.asarray(out[self._logits_port]).reshape(-1)
        nxt = int(np.argmax(logits))
        if nxt in EOS_IDS:
            self.probe['decode_ms'].append((time.perf_counter() - t0) * 1000)
            self.probe['n_decode'].append(0)
            self.probe['out_tokens'].append(0)
            return []
        generated = [nxt]

        n_dec = 0
        for _ in range(max(1, max_new_tokens) - 1):
            # ⚠️ 无 KV ⇒ 每步把**已生成的全部 token** 的 embedding 追加到序列尾部，
            #    并整体右对齐（等价 p3_ov_app.py::generate 的
            #    `cat([base, torch.cat(gen_embs, dim=1)])` + 右对齐）。
            #    🔴 必须是**全部**已生成 token，不能只取最后一个
            #    （只取最后一个 ⇒ 第 3 步起上下文缺 token ⇒ 与参考实现不等价）。
            cur = np.concatenate([emb, self._W[generated]], axis=0)
            L2 = int(cur.shape[0])
            if L2 > DEC_PROMPT_LEN:
                self.probe['decode_ms'].append((time.perf_counter() - t0) * 1000)
                self.probe['n_decode'].append(n_dec)
                self.probe['out_tokens'].append(len(generated))
                break
            buf2 = np.zeros((DEC_PROMPT_LEN, HIDDEN), dtype=np.float32)
            buf2[DEC_PROMPT_LEN - L2:] = cur
            am2 = np.zeros((1, DEC_PROMPT_LEN), dtype=np.int64)
            am2[0, DEC_PROMPT_LEN - L2:] = 1
            out = self.dec_infer.infer([buf2[None, :, :], am2])
            logits = np.asarray(out[self._logits_port]).reshape(-1)
            nxt = int(np.argmax(logits))
            n_dec += 1
            if nxt in EOS_IDS:
                break
            generated.append(nxt)
        self.probe['decode_ms'].append((time.perf_counter() - t0) * 1000)
        self.probe['n_decode'].append(n_dec)
        self.probe['out_tokens'].append(len(generated))
        return generated

    def generate_with_prefix(self, state: ASRStreamingState,
                             audio_accum: np.ndarray,
                             prefix_text: str,
                             max_new_tokens: int) -> str:
        import time
        t0 = time.perf_counter()
        audio_emb, _, _ = self.encode_audio(audio_accum)
        self.probe['enc_ms'].append((time.perf_counter() - t0) * 1000)
        prefix_ids = (self.tokenizer.encode(prefix_text, add_special_tokens=False)
                      if prefix_text else [])
        out_ids = self.greedy_decode_with_prefix(
            audio_emb, prefix_ids, max_new_tokens,
            force_language=getattr(state, 'force_language', None))
        return self.tokenizer.decode(out_ids, skip_special_tokens=True)


def load_chat_template_06b(tokenizer_dir: str) -> str:
    """读 0.6B 的 `chat_template.json`（**仅供诊断/对照**，后端本身不依赖它）。"""
    p = os.path.join(tokenizer_dir, 'chat_template.json')
    with open(p, encoding='utf-8') as f:
        return json.load(f)['chat_template']
