"""c080i_gpu_compute.py — C-080#3 要求的「GPU compute 占用对配置 A 的降幅」。

## 为什么必须单独测

`c058l_gpu_guard.py` 记录的是**其它进程**的 GPU 峰值（用来判断 RTF 是否被
污染），它**不记录本作业自己的占用**。所以 guard 的 `rtf_valid: true` 只能
证明「RTF 没被污染」，不能回答「GPU 负载降了多少」。

而这正是 NPU 方案的核心卖点：decoder 从 iGPU 挪到 NPU，iGPU 上只剩
encoder，理应显著降载。

## 口径

- 同一段切片（12–27 min 的前 3 分钟），**fresh 进程**跑两个配置：
  A = 生产（FP16 enc + INT8 dec，**全在 GPU**）、cleanie = enc@GPU + dec@NPU
- 每秒采样一次 `\\GPU Engine(*)\\Utilization Percentage`，
  只统计**本作业 PID** 的 `Compute_0` / `3D` 引擎
- 报峰值与均值，归一化到「音频秒」以便跨配置比较
- ⚠️ 3D 引擎含桌面合成器底噪，只作参考，不作判据

输出：reports/c080i_gpu_compute.json
"""
import json
import os
import re
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
SLICE_SEC = 180          # 3 分钟：够稳，又不至于让作业拖太久
OUT = 'reports/c080i_gpu_compute.json'

PS_SAMPLE = (
    "$s=(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' "
    "-SampleInterval 1 -MaxSamples 1).CounterSamples;"
    "$s|ForEach-Object{"
    "if($_.InstanceName -match 'pid_(\\d+)_.*?engtype_([\\w]+)'){"
    "'{0}|{1}|{2}' -f $Matches[1],$Matches[2],$_.CookedValue}}"
)


def log(*a, **kw):
    print(*a, flush=kw.get('flush', True))


def sample_all():
    try:
        p = subprocess.run(['powershell.exe', '-NoProfile', '-Command', PS_SAMPLE],
                           capture_output=True, timeout=30)
    except Exception:
        return []
    txt = (p.stdout or b'').decode('utf-8', errors='replace')
    out = []
    for line in txt.splitlines():
        parts = line.strip().split('|')
        if len(parts) == 3:
            try:
                out.append((int(parts[0]), parts[1].lower(),
                            float(parts[2])))
            except ValueError:
                pass
    return out


class Sampler(threading.Thread):
    """按命令行标记收集自己的 PID，每秒采一次 compute/3d。"""

    def __init__(self, pattern):
        super().__init__(daemon=True)
        self.pattern = pattern
        self.pids = {os.getpid()}
        self.rows = []
        self.stop_flag = False

    def _refresh(self):
        ps = ("Get-CimInstance Win32_Process | Where-Object { "
              "$_.CommandLine -like '*%s*' } | "
              "ForEach-Object { $_.ProcessId }" % self.pattern)
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
            comp, td = 0.0, 0.0
            for pid, eng, u in sample_all():
                if pid not in self.pids:
                    continue
                if eng.startswith('compute'):
                    comp += u
                elif eng == '3d':
                    td += u
            self.rows.append((comp, td))
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

    samp = Sampler('c080i_gpu_compute.py')
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

    time.sleep(3)          # 让 sampler 收尾
    samp.stop_flag = True
    samp.join(timeout=15)

    comp = [r[0] for r in samp.rows]
    td = [r[1] for r in samp.rows]
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
            'gpu_compute': st(comp), 'gpu_3d': st(td),
            'compute_per_audio_sec': round(
                float(np.mean(comp)) / dur, 3) if comp else None,
            'compute_integrated_pct_sec': round(
                float(np.mean(comp)) / dur, 2) if comp else None,
            'decoder_device': 'GPU.0' if cfg == 'A' else 'NPU',
            'text_head': text[:200]}


def main():
    if '--child' in sys.argv:
        r = run_child(sys.argv[sys.argv.index('--child') + 1])
        print('\n__RESULT__' + json.dumps(r, ensure_ascii=False), flush=True)
        return 0

    res = {}
    for cfg in ('A', 'cleanie'):
        log('\n[c080i] === %s ===' % cfg)
        env = dict(os.environ)
        env.update({'USE_TORCH': '0', 'USE_TF': '0', 'USE_FLAX': '0',
                    'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
        p = subprocess.run([sys.executable, __file__, '--child', cfg],
                           capture_output=True, env=env)
        out = p.stdout.decode('utf-8', 'replace')
        line = [l for l in out.splitlines() if l.startswith('__RESULT__')]
        if not line:
            log('[c080i] %s 失败: %s' % (cfg, out[-1200:]))
            log(p.stderr.decode('utf-8', 'replace')[-1200:])
            res[cfg] = {'error': 'child failed'}
            continue
        res[cfg] = json.loads(line[0][len('__RESULT__'):])
        log('[c080i] %s RTF=%.4f compute mean=%.2f peak=%.1f'
            % (cfg, res[cfg]['rtf'],
               res[cfg]['gpu_compute'].get('mean', -1),
               res[cfg]['gpu_compute'].get('peak', -1)))

    rep = {'note': 'C-080#3 的 GPU compute 降幅。同一 3 min 切片、fresh 进程，'
                   '采样本作业 PID 的 GPU Engine Compute。'
                   'A = 全 GPU（生产）；cleanie = enc@GPU + dec@NPU。',
           'slice_sec': [START, START + SLICE_SEC],
           'why_separate_from_guard': 'c058l_gpu_guard 只记其它进程占用，'
                                      '不记本作业，故无法回答降载幅度。',
           'by_cfg': res}
    if 'A' in res and 'cleanie' in res and 'error' not in (res['A'], res['cleanie']):
        am = res['A']['gpu_compute']['mean']
        cm = res['cleanie']['gpu_compute']['mean']
        rep['comparison'] = {
            'compute_mean_A': am, 'compute_mean_cleanie': cm,
            'reduction_pct': round((1 - cm / am) * 100, 1) if am else None,
            'peak_A': res['A']['gpu_compute']['peak'],
            'peak_cleanie': res['cleanie']['gpu_compute']['peak'],
            'peak_reduction_pct': round(
                (1 - res['cleanie']['gpu_compute']['peak'] /
                 res['A']['gpu_compute']['peak']) * 100, 1)
            if res['A']['gpu_compute']['peak'] else None,
            'rtf_A': res['A']['rtf'], 'rtf_cleanie': res['cleanie']['rtf'],
            'rtf_ratio': round(res['cleanie']['rtf'] / res['A']['rtf'], 3),
        }
        c = rep['comparison']
        log('\n[c080i] GPU compute 均值 A=%.2f%% cleanie=%.2f%% → 降幅 %.1f%%'
            % (am, cm, c['reduction_pct']))
        log('[c080i] 峰值 A=%.1f%% cleanie=%.1f%% → 降幅 %.1f%%'
            % (c['peak_A'], c['peak_cleanie'], c['peak_reduction_pct']))
        log('[c080i] RTF A=%.4f cleanie=%.4f（比 %.2f）'
            % (c['rtf_A'], c['rtf_cleanie'], c['rtf_ratio']))

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
