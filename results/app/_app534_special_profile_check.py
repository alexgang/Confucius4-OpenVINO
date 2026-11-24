#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app534_special_profile_check.py —— 校验 Special MVP 的 profile 行为（静态、零推理）。

在**临时目录**里搭三个假包（specialmvp / minimvp / full），各放一份 app/ 代码，
跑真代码 ⇒ 断言：
  ① specialmvp ⇒ DEFAULT_DEVICES = {asr:GPU.0, mt:NPU, tts:CUDA}、tts_extra_devices=['CUDA']；
  ② minimvp   ⇒ {asr:GPU.0, mt:GPU.0, tts:NPU}、tts_extra_devices=[]（APP-098 行为不变）；
  ③ full      ⇒ {asr:GPU.0, mt:GPU.0, tts:GPU.0}、tts_extra_devices=[]。
"""
import json
import os
import shutil
import sys
import tempfile

SRC = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
MODS = ['device_config.py', 'package_profile.py', 'tts_cuda.py', 'tts_cuda_sidecar.py']

errs = []
res = {}

tmp = tempfile.mkdtemp(prefix='specprof_')
try:
    for prof, marker in (('specialmvp', {'profile': 'specialmvp', 'allow_cuda': True,
                                         'allow_clone_voice': False, 'target_langs': 10}),
                         ('minimvp', {'profile': 'minimvp', 'allow_cuda': False,
                                      'allow_clone_voice': False, 'target_langs': 10}),
                         ('full', {'profile': 'full', 'allow_cuda': False,
                                   'allow_clone_voice': True, 'target_langs': 10})):
        root = os.path.join(tmp, prof)
        app = os.path.join(root, 'app')
        os.makedirs(app)
        os.makedirs(os.path.join(root, 'models', 'qwen3tts', 'voices'))
        for m in MODS:
            shutil.copy2(os.path.join(SRC, m), os.path.join(app, m))
        with open(os.path.join(root, 'package_profile.json'), 'w', encoding='utf-8') as f:
            json.dump(marker, f)
        # specialmvp 才给一个假的 cuda_env（available() 只查文件是否存在）
        if prof == 'specialmvp':
            ce = os.path.join(root, 'cuda_env', 'Scripts')
            os.makedirs(ce)
            open(os.path.join(ce, 'python.exe'), 'wb').write(b'MZ')
        # 让包内 tts_cuda 找到「包」（default_pkg_dir 需要 app/ + models/）
        os.environ['LIVECAP_PKG'] = root
        sys.path.insert(0, app)
        for m in list(sys.modules):
            if m in ('device_config', 'package_profile', 'tts_cuda'):
                del sys.modules[m]
        import device_config
        import package_profile
        res[prof] = {
            'PROFILE': package_profile.PROFILE,
            'allow_cuda': package_profile.allow_cuda(),
            'is_specialmvp': package_profile.is_specialmvp(),
            'DEFAULT_DEVICES': dict(device_config.DEFAULT_DEVICES),
            'tts_extra_devices': device_config.tts_extra_devices(),
            'label_CUDA': device_config.device_label('CUDA'),
        }
        sys.path.remove(app)
        for m in list(sys.modules):
            if m in ('device_config', 'package_profile', 'tts_cuda'):
                del sys.modules[m]
finally:
    shutil.rmtree(tmp, ignore_errors=True)

expect = {
    'specialmvp': ({'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'CUDA'}, ['CUDA'], True),
    'minimvp': ({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}, [], False),
    'full': ({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'GPU.0'}, [], False),
}
for prof, (exp_def, exp_extra, exp_cuda) in expect.items():
    r = res[prof]
    if r['DEFAULT_DEVICES'] != exp_def:
        errs.append('%s: DEFAULT_DEVICES %r != %r' % (prof, r['DEFAULT_DEVICES'], exp_def))
    if r['tts_extra_devices'] != exp_extra:
        errs.append('%s: tts_extra_devices %r != %r' % (prof, r['tts_extra_devices'], exp_extra))
    if r['allow_cuda'] != exp_cuda:
        errs.append('%s: allow_cuda %r != %r' % (prof, r['allow_cuda'], exp_cuda))

out = {'verdict': 'FAIL' if errs else 'PASS', 'errors': errs, 'detail': res}
print(json.dumps(out, ensure_ascii=False, indent=1))
with open(sys.argv[1] if len(sys.argv) > 1 else 'app534_special_profile_check.json',
          'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
sys.exit(0 if not errs else 2)
