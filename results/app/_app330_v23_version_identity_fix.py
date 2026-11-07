#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app330 — APP-081：v2.3 包内**版本标识**定点修正（精确替换 + 唯一命中断言）。

起因：从 v2.2 复制来的 README_zh/en 首行仍是 v2.2；NOTICE 首行是
`Confucius4 LiveCaption MiniMVP v1.0-rc3 — 第三方组件归属与许可证`
（MiniMVP 版本线遗留）⇒ app170 闸门 D1/D2/D3 FAIL，
且 sync_c172 的 `_NOTICE_RE` 因该格式无法识别而直接中止。

处置：**只改这三处身份行**，NOTICE 正文的第三方许可署名一字不动
（app170 的 I2–I6 不变量必须继续 PASS）；写后逐字节复核 + app170 闸门复跑。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.3'
OUT = os.path.join(ROOT, 'results', 'app', '_app330_v23_version_identity_fix.json')
GATE = os.path.join(ROOT, 'results', 'app', 'app170_version_identity_gate.py')

BLOCKS = [
    ('README_zh.md',
     b'# Confucius4-R2T2 \xe5\xae\x9e\xe6\x97\xb6\xe5\xad\x97\xe5\xb9\x95'
     b'\xef\xbc\x88\xe6\x8a\x80\xe6\x9c\xaf\xe8\xaf\x84\xe4\xbc\xb0\xe7\x89\x88 v2.2\xef\xbc\x89',
     b'# Confucius4-R2T2 \xe5\xae\x9e\xe6\x97\xb6\xe5\xad\x97\xe5\xb9\x95'
     b'\xef\xbc\x88\xe6\x8a\x80\xe6\x9c\xaf\xe8\xaf\x84\xe4\xbc\xb0\xe7\x89\x88 v2.3\xef\xbc\x89'),
    ('README_en.md',
     b'# Confucius4-R2T2 Live Captions (technical evaluation build v2.2)',
     b'# Confucius4-R2T2 Live Captions (technical evaluation build v2.3)'),
    ('NOTICE',
     ('Confucius4 LiveCaption MiniMVP v1.0-rc3 — 第三方组件归属与许可证').encode('utf-8'),
     ('Confucius4 LiveCaption v2.3 — 第三方组件归属与许可证').encode('utf-8')),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ev = {'tool': '_app330', 'app': 'APP-081',
          'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'pkg': PKG, 'blocks': [], 'gate_after': None}
    for name, old, new in BLOCKS:
        p = os.path.join(PKG, name)
        raw = open(p, 'rb').read()
        n = raw.count(old)
        rec = {'file': name, 'old_hits': n, 'bytes_before': len(raw),
               'sha256_before': sha(raw)}
        if n != 1:
            rec['verdict'] = 'FAIL_ANCHOR'
            ev['blocks'].append(rec)
            print('[FAIL] %s 锚点命中 %d 次（需 1）' % (name, n))
            continue
        out = raw.replace(old, new, 1)
        # 行尾不变（只做同长度附近的身份串替换）
        rec['crlf_before'] = raw.count(b'\r\n')
        rec['crlf_after'] = out.count(b'\r\n')
        tmp = p + '._app330_tmp'
        with open(tmp, 'wb') as f:
            f.write(out)
        back = open(tmp, 'rb').read()
        assert back == out, '写后逐字节复核失败 %s' % name
        os.replace(tmp, p)
        rec.update({'bytes_after': len(out), 'sha256_after': sha(out),
                    'verdict': 'PASS'})
        ev['blocks'].append(rec)
        print('[OK] %-16s 唯一命中 1 次，行尾 %d→%d，%d→%d B'
              % (name, rec['crlf_before'], rec['crlf_after'],
                 len(raw), len(out)))
    ok_blocks = all(b.get('verdict') == 'PASS' for b in ev['blocks'])
    r = subprocess.run([sys.executable, GATE, '--pkg', PKG,
                        '--expect-version', '2.3'],
                       capture_output=True, timeout=600)
    txt = (r.stdout or b'').decode('utf-8', errors='replace')
    ev['gate_after'] = {'rc': r.returncode,
                        'tail': txt.strip().splitlines()[-12:]}
    for line in txt.strip().splitlines():
        if 'PASS=' in line or 'verdict=' in line or 'FAIL=' in line:
            print('  [gate]', line.strip())
    ev['verdict'] = 'PASS' if (ok_blocks and r.returncode == 0) else 'FAIL'
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[%s] %s' % (ev['verdict'], OUT))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
