"""cuda_diagnose.py — C-020: CUDA (audio.cpp) 流式/离线诊断

跑 audio.cpp CUDA 端：
  - cfg 6: 流式 (A/B 各一次)
  - cfg 7: 离线 (A/B 各一次)

音频通过 stdin raw PCM 喂给流式 (--mode streaming --audio -)，
离线通过 --batch-audio-dir 跑每个段。
"""
import os, sys, time, json, subprocess, wave
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf

CUDA_DIR = 'C:/Users/Trekker-PTL/confucius4-r2t2'
CUDA_EXE = f'{CUDA_DIR}/audio.cpp/audiocpp_cli.exe'
CUDA_MODEL = f'{CUDA_DIR}/models/r2t2-q8_0.gguf'
CUDA_BACKEND = 'cuda'
CUDA_FAMILY = 'confucius4_r2t2'
AUDIO_A = 'reports/c019_A.wav'
AUDIO_B = 'reports/c019_B.wav'
OUT_DIR = 'reports/c019_diag'
os.makedirs(OUT_DIR, exist_ok=True)


def _decode_streaming_text(stdout: str) -> str:
    """从 audiocpp_cli 流式输出解析最终文本。"""
    final = ""
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith('text_output='):
            final = line[len('text_output='):]
    return final


def _decode_offline_outputs(stdout: str) -> list[str]:
    """从 audiocpp_cli 离线 batch 输出解析每段文本。"""
    out = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith('text=') or line.startswith('text_output=') or '"text":' in line:
            # 取 = 或 : 后的 quoted string
            if 'text_output=' in line:
                out.append(line.split('text_output=', 1)[1].strip('"').rstrip(','))
            elif line.startswith('text='):
                out.append(line[len('text='):].strip('"'))
            elif '"text":' in line:
                v = line.split('"text":', 1)[1].strip().lstrip('"')
                out.append(v.rstrip('",').rstrip('"'))
    return out


# ── cfg 6: CUDA 流式 (单段, 通过 stdin raw PCM) ──
def cfg6_cuda_streaming(wav_path, name):
    print(f'[{name}] CUDA streaming ...', flush=True)
    # wav → raw PCM s16le 16kHz mono (stdin)
    audio, sr = sf.read(wav_path)
    assert sr == 16000
    audio = audio.astype(np.float32)
    pcm = (audio * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    cmd = [
        CUDA_EXE,
        '--task', 'asr', '--family', CUDA_FAMILY, '--model', CUDA_MODEL, '--backend', CUDA_BACKEND,
        '--mode', 'streaming',
        '--audio', '-', '--input-format', 's16le', '--input-rate', '16000', '--input-channels', '1',
        '--session-option', 'chunk_size_ms=640',
        '--session-option', 'unfixed_chunk_num=0',
        '--session-option', 'unfixed_token_num=5',
        '--session-option', 'max_tokens=32',
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, input=pcm, capture_output=True, timeout=600)
    wall = time.perf_counter() - t0
    text = _decode_streaming_text(proc.stdout.decode('utf-8', errors='replace'))
    print(f'[{name}] wall={wall:.2f}s text(前 80 词)={text[:300]!r}', flush=True)
    # 保存 raw 输出
    with open(f'{OUT_DIR}/{name}.stdout', 'w', encoding='utf-8') as f:
        f.write(proc.stdout.decode('utf-8', errors='replace'))
    with open(f'{OUT_DIR}/{name}.stderr', 'w', encoding='utf-8') as f:
        f.write(proc.stderr.decode('utf-8', errors='replace'))
    return text, wall


# ── cfg 7: CUDA 离线 (单段) ──
def cfg7_cuda_offline(wav_path, name):
    print(f'[{name}] CUDA offline ...', flush=True)
    cmd = [
        CUDA_EXE,
        '--task', 'asr', '--family', CUDA_FAMILY, '--model', CUDA_MODEL, '--backend', CUDA_BACKEND,
        '--mode', 'offline',
        '--audio', wav_path,
        '--metrics',
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, timeout=600)
    wall = time.perf_counter() - t0
    text = _decode_streaming_text(proc.stdout.decode('utf-8', errors='replace'))
    print(f'[{name}] wall={wall:.2f}s text(前 80 词)={text[:300]!r}', flush=True)
    with open(f'{OUT_DIR}/{name}.stdout', 'w', encoding='utf-8') as f:
        f.write(proc.stdout.decode('utf-8', errors='replace'))
    with open(f'{OUT_DIR}/{name}.stderr', 'w', encoding='utf-8') as f:
        f.write(proc.stderr.decode('utf-8', errors='replace'))
    return text, wall


def first_n_words(s, n=80):
    return ' '.join(s.split()[:n])


def main():
    summary = []
    for seg_name, seg_path in [('A', AUDIO_A), ('B', AUDIO_B)]:
        print(f'\n========= segment {seg_name}: {seg_path} =========', flush=True)
        for cfg_id, cfg_fn, cfg_name in [
            (6, cfg6_cuda_streaming, 'cfg6_cuda_streaming'),
            (7, cfg7_cuda_offline, 'cfg7_cuda_offline'),
        ]:
            print(f'\n--- cfg {cfg_id} on {seg_name} ---', flush=True)
            try:
                text, wall = cfg_fn(seg_path, f'{seg_name}_{cfg_name}')
            except Exception as e:
                import traceback
                print(f'[{seg_name}_{cfg_name}] ERROR: {type(e).__name__}: {e}', flush=True)
                traceback.print_exc()
                text, wall = f'[ERROR: {e}]', 0.0
            summary.append({
                'seg': seg_name, 'cfg': cfg_id, 'cfg_name': cfg_name,
                'text': text, 'text_first_80w': first_n_words(text, 80),
                'text_words': len(text.split()), 'wall_s': wall,
            })
    with open(f'{OUT_DIR}/cuda_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(f'{OUT_DIR}/cuda_compare.txt', 'w', encoding='utf-8') as f:
        for s in summary:
            f.write(f"\n=== {s['seg']} | cfg {s['cfg']} ({s['cfg_name']}) | "
                    f"wall={s['wall_s']:.2f}s | words={s['text_words']} ===\n")
            f.write(s['text_first_80w'] + '\n')
    print(f'\n[diag] summary → {OUT_DIR}/cuda_summary.json', flush=True)


if __name__ == '__main__':
    main()
