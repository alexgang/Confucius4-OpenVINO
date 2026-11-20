# STATUS_APP §218 明细（待命轮：6 通道无新纠偏 ＋ A 机换网 ⇒ 目标机不可达归因更正）

> 🔴 本文件是 `status/app/STATUS_APP.md` **§218 的正文**（活文档逼近 40 000 B 限额 ⇒ 正文放 companion）。
> 活文档里只有 §218 标题行 ＋ 一段摘要 ＋ 指向本文件的指针行。

**时间**：2026-11-20 19:35（巡检开工）→ 收尾时间见活文档头部「更新时间」
**执行条数**：**0 条新纠偏**（6 通道全查空 ⇒ `last_ack` **保持 APP-118 不变**）
**性质**：**待命轮**（APP-085 §2）**＋ 1 项此前未记录的新事实** ⇒ 按 §194 ⑪ / §203 ⑫ 先例写入本节并**如实申报偏离**（见 §7）

---

## §0 一句话

🔴 **本轮无新 reviewer 纠偏**（`CORRECTIONS_APP.md` 118 条 / max **APP-118** = `last_ack`；QQ 邮箱白名单最新封 = **TTS-075**、最新 APP 封 = **APP-118**；其它模块最新 = ASR-066 / TTS-075 / H-026 ⇒ **零 App 动作**）。
🔴 **新事实（此前未记录）**：**A 机已离开 `192.168.2.0/24` 网段** —— 现 WLAN = **`10.188.194.152/21`**（SSID `EmployeeHotspot`，网关 `10.188.192.1`），**路由表里根本没有 `192.168.2.0/24` 这一条** ⇒ 目标机 `192.168.2.206` 当前**不可达**。
⇒ **更正 §200 ⑦ 的归因前提**（当时记「本机仍在 192.168.2.189/24 ⇒ 不是本机换网」——**该前提现已失效**）⇒ 「目标机不可达」**当前至少有两个可能原因**（① 目标机离线 ② **A 机已换网**），**不能再单因归因**。
⇒ 续跑 `_app547_hash_retry.py` 须**同时**满足两个条件：HOST 改 `.206`（现在仍是 `.194`）**且** A 机回到能路由到 `192.168.2.0/24` 的网络。

---

## §1 六通道纠偏核查（开工 → 收尾）

| # | 通道 | 结果 | 证据 |
|---|---|---|---|
| ① | `status/app/CORRECTIONS_APP.md` | 🔴 **无新条目**：`## APP-xxx` **118** 条／max **APP-118**／distinct 118／**dupes 空**／**gaps 空**（109→118 连续）／全文搜 `APP-11[9]` `APP-1[2-9][0-9]` `APP-[2-9][0-9][0-9]` ⇒ **0 命中** | 开工 SHA256 `adf4d7046c9a85c9e583cc74d3d89433e8497c1f419d69b49fe9462273f459f5`／**399 777 B**／mtime **2026-11-20 15:30:56**；收尾复核见 §7 |
| ② | QQ 邮箱 `1985197690@qq.com` | 🔴 **无新 App 纠偏**：发件人 `alexchen7694@agent.qq.com` 共 **10 封**（has_more=false）；**最新 3 封** = `TTS-075`(11-20 15:38)／`ASR-066`(11-20 15:33)／`T-MAIL-003`(11-20 15:30)；**最新 APP 封 = APP-118**（11-20 11:34，**上一轮已执行完毕**）⇒ **无 APP-119+**。spam **0 封**；trash **1 封**（MiniMVP rc9 报告，收件人 `alexgang.chen@gmail.com`，**非 reviewer 邮件 ⇒ 未动、未标已读**） | `mcp__qq-mail` ListMessages/SearchMessages 只读 |
| ③ | agent-mail | 🔴 **不可用**：`not_bound`（面板显示 connected，实际未开通；**与 §193／§194 同**，只试 1 次即停） | `mcp__agent-mail__ListMessages` 返回 `{"status":"not_bound"}` |
| ④ | `shared/NOTICE*` | 🔴 **无新**：最新仍 **2026-11-05 09:35**（`NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md`，16 629 B） | 目录 mtime 实测 |
| ⑤ | 根 `status/CORRECTIONS.md` | 🔴 **无 App 条目**：max **C-135**（10-24）；全文 `APP-` 仅 **1 命中** = 第 1883 行的**指路说明**（「d App、打包、git：`…\status\app\CORRECTIONS_APP.md`（APP-xxx）」）⇒ **不是纠偏条目** | `grep -c "APP-"` = 1 |
| ⑥ | 其它模块纠偏文件 | 🔴 **零 App 动作**：ASR max **ASR-066**／TTS max **TTS-075**（`qwen3tts_eval/status/CORRECTIONS_TTS.md`，154 886 B，mtime 11-20 15:38，TTS-075 已在文件内）／HY max **H-026**（`C:\Users\Trekker-PTL\hy_bench\CORRECTIONS_HY.md`，21 906 B，mtime 11-20 18:45） | 各自 `^## XXX-\d+` 扫描 |

⇒ **6 通道全空 ⇒ 本轮无「编号 > last_ack」的条目可执行 ⇒ `last_ack` 保持 `APP-118`**（MEMORY §三：无新纠偏时 `last_ack` 不变）。

---

## §2 🔴 新事实：A 机已离开 `192.168.2.0/24` 网段（本轮唯一实质产出）

### §2.1 证据（全部本轮实测，可复算）

| # | 探针 | 结果 |
|---|---|---|
| ① | `Get-NetIPAddress -AddressFamily IPv4`（排除 127／169.254） | **唯一非链路本地 IPv4 = `10.188.194.152`，PrefixLength = 21，InterfaceAlias = `WLAN`，InterfaceIndex = 9**；**没有任何 `192.168.2.x` 地址** |
| ② | `netsh wlan show interfaces` | 状态 **已连接**；**SSID = `EmployeeHotspot`**；配置文件 `EmployeeHotspot`；无线电类型 802.11ax；信号 83% |
| ③ | `Get-NetRoute -AddressFamily IPv4`（排除链路本地／组播） | 仅 4 条非环回路由：**`0.0.0.0/0` → `10.188.192.1`（WLAN，metric 45）** ＋ `10.188.192.0/21`（on-link）＋ `10.188.194.152/32` ＋ `10.188.199.255/32` ⇒ 🔴 **路由表里不存在 `192.168.2.0/24` 任何条目** |
| ④ | `Get-NetNeighbor -AddressFamily IPv4` | `192.168.2.x` 全部 **`Unreachable`**（含 `.1` 网关、`.206`）⇒ **无 ARP 表项**（本机与该网段不同链路） |
| ⑤ | `ping -n 2 -w 2000 192.168.2.206` | 已发送 **2**／接收 **0**／丢失 **2（100 % 失败）** |
| ⑥ | `ssh -o BatchMode=yes -o ConnectTimeout=8 63446@192.168.2.206`（15 s 超时） | **`ssh: connect to host 192.168.2.206 port 22: Connection timed out`** |
| ⑦ | TCP 对照：`/dev/tcp/192.168.2.206/22` | **无连接**（超时） |
| ⑧ | TCP 对照：`/dev/tcp/github.com/443` | **`TCP443_OK`** ⇒ 🔴 **不是沙箱禁网**，是真实网络状况 |
| ⑨ | 网关对照：`Test-Connection 10.188.192.1` | **True** ⇒ 本机无线链路**健康** |
| ⑩ | `Get-NetAdapter`（Status=Up） | `WLAN`（Intel Wi-Fi 7 BE211，287 Mbps）＋ `Tailscale`（Tunnel） |

### §2.2 时间线（能证到什么程度）

- Wi-Fi 自动配置日志（`Microsoft-Windows-WLAN-AutoConfig/Operational`，ID 8001）**最后一次成功连接 = `2026/11/17 07:56:13`**（SSID GUID `5ebe5072-d5c6-4f6e-a462-4d14531c2ca0`，即 `EmployeeHotspot`）；此前依次为 11-16 14:31:57／11-14 15:21:50／11-14 00:31:16／11-13 22:36:55／11-13 20:27:04／11-12 08:32:10。
- 系统启动时间 **2026-11-14 00:30:45**。
- `Microsoft-Windows-Dhcp-Client/Admin`（ID 1004）**无任何条目** ⇒ 🔴 **切换到 `10.188.x` 的精确时刻不可定位**，只能说「**当前**（2026-11-20 19:38～19:5x）已不在 `192.168.2.0/24`」。
- `Tailscale` 适配器 Up，但 `tailscale status` = **`NoState`**（协调服务器连不上）⇒ **无第三条路**（与 §196 记录一致）。
- 历史对照：`status/archive/STATUS_APP_upto_20261030.md` 第 2996 行记「本机当前 `100.70.84.17` Tailscale / **`192.168.2.189`** WLAN」⇒ 该网段是**历史上**本机所在的 LAN，不是当前。

### §2.3 🔴 归因更正（对既有结论）

- **§200 ⑦ 当时记录**：「本机仍在 **192.168.2.189/24**（网关 192.168.2.1）⇒ **不是本机换网**；目标 `192.168.2.194` ping 4/4 丢包、无 ARP 表项、TCP 22/445 均超时 ⇒ **目标机已关机／脱网**」——**该结论的前提「本机仍在 192.168.2.189/24」现已失效**（§2.1 ①③）。
- ⇒ **「目标机不可达」当前至少有两个可能原因**：① 目标机离线（§200 的原始假设）；② **A 机已换网**（本轮新证）。**两者可同时成立、且本轮无法区分** ⇒ 🔴 **不能再单因归因为「目标机已关机」**。
- ⇒ 对 L5/L6 的直接影响：目标机相关三项（① 授权删目标机 zip／② 目标机实机 `--check`／**两端 SHA256 对账**）现在**多一道前置条件**：**A 机得先能路由到 `192.168.2.0/24`**。
- ⇒ `_app547_hash_retry.py`（实位于 `%TEMP%\_app547_hash_retry.py`，**3 159 B**，mtime **2026-11-13 22:48**，第 3 行 `HOST = "192.168.2.194"`）：**HOST 仍是旧地址 `.194`**（L5 早已登记，本轮再次确认脚本**未落盘**到仓库、也**未改**）⇒ **续跑前必须同时**：① HOST 改 `.206` ② A 机网络回到可达 `192.168.2.0/24`。
- ⇒ **与 T-MAIL-002/003 背景一致**：reviewer 常切网络 ⇒ 协作用邮件；本轮同样确认 A 机已不在 reviewer 原先可达的 LAN 上。

---

## §3 只读复核（本轮**零**改动、零推理、零计时）

> 🔴 本轮**未跑任何推理／测速** ⇒ **未取 `MACHINE_LOCK`**（实测：`C:\Users\Trekker-PTL\shared\MACHINE_LOCK` **不存在**）⇒ 未占 GPU/NPU。

| 项 | 结果 | 证据 |
|---|---|---|
| 语速常量（dev） | `SPEED_MAX = 1.70`／`ZH_SPEED_MIN = 1.10`／`ZH_SPEED_MAX = 1.70` | `live_caption/time_stretch.py:85,112,113` |
| TTS 参数（dev） | `'tts_speed_max_zh': 1.70`／`'tts_late_drop_sec': 0.0` | `live_caption/device_config.py:837,843` |
| APP-086·2a 收窄 | `tts_worker.py` **`and not _bound`** 命中 **2** 处（L2006 `if self.clone_mode and not _bound:`／L2012 `elif self._has_clone_voice() and not _bound:`）；旧式 `elif self._has_clone_voice():` **0** 处 | `grep -c` = 0 |
| v2.5 包内一致性 | v2.5 `app/` 与 dev `live_caption/` **4 个关键文件 md5 逐字节一致**：`device_config.py` `7e2c6846c0ee941104a262daf4fd040c`／`tts_worker.py` `e012214a8940f13c2b497a7fd22576ce`／`live_caption_app.py` `7913f54a72d2ce96b05922d4d9624a34`／`time_stretch.py` `9eebf2bc887635bb40c2bd43675f5c39` | `md5sum` 两两比对 |
| 客户包矩阵 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_*` 共 **11** 个目录（完整版 v1.13／v1.5／v2.0／v2.1／v2.2／v2.3／v2.3_aborted／v2.4／**v2.5** ＋ MiniMVP **rc11** ＋ SpecialMVP **sp5**）⇒ **旧目录旧 zip 一律未删未改** | 目录列举 |
| zip 现状 | MiniMVP `rc10` zip **5 926 048 165 B**（11-12 16:49:06，reviewer 11-13 已独立复核）**与** `rc11` zip **6 697 683 352 B**（11-13 10:23）**两个都在**；🔴 **v2.5／sp5／rc11 目录均无 zip** ⇒ **本轮未打包**（用户长期规则：不通知 ⇒ 不打包） | `shared/minimvp/*.zip` 列举 |
| git | 分支 **main**；HEAD **`dfb225e`**（上轮 §217）；`origin/main` = `31e5c67` ⇒ **ahead 8 / behind 0**；ahead 的 8 个里 **5 个是 ASR 模块**的（`89474df` `e2376be` `240abeb` `f015d1e` `eb3bf1f`）、**3 个是 App 的**（`e04e873` `86639e9` `dfb225e`） | `git log --oneline origin/main..HEAD` |
| `live_caption/` | tracked 实改动 **0 行**（本轮零产品代码改动） | `git diff --numstat -- live_caption/` 空 |
| OpenVINO（本仓库 venv，仅作参照；本轮未跑推理） | `openvino 2026.4.1-22982-e213a147257-releases/2026/4`／Python 3.12.10 | `./.venv/Scripts/python.exe -c "import openvino"` |

---

## §4 本轮**未**做的事（显式列出，避免误读）

- 🔴 **未执行任何新纠偏**（无编号 > APP-118 的条目）⇒ `last_ack` 不变。
- 🔴 **未改 `status/app/CORRECTIONS_APP.md`**（reviewer 独占文件，**只读**；开工＝收尾 SHA/字节/mtime 见 §7）。
- 🔴 **未改任何产品代码**（`live_caption/` tracked 改动 0 行）；**未新建闸门／矩阵／判据脚本**。
- 🔴 **未打包／未打 zip**；**未写客户包目录**（11 个目录全部逐字节未动）。
- 🔴 **未跑推理／测速** ⇒ 未占 GPU/NPU，未取 `MACHINE_LOCK`。
- 🔴 **未删任何客户包目录／zip**；**未连接 B 机**（APP-109 ④ 仍然有效）；**未对目标机做任何写操作**（未连、未经授权删 zip、未拷贝、未做 SHA 对账）。
- 🔴 **未吞他模块未提交改动**（全仓脏 827 项，与上轮同量级；`status/app/CORRECTIONS_APP.md` 的 ` M` 是 **reviewer 自己**的未提交追加，**永不 add**）。
- 🔴 **未自行调用 MiniMax** 做质量判定。

---

## §5 git 提交范围（只提 App 侧文件）

本轮**新增/修改并提交**（逐文件 `git add`，禁 `-A`）：

- `status/app/STATUS_APP.md`（改：头部「更新时间」一行 ＋「最近更新」一行 ＋ §218 标题/摘要/指针 ＋ L6 待用户一句 ＋ L7 压缩索引一句 ＋ §162–§169 标题行块换成指针行）
- `status/app/STATUS_APP_sec218_detail_20261120.md`（新：本文件，§218 正文）
- `status/archive/STATUS_APP_sec162_169_headers_20261120.md`（新：§162–§169 标题行＋指针行**整块逐字归档**，write-once）
- `status/archive/STATUS_APP_recent_updates_20261120.md`（新：「最近更新」上一条（11-20 18:28）**整块逐字归档**，write-once）

🔴 **不提交**：`status/app/CORRECTIONS_APP.md`（reviewer 独占）。
🔴 **不 push**：沿用上一轮口径（`origin/main` 的 ahead 段里含 **5 个 ASR 模块**的提交，push 会一并发布他模块成果 ⇒ 留待 reviewer/用户统一决定）；本轮**普通 push 预演已验证可快进**（`git push --dry-run` ⇒ `31e5c67..dfb225e main -> main`）。

---

## §6 未结项（沿用 + 本轮新增）

| # | 项 | 状态 |
|---|---|---|
| 1 | **§217 待 reviewer 复核** | 沿用（本轮未动） |
| 2 | **完整版出厂默认（ASR+MT+TTS 全 GPU.0）10 分钟整链 FAIL**（OV 集显 RTF≈4.4 ⇒ 积压 917 s；既有局限、非 v2.5 回归） | 🔴 **等用户裁定**默认摆放（APP-118 §1：改默认先问用户） |
| 3 | **预设 B（男声）抽听 + 点头后才进包** | 🔴 等用户抽听（回转写 CER_zh 0.0048／WER 0.0，与预设 A 逐项相等；`preset_B.wav` **不在** v2.5 包内） |
| 4 | **v2.5 的 zip** | 🔴 等用户通知（**不通知 ⇒ 不打包**） |
| 5 | **目标机三件套**：① 授权删目标机 zip（C: 仅 1.55 GiB 可用）② 目标机实机 `--check`（sm_89/6 GB vs 包基线 sm_120）③ **两端 SHA256 对账** | 🔴 **本轮新增前置条件**：**A 机须回到能路由到 `192.168.2.0/24` 的网络**（§2）**且** `_app547_hash_retry.py` 的 HOST 须先由 `.194` 改 `.206` |
| 6 | **10 个带 APP-086·2a 缺陷包**：作废还是标注 | 沿用（等用户决定；目录一律保留不删） |
| 7 | **EXT 换嵌通知**（v0.4.18 vs 内嵌 v0.4.16，差 2 版） | 沿用 |
| 8 | **§214 未结项其余 3 条** | 沿用 |
| 9 | **§215 未结项①**（reviewer 侧 5 处 `finally` 无条件 `Remove-Item $lock`） | 沿用（**只取证、不越界**） |
| 10 | **OPEN-1**（长跑退出码 3221226505） | 沿用 |

---

## §7 纪律自检 ＋ 与 APP-085 §2 的偏离申报

### §7.1 偏离申报（依 §194 ⑪ / §203 ⑫ 先例，如实申报）

- APP-085 §2 原文：待命期（**没有编号大于 last_ack 的纠偏**）巡检只做两件事 —— 读最大编号；如无新条目，**只改 STATUS 头部「更新时间」这一行**（或干脆什么都不写），**不新建脚本/json，不新增 § 章节，不归档，不 commit/push**。
- **本轮偏离**（如实登记）：本轮**确实无新纠偏**（6 通道全查空，节点未推进），但**产出 1 项此前未记录、可复算、且会改变既有归因的事实** —— §2「**A 机已离开 `192.168.2.0/24`**」⇒ 它**直接更正 §200 ⑦ 的前提**（「本机仍在 192.168.2.189/24 ⇒ 不是本机换网」），并**给目标机三件套增加一道前置条件** ⇒ 按任务口径「结果只写进 `STATUS_APP.md`，且只**追加** `## §N` 章节」写入 §218，并按 APP-052④ 的 40 000 B 限额把 **§162–§169 的标题行＋指针行整块归档**（各节**正文**早已分别归档在 `status/archive/STATUS_APP_sec162_20261110.md`～`…sec169_20261110.md`，本次只搬标题行＋指针行，**正文一字未删**）。
- ⇒ **本轮新增 § 章节 1 节（§218）／归档件 2 份／提交 1 次**（逐文件 `git add`、**未提交** `CORRECTIONS_APP.md`、**未 push**）。
- ⇒ **若 reviewer 认为本轮应当零写入**：**单步回退即可**（`git revert <本轮 commit>`）—— 归档件与改前逐字节备份都在磁盘上（备份：`%TEMP%/STATUS_APP.bak_standby_20261120.md`）⇒ **回退不丢任何原始交付物**（11 个客户包目录、全部 zip 均未被本轮触碰）。

### §7.2 纪律自检

- 🔴 **未改 `status/app/CORRECTIONS_APP.md`**（reviewer 独占文件，只读）——开工 SHA256 `adf4d7046c9a85c9e583cc74d3d89433e8497c1f419d69b49fe9462273f459f5`／399 777 B／mtime 2026-11-20 15:30:56／118 条；**收尾复核见本轮收尾记录**（若中途被 reviewer 追加则如实登记，**绝不声称「SHA 零改动」而不核**）。
- 🔴 **未改其它模块的未提交改动**（全仓脏 827 项，与上轮同量级；`status/app/CORRECTIONS_APP.md` 的 ` M` 是 reviewer 自己的未提交追加 ⇒ **永不 add**）。
- 🔴 **未删任何客户包/zip**（11 个目录 + 全部 zip **一律保留**）；**未覆盖任何旧版本目录**（版本纪律 APP-055：只打新版本号，本轮**未打**）。
- 🔴 **写盘纪律**：备份 → 临时文件 → `os.replace` → 写后独立复核（UTF-8 **文本**比对，避免「已是 UTF-8 字节的串再 `.encode()`」假 FAIL）；归档件 **write-once**。
- 🔴 **本轮零推理零计时** ⇒ 未占设备 ⇒ `MACHINE_LOCK` 保持不存在。

---

## §8 本轮待 reviewer 确认的一句话

🔴 **本轮无新纠偏可执行；但 A 机已不在 `192.168.2.0/24`（现 `10.188.194.152/21`，SSID `EmployeeHotspot`）⇒ 「目标机不可达」不再能单因归因为「目标机关机」，且目标机三件套（删 zip 授权／实机 `--check`／两端 SHA256 对账）现在**多一道前置条件：A 机网络须回到可达 `192.168.2.0/24`**。请 reviewer 确认此归因更正是否成立、以及 §218 本轮写入是否可接受（可一键回退）。**
