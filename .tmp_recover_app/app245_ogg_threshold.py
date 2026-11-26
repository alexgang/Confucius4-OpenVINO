# -*- coding: utf-8 -*-
"""按样本数探测 libsndfile VORBIS 的崩溃阈值（每个 case 独立子进程 ⇒ 崩了不影响下一例）。"""
import json
import os
import subprocess
import sys

PY = sys.executable
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app'

CHILD = r'''
import os, sys, numpy as np, soundfile as sf
sr = int(sys.argv[1]); sec = float(sys.argv[2]); sub = sys.argv[3]
x = (0.1 * np.sin(np.linspace(0, 3000, max(1, int(sr * sec))))).astype(np.float32)
p = os.path.join(%r, '_ogg_probe_%%s_%%d_%%d.ogg' %% (sub, sr, int(sec)))
sf.write(p, x, sr, format='OGG', subtype=sub)
print('OK BYTES=%%d' %% os.path.getsize(p))
''' % OUT

cases = [(48000, 5.0, 'VORBIS'), (48000, 10.0, 'VORBIS'),
         (48000, 20.0, 'VORBIS'), (48000, 30.0, 'VORBIS'),
         (48000, 40.0, 'VORBIS'), (16000, 30.0, 'VORBIS'),
         (16000, 40.0, 'VORBIS'), (16000, 40.0, 'OPUS'),
         (8000, 40.0, 'VORBIS')]
res = []
for sr, sec, sub in cases:
    p = subprocess.run([PY, '-c', CHILD, str(sr), str(sec), sub],
                       capture_output=True, text=True, errors='replace')
    ok = p.returncode == 0
    res.append({'sr': sr, 'sec': sec, 'subtype': sub, 'rc': p.returncode,
                'ok': ok, 'stdout': (p.stdout or '').strip()[:120],
                'stderr_tail': (p.stderr or '').strip().splitlines()[-1:] })
    print('%-7s %5d Hz %4.0f s -> rc=%-6s %s'
          % (sub, sr, sec, p.returncode, (p.stdout or '').strip()[:40]), flush=True)

with open(os.path.join(OUT, 'app245_ogg_threshold.json'), 'w',
          encoding='utf-8', newline='\n') as fh:
    json.dump({'cases': res}, fh, ensure_ascii=False, indent=1)
print('DONE')
