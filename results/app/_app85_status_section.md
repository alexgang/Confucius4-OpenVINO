## §85 🔴🔴 **客户包 `NOTICE` / `THIRD_PARTY.md` 许可不实表述已修正（num2words 实为 LGPL-2.1，非 MIT；47 个 vendored 包署名全覆盖）＋ ASR 的 WeSpeaker 署名义务判定回告（包内不带权重 ⇒ 义务免除）**（2026-10-28 16:27）｜**本条已完成**｜**本条需等 reviewer 复核**

### §85.0 本节结论（一句话）

🔴 **查出一个真实合规缺陷并已修掉**：客户包 `NOTICE` 顶部声称「**所有组件均为 Apache License 2.0 授权**」，
而同文件下方又把 `num2words` 标为 `MIT` —— **两处都与包内实测矛盾**（`num2words-0.5.14` 实为 **LGPL-2.1**），
且两个文件合计只覆盖了包内 **47 个** vendored 分发包中的 **10 / 28 个** ⇒ **已按实测逐包重写为 47/47 全覆盖**；
⛔ **`NOTICE` 在 zip 内 ⇒ 本次修改会进入下一次打包，但本轮按 APP-031 不重打 zip**；
✅ **ASR 的 WeSpeaker CC BY 4.0 署名义务判定为「免除」（包内不带权重）⇒ 已回告 ASR**。

### §85.1 🔴 缺陷本体（实测取证，不是推测）

**取证方法**：直接读包内 `python/Lib/site-packages/<包>.dist-info/METADATA` 的
`License` / `Classifier: License` 字段，并与各包自带的 `LICENSE` / `COPYING` / `licenses/` **正文交叉核对**。

#### §85.1.1 缺陷①：顶部「所有组件均为 Apache License 2.0」不实

原 `NOTICE` 第 4–5 行原文：

```
本软件包含或依赖以下第三方组件。所有组件均为 Apache License 2.0 授权，
可自由再分发。
```

⇒ **实测包内 47 个 vendored 分发包的许可并非统一 Apache**，其中至少包含
**LGPL-2.1（`num2words`、`soxr`）、MPL-2.0（`certifi`）、PSF-2.0（`defusedxml`、`typing_extensions`）、
ISC（`librosa`）、MIT（`urllib3`、`tqdm` 之一等）、BSD 变体、HPND（`pillow`）、MIT-0（`cffi`）**。

⚠️ **这个表述的危害是实质性的**：它会让拿到包的接收方**误以为可以按 Apache-2.0 条款统一处置**，
而实际上 LGPL-2.1 组件有**独立的再分发与反向引用义务** ⇒ 属**合规风险**，不只是文字瑕疵。

#### §85.1.2 缺陷②：`num2words` 的许可写错（MIT → 实为 LGPL-2.1）

原 `NOTICE` 第 45 行：`num2words           MIT`

**实测（双重取证）**：

| 取证点 | 原始内容 |
|---|---|
| `num2words-0.5.14.dist-info/METADATA` | `License: LGPL` |
| 同上 `Classifier:` | `License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)` |
| 同上 `License-File:` | `COPYING` |
| `num2words-0.5.14.dist-info/COPYING` 首行 | `GNU Lesser General Public License` / `Version 2.1, February 1999` |

⇒ **MIT 是错的，LGPL-2.1 是对的**。

#### §85.1.3 缺陷③：署名覆盖率严重不足

| 文件 | 原覆盖 | 包内实际 dist-info | 缺口 |
|---|---|---|---|
| `NOTICE`「运行时 Python 依赖」段 | **10** 个 | **47** | **缺 37** |
| `THIRD_PARTY.md` 表格 | **28** 个（且**完全没有 `num2words`**） | **47** | **缺 19** |

⇒ 已补齐为 **47/47**，并为每个包标注**随包许可证全文的真实路径**。

#### §85.1.4 附带查明的事实（不是缺陷，但此前无人记录）

- **46 / 47** 个包自带 LICENSE/COPYING 文件；**唯一例外是 `tokenizers 0.22.2`**（dist-info 内**无**任何许可证文件）
  ⇒ 已在 `NOTICE` 中**显式标注**该缺失，并指明其许可标识来自 METADATA 的
  `Classifier: License :: OSI Approved :: Apache Software License`。
- `numpy` 除 BSD-3-Clause 外还带 0BSD / MIT / Zlib / CC0-1.0（`licenses/` 下 **16** 个嵌套许可文件）；
  `openvino` 带 oneDNN / oneTBB 第三方条款（`licensing/` 下 3 个文件）；
  `openvino-genai` / `openvino-tokenizers` 各带 `third-party-programs.txt`；
  `llvmlite` 带 `LICENSE.thirdparty`（LLVM Apache-2.0 with LLVM-exception）；`numba` 带 `LICENSES.third-party`。
  ⇒ 这些**多许可**情形已在 `NOTICE` 与 `THIRD_PARTY.md` 中**如实标注**，不再压成单一 SPDX。

### §85.2 ✅ 验收（`results/app/app124_notice_license_audit.py`）：**12 PASS / 0 FAIL**

（零推理、零 GPU、零 NPU、不调 MiniMax、**只读核对**，不改客户包任何文件）

| 判据 | 内容 | 结果 |
|---|---|---|
| G1 | `NOTICE` 表格覆盖包内**全部 47** 个 dist-info | PASS |
| G2 | 每个包**恰好一行**（无重复、无遗漏） | PASS |
| G3 | `NOTICE` 版本号 == 各包 `METADATA` 的 `Version`（逐包核对） | PASS |
| G4 | `NOTICE` 标注的**随包许可证全文路径全部真实存在** | PASS |
| G4b | 被标注为「未自带许可证文件」的包**确实没有** | PASS（`tokenizers` = 0） |
| G5 | `num2words` = LGPL-2.1（**METADATA + COPYING 双重取证**，且 `NOTICE` 已改正） | PASS |
| G6 | `NOTICE` 不再声称「所有组件均为 Apache License 2.0」 | PASS |
| G7 | `NOTICE` **表格行**里 `num2words` 许可列不再写 MIT（行级提取） | PASS |
| G8 | `NOTICE` 的许可标识与包内 METADATA/Classifier **无冲突** | PASS |
| G9 | `THIRD_PARTY.md` 覆盖**全部 47** 个 dist-info | PASS |
| G10 | `THIRD_PARTY.md` 的 `num2words` = LGPL | PASS |
| G11 | 【自检】把 `NOTICE` 的 `num2words` 改成 MIT ⇒ G5 判据**必须 FAIL** | PASS |

证据：`results/app/app124_notice_license_audit_evidence.json`（2 811 B @ 16:26:59，
SHA256 `dae03752d4e71227f10e22e87331856a5ec59246ecfe23c48b6b87faea13bcd0`）。

### §85.3 ✅ 反证（`results/app/app125_notice_license_counterproof.py`）：**10 PASS / 0 FAIL**

**反证基准 = 本轮修正前的实际原文**（把修正前的 `NOTICE` / `THIRD_PARTY.md` 片段**内嵌**进反证脚本，
**不用 HEAD** —— HEAD 若已修好，反证会落空 ⇒ 假证据，§31 教训）。

| 判据 | 内容 | 结果 |
|---|---|---|
| R1-1 | 修正前 `NOTICE` ⇒ **G6 必须 FAIL**（缺陷①曾真实存在） | PASS |
| R1-2 | 修正前 `NOTICE` ⇒ **G1 必须 FAIL**（表格 0 行 vs 47） | PASS |
| R2-1 | 修正前 `THIRD_PARTY.md` ⇒ **G10 必须 FAIL**（无 `num2words` 行） | PASS |
| R3-G6/G7/G1/G10 | **当前实文件** ⇒ 四条判据**必须全 PASS**（证明判据非恒 FAIL） | PASS |
| R4-1 | 把当前 `NOTICE` 的 `num2words` 改成 MIT ⇒ **G7 必须 FAIL** | PASS |
| R4-2 | 把当前 `THIRD_PARTY.md` 的 `num2words` 改成 MIT ⇒ **G10 必须 FAIL** | PASS |
| R5-1 | 「包内确有 47 个 dist-info」这一**前提本身可被验证** | PASS |

证据：`results/app/app125_notice_license_counterproof_evidence.json`（2 080 B @ 16:27:00，
SHA256 `cef3d24c1669cbf8f9dc4ec0aa1477e86fb1c98050217aa86551023142d01061`）。

#### §85.3.1 🔴 反证过程中抓到的**判据自身缺陷（2 处，均已修）**

⚠️ **这是本节最值得记的部分** —— 判据自己也会骗人：

1. **G7 第一版过弱**（相邻正则 `num2words\s*\S*\s*MIT`）——
   表格行实际是 `| num2words | 0.5.14 | MIT | ...` ⇒ **相邻正则匹配不到**
   ⇒ 把该行许可改成 MIT 后判据**仍然 PASS（假通过）** ⇒ 被 R4-1 反证抓出
   ⇒ 改为**行级提取许可列**。
2. **G7 第二版过严** —— 把说明句「…的许可经实测确认为 **LGPL-2.1**，**不是 MIT**。」也误判为 FAIL
   ⇒ 改为**只判表格行**（以 `|` 开头且能解析出许可列）。
3. 附带：**G2/G3/G4 的包名键未与 dist-info 归一化对齐**（`openvino-genai` 被首段切分压成 `openvino`、
   `charset_normalizer` 与 `charset-normalizer` 不匹配）⇒ 首跑 FAIL ⇒ 改为
   **去版本号段 + 下划线转连字符 + 小写**的归一化 ⇒ 再跑全 PASS。

⇒ 📌 **教训**：**审计脚本「跑出 PASS」不等于「审计脚本是对的」** ⇒ 必须做**双向反证**
（修正前 FAIL + 修正后 PASS + 沙盒注入 FAIL）。本节两处判据缺陷都是这样抓出来的。

### §85.4 ✅ ASR 的 WeSpeaker 署名义务判定（**免除**）＋ 回告

#### §85.4.1 判定依据（可复核实测）

在 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6` 全目录实测：

| 检查项 | 结果 |
|---|---|
| `find . -iname "*wespeaker*" -o -iname "*resnet34*"` | **0 命中** |
| `find . \( -name "pytorch_model.bin" -o -name "*.pt" -o -name "*.pth" -o -name "*.ckpt" -o -name "*.safetensors" \)` | **0 命中** |
| `site-packages/` 内 `torch` / `pyannote` / `speechbrain` | **均不存在** |

⇒ ASR 来文 `NOTICE_asr_to_app_wespeaker_license_20261028.md` §五.3 的分支判定：
**「如果最终决定不带 ⇒ 署名义务可免除（届时请回告 ASR 模块）」⇒ 走「不带」分支 ⇒ 义务免除。**

#### §85.4.2 来文 §四「绝不把 wespeaker 向量传给 TTS 做克隆音色」—— App 侧**未被违反**

| 环节 | 实测实现 | 接触 wespeaker？ |
|---|---|---|
| 克隆向量（CPU 路线） | `live_caption/tts_engine.py:891` → `eng.extract_speaker_embedding(wav)`（**BabelVox** x-vector） | **否** |
| 克隆向量（CUDA 路线） | `live_caption/tts_cuda.py` / `tts_cuda_sidecar.py` → `set_ref` + `ref_audio` | **否** |
| ASR 说话人聚类 | `pyannote/segmentation-3.0` **旁路**，只识别说话人、不阻塞定稿、不参与断句 | 是（仅 ASR 侧，且不在本包内） |

⇒ 克隆向量**只来自 Qwen3-TTS 自己的 x-vector**，与来文限制**完全一致**。

#### §85.4.3 回告文件

`C:\Users\Trekker-PTL\shared\NOTICE_app_to_asr_wespeaker_license_reply_20261028.md`
（**5 605 B @ 2026-10-28 16:27:40**，SHA256 `b37b30d0a2e3a1d44e47e0308d6eaff1ae317b1ead16de859384bc9d559ddf42`）

内容要点：① 结论「署名义务免除」；② 判定依据（§85.4.1 的三条实测 + §85.4.2 的代码路径表）；
③ 对 ASR 的 4 项请求（更新 STATUS 头部第 ④ 项的「App 侧未确认」/ 若后续要带权重**必须先回告**/
运行时加载场景由 ASR 自行判定 / 确认 App 从未把「wespeaker 已可交付」当既定事实）；
④ 同时告知 ASR：App 已**独立修正**了 `NOTICE` 的许可不实表述（与 WeSpeaker 无关，但影响同一文件）。

### §85.5 🔴⚠️ **交付影响（必须说清）**

- 🔴 **`NOTICE` 与 `THIRD_PARTY.md` 都在 zip 内**（`Confucius4_LiveCaption_v1.6/NOTICE`）
  ⇒ **本次修改会进入下一次打包**。
- ⛔ **本轮未重打 zip** —— APP-031 明文「**三项做完后合在一起重打一次包**」，
  而 APP-027 的 **V4（用户实听）未做** ⇒ 不满足合打条件 ⇒ **不重打**。
- ⛔ 按 §66 口径 **不写「已交付」**。准确表述：
  **代码侧已入库、已同步到包目录；zip 未重打**。
- ⚠️ **本轮未跑 `verify_pkg_zip.py`、未开 FTP、未跑 `publish_ftp.py`**。

### §85.6 ✅ 本轮改动文件清单（App 侧）

| 文件 | 类型 | 字节 | SHA256 |
|---|---|---|---|
| `Confucius4_LiveCaption_v1.6/NOTICE` | 改（客户包，非 git 跟踪） | 8 289 | `11cda5c0a41660390cfc1b0888ca07cc7b0e8358db2938d72d1869d44f5ace7e` |
| `Confucius4_LiveCaption_v1.6/THIRD_PARTY.md` | 改（客户包，非 git 跟踪） | 3 310 | `b00115217aa819b8268eeaacd5ca3851e02a7e17cfd9885bc0aa29fd6366850e` |
| `shared/NOTICE_app_to_asr_wespeaker_license_reply_20261028.md` | 新建（跨模块回告） | 5 605 | `b37b30d0a2e3a1d44e47e0308d6eaff1ae317b1ead16de859384bc9d559ddf42` |
| `results/app/app124_notice_license_audit.py` | 新建（审计，12 判据） | 11 960 | `9872dcec949958ac4a0262a387141a5a8405fee98db3bf2de8201ca401d9b7e5` |
| `results/app/app124_notice_license_audit_evidence.json` | 新建 | 2 811 | `dae03752d4e71227f10e22e87331856a5ec59246ecfe23c48b6b87faea13bcd0` |
| `results/app/app125_notice_license_counterproof.py` | 新建（反证，10 判据） | 6 189 | `ad6f4e9252b32ad18178071213d5f3ccfce6cb87d682554af33e875e36fa3b79` |
| `results/app/app125_notice_license_counterproof_evidence.json` | 新建 | 2 080 | `cef3d24c1669cbf8f9dc4ec0aa1477e86fb1c98050217aa86551023142d01061` |
| `status/app/STATUS_APP.md` | 追加 | — | 本节 §85（**只追加，未改旧章节**） |

### §85.7 ⛔ 待 reviewer 裁定 / 待用户确认

1. 🔴 **§85.1 的「所有组件均为 Apache License 2.0」表述是否曾进入过已交付的 zip** ——
   若 v1.6 的 zip（11 218 087 123 B / SHA256 `907a1caa…2589f`）已含旧 `NOTICE`
   ⇒ **该 zip 分发出去时即带不实许可声明** ⇒ **是否需要重新打包并重新分发，请 reviewer 裁定**
   （App 不自行决定，因为重打 zip 受 APP-031 的合打约束约束）。
2. 🔴 **`tokenizers 0.22.2` 无随包许可证文件** —— 是否需要在打包时**补一份** Apache-2.0 全文进 zip？
   （当前做法：在 `NOTICE` 中显式标注缺失 + 给出官方全文链接。）
3. 🔴 **`pillow` 的许可标识** —— `METADATA` 无 `License` 字段、`Classifier` 也无 License 项，
   其 `licenses/LICENSE` 正文含 Apache-2.0 / MIT / BSD / GNU 段落的**多许可组合**（HPND 主体），
   本轮按 **HPND** 标注 ⇒ **是否需要按更细的多许可口径展开，请 reviewer 裁定**。
4. 🔴 **`soxr` 与 `llvmlite` / `numba` / `numpy` / `openvino` 的第三方条款** ——
   本轮已在 `NOTICE` / `THIRD_PARTY.md` 中**指明随包路径**（如 `licensing/`、`LICENSES.third-party`）
   ⇒ **是否需要在 `NOTICE` 正文中逐条摘录其关键义务，请 reviewer 裁定**。
5. 🔴 **§84 的待裁定项仍然有效**：V3-CER（MiniMax 回转写）/ V3-CAMPPlus（余弦）/
   V4 用户实听 / CUDA 组无「预设 A 对照」是否补跑 / NPU 前 6 句是否算缺陷 / §83.5 的 4 项。
6. ⛔ **zip 未重打** ⇒ **不写「已交付」**（准确表述：**代码侧已入库、已同步到包目录；zip 未重打**）。
7. 🔴 **MT notice 15 §3.4 的真实时序「草稿行计数」端到端证据缺口** ——
   `hy_bench` 侧建议 App 在真实时序下补跑 ⇒ **仍是 App 侧遗留项，本轮未处理**。

### §85.8 头部字段

- `last_ack` = **APP-033**（**保持不变**：本轮**无新 reviewer 纠偏条目** ⇒ 无编号可 ack；
  §84 / §85 都是对**已 ack 的历史条目**（APP-027 / ASR-023 的许可义务）做遗留事项的补做）。
- 「更新时间」= **2026-10-28 16:27**（`Get-Date -Format "yyyy-MM-dd HH:mm"` **实测值**，非推算）。
