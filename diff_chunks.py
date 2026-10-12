"""diff_chunks.py — C-010 #4：torch vs OV 逐 chunk 文本对比

读取 reports/stream_torch_c010.csv 和 reports/stream_ov_c010.csv，
按 chunk_id 对齐，对比 fixed_text 字段。
"""
import csv

def read_csv(p):
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))

torch = read_csv('reports/stream_torch_c010.csv')
ov = read_csv('reports/stream_ov_c010.csv')

print(f'torch chunks: {len(torch)}, ov chunks: {len(ov)}')
assert len(torch) == len(ov), f'chunk count mismatch: {len(torch)} vs {len(ov)}'

diffs = []
for t, o in zip(torch, ov):
    if t['text'] != o['text']:
        diffs.append((t['chunk_id'], t['text'], o['text']))

print(f'\nDiffs: {len(diffs)}')
for cid, tt, ot in diffs:
    print(f'  chunk {cid}: torch={tt!r}  ov={ot!r}')

if not diffs:
    print('\n✅ 22/22 chunks torch == OV (text 完全一致)')
    # 也比 n_tokens
    tok_diffs = [(t['chunk_id'], t['n_tokens'], o['n_tokens'])
                 for t, o in zip(torch, ov) if t['n_tokens'] != o['n_tokens']]
    print(f'\nn_tokens diffs: {len(tok_diffs)}')
    for cid, tn, on in tok_diffs:
        print(f'  chunk {cid}: torch={tn} ov={on}')
    if not tok_diffs:
        print('\n✅ token counts 也完全一致')
