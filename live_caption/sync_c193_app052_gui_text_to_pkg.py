#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c193_app052_gui_text_to_pkg.py —— **【APP-052 ② 末段】定点同步**：

把仓库 `live_caption/live_caption_app.py` 里本轮**清理 GUI 说明文字**的改动
同步到客户包 `app/`。

reviewer APP-052 ② 末段（不阻断交付，但要求「清理这些说明文字」）指出：

* 说明文字原样显示了 `**f16**`、`**推荐**` 的 markdown 星号；
* 同一段设备说明**重复出现两次**；
* 1280×720 下文字被截断；
* 面向客户的界面上出现了「onednn 执行失败 / 本机 OV 未安装 CUDA plugin」这类研发术语。

🔴🔴🔴 **纪律（§48 / §120 / 铁律「仓库 ⇄ 客户包 = 两份独立副本」）**：
  - **禁止整目录 / 整文件覆盖** ⇒ 本脚本**只做 N 处精确字符串替换**；
  - 每处替换前**断言「旧串在包内恰好命中 1 次」** ⇒ 命中 0 或 ≥2 ⇒
    **立即抛错退出**（fail-closed，绝不猜）；
  - 🔴 **幂等**：包内**已经是新串** ⇒ 视为「已同步」⇒ **跳过**（不报错），
    这样脚本**重复执行安全**；
  - **不写死客户包版本号** ⇒ 从 `pkg_paths` 自动发现**最新版本**；
  - 写回后**定点复核**（「本轮那处新串 1 次 ＋ 旧串 0 次」）；
  - **只同步仓库里已经改好的内容** ⇒ 本脚本**不修改仓库**。

用法：
    python live_caption/sync_c193_app052_gui_text_to_pkg.py [--dry-run]
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


#: (旧串, 新串) —— 全部只在本轮**用户可见说明文字**里改过的地方
EDITS = (
    # ① 研发术语：CUDA plugin
    ("'本机 OV 未安装 CUDA plugin ⇒ NVIDIA 独显上的 TTS 引擎'",
     "'本机未安装 NVIDIA 显卡加速组件 ⇒ NVIDIA 独显上的语音合成引擎'"),
    # ② 研发术语：onednn / talker / peak 1.000 ＋ markdown 星号
    ("return ('实测本机 Intel 集显 **f16** 合成失控：talker 跑满 512 帧 '",
     "return ('实测本机 Intel 集显用半精度（f16）合成会失控：'"),
    ("'⇒ 40.96 s 削波音频（peak 1.000），且 speaker embedding 的 '",
     "'生成过程跑满 512 帧 ⇒ 40.96 s 削波音频（峰值 1.000），'"),
    ("'onednn 执行失败 ⇒ 会静默回退内置音色；'",
     "'且音色特征计算失败 ⇒ 会静默回退内置音色；'"),
    ("'同一设备改用 **f32** 可正常合成')",
     "'同一设备改用全精度（f32）可正常合成')"),
    # ③ CUDA（PyTorch）note
    ("note = 'CUDA 后端（OV CUDA plugin 已安装）'",
     "note = 'CUDA 后端（NVIDIA 显卡加速组件已安装）'"),
    # ④ markdown 星号：**推荐**
    ("note = '✅ 实测可用（端到端合成 PASS，RTF≈1.16）⇒ **推荐**'",
     "note = '✅ 实测可用（端到端合成 PASS，RTF≈1.16）⇒ 推荐'"),
    # ⑤ markdown 星号：**也能播出声音** / **f16 会失控所以不在此列**
    ("note = ('⚠️ 实测本机集显 f32 能合成、**也能播出声音**，但很慢'",
     "note = ('⚠️ 实测本机集显 f32 能合成、也能播出声音，但很慢'"),
    ("'**f16 会失控所以不在此列**')",
     "'半精度（f16）会失控所以不在此列')"),
    # ⑥ ASR CUDA note 的 markdown 星号
    ("note = (note + '；🔴 客户包**未随附** audio.cpp / GGUF 模型'",
     "note = (note + '；🔴 客户包未随附 audio.cpp / GGUF 模型'"),
    # ⑦ TTS CUDA（PyTorch）note 的 markdown 星号
    ("note=('✅ 实测可用（PyTorch+CUDA，RTX 5050）：**流式首包 0.547 s** / RTF 0.892'",
     "note=('✅ 实测可用（PyTorch+CUDA，RTX 5050）：流式首包 0.547 s / RTF 0.892'"),
    ("'（比 NPU 快 12.7×）⇒ **最快**；'",
     "'（比 NPU 快 12.7×）⇒ 最快；'"),
    # ⑧ 测试音 note 的 markdown 星号
    ("'此测试**不依赖 TTS worker**。')",
     "'此测试不依赖 TTS worker。')"),
    # ⑨ CLI 控制台输出的 markdown 星号
    ("print('[TTS] 取料来源 = **ASR 原文**（不经过 MT ⇒ MT 模型不加载）',",
     "print('[TTS] 取料来源 = ASR 原文（不经过 MT ⇒ MT 模型不加载）',"),
    ("print('  结论：**未检测到 Intel 集显**，Intel 后端无法运行。')",
     "print('  结论：未检测到 Intel 集显，Intel 后端无法运行。')"),
    ("print('  结论：**模型文件不完整**，请确认包已完整解压。')",
     "print('  结论：模型文件不完整，请确认包已完整解压。')"),
    # ⑩ argparse help 的 markdown 星号
    ("help='译文语音输出开关。**默认 on**（TTS 已是正式功能）；'",
     "help='译文语音输出开关。默认 on（TTS 已是正式功能）；'"),
    ("'🔴 APP-021⑥：**逐句** wav 落盘目录（每段一个 wav）。'",
     "'🔴 APP-021⑥：逐句 wav 落盘目录（每段一个 wav）。'"),
    ("help='🔴 APP-027 V1/V2 验收：**逐句遥测** JSONL 落盘路径。'",
     "help='🔴 APP-027 V1/V2 验收：逐句遥测 JSONL 落盘路径。'"),
    ("help='🔴🔴🔴 **APP-027「争用定量」四臂对照**所需的最小开关。'",
     "help='🔴🔴🔴 APP-027「争用定量」四臂对照所需的最小开关。'"),
    ("'🔴🔴 APP-027 V3（§84）：**已真正启用**'",
     "'🔴🔴 APP-027 V3（§84）：已真正启用'"),
    ("'**CLI 也能开**（V3 实测用）；'",
     "'CLI 也能开（V3 实测用）；'"),
    ("'🔴🔴 APP-039：标注为**实验性**——当前实现是'",
     "'🔴🔴 APP-039：标注为实验性——当前实现是'"),
    ("'⚠️ `--tts-out` 只在**落盘模式**下写 JSONL'",
     "'⚠️ `--tts-out` 只在落盘模式下写 JSONL'"),
    ("'（该模式**不播放** ⇒ 欠载/积压字段无意义）；'",
     "'（该模式不播放 ⇒ 欠载/积压字段无意义）；'"),
    ("'要测**真实播放**的欠载/积压/语音滞后，'",
     "'要测真实播放的欠载/积压/语音滞后，'"),
    ("'**必须**用这个开关（可与 `--tts-out` 互斥使用）')",
     "'必须用这个开关（可与 `--tts-out` 互斥使用）')"),
    ("'⚠️ 为什么需要：TTS 原本**只订阅 MT 输出** ⇒ '",
     "'⚠️ 为什么需要：TTS 原本只订阅 MT 输出 ⇒ '"),
    ("'⇒ 「TTS 单独」与「+ASR（无 MT）」两臂**在本 CLI 下无法实现**'",
     "'⇒ 「TTS 单独」与「+ASR（无 MT）」两臂在本 CLI 下无法实现'"),
    ("（reviewer 明文）**整个失效**", "（reviewer 明文）整个失效"),
    ("'⚠️ `asr` 模式下**不加载 MT 模型**（省 GPU/NPU 占用）'",
     "'⚠️ `asr` 模式下不加载 MT 模型（省 GPU/NPU 占用）'"),
    ("'`mt`（默认）= 朗读**定稿译文**（现有行为）；'",
     "'`mt`（默认）= 朗读定稿译文（现有行为）；'"),
    ("'`asr` = **直接朗读 ASR 原文**，**完全不经过 MT**。'",
     "'`asr` = 直接朗读 ASR 原文，完全不经过 MT。'"),
    # ⑪ 重复显示的根因：第二个 label 绑了同一个 var_tts_note
    #
    # 🔴🔴 **注意**：`var_tts_note2` 的**声明**在仓库侧已加好（挂在
    #    `var_tts_note` 声明之后）⇒ 包侧只需补**声明**这一处；
    #    而 `_lbl_tts_note2` 的绑定改造是**另一处**（见下一条）。
    ("        self.var_tts_note = tk.StringVar(value='')\n"
     "\n"
     "        # 🔴 **耳机提示**（APP-014：TTS 转正式功能 ⇒ 默认开启）",
     "        self.var_tts_note = tk.StringVar(value='')\n"
     "        # 🔴 APP-052 ②：离线朗读入口的**独立**说明行（不与设备说明重复）\n"
     "        self.var_tts_note2 = tk.StringVar(\n"
     "            value='离线朗读：上传音频文件或输入文本，直接播报（不经过识别与翻译）')\n"
     "\n"
     "        # 🔴 **耳机提示**（APP-014：TTS 转正式功能 ⇒ 默认开启）"),
    ("        self._lbl_tts_note2 = self._bind_wrap(\n"
     "            ttk.Label(row_tts2, textvariable=self.var_tts_note, foreground='#555'),\n"
     "            row_tts2, self.var_tts_note)",
     "        # 🔴🔴🔴 **APP-052 ②：这里原来绑的是 `var_tts_note`**\n"
     "        #   ⇒ 与上面 `_lbl_tts_note` **同一个变量**\n"
     "        #   ⇒ 同一段「设备 · 精度 · ⚠️ 设备说明」在界面上**显示了两遍**\n"
     "        #   （reviewer 原话：「同一段设备说明重复出现两次」，\n"
     "        #    1280×720 截图里可见两段几乎一样的长文本）。\n"
     "        #   ⇒ **修法**：这一行显示**离线朗读的用途说明**（本来就要一行引导），\n"
     "        #     用**独立变量** ⇒ 与设备说明不再重复。\n"
     "        #   ⚠️ 保留 `_lbl_tts_note2` 这个属性名（既有验收脚本可能引用）。\n"
     "        self.var_tts_note2 = tk.StringVar(value='')\n"
     "        self._lbl_tts_note2 = self._bind_wrap(\n"
     "            ttk.Label(row_tts2, textvariable=self.var_tts_note2,\n"
     "                      foreground='#555'),\n"
     "            row_tts2, self.var_tts_note2)"),
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    repo = find_repo_root(HERE)
    pkg = find_pkg_dir(repo)
    pkg_app = os.path.join(pkg, 'app')
    fname = 'live_caption_app.py'
    p_repo = os.path.join(repo, 'live_caption', fname)
    p_pkg = os.path.join(pkg_app, fname)
    print('[repo] %s' % repo)
    print('[pkg]  %s' % pkg)

    for p in (p_repo, p_pkg):
        if not os.path.isfile(p):
            print('  !! 缺文件：%s' % p)
            return 1

    with open(p_repo, 'r', encoding='utf-8', newline='') as f:
        src_repo = f.read()
    with open(p_pkg, 'r', encoding='utf-8', newline='') as f:
        src_pkg = f.read()

    ok = True
    plan = []
    skipped = 0
    for old, new in EDITS:
        n_repo_new = src_repo.count(new)
        n_repo_old = src_repo.count(old)
        n_pkg_old = src_pkg.count(old)
        n_pkg_new = src_pkg.count(new)
        if n_repo_new < 1 or n_repo_old != 0:
            print('  !! 仓库侧状态不对（新串 %d 次 / 旧串 %d 次，须 ≥1/0）：%s'
                  % (n_repo_new, n_repo_old, old[:60]))
            ok = False
            continue
        if n_pkg_old == 1:
            plan.append((old, new))
            print('  [ok] 包内旧串命中 1 次 ⇒ 可替换：%s' % old[:56])
        elif n_pkg_old == 0 and n_pkg_new >= 1:
            skipped += 1
            print('  [skip] 包内已是新串 ⇒ 已同步，跳过：%s' % old[:56])
        elif n_pkg_old == 0:
            print('  !! 包内旧串 0 次且新串 %d 次（状态不明）：%s'
                  % (n_pkg_new, old[:56]))
            ok = False
        else:
            print('  !! 包内旧串命中 %d 次（须恰好 1）：%s'
                  % (n_pkg_old, old[:56]))
            ok = False

    if not ok:
        print('\n[FAIL] 前置断言不通过 ⇒ 未做任何修改')
        return 1
    print('\n[plan] 待替换 %d 处 / 已同步跳过 %d 处' % (len(plan), skipped))
    if args.dry_run:
        print('[dry-run] 未写入')
        return 0

    for old, new in plan:
        with open(p_pkg, 'r', encoding='utf-8', newline='') as f:
            src = f.read()
        assert src.count(old) == 1
        out = src.replace(old, new)
        with open(p_pkg, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        with open(p_pkg, 'r', encoding='utf-8', newline='') as f:
            after = f.read()
        if after.count(old) != 0 or after.count(new) < 1:
            print('  [FAIL] 写后复核不通过（旧串 %d 次 / 新串 %d 次）：%s'
                  % (after.count(old), after.count(new), old[:56]))
            ok = False
        else:
            print('  [ok] 已替换 ＋ 复核通过：%s' % old[:56])

    # 🔴 收尾：**包内**该文件不得再有用户可见的 markdown 星号 / 研发术语
    print('\n=== 包内用户可见字符串复核 ===')
    import ast
    tree = ast.parse(after)
    doc_ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            if ast.get_docstring(n, clean=False) is not None:
                doc_ids.add(id(n.body[0].value))
    bad = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in doc_ids):
            for pat in ('**', 'onednn', 'CUDA plugin'):
                if pat in n.value:
                    bad.append((n.lineno, pat, n.value[:70]))
                    break
    if bad:
        print('  [FAIL] 仍有 %d 处用户可见字符串命中：' % len(bad))
        for b in bad:
            print('        %s' % (b,))
        ok = False
    else:
        print('  [ok] 用户可见字符串里无 markdown 星号 / onednn / CUDA plugin')

    print('\n%s' % ('[PASS] 全部同步完成' if ok else '[FAIL] 有失败项'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
