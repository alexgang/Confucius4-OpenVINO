# STATUS_APP §135–§140 摘要行归档

> 🔴 2026-11-10 15:5x ｜ 为写 §167 腾字节限额（APP-052④ ≤40000 B）
> ⇒ 把 §135–§140 的**摘要行整块**移入本文件（原正文早已各自归档到
>   `status/archive/STATUS_APP_secNNN_*.md`）⇒ **零信息丢失**，
>   `STATUS_APP.md` 对应位置只留短指针。

---


> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec135_upto_20261105.md`（18 133 B，逐字保留）＋ 本轮追加的 §135–§137 三节原文另见 `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：④ ABBA **10/0** ＋ GUI 臂 **5/0**；② 交付物 **12/0**（`shared/app_listen/v23_clone/`）；3(a) CLI **8/0**；**MiniMVP P0 已修（rc2）**。

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec136_upto_20261105.md`（12 364 B，逐字保留，含 9 项速查表）＋ `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：APP-069① 根因＝**rc2 的 24 段全零是「落盘算法」假象**（`app267` 6/0）；dump 已修（顺序拼接＋回填 `wav_t0`/`wav_t1`/`peak`/`rms_db`）；内容判据 `app268` **4/0**；APP-068 `app266` **7/0**；APP-069⑤ 5 项清理全落地（含 torch 拆 `backends_torch.py`）；APP-070① **删 IR 清单已出（8 个 / 975.9 MB，一个都没删）**；rc3 **6 843.8 MB / 10 503 文件**；设备级 3(a) **PASS 9/0**（wall 381.86 s / 76 句全成）；APP-069② `--check` 臂 **10/10 零崩溃**。

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec137_20261105.md`（9 705 B，逐字保留，含 14 个产物的字节数／mtime／SHA256 清单）＋ `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：APP-069⑥ MT INT4 vs INT8 **本条已完成**（46 段／`exact_same_pct=4.35`）；🔴 夹具缺陷**已修**（首跑 `APP273_EXIT=2` ＝ 0 段）；口径差异已说明（reviewer 写 76 段，本机英文定稿 **46**）；APP-069② GUI 臂 **需等 reviewer 复核**（`--check` 10/10 零崩溃 ✅，GUI 有效启动 0/10）；本轮回收 2 个孤儿机器锁（`OpenProcess err=87` 确证死）。

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec138_20261105.md`（28 336 B，逐字保留，含 README 全文、全部产物元数据、闸门原始字段）＋ 本轮压缩前的**逐字正文**另见 `status/archive/STATUS_APP_sec138_live_20261105.md`。
> 🔴 **速查**：zip `…_v1.0-rc3_perftest.zip`（5 591 630 138 B／10 474 条目／SHA `dda6f229…2d45f1`）；三闸门全过（黑名单 **6/0**／NOTICE 署名 PASS／`--check` **5/0**）＋ GUI 冒烟 **5/0**；README_perftest.txt 9 155 B 进包；⛔ APP-071 **(a)(b)(c)(d) 全未做** ⇒ v2.3 不打包（续见 §139 ⑨）。

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec139_20261105.md`（逐字保留，含 10 项速查表、全部产物元数据、纪律自检）。
> 🔴 **开工/收尾 `CORRECTIONS_APP.md`（reviewer 独占文件，全程只读、未改、未提交）**：SHA `1dd0bcca…9c42900`／215 258 B／mtime 2026-11-05 16:03:18／**74 条**（APP-001..APP-074）⇒ 开工与收尾**逐字相同**（reviewer 本轮未追加）。
> 🔴 **速查**：**解压副本冒烟 7 PASS / 0 FAIL**（rev2 zip 的解压副本：`--check` 5/0／CLI rc=0 wall 87.98 s／log 无 Traceback／**tts.jsonl 非零 wav 17/17**／音色 A 未回落／无 babelvox 示例音色）＋ 内容判据 **PASS**（零段 0）＋ 反证 **PASS**（rc2 旧产物 FAIL/受损 24）｜🔴 **核心疑问已定案：`--tts-voice A` 不依赖被剪掉的 babelvox 示例音色**（`--tts-voice` 的 `choices` 只有 `A`/`follow_speaker` ⇒ **传不进 cindy**；`A` → `preset_A.wav`，**在包内**）｜**README 文件数已改正**（10 503 → **10 474**）＋ **zip 已重打（新文件名 ⇒ 不覆盖旧 zip）**：**最终 SHA256 `90ae8b9da38eeca6ab9e6a693e9ac6395bdcb678e9377c5a4f655a7c5a06f58f`**（`shared/minimvp/…_v1.0-rc3_perftest_rev2.zip`／5 591 630 139 B／10 474 条目）｜**一致性对账**：逐条 CRC32 ⇒ **只 `README_perftest.txt` 1 个不同**，其余 10 473 个逐条未变；旧 zip SHA 逐字未变｜🔴 **APP-074(a)② 已答**：预设 A 在 v1.13/v2.0/v2.1/v2.2/rc3 五个包里 **SHA 全部相同**（来源 **Amphion metis prompt.wav**，NOTICE 署名 Apache-2.0）⇒ **不来自 babelvox 示例 ⇒ v2.x 不违规**｜⛔ **APP-071 仍未完成（BLOCKING，放 rc4）**：本轮未动，上一会话的 `app283_app071_diag/` 一字未动 ⇒ **v2.3 不打包**。

> 全文（4 条证据／md5 表／3 旧包清单／8 音色与 r2 顶层文件**完整 SHA256**／日志原文／口径订正）**逐字归档** ⇒ `status/archive/STATUS_APP_sec140_20261106.md`；本节仅速查。
> 🔴 `CORRECTIONS_APP.md` 只读未改：开工 `3f759ebe…7f359`／219 810 B／77 条 ⇒ 收尾 `bbc95c43…d82af`／220 735 B／**78 条**（中途追加 APP-078）；**SHA/字节/条数均变，不声称零改动**。
> 🔴 **APP-075 需等复核**：r2 最终 **54 文件／20 175 499 B**（manifest 自记＝磁盘；`_app309` **18/0** 补齐静默漏拷的 `submit.jsonl`，旧「52／20 160 623 B」为写前口径）；F0 **21/19/6**，19 FAIL 全 `male→female`，S2 已登记仍串女声；真 x-vector 未产出、第 2 臂未跑 ⇒ **v2.3 不打包**。
> 🔴 **APP-076 已完成**：`_app304` **39/0**（5 文件 md5／`ASR_FILES` 4→5／0.6 同源／app193 正则／克隆门槛未放宽）；MiniMVP「不适用」。v2.3 带 5 文件＋`fp16-w5/`。
> 🔴 **APP-077 已完成**：`_app302` **26/0**（3 旧 zip 同值 `bridge_token.txt`，完整清单见归档件 §3；MiniMVP 无 token）＋`pkg_exclude` 两处独立拦；`_app305` **27/0**（版本无关启动器）；**未生成桌面 .lnk**，待 v2.3 接线。
> 🔴 **APP-078 已完成**（13:31 追加）：`_app306` **28/0** —— **目录 ≠ zip**（3 安装目录各 8 音色，3 zip 均 0；完整 SHA 见归档件 §4①）⇒ **改正 §139「v2.x 不违规」：只对 zip 成立**；`assert_pkg_clean.py`＋`_app307` **14/0**；旧包一字节未动。
> 🔴 **纪律**：未打包／未打 zip／只读扫描旧包／未改 .lnk／未动 `v23_clone/`／未在 CPU 跑推理测速／未调 MiniMax／未提交纠偏文件／逐文件 `git add`＋main 普通 push。**没落盘的不写已交付**。
