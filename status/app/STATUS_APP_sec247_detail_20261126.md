# §247 全文（MiniMVP v1.2 打包）· 2026-11-26 22:27–22:50

> 用户 22:27 明确放行「打包 zip」⇒ 按 APP-147 第 5 步执行（此前 §245 只差这一步）。
> 本节正文全文在此；`status/app/STATUS_APP.md` 只留指针行。

## §0 触发与执行顺序

APP-147 第 5 步原文要求的顺序是「改名 → 打 zip → 写 ACCEPTED → 发 STATUS 邮件」，
但**签 ACCEPTED 必须在打 zip 之前**，否则 `ACCEPTED.json` 进不了 zip（而 v1.1.1 的 zip
里是**含** `Confucius4_LiveCaption_MiniMVP_v1.1.1/ACCEPTED.json` 的，条目第 1 条即是）；
且 APP-148 §1b 要求 zip 与**目录**逐条一致 ⇒ 若 ACCEPTED 只在目录里、zip 里没有，
比对必然出现「只在目录里 = 1」。

⇒ 本轮实际顺序（与 v1.1.1 一致，已在该包上验证过）：

1. 打包前把包内文档的 `0.4.22` 过时文案修成 `0.4.23`（见 §1）；
2. 洁净白名单 19 条（**此时包内无 ACCEPTED.json**，避免带着旧签名）；
3. 目录改名 `…v1.2.candidate` → `…v1.2`；
4. 签 `ACCEPTED.json`（复用 `pack_v13` 的指纹函数 ＋ 闸门⑤ 校验）；
5. 打 zip（含 ACCEPTED）；
6. APP-148 §1b zip↔目录比对 ＋ 反证组；
7. 解压到临时目录跑 `--check`，删临时目录。

## §1 打包前修：包内文档的 EXT 版本自相矛盾（0.4.22 vs 实际 0.4.23）

**事实依据**（三处一致，指向 0.4.23）：
- `ext/extension/manifest.json` → `"version": "0.4.23"`
- `package_profile.json` → `ext_version = "0.4.23"`
- `release.json` → `ext.version = "0.4.23"`

**但**另有一处写 0.4.22，且 `ext/bridge/engine_runtime.py` 的**代码注释**里也有 0.4.22
（那是历史版本标注，**不动**）。文档层四处已修（脚本 `.tmp_recover_app/app247_extver_doc.py`）：

| 文件 | 改法 | 字节 |
|---|---|---|
| `README_zh.md` | 标题升 0.4.23 ＋ 补一条「ASR 按包内模型族自动适配（Qwen3-ASR 0.6B；`EXT_ASR_FAMILY=06b|r2t2` 可强制）」 | 31 554 → 31 676 (+122) |
| `README_en.md` | 同上（英文） | 34 476 → 34 600 (+124) |
| `app/MANIFEST.json` | `notes` 里 `EXT v0.4.22；` → `v0.4.23；` | 1 913 → 1 913 (+0) |
| `release.json` | `"EXT 升级到 v0.4.22（…查找顺序…）"` → `"EXT 升级到 v0.4.23（桥接侧 ASR 按包内模型族自动适配 Qwen3-ASR 0.6B，APP-149）"` | 1 481 → 1 502 (+21) |

判据（写前＋写后，全部通过）：备份逐字节等于原文（备份在**包外**
`shared\pkg_baks_20261126\*.bak_app247_extver`）／锚点唯一／行尾仍全 LF／
行数变化 = 预期／字节差 = 新串减旧串／落盘逐字节等于预期／sha 已变。
复核：文档层 `grep 0.4.22` = 0 命中；三个 json 仍可 `json.load`。

> 未改 `app/MANIFEST.json` 的 `"files": 10891` / `"bytes": 6829594548`：那是 APP-146
> 生成时的**快照**，本轮 README/MANIFEST/release 文案变动后必然不等；`MANIFEST.json`
> 在代码里只被当作「包身份标记文件」（`live_caption_app.py:1277` `os.path.isfile`），
> **files/bytes 不被任何代码读**。真实条目数/字节数以 zip 中央目录为准（§5）。

## §2 洁净白名单：19 PASS / 0 FAIL（在签 ACCEPTED 之前跑）

`APPCAND=…v1.2.candidate APP150_OUT=results/app/app247_zip_whitelist.json` →
19 项全 PASS，含本轮新增第 ⑨ 条（`*.bak*` / `*.overwritten*` / `*.tmp` = 0 个）、
`profile: EXT v0.4.23`、`MT=mt3`、`clone 目录为空`、`除 preset_A.wav 外无音视频`、
`无 CUDA DLL`、`ACCEPTED.json 不在包内`。

## §3 签 `ACCEPTED.json`（v1.2）

脚本 `live_caption/_app247_sign_accepted_v12.py`，**口径照抄** `_app121_sign_accepted_v111.py`：
复用 `pack_v13._acc_module_fingerprints` / `_acc_aggregate`（签的与闸门重算的必须同口径）。

- 生产模块 **34 个**；聚合指纹 `d51d4d675b872f36115e9c4f7e65b41a1bf473dd65529cb4233cee95fbd9b613`
- 写后重读复核 **7/7 PASS**：accepted / version=1.2 / pkg_dir 目录名一致 /
  fingerprints 非空 / 逐条一致 / 集合一致 / 聚合一致
- 闸门⑤ `check_acceptance_binding(pkg, "1.2")` → **True（OK）**
- 证据 `results/app/app247_sign_accepted_v12_evidence.json`
- `built_by` 里如实写明：**reviewer 从 zip 复核待做；B 机复验待做**（APP-147 口径）

## §4 APP-148 §1a：MT3 权重确认（不算 SHA，3 处固定偏移 32 字节）

三份 `openvino_model.bin` **字节数完全相同**（各 1 792 991 738 B）⇒ 正是 reviewer 说的
「只看 config 和大小分不出来」，必须比 hex：

| 偏移 | 候选包 mt3 | 源 mt3 | 源 mt2 |
|---|---|---|---|
| 4096 | `0000a83c0000643d0000563d0000653d0000633d0000b73c0000773d0000413d` | 同左 | `0000993c0000553d0000423d0000503d00004e3d0000aa3c0000653d0000323d` |
| size//2 | `1415d1ee1a17cef6e9b7fc5915fc241501eaf209eb2be9e7db0ae2d7f9f63fe9` | 同左 | `ee03081e03df30050e1c02a0f019e8db0dfe07f61de9220c1efb241f0122b714` |
| size-4096 | `2891389020140090b090e80fb80f5810e00f6890d80fe80f500f888fd80f000f` | 同左 | `a091789008141890a8904810480f6010d00f38902810f80f181008903810480f` |

判定：候选 = 源 mt3（**3/3 一致**）；源 mt3 vs 源 mt2（**3/3 全不同**）。
证据 `results/app/app148_mt3_weight_check.json`（脚本 `live_caption/_app148_mt3_weight_check.py`）。

## §5 打 zip

- 目录改名：`…v1.2.candidate` → `…v1.2`（文件名数 10 892 → 10 892 不变；源 `.candidate` 已不存在）
- 签 ACCEPTED 后目录 10 893 文件 / 6 829 555 370 B（6.361 GiB）
- 产物 **`C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.zip`**
  **5 309 448 161 B（4.945 GiB）**／**10 893 条目**／mtime **2026-11-26 22:39:16**
- 压缩率 **77.7%**（v1.1.1 是 77.8%）；耗时 **391.4 s**
- 结构照抄 v1.1.1：条目全部带顶层目录前缀 `Confucius4_LiveCaption_MiniMVP_v1.2/`，
  **不写目录条目**；`ZipFile` 会自己读回条目数与写入数比对（10 893 = 10 893）
- 打包脚本 `.tmp_recover_app/app247_make_zip.py`：**目标已存在直接拒绝**（不覆盖旧产物）、
  **只写不删**（本机删除 shim 风险）
- 与 v1.1.1 zip 体积比 1.019

## §6 APP-148 §1b：zip↔目录一致（不算哈希）——**判据自身有缺陷，已修并加反证**

**原脚本 `_app148_zip_consistency.py` 首跑 = 假 FAIL**：

```
zip 条目数 = 10893，目录文件数 = 10893
只在 zip 里 = 10893；只在目录里 = 10893；大小不同 = 0
```

根因：zip 条目是 `Confucius4_LiveCaption_MiniMVP_v1.2/<rel>`，目录侧是 `<rel>`（无前缀）
⇒ 直接比对 ⇒ **10893 条全不匹配**。这**不是包的问题**（v1.1.1 的 zip 同样带前缀），
是判据没考虑交付 zip 的顶层目录结构。

修法：① 先剥掉 `basename(cand)/` 前缀再比；② 新增判据
`all_entries_have_top_prefix`（有条目不带前缀 ⇒ 结构不合惯例 ⇒ FAIL）；
③ 收尾 `ok` 里加上「全部带前缀」与「条目数相等」两项（原来只查三项＋CRC）。

修后真跑：**10 893 / 10 893，只在 zip 里 0、只在目录里 0、大小不同 0，
不带前缀 0，`testzip()` = None（CRC 全过）** ⇒ PASS。
证据 `results/app/app148_zip_consistency.json`（`verdict` 四项全 true）。

**反证组** `live_caption/_app247_zip_consistency_counterexample.py`（**6/6 如期望**，
证明判据有鉴别力、不是修成恒 PASS）：

| case | 构造 | 期望 | 实际 |
|---|---|---|---|
| c1 | 正常 2 文件（带前缀） | PASS | rc=0 |
| c2 | zip 多一个文件 | FAIL | rc=1（only_in_zip=1，条目数不等） |
| c3 | zip 缺一个文件 | FAIL | rc=1（only_in_dir=1） |
| c4 | 同名文件内容更长 | FAIL | rc=1（size_differs=1） |
| c5 | zip 不带顶层前缀 | FAIL | rc=1（`all_entries_have_top_prefix=false`） |
| c6 | **真实 v1.2 zip** | PASS | rc=0（10 893 / 10 893） |

证据 `results/app/app247_zip_consistency_counterexample.json`。

## §7 解压自检（APP-147 自查条件 4）

用 `zipfile.extractall` 解到 `shared\zipcheck_v12`（**交付目录之外**）：

- 解压 **44.0 s**；解出 **10 893 文件 = zip 条目数**（`files_match=True`）
- 用**解压出来的包内 python** 跑 `-s app\live_caption_app.py --check`（Diagnose.bat 同款）：
  **rc=0，42.3 s**，结论行「环境正常。ASR 可用后端 2 个，Intel 集显可用。」
  - 依赖：numpy 2.4.6 / openvino 2026.4.1 / openvino_genai 2026.4.1 / transformers 4.57.6 /
    babelvox(Qwen3-TTS) 1.7.1 / qwen3tts 模型 OK
  - 设备：GPU.0 Intel iGPU OK、NPU Intel AI Boost OK
  - ASR 后端：Intel GPU·INT8(stateful) / Intel NPU·INT8(stateful) 模型齐全
  - 翻译：**Hy-MT3-1.8B** INT8-CW（GPU.0 默认 / NPU），INT4 两行显示「本包不附带」
  - 麦克风 3 个、输出 Speaker (Realtek) OK
  - 无 `Traceback`
- 证据 `results/app/app247_zip_extract_check.json`
- 临时目录**已删除**（`shutil.rmtree` 成功，`exists=False`）

## §8 未完成 / 留白（如实登记）

1. **reviewer 从 zip 复核**：未做（本轮由 App 侧自查；reviewer 会从交付 zip 独立复核）。
2. **B 机复验**：未做（APP-147 明确「B 机不挡这次发版」）。
3. **APP-148 §2（APP-144 ① 历史脱敏）**：仍排在发版之后，本轮未动。
4. **LOCK-001 遗留**（§246 已登记）：`machine_lock_app.py` 的 `write_lock_atomic` 与三轮编排
   脚本的 CreateNew/finally **尚未改成套 `machine_lock.py run`**；下次计时作业起法必须改，
   并在日志核对 `acquired` / `released` 两行。
5. 包内 `app/MANIFEST.json` 的 `files/bytes` 仍是 APP-146 生成时快照（见 §1 末注），未改。

## §9 纪律自查

- **未改** `status/app/CORRECTIONS_APP.md`（无新编号；本轮无 §N 追加依据）
- **未连** B 机、**未调** MiniMax、**未推** 任何强制推送
- 交付目录内**未留**备份/临时文件（备份全部落在包外 `shared\pkg_baks_20261126\`）
- zip **只写不删**；旧包（v1.1.1 目录与 zip、v1.0-rc11 等）**一律未动**
- 本机未跑任何占 GPU/NPU 的计时作业（本轮只有打包与 `--check`）⇒ 无需机器锁
