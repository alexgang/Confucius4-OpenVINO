#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app287_rc3_readme_count_patch.py —— APP-073(b) / APP-074：**README 文件数改正**。

## 做什么

reviewer 在 APP-073 指出（原文）：

> 2. README 磁盘写"10 503 个文件/约6.7GB"与 zip 10 474 条目不符（小问题）。

APP-074 末尾进一步确认（原文）：

> 如果 A 不依赖这 4 个文件，冒烟 PASS 后按 APP-073 (c) 收口，
> **并把 README 的文件数改成 10 474**。

实测口径（`pkg_exclude.iter_package_files` ⇒ 与 zip 的清单**同源**）：

| 口径 | 值 |
|---|---|
| rc3 目录**磁盘上**的文件数（含被排除的第三方素材） | **10 504** |
| **进 zip** 的文件数（`pkg_exclude` 口径） | **10 474** |
| zip 内条目数 | **10 474** |
| zip 解压后的文件数 | **10 474** |

⇒ README 里那个「10 503」**是 rc3 磁盘目录的旧数字**（还差 1 是因为
`README_perftest.txt` 自己是后加的）⇒ **对「解压后」的口径是错的**
⇒ 必须改成 **10 474**。

## 🔴 改法纪律（与 app278 同款）

* **定点字符串替换 + 唯一命中断言**（不是整文件重写）。
* 只动**一个数字**：`（10 503 个文件）` ⇒ `（10 474 个文件）`。
* 「约 6.7 GB」**不改**（实测 7 176 154 805 B = 6.683 GiB ⇒ 「约 6.7 GB」是对的）。
* 写前备份原文 + 写后**逐字节复核**（除目标片段外一字未变）。
* 🔴 **只改 rc3 目录里的 README**（`Confucius4_LiveCaption_MiniMVP_v1.0-rc3/`）
  ⇒ **不碰**用户正在测试的安装目录 `Confucius4_LiveCaption_v*`
  （APP-055 铁律）⇒ **zip 的重打由打包脚本另做**（新版本目录 + 新 zip）。

## 用法

```
.venv/Scripts/python.exe results/app/_app287_rc3_readme_count_patch.py --dry-run
.venv/Scripts/python.exe results/app/_app287_rc3_readme_count_patch.py --run
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
sys.path.insert(0, REPO)

DEFAULT_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
REPORT = os.path.join(HERE, 'app287_rc3_readme_count_patch_evidence.json')

#: 定点替换块（**唯一命中**；带前后锚点 ⇒ 不会误伤别处的「10 503」）
OLD_SNIPPET = '解压后 **约 6.7 GB**（10 503 个文件）'
NEW_SNIPPET = '解压后 **约 6.7 GB**（10 474 个文件）'


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--out', default=REPORT)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if not (a.dry_run or a.run):
        ap.error('必须给 --dry-run 或 --run')

    readme = os.path.join(a.pkg, 'README_perftest.txt')
    out = {'script': '_app287_rc3_readme_count_patch.py',
           'correction': 'APP-073(b) ② + APP-074（README 文件数 10 503 → 10 474）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': a.pkg, 'readme': readme,
           'old_snippet': OLD_SNIPPET, 'new_snippet': NEW_SNIPPET,
           'mode': 'run' if a.run else 'dry-run'}

    if not os.path.isfile(readme):
        out['verdict'] = 'FAIL'
        out['reason'] = 'README 不存在：%s' % readme
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    before = open(readme, 'rb').read()
    out['before'] = {'bytes': len(before), 'sha256': sha256_bytes(before),
                     'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                           time.localtime(os.path.getmtime(readme)))}

    # ── 计数复核：README 该写的数字 = **实际进 zip 的条目数** ──────────
    import pkg_exclude as PE
    n_pkg = len(list(PE.iter_package_files(a.pkg)))
    out['n_files_pkg_exclude'] = n_pkg
    out['target_count'] = 10474

    old_b = OLD_SNIPPET.encode('utf-8')
    new_b = NEW_SNIPPET.encode('utf-8')
    n_hit = before.count(old_b)
    out['n_hit_old_snippet'] = n_hit
    if n_hit != 1:
        out['verdict'] = 'FAIL'
        out['reason'] = '目标片段命中 %d 次（必须恰好 1 次）' % n_hit
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    after = before.replace(old_b, new_b, 1)
    out['n_bytes_delta'] = len(after) - len(before)

    # ── 写后**逐字节复核**：除目标片段外一字未变 ───────────────────
    if after.replace(new_b, old_b, 1) != before:
        out['verdict'] = 'FAIL'
        out['reason'] = '写后复核失败：反向替换不等于原文'
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1
    out['roundtrip_ok'] = True

    if a.dry_run:
        out['verdict'] = 'DRY_RUN_OK'
        out['after_bytes'] = len(after)
        out['after_sha256'] = sha256_bytes(after)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    # ── 实写（先备份，再原子替换）────────────────────────────────
    bak = readme + '.bak_app284'
    with open(bak, 'wb') as f:
        f.write(before)
    out['backup'] = {'path': bak, 'bytes': len(before),
                     'sha256': sha256_bytes(before)}

    tmp = readme + '.tmp_app284'
    with open(tmp, 'wb') as f:
        f.write(after)
    os.replace(tmp, readme)

    # ── 写后复核（落盘的真实字节）────────────────────────────────
    disk = open(readme, 'rb').read()
    out['after'] = {'bytes': len(disk), 'sha256': sha256_bytes(disk),
                    'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                           time.localtime(os.path.getmtime(readme)))}
    out['disk_equals_intended'] = (disk == after)
    out['n_hit_new_on_disk'] = disk.count(new_b)
    out['n_hit_old_on_disk'] = disk.count(old_b)
    out['n_lines'] = disk.count(b'\n')
    out['crlf_count'] = disk.count(b'\r\n')
    out['verdict'] = ('PASS' if (disk == after and disk.count(new_b) == 1
                                 and disk.count(old_b) == 0) else 'FAIL')
    out['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
