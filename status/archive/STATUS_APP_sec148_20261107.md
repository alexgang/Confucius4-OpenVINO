# 归档：STATUS_APP §148 正文（逐字保留，APP-052④）

> 归档时间：2026-11-07 17:14:32；块 SHA256 `41fc4e67eee63d789da263bd6e7be5e3e8f550a39ce1a94db3d0958362dea7de`；块字节数 8534；块行数 29。
> 原文自下一行起**一字未改**，用于反向还原与逐字命中核验。

## §148 无新纠偏（last_ack=APP-080）｜APP-080 ④⑥ 随包洁净度闸门覆盖一致性审计与构建期补丁端到端回归（2026-11-07 13:55:33）

- **步骤 1–2**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，只读／未改／未提交）开工 SHA `b3ae9ea9…f392b937d5`／224 562 B／mtime 2026-11-06 21:40:34／**80 条**（APP-001..080 连续无缺号，`max_id=80`，`continuous=true`）；`last_ack: APP-080` 对齐 ⇒ **无编号大于 last_ack 的新条目，步骤 3 无条可执行，无需写「本条已完成／本条需等复核」**。租约 `acquire app` ⇒ exit 0（TOKEN 9c1b825d，**无 TAKEOVER**）；`MACHINE_LOCK` 全程 `NOT_PRESENT`。
- **步骤 3 / APP-046② 不空转**（STATUS 头部「阻塞/待办」非空、本模块无进程在跑，且三条复核节点明文不得自行推进）：做**不占设备的纯 CPU 静态自证** ⇒ `results/app/_app326_v23_pkg_gate_audit.json` → `verdict=PASS`／`n_pass=41`／`n_fail=0`／`n_unknown=1`／`counterproof_identified=9/9`（9 条反证改的都是「被测的那个对象」：`TOKEN_RE`／`VOICE_RE`／排除模式列表／黑名单列表／**未打补丁的 dev 原文**，逐条见 JSON 的 `counterproof` 字段）。
- 🔴 **本轮新结论（历史各轮未验过的判据盲区，需 reviewer 复核）**：§143 落盘的两份 dev 资产 —— `live_caption/assert_pkg_clean.py`（**3458 B**／SHA `ba7690693849…`，建包后实际调用的随包闸门）与 `live_caption/v23_preset_only.py`（**17260 B**／SHA `362825e644d2…`，定义 `PKG_EXCLUDE_PATTERNS` **5** 条＋`BLACKLIST_PATTERNS` **5** 条）—— **覆盖范围不一致**：`facts.coverage_matrix` 用 `tempfile` 临时夹具（自动清理、非客户包、非 shared）实算 6 类应排除路径 ⇒ `assert_pkg_clean.scan()` 只检出前 **3/6**（APP-077 固定 token 与 APP-078 babelvox 示例音色），对 **3 类 APP-080 ④ 违规路径 `scan_detected=false`**：`APP-080 ④ 克隆音色`, `APP-080 ④ 克隆产物目录`, `APP-080 ④ 测试 wav`；而 `PKG_EXCLUDE_PATTERNS` 对 6/6 全部命中（`exclude_hits` 各 ≥1）。⇒ **随包闸门覆盖不全（NOT_COVERED 3/6）**，仅靠 `assert_pkg_clean.py` 无法拦住 APP-080 ④「不含任何克隆音色或测试 wav」。覆盖矩阵（原始字段 `facts.coverage_matrix`）：
| 类别 | 夹具路径 | `scan_detected` | `exclude_hits` |
|---|---|---|---|
| APP-077 固定 token | `ext/bridge_token.txt` | PASS | 1 |
| APP-078 示例音色 | `python/Lib/site-packages/babelvox/data/speakers/cindy.json` | PASS | 1 |
| APP-078 示例音色 | `python/Lib/site-packages/babelvox/data/speakers/steve.npy` | PASS | 1 |
| APP-080 ④ 克隆音色 | `app/voices/spk_clone_s1.wav` | **0 检出** | 1 |
| APP-080 ④ 克隆产物目录 | `app/v23_clone_r2/male_01_seg5.wav` | **0 检出** | 1 |
| APP-080 ④ 测试 wav | `app/audio/foo_test.wav` | **0 检出** | 1 |
  干净路径（`facts.clean_paths_not_flagged`）⇒ 两闸门均 0 命中，不误伤 `preset_A.wav`／babelvox 库代码／tokenizer 配置；`facts.blacklist_positive_hits` ⇒ 5 条黑名单正则全部被正例覆盖、干净串 0 命中。**处置：并入 APP-080 ⑤ 待办（扩展 `assert_pkg_clean.py` 或统一由 `PKG_EXCLUDE_PATTERNS` 驱动），是否需改闸门属 reviewer 裁定 ⇒ 记 `n_unknown=1`，本轮不自行改代码、不写「已修复／已交付」**。
- **构建期补丁端到端回归（内存中，零写盘）**：`facts.patches` ⇒ live_caption_app.py 11 锚点・LF・verify_source_ok=true／tts_service.py 3 锚点・CRLF・verify_source_ok=true／tts_worker.py 4 锚点・CRLF・verify_source_ok=true，`facts.applied_anchor_total=18` 且 18 个 id 无重复；补丁后 `ast.parse` 通过、`verify_source` 三份全 `ok=True`、**docstring 常量多重集补丁前后相等**（§143 `_app316` 首版插在 def 与 docstring 之间的教训已回归覆盖）、行尾还原（LF 文件仍 LF、CRLF 文件仍 CRLF）、`facts.dev_sources` 补丁前后磁盘 SHA/字节**全等** ⇒ dev 源文件与客户包一字未动。反证 `E7_unpatched_dev_*` 三份「未打补丁的 dev 原文」调同一 `verify_source` 全部返回 `ok=False` ⇒ 判据非恒真。
- **判据缺陷自纠（⚠️ 如实记录首跑）**：首跑 **40 PASS / 1 FAIL / 反证 9/9**，FAIL 项为 `sec147_packaging_chain_not_wired` —— 我把 `_app324` JSON 的 `facts.packaging_chain.refs_by_file`（**23 项「被扫描文件 → 引用数」映射，值全 0**）误当成「有引用的文件清单」而断言 `len()==0`；按「**FAIL 先怀疑判据／环境**」查证后改为 `sum(values)==0 and len==scanned`，复跑 **41 PASS / 0 FAIL**，判据口径错误非产品缺陷、未改任何产品代码。
- **历史结论实算复核（结果文件＋原始字段）**：`facts.historical_fields` ⇒ §147 `sec147_packaging_chain.scanned=23`／`total_refs=0` ⇒ `PKG_INCLUDE_FILES` **仍 NOT_WIRED**；§146 `sec146_pkg_v22_unique_anchors=14`／`sec146_direct_patch_applicable=false`（18 锚点中包内基底仅 14 个，须先升级基底再套补丁）；§147 `sec147_bridge_token_paths=['ext/bridge_token.txt']` ⇒ APP-077 固定 token 在 v2.2 包根**仍在**（只记清单、不写已修）；`sec147_seg_w5_xml_differs=true` ⇒ D5 仍 UNKNOWN、取哪份 xml 待 reviewer 裁定。`facts.independent_packaging_scan` ⇒ 独立实算 **23 个建包脚本／refs=0**，与 §145/§147 一致。
- ⛔ **停止点（明文）**：APP-075「需 Opus 复核」・APP-079「需 reviewer 复核」・APP-080 ⑤⑥「reviewer 复核通过后才通知用户」＋用户级「**不通知不打包**」⇒ 本轮**未自行推进 ⑤⑥**、**v2.3 不打包**；未打新版本目录与 zip／未改任何客户安装目录与 .lnk／未复制影子包资产／未建 `MACHINE_LOCK`（未占设备）／未在 CPU 跑推理测速／未调 MiniMax。**没落盘的一律不写「已交付」**。
- **写入纪律（APP-052④）**：`facts.status_before` ⇒ 写前 **33623 B／177 行**／SHA `3803d0749923…`；**首版 41 860 B 超 40 000 B 限额被写前自检拦下（STATUS 一个字节未落盘）** ⇒ 按 APP-052④ 把 §147 正文（22 行／7516 B／块 SHA256 `cd4ea569b3434e1e6327c1b553825ebecf462e80dc3571e3aae9804c2ef84957`）**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec147_20261107.md`，原位留 1 行速查；头部仅定点改 `更新时间`／`当前任务` 2 行，`last_ack` 保持 APP-080、`已压缩` 一字未动；末尾只追加本章节；写前自检「反向还原==旧全文・归档件逐字命中・章节不减・LF 未破・≤40 000 B / ≤300 行」＋临时文件 `os.replace` 原子替换＋写后磁盘逐字节复核 ⇒ `results/app/_app327_write_status_sec148.json`。
- **纠偏文件收尾复核（步骤 4）**：SHA `b3ae9ea9fb72282bbf619dd26b73de688f8c771911bd0b56e0faf8f392b937d5`／224562 B／2026-11-06 21:40:34／**80 条**（最大 APP-080，`continuous=true`）⇒ 与开工逐字一致，**reviewer 本轮未追加**；全程只读／未改／未提交，可称零改动。
- **产物清单（写 STATUS 时磁盘实测，共 4 个文件）**：
| 文件 | mtime | 字节数 | SHA256 |
|---|---|---|---|
| `results/app/_app326_v23_pkg_gate_audit.py` | 2026-11-07T13:55:11 | 21408 | `b1c63a47ba9ab25e572a5b82855e5d981c78eb8ee28661eac20298b0ee436ed5` |
| `results/app/_app326_v23_pkg_gate_audit.json` | 2026-11-07T13:55:14 | 12694 | `3edd80930ab4dd83b9e598f314fb1a35160c9f730379a19a9c57aff32a3f98c7` |
| `status/archive/STATUS_APP_sec147_20261107.md` | 2026-11-07T13:59:13 | 7824 | `dbbcaab205bd56a2fc631c66f5e291e2be0b9cdd6ad0c17da865a38d056641b6` |
| `results/app/_app327_write_status_sec148.py` | 2026-11-07T13:59:10 | 20388 | `12b4980ca36e2fc53c261505022deb3f5cda6a8d4074dc0ef7c46bdfd3b43e14` |
- **git**：逐文件 `git add`（禁 `-A`）⇒ main 普通 push、不 force；不提交 `CORRECTIONS_APP.md`，不吞其它模块。
- **下一轮必读**：① 等 reviewer 复核 §143–§148（尤其本轮「随包闸门覆盖缺口」是否要扩展 `assert_pkg_clean.py`）；② APP-080 ⑤ 待办已增至：接入 `PKG_INCLUDE_FILES` 到建包链路、把新包 3 份源文件升级到 dev 基底再套 18 锚点补丁、随包闸门补齐 3 类排除规则、D5 取哪份 xml 裁定；③ v2.3 打包只在用户明确通知＋⑤⑥ 验收＋reviewer 复核后做，且须新目录／新 zip／新 MANIFEST／重签 ACCEPTED；④ 「不主动打包」规则不变。
