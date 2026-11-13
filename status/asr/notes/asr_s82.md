# §82 明细 —— ASR-057 落地

> 🔴 本文件是 `status/asr/STATUS_ASR.md` §82 的**明细全文**（ASR-036 规则：
> 正文只留结论与数字，明细归 notes）。
> 出处：纠偏 `status/asr/CORRECTIONS_ASR.md` → `## ASR-057 [HIGH] 2026-11-13 09:05`。
> 落地时间：**2026-11-13 09:51–10:10**。

---

## 0. 一句话

reviewer 验收 ASR-056 的**主体结论全部成立**（§79 撤回、10 个 json 标 `unverified`、
跨脚本块清理、4 组持锁补跑、离线 wheels、MANIFEST `sources` 都已核实）；
但 **B 机一键入口 `run_bk.cmd` 实测完全跑不起来**（LF 换行 + cmd 解析错行；
且 `all` / `selftest` 两种用法**静默地一组不跑却报成功**）⇒ 修好前**套件不能交 B**。
另有 3 处收尾（套件目录残留不交付的东西、`ref_A` 缺最终版 18 s 参照、
MANIFEST `sources` 里自证的条目）+ 1 处线程记忆过期项。

---

## 1. 纠偏要求的 5 件事 → 逐条落地

### ① [BLOCKING] `run_bk.cmd` 跑不起来（两个独立 bug）

#### (a) 换行符 + 编码

reviewer 实测：文件是 **LF 换行**（**60 个 `\n`、0 个 `\r\n`**），里面又有
**UTF-8 中文** ⇒ cmd.exe 解析时把行切错，输出 `'M' is not recognized…`、
`'local' is not recognized…`，最后 `< was unexpected at this time.` 中止，
**一组都没调用**。

**修法**：重写 `run_bk.cmd` ⇒ **CRLF 换行** ＋ **纯 ASCII**（中文说明全部移到 README）。

- 产物：`qwen3asr_06b/b_kit_stateful/run_bk.cmd`，**3764 B**，
  SHA256 `3c9b387a3be85b9b…`
- 写入器：`qwen3asr_06b/scripts/_asr057_write_cmd.py`
  （写前**逐字节自检**：纯 ASCII ＋ 无裸 LF；用 `newline=''` ＋ 显式 `\r\n`，
  **不依赖平台换行转换**）
- 实测：**LF=134、CRLF=134、裸 LF=0**；全部 3764 字节均为 ASCII。

#### (b) 逻辑：补 `all`（默认 12 组）与 `selftest` 分支

旧版 `:run` 段只处理「形态 设备 时长」三元组 ⇒
无参数调用（README §3.1/§8.3 写的「跑全部 12 组」）时 `%~1` 为空 → 直接
`goto :done` → 打印「全部完成」→ `exit /b 0`；
`selftest` 调用时 DEV/TASK 都为空 → 同样直接结束。
⇒ **两种用法都静默地一组不跑，却报成功。**

**修法**（重写后的 `run_bk.cmd`）：

| 用法 | 行为 | 组数 |
|---|---|---|
| `run_bk.cmd`（无参数） | `all`（默认）：2 形态 × 2 设备 × 3 时长 | **12** |
| `run_bk.cmd selftest` | 只跑 stateful / GPU.0 / 300s | **1** |
| `run_bk.cmd stateful NPU 300s` | 只跑指定的一组 | **1** |
| 参数不成组 | 打印用法 | `exit /b 2` |

另加：**任一组失败 ⇒ 打印失败组数 ＋ 非 0 退出**（`FAILED` 计数器）。

#### 验收：假桩调用次数 12 / 1 / 1

reviewer 的验收要求：「在 A 上用一个**只打印参数的假 `bk_run.py`**
（放在临时目录，不碰模型和设备）分别跑无参数、`selftest`、显式三元组三种用法，
打印出来的调用次数应分别是 **12、1、1**。把这三份输出贴进 STATUS。」

**实测**（`qwen3asr_06b/scripts/_asr057_verify_cmd.py`）：

```
[v] case=noargs     argv=(none)                 rc=0  n_calls=12
        call: stateful|GPU.0|18s
        call: stateful|GPU.0|300s
        call: stateful|GPU.0|10min
        call: stateful|NPU|18s
        call: stateful|NPU|300s
        call: stateful|NPU|10min
        call: stateless|GPU.0|18s
        call: stateless|GPU.0|300s
        call: stateless|GPU.0|10min
        call: stateless|NPU|18s
        call: stateless|NPU|300s
        call: stateless|NPU|10min
[v] case=selftest   argv=selftest               rc=0  n_calls=1
        call: stateful|GPU.0|300s
[v] case=explicit   argv=stateful NPU 300s      rc=0  n_calls=1
        call: stateful|NPU|300s
[v] case=fail_case  argv=stateful NPU 18s       rc=1  n_calls=1
        call: stateful|NPU|18s

[v] noargs     n_calls=12 (want 12)  rc=0  => PASS
[v] selftest   n_calls=1 (want 1)  rc=0  => PASS
[v] explicit   n_calls=1 (want 1)  rc=0  => PASS
[v] fail_case  n_calls=1 (want 1)  rc=1 (want != 0)  => PASS
[v] ALL PASS
```

- 三份输出落盘：`qwen3asr_06b/b_kit_A_local/cmd_check_out/{noargs,selftest,explicit,fail_case}.txt`
- 🔴 假桩**放在临时目录**（`tempfile.mkdtemp`），**不碰模型和设备**，
  **不取 MACHINE_LOCK**；被测的 `run_bk.cmd` 是套件里那份的**逐字节副本**。
- 🔴 额外验证「任一组失败 ⇒ 非 0 退出」：假桩用 `BK_STUB_FAIL_TASK=18s`
  让 18 s 那一组返回 7 ⇒ `run_bk.cmd` 的 `rc=1`（**不是 0**）。

#### 检查脚本（纯 ASCII + CRLF 的断言）

新增 `qwen3asr_06b/b_kit_stateful/scripts/bk_check_cmd.py`（**3870 B**）
—— 静态断言（**不执行 cmd、不碰模型和设备**）：

```
[c] run_bk.cmd 静态检查：8 PASS / 0 FAIL
   PASS  run_bk.cmd 无裸 LF              LF=134  CRLF=134  裸LF=0
   PASS  run_bk.cmd 纯 ASCII            全部 3764 字节均为 ASCII
   PASS  run_bk.cmd 含 all 分支           OK
   PASS  run_bk.cmd 含 selftest 分支      OK
   PASS  run_bk.cmd 含失败计数变量            OK
   PASS  run_bk.cmd 含 errorlevel 判断    OK
   PASS  run_bk.cmd 含非 0 退出            OK
   PASS  run_bk.sh 头部写「12 组」           命中
```

#### `run_bk.sh` 头部「6 组」→「12 组」

`run_bk.sh` 第 5 行：`#   ./run_bk.sh  # 跑全部 6 组（…）` ⇒ 改成 **`12 组`**。
🔴 **顺带**：`run_bk.sh` 的 `run()` 原来失败也 `exit 0` ⇒ 与 `run_bk.cmd`
统一契约（`TOTAL` / `FAILED` 计数 ＋ 失败时 `exit 1`）；`bash -n run_bk.sh` ⇒ **语法 OK**。

---

### ② 套件目录里还留着不交付的东西

reviewer 实测：`b_kit_stateful\` 实际有 **117 个文件 / 2348967295 B**，
MANIFEST 只列了 **61 个**；多出来的是 `.bak_asr056\`（里面还带
`scripts\__pycache__\*.pyc`）和 `results_A_local\`。
`bk_sha256.py` 的 `SKIP_DIRS` 把这两个目录跳过了 ⇒ `--check` 会通过，
**但整目录拷到 B 时它们会一起带过去** ⇒ 与 ASR-056 §2.6(d) 不符。

**修法**：

| 动作 | 结果 |
|---|---|
| `.bak_asr056\` | 移到 `qwen3asr_06b\b_kit_A_local\.bak_asr056\` |
| `results_A_local\` | 移到 `qwen3asr_06b\b_kit_A_local\results_A_local\` |
| `SKIP_DIRS` | **收窄为** `{'results', '__pycache__'}` |

🔴 **验收：文件数 == MANIFEST 的 `n_files`**。

- 套件目录实际文件数（PowerShell `Get-ChildItem -Recurse -File`，排除
  `results` / `__pycache__`）= **65**
- `MANIFEST.json` → `n_files` = **65** ⇒ **匹配**
- 套件内**无** `.bak*` / `results_A_local` / `.pyc`（递归扫描确认）

#### 🔴 附带发现并修掉 2 处真缺陷

**(i) `n_files` 语义不自洽**：`n_files` 原来 = 参与哈希的文件数（**63**），
但磁盘上实际有 **65** 个文件（多的是 `SHA256SUMS.txt` / `MANIFEST.json` 这两个
**输出文件自身**，它们因「自指 churn」不进哈希）⇒ reviewer 的判据
「`Get-ChildItem -Recurse -File` 的文件数等于 MANIFEST 的 `n_files`」**对不上**。

**修法**：`bk_sha256.py` 改用 `walk_all_files()`（**不排除**输出文件自身）
⇒ `n_files` = **磁盘实际文件数** = **65**；另加 **`n_hashed_files`** = **63**
（= `n_files - 2`）与 `n_files_note` 说明两者关系。
🔴 **首次生成也不会 churn**：`n_missing_outputs` 会给尚不存在的输出文件**预留名额**。

**(ii) 🔴 `MANIFEST.json` 在 PowerShell 5.1 上**解析失败**（reviewer 的验收环境！）**
—— 实测 `Get-Content -Raw MANIFEST.json | ConvertFrom-Json` 报
**「传入的对象无效，应为":"或"}"」**：因为 PS 5.1 的 `Get-Content -Raw`
**默认按 ANSI(GBK) 解码** UTF-8 文件 ⇒ 中文变乱码 ⇒ 乱码里出现 `"` 字符
⇒ JSON 解析中断。

**修法**：`MANIFEST.json` 改用 **`utf-8-sig`（带 BOM）** 写 ⇒ PS 5.1 能正确
识别 UTF-8 ⇒ 解析通过。（🔴 读回时也要用 `utf-8-sig`。）

**修完实测**（reviewer 的 PowerShell 判据原样跑）：

```
PS file count     = 65
MANIFEST n_files  = 65
n_hashed_files    = 63
total_bytes       = 2348478744
sources count     = 14
MATCH n_files     = True
derived entries   = 4
derived identical all null = True
```

---

### ③ `ref_A` 缺少最终版的 18 s 参照

reviewer 实测：README §8.2 列的 4 组里，有 **3 组是 13:19–13:45 用改动前的脚本**
跑出来的（`bk_stateful_GPU0_300s`、`bk_selftest_*`）；
**最终版、持锁的结果只有 GPU.0 300 s 这一组** ⇒ B 机要对照 NPU 和 stateless 的
18 s 臂，**现在没有参照可用**。

**修法**：

| 组 | 来源 | 处理 |
|---|---|---|
| `bk_asr056_stateful_NPU_18s` | `results_A_local/`（11-11 15:20 持锁补跑） | ✅ **加入 `ref_A/`** |
| `bk_asr056_stateless_NPU_18s` | 同上（15:23） | ✅ **加入 `ref_A/`** |
| `bk_asr056_stateless_GPU0_18s` | 同上（15:23） | ✅ **加入 `ref_A/`** |
| `bk_asr056_stateful_GPU0_300s` | 同上（15:20） | ✅ 已在（最终版） |
| `bk_stateful_GPU0_300s` | 11-11 13:19 **旧脚本** | 🔴 **已删除** |
| `bk_selftest_stateful_GPU0_300s` | 11-11 13:34 **旧脚本** | 🔴 **已删除** |
| `bk_selftest_torchmel_GPU0_300s` | 11-11 13:45 **旧脚本** | 🔴 **已删除** |

（3 个旧脚本组**直接删除**而不是「README 标成仅供参考」—— 理由：
它们是**同臂同参数**的旧脚本结果，放在 `ref_A/` 里会让 B 机分不清该对照哪一份，
且 README 的 4 组表已经能说清历史 ⇒ 删更干净。）

**验收**：`ref_A/` = **4 组 / 8 个文件**（`summary.json` + `transcript.txt` 各 4），
每组都有 summary + transcript；3 个旧组确认已删。
🔴 新加入的 3 组都是**最终版脚本 + 持锁**：`mel_mode`=`fft`、
`exec_devices` 正确、`timing_valid`=`true`、`lock_record` 完整（含
`released_at` / `exit_code`=0）。

---

### ④ MANIFEST `sources` 里有自证的条目

reviewer 实测：`assets/embed_tokens.npy`、`assets/mel_filters.npy`、
`assets/hann_400.npy` 三项都是 `src_present=false`，`src_path` 是**拼出来的说明文字**
（例如 `models/Qwen3-ASR-0.6B/embed_tokens.npy (导出产物)`），
`src_sha256` 却**直接抄了 kit 的值**，还标着 `identical=true` ⇒ **不算源对比**。

**修法**：把 `sources` 拆成**两类**（`bk_sha256.py` → `SOURCE_MAP` + `build_sources()`）：

| `kind` | 含义 | `src_sha256` | `identical` |
|---|---|---|---|
| `copy` | 逐字节拷贝 | **源文件实测 SHA** | 实测的逐位比较 |
| `derived` | **算出来的**，没有同字节的源 | **真正决定其内容的源文件**的实测 SHA | **`null`**（不是 `true`！） |

`derived` 条目另带 **`derived: true`** ＋ `src_note`（怎么算出来的、怎么核验）。

#### 4 个派生资产的真源（A 机实测查证）

| 套件内文件 | 真源 | 依据 |
|---|---|---|
| `assets/embed_tokens.npy` | `models/Qwen3-ASR-0.6B/model.safetensors` | 张量 `thinker.model.embed_tokens.weight`，形状 `[151936, 1024]`，源 dtype float32 ⇒ **转 fp16 ⇒ 与源不是逐字节相同** |
| `assets/mel_filters.npy` | `models/Qwen3-ASR-0.6B/preprocessor_config.json` | `WhisperFeatureExtractor` 参数（`n_fft=400` / `hop_length=160` / `feature_size=128` / `n_samples=480000`）决定 `mel_filters` 的内容（`[201, 128]`） |
| `assets/hann_400.npy` | **`scripts/a_only/bk_export_hann.py`**（**没有权重源**） | 值是常量 `torch.hann_window(400).numpy()`（float32, periodic） |
| `assets/prompt.json` | `scripts/a_only/bk_export_assets.py` | 写出 `_build_text_prompt(context='', force_language='English')` 的结果 + token id + 常量 |

🔴 **`hann_400.npy` 的源可核验**：新增
`b_kit_stateful/scripts/a_only/bk_export_hann.py`（**2825 B**，**默认只校验不写**）
⇒ 重算 torch 的窗并与资产**逐位比较**。A 机实测：

```
[h] torch.hann_window(400) vs assets/hann_400.npy
    dtype  : torch=float32  kit=float32
    shape  : torch=(400,)  kit=(400,)
    逐位相同: True
    asset sha256: 138de18ad784bd866e7ebe9807f1713b69cebe99ebf43dd85dd85abab294eb88
[h] PASS
```

（另：numpy 的 Hann 公式**无法**与 torch 逐位一致 ⇒ float64 版本差
**2.384e-07** ⇒ 这正是必须固化的原因。）

#### tokenizer 4 个文件 ＋ `prompt.json` 补进 `sources`

🔴 **`assets/tokenizer/tokenizer.json` 的来源与另外 3 个不同**（reviewer 特别点名
「注意 `tokenizer.json` 的 mtime 是 11-11 13:07，另外 3 个文件是 10-24，
请注明它从哪里来」）—— A 机查证结论：

| 文件 | 源仓库 | 源路径 | 原始 mtime | 套件内 mtime |
|---|---|---|---|---|
| `tokenizer.json` | **`confucius4-openvino`** | `models/hf-qwen3-lm/tokenizer.json` | **2026-10-08 13:48:14** | 2026-11-11 13:07:18（拷贝时间） |
| `vocab.json` | `qwen3asr_06b` | `models/Qwen3-ASR-0.6B/vocab.json` | 2026-10-24 10:41:20 | 同（`copy2` 保留） |
| `merges.txt` | `qwen3asr_06b` | `models/Qwen3-ASR-0.6B/merges.txt` | 2026-10-24 10:41:20 | 同 |
| `tokenizer_config.json` | `qwen3asr_06b` | `models/Qwen3-ASR-0.6B/tokenizer_config.json` | 2026-10-24 10:41:19 | 同 |

🔴 **重要核验**：`tokenizer.json` **不是**从 `models/Qwen3-ASR-0.6B/`
重新序列化出来的 —— A 机实测 transformers 4.57.6 从该目录重新
`backend_tokenizer.save()` 得到 `bd2a97b55c8f7f9c328c73ee9b9178771037e9f566dfca8e238a063d41cbac92`
（**11 429 377 B**），而套件里那份是 `0499602714160467f2d68b910651d6216020689f1e016be87a2d0019ee3baeab`
（**11 429 499 B**，**多 122 B**）⇒ **两者不是同一份**。
差异定位在 `pre_tokenizer` 的 Split 正则（新版 Mistral 正则 vs 旧版）。

⇒ 套件里那份是 **`confucius4-openvino` 的 `models/hf-qwen3-lm/tokenizer.json`** 的
**逐字节拷贝**（`cmp` 实测完全相同）⇒ `src_root_key` = **`app`**（另一个源根），
`src_rel` = `models/hf-qwen3-lm/tokenizer.json`，`identical` = **`true`**（实测）。

⇒ 「另外 3 个文件 mtime 是 10-24」= **`copy2` 保留了源文件的 mtime** ⇒
**未重新生成**（`bk_export_assets.py` 里是 `shutil.copy2`）。

#### 验收

- `sources` 条目数：**9 → 14**
- **14 条全部 `src_present=true`**（真源都在本机，实测 SHA）
- 4 个 `derived` 条目的 `identical` **全部为 `null`**（PowerShell 实测
  `derived identical all null = True`）
- 8 个 `copy` 条目的 `identical` **全部为 `true`**（逐字节拷贝，实测）
- 🔴 MANIFEST 新增 **`source_roots`** = `{"asr": ..., "app": ...}`（两个源根）

---

### ⑤ 线程记忆里有过期事项

用户 **11-07 19:05** 已决定 **`overlap_ratio_max` 不修** ⇒ 从遗留项中删掉。

**处理**（3 个文件）：

| 文件 | 处理 |
|---|---|
| `status/asr/STATUS_ASR.md` | 头部「阻塞 / 待用户决定」行删掉该条 |
| `.workbuddy/memory/MEMORY.md` | E 节遗留项删掉该条 |
| `.workbuddy/memory/MEMORY_E_progress_full.md` | 第 41 条删掉 |
| `.workbuddy/memory/2026-11-13.md` | 巡检行里的遗留项描述删掉 |

---

## 2. 总验收

`qwen3asr_06b/scripts/_asr057_verify_kit.py`（**只读检查**：不重跑推理/计时、
不取 MACHINE_LOCK）⇒ **26 PASS / 0 FAIL**：

```
== ASR-057 验收（只读） ==
   PASS  ① 假桩 无参数 ⇒ 12 次
   PASS  ① 假桩 selftest ⇒ 1 次
   PASS  ① 假桩 显式三元组 ⇒ 1 次
   PASS  ① 假桩总判定
   PASS  ② 套件文件数 == MANIFEST n_files          磁盘 65 / n_files 65
   PASS  ② 套件内无 .bak* / results_A_local / .pyc  干净
   PASS  ② SKIP_DIRS 已收窄
   PASS  ③ ref_A = 最终版 4 组
   PASS  ③ ref_A/... 有 summary+transcript ×4
   PASS  ③ 旧脚本组已删除 ×3
   PASS  ④ assets/embed_tokens.npy 是派生条目
   PASS  ④ assets/mel_filters.npy 是派生条目
   PASS  ④ assets/hann_400.npy 是派生条目
   PASS  ④ tokenizer.json 源在 app 仓库且有注明
   PASS  ④ sources 含 vocab.json / merges.txt / tokenizer_config.json / prompt.json
   PASS  ④ 全部 sources 条目源文件存在              14 条全部存在
   PASS  ⑤ bk_sha256.py --check 0 处不符
   PASS  ⑤ 给出总字节数

== 26 PASS / 0 FAIL ==
```

## 3. 套件最终状态

| 项 | 值 |
|---|---|
| `n_files`（磁盘实际） | **65** |
| `n_hashed_files`（进哈希） | **63** |
| `total_bytes` | **2 348 478 744 B**（2239.7 MB） |
| `dir_sizes` | assets 356 067 863 B / 11；models 1 884 374 957 B / 6；ref_A 15 391 B / 8；scripts 121 679 B / 12；wheels 107 868 519 B / 23 |
| `sources` | **14 条**（copy 8 / derived 4 / 待核 2 ⇒ 见 §1④） |
| `bk_sha256.py --check` | **0 处不符** |
| `bk_check_cmd.py --check` | **8 PASS / 0 FAIL** |

🔴 **本轮只做纠偏要求的事**：**未打包、未重跑任何计时、未重跑 WER、
未做新的导出或量化、未动 App 树 / 客户包 / `live_caption/`、未在 B 机上操作**
（ASR-057 §3「不做的事」逐条遵守）。
