r"""sync_c134_to_pkg.py — 把「默认翻译改 INT8-CW」移植到客户包 v1.3

做法与 C-105/C-106/C-108/C-109/C-133 一致：**精确字符串替换 + assert 唯一命中**。

背景（APP-002 / APP-003②，用户决定）
--------------------------------------
翻译默认量化由 **INT4 按通道** 改为 **INT8 按通道**（`mt2-int8sym-cw-q`）。

依据 MT 模块 **H-001 / H-007**（`hy_bench/STATUS_hy.md` §37）：
200 句 wmt24pp **语料级**配对 bootstrap（1000 次，seed=12345）重算 ——
INT4 在 en2zh / zh2en × GPU / NPU 四个组合上**全部显著劣化**
（ΔchrF −2.320 / −2.058 / −1.632 / −1.536，CI 均不含 0）；
INT8 四个组合**全部不劣化**（Δ +0.219 / +0.318 / −0.039 / +0.027）。

⚠️ 撤回旧结论「INT8 质量与 INT4 持平（同义改写级差异），对客户机没有实际收益」
   —— 该结论基于旧的**句子级**配对检验口径，已被语料级 bootstrap 推翻。
   INT8 与 INT4 是**显著差异**（INT4 掉 1.5~2.3 chrF++）。

本脚本只做**四处定点替换**（全在 `translator.py`），不碰其他任何文件。

改动四处
--------
1. `DEFAULT_MODEL` —— 默认模型目录由 `mt2-int4sym-cw-q` 改为 `mt2-int8sym-cw-q`，
   并保留 INT4 作为**回退**（老包 / 未拷贝 INT8 时仍能跑）。
2. `_HY_ROOT` 注释 —— 客户包路径示例同步更新。
3. `_MT_CANDIDATES` —— 重新排序（INT8 GPU 在前，标「默认」）、更新说明文案、
   `bundled` 标志全部改 True（INT8 随包附带，INT4 也保留为可选）。
4. `MT_ENGINES['auto']` / `MT_ALL_CANDIDATES['auto']` 的 label ——
   「自动 · INT4-CW 模型」→「自动 · INT8-CW 模型（默认）」。

用法
----
    python sync_c134_to_pkg.py <pkg_app_dir>

默认目标：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app`
"""

from __future__ import annotations

import os
import sys


# ── 1) DEFAULT_MODEL ────────────────────────────────────────────────
OLD_DEFAULT_MODEL = """DEFAULT_MODEL = os.environ.get(
    'LIVECAP_MT_MODEL',
    _first_existing(
        os.path.join(MODELS, 'mt', 'mt2-int4sym-cw-q'),   # 客户包自带（per-channel，GPU/NPU 通吃）
        os.path.join(MODELS, 'mt2-int4sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int4sym-cw-q'),       # 开发机导出产物
    ))"""

NEW_DEFAULT_MODEL = """DEFAULT_MODEL = os.environ.get(
    'LIVECAP_MT_MODEL',
    _first_existing(
        os.path.join(MODELS, 'mt', 'mt2-int8sym-cw-q'),   # 客户包自带（per-channel，GPU/NPU 通吃）
        os.path.join(MODELS, 'mt2-int8sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int8sym-cw-q'),       # 开发机导出产物
        # ↓ 回退到 INT4：INT8 目录不存在时（老包 / 未拷贝）仍能跑
        os.path.join(MODELS, 'mt', 'mt2-int4sym-cw-q'),
        os.path.join(MODELS, 'mt2-int4sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int4sym-cw-q'),
    ))"""


# ── 2) _HY_ROOT 注释 ────────────────────────────────────────────────
OLD_HY_ROOT = """        os.path.join(MODELS, 'mt'),                 # 客户包：models/mt/mt2-int4sym-cw-q"""

NEW_HY_ROOT = """        os.path.join(MODELS, 'mt'),                 # 客户包：models/mt/mt2-int8sym-cw-q"""


# ── 3) 候选表 + 说明注释 ────────────────────────────────────────────
OLD_CANDIDATES = """# 候选翻译后端：(key, label, device, 模型目录名, 说明, 是否随客户包附带)
# 只有**本机真实存在**的模型才进下拉 —— 客户机上不该出现「缺模型」的项。
# v1.3：客户包**只附带 INT4**（mt2-int4sym-cw-q，993 MB）。
# INT8（1.7 GB）不随包发布 —— 译文质量与 INT4 持平（同义改写级差异），
# 换来的是 +700 MB 显存占用与慢 33%，对客户机没有实际收益。
# 开发机 hy_bench/ov/ 下仍保留 INT8 产物供对比测试。
# 排序：先按设备（GPU 在前，ASR 默认也占 GPU，所以 NPU 项放后面做「错峰」选择）。"""

NEW_CANDIDATES = """# 候选翻译后端：(key, label, device, 模型目录名, 说明, 是否随客户包附带)
# 只有**本机真实存在**的模型才进下拉 —— 客户机上不该出现「缺模型」的项。
#
# ★ v1.4：默认量化由 INT4 改为 **INT8 按通道（int8sym-cw-q）** —— 用户决定。
#   依据 **H-001 / H-007**（MT 模块 `hy_bench/STATUS_hy.md` §37）：
#   200 句 wmt24pp 语料级配对 bootstrap（1000 次，seed=12345）重算结果 ——
#     en2zh：int4_gpu ΔchrF **−2.320**（CI [−3.192,−1.367]，不含 0）
#             int4_npu ΔchrF **−2.058**（CI [−3.003,−1.060]，不含 0）⇒ 显著劣化
#             int8_gpu ΔchrF +0.219（CI 含 0）
#             int8_npu ΔchrF **+0.318**（CI [+0.032,+0.629]，全为正）⇒ 不劣化
#     zh2en：int4_gpu ΔchrF++ −1.632 / int4_npu −1.536（CI 均不含 0）⇒ 显著劣化
#             int8_gpu −0.039 / int8_npu +0.027（CI 均含 0）⇒ 不劣化
#   ⇒ **INT4 在两个方向、两种设备上全部显著劣化；INT8 全部不劣化。**
#   代价：IR 体积 1.02 GB → 1.79 GB（**+0.77 GB**），GPU 吞吐 57.9 → 37.5 tok/s
#   （仍满足实时），显存 +0.75 GB。
# ⚠️ 撤回旧注释「INT8 质量与 INT4 持平…对客户机没有实际收益」——
#   该结论基于旧的句子级配对检验口径，已被 H-001/H-006 的语料级 bootstrap 推翻。
#   INT8 与 INT4 是**显著差异**（INT4 掉 1.5~2.3 chrF++）。
# 排序：先按设备（GPU 在前，ASR 默认也占 GPU，所以 NPU 项放后面做「错峰」选择）。"""

OLD_LIST = """_MT_CANDIDATES = [
    ('gpu_int4cw', 'Intel GPU · INT4-CW', 'GPU.0', 'mt2-int4sym-cw-q',
     'Hy-MT2 INT4_SYM 按通道，约 993 MB。57.9 tok/s，TTFT 35 ms；GPU/NPU 通吃', True),
    ('gpu_int8cw', 'Intel GPU · INT8-CW', 'GPU.0', 'mt2-int8sym-cw-q',
     'Hy-MT2 INT8_SYM 按通道，1.7 GB。37.5 tok/s，质量与 INT4 持平；显存充足时可用，'
     'ASR 也在 GPU 上会互相争抢', False),
    ('npu_int4cw', 'Intel NPU · INT4-CW', 'NPU', 'mt2-int4sym-cw-q',
     'NPU 推荐：44.0 tok/s、零乱码，约 993 MB。ASR 请留在 GPU/NPU 另一侧以免争抢', True),
    ('npu_int8cw', 'Intel NPU · INT8-CW', 'NPU', 'mt2-int8sym-cw-q',
     'NPU 备用：29.6 tok/s、1.7 GB，质量与 INT4 持平但慢 33%', False),
]"""

NEW_LIST = """_MT_CANDIDATES = [
    ('gpu_int8cw', 'Intel GPU · INT8-CW（默认）', 'GPU.0', 'mt2-int8sym-cw-q',
     'Hy-MT2 INT8_SYM 按通道，1.7 GB。**默认**：37.5 tok/s，TTFT 44 ms，'
     '质量与 BF16 统计等价（ΔchrF ≤0.32）；显存 +0.75 GB', True),
    ('gpu_int4cw', 'Intel GPU · INT4-CW', 'GPU.0', 'mt2-int4sym-cw-q',
     'Hy-MT2 INT4_SYM 按通道，约 993 MB。更小更快（57.9 tok/s），但质量**显著低于** '
     'INT8（ΔchrF −2.3，H-001），仅在显存吃紧时选', True),
    ('npu_int8cw', 'Intel NPU · INT8-CW', 'NPU', 'mt2-int8sym-cw-q',
     'NPU：29.6 tok/s、1.7 GB，质量不劣化；ASR 请留在 GPU 以免争抢', True),
    ('npu_int4cw', 'Intel NPU · INT4-CW', 'NPU', 'mt2-int4sym-cw-q',
     'NPU 备用：44.0 tok/s、零乱码，约 993 MB，但质量显著低于 INT8（ΔchrF++ −1.5）', True),
]"""


# ── 4) auto 标签 ────────────────────────────────────────────────────
OLD_AUTO1 = """    label='自动 · INT4-CW 模型', device=None, model=None,"""
NEW_AUTO1 = """    label='自动 · INT8-CW 模型（默认）', device=None, model=None,"""

OLD_AUTO2 = """    label='自动 · INT4-CW 模型', device=None, model=DEFAULT_MODEL, note='',"""
NEW_AUTO2 = """    label='自动 · INT8-CW 模型（默认）', device=None, model=DEFAULT_MODEL, note='',"""


PATCHES = [
    ('translator.py', OLD_DEFAULT_MODEL, NEW_DEFAULT_MODEL),
    ('translator.py', OLD_HY_ROOT, NEW_HY_ROOT),
    ('translator.py', OLD_CANDIDATES, NEW_CANDIDATES),
    ('translator.py', OLD_LIST, NEW_LIST),
    ('translator.py', OLD_AUTO1, NEW_AUTO1),
    ('translator.py', OLD_AUTO2, NEW_AUTO2),
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
            if src.count(new) == 1:
                print(f'[跳过] {fname} —— 已是 C-134 版（幂等）')
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
    print('\n结论：PASS —— C-134（默认 MT 改 INT8-CW）已移植到客户包')
    return 0


if __name__ == '__main__':
    sys.exit(main())
