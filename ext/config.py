"""config.py — EXT 模块全局常量

来源：EXT-001 架构 + EXT-002 修订。
只放常量与纯配置，不含逻辑，便于 reviewer 一眼核对。
"""
from __future__ import annotations

# ── 音频 ──────────────────────────────────────────────────────────
SAMPLE_RATE = 16000          # ASR 输入采样率（EXT-001：AudioWorklet 重采样到 16 kHz 单声道 PCM16）
PCM_SAMPLE_WIDTH = 2         # bytes/sample（PCM16）
FRAME_MIN_MS = 20            # 插件上行帧长下限
FRAME_MAX_MS = 100           # 插件上行帧长上限

# ── 分段（EXT-002：一直用 R2T2 原有断句，不等 pyannote） ─────────
SEG_MIN_SEC = 12.0           # 与 R2T2 seg_stream.py 'vad' 策略一致
SEG_MAX_SEC = 20.0
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

# ── 引擎设备摆放（EXT-001 总原则） ──────────────────────────────
DEVICE_ASR = "GPU.0"         # R2T2 INT8
DEVICE_MT = "GPU.0"          # Hy-MT2 INT8
DEVICE_TTS = "NPU"           # Qwen3-TTS 全 NPU
