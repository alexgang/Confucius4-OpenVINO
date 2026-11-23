# ASR §89 —— APP-121（App 模块纠偏）复核：**ASR 侧只读复核 + 契约补正 + 撤回 §88 两句结论**

> 🔴 **本轮触发源**：reviewer 的 **APP-121**（App 模块纠偏，2026-11-23 09:03，
> 邮件 `msg_Nz6bxdO7DCc6M5vrw3fbQIdOWwXuYdRjFVGNmdYk1VS8iQ`，收件箱未读）。
> 🔴 **纠偏文件通道无新条目**：`CORRECTIONS_ASR.md` **105 868 B** /
> md5 `b6fd2e142d04d20268af28b2340dd49a` / mtime **2026-11-20 15:33:39**
> （与前 25+ 轮逐字相同）⇒ **35 个 `## ASR-` 标题、最大编号 ASR-066**
> ⇒ 搜 `ASR-067+` **0 命中** ⇒ **`last_ack` 保持 `ASR-066`**。
> 🔴 **本轮是只读复核 ＋ 文档**：**未跑任何推理/计时**、**未取 MACHINE_LOCK**
> （全程锁不存在）、**未改交付文件**（`live_caption/` 属 App）、**未打包**。

---

## 一、结论（一行）

🔴 **reviewer 的 APP-121 §1 断言成立**：App 的 `asr06b_stateful_backend.py`
把**生成预算 `reserve`** 也减进了 **prompt 上界** ⇒ **NPU 档（limit=320）**
在**段长 ≈18.3–18.6 s** 时 `allowed_prefix < 0` ⇒ **抛 `ValueError`**
⇒ 异常冒到 `live_caption_app.py` `Session._loop` 的外层 `except`
⇒ **本次会话的字幕整条停掉**。✅ **本模块已复核复现（只读、无推理）**，
并**补正了自己写的 handoff 契约**（新增 §三点三）—— 根因是**契约表述有歧义**，
不是 ASR-065 的参考实现有错。

---

## 二、§1 缺陷复现（**只读单元复核，不做推理**）

### 2.1 方法

🔴 **不做任何推理**：不加载 IR、不 compile、不跑模型 ⇒ 只
**加载真实的后端类**（`ASR06BStatefulBackend`），用**算术输入**调用
**未经修改**的 `build_inputs_embeds()`。

- 音频 token 数直接喂 `audio_emb.shape[0]`（= encoder 输出行数 = 音频 token 数）；
- 骨架 = `len(_ids_left) + audio_tok + len(_right_ids(force_language))`；
- 文本骨架**实测**：`_PROMPT_LEFT` = **9** token、`_PROMPT_RIGHT` = **6** token
  ⇒ **骨架 15**；语言后缀 `language English<asr_text>` = **3** token
  ⇒ 带语言时骨架 **18**。
- 音频 token ⇄ 帧数换算用 `bk_mel.total_aftercnn_len`（**逐帧一致**，每 100 帧 → 13 token）。

### 2.2 两个版本

| 版本 | 文件 | md5 | 说明 |
|---|---|---|---|
| **A = 交付版（有缺陷）** | `git show HEAD:live_caption/asr06b_stateful_backend.py` | `a92c02f2eff02ec7cd29013cfdd2f8b8` | **＝ MiniMVP v1.1 包内那份**（`Confucius4_LiveCaption_MiniMVP_v1.1/app/`，md5 相同） |
| **B = App 正在修的工作树版** | `live_caption/asr06b_stateful_backend.py`（**未提交**） | `4b43dcbcd6ce5cb44cf8c07bc084a50f` | APP-121 §1 的修法（App 线程在自己树里改） |

### 2.3 A 版（交付版）实测结果

| 用例 | audio_tok | reserve | 语种后缀 | skeleton | 结果 |
|---|---|---|---|---|---|
| NPU 长段 | 238 | 32 | 无 | 253 | **OK**（emb=253） |
| NPU 长段 | 238 | **64** | 无 | 253 | 🔴 **RAISE ValueError** |
| NPU 长段 | 238 | 32 / 64 | **en(+3)** | 256 / 256 | 32 → OK；**64 → RAISE** |
| NPU 长段 | 260 | 32 / 64 | 无 | 275 | 32 → OK；**64 → RAISE** |
| NPU 长段 | 266 | 32 / 64 | 无 | 281 | 32 → OK；**64 → RAISE** |
| NPU skeleton=321（验收：必须报错） | 306 | 32 / 64 | 无 | 321 | ✅ **RAISE ValueError**（两版本都正确） |
| GPU.0（limit=512）同样输入 | 238/260/266 | 32 / 64 | 无 | 253/275/281 | ✅ **全部 OK**（GPU 档不受影响） |

🔴 **触发门槛（段长）**（A 版，NPU 档）：

| 语种后缀 | reserve | 首个坏音频 token | ≈ 段长 |
|---|---|---|---|
| 无（骨架 15） | **64** | 242 | **≈ 18.57 s** |
| en（骨架 18） | **64** | 239 | **≈ 18.33 s** |
| 无 | 32 | 274 | ≈ 21.01 s |
| en | 32 | 271 | ≈ 20.81 s |

⇒ **reviewer 的「≥~18.3 s 会抛」成立**（本模块实测 18.33–18.57 s，
比 reviewer 的 18.3 s 略保守，因骨架实测是 **15**（不是 18）而**语言后缀 +3**）。

### 2.4 A 版的第二个后果：**前缀被多砍 32–64 token**

`allowed_prefix = limit - skeleton - reserve` ⇒ 流式档（reserve=32）与
段尾档（reserve=64）**截断口径不同** ⇒ 前缀保留量实测：

| audio_tok | skeleton | reserve | A 版保留前缀 | handoff 口径保留 | **多砍** |
|---|---|---|---|---|---|
| 238 | 253 | 32 | 35 | 67 | **32** |
| 238 | 253 | 64 | 3 | 67 | **64** |
| 260 | 275 | 32 | 13 | 45 | **32** |
| 266 | 281 | 32 | 7 | 39 | **32** |

（prefix_len=120 时；A 版 reserve=64 且 skeleton ≥ 275 时 `allowed_prefix < 0` ⇒ 直接抛错）

🔴 **这正是「App 侧在 NPU 上逐字节复现参照」不成立的机理之一**：
**App 的 prompt 口径与本模块参照口径不是同一个** ⇒ 即使真用 App 代码跑，
NPU 转写也**未必**与 §86 参照逐字节相同。

### 2.5 B 版（App 的修法）实测结果 ✅

| 用例 | 结果 |
|---|---|
| NPU 长段（238/260/266 × reserve 32/64 × 有/无语言后缀） | ✅ **全部 OK**（不抛错） |
| NPU skeleton=321 | ✅ **RAISE ValueError**（保持「截断救不了就报错」） |
| GPU.0（512）全部用例 | ✅ **全部 OK**（GPU 档逻辑一字未动） |
| **前缀口径**：同一 audio_tok 下 reserve=32 与 64 的 `emb_len` | ✅ **一致**（238/260/266 三组都是 **320 == 320**）⇒ 与 handoff 口径对齐 |

🔴 **App 的修法与 ASR-065 handoff 契约一致**：
`allowed_prefix = limit - skeleton`（**不减 reserve**）＋
**只有 `skeleton > limit` 才报错** ＋ 总量检查
`prompt + reserve ≤ limit + NPUW_LLM_MIN_RESPONSE_LEN(64)`（= 384，KV 容量口径）。

### 2.6 归因：`git log -S`

```
git log -S "allowed_prefix = limit - skeleton" -- live_caption/asr06b_stateful_backend.py
⇒ dfb225e  APP-116/117/118 v2.5 = 全集 —— …（§217）
```

🔴 **「减 reserve」这个写法是 `dfb225e`（APP-118 接入 pml=320）引入的**
⇒ 属于 **App 接入 pml=320 时的实现口径**，**不是**本模块 ASR-065 参考实现
（`scripts/_asr065/asr065_backend.py`）的问题 —— 参考实现是
`if base_len > self._pml: raise`（**不减 reserve**），**与 handoff 一致**。

---

## 三、§2：撤回 §88 的两句结论

reviewer 指出的**成立**：

🔴 `_app120_asr_3mat.py` **L165-172 / L219-242** 用的是
**ASR 模块**的 `bk_run.run_stream` ＋ `asr065_backend.Asr065Runner`
⇒ **没有经过 App 的 `ASR06BStatefulBackend`**
⇒ §88 ④/⑤ 的「**App 侧接入在 NPU 上逐字节复现参照**」「**对 GPU.0 零回归**」
两句**不成立** ⇒ **本轮撤回**（§89 不回头改 §88 正文，按纪律记在此处）。

🔴 **补充一层**：即使改用 App 代码跑，**A 版**（交付版）因为
「减 reserve」⇒ **NPU 前缀口径与参照不同**（多砍 32–64 token，§二 2.4）
⇒ **App 侧 NPU 转写与 §86 参照大概率仍不会逐字节相同**。

🔴 **另需注意**：§88 的「GPU.0 与 ASR 模块 11-19 基准逐字节相同 ⇒ 零回归」
这一句**本身**是**ASR 模块内部**的前后自比（都是 ASR 模块代码路径），
所以它**仍然成立**；**不成立**的是把它当成「**App 接入**零回归」的证据。

🟡 **item 2 的补测（用 App 后端跑 §86 三素材，NPU 与 GPU.0 各一次）**：
**属 App 线程的交付面作业**（App 已有 `_app121_asr_app_3mat.py`，
且需先重建包 v1.1.1）⇒ **本模块不代做**（不重复跑同机推理）。

---

## 四、§4：其余条目的 ASR 侧说明

- **README 的「怎么改设备」示例正好推荐 `--asr-device NPU`** ⇒
  在 §1 修好并重签前，**NPU 示例确实不能给客户**（≥18.3 s 长段会停字幕）。
  ⇒ 属 App 的 README 改动面（§5 范围）。
- **§220 的「首字延迟 0.39 s」＝ TTS 状态行首包** vs **字幕出字延迟中位 303 ms**
  ⇒ 属 TTS/App 口径，**ASR 侧不持有这两个数**，不表态。
- **「机器被占」归因无证据（锁看门狗外来变动 = 0）** ⇒ 与 ASR 侧无关；
  🟢 但**与本模块纪律一致**：ASR 侧的锁自检（`lock_probe`）一直是
  「外来变动 0 ⇒ 归因不成立」的做法。

---

## 五、本轮动作清单（**本模块只改自己的文件**）

| # | 动作 | 文件 | 状态 |
|---|---|---|---|
| 1 | 只读复核脚本（**不做推理**） | `qwen3asr_06b/results/asr121_item1_check/_asr121_item1_check.py` | ✅ 已落盘（**仓库外**） |
| 2 | 同上产物 json | `qwen3asr_06b/results/asr121_item1_check/_asr121_item1_check.json` | ✅ 已落盘 |
| 3 | A 版基线副本（git HEAD 抽出） | `qwen3asr_06b/results/asr121_item1_check/_asr121_backend_head.py` | ✅ 已落盘 |
| 4 | **补正 handoff 契约**（新增 §三点三 ＋ §八 口径提醒） | `qwen3asr_06b/dev/asr065_handoff.md` | ✅ 已改（**18 295 B / LF 348 行**） |
| 5 | STATUS 正文 | `status/asr/STATUS_ASR.md` | ✅ §89（**归档 §88**） |
| 6 | 本明细 | `status/asr/notes/asr_s89.md` | ✅ 本文件 |
| 7 | 交付文件（`live_caption/`） | — | 🔴 **未动**（属 App；App 已在自有树里改） |
| 8 | 打包 | — | 🔴 **未打包** |

🔴 **仓库外产物说明**：`results/asr121_item1_check/` 在 `qwen3asr_06b`（仓库外）
⇒ 与 `results/asr162`/`asr163` **同一处置口径**（按纪律**未入库**）。

---

## 六、遗留 / 待决

- 🟡 **待用户/reviewer 决定 1 项（沿用 §88，本轮不变）**：
  「md5 逐字节相同」的口径改写为「**NPU 档 + OV 2026.4.1**」⇒ **仍未获批**；
  🔴 但经本轮 §二 2.4 的新证据，**即便标注了 NPU 档，「App 侧逐字节复现参照」
  仍需等 App 修完 §1 后用 App 代码实测**（reviewer item 2 的补测）。
- 🟡 **待用户决定 3 项**（沿用，数字以 §86/§87 为准）：整段离线是否加成交付路径；
  「RTF≈0.05」对外口径；🔴 encoder 静态上限 2400 mel 帧 = 24.0 s ⇒
  30 s 上下文**得重导出 encoder**（**放宽段长 ⇒ pml=320 必须重算**）。
- ⚠️ **待 App 侧落地**：§1 修法重签 + 重打 zip + 解压自检（§3/§5）；
  item 2 的 App 后端三素材 md5 实测。
- ⚠️ 沿用不变：ASR-028 换人点抽听（用户侧）；**ASR-042 第 3 步仍暂停**（ASR-047）
  ⇒ 本模块不跑 TTS；**B 机实测已关闭**（ASR-059）；**OV 2026.4.1 口径纪律**。
