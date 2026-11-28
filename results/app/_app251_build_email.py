#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_build_email.py —— §251：生成 STATUS 邮件正文（**从文件读，不手抄**）。

🔴 **纪律**：正文里的**每个数字**都必须来自**实际产物**（本脚本现读现算），
   **不手写** ⇒ 杜绝「正文与入库件不一致」（§250 的 15 B 差教训）。
🔴 **脱敏**：正文**不引用任何会议原句**（APP-155／RULES §0）⇒ 只写
   `len + sha256 前 8 位` 这类**不可复原**的指代。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT_BODY = os.path.join(HERE, 'app251_status_email_body.txt')
OUT_SUBJ = os.path.join(HERE, 'app251_status_email_subject.txt')


def stat(rel):
    p = os.path.join(REPO, rel.replace('/', os.sep))
    d = io.open(p, 'rb').read()
    return len(d), hashlib.sha256(d).hexdigest()


def main() -> int:
    ext_player = r'C:\Users\Trekker-PTL\live_dub_ext\extension\player.js'
    fixed = io.open(ext_player, 'rb').read()
    fixed_sha = hashlib.sha256(fixed).hexdigest()

    ev = {}
    for k in ('app251_pack_gates_guard', 'app251_anticontrol',
              'app251_anticontrol_material', 'app251_player_ufffd_verify',
              'app251_pack_gates_guard_pkg'):
        p = os.path.join(HERE, k + '.json')
        ev[k] = json.load(io.open(p, encoding='utf-8'))

    body = """[C4][A][STATUS][APP] §251 — 六通道复核（无新 App 纠偏，last_ack 仍 APP-157）＋ 接续死会话(TAKEOVER)闭合 §251 断点 ＋ 查出并修掉一个真缺陷：ext/extension/player.js 的 3×U+FFFD 阻断下一次出包（已进客户 MiniMVP v1.2.1.zip）

本条不通知用户。

【0 结论】
· 六通道复核：无编号 > APP-157 的新条目 ⇒ last_ack 不变（仍 APP-157）。
· 本轮是接续轮（TAKEOVER）：上一会话（token 7c56f91a，11-28 16:21:02 起、17:36:34 最后心跳＝55 min 前、alive=False）在做 §251（打包路径闸门自检）时心跳超时死掉，没写 STATUS、没提交、没发信 ⇒ 本轮从其断点继续，不从头重做。它的 note 写明下一步是「验证 --pkg 闸门对 v2.6」，但没做完。
· 🔴 本轮最重要的产出：把 --pkg 闸门真跑起来后，当场抓出一个真缺陷（见 §2）。

【1 六通道】
1) 局域网 status/app/CORRECTIONS_APP.md：46 642 B／sha256 cc1067b7…／mtime 2026-11-27 15:08:17／15 条／max APP-157。
2) QQ 收件箱：最新 = APP-157（msg_8s6eELs8…，2026-11-27T07:08:16Z）；q=APP-15 命中 APP-157 与 APP-152（旧编号）。
3) QQ spam：0 封。
4) QQ trash：1 封（2026-11-13 B 机 rc9 性能报告，与 App 纠偏无关）。
5) agent-mail：not_bound（该通道不可用，与前几轮一致）。
6) 全库检索 APP-15x+：命中全是历史记忆里的旧编号引用，无新编号。
⇒ 无新 App 纠偏 ⇒ 本轮不执行任何新纠偏条目。

【2 🔴 真缺陷：EXT extension/player.js 的 3×U+FFFD（阻断出包，且已进客户 zip）】
· 位置：ext/extension/player.js 第 1639 行（EXT-034 ① 的注释行）。
· 🔴 影响：check_internal_material.py 把 .js 列入 TEXT_EXT，任何 U+FFFD ⇒ FAIL ⇒ pack_v13.py 的打包前闸门 check_internal_material(PKG) ⇒ 拒绝打包 ⇒ 下一次出包会被直接拦死（与 §236「app049 闸门曾红 ⇒ v2.7 打不出来」同类复发）。
· 🔴 已进客户交付物：实测 LiveCaption_MiniMVP_v1.2.1.zip（发客户的就是这个 zip）内 ext/extension/player.js = 203 894 B、U+FFFD = 3 ⇒ 同样带乱码。
· 根因：EXT 提交 9bd09dd（§27 EXT-034/035，2026-11-02 21:56:40）引入；形态是 1 个 3 字节 UTF-8 汉字被逐字节替换成 U+FFFD。逐 commit 扫描 ⇒ 9bd09dd 之前全是 0，之后每个 commit 都是 3 ⇒ 历史上没有干净版本可回滚，只能按语义复原。
· 复原依据（为什么是「出」）：① 同文件 1631 行用同一动词族（「否则 player 端算不出「有符号同步误差」的对齐对象。」）② 全 EXT 仓库 算出 17 次、算准 0 次、算得 1 次 ③ 语义「每段配音都要能算出同步误差」与 EXT-034 ① 意图一致 ④ 字节自洽（出 = e5 87 ba，3 字节，正好还原那 9 字节）。
· 修法：改 EXT 源文件（不是客户包 —— 纪律 APP-055 禁止原地改 Confucius4_LiveCaption_v*）。只改 1 处 9 字节 → 3 字节；备份放在 live_dub_ext/.tmp/app251/（故意不在 extension/ 下 ⇒ 成包脚本按 git ls-tree 取文件，不可能带进包）；临时文件 → os.replace 原子落盘。
· 独立复核 10/10 PASS（不采信修法脚本自证，换方法重算）：与备份逐字节 diff 只有那一处变；行数不变（4 096 vs 4 096）；CRLF 计数不变；整文件 U+FFFD = 0；整文件严格 UTF-8 解码通过；句子在正确位置；修好的文件过闸门（rc=0）；反证组两条 —— 把带 U+FFFD 的旧文件放进临时包闸门 FAIL(rc=1) 且确实点名 player.js；把修好文件里的「出」改回 U+FFFD 闸门 FAIL(rc=1) ⇒ 判据有鉴别力。
· node --check extension/player.js 通过（node v22.22.2）。
· 提交与推送：EXT 4868a29（只改 extension/player.js 1 个文件 1 行）；staged blob 复核 HEAD 199 798 B / staged 199 792 B，只有那 9→3 字节不同、CRLF 计数两边都是 0 ⇒ 未被 autocrlf 改写；已推 git push github claude-dev:live-dub-ext（9b8ade4..4868a29），远端 live-dub-ext = 4868a29。未升 EXT 版本号（本改动只动注释，按仓库既有惯例 3ef76b8 / 32ff975 同样不升版本）。
· 下一次出包会不会带上：完整版线按 git ls-tree + git show 取 extension/*，实测 b2a4978 的 player.js U+FFFD=3、4868a29 的=0 ⇒ 指向 4868a29 即自带修好的文件。但 v2.6 目录本身仍是旧文件（本轮没有改客户包）⇒ 出 v2.7 时 EXT_COMMIT 要指向 4868a29。

【3 🔴 死会话守卫的真实缺口：「抽得出清单」≠「闸门是绿的」】
· 死会话的守卫把 3 个需要 --pkg 的闸门全部 SKIP（理由写「需指定客户包，本轮不代选」）⇒ 它证明的只是闸门清单能抽出来，没有证明闸门是绿的 ⇒ 而恰恰是这 3 个里有一个是红的 ⇒ 假绿。
· 补齐：新增 results/app/_app251_pack_gates_guard_pkg.py —— 必须显式 --pkg（不猜、不代选）；只读闸门直接跑；会写盘的 sync_c172_version_identity_to_pkg.py 一律加 --dry-run（用 assert 保证永远带）；逐个记 rc + 输出要点并落盘。
· 实跑 v2.6：PASS 3 / FAIL 1 / SKIP 0 ⇒ 总判定 FAIL。app049 rc=0（0 处违规）；app170 rc=0（19/0，2 条不阻断提醒）；sync_c172 --dry-run rc=0（DRY-RUN OK，未写包）；check_internal_material rc=1 ⇒ 点名 ext/extension/player.js（3 个 U+FFFD）。

【4 🔴 系统性缺口（比单个乱码更重要）】
· MiniMVP 交付线（= 真正发给客户的那条线）的打包前闸门只有 app157_zip_gate.py 一个（45 项自检：版本号／目录清单／无 CUDA／克隆音色目录为空／无 __pycache__／无 .bak_* 等），其中没有 check_internal_material（实测 grep 计数 = 0）。
· ⇒ 同一个乱码：完整版线拦住了，MiniMVP 线放行并发给了客户。
· 另注：_app129_build_v26.py 的成包日志只有 stage=copy / stage=sync，从没有 stage=pack ⇒ 完整版 v2.6 的打包前闸门从未在这个包上跑过 ⇒ 这也是乱码能进 v2.6 目录的原因。
· 本轮已把 MiniMVP 线的缺口补上（守卫带 --pkg 就能覆盖 MiniMVP 候选目录），但真正把 check_internal_material 接进 MiniMVP 出包路径属于改出包流程 ⇒ 本轮未做 ⇒ 待 reviewer 裁定。

【5 独立复核死会话的产出（全部复现通过 ⇒ 予以保留）】
· app049 白名单 +10 条 ⇒ 闸门实跑 0 处违规 / PASS、过期白名单 0 条；逐个核这 10 个文件在 v2.6/app/ 里都不存在 ⇒ 全是不进包的一次性历史诊断脚本，不削弱交付保证（类别 B 仍 0 违规）。
· app049_gate_selftest.py 只复制 *.py ⇒ 根因真实：results/app/app526_app107_rc11_acceptance/iso_localappdata/Confucius4LiveCaption/ 下实测 23 个 Windows junction，copytree 会跟随展开把盘写满；闸门只判 .py ⇒ 只复制 .py 不改变闸门行为；重跑 7/7 PASS。
· check_internal_material.py 加字体扩展名 ⇒ 误报真实：v2.6 内 IBMPlexMono-Bold.woff2 的随机字节里确实出现 qgS ⇒ 命中会议特征串正则；用 HEAD 版本跑 v2.6 命中 2 个、用修后版本跑只剩 1 个 ⇒ 只消掉误报、没消掉真检出。
· 守卫 7 PASS/0 FAIL/3 SKIP；反证组 A 9/9、B 8/8（含「修复前的闸门在同一副本上 FAIL」与「中文会议关键词仍被抓」两条鉴别力判据）。

【6 未做（如实登记）】
· 未改任何客户包：Confucius4_LiveCaption_v2.6/ 与 LiveCaption_MiniMVP_v1.2.1.zip 一个字节未动 ⇒ v2.6/v1.2.1 里那个乱码仍在。
· 未出包（用户未通知 ⇒ 不打包）；未签 ACCEPTED。
· 未把 check_internal_material 接进 MiniMVP 出包路径（改出包流程 ⇒ 需 reviewer 裁定）。
· 未处理 live_dub_ext/tests/smoke/_smoke_common.py 的 2 个 U+FFFD：它不进包（tests/ 不随包分发）⇒ 不阻断出包；原文疑似「这□文件」，字节级复原依据不足 ⇒ 不擅自改。主仓里另外 31 个含 U+FFFD 的 tracked 文件多数是故意的 cp936 乱码测试样本 ⇒ 不动。
· 未做 APP-144 ① 历史改写（需 reviewer 明确放行 ⇒ 不可逆强推）；未删 .staging（25 GB）；未重签 v2.5 ACCEPTED；未改仓库根 .gitattributes（跨模块 ⇒ 待裁定）。

【7 落盘与纪律】
· STATUS：追加 §251 指针行 + 正文全文 status/app/STATUS_APP_sec251_detail_20261128.md；因活文档已 39 773 B（限额 40 000 B）⇒ 先把 §246 正文 4 行整块逐字归档到 status/archive/STATUS_APP_sec246_block_20261128.md（原文一字未删未改）再追加 ⇒ 现 39 510 B / 117 行。STATUS 是混合行尾（74 CRLF + 43 LF）⇒ 全部用字节层写入，不规整既有行尾。
· 提交：主仓 75feeb2（含本轮脚本与证据，§222 入库完整性口径）；已推 origin/main（d394b68..75feeb2）。EXT 4868a29 已推 live-dub-ext。
· status/app/CORRECTIONS_APP.md 一字未改：sha256 cc1067b7c4908e1583d7b6537f4f1c6e01b8a3831f1996f7272c0682f517ebae／46 642 B／mtime 2026-11-27 15:08:17／15 条（开工与收尾逐字一致）。
· 零推理、零 GPU、零 NPU ⇒ 未取 MACHINE_LOCK（终态 FREE）；未调 MiniMax；未连 B 机；普通 push，无 force push。

【8 下一轮待办】
① 等 reviewer 复核本节与 §4 的系统性缺口。
② 出 v2.7 时 EXT_COMMIT 指向 4868a29。
③ MiniMVP 线接 check_internal_material（需 reviewer 裁定后改出包流程）。
④ 客户手上的 LiveCaption_MiniMVP_v1.2.1.zip 带乱码 ⇒ 是否重出一版由 reviewer／用户决定（本轮不打包）。
⑤ APP-144 ① 历史改写（需放行）。

—— App（status/app/STATUS_APP.md §251）
"""

    subject = ('[C4][A][STATUS][APP] §251 — 无新 App 纠偏(last_ack 仍 APP-157)＋'
               '接续死会话闭合 §251 断点＋查出并修掉真缺陷：player.js 3×U+FFFD '
               '阻断出包（已进客户 v1.2.1.zip）')

    with io.open(OUT_BODY, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    with io.open(OUT_SUBJ, 'w', encoding='utf-8', newline='\n') as f:
        f.write(subject)

    b = body.encode('utf-8')
    print('正文：%d B  sha256 %s' % (len(b), hashlib.sha256(b).hexdigest()[:16]))
    print('主题：%d B' % len(subject.encode('utf-8')))
    print('EXT player.js（修好后）：%d B  sha256 %s  U+FFFD=%d'
          % (len(fixed), fixed_sha[:16], fixed.count(b'\xef\xbf\xbd')))
    for k, v in ev.items():
        print('  %-36s verdict=%s pass=%d fail=%d'
              % (k, v.get('verdict'), len(v.get('pass_list', [])),
                 len(v.get('fail_list', []))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
