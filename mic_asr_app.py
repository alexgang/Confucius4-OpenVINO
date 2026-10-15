"""mic_asr_app.py — Confucius4 OpenVINO 实时麦克风语音识别

把仓库现有的流式 ASR（`streaming_asr.streaming_transcribe` + segment encoder
+ INT8 decoder）包装成一个桌面应用：
  - 采集本机麦克风（16 kHz 单声道）
  - 逐 chunk 增量解码，边说边出字
  - 在线 VAD 分段（12-20 s），段结束时 flush 尾巴
  - tkinter 窗口实时显示已确认文本 + 当前段的临时结果

与离线 `transcribe_stream.py` 共用同一套模型和参数（adaptive_budget 默认开），
因此这里显示的质量与 61-min 验收口径一致。

用法:
  .venv python mic_asr_app.py                       # 默认麦克风 + GUI
  .venv python mic_asr_app.py --cli                 # 终端模式（无 GUI）
  .venv python mic_asr_app.py --list-devices        # 列出输入设备
  .venv python mic_asr_app.py --device 3            # 指定输入设备
  .venv python mic_asr_app.py --file in.wav         # 用音频文件模拟实时（自测）
"""
import argparse
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime

os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

SR = 16000
CHUNK_SEC = 0.64          # 与 offline 主循环同粒度
MIN_SEG_SEC = 12.0        # 低于此时长不切段
MAX_SEG_SEC = 20.0        # 硬切上限（segment encoder 上限 ≈24.3 s）
SIL_LOOKBACK_SEC = 3.0    # 超过最短时长后，只看最近这几秒有没有静音

# 默认与 transcribe_stream.py 的 C-047 交付配置一致
DEFAULT_ENCODER = 'models/ov-encoder-segment-reviewer'
DEFAULT_DECODER = 'models/ov-int8-past'
DEFAULT_DEVICE = 'GPU.0'


# ── 重采样（仅当麦克风不支持 16 kHz 时使用）─────────────────────────────
def _norm_word(w: str) -> str:
    """接缝比较用的词归一化：去首尾标点 + 小写。"""
    return str(w).strip('.,!?;:').lower()


def resample_to_16k(x: np.ndarray, src_sr: int) -> np.ndarray:
    if src_sr == SR:
        return x
    n = int(round(len(x) * SR / src_sr))
    idx = np.linspace(0, len(x) - 1, n)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


# ── 识别引擎 ────────────────────────────────────────────────────────────
class StreamingEngine:
    """把 streaming_transcribe 包装成可持续 feed 的增量引擎。

    外部只需反复调用 feed(pcm)；引擎内部处理在线分段，
    并在每次解码后通过 cur_text 暴露当前段的累计文本。
    """

    def __init__(self, *, encoder_dir=DEFAULT_ENCODER, decoder_dir=DEFAULT_DECODER,
                 device=DEFAULT_DEVICE, chunk_sec=CHUNK_SEC,
                 adaptive_budget=True, force_language=None,
                 seam_dedup=True,
                 on_log=lambda msg: None):
        from segment_encoder_backend import SegmentEncoderOVBackend
        from seg_stream import _make_segment_state, find_silence_in_range
        from streaming_asr import (streaming_transcribe,
                                   finish_streaming_transcribe,
                                   parse_asr_output,
                                   _normalize_punct_by_context)

        self._st = streaming_transcribe
        self._find = finish_streaming_transcribe
        self._parse = parse_asr_output
        self._norm = _normalize_punct_by_context
        self._find_silence = find_silence_in_range
        self._make_state = _make_segment_state
        self.chunk_sec = chunk_sec
        self.adaptive_budget = adaptive_budget
        self.force_language = force_language
        self.seam_dedup = seam_dedup
        self._last_words = []     # 上一段末尾若干词，供接缝去重
        self.on_log = on_log

        self.on_log(f'加载 {encoder_dir} ...')
        self.backend = SegmentEncoderOVBackend(
            encoder_dir=encoder_dir, decoder_dir=decoder_dir,
            device=device, precision='f16')
        self.on_log(f'加载 {decoder_dir} 完成')

        self.reset()
        self.stats = dict(chunks=0, segs=0, proc_s=0.0, wall_s=0.0)

    def reset(self):
        """开一个新段。"""
        self.state = self._make_state(
            self.backend, unfixed_chunk_num=0, unfixed_token_num=5,
            chunk_size_sec=self.chunk_sec, force_language=self.force_language)
        if getattr(self, 'adaptive_budget', False):
            self.state.diag_log = []
        self.cur_text = ''
        self.cur_lang = ''
        # 注意：不能在这里清空 self._last_words —— 它要跨段保留供 _stitch 用，
        # 只有整场会话重置时才清（reset_session）。

    # -- 在线分段判断 ----------------------------------------------------
    def _due_for_cut(self):
        """是否可以现在切段。

        切点必然落在 **chunk 边界**（= audio_accum 末尾），不做任意位置切割。
        原因：切割点之后、尚未解码的音频会被当作 carry 交给下一段；若切在
        chunk 内部，那部分音频其实**已经参与过本段的 encoder**，再喂一次下一段
        就会被识别两遍（实测段尾段首出现重复短语）。对齐到 chunk 边界后，
        carry 恒等于 state.buffer —— 一段从未解码过的干净残余。
        """
        acc = self.state.audio_accum
        n = acc.shape[0]
        dur = n / SR
        if dur < MIN_SEG_SEC:
            return False
        if dur >= MAX_SEG_SEC:
            return True
        # 到了最短时长就盯着尾部的静音，说完整句再切
        start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
        cut = self._find_silence(acc, start_sample=start, end_sample=n,
                                 silence_db=-40.0, min_silence_ms=300)
        return cut is not None

    def reset_session(self):
        """整场会话重新开始（清拼接状态与统计）。"""
        self.reset()
        self._last_words = []
        self.stats = dict(chunks=0, segs=0, proc_s=0.0, wall_s=0.0)

    def _finalize(self):
        """段收尾：与 finish_streaming_transcribe 同逻辑，但**不吞 state.buffer**。

        finish 一旦看到非空 buffer 就会把它拼进 audio_accum 再生成一次；
        在线切段时这段音频要留给下一段，所以这里自己走一遍收尾生成，
        只用 audio_accum，buffer 保持不动。
        """
        st = self.state
        cur_ids = self.backend.tokenizer.encode(st._raw_decoded)
        end_idx = max(1, len(cur_ids) - int(st.unfixed_token_num))
        prefix = self.backend.tokenizer.decode(cur_ids[:end_idx]).split('|')[0]
        gen = self.backend.generate_with_prefix(st, st.audio_accum, prefix,
                                                max(64, 32))
        gen = self._norm(gen).replace('\ufffd', '')
        st._raw_decoded = ((prefix + gen) if prefix else gen).split('|')[0]
        lang, txt = self._parse(st._raw_decoded, user_language=st.force_language)
        st.language = lang
        st.text = txt.split('|')[0]
        st.chunk_id += 1
        return st.text

    # -- 增量喂数据 ------------------------------------------------------
    def feed(self, pcm: np.ndarray):
        """喂一小段麦克风音频。返回本轮定稿文本（可能含多段），None 表示没有。"""
        if pcm is None or len(pcm) == 0:
            return None
        x = np.asarray(pcm, dtype=np.float32).reshape(-1)

        pre_cid = self.state.chunk_id
        t0 = time.perf_counter()
        self._st(self.backend, x, self.state,
                 max_new_tokens=32, rollback_punctuation=False,
                 enable_hallucination_reset=False,
                 adaptive_budget=self.adaptive_budget)
        self.stats['wall_s'] += time.perf_counter() - t0

        n_new = self.state.chunk_id - pre_cid
        if n_new <= 0:
            return None                    # 还没攒够一个 chunk，本次无解码
        self.stats['chunks'] += n_new
        self.stats['proc_s'] += n_new * self.chunk_sec

        self.cur_lang, self.cur_text = self._parse(
            self.state._raw_decoded, user_language=self.force_language)

        outs = []
        while self._due_for_cut():
            outs.append(self._close_segment())
            if self.state.audio_accum.shape[0] == 0:
                break
        return ''.join(outs) if outs else None

    def _stitch(self, text: str) -> str:
        """接缝去重：处理段边界处偶发的 1 词重复。

        在线切段对齐到 chunk 边界（640 ms），一个词可能正好横跨边界，
        于是上一段末尾吐出了它、下一段开头又吐一次。
        只在"下一段首词 == 上一段尾词"时删掉首词 —— 最保守的一条规则，
        正常口语里极少出现这种合法重复。
        """
        if not self.seam_dedup or not self._last_words or not text:
            return text
        words = text.split()
        if not words:
            return text
        nw = [_norm_word(w) for w in words]
        prev = [_norm_word(w) for w in self._last_words]
        # 只匹配 2-3 词：连续 2 词以上完全相同在正常口语里几乎不会出现，
        # 而 1 词太容易误伤合法的单词重复（"that that"、"very very"）。
        for n in (3, 2):
            if len(nw) >= n and len(prev) >= n and prev[-n:] == nw[:n]:
                rest = words[n:]
                return ' '.join(rest) if rest else text
        return text

    def _close_segment(self):
        carry = self.state.buffer.copy()
        final = self._finalize()
        final = self._stitch(final)
        ws = final.split()
        if ws:
            self._last_words = ws[-3:]
        self.stats['segs'] += 1
        self.reset()
        self.state.buffer = carry          # 未解码残余交给下一段
        return final

    def flush(self):
        """停止时把残留音频收尾（此时没有下一段，用官方 finish 即可）。"""
        st = self.state
        if st.audio_accum.shape[0] == 0 and st.buffer.shape[0] == 0:
            return None
        final = self._find(self.backend, st, max_new_tokens=max(64, 32))
        self.stats['segs'] += 1
        self.reset()
        return final

    @property
    def rtf(self):
        return (self.stats['wall_s'] / self.stats['proc_s']
                if self.stats['proc_s'] > 0 else 0.0)


# ── 音频源 ──────────────────────────────────────────────────────────────
class AudioSource(threading.Thread):
    """后台线程把 PCM 块送进 out_q；支持麦克风与文件回放两种模式。"""

    def __init__(self, out_q, *, device=None, block_ms=100, wav=None):
        super().__init__(daemon=True)
        self.out_q = out_q
        self.device = device
        self.block_ms = block_ms
        self.wav = wav
        self.stop_evt = threading.Event()
        self.src_sr = SR
        self.err = None
        self.actual_device = None
        self.level = 0.0          # 最近一块的 RMS，用于 UI 电平条

    def run(self):
        try:
            if self.wav:
                self._run_file()
            else:
                self._run_mic()
        except Exception as e:          # 线程里的异常必须带回主线程
            self.err = e
        finally:
            self.out_q.put(None)        # EOF 哨兵

    def _run_mic(self):
        import sounddevice as sd
        # 先确认 16 kHz 是否可用，不行就按设备原生采样率开 + 重采样
        try:
            sd.check_input_settings(device=self.device, samplerate=SR, channels=1)
            self.src_sr = SR
        except Exception:
            info = sd.query_devices(self.device, 'input')
            self.src_sr = int(info['default_samplerate'])
        self.actual_device = sd.query_devices(
            self.device, 'input')['name'] if self.device is not None \
            else sd.query_devices(kind='input')['name']

        n = int(self.src_sr * self.block_ms / 1000)

        def cb(indata, frames, _t, status):
            if self.stop_evt.is_set():
                raise sd.CallbackStop()
            x = np.asarray(indata, dtype=np.float32).reshape(-1)
            self.level = float(np.sqrt(float(np.mean(x * x)) + 1e-12))
            self.out_q.put(x.copy())

        with sd.InputStream(samplerate=self.src_sr, channels=1, dtype='float32',
                            blocksize=n, device=self.device, callback=cb):
            while not self.stop_evt.is_set():
                time.sleep(0.05)

    def _run_file(self):
        import soundfile as sf
        audio, sr = sf.read(self.wav, dtype='float32')
        if audio.ndim > 1:
            audio = audio[:, 0]
        if sr != SR:
            audio = resample_to_16k(audio, sr)
        step = int(SR * self.block_ms / 1000)
        for i in range(0, len(audio), step):
            if self.stop_evt.is_set():
                break
            blk = audio[i:i + step].copy()
            self.level = float(np.sqrt(float(np.mean(blk * blk)) + 1e-12))
            self.out_q.put(blk)
            time.sleep(self.block_ms / 1000.0)   # 按真实时间回放


# ── tkinter UI ──────────────────────────────────────────────────────────
class App:
    POLL_MS = 60

    def __init__(self, root, args):
        import tkinter as tk
        from tkinter import ttk, scrolledtext, messagebox, filedialog
        self.tk, self.ttk = tk, ttk
        self._sct, self._mb, self._fd = scrolledtext, messagebox, filedialog

        self.root = root
        self.args = args
        self.engine = None
        self.src = None
        self.q = queue.Queue()
        self.running = False
        self.audio_sec = 0.0
        self.final_text = ''
        self.partial = ''
        self.seg_count = 0
        self._worker = None

        root.title('Confucius4 · OpenVINO 实时语音识别')
        root.geometry('980x680')

        top = ttk.Frame(root, padding=(10, 8))
        top.pack(fill='x')
        self.btn = ttk.Button(top, text='▶ 开始识别', command=self.toggle)
        self.btn.pack(side='left')
        ttk.Button(top, text='清空', command=self.clear).pack(side='left', padx=6)
        ttk.Button(top, text='保存 transcript', command=self.save).pack(side='left')
        self.var_status = tk.StringVar(value='正在加载模型…')
        ttk.Label(top, textvariable=self.var_status,
                  foreground='#555').pack(side='right')

        mono = ('Consolas', 13)
        self.txt = scrolledtext.ScrolledText(root, wrap='word', font=mono,
                                             relief='flat', padx=12, pady=10,
                                             spacing3=6)
        self.txt.pack(fill='both', expand=True, padx=10, pady=(0, 4))
        self.txt.configure(state='disabled')

        # 当前段的临时结果用灰色斜体区分
        self.txt.tag_config('partial', foreground='#9a9a9a', font=('Consolas', 13, 'italic'))
        self.txt.tag_config('seg', foreground='#1a1a1a')
        self.txt.tag_config('hdr', foreground='#2b6cb0',
                            font=('Consolas', 10, 'bold'))

        bot = ttk.Frame(root, padding=(10, 4))
        bot.pack(fill='x')
        self.var_meter = tk.StringVar(value='')
        ttk.Label(bot, textvariable=self.var_meter, font=('Consolas', 10),
                  foreground='#444').pack(side='left')

        threading.Thread(target=self._boot_engine, daemon=True).start()

    # -- 引擎 -----------------------------------------------------------
    def _boot_engine(self):
        try:
            self.engine = StreamingEngine(
                encoder_dir=self.args.encoder_dir,
                decoder_dir=self.args.decoder_dir,
                device=self.args.device_target,
                adaptive_budget=not self.args.no_adaptive_budget,
                seam_dedup=not self.args.no_seam_dedup,
                on_log=lambda m: self.root.after(0, lambda: self.var_status.set(m)))
        except Exception as e:
            self.root.after(0, lambda: self._mb.showerror(
                '模型加载失败', f'{type(e).__name__}: {e}'))
            return
        self.root.after(0, lambda: (
            self.var_status.set('就绪 — 点「开始识别」'),
            self.btn.configure(state='normal')))

    # -- 控制 -----------------------------------------------------------
    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.engine is None or self.running:
            return
        self.running = True
        self.btn.configure(text='■ 停止')
        self.q = queue.Queue()
        self.src = AudioSource(self.q, device=self.args.device,
                               wav=self.args.file)
        self.src.start()
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()
        self.root.after(self.POLL_MS, self._poll)

    def stop(self):
        self.running = False
        if self.src:
            self.src.stop_evt.set()
        self.btn.configure(text='▶ 开始识别')
        self.var_status.set('已停止')

    def clear(self):
        self.final_text = ''
        self.partial = ''
        self.seg_count = 0
        self._render()

    def save(self):
        if not self.final_text:
            return
        p = self._fd.asksaveasfilename(
            defaultextension='.txt',
            initialfile=f'mic_{datetime.now():%Y%m%d_%H%M%S}.txt')
        if p:
            open(p, 'w', encoding='utf-8').write(self.final_text)
            self.var_status.set(f'已保存 {os.path.basename(p)}')

    # -- 推理循环（后台线程）--------------------------------------------
    def _loop(self):
        while self.running:
            try:
                pcm = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            if pcm is None:
                break
            if self.src.src_sr != SR:
                pcm = resample_to_16k(pcm, self.src.src_sr)
            self.audio_sec += len(pcm) / SR
            try:
                final = self.engine.feed(pcm)
            except Exception:
                if not self.running:
                    break
                raise
            if final:
                self.seg_count += 1
                self.final_text += final
            self.partial = self.engine.cur_text
        # 收尾
        try:
            tail = self.engine.flush() if self.engine else None
            if tail:
                self.seg_count += 1
                self.final_text += tail
        except Exception:
            pass
        if self.running:
            self.root.after(0, self.stop)

    # -- UI 刷新（主线程）-----------------------------------------------
    def _poll(self):
        if not self.running:
            return
        if self.src and self.src.err:
            self._mb.showerror('音频采集失败',
                               f'{type(self.src.err).__name__}: {self.src.err}')
            self.stop()
            return
        self._render()
        e = self.engine
        pct = min(100, len(e.state.audio_accum) / SR / MAX_SEG_SEC * 100) if e else 0
        # 电平条：RMS 0.03 算满格，粗略但足以看出麦克风是否在收声
        lv = self.src.level if self.src else 0.0
        bars = min(12, int(lv / 0.03 * 12))
        self.var_meter.set(
            f'麦克风 {"█" * bars}{"░" * (12 - bars)}   '
            f'音频 {self.audio_sec:6.1f}s   RTF {e.rtf:.3f}   '
            f'chunks {e.stats["chunks"]:4d}   已定稿段 {self.seg_count}   '
            f'本段缓冲 {pct:3.0f}%')
        self.var_status.set('识别中…')
        self.root.after(self.POLL_MS, self._poll)

    def _render(self):
        self.txt.configure(state='normal')
        self.txt.delete('1.0', 'end')
        self.txt.insert('end', self.final_text, 'seg')
        if self.partial:
            if self.final_text and not self.final_text.endswith('\n'):
                self.txt.insert('end', '\n')
            self.txt.insert('end', self.partial, 'partial')
        self.txt.see('end')
        self.txt.configure(state='disabled')


# ── CLI 模式（无 GUI）───────────────────────────────────────────────────
def run_cli(args):
    print('加载模型…', flush=True)
    eng = StreamingEngine(encoder_dir=args.encoder_dir,
                          decoder_dir=args.decoder_dir,
                          device=args.device_target,
                          adaptive_budget=not args.no_adaptive_budget,
                          seam_dedup=not args.no_seam_dedup,
                          on_log=lambda m: print(' ', m, flush=True))
    q = queue.Queue()
    src = AudioSource(q, device=args.device, wav=args.file)
    src.start()
    print(f'开始（Ctrl-C 结束）。{"文件回放: " + args.file if args.file else "麦克风"}',
          flush=True)

    acc = 0.0
    last_printed = ''
    t_start = time.time()
    try:
        while True:
            if args.max_minutes > 0 and \
               (time.time() - t_start) > args.max_minutes * 60:
                print('\n[到达 --max-minutes 上限，自动停止]', flush=True)
                break
            try:
                pcm = q.get(timeout=0.3)
            except queue.Empty:
                continue
            if pcm is None:
                break
            if src.src_sr != SR:
                pcm = resample_to_16k(pcm, src.src_sr)
            acc += len(pcm) / SR
            final = eng.feed(pcm)
            if final:
                print(f'\n[定稿] {final}', flush=True)
            cur = eng.cur_text
            if cur != last_printed and cur:
                print(f'\r[实时] {cur}', end='', flush=True)
                last_printed = cur
    except KeyboardInterrupt:
        pass
    finally:
        src.stop_evt.set()
        tail = eng.flush()
        if tail:
            print(f'\n[定稿] {tail}', flush=True)
        print(f'\n音频 {acc:.1f}s  RTF {eng.rtf:.3f}  '
              f'chunks {eng.stats["chunks"]}  段 {eng.stats["segs"]}', flush=True)


def list_devices():
    import sounddevice as sd
    print('可用输入设备:')
    for i, d in enumerate(sd.query_devices()):
        if d.get('max_input_channels', 0) > 0:
            star = ' *' if i == sd.default.device[0] else ''
            print(f'  [{i}] {d["name"]}  sr={d.get("default_samplerate")}{star}')


def main():
    ap = argparse.ArgumentParser(description='Confucius4 OV 实时麦克风识别')
    ap.add_argument('--list-devices', action='store_true')
    ap.add_argument('--device', type=int, default=None, help='输入设备序号')
    ap.add_argument('--cli', action='store_true', help='终端模式，不弹窗口')
    ap.add_argument('--file', default=None, help='用音频文件按实时速度回放（自测）')
    ap.add_argument('--encoder-dir', default=DEFAULT_ENCODER)
    ap.add_argument('--decoder-dir', default=DEFAULT_DECODER)
    ap.add_argument('--device-target', default=DEFAULT_DEVICE, help='OpenVINO 设备')
    ap.add_argument('--no-adaptive-budget', action='store_true',
                    help='关闭 C-047 自适应生成长度（退回固定 32）')
    ap.add_argument('--no-seam-dedup', action='store_true',
                    help='关闭段接缝处的 1-3 词重叠去重')
    ap.add_argument('--max-minutes', type=float, default=0.0,
                    help='CLI 模式最多跑多少分钟后自动停止，0 = 不限')
    args = ap.parse_args()

    if args.list_devices:
        list_devices()
        return
    if args.cli:
        run_cli(args)
        return

    import tkinter as tk
    root = tk.Tk()
    App(root, args)
    try:
        root.iconbitmap(default='')      # Windows 下避免默认 tk 图标
    except Exception:
        pass
    root.mainloop()


if __name__ == '__main__':
    main()
