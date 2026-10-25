r"""live_caption_app.py — Confucius4-R2T2 实时字幕（多后端对比测试应用）

采集音频（16 kHz 单声道），流式识别，并把字幕实时显示在屏幕上。
可在界面里切换推理后端：

  Intel GPU · INT8     集显，编码器与解码器都是 INT8
  Intel GPU · INT4     集显，编码器与解码器都是 INT4
  Intel NPU · INT8     编码器与解码器都在 NPU（inputs_embeds 版解码器，INT8_SYM）
  Intel NPU · INT4     同上，解码器 INT4（AWQ + 20% INT8 混合，实验配置，WER 显著变差）
  NVIDIA GPU · CUDA    audio.cpp + GGUF（Q8_0 / Q4_K），独显

## 音频输入（三种，见 audio_source.py）

  1. **麦克风**   —— 系统默认或指定输入设备。
  2. **系统声音** —— WASAPI loopback，采集「正在播放的输出设备」的混音。
                  给会议 / 视频 / 任何本机播放的声音做字幕时用它：
                  比麦克风干净，不会把房间噪音和本地声音一起录进去。
  3. **音频文件** —— 用户上传的音频文件，按实时速度回放（也支持全速跑批）。

OpenVINO 后端复用仓库里的流式实现（streaming_asr + seg_stream，640 ms 分块，
LSP 前缀回滚，自适应生成预算）；分段规则与 mic_asr_app.py 相同：
段长 ≥12 s 且最近 3 s 内出现 ≥300 ms 静音就切段，最长 20 s 硬切。
CUDA 后端每段起一个 audiocpp_cli 流式进程（stdin 喂 PCM，stdout 读 partial_text），
并提前预热下一段要用的进程，切段时无需等模型加载。

用法:
  python live_caption_app.py                         # GUI
  python live_caption_app.py --engine npu_int8       # 启动时预选后端
  python live_caption_app.py --cli --engine gpu_int8 --file x.wav --max-seconds 60
  python live_caption_app.py --cli --source system    # 采集系统声音
  python live_caption_app.py --list-devices
  python live_caption_app.py --check                # 环境检查（Diagnose.bat）

实时翻译（C-102 起翻译模型为 Hy-MT2-1.8B）：
  python live_caption_app.py --cli --engine gpu_int8 --file x.wav --translate zh
  python live_caption_app.py --translate en --mt-device NPU

ASR 与翻译的设备/量化各自独立选择（C-098 阶段 B，实测结论见 hy_bench\STATUS_hy.md）：
  --engine   决定 ASR 跑哪张卡/哪种量化；--mt-engine 决定翻译跑哪张卡/哪种量化。
  python live_caption_app.py --engine npu_int8  --translate zh --mt-engine gpu_int4cw
  python live_caption_app.py --engine gpu_int8  --translate zh --mt-engine npu_int4cw
  # 翻译后端：auto(默认) | gpu_int4cw | gpu_int8cw | npu_int4cw | npu_int8cw
  #   （下拉里只列出本机真实存在的模型；旧的 int4_asym 只在包内 models/ 有副本时才出现）
"""
import argparse
import gc
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime

os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import numpy as np

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
# 包根目录：代码目录的上一级。模型、README 都在这一层。
# 开发版：<repo>/live_caption/*.py + <repo>/models/
# 客户包：<pkg>/app/*.py        + <pkg>/models/
PKG_ROOT = os.path.dirname(APP_DIR)

from translator import (MT_DEFAULT, MT_ALL_CANDIDATES, MT_ENGINES, TARGETS,
                        TARGET_LABELS, TranslationService, mt_available,
                        prewarm_transformers, split_sentences)
import device_config
import audio_source
from audio_source import (BLOCK_MS, SR, default_output_device_id,
                          list_input_devices, list_output_devices, make_source,
                          resample_to_16k, soundcard_available)

CHUNK_SEC = 0.64

# 规则1 的最短段门槛（计时器兜底）：段长 ≥ MIN_SEG_SEC 且最近 SIL_LOOKBACK_SEC
# 内有 ≥300ms 静音就切段。
#
# ★ C-109：由 12.0s 降到 **6.0s**（用户决策）。
#   背景（C-107/C-108）：12s 门槛是「等满 12 秒才定稿」的计时器兜底，
#   它切出了 94.2% 的段 —— 意味着引擎基本没在做「按停顿切」。
#   C-108 已把规则2 的 hangover 降到 0.8s（Qwen3 默认值），规则2 切点
#   29/29 全安全；但素材是连续演讲（≥800ms 停顿仅 1.9 处/分钟），
#   规则2 能切的点有限，规则1 仍是主力 → 降它的门槛才能真正提早白字。
#
#   离线实测（61 分钟真实演讲，含空段守卫）：
#     门槛 12s → 300 段，段长 p50=12.16s，白字提前中位 0.64s
#     门槛  6s → 532 段，段长 p50= 6.40s，白字提前中位 5.12s
#     门槛  8s → 415 段，段长 p50= 8.32s，白字提前中位 3.84s
#   规则2 切点 23/23 全安全、空段 0、短段(<2s) 仅 2 段。
#
#   代价：段数 300 → 532（+77%），每次切段都要跑一次收尾解码
#   （实测 428ms/次：编码 68 + prefill 108 + 解码 252），
#   61 分钟累计收尾开销 128s → 228s（+100s）。
MIN_SEG_SEC = float(os.environ.get('LIVECAP_MIN_SEG_SEC', '6.0'))
MAX_SEG_SEC = 20.0
SIL_LOOKBACK_SEC = 3.0

# 静音超时切段（解决「说完话迟迟不定稿」/ cut on silence timeout）
# 段尾连续静音多久就切段定稿。
#
# ★ C-108：按 Qwen3-ASR-Flash-Realtime 的 `session.turn_detection.silence_duration_ms`
#   改造。Qwen3 官方取值：**默认 800ms，范围 [200, 6000]**，
#   并明确「对话和聊天等需快速断句的场景推荐设为 400」。
#   本项目 = 实时字幕 App，取 **800ms**（Qwen3 默认值），理由：
#     * 离线实测（61 分钟真实演讲）800ms 时规则2 从 17 段 → 37 段，
#       **新增的 20 个切点 100% 落在词间隙**（0 危险）；
#     * 700ms 起开始出现危险切点（实测 0.7s → 3 个危险），
#       所以 800ms 正好是「收益最大 + 零危险」的上沿；
#     * 600ms 虽然也 0 危险且白字提前更多（5.12s vs 0.64s 中位），
#       但段数涨到 319、空段守卫前有 5 个空段，风险收益比不如 800ms。
SILENCE_CUT_SEC = float(os.environ.get('LIVECAP_SILENCE_CUT_SEC', '0.8'))
# 保护期：段尾这么多秒内的静音不算「说话结束」（开头爆破音会被误判）。
SILENCE_TAIL_GUARD_SEC = float(os.environ.get('LIVECAP_SILENCE_GUARD_SEC', '0.35'))
# 静音判定阈值（dBFS），与 seg_stream.find_silence_in_range 的默认值一致。
#
# 对应 Qwen3 的 `session.turn_detection.threshold`（VAD 灵敏度，默认 0.5，
# 范围 [-1, 1]）。⚠️ 二者量纲不同：Qwen3 是**概率**阈值，本项目是**能量 dB**，
# 不能直接换算。-40dB 是本项目全链路实测的基准值（C-105/C-106 的能量分布
# 分析、0.8s 门槛扫描均以它为准），保持不变。
SILENCE_DB = -40.0

# ── 空段守卫（C-108：配合 Qwen3 方案新增）──────────────────────────
# 切段前要求段内确实有**成段的连续语音**，否则不切。
#
# 为什么需要（C-108 的发现）：
#   把 hangover 从 1.2s 降到 0.4s 后，空段从 1 个涨到 11 个。
#   典型空段 [41.60, 42.88]：帧 dB max=-36.3 / p90=-44.0，
#   尾静音起点前 0.35s 的 probe=-42.5dB（绝对判据 -40dB 拦下），
#   但相对判据的「段内语音电平 p90」被**噪声突发**拉高到 -40 以上，
#   导致准入门槛误放行 → 切出一个纯静音段。
#
# 判别特征**不是能量电平，而是「有没有成段的连续语音」**：
#   合法段：连续语音可达数百毫秒以上；空段：只有零星噪声突发。
#   所以用「最长连续语音帧」而不是 p90 电平来判定。
#
# 离线实测（61 分钟真实演讲）：
#   守卫关掉：hang0.8 空段 2 / hang0.6 空段 5 / hang0.5 空段 6
#   守卫打开：hang0.8 空段 **0** / hang0.6 空段 **0** / hang0.5 空段 **0**
#   且**不损失任何安全切点**（hang0.8 规则2 37→29，全仍 100% 安全；
#   hang0.6 103→86，全 100% 安全）。
#
# 阈值 200ms：30ms 帧 + 10ms hop → 20 帧。低于此值的「语音」是噪声突发。
SEG_SPEECH_FRAME_DB = -35.0
SEG_MIN_SPEECH_RUN_MS = int(os.environ.get('LIVECAP_MIN_SPEECH_RUN_MS', '200'))

# ── 相对判据（2026-10-23 §10）─────────────────────────────────────
# 背景：上面两个阈值（静音 -40dBFS、语音 -35dBFS）都是**绝对 dBFS**，
# 与实际输入电平/背景声无关。实测有**两种**失效模式：
#
#   (a) 电平偏低（麦克风）：帧能量整体低 → 语音守卫恒 False
#       → 在 due() 最前面短路 → 只剩 20s 硬切（实测 20.48s 一段）。
#   (b) 持续背景声（视频回环）：噪声把底噪撑到 -40dBFS 以上
#       → 永远「没有静音」→ 规则2/规则1 都不触发 → 只剩 20s 硬切。
#
# 用户实测场景是 (b)：WASAPI 回环采 B 站视频，帧 dB p50=-21.8 / p90=-13.9，
# 低于 -40dB 的帧只占 12.2%，逐 2 秒窗口最长连续静音 0.00~0.43s
# ⇒ 绝对 -40dBFS 永远判不出静音 ⇒ 定稿间隔恒为 20.48s。
#
# 改法：判据**相对化** —— 锚定到「这一段自己的说话电平」（段内 30ms 帧
# 能量 p90），而不是全局绝对值。真实回环 120s 上离线模拟：
#   绝对 -40dBFS（现状）  8 段 4 硬切 p50=17.28 >12s 62.5%
#   相对 p90-12dB         16 段 0 硬切 p50= 6.40 >12s  6.2%   ← 采用
#   相对 p90-18dB         12 段 1 硬切 p50= 7.04 >12s 25.0%
# 真实演讲 12 分钟交叉验证不劣化：
#   现状   108 段 0 硬切 0 空段 p50=6.40 max=11.52 >12s 0%
#   相对   110 段 0 硬切 0 空段 p50=6.40 max=10.88 >12s 0%
#
# ⚠️ 否定结论（§9.4 实测）：「绝对 ∪ 相对（取 min）」在回环上**无效**
#   —— 绝对 -40dBFS 恒比相对值更严格，取 min 仍等于绝对 ⇒ 必须**只取相对**。
#   所以下面 SIL_REL 是**替换**关系，不是 C-105 保护期那种「并集放宽」。
SIL_REL_ENABLED = os.environ.get('LIVECAP_SIL_REL', '1') == '1'
# 静音门限比段内语音电平低多少 dB 仍算「静音」。
SIL_REL_DROP_DB = float(os.environ.get('LIVECAP_SIL_REL_DROP', '12'))
# 段内 p90 低于此绝对值时说明这段基本是噪声/数字静音，
# 相对判据不可用 ⇒ 退回绝对阈值（防止回环无播放时的全零被误判成静音）。
SIL_REL_MIN_SPEECH_DB = float(os.environ.get('LIVECAP_SIL_REL_MIN_SPEECH', '-60'))
# 静音门限的组合方式：
#   'max' —— 取 max(相对, 绝对)，即**取更宽松**的那个门限（门限越高越多帧算静音）。
#            安静输入（段内 p90 低）时绝对 -40dBFS 更宽松 ⇒ 旧行为不变；
#            背景声输入（段内 p90 高）时相对门限更高 ⇒ 相对判据生效。
#   'rel' —— 只用相对门限（严格按 §9.4 实测结论）。
#   'abs' —— 只用绝对门限（= 关闭相对化，用于 A/B 回退）。
SIL_REL_MODE = os.environ.get('LIVECAP_SIL_REL_MODE', 'max').lower()

# 语音守卫的相对分支（解决失效模式 (a)：麦克风电平偏低）。
# 绝对分支（> -35dBFS 连续 200ms）保留为**一票通过**，相对分支与之**取并集**
# —— 只放宽不收紧，保证基线行为不退化。
SPK_REL_ENABLED = os.environ.get('LIVECAP_SPK_REL', '1') == '1'
# 语音帧比段内 p90 低多少 dB 仍算「语音」。
SPK_REL_DROP_DB = float(os.environ.get('LIVECAP_SPK_REL_DROP', '18'))
# 同上：段内 p90 低于此值就不用相对分支（纯噪声/数字静音段）。
SPK_REL_MIN_SPEECH_DB = float(os.environ.get('LIVECAP_SPK_REL_MIN_SPEECH', '-60'))
# 相对分支的**绝对地板**：语音帧还必须高于此 dBFS，
# 否则纯噪声段（全零回环 / 数字静音）会被相对判据当成语音而误放行。
SPK_REL_FLOOR_DB = float(os.environ.get('LIVECAP_SPK_REL_FLOOR', '-70'))

# 「空段拒切」的**相对**语音覆盖率下限。
#
# 为什么需要（2026-10-23 §10 实测发现）：
#   静音门限相对化后门限被**抬高**（真实演讲上从绝对 -40dBFS 抬到 -35~-39dB），
#   会把「安静但连续」的一小段提前切出来 ——
#   实测 12 分钟真实演讲：基线空段 0，新判据空段 2
#   （典型段：1.28s，其中 1.08s 是静音、只有 3 帧超过 -35dBFS）。
#   ASR 会对这种段产出一句无意义内容（C-106 记录过同类问题）。
#
# 为什么用**相对**覆盖率（帧 > 段内 p90 − SPK_REL_DROP_DB 的占比）
# 而不是 C-108 的绝对口径（帧 > -35dBFS 的占比）：
#
#   绝对口径在低电平麦克风场景**不可用** —— 实测 gain=0.3 的正常说话段
#   绝对语音占比只有 0.8%~6%（那**是真的说话**），用它拒切会把低电平
#   场景打死（实测 >12s 从 0% 退化到 23.4%）。
#   「静音占比」（帧 ≤ -40dBFS）同样是绝对口径，低电平时底噪本身就在
#   -40dBFS 以下 ⇒ 会被误判成全静音 ⇒ 同样出问题。
#
#   ⇒ 绝对电平口径**在原理上**无法区分「轻声说话」与「安静」：
#      把增益调低 10dB 后二者不可分辨。相对口径则与电平无关。
#
# 实测区分度（12 分钟真实演讲，真实 due() 产生的段）：
#   真空段（gain=1.0，2 个）：相对覆盖率 0.317 / 0.379
#   正常段 gain=1.0/0.5/0.3/0.1：全部 ≥ 0.425
#   ⇒ 阈值 0.40 能干净分开。
#
# 附加放行：段内 p90 ≤ SPK_REL_MIN_SPEECH_DB(-60dBFS) ⇒ 整段极弱
#   （纯底噪 / 数字静音 / 回环无播放时的全零）→ 不拒切。
SEG_MIN_REL_COVER = float(os.environ.get('LIVECAP_MIN_REL_COVER', '0.40'))

# ── 保护期判据（C-105：改用相对阈值）────────────────────────────
# 保护期本来是防「刚开口的爆破音（/b/ /p/）能量低，被静音检测误判成
# 静音」而设的。旧判据是**绝对阈值** probe_db > SILENCE_DB(-40dB)，
# 在真实录音里会大面积失效：
#
#   真实演讲 <内部音频>.wav 实测 —— 30 处 ≥1.2s 静音里，
#   现状判据拦截了 24 处（80%）。原因底噪本身就接近 -40dB
#   （中位 -56dB 但 p10 到 -65dB），说话收尾时能量渐弱，
#   句末 0.35s 的能量中位只有 -42.4dB，低于 -40dB → 判「不是说完」
#   → 规则2（静音超时切段）形同虚设，只能等规则1 的 12s 下限，
#   白等 1~2s，用户看到白字明显偏慢。
#
# 改法：把判据锚定到**这一段自己的语音电平**，而不是全局绝对值。
#   放行条件 = 绝对判据 或 相对判据（取并集，绝不收紧现状）
#     绝对：probe_db > SILENCE_DB(-40dB)              ← 现状，一票通过
#     相对：probe_db > 段内语音电平(p90) - DROP_DB     ← 新增，低能量句末
# 语音电平用段内 30ms 帧能量的 90 分位（代表「这一段说话时的响度」）：
#   * 底噪高/尾音渐弱时，相对阈值同步下移 → 不再误杀正常收尾；
#   * 刚开口的爆破音仍远低于段内语音电平 → 保护依然有效。
#
# 实测（61 分钟真实演讲，离线切段模拟 A/B，drop=18dB）：
#   规则2 触发 11 → 18 段；新增 7 个切点**全部落在词间隙**（0 危险）；
#   白字提前量中位 5.76s、最大 12.8s，61 分钟累计提前 42.2s。
#   drop 必须 ≥15：drop≤12 时相对判据比绝对判据更严，会**丢掉**
#   基线本来能切的点（实测丢 2~9 个），反而更慢。
GUARD_REL_ENABLED = os.environ.get('LIVECAP_GUARD_REL', '1') == '1'
# 允许句末能量比段内语音电平低多少 dB 仍算「说完了」。
GUARD_REL_DROP_DB = float(os.environ.get('LIVECAP_GUARD_REL_DROP', '18'))
# 段内语音电平低于此绝对值时，说明这段基本是噪声，不用相对判据。
#
# ⚠️ C-106：此值由 -45 收紧到 -40。原因是 -45 会让相对判据**切出空段**：
#   61 分钟真实演讲上，520.96s 处多切了一刀**只有 1.92s 的段**，
#   而该段语音帧(>-35dB)占比只有 **1%**（前后正常段是 50%/46%），是一段纯静音。
#   ASR 会对它产出一句无意义内容，还打乱后续切点节奏
#   （规则1 从 520.96s 重新起算，+1.28s 逐段累积 → 端到端末段看起来晚了 56.8s）。
#   判别特征不是「probe 与 speech 的差值」，而是 **speech 本身**：
#     合法救回点 speech=-26.4dB（真在说话）；误切空段 speech=-40.4dB（就是噪声底）。
#   门槛扫描（61 分钟，diag_guard_speech_gate2.py，只比 rule2 切点）：
#     -45dB → 新增 7 个、其中 2 个空段
#     -40dB → 新增 6 个、空段 1 个（**唯一空段是基线原有的**）、**合法点一个没丢**
#     -30dB → 新增 5 个（白白丢掉 speech=-31dB 的合法救回点）
#     -26dB → 新增 2 个（丢掉 4 个合法点，太严）
#   → 取 -40dB：区间 -40~-32dB 结果完全相同，取上沿 = 最宽松、收益最大。
GUARD_REL_MIN_SPEECH_DB = float(os.environ.get('LIVECAP_GUARD_REL_MIN_SPEECH', '-40'))

# ── 路径解析（全部相对包根目录，不依赖任何开发机绝对路径）─────────────
# 模型目录放在包根的 models/ 下：<包根>/models/<子目录>
# 这里用**相对路径**定位，不写死盘符/用户名，压缩包解压到任意目录都能跑。
MODELS = os.environ.get(
    'LIVECAP_MODELS_DIR',
    os.path.join(PKG_ROOT, 'models'))

# 模型目录名映射：客户包把开发机的模型目录**重命名并重组**过
# （权重文件逐个 hash 一致，只是目录名不同）。
# key = 逻辑名（开发版目录名），value = 客户包里的目录名列表（按优先级）。
# 找不到时回退到开发版目录名（开发机上 models/ 仍是原名）。
_MODEL_ALIASES = {
    # 编码器
    'ov-encoder-segment-reviewer-int8asym': ['encoder-int8'],
    'ov-encoder-segment-reviewer-int4': ['encoder-int4'],
    'ov-encoder-segment-reviewer': ['encoder-fp16'],
    # GPU 解码器
    'ov-int8-past': ['decoder-gpu-int8'],
    'ov-int4-lmhead-past': ['decoder-gpu-int4'],
    # NPU 解码器
    'qwen3-lm-int8sym-cleanie-ov': ['decoder-npu-int8'],
    'c089_int4/R4': ['decoder-npu-int4'],
    # NPU 用的 embedding 表（开发版在 decoder 目录里，包内提到了 models/ 根）
    'qwen3-lm-int8sym-cleanie-ov/embed_tokens_f16.npy': ['embed_tokens_f16.npy'],
}


def _model_path(name):
    """把逻辑模型名解析成实际目录/文件路径。

    解析顺序：
      1) <包根>/models/<别名>       —— 客户包布局
      2) <包根>/models/<逻辑名>      —— 开发机布局（models/ 里是原名）
      3) <包根>/models/<逻辑名的父目录>/<文件名> —— 散落文件（如 embed_tokens）
    找不到时返回第 2 条的路径（保持原行为，由调用方报「缺模型」）。

    名字里的分隔符统一按 '/' 处理：ENGINES 里写 'c089_int4\\R4' 或
    'c089_int4/R4' 都能匹配到同一个别名。
    """
    key = name.replace('\\', '/')
    cands = _MODEL_ALIASES.get(key, [])
    for alias in cands:
        p = os.path.join(MODELS, *alias.split('/'))
        if os.path.exists(p):
            return p
    # 散落文件：别名里带斜杠的（embed_tokens_f16.npy）
    if '/' in key and cands:
        parent, fname = key.rsplit('/', 1)
        p = os.path.join(MODELS, cands[0])
        if os.path.isdir(p) and os.path.exists(os.path.join(p, fname)):
            return os.path.join(p, fname)
    return os.path.join(MODELS, *key.split('/'))


# ── CUDA（audio.cpp）路径 ───────────────────────────────────────────────
# CUDA 后端依赖外部的 audio.cpp 可执行文件 + GGUF 模型，**不在客户包里**
# （包内没有 audiocpp_cli.exe，也没有 .gguf）。
# 解析顺序：LIVECAP_CUDA_DIR 环境变量 → <包根>/cuda/ → <用户目录>/confucius4-r2t2
#           （最后一条是开发机布局；只有目录里确实有 audio.cpp/audiocpp_cli.exe
#             才认，避免在客户机上误命中同名目录）。
# 找不到时 CUDA 后端自然不可用，不影响 Intel 后端。
def _cuda_root():
    env = os.environ.get('LIVECAP_CUDA_DIR')
    if env:
        return env if os.path.isdir(env) else None
    cands = (os.path.join(PKG_ROOT, 'cuda'),
             os.path.join(os.path.expanduser('~'), 'confucius4-r2t2'))
    for p in cands:
        if os.path.exists(os.path.join(p, 'audio.cpp', 'audiocpp_cli.exe')):
            return p
    return None


CUDA_DIR = _cuda_root()
CUDA_CLI = os.path.join(CUDA_DIR, 'audio.cpp', 'audiocpp_cli.exe') \
    if CUDA_DIR else ''


# 编译缓存：放在**用户可写目录**（压缩包可能装在 Program Files，只读）。
# C-133 / APP-002：编译缓存**绝不写包内** —— 包内缓存对客户机基本无用，
# 却是实打实的体积（开发机实测长到 4.1 GB）。
def _cache(name):
    """编译缓存目录：**用户可写目录**，绝不写包内。

    C-133 / APP-002（客户包瘦身）—— 为什么不能放包里：
    - 包内缓存对客户机**基本无用**：GPU blob 头写死 ie_version
      （实测 "2026.4.1-22982-e213a147257-release"），oneDNN kernel 缓存
      绑 CPU 微架构 ⇒ 换机器 / 换 OV 版本基本不命中；
    - 但它是**实打实的体积**：开发机实测长到 4.1 GB（其中单个 decoder
      blob 1.65 GB），压缩率只有 88%（已编译二进制），删比压划算；
    - 包可能装在 Program Files（只读）⇒ 写不进去 ⇒ 每次启动都重编译
      （实测首次多约 19 s）。

    与 translator.py 的 mt_cache 保持同一根目录，便于用户一次性清理。

    不可写时**回落包内**（不致命）：已实测只读 CACHE_DIR 不崩，
    OpenVINO 会静默跳过写缓存，只影响编译速度。
    """
    root = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(root, 'Confucius4LiveCaption', name)
    try:
        os.makedirs(d, exist_ok=True)
        # Windows 上目录可能存在但 ACL 拒绝写入，此时 makedirs 不报错，
        # 而后续 OpenVINO 写缓存会失败 ⇒ 必须显式探测写权限。
        if not os.access(d, os.W_OK):
            raise OSError(f'not writable: {d}')
        return d
    except Exception as e:
        print(f'[warn] 编译缓存目录不可用（{e}），回落包内 {name}/')
        return os.path.join(APP_DIR, name)


ENGINES = {
    'gpu_int8': dict(label='Intel GPU · INT8', kind='ov', device='GPU.0',
                     enc='ov-encoder-segment-reviewer-int8asym', dec='ov-int8-past',
                     note='集显：编码器 INT8 + 解码器 INT8'),
    'gpu_int4': dict(label='Intel GPU · INT4', kind='ov', device='GPU.0',
                     enc='ov-encoder-segment-reviewer-int4', dec='ov-int4-lmhead-past',
                     note='集显：编码器 INT4 + 解码器 INT4（最快；61 分钟 WER 比 INT8 显著差约 1.3 个百分点）'),
    'npu_int8': dict(label='Intel NPU · INT8', kind='npu',
                     enc='ov-encoder-segment-reviewer', dec='qwen3-lm-int8sym-cleanie-ov',
                     note='编码器与解码器都在 NPU，不占 GPU'),
    'npu_int4': dict(label='Intel NPU · INT4（实验）', kind='npu',
                     enc='ov-encoder-segment-reviewer', dec=r'c089_int4\R4',
                     note='实验配置：更快，但 61 分钟 WER 比 INT8 显著差约 2 个百分点'),
    'cuda_q8': dict(label='NVIDIA GPU · CUDA Q8_0', kind='cuda',
                    gguf='r2t2-q8_0.gguf', note='audio.cpp + GGUF Q8_0，RTX 独显'),
    'cuda_q4': dict(label='NVIDIA GPU · CUDA Q4_K', kind='cuda',
                    gguf='r2t2-q4_k.gguf', note='audio.cpp + GGUF Q4_K，RTX 独显'),
}


# ── 「设备 + 精度」组合选项（APP-007：三个分区各一个下拉）────────────
# 用户决策：每个分区**只保留一个「设备+精度」组合下拉**，不再有独立的
# 设备下拉（原来的「推理设备」行把三个下拉挤在一行，且 ASR/MT 的后端下拉
# 标签里本来就含设备名 ⇒ 语义重叠）。
#
# 选项 id 约定：ASR/翻译 = '{engine_key}@{device}'，语音 = '{device}@{precision}'
# ⇒ id 唯一可反查；label 供人读。
# ⚠️ label 必须**全局唯一**（GUI 靠 label 反查 engine/device）。
ASR_PRECISION = {
    'gpu_int8': 'INT8', 'gpu_int4': 'INT4',
    'npu_int8': 'INT8', 'npu_int4': 'INT4',
    'cuda_q8': 'Q8_0', 'cuda_q4': 'Q4_K',
}
MT_PRECISION = {
    'gpu_int8cw': 'INT8-CW', 'gpu_int4cw': 'INT4-CW',
    'npu_int8cw': 'INT8-CW', 'npu_int4cw': 'INT4-CW',
}
# ⚠️ TTS 的 precision 是 **OV 推理精度 f32/f16**，不是量化位宽
#    （见 tts_service.py::TTSService.precision）。
TTS_PRECISIONS = ('f32', 'f16')


def _asr_ir_ready(cfg):
    """该 ASR 档的 IR（编码器 + 解码器）在本机是否齐全。

    ⚠️ 这是「选了 CPU 但只有 INT8 IR」这类过滤的依据：
       本机没有 INT4 的 IR ⇒ **不出现 INT4 选项**（而不是选完再报错）。
    """
    try:
        return (os.path.isdir(_model_path(cfg['enc']))
                and os.path.isdir(_model_path(cfg['dec'])))
    except Exception:
        return False


def build_asr_options(devices):
    """ASR 分区的「设备+精度」组合选项。

    返回 ``[{'id','label','engine','device','precision','note','fixed'}]``。

    ⚠️ 三种 kind 的处理**完全不同**（这是本设计最易错的地方）：
    - kind=='ov'（gpu_int8/gpu_int4）：设备**可覆盖** ⇒ 与本机可用设备
      求交集逐个生成；但 **排除 NPU**（NPU 由 kind=='npu' 的 all-NPU
      交付后端承担，两条路会争用设备）。
    - kind=='npu'（npu_int8/npu_int4）：**设备写死 NPU**，不可覆盖
      （make_engine 注释明确「不接受覆盖」）。
    - kind=='cuda'（cuda_q8/cuda_q4）：另一种 kind（audio.cpp），
      设备概念不同 ⇒ 单列一条，标注 CUDA。
    """
    out = []
    for key, cfg in ENGINES.items():
        prec = ASR_PRECISION.get(key, 'INT8')
        note = cfg.get('note', '')
        if cfg['kind'] == 'cuda':
            out.append(dict(id=f'{key}@CUDA',
                            label=f'NVIDIA GPU（CUDA） · {prec}',
                            engine=key, device='CUDA', precision=prec,
                            fixed=True, note=note))
            continue
        if not _asr_ir_ready(cfg):
            continue                       # 本机缺该精度的 IR ⇒ 不出现
        if cfg['kind'] == 'npu':
            out.append(dict(id=f'{key}@NPU',
                            label=f'Intel NPU · {prec}',
                            engine=key, device='NPU', precision=prec,
                            fixed=True, note=note))
            continue
        for dev in devices:
            if str(dev).upper() == 'NPU':
                continue                   # NPU 归 kind=='npu' 那条路
            out.append(dict(id=f'{key}@{dev}',
                            label=f'{device_config.device_label(dev)} · {prec}',
                            engine=key, device=dev, precision=prec,
                            fixed=False, note=note))
    return out


def build_mt_options(devices):
    """翻译分区的「设备+量化」组合选项。

    翻译模型（Hy-MT2 INT8/INT4-CW）**GPU / NPU 通吃**（per-channel 产物，
    见 translator.py 的实测结论）⇒ 设备可自由选，与量化组合成笛卡尔积。

    🔴 **label 必须全局唯一**（GUI 靠 label 反查 engine/device）。
    MT_ENGINES 里 ``gpu_int8cw`` 与 ``npu_int8cw`` 指的是**同一个模型目录**
    （mt2-int8sym-cw-q），只是 engine 默认设备不同 ⇒ 若按 engine × device
    展开，``gpu_int8cw@GPU.0`` 与 ``npu_int8cw@GPU.0`` 会得到**同一个 label**
    「Intel GPU（集显） · INT8-CW」⇒ 反查会取错引擎。
    ⇒ **以「量化」为维度**展开（INT8-CW / INT4-CW 两档），
    engine key 取该档里已注册（模型目录在本机）的那个。
    ``set_engine`` 会把 device 重置成 engine 默认值，随后 ``set_device``
    再纠正回用户选的设备（顺序铁律，见 ``App._on_mt_combo_changed``）。

    ⚠️ **'auto' 不出现在下拉里**（用户决策）：'auto' 的 device 是 None，
    语义上不是「某个设备 × 某个量化」。启动时把 auto **解析成实际模型键**
    （见 ``App._resolve_mt_engine_key``）再显示。
    """
    out = []
    for dev in devices:
        for quant, engines in (('INT8-CW', ('gpu_int8cw', 'npu_int8cw')),
                               ('INT4-CW', ('gpu_int4cw', 'npu_int4cw'))):
            key = next((k for k in engines if k in MT_ENGINES), None)
            if key is None:
                continue                   # 该量化的模型目录不在本机 ⇒ 不出现
            cfg = MT_ENGINES[key]
            out.append(dict(id=f'{quant}@{dev}',
                            label=f'{device_config.device_label(dev)} · {quant}',
                            engine=key, device=dev, precision=quant,
                            fixed=False, note=cfg.get('note', '')))
    return out


def build_tts_options(devices):
    """语音分区的「设备+精度」组合选项。

    ⚠️ 这里的 precision 是 **OV 推理精度 f32/f16**，不是量化位宽。
    过滤规则：``device_config.check_precision`` —— **NPU 不支持 f32**
    （PRECISION_UNSUPPORTED = {'NPU': ('f32',)}）。

    🔴🔴 **CUDA 设备（2026-10-25 用户要求：TTS 设备里也要有 CUDA）**：
       本机 ``GPU.1`` = NVIDIA GeForce RTX 5050（dGPU）⇒ 必须能在 TTS 下拉里
       **显式看到 CUDA 选项**。但实测（见 ``results/app/app024_tts_ir_probe.py``）：

           GPU.0（Intel 集显） : TTS 真实 IR **7/7** 编译成功
           GPU.1（NVIDIA 独显） : TTS 真实 IR **3/7** 编译成功
                                （4 个在 FP16↔FP32 reorder 节点上无 kernel）

       根因：**本机 OV 未安装 CUDA plugin**（`openvino` 包内无 cuda 组件）
       ⇒ OV 2026.4 对 NVIDIA 独显仍走 **Intel GPU plugin**（经 Level Zero），
       对 INT8 权重的 FP16 reorder 覆盖不全。

       ⇒ 本函数的处理：**照常列出 CUDA 选项**（用户要求），
         但 **note 里写明实测结论**，让用户知道它当前跑不通、为什么。
         绝不把用不了的选项**静默隐藏**（用户明确要看到），
         也绝不**假装它可用**。
    """
    out = []
    cuda_ok = device_config.has_cuda_plugin()
    for dev in devices:
        is_cuda = device_config.is_cuda_device(dev)
        note = ''
        if is_cuda:
            if cuda_ok:
                note = 'CUDA 后端（OV CUDA plugin 已安装）'
            else:
                note = ('CUDA 设备：🔴 本机 OV **未安装 CUDA plugin**'
                        '（OV 仍用 Intel GPU plugin 驱动它）⇒ TTS 的 INT8 权重'
                        '在 FP16 reorder 节点上无 kernel，**实测 3/7 IR 编译失败**；'
                        '要真正启用需装 openvino 的 CUDA 组件')
        for prec in TTS_PRECISIONS:
            if device_config.check_precision(dev, prec):
                continue                   # 例如 NPU + f32 ⇒ 不出现
            label = f'{device_config.device_label(dev)} · {prec.upper()}'
            if is_cuda:
                label = f'CUDA · {label}'
            out.append(dict(id=f'{dev}@{prec}',
                            label=label,
                            device=dev, precision=prec, fixed=False, note=note))
    return out

# Qwen3-ASR 模型内置 support_languages（见 models/hf/config.json），
# 这里列出全部 30 种。值必须是模型认识的**英文名**（不是 ISO 代码），
# 因为它会被拼进 prompt 后缀「language {name}<asr_text>」。
ASR_LANGS = (
    'Chinese', 'English', 'Cantonese', 'Arabic', 'German', 'French',
    'Spanish', 'Portuguese', 'Indonesian', 'Italian', 'Korean', 'Russian',
    'Thai', 'Vietnamese', 'Japanese', 'Turkish', 'Hindi', 'Malay',
    'Dutch', 'Swedish', 'Danish', 'Finnish', 'Polish', 'Czech',
    'Filipino', 'Persian', 'Greek', 'Romanian', 'Hungarian', 'Macedonian',
)

# 中文显示名（其余语种直接用英文名，模型侧与界面侧一致，省去一层映射）
ASR_LANG_LABELS = {
    'Chinese': '中文', 'English': 'English', 'Cantonese': '粤语',
    'Korean': '한국어', 'Japanese': '日本語',
}

# 「自动检测」：不往 prompt 里塞语种提示，交给模型自己判断
ASR_LANG_AUTO = 'auto'


def asr_lang_label(name):
    """语种英文名 -> 界面显示文本。"""
    if name == ASR_LANG_AUTO:
        return '自动检测'
    return ASR_LANG_LABELS.get(name, name)


def _init_draft_flag(args):
    """草稿译文的初始开关状态。

    优先级：命令行 --mt-draft > 环境变量 LIVECAP_DRAFT=1 > 默认**关闭**。
    默认关闭 = 只翻译已经定稿的文本；草稿每 1.5s 要翻近一整句 partial，
    是 GUI 下 ASR 积压的主要来源（关掉 RTF +0.042，打开 1.5s 间隔 +0.144）。
    """
    if getattr(args, 'mt_draft', False):
        return True
    return os.environ.get('LIVECAP_DRAFT') == '1'


def _frame_db_series(x, frame_ms=30, hop_ms=10):
    """逐帧 RMS→dB 序列（与 seg_stream._frame_rms 同参数）。

    C-105 的相对阈值保护期要用「段内语音电平」，需要帧级能量序列。
    这里独立实现（而不是 import seg_stream），是为了让 live_caption_app
    的判据不依赖 seg_stream 的内部实现细节。
    """
    if x is None or x.size == 0:
        return np.zeros((0,), dtype=np.float64)
    n = int(frame_ms * SR / 1000)
    h = int(hop_ms * SR / 1000)
    if n <= 0 or h <= 0:
        return np.zeros((0,), dtype=np.float64)
    if x.shape[0] < n:
        pad = np.zeros(n - x.shape[0], dtype=x.dtype)
        x = np.concatenate([x, pad])
    nf = (x.shape[0] - n) // h + 1
    sq = x.astype(np.float64) ** 2
    cs = np.concatenate(([0.0], np.cumsum(sq)))
    out = np.empty(nf, dtype=np.float64)
    for i in range(nf):
        s = i * h
        out[i] = 20.0 * np.log10(np.sqrt((cs[s + n] - cs[s]) / n + 1e-12) + 1e-7)
    return out



def _norm_word(w):
    return str(w).strip('.,!?;:，。！？；：').lower()


# ── 段接缝重复词消除（APP-012② / APP-014①）─────────────────────────
#
# 🔴🔴 **问题（ASR-006 §2 实测）**：rule1 的切点会**穿过一个词**，
#    前后两段都把这个词转写出来（例：`...future technology | technology needs...`）。
#
# 🔴🔴 **旧 `stitch()` 的致命缺口**：它只试 n=3,2 —— 而**实测接缝重复
#    绝大多数是 n=1（单个词）**！61 分钟 A/B 两组离线实测
#    （`results/app/app024_seam_diag.py`，素材 reports/asr004_ab/segments_{A,B}.json，
#    段边界由**真实 Segmenter** 判定 ⇒ 与 App 实时路径逐点一致）：
#      A 组：536 对相邻段 → n≥3: **0**、n=2: **0**、n=1: **36**
#      B 组：557 对相邻段 → n≥3: **0**、n=2: **0**、n=1: **42**
#    ⇒ 旧 stitch **一次都没命中过** ⇒ 重复词 100% 漏到用户屏幕上。
#
# ✅ 修法：**整词级 n-gram 去重**（n = 3 → 2 → 1），
#    命中就删掉新段开头的重复词。
#
# 🔴🔴🔴 **n=1 的判据（本轮实测重新设计，替换掉原先的「停用词表」方案）**：
#   原方案用「英文停用词表」做安全阀，**方向是错的** ——
#   `app024_stopword_audit.py` 实测：被它挡掉的 15(A)/18(B) 处**全是真缺陷**
#   （切点正好落在词中间）：
#     ...our strategy will and has | has been to maximize the overall result.
#     ...And the scale is | is very important.
#     ...a different perspective on that approach. So | So this was just a summary.
#   ⇒ 停用词表把**真缺陷**当成了「真内容」⇒ 漏掉一半以上的真缺陷。
#
#   ✅ **新判据（两个可观测特征，实测有效）**：
#     ① **后段首词是大写开头、而前段末尾词不是** ⇒ 后段**重新起句**
#        （ASR 给新句首字母大写）⇒ 强特征「切点穿词」；
#        典型：`...So, welcome | Welcome to our Q3 preview.`、
#               `...love the scale | Scale and compatibility for multiple generations.`
#     ② **前段末尾不是句末标点**（`.` `?` `!` `。` `！` `？`）
#        ⇒ 同一句话被切成两半 ⇒ 「切点穿词」；
#        反之若有句末标点 ⇒ 上一句说完了，新句又说了同一个词 ⇒ **真内容**。
#
#   ⚠️ **上面的示例句已脱敏**（2026-10-25）：原先直接引用内部会议转写片段，
#      被内部素材闸门（`check_internal_material.py`）在打包前拦下
#      ⇒ 全部换成语义等价的合成句，**判据逻辑不受影响**。
#
#   📊 **量化（独立参照 c048 adaptive，语料级配对 bootstrap K=40/5000 次，
#      `results/app/app024_seam_rule_wer.py`）**：
#      A 组 6.055% → 6.013%   Δ = −0.043 pp  CI [−0.077, −0.009] ⇒ 上界<0 改善
#      B 组 5.851% → 5.791%   Δ = −0.060 pp  CI [−0.102, −0.026] ⇒ 上界<0 改善
#   ⇒ 显著改善，且比「无安全阀」更保守（少误删）。
#
# ⚠️ **不要误读这个收益的量级**：它只覆盖 ASR-006 所述 **+2.6pp** 缺口的
#    **约 3%** ⇒ **接缝去重不是 +2.6pp 的主因**（主因是段首/段尾的**插入**
#    本身，ASR 侧记的是多 178 个）。详见 STATUS_APP §32。
#
# 🔴 **已删掉的「字符级重叠裁剪」**：原在制品里有 `_stitch_char_overlap()`
#    + 注释提到的 `stitch_pair()`，但 **stitch_pair 根本不存在**，
#    且实时路径上 `stitch()` 只有 `prev_words`（前 3 个词）**没有 prev_text**
#    ⇒ 该分支**无生效路径**；实测 A/B 两组**字符级命中 0 次**
#    （真缺陷全是整词级 n=1）⇒ 整段移除，避免留下「看着有、其实没生效」的代码。
#
#   * 开关：`LIVECAP_STITCH_SEAM=0` 可**完全退回旧行为**（只试 n=3,2；**默认开**）。

# 接缝整词去重的最大 n（3 → 2 → 1）
STITCH_MAX_NGRAM = int(os.environ.get('LIVECAP_STITCH_MAX_NGRAM', '3'))
# 接缝去重总开关（1=开，0=退回旧行为）
STITCH_SEAM_ENABLED = os.environ.get('LIVECAP_STITCH_SEAM', '1') not in ('0', 'false', 'False')

# 🔴 **句末标点集**（判据②用）：前段末尾是这些字符 ⇒ 上一句说完了
_STITCH_SENT_END = '.?!。！？；…'


def _stitch_is_capitalized(w: str) -> bool:
    """词是否**首字母大写**（后段重新起句的特征）。"""
    return bool(w) and w[0].isupper()


def _stitch_tail_is_sentence_end(prev_text: str) -> bool:
    """前段末尾是否为**句末标点**（⇒ 上一句说完了 ⇒ 新句重说 ⇒ 真内容）。"""
    t = (prev_text or '').rstrip()
    return bool(t) and t[-1] in _STITCH_SENT_END


def _stitch_is_cut_through_word(prev_text, prev_word: str,
                                cur_word: str) -> bool:
    """判定「这次 n=1 重复」是不是**切点穿词**（真缺陷）造成的。

    🔴 **判据（实测验证，见文件头注释）**：
       ① 后段首词大写开头、而前段末尾词不是 ⇒ 后段重新起句 ⇒ 切点穿词；
       ② 前段末尾**非**句末标点 ⇒ 同一句被切开 ⇒ 切点穿词。
       ⇒ 任一成立即判为「切点穿词」（该删）。

    🔴 **`prev_text` 为 None 时只判据①**（判据②需要标点信息，
       没有就不能用 ⇒ 宁可漏删也不误删；空串 '' 同理**不能**当「无标点」用，
       否则判据②恒成立 ⇒ 退化成最激进的「无安全阀」档）。
    """
    if _stitch_is_capitalized(cur_word) and not _stitch_is_capitalized(prev_word):
        return True
    if not prev_text:
        return False
    if not _stitch_tail_is_sentence_end(prev_text):
        return True
    return False


class Segmenter:
    """在线切段规则（只看已累计的音频）。

    两条规则，**任一**满足就切段：

    1. **常规规则**（原 mic_asr_app 的做法）：段长 ≥ ``MIN_SEG_SEC``(6 s)
       且最近 ``SIL_LOOKBACK_SEC``(3 s) 内有 ≥300 ms 静音；段长 ≥
       ``MAX_SEG_SEC``(20 s) 硬切。

    2. **静音超时规则**（C-103 新增，解决「说完话迟迟不定稿」）：
       段尾检测到连续 ≥ ``SILENCE_CUT_SEC``(0.8 s) 的静音就立即切段，
       不管段长够不够 6 秒。

    ★ C-109：``MIN_SEG_SEC`` 由 12s 降到 **6s**。
       12s 门槛是「等满 12 秒才定稿」的计时器兜底，实测它切出了 **94.2%**
       的段 —— 引擎基本没在做「按停顿切」，白字要等满 12 秒。
       降到 6s 后（61 分钟真实演讲）：段长 p50 12.16s → **6.40s**，
       白字提前中位 0.64s → **5.12s**，规则2 切点仍 23/23 全安全、空段 0。

    为什么需要第 2 条：原规则只在段长够长后才去看静音。短语音
    （会议里一句「好的」大约 1–3 秒）说完后，用户要干等到累积满门槛
    才能看到定稿（实测 3 秒语音等 5.8 秒、5 秒语音等 5.2 秒），
    字幕不转白、译文也跟着卡住。

    第 2 条不会损失识别质量：切段点落在静音区，音频内容已经解码完，
    提前收尾得到的文本与等满门槛的结果一致（实测逐字相同）。

    为什么要 ``SILENCE_TAIL_GUARD_SEC`` 保护：刚开口的第一个音节
    （如爆破音 /b/、/p/）本身能量低，可能被误判成静音。保护期内的
    静音不足以切段，避免把第一个字切到下一段。

    为什么要 ``_has_speech()`` 空段守卫（C-108）：降门槛后容易切出
    纯静音段 —— 判别依据不是能量电平，而是「有没有成段的连续语音」。
    """

    def __init__(self):
        from seg_stream import find_silence_in_range, find_trailing_silence
        self._find = find_silence_in_range
        self._trail = find_trailing_silence

    def due(self, acc):
        n = acc.shape[0]
        dur = n / SR
        if dur >= MAX_SEG_SEC:
            return True
        # 空段守卫（C-108）：段内必须有成段的连续语音才允许切段。
        # 放在最前面统一把关 —— 规则1/规则2 都可能切出纯静音段。
        if not self._has_speech(acc):
            return False
        # 规则 2：静音超时（优先判定，短段靠它出定稿）
        # ★ 2026-10-23 §10：加一道「空段拒切」防护 —— 静音门限抬高会切出
        # 「安静但连续」的短段（实测 1.28s 段里 1.08s 是静音）
        # ⇒ ASR 会产出一句无意义内容。拒切后段继续累积，仍可走规则1。
        if self._silence_tail(acc):
            if self._speech_ratio_ok(acc):
                return True
        # 规则 1：常规规则
        if dur < MIN_SEG_SEC:
            return False
        if not self._speech_ratio_ok(acc):
            return False
        start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
        # ★ 2026-10-23 §10：静音门限**相对化**（原来这里是硬编码 -40.0）
        sil_db = self._silence_threshold(acc)
        return self._find(acc, start_sample=start, end_sample=n,
                          silence_db=sil_db, min_silence_ms=300) is not None

    # ── 相对门限（2026-10-23 §10）────────────────────────────────
    def _speech_ratio_ok(self, acc):
        """空段拒切：这一段是否含有**足够的语音覆盖**（§10，相对口径）。

        判据（**相对**，与输入电平无关）：
          * 语音门限 = 段内 p90 − ``SPK_REL_DROP_DB``(18dB)
          * 语音覆盖率 = 帧 > 该门限的占比
          * 覆盖率 ≥ ``SEG_MIN_REL_COVER``(40%) → 放行
          * 段内 p90 ≤ ``SPK_REL_MIN_SPEECH_DB``(-60dBFS)
            ⇒ 整段极弱（纯底噪 / 数字静音）→ 放行
          * 否则拒切（段继续累积）

        为什么必须相对化：绝对电平口径**在原理上**无法区分
        「轻声说话」与「安静」——把增益调低 10dB 后二者不可分辨。
        实测绝对语音占比在 gain=0.3 的正常段只有 0.8%~6%，
        用它拒切会把麦克风场景打死（>12s 从 0% 退化到 23.4%）。

        实测区分度（12 分钟真实演讲，真实 due() 产生的段）：
          真空段（gain=1.0，2 个）：相对覆盖率 0.317 / 0.379
          正常段（gain=1.0 / 0.5 / 0.3 / 0.1）：全部 ≥ 0.425
        ⇒ 阈值 0.40 能干净分开。
        """
        if SEG_MIN_REL_COVER <= 0:
            return True
        f = _frame_db_series(acc)
        if f.size == 0:
            return True
        p90 = float(np.percentile(f, 90))
        if p90 <= SPK_REL_MIN_SPEECH_DB:
            return True                    # 整段极弱 → 放行
        thr = max(p90 - SPK_REL_DROP_DB, SPK_REL_FLOOR_DB)
        cover = float((f > thr).mean())
        return cover >= SEG_MIN_REL_COVER

    def _silence_threshold(self, acc):
        """本段的静音门限（dBFS），锚定到「这一段自己的说话电平」。

        旧行为是常量 ``SILENCE_DB``(-40dBFS)，**绝对**阈值。它在两种
        场景下失效（实测见 STATUS §9）：

        * 持续背景声（视频回环）：底噪被撑到 -40dBFS 以上 ⇒ 永远
          判不出静音 ⇒ 规则1/规则2 都不触发 ⇒ 只剩 20s 硬切。
        * 电平偏低（麦克风）：见 ``_has_speech``。

        新判据：``silence_db = 段内 30ms 帧能量 p90 - SIL_REL_DROP_DB``
        （默认 -12dB）。

        ⚠️ 与 C-105 保护期的「绝对 ∪ 相对」**方向相反**：那里是
        「只放宽不收紧」，这里必须**只取相对** —— 因为绝对 -40dBFS
        恒比相对值更严格，取 min/取严 会退回绝对判据、在回环上完全
        无效（实测 62.5% 的间隔仍 >12s，与现状逐位相同）。
        """
        if not SIL_REL_ENABLED:
            return SILENCE_DB
        f = _frame_db_series(acc)
        if f.size == 0:
            return SILENCE_DB
        p90 = float(np.percentile(f, 90))
        if p90 < SIL_REL_MIN_SPEECH_DB:
            # 数字静音（回环无播放时全零，帧 dB max=-119dB）或纯噪声段
            # → 相对判据不可用，退回绝对阈值。
            return SILENCE_DB
        rel = p90 - SIL_REL_DROP_DB
        if SIL_REL_MODE == 'max':
            # 混合模式：取两者中**更宽松**（门限更高 = 更多帧算静音）。
            # 安静输入（p90 低）时绝对判据更宽松 → 保留旧行为；
            # 背景声输入时相对判据更宽松 → 相对判据生效。
            return max(rel, SILENCE_DB)
        return rel

    def _has_speech(self, acc):
        """段内是否存在「成段的连续语音」（C-108 空段守卫 + §10 相对分支）。

        **绝对分支**（旧行为，保留为**一票通过**）：
        30ms 帧能量连续 ≥ ``SEG_MIN_SPEECH_RUN_MS``(200ms) 的帧
        都高于 ``SEG_SPEECH_FRAME_DB``(-35dB)。

        **相对分支**（2026-10-23 §10 新增）：解决「电平偏低」失效模式 ——
        麦克风电平整体偏低时（如增益 0.3），绝对阈值 -35dBFS 永远达不到
        ⇒ 守卫恒 False ⇒ 在 ``due()`` 最前面短路 ⇒ 只剩 20s 硬切
        （实测 100% 的间隔 = 20.48s）。相对分支把判据锚定到段内 p90：
        ``v > p90 - SPK_REL_DROP_DB``（默认 -18dB），且帧还要高于
        ``SPK_REL_FLOOR_DB``（绝对地板，防止纯噪声被当成语音）。

        两分支取**并集**（只放宽不收紧）⇒ 基线行为不会退化。

        为什么要连续而不是看电平：单个噪声突发（9 帧连续 -36dB）就能把
        「段内 p90 电平」拉到 -40dB 以上，让基于电平的判据误放行；
        而真正的语音必然连续上百毫秒以上。
        """
        if SEG_MIN_SPEECH_RUN_MS <= 0:
            return True
        f = _frame_db_series(acc)
        if f.size == 0:
            return False
        need = max(1, SEG_MIN_SPEECH_RUN_MS // 10)   # hop 10ms
        # 绝对分支（一票通过）
        run = 0
        for v in f:
            if v > SEG_SPEECH_FRAME_DB:
                run += 1
                if run >= need:
                    return True
            else:
                run = 0
        # 相对分支
        if not SPK_REL_ENABLED:
            return False
        p90 = float(np.percentile(f, 90))
        if p90 < SPK_REL_MIN_SPEECH_DB:
            return False                      # 数字静音/纯噪声段
        thr = max(p90 - SPK_REL_DROP_DB, SPK_REL_FLOOR_DB)
        run = 0
        for v in f:
            if v > thr:
                run += 1
                if run >= need:
                    return True
            else:
                run = 0
        return False

    def _silence_tail(self, acc):
        """段尾是不是已经安静了足够久（且确实有语音内容）。

        判定方式：找**紧贴音频末尾**的那段连续静音（``find_trailing_silence``），
        要求

          * 静音长度 ≥ ``SILENCE_CUT_SEC``（说话确实停了）；**且**
          * 静音起点之前有语音 —— 即「静音开始」这个点往前
            ``SILENCE_TAIL_GUARD_SEC`` 内有实际声音。

        最后一条是「保护期」：说话刚开口时，第一个音节（尤其爆破音
        /b/ /p/）本身能量就低，可能被静音检测当成静音。如果不保护，
        刚开口就会被误判成「说完了」而切段。

        注意保护期是相对**静音起点**算的，不是相对音频末尾 —— 末尾本来
        就是静音的。

        保护期的判据（C-105）—— **绝对 ∪ 相对**，取并集：
          * 绝对：probe_db > SILENCE_DB(-40dB)  ← 旧判据，一票通过
          * 相对：probe_db > 段内语音电平(p90) - GUARD_REL_DROP_DB
        取并集是为了**只放宽、不收紧**：相对判据单独用会比绝对判据更严
        （实测 drop≤12 会丢掉基线本来能切的切点），必须以绝对判据兜底。
        """
        n = acc.shape[0]
        if n < int(SR * 0.5):
            return False                       # 太短，噪声而已
        # 窗口要比判定阈值再宽一点，保证「末尾静音」完整落在窗口里
        win = int(SR * (SILENCE_CUT_SEC + SILENCE_TAIL_GUARD_SEC + 0.5))
        start = max(0, n - win)
        # ★ 2026-10-23 §10：静音门限相对化（与 due() 规则1 共用同一门限）
        sil_db = self._silence_threshold(acc)
        span = self._trail(acc, start_sample=start, end_sample=n,
                           silence_db=sil_db,
                           min_silence_ms=int(SILENCE_CUT_SEC * 1000))
        if span is None:
            return False
        sil_start, _sil_end = span
        # 静音起点往前 SILENCE_TAIL_GUARD_SEC 必须有语音
        guard = int(SR * SILENCE_TAIL_GUARD_SEC)
        probe_start = max(0, sil_start - guard)
        if probe_start >= sil_start:
            return False
        probe = acc[probe_start:sil_start]
        if probe.size == 0:
            return False
        rms = float(np.sqrt(float(np.mean(probe.astype(np.float64) ** 2)) + 1e-12))
        db = 20.0 * float(np.log10(rms + 1e-7))
        # 绝对判据（旧行为，保留）
        if db > SILENCE_DB:
            return True
        if not GUARD_REL_ENABLED:
            return False
        # 相对判据：把阈值锚定到「这一段自己的说话响度」。
        # 段内语音电平取静音起点之前的 30ms 帧能量 90 分位。
        seg_db = _frame_db_series(acc[:sil_start])
        if seg_db.size == 0:
            return False
        speech_db = float(np.percentile(seg_db, 90))
        if speech_db < GUARD_REL_MIN_SPEECH_DB:
            return False                      # 这段基本是噪声，不放行
        return db > speech_db - GUARD_REL_DROP_DB


def stitch(prev_words, text, prev_text=None):
    """段接缝去重：下一段开头与上一段末尾重复的词删掉。

    🔴🔴 **为什么必须扩到 n=1**（APP-012② / APP-014①）：
    61 分钟 A/B 两组离线实测（`results/app/app024_seam_diag.py`），**接缝重复
    几乎全是 n=1（单个词）**：
    A 组 536 对相邻段 → n≥3: 0 / n=2: 0 / n=1: **36**；
    B 组 557 对相邻段 → n≥3: 0 / n=2: 0 / n=1: **42**。
    ⇒ 旧实现（只试 3、2）**一次都没命中过**。

    判据（**顺序固定**）：

    ① **整词级 n-gram**（n = STITCH_MAX_NGRAM → … → 1）：
       前段末尾 n 个词 == 后段开头 n 个词 ⇒ 删掉后段开头的这 n 个词。
       🔴 n=1 有**判据**（`_stitch_is_cut_through_word`）：只有当
       「后段重新起句（首字母大写）」**或**「前段末尾非句末标点」时
       才算「切点穿词」才删；否则是真内容（上一句说完了，新句又说一遍）。

    ⚠️ **`prev_text` 现在是必需的信息**（判据②要用前段末尾的标点信息）：
       调用方**必须**传前段的完整文本；传 None / 空串时退化为「只信判据①」
       （宁可漏删也不误删）。

    🔴 **开关语义**（`LIVECAP_STITCH_SEAM`，默认 **1**）：
       `0` ⇒ **完全退回旧行为**（只试 n=3,2，**不做 n=1**）
       —— 注意不是「跳过判据」，而是「连 n=1 都不做」；
       「跳过判据」反而会**更激进**（最激进档），与「关掉」的语义相反。
    """
    if not text:
        return text
    if not prev_words:
        return text

    words = text.split()
    nw = [_norm_word(w) for w in words]
    prev = [_norm_word(w) for w in prev_words]

    # 🔴 开关关闭 ⇒ 退回旧行为：**下限抬到 2**（旧实现只试 n=3,2，不做 n=1）
    #   注意是「下限」不是「上限」—— 旧行为保留了 n=3 的去重能力。
    min_n = 1 if STITCH_SEAM_ENABLED else 2
    max_n = STITCH_MAX_NGRAM

    # ── ① 整词级 n-gram：n 从大到小 ──
    for n in range(min(max_n, len(words)), min_n - 1, -1):
        if len(nw) < n or len(prev) < n:
            continue
        if prev[-n:] != nw[:n]:
            continue
        # 🔴 n=1 用「切点穿词」判据决定删不删
        if n == 1 and STITCH_SEAM_ENABLED:
            if not _stitch_is_cut_through_word(prev_text, prev_words[-1],
                                                words[0]):
                continue
        rest = words[n:]
        return ' '.join(rest) if rest else text
    return text


# ── OpenVINO 引擎（Intel GPU / NPU）────────────────────────────────────
class OVEngine:
    """把 streaming_transcribe 包装成增量引擎（逻辑同 mic_asr_app.StreamingEngine）。"""

    def __init__(self, key, on_log=print, force_language=None, device=None):
        from seg_stream import _make_segment_state
        from streaming_asr import (streaming_transcribe, finish_streaming_transcribe,
                                   parse_asr_output, _normalize_punct_by_context)
        self.key, self.cfg = key, ENGINES[key]
        # 用户显式选的设备优先（APP-004 第 3 条）；NPU 档忽略（all-NPU 后端写死）。
        if device and self.cfg['kind'] == 'ov':
            self.cfg = dict(self.cfg)
            self.cfg['device'] = device
        self._st, self._finish = streaming_transcribe, finish_streaming_transcribe
        self._parse, self._norm = parse_asr_output, _normalize_punct_by_context
        self._make_state = _make_segment_state
        self.seg = Segmenter()
        # ASR 识别语种：None = 自动检测。用户在下拉里改语种后要重新建 state
        # （语种是拼进 prompt 的，state 里已经缓存了 prompt_raw）。
        self.force_language = force_language
        t0 = time.perf_counter()
        enc = _model_path(self.cfg['enc'])
        dec = _model_path(self.cfg['dec'])
        if self.cfg['kind'] == 'ov':
            from segment_encoder_backend import SegmentEncoderOVBackend
            on_log(f'加载 {self.cfg["label"]}（{self.cfg["dec"]}）…')
            self.backend = SegmentEncoderOVBackend(
                encoder_dir=enc, decoder_dir=dec, device=self.cfg['device'],
                precision='f16', cache_dir=_cache('ov_cache'))
            self.device_desc = self.cfg['device']
        else:
            import npu_embeds_backend
            from npu_delivery_backend import make_delivery_all_npu_backend
            npy = _model_path('qwen3-lm-int8sym-cleanie-ov/embed_tokens_f16.npy')
            npu_embeds_backend._load_embed_table = \
                lambda: np.asarray(np.load(npy), dtype=np.float32)
            on_log(f'加载 {self.cfg["label"]}（首次编译 NPU 模型可能要 1–2 分钟）…')
            self.backend = make_delivery_all_npu_backend(
                encoder_dir=enc, decoder_dir=dec,
                tokenizer_dir=_model_path('ov-int8-past'),
                npu_cache=_cache('npu_cache'))
            self.device_desc = 'NPU'
        self.load_s = time.perf_counter() - t0
        self._last_words = []
        # 🔴 前段的**完整文本**（接缝判据②需要看末尾的标点）⇒ 必须保留
        self._last_text = ''
        self.stats = dict(chunks=0, segs=0, proc_s=0.0, wall_s=0.0, lag_ms=None)
        self.reset()

    def reset(self):
        self.state = self._make_state(self.backend, unfixed_chunk_num=0, unfixed_token_num=5,
                                      chunk_size_sec=CHUNK_SEC,
                                      force_language=self.force_language)
        self.state.diag_log = []
        self.cur_text = ''

    def set_force_language(self, lang):
        """设置 ASR 识别语种（None/'' = 自动检测）。

        语种是通过 prompt 后缀「language {lang}<asr_text>」注入的，
        而 prompt_raw 在建 state 时就固定了，所以换语种必须重建 state。
        重建会清掉当前累积的音频与已识别文本，所以只在**没有正在识别**时调用。
        """
        if (lang or None) == (self.force_language or None):
            return False
        self.force_language = lang or None
        self.reset()
        return True

    def feed(self, pcm, t_capture):
        pre = self.state.chunk_id
        t0 = time.perf_counter()
        self._st(self.backend, pcm, self.state, max_new_tokens=32,
                 rollback_punctuation=False, enable_hallucination_reset=False,
                 adaptive_budget=True)
        self.stats['wall_s'] += time.perf_counter() - t0
        n_new = self.state.chunk_id - pre
        if n_new <= 0:
            return None
        self.stats['chunks'] += n_new
        self.stats['proc_s'] += n_new * CHUNK_SEC
        self.stats['lag_ms'] = (time.perf_counter() - t_capture) * 1000
        _, self.cur_text = self._parse(self.state._raw_decoded, user_language=None)
        outs = []
        while self.seg.due(self.state.audio_accum):
            outs.append(self._close_segment())
            if self.state.audio_accum.shape[0] == 0:
                break
        return ''.join(outs) if outs else None

    def _finalize(self):
        st = self.state
        cur_ids = self.backend.tokenizer.encode(st._raw_decoded)
        end_idx = max(1, len(cur_ids) - int(st.unfixed_token_num))
        prefix = self.backend.tokenizer.decode(cur_ids[:end_idx]).split('|')[0]
        gen = self.backend.generate_with_prefix(st, st.audio_accum, prefix, 64)
        gen = self._norm(gen).replace('\ufffd', '')
        st._raw_decoded = ((prefix + gen) if prefix else gen).split('|')[0]
        _, txt = self._parse(st._raw_decoded, user_language=None)
        return txt.split('|')[0]

    def _close_segment(self):
        carry = self.state.buffer.copy()     # 未解码残余（chunk 边界之后）交给下一段
        # 🔴 必须传 prev_text（接缝判据②要看前段末尾的标点）
        final = stitch(self._last_words, self._finalize(), self._last_text)
        if final.split():
            self._last_words = final.split()[-3:]
            self._last_text = final
        self.stats['segs'] += 1
        self.reset()
        self.state.buffer = carry
        return final

    def flush(self):
        st = self.state
        if st.audio_accum.shape[0] == 0 and st.buffer.shape[0] == 0:
            return None
        # 🔴 必须传 prev_text（接缝判据②要看前段末尾的标点）
        final = stitch(self._last_words,
                       self._finish(self.backend, st, max_new_tokens=64),
                       self._last_text)
        self.stats['segs'] += 1
        self.reset()
        self._last_words = []
        self._last_text = ''
        return final

    @property
    def rtf(self):
        s = self.stats
        return s['wall_s'] / s['proc_s'] if s['proc_s'] > 0 else 0.0

    def close(self):
        self.backend = None
        gc.collect()


# ── CUDA 引擎（audio.cpp 流式进程）──────────────────────────────────────
class _CudaProc:
    """一个 audiocpp_cli 流式会话：stdin 收 s16le PCM，stdout 逐条给 partial_text。"""

    def __init__(self, gguf, force_language=None):
        cmd = [CUDA_CLI, '--task', 'asr', '--family', 'confucius4_r2t2',
               '--model', os.path.join(CUDA_DIR, 'models', gguf), '--backend', 'cuda',
               '--mode', 'streaming', '--audio', '-', '--input-format', 's16le',
               '--input-rate', '16000', '--input-channels', '1',
               '--session-option', 'chunk_size_ms=640',
               '--session-option', 'unfixed_chunk_num=0',
               '--session-option', 'unfixed_token_num=5',
               '--session-option', 'max_tokens=32']
        # 语种提示：audiocpp_cli 用 --language <code>，与 OV 侧一样传模型认识的
        # 英文名（Chinese/English/…）。不指定就是自动检测。
        if force_language:
            cmd += ['--language', force_language]
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, bufsize=0, creationflags=flags)
        self.partial = ''
        self.final = None
        self.ready = threading.Event()      # 模型加载完成、开始读 stdin
        self.done = threading.Event()
        self.last_out = None                 # 最近一次收到 partial 的时间
        self.err_tail = []
        threading.Thread(target=self._read_out, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()

    def _read_out(self):
        for raw in iter(self.p.stdout.readline, b''):
            s = raw.decode('utf-8', 'replace').rstrip('\r\n')
            if s.startswith('audio_input='):
                self.ready.set()
            elif s.startswith('partial_text='):
                self.partial += s[len('partial_text='):]
                self.last_out = time.perf_counter()
            elif s.startswith('text_output='):
                self.final = s[len('text_output='):]
        self.ready.set()
        self.done.set()

    def _read_err(self):
        for raw in iter(self.p.stderr.readline, b''):
            self.err_tail = (self.err_tail + [raw.decode('utf-8', 'replace').rstrip()])[-20:]

    def write(self, pcm):
        b = (np.clip(pcm, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        self.p.stdin.write(b)

    def finish(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass

    def kill(self):
        try:
            self.p.kill()
        except OSError:
            pass


class CudaEngine:
    def __init__(self, key, on_log=print, force_language=None):
        self.key, self.cfg = key, ENGINES[key]
        if not CUDA_CLI or not os.path.exists(CUDA_CLI):
            raise FileNotFoundError(
                f'未找到 audio.cpp 可执行文件（audiocpp_cli.exe）：{CUDA_CLI or "<未配置>"}。'
                f'CUDA 后端需要额外的 audio.cpp 运行包，本包不自带。')
        self.seg = Segmenter()
        self.device_desc = 'CUDA'
        # ASR 识别语种：None = 自动检测。audiocpp_cli 的语种是**进程启动参数**
        # （--language），所以换语种要重启会话进程。
        self.force_language = force_language
        on_log(f'加载 {self.cfg["label"]}（预热两个进程）…')
        t0 = time.perf_counter()
        self.cur = _CudaProc(self.cfg['gguf'], force_language)
        self.spare = _CudaProc(self.cfg['gguf'], force_language)
        if not self.cur.ready.wait(120) or self.cur.done.is_set():
            raise RuntimeError('audiocpp_cli 启动失败：\n' + '\n'.join(self.cur.err_tail))
        self.load_s = time.perf_counter() - t0
        self.finishing = []                  # 已关闭 stdin、等最终文本的会话（按顺序）
        self.acc = np.zeros(0, np.float32)
        self._last_words = []
        # 🔴 前段的**完整文本**（接缝判据②需要看末尾的标点）⇒ 必须保留
        self._last_text = ''
        self.stats = dict(chunks=0, segs=0, proc_s=0.0, wall_s=0.0, lag_ms=None)

    def set_force_language(self, lang):
        """设置 ASR 识别语种（None/'' = 自动检测）。

        CUDA 侧的语种是 audiocpp_cli 的 --language 启动参数，改语种必须重启
        会话进程 —— 已积累的音频会丢弃，所以只在**没有正在识别**时调用。
        """
        if (lang or None) == (self.force_language or None):
            return False
        self.force_language = lang or None
        for p in [self.cur, self.spare] + self.finishing:
            p.kill()
        self.finishing = []
        self.cur = _CudaProc(self.cfg['gguf'], self.force_language)
        self.spare = _CudaProc(self.cfg['gguf'], self.force_language)
        self.acc = np.zeros(0, np.float32)
        self._last_words = []
        self._last_text = ''
        return True

    @property
    def cur_text(self):
        pend = ''.join(p.partial for p in self.finishing)
        return pend + self.cur.partial

    def feed(self, pcm, t_capture):
        if self.cur.done.is_set():
            raise RuntimeError('audiocpp_cli 意外退出：\n' + '\n'.join(self.cur.err_tail))
        self.cur.write(pcm)
        self.acc = np.concatenate([self.acc, pcm])
        self.stats['proc_s'] += len(pcm) / SR
        if self.seg.due(self.acc):
            self.cur.finish()
            self.finishing.append(self.cur)
            self.cur, self.spare = self.spare, _CudaProc(self.cfg['gguf'], self.force_language)
            self.acc = np.zeros(0, np.float32)
        return self._collect()

    def _collect(self):
        outs = []
        while self.finishing and self.finishing[0].done.is_set():
            p = self.finishing.pop(0)
            # 🔴 必须传 prev_text（接缝判据②要看前段末尾的标点）
            text = stitch(self._last_words,
                          p.final if p.final is not None else p.partial,
                          self._last_text)
            if text.split():
                self._last_words = text.split()[-3:]
                self._last_text = text
            self.stats['segs'] += 1
            outs.append(text)
        return ''.join(outs) if outs else None

    def flush(self):
        self.cur.finish()
        self.finishing.append(self.cur)
        for p in self.finishing:
            p.done.wait(60)
        out = self._collect()
        self.cur = self.spare
        self.spare = _CudaProc(self.cfg['gguf'], self.force_language)
        self.acc = np.zeros(0, np.float32)
        self._last_words = []
        return out

    @property
    def rtf(self):
        return 0.0                           # CLI 不回报逐块耗时

    def close(self):
        for p in [self.cur, self.spare] + self.finishing:
            p.kill()


def make_engine(key, on_log=print, force_language=None, device=None):
    """创建推理引擎。

    force_language：ASR 识别语种（模型认识的英文名，如 'Chinese'/'English'）；
    None = 自动检测。传进来后会在建 state / 起进程时生效。

    device：用户显式选的推理设备（APP-004 第 3 条）。None = 用后端表里的默认值。
    ⚠️ **NPU 档（kind='npu'）设备是写死在后端实现里的**，不接受覆盖 ——
    那条路径走的是 all-NPU 交付后端，换设备会让模型与后端不匹配。

    🔴 **只有 kind=='ov' 才接受 device 参数**：
       - kind=='cuda' → ``CudaEngine.__init__`` 没有 device 形参，
         无条件传会抛 ``TypeError: CudaEngine.__init__() got an
         unexpected keyword argument 'device'``（APP-007 实测）；
       - kind=='npu' → 设备写死 NPU，OVEngine 内部自己忽略。
    """
    kind = ENGINES[key]['kind']
    if kind == 'cuda':
        return CudaEngine(key, on_log=on_log, force_language=force_language)
    if device and kind == 'ov':
        return OVEngine(key, on_log=on_log, force_language=force_language,
                        device=device)
    return OVEngine(key, on_log=on_log, force_language=force_language)


# ── 会话（音频源 + 引擎）────────────────────────────────────────────────
class Session:
    """把音频源和引擎接起来的后台推理循环（GUI 与 CLI 共用）。

    音频源由外部构造好传进来（见 audio_source.make_source）：
    麦克风 / 系统声音（WASAPI loopback）/ 音频文件三选一。
    """

    def __init__(self, engine, source, on_final=None):
        self.engine = engine
        self.src = source
        # 必须复用音源自己的队列：音源是在外面构造的，它往自己的队列里送数据。
        # 这里另建一个队列的话，数据永远进不来（表现为「音频 0.0s，队列空」）。
        self.q = source.out_q
        self.on_final = on_final or (lambda t: None)
        self.audio_s = 0.0
        self.running = False
        self.error = None
        self.ended = threading.Event()

    def start(self):
        self.running = True
        self.src.start()
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.src.stop()

    @property
    def backlog_s(self):
        return self.q.qsize() * BLOCK_MS / 1000.0

    def _loop(self):
        try:
            while self.running:
                try:
                    item = self.q.get(timeout=0.2)
                except queue.Empty:
                    continue
                if item is None:
                    break
                pcm, t_cap = item
                pcm = resample_to_16k(pcm, self.src.src_sr)
                self.audio_s += len(pcm) / SR
                final = self.engine.feed(pcm, t_cap)
                if final:
                    self.on_final(final)
            tail = self.engine.flush()
            if tail:
                self.on_final(tail)
        except Exception as e:
            self.error = e
        finally:
            self.running = False
            self.ended.set()


# ── GUI ────────────────────────────────────────────────────────────────
class CaptionOverlay:
    """屏幕底部的置顶半透明字幕条（**鼠标穿透**，靠独立把手拖动）。

    两行（APP-007 用户决策）：
      第一行 定稿译文（青 #5fd7d7）
      第二行 实时识别（黄 #ffd75e）
    ⚠️ 已删除：定稿原文（白 #f2f2f2）、草稿译文预览（浅蓝 #7aa7d0）。
    定稿原文仍在**主文本区**与**保存的 txt**里，只是不再上屏幕字幕。

    鼠标穿透（APP-007 第 4 项）：
      主窗口设 ``WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE``
      ⇒ **完全穿透**，其后方的桌面元素照常点击/拖拽；
      另建一个**不穿透**的小 Toplevel「拖拽把手」（44×24）贴在左上角，
      拖它就同步移动主窗口。

    🔴 为什么要有把手：Windows 上加了 ``WS_EX_TRANSPARENT`` 之后窗口
    **收不到鼠标消息** ⇒ 老式的「直接拖字幕」必然失效。
    把手不穿透，是唯一的拖拽入口（也是关掉字幕的入口）。
    """

    HANDLE_W = 44
    HANDLE_H = 24
    HANDLE_BG = '#2b6cb0'

    def __init__(self, root, font_size=26, click_through=True):
        import tkinter as tk
        import tkinter.font as tkfont
        self.root = root
        self.on_close = None            # 把手右键菜单「关闭屏幕字幕」的回调
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        try:
            self.win.attributes('-alpha', 0.86)
        except Exception:
            pass
        self.font = tkfont.Font(family='Microsoft YaHei UI', size=font_size)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.w = int(sw * 0.8)
        line = self.font.metrics('linespace')
        # 2 行：定稿译文 / 实时识别
        h = 2 * line + 30
        self.win.geometry(f'{self.w}x{h}+{(sw - self.w) // 2}+{sh - h - int(sh * 0.07)}')
        self.win.configure(bg='#111111')
        # ── 两行 Label（顺序即显示顺序：译文在上，实时在下）──
        self.mt = tk.Label(self.win, text='', fg='#5fd7d7', bg='#111111',
                           font=self.font, anchor='w')
        self.partial = tk.Label(self.win, text='', fg='#ffd75e', bg='#111111',
                                font=self.font, anchor='w')
        self.mt.pack(fill='x', padx=20, pady=(10, 0))
        self.partial.pack(fill='x', padx=20)
        # 兜底拖动：**穿透失败时**（降级路径）字幕窗口本身仍可直接拖。
        for wdg in (self.win, self.mt, self.partial):
            wdg.bind('<ButtonPress-1>', self._press)
            wdg.bind('<B1-Motion>', self._drag)

        # ── 独立拖拽把手（**不穿透** ⇒ 唯一能接到鼠标的地方）──
        self.handle = tk.Toplevel(root)
        self.handle.overrideredirect(True)
        self.handle.attributes('-topmost', True)
        self.handle.configure(bg=self.HANDLE_BG)
        self.handle_lbl = tk.Label(self.handle, text='≡', bg=self.HANDLE_BG,
                                   fg='#ffffff', font=('Consolas', 12))
        self.handle_lbl.pack(fill='both', expand=True)
        for wdg in (self.handle, self.handle_lbl):
            wdg.bind('<ButtonPress-1>', self._press_handle)
            wdg.bind('<B1-Motion>', self._drag_handle)
        self.handle.bind('<Button-3>', self._handle_menu)
        self.handle_lbl.bind('<Button-3>', self._handle_menu)
        # 把手相对字幕窗口左上角的偏移（拖动时保持不变）
        # ⚠️ 把手放在字幕窗**左上角外侧**（-HANDLE_W-6, -HANDLE_H-6），
        #    不放在内侧。理由：字幕窗是 **WS_EX_LAYERED**（带 alpha 0.86），
        #    Layered 窗口在屏幕截图/合成时可能不绘出被它覆盖的区域 ⇒
        #    放在内侧的话把手会「看不见」（实测截图里消失）。
        #    放外侧同时保证字幕第一行不被挡。
        self._h_off = (-self.HANDLE_W - 6, -self.HANDLE_H - 6)
        self._grab = None

        # ── 鼠标穿透 ──
        # ⚠️ 必须在窗口**已映射**之后做（Tk 的 overrideredirect 窗口在
        #    update_idletasks() 之前还没真正创建），否则样式会丢。
        self.click_through = False
        try:
            self.win.update_idletasks()
        except Exception:
            pass
        if click_through:
            try:
                import win_clickthrough as wct
                self.click_through = wct.enable_click_through(self.win)
            except Exception:
                self.click_through = False

        # ⚠️ **必须在字幕窗映射之后再摆把手**：overrideredirect 的 Toplevel
        #    在 update_idletasks() 之前还没真正创建 ⇒ 此时 ``win.winfo_x()``
        #    返回 0（相对 root 的原点）⇒ 把手会被放到屏幕左上角，
        #    看起来「把手不见了」。实测初始位置 (12,8)，应是 (205+12, 1069+8)。
        self._place_handle()

    # -- 位置 ------------------------------------------------------------
    def _place_handle(self, x=None, y=None):
        """把手贴到字幕窗口左上角（跟随移动）。

        ⚠️ **不能依赖 ``winfo_x()``**：``geometry('+x+y')`` 之后要等事件循环
        刷新，``winfo_x()`` 立刻读到的还是**旧坐标** ⇒ 把手会掉队。
        ⇒ 调用方把目标坐标传进来。
        """
        try:
            if x is None or y is None:
                # ⚠️ 用 winfo_rootx/y（屏幕坐标）。winfo_x/y 是相对父容器的，
                #    对 overrideredirect 的 Toplevel 在未映射时返回 0。
                x, y = self.win.winfo_rootx(), self.win.winfo_rooty()
            hx = int(x) + self._h_off[0]
            hy = int(y) + self._h_off[1]
            self.handle.geometry(f'{self.HANDLE_W}x{self.HANDLE_H}+{hx}+{hy}')
        except Exception:
            pass

    def move_to(self, x, y):
        """移动字幕窗口 + 把手（两者绑定）。"""
        x, y = int(x), int(y)
        self.win.geometry(f'+{x}+{y}')
        self._place_handle(x, y)

    # -- 拖动（兜底：字幕窗口本身）---------------------------------------
    def _press(self, e):
        self._dx, self._dy = e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y()

    def _drag(self, e):
        self.move_to(e.x_root - self._dx, e.y_root - self._dy)

    # -- 拖动（把手：主路径）---------------------------------------------
    def _press_handle(self, e):
        """记录把手按下时的锚点（鼠标根坐标 + 字幕窗口原点）。"""
        self._grab = (e.x_root, e.y_root,
                      self.win.winfo_x(), self.win.winfo_y())

    def _drag_handle(self, e):
        """拖把手 ⇒ 字幕窗口跟着走（把手与窗口的相对位置保持不变）。"""
        if not self._grab:
            self._press_handle(e)
            return
        mx, my, ox, oy = self._grab
        self.move_to(ox + (e.x_root - mx), oy + (e.y_root - my))

    # -- 把手右键菜单 ----------------------------------------------------
    def _handle_menu(self, e):
        """右键菜单：切换穿透 / 关闭字幕。

        🔴 穿透之后鼠标**点不到字幕窗口** ⇒ 必须有别的入口关掉它。
        """
        import tkinter as tk
        m = tk.Menu(self.handle, tearoff=0)
        m.add_command(
            label='鼠标穿透：开（拖我移动字幕）' if self.click_through
            else '鼠标穿透：关',
            command=self._toggle_click_through)
        m.add_command(label='关闭屏幕字幕', command=self._request_close)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _toggle_click_through(self):
        """开/关穿透。返回是否切换成功（失败保持原状）。"""
        try:
            import win_clickthrough as wct
            if self.click_through:
                self.click_through = not wct.disable_click_through(self.win)
            else:
                self.click_through = wct.enable_click_through(self.win)
        except Exception:
            self.click_through = False

    def _request_close(self):
        """通知 App 关闭字幕（穿透后鼠标点不到窗口 ⇒ 走回调）。"""
        cb = getattr(self, 'on_close', None)
        if cb:
            cb()

    def _tail_fit(self, text):
        """取能在一行内放下的最长结尾部分（按实际字体宽度量）。"""
        text = text.strip()
        room = self.w - 50
        if self.font.measure(text) <= room:
            return text
        lo, hi = 0, len(text)
        while lo < hi:                       # 找最小的起点 k，使 text[k:] 放得下
            mid = (lo + hi) // 2
            if self.font.measure('…' + text[mid:]) <= room:
                hi = mid
            else:
                lo = mid + 1
        return '…' + text[lo:].lstrip()

    def show(self, mt='', partial=''):
        """更新两行。

        ⚠️ 签名已从 4 参（final_tail, partial, mt, draft）改为 2 参
        （mt, partial）—— 定稿原文与草稿预览不再上屏幕字幕。
        """
        self.mt.configure(text=self._tail_fit(mt[-400:]) if mt else '')
        self.partial.configure(text=self._tail_fit(partial[-400:]) if partial else '')

    def destroy(self):
        try:
            self.handle.destroy()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


class App:
    POLL_MS = 80

    def __init__(self, root, args):
        import tkinter as tk
        from tkinter import ttk, scrolledtext
        self.tk, self.root, self.args = tk, root, args
        self.engine = None
        self.engine_key = None
        self.session = None
        self.final_text = ''
        self.blocks = []                  # [(定稿原文, 译文 or None)]
        self.overlay = None
        self._loading = False
        # auto=False：翻译模型等 ASR 引擎就绪后再加载，避免两个模型在同一 GPU 上并行编译
        #
        # on_log 必须线程安全：翻译/引擎都在后台线程，直接 root.after() 会和主线程
        # 互锁（Tk 的 after 不是线程安全的 —— 它要等主线程的 Tcl 锁；主线程一旦在
        # wait/join 上阻塞，后台线程就永远卡在这里，表现为「翻译不跑了」）。
        # 所以跨线程只往队列里塞，由 _poll 在主线程排空。
        self._ui_log_q = queue.Queue()
        # 设备解析结果（APP-004 第 3 条）：命令行 > 配置文件 > 推荐默认值。
        # 已在 main() 里解析过一次并回退过不可用的设备。
        self._dev_selected = {
            'asr': getattr(args, 'asr_device', None) or 'GPU.0',
            'mt': getattr(args, 'mt_device', None) or 'GPU.0',
            'tts': getattr(args, 'tts_device', None) or 'NPU',
        }
        self._device_notes = list(getattr(args, 'device_notes', []) or [])
        self.mt = TranslationService(
            target=args.translate, device=self._dev_selected['mt'], auto=False,
            engine_key=args.mt_engine, use_ctx=getattr(args, 'mt_ctx', False),
            glossary=getattr(args, 'mt_glossary', False),
            draft=_init_draft_flag(args),
            on_log=self._ui_log)

        root.title('Confucius4-R2T2 实时字幕 · 多后端测试')
        # ⚠️ 1080x820：三分区改**纵向三行**后（每行 = 控件行 + 说明行），
        #    700 高装不下，主文本区会被压扁。820 能让三行都完整显示。
        root.geometry('1080x820')

        # ── 顶栏 ──────────────────────────────────────────────────────
        # APP-007：ASR 后端与翻译目标语言的下拉**移入三分区**，
        # 顶栏只留「开始 / 清空 / 保存 / 屏幕字幕」这类全局操作。
        top = ttk.Frame(root, padding=(10, 8))
        top.pack(fill='x')
        ttk.Label(top, text='Confucius4 实时字幕').pack(side='left')

        self.btn = ttk.Button(top, text='▶ 开始', command=self.toggle, state='disabled')
        self.btn.pack(side='left', padx=(12, 0))
        ttk.Button(top, text='清空', command=self.clear).pack(side='left', padx=4)
        ttk.Button(top, text='保存', command=self.save).pack(side='left')
        self.var_overlay = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text='屏幕字幕', variable=self.var_overlay,
                        command=self._toggle_overlay).pack(side='left', padx=10)

        self.var_note = tk.StringVar(value='')
        ttk.Label(root, textvariable=self.var_note, foreground='#555',
                  padding=(12, 0)).pack(fill='x')

        # ── 状态栏（APP-007：从窗口底部迁到主面板顶部）────────────────
        # ⚠️ **pack 顺序是关键**：状态栏必须排在 self.txt **之前** pack。
        #    pack 按顺序分配空间，先 pack 的控件先拿到请求高度；
        #    以前状态栏在最后、而 ScrolledText 默认请求 718px（24 行），
        #    在 1080x700 窗口里 pack 优先满足它 ⇒ 状态栏被压成 **1px**
        #    （实测 700/900 窗口高都是 1px，1000px 才恢复 29px）。
        #    ⚠️ 这跟「全屏」没有任何关系 —— 代码里从来没有全屏逻辑。
        bot = ttk.Frame(root, padding=(10, 4))
        bot.pack(fill='x')
        self.var_meter = tk.StringVar(value='')
        self.lbl_meter = ttk.Label(bot, textvariable=self.var_meter, font=('Consolas', 10))
        self.lbl_meter.pack(side='left')
        self.var_status = tk.StringVar(value='')
        ttk.Label(bot, textvariable=self.var_status, foreground='#555').pack(side='right')

        # 音频来源单独一行：三种输入（麦克风 / 系统声音 / 音频文件）
        # 的设备选择互斥，挤在一行会让顶栏没法看。
        srow = ttk.Frame(root, padding=(12, 4))
        srow.pack(fill='x')
        ttk.Label(srow, text='音频来源').pack(side='left')
        self.source_keys = ['mic', 'system', 'file']
        self._src_label = {k: audio_source.SOURCES[k] for k in self.source_keys}
        self._src_label_back = {v: k for k, v in self._src_label.items()}
        self.var_source = tk.StringVar(value=self._src_label[args.source])
        self.cb_source = ttk.Combobox(srow, state='readonly', width=12,
                                      textvariable=self.var_source,
                                      values=[self._src_label[k] for k in self.source_keys])
        self.cb_source.pack(side='left', padx=(4, 12))
        self.cb_source.bind('<<ComboboxSelected>>', self._on_source_changed)

        # ASR 识别语种：'auto' = 自动检测（不注入语种提示），其余是模型
        # support_languages 里的英文名。
        # ⚠️ APP-007：这个下拉**移入 ASR 分区**（它属于识别行为，
        #    跟采集方式无关，放在音频来源行里反而挤）。
        #    这里只先算出 label 映射，控件本身在三分区里创建。
        self._asr_lang_keys = [ASR_LANG_AUTO] + list(ASR_LANGS)
        self._asr_lang_label = {k: asr_lang_label(k) for k in self._asr_lang_keys}
        self._asr_lang_label_back = {v: k for k, v in self._asr_lang_label.items()}
        init_lang = getattr(args, 'asr_lang', ASR_LANG_AUTO) or ASR_LANG_AUTO
        if init_lang not in self._asr_lang_keys:
            init_lang = ASR_LANG_AUTO
        self.var_asr_lang = tk.StringVar(value=self._asr_lang_label[init_lang])

        # 麦克风设备
        self.mics = list_input_devices()
        self.var_mic = tk.StringVar(value=self.mics[0][1] if self.mics else '（未找到输入设备）')
        self.cb_mic = ttk.Combobox(srow, state='readonly', width=32,
                                   textvariable=self.var_mic,
                                   values=[m[1] for m in self.mics])
        self.cb_mic.pack(side='left', padx=(4, 12))

        # 系统输出设备（loopback 目标）
        self.outs = list_output_devices()          # [(wasapi_id, 显示名), ...]
        self._out_label = {oid: name for oid, name in self.outs}
        self._out_label_back = {name: oid for oid, name in self.outs}
        dflt_out = default_output_device_id()
        init_out = dflt_out if dflt_out in self._out_label else \
            (self.outs[0][0] if self.outs else None)
        self.var_out = tk.StringVar(
            value=self._out_label.get(init_out, '（未找到输出设备）'))
        self.cb_out = ttk.Combobox(srow, state='readonly', width=32,
                                   textvariable=self.var_out,
                                   values=[self._out_label[oid] for oid, _ in self.outs])
        self.cb_out.pack(side='left', padx=(4, 12))

        # 音频文件
        self.var_file = tk.StringVar(value=args.file or '')
        self.entry_file = ttk.Entry(srow, width=30, textvariable=self.var_file)
        self.entry_file.pack(side='left', padx=(4, 4))
        self.btn_pick_file = ttk.Button(srow, text='选择…', command=self._pick_file)
        self.btn_pick_file.pack(side='left', padx=(0, 8))

        # 文件回放速度（0=全速跑批，1.0=实时）与循环播放
        self._speed_label = {0.0: '全速', 0.5: '0.5×', 1.0: '1.0×（实时）', 1.5: '1.5×', 2.0: '2.0×'}
        self._speed_back = {v: k for k, v in self._speed_label.items()}
        self.var_speed = tk.StringVar(value=self._speed_label[1.0])
        self.cb_speed = ttk.Combobox(srow, state='readonly', width=12,
                                     textvariable=self.var_speed,
                                     values=list(self._speed_label.values()))
        self.cb_speed.pack(side='left', padx=(0, 8))
        self.var_loop = tk.BooleanVar(value=False)
        self.cb_loop = ttk.Checkbutton(srow, text='循环', variable=self.var_loop)
        self.cb_loop.pack(side='left', padx=(0, 8))

        self.var_source_note = tk.StringVar(value='')
        self.lbl_source_note = ttk.Label(srow, textvariable=self.var_source_note,
                                         foreground='#555')
        self.lbl_source_note.pack(side='left', padx=(10, 0))

        # ── 三个配置分区：ASR / 翻译 / 语音（APP-007）───────────────
        #    每个分区**只保留一个「设备+精度」组合下拉**（用户决策）。
        #    原来的「推理设备」行（drow）把三个独立设备下拉挤在一行，
        #    且 ASR/MT 的后端下拉标签里本来就含设备名 ⇒ 语义重叠。
        #
        #    ⚠️ **纵向三行**，不是横向三列：1080 宽装不下三列
        #       （实测「语音输出」整块被裁掉，翻译分区的 note 也被切）。
        #       每行结构 = [控件行] + [说明文字行]，长 note 单独占一行，
        #       不会被相邻控件挤没。
        #    ⚠️ 继续用 pack（项目全仓库 0 个 grid）。
        self._dev_avail = device_config.available_devices()
        self._dev_label_back = {device_config.device_label(d): d
                                for d in self._dev_avail}
        # 命令行 > 配置文件 > 推荐默认值（device_config.get_devices 已解析）
        self._dev_choices = dict(self._dev_selected)

        areas = ttk.Frame(root, padding=(10, 4))
        areas.pack(fill='x')

        # ---- ASR 分区 ----
        f_asr = ttk.LabelFrame(areas, text='ASR 识别', padding=(8, 4))
        f_asr.pack(fill='x', pady=2)
        row_asr = ttk.Frame(f_asr)
        row_asr.pack(fill='x')
        self._asr_opts = build_asr_options(self._dev_avail)
        self._asr_opt_by_id = {o['id']: o for o in self._asr_opts}
        self.var_asr_combo = tk.StringVar(value='')
        self.cb_asr_combo = ttk.Combobox(
            row_asr, state='readonly', width=24, textvariable=self.var_asr_combo,
            values=[o['label'] for o in self._asr_opts])
        self.cb_asr_combo.pack(side='left', padx=(0, 8))
        self.cb_asr_combo.bind('<<ComboboxSelected>>', self._on_asr_combo_changed)
        ttk.Label(row_asr, text='识别语种').pack(side='left', padx=(0, 4))
        self.cb_asr_lang = ttk.Combobox(
            row_asr, state='readonly', width=12, textvariable=self.var_asr_lang,
            values=[self._asr_lang_label[k] for k in self._asr_lang_keys])
        self.cb_asr_lang.pack(side='left', padx=(0, 8))
        self.cb_asr_lang.bind('<<ComboboxSelected>>', self._on_asr_lang_changed)
        self.var_asr_note = tk.StringVar(value='')
        ttk.Label(f_asr, textvariable=self.var_asr_note,
                  foreground='#555').pack(fill='x')

        # ---- 翻译分区 ----
        f_mt = ttk.LabelFrame(areas, text='翻译', padding=(8, 4))
        f_mt.pack(fill='x', pady=2)
        row_mt = ttk.Frame(f_mt)
        row_mt.pack(fill='x')
        ttk.Label(row_mt, text='目标语言').pack(side='left', padx=(0, 4))
        self.mt_keys = list(TARGETS)
        self.var_mt = tk.StringVar(value=TARGET_LABELS[args.translate])
        self.cb_mt = ttk.Combobox(
            row_mt, state='readonly', width=8, textvariable=self.var_mt,
            values=[TARGET_LABELS[k] for k in self.mt_keys])
        self.cb_mt.pack(side='left', padx=(0, 8))
        self.cb_mt.bind('<<ComboboxSelected>>', self._on_mt_changed)
        self._mt_opts = build_mt_options(self._dev_avail)
        self._mt_opt_by_id = {o['id']: o for o in self._mt_opts}
        self.var_mt_combo = tk.StringVar(value='')
        self.cb_mt_combo = ttk.Combobox(
            row_mt, state='readonly', width=26, textvariable=self.var_mt_combo,
            values=[o['label'] for o in self._mt_opts])
        self.cb_mt_combo.pack(side='left', padx=(0, 8))
        self.cb_mt_combo.bind('<<ComboboxSelected>>', self._on_mt_combo_changed)
        # 草稿译文开关：默认**关闭**，只翻已经定稿的文本。勾上后还会实时翻译
        # 还没定稿的那句，但会占翻译算力、抬高 ASR 积压。
        self.var_mt_draft = tk.BooleanVar(value=_init_draft_flag(args))
        self.chk_mt_draft = ttk.Checkbutton(
            row_mt, text='草稿译文 Draft', variable=self.var_mt_draft,
            command=self._on_mt_draft_toggled)
        self.chk_mt_draft.pack(side='left', padx=(0, 8))
        # 重试按钮：翻译模型加载失败时（状态栏显示「失败」）一键重试，
        # 不用重启整个程序。加载中时禁用。
        self.btn_mt_retry = ttk.Button(row_mt, text='↻ 重试翻译 Retry', width=16,
                                       command=self._retry_mt, state='disabled')
        self.btn_mt_retry.pack(side='left', padx=(0, 8))
        self.var_mt_note = tk.StringVar(value='')
        ttk.Label(f_mt, textvariable=self.var_mt_note, foreground='#555').pack(fill='x')
        self.mt.set_draft(self.var_mt_draft.get())

        # ---- 语音分区（TTS，C-101 P4 第 4 条）----
        f_tts = ttk.LabelFrame(areas, text='语音输出', padding=(8, 4))
        f_tts.pack(fill='x', pady=2)
        row_tts = ttk.Frame(f_tts)
        row_tts.pack(fill='x')
        # 🔴 **TTS 默认开启**（APP-014：TTS 已转为正式功能）
        #    ⚠️ 兼容：命令行显式给了 `--tts off` 时仍按 off；
        #       没给（`None`）⇒ 按**默认开启**处理。
        _tts_arg = getattr(args, 'tts', None)
        self.var_tts_on = tk.BooleanVar(
            value=(True if _tts_arg is None else _tts_arg == 'on'))
        self.chk_tts = ttk.Checkbutton(row_tts, text='开启', variable=self.var_tts_on,
                                       command=self._on_tts_toggled)
        self.chk_tts.pack(side='left', padx=(0, 8))
        self._tts_opts = build_tts_options(self._dev_avail)
        self._tts_opt_by_id = {o['id']: o for o in self._tts_opts}
        self.var_tts_combo = tk.StringVar(value='')
        self.cb_tts_combo = ttk.Combobox(
            row_tts, state='readonly', width=22, textvariable=self.var_tts_combo,
            values=[o['label'] for o in self._tts_opts])
        self.cb_tts_combo.pack(side='left', padx=(0, 8))
        self.cb_tts_combo.bind('<<ComboboxSelected>>', self._on_tts_combo_changed)
        ttk.Label(row_tts, text='音色').pack(side='left', padx=(0, 4))
        # 🔴🔴 **只保留音色 A**（APP-007 交付修正，2026-10-23）。
        #    客户包只带 `models/qwen3tts/voices/preset_A.wav`（BRIEF 硬要求：
        #    同事音色 B / 克隆音色 C 一律不进包）。
        #    ⚠️ 之前这里写死 ['A','B','clone'] 是**错的**：
        #      - 选 B ⇒ tts_worker._setup_babelvox_voice 回落 preset_voice_path()
        #        ⇒ **实际发的是音色 A 的声音**（静默错标，用户无从察觉）；
        #      - 选 clone ⇒ 需要 voices/clone_C.npz + torch ⇒ 包内两者都没有
        #        ⇒ 失败回落内置 speaker cindy。
        #    ⇒ 列出来只会让用户选了却拿不到对应的音色。
        self.tts_voices = ['A']
        self._tts_voice_label = {'A': '预设 A'}
        self._tts_voice_back = {v: k for k, v in self._tts_voice_label.items()}
        self.var_tts_voice = tk.StringVar(
            value=self._tts_voice_label.get(args.tts_voice, 'A'))
        self.cb_tts_voice = ttk.Combobox(
            row_tts, state='readonly', width=12, textvariable=self.var_tts_voice,
            values=[self._tts_voice_label[k] for k in self.tts_voices])
        self.cb_tts_voice.pack(side='left', padx=(0, 8))
        self.cb_tts_voice.bind('<<ComboboxSelected>>', self._on_tts_voice_changed)
        ttk.Label(row_tts, text='输出设备').pack(side='left', padx=(0, 4))
        # 复用 App 已有的输出设备列表（MME/WASAPI）—— C-101 P4 第 4 条
        self.var_tts_out = tk.StringVar(
            value=self._out_label.get(init_out, '（未找到输出设备）'))
        self.cb_tts_out = ttk.Combobox(
            row_tts, state='readonly', width=24, textvariable=self.var_tts_out,
            values=[self._out_label[oid] for oid, _ in self.outs])
        self.cb_tts_out.pack(side='left', padx=(0, 8))
        self.tts = None                      # TTSService 实例
        self.var_tts_note = tk.StringVar(value='')

        # 🔴 **耳机提示**（APP-014：TTS 转正式功能 ⇒ 默认开启）
        #    TTS 从**系统输出设备**播放，而 ASR 可能采**系统回环**⇒
        #    不戴耳机会把 TTS 的声音**再采回去** ⇒ 自激 / 回声 / 重复词。
        #    ⇒ 在开关旁边常驻一行提示（不是弹窗，避免打断会议）。
        ttk.Label(row_tts, text='⚠️ 请佩戴耳机，避免回授',
                  foreground='#b26a00').pack(side='left', padx=(4, 0))

        ttk.Label(f_tts, textvariable=self.var_tts_note, foreground='#555').pack(fill='x')

        # ⚠️ height=10（行）：**这是状态栏可见的关键**。
        #    ScrolledText 默认请求高度 718 px（24 行），在 1080x700 窗口里
        #    pack 优先满足它 ⇒ 状态栏被压成 1 px（实测）。
        #    配合「bot 在 txt 之前 pack」，窗口再小也是压 txt 而不是压状态栏。
        self.txt = scrolledtext.ScrolledText(root, wrap='word', font=('Microsoft YaHei UI', 13),
                                             relief='flat', padx=12, pady=10, spacing3=6,
                                             height=10)
        self.txt.pack(fill='both', expand=True, padx=10, pady=(4, 4))
        self.txt.tag_config('partial', foreground='#9a9a9a')
        self.txt.tag_config('mt', foreground='#1565c0')            # 定稿译文
        self.txt.tag_config('mt_partial', foreground='#7aa7d0')    # 实时译文草稿
        self.txt.configure(state='disabled')

        # ── 三个组合下拉的初值（命令行 > 配置文件 > 推荐默认）──────────
        # ⚠️ 找不到匹配项 ⇒ 回退到该分区的默认选项 + **明确提示**（不能卡死）。
        self._combo_notes = []
        self._asr_effective_device = None      # 当前引擎实际用的设备
        self._tts_precision = getattr(args, 'tts_precision', 'f32')
        self._init_combo_values(args)

        self._toggle_overlay()
        self._sync_source_widgets()
        root.protocol('WM_DELETE_WINDOW', self.quit)
        # 预热 transformers / openvino_genai 的导入 —— 必须在**主线程**里做，
        # 而且要在任何后台线程起之前。
        #
        # 原因：transformers 4.57 是延迟导入，两个线程同时首次 import 同一个类
        # 会抛 ImportError（实测 8 线程并发有 2 个失败）。ASR 引擎线程和翻译线程
        # 都会 import transformers，并发时翻译侧就起不来（表现为「翻译一直加载中」）。
        # 这里先在主线程导入完，后台线程再 import 就只是取现成的属性。
        try:
            _pw = prewarm_transformers()
            if _pw > 0.2:
                self._ui_log(f'prewarm transformers {_pw:.1f}s')
        except Exception as e:
            self._ui_log(f'prewarm transformers failed: {type(e).__name__}: {e}')
        self.load_engine()
        root.after(self.POLL_MS, self._poll)

    # -- 组合下拉（APP-007）---------------------------------------------
    def _resolve_mt_engine_key(self, key, dev):
        """把翻译引擎键解析成**实际模型键**（用户决策：下拉里不显示 auto）。

        'auto' 的 device 是 None、model 是 None（走 translator.DEFAULT_MODEL），
        语义上不是「某个设备 × 某个量化」⇒ 启动时把它解析成同设备下
        **本机确实存在**的实际引擎（gpu_int8cw / npu_int8cw ...）。
        """
        if key != 'auto':
            return key
        cands = [k for k in MT_ENGINES
                 if k != 'auto' and MT_ENGINES[k].get('device') == dev]
        for k in cands:
            if mt_available(k):
                return k
        for k in cands:
            if k in MT_ENGINES:
                return k
        return next((k for k in MT_ENGINES if k != 'auto'), 'auto')

    def _init_combo_values(self, args):
        """给三个组合下拉设初值；找不到匹配项就回退并提示。"""
        # ---- ASR ----
        want = f'{args.engine}@{self._dev_selected["asr"]}'
        opt = self._asr_opt_by_id.get(want)
        if opt is None:
            opt = next((o for o in self._asr_opts
                        if o['engine'] == args.engine), None)   # 同引擎、任意设备
        if opt is None and self._asr_opts:
            opt = self._asr_opts[0]
        if opt is None:
            self._combo_notes.append('ASR：没有可用后端')
            self.var_asr_note.set('本机未检测到 GPU/NPU，CPU 推理已隐藏；'
                                  '可用命令行 --asr-device CPU 启动')
        else:
            self.var_asr_combo.set(opt['label'])
            self._dev_choices['asr'] = opt['device']
            self.var_note.set(opt.get('note', ''))

        # ---- 翻译（auto 先解析成实际模型键）----
        mt_key = self._resolve_mt_engine_key(args.mt_engine, self._dev_selected['mt'])
        # ⚠️ 翻译组合的 id 是「量化@设备」（不是 engine@设备，见 build_mt_options），
        #    且 engine_key 与量化是**多对一**（gpu_int8cw / npu_int8cw 同模型）。
        #    ⇒ 先按「同 engine + 同设备」找，找不到再按「同设备 + 同精度」找。
        want_dev = self._dev_selected['mt']
        opt = next((o for o in self._mt_opts
                    if o['engine'] == mt_key and o['device'] == want_dev), None)
        if opt is None:
            want_prec = MT_PRECISION.get(mt_key)
            opt = next((o for o in self._mt_opts
                        if o['device'] == want_dev and o['precision'] == want_prec),
                       None)
        if opt is None:
            opt = next((o for o in self._mt_opts
                        if o['engine'] == mt_key), None)   # 同 engine、任意设备
        if opt is None and self._mt_opts:
            opt = self._mt_opts[0]
        if opt is None:
            self._combo_notes.append('翻译：没有可用后端')
            self.var_mt_note.set('本机未检测到 GPU/NPU，CPU 推理已隐藏；'
                                  '可用命令行 --mt-device CPU 启动')
        else:
            self.var_mt_combo.set(opt['label'])
            self._dev_choices['mt'] = opt['device']
            self.var_mt_note.set(opt.get('note', ''))
            # 🔴 **GUI 显示的组合必须真的生效**：TranslationService 是用
            #    args.mt_engine（可能是 'auto'）建的 ⇒ 'auto' 恒等于 INT8-CW。
            #    若组合落在 INT4-CW（或别的 engine 键），必须在这里
            #    set_engine → set_device 纠正，否则界面显示与实际跑的不一致。
            #    顺序铁律：先 set_engine，后 set_device。
            try:
                if opt['engine'] != getattr(self.mt, 'engine_key', None):
                    self.mt.set_engine(opt['engine'])
                self.mt.set_device(opt['device'])
            except Exception as e:
                self._combo_notes.append(f'翻译后端初始化失败：{e}')

        # ---- 语音 ----
        want = f'{self._dev_selected["tts"]}@{self._tts_precision}'
        opt = self._tts_opt_by_id.get(want)
        if opt is None:
            opt = next((o for o in self._tts_opts
                        if o['device'] == self._dev_selected['tts']), None)
        if opt is None and self._tts_opts:
            opt = self._tts_opts[0]
        if opt is None:
            self._combo_notes.append('语音：没有可用组合')
            self.var_tts_note.set('本机未检测到 GPU/NPU，CPU 推理已隐藏；'
                                  '可用命令行 --tts-device CPU 启动')
        else:
            self.var_tts_combo.set(opt['label'])
            self._dev_choices['tts'] = opt['device']
            self._tts_precision = opt['precision']
            self.var_tts_note.set(self._tts_note_text(opt))

        # ⚠️ TranslationService.__init__ 里的 _apply_engine_defaults 会用
        #    MT_ENGINES[key]['device'] **覆盖**显式传入的 device ⇒ 上面的
        #    set_engine → set_device 已一并纠正（顺序铁律：先 engine 后 device）。

        if self._combo_notes:
            msg = '；'.join(self._combo_notes)
            self.var_note.set(msg)
            self.var_status.set(msg)
        device_config.save_config(dict(self._dev_choices))

    def _cur_asr_opt(self):
        """当前选中的 ASR 组合选项（按 label 反查；label 必须全局唯一）。"""
        lab = self.var_asr_combo.get()
        for o in self._asr_opts:
            if o['label'] == lab:
                return o
        return None

    def _cur_mt_opt(self):
        lab = self.var_mt_combo.get()
        for o in self._mt_opts:
            if o['label'] == lab:
                return o
        return None

    def _cur_tts_opt(self):
        lab = self.var_tts_combo.get()
        for o in self._tts_opts:
            if o['label'] == lab:
                return o
        return None

    # -- 设备 / 引擎 ------------------------------------------------------
    def _mic_index(self):
        for i, label in self.mics:
            if label == self.var_mic.get():
                return i
        return None

    def _out_device_id(self):
        """当前选中的系统输出设备 WASAPI id（None = 系统默认）。"""
        return self._out_label_back.get(self.var_out.get())

    # -- 音频来源 --------------------------------------------------------
    def _cur_source_key(self):
        return self._src_label_back.get(self.var_source.get(), 'mic')

    # -- ASR 识别语种 -----------------------------------------------------
    def _cur_asr_lang(self):
        """当前选中的识别语种（英文名；None = 自动检测）。"""
        k = self._asr_lang_label_back.get(self.var_asr_lang.get(), ASR_LANG_AUTO)
        return None if k == ASR_LANG_AUTO else k

    def _on_asr_lang_changed(self, *_a):
        """切换识别语种。

        语种是通过 prompt 后缀注入的（state.prompt_raw 建 state 时就固定了），
        所以必须重建 state。CUDA 后端的语种更是 audiocpp_cli 的启动参数，
        要重启会话进程。

        正在识别时切换会丢掉已积累的音频 —— 与「切换音频来源」一致，
        这里也先停掉当前会话，让用户重新点「开始」。
        """
        lang = self._cur_asr_lang()
        if self.session and self.session.running:
            self.stop()
            self.var_status.set('识别语种已切换，请重新点「开始」')
        if self.engine is not None:
            try:
                self.engine.set_force_language(lang)
            except Exception as e:
                self._ui_log(f'切换识别语种失败：{type(e).__name__}: {e}')
        self._ui_log(f'ASR 识别语种：{lang or "自动检测"}')

    def _on_source_changed(self, *_a):
        """切换音频来源：只显示与该来源相关的控件。

        正在识别时切换来源需要先停掉当前会话 —— 采集线程已经在跑了，
        换源必须重新起一个 Session。
        """
        if self.session and self.session.running:
            self.stop()
            self.var_status.set('音频来源已切换，请重新点「开始」')
        self._sync_source_widgets()

    def _sync_source_widgets(self):
        kind = self._cur_source_key()
        # 只有对应来源的控件可用，其余隐藏 —— 避免用户选错（比如选了
        # 「系统声音」却还在改麦克风设备）。
        if kind == 'mic':
            self.cb_mic.configure(state='readonly')
            self.cb_mic.pack(side='left', padx=(4, 12), before=self.lbl_source_note)
            self._hide(self.cb_out, self.entry_file, self.btn_pick_file,
                       self.cb_speed, self.cb_loop)
            self.var_source_note.set('采集麦克风；设备原生采样率会重采样到 16 kHz')
        elif kind == 'system':
            self._hide(self.cb_mic, self.entry_file, self.btn_pick_file,
                       self.cb_speed, self.cb_loop)
            if self.outs:
                self.cb_out.configure(state='readonly')
                self.cb_out.pack(side='left', padx=(4, 12), before=self.lbl_source_note)
                self.var_source_note.set('采集系统正在播放的声音（WASAPI 回环），不占用麦克风')
            else:
                self.cb_out.configure(state='disabled')
                self._hide(self.cb_out)
                self.var_source_note.set('未找到可回环的输出设备（需要 Windows WASAPI）')
        else:
            self._hide(self.cb_mic, self.cb_out)
            self.entry_file.configure(state='normal')
            self.entry_file.pack(side='left', padx=(4, 4), before=self.lbl_source_note)
            self.btn_pick_file.configure(state='normal')
            self.btn_pick_file.pack(side='left', padx=(0, 8), before=self.lbl_source_note)
            self.cb_speed.configure(state='readonly')
            self.cb_speed.pack(side='left', padx=(0, 8), before=self.lbl_source_note)
            self.cb_loop.configure(state='normal')
            self.cb_loop.pack(side='left', padx=(0, 8), before=self.lbl_source_note)
            self.var_source_note.set('回放本地音频文件；可按实时速度播放')

    @staticmethod
    def _hide(*widgets):
        for w in widgets:
            w.configure(state='disabled')
            w.pack_forget()

    def _pick_file(self):
        from tkinter import filedialog
        p = filedialog.askopenfilename(
            title='选择音频文件',
            filetypes=[('音频文件', '*.wav *.mp3 *.m4a *.mp4 *.flac *.ogg *.opus *.aac *.wma'),
                       ('所有文件', '*.*')])
        if p:
            self.var_file.set(p)
            self.var_source.set(self._src_label['file'])
            self._sync_source_widgets()
            self.var_status.set(f'已选择音频文件：{os.path.basename(p)}')

    def _build_source(self):
        """按当前 GUI 选择构造一个音源对象。"""
        kind = self._cur_source_key()
        q = queue.Queue()
        if kind == 'mic':
            return make_source('mic', q, device=self._mic_index())
        if kind == 'system':
            if not self.outs:
                raise RuntimeError('没有可用的系统输出设备（WASAPI 回环不可用）')
            return make_source('system', q, system_device=self._out_device_id())
        path = (self.var_file.get() or '').strip()
        if not path:
            raise RuntimeError('请先选择要播放的音频文件')
        speed = self._speed_back.get(self.var_speed.get(), 1.0)
        return make_source('file', q, file=path, speed=speed,
                           loop=bool(self.var_loop.get()))

    # -- 线程安全的日志投递 ----------------------------------------------
    def _ui_log(self, msg):
        """后台线程 -> 主线程。绝不能在这里碰 tk。"""
        self._ui_log_q.put(msg)

    def _drain_ui_log(self):
        """在主线程里把积压的日志刷到状态栏（由 _poll 调用）。"""
        got = False
        while True:
            try:
                msg = self._ui_log_q.get_nowait()
            except queue.Empty:
                break
            got = True
            self.var_status.set(str(msg))
        return got

    def load_engine(self):
        """按当前 ASR 组合选项（引擎 + 设备）加载/重载引擎。"""
        opt = self._cur_asr_opt()
        if opt is None:
            return
        key, dev = opt['engine'], opt['device']
        if self._loading:
            return
        if (key == self.engine_key
                and dev == getattr(self, '_asr_effective_device', None)):
            return
        self.stop()
        self._loading = True
        self.btn.configure(state='disabled')
        self.cb_asr_combo.configure(state='disabled')
        self.var_note.set(opt.get('note', ''))
        old = [self.engine]
        self.engine, self.engine_key = None, None
        self._asr_effective_device = None

        def work():
            try:
                if old[0]:
                    old[0].close()            # 先释放旧引擎的显存/内存，再加载新的
                    old[0] = None
                    gc.collect()
                # 语种在引擎创建时就定下来（要进 prompt / 进程启动参数），
                # 所以这里传 GUI 上的实时选择，不是 args 的启动快照。
                # ⚠️ device 来自组合下拉（用户显式选的），make_engine 内部
                #    按 kind 决定是否采纳（npu/cuda 档写死）。
                eng = make_engine(key, on_log=self._ui_log,
                                  force_language=self._cur_asr_lang(),
                                  device=dev)
                self.root.after(0, self._engine_ready, key, eng, dev)
            except Exception as e:
                msg = f'{type(e).__name__}: {e}'
                self.root.after(0, self._engine_failed, msg)

        threading.Thread(target=work, daemon=True).start()

    def _engine_ready(self, key, eng, dev=None):
        self.engine, self.engine_key, self._loading = eng, key, False
        self._asr_effective_device = dev
        self.cb_asr_combo.configure(state='readonly')
        self.btn.configure(state='normal')
        self.var_status.set(f'{ENGINES[key]["label"]} 就绪（加载 {eng.load_s:.1f} s）')
        # 翻译模型要等 ASR 就绪后再加载（同一张卡上并行编译会把 GUI 卡死）。
        # 这里必须用 GUI 的实时状态，不能用 args.translate —— 那是启动时的快照：
        # 用户在下拉里改过翻译后，任何一次切换 ASR 后端都会把翻译重置回启动值，
        # 表现为「改设备之后翻译再也不跑了」。
        self.mt.set_target(self._cur_mt_target())
        if self.args.autostart:
            self.args.autostart = False
            self.start()

    def _engine_failed(self, msg):
        self._loading = False
        self.cb_asr_combo.configure(state='readonly')
        self.var_status.set('加载失败')
        from tkinter import messagebox
        messagebox.showerror('后端加载失败', msg)

    # -- 控制 -------------------------------------------------------------
    def toggle(self):
        self.stop() if self.session and self.session.running else self.start()

    def start(self):
        if not self.engine or (self.session and self.session.running):
            return
        try:
            src = self._build_source()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror('音频源错误', f'{type(e).__name__}: {e}')
            self.var_status.set('音频源错误')
            return
        self.session = Session(self.engine, src, on_final=self._on_final)
        self.session.start()
        self.btn.configure(text='■ 停止')
        kind = self._cur_source_key()
        self.var_status.set(f'识别中 · {ENGINES[self.engine_key]["label"]} · '
                            f'{audio_source.SOURCES[kind]}')

    def stop(self):
        if self.session and self.session.running:
            self.session.stop()
            self.session.ended.wait(30)
        # C-099①：停的时候把挂起的半句补翻，否则最后半句的译文（含 TTS）会丢。
        # （`Translator.flush` 内部按 seg_keys 去重，重复调用是安全的。）
        try:
            if self.mt.active:
                self.mt.flush(seg=len(self.blocks) - 1 if self.blocks else None)
        except Exception:
            pass
        self.btn.configure(text='▶ 开始')

    def _on_mt_changed(self, *_a):
        key = self.mt_keys[[TARGET_LABELS[k] for k in self.mt_keys].index(self.var_mt.get())]
        self.mt.set_target(key)
        self.var_status.set('翻译：' + TARGET_LABELS[key])

    def _cur_mt_target(self):
        """GUI 下拉当前选中的目标语言（而不是 args.translate 启动快照）。"""
        try:
            return self.mt_keys[[TARGET_LABELS[k] for k in self.mt_keys]
                                .index(self.var_mt.get())]
        except ValueError:
            return self.mt.target

    # -- 组合下拉事件（APP-007）-----------------------------------------
    def _on_asr_combo_changed(self, *_a):
        """ASR 分区的「设备+精度」组合变化 ⇒ 重载引擎。"""
        opt = self._cur_asr_opt()
        if not opt:
            return
        self._dev_choices['asr'] = opt['device']
        self.var_asr_note.set(opt.get('note', ''))
        device_config.save_config(dict(self._dev_choices))
        if (opt['engine'] == self.engine_key
                and opt['device'] == getattr(self, '_asr_effective_device', None)):
            return
        self.var_status.set(f'ASR 切换中：{opt["label"]}')
        self.load_engine()

    def _on_mt_combo_changed(self, *_a):
        """翻译分区的「设备+量化」组合变化。

        🔴 **顺序铁律**：先 ``set_engine(key)``，后 ``set_device(dev)``。
        ``TranslationService.set_engine`` 内部会把 ``self.device`` 重置成
        该 engine 的默认值（translator.py:set_engine），只调 set_device 会被
        覆盖；反过来只调 set_engine 则设备回不到用户选的值。
        两次调用只触发**一次**模型重建（重建在工作线程，读取的是最终 device）。
        """
        opt = self._cur_mt_opt()
        if not opt:
            return
        self._dev_choices['mt'] = opt['device']
        self.var_mt_note.set(opt.get('note', ''))
        device_config.save_config(dict(self._dev_choices))
        if not self.mt.set_engine(opt['engine']):
            self.var_status.set('翻译后端切换失败（保持原后端）')
            return
        self.mt.set_device(opt['device'])
        if not self.mt.active:
            self.var_status.set(
                f'翻译后端：{opt["label"]}（翻译关闭中，切换将在开启翻译时生效）')
            return
        self.cb_mt_combo.configure(state='disabled')
        self.var_status.set(f'翻译后端切换中：{opt["label"]} · {self.mt.device}')
        self.root.after(300, lambda: self.cb_mt_combo.configure(state='readonly'))

    def _tts_note_text(self, opt):
        """语音分区的说明文字（设备 + 精度 + 必要的警示）。

        🔴 CUDA 选项必须**带上实测结论**（用户能在选之前就知道它跑不通），
           不能只显示「设备 GPU.1」让人以为能用。
        """
        base = f'设备 {opt["device"]} · 精度 {opt["precision"]}'
        note = opt.get('note') or ''
        if note:
            return f'{base}　⚠️ {note}'
        return base

    def _on_tts_combo_changed(self, *_a):
        """语音分区的「设备+精度」组合变化 ⇒ 重起 TTS worker。

        ⚠️ TTS 的 precision 是 **OV 推理精度 f32/f16**，不是量化位宽；
        worker 进程启动时就绑定了设备与精度 ⇒ 换组合必须重启。
        """
        opt = self._cur_tts_opt()
        if not opt:
            return
        self._dev_choices['tts'] = opt['device']
        self._tts_precision = opt['precision']
        self.var_tts_note.set(self._tts_note_text(opt))
        device_config.save_config(dict(self._dev_choices))
        if getattr(self, 'tts', None) is not None:
            self._restart_tts_on_device(opt['device'], opt['precision'])

    def _on_mt_draft_toggled(self, *_a):
        """开关草稿译文（还没定稿那句的实时预览）。

        默认关闭 —— 只翻译已定稿的文本。打开后每 1.5s 会额外翻一次 partial，
        是 ASR 积压的主要来源，所以关闭时也把残留的草稿译文清掉。
        """
        on = self.mt.set_draft(self.var_mt_draft.get())
        self._ui_log(f'草稿译文：{"开启（实时预览）" if on else "关闭（只翻定稿文本）"}')
        if on:
            self.var_status.set('草稿译文已开启（会额外占用翻译算力，ASR 积压可能上升）')
        else:
            self.var_status.set('草稿译文已关闭（只翻译已定稿的文本）')

    # -- 推理设备（APP-004 第 3 条 / APP-007 组合下拉）------------------
    def _reload_engine_on_device(self, key, dev):
        """ASR 换设备 ⇒ 重载引擎。

        🔴 **不再改写全局 ``ENGINES``**：``OVEngine.__init__`` 已经支持
        ``device=`` 覆盖（kind=='ov' 时），把全局表改了会让**别的会话**
        （CLI / 后台回放）跟着变，属于隐藏的全局副作用。
        """
        self.var_status.set(f'ASR 设备切换中：{dev}（正在重载引擎）')
        self.load_engine()

    def _restart_tts_on_device(self, dev, precision=None):
        """TTS 换设备/精度 ⇒ 重起 worker（worker 进程启动时就绑定了这两项）。"""
        try:
            self.tts.close()
        except Exception:
            pass
        self.tts = None
        if precision:
            self._tts_precision = precision
        self.var_status.set(
            f'语音输出切换中：{dev} · {self._tts_precision}（正在重启 TTS）')
        self._on_tts_toggled()

    # -- TTS（C-101 P4）--------------------------------------------------
    def _on_tts_toggled(self, *_a):
        """语音输出勾选：起/停 TTS worker。

        ⚠️ **TTS 加载失败不能影响字幕和翻译**（C-101 P4 第 5 条）⇒
        整段 try/except，失败只提示、不抛。
        """
        on = self.var_tts_on.get()
        if not on:
            if self.tts is not None:
                try:
                    self.tts.close()
                except Exception:
                    pass
                self.tts = None
            self.var_tts_note.set('已关闭（译文朗读不输出）')
            self.var_status.set('语音输出已关闭')
            return
        try:
            from tts_service import TTSService
            voice = self._tts_voice_back.get(self.var_tts_voice.get(), 'A')
            out_name = self.var_tts_out.get()
            out_id = self._out_label_back.get(out_name)
            # ⚠️ 用 **GUI 的实时选择**，不是 args 的启动快照：
            #    用户在组合下拉里改过设备/精度后，args 里的值是旧的。
            dev = self._dev_choices.get('tts') or getattr(self.args, 'tts_device', 'NPU')
            prec = self._tts_precision or getattr(self.args, 'tts_precision', 'f32')
            self.tts = TTSService(
                device=dev, voice=voice,
                out_device=out_id,
                precision=prec,
                on_log=lambda m: self._ui_log(f'tts: {m}'))
            self.var_tts_note.set(f'启动中… 设备 {dev} · 精度 {prec}')
            self.var_status.set('语音输出已开启（正在加载 TTS 模型）')
        except Exception as e:
            self.tts = None
            self.var_tts_note.set(f'启动失败：{e}')
            self.var_status.set('语音输出启动失败（不影响字幕与翻译）')
            self._ui_log(f'tts start failed: {type(e).__name__}: {e}')

    def _on_tts_voice_changed(self, *_a):
        """切换音色：需要重启 worker（音色条件在加载时绑定）。"""
        voice = self._tts_voice_back.get(self.var_tts_voice.get(), 'A')
        if self.tts is not None:
            try:
                self.tts.close()
            except Exception:
                pass
            self.tts = None
        if self.var_tts_on.get():
            self._on_tts_toggled()

    def _pump_tts(self):
        """把**定稿译文**提交给 TTS（C-101 P4 第 1 条：只念定稿译文）。

        ⚠️ GUI 侧原先**只加了控件和统计，没接提交链路**
        ⇒ 译文从来没送到 TTS。CLI 侧（`run_cli`）是在 `mt.pop_outbox()`
        的循环里提交的，GUI 侧要在这里补上（定时轮询里做，不能阻塞 UI）。

        - 只提交 `kind == 'final'` 的译文（草稿译文会反复改，不能念）；
        - **outbox 一定要 pop**（哪怕 TTS 没开）——
          否则 GUI 模式下 `mt.outbox` 会**无限增长**（之前没人消费它，
          界面显示译文走的是 `mt_of_seg` 读 `done` 字典，不依赖 outbox）；
        - 翻译没开 / TTS 没开 ⇒ 只丢不提交。

        ⚠️ C-111 已撤回（2026-10-23）：段尾半句不再单独翻译，
        恢复 C-099① 的挂起机制 ⇒ outbox 只有 'final'/'draft'/'switch'。
        """
        try:
            if not self.mt.active:
                return
            for kind, key, txt in self.mt.pop_outbox():
                if kind == 'final' and txt and txt.strip():
                    if self.tts is not None:
                        self.tts.submit(txt, seg=key)
        except Exception as e:
            self._ui_log(f'tts submit failed: {e!r}')

    def _tts_meter(self):
        """底栏的 TTS 统计（首包 / 积压 / 丢句）。"""
        if self.tts is None:
            return ''
        try:
            st = self.tts.stats()
        except Exception:
            return ''
        fp = st.get('first_packet_s')
        f = lambda v, d=1: ('—' if v is None else f'{v:.{d}f}')
        return (f'  |  TTS 首包 {f(fp, 2)}s  积压 {f(st.get("backlog_s"))}s'
                f'/最大 {f(st.get("max_backlog_s"))}s  丢句 {st.get("n_dropped", 0)}'
                f'  已播 {st.get("n_played", 0)}')

    def _mt_of(self, seg):
        """定稿段的译文（按段序号查）。"""
        return self.mt.mt_of_seg(seg)

    def _on_final(self, text):
        self.final_text += text + '\n'
        self.blocks.append(text)
        self.mt.submit(text, seg=len(self.blocks) - 1)

    def clear(self):
        self.final_text = ''
        self.blocks = []
        self._reset_mt_session()
        self._render('')

    def _reset_mt_session(self):
        """🔴🔴 清空**整个 MT 会话状态**（不只 3 个字典）。

        ★ **旧行为是真 bug**（MT 移交说明 §4.3 点名）：
          原来只清 `seg_keys` / `seg_carry` / `seg_half`
          ⇒ **没清** `units`（句单元列表）、`_seen`（已提交句集合）、
          `_pend`（跨段缓冲）、`done` / `done_fix`（译文缓存）。
          ⇒ 点「清空」之后：
            · `mt.units` 里**上一场**的句单元还在 ⇒ 渲染层会把旧译文混进新场次；
            · `_seen` 还在 ⇒ 新场次里出现的**同一句**会被当成「已翻过」
              ⇒ **不翻译、不进显示单元** ⇒ 新场次的这句话**直接丢失**；
            · `_pend` 里还挂着上一场的半句 ⇒ 新场次第一段会**接到上一场的尾巴后面**
              ⇒ 出现「前半句丢失 / 跨行重复」；
            · `done` 里还留着旧译文 ⇒ 同一句在新场次**读到上一场的旧译文**。
          ⇒ 这些和 `translator._loop()` 里「换模型后清缓存」是同一套字段，
            这里按同样口径清（**不重载模型**，只重置会话状态）。

        ⚠️ 用 `getattr(..., None)` 防御：字段名是 `translator.py` 的内部约定，
          万一将来改名 ⇒ 跳过而不是抛异常把「清空」按钮搞崩。
        """
        mt = self.mt
        # ── 字典类（原来清的 3 个 + 译文缓存）──
        for name in ('seg_keys', 'seg_carry', 'seg_half'):
            d = getattr(mt, name, None)
            if isinstance(d, dict):
                d.clear()
        for name in ('done', 'done_fix'):
            d = getattr(mt, name, None)
            if hasattr(d, 'clear'):
                d.clear()
        # ── 列表 / 集合 / 标量 ──
        units = getattr(mt, 'units', None)
        if isinstance(units, list):
            units.clear()
        seen = getattr(mt, '_seen', None)
        if isinstance(seen, set):
            seen.clear()
        if hasattr(mt, '_pend'):
            mt._pend = ''
        if hasattr(mt, '_half'):
            mt._half = None
        if hasattr(mt, 'draft'):
            mt.draft = ''
        if hasattr(mt, '_last_src'):
            mt._last_src = ''

    def _save_text(self):
        """原文 + 译文（保存/自测共用）。"""
        out = []
        for i, src in enumerate(self.blocks):
            out.append(src)
            mt = self._mt_of(i)
            if mt:
                # 本段原文开头承接上一段的半句（C-111：半句的完整译文在**上一行**，
                # 本行的译文是它的后半截）—— 用 … 标出接续关系
                if self.mt.seg_carry.get(i):
                    mt = '…' + mt
                out.append('〔译〕' + mt)
            elif self.mt.seg_carry.get(i) and self.mt.active:
                # 本段译文还没出来（翻译在途）—— 说明它在等什么，避免看起来像丢了
                out.append('〔译〕（译文生成中…）')
        return '\n'.join(out) + ('\n' if out else '')

    def save(self):
        from tkinter import filedialog
        if not self.blocks:
            return
        p = filedialog.asksaveasfilename(defaultextension='.txt',
                                         initialfile=f'caption_{datetime.now():%Y%m%d_%H%M%S}.txt')
        if p:
            open(p, 'w', encoding='utf-8').write(self._save_text())

    def _toggle_overlay(self):
        """屏幕字幕开关。

        🔴 **默认完全穿透**（APP-007 第 4 项）：字幕不挡桌面交互，
        拖动改用独立的把手（字幕窗口自己收不到鼠标消息）。
        """
        if self.var_overlay.get() and not self.overlay:
            self.overlay = CaptionOverlay(self.root, self.args.font_size,
                                          click_through=True)
            # 穿透后鼠标点不到字幕窗口 ⇒ 把手右键菜单「关闭屏幕字幕」
            # 必须能回调回来，否则关不掉。
            self.overlay.on_close = self._close_overlay_from_handle
        elif not self.var_overlay.get() and self.overlay:
            self.overlay.destroy()
            self.overlay = None

    def _close_overlay_from_handle(self):
        """字幕把手右键「关闭屏幕字幕」⇒ 同步把顶栏开关打回关。"""
        try:
            self.var_overlay.set(False)
        except Exception:
            pass
        self._toggle_overlay()
        self.var_status.set('屏幕字幕已关闭')

    def quit(self):
        self.stop()
        # 🔴🔴 2026-10-25 §31 修：**必须等 MT 把这句翻完**。
        #   `mt.flush()` 只是把挂起的半句**入队**（`q.put(_Job(...))`），
        #   翻译在**后台工作线程**里异步做 ⇒ flush 返回时译文**还没出**。
        #   旧实现在这里直接 `_pump_tts()` ⇒ outbox 还是空的
        #   ⇒ 这一句**既不显示、也不朗读**，而且随后 `self.mt.close()` 把
        #   工作线程**直接停掉** ⇒ 这一句**永远丢**。
        #   ⇒ 用户看到的就是「最后一句话的译文不见了」。
        #   CLI 侧 `run_cli` 收尾**有**这一段（`mt.wait_idle(180)`），
        #   GUI 侧漏了 ⇒ 两边行为不一致。
        #   ⚠️ `wait_idle` 是**阻塞**调用（最多 180 s），但在退出路径上
        #      这是**必须**的 —— 退出时用户本来就等着，不在乎多等这一会儿。
        #      若超时，`wait_idle` 自己会返回，不会永久卡死。
        try:
            if self.mt.active:
                # ⚠️ **只有 `flush()` 真的入队了句子才需要等**。
                #   `wait_idle()` 的判据是「队列非空 **或** state == 'loading'」
                #   ⇒ 若翻译模型**正在加载**（state='loading'），
                #   即使没有任何待翻内容也会**白等到超时**（180 s）
                #   ⇒ 用户点关闭后界面卡住不动 ⇒ 不可接受。
                #   `flush()` 返回的是**句单元 key 列表**
                #   （`translator.py::TranslationService.flush`）⇒ 空列表
                #   ⇒ 没有需要等的译文 ⇒ 直接跳过。
                #   ⚠️ 但 `flush()` 在「这句**已经翻过**」的分支也返回 `[k]`
                #   （只是把译文重新标成可朗读，**没有新任务入队**）
                #   ⇒ 不能只看返回值 ⇒ 还要看**队列里到底有没有待办**。
                #   ⚠️ `wait_idle()` 的判据是「队列非空 **或** state == 'loading'」
                #   ⇒ 若翻译模型**正在加载**（state='loading'），
                #   即使没有任何待翻内容也会**白等到超时**（180 s）
                #   ⇒ 用户点关闭后界面卡住不动 ⇒ 不可接受。
                #   ⇒ 只有「队列里确实有待办」时才等。
                #   ⚠️ **只 flush 一次**（旧实现先裸调一次 flush，
                #      重复调用会让第二次返回空列表 ⇒ wait_idle 被跳过）。
                flushed = self.mt.flush()
                if flushed and self.mt.pending:
                    self.mt.wait_idle(180)
        except Exception:
            pass
        # 收尾：把最后一批定稿译文补交给 TTS，然后等它排空再关
        # （CLI 侧 `run_cli` 收尾也有同样一段，见 C-101 P4 第 6 条）
        try:
            self._pump_tts()
        except Exception:
            pass
        if self.tts is not None:
            try:
                self.tts.drain(timeout=30)
            except Exception:
                pass
            try:
                self.tts.close()
            except Exception:
                pass
            self.tts = None
        self.mt.close()
        if self.engine:
            self.engine.close()
        # 字幕窗（含独立拖拽把手）要显式销毁，否则进程可能不退出。
        if self.overlay is not None:
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None
        self.root.destroy()

    # -- 刷新 -------------------------------------------------------------
    def _render(self, partial):
        self.txt.configure(state='normal')
        self.txt.delete('1.0', 'end')
        for i, src in enumerate(self.blocks):
            self.txt.insert('end', src + '\n')
            mt = self._mt_of(i)
            if mt:
                if self.mt.seg_carry.get(i):
                    mt = '…' + mt
                self.txt.insert('end', '    〔译〕' + mt + '\n', 'mt')
        if partial:
            self.txt.insert('end', partial, 'partial')
            # 草稿译文只在勾选了「草稿译文」时才显示（默认关闭）
            dra = self.mt.draft if (self.mt.active and self.mt.draft_on) else ''
            if dra:
                self.txt.insert('end', '\n    〔译〕' + dra, 'mt_partial')
        self.txt.see('end')
        self.txt.configure(state='disabled')
        if self.overlay:
            # 取最近 3 段的译文。★ 必须用**段序号**（blocks 的下标）去查
            # seg_keys —— blocks 里存的是原文文本，直接拿文本当 key 查不到，
            # 结果是屏幕字幕的译文行永远为空。
            mt_tail = ' '.join(
                m for m in (self._mt_of(i) for i in range(len(self.blocks) - 3,
                                                            len(self.blocks))) if m)
            # APP-007：屏幕字幕只保留**定稿译文**（青）与**实时识别**（黄）两行。
            # 定稿原文与草稿译文预览不再上屏幕字幕（仍在主文本区里）。
            self.overlay.show(mt_tail, partial)

    def _poll(self):
        self._drain_ui_log()          # 后台线程的日志统一在这里上屏
        self._track_mt_state()
        self._pump_tts()              # ← 把定稿译文提交给 TTS（GUI 侧链路）
        s, e = self.session, self.engine
        if s:
            if s.error:
                err, s.error = s.error, None
                from tkinter import messagebox
                messagebox.showerror('识别出错', f'{type(err).__name__}: {err}')
            if s.src.err:
                err, s.src.err = s.src.err, None
                from tkinter import messagebox
                messagebox.showerror('音频采集失败', f'{type(err).__name__}: {err}')
            partial = e.cur_text if (e and s.running) else ''
            if partial and self.mt.active:
                # C-100③：把 ASR 积压传进去，拥塞时自动暂停草稿（定稿翻译不受影响）
                self.mt.maybe_draft(partial[-160:], asr_backlog=s.backlog_s)
            self._render(partial)
            lv = s.src.level
            bars = min(12, int(lv / 0.03 * 12))
            lag = e.stats.get('lag_ms') if e else None
            rtf = f'{e.rtf:.2f}' if e and e.rtf else '—'
            backlog = s.backlog_s
            self._max_backlog = max(getattr(self, '_max_backlog', 0.0), backlog)
            self.var_meter.set(
                f'电平 {"█" * bars}{"░" * (12 - bars)}  音频 {s.audio_s:6.1f}s  '
                f'来源 {self._src_label.get(self._cur_source_key(), "?")}'
                f'/{s.src.name_used or "—"}  '
                f'设备 {e.device_desc if e else "—"}  RTF {rtf}  '
                f'出字延迟 {f"{lag:.0f} ms" if lag is not None else "—"}  '
                f'积压 {backlog:.1f}s  段 {e.stats["segs"] if e else 0}'
                f'{self._mt_meter()}')
            self.lbl_meter.configure(foreground='#c0392b' if backlog > 2.0 else '#333')
            if not s.running and self.btn.cget('text') == '■ 停止':
                self.btn.configure(text='▶ 开始')
                self.var_status.set('已停止')
        if self.args.selftest and s and (s.audio_s >= self.args.selftest or not s.running):
            self._selftest_done()
            return
        self.root.after(self.POLL_MS, self._poll)

    def _track_mt_state(self):
        """记录翻译状态的进入时刻（用于「加载中…已等 N 秒」提示）。"""
        st = self.mt.state
        if st != getattr(self, '_mt_last_state', None):
            self._mt_last_state = st
            if st == 'loading':
                self._mt_load_since = time.perf_counter()
            elif st == 'error':
                # 加载失败要写进日志 —— 状态栏那一行放不下完整堆栈，
                # 用户报问题时需要这份信息。
                self._ui_log(f'mt load failed: {self.mt.err!r}')
        # 失败时亮出重试按钮；加载中禁用
        try:
            self.btn_mt_retry.configure(
                state='normal' if (st == 'error' and self.mt.active) else 'disabled')
        except Exception:
            pass

    def _retry_mt(self):
        """重新加载翻译模型（上次失败后用）。"""
        tgt = self._cur_mt_target()
        if tgt == 'off':
            self.var_status.set('请先选择翻译目标语言')
            return
        self._ui_log(f'retry mt target={tgt} engine={self.mt.engine_key} device={self.mt.device}')
        # set_target 里只有在工作线程**已死**时才会重启；这里强制重启一次，
        # 覆盖「线程还活着但卡住」的情况。
        self.mt.restart()
        self.var_status.set('正在重新加载翻译模型…')

    def _mt_meter(self):
        """指标栏里的翻译一段：加载中 / 失败 / 延迟中位 + 积压（含实际生效设备）。"""
        mt = self.mt
        if not mt.active:
            return ''
        if mt.state == 'loading':
            # 加载中要能看到「过了多久」—— 否则卡住了和正常编译长得一样，
            # 用户只能干等。首次编译（无缓存）要 30–60 秒，超过阈值就提示。
            waited = time.perf_counter() - getattr(self, '_mt_load_since', 0.0)
            hint = ''
            if waited > 90:
                hint = '（已等 %.0f s，若长时间无变化请看日志）' % waited
            elif waited > 30:
                hint = '（%.0f s，首次编译较慢）' % waited
            return f'  翻译 {mt.device} 加载中…{hint}'
        if mt.state == 'error':
            # 完整错误很长，状态栏放不下也不好看 —— 摘要 + 指向日志/重试按钮
            brief = str(mt.err or '').split('(')[0].strip() or '未知错误'
            return f'  翻译 失败（{brief}）· 详情见日志，可点「重试翻译」'
        s = mt.summary()
        lat = f'{s["lat_med"]:.0f}' if s['lat_med'] is not None else '—'
        return f'  翻译 {mt.device} 延迟中位 {lat} ms  翻译积压 {s["pending"]}'

    def _selftest_done(self):
        """自测：截一张屏幕图、写结果，然后退出（只在 --selftest 下使用）。"""
        out = self.args.selftest_out or os.path.join(APP_DIR, 'selftest')
        os.makedirs(out, exist_ok=True)
        switch_log = ''
        if getattr(self.args, 'selftest_mt_switch', None):
            switch_log = self._run_mt_switch_probe()
        try:
            from PIL import ImageGrab
            ImageGrab.grab().save(os.path.join(out, f'{self.engine_key}_screen.png'))
        except Exception as ex:
            open(os.path.join(out, 'screenshot_error.txt'), 'w').write(repr(ex))
        e = self.engine
        if self.mt.active:
            # C-099①：先把挂起的半句补翻，再等队列排空，否则最后半句会丢
            self.mt.flush(seg=len(self.blocks) - 1 if self.blocks else None)
            self.mt.wait_idle(30)          # 等最后一两句译文落地再截图
        mt = self.mt.summary() if self.mt.active else None
        open(os.path.join(out, f'{self.engine_key}_gui.txt'), 'w', encoding='utf-8').write(
            f'engine={self.engine_key} audio_s={self.session.audio_s:.1f} rtf={e.rtf:.3f} '
            f'lag_ms={e.stats.get("lag_ms")} segs={e.stats["segs"]} '
            f'max_backlog={getattr(self, "_max_backlog", 0.0):.2f}\n'
            f'translate={self.mt.target} mt_engine={self.mt.engine_key} '
            f'mt_device={self.mt.device} state={self.mt.state} mt={mt}\n'
            + (f'mt_switch: {switch_log}\n' if switch_log else '')
            + f'final:\n{self.final_text}\npartial:\n{e.cur_text}\n'
            f'--- 原文+译文 ---\n{self._save_text()}\n')
        self.quit()

    def _run_mt_switch_probe(self):
        """自测：切换翻译后端，验证切换后翻译仍在工作。

        这是回归测试 —— 曾有个 bug：_engine_ready 用 args.translate 启动快照，
        导致用户改过设置后，任何一次 ASR 后端切换都会把翻译重置成「关闭」。

        必须放到后台线程跑：TranslationService 的 on_log 走 root.after，
        主线程一旦 wait_idle 阻塞就跟它互锁（实测 GUI 直接无响应）。
        """
        lines = []
        probe = 'We are making good progress on this milestone.'
        keys = [k for k in MT_ENGINES if k != self.mt.engine_key][:2]
        # tk 变量只能在主线程读：先取好目标语言再进后台线程
        target = self._cur_mt_target()

        def work():
            lines.append(f'before: target={self.mt.target} engine={self.mt.engine_key} '
                         f'device={self.mt.device} state={self.mt.state}')
            if not self.mt.active:
                self.mt.set_target(target)                   # 启动时翻译是关的
                self.mt.wait_idle(180)
                lines.append(f'enabled: target={self.mt.target} state={self.mt.state} '
                             f'err={self.mt.err}')
            for key in keys:
                ok = self.mt.set_engine(key)
                self.mt.wait_idle(240)
                self.mt.submit(probe)
                self.mt.wait_idle(90)
                got = self.mt.get(probe)
                lines.append(f'switch->{key}: set={ok} device={self.mt.device} '
                             f'state={self.mt.state} n_done={self.mt.n_done} '
                             f'{"OK" if got else "FAIL(无译文)"} :: {got}')
        th = threading.Thread(target=work, daemon=True)
        th.start()
        th.join(timeout=600)                                  # 主线程不阻塞事件循环太久
        return ' | '.join(lines)


# ── CLI ────────────────────────────────────────────────────────────────
def _cli_source(args):
    """按命令行参数构造音源。

    ``--source`` 决定用哪一路：
      mic（默认） / system（系统声音回环） / file（音频文件）

    兼容旧用法：只给 ``--file`` 而不给 ``--source`` 时自动切到 file 模式。
    """
    kind = args.source
    if kind == 'file' and not args.file:
        raise SystemExit('--source file 需要配合 --file 指定音频文件')
    if kind == 'system' and not soundcard_available():
        raise SystemExit('系统声音模式需要 soundcard 包：'
                         'pip install soundcard（不需要 ffmpeg）')
    q = queue.Queue()
    if kind == 'system':
        return make_source('system', q, system_device=args.system_device)
    if kind == 'file':
        return make_source('file', q, file=args.file,
                           speed=args.speed, loop=args.loop)
    return make_source('mic', q, device=args.device)


def run_cli(args):
    asr_lang = None if (getattr(args, 'asr_lang', ASR_LANG_AUTO) or
                         ASR_LANG_AUTO) == ASR_LANG_AUTO else args.asr_lang
    eng = make_engine(args.engine, on_log=lambda m: print(m, flush=True),
                      force_language=asr_lang, device=args.asr_device)
    print(f'[{args.engine}] 加载 {eng.load_s:.1f} s，设备 {eng.device_desc}，'
          f'识别语种 {asr_lang or "自动检测"}', flush=True)
    mt = TranslationService(target=args.translate, device=args.mt_device,
                            engine_key=args.mt_engine, use_ctx=args.mt_ctx,
                            glossary=args.mt_glossary,
                            draft=_init_draft_flag(args),
                            on_log=lambda m: print(f'  [翻译] {m}', flush=True))
    # ── TTS（C-101 P4 第 5 条：加载顺序 ASR → MT → TTS）──
    #    TTS 加载失败**不能影响字幕和翻译** ⇒ 整段 try/except。
    tts = None
    # 🔴 **默认开启**（APP-014）：`--tts` 默认 None ⇒ 视为 on；
    #    显式 `--tts off` ⇒ 关闭。
    if getattr(args, 'tts', None) != 'off':
        try:
            from tts_service import TTSService
            tts = TTSService(device=args.tts_device, voice=args.tts_voice,
                             out_device=args.tts_out_device,
                             precision=args.tts_precision,
                             out_wav=args.tts_out,
                             on_log=lambda m: print(f'  [TTS] {m}', flush=True))
            print(f'[TTS] worker 已启动（设备 {args.tts_device}，'
                  f'音色 {args.tts_voice}，精度 {args.tts_precision}）', flush=True)
        except Exception as e:
            tts = None
            print(f'[TTS] 启动失败（不影响字幕与翻译）：{e}', flush=True)
    finals = []

    def on_final(t):
        finals.append(t)
        print(f'\n[定稿] {t}', flush=True)
        mt.submit(t, seg=len(finals) - 1)

    s = Session(eng, _cli_source(args), on_final=on_final)
    t0 = time.perf_counter()
    s.start()
    last, lags, max_backlog = '', [], 0.0
    try:
        while s.running:
            time.sleep(0.2)
            if eng.stats.get('lag_ms') is not None:
                lags.append(eng.stats['lag_ms'])
            max_backlog = max(max_backlog, s.backlog_s)
            cur = eng.cur_text
            if cur and cur != last:
                print(f'\r[实时] {cur[-90:]}', end='', flush=True)
                last = cur
            for kind, key, txt in mt.pop_outbox():
                if kind == 'half' and txt.strip():
                    # C-111：段尾半句的初翻译文 —— 显示但**不朗读**
                    print(f'\n[半句译文] {txt}', flush=True)
                elif kind in ('final', 'fix') and txt.strip():
                    tag = '修正译文' if kind == 'fix' else '译文'
                    print(f'\n[{tag}] {txt}', flush=True)
                    # ── TTS：只提交**定稿译文**（C-101 P4 第 1 条）──
                    if tts is not None and tts.active:
                        tts.submit(txt, seg=key)
            if args.max_seconds and s.audio_s >= args.max_seconds:
                s.stop()
    except KeyboardInterrupt:
        s.stop()
    s.ended.wait(120)
    if s.error:
        raise s.error
    wall = time.perf_counter() - t0
    med = float(np.median(lags)) if lags else None
    print(f'\n[{args.engine}] 音频 {s.audio_s:.1f}s  墙钟 {wall:.1f}s  RTF(计算) {eng.rtf:.3f}  '
          f'出字延迟中位 {med if med is None else round(med)} ms  最大积压 {max_backlog:.1f}s  '
          f'段 {eng.stats["segs"]}', flush=True)
    if mt.active:
        # C-099①：先把挂起的半句补翻，再等队列排空，否则最后半句会丢
        mt.flush(seg=len(finals) - 1 if finals else None)
        mt.wait_idle(180)
        for kind, key, txt in mt.pop_outbox():
            if kind == 'half' and txt.strip():
                print(f'[半句译文] {txt}', flush=True)
            elif kind in ('final', 'fix') and txt.strip():
                tag = '修正译文' if kind == 'fix' else '译文'
                print(f'[{tag}] {txt}', flush=True)
                # ── TTS：补交最后一批定稿译文 ──
                if tts is not None and tts.active:
                    tts.submit(txt, seg=key)
        sm = mt.summary()
        f = lambda v, d=1: ('—' if v is None else f'{v:.{d}f}')
        print(f'[{args.engine}] 翻译 target={mt.target} 后端={mt.engine_key} 设备 {mt.device} '
              f'state={mt.state} 句数 {sm["n"]}  延迟中位 {f(sm["lat_med"])} ms  '
              f'P95 {f(sm["lat_p95"])} ms  TTFT {f(sm["ttft_med"])} ms  '
              f'{f(sm["tok_s"])} tok/s', flush=True)
    if args.out:
        # 输出目录可能还没建：--out 指向的父目录不存在时直接崩掉会丢掉前面所有结果
        _outdir = os.path.dirname(os.path.abspath(args.out))
        if _outdir:
            os.makedirs(_outdir, exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write('\n'.join(finals) + '\n')
        if mt.active:
            mtp = os.path.splitext(args.out)[0] + '.mt.txt'
            lines = []
            for i, t in enumerate(finals):
                m = mt.mt_of_seg(i)
                if m and mt.seg_carry.get(i):
                    m = '…' + m          # 本段开头接上了上一段的半句
                elif not m and mt.seg_carry.get(i):
                    m = '（译文生成中…）'
                lines.append(m or '')
            with open(mtp, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
            print(f'[{args.engine}] 译文已写 {mtp}', flush=True)
    # ── TTS 收尾：等队列排空并落盘 ──
    if tts is not None:
        try:
            time.sleep(0.2)
            tts.drain(timeout=120)
            st = tts.stats()
            f = lambda v, d=2: ('—' if v is None else f'{v:.{d}f}')
            print(f'[TTS] 首包 {f(st.get("first_packet_s"))}s  '
                  f'积压 当前 {f(st.get("backlog_s"))}s / 最大 '
                  f'{f(st.get("max_backlog_s"))}s  '
                  f'提交 {st.get("n_submitted")}  播完 {st.get("n_played")}  '
                  f'丢弃 {st.get("n_dropped")}  重启 {st.get("n_restart")}  '
                  f'state={st.get("state")}', flush=True)
            if args.tts_out:
                print(f'[TTS] 语音已写 {args.tts_out}，'
                      f'逐句时间线 {args.tts_out}.tts.jsonl', flush=True)
        except Exception as e:
            print(f'[TTS] 收尾异常（不影响字幕）：{e}', flush=True)
        finally:
            try:
                tts.close()
            except Exception:
                pass
    mt.close()
    eng.close()


def list_devices():
    """列出音频设备：麦克风（输入）+ 可回环的系统输出设备。"""
    import sounddevice as sd
    print('── 麦克风（--device 选序号）──')
    for i, d in enumerate(sd.query_devices()):
        if d.get('max_input_channels', 0) > 0:
            print(f'[{i}] {d["name"]}  sr={d.get("default_samplerate")}'
                  f'{"  *默认" if i == sd.default.device[0] else ""}')
    print()
    print('── 系统输出设备（--source system 的回环目标）──')
    outs = list_output_devices()
    if not outs:
        print('（未找到可回环的输出设备，需要 Windows WASAPI）')
    else:
        dflt = default_output_device_id()
        for oid, name in outs:
            print(f'{name}  id={oid}{"  *默认" if oid == dflt else ""}')
    print()
    print('提示：--source system 用默认输出设备时不需要指定 id；'
          '本机只有一个输出设备时用上面打印的 id 也可。')


# ── 环境检查（--check，给 Diagnose.bat 用）──────────────────────────────
def _pad(text, width):
    """按**显示宽度**左对齐补空格（中文算 2 格）。

    直接用 str.ljust 会让含中文的标签错位（'Intel NPU · INT4（实验）' 里
    括号是全角），所以这里按 east_asian_width 折算。
    """
    import unicodedata
    w = sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)
    return text + ' ' * max(0, width - w)


def _check_devices():
    """探测 OpenVINO 可用设备。返回 (设备名 -> 全名) 映射。

    ⚠️ 与 `device_config.detect_devices()` 是同一套逻辑（单一数据源）——
    GUI 下拉框、CLI 设备解析、`--check` 输出看到的必须是同一份列表。
    """
    devs = device_config.detect_devices()
    if not devs:
        print('  [跳过] OpenVINO 不可用')
    return devs


def _check_models():
    """检查每个 ASR 后端需要的模型文件是否齐全。

    返回 (key -> (是否就绪, 说明))。
    """
    out = {}
    for key, cfg in ENGINES.items():
        if cfg['kind'] == 'cuda':
            cli = CUDA_CLI
            gguf = os.path.join(CUDA_DIR or '', 'models', cfg['gguf'])
            if not cli or not os.path.exists(cli):
                out[key] = (False, '缺 audio.cpp（audiocpp_cli.exe），本包不自带')
            elif not os.path.exists(gguf):
                out[key] = (False, f'缺模型 {cfg["gguf"]}')
            else:
                out[key] = (True, '模型齐全')
            continue
        enc = _model_path(cfg['enc'])
        dec = _model_path(cfg['dec'])
        missing = []
        # 编码器
        if not (os.path.isdir(enc) and
                os.path.exists(os.path.join(enc, 'openvino_encoder_model.xml'))):
            missing.append('编码器')
        # 解码器：NPU 侧是 openvino_model.xml，GPU 侧是 openvino_decoder_model.xml
        if not os.path.isdir(dec):
            missing.append('解码器')
        else:
            has_xml = (os.path.exists(os.path.join(dec, 'openvino_model.xml')) or
                       os.path.exists(os.path.join(dec, 'openvino_decoder_model.xml')))
            if not has_xml:
                missing.append('解码器')
        # NPU 侧还需要 embedding 表
        if cfg['kind'] == 'npu':
            npy = _model_path('qwen3-lm-int8sym-cleanie-ov/embed_tokens_f16.npy')
            if not os.path.exists(npy):
                missing.append('embedding 表')
        if missing:
            out[key] = (False, '缺 ' + '、'.join(missing))
        else:
            out[key] = (True, '模型齐全')
    return out


def run_check():
    """环境检查：设备、后端模型、翻译后端、音频设备、关键依赖。

    Diagnose.bat 调用它；README 里承诺「各后端前面显示 OK」。
    输出用 UTF-8，Windows 控制台按 chcp 65001 显示。
    """
    print('=' * 68)
    print('  Confucius4-R2T2 实时字幕 · 环境检查')
    print('=' * 68)
    print(f'包目录：{PKG_ROOT}')
    print(f'模型目录：{MODELS}')
    print()

    # ── 1. 依赖 ────────────────────────────────────────────────────
    print('── 依赖 ──')
    # 注意：**不检查 torch** —— 本程序刻意不依赖它（USE_TORCH=0），
    # 客户包里也不带 torch，列成「缺」只会误导客户。
    deps = [('numpy', 'numpy'), ('openvino', 'openvino'),
            ('openvino_genai', 'openvino_genai'),
            ('transformers', 'transformers'), ('sounddevice', 'sounddevice'),
            ('soundcard', 'soundcard')]
    for label, mod in deps:
        try:
            m = __import__(mod)
            ver = getattr(m, '__version__', '')
            print(f'  [ OK ] {_pad(label, 16)} {ver}')
        except Exception as e:
            print(f'  [缺 ] {_pad(label, 16)} {type(e).__name__}: {e}')
    print()

    # ── 2. 设备 ────────────────────────────────────────────────────
    print('── OpenVINO 设备 ──')
    devs = _check_devices()
    if devs:
        for d, full in devs.items():
            print(f'  [ OK ] {_pad(d, 8)} {full}')
    else:
        print('  [缺 ] 未探测到任何 OpenVINO 设备')
    has_gpu = any(d.startswith('GPU') for d in devs)
    has_npu = any(d.upper() == 'NPU' for d in devs)
    print(f'  Intel 集显 (GPU)：{"[ OK ] 可用" if has_gpu else "[缺 ] 不可用"}')
    print(f'  Intel NPU     ：{"[ OK ] 可用" if has_npu else "[缺 ] 不可用"}')
    # 🔴 CPU 已从设备清单移除（用户决定 2026-10-23）⇒ 明说，免得
    #    客户以为「没检测到 CPU」是安装故障。
    print('  注：CPU 推理已从可选设备清单移除（性能不推荐）；'
          '如确需 CPU 请用命令行 --asr-device CPU / --mt-device CPU。')
    print()

    # ── 3. ASR 后端 ────────────────────────────────────────────────
    print('── ASR 后端（识别）──')
    models = _check_models()
    for key, cfg in ENGINES.items():
        ok, why = models[key]
        need = cfg.get('device', '')
        dev_ok = True
        if need == 'GPU.0':
            dev_ok = has_gpu
        elif need.upper() == 'NPU':
            dev_ok = has_npu
        mark = '[ OK ]' if (ok and dev_ok) else '[缺 ]'
        extra = '' if dev_ok else '（本机没有该设备）'
        print(f'  {mark} {_pad(cfg["label"], 26)} {why}{extra}')
    print()

    # ── 4. 翻译后端 ────────────────────────────────────────────────
    print('── 翻译后端（Hy-MT2-1.8B）──')
    for key, cfg in MT_ALL_CANDIDATES.items():
        ok = cfg.get('available')
        bundled = cfg.get('bundled', True)
        if ok:
            mark = '[ OK ]'
        elif bundled:
            mark = '[缺 ]'
        else:
            # 本包本就不附带这个量化版本（不是客户机缺文件）——
            # 用 [ — ] 而不是 [缺 ]，免得客户误以为安装坏了。
            mark = '[ — ]'
        dev = cfg.get('device') or '跟随 --mt-device'
        dev_ok = True
        if dev == 'GPU.0':
            dev_ok = has_gpu
        elif dev.upper() == 'NPU':
            dev_ok = has_npu
        extra = '' if dev_ok else '（本机没有该设备）'
        if ok:
            note = ''
        elif bundled:
            note = '（缺模型）'
        else:
            note = '（本包不附带该量化版本）'
        print(f'  {mark} {_pad(cfg["label"], 26)} {_pad(dev, 8)} {note}{extra}')
    print()

    # ── 5. 音频设备 ────────────────────────────────────────────────
    print('── 音频设备 ──')
    mics = list_input_devices()
    if mics:
        for idx, name in mics:
            print(f'  [ OK ] 麦克风 {name}')
    else:
        print('  [缺 ] 未找到可用麦克风（MME / Windows WASAPI）')
    outs = list_output_devices()
    if outs:
        for oid, name in outs:
            print(f'  [ OK ] 输出 {name}  id={oid}')
    else:
        print('  [缺 ] 未找到可回环的输出设备（--source system 需要 Windows WASAPI）')
    print()

    # ── 6. 结论 ────────────────────────────────────────────────────
    ok_backends = [k for k, (ok, _) in models.items() if ok]
    print('=' * 68)
    if has_gpu and ok_backends:
        print(f'  结论：环境正常。ASR 可用后端 {len(ok_backends)} 个，'
              f'Intel 集显可用。')
    else:
        if not has_gpu:
            print('  结论：**未检测到 Intel 集显**，Intel 后端无法运行。')
        if not ok_backends:
            print('  结论：**模型文件不完整**，请确认包已完整解压。')
    print('=' * 68)


def main():
    ap = argparse.ArgumentParser(description='Confucius4-R2T2 实时字幕（多后端）')
    ap.add_argument('--engine', choices=list(ENGINES), default='gpu_int8')
    ap.add_argument('--source', choices=list(audio_source.SOURCES), default=None,
                    help='音频来源：mic=麦克风（默认）/ system=系统声音（WASAPI 回环）/ '
                         'file=音频文件')
    ap.add_argument('--device', type=int, default=None, help='CLI 模式的麦克风序号')
    ap.add_argument('--system-device', default=None,
                    help='CLI 模式的系统输出设备 WASAPI id（--source system）；'
                         '省略=系统默认输出设备')
    ap.add_argument('--file', default=None, help='用音频文件按实时速度回放代替麦克风')
    ap.add_argument('--speed', type=float, default=1.0,
                    help='文件回放速度（1.0=实时，>1 更快，0=全速跑批）')
    ap.add_argument('--loop', action='store_true', help='文件播完后从头循环播放')
    ap.add_argument('--cli', action='store_true')
    ap.add_argument('--max-seconds', type=float, default=0.0)
    ap.add_argument('--out', default=None, help='CLI 模式：把定稿文本写到文件')
    ap.add_argument('--font-size', type=int, default=26)
    ap.add_argument('--autostart', action='store_true')
    ap.add_argument('--selftest', type=float, default=0.0,
                    help='GUI 自测：回放到这么多秒后截屏并退出（需配合 --file --autostart）')
    ap.add_argument('--selftest-out', default=None)
    ap.add_argument('--selftest-mt-switch', action='store_true',
                    help='自测结束前模拟切换翻译后端，验证切换后翻译仍工作（回归用）')
    ap.add_argument('--list-devices', action='store_true')
    ap.add_argument('--check', action='store_true',
                    help='环境检查：设备、各后端模型、翻译后端、音频设备'
                         '（Diagnose.bat 用这个参数）')
    ap.add_argument('--asr-lang', default=ASR_LANG_AUTO,
                    choices=[ASR_LANG_AUTO] + list(ASR_LANGS),
                    help='ASR 识别语种（auto=自动检测，默认）。指定后会把语种提示'
                         '注入模型（prompt 后缀 language {语种}<asr_text>），'
                         '可显著降低语种误判；语种名用模型的英文名，'
                         '如 Chinese / English / Japanese / Korean')
    ap.add_argument('--translate', choices=list(TARGETS), default='off',
                    help='实时翻译目标语言（Hy-MT2-1.8B）；off=不翻译')
    ap.add_argument('--mt-engine', choices=list(MT_ENGINES), default=MT_DEFAULT,
                    help='翻译后端（设备 × 量化）；auto = 用 --mt-device + LIVECAP_MT_MODEL')
    ap.add_argument('--mt-ctx', action='store_true',
                    help='翻译时带上一句原文做上下文（C-099②，减少术语/指代错误）')
    ap.add_argument('--mt-glossary', action='store_true',
                    help='H-003：翻译时带上芯片/硬件术语表（官方 Terminology 模板，'
                         'QS→资格样品等）；prompt 变长约 +200 token，延迟会涨')
    ap.add_argument('--mt-draft', action='store_true',
                    help='开启草稿译文：除定稿文本外，还实时翻译还没定稿的那句'
                         '（界面上的浅蓝色预览）。默认关闭 —— 只翻译已定稿的文本；'
                         '草稿每 1.5s 翻一次近整句，是 ASR 积压的主要来源')
    # ── TTS（C-101 P4）──
    # 🔴 **默认 on**（APP-014：TTS 已从「实验性」转为**正式功能**）。
    #    ⚠️ 默认 None（而不是 'on'）⇒ GUI 与 CLI 都能区分
    #       「用户没给」与「用户显式给了 --tts off」
    #       ⇒ GUI 初值按「没给 ⇒ 开启」，显式 off 则仍按 off。
    ap.add_argument('--tts', choices=['off', 'on'], default=None,
                    help='译文语音输出开关。**默认 on**（TTS 已是正式功能）；'
                         '显式 --tts off 可关闭。'
                         '⚠️ 请佩戴耳机，避免 TTS 声音被 ASR 回采造成回授')
    ap.add_argument('--tts-precision', default='f32', choices=['f32', 'f16'],
                    help='TTS 推理精度')
    ap.add_argument('--tts-voice', default='A', choices=['A'],
                    help='音色：预设 A（客户包只随包分发音色 A；'
                         '音色 B / 克隆说话人素材按 BRIEF 不进包）')
    ap.add_argument('--tts-out', default=None,
                    help='CLI 回放测试：把语音按真实时间轴混成一个 wav 落盘；'
                         '同时写 <out>.tts.jsonl（逐句时间线）')
    ap.add_argument('--tts-out-device', default=None,
                    help='TTS 播放输出设备（名称或索引；默认系统默认输出）')

    # ── 推理设备（APP-004 第 3 条）──
    # 三个模型各一个设备；不给就用配置文件里的（再没有就用推荐默认值）。
    ap.add_argument('--asr-device', default=None,
                    help='ASR 推理设备（GPU.0 / NPU；CPU 已从清单移除，'
                         '但仍可显式指定）。不给则用配置文件里的选择')
    ap.add_argument('--mt-device', default=None,
                    help='翻译推理设备（GPU.0 / NPU；CPU 已从清单移除，'
                         '但仍可显式指定）。不给则用配置文件里的选择')
    ap.add_argument('--tts-device', default=None,
                    help='语音输出推理设备（默认 NPU）。不给则用配置文件里的选择')
    args = ap.parse_args()

    # 设备解析：命令行 > 配置文件 > 推荐默认值；不可用时回退并提示。
    _dev_cli = {
        'asr': args.asr_device,
        'mt': args.mt_device,
        'tts': args.tts_device,
    }
    _dev_sel, _dev_notes = device_config.get_devices(_dev_cli)
    args.asr_device = _dev_sel['asr']
    args.mt_device = _dev_sel['mt']
    args.tts_device = _dev_sel['tts']
    args.device_notes = _dev_notes

    # 没显式给 --source 时按老习惯推断：给了 --file 就是文件模式，否则麦克风
    if args.source is None:
        args.source = 'file' if args.file else 'mic'
    # GUI 也要用这个值（App 读 args.source 初始化下拉框）

    if args.check:
        run_check()
    elif args.list_devices:
        list_devices()
    elif args.cli:
        run_cli(args)
    else:
        import tkinter as tk
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        root = tk.Tk()
        App(root, args)
        root.mainloop()


if __name__ == '__main__':
    main()
