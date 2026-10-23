r"""pkg_exclude.py —— 客户包排除规则（**单一数据源**）

C-133 / APP-002：客户包瘦身（删除编译缓存等不进包的文件）。

为什么要有这个模块
------------------
「打包要剔的东西」「MANIFEST 要统计的东西」「物理清理要删的东西」
**必须是同一套规则**，否则会出现两种典型故障：

  1. 删了但下次打包又带进去 —— 打包脚本和清理脚本各写一份规则；
  2. 打包剔了但源目录还在 —— 客户包源目录本身还是脏的。

所以规则只在这里写一份，`pack_v13.py` / `fix_manifest_v13d.py` /
`update_manifest_v13.py` 全部 `import` 本模块。

**本模块刻意零依赖**（只用 stdlib、不 import 仓库里的任何其他模块），
这样从任意 CWD 用 `python <脚本路径>` 运行都能找到它。

排除项与理由
------------
| 排除 | 理由 |
|---|---|
| `ov_cache/` | OpenVINO 编译缓存。GPU blob 头写死 `ie_version`（实测 `"2026.4.1-22982-e213a147257-release"`），oneDNN `*.cl_cache` 绑 CPU 微架构 ⇒ 换机器/换 OV 版本基本不命中。开发机实测长到 **4.1 GB**（单个 decoder blob 1.65 GB），压缩率只有 88%（已编译二进制），**删比压划算** |
| `npu_cache/` | 同上（NPU 插件编译缓存） |
| `mt_cache/` | 翻译模型编译缓存。`translator.py` 默认就写用户目录，但若有人显式传相对路径会在包内生成 |
| `app/reports/`、`reports/` | 运行期报告输出，不是交付物 |
| `*.bak*` | 开发期备份（`.bak_c105` / `.bak_instruct_20261022` / `.bak_mtdev_20261019` …） |
| `results/**/*_spoken.*` | 🔴 **内部会议录音的转写/翻译**（APP-003①）。`results/mt2_acc_outputs/int8_gpu_spoken.txt` 第 2 行是「[REDACTED-内部会议引文]」⇒ 属 BRIEF 规定的「会议录音不能进客户包」 |
| `results/mt2_memory.json` | 🔴 **同样含内部会议内容**（APP-003①，reviewer 未点名，本模块实测发现）。该文件的 `out` 字段是「[REDACTED-内部会议引文]—— 是 `spoken` 语料的译文示例 |

**刻意保留**
| 保留 | 理由 |
|---|---|
| `python/**/__pycache__` | 包内 Python 恒为 3.12，pyc 版本固定 ⇒ 保留可省客户机首次启动 1~5 s 重编译。代价仅压缩后约 5 MB |
| `site-packages/pip/`、`ensurepip/` | `app/live_caption_app.py` 有「pip install soundcard（不需要 ffmpeg）」的引导文案，而 `soundcard` **不在包内** ⇒ 必须保留 pip 客户才能自行装依赖 |
| `models/tokenizer/` | 孤儿目录（不在 `_MODEL_ALIASES`、无代码引用、内容与 `decoder-gpu-int8/` 内同名文件逐字节相同）。**零风险可剔，但收益仅 15 MB**，本轮按用户决策保留 |
| `results/`（除 `_spoken` 与 `mt2_memory.json`） | `MANIFEST.json` 的 notes 已两次宣称「完整矩阵与逐句输出随包附在 `results\`」⇒ 保留并打进包，让承诺成立。**但内部会议内容必须剔掉**（APP-003①）⇒ MANIFEST 的 notes 文案也要同步改成「公开新闻语料的部分」 |
| `python/Lib/tkinter/`、`python/tcl/` | GUI 依赖，**绝不能剔** |

设计要点
--------
1. **按目录名匹配，不按完整相对路径**。
   `backends.py:279` / `:440` 的 `cache_dir: str = "./ov_cache"` 是 **CWD 相对**，
   而 `Start_LiveCaption.bat` 有 `cd /d "%~dp0"` ⇒ CWD = 包根 ⇒ 会创建
   `<包根>/ov_cache/`（**不是** `app/ov_cache/`）。
   按目录名匹配天然同时覆盖根级与 `app/` 级两种位置。

2. **路径前缀必须带尾 `/`**。
   `app/reports/` 只匹配目录下的文件；写成 `app/reports` 会误伤
   `app/reports_zh.md` 一类同名文件。

3. **MANIFEST 自身不计入 `files`/`bytes`**（见 `package_stats` 的 `skip` 参数）。
   否则产生自引用：MANIFEST 的大小取决于它自己写的 `bytes` 字段。

4. **内部会议内容必须排除**（APP-003①）。
   `results/` 里混着两类语料：
   - `en2zh` / `zh2en`（各 200 句）= **公开新闻语料**（wmt24pp，Vicente Siso 画展报道）⇒ 可进包
   - `spoken` = **内部会议录音**的转写/翻译 ⇒ **禁止进包**
   判定用两条独立规则（文件名含 `_spoken` + 精确点名 `mt2_memory.json`），
   都限定在 `results/` 前缀下，避免误伤别处同名文件。
"""

from __future__ import annotations

import os
import re

__all__ = [
    'SKIP_DIR_NAMES',
    'KEEP_PYCACHE_UNDER',
    'SKIP_PATH_PREFIXES',
    'SKIP_FILE_RE',
    'SKIP_DIR_PREFIXES',
    'SPOKEN_FILE_RE',
    'RESULTS_DIR',
    'INTERNAL_EXACT',
    'is_excluded',
    'iter_package_files',
    'package_stats',
    'iter_excluded',
]

# ── 按**目录名**排除（任意层级）──────────────────────────────────────
# 注意：不含 '__pycache__' —— 它由 KEEP_PYCACHE_UNDER 做例外处理。
SKIP_DIR_NAMES = frozenset({
    'ov_cache',    # OpenVINO 编译缓存（实测 4181 MB）
    'npu_cache',   # NPU 插件编译缓存
    'mt_cache',    # 翻译模型编译缓存
})

# 例外：这些顶层目录下的 __pycache__ **保留**
# （包内 Python 恒为 3.12，pyc 版本固定 ⇒ 保留可省首次启动 1~5 s）
KEEP_PYCACHE_UNDER = frozenset({'python'})

# ── 按**路径前缀**排除（必须带尾 '/'）──────────────────────────────
SKIP_PATH_PREFIXES = (
    'app/reports/',
    'reports/',
)

# ── 按**文件名**排除（开发期备份）──────────────────────────────────
# 用 r'\.bak'（不限定后缀形态）而不是 r'\.bak_[a-z0-9]+$' ——
# 后者会漏掉 .bak_instruct_20261022 / .bak_mtdev_20261019 / .bak_audio_20261020。
SKIP_FILE_RE = re.compile(r'\.bak', re.I)

# ── 🔴 内部会议内容排除（APP-003①）─────────────────────────────────
# 客户包 `results/` 下有**内部会议录音**的转写/翻译，属于 BRIEF 规定的
# 「会议录音不能进客户包」。这里按**两条独立规则**排除：
#
# ① `*_spoken.*` —— 文件名带 `_spoken` 的一律排除（8 个文件：
#    {int4,int8,bf16}_{gpu,npu}_spoken.{json,txt}）
# ② `results/mt2_memory.json` —— **文件名不含 _spoken**，但它的 `out`
#    字段是「[REDACTED-内部会议引文]⇒ 同样是 spoken 语料的译文，
#    必须单独点名排除（reviewer 未点名，本模块实测发现）
#
# ⚠️ 规则**只对 results/ 生效** —— 别处叫 `_spoken` 的文件不误伤。
SPOKEN_FILE_RE = re.compile(r'_spoken', re.I)
RESULTS_DIR = 'results/'

# 精确点名的内部内容文件（相对包根）
INTERNAL_EXACT = (
    'results/mt2_memory.json',
)

# ── 供 pack_v13.py 做「目录前缀」断言用（带尾 '/'，零假阳性）──────
SKIP_DIR_PREFIXES = tuple(
    f'{p}/' for p in (
        'app/ov_cache',
        'app/npu_cache',
        'app/mt_cache',
        'ov_cache',
        'npu_cache',
        'mt_cache',
    )
) + SKIP_PATH_PREFIXES


def _top_dir(relpath: str) -> str:
    """相对路径的第一段（顶层目录名）；顶层文件返回 ''。"""
    return relpath.split('/', 1)[0] if '/' in relpath else ''


def is_excluded(relpath: str, top_dir: str = None) -> bool:
    """判断相对路径（'/' 分隔）是否应从客户包中排除。

    参数
    ----
    relpath : 相对包根的路径，'/' 分隔，例如 'app/ov_cache/x.xml'
    top_dir : 该路径所在的最顶层目录名。缺省时从 relpath 推断
              （推断对顶层文件正确，但嵌套目录会取到首段 —— 调用方
               最好显式传，见 `iter_package_files`）。
    """
    if top_dir is None:
        top_dir = _top_dir(relpath)

    # 1) 文件名命中备份规则
    if SKIP_FILE_RE.search(relpath.rsplit('/', 1)[-1]):
        return True

    # 2) 路径前缀
    for prefix in SKIP_PATH_PREFIXES:
        if relpath.startswith(prefix):
            return True

    # 2.5) 🔴 内部会议内容（APP-003①）
    if relpath in INTERNAL_EXACT:
        return True
    if relpath.startswith(RESULTS_DIR) and SPOKEN_FILE_RE.search(relpath):
        return True

    # 3) __pycache__：python/ 下保留，其余排除
    if '__pycache__' in relpath.split('/'):
        return top_dir not in KEEP_PYCACHE_UNDER

    # 4) 编译缓存目录名（任意层级）
    for seg in relpath.split('/')[:-1]:
        if seg in SKIP_DIR_NAMES:
            return True

    return False


def iter_package_files(pkg_root: str):
    """遍历包根下**要进包**的文件，产出 (relpath, size)。

    实现方式是在 `os.walk` 里 **prune 目录**（而不是写完再判断），
    这样连遍历开销都省了，也不会留下空目录条目。

    relpath 用 '/' 分隔；size 是原始字节数。
    """
    pkg_root = os.path.abspath(pkg_root)
    for dirpath, dirnames, filenames in os.walk(pkg_root):
        rel_dir = os.path.relpath(dirpath, pkg_root).replace('\\', '/')
        top_dir = '' if rel_dir == '.' else rel_dir.split('/')[0]

        # prune：目录名命中排除规则，或 __pycache__ 且不在豁免顶层下
        keep = []
        for d in dirnames:
            if d in SKIP_DIR_NAMES:
                continue
            if d == '__pycache__' and top_dir not in KEEP_PYCACHE_UNDER:
                continue
            keep.append(d)
        dirnames[:] = sorted(keep)

        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            # 断链的符号链接：跳过（与 pack_v13.py 原行为一致）
            if os.path.islink(full) and not os.path.exists(full):
                continue
            rel = os.path.relpath(full, pkg_root).replace('\\', '/')
            # 文件级规则（备份文件等）——目录级已在 prune 里处理
            if SKIP_FILE_RE.search(fn):
                continue
            if any(rel.startswith(p) for p in SKIP_PATH_PREFIXES):
                continue
            # 🔴 内部会议内容（APP-003①）
            if rel in INTERNAL_EXACT:
                continue
            if rel.startswith(RESULTS_DIR) and SPOKEN_FILE_RE.search(fn):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            yield rel, size


def iter_excluded(pkg_root: str):
    """遍历包根下**要排除**的文件，产出 (relpath, size)。

    与 `iter_package_files` 互补，用于「物理清理」和「--dry-run 报告」。
    """
    pkg_root = os.path.abspath(pkg_root)
    for dirpath, dirnames, filenames in os.walk(pkg_root):
        rel_dir = os.path.relpath(dirpath, pkg_root).replace('\\', '/')
        top_dir = '' if rel_dir == '.' else rel_dir.split('/')[0]

        for d in list(dirnames):
            hit = d in SKIP_DIR_NAMES or (
                d == '__pycache__' and top_dir not in KEEP_PYCACHE_UNDER)
            if not hit:
                continue
            for p2, _d2, f2 in os.walk(os.path.join(dirpath, d)):
                for fn in f2:
                    full = os.path.join(p2, fn)
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        size = 0
                    rel = os.path.relpath(full, pkg_root).replace('\\', '/')
                    yield rel, size
            dirnames.remove(d)

        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, pkg_root).replace('\\', '/')
            if not is_excluded(rel, top_dir):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            yield rel, size


def package_stats(pkg_root: str, skip=()) -> tuple:
    """返回 (files, bytes) —— 与 `iter_package_files` **完全同一口径**。

    `skip` 是要额外跳过的相对路径集合，默认为空。
    ⚠️ MANIFEST 自身**不要**计入（否则自引用），调用方应显式传
    `skip=('app/MANIFEST.json',)`。
    """
    skip = set(skip)
    n_files = 0
    n_bytes = 0
    for rel, size in iter_package_files(pkg_root):
        if rel in skip:
            continue
        n_files += 1
        n_bytes += size
    return n_files, n_bytes


if __name__ == '__main__':
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else \
        r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
    nf, nb = package_stats(root, skip=('app/MANIFEST.json',))
    print(f'包根: {root}')
    print(f'进包: {nf} 文件 / {nb} 字节 ({nb / 1024 ** 3:.2f} GB)')
    ef = eb = 0
    for _rel, size in iter_excluded(root):
        ef += 1
        eb += size
    print(f'剔除: {ef} 文件 / {eb} 字节 ({eb / 1024 ** 2:.1f} MB)')
