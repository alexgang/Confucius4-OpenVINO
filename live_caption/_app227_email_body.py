#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app227_email_body.py —— §227 轮：**由脚本生成** STATUS 邮件正文（§222 教训）。

🔴 **为什么必须由脚本生成**：§222 抓到「入库的发信记录**不是实际发出的那版**」⇒
本脚本是**正文的唯一来源** ⇒ 发出去的正文与入库的 `live_caption/_app227_email_body.txt`
**逐字节相同**（发完再用 `sha256sum` 对账）。

🔴 **正文长度**：§224 抓到 **11 KB 正文中间被截断** ⇒ 本轮正文**控制在 ~2 KB 以内**
（表格类结论单独发短邮件的规矩），关键数字与证据全部落在正文中，**不写「见某某路径」**。

用法：python _app227_email_body.py   # 打印正文 + 写出 .txt
"""
from __future__ import annotations

import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_app227_email_body.txt')

BODY = """[C4][A][STATUS][APP] §227 巡检（无新 reviewer 纠偏）＋ 接续上一会话闭合其遗留的 3 处半交付（last_ack 仍 APP-128）

■ 0. 应回主题与编号
本邮件回复主题：「[C4][A][CORRECTION][APP] APP-128 补充：STATUS 正文被截断，请单独补发 e2e7 三臂表」
应回编号：APP-128（无新编号 ⇒ last_ack 不变；§227 是待命轮）

■ 1. 结论（一行）
六通道复核无新 App 纠偏 ⇒ last_ack 仍 APP-128；本轮是待命轮，但上一会话死在收尾，本轮用 TAKEOVER 接续并闭合其遗留的 3 处半交付。

■ 2. 六通道（实测）
局域网 status/app/CORRECTIONS_APP.md：125 条／max APP-127／SHA256 fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48／429 255 B／mtime 2026-11-23 16:55:40（与 §225/§226 开工指纹四项逐字一致 ⇒ 无 APP-128+）
QQ 收件箱（alexchen7694@agent.qq.com）：最新 App 封仍是 APP-128 补充（msg_fGIsiLHODyOPwNYqu7_98Pa_yjPt80xLFhbTGTT26hLfvA，2026-11-23T12:52:07Z，§225 已执行）；其后仅 NAS T-004 与 ASR-068 ⇒ 与 App 无关；全库检索 APP-129 命中 0
spam 0 封；trash 1 封无关旧邮件；根 status/CORRECTIONS.md 最大 C-135（唯一 APP- 字样是路径指路）；shared/NOTICE* 最新仍 2026-11-05 09:35；agent-mail not_bound

■ 3. TAKEOVER 交接
session_lease.py acquire app ⇒ TAKEOVER：上一租约 4dc753a6，00:20:07 起、最后心跳 00:45:18（276 分钟前 ⇒ 判定死会话），note = "step11: STATUS email sent msg_73akZokC... (2833B, 3 landmarks verified, no truncation); recording evidence"。它死在 step11 之后：代码/STATUS/邮件都已落盘并推送（58439ba，origin/main 0/0），但留下 3 处半交付。

■ 4. 遗留①：MEMORY.md 超限 710 字符（注入被截断）——已修
实测：文件自声明 ≤9 700 字符，实际 10 410 字符 / 18 909 B ⇒ 超限 710；本次会话开头即收到「MEMORY.md 超限被截断」告警。
修法（沿用项目既有约定）：压缩前全文逐字下沉 MEMORY_MODULES.md 新附录·四十九（append-only、write-once）＋ 逐条不删只压从句 ＋ 临时文件 os.replace。
写后独立复核 ALL PASS：9 699 字符 / 17 479 B / 68 行（行数与章节数不变）／每行 🔴🟢 判据标记数不减少／全部 APP-/TTS-/ASR-/MT-/C-/§ 编号存活／附录逐字含压缩前全文 10 410 字符且只出现 1 次／被压掉的反引号标识符仅 1 个（invalid character，纯错误提示串）且在 MODULES 有逐字原文。
标题压缩从句 2 处（§十二 去掉每轮都变的日期戳、§十二之补 去掉一个「的」）⇒ 无节被删。

■ 5. 遗留②：上一会话从未写 automation memory ＋当日日志——已补
automations/c773e368-.../memory.md 补写前 grep §226 = 0（最后一条是 §225）；2026-11-24.md 补写前只有 2 条 TTS 巡检条目、无 App 条目。
本轮 append-only 补齐（断言原文逐字仍在）：171 301 → 173 253 字符／2 282 → 3 588 字符。

■ 6. 遗留③：MEMORY.md 里 §226 的方法细节与 §八「§226 修法」重复——已压掉重复，全文仍在 MODULES 附录·四十九。

■ 7. 收尾复核
status/app/CORRECTIONS_APP.md 四项指纹逐字一致 ⇒ SHA 零改动（reviewer 独占写入，全程只读、未修改、未 add）。
STATUS_APP.md：36 764 B/107 行 → 38 826 B/111 行（≤40 000 B/≤300 行）；§227 标题 + 指针行 + companion status/app/STATUS_APP_sec227_detail_20261124.md（12 605 B）；「最近更新」最老的一条真条目整块逐字归档到 status/archive/STATUS_APP_recent_updates_20261124b.md（1 544 B）。写后独立复核 ALL PASS。

■ 8. 纪律
未打包／未改任何客户包既有文件／未跑推理·计时（未取 MACHINE_LOCK）／未调 MiniMax／未连 B 机／未改纠偏文件／未进 v2.6／只提交 App 侧文件（未 add CORRECTIONS_*.md，未吞其它模块改动）／普通 push，无 force push。

■ 9. 待你复核 / 裁定
① §227 的 MEMORY.md 压缩是否可接受（可核对：live_caption/_app227_verify_memory.py 输出 ALL PASS；压缩前全文在 MEMORY_MODULES.md 附录·四十九）
② §226 的复核仍挂着：三份 e2e7 底本在 core.autocrlf=false 的机器上 clone 后能否按公布 SHA256 逐字节复现（3/3）
③ 仓库根 .gitattributes 根治是否授权（全仓 --renormalize 影响 851 个历史文件的 blob ⇒ 跨模块，且会改写你已在复核的历史条目入库字节）—— 本轮未自行执行
④ 默认分离设备：实测 GPU.0 0.215 / CPU 0.458（p50 RTF）⇒ 建议 GPU.0
⑤ n_speakers=0 的口径：App 侧 SpeakerBridge 的 stats 是否收进 stats_full
⑥ v2.6 交接：e2e7 三臂表已单独补发（msg_52Ta35TCkxRJS1CDLmdVZbCF5yDGbx4gPdFrKHNlMH7bJw，正文 462 B，未截断）⇒ 前置材料已到位，但 APP-126 §7 与「v2.6 打包等 reviewer 交接」仍在 ⇒ 本轮未进 v2.6、未打包、未跑 10 分钟整链、未抽听，等你明确交接指令
⑦ 沿用：v2.5 重签 ACCEPTED（ACCEPTED 仍指 v2.4）／发客户必须确认发 v1.1.1.zip／目标机三件套仍被 A 机已离开 192.168.2.0/24 挡住

—— App 线程
"""


def main():
    assert '\r' not in BODY, '正文含 CR'
    data = BODY.encode('utf-8')
    with io.open(OUT, 'wb') as f:
        f.write(data)
    print('[ok] 正文已生成：%s（%d 字节 / %d 字符）'
          % (OUT, len(data), len(BODY)))
    print('--- 正文开始 ---')
    print(BODY)
    print('--- 正文结束 ---')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
