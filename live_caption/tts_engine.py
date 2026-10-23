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

import os
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
BUILTIN_SPEAKERS = ('cindy', 'lou', 'phil', 'steve')

# 🔴 BabelVox 输出采样率（babelvox `generate` / `generate_stream` 返回 24000）
TTS_SAMPLE_RATE = 24000

# ── 引擎参数（交接单 §1.1）────────────────────────────────────────────
TALKER_BUCKETS = [64, 128, 256, 384, 512]
DECODER_BUCKETS = [8, 16, 32, 64, 128, 256]
MAX_DECODER_FRAMES = 512          # 🔴 保持 512 —— 一参两用，降了会砍断长句
MAX_TALKER_SEQ = 512


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


def make_engine(device: str = 'NPU',
                model_path: Optional[str] = None,
                cache_dir: Optional[str] = None,
                on_log=print):
    """创建 BabelVox 引擎实例。

    返回的对象有 `.generate_stream(text, language=..., ref_audio=..., ...)`
    与 `.generate(...)`，与 TTS 交接单一致。

    ⚠️ `device='NPU'` 时会用 `MultiDecoderBabelVox`（多桶解码器），
    没有 patch 文件时退回原生 `BabelVox`（功能可用，但长句解码慢）。
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

    cdir = cache_dir or _cache_dir()
    kwargs = dict(
        export_dir=root,
        model_path=tok,
        device=device,
        precision='int8',
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
        kwargs['decoder_buckets'] = DECODER_BUCKETS
        on_log('[tts_engine] 使用 MultiDecoderBabelVox（解码器多桶）')
    else:
        on_log('[tts_engine] ⚠️ 未找到 tts_engine_patch.py，'
               '退回原生 BabelVox（长句解码较慢）')

    on_log(f'[tts_engine] 加载模型：device={device} root={root} cache={cdir}')
    t0 = os.times()
    try:
        eng = cls(**kwargs)
    except Exception as e:
        raise TTSEngineError(f'模型加载失败：{type(e).__name__}: {e}') from e
    on_log('[tts_engine] 模型加载完成')

    # 🔴🔴 **必须挂 SpeakerLibrary**，否则按名查内置音色会直接抛
    #   `ValueError: speaker_library not set; cannot look up named speaker`
    #   （babelvox/pipeline.py:782 —— `speaker_library` 默认是 None）。
    # 内置音色 cindy/lou/phil/steve **不是引擎内置常量**，而是随包文件
    # `babelvox/data/speakers/{name}.json` + `{name}.npy`（embedding 1×1024）；
    # `SpeakerLibrary(dir, copy_builtins=True)` 会把它们复制到库目录。
    # ⇒ 只建 `SpeakerLibrary` 而不设 `eng.speaker_library` 是无效的。
    _attach_speaker_library(eng, on_log=on_log)
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


def stream(eng, text: str, language: str = 'English',
           speaker_embed=None,
           speaker: Optional[str] = None,
           cancel_event=None,
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
    """
    kwargs = dict(
        text=text,
        language=language,
        speaker_embed=speaker_embed,
        speaker=speaker,
        split_on_silence=False,      # 🔴 必须 False
        cancel_event=cancel_event,
    )
    return eng.generate_stream(**kwargs)


def _estimate_sec(s: str) -> float:
    """粗估一段文本的朗读时长（秒）。

    中文按字数（1 字 ≈ 0.12 s），英文按词数（1 词 ≈ 0.38 s），另加 0.4 s 起停余量。
    """
    import re
    zh = len(re.findall(r'[\u4e00-\u9fff]', s))
    en = len(re.findall(r"[A-Za-z']+", s))
    return zh * 0.12 + en * 0.38 + 0.4


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
