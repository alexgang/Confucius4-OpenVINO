"""c045_wer.py — C-045: 任意 transcript 的真实 WER + S/D/I 误差分解

口径与 reports/WER_ANALYSIS_2026-10-13.md 一致:
- 参考: reports/c026_minimax_transcript.txt (MiniMax baseline, 11066 词)
- 归一化: 小写, 去标点 (保留 apostrophe 后再删), 按空白切词
- 距离: difflib.SequenceMatcher(autojunk=False) 的 opcode → S=replace 取 max, D=delete, I=insert

用法:
  .venv python c045_wer.py                          # 跑默认清单
  .venv python c045_wer.py reports/xxx.txt ...      # 跑指定文件
"""
import re, sys, os
from difflib import SequenceMatcher

REF = 'reports/c026_minimax_transcript.txt'


def norm(w):
    w = w.lower()
    w = re.sub(r"[^\w']", '', w).replace("'", '')
    return w


def ref_words(path=REF):
    ws = []
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^\[[\d.\-]+\]\s*(.*)$', line.strip())
        if m and m.group(1).strip():
            ws.append(m.group(1).strip())
    return [n for w in ws for n in (norm(x) for x in w.split()) if n]


def hyp_words(path):
    ws = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[\s*[\d.]+\s*-\s*[\d.]+\]\s*(.*)$', line)
        if m:
            line = m.group(1)
        ws.extend(norm(w) for w in line.split())
    return [w for w in ws if w]


def score(ref, hyp):
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    S = D = I = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            S += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            D += i2 - i1
        elif tag == 'insert':
            I += j2 - j1
    return S, D, I


def main():
    ref = ref_words()
    print(f'ref (MiniMax) words={len(ref)}')
    print(f'{"transcript":46s} {"words":>6s} {"S":>5s} {"D":>5s} {"I":>5s} {"WER":>7s}')
    print('-' * 84)
    paths = sys.argv[1:] or [
        'reports/spe_61min_transcript_noreset.txt',
        'reports/spe_hybrid_offline.txt',
        'reports/cuda/spe_cuda_stream.txt',
    ]
    for p in paths:
        if not os.path.exists(p):
            print(f'{os.path.basename(p):46s} FILE NOT FOUND')
            continue
        hyp = hyp_words(p)
        S, D, I = score(ref, hyp)
        wer = 100.0 * (S + D + I) / len(ref)
        print(f'{os.path.basename(p):46s} {len(hyp):6d} {S:5d} {D:5d} {I:5d} {wer:6.2f}%')


if __name__ == '__main__':
    main()