"""diff_int8.py — C-013 #3：INT8 640ms vs torch 640ms 逐 chunk 对比"""
import csv

def read_csv(p):
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))

torch = read_csv('reports/stream_torch_640.csv')
ov = read_csv('reports/stream_int8_640.csv')

print(f'torch chunks: {len(torch)}, INT8 chunks: {len(ov)}')
if len(torch) != len(ov):
    print('⚠ chunk count differs')

diffs = []
for t, o in zip(torch, ov):
    if t['text'] != o['text']:
        diffs.append((t['chunk_id'], t['text'], o['text']))

print(f'\nText diffs: {len(diffs)}')
for cid, tt, ot in diffs:
    print(f'  chunk {cid}: torch={tt!r}  INT8={ot!r}')

if not diffs and len(torch) == len(ov):
    print('\n✅ All chunks: torch == INT8 (text 完全一致)')

# CER
final_torch = torch[-1]['text']
final_ov = ov[-1]['text']
# remove diff and compare
import re
def normalize(s):
    return re.sub(r'[\s，。！？、；：,.!?;:\'\"]', '', s)
t_norm = normalize(final_torch)
o_norm = normalize(final_ov)
if t_norm == o_norm:
    print('✅ CER=0%（仅标点差异视为 0）')
else:
    # edit distance
    import editdistance
    ed = editdistance.eval(t_norm, o_norm)
    cer = ed / max(len(t_norm), 1)
    print(f'CER（去标点后）: {cer*100:.2f}%  ({ed}/{len(t_norm)})')
    print(f'  torch: {final_torch!r}')
    print(f'  INT8:  {final_ov!r}')

# n_tokens
tok_diffs = [(t['chunk_id'], t['n_tokens'], o['n_tokens'])
             for t, o in zip(torch, ov) if t['n_tokens'] != o['n_tokens']]
if tok_diffs:
    print(f'\nn_tokens diffs: {len(tok_diffs)}')
    for cid, tn, on_ in tok_diffs:
        print(f'  chunk {cid}: torch={tn} INT8={on_}')
else:
    print('n_tokens: 完全一致')
