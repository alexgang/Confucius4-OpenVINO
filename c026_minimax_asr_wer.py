"""c026_minimax_asr_wer.py — 用 MiniMax cloud ASR (asr-1.0) 跑 61-min 录音 + WER vs 本地 OV 流式

流程：
1. 把 61-min 音频切成 ≤500s 的 wav 段（每段约 459s，共 8 段）
2. 对每段调 https://api.minimaxi.com/v1/speech_to_text (model=asr-1.0, response_format=verbose_json, timestamp_level=word)
3. 把多段 ASR 输出拼成完整 transcript（[start-end] text 每行一段）
4. 算 OV 流式 transcript vs MiniMax ASR baseline 的全文 WER

API key 从 $MINIMAX_API_KEY 读取（用户已提供），绝不入文件。
"""
import os, sys, time, json, re
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import requests
import soundfile as sf
import numpy as np

WAV_IN = 'test_audio/260902_SPE_audio.wav'
SEG_DIR = 'reports/c026_minimax'
OUT_TXT = 'reports/c026_minimax_transcript.txt'
OUT_RAW = 'reports/c026_minimax_raw.json'
WER_JSON = 'reports/c026_wer.json'
OV_TXT = 'reports/spe_61min_transcript.txt'

URL = 'https://api.minimaxi.com/v1/speech_to_text'
MODEL = 'asr-1.0'
MAX_SEG_S = 500  # API 上限 500s/段


def get_api_key():
    k = os.environ.get('MINIMAX_API_KEY')
    if not k:
        # try the Anthropic env (same key in user's env)
        k = os.environ.get('ANTHROPIC_AUTH_TOKEN')
    if not k:
        raise SystemExit('MINIMAX_API_KEY / ANTHROPIC_AUTH_TOKEN not set')
    return k


def split_audio(wav_path, seg_dir, max_seg_s):
    os.makedirs(seg_dir, exist_ok=True)
    audio, sr = sf.read(wav_path, dtype='float32')
    assert sr == 16000
    n = len(audio)
    seg_samps = max_seg_s * sr
    chunks = []
    i = 0
    idx = 0
    while i < n:
        end = min(i + seg_samps, n)
        chunk = audio[i:end]
        p = os.path.join(seg_dir, f'chunk_{idx:02d}.wav')
        sf.write(p, chunk, sr)
        chunks.append({
            'idx': idx,
            'path': p,
            'start_s': i / sr,
            'end_s': end / sr,
            'duration_s': (end - i) / sr,
        })
        idx += 1
        i = end
    print(f'[c026] split into {len(chunks)} chunks, total {n/sr:.1f}s', flush=True)
    return chunks


def call_asr(wav_path, key):
    with open(wav_path, 'rb') as f:
        resp = requests.post(
            URL,
            headers={'Authorization': f'Bearer {key}'},
            files={'file': (os.path.basename(wav_path), f, 'audio/wav')},
            data={
                'model': MODEL,
                'response_format': 'verbose_json',
                'timestamp_level': 'word',
            },
            timeout=600,
        )
    if resp.status_code != 200:
        print(f'  HTTP {resp.status_code}: {resp.text[:500]}', flush=True)
        resp.raise_for_status()
    return resp.json()


def words(s):
    s = s.lower()
    s = re.sub(r'[\.,!?;:\(\)\[\]\-\—\"]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return [w for w in s.split() if w]


def edit_dist(a, b):
    m, n = len(a), len(b)
    if m == 0: return n
    if n == 0: return m
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(m+1): dp[i][0] = i
    for j in range(n+1): dp[0][j] = j
    for i in range(1, m+1):
        for j in range(1, n+1):
            if a[i-1] == b[j-1]: dp[i][j] = dp[i-1][j-1]
            else: dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    return dp[m][n]


def main():
    key = get_api_key()
    chunks = split_audio(WAV_IN, SEG_DIR, MAX_SEG_S)

    # Call ASR per chunk
    all_results = []
    for ch in chunks:
        print(f'[c026] ASR chunk {ch["idx"]}/{len(chunks)} '
              f'[{ch["start_s"]:.1f}-{ch["end_s"]:.1f}] ...', flush=True)
        t0 = time.perf_counter()
        try:
            r = call_asr(ch['path'], key)
            wall = time.perf_counter() - t0
            # verbose_json has 'text', 'segments', 'words' (per timestamp_level=word)
            text = r.get('text', '')
            segs = r.get('segments', [])
            words_list = r.get('words', [])
            print(f'  → {len(text)} chars, {len(segs)} segs, '
                  f'{len(words_list)} words, wall={wall:.1f}s', flush=True)
            ch.update({'text': text, 'segs': segs, 'words': words_list, 'wall_s': wall, 'ok': True})
        except Exception as e:
            ch.update({'text': '', 'segs': [], 'words': [], 'err': str(e), 'ok': False})
            print(f'  ERROR: {e}', flush=True)
        all_results.append(ch)

    # Save raw
    with open(OUT_RAW, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f'[c026] → {OUT_RAW}', flush=True)

    # Build combined transcript
    # Strategy: use segments if present, else just text per chunk
    lines = []
    full_text_words = []
    for ch in all_results:
        if not ch.get('ok'):
            continue
        if ch.get('segs'):
            # Use per-chunk segment timestamps, shifted by chunk start
            for s in ch['segs']:
                start = s.get('start', 0) + ch['start_s']
                end = s.get('end', 0) + ch['start_s']
                text = s.get('text', '').strip()
                if text:
                    lines.append(f'[{start:.1f}-{end:.1f}] {text}')
                    full_text_words.extend(words(text))
        else:
            # Fall back to chunk-level text
            text = ch.get('text', '').strip()
            if text:
                lines.append(f'[{ch["start_s"]:.1f}-{ch["end_s"]:.1f}] {text}')
                full_text_words.extend(words(text))
    with open(OUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'[c026] → {OUT_TXT} ({len(lines)} segs)', flush=True)

    # WER vs OV
    print(f'[c026] computing WER vs OV ...', flush=True)
    ov_segs = []
    with open(OV_TXT, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            m = re.match(r'\[([\d.]+)-([\d.]+)\]\s*(.*)', line)
            if m: ov_segs.append({'s': float(m.group(1)), 'e': float(m.group(2)),
                                   't': m.group(3)})
    ov_words = []
    for s in ov_segs:
        ov_words.extend(words(s['t']))

    ed = edit_dist(ov_words, full_text_words)
    wer = ed / max(len(full_text_words), 1)
    print(f'[c026]   OV: {len(ov_words)} words', flush=True)
    print(f'[c026]   MiniMax: {len(full_text_words)} words', flush=True)
    print(f'[c026]   edit dist: {ed}', flush=True)
    print(f'[c026]   WER: {wer*100:.2f}%', flush=True)
    print(f'[c026]   Target: ≤ 12%', flush=True)

    result = {
        'ov_words': len(ov_words),
        'mm_words': len(full_text_words),
        'edit_dist': ed,
        'wer_pct': wer * 100,
        'target_pct': 12.0,
        'pass': wer <= 0.12,
        'chunks_ok': sum(1 for c in all_results if c.get('ok')),
        'chunks_err': sum(1 for c in all_results if not c.get('ok')),
    }
    with open(WER_JSON, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'[c026] → {WER_JSON}', flush=True)


if __name__ == '__main__':
    main()
