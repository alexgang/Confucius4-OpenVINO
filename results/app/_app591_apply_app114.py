#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app591_apply_app114.py —— 应用 **APP-114 §1 + §2.1** 的产品代码改动（dev 树）。

🔴 **reviewer 原文（APP-114）**：
  §1「`time_stretch.SPEED_MAX` 和 `ZH_SPEED_MAX`：**2.00 → 1.70**；
      `speed_bounds_for_lang()` 改成中文 (1.10, 1.70)、其他语言 (1.00, 1.70)。
      `tts_worker.py` 里两处兜底 `(1.0, 2.00)` 改成 `(1.0, 1.70)`；
      `tts_service.py`、`device_config.py`、GUI 提示文字、README 里出现的
      2.0×/1.30× 上限说明一起改。」
  §1「**不改**：丢句阈值 `tts_late_drop_sec=0`；增益曲线（DEADZONE 3.0 / 0.025 每秒 /
      滞后回差 2.0 / 相邻句最大变化 0.1）；视频播放速度；中文下限 1.10。」
  §2.1「120 s 溢出丢弃和『一句不丢』冲突 ⇒ 只有 TTS worker 明确失败或退出时才清空队列，
      并计数、在 GUI 上显示；正常加载慢的时候**不按时间丢句**。」

🔴 **纪律**：
  · **精确字符串替换 + 唯一命中断言**（命中数必须 == 1，否则**零写入**）；
  · **CRLF 感知**（`tts_worker.py` / `tts_service.py` 是 CRLF，其余是 LF）；
  · 写盘走「临时文件 → `os.replace`」；
  · 写后**逐字复核**：把改动逆向还原 ⇒ 必须与原文件**逐字节相同**；
  · **不碰**增益曲线 / 丢句阈值 / 中文下限 / 视频（文件回放）速度。
"""
import os
import sys

DEV = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"

# ══════════════════════════════════════════════════════════════════
# time_stretch.py
# ══════════════════════════════════════════════════════════════════
TIME_STRETCH = [
    # ── 文件头 docstring ──
    ("""  ⇒ App 侧按句变速（1.0×–2.00×）来追赶语音滞后，
    **不改译文、不丢句、不回退到丢句**。
  🔴🔴🔳 **APP-113 §3（用户 11-16 决定「非中文目标语言的语速上限也从 1.30× 放到 2.0×」）**
    ⇒ **所有目标语言的上限统一为 2.00×**（中文原本就是 2.00）。""",
     """  ⇒ App 侧按句变速（1.0×–1.70×）来追赶语音滞后，
    **不改译文、不丢句、不回退到丢句**。
  🔴🔴🔳 **APP-113 §3（用户 11-16 决定「非中文目标语言的语速上限也从 1.30× 放到 2.0×」）**
    ⇒ **所有目标语言的上限统一为 2.00×**（中文原本就是 2.00）。
  🔴🔴🔳 **APP-114 §1（用户 11-16 22:20 决定「2.0 速度还是太快了听上去不舒服，
    最高速度调整到 1.7x」）**
    ⇒ **所有目标语言的上限统一为 1.70×**（中文 2.00→1.70；非中文 2.00→1.70）
    ⇒ **增益曲线不变**（DEADZONE 3.0 / 0.025 每秒 / 滞回 2.0 / 相邻句 ≤0.1）。"""),
    # ── APP-042 统一参数 ──
    ("""  - `speed = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 2.00)`
    ⇒ lag ≤ 3 s 时 1.0×（中文目标 1.10×）；
      ⇒ **APP-113 §3**：上限 **2.00×**（非中文 1.30→2.00，中文原本 2.00），
      ⇒ 非中文要摸到上限需 lag ≥ 43 s，中文需 lag ≥ 39 s""",
     """  - `speed = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.70)`
    ⇒ lag ≤ 3 s 时 1.0×（中文目标 1.10×）；
      ⇒ **APP-114 §1**：上限 **1.70×**（中文 2.00→1.70；非中文 2.00→1.70），
      ⇒ 非中文要摸到上限需 lag ≥ 31 s，中文需 lag ≥ 27 s"""),
    # ── LAG_FULL_SPEED_S 注释 ──
    ("#: 超过这个滞后（秒）⇒ 达到倍率上限（**APP-113 §3：上限统一 2.00×**）",
     "#: 超过这个滞后（秒）⇒ 达到倍率上限（**APP-114 §1：上限统一 1.70×**）"),
    # ── SPEED_MAX 注释 + 常量 ──
    ("""#: 🔴🔴🔳 **APP-113 §3**（用户 11-16 决定「非中文目标语言的语速上限也从 1.30× 放到 2.0×」）
#:   ⇒ `SPEED_MAX` **1.30 → 2.00**（11-16 取代 10-29 的 1.30× 上限）
#:   ⚠️ **增益曲线不变**（`SPEED_PER_LAG_S` / `LAG_DEADZONE_S` / `LAG_HYSTERESIS_S`
#:     / `MAX_STEP_CHANGE` 全部照旧）⇒ 视频不变速的规则也不变。
#:   ⇒ 非中文目标（下限 1.00）要摸到 2.00× 需 lag ≥ 3 + 100×0.025⁻¹ = **43 s**
#:     （中文目标下限 1.10 ⇒ lag ≥ **39 s**）。
SPEED_MIN = 1.0
SPEED_MAX = 2.00""",
     """#: 🔴🔴🔳 **APP-113 §3**（用户 11-16 决定「非中文目标语言的语速上限也从 1.30× 放到 2.0×」）
#:   ⇒ `SPEED_MAX` **1.30 → 2.00**（11-16 取代 10-29 的 1.30× 上限）
#: 🔴🔴🔳 **APP-114 §1**（用户 11-16 22:20 决定「2.0 速度还是太快了听上去不舒服，
#:   最高速度调整到 1.7x」）⇒ `SPEED_MAX` **2.00 → 1.70**
#:   （取代 APP-113 §3 的 2.00；**所有目标语言**统一 1.70）
#:   ⚠️ **增益曲线不变**（`SPEED_PER_LAG_S` / `LAG_DEADZONE_S` / `LAG_HYSTERESIS_S`
#:     / `MAX_STEP_CHANGE` 全部照旧）⇒ 视频不变速的规则也不变。
#:   ⇒ 非中文目标（下限 1.00）要摸到 1.70× 需 lag ≥ 3 + 70×0.025⁻¹ = **31 s**
#:     （中文目标下限 1.10 ⇒ lag ≥ **27 s**）。
SPEED_MIN = 1.0
SPEED_MAX = 1.70"""),
    # ── ZH_SPEED_MAX 注释 + 常量 ──
    ("""#   🔴🔴🔳 **APP-113 §3（11-16 用户决定）**：**非中文目标的上限也放到 2.00×**
#     ⇒ 非中文：下限 1.00（不变）／**上限 2.00**（原 1.30）；
#     ⇒ 中文：下限 1.10／上限 2.00 ⇒ **两种目标的「上限」现已一致**。
ZH_SPEED_MIN = 1.10
ZH_SPEED_MAX = 2.00""",
     """#   🔴🔴🔳 **APP-113 §3（11-16 用户决定）**：**非中文目标的上限也放到 2.00×**
#     ⇒ 非中文：下限 1.00（不变）／**上限 2.00**（原 1.30）；
#     ⇒ 中文：下限 1.10／上限 2.00 ⇒ **两种目标的「上限」现已一致**。
# 🔴🔴🔳 **APP-114 §1（11-16 22:20 用户决定「最高速度调整到 1.7x」）**：
#     ⇒ **中文 2.00 → 1.70**；非中文同为 **1.70** ⇒ 两种目标仍一致。
#     ⚠️ **中文下限 1.10 不变**（reviewer 明文「中文下限 1.10」不动）。
ZH_SPEED_MIN = 1.10
ZH_SPEED_MAX = 1.70"""),
    # ── speed_bounds_for_lang docstring ──
    ("""    - 中文目标 ⇒ `(ZH_SPEED_MIN=1.10, ZH_SPEED_MAX=2.00)`
    - 其他目标 ⇒ `(SPEED_MIN=1.0, SPEED_MAX=2.00)`
      🔴🔴🔳 **APP-113 §3**（11-16 用户决定）：**上限对两种目标统一为 2.00×**
      （非中文原本 1.30 ⇒ **只放开上限，下限 1.00 不变**；增益曲线不变）。""",
     """    - 中文目标 ⇒ `(ZH_SPEED_MIN=1.10, ZH_SPEED_MAX=1.70)`
    - 其他目标 ⇒ `(SPEED_MIN=1.0, SPEED_MAX=1.70)`
      🔴🔴🔳 **APP-114 §1**（11-16 22:20 用户决定）：**上限对两种目标统一为 1.70×**
      （中文 2.00→1.70；非中文 2.00→1.70；**下限不变**：中文 1.10 / 非中文 1.00；
      增益曲线不变）。"""),
    # ── speed_bounds_for_lang 可配键说明 ──
    ("    - `tts_speed_max_zh`（默认 **2.00**，APP-111 §1）",
     "    - `tts_speed_max_zh`（默认 **1.70**，APP-114 §1；原 APP-111 §1 的 2.00）"),
    # ── speed_for_lag docstring ──
    ("""        中文目标 ⇒ 下限 `ZH_SPEED_MIN`(1.10) / 上限 `ZH_SPEED_MAX`(2.00, APP-111 §1)；
        其他目标 ⇒ 下限 1.0（不变）/ 上限 **2.00**（APP-113 §3，原 1.30）。""",
     """        中文目标 ⇒ 下限 `ZH_SPEED_MIN`(1.10) / 上限 `ZH_SPEED_MAX`(1.70, APP-114 §1)；
        其他目标 ⇒ 下限 1.0（不变）/ 上限 **1.70**（APP-114 §1，原 2.00）。"""),
]

# ══════════════════════════════════════════════════════════════════
# tts_worker.py
# ══════════════════════════════════════════════════════════════════
TTS_WORKER = [
    ("""                #   ⇒ 中文目标：下限 1.10×、上限 2.00×（APP-111 §1）
                #   ⇒ 其他目标：下限 1.00×、**上限 2.00×（APP-113 §3）**""",
     """                #   ⇒ 中文目标：下限 1.10×、上限 1.70×（APP-114 §1）
                #   ⇒ 其他目标：下限 1.00×、**上限 1.70×（APP-114 §1）**"""),
    ("""        #   ⚠️ **用户定的 2.00× 上限**（APP-113 §3：两种目标语言一致；
        #     `_speed_cap_by_rtf` 里已封顶）。""",
     """        #   ⚠️ **用户定的 1.70× 上限**（APP-114 §1：两种目标语言一致；
        #     `_speed_cap_by_rtf` 里已封顶）。"""),
    ("""        - `tts_speed_max_zh`（默认 **2.00**，APP-111 §1）""",
     """        - `tts_speed_max_zh`（默认 **1.70**，APP-114 §1）"""),
    ("""            # 🔴🔴🔳 APP-113 §3：**上限对所有目标语言统一 2.00×**
            #   （原非中文 1.30；`time_stretch` 不可用时的兜底也要一致）
            return (1.0, 2.00)""",
     """            # 🔴🔴🔳 APP-114 §1：**上限对所有目标语言统一 1.70×**
            #   （原 2.00；`time_stretch` 不可用时的兜底也要一致）
            return (1.0, 1.70)"""),
    ("""        - 上限随语言变（🔴🔴🔳 **APP-113 §3：两种目标语言的上限现已统一为 2.00×**，
          中文 2.00〔APP-111 §1〕／非中文 2.00〔APP-113 §3，原 1.30〕）；""",
     """        - 上限随语言变（🔴🔴🔳 **APP-114 §1：两种目标语言的上限现已统一为 1.70×**，
          中文 1.70〔原 2.00〕／非中文 1.70〔原 2.00〕）；"""),
    ("""            _lo, _hi = 1.0, 2.00
        cap = 1.0 / r
        if cap > _hi:                 # 用户定的上限（**2.00×〔APP-113 §3〕两种目标一致**）""",
     """            _lo, _hi = 1.0, 1.70
        cap = 1.0 / r
        if cap > _hi:                 # 用户定的上限（**1.70×〔APP-114 §1〕两种目标一致**）"""),
    ("""                #   ⇒ 中文目标 1.10–2.00×（APP-111 §1；取代 10-29 的 1.30× 上限）
                #   ⇒ 其他目标 1.00–**2.00**×（APP-113 §3：**上限也放开**，
                #     下限 1.00 不变）""",
     """                #   ⇒ 中文目标 1.10–1.70×（APP-114 §1；取代 APP-111 §1 的 2.00×）
                #   ⇒ 其他目标 1.00–**1.70**×（APP-114 §1：**上限统一 1.70×**，
                #     下限 1.00 不变）"""),
    ("""                except Exception:
                    _lo, _hi = 1.0, 2.00
                if speed < _lo:""",
     """                except Exception:
                    _lo, _hi = 1.0, 1.70
                if speed < _lo:"""),
]

# ══════════════════════════════════════════════════════════════════
# tts_service.py
# ══════════════════════════════════════════════════════════════════
TTS_SERVICE = [
    ("""                #   ⇒ 中文目标 1.10–2.00×（APP-111 §1），其他 1.00–**2.00**×
                #     （APP-113 §3：**上限也放开**，下限不变）。""",
     """                #   ⇒ 中文目标 1.10–1.70×（APP-114 §1），其他 1.00–**1.70**×
                #     （APP-114 §1：**上限统一 1.70×**，下限不变）。"""),
]

# ══════════════════════════════════════════════════════════════════
# device_config.py
# ══════════════════════════════════════════════════════════════════
DEVICE_CONFIG = [
    ("""#   `tts_speed_max_zh`  中文目标倍率**上限**（默认 **2.00**）""",
     """#   `tts_speed_max_zh`  中文目标倍率**上限**（默认 **1.70**）"""),
    ("""#   ⚠️ **非中文目标**的 1.00–2.00× 口径（**APP-113 §3**：11-16 用户决定
#     「非中文目标语言的语速上限也从 1.30× 放到 2.0×」⇒ 上限与中文一致；
#     下限仍是 1.00）⇒ 该上限是 `time_stretch.SPEED_MAX` 的**模块常量**，""",
     """#   ⚠️ **非中文目标**的 1.00–1.70× 口径（**APP-114 §1**：11-16 22:20 用户决定
#     「最高速度调整到 1.7x」⇒ 上限与中文一致；下限仍是 1.00）
#     ⇒ 该上限是 `time_stretch.SPEED_MAX` 的**模块常量**，"""),
    ("""    # 🔴🔴🔳 APP-111 §1（用户 11-15 决定「TTS 语速上限改到 2.0x」）：
    #   中文目标倍率**上限 1.50 → 2.00**（11-15 取代 APP-090②c / APP-091② 的 1.50）。
    #   ⚠️ **非中文目标**的 1.00–2.00× 口径（**APP-113 §3**：11-16 用户决定
    #     「非中文目标语言的语速上限也从 1.30× 放到 2.0×」）⇒ **不单独配键**
    #     （上限取 `time_stretch.SPEED_MAX` = 2.00；下限仍是 1.00）。
    'tts_speed_max_zh': 2.00,     # 中文目标倍率上限（APP-111 §1；原 APP-090②c/APP-091② 的 1.50）""",
     """    # 🔴🔴🔳 APP-111 §1（用户 11-15 决定「TTS 语速上限改到 2.0x」）：
    #   中文目标倍率**上限 1.50 → 2.00**（11-15 取代 APP-090②c / APP-091② 的 1.50）。
    # 🔴🔴🔳 **APP-114 §1**（用户 11-16 22:20 决定「2.0 速度还是太快了听上去不舒服，
    #   最高速度调整到 1.7x」）：中文目标倍率**上限 2.00 → 1.70**。
    #   ⚠️ **非中文目标**的 1.00–1.70× 口径（**APP-114 §1**）⇒ **不单独配键**
    #     （上限取 `time_stretch.SPEED_MAX` = 1.70；下限仍是 1.00）。
    'tts_speed_max_zh': 1.70,     # 中文目标倍率上限（APP-114 §1；原 APP-111 §1 的 2.00）"""),
]

# ══════════════════════════════════════════════════════════════════
# live_caption_app.py —— §1 语速说明 + §2.1 队列语义
# ══════════════════════════════════════════════════════════════════
LIVE_APP = [
    # ── §2.1：队列语义（模块级说明）──
    ("""#     滞后靠自适应语速（最高 2.0×）追回。不丢句。」""",
     """#     滞后靠自适应语速（最高 1.7×）追回。不丢句。」"""),
    ("""#   「队列要有上限保护，防止 TTS 一直起不来时无限增长：例如超过 120 s 仍未就绪，
#     才按最旧优先丢弃并计数（`n_drop_not_ready_overflow`），并在 GUI/日志明示。
#     正常冷启动（≤60 s）必须一句不丢。」""",
     """#   「队列要有上限保护，防止 TTS 一直起不来时无限增长：例如超过 120 s 仍未就绪，
#     才按最旧优先丢弃并计数（`n_drop_not_ready_overflow`），并在 GUI/日志明示。
#     正常冷启动（≤60 s）必须一句不丢。」
# 🔴🔴🔳 **APP-114 §2.1 取代上面这句**（reviewer 裁定）：
#   「120 s 溢出丢弃」与「一句不丢」**冲突** —— §212 冷启动臂实测
#   **TTS 就绪用了 120.1 s** ⇒ 旧阈值 120 s **正好压在线上**
#   ⇒ B 机或更冷的机器上**必然丢句**。
#   ⇒ **取消「按时间丢弃」**（`_TTS_QUEUE_OVERFLOW_S = None`）
#   ⇒ 只在「**TTS worker 明确失败或退出**」时清空队列（计数 + GUI 明示）
#   ⇒ **正常加载慢的时候不按时间丢句**。"""),
    # ── §2.1：常量 ──
    ("""#: 🔴 APP-113 §1：**队列溢出丢弃阈值**（秒）
#:   ⇒ 「超过 120 s 仍未就绪」⇒ **按最旧优先丢弃**并计数。
#:   ⚠️ 正常冷启动（≤60 s）**一句不丢**（sp4 实测 TTS 就绪 ≈ 88 s ⇒ 也不丢）。
_TTS_QUEUE_OVERFLOW_S = 120.0""",
     """#: 🔴🔴🔳 APP-114 §2.1：**「按时间丢弃」的阈值已取消**（`None` = **不设时间上限**）
#:   ⇒ reviewer 原话：「正常加载慢的时候**不按时间丢句**；
#:     只有 TTS worker 明确失败或退出时才清空队列，并计数、在 GUI 上显示」。
#:   ⚠️ **实测依据**：§212 冷启动臂 **TTS 就绪 120.1 s** ⇒ 旧阈值 120 s 压线。
#:   ⇒ **唯一的丢弃路径** = `clear_on_worker_failure()`（worker 失败/退出）。
#:   ⚠️ 若将来要重新设时间上限，必须 **≫ 实测最坏冷启动**（建议 ≥600 s）。
_TTS_QUEUE_OVERFLOW_S = None"""),
    # ── §2.1：TtsReadyQueue.__init__（overflow_s 可为 None）──
    ("""        self._q = []                       # [(入队墙钟, 提交动作, meta)]
        self._overflow_s = float(overflow_s)""",
     """        self._q = []                       # [(入队墙钟, 提交动作, meta)]
        # 🔴 APP-114 §2.1：`None` ⇒ **不按时间丢弃**（默认 = `_TTS_QUEUE_OVERFLOW_S`）
        self._overflow_s = (None if overflow_s is None else float(overflow_s))"""),
    ("""        self.n_queued_before_ready = 0     # 就绪前入队句数
        self.n_drop_not_ready_overflow = 0  # 溢出丢弃句数""",
     """        self.n_queued_before_ready = 0     # 就绪前入队句数
        self.n_drop_not_ready_overflow = 0  # 溢出丢弃句数（APP-114 §2.1 后恒为 0）
        self.n_drop_worker_failed = 0      # worker 失败/退出 ⇒ 清空的句数"""),
    # ── §2.1：enforce_overflow（不再按时间丢）──
    ("""    def enforce_overflow(self):
        \"\"\"🔴 超过 `overflow_s`（默认 120 s）仍未就绪 ⇒ **按最旧优先丢弃**。

        ⇒ 返回被丢弃的 meta 列表（供调用方记账/提示）。
        \"\"\"""",
     """    def enforce_overflow(self):
        \"\"\"🔴🔴🔳 APP-114 §2.1：**「按时间丢弃」已取消** ⇒ **不丢句**。

        🔴 **reviewer 原话**（APP-114 §2.1）：
          「120 s 溢出丢弃和『一句不丢』冲突 …… 改成：**只有 TTS worker 明确失败
            或退出时才清空队列**，并计数、在 GUI 上显示；正常加载慢的时候
            **不按时间丢句**。」

        ⚠️ **实测依据**：§212 冷启动臂 **TTS 就绪 120.1 s** ⇒ 旧阈值 120 s
          **压线** ⇒ B 机 / 更冷的机器上必然丢句。

        ⚠️ **本方法保留**（调用点不变）⇒ 旧阈值不再生效；
          若将来要重新设时间上限，必须 **≫ 实测最坏冷启动**（建议 ≥600 s）。
        \"\"\""""),
    # ── §2.1：新增 clear_on_worker_failure ──
    ("""    # -- 就绪 / 积压清空 -------------------------------------------------
    def poll(self, ready, lag_s=None, ready_at=None, play_lag_s=None,""",
     """    # -- worker 失败/退出 ⇒ 清空队列（APP-114 §2.1）---------------------
    def clear_on_worker_failure(self, reason=''):
        \"\"\"🔴🔴🔳 APP-114 §2.1：**TTS worker 明确失败或退出** ⇒ 清空排队句。

        ⇒ 这是**唯一**允许丢弃排队句的路径（正常慢加载**一律不丢**）；
        ⇒ 丢弃句数计入 `n_drop_worker_failed`（GUI 明示 + 日志）。
        \"\"\"
        with self._lock:
            n = len(self._q)
            self._q = []
            if n:
                self.n_drop_worker_failed += n
        if self._on_log:
            self._on_log(
                '[TTS] 🔴 TTS worker 失败/退出（%s）⇒ **清空排队 %d 句**'
                '（累计 worker 失败丢弃 %d 句；APP-114 §2.1：正常慢加载'
                '不按时间丢句，只有 worker 失败/退出才清空）'
                % (reason or '未知原因', n, self.n_drop_worker_failed))
        return n

    # -- 就绪 / 积压清空 -------------------------------------------------
    def poll(self, ready, lag_s=None, ready_at=None, play_lag_s=None,"""),
    # ── §2.1：stats() 增加字段 ──
    ("""                'n_drop_not_ready_overflow': self.n_drop_not_ready_overflow,
                'n_flushed': self.n_flushed,""",
     """                'n_drop_not_ready_overflow': self.n_drop_not_ready_overflow,
                'n_drop_worker_failed': self.n_drop_worker_failed,
                'n_flushed': self.n_flushed,"""),
    ("""                'overflow_s': self._overflow_s,
                'backlog_clear_threshold_s': _TTS_BACKLOG_CLEAR_S,""",
     """                'overflow_s': self._overflow_s,
                'overflow_enabled': (self._overflow_s is not None),
                'backlog_clear_threshold_s': _TTS_BACKLOG_CLEAR_S,"""),
    # ── GUI：计数器注释 ──
    ("""        #   ⇒ 本计数器现在只统计「**溢出丢弃**」（队列上限保护触发时）；
        #   正常冷启动（≤120 s）它恒为 0 ⇒ **一句不丢**。""",
     """        #   ⇒ 本计数器现在统计「**worker 失败/退出清空的句数**」
        #     （APP-114 §2.1：唯一允许丢弃的路径）；正常慢加载 ⇒ 恒为 0
        #     ⇒ **一句不丢**。"""),
    # ── GUI：提交点注释 ──
    ("""                        #     ⇒ **不丢句**；滞后靠自适应语速（上限 2.0×）追回。
                        #   ⚠️ 队列有**上限保护**：120 s 仍未就绪 ⇒ 按最旧优先
                        #     丢弃并计数 `n_drop_not_ready_overflow`。""",
     """                        #     ⇒ **不丢句**；滞后靠自适应语速（上限 1.7×）追回。
                        #   🔴 APP-114 §2.1：**不再按时间丢弃** ⇒ 正常慢加载
                        #     一句不丢；只有 **TTS worker 明确失败/退出**才清空
                        #     队列（计数 `n_drop_worker_failed` + GUI 明示）。"""),
    # ── GUI：状态条文字 ──
    ("""                _qtxt = '%d（就绪前排队 %d / 溢出丢弃 %d）' % (
                    n_q, _qst.get('n_queued_before_ready') or 0,
                    _qst.get('n_drop_not_ready_overflow') or 0)""",
     """                # 🔴 APP-114 §2.1：唯一允许丢弃的路径 = worker 失败/退出
                _qtxt = '%d（就绪前排队 %d / worker失败丢弃 %d）' % (
                    n_q, _qst.get('n_queued_before_ready') or 0,
                    _qst.get('n_drop_worker_failed') or 0)"""),
    # ── GUI：worker 失败 ⇒ 清空队列 ──
    ("""            self.var_status.set('语音输出加载失败（不影响字幕与翻译）')
            self._ui_log(f'[tts] worker error: {raw!r}')""",
     """            self.var_status.set('语音输出加载失败（不影响字幕与翻译）')
            self._ui_log(f'[tts] worker error: {raw!r}')
            # 🔴🔴🔳 APP-114 §2.1：worker **明确失败/退出** ⇒ 清空排队句
            #   （**唯一**允许丢弃排队句的路径；计数 + GUI 明示）
            try:
                _q = getattr(self, '_tts_pending_q', None)
                if _q is not None:
                    _q.clear_on_worker_failure(raw or 'worker error')
            except Exception:
                pass"""),
    # ── GUI：_flush_tts_pending docstring ──
    ("""        ⚠️ **不丢句**：队列里的句子一句都不跳（除非触发 120 s 溢出保护）。""",
     """        ⚠️ **不丢句**：队列里的句子一句都不跳（**只有 TTS worker 明确失败/退出**
        才清空 ⇒ APP-114 §2.1）。"""),
    # ── CLI：计数器注释 ──
    ("""    #   ⇒ 现在**唯一的丢弃来源**是队列溢出保护
    #     （`_pending_q.n_drop_not_ready_overflow`）
    #   ⇒ 正常冷启动（≤120 s）它恒为 0 ⇒ **一句不丢**。""",
     """    #   ⇒ 现在**唯一的丢弃来源**是「TTS worker 明确失败/退出」
    #     （`_pending_q.n_drop_worker_failed`；APP-114 §2.1）
    #   ⇒ **正常加载慢一律不丢句**（不再按时间丢弃）。"""),
    # ── CLI：主循环 ⇒ worker 失败清空队列 ──
    ("""            # 🔴🔴🔳 APP-113 §1：TTS 就绪 ⇒ **补发**就绪前排队的句子（第一拍就补）
            _cli_flush_pending()""",
     """            # 🔴🔴🔳 APP-113 §1：TTS 就绪 ⇒ **补发**就绪前排队的句子（第一拍就补）
            _cli_flush_pending()
            # 🔴🔴🔳 APP-114 §2.1：TTS worker **明确失败/退出** ⇒ 清空排队句
            #   （**唯一**允许丢弃排队句的路径；正常慢加载不按时间丢句）
            if getattr(tts, 'state', '') == 'error':
                _pending_q.clear_on_worker_failure(
                    getattr(tts, 'err', '') or 'worker error')"""),
    # ── CLI：结算行加「worker失败丢弃」字段 ──
    ("""            print('[APP-113] 就绪前排队=%d 溢出丢弃=%d 已补发=%d ｜ '""",
     """            print('[APP-113] 就绪前排队=%d 溢出丢弃=%d 已补发=%d ｜ '
                  'worker失败丢弃=%d ｜ '"""),
    ("""                     _qs.get('n_drop_not_ready_overflow'),
                     _qs.get('n_flushed'),""",
     """                     _qs.get('n_drop_not_ready_overflow'),
                     _qs.get('n_flushed'),
                     _qs.get('n_drop_worker_failed') or 0,"""),
]

PLAN = {
    'time_stretch.py': TIME_STRETCH,
    'tts_worker.py': TTS_WORKER,
    'tts_service.py': TTS_SERVICE,
    'device_config.py': DEVICE_CONFIG,
    'live_caption_app.py': LIVE_APP,
}


def apply_one(path, patches):
    """精确替换 + 唯一命中断言 + 还原式复核。"""
    with open(path, 'rb') as f:
        orig = f.read()
    crlf = b'\r\n' in orig
    text = orig.decode('utf-8')
    out = text
    for old, new in patches:
        o = old.replace('\n', '\r\n') if crlf else old
        n = new.replace('\n', '\r\n') if crlf else new
        cnt = out.count(o)
        if cnt != 1:
            raise SystemExit('FAIL %s：命中数=%d（要求 1）\n--- 锚点 ---\n%s'
                             % (os.path.basename(path), cnt, old[:200]))
        out = out.replace(o, n, 1)
    # ── 还原式复核：逆向还原 ⇒ 必须与原文件逐字节相同 ──
    back = out
    for old, new in reversed(patches):
        o = old.replace('\n', '\r\n') if crlf else old
        n = new.replace('\n', '\r\n') if crlf else new
        back = back.replace(n, o, 1)
    if back != text:
        raise SystemExit('FAIL %s：还原式复核不一致 ⇒ 零写入' % os.path.basename(path))
    # ── 写盘（临时文件 → os.replace）──
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(out.encode('utf-8'))
    os.replace(tmp, path)
    with open(path, 'rb') as f:
        after = f.read()
    print('OK  %-22s patches=%2d  bytes %d -> %d  crlf=%s'
          % (os.path.basename(path), len(patches), len(orig), len(after), crlf))
    return len(orig), len(after)


def main():
    print('=== APP-114 §1/§2.1 产品代码改动（dev 树）===')
    for fn, patches in PLAN.items():
        apply_one(os.path.join(DEV, fn), patches)
    # ── 语法自检 ──
    import ast
    for fn in PLAN:
        p = os.path.join(DEV, fn)
        with open(p, 'rb') as f:
            ast.parse(f.read().decode('utf-8'), filename=fn)
        print('AST OK', fn)
    print('ALL DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
