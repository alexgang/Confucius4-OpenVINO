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
CLIENT_DELAY_MIN = 6.0       # 11-09: panel delay range (popup.html 6-20 s)
CLIENT_DELAY_MAX = 20.0
SEG_MIN_SEC_CLONE = 1.5      # 11-08: clone mode - split at speaker-turn pauses from 1.5 s
SEG_MAX_FLOOR_SEC = 3.5      # 11-09: segment max follows D: min(SEG_MAX, max(floor, D - reserve))
SEG_MAX_RESERVE_SEC = 6.5    #   reserve = ASR + MT + TTS start under load
SEG_MAX_SEC = 8.0            # ★ EXT-027④：20.0 → 8.0（reviewer 要求 6–8 s）

# ★★★★★ EXT-034 ④：**首段单独限长**（缩短「起步」）。
#
# ## 为什么需要（reviewer EXT-034 ③ 的原话）
#   「开头静音主要归 EXT（首段切得太长、ASR 在整段结束后才定稿）」。
#   ASR 是**整段到齐才定稿**的（`ext/bridge.py` 的 `_dispatch_segment`
#   只在**整段音频完整到达**后才调 `_process_segment`）
#   ⇒ **首段越长、起步就越晚**：
#     起步耗时 ≈ 首段长度 + ASR + MT + TTS
#     实测（run 20261102_121431）：8.0 + 5.20 + 1.30 + 11.04 = **25.54 s**
#     ⇒ 而 D = 10 s ⇒ **结构上就赶不上** ⇒ 开头静音必然 ≫ D。
#
# ## 取值
#   3.5 s —— 落在 EXT-027④ 要求的「min 2–3 s」上沿之上一点，
#   给首段留够内容（太短会切碎语义），但把起步省下 ~4.5 s。
#   ⚠️ **只作用于会话的第一段**；其余段仍按 `SEG_MAX_SEC` 切
#     ⇒ 稳态吞吐不变，只改「起步」。
# ⚠️ 与 R2T2 原件的等价性：`plan_segments` 的 `first_segment_max_sec`
#   默认 None ⇒ **默认行为与 R2T2 逐位一致**（等价性自测仍成立）。
FIRST_SEGMENT_MAX_SEC = 3.5   # ★ EXT-034④：首段 ≤ 3.5 s（原来是 8 s）
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
ADAPT_LAG_FREE_SEC = 0.5   # 11-06: was 3.0 — lag was allowed to build up (user saw drift; dub/source=1.16)      # lag ≤ 此值 ⇒ 1.0×
ADAPT_LAG_HYST_SEC = 0.3   # 11-06: was 2.0      # 降速滞回门槛（lag < 此值才回 1.0×）
ADAPT_GAIN_PER_SEC = 0.15  # 11-08: 按滞后渐进 1.0×(≤0.5 s)→1.5×(≥3.8 s)；原 0.08  # 11-06: was 0.025 (only 1.18x at 10 s lag); now 1.12x@2s, 1.28x@4s    # 每秒滞后的加速系数
ADAPT_SPEED_MAX = 2.00        # 11-15 用户：上限 2.0×，以便快速追回（11-08 曾定 1.5×，原 1.30）
ADAPT_SPEED_MIN = 1.0
# 11-09 user: en->zh dubs are longer (median 1.17x the source) => minimum speed when target is Chinese
ZH_BASE_SPEED = float(os.environ.get("EXT_ZH_BASE_SPEED", "1.10"))
ADAPT_MAX_STEP = 0.20  # 11-08: 原 0.10         # 相邻句之间的最大速度变化（0.1×）
# ★ EXT-009 EXT 侧：**两者相乘后总倍率仍然不超过 1.30×**
#   （单句时长适配的 1.25× 与自适应加速相乘 ⇒ 必须再封顶一次）
ADAPT_TOTAL_RATE_MAX = 2.00   # 11-15 用户定 2.0×（11-08 为 1.5×，原 1.30）

# ── 目标语言码（引擎只认这 4 种）────────────────────────────────
# ★★ T-3：这份表与 `ext/engine_runtime.py` 的 LANG_TO_MT / LANG_TO_TTS
#   **键集合一致**（zh/en/ja/ko）。
#   为什么要放在 config：本模块被 bridge 在**任何**时候 import，
#   而 engine_runtime 会拉 numpy 与引擎路径（重）⇒ 轻量的语言表放 config。
#   ⚠️ 插件面板（popup）此前用的却是语言**全称**（Chinese/English/Japanese）
#     ⇒ 与引擎不匹配 ⇒ 面板上选语言实际不生效。插件侧已改为直接用这里的码。
LANG_CODES = ("zh", "en", "ja", "ko", "de", "fr", "es", "pt", "it", "ru")  # v0.4.4：扩到 Qwen3-TTS 的 10 种

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
    # v0.4.4：新增 6 种
    "de": "de", "german": "de", "deutsch": "de", "德语": "de", "德文": "de",
    "fr": "fr", "french": "fr", "français": "fr", "francais": "fr", "法语": "fr", "法文": "fr",
    "es": "es", "spanish": "es", "español": "es", "espanol": "es", "西班牙语": "es",
    "pt": "pt", "portuguese": "pt", "português": "pt", "portugues": "pt", "pt-br": "pt", "pt-pt": "pt", "葡萄牙语": "pt",
    "it": "it", "italian": "it", "italiano": "it", "意大利语": "it",
    "ru": "ru", "russian": "ru", "русский": "ru", "俄语": "ru", "俄文": "ru",
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

# ── v0.3.8 局域网模式（用户 2026-11-11：插件装在别的机器上，桥接跑在 A 上）────────
# EXT_BRIDGE_LAN=1 ⇒ 桥接 WS 和配对端点改为监听 0.0.0.0；默认仍只绑 127.0.0.1。
# 只接受 loopback 或 EXT_LAN_ALLOW（逗号分隔 CIDR）里的对端；不设则取本机每个网卡的真实网段（Get-NetIPAddress，取不到时退回 /24）。
# 同一时间只服务一个用户（按对端 IP 计）：别的 IP 连上来 ⇒ close(1013, "busy")。
LAN_MODE = os.environ.get("EXT_BRIDGE_LAN", "0").strip() == "1"
LAN_ALLOW = os.environ.get("EXT_LAN_ALLOW", "").strip()


def lan_allowed_nets():
    import ipaddress, socket
    nets = []
    if LAN_ALLOW:
        for c in LAN_ALLOW.split(","):
            c = c.strip()
            if c:
                nets.append(ipaddress.ip_network(c, strict=False))
        return nets
    try:
        import subprocess
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-NetIPAddress -AddressFamily IPv4 | % { $_.IPAddress + '/' + $_.PrefixLength }"],
                             capture_output=True, text=True, timeout=15).stdout.split()
        for c in out:
            if not c.startswith("127.") and not c.startswith("169.254."):
                nets.append(ipaddress.ip_network(c.strip(), strict=False))
    except Exception:
        nets = []
    if nets:
        return nets
    try:
        ips = socket.gethostbyname_ex(socket.gethostname())[2]
    except Exception:
        ips = []
    for ip in ips:
        if not ip.startswith("127."):
            nets.append(ipaddress.ip_network(ip + "/24", strict=False))
    return nets


_LAN_NETS = None


def peer_allowed(ip) -> bool:
    """loopback 永远放行；LAN 模式下再放行 LAN_ALLOW 网段；其它一律拒绝。"""
    import ipaddress
    global _LAN_NETS
    try:
        a = ipaddress.ip_address(str(ip).split("%")[0])
    except Exception:
        return False
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    if a.is_loopback:
        return True
    if not LAN_MODE:
        return False
    if _LAN_NETS is None:
        _LAN_NETS = lan_allowed_nets()
    return any(a in n for n in _LAN_NETS)
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
import os as _os
# 11-06 (reviewer): TTS on NPU cannot keep up in EXT (dub is ~1.27x the source and
#   NPU TTS runs ~1.2x real time under contention => backlog grows).  "AUTO" uses the
#   App's CUDA sidecar (faster-qwen3-tts on the NVIDIA GPU) when its env exists,
#   else NPU.  Override with env EXT_TTS_DEVICE=NPU|CUDA|AUTO.
DEVICE_TTS = (_os.environ.get("EXT_TTS_DEVICE", "AUTO").strip().upper() or "AUTO")           # Qwen3-TTS 全 NPU
# 11-08 reviewer (user test 3): ASR+MT+clone bypass kept GPU.0 ~98% busy => dub drifted to 90 s.
#   MT AUTO = NPU when TTS runs on the CUDA sidecar (NPU idle then; measured 0.81 s/sentence vs
#   0.55 s on GPU.0, identical output), else GPU.0.  Override: env EXT_MT_DEVICE=GPU.0|NPU|AUTO.
DEVICE_MT = (_os.environ.get("EXT_MT_DEVICE", "AUTO").strip().upper() or "AUTO")
if DEVICE_MT == "GPU":
    DEVICE_MT = "GPU.0"
# 11-08: a dub that would start more than this many seconds after its picture slot is not
#   played (subtitle only) - playing it would put the voice on the wrong picture.
# v0.4.9 (user 11-12: whole passages without dub): 6 -> 12 s; late dubs catch up at <=1.5x
# v0.4.15 (user 11-15): threshold 0 = never drop a dub (late dubs catch up at <=2.0x instead).
#   <= 0 disables all three drop points (late_drop / catch-up skip / skip_tts); > 0 restores them.
LATE_DROP_SEC = float(_os.environ.get("EXT_LATE_DROP_SEC", "0"))
# 11-08: clone - wait up to this long in the TTS stage for the sentence speaker label,
#   only while the sentence still has more than CLONE_LABEL_RESERVE_SEC of slack.
CLONE_LABEL_WAIT_SEC = float(os.environ.get("EXT_CLONE_LABEL_WAIT_SEC", "0"))   # 11-09: waits blocked the TTS thread 50 s / 6 min
# 11-08: CUDA sidecar wall time per second of dub audio (measured 0.6-0.8 live) - used to
#   predict whether a sentence can still make its slot before synthesizing it.
TTS_EST_RTF = 0.8
CLONE_LABEL_RESERVE_SEC = 9.0


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

# 11-08 用户：倍率不能是定值，按滞后严重程度从 1.0× 渐进到 1.5×。
#   rate = clamp(1 + (lag − ADAPT_LAG_FREE_SEC) × ADAPT_GAIN_PER_SEC, 1.0, 1.5)，相邻句变化 ≤ ADAPT_MAX_STEP
#   lag 取服务端模拟的 player 配音队列（不再乘时长适配的固定 1.25×）
