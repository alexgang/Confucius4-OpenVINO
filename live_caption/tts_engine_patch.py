#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""qwen3tts_patch.py — 修复 BabelVox NPU 路径的「解码器形状 / 生成上限」耦合缺陷。

## 缺陷（BabelVox 1.7.1 `pipeline.py`）

`max_decoder_frames` 被同时用作两个**语义完全不同**的参数：

| 角色 | 代码位置 | 含义 |
|---|---|---|
| ① NPU 解码器静态形状 | `_load_npu_models`: `m.reshape({"codes":[1,16,self.max_decoder_frames]})` | 决定**解码耗时**（256 帧 → 恒 0.67 s/次） |
| ② **生成帧数上限** | `generate_stream`: `effective_max = min(max_new_tokens, talker_limit, decoder_limit)` | 决定**音频是否被截断** |

后果：为了提速把 `max_decoder_frames` 从 256 调到 32，
**角色①变快（RTF 3.19→1.07），但角色②把长句在 32 帧（2.56 s）处强制截断**，
且 `hit_eos=(len(all_codes) < max_new_tokens)` 为 False ⇒ 末尾还叠了 100 ms 淡出。
⇒ 所有基于该配置的「RTF 1.07 / 首包 0.70 s」数据**全部作废**。

## 本模块的修法：解耦 + 多桶解码器

1. `max_decoder_frames` **保持 256**（角色②正确，长句不再被截断）。
2. 额外编译若干**小形状** tokenizer_decoder（角色①），
   按 chunk 实际帧数挑**最小够用的桶** ⇒ 单次解码从 256 帧的 0.67 s 降到小桶耗时。
3. 多桶与 talker 桶同理走「选最小够用的桶」策略。

前提假设（**需实测验证**）：tokenizer_decoder 是 **causal** ConvNet
⇒ 尾部 padding 长度不影响前缀输出 ⇒ 分块解码与整段解码应逐位等价。
`verify_patch_equivalence.py` 负责验证这一点。
"""
from __future__ import annotations

import os
from typing import Sequence

import numpy as np

from babelvox.pipeline import BabelVox


class MultiDecoderBabelVox(BabelVox):
    """BabelVox + 多桶 tokenizer_decoder（解耦「解码器形状」与「生成上限」）。

    新增参数
    --------
    decoder_buckets : Sequence[int] | None
        除 ``max_decoder_frames`` 外，额外编译的解码器桶（帧数）。
        解码时选**最小 ≥ 实际帧数**的桶。None 表示不额外编译（保持原行为）。
    """

    def __init__(self, *args, decoder_buckets: Sequence[int] | None = None,
                 **kwargs):
        self.decoder_buckets = sorted(set(decoder_buckets or ()))
        self._dec_bucket_models: dict[int, object] = {}
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # 编译额外的解码器桶
    # ------------------------------------------------------------------
    def _load_npu_models(self, core, export_dir):
        super()._load_npu_models(core, export_dir)
        if not self.decoder_buckets:
            return
        import time as _t
        from babelvox.pipeline import logger
        logger.info("    Compiling %d extra tokenizer_decoder bucket(s): %s",
                    len(self.decoder_buckets), self.decoder_buckets)
        for n in self.decoder_buckets:
            if n == self.max_decoder_frames:
                continue
            t1 = _t.time()
            m = core.read_model(os.path.join(export_dir,
                                             "tokenizer_decoder.xml"))
            m.reshape({"codes": [1, 16, n]})
            cm, dev = self._compile_npu(core, m, f"tokenizer_decoder@{n}")
            self._dec_bucket_models[n] = cm
            logger.info("    Tok decoder @%3d: %.1fs (%s)", n, _t.time() - t1, dev)

    # ------------------------------------------------------------------
    # 选桶 + 解码
    # ------------------------------------------------------------------
    def _select_decoder(self, num_frames: int):
        """选最小够用的解码器。返回 (model, 桶大小)。"""
        best = None
        for n in sorted(self._dec_bucket_models):
            if n >= num_frames and (best is None or n < best):
                best = n
        if best is not None:
            return self._dec_bucket_models[best], best
        return self.tok_decoder, self.max_decoder_frames

    def _decode_audio(self, codes_array):
        """与上游同语义，但按帧数选最小桶。

        上游 NPU 分支是：
            padded = zeros((1,16,max_decoder_frames)); padded[:,:,:n]=codes
            wav_out = tok_decoder({"codes": padded}); wav = out[:n*1920]
        本实现保持**完全相同**的取样语义，只把「跑满 max_decoder_frames」
        换成「跑满选中的最小桶」。
        """
        num_frames = codes_array.shape[2]
        if self.is_npu:
            model, bucket = self._select_decoder(num_frames)
            padded = np.zeros((1, 16, bucket), dtype=np.int64)
            padded[:, :, :num_frames] = codes_array
            wav_out = model({"codes": padded})
            expected_samples = num_frames * 1920
            wav = wav_out[0].squeeze()[:expected_samples]
        else:
            wav_out = self.tok_decoder({"codes": codes_array})
            wav = wav_out[0].squeeze()
        return np.clip(wav, -1.0, 1.0)


class QuantEvalBabelVox(MultiDecoderBabelVox):
    """多桶解码器 + **可替换 IR 路径**（用于量化对照实验）。

    ## 与上游 `BabelVox` 的差异

    | # | 上游 | 本类 |
    |---|---|---|
    | ① | IR 路径写死 `export_dir/int8/<name>.xml` | `ir_map` 可逐组件替换 ⇒ 可换自量化 IR |
    | ② | NPU 档解码器只有**一个**静态形状（`max_decoder_frames`） | **多桶**（`decoder_buckets`），按帧数选最小够用的 |
    | ③ | talker 静态桶分支绑在 `is_npu` 上 | 用 `ir_map`/`device` 组合控制，不额外解耦 |

    ## ⚠️ 为什么用 `device="NPU"` 构造（而不是 `device="CPU"`）

    上游 `_run_talker` 只在 `self.is_npu` 为 True 时才走 talker 静态桶：

    ```python
    if self.is_npu:
        if self.talker_bucket_sizes:
            pad_len, model = self._select_bucket(real_len)
        else:
            pad_len, model = self.max_talker_seq, self.talker
        # ... padding + 静态形状
    else:
        out = self.talker({"inputs_embeds": seq_embeds, ...})   # 动态维
    ```

    而 GPU/NPU 上的 talker IR 是**静态编译**的 ⇒ 走动态维分支会形状不匹配。
    ⇒ 必须让 `is_npu=True`（= `device="NPU"`），
    这样 talker 分桶、`effective_max` clamp 都走上游**原生**逻辑
    ⇒ 与 `eval_qwen3tts_golden2.py`（现役配置）**同一套代码路径**。

    ⚠️ **注意**：`device="NPU"` ⇒ `effective_max = min(max_new_tokens,
    talker_limit, decoder_limit)` 生效 ⇒ `max_decoder_frames` 必须 ≥ 期望帧数，
    否则长句被砍（就是「一参两用」那个坑）。本类默认 `max_decoder_frames=256`。
    """

    def __init__(self, *args, ir_map=None, decoder_buckets=None,
                 cache_dir=None, export_dir=None, **kwargs):
        self.ir_map = dict(ir_map or {})
        self._cache_dir = cache_dir
        # ⚠️ 上游 `__init__` 会自行决定 export_dir（None ⇒ download_models()）
        #    ⇒ 这里**提前**算好，保证 `_ir_path` 的 fallback 路径可用
        #    （CPU 路径不会调 `_load_npu_models`，`_model_dir` 不会被设置）。
        if export_dir is None:
            # 🔴 离线优先：`download_models()` 默认联网查 HF，Windows 上偶发
            #    `WinError 10053` 让整个评测挂掉 ⇒ 模型已缓存，优先走离线。
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from babelvox import download_models
            try:
                export_dir = download_models()
            except Exception:
                os.environ.pop("HF_HUB_OFFLINE", None)
                export_dir = download_models()
        elif not os.path.isdir(export_dir):
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from babelvox import download_models
            try:
                export_dir = download_models(local_dir=export_dir)
            except Exception:
                os.environ.pop("HF_HUB_OFFLINE", None)
                export_dir = download_models(local_dir=export_dir)
        self._model_dir = os.path.join(export_dir, "int8")
        super().__init__(*args, decoder_buckets=decoder_buckets,
                         cache_dir=cache_dir, export_dir=export_dir, **kwargs)
        # 🔴 CPU 路径：上游 `__init__` 内联拼 `model_dir`，**忽略 ir_map**
        #    ⇒ CPU 档必须在这里把受影响组件**重新编译**一遍。
        if self.ir_map and not self.is_npu:
            self._recompile_cpu_with_ir_map()

    # ------------------------------------------------------------------
    # ①-b CPU 路径的 IR 替换（上游 `__init__` 内联拼路径，只能事后重编）
    # ------------------------------------------------------------------
    def _recompile_cpu_with_ir_map(self):
        import openvino as ov
        core = ov.Core()
        if self._cache_dir:
            core.set_property({"CACHE_DIR": self._cache_dir})
        dev = "CPU"
        if "speaker_encoder" in self.ir_map:
            p = self._ir_path("speaker_encoder")
            if os.path.exists(p):
                self.speaker_enc = core.compile_model(p, dev)
        if "talker" in self.ir_map:
            p = self._ir_path("talker")
            if os.path.exists(p):
                self.talker = core.compile_model(p, dev)
        if "cp_prefill" in self.ir_map and self.use_cp_kv_cache:
            p = self._ir_path("cp_prefill")
            if os.path.exists(p):
                self.cp_prefill = core.compile_model(p, dev)
        if "cp_decode" in self.ir_map and self.use_cp_kv_cache:
            p = self._ir_path("cp_decode")
            if os.path.exists(p):
                self.cp_decode = core.compile_model(p, dev)
        if "tokenizer_decoder" in self.ir_map:
            p = self._ir_path("tokenizer_decoder")
            if os.path.exists(p):
                self.tok_decoder = core.compile_model(p, dev)

    # ------------------------------------------------------------------
    # ② talker 静态桶（**不绑 is_npu** ⇒ iGPU 也能用）
    # ------------------------------------------------------------------
    def _run_talker(self, seq_embeds, real_len):
        """与上游同语义，但静态桶分支由「有没有 talker 桶」决定（不看 `is_npu`）。

        上游只在 `is_npu` 时才用桶 ⇒ iGPU 档（`device="CPU"` 构造 +
        talker 放 GPU.0）会走动态维分支，而 GPU 插件不接动态维 ⇒ 形状不匹配。
        """
        pos_ids = np.arange(real_len, dtype=np.int64).reshape(1, 1, -1)
        pos_ids = np.broadcast_to(pos_ids, (3, 1, real_len)).copy()
        if self.talker_bucket_sizes:
            pad_len, model = self._select_bucket(real_len)
            padded_e = np.zeros((1, pad_len, self.hidden_size), dtype=np.float32)
            padded_e[:, :real_len, :] = seq_embeds
            padded_p = np.zeros((3, 1, pad_len), dtype=np.int64)
            padded_p[:, :, :real_len] = pos_ids
            out = model({"inputs_embeds": padded_e, "position_ids": padded_p})
        elif self.is_npu:
            pad_len = self.max_talker_seq
            padded_e = np.zeros((1, pad_len, self.hidden_size), dtype=np.float32)
            padded_e[:, :real_len, :] = seq_embeds
            padded_p = np.zeros((3, 1, pad_len), dtype=np.int64)
            padded_p[:, :, :real_len] = pos_ids
            out = self.talker({"inputs_embeds": padded_e, "position_ids": padded_p})
        else:
            out = self.talker({"inputs_embeds": seq_embeds,
                               "position_ids": pos_ids})
        logits = out["logits"][:, real_len - 1:real_len, :]
        hidden = out["hidden_states"][:, real_len - 1:real_len, :]
        return logits, hidden

    def _select_bucket(self, real_len: int):
        """选最小 ≥ real_len 的桶。**超桶时抛错**（不静默截断）。"""
        for bsize in self.talker_bucket_sizes:
            if bsize >= real_len:
                return bsize, self.talker_buckets[bsize]
        raise ValueError(
            f"talker 序列 {real_len} 超过最大桶 {self.talker_bucket_sizes[-1]}；"
            f"请加大 talker_buckets（长句需要 512 桶）")

    # ------------------------------------------------------------------
    # ① IR 路径替换
    # ------------------------------------------------------------------
    def _ir_path(self, name):
        """自量化目录优先，否则回退到原 IR。"""
        d = self.ir_map.get(name)
        if d:
            cand = os.path.join(d, f"{name}.xml")
            if os.path.exists(cand):
                return cand
        return os.path.join(self._model_dir, f"{name}.xml")

    def _load_npu_models(self, core, export_dir):
        """覆写：IR 路径可替换 + 解码器多桶。"""
        import time as _t
        from babelvox.pipeline import logger
        self._model_dir = export_dir

        # --- speaker encoder ---
        t1 = _t.time()
        m = core.read_model(self._ir_path("speaker_encoder"))
        m.reshape({"mel_spectrogram": [1, self.max_speaker_frames, 128]})
        self.speaker_enc, dev = self._compile_npu(core, m, "speaker_encoder")
        logger.info("    Speaker encoder: %.1fs (%s)", _t.time() - t1, dev)

        # --- talker 静态桶 ---
        talker_xml = self._ir_path("talker")
        if self.talker_bucket_sizes:
            self.talker_buckets = {}
            for bsize in self.talker_bucket_sizes:
                t1 = _t.time()
                m = core.read_model(talker_xml)
                m.reshape({"inputs_embeds": [1, bsize, 1024],
                           "position_ids": [3, 1, bsize]})
                self.talker_buckets[bsize], dev = self._compile_npu(
                    core, m, f"talker@{bsize}")
                logger.info("    Talker @%3d: %.1fs (%s)", bsize,
                            _t.time() - t1, dev)
            self.max_talker_seq = max(self.talker_bucket_sizes)
        else:
            t1 = _t.time()
            m = core.read_model(talker_xml)
            m.reshape({"inputs_embeds": [1, self.max_talker_seq, 1024],
                       "position_ids": [3, 1, self.max_talker_seq]})
            self.talker, dev = self._compile_npu(core, m, "talker")
            logger.info("    Talker (28L): %.1fs (%s)", _t.time() - t1, dev)

        # --- code predictor（CPU）---
        t1 = _t.time()
        if self.use_cp_kv_cache:
            self.cp_prefill = core.compile_model(
                self._ir_path("cp_prefill"), "CPU")
            self.cp_decode = core.compile_model(
                self._ir_path("cp_decode"), "CPU")
        else:
            self.code_predictor = core.compile_model(
                self._ir_path("code_predictor"), "CPU")
        self.cp_on_cpu = True
        logger.info("    CP prefill+decode: %.1fs (CPU)", _t.time() - t1)

        # --- tokenizer decoder：多桶 ---
        dec_xml = self._ir_path("tokenizer_decoder")
        t1 = _t.time()
        m = core.read_model(dec_xml)
        m.reshape({"codes": [1, 16, self.max_decoder_frames]})
        self.tok_decoder, dev = self._compile_npu(core, m, "tokenizer_decoder")
        logger.info("    Tok decoder @%3d: %.1fs (%s)",
                    self.max_decoder_frames, _t.time() - t1, dev)

        if self.decoder_buckets:
            self._dec_bucket_models = {}
            for n in self.decoder_buckets:
                if n == self.max_decoder_frames:
                    continue
                t1 = _t.time()
                m = core.read_model(dec_xml)
                m.reshape({"codes": [1, 16, n]})
                cm, dev = self._compile_npu(core, m, f"tokenizer_decoder@{n}")
                self._dec_bucket_models[n] = cm
                logger.info("    Tok decoder @%3d: %.1fs (%s)",
                            n, _t.time() - t1, dev)
