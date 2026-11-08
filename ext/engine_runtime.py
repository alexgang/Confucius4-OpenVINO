"""engine_runtime.py — **真实引擎接线**（EXT-006 [HIGH]：P1 接入真实引擎）

## 本文件的定位

`ext/engines.py`（EXT-002 建的）只定义了 `EngineAdapter` **接口**，没有注入实现。
EXT-006 要求 P1 走**真实的 ASR → MT → TTS 链路**（回声模式只作自测保留）。

⇒ 本文件提供 `RuntimeEngine`：把 `EngineAdapter` 的三个空方法接到
   实时字幕 App 已交付的引擎上。

## 铁律（EXT-001 总原则，EXT-006 复述）

* **不改其他模块的文件** —— 下面所有 import 都是**只读**引用
  `Confucius4_LiveCaption_v*/app/` 与 `.../models/` 里的原件（版本自适应）；
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
（`Confucius4_LiveCaption_v*/python/python.exe`；目录由 `ext/app_root.py` 解析）。

⇒ 因此 `RuntimeEngine` 必须在**那个解释器**里运行。
   桥接服务的启动脚本（`tools/bridge_server.py`）负责用该解释器拉起本模块。
   本模块的 import 全部**延迟**到真正要跑推理时 ⇒ 只在桥接服务进程内部用。
"""
from __future__ import annotations

import os
import sys
import time
import traceback
import json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config import DEVICE_ASR, DEVICE_MT, DEVICE_TTS, SAMPLE_RATE
# ★ EXT-017①：日志写出必须不因编码问题抛异常（GBK 控制台 + 🔴/⇒ ⇒ 崩）。
from .utf8_io import safe_print as _safe_print

# ── 运行时位置（★ 缺陷 22：**不再硬编码版本号**） ──────────────────
#   原实现把路径硬编码成 `..._v1.6`；实测 2026-10-29 App 升级到 v1.7、
#   v1.6 目录**已被删除** ⇒ 引擎接线全线失效（自测实测 1 FAIL）。
#   ⇒ 改用 `ext/app_root.py` **按目录实际存在情况**解析（版本自适应）。
#   环境变量 `EXT_APP_ROOT` 仍然最高优先（便于离线复现/CI）。
from .app_root import resolve_app_root as _resolve_app_root

_APP_ROOT_RESOLVED = _resolve_app_root()
if not _APP_ROOT_RESOLVED:
    raise RuntimeError(
        "找不到实时字幕 App 的安装目录（需要 app/ + models/ + python/python.exe）。"
        "可用环境变量 EXT_APP_ROOT 显式指定。")
APP_ROOT = _APP_ROOT_RESOLVED
APP_DIR = os.path.join(APP_ROOT, "app")
MODELS_DIR = os.path.join(APP_ROOT, "models")

# ── 模型别名 → 实际目录（照抄 App 的 live_caption_app.py 的映射） ───
#   'ov-encoder-segment-reviewer-int8asym': ['encoder-int8']
#   'ov-int8-past'                          : ['decoder-gpu-int8']
# ⇒ EXT-001 要求的「R2T2 INT8」= encoder-int8 + decoder-gpu-int8
ASR_ENCODER_DIR = os.path.join(MODELS_DIR, "encoder-int8")
ASR_DECODER_DIR = os.path.join(MODELS_DIR, "decoder-gpu-int8")
TTS_MODEL_DIR = os.path.join(MODELS_DIR, "qwen3tts")


def _first_existing(*paths: str) -> Optional[str]:
    """返回第一个**存在**的路径；全不存在则返回 None（照抄 App 的同名工具）。"""
    for p in paths:
        if p and os.path.isdir(p):
            return p
    return None


def _resolve_mt_model_dir() -> Optional[str]:
    r"""定位 Hy-MT2 的模型目录（**照抄 App 的 `translator.DEFAULT_MODEL` 顺序**）。

    ★ 本轮修掉的真实缺陷：原来直接用 `models/mt`（**父目录**），
      而 openvino_genai 要求目录里**直接**放 `openvino_model.xml` 等 IR 文件
      ⇒ 实测报 `Could not find a model in the directory '...\models\mt'`。
      真正的模型在**子目录**里：
        `models/mt/mt2-int8sym-cw-q`（INT8 per-channel，GPU/NPU 通吃）
        `models/mt/mt2-int4sym-cw-q`（INT4 回退）
      ⇒ 与 App 的 `DEFAULT_MODEL` 保持同一套查找顺序（含开发机 hy_bench 回退）。
    """
    return _first_existing(
        os.environ.get("LIVECAP_MT_MODEL", ""),
        os.path.join(MODELS_DIR, "mt", "mt2-int8sym-cw-q"),
        os.path.join(MODELS_DIR, "mt2-int8sym-cw-q"),
        os.path.join(MODELS_DIR, "mt", "mt2-int4sym-cw-q"),
        os.path.join(MODELS_DIR, "mt2-int4sym-cw-q"),
    )


# MT 模型目录在**运行时**解析（不是常量）—— 因为要用 App 的 fallback 顺序，
# 且 `LIVECAP_MT_MODEL` 环境变量可能在 import 之后才被设置。
# ★ 但 `available()` 之类的**探测**接口要一个立即可用的值 ⇒ 保留一份
#   import 时的快照；真正加载模型时用 `_resolve_mt_model_dir()` 重新解析。
MT_MODEL_DIR = _resolve_mt_model_dir()

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
    """引擎层日志（写 stderr）。

    ★ EXT-017①：同样**绝不因编码问题抛异常** ——
      中文 Windows 控制台是 GBK，`🔴` 在 GBK 下无法编码 ⇒
      直接 `sys.stderr.write` 会抛 `UnicodeEncodeError` ⇒ 引擎加载中断。
      ⇒ 走 `safe_print`（降级替换，不抛异常）。
    """
    _safe_print("[ext-engine] %s" % msg, stream=sys.stderr)


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

        # ★★ T-4：最后一次**真正用于翻译/合成**的目标语言。
        #   （构造时的 `target_lang` 是服务端启动参数；
        #     客户端按句覆盖后，这里记的是**实际生效**的那个。）
        self.applied_target_lang: Optional[str] = None

        self.needs_change: List[str] = []
        self.load_s: Dict[str, float] = {}
        self.n_calls = {"asr": 0, "mt": 0, "tts": 0}
        self.last_error: Dict[str, str] = {}
        # ★★★ EXT-023：TTS 各组件**实际执行设备**（EXECUTION_DEVICES）。
        #   加载完 TTS 后由 `_report_tts_exec_devices()` 填。
        #   ⚠️ 初始 None（**没加载就是没测过**）⇒ 绝不臆造。
        self.tts_exec_devices: Optional[dict] = None

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

    # ── ★ EXT-017②：预热（启动即加载，把「加载模型」变成**可见**的过程） ──
    def warmup(self, *, stages: Tuple[str, ...] = ("asr", "mt", "tts"),
               on_progress=None) -> dict:
        """**主动**加载三个引擎，并把每一步的进度回报出去。

        ## 为什么要这个方法（EXT-017② 的根因）

        原先三个引擎都是**懒加载**（第一次真正用到某引擎时才 load）：

        * `_load_asr` 只在 `asr()` 里被调；
        * `_load_mt` 只在 `mt()` 里被调；
        * `_load_tts` 只在 `tts()` 里被调。

        ⇒ 桥接服务 `start` 之后**屏幕上什么都没有**，
          用户要等到第一句音频真的流进来才看到「ASR 就绪」。
          这正是用户报的「start 之后没有任何输出」。

        ⇒ 本方法让**启动阶段**就把三个引擎加载好，并逐条回报进度：

            [engine] (1/3) 正在加载 ASR（R2T2 INT8 @ GPU.0）……
            [engine] ASR 就绪（R2T2 INT8 @ GPU.0，12.3s）
            ...

        ## 返回值

        ``{"ok": bool, "loaded": [...], "failed": {stage: reason},
          "load_s": {...}, "elapsed_sec": float}``

        ★ **失败不抛异常**：任何一个阶段加载失败，都**记下来并继续**
          （引擎是独立的：MT 挂了不该让 ASR 也起不来）。
          ⇒ 调用方（`ext.bridge.main`）据此决定要不要拒绝启动。
        """
        report = {
            "ok": True,
            "loaded": [],
            "failed": {},
            "load_s": {},
            "elapsed_sec": 0.0,
        }
        t_all = time.perf_counter()

        def emit(msg: str) -> None:
            try:
                if on_progress is not None:
                    on_progress(msg)
                else:
                    self.on_log(msg)
            except Exception:
                # ★ 进度回报失败**绝不影响**加载本身。
                pass

        total = len(stages)
        for i, stage in enumerate(stages, 1):
            label = {"asr": "ASR（R2T2 INT8）", "mt": "MT（Hy-MT2 INT8）",
                     "tts": "TTS（Qwen3-TTS）"}.get(stage, stage)
            device = {"asr": self.asr_device, "mt": self.mt_device,
                      "tts": self.tts_device}.get(stage, "?")
            emit("(%d/%d) 正在加载 %s @ %s ……" % (i, total, label, device))
            t0 = time.perf_counter()
            try:
                if stage == "asr":
                    self._load_asr()
                elif stage == "mt":
                    self._load_mt()
                elif stage == "tts":
                    self._load_tts()
                else:
                    raise EngineNeedsChange(stage, "未知阶段：%s" % stage)
            except Exception as e:
                reason = "%s: %s" % (type(e).__name__, e)
                report["failed"][stage] = reason
                report["ok"] = False
                emit("(%d/%d) %s 加载失败 ⇒ %s" % (i, total, label, reason))
                continue
            dt = time.perf_counter() - t0
            report["loaded"].append(stage)
            report["load_s"][stage] = round(dt, 2)
            emit("(%d/%d) %s 加载完成（%.1f 秒）" % (i, total, label, dt))

        report["elapsed_sec"] = round(time.perf_counter() - t_all, 2)
        emit("引擎预热完成：成功 %d/%d，总耗时 %.1f 秒"
             % (len(report["loaded"]), total, report["elapsed_sec"]))
        return report

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
        # 11-08 reviewer: MT AUTO => NPU when TTS will use the CUDA sidecar (frees GPU.0 for ASR)
        if str(self.mt_device or "").upper() == "AUTO":
            _cuda = False
            if str(self.tts_device or "").upper() in ("AUTO", "CUDA"):
                try:
                    import tts_cuda
                    _cuda = bool(tts_cuda.available())
                except Exception:
                    _cuda = False
            self.mt_device = "NPU" if _cuda else "GPU.0"
            self.on_log("MT 设备 AUTO => %s（TTS %s CUDA 边车）"
                        % (self.mt_device, "走" if _cuda else "不走"))
        # ★ 运行时重新解析（支持 import 之后才设的环境变量）
        model_dir = _resolve_mt_model_dir()
        if not model_dir:
            raise EngineNeedsChange(
                "Hy-MT2",
                "找不到 MT 模型目录（已查：LIVECAP_MT_MODEL / models/mt/mt2-int8sym-cw-q "
                "/ models/mt2-int8sym-cw-q / models/mt/mt2-int4sym-cw-q）")
        try:
            self._mt = HunyuanTranslator(
                model_dir=model_dir, device=self.mt_device,
                cache_dir=os.path.join(os.environ.get("LOCALAPPDATA", "."),
                                       "Confucius4LiveCaption", "ext_mt_cache"),
                on_log=self.on_log)
        except Exception as e:
            raise EngineNeedsChange(
                "Hy-MT2", "HunyuanTranslator 构造失败（device=%s, dir=%s）: %s"
                % (self.mt_device, model_dir, e))
        self.load_s["mt"] = time.perf_counter() - t0
        self.on_log("MT 就绪（Hy-MT2 INT8 @ %s，%.1fs）"
                    % (self.mt_device, self.load_s["mt"]))

    def mt(self, text: str, *, target_lang: Optional[str] = None) -> str:
        """翻译一句。`target_lang` 走 MT 的 `tgt` 参数。

        ★★ T-4：支持**按调用覆盖**目标语言。
          此前 `target_lang` 只在**构造时**定死（= 服务端 `--target-lang`），
          而插件面板上的「目标语言」虽然已经传到服务端，
          却只被**记录**（`client_target_lang`）、**从不生效**
          ⇒ 用户在面板上选日语，MT 仍然按服务端的语言译。
          ⇒ 现在允许调用方按句传入目标语言（不传则沿用构造时的默认值）。
          ⚠️ 传入的码**必须**是引擎认识的（zh/en/ja/ko），
            映射不到就**抛异常**，绝不静默回落。
        """
        if not text:
            return ""
        self._load_mt()
        tgt = self.mt_target(target_lang)
        # ★★ T-4：记下**实际生效**的目标语言（按句覆盖后的那个）。
        self.applied_target_lang = (target_lang if target_lang is not None
                                    else self.target_lang)
        try:
            r = self._mt.translate(text, tgt)
        except Exception as e:
            self.last_error["mt"] = "%s: %s" % (type(e).__name__, e)
            self.on_log("MT 调用失败: %s" % e)
            return ""
        self.n_calls["mt"] += 1
        return (r or {}).get("text", "") or ""

    def mt_target(self, target_lang: Optional[str] = None) -> str:
        """把目标语言映射成 MT 的 `tgt` 参数值。

        ★ 映射不到就**抛异常**，绝不静默传一个引擎不认的码
          （Hy-MT2 的 `_LANG_NAME` 只有 zh/en/ja/ko ⇒ 传别的会 KeyError
            或让 `_LANG_NAME[tgt]` 崩在渲染 prompt 的路上）。

        ★★ T-4：`target_lang` 给了就用它（**按调用覆盖**），
          不给（或为空）才沿用构造时的 `self.target_lang`。
        """
        key = (target_lang if target_lang is not None
               else (self.target_lang or "")).strip().lower()
        if key in LANG_TO_MT:
            return LANG_TO_MT[key]
        raise EngineNeedsChange(
            "Hy-MT2",
            "目标语言 %r 没有对应的 MT tgt（已知：%s）"
            % (target_lang if target_lang is not None else self.target_lang,
               ", ".join(sorted(LANG_TO_MT))))

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
        # 11-06 (reviewer): optional CUDA backend = the App's faster-qwen3-tts sidecar.
        dev = str(self.tts_device or "NPU").upper()
        if dev in ("AUTO", "CUDA"):
            cuda_ok = False
            try:
                import tts_cuda
                cuda_ok = tts_cuda.available()
            except Exception as e:
                self.on_log("TTS: CUDA 边车模块不可用：%s" % e)
            if cuda_ok:
                try:
                    # 11-08 reviewer: EXT copy of the sidecar = ICL clone when <ref>.txt exists
                    #   + steadier sampling (App package untouched).
                    _sc = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "tts_cuda_sidecar_ext.py")
                    if os.path.isfile(_sc):
                        tts_cuda.SIDECAR = _sc
                        os.environ.setdefault("LIVECAP_PKG", APP_ROOT)
                        os.environ.setdefault("EXT_TTS_TEMPERATURE", "0.6")
                        os.environ.setdefault("EXT_TTS_TOP_K", "20")
                    eng = tts_cuda.CudaTTSEngine(on_log=self.on_log)
                    eng.start()
                    self._tts_eng = eng
                    self._tts_spk_embed = None      # CUDA sidecar uses preset-A reference wav itself
                    self.tts_device = "CUDA"
                    self.load_s["tts"] = time.perf_counter() - t0
                    self.on_log("TTS 就绪（Qwen3-TTS @ CUDA 边车 faster-qwen3-tts，%.1fs，GPU=%s）"
                                % (self.load_s["tts"], getattr(eng, "device_name", "?")))
                    return
                except Exception as e:
                    if dev == "CUDA":
                        raise EngineNeedsChange("Qwen3-TTS", "CUDA 边车启动失败: %s" % e)
                    self.on_log("TTS: CUDA 边车启动失败，回落 NPU：%s" % e)
            elif dev == "CUDA":
                raise EngineNeedsChange("Qwen3-TTS", "要求 CUDA 但找不到 CUDA 环境（_fq3tts_env）")
            self.tts_device = "NPU"
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
        # ★★★ EXT-023：打印并落盘**各组件的实际执行设备**
        #   （EXECUTION_DEVICES）—— 确认 talker / cp_prefill / cp_decode /
        #   decoder **全部在 NPU**。
        #
        #   ## 背景（主会话转达 TTS reviewer 10-31 Opus）
        #   `qwen3tts_eval` 里裸 `build()` 默认把 **cp_decode 放在 CPU**，
        #   只有显式 `_recompile_cp_on_npu(only=["cp_decode"])` 之后才到 NPU
        #   （TTS-037 正在把默认改成 NPU）⇒ cp_decode 在 CPU 上会让
        #   TTS 的 RTF 变差约 30%（1.01 vs 0.71）。
        #
        #   ## 为什么这里能直接拿到
        #   App 侧 `tts_engine.make_engine()` 的**最后一步**已经调了
        #   `execution_devices(eng, on_log=on_log)` 并把结果挂成
        #   `eng.exec_devices`（含 `key4_line` / `devices` / `actual` /
        #   `on_npu` / `on_cpu` / `unknown` / `absent`）
        #   ⇒ **不需要重复探测**（重复探测会把 NPU 抢一次、很慢）。
        #
        #   ## 判据（**如实**）
        #   App 的 `execution_devices()` 用 OV 的 `EXECUTION_DEVICES` 属性
        #   ⇒ 是「**实际**执行设备」，不是「**请求**的设备」。
        #   ⚠️ OV 2026.4.1：NPU 档返回**字符串** `'NPU'`，
        #     CPU 档返回**列表** `['CPU']` ⇒ App 已做规范化。
        #
        #   ⚠️ **绝不臆造**：探测不到就写 `ok=False` + 原因，
        #     绝不假装「都在 NPU」。
        self._report_tts_exec_devices()
        self._prepare_preset_voice()

    # ── ★★★ EXT-023：TTS 各组件实际执行设备 ──────────────────
    def _report_tts_exec_devices(self) -> dict:
        """把 `eng.exec_devices` 打印成日志并**落盘**（EXT-023）。

        ## 为什么必须落盘（不能只在控制台打一行）
        * 铁律「**没落盘的东西不能写『已交付』**」——
          只打在启动日志里，reviewer 事后无从核对；
        * 落盘后 reviewer 可以直接 `json.load` 出**原始字段**
          （`devices` / `actual` / `on_npu` / `on_cpu` / `unknown`），
          而不是从日志文本里猜。

        ## 落盘位置
        `%LOCALAPPDATA%\\LiveDubEXT\\tts_exec_devices.json`
        —— 与 `bridge.log` **同目录**（reviewer 已经在看那个目录）。

        ## 返回
        落盘的字典（失败时是 `{"ok": False, "error": ...}`）。
        """
        out: dict = {}
        eng = self._tts_eng
        info = getattr(eng, "exec_devices", None) if eng is not None else None
        if not isinstance(info, dict):
            out = {"ok": False,
                   "error": "引擎没有 exec_devices 属性（App 侧未探测）",
                   "requested_device": self.tts_device}
        else:
            out = dict(info)
            out.setdefault("requested_device", self.tts_device)
            # ★ App 的 `key4_line` 就是 reviewer 要的那一行证据
            #   （'EXECUTION_DEVICES talker=…，cp_prefill=…，…'）。
            key4 = out.get("key4_line")
            if key4:
                self.on_log("[TTS-EXEC] %s" % key4)
            # ★ 逐组件也打一行（reviewer 要确认「全部是 NPU」）
            devs = out.get("devices") or {}
            actual = out.get("actual") or {}
            for label in sorted(devs):
                self.on_log("[TTS-EXEC] %-22s → %s"
                            % (label, devs.get(label)))
            on_npu = list(out.get("on_npu") or [])
            on_cpu = list(out.get("on_cpu") or [])
            unknown = list(out.get("unknown") or [])
            absent = list(out.get("absent") or [])
            self.on_log("[TTS-EXEC] on_npu=%d on_cpu=%d unknown=%d absent=%d"
                        % (len(on_npu), len(on_cpu), len(unknown), len(absent)))
            if on_cpu:
                self.on_log("[TTS-EXEC] ⚠️ **这些组件在 CPU 上**：%s"
                            % ", ".join(on_cpu))
            if unknown:
                self.on_log("[TTS-EXEC] ⚠️ **这些组件落点未知**：%s"
                            % ", ".join(unknown))
            # ★ 顺手把「实际落点」也带上（App 的 `actual` 字段）
            out["actual_devices"] = actual

        # ── 落盘（**失败不抛**，诊断增强不能搞挂引擎）────────────
        try:
            base = os.environ.get("LOCALAPPDATA") or "."
            d = os.path.join(base, "LiveDubEXT")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "tts_exec_devices.json")
            out["_saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            out["_saved_path"] = path
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            self.on_log("[TTS-EXEC] 已落盘：%s" % path)
        except Exception as e:
            self.on_log("[TTS-EXEC] ⚠️ 落盘失败：%r" % (e,))
        self.tts_exec_devices = out
        return out

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

    def tts_language(self, target_lang: Optional[str] = None) -> str:
        """把目标语言映射成 TTS 的 `language` 参数值。

        ★ EXT-006：TTS **必须**显式传目标语言（APP-030 日文失控事故的根因）。
        ⇒ 映射不到就**抛异常**，绝不静默退回 English。

        ★★ T-4：同 `mt_target` —— 支持**按调用覆盖**目标语言
          （面板上选的语言要真正作用到 TTS，而不只是被记录）。
        """
        key = (target_lang if target_lang is not None
               else (self.target_lang or "")).strip().lower()
        if key in LANG_TO_TTS:
            return LANG_TO_TTS[key]
        raise EngineNeedsChange(
            "Qwen3-TTS",
            "目标语言 %r 没有对应的 TTS language（已知：%s）"
            % (target_lang if target_lang is not None else self.target_lang,
               ", ".join(sorted(LANG_TO_TTS))))

    def tts(self, text: str, *, voice: str,
            target_lang: Optional[str] = None) -> Tuple[Optional[bytes], float]:
        """合成配音。

        ★ 显式传 `language`（EXT-006 / APP-030）
        ★ 显式传 `max_new_tokens`（失控闸第一道，APP-030②）
        ★ 墙钟与音频双上限 ⇒ 失控中止（EXT-006 明文要求）
        ★★ T-4：`target_lang` 支持**按调用覆盖**（面板上的选择要真正生效）

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

        language = self.tts_language(target_lang)   # ★ 必传，映射不到就抛
        max_tok = clamp_max_new_tokens(text, language)
        # ★ 第二道闸的输入（APP-030② 的口径）：用 `estimate_sec`
        #   （按字符口径，与 clamp 同源）而不是 `estimate_frames/12`
        #   —— 后者在语言全称（如 'Japanese'）下会因 `_SEC_PER_CHAR`
        #   的键不匹配而落到英文口径，阈值被低估。
        est_sec = float(estimate_sec(text, language))
        # ★ 墙钟闸用 App 的 RUNAWAY 判据：`max(3×est, est+8s)`，
        #   再用硬上限封顶（防止 est 估偏大时闸门形同虚设）。
        wall_limit = min(runaway_threshold_s(est_sec), TTS_WALL_CLOCK_CAP_SEC)

        spk_embed = self._apply_voice(voice)
        pcm = self._collect_tts(text, language=language, max_tok=max_tok,
                                wall_limit=wall_limit, speaker_embed=spk_embed)
        if pcm is None:
            return (None, 0.0)
        speech_sec = len(pcm) / 2.0 / 24000.0
        self.n_calls["tts"] += 1
        return (pcm, speech_sec)

    def _apply_voice(self, voice):
        """11-08 reviewer: voice = 克隆参考 wav 路径 ⇒ 用该说话人音色；否则预设 A。
        CUDA 边车按请求带 ref_audio ⇒ 当句生效；NPU 走 x-vector（按路径缓存）。"""
        path = voice if (voice and os.path.isfile(str(voice))) else None
        eng = self._tts_eng
        if getattr(eng, 'USES_REF_AUDIO', False):
            if not hasattr(self, '_preset_ref'):
                self._preset_ref = getattr(eng, 'ref_audio', None)
            want = path or self._preset_ref
            if want and getattr(eng, 'ref_audio', None) != want:
                eng.set_ref_audio(want)
            return None
        if path is None:
            return self._tts_spk_embed
        cache = self.__dict__.setdefault('_clone_embeds', {})
        if path not in cache:
            try:
                from tts_engine import speaker_embedding
                cache[path] = speaker_embedding(eng, ref_wav=path, on_log=self.on_log)
            except Exception as e:
                self.on_log('克隆 x-vector 失败（用预设 A）：%s' % e)
                cache[path] = None
        return cache[path] if cache[path] is not None else self._tts_spk_embed

    def _collect_tts(self, text: str, *, language: str, max_tok: int,
                     wall_limit: float, speaker_embed=None) -> Optional[bytes]:
        """跑 TTS 流式合成并收集 PCM，同时执行两道失控中止。"""
        from tts_engine import stream as tts_stream

        chunks: List[np.ndarray] = []
        sr = 24000
        t0 = time.perf_counter()
        aborted = None
        try:
            for wave, sample_rate in tts_stream(
                    self._tts_eng, text, language=language,
                    speaker_embed=speaker_embed,   # 11-08: 预设 A 或克隆说话人的 x-vector（CUDA 为 None）
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
            # ★★ T-4：客户端按句覆盖过的目标语言（最后一次）。
            #   ⇒ reviewer 能从引擎产物核对「面板上选的语言真的生效了吗」。
            "applied_target_lang": self.applied_target_lang,
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
