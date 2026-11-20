# APP-119 STATUS 邮件 · 完整明细（A 机留档）

> 邮件正文（紧凑版）见 `results/app/app219_status_email_body.md`。
> 本文件是**完整明细**，供 reviewer 复核时对照。

## 一、§1 出厂默认

- 完整版出厂默认 = **ASR GPU.0 / MT GPU.0 / TTS NPU**（取代 APP-099 0.1 的 TTS=GPU.0；
  ASR 模型仍是 R2T2 1.7B）。
- 代次：完整版 `defaults_version` **9 → 11**（MiniMVP 9 / SpecialMVP 10 不变）。
- 迁移判据（值判据）：旧出厂默认整体相等才迁；`defaults_version >= 11` 一律信任；
  迁移写进日志/状态条。
- 迁移判据实测：**15/15 PASS**（`app119_migration_test.json`，n_fail=0）。

## 二、§2 取消 NPU 互斥

- 删除 `_enforce_no_npu_conflict()` / `_sync_mt_combo_to_gpu0()`；启动时的 D4 冲突处理删除。
- GUI / CLI / device_config 一视同仁：**任意组合都允许**（含三个模块全 NPU），
  **不再自动改用户的选择**。
- 只保留**一条不阻塞**的 NPU 共用性能提示（挂 TTS 状态条）；**APP-117 总状态灯未加回**。
- 回退链仍不含 NPU（回退只在「用户选的设备本机不存在」时发生 ⇒ 不静默换设备）。

## 三、§3 三臂验收

### 臂 1 新默认（GPU.0/GPU.0/NPU）—— 必须 PASS

| 项 | 第一次跑 run20261121-030855 | 复跑 run20261121-032253 |
|---|---|---|
| 总判 | **FAIL**（唯一 FAIL＝并行） | **PASS 14/14** |
| 并行生效 | False | **True** |
| TTS 就绪 | 20.4 s | **11.0 s** |
| 丢句 | 0 | **0** |
| 语速 max | 1.4281 | **1.4368**（≤1.70） |
| synth_rtf 中位/P90 | 0.9881/1.0731 | **0.9656/1.0604** |
| play_lag max/end | 106.711/84.771 s | **88.805/69.635 s** |
| 整链耗时 | 695.4 s | 678.3 s |

- 计数：150（译文）== 150（进 TTS）+ 0（丢弃）
- `timing_valid=false`：synth_rtf P90=1.060 > 0.75（合成 RTF 异常 ⇒ 机器被占） ⇒ **计时类结论不成立**（计数类结论不受影响）
- 锁看门狗：67；外部写入 []；运行前后 GPU 占用列表逐项相同。

### 臂 2 极限组合（全 NPU）

- verdict=FAIL；rc=0；耗时 758.0 s；检查 14/14（唯一 FAIL＝「并行生效」，
  **同卡 ⇒ 该串行，属设计内**）。
- 实际设备：ASR `NPU`／MT `NPU`／TTS `NPU`（日志原文核对，**无任何**
  「自动改到 GPU.0」）。
- synth_rtf 中位/P90/max = 1.065/1.3228/1.6232；丢句 0；
  积压峰值 178.163 s；TTS 就绪 11.5 s。
- NPU 加载/编译：ASR 1.7 s／翻译 2.4 s／TTS 引擎 5.7 s／worker 8.3 s。
- 进程内存（Windows 工作集，并行采样 152 次）：合计峰值 **8891.4 MiB**／
  单进程峰值 **4815.5 MiB**（3 个包内进程）。

### 臂 3 混合组合（ASR=NPU/MT=NPU/TTS=GPU.0）

- verdict=PASS；9/9 项检查全过（n_fail=0）；rc=0；耗时 187.5 s。
- ASR 实际 = NPU；MT 实际 = NPU；TTS 实际落点 = GPU.0；
  **日志里没有「MT 自动改到 GPU.0」⇒ §2「不再自动改用户的选择」实证成立**。

## 四、🔴 本轮修掉的真缺陷

- APP-113 §2 的并行加载判定写死「TTS 档位 == CUDA」；
  APP-119 §1 把默认改成 TTS=NPU 后，默认配置（ASR=GPU.0 与 TTS=NPU **异卡**）
  被**静默地永远串行** ⇒ 默认配置白丢并行收益 ⇒ 首次跑唯一 FAIL。
- 修法：新增 `_accel_class()` / `_same_accel()`，判定改成「**同卡才串行**」；
  同卡（GPU↔GPU、NPU↔NPU）保持原串行行为，异卡允许并行，未知保守串行。
- 只改**加载顺序**，不改落点，不引入设备限制。
- 行为级判据：`_same_accel` 真值表 **9/9 PASS**；反证组（老实现恒当同卡）
  被 **5 条**用例识破。

## 五、包与纪律

- v2.5 已同步（`device_config.py` / `live_caption_app.py` 与 dev **逐字节一致**，
  包文件数 48790）；**v2.4 / rc11 / sp5 逐字节未动**；🔴 **未打 zip**（§3 明令）。
- `CORRECTIONS_APP.md` **只读**（本轮一个字未改）；未跑 MiniMax；未占他模块锁；
  未连接 B 机（APP-109 ④）。
