# STATUS_APP「最近更新」条目归档（§144 写入前整块逐字搬迁，2026-11-07 00:29:43）

> 🔴 以下 2 行原文逐字保留，一字未删、行尾未改；原文件原位只留 1 行速查。
> 来源：`status/app/STATUS_APP.md` 的 `## 最近更新`（§139 / §140 两条）。
> 块 SHA256：`853a0d85678f895f4b88ee294faaaeabec61ca31c2a3a247958a8f8c442f1c8d`

```text
- 2026-11-05 18:07:58 **§139 已写** ⇒ **APP-073 + APP-074 本条已完成**：**解压副本冒烟 7/0**（rev2 zip 的解压副本：`--check` 5/0／CLI rc=0 wall 87.98 s／log 无 Traceback／**tts.jsonl 非零 wav 17/17**／音色 A 未回落／无 babelvox 示例音色）＋ 内容判据 **PASS**（零段 0）＋ 反证 **PASS**（rc2 旧产物 FAIL/受损 24）｜🔴 **reviewer 的核心疑问已定案：`--tts-voice A` 不依赖被剪掉的 babelvox 示例音色**（`--tts-voice` 的 `choices` 只有 `A`/`follow_speaker` ⇒ **传不进 cindy**；`A` → `preset_A.wav`，**在包内**）｜**README 文件数已改正**（10 503 → **10 474**，唯一命中，写后逐字节复核）｜**zip 已重打（新文件名 ⇒ 不覆盖旧 zip）**：`…_v1.0-rc3_perftest_rev2.zip`（**5 591 630 139 B／10 474 条目／SHA256 `90ae8b9da38eeca6ab9e6a693e9ac6395bdcb678e9377c5a4f655a7c5a06f58f`**）｜**一致性对账**：逐条 CRC32 ⇒ **只 `README_perftest.txt` 1 个不同**，其余 10 473 个逐条未变；旧 zip SHA 逐字未变 ｜🔴 **APP-074(a)② 已答**：预设 A 在 v1.13/v2.0/v2.1/v2.2/rc3 五个包里 **SHA 全部相同**（来源 **Amphion metis prompt.wav**，NOTICE 已署名 Apache-2.0）⇒ **不来自 babelvox 示例 ⇒ v2.x 不违规**｜⛔ **APP-071 仍未完成（BLOCKING）**：本轮未动（reviewer 明文放 rc4）；上一会话的 `app283_app071_diag/` 一字未动
- 2026-11-06 13:59:48 **§140 已写** ⇒ **APP-076/077/078 本条已完成**（39/0｜26/0＋27/0｜28/0＋14/0）、**APP-075 需等 reviewer 复核**（r2 最终 54 文件／20 175 499 B，`_app309` 18/0 补齐 `submit.jsonl`，F0 21/19/6 未通过）；**改正 §139**（目录≠zip）；**reviewer 中途追加 APP-078**（77→78 条，SHA 变化如实记录）；⛔ **v2.3 不打包、旧包一字节未动**
```
