r"""c088b_resource_usage.py — C-088#3-3：全 NPU 交付形态的资源占用实测

Reviewer 要求（原文）：
> 「补测资源占用：3 分钟切片、全新进程，测全 NPU 的峰值内存（Private Bytes /
>   Working Set）、CPU 平均占用、**按 LUID 拆分的集显和 NPU 占用**（用实测代替
>   「GPU 占用 0」这个推断）。修好 1、2 之后再测。」

为什么必须实测而不是推断
-------------------------
此前 STATUS 里写的「GPU 占用 0」是**推断**的 —— 代码把设备写成 'NPU'，
就断言不会碰 GPU。但 Windows 的 `\GPU Engine(*)` 计数器**同时覆盖集显和 NPU**
（engtype_NPU / engtype_Compute 等），只要有任何一处在 GPU 上跑，计数器就有值。
所以必须按 **LUID** 分桶看两个设备各自的值。

本脚本做的事
------------
1. fresh process（`__main__` 里什么都不继承），3 分钟真实音频（0–180 s）；
2. 起采样线程：250 ms 一次，读
   * psutil：进程 Working Set / Private Bytes / CPU%
   * PDH `\GPU Engine(*)\Utilization Percentage`、`\GPU Adapter Memory(*)\{Dedicated,Shared} Usage`
   * 按 LUID 拆成 集显 / NPU 两桶，分别给峰值、均值、按 engtype 细分；
3. 用 **C-088#3-2 新建的 `npu_delivery_backend`**（不编译 aux 解码器、
   embed 表走独立 npy），并额外记录 init 前后内存差，用来验证修复 1、2 的效果。

输出：reports/c088b_resource_usage.json
"""
import json
import os
import re
import statistics
import sys
import threading
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

SR = 16000
SLICE_SEC = 180          # 3 分钟，Reviewer 指定
OUT = 'reports/c088b_resource_usage.json'

GPU_PATHS = [r'\GPU Engine(*)\Utilization Percentage',
             r'\GPU Adapter Memory(*)\Dedicated Usage',
             r'\GPU Adapter Memory(*)\Shared Usage']

LUID_RE = re.compile(r'luid_0x[0-9A-Fa-f]{8}_(0x[0-9A-Fa-f]{8})')
ENGTYPE_RE = re.compile(r'engtype_([A-Za-z0-9_]+)')


def _luid_of(path):
    m = LUID_RE.search(path)
    return m.group(1).upper().replace('0X', '0x') if m else None


def _engtype_of(path):
    m = ENGTYPE_RE.search(path)
    return m.group(1) if m else 'unknown'


class Sampler(threading.Thread):
    """250 ms 采一次进程内存 + CPU + 按 LUID 分桶的 GPU 计数器。"""

    def __init__(self, self_pid):
        super().__init__(daemon=True)
        self._halt = threading.Event()
        self.rows = []
        self.pid = self_pid
        self.q = None
        self.q_err = None
        try:
            import psutil
            self._psutil = psutil
            self.proc = psutil.Process(self_pid)
            self.proc.cpu_percent(None)          # 预热
        except Exception as e:
            self._psutil = None
            self.proc = None
            self.q_err = f'psutil unavailable: {e}'
        try:
            from win_gpu_perf import GpuQuery
            self.q = GpuQuery(GPU_PATHS)
        except Exception as e:
            self.q = None
            self.q_err = (self.q_err or '') + f' | GpuQuery failed: {e}'

    def run(self):
        t_start = time.perf_counter()
        cpu_t0 = self.proc.cpu_times() if self.proc else None
        # PDH 需要先 collect 一次建立基线，否则第一个值无意义
        while not self._halt.is_set():
            row = {'t': time.perf_counter() - t_start}
            if self.proc is not None:
                try:
                    mi = self.proc.memory_info()
                    # Windows 上 psutil 的 private 就是 Private Bytes（页提交量）
                    row['ws_mb'] = mi.rss / 2 ** 20
                    row['private_mb'] = getattr(mi, 'private', 0) / 2 ** 20
                    # Working Set 里含共享页，OpenVINO .so / 模型权重很大，单独记
                    row['ws_detail'] = {
                        'rss_mb': mi.rss / 2 ** 20,
                        'vms_mb': getattr(mi, 'vms', 0) / 2 ** 20,
                    }
                except Exception:
                    pass
            if self.q is not None:
                try:
                    snap = self.q.sample()
                    row['gpu'] = {k: v for k, v in snap.items()
                                  if f'pid_{self.pid}_' in k}
                except Exception:
                    pass
            self.rows.append(row)
            time.sleep(0.25)
        self.cpu_t0 = cpu_t0

    def stop(self):
        self._halt.set()
        self.join(timeout=5)

    # ── 汇总 ────────────────────────────────────────────────────
    def summary(self):
        out = {'n_samples': len(self.rows)}
        if not self.rows:
            return out
        for key in ('ws_mb', 'private_mb'):
            vals = [r[key] for r in self.rows if key in r]
            if vals:
                out[key] = {
                    'peak': round(max(vals), 1),
                    'mean': round(statistics.fmean(vals), 1),
                    'min': round(min(vals), 1),
                    'first': round(vals[0], 1),
                    'last': round(vals[-1], 1),
                }
        # CPU 平均占用：进程 CPU 时间 / 墙钟
        if self.proc is not None and getattr(self, 'cpu_t0', None):
            try:
                t1 = self.proc.cpu_times()
                cpu_s = ((t1.user - self.cpu_t0.user) +
                         (t1.system - self.cpu_t0.system))
                wall = self.rows[-1]['t']
                out['cpu_avg_pct_of_one_core'] = round(cpu_s / wall * 100, 1)
                out['cpu_avg_cores_used'] = round(cpu_s / wall, 2)
                out['cpu_time_s'] = round(cpu_s, 2)
                out['wall_s'] = round(wall, 2)
                out['n_logical_cpus'] = os.cpu_count()
            except Exception as e:
                out['cpu_err'] = str(e)

        # GPU：按 LUID 分桶
        buckets = {}
        for r in self.rows:
            for path, v in (r.get('gpu') or {}).items():
                luid = _luid_of(path) or 'unknown'
                b = buckets.setdefault(luid, {'util_pct': [], 'ded_mb': [],
                                              'shr_mb': [],
                                              'engtypes': {}})
                if 'Utilization' in path:
                    b['util_pct'].append(v)
                    et = _engtype_of(path)
                    b['engtypes'].setdefault(et, []).append(v)
                elif 'Dedicated Usage' in path:
                    b['ded_mb'].append(v)
                elif 'Shared Usage' in path:
                    b['shr_mb'].append(v)
        gpu = {}
        for luid, b in buckets.items():
            e = {}
            if b['util_pct']:
                e['util_pct'] = {
                    'peak': round(max(b['util_pct']), 2),
                    'mean': round(statistics.fmean(b['util_pct']), 2),
                    'p95': round(sorted(b['util_pct'])[
                        int(len(b['util_pct']) * 0.95)], 2) if b['util_pct'] else 0,
                }
                e['util_by_engtype_peak'] = {
                    k: round(max(v), 2) for k, v in b['engtypes'].items()}
            for k, src in (('ded_mb', 'ded_mb'), ('shared_mb', 'shr_mb')):
                if b[src]:
                    e[k] = {'peak': round(max(b[src]), 1),
                            'mean': round(statistics.fmean(b[src]), 1)}
            e['n_samples'] = len(b['util_pct']) or len(b['ded_mb']) or len(b['shr_mb'])
            gpu[luid] = e
        out['gpu_by_luid'] = gpu
        return out


def main():
    import numpy as np
    import soundfile as sf

    os.makedirs('reports', exist_ok=True)
    rep = {
        'task': 'C-088#3-3',
        'slice_sec': [0, SLICE_SEC],
        'backend': 'npu_delivery_backend.make_delivery_all_npu_backend '
                   '(C-088#3-2 交付形态：无 aux 解码器、embed 走独立 npy)',
        'note': 'Reviewer 要求「用实测代替 GPU 占用 0 的推断」。'
                '本脚本按 LUID 把 \\GPU Engine(*) 拆成集显/NPU 两桶分别报告。',
    }

    def mem_now():
        import psutil
        p = psutil.Process(os.getpid())
        mi = p.memory_info()
        return {'ws_mb': round(mi.rss / 2 ** 20, 1),
                'private_mb': round(getattr(mi, 'private', 0) / 2 ** 20, 1)}

    rep['mem_before_import'] = mem_now()
    t_import0 = time.perf_counter()

    from npu_delivery_backend import make_delivery_all_npu_backend
    rep['mem_after_import'] = mem_now()
    rep['import_s'] = round(time.perf_counter() - t_import0, 2)

    # ── 加载音频（3 分钟）─────────────────────────────────────────
    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    a = audio[:SR * SLICE_SEC]
    assert len(a) == SR * SLICE_SEC, f'audio short: {len(a) / SR:.1f}s'
    rep['audio_sec'] = round(len(a) / SR, 2)

    # ── 加载 backend ────────────────────────────────────────────
    t0 = time.perf_counter()
    be = make_delivery_all_npu_backend()
    rep['backend_init_s'] = round(time.perf_counter() - t0, 1)
    rep['npu_encoder_compile_s'] = getattr(be, 'npu_enc_compile_s', None)
    rep['npu_decoder_compile_s'] = getattr(be, 'npu_compile_s', None)
    rep['aux_decoder_loaded'] = getattr(be, 'aux_decoder_loaded', True)
    rep['dec_infer_is_none'] = getattr(be, 'dec_infer', 'MISSING') is None
    rep['mem_after_backend'] = mem_now()
    rep['mem_cost_of_backend_mb'] = {
        'ws': round(rep['mem_after_backend']['ws_mb'] -
                    rep['mem_before_import']['ws_mb'], 1),
        'private': round(rep['mem_after_backend']['private_mb'] -
                         rep['mem_before_import']['private_mb'], 1),
    }
    print(f'[c088b] backend init {rep["backend_init_s"]}s '
          f'(enc {rep["npu_encoder_compile_s"]}s / dec {rep["npu_decoder_compile_s"]}s), '
          f'aux_decoder_loaded={rep["aux_decoder_loaded"]}', flush=True)
    print(f'[c088b] 加载后 WS={rep["mem_after_backend"]["ws_mb"]} MiB / '
          f'Private={rep["mem_after_backend"]["private_mb"]} MiB', flush=True)

    # 记录设备 LUID，供报告对照
    try:
        import openvino as ov
        c = ov.Core()
        luids = {}
        for d in c.available_devices:
            try:
                luids[d] = c.get_property(d, 'DEVICE_LUID')
            except Exception:
                pass
        rep['ov_devices'] = luids
        rep['ov_npu_name'] = c.get_property('NPU', 'FULL_DEVICE_NAME')
        print(f'[c088b] NPU = {rep["ov_npu_name"]}  LUID = {luids}', flush=True)
    except Exception as e:
        rep['ov_devices_err'] = str(e)

    # ── 预热（不计入采样）────────────────────────────────────────
    from seg_stream import SegmentedStreamer
    warm = a[:SR * 20]
    SegmentedStreamer(
        be, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
        unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
        finish_budget='max64', enable_hallucination_reset=False).run(warm)
    print('[c088b] 预热完成', flush=True)

    # ── 正式跑 3 分钟，边跑边采样 ────────────────────────────────
    smp = Sampler(os.getpid())
    for k in be.probe:
        be.probe[k].clear()
    t0 = time.perf_counter()
    smp.start()
    text, out_segs = SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False).run(a)
    wall = time.perf_counter() - t0
    smp.stop()

    rep['wall_s'] = round(wall, 2)
    rep['rtf'] = round(wall / (len(a) / SR), 4)
    rep['n_segments'] = len(out_segs)
    rep['transcript_head'] = text[:800]
    for k in ('enc_ms', 'prefill_ms', 'decode_ms', 'n_decode', 'prompt_len'):
        v = be.probe[k]
        if v:
            rep[k + '_median'] = round(float(np.median(v)), 1)
            rep[k + '_n'] = len(v)
    rep['resource'] = smp.summary()

    # 便利字段：两个 LUID 的关键值
    g = rep['resource'].get('gpu_by_luid', {})
    flat = {}
    for luid, e in g.items():
        flat[luid] = {
            'util_peak_pct': e.get('util_pct', {}).get('peak'),
            'util_mean_pct': e.get('util_pct', {}).get('mean'),
            'util_p95_pct': e.get('util_pct', {}).get('p95'),
            'by_engtype_peak': e.get('util_by_engtype_peak'),
            'dedicated_peak_mb': e.get('ded_mb', {}).get('peak'),
            'shared_peak_mb': e.get('shared_mb', {}).get('peak'),
        }
    rep['gpu_flat'] = flat

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print('\n' + '=' * 72)
    print(f'RTF={rep["rtf"]}  wall={rep["wall_s"]}s  segs={rep["n_segments"]}')
    r = rep['resource']
    print(f'WS peak={r.get("ws_mb", {}).get("peak")} MiB  '
          f'Private peak={r.get("private_mb", {}).get("peak")} MiB')
    print(f'CPU avg={r.get("cpu_avg_pct_of_one_core")}% of one core '
          f'= {r.get("cpu_avg_cores_used")} cores')
    for luid, v in flat.items():
        print(f'  {luid}: util peak={v["util_peak_pct"]}% '
              f'mean={v["util_mean_pct"]}% p95={v["util_p95_pct"]}% '
              f'ded={v["dedicated_peak_mb"]}MB shr={v["shared_peak_mb"]}MB')
        print(f'      engtype: {v["by_engtype_peak"]}')
    print('=' * 72)
    print('saved ->', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
