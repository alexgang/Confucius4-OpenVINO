# -*- coding: utf-8 -*-
"""🔴🔴🔴 APP-039 / APP-040：**音色按句绑定说话人**（说话人音色表）。

## 为什么要有这个模块（用户实测的三个症状）

APP-039 用户原话：

1. "语音音色切换非常滞后，超过了 10 s 的预期。"
2. "即使切换，音色也不正确，比如男声切女声，它是从一个低的音色逐渐切换到
   高的音色。设计本意是克隆原始说话人的音色，不是渐变。"
3. "感觉后台一直持续不断在采样克隆，应该是检测到说话人切换的时候才做
   采样克隆的动作，减少冗余计算量。"

⇒ **旧设计的三宗罪**（reviewer 推测，本模块的实现逐条对上了代码）：

| 罪 | 旧实现 | 本模块 |
|---|---|---|
| ① 渐变 | `clone_collector` 每 30 s 或 ≥6 s 新语音就重算 x-vector ⇒ **窗口里混了两个人** | **只在 `is_new_spk=True` 时取样一次** ⇒ 窗口只含**这个人自己的**语音 |
| ② 滞后 | 采样窗口是「最近 3–10 s」⇒ 要等新说话人说了几句话才够 3 s | APP-040②：新说话人**第一段**就有 ≥1.5 s 就能用 ⇒ 立即切换 |
| ③ 一直采样 | 每 30 s 一次，**与说话人无关** | **没有新 spk 就不做任何声纹计算** |

## 🔴🔴🔴 本模块的核心不变量（APP-039 明文）

1. **音色按句绑定**：`voice_for_sentence(spk)` 返回**这一句**该用的音色
   ⇒ 句子在队列里等多久都不影响它用谁的声音
   （旧实现是「取合成那一刻的当前音色」⇒ 队列里已合成的句子都用旧音色
   ⇒ 加上播放本身落后几十秒 ⇒ 用户听到换声远晚于实际换人）。
2. **切换是一次性的**：`is_new_spk` ⇒ 直接用新说话人的向量，
   **不插值、不渐变**（APP-039「切换是一次性的」）。
3. **禁止跨说话人平滑 / 滑动窗口**：每个 spk 的取样区间**只含该 spk 自己的**
   `clean_ranges`（由 ASR 旁路给出）⇒ 天然不会混入别人。
4. **没攒够就用预设 A**：新 spk 还没有可用音色 ⇒ **不用上一个人的声音冒充**
   ⇒ 回落到预设 A（APP-040②）。
5. **声纹只放内存**：`SpeakerVoiceTable` 只持有 numpy 数组 ⇒
   **会话结束清空、绝不落盘**（APP-039「内存：说话人表只放内存，
   会话结束清空，不落盘」）。
6. **换回老的人直接用缓存**（APP-040③）：**不重新取样**。

## 🔴 与 ASR 旁路接口的分工（ASR-029，`shared/NOTICE_asr_to_app_speaker_api.md`）

| 职责 | 归谁 |
|---|---|
| 判断「这句是谁说的」 | **ASR**（`SpeakerTracker.on_final` ⇒ `spk` / `spk_conf`） |
| 判断「这段里哪些区间是**干净的这个人**的语音」 | **ASR**（`clean_ranges`） |
| 从干净区间提取 **TTS 自己的 x-vector** | **App（本模块 + worker）** |
| 决定「用谁的声音、按句绑定、一步到位」 | **App（本模块）** |

🔴 **铁律**（ASR-026/§50）：**wespeaker 的向量只用于 ASR 内部聚类**，
**绝不**把它当作克隆向量传给 TTS ⇒ 本模块**不接触** ASR 的嵌入向量，
只用 `clean_ranges`（**时间区间**）⇒ App 自己去取 PCM、自己提 x-vector。

## 🔴 取样门槛（APP-040②）

- **≥ 1.5 s**：新说话人的**第一段**就够 ⇒ 立即可用（先切换，不等攒够）。
- **≥ 3 s**：攒够后**用这个人自己的段重算一次**（更准）⇒ 之后不再更新
  （APP-040②「攒到 ≥ 3 s 时用他自己的段重算一次，之后不再更新」）。

⇒ **声纹计算次数 ≈ 说话人数 × 1–2 次**（APP-039 验收③ / APP-040⑤）。

## 🔴 线程模型

- `note_final()`：由**会话线程**（`Session._loop`）调用 ⇒ 记录「这一句是谁」。
- `resolve()`：由**主线程**（GUI 轮询 / CLI 提交）调用 ⇒ 决定**这一句用哪个音色**。
- `pending_samples()`：由会话线程喂 PCM 时调用 ⇒ 攒**每个 spk 自己的**干净语音。

⇒ 所有状态用一把 `threading.Lock` 保护；**不碰任何 UI 对象**。
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

# 🔴🔴🔴 APP-040②：**取样门槛**（秒）
#   - `MIN_S` = 1.5 s：新说话人第一段够这个长度就**立即可用**
#     （APP-040②「≥ 1.5 s 就先用」）。
#   - `REFINE_S` = 3.0 s：攒够后**用这个人自己的段重算一次**（更准）
#     （APP-040②「攒到 ≥ 3 s 时用他自己的段重算一次，之后不再更新」）。
#   ⚠️ **两个门槛都只对「该 spk 自己的语音」计** ⇒ 绝不混入别人
#     ⇒ 这是「不渐变」的结构性保证。
MIN_S = 1.5
REFINE_S = 3.0

# 🔴 单个 spk 最多保留多少秒干净语音（**有界** ⇒ 内存不无界增长）
MAX_PER_SPK_S = 10.0

# 🔴 采样率（16 kHz 单声道）
SR = 16000


class SpeakerVoiceTable:
    """🔴🔴🔴 APP-039/040：**说话人 → 音色**的表（只放内存，绝不落盘）。

    ## 三种音色来源（`_voice`）

    | `_voice` | 含义 | 何时用 |
    |---|---|---|
    | `None` | **还没取到** ⇒ 用**预设 A** | 新 spk 的第一段不足 `MIN_S` |
    | `'preset'` | 用预设 A | 同上（显式区分「刻意用预设」与「还没取到」） |
    | `'clone'` | 用**该 spk 自己的**克隆向量 | 已取到 x-vector |

    ## 取样策略（APP-040②）

    - 新 spk 第一次出现 ⇒ 用它的 `clean_ranges` 取 PCM
      ⇒ 累计 ≥ `MIN_S` ⇒ **立刻**提取 x-vector ⇒ 标 `'clone'`
    - 该 spk 的语音累计到 ≥ `REFINE_S` ⇒ **重算一次**（更准）
      ⇒ 之后**不再更新**（APP-040②「之后不再更新」）
    - 换回老 spk ⇒ **直接用缓存**（`APP-040③`）⇒ **不重新取样**

    ## 隐私（APP-039）

    - 采样到的 PCM 与 x-vector **只在内存里**；
    - **绝不**写 `voices/clone_*.npz`、**绝不**写 `tts_speakers/`；
    - `reset()` 清空一切（会话结束 / 点「清空」时调用）。
    """

    def __init__(self,
                 min_s: float = MIN_S,
                 refine_s: float = REFINE_S,
                 max_per_spk_s: float = MAX_PER_SPK_S,
                 on_event: Optional[Callable[[str, dict], None]] = None):
        self._min_s = float(min_s)
        self._refine_s = float(refine_s)
        self._max_per_spk_s = float(max_per_spk_s)
        self._on_event = on_event

        self._lock = threading.Lock()
        # spk -> {'chunks': [np.ndarray], 'dur_s': float, 'voice': None|'clone',
        #         'vec': np.ndarray|None, 'refined': bool, 'first_seen': float}
        self._table: Dict[str, dict] = {}
        # seg -> spk（**按句绑定**的权威来源）
        self._seg_spk: Dict[int, str] = {}
        # spk -> [(start_s, end_s)]（ASR 给的干净区间，**只用来定位 PCM**）
        self._clean_ranges: Dict[str, List[Tuple[float, float]]] = []
        # 统计（APP-039 验收③：声纹计算次数）
        self.n_embed = 0          # 实际提取 x-vector 的次数
        self.n_switch = 0         # 说话人切换次数
        self.last_error = ''

    # ── 只读快照 ────────────────────────────────────────────────
    @property
    def n_speakers(self) -> int:
        with self._lock:
            return len(self._table)

    def stats(self) -> dict:
        """🔴 统计（供落盘证据 / GUI 显示）。"""
        with self._lock:
            return dict(
                n_speakers=len(self._table),
                n_embed=int(self.n_embed),
                n_switch=int(self.n_switch),
                n_seg=len(self._seg_spk),
                spks={k: dict(dur_s=round(v['dur_s'], 2),
                              clean_dur_s=round(v.get('clean_dur_s', 0.0), 2),
                              voice=v['voice'],
                              refined=bool(v['refined']))
                      for k, v in sorted(self._table.items())},
                last_error=self.last_error,
            )

    # ── ① 记录「这一句是谁说的」────────────────────────────────
    def note_final(self, seg: int, spk: Optional[str],
                   clean_ranges: Optional[list] = None) -> bool:
        """**按句绑定**：`seg` → `spk`。

        🔴 **与合成时刻无关**（APP-039「音色按句绑定…跟'当前时间'无关」）
        ⇒ 这一步**不做任何声纹计算**（APP-039「没有新 spk 时不做任何声纹计算」）。

        返回：是否**新出现**的说话人（`is_new_spk`）。
        """
        if not spk:
            return False
        is_new = False
        with self._lock:
            prev = self._seg_spk.get(seg)
            self._seg_spk[seg] = str(spk)
            if spk not in self._table:
                self._table[spk] = dict(
                    chunks=[], dur_s=0.0, clean_dur_s=0.0,
                    clean_spans=[], voice=None, vec=None,
                    refined=False, first_seen=time.time())
                is_new = True
            if clean_ranges:
                self._clean_ranges.append((str(spk),
                                           [(float(a), float(b))
                                            for a, b in clean_ranges]))
                # 🔴🔴🔴 §99（断链 B）：**登记时就把区间并集算进去**
                #   ⇒ 不必等外部再调 `add_clean_ranges` 才有时长
                #   ⇒ `dur_s` 不再恒为 0 ⇒ APP-040② 的「攒够 3 s 重算」
                #      才有可能发生。
                self._merge_clean_spans(str(spk), clean_ranges)
            if prev is not None and prev != spk:
                self.n_switch += 1
        if is_new:
            self._emit('new_spk', dict(spk=spk))
        return is_new

    def _merge_clean_spans(self, spk: str, ranges) -> None:
        """🔴 §99（断链 B）：把区间并进该 spk 的并集集合，并更新时长。

        ⚠️ **调用方必须已持有 `self._lock`**（`note_final` / `add_clean_ranges`）。
        """
        row = self._table.get(str(spk))
        if row is None:
            return
        try:
            items = [(float(a), float(b)) for a, b in (ranges or [])
                     if float(b) > float(a)]
        except Exception:
            return
        if not items:
            return
        merged = list(row.get('clean_spans') or [])
        merged.extend(items)
        merged.sort()
        out = []
        for a, b in merged:
            if out and a <= out[-1][1] + 1e-9:
                if b > out[-1][1]:
                    out[-1] = (out[-1][0], b)
            else:
                out.append((a, b))
        row['clean_spans'] = out
        row['clean_dur_s'] = sum((b - a) for a, b in out)
        row['dur_s'] = row['clean_dur_s']

    def rebind(self, seg: int, spk: str) -> bool:
        """🔴 APP-040④：**标签晚到时补标签**（`on_spk_update`）。

        ⇒ 该句先显示（无标签），标签随后补上。
        ⚠️ **已经合成过的句子不改音色**（APP-029/APP-039 明文）
        ⇒ 本函数只改**标签**，不动音色表。
        """
        if not spk:
            return False
        with self._lock:
            self._seg_spk[seg] = str(spk)
            if spk not in self._table:
                self._table[spk] = dict(
                    chunks=[], dur_s=0.0, clean_dur_s=0.0,
                    clean_spans=[], voice=None, vec=None,
                    refined=False, first_seen=time.time())
                self.n_switch += 1
                new = True
            else:
                new = False
        if new:
            self._emit('new_spk', dict(spk=spk))
        return True

    # ── ② 取样：攒「该 spk 自己的」干净语音 ────────────────────
    def add_clean_ranges(self, spk: Optional[str], ranges) -> bool:
        """🔴🔴🔴 §99（断链 B）：按 `clean_ranges` **累计干净语音时长**。

        ## 为什么必须有这个方法（§97 的断链）

        §97 声称「APP-040②：攒到 ≥ 3 s 时用他自己的段重算一次」已实施，
        但生产代码里**没有任何地方调用 `add_sample`** ⇒
        ⇒ `dur_s` **恒为 0** ⇒ `ready_to_embed` **恒为 False**
        ⇒ **「攒够 3 s 重算一次」这条永远不发生**。
        ⇒ 而 `add_sample` 要传 PCM，主进程手上只有**时间区间**
        （`clean_ranges`）⇒ 缺一个「按区间累计时长」的入口。

        ## 🔴 为什么必须按「并集」而不是「求和」

        同一段音频会被**多次引用**：每句定稿都会把该 spk 的**全部**干净区间
        再登记一次 ⇒ 若用求和 ⇒ 时长**虚高**（同一秒被数好几遍）
        ⇒ `ready_to_embed` 会**提前**为 True
        ⇒ APP-040②「攒到 3 s 重算一次」在**还没攒够**时就触发
        ⇒ 音色用**不足 3 s** 的样本算出来 ⇒ 音色质量下降。
        ⇒ 修法：**维护区间并集**（合并重叠区间）⇒ 时长**不重复计**。

        返回：是否成功登记（`spk` 未知 ⇒ False）。
        """
        if not spk:
            return False
        try:
            items = [(float(a), float(b)) for a, b in (ranges or [])
                     if float(b) > float(a)]
        except Exception:
            return False
        if not items:
            return False
        with self._lock:
            row = self._table.get(str(spk))
            if row is None:
                return False
            # 🔴 合并区间（并集）
            merged = list(row.get('clean_spans') or [])
            for a, b in items:
                merged.append((a, b))
            merged.sort()
            out = []
            for a, b in merged:
                if out and a <= out[-1][1] + 1e-9:
                    # 重叠 / 相接 ⇒ 合并
                    if b > out[-1][1]:
                        out[-1] = (out[-1][0], b)
                else:
                    out.append((a, b))
            row['clean_spans'] = out
            # 🔴 **时长 = 并集的总长**（不重复计）
            row['clean_dur_s'] = sum((b - a) for a, b in out)
            row['dur_s'] = row['clean_dur_s']
        return True

    def add_sample(self, spk: Optional[str], pcm) -> bool:
        """把一段**属于该 spk 的**干净 PCM 攒进它的表项。

        🔴 **调用方必须保证这段 PCM 是该 spk 自己的**（来自 ASR 的
        `clean_ranges`）⇒ 这样**天然不会混入别人** ⇒ 不需要任何平滑。
        ⚠️ 本函数**不做声纹计算**（只攒 PCM）⇒ 声纹计算发生在
        `maybe_embed()`（**只在够门槛时**才做）。
        """
        if not spk:
            return False
        try:
            import numpy as np
            a = np.asarray(pcm, dtype=np.float32).reshape(-1)
        except Exception:
            return False
        if a.size == 0:
            return False
        with self._lock:
            row = self._table.get(str(spk))
            if row is None:
                return False
            row['chunks'].append(a.copy())
            row['dur_s'] += a.size / float(SR)
            # 有界：只保留最近的语音
            max_samples = int(self._max_per_spk_s * SR)
            total = sum(c.size for c in row['chunks'])
            while total > max_samples and len(row['chunks']) > 1:
                total -= row['chunks'].pop(0).size
        return True

    def ready_to_embed(self, spk: str) -> bool:
        """该 spk 是否**攒够门槛**（可以提 x-vector 了）。"""
        with self._lock:
            row = self._table.get(str(spk))
            if row is None:
                return False
            if row['voice'] == 'clone' and row['refined']:
                return False        # 已经重算过 ⇒ 不再更新（APP-040②）
            need = self._refine_s if row['voice'] == 'clone' else self._min_s
            return row['dur_s'] >= need

    def take_pcm(self, spk: str):
        """取出该 spk 攒下的 PCM（调用方提 x-vector 用）⇒ **内存里交出副本**。"""
        with self._lock:
            row = self._table.get(str(spk))
            if row is None or not row['chunks']:
                return None
            import numpy as np
            return np.concatenate(row['chunks'], axis=0).reshape(-1).copy()

    def mark_embedded(self, spk: str, vec=None, refined: bool = False) -> None:
        """标记该 spk **已有可用音色**。

        ⚠️ `vec` 只保存在**内存**里（APP-039「说话人表只放内存」）
        ⇒ **绝不落盘**。
        """
        with self._lock:
            row = self._table.get(str(spk))
            if row is None:
                return
            row['voice'] = 'clone'
            if vec is not None:
                row['vec'] = vec
            if refined:
                row['refined'] = True
            # 提完就把攒的 PCM 丢掉（省内存，且不再需要）
            row['chunks'] = []
        self.n_embed += 1
        self._emit('embedded', dict(spk=spk, refined=refined))

    def mark_fallback(self, spk: str, reason: str = '') -> None:
        """🔴 明确记录「这个 spk 目前只能用预设 A」。

        🔴 **绝不**用上一个人的声音冒充新的人（APP-040②）
        ⇒ 这里只是**记录事实**（供 GUI 显示与日志）。
        """
        with self._lock:
            row = self._table.get(str(spk))
            if row is None:
                return
            row['voice'] = row['voice'] or 'preset'
            if reason:
                self.last_error = reason

    # ── ③ **按句**解析音色（核心）────────────────────────────────
    def voice_for_sentence(self, seg: int) -> str:
        """**这一句**该用谁的音色 ⇒ 返回 `spk` id。

        🔴🔴🔴 **这是 APP-039 的核心**：
        - 查的是「**这一句的 spk**」⇒ **与合成时刻无关**
          ⇒ 句子在队列里等多久都不影响它用谁的声音。
        - 该 spk **还没有可用音色** ⇒ 返回 `''`（⇒ 调用方用**预设 A**）
          ⇒ **不用上一个人的声音冒充**（APP-040②）。
        """
        with self._lock:
            spk = self._seg_spk.get(seg)
            if not spk:
                return ''
            row = self._table.get(spk)
            if row is None or row['voice'] != 'clone':
                return ''
            return spk

    def spk_of(self, seg: int) -> str:
        """这一句的 spk（**不管有没有音色**）⇒ 供字幕标签用。"""
        with self._lock:
            return self._seg_spk.get(seg, '')

    def has_voice(self, spk: str) -> bool:
        with self._lock:
            row = self._table.get(str(spk))
            return bool(row and row['voice'] == 'clone')

    def clean_ranges_of(self, spk: str) -> list:
        """🔴 APP-039/040：该 spk 的**干净区间**（累计，只含它自己的）。

        ⇒ 调用方用它从 PCM 环形缓冲里切出**这个人的**语音
        ⇒ **结构性保证**「不混入别人」（⇒ 不需要任何平滑/渐变）。
        """
        out = []
        with self._lock:
            for k, rngs in self._clean_ranges:
                if k == str(spk):
                    out.extend(rngs)
        return out

    # ── ④ 会话结束 ──────────────────────────────────────────────
    def reset(self) -> None:
        """🔴 **会话结束清空**（隐私纪律：x-vector 只在内存里）。"""
        with self._lock:
            self._table.clear()
            self._seg_spk.clear()
            del self._clean_ranges[:]
            self.n_embed = 0
            self.n_switch = 0
            self.last_error = ''

    def _emit(self, kind: str, payload: dict) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(kind, payload)
        except Exception:
            pass


__all__ = ['SpeakerVoiceTable', 'MIN_S', 'REFINE_S', 'MAX_PER_SPK_S', 'SR']
