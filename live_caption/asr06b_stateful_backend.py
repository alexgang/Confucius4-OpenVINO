# -*- coding: utf-8 -*-
r"""asr06b_stateful_backend.py — **APP-101/102/103**：Qwen3-ASR-0.6B stateful（KV cache）OV 后端。

## 为什么单独一个模块
MiniMVP rc8 只带 **stateful** 解码器 ``ov-dec-06b-stateful-int8sym``（带 KV
cache）；无 KV 的旧解码器只留在开发树当 WER/RTF 配对基线，不进包。两者端口与
解码语义不同，故各用一个后端类，由 dev 侧开关选择。

## 口径来源（APP-103 裁定：只读引用，不改 ASR 模块任何文件）
``C:\Users\Trekker-PTL\qwen3asr_06b\b_kit_stateful\scripts\bk_run.py``
（ASR 模块已验收、不依赖 torch 的 stateful 实现）：

* 端口：``inputs_embeds [1, 1..512, 1024]`` / ``attention_mask`` /
  ``position_ids`` / ``beam_idx``；
* NPU 编译属性（bk_run 第 71–78、133–141 行）：
  ``NPU_USE_NPUW=YES``、``NPUW_LLM=YES``、
  ``NPUW_LLM_MAX_PROMPT_LEN=512``、``NPUW_LLM_MIN_RESPONSE_LEN=64``；
  🔴 **encoder 不能带 NPUW 属性**（NPUW_LLM 会触发 StatefulToStateless pass）；
* **每次 generate 新建 InferRequest + ``reset_state()``** ⇒ 每个 640 ms 块 /
  每个段落都从干净的 KV 开始（路线 A：调用内 KV，不跨调用复用）；
* EOS / PAD 用导出元数据 ``assets/prompt.json`` 的 **id**（eos=151645 /
  pad=151643）；tokenizer 里这些 token 的 content 是空串，**不能按文本匹配**；
* embedding 表 = ``assets/embed_tokens.npy``（151936×1024，fp16），
  与包内 ``models/embed_tokens_06b_f16.npy`` 逐字节同一份
  （SHA256 ``e8d4448c…`` / 311 165 056 B）；不依赖 torch；
* prompt 上界 512：IR 的 ``inputs_embeds`` 是 ``[1, 1..512, 1024]``，
  和 NPUW 的 ``MAX_PROMPT_LEN=512`` 是同一个约束。前缀 + 音频 token +
  生成 token 超限时，**截掉最旧的前缀**，截断次数记进日志；不为此改 IR。

## 与 App 流式接口的适配
``streaming_asr`` 每 640 ms 调一次
``generate_with_prefix(state, audio_accum, prefix, budget)``；本后端每次调用
重新拼 embeds、新建 InferRequest，prefill 一次后逐步 decode。
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

import numpy as np

from backends import ASRBackend, ASRStreamingState, SAMPLE_RATE, extract_audio_features

# ── IR 与常量 ───────────────────────────────────────────────────────────
#: stateful IR 的序列硬上界（inputs_embeds [1, 1..512, 1024]）
MAX_STATEFUL_TOK = 512
#: 0.6B 的 encoder 静态 mel 帧数
ENC_MAX_FRAMES = 2400
#: 0.6B hidden / vocab
HIDDEN = 1024
VOCAB = 151936
#: 特殊 token
AUDIO_START = 151669
AUDIO_PAD = 151676
AUDIO_END = 151670
#: 🔴 导出元数据 b_kit_stateful/assets/prompt.json 的 id（bk_run 第 167–168 行）
EOS_TOKEN_ID = 151645
PAD_TOKEN_ID = 151643
EOS_IDS = frozenset((EOS_TOKEN_ID, PAD_TOKEN_ID))

#: NPU 编译属性（**只给 stateful decoder**；encoder 与 GPU 档都不带）
#:
#: 🔴🔴🔳 **APP-118 §1：并入 ASR-065 的结果**（用户 11-20 决定）：
#:   `NPUW_LLM_MAX_PROMPT_LEN`：**512 → 320**
#:   （依据见 `qwen3asr_06b/dev/asr065_handoff.md`：
#:     `T = 18（模板 token）+ aftercnn_len(mel_frames)（音频 token）
#:        + len(tok.encode(prefix_text))（前缀 token）`
#:     段长上限 20.48 s ⇒ 音频 token 266 ⇒ `T = 18 + 266 + 前缀`
#:     ⇒ 前缀 ≤ **36 token** 时 T ≤ 320；实测最大前缀 **29 token**（余量 7）
#:     ⇒ 前缀**没有硬上限**（随段内累积文本增长）⇒ 必须靠**截断**兜底。）
#:   `NPUW_LLM_MIN_RESPONSE_LEN`：**保持 64**（不变，理由见 handoff §一）
NPUW_PROPS = {
    'NPU_USE_NPUW': 'YES',
    'NPUW_LLM': 'YES',
    'NPUW_LLM_MAX_PROMPT_LEN': '320',
    'NPUW_LLM_MIN_RESPONSE_LEN': '64',
}

#: 🔴🔴🔳 **APP-118 §1：encoder 分档开关（`asr_enc_tiers`），默认 OFF。**
#:
#: 🔴 **默认必须 off** ⇒ 不设置时**行为与 ASR-065 之前完全一致**
#:   （单档 2400 mel 帧；不构建、不多编、不多占内存）。
#:   档位：`{400, 800, 1600, 2400}`（2400 = 24.0 s = 当前单档）。
#:   开启时：**运行时从 base IR 现场构建各档 → 直接 compile → 不落盘**。
ASR_ENC_TIERS = (400, 800, 1600, 2400)

#: 🔴🔴🔳 **APP-118 §1：前缀截断计数**（ASR-065 §四 的日志字段）。
#:   `prefix_truncations`（int，累加）＝ 本次会话累计触发降级的次数。
#:   ⚠️ **正常素材不会触发**（实测 3 素材各 1 轮 ⇒ 计数 0、transcript 逐字节不变）
#:   ⇒ **线上如果这个计数持续增长 ⇒ 说明段长/前缀策略有异常，值得告警**。
PROBE_PREFIX_TRUNCATIONS = 'prefix_truncations'


def _env_tiers_enabled() -> bool:
    """`asr_enc_tiers` 开关是否打开（**默认 OFF**）。

    🔴🔴🔳 **APP-118 §1（并入 ASR-065 §五）**：编码器分档是**可选开关**，
      **默认 off** ⇒ 不设置时**行为与现状完全一样**
      （单档 2400 mel 帧；不构建、不多编、不多占内存）。

    🔴 **读取方式**（与本仓既有 `asr_runtime_switches` 风格一致）：
      环境变量 `ASR_ENC_TIERS` ∈ {`1`,`on`,`true`,`yes`} ⇒ 开。
    """
    v = (os.environ.get('ASR_ENC_TIERS', '') or '').strip().lower()
    return v in ('1', 'on', 'true', 'yes')


#: 🔴🔴🔳 **ASR-065 §五：构建前必须断言每档 `patched == 60`**。
#:   （这份 IR 上尺寸相关常量的数量；**IR 变了就退单档** ⇒ 不猜。）
EXPECTED_PATCHED_CONSTS = 60


def _patch_size_consts(model, G: int, T: int) -> list:
    """把 **60 处尺寸相关常量**改掉（ASR-065 §五 的三步法第 ② 步）。

    🔴 **为什么必须 patch**：这份 encoder IR 是**完全静态**的
      （1577 个 layer 的端口维度全烘死成 2400/24/312）
      ⇒ 只 `reshape` 会让 OV 的 shape inference 重算整张图 ⇒ **fail-closed 抛异常**。
      ⇒ 必须把尺寸相关常量同步改掉。

    🔴 **顺序不可换**：① 动态 reshape → ② patch → ③ 静态 reshape
      （先 patch 再静态 reshape ⇒ 挂在第一个 Reshape；
        先静态 reshape 再 patch ⇒ 挂在后面的 `aten::view/Reshape_1`）。
    """
    import openvino as ov
    patched = []

    def swap(node, new_vals):
        node.output(0).replace(
            ov.opset13.constant(np.array(new_vals, dtype=np.int64)).output(0))
        patched.append({'node': node.get_friendly_name(),
                        'new': list(new_vals)})

    for op in model.get_ordered_ops():
        if op.get_type_name() != 'Constant':
            continue
        try:
            d = np.asarray(op.get_data())
        except Exception:
            continue
        if d.dtype.kind not in 'iu':
            continue
        r = d.ravel().tolist()
        new = None
        if r == [24, 100, 128]:
            new = [G, 100, 128]
        elif r == [24, 13, 7680]:
            new = [G, 13, 7680]
        elif r == [312, -1]:
            new = [T, -1]
        elif r == [312, 14, -1]:
            new = [T, 14, -1]
        elif r == [1, 1, 1, 312]:
            new = [1, 1, 1, T]
        elif r == [1, 1, 312, 312]:
            new = [1, 1, T, T]
        elif len(r) == 312 and r == list(range(312)):
            # 🔴 `aten::arange/Range` 的常量值本身就是 arange(312)
            new = list(range(T))
        if new is not None:
            swap(op, new)
    return patched


def _build_encoder_tier(enc_xml: str, N: int, device: str):
    """🔴 **运行时从 base IR 现场构建一档静态 encoder 并直接 compile（不落盘）**。

    返回 ``(info, compiled_model_or_None)``。
    🔴 **断言 `patched == 60`** ⇒ 不满足 ⇒ **退回单档 2400**（不猜、不硬编）。
    """
    import openvino as ov
    import time as _time
    G = N // 100
    T = total_aftercnn_len(N)
    info = {'N': N, 'G': G, 'T': T}
    t0 = _time.perf_counter()
    try:
        m = ov.Core().read_model(enc_xml)
        # ① 先放宽成动态维（让 OV 接受形状变化）
        m.reshape({'input_features':
                   ov.PartialShape([1, 128, ov.Dimension(1, 2400)])})
        # ② patch 尺寸相关常量
        patched = _patch_size_consts(m, G, T)
        # ③ 再收回静态
        m.reshape({'input_features': ov.PartialShape([1, 128, N])})
        info['build_s'] = round(_time.perf_counter() - t0, 3)
        info['n_patched'] = len(patched)
    except Exception as e:
        info['ok'] = False
        info['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
        info['n_patched'] = 0
        return info, None
    # 🔴 断言：patched 数必须 = 60（IR 变了就退单档）
    if info['n_patched'] != EXPECTED_PATCHED_CONSTS:
        info['ok'] = False
        info['error'] = ('patched=%d != 期望 %d ⇒ IR 结构已变 ⇒ 退回 2400 单档'
                         % (info['n_patched'], EXPECTED_PATCHED_CONSTS))
        return info, None
    t1 = _time.perf_counter()
    try:
        cm = ov.Core().compile_model(m, device)
        info['compile_s'] = round(_time.perf_counter() - t1, 3)
        info['ok'] = True
        return info, cm
    except Exception as e:
        info['ok'] = False
        info['error'] = 'compile: %s: %s' % (type(e).__name__, str(e)[:300])
        return info, None


def pick_encoder_tier(frames: int, tiers=ASR_ENC_TIERS):
    """按实际 mel 帧数选**最小能放下的档**；放不下 ⇒ ``None``（**不得静默截断**）。"""
    for n in sorted(tiers):
        if frames <= n:
            return n
    return None

#: prompt 模板（context='' 时官方 _build_text_prompt 的确切常量）
_PROMPT_LEFT = ('<|im_start|>system\n<|im_end|>\n'
                '<|im_start|>user\n<|audio_start|>')
_PROMPT_RIGHT = ('<|audio_end|><|im_end|>\n'
                 '<|im_start|>assistant\n')


def total_aftercnn_len(frames: int) -> int:
    """音频 token 数（与官方 _get_feat_extract_output_lengths 逐帧一致）。"""
    if frames <= 0:
        return 0
    n_full = frames // 100
    leave = frames - n_full * 100
    if leave == 0:
        return n_full * 13
    feat = (leave - 1) // 2 + 1
    return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + n_full * 13


class ASR06BStatefulBackend(ASRBackend):
    """Qwen3-ASR-0.6B stateful（KV cache）OV 后端：GPU.0 / NPU 两档。"""

    name = "asr06b_stateful"

    def __init__(self,
                 encoder_dir: str,
                 decoder_dir: str,
                 tokenizer_dir: str,
                 embed_npy: str,
                 device: str = "GPU.0",
                 precision: str = "f16",
                 cache_dir: Optional[str] = None,
                 strict_intel: bool = True):
        import openvino as ov
        from transformers import AutoTokenizer, WhisperFeatureExtractor

        self.device = device
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

        # 🔴 bk_run 不设 PERFORMANCE_HINT / INFERENCE_PRECISION_HINT；
        #    NPU 档只给 decoder 加 NPUW 属性，encoder 保持空属性。
        #    （precision 参数保留以兼容 App 调用签名，但不下传 ⇒ 与验收实现一致）
        dec_props = dict(NPUW_PROPS) if device == 'NPU' else {}
        enc_props = {}
        self.npuw_props = dec_props
        self.precision_arg = precision

        # 🔴🔴🔳 **APP-118 §1（并入 ASR-065）**：**实际生效的 prompt 上界**。
        #   NPU 档用 NPUW 的 `MAX_PROMPT_LEN`（**320**）⇒ 前缀必须按 320 截；
        #   GPU 档不走 NPUW ⇒ 仍可用 IR 的硬上界 **512**。
        #   ⇒ 写成**实例属性**（不是模块常量）⇒ 不同档各用各的上界。
        self._max_prompt_tok = (int(dec_props.get(
            'NPUW_LLM_MAX_PROMPT_LEN', MAX_STATEFUL_TOK))
            if device == 'NPU' else MAX_STATEFUL_TOK)

        # 🔴🔴🔳 **APP-118 §1：`asr_enc_tiers` 开关（默认 OFF）**。
        #   ON ⇒ 运行时从 base IR 现场构建各档（{400,800,1600,2400} mel 帧）
        #        → 直接 compile → **不落盘**；
        #   OFF ⇒ 单档 2400（**行为与现状完全一致**）。
        #   🔴 **默认必须 off** ⇒ 不设置环境变量时**行为一字不变**。
        self.asr_enc_tiers = bool(_env_tiers_enabled())
        self.enc_tiers = {}

        enc_xml = self._find(encoder_dir, ('ov-encoder-06b-fp16-static.xml',
                                           'openvino_encoder_model.xml'))
        dec_xml = self._find(decoder_dir, ('openvino_model.xml',
                                           'openvino_decoder_model.xml'))
        self.enc = core.compile_model(enc_xml, device, enc_props)
        self.enc_infer = self.enc.create_infer_request()
        self.dec = core.compile_model(dec_xml, device, dec_props)
        self.dec_inputs = [i.get_any_name() for i in self.dec.inputs]

        # 🔴🔴🔳 **APP-118 §1（并入 ASR-065 §五）：encoder 分档（默认 OFF）**。
        #   ON ⇒ 运行时从 base IR 现场构建各档 → **直接 compile → 不落盘**。
        #   ⚠️ **构建放这里（构造期）**，不在推理路径上
        #   ⇒ 不占「计时窗口」⇒ 计时结论不被污染。
        #   🔴 **任一档构建失败（patched ≠ 60 等）⇒ 退回单档 2400**
        #   ⇒ 绝不「编了一半还继续用」。
        self.enc_tier_build_log = []
        if self.asr_enc_tiers:
            for _n in ASR_ENC_TIERS:
                if _n == ENC_MAX_FRAMES:
                    continue                     # 基准档就是已编好的 self.enc
                _info, _cm = _build_encoder_tier(enc_xml, _n, device)
                self.enc_tier_build_log.append(_info)
                if _info.get('ok') and _cm is not None:
                    self.enc_tiers[_n] = _cm
            print('[asr06b-stateful] encoder 分档已开启（ASR-065）：%s'
                  % (sorted(self.enc_tiers) or '（全部失败 ⇒ 用单档 2400）'),
                  flush=True)

        # 🔴 APP-101 §4.1：日志打印 EXECUTION_DEVICES 与 NPUW 配置。
        #    OV 的 EXECUTION_DEVICES 可能是字符串 'NPU'，也可能是 list
        #    ⇒ 字符串按单个设备名处理（逗号分隔），绝不逐字符拆。
        self.exec_devices = {}
        for _role, _model in (('encoder', self.enc), ('decoder', self.dec)):
            self.exec_devices[_role] = self._read_exec_devices(_model)
        _dev_txt = '，'.join(
            '%s=%s' % (_r, ('/'.join(_d) if _d else '?'))
            for _r, _d in self.exec_devices.items())
        print('[asr06b-stateful] EXECUTION_DEVICES：%s（请求设备 %s）'
              % (_dev_txt, device), flush=True)
        print('[asr06b-stateful] NPUW 配置=%s；decoder 输入端口=%s；'
              'KV=每次 generate 新建 InferRequest + reset_state'
              % (dec_props if dec_props else '（无，GPU 档/plain 编译）',
                 self.dec_inputs), flush=True)

        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir,
                                                      fix_mistral_regex=True)
        self.feature_extractor = WhisperFeatureExtractor.from_pretrained(
            tokenizer_dir)

        # 🔴 APP-103：fp16 文本 embedding 表（B-kit assets，不依赖 torch）
        self._W = np.asarray(np.load(embed_npy), dtype=np.float32)
        if self._W.shape != (VOCAB, HIDDEN):
            raise RuntimeError(
                f"embed table shape {self._W.shape} != {(VOCAB, HIDDEN)}；"
                f"应为 B-kit 导出的 0.6B fp16 表")

        self._ids_left, self._ids_right = self._build_prompt_ids()
        self._ids_right_en = self.tokenizer.encode(
            'language English<asr_text>', add_special_tokens=False)
        self._ids_right_zh = self.tokenizer.encode(
            'language Chinese<asr_text>', add_special_tokens=False)

        self.probe = {
            'enc_ms': [], 'decode_ms': [], 'prefill_ms': [],
            'n_decode': [], 'prompt_len': [], 'n_audio': [],
            'out_tokens': [], 'truncations': 0, 'kv_resets': 0,
            # 🔴🔴🔳 ASR-065 §四：前缀截断计数（**独立**于 512 上界的总截断）
            PROBE_PREFIX_TRUNCATIONS: 0,
        }

    # ── 小工具 ───────────────────────────────────────────────────────
    @staticmethod
    def _find(d: str, names: Tuple[str, ...]) -> str:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
        raise FileNotFoundError(f"none of {names} found in {d}")

    @staticmethod
    def _read_exec_devices(model) -> List[str]:
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
        # 🔴🔴🔳 **APP-118 §1（并入 ASR-065 §五）：encoder 分档（默认 OFF）**。
        #   OFF ⇒ 单档 2400（**行为与现状完全一致**）。
        #   ON  ⇒ 按 mel 长度选**最小能放下的档**（{400,800,1600,2400}），
        #         用该档的模型推理（**零填充到该档长度**）。
        #   🔴 **选不中 ⇒ 用单档 2400**（绝不静默截断）。
        _tier = ENC_MAX_FRAMES
        _cm = self.enc
        _infer = self.enc_infer
        if self.asr_enc_tiers and self.enc_tiers:
            _picked = pick_encoder_tier(mel_len)
            if _picked is not None and _picked != ENC_MAX_FRAMES:
                _cm = self.enc_tiers.get(_picked) or self.enc
                _tier = _picked
                _infer = _cm.create_infer_request()
            elif _picked is None:
                print('[asr06b-stateful] ⚠️ mel %d 帧放不进任何档 ⇒ 用单档 %d'
                      % (mel_len, ENC_MAX_FRAMES), flush=True)
        enc_in = np.zeros((1, 128, _tier), dtype=np.float32)
        enc_in[0, :, :mel_len] = mel
        n_valid = np.array([N_audio], dtype=np.int32)
        assert int(N_audio) == total_aftercnn_len(mel_len), (
            f"N_audio mismatch: {N_audio} vs {total_aftercnn_len(mel_len)}")
        out = _infer.infer([enc_in, n_valid])
        h = np.asarray(out[0])[0, :N_audio, :]
        self.probe.setdefault('tier_used', []).append(_tier)
        return h.astype(np.float32), n_real, N_audio

    # ── embeds 拼装（官方 masked_scatter 语义）──────────────────────
    def build_inputs_embeds(self, audio_emb: np.ndarray,
                            prefix_ids: List[int],
                            force_language: Optional[str] = None,
                            reserve: int = 1) -> np.ndarray:
        """left_ids + [audio] + right_ids(+语种) + prefix_ids。

        🔴 APP-103：上界 512。给生成 token 预留 ``reserve`` 位，
        超限时**从最旧的前缀 token 开始截**（不丢 prompt 骨架、不改 IR），
        截断次数记进 probe 与日志。

        🔴🔴🔳 **APP-118 §1（并入 ASR-065）**：NPUW 侧的
        `NPUW_LLM_MAX_PROMPT_LEN` 已从 512 降到 **320**
        ⇒ **GPU 档**（不用 NPUW）仍可用 512，**NPU 档**必须用 **320**。
        ⇒ 本方法按**实际生效的上界**截断：
        `self._max_prompt_tok`（构造时按设备定：NPU ⇒ 320，GPU ⇒ 512）。
        ⇒ 截断**从左**（保留右端＝最近的内容；前缀右端才是最新内容）
        ⇒ **不抛错、不回退 512**（用户 11-20 定）。
        """
        prefix_ids = list(prefix_ids or [])
        limit = int(getattr(self, '_max_prompt_tok', MAX_STATEFUL_TOK))
        skeleton = (len(self._ids_left) + int(audio_emb.shape[0])
                    + len(self._right_ids(force_language)))
        allowed_prefix = limit - skeleton - max(1, int(reserve))
        if allowed_prefix < 0:
            raise ValueError(
                'prompt 骨架 %d + 预留 %d > stateful 上界 %d（音频过长）'
                % (skeleton, reserve, limit))
        if len(prefix_ids) > allowed_prefix:
            drop = len(prefix_ids) - allowed_prefix
            # 🔴 **从左截断**（保留右端＝最近的内容）—— 前缀的**右端才是最新内容**
            prefix_ids = prefix_ids[drop:]
            self.probe['truncations'] += 1
            # 🔴🔴🔳 ASR-065 §四：前缀截断**单独计数**（与 512 上界的通用截断分开）
            self.probe[PROBE_PREFIX_TRUNCATIONS] = (
                int(self.probe.get(PROBE_PREFIX_TRUNCATIONS, 0)) + 1)
            print('[asr06b-stateful] %d 上界：前缀截断 T %d→%d dropped=%d'
                  '（累计 prefix_truncations=%d，总截断=%d 次）'
                  % (limit, skeleton + len(prefix_ids) + drop,
                     skeleton + len(prefix_ids), drop,
                     self.probe[PROBE_PREFIX_TRUNCATIONS],
                     self.probe['truncations']), flush=True)
        parts = [np.ascontiguousarray(self._W[list(self._ids_left)], dtype=np.float32),
                 np.asarray(audio_emb, dtype=np.float32),
                 np.ascontiguousarray(self._W[self._right_ids(force_language)],
                                      dtype=np.float32)]
        if prefix_ids:
            parts.append(np.ascontiguousarray(self._W[prefix_ids],
                                              dtype=np.float32))
        emb = np.concatenate(parts, axis=0)
        if emb.shape[0] + max(1, int(reserve)) > MAX_STATEFUL_TOK:
            raise ValueError(
                f"sequence {emb.shape[0]} + reserve {reserve} > {MAX_STATEFUL_TOK}")
        return emb

    # ── stateful greedy（照 bk_run._decode_logits_stateful）──────────
    def _infer_step(self, req, embeds: np.ndarray, past: int):
        T = past + embeds.shape[0]
        feed = {
            'inputs_embeds': np.ascontiguousarray(
                embeds[None, ...], dtype=np.float32),
            'attention_mask': np.ones((1, T), dtype=np.int64),
            'position_ids': (np.array([[past]], dtype=np.int64)
                             if embeds.shape[0] == 1
                             else np.arange(past, T, dtype=np.int64)[None, :]),
            'beam_idx': np.zeros(1, dtype=np.int32),
        }
        out = req.infer(feed)
        arr = np.array(list(out.values())[0].data)
        return np.ascontiguousarray(arr[0, -1])

    def greedy_decode_with_prefix(self, audio_emb: np.ndarray,
                                  prefix_ids: List[int],
                                  max_new_tokens: int,
                                  force_language: Optional[str] = None) -> List[int]:
        import time
        budget = max(1, int(max_new_tokens))
        emb = self.build_inputs_embeds(audio_emb, prefix_ids, force_language,
                                       reserve=budget)
        L = int(emb.shape[0])
        self.probe['prompt_len'].append(L)
        self.probe['n_audio'].append(int(audio_emb.shape[0]))

        # 🔴 路线 A：调用内 KV —— 每次 generate 新建 InferRequest 并重置
        #    ⇒ 段落定稿后无需额外清理，下一次调用天然从空 KV 开始。
        req = self.dec.create_infer_request()
        req.reset_state()
        self.probe['kv_resets'] += 1
        t0 = time.perf_counter()
        try:
            logits = self._infer_step(req, emb, 0)
            self.probe['prefill_ms'].append((time.perf_counter() - t0) * 1000)
            tid = int(np.argmax(logits))
            if tid in EOS_IDS:
                self.probe['decode_ms'].append((time.perf_counter() - t0) * 1000)
                self.probe['n_decode'].append(0)
                self.probe['out_tokens'].append(0)
                return []
            generated = [tid]
            for _ in range(budget - 1):
                past = L + len(generated) - 1
                if past + 1 >= MAX_STATEFUL_TOK:
                    break
                nxt = self._W[tid].astype(np.float32)[None, :]
                t1 = time.perf_counter()
                logits = self._infer_step(req, nxt, past)
                self.probe['decode_ms'].append((time.perf_counter() - t1) * 1000)
                tid = int(np.argmax(logits))
                if tid in EOS_IDS:
                    break
                generated.append(tid)
        finally:
            del req
        self.probe['n_decode'].append(len(generated))
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

    def finish_streaming_transcribe(self, state: ASRStreamingState,
                                    audio_accum: np.ndarray,
                                    prefix_text: str,
                                    max_new_tokens: int) -> str:
        """段尾刷新；同样走「新建 InferRequest + reset_state」⇒ KV 已重置。"""
        return self.generate_with_prefix(state, audio_accum, prefix_text,
                                         max_new_tokens)


#: dev 树后端工厂按这个属性取类（与旧基线模块的接口一致）
BACKEND_CLASS = ASR06BStatefulBackend
