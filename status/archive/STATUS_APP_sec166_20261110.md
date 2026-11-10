## §166 执行 APP-097（last_ack=APP-097）｜目标语言扩到 **10 种**（静态部分完成）｜**逐语种设备验收未跑 ⇒ 需等 reviewer 复核**

### ① 已完成（静态 + 单元）
* `tts_engine.LANG_MAP`：**+6 种**（de/german/deutsch、fr/french/français、es/spanish/español、pt/portuguese/português/pt-br/pt-pt、it/italian/italiano、ru/russian/русский）。
* `tts_engine.SUPPORTED_LANGS`：**4 → 10 种**；注释改成**真实来源**并照录 `config.json` 的 `codec_language_id` 十个 id（chinese 2055 / english 2050 / german 2053 / italian 2070 / portuguese 2071 / spanish 2054 / japanese 2058 / korean 2064 / french 2061 / russian 2069）⇒ **旧注释「来源是 config.json」确是错的**（那张 4 种表是早期手写）。
* `tts_engine._SEC_PER_CHAR`：6 种新语言**先用 en 的 0.07 当初值**（待实测校准；初值偏小 ⇒ 失控守卫阈值偏低 ⇒ 已在代码里注明）。
* 🔴 **`_lang_key` 的失效前提已修**（reviewer 第 1.2 条）：扩表后「`LANG_MAP` 的值里只有 4 种 ⇒ 必然命中」**不成立** ⇒ 旧写法会拿**别名**（`'german'`/`'deutsch'`）当 `_SEC_PER_CHAR` 的键 ⇒ 静默落 en 的 0.07 ⇒ 改为**规范小写代号优先**（`_CANON`）。
* `translator._LANG_NAME`：+6 种；`translator.TARGETS` / `TARGET_LABELS`：+6 种（本地语言显示名 Deutsch / Français / Español / Português / Italiano / Русский）。
* 🔴 **GUI 与 CLI 自动跟随**：App 侧下拉/choices 直接读 `translator.TARGETS`（`live_caption_app.py:2803-2808`、`8225`）⇒ **扩表即生效**，**默认值未改**。
* 🔴 **未知语言显式拒绝**：`map_language(lang, strict=True)` 抛 `ValueError`（默认仍兜底 English，避免破坏既有调用方）。
* 🔴 **源语言判定的坑已处理**（reviewer 第 1.4 条）：
  * `translator.detect_lang` **新增西里尔 ⇒ `'ru'`**；`tts_engine._script_counts` 增 `cyr` 计数；`guess_language_by_script` 增 ru 分支。
  * **拉丁字母语言之间不再凭脚本跳过翻译**：新增 `_SKIP_EQ_SAFE = {zh, ja, ko, ru}` ⇒ `'en'`（拉丁兜底）**不在**跳过集合 ⇒ 源法语→目标英语**不会**被误判成「已经是英文」而跳过；**ASR 给了语种标签就用标签**（`translate(..., src_hint=...)` 优先级最高）。
* **只对中文目标生效的逻辑**（`ZH_BASE_SPEED` 1.10× 地板 / 中文断句 / 标点）**未动** ⇒ 仍只对 zh 生效；新语言走 en 的口径。
* **克隆 / 说话人切段 / 追赶跳段**与语言无关 ⇒ **未动**。

### ② 静态验收（自检全过）
* 10 种语言码经 `map_language` / `_LANG_NAME` / `is_supported` 的结果**逐个断言**；`map_language` ↔ `_lang_key` **往返一致**（`_lang_key(c) == c`）。
* 9 个别名（german/deutsch/français/español/português/pt-BR/italiano/русский/jp）**逐个断言**映射到预期全称。
* 未知语言 `'nl'`：默认 ⇒ `'English'`；`strict=True` ⇒ **显式抛错**。
* `detect_lang`：ru/zh/ja/ko 各自正确；fr/de ⇒ 落 `'en'`（拉丁兜底）⇒ **不进跳过集合**。
* 🔴 **grep 证据**：开发树里**再没有**只列 4 种语言的硬编码表（`_LANG_NAME` / `LANG_MAP` / `SUPPORTED_LANGS` / `TARGETS` / `TARGET_LABELS` 均已扩）；剩余的「zh/en/ja/ko」字样只在**注释**里（已改成反映 10 种的新描述）与**同步脚本**的历史说明里（`sync_s71_*` / `sync_s73_*`，非运行期代码）。

### ③ 未做 / 停下等 reviewer
* 🔴 **APP-097 §2 的逐语种设备验收全部未跑**：§2-2（MT 6 语种 × 15 句）、§2-3（TTS 6 语种 × 15 句 × 预设/克隆音色）、§2-4（时长口径校准）、§2-5（zh 回归 before/after + ja/ko 冒烟）、§2-6（模型身份 MANIFEST 一致性）⇒ 需 **MACHINE_LOCK 长作业**（计时跑）⇒ **本条需等 reviewer 复核**。
* **未打包、未通知用户**（APP-097 明文）。
* ⚠️ **EXT 内嵌版本**：reviewer 11-10 通知以 **v0.3.7 @c414294** 为准（取代 APP-094 的 ab9a767）⇒ 但 **v2.5 本轮未打包**（APP-094 明文「复核通过前不打 v2.5」）⇒ v2.5 的 EXT 版本**待 reviewer 复核后打包时**才落地。
* ⚠️ **§165 与 §164 的旧结论**：本轮**未改**（§164/§163 已整块归档到 `status/archive/STATUS_APP_sec164_20261110.md` / `..._sec163_20261110.md`）。
