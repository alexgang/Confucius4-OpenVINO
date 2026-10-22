# -*- coding: utf-8 -*-
"""端到端：在**客户包**路径下用 INT8 模型实际翻译。

验证新增的「Intel GPU · INT8-CW」选项在客户包环境里真的能跑通整条链路
（加载 -> 推理 -> 提取译文）。
"""
import os, sys

APP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.2\app'
sys.path.insert(0, APP)

from translator import MT_ENGINES, HunyuanTranslator

cfg = MT_ENGINES['gpu_int8cw']
model = cfg['model']
print('选项 :', cfg['label'])
print('设备 :', cfg['device'])
print('模型 :', model)
print('说明 :', cfg['note'])
print('=' * 64)

assert os.path.isdir(model), model
assert cfg['device'] == 'GPU.0'

cache = os.path.join(os.environ.get('TEMP', '.'), 'lc_mt_int8_pkg_cache')
tr = HunyuanTranslator(model, cfg['device'], cache_dir=cache,
                       on_log=lambda m: print('  [log]', m))
print(f'加载完成：{tr.load_s:.2f} s')
print('=' * 64)

CASES = [
    ('对，好的。', 'en'),
    ('我们下周一上午十点在三楼会议室开会，讨论新产品的发布计划。', 'en'),
    ('Okay, sounds good.', 'zh'),
]

fails = []
for text, tgt in CASES:
    r = tr.translate(text, tgt)
    out = r['text']
    print(f'\n-> {tgt}: {text[:34]}')
    print(f'   译文: {out[:90]}')
    print(f'   lat={r["lat_ms"]:.0f}ms ttft={r["ttft_ms"]:.0f}ms out_tok={r.get("n_out")}')
    if not out:
        fails.append(f'空输出: {text[:20]}')
    if '\ufffd' in out:
        fails.append(f'乱码: {out[:50]}')
    for bad in ('<answer>', '</answer>', '<think>'):
        if bad in out:
            fails.append(f'残留 {bad}: {out[:50]}')

print()
print('=' * 64)
if fails:
    print('FAILED:')
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('ALL PASS：客户包内 INT8-CW on GPU.0 端到端翻译正常')
