#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""§245：把候选包里 **32 个 `*.bak*` 备份文件**移到包外（**只移不删**），并落清单。

## 为什么
APP-150 §1 的白名单 18/18 全过，但**没有一条查备份文件** ⇒ 32 个 `*.bak_app146_*` /
`*.bak_app151` 会随 zip 一起发给客户（含 `translator.py.bak_app151`＝改之前的旧版）。
这是**交付面缺陷**，也说明白名单本身漏了一项（已在 `_app150_zip_whitelist.py` 补第 ⑨ 条）。

## 纪律
目标目录在包外（`shared/pkg_baks_20261126/`），逐个 `shutil.move`，移动前后核对
size + sha256；**不删除任何文件**（本机安全删除 shim 会拦删除，见 MEMORY）。
"""
import hashlib
import io
import json
import os
import shutil
import sys
import time

CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate'
DEST = r'C:\Users\Trekker-PTL\shared\pkg_baks_20261126'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app245_pkg_baks_move.json'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def is_bak(fn):
    low = fn.lower()
    return '.bak' in low or '.overwritten' in low or low.endswith('.tmp')


def main():
    os.makedirs(DEST, exist_ok=True)
    moved, failed = [], []
    for dp, dns, fns in os.walk(CAND):
        for fn in fns:
            if not is_bak(fn):
                continue
            src = os.path.join(dp, fn)
            rel = os.path.relpath(src, CAND).replace('\\', '/')
            dst = os.path.join(DEST, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            before = (os.path.getsize(src), sha(src))
            try:
                shutil.move(src, dst)
            except Exception as e:
                failed.append({'rel': rel, 'error': repr(e)})
                continue
            after = (os.path.getsize(dst), sha(dst))
            ok = (before == after) and (not os.path.isfile(src))
            moved.append({'rel': rel, 'bytes': before[0], 'sha256': before[1],
                          'dest': dst, 'verified': ok})
            if not ok:
                failed.append({'rel': rel, 'error': 'move verify failed'})

    left = []
    for dp, dns, fns in os.walk(CAND):
        for fn in fns:
            if is_bak(fn):
                left.append(os.path.relpath(os.path.join(dp, fn), CAND))

    payload = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
               'candidate': CAND, 'dest': DEST,
               'n_moved': len(moved), 'n_failed': len(failed),
               'n_left_in_pkg': len(left), 'moved': moved,
               'failed': failed, 'left': left,
               'note': '🔴 只移不删；每个文件移动前后比 size+sha256。'}
    with io.open(OUT + '.tmp', 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    os.replace(OUT + '.tmp', OUT)
    print('移出 %d 个，失败 %d 个，包内残留 %d 个' % (len(moved), len(failed), len(left)))
    for m in moved:
        print('   %-46s %8d B  verified=%s' % (m['rel'], m['bytes'], m['verified']))
    print('证据：%s' % OUT)
    return 0 if (not failed and not left) else 3


if __name__ == '__main__':
    sys.exit(main())
