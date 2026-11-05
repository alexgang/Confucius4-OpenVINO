#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-069⑥ 夹具修正：app273 的英文段来源改为真实落盘的 46 行英文定稿。

背景（本轮实测）：`_app273_mt_int4_vs_int8.py` 原 `load_segments()` 从
`minimvp.tts.jsonl` 按 `lang='en'` 取段 ⇒ 该文件 76 行全是中文译文（lang='zh'）
⇒ 首跑 APP273_EXIT=2「没找到英文段」⇒ 0 条 tsv / 0 个 evidence。
真实英文定稿在 `app253_minimvp_out/minimvp.txt`（46 行，
`app253_app066_minimvp_cli_evidence.json` → `summary.segs=46`）。

🔴 定点替换：只动 `load_segments()` 函数体 + `main()` 两处单行；
   唯一命中断言 + `ast.parse` + 写后逐字节复核；CRLF 保持；旧正文不删。
🔴 口径：46 vs reviewer 的 76 ⇒ **写进 evidence，交 reviewer 裁定**，不切句凑 76。
"""
import ast
import os

P = r'C:/Users/Trekker-PTL/confucius4-openvino/results/app/_app273_mt_int4_vs_int8.py'


def crlf(block):
    lines = block.strip('\n').split('\n')
    return ('\r\n'.join(lines) + '\r\n').encode('utf-8')


NEW_LOAD = '''def load_segments():
    """APP-069⑥：reviewer 要「app253 的 76 个定稿英文段」。

    🔴 本机可查的真实英文原文 = app253_minimvp_out/minimvp.txt
       （= shared/app_listen/minimvp_v1.0/minimvp_v1.0_final.txt），**46 行**
       （app253_app066_minimvp_cli_evidence.json → summary.segs=46）。
       minimvp.tts.jsonl 的 **76 行是中文译文**（lang='zh'），不是英文原文
       ⇒ 原实现按 lang='en' 过滤得到 **0 段**（实测 APP273_EXIT=2）。
    ⇒ 按 46 段真实英文定稿跑；46 vs 76 的口径差异写进 evidence，
       **交 reviewer 裁定**，不自行切句凑 76。
    """
    src_txt = os.path.join(HERE, 'app253_minimvp_out', 'minimvp.txt')
    final_txt = os.path.join(HOME, 'shared', 'app_listen', 'minimvp_v1.0',
                             'minimvp_v1.0_final.txt')
    for p in (src_txt, final_txt):
        if not os.path.isfile(p):
            continue
        with open(p, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
        segs = [(i, t) for i, t in enumerate(lines)
                if not any('一' <= c <= '鿿' for c in t)]
        if segs:
            print('源：%s ｜ 英文定稿段 %d' % (os.path.basename(p), len(segs)))
            meta = {
                'source_file': p,
                'n_source_lines': len(lines),
                'n_english_segments': len(segs),
                'reviewer_expected_n_segments': 76,
                'scope_note': ('reviewer 的 76 = TTS 侧中文译文句数；'
                               '本机英文定稿段只有 46（app253 summary.segs=46）'
                               '⇒ 按 46 段跑，差异交 reviewer 裁定'),
                'jsonl_rejected_because': ('minimvp.tts.jsonl 76 行 lang=zh'
                                           '（中文译文），按 en 过滤得 0 段'),
            }
            return segs, meta
    return [], {}

'''

b = open(P, 'rb').read()
for anchor in (b'def load_segments():', b'def chrf(a, b):',
               b'    segs = load_segments()',
               b"        'tsv_bytes': os.path.getsize(OUT_TSV),"):
    n = b.count(anchor)
    assert n == 1, ('锚点命中数异常', anchor, n)

s = b.index(b'def load_segments():')
e = b.index(b'def chrf(a, b):')
b2 = b[:s] + crlf(NEW_LOAD) + b[e:]
b2 = b2.replace(b'    segs = load_segments()',
                b'    segs, src_meta = load_segments()', 1)
b2 = b2.replace(
    b"        'tsv_bytes': os.path.getsize(OUT_TSV),",
    crlf("        'source': src_meta,\n"
         "        'chrf_impl': 'difflib.SequenceMatcher.ratio()*100（字符级相似度，非 sacrebleu chrF）',\n"
         "        'tsv_bytes': os.path.getsize(OUT_TSV),").rstrip(b'\r\n'),
    1)

assert b2.count(b'def load_segments():') == 1
assert b2.count(b'    segs, src_meta = load_segments()') == 1
assert b2.count(b"        'source': src_meta,") == 1
ast.parse(b2.decode('utf-8'))

tmp = P + '.tmp'
with open(tmp, 'wb') as f:
    f.write(b2)
os.replace(tmp, P)
assert open(P, 'rb').read() == b2
print('OK 定点替换完成：bytes %d -> %d（CRLF 保持，ast.parse 通过，写后逐字节复核一致）'
      % (len(b), len(b2)))
