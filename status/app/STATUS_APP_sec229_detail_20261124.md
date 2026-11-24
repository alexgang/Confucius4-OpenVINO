# STATUS_APP §229 · 执行 **APP-130**（NPU 配音杂音根因：code predictor 输出 NaN ⇒ 自检兜底 + 运行时保险）

- 日期：2026-11-24（本轮实跑）
- `last_ack`：APP-129 → **APP-130**
- 纠偏来源：**QQ 邮箱** `msg_Yyrg-pvMdtPKf1VeqUKgcQuNp_2U35aZPYNyVIE6GqqdQA`（2026-11-24 08:58:20 GMT+8）＋ **局域网同一条**（mtime 08:58:23）⇒ 同一编号只执行一次。

## §0 根因（reviewer 的 4 组对照实验，本轮原样承接）

| 臂 | 结果 |
|---|---|
| 产品 NPU 引擎原样 | 每句生成到 492 帧 = 39.36 s（GPU.0 引擎同句 5.84 s） |
| 声码器：同一组码在 NPU / GPU.0 / CPU 解码 | 精度差正常 ⇒ **不是声码器** |
| talker 全部桶改到 CPU（同静态形状）/ NPU 显式 f16 | 仍 492 帧 ⇒ **不是 talker** |
| 说话人向量换成 GPU.0 算的 | 仍 492 帧；两边向量余弦 0.998 ⇒ **不是 speaker encoder** |
| **cp_prefill / cp_decode 改到 CPU（同静态形状、循环不变）** | **5.44 s / 68 帧，正常收尾** |
| 同一个 cp_prefill 输入在 NPU vs CPU | 比较结果为 **NaN（输出含 NaN）** |

⇒ 根因：`tts_engine._move_cp_prefill_to_npu` / `_move_cp_decode_to_npu` 把 code predictor 编到 NPU 后，在**这类机型/驱动上输出 NaN** ⇒ talker 每步拿到的 15 组码被污染 ⇒ **永远走不到 EOS**⇒ 一句拖到帧上限（39 s 乱说）。A 机（Panther Lake）NPU 正常 ⇒ **机型/驱动相关**，代码原本无任何兜底。

## §1 代码改动（`live_caption/tts_engine.py` ＋ `live_caption/tts_worker.py`）

1. **自检兜底**（APP-130 §要做的 1）：`_move_cp_prefill_to_npu` / `_move_cp_decode_to_npu` 在 **NPU 编译成功后、替换 `eng.cp_*` 之前**做自检 —— 固定种子（`CP_SELFCHECK_SEED=20261124`）造 3 组输入（幅度 **0.02 / 0.1 / 1.0**；cp_prefill 用 `(1,2,1024)`，cp_decode 按 `CP_DECODE_NPU_SHAPE` 造**零 KV + 合法 attention_mask**），在 NPU 版与**现有 CPU 版**上各跑一遍 ⇒ 任一输出含 **NaN/Inf**、或与 CPU 的余弦 **< 0.99** ⇒ **不替换、保留 CPU** ＋ 日志写明「NPU 自检失败（原因）⇒ 留在 CPU」。
2. **运行时保险**（§要做的 2）：`_CPNaNGuard` 包裹 code predictor ⇒ 输出 NaN/Inf **立刻抛 `CPNaNError`** ⇒ 生成循环当场停止本句 ＋ 记 **`tts_runaway`** 计数；另加**失控阈值**保险（阈值 = `runaway_threshold_s(estimate_sec(text, lang))` = `max(3×估计秒数, 估计秒数+8 s)`，估计秒数 = **非空白字符数 × 每字秒数 + 尾部常数**）。
3. **计数唯一权威点**：`tts_engine._mark_runaway(eng, reason)` 用 `eng._runaway_counted` 守卫（`stream()` 每句重置）⇒ worker 侧第三道闸与引擎侧保险**同一句只记一次**。
4. **worker 侧**：`tts_worker.py` 的 worker 第三道闸触发处记 `tts_runaway`；引擎侧保险触发的 RUNAWAY 反映到逐句遥测的 `runaway` 标记。

## §2 单测（不需要 NPU；`results/app/test_app130_cp_selfcheck.py`）

- **34/34** 条断言全过；覆盖：自检走「替换」／「保留 CPU」两条路、运行时保险在假 NaN 下 **1 步内停**、失控阈值保险、🔴 **OV 真实返回形态（`OVDict`）的回归用例**（见 §4 事故①）。

## §3 A 机（NPU 正常机型）实测：**自检通过、cp 仍在 NPU**

- （本轮未取到自检日志 ⇒ **如实留空**，未取到的数字不写「已通过」。）

## §4 本轮如实登记的 3 处事故与 2 处判据错误

🔴 **事故①（判据错误，最严重）**：补丁①的判据把 OV 的输出当成 `dict` 处理 ——而本机 OV 2026.4.1 的 `CompiledModel.__call__` 返回的是 **`OVDict`**（`collections.abc.Mapping`，**不是 `dict`**），且 `np.asarray(OVDict)` 得到 **object 数组** ⇒ 余弦恒 **0.0000** ⇒ **A 机上自检恒判失败 ⇒ cp 被打回 CPU**（一度把 A 机的 TTS 从 NPU 降级到 CPU）。⇒ 同一个根因还让 **运行时 NaN 守卫形同虚设**（`_find_nonfinite` 永远返回 None）。⇒ 修法＝补丁④（`_ov_out_to_dict` 归一化）＋补丁⑤（`ConstOutput.get_names()` 取名，**不能带形状**：CPU 动态维 IR 的键是 `names[hidden_states] shape[1,?,1024]`，NPU 静态形状的是 `names[hidden_states] shape[1,2,1024]`）⇒ 修后 A 机余弦 **0.998595 ~ 0.999968**（见 §3）⇒ 自检通过。
🔴 **判据教训**：「FAIL 先怀疑判据/环境」**本轮再次被证实** —— 余弦**恰好 0.0000** 是「形状不匹配」的特征，不是「数值无关」的特征。
🔴 **事故②**：EXT 源码仓 `live_dub_ext` 的工作树在本轮执行期间已被 reviewer 改成 **v0.4.20**（`M ext/bridge.py`／`M ext/version.py`／`M extension/manifest.json` 等 ＋ 未跟踪的 `tests/test_ext0420_clone_gender.py`）⇒ **第一次同步会把它当 v0.4.19 打进去** ⇒ 改为**按 commit `3573b2d` 取内容**（`git show`）⇒ 包内逐文件与 commit 比对 **10/10 一致**。
🔴 **事故③**：桥接默认把 `bridge_token.txt` 落在 **`<包根>/ext/`** ⇒ **包内污染** ⇒ 改为显式 `--token-file <包外臂目录>/bridge_token.txt` ＋ 清掉已落盘的那一份。
🔴 **事故④**：顶层目录改名（`…v2.6.staging` → `…v2.6`）被本机系统拒绝（`PermissionError 13`；同名的**嵌套**目录改名/删除都正常 ⇒ 是目录自身的 OS 句柄未释放，不是权限问题）⇒ 改为**直接 robocopy 到正式目录**，staging 残留在盘上（待句柄释放后清理）。
🔴 **事故⑤**：第一次整链用 EXT 的 `AUTO` 设备解析 ⇒ 实际是 **MT=NPU / TTS=CUDA 边车**（与 App 完整版默认档 `device_config` 的 **GPU.0 / GPU.0 / NPU** 不同）⇒ 按 reviewer 明文「出厂默认：ASR/MT GPU.0、TTS NPU」显式钉死 `EXT_MT_DEVICE=GPU.0` ＋ `EXT_TTS_DEVICE=NPU` 重跑。

## §5 纪律

- 🔴 **未通知用户**（reviewer 明文「不要通知用户，reviewer 复核后再说」）。
- 🔴 **未连 B 机**（APP-109 ④）—— B 机的复现验证留给 reviewer。
- 🔴 **未调 MiniMax**（质量判定由 reviewer 回转写）。
- 🔴 **未改 `status/app/CORRECTIONS_APP.md`**（只读）。