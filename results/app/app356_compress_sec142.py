# -*- coding: utf-8 -*-
"""app356_compress_sec142.py — APP-052④ 二次压缩，为 §159 腾出 1121 B 缺口。

§142 正文整块逐字归档 => status/archive/STATUS_APP_sec142_20261109.md，
正文留标题 + 2 行速查。写前自检 + 原子替换 + 写后逐字节复核。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec142_20261109.md')
EVID = os.path.join(REPO, 'results', 'app', 'app356_compress_sec142_evidence.json')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    old = open(STATUS, 'rb').read()
    assert b'\r\n' not in old
    txt = old.decode('utf-8')
    lines = txt.split('\n')
    hits = [i for i, l in enumerate(lines) if l.startswith('## §142 ')]
    assert len(hits) == 1, hits
    a = hits[0]
    z = next((i for i in range(a + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
    blk = '\n'.join(lines[a:z])
    assert len(blk.encode('utf-8')) > 1500, len(blk)
    h = sha(blk.encode('utf-8'))
    assert txt.count(blk) == 1

    quick = '\n'.join([
        lines[a],
        '',
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec142_20261109.md`（%d B／块 SHA256 `%s`；含版本纪律与证据落盘 26/0 静态自证）。'
        % (len(blk.encode('utf-8')), h),
        '> 🔴 **速查**：APP-078 版本纪律（不 `--same-version`／不原地改客户包）与证据落盘口径不变；26 PASS / 0 FAIL。',
    ])
    new_txt = txt.replace(blk, quick, 1)
    new = new_txt.encode('utf-8')
    checks = []

    def ck(n, ok, d=''):
        checks.append(dict(name=n, ok=bool(ok), detail=str(d)[:200]))
        assert ok, 'FAILED %s %s' % (n, d)

    ck('limit_bytes', len(new) <= 40000, len(new))
    ck('lf_intact', b'\r\n' not in new)
    ck('h2_unchanged',
       sum(1 for l in new_txt.split('\n') if l.startswith('## ')) ==
       sum(1 for l in lines if l.startswith('## ')))
    ck('reverse_restore', new_txt.replace(quick, blk, 1).encode('utf-8') == old)
    ck('quick_present', quick in new_txt and blk not in new_txt)

    os.makedirs(os.path.dirname(ARCH), exist_ok=True)
    with open(ARCH, 'wb') as f:
        f.write(blk.encode('utf-8'))
    ck('archive_verbatim', open(ARCH, 'rb').read() == blk.encode('utf-8'))

    tmp = STATUS + '.tmp_app356'
    with open(tmp, 'wb') as f:
        f.write(new)
    os.replace(tmp, STATUS)
    disk = open(STATUS, 'rb').read()
    ck('disk_identical', disk == new)

    ev = dict(tool='app356_compress_sec142',
              before=dict(bytes=len(old), sha256=sha(old)),
              after=dict(bytes=len(disk), sha256=sha(disk)),
              archive=dict(path='status/archive/STATUS_APP_sec142_20261109.md',
                           bytes=len(blk.encode('utf-8')), sha256=h, verbatim=True),
              checks=checks, n_pass=sum(1 for c in checks if c['ok']),
              n_fail=sum(1 for c in checks if not c['ok']),
              verdict='PASS')
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps(dict(verdict='PASS', n_pass=ev['n_pass'], before=len(old),
                          after=len(disk), archive_sha=h[:12]), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
