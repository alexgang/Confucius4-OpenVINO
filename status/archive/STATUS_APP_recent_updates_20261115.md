# STATUS_APP 「最近更新」3 条较旧条目整块逐字归档（2026-11-15）

归档时间：2026-11-15 08:47:45
归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §207 出空间。
正文一字未删。

块 SHA256：b3ee13324dbc5e5eb2c5d6fb0043da37ef0bbea62bb65b1cb8afe3f12944b230（1939 B）

---- 以下为原文，逐字 ----
> 🔴 2026-11-14 20:52:02 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-109）**：6 通道全查空（`CORRECTIONS_APP.md` 109 条/APP-109 逐字未变、agent-mail 仍 `not_bound`、`conversation_search` 0 命中、`NOTICE` 最新 11-05、git 0/0、`MACHINE_LOCK` 无）｜🔴 **修掉 Special MVP 两个真缺陷：sp2 的 MANIFEST 指向 sp1（重定向是死代码）＋ 出包闸门对包内容 0 字节验证（验收后改包照样能出包）**｜**鉴别力矩阵 12/12 PASS**｜**客户包写入仅 sp2 的 MANIFEST 一个字段**｜**未打包／未改产品代码**
> 🔴 2026-11-14 19:38:17 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-109）**：6 通道全查空（`CORRECTIONS_APP.md` 109 条/APP-109 逐字未变、agent-mail 仍 `not_bound`、`conversation_search` 0 命中、`NOTICE` 最新 11-05、git 0/0、`MACHINE_LOCK` 无）｜🔴 **修掉交付闸门真缺陷：Special MVP 打 zip 的闸门可被架空**（脚本把 `ACCEPT` 写死成 sp1 ⇒ 拿 sp1 的验收结论放行 sp2；且 verdict 精确字符串比较使 sp2 自己的证据反被拒）｜**参数化＋闸门重写，鉴别力矩阵 6/6 PASS**｜**未打包／未改客户包／未改产品代码**
> 🔴 2026-11-14 18:28:17 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-109）**：6 通道全查空（`CORRECTIONS_APP.md` 109 条/APP-109 未变、agent-mail 仍 `not_bound`、`conversation_search` 0 命中、`NOTICE` 最新 11-02、git 0/0、`MACHINE_LOCK` 无）｜🔴 **修掉包矩阵闸门 `app512` 的覆盖漏洞**（`SpecialMVP` sp1/sp2 **从未进过闸门** ⇒ 枚举放宽 ⇒ 复跑 **21/21**，sp1/sp2 均 **PASS 11/0**）＋ **静默丢弃无 `tts_worker.py` 的包**的口子（改 `SKIP` 行＋`coverage` 字段）｜**「10 个带缺陷包」经全盘 AST 复核数字不变**（v1.5 判据不适用、v1.13/v2.0/v2.1 无分支②）｜**未打包／未改客户包／未改产品代码**
