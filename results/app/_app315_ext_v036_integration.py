#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app315_ext_v036_integration.py —— **v2.5 内嵌 EXT @ab9a767（v0.3.6）**（APP-094 §3）。

## 依据

* **APP-094 §3**：客户包 v2.5 必须内嵌 EXT @**ab9a767**（v0.3.6，
  "each speaker keeps his first x-vector reference (no 8 s upgrade)"），
  **取代** APP-092 里的 @23aae0b（v0.3.5）；
  **桥接日志须显示「实时配音桥接 v0.3.6」**。
* **APP-094 §2**：不加 anchor（EXT 侧 `CLONE_ANCHOR` 默认 "0" ⇒ 天然满足）。

## 🔴🔴🔴 为什么必须「重新取件」（不能沿用 v2.4 的 ext/）

只读审计（**已实测**）：

| 包 | `ext/bridge/bridge.py` 的 md5 | 对应 EXT 提交 |
|---|---|---|
| v2.0 / v2.1 / v2.2 / v2.3 / **v2.4** | **全部 = `39cbb6590bef`** | `474ae4f` / `06c041c`（EXT-030/031/032 时代） |

⇒ **v2.0→v2.4 五个包的 `ext/` 字节级完全一致** ⇒ EXT 从 v2.0 之后**从未更新**；
   APP-092 要求的「v2.5 内嵌 EXT @23aae0b」**从未落地**。
⇒ 本脚本**从 `live_dub_ext` 的 ab9a767 重新取件**（`git archive` 取那个提交，
   **不是**工作区 HEAD —— HEAD 已是 v0.3.7）。

## 🔴 纪律

* **只读** `live_dub_ext`（`git archive` 不改工作区）。
* **不动 v2.4**（只产出 v2.5 的 `ext/` 片段，供后续 v2.5 构建脚本取用）。
* `bridge_launcher.py` / `start_bridge.cmd` **EXT 仓库里没有**（打包侧自产）
  ⇒ 必须从 v2.4 保留，否则 `bridge_bootstrap.py` 的 REQUIRED 判据失败。

## 用法

```
.venv/Scripts/python.exe results/app/_app315_ext_v036_integration.py --dry-run
.venv/Scripts/python.exe results/app/_app315_ext_v036_integration.py --run
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

EXT_REPO = os.path.join(HOME, 'live_dub_ext')
EXT_COMMIT = 'ab9a767'          # 🔴 APP-094 指定的提交（v0.3.6）
EXT_VERSION = '0.3.6'
V24_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.4')
STAGE = os.path.join(HERE, '_ext_v036_stage')
REPORT = os.path.join(HERE, 'app315_ext_v036_evidence.json')

#: 打包侧自产、EXT 仓库里**没有**的文件（必须从 v2.4 保留）
PACKAGE_SIDE_FILES = ('bridge_launcher.py', 'start_bridge.cmd')


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def git_archive(commit, sub):
    """从 git 取某个提交下子目录的内容（**只读**，不改工作区）。"""
    out = subprocess.run(['git', '-C', EXT_REPO, 'archive', '--format=tar',
                          commit, sub],
                         capture_output=True, check=True)
    return out.stdout


def extract_tar(tar_bytes, dest_prefix):
    """解出 tar 里的某前缀，返回 {相对路径: bytes}。"""
    files = {}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode='r:') as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            if not m.name.startswith(dest_prefix):
                continue
            rel = os.path.relpath(m.name, dest_prefix).replace('\\', '/')
            files[rel] = tf.extractfile(m).read()
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    dry = not args.run

    ev = {
        'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'correction': 'APP-094 §3 (v2.5 embeds EXT @ab9a767 / v0.3.6)',
        'ext_repo': EXT_REPO,
        'ext_commit': EXT_COMMIT,
        'ext_version': EXT_VERSION,
        'dry_run': dry,
        'checks': [],
    }

    def chk(name, cond, detail):
        ev['checks'].append({'name': name, 'pass': bool(cond), 'detail': detail})
        print('[%s] %s — %s' % ('PASS' if cond else 'FAIL', name, detail))

    if not os.path.isdir(EXT_REPO):
        print('!! EXT 仓库不存在')
        return 2

    # ── 闸门：目标提交存在 ─────────────────────────────────────────
    r = subprocess.run(['git', '-C', EXT_REPO, 'cat-file', '-t', EXT_COMMIT],
                       capture_output=True, text=True)
    chk('ext_commit_exists', r.stdout.strip() == 'commit',
        '%s -> %r' % (EXT_COMMIT, r.stdout.strip()))

    # ── 取件 ───────────────────────────────────────────────────────
    bridge = extract_tar(git_archive(EXT_COMMIT, 'ext'), 'ext/')
    plugin = extract_tar(git_archive(EXT_COMMIT, 'extension'), 'extension/')
    ev['n_bridge_py'] = sum(1 for k in bridge if k.endswith('.py'))
    ev['n_plugin_files'] = len(plugin)

    # ① version.py 的版本号必须是 0.3.6
    ver = bridge.get('version.py', b'').decode('utf-8')
    chk('version_py_is_036', 'EXT_VERSION = "0.3.6"' in ver,
        'version.py 里的 EXT_VERSION 片段: %r'
        % ([l for l in ver.split('\n') if 'EXT_VERSION =' in l],))
    chk('version_py_has_label', 'def version_label()' in ver,
        'version_label() 存在（横幅来源）')

    # ② manifest.json 的 version 必须同步成 0.3.6
    man = json.loads(plugin['manifest.json'].decode('utf-8'))
    chk('manifest_version_036', man.get('version') == '0.3.6',
        'manifest.json version=%r' % man.get('version'))
    ev['manifest_key'] = man.get('key')

    # ③ clone_voice.py 必须含 XV_UPGRADE 开关（keep first）
    cv = bridge.get('clone_voice.py', b'').decode('utf-8')
    chk('clone_voice_has_xv_upgrade_switch',
        'XV_UPGRADE' in cv and 'EXT_CLONE_XV_UPGRADE' in cv,
        'clone_voice.py 含 XV_UPGRADE 开关')
    chk('clone_voice_xv_upgrade_default_off',
        'EXT_CLONE_XV_UPGRADE", "0"' in cv,
        '默认 EXT_CLONE_XV_UPGRADE="0"（keep first）')
    chk('clone_voice_anchor_default_off',
        'EXT_CLONE_ANCHOR", "0"' in cv,
        '默认 EXT_CLONE_ANCHOR="0"（不加 anchor，APP-094 §2）')

    # ④ 打包侧自产文件必须能拿到（EXT 仓库里没有）
    for fn in PACKAGE_SIDE_FILES:
        p = os.path.join(V24_PKG, 'ext', 'bridge', fn)
        chk('package_side_file_present_%s' % fn, os.path.exists(p),
            p)

    # ⑤ 桥接横幅的输出点（bridge.py 里应有 version_label 的调用）
    b = bridge.get('bridge.py', b'').decode('utf-8', errors='replace')
    chk('bridge_logs_version_banner',
        '实时配音桥接' in b and 'version_label' in b,
        'bridge.py 输出「实时配音桥接」+ version_label()')

    ev['n_fail'] = sum(1 for c in ev['checks'] if not c['pass'])
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'

    if dry:
        print(json.dumps(ev, ensure_ascii=False, indent=1))
        print('[dry-run] 未写盘')
        return 0 if ev['n_fail'] == 0 else 1

    # ── 落盘到暂存区（供 v2.5 构建脚本取用）──────────────────────
    if os.path.exists(STAGE):
        import shutil
        shutil.rmtree(STAGE)
    bridge_dst = os.path.join(STAGE, 'ext', 'bridge')
    plugin_dst = os.path.join(STAGE, 'ext', 'extension')
    os.makedirs(bridge_dst, exist_ok=True)
    os.makedirs(plugin_dst, exist_ok=True)
    written = {}
    for rel, data in bridge.items():
        if not rel.endswith('.py'):
            continue
        p = os.path.join(bridge_dst, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)
        written['ext/bridge/' + rel] = sha256_bytes(data)
    for rel, data in plugin.items():
        p = os.path.join(plugin_dst, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)
        written['ext/extension/' + rel] = sha256_bytes(data)

    # 打包侧自产文件：从 v2.4 保留
    for fn in PACKAGE_SIDE_FILES:
        src = os.path.join(V24_PKG, 'ext', 'bridge', fn)
        if os.path.exists(src):
            with open(src, 'rb') as f:
                data = f.read()
            with open(os.path.join(bridge_dst, fn), 'wb') as f:
                f.write(data)
            written['ext/bridge/' + fn] = sha256_bytes(data)

    # manifest 的 liveDub 段（release / captureModes）—— 照 v2.0 的 app209 口径
    mp = os.path.join(plugin_dst, 'manifest.json')
    with open(mp, encoding='utf-8') as f:
        old = f.read()
    doc = json.loads(old)
    ld = doc.get('liveDub')
    if isinstance(ld, dict):
        new = dict(doc)
        new['liveDub'] = dict(ld)
        new['liveDub']['release'] = True
        new['liveDub']['captureModes'] = ['tabCapture']
        new['key'] = doc.get('key')          # 🔴 key 不变（扩展 ID）
        with open(mp, 'w', encoding='utf-8') as f:
            f.write(json.dumps(new, ensure_ascii=False, indent=2) + '\n')
        written['ext/extension/manifest.json'] = sha256_file(mp)

    ev['stage'] = STAGE
    ev['written'] = written
    ev['n_written'] = len(written)

    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] 暂存区 %s（%d 个文件）' % (STAGE, len(written)))
    print('证据：%s' % REPORT)
    return 0 if ev['n_fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
