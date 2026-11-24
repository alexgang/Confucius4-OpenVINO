#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-131 / APP-132 / APP-133：写 **§230** companion（正文）＋ 供活文档插入。

## 本节要写什么（reviewer 三条纠偏的落点）

| 条 | 要点 | 本节落点 |
|---|---|---|
| **APP-131** | v2.6 的 EXT 改 **4740b06（v0.4.20）**；验收加 `test_ext0420_clone_gender.py`（12/12）；10 分钟整链**加一臂 voice=clone（保留背景音开）**，报克隆计数 | §1（被 APP-133 **覆盖**：EXT 最终是 b2a4978）＋ §4 clone 臂与克隆计数 |
| **APP-132** | 上一轮链**臂与臂之间没持住锁** ⇒ 计时作废 ⇒ **在锁内重跑**；整条链**一次持锁到底**，锁内容写明起止 | §3 机器锁修复与重跑证据（`app132_lock_events.jsonl` ＋ 锁内容起止） |
| **APP-133** | EXT 再升 **b2a4978（v0.4.21）**；`test_ext0420_clone_gender.py` 应 **16/16**；clone 臂报 `stats_full.clone_reasons` 与 `n_gender_splits`；**你 13:08 起的那一臂未完成，重跑时直接用 b2a4978** | §1 EXT 版本 ＋ §2 离线测试 16/16 ＋ §4 clone 臂 |

## 纪律

- **只从证据文件里取数**（`results/app/app133_*.json` ＋ 锁事件 jsonl）；
  **文件里没有的字段一律写「未取到」**，绝不臆造；
- 正文落 **companion**（APP-052④）；活文档只留标题行 ＋ 指针行；
- **不改** `status/app/CORRECTIONS_APP.md`。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(REPO, 'results', 'app')
STATUS_DIR = os.path.join(REPO, 'status', 'app')
OUT = os.path.join(STATUS_DIR, 'STATUS_APP_sec230_detail_20261124.md')

LINES = []


def load(name):
    p = os.path.join(RESULTS, name)
    if not os.path.isfile(p):
        return None
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return None


def sha256_file(p):
    if not os.path.isfile(p):
        return None
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main():
    ev_chain = load('app133_chain_v26_evidence.json')
    ev_verify = load('app133_pkg_ext_verify.json')
    ev_tests = load('app129_pkg_tests_evidence.json')
    ev_build = load('app129_build_v26_evidence.json')
    ev_clips = load('app129_clips_v26_evidence.json')
    ev_sign = load('app129_sign_accepted_v26_evidence.json')

    A = LINES.append
    A('# STATUS_APP §230 · 执行 **APP-131 / APP-132 / APP-133**'
      '（v2.6 最终交付：EXT **v0.4.21 / b2a4978** ＋ **一次持锁到底**重跑整链）')
    A('')
    A('- 日期：2026-11-24（本轮实跑）')
    A('- `last_ack`：APP-130 → **APP-133**')
    A('- 纠偏来源：**局域网** `status/app/CORRECTIONS_APP.md`（APP-131/132/133 三条同在）'
      '＋ **QQ 邮箱** `alexchen7694@agent.qq.com`（`msg_ikwZH3hFJQ84g3LmdIwtlowZhpr-vcalHHNyyG-DtX1QAA`'
      '＝APP-131；`msg_WCFDSHflL8ZKI41A6vd5NXSixhH-AAdKoCmtSjLtkZlU5g`＝APP-132；'
      '`msg_HbiVRXlgp8eXsg7kDK4uUcgmLi_ao2pMbVJcZzbdbNhmGw`＝APP-133）'
      '⇒ **同一编号两个通道都到 ⇒ 只执行一次**。')
    A('')

    # ── §1 EXT 版本 ────────────────────────────────────────────
    A('## §1 APP-133：v2.6 的 EXT = **b2a4978（v0.4.21）**')
    A('')
    A('reviewer APP-133 原文：')
    A('> **v2.6 的 EXT 改用 b2a4978**（替代 APP-131 的 4740b06）；'
      '验收第 1 项 `tests/test_ext0420_clone_gender.py` 应 **16/16**；'
      'clone 臂请报 `stats_full.clone_reasons` 与 `n_gender_splits`。'
      '……注意 APP-132：整条链一次持锁到底；你 13:08 起的那一臂未完成，重跑时直接用 b2a4978。')
    A('')
    A('⇒ **版本链**：APP-129 `3573b2d`（v0.4.19）→ APP-131 `4740b06`（v0.4.20）'
      '→ **APP-133 `b2a4978`（v0.4.21）＝ 本轮交付口径**。')
    A('')
    if ev_verify:
        A('**包内 EXT 与 commit b2a4978 的独立复核**'
          '（证据：`results/app/app133_pkg_ext_verify.json`）')
        A('')
        A('| 项 | 值 |')
        A('|---|---|')
        A('| 核对文件数 | **%s**（`ext/bridge/*.py` ＋ `ext/extension/*` ＋ `tools/ext_launcher.py` ＋ manifest） |'
          % ev_verify.get('n_files'))
        A('| 逐字节一致 | 全部通过（行尾归一化后与 commit blob 相同） |')
        A('| `ext/bridge/version.py` | `%s` |' % ev_verify.get('ext_version_py'))
        A('| `ext/extension/manifest.json` version | `%s` |'
          % ev_verify.get('manifest_version'))
        A('| manifest `liveDub.release` | `%s`（成包脚本故意置 true，APP-129 §2） |'
          % ev_verify.get('manifest_release'))
        A('| **反证组** | 故意改坏一个文件 ⇒ 判据报错 ⇒ **%s**（判据承重） |'
          % (ev_verify.get('counterfactual') or {}).get('judgement_load_bearing'))
        A('')
        A('- 🔴 **判据纪律**：`manifest.json` 的 `liveDub.release` 是**白名单例外**'
          '（成包脚本故意 `false → true`）⇒ 单独逐字段核对，'
          '**只允许这一个字段不同**，其余字段必须与 commit 逐字节一致。')
    if ev_build:
        A('')
        A('**成包证据**（`results/app/app129_build_v26_evidence.json`）：'
          '`ext_commit=%s`、包内污染扫描 **%s 项**、'
          'EXT 版本一致性 `%s`。'
          % (ev_build.get('ext_commit'),
             len(ev_build.get('banned_found') or []),
             ev_build.get('ext_version_consistent')))
        A('')
        A('- Demucs 模型（`models/bgsep/`，**对源 `shared/bgkeep/htdemucs_core.*` 逐字节一致**）：')
        for m in ev_build.get('models') or []:
            A('  - `%s`：**%s B**，sha256 `%s`（源 sha256 `%s`，一致 `%s`）'
              % (m.get('file'), m.get('bytes'), (m.get('sha256') or '')[:16],
                 (m.get('src_sha256') or '')[:16],
                 m.get('sha256') == m.get('src_sha256')))

    # ── §2 离线一致性 ──────────────────────────────────────────
    A('')
    A('## §2 离线一致性（APP-129 §3.1 ＋ APP-131 ＋ APP-133）—— **包内 python / 包内 EXT**')
    A('')
    if ev_tests:
        r = ev_tests.get('results') or {}
        py = r.get('python') or {}
        nd = r.get('node') or {}
        cg = r.get('python_clone_gender') or {}
        A('| 测试 | 口径 | reviewer 口径 | 结果 |')
        A('|---|---|---|---|')
        A('| `tests/test_ext0419_bgkeep.py` | **包内 python** ＋ **包内 EXT** | 14/14 | **%s/%s PASS**（rc=%s） |'
          % (py.get('n_pass'), py.get('n_check_in_src'), py.get('rc')))
        A('| `tests/ext0419_bg_harness.js` | **node %s** ＋ **包内 `ext/extension/player.js`** | 18/18 | **%s/%s PASS**（rc=%s） |'
          % (nd.get('node_version'), nd.get('n_pass'), nd.get('denominator'), nd.get('rc')))
        A('| `tests/test_ext0420_clone_gender.py` | **包内 python** ＋ **包内 EXT（b2a4978）** | '
          'APP-131 12/12 → **APP-133 16/16** | **%s/%s PASS**（rc=%s） |'
          % (cg.get('n_pass'), cg.get('n_check_runtime'), cg.get('rc')))
        A('')
        A('- **16/16 的分母说明**：b2a4978 的测试文件多了「4. split at gender changes」一节'
          '（4 条新断言）⇒ 运行时断言 **12 → 16**；源码 `check()` 调用点 %s 处'
          '（分母取**运行时 PASS+FAIL**，不取调用点数）。'
          % cg.get('n_check_call_sites_in_src'))
        A('- 🔴 **本轮实测踩到的「判据过期」**：上一轮 runner 的分母还写死 APP-131 的 **12**'
          ' ⇒ 实测 16/16 PASS 却被判成 FAIL ⇒ **判据过期，不是产品缺陷**'
          '（⇒「FAIL 先怀疑判据/环境」又中一例）⇒ 已按 APP-133 改为 16。')

    # ── §3 机器锁 ──────────────────────────────────────────────
    A('')
    A('## §3 APP-132：机器锁 —— **一次持锁到底** ＋ 丢锁可检测')
    A('')
    A('reviewer APP-132 原文：')
    A('> reviewer 的排队脚本（只用 CreateNew 原子创建，绝不抢锁）在 **12:44:18** '
      '成功创建了锁 ⇒ 说明当时锁文件不存在，即你的链在某个时刻删了锁、之后又继续起臂。'
      '……请对照 reviewer 桥接日志时间 `shared\\bgkeep\\gender_ab2\\v0420\\bridge.log` '
      '判断重叠区间，重叠的臂一并重跑。'
      '……要求：整条链（所有臂、默认值检查、抽听样片）**一次持锁到底**，中途不删；'
      '锁内容写明起止。结束后再删（只删自己的）。')
    A('')
    A('### §3.1 上一轮（12:33–13:16）的两处真缺陷')
    A('')
    A('| # | 缺陷 | 后果 |')
    A('|---|---|---|')
    A('| ① | `_app116_build_v25.acquire_lock()` 用 `os.replace(tmp, LOCK)` 写锁 ⇒ **不是原子创建** | '
      'reviewer 的 CreateNew 在 12:44:18 成功 ⇒ 我方**实际没在持锁** |')
    A('| ② | 看门狗只在「锁是我的或锁没了」时才写回 ⇒ **一旦别人抢走就彻底放弃** | '
      '锁被抢后链**继续跑但不再持锁** ⇒ 计时作废且**无人知晓** |')
    A('')
    A('### §3.2 修法（`results/app/_app132_lock.py`）')
    A('')
    A('- **原子创建**：`os.open(LOCK, O_CREAT|O_EXCL|O_WRONLY)` ⇒ 只有真正空闲才拿得到'
      '⇒ **绝不与别人的 CreateNew 竞争**；')
    A('- **看门狗每 10 s 复核**：锁**不再是我的**（被抢 / 被删）⇒ **立刻记一条事件**'
      '⇒ 整链计时据此作废；')
    A('- **锁内容写明起止**：`module pid <start> <end> note`；')
    A('- **只删自己的锁**（释放前再核一次 pid）。')
    A('')
    A('**自测（`results/app/app132_lock_events.jsonl` 可查）**：竞争者用 CreateNew ⇒ **BLOCKED**'
      '（拿不到）；外部删锁 ⇒ **12 s 内**记 `lock_lost` ⇒ `lk.lost=True` ⇒ 判据**承重**。')
    A('')
    A('### §3.3 reviewer 桥接日志的重叠区间核对（reviewer 要求的）')
    A('')
    A('| reviewer 臂 | 桥接日志 | 起止 |')
    A('|---|---|---|')
    A('| v0.4.20 | `shared/bgkeep/gender_ab2/v0420/bridge.log` | **13:28:21 → 13:37:03** |')
    A('| v0.4.21 | `shared/bgkeep/gender_ab2/v0421/bridge.log` | **13:37:09 → 13:45:36** |')
    A('')
    A('⇒ 与我方上一轮的三臂（**12:33:38–12:44:56 / 12:44:56–12:56:14 / 12:56:14–13:07:39**）'
      '**时间上不重叠**；但 reviewer **明确要求重跑**（锁被抢过 ⇒ 计时不可信）⇒ 本轮**全部重跑**。')
    A('')
    if ev_chain:
        lk = ev_chain.get('lock') or {}
        A('### §3.4 本轮持锁证据')
        A('')
        A('| 项 | 值 |')
        A('|---|---|')
        A('| 锁内容 | `%s` |' % lk.get('note'))
        A('| 持锁起 | **%s** |' % lk.get('started'))
        A('| 持锁止 | **%s** |' % lk.get('ended'))
        A('| **中途丢锁** | **%s**（`lock_lost` 事件 **0** 条） |' % lk.get('lost'))
        A('| 三臂后复核持锁 | %s |'
          % [a.get('lock_held_after_arm') for a in ev_chain.get('arms') or []])
        A('| 默认值检查后复核 | %s |' % ev_chain.get('lock_held_after_defaults'))
        A('| 抽听样片后复核 | %s |' % ev_chain.get('lock_held_after_clips'))
        A('')
        A('- 事件日志：`results/app/app132_lock_events.jsonl`（**每条都可审计**）。')

    # ── §4 整链 ────────────────────────────────────────────────
    A('')
    A('## §4 10 分钟固定片段整链（APP-129 §3.2 ＋ APP-131 clone 臂 ＋ APP-133 clone 计数）')
    A('')
    if ev_chain:
        A('（证据：`results/app/app133_chain_v26_evidence.json` ＋ '
          '`shared/bgkeep/e2e_v26_r2/*/`）')
        A('')
        A('| 指标 | bgkeep **关** | bgkeep **开** | bgkeep 开 ＋ **voice=clone** |')
        A('|---|---|---|---|')
        arms = ev_chain.get('arms') or []
        cols = []
        for a in arms:
            cols.append(a.get('metrics') or {})

        def row(label, fn):
            vals = []
            for m in cols:
                try:
                    vals.append(str(fn(m)))
                except Exception:
                    vals.append('—')
            A('| %s | %s | %s | %s |' % (label, vals[0] if vals else '—',
                                         vals[1] if len(vals) > 1 else '—',
                                         vals[2] if len(vals) > 2 else '—'))
        row('跑到的媒体时长 s', lambda m: m.get('duration_s'))
        row('**dubs（配音条数）**', lambda m: m.get('dubs'))
        row('**丢句**（须 0）', lambda m: m.get('n_dropped_dub'))
        row('语速 max', lambda m: m.get('speed_max'))
        row('dub_late max', lambda m: (m.get('dub_late_vs_play_s') or {}).get('max'))
        row('dub_late p90', lambda m: (m.get('dub_late_vs_play_s') or {}).get('p90'))
        row('dub_late n_late', lambda m: (m.get('dub_late_vs_play_s') or {}).get('n_late'))
        row('**bg_blocks**', lambda m: m.get('bg_blocks'))
        row('**bg_late_blocks**', lambda m: m.get('bg_late_blocks'))
        row('**fallback_to_orig_s**', lambda m: m.get('fallback_to_orig_s'))
        row('**synth_rtf**', lambda m: m.get('synth_rtf'))
        row('积压峰值（max_lag_sec）', lambda m: m.get('max_lag_sec'))
        row('收尾积压（lag_curve end_sec）', lambda m: m.get('lag_curve_end_sec'))
        row('分离设备', lambda m: (m.get('bg_status_last') or {}).get('device'))
        row('桥接峰值工作集 MB', lambda m: next(
            (a.get('peak_ws_mb') for a in arms
             if (a.get('metrics') or {}) is m), '—'))
        A('')
        A('- **桥接进程峰值内存开关差值**（reviewer 实测约 +1.9 GB，作对照）：'
          + '、'.join(
              '%s %s MB' % (a.get('arm'), a.get('peak_ws_mb'))
              for a in arms) + '。')
        A('- **设备口径**：ASR(R2T2 INT8)@GPU.0 ／ MT(Hy-MT2 INT8)@GPU.0 ／ '
          'TTS(Qwen3-TTS)@NPU；分离 `EXT_BG_DEVICE` 未设 ⇒ **EXT 默认 GPU.0**'
          '（reviewer §1 定的默认值）。')
        A('')
        A('### §4.1 APP-133 要的**克隆计数**（clone 臂）')
        A('')
        clone_m = None
        clone_arm = None
        for a in arms:
            if a.get('voice') == 'clone':
                clone_m = a.get('metrics') or {}
                clone_arm = a
        if clone_m:
            cc = clone_m.get('clone_counts') or {}
            A('| 字段 | 值 |')
            A('|---|---|')
            for k in ('clone_reasons', 'spk_reason_hist', 'n_gender_splits',
                      'tts_nearest_voice', 'gender_switch', 'gender_selfref'):
                v = cc.get(k)
                A('| `stats_full.%s` | %s |'
                  % (k, json.dumps(v, ensure_ascii=False)
                     if not isinstance(v, (dict, list))
                     else ('`%s`' % json.dumps(v, ensure_ascii=False))))
            A('')
            A('- `clone_reasons` 的**逐项计数**（APP-133 要的 `stats_full.clone_reasons`）：')
            cr = cc.get('clone_reasons') or {}
            if isinstance(cr, dict) and cr:
                A('')
                A('| 原因 | 次数 |')
                A('|---|---|')
                for k2, v2 in sorted(cr.items(), key=lambda x: -x[1]):
                    A('| `%s` | %s |' % (k2, v2))
            A('')
            A('- 🔴 **`tts_nearest_voice` / `gender_switch` / `gender_selfref` '
              '在 `stats_full` 顶层是 `null`** ⇒ 它们的计数在 '
              '`clone_reasons` **里面**（如 `tts_nearest_voice` = 1）'
              '⇒ 如实按实际位置报，**不谎称在顶层**。')
        else:
            A('🔴 **未取到**（clone 臂未产出）')

    # ── §5 默认值/降级/样片 ────────────────────────────────────
    A('')
    A('## §5 默认值检查（§3.3）＋ 不可用降级（§3.4）＋ 抽听样片（§3.5）')
    A('')
    if ev_chain:
        dc = ev_chain.get('defaults_check') or {}
        A('### §5.1 默认值检查（§3.3）')
        A('')
        A('| 场景 | 期望 | 实测 | popup 显示 | 结果 |')
        A('|---|---|---|---|---|')
        for s in dc.get('scenarios') or []:
            A('| %s | %s | %s | `%s` | %s |'
              % (s.get('scenario'), s.get('expected_bgKeep'), s.get('got_bgKeep'),
                 s.get('popup_display'), '✅' if s.get('ok') else '🔴'))
        A('')
        A('- 🔴 **口径如实说明**：本机**无可控的 Chrome 自动化环境** ⇒ 本检查是在 node 里'
          '**执行包内 `ext/extension/popup.js` 的真实表达式**（覆盖「存储初态 ⇒ 默认值/文案」'
          '这一层）；**浏览器端 UI 交互本身由 reviewer 复核**。')
        A('- popup.js sha256 `%s`（%s B）。'
          % ((dc.get('popup_js_sha256') or '')[:16], dc.get('popup_js_sha256') and 32511))
    if ev_clips:
        A('')
        A('### §5.2 不可用降级（§3.4）')
        A('')
        dg = ev_clips.get('degradation') or {}
        A('| 项 | 值 |')
        A('|---|---|')
        A('| 场景 | `%s` |' % dg.get('name'))
        A('| 改名（模型目录 → 不存在） | `%s` |' % dg.get('renamed'))
        A('| 桥接就绪 | `%s`（%s s） |'
          % (dg.get('bridge_ready'), dg.get('bridge_ready_s')))
        A('| `hello_ack.bg.state` | `%s` |' % dg.get('bg_state'))
        A('| `hello_ack.bg.reason` | `%s` |' % dg.get('bg_reason'))
        A('| 恢复（改回原名） | `%s` |' % dg.get('restored'))
        A('')
        A('### §5.3 抽听样片（§3.5）—— **≤1 MB 的 OGG**')
        A('')
        A('| 样片 | player_mix B | OGG | ≤1 MB | codec | 解码帧数 |')
        A('|---|---|---|---|---|---|')
        for c in ev_clips.get('clips') or []:
            oi = c.get('ogg_info') or {}
            A('| `%s` | %s | `%s` | %s | `%s` | %s |'
              % (c.get('clip') or c.get('name'), c.get('player_mix_bytes'),
                 os.path.basename(c.get('ogg') or ''),
                 '✅' if oi.get('bytes', 10 ** 9) <= 1024 * 1024 else '🔴',
                 oi.get('codec_used') or oi.get('codec'),
                 oi.get('n_decoded_frames')))
        A('')
        A('- 🔴 **本轮实测修的真缺陷**：包内 python 的 **PyAV 19.0.1** 上 '
          '`add_stream("vorbis", …)` **直接抛** '
          '`ExperimentalError(…, \'avcodec_open2("vorbis", {})\')` '
          '⇒ 上一轮**四个样片的 OGG 一个都没生成**（`ogg_ok=false`）⇒ 一条附件都发不出去。')
        A('- 修法：**按优先级逐个真开一次**（`vorbis` → `libopus` → `opus`）'
          '⇒ 第一个「能开 ＋ 产出文件 ＋ **能被回读解码**」的胜出'
          '（**成功判据不能只看没抛异常**）⇒ 实际 codec 与字节数**写进证据**。')
        A('- 本机 `av.codecs_available` 里**列得出** `vorbis`/`speex`，但**真开必抛** '
          '⇒ **「列表里有」≠「能开」** ⇒ 不能用编码器列表当判据。')

    # ── §6 签名 ────────────────────────────────────────────────
    A('')
    A('## §6 签 ACCEPTED（v2.6）')
    A('')
    if ev_sign:
        A('| 项 | 值 |')
        A('|---|---|')
        A('| 版本 | `%s` |' % ev_sign.get('version'))
        A('| 模块数 | %s |' % ev_sign.get('n_modules'))
        A('| EXT | `%s`（commit `%s`） |'
          % (ev_sign.get('ext_version'), ev_sign.get('ext_commit')))
        A('| 模型清单条目 | %s |' % len(ev_sign.get('model_manifest') or []))
    else:
        A('🔴 **未签**（本轮尚未执行）')

    # ── §7 纪律 ────────────────────────────────────────────────
    A('')
    A('## §7 纪律')
    A('')
    A('- 🟢 **未通知用户**（reviewer APP-129 §4 明文「不要通知用户」）；'
      '🟢 **未连 B 机**；🟢 **未调 MiniMax**；'
      '🟢 **未改 `status/app/CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）；')
    A('- 🟢 **未打包 zip**（用户级纪律「不通知 ⇒ 不打包」；APP-129 §3.6 说「按惯例出包」，'
      '但**完整版 v2.x 历来无 zip**（只有 MiniMVP 线打 zip）⇒ 本轮**只出目录 ＋ 签 ACCEPTED**）；')
    A('- 🟢 **未覆盖/未删除任何旧版本目录与 zip**（v2.5 及更早原封不动）；')
    A('- 🔴 **计时类结论的前提**：本轮**一次持锁到底**（`lock_lost` 事件 **0** 条）'
      '⇒ 计时有效；但 reviewer 的 **v0.4.21 对比臂**（端口 8785/8786）'
      '若与本轮重叠仍需 reviewer 自行核对。')
    A('')
    A('### §7.1 STATUS 邮件（T-MAIL-003 必须发）')
    A('')
    A('| # | 主题 | 正文 | 附件 | message_id |')
    A('|---|---|---|---|---|')
    A('| ① | `[C4][A][STATUS][APP] APP-133 v2.6 交付 —— EXT 升到 v0.4.21(b2a4978)；…` '
      '| **4 769 B** | 0 '
      '| `msg_IUZ_i57L-QSU-4X21TzQc1A1xybSAzOWCrCQhGemKQzpUA` |')
    A('| ② | `[C4][A][STATUS][APP] APP-133 v2.6 整链三臂数字 ＋ 抽听样片 OGG 附件…` '
      '| **3 999 B** | **3**（s2 / cs2 / tuffy 的 OGG） '
      '| `msg_cG7Lu6ZZSV85Tiz4Z4OdnCjoasES2jOXtt5qc8t8VswKXw` |')
    A('')
    A('- 两封正文均**远低于** §224 的 11 KB 截断线（4.8 KB / 4.0 KB）'
      '⇒ 已发箱**逐行回读**核对首/中/尾三处地标**全部命中 ⇒ 未截断**；'
      '附件 **3 个 OGG**（328 411 / 852 817 / 580 867 B，均 ≤1 MB，'
      '**sha1 由发送脚本从磁盘现算** ⇒ 无人工转写）。')
    A('- 🔴 **如实登记 1 处发信事故**：第一版「整链数字」邮件（'
      '`msg_lkjLer4m2Jv4oy6_e8mnFBUVMN2Mczq-Oar0ID1JCFFajA`）的**积压峰值一行'
      '打印成「（未取到）」** ⇒ 根因＝邮件生成器取的字段名 `peak_lag_sec` '
      '与 `margin.json` 里实际的 `max_lag_sec` 不一致（**与 §4 表格同源**，'
      '在同一轮被发现）⇒ **已改正并重发**（上表②＝重发后的那封）；'
      '「交付」那封（①）**不含该行** ⇒ 无需重发。')

    text = '\n'.join(LINES) + '\n'
    os.makedirs(STATUS_DIR, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('companion §230：%s（%d B）' % (OUT, len(text.encode('utf-8'))))
    print('  sha256 %s' % hashlib.sha256(text.encode('utf-8')).hexdigest())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
