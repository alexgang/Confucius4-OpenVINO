# STATUS_APP 「最近更新」较旧条目整块逐字归档（2026-11-13）

归档时间：2026-11-13 04:46:11
归档原因：活文档触顶 **40 000 B** 上限（APP-052④），为 §188 出陠。
正文一字未删。

---

> 🔴 2026-11-12 12:45:59 ｜ **APP-104 执行完（rc9）**｜rc9 目录 10,692 文件／5.517 GiB ＋ zip 5,927,246,232 B｜包上验收 5/5 PASS（`--check`/GUI/整链/EXT/用户选择）｜**修掉 2 个真缺陷**（GUI 绕过旧配置迁移；`--engine` 默认写死 gpu_int8）＋**补上 `.runtime_deps`**（websockets/psutil，桥接才起得来）｜三份 README 改由打包脚本按实际文件生成（grep 旧字面 = 0）｜MANIFEST 6 个模型 SHA 与 rc8 相同（模型未动）｜未打 v2.5、未调 MiniMax、未通知用户
> 🔴 2026-11-12 10:44:44 ｜ **APP-102 执行完（APP-103 裁定本会话做完）**｜MiniMVP **rc8** 目录（10 541 文件／5.515 GiB）＋ zip `~/shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc8_perftest.zip`（**5 924 663 034 B**／10:40）｜**包上验收 6/6 PASS**（`app488_app102_rc8_acceptance.json`）：无旧解码器目录／`app/` grep `mask2`=0／MANIFEST decoder `0059531a…d6a3`＋encoder `0b7463d6…` 与源一致／EXT 0.4.8 @`817abcb`／包内 python `--check` exit=0（21 个 OK 行）／包目录整链 exit=0、ASR RTF **0.544**、播完 **2** 句｜**4 臂短冒烟 4/4 PASS**（`app486_app102_rc8_smoke.json`）：stateful GPU.0 **0.397**／NPU **0.538**（`EXECUTION_DEVICES` encoder+decoder 均 NPU）／新默认整链 **0.573**／GUI 截图 42 549 B 非空白、ASR 两档 stateful、克隆置灰、10 语种｜**10 语种 MT 30/30 ＋ TTS 30/30**（30 个 wav 落盘、撞上限 0 次、`_patch_app_langs` 新增键 **0**，`app487_app102_10lang_smoke.json`）｜**停下等 reviewer 复核**；未打 v2.5、未调 MiniMax、未通知用户
> 🔴 2026-11-12 09:46:41 ｜ **接单 APP-101 / APP-102**（纠偏 102 条／SHA `f5346cbd…`／325 733 B／mtime 08:59:56）｜静态前置落盘：EXT v0.4.8 @`817abcb` 暂存、stateful 模型身份核对、MiniMVP TTS 默认改 GPU.0｜**stateful 后端／4 臂冒烟／10 语种冒烟／rc8 未做**（需持锁长作业）⇒ **未 ack、未打 rc8**，详见 §181
> 🔴 2026-11-11 12:53:38 ｜ **执行 APP-099 完成**（第 4 节 8 项，明细见 §175 归档件）｜rc7 六臂 6/6 ＋ GPU 同占 1/2 有效（判据修正后 PARTIAL）＋ dev 修正 33/33 ＋ MANIFEST 逐项 84/84｜**未打 rc8 / v2.5，停下等 reviewer 复核**
> 🔴 2026-11-11 10:19:33 ｜ **开始执行 APP-099**（reviewer 09:20 追加，纠偏文件 **99 条** / SHA `F01C5C88…` / 307 394 B / mtime 09:28:13）｜第 0 节 **5 项用户决定** ＋ 第 4 节 **8 项任务** ｜**修在 dev 树、暂不打 rc8、不打 v2.5、不通知用户、做完停等复核**｜🔴 **设备作业排队**：`MACHINE_LOCK` 09:38:49 空文件（无 PID 可解析 ⇒ fail-closed 视为存活）＋ ASR 租约活跃（token `9bda917a`，beat 10:11）⇒ 第 1/2 项须等锁，不抢｜本条**需等 reviewer 复核**
