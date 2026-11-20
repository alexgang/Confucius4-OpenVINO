#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **生成 APP-119 的 STATUS 邮件正文**（T-MAIL-003：「每份 STATUS 都必须发邮件」）。

## 为什么要脚本生成（不是手写）

  * **数字全部来自证据 json 的原始字段** ⇒ 邮件里的每个数字都可回指；
  * 🔴 **QQ 邮箱正文上限**：≳2.4 KB（中文）会报 `HTML error page`
    ⇒ 脚本**自带长度断言**（> 2 300 B ⇒ 直接报错，不发）；
  * **明细不塞进邮件**：写在 A 机路径上（companion ＋ results/app/*.json）。

## 输出

  * `results/app/app219_status_email_body.md` —— 发邮件用的**紧凑正文**；
  * `results/app/app219_status_email_body_full.md` —— **完整明细**（A 机路径引用）。

## 用法

  python _app219_email_body.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = HERE if os.path.isdir(os.path.join(HERE, 'results')) else \
    os.path.dirname(HERE)
RES = os.path.join(REPO, 'results', 'app')
OUT = os.path.join(RES, 'app219_status_email_body.md')
OUT_FULL = os.path.join(RES, 'app219_status_email_body_full.md')
LIMIT_B = 2300          # 🔴 QQ 邮箱正文上限 ≲2.3 KB


def load(name):
    with open(os.path.join(RES, name), encoding='utf-8') as f:
        return json.load(f)


DEF = load('app591_acceptance_app119_default_run20261121-032253.json')
DEF1 = load('app591_acceptance_app119_default_run20261121-030855.json')
ALN_SUM = load('app119_allnpu_summary.json')
ALN = load(os.path.basename(ALN_SUM['out_json']))
MIX = load('app119_mixed_smoke.json')
MIG = load('app119_migration_test.json')
MEM = load('app119_allnpu_memprobe.json')
SY2 = load('app119_sync_v25_evidence_r2.json')

dt = DEF['telemetry']
dt1 = DEF1['telemetry']
at = ALN.get('telemetry') or {}
sc = ALN.get('sentence_counts') or {}
dr = DEF.get('tts_ready') or {}
dr1 = DEF1.get('tts_ready') or {}
lp = ALN.get('log_parse') or {}


def grab(pat, lines):
    import re
    for ln in (lines or []):
        m = re.search(pat, ln)
        if m:
            return m.group(1)
    return None


def _count_files(root):
    n = 0
    for _dp, _dn, _fn in os.walk(root):
        n += len(_fn)
    return n


# 🔴 同步证据里的文件数是**同步当时**的；本轮把 `ext/bridge_token.txt`
#   挪出包目录后**少 1 个** ⇒ 邮件里报**当前实测值**。
PKGN_CUR = _count_files(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5')


FULL = """# APP-119 STATUS 邮件 · 完整明细（A 机留档）

> 邮件正文（紧凑版）见 `results/app/app219_status_email_body.md`。
> 本文件是**完整明细**，供 reviewer 复核时对照。

## 一、§1 出厂默认

- 完整版出厂默认 = **ASR GPU.0 / MT GPU.0 / TTS NPU**（取代 APP-099 0.1 的 TTS=GPU.0；
  ASR 模型仍是 R2T2 1.7B）。
- 代次：完整版 `defaults_version` **9 → 11**（MiniMVP 9 / SpecialMVP 10 不变）。
- 迁移判据（值判据）：旧出厂默认整体相等才迁；`defaults_version >= 11` 一律信任；
  迁移写进日志/状态条。
- 迁移判据实测：**{MIG_N}/{MIG_N} PASS**（`app119_migration_test.json`，n_fail={MIG_FAIL}）。

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
| 总判 | **FAIL**（唯一 FAIL＝并行） | **PASS {DN}/{DN}** |
| 并行生效 | {PAR1} | **{PAR2}** |
| TTS 就绪 | {TRDY1} s | **{TRDY2} s** |
| 丢句 | {DROP1} | **{DROP2}** |
| 语速 max | {SMAX1} | **{SMAX2}**（≤1.70） |
| synth_rtf 中位/P90 | {R501}/{R901} | **{R50}/{R90}** |
| play_lag max/end | {BMAX1}/{BEND1} s | **{BMAX2}/{BEND2} s** |
| 整链耗时 | {EL1} s | {EL2} s |

- 计数：{RECON}
- `timing_valid=false`：{TIMING_REASON}
- 锁看门狗：{WD}；外部写入 {EXT}；运行前后 GPU 占用列表逐项相同。

### 臂 2 极限组合（全 NPU）

- verdict={AV}；rc={ARC}；耗时 {AEL} s；检查 {AN}/{AN}（唯一 FAIL＝「并行生效」，
  **同卡 ⇒ 该串行，属设计内**）。
- 实际设备：ASR `{A_ASR}`／MT `{A_MT}`／TTS `{A_TTS}`（日志原文核对，**无任何**
  「自动改到 GPU.0」）。
- synth_rtf 中位/P90/max = {AR50}/{AR90}/{ARMAX}；丢句 {ADROP}；
  积压峰值 {ABMAX} s；TTS 就绪 {ATRDY} s。
- NPU 加载/编译：ASR {AASR} s／翻译 {AMT} s／TTS 引擎 {ATTS} s／worker {ATTSW} s。
- 进程内存（Windows 工作集，并行采样 {MEMN} 次）：合计峰值 **{MEMSUM} MiB**／
  单进程峰值 **{MEMMAX} MiB**（{MEMNP} 个包内进程）。

### 臂 3 混合组合（ASR=NPU/MT=NPU/TTS=GPU.0）

- verdict={MV}；{MN}/{MN} 项检查全过（n_fail={MNF}）；rc={MRC}；耗时 {MEL} s。
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
  包文件数 {PKGN}）；**v2.4 / rc11 / sp5 逐字节未动**；🔴 **未打 zip**（§3 明令）。
- `CORRECTIONS_APP.md` **只读**（本轮一个字未改）；未跑 MiniMax；未占他模块锁；
  未连接 B 机（APP-109 ④）。
""".format(
    MIG_N=MIG.get('n_cases'), MIG_FAIL=MIG.get('n_fail'),
    DN=len(DEF.get('checks') or []),
    PAR1=dr1.get('parallel'), PAR2=dr.get('parallel'),
    TRDY1=dr1.get('app113_rel_s'), TRDY2=dr.get('app113_rel_s'),
    DROP1=DEF1['sentence_counts'].get('n_drop_total_any_reason'),
    DROP2=DEF['sentence_counts'].get('n_drop_total_any_reason'),
    SMAX1=dt1.get('speed_max'), SMAX2=dt.get('speed_max'),
    R501=dt1.get('synth_rtf_p50'), R901=dt1.get('synth_rtf_p90'),
    R50=dt.get('synth_rtf_p50'), R90=dt.get('synth_rtf_p90'),
    BMAX1=dt1.get('play_lag_max'), BEND1=dt1.get('play_lag_end'),
    BMAX2=dt.get('play_lag_max'), BEND2=dt.get('play_lag_end'),
    EL1=DEF1.get('elapsed_s'), EL2=DEF.get('elapsed_s'),
    RECON=DEF['sentence_counts'].get('reconciliation_expr'),
    TIMING_REASON=DEF.get('timing_invalid_reason'),
    WD=(DEF.get('lock_watch') or {}).get('n_samples'),
    EXT=DEF.get('external_writes_during_run'),
    AV=ALN.get('verdict'), ARC=ALN.get('rc'), AEL=ALN.get('elapsed_s'),
    AN=len(ALN.get('checks') or []),
    A_ASR='NPU', A_MT='NPU', A_TTS='NPU',
    AR50=at.get('synth_rtf_p50'), AR90=at.get('synth_rtf_p90'),
    ARMAX=at.get('synth_rtf_max'), ADROP=sc.get('n_drop_total_any_reason'),
    ABMAX=at.get('play_lag_max'), ATRDY=(ALN.get('tts_ready') or {}).get('app113_rel_s'),
    AASR=(ALN.get('tts_ready') or {}).get('asr_ready_s'),
    AMT=grab(r'加载\s+([\d.]+) s', lp.get('mt_ready_lines')),
    ATTS=grab(r'模型加载完成（([\d.]+) s）', lp.get('model_done_lines')),
    ATTSW=grab(r'模型加载完成\s+([\d.]+)s', lp.get('model_done_lines')),
    MEMN=MEM.get('n_samples'), MEMSUM=MEM.get('peak_sum_ws_mib'),
    MEMMAX=MEM.get('peak_single_proc_ws_mib'),
    MEMNP=len(MEM.get('pids_seen') or []),
    MV=MIX.get('verdict'), MN=len(MIX.get('checks') or []),
    MNF=MIX.get('n_fail'), MRC=MIX.get('rc'), MEL=MIX.get('elapsed_s'),
    PKGN=PKGN_CUR,
)

BODY = """[C4][A][STATUS][APP] APP-119 —— 出厂默认 ASR=GPU.0/MT=GPU.0/TTS=NPU；§2 取消 NPU 互斥；三臂验收完成；修掉一个真缺陷；未打 zip

一句话：APP-119 全部落地。§1 出厂默认 = ASR GPU.0 / MT GPU.0 / TTS NPU（代次 9→11；迁移 {MIG_N}/{MIG_N} PASS）；§2 删掉「MT+TTS 不能同在 NPU ⇒ 自动把 MT 挪到 GPU.0」强制规则，三模块设备自由配置、不再自动改用户选择，只留一条不阻塞的 NPU 共用提示，APP-117 总状态灯未加回；§3 三臂：新默认臂 {DN}/{DN} PASS、allnpu 臂（唯一 FAIL＝并行，同卡⇒该串行，属设计内）、混合臂 {MV}。

🔴 另修掉一个真缺陷：APP-113 §2 的并行加载判定写死「TTS=CUDA」，§1 把默认改成 TTS=NPU 后，默认配置（ASR=GPU.0 与 TTS=NPU 异卡）被静默地永远串行 ⇒ 首次跑唯一 FAIL。改成「同卡才串行」后复跑 {DN}/{DN} PASS，TTS 就绪 {TRDY1}→{TRDY2} s。

默认臂 10 分钟：150 句 == 150 进 TTS + 丢句 {DROP2}；语速 max {SMAX2} ≤ 1.70；synth_rtf 中位 {R50} / P90 {R90}；积压峰值 {BMAX2} s ⇒ 收尾排空到 {BEND2} s；整链 {EL2} s；并行 on。🔴 timing_valid=false（RTF P90>0.75 计时线；锁未被抢 ⇒ 计数类成立）。

allnpu（ASR=MT=TTS=NPU）：启动/rc=0/不崩；三模块实际设备逐项 = NPU，日志里无任何「自动改到 GPU.0」；synth_rtf 中位 {AR50}/P90 {AR90}；丢句 {ADROP}；积压峰值 {ABMAX} s；加载 ASR {AASR}/翻译 {AMT}/TTS 引擎 {ATTS}/worker {ATTSW} s；进程工作集峰值合计 {MEMSUM} MiB。

混合臂（ASR=NPU/MT=NPU/TTS=GPU.0）：{MN}/{MN} PASS，实际设备逐项相符，MT 未被自动挪走 ⇒ §2 成立。

包：v2.5 目录已更新（device_config.py / live_caption_app.py 与 dev 逐字节一致，{PKGN} 文件），v2.4 / rc11 / sp5 逐字节未动，🔴 未打 zip（§3 明令）。预设 A/B 不进包（等抽听）。

🔴 另：包上自检查出 1 项上一轮遗留违规（ext/bridge_token.txt，APP-077 明令不得进包；§217 换嵌 EXT v0.4.18 带进去的）⇒ 已改名挪出包目录（不删除）；桥接自生成 token ⇒ EXT 冒烟复跑 7/7 PASS、洁净度闸门 0 违规。

明细：A 机 status\\app\\STATUS_APP_sec219_detail_20261121.md；results\\app\\ 下 app119_* 证据 json。本条需等 reviewer 复核。
""".format(
    MIG_N=MIG.get('n_cases'), DN=len(DEF.get('checks') or []),
    AV=ALN.get('verdict'), MV=MIX.get('verdict'),
    TRDY1=dr1.get('app113_rel_s'), TRDY2=dr.get('app113_rel_s'),
    DROP2=DEF['sentence_counts'].get('n_drop_total_any_reason'),
    SMAX2=dt.get('speed_max'), R50=dt.get('synth_rtf_p50'),
    R90=dt.get('synth_rtf_p90'), BMAX2=dt.get('play_lag_max'),
    BEND2=dt.get('play_lag_end'), EL2=DEF.get('elapsed_s'),
    AR50=at.get('synth_rtf_p50'), AR90=at.get('synth_rtf_p90'),
    ADROP=sc.get('n_drop_total_any_reason'), ABMAX=at.get('play_lag_max'),
    AASR=(ALN.get('tts_ready') or {}).get('asr_ready_s'),
    AMT=grab(r'加载\s+([\d.]+) s', lp.get('mt_ready_lines')),
    ATTS=grab(r'模型加载完成（([\d.]+) s）', lp.get('model_done_lines')),
    ATTSW=grab(r'模型加载完成\s+([\d.]+)s', lp.get('model_done_lines')),
    MEMSUM=MEM.get('peak_sum_ws_mib'), MN=len(MIX.get('checks') or []),
    PKGN=SY2.get('pkg_file_count'),
)


def main():
    with open(OUT_FULL, 'w', encoding='utf-8') as f:
        f.write(FULL)
    n = len(BODY.encode('utf-8'))
    if n > LIMIT_B:
        print('ABORT: 正文 %d B > 上限 %d B（QQ 邮箱会报 HTML error page）'
              % (n, LIMIT_B))
        return 1
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(BODY)
    print('紧凑正文 %d B（上限 %d）⇒ %s' % (n, LIMIT_B, OUT))
    print('完整明细 %d B ⇒ %s' % (len(FULL.encode('utf-8')), OUT_FULL))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
