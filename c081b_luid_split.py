"""c081b_luid_split.py — C-081#2/#3：按 LUID 拆分重算 GPU compute 占用。

## c080i 错在哪

c080i 的正则 `pid_(\\d+)_.*?engtype_(\\w+)` 把 `luid_..._..._phys_0_eng_N_`
整段丢掉了，只按 PID 过滤。而 Windows 的 `\\GPU Engine(*)` 实例是按
**适配器 LUID** 分开的，NPU 在 WDDM 里注册成一个计算适配器、独占一个
`compute` 引擎实例组。c081a 实测：

    luid 0x00000000_0x00012e84  = Intel iGPU   (GPU.0, DEVICE_LUID 842e010000000000)
    luid 0x00000000_0x000144f0  = Intel NPU    (NPU,    DEVICE_LUID f044010000000000)

`0x00012e84` / `0x000144f0` 正是 reviewer 报的那两个 LUID。所以 c080i 把
NPU 上 decoder 的占用算进了「GPU compute」—— 这就是 NPU 方案 73.7% 比
全 GPU 63.9% 还高的唯一解释（GPU 只跑 encoder，物理上不可能更忙）。

## 本脚本口径

按 (luid, engtype) 分桶累加，**只把 iGPU LUID 的 compute/copy 计入
「GPU compute」**，NPU LUID 单独列为 `npu_compute`。

输出：reports/c081b_luid_split.json
"""
import json
import os
import subprocess
import sys
import threading
import time

os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

SR = 16000
START = 12 * 60
SLICE_SEC = 180
OUT = 'reports/c081b_luid_split.json'
MARKER = 'c081b_luid_split.py'

# c081a 实测（DEVICE_LUID 低位 DWORD）
LUID_IGPU = '0x00012e84'
LUID_NPU = '0x000144f0'

# 实例名形如 pid_11776_luid_0x00000000_0x00012e84_phys_0_eng_5_engtype_compute
PS_SAMPLE = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$s=(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' "
    "-SampleInterval 1 -MaxSamples 1).CounterSamples;"
    # 每条样本内部自匹配：`-match` 会写全局 $Matches，放在 Where-Object 里
    # 再在 ForEach-Object 里读会被后续迭代覆盖，所以逐条 if 里解析。
    "$s|ForEach-Object{"
    "$n=$_.InstanceName; $v=$_.CookedValue;"
    "if($n -match "
    "'pid_(\\d+)_luid_(0x[0-9A-Fa-f]+)_(0x[0-9A-Fa-f]+)_.*?engtype_([A-Za-z0-9]+)'){"
    "'{0}|{1}|{2}|{3}|{4}' -f $Matches[1],$Matches[2],$Matches[3],"
    "$Matches[4],$v}}"
)


def log(*a):
    print(*a, flush=True)


def sample_all():
    try:
        p = subprocess.run(['powershell.exe', '-NoProfile', '-Command', PS_SAMPLE],
                           capture_output=True, timeout=30)
    except Exception:
        return []
    out = []
    for line in (p.stdout or b'').decode('utf-8', 'replace').splitlines():
        p5 = line.strip().split('|')
        if len(p5) == 5:
            try:
                out.append((int(p5[0]), p5[1].lower(), p5[2].lower(),
                            p5[3].lower(), float(p5[4])))
            except ValueError:
                pass
    return out


class Sampler(threading.Thread):
    """按命令行标记收集自己的 PID，按 LUID 分桶累加 compute/copy。"""

    def __init__(self, pattern):
        super().__init__(daemon=True)
        self.pattern = pattern
        self.pids = {os.getpid()}
        self.rows = []          # [(gpu_compute, gpu_copy, npu_compute, npu_copy)]
        self.stop_flag = False

    def _refresh(self):
        ps = ("Get-CimInstance Win32_Process | Where-Object { "
              "$_.CommandLine -like '*%s*' } | ForEach-Object { $_.ProcessId }"
              % self.pattern)
        try:
            p = subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps],
                               capture_output=True, timeout=60)
        except Exception:
            return
        for line in (p.stdout or b'').decode('utf-8', 'replace').splitlines():
            line = line.strip()
            if line.isdigit():
                self.pids.add(int(line))

    def run(self):
        last = 0.0
        while not self.stop_flag:
            if time.time() - last > 10:
                self._refresh()
                last = time.time()
            gc = gcp = nc = ncp = 0.0
            for pid, luid_hi, luid_lo, eng, u in sample_all():
                if pid not in self.pids:
                    continue
                luid = '%s_%s' % (luid_hi, luid_lo)
                if luid.endswith(LUID_IGPU):
                    if eng == 'compute':
                        gc += u
                    elif eng == 'copy':
                        gcp += u
                elif luid.endswith(LUID_NPU):
                    if eng == 'compute':
                        nc += u
                    elif eng == 'copy':
                        ncp += u
            self.rows.append((gc, gcp, nc, ncp))
            time.sleep(1)


def run_child(cfg):
    import numpy as np
    import soundfile as sf
    from seg_stream import SegmentedStreamer

    a, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if a.ndim > 1:
        a = a[:, 0]
    assert sr == SR
    a = a[SR * START:SR * (START + SLICE_SEC)]

    samp = Sampler(MARKER)
    samp.start()

    if cfg == 'A':
        from segment_encoder_backend import SegmentEncoderOVBackend
        be = SegmentEncoderOVBackend(
            encoder_dir='models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-past', device='GPU.0',
            precision='f16')
    else:
        from npu_embeds_backend import NPUEmbedsDecoderBackend
        be = NPUEmbedsDecoderBackend(
            decoder_dir='models/qwen3-lm-int8sym-cleanie-ov')

    for s in (5, 12, 18):
        SegmentedStreamer(
            be, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
            unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
            enable_hallucination_reset=False).run(a[:SR * s])

    t0 = time.perf_counter()
    text, segs = SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False).run(a)
    wall = time.perf_counter() - t0

    time.sleep(3)
    samp.stop_flag = True
    samp.join(timeout=15)

    cols = list(zip(*samp.rows)) if samp.rows else []
    dur = len(a) / SR

    def st(v):
        if not v:
            return {}
        s = sorted(v)
        return {'peak': round(max(v), 1), 'mean': round(float(np.mean(v)), 2),
                'p50': round(float(np.median(v)), 2),
                'p95': round(s[min(int(len(s) * .95), len(s) - 1)], 1)}

    return {'cfg': cfg, 'audio_sec': round(dur, 1), 'wall_s': round(wall, 1),
            'rtf': round(wall / dur, 4), 'n_segs': len(segs),
            'n_samples': len(samp.rows),
            'igu_compute': st(cols[0] if len(cols) > 0 else []),
            'igu_copy': st(cols[1] if len(cols) > 1 else []),
            'npu_compute': st(cols[2] if len(cols) > 2 else []),
            'npu_copy': st(cols[3] if len(cols) > 3 else []),
            'decoder_device': 'GPU.0' if cfg == 'A' else 'NPU',
            'text_head': text[:200]}


def main():
    if '--child' in sys.argv:
        r = run_child(sys.argv[sys.argv.index('--child') + 1])
        print('\n__RESULT__' + json.dumps(r, ensure_ascii=False), flush=True)
        return 0

    res = {}
    for cfg in ('A', 'cleanie'):
        log('\n[c081b] === %s ===' % cfg)
        env = dict(os.environ)
        env.update({'USE_TORCH': '0', 'USE_TF': '0', 'USE_FLAX': '0',
                    'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
        p = subprocess.run([sys.executable, __file__, '--child', cfg],
                           capture_output=True, env=env)
        out = p.stdout.decode('utf-8', 'replace')
        line = [l for l in out.splitlines() if l.startswith('__RESULT__')]
        if not line:
            log('[c081b] %s 失败: %s' % (cfg, out[-1500:]))
            log(p.stderr.decode('utf-8', 'replace')[-1500:])
            res[cfg] = {'error': 'child failed'}
            continue
        res[cfg] = json.loads(line[0][len('__RESULT__'):])
        c = res[cfg]
        log('[c081b] %s RTF=%.4f  iGPU compute mean=%.2f peak=%.1f | '
            'NPU compute mean=%.2f peak=%.1f'
            % (cfg, c['rtf'], c['igu_compute'].get('mean', -1),
               c['igu_compute'].get('peak', -1),
               c['npu_compute'].get('mean', -1),
               c['npu_compute'].get('peak', -1)))

    rep = {
        'note': 'C-081#2：按 LUID 拆分后的 GPU/NPU 占用。同一 3 min 切片、'
                'fresh 进程。A = 全 GPU（生产）；cleanie = enc@iGPU + dec@NPU。',
        'why_c080i_was_wrong':
            'c080i 的正则丢掉了 luid 段，只按 PID 过滤。GPU Engine 实例按'
            '适配器 LUID 分组，NPU 在 WDDM 里也注册成计算适配器并占用'
            'engtype_compute 实例组，于是 NPU 占用被并进「GPU compute」。',
        'luid_map': {'iGPU (GPU.0)': LUID_IGPU, 'NPU': LUID_NPU,
                     'source': 'reports/c081a_luid_map.json'},
        'slice_sec': [START, START + SLICE_SEC],
        'by_cfg': res,
    }
    A, Cn = res.get('A', {}), res.get('cleanie', {})
    if 'error' not in (A, Cn) and A and Cn:
        am, cm = A['igu_compute'].get('mean'), Cn['igu_compute'].get('mean')
        comp = {
            'iGPU_compute_mean_A': am,
            'iGPU_compute_mean_cleanie': cm,
            'iGPU_compute_reduction_pct': round((1 - cm / am) * 100, 1)
            if am else None,
            'iGPU_compute_peak_A': A['igu_compute'].get('peak'),
            'iGPU_compute_peak_cleanie': Cn['igu_compute'].get('peak'),
            'NPU_compute_mean_A': A['npu_compute'].get('mean'),
            'NPU_compute_mean_cleanie': Cn['npu_compute'].get('mean'),
            'rtf_A': A['rtf'], 'rtf_cleanie': Cn['rtf'],
            'rtf_ratio': round(Cn['rtf'] / A['rtf'], 3),
        }
        rep['comparison'] = comp
        log('\n[c081b] === 按 LUID 拆分后的结论 ===')
        log('[c081b] iGPU compute 均值 A=%.2f%% cleanie=%.2f%% → 降幅 %.1f%%'
            % (am, cm, comp['iGPU_compute_reduction_pct']))
        log('[c081b] iGPU compute 峰值 A=%s cleanie=%s'
            % (comp['iGPU_compute_peak_A'], comp['iGPU_compute_peak_cleanie']))
        log('[c081b] NPU compute 均值 A=%s cleanie=%s'
            % (comp['NPU_compute_mean_A'], comp['NPU_compute_mean_cleanie']))

    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
