# §19 / §20 全量明细（EXT-016 下沉存档）

> ★ 本文件是 `status/STATUS_EXT.md` 中 **§19 / §20 两节内联正文的原文存档**。
> 依据 **EXT-016 写作规则**（「STATUS ≤ 300 行 / ≤ 40 KB / < 归档/10」），
> §19 / §20 的内联明细**下沉到本文件**，STATUS 只留「依据 + 关键数字 + 结论 + 指针」。
> ⚠️ **不回头改旧章节的结论**——§19 / §20 的**数字一字未改**（只是搬到本文件）。

---

## §19 T-5 / T-6 —— 内存不持续增长（无界列表有界化） + 设置持久化（2026-10-31 23:21）

**依据**：闸门 **exit 1**（latest=**EXT-026** / last_ack=26 / `already_executed`）⇒ **没有更新的纠偏条目**
⇒ **未认领新编号** ⇒ **`last_ack` 保持 EXT-026**。★ 按 **EXT-014 ②**（「`last_ack` 追平后，只要还有未完成项，
就自己继续做，不要空转」）⇒ 继续「未完成纠偏清单」里的 **P2 待办**（`设置持久化 / 30 分钟不崩·内存不持续增长`）；
克隆音色（依赖 ASR-013 交付）、暂停拖动（需真实手势 + reviewer 口径）本轮**不做**。
★ **明细全文见 `status/notes/sec19_t5_t6_bounds_persist.md`**（6 节，13 267 B）——本节按 EXT-016 常设规则**只留结论**。

⇒ **① 3 类真缺陷（无界增长）**（★ 逐条根因/修法见 notes §19.2）：
**T5-a** 服务端 `_frame_arrival_delays` 每帧追加永不裁剪（≈47 帧/秒 ⇒ **30 分钟 ≈ 8.5 万条/会话**）
⇒ 保留最近 **`C.FRAME_DELAY_HISTORY = 2000`** 条；**统计口径不变**（`n_frames_measured`/`late_ratio`/`mean`/`max`
改由**累计量**承担，⚠️ 均值累加 `round(delay,4)` ⇒ 与旧实现**逐位等价**），新增 `history_window`/`history_kept`。
**T5-b** `_seg_orig_end`/`_seg_ready` **只写不读**（全仓 grep 零读取点）⇒ 保留最近 **`C.SEG_TIMING_HISTORY = 50`** 段
（无读取点 ⇒ **不影响任何统计口径**；加 `threading.Lock` 防并发改 dict）。
**T5-c** 插件 `player.js`+`offscreen.js` 的 `gapDetail` 只追加永不裁剪 ⇒ 两侧各加 **`GAP_DETAIL_CAP = 200`**，
超出丢最旧的并**如实计数**（`gapDetailDropped`），上报口径 `slice(-20)` **不变**。
⚠️ **刻意没改** `margins`/`engine_calls`（reviewer 的**验收记录本体** ⇒ 裁剪会让验收数字失真）。

⇒ **② T-6 设置持久化**：`saveCfg()` **只在点「开始」时被调用** ⇒ 用户改了设置后**直接关掉弹窗** ⇒ 改动**全丢**
⇒ 新增 `readCfg()`/`persistCfgNow()`/`schedulePersistCfg()`（400 ms 防抖）/`bindPersistListeners()`
（**8 个控件**全挂 `change`，文本框与数字框额外挂 `input`）；`saveCfg()` **改为复用 `readCfg()`** ⇒ 两条写盘路径
口径**必然一致**；落盘前**归一**；绑定**幂等**；调用点在 `loadCfg()` **之后**。

⇒ **③ 自测**：新增 `t5_t6_bounds_persist_harness.js`（**16**）+ `test_t5_t6_bounds_persist.py`（**40**）
⇒ **24 套 / 1 104 PASS / 1 FAIL**（§18 为 23 套 / 1 064 / 1 ⇒ **+1 套 / +40 PASS，零回归**）；
node harness **7 套全 rc=0**；三套明文自测单独确认 rc=0（**103**/**11**/**19**）。

⇒ **④ ★反证**（区分真通过/假通过，详见 notes §19.4）：短路 `player.js` 裁剪 / 改坏 `popup.js` 绑定
⇒ harness **rc=1**；删掉 `bridge.py` 裁剪两行 ⇒ Python **rc=1（3 条断言红）**；短路
`_trim_seg_timing_history` ⇒ **rc=1**。★ 另修**两个测试自身的坑**：①「口径对照」首跑红 2 条
⇒ 根因**墙钟噪声**（两个 session 的 `t0` 不同）⇒ 改为**显式对齐 `t0` + 同一组 `recv_at`**
⇒ 并借此发现并修正一个**真口径差异**（round 前 vs round 后求和）；② `popup.js` 是 **CRLF**
⇒ 反证正则写死 `\n` 匹配不到 ⇒ 全改 `\r?\n`。

⇒ **⑤ FAIL 归因**：`test_ext016_compression` ⇒ **基线复核**（`git stash` 后重跑）⇒ **同样 37 PASS / 2 FAIL**
⇒ **既有状态、非本轮引入**；其中「CORRECTIONS 明显变小」⇒ reviewer 独占文件 ⇒ **只读、不 `git add -f`**；
「精简版 STATUS 不含历史全文」⇒ **本轮已修**（见 §20）。

⇒ **⑥ 产物**：产品代码改动 **5 个**（+215 −12 行）；新增自测 **2 个**；notes 明细 **1 个**。

⇒ ⛔ **未做 / 不宣称**：⛔ **未认领新 EXT 编号**；⛔ **克隆音色仍不可用**（依赖 ASR-013 交付）；
⛔ **「30 分钟不崩」未做**（需真实引擎 + 独占设备）⇒ **不宣称「30 分钟不崩已验证」**；
⛔ **「暂停拖动」未做**（需真实手势 + reviewer 口径）；⛔ 端到端仍不实时（TTS RTF 1.0022）/ 同步误差仍超标；
⛔ **未改任何引擎文件**；⛔ **未跑真实推理、未占 GPU/NPU、未创建/未回收机器锁**（开工时锁不存在）；
⛔ `CORRECTIONS_EXT.md` **只读、未修改、未入库**。

---

## §20 §19 收口 —— 补 EXEC_LOG + 提交 + **STATUS 压缩回限额内**（2026-11-01 00:57）

**依据**：闸门 **exit 1**（latest=**EXT-026** / last_ack=26）⇒ **无新编号** ⇒ 继续 §19 的**收口**（上一轮被中断：
代码与 notes 已写好，但 **EXEC_LOG 未追加、未提交**）。

⇒ **① 补完 §19 的收口动作**：追加 `status/EXEC_LOG.md` 本轮记录 + 在本仓库提交
（只加本模块文件；`status/CORRECTIONS_EXT.md` 在 `.gitignore` ⇒ **未 `git add -f`**）。

⇒ **② ★发现并修掉一个本轮引入的回归**：§19 的正文写入把精简版 STATUS 从 **22 559 B** 推到 **29 652 B**
⇒ 撞破 EXT-016 的硬约束「< 归档/10 = 22 483 B」⇒ `test_ext016_compression` 的
「精简版 STATUS 不含历史全文」断言**由 PASS 转 FAIL**（⇒ **不能只报「既有 FAIL」就放过**）。
★ 修法（**按 EXT-016 规则裁剪，不是删内容**）：§17 / §18 / §19 的内联明细**下沉到 `status/notes/`**
（三份 notes 已在库、已含全部实测数字与反证）⇒ STATUS 只留「依据 + 关键数字 + 结论 + 指针」。
⚠️ **不回头改旧章节的结论**；§17/§18/§19 的**数字一字未改**（只是搬到 notes）。

⇒ **③ 自测**：三套明文自测 **rc=0**（**103**/**11**/**19**）；全量 **24 套**；
node harness **7 套全 rc=0**；`test_t5_t6_bounds_persist.py` **40 PASS / 0 FAIL**。
