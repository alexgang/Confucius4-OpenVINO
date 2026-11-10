#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app434_trim_memory.py —— 把 MEMORY.md 压回自述预算（≤ 9 700 字符）。

做法：按**行首前缀断言**定位 ⇒ 不会误伤别的行；逐行替换为**更短**的版本
（脚本断言每行确实变短 ⇒ 不会假装修正）。

纪律：12 节标题与全部条目逐条保留、**事实不删**（只压从句与重复表述）；
§12 各轮的**逐字明细**在 `status/app/STATUS_APP.md` §171/§172/§173/§174（该节抬头已声明
「明细以 `status/app/STATUS_APP.md` 为准」）；压缩前逐字全文在 `MEMORY_MODULES.md` 二十一。
"""
import os
import sys

P = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), '.workbuddy', 'memory', 'MEMORY.md')

s = open(P, encoding='utf-8').read()
before = len(s)
lines = s.split('\n')

# (前缀断言, 新行) —— 新行必须**比旧行短**
REPL = [
    # ① §12 抬头：时间戳 → 本轮（**保留「明细以 STATUS_APP.md 为准」那句**）
    ("## 十二、App 模块当前状态（2026-11-11 04:10；明细以 `status/app/STATUS_APP.md` 为准）",
     "## 十二、App 模块当前状态（2026-11-11 06:40；明细以 STATUS_APP.md 为准）"),
    # ② last_ack 那条：节点 → §174
    ("- 🔴 `last_ack=APP-098`；",
     "- 🔴 `last_ack=APP-098`；`CORRECTIONS_APP.md` **97 条 / 最大 APP-097**"
     "（SHA `36af1620…`／285 671 B）⇒ **APP-098 是 reviewer 口头下达、未落该文件**"
     "；节点 = **等 reviewer 复核 §174**。"),
    # ③ §173 那条 ⇒ 指针（逐字明细见 STATUS_APP.md §173 ＋归档件）
    ("- 🔴 **§173（04:07）**：",
     "- 🔴 **§173（04:07）**：无新纠偏；修掉 STATUS 头部 4 处过期／矛盾＋新增「归档指针可核对性」判据"
     "（逐字明细见 STATUS_APP.md §173）。"),
    # ④ §172 那条 ⇒ 压成一句
    ("- 🔴 **§172（02:21）**：",
     "- 🔴 **§172（02:21）**：无新纠偏；补做 §2-4 回填（6 新语言，见十一节）＋闸门 27/27＋app109 34/34。"),
    # ⑤ 「新发现（只报不改）」⇒ 已修（§174）
    ("- 🔴 **新发现（只报不改）**：",
     "- 🔴 **self_ref 闸门已修**（§174）：根因 = `_maybe_send_self_ref`／`_cli_maybe_send_self_ref` "
     "缺克隆模式闸门 ⇒ 已补（**只改 dev 树**，客户包未动 ⇒ 已交付包零影响）。"),
    # ⑥ HEAD 更新
    ("- 🔴 交付配置冻结 **全 NPU/spkonly/INT8**；",
     "- 🔴 交付配置冻结 **全 NPU/spkonly/INT8**；EXT 内嵌 = **v0.3.7 @c414294**；"
     "仓库 HEAD = `37eeae5`（ahead=0）。"),
    # ⑦ 压缩：APP-076 那条（事实不删，只压从句）
    ("- 🔴🔴 APP-076：",
     "- 🔴🔴 APP-076：`min_clean_ratio` 0.8→0.6 同步进 dev + 下一版包；🔴 克隆登记**不放宽**；"
     "环境变量 `LIVECAP_SPK_MIN_CLEAN_RATIO`，默认值来自 ASR `DEFAULT_MIN_CLEAN_RATIO`。"),
    # ⑧ 压缩：§171 定界那条（明细在 STATUS_APP.md §171 ＋归档件）
    ("- 🔴 **§171 定界**",
     "- 🔴 **§171 定界**（全文在 §171 归档件）：**D1（GUI 布局被吞）= 零交付物受影响**"
     "（15 包 AST 0 中招）⇒ `_clone_nearest` 是**兄弟方法**。**D2（asr06b label 撞车）= "
     "已交付的 rc5 中招** ⇒ **rc5/rc6 = BUG**（label 重复、**NPU 档不在 GUI 下拉**）／"
     "**rc7 = OK**／其余 NA。"),
    # ⑧b 压缩：磁盘风险那条（事实不删，只压从句）
    ("- 🔴 **风险：C 盘 99 %、仅剩 22.7 G**",
     "- 🔴 **风险：C 盘 99 %、仅剩 22.7 G** ⇒ 打包需 10–15 G ⇒ **空间不足会直接失败**；"
     "**未删任何文件**。**§3.5 判据失效**（真值余弦 0.957–0.972 ⇒ 不可分）"
     "⇒ 未自行换判据；**§3.6 切段 RTF 已补做**（0.621 vs 0.627 ⇒ 噪声地板内）。"),
    # ⑧c 压缩：§12 里「§172 回填」那条的重复表述
    ("- 🔴 **回填口径（§172 定案，等复核）**：",
     "- 🔴 **回填口径（§172 定案，等复核）**：`value = ceil3(max(preset_p50, clone_p50))`，"
     "源 = 已落盘 `app326_app097_lang_out/tts.json`（复算不手抄）；两音色取大＋上取整 ⇒ "
     "守卫阈值**只可能不变或变松**；zh/en/ja/ko 不动；**倍率地板未改**。"),
    # ⑧e 压缩：§12 里「GUI 布局」那条（明细见 §171）
]

# ⑨ 新增一条（§174）—— 追加在 §173 那条**之后**（保时间序）
INSERT_AFTER = "- 🔴 **§173（04:07）**："
INSERT_NEW = (
    "- 🔴 **§174（06:32）**：无新纠偏（SHA 零改动，全程只读）；**修掉 2 个 App 侧真缺陷**："
    "**① self_ref 克隆漏「克隆模式」闸门**（§168 ⑤ 实测 `--tts-voice A` ⇒ **78/78 句** clone "
    "⇒ 与 v2.4 口径「preset voice never registers clone voices」冲突 ⇒ 补 GUI "
    "`_clone_enabled`／CLI `_want_clone` 闸门）＋ **② `assert_*.py` 可能随包泄漏**（§173 ⑥ 必读项 "
    "⇒ `pkg_exclude` 加 `APP_DEV_ONLY_ASSERT_RE`＋`assert_pkg_clean.py` 白名单例外）"
    "⇒ 判据 **8/8＋13/13**（反证 2/2 ＋ 非空自证）⇒ **已交付 16 包零影响**；git `37eeae5`。")

hits = 0
for prefix, new in REPL:
    idx = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    if len(idx) != 1:
        print("!! 前缀命中 %d 次（应为 1）：%s" % (len(idx), prefix[:40]))
        sys.exit(1)
    i = idx[0]
    old = lines[i]
    if len(new) >= len(old):
        print("!! 新行不比旧行短（%d >= %d）⇒ 拒绝" % (len(new), len(old)))
        sys.exit(1)
    lines[i] = new
    hits += 1

# ⑨ 插入 §174 新条目（在 §173 那条之后）
idx = [i for i, l in enumerate(lines) if l.startswith(INSERT_AFTER)]
if len(idx) != 1:
    print("!! 插入锚点命中 %d 次（应为 1）" % len(idx))
    sys.exit(1)
lines.insert(idx[0] + 1, INSERT_NEW)
hits += 1

out = "\n".join(lines)
after = len(out)
LIMIT = 9700
if after > LIMIT:
    print("!! 压完仍超预算：%d > %d ⇒ **不写**" % (after, LIMIT))
    sys.exit(1)


def count(t, pat):
    return len([l for l in t.split("\n") if l.startswith(pat)])


for pat, label in (("# ", "节标题"), ("- 🔴", "条目")):
    if count(out, pat) != count(s, pat) + (1 if pat == "- 🔴" else 0):
        print("!! %s 条数变了（%d ⇒ %d）⇒ **不写**"
              % (label, count(s, pat), count(out, pat)))
        sys.exit(1)

open(P, "w", encoding="utf-8", newline="\n").write(out)
print("[app434] MEMORY.md %d ⇒ %d 字符（≤ %d）；替换/插入 %d 行；节标题不变、条目 +1（§174）"
      % (before, after, LIMIT, hits))
