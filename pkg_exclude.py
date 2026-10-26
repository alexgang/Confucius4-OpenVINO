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
| `results/mt2_memory.json` | 🔴 **同样含内部会议内容**（APP-003①，reviewer 未点名，本模块实测发现）。该文件的 `out` 字段是「[REDACTED-内部会议引文]」—— 是 `spoken` 语料的译文示例 |

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
    'APP_DIR',
    'APP_DEV_ONLY_FILE_RE',
    'is_app_dev_only',
    'is_excluded',
    'iter_package_files',
    'package_stats',
    'iter_excluded',
    'APP_LOCAL_MODULE_RE',
    'find_missing_local_modules',
    'THIRD_PARTY_NOISE_PREFIXES',
    'THIRD_PARTY_NOISE_FILE_RE',
    'is_third_party_noise',
]

# ── 按**目录名**排除（任意层级）──────────────────────────────────────
# 注意：不含 '__pycache__' —— 它由 KEEP_PYCACHE_UNDER 做例外处理。
SKIP_DIR_NAMES = frozenset({
    'ov_cache',    # OpenVINO 编译缓存（实测 4181 MB）
    'npu_cache',   # NPU 插件编译缓存
    'mt_cache',    # 翻译模型编译缓存
    # 🔴 TTS 编译缓存（APP-007）。
    # `live_caption/tts_engine.py::_cache_dir('tts_npu_cache')` 在
    # %LOCALAPPDATA% 不可写时会**回落包内** `app/tts_npu_cache/`
    # ⇒ 与 ov_cache/npu_cache/mt_cache 同性质，必须排除。
    'tts_npu_cache',
})

# 🔴 备份目录（任意层级）
# C-133 教训：**备份不能放在包目录内** —— `_backup_*` 目录不被 `.bak`
# 文件名规则覆盖，会污染包（实测 2026-10-23 客户包根又出现了
# `_backup_c111/`，里面有旧版 live_caption_app.py / translator.py）。
BACKUP_DIR_RE = re.compile(r'^_backup', re.I)

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

# ══════════════════════════════════════════════════════════════════════
# 🔴 第三方自带素材排除（APP-018 第 2 条 + APP-019）
# ══════════════════════════════════════════════════════════════════════
#
# 交付包里有两类**第三方自带素材**，授权归属**不属于本项目**：
#
#  ① babelvox 自带的 speaker profile
#     （`babelvox/data/speakers/{cindy,lou,phil,steve}.json` + `.npy`
#      = 第三方音色 embedding，1×1024）⇒ **第三方音色**；
#  ② scipy 自带的**测试 wav**（`scipy/io/tests/data/*.wav`，22 个）
#     ⇒ **第三方音频素材**。
#
# ⇒ 一律排除（reviewer APP-018 第 2 条 / APP-019 确认）。
# ⚠️ **目的不是减体积**（reviewer 明确「不需要为减小体积再额外下功夫」）
#    ⇒ 体积只掉 90 KB，**关键是授权边界干净**。
#
# 🔴 **安全性依据（删掉不会让包跑不起来）**：
#  ① `babelvox/speakers.py::_copy_builtin_speakers()` 在
#     `BUILTIN_SPEAKERS_DIR` 不存在时**直接 return**（L63-64）⇒ 删目录不报错；
#  ② App 的**生产路线是 spkonly**（`preset_A.wav` → `speaker_embed`）
#     ⇒ **不依赖**内置音色；
#  ③ scipy 的 `tests/` 目录**运行时不会被 import**
#     （只有 pytest 会用）⇒ 删掉不影响 `import scipy.*`；
#  ④ 唯一依赖点是「按名查内置 speaker」（`--voice cindy`）
#     ⇒ 已加**显式回落**（`tts_engine.builtin_speaker_available()`）。
#
# ── 目录前缀（带尾 '/'，可在 walk 时整目录 prune）────────────────
THIRD_PARTY_NOISE_PREFIXES = (
    'python/Lib/site-packages/babelvox/data/speakers/',
)

# ── 文件名正则：**只限 scipy 下的 tests 目录**里的音频素材 ──────────
# ⚠️ 必须限定 `scipy/` + `tests/`，否则会误伤客户自己的音频
#    （例如 `models/qwen3tts/voices/preset_A.wav` 绝不能被排除）。
THIRD_PARTY_NOISE_FILE_RE = re.compile(
    r'^python/Lib/site-packages/scipy/.*/tests/.*\.(wav|flac|mp3|ogg|aiff|m4a)$',
    re.I)


def is_third_party_noise(relpath: str) -> bool:
    """判断相对路径是否属于**第三方自带素材**（⇒ 不进客户包）。

    见 `THIRD_PARTY_NOISE_PREFIXES` / `THIRD_PARTY_NOISE_FILE_RE` 的说明。
    """
    if not relpath:
        return False
    for prefix in THIRD_PARTY_NOISE_PREFIXES:
        if relpath.startswith(prefix):
            return True
    return bool(THIRD_PARTY_NOISE_FILE_RE.match(relpath))


# ── 供 pack_v13.py 做「目录前缀」断言用（带尾 '/'，零假阳性）──────
SKIP_DIR_PREFIXES = tuple(
    f'{p}/' for p in (
        'app/ov_cache',
        'app/npu_cache',
        'app/mt_cache',
        'app/tts_npu_cache',
        'ov_cache',
        'npu_cache',
        'mt_cache',
        'tts_npu_cache',
        '_backup_c111',
        '_backup_c133',
        '_backup_c134',
        '_backup_c135',
    )
) + SKIP_PATH_PREFIXES

# ══════════════════════════════════════════════════════════════════════
# 🔴 开发专用文件排除（APP-002 的延伸）
# ══════════════════════════════════════════════════════════════════════
# 客户包是**交付物** ⇒ 包内只应有「客户能直接用的东西」。
# 🔴 **开发专用文件** = 只在开发机上有意义的文件：
#   - 一次性实测探针（如 `app/_probe_tts_cuda.py`：实测 OV 的 CUDA plugin
#     在 NVIDIA 独显上能否加载 TTS ⇒ **与客户无关**，且里面写着
#     **开发机绝对路径** `C:\Users\Trekker-PTL\confucius4-openvino`
#     ⇒ 属于「开发机路径泄漏」）；
#   - 任何**未被 README / bat / 其它代码引用**的 `_` 前缀脚本。
#
# ⚠️ **判据必须是「文件本身」而不是「名字前缀」**：
#   `selftest_audio_sources.py` 是**客户自检**用的（`verify_pkg_zip.py`
#   的 `KEY_APP_FILES` 把它列为必需）⇒ **绝不能**被 `_` 前缀规则误伤。
#   ⇒ 规则 = 「**下划线前缀**」∧「**在 `app/` 下**」∧「**不在白名单**」。
APP_DIR = 'app/'

# 🔴 **开发专用**（下划线前缀）—— 命中即排除
APP_DEV_ONLY_FILE_RE = re.compile(r'^_[A-Za-z0-9_]+\.(py|ps1|bat|sh)$', re.I)

# 🔴 **明确保留**（虽然也可能命中上面的规则）—— 键 = 文件名（不含目录）
APP_DEV_ONLY_KEEP = frozenset({
    # 客户自检用（`verify_pkg_zip.py` 的 KEY_APP_FILES 列为必需）
    'selftest_audio_sources.py',
})

# 🔴 **App 侧代码会主动引用**的文件（防止误排除）
APP_DEV_ONLY_REFERENCED = frozenset({
    'tts_engine.py', 'tts_engine_patch.py', 'tts_service.py',
    'tts_worker.py', 'translator.py', 'live_caption_app.py',
    'device_config.py', 'audio_source.py', 'backends.py',
    'seg_stream.py', 'segment_encoder_backend.py',
    'npu_delivery_backend.py', 'npu_embeds_backend.py',
    'streaming_asr.py', 'win_clickthrough.py',
    'selftest_audio_sources.py',
})


def is_app_dev_only(relpath: str) -> bool:
    """判断相对路径是否**只在开发机上有意义**（⇒ 不进客户包）。

    规则（全部条件同时满足才排除）：

    1. 位于 `app/` 下（客户包代码目录）；
    2. 文件名**以下划线开头**（开发期临时脚本的命名惯例）；
    3. 扩展名属于脚本类（`.py` / `.ps1` / `.bat` / `.sh`）；
    4. **不在**白名单里（`selftest_audio_sources.py` 等客户真要用的）。

    ⚠️ **故意不做的事**：
    - 不按「代码是否引用了它」判断 ⇒ 那需要全包静态分析，
      太重且易误判；`_` 前缀 + 白名单已经足够；
    - 不排除 `results/` 下的诊断产物（它们由 `SKIP_FILE_RE` /
      `INTERNAL_EXACT` 单独管）⇒ **本规则只管 `app/` 下的脚本**。
    """
    if not relpath.startswith(APP_DIR):
        return False
    name = relpath.rsplit('/', 1)[-1]
    if name in APP_DEV_ONLY_KEEP or name in APP_DEV_ONLY_REFERENCED:
        return False
    return bool(APP_DEV_ONLY_FILE_RE.match(name))


def _top_dir(relpath: str) -> str:
    """相对路径的第一段（顶层目录名）；顶层文件返回 ''。"""
    return relpath.split('/', 1)[0] if '/' in relpath else ''


# ══════════════════════════════════════════════════════════════════════
# 包内**本地模块**导入完整性（APP-042）
# ══════════════════════════════════════════════════════════════════════
#
# 🔴 **要防的故障（真实发生过，不是假想）**：
#   `app/live_caption_app.py` 里新增了 `import caption_render`，
#   但同步脚本只替换了 `live_caption_app.py`、**漏了复制新的
#   `caption_render.py`** ⇒ 客户包启动即 `ModuleNotFoundError`。
#   ⇒ **包内代码互相 import 的本地模块必须都在包内**。
#
# 🔴 **为什么用 `ast` 静态解析而不是真 import**：
#   - 真 import 会**执行**模块顶层代码（`app/` 下的模块一 import numpy
#     就可能 abort，见项目铁律「分析脚本一律不要 import 被测模块」）；
#   - 包内文件数以万计，真 import 无法在打包校验的合理耗时内完成。
#   ⇒ `ast.parse` 只看语法树，**不执行任何代码**。
#
# ⚠️ **只查 `app/` 下的模块**：客户包 `app/` 是一组**平铺**的本地模块
#   （`from translator import X` 这种同目录 import），而 `python/` 下的
#   site-packages 是第三方依赖，不属于「本地模块缺失」范畴。

#: `app/` 下的本地模块名（不含扩展名）—— 由包内文件清单推导。
APP_LOCAL_MODULE_RE = re.compile(r'^app/([A-Za-z_][A-Za-z0-9_]*)\.py$')

#: 这些名字**不是**本地模块（标准库 / 第三方 / 包内但不在 app/ 下）。
_LOCAL_MODULE_ALLOW = frozenset({
    # 标准库里最常见的同名项（防止把 `import xml` 之类误判成缺模块）
    '__future__',
    'xml', 'os', 'sys', 'json', 're', 'time', 'math', 'audio', 'queue',
    'email', 'http', 'logging', 'typing', 'unittest', 'argparse', 'asyncio',
    'dataclasses', 'subprocess', 'threading', 'collections', 'pathlib',
    'tempfile', 'traceback', 'warnings', 'pickle', 'socket', 'sqlite3',
    'struct', 'random', 'uuid', 'hashlib', 'base64', 'copy', 'csv',
    'datetime', 'glob', 'html', 'itertools', 'functools', 'inspect',
    'io', 'ipaddress', 'mmap', 'numbers', 'operator', 'shutil', 'signal',
    'stat', 'string', 'textwrap', 'tokenize', 'types', 'unicodedata',
    'urllib', 'zipfile', 'ctypes', 'abc', 'contextlib', 'enum', 'errno',
    'gc', 'getpass', 'importlib', 'inspect', 'ipaddress', 'json',
    'keyword', 'locale', 'marshal', 'numbers', 'operator', 'pprint',
    'pty', 'pwd', 'py_compile', 'reprlib', 'secrets', 'select', 'selectors',
    'site', 'ssl', 'stat', 'string', 'symtable', 'sysconfig', 'tarfile',
    'token', 'trace', 'unicodedata', 'venv', 'webbrowser', 'zlib',
})


def _iter_local_imports(src_text: str):
    """从一段 Python 源码里抽出它引用的**本地模块名**。

    产出模块名（不含扩展名），形如 ``caption_render``。

    🔴 **只认「同目录平铺模块」形态**：
       - ``import caption_render``        ⇒ ``caption_render``
       - ``import caption_render as cr``  ⇒ ``caption_render``
       - ``from caption_render import X`` ⇒ ``caption_render``
       - ``from . import caption_render`` ⇒ ``caption_render``
       - ``from .caption_render import X``⇒ ``caption_render``

    ⚠️ **不认** ``from a.b import c``（子包形态）—— `app/` 下没有子包；
       遇到时按「顶层名 ``a``」处理是**错的**（``a.b`` 可能是第三方），
       所以这里**直接跳过**，避免把第三方包误报成缺失。
    """
    import ast
    try:
        tree = ast.parse(src_text)
    except SyntaxError:
        # 语法错误不该让打包校验崩掉；调用方会另外报语法问题。
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # `import a.b` → 只取顶层 `a`（但子包形态在 app/ 下不存在，
                # 这里保守取顶层名即可，见下方白名单过滤）
                top = alias.name.split('.')[0]
                yield top
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # 相对导入：`from . import X` / `from .X import Y`
                for alias in node.names:
                    if alias.name != '*':
                        yield alias.name
                continue
            if not node.module:
                continue
            # `from a.b import c` —— 子包形态 ⇒ 跳过（避免误报第三方包）
            if '.' in node.module:
                continue
            yield node.module


def find_missing_local_modules(pkg_root: str, known_modules=None):
    """检查客户包 ``app/`` 下的**本地模块导入完整性**。

    返回 ``(certain, suspect, checked)``：

    - ``certain`` : **确定缺失**的 ``(引用方相对路径, 模块名)`` 列表。
      判据：包内 ``app/`` 下**没有**该 ``.py``，但**仓库源目录**里
      **确实有**同名 ``.py`` ⇒ 它是**本地模块**，只是**没被带进包**
      ⇒ **真故障**，必须让打包 FAIL。
    - ``suspect`` : **疑似缺失**的同名结构列表。
      判据：包内没有、仓库源里也没有 ⇒ 可能是**第三方依赖**
      （``numpy`` / ``soundcard`` / …）⇒ **只提示，不判负**。
    - ``checked`` : 被检查过的 ``app/*.py`` 文件数。

    🔴 **为什么要这道闸门**（见上方注释）：
       同步脚本做「精确字符串替换」时，新增一个 ``import X`` 的同时
       **可能漏掉把 ``X.py`` 复制进包** ⇒ 客户包启动即
       ``ModuleNotFoundError``，而打包流水线**全绿**（zip 完整、
       MANIFEST 一致、逐字节一致）⇒ **缺陷会直接漏到客户手里**。

    ⚠️ **判据边界**（避免误报，这是本函数最关键的设计）：
       「包内没有」**不足以**判定缺失 —— 第三方依赖也满足这个条件。
       ⇒ 必须引入**外部基准**：``known_modules``
       （默认由调用方传入「仓库 `live_caption/` 下的 `.py` 名」）
       ⇒ 只有「仓库里存在 ⇒ 本该在包内，却没在」才算**确定缺失**。

    🔴 **`known_modules` 为什么必须由调用方传入**：
       本模块刻意**零依赖**（不 import 仓库任何其他模块），
       而「仓库 `live_caption/` 的文件名清单」需要知道仓库在哪
       ⇒ 只能由调用方（`pack_v13.py` / 测试脚本）传入。
    """
    import os

    pkg_root = os.path.abspath(pkg_root)
    app_dir = os.path.join(pkg_root, APP_DIR.rstrip('/'))

    if not os.path.isdir(app_dir):
        return [], [], 0

    if known_modules is None:
        known_modules = set()

    # 包内 app/ 下实际存在的模块名
    present = set()
    py_files = []
    for fn in sorted(os.listdir(app_dir)):
        if not fn.endswith('.py'):
            continue
        py_files.append(fn)
        present.add(fn[:-3])

    certain = []
    suspect = []
    for fn in py_files:
        full = os.path.join(app_dir, fn)
        try:
            with open(full, 'rb') as f:
                raw = f.read()
        except OSError:
            continue
        try:
            src = raw.decode('utf-8')
        except UnicodeDecodeError:
            src = raw.decode('utf-8', 'replace')
        # 🔴 **去重**：同一文件里同一模块可能被 import 多次
        #    （`import soundcard` 出现在 5 个函数里）⇒ 只报一次。
        seen = set()
        for name in _iter_local_imports(src):
            if name in seen:
                continue
            seen.add(name)
            if name in present:
                continue
            if name in _LOCAL_MODULE_ALLOW:
                continue
            if name in known_modules:
                certain.append((f'{APP_DIR}{fn}', name))
            else:
                suspect.append((f'{APP_DIR}{fn}', name))

    return certain, suspect, len(py_files)


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

    # 2.75) 🔴 开发专用文件（app/ 下的 `_` 前缀脚本，如 `_probe_tts_cuda.py`）
    if is_app_dev_only(relpath):
        return True

    # 2.8) 🔴 第三方自带素材（APP-018 第 2 条 / APP-019）
    #   babelvox 自带 speaker profile + scipy 自带测试 wav
    if is_third_party_noise(relpath):
        return True

    # 3) __pycache__：python/ 下保留，其余排除
    if '__pycache__' in relpath.split('/'):
        return top_dir not in KEEP_PYCACHE_UNDER

    # 4) 编译缓存目录名（任意层级）
    for seg in relpath.split('/')[:-1]:
        if seg in SKIP_DIR_NAMES:
            return True
        # 🔴 备份目录（任意层级）—— C-133 教训：备份放包内会污染包
        if BACKUP_DIR_RE.match(seg):
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
            # 🔴 备份目录（任意层级）—— C-133 教训：备份放包内会污染包
            if BACKUP_DIR_RE.match(d):
                continue
            if d == '__pycache__' and top_dir not in KEEP_PYCACHE_UNDER:
                continue
            # 🔴 第三方自带素材目录（APP-018 第 2 条）—— 整目录 prune
            #   （`babelvox/data/speakers/` ⇒ 内置音色 profile）
            d_rel = (rel_dir + '/' + d) if rel_dir != '.' else d
            d_rel = d_rel.replace('\\', '/') + '/'
            if any(d_rel.startswith(p) for p in THIRD_PARTY_NOISE_PREFIXES):
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
            # 🔴 开发专用文件（app/ 下的 `_` 前缀脚本）
            if is_app_dev_only(rel):
                continue
            # 🔴 第三方自带素材（APP-018 第 2 条）—— 文件级
            #   （scipy 的测试 wav：目录里还有 .sav/.mat 等非音频数据，
            #    只排音频文件，不整目录删）
            if is_third_party_noise(rel):
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
            d_rel = (rel_dir + '/' + d) if rel_dir != '.' else d
            d_rel = d_rel.replace('\\', '/') + '/'
            hit = d in SKIP_DIR_NAMES or (
                BACKUP_DIR_RE.match(d)) or (
                d == '__pycache__' and top_dir not in KEEP_PYCACHE_UNDER) or (
                any(d_rel.startswith(p) for p in THIRD_PARTY_NOISE_PREFIXES))
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
