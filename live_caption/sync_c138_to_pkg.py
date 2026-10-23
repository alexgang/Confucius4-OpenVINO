r"""sync_c138_to_pkg.py — 客户包 v1.4 的代码同步（APP-007 交付修正）

背景
----
v1.3 客户包的 `app/` 是**旧版**（2112 行的 `live_caption_app.py`、
旧四行字幕、旧引擎下拉）。v1.4 要把仓库 `live_caption/` 的成果带进去：

| 动作 | 文件 | 来源 | 为什么 |
|---|---|---|---|
| 覆盖 | `live_caption_app.py` | 仓库 | GUI 四项改造（三分区配置 / 状态栏迁移 / 字幕两栏 / 鼠标穿透）+ APP-004 设备自选 + ASR §10/§11 |
| 覆盖 | `translator.py` | 仓库 | `TranslationService.set_device()`（APP-004③：GUI 翻译设备切换必需） |
| 覆盖 | `audio_source.py` | 仓库 | 回环立体声混合（ASR §10） |
| 覆盖 | `device_config.py` | 仓库 | **CPU 从设备清单移除**（用户决定 2026-10-23）—— GUI 下拉与 CLI 设备解析共用 |
| 新增 | `tts_service.py` | 仓库 | 新版 GUI 的 TTS 面板 `from tts_service import TTSService` 必需 |
| 新增 | `win_clickthrough.py` | 仓库 | 鼠标穿透必需 |
| 覆盖 | `tts_worker.py` | 仓库 | **import 死锁修复**（APP-FIX-20261023，见 `sync_c137_to_pkg.py`）—— 2026-10-23 21:05 实测发现本脚本原 FILES 列表**漏了它**，导致 v1.4 包内 `tts_worker.py` 仍是 38670 B 旧版 ⇒ 客户包会重现「worker 永不 emit ready」死锁 |

做法
----
**整文件覆盖 + 逐行差异留证 + SHA256 幂等**。

🔴 为什么这里可以用「整文件覆盖」而不用定点字符串替换：
   逐行 `difflib` 比对（忽略 CRLF/LF）证明包内 `live_caption_app.py`
   独有的 153 行**全是旧版代码**（旧四行字幕 `self.final/self.mt/self.draft`、
   旧引擎下拉 `self.cb_engine`、旧 `make_engine`）⇒ **包内没有任何
   客户包专属定制**，整文件覆盖不会丢东西。
   （`audio_source.py` 包内独有的 8 行是 `SOURCES_BI`（中英双语标签），
   但全仓 grep 无任何引用 ⇒ 历史遗留，可丢弃。）

⚠️ 换行符：仓库是 **CRLF**，包内是 **LF** ⇒ 写入时统一转 LF。

⚠️ 备份**必须放包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中
   而污染包，C-133 教训）⇒ 备份目录 `C:\Users\Trekker-PTL\pkg_backup_app014`。

⚠️ 编号说明：`c137` 已被 TTS 并行会话占用（`sync_c137_to_pkg.py`
   = tts_worker 的 import 死锁修复）⇒ 本脚本用 `c138`，互不覆盖。

用法
----
    python sync_c138_to_pkg.py [pkg_app_dir] [--report <报告输出路径>]

默认目标：按 `Confucius4_LiveCaption_vX.Y` 自动发现**版本号最大**的
客户包目录（排除 `.bak` / `backup` / `_pre_` 目录），不写死版本号。
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'live_caption')

# 包外备份目录（绝不能放包内）
BACKUP_ROOT = r'C:\Users\Trekker-PTL\pkg_backup_app014'

# (包内文件名, 模式) —— 模式：'overwrite' 覆盖 / 'new' 新增
FILES = [
    ('live_caption_app.py', 'overwrite'),
    ('translator.py', 'overwrite'),
    ('audio_source.py', 'overwrite'),
    ('device_config.py', 'overwrite'),
    ('tts_service.py', 'new'),
    ('win_clickthrough.py', 'new'),
    # 🔴 2026-10-23 21:05 补入：import 死锁修复（APP-FIX-20261023）。
    #    原列表漏了它 ⇒ v1.4 包内 tts_worker.py 是未修复的 38670 B 旧版
    #    ⇒ 客户机 TTS worker 永不 emit `ready`、主进程永远 `state=loading`。
    #    已用 `sync_c137_to_pkg.py`（定点替换 + assert count==1）单独修过一次，
    #    这里再补进来是为了**下次同步不会漏**（幂等：已一致会走 skipped 分支）。
    ('tts_worker.py', 'overwrite'),
]


# ── 客户包自动发现 ────────────────────────────────────────────────────
def discover_pkg_app(home: str = r'C:\Users\Trekker-PTL') -> str:
    """按 `Confucius4_LiveCaption_vX.Y` 自动发现**版本号最大**的包。

    🔴 必须排除 `.bak` / `backup` / `_pre_` 目录 —— 否则会选中
       `v1.0.bak_20261020`（历史教训）。
    """
    best = None
    best_key = None
    for name in os.listdir(home):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        low = name.lower()
        if '.bak' in low or 'backup' in low or '_pre_' in low:
            continue
        app = os.path.join(home, name, 'app')
        if not os.path.isdir(app):
            continue
        ver = name.rsplit('_v', 1)[-1]
        try:
            key = tuple(int(x) for x in ver.split('.'))
        except ValueError:
            continue
        if best_key is None or key > best_key:
            best_key = key
            best = app
    if best is None:
        raise SystemExit('[客户包] 未找到 Confucius4_LiveCaption_vX.Y/app')
    return best


def _norm(text: str) -> str:
    """统一换行符为 LF（仓库 CRLF / 包内 LF）。"""
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _read(path: str) -> str:
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return _norm(f.read())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _diff_report(pkg_text: str, repo_text: str, name: str) -> dict:
    """按行 difflib 统计（忽略换行符差异）。"""
    a = pkg_text.splitlines()
    b = repo_text.splitlines()
    sm = difflib.SequenceMatcher(None, a, b)
    pkg_only = 0
    repo_only = 0
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag in ('delete', 'replace'):
            pkg_only += i2 - i1
        if tag in ('insert', 'replace'):
            repo_only += j2 - j1
        hunks.append(dict(tag=tag, pkg_lines=[i1 + 1, i2],
                         repo_lines=[j1 + 1, j2],
                         pkg_text=a[i1:i2][:20], repo_text=b[j1:j2][:20]))
    return dict(file=name, pkg_lines=len(a), repo_lines=len(b),
                pkg_only_lines=pkg_only, repo_only_lines=repo_only,
                hunks=hunks[:60])


def main():
    ap = argparse.ArgumentParser(description='客户包 v1.4 代码同步（整文件覆盖 + 留证）')
    ap.add_argument('pkg_app', nargs='?', default=None,
                    help='客户包 app 目录（默认自动发现版本号最大的包）')
    ap.add_argument('--report', default=None, help='差异报告输出路径（JSON）')
    ap.add_argument('--dry-run', action='store_true', help='只报告，不写入')
    args = ap.parse_args()

    pkg_app = args.pkg_app or discover_pkg_app()
    pkg_app = os.path.abspath(pkg_app)
    if not os.path.isdir(pkg_app):
        raise SystemExit(f'[客户包] 目录不存在: {pkg_app}')
    print(f'[客户包] {pkg_app}')
    print(f'[仓库  ] {SRC}')
    print()

    os.makedirs(BACKUP_ROOT, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')

    report = dict(pkg_app=pkg_app, stamp=stamp, files=[])
    changed = 0
    skipped = 0

    for name, mode in FILES:
        repo_path = os.path.join(SRC, name)
        pkg_path = os.path.join(pkg_app, name)
        if not os.path.isfile(repo_path):
            print(f'[FAIL] 仓库源文件不存在: {repo_path}')
            return 1
        repo_text = _read(repo_path)
        repo_sha = _sha256_text(repo_text)

        exists = os.path.isfile(pkg_path)
        pkg_text = _read(pkg_path) if exists else ''

        entry = dict(file=name, mode=mode, existed=exists,
                     repo_sha256=repo_sha, repo_bytes=len(repo_text.encode('utf-8')),
                     repo_lines=len(repo_text.splitlines()))

        if exists and _sha256_text(pkg_text) == repo_sha:
            print(f'[跳过] {name:26s} 已与仓库一致（SHA256 {repo_sha[:16]}…）')
            entry.update(status='skipped', pkg_sha256=repo_sha)
            report['files'].append(entry)
            skipped += 1
            continue

        if exists:
            d = _diff_report(pkg_text, repo_text, name)
            entry.update(diff=d)
            print(f'[覆盖] {name:26s} 包内独有行 {d["pkg_only_lines"]:>4} '
                  f'/ 仓库独有行 {d["repo_only_lines"]:>4}  '
                  f'（包内 {d["pkg_lines"]} 行 → 仓库 {d["repo_lines"]} 行）')
            if not args.dry_run:
                bak = os.path.join(BACKUP_ROOT, f'{stamp}_{name}.bak')
                shutil.copy2(pkg_path, bak)
                entry['backup'] = bak
        else:
            print(f'[新增] {name:26s} 包内原本没有（仓库 {len(repo_text.splitlines())} 行）')

        if not args.dry_run:
            with open(pkg_path, 'w', encoding='utf-8', newline='') as f:
                f.write(repo_text)
            # 回读校验
            back = _read(pkg_path)
            if _sha256_text(back) != repo_sha:
                print(f'[FAIL] {name} 写入后 SHA256 不一致')
                return 1
            st = os.stat(pkg_path)
            entry.update(status='written',
                         pkg_sha256=repo_sha,
                         pkg_bytes=st.st_size,
                         pkg_mtime=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)))
            print(f'        → {pkg_path}')
            print(f'        → {st.st_size:,} B  SHA256 {repo_sha}')
            print(f'        → 备份 {entry.get("backup", "（新文件，无需备份）")}')
        else:
            entry['status'] = 'dry-run'
        report['files'].append(entry)
        changed += 1

    print()
    print(f'合计：写入 {changed} 个 / 跳过 {skipped} 个 / 备份目录 {BACKUP_ROOT}')

    if args.report:
        with open(args.report, 'w', encoding='utf-8', newline='') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f'差异报告已落盘: {args.report}  '
              f'({os.path.getsize(args.report):,} B)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
