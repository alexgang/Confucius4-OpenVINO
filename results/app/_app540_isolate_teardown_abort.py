#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app540_isolate_teardown_abort.py —— 隔离「退出时 abort（rc=3221226505）」的归属。

问题：Special MVP 的 10 分钟整链**跑完了**（142 句出声、文件全写出），
**但进程退出码是 3221226505（0xC0000409）** ⇒ 崩在**收尾**阶段。

要回答：**这是 CUDA 引入的，还是 OV/NPU 侧本来就有的？**
⇒ 同一台机、同一段 60 s 音频、同一包，跑三臂：
   A `--tts off`（**不碰 CUDA**）⇒ 退出码？
   B `--tts on --tts-device CUDA` ⇒ 退出码？
   C `--tts on --tts-device NPU`（OV 路径）⇒ 退出码？
   ⇒ 若 A 也 abort ⇒ 与 CUDA 无关（pre-existing）；若只有 B abort ⇒ CUDA 相关。
"""
import json
import os
import subprocess
import time

HOME = r"C:\Users\Trekker-PTL"
PKG = os.path.join(HOME, "Confucius4_LiveCaption_SpecialMVP_v1.0-sp1")
PKG_PY = os.path.join(PKG, "python", "python.exe")
RESULTS = os.path.join(HOME, "confucius4-openvino", "results", "app")
AUDIO = os.path.join(HOME, "confucius4-openvino", "reports", "c025",
                      "audio_A_600_660.wav")
OUT = os.path.join(RESULTS, "app540_teardown_abort_isolation.json")

arms = [
    ('A_tts_off', ['--tts', 'off']),
    ('B_tts_cuda', ['--tts', 'on', '--tts-device', 'CUDA']),
    ('C_tts_npu_ov', ['--tts', 'on', '--tts-device', 'NPU']),
]
res = {}
for name, extra in arms:
    cmd = [PKG_PY, os.path.join(PKG, 'app', 'live_caption_app.py'),
           '--cli', '--file', AUDIO,
           '--asr-device', 'GPU.0', '--mt-device', 'NPU',
           '--translate', 'zh'] + extra
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=PKG)
    so = p.stdout or ''
    m = [ln for ln in so.splitlines() if '最终统计' in ln]
    res[name] = {'rc': p.returncode,
                 'rc_hex': hex(p.returncode & 0xFFFFFFFF),
                 'elapsed_s': round(time.time() - t0, 1),
                 'final_stats': m[-1][:200] if m else '',
                 'stdout_tail': so[-800:]}
    print('%-12s rc=%-12s (%s) %ss | %s'
          % (name, p.returncode, hex(p.returncode & 0xFFFFFFFF),
             res[name]['elapsed_s'], (m[-1][:90] if m else '')), flush=True)

# 判读
rcs = {k: v['rc'] for k, v in res.items()}
aborts = {k: (v['rc'] == 3221226505) for k, v in res.items()}
if aborts['A_tts_off'] and aborts['B_tts_cuda']:
    verdict = ('abort 与 CUDA 无关：**A 臂（完全不碰 CUDA）也 abort** '
               '⇒ 属 **pre-existing（OV/NPU 侧收尾）**，非本包引入')
elif aborts['B_tts_cuda'] and not aborts['A_tts_off']:
    verdict = ('abort **只在 CUDA 臂出现** ⇒ 与 CUDA 边车收尾相关 '
               '（本包引入，需修）')
else:
    verdict = '各臂退出码不一致 ⇒ 需进一步定位'
res['verdict'] = verdict
res['rcs'] = rcs
res['aborts'] = aborts
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print('\n判读：%s' % verdict)
