# -*- coding: utf-8 -*-
"""验证 INT8-SYM-CW 翻译模型在 Intel GPU (GPU.0) 上能真正加载并推理。

直接用项目真实的 HunyuanTranslator（与 GUI 里跑的完全同一条路径）。
"""
import os, sys, time, statistics as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_caption'))

from translator import HunyuanTranslator

MODEL = r'C:\Users\Trekker-PTL\hy_bench\ov\int8sym-cw-q'
if not os.path.isdir(MODEL):
    print('SKIP: 模型目录不存在', MODEL)
    sys.exit(0)

cache = os.path.join(os.environ.get('TEMP', '.'), 'lc_mt_int8_gpu_cache')
tr = HunyuanTranslator(MODEL, 'GPU.0', cache_dir=cache,
                       on_log=lambda m: print('  [log]', m))
print(f'加载完成：{tr.load_s:.2f} s，设备 {tr.device}')
print('=' * 64)

CASES = [
    ('对，好的。', 'en'),
    ('我们下周一上午十点在三楼会议室开会，讨论新产品的发布计划，请大家提前准备好材料。', 'en'),
    ('Okay, sounds good.', 'zh'),
    ('Could you send me the latest version of the report before the meeting?', 'zh'),
]

fails = []
tpots = []
for text, tgt in CASES:
    r = tr.translate(text, tgt)
    out = r['text']
    lat, ttft = r['lat_ms'], r['ttft_ms']
    n_out = r.get('n_out', 0)
    tpot = (lat - ttft) / n_out if n_out and lat > ttft else 0
    if tpot:
        tpots.append(1000 / tpot)
    print(f'\n-> {tgt}: {text[:34]}')
    print(f'   译文: {out[:90]}')
    print(f'   in={r.get("n_in")} out={n_out} lat={lat:.0f}ms ttft={ttft:.0f}ms '
          f'tok/s={1000/tpot if tpot else 0:.1f}')

    if not out:
        fails.append(f'空输出: {text[:20]}')
    if '\ufffd' in out:
        fails.append(f'乱码: {out[:50]}')
    # 译文里不该残留 prompt 标签
    for bad in ('<answer>', '</answer>', '<think>', 'system', 'Translate this'):
        if bad in out:
            fails.append(f'输出残留 {bad!r}: {out[:60]}')
    # 中译英应产出英文（ASCII 为主）
    if tgt == 'en' and not any(c.isascii() and c.isalpha() for c in out):
        fails.append(f'中译英未产出英文: {out[:50]}')

print()
print('=' * 64)
if tpots:
    print(f'tok/s 中位数 = {st.median(tpots):.1f}（含首 token 抖动，非纯 bench 值）')
if fails:
    print('FAILED:')
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('ALL PASS：INT8-SYM-CW 在 GPU.0 上加载与推理均正常，无乱码、无标签残留')
