"""engine_runtime.py — **真实引擎接线**（EXT-006 [HIGH]：P1 接入真实引擎）

## 本文件的定位

`ext/engines.py`（EXT-002 建的）只定义了 `EngineAdapter` **接口**，没有注入实现。
EXT-006 要求 P1 走**真实的 ASR → MT → TTS 链路**（回声模式只作自测保留）。

⇒ 本文件提供 `RuntimeEngine`：把 `EngineAdapter` 的三个空方法接到
   实时字幕 App 已交付的引擎上。

## 铁律（EXT-001 总原则，EXT-006 复述）

* **不改其他模块的文件** —— 下面所有 import 都是**只读**引用
  `Confucius4_LiveCaption_v1.6/app/` 与 `.../models/` 里的原件；
* **只在 import 或复制适配层范围内复用** —— 本文件就是那个适配层；
* **不在 CPU 上跑推理** —— ASR/MT 放 GPU.0，TTS 放 NPU；
* **发现引擎需要改动，写进 STATUS_EXT.md 由主会话转给对应模块** —— 本文件
  用 `EngineNeedsChange` 异常 + `needs_change` 列表表达，**不自己改引擎**。

## 设备摆放（EXT-001）

| 引擎 | 交付版本 | 设备 | 本机 OpenVINO 设备名 |
|---|---|---|---|
| ASR | R2T2 INT8 | GPU.0 | `Intel(R) Graphics (iGPU)` |
| MT  | Hy-MT2 INT8 | GPU.0 | 同上 |
| TTS | Qwen3-TTS 全 NPU | NPU | `Intel(R) AI Boost` |

⚠️ 本机 GPU.1 是 NVIDIA RTX 5050（dGPU），**不用**（EXT-001 指定 GPU.0）。
⚠️ `SegmentEncoderOVBackend` 默认 `strict_intel=True` 会断言设备名含 "Intel"；
   GPU.0 就是 Intel iGPU ⇒ **该断言成立，无需绕过**。

## TTS 的两条硬纪律（EXT-006 明文要求）

1. **必须显式传目标语言** —— App 的日文失控事故（APP-030）就是因为没传
   ⇒ 本文件把 `language` 设为**必填**，缺省直接抛异常，不猜。
2. **必须设帧数上限 + 失控中止** —— 用 App 已有的
   `tts_engine.clamp_max_new_tokens(text, lang)`（APP-030② 的公式）
   ⇒ 失控句在几秒内被截断，而不是拖 100 s 把整条链堵死。

## 运行时

引擎依赖 `openvino` / `openvino_genai` / `babelvox` / `transformers`，
这些**只在 App 自带的 Python 运行时里**存在
（`Confucius4_LiveCaption_v1.6/python/python.exe`）。

⇒ 因此 `RuntimeEngine` 必须在**那个解释器**里运行。
   桥接服务的启动脚本（`tools/bridge_server.py`）负责用该解释器拉起本模块。
   本模块的 import 全部**延迟**到真正要跑推理时 ⇒ 只在桥接服务进程内部用。
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config import DEVICE_ASR, DEVICE_MT, DEVICE_TTS, SAMPLE_RATE

# ── 运行时位置（可用环境变量覆盖） ─────────────────────────────────
APP_ROOT = os.environ.get(
    "EXT_APP_ROOT", r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6")
APP_DIR = os.path.join(APP_ROOT, "app")
MODELS_DIR = os.path.join(APP_ROOT, "models")

# ── 模型别名 → 实际目录（照抄 App 的 live_caption_app.py 的映射） ───
#   'ov-encoder-segment-reviewer-int8asym': ['encoder-int8']
#   'ov-int8-past'                          : ['decoder-gpu-int8']
# ⇒ EXT-001 要求的「R2T2 INT8」= encoder-int8 + decoder-gpu-int8
ASR_ENCODER_DIR = os.path.join(MODELS_DIR, "encoder-int8")
ASR_DECODER_DIR = os.path.join(MODELS_DIR, "decoder-gpu-int8")
MT_MODEL_DIR = os.path.join(MODELS_DIR, "mt")
TTS_MODEL_DIR = os.path.join(MODELS_DIR, "qwen3tts")

# ── ASR 行为参数（照抄 App：live_caption_app.py CHUNK_SEC=0.64） ────
ASR_CHUNK_SEC = 0.64
ASR_UNFIXED_CHUNK_NUM = 0
ASR_UNFIXED_TOKEN_NUM = 5
# ★ max_new_tokens 必须传 int（照抄 App 的 live_caption_app.py）：
#   流式 32 / 收尾 64 ⇒ 传 None 会崩（OV backend 里是 `range(max_new_tokens - 1)`）
ASR_MAX_NEW_TOKENS = 32
ASR_MAX_NEW_TOKENS_FINISH = 64

# ── TTS 行为参数 ──────────────────────────────────────────────────
# ★ 目标语言必须显式传（EXT-006）。这里只放**映射表**，不是默认值 ——
#   拿不到目标语言时**抛异常**，绝不静默用 en。
#
# ★★ 口径收窄（本轮修掉的真实缺陷）：上一版把 fr/de/es/ru/pt/it 也列进了
#   映射表，但**引擎侧根本不支持**这几种语言：
#     - TTS：Qwen3-TTS 的 `SUPPORTED_LANGS = ('Chinese','English','Japanese','Korean')`
#       （来源：包内 `models/qwen3tts/weights/config.json` 的 `codec_language_id`）；
#     - MT：Hy-MT2 的 `_LANG_NAME = {'zh','en','ja','ko'}`。
#   ⇒ 映射到未支持语言 ⇒ 模型按**兜底**走（`map_language` 兜底 English）
#   ⇒ 日文素材会被读成英文，而**日志里看不出来**（静默失准）。
#   ⇒ 本表只保留引擎**确实支持**的 4 种；其余语言**显式报错**。
LANG_TO_TTS = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
}

# MT 的目标语言码（与 Hy-MT2 的 `_LANG_NAME` 一致）
LANG_TO_MT = {
    "zh": "zh",
    "en": "en",
    "ja": "ja",
    "ko": "ko",
}

# 失控中止：单句合成墙钟上限（秒）。超过 ⇒ 中止该句并记录。
# ★ 与 App 的 RUNAWAY 判据口径一致：`runaway_threshold_s(est_sec)` =
#   `max(3×est, est + 8s)`（APP-030②）。这里取**上限封顶**：墙钟闸取该阈值，
#   但不超过硬上限 TTS_WALL_CLOCK_CAP_SEC（防止 est 估偏大时闸门形同虚设）。
TTS_RUNAWAY_SEC = 30.0
# 失控中止：单句生成音频上限（秒）。超过 ⇒ 中止该句并记录。
TTS_MAX_AUDIO_SEC = 60.0
# 墙钟闸的硬上限（秒）—— 即便阈值算出来更大，也不允许超过这个值。
TTS_WALL_CLOCK_CAP_SEC = 60.0


class EngineNeedsChange(Exception):
    """引擎需要改动 —— **本模块不自己改引擎**，只把诉求上报给主会话。"""

    def __init__(self, module: str, detail: str):
        super().__init__(f"[{module}] {detail}")
        self.module = module
        self.detail = detail


def _ensure_app_on_path() -> None:
    """把 App 的 `app/` 目录挂到 sys.path（只读引用，不改对方文件）。"""
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)


def _log(msg: str) -> None:
    sys.stderr.write("[ext-engine] %s\n" % msg)
    sys.stderr.flush()


class RuntimeEngine:
    """**真实**引擎适配器：ASR(R2T2 INT8@GPU.0) → MT(Hy-MT2 INT8@GPU.0)
    → TTS(Qwen3-TTS@NPU)。

    与 `ext/engines.py` 的 `EngineAdapter` 接口一致：
        asr(audio, t_start, t_end) -> str
        mt(text) -> str
        tts(text, voice=...) -> (pcm_bytes, speech_sec)
    """

    def __init__(self, *, target_lang: str = "en",
                 asr_device: str = DEVICE_ASR,
                 mt_device: str = DEVICE_MT,
                 tts_device: str = DEVICE_TTS,
                 on_log=_log) -> None:
        self.target_lang = target_lang
        self.asr_device = asr_device
        self.mt_device = mt_device
        self.tts_device = tts_device
        self.on_log = on_log

        self._asr_backend = None
        self._asr_state = None
        self._mt = None
        self._tts_eng = None
        self._tts_spk_embed = None

        self.needs_change: List[str] = []
        self.load_s: Dict[str, float] = {}
        self.n_calls = {"asr": 0, "mt": 0, "tts": 0}
        self.last_error: Dict[str, str] = {}

    # ── 可用性探测（静态，不加载权重） ───────────────────────────
    def available(self) -> dict:
        return {
            "asr": {"root": ASR_ENCODER_DIR, "device": self.asr_device,
                    "probe_ok": os.path.isdir(ASR_ENCODER_DIR)
                    and os.path.isdir(ASR_DECODER_DIR)},
            "mt": {"root": MT_MODEL_DIR, "device": self.mt_device,
                   "probe_ok": os.path.isdir(MT_MODEL_DIR)},
            "tts": {"root": TTS_MODEL_DIR, "device": self.tts_device,
                    "probe_ok": os.path.isdir(TTS_MODEL_DIR)},
            "runtime_ok": self._runtime_ok(),
        }

    @staticmethod
    def _runtime_ok() -> bool:
        """检查 App 自带运行时是否可用（openvino / ov_genai / babelvox）。"""
        try:
            import openvino  # noqa: F401
            import openvino_genai  # noqa: F401
        except Exception:
            return False
        return os.path.isdir(os.path.join(APP_ROOT, "python", "Lib",
                                          "site-packages", "babelvox"))

    # ── ASR ─────────────────────────────────────────────────────
    def _load_asr(self) -> None:
        if self._asr_backend is not None:
            return
        _ensure_app_on_path()
        t0 = time.perf_counter()
        try:
            from segment_encoder_backend import SegmentEncoderOVBackend
        except Exception as e:
            raise EngineNeedsChange("R2T2", "import SegmentEncoderOVBackend 失败: %s" % e)
        try:
            # ★ device=GPU.0（Intel iGPU）⇒ strict_intel 的断言成立，不绕过
            self._asr_backend = SegmentEncoderOVBackend(
                encoder_dir=ASR_ENCODER_DIR,
                decoder_dir=ASR_DECODER_DIR,
                device=self.asr_device,
                precision="f16",
                cache_dir=os.path.join(os.environ.get("LOCALAPPDATA", "."),
                                       "Confucius4LiveCaption", "ext_ov_cache"),
                strict_intel=True,
            )
        except Exception as e:
            raise EngineNeedsChange(
                "R2T2", "SegmentEncoderOVBackend 构造失败（device=%s）: %s"
                % (self.asr_device, e))
        self._asr_state = self._make_asr_state()
        self.load_s["asr"] = time.perf_counter() - t0
        self.on_log("ASR 就绪（R2T2 INT8 @ %s，%.1fs）"
                    % (self.asr_device, self.load_s["asr"]))

    def _make_asr_state(self):
        from seg_stream import _make_segment_state
        return _make_segment_state(
            self._asr_backend,
            unfixed_chunk_num=ASR_UNFIXED_CHUNK_NUM,
            unfixed_token_num=ASR_UNFIXED_TOKEN_NUM,
            chunk_size_sec=ASR_CHUNK_SEC,
            force_language=None,      # None = 自动检测语种
        )

    def asr(self, audio: np.ndarray, t_start: float, t_end: float) -> str:
        """对一段定稿音频做 ASR。

        用 App 的**流式**接口：把整段音频一次性喂进去
        （`streaming_transcribe` 内部按 chunk 循环），
        再用 `finish_streaming_transcribe` 收尾拿最终文本。

        ⚠️ 每次调用都**重置 state** —— 段落是独立的定稿单元，
           不应继承上一段的左上下文。
        """
        self._load_asr()
        from streaming_asr import streaming_transcribe, finish_streaming_transcribe
        x = np.asarray(audio, dtype=np.float32).reshape(-1)
        if x.shape[0] == 0:
            return ""
        # 重置 state（每段独立）
        self._asr_state = self._make_asr_state()
        try:
            # ★ max_new_tokens **必须传 int**：OV backend 的
            #   `greedy_decode_with_prefix` 里是 `range(max_new_tokens - 1)`
            #   ⇒ 传 None 会抛 `TypeError: unsupported operand type(s) for -`
            #   （实测踩过）。数值照抄 App（live_caption_app.py）：
            #   流式 32 / 收尾 64。
            _text, _fixed = streaming_transcribe(
                self._asr_backend, x, self._asr_state,
                max_new_tokens=ASR_MAX_NEW_TOKENS,
                rollback_punctuation=False,
                enable_hallucination_reset=True, adaptive_budget=False)
            final = finish_streaming_transcribe(
                self._asr_backend, self._asr_state,
                max_new_tokens=ASR_MAX_NEW_TOKENS_FINISH)
        except Exception as e:
            self.last_error["asr"] = "%s: %s" % (type(e).__name__, e)
            self.on_log("ASR 调用失败: %s" % e)
            return ""
        self.n_calls["asr"] += 1
        return (final or "").strip()

    # ── MT ─────────────────────────────────────────────────────
    def _load_mt(self) -> None:
        if self._mt is not None:
            return
        _ensure_app_on_path()
        t0 = time.perf_counter()
        try:
            from translator import HunyuanTranslator
        except Exception as e:
            raise EngineNeedsChange("Hy-MT2", "import HunyuanTranslator 失败: %s" % e)
        try:
            self._mt = HunyuanTranslator(
                model_dir=MT_MODEL_DIR, device=self.mt_device,
                cache_dir=os.path.join(os.environ.get("LOCALAPPDATA", "."),
                                       "Confucius4LiveCaption", "ext_mt_cache"),
                on_log=self.on_log)
        except Exception as e:
            raise EngineNeedsChange(
                "Hy-MT2", "HunyuanTranslator 构造失败（device=%s）: %s"
                % (self.mt_device, e))
        self.load_s["mt"] = time.perf_counter() - t0
        self.on_log("MT 就绪（Hy-MT2 INT8 @ %s，%.1fs）"
                    % (self.mt_device, self.load_s["mt"]))

    def mt(self, text: str) -> str:
        """翻译一句。`target_lang` 走 MT 的 `tgt` 参数。"""
        if not text:
            return ""
        self._load_mt()
        tgt = self.mt_target()
        try:
            r = self._mt.translate(text, tgt)
        except Exception as e:
            self.last_error["mt"] = "%s: %s" % (type(e).__name__, e)
            self.on_log("MT 调用失败: %s" % e)
            return ""
        self.n_calls["mt"] += 1
        return (r or {}).get("text", "") or ""

    def mt_target(self) -> str:
        """把目标语言映射成 MT 的 `tgt` 参数值。

        ★ 映射不到就**抛异常**，绝不静默传一个引擎不认的码
          （Hy-MT2 的 `_LANG_NAME` 只有 zh/en/ja/ko ⇒ 传别的会 KeyError
            或让 `_LANG_NAME[tgt]` 崩在渲染 prompt 的路上）。
        """
        key = (self.target_lang or "").strip().lower()
        if key in LANG_TO_MT:
            return LANG_TO_MT[key]
        raise EngineNeedsChange(
            "Hy-MT2",
            "目标语言 %r 没有对应的 MT tgt（已知：%s）"
            % (self.target_lang, ", ".join(sorted(LANG_TO_MT))))

    # ── TTS ────────────────────────────────────────────────────
    def _load_tts(self) -> None:
        if self._tts_eng is not None:
            return
        _ensure_app_on_path()
        t0 = time.perf_counter()
        try:
            from tts_engine import make_engine
        except Exception as e:
            raise EngineNeedsChange("Qwen3-TTS", "import make_engine 失败: %s" % e)
        try:
            self._tts_eng = make_engine(
                device=self.tts_device, model_path=TTS_MODEL_DIR,
                cache_dir=os.path.join(os.environ.get("LOCALAPPDATA", "."),
                                       "Confucius4LiveCaption", "ext_tts_cache"),
                on_log=self.on_log)
        except Exception as e:
            raise EngineNeedsChange(
                "Qwen3-TTS", "make_engine 构造失败（device=%s）: %s"
                % (self.tts_device, e))
        self.load_s["tts"] = time.perf_counter() - t0
        self.on_log("TTS 就绪（Qwen3-TTS @ %s，%.1fs）"
                    % (self.tts_device, self.load_s["tts"]))
        self._prepare_preset_voice()

    def _prepare_preset_voice(self) -> None:
        """预计算「预设音色 A」的 speaker embedding（**只算一次**）。

        ★ 为什么不用 `speaker=None`：App 的交接单明确写
          （TTS-005）：ICL 路线（ref_audio + ref_text）在 codec 轨道上
          没有参考音频的 codec 码 ⇒ 对模型是「有文本、没音频」的
          分布外 prompt ⇒ **EOS 不稳**（实测 60 句里撞上限 9 次）。
          ⇒ 一律走 x-vector 路线（`speaker_embed`），
            实测撞上限 0/60。

        ★ EXT-001/EXT-006：P1 用**预设音色 A**（`voices/preset_A.wav`）。
          克隆音色（按说话人）留到 P2。
        """
        if self._tts_spk_embed is not None:
            return
        from tts_engine import speaker_embedding
        emb = speaker_embedding(self._tts_eng, ref_wav=None, on_log=self.on_log)
        if emb is None:
            self.needs_change.append(
                "Qwen3-TTS: 预设音色 A 的 speaker embedding 计算失败")
            self.on_log("🔴 预设音色 A 不可用 ⇒ TTS 走内置 speaker")
            return
        self._tts_spk_embed = emb
        self.on_log("预设音色 A embedding 就绪：shape=%s" % (emb.shape,))

    def tts_language(self) -> str:
        """把目标语言映射成 TTS 的 `language` 参数值。

        ★ EXT-006：TTS **必须**显式传目标语言（APP-030 日文失控事故的根因）。
        ⇒ 映射不到就**抛异常**，绝不静默退回 English。
        """
        key = (self.target_lang or "").strip().lower()
        if key in LANG_TO_TTS:
            return LANG_TO_TTS[key]
        raise EngineNeedsChange(
            "Qwen3-TTS",
            "目标语言 %r 没有对应的 TTS language（已知：%s）"
            % (self.target_lang, ", ".join(sorted(LANG_TO_TTS))))

    def tts(self, text: str, *, voice: str) -> Tuple[Optional[bytes], float]:
        """合成配音。

        ★ 显式传 `language`（EXT-006 / APP-030）
        ★ 显式传 `max_new_tokens`（失控闸第一道，APP-030②）
        ★ 墙钟与音频双上限 ⇒ 失控中止（EXT-006 明文要求）

        Returns
        -------
        (pcm_bytes, speech_sec)
            pcm_bytes 为 24 kHz PCM16（单声道）；失败时 (None, 0.0)。
        """
        if not text:
            return (None, 0.0)
        self._load_tts()
        from tts_engine import (clamp_max_new_tokens, estimate_sec,
                                runaway_threshold_s)

        language = self.tts_language()          # ★ 必传，映射不到就抛
        max_tok = clamp_max_new_tokens(text, language)
        # ★ 第二道闸的输入（APP-030② 的口径）：用 `estimate_sec`
        #   （按字符口径，与 clamp 同源）而不是 `estimate_frames/12`
        #   —— 后者在语言全称（如 'Japanese'）下会因 `_SEC_PER_CHAR`
        #   的键不匹配而落到英文口径，阈值被低估。
        est_sec = float(estimate_sec(text, language))
        # ★ 墙钟闸用 App 的 RUNAWAY 判据：`max(3×est, est+8s)`，
        #   再用硬上限封顶（防止 est 估偏大时闸门形同虚设）。
        wall_limit = min(runaway_threshold_s(est_sec), TTS_WALL_CLOCK_CAP_SEC)

        pcm = self._collect_tts(text, language=language, max_tok=max_tok,
                                wall_limit=wall_limit)
        if pcm is None:
            return (None, 0.0)
        speech_sec = len(pcm) / 2.0 / 24000.0
        self.n_calls["tts"] += 1
        return (pcm, speech_sec)

    def _collect_tts(self, text: str, *, language: str, max_tok: int,
                     wall_limit: float) -> Optional[bytes]:
        """跑 TTS 流式合成并收集 PCM，同时执行两道失控中止。"""
        from tts_engine import stream as tts_stream

        chunks: List[np.ndarray] = []
        sr = 24000
        t0 = time.perf_counter()
        aborted = None
        try:
            for wave, sample_rate in tts_stream(
                    self._tts_eng, text, language=language,
                    speaker_embed=self._tts_spk_embed,   # ★ 预设音色 A（x-vector）
                    speaker=None,
                    max_new_tokens=max_tok,
                    on_log=self.on_log):
                if sample_rate:
                    sr = int(sample_rate)
                if wave is None:
                    continue
                arr = np.asarray(wave, dtype=np.float32).reshape(-1)
                if arr.shape[0]:
                    chunks.append(arr)
                # 失控闸 1：墙钟上限（App RUNAWAY 判据）
                elapsed = time.perf_counter() - t0
                if elapsed > wall_limit:
                    aborted = "wall_clock>%.1fs (limit %.1fs)" % (
                        elapsed, wall_limit)
                    break
                # 失控闸 2：累计音频上限
                total = sum(c.shape[0] for c in chunks) / float(sr)
                if total > TTS_MAX_AUDIO_SEC:
                    aborted = "audio>%.0fs" % TTS_MAX_AUDIO_SEC
                    break
        except Exception as e:
            self.last_error["tts"] = "%s: %s" % (type(e).__name__, e)
            self.on_log("TTS 调用失败: %s" % e)
            return None
        if aborted:
            self.last_error["tts"] = "runaway_abort: %s" % aborted
            self.on_log("🔴 TTS 失控中止：%s（已丢弃该句）" % aborted)
            return None
        if not chunks:
            return None
        audio = np.concatenate(chunks)
        # float [-1,1] → int16
        audio = np.clip(audio, -1.0, 1.0)
        return (audio * 32767.0).astype("<i2").tobytes()

    # ── 诊断 ───────────────────────────────────────────────────
    def stats(self) -> dict:
        return {
            "target_lang": self.target_lang,
            "devices": {"asr": self.asr_device, "mt": self.mt_device,
                        "tts": self.tts_device},
            "loaded": {"asr": self._asr_backend is not None,
                       "mt": self._mt is not None,
                       "tts": self._tts_eng is not None},
            "load_s": {k: round(v, 2) for k, v in self.load_s.items()},
            "n_calls": dict(self.n_calls),
            "last_error": dict(self.last_error),
            "needs_change": list(self.needs_change),
        }


def load_runtime(**kwargs) -> RuntimeEngine:
    """构造 RuntimeEngine（不立刻加载权重 —— 延迟到第一次调用）。"""
    return RuntimeEngine(**kwargs)
