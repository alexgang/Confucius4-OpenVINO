"""APP-086(2)：克隆说话人音色编排层（a–f）。

移植口径（来自 `live_dub_ext` claude-dev:ext/clone_voice.py，**只读参考**，未改 EXT）：
  a 无标签不沿用上一句音色 / b 临时标签 / c 先出临时音色 /
  d 整句 clean + ASR 文本（ICL 参考，**仅 CUDA 路线**）/ e 参考冻结 / f 克隆工作移出 ASR 线程。

🔴🔴🔴 **接线口径（APP-086②，本轮裁定）**：**复用 App 既有的那一份旁路与音色表**
──────────────────────────────────────────────────────────────
上一版（§159 落盘的那份）`CloneVoices` **自带** `SpeakerBridge` +
`SpeakerVoiceTable` ⇒ 与 App GUI/CLI 各自已有的 `_spk_voices` **并存**
⇒ **双旁路**（两份 wespeaker + 两份 pyannote 同时跑 ⇒ 抢 NPU/集显
⇒ 两套标签互相打架 ⇒ 必然串音）。
⇒ 现在：**旁路（`bridge`）与音色表（`table`）都由 App 注入**
⇒ 全程**只有一份**旁路 + 一份音色表 ⇒ **不可能双旁路**。
⇒ 独立运行（不注入）时仍可自建旁路 ⇒ 保持「可单测」的形态。

**a（无标签不许沿用上一句音色）** 的落点分两层，缺一不可：
  ① **App 侧**（`live_caption_app.py`）：合成前用本模块算出「最近已登记说话人」
     （cos ≥ `MIN_SIM_NEAREST`）⇒ 把**那个 spk** 交给 worker；
  ② **worker 侧**（`tts_worker.py`）：按句绑定模式下 `spk=None` ⇒ **回落预设 A**
     ⇒ **绝不**沿用上一句的克隆音色（结构性保证）。
⇒ 只做 ① 不做 ②：最近说话人算不出来时仍会串音；只做 ② 不做 ①：
  无标签句全是预设 A（音色对，但**不是**本人音色 ⇒ 切换慢）。

**b（临时标签）**：定稿即给一个临时标签（最近质心，cos ≥ `MIN_SIM_PROVISIONAL`）
⇒ 旁路之后的正式标签覆盖它。

**d/e（ICL 参考 + 冻结）**：**仅 CUDA 路线**有意义（NPU 走 x-vector，
交接单 §5.1 / TTS-005 明文**禁止**在 NPU 侧传 `ref_text`/`ref_audio`）
⇒ 这里只做「整句 clean + 文本」的**收集与冻结**（写出 `<spk>_<n>.wav` + `.txt`，
`tts_cuda_sidecar.py` 侧已支持读同目录 `.txt` 作 `ref_text`）
⇒ **NPU 闸门不依赖它**（APP-088③：以 NPU 数字为闸门，CUDA 数字可选）。

**f（克隆工作移出 ASR/音频线程）**：最近质心要在 wespeaker 上做嵌入
⇒ 放在本模块自己的 `clone-policy` 线程里算 ⇒ ASR/音频线程只做「入队」。
"""
from __future__ import annotations

import os
import queue as _queue
import threading
import time as _time
from typing import Optional

import numpy as np

SR = 16000
KEEP_S = 90.0

# ── APP-086② a/b 的两个门槛 ──────────────────────────────────────────
MIN_SIM_NEAREST = 0.25     # a：无标签句 ⇒ 最近已登记说话人的最小余弦
MIN_SIM_PROVISIONAL = 0.40  # b：定稿时的临时标签最小余弦
MIN_SIM_DEFAULT = 0.20      # 内部默认（与移植版一致）

# ── d/e：ICL 参考的时长门槛与冻结规则 ───────────────────────────────
REF_FIRST_S = 3.0      # 首次登记门槛：攒够这么多「整句 clean」才写参考
REF_UPGRADE_S = 8.0    # 升级门槛：到这么多才允许**升级一次**，之后冻结
REF_MAX_S = 12.0       # 单个参考最多取多少秒

_CACHE_MAX = 256       # 最近质心缓存上限（段数）


def _seg_int(seg_id) -> int:
    return int(str(seg_id).rsplit("_", 1)[-1])


class CloneVoices:
    """APP-086② 的**策略层**：无标签句的最近说话人 / 临时标签 / ICL 参考收集。

    ⚠️ **本类不做音色登记**：登记仍由 App 既有的 `_pump_spk_voices()`
    （`register_spk_voice` ⇒ worker 侧算 x-vector）负责
    ⇒ **不产生第二条登记路径** ⇒ 不会双登记、不会互相覆盖。
    """

    def __init__(self, on_log=print, bridge=None, table=None,
                 pcm_getter=None, span_getter=None,
                 manage_reference=True, on_nearest=None):
        import sys as _sys
        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in _sys.path:
            _sys.path.insert(0, _here)

        self._log = on_log
        self.sv = table
        self.br = bridge
        self._own_bridge = False
        self._own_table = False

        if self.br is None:
            # 独立运行（单测 / 脚本）⇒ 自建旁路（App 侧**不会**走这条分支）
            import speaker_tracker
            self.br = speaker_tracker.SpeakerBridge(
                on_log=lambda m: on_log("[spk] %s" % m), enabled=True)
            self._own_bridge = True
        if self.sv is None:
            import speaker_voice
            self.sv = speaker_voice.SpeakerVoiceTable(
                on_event=lambda k, p: on_log("[spk] %s %s" % (k, p)))
            self._own_table = True

        self._pcm_getter = pcm_getter or (lambda: (np.zeros(0, dtype=np.float32), 0.0))
        self._span_getter = span_getter or (lambda seg: None)

        self._lock = threading.Lock()
        self._span = {}          # seg -> (t_start, t_end)
        self._text = {}          # seg -> ASR 文本（ICL 参考用）
        self._nearest = {}       # seg -> (spk, cos)（最近质心缓存；**带余弦**⇒ a/b 两个门槛都能用）
        self._emb = {}           # seg -> 嵌入向量（**缓存**⇒ 质心长出来后可零成本重算）
        self._pushed = {}        # seg -> (spk, cos)（已推给 worker 的最近说话人）
        self._on_nearest = on_nearest
        self._q = _queue.Queue()
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._worker, name="clone-policy",
                                     daemon=True)
        self._th.start()

        # d/e：整句 clean 参考（CUDA 路线）
        self._manage_reference = bool(manage_reference)
        self._cands = {}         # spk -> [(seg, dur, pcm, text)]
        self._ref_dur = {}       # spk -> 已写入参考的秒数
        self._upgraded = {}      # spk -> 是否已升级过（冻结）
        self.paths = {}          # spk -> 参考 wav 路径
        self.n_ref = 0
        self.dir = os.path.join(
            os.environ.get("LIVECAP_CLONE_VOICES_DIR")
            or os.environ.get("LOCALAPPDATA", "."),
            "Confucius4LiveCaption", "clone_voices")
        try:
            os.makedirs(self.dir, exist_ok=True)
        except Exception:
            pass

        self.n_nearest = 0
        self.n_hit = 0

    # ── ASR 线程：定稿时登记（**只入队，不算**）──────────────────
    def on_segment(self, seg_id, t_start: float, t_end: float,
                   text: str = "") -> None:
        """定稿一段 ⇒ 记下区间/文本 ⇒ 请求算「最近质心」。

        🔴 **不在这里做嵌入**（f）⇒ ASR/音频线程零阻塞。
        """
        seg = _seg_int(seg_id)
        with self._lock:
            self._span[seg] = (float(t_start), float(t_end))
            if text:
                self._text[seg] = str(text)
        self._q.put(seg)

    # ── 策略线程：算最近质心 ──────────────────────────────────────
    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                seg = self._q.get(timeout=0.25)
            except _queue.Empty:
                continue
            try:
                v = self._embed(seg)
                if v is None:
                    continue
                with self._lock:
                    self._emb[seg] = v
                    if len(self._emb) > _CACHE_MAX:
                        for k in list(self._emb.keys())[:len(self._emb) // 2]:
                            self._emb.pop(k, None)
                spk, sim = self._nearest_from_vec(v)
                with self._lock:
                    self._nearest[seg] = (spk, sim)
                if spk:
                    self.n_hit += 1
                self._try_push(seg)
            except Exception as e:
                self._log("[spk] 最近说话人计算失败（忽略）：%s" % e)

    def _embed(self, seg):
        """对这一句做嵌入（**只做一次**⇒ 缓存；质心长出来后可零成本重算）。

        🔴 与移植版一致：编码器有编译上限 ⇒ 超过 6 s 取中间 6 s。
        """
        tr = getattr(self.br, "_tracker", None)
        if tr is None:
            return None
        enc = getattr(tr, "_enc", None)
        clu = getattr(tr, "_clu", None)
        if enc is None or clu is None:
            return None
        span = self._span_getter(seg) or self._span.get(seg)
        if not span:
            return None
        try:
            buf, t0 = self._pcm_getter()
        except Exception:
            return None
        buf = np.asarray(buf, dtype=np.float32).reshape(-1)
        i0 = int((float(span[0]) - float(t0)) * SR)
        i1 = int((float(span[1]) - float(t0)) * SR)
        if i0 < 0 or i1 > buf.size or (i1 - i0) < int(1.0 * SR):
            return None
        pcm = buf[i0:i1]
        if pcm.size > int(6.0 * SR):
            m = (pcm.size - int(6.0 * SR)) // 2
            pcm = pcm[m:m + int(6.0 * SR)]
        try:
            with tr._lock:
                v = np.asarray(enc.embed(pcm, SR), dtype=np.float64).reshape(-1)
        except Exception as e:
            self._log("[spk] 最近说话人嵌入失败：%s" % e)
            return None
        n = float(np.linalg.norm(v))
        if n <= 0:
            return None
        return v / n

    def _nearest_from_vec(self, v):
        """拿**缓存的嵌入** ⇒ 与**当前**质心比 ⇒ `(spk, cos)`。

        🔴 质心是随会话增长的（旁路每识别出一个新说话人就加一个）
        ⇒ 同一个嵌入在不同时间点的「最近说话人」可能不同 ⇒ 允许重算。
        """
        tr = getattr(self.br, "_tracker", None)
        if tr is None:
            return None, 0.0
        clu = getattr(tr, "_clu", None)
        if clu is None:
            return None, 0.0
        try:
            with tr._lock:
                cents = list(clu.centroids)
                labels = [clu._label(k) for k in range(len(cents))]
        except Exception:
            return None, 0.0
        if not cents:
            return None, 0.0
        best, best_s = None, -1.0
        for k, c in enumerate(cents):
            s = float(np.dot(v, np.asarray(c).reshape(-1)))
            if s > best_s:
                best, best_s = labels[k], s
        if best is None:
            return None, 0.0
        self.n_nearest += 1
        return best, best_s

    def pump(self) -> None:
        """质心长出来之后**零成本重算**最近说话人（嵌入已缓存）⇒ 推给 worker。

        🔴 由 App 的**周期性泵**调用（GUI `_pump_spk_voices` / CLI `_cli_pump_spk_voices`）
        ⇒ 嵌入算在策略线程里（f）⇒ 这里只做**余弦比较**（微秒级）。
        """
        with self._lock:
            segs = list(self._emb.keys())
        for seg in segs:
            try:
                v = self._emb.get(seg)
                if v is None:
                    continue
                spk, sim = self._nearest_from_vec(v)
                with self._lock:
                    self._nearest[seg] = (spk, sim)
                self._try_push(seg)
            except Exception:
                continue

    def _try_push(self, seg) -> None:
        """把「最近**已登记**说话人」推给 worker（**走既有 `spk_update` 通道**）。

        🔴🔴🔳 **为什么不在提交时直接把 spk 塞进命令**：
          worker 的晚到标签通道（`_spk_bind`）**只在命令里 spk 为空时**才生效
          ⇒ 一旦提前塞了「最近说话人」，旁路后来的**官方标签就被挡住**
          ⇒ 可能用**错的**说话人 ⇒ 比回落预设 A 更糟。
        ⇒ 现在：**官方标签**仍走 `_spk_push_update`；**最近说话人**走同一条
          `spk_update` 通道（后写覆盖先写）⇒ 官方标签**后到**时自动胜出。
        🔴 **已有确认标签 ⇒ 一律不推**（官方优先）。
        """
        if self._on_nearest is None:
            return
        try:
            if self.sv.spk_of(seg):
                return                       # 已有官方标签 ⇒ 不动
        except Exception:
            return
        spk, sim = self._cached(seg) or (None, 0.0)
        if not spk or sim < MIN_SIM_NEAREST:
            return
        if not self._has_voice(spk):
            return                           # 该说话人还没登记音色 ⇒ 不推
        key = (spk, round(float(sim), 3))
        with self._lock:
            if self._pushed.get(seg) == key:
                return
            self._pushed[seg] = key
        try:
            self._on_nearest(seg, spk, float(sim))
        except Exception as e:
            self._log("[spk] 推最近说话人失败（忽略）：%s" % e)

    def _cached(self, seg_id):
        with self._lock:
            return self._nearest.get(_seg_int(seg_id))

    # ── 对外：合成前解析音色（**只读缓存，不阻塞**）──────────────
    def nearest_registered(self, seg_id, min_sim: float = MIN_SIM_NEAREST
                           ) -> Optional[str]:
        """a：**无标签**句 ⇒ 最近**已登记**（有音色）的说话人。

        🔴 **只认「已登记音色」的说话人** ⇒ 找不到就返回 `None`
        ⇒ 调用方回落**预设 A**（绝不用别人的音色）。
        🔴 **b 优先**：先取 cos ≥ `MIN_SIM_PROVISIONAL` 的**临时标签**
        （更可靠）⇒ 没有才放宽到 `min_sim`（a）。
        """
        seg = _seg_int(seg_id)
        spk, sim = self._cached(seg) or (None, 0.0)
        if not spk:
            return None
        if sim >= MIN_SIM_PROVISIONAL and self._has_voice(spk):
            return spk
        if sim >= float(min_sim) and self._has_voice(spk):
            return spk
        return None

    def provisional_spk(self, seg_id, min_sim: float = MIN_SIM_PROVISIONAL
                        ) -> Optional[str]:
        """b：定稿时的**临时标签**（最近质心，cos ≥ `min_sim`）。

        ⚠️ 临时标签**只是标签** ⇒ 不参与登记门槛的 conf 判定
        ⇒ 旁路正式标签到达后覆盖它。
        """
        spk, sim = self._cached(seg_id) or (None, 0.0)
        if not spk:
            return None
        return spk if sim >= float(min_sim) else None

    def _has_voice(self, spk) -> bool:
        try:
            return bool(self.sv.has_voice(spk))
        except Exception:
            return False

    def has_label(self, seg_id) -> bool:
        """这一句**已经有**（正式或临时）标签吗？"""
        seg = _seg_int(seg_id)
        try:
            if self.sv.spk_of(seg):
                return True
        except Exception:
            pass
        with self._lock:
            return bool(self._nearest.get(seg, (None, 0.0))[0])

    # ── d/e：ICL 参考（**仅 CUDA 路线**用）────────────────────────
    def collect_reference(self, seg_id, spk: str, conf, clean_ranges,
                          pcm=None, text: str = "") -> None:
        """收集「整句 clean + ASR 文本」⇒ 攒够 `REF_FIRST_S` 写一次参考。

        门槛（与移植版一致）：conf ≥ 0.5、clean 覆盖 ≥ 70 %、时长 1.5–12 s。
        """
        if not self._manage_reference or not spk:
            return
        seg = _seg_int(seg_id)
        span = self._span_getter(seg) or self._span.get(seg)
        if not span:
            return
        dur = float(span[1]) - float(span[0])
        if not (1.5 <= dur <= 12.0):
            return
        if float(conf or 0.0) < 0.5:
            return
        cover = sum(max(0.0, float(b) - float(a))
                    for a, b in (clean_ranges or [])) / max(dur, 1e-6)
        if cover < 0.7:
            return
        if pcm is None:
            try:
                buf, t0 = self._pcm_getter()
                buf = np.asarray(buf, dtype=np.float32).reshape(-1)
                i0 = int((float(span[0]) - float(t0)) * SR)
                i1 = int((float(span[1]) - float(t0)) * SR)
                if i0 < 0 or i1 > buf.size:
                    return
                pcm = buf[i0:i1]
            except Exception:
                return
        if pcm is None or np.asarray(pcm).size < int(1.5 * SR):
            return
        txt = str(text or self._text.get(seg) or "").strip()
        if not txt:
            return
        with self._lock:
            self._cands.setdefault(spk, []).append(
                (seg, dur, np.asarray(pcm, dtype=np.float32), txt))
        self._write_reference(spk)

    def _write_reference(self, spk: str) -> None:
        """e：**冻结**规则 ⇒ 首次 `REF_FIRST_S`，最多升级一次（`REF_UPGRADE_S`），之后不再改。"""
        with self._lock:
            cands = list(self._cands.get(spk) or [])
            cur = self._ref_dur.get(spk, 0.0)
            upgraded = bool(self._upgraded.get(spk))
        if not cands:
            return
        if cur > 0 and (cur >= REF_UPGRADE_S or upgraded):
            return                       # 冻结：不再改（避免音色漂）
        total = sum(c[1] for c in cands)
        need = REF_FIRST_S if cur <= 0 else REF_UPGRADE_S
        if total < need:
            return
        pick, acc = [], 0.0
        for c in reversed(cands):
            if acc + c[1] > REF_MAX_S and pick:
                break
            pick.append(c)
            acc += c[1]
        pick.reverse()
        gap = np.zeros(int(0.2 * SR), dtype=np.float32)
        pcm = np.concatenate([x for c in pick for x in (c[2], gap)])[:-gap.size]
        text = " ".join(c[3] for c in pick)
        with self._lock:
            self.n_ref += 1
            path = os.path.join(self.dir, "%s_%d.wav" % (spk, self.n_ref))
        import wave
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
        with open(path + ".txt", "w", encoding="utf-8") as f:
            f.write(text)
        with self._lock:
            if cur > 0:
                self._upgraded[spk] = True
            self._ref_dur[spk] = acc
            self.paths[spk] = path
        self._log("[spk] %s 参考%s（整句 %d 句 %.1f s + 文本，ICL）" % (
            spk, "升级" if cur > 0 else "已登记", len(pick), acc))

    def reference_path(self, spk: str) -> Optional[str]:
        with self._lock:
            return self.paths.get(spk)

    def stats(self) -> dict:
        with self._lock:
            return {
                'n_nearest': self.n_nearest,
                'n_hit': self.n_hit,
                'n_ref': self.n_ref,
                'cached': len(self._nearest),
                'paths': dict(self.paths),
            }

    def close(self) -> None:
        self._stop.set()
        if self._own_bridge:
            try:
                self.br.stop()
            except Exception:
                pass


__all__ = ['CloneVoices', 'SR', 'KEEP_S',
           'MIN_SIM_NEAREST', 'MIN_SIM_PROVISIONAL', 'MIN_SIM_DEFAULT',
           'REF_FIRST_S', 'REF_UPGRADE_S', 'REF_MAX_S']
