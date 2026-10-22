"""parse_audiocpp_stream.py — 解析 audio.cpp 流式运行日志，提取逐块时序

日志行示例：
  [TIMING ts=...] confucius4_r2t2.audio_encoder.graph.compute_ms 151.5009
  [TIMING ts=...] greedy_qwen_decoder.reusable.prefill_ms 94.6317
  [TIMING ts=...] greedy_qwen_decoder.reusable.decode.tokens 5
  [TIMING ts=...] session.finalize_ms 170.7

用法：
    python parse_audiocpp_stream.py run_q8.log q8
"""
import re
import sys
import json

TS = re.compile(r'\[TIMING ts=(\S+)\] (\S+) ([\d.]+)')
FINALIZE = re.compile(r'\[TIMING ts=\S+\] session\.finalize_ms ([\d.]+)')


def parse(path):
    chunks = []
    cur = {}
    finalize_ms = None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if 'audio_encoder.graph.compute_ms' in line:
                m = TS.search(line)
                if m:
                    cur = {'enc': float(m.group(3))}
            elif 'greedy_qwen_decoder.reusable.prefill_ms' in line:
                m = TS.search(line)
                if m and cur:
                    cur['prefill'] = float(m.group(3))
                    chunks.append(cur)
                    cur = {}
            elif 'session.finalize_ms' in line:
                m = FINALIZE.search(line)
                if m:
                    finalize_ms = float(m.group(1))
    for i, c in enumerate(chunks, 1):
        c['chunk'] = i
        c['total'] = round(c['enc'] + c.get('prefill', 0.0), 1)
        c['enc'] = round(c['enc'], 1)
        c['prefill'] = round(c.get('prefill', 0.0), 1)
    return chunks, finalize_ms


def main():
    path, tag = sys.argv[1], sys.argv[2]
    chunks, fin = parse(path)
    tot = [c['total'] for c in chunks]
    enc = [c['enc'] for c in chunks]
    pre = [c['prefill'] for c in chunks]
    steady = tot[1:] or tot
    print(f'[{tag}] chunks={len(chunks)}  finalize_ms={fin}')
    print(f'[{tag}] enc   mean={sum(enc)/len(enc):7.1f}  '
          f'first={enc[0]:7.1f}  steady={sum(enc[1:])/(len(enc)-1):7.1f}')
    print(f'[{tag}] pre   mean={sum(pre)/len(pre):7.1f}  '
          f'first={pre[0]:7.1f}  steady={sum(pre[1:])/(len(pre)-1):7.1f}')
    print(f'[{tag}] total mean={sum(tot)/len(tot):7.1f}  '
          f'first={tot[0]:7.1f}  steady={sum(steady)/len(steady):7.1f}  '
          f'min={min(tot):6.1f}  max={max(tot):6.1f}')
    audio_s = 6.74
    wall = sum(tot) / 1000.0 + (fin or 0) / 1000.0
    print(f'[{tag}] 音频内逐块合计+flush = {wall:.3f}s  → RTF(不含加载) '
          f'{wall/audio_s:.3f}')
    out = sys.argv[3] if len(sys.argv) > 3 else None
    if out:
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'chunks': chunks, 'finalize_ms': fin,
                       'audio_s': audio_s}, f, ensure_ascii=False, indent=2)
        print(f'[{tag}] saved -> {out}')


if __name__ == '__main__':
    main()
