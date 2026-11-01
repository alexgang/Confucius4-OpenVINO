"""config.py — EXT 模块全局常量

来源：EXT-001 架构 + EXT-002 修订。
只放常量与纯配置，不含逻辑，便于 reviewer 一眼核对。
"""
from __future__ import annotations

import os

# ── 音频 ──────────────────────────────────────────────────────────
SAMPLE_RATE = 16000          # ASR 输入采样率（EXT-001：AudioWorklet 重采样到 16 kHz 单声道 PCM16）
PCM_SAMPLE_WIDTH = 2         # bytes/sample（PCM16）
FRAME_MIN_MS = 20            # 插件上行帧长下限
FRAME_MAX_MS = 100           # 插件上行帧长上限

# ── 分段（EXT-002：一直用 R2T2 原有断句，不等 pyannote） ─────────
# ★★★★ EXT-027 ④：**切段参数下调**（断句方式不变，仍是 R2T2 的 VAD 断句）。
#
# ## 为什么必须下调（reviewer EXT-027 ④ 的根因分析）
#   旧值 `min=12 / max=20` ⇒ **一段最少 12 秒**。
#   而延迟 D = 10 s ⇒ 单是「等这一段说完」就已经超过 D
#   ⇒ 再加上 ASR+MT+TTS（TTS RTF ≈ 1.0）⇒ **按设计就不可能在 D 内就绪**。
#   实测：A 轮 `lagSec=12.70`、B 轮 `16.48`、`schedClamped=7`
#   （7 段**全部**到达太晚，被钳成「立即播」）⇒ 超出目标约 40 倍。
#
# ## 新值（reviewer 原文：「max_segment_sec 降到 6–8 s、min_segment_sec 降到 2–3 s」）
#   SEG_MAX_SEC = 8.0   （落在 6–8 s 区间的上沿 ⇒ 段落数不太多）
#   SEG_MIN_SEC = 3.0   （落在 2–3 s 区间的上沿）
#   ⇒ 一段最长 8 s ⇒ 等它说完（8 s）< D（10 s）⇒ **留出 2 s 给管线**。
#
# ⚠️ **断句方式没变**：仍是 R2T2 原有的 VAD 断句
#   （`ext/segmenter.py` 的 `plan_segments`，仍优先 import R2T2 原件），
#   **没有**用 pyannote 强制断句（EXT-002 仍然成立）。
# ⚠️ 这里的常量**同时**被 `ext/segmenter.py` 与 R2T2 等价性自测使用
#   ⇒ 改了它，两边**同时**用新参数 ⇒ 等价性自测依然成立。
SEG_MIN_SEC = 3.0            # ★ EXT-027④：12.0 → 3.0（reviewer 要求 2–3 s）
SEG_MAX_SEC = 8.0            # ★ EXT-027④：20.0 → 8.0（reviewer 要求 6–8 s）
VAD_SILENCE_DB = -40.0       # 复制 R2T2 find_silence_in_range 默认值
VAD_MIN_SILENCE_MS = 300
VAD_FRAME_MS = 30
VAD_HOP_MS = 10

# ── 说话人（EXT-002：旁路，不阻塞定稿） ─────────────────────────
SPK_CLEAN_SEC_REQUIRED = 3.0  # 攒够约 3 s 干净语音才算可用说话人
SPK_LATE_UPDATE_MAX_LAG_SEC = 2.0  # spk 最多允许比定稿晚多久；超出则标 stale
PRESET_VOICE = "A"           # 预设音色 A（兜底）

# ── 时长适配（EXT-001 B 节） ────────────────────────────────────
TTS_RATE_MAX = 1.25          # 保持音高变速上限；超出则顺延
TTS_RATE_MIN = 1.0

# ── 自适应加速播放（EXT-009；App 与插件**统一**参数） ────────────
# 统一参数（EXT-009 明文）：
#   lag   = 实际开播时刻 − 目标开播时刻
#           （插件的目标开播时刻 = t0 + t_start + D）
#   speed = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)
#     · lag ≤ 3 s  ⇒ 1.0×
#     · lag = 15 s  ⇒ 1.30×（上限）
#   滞回：降速时 lag < 2 s 才回到 1.0×（避免来回抖动）
#   按句变速：每句开播时定一次速度，句内不变
#   相邻句之间每次变化不超过 0.1×（听感更平滑）
ADAPT_LAG_FREE_SEC = 3.0      # lag ≤ 此值 ⇒ 1.0×
ADAPT_LAG_HYST_SEC = 2.0      # 降速滞回门槛（lag < 此值才回 1.0×）
ADAPT_GAIN_PER_SEC = 0.025    # 每秒滞后的加速系数
ADAPT_SPEED_MAX = 1.30        # 速度上限
ADAPT_SPEED_MIN = 1.0
ADAPT_MAX_STEP = 0.10         # 相邻句之间的最大速度变化（0.1×）
# ★ EXT-009 EXT 侧：**两者相乘后总倍率仍然不超过 1.30×**
#   （单句时长适配的 1.25× 与自适应加速相乘 ⇒ 必须再封顶一次）
ADAPT_TOTAL_RATE_MAX = 1.30   # 时长适配 × 自适应加速 的总倍率上限

# ── 目标语言码（引擎只认这 4 种）────────────────────────────────
# ★★ T-3：这份表与 `ext/engine_runtime.py` 的 LANG_TO_MT / LANG_TO_TTS
#   **键集合一致**（zh/en/ja/ko）。
#   为什么要放在 config：本模块被 bridge 在**任何**时候 import，
#   而 engine_runtime 会拉 numpy 与引擎路径（重）⇒ 轻量的语言表放 config。
#   ⚠️ 插件面板（popup）此前用的却是语言**全称**（Chinese/English/Japanese）
#     ⇒ 与引擎不匹配 ⇒ 面板上选语言实际不生效。插件侧已改为直接用这里的码。
LANG_CODES = ("zh", "en", "ja", "ko")

# ── ★★ EXT-024 G：语言**全称/别名** → 引擎码 的映射 ─────────────
# ★ 为什么服务端也要有这张表（用户 10-31 实测的现场证据）：
#   Edge 默认 profile 的 `chrome.storage` 里 `targetLang` 存的是
#   **`"Chinese"`**（旧版 popup 存的语言全称）。
#   插件侧后来（EXT-022 之后）改成了引擎码，但**存量配置不会自动迁移**
#   ⇒ 服务端只认 zh/en/ja/ko 时，"Chinese" 会落到 None
#   ⇒ 服务端用启动参数（默认 en）翻译 ⇒ **用户看到的是「没翻译成中文」**。
# ⇒ 所以服务端**独立地**也认全称（不依赖插件是否已升级）。
# ⚠️ 只认白名单里的值 ⇒ 未知字符串一律返回 None（**绝不臆造**）。
LANG_ALIASES = {
    "zh": "zh", "cn": "zh", "chinese": "zh", "中文": "zh", "简体中文": "zh",
    "en": "en", "english": "en", "英文": "en", "英语": "en",
    "ja": "ja", "jp": "ja", "japanese": "ja", "日文": "ja", "日语": "ja",
    "ko": "ko", "kr": "ko", "korean": "ko", "韩文": "ko", "韩语": "ko",
}


def normalize_lang_code(value) -> str | None:
    """把语言值（码或全称）归一成**引擎码**；认不出来返回 None。

    ★ 与插件侧 `player.js` / `popup.js` 的 `normalizeLang` **口径一致**
      （服务端这份是**独立实现**，这样插件没升级时也能正确翻译）。

    ⚠️ 认不出来 ⇒ 返回 **None**（不是默认 'zh'）——
      宁可「不知道」，也不要「猜一个」把用户译成别的语言。
    """
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    mapped = LANG_ALIASES.get(key)
    if mapped:
        return mapped
    return key if key in LANG_CODES else None

# ── 桥接服务 ──────────────────────────────────────────────────────
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8765
BRIDGE_TOKEN_FILE = "bridge_token.txt"
ALLOWED_ORIGIN_PREFIX = "chrome-extension://"

# ★★ EXT-012：配对 HTTP 端点（插件自动取 token ⇒ 用户不手动复制）
#   桥接端口 + 1（8765 ⇒ 8766）
PAIR_PORT = BRIDGE_PORT + 1

# ★★ T-5：逐帧「到达延迟」的**保留窗口**（条）。
#   为什么要有界（P2「30 分钟不崩、内存不持续增长」）：
#   上行帧率 ≈ 47 帧/秒（20–100 ms/帧）⇒ 30 分钟 ≈ 8.5 万条/会话；
#   旧实现**只追加、永不裁剪** ⇒ 内存随会话时长**线性增长**。
#   ⇒ 只保留最近 N 条明细；统计口径由**累计量**承担（不受窗口影响）。
#   2000 条 ≈ 42 秒的明细 ⇒ 足够 reviewer 核对「喂帧慢」，
#   内存占用恒定在几十 KB 量级。
FRAME_DELAY_HISTORY = 2000

# ★★ T-5：会话内「段级时刻表」的保留条数（`_seg_orig_end` / `_seg_ready`）。
#   这两个字典**只写不读**（实测无任何读取点）⇒ 原本每段永久留两个 key。
#   ⇒ 改成有界：只留最近 N 段（50 段 ≈ 10 分钟的段级信息）。
SEG_TIMING_HISTORY = 50

# ── 引擎设备摆放（EXT-001 总原则） ──────────────────────────────
DEVICE_ASR = "GPU.0"         # R2T2 INT8
DEVICE_MT = "GPU.0"          # Hy-MT2 INT8
DEVICE_TTS = "NPU"           # Qwen3-TTS 全 NPU


# ── 发行版模式（EXT-031③） ──────────────────────────────────────
def _release_mode() -> bool:
    """是不是**发行版**（发行包里调试/回退路径默认关闭）。

    ★ 判定顺序（**显式覆盖永远优先**）：
      ① 环境变量 `EXT_RELEASE`（`1/true/yes/on` ⇒ True；`0/false/no/off` ⇒ False）；
      ② 包根下的 `release.json`（`{"release": true}` ⇒ True）——
         发行包里带这个文件，开发目录里没有；
      ③ 默认 **False**（开发目录保持现状）。
    """
    v = (os.environ.get("EXT_RELEASE") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    try:
        import json as _json
        from .app_root import package_root
        p = os.path.join(package_root(), "release.json")
        with open(p, "r", encoding="utf-8") as f:
            return bool((_json.load(f) or {}).get("release"))
    except Exception:
        return False


#: **发行版模式**（EXT-031③）
RELEASE_MODE = _release_mode()

#: 允许的抓流方式白名单。
#: ★ 发行版 = **只有标签页音频路径**（EXT-027① `tabCapture`）
#:   ⇒ 整机 `getDisplayMedia` 回退**默认关闭**。
CAPTURE_MODES = (["tabCapture"] if RELEASE_MODE
                 else ["tabCapture", "getDisplayMedia"])
