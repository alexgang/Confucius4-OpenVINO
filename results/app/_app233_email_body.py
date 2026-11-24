#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · 生成 STATUS 邮件正文（**入库件与实发件必须逐字节相同**）。

## 🔴 为什么正文必须由脚本生成（§222／§224 两次实证）
- 「入库件」≠「实发件」曾导致 reviewer 拿到草稿；
- **base64 人工转写必错** ⇒ 正文**不手抄**；
⇒ 本脚本把正文**写到磁盘**（`live_caption/_app233_email_body.txt`），
发信时**从磁盘读同一份文件** ⇒ 入库件 == 实发件（逐字节）。

## 🔴 为什么正文要短（≤ ~4 KB）
§224 实证：**长邮件正文会被服务端截断**（11 KB 中间丢失）⇒
表格类结论**单独发短邮件**，正文 ≤ ~2–4 KB；
且正文里放**首/中/尾三个地标** ⇒ 发完在已发箱逐个检索命中 ⇒ 证明中间没丢。
"""
from __future__ import annotations

import io
import os

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
OUT = os.path.join(REPO, 'live_caption', '_app233_email_body.txt')

# ── 三个地标（首/中/尾）──────────────────────────────────────────────
M_HEAD = '【地标-首】'
M_MID = '【地标-中】'
M_TAIL = '【地标-尾】'

BODY = """[C4][A][STATUS][APP] APP-233 — 待命轮（无新 App 纠偏，last_ack 仍 APP-133）＋ TAKEOVER 闭合上一会话遗留的 4 处真缺陷

""" + M_HEAD + """
一、纠偏复核：六通道全空 ⇒ 无新 App 纠偏 ⇒ last_ack 仍 APP-133（值不变）
  1) 局域网 status/app/CORRECTIONS_APP.md：130 条／max APP-133／SHA 2db65bf13f23a701…／440181 B／mtime 11-24 13:56:42（与上轮逐字一致）
  2) QQ 收件箱：最新 App 封仍 = APP-133（已执行）；其后仅 H-028 [MT]，正文明确「App 接入等本条验收后另发」⇒ 不据此动 App 代码
  3) 垃圾箱 0；4) 已删除 1（MiniMVP rc9 报告，无关）；5) 全库 APP-134+ 命中 0；6) 根 CORRECTIONS.md max C-135／NOTICE ≤11-05／agent-mail not_bound

二、TAKEOVER：上一会话（token b1933ada，last_beat 11-24 23:50:08，108 min 前）死在「核实事实」中途，未留下任何可交付物。
  本轮从会话 JSONL 重建其分析链取回「4 处真缺陷」清单，并逐条独立复核后才动手。

""" + M_MID + """
三、4 处真缺陷（逐条根因→修法→独立复核）
  ① STATUS_APP.md 只剩 196 B 余量（上限 40000 B）⇒ 下一轮写 §N 必超限
     修法：§211–§227 标题行＋指针行整块逐字归档（write-once）⇒ 39804→24998 B（余量 15002 B）
     复核：17/17 PASS（含反证组）
  ② v2.6 的 README_zh「## v2.6 改动说明」出现 2 次（第 1 个是空段）；README_en 多出空的「## What's new in v2.6」＋「## v2.6 changes」
     根因：sync_c172 插入时自己写一个标题，而人撰写的正文首行又是同一个标题 ⇒ 两个标题叠加
     修法：开发树 sync_c172 插入前剥离正文自带的同版本标题（窄口径：只剥首行、恰好二级标题、含本版本号；### 小节绝不剥；幂等）
     复核：16/16 PASS ＋ 影子包端到端 23/23 PASS（含真包隔离检查）
  ③ v2.6 的 app/MANIFEST.json 写着 version=2.5，且与 v2.5 的该文件逐字节相同（md5 239ea82a4b1a12f9ad2e8cf55f244097）
     根因：该字段只有 pack_v13 的 refresh_manifest() 会写，而它挂在打包阶段；完整版线（v2.x）从来不出 zip ⇒ 打包阶段永不执行
     附带：app170 的 I1b 提醒原写「zip 级断言兜底」，但完整版线没有 zip ⇒ 那个兜底不存在 ⇒ 提醒措辞已改为真实修法
     修法：开发树 sync_c172 新增 MANIFEST.version 同步（只改这一个字段，files/bytes 仍归打包口径；幂等）
     复核：19/19 PASS（含反证组）
  ④ 入库的 app170 证据与实包对不上（README_zh 记 6f8b933e…/55968 B、实包 0bb23e7c…/57986 B；D4 count 0 vs 实包 2）
     修法：重跑闸门刷新入库证据 ⇒ 与实包逐字节一致；两条提醒如实保留，不掩盖

四、如实登记（未修／不擅自修）
  · v2.6 包两处缺陷（②③）修法已落开发树，但按 APP-055 未原地改已签 ACCEPTED 的包 ⇒ 是否出 v2.7 待 reviewer/用户裁定
  · results/app/app231_pack_lock_events.jsonl 不存在且未入库（被 4 处当审计指针）：它是修好后的生产路径在运行时产出的文件，
    v2.6 那次构建跑在修复提交之前 ⇒ 尚未产出。不伪造空文件；§231「lock_lost 0 条」结论不受影响（其证据 app132_lock_events.jsonl 已入库）
  · Confucius4_LiveCaption_v2.6.staging 残留 25 GB ⇒ 删除属破坏性操作，未删，待授权

五、纪律：未打包 zip（用户规则「不通知 ⇒ 不打包」）／未改任何客户包（v2.6 四个文件跑前跑后 SHA256 一致）／未跑推理·计时（未取 MACHINE_LOCK）／未调 MiniMax／未连 B 机／未改 CORRECTIONS_APP.md（收尾四项指纹逐字一致，SHA 零改动）／只 add App 侧文件／普通 push 未 force。
  提交：3670d1a（代码修复）＋ 910e726（§233）已推 origin/main（0/0）。
  正文全文：status/app/STATUS_APP_sec233_detail_20261125.md（18723 B）

""" + M_TAIL + """
（本条需等 reviewer 复核）
"""


def main() -> int:
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(BODY)
    b = open(OUT, 'rb').read()
    print('written %s' % OUT)
    print('bytes=%d  chars=%d' % (len(b), len(BODY)))
    for i, m in enumerate((M_HEAD, M_MID, M_TAIL), 1):
        print('  地标%d 位置=%d %s' % (i, b.decode('utf-8').find(m), m))
    print('  控制字符数=%d' % sum(1 for c in b.decode('utf-8')
                              if ord(c) < 32 and c not in '\n\r\t'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
