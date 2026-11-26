# -*- coding: utf-8 -*-
"""探测 libsndfile 的 OGG 编码能力（小样本，隔离崩溃）。"""
import os

import numpy as np
import soundfile as sf

OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app'
x = (0.1 * np.sin(np.linspace(0, 1000, 48000))).astype(np.float32)

cases = [('OGG', 'VORBIS', 48000), ('OGG', 'VORBIS', 16000),
         ('OGG', 'OPUS', 16000), ('OGG', 'VORBIS', 8000)]
print('libsndfile', sf.__libsndfile_version__, flush=True)
for fmt, sub, sr in cases:
    p = os.path.join(OUT, '_ogg_probe_%s_%d.ogg' % (sub, sr))
    y = x[::max(1, int(48000 / sr))]
    try:
        sf.write(p, y, sr, format=fmt, subtype=sub)
        print('OK  %-7s %5d  %d B' % (sub, sr, os.path.getsize(p)), flush=True)
    except Exception as e:
        print('ERR %-7s %5d  %r' % (sub, sr, e), flush=True)
print('DONE', flush=True)
