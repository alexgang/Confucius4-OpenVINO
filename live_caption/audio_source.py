r"""audio_source.py — 实时字幕 App 的统一音频输入层（三种音源）

## 为什么要单独一个模块

实时字幕要处理三种完全不同的音频来源，它们的采集语义差别很大：

  1. **麦克风**（系统默认 / 指定设备）—— 实时流，设备采样率由驱动决定。
  2. **系统声音**（WASAPI loopback）—— 实时流，采集的是「正在播放的输出设备」
     的音频混音。没有声音时设备不产生帧，必须自己补静音，否则流水线会
     因为「等不到数据」而卡住甚至误判流结束。
  3. **音频文件**（用户上传）—— 有限长度，可以按实时速度回放（保持
     「实时字幕」的观感），也可以全速跑（跑批更���）。

三者的共同点是：都要吐出 **16 kHz 单声道 float32** 的 PCM 块。
本模块把差异全部封在下面，上层（Session / GUI / CLI）只认这一种格式。

## 采样率与声道

采集端可能是 44.1 kHz / 48 kHz，声道可能是 1 / 2 / 4。
统一策略：

  * 声道：取第 0 声道（系统回环的立体声混音里第 0 声道就是左声道，
    人声语音内容在左右声道是相同的，丢一路不丢信息）。
  * 采样率：统一重采样到 16 kHz。
    - 麦克风走 numpy 线性插值（沿用旧实现，够用且零依赖）。
    - loopback 走 WASAPI 自身的 SRC 重采样引擎（由 soundcard 传入
      16 kHz 给设备），比线性插值干净。
    - 文件走 soundfile / PyAV 自带的解码器重采样。

## 依赖

  * 麦克风 / 文件：``sounddevice`` / ``soundfile``（项目 venv 已装）
  * 系统声音：``soundcard``（纯 cffi 实现的 WASAPI，无需 ffmpeg）
  * 额外格式（m4a / mp4 / mov 等 soundfile 不支持的容器）：``av``（PyAV）

``soundcard`` 只在「系统声音」这一路用到；没装也不影响其它两路。
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
from typing import List, Optional, Tuple

import numpy as np

SR = 16000                 # 统一输出采样率
BLOCK_MS = 100             # 每块时长（毫秒）


# ── 工具 ────────────────────────────────────────────────────────────────
def resample_to_16k(x: np.ndarray, src_sr: int) -> np.ndarray:
    """线性插值重采样到 16 kHz（麦克风 / 文件回放用）。"""
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    if src_sr == SR or x.size == 0:
        return x
    n = int(round(len(x) * SR / src_sr))
    if n <= 0:
        return np.zeros(0, np.float32)
    idx = np.linspace(0, len(x) - 1, n)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


def _rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(float(np.mean(x.astype(np.float64) ** 2)) + 1e-12))


def _to_mono(x: np.ndarray) -> np.ndarray:
    """任意形状 → 单声道 float32（取第 0 声道）。"""
    a = np.asarray(x, dtype=np.float32)
    if a.ndim > 1:
        a = a[:, 0] if a.shape[1] >= 1 else a.reshape(-1)
    return a.reshape(-1).astype(np.float32, copy=False)


# ── 设备枚举 ────────────────────────────────────────────────────────────
def list_input_devices() -> List[Tuple[int, str]]:
    """麦克风列表 [(索引, 显示名)]，只保留 MME / WASAPI（免驱动的那些）。"""
    try:
        import sounddevice as sd
    except Exception:
        return []
    try:
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


def list_output_devices() -> List[Tuple[str, str]]:
    """可作「系统声音」来源的输出设备 [(WASAPI id, 显示名)]。

    用 soundcard 枚举 render 端点：只有这些设备能被 WASAPI loopback 采集。
    """
    try:
        import soundcard as sc
    except Exception:
        return []
    try:
        with _com_apartment():
            out = []
            for s in sc.all_speakers():
                out.append((s.id, f'{s.name}（{s.channels} 声道）'))
            return out
    except Exception:
        return []


def default_output_device_id() -> Optional[str]:
    """系统默认输出设备的 WASAPI id。"""
    try:
        import soundcard as sc
        with _com_apartment():
            return sc.default_speaker().id
    except Exception:
        return None


def soundcard_available() -> bool:
    try:
        import soundcard  # noqa: F401
        return True
    except Exception:
        return False


# ── COM 线程公寓 ────────────────────────────────────────────────────────
# soundcard 在 **import 时** 就在「当时的线程」初始化 COM（CoInitializeEx MTA），
# 而 WASAPI 的设备枚举 / 采集发生在不同线程里。COM 规则是「每个线程都要自己
# 初始化」，跨线程直接用 IAudioClient 指针是不安全的。
#
# 但顺序很讲究：soundcard 自己的 _COMLibrary 在 CoInitializeEx 返回 S_FALSE(1)
# 时会直接抛异常（它只容忍 RPC_E_CHANGED_MODE），而 S_FALSE 恰好意味着
# 「本线程已经用同样的模型初始化过了」。所以：
#
#   * soundcard 尚未 import → 让它在本线程 import，由它初始化 COM，我们不再插手；
#   * soundcard 已在别处 import → 本线程得自己 CoInitializeEx，并在结束时配对
#     CoUninitialize。
#
# 记错这个顺序的表现是：系统声音模式一启动就报 "Error 0x100000001"。
def _co_prepare_thread() -> bool:
    """准备当前线程的 COM 公寓。返回 True = 需要我们自己做 CoUninitialize。"""
    had = 'soundcard' in sys.modules
    try:
        import soundcard  # noqa: F401
    except Exception:
        pass
    if not had:
        # soundcard 刚在本线程完成 import，它自己初始化了 COM —— 我们不能再来一次
        return False
    return _co_init_thread()


def _co_init_thread() -> bool:
    try:
        import ctypes
        COINIT_MULTITHREADED = 0x0
        S_OK, S_FALSE = 0, 1
        RPC_E_CHANGED_MODE = 0x80010106
        hr = ctypes.windll.ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        if hr == S_OK:
            return True            # 我们自己初始化的，结束时必须配对 CoUninitialize
        if hr == S_FALSE:
            return False           # 本线程已有同模型的公寓，别人负责反初始化
        if hr == RPC_E_CHANGED_MODE:
            return False           # 已是别的公寓（STA），直接用即可
        return False
    except Exception:
        return False


def _co_uninit_thread():
    try:
        import ctypes
        ctypes.windll.ole32.CoUninitialize()
    except Exception:
        pass


class _com_apartment:
    """上下文管理器：保证当前线程有一个可用的 COM 公寓。

    用于「在任意线程枚举 WASAPI 设备」的场景（GUI 主线程、采集线程都用到）。
    """

    def __enter__(self):
        self._own = _co_prepare_thread()
        return self

    def __exit__(self, *exc):
        if self._own:
            _co_uninit_thread()
        return False


# ── 音源基类 ────────────────────────────────────────────────────────────
class BaseAudioSource(threading.Thread):
    """后台线程把 (pcm, 采集时刻) 送进队列。

    约定：

    * ``pcm`` 一定是单声道 float32，采样率由 ``src_sr`` 声明；
      下游（Session）统一重采样到 16 kHz。
      麦克风走设备原生率（重采样放在下游，避免在 PortAudio 实时回调里做插值）；
      回环与文件两路本身就直接产出 16 kHz。
    * 队列读到 ``None`` 表示流结束（正常结束或出错，出错信息在 ``err``）。
    """

    def __init__(self, out_q: 'queue.Queue'):
        super().__init__(daemon=True)
        self.out_q = out_q
        self.stop_evt = threading.Event()
        self.src_sr = SR
        self.err: Optional[Exception] = None
        self.level = 0.0                 # 最近一块的 RMS 电平
        self.name_used = ''              # 实际使用的设备 / 文件名
        self.total_s = 0.0               # 已送出的音频时长（秒）

    # 子类实现 run()
    def run(self):
        try:
            self._run()
        except Exception as e:            # noqa: BLE001
            self.err = e
        finally:
            self.out_q.put(None)

    def _run(self):                      # pragma: no cover - 子类覆盖
        raise NotImplementedError

    def _emit(self, pcm: np.ndarray, t_cap: float):
        """把一块 PCM 推进队列。"""
        if pcm.size == 0:
            return
        self.level = _rms(pcm)
        self.total_s += len(pcm) / self.src_sr
        self.out_q.put((pcm, t_cap))

    def stop(self):
        self.stop_evt.set()


# ── 1. 麦克风 ───────────────────────────────────────────────────────────
class MicSource(BaseAudioSource):
    """系统麦克风（sounddevice / PortAudio）。

    ``device`` 为 None 时用系统默认输入设备。
    """

    def __init__(self, out_q, device: Optional[int] = None):
        super().__init__(out_q)
        self.device = device

    def _run(self):
        import sounddevice as sd
        try:
            sd.check_input_settings(device=self.device, samplerate=SR, channels=1)
            self.src_sr = SR
        except Exception:
            self.src_sr = int(sd.query_devices(self.device, 'input')['default_samplerate'])
        dev = sd.query_devices(self.device, 'input') if self.device is not None \
            else sd.query_devices(kind='input')
        self.name_used = dev['name']

        def cb(indata, frames, _t, status):
            if self.stop_evt.is_set():
                raise sd.CallbackStop()
            x = np.asarray(indata, dtype=np.float32).reshape(-1)
            self.out_q.put((x.copy(), time.perf_counter()))

        with sd.InputStream(samplerate=self.src_sr, channels=1, dtype='float32',
                            blocksize=int(self.src_sr * BLOCK_MS / 1000),
                            device=self.device, callback=cb):
            while not self.stop_evt.is_set():
                time.sleep(0.05)


# ── 2. 系统声音（WASAPI loopback）──────────────────────────────────────
class SystemAudioSource(BaseAudioSource):
    """系统输出设备的实时混音（WASAPI loopback）。

    采集的是「正在播放的输出设备」——浏览器视频、播放器、会议软件、
    任何在系统里发声的程序。想给会议/视频做字幕时用它，而不是麦克风
    （麦克风会把对方和本地声音一起录进来，质量也差）。

    实现：``soundcard``（纯 cffi 封装 WASAPI，无需 ffmpeg）。
    向设备请求 16 kHz，由 Windows 的 SRC（重采样器）负责降采样，
    比自己插值干净。

    静音处理：输出设备没有声音时 WASAPI **不产生任何帧**。若直接等，
    流水线会一直空转。这里用「超时补静音」的策略：等不到帧就按块长
    补零并继续，这样下游的 VAD / 切段逻辑能正常看到「一段时间的静音」。
    """

    def __init__(self, out_q, device_id: Optional[str] = None):
        super().__init__(out_q)
        self.device_id = device_id
        self.src_sr = SR                 # 直接向设备要 16 kHz
        self._loopback = None
        self._rec = None
        self._pending = np.zeros(0, np.float32)

    def _resolve(self):
        """找到要采集的 loopback 设备。"""
        import soundcard as sc
        if self.device_id:
            mic = sc.get_microphone(self.device_id, include_loopback=True)
        else:
            mic = sc.get_microphone(sc.default_speaker().id, include_loopback=True)
        if not getattr(mic, 'isloopback', False):
            raise RuntimeError('该设备不支持回环采集（WASAPI loopback）')
        self._loopback = mic
        self.name_used = mic.name
        return mic

    def _run(self):
        step = int(SR * BLOCK_MS / 1000)
        # COM 公寓准备：soundcard 若已在别处 import，本线程得自己初始化；
        # 若首次 import，则由 soundcard 自己初始化（见 _co_prepare_thread 注释）。
        need_uninit = _co_prepare_thread()
        try:
            mic = self._resolve()
            with mic.recorder(samplerate=SR, channels=min(2, max(1, mic.channels)),
                              blocksize=step) as rec:
                self._rec = rec
                while not self.stop_evt.is_set():
                    try:
                        data = rec.record(numframes=step)
                    except Exception:
                        # 设备被占用 / 静音超时：补一块静音后重试
                        if self.stop_evt.is_set():
                            break
                        self._emit(np.zeros(step, np.float32), time.perf_counter())
                        time.sleep(0.02)
                        continue
                    if data is None or len(data) == 0:
                        # 静音设备：补零，保持时间轴连续
                        self._emit(np.zeros(step, np.float32), time.perf_counter())
                        continue
                    pcm = resample_to_16k(_to_mono(data), SR)
                    if pcm.size == 0:
                        continue
                    self._emit(pcm, time.perf_counter())
        finally:
            if need_uninit:
                _co_uninit_thread()


# ── 3. 音频文件 ────────────────────────────────────────────────────────
class FileSource(BaseAudioSource):
    """用户上传的音频文件，按实时速度回放。

    * ``speed=1.0`` —— 与播放速度一致（默认），保持「实时字幕」观感。
    * ``speed=0``   —— 全速跑（不等实时），适合跑批 / 回归测试。
    * ``loop``      —— 播完自动从头再来（用于压测长音频）。

    解码：
      1. 先试 ``soundfile``（WAV / FLAC / OGG / MP3 等，libsndfile 1.2.2）。
      2. 失败再用 ``av``（PyAV）——覆盖 m4a / mp4 / mov / aac 等
         libsndfile 不支持的容器，PyAV 自带解码 + 重采样。
    """

    def __init__(self, out_q, path: str, speed: float = 1.0, loop: bool = False):
        super().__init__(out_q)
        self.path = path
        self.speed = float(speed)
        self.loop = bool(loop)
        self.name_used = os.path.basename(path)

    # -- 解码 ------------------------------------------------------------
    def _load_soundfile(self):
        import soundfile as sf
        audio, sr = sf.read(self.path, dtype='float32', always_2d=True)
        return _to_mono(audio), int(sr), 'soundfile'

    def _load_pyav(self):
        """PyAV 解码路径：覆盖 m4a / mp4 / mov / aac 等 libsndfile 不支持的容器。

        走 ``AudioResampler`` 统一到 **单声道 float32**，而不是直接读
        ``frame.to_ndarray()`` —— 后者在多声道时返回的是打包布局（packed），
        形状和声道数对不上，立体声会被当成双倍长的单声道。
        """
        import av
        from av.audio.resampler import AudioResampler
        container = av.open(self.path)
        try:
            stream = container.streams.audio[0]
            rate = int(stream.codec_context.sample_rate)
            resampler = AudioResampler(format='fltp', layout='mono', rate=rate)
            chunks = []
            for frame in container.decode(stream):
                for out in resampler.resample(frame):
                    arr = out.to_ndarray()
                    if arr.ndim > 1:
                        arr = arr[0]
                    chunks.append(arr.astype(np.float32, copy=False).reshape(-1))
            # 冲刷重采样器内部缓冲的尾帧
            for out in resampler.resample(None):
                arr = out.to_ndarray()
                if arr.ndim > 1:
                    arr = arr[0]
                chunks.append(arr.astype(np.float32, copy=False).reshape(-1))
            if not chunks:
                raise RuntimeError('文件里没有可解码的音频轨')
            return np.concatenate(chunks), rate, 'pyav'
        finally:
            container.close()

    def load(self):
        """读出整段音频 → (float32 单声道, 采样率, 解码器名)。"""
        if not os.path.isfile(self.path):
            raise FileNotFoundError(self.path)
        try:
            return self._load_soundfile()
        except Exception as e:
            sf_err = e
        try:
            return self._load_pyav()
        except Exception as av_err:
            raise RuntimeError(
                f'无法解码该音频文件（soundfile: {sf_err}；PyAV: {av_err}）') from av_err

    # -- 回放 ------------------------------------------------------------
    def _run(self):
        audio, sr, decoder = self.load()
        self.src_sr = sr
        audio = resample_to_16k(audio, sr)
        if audio.size == 0:
            raise RuntimeError('音频文件为空')
        self.name_used = f'{os.path.basename(self.path)}（{decoder}）'

        step = int(SR * BLOCK_MS / 1000)
        do_loop = self.loop
        while not self.stop_evt.is_set():
            t_next = time.perf_counter()
            for i in range(0, len(audio), step):
                if self.stop_evt.is_set():
                    return
                blk = audio[i:i + step]
                if len(blk) < step:
                    blk = np.pad(blk, (0, step - len(blk)))
                self._emit(blk.copy(), time.perf_counter())
                if self.speed > 0:
                    t_next += (BLOCK_MS / 1000.0) / self.speed
                    delay = t_next - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
            if not do_loop:
                break


# ── 工厂 ────────────────────────────────────────────────────────────────
SOURCES = {
    'mic': '麦克风',
    'system': '系统声音',
    'file': '音频文件',
}


def make_source(kind: str, out_q, *, device=None, system_device=None,
                file=None, speed=1.0, loop=False) -> BaseAudioSource:
    """按类型造一个音源。

    kind: ``mic`` | ``system`` | ``file``
    """
    kind = (kind or 'mic').lower()
    if kind == 'mic':
        return MicSource(out_q, device=device)
    if kind == 'system':
        return SystemAudioSource(out_q, device_id=system_device)
    if kind == 'file':
        if not file:
            raise ValueError('音频文件模式需要指定文件')
        return FileSource(out_q, file, speed=speed, loop=loop)
    raise ValueError(f'未知音源类型：{kind}')
