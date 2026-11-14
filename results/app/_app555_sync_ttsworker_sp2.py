#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app555_sync_ttsworker_sp2.py —— 把 dev 树的 `tts_worker.py` **定点**同步进 sp2。

🔴 **为什么现在才同步**：APP-108 §5 FYI 要求的 `_clone_tmp_wav` docstring
   修正会改到**包内 app 代码**；若在 §3 的两臂/三臂实测**之前**改，
   实测对象与交付物就**不是同一份代码** ⇒ 实测失去意义。
   ⇒ 排在实测**之后**同步，**零运行时影响**（只改 docstring），
   并在同步后**重跑** app549（设备解析复验）与 A2（app 代码与 dev 树一致）
   两道闸门。

🔴 **纪律**：仓库 ⇄ 客户包 = 两份独立副本 ⇒ **不整目录覆盖**，
   只做「逐文件比对 + 唯一命中断言 + 逐字节复核」。
"""
import hashlib
import json
import os
import shutil
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
DEV = os.path.join(REPO, 'live_caption')
SP2 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2')
RESULTS = os.path.join(REPO, 'results', 'app')
OUT = os.path.join(RESULTS, 'app555_sync_ttsworker_sp2.json')
FILES = ['tts_worker.py']


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


ev = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'files': [],
      'pkg': SP2}
for f in FILES:
    src = os.path.join(DEV, f)
    dst = os.path.join(SP2, 'app', f)
    before = sha256_file(dst)
    after = sha256_file(src)
    rec = {'file': f, 'sha256_before': before, 'sha256_after': after,
           'bytes': os.path.getsize(src), 'changed': before != after}
    if before != after:
        shutil.copy2(src, dst)
    # 逐字节复核：同步后包内文件必须与 dev 树**完全一致**
    rec['identical_after'] = (sha256_file(dst) == after)
    ev['files'].append(rec)
    print('%-20s %s -> %s  identical=%s'
          % (f, before[:12], after[:12], rec['identical_after']))

# 整包 app 目录复核：所有 .py 必须与 dev 树逐字节一致
mism = []
n = 0
for f in sorted(os.listdir(os.path.join(SP2, 'app'))):
    if not f.endswith('.py'):
        continue
    n += 1
    src = os.path.join(DEV, f)
    dst = os.path.join(SP2, 'app', f)
    if not os.path.isfile(src) or sha256_file(src) != sha256_file(dst):
        mism.append(f)
ev['app_dir'] = {'n_py': n, 'mismatch': mism}
ev['verdict'] = 'PASS' if not mism else 'FAIL'
ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('VERDICT=%s  n_py=%d  mismatch=%s -> %s'
      % (ev['verdict'], n, mism, OUT))
sys.exit(0 if ev['verdict'] == 'PASS' else 1)
