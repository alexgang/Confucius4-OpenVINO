#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-130：跑单测并落**证据 json**（`results/app/app130_unit_evidence.json`）。

证据要求（§222 教训）：结论必须能落到**结果文件 + 原始字段** ⇒
这里把单测的**逐条断言**（名字 + 结论）都写进 json，供 STATUS/邮件引用。

用法：`.venv/Scripts/python.exe results/app/_app130_unit_evidence.py`
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TEST = os.path.join(HERE, 'test_app130_cp_selfcheck.py')
OUT = os.path.join(HERE, 'app130_unit_evidence.json')
PY = os.path.join(REPO, '.venv', 'Scripts', 'python.exe')


def main():
    py = PY
    if not os.path.isfile(py):
        py = sys.executable
    p = subprocess.run([py, TEST], capture_output=True, text=True, timeout=600,
                       cwd=REPO)
    out = (p.stdout or '') + (p.stderr or '')
    lines = [l for l in out.splitlines() if l.startswith(('PASS ', 'FAIL '))]
    asserts = [{'name': l[5:].split('  — ')[0].strip(),
                'ok': l.startswith('PASS '),
                'detail': l[5:].split('  — ')[1].strip() if '  — ' in l else ''}
               for l in lines]
    n_pass = sum(1 for a in asserts if a['ok'])
    summary = '%d/%d' % (n_pass, len(asserts))
    ev = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'test': os.path.relpath(TEST, REPO).replace('\\', '/'),
          'python': py, 'rc': p.returncode, 'summary': summary,
          'n_pass': n_pass, 'n_total': len(asserts),
          'asserts': asserts,
          'groups': sorted({a['name'].split('-')[0] for a in asserts})}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print(out[-2500:])
    print('证据：%s（%s）' % (OUT, summary))
    return 0 if (p.returncode == 0 and n_pass == len(asserts) and asserts) else 1


if __name__ == '__main__':
    sys.exit(main())
