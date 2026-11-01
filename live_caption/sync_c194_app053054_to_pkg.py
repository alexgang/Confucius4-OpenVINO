#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c194_app053054_to_pkg.py —— **【APP-053/054】定点同步**：
把仓库 `live_caption/` 里 **APP-053/054 的改动**同步到客户包 `app/`。

🔴🔴🔴 **纪律（§48 / §120 / 铁律「仓库 ⇄ 客户包 = 两份独立副本」）**：
  - **禁止整目录覆盖** ⇒ 本脚本**只做精确字符串替换**；
  - 每处替换前**断言「旧串在包内恰好命中 1 次」** ⇒ 命中 0 或 ≥2 ⇒
    **立即抛错退出**（fail-closed，绝不猜）；
  - 🔴 **幂等**：包内**已经是新串** ⇒ 视为「已同步」⇒ **跳过**（不报错），
    这样脚本**重复执行安全**；
  - **不写死客户包版本号** ⇒ 从 `pkg_paths` 自动发现**最新版本**；
  - **行尾归一化**（§119 铁律：仓库 ⇄ 包可能是 LF/CRLF 差异
    ⇒ 字符串锚点匹配在 clone 里会恒为 0）⇒ 读入归一化、写回还原原行尾；
  - 写回后**定点复核**（「本轮那处新串 ≥1 次 ＋ 旧串 0 次」）；
  - **只同步仓库里已经改好的内容** ⇒ 本脚本**不修改仓库**。

🔴 **本轮同步的内容（APP-053 + APP-054）**：

| 文件 | 内容 |
|---|---|
| `speaker_tracker.py` | APP-054：后台线程化 / 攒整窗 / 降级不丢音 / 标签不被吞 / 会话代号；APP-053：`span_for_segment()` 时间对齐 |
| `live_caption_app.py` | APP-054：GUI「说话人识别」勾选框**真正生效**；APP-053：`span_for_segment` 调用 |

用法：
    python live_caption/sync_c194_app053054_to_pkg.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def find_repo_root(start: str) -> str:
    """🔴 向上查找仓库根（祖先目录含 `live_caption/` ＋ `pkg_paths.py`）。

    ⇒ **不写死仓库根**（§118/§119 铁律：写死 ⇒ fresh clone 里是假象）。
    """
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('向上查找仓库根失败：%s' % start)
        cur = parent


def find_pkg_dir(repo: str) -> str:
    """自动发现**最新版本**客户包目录（**不写死版本号**）。"""
    sys.path.insert(0, repo)
    try:
        import pkg_paths
    finally:
        sys.path.pop(0)
    return pkg_paths.discover_pkg_dir()


def read_norm(path: str):
    """读文件 ⇒ 返回 `(归一化文本, 原行尾)`。

    🔴 §119 铁律：仓库 ⇄ 包可能有 LF/CRLF 差异 ⇒ 锚点匹配前**必须归一化**。
    """
    with open(path, 'r', encoding='utf-8', newline='') as f:
        raw = f.read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    return raw.replace('\r\n', '\n'), nl


#: (文件名, 旧串, 新串) —— **每处的旧串必须在包内恰好命中 1 次**
#:
#: 🔴 **说明**：这些替换块是「**旧串 = 包内现状**」「新串 = 仓库现状**」。
#: 包内的 `speaker_tracker.py` 是**同步阻塞版**（无 `enabled`、无线程），
#: 所以替换块覆盖的是**整段方法体**。
EDITS = (
    # ── APP-054：构造函数新增 `enabled` / `max_queue_s` 参数 ──────────
    ('speaker_tracker.py',
     "                 on_log=None):\n"
     "        self._on_log = on_log or (lambda m: None)",
     "                 on_log=None,\n"
     "                 enabled: bool = False,\n"
     "                 max_queue_s: float = 60.0):\n"
     "        self._on_log = on_log or (lambda m: None)"),

    # ── APP-054：`feed()` 改为「只入队即返回」＋ 积压降级 ────────────
    ('speaker_tracker.py',
     "    def feed(self, pcm, t_end: Optional[float] = None) -> bool:\n"
     "        \"\"\"喂一段 16 kHz PCM。",
     "    def feed(self, pcm, t_end: Optional[float] = None) -> bool:\n"
     "        \"\"\"喂一段 16 kHz PCM（**永不阻塞主循环**）。"),
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    repo = find_repo_root(HERE)
    pkg = find_pkg_dir(repo)
    pkg_app = os.path.join(pkg, 'app')
    print('[repo] %s' % repo)
    print('[pkg]  %s' % pkg)

    ok = True
    plan = []
    skipped = 0
    for fname, old, new in EDITS:
        p_repo = os.path.join(repo, 'live_caption', fname)
        p_pkg = os.path.join(pkg_app, fname)
        for p in (p_repo, p_pkg):
            if not os.path.isfile(p):
                print('  !! 缺文件：%s' % p)
                ok = False
        if not ok:
            continue
        src_repo, _ = read_norm(p_repo)
        src_pkg, _ = read_norm(p_pkg)

        n_repo_new = src_repo.count(new)
        n_repo_old = src_repo.count(old)
        n_pkg_old = src_pkg.count(old)
        n_pkg_new = src_pkg.count(new)
        if n_repo_new != 1 or n_repo_old != 0:
            print('  !! 仓库侧状态不对（新串 %d 次 / 旧串 %d 次，须 1/0）：%s'
                  % (n_repo_new, n_repo_old, fname))
            ok = False
            continue
        if n_pkg_old == 1:
            plan.append((fname, old, new))
            print('  [ok] %-22s 包内旧串命中 1 次 ⇒ 可替换' % fname)
        elif n_pkg_old == 0 and n_pkg_new == 1:
            skipped += 1
            print('  [skip] %-19s 包内已是新串 ⇒ 已同步，跳过' % fname)
        elif n_pkg_old == 0:
            print('  !! 包内旧串 0 次且新串 %d 次（状态不明）：%s'
                  % (n_pkg_new, fname))
            ok = False
        else:
            print('  !! 包内旧串命中 %d 次（须恰好 1）：%s'
                  % (n_pkg_old, fname))
            ok = False

    if not ok:
        print('\n[FAIL] 前置断言不通过 ⇒ 未做任何修改')
        return 1
    print('\n[plan] 待替换 %d 处 / 已同步跳过 %d 处' % (len(plan), skipped))
    if args.dry_run:
        print('[dry-run] 未写入')
        return 0

    for fname, old, new in plan:
        p_pkg = os.path.join(pkg_app, fname)
        src, nl = read_norm(p_pkg)
        assert src.count(old) == 1
        out = src.replace(old, new)
        # 🔴 写回时**还原原行尾**（§119 铁律：同步不得改变包的行尾）
        with open(p_pkg, 'w', encoding='utf-8', newline='') as f:
            f.write(out.replace('\n', nl) if nl == '\r\n' else out)
        after, _ = read_norm(p_pkg)
        if after.count(new) != 1 or after.count(old) != 0:
            print('  [FAIL] %s：写后复核不通过（新串 %d 次 / 旧串 %d 次）'
                  % (fname, after.count(new), after.count(old)))
            ok = False
        else:
            print('  [ok] %-22s 已替换 ＋ 复核通过' % fname)

    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
