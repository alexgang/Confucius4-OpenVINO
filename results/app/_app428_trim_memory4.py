# -*- coding: utf-8 -*-
"""_app428d —— MEMORY.md 瘦身收尾：压到 **≤ 9 700 字符**（注入预算 9 800 内有余量）。

纪律：逐条唯一命中替换；压缩前全文在 `MEMORY_MODULES.md` 二十（逐字）⇒ 细节可查。
写后复核：字符数 ≤ 预算 ＋ 章节数/条目数不减少 ＋ 逐字节复核。
"""
from __future__ import annotations

import os
import re
import shutil
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
BUDGET = 9700

REPS = [
    # 一：heredoc 条 —— 细节在 MODULES
    ("- 🔴 含 `\\` 正文不用 bash heredoc ⇒ Write＋`python -c` 替换；CRLF 副本多行匹配串须带 `\\r\\n`；docstring 改 raw 后用 `ast` 常量多重集比对证值未变。",
     "- 🔴 含 `\\` 正文不用 bash heredoc ⇒ Write＋`python -c` 替换；CRLF 副本多行匹配串须带 `\\r\\n`；docstring 改 raw 后用 `ast` 常量比对证值未变。"),
    # 二：常设规则条
    ("- 🔴 常设规则：严禁按 `python.exe` 通配 kill（曾误杀 App/EXT 进程）；每段持锁 ≤ 60 min；两臂之间可释放锁；`gpu_*` 臂常设同窗 `npu_base` 控制臂。",
     "- 🔴 常设规则：严禁按 `python.exe` 通配 kill（曾误杀 App/EXT 进程）；每段持锁 ≤ 60 min；两臂之间可释放锁。"),
    # 四：PASS≠正确条
    ("- 🔴🔴🔴 PASS ≠ 正确：须拿已知有缺陷的旧产物能识破；弱标记恒真 ⇒ 查分支本体特征；抓取串须覆盖真实故障日志。",
     "- 🔴🔴🔴 PASS ≠ 正确：须拿已知有缺陷的旧产物能识破；弱标记恒真 ⇒ 查分支本体特征；抓取串须覆盖真实故障日志。"),
    # 四：FAIL 条
    ("- 🔴🔴 FAIL 先怀疑判据/环境：反证基线必须是「当前被测对象」；依赖缺失（缺 `pywin32`/`numpy` ⇒ 假 FAIL ⇒ 用仓库 `.venv`）；口径错；夹具写死时间/路径。三态 ⇒「无法判定」≠「不合格」。",
     "- 🔴🔴 FAIL 先怀疑判据/环境：反证基线必须是「当前被测对象」；依赖缺失（缺 `pywin32`/`numpy` ⇒ 假 FAIL ⇒ 用仓库 `.venv`）；口径错；三态 ⇒「无法判定」≠「不合格」。"),
    # 四：闸门判据条
    ("（会诱导把兜底 10.0 改成 5.0 ⇒ 破坏与 IR 兜底 `fp16`（160000 样本 = 10 s）的配套 ⇒ **旁路静默降级、零标签**）",
     "（会诱导把兜底 10.0 改成 5.0 ⇒ 破坏与 IR 兜底 `fp16`（= 10 s）的配套 ⇒ **旁路静默降级、零标签**）"),
    # 四：行为级真跑条
    ("⇒ **AST 直读表 + 桩里 `__file__` 指向包内真实路径 + 真跑被测函数 + 反证组用 AST 定位 + `if False:` 替换**；v1/v2 也留档。",
     "⇒ **AST 直读表 + 桩里 `__file__` 指向包内真实路径 + 真跑被测函数 + 反证组用 AST 定位 + `if False:` 替换**（v1/v2 也留档）。"),
    # 四：历史影响条
    ("⇒ 🔴 **dev 树 git 史 ≠ 交付物史**（MiniMVP rc5/rc6 的 `app/` 是字符串补丁的**独立血脉**）⇒ 逐 commit 结论**不能外推到包**，必须逐包实测；**zip 内文件要单独抽出来真跑**。",
     "⇒ 🔴 **dev 树 git 史 ≠ 交付物史**（MiniMVP rc5/rc6 的 `app/` 是字符串补丁的**独立血脉**）⇒ 逐 commit 结论**不能外推到包**，必须逐包实测。"),
    # 六：旁路条
    ("- 🔴🔴 旁路不得阻塞主循环（APP-054）：`feed()` 只入队即返回＋后台线程＋攒整窗喂（固定形状⇒帧数零漂移）＋积压不反压 ASR ⇒ 默认关闭；动态形状⇒每次调用重编译 ⇒「攒整窗」是根治方向。",
     "- 🔴🔴 旁路不得阻塞主循环（APP-054）：`feed()` 只入队即返回＋后台线程＋攒整窗喂（固定形状⇒帧数零漂移）＋积压不反压 ASR ⇒ 默认关闭；动态形状⇒「攒整窗」是根治方向。"),
    # 六：APP-086② 条
    ("⇒ 上一句的克隆音色被这句照用；且与同函数 1696–1713 注释（「spk 为 None ⇒ 必须回落预设 A」）**自相矛盾** ⇒ 收窄为 **`and not _bound`**。",
     "⇒ 上一句的克隆音色被这句照用；且与同函数 1696–1713 注释（「spk 为 None ⇒ 必须回落预设 A」）**自相矛盾** ⇒ 收窄为 **`and not _bound`**。"),
    # 六：worker 晚到标签条
    ("⇒ **绝不能**把「最近说话人」预先塞进 `spk`（会挡住官方标签 ⇒ 用错的人，比回落预设 A 更糟）⇒ 只能走既有 `spk_update` 通道。",
     "⇒ **绝不能**把「最近说话人」预先塞进 `spk`（会挡住官方标签 ⇒ 用错的人，比回落预设 A 更糟）⇒ 只走既有 `spk_update` 通道。"),
    # 六：GUI 条
    ("- 🔴🔴🔴 GUI/抓屏/快捷方式：`ImageGrab.grab()` 本机全黑 ⇒ 改 Win32 `PrintWindow`＋像素级守卫；输出设备 = `soundcard` WASAPI 端点 id ⇒ 须 `resolve_out_device()`（选了 ≠ 真用）；`.lnk` 必须用 `WScript.Shell.CreateShortcut` 生成 ⇒ COM 读回＋反证；用户走桌面 `pythonw.exe` ⇒ 测试须覆盖此路径。",
     "- 🔴🔴🔴 GUI/抓屏/快捷方式：`ImageGrab.grab()` 本机全黑 ⇒ 改 Win32 `PrintWindow`＋像素级守卫；输出设备 = `soundcard` WASAPI 端点 id ⇒ 须 `resolve_out_device()`（选了 ≠ 真用）；`.lnk` 必须用 `WScript.Shell.CreateShortcut` 生成 ⇒ COM 读回；用户走桌面 `pythonw.exe` ⇒ 测试须覆盖此路径。"),
    # 七：iGPU 条
    ("⇒ **交付配置冻结 = 全 NPU / spkonly / INT8**；NPU 变慢根因 =「同 SoC 的集显/DRAM/封装被抢」⇒ 判据用 SoC 负载（不是核数）、限线程无效。",
     "⇒ **交付配置冻结 = 全 NPU / spkonly / INT8**；NPU 变慢根因 =「同 SoC 的集显/DRAM/封装被抢」⇒ 判据用 SoC 负载（不是核数）。"),
    # 八：CRLF 条
    ("⇒ ①「逐字节比对」须先归一化行尾 ②字符串锚点匹配在 clone 恒为 0 ⇒ 定点同步脚本必然定位失效 ③读入归一化、写回还原行尾。",
     "⇒ ①「逐字节比对」须先归一化行尾 ②字符串锚点匹配在 clone 恒为 0 ⇒ 定点同步必然定位失效 ③读入归一化、写回还原行尾。"),
    # 八：A/B 条
    ("⇒ 比值才有效；顺序对照 ≠ ABBA；「磁盘上存在」≠「已交付」（zip ⇄ 包目录逐字节一致才算）；`ACCEPTED.json` 在 zip 内 ⇒ 必须「先按新代码重签 → 再打包」。",
     "⇒ 比值才有效；顺序对照 ≠ ABBA；「磁盘上存在」≠「已交付」（zip ⇄ 包目录逐字节一致才算）；`ACCEPTED.json` 在 zip 内 ⇒ 先重签再打包。"),
    # 十：交付版条
    ("口径 A 已作废 ⇒ 唯一口径 = 口径 B 7/12 = 58.33 % ⇒ 不得为凑 60 % 调阈值。APP-066 MiniMVP 独立版本线 ⇒ 不覆盖/不删除旧目录与 zip。",
     "口径 A 已作废 ⇒ 唯一口径 = 口径 B 7/12 = 58.33 % ⇒ 不得为凑 60 % 调阈值。APP-066 MiniMVP 独立版本线 ⇒ 不覆盖/删旧目录与 zip。"),
    # 十：D1 条
    ("🔴 但「唯一事实来源」被改 ≠ 下游都读它 ⇒ 跨模块常量须核对所有下游消费者。改 dev 树 ⇒ 必须复跑既有回归套件 ⇒ 输出另存。",
     "🔴 但「唯一事实来源」被改 ≠ 下游都读它 ⇒ 跨模块常量须核对所有下游。改 dev 树 ⇒ 必须复跑既有回归套件 ⇒ 输出另存。"),
    # 十：APP-076 条
    ("APP-077：EXT 的 `bridge_token.txt` 是**固定值** ⇒ 以后的包**不带**，改首次启动在用户目录随机生成；旧包不原地改；桥接快捷方式用 pythonw 无日志 ⇒ 新包须「启动失败弹提示框」。",
     "APP-077：EXT 的 `bridge_token.txt` 是**固定值** ⇒ 以后的包**不带**，改首次启动在用户目录随机生成；旧包不原地改；桥接快捷方式用 pythonw 无日志 ⇒ 新包须弹提示框。"),
    # 十一：§2-4 两半条
    ("§167/§171 只做了「报数」⇒ 6 种新语言长期停在占位 0.07（初值偏小 ⇒ 失控守卫阈值偏低 ⇒ 可能误杀正常长句）。",
     "§167/§171 只做了「报数」⇒ 6 种新语言长期停在占位 0.07（初值偏小 ⇒ 失控守卫阈值偏低 ⇒ 可能误杀长句）。"),
    # 十二：§172 条
    ("- 🔴 **§172（11-11 02:21）**：无新纠偏（开工＝收尾指纹一致 ⇒ SHA 零改动）；**补做 APP-097 §2-4 回填**（6 新语言 `_SEC_PER_CHAR` 0.07 → .073/.070/.085/.080/.081/.083）＋新闸门 27/27（含 3 反证）＋app109 回归 34/34 ⇒ **只改开发树 `live_caption/tts_engine.py`**；v2.5 未打包、未通知用户。",
     "- 🔴 **§172（11-11 02:21）**：无新纠偏（开工＝收尾指纹一致 ⇒ SHA 零改动）；**补做 APP-097 §2-4 回填**（6 新语言 `_SEC_PER_CHAR` 0.07 → .073/.070/.085/.080/.081/.083）＋新闸门 27/27（含 3 反证）＋app109 回归 34/34 ⇒ **只改开发树 `tts_engine.py`**；v2.5 未打包、未通知用户。"),
    # 十二：§171 条
    ("**D2（asr06b label 撞车）= 已交付的 rc5 中招** ⇒ **rc5/rc6 = BUG**（label 重复、**NPU 档在 GUI 下拉里不存在**）／**rc7 = OK**／其余 NA；**rc5 的 CLI 验收绕开 GUI ⇒ 结构性不可见**。",
     "**D2（asr06b label 撞车）= 已交付的 rc5 中招** ⇒ **rc5/rc6 = BUG**（label 重复、**NPU 档在 GUI 下拉里不存在**）／**rc7 = OK**／其余 NA；**rc5 的 CLI 验收绕开 GUI ⇒ 不可见**。"),
    # 十二：风险条
    ("**§3.5 判据失效**（真值余弦 0.957–0.972 ⇒ 不可分）⇒ 未自行换判据；**§3.6 切段 ASR RTF 已补做**（0.621 vs 0.627 ⇒ 噪声地板内）。",
     "**§3.5 判据失效**（真值余弦 0.957–0.972 ⇒ 不可分）⇒ 未自行换判据；**§3.6 切段 ASR RTF 已补做**（0.621 vs 0.627 ⇒ 噪声地板内）。"),
    # 十一：闸门条
    ("- 🔴 新闸门 `live_caption/assert_sec_per_char_calibrated.py`（dev 树，**未进客户包** ⇒ v2.5 建包别把 `assert_*.py` 带进 `app/`）：A 值==证据复算／B 既有 4 语言未变／C 10 键／D 新值≥0.07／E 别名同值／F 反证 3 组。",
     "- 🔴 新闸门 `live_caption/assert_sec_per_char_calibrated.py`（dev 树，**未进客户包** ⇒ v2.5 建包别把 `assert_*.py` 带进 `app/`）：A 值==证据复算／B 既有 4 语言未变／C 10 键／D 新值≥0.07／E 别名同值／F 反证 3 组。"),
    # 十二：新发现条
    ("- 🔴 **新发现（只报不改）**：`--tts-voice A`＋说话人识别开 ⇒ **78/78 句仍用 self_ref 克隆音色** ⇒ 与 v2.4 验收口径冲突 ⇒ 根因 = `_maybe_send_self_ref` 缺 `_want_clone` 闸门。",
     "- 🔴 **新发现（只报不改）**：`--tts-voice A`＋说话人识别开 ⇒ **78/78 句仍用 self_ref 克隆音色** ⇒ 与 v2.4 验收口径冲突 ⇒ 根因 = `_maybe_send_self_ref` 缺 `_want_clone` 闸门。"),
    # 头部：索引行压紧
    ("> **逐字全文**在 `MEMORY_MODULES.md`（四＝判据｜五–八＝App/GUI｜十＝设备归属｜十二＝交付｜十三＝TTS｜**二十＝压缩前全文，含下列各节逐字**）；存档 `MEMORY_ARCHIVE_*.md`；进展 `.workbuddy/memory/YYYY-MM-DD.md`（不入 git）。",
     "> **逐字全文**在 `MEMORY_MODULES.md`（四＝判据｜五–八＝App/GUI｜十＝设备归属｜十二＝交付｜十三＝TTS｜**二十＝压缩前全文**）；存档 `MEMORY_ARCHIVE_*.md`；进展 `.workbuddy/memory/YYYY-MM-DD.md`（不入 git）。"),
    # 十一：回填口径条
    ("- 🔴 **回填口径（§172 定案，等 reviewer 复核）**：`value = ceil3(max(preset_p50, clone_p50))`，源 = 已落盘 `results/app/app326_app097_lang_out/tts.json` ⇒ **复算不手抄**；两音色取大 + 向上取整 ⇒ 守卫阈值**只可能不变或变松**；zh/en/ja/ko 不动；**倍率地板未改**（等 reviewer）。",
     "- 🔴 **回填口径（§172 定案，等 reviewer 复核）**：`value = ceil3(max(preset_p50, clone_p50))`，源 = 已落盘 `results/app/app326_app097_lang_out/tts.json` ⇒ **复算不手抄**；两音色取大 + 向上取整 ⇒ 守卫阈值**只可能不变或变松**；zh/en/ja/ko 不动；**倍率地板未改**。"),
    # 八：影子包条
    ("⇒ diff 落盘供 reviewer 核对「没改判据」；**开发树一字不改**。**影子包底座必须全量对齐开发树**（混版 ⇒ 接口缺失 ⇒ 路径没跑到）⇒ 自检 `py_files_differing_from_dev == ['<探针文件>']`。",
     "⇒ diff 落盘供 reviewer 核对「没改判据」；**开发树一字不改**。**影子包底座必须全量对齐开发树**（混版 ⇒ 接口缺失 ⇒ 路径没跑到）⇒ 自检 `py_files_differing_from_dev` 只差探针文件。"),
]


def main() -> None:
    t = open(MEM, encoding='utf-8').read()
    before = len(t)
    ns = len(re.findall(r'^## ', t, re.M))
    nb = len(re.findall(r'^- ', t, re.M))
    for a, b in REPS:
        if t.count(a) != 1:
            print('MISS(%d) %s' % (t.count(a), a[:40]))
            continue
        t = t.replace(a, b, 1)
    after = len(t)
    ns2 = len(re.findall(r'^## ', t, re.M))
    nb2 = len(re.findall(r'^- ', t, re.M))
    ok = after <= BUDGET and ns == ns2 and nb == nb2
    print('chars %d -> %d (budget %d) sec %d->%d bul %d->%d %s'
          % (before, after, BUDGET, ns, ns2, nb, nb2, 'OK' if ok else 'NOT OK'))
    if ok:
        bak = MEM + '.bak_pre_slim_20261111_%s' % time.strftime('%H%M%S')
        shutil.copy2(MEM, bak)
        tmp = MEM + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(t)
        os.replace(tmp, MEM)
        assert open(MEM, encoding='utf-8').read() == t, 'byte verify failed'
        print('WROTE %s (%d bytes)' % (MEM, os.path.getsize(MEM)))


if __name__ == '__main__':
    main()
