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

R2T2_ROOT = os.environ.get("EXT_R2T2_ROOT",
                           r"C:\Users\Trekker-PTL\confucius4-openvino")
HY_ROOT = os.environ.get("EXT_HY_ROOT",
                         r"C:\Users\Trekker-PTL\hy_bench")
TTS_ROOT = os.environ.get("EXT_TTS_ROOT",
                          r"C:\Users\Trekker-PTL\confucius4-tts")


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
        """各引擎当前是否可接入（静态探测，不加载模型）。"""
        return {
            "asr": {"root": R2T2_ROOT, "device": DEVICE_ASR,
                    "probe_ok": self._probe(R2T2_ROOT, ("SegmentedStreamer",))},
            "mt": {"root": HY_ROOT, "device": DEVICE_MT,
                   "probe_ok": self._probe(HY_ROOT, ("hy",))},
            "tts": {"root": TTS_ROOT, "device": DEVICE_TTS,
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
