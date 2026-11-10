# -*- coding: utf-8 -*-
"""_app428b —— MEMORY.md 瘦身第二轮：定点删冗余从句，压到 ≤ 9 000 字符。

纪律：逐条**唯一命中**的字符串替换；压缩前全文已在 `MEMORY_MODULES.md` 二十 ⇒ 细节可查。
写前自检：每条唯一命中；写后复核字符数 ≤ 预算 + 逐字节复核。
"""
from __future__ import annotations

import os
import shutil
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
BUDGET = 9000

REPS = [
    # 一：STATUS 写入条 —— 去掉重复的「先临时文件再原子替换」（九节已有）
    ("🔴 `STATUS_*.md` 定点写入：只动头部、只追加、旧正文一字不删；写后验章节不少＋旧正文逐字未变＋行尾未破；先临时文件再原子替换。",
     "🔴 `STATUS_*.md` 定点写入：只动头部、只追加、旧正文一字不删；写后验章节不少＋旧正文逐字未变＋行尾未破。"),
    # 二：后台作业条
    ("⇒ 立刻 `addpid`；被杀后先以 err==87 确证死再回收；等锁先探测、不反复建删 tmp。",
     "⇒ 立刻 `addpid`；被杀后先以 err==87 确证死再回收；等锁先探测。"),
    # 四：PASS≠正确条
    ("- 🔴🔴🔴 PASS ≠ 正确：须拿已知有缺陷的旧产物能识破；弱标记恒真 ⇒ 查分支本体特征；抓取串须覆盖真实故障日志，写完拿真实失败日志反查。",
     "- 🔴🔴🔴 PASS ≠ 正确：须拿已知有缺陷的旧产物能识破；弱标记恒真 ⇒ 查分支本体特征；抓取串须覆盖真实故障日志。"),
    # 四：FAIL 先怀疑条
    ("- 🔴🔴 FAIL 先怀疑判据/环境：反证基线必须是「当前被测对象」；依赖缺失（缺 `pywin32`/`numpy` ⇒ 假 FAIL ⇒ 用仓库 `.venv`）；口径错；夹具写死时间/路径。三态 True/False/None ⇒「无法判定」≠「不合格」。",
     "- 🔴🔴 FAIL 先怀疑判据/环境：反证基线必须是「当前被测对象」；依赖缺失（缺 `pywin32`/`numpy` ⇒ 假 FAIL ⇒ 用仓库 `.venv`）；口径错；夹具写死时间/路径。三态 ⇒「无法判定」≠「不合格」。"),
    # 四：反证构造条
    ("；多调用点须破坏全部。`ast`+`exec` 坑：丢 `Import` ⇒ NameError ⇒ 假 FAIL；",
     "；多调用点须破坏全部。`ast`+`exec` 坑：丢 `Import` ⇒ NameError；"),
    # 四：闸门判据条
    ("（会诱导把兜底 10.0 改成 5.0 ⇒ 破坏与 IR 兜底 `fp16`（160000 样本 = 10 s）的配套 ⇒ **旁路静默降级、零标签**）",
     "（会诱导把兜底 10.0 改成 5.0 ⇒ 破坏与 IR 兜底 `fp16`（160000 样本 = 10 s）的配套 ⇒ **旁路静默降级、零标签**）"),
    # 五：设备归属条
    ("⇒ `list(devs)` 拆成 `['N','P','U']` ⇒ 旧「fallback 链」是误读；CPU 档返字符串落进 `on_unknown` ⇒ 静默漏报回落。",
     "⇒ `list(devs)` 拆成 `['N','P','U']`（旧「fallback 链」是误读）；CPU 档返字符串落进 `on_unknown` ⇒ 静默漏报回落。"),
    # 六：音色回落条
    ("⇒ 保留克隆音色 / 回落预设 A；同成立按句绑定优先。「为修 X 引入的 else 分支」会静默改另一条语义 ⇒ 改分支后必须复跑回归。",
     "⇒ 保留克隆音色 / 回落预设 A；同成立按句绑定优先。「为修 X 引入的 else 分支」会静默改另一条语义 ⇒ 改后必须复跑回归。"),
    # 六：APP-086② 条
    ("⇒ 上一句的克隆音色被这句照用；且与同函数 1696–1713 注释（「spk 为 None ⇒ 必须回落预设 A」）**自相矛盾** ⇒ 收窄为 **`and not _bound`**。",
     "⇒ 上一句的克隆音色被这句照用；且与同函数 1696–1713 注释（「spk 为 None ⇒ 必须回落预设 A」）**自相矛盾** ⇒ 收窄为 **`and not _bound`**。"),
    # 六：GUI 条
    ("- 🔴🔴🔴 GUI/抓屏/快捷方式：`ImageGrab.grab()` 本机全黑 ⇒ 改 Win32 `PrintWindow`＋像素级守卫；输出设备 = `soundcard` WASAPI 端点 id ⇒ 须 `resolve_out_device()`（选了 ≠ 真用）；`.lnk` 必须用 `WScript.Shell.CreateShortcut` 生成 ⇒ COM 读回＋反证＋仓库 `.venv`；用户走桌面 `pythonw.exe` ⇒ 测试须覆盖此路径。",
     "- 🔴🔴🔴 GUI/抓屏/快捷方式：`ImageGrab.grab()` 本机全黑 ⇒ 改 Win32 `PrintWindow`＋像素级守卫；输出设备 = `soundcard` WASAPI 端点 id ⇒ 须 `resolve_out_device()`（选了 ≠ 真用）；`.lnk` 必须用 `WScript.Shell.CreateShortcut` 生成 ⇒ COM 读回＋反证；用户走桌面 `pythonw.exe` ⇒ 测试须覆盖此路径。"),
    # 七：TTS 帧数条
    ("⇒ 引用负加速数字须限定「当前 IR + oneDNN GPU 下」；⚠️ 顺序对照 ≠ ABBA、跨会话绝对 RTF 不可比；cp unroll NO-GO；41 ms 异常值不得引用。",
     "⇒ 引用负加速数字须限定「当前 IR + oneDNN GPU 下」；⚠️ 顺序对照 ≠ ABBA、跨会话绝对 RTF 不可比；cp unroll NO-GO。"),
    # 七：TTS-055/056 条
    ("⇒ §73.5「崩塌⇒不值得」是**判据口径问题**（0.999/0.99 为 fp16 判据，不适用 INT8 weight-only）⇒ **撤回该因果表述**、交 reviewer 定口径；两次都**不启动阶段 2/3**。",
     "⇒ §73.5「崩塌⇒不值得」是**判据口径问题**（0.999/0.99 为 fp16 判据，不适用 INT8 weight-only）⇒ **撤回该因果表述**、交 reviewer 定口径。"),
    # 八：CRLF 条
    ("⇒ ①「逐字节比对」判据须先归一化行尾 ②字符串锚点匹配在 clone 恒为 0 ⇒ 定点同步脚本必然定位失效 ③读入归一化、写回还原原行尾。",
     "⇒ ①「逐字节比对」须先归一化行尾 ②字符串锚点匹配在 clone 恒为 0 ⇒ 定点同步脚本必然定位失效 ③读入归一化、写回还原行尾。"),
    # 八：影子包条
    ("（只加日志 + env 门控提前返回）⇒ diff 落盘供 reviewer 核对「没改判据」；**开发树一字不改**。",
     "（只加日志 + env 门控提前返回）⇒ diff 落盘供 reviewer 核对「没改判据」；**开发树一字不改**。"),
    # 九：压缩条
    ("- 🔴 模板生成 + 占位符不动点迭代 ⇒ 自指大小必须与磁盘实测一致（差 2 B 也要改）⇒ 压缩后复核 ≤40 KB / ≤300 行 ＋ 归档件逐字命中 ＋ 旧正文整块原样保留。",
     "- 🔴 模板生成 + 占位符不动点迭代 ⇒ 自指大小必须与磁盘实测一致（差 2 B 也要改）⇒ 压缩后复核 ≤40 KB / ≤300 行 ＋ 归档件逐字命中 ＋ 旧正文原样保留。"),
    # 十：交付版条
    ("今后只打 v2.3+ 新版本号（新目录＋新 zip＋新 MANIFEST＋重签 ACCEPTED），永不 `--same-version`、永不原地改旧版；.lnk 版本号从目标包目录名派生。",
     "今后只打 v2.3+ 新版本号（新目录＋新 zip＋新 MANIFEST＋重签 ACCEPTED），永不 `--same-version`、永不原地改旧版；.lnk 版本号由目标包目录名派生。"),
    # 十：APP-071/075 条
    ("⇒ 不接受只统计 voice_kind 的验收；须 ①每音色落盘诊断 ②真 x-vector 余弦矩阵（反证组须能被识破）③登记加 `spk_conf` 门槛＋≥2.5 s 连续干净＋pending 标记",
     "⇒ 不接受只统计 voice_kind 的验收；须 ①每音色落盘诊断 ②真 x-vector 余弦矩阵（反证组须能被识破）③登记加 `spk_conf` 门槛＋≥2.5 s 连续干净＋pending"),
    # 十一：回填口径条
    ("⇒ **复算不手抄**；两音色取大 + 向上取整 ⇒ 守卫阈值**只可能不变或变松、绝不变紧**；zh/en/ja/ko 不动；**倍率地板未改**（等 reviewer）。",
     "⇒ **复算不手抄**；两音色取大 + 向上取整 ⇒ 守卫阈值**只可能不变或变松**；zh/en/ja/ko 不动；**倍率地板未改**（等 reviewer）。"),
    # 十二：§172 条
    ("＋新闸门 27/27（含 3 反证）＋app109 回归 34/34 ⇒ **只改开发树 `live_caption/tts_engine.py`，未碰客户包**；v2.5 未打包、未通知用户。",
     "＋新闸门 27/27（含 3 反证）＋app109 回归 34/34 ⇒ **只改开发树 `live_caption/tts_engine.py`**；v2.5 未打包、未通知用户。"),
    # 十二：§171 条
    ("**D1（GUI 布局被吞）= 零交付物受影响**（15 包 AST 判定 0 中招）⇒ **真机制纠正**：`_clone_nearest` 是**兄弟方法**（**不是嵌套**）。",
     "**D1（GUI 布局被吞）= 零交付物受影响**（15 包 AST 判定 0 中招）⇒ **真机制纠正**：`_clone_nearest` 是**兄弟方法**（非嵌套）。"),
    # 十二：风险条
    ("⇒ 打包需 10–15 G ⇒ **空间不足会直接失败**；**未删任何文件** ⇒ 待 reviewer / 用户决定。",
     "⇒ 打包需 10–15 G ⇒ **空间不足会直接失败**；**未删任何文件** ⇒ 待 reviewer 决定。"),
]


def main() -> None:
    t = open(MEM, encoding='utf-8').read()
    before = len(t)
    miss = 0
    for a, b in REPS:
        n = t.count(a)
        if n != 1:
            print('MISS(%d) %s' % (n, a[:44]))
            miss += 1
            continue
        t = t.replace(a, b, 1)
    after = len(t)
    print('chars %d -> %d (budget %d, miss %d) %s'
          % (before, after, BUDGET, miss, 'OK' if after <= BUDGET else 'STILL OVER'))
    if after <= BUDGET:
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
