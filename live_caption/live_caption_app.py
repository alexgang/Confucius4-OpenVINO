r"""live_caption_app.py — Confucius4-R2T2 实时麦克风字幕（多后端对比测试应用）

采集麦克风（16 kHz 单声道），流式识别，并把字幕实时显示在屏幕上。
可在界面里切换推理后端：

  Intel GPU · INT8     集显，编码器与解码器都是 INT8
  Intel GPU · INT4     集显，编码器与解码器都是 INT4
  Intel NPU · INT8     编码器与解码器都在 NPU（inputs_embeds 版解码器，INT8_SYM）
  Intel NPU · INT4     同上，解码器 INT4（AWQ + 20% INT8 混合，实验配置，WER 显著变差）
  NVIDIA GPU · CUDA    audio.cpp + GGUF（Q8_0 / Q4_K），独显

OpenVINO 后端复用仓库里的流式实现（streaming_asr + seg_stream，640 ms 分块，
LSP 前缀回滚，自适应生成预算）；分段规则与 mic_asr_app.py 相同：
段长 ≥12 s 且最近 3 s 内出现 ≥300 ms 静音就切段，最长 20 s 硬切。
CUDA 后端每段起一个 audiocpp_cli 流式进程（stdin 喂 PCM，stdout 读 partial_text），
并提前预热下一段要用的进程，切段时无需等模型加载。

用法:
  python live_caption_app.py                         # GUI
  python live_caption_app.py --engine npu_int8       # 启动时预选后端
  python live_caption_app.py --cli --engine gpu_int8 --file x.wav --max-seconds 60
  python live_caption_app.py --list-devices

实时翻译（C-098 阶段 A，Hunyuan-1.8B-Instruct）：
  python live_caption_app.py --cli --engine gpu_int8 --file x.wav --translate zh
  python live_caption_app.py --translate en --mt-device NPU

ASR 与翻译的设备/量化各自独立选择（C-098 阶段 B，实测结论见 hy_bench\STATUS_hy.md）：
  --engine   决定 ASR 跑哪张卡/哪种量化；--mt-engine 决定翻译跑哪张卡/哪种量化。
  python live_caption_app.py --engine npu_int8  --translate zh --mt-engine gpu_int4
  python live_caption_app.py --engine gpu_int8  --translate zh --mt-engine npu_int4cw
  # 翻译后端：auto(默认) | gpu_int4 | gpu_int4cw | npu_int4cw | npu_int8cw
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

from translator import (MT_DEFAULT, MT_ENGINES, TARGETS, TARGET_LABELS,
                        TranslationService, mt_available, split_sentences)

SR = 16000
CHUNK_SEC = 0.64
MIN_SEG_SEC = 12.0
MAX_SEG_SEC = 20.0
SIL_LOOKBACK_SEC = 3.0
BLOCK_MS = 100

HOME = r'C:\Users\Trekker-PTL'
MODELS = os.path.join(HOME, r'confucius4-openvino\models')
WORKTREE = os.path.join(HOME, r'WorkBuddy\Worktrees\confucius4-openvino\c038-v2-ir-6c123954')
CUDA_DIR = os.path.join(HOME, 'confucius4-r2t2')
CUDA_CLI = os.path.join(CUDA_DIR, r'audio.cpp\audiocpp_cli.exe')


def _cache(name):
    """复用目标机已有的编译缓存（首次编译 NPU 模型要 1–2 分钟）。"""
    shared = os.path.join(WORKTREE, 'reports' if name == 'npu_cache' else '', name)
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


def _norm_word(w):
    return str(w).strip('.,!?;:，。！？；：').lower()


def resample_to_16k(x, src_sr):
    if src_sr == SR:
        return x
    n = int(round(len(x) * SR / src_sr))
    idx = np.linspace(0, len(x) - 1, n)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


class Segmenter:
    """与 mic_asr_app 相同的在线切段规则（只看已累计的音频）。"""

    def __init__(self):
        from seg_stream import find_silence_in_range
        self._find = find_silence_in_range

    def due(self, acc):
        n = acc.shape[0]
        dur = n / SR
        if dur < MIN_SEG_SEC:
            return False
        if dur >= MAX_SEG_SEC:
            return True
        start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
        return self._find(acc, start_sample=start, end_sample=n,
                          silence_db=-40.0, min_silence_ms=300) is not None


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

    def __init__(self, key, on_log=print):
        from seg_stream import _make_segment_state
        from streaming_asr import (streaming_transcribe, finish_streaming_transcribe,
                                   parse_asr_output, _normalize_punct_by_context)
        self.key, self.cfg = key, ENGINES[key]
        self._st, self._finish = streaming_transcribe, finish_streaming_transcribe
        self._parse, self._norm = parse_asr_output, _normalize_punct_by_context
        self._make_state = _make_segment_state
        self.seg = Segmenter()
        t0 = time.perf_counter()
        enc = os.path.join(MODELS, self.cfg['enc'])
        dec = os.path.join(MODELS, self.cfg['dec'])
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
            npy = os.path.join(MODELS, 'qwen3-lm-int8sym-cleanie-ov', 'embed_tokens_f16.npy')
            npu_embeds_backend._load_embed_table = \
                lambda: np.asarray(np.load(npy), dtype=np.float32)
            on_log(f'加载 {self.cfg["label"]}（首次编译 NPU 模型可能要 1–2 分钟）…')
            self.backend = make_delivery_all_npu_backend(
                encoder_dir=enc, decoder_dir=dec,
                tokenizer_dir=os.path.join(MODELS, 'ov-int8-past'),
                npu_cache=_cache('npu_cache'))
            self.device_desc = 'NPU'
        self.load_s = time.perf_counter() - t0
        self._last_words = []
        self.stats = dict(chunks=0, segs=0, proc_s=0.0, wall_s=0.0, lag_ms=None)
        self.reset()

    def reset(self):
        self.state = self._make_state(self.backend, unfixed_chunk_num=0, unfixed_token_num=5,
                                      chunk_size_sec=CHUNK_SEC, force_language=None)
        self.state.diag_log = []
        self.cur_text = ''

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

    def __init__(self, gguf):
        cmd = [CUDA_CLI, '--task', 'asr', '--family', 'confucius4_r2t2',
               '--model', os.path.join(CUDA_DIR, 'models', gguf), '--backend', 'cuda',
               '--mode', 'streaming', '--audio', '-', '--input-format', 's16le',
               '--input-rate', '16000', '--input-channels', '1',
               '--session-option', 'chunk_size_ms=640',
               '--session-option', 'unfixed_chunk_num=0',
               '--session-option', 'unfixed_token_num=5',
               '--session-option', 'max_tokens=32']
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
    def __init__(self, key, on_log=print):
        self.key, self.cfg = key, ENGINES[key]
        if not os.path.exists(CUDA_CLI):
            raise FileNotFoundError(CUDA_CLI)
        self.seg = Segmenter()
        self.device_desc = 'CUDA'
        on_log(f'加载 {self.cfg["label"]}（预热两个进程）…')
        t0 = time.perf_counter()
        self.cur = _CudaProc(self.cfg['gguf'])
        self.spare = _CudaProc(self.cfg['gguf'])
        if not self.cur.ready.wait(120) or self.cur.done.is_set():
            raise RuntimeError('audiocpp_cli 启动失败：\n' + '\n'.join(self.cur.err_tail))
        self.load_s = time.perf_counter() - t0
        self.finishing = []                  # 已关闭 stdin、等最终文本的会话（按顺序）
        self.acc = np.zeros(0, np.float32)
        self._last_words = []
        self.stats = dict(chunks=0, segs=0, proc_s=0.0, wall_s=0.0, lag_ms=None)

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
            self.cur, self.spare = self.spare, _CudaProc(self.cfg['gguf'])
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
        self.spare = _CudaProc(self.cfg['gguf'])
        self.acc = np.zeros(0, np.float32)
        self._last_words = []
        return out

    @property
    def rtf(self):
        return 0.0                           # CLI 不回报逐块耗时

    def close(self):
        for p in [self.cur, self.spare] + self.finishing:
            p.kill()


def make_engine(key, on_log=print):
    return (CudaEngine if ENGINES[key]['kind'] == 'cuda' else OVEngine)(key, on_log=on_log)


# ── 音频源 ──────────────────────────────────────────────────────────────
class AudioSource(threading.Thread):
    """后台线程把 (pcm, 采集时刻) 送进队列；支持麦克风与按实时速度回放文件。"""

    def __init__(self, out_q, *, device=None, wav=None):
        super().__init__(daemon=True)
        self.out_q, self.device, self.wav = out_q, device, wav
        self.stop_evt = threading.Event()
        self.src_sr = SR
        self.err = None
        self.level = 0.0
        self.name_used = ''

    def run(self):
        try:
            self._run_file() if self.wav else self._run_mic()
        except Exception as e:
            self.err = e
        finally:
            self.out_q.put(None)

    def _run_mic(self):
        import sounddevice as sd
        try:
            sd.check_input_settings(device=self.device, samplerate=SR, channels=1)
            self.src_sr = SR
        except Exception:
            self.src_sr = int(sd.query_devices(self.device, 'input')['default_samplerate'])
        self.name_used = sd.query_devices(self.device, 'input')['name'] \
            if self.device is not None else sd.query_devices(kind='input')['name']

        def cb(indata, frames, _t, status):
            if self.stop_evt.is_set():
                raise sd.CallbackStop()
            x = np.asarray(indata, dtype=np.float32).reshape(-1)
            self.level = float(np.sqrt(float(np.mean(x * x)) + 1e-12))
            self.out_q.put((x.copy(), time.perf_counter()))

        with sd.InputStream(samplerate=self.src_sr, channels=1, dtype='float32',
                            blocksize=int(self.src_sr * BLOCK_MS / 1000),
                            device=self.device, callback=cb):
            while not self.stop_evt.is_set():
                time.sleep(0.05)

    def _run_file(self):
        import soundfile as sf
        audio, sr = sf.read(self.wav, dtype='float32')
        if audio.ndim > 1:
            audio = audio[:, 0]
        audio = resample_to_16k(audio, sr)
        self.name_used = os.path.basename(self.wav)
        step = int(SR * BLOCK_MS / 1000)
        t_next = time.perf_counter()
        for i in range(0, len(audio), step):
            if self.stop_evt.is_set():
                break
            blk = audio[i:i + step].copy()
            self.level = float(np.sqrt(float(np.mean(blk * blk)) + 1e-12))
            self.out_q.put((blk, time.perf_counter()))
            t_next += BLOCK_MS / 1000.0
            time.sleep(max(0.0, t_next - time.perf_counter()))


class Session:
    """把音频源和引擎接起来的后台推理循环（GUI 与 CLI 共用）。"""

    def __init__(self, engine, *, device=None, wav=None, on_final=None):
        self.engine = engine
        self.q = queue.Queue()
        self.src = AudioSource(self.q, device=device, wav=wav)
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
        self.src.stop_evt.set()

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
    第一行最近定稿（白），第二行正在识别（黄），第三行译文（青）。"""

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
        h = 3 * line + 34
        self.win.geometry(f'{self.w}x{h}+{(sw - self.w) // 2}+{sh - h - int(sh * 0.07)}')
        self.win.configure(bg='#111111')
        self.final = tk.Label(self.win, text='', fg='#f2f2f2', bg='#111111',
                              font=self.font, anchor='w')
        self.partial = tk.Label(self.win, text='', fg='#ffd75e', bg='#111111',
                                font=self.font, anchor='w')
        self.mt = tk.Label(self.win, text='', fg='#5fd7d7', bg='#111111',
                           font=self.font, anchor='w')
        self.final.pack(fill='x', padx=20, pady=(10, 0))
        self.partial.pack(fill='x', padx=20)
        self.mt.pack(fill='x', padx=20)
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

    def show(self, final_tail, partial, mt=''):
        self.final.configure(text=self._tail_fit(final_tail[-400:]))
        self.partial.configure(text=self._tail_fit(partial[-400:]))
        self.mt.configure(text=self._tail_fit(mt[-400:]) if mt else '')

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

        ttk.Label(top, text='麦克风').pack(side='left')
        self.mics = self._list_mics()
        self.var_mic = tk.StringVar(value=self.mics[0][1] if self.mics else '（未找到输入设备）')
        ttk.Combobox(top, state='readonly', width=30, textvariable=self.var_mic,
                     values=[m[1] for m in self.mics]).pack(side='left', padx=(4, 12))

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
        root.protocol('WM_DELETE_WINDOW', self.quit)
        self.load_engine()
        root.after(self.POLL_MS, self._poll)

    # -- 设备 / 引擎 ------------------------------------------------------
    def _list_mics(self):
        try:
            import sounddevice as sd
            default = sd.default.device[0]
            hostapis = sd.query_hostapis()
            out = []
            for i, d in enumerate(sd.query_devices()):
                if d.get('max_input_channels', 0) > 0 and \
                        hostapis[d['hostapi']]['name'] in ('MME', 'Windows WASAPI'):
                    tag = '（默认）' if i == default else ''
                    out.append((i, f'[{i}] {d["name"]} · {hostapis[d["hostapi"]]["name"]}{tag}'))
            out.sort(key=lambda m: '（默认）' not in m[1])
            return out
        except Exception:
            return []

    def _mic_index(self):
        for i, label in self.mics:
            if label == self.var_mic.get():
                return i
        return None

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
                eng = make_engine(key, on_log=self._ui_log)
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
        self.session = Session(self.engine, device=self._mic_index(), wav=self.args.file,
                               on_final=self._on_final)
        self.session.start()
        self.btn.configure(text='■ 停止')
        self.var_status.set(f'识别中 · {ENGINES[self.engine_key]["label"]}')

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
            dra = self.mt.draft if self.mt.active else ''
            if dra:
                self.txt.insert('end', '\n    〔译〕' + dra, 'mt_partial')
        self.txt.see('end')
        self.txt.configure(state='disabled')
        if self.overlay:
            mt_tail = ' '.join(m for m in (self._mt_of(b) for b in self.blocks[-3:]) if m)
            self.overlay.show(self.final_text.replace('\n', ' ').rstrip(), partial,
                              mt_tail or (self.mt.draft if self.mt.active else ''))

    def _poll(self):
        self._drain_ui_log()          # 后台线程的日志统一在这里上屏
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

    def _mt_meter(self):
        """指标栏里的翻译一段：加载中 / 失败 / 延迟中位 + 积压（含实际生效设备）。"""
        mt = self.mt
        if not mt.active:
            return ''
        if mt.state == 'loading':
            return f'  翻译 {mt.device} 加载中…'
        if mt.state == 'error':
            return f'  翻译 失败（{mt.err}）'
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
def run_cli(args):
    eng = make_engine(args.engine, on_log=lambda m: print(m, flush=True))
    print(f'[{args.engine}] 加载 {eng.load_s:.1f} s，设备 {eng.device_desc}', flush=True)
    mt = TranslationService(target=args.translate, device=args.mt_device,
                            engine_key=args.mt_engine, use_ctx=args.mt_ctx,
                            on_log=lambda m: print(f'  [翻译] {m}', flush=True))
    finals = []

    def on_final(t):
        finals.append(t)
        print(f'\n[定稿] {t}', flush=True)
        mt.submit(t, seg=len(finals) - 1)

    s = Session(eng, device=args.device, wav=args.file, on_final=on_final)
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
    import sounddevice as sd
    for i, d in enumerate(sd.query_devices()):
        if d.get('max_input_channels', 0) > 0:
            print(f'[{i}] {d["name"]}  sr={d.get("default_samplerate")}'
                  f'{"  *默认" if i == sd.default.device[0] else ""}')


def main():
    ap = argparse.ArgumentParser(description='Confucius4-R2T2 实时字幕（多后端）')
    ap.add_argument('--engine', choices=list(ENGINES), default='gpu_int8')
    ap.add_argument('--device', type=int, default=None, help='CLI 模式的麦克风序号')
    ap.add_argument('--file', default=None, help='用音频文件按实时速度回放代替麦克风')
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
    ap.add_argument('--translate', choices=list(TARGETS), default='off',
                    help='实时翻译目标语言（Hunyuan-1.8B-Instruct）；off=不翻译')
    ap.add_argument('--mt-device', default='GPU.0',
                    help="翻译模型推理设备；--mt-engine 非 auto 时以后端自带的设备为准")
    ap.add_argument('--mt-engine', choices=list(MT_ENGINES), default=MT_DEFAULT,
                    help='翻译后端（设备 × 量化）；auto = 用 --mt-device + LIVECAP_MT_MODEL')
    ap.add_argument('--mt-ctx', action='store_true',
                    help='翻译时带上一句原文做上下文（C-099②，减少术语/指代错误）')
    args = ap.parse_args()

    if args.list_devices:
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
