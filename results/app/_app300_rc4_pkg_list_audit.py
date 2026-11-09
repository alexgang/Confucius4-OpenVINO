#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app300_rc4_pkg_list_audit.py —— **rc4 打包前的清单审计**。

## 为什么要有这个脚本

rc3 的 README 写着「解压后 约 6.7 GB（10 474 个文件）」，
而 rc4 的 README **沿用了 rc3 的这两个数字** ⇒ 与实际不符
（reviewer 在 APP-073(c) 正是抓过「README 数字 vs zip 条目数」不一致）。

⇒ 打包前**必须**先把 README 的数字改成**实测值**，再打 zip，
否则 zip 里的 README 又是一份对不上的说明书。

## 本脚本干什么

1. 用 `pkg_exclude`（**单一数据源**）算出**进包清单**（文件数 / 字节数）；
2. 列出**被排除**的文件（确认没有该排除的漏进来 / 不该排除的误剔）；
3. 校验 rc4 的 README 里写的「文件数 / 体积」与清单**一致**
   ⇒ 不一致就**报出来**（由 `_app301` 去定点改 README）；
4. 对照 rc3 的 zip 实际条目数，确认**计数口径一致**
   （rc3 zip 条目数 == rc3 `pkg_exclude` 文件数 ⇒ 同一口径）。

用法：
    .venv/Scripts/python.exe results/app/_app300_rc4_pkg_list_audit.py
"""
from __future__ import annotations

import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

import pkg_exclude as PE  # noqa: E402

HOME = os.path.expanduser('~')
RC3 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
RC4 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
RC3_ZIP = os.path.join(HOME, 'shared', 'minimvp',
                        'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip')
EVID = os.path.join(HERE, 'app300_rc4_pkg_list_audit_evidence.json')


def walk_all(pkg: str) -> list:
    out = []
    for dp, _dn, fn in os.walk(pkg):
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), pkg)
                       .replace(os.sep, '/'))
    return out


def main() -> int:
    res = {'script': os.path.basename(__file__), 'pkg': RC4}

    keep_rows = list(PE.iter_package_files(RC4))
    keep = {r: s for r, s in keep_rows}
    allf = walk_all(RC4)
    excl = sorted(set(allf) - set(keep))

    res['n_on_disk'] = len(allf)
    res['n_in_package'] = len(keep)
    res['n_excluded'] = len(excl)
    res['excluded_files'] = excl[:40]
    res['package_bytes'] = sum(keep.values())
    res['package_gb'] = round(res['package_bytes'] / 1024 ** 3, 3)

    # ── 计数口径对照：rc3 zip 实际条目数 vs rc3 pkg_exclude 文件数 ──
    rc3_rows = list(PE.iter_package_files(RC3))
    res['rc3_pkg_exclude_n'] = len(rc3_rows)
    if os.path.isfile(RC3_ZIP):
        z = zipfile.ZipFile(RC3_ZIP)
        n = [i for i in z.infolist() if not i.is_dir()]
        z.close()
        res['rc3_zip_entries'] = len(n)
        res['count_convention_same'] = (len(n) == len(rc3_rows))
    res['rc3_pkg_exclude_bytes'] = sum(s for _r, s in rc3_rows)
    res['rc3_pkg_exclude_gb'] = round(res['rc3_pkg_exclude_bytes'] / 1024 ** 3, 3)

    # ── README 现状 vs 实测 ──
    rp = os.path.join(RC4, 'README_perftest.txt')
    txt = open(rp, encoding='utf-8').read()
    import re
    m_size = re.search(r'解压后 \*\*约 ([0-9.]+) GB\*\*（([0-9 ]+) 个文件）', txt)
    cur = {'gb': float(m_size.group(1)) if m_size else None,
           'n_files': int(m_size.group(2).replace(' ', '')) if m_size else None}
    res['readme_claims'] = cur
    res['readme_matches_actual'] = (
        cur['n_files'] == res['n_in_package']
        and abs(cur['gb'] - res['package_gb']) < 0.15)
    res['verdict'] = ('LIST_OK' if res['readme_matches_actual']
                      else 'README_NUMBERS_STALE')

    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in
                      ('n_on_disk', 'n_in_package', 'n_excluded',
                       'package_gb', 'rc3_zip_entries', 'rc3_pkg_exclude_n',
                       'count_convention_same', 'readme_claims',
                       'readme_matches_actual', 'verdict')},
                     ensure_ascii=False, indent=1))
    if res['excluded_files']:
        print('被排除的文件（前 %d 个）：' % len(res['excluded_files']))
        for e in res['excluded_files'][:20]:
            print('   ', e)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
