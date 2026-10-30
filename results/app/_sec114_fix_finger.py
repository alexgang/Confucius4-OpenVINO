#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 §114 草稿里的**产物指纹表**对齐到实际文件（迭代到收敛）。

🔴 为什么必须迭代：改草稿 ⇒ STATUS 大小变 ⇒ §114 里的「体积自指」变
   ⇒ 再改草稿 ⇒ …… ⇒ 必须跑到不动点（ASR-036 同类坑）。
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
BODY = os.path.join(HERE, '_sec114_body.md')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec109_113_upto_20261030.md')
WRITER = os.path.join(HERE, '_sec114_write_status.py')
BASE = os.path.join(os.environ.get('TEMP', '/tmp'), 'STATUS_APP.sec114_base.md')

PY = sys.executable
SCRIPT = 'results/app/app171_app027_v3_cer_compare.py'
EVID = 'results/app/app171_app027_v3_cer_compare_evidence.json'


def fp(rel):
    raw = open(os.path.join(REPO, rel), 'rb').read()
    st = os.stat(os.path.join(REPO, rel))
    import datetime
    return {
        'bytes': len(raw),
        'sha': hashlib.sha256(raw).hexdigest(),
        'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%H:%M:%S'),
        'lines': len(raw.decode('utf-8').split('\n')),
    }


def size():
    raw = open(STATUS, 'rb').read()
    return len(raw), len(raw.decode('utf-8').split('\n'))


for it in range(1, 9):
    # ① 指纹表对齐
    s = fp(SCRIPT)
    e = fp(EVID)
    b, l = size()
    t = open(BODY, encoding='utf-8').read()
    new_s = ('| `results/app/app171_app027_v3_cer_compare.py` | **%d B** / SHA256 `%s…` / '
             'mtime %s / %d 行 |' % (s['bytes'], s['sha'][:16], s['mtime'], s['lines']))
    new_e = ('| `results/app/app171_app027_v3_cer_compare_evidence.json` | **%d B** / SHA256 `%s…` / '
             'mtime %s（`n_pass=14` / `n_fail=0` / `verdict=PASS`；**内容命中 0**；'
             'SHA256 随 `generated_ts` 变，字节数恒定） |'
             % (e['bytes'], e['sha'][:16], e['mtime']))
    t2 = re.sub(r'\| `results/app/app171_app027_v3_cer_compare\.py` \|.*?\|',
                new_s.replace('\\', '\\\\'), t)
    t2 = re.sub(r'\| `results/app/app171_app027_v3_cer_compare_evidence\.json` \|.*?\|',
                new_e.replace('\\', '\\\\'), t2)
    # 体积自指
    t2 = re.sub(r'现 \*\*[\d\s]+ B / \d+ 行\*\*',
                '现 **%d B / %d 行**' % (b, l), t2)
    if t2 != t:
        open(BODY, 'w', encoding='utf-8', newline='').write(t2)
        print('[迭代 %d] 草稿已更新（指纹 + 体积）' % it)

    # ② 从基线重跑写入器
    shutil.copyfile(BASE, STATUS)
    if os.path.exists(ARCHIVE):
        os.remove(ARCHIVE)
    r = subprocess.run([PY, WRITER], capture_output=True, text=True,
                       cwd=REPO, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print('[迭代 %d] 写入器失败：\n%s' % (it, r.stdout[-1500:] + r.stderr[-1500:]))
        sys.exit(1)
    nb, nl = size()

    # ③ 收敛判据：草稿里的指纹与体积 == 实际
    s2 = fp(SCRIPT)
    e2 = fp(EVID)
    t3 = open(BODY, encoding='utf-8').read()
    m = re.search(r'`results/app/app171_app027_v3_cer_compare\.py` \| \*\*(\d+) B\*\*', t3)
    m2 = re.search(r'`results/app/app171_app027_v3_cer_compare_evidence\.json` \| \*\*(\d+) B\*\*', t3)
    m3 = re.search(r'现 \*\*([\d\s]+) B / (\d+) 行\*\*', t3)
    ok = (m and int(m.group(1)) == s2['bytes'] and
          m2 and int(m2.group(1)) == e2['bytes'] and
          m3 and int(m3.group(1).replace(' ', '')) == nb and int(m3.group(2)) == nl)
    print('[迭代 %d] 写入后 %d B / %d 行；脚本 %d B；证据 %d B；收敛=%s'
          % (it, nb, nl, s2['bytes'], e2['bytes'], ok))
    if ok:
        print('\n✅ 收敛（迭代 %d 次）' % it)
        break
else:
    print('❌ 未收敛')
    sys.exit(1)
