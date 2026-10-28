# -*- coding: utf-8 -*-
"""🔴🔴🔴 APP-027⑤：**克隆源语音采集器**（主进程侧，GUI 与 CLI 共用）。

## 为什么要独立成模块（🔴 本轮的根因）

APP-027 V3 明文要求「**用 SPE 前 5 分钟切片实时跑，开启克隆，落盘 ≥ 10 句 wav**」
⇒ 这必须能在 **CLI 回放** 里跑（GUI 需要人操作桌面快捷方式）。

⇒ 但旧的采集器是 **`App._collect_clone_pcm` 这个 GUI 实例方法** ⇒
**CLI 路径（`run_cli`）根本没有它** ⇒

- `run_cli` 构造 `Session(eng, src, on_final=on_final)` ⇒ **没有 `on_audio`** ⇒
  `Session._loop` 里的 `self.on_audio(pcm)` 那一段**永远不执行**；
- ⇒ 主进程**从不把克隆源 PCM 发给 worker** ⇒
  worker 的 `clone` 命令**永远收不到** ⇒ **克隆永远不生效**；
- ⇒ **V3（克隆实测）在 CLI 下客观做不了** ⇒ reviewer 要的
  「克隆组 wav」**根本采集不到**。

⇒ **本模块把采集逻辑抽成独立类**，GUI 与 CLI **共用同一份实现**
⇒ 既补上 CLI 的缺口，又**不复制逻辑**（复制 ⇒ 两边漂移 ⇒ 又是假证据）。

## 采集规则（APP-027 明文，逐字对齐）

> 「主进程从 ASR 输入的 16 kHz PCM 里取最近 3–10 s 的语音（去掉静音），
>   定期（如每 30 s，或累计到 ≥ 6 s 新语音时）发给 worker。」

⇒ 参数（与旧 GUI 实现**逐字一致**）：

| 参数 | 值 | 含义 |
|---|---|---|
| `_CLONE_MIN_S` | 3.0 s | 最短 3 s（worker 侧硬要求：不足 3 s 拒绝更新） |
| `_CLONE_MAX_S` | 10.0 s | 最长 10 s（只保留最近 10 s 的语音） |
| `_CLONE_UPDATE_INTERVAL_S` | 30.0 s | 触发条件①：每 30 s |
| `_CLONE_NEW_VOICED_S` | 6.0 s | 触发条件②：累计 ≥ 6 s **新**语音 |
| `_CLONE_FRAME` | 320 | 语音帧长（20 ms @ 16 kHz） |

## 去静音怎么做

按 20 ms 一帧算 RMS ⇒ 低于**自适应噪声门限**的帧丢掉。
⚠️ 噪声门限**自适应**：初始 0.004（≈ −48 dBFS），
随观测到的最小 RMS 缓慢下调（避免在噪声大的环境里一句都收不到）。

## 隐私（APP-022「共用约定」）

- 采集到的 PCM **只在进程内存里**（本类持有，不落盘）；
- 送给 worker 时走 **base64 进程间管道**（worker 侧若库只接受路径，
  会落 `tempfile.gettempdir()` 的临时 wav ⇒ **会话结束即删**）；
- ⇒ **绝不**写 `voices/clone_C.npz`、**绝不**写 `tts_speakers/`。
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import numpy as np

# 🔴🔴🔴 APP-027⑤：**克隆采集参数**（主进程侧）
#   - 最短 3 s（worker 侧硬要求：不足 3 s 拒绝更新）
#   - 最长 10 s（APP-027 明文：「取最近 3–10 s 语音」）
#   - 触发条件：每 30 s **或** 累计 ≥ 6 s 新语音（APP-027 明文）
_CLONE_MIN_S = 3.0
_CLONE_MAX_S = 10.0
_CLONE_UPDATE_INTERVAL_S = 30.0
_CLONE_NEW_VOICED_S = 6.0
#   - 语音帧长（20 ms @ 16 kHz）
_CLONE_FRAME = 320


class CloneCollector:
    """🔴🔴🔴 APP-027⑤：**克隆源语音采集器**（GUI 与 CLI 共用）。

    🔴 **用法**：
    ```python
    col = CloneCollector(lambda: tts_service)
    col.enabled = True
    Session(eng, src, on_final=..., on_audio=col.feed)   # ← 关键接线
    ```

    🔴 **线程**：本类由**会话线程**调用（`Session._loop`）⇒
      - 只碰自己的状态（有锁保护）；
      - **不碰任何 UI 对象**（Tk 不是线程安全的）⇒ GUI 显示走轮询拉取；
      - 调用 `service.set_clone_pcm()` ⇒ 它会写 worker 的 stdin
        ⇒ `tts_service` 侧已加**写锁**（APP-027⑤）⇒ 不会与
        `submit()`/`cancel()` 的命令交错。
    """

    def __init__(self,
                 get_service: Callable[[], Optional[object]],
                 min_s: float = _CLONE_MIN_S,
                 max_s: float = _CLONE_MAX_S,
                 update_interval_s: float = _CLONE_UPDATE_INTERVAL_S,
                 new_voiced_s: float = _CLONE_NEW_VOICED_S,
                 frame: int = _CLONE_FRAME,
                 on_status: Optional[Callable[[str], None]] = None):
        self._get_service = get_service
        self._min_s = float(min_s)
        self._max_s = float(max_s)
        self._update_interval_s = float(update_interval_s)
        self._new_voiced_s = float(new_voiced_s)
        self._frame = int(frame)
        self._on_status = on_status

        self._lock = threading.Lock()
        self._frames: list = []          # [np.float32(frame)] 有语音的帧
        self._voiced_s = 0.0             # 当前缓冲里的语音秒数
        self._sent_voiced_s = 0.0        # 已发送出去的语音秒数（累计）
        self._last_update = 0.0          # 上次发送时刻（time.monotonic）
        self._noise_floor = 0.004        # 自适应静音阈值（初始值）

        # 🔴 对外可读状态（GUI 拉取 / CLI 落盘）
        self.enabled = False             # 用户是否选了「跟随说话人（克隆）」
        self.status = ''                 # 状态文字（GUI 显示用）
        self.n_updates = 0              # 🔴 APP-027 V3：实际发出过几次更新
        self.n_sent_fail = 0             # 🔴 APP-027 V3：发送失败次数

    # ── 对外只读属性 ────────────────────────────────────────────
    @property
    def voiced_s(self) -> float:
        with self._lock:
            return self._voiced_s

    @property
    def sent_voiced_s(self) -> float:
        with self._lock:
            return self._sent_voiced_s

    def legacy_snapshot(self) -> dict:
        """🔴 §84：**旧 GUI 字段的快照**（向后兼容用）。

        ⇒ 旧实现把采集状态放在 `App._clone_frames` / `_clone_voiced_s` /
        `_clone_sent_voiced_s` / `_clone_last_update` / `_clone_noise_floor`
        ⇒ 抽成独立类后，GUI 仍保留这些字段 ⇒ **每帧同步回来** ⇒
        外部脚本（以及旧测试）读到的值**不变**。
        """
        with self._lock:
            return dict(
                frames=list(self._frames),
                voiced_s=self._voiced_s,
                sent_voiced_s=self._sent_voiced_s,
                last_update=self._last_update,
                noise_floor=self._noise_floor,
            )

    def reset(self):
        """清掉上一轮的采集状态（⇒ 避免用旧语音）。"""
        with self._lock:
            self._frames = []
            self._voiced_s = 0.0
            self._sent_voiced_s = 0.0
            self._last_update = 0.0
            self._noise_floor = 0.004
        self.n_updates = 0
        self.n_sent_fail = 0
        self._set_status('采集中…')

    def _set_status(self, text: str):
        self.status = text
        if self._on_status is not None:
            try:
                self._on_status(text)
            except Exception:
                pass

    # ── 主入口（会话线程调用）────────────────────────────────────
    def feed(self, pcm) -> bool:
        """吃一段 **16 kHz PCM**（`Session._loop` 调）⇒ 返回是否发出了更新。

        🔴 **失败绝不抛异常**（它在会话线程里 ⇒ 抛了会打断音频循环）。
        """
        if not self.enabled:
            return False
        try:
            a = np.asarray(pcm, dtype=np.float32).reshape(-1)
        except Exception:
            return False
        if a.size == 0:
            return False
        frame = self._frame
        n = a.size // frame
        if n <= 0:
            return False
        frames = a[:n * frame].reshape(n, frame)
        rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
        # 🔴 自适应噪声门限：取本批的最小 RMS 作参考（保守 floor）
        thr = max(self._noise_floor, float(rms.min()) * 2.0, 0.0015)
        # 🔴 门限缓慢跟随（升快降慢）⇒ 噪声环境里也能收够语音
        self._noise_floor = min(0.02, max(0.0015, self._noise_floor * 0.995))
        voiced_frames = frames[rms > thr]
        if voiced_frames.size == 0:
            return False

        need = False
        with self._lock:
            self._frames.append(voiced_frames)
            self._voiced_s += voiced_frames.shape[0] * frame / 16000.0
            # 只保留最近 10 s 的语音
            max_frames = int(self._max_s * 16000 / frame)
            total = sum(f.shape[0] for f in self._frames)
            while total > max_frames and len(self._frames) > 1:
                total -= self._frames.pop(0).shape[0]
            new_voiced = self._voiced_s - self._sent_voiced_s
            now = time.monotonic()
            last = self._last_update
            if (new_voiced >= self._new_voiced_s
                    or (now - last) >= self._update_interval_s):
                if self._voiced_s >= self._min_s:
                    need = True
                    self._last_update = now
                    self._sent_voiced_s = self._voiced_s
        if not need:
            return False

        try:
            sel = np.concatenate(self._frames, axis=0).reshape(-1)
        except Exception:
            return False

        svc = None
        try:
            svc = self._get_service()
        except Exception:
            svc = None
        if svc is None:
            return False
        try:
            ok = svc.set_clone_pcm(sel)
        except Exception as e:
            self.n_sent_fail += 1
            self._set_status('克隆更新异常：%s' % type(e).__name__)
            return False
        if ok:
            self.n_updates += 1
            self._set_status('已发送')
        else:
            self.n_sent_fail += 1
            self._set_status('发送失败（已回落预设 A）')
        return bool(ok)

    def summary(self) -> dict:
        """🔴 APP-027 V3：**采集器的可观测摘要**（供落盘证据）。"""
        with self._lock:
            return dict(
                enabled=bool(self.enabled),
                voiced_s=round(self._voiced_s, 2),
                sent_voiced_s=round(self._sent_voiced_s, 2),
                n_updates=int(self.n_updates),
                n_sent_fail=int(self.n_sent_fail),
                status=self.status,
                min_s=self._min_s,
                max_s=self._max_s,
                update_interval_s=self._update_interval_s,
                new_voiced_s=self._new_voiced_s,
                frame=self._frame,
            )
