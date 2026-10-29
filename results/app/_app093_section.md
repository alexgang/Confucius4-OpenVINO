## §93 🔴🔴 **客户包 v1.6 已持锁重打 zip ⇒「已交付」成立（代码 + 包目录 + zip 三方闭环）＋ 自查抓出并修掉 2 个真实缺陷（§48 闸门命中未入库脚本的写死包路径）**（2026-10-29 13:28）｜**本条已完成**｜**本条需等 reviewer 复核**

### §93.0 本节缘起

§92 已完成 APP-034/035/036/037/038 五条纠偏的**代码侧**，但明确登记「⛔ 客户包 v1.6 zip 未重打 ⇒ zip 内仍是旧代码 ⇒ **不写「已交付」**」。
本节补齐**交付闭环**这一环：持锁重打 zip ⇒ 三方只读复核 ⇒ 写入证据。

### §93.1 🔴 打包闸门第一次拦下了我 —— §48「客户包路径写死」

第一次跑 `pack_v13.py`（13:04:15 起，PID 9768）⇒ **闸门 FAIL ⇒ 拒绝打包**（旧 zip 未被动过，安全）：

```
§48 闸门：客户包路径「写死版本」缺陷类别
命中「代码行里有客户包名」的文件数 = 74
🔴 违规 2 处：
   [A] results/app/app132_s91_threeway_check.py   行[33, 35, 36]
   [A] results/app/app136_s92_threeway_check.py   行[37, 39, 40]
        PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6'
        ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6.zip'
        PREFIX = 'Confucius4_LiveCaption_v1.6'
总判定：FAIL ⇒ 拒绝打包
```

**🔴 判别**：
- `app136` 是**本轮我自己新写的**脚本 ⇒ 是**我引入的缺陷**；
- `app132` 是**上一轮（§91）留下的**脚本 ⇒ 是**潜伏缺陷**（当时没被 §48 拦到，因为它是在闸门修好之后才写的）。

⇒ **闸门行为正确**（这正是 §48 设计的初衷：防止「脚本写死版本号 ⇒ 升版后指向旧包 ⇒ 报出假 FAIL」）。

**修法**（按闸门自己给出的指引）：改用 `pkg_paths`（**单一数据源**）自动发现，**不写死版本号**：

```python
sys.path.insert(0, REPO)
import pkg_paths  # noqa: E402

PKG = pkg_paths.discover_pkg_dir()      # 自动发现最大版本（含 app/ 的）
PKG_APP = pkg_paths.pkg_app_dir(PKG)
PREFIX = os.path.basename(PKG.rstrip('\\/'))
ZIP = PKG + '.zip'
```

**修后实测**：`pkg_paths.discover_pkg_dir()` → `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6`
⇒ 与原先写死的值**完全一致**（行为不变，只是解除了版本硬编码）。
单独复跑闸门 ⇒ **「✅ 0 处违规」/ 总判定 PASS**。

🔴 **教训**：§48 闸门**扫的是「仓库里的脚本」**⇒ 一个**验收脚本**写死包路径也会阻断交付。
⇒ 「验收脚本」不是「一次性草稿」⇒ 它同样受闸门管辖 ⇒ **写脚本时就要用 `pkg_paths`**。

### §93.2 持锁重打 zip（PASS）

| 项 | 实测 |
|---|---|
| 锁 | `app-pack PID 4788 started 2026-10-29 13:06:34`（**第 1 次尝试即取得**） |
| 安静窗口 | 45 s（期间报「有 1 个『在算』的外部 python 进程」⇒ 是**我自己**在复跑 `app133`/`app134` 包内验收 ⇒ 等它跑完 ⇒ 重新计时 ⇒ 通过） |
| §48 闸门 | **PASS**（0 处违规） |
| 内部素材闸门（APP-006 第 6 步） | **PASS**（命中 0 个内部素材） |
| 文件数 | **14 200**（MANIFEST files=14 199） |
| 原始字节 | 13 672 878 916 |
| 压缩后字节 | **11 218 138 008**（10.45 GB，压缩率 82.0%） |
| 压缩耗时 | **604 s** |
| `testzip()` | **Everything is Ok** |
| 内容一致性 | **比对 14 200 个文件 ⇒ 全部逐字节一致** |
| 原子改名 | **已改名到正式路径** `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6.zip` |
| 打包脚本结论 | **PASS** `md5=f78d7fd3105a4f513f928b8b0b6cd90a` |
| 锁释放 | `[lock] 已释放` ✔ |

**zip 最终指纹**：

| 项 | 实测 |
|---|---|
| 路径 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6.zip` |
| 字节数 | **11 218 138 008** |
| mtime | **2026-10-29 13:20:04** |
| SHA256 | **`376c483201007ce2805df126df8241cf01ddc8757a2447226981090ae06631b8`** |

⚠️ **与上一版对比**：旧 zip = 11 218 129 470 B / 2026-10-29 09:53:26 / SHA256 `dfd97ab2…4b53`
⇒ 本次 **+8 538 B**（正是 3 个改动文件的增量 ＋ MANIFEST 刷新）⇒ **zip 确实换了内容**。

### §93.3 独立只读三方复核（`app136`）⇒ **PASS**

**为什么要独立脚本**：打包脚本自己说 PASS **不等于**闭环 ⇒ 必须有一个**独立**直读 zip 内字节的复核。

`results/app/app136_s92_threeway_check.py`（只读：不写包、不写 zip、不删任何文件）：

```
仓库 live_caption/<f>  ⇄  客户包 v1.6/app/<f>  ⇄  zip 内 <prefix>/app/<f>
```

**实测结果**：

| 判据 | 实测 |
|---|---|
| 参与比对的包内 `.py` | **23 个**（排除 1 个 `pkg_exclude` 排除项） |
| 仓库 ⇄ 包目录 | **23 / 23 一致**（归一化 LF 后 SHA256） |
| 包目录 ⇄ zip | **23 / 23 一致** |
| `testzip()` | **OK（无损坏条目）** |
| **结论** | **PASS（三方全部逐字一致 + zip 完整）** |

**§92 本轮改动的 3 个文件三方指纹**：

| 文件 | 仓库 | 包目录 | zip | 判定 |
|---|---|---|---|---|
| `tts_worker.py` | `90835802f79a47e1` | `90835802f79a47e1` | `90835802f79a47e1` | **MATCH** |
| `tts_service.py` | `ec2ef04a5c6f9276` | `ec2ef04a5c6f9276` | `ec2ef04a5c6f9276` | **MATCH** |
| `live_caption_app.py` | `5aa3269aa9b0b740` | `5aa3269aa9b0b740` | `5aa3269aa9b0b740` | **MATCH** |

⇒ **「APP-036 遥测口径 4 处」＋「APP-037 句首标点规范化」确实进了 zip** ✔

### §93.4 🔴 复核脚本的**反向自证**（判据不恒真）

按「验收脚本跑出 PASS ≠ 脚本是对的」纪律 ⇒ **必须双向反证**：

| 步骤 | 实测 |
|---|---|
| ① 向包内 `tts_worker.py` 注入 1 处真实差异（追加 1 行注释） | 包内 SHA 变为 `eeaaf6e61453d094` |
| ② 复跑 `app136` | **FAIL** ⇒ 仓库⇄包目录 22/23、包目录⇄zip 22/23 ⇒ **精确定位到 `tts_worker.py`** ✔ |
| ③ 恢复（从包外备份 copy 回） | 包内 SHA 回到 `90835802f79a47e1` ⇒ **与仓库 MATCH = True** ✔ |
| ④ 复跑 `app136` | **PASS**（23/23 ×2 + testzip OK）✔ |

⇒ **判据有分辨力**（能抓到真差异，不是恒真）⇒ 且**注入痕迹已完全清除**（三重校验：SHA 一致 + MATCH=True + 复跑 PASS）。

### §93.5 交付闭环的 git 侧

| 项 | 实测 |
|---|---|
| commit | **`dc7603b`** `app: §92 执行 APP-034/035/036/037/038 五条纠偏（代码侧）` |
| 变更 | **20 文件 / +5233 −11** |
| push | **普通 push** `6ff8bf6..dc7603b`（**非 force**） |
| `HEAD == origin/main` | **dc7603b4e85c9682eb3484556f9cb39680eaf356** ✔ |
| 分支 | 仓库仍**只有 main** ✔ |
| `CORRECTIONS_APP.md` | **未入库**（`git show --name-only --format="" HEAD | grep CORRECTIONS` ⇒ **0 命中**）✔ |
| 他模块改动 | **未吞**（逐文件 `git add`，**禁用 `-A`** ⇒ 暂存清单 21 项**全部是 App 侧**；ASR/MT/TTS 路径命中数 **0**）✔ |

### §93.6 「已交付」判定（§66 口径）

| 条件 | 状态 |
|---|---|
| 代码侧已入库并 push | ✔ `dc7603b` == `origin/main` |
| 客户包**目录**已含最新代码 | ✔ 仓库⇄包目录 23/23 MATCH |
| 客户包 **zip** 已含最新代码 | ✔ 包目录⇄zip 23/23 MATCH ＋ 打包脚本 14 200 文件逐字节一致 |
| 独立三方只读复核 | ✔ `app136` PASS ＋ 反向自证 FAIL（判据有分辨力） |
| zip 完整性 | ✔ `testzip()` OK |

⇒ ✅ **「已交付」成立（代码 + 客户包目录 + 客户包 zip）**

**分发方式**（reviewer APP-035 第 3 条）：v1.6 zip 留在目标机原位 ⇒

```
C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6.zip
字节数   11 218 138 008
mtime    2026-10-29 13:20:04
SHA256   376c483201007ce2805df126df8241cf01ddc8757a2447226981090ae06631b8
```

⇒ **由 reviewer 用 SSH/SFTP 拉取**；FTP 已关闭（§92.1）⇒ **本轮未运行 `publish_ftp.py`、未开 FTP**；
`FTP_Share/` 仍**只有 v1.4 / v1.5**（11 216 051 100 B / 11 216 287 107 B）⇒ **未动、未删**。

### §93.7 本轮证据文件

| 文件 | 字节 | mtime | SHA256（前 32） |
|---|---|---|---|
| `results/app/app136_s92_threeway_check.py` | 7 243 | 2026-10-29 13:05:34 | `eaac7fae0f5df49888be9dbf63bb8ea3` |
| `results/app/app136_s92_threeway_check_evidence.json` | 7 130 | 2026-10-29 13:28:03 | `0fa607c2cd1a02325a19432388981093` |
| `results/app/pack_v16_s92_log.txt` | 9 221 | 2026-10-29 13:23:05 | `becd0e22151e54d67582922f423038db` |
| `results/app/app132_s91_threeway_check.py`（修 §48 写死） | 5 130 | 2026-10-29 13:05:39 | `7ab03e299430444eaf5d104eebe573f5` |
| `results/app/app133_app037c_lead_punct_pkg_evidence.json`（复跑重生成） | 8 640 | 2026-10-29 13:07:33 | `c3f09db726a1c995d12c4dc257508962` |
| `results/app/app134_app036c_telemetry_pkg_evidence.json`（复跑重生成） | 9 848 | 2026-10-29 13:07:27 | `f7921cca5ba9bbb4c4f79087669b240b` |

🔴 **⚠️ 产物时效说明（§92.9 表格的一条已陈旧，如实登记）**：
`app134_app036c_telemetry_pkg_evidence.json` 在 §92 落盘时指纹是 `7edd54dd57bc86ff…`（mtime 12:58:40），
本节 §93.8 的**同步后复跑**重写了它 ⇒ **现指纹 = `f7921cca5ba9bbb4…`（mtime 13:07:27）**。
⇒ **§92.9 表格中这一条已过时**（内容为**同口径复跑**，PASS/FAIL 结构相同，但含实测时序 ⇒ 字节与指纹会变）。
⇒ 本节表格为**当前权威值**；`app133` 的包内 evidence **逐字节相同**（`c3f09db7…`）⇒ 纯判定型内容可复现 ✔
⇒ 📌 **教训**：含**实测时序/采样点**的 evidence **不可复现** ⇒ 引用时**必须带 mtime**，
否则「指纹对不上」会被误当成「产物被改坏」。

### §93.8 同步后的**包内代码复跑复核**（脚本先跑、同步在后 ⇒ 必须复跑）

⚠️ §92 的 `app133`/`app134` 验收脚本**跑在同步之前** ⇒ 同步后必须**复跑**确认包内那份代码仍全绿：

| 脚本 | 目标 | 结果 |
|---|---|---|
| `app134`（`APP134_SRC_ROOT` = 包根） | 客户包 v1.6 内那份 `tts_worker/tts_service/live_caption_app` | **50 PASS / 0 FAIL** ✔ |
| `app133`（`APP133_SRC_ROOT` = 包根） | 同上 | **50 PASS / 0 FAIL** ✔ |

⇒ **包内代码与仓库代码行为一致** ✔

### §93.9 仍然未做（**不因 zip 重打而消失**）

- ⛔ **APP-036 的真实验收未做**：reviewer 要求「SPE 前 5 分钟 **NPU 默认配置**、**播放模式**重跑
  ⇒ ≥100 采样点曲线 ＋ `worker_fifo_wait` P50/P95/max ＋ `end_lag_s` ＋ `n_discard_on_close=0`
  ＋ B 段「中文时长/原声时长」比值
  ⇒ 本轮只做了**口径修正 + 零推理验收 + 离线模拟** ⇒ **真机 5 分钟 NPU 播放模式重跑未做**（守纪律）
  ⇒ **待 reviewer 复核**；
- ⛔ **APP-037 B1/B2/B3 未做**：「lang 显式下传」的流水线级证据（CLI `--translate ja` 76± 句逐句 `lang=ja` /
  `lang_src=explicit`）、NPU 组用修好语料（`97a8bb91…`）重跑 29×3 + wav、日文 GUI 5 分钟 ⇒ 本轮**未跑**（须持锁）；
- ⛔ **追赶策略未做**（APP-036 D 明文等用户决定）⇒ 本轮**只给数字**；
- ⛔ **APP-034 方案 A 的真机效果未验证**（App 侧未调用 `spk_update` ⇒ 结论是**静态核查**得出）；
- ⛔ **APP-038** 未跑 NPU 推理（reviewer 明文「不需要专门去测」）⇒ 仅登记**编译缓存可能失效、冷启动变长**的风险；
- ⛔ **未跑 `verify_pkg_zip.py`**（§66 口径不跑）、**未跑 `publish_ftp.py`**、**未开 FTP**（APP-035）；
- ⛔ **未修改 `CORRECTIONS_APP.md`**（只读、零改动，指纹见 §92.0：100 067 B / mtime 2026-10-29 11:00:14 / SHA256 `838b3171…`）；
- ⛔ **未调 MiniMax**（质量判定归 reviewer）；**未用 `git add -A`**（逐文件 add）。
