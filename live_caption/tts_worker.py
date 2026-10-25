"""tts_worker.py — TTS 独立子进程（C-101 / P4）。

## 为什么独立进程

1. **不抢 GIL**：TTS 的重活是 numpy 特征提取 + numpy 采样 + S2A 的 25 步 Euler
   循环 + BigVGAN。这些都在主进程的话，会把 ASR / MT 饿死，字幕会卡。
2. **崩溃隔离**：worker 挂了只影响语音输出，字幕翻译照常（C-101 的硬要求）。

## 进程内协议

主进程 → worker（stdin，每行一个 JSON）：
    {"cmd": "synth", "id": 3, "text": "..."}
    {"cmd": "clone", "pcm": "<base64 float32 16k>"}     # 克隆说话人（可选）
    {"cmd": "quit"}

worker → 主进程（stdout，每行一个 JSON）：
    {"kind": "ready", "device": "GPU.0", "voice": "A"}
    {"kind": "first_packet", "latency_s": 0.83}
    {"kind": "played", "id": 3}
    {"kind": "error", "message": "..."}
    {"kind": "log", "message": "..."}

非 JSON 的行当作普通日志转发。

## 播放

`sounddevice.OutputStream`（22050 Hz、单声道、float32）+ 环形缓冲。
合成线程把波形塞进环形缓冲，音频回调线程从中取数据播。
缓冲满时丢弃**最旧**的音频（宁可开头少一句，也不能让实时性崩掉）。

合成用**流式**路径（`native_stream.synth_stream`）：首块 25 token，之后每 50 token，
overlap 10，交叉淡化。这样第一包能早出来。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import threading
import time
from collections import deque
from typing import Optional

SR = 22050
CHUNK_SAMPLES = 1024          # 音频回调每次取多少采样

# 🔴 Qwen3-TTS（BabelVox）的输出采样率 —— **24000 Hz**（babelvox 原生）。
# 旧引擎（OVSynth + BigVGAN）是 22050 Hz。
# ⇒ 走 BabelVox 路线时播放流必须用 24000，否则**变调/加速**。
TTS_SR = 24000

# ⚠️ 2026-10-22 修：`_HERE` 之前**从未定义**，但被用了 2 处
#    （`_load_conds` 的 `voices/` 目录、`_update_clone` 的 `clone_C.npz`）
#    ⇒ `NameError: name '_HERE' is not defined` ⇒ 音色加载必崩 ⇒ `ready=False`。
_HERE = os.path.dirname(os.path.abspath(__file__))


def emit(obj: dict):
    """往 stdout 发一行 JSON（立刻 flush，主进程要实时看到状态）。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def log(msg: str):
    sys.stdout.write(str(msg) + '\n')
    sys.stdout.flush()


class RingBuffer:
    """线程安全的 float32 环形缓冲（**整句原子写入 + 写满时阻塞**）。

    ## 语义（C-101 第 3 条）

    原实现是「写满时丢最旧的样本」—— **不行**：
    在播放层丢样本会让一句话中间突然被切掉，听感很差。

    现在的语义：
    1. **整句原子写入**：`write()` 要么整句进去，要么整句不进（不会出现半句）。
    2. **写满时阻塞（反压）**：调用方（合成线程）被 `write()` 阻塞住，
       合成自然暂停，音频播放追上来后写入继续。
       这就是「缓冲容量 ≥ 2 块」的意义：宁可合成慢，不要播放断句。
    3. **丢弃不在这一层做**：整句级丢弃由 `tts_service` 层负责
       （丢的是**尚未开始播放**的整句），见 C-101 P4 第 2 条。

    实现：用 `threading.Condition` 做生产者-消费者同步。
    """

    def __init__(self, capacity: int = SR * 30, timeout_s: float = 30.0):
        self._cap = capacity
        self._buf = [None] * capacity
        self._w = 0
        self._r = 0
        self._count = 0
        self._cv = threading.Condition()
        self._closed = False
        self.timeout_s = timeout_s
        self.n_written = 0
        self.n_read = 0              # 累计被播放回调取走的样本数（诊断用）
        self.n_blocks = 0            # 因写满而阻塞的次数
        # 🔴 播放回调**完全没消费**时的判定阈值：超过这么久没有任何进展
        #    ⇒ 直接抛「回调没消费」而不是傻等 30 s（见 write() 的说明）。
        self.stall_s = min(5.0, float(timeout_s))

    def write(self, data, should_stop=None):
        """整句写入 —— **按空位分片推进**（不再要求「整句一次装下」）。

        🔴🔴 **2026-10-25 修（用户反馈「语音输出无论 NPU/GPU 都听不到声音」）**：

           旧实现是「**整句原子写入**」：:

               while self._count + n > self._cap:   # 等播放消费
                   ...

           ⇒ **只要整句样本数 n > 容量，`count + n > cap` 就永远成立**
             （`count` 最小是 0：`0 + n > cap`）⇒ 等满 `timeout_s` 必然
             `TimeoutError` ⇒ 该句被判「合成失败（已丢弃）」⇒ **一声都不响**。

           实测（`results/app/app044_player_probe.py`）：
             - 容量 = `sr*3` = **72 000 样本（3.00 s）**；
             - BabelVox 一句 19 字 = **138 240 样本（5.76 s）**；
             - ⇒ **每一句都 > 容量 ⇒ 每一句都必然写入失败**。
             - ⚠️ **与设备/精度/NPU/GPU 全都无关**；也**与回调在不在跑无关**
               —— 实测「有消费者」时仍然超时（70 次回调、消费 0 样本），
               因为要求的是「整句一次装下」，消费再多也腾不出 138 240 个空位。

           ⇒ 现改为**分片写入**：缓冲一有空位就写一段，直到整句写完。
             **仍然不丢样本、不切断句子**（语义不变），只是不再要求「一次装下」。
             `n_blocks` 仍记录「被反压阻塞的次数」，供诊断。

        `should_stop`：可选的无参可调用对象；返回 True 时**中止**本句
        （返回 False），已写入的部分留在缓冲里自然播完（不制造爆音）。
        """
        n = len(data)
        if n == 0:
            return True
        i = 0
        last_progress = time.monotonic()
        base_read = self.n_read
        while i < n:
            if should_stop is not None and should_stop():
                return False
            with self._cv:
                if self._closed:
                    raise RuntimeError('环形缓冲已关闭')
                if self._count < self._cap:
                    space = self._cap - self._count
                    take = min(space, n - i)
                    for j in range(take):
                        self._buf[self._w] = data[i + j]
                        self._w = (self._w + 1) % self._cap
                    self._count += take
                    self.n_written += take
                    i += take
                    self._cv.notify_all()
                    continue
                # ── 缓冲已满 ⇒ 等播放消费（反压）──
                if self.n_read != base_read:
                    base_read = self.n_read
                    last_progress = time.monotonic()
                stalled = time.monotonic() - last_progress
                if stalled > self.stall_s:
                    # 🔴 把「30 s 静默挂起」变成一条**能定位**的报错
                    raise RuntimeError(
                        '播放回调没有消费音频（%.1f s 无进展：容量 %d，已有 %d，'
                        '累计已写 %d，累计已读 %d）⇒ 请检查播放设备是否被占用/静音'
                        % (stalled, self._cap, self._count,
                           self.n_written, self.n_read))
                self.n_blocks += 1
                self._cv.wait(timeout=min(0.5, max(0.05,
                                                    self.stall_s - stalled)))
        return True

    def read(self, n) -> list:
        with self._cv:
            out = []
            for _ in range(min(n, self._count)):
                out.append(self._buf[self._r])
                self._buf[self._r] = None
                self._r = (self._r + 1) % self._cap
                self._count -= 1
            self.n_read += len(out)
            self._cv.notify_all()
            return out

    def level(self) -> int:
        with self._cv:
            return self._count

    def close(self):
        with self._cv:
            self._closed = True
            self._cv.notify_all()


class Player:
    """sounddevice 输出流 + 环形缓冲。

    音频回调在独立线程里跑（sounddevice 自己开线程），从环形缓冲取数据。
    缓冲欠载时补静音（不补静音会爆音）。
    """

    def __init__(self, device=None, sr: int = SR):
        import sounddevice as sd
        self.sr = sr
        # 容量 ≥ 2 块（约 2–3 s）：写满时靠阻塞反压，不靠丢样本
        # （C-101 第 3 条：播放层丢样本会让一句话中间被切断）。
        # 🔴 容量只影响「反压多早触发」，**不再影响能否写进去**
        #    （write() 已改为分片推进，见其 docstring）。
        self.ring = RingBuffer(capacity=sr * 3, timeout_s=30.0)
        self._sd = sd
        self._stream = None
        self._lock = threading.Lock()
        self.n_cb = 0                # 音频回调次数（诊断：0 = 回调根本没跑）
        try:
            self._stream = sd.OutputStream(
                samplerate=sr, channels=1, dtype='float32',
                device=device, blocksize=CHUNK_SAMPLES,
                callback=self._cb)
            self._stream.start()
            log(f'[tts_worker] 播放流已启动：sr={sr} device={device} '
                f'blocksize={CHUNK_SAMPLES} '
                f'latency={getattr(self._stream, "latency", None)}')
        except Exception as e:
            log(f'[tts_worker] 播放设备打开失败：{e}')
            emit({'kind': 'error', 'message': f'播放设备打开失败：{e}'})
            self._stream = None

    def _cb(self, outdata, frames, time_info, status):
        self.n_cb += 1
        if status and self.n_cb <= 5:
            # ⚠️ 只报前 5 次，避免刷屏（欠载时每块都会带 status）
            log(f'[tts_worker] 播放状态：{status}')
        data = self.ring.read(frames)
        if len(data) < frames:
            data = data + [0.0] * (frames - len(data))
        outdata[:, 0] = data

    def write(self, wav, should_stop=None):
        if self._stream is None:
            raise RuntimeError('播放流未打开（无法播出声音）')
        return self.ring.write(wav, should_stop=should_stop)

    def close(self):
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None


class TTSWorker:
    def __init__(self, device='GPU.0', voice='A', out_device=None, model_dir=None,
                 clone=False, bigvgan_ir=None, precision='f32',
                 out_wav=None, seed=1234, steps=25, cfg_rate=0.7):
        self.device = device
        self.voice = voice
        self.out_device = out_device
        self.model_dir = model_dir
        self.clone_mode = clone
        self.precision = precision   # OV 推理精度（f32 / f16）
        self.out_wav = out_wav       # 落盘模式：按真实时间轴混成一个 wav
        self.seed = seed
        self.steps = steps
        self.cfg_rate = cfg_rate
        self.model = None
        self.ov_rt = None            # OV 合成器（OVSynth 实例；非 torch 路径）
        self.ov_runtime = None       # OVRuntime 实例（供克隆音色/编码器链路用）
        self.bigvgan_ir = bigvgan_ir  # 指定 BigVGAN IR（多相分解版）
        self.conds = {}
        self.player = None
        self._clone_pcm = None       # 克隆说话人的 16 kHz PCM
        self._synth_lock = threading.Lock()
        self._stop = threading.Event()
        self._cancel_lock = threading.Lock()
        self._cancelled: set = set()  # 被主进程丢弃的句子 id
        # ── BabelVox 路线（APP-004 第 2 条）──
        self.engine = None           # BabelVox 实例
        self.speaker_embed = None    # spkonly：预计算的 (1, 1024) 向量
        self.speaker_name = None     # 内置 speaker 名（用内置时有效）
        self.tts_cache_dir = None    # NPU 编译缓存目录
        self.sr = SR                # 当前引擎的采样率
        self._cur_jid = -1          # 当前正在合成的句子 id（供取消检查）
        # ── 落盘模式（--tts-out 回放测试）──
        self._timeline = []          # [(t_start_s, wav)]
        self._t0 = None
        self._jsonl_path = None      # 逐句记录文件（x.tts.jsonl）
        self._jsonl_rows = []

    # -- 模型加载 --------------------------------------------------------
    def load(self):
        t0 = time.perf_counter()

        # 🔴 优先走 **Qwen3-TTS（BabelVox）** 路线（APP-004 第 2 条：
        #   TTS 模型文件随客户包分发 ⇒ 客户机离线也能跑）。
        #   旧引擎（confucius4-tts 的 OVSynth + BigVGAN）只作为回落。
        engine = self._try_load_babelvox()

        if engine is None:
            # 导入 tts_ov 运行时包（如果 P2 移植已完成，优先用 OV 版本）
            ov_rt = self._try_load_ov()

            if ov_rt is None:
                # ── 回落：torch 参考实现 ──
                log('[tts_worker] 使用 torch 参考实现（OpenVINO 版本尚未就绪）')
                import tts_model
                import native_stream as NS
                self.tts_model = tts_model
                self.NS = NS
                self.model = tts_model.load_model(
                    device='cuda' if self.device.upper() in ('GPU.0', 'GPU.1', 'GPU') else self.device,
                    config=self.model_dir)
            else:
                # ── OV 路径：**不 import torch** ──
                self.ov_rt = ov_rt
                self.model = ov_rt          # 合成的调用方按 OV 路径走
                log(f'[tts_worker] OpenVINO 运行时已加载，设备 {self.device}')

            # 音色条件
            self.conds = self._load_conds()
        else:
            # ── BabelVox 路线（spkonly）──
            self.engine = engine
            self.model = engine
            self._setup_babelvox_voice()
            # 🔴 BabelVox 输出 24000 Hz（旧的 22050 播放流会变调/加速）
            #    ⇒ 播放流必须按新采样率**重建**。
            self.sr = TTS_SR
            self._reopen_player(TTS_SR)

        log(f'[tts_worker] 模型加载完成 {time.perf_counter() - t0:.1f}s')
        emit({'kind': 'ready', 'device': self.device, 'voice': self.voice})

    def _reopen_player(self, sr: int):
        """按新的采样率**重建**播放流。

        🔴 为什么要重建：`Player` 在构造时用 `samplerate=sr` 建了
        `sounddevice.OutputStream`，采样率是**流级属性**，之后改不了。
        BabelVox 输出 24000 Hz，而旧引擎是 22050 Hz
        ⇒ 播放流必须跟着引擎走，否则**变调/加速**。
        """
        if self.player is None:
            return
        try:
            self.player.close()
        except Exception:
            pass
        try:
            self.player = Player(device=self.out_device, sr=sr)
            log(f'[tts_worker] 播放流已按 {sr} Hz 重建')
        except Exception as e:
            log(f'[tts_worker] 播放流重建失败（{e}）⇒ 语音输出不可用')
            self.player = None

    def _try_load_babelvox(self):
        """加载 Qwen3-TTS 的 BabelVox 引擎。失败返回 None（回落旧引擎）。

        ⚠️ 这条路径**不 import torch**（babelvox 只用 transformers 的 tokenizer）。
        """
        try:
            import tts_engine
            # 🔴🔴 **必须传 precision**（2026-10-25 修）：
            #   之前**没传** ⇒ GUI 的「精度 f32/f16」下拉**完全无效**
            #   （BabelVox 内部自建 ov.Core，不传任何 property）。
            #   ⇒ 用户在 GUI 里选 f16 也毫无作用（摆设）。
            eng = tts_engine.make_engine(device=self.device,
                                         cache_dir=self.tts_cache_dir,
                                         on_log=log,
                                         precision=self.precision)
            return eng
        except Exception as e:
            log(f'[tts_worker] BabelVox 引擎不可用（{e}）⇒ 回落旧引擎')
            import traceback
            log(traceback.format_exc()[-1000:])
            return None

    def _setup_babelvox_voice(self):
        """准备音色（spkonly 路线）。

        🔴🔴 **只传 `speaker_embed`，禁止传 `ref_text` / `ref_audio`**
        （交接单 §5.1 / TTS-005：babelvox 的 ref_text 路径不是官方 ICL，
        codec 轨道没有 ref_code ⇒ 分布外 prompt ⇒ EOS 不稳）。

        优先级：
        1. 用户指定的内置 speaker（`--voice cindy`）⇒ 零体积；
        2. 预设音色 A 的参考 wav ⇒ 预计算 speaker embedding（只算一次）。
        """
        import tts_engine

        key = (self.voice or 'A').strip()
        if key.lower() in tts_engine.BUILTIN_SPEAKERS:
            self.speaker_embed = None
            self.speaker_name = key.lower()
            log(f'[tts_worker] 使用内置 speaker：{self.speaker_name}')
            return

        wav = tts_engine.preset_voice_path()
        self.speaker_embed = tts_engine.speaker_embedding(self.engine, wav, on_log=log)
        self.speaker_name = 'A'
        if self.speaker_embed is None:
            log('[tts_worker] ⚠️ 没有可用音色 ⇒ 退回内置 speaker cindy')
            self.speaker_name = 'cindy'

    def _try_load_ov(self):
        """尝试加载 OpenVINO 版运行时包（tts_ov）。失败则回落到 torch。

        ⚠️ **OV 路径下绝不 import torch**（C-101 铁律）。

        ⚠️ **本函数返回的是 `OVSynth` 实例**（不是 `OVRuntime`）：
        `OVSynth` 才有整句合成入口 `synth()`。
        （旧实现返回 `OVRuntime` 且调用不存在的 `synth_ov.synth_whole(...)`
          ⇒ OV 路径一跑就崩，会静默回落到 torch，违反「运行时不能依赖 torch」的铁律。）

        ⚠️ **IR 路径必须显式给对**（2026-10-22 修）：
        - `OVRuntime` 默认找 `ir/` 下的 `bigvgan_dynamic.xml`，那份**在 GPU 上算错**
          （SNR ≈ -8 dB，见 runtime.py 注释）⇒ 改用 `ir_dyn/bigvgan_poly.xml`（多相版）；
        - `s2a_estimator` 在 `ir_dyn/` 里叫 `s2a_estimator_f32.xml` / `_f16.xml`；
        - `ir_dir` 指向 `ir_dyn`，`OVRuntime.load()` 再按候选列表兜底。
        """
        try:
            tts_dir = os.environ.get('LIVECAP_TTS_DIR', '').strip()
            candidates = [p for p in [tts_dir, r'C:\Users\Trekker-PTL\confucius4-tts'] if p]
            for d in candidates:
                if os.path.isdir(os.path.join(d, 'tts_ov')):
                    if d not in sys.path:
                        sys.path.insert(0, d)
                    from tts_ov.runtime import OVRuntime, IR_DYN_DIR
                    from tts_ov.synth_ov import OVSynth

                    ptag = 'f16' if self.precision in ('f16', 'fp16') else 'f32'
                    # ── BigVGAN IR（多相版优先）──
                    bg = self.bigvgan_ir
                    if not bg:
                        for cand in ('bigvgan_poly.xml', 'bigvgan_poly_dyn.xml'):
                            p = os.path.join(IR_DYN_DIR, cand)
                            if os.path.exists(p):
                                bg = p
                                break
                    # ── S2A estimator IR（按精度）──
                    s2a = os.path.join(IR_DYN_DIR, f's2a_estimator_{ptag}.xml')
                    if not os.path.exists(s2a):
                        s2a = None

                    rt = OVRuntime(device=self.device, precision=self.precision,
                                   ir_dir=IR_DYN_DIR, verbose=True,
                                   bigvgan_ir=bg, s2a_estimator_ir=s2a)
                    rt.load()
                    synth = OVSynth(rt, device=self.device,
                                    precision=self.precision,
                                    use_torch_rng=True,
                                    bigvgan_ir=bg, s2a_estimator_ir=s2a)
                    # 保留 OVRuntime 引用（克隆音色 / 编码器链路要用）
                    self.ov_runtime = rt
                    log(f'[tts_worker] BigVGAN IR = {os.path.basename(bg) if bg else "（自动）"}'
                        f' / S2A = {os.path.basename(s2a) if s2a else "（自动）"}')
                    return synth
        except Exception as e:
            log(f'[tts_worker] OpenVINO 运行时不可用（{e}），用 torch 回落')
            import traceback
            log(traceback.format_exc()[-1200:])
        return None

    def _load_conds(self):
        """加载音色条件。

        **优先从 npz 加载**（C-101 P4 第 3 条：预设音色的 conditioning 预先算好，
        存为 `live_caption\\voices\\*.npz`，运行时直接加载）。
        这样 App 运行时**完全不需要 torch**（C-101 铁律），也省掉 w2v-BERT +
        CAMPPlus 的前向（w2v-BERT 是 17 层 transformer，CPU 上要几秒）。

        npz 的键（与 `tts_model.py::extract_cond` 对齐）：
            semantic_features  (1, T_feat, 1024)  float32
            style_embedding    (1, 192)          float32
            reference_mel      (1, T_mel, 80)    float32

        没有 npz 时才回落到「用 torch 从 wav 现场算」。
        """
        import numpy as np

        out = {}
        base = os.environ.get('LIVECAP_TTS_DIR', '').strip() or \
            r'C:\Users\Trekker-PTL\confucius4-tts'
        vdir = os.path.join(_HERE, 'voices')

        # ① npz 优先（无需 torch）
        for key, fn in (('A', 'preset_A.npz'), ('B', 'preset_B.npz'),
                        ('clone', 'clone_C.npz')):
            p = os.path.join(vdir, fn)
            if not os.path.exists(p):
                continue
            try:
                z = np.load(p)
                out[key] = {
                    'semantic_features': z['semantic_features'].astype(np.float32),
                    'style_embedding': z['style_embedding'].astype(np.float32),
                    'reference_mel': z['reference_mel'].astype(np.float32),
                }
                log(f'[tts_worker] 音色 {key} 条件就绪（npz，'
                    f'semantic{out[key]["semantic_features"].shape}）')
            except Exception as e:
                log(f'[tts_worker] 音色 {key} npz 加载失败：{e}')

        if out:
            return out

        # ② 回落：现场从 wav 算（需要 torch）
        log('[tts_worker] 没有找到 voices/*.npz，回落到现场计算（需要 torch）')
        vdir_wav = os.path.join(base, 'golden', 'voices')
        presets = {
            'A': os.path.join(vdir_wav, 'preset_A.wav'),
            'B': os.path.join(vdir_wav, 'preset_B_new.wav'),
        }
        for k, p in presets.items():
            if not os.path.exists(p):
                log(f'[tts_worker] 缺少音色文件：{p}')
                continue
            try:
                out[k] = self.tts_model.extract_cond(self.model, p)
                log(f'[tts_worker] 音色 {k} 条件就绪')
            except Exception as e:
                log(f'[tts_worker] 音色 {k} 条件提取失败：{e}')
        # 克隆 C：会议录音里截的干净人声
        clone_wav = os.path.join(vdir_wav, 'clone_C.wav')
        if os.path.exists(clone_wav):
            try:
                out['clone'] = self.tts_model.extract_cond(self.model, clone_wav)
                log('[tts_worker] 克隆音色 C 条件就绪')
            except Exception as e:
                log(f'[tts_worker] 克隆音色 C 条件提取失败：{e}')
        return out

    # -- 合成 ------------------------------------------------------------
    def synth(self, jid: int, text: str):
        """合成一句并播放。

        三条路径：
        - **BabelVox**（`self.engine` 存在）—— Qwen3-TTS，**不碰 torch**；
        - OV 路径（`self.ov_rt` 存在）—— 旧 OVSynth，**不碰 torch**；
        - 否则回落到 torch 的 `native_stream.synth_stream`。

        ⚠️ **落盘模式**（`--out-wav`）：不实时播放，而是按**真实时间轴**
        把每句记到时间轴上，最后混成一个 wav（C-101 P4 第 6 条）。
        """
        import numpy as np

        t_submit = time.perf_counter()
        lang = self._guess_lang(text)
        is_babelvox = self.engine is not None

        if is_babelvox:
            # BabelVox 路线：音色由 speaker_embed / 内置 speaker 提供
            if self.speaker_embed is None and not self.speaker_name:
                # 🔴 2026-10-24 §22：**句子级**错误必须带 `id`
                #   （主进程据此判定「这一句失败」而不是「worker 整体挂了」）
                emit({'kind': 'error', 'message': '没有可用的音色', 'id': jid})
                return
            cond = None
        else:
            key = self.voice
            if key not in self.conds:
                # 🔴 2026-10-24 §22：**句子级**错误必须带 `id`（同上一处）
                emit({'kind': 'error', 'message': f'没有可用的音色：{key}', 'id': jid})
                return
            cond = self.conds[key]

        # 主进程可能已经因为积压超限丢弃了这一句（C-101 P4 第 2 条）
        if self._is_cancelled(jid):
            log(f'[tts_worker] 句子 id={jid} 已被丢弃，跳过合成')
            self._record_jsonl(jid, text, t_submit, dropped=True)
            return

        try:
            with self._synth_lock:
                if self._is_cancelled(jid):
                    return
                self._cur_jid = jid
                if is_babelvox:
                    chunks = self._synth_babelvox(text, lang)
                elif self.ov_rt is not None:
                    chunks = self._synth_ov(text, lang, cond)
                else:
                    chunks = self._synth_torch(text, lang, cond)
        except Exception as e:
            import traceback
            log('[tts_worker] 合成失败：' + traceback.format_exc())
            emit({'kind': 'error', 'message': f'合成失败：{e}', 'id': jid})
            self._record_jsonl(jid, text, t_submit, error=str(e)[:200])
            return

        if self._is_cancelled(jid):
            log(f'[tts_worker] 句子 id={jid} 合成完成但已被丢弃，不播放')
            self._record_jsonl(jid, text, t_submit, dropped=True)
            return

        if not chunks:
            emit({'kind': 'played', 'id': jid})
            self._record_jsonl(jid, text, t_submit)
            return

        # 首包延迟：从收到指令到第一块音频可用
        latency = time.perf_counter() - t_submit
        emit({'kind': 'first_packet', 'latency_s': round(latency, 3), 'id': jid})

        # 播放：把整句的波形一次性塞进环形缓冲
        wav = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        # 🔴🔴 2026-10-25 §30 修：**播放前必须再查一次取消**。
        #   起因（真实竞态）：`synth()` 跑在**独立线程**（`run()` 里
        #   `threading.Thread(target=self.synth, ...)`），而 `cancel` 指令
        #   由**主线程**的 `for line in sys.stdin` 循环接收 ⇒ 二者并发。
        #   ⇒ 主进程在「积压超限」时发 `cancel`，若此刻 `synth` 线程已经
        #      **越过**上面 L537 的取消检查 ⇒ 这句话**照样被合成并播出去**。
        #   ⇒ 主进程已把它记为「丢弃」（`n_dropped += 1`），worker 又回
        #      `played` ⇒ 主进程**双记**（丢了 + 播了）
        #      ⇒ `n_played + n_dropped` 比 `n_submitted` **多 1**。
        #   ⇒ 这里在**真正播放前**补一次检查，**收窄竞态窗口**。
        #   ⚠️ 这只是**缩小**窗口（检查与 write 之间仍有纳秒级缝隙），
        #      **权威判据在主进程**（`tts_service.py` 的 `_dropped_ids` ⇒
        #      收到 `played` 时改记为「已播」）⇒ 两边都要有。
        if self._is_cancelled(jid):
            log(f'[tts_worker] 句子 id={jid} 播放前被丢弃，不播放')
            self._record_jsonl(jid, text, t_submit, dropped=True)
            return
        t_first = time.perf_counter()
        if self.out_wav:
            # ── 落盘模式：按真实时间轴排队，不实时播放 ──
            now = time.perf_counter()
            if self._t0 is None:
                self._t0 = now
            self._timeline.append((now - self._t0, wav.copy()))
        elif self.player is not None:
            try:
                # 🔴🔴 2026-10-25 修：`write()` 已改为**分片推进**（不再要求整句
                #   一次装下）。旧实现在这句 5.76 s 音频上必然超时 ⇒ 一声不响。
                #   这里同时把「取消」做成**逐片可中断** ⇒ 长句播放期间也能被丢弃。
                self.player.write(
                    wav.tolist(),
                    should_stop=lambda: (self._is_cancelled(jid)
                                         or self._stop.is_set()))
            except TimeoutError as e:
                # 旧语义：缓冲写满 ⇒ 播放跟不上（C-101 P4 第 2 条）
                log(f'[tts_worker] 播放缓冲写满，阻塞超时：{e}')
                emit({'kind': 'error', 'message': f'播放缓冲写满：{e}',
                      'id': jid, 'dropped': True})
                self._record_jsonl(jid, text, t_submit, dropped=True)
                return
            except Exception as e:
                # 🔴 带上播放器诊断：回调次数 / 已写 / 已读
                #   0 次回调 = 播放流没跑；有回调但没读 = 设备被占用/静音
                diag = ''
                try:
                    diag = (' [诊断: 回调 %d 次, 已写 %d, 已读 %d, 缓冲 %d/%d]'
                            % (self.player.n_cb,
                               self.player.ring.n_written,
                               self.player.ring.n_read,
                               self.player.ring.level(),
                               self.player.ring._cap))
                except Exception:
                    pass
                log(f'[tts_worker] 播放写入失败：{e}{diag}')
                emit({'kind': 'error', 'message': f'播放写入失败：{e}{diag}',
                      'id': jid})
                self._record_jsonl(jid, text, t_submit,
                                   error=(str(e) + diag)[:300])
                return
        self._record_jsonl(jid, text, t_submit, dur_s=len(wav) / self.sr,
                           t_first=t_first)
        emit({'kind': 'played', 'id': jid,
              'dur_s': round(len(wav) / self.sr, 3),
              'latency_s': round(latency, 3)})

    # -- 逐句记录（C-101 P4 第 6 条：`x.tts.jsonl`）----------------------
    def _record_jsonl(self, jid, text, t_submit, dur_s=None, t_first=None,
                      dropped=False, error=None):
        """记录一句的时间线（供 `x.tts.jsonl` 落盘）。

        每条字段：译文、入队时间、首包时间、播完时间、是否被丢弃。
        """
        row = dict(id=jid, text=text,
                   t_submit=round(t_submit, 4),
                   t_first_packet=(round(t_first - t_submit, 4)
                                   if t_first is not None else None),
                   t_done=round(time.perf_counter(), 4),
                   dur_s=round(dur_s, 3) if dur_s is not None else None,
                   dropped=bool(dropped),
                   error=error)
        self._jsonl_rows.append(row)
        # 实时追加到文件（崩溃也能留下已完成的行）
        if self._jsonl_path:
            try:
                with open(self._jsonl_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
            except Exception:
                pass

    def _flush_timeline(self):
        """落盘模式收尾：把时间轴上的句子混成一个 wav。"""
        if not self.out_wav or not self._timeline:
            return
        import numpy as np
        sr = self.sr                     # 🔴 采样率随引擎走（BabelVox=24000）
        items = list(self._timeline)
        end = max(t + len(w) / sr for t, w in items)
        total = int(end * sr)
        out = np.zeros(total, dtype=np.float32)
        for t, w in items:
            i = int(t * sr)
            j = min(i + len(w), total)
            out[i:j] += w[:j - i]
        try:
            import soundfile as sf
            sf.write(self.out_wav, out, sr)
            log(f'[tts_worker] 已落盘 {self.out_wav}'
                f'（{len(out)/sr:.2f}s，{len(items)} 句，{sr} Hz）')
        except Exception as e:
            log(f'[tts_worker] 落盘失败：{e}')

    def _synth_babelvox(self, text: str, lang: str):
        """BabelVox（Qwen3-TTS）流式合成。返回 list[np.ndarray]（**24000 Hz**）。

        🔴🔴 **音色路线：spkonly** —— 只传 `speaker_embed`，
        **不传 `ref_text` / `ref_audio`**（交接单 §5.1 / TTS-005）。

        ⚠️ **长句要按句切分**（交接单 §6.2）：帧数上限 =
        `max_talker_seq − prefill_len`，逐条不同 ⇒ 超限会被**静默砍断**。
        ⇒ 这里对超长句先切分，逐段合成后拼起来。
        """
        import numpy as np
        import tts_engine

        # 语言映射：babelvox 用全称（'English' / 'Chinese'）
        blang = 'Chinese' if lang.lower().startswith('zh') else 'English'

        # 🔴🔴 TTS-006：**中文数字正则化要在分句之前**
        #   （分句按字数估帧数 ⇒ 若先分句再正则化，估的是「数字」的字数，
        #    而实际读的是「五十二」的 3 个字 ⇒ 帧数上限会被低估）
        #   ⇒ 这里先正则化，再 split_long_text。
        #   ⚠️ `tts_engine.stream()` 里也有一层（幂等 ⇒ 不重复转换），
        #   那层负责覆盖**其它 stream 调用方**。
        if lang.lower().startswith('zh'):
            text = tts_engine.normalize_zh_numbers(text)

        # 长句切分（保守上限 478 帧 ≈ 39.8 s）
        parts = tts_engine.split_long_text(text)
        chunks = []
        for p in parts:
            if self._stop.is_set():
                break
            if self._is_cancelled(self._cur_jid):
                break
            for wav_chunk, sr in tts_engine.stream(
                    self.engine, p, language=blang,
                    speaker_embed=self.speaker_embed,
                    speaker=self.speaker_name if self.speaker_embed is None else None,
                    cancel_event=self._stop):
                w = np.asarray(wav_chunk, dtype=np.float32).reshape(-1)
                chunks.append(w)
                self.sr = int(sr)
        return chunks

    def _synth_ov(self, text: str, lang: str, cond: dict):
        """OV 整句合成（**不依赖 torch**）。返回 list[np.ndarray]（22050 Hz）。

        ⚠️ 入口是 `OVSynth.synth()`（**实例方法**）。
        旧实现调用的 `synth_ov.synth_whole(rt, ...)` **不存在** ⇒ 必崩。
        """
        import numpy as np

        synth = self.ov_rt
        res = synth.synth(
            text, lang, cond,
            seed=self.seed, n_timesteps=self.steps, cfg_rate=self.cfg_rate,
        )
        wav = np.asarray(res['wav'], dtype=np.float32).reshape(-1)
        return [wav]

    def _synth_torch(self, text: str, lang: str, cond: dict):
        """torch 回落路径（流式）。"""
        import numpy as np

        gen = self.NS.make_generator(seed=1234, device='cuda')
        chunks = []
        for c in self.NS.synth_stream(
                self.model, text, lang, cond,
                first_chunk_size=25, chunk_size=50, overlap_tokens=10,
                n_timesteps=25, inference_cfg_rate=0.7, gen=gen):
            chunks.append(c)
            if self._stop.is_set():
                break
        return chunks

    @staticmethod
    def _guess_lang(text: str) -> str:
        """粗判语言：CJK 字符占比高就是 zh，否则 en。"""
        cjk = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
        return 'zh' if cjk * 4 >= len(text) else 'en'

    def _is_cancelled(self, jid) -> bool:
        with self._cancel_lock:
            return jid in self._cancelled

    # -- 主循环 ----------------------------------------------------------
    def run(self):
        # 先起播放流，再加载模型（模型加载要几秒，播放流要先开好）
        try:
            self.player = Player(device=self.out_device, sr=self.sr)
        except Exception as e:
            log(f'[tts_worker] 播放流创建失败：{e}')
            self.player = None

        # 模型加载放到后台线程，主线程立刻开始收指令（避免主进程等太久）
        th = threading.Thread(target=self._safe_load, daemon=True)
        th.start()

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            cmd = msg.get('cmd')
            if cmd == 'quit':
                break
            elif cmd == 'synth':
                jid = msg.get('id')
                text = msg.get('text', '')
                t = threading.Thread(target=self.synth, args=(jid, text), daemon=True)
                t.start()
            elif cmd == 'cancel':
                # 主进程判定积压超限，丢弃这一句（整句为单位，C-101 P4 第 2 条）
                jid = msg.get('id')
                with self._cancel_lock:
                    self._cancelled.add(jid)
                log(f'[tts_worker] 收到丢弃指令 id={jid}')
                emit({'kind': 'dropped', 'id': jid, 'count': 1})
            elif cmd == 'clone':
                # 克隆说话人：更新最近 ≥3 s 的 16 kHz PCM 的条件
                try:
                    import base64
                    import numpy as np
                    pcm = np.frombuffer(base64.b64decode(msg.get('pcm', '')),
                                        dtype=np.float32)
                    self._update_clone(pcm)
                except Exception as e:
                    log(f'[tts_worker] 克隆更新失败：{e}')

        self._stop.set()
        if self.player is not None:
            self.player.close()
        # 落盘模式：把时间轴混成 wav（C-101 P4 第 6 条）
        self._flush_timeline()
        # 逐句记录收尾（补写完整文件，崩溃也能靠增量行保留已完成部分）
        if self._jsonl_path and self._jsonl_rows:
            try:
                with open(self._jsonl_path, 'w', encoding='utf-8') as f:
                    for r in self._jsonl_rows:
                        f.write(json.dumps(r, ensure_ascii=False) + '\n')
            except Exception as e:
                log(f'[tts_worker] jsonl 收尾失败：{e}')

    def _safe_load(self):
        try:
            self.load()
        except Exception as e:
            import traceback
            log('[tts_worker] 加载失败：' + traceback.format_exc())
            emit({'kind': 'error', 'message': f'模型加载失败：{e}'})

    def _update_clone(self, pcm):
        """用最近的 16 kHz PCM 更新克隆音色条件。

        优先走 **npz 路线**（不需要 torch）：
        把 PCM 写到临时 wav → 用已有的 OV 编码器（w2v-BERT / CAMPPlus）算条件
        → 存成 `voices/clone_C.npz`（原子替换）。

        如果 OV 编码器不可用，才回落到 torch 的 `extract_cond`。
        """
        import numpy as np

        if len(pcm) < 16000 * 3:      # 至少 3 s
            return
        pcm = pcm[-16000 * 10:]        # 最多留 10 s

        # ── 路线 1：OV 编码器（无 torch）──
        if getattr(self, 'ov_runtime', None) is not None:
            try:
                cond = self._extract_cond_ov(pcm)
                if cond is not None:
                    out = os.path.join(_HERE, 'voices', 'clone_C.npz')
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    tmp = out + '.tmp.npz'
                    np.savez(tmp, **cond)
                    os.replace(tmp, out)     # 原子替换
                    self.conds['clone'] = cond
                    log(f'[tts_worker] 克隆音色已更新（OV，{len(pcm)/16000:.1f}s）')
                    return
            except Exception as e:
                log(f'[tts_worker] OV 克隆更新失败（回落 torch）：{e}')

        # ── 路线 2：torch ──
        if self.model is None or not hasattr(self, 'tts_model'):
            return
        import soundfile as sf
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            path = f.name
        sf.write(path, pcm, 16000)
        try:
            self.conds['clone'] = self.tts_model.extract_cond(self.model, path)
            log(f'[tts_worker] 克隆音色已更新（torch，{len(pcm)/16000:.1f}s）')
        except Exception as e:
            log(f'[tts_worker] 克隆音色更新失败：{e}')
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def _extract_cond_ov(self, pcm):
        """用 OV 运行时算音色条件（w2v-BERT + CAMPPlus + 参考 mel）。

        返回 dict（numpy），结构与 npz 一致。不可用时返回 None。
        """
        import numpy as np
        rt = getattr(self, 'ov_runtime', None)
        if rt is None:
            return None
        if not (rt.has('w2vbert_17') and rt.has('campplus')):
            return None

        # 16 kHz PCM → 特征
        from tts_ov import features as F
        feats = F.seamless_m4t_features(pcm, 16000)
        if feats.ndim == 3:
            feats = feats[0]
        feats = feats[None, ...].astype(np.float32)      # (1, T_feat, 160)
        mask = np.ones((1, feats.shape[1]), dtype=np.float32)

        sem = rt.w2v(feats, mask)                        # (1, T, 1024)
        sem = np.asarray(sem, dtype=np.float32)

        # CAMPPlus 吃 kaldi fbank
        fb = F.kaldi_fbank(pcm, 16000)                   # (T, 80)
        style = np.asarray(rt.campplus(fb[None, ...].astype(np.float32)),
                            dtype=np.float32)

        # 参考 mel（22.05 kHz）
        wav22 = F.resample(pcm, 16000, 22050)
        mel = F.mel_spectrogram(wav22, 22050)            # (80, T)
        mel = mel.T[None, ...].astype(np.float32)        # (1, T, 80)

        return dict(semantic_features=sem, style_embedding=style,
                    reference_mel=mel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='GPU.0')
    ap.add_argument('--precision', default='f32', choices=['f32', 'f16'])
    ap.add_argument('--voice', default='A',
                    help='音色：A / B / clone，或 babelvox 内置 speaker'
                         '（cindy / lou / phil / steve）')
    ap.add_argument('--out-device', default=None)
    ap.add_argument('--model-dir', default=None)
    ap.add_argument('--clone', action='store_true')
    ap.add_argument('--bigvgan-ir', default=None,
                    help='指定 BigVGAN IR 路径（多相分解版）')
    ap.add_argument('--tts-cache-dir', default=None,
                    help='NPU 编译缓存目录（默认 %%LOCALAPPDATA%%'
                         '\\Confucius4LiveCaption\\tts_npu_cache）')
    ap.add_argument('--out-wav', default=None,
                    help='落盘模式：把语音按**真实时间轴**混成一个 wav'
                         '（C-101 P4 第 6 条的 CLI 回放测试）')
    ap.add_argument('--jsonl', default=None,
                    help='逐句记录文件（默认 <out-wav>.tts.jsonl）')
    ap.add_argument('--seed', type=int, default=1234)
    ap.add_argument('--steps', type=int, default=25)
    ap.add_argument('--cfg-rate', type=float, default=0.7)
    args = ap.parse_args()

    # 🔴🔴 [APP-FIX-20261023] 主线程**预导入**重依赖（numpy / scipy.linalg）
    #
    # 症状：worker 经 `tts_service.TTSService`（`Popen(stdout=PIPE)`）起时
    #      **stdout 一行都不输出**，主进程永远停在 `state=loading`，
    #      drain 超时、0 句播完（见 status/app/STATUS_APP.md §15）。
    #
    # 根因：模型加载跑在**后台线程**（`threading.Thread(target=self._safe_load)`），
    #      而它要 import 的 numpy / scipy 是 **C 扩展** ⇒ import 期间持有
    #      importlib 的**模块级锁**；与此同时主线程正阻塞在
    #      `for line in sys.stdin`（首次迭代会触发 io/textiobuffer 的加载），
    #      同样需要这把锁 ⇒ **互相等待的 import 死锁**。
    #      faulthandler 实测栈：后台线程停在
    #      `numpy/_core/multiarray.py:11 in create_module`。
    #
    # 为什么之前没暴露：`import tts_engine`（纯 python）不触发 C 扩展加载，
    #      单独测 worker 一切正常 ⇒ 只有「Popen + 后台加载 + stdin 阻塞」
    #      三者同时成立才复现。
    #
    # 修法：把重依赖的 import 提到**主线程**、且在**任何后台线程启动之前**。
    #      实测预导入耗时 0.3 s，修复后 worker 9.4 s 正常 emit `ready`。
    try:
        import numpy  # noqa: F401
        import scipy.linalg  # noqa: F401
    except Exception:
        # 预导入失败不致命：退回旧行为（下游仍会在 import 处报错，但有 traceback）
        pass

    w = TTSWorker(device=args.device, voice=args.voice, out_device=args.out_device,
                  model_dir=args.model_dir, clone=args.clone,
                  bigvgan_ir=args.bigvgan_ir, precision=args.precision,
                  out_wav=args.out_wav, seed=args.seed, steps=args.steps,
                  cfg_rate=args.cfg_rate)
    w.tts_cache_dir = args.tts_cache_dir
    # jsonl 路径：`--out-wav` 存在时默认 `<out-wav>.tts.jsonl`
    if args.jsonl:
        w._jsonl_path = args.jsonl
    elif args.out_wav:
        w._jsonl_path = args.out_wav + '.tts.jsonl'
    try:
        w.run()
    except Exception:
        import traceback
        log('[tts_worker] 异常退出：' + traceback.format_exc())
        w._flush_timeline()
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
