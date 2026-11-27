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

# 现有交付版本（R2T2）所在目录。只读引用。
# ★★ EXT-031 ②：**去掉写死的开发机绝对路径**（原
#   `<开发目录>\confucius4-openvino`）⇒ 改成：
#   ① 环境变量 `EXT_R2T2_ROOT`（显式覆盖永远优先）；
#   ② **App 包内 `app/`**（发行包里 R2T2 原件的真实位置 ——
#      App 自带 `seg_stream.py` + `backends.py`，**不另带一份**）；
#   ③ 空串 ⇒ 退回本文件内**复制**的等价 VAD 切分逻辑（EXT-001 允许）。
def _resolve_r2t2_root() -> str:
    """解析 R2T2 原件目录（发行版优先；**绝不**臆造路径）。"""
    env = (os.environ.get("EXT_R2T2_ROOT") or "").strip()
    if env:
        return env
    try:
        from .app_root import app_path
        cand = app_path("app")
    except Exception:
        cand = None
    if cand and os.path.isfile(os.path.join(cand, "seg_stream.py")):
        return cand
    return ""


R2T2_ROOT = _resolve_r2t2_root()


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
                  max_segment_sec: float = SEG_MAX_SEC
                  ) -> List[Tuple[int, int]]:
    """规划分段，返回 [(start_sample, end_sample), ...]。

    与 R2T2 `SegmentedStreamer._plan_segments` 的 'vad' 策略一致：
      * 累积到 min_segment_sec 后，在 [min, max] 区间里找静音点切；
      * 找不到静音就强制切在 max_segment_sec；
      * 尾段直接到结尾。

    注意（EXT-002）：本函数**不涉及** pyannote，不做说话人判断。

    ★★★★★ EXT-034 ④：**首段限长不在这里做**（故意的）。

    ## 为什么不在这里做（踩过的坑）
      「首段限长」看起来该是分段器的事，但**流式**场景下
      缓冲区每处理一段就被裁掉（`ext/bridge.py` 的
      `self._buf = self._buf[cut:]`）⇒ **缓冲区里的「第一段」
      每轮都可能是不同的那一段**。
      ⇒ 若在分段器里按「缓冲区第一段」限长 ⇒ **每一轮的第一段**
      都被限短 ⇒ 等于把**所有段**都变成 3.5 s ⇒ 段数暴增、
      切点栅格整体平移 ⇒ **尾部残留**变少（实测 60 s 输入只剩 0.5 s
      ⇒ 低于 `flush` 的 1 s 门槛 ⇒ **尾段被丢**）。
      ⇒ 现在：**分段器保持与 R2T2 逐位一致**（等价性自测不变），
        首段限长改在 **`ext/bridge.py` 的会话级**做
        （见 `Session._split_first_segment`）。
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


def split_first_segment(segs: List[Tuple[int, int]], *,
                        cap_sec: Optional[float] = None,
                        min_sec: float = SEG_MIN_SEC,
                        sample_rate: int = SAMPLE_RATE,
                        ) -> List[Tuple[int, int]]:
    """★ EXT-034 ④：**把会话的第一段拆成两段**（缩短「起步」）。

    ## 语义（服务端与客户端共用**同一份**实现）
      * 只拆**会话真正的第一段**（调用方负责保证这一点）；
      * 首段长度 > `cap_sec` ⇒ 拆成 `[s0, s0+cap]` + `[s0+cap, e0]`；
      * 拆出来的第二片若 < `min_sec` ⇒ **不拆**（避免「碎片段」）；
      * 其余段的切点**逐位不变** ⇒ 尾段行为与原来完全一致。

    ## 为什么拆而不截短
      ★ 截短会整体平移切点栅格 ⇒ 尾部残留变少
        （60 s 输入：原来留 4 s 尾段，平移后只剩 0.5 s
        ⇒ 低于 `flush` 的 1 s 门槛 ⇒ **尾段被丢**）。
      ★ 拆成两段则：首段 `[0, cap]`、第二段 `[cap, 原切点]`
        ⇒ **后续所有切点逐位不变** ⇒ 尾段行为与原来**完全一致**
        ⇒ 唯一的差别 = 首段被拆成两段（更早起步）。

    ## 为什么放在这里（而不是 `Session` 的方法）
      服务端（`ext/bridge.py`）与客户端（`tools/p1_pipeline.py` 的
      `expected_segment_count()`）**都要**用它算「服务端会吐几段」
      ⇒ 必须**共用同一个函数**，否则两边各写一份 ⇒ 口径漂移
      ⇒ 客户端预期与服务端实际不符 ⇒ 收尾永远等不到。

    Parameters
    ----------
    segs : list
        `plan_segments()` 的结果（采样区间列表）。
    cap_sec : float or None
        首段上限（秒）。`None` ⇒ 不限长（**保持原样**）。
    min_sec : float
        拆出来的第二片的最短长度（秒）⇒ 低于它就不拆。

    Returns
    -------
    list
        拆过（或没拆）的分段列表。
    """
    if not cap_sec or not segs:
        return segs
    cap_samp = int(cap_sec * sample_rate)
    s0, e0 = segs[0]
    if (e0 - s0) <= cap_samp:
        # 首段本来就够短 ⇒ 不拆
        return segs
    split = min(s0 + cap_samp, e0)
    # ⚠️ 切出来的第二片不能短于 `min_sec`（否则是「碎片段」）
    if (e0 - split) < int(min_sec * sample_rate):
        # 碎片太短 ⇒ **不拆**（保持原样，宁可起步慢一点也不出碎片）
        return segs
    return [(s0, split), (split, e0)] + list(segs[1:])


def segments_to_seconds(segs: List[Tuple[int, int]]) -> List[Tuple[float, float]]:
    """采样区间 → 秒区间。"""
    return [(s / SAMPLE_RATE, e / SAMPLE_RATE) for s, e in segs]


def plan_segments_first_capped(audio: np.ndarray, *,
                                cap_sec: Optional[float] = None,
                                min_segment_sec: float = SEG_MIN_SEC,
                                max_segment_sec: float = SEG_MAX_SEC,
                                sample_rate: int = SAMPLE_RATE,
                                ) -> List[Tuple[int, int]]:
    """★ EXT-036 ④：**首段提前交付**口径（服务端与客户端共用同一份）。

    ## 要解决的问题（reviewer EXT-036 ④ 的原话）
      「seg_0 [0,3.5] 和 seg_56000 [3.5,8.0] 的 `audio_ready_rel` 都是
        **8.22 s**，也就是要等原来那段 8 s 的音频全部到齐以后才拆。
        ⇒ **要做的**：在切段器里 **3.5 s 一到就交出首段**。」

    ## 本函数给出的就是**服务端最终会吐出的段列表**
      （服务端是**流式**的 ⇒ 它按同一套规则增量地实现本函数；
        客户端拿**整段音频**调用本函数预测 ⇒ 段数永远一致）。

    ## 规则（与服务端增量实现**逐条对应**）
      1. 先按 R2T2 原件规划（`plan_segments`）⇒ 得到原始网格 `segs`；
      2. `cap = cap_sec × sample_rate`：
         * `e0 = segs[0][1]`（原始首段终点）；
         * 若 `e0 > cap` ⇒ 首段被**限长**成 `[0, cap]`，
           余下 `[cap, e0]` 成为第二段（**其余切点逐位不变**）；
         * 若 `e0 ≤ cap` ⇒ 首段本来就不长（提前交付会**越过**自然切点）
           ⇒ 第二段起点**移到 `cap`**（丢掉 `[e0, cap]` 这一小段自然边界）；
         * 若 `(e0 − cap) < min_segment_sec`（余段是**碎片**）
           ⇒ **不单独成段** ⇒ 并进下一段（起点 `cap`）⇒ **不产生碎片段**；
      3. `cap_sec is None` ⇒ 与 `plan_segments` **逐位一致**
         （R2T2 等价性不受影响）。

    ★ 与旧的 `split_first_segment()` 的差别：
      旧函数**只在服务端切网格之后**才拆 ⇒ **必须等原段（最多 8 s）到齐**
      ⇒ 首段的音频要等 8 s 才交出（EXT-036 ④ 的病根）。
      新函数描述的是**最终结果**，服务端按它**增量**实现 ⇒
      首段**一到 cap 秒就交出**，不必等原段。

    ★★★★★★ EXT-036 ④ 修正（**本函数必须与服务端逐位一致**）：
      上一版实现有一个**真缺陷**：服务端提前交付后把缓冲**裁掉**了
      `cap` 秒 ⇒ 下一轮 `plan_segments(self._buf)` 是**从 cap 处重新起算**
      ⇒ **VAD 切点栅格整体平移 3.5 s**
      ⇒ ① 尾段被吃掉（实测 flush 产出 0 段）；② 客户端段数预期漂移。
      ⇒ 现在服务端**保留缓冲**（只标记「已交付多少」）⇒ **栅格逐位不变**
      ⇒ 本函数也必须表达**同一个结果**：
        * 首段 = `[0, cap]`；
        * **其余段的切点 = 原始网格逐位不变**
          （只是把「原始首段」从网格里去掉，
            即 `segs[1:]`，**不重排**后续切点）；
        * 原始首段的**尾巴** `[cap, e0]`：
          - 若 `(e0 − cap) ≥ min_segment_sec` ⇒ 独立成段
            （接在首段之后，**位置就是原首段的位置** ⇒
              后续切点不受影响）；
          - 否则（碎片）⇒ **并进下一段**（下一段起点前移到 `cap`）。
      ⇒ 关键：**后续段的切点永远取自原始网格** ⇒ 尾段行为与原来完全一致。
    """
    segs = plan_segments(audio, min_segment_sec=min_segment_sec,
                         max_segment_sec=max_segment_sec)
    if not segs or not cap_sec:
        return segs
    cap = int(cap_sec * sample_rate)
    e0 = segs[0][1]
    min_samp = int(min_segment_sec * sample_rate)
    if len(segs) == 1:
        # 只有一段 ⇒ 首段限长后就是 `[0, cap]`（尾巴留给 flush）
        return [(0, min(cap, e0))]
    if e0 <= cap:
        # 首段本来就不长 ⇒ 提前交付点越过自然切点 ⇒ 第二段起点移到 cap
        #   （其余切点逐位不变）
        return [(0, cap), (cap, segs[1][1])] + list(segs[2:])
    if (e0 - cap) < min_samp:
        # 余段是碎片 ⇒ 并进下一段（不产生碎片段）
        #   ⇒ 下一段起点前移到 cap，其余切点逐位不变
        return [(0, cap), (cap, segs[1][1])] + list(segs[2:])
    # ★ 正常情况：首段限长 + 原首段尾巴独立成段 ⇒ **其余切点逐位不变**
    return [(0, cap), (cap, e0)] + list(segs[1:])


def split_first_segment_streaming(segs: List[Tuple[int, int]], *,
                                  cap_sec: Optional[float] = None,
                                  min_sec: float = SEG_MIN_SEC,
                                  ) -> List[Tuple[int, int]]:
    """★ EXT-036 ④：**首段已提前交付**之后的网格（服务端增量路径用）。

    ## 场景
      服务端把首段 `[0, cap]` **提前交出**后，缓冲**不裁剪**
      ⇒ `plan_segments(self._buf)` 给的仍是**原始网格**
      ⇒ 需要把这个网格里「已经交出去的首段」去掉，
        并把原首段的**尾巴**处理掉（独立成段 或 并进下一段）。

    ## 规则（与 `plan_segments_first_capped()` 的结果**逐位一致**）
      * 原首段尾巴 `[cap, e0]` 够长（≥ `min_sec`）⇒ **独立成段**，
        位置就是原首段的位置；
      * 否则是**碎片** ⇒ 并进下一段（下一段起点前移到 `cap`）；
      * **其余段的切点永远逐位不变** ⇒ 尾段行为与原来完全一致
        ⇒ 尾段**不会**被吃掉（这是上一版实现的真缺陷）。

    Parameters
    ----------
    segs : list
        `plan_segments()` 的**原始**网格（仍含首段）。
    cap_sec : float or None
        提前交付的长度（样本数口径已换算成秒）。
    min_sec : float
        独立成段的最短长度 ⇒ 低于它算碎片。

    Returns
    -------
    list
        去掉首段、补好尾巴之后的网格。
    """
    if not segs or not cap_sec:
        return segs
    cap = int(cap_sec * SAMPLE_RATE)
    e0 = segs[0][1]
    rest = list(segs[1:])
    min_samp = int(min_sec * SAMPLE_RATE)
    if e0 > cap and (e0 - cap) >= min_samp:
        # 尾巴够长 ⇒ 独立成段
        return [(cap, e0)] + rest
    # 碎片 ⇒ 并进下一段
    if rest:
        return [(cap, rest[0][1])] + list(rest[1:])
    return []


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
