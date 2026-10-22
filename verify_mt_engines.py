# -*- coding: utf-8 -*-
"""验证新增的「Intel GPU · INT8-CW」翻译后端选项。

检查点：
  1) MT_ENGINES 里有 gpu_int8cw，device=GPU.0，模型目录指向 int8sym-cw-q
  2) mt_available('gpu_int8cw') 为真（模型在本机）
  3) set_engine('gpu_int8cw') 后 device/model 正确落到 GPU.0 + INT8 目录
  4) 切回 gpu_int4cw 能正确还原
  5) 标签唯一（GUI 用标签反查 key，重复会导致反查错乱）
  6) 每个后端的 note 非空且含关键提示（显存/争抢/速度）
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_caption'))

from translator import MT_ENGINES, TranslationService, mt_available

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + ('   ' + str(extra) if extra else ''))
    if not cond:
        fails.append(name)


# ① 存在 gpu_int8cw
check('MT_ENGINES 含 gpu_int8cw', 'gpu_int8cw' in MT_ENGINES)
if 'gpu_int8cw' not in MT_ENGINES:
    print('gpu_int8cw 不存在，后续检查跳过')
    sys.exit(1)

cfg = MT_ENGINES['gpu_int8cw']
check("gpu_int8cw 的 device 是 GPU.0", cfg['device'] == 'GPU.0', cfg['device'])
check('gpu_int8cw 模型目录指向 int8sym-cw-q',
      'int8sym-cw-q' in (cfg['model'] or ''), cfg['model'])
check('gpu_int8cw 标签含 INT8', 'INT8' in cfg['label'], cfg['label'])
check('gpu_int8cw 标签含 Intel GPU', 'Intel GPU' in cfg['label'], cfg['label'])

# ② 模型可用
check('mt_available(gpu_int8cw) 为真', mt_available('gpu_int8cw') is True)
check('gpu_int8cw 模型目录真实存在',
      os.path.isdir(cfg['model']), cfg['model'])

# ③ set_engine 切换
svc = TranslationService(target='zh', auto=False, engine_key='gpu_int4cw')
check('初始 device 为 GPU.0', svc.device == 'GPU.0', svc.device)
check('初始 model 为 int4 目录', 'int4sym-cw-q' in svc.model_dir, svc.model_dir)

ok = svc.set_engine('gpu_int8cw')
check('set_engine(gpu_int8cw) 返回 True', ok is True)
check('切换后 device 为 GPU.0', svc.device == 'GPU.0', svc.device)
check('切换后 model 指向 int8 目录', 'int8sym-cw-q' in svc.model_dir, svc.model_dir)

# ④ 切回
svc.set_engine('gpu_int4cw')
check('切回 gpu_int4cw 后 model 为 int4 目录',
      'int4sym-cw-q' in svc.model_dir, svc.model_dir)

# ⑤ 标签唯一
labels = [v['label'] for v in MT_ENGINES.values()]
check('所有后端标签唯一', len(labels) == len(set(labels)), labels)

# ⑥ note 非空
for k, v in MT_ENGINES.items():
    check(f'{k} 的 note 非空', bool((v.get('note') or '').strip()))

# ⑦ gpu_int8cw 的 note 含速度与显存提示
note = cfg['note']
check('gpu_int8cw note 含 tok/s 速度', 'tok/s' in note, note)
check('gpu_int8cw note 提到争抢/显存', ('争抢' in note or '显存' in note), note)

# ⑧ 完整下拉项列表
print()
print('翻译后端下拉（' + str(len(MT_ENGINES)) + ' 项）：')
for k, v in MT_ENGINES.items():
    print(f'  {k:<14} {v["label"]:<26} dev={str(v["device"]):<7} '
          f'avail={mt_available(k)}')

print()
print('=' * 60)
if fails:
    print('FAILED %d 项：%s' % (len(fails), fails))
    sys.exit(1)
print('ALL PASS')
