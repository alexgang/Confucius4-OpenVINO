#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-235 轮 · **追加**当日日志与 automation memory（**只追加，绝不覆盖**）。

🔴 为什么用脚本而不是 Write：`Write` 是**整文件覆盖** ⇒ 对累积型文件绝对不能用。
🔴 追加用 `io.open(..., 'a', encoding='utf-8', newline='\n')`。
🔴 反斜杠：正文里的路径含 `\\` ⇒ **不能用非 raw 的普通字符串**
   （`\a` 会被解释成 BEL 控制字符 ⇒ 本轮已在 MODULES 附录实测踩到）
   ⇒ 本脚本统一用 `chr(92)` 拼接。
"""
from __future__ import annotations

import io
import os

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
BS = chr(92)
TMPP = '%TEMP%' + BS + 'app234_id_klh3m45v' + BS + \
    'Confucius4_LiveCaption_v2.10'

DAILY = os.path.join(REPO, '.workbuddy', 'memory', '2026-11-25.md')
AUTOM = os.path.join(REPO, '.workbuddy', 'memory', 'automations',
                     'c773e368-530e-4404-9b0d-66da2193cbf6', 'memory.md')

DAILY_ENTRY = """
## 2026-11-25 05:45–05:5x · App 巡检轮 · **§235**（接续上一会话 TAKEOVER）—— 六通道全空 ⇒ 无新 App 纠偏（`last_ack` 仍 **APP-133**）；🟢 独立复现 §234 的 3 处修法；🟢 修掉 **2 处新真缺陷**（1 处判据自身、1 处**生产路径**）

- **租约**：`acquire app` ⇒ exit 0 / **TAKEOVER**（上一 token `14ce4ac0`，started 11-25 03:15:31、last_beat **03:52:12**＝**114 min 前** ⇒ 死会话；note=`confirming operator-order effect`；`live_pids=[]` `alive=False`）⇒ 本轮 token **`d2f7f45a`**，beats ×N ⇒ 收尾 `release`。
- 🔴 **上一会话遗留**：`## §234` **已写入** STATUS（30 634 B／87 行）＋ companion（14 311 B），但**未提交／未推送／未发信／未写日志** ⇒ 本轮**从断点继续**。
- **六通道全空**（`last_ack` **仍 APP-133**，**值不变**）：局域网 **130 条／max APP-133**／SHA `2db65bf13f23a701…`／**440 181 B**／mtime **11-24 13:56:42**（与 §232/§233/§234 逐字一致 ⇒ 本轮期间无人追加）；QQ 收件箱最新 App 封仍 = **APP-133**（已执行），其后仅 **H-028 [MT]**（11-24 18:11 GMT+8，正文明写「**不要改 App 代码和任何客户包**」⇒ 不据此动 App 代码）；spam **0**；trash 1（无关）；根 `CORCORRECTIONS.md` max **C-135**；`shared/NOTICE*` 仍 ≤11-05；全库 `APP-134+` 命中 0。
- 🟢 **独立复现** §234 的 3 处修法（**不直接采信**上一会话的结论）：`_app234_verify_patch.py` **11/11**、`_app234_verify_identity_tool.py` **17/17**、`_app234_verify_anchor_fix.py` **16/16** —— 全 PASS（各含反证组）。
- 🟢 **修掉 2 处新真缺陷**：
  - ① 🟡 **判据自身缺陷** ⇒ `_app234_verify_status.py` 判据 9 把 `更新时间: <ts>` 换成**只有时间戳** ⇒ 丢掉 `更新时间: ` 的 **6 个字符** ⇒ **恒 FAIL（假 FAIL）**（实测 13/14 FAIL 1）⇒ 修判据（保留前缀）＋ **新增反证组 9b** ⇒ **15/15 PASS**；修正后还原串与写前备份**逐字节相等**（18 250＝18 250）⇒ **STATUS 正文本身无缺陷**。
  - ② 🔴 **生产路径缺陷** ⇒ `live_caption/sync_pkg_identity.py` **无条件**把 app170 闸门证据写到**规范路径** ⇒ 在任何影子包上跑一次就**覆盖**「交付包的闸门记录」（实测 `pkg` 变成 `%TEMP%` + 临时目录 + v2.10 ＝ **跑完即删不可复算**、`pass` 19→20、真实包两条**真实 advisory** 整条消失 ⇒ **审计链断**）⇒ 改**生产路径**：**交付候选包**才写规范文件；**非交付包**写**临时文件**并用后删除 ⇒ ①绝不覆盖 ②**零仓库污染**；规范证据已用**真实交付包 v2.6** 重刷（rc=0／`pass=19`／`fail=0`／两条 advisory 回到位／**与 HEAD 逐字节相同**）。
- 🟢 **独立行为级复核 25/25 PASS**（`_app235_verify_evidence_scope.py`）：A 5（影子不改规范证据＋零新增文件＋闸门确实跑了）＋ B 6（`_is_delivery_pkg` 单元）＋ **C 3 反证组**（注入旧行为 ⇒ 规范证据**确实**被改 ⇒ 判据有鉴别力）＋ **D 4 非空洞检查**（交付候选包**确实**会更新规范证据 ⇒ A1 不是恒 PASS）＋ E 5（收尾还原＋真包隔离）。
- 🟢 **交付面只读**：真包 **48 792** 文件跑前跑后 **0 变化**；4 个身份文件 SHA256 一致；`ACCEPTED.json`（v2.6／`b2a4978`／n=33）未改；真包两处已知缺陷仍在（README 双标题、MANIFEST.version=2.5）⇒ 按 APP-055 **未原地改已签包** ⇒ **是否出 v2.7 待裁定**。
- 🟢 **STATUS §235**（⇒ `status/app/STATUS_APP_sec235_detail_20261125.md`，**12 270 B**）：**34 128 B／91 行**｜`last_ack` **未变**｜「更新时间」**Get-Date 实测值**（`2026-11-25 05:52:38`）｜「最近更新」**+1 条**（旧条下移未删）｜**只追加在文末** ⇒ 独立复核 **17/17 PASS**（含反证组 9b／13）。
- 🔴 **本轮新学的 4 个判据坑（已下沉 `MEMORY_MODULES.md` 附录·五十三）**：① **还原式复核丢掉定长前缀 ⇒ 固定字符差 ⇒ 假 FAIL**（差值＝前缀长度 ⇒ 直指被丢的前缀）；② **反证组里的判据必须「有鉴别力」**（去掉被检对象后仍成立 ⇒ 不能进反证组）；③ **闸门证据要分作用域**（影子/临时包不得覆盖交付包的规范证据）；④ 🔴 **heredoc 里的 `\\a` 会被 Python 解释成 BEL 控制字符** ⇒ 含反斜杠的正文**必须用 `chr(92)` 或 raw string**（本轮已在 MODULES 实测踩到并当场修掉）。
- **纪律**：🟢 **未打包 zip**（用户级「不通知 ⇒ 不打包」）｜🟢 未覆盖/未删除旧目录与 zip｜🟢 **未改任何客户包**｜🟢 未跑推理·计时（**未取 MACHINE_LOCK**）｜🟢 未调 MiniMax｜🟢 未连 B 机｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致 ⇒ SHA 零改动）｜🟢 只 add App 侧文件｜🟢 普通 push 未 force。
- **提交**：`1a4a754` **已推 `origin/main`**（`git rev-list --left-right --count origin/main...main` = **0 0**）。
- **下一轮**：`last_ack` 仍 **APP-133**；⏭ 等 reviewer 复核 **§234/§235**；🔴 **待裁定**：**是否出 v2.7**（带三处修法）／**是否删** `.staging`（25 GB）／`app231_pack_lock_events.jsonl` 下轮入库／**v2.5 重签 ACCEPTED**／仓库根 `.gitattributes` 根治／默认分离设备／`n_speakers=0` 口径。
"""

AUTOM_ENTRY = """
## 2026-11-25 05:45–05:5x · App 巡检轮 · **§235**（接续上一会话 TAKEOVER）—— 六通道全空 ⇒ 无新 App 纠偏（`last_ack` 仍 **APP-133**）；🟢 独立复现 §234 的 3 处修法；🟢 修掉 **2 处新真缺陷**（1 处判据自身、1 处**生产路径**）

- **租约**：`acquire app` ⇒ exit 0 / **TAKEOVER**（上一 token `14ce4ac0`，last_beat 11-25 03:52:12＝114 min 前 ⇒ 死会话；`live_pids=[]` `alive=False`）⇒ 本轮 token **`d2f7f45a`** ⇒ 收尾 `release`。
- 🔴 **上一会话遗留**：§234 已写入 STATUS，但**未提交/未推送/未发信/未写日志** ⇒ 本轮从断点继续并**全部补齐**。
- **六通道全空** ⇒ **`last_ack` 仍 APP-133**（值不变）：局域网 130 条／max APP-133／SHA `2db65bf1…`／440 181 B／mtime 11-24 13:56:42；QQ 收件箱最新 App 封仍 = APP-133，其后仅 **H-028 [MT]**（明确「不要改 App 代码」）；spam 0；trash 1（无关）；根 max C-135；NOTICE ≤11-05；`APP-134+` 命中 0。
- 🟢 **独立复现** §234 的 3 处修法：**11/11 ＋ 17/17 ＋ 16/16 全 PASS**（各含反证组）。
- 🟢 **修掉 2 处新真缺陷**：① 判据自身缺陷（还原式复核丢掉 `更新时间: ` 前缀 ⇒ 6 字符恒 FAIL ⇒ 假 FAIL）⇒ 修判据＋新增反证组 9b ⇒ **15/15**；② 🔴 **生产路径缺陷**（`sync_pkg_identity.py` 会用**影子包**结果**覆盖**交付包的 app170 闸门证据 ⇒ 审计链断）⇒ 改生产路径（交付候选包才写规范文件；非交付包写临时文件并用后删除）⇒ 规范证据已用**真实交付包 v2.6** 重刷（rc=0／pass=19／两条 advisory 回到位／**与 HEAD 逐字节相同**）。
- 🟢 **独立行为级复核 25/25 PASS**（含**反证组**与**非空洞**检查）。
- 🔴 **新学的 4 个判据坑**（已下沉 `MEMORY_MODULES.md` **附录·五十三**）：还原式丢定长前缀 ⇒ 固定字符差；反证组判据须「有鉴别力」；闸门证据要分作用域；heredoc 里的 `\\a` ⇒ BEL 控制字符（须 `chr(92)`）。
- **纪律**：未打包 zip｜未改任何客户包（真包 48 792 文件 0 变化）｜未跑推理·计时（未取 MACHINE_LOCK）｜未调 MiniMax｜未连 B 机｜未改 `CORRECTIONS_APP.md`（SHA 零改动）｜只 add App 侧文件｜普通 push。
- **提交**：`1a4a754` **已推 `origin/main`**（0 0）。
- **下一轮**：`last_ack` 仍 APP-133；⏭ 等 reviewer 复核 §234/§235；🔴 待裁定：是否出 v2.7／是否删 `.staging`（25 GB）／`app231_pack_lock_events.jsonl` 入库／v2.5 重签 ACCEPTED／仓库根 `.gitattributes`／默认分离设备／`n_speakers=0` 口径。
"""


def append(path, text):
    before = os.path.getsize(path)
    # 🔴 **幂等守卫**：本条已落盘 ⇒ 直接拒（防重复追加）
    head = open(path, encoding='utf-8').read()[-len(text) - 200:]
    if '§235' in head:
        print('%s：已含本轮 §235 条目 ⇒ **幂等守卫命中，拒绝重复追加**'
              % os.path.basename(path))
        return False
    with io.open(path, 'a', encoding='utf-8', newline='\n') as f:
        f.write(text)
    after = os.path.getsize(path)
    print('%s：%d B → %d B（+%d）' % (os.path.basename(path), before, after,
                                     after - before))
    return True


def main() -> int:
    append(DAILY, DAILY_ENTRY)
    append(AUTOM, AUTOM_ENTRY)
    # 🔴 控制字符自检：**只查本轮追加的片段**
    #    （automation memory 里**存在一段历史遗留**的 `\x08`
    #      —— 旧条目的 `shared\bgkeep\e2e8\` 里的 `\b` 被 Python 解释成退格
    #      ⇒ 该文件**只许追加、禁覆盖** ⇒ **不回头改历史**，
    #        已在 STATUS §235 如实登记）
    for path, entry in ((DAILY, DAILY_ENTRY), (AUTOM, AUTOM_ENTRY)):
        t = open(path, encoding='utf-8').read()
        assert t.rstrip('\n').endswith(entry.rstrip('\n')), \
            (path, '追加片段不在文末')
        bad = [repr(c) for c in entry if ord(c) < 32 and c not in '\n\t']
        assert not bad, (path, bad[:5])
        assert entry.count('## 2026-11-25 05:45') == 1, (path, '本轮条目重复')
        print('%s：追加片段控制字符自检 PASS；本轮条目恰好 1 条 PASS'
              % os.path.basename(path))
    print('两文件追加完成（或已幂等跳过）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
