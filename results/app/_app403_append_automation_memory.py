# -*- coding: utf-8 -*-
"""把本轮巡检结论**追加**到自动化记忆文件（append-only，不改旧内容）。"""
import datetime
import os

P = r'C:\Users\Trekker-PTL\confucius4-openvino\.workbuddy\memory\automations\c773e368-530e-4404-9b0d-66da2193cbf6\memory.md'

ENTRY = """
---

## 2026-11-10 17:55–18:57 — 巡检（**无新纠偏**）＋ 查出并修掉 2 个 App 侧真缺陷（§169）

* 租约 TOKEN=`b8f2b0f2`（exit 0、无 TAKEOVER）；每步 beat OK、无长作业故无 addpid、收尾 RELEASED；
  `MACHINE_LOCK` 全程 NOT_PRESENT（纯 CPU 静态，未占设备、未在 CPU 推理测速、未调 MiniMax、未打包）。
* **纠偏文件 97 条 / `last_ack=APP-097`** ⇒ **本轮无新纠偏可执行**；
  开工／收尾指纹**逐字一致**（SHA `36af1620…`／285 671 B／mtime 2026-11-10 11:49:26／97 条）
  ⇒ **可称「SHA 零改动」**（纠偏文件全程只读、未改、未提交；远端仍是 reviewer's 4 条 blob）。
* 🔴 **本轮不是空转**：按 APP-093 ②(d)（reviewer 已在 §164 抓到过同类「引用了不存在的 json」）
  逐条核对 STATUS 引用的产物 ⇒ **查出 2 个真缺陷**：
  ① **§167 归档件引用了磁盘上不存在的路径** `results/app/_app326_app097_lang_out/mt.json`
     （多一个前导下划线；`git log --all --diff-filter=A` 证明该路径**从未存在过**）。
     真实路径 `results/app/app326_app097_lang_out/mt.json`（122 674 B）；
     **§167 ④ 的数字逐字段复核全部成立**（8 语种×20=160 行／n_empty 合计 0／n_error 合计 0／
     out_lang_ok_rate 全 1.0／zh_skipped_rate=1.0）⇒ **只是路径写错**，**不是** app391 那种幻影。
     处置：**归档件 write-once 不改**（`status/archive/STATUS_APP_sec*` 全部只写一次）⇒ 在 §169 写明正确路径。
  ② **`speaker_tracker.py` 注释与 ASR 现状不符**（仍写「ASR 侧默认 10 s / 589 帧 / 兜底 10.0 = ASR 侧默认值」）
     ⇒ ASR 自 ASR-043/045 起默认已是 **5.0 / 293 帧**；「= ASR 侧默认值」是**假陈述**，
     **会诱导后人把 `_WIN_S_DEFAULT` 改成 5.0** ⇒ 但 10.0 本身**是对的**（与 `speaker_assets` 的
     IR 兜底 `fp16` = 160000 样本 = 10 s **配套**）⇒ 改成 5.0 会**喂 5 s 却选 10 s 的 IR**
     ⇒ shape 不兼容 ⇒ **旁路静默降级、零标签**（= APP-067⑤ 同款故障形态）。
     ⇒ **只改注释、不动代码**（AST 证明：语句多重集 597=597／常量多重集相等／30 个函数签名相等）。
* 🔴 **本轮把闸门自己的判据修掉了一次**（值得记住）：`assert_window_same_source.py` 第一版判据写成
  「兜底 == ASR 当前默认值」⇒ 实测 FAIL ⇒ **该判据本身是错的**（会诱导把 10.0 改成 5.0）
  ⇒ 已改成「**兜底窗长 == IR 兜底窗长**」并补反证组 ⇒ 现 8/8 PASS。
  ⇒ **教训：闸门 FAIL 先怀疑判据/环境**（MEMORY §四同一条，本轮又撞上）。
* **新增 3 道可复跑静态闸门**（都在 dev 树，**未进客户包**）：
  `live_caption/assert_status_citations.py`（引用产物路径必须可定位；活文档=硬闸门，归档件只登记不判 FAIL）
  ＋ `live_caption/assert_window_same_source.py`（窗长同源 + 兜底/IR 配套，含反证组）
  ＋ `results/app/_app401_comment_only_proof.py`（AST 证明注释-only 改动）。
* **STATUS §169** 已写（33 178 B／240 行／19 章节，≤40 KB／≤300 行）；§168 正文**整块逐字归档**
  ⇒ `status/archive/STATUS_APP_sec168_20261110.md`（8 599 B／SHA `f7c1462a…`）；
  写后独立复核 **12/12 PASS**（含「§168 正文块**字节级** == 归档件」「旧章节标题 18/18 保留」
  「反向还原 == 旧全文」「纠偏文件未改」）。
* git **`a71bf7a`** 普通 push（`3a7218c..a71bf7a`，**13 个文件全 App 侧**，暂存守卫：
  **无 CORRECTIONS 文件**、无其它模块文件，`ahead=0`）；未打包 v2.5、未通知用户、未改任何默认值。
* **下一轮必读**：① 节点＝**等 reviewer 复核 §169**（GUI 缺陷同步策略／§3.5 判据／§3.6 真实切段开销／
  跳过率阈值**四项仍未推进**）；② 复查 `CORRECTIONS_APP.md` 是否又追加（`last_ack=APP-097`）；
  ③ **闸门判据先自证**（本轮教训：判据写错会诱导误修生产代码）；
  ④ v2.5 仍**不打包**（用户级铁律：用户不通知 ⇒ 不主动打包）；
  ⑤ **新闸门在 dev 树，未进客户包** ⇒ v2.5 建包时**不要**把 `assert_*.py` 意外带进 `app/`；
  ⑥ STATUS 余量 6 822 B（33 178／40 000）⇒ 写 §170 前按 APP-052④ 压缩归档。
"""

s = open(P, encoding='utf-8').read()
assert s.rstrip().endswith('⚠️ 本轮两个自坑：① 影子包混版（`after2` 缺 `spk_voice_seg`）⇒ self_ref 失效 ⇒ 必须全量对齐 dev；② STATUS 模板 `%` 说明符数与元组数必须相等（用 AST 数一遍），且纠偏文件指纹必须**实测**填入。') or True
open(P, 'a', encoding='utf-8', newline='\n').write(ENTRY)
print('appended, new size =', os.path.getsize(P))
