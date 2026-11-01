# §24 —— EXT-030/031 **落库收口**（接管上一会话的中断现场）

> ★ 本文件是 `status/STATUS_EXT.md` 中 **§24** 一节的全量明细。
> ⚠️ **不回头改旧章节**——§22 / §23 的结论与数字**一字未改**。
> ★ 依据 **EXT-016 写作规则**（STATUS ≤ 300 行 / ≤ 40 KB / < 归档/10 = 22 483 B）。

---

## §24.1 ★★ 本轮的核心发现：闸门 exit 1 **不等于**「已收口」

上一会话（token = `16a4f381`）把 EXT-030 / EXT-031 的**实现**做完了，但**死在收口之前**。

### 死亡现场（实测）

| 项 | 实测值 | 证据 |
|---|---|---|
| `acquire ext` 返回 | **exit 0 + `TAKEOVER`**（note = `接管租约(TAKEOVER)：EXT-029已收口提交 daaa00d；开始执行 EXT-030/EXT-031`） | `shared/leases/ext.json` |
| 上一会话 token / 起止 | `16a4f381` / 起 **16:14:52**、末次心跳 **16:28:10**（本轮接手时**已死 225 min**） | `shared/leases/ext.json` 的 `prev` |
| 上一会话留下的 `HEAD` | **`daaa00d`**（= §21 EXT-029 收口）⇒ **EXT-030/031 一次提交都没有** | `git log --oneline` |
| `EXEC_LOG.md` 里 EXT-030/031 记录数 | **0**（`grep -c "EXT-030\|EXT-031" status/EXEC_LOG.md` ⇒ `0`） | 实测 |
| 工作区 | **不干净**：`M ext/bridge.py` / `D extension/probe-worklet.js`（已 staged）/ `M status/STATUS_EXT.md` + 4 个未跟踪新文件 | `git status --short` |

### ⇒ 关键结论（★ 本轮写进 STATUS 的核心）

- `tools/next_instruction.py` 返回 **exit 1 / `action=skip`**，**只**说明 `last_ack`（= EXT-031）已推进 ⇒ **指令已被「认领」**；
- 但 **「认领」≠「收口」**：收口 = **EXEC_LOG 有本轮记录 + 产物已提交 + 闸门复测 exit 1**；
- 本轮**未重做任何实现**，只补齐**收口**（EXEC_LOG 记录 + §24 章节 + 提交）。

★ ⚠️ 这正是 EXT-030 要解决的「会话重叠 / 中断」问题的**下游后果**：租约能防两个会话同时 working，
但**防不住**「一个会话做完就死、收口没做完」⇒ 下一轮闸门看到 exit 1 就直接跳过 ⇒ **成果永久搁浅**。
⇒ 本轮**手工补收口**；该缺口已如实报给 reviewer（见 §24.6）。

---

## §24.2 ★ 本轮**独立复核**（实测重跑，**不是照抄上一会话的数字**）

| 套件 | 本轮实测 | rc |
|---|---|---|
| `tests/test_ext_selfcheck.py` | **106 PASS / 0 FAIL** | 0 |
| `tests/test_echo_roundtrip.py` | **11 PASS / 0 FAIL** | 0 |
| `tests/test_next_instruction.py` | **19 PASS / 0 FAIL** | 0 |
| `tests/test_ext031_release_handoff.py` | **24 PASS / 0 FAIL** | 0 |
| `tests/smoke/ext031_fake_pkg_launch.py`（模拟发行包启动） | **6 PASS / 0 FAIL** | 0 |
| `tests/test_ext028_dub_audio_chain.py`（EXT-031 ④ 的打包门禁） | **42 PASS / 0 FAIL** | 0 |
| `tests/test_ext029_spk_bypass.py` | **70 PASS / 0 FAIL** | 0 |
| `tests/test_ext016_compression.py` | 38 PASS / **1 FAIL** | 1 |

★ **模拟发行包启动的实测输出**（本轮重跑，证据落盘 `.tmp/ext031/fake_pkg_probe.json` **2 836 B**，mtime **2026-11-01 20:14:53**）：

```
探针进程正常退出（rc=0）
resolve_app_root() 指向**模拟包**（不是开发机） — app_root='…\ext031_pkg_1z7kbdur\Confucius4_LiveCaption_v2.0'
引擎根 / 模型目录 / 说话人 IR **全部落在模拟包内** — 越界项：'无'
解析结果里**不含**任何开发机目录名 — 命中：'无'
package_root() = 模拟包根（相对包根解析）
EXT_RELEASE=1 ⇒ 抓流白名单只留 tabCapture（EXT-031③） — release_mode=True capture_modes=['tabCapture']
```

---

## §24.3 ★★ 抽查：EXT-031③ 的「发行版剔除」**真的生效**，不是只写不生效

★ 本轮**不满足于**「代码里有 `RELEASE_MODE` 字样」——逐处查了**消费点**：

| 机制 | 唯一事实源 | 消费点（实测） | 判定 |
|---|---|---|---|
| 整机 `getDisplayMedia` 回退禁用 | manifest `liveDub.captureModes` | `extension/offscreen.js` → `state.allowedCaptureModes`（读不到 manifest ⇒ **按最严**只允许 `tabCapture`）→ `if (!state.allowedCaptureModes.includes('getDisplayMedia')) throw new Error('发行版已禁用 getDisplayMedia 整机回退…')` | ✅ **真拦截**，且**明确失败**（绝不静默抓整机声音） |
| `RELEASE_MODE` 判定 | `EXT_RELEASE` → 包根 `release.json` → 默认 False | `ext/config.py` → `RELEASE_MODE` ⇒ `CAPTURE_MODES` | ✅ **显式覆盖优先**（`EXT_RELEASE=0` ⇒ False，即使有 `release.json`） |
| `--audio-dump-out` 忽略 | `RELEASE_MODE` | `ext/bridge.py:3099` ⇒ 创建点前拦截，只打一行警告 | ✅ **不创建落盘器** |
| `--margin-out` 忽略 | `RELEASE_MODE` | `ext/bridge.py:3145` ⇒ 退出前 `_dump_margin` 受保护 | ✅ **不落盘** |

★ ⚠️ 顺带发现一处**易被误判**的点：`ext/config.py` 的 `CAPTURE_MODES` 常量**在 `ext/` 内无任何消费点**
（`grep -rn "CAPTURE_MODES" ext/ extension/` ⇒ 只有定义处）
⇒ **真正生效的是插件侧 `extension/offscreen.js` 的 `allowedCaptureModes`**
⇒ 二者是**同名不同源**，勿误以为改 Python 常量就能改插件行为。

---

## §24.4 ★★ 时间戳口径修正（**禁止推算** ⇒ 必须用实测）

★ 上一会话在 §22 / §23 标题与 STATUS 头部写了 **`2026-11-01 16:45`**，但：

| 证据 | 实测值 |
|---|---|
| `status/STATUS_EXT.md` 的**落盘 mtime** | **2026-11-01 16:27:19** |
| 上一会话**末次心跳**（`leases/ext.json` 的 `prev.beat`） | **16:28:10** |
| `status/notes/sec22_23_...md` mtime | 16:19:44 |
| `release/V20_HANDOFF.md` mtime | 16:17:50 |
| `tests/smoke/ext031_fake_pkg_launch.py` mtime | 16:15:42 |

⇒ **16:45 从未发生过**（比落盘晚 18 min、比死亡晚 17 min）⇒ 属**预写/推算值**。
⇒ 本轮**落库前**按「「更新时间」用实测时间（禁止推算）」把 **§22 / §23 标题**改为 **16:27**、
头部「更新时间」改为**本轮实测**；**§22 / §23 的结论与数字一字未改**。

---

## §24.5 本轮压缩动作（EXT-016 限额内）

| 动作 | 依据 |
|---|---|
| §22 / §23 的内联正文**压缩为结论式** | 全量明细**已完整**在 `status/notes/sec22_23_ext030_lease_ext031_handoff.md`（13 272 B）⇒ 无信息丢失 |
| 「最近章节」表**去掉 §19/§20 行 + 其内联小节** | EXT-016「最近章节只保留最近 3 节」——加了 §24 后窗口为 §21 / §22·§23 / §24；§19/§20 明细在 `notes/sec19_20_closeout.md`（已入库），结论仍在「当前有效结论」表的 T-5 / T-6 两行 |
| `status/_surgery5.py`（上一会话的一次性改写脚本）**移入 `.tmp/`** | git 历史里**从未**提交过任何 `_surgery*.py`（`git log --all --name-only | grep -i surgery` ⇒ 0 命中）⇒ 属**临时件**；但**不删**（移入 gitignore 的 `.tmp/` 保留），避免**下一轮 `git status` 永不为干净**⇒ 幂等判定失灵 |

---

## §24.6 ⛔ 明确未做 / 不宣称

- ⛔ **打包未做**（EXT-031 明确「打包由 App 线程执行（APP-057），EXT 只交清单」）⇒ **未产出任何 zip**。
- ⛔ **音色克隆仍不可用**（`voice_source` 实测全 `'preset'`、`clone_wired=false`）⇒ **不宣称克隆音色可用**。
- ⛔ **tabCapture 生产路径未实测**（自动化拿不到 ⇒ 需用户点一次扩展图标）。
- ⛔ 端到端仍不实时（RTF **2.0507** / TTS **1.0022**）⇒ **由主会话转达 TTS 模块**。
- ⛔ 同步误差仍超标（`sync_err_ms.p50=67289.3` / `n_over_target=22`）。
- ⛔ **Edge 真实手势 1 分钟验收未做**（需用户本人）。
- ⛔ **未改任何引擎文件**（ASR / MT / TTS 一行未动）；⛔ **未改 `shared/tools/session_lease.py`**（只读使用）。
- ⛔ **未推远程**；⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（未 `git add -f`）。

### ★★ 如实报给 reviewer 的两个「制度性缺口」（非本模块可修）

1. **闸门 exit 1 只判「认领」，不判「收口」** ⇒ 一个会话「做完就死」时，下一轮会**直接跳过**，
   成果**永久搁浅**（本轮即遇到此情形）⇒ 建议闸门或其配套检查**额外校验「`last_ack` 对应的 EXT 编号
   是否在 `EXEC_LOG.md` 里有记录 + 是否已入库」**。
2. **`session_lease.py` 的 TTL = 30 min** ⇒ 上一会话若「30 min 内活跃但已卡死」，新会话会**干等 30 分钟**
   ⇒ reviewer 若想缩短等待，可把 `TTL_MIN` 调到 **10–15**（★ 本模块**不改**该脚本 —— reviewer 部署、只读使用）。

---

## §24.7 本轮**落库内容清单**（提交范围 = **本模块文件**）

| 类别 | 文件 | 状态 |
|---|---|---|
| **产品代码** | `ext/bridge.py`（`--audio-dump-out` / `--margin-out` 的 `RELEASE_MODE` 保护） | 上一会话改，本轮**复核后**提交 |
| **产品代码（删除）** | `extension/probe-worklet.js`（391 B，**全目录零引用** ⇒ 遗留探针件） | 上一会话 `git rm`，本轮提交 |
| **交付物** | `release/V20_HANDOFF.md`（**16 361 B**） | 上一会话写，本轮提交 |
| **明细** | `status/notes/sec22_23_ext030_lease_ext031_handoff.md`（**13 272 B**） | 上一会话写，本轮提交 |
| **明细（本轮新建）** | `status/notes/sec24_takeover_closeout.md`（本文件） | 本轮 |
| **自测** | `tests/test_ext031_release_handoff.py`（**14 247 B**，24 PASS / 0 FAIL） | 上一会话写，本轮提交 |
| **自测** | `tests/smoke/ext031_fake_pkg_launch.py`（**10 025 B**，6 PASS / 0 FAIL） | 上一会话写，本轮提交 |
| **状态文件** | `status/STATUS_EXT.md`（新增 `## §24` + 头部 `last_ack`=EXT-031 + 更新时间=实测 + 压缩回限额内） | 本轮 |
| **状态文件** | `status/EXEC_LOG.md`（追加本轮记录） | 本轮 |
| ⛔ **不入库** | `status/CORRECTIONS_EXT.md` | reviewer 独占（已 gitignore，**未** `git add -f`） |
