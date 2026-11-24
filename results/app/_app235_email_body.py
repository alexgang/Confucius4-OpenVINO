#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-235 轮 · 生成 STATUS 邮件正文（**入库件与实发件必须逐字节相同**）。

## 🔴 为什么正文必须由脚本生成（§222／§224 两次实证）
- 「入库件」≠「实发件」曾导致 reviewer 拿到草稿；
- **base64 人工转写必错** ⇒ 正文**不手抄**；
⇒ 本脚本把正文**写到磁盘**（`live_caption/_app235_email_body.txt`），
发信时**从磁盘读同一份文件** ⇒ 入库件 == 实发件（逐字节）。

## 🔴 为什么正文要短（≤ 4 096 B）
§224 实证：**长邮件正文会被服务端截断**（11 KB 中间丢失）；
已知**安全**的先例＝§233 的 **4 044 B** ⇒ 本轮沿用同一阈值。
且正文里放**首/中/尾三个地标** ⇒ 发完在已发箱逐个检索命中 ⇒ 证明中间没丢。
详细正文一律落 companion（§235 全文字段在仓库里）。

## 🔴 反斜杠
正文含 Windows 路径 ⇒ 本脚本用 `chr(92)` 拼，**不用** `\\a`/`\\b` 之类
（Python 会把 `\a`/`\b` 解释成控制字符 ⇒ §235 轮已在 MODULES 实测踩到）。
"""
from __future__ import annotations

import io
import os

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
OUT = os.path.join(REPO, 'live_caption', '_app235_email_body.txt')
BS = chr(92)
LIMIT = 4096

# ── 三个地标（首/中/尾）──────────────────────────────────────────────
M_HEAD = '【地标-首】'
M_MID = '【地标-中】'
M_TAIL = '【地标-尾】'

BODY = """[C4][A][STATUS][APP] APP-235 — 接续上一会话（TAKEOVER）：六通道全空 ⇒ 无新 App 纠偏（last_ack 仍 APP-133）；独立复现 §234 的 3 处修法；修掉 2 处新真缺陷

""" + M_HEAD + """
一、纠偏复核：六通道全空 ⇒ 无新 App 纠偏 ⇒ last_ack 仍 APP-133（值不变）
  1) 局域网 CORRECTIONS_APP.md：130 条／max APP-133／SHA 2db65bf13f23a701…／440181 B／mtime 11-24 13:56:42（与 §232–§234 逐字一致 ⇒ 本轮无人追加）
  2) QQ 收件箱最新 App 封仍 = APP-133（已执行）；其后仅 H-028 [MT]（11-24 18:11），正文明写「不要改 App 代码和任何客户包」⇒ 不据此动 App 代码
  3) 垃圾箱 0／已删除 1（无关）／全库 APP-134+ 命中 0／根 CORRECTIONS.md max C-135／NOTICE ≤11-05
二、TAKEOVER：上一会话（token 14ce4ac0，last_beat 03:52:12＝114 min 前）死在收尾中途；它已把 §234 写进 STATUS＋companion，但「未提交／未推送／未发信／未写日志」四件事没做 ⇒ 本轮从断点继续并全部补齐。

""" + M_MID + """
三、独立复现 §234 的 3 处修法（不直接采信，全部重跑）：11/11 ＋ 17/17 ＋ 16/16 PASS（各含反证组）⇒ 成立。
四、本轮修掉 2 处新真缺陷
  ① 判据自身：_app234_verify_status.py 判据 9 把整串「更新时间: <ts>」换成「只有时间戳」⇒ 丢掉「更新时间: 」6 个字符 ⇒ 恒 FAIL（假 FAIL）。实测直接跑它 = 13/14 FAIL 1（len 18244 vs 18250）——它是上一会话死前最后写的脚本、没来得及跑。改正后还原串 18250 == 备份 18250 且逐字节相等 ⇒ STATUS 正文本身没缺陷。修法：修判据＋新增反证组 9b（中段挖 1 字符 ⇒ 必须 FAIL）⇒ 15/15 PASS
  ② 生产路径：sync_pkg_identity.py 无条件把 app170 闸门证据写到规范路径 ⇒ 在任何影子包上跑一次就覆盖「交付包的闸门记录」。实测：pkg 变成 %TEMP% 临时目录下的 v2.10（跑完即删 ⇒ 无法复算）、pass 19→20、真实包两条真实 advisory（I1b／D4）整条消失 ⇒ 审计链断。修法（改生产路径）：交付候选包才写规范文件；非交付包写临时文件并用后删除 ⇒ ①绝不覆盖 ②零仓库污染。收尾：规范证据已用真实交付包 v2.6 重刷（rc=0／pass=19／fail=0／两条 advisory 回到位／与 HEAD 逐字节相同）
五、独立复核 _app235_verify_evidence_scope.py 25/25 PASS：A 5（影子包：规范证据逐字节不变＋零新增文件＋闸门确实跑了）｜B 6（单元）｜C 3 反证组（注入旧行为 ⇒ 规范证据确实被改）｜D 4 非空洞（交付候选包确实会更新规范证据）｜E 5（收尾重刷＋真包 48 792 文件 0 变化＋4 个身份文件 SHA256 一致）

""" + M_TAIL + """
六、如实登记（未修／不擅自修）：真包 v2.6 两处缺陷仍在（README_zh 段 2 次／MANIFEST.version 仍 2.5）⇒ 按 APP-055 未原地改已签包 ⇒ 是否出 v2.7 待裁定（§233–§235 第三次登记）｜app231_pack_lock_events.jsonl 仍不存在且未入库（运行时产物）⇒ 不伪造空文件｜.staging 残留 25 GB ⇒ 未删，待授权｜v2.5 的 ACCEPTED.json 仍指向 v2.4｜仓库根 .gitattributes 根治跨模块 ⇒ 待裁定｜默认分离设备、n_speakers=0 口径 ⇒ 待裁定｜app234_app170_gate_evidence.json 的 pkg 指向已删除的临时目录 ⇒ 不可复算 ⇒ 仅作审计痕迹
七、纪律：未打包 zip（用户规则「不通知 ⇒ 不打包」）／未改任何客户包／未跑推理·计时（未取 MACHINE_LOCK）／未调 MiniMax／未连 B 机／未改 CORRECTIONS_APP.md（收尾四项指纹逐字一致，SHA 零改动）／只 add App 侧文件／普通 push 未 force。提交 1a4a754 已推 origin/main（0/0）。
  正文全文：status/app/STATUS_APP_sec235_detail_20261125.md（12270 B）

（本条需等 reviewer 复核）
"""


def main() -> int:
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(BODY)
    b = open(OUT, 'rb').read()
    print('written %s' % OUT)
    print('bytes=%d  chars=%d  limit=%d' % (len(b), len(BODY), LIMIT))
    ok = True
    for i, m in enumerate((M_HEAD, M_MID, M_TAIL), 1):
        pos = b.decode('utf-8').find(m)
        print('  地标%d 位置=%d %s' % (i, pos, m))
        if pos < 0:
            ok = False
    nctrl = sum(1 for c in b.decode('utf-8') if ord(c) < 32 and c not in '\n\r\t')
    print('  控制字符数=%d' % nctrl)
    if nctrl:
        ok = False
    if len(b) > LIMIT:
        print('  [FAIL] 正文 %d B > %d B ⇒ 存在截断风险（§224）' % (len(b), LIMIT))
        ok = False
    print('自检：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
