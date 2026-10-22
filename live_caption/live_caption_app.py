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
import audio_source
from audio_source import (BLOCK_MS, SR, default_output_device_id,
                          list_input_devices, list_output_devices, make_source,
                          resample_to_16k, soundcard_available)

CHUNK_SEC = 0.64
MIN_SEG_SEC = 12.0
MAX_SEG_SEC = 20.0
SIL_LOOKBACK_SEC = 3.0

# 静音超时切段（解决「说完话迟迟不定稿」/ cut on silence timeout）
# 段尾连续静音多久就切段定稿。
SILENCE_CUT_SEC = float(os.environ.get('LIVECAP_SILENCE_CUT_SEC', '1.2'))
# 保护期：段尾这么多秒内的静音不算「说话结束」（开头爆破音会被误判）。
SILENCE_TAIL_GUARD_SEC = float(os.environ.get('LIVECAP_SILENCE_GUARD_SEC', '0.35'))
# 静音判定阈值（dBFS），与 seg_stream.find_silence_in_range 的默认值一致。
SILENCE_DB = -40.0

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
# 不用开发机路径；开发机上会沿用已有的缓存目录以省编译时间。
def _cache(name):
    """编译缓存目录。优先复用开发机已有缓存，其次用包内目录。"""
    shared = os.path.join(
        os.path.expanduser('~'), '.openvino', 'models',
        'reports' if name == 'npu_cache' else '', name)
    return shared if os.path.isdir(shared) else os.path.join(APP_DIR, name)


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


# ── ASR 识别语种（用户可选）──────────────────────────────────────────
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



def _norm_word(w):
    return str(w).strip('.,!?;:，。！？；：').lower()


class Segmenter:
    """在线切段规则（只看已累计的音频）。

    两条规则，**任一**满足就切段：

    1. **常规规则**（原 mic_asr_app 的做法）：段长 ≥ ``MIN_SEG_SEC``(12 s)
       且最近 ``SIL_LOOKBACK_SEC``(3 s) 内有 ≥300 ms 静音；段长 ≥
       ``MAX_SEG_SEC``(20 s) 硬切。

    2. **静音超时规则**（新增，解决「说完话迟迟不定稿」）：
       段尾检测到连续 ≥ ``SILENCE_CUT_SEC``(1.2 s) 的静音就立即切段，
       不管段长够不够 12 秒。

    为什么需要第 2 条：原规则只在段长 ≥12 s 后才去看静音。短语音
    （会议里一句「好的」大约 1–3 秒）说完后，用户要干等到累积满 12 秒
    才能看到定稿（实测 3 秒语音等 5.8 秒、5 秒语音等 5.2 秒），
    字幕不转白、译文也跟着卡住。

    第 2 条不会损失识别质量：切段点落在静音区，音频内容已经解码完，
    提前收尾得到的文本与等满 12 秒的结果一致（实测逐字相同）。

    为什么要 ``SILENCE_TAIL_GUARD_SEC`` 保护：刚开口的第一个音节
    （如爆破音 /b/、/p/）本身能量低，可能被误判成静音。保护期内的
    静音不足以切段，避免把第一个字切到下一段。
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
        # 规则 2：静音超时（优先判定，短段靠它出定稿）
        if self._silence_tail(acc):
            return True
        # 规则 1：常规规则
        if dur < MIN_SEG_SEC:
            return False
        start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
        return self._find(acc, start_sample=start, end_sample=n,
                          silence_db=-40.0, min_silence_ms=300) is not None

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
        """
        n = acc.shape[0]
        if n < int(SR * 0.5):
            return False                       # 太短，噪声而已
        # 窗口要比判定阈值再宽一点，保证「末尾静音」完整落在窗口里
        win = int(SR * (SILENCE_CUT_SEC + SILENCE_TAIL_GUARD_SEC + 0.5))
        start = max(0, n - win)
        span = self._trail(acc, start_sample=start, end_sample=n,
                           silence_db=SILENCE_DB,
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
        return db > SILENCE_DB


def stitch(prev_words, text):
    """段接缝去重：下一段开头 2–3 词与上一段末尾完全相同时删掉。"""
    if not prev_words or not text:
        return text
    words = text.split()
    nw = [_norm_word(w) for w in words]
    prev = [_norm_word(w) for w in prev_words]
    for n in (3, 2):
        if len(nw) >= n and len(prev) >= n and prev[-n:] == nw[:n]:
            rest = words[n:]
            return ' '.join(rest) if rest else text
    return text


# ── OpenVINO 引擎（Intel GPU / NPU）────────────────────────────────────
class OVEngine:
    """把 streaming_transcribe 包装成增量引擎（逻辑同 mic_asr_app.StreamingEngine）。"""

    def __init__(self, key, on_log=print, force_language=None):
        from seg_stream import _make_segment_state
        from streaming_asr import (streaming_transcribe, finish_streaming_transcribe,
                                   parse_asr_output, _normalize_punct_by_context)
        self.key, self.cfg = key, ENGINES[key]
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
        final = stitch(self._last_words, self._finalize())
        if final.split():
            self._last_words = final.split()[-3:]
        self.stats['segs'] += 1
        self.reset()
        self.state.buffer = carry
        return final

    def flush(self):
        st = self.state
        if st.audio_accum.shape[0] == 0 and st.buffer.shape[0] == 0:
            return None
        final = stitch(self._last_words, self._finish(self.backend, st, max_new_tokens=64))
        self.stats['segs'] += 1
        self.reset()
        self._last_words = []
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
            text = stitch(self._last_words, p.final if p.final is not None else p.partial)
            if text.split():
                self._last_words = text.split()[-3:]
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


def make_engine(key, on_log=print, force_language=None):
    """创建推理引擎。

    force_language：ASR 识别语种（模型认识的英文名，如 'Chinese'/'English'）；
    None = 自动检测。传进来后会在建 state / 起进程时生效。
    """
    cls = CudaEngine if ENGINES[key]['kind'] == 'cuda' else OVEngine
    return cls(key, on_log=on_log, force_language=force_language)


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
    """屏幕底部的置顶半透明字幕条（可拖动）：
    第一行最近定稿（白），第二行正在识别（黄），第三行译文（青），
    第四行草稿译文预览（浅蓝，仅在勾选「草稿译文」且有预览时出现）。"""

    def __init__(self, root, font_size=26):
        import tkinter as tk
        import tkinter.font as tkfont
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
        # 4 行：定稿 / 实时 / 译文 / 草稿预览
        h = 4 * line + 34
        self.win.geometry(f'{self.w}x{h}+{(sw - self.w) // 2}+{sh - h - int(sh * 0.07)}')
        self.win.configure(bg='#111111')
        self.final = tk.Label(self.win, text='', fg='#f2f2f2', bg='#111111',
                              font=self.font, anchor='w')
        self.partial = tk.Label(self.win, text='', fg='#ffd75e', bg='#111111',
                                font=self.font, anchor='w')
        self.mt = tk.Label(self.win, text='', fg='#5fd7d7', bg='#111111',
                           font=self.font, anchor='w')
        self.draft = tk.Label(self.win, text='', fg='#7aa7d0', bg='#111111',
                              font=self.font, anchor='w')
        self.final.pack(fill='x', padx=20, pady=(10, 0))
        self.partial.pack(fill='x', padx=20)
        self.mt.pack(fill='x', padx=20)
        self.draft.pack(fill='x', padx=20)
        for wdg in (self.win, self.final, self.partial, self.mt):
            wdg.bind('<ButtonPress-1>', self._press)
            wdg.bind('<B1-Motion>', self._drag)

    def _press(self, e):
        self._dx, self._dy = e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y()

    def _drag(self, e):
        self.win.geometry(f'+{e.x_root - self._dx}+{e.y_root - self._dy}')

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

    def show(self, final_tail, partial, mt='', draft=''):
        self.final.configure(text=self._tail_fit(final_tail[-400:]))
        self.partial.configure(text=self._tail_fit(partial[-400:]))
        self.mt.configure(text=self._tail_fit(mt[-400:]) if mt else '')
        # 草稿预览单独一行 —— 不与定稿译文挤在同一行，否则定稿译文一出现
        # 就会把草稿预览顶掉（草稿开关等于白开）。
        self.draft.configure(text=self._tail_fit(draft[-400:]) if draft else '')

    def destroy(self):
        self.win.destroy()


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
        self.mt = TranslationService(
            target=args.translate, device=args.mt_device, auto=False,
            engine_key=args.mt_engine, use_ctx=getattr(args, 'mt_ctx', False),
            glossary=getattr(args, 'mt_glossary', False),
            draft=_init_draft_flag(args),
            on_log=self._ui_log)

        root.title('Confucius4-R2T2 实时字幕 · 多后端测试')
        root.geometry('1080x700')

        top = ttk.Frame(root, padding=(10, 8))
        top.pack(fill='x')
        ttk.Label(top, text='推理后端').pack(side='left')
        self.keys = list(ENGINES)
        self.var_engine = tk.StringVar(value=ENGINES[args.engine]['label'])
        self.cb_engine = ttk.Combobox(top, state='readonly', width=26,
                                      values=[ENGINES[k]['label'] for k in self.keys],
                                      textvariable=self.var_engine)
        self.cb_engine.pack(side='left', padx=(4, 12))
        self.cb_engine.bind('<<ComboboxSelected>>', lambda e: self.load_engine())

        ttk.Label(top, text='翻译').pack(side='left')
        self.mt_keys = list(TARGETS)
        self.var_mt = tk.StringVar(value=TARGET_LABELS[args.translate])
        self.cb_mt = ttk.Combobox(top, state='readonly', width=8,
                                  values=[TARGET_LABELS[k] for k in self.mt_keys],
                                  textvariable=self.var_mt)
        self.cb_mt.pack(side='left', padx=(4, 12))
        self.cb_mt.bind('<<ComboboxSelected>>', self._on_mt_changed)

        self.btn = ttk.Button(top, text='▶ 开始', command=self.toggle, state='disabled')
        self.btn.pack(side='left')
        ttk.Button(top, text='清空', command=self.clear).pack(side='left', padx=4)
        ttk.Button(top, text='保存', command=self.save).pack(side='left')
        self.var_overlay = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text='屏幕字幕', variable=self.var_overlay,
                        command=self._toggle_overlay).pack(side='left', padx=10)

        self.var_note = tk.StringVar(value='')
        ttk.Label(root, textvariable=self.var_note, foreground='#555',
                  padding=(12, 0)).pack(fill='x')

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
        # support_languages 里的英文名。这个下拉放在「音频来源」右边，
        # 因为语种是识别行为、跟采集方式无关，但顶栏已经很挤了。
        ttk.Label(srow, text='识别语种').pack(side='left')
        self._asr_lang_keys = [ASR_LANG_AUTO] + list(ASR_LANGS)
        self._asr_lang_label = {k: asr_lang_label(k) for k in self._asr_lang_keys}
        self._asr_lang_label_back = {v: k for k, v in self._asr_lang_label.items()}
        init_lang = getattr(args, 'asr_lang', ASR_LANG_AUTO) or ASR_LANG_AUTO
        if init_lang not in self._asr_lang_keys:
            init_lang = ASR_LANG_AUTO
        self.var_asr_lang = tk.StringVar(value=self._asr_lang_label[init_lang])
        self.cb_asr_lang = ttk.Combobox(srow, state='readonly', width=12,
                                        textvariable=self.var_asr_lang,
                                        values=[self._asr_lang_label[k]
                                                for k in self._asr_lang_keys])
        self.cb_asr_lang.pack(side='left', padx=(4, 12))
        self.cb_asr_lang.bind('<<ComboboxSelected>>', self._on_asr_lang_changed)

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

        # 翻译后端（设备 × 量化）单独一行：顶栏放不下，且与 ASR 后端独立可选。
        mrow = ttk.Frame(root, padding=(12, 4))
        mrow.pack(fill='x')
        ttk.Label(mrow, text='翻译后端').pack(side='left')
        self.mt_eng_keys = [k for k in MT_ENGINES]
        self._mt_eng_label = {k: MT_ENGINES[k]['label'] for k in self.mt_eng_keys}
        self._mt_eng_label_back = {v: k for k, v in self._mt_eng_label.items()}
        self.var_mt_eng = tk.StringVar(value=self._mt_eng_label[args.mt_engine])
        self.cb_mt_eng = ttk.Combobox(
            mrow, state='readonly', width=26, textvariable=self.var_mt_eng,
            values=[self._mt_eng_label[k] for k in self.mt_eng_keys])
        self.cb_mt_eng.pack(side='left', padx=(4, 12))
        self.cb_mt_eng.bind('<<ComboboxSelected>>', self._on_mt_engine_changed)
        self.var_mt_note = tk.StringVar(value='')
        ttk.Label(mrow, textvariable=self.var_mt_note, foreground='#555').pack(side='left')
        # 重试按钮：翻译模型加载失败时（状态栏显示「失败」）一键重试，
        # 不用重启整个程序。加载中时禁用。
        self.btn_mt_retry = ttk.Button(mrow, text='↻ 重试翻译 Retry', width=16,
                                       command=self._retry_mt, state='disabled')
        self.btn_mt_retry.pack(side='left', padx=(8, 0))
        # 草稿译文开关：默认**关闭**，只翻已经定稿的文本。勾上后还会实时翻译
        # 还没定稿的那句（浅蓝色显示），但会占翻译算力、抬高 ASR 积压。
        self.var_mt_draft = tk.BooleanVar(value=_init_draft_flag(args))
        self.chk_mt_draft = ttk.Checkbutton(
            mrow, text='草稿译文 Draft', variable=self.var_mt_draft,
            command=self._on_mt_draft_toggled)
        self.chk_mt_draft.pack(side='left', padx=(12, 0))
        self.mt.set_draft(self.var_mt_draft.get())
        self._mark_missing_mt_engines()
        self._set_mt_note(args.mt_engine)

        self.txt = scrolledtext.ScrolledText(root, wrap='word', font=('Microsoft YaHei UI', 13),
                                             relief='flat', padx=12, pady=10, spacing3=6)
        self.txt.pack(fill='both', expand=True, padx=10, pady=(4, 4))
        self.txt.tag_config('partial', foreground='#9a9a9a')
        self.txt.tag_config('mt', foreground='#1565c0')            # 定稿译文
        self.txt.tag_config('mt_partial', foreground='#7aa7d0')    # 实时译文草稿
        self.txt.configure(state='disabled')

        bot = ttk.Frame(root, padding=(10, 4))
        bot.pack(fill='x')
        self.var_meter = tk.StringVar(value='')
        self.lbl_meter = ttk.Label(bot, textvariable=self.var_meter, font=('Consolas', 10))
        self.lbl_meter.pack(side='left')
        self.var_status = tk.StringVar(value='')
        ttk.Label(bot, textvariable=self.var_status, foreground='#555').pack(side='right')

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
        key = self.keys[[ENGINES[k]['label'] for k in self.keys].index(self.var_engine.get())]
        if self._loading or key == self.engine_key:
            return
        self.stop()
        self._loading = True
        self.btn.configure(state='disabled')
        self.cb_engine.configure(state='disabled')
        self.var_note.set(ENGINES[key]['note'])
        old = [self.engine]
        self.engine, self.engine_key = None, None

        def work():
            try:
                if old[0]:
                    old[0].close()            # 先释放旧引擎的显存/内存，再加载新的
                    old[0] = None
                    gc.collect()
                # 语种在引擎创建时就定下来（要进 prompt / 进程启动参数），
                # 所以这里传 GUI 上的实时选择，不是 args 的启动快照。
                eng = make_engine(key, on_log=self._ui_log,
                                  force_language=self._cur_asr_lang())
                self.root.after(0, self._engine_ready, key, eng)
            except Exception as e:
                msg = f'{type(e).__name__}: {e}'
                self.root.after(0, self._engine_failed, msg)

        threading.Thread(target=work, daemon=True).start()

    def _engine_ready(self, key, eng):
        self.engine, self.engine_key, self._loading = eng, key, False
        self.cb_engine.configure(state='readonly')
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
        self.cb_engine.configure(state='readonly')
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

    # -- 翻译后端（设备 × 量化）-------------------------------------------
    def _mark_missing_mt_engines(self):
        """模型目录不在本机的项，标签后面加「（缺模型）」提示。"""
        for k in self.mt_eng_keys:
            if not mt_available(k):
                self._mt_eng_label[k] += '（缺模型）'
                self._mt_eng_label_back[self._mt_eng_label[k]] = k
        self.cb_mt_eng.configure(values=[self._mt_eng_label[k] for k in self.mt_eng_keys])

    def _cur_mt_engine_key(self):
        return self._mt_eng_label_back.get(self.var_mt_eng.get(), self.mt.engine_key)

    def _set_mt_note(self, key):
        cfg = MT_ENGINES.get(key)
        self.var_mt_note.set((cfg or {}).get('note', ''))

    def _on_mt_engine_changed(self, *_a):
        key = self._cur_mt_engine_key()
        self._set_mt_note(key)
        if not self.mt.set_engine(key):
            return
        if not self.mt.active:
            self.var_status.set(f'翻译后端：{MT_ENGINES[key]["label"]}（翻译关闭中，切换将在开启翻译时生效）')
            return
        self.cb_mt_eng.configure(state='disabled')
        self.var_status.set(f'翻译后端切换中：{MT_ENGINES[key]["label"]} · {self.mt.device}')
        self.root.after(300, lambda: self.cb_mt_eng.configure(state='readonly'))

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

    def _mt_of(self, seg):
        """定稿段的译文（按段序号查；半句并入下一段的，本段译文会少那一截）。"""
        return self.mt.mt_of_seg(seg)

    def _on_final(self, text):
        self.final_text += text + '\n'
        self.blocks.append(text)
        self.mt.submit(text, seg=len(self.blocks) - 1)

    def clear(self):
        self.final_text = ''
        self.blocks = []
        self.mt.seg_keys.clear()
        self.mt.seg_carry.clear()
        self._render('')

    def _save_text(self):
        """原文 + 译文（保存/自测共用）。"""
        out = []
        for i, src in enumerate(self.blocks):
            out.append(src)
            mt = self._mt_of(i)
            if mt:
                # 本段开头接上了上一段的半句：用 … 标出接续关系（C-099①）
                if self.mt.seg_carry.get(i):
                    mt = '…' + mt
                out.append('〔译〕' + mt)
            elif self.mt.seg_carry.get(i) and self.mt.active:
                # 整段都是半句、已并入下一段：说明译文在哪，避免看起来像丢了
                out.append('〔译〕（半句，接续下一段）')
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
        if self.var_overlay.get() and not self.overlay:
            self.overlay = CaptionOverlay(self.root, self.args.font_size)
        elif not self.var_overlay.get() and self.overlay:
            self.overlay.destroy()
            self.overlay = None

    def quit(self):
        self.stop()
        self.mt.flush()          # C-099①：收尾时把挂起的半句补翻，不能丢
        self.mt.close()
        if self.engine:
            self.engine.close()
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
            draft = self.mt.draft if (self.mt.active and self.mt.draft_on) else ''
            # 定稿译文与草稿预览**分行**显示：草稿单独占 overlay 的第四行，
            # 不与定稿译文互相顶替（否则定稿译文一出现，草稿预览就没了）。
            self.overlay.show(self.final_text.replace('\n', ' ').rstrip(), partial,
                              mt_tail, draft)

    def _poll(self):
        self._drain_ui_log()          # 后台线程的日志统一在这里上屏
        self._track_mt_state()
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
                      force_language=asr_lang)
    print(f'[{args.engine}] 加载 {eng.load_s:.1f} s，设备 {eng.device_desc}，'
          f'识别语种 {asr_lang or "自动检测"}', flush=True)
    mt = TranslationService(target=args.translate, device=args.mt_device,
                            engine_key=args.mt_engine, use_ctx=args.mt_ctx,
                            glossary=args.mt_glossary,
                            draft=_init_draft_flag(args),
                            on_log=lambda m: print(f'  [翻译] {m}', flush=True))
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
                if kind == 'final' and txt.strip():
                    print(f'\n[译文] {txt}', flush=True)
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
            if kind == 'final' and txt.strip():
                print(f'[译文] {txt}', flush=True)
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
                    m = '（半句，接续下一段）'
                lines.append(m or '')
            with open(mtp, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
            print(f'[{args.engine}] 译文已写 {mtp}', flush=True)
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
    """探测 OpenVINO 可用设备。返回 (设备名 -> 全名) 映射。"""
    try:
        import openvino as ov
        core = ov.Core()
        out = {}
        for d in core.available_devices:
            try:
                out[d] = core.get_property(d, 'FULL_DEVICE_NAME')
            except Exception:
                out[d] = d
        return out
    except Exception as e:
        print(f'  [跳过] OpenVINO 不可用：{e}')
        return {}


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
    ap.add_argument('--mt-device', default='GPU.0',
                    help="翻译模型推理设备；--mt-engine 非 auto 时以后端自带的设备为准")
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
    args = ap.parse_args()

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
