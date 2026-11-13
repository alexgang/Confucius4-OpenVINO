#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app538_chain_rerun.py —— 重跑 Special MVP 的**整链**（10 分钟片段）并更新验收证据。

🔴 为什么重跑：上一轮用 30 s 片段 ⇒ **CUDA TTS 的模型加载 59~67 s**
   （比 OV 路径的 ~13 s 慢很多）⇒ 音频先播完、TTS 才就绪 ⇒ **提交 0 句**
   ⇒ 不是产品缺陷，是**测试时长不够**。本轮改用 rc11 验收同款
   `test_audio/clip_10min_0_600.wav`（10 分钟）⇒ TTS 有充足时间就绪并合成。
"""
import json
import os
import subprocess
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1')
RESULTS = os.path.join(HOME, 'confucius4-openvino', 'results', 'app')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
AUDIO = os.path.join(HOME, 'confucius4-openvino', 'test_audio',
                      'clip_10min_0_600.wav')
ACCEPT = os.path.join(RESULTS, 'app536_specialmvp_acceptance.json')
TTS_OUT = os.path.join(RESULTS, '_app538_special_tts_out.wav')
TIMELINE = TTS_OUT + '.tts.jsonl'

ev = json.load(open(ACCEPT, encoding='utf-8'))

# ── 模型文件计数（递归，之前只数了顶层条目 ⇒ 9 而非 12）──
mdir = os.path.join(PKG, 'models', 'tts_cuda')
n_model = sum(len(f) for _, _, f in os.walk(mdir)) if os.path.isdir(mdir) else 0
A = ev['phases']['A_static']
A['model_files'] = n_model
A['model_files_note'] = ('🔴 上一轮这里只数了**顶层条目**（9）⇒ 误判「模型缺失」；'
                         '实际 speech_tokenizer/ 是**目录**（内含 3 个文件）'
                         '⇒ 递归计数 = %d 个文件（与 MANIFEST 登记的 12 一致）'
                         % n_model)
for c in ev.get('checks', []):
    if c['name'].startswith('A: TTS CUDA 模型随包'):
        c['pass'] = (A['model_dir_exists'] and n_model == 12)
        c['detail'] = '%d 个文件（递归）' % n_model

# ── 整链重跑 ──
for p in (TTS_OUT, TIMELINE):
    if os.path.exists(p):
        os.rename(p, p + '.old')

cmd = [PKG_PY, os.path.join(PKG, 'app', 'live_caption_app.py'),
       '--cli', '--file', AUDIO,
       '--asr-device', 'GPU.0',
       '--mt-device', 'NPU',
       '--tts-device', 'CUDA',
       '--translate', 'zh',
       '--tts', 'on',
       '--tts-out', TTS_OUT]
t1 = time.time()
p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, cwd=PKG)
so, se = p.stdout or '', p.stderr or ''
D = ev['phases']['D_chain']
D.update({'rc': p.returncode, 'elapsed_s': round(time.time() - t1, 1),
          'audio': AUDIO, 'stdout_tail': so[-9000:], 'stderr_tail': se[-4000:]})
D['tts_out_exists'] = os.path.isfile(TTS_OUT)
D['tts_out_bytes'] = os.path.getsize(TTS_OUT) if D['tts_out_exists'] else None
D['timeline_exists'] = os.path.isfile(TIMELINE)
if D['tts_out_exists']:
    q = subprocess.run([PKG_PY, '-c',
                        'import soundfile as sf, numpy as np;'
                        'd,sr=sf.read(r"%s");'
                        'print(sr, round(len(d)/sr,2), round(float(np.abs(d).max()),4))'
                        % TTS_OUT], capture_output=True, text=True, timeout=120)
    D['tts_out_info'] = q.stdout.strip()[:300]
# 统计 TTS 遥测行
tts_lines = [ln for ln in so.splitlines() if '[TTS]' in ln]
D['tts_telemetry_tail'] = tts_lines[-14:]
D['n_tts_lines'] = len(tts_lines)
ev['phases']['D_chain'] = D

for c in ev.get('checks', []):
    if c['name'].startswith('D: 整链跑通'):
        ok = (D.get('rc') == 0 and D.get('tts_out_exists')
              and (D.get('tts_out_bytes') or 0) > 1000)
        c['pass'] = ok
        c['detail'] = ('rc=%s elapsed=%ss tts_out=%s bytes=%s info=%s'
                       % (D.get('rc'), D.get('elapsed_s'), D.get('tts_out_exists'),
                          D.get('tts_out_bytes'), D.get('tts_out_info')))

ev['n_fail'] = sum(1 for c in ev.get('checks', []) if not c['pass'])
ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
with open(ACCEPT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('判定：%s（%d/%d 通过）' % (ev['verdict'],
                                len(ev.get('checks', [])) - ev['n_fail'],
                                len(ev.get('checks', []))))
for c in ev.get('checks', []):
    if not c['pass']:
        print('   FAIL: %s | %s' % (c['name'], c['detail'][:200]))
print('TTS 遥测尾部：')
for ln in D['tts_telemetry_tail']:
    print('   ', ln[:150])
