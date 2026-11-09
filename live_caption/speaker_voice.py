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

# ══════════════════════════════════════════════════════════════
# 🔴🔴🔴 APP-071(c) / APP-075(a)：**登记门槛**（防止「用错人的音频登记音色」）
# ══════════════════════════════════════════════════════════════
# 📌 背景（实测，见 `results/app/_app293_label_overlap.json`）：
#    ASR 给 seg1（9.6–19.2 s）打的标签是 **S2**，但 `spk_conf=0.1292`
#    ⇒ 该段的**真实说话人是女声**（实测 F0 197.53 Hz，GT = S1）。
#    旧逻辑**不看 `spk_conf`** ⇒ 拿这段女声给「S2」登记了 x-vector
#    ⇒ 之后**所有**男声句子都用女声播出（用户实测「男声听上去也是女声」）。
#
# 🔴🔴🔴 APP-075(a) 的要求是**三件事同时成立**才可登记：
#    ① `spk_conf ≥ REG_CONF_MIN`；
#    ② 该段落在 ASR 给的 `clean_ranges` **内**；
#    ③ 去掉**切换点前后 `SWITCH_GUARD_S`** 之后，仍有**连续 ≥ REG_MIN_CONT_S**
#       的音频。
#
# 🔴🔴🔴🔴 **实测硬证据：①（conf 门槛）与③（边界守卫）**都**挡不住**
#    **「标签已切给新人、但音频还属于旧人」的那几段**：
#
#    | 段 | 时间(s) | `spk_conf` | 边界守卫 | 真实性别（实测 F0） |
#    |---|---|---|---|---|
#    | seg1 | 9.6–19.2 | 0.1292 | 被挡 | 女 197.53 Hz |
#    | **seg2** | 19.2–25.6 | **0.8996** | **挡不住** | **女 175.82 Hz** |
#    | **seg3** | 25.6–32.0 | **0.9104** | **挡不住** | **女 188.24 Hz** |
#    | seg4 | 32.0–38.4 | 0.3757 | 被挡 | 中性 168.42 Hz |
#    | seg5 | 38.4–44.8 | 0.4016 | 挡不住 | 男 108.84 Hz |
#    | seg6–14 | 44.8–102.4 | 0.73–0.95 | 挡不住 | **男 100–135 Hz** |
#
#    ⇒ S1→S2 的切换点只有 **9.6 s**（S2 的 seg1 之后**再无换人**）
#      ⇒ seg2/seg3（19.2–32.0 s）**离切换点很远** ⇒ **守卫挡不住**
#      ⇒ 且它们的 `spk_conf` 高达 0.90/0.91 ⇒ **conf 门槛也挡不住**
#    ⇒ **①③ 只能挡掉 seg1/seg4 两段**，女声的 seg2/seg3 **必然**成为合格段。
#    ⇒ 🔴 **真正能选对人的是「择段策略」**（见 `registration_ticket()`）：
#      **最长**合格段 = 男声 57.6 s（seg6–14）＞ 女声 12.8 s（seg2–3）
#      ⇒ 登记到**对的人**。
#
# 🔴 `REG_CONF_MIN`：**登记用的 `spk_conf` 门槛**。
#    依据（`_app292_threshold_probe.json`，app250 设备实测段表）：
#      · 必须 **> 0.3217**（S4 首现段的 conf）⇒ 才能挡住**全部三处**
#        「切换边界首现」的高危段（S2 0.1292 / S3 0.0602 / S4 0.3217）；
#      · 必须 **≤ 0.6** ⇒ 门槛再高，S4 就**再也攒不够 2.5 s 连续合格音频**
#        （实测 0.7 ⇒ S4 最长连续 0.0 s ⇒ 该说话人**永远登记不上**）。
#    ⇒ 可行窗口 **[0.4, 0.6]** ⇒ 取中点 **0.5**（余量最大）。
#    🔴 **口径声明（APP-075(c)）**：该窗口**只来自一份 5 分钟样本**
#      （`SPE_mix_3303_3603.wav`）⇒ 见 §140 的第二份材料复验
#      （ASR-122 `asr122_asr050_regression.json`，900 s / 3 clip / 136 段）。
#    ⚠️ **语义澄清（ASR-048/049 明文）**：`spk_conf` = **与已登记者的最大余弦
#      相似度** ⇒ **低 = 新人**，**不是**「标签不可信」
#      ⇒ 所以门槛的**唯一作用**是「**选哪段音频登记**」（APP-075(b) 明文）
#      ⇒ **绝不**因为首段 conf 低就不登记、不播。
REG_CONF_MIN = 0.5

# 🔴 `REG_MIN_CONT_S`：**登记所需的最短「连续合格音频」**（秒）。
#    APP-071(c) 原文：「该说话人连续干净 ≥ 2.5 s 的音频登记」。
REG_MIN_CONT_S = 2.5

# 🔴 `SWITCH_GUARD_S`：**切换边界前后各留 0.5 s 不取**（APP-071(c) 原文）。
#    🔴 **这是本轮最关键的一条**（见上方 seg2/seg3 的反例）⇒ 不能调小。
SWITCH_GUARD_S = 0.5

# 🔴 `CONT_GAP_TOL_S`：**同一人相邻干净区间之间允许的间隙**（秒）。
#    ASR 的 `clean_ranges` 是段内 `p_speech>=0.5` 的子区间 ⇒ 同一人连续说话时
#    区间之间会有**几十到几百毫秒**的静音间隙 ⇒ 若间隙 > 0 则永远攒不够 2.5 s。
#    ⇒ 间隙 ≤ 0.5 s 视为**同一段连续发言**；间隙 > 0.5 s ⇒ 判为**断开**。
CONT_GAP_TOL_S = 0.5

# 🔴🔴🔳 **为什么没有「登记稳定期」参数**（本轮**评估后否决**的设计，写在
#    代码里避免以后重复走一遍）：
#   曾考虑加 `REG_SETTLE_S`（「等该标签的合格段不再增长 N 秒再登记」）
#   ⇒ 用真实数据推演后发现**会引入新的误判**：
#     S2 的女声合格段（19.2–32.0 s，12.8 s）在 seg3 到手后**不再增长**
#     ⇒ 稳定期一到（≈40 s）就登记**女声**
#     ⇒ 而真男声合格段要到 **44.8 s** 才出现 ⇒ **稳定期反而更早锁错**。
#   ⇒ **否决**：改用「**最长合格段优先 ＋ 变长即升级**」
#     （`registration_ticket()` + `mark_registered()`）
#     ⇒ 离线取到的是**男声**（57.6 s）；流式下**随合格段变长自动升级**。
#   🔴 **残留局限**（必须写进 STATUS）：升级**之前**已合成的句子仍用旧音色
#     ⇒ APP-029 明文「**已合成的不改**」⇒ 只能靠**选交付段**规避。

# 🔴 单个 spk 最多保留多少秒干净语音（**有界** ⇒ 内存不无界增长）
MAX_PER_SPK_S = 10.0

# ══════════════════════════════════════════════════════════════
# 🔴🔴🔴 APP-089 §2c-2：**EXT v0.3.2 的「说话人参考」口径**（XV_*）
# ══════════════════════════════════════════════════════════════
# 📌 EXT v0.3.2 `ext/clone_voice.py:_register_sentences` 的 x-vector 分支：
#   把这个人**干净、有标签**的句子**拼起来** ⇒ ≥ `XV_FIRST_S` 首次写入
#   ⇒ ≥ `XV_UPGRADE_S` **升级一次** ⇒ 最长 `XV_MAX_S` ⇒ 之后**冻结**。
#   🔴 **只生成 x-vector，不写 `.txt`**（ICL 已按 APP-089 §2a 删除）。
#
# 🔴 **与 APP-075 的关系（必须说清）**：
#   本口径**复用** APP-075 的合格段门槛（`REG_CONF_MIN` + `clean_ranges`
#   + 切换点守卫 + 连续 `REG_MIN_CONT_S`）⇒ **不会**把「低置信度段」
#   （APP-071 的女声误标段，`spk_conf=0.1292`）拉进来
#   ⇒ **不回归 APP-071/075**。
#   差别只在：**拼接多个合格段**（EXT 口径）而不是**只取最长那一段**。
XV_FIRST_S = 3.0     # 首次写入门槛（攒够 3.0 s 干净有标签语音）
XV_UPGRADE_S = 8.0   # 升级门槛（≥ 8.0 s 时升级**一次**）
XV_MAX_S = 10.0      # 单个参考最长 10.0 s
# 🔴🔴🔳 **纪元分簇的间隙阈值**（APP-071 保护）
#   ⇒ 同一个标签**先后覆盖两个人**时（实测 S2 先女声后男声）
#     ⇒ 两段**绝不能拼**（拼出来的 x-vector 是两个声音的平均 ⇒ 串音）
#   ⇒ 间隙 > 这个值 ⇒ 视为**不同纪元** ⇒ 分开处理。
XV_CLUSTER_GAP_S = 1.5

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
        # 🔴🔴🔳 APP-075(a)：seg -> 该段的 `spk_conf`（登记门槛用）
        self._seg_conf: Dict[int, float] = {}
        # 🔴🔴🔳 APP-075(a)：seg -> 该段的干净区间（登记门槛用）
        self._seg_clean: Dict[int, List[Tuple[float, float]]] = {}
        # 🔴🔴🔳 APP-075(a)：**切换点**（秒，全局时间轴）⇒ 边界守卫用
        self._switch_points: List[float] = []
        # 🔴🔴🔳 APP-075(a)(b)：spk -> **已登记所用的那一段**（判「要不要升级」）
        self._reg_run: Dict[str, dict] = {}
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

    def gate_stats(self) -> dict:
        """🔴🔴🔳 **登记门槛的可观测快照**（APP-075(b)：不能静默）。

        ⇒ 「这个 spk 现在有没有合格段」必须**看得见**
        ⇒ 否则「回落预设 A」就变成静默降级（用户以为在用克隆音色）。
        """
        out = {}
        with self._lock:
            spks = sorted(self._table.keys())
            for s in spks:
                runs = self._qualified_runs_locked(s)
                out[s] = dict(
                    n_qualified=len(runs),
                    qualified_dur_s=round(sum(r['dur_s'] for r in runs), 3),
                    longest_s=round(max([r['dur_s'] for r in runs] or [0.0]), 3),
                    reg_run=dict(self._reg_run.get(s) or {}),
                    voice=self._table.get(s, {}).get('voice'),
                )
        return out


    # ── ① 记录「这一句是谁说的」────────────────────────────────
    def note_final(self, seg: int, spk: Optional[str],
                   clean_ranges: Optional[list] = None,
                   spk_conf: Optional[float] = None) -> bool:
        """**按句绑定**：`seg` → `spk`。

        🔴 **与合成时刻无关**（APP-039「音色按句绑定…跟'当前时间'无关」）
        ⇒ 这一步**不做任何声纹计算**（APP-039「没有新 spk 时不做任何声纹计算」）。

        🔴🔴🔳 **APP-075(a)**：新增 `spk_conf` 参数 ⇒ 登记门槛要用的
        **置信度**必须**随段一起进来** ⇒ 旧签名只有 `clean_ranges`
        ⇒ 「这一段有多确信」这条信息**根本没进来** ⇒ 门槛无从谈起。

        🔴🔴🔳 **APP-075(a)**：同时记录**切换点**（相邻两段 spk 不同处）
        ⇒ 供「切换边界前后 `SWITCH_GUARD_S` 不取」使用。

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
                # 🔴🔴🔳 APP-075(a)：**登记用的干净区间**必须与**该段的
                #   `spk_conf`** 绑定 ⇒ 后面 `qualified_spans()` 才能
                #   「只看 conf 达标的段」。
                self._seg_clean.setdefault(int(seg), []).extend(
                    [(float(a), float(b)) for a, b in clean_ranges])
            # 🔴🔴🔳 APP-075(a)：**逐段记 conf**（登记门槛用）。
            if spk_conf is not None:
                try:
                    self._seg_conf[int(seg)] = float(spk_conf)
                except Exception:
                    pass
            # 🔴🔴🔳 APP-075(a)：**切换点**（相邻两段 spk 不同 ⇒ 交界处）
            #   ⇒ 供 `qualified_spans()` 做「边界前后 0.5 s 守卫」。
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

    # ── ② 登记门槛（APP-075(a)(b)）────────────────────────────────
    #
    # 🔴🔴🔳 **本模块是「登记音色」的唯一守门人**：
    #   旧实现 `clean_ranges_of(spk)` 返回该 spk 的**全部**干净区间
    #   ⇒ 拿**第一段**（= 切换边界那一段）去登记 ⇒ **用错人的音频**
    #   ⇒ 克隆音色串音（APP-071 / APP-075 的根因）。
    #
    #   现在：**只有「合格段」才能登记**（`qualified_runs()`），
    #   合格 = ① `spk_conf ≥ REG_CONF_MIN`
    #        ② 落在该段的 `clean_ranges` 内
    #        ③ 去掉**切换点前后 `SWITCH_GUARD_S`**
    #        ④ 连续 ≥ `REG_MIN_CONT_S`（间隙 ≤ `CONT_GAP_TOL_S` 视为连续）

    def _switch_points_locked(self) -> List[float]:
        """**切换点**（秒，全局时间轴）⇒ 边界守卫用。

        🔴 判定：**相邻两段**（按 seg 号）**说话人不同** ⇒ 交界处即切换点。
        ⚠️ **调用方必须已持有 `self._lock`**。
        """
        segs = sorted(self._seg_spk.keys())
        pts = []
        for a, b in zip(segs, segs[1:]):
            if self._seg_spk.get(a) == self._seg_spk.get(b):
                continue
            ra = self._seg_clean.get(int(a)) or []
            rb = self._seg_clean.get(int(b)) or []
            if not ra or not rb:
                continue          # 该侧没有区间 ⇒ 无法定位交界 ⇒ 跳过
            prev_end = max(x[1] for x in ra)
            cur_start = min(x[0] for x in rb)
            if cur_start < prev_end:
                cur_start = prev_end
            pts.append(round((prev_end + cur_start) / 2.0, 4))
        return pts

    @staticmethod
    def _subtract_guard(a: float, b: float, pts) -> List[Tuple[float, float]]:
        """从 `[a,b]` 里**挖掉所有切换点前后 `SWITCH_GUARD_S`**。"""
        pieces = [(float(a), float(b))]
        for p in pts:
            lo = p - SWITCH_GUARD_S
            hi = p + SWITCH_GUARD_S
            nxt = []
            for (x, y) in pieces:
                if y <= lo or x >= hi:
                    nxt.append((x, y))      # 不相交 ⇒ 整段保留
                    continue
                if x < lo:
                    nxt.append((x, lo))      # 守卫左侧
                if y > hi:
                    nxt.append((hi, y))      # 守卫右侧
            pieces = [(x, y) for (x, y) in nxt if y - x > 1e-6]
            if not pieces:
                break
        return pieces

    def qualified_runs(self, spk: str) -> List[dict]:
        """🔴🔴🔳 **该 spk 的「合格登记段」**（APP-075(a)）。

        返回 `[{'a','b','dur_s','segs'}, ...]`，按**时间先后**排序。
        🔴 **没有合格段 ⇒ 返回 `[]`** ⇒ 调用方**不得**用不合格段登记
        ⇒ 回落预设 A 并记日志（APP-075(b)）。

        合格判定（**三条同时成立**）：
        ① 该段的 `spk_conf ≥ REG_CONF_MIN`；
        ② 取该段的 `clean_ranges`（**必须落在 clean_ranges 内**）；
        ③ 挖掉**切换点前后 `SWITCH_GUARD_S`**；
        ④ 合并间隙 ≤ `CONT_GAP_TOL_S` 的相邻区间 ⇒ 连续时长 ≥ `REG_MIN_CONT_S`。
        """
        with self._lock:
            return self._qualified_runs_locked(spk)

    def _qualified_runs_locked(self, spk: str) -> List[dict]:
        """🔴 `qualified_runs` 的**无锁版本**（调用方必须已持有 `self._lock`）。

        🔴 **为什么要有这一层**：`self._lock` 是**不可重入**的
        `threading.Lock` ⇒ 「持锁再调 `qualified_runs`（它自己又取锁）」
        ⇒ **死锁**（实测：自检脚本挂死 ⇒ 定位到此）。
        ⇒ 所有**内部调用**一律走 `_qualified_runs_locked`。
        """
        pts = self._switch_points_locked()
        spans = []
        for seg, s in self._seg_spk.items():
            if str(s) != str(spk):
                continue
            conf = self._seg_conf.get(int(seg))
            if conf is None:
                # 🔴 **没有 conf ⇒ 无法判定 ⇒ 不许登记**
                #   （APP-075(a)：登记必须「conf ≥ 阈值 且落在 clean_ranges 内」）
                continue
            if float(conf) < REG_CONF_MIN:
                continue
            for (x, y) in (self._seg_clean.get(int(seg)) or []):
                for piece in self._subtract_guard(x, y, pts):
                    spans.append((piece[0], piece[1], int(seg)))
        if not spans:
            return []
        spans.sort()
        merged = []          # [a, b, [seg...]]
        for (x, y, seg) in spans:
            if merged and (x - merged[-1][1]) <= CONT_GAP_TOL_S:
                if y > merged[-1][1]:
                    merged[-1][1] = y
                merged[-1][2].append(seg)
            else:
                merged.append([x, y, [seg]])
        out = []
        for (x, y, segs) in merged:
            dur = y - x
            if dur < REG_MIN_CONT_S:
                continue          # ④ 连续时长不够 ⇒ 不合格
            out.append(dict(a=round(x, 4), b=round(y, 4),
                            dur_s=round(dur, 4),
                            segs=sorted(set(segs))))
        return out

    def registration_ticket(self, spk: str):
        """🔴🔴🔳 **本次登记该用哪一段 ＋ 身份票**（APP-075(a)(b)）。

        返回 `([(a, b)], key)`：
        - **没有合格段** ⇒ `([], None)`
          ⇒ 调用方**不得**用不合格段登记 ⇒ **回落预设 A ＋ 记日志**
          （APP-075(b) 明文：「不得用不合格段登记」）。
        - `key` 变化 ⇒ 说明该重发（**升级登记**，APP-075(b)）。

        🔴🔴🔳 **选段策略 =「最长的一段合格段」**（**不是**最早的那段）：

        ## 为什么不能「谁先来用谁」
        实测（`results/app/_app295_f0_verify.json` / `_app293_label_overlap.json`）：
        ASR 的**同一个标签** `S2` 先覆盖了**女声**（seg2–3，F0 175.82/188.24 Hz），
        后覆盖**男声**（seg6–14，F0 100–135 Hz）
        ⇒ **同一个标签下先后是两个人**。
        ⇒ 「先来先登记」⇒ 登记到**女声** ⇒ 之后**所有**该标签的句子
        （包括真正的男声）都用女声播出 ⇒ **这就是 APP-071 的现象**。
        ⇒ 只能等**更长**的合格段出现（= 更长的干净音频）⇒ 声纹更稳 ⇒ 更可靠。

        ## 为什么「最长」能选对
        S2 的合格段：女声段 12.8 s（seg2–3）／男声段 **57.6 s**（seg6–14）
        ⇒ 「最长」= **男声** ⇒ 登记到**对的人**。
        （女声段虽然 `spk_conf` 高达 0.90/0.91，但**时长短** ⇒ 落选。）

        🔴🔴🔳 **升级语义（APP-075(b)「有合格段后升级登记」）**：
        已经用某段登记过 ⇒ **只有出现「更长」的合格段**才返回新票
        （⇒ 覆盖旧登记）；否则返回**空票** ⇒ 调用方**不会重发**
        ⇒ 避免「每来一段就重登记一次」⇒ 声纹计算次数不受控。

        ## 代价（必须写进 STATUS）
        🔴 首次登记会**晚一点**才定型（要等到「更长的一段」出现）
        ⇒ APP-040②「第一段就够 1.5 s 立即用」的**即时性被牺牲**
        ⇒ 这是**为正确性付的代价**（串音比延迟严重）。
        ⇒ 期间**回落预设 A**（APP-075(b)）⇒ 不出声错人。
        """
        with self._lock:
            runs = self._qualified_runs_locked(spk)
            if not runs:
                return [], None
            # 🔴 **最长**优先；等长时取**更晚**的那段（更新的数据更可信）
            best = runs[0]
            for r in runs[1:]:
                if (r['dur_s'], r['a']) > (best['dur_s'], best['a']):
                    best = r
            # 🔴🔴🔳 **升级判定**：已登记过 ⇒ 只有「更长」的合格段才给新票。
            prev = self._reg_run.get(str(spk)) or {}
            if prev:
                prev_dur = float(prev.get('dur_s') or 0.0)
                if float(best['dur_s']) <= prev_dur + 1e-6:
                    # 🔴 没有更长的合格段 ⇒ **不给票**（调用方不会重发）
                    return [], None
                # reviewer 11-07: the SAME run growing past the cap gives the same
                #   (MAX_PER_SPK_S-capped) audio => no new ticket (was: re-register on
                #   every final, 9x identical x-vectors in the SPE mix test).
                if (abs(float(best['a']) - float(prev.get('a', -1.0))) < 1e-3
                        and prev_dur >= MAX_PER_SPK_S - 1e-6):
                    return [], None
            key = (round(best['a'], 3), round(best['b'], 3),
                   round(best['dur_s'], 3))
            return [(float(best['a']), float(best['b']))], key

    # ══════════════════════════════════════════════════════════════
    # 🔴🔴🔴 APP-089 §2c-2：**EXT v0.3.2 的「说话人参考」（XV_*）**
    # ══════════════════════════════════════════════════════════════
    def xv_reference_ticket(self, spk: str):
        """🔴🔴🔴 **EXT v0.3.2 的「说话人参考」**：拼接该 spk 的干净有标签句子。

        ## 与 `registration_ticket()` 的差别

        | | `registration_ticket()`（APP-075） | **本方法**（APP-089 §2c-2） |
        |---|---|---|
        | 取哪几段 | **只取最长**的一段 | **拼接多个**合格段（按时间序） |
        | 首次写入门槛 | ≥ `MIN_S`(1.5 s) | ≥ `XV_FIRST_S`(3.0 s) |
        | 升级 | 变长即升级（可多次） | ≥ `XV_UPGRADE_S`(8.0 s) 时**升级一次** ⇒ 之后冻结 |
        | 最长 | `MAX_PER_SPK_S`(10 s) | `XV_MAX_S`(10 s) |
        | 产出 | 段区间 | 段区间（**只产 x-vector，不写 `.txt`**） |

        🔴 **不回归 APP-071/075**：候选段**仍然**必须过 APP-075 的合格门槛
        （`REG_CONF_MIN` + 落在 `clean_ranges` 内 + 切换点守卫 +
        连续 `REG_MIN_CONT_S`）⇒ 低置信度误标段**进不来**。

        返回 `([(a, b), ...], key, total_s, state)`：
        - `state` ∈ `'wait'`（还不够 `XV_FIRST_S`）/ `'first'`（可首次写入）
          / `'upgrade'`（可升级一次）/ `'frozen'`（已冻结，不再改）
        - 无合格段 ⇒ `([], None, 0.0, 'wait')`
        """
        spk = str(spk)
        with self._lock:
            runs = self._qualified_runs_locked(spk)
            row = self._table.get(spk)
            voice = (row or {}).get('voice')
            prev = dict(self._reg_run.get(spk) or {})
        if not runs:
            return [], None, 0.0, 'wait'
        # 🔴🔴🔳 **按「说话人纪元」分簇**（APP-071 保护）
        #   ⇒ 同一个标签**先后覆盖两个人**时（APP-071 实测：S2 先女声后男声）
        #     ⇒ 两段**不能拼在一起**（拼出来的 x-vector 是两个声音的平均 ⇒ 串音）
        #   ⇒ 分簇规则：相邻合格段之间的间隙 > `XV_CLUSTER_GAP_S` ⇒ 换簇
        #   ⇒ 取**总时长最长**的那一簇（= APP-075「最长合格段优先」的推广）
        ordered = sorted(runs, key=lambda r: float(r['a']))
        clusters = []
        cur = [ordered[0]]
        for r in ordered[1:]:
            gap = float(r['a']) - float(cur[-1]['b'])
            if gap > XV_CLUSTER_GAP_S:
                clusters.append(cur)
                cur = [r]
            else:
                cur.append(r)
        clusters.append(cur)
        best = max(clusters, key=lambda c: sum(float(x['dur_s']) for x in c))
        # 🔴 **按时间序拼接**该簇（EXT：`for c in reversed(cands)` 取最近几句 ⇒
        #   这里等价于「按时间序取满 `XV_MAX_S`」）。
        picked = []
        acc = 0.0
        for r in best:
            d = float(r['dur_s'])
            if picked and acc + d > XV_MAX_S:
                break
            picked.append(r)
            acc += d
        if acc <= 0.0:
            return [], None, 0.0, 'wait'
        rngs = [(float(r['a']), float(r['b'])) for r in picked]
        key = (round(acc, 3), len(rngs),
               tuple((round(a, 3), round(b, 3)) for a, b in rngs))
        if voice != 'clone':
            # 🔴 还没登记 ⇒ 首次写入门槛
            if acc < XV_FIRST_S:
                return rngs, None, acc, 'wait'
            return rngs, key, acc, 'first'
        # 🔴 已登记 ⇒ 升级判定
        prev_dur = float(prev.get('xv_dur_s') or prev.get('dur_s') or 0.0)
        if prev.get('upgraded'):
            return rngs, None, acc, 'frozen'    # 已升级过一次 ⇒ 冻结
        if acc < XV_UPGRADE_S:
            return rngs, None, acc, 'frozen'    # 还没到升级门槛 ⇒ 不动
        if acc <= prev_dur + 1e-6:
            return rngs, None, acc, 'frozen'    # 没变长 ⇒ 不动
        return rngs, key, acc, 'upgrade'

    def mark_xv_registered(self, spk: str, total_s: float,
                           upgraded: bool = False) -> None:
        """🔴 记下「已用 XV 参考登记了多久」＋**是否已升级过**（冻结用）。

        🔴 `upgraded=True` **只在「升级那次」登记时传**
        （EXT：首次写入 `cur==0` ⇒ 不置 `upgraded`；升级那次才置 ⇒ 之后冻结）。
        """
        with self._lock:
            prev = self._reg_run.get(str(spk)) or {}
            prev['xv_dur_s'] = round(float(total_s), 4)
            if upgraded:
                prev['upgraded'] = True
            self._reg_run[str(spk)] = prev

    def mark_registered(self, spk: str, a: float, b: float) -> None:
        """🔴 **记下「这个 spk 已用哪一段登记了」**（下次判「要不要升级」用）。

        🔴🔴🔳 **APP-075(b)**：「有合格段后升级登记（覆盖旧登记）」
        ⇒ 必须知道**上一次登记用的是哪一段**、**多长**
        ⇒ 只有「新的合格段**更长**」才算升级（否则反复重登记 ⇒ 白耗算力）。

        🔴🔴🔳 **APP-089 §2c-2 修正**：旧实现**整份覆盖** `_reg_run[spk]`
        ⇒ 会把 `mark_xv_registered` 写的 `xv_dur_s` / `upgraded` **冲掉**
        ⇒ XV 的「升级一次然后冻结」状态**丢失** ⇒ 可能反复升级。
        ⇒ 现在改成**合并**（保留 XV 字段）。
        """
        with self._lock:
            prev = dict(self._reg_run.get(str(spk)) or {})
            prev.update(a=float(a), b=float(b),
                        dur_s=round(float(b) - float(a), 4),
                        at=time.time())
            self._reg_run[str(spk)] = prev

    def reg_run_of(self, spk: str) -> dict:
        """🔴🔴🔳 **读回「这个 spk 上次登记用的是哪一段」**（判升级用）。"""
        with self._lock:
            return dict(self._reg_run.get(str(spk)) or {})


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
        """该 spk 是否**攒够门槛**（可以提 x-vector 了）。

        🔴🔴🔳 **APP-075(a)(b)**：门槛**必须看「合格段」**，不能看
        「该 spk 的全部干净时长」⇒ 否则第一段（切换边界那一段）就会被
        当成「够 1.5 s」⇒ 用错人的音频登记。

        🔴🔴🔳 **升级口径**：已登记过（`voice=='clone'`）⇒
        只有「**出现更长的合格段**」才允许重算（覆盖旧登记，APP-075(b)）
        ⇒ 旧的 `refined` 一票否决**改为**「没有更长合格段 ⇒ 不更新」
        （否则升级路径永远走不到）。

        🔴🔴🔳 **兜底路径（保持旧行为逐字一致）**：
        **当这个 spk 压根没有 `spk_conf` 记录**（= 该 spk 的段**全都没有**
        conf ⇒ 走的是 `add_sample()` 老路径 / 单测）⇒ **退回旧口径**
        （看 `dur_s`）⇒ 否则 app150 回归套件的 A6b 会 FAIL
        （旧行为：攒够 `REFINE_S` ⇒ 可细化）。
        🔴 **判别条件必须严格**：只要**有任何一段**带 conf ⇒ 走**合格段**
        口径（⇒ 绝不放宽）；**一段 conf 都没有** ⇒ 走旧口径。
        """
        with self._lock:
            row = self._table.get(str(spk))
            if row is None:
                return False
            runs = self._qualified_runs_locked(spk)
            # 🔴🔴🔳 **有没有任何一段带 conf**？（区分「新门槛口径」与「旧口径」）
            has_conf = any(
                self._seg_conf.get(int(s)) is not None
                for s in self._seg_spk if str(self._seg_spk.get(s)) == str(spk))
            if not runs:
                if has_conf:
                    return False        # 🔴 有 conf 却没合格段 ⇒ 不许登记
                # 🔴 旧口径兜底：没有任何 conf ⇒ 按累计干净时长判断
                need = (self._refine_s if row['voice'] == 'clone'
                        else self._min_s)
                if row['voice'] == 'clone' and row['refined']:
                    return False        # 已细化 ⇒ 不再更新（APP-040②）
                return row['dur_s'] >= need
            longest = max(r['dur_s'] for r in runs)
            if row['voice'] == 'clone':
                # 🔴 已登记 ⇒ 只在「有更长合格段」时允许升级
                prev = self._reg_run.get(str(spk)) or {}
                prev_dur = float(prev.get('dur_s') or 0.0)
                if not prev:
                    # 🔴🔴🔳 **没记录登记段**（老路径 / 单测直接 mark_embedded）
                    #   ⇒ 退回旧的「refined 一票否决」口径（保持旧行为逐字一致）
                    return not bool(row['refined'])
                return longest > prev_dur + 1e-6
            need = self._min_s
            return longest >= need

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
            # 🔴🔴🔳 APP-075(a)：一并清掉门槛用的状态（否则下一个会话
            #   会继承上一个会话的 conf / clean / 登记记录 ⇒ 串音）。
            self._seg_conf.clear()
            self._seg_clean.clear()
            del self._switch_points[:]
            self._reg_run.clear()
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


__all__ = ['SpeakerVoiceTable', 'MIN_S', 'REFINE_S', 'MAX_PER_SPK_S', 'SR',
           # 🔴🔴🔳 APP-075(a)：登记门槛常量（必须可被测试/STATUS 引用）
           'REG_CONF_MIN', 'REG_MIN_CONT_S', 'SWITCH_GUARD_S',
           'CONT_GAP_TOL_S']
