r"""sync_c133_to_pkg.py — 把 C-133（编译缓存外移到用户目录）移植到客户包 v1.3

做法与 C-105/C-106/C-108/C-109 一致：**精确字符串替换 + assert 唯一命中**。

背景（APP-002）
--------------
仓库 `live_caption/` 与客户包 `app/` 是**两份独立维护的副本**：

    live_caption_app.py   repo 114596 B / pkg 102166 B / zip 92654 B
    streaming_asr.py      repo  25485 B / pkg  24888 B
    audio_source.py       repo  20116 B / pkg  20321 B

仓库版**独有** `tts_service.py` / `tts_worker.py` 与 TTS 面板 ⇒
**严禁整目录覆盖同步**，否则会把未交付的 TTS 功能带进 v1.3。

本脚本只做**三处定点替换**，不碰其他任何文件。

改动三处
--------
1. `live_caption_app.py` 的 `_cache()` —— 编译缓存改到
   `%LOCALAPPDATA%\Confucius4LiveCaption\<name>`，不可写时回落包内；
   同时删掉误导性注释（「开发机上会沿用已有的缓存目录」——实测
   `~/.openvino/models/ov_cache` 在开发机上**根本不存在**，那个分支是死代码，
   实际一直在往包内 `app/ov_cache` 写缓存）。
2. `npu_delivery_backend.py` 的 `DEFAULT_NPU_CACHE` —— 兜底值从 WORK 相对
   路径改为用户目录绝对路径。
3. `npu_embeds_backend.py` 的 `cache_dir` 缺省值 —— 同上（原默认
   `"./reports/npu_cache"` 在客户包里会解析到 `<包根>/app/reports/npu_cache`，
   污染包目录）。

用法
----
    python sync_c133_to_pkg.py <pkg_app_dir>

默认目标：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app`
"""

from __future__ import annotations

import os
import sys


# ── 1) live_caption_app.py::_cache() ─────────────────────────────────
OLD_CACHE = '''# 编译缓存：放在**用户可写目录**（压缩包可能装在 Program Files，只读）。
# 不用开发机路径；开发机上会沿用已有的缓存目录以省编译时间。
def _cache(name):
    """编译缓存目录。优先复用开发机已有缓存，其次用包内目录。"""
    shared = os.path.join(
        os.path.expanduser('~'), '.openvino', 'models',
        'reports' if name == 'npu_cache' else '', name)
    return shared if os.path.isdir(shared) else os.path.join(APP_DIR, name)'''

NEW_CACHE = '''# 编译缓存：放在**用户可写目录**（压缩包可能装在 Program Files，只读）。
# C-133 / APP-002：编译缓存**绝不写包内** —— 包内缓存对客户机基本无用，
# 却是实打实的体积（开发机实测长到 4.1 GB）。
def _cache(name):
    """编译缓存目录：**用户可写目录**，绝不写包内。

    C-133 / APP-002（客户包瘦身）—— 为什么不能放包里：
    - 包内缓存对客户机**基本无用**：GPU blob 头写死 ie_version
      （实测 "2026.4.1-22982-e213a147257-release"），oneDNN kernel 缓存
      绑 CPU 微架构 ⇒ 换机器 / 换 OV 版本基本不命中；
    - 但它是**实打实的体积**：开发机实测长到 4.1 GB（其中单个 decoder
      blob 1.65 GB），压缩率只有 88%（已编译二进制），删比压划算；
    - 包可能装在 Program Files（只读）⇒ 写不进去 ⇒ 每次启动都重编译
      （实测首次多约 19 s）。

    与 translator.py 的 mt_cache 保持同一根目录，便于用户一次性清理。

    不可写时**回落包内**（不致命）：已实测只读 CACHE_DIR 不崩，
    OpenVINO 会静默跳过写缓存，只影响编译速度。
    """
    root = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(root, 'Confucius4LiveCaption', name)
    try:
        os.makedirs(d, exist_ok=True)
        # Windows 上目录可能存在但 ACL 拒绝写入，此时 makedirs 不报错，
        # 而后续 OpenVINO 写缓存会失败 ⇒ 必须显式探测写权限。
        if not os.access(d, os.W_OK):
            raise OSError(f'not writable: {d}')
        return d
    except Exception as e:
        print(f'[warn] 编译缓存目录不可用（{e}），回落包内 {name}/')
        return os.path.join(APP_DIR, name)'''


# ── 2) npu_delivery_backend.py::DEFAULT_NPU_CACHE ────────────────────
OLD_NPU_DEFAULT = """DEFAULT_TOKENIZER_DIR = 'models/ov-int8-past'
DEFAULT_NPU_CACHE = './reports/npu_cache'"""

NEW_NPU_DEFAULT = """DEFAULT_TOKENIZER_DIR = 'models/ov-int8-past'
# C-133 / APP-002：编译缓存**绝不写包内**（包可能装在 Program Files 只读；
# 且包内缓存跨机器/跨 OV 版本基本不命中）。与 live_caption_app._cache()、
# translator.py 的 mt_cache 保持同一根目录。
# 说明：正常路径由 live_caption_app.py 显式传 npu_cache=_cache('npu_cache')，
# 这里只是**死代码兜底**，改它是为了防止未来误用时在包内生成 reports/。
DEFAULT_NPU_CACHE = os.path.join(
    os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'),
    'Confucius4LiveCaption', 'npu_cache')"""


# ── 3) npu_embeds_backend.py::cache_dir 缺省值 + 兜底逻辑 ─────────────
OLD_EMBEDS_SIG = '''                 cache_dir: str = "./reports/npu_cache",
                 strict_intel: bool = True):
        import openvino as ov
        from transformers import AutoTokenizer, WhisperFeatureExtractor

        # ── 父类只负责 encoder + tokenizer/特征提取器 ────────────────'''

NEW_EMBEDS_SIG = '''                 cache_dir: str = None,
                 strict_intel: bool = True):
        import openvino as ov
        from transformers import AutoTokenizer, WhisperFeatureExtractor

        # C-133 / APP-002：编译缓存**绝不写包内**（原默认 "./reports/npu_cache"
        # 是 WORK 相对路径 ⇒ 在客户包里会解析到 <包根>/app/reports/npu_cache，
        # 污染包目录）。缺省改为用户可写目录。
        if not cache_dir:
            cache_root = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
            cache_dir = os.path.join(cache_root, 'Confucius4LiveCaption', 'npu_cache')
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except OSError:
                pass

        # ── 父类只负责 encoder + tokenizer/特征提取器 ────────────────'''


# ── 应用 ──────────────────────────────────────────────────────────────
PATCHES = [
    ('live_caption_app.py', OLD_CACHE, NEW_CACHE),
    ('npu_delivery_backend.py', OLD_NPU_DEFAULT, NEW_NPU_DEFAULT),
    ('npu_embeds_backend.py', OLD_EMBEDS_SIG, NEW_EMBEDS_SIG),
]

DEFAULT_PKG_APP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app'


def main():
    pkg_app = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PKG_APP
    if not os.path.isdir(pkg_app):
        print(f'!! 目标目录不存在: {pkg_app}')
        return 1

    ok = True
    for fname, old, new in PATCHES:
        path = os.path.join(pkg_app, fname)
        if not os.path.isfile(path):
            print(f'!! 缺少文件: {path}')
            ok = False
            continue
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        n = src.count(old)
        if n == 0:
            # 已经是新版（幂等）
            if src.count(new) == 1:
                print(f'[跳过] {fname} —— 已是 C-133 版')
                continue
            print(f'!! {fname}: 未匹配到待替换片段（当前已改动过？）')
            ok = False
            continue
        if n > 1:
            print(f'!! {fname}: 片段命中 {n} 次（要求恰好 1 次），拒绝替换')
            ok = False
            continue
        src = src.replace(old, new)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(src)
        print(f'[已移植] {fname}')

    if not ok:
        print('\n结论：FAIL（部分文件未移植）')
        return 1
    print('\n结论：PASS —— C-133（编译缓存外移到用户目录）已移植到客户包')
    return 0


if __name__ == '__main__':
    sys.exit(main())
