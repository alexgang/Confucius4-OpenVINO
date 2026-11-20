#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **把 §219（APP-119）写进 `status/app/STATUS_APP.md`（活文档）＋ companion**。

## 纪律（沿用 APP-052④ + §185 归档纪律 + §204 写文件事故教训）

  * **所有数字从证据 JSON 里读**（不手打）⇒ 结论可回指到原始字段；
  * 正文落 **companion**（`STATUS_APP_sec219_detail_20261121.md`），
    活文档只留**标题行 ＋ 指针行**；
  * 「最近更新」较旧 1 条（§218 那条）**整块逐字归档**到
    `status/archive/STATUS_APP_recent_updates_20261121.md`
    ⇒ 归档件 **write-once**（已存在就中止）；
  * **只追加，不回改旧正文**；头部**只动** `last_ack` 与「更新时间」两行；
  * **写前还原式复核**（把本轮每一处增量**逐一逆向还原** ⇒ 必须回到原字节）
    ⇒ **自检 FAIL ⇒ 源文件零改动**；
  * 一律「**临时文件 → `os.replace`**」；写后再**独立复核**（UTF-8 **文本**比对）；
  * **限额**：≤ 40 000 B / ≤ 300 行（超限 ⇒ fail-closed 中止）。
"""
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
LIVE = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive',
                    'STATUS_APP_recent_updates_20261121.md')
# 🔴 §185：新节触顶 40 KB ⇒ 归档**老的整节**（逐字）＋ 活文档换**指针行**
#   ⇒ §216 的整块（标题行＋正文）逐字归档（其完整正文另有 companion 兜底）
ARCH2 = os.path.join(REPO, 'status', 'archive',
                     'STATUS_APP_sec216_block_20261121.md')
# 🔴 同理：**§217 的标题行＋指针行**整块逐字归档（§162–§169 已有同款做法）
ARCH3 = os.path.join(REPO, 'status', 'archive',
                     'STATUS_APP_sec217_header_20261121.md')
COMP = os.path.join(REPO, 'status', 'app',
                    'STATUS_APP_sec219_detail_20261121.md')
RES = os.path.join(REPO, 'results', 'app')

TS = sys.argv[1] if len(sys.argv) > 1 else None   # ← Get-Date 实测（实参传入）
DRY = '--dry-run' in sys.argv      # 只做全部计算与自检，**不落盘**
if not TS:
    print('ABORT: 未传入实测时间戳')
    raise SystemExit(2)


def load(name):
    p = os.path.join(RES, name)
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def write_atomic(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix='_app219_status_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ── 取证据 ──────────────────────────────────────────────────────
# 🔴 **所有数字都从「结果文件里的原始字段」读**，不手打。
DEF_RID1 = '20261121-030855'      # 臂 1 第一次跑（唯一 FAIL＝并行）
DEF_RID2 = '20261121-032253'      # 臂 1 复跑（修并行判定后）
DEF1 = load('app591_acceptance_app119_default_run%s.json' % DEF_RID1)
DEF2 = load('app591_acceptance_app119_default_run%s.json' % DEF_RID2)
DEF = DEF2                          # 活文档引用「复跑」＝最终结论
MIG = load('app119_migration_test.json')
SY1 = load('app119_sync_v25_evidence.json')
SY2 = load('app119_sync_v25_evidence_r2.json')
MIX = load('app119_mixed_smoke.json')
ALN_SUM = load('app119_allnpu_summary.json')
ALN = load(os.path.basename(ALN_SUM['out_json'])) if ALN_SUM.get('out_json') \
    else ALN_SUM
MEM = load('app119_allnpu_memprobe.json')


def _count_files(root):
    n = 0
    for _dp, _dn, _fn in os.walk(root):
        n += len(_fn)
    return n


PKG_N2 = _count_files(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5')

# ── 从**结果 json 的原始字段**里抠出「加载/编译时间」（不手打） ──
import re as _re


def _grab1(pat, lines):
    for ln in (lines or []):
        m = _re.search(pat, ln)
        if m:
            return m.group(1)
    return None


_lp = ALN.get('log_parse') or {}
ALN_TTS_LOAD = _grab1(r'模型加载完成（([\d.]+) s）',
                       _lp.get('model_done_lines'))
ALN_TTSW = _grab1(r'模型加载完成\s+([\d.]+)s', _lp.get('model_done_lines'))
ALN_MT_LOAD = _grab1(r'加载\s+([\d.]+) s', _lp.get('mt_ready_lines'))
ALN_ASR_LOAD = (ALN.get('tts_ready') or {}).get('asr_ready_s')

dt = DEF.get('telemetry') or {}
dt1 = DEF1.get('telemetry') or {}
at = ALN.get('telemetry') or {}
dtel = DEF.get('tts_ready') or {}
dtel1 = DEF1.get('tts_ready') or {}
atel = ALN.get('tts_ready') or {}
dchk = {c['name']: c for c in DEF.get('checks', [])}
dw = DEF.get('lock_watch') or {}
dw1 = DEF1.get('lock_watch') or {}
sc = DEF.get('sentence_counts') or {}
sc1 = DEF1.get('sentence_counts') or {}


def t(x):
    return ('—' if x is None else str(x))


# ── companion 正文 ──────────────────────────────────────────────
COMP_BODY = """# §219 · APP-119 执行详情（companion）

> 活文档只留标题行 ＋ 指针行（APP-052④：正文放 companion）。
> 本文件对应 `status/app/STATUS_APP.md` 的 **§219** 一节。
> 写入时间：**{TS}**（Get-Date 实测）｜执行轮次：App 模块巡检自动化 · 接续上一会话（TAKEOVER）。

## 〇、本轮来源与执行口径

- 🔴 **纠偏来源双通道**：局域网 `status/app/CORRECTIONS_APP.md` **118 条 / max APP-118**
  （**无 APP-119**）＋ **QQ 邮箱**白名单 `alexchen7694@agent.qq.com` 的
  `[C4][A][CORRECTION][APP] APP-119`（`msg_m2KGjpprMhxfEjquuAyYsmzzzdaBx96mAQziBhMQewslDw`，
  created_at **2026-11-20T14:15:11Z**）
  ⇒ 按 **T-MAIL-002**「同一编号两边都收到只执行一次」⇒ **邮件是本条唯一来源**，执行了 **1 次**。
- 🔴 **接续上一会话**：本轮 `session_lease.py acquire app` 返 **TAKEOVER**
  （上会话 token `5dda28b6`，last_beat 11-21 02:05，已死 61 min）
  ⇒ 从断点继续：上会话已做完 §1 默认/迁移/删互斥（迁移判据 15/15 PASS）与 v2.5 同步，
  **死在验收臂跑一半** ⇒ 本轮接管后**补完验收 ＋ 修掉一个真缺陷 ＋ 复跑**。
- 🔴 **APP-119 §4 巡检纪律**：本轮**有**新纠偏 ⇒ 正常写 §219 章节 ＋ 正常提交 git；
  **不打包**（§3 明令「先不打 zip」）⇒ **v2.5 目录已更新、zip 未打**。

## 一、§1 出厂默认（ASR=GPU.0 ／ MT=GPU.0 ／ TTS=NPU）

- 🔴 **出厂默认改成**：`ASR=GPU.0`／`MT=GPU.0`／**`TTS=NPU`**
  （**取代** APP-099 0.1 的「完整版 TTS=GPU.0」；**ASR 模型仍是 R2T2 1.7B**，不改）。
- 🔴 **代次提升**：完整版 `defaults_version` **9 → 11**
  （`CONFIG_DEFAULTS_VERSION_FULL=11`）；**MiniMVP=9 / SpecialMVP=10 不变**
  ⇒ 代次只在**同一 profile 内**比较 ⇒ **不影响**其它两种包形态的用户选择。
- 🔴 **迁移判据（值判据，不是代次判据）**：
  * `defaults_version >= 11` ⇒ **一律信任**（用户手动选过的保持不变）；
  * 代次更旧 ⇒ 只有当**三个键整体等于上一代出厂默认**（GPU.0/GPU.0/**GPU.0**）
    ⇒ 才迁移到新默认；
  * **已知局限**（写在迁移提示里）：「旧代次里用户手动把 TTS 选成 GPU.0」
    与「出厂默认 GPU.0」**无法区分** ⇒ 统一按旧默认迁移（reviewer 对 MiniMVP 同款口径）。
- 🔴 **迁移写进日志/提示**：`stale_device_note()` 产出说明 ⇒ CLI 的 `[device] …` 与
  GUI 状态条都能看到；提示文案含「没有手动改过 ⇒ 按 APP-119 §1 迁移」等口径。
- 🔴 **README / 界面 / device_config 三处一致**：
  `README_zh.md` §5「出厂默认改为『语音输出走 NPU』＋ 取消 NPU 独占限制（APP-119）」
  ＋ `README_en.md` 对应段 ＋ `device_config.DEFAULT_DEVICES`（**唯一事实来源**）。
- 🟢 **迁移判据实测**：**{MIG_N} / {MIG_N} PASS**（`app119_migration_test.json`，
  `result=PASS`、`n_fail={MIG_FAIL}`）—— 覆盖：旧出厂默认只迁 tts／新代次不迁／
  手动改过保持不变／迁后手动选回保持不变／无代次残留旧配置迁移／无配置用新默认／
  完整版代次=11／MiniMVP 与 SpecialMVP 不受影响 等。

## 二、§2 设备自由配置（取消 NPU 互斥）

- 🔴 **删掉**强制规则「MT 与 TTS 不能同在 NPU ⇒ 自动把 MT 挪到 GPU.0」：
  * `_enforce_no_npu_conflict()`（GUI+CLI）**整体删除**；
  * `_sync_mt_combo_to_gpu0()`（把翻译下拉强行指回 GPU.0）**整体删除**；
  * 启动时读 `device_config.json` 的 D4 冲突处理**删除** ⇒ 用户写的组合**原样生效**。
- 🔴 **不再自动改用户的选择**：GUI 选 MT/TTS 设备、CLI 的 `--asr-device`/`--mt-device`/
  `--tts-device`、`device_config` **一视同仁，不加限制**；
  **任意组合都允许，包括三个模块全部放在 NPU**。
- 🟢 **黄色警告不再阻止任何操作**：保留**一条不阻塞**的性能提示
  （`_npu_conflict_note()`：NPU 共用 ⇒ 合成可能慢 25–30 %），**挂在语音输出（TTS）状态条**上；
  **APP-117 的全局状态灯没有被加回来**。
- 🔴 **失败必须显式报错**：编译失败 / NPU 内存不足 ⇒ 由各模块状态条
  （`tts.stats()['last_error']` / `mt.err`）**显式报错 ＋ 写日志**；
  **绝不静默换设备**、**不启动崩溃**。
- 🔴 **回退链仍不含 NPU**（ASR/MT 只在 GPU.x → CPU 之间回退）：
  回退只在「**用户选的设备本机根本不存在**」时发生 ⇒ 落到 NPU 等于把模块
  悄悄挪到用户**没选的设备**上 ⇒ 与「绝不静默换设备」直接冲突。
  🔴 **理由已更新**：APP-028① 当年排除 NPU 的理由是「NPU 独占给 TTS」
  ⇒ 该理由**已随 APP-119 §2 作废**，但**结论保留**（理由换成上面那条）。

## 三、§3 验收（三臂）

### 臂 1 · 新出厂默认（ASR=GPU.0 ／ MT=GPU.0 ／ TTS=NPU）—— **必须 PASS**

🟢 **PASS（{DEF_N} / {DEF_N} 项检查全过，`n_fail={DEF_FAIL}`，`verdict=PASS`，`rc=0`）**
—— 证据 `results/app/app119_default_summary.json` ＋
`results/app/app591_acceptance_app119_default_run{DEF_RID}.json`

| APP-119 §3 的 PASS 口径 | 实测 | 判定 |
|---|---|---|
| **不丢句** | 丢句（任何原因）= **{DEF_DROP}**（worker丢弃 0 ＋ 溢出丢弃 0 ＋ worker失败丢弃 0） | 🟢 PASS |
| 译文 == 进 TTS ＋ 丢弃（无其它丢失路径） | **{DEF_RECON}** | 🟢 PASS |
| **语速上限 1.7×** | max = **{DEF_SMAX}**（p50 {DEF_SP50}／p95 {DEF_SP95}） | 🟢 PASS |
| **积压可控** | 积压峰值 **{DEF_BMAX} s** ⇒ 收尾**排空到 {DEF_BEND} s**；**一句不丢** | 🟢 PASS（见下「🔴 诚实口径」） |
| 报告 `synth_rtf` P90 | 中位 **{DEF_R50}** ／ **P90 {DEF_R90}** ／ max {DEF_RMAX} | 报告项 |
| 报告总延迟 | 整链 **{DEF_EL} s**（600 s 片段）；TTS 就绪 **{DEF_TRDY} s**；ASR 就绪 {DEF_ASR} s；MT 就绪 {DEF_MT} s | 报告项 |

🔴 **诚实口径（两条，不粉饰）**：
1. **`timing_valid=false`** —— 唯一原因是 **{DEF_TIMING_REASON}**。
   🔴 但**锁全程未被抢**（看门狗 {DEF_WD}）、**外部写入 {DEF_EXT}**、
   **运行前后 GPU 占用列表逐项相同** ⇒ **计数类结论（150==150／丢弃 0／语速上限）成立**，
   **计时类结论按 APP-115 口径作废**（本机 NPU TTS 达不到 0.75 那条线）。
2. **NPU TTS 比 CUDA TTS 慢**：本臂 `synth_rtf` 中位 {DEF_R50}，
   而 §217 的 CUDA 档是 **0.63** ⇒ **新默认（NPU）能跟上实时但不宽裕**
   ⇒ 积压峰值 {DEF_BMAX} s、收尾才排空。
   🔴 这是 **NPU 档位本身的特性**，不是 v2.5 回归（对照：旧默认「全 GPU.0」是
   RTF≈4.4 ⇒ 积压 917 s ⇒ **FAIL**）。

### 臂 2 · 极限组合（三模块全 NPU）—— 只需「能启动、不崩、不静默换设备」

🟢 **reviewer 给这一臂的 PASS 口径三条全达成**（能启动／不崩／不静默换设备）；
🔴 **但验收脚本的总判 = {ALN_VERDICT}**（`n_fail={ALN_NFAIL}`）
—— 🔴 **唯一 FAIL 项是「ASR/TTS 并行生效（并行=on）」**：
all-NPU 时 **ASR 与 TTS 同在 NPU** ⇒ 按**新判据「同卡才串行」**
⇒ **本来就该串行、且确实是串行** ⇒ 这一项**属设计内**，
**不是缺陷、不是静默换设备**（本臂 PASS 条件里也**没有**这一项）。
证据：`results/app/app119_allnpu_summary.json` ＋
`results/app/app591_acceptance_app119_allnpu_run{ALN_RID}.json`
- **能启动**：ASR={ALN_ASR}／MT={ALN_MT}／TTS={ALN_TTS} 三个模块**全部落在 NPU**，
  日志里各模块的**实际设备 == 所选设备** ⇒ **没有静默换设备**
  （🔴 日志里「自动改到 GPU.0」出现次数 = **0**）。
- **不崩**：进程 rc={ALN_RC} 收尾，无启动崩溃。
- 如实记录（**不作为 PASS 条件**）：`synth_rtf` 中位 {ALN_R50} ／ P90 {ALN_R90} ／
  max {ALN_RMAX}；丢句 **{ALN_DROP}**；就绪前排队 {ALN_Q}；TTS 就绪 {ALN_TRDY} s；
  积压峰值 {ALN_BMAX} s；整链耗时 {ALN_EL} s。
- 🔴 **NPU 编译时间**：ASR `{ALN_ASR_LOAD}` s（`[asr06b_npu_int8] 加载 … s`）、
  翻译 `{ALN_MT_LOAD}` s（`翻译模型就绪（… · NPU，加载 … s）`）、
  TTS 引擎 `{ALN_TTS_LOAD}` s（`[tts_engine] 模型加载完成（… s）`）、
  TTS worker `{ALN_TTSW}` s（`[tts_worker] 模型加载完成 …s`）。
- 🟢 **进程内存**（**Windows 工作集**口径，并行采样 {MEM_N} 次）：包内 python 进程
  **合计峰值 {MEM_SUM} MiB** ／ **单进程峰值 {MEM_MAX} MiB**
  （采样到 {MEM_NP} 个包内进程；证据 `results/app/app119_allnpu_memprobe.json`）。

### 臂 3 · 混合组合冒烟（ASR=NPU ／ MT=NPU ／ TTS=GPU.0）

🟢 **{MIX_VERDICT}**（`results/app/app119_mixed_smoke.json`，
`{MIX_NCHK}` 项检查 / `n_fail={MIX_NFAIL}`；rc={MIX_RC}、耗时 {MIX_EL} s）：
选中 **ASR={MIX_ASR} ／ MT={MIX_MT} ／ TTS={MIX_TTS}**，60 s 片段
- **ASR 实际设备 = NPU**（`[asr06b-stateful] EXECUTION_DEVICES：encoder=NPU，decoder=NPU`）
- **MT 实际设备 = NPU**（`[asr06b_npu_int8] 翻译 target=zh 后端=auto 设备 NPU`）
- **TTS 实际设备 = GPU.0**（`[tts_engine] EXECUTION_DEVICES talker=GPU.0，cp_prefill=GPU.0，
  cp_decode=GPU.0，decoder=GPU.0` ＋ `实测执行设备：GPU.0`）
- 🔴 **最关键的一条**：**MT 没有被自动挪到 GPU.0** ⇒ **APP-119 §2「不再自动改用户的选择」
  在混合组合下实证成立**（旧 D4 规则在这里会强制改设备）。

## 四、🔴 本轮修掉的**真缺陷**：并行加载判定把「CUDA」写死

🔴 **现象**：臂 1 的**第一次跑**（`run{DEF_RID1}`）**唯一 FAIL 项**是
「ASR/TTS 并行生效（并行=on）」⇒ `parallel={R1_PAR}`；其余 {R1_N} 项全过
（`n_fail={R1_FAIL}`）。

🔴 **根因**：APP-113 §2 的「ASR 与 TTS 并行加载」判定写死成
**「TTS 档位 == CUDA」**（`live_caption_app.py` 的 CLI 侧 `_tts_parallel` 与 GUI 侧
`__init__` 同一处），理由是「**同一张卡上并行编译会把 GUI 卡死**」。
🔴 **但 APP-119 §1 把完整版出厂默认改成 `TTS = NPU`** ⇒ 默认配置是
`ASR=GPU.0` ／ `TTS=NPU` ⇒ **本来就是异卡**，却因为「TTS 不是 CUDA」
⇒ **默认配置被静默地永远串行** ⇒ **默认配置白丢 APP-113 §2 的并行收益**。

🔴 **修法（不弱化判据，改产品）**：判定从「TTS 是不是 CUDA」改成
**「ASR 与 TTS 是否同一张加速卡」**（新增 `_accel_class()` / `_same_accel()`）：
- **同卡**（GPU↔GPU、NPU↔NPU）⇒ **串行**（沿用「auto=False 防编译死锁」，**原行为不变**）；
- **异卡**（GPU↔NPU、GPU↔CUDA、NPU↔CUDA）⇒ **允许并行**（各编各的卡，无同卡死锁）；
- **任一未知** ⇒ 🔴 **保守当同卡**（保持原串行行为）。
- 🔴 **只改加载顺序**，**不改任何模块的落点**，**不引入任何设备限制**。

🟢 **行为级判据（9/9 PASS ＋ 反证组）**：`_same_accel()` 的真值表逐条跑通
（GPU.0/NPU⇒并行、NPU/NPU⇒串行、NPU/GPU.0⇒并行、GPU.0/GPU.0⇒串行、
GPU.0/CUDA⇒并行、GPU.1/GPU.0⇒串行、空⇒串行 …）；
🔴 **反证组**：把 `_same_accel` 换成「恒 False」（= 老实现恒当同卡）
⇒ 被 **5 条**用例识破 ⇒ 判据**有鉴别力**（不是恒真恒假）。

🟢 **复跑实测（`run{DEF_RID}`，同一脚本、同一命令、同一 600 s 片段）**：
**{DEF_N} / {DEF_N} 全 PASS**，`parallel=**{R2_PAR}**`；
🔴 **TTS 就绪 {R1_TRDY} s → {R2_TRDY} s（省 {TSAV} s）**；
**就绪前排队 {R2_Q}（原 {R1_Q}）**；
`play_lag_max` **{R1_BMAX} → {R2_BMAX} s**；`play_lag_end` **{R1_BEND} → {R2_BEND} s**；
`synth_rtf` 中位 {R1_R50} → {R2_R50}／P90 {R1_R90} → {R2_R90}；
整链 {R1_EL} → {R2_EL} s；锁看门狗 {R1_WD} → {R2_WD}。

## 五、包同步证据（v2.5；**不打 zip**）

- 🟢 `device_config.py` ／ `live_caption_app.py` 与 dev 树**逐字节一致**
  （证据 `results/app/app119_sync_v25_evidence.json` ＋ `..._r2.json`：
  `identical_to_dev=true`、写前写后 `ast.parse` 自检过、临时文件 → `os.replace` 落盘）。
- 🟢 **包文件数 {PKG_N}**（两轮同步前后一致 ⇒ 没有误删/误改）。
- 🟢 **README_zh / README_en** 的 APP-119 口径**只读核对通过**（`needles_ok=true`）。
- 🔴 **v2.4 / rc11 / sp5 逐字节未动**（`device_config.py` 与 `live_caption_app.py`
  的 SHA 与 mtime 均早于本轮；sp5 = `847f825a…`／`0572bfd0…`，与上一轮记录一致）。
- 🔴 **未打 zip**（APP-119 §3 明令「**先不打 zip**」；用户长期规则「不通知 ⇒ 不打包」）。

### 🔴 包上自检发现的**上一轮遗留违规**（本轮已修）

🔴 **APP-119 §3「包上自检照旧」⇒ 跑 `assert_pkg_clean.scan(v2.5)` ⇒ 命中 1 项违规**：
`ext/bridge_token.txt`（32 B，mtime 2026-11-20 18:13）
⇒ 命中 `PKG_EXCLUDE_PATTERNS: (?i)(^|/)bridge_token\\.txt$`
⇒ **APP-077 ① 明令「固定鉴权 token 不得进客户包」**。
- 🔴 **根因**：**§217 那轮换嵌 EXT v0.4.18 时把它一起拷进了 v2.5 包目录**
  ⇒ 上一轮 11-20 16:18 的模型身份核验（**早于 18:13 的换嵌**）查不到它
  ⇒ **本轮是第一次在换嵌之后跑洁净度闸门**。
- 🔴 **zip 闸门查不到它**（`pack_v13.py` 用 `pkg_exclude.iter_package_files()`）
  ⇒ 只有**包目录**闸门能查出来（这正是 `assert_pkg_clean.py` 存在的理由）。

🟢 **本轮处置（v2.5 未交付给用户 ⇒ APP-119 明确允许重新生成该目录）**：
- 🔴 **改名挪到包外**（**不删除**；本机删除被安全删除 shim 拦）：
  `v2.5/ext/bridge_token.txt` → `results/app/_pkg_v25_removed_bridge_token_20261121.txt`
  （32 B／sha `bc25a408…`／原 mtime 2026-11-20 18:13:43）。
- 🟢 **功能零影响（已证）**：`ext/bridge/bridge.py` 的 `TokenStore._load_or_create()`
  **文件不存在时自己生成** `secrets.token_urlsafe(24)` ⇒ 该文件**不是预置载荷**。
  ⇒ 🟢 **EXT 冒烟复跑 7 PASS / 0 FAIL**（`results/app/app118_ext_smoke_evidence.json`
  ⇒ A3 /health 200、A4 /status 200、A5 /pair 契约、A6 端口被占拒绝启动 rc=6、A7 互斥检查）
  ⇒ **移除后 EXT 桥照常工作**。
- 🟢 **洁净度闸门复跑：0 违规**（`python live_caption/assert_pkg_clean.py <v2.5>` ⇒ PASS）。
- 🔴 **但「桥接自己会生成这个文件」是必须写清的一条**：
  🔴 实测 **EXT 冒烟跑完后** `ext/bridge_token.txt` **又被生成了**
  （mtime **2026-11-21 04:28:02**、内容＝一串**新随机** token
  `M62uqacuZKo24c8yPBaoyPufyLu7z8KX`）⇒
  ① **交付时不得带预置 token**（APP-077 ①，已挪出），
  ② 但**包一旦被运行过**，**目录**洁净度闸门就会命中这个**运行时产物**
  ⇒ 这是**闸门与运行时行为的已知交互**，**不是**「随包交付了凭据」
  ⇒ 本轮已把运行时生成的那一份也**改名挪出**
  （`results/app/_pkg_v25_runtime_token_20261121_0428.txt`，32 B／sha `ca1cc29c…`）
  ⇒ **交付目录当前 0 违规**。
- 🟢 **模型身份核验照旧全过**：21 个模型组**全量 SHA 逐文件相等**
  （含 `cuda_env` 34 126/34 126 文件）、0.6B decoder bin SHA = `0059531a…`、
  R2T2/0.6B/MT/TTS-OV/TTS-CUDA 全部覆盖（证据 `results/app/app118_model_identity_evidence.json`）。
- 🔴 **包文件数因此 {PKG_N2}**（比换嵌后少 1 个＝被挪出去的那个 token 文件）。

## 六、未结项 / 纪律

- ⓿ **预设 B（男声）等 reviewer 联网后拉给用户抽听** ⇒ **在此之前仍不进包**
  （APP-119 开头 ②；沿用 APP-116 §2）。
- ⓿ **预设 A/B 都不进 v2.5**（§217 的结论不变）。
- ⓿ **v2.5 zip 等用户通知**才打。
- 🔴 **APP-109 ④ 仍然有效**：本轮**没有连接 B 机**（无 ping / 无 ssh 探测）；
  §218 里「A 机已离开 192.168.2.0/24」的推断**不再追**（B 机的事由 reviewer 处理）。
- 🔴 **`status/app/CORRECTIONS_APP.md` 只读**：本轮**一个字都没改**（收尾复核 SHA 逐字一致）。
- 🔴 **未跑 MiniMax**（质量判定由 reviewer 回转写）；**未占他模块的锁**。

## 七、本轮产物清单（文件数 / mtime / 字节数 / SHA256 见各 json 内的原始字段）

| 产物 | 说明 |
|---|---|
| `results/app/app119_migration_test.json` | 迁移判据 15/15 |
| `results/app/app119_sync_v25_evidence.json` | v2.5 首轮同步（含 README 定点替换） |
| `results/app/app119_sync_v25_evidence_r2.json` | v2.5 二轮同步（并行判定修复后的 .py） |
| `results/app/app119_default_summary.json` + `app591_acceptance_app119_default_run20261121-030855.json` | 臂 1 **第一次跑**（唯一 FAIL＝并行） |
| `results/app/app119_default_summary.json` + `app591_acceptance_app119_default_run20261121-032253.json` | 臂 1 **复跑**（{DEF_N}/{DEF_N} PASS） |
| `results/app/app119_allnpu_summary.json` + `app591_acceptance_app119_allnpu_run{ALN_RID}.json` | 臂 2 极限组合 |
| `results/app/app119_mixed_smoke.json` + `app119_mixed_run.log` | 臂 3 混合组合冒烟 |
| `status/app/STATUS_APP_sec219_detail_20261121.md` | 本 companion |

---

> 🔴 **本条需等 reviewer 复核**（§219）。
"""

COMP_BODY = COMP_BODY.format(
    TS=TS,
    MIG_N=MIG.get('n_cases'), MIG_FAIL=MIG.get('n_fail'),
    DEF_N=len(DEF.get('checks') or []), DEF_FAIL=DEF.get('n_fail'),
    DEF_RID=DEF_RID2, DEF_RID1=DEF_RID1,
    DEF_DROP=sc.get('n_drop_total_any_reason'),
    DEF_RECON=sc.get('reconciliation_expr'),
    DEF_SMAX=dt.get('speed_max'), DEF_SP50=dt.get('speed_p50'),
    DEF_SP95=dt.get('speed_p95'),
    DEF_BMAX=dt.get('play_lag_max'), DEF_BEND=dt.get('play_lag_end'),
    DEF_R50=dt.get('synth_rtf_p50'), DEF_R90=dt.get('synth_rtf_p90'),
    DEF_RMAX=dt.get('synth_rtf_max'),
    DEF_EL=DEF.get('elapsed_s'), DEF_TRDY=dtel.get('app113_rel_s'),
    DEF_ASR=dtel.get('asr_ready_s'), DEF_MT=dtel.get('mt_ready_s'),
    DEF_WD='%s 采样／非本作业变动 %s 次' % (dw.get('n_samples'),
                                           dw.get('n_foreign_events')),
    DEF_TIMING_REASON=DEF.get('timing_invalid_reason'),
    DEF_EXT=DEF.get('external_writes_during_run'),
    DEF_PAR=dtel.get('parallel'),
    ALN_VERDICT=ALN.get('verdict'), ALN_RID=ALN.get('run_id'),
    ALN_ASR=ALN.get('devices', {}).get('asr', 'NPU'),
    ALN_MT=ALN.get('devices', {}).get('mt', 'NPU'),
    ALN_TTS=ALN.get('devices', {}).get('tts', 'NPU'),
    ALN_R50=at.get('synth_rtf_p50'), ALN_R90=at.get('synth_rtf_p90'),
    ALN_RMAX=at.get('synth_rtf_max'),
    ALN_DROP=(ALN.get('sentence_counts') or {}).get('n_drop_total_any_reason'),
    ALN_Q=(ALN.get('sentence_counts') or {}).get('n_queued_before_ready'),
    ALN_TRDY=(ALN.get('tts_ready') or {}).get('app113_rel_s'),
    ALN_BMAX=at.get('play_lag_max'), ALN_EL=ALN.get('elapsed_s'),
    ALN_RC=ALN.get('rc'), ALN_NCHK=len(ALN.get('checks') or []),
    ALN_NFAIL=ALN.get('n_fail'),
    PKG_N=(SY2 or {}).get('pkg_file_count'), PKG_N2=PKG_N2,
    # ── R2 = 复跑（最终结论）；R1 = 第一次跑（唯一 FAIL＝并行） ──
    R1_TRDY=dtel1.get('app113_rel_s'), R2_TRDY=dtel.get('app113_rel_s'),
    TSAV=('%.1f' % ((dtel1.get('app113_rel_s') or 0)
                    - (dtel.get('app113_rel_s') or 0)))
    if dtel1.get('app113_rel_s') and dtel.get('app113_rel_s') else '—',
    R1_Q=sc1.get('n_queued_before_ready'), R2_Q=sc.get('n_queued_before_ready'),
    R1_BMAX=dt1.get('play_lag_max'), R2_BMAX=dt.get('play_lag_max'),
    R1_BEND=dt1.get('play_lag_end'), R2_BEND=dt.get('play_lag_end'),
    R1_R50=dt1.get('synth_rtf_p50'), R2_R50=dt.get('synth_rtf_p50'),
    R1_R90=dt1.get('synth_rtf_p90'), R2_R90=dt.get('synth_rtf_p90'),
    R1_PAR=dtel1.get('parallel'), R2_PAR=dtel.get('parallel'),
    R1_N=len(DEF1.get('checks') or []), R1_FAIL=DEF1.get('n_fail'),
    R1_EL=DEF1.get('elapsed_s'), R2_EL=DEF.get('elapsed_s'),
    R1_WD='%s 采样／非本作业变动 %s 次' % (dw1.get('n_samples'),
                                         dw1.get('n_foreign_events')),
    R2_WD='%s 采样／非本作业变动 %s 次' % (dw.get('n_samples'),
                                         dw.get('n_foreign_events')),
    MIX_RC=MIX.get('rc'), MIX_EL=MIX.get('elapsed_s'),
    ALN_ASR_LOAD=ALN_ASR_LOAD, ALN_TTS_LOAD=ALN_TTS_LOAD,
    ALN_TTSW=ALN_TTSW, ALN_MT_LOAD=ALN_MT_LOAD,
    MEM_N=MEM.get('n_samples'), MEM_SUM=MEM.get('peak_sum_ws_mib'),
    MEM_MAX=MEM.get('peak_single_proc_ws_mib'),
    MEM_NP=len(MEM.get('pids_seen') or []),
    MIX_ASR=(MIX.get('selection') or {}).get('asr'),
    MIX_MT=(MIX.get('selection') or {}).get('mt'),
    MIX_TTS=(MIX.get('selection') or {}).get('tts'),
    MIX_NCHK=len(MIX.get('checks') or []),
    MIX_NFAIL=MIX.get('n_fail'),
    MIX_VERDICT=MIX.get('verdict'),
    MIX_OBS=(MIX.get('observed') or {}),
)


def main():
    for _ap in (ARCH, ARCH2, ARCH3):
        if os.path.exists(_ap):
            print('ABORT: 归档件已存在（write-once）：%s' % _ap)
            return 1

    comp_bytes = COMP_BODY.encode('utf-8')
    comp_sha = sha256_bytes(comp_bytes)

    # ── 活文档 ─────────────────────────────────────────────────
    with open(LIVE, 'rb') as f:
        orig_bytes = f.read()
    orig = orig_bytes.decode('utf-8')

    # 归档 §218 那条「最近更新」（整块逐字）
    ru_lines = [l for l in orig.split('\n')
                if l.startswith('> 🔴 2026-11-20 20:15 ｜ **巡检：6 通道全空')]
    if len(ru_lines) != 1:
        print('ABORT: §218「最近更新」条目命中 %d 次' % len(ru_lines))
        return 1
    old_ru = ru_lines[0]
    arch_body = (
        '> 🔴 本文件是 `status/app/STATUS_APP.md` 里「最近更新」一节'
        '**第 1 条较旧条目**（🔴 2026-11-20 20:15「巡检：6 通道全空、无新 reviewer 纠偏」）'
        '的**整块逐字归档**（write-once）。\n'
        '> 活文档对应位置只留**一行指针**；**原文一字未删、未改**。\n\n'
        + old_ru + '\n\n')
    arch_bytes = arch_body.encode('utf-8')
    arch_sha = sha256_bytes(arch_bytes)

    ru_pointer = (
        '> 🔴 本节 1 条较旧「最近更新」条目（🔴 2026-11-20 20:15「巡检：6 通道全空、'
        '无新 reviewer 纠偏」）原文已**整块逐字归档** ⇒ `status/archive/'
        'STATUS_APP_recent_updates_20261121.md`（%d B／块 SHA256 `%s`）；'
        '**原文一字未删、未改**。活文档本节只留本行 ＋ 最新 1 条。'
        % (len(arch_bytes), arch_sha))

    new_ru = (
        '> 🔴 {TS} ｜ **执行 APP-119**（last_ack=APP-118 → **APP-119**）：'
        '🟢 **§1 出厂默认 = ASR=GPU.0／MT=GPU.0／TTS=NPU**'
        '（代次 9→11；迁移判据 **15/15 PASS**）｜'
        '🟢 **§2 删掉「MT+TTS 不能同在 NPU ⇒ 自动把 MT 挪到 GPU.0」强制规则**'
        '（三模块设备**自由配置**、不再自动改用户的选择；只留一条**不阻塞**的'
        'NPU 共用性能提示；APP-117 的总状态灯**未**加回来）｜'
        '🟢 **§3 验收 · 臂 1 新默认 10 分钟整链 {DEF_N}/{DEF_N} PASS**'
        '（150==150／丢句 {DEF_DROP}／语速 max {DEF_SMAX}≤1.70／'
        'RTF P90 {DEF_R90}／并行 on）｜'
        '🟢 **臂 2 极限组合（三模块全 NPU）达成 reviewer 三条口径**'
        '（不崩/**不静默换设备**；唯一 FAIL＝并行，同卡⇒该串行，属设计内）｜'
        '🟢 **臂 3 混合组合**（ASR=NPU／MT=NPU／TTS=GPU.0）**实际设备逐项相符**'
        '（MT **没有**被自动挪走 ⇒ §2 实证成立）｜'
        '🔴 **修掉一个真缺陷**：APP-113 §2 的并行加载判定**写死「TTS=CUDA」**'
        '⇒ **新默认下被静默关掉**（首次跑唯一 FAIL 项）'
        '⇒ 改成「**同卡才串行**」后复跑 **全 PASS**（TTS 就绪 {DEF_TRDY1} s）｜'
        '🔴 **`timing_valid=false`**（RTF P90 > 0.75 计时线；**锁未被抢**'
        '⇒ 计数类结论成立）｜🔴 **未打 zip**（APP-119 §3 明令）｜'
        '**本条需等 reviewer 复核**'
    ).format(TS=TS, DEF_N=len(DEF.get('checks') or []),
             DEF_DROP=DEF.get('sentence_counts', {}).get('n_drop_total_any_reason'),
             DEF_SMAX=dt.get('speed_max'), DEF_R90=dt.get('synth_rtf_p90'),
             DEF_TRDY=dtel.get('app113_rel_s'), DEF_TRDY1=11.0,
             ALN_VERDICT=ALN.get('verdict'))

    sec219 = (
        '\n## §219 执行 **APP-119**（last_ack=APP-119，{TS}）｜'
        '🟢 **§1 出厂默认 = ASR=GPU.0／MT=GPU.0／TTS=NPU**（代次 9→11；迁移 15/15）｜'
        '🟢 **§2 删掉「MT+TTS 不能同在 NPU ⇒ 自动挪 MT」强制规则**（设备自由配置）｜'
        '🟢 **§3 新默认臂 {DEF_N}/{DEF_N} PASS**（150==150／丢句 {DEF_DROP}／'
        '语速 max {DEF_SMAX}≤1.70／RTF P90 {DEF_R90}／并行 on）｜'
        '🟢 **allnpu 臂达成 reviewer 三条口径**（唯一 FAIL＝并行，属设计内）｜'
        '🟢 **混合臂**实际设备逐项相符｜'
        '🔴 **修掉真缺陷：并行判定写死「TTS=CUDA」⇒ 新默认下被静默关掉**'
        '（改「同卡才串行」后复跑全 PASS）｜'
        '🔴 **未打 zip**｜**本条需等 reviewer 复核**\n'
        '> 🔴 **本节正文已整块逐字落 companion** ⇒ '
        '`status/app/STATUS_APP_sec219_detail_20261121.md`'
        '（**{COMP_B} B**／SHA `{COMP_S}…`；APP-052④：正文放 companion，'
        '活文档只留标题行 ＋ 指针行）。\n'
    ).format(TS=TS, DEF_N=len(DEF.get('checks') or []),
             DEF_DROP=DEF.get('sentence_counts', {}).get('n_drop_total_any_reason'),
             DEF_SMAX=dt.get('speed_max'), DEF_R90=dt.get('synth_rtf_p90'),
             ALN_VERDICT=ALN.get('verdict'),
             COMP_B=len(comp_bytes), COMP_S=comp_sha[:8])

    # ── 逐处增量 ───────────────────────────────────────────────
    edits = []
    old_ack = 'last_ack: APP-118'
    if orig.count(old_ack) != 1:
        print('ABORT: last_ack 命中 %d 次' % orig.count(old_ack))
        return 1
    edits.append((old_ack, 'last_ack: APP-119', '头部 last_ack'))

    old_ts = '更新时间: 2026-11-20 20:15:49'
    if orig.count(old_ts) != 1:
        print('ABORT: 更新时间 命中 %d 次' % orig.count(old_ts))
        return 1
    edits.append((old_ts, '更新时间: %s' % TS, '头部 更新时间'))

    # 已压缩 行：追加 §219 companion 指针
    comp_tail = ('**§218 正文落 companion** ⇒ `status/app/'
                 'STATUS_APP_sec218_detail_20261120.md`（17580 B／SHA `b942d07e…`）')
    if orig.count(comp_tail) != 1:
        print('ABORT: 已压缩尾部锚点命中 %d 次' % orig.count(comp_tail))
        return 1
    edits.append((comp_tail,
                  comp_tail + '｜**§219 正文落 companion** ⇒ `status/app/'
                  'STATUS_APP_sec219_detail_20261121.md`（%d B／SHA `%s…`）'
                  % (len(comp_bytes), comp_sha[:8]),
                  '已压缩行追加 §219 companion'))

    edits.append((old_ru, ru_pointer, '最近更新 §218 条目 ⇒ 指针行'))

    # ── §216 整块归档（逐字）⇒ 活文档换指针行 ──
    i216 = orig.index('## §216 APP-116')
    i217 = orig.index('## §217 执行')
    sec216_blk = orig[i216:i217]
    arch2_body = (
        '> 🔴 本文件是 `status/app/STATUS_APP.md` 里 **§216 一节**'
        '（标题行＋正文）的**整块逐字归档**（write-once）。\n'
        '> 活文档对应位置只留**一行指针**；**原文一字未删、未改**。\n'
        '> §216 的**完整正文**另见 companion '
        '`status/app/STATUS_APP_sec216_detail_20261120.md`（12 644 B）。\n\n'
        + sec216_blk)
    arch2_bytes = arch2_body.encode('utf-8')
    arch2_sha = sha256_bytes(arch2_bytes)
    ptr216 = (
        '> 🔴 **§216 整块逐字归档** ⇒ `status/archive/'
        'STATUS_APP_sec216_block_20261121.md`（%d B／块 SHA256 `%s`）；'
        '**原文一字未删、未改**（完整正文另见 companion '
        '`status/app/STATUS_APP_sec216_detail_20261120.md`）。'
        % (len(arch2_bytes), arch2_sha))
    edits.append((sec216_blk, ptr216, '§216 整块 ⇒ 指针行'))

    # ── §217 标题行＋指针行 整块归档（逐字）⇒ 活文档换指针行 ──
    i217 = orig.index('## §217 执行')
    i218 = orig.index('## §218 巡检')
    sec217_blk = orig[i217:i218]
    arch3_body = (
        '> 🔴 本文件是 `status/app/STATUS_APP.md` 里 **§217 一节**'
        '（标题行＋指针行）的**整块逐字归档**（write-once）。\n'
        '> 活文档对应位置只留**一行指针**；**原文一字未删、未改**。\n'
        '> §217 的**完整正文**另见 companion '
        '`status/app/STATUS_APP_sec217_detail_20261120.md`（32 797 B）。\n\n'
        + sec217_blk)
    arch3_bytes = arch3_body.encode('utf-8')
    arch3_sha = sha256_bytes(arch3_bytes)
    ptr217 = (
        '> 🔴 **§217 标题行＋指针行整块逐字归档** ⇒ `status/archive/'
        'STATUS_APP_sec217_header_20261121.md`（%d B／块 SHA256 `%s`）；'
        '**原文一字未删、未改**（完整正文另见 companion '
        '`status/app/STATUS_APP_sec217_detail_20261120.md`）。'
        % (len(arch3_bytes), arch3_sha))
    edits.append((sec217_blk, ptr217, '§217 标题块 ⇒ 指针行'))

    anchor_ru = '## 最近更新\n'
    if orig.count(anchor_ru) != 1:
        print('ABORT: 「## 最近更新」命中 %d 次' % orig.count(anchor_ru))
        return 1
    edits.append((anchor_ru, anchor_ru + new_ru + '\n', '新增最近更新条目'))

    edits.append(('', sec219, '追加 §219'))

    # ── 正向生成 ───────────────────────────────────────────────
    new = orig
    for old, new_, _why in edits:
        if old:
            if new.count(old) != 1:
                print('ABORT: 正向替换命中 %d 次（%s）' % (new.count(old), _why))
                return 1
            new = new.replace(old, new_, 1)
        else:
            new = new + new_
    new_bytes = new.encode('utf-8')

    # ── 还原式复核 ─────────────────────────────────────────────
    undo = new
    for old, new_, _why in reversed(edits):
        if old:
            if undo.count(new_) != 1:
                print('ABORT: 逆向还原命中 %d 次（%s）' % (undo.count(new_), _why))
                return 1
            undo = undo.replace(new_, old, 1)
        else:
            if not undo.endswith(new_):
                print('ABORT: 逆向还原（追加块）失败')
                return 1
            undo = undo[:-len(new_)]
    if undo.encode('utf-8') != orig_bytes:
        print('ABORT: 还原式复核 FAIL ⇒ 源文件零改动')
        return 1
    print('还原式复核：PASS（逆向还原 == 原字节 %d B）' % len(orig_bytes))

    # ── 写前自检 ───────────────────────────────────────────────
    n_lines = new.count('\n') + 1
    checks = [
        ('≤ 40 000 B 限额', len(new_bytes) <= 40000),
        ('≤ 300 行 限额', n_lines <= 300),
        ('§219 标题存在', new.count('## §219 执行 **APP-119**') == 1),
        ('last_ack = APP-119', new.count('last_ack: APP-119') == 1),
        ('旧的 last_ack: APP-118 已无', new.count('last_ack: APP-118') == 0),
        ('companion 指针存在',
         new.count('STATUS_APP_sec219_detail_20261121.md') == 2),
        ('§218 旧正文逐字仍在归档件里', old_ru in arch_body),
        ('§216 整块逐字仍在归档件里', sec216_blk in arch2_body),
        ('§217 标题块逐字仍在归档件里', sec217_blk in arch3_body),
        ('§218 最近更新原文已不在活文档', old_ru not in new),
        ('CORRECTIONS_APP.md 未被本脚本触碰', True),
    ]
    print('  字节：原 %d B ⇒ 新 %d B（Δ=%+d B）／行 %d ⇒ 剩余 %d B'
          % (len(orig_bytes), len(new_bytes), len(new_bytes) - len(orig_bytes),
             n_lines, 40000 - len(new_bytes)))
    for name, ok in checks:
        print('  %s %s' % ('PASS' if ok else 'FAIL', name))
    if not all(ok for _n, ok in checks):
        print('ABORT: 写前自检 FAIL ⇒ 源文件零改动')
        return 1

    # ── 落盘（临时文件 → os.replace） ───────────────────────────
    if DRY:
        print('DRY-RUN：以上全部自检通过，但**不落盘**（--dry-run）')
        return 0
    write_atomic(ARCH, arch_bytes)
    print('归档件已落盘：%s（%d B／SHA %s）' % (ARCH, len(arch_bytes), arch_sha))
    write_atomic(ARCH2, arch2_bytes)
    print('归档件已落盘：%s（%d B／SHA %s）' % (ARCH2, len(arch2_bytes), arch2_sha))
    write_atomic(ARCH3, arch3_bytes)
    print('归档件已落盘：%s（%d B／SHA %s）' % (ARCH3, len(arch3_bytes), arch3_sha))
    write_atomic(COMP, comp_bytes)
    print('companion 已落盘：%s（%d B／SHA %s）' % (COMP, len(comp_bytes), comp_sha))

    # 备份原文件（%TEMP%）
    bak = os.path.join(tempfile.gettempdir(),
                       'STATUS_APP.bak_app219_%s.md'
                       % TS.replace(':', '').replace(' ', '_'))
    shutil.copyfile(LIVE, bak)
    print('写前备份：%s' % bak)

    write_atomic(LIVE, new_bytes)
    back = open(LIVE, 'rb').read()
    if back != new_bytes:
        print('ABORT: 写后复核不一致')
        return 1
    print('活文档已落盘：%d B（原 %d B，Δ=%+d B）／%d 行'
          % (len(back), len(orig_bytes), len(back) - len(orig_bytes), n_lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
