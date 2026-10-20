"""c049_minimax_ref.py — C-049: 用 MiniMax cloud ASR 为测试集生成 ground truth

用途:
  现有 61-min 测试集的参考文本来自 MiniMax 转录(见 c026_minimax_asr_wer.py),
  新建的中英测试集若要与之同口径, 也需要 MiniMax 转写。

  同时提供 official / minimax 双轨对照 —— 官方人工转写更严谨, MiniMax 与历史
  数据口径一致, 两者差异可给出 WER 的置信区间。

API key从 $MINIMAX_API_KEY 读取(或 $ANTHROPIC_AUTH_TOKEN), 绝不入文件。

用法:
  .venv python c049_minimax_ref.py test_data/sets/zh_60min
  .venv python c049_minimax_ref.py test_data/sets/mix_60min --max-seg-s 500
"""
import argparse
import json
import os
import re
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import requests
import soundfile as sf
import numpy as np

URL = 'https://api.minimaxi.com/v1/speech_to_text'
MODEL = 'asr-1.0'
MAX_SEG_S = 500      # API 单请求上限
SR = 16000


def get_api_key():
    k = os.environ.get('MINIMAX_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')
    if not k:
        raise SystemExit('MINIMAX_API_KEY / ANTHROPIC_AUTH_TOKEN 未设置')
    return k


def split_audio(wav_path, workdir, max_seg_s):
    os.makedirs(workdir, exist_ok=True)
    a, sr = sf.read(wav_path, dtype='float32')
    assert sr == SR, f'期望 {SR}Hz, 实际 {sr}Hz'
    if a.ndim > 1:
        a = a[:, 0]
    n = len(a)
    step = max_seg_s * sr
    out = []
    i = idx = 0
    while i < n:
        end = min(i + step, n)
        p = os.path.join(workdir, f'_mm_chunk_{idx:03d}.wav')
        sf.write(p, a[i:end], sr)
        out.append({'path': p, 'start': i / sr, 'end': end / sr})
        i = end
        idx += 1
    return out


def call_asr(wav_path, key, retries=3):
    for attempt in range(retries):
        try:
            with open(wav_path, 'rb') as f:
                resp = requests.post(
                    URL,
                    headers={'Authorization': f'Bearer {key}'},
                    files={'file': (os.path.basename(wav_path), f, 'audio/wav')},
                    data={'model': MODEL, 'response_format': 'verbose_json',
                          'timestamp_level': 'word'},
                    timeout=600)
            if resp.status_code != 200:
                print(f'  HTTP {resp.status_code} (第{attempt+1}次): {resp.text[:300]}',
                      flush=True)
                time.sleep(3 * (attempt + 1))
                continue
            return resp.json()
        except Exception as e:
            print(f'  请求异常 (第{attempt+1}次): {e}', flush=True)
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f'{wav_path} 转写失败')


def flatten(d):
    """MiniMax verbose_json -> [(start_s, end_s, text), ...] 句子列表。"""
    sents = []
    for s in d.get('subtitles', []) or d.get('sentences', []) or []:
        st, et, tx = s.get('start'), s.get('end'), (s.get('text') or '').strip()
        if tx:
            sents.append((st, et, tx))
    if not sents:
        txt = (d.get('text') or '').strip()
        if txt:
            sents.append((0, 0, txt))
    return sents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('set_dir')
    ap.add_argument('--max-seg-s', type=int, default=MAX_SEG_S)
    ap.add_argument('--sleep', type=float, default=1.0, help='请求间隔秒')
    args = ap.parse_args()

    sd = args.set_dir.rstrip('/\\')
    wav = os.path.join(sd, 'audio.wav')
    if not os.path.exists(wav):
        raise SystemExit(f'找不到 {wav}')

    key = get_api_key()
    workdir = os.path.join(sd, '_minimax_chunks')
    chunks = split_audio(wav, workdir, args.max_seg_s)
    print(f'切{len(chunks)} 段, 开始调用 MiniMax ASR ...', flush=True)

    all_sents, raw = [], []
    for i, c in enumerate(chunks):
        d = call_asr(c['path'], key)
        raw.append({'chunk': c, 'resp': d})
        ss = flatten(d)
        for st, et, tx in ss:
            # 句子时间是 chunk 内相对时间 → 换算成全局
            gs = c['start'] + (st or 0)
            ge = c['start'] + (et if et is not None else c['end'] - c['start'])
            all_sents.append((gs, ge, tx))
        print(f'  [{i+1}/{len(chunks)}] +{len(ss)} 句, 累计 {len(all_sents)}', flush=True)
        time.sleep(args.sleep)

    out_txt = os.path.join(sd, 'ref_minimax.txt')
    with open(out_txt, 'w', encoding='utf-8') as f:
        for st, et, tx in all_sents:
            f.write(f'[{st:8.1f}-{et:8.1f}] {tx}\n')

    out_json = os.path.join(sd, 'ref_minimax_raw.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)

    print(f'→ {out_txt}  ({len(all_sents)} 句)')
    print(f'→ {out_json}')


if __name__ == '__main__':
    main()