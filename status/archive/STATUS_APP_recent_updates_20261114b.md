# STATUS_APP 「最近更新」2 条较旧条目整块逐字归档（2026-11-14）

归档时间：2026-11-14 18:28:17
归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §203 出空间。
正文一字未删。

块 SHA256：e9bc7572fc542b16fbc1ac58d776d7cffab6b415a8a2e1ad055dde732e043ae0（1572 B）

---- 以下为原文，逐字 ----
> 🔴 2026-11-14 17:17:05 ｜ **执行 APP-108／APP-109**（last_ack 107→**109**）：**修掉 Special MVP 真缺陷**（`current_profile()` 从不返回 'specialmvp' ⇒ 旧配置覆盖出厂默认 **MT=NPU→GPU.0**）⇒ **出 sp2**（包内复验 **PASS**：三配置全解析出 GPU.0/NPU/CUDA）；**OPEN-1（0xC0000409）三臂对照已跑**（10 分钟 × 3 臂 rc 全 0，**含原组合**）⇒ 验收结论改写为「PASS（有 1 项未结：退出码异常）」，不写 13/13；**10 句丢弃 = 全部 late_drop**（阈值 6.0 s，非 8 s）＋§195 ③ 的「?」字段已补齐（CUDA／加载 25.4 s／预热 2.0 s）｜**未打包 zip**（用户不通知不打包）／未改 sp1／未动 B 机
> 🔴 2026-11-13 23:59:06 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-107）**：6 通道全查空（`CORRECTIONS_APP.md` 107 条/APP-107 未变、NOTICE 最新 11-05、agent-mail 仍 `not_bound` 查不了、conversation_search 0 命中、git 0/0、`MACHINE_LOCK` 无）｜🔴 **本轮唯一实质发现（交付通道层）：目标机的无人值守进入通道已失效** —— 口令当时只放在临时环境变量 `WB_SSH_PASS`（**未落盘未入库**）⇒ 本轮及后续会话都登不上；公钥路实测也未通（**已排除探法错误**：显式 `-i github_backup_ed25519 -o IdentitiesOnly=yes` 仍 Permission denied）⇒ §197⑤/§198② 的**两端 SHA256 对账任何无人值守轮次都无法闭环**，需用户给一次密码或装公钥｜未打包/未改客户包/未改产品代码/未跑推理/未调 MiniMax
