r"""app014b_build_v15_dir.py —— 建 v1.5 干净客户包目录（APP-014② 第①步）

做什么
------
从 `Confucius4_LiveCaption_v1.4/`（已含本轮代码 + README 改动）复制出
`Confucius4_LiveCaption_v1.5/`：

- **排除规则与 `pkg_exclude.py` 完全同一口径**（单一数据源）
  ⇒ 编译缓存 / `.bak` 备份 / `_backup*` 目录 / `__pycache__`（非 python/ 下）
  都不会进新目录；
- **排除历史残留**：v1.4 目录里的 `results/**` 保留（MANIFEST notes 承诺过），
  但 `*.tmp` / `*.zip.tmp` / `*.log` 之类的临时产物一律不带；
- 大目录（`models/` 12 GB、`python/` 831 MB）用 **硬链接**优先，
  硬链接不可用时退回复制 ⇒ 省时间省空间。

🔴 为什么大目录用硬链接
----------------------
`models/` + `python/` 约 13 GB，纯复制要几分钟且**抢磁盘 IO**；
而同一卷上硬链接与复制**内容完全一致**（`os.stat` 的 st_ino 相同、
SHA256 相同）⇒ 对打包产物**没有任何区别**，但省掉一次全量拷贝。

⚠️ **硬链接的安全边界**：v1.5 目录里的文件与 v1.4 目录里的文件是**同一份数据**。
⇒ 如果后续要**修改** v1.5 里的某个模型文件，**必须先 `shutil.copy2` 断开硬链接**，
否则会连带改到 v1.4！本脚本在「需要改写的文件」上**一律用真实复制**
（README / MANIFEST / app 代码），不使用硬链接。

用法
----
    python app014b_build_v15_dir.py --src <v1.4目录> --dst <v1.5目录>
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
import pkg_exclude  # noqa: E402

# ── 大目录：优先硬链接 ────────────────────────────────────────────────
HARDLINK_DIRS = ('models', 'python')

# ── 历史残留 / 临时产物（额外的排除，与 pkg_exclude 互补）────────────
EXTRA_SKIP_SUFFIX = ('.tmp', '.log', '.old', '.orig', '.swp', '.part')
EXTRA_SKIP_NAMES = ('Thumbs.db', 'desktop.ini', '.DS_Store')

# 🔴 这些文件**必须真实复制**（后续会改写；硬链接会连带改到 v1.4）
REAL_COPY_FILES = ('README_zh.md', 'README_en.md', 'app/MANIFEST.json')


def sha256(path, n=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(n), b''):
            h.update(chunk)
    return h.hexdigest()


def should_extra_skip(rel):
    fn = rel.rsplit('/', 1)[-1]
    if fn in EXTRA_SKIP_NAMES:
        return True
    low = fn.lower()
    return any(low.endswith(s) for s in EXTRA_SKIP_SUFFIX)


def try_hardlink(src, dst):
    """尝试硬链接；成功返回 True，失败返回 False（调用方退回复制）。"""
    try:
        os.link(src, dst)
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--dst', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    dst = os.path.abspath(args.dst)
    if not os.path.isdir(src):
        raise SystemExit(f'源目录不存在: {src}')
    if os.path.exists(dst) and os.listdir(dst):
        raise SystemExit(f'目标目录非空（请先清空）: {dst}')

    t0 = time.time()
    n_link = n_copy = 0
    n_bytes = 0
    skipped = []

    # 用 pkg_exclude 的同一口径遍历（它已处理缓存/备份/__pycache__）
    for rel, size in pkg_exclude.iter_package_files(src):
        if should_extra_skip(rel):
            skipped.append(rel)
            continue
        s_full = os.path.join(src, rel.replace('/', os.sep))
        d_full = os.path.join(dst, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(d_full), exist_ok=True)

        top = rel.split('/', 1)[0]
        use_link = (top in HARDLINK_DIRS
                    and rel not in REAL_COPY_FILES
                    and not rel.startswith('python/'))
        if use_link and try_hardlink(s_full, d_full):
            n_link += 1
        else:
            shutil.copy2(s_full, d_full)
            n_copy += 1
        n_bytes += size
        if (n_link + n_copy) % 2000 == 0:
            print(f'  ... {n_link + n_copy} 文件')

    print()
    print(f'硬链接 {n_link} 个 / 真实复制 {n_copy} 个'
          f'（{n_bytes / 1024 ** 3:.2f} GB 逻辑大小）')
    if skipped:
        print(f'额外排除的历史残留 {len(skipped)} 个：')
        for r in skipped[:20]:
            print('   -', r)

    # ── 校验：抽样比对 SHA256（硬链接 vs 复制 都要一致）────────────
    if not args.dry_run:
        print()
        print('抽样 SHA256 校验（硬链接 / 复制 各取若干）：')
        samples = []
        for rel, _sz in pkg_exclude.iter_package_files(src):
            top = rel.split('/', 1)[0]
            if top in HARDLINK_DIRS and rel not in samples:
                samples.append(rel)
            if len(samples) >= 6:
                break
        samples += ['app/live_caption_app.py', 'app/translator.py',
                    'README_zh.md', 'README_en.md']
        bad = 0
        for rel in samples:
            s = os.path.join(src, rel.replace('/', os.sep))
            d = os.path.join(dst, rel.replace('/', os.sep))
            a, b = sha256(s), sha256(d)
            ok = (a == b)
            if not ok:
                bad += 1
            print(f'  [{"OK" if ok else "不符"}] {rel}  {a[:12]}')
        if bad:
            raise SystemExit(f'❌ {bad} 个文件内容不一致 ⇒ 中止')

        # ── 硬链接隔离性检查 ──────────────────────────────────────
        # ⚠️ 真正要保证的不是「写 v1.5 不影响 v1.4」（那对**会改写的文件**
        #    必须成立），而是：
        #   ① **会改写的文件**（README / MANIFEST）必须是**真实副本**
        #      （inode 不同）⇒ 改 v1.5 绝不连带改 v1.4；
        #   ② **只读的大目录**（models/）可以用硬链接（省 13 GB 拷贝）。
        print()
        print('硬链接隔离性检查：')
        bad = 0
        for rel in REAL_COPY_FILES:
            p14 = os.path.join(src, rel.replace('/', os.sep))
            p15 = os.path.join(dst, rel.replace('/', os.sep))
            if not (os.path.isfile(p14) and os.path.isfile(p15)):
                continue
            i14 = os.stat(p14).st_ino
            i15 = os.stat(p15).st_ino
            ok = (i14 != i15)
            if not ok:
                bad += 1
            print(f'  [{"OK" if ok else "共享inode"}] {rel}  '
                  f'v1.4 ino={i14} / v1.5 ino={i15}')
        if bad:
            raise SystemExit(
                f'❌ {bad} 个「会改写的文件」被硬链接了 ⇒ 改 v1.5 会连带改 v1.4'
                ' ⇒ 必须改成真实复制后重做')
        # 只读大目录：确认确实是硬链接（省了 13 GB 拷贝）
        for rel in ('models/qwen3tts/tokenizer/vocab.json',
                    'python/python.exe'):
            p14 = os.path.join(src, rel.replace('/', os.sep))
            p15 = os.path.join(dst, rel.replace('/', os.sep))
            if not (os.path.isfile(p14) and os.path.isfile(p15)):
                continue
            i14 = os.stat(p14).st_ino
            i15 = os.stat(p15).st_ino
            print(f'  [{"硬链接" if i14 == i15 else "真实复制"}] {rel}  '
                  f'ino v1.4={i14} / v1.5={i15}')
        print('  ⇒ 只读大目录用硬链接（内容逐字节相同，打包产物无区别）；'
              '会改写的文件一律真实副本。')

    print()
    print(f'耗时 {time.time() - t0:.0f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
