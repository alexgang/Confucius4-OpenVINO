r"""c089e_cpu_attribution.py — C-090#3：定位全 NPU 平均 6.1 个 CPU 核花在哪

Reviewer 原文：
> 「C-090 第 3 条 …… 全 NPU 平均要占 6.1 个 CPU 核。对一台只有 CPU + NPU 的台式机
> 来说，这个开销不小。C-089 做完后用 3 分钟切片定位一下 CPU 花在哪里，比如 mel
> 特征和 VAD、拼 `inputs_embeds` 的 numpy 拷贝、NPU 插件的主机侧线程。
> **只做测量，不用优化。**」

## 方法

用 `py-spy` 采样主进程 + NPU 插件线程的原生栈，按「栈顶属于哪个阶段」归类。
`py-spy` 抓不到 NPU 插件的 C++ 栈，所以同时用 psutil 记录**线程级** CPU 时间
作为交叉验证：线程越多、平均占用越高，说明主机侧并发越大。

阶段分类（按栈里的函数名匹配，优先级从上到下）：
* `mel`   —— mel 特征（fbank / STFT）
* `vad`   —— VAD / 能量检测
* `embeds`—— 拼 `inputs_embeds` 的 numpy 拷贝 / embed 表查表
* `ov`    —— OpenVINO / NPUW 插件的 infer 调用（含主机侧预处理）
* `decode`—— 贪心解码循环（tokenizer、argmax）
* `other` —— 其它（流控、resample 等）

## 用法

    python c089e_cpu_attribution.py                 # 3 分钟切片
    python c089e_cpu_attribution.py --seconds 180
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections import defaultdict

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, '.')

SR = 16000
SECONDS = 180.0
# 复用 C-088b 同样的 3 分钟切片口径，保证可与 6.1 核的数字直接对比
SLICE_LO, SLICE_HI = 0.0, 180.0
OUT = 'reports/c089_int4/cpu_attribution.json'

# 栈匹配规则：(阶段, [子串...])，按顺序第一个命中
RULES = [
    ('mel', ['fbank', 'mel', 'stft', 'spectrogram', 'torchaudio']),
    ('vad', ['vad', 'energy', 'silence', 'detect_speech']),
    ('embeds', ['inputs_embeds', 'embed_table', 'ascontiguousarray',
                'take_along_axis', '_load_embed_table', 'np.take']),
    ('decode', ['greedy_decode', 'argmax', 'tokenize', 'decode_ids',
                'logits', 'sample']),
    ('ov', ['infer_request', 'infer(', 'compiled_model', 'npu', 'openvino',
            'remote', 'sync_request', 'wait']),
]


def classify(frame_names):
    names = '\n'.join(frame_names).lower()
    for stage, keys in RULES:
        if any(k.lower() in names for k in keys):
            return stage
    return 'other'


def thread_cpu_snapshot():
    """线程级 CPU 时间（秒），进程内每线程累计值。"""
    import psutil
    p = psutil.Process()
    t = psutil.Process().cpu_times()
    per = {}
    try:
        for tid, tinfo in p.cpu_times(per_thread=True).items():
            per[tid] = tinfo.user + tinfo.system
    except Exception:
        return {}, t.user + t.system
    return per, t.user + t.system


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=SECONDS)
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()

    import numpy as np
    import soundfile as sf
    import psutil
    from npu_delivery_backend import make_delivery_all_npu_backend
    from seg_stream import SegmentedStreamer

    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    i0, i1 = int(SR * SLICE_LO), int(SR * SLICE_HI)
    clip = audio[i0:i1]
    print(f'[c089e] 切片 {SLICE_LO:.0f}–{SLICE_HI:.0f} s '
          f'({len(clip)/SR:.1f} s 音频)', flush=True)

    be = make_delivery_all_npu_backend(
        encoder_dir='models/ov-encoder-segment-reviewer',
        decoder_dir='models/qwen3-lm-int8sym-cleanie-ov')
    print(f'[c089e] backend init 完成（enc {be.npu_enc_compile_s}s / '
          f'dec {be.npu_compile_s}s）', flush=True)

    # 预热（不计入）
    SegmentedStreamer(
        be, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
        unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
        finish_budget='max64', enable_hallucination_reset=False
    ).run(clip[:SR * 15])

    proc = psutil.Process()
    samples = []          # (wall, per_thread_cpu, total_cpu)
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            per, tot = thread_cpu_snapshot()
            samples.append((time.perf_counter(), per, tot))
            time.sleep(0.25)

    # py-spy dump 到临时文件，避免阻塞
    spy_dumps = []
    spy_dir = os.path.abspath('_c089e_spy')
    os.makedirs(spy_dir, exist_ok=True)

    def spy_loop(n_max):
        i = 0
        while not stop.is_set() and i < n_max:
            dst = os.path.join(spy_dir, f'dump_{i:04d}.txt')
            r = subprocess.run(
                ['py-spy', 'dump', '--pid', str(os.getpid()),
                 '--locals', '--nonblocking'],
                capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                spy_dumps.append(r.stdout)
                i += 1
            time.sleep(0.5)

    try:
        import shutil
        have_spy = shutil.which('py-spy') is not None
    except Exception:
        have_spy = False
    print(f'[c089e] py-spy: {"可用" if have_spy else "未安装 —— 只做线程级统计"}',
          flush=True)

    th_s = threading.Thread(target=sampler, daemon=True)
    th_s.start()
    if have_spy:
        threading.Thread(target=spy_loop, args=(4000,), daemon=True).start()

    print(f'[c089e] 开始采样 {a.seconds:.0f} s …', flush=True)
    t0 = time.perf_counter()
    it = {'n': 0}

    orig = be.greedy_decode_with_prefix

    def traced(*aa, **kw):
        r = orig(*aa, **kw)
        it['n'] += 1
        if it['n'] % 10 == 0:
            el = time.perf_counter() - t0
            print(f'  [{el:6.1f}s] 已完成 {it["n"]} 段', flush=True)
        return r
    be.greedy_decode_with_prefix = traced

    SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False).run(clip)
    wall = time.perf_counter() - t0
    stop.set()
    time.sleep(0.6)
    th_s.join(timeout=3)

    # ── 线程级统计 ──────────────────────────────────────────────
    cpu_by_thread = defaultdict(float)
    t_prev = samples[0][1] if samples else {}
    wall_prev = samples[0][0] if samples else 0.0
    thread_wall = defaultdict(float)
    for t_w, per, tot in samples[1:]:
        dw = t_w - wall_prev
        for tid, v in per.items():
            d = v - t_prev.get(tid, 0.0)
            if d > 0:
                cpu_by_thread[tid] += d
                thread_wall[tid] += dw
        wall_prev = t_w
        t_prev = per

    tot_cpu = sum(cpu_by_thread.values())
    print(f'\n[c089e] 墙钟 {wall:.1f} s，CPU 线程合计 {tot_cpu:.1f} s '
          f'= {tot_cpu/wall:.2f} 核', flush=True)

    # ── 栈归类 ────────────────────────────────────────────────
    stage_count = defaultdict(int)
    stage_names = defaultdict(list)
    for dump in spy_dumps:
        frames = [l.strip() for l in dump.splitlines()
                  if l.strip() and 'Thread' not in l and 'idle' not in l]
        st = classify(frames)
        stage_count[st] += 1
        if len(stage_names[st]) < 6:
            stage_names[st].append(frames[:4])
    n_dumps = len(spy_dumps) or 1

    # ── 进程总占用（交叉验证 6.1 核）────────────────────────────
    t0c = proc.cpu_times()
    tot_proc = t0c.user + t0c.system

    rep = {
        'slice_sec': [SLICE_LO, SLICE_HI],
        'audio_s': len(clip) / SR,
        'wall_s': round(wall, 2),
        'rtf': round(wall / (len(clip) / SR), 4),
        'n_segments': it['n'],
        'cpu': {
            'thread_total_cpu_s': round(tot_cpu, 2),
            'avg_cores': round(tot_cpu / wall, 2),
            'process_total_cpu_s': round(tot_proc, 2),
            'process_avg_cores': round(tot_proc / wall, 2),
            'n_threads_active': len(cpu_by_thread),
            'samples': len(samples),
        },
        'by_thread': {str(tid): {'cpu_s': round(v, 2),
                                 'share_pct': round(100.0 * v / tot_cpu, 1),
                                 'avg_cores': round(
                                     v / max(thread_wall[tid], 1e-9), 3)}
                      for tid, v in sorted(cpu_by_thread.items(),
                                            key=lambda kv: -kv[1])[:20]},
        'stack_sampling': {
            'py_spy_available': have_spy,
            'n_dumps': len(spy_dumps),
            'by_stage_pct': {k: round(100.0 * v / n_dumps, 1)
                             for k, v in stage_count.items()},
            'example_stacks': {k: v for k, v in stage_names.items()},
        },
        'note': 'C-090#3 只做测量，不做优化。avg_cores 应与 C-088b 的 6.10 '
                '核（同为 3 分钟切片）在同一量级。',
    }
    json.dump(rep, open(a.out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print('\n按栈归类占比（%d 次采样）：' % len(spy_dumps))
    for k, v in sorted(rep['stack_sampling']['by_stage_pct'].items(),
                       key=lambda kv: -kv[1]):
        print('  %-8s %5.1f%%' % (k, v))
    print('\nCPU 占比最高的线程：')
    for tid, d in list(rep['by_thread'].items())[:8]:
        print('  tid %-8s cpu %7.2f s (%4.1f%%)  ≈ %.2f 核'
              % (tid, d['cpu_s'], d['share_pct'], d['avg_cores']))
    print('\nsaved ->', a.out)


if __name__ == '__main__':
    sys.exit(main())
