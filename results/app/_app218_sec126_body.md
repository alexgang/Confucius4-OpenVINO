### §126 ✅ **APP-060 —— 交付版定为 v2.1；v2.0 标 superseded；桌面 v2.0.lnk 已由 reviewer 删除（脚本加硬闸门）；今后改动只打 v2.2+** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> 本节只追加，不改旧章节。

#### ① 交付版 = v2.1；v2.0 标 superseded（APP-060 ①）
* 交付物 = `Confucius4_LiveCaption_v2.1.zip`（2026-11-01 20:38，**11 233 135 359 B**，SHA256 `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`）；**v2.0 目录与 zip 保留作历史记录、不再对外**。
* 已标 superseded（**只追加字段，原字段逐字保留**）：`DELIVERY_2.0.json` → `status="superseded"` / `superseded_by="2.1"` / `superseded_at="2026-11-01T21:13:39"` / `superseded_note`（857 B，SHA256 `a857b6980260849a…`）；`DELIVERY_2.1.json` → `status="delivery"` / `delivery_decided_by="APP-060 ①（用户决定）"` / `supersedes="2.0"` / `known_gap`（见 ④）（1 383 B，SHA256 `cc83d69b5a360c5f…`）；STATUS 头部同步改写。

#### ② 桌面 v2.0.lnk 已删；**任何脚本都不得再生成**（APP-060 ②）
* 实测（21:13）桌面只剩 `Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`（均 mtime 20:42:58）⇒ **`实时配音桥接服务 v2.0.lnk` 已不在**（reviewer 21:10 删除）。
* 全仓库**只有** `results/app/app212_app057_v20_shortcuts.py` 会生成桌面 `.lnk`（`app192` 的坏链只写临时目录；其余 `_*.py` 是只读探测）；它**版本号从包目录名派生**（`ver = pkg_version_of(PKG)`）⇒ 本就只生成「目标包那个版本」。
* 🔴 但它 `--pkg` **默认值写死 v2.0** ⇒ 裸跑一次就会**重建 v2.0 的快捷方式** ⇒ 已改：默认改为**交付版 v2.1** ＋ 新增硬闸门 `SUPERSEDED = {'2.0': '2.1'}`（被取代 ⇒ **exit 2、一个 .lnk 都不写**）；docstring 改 raw string（消除 `SyntaxWarning: invalid escape sequence '\p'`）。
* **反证实测**：`.venv\Scripts\python.exe results/app/app212_app057_v20_shortcuts.py --pkg "C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.0"` ⇒ 打印 `[ABORT] 版本 v2.0 已被 v2.1 取代（APP-060 ①）…`、**EXIT=2**；复查桌面**仍只有 v2.1 两个 .lnk**（未误建）。

#### ③ APP-059 三项本轮已做完（APP-060 ③ 复核）
* ① 更正两处说法 ✔（§125 ③）② 补全 MANIFEST 哈希 ✔（§125 ④）③ ≤ 6 步用户操作说明 ✔（§125 ⑤，`shared\ext_listen\v21\HOWTO.txt`）；**插件配音实录仍等 EXT-032 通过**后由用户抽听（EXT 模块 `last_ack` 仍 EXT-031 ⇒ EXT-032 未执行）。

#### ④ 🔴 已知缺口（如实记录）：**交付 zip 内的 README 仍是改前版本**
* APP-059 ① 的「说话人标签局限」段落是在 **21:05** 定点写进 **v2.1 目录**的，而 zip 是 **20:38** 打的 ⇒ zip 内 `README_zh.md` = 47 497 B / `1b022c33d04f7eca…`、`README_en.md` = 52 950 B / `42cdd5a146a8fb87…`（**改前**）；目录里是 47 786 B / `6300285e9d7c51bd…` 与 53 291 B / `91cbca2ef1096b41…`。该改动**早于** APP-060 ④（21:10）⇒ 属规则生效前动作；**此后不再原地改 v2.1 的目录与 zip**。
* 要让**交付 zip** 带上这段说明 ⇒ 需**另打 v2.2**（APP-060 ④）⇒ 本轮**未打包**（未获用户授权）⇒ 已写进 `DELIVERY_2.1.json` 的 `known_gap` 字段。

#### ⑤ 收尾复核（本轮真实值）
* 🔴 **CORRECTIONS_APP.md 在本轮中途被 reviewer 追加了新条目**（**不是**「SHA 零改动」）：开工 SHA256 `ccdb7712e893c6d2…` / 150 636 B / 20:56:19 / 59 条 ⇒ 收尾 SHA256 `4aab04746e9356d552af2455ff7ebe3ae2d195205ef39437c772cfd3d2dadade` / **151 541 B** / **21:09:20** / **60 条（新增 APP-060）** ⇒ **§125 ⑧ 原写的「零修改」作废，以本行为准**；该文件本模块全程**只读**。
* 本轮**未打包**、未改任何 zip；v2.0 / v2.1 的目录与 zip **均未覆盖、未删除**。
