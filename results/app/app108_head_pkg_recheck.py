# -*- coding: utf-8 -*-
"""§77 收尾：仓库 HEAD ⇄ 客户包 app/ 逐文件 LF SHA256 复核。

🔴 只读检查：不写任何文件。
🔴 口径：**HEAD 里的内容**（`git show HEAD:<rel>`）vs **客户包磁盘上的文件**，
   两侧都归一化 LF 后取 SHA256（仓库 CRLF / 包 LF ⇒ 不归一化必然全 DIFF）。
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6\app'

# §76 复核过的 7 个文件 + 本轮 §77 新增同步的 3 个文件
TARGETS = [
    'tts_engine.py',
    'tts_worker.py',
    'tts_service.py',
    'tts_cuda.py',
    'tts_cuda_sidecar.py',
    'live_caption_app.py',
    'translator.py',
    # §77
    'offline_reader.py',
    'offline_reader_gui.py',
]


def lf_sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def git_show(rel: str) -> bytes:
    out = subprocess.run(
        ['git', '-C', REPO, 'show', 'HEAD:' + rel],
        capture_output=True, check=True).stdout
    return out


def main() -> int:
    rows = []
    for name in TARGETS:
        rel = 'live_caption/' + name
        pkg_path = os.path.join(PKG, name)
        try:
            head_bytes = git_show(rel)
        except subprocess.CalledProcessError:
            rows.append((name, 'SKIP', 'not in HEAD', '', ''))
            continue
        if not os.path.exists(pkg_path):
            rows.append((name, 'MISSING', 'pkg file absent', '', ''))
            continue
        with open(pkg_path, 'rb') as f:
            pkg_bytes = f.read()
        h1, h2 = lf_sha(head_bytes), lf_sha(pkg_bytes)
        rows.append((name, 'MATCH' if h1 == h2 else 'DIFF',
                     '%d B' % len(head_bytes), h1[:16], h2[:16]))

    print('%-26s %-8s %-12s %-18s %-18s' %
          ('file', 'verdict', 'HEAD size', 'HEAD sha256[:16]', 'PKG sha256[:16]'))
    n_match = n_diff = n_other = 0
    for name, v, sz, a, b in rows:
        print('%-26s %-8s %-12s %-18s %-18s' % (name, v, sz, a, b))
        if v == 'MATCH':
            n_match += 1
        elif v == 'DIFF':
            n_diff += 1
        else:
            n_other += 1
    print('\nSUMMARY: MATCH=%d DIFF=%d OTHER=%d (total %d)' %
          (n_match, n_diff, n_other, len(rows)))
    return 0 if (n_diff == 0 and n_other == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
