#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app255 — 从 `_app244_build_minimvp_rc1.py` 派生 **rc2 构建器**。

## 为什么（本轮实测的 P0）
MiniMVP `v1.0-rc1` **打不开**：
> `ModuleNotFoundError: No module named 'segment_encoder_backend'`

🔴 **根因**：`live_caption_app.py:1476` 的
`from segment_encoder_backend import SegmentEncoderOVBackend`
写在**类的 `__init__` 里** ⇒ **模块级 import 不执行**
⇒ rc1 的构建闸门 G1「导入冒烟 17/17 ✅」是**假 PASS**。

## rc2 做了什么
1. **补齐导入闭包**（AST 口径，见 G8）：
   `segment_encoder_backend` / `npu_embeds_backend` / `npu_delivery_backend`
   / `time_stretch` / `offline_reader` / `offline_reader_gui` / `win_clickthrough`
   ⇒ 共 17 → **24 个模块**；
2. **新增构建闸门 G8：AST 导入闭包检查**（CPU、不跑模型）
   ⇒ 以后再少文件 ⇒ **构建就红**（不再靠运行才发现）；
3. **新增 G9：鉴别力** ⇒ 同一判据在**已知有缺陷的 rc1** 上必须 FAIL。

## 纪律
* **新目录** `Confucius4_LiveCaption_MiniMVP_v1.0-rc2`；**rc1 / v1.0 一个字节都不动**
  （它们是缺陷证据）。
* `tts_cuda` / `tts_cuda_sidecar` **仍然不带**（APP-066 明确排除 CUDA 内容）；
  它们的 import 全部在 `try/except` 里 ⇒ 缺失时优雅降级。

## 用法
```
python results/app/_app255_make_rc2_builder.py      # 只生成构建器
python results/app/_app255_build_minimvp_rc2.py     # 真正构建
```
"""
from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '_app244_build_minimvp_rc1.py')
DST = os.path.join(HERE, '_app255_build_minimvp_rc2.py')

#: 🔴 rc2 要**补进**包里的模块（AST 导入闭包口径）
ADD_MODULES = (
    # ── 硬需求（缺了就打不开）──
    'segment_encoder_backend.py',
    # ── NPU ASR 后端（GUI 允许 ASR 选 NPU 时会用到）──
    'npu_embeds_backend.py',
    'npu_delivery_backend.py',
    # ── APP-042 自适应变速（缺了 ⇒ 语音滞后无法追赶）──
    'time_stretch.py',
    # ── GUI 离线朗读对话框 ──
    'offline_reader.py',
    'offline_reader_gui.py',
    # ── GUI 窗口穿透（try/except 保护，缺了只是没这个功能）──
    'win_clickthrough.py',
)

#: 🔴 闸门 G8 的实现（AST 导入闭包；**含函数内/类内/try 内**的 import）
G8_FUNC = '''

# ══════════════════════════════════════════════════════════════════════
# 🔴🔴🔳 APP-066 rc2：G8 —— **AST 导入闭包**检查（rc1 的 P0 就是这里漏的）
# ══════════════════════════════════════════════════════════════════════
def _local_imports(path):
    """抓一个文件里的**全部** import（含函数内/类内/try 内）⇒ 模块名。"""
    src = open(path, 'r', encoding='utf-8', errors='replace').read()
    tree = ast.parse(src)
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.append(a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                if node.module:
                    mods.append(node.module.split('.')[0])
                continue
            if node.module:
                mods.append(node.module.split('.')[0])
    return mods


def import_closure_check(dst):
    """算「包内模块的导入闭包」⇒ 报告**缺失**的本地模块。

    🔴 **为什么要 AST 而不是运行**：rc1 的 G1「导入冒烟」只做**模块级**
    import ⇒ 抓不到**写在类 `__init__` 里**的 import
    （`segment_encoder_backend` 就是这样 ⇒ rc1 假 PASS ⇒ 包打不开）。
    """
    app_dir = os.path.join(dst, 'app')
    pkg_mods = {fn[:-3] for fn in os.listdir(app_dir)
                if fn.endswith('.py')}
    dev_dir = os.path.join(REPO, 'live_caption')
    dev_mods = {fn[:-3]: os.path.join(dev_dir, fn)
                for fn in os.listdir(dev_dir) if fn.endswith('.py')}
    # 已知「不在包内也 OK」的模块（第三方/标准库，或 APP-066 明确排除的 CUDA）
    optional = {'tts_cuda', 'tts_cuda_sidecar'}
    seen, stack, missing = set(), sorted(pkg_mods), {}
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        p = dev_mods.get(name)
        if not p:
            continue
        try:
            mods = _local_imports(p)
        except Exception as e:
            missing.setdefault(name, []).append('parse failed: %r' % (e,))
            continue
        for m in mods:
            if m in dev_mods and m not in pkg_mods:
                missing.setdefault(m, []).append(
                    '被 %s 引用（本地模块，但**不在包内**）' % name)
            if m in dev_mods and m not in seen:
                stack.append(m)
    # 排除「被引用但可选」的（CUDA：APP-066 明确不带）
    real_missing = {k: v for k, v in missing.items() if k not in optional}
    optional_hit = {k: v for k, v in missing.items() if k in optional}
    return {'ok': not real_missing,
            'n_pkg_modules': len(pkg_mods),
            'n_closure': len(seen),
            'missing': real_missing,
            'optional_not_packed': optional_hit,
            'note': ('optional_not_packed = 被引用但 APP-066 明确排除的模块'
                     '（CUDA）⇒ 其 import 全在 try/except 内 ⇒ 优雅降级')}
'''

#: 🔴 闸门 G9（鉴别力）：同一判据在**已知有缺陷的 rc1** 上必须 FAIL
G9_CODE = """        {'id': 'G9', 'name': '鉴别力：G8 同判据在**已知有缺陷**的 rc1 上必须 FAIL',
         'ok': (closure_prev is not None and closure_prev.get('ok') is False),
         'detail': 'rc1 ok=%s missing=%s'
         % ((closure_prev or {}).get('ok'),
            sorted((closure_prev or {}).get('missing', {}).keys()))},
"""


def main():
    src = open(SRC, 'rb').read().decode('utf-8')
    orig_len = len(src)

    # ── ① 改目录 / 版本 ────────────────────────────────────────
    src = src.replace("'Confucius4_LiveCaption_MiniMVP_v1.0-rc1'",
                      "'Confucius4_LiveCaption_MiniMVP_v1.0-rc2'")
    src = src.replace("VERSION = '1.0-rc1'", "VERSION = '1.0-rc2'")

    # ── ② 扩 APP_MODULES ───────────────────────────────────────
    old_tail = ("    'audio_source.py', 'streaming_asr.py', 'device_config.py',\n"
                "    'backends.py',\n)")
    new_tail = ("    'audio_source.py', 'streaming_asr.py', 'device_config.py',\n"
                "    'backends.py',\n"
                "    # 🔴🔴🔳 rc2（APP-066）：**AST 导入闭包**补进来的模块\n"
                "    #   ⇒ rc1 缺 `segment_encoder_backend` ⇒ **包打不开**（P0）\n"
                "    'segment_encoder_backend.py', 'npu_embeds_backend.py',\n"
                "    'npu_delivery_backend.py', 'time_stretch.py',\n"
                "    'offline_reader.py', 'offline_reader_gui.py',\n"
                "    'win_clickthrough.py',\n)")
    assert src.count(old_tail) == 1, 'APP_MODULES 尾部定位失败'
    src = src.replace(old_tail, new_tail)

    # ── ③ 插入 G8 实现（放在 main() 之前）──────────────────────
    anchor = "\ndef main():"
    assert src.count(anchor) == 1, 'main() 定位失败'
    src = src.replace(anchor, G8_FUNC + anchor)

    # ── ④ 插入 G8/G9 闸门 + 在 main() 里算 closure ─────────────
    g7_anchor = """        {'id': 'G7', 'name': '鉴别力：同判据在**已知有缺陷**的 v1.0 上必须 FAIL',"""
    assert src.count(g7_anchor) == 1, 'G7 定位失败'
    # 在 G7 之后追加 G8/G9
    g7_block_end = src.index(g7_anchor)
    g7_block_end = src.index("\n    ]", g7_block_end)
    insert_at = g7_block_end
    g8_g9 = """
        {'id': 'G8', 'name': '包内模块的 **AST 导入闭包**完整（不缺模块）',
         'ok': (closure.get('ok') is True),
         'detail': 'pkg_modules=%d closure=%d missing=%s'
         % (closure.get('n_pkg_modules', -1), closure.get('n_closure', -1),
            sorted(closure.get('missing', {}).keys()))},
""" + G9_CODE
    src = src[:insert_at] + g8_g9 + src[insert_at:]

    # 在 main() 里：算 closure（当前包）+ closure_prev（rc1）
    # 🔴 **必须放在 `gates = [` 之前**（否则 gates 里引用不到 ⇒ UnboundLocalError）
    main_anchor = """    gates = [
        {'id': 'G1',"""
    assert src.count(main_anchor) == 1, 'gates 列表定位失败'
    compute = """    # 🔴 G8：当前包的导入闭包
    closure = import_closure_check(dst)
    print('   G8 导入闭包：ok=%s 缺失=%s'
          % (closure.get('ok'), sorted(closure.get('missing', {}).keys())))
    # 🔴 G9：鉴别力 —— 同一判据在**已知有缺陷的 rc1** 上必须 FAIL
    closure_prev = None
    prev_rc1 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc1')
    if os.path.isdir(os.path.join(prev_rc1, 'app')):
        closure_prev = import_closure_check(prev_rc1)
        print('   G9 鉴别力：rc1 同判据 ok=%s 缺失=%s'
              % (closure_prev.get('ok'),
                 sorted(closure_prev.get('missing', {}).keys())))

"""
    src = src.replace(main_anchor, compute + main_anchor)

    # ── ⑤ 证据里记 closure ─────────────────────────────────────
    ev_anchor = "        'accepted_code_fingerprint': accepted['code_fingerprint'],"
    assert src.count(ev_anchor) == 1, '证据字段定位失败'
    src = src.replace(ev_anchor,
                      ev_anchor + "\n        'import_closure': closure,\n"
                      "        'import_closure_prev_rc1': closure_prev,")

    # ── ⑥ 文档头更新（🔴 **只改文案**，绝不做全局 `rc1→rc2` 替换：
    #     `prev_rc1` / `closure_prev` 指向的**必须是 rc1**（鉴别力对照组））──
    src = src.replace("'correction': 'APP-066（MiniMVP 最小客户包）· rc1',",
                      "'correction': 'APP-066（MiniMVP 最小客户包）· rc2',")
    src = src.replace("REPORT = os.path.join(HERE, 'app244_minimvp_rc1_build_evidence.json')",
                      "REPORT = os.path.join(HERE, 'app255_minimvp_rc2_build_evidence.json')")
    src = src.replace("'prev_build': 'Confucius4_LiveCaption_MiniMVP_v1.0（保留不动，作为缺陷证据）',",
                      "'prev_build': ('Confucius4_LiveCaption_MiniMVP_v1.0 / v1.0-rc1"
                      "（保留不动，作为缺陷证据）'),")
    # 🔴 需要 ast（新增的 G8 用）
    src = src.replace("import argparse\nimport hashlib",
                      "import argparse\nimport ast\nimport hashlib")

    with open(DST, 'w', encoding='utf-8', newline='') as f:
        f.write(src)
    print('已生成：%s（%d → %d 字节）' % (DST, orig_len, len(src)))
    # 自检：语法
    ast.parse(src)
    print('AST_PARSE OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
