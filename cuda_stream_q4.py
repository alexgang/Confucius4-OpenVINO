"""cuda_stream_full.py — C-020: CUDA 流式 跑 61 分钟 (按同一套 VAD 切段)

按 reports/spe_61min_segments.json 切 226 段，每段用 audiocpp_cli --mode streaming
喂 raw PCM 跑一次，与 OV 段对齐。
"""
import os, sys, time, json, subprocess
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf

CUDA_DIR = 'C:/Users/Trekker-PTL/confucius4-r2t2'
CUDA_EXE = f'{CUDA_DIR}/audio.cpp/audiocpp_cli.exe'
CUDA_MODEL = f'{CUDA_DIR}/models/r2t2-q4_k.gguf'
SEG_DIR = 'reports/seg_wavs'
OUT_TXT = 'reports/cuda_q4/spe_cuda_stream.txt'
OUT_JSON = 'reports/cuda_q4/spe_cuda_stream_segments.json'
LOG_DIR = 'reports/cuda_q4/logs_stream'
os.makedirs(os.path.dirname(OUT_TXT), exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


def run_one_session(wav_path, seg_idx):
    audio, sr = sf.read(wav_path)
    assert sr == 16000
    audio = audio.astype(np.float32)
    pcm = (audio * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    cmd = [
        CUDA_EXE,
        '--task', 'asr', '--family', 'confucius4_r2t2',
        '--model', CUDA_MODEL, '--backend', 'cuda',
        '--mode', 'streaming',
        '--audio', '-', '--input-format', 's16le', '--input-rate', '16000', '--input-channels', '1',
        '--session-option', 'chunk_size_ms=640',
        '--session-option', 'unfixed_chunk_num=0',
        '--session-option', 'unfixed_token_num=5',
        '--session-option', 'max_tokens=32',
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, input=pcm, capture_output=True, timeout=300)
    wall = time.perf_counter() - t0
    out = proc.stdout.decode('utf-8', errors='replace')
    err = proc.stderr.decode('utf-8', errors='replace')
    final = ""
    for line in out.splitlines():
        if line.strip().startswith('text_output='):
            final = line.strip()[len('text_output='):]
            break
    with open(f'{LOG_DIR}/seg_{seg_idx:03d}.stdout', 'w', encoding='utf-8') as f:
        f.write(out)
    with open(f'{LOG_DIR}/seg_{seg_idx:03d}.stderr', 'w', encoding='utf-8') as f:
        f.write(err)
    return final, wall


def main():
    # 列出所有 seg wav
    wavs = sorted([f for f in os.listdir(SEG_DIR) if f.endswith('.wav')])
    print(f'[cuda-q4-stream] {len(wavs)} segments', flush=True)
    results = []
    txt_lines = []
    wall_start = time.perf_counter()
    for i, fn in enumerate(wavs):
        seg_idx = int(fn.replace('seg_', '').replace('.wav', ''))
        wav_path = f'{SEG_DIR}/{fn}'
        info = sf.info(wav_path)
        try:
            text, wall = run_one_session(wav_path, seg_idx)
        except subprocess.TimeoutExpired:
            text, wall = '[TIMEOUT]', 300.0
        except Exception as e:
            text, wall = f'[ERROR: {e}]', 0.0
        start_s = i * 16.24  # 占位估算
        end_s = start_s + info.duration
        results.append({
            'seg_idx': seg_idx, 'wall_s': wall,
            'duration_s': info.duration, 'text': text,
        })
        txt_lines.append(f"[{start_s:.1f}-{end_s:.1f}] {text}")
        if (i + 1) % 10 == 0 or i == len(wavs) - 1:
            print(f'[cuda-q4-stream] {i+1}/{len(wavs)} seg={seg_idx:3d} '
                  f'dur={info.duration:.2f}s wall={wall:.2f}s text[:50]={text[:50]!r}',
                  flush=True)
    wall_total = time.perf_counter() - wall_start
    print(f'[cuda-q4-stream] done {len(results)} segs, wall={wall_total:.2f}s', flush=True)
    with open(OUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(txt_lines) + '\n')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'wall_s': wall_total, 'segments': results}, f, ensure_ascii=False, indent=2)
    print(f'[cuda-q4-stream] → {OUT_TXT}', flush=True)


if __name__ == '__main__':
    main()
