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

# ── 桥接服务 ──────────────────────────────────────────────────────
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8765
BRIDGE_TOKEN_FILE = "bridge_token.txt"
ALLOWED_ORIGIN_PREFIX = "chrome-extension://"

# ── 引擎设备摆放（EXT-001 总原则） ──────────────────────────────
DEVICE_ASR = "GPU.0"         # R2T2 INT8
DEVICE_MT = "GPU.0"          # Hy-MT2 INT8
DEVICE_TTS = "NPU"           # Qwen3-TTS 全 NPU
