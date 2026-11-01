"""engines.py — 引擎适配层（复用现有交付版本，不改对方文件）

EXT-001 总原则：
  * 引擎复用现有交付版本，**不改其他模块的文件**：
      - ASR  R2T2 INT8 @ GPU.0     → C:\\Users\\Trekker-PTL\\confucius4-openvino
      - MT   Hy-MT2 INT8 @ GPU.0    → C:\\Users\\Trekker-PTL\\hy_bench
      - TTS  Qwen3-TTS 全 NPU       → C:\\Users\\Trekker-PTL\\confucius4-tts
  * 只在 import 或**复制适配层**的范围内复用；
  * 发现引擎需要改动，**写进 status/STATUS_EXT.md**，由主会话转给对应模块。

当前状态（EXT-002，2026-10-27 16:40）：
  * ASR/MT/TTS 的**具体调用入口**在各自模块交付后由主会话通知接线；
    本文件已留好 `EngineAdapter` 接口与探测逻辑；
  * 引擎未接入时，`EngineAdapter.available` 为 False，
    桥接服务仍可跑 **P0 ③ 回声自测**（不占 GPU/NPU，不跑推理）。
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

import numpy as np

from .config import DEVICE_ASR, DEVICE_MT, DEVICE_TTS

def _resolve_roots() -> dict:
    """解析三个引擎的**代码根**（只读引用；**不加载**任何模型）。

    ★★ EXT-031 ②：**去掉写死的开发机绝对路径**
      （原 `C:\\Users\\Trekker-PTL\\confucius4-openvino` /
        `…\\hy_bench` / `…\\confucius4-tts`）
      ⇒ 改成「**App 包内**相对解析」：

      | 引擎 | 代码根（发行包内） | 模型目录（发行包内） |
      |---|---|---|
      | ASR (R2T2) | `app/`（含 `seg_stream.py`/`backends.py`） | `models/encoder-int8` + `models/decoder-gpu-int8` |
      | MT (Hy-MT2) | `app/`（含 `translator.py`） | `models/mt/mt2-int8sym-cw-q` |
      | TTS (Qwen3-TTS) | `app/`（含 `tts_engine.py`） | `models/qwen3tts` |

      ⇒ **不另带一份模型**（全部映射到 App 包内现有的）。
      环境变量 `EXT_R2T2_ROOT` / `EXT_HY_ROOT` / `EXT_TTS_ROOT` 仍可显式覆盖。
    """
    env = {"asr": os.environ.get("EXT_R2T2_ROOT"),
           "mt": os.environ.get("EXT_HY_ROOT"),
           "tts": os.environ.get("EXT_TTS_ROOT")}
    roots = {"asr": "", "mt": "", "tts": ""}
    models = {"asr": [], "mt": [], "tts": []}
    try:
        from .app_root import app_path
        app = app_path("app") or ""
        roots = {"asr": app, "mt": app, "tts": app}
        models = {
            "asr": [app_path("models", "encoder-int8") or "",
                    app_path("models", "decoder-gpu-int8") or ""],
            "mt": [app_path("models", "mt", "mt2-int8sym-cw-q") or ""],
            "tts": [app_path("models", "qwen3tts") or ""],
        }
    except Exception:
        pass
    for k in roots:
        if env.get(k):
            roots[k] = env[k].strip()
    return {"roots": roots, "models": models}


_ROOTS = _resolve_roots()
R2T2_ROOT = _ROOTS["roots"]["asr"]
HY_ROOT = _ROOTS["roots"]["mt"]
TTS_ROOT = _ROOTS["roots"]["tts"]
ENGINE_MODEL_DIRS = _ROOTS["models"]


class EngineAdapter:
    """统一封装 ASR / MT / TTS 三个引擎的调用。

    每个方法都**延迟加载**对方模块，避免桥接服务启动时就把
    GPU/NPU 全部占住（EXT-001：不在 CPU 上跑推理）。
    """

    def __init__(self) -> None:
        self._asr = None
        self._mt = None
        self._tts = None
        self._loaded = set()

    # ── 可用性探测（只探目录与符号，不加载权重） ─────────────────
    @staticmethod
    def _probe(root: str, needles=()) -> bool:
        if not os.path.isdir(root):
            return False
        if not needles:
            return True
        try:
            for dirpath, _dirs, files in os.walk(root):
                for fn in files:
                    if fn.endswith(".py"):
                        try:
                            with open(os.path.join(dirpath, fn), "r",
                                      encoding="utf-8", errors="ignore") as f:
                                head = f.read(40000)
                        except Exception:
                            continue
                        if all(n in head for n in needles):
                            return True
        except Exception:
            pass
        return False

    def available(self) -> dict:
        """各引擎当前是否可接入（静态探测，不加载模型）。

        ★★ EXT-031 ②：探测根**改为 App 包内**（发行包里真实位置），
          并额外报 `model_dirs`（**不另带一份模型**的映射证据）。
        """
        return {
            "asr": {"root": R2T2_ROOT, "device": DEVICE_ASR,
                    "model_dirs": ENGINE_MODEL_DIRS.get("asr", []),
                    "probe_ok": self._probe(R2T2_ROOT, ("SegmentedStreamer",))},
            "mt": {"root": HY_ROOT, "device": DEVICE_MT,
                   "model_dirs": ENGINE_MODEL_DIRS.get("mt", []),
                   "probe_ok": self._probe(HY_ROOT, ("mt_available",))},
            "tts": {"root": TTS_ROOT, "device": DEVICE_TTS,
                    "model_dirs": ENGINE_MODEL_DIRS.get("tts", []),
                    "probe_ok": self._probe(TTS_ROOT, ("tts",))},
        }

    # ── ASR ─────────────────────────────────────────────────────
    def asr(self, audio: np.ndarray, t_start: float, t_end: float) -> str:
        """对一段定稿音频做 ASR。引擎未接入时抛 NotImplementedError。"""
        if "asr" not in self._loaded:
            raise NotImplementedError(
                "ASR 引擎尚未接线：R2T2 的调用入口待主会话通知（见 STATUS_EXT.md）")
        return self._asr(audio, t_start, t_end)

    # ── MT ──────────────────────────────────────────────────────
    def mt(self, text: str) -> str:
        """翻译。引擎未接入时抛 NotImplementedError。"""
        if "mt" not in self._loaded:
            raise NotImplementedError(
                "MT 引擎尚未接线：Hy-MT2 的调用入口待主会话通知（见 STATUS_EXT.md）")
        return self._mt(text)

    # ── TTS ─────────────────────────────────────────────────────
    def tts(self, text: str, *, voice: str) -> Tuple[Optional[bytes], float]:
        """合成配音。

        Returns
        -------
        (pcm_bytes, speech_sec)
            pcm_bytes 为 24 kHz PCM16；引擎未接入时返回 (None, 0.0)。
        """
        if "tts" not in self._loaded:
            raise NotImplementedError(
                "TTS 引擎尚未接线：Qwen3-TTS 的调用入口待主会话通知（见 STATUS_EXT.md）")
        return self._tts(text, voice=voice)


def load_default() -> EngineAdapter:
    """返回默认适配器（当前为空接线状态）。"""
    return EngineAdapter()


# ═══════════════════════════════════════════════════════════════════
# EXT-006 [HIGH]：P1 接入**真实引擎**
# ═══════════════════════════════════════════════════════════════════
#
# EXT-002 时这里只能返回空适配器（引擎入口未确认）。EXT-006 明确要求
# 「P1 的定义以 EXT-001 为准：桥接服务接入 ASR/MT/TTS，走真实的
#  ASR→MT→TTS 链路，回声模式只作为自测保留」。
#
# ⇒ 真实实现放在 `ext/engine_runtime.py`（适配层，**不改对方文件**），
#   这里只做**延迟切换**：调用方显式要真实引擎时才 import 它。
#
# ⚠️ 真实引擎依赖 App 自带运行时（openvino / openvino_genai / babelvox），
#   在普通 venv 里 import 会失败 ⇒ 延迟到真正要用时才 import，
#   且失败时**降级为空适配器**并给出明确原因，不让整个桥接服务起不来。

def load_runtime_engine(*, target_lang: str = "en", **kwargs):
    """返回**真实引擎**适配器（EXT-006 P1）。

    Raises
    ------
    RuntimeError
        App 自带运行时不可用时抛出（调用方应把它当「明确失败」处理，
        **不静默回落到回声模式** —— 否则 P1 验收会拿到假数据）。
    """
    from .engine_runtime import load_runtime
    return load_runtime(target_lang=target_lang, **kwargs)


def try_load_runtime_engine(*, target_lang: str = "en", **kwargs):
    """返回真实引擎适配器；运行时不可用时返回 (None, 原因字符串)。"""
    try:
        return load_runtime_engine(target_lang=target_lang, **kwargs), ""
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
