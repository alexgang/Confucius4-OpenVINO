"""segmenter.py — EXT-002 核心：分段一直用 R2T2 原有断句

EXT-002 修订（2026-10-27 15:48，优先级高于 EXT-001）：
  * pyannote / segmentation-3.0 **只**做说话人识别，**不再**用来给 ASR 强制断句；
  * 断句继续用 R2T2 原有的方式（`seg_stream.py` 的 VAD 切分）；
  * 分段结果**不等待** pyannote 断句，不阻塞定稿。

复用边界（EXT-001 总原则）：
  * 优先 **import** 现有交付版本 `confucius4-openvino/seg_stream.py`，
    只读不改该仓库任何文件；
  * 该仓库不可用时，退回到本文件内**复制**的等价 VAD 切分逻辑
    （EXT-001 允许"复制适配层"）；
  * 两份实现共用同一组常量，默认参数与 R2T2 保持一致。
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional, Tuple

import numpy as np

from .config import (
    SAMPLE_RATE,
    SEG_MIN_SEC,
    SEG_MAX_SEC,
    VAD_SILENCE_DB,
    VAD_MIN_SILENCE_MS,
    VAD_FRAME_MS,
    VAD_HOP_MS,
)

# 现有交付版本（R2T2）所在仓库根目录。只读引用。
R2T2_ROOT = os.environ.get(
    "EXT_R2T2_ROOT",
    r"C:\Users\Trekker-PTL\confucius4-openvino",
)


# ── R2T2 原件加载（优先 import，不改其文件） ────────────────────────
_R2T2_MOD = None
_R2T2_TRIED = False

# ★ 本模块用**私有名**加载 R2T2 的 seg_stream，不占用全局 `seg_stream` 槽位。
#   原因（EXT-006 P1 实测踩到）：R2T2 仓库与 App 的 `app/` 目录有 **6 个同名
#   顶层模块**（backends / seg_stream / streaming_asr / segment_encoder_backend /
#   npu_delivery_backend / npu_embeds_backend）。若按普通 `import seg_stream`
#   加载，R2T2 的版本会**先进占位** `sys.modules['seg_stream']` 与
#   `sys.modules['backends']`；之后 App 的 `streaming_asr` / `segment_encoder_backend`
#   执行 `from backends import ...` 时会拿到 **R2T2 的 backends**（两份内容不同：
#   App 版多了 `_build_prompt_template_ids_for` 与 `force_language` 透传）
#   ⇒ 引擎被喂了**别的模块的依赖**。
#   ⇒ 私有名加载 ⇒ R2T2 的 seg_stream 只在本模块内可见，不污染全局命名空间。
_R2T2_MODULE_NAME = "ext._r2t2_seg_stream"
_R2T2_BACKENDS_NAME = "ext._r2t2_backends"


def _load_private(name: str, path: str):
    """按文件路径加载一个模块到**私有名**下（不改对方文件）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


def _try_load_r2t2():
    """加载 R2T2 的 seg_stream 模块（**私有名**，不占用全局 `seg_stream`）。

    Returns
    -------
    module or None
    """
    global _R2T2_MOD, _R2T2_TRIED
    if _R2T2_TRIED:
        return _R2T2_MOD
    _R2T2_TRIED = True
    if not os.path.isdir(R2T2_ROOT):
        return None
    path = os.path.join(R2T2_ROOT, "seg_stream.py")
    backends_path = os.path.join(R2T2_ROOT, "backends.py")
    if not os.path.isfile(path):
        return None

    # ★ 隔离两件事：
    #   ① `seg_stream` 本体用**私有名**加载 ⇒ 不占用全局 `sys.modules['seg_stream']`；
    #   ② `seg_stream` 顶层有 `from backends import ...` ⇒ 执行期间若全局
    #      `sys.modules['backends']` 为空，Python 会按 sys.path 找到
    #      **R2T2 的 backends** 并**占进全局** ⇒ 之后 App 侧的
    #      `streaming_asr` / `segment_encoder_backend` 执行
    #      `from backends import ...` 时会拿到 **R2T2 的 backends**
    #      （两份内容不同：App 版多了 `_build_prompt_template_ids_for`
    #      与 `force_language` 透传）⇒ 引擎被喂了别的模块的依赖。
    #   ⇒ 执行期间**临时**把 `sys.modules['backends']` 指向 R2T2 的 backends，
    #      执行完**还原** ⇒ 全局命名空间保持干净。
    saved_backends = sys.modules.get("backends")
    try:
        if os.path.isfile(backends_path):
            sys.modules["backends"] = _load_private(
                _R2T2_BACKENDS_NAME, backends_path)
        _R2T2_MOD = _load_private(_R2T2_MODULE_NAME, path)
    except Exception:
        _R2T2_MOD = None
    finally:
        if saved_backends is None:
            sys.modules.pop("backends", None)
        else:
            sys.modules["backends"] = saved_backends
    return _R2T2_MOD


def r2t2_available() -> bool:
    """是否能直接 import R2T2 原件（用于自测报告里写明走的是哪条路）。"""
    return _try_load_r2t2() is not None


def r2t2_module():
    """返回已加载的 R2T2 `seg_stream` 模块（**私有名**加载，见 `_try_load_r2t2`）。

    自测用它做「与 R2T2 原件逐段比对」；
    ⚠️ **不要**再写裸 `import seg_stream` —— 那会拿到 App 侧或全局槽位里的
    其它版本，比对的就不是 R2T2 原件了。
    """
    return _try_load_r2t2()


# ── 复制的等价 VAD 逻辑（仅在 R2T2 不可 import 时使用） ─────────────
def _frame_rms(x: np.ndarray, frame_ms: int = VAD_FRAME_MS,
               hop_ms: int = VAD_HOP_MS) -> np.ndarray:
    n = int(frame_ms * SAMPLE_RATE / 1000)
    h = int(hop_ms * SAMPLE_RATE / 1000)
    if n <= 0 or h <= 0:
        return np.zeros((0,), dtype=np.float32)
    if x.shape[0] < n:
        x = np.concatenate([x, np.zeros(n - x.shape[0], dtype=np.float32)])
    n_frames = max(0, (x.shape[0] - n) // h + 1)
    out = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        s = i * h
        out[i] = float(np.sqrt(np.mean(x[s:s + n] ** 2) + 1e-12))
    return out


def _find_silence_in_range(audio: np.ndarray, *, start_sample: int,
                            end_sample: int, silence_db: float = VAD_SILENCE_DB,
                            min_silence_ms: int = VAD_MIN_SILENCE_MS,
                            frame_ms: int = VAD_FRAME_MS,
                            hop_ms: int = VAD_HOP_MS) -> Optional[int]:
    """与 R2T2 `find_silence_in_range` 等价（取最长静音段中点作切点）。"""
    if end_sample <= start_sample:
        return None
    seg = audio[start_sample:end_sample]
    rms = _frame_rms(seg, frame_ms=frame_ms, hop_ms=hop_ms)
    if rms.shape[0] == 0:
        return None
    db = 20.0 * np.log10(rms + 1e-7)
    n = int(hop_ms * SAMPLE_RATE / 1000)
    is_sil = db < silence_db
    min_sil_frames = max(1, int(min_silence_ms / hop_ms))
    best_start, best_len = -1, 0
    cur_start, cur_len = -1, 0
    for i in range(is_sil.shape[0]):
        if is_sil[i]:
            if cur_start < 0:
                cur_start, cur_len = i, 1
            else:
                cur_len += 1
        else:
            if cur_len > best_len:
                best_start, best_len = cur_start, cur_len
            cur_start, cur_len = -1, 0
    if cur_len > best_len:
        best_start, best_len = cur_start, cur_len
    if best_start < 0 or best_len < min_sil_frames:
        return None
    mid_frame = best_start + best_len // 2
    return start_sample + mid_frame * n


# ── 对外接口 ───────────────────────────────────────────────────────
def plan_segments(audio: np.ndarray, *, min_segment_sec: float = SEG_MIN_SEC,
                  max_segment_sec: float = SEG_MAX_SEC) -> List[Tuple[int, int]]:
    """规划分段，返回 [(start_sample, end_sample), ...]。

    与 R2T2 `SegmentedStreamer._plan_segments` 的 'vad' 策略一致：
      * 累积到 min_segment_sec 后，在 [min, max] 区间里找静音点切；
      * 找不到静音就强制切在 max_segment_sec；
      * 尾段直接到结尾。

    注意（EXT-002）：本函数**不涉及** pyannote，不做说话人判断。
    """
    audio = np.asarray(audio, dtype=np.float32)
    if audio.shape[0] == 0:
        return []
    if min_segment_sec <= 0:
        return [(0, audio.shape[0])]

    r2t2 = _try_load_r2t2()
    if r2t2 is not None and hasattr(r2t2, "find_silence_in_range"):
        find_silence = r2t2.find_silence_in_range
    else:
        find_silence = _find_silence_in_range

    min_samp = int(min_segment_sec * SAMPLE_RATE)
    max_samp = int(max_segment_sec * SAMPLE_RATE)
    segs: List[Tuple[int, int]] = []
    i = 0
    while i < audio.shape[0]:
        j = min(i + min_samp, audio.shape[0])
        if j >= audio.shape[0]:
            segs.append((i, audio.shape[0]))
            break
        upper = min(i + max_samp, audio.shape[0])
        cut = find_silence(audio, start_sample=j, end_sample=upper,
                           silence_db=VAD_SILENCE_DB,
                           min_silence_ms=VAD_MIN_SILENCE_MS)
        if cut is None:
            segs.append((i, upper))
            i = upper
        else:
            segs.append((i, cut))
            i = cut
    return segs


def segments_to_seconds(segs: List[Tuple[int, int]]) -> List[Tuple[float, float]]:
    """采样区间 → 秒区间。"""
    return [(s / SAMPLE_RATE, e / SAMPLE_RATE) for s, e in segs]


def describe() -> dict:
    """自测用：说明当前分段来源与参数。"""
    r2t2 = _try_load_r2t2()
    return {
        "segmentation_source": "R2T2 import" if r2t2 is not None else "ext 内复制等价实现",
        "r2t2_root": R2T2_ROOT,
        "strategy": "vad",
        "min_segment_sec": SEG_MIN_SEC,
        "max_segment_sec": SEG_MAX_SEC,
        "silence_db": VAD_SILENCE_DB,
        "min_silence_ms": VAD_MIN_SILENCE_MS,
        "pyannote_used_for_segmentation": False,  # EXT-002
    }
