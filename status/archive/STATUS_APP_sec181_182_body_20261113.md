# STATUS_APP §181/§182 正文整块逐字归档（2026-11-13）

归档时间：2026-11-13 10:26:18
归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §192 出陠。
正文一字未删（标题行仍留在活文档）。

块 SHA256（正文块，含末尾换行）= 4e101ee84c2ca7e3361a1b431ae2cc26acc74b8df81e9472bb6d2092aaf52db4

---

> 🔴 **已做**（证据 `results/app/app482_app101_102_model_identity.json`）：EXT v0.4.8 @`817abcbe…` 用 `git archive` 暂存 `_ext_v048_stage`（167 文件／`ext/accel_usage.py` 在位／manifest `version=0.4.8`）；decoder bin SHA `0059531a…d6a3` 与 reviewer 一致、IR `inputs_embeds [1,1..512,1024]`、hidden 1024／28 层、encoder bin `0b7463d6…` 前缀一致；`device_config.py:69-74` MiniMVP `tts` `NPU`→`GPU.0`（`ast.parse` OK、GUI/CLI 同源）。
> 🔴 **未做**（需持 `MACHINE_LOCK` 长作业，**不虚报**）：`backends_stateful.py` 后端／`make_backend` 分派／`manifest_gen` 源目录／rc8 打包脚本、4 臂短冒烟、10 语种冒烟、GUI 截图、rc8 目录+zip 与包上验收 ⇒ **未打 rc8／v2.5、未通知用户、未调 MiniMax、未占设备**；`last_ack` 保持 `APP-100`（理由见头部），**等 reviewer 裁定**。
> 🔴 **已做**（证据 `app484…json` / `app486…json` / `app487…json` / `app488…json`）：stateful 后端照 B-kit `bk_run.py`（NPUW_LLM、每次 generate 新建 InferRequest＋`reset_state`、eos/pad 用导出 id、512 上界截最旧前缀且实测截断 0 次）；旧无 KV 基线只在 dev 树，包内旧目录/字面 0（打包闸门反例自测 2/2 能识破）；rc8 目录＋zip 落盘，验收 6/6、4 臂短冒烟 4/4、10 语种 30/30，`last_ack=APP-102`（APP-103 裁定）。
> 🔴 **rc8 后补**（APP-102 §4）：10 分钟片段 4 臂配对 WER/RTF ＋ 整链一臂、预设 A 对照组、交付配置表细项；计时 json 已带锁 `ended` 与 `timing_valid`（`app486/487/488`）。**做完即停，等 reviewer 复核**（B 机实测由 reviewer 安排）；v2.5 未打、未调 MiniMax。
