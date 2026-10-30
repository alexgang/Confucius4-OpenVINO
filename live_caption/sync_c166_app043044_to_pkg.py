#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""sync_c166_app043044_to_pkg.py —— §101 / APP-043 + APP-044：把**本会话自己的**
App 侧改动定点同步进客户包。

## 为什么必须做

APP-043 要求 App 进程**在任何 numpy / OpenVINO import 之前**限线程并记日志；
APP-044 要求客户包**带上**说话人识别的小模型与 ASR 的 SpeakerTracker 接口代码。

仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**（铁律）
⇒ **禁止整目录覆盖** ⇒ 本脚本用「**精确字符串替换 + 唯一命中断言**」。

## 🔴🔴🔴 本脚本的一条铁律：**插入块必须从仓库真实文件提取**

**不许在脚本源码里手写要插入的代码文本。**

原因（本轮真实踩到）：在 Python 三引号字符串里写 `newline='\n'`，
解析时 `\n` 会被解释成**真换行** ⇒ 写进客户包的代码变成
`'a', encoding='utf-8', newline='` + 真换行 + `')` ⇒ **语法错误**
⇒ 客户机启动即崩。

⇒ 做法：待插入的块**从仓库真实文件按行边界提取**（`slice_block()`）
⇒ 「仓库里是什么，包里就是什么」⇒ **不可能**再出现转义走样。
⇒ OLD（锚点）可以手写（不含需要转义的字符），但**必须逐字与包内一致**。

## 同步内容（本会话自己的 4 块）

1. `live_caption_app.py` 头部：**限线程 + 启动日志**（APP-043）
2. `speaker_tracker.py.__init__` / `._load()`：**包内资产接入**（APP-044）
3. `speaker_assets.py`：**新文件**（包内资产定位模块）
4. `tts_worker.py`：**§101 follow_speaker 回归修复**（决策分支 + `_log_keep_clone`）

## 纪律

- 每处替换都要求 **OLD 在目标文件中恰好命中 1 次**，否则中止。
- 幂等：目标里已有 NEW 的特征串 ⇒ 报 `[ALREADY]`。
- **不碰**并发会话的改动（`retry_pending` / `_retry_spk_labels` / `_spk_by_seg`）
  ⇒ 同步后必须复核这些特征串**仍在**包内。
- **写回后必须 `ast.parse` 校验语法** ⇒ 语法坏了要**立刻**发现，不能留给客户机。

## 用法

```
python sync_c166_app043044_to_pkg.py --pkg <包根> [--dry-run]
```
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
import sys

# ══════════════════════════════════════════════════════════════════
# 锚点（OLD）—— 纯 ASCII / 无需转义 ⇒ 可手写
# ══════════════════════════════════════════════════════════════════

# ① APP-043：live_caption_app.py 头部
APP_OLD = (
    "os.environ.setdefault('PYTHONUTF8', '1')\n"
    "os.environ.setdefault('PYTHONIOENCODING', 'utf-8')\n"
    "\n"
    "import numpy as np\n"
)

# ② APP-044：speaker_tracker.py.__init__
ST_INIT_OLD = (
    "        # seg -> 等待补标签的段（`pending=True`）\n"
    "        self._pending = set()\n"
    "        self._scripts_dir = scripts_dir\n"
    "        self._thr = thr\n"
)

# ③ APP-044：speaker_tracker.py._load()
ST_LOAD_OLD = (
    "            try:\n"
    "                if self._scripts_dir not in sys.path:\n"
    "                    sys.path.insert(0, self._scripts_dir)\n"
    "                from asr052_speaker_tracker_api import SpeakerTracker\n"
    "                self._tracker = SpeakerTracker(device=self.device,\n"
    "                                               seg_device=self.seg_device,\n"
    "                                               thr=self._thr)\n"
)

# ④ §101：tts_worker.py 决策分支
TW_OLD = (
    "        if spk:\n"
    "            self._apply_spk_voice(spk)\n"
    "        else:\n"
    "            self._fallback_to_preset('no_spk_label')\n"
)

# ⑤ §101：tts_worker.py 新方法（插在 _fallback_to_preset 之前）
TW_LOG_OLD = "    def _fallback_to_preset(self, why: str = ''):\n"

# ══════════════════════════════════════════════════════════════════
# 插入块（NEW）—— **从仓库真实文件按行边界提取**
# ══════════════════════════════════════════════════════════════════


def norm(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\r', '\n')


def slice_block(src: str, start_marker: str, end_marker: str,
                include_end: bool = False) -> str:
    """从 `src` 里提取 `[start_marker, end_marker)` 之间的文本。

    ⚠️ `start_marker` 必须**唯一**命中（否则抛错）⇒ 避免取错块。
    """
    i = src.find(start_marker)
    if i < 0:
        raise RuntimeError('起点标记未找到：%r' % start_marker[:60])
    if src.find(start_marker, i + 1) >= 0:
        raise RuntimeError('起点标记**不唯一**：%r' % start_marker[:60])
    j = src.find(end_marker, i + len(start_marker))
    if j < 0:
        raise RuntimeError('终点标记未找到：%r' % end_marker[:60])
    if include_end:
        j += len(end_marker)
    return src[i:j]


def build_blocks(repo: str) -> dict:
    """从仓库真实文件里抽出 5 个插入块。"""
    live = os.path.join(repo, 'live_caption')

    # ① APP-043 限线程 + 日志：仓库 `live_caption_app.py` 里，
    #    从 APP-043 注释块起点到 `import numpy as np` 之前。
    app_src = norm(open(os.path.join(live, 'live_caption_app.py'),
                        'r', encoding='utf-8', newline='').read())
    app_block = slice_block(
        app_src,
        "# \U0001f534\U0001f534\U0001f534 APP-043：",
        "import numpy as np\n")

    # ②③ APP-044 speaker_tracker：仓库里的新块
    st_src = norm(open(os.path.join(live, 'speaker_tracker.py'),
                       'r', encoding='utf-8', newline='').read())
    st_init_block = slice_block(
        st_src,
        "        # \U0001f534\U0001f534\U0001f534 APP-044：**优先用包内资产**",
        "\n    # ── ① 加载（惰性）")
    st_load_block = slice_block(
        st_src,
        "                # \U0001f534 APP-044：包内无资产且无研发机回退",
        "                self.available = True\n")

    # ④⑤ §101 tts_worker
    tw_src = norm(open(os.path.join(live, 'tts_worker.py'),
                       'r', encoding='utf-8', newline='').read())
    tw_dec_block = slice_block(
        tw_src,
        "        # \U0001f534\U0001f534\U0001f534 §101（follow_speaker 回归）：",
        "\n        if is_babelvox:")
    tw_log_block = slice_block(
        tw_src,
        "    def _log_keep_clone(self):",
        "\n    def _fallback_to_preset(self, why: str = ''):")

    # 组装 NEW
    app_new = (
        "os.environ.setdefault('PYTHONUTF8', '1')\n"
        "os.environ.setdefault('PYTHONIOENCODING', 'utf-8')\n"
        "\n" + app_block + "import numpy as np\n")

    st_init_new = (
        "        # seg -> 等待补标签的段（`pending=True`）\n"
        "        self._pending = set()\n"
        "        self._thr = thr\n" + st_init_block)

    st_load_new = (
        "            try:\n" + st_load_block + "                self.available = True\n")

    tw_new = tw_dec_block
    tw_log_new = tw_log_block + "    def _fallback_to_preset(self, why: str = ''):\n"

    return dict(app_new=app_new,
                st_init_new=st_init_new,
                st_load_new=st_load_new,
                tw_new=tw_new,
                tw_log_new=tw_log_new)


# 幂等特征串
APP_MARK = "APP-043：**在任何 numpy / OpenVINO import 之前**限线程"
ST_MARK = "APP-044：**优先用包内资产**（客户机形态）"
ST_LOAD_MARK = "APP-044：**把包内 IR 路径传进去**"
TW_MARK = "§101（follow_speaker 回归）：`spk=None` 有**两种完全不同的语义**"
TW_LOG_MARK = "def _log_keep_clone(self):"

# 并发会话的改动特征串（同步后**必须仍在**）
CONCURRENT_MARKS = {
    'speaker_tracker.py': ['retry_pending'],
    'live_caption_app.py': ['_retry_spk_labels', '_spk_by_seg'],
}


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def patch_exact(path: str, old: str, new: str, mark: str,
                dry: bool = False) -> str:
    """**精确字符串替换 + 唯一命中断言**（铁律）。"""
    with open(path, 'rb') as f:
        raw = f.read()
    use_crlf = b'\r\n' in raw
    text = raw.decode('utf-8')
    if use_crlf:
        text = text.replace('\r\n', '\n')

    if mark in text:
        return '[ALREADY]'
    n = text.count(old)
    if n != 1:
        raise RuntimeError('OLD 命中 %d 次（要求恰好 1 次）' % n)
    patched = text.replace(old, new, 1)

    # 🔴 写回前**必须**语法校验 ⇒ 语法坏了立刻发现，不留给客户机。
    try:
        ast.parse(patched)
    except SyntaxError as e:
        raise RuntimeError('替换后语法错误（已中止，未落盘）：%s' % e)

    if dry:
        return '[DRY]'
    if use_crlf:
        patched = patched.replace('\n', '\r\n')
    with open(path, 'wb') as f:
        f.write(patched.encode('utf-8'))
    return '[SYNCED]'


def copy_new_file(src: str, dst: str, dry: bool = False) -> str:
    """新增文件：整文件复制（文件在仓库是**新建**的 ⇒ 不存在覆盖风险）。"""
    if not os.path.isfile(src):
        raise RuntimeError('源文件不存在：%s' % src)
    if os.path.exists(dst):
        if sha256_file(src) == sha256_file(dst):
            return '[ALREADY]'
        raise RuntimeError('目标已存在且内容不同，拒绝覆盖：%s' % dst)
    if dry:
        return '[DRY]'
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, 'rb') as fi, open(dst, 'wb') as fo:
        fo.write(fi.read())
    return '[SYNCED]'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pkg = args.pkg
    if not pkg:
        print('请用 --pkg 指定客户包根目录')
        return 2
    app_dir = os.path.join(pkg, 'app')

    print('仓库 = %s' % repo)
    print('客户包 = %s' % pkg)
    if args.dry_run:
        print('（dry-run：不落盘）')
    print()

    try:
        B = build_blocks(repo)
    except RuntimeError as e:
        print('  [FAIL] 从仓库提取插入块失败：%s' % e)
        return 1

    ok = True
    try:
        st = patch_exact(os.path.join(app_dir, 'live_caption_app.py'),
                         APP_OLD, B['app_new'], APP_MARK, args.dry_run)
        print('  %-9s live_caption_app.py（APP-043 限线程+日志）' % st)

        st = patch_exact(os.path.join(app_dir, 'speaker_tracker.py'),
                         ST_INIT_OLD, B['st_init_new'], ST_MARK, args.dry_run)
        print('  %-9s speaker_tracker.py __init__（APP-044 包内资产）' % st)

        st = patch_exact(os.path.join(app_dir, 'speaker_tracker.py'),
                         ST_LOAD_OLD, B['st_load_new'], ST_LOAD_MARK, args.dry_run)
        print('  %-9s speaker_tracker.py _load()（APP-044 IR 传参）' % st)

        st = copy_new_file(os.path.join(repo, 'live_caption', 'speaker_assets.py'),
                           os.path.join(app_dir, 'speaker_assets.py'), args.dry_run)
        print('  %-9s speaker_assets.py（新增文件）' % st)

        st = patch_exact(os.path.join(app_dir, 'tts_worker.py'),
                         TW_OLD, B['tw_new'], TW_MARK, args.dry_run)
        print('  %-9s tts_worker.py 决策分支（§101 follow_speaker 回归）' % st)

        st = patch_exact(os.path.join(app_dir, 'tts_worker.py'),
                         TW_LOG_OLD, B['tw_log_new'], TW_LOG_MARK, args.dry_run)
        print('  %-9s tts_worker.py _log_keep_clone（§101）' % st)
    except RuntimeError as e:
        print('  [FAIL] %s' % e)
        return 1

    # ── 复核：并发会话的改动**必须仍在**包内 ───────────────────────
    print()
    print('复核（并发会话的改动必须仍在包内）：')
    for name, marks in CONCURRENT_MARKS.items():
        p = os.path.join(app_dir, name)
        t = open(p, 'r', encoding='utf-8', newline='').read()
        miss = [m for m in marks if m not in t]
        if miss:
            print('  [FAIL] %s 丢失并发会话特征串：%s' % (name, miss))
            ok = False
        else:
            print('  [OK]   %s 保留 %s' % (name, marks))

    # ── 复核：包内 app/*.py 全部可编译 ─────────────────────────────
    print()
    print('复核（包内 app/*.py 语法）：')
    bad = []
    for name in sorted(os.listdir(app_dir)):
        if not name.endswith('.py'):
            continue
        p = os.path.join(app_dir, name)
        try:
            ast.parse(norm(open(p, 'r', encoding='utf-8',
                                newline='').read()))
        except SyntaxError as e:
            bad.append('%s: %s' % (name, e))
    if bad:
        ok = False
        for b in bad:
            print('  [FAIL] %s' % b)
    else:
        print('  [OK]   包内 app/*.py 全部可编译')

    print()
    if ok:
        for name in ('live_caption_app.py', 'speaker_tracker.py',
                     'speaker_assets.py', 'tts_worker.py'):
            p = os.path.join(app_dir, name)
            if os.path.isfile(p):
                print('  %-24s %8d B  sha256=%s'
                      % (name, os.path.getsize(p), sha256_file(p)))
    else:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
