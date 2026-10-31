#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c175_app051_to_pkg.py —— APP-051：把本轮 App 侧改动**定点同步**到客户包。

🔴🔴🔴 **纪律（MEMORY 铁律）**：
  仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**
  ⇒ **禁止整目录覆盖** ⇒ 本脚本只用
  「**精确字符串替换 + 唯一命中断言**」+「difflib 自动派生替换块」。

🔴 **替换块从 `git diff` 自动派生**（不手抄源码 ⇒ 抄错风险归零）：
  - 基线 = `git show HEAD:<file>`（修复前）
  - 候选 = 工作区当前内容（修复后）
  - 用 `difflib` 派生「OLD → NEW」块（带上下文 ⇒ 唯一命中）
  - ⚠️ **纯新增块**（OLD 为空）不能用新块内部的行当锚点
    （那些行在目标包里**根本不存在**）⇒ 用块**前后各一行**的公共上下文定位。

🔴 **幂等**：逐块判定，**NEW 优先** ⇒ 已同步的块报 `ALREADY`。

用法：
    python live_caption/sync_c175_app051_to_pkg.py [--pkg <包目录>]
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
HOME = r'C:\Users\Trekker-PTL'

# 🔴 本轮要同步的文件（**只改这几个**）
TARGETS = ('live_caption_app.py',)

# 🔴 替换块（OLD → NEW）。**OLD 必须是包内逐字存在的文本**。
BLOCKS = {
    'live_caption_app.py': [(
        """            self.tts = TTSService(
                device=dev, voice=voice,
                out_device=out_id,
                precision=prec,
                on_log=lambda m: self._ui_log(f'tts: {m}'))
""",
        """            self.tts = TTSService(
                device=dev, voice=voice,
                out_device=out_id,
                precision=prec,
                # 🔴🔴 APP-051②：GUI 路径的 APP-042 自适应加速播放**验收**
                #   需要逐句遥测（`speed` / `play_lag_s` / `target_wall`）。
                #   ⚠️ 旧行为：GUI **不传** `jsonl_path` ⇒ worker 不落盘遥测
                #   ⇒ **GUI 路径的加速行为无法被离线复核**（只有 CLI 能）。
                #   ⇒ 这里**只在显式给了路径时**才传 ⇒ 默认行为逐字不变。
                jsonl_path=getattr(self.args, 'tts_jsonl', None),
                on_log=lambda m: self._ui_log(f'tts: {m}'))
""",
    )],
}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def norm_sha(p):
    return hashlib.sha256(
        open(p, 'rb').read().replace(b'\r\n', b'\n')).hexdigest()


def discover_pkg():
    """自动发现**最大版本**包目录（**不写死版本号**）。"""
    import re
    cands = []
    for d in os.listdir(HOME):
        m = re.match(r'^Confucius4_LiveCaption_v(\d+)\.(\d+)$', d)
        if not m:
            continue
        if '.bak_' in d or d.endswith('_backup'):
            continue
        cands.append(((int(m.group(1)), int(m.group(2))),
                      os.path.join(HOME, d)))
    if not cands:
        raise SystemExit('找不到客户包目录')
    cands.sort()
    return cands[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    pkg_app = os.path.join(args.pkg or discover_pkg(), 'app')
    if not os.path.isdir(pkg_app):
        raise SystemExit('包目录不存在：%s' % pkg_app)
    print('[pkg] %s' % pkg_app)

    backup = os.path.join(tempfile.gettempdir(),
                          'app051_backup_%s' % time.strftime('%Y%m%d_%H%M%S'))
    os.makedirs(backup, exist_ok=True)
    print('[backup] %s' % backup)

    rc = 0
    for fname in TARGETS:
        repo_p = os.path.join(REPO, 'live_caption', fname)
        pkg_p = os.path.join(pkg_app, fname)
        if not os.path.isfile(pkg_p):
            print('[SKIP] 包内不存在：%s' % fname)
            continue
        shutil.copy2(pkg_p, os.path.join(backup, fname))

        with open(pkg_p, 'rb') as f:
            raw = f.read()
        text = raw.decode('utf-8')
        crlf = b'\r\n' in raw

        blocks = BLOCKS.get(fname, [])
        if not blocks:
            # 兜底：仓库版与包内版**归一化后一致** ⇒ 报 ALREADY
            if norm_sha(repo_p) == norm_sha(pkg_p):
                print('[ALREADY] %s（与仓库逐字一致，无需改）' % fname)
            else:
                print('[WARN] %s：无替换块且与仓库不一致 ⇒ 未处理' % fname)
                rc = 1
            continue

        changed = False
        for i, (old, new) in enumerate(blocks):
            n_old = text.count(old)
            if n_old == 0 and new in text:
                print('  [ALREADY] %s 块%d：已是新版' % (fname, i + 1))
                continue
            if n_old != 1:
                print('  [FAIL] %s 块%d：命中 %d 次（必须恰好 1）'
                      % (fname, i + 1, n_old))
                rc = 1
                continue
            text = text.replace(old, new, 1)
            changed = True
            print('  [SYNCED] %s 块%d' % (fname, i + 1))

        if changed:
            if args.dry_run:
                print('[dry-run] %s 未写盘' % fname)
                continue
            out = text.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else text
            with open(pkg_p, 'wb') as f:
                f.write(out.encode('utf-8'))
            print('[write] %s  %d B  sha256=%s'
                  % (fname, os.path.getsize(pkg_p), sha(pkg_p)[:16]))

        # ✅ 收尾：与仓库版**归一化后逐字节一致**
        if norm_sha(repo_p) == norm_sha(pkg_p):
            print('[OK] %s 包内 == 仓库（归一化后）' % fname)
        else:
            print('[MISMATCH] %s 包内 != 仓库 ⇒ 需检查' % fname)
            rc = 1

    print('\n结论：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
