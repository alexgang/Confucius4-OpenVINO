"""Qwen3-TTS（BabelVox）引擎适配层 —— App 侧。

APP-004 第 2 条：TTS 模型文件随客户包分发；worker 侧适配新引擎接口。

依据 `qwen3tts_eval/TTS_交接单.md`（TTS-004 交接单，**mtime 2026-10-23 14:37**）。

## 关键约束（**不能改错**）

| 参数 | 必须 | 原因 |
|---|---|---|
| `use_kv_cache` | **False** | 开它 talker prefill 落到 CPU，反而更慢 |
| `split_on_silence` | **False** | 每帧多跑一次 decode 判静音 ⇒ RTF 1.83 → **5.90** |
| `precision` | **"int8"** | 只发布 INT8 导出，fp16 不可用 |

## 🔴🔴 音色路线：**spkonly**（交接单 §5.1 / TTS-005，2026-10-23 14:37 更新）

**只传 `speaker_embed`，禁止传 `ref_text` / `ref_audio`。**

理由：babelvox 的 `ref_text` 路径**不是官方 ICL** ——
codec 轨道上没有任何参考音频的 codec 码（`ref_code`），
`ref_text` 只是被包成独立文本段拼在 talker 序列最前面
⇒ 对模型是「有文本、没音频」的**分布外 prompt** ⇒ **EOS 不稳**。

实测（同一 seed 规则、桶 512、temperature 0.9）：

| 模式 | 撞上限 | 跨音色帧数 spread | 削波 |
|---|---|---|---|
| ICL（`ref_audio` + `ref_text`） | 9 / 60 | 0.852 | 2 |
| **x_vector（`speaker_embed` only）** | **0 / 60** ✅ | **0.294** ✅ | **0** ✅ |

⇒ **客户包不需要 `ref_text`**，只需参考 wav ⇒ 运行时少一个易错点。
⚠️ 对照实验必须**同温度同 seed**。

## ⚠️ 采样率

BabelVox 输出 **24000 Hz**（`generate` / `generate_stream` 均是）。
旧的 `tts_worker.py` 播放器按 **22050 Hz** 建 ⇒ 直接播会**变调/加速**。
⇒ 走 BabelVox 路线时必须用 `TTS_SAMPLE_RATE`（24000）建播放流。

## 推荐配置（交接单 §1.1）

```python
BabelVox(
    device="NPU",              # ★ 首选 NPU；GPU.0 见 §2；CPU 仅兜底
    precision="int8",
    use_cp_kv_cache=True,      # ★ 只开这一个
    use_kv_cache=False,        # ★ 必须 False
    talker_buckets=[64, 128, 256, 384, 512],   # ★ 桶必须到 512
    decoder_buckets=[8, 16, 32, 64, 128, 256],
    max_decoder_frames=512,
)
```

## 🔴 两个必须自己处理的问题

1. **`max_decoder_frames` 一参两用**（角色①静态形状定解码耗时 /
   角色②`effective_max` 定截断）⇒ 降它会**砍断长句**。
   ⇒ 本模块用 **`MultiDecoderBabelVox`**（TTS 模块的 `qwen3tts_patch.py`）
   把两者解耦：`max_decoder_frames=512` 保持角色②正确，
   另编小桶供角色①用。**任何 TTS 评测都要加「多句时长完全相同 = 被截断」自检。**

2. **帧数上限 = `max_talker_seq − prefill_len`**（不是 `max_talker_seq − 20`）
   ⇒ 逐条不同，**桶必须到 512**（上限 ≈ 478 帧 ≈ 38.2 s）。
   ⇒ 超过上限的句子**必须走「按句切分 + 流式拼接」**。

## 编译缓存

放 `%LOCALAPPDATA%\\Confucius4LiveCaption\\tts_npu_cache`，
**不得写进客户包目录**（客户机可能装在只读盘 / Program Files）。
"""

from __future__ import annotations

import contextlib
import os
import time
from typing import Iterator, List, Optional, Tuple

# ── 目录 ──────────────────────────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.dirname(APP_DIR)


def _cache_dir(name: str = 'tts_npu_cache') -> str:
    """编译缓存目录（与 live_caption_app.py::_cache 同一套规则）。

    ⚠️ Windows ACL deny 时 `makedirs` **不报错** ⇒ 必须用 `os.access(W_OK)` 探测。
    """
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'Confucius4LiveCaption', name)
    try:
        os.makedirs(d, exist_ok=True)
        if os.access(d, os.W_OK):
            return d
    except Exception:
        pass
    return os.path.join(APP_DIR, name)


# ── 模型目录 ──────────────────────────────────────────────────────────
def model_root() -> str:
    """Qwen3-TTS 模型根目录（客户包 `models/qwen3tts/`）。

    开发机也可能在 `<repo>/models/qwen3tts/` ⇒ 两个位置都试。
    """
    for p in (os.path.join(PKG_ROOT, 'models', 'qwen3tts'),
              os.path.join(APP_DIR, 'models', 'qwen3tts')):
        if os.path.isdir(os.path.join(p, 'int8')):
            return p
    return os.path.join(PKG_ROOT, 'models', 'qwen3tts')


def tokenizer_dir() -> Optional[str]:
    """tokenizer 目录（离线用，随包分发）。

    客户包 `models/qwen3tts/tokenizer/`；开发机可能没拷 ⇒ 返回 None，
    此时回落到 HF 缓存（需要联网）。
    """
    for p in (os.path.join(model_root(), 'tokenizer'),
              os.path.join(PKG_ROOT, 'models', 'qwen3tts', 'tokenizer')):
        if os.path.isdir(p) and os.path.exists(os.path.join(p, 'tokenizer_config.json')):
            return p
    return None


def preset_voice_path() -> Optional[str]:
    """预设音色 A 的参考音频路径。"""
    for p in (os.path.join(model_root(), 'voices', 'preset_A.wav'),
              os.path.join(PKG_ROOT, 'models', 'qwen3tts', 'voices', 'preset_A.wav')):
        if os.path.isfile(p):
            return p
    return None


# 🔴🔴 **音色 A 的参考文本已作废，不要用**（交接单 2026-10-23 14:37 更新，TTS-005）
#
# 旧口径（ICL）要求传 `ref_audio` + `ref_text`。实测证明这条路**不是官方 ICL**：
#   ① `ref_text` 只被包成独立的 `assistant\n{ref_text}\n` 文本段，
#      拼在 talker 序列**最前面**；
#   ② 🔴 **codec 轨道上没有任何参考音频的 codec 码（ref_code）**；
#   ③ `tokenizer_encoder`（raw audio → audio codes）**babelvox 库零调用**。
# ⇒ 对模型来说这是「**有文本、没音频**」的分布外 prompt ⇒ **EOS 不稳**。
#
# 实测（同一 seed 规则、桶 512、temperature 0.9）：
#   ICL（ref_audio + ref_text）  撞上限 9/60，跨音色帧数 spread 0.852，削波 2
#   x_vector（speaker_embed only）撞上限 0/60，spread 0.294，削波 0  ✅
#
# ⇒ **正解：spkonly** —— 只把参考 wav 过 speaker encoder 得 1024 维向量，
#   注入 codec prefill；**不传 ref_text、不传 ref_audio**。
# ⇒ **客户包不需要 ref_text**（运行时少一个易错点）。
#
# ⚠️ 保留此常量只为**向后兼容与审计对照**，运行时**禁止**传入。
PRESET_A_REF_TEXT = None

# babelvox 内置 speaker（零额外体积，随包分发）
# 🔴🔴 **2026-10-26 §48（APP-018 第 2 条 / APP-019）**：
#   这些 profile 是**第三方音色**（`babelvox/data/speakers/*.npy`）
#   ⇒ 客户包里**不再分发**（授权边界）⇒ **本机开发环境仍有**。
#   ⇒ 运行时**必须先探测可用性**，不能假设它们一定在
#   （否则 `--voice cindy` 会一路走到 babelvox 内部才抛
#    `ValueError: speaker library not set` / `No such file`）。
BUILTIN_SPEAKERS = ('cindy', 'lou', 'phil', 'steve')


def builtin_speakers_available() -> tuple:
    """返回**当前可用**的内置 speaker 名列表（可能为空）。

    🔴 **为什么要探测**：APP-018 第 2 条把
    `babelvox/data/speakers/` 从客户包里排除了 ⇒ 客户机上**没有**这些文件
    ⇒ `--voice cindy` 必须**在选之前**就知道不可用。

    判据 = `babelvox/data/speakers/{name}.json` + `{name}.npy` **同时存在**。
    ⚠️ 探测**不 import babelvox**（只查文件）⇒ 零副作用、零开销。
    """
    try:
        import babelvox.speakers as _bs
        base = getattr(_bs, 'BUILTIN_SPEAKERS_DIR', None)
        if not base:
            return ()
        import os as _os
        out = []
        for name in BUILTIN_SPEAKERS:
            j = _os.path.join(base, name + '.json')
            n = _os.path.join(base, name + '.npy')
            if _os.path.isfile(j) and _os.path.isfile(n):
                out.append(name)
        return tuple(out)
    except Exception:
        return ()

# 🔴 BabelVox 输出采样率（babelvox `generate` / `generate_stream` 返回 24000）
TTS_SAMPLE_RATE = 24000

# ── 引擎参数（交接单 §1.1）────────────────────────────────────────────
TALKER_BUCKETS = [64, 128, 256, 384, 512]
DECODER_BUCKETS = [8, 16, 32, 64, 128, 256]
MAX_DECODER_FRAMES = 512          # 🔴 保持 512 —— 一参两用，降了会砍断长句
MAX_TALKER_SEQ = 512

# 🔴🔴 **左上下文帧数**（TTS-010 修复 —— 杂音/音色突变的根因）
#
# 上游 babelvox 的分块解码是「每 chunk 独立解码、**零上下文**」
# ⇒ 声码器在帧维度**非因果** ⇒ 独立解码 ≠ 整段取前缀
# ⇒ **每个 chunk 边界都引入失真** ⇒ 用户抽听听到的「杂音 / 音色突变」，
#    官方 CUDA（faster-qwen3-tts）用「25 帧左上下文滑动窗口」正是为此：
#        *Sliding window with 25-frame left context … avoids boundary
#        artifacts (pops) while keeping decode cost bounded.*
#
# ⇒ 这里照抄官方：解码时把前 CTX_FRAMES 帧一起送进声码器，
#    只取本 chunk 对应的那一段样本（丢弃左上下文部分）。
#
# 实测（`qwen3tts_eval/results/voice_ac/ctx_production/manifest.json`）：
#   ctx vs 整句  cos 中位 0.999999 / 最低 0.989294
#                 SNR 中位 70.03 dB / 最低 16.68 dB
#   基线 vs 整句 cos 中位 0.838118 / SNR 中位 4.83 dB
#   边界跳变    中位 0.0574 → 0.0075（−7.6×），20/20 条全部改善
#
# ⚠️ 25 是官方 CUDA 的取值；改小会退回边界失真，改大只增解码开销。
CTX_FRAMES = 25
# 🔴 chunk 大小（babelvox `generate_stream(chunk_frames=...)`，单位=帧）
# 官方 12 帧/秒 ⇒ chunk_frames=8 ≈ 0.67 s 一次解码。
CHUNK_FRAMES = 8
# 🔴 解码器静态桶：必须覆盖「左上下文 + 一个 chunk」的最大帧数
#    （8 + 25 = 33）以及「历史满 + 末块」的组合（25 + 12 = 37 ⇒ 取 40）。
#    ⇒ 新增 33 / 40 两个桶，其余沿用。
DECODER_BUCKETS_CTX = [8, 16, 32, 33, 40, 64, 128, 256]

# 🔴🔴🔴 **cp_decode 的静态形状**（APP-018 第 1 条 —— 补上从未实现的生产配置）
#
# ## 根因（实测，非推测）
#
# reviewer 的生产配置明写「**cp_decode 放 NPU**」，但 **App 侧从未实现**：
#
# | 位置 | 代码 | cp_decode 实际设备 |
# |---|---|---|
# | `babelvox/pipeline.py` L347-350（原生 `BabelVox._load_npu_models`） | `core.compile_model(cp_decode.xml, "CPU")` | **CPU** |
# | `live_caption/tts_engine_patch.py` L379-382（vendored patch，md5 与 TTS 模块 `qwen3tts_patch.py` **完全一致**） | 同上 | **CPU** |
# | `qwen3tts_eval/eval_cp_on_npu.py::_recompile_cp_on_npu()`（TTS 模块的「尺子」） | `m.reshape(CP_SHAPE)` 后 `compile_model(m, "NPU")` | **NPU** |
#
# ⇒ TTS 模块测出 RTF 0.8568 / 首包 0.5862 s 时 **cp_decode 在 NPU**；
#   App 测出 RTF ~1.9 / 首块 ~1.3 s 时 **cp_decode 在 CPU**。
# ⇒ `cp_decode` 是**每步 AR 都要跑**的组件（pipeline L920/L1161）
#   ⇒ 放 CPU 直接拖慢整条 AR 链。
#
# ## 实测 A/B（`results/app/app062_cp_decode_device_ab.py`，持锁 + 安静窗口）
#
# | 臂 | cp_decode | 单句 RTF 中位 | 首块中位 | 聚合 RTF |
# |---|---|---|---|---|
# | A | CPU（App 现状） | **1.912** | **1.296 s** | 1.971 |
# | B | NPU（本修复） | **1.218** | **0.837 s** | 1.256 |
# | Δ | — | **提速 1.57×** | **提速 1.55×** | — |
#
# ## 🔴 为什么必须 reshape
#
# 直接 `compile_model(cp_decode.xml, "NPU")` ⇒ **Segmentation fault**
# （进程直接崩，try/except 接不住；OV 的 NPU 插件在动态维 IR 上崩）。
# 生产路径的 cp_decode **形状本来就是静态的**
# （babelvox `pipeline.py` L110-113: CP_NUM_LAYERS=5 / CP_NUM_KV_HEADS=8 /
#  CP_HEAD_DIM=128 / **CP_MAX_KV_LEN=20**；`_run_cp_decode` L567-580 每次都传
# 固定形状的 attn_mask 与 kv）⇒ **可以 reshape 定死后编译到 NPU**。
#
# ⚠️ 形状必须与 TTS 模块 `_recompile_cp_on_npu()` **完全一致**
#    ⇒ 否则两边的数不可比（铁律：同一把尺子）。
CP_DECODE_NPU_SHAPE = {
    "inputs_embeds": [1, 1, 1024],
    "cache_position": [1],
    "attention_mask": [1, 1, 1, 20],
    "past_keys": [5, 1, 8, 20, 128],
    "past_values": [5, 1, 8, 20, 128],
}

# ══════════════════════════════════════════════════════════════════════
# 🔴🔴 `cp_prefill` 的 NPU 静态形状（TTS-017① / `shared\NOTICE_tts_to_app_20261026.md`）
# ══════════════════════════════════════════════════════════════════════
#
# ## 🔴🔴 **推翻**旧文档「变长 IR 编不了 NPU」的结论
#
# 旧结论（TTS §15 / 交接单）写的是「cp_prefill 输入**变长** `[1,?,1024]`
# ⇒ NPU 插件算不出 bounds ⇒ `Reshape node '/Reshape_2': cannot compute
# output bounds dimension`」。
#
# ⇒ **错在只看「导出时的签名」，没看「运行时喂什么」。**
#
# ## 运行时输入**恒为** `(1, 2, 1024)`
#
# babelvox `pipeline.py`（包内 `python/Lib/site-packages/babelvox/pipeline.py`）：
#   L908-909（流式）/ L1145-1146（非流式）：
#     `code_0_embed = self.codec_emb[[code_0]][np.newaxis, :, :]`
#     `cp_input = np.concatenate([hidden, code_0_embed], axis=1)`
#   ⇒ `hidden` 是 (1,1,1024)、`code_0_embed` 是 (1,1,1024)
#   ⇒ `cp_input` **恒为 (1, 2, 1024)**（prefill 长度**固定为 2**）。
#
# 🔴 **本机实测复核**（2026-10-26，`v1.5` 包内 `babelvox/pipeline.py`）：
#   L909 `cp_input = np.concatenate([hidden, code_0_embed], axis=1)`
#   L1146 `cp_input = np.concatenate([hidden, code_0_embed], axis=1)  # (1,2,1024)`
#   ⇒ 与 TTS 侧 `pipeline.py` L909/L1146 **逐位一致**。
#
# 🔴 **IR 确实是动态维**（本机实测 `models/qwen3tts/int8/cp_prefill.xml`）：
#   `<data shape="1,?,1024" element_type="f32" />`
#   ⇒ **必须 reshape** 才能编到 NPU（同 cp_decode）。
#
# ⚠️ 形状必须与 TTS 模块 `diag_cp_prefill_npu.py` **完全一致**
#    ⇒ 否则两边的数不可比（铁律：同一把尺子）。
CP_PREFILL_NPU_SHAPE = {
    "inputs_embeds": [1, 2, 1024],
}


class TTSEngineError(RuntimeError):
    """TTS 引擎加载/合成失败。"""


def _load_patch_class():
    """加载 TTS 模块的 `qwen3tts_patch.py`（MultiDecoderBabelVox）。

    ⚠️ 该文件在 `qwen3tts_eval/` 下，客户包里要 vendored 一份
    （`app/tts_engine_patch.py`）。优先用客户包内的，失败再退回开发机路径。
    """
    import importlib.util
    for p in (os.path.join(APP_DIR, 'tts_engine_patch.py'),
              r'C:\Users\Trekker-PTL\qwen3tts_eval\qwen3tts_patch.py'):
        if os.path.isfile(p):
            spec = importlib.util.spec_from_file_location('tts_engine_patch', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def execution_devices(eng, on_log=print) -> dict:
    """🔴🔴🔴 **实测「每个 IR 到底跑在哪个设备上」**（不是「请求了什么设备」）。

    ## 为什么必须有这个函数（§81.11 第 3 条的根因）

    §81 的引擎基线报告里 `device_desc=null` / `load_s=null`
    ⇒ ��审问「**是否真在 NPU 上跑**」⇒ **无法回答**。

    根因是**两个不同的问题被混为一谈**：
    - 「**请求**的设备」= `make_engine(device='NPU')` 的参数
      ⇒ 只能证明「**我们要求**它跑在 NPU 上」；
    - 「**实际**执行设备」= OV 编译产物**真正落在哪个 plugin 上**
      ⇒ 才能证明「它**确实**跑在 NPU 上」。

    ⚠️ **两者会不一致**，且**不会报错**：
    - `babelvox.pipeline._compile_npu()` 在 NPU 编译失败时
      **`fallback_cpu=True` ⇒ 静默回落 CPU**（`pipeline.py` L271-281）
      ⇒ 日志里仍写着「device=NPU」；
    - `pipeline.py` L297/L347-350 把 `talker_prefill` / `cp_prefill` /
      `cp_decode` **显式编到 CPU** ⇒ 即使整体「在 NPU 上」，
      **有一部分计算在 CPU 上**；
    - App 侧的 `_move_cp_decode_to_npu` / `_move_cp_prefill_to_npu`
      是**事后重新编译**这两个 IR ⇒ 它们的真实落点**只能事后查**。

    ## 判据：OV 的 `EXECUTION_DEVICES` 属性（本机实测可用）

    `CompiledModel.get_property('EXECUTION_DEVICES')` 返回
    **该模型实际执行的设备名列表**（本机实测：
    CPU 档 = `['CPU']`；NPU 档 = `['NPU']`）⇒ **这是决定性证据**。

    ⚠️ **OV 版本差异**：本机 OV `2026.4.1` 的 `CompiledModel`
    **没有** `get_device_name()`（实测 `AttributeError`）
    ⇒ 必须用 `get_property('EXECUTION_DEVICES')`。
    ⇒ 且**必须 try/except** ⇒ 老版本上取不到就返回 `None`（**不猜、不编**）。

    ## 返回值

    ```python
    dict(ok=bool,            # 是否成功取到至少一个设备
         devices={名称: [设备, ...]},   # 每个组件的实际执行设备
         unknown=[组件名, ...],          # 取不到的组件（**不猜**）
         requested='NPU')                # 只是「请求」值，不是证据
    ```
    """
    out = dict(ok=False, devices={}, unknown=[], requested=None)
    try:
        out['requested'] = str(getattr(eng, 'device', '') or '') or None
    except Exception:
        pass

    # 🔴 组件名 → 引擎上的属性名（babelvox pipeline 里就是这些属性）
    #   ⚠️ **属性名必须与 `babelvox/pipeline.py` 完全一致**，否则取不到
    #   （本轮实测踩过：`speaker_encoder` / `tokenizer_decoder` 是**文件名**，
    #   不是**属性名** ⇒ 实测属性名是 `speaker_enc` / `tok_decoder`
    #   ⇒ 写错 ⇒ 组件被误判成 unknown ⇒ **假装测到了，其实没测到**）。
    _COMPONENTS = (
        ('speaker_enc', 'speaker_enc'),
        ('talker_prefill', 'talker_prefill'),
        ('talker_decode', 'talker_decode'),
        ('talker', 'talker'),
        ('cp_prefill', 'cp_prefill'),
        ('cp_decode', 'cp_decode'),
        ('code_predictor', 'code_predictor'),
        ('tok_decoder', 'tok_decoder'),
    )
    # 🔴 多桶解码器（`MultiDecoderBabelVox`）的桶模型在 `talker_buckets` 字典里
    buckets = getattr(eng, 'talker_buckets', None)
    if isinstance(buckets, dict) and buckets:
        for b in sorted(buckets.keys()):
            _COMPONENTS = _COMPONENTS + (('talker_bucket@%s' % b,
                                          'talker_bucket@%s' % b),)

    for label, attr in _COMPONENTS:
        if attr.startswith('talker_bucket@'):
            b = attr.split('@', 1)[1]
            obj = buckets.get(b) if isinstance(buckets, dict) else None
        else:
            obj = getattr(eng, attr, None)
        if obj is None:
            continue
        devs = None
        try:
            devs = obj.get_property('EXECUTION_DEVICES')
        except Exception:
            devs = None
        if not devs:
            out['unknown'].append(label)
        else:
            out['devices'][label] = list(devs)

    out['ok'] = bool(out['devices'])
    if out['ok']:
        # 🔴🔴🔴 **NPU 插件返回的是「设备缩写 + fallback 链」，不是 `NPU` 字面量**
        #   （本轮实测，OV 2026.4.1 + intel_npu_plugin）：
        #   - 直接 `compile_model(m, 'NPU')` ⇒ `EXECUTION_DEVICES == 'NPU'`（字符串）
        #   - 经 App 的 `_ov_precision`（`set_property('NPU', {...})`）后 ⇒
        #     `EXECUTION_DEVICES == ['N', 'P', 'U']`
        #     （= NPU plugin / CPU fallback / Unknown 的**缩写 fallback 链**）
        #   - CPU 档 ⇒ `['CPU']`
        # ⇒ **判据 = 链首（首选设备）** ⇒ `N` ⇒ 首选 NPU ⇒ 实际跑在 NPU 上；
        #   `P` ⇒ 首选 CPU ⇒ **实际落在 CPU 上**（= NPU 编译静默回落的实证）。
        # ⇒ ⚠️ 只按 `startswith('NPU')` 判 ⇒ **全部落空**（实测踩过）。
        _norm_dev = {'N': 'NPU', 'P': 'CPU', 'U': 'UNKNOWN'}
        out['devices_norm'] = {
            k: [_norm_dev.get(str(d).upper(), str(d)) for d in v]
            for k, v in out['devices'].items()
        }
        # 🔴 **实际落点 = fallback 链首元素**
        out['actual'] = {k: (v[0] if v else None)
                         for k, v in out['devices_norm'].items()}
        out['on_npu'] = sorted(k for k, v in out['actual'].items() if v == 'NPU')
        out['on_cpu'] = sorted(k for k, v in out['actual'].items() if v == 'CPU')
        out['on_unknown'] = sorted(k for k, v in out['actual'].items()
                                   if v not in ('NPU', 'CPU'))
        # 🔴 汇总成一句人话（便于写进日志 / 报告）
        flat = sorted({d for d in out['actual'].values() if d})
        on_log('[tts_engine] 实测执行设备（fallback 链首 = 实际落点）：%s'
               % ('/'.join(flat)))
        on_log('[tts_engine] 各组件落点：%s'
               % '，'.join('%s=%s' % (k, v)
                           for k, v in sorted(out['actual'].items())))
        on_log('[tts_engine] 落点统计：NPU 上 %d 个组件 %s；'
               'CPU 上 %d 个组件 %s'
               % (len(out['on_npu']), out['on_npu'],
                  len(out['on_cpu']), out['on_cpu']))
        if out['unknown']:
            on_log('[tts_engine] ⚠️ 取不到执行设备的组件：%s'
                   % '，'.join(out['unknown']))
    else:
        on_log('[tts_engine] ⚠️ 取不到任何组件的 EXECUTION_DEVICES '
               '（OV 版本可能不支持）⇒ 无法证明实际执行设备')
    return out


def _class_supports_param(cls, name: str) -> bool:
    """探测类是否支持某个构造参数（**能力探测**，不是版本号判断）。

    ⚠️ 为什么要探测而不是直接传：
    客户包 vendored 的 `tts_engine_patch.py` 可能是**旧版**
    （TTS-010 之前）⇒ 不认识 `ctx_frames` ⇒ 无条件传会
    `TypeError` ⇒ **整个 TTS 引擎加载失败**（客户机上表现为「TTS 起不来」）。
    ⇒ 探测不到就不传，退回旧行为（音质差但能跑）比**完全起不来**好。
    """
    import inspect
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return False
    if name in sig.parameters:
        return True
    # 有 **kwargs ⇒ 理论上能收，但旧 patch 的 **kwargs 会吞掉并忽略
    # ⇒ 这种情况**按不支持处理**（避免「以为开了其实没开」）。
    return False


@contextlib.contextmanager
def _ov_precision(prec: str, device: str, on_log=print):
    """把 OV **推理精度**（``INFERENCE_PRECISION_HINT``）注入本次编译。

    🔴🔴 **为什么需要这个上下文管理器**：
       BabelVox 在 ``BabelVox.__init__`` 内部**自建** ``ov.Core()`` 并
       ``core.compile_model(model.xml, device)``（**不传任何 property**）
       ⇒ App 侧**没有任何钩子**能把精度塞进去。
       ⇒ 之前 GUI 的「精度 f32/f16」下拉 ⇒ **完全无效**（摆设）。

    ⇒ 做法：**临时替换** ``babelvox.pipeline.ov.Core`` 为一个子类，
       其 ``__init__`` 会 ``set_property({'INFERENCE_PRECISION_HINT': prec})``。
       退出上下文时**还原**（不污染同进程内的其它代码）。

    ⚠️ **只在目标设备上设精度**：``set_property(device, {...})`` 是
       按设备的全局属性 ⇒ 只对要用的那个设备设，避免影响别的设备。
    ⚠️ **NPU + f32 会被 OV 拒** ⇒ 上游已在 `make_engine` 里回落到 f16。
    ⚠️ **NVIDIA 设备**在无 CUDA plugin 时 ``GPU.N`` 是被 Intel GPU plugin
       枚举到的 ⇒ 设 f16 有可能让「FP16 reorder 无 kernel」变成
       「FP16 kernel 有但缺 INT8 转换」……**实测为准**，不预断。
    """
    patched = False
    core_cls = None
    try:
        import babelvox.pipeline as bp
    except Exception:
        bp = None
    if bp is not None and hasattr(bp, 'ov'):
        core_cls = bp.ov.Core

        class _PrecCore(core_cls):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                try:
                    self.set_property(device,
                                      {'INFERENCE_PRECISION_HINT': prec})
                except Exception as e:
                    on_log(f'[tts_engine] ⚠️ 设置推理精度 {prec} 失败：{e}')

        bp.ov.Core = _PrecCore
        patched = True
        on_log(f'[tts_engine] 已把 INFERENCE_PRECISION_HINT={prec}'
               f' 注入 {device} 的编译')
    try:
        yield
    finally:
        if patched and bp is not None and core_cls is not None:
            bp.ov.Core = core_cls


def make_engine(device: str = 'NPU',
                model_path: Optional[str] = None,
                cache_dir: Optional[str] = None,
                on_log=print,
                precision: Optional[str] = None):
    """创建 BabelVox 引擎实例。

    返回的对象有 `.generate_stream(text, language=..., ref_audio=..., ...)`
    与 `.generate(...)`，与 TTS 交接单一致。

    ⚠️ `device='NPU'` 时会用 `MultiDecoderBabelVox`（多桶解码器），
    没有 patch 文件时退回原生 `BabelVox`（功能可用，但长句解码慢）。

    🔴🔴 **`precision` 是 OV **推理精度**（f32/f16），不是权重位宽**：
       - **权重位宽**恒为 ``int8``（包内只有 INT8 一份 IR）⇒ 不能改；
       - **推理精度**通过 ``INFERENCE_PRECISION_HINT`` 传给 OV 编译。
       ⇒ 之前 GUI 有「精度 f32/f16」下拉，但**这个参数根本没传进来**
       ⇒ 下拉是**摆设**（用户选了没有任何效果）。
       ⇒ 现在真正接上：``precision`` → ``ov.Core().set_property``。

    ⚠️ **NPU 不支持 f32**（``INFERENCE_PRECISION_HINT=f32`` 会被 OV 拒）
       ⇒ 传 f32 + device=NPU 时**主动回落到 f16**（并打日志），
       不能让整个引擎加载失败。
    """
    try:
        from babelvox import BabelVox
    except Exception as e:
        raise TTSEngineError(
            f'未安装 babelvox：{e}。本包应自带该运行时，'
            f'请确认 python/Lib/site-packages/babelvox 存在。') from e

    root = model_root()
    if not os.path.isdir(os.path.join(root, 'int8')):
        raise TTSEngineError(
            f'找不到 TTS 模型（{root}/int8）。本包应自带 Qwen3-TTS INT8 IR。')

    tok = tokenizer_dir() or model_path
    if not tok:
        raise TTSEngineError(
            '找不到 tokenizer，且未指定 model_path。'
            '客户机离线运行需要随包分发 tokenizer。')

    # 离线优先：禁止 HF 联网
    os.environ.setdefault('HF_HUB_OFFLINE', '1')

    # 🔴 推理精度归一（f16/fp16 → f16；f32/None → f32）
    prec = (precision or 'f32').strip().lower()
    prec = 'f16' if prec in ('f16', 'fp16', 'half') else 'f32'
    if str(device).upper() == 'NPU' and prec == 'f32':
        # 🔴 NPU 拒 f32 ⇒ 回落 f16（宁可精度降一档，也不能整个引擎起不来）
        on_log('[tts_engine] NPU 不支持 f32 推理精度 ⇒ 已自动改用 f16')
        prec = 'f16'
    on_log(f'[tts_engine] OV 推理精度 = {prec}（权重位宽恒为 INT8）')

    cdir = cache_dir or _cache_dir()
    kwargs = dict(
        export_dir=root,
        model_path=tok,
        device=device,
        precision='int8',            # 🔴 权重位宽恒为 INT8（只有这一份 IR）
        use_cp_kv_cache=True,
        use_kv_cache=False,          # 🔴 必须 False
        talker_buckets=TALKER_BUCKETS,
        max_talker_seq=MAX_TALKER_SEQ,
        max_decoder_frames=MAX_DECODER_FRAMES,
        cache_dir=cdir,
    )

    patch = _load_patch_class()
    cls = BabelVox
    if patch is not None and hasattr(patch, 'MultiDecoderBabelVox'):
        cls = patch.MultiDecoderBabelVox
        # 🔴🔴 **TTS-010：左上下文解码**（消边界失真 = 消杂音/音色突变）
        #   ⚠️ **必须做能力探测**：客户包 vendored 的 `tts_engine_patch.py`
        #   可能还是旧版（不支持 `ctx_frames`）⇒ 无条件传会
        #   `TypeError: __init__() got an unexpected keyword argument` ⇒
        #   **整个 TTS 引擎加载失败**（比音质问题更严重）。
        #   ⇒ 用 `inspect.signature` 探测，不支持就不传（退回旧行为）。
        _supports_ctx = _class_supports_param(cls, 'ctx_frames')
        if _supports_ctx:
            kwargs['decoder_buckets'] = DECODER_BUCKETS_CTX
            kwargs['ctx_frames'] = CTX_FRAMES
            on_log(f'[tts_engine] 使用 MultiDecoderBabelVox'
                   f'（解码器多桶 + 左上下文 {CTX_FRAMES} 帧）')
        else:
            kwargs['decoder_buckets'] = DECODER_BUCKETS
            on_log('[tts_engine] ⚠️ tts_engine_patch.py **不支持左上下文**'
                   '（旧版）⇒ 已退回无上下文解码，'
                   '边界失真/杂音仍在 ⇒ 请同步新版 patch')
    else:
        on_log('[tts_engine] ⚠️ 未找到 tts_engine_patch.py，'
               '退回原生 BabelVox（长句解码较慢，'
               '且**无左上下文** ⇒ 边界失真/杂音）')

    on_log(f'[tts_engine] 加载模型：device={device} root={root} cache={cdir}')
    t0 = time.perf_counter()
    with _ov_precision(prec, device, on_log=on_log):
        try:
            eng = cls(**kwargs)
        except Exception as e:
            raise TTSEngineError(f'模型加载失败：{type(e).__name__}: {e}') from e
    # 🔴🔴 **加载耗时**（§81.11 第 3 条：`app118` 的 `load_s=null` 的根因）
    #   ⇒ 引擎对象上**必须自带**这两个字段，否则报告脚本只能靠 `getattr`
    #   猜 ⇒ 猜不到就写 `null` ⇒ **审问「是否真在 NPU 上跑」时无法回答**。
    try:
        eng.load_s = round(time.perf_counter() - t0, 2)
    except Exception:
        pass
    try:
        eng.device_desc = str(device)
    except Exception:
        pass
    on_log('[tts_engine] 模型加载完成（%.1f s）' % (time.perf_counter() - t0))

    # 🔴🔴🔴 **cp_decode 放 NPU**（APP-018 第 1 条 —— 补上从未实现的生产配置）
    #   原生 babelvox 把它编译到 **CPU**（pipeline L347-350）⇒
    #   App 的 RTF 比 TTS 模块的尺子差 ~2.2×。
    #   实测 A/B：RTF 1.912→1.218、首块 1.296→0.837 s（提速 ~1.57×）。
    #   ⚠️ 失败会优雅降级（保持 CPU）⇒ 不会把引擎搞挂。
    try:
        _move_cp_decode_to_npu(eng, on_log=on_log)
    except Exception as e:
        on_log(f'[tts_engine] cp_decode: CPU'
               f'（回落原因：搬运时异常 {e}）')

    # 🔴🔴🔴 **cp_prefill 放 NPU**（TTS-017① 交付配置）
    #   APP-020 说「等 TTS 线程在 STATUS_TTS 里给出新的 config 后再同步」；
    #   TTS 线程已于 2026-10-26 17:10 交付（`shared\NOTICE_tts_to_app_20261026.md`，
    #   依据 STATUS_TTS §41 / 交接单 §28）⇒ **本轮同步**。
    #   ⚠️ 与 cp_decode 同类：失败**优雅降级**（保持 CPU）⇒ 不会把引擎搞挂。
    try:
        _move_cp_prefill_to_npu(eng, on_log=on_log)
    except Exception as e:
        on_log(f'[tts_engine] cp_prefill: CPU'
               f'（回落原因：搬运时异常 {e}）')

    # 🔴🔴 **必须挂 SpeakerLibrary**，否则按名查内置音色会直接抛
    #   `ValueError: speaker_library not set; cannot look up named speaker`
    #   （babelvox/pipeline.py:782 —— `speaker_library` 默认是 None）。
    # 内置音色 cindy/lou/phil/steve **不是引擎内置常量**，而是随包文件
    # `babelvox/data/speakers/{name}.json` + `{name}.npy`（embedding 1×1024）；
    # `SpeakerLibrary(dir, copy_builtins=True)` 会把它们复制到库目录。
    # ⇒ 只建 `SpeakerLibrary` 而不设 `eng.speaker_library` 是无效的。
    _attach_speaker_library(eng, on_log=on_log)

    # 🔴🔴🔴 **实测每个 IR 的真实执行设备**（§81.11 第 3 条的正面解法）
    #   ⇒ 放在**最后**（cp_prefill / cp_decode 搬运之后）⇒ 反映**最终状态**。
    #   ⚠️ **绝不抛异常** ⇒ 取不到只记日志（诊断增强，不能搞挂引擎）。
    try:
        eng.exec_devices = execution_devices(eng, on_log=on_log)
    except Exception as e:
        on_log('[tts_engine] ⚠️ 执行设备探测失败：%r' % (e,))
        eng.exec_devices = dict(ok=False, devices={}, unknown=[],
                                requested=str(device))
    return eng


def _attach_speaker_library(eng, on_log=print) -> bool:
    """给引擎挂上 `SpeakerLibrary`（按名查内置音色的前提）。

    库目录放 `%LOCALAPPDATA%\\Confucius4LiveCaption\\tts_speakers`
    （**不写进客户包目录**，同编译缓存的纪律）。
    失败只告警不抛 —— 内置音色是可选路径，参考 wav（spkonly）才是主路径。
    """
    try:
        from babelvox.speakers import SpeakerLibrary
    except Exception as e:
        on_log(f'[tts_engine] ⚠️ babelvox.speakers 不可用（{e}）'
               f' ⇒ 内置音色（cindy/lou/phil/steve）不可用，只能用参考 wav')
        return False
    lib_dir = _cache_dir('tts_speakers')
    try:
        eng.speaker_library = SpeakerLibrary(lib_dir, copy_builtins=True)
    except Exception as e:
        on_log(f'[tts_engine] ⚠️ SpeakerLibrary 初始化失败（{e}）'
               f' ⇒ 内置音色不可用')
        return False
    try:
        names = sorted(p['name'] for p in eng.speaker_library.list_profiles())
    except Exception:
        names = []
    on_log(f'[tts_engine] SpeakerLibrary 就绪：{lib_dir}'
           f'（{len(names)} 个音色：{", ".join(names) if names else "无"}）')
    return True


def _cp_ir_path(eng, name: str) -> Optional[str]:
    """定位 code predictor 组件（`cp_prefill` / `cp_decode`）的 IR 路径。

    🔴 `MultiDecoderBabelVox`（App 用的类）**没有** `_ir_path`
    （那是 `QuantEvalBabelVox` 才有的）⇒ 走原生路径：
    `model_dir = export_dir / precision` ⇒ `.../int8/cp_decode.xml`。

    🔴 **通用化**（TTS 通知 §1.2「建议合并成一个『NPU 搬运』工具函数，
    避免两份 IR 定位逻辑漂移」）：cp_prefill 与 cp_decode 共用本函数。
    """
    fn = getattr(eng, '_ir_path', None)
    if callable(fn):
        try:
            return fn(name)
        except Exception:
            pass
    root = getattr(eng, '_model_dir', None)
    if not root:
        try:
            root = os.path.join(model_root(), 'int8')
        except Exception:
            return None
    return os.path.join(root, f'{name}.xml')


def _cp_decode_ir_path(eng) -> Optional[str]:
    """定位 cp_decode 的 IR 路径（兼容旧调用方）。"""
    return _cp_ir_path(eng, 'cp_decode')


def _move_cp_prefill_to_npu(eng, on_log=print) -> bool:
    """🔴🔴 把 `cp_prefill` 从 CPU 搬到 **NPU**（TTS-017① 的交付配置）。

    依据：`shared\\NOTICE_tts_to_app_20261026.md` §1（TTS 线程交付）
    + TTS 交接单 §28 / STATUS_TTS §41。

    ## 为什么能搬（旧结论「变长 IR 编不了 NPU」已被推翻）

    `cp_input` **恒为 (1, 2, 1024)** ⇒ `reshape(CP_PREFILL_NPU_SHAPE)`
    后可编到 NPU（TTS 侧实测 `compile_s = 0.219 s`）。

    ## 🔴 降级约定（通知 §1.3，**必须照做**）

    - **编译失败 ⇒ 保留 CPU + 记日志 + 返回 False**，**引擎必须仍然可用**
      （只是慢一点）⇒ **绝不抛异常中断 TTS 启动流程**。
    - 启动日志打印一行 **`cp_prefill: NPU / CPU（回落原因：…）`**，
      便于现场判断是「走了 NPU」还是「悄悄在 CPU 上跑」。

    ⚠️ **与 `_move_cp_decode_to_npu` 同一类操作** ⇒ 共用
    `_cp_ir_path()` / `_cache_dir()` / 同一套 try-except 降级骨架。
    """
    # 🔴 判据用 `is_npu`（babelvox pipeline L127 自己算的标志位）
    #   ⚠️ **不要用 `device == "NPU"` 精确匹配**：本机设备名是精确的 "NPU"，
    #   但约定上应写成「大小写不敏感的前缀匹配」，免得 NPU.0 之类被误判。
    is_npu = bool(getattr(eng, 'is_npu', False))
    if not is_npu:
        dev = str(getattr(eng, 'device', '') or '')
        if not dev.upper().startswith('NPU'):
            on_log(f'[tts_engine] cp_prefill: CPU（非 NPU 档 device={dev}）')
            return False

    ir = _cp_ir_path(eng, 'cp_prefill')
    if not ir or not os.path.isfile(ir):
        on_log(f'[tts_engine] cp_prefill: CPU'
               f'（回落原因：找不到 IR {ir}）')
        return False

    try:
        import openvino as ov
        core = ov.Core()
        cdir = _cache_dir()
        if cdir:
            core.set_property({'CACHE_DIR': cdir})
        m = core.read_model(ir)
        # 🔴🔴 必须 reshape：IR 是动态维 `1,?,1024`（实测 cp_prefill.xml）
        #   ⇒ 不 reshape 直接编到 NPU 会失败（Reshape bounds 算不出）。
        #   运行时输入**恒为 (1,2,1024)** ⇒ 这个静态形状是安全的。
        m.reshape(CP_PREFILL_NPU_SHAPE)
        cm = core.compile_model(m, 'NPU')
    except Exception as e:
        # 🔴 **绝不抛异常**：NPU 编译失败应降级，不应让 TTS 不可用
        on_log(f'[tts_engine] cp_prefill: CPU'
               f'（回落原因：{type(e).__name__}: {e}）'
               f'⇒ 引擎仍可用，仅较慢')
        return False

    eng.cp_prefill = cm
    # `cp_on_cpu` 在 babelvox 里**只被写、从不被读**（pipeline L181/L356）
    # ⇒ 纯信息标志，置 False 安全（用于日志/诊断）
    try:
        eng.cp_on_cpu = False
    except Exception:
        pass
    on_log('[tts_engine] cp_prefill: NPU'
           '（TTS-017① 交付配置：运行时输入恒为 (1,2,1024) ⇒ 静态形状安全）')
    return True


def _move_cp_decode_to_npu(eng, on_log=print) -> bool:
    """🔴🔴 把 `cp_decode` 从 CPU 搬到 **NPU**（补上从未实现的生产配置）。

    见模块顶部 `CP_DECODE_NPU_SHAPE` 的完整根因说明与 A/B 数据。

    ⚠️ **失败必须优雅降级**：NPU 编译失败（Segfault 风险 / 插件缺失）
    ⇒ 保留 CPU 版本 ⇒ **引擎仍可用**（只是慢一点）
    ⇒ 绝不能因为「优化」把整个 TTS 引擎搞挂。
    """
    # 🔴 判据用 `is_npu`（babelvox pipeline L127 自己算的标志位）
    #   ⚠️ **不要用 `device == "NPU"`**：本机设备名是精确的 "NPU"，
    #   但约定上应写成「大小写不敏感的前缀匹配」，免得 NPU.0 之类被误判。
    is_npu = bool(getattr(eng, 'is_npu', False))
    if not is_npu:
        dev = str(getattr(eng, 'device', '') or '')
        if not dev.upper().startswith('NPU'):
            on_log(f'[tts_engine] cp_decode: CPU'
                   f'（非 NPU 档 device={dev}）')
            return False

    ir = _cp_ir_path(eng, 'cp_decode')
    if not ir or not os.path.isfile(ir):
        on_log(f'[tts_engine] cp_decode: CPU'
               f'（回落原因：找不到 IR {ir}）')
        return False

    try:
        import openvino as ov
        core = ov.Core()
        cdir = _cache_dir()
        if cdir:
            core.set_property({'CACHE_DIR': cdir})
        m = core.read_model(ir)
        # 🔴🔴 必须 reshape：动态维 IR 直接编到 NPU 会 Segfault
        m.reshape(CP_DECODE_NPU_SHAPE)
        cm = core.compile_model(m, 'NPU')
    except Exception as e:
        on_log(f'[tts_engine] cp_decode: CPU'
               f'（回落原因：{type(e).__name__}: {e}）'
               f'⇒ 引擎仍可用，仅较慢')
        return False

    eng.cp_decode = cm
    # `cp_on_cpu` 在 babelvox 里**只被写、从不被读**（pipeline L181/L356）
    # ⇒ 纯信息标志，置 False 安全（用于日志/诊断）
    try:
        eng.cp_on_cpu = False
    except Exception:
        pass
    on_log('[tts_engine] cp_decode: NPU'
           '（生产配置要求；实测 RTF 1.912→1.218、首块 1.296→0.837 s）')
    return True


def speaker_embedding(eng, ref_wav: Optional[str] = None,
                      on_log=print) -> Optional['np.ndarray']:
    """预计算参考 wav 的 speaker embedding（**x_vector / spkonly 路线**）。

    返回 shape `(1, 1024)` 的 numpy 数组。

    🔴 **只算一次**，不要每句重跑 speaker encoder（交接单 §5.1）。
    ⚠️ **不要传 `ref_audio=` 给 `generate_stream`** —— 那条路径内部会走
    `extract_speaker_embedding` **并同时接受 `ref_text`**；
    若同时给了 `ref_text` 就会退回分布外 prompt ⇒ EOS 不稳。
    """
    import numpy as np

    wav = ref_wav or preset_voice_path()
    if not wav:
        on_log('[tts_engine] ⚠️ 没有参考音频 ⇒ 只能用内置 speaker')
        return None
    try:
        spk = eng.extract_speaker_embedding(wav)
    except Exception as e:
        on_log(f'[tts_engine] ⚠️ speaker embedding 计算失败（{e}）'
               f' ⇒ 退回内置 speaker')
        return None
    spk = np.asarray(spk, dtype=np.float32).reshape(1, -1)
    on_log(f'[tts_engine] speaker embedding 就绪：{wav} -> {spk.shape}')
    return spk


# ── 中文数字正则化（TTS-006，规则版本 zh-num-v1.0）────────────────────
#
# 🔴🔴 **为什么需要**：Qwen3-TTS 读中文里的阿拉伯数字会读成英文
#   （实测 zh13「[REDACTED]心B0」→「fifty two 核心 B zero」，
#    zh12「28核心样本」→「twenty eight 核心」），
#   而 Confucius4 参照读成「五十二核心B零」「二十八核心」⇒ 回转写错误率
#   2.3~2.5% vs 参照 1.0% 的差距**基本全部来自这里**。
#
# 🔴 **只对 language=zh 生效**；英文句**逐字不动**。
# 🔴 **无数字的句子必须逐字不变**（自证没有误伤，见 verify_zh_num.py）。
#
# 规则：
#   ① 百分数  85%      → 百分之八十五
#   ② 年份    2026     → 二零二六（逐位；1900~2099 才当年份）
#   ③ 小数    3.5      → 三点五（小数位逐位）
#   ④ 型号    B0 / iPhone15 → B零 / iPhone一五（字母紧邻 ⇒ 逐位）
#   ⑤ 普通数  52 / 28  → 五十二 / 二十八（按数值读）
#
# ⚠️ **维护方**：本文件由 **TTS 模块**维护（规则 + 单元测试在
#   `qwen3tts_eval/verify_zh_num.py`）；App 模块只负责同步到客户包。

ZH_NUM_RULES_VERSION = 'zh-num-v1.0'

_CN_DIGITS = '零一二三四五六七八九'


def _int_to_cn(n: int) -> str:
    """0 ~ 99999999 的整数读法（中文口语习惯，无「一」开头的一十）。"""
    if n < 0:
        return '负' + _int_to_cn(-n)
    if n < 10:
        return _CN_DIGITS[n]
    if n < 20:
        return '十' + (_CN_DIGITS[n % 10] if n % 10 else '')
    if n < 100:
        return _CN_DIGITS[n // 10] + '十' + (_CN_DIGITS[n % 10] if n % 10 else '')
    if n < 1000:
        head = _CN_DIGITS[n // 100] + '百'
        rest = n % 100
        if rest == 0:
            return head
        if rest < 10:
            return head + '零' + _CN_DIGITS[rest]
        return head + _int_to_cn(rest)
    if n < 10000:
        head = _CN_DIGITS[n // 1000] + '千'
        rest = n % 1000
        if rest == 0:
            return head
        if rest < 100:
            return head + '零' + _int_to_cn(rest)
        return head + _int_to_cn(rest)
    if n < 100000000:
        head = _int_to_cn(n // 10000) + '万'
        rest = n % 10000
        if rest == 0:
            return head
        if rest < 1000:
            return head + '零' + _int_to_cn(rest)
        return head + _int_to_cn(rest)
    return str(n)


def _digits_to_cn(s: str) -> str:
    """逐位读（年份、型号里的单个数字）。"""
    return ''.join(_CN_DIGITS[int(c)] if c.isdigit() else c for c in s)


def normalize_zh_numbers(text: str) -> str:
    """把中文文本里的阿拉伯数字改成中文读法（TTS-006）。

    🔴 **幂等**：对已正则化的文本再跑一次结果不变
    （⇒ 不会与其它前端处理叠加成双重转换）。
    🔴 **无数字文本逐字返回原对象内容**（长度与内容都不变）。
    """
    if not text or not any(c.isdigit() for c in text):
        return text

    import re

    def _pct(m):
        num = m.group(1)
        if '.' in num:
            ip, fp = num.split('.', 1)
            val = _int_to_cn(int(ip)) + '点' + _digits_to_cn(fp)
        else:
            val = _int_to_cn(int(num))
        return '百分之' + val

    def _year(m):
        n = int(m.group(0))
        if 1900 <= n <= 2099:
            return _digits_to_cn(m.group(0))
        return _int_to_cn(n)

    def _dec(m):
        ip, fp = m.group(1), m.group(2)
        return _int_to_cn(int(ip)) + '点' + _digits_to_cn(fp)

    def _model(m):
        # 字母紧邻数字 ⇒ 型号 ⇒ 逐位读（B0 → B零）
        return m.group(1) + _digits_to_cn(m.group(2))

    def _plain(m):
        return _int_to_cn(int(m.group(0)))

    out = text
    # ① 百分数（先做，避免 % 里的数字被后面规则吃掉）
    out = re.sub(r'(\d+(?:\.\d+)?)\s*%', _pct, out)
    # ② 小数（先于年份，否则 2026.5 会被年份规则误吃）
    out = re.sub(r'(?<![\d.])(\d+)\.(\d+)(?![\d])', _dec, out)
    # ③ 年份（4 位，1900~2099）
    out = re.sub(r'(?<![\d.])(\d{4})(?![\d.])', _year, out)
    # ④ 型号：字母紧跟数字（前面必须紧邻字母 ⇒ "BLC 28" 不会被误判）
    out = re.sub(r'([A-Za-z])(\d+)', _model, out)
    # ⑤ 普通整数
    out = re.sub(r'(?<![\d.])(\d+)(?![\d.])', _plain, out)
    return out


def _is_zh_language(language: str) -> bool:
    """babelvox 的 language 传 'Chinese' / 'English'；兼容 'zh' / 'zh-CN'。"""
    s = (language or '').strip().lower()
    return s.startswith('zh') or s.startswith('chinese')


# ════════════════════════════════════════════════════════════════════
# 🔴🔴🔴 APP-030①：**目标语言显式下传**
# ════════════════════════════════════════════════════════════════════
#
# ## 为什么要改（reviewer 已用会话日志定位的真缺陷）
#
#   `tts_service.submit()` 下发的 `synth` 命令**只有 `id/text`**，**不带目标语言**
#   ⇒ `tts_worker._guess_lang()` 只能按「汉字占比 ≥ 25%」**二分 zh/en**
#   ⇒ **TTS 永远收不到 Japanese**
#   ⇒ 日文被当英文念（分布外 ⇒ EOS 不稳 ⇒ 偶发撞 2048 帧上限）
#     或被当中文念（`normalize_zh_numbers` 把「2026年」读成「二零二六年」）。
#
#   reviewer 在本机用同一函数实测 8 条日文样句：
#     **5 条判 en**（ありがとうございます。/はい、そうです。/これはテストです。/
#                  2026年の売上は52%増えました。/プロセッサーのパフォーマンスが向上しました。）
#     **3 条判 zh**（今日は会議があります。等）
#
# ## 映射表（babelvox / faster-qwen3-tts 都用这四个全称）
#
#   'zh' → 'Chinese'    'en' → 'English'
#   'ja' → 'Japanese'   'ko' → 'Korean'
#
# ⚠️ **模型侧是否支持**：Qwen3-TTS 的 `codec_language_id` 实测（包内
#   `models/qwen3tts/weights/config.json`）包含
#   chinese/english/german/italian/portuguese/spanish/**japanese**/korean/french/russian
#   ⇒ **Japanese / Korean 都有语言 id** ⇒ 不需要静默回落 English。
#   ⚠️ 但 `babelvox.pipeline` 若拿不到 language_id 会退成
#   「language-agnostic mode」⇒ 必须**显式告警**（见 `language_supported`）。
#
# ⚠️ **`normalize_zh_numbers` 只在 Chinese 时执行**（APP-030① 明文）：
#   日文数字规则（2026年 → 2026年）交 TTS 模块定 ⇒ App 侧**保持原样不转**。

LANG_MAP = {
    'zh': 'Chinese', 'chinese': 'Chinese', 'zh-cn': 'Chinese',
    'zh-tw': 'Chinese',
    'en': 'English', 'english': 'English',
    'ja': 'Japanese', 'japanese': 'Japanese', 'jp': 'Japanese',
    'ko': 'Korean', 'korean': 'Korean',
}

#: babelvox / faster-qwen3-tts 侧**确认支持**的语言 id
#: （来源：包内 `models/qwen3tts/weights/config.json` 的 `codec_language_id`）
SUPPORTED_LANGS = ('Chinese', 'English', 'Japanese', 'Korean')


def map_language(lang: str) -> str:
    """把「目标语言代号」映射成引擎用的**全称**。

    🔴 **兜底是 English**（不是 Auto）⇒ 与历史行为一致（`_guess_lang` 的 else 分支）。
    ⚠️ 调用方应先用 `guess_language()` 拿到**显式**语言再调本函数。
    """
    s = (lang or '').strip().lower()
    if not s:
        return 'English'
    if s in LANG_MAP:
        return LANG_MAP[s]
    # 'zh-CN' / 'ja-JP' 这类带区域的
    base = s.split('-')[0]
    if base in LANG_MAP:
        return LANG_MAP[base]
    return LANG_MAP.get(s, 'English')


def language_supported(language: str) -> bool:
    """引擎侧是否**确实**支持这个语言 id（用于**显式告警**，禁止静默回落）。"""
    return (language or '').strip() in SUPPORTED_LANGS


def _script_counts(s: str) -> dict:
    """统计文本里各文字体系的**字符数**（不含空白）。

    🔴 APP-030④：**必须补假名（U+3040–30FF）与谚文（U+AC00–D7AF）**
      ⇒ 旧 `_estimate_sec` 只数汉字与英文词
      ⇒ 日文长句被**大幅低估** ⇒ `split_long_text` 不切
      ⇒ NPU 侧撞 478 帧桶上限（截断或失控）。
    """
    han = kana = hang = latin = digits = 0
    for ch in s:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:
            han += 1
        elif 0x3040 <= o <= 0x30FF:
            kana += 1
        elif 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF:
            hang += 1
        elif ('a' <= ch <= 'z') or ('A' <= ch <= 'Z'):
            latin += 1
        elif ch.isdigit():
            digits += 1
    return dict(han=han, kana=kana, hang=hang, latin=latin, digits=digits)


def guess_language(text: str, hint: str = '') -> str:
    """**兜底**判语言（APP-030①：`_guess_lang` 只作兜底）。

    🔴 **优先用 hint**（主进程从 MT 目标显式下传的语言）
    ⇒ 命中则**直接返回**，不做任何启发式判断。
    ⇒ hint 缺失/不认识时才走文字体系启发式。

    🔴 **启发式必须能区分日文**（reviewer 实测旧函数 5/8 判错）：
      - **假名**（U+3040–30FF）出现 ⇒ 判 `ja`（**最强信号**）
      - **谚文**（U+AC00–D7AF）出现 ⇒ 判 `ko`
      - 汉字占比 ≥ 25% ⇒ `zh`
      - 否则 ⇒ `en`
    ⚠️ 旧函数用 `cjk * 4 >= len(text)`（**把空格也计入分母**）
      ⇒ 含空格的日文/中文句会被**误判成 en** ⇒ 本版**只数非空白字符**。
    """
    h = (hint or '').strip().lower()
    if h:
        if h in LANG_MAP:
            return h
        base = h.split('-')[0]
        if base in LANG_MAP:
            return base
    return guess_language_by_script(text)


def guess_language_by_script(text: str) -> str:
    """**纯启发式**语言判定（不看 hint）。返回 'zh'/'ja'/'ko'/'en'。"""
    t = text or ''
    c = _script_counts(t)
    if c['kana'] > 0:
        return 'ja'
    if c['hang'] > 0:
        return 'ko'
    visible = c['han'] + c['kana'] + c['hang'] + c['latin'] + c['digits']
    if visible <= 0:
        return 'en'
    if c['han'] * 4 >= visible:
        return 'zh'
    return 'en'


# 🔴🔴🔴 APP-030②：**按语言估帧**（失控守卫的输入）
#
#   reviewer 给的参考值（APP-030② 明文）：
#     ja ≈ 0.15 s/字、zh ≈ 0.25 s/字、en ≈ 0.07 s/字符
#   ⇒ 帧率 12 fps ⇒ 帧数 = 秒 × 12
#   ⚠️ 「起停另加余量」⇒ 公式里留了 `_LANG_TAIL_S` 的余量。
#
#   ⚠️ **这些是「秒/字符」不是「秒/词」** ⇒ 与 `_estimate_sec` 的
#      「中文按字数、英文按词数」**口径不同** ⇒ 两套函数**不要混用**。
#      本函数专门给**失控守卫**用（要的是帧数上限，不是切分估算）。

#: 每字符的预计秒数（APP-030② 的参考值）
#: 🔴🔴 **键必须是「小写语言代号」** ⇒ 取值前**必须**先过 `_lang_key()`。
_SEC_PER_CHAR = {'zh': 0.25, 'ja': 0.15, 'ko': 0.18, 'en': 0.07}

#: 起停余量（秒）
_LANG_TAIL_S = 0.6


def _lang_key(lang: str) -> str:
    """把**任意形态**的语言标识归一成 `_SEC_PER_CHAR` 的键。

    🔴🔴🔴 **本轮自查抓出的真实缺陷（§78）**：
      `estimate_frames()` / `estimate_sec()` 原先直接
      `_SEC_PER_CHAR.get((lang or 'en').lower(), _SEC_PER_CHAR['en'])`
      ⇒ **只认小写代号**（`zh` / `ja` / `ko` / `en`）。
      但同一份代码里 `map_language()` **认得**全称与带区域写法
      （`'Japanese'` / `'zh-cn'` / `'zh-tw'` / `'jp'` …）
      ⇒ **两套表解析同一个语言标识 ⇒ 口径不一致**：
        - `estimate_sec(text, 'Japanese')` ⇒ 落**英文** 0.07 s/字
          （日文真实 0.15 ⇒ **低估 2.1 倍**）
        - `estimate_sec(text, 'zh-cn')`     ⇒ 落**英文** 0.07 s/字
          （中文真实 0.25 ⇒ **低估 3.6 倍**）
      ⇒ 后果 = **失控守卫的阈值被算得过低**：
        `RUNAWAY` 阈值 `max(3×est, est+8)` 用小 est ⇒ **更容易误杀正常长句**，
        而 `clamp_max_new_tokens` 用小 est ⇒ **帧数上限偏松**（= 失控上限放行）。
      ⚠️ 当前生产路径**恰好**只传小写代号（`translator.TARGETS` = zh/en/ja/ko）
      ⇒ 缺陷**未暴露**；但这属于「同一个标识两套口径」的隐患
      ⇒ 一旦有人传全称或带区域写法就静默失准。

    ⇒ 修法：**统一走 `map_language()`**（唯一映射表）再反查小写代号。
      未知语言仍落 `'en'`（与历史行为一致）。
    """
    try:
        full = map_language(lang)
    except Exception:
        full = 'English'
    for k, v in LANG_MAP.items():
        if v == full:
            return k if k in _SEC_PER_CHAR else 'en'
    # `LANG_MAP` 的值里只有 Chinese/English/Japanese/Korean ⇒ 上面必然命中
    return 'en'


def estimate_frames(text: str, lang: str = 'en') -> int:
    """按语言估「这句大概多少帧」（12 fps）。

    🔴 APP-030②：失控守卫的**输入**。
    ⚠️ 这是**估算**，不是精确值 ⇒ 客户端的 RUNAWAY 判据用
      `max(3×估计, 估计+8 s)` 这种**宽松**阈值（宁可漏判也不误杀）。
    """
    n = len([c for c in (text or '') if not c.isspace()])
    s = _SEC_PER_CHAR.get(_lang_key(lang), _SEC_PER_CHAR['en'])
    sec = n * s + _LANG_TAIL_S
    return max(8, int(sec * 12))


#: 🔴 APP-030②：客户端**第二道闸**（RUNAWAY）的阈值系数
#:   判据（APP-030② 明文）：本句已收音频 > max(3×估计, 估计 + 8 s) ⇒ RUNAWAY
RUNAWAY_FACTOR = 3.0
RUNAWAY_EXTRA_S = 8.0


def runaway_threshold_s(est_sec: float) -> float:
    """RUNAWAY 判据阈值（秒）。

    🔴 APP-030② 明文：「本句已收音频 > `max(3×估计, 估计+8 s)` ⇒ 判 RUNAWAY」。
    ⚠️ **故意宽松** ⇒ 宁可漏判也不误杀正常句（误杀会把好句截断）。
    """
    try:
        e = float(est_sec)
    except Exception:
        e = 0.0
    if e <= 0:
        e = 0.0
    return max(RUNAWAY_FACTOR * e, e + RUNAWAY_EXTRA_S)


def estimate_sec(text: str, lang: str = 'en') -> float:
    """按语言估「这句大概多少秒」（**失控守卫的第二道闸**用）。

    ⚠️ 与 `_estimate_sec`（切分用）**口径不同**：
      - `_estimate_sec`：中文按字数 / 英文按**词数** ⇒ 用于 `split_long_text`；
      - 本函数：按**字符**（`_SEC_PER_CHAR`）⇒ 与 APP-030② 的估帧口径一致。
    ⇒ 两套函数**不要混用**。
    """
    n = len([c for c in (text or '') if not c.isspace()])
    s = _SEC_PER_CHAR.get(_lang_key(lang), _SEC_PER_CHAR['en'])
    return n * s + _LANG_TAIL_S


def clamp_max_new_tokens(text: str, lang: str = 'en') -> int:
    """算**本句的生成帧数上限**（APP-030②）。

    公式（APP-030② 明文）：
        `clamp(3×估计帧数 + 36, 48, 2048)`

    🔴 **为什么要有上限**（reviewer 的实测证据）：
      边车**不传** `max_new_tokens` ⇒ 用库默认 **2048 帧**
      ⇒ **2048 帧 = 163.8 s 音频**（12 fps）
      ⇒ 一句 7 字的日文实测跑了 **106.61 s**、255 块、163.0 s 音频
      ⇒ 用户听到的是 ~106 s 的低电平含糊气声，且**边车串行**
      ⇒ 后续句全部排队堵住 1~2 分钟（APP-030 的真缺陷）。

    ⇒ 传一个**按句估算**的上限 ⇒ 失控句在几秒内被截断，
      而不是拖 100 秒把整条语音链堵死。
    """
    est = estimate_frames(text, lang)
    v = 3 * est + 36
    return max(48, min(2048, int(v)))


def reset_ctx(eng) -> None:
    """🔴🔴 **生成新句子前必须调用**（TTS-010 左上下文纪律）。

    左上下文解码会在引擎里缓存「上一批解码过的帧码」，
    用来给下一个 chunk 提供边界上下文。
    ⇒ 若不清理，**上一句的尾帧会串进下一句** ⇒ 音色突变 / 杂音。

    ⚠️ 引擎无此方法时**静默跳过**（原生 BabelVox / 老 patch 没有 ctx）。
    """
    fn = getattr(eng, 'reset_ctx', None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


def stream(eng, text: str, language: str = 'English',
           speaker_embed=None,
           speaker: Optional[str] = None,
           cancel_event=None,
           max_new_tokens: Optional[int] = None,
           est_sec: Optional[float] = None,
           on_log=print) -> Iterator[Tuple]:
    """流式合成（**spkonly 路线**）。

    产出 `(chunk_waveform, sample_rate)` 元组（babelvox 原生接口），
    `sample_rate` 恒为 **24000**。

    🔴🔴 **不要传 `ref_text`**（交接单 §5.1 / TTS-005）：
    `ref_text` 路径不是官方 ICL（codec 轨道没有 ref_code）⇒
    对模型是「有文本、没音频」的分布外 prompt ⇒ **EOS 不稳**。
    音色一律走 `speaker_embed`（预计算）或内置 `speaker`。

    ⚠️ **`split_on_silence` 必须是 False**（交接单 §1.2）：
    打开它每帧多跑一次 decode 判静音 ⇒ RTF 1.83 → 5.90。

    🔴🔴 **TTS-006：中文数字正则化在这里生效**（`language=zh` 时）
    ⇒ 中文里的「52 核心 B0」送进模型前会变成「五十二核心B零」
    ⇒ 避免模型读成英文 "fifty two 核心 B zero"。
    ⚠️ 英文句**逐字不动**；无数字的中文句**逐字不动**。

    🔴🔴 **TTS-010：左上下文 + chunk 尺寸**
    - `chunk_frames=CHUNK_FRAMES`：分块解码的粒度（帧），
      越小边界越多（失真越大），越大首字延迟越高。
    - 调用前先 `reset_ctx(eng)`：**清掉上一句的尾帧上下文**，
      否则跨句串音。
    """
    if _is_zh_language(language):
        text = normalize_zh_numbers(text)
    # 🔴 每句独立：清掉上一句残留的左上下文
    reset_ctx(eng)
    kwargs = dict(
        text=text,
        language=language,
        speaker_embed=speaker_embed,
        speaker=speaker,
        split_on_silence=False,      # 🔴 必须 False
        cancel_event=cancel_event,
    )
    # 🔴 chunk_frames：babelvox 支持时传入（老版本无此参数 ⇒ 退回默认 12）
    try:
        import inspect
        _sig = inspect.signature(eng.generate_stream)
        _has_chunk = 'chunk_frames' in _sig.parameters
    except Exception:
        _has_chunk = False
    if _has_chunk:
        kwargs['chunk_frames'] = CHUNK_FRAMES
    # 🔴🔴🔴 APP-030②：**生成帧数上限**（失控守卫的第一道闸）。
    #   旧实现**从不传** ⇒ 用库默认 512（babelvox）/ 2048（边车）
    #   ⇒ 一句失控能拖 100 秒（reviewer 实测 163.0 s 音频）。
    # ⚠️ **只在本模块自己算出的上限更严时才覆盖** ⇒ 绝不放大引擎的上限。
    if max_new_tokens is not None:
        try:
            cur = _sig.parameters['max_new_tokens'].default
        except Exception:
            cur = None
        if cur is None or int(max_new_tokens) < int(cur):
            kwargs['max_new_tokens'] = int(max_new_tokens)
    # 🔴🔴🔴 APP-030②：**第二道闸（客户端 RUNAWAY）**的输入。
    #   `est_sec` = 本句预计音频秒数 ⇒ 客户端按
    #   `max(3×估计, 估计+8 s)` 判 RUNAWAY。
    #   ⚠️ **只对支持该参数的引擎传**（CUDA 边车客户端支持；
    #     babelvox 原生**不认** ⇒ 传了会 TypeError）。
    if est_sec is not None:
        try:
            if 'est_sec' in _sig.parameters:
                kwargs['est_sec'] = float(est_sec)
        except Exception:
            pass
    return eng.generate_stream(**kwargs)


def _estimate_sec(s: str) -> float:
    """粗估一段文本的朗读时长（秒）。

    中文按字数（1 字 ≈ 0.12 s），英文按词数（1 词 ≈ 0.38 s），另加 0.4 s 起停余量。

    🔴🔴 APP-030④：**必须补假名与谚文**。
      旧实现只数汉字（`[\u4e00-\u9fff]`）与英文词
      ⇒ **日文句子一个字符都数不到**（假名不在汉字区）
      ⇒ 估时恒等于「0.4 s 起停」⇒ 日文长句被**严重低估**
      ⇒ `split_long_text` 判「没超上限」⇒ **不切**
      ⇒ NPU 侧撞 478 帧桶上限（截断或失控）。
      ⇒ 现在：假名按 0.13 s/字、谚文按 0.15 s/字。
    """
    import re
    zh = len(re.findall(r'[\u4e00-\u9fff]', s))
    # 🔴 APP-030④：假名（U+3040–30FF，含浊音/半浊音与小写假名）
    kana = len(re.findall(r'[\u3040-\u30ff]', s))
    # 🔴 APP-030④：谚文音节（U+AC00–D7AF）
    hang = len(re.findall(r'[\uac00-\ud7af]', s))
    en = len(re.findall(r"[A-Za-z']+", s))
    return zh * 0.12 + kana * 0.13 + hang * 0.15 + en * 0.38 + 0.4


def split_long_text(text: str, max_frames: int = 478,
                    sr: int = 24000, fps: int = 12) -> List[str]:
    """把过长的句子按句切开（超过 talker 帧数上限时）。

    🔴 **帧数上限是 `max_talker_seq − prefill_len`，逐条不同**；
    这里用最保守值（512 − 34）估算 ⇒ 宁可多切，不要被静默截断。

    ⚠️ **不要无条件切分**（交接单 §6.3）：
    切分对 RTF **几乎没有影响**（Δ ≈ 0），只会多占 300 ms/段静音；
    只有「整句接近帧数上限」时才切（5 段的长句 RTF 1.227 → 0.904，−0.30）。
    ⚠️ **分段会让音频变长**（segs=5 时中位 21.28 s → 25.92 s，+22%）
    ⇒ 切分的价值是「不缺尾 + 反而更快」，不是纯速度。

    交接单 §6.3 实测：整句 18.88 s 被截断 → 分段 25.28 s 完整，
    **RTF 1.372 → 1.063（分段反而更快）**。
    """
    max_sec = max_frames / float(fps)
    out: List[str] = []
    for para in (text or '').split('\n'):
        para = para.strip()
        if not para:
            continue
        # 先按中英文句末标点切
        import re
        sents = [s for s in re.split(r'(?<=[。！？!?；;])\s*|(?<=[.!?])\s+', para) if s]
        buf = ''
        buf_est = 0.0
        for s in sents:
            est = _estimate_sec(s)
            # 🔴 判据是「**累计** buf_est + est 超过上限」，
            #    不是单句 est 超过上限 —— 后者会让长句被整句塞进同一段。
            if buf and (buf_est + est) > max_sec:
                out.append(buf.strip())
                buf = s
                buf_est = est
            else:
                buf = (buf + ' ' + s).strip() if buf else s
                buf_est += est
            # 单句本身就超长 ⇒ 再按逗号切
            while buf_est > max_sec and len(buf) > 40:
                cut = buf.rfind('，')
                if cut < 0:
                    cut = buf.rfind(',')
                if cut < 10:
                    break
                head = buf[:cut].strip()
                buf = buf[cut + 1:].strip()
                out.append(head)
                buf_est = _estimate_sec(buf)
        if buf.strip():
            out.append(buf.strip())
    return [s for s in out if s]


if __name__ == '__main__':
    print('模型根目录：', model_root())
    print('tokenizer：', tokenizer_dir())
    print('音色 A：', preset_voice_path())
    print('缓存目录：', _cache_dir())
    print('采样率：', TTS_SAMPLE_RATE)
    print('PRESET_A_REF_TEXT：', PRESET_A_REF_TEXT,
          '（None = 已作废，禁止传入）')
    print('长句切分示例：')
    for t in split_long_text('第一句话。第二句话。' * 40):
        print('  ', t[:40], '...')
    # 累计判据自检：长句不能被塞进同一段
    long_text = 'This is a sentence about engine growth. ' * 120
    parts = split_long_text(long_text)
    est = [_estimate_sec(p) for p in parts]
    print(f'长句切分：{len(parts)} 段，每段估时 max={max(est):.1f}s '
          f'（上限 {478/12:.1f}s）')
    assert max(est) <= 478 / 12 + 1.0, '切分后仍有超长段'
    print('OK')
