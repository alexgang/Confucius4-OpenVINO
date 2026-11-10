# -*- coding: utf-8 -*-
"""_app428 —— MEMORY.md 第十次瘦身：定点压缩到注入预算内（≤ ~9 000 字符）。

纪律：
- 只做**定点字符串替换**（唯一命中），不改结构、不删条目 ⇒ 压缩后仍保留全部判据条目。
- 压缩前的**逐字全文**已整块存入 `MEMORY_MODULES.md` 二十 ⇒ 细节可查。
- 写前自检：每条替换唯一命中；写后复核字符数 ≤ 预算。
"""
from __future__ import annotations

import os
import shutil
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
BUDGET_CHARS = 9800

REPS = [
    # ── 结构性压缩：把「长引用原文」换成「指针 + 结论」 ──
    # 四：闸门判据条（逐字在 MODULES 二十）
    ("- 🔴🔴 **闸门自己的判据也会是错的**：判据写成「兜底 == ASR 当前默认值」⇒ 实测 FAIL ⇒ **该判据本身错**（会诱导把兜底 10.0 改成 5.0 ⇒ 破坏与 IR 兜底 `fp16`（160000 样本 = 10 s）的配套 ⇒ **旁路静默降级、零标签**）⇒ 正确判据是「**兜底窗长 == IR 兜底窗长**」⇒ **写闸门前先问「这条判据若被人当真去改生产代码，会不会改坏」**。",
     "- 🔴🔴 **闸门自己的判据也会是错的**（2026-11-10 实例）：「兜底 == ASR 当前默认值」这个判据本身错（会诱导把兜底 10.0 改成 5.0 ⇒ 破坏与 IR 兜底 `fp16`（160000 样本 = 10 s）的配套 ⇒ **旁路静默降级、零标签**）⇒ 正确判据是「**兜底窗长 == IR 兜底窗长**」⇒ **写闸门前先问「这条判据若被人当真去改生产代码，会不会改坏」**。"),
    # 四：行为级真跑条
    ("- 🔴🔴🔴 **判据改成「行为级真跑」才是定论**（2026-11-11，同一判据连改三轮：v1 假阴性／v2 假阳性／v3 定案）⇒ **AST 直读表 + 桩里 `__file__` 指向包内真实路径 + 真跑一遍被测函数 + 反证组用 AST 定位 + `if False:` 替换**；**v1/v2 也要留档**。",
     "- 🔴🔴🔴 **判据改成「行为级真跑」才是定论**（2026-11-11，同一判据连改三轮：v1 假阴性／v2 假阳性／v3 定案）⇒ **AST 直读表 + 桩里 `__file__` 指向包内真实路径 + 真跑被测函数 + 反证组用 AST 定位 + `if False:` 替换**；v1/v2 也留档。"),
    # 六：APP-086② 条
    ("- 🔴🔴🔴 **APP-086②「男声被配成女声」根因（读码定案）**：`tts_worker.py` 的 `elif self._has_clone_voice():` → `_log_keep_last_clone()` **只改遥测、不改引擎音色**（`speaker_embed`/`speaker_name` 原样留着）⇒ 上一句的克隆音色被这句照用；且与同函数 1696–1713 注释（「spk 为 None ⇒ 必须回落预设 A」）**自相矛盾**。APP-086②a ⇒ 收窄为 **`and not _bound`**。「全局克隆定时采集器已停用」⇒ `_clone_active` 恒 False ⇒「沿用上一句音色」在 App 常态下已成死路径。",
     "- 🔴🔴🔴 **APP-086②「男声被配成女声」根因（读码定案）**：`tts_worker.py` 的 `elif self._has_clone_voice():` → `_log_keep_last_clone()` **只改遥测、不改引擎音色**（`speaker_embed`/`speaker_name` 原样留着）⇒ 上一句的克隆音色被这句照用；且与同函数 1696–1713 注释（「spk 为 None ⇒ 必须回落预设 A」）**自相矛盾** ⇒ 收窄为 **`and not _bound`**。「全局克隆采集器已停用」⇒ `_clone_active` 恒 False ⇒「沿用上一句音色」已成死路径。"),
    # 六：CUDA/GUI 条
    ("- 🔴🔴 CUDA 置灰 = 行为性拦截（`ttk.Combobox` 不支持逐项 `state=['disabled']`）⇒ 项标 `disabled`+`why`、不可用项不作初值、选中不可用项 ⇒ 拒绝启动＋显示原因 ⇒ 判据查锚点字符串不查 `state=`。状态栏「模型」取真值（engine_key+实际设备）。GUI 重排（APP-065 A）：5 组 GroupBox；「等宽」必须用**像素**（`ttk.Label(width=N)` 的 N 是字符数 ⇒ 跨缩放不可比）⇒ `uniform='lbl'`＋`minsize`＋`anchor='e'`；`messagebox` 模态 ⇒ 无头探针会挂死 ⇒ 弹框加「有 GUI root 才弹」守卫。",
     "- 🔴🔴 CUDA 置灰 = 行为性拦截（`ttk.Combobox` 不支持逐项 `state=['disabled']`）⇒ 项标 `disabled`+`why`、不可用项不作初值、选中不可用项 ⇒ 拒绝启动＋显示原因 ⇒ 判据查锚点字符串不查 `state=`。状态栏「模型」取真值（engine_key+实际设备）。GUI 重排（APP-065 A）：5 组 GroupBox；「等宽」必须用**像素**（`ttk.Label(width=N)` 的 N 是字符数 ⇒ 跨缩放不可比）⇒ `uniform='lbl'`＋`minsize`＋`anchor='e'`；`messagebox` 模态 ⇒ 无头探针会挂死 ⇒ 弹框加「有 GUI root 才弹」守卫。"),
    # 十：APP-071/075 条
    ("- 🔴🔴 APP-071/075（BLOCKING）：v23_clone 男声 3 段听上去是女声 ⇒ 克隆音色串到女声 ⇒ 不接受只统计 voice_kind 的验收；须 ①每音色落盘诊断 ②真 x-vector 余弦矩阵（反证组须能被识破）③登记加 `spk_conf` 门槛＋≥2.5 s 连续干净＋pending 标记 ④重交 `v23_clone_r2/`＋F0 闸门（男 <160 Hz／女 >170 Hz）⑤未通过前 v2.3 不打包。",
     "- 🔴🔴 APP-071/075（BLOCKING）：v23_clone 男声 3 段听上去是女声 ⇒ 克隆音色串到女声 ⇒ 不接受只统计 voice_kind 的验收；须 ①每音色落盘诊断 ②真 x-vector 余弦矩阵（反证组须能被识破）③登记加 `spk_conf` 门槛＋≥2.5 s 连续干净＋pending 标记 ④重交 `v23_clone_r2/`＋F0 闸门（男 <160／女 >170 Hz）⑤未通过前 v2.3 不打包。"),
    # 十二：§171 条
    ("- 🔴 **§171 两项「历史影响未评估」定界**（全文在 STATUS §171 归档件）：① **D1（GUI 布局被吞）= 零交付物受影响**（15 包逐个 AST 判定 0 中招；PASS 结论未被污染）⇒ **真机制纠正**：`_clone_nearest` 是**兄弟方法**（**不是嵌套**）。② 🔴 **D2（asr06b label 撞车）= 已交付的 rc5 中招** ⇒ **rc5/rc6 = BUG**（label 重复、**NPU 档在 GUI 下拉里不存在**）／**rc7 = OK**／其余 12 包 NA；**rc5 的 CLI 验收绕开 GUI ⇒ 结构性不可见**。",
     "- 🔴 **§171 两项「历史影响未评估」定界**（全文在 STATUS §171 归档件）：① **D1（GUI 布局被吞）= 零交付物受影响**（15 包 AST 判定 0 中招）⇒ **真机制纠正**：`_clone_nearest` 是**兄弟方法**（**不是嵌套**）。② 🔴 **D2（asr06b label 撞车）= 已交付的 rc5 中招** ⇒ **rc5/rc6 = BUG**（label 重复、**NPU 档在 GUI 下拉里不存在**）／**rc7 = OK**／其余 NA；**rc5 的 CLI 验收绕开 GUI ⇒ 结构性不可见**。"),
    # 十二：§172 条
    ("- 🔴 **§172（11-11 02:21）**：无新纠偏（开工＝收尾指纹逐字一致 ⇒ SHA 零改动）；**补做 APP-097 §2-4 回填**（6 新语言 `_SEC_PER_CHAR` 0.07 → .073/.070/.085/.080/.081/.083）＋新闸门 27/27（含 3 反证）＋app109 回归 34/34 ⇒ **只改开发树 `live_caption/tts_engine.py`，未碰客户包目录**；v2.5 未打包、未通知用户。",
     "- 🔴 **§172（11-11 02:21）**：无新纠偏（开工＝收尾指纹一致 ⇒ SHA 零改动）；**补做 APP-097 §2-4 回填**（6 新语言 `_SEC_PER_CHAR` 0.07 → .073/.070/.085/.080/.081/.083）＋新闸门 27/27（含 3 反证）＋app109 回归 34/34 ⇒ **只改开发树 `live_caption/tts_engine.py`，未碰客户包**；v2.5 未打包、未通知用户。"),
    # 十二：风险条
    ("- 🔴 **风险：C 盘 99 %、仅剩 23 G** ⇒ 打包需 10–15 G ⇒ **空间不足会直接失败**；**未删任何文件** ⇒ 待 reviewer / 用户决定。**§3.5 判据失效**（真值余弦 0.957–0.972 ⇒ 不可分）⇒ **未自行换判据**；**§3.6 切段 ASR RTF 已补做**（0.621 vs 0.627 ⇒ 落在噪声地板内）。",
     "- 🔴 **风险：C 盘 99 %、仅剩 23 G** ⇒ 打包需 10–15 G ⇒ **空间不足会直接失败**；**未删任何文件** ⇒ 待 reviewer / 用户决定。**§3.5 判据失效**（真值余弦 0.957–0.972 ⇒ 不可分）⇒ 未自行换判据；**§3.6 切段 ASR RTF 已补做**（0.621 vs 0.627 ⇒ 噪声地板内）。"),
    # 十一：§2.4 两半条
    ("- 🔴 **§2-4 的两半要分开读**：reviewer §2-4 =「报『合成时长 ÷ 字符数』的 p50，**用它定 `_SEC_PER_CHAR`**」＋「报 ratio p50 给 reviewer 判断**倍率地板**；**倍率默认值不改，只报数字**」⇒ **前者要回填，后者只报数**。§167/§171 只做了「报数」那一半 ⇒ 6 种新语言长期停在占位 0.07（初值偏小 ⇒ 失控守卫阈值偏低 ⇒ 可能误杀正常长句）。",
     "- 🔴 **§2-4 的两半要分开读**：§2-4 =「报『合成时长 ÷ 字符数』的 p50，**用它定 `_SEC_PER_CHAR`**」＋「报 ratio p50 供 reviewer 判断**倍率地板**；**倍率默认值不改，只报数字**」⇒ **前者要回填，后者只报数**。§167/§171 只做了「报数」⇒ 6 种新语言长期停在占位 0.07（初值偏小 ⇒ 失控守卫阈值偏低 ⇒ 可能误杀正常长句）。"),
    # 十一：回填口径条
    ("- 🔴 **回填口径（§172 定案，等 reviewer 复核）**：`value = ceil3(max(preset_p50, clone_p50))`，源 = 已落盘 `results/app/app326_app097_lang_out/tts.json` ⇒ **复算不手抄**；两音色取大 + 向上取整 ⇒ 守卫阈值**只可能不变或变松、绝不变紧**；zh/en/ja/ko 逐字不动；**倍率地板未改**（等 reviewer）。",
     "- 🔴 **回填口径（§172 定案，等 reviewer 复核）**：`value = ceil3(max(preset_p50, clone_p50))`，源 = 已落盘 `results/app/app326_app097_lang_out/tts.json` ⇒ **复算不手抄**；两音色取大 + 向上取整 ⇒ 守卫阈值**只可能不变或变松、绝不变紧**；zh/en/ja/ko 不动；**倍率地板未改**（等 reviewer）。"),
]


def main() -> None:
    t = open(MEM, encoding='utf-8').read()
    before = len(t)
    for a, b in REPS:
        n = t.count(a)
        if n != 1:
            print('MISS(%d) %s' % (n, a[:46]))
            continue
        t = t.replace(a, b, 1)
    after = len(t)
    print('chars %d -> %d (budget %d) %s'
          % (before, after, BUDGET_CHARS, 'OK' if after <= BUDGET_CHARS else 'STILL OVER'))
    if after <= BUDGET_CHARS:
        bak = MEM + '.bak_pre_slim_20261111_%s' % time.strftime('%H%M%S')
        shutil.copy2(MEM, bak)
        tmp = MEM + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(t)
        os.replace(tmp, MEM)
        back = open(MEM, encoding='utf-8').read()
        assert back == t, 'byte verify failed'
        print('WROTE %s (%d bytes)' % (MEM, os.path.getsize(MEM)))
        print('backup %s' % os.path.basename(bak))
    else:
        print('NOT WRITTEN (over budget)')


if __name__ == '__main__':
    main()
