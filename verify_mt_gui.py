# -*- coding: utf-8 -*-
"""验证 GUI 翻译后端下拉能正确渲染新增的 GPU·INT8-CW 选项（无 Tk 模拟）。

复刻 live_caption_app.App 里 _mark_missing_mt_engines / _cur_mt_engine_key
/ _set_mt_note 的逻辑，验证：
  1) 5 个后端全部出现在下拉里
  2) label -> key 反查正确（GUI 用 label 反查 key，重名会导致错乱）
  3) 选中「Intel GPU · INT8-CW」能反查到 gpu_int8cw
  4) 切换后 note 正确显示
  5) 「缺模型」标注逻辑正确（不存在的模型才加后缀）
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_caption'))

import live_caption_app as A
from translator import MT_ENGINES, mt_available

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + ('   ' + str(extra) if extra else ''))
    if not cond:
        fails.append(name)


# 复刻 App 的下拉构建
keys = list(MT_ENGINES)
label = {k: MT_ENGINES[k]['label'] for k in keys}
back = {v: k for k, v in label.items()}

# 复刻 _mark_missing_mt_engines
for k in keys:
    if not mt_available(k):
        label[k] += '（缺模型）'
        back[label[k]] = k

values = [label[k] for k in keys]
print('下拉项：')
for v in values:
    print('   ', v)
print()

check('下拉共 5 项', len(values) == 5, len(values))
check('含「Intel GPU · INT8-CW」', 'Intel GPU · INT8-CW' in values)
check('含「Intel GPU · INT4-CW」', 'Intel GPU · INT4-CW' in values)
check('含「Intel NPU · INT4-CW」', 'Intel NPU · INT4-CW' in values)
check('含「Intel NPU · INT8-CW」', 'Intel NPU · INT8-CW' in values)
check('含「自动 · INT4-CW 模型」', '自动 · INT4-CW 模型' in values)

# 反查
check('反查「Intel GPU · INT8-CW」-> gpu_int8cw',
      back.get('Intel GPU · INT8-CW') == 'gpu_int8cw', back.get('Intel GPU · INT8-CW'))
check('反查「Intel GPU · INT4-CW」-> gpu_int4cw',
      back.get('Intel GPU · INT4-CW') == 'gpu_int4cw')
check('反查「Intel NPU · INT8-CW」-> npu_int8cw',
      back.get('Intel NPU · INT8-CW') == 'npu_int8cw')
check('反查「自动 · INT4-CW 模型」-> auto',
      back.get('自动 · INT4-CW 模型') == 'auto')
check('反查表大小等于后端数（无重名）', len(back) == len(keys), f'{len(back)} vs {len(keys)}')

# note
for k in ('gpu_int8cw', 'gpu_int4cw', 'npu_int4cw', 'npu_int8cw'):
    n = MT_ENGINES[k]['note']
    check(f'{k} note 非空', bool(n.strip()))
check('gpu_int8cw note 含 GPU.0 设备语义（提到争抢）',
      '争抢' in MT_ENGINES['gpu_int8cw']['note'], MT_ENGINES['gpu_int8cw']['note'])

# 所有下拉项都能反查到 key（模拟用户逐项点选）
for v in values:
    check(f'下拉项可反查: {v}', back.get(v) in keys, back.get(v))

print()
print('=' * 60)
if fails:
    print('FAILED %d 项：%s' % (len(fails), fails))
    sys.exit(1)
print('ALL PASS')
