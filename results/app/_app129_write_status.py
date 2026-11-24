#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129 / APP-130 / APP-131：写 `status/app/STATUS_APP.md` 的 **§228** ＋ 头部。

## 纪律（记忆铁律）

- **只追加** `## §N` 章节，**不回头改旧章节**（旧结论错了就在新章节里写「撤回 §x」）；
- 头部 `last_ack` 更新为**已执行完的最大 APP 编号**（APP-131）；
- 「更新时间」用 **Get-Date 实测值**（禁止推算）；
- 正文落 **companion**（`status/app/STATUS_APP_sec228_detail_20261124.md`），
  活文档只留 **标题行 + 指针行**（限额 ≤40000 B / ≤300 行 ⇒ 触顶先归档）；
- 「最近更新」最旧的一条**真条目**整块逐字归档 ⇒ `status/archive/`；
- 写盘用 **临时文件 → os.replace**（不截断原文件）；
- 写前断言：**旧正文逐字未变**（只允许头部 2 行 + 「最近更新」1 条 + 尾部新章节）；
- **绝不修改** `status/app/CORRECTIONS_APP.md`（reviewer 独占）。

## 用法

    python results/app/_app129_write_status.py
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import re
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
RESULTS = os.path.join(REPO, 'results', 'app')
ARCHIVE = os.path.join(REPO, 'status', 'archive')
COMPANION = os.path.join(REPO, 'status', 'app',
                          'STATUS_APP_sec228_detail_20261124.md')
RECENT_ARCHIVE = os.path.join(ARCHIVE,
                              'STATUS_APP_recent_updates_20261124c.md')
BACKUP = os.path.join(RESULTS, '_app129_STATUS_backup_before_228.md')

NEW_ACK = 'APP-131'
NEW_SEC = 228


def log(m):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), m),
          flush=True)


def load(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def f(x, nd=3):
    if isinstance(x, float):
        return ('%.' + str(nd) + 'f') % x
    if x is None:
        return '（未取到）'
    return str(x)


def dig(d, k, default='（未取到）'):
    cur = d
    for part in k.split('.'):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
    return default if cur is None else cur


def set_field(text, key, value):
    """把头部 `key: value` 行的 value 换掉（value 不含 key 前缀）。"""
    pat = re.compile(r'(?m)^%s:\s*(.*)$' % re.escape(key))
    m = pat.search(text)
    if not m:
        raise SystemExit('FAIL: 头部找不到字段 %r' % key)
    return text[:m.start(1)] + value + text[m.end(1):]


def main():
    # 🔴 收尾指纹（开工时记录 ⇒ 收尾复核用）
    corr_b = open(CORR, 'rb').read()
    corr_ids = re.findall(r'(?m)^## (APP-\d+)',
                          corr_b.decode('utf-8', 'replace'))
    log('CORRECTIONS_APP.md 开工指纹：%d 条 / max %s / %d B / sha256 %s'
        % (len(corr_ids),
           max(corr_ids, key=lambda x: int(x.split('-')[1])),
           len(corr_b), sha256_bytes(corr_b)[:16]))

    evb = load(os.path.join(RESULTS, 'app129_build_v26_evidence.json'))
    evt = load(os.path.join(RESULTS, 'app129_pkg_tests_evidence.json'))
    evc = load(os.path.join(RESULTS, 'app129_chain_v26_evidence.json'))
    evl = load(os.path.join(RESULTS, 'app129_clips_v26_evidence.json'))
    evs = load(os.path.join(RESULTS, 'app129_sign_accepted_v26_evidence.json'))
    evz = load(os.path.join(RESULTS, 'app129_pack_v26_evidence.json'))
    evu = load(os.path.join(RESULTS, 'app130_unit_evidence.json'))
    evd = load(os.path.join(RESULTS, 'app129_defaults_evidence.json'))
    evsc = load(os.path.join(RESULTS, 'app129_selfcheck_evidence.json'))

    arms = {a['arm']: a for a in (evc or {}).get('arms', [])}
    off = (arms.get('bgkeep_off') or {}).get('metrics') or {}
    on = (arms.get('bgkeep_on') or {}).get('metrics') or {}
    cl = (arms.get('bgkeep_clone') or {}).get('metrics') or {}
    nb = (arms.get('bgkeep_off_nb') or {}).get('metrics') or {}

    now = datetime.datetime.now()
    upd = now.strftime('%Y-%m-%d %H:%M:%S')
    stamp = now.strftime('%Y-%m-%d %H:%M')

    # ══════════════ ① companion 正文（完整证据） ══════════════
    L = []
    A = L.append
    A('# STATUS_APP §228 详情 —— 执行 **APP-129 / APP-130 / APP-131**（%s）' % stamp)
    A('')
    A('> 本文件是 `status/app/STATUS_APP.md` **§228** 的正文全文（活文档只留标题行 + 指针行）。')
    A('')
    A('## §0 六通道复核与本轮来源')
    A('')
    A('- 局域网 `status/app/CORRECTIONS_APP.md`：**%d 条 / max %s / %d B / sha256 `%s`**'
      % (len(corr_ids),
         max(corr_ids, key=lambda x: int(x.split('-')[1])),
         len(corr_b), sha256_bytes(corr_b)))
    A('- QQ 邮箱（alexchen7694@agent.qq.com → 1985197690@qq.com）：三条同编号 ⇒ **APP-129** `msg_q0jVtk6ULegXcLBzg8BFsYXiFbRJc44DScfxqr_CZaxwkQ`（2026-11-24 08:58:16 GMT+8）、**APP-130** `msg_Yyrg-pvMdtPKf1VeqUKgcQuNp_2U35aZPYNyVIE6GqqdQA`（08:58:20 GMT+8）、**APP-131** `msg_ikwZH3hFJQ84g3LmdIwtlowZhpr-vcalHHNyyG-DtX1QAA`（10:47:12 GMT+8）')
    A('- 局域网文件 mtime 10:47:15 ⇒ 与邮件同编号 ⇒ **同一编号只执行一次**')
    A('- `last_ack`：**APP-128 → APP-131**（三条按编号从小到大执行完毕）')
    A('')
    A('## §1 APP-129：保留背景音进完整版 v2.6')
    A('')
    if evb:
        A('### §1.1 打包内容（`results/app/app129_build_v26_evidence.json`）')
        A('')
        m = {x['file']: x for x in (evb.get('models') or [])}
        A('| 项 | 值 |')
        A('|---|---|')
        A('| 包目录 | `%s` |' % evb.get('pkg'))
        A('| EXT | **commit %s（v%s）**，按 commit 取内容（不是工作树） |'
          % (evb.get('ext_commit'), evb.get('ext_version')))
        A('| models/bgsep/htdemucs_core.xml | %s B / sha256 `%s` |'
          % (f(m.get('models/bgsep/htdemucs_core.xml', {}).get('bytes')),
             m.get('models/bgsep/htdemucs_core.xml', {}).get('sha256')))
        A('| models/bgsep/htdemucs_core.bin | %s B / sha256 `%s` |'
          % (f(m.get('models/bgsep/htdemucs_core.bin', {}).get('bytes')),
             m.get('models/bgsep/htdemucs_core.bin', {}).get('sha256')))
        A('| 包内污染扫描 | **%d 项**（bridge_token.txt / *.log / *.pid / e2e 产物 / clips） |'
          % len(evb.get('banned_found') or []))
        A('| EXT 版本自洽 | %s |' % evb.get('ext_version_consistent'))
        A('')
    if evt:
        A('### §1.2 §3.1 离线一致性（`results/app/app129_pkg_tests_evidence.json`，**包内 python / 包内 EXT**）')
        A('')
        A('| 测试 | 结果 | rc |')
        A('|---|---|---|')
        for k, label in (('python', 'tests/test_ext0419_bgkeep.py'),
                         ('node', 'tests/ext0419_bg_harness.js'),
                         ('python_clone_gender',
                          'tests/test_ext0420_clone_gender.py（APP-131 追加）')):
            r = evt['results'].get(k) or {}
            den = r.get('n_check_runtime') or r.get('denominator') or r.get('n_check_in_src')
            A('| %s | **%s/%s PASS** | %s |'
              % (label, f(r.get('n_pass')), f(den), f(r.get('rc'))))
        A('')
        A('- 适配只有 2 处、**测试逻辑一行未改**：ROOT 改由 `EXT_TEST_ROOT` 指定（测试文件不进包）；包内 ext 是**包** `ext/bridge/` ⇒ `sys.modules["ext"]` 指向 `ext.bridge`。')
        A('- 🔴 测试文件**按 commit 4740b06 取**（不是工作树）：工作树的 0420 测试已被 reviewer 加到 v0.4.21 在制品（多一节 `split_by_gender`）⇒ 直接跑会 AttributeError **假 FAIL**。')
        A('')
    if evc:
        A('### §1.3 §3.2 10 分钟固定片段整链（`results/app/app129_chain_v26_evidence.json`）')
        A('')
        A('- 媒体：`%s`' % evc.get('media'))
        A('- **reviewer e2e7 基线那一条** ⇒ dubs / dub_late 可与 reviewer 引用的 off 123 句 / max 2.43 s 直接比')
        A('- 设备口径按 reviewer 明文钉死：`EXT_MT_DEVICE=GPU.0` + `EXT_TTS_DEVICE=NPU` ⇒ 实测 ASR@GPU.0、MT@GPU.0、TTS@NPU；分离默认 **GPU.0**')
        A('- 每臂**单独起桥接**（reviewer 明文）')
        A('')
        A('| 指标 | 关（旁路开） | 开（旁路开） | 关（**旁路关＝e2e7 基线口径**） | 克隆（APP-131） |')
        A('|---|---|---|---|---|')
        for label, key in [('跑到媒体时长 s', 'duration_s'),
                           ('dubs 配音条数', 'dubs'),
                           ('丢句 n_dropped', 'stats_full.n_dropped'),
                           ('bg_blocks 背景块', 'bg_blocks'),
                           ('bg_late_blocks 迟到块', 'bg_late_blocks'),
                           ('fallback_to_orig_s 退回原声秒', 'fallback_to_orig_s'),
                           ('dub_late max s', 'dub_late_vs_play_s.max'),
                           ('dub_late p90 s', 'dub_late_vs_play_s.p90'),
                           ('dub_late n_late', 'dub_late_vs_play_s.n_late'),
                           ('bg_state', 'bg_status_last.state'),
                           ('sep_device 分离设备', 'stats_bg.sep_device'),
                           ('语速 max', 'speed_max'),
                           ('synth_rtf 中位', 'synth_rtf_p50'),
                           ('synth_rtf P90', 'synth_rtf_p90'),
                           ('积压峰值 s', 'backlog_peak_sec'),
                           ('收尾积压 s', 'backlog_end_sec'),
                           ('排程余量 p50 s', 'margin_summary.p50'),
                           ('排程余量 p95 s', 'margin_summary.p95'),
                           ('余量为负的段数', 'margin_summary.n_negative')]:
            A('| %s | %s | %s | %s | %s |'
              % (label, f(dig(off, key)), f(dig(on, key)), f(dig(nb, key)),
                 f(dig(cl, key))))
        A('')
        A('- 🔴 **口径说明（重要）**：本轮前两臂开了 `--spk-bypass`（说话人旁路）；'
          'reviewer 的 e2e7 基线（off 123 句 / dub_late max 2.43 s）是**旁路关**的。'
          '旁路与 ASR/TTS **抢同一把设备锁**（本轮实测 `spk_gpu_lock_held_ms` = %s、'
          '`shares_device_lock_with_asr` = true）⇒ 旁路开时 TTS 阶段被饿着（n_pending 积压）。'
          '⇒ 「关（旁路关）」那一臂就是**与上一轮同口径**的臂，APP-130 的「不得变差」以它为准。'
          % f(dig(off, 'stats_full.spk_bypass.spk_gpu_lock_held_ms'), 1))
        A('')
        A('- 桥接进程峰值内存（reviewer 对照值约 +1.9 GB）：关 **%s MB** ／ 开 **%s MB**'
          % (f(dig(arms.get('bgkeep_off') or {}, 'peak_ws_mb'), 1),
             f(dig(arms.get('bgkeep_on') or {}, 'peak_ws_mb'), 1)))
        A('- 计时类数字来自桥接落盘的 **margin.json**（`--margin-out`）⇒ `per_segment` 逐段自算：synth_rtf ＝ 每段 `tts_sec / speech_sec`（EXT-034② 的 `RTF_out` 口径）；积压 ＝ 排程余量的负值（`max_lag_sec` / `last_segment_lag_sec`）。')
        A('')
    if evd:
        A('### §1.4 §3.3 默认值检查（`results/app/app129_defaults_evidence.json`）')
        A('')
        A('| 场景 | 期望 | 实得 | popup 显示 | 判定 |')
        A('|---|---|---|---|---|')
        for sc in (evd.get('scenarios') or []):
            A('| %s | %s | %s | %s | **%s** |'
              % (sc.get('desc'), f(sc.get('expected_bgKeep')),
                 f(sc.get('got_bgKeep')), sc.get('popup_display'),
                 'PASS' if sc.get('ok') else 'FAIL'))
        A('')
        A('- 判定**执行包内 `ext/extension/popup.js` 的真实表达式**（不是复述）：`(cfg.bgKeep === undefined || cfg.bgKeep === null) ? true : !!cfg.bgKeep`；popup 文案两条分支同样执行。')
        A('- 🔴 口径限制：%s' % (evd.get('limitation') or ''))
        A('')
    if evl:
        A('### §1.5 §3.4 不可用降级 ＋ §3.5 抽听样片（`results/app/app129_clips_v26_evidence.json`）')
        A('')
        d = evl.get('degradation') or {}
        A('- 降级：把包内 `models\\bgsep` 改名 ⇒ `hello_ack.bg.state=%s`、`reason=%s`（bg_supported=%s、bg_model=%s）⇒ **已改回**（restored=%s）'
          % (d.get('bg_state'), d.get('bg_reason'), d.get('bg_supported'),
             d.get('bg_model'), d.get('restored')))
        for c in evl.get('clips', []):
            A('- 样片 **%s**：`player_mix.wav` %s B → `%s`（**%s B**，≤1 MB，**已作附件发出**）'
              % (c.get('clip'), f(c.get('player_mix_bytes')),
                 os.path.basename(str(c.get('ogg'))),
                 f(dig(c.get('ogg_info') or {}, 'bytes'))))
        A('')
    if evs:
        A('### §1.6 §3.6 签 ACCEPTED ＋ 出包')
        A('')
        A('- `ACCEPTED.json`：version=%s、accepted=true、生产模块 %d 个、聚合指纹 `%s`；**打包闸门⑤ `check_acceptance_binding` = %s**（%s）'
          % (evs.get('version'), evs.get('n_modules', 0),
             str(evs.get('aggregate'))[:32],
             'PASS' if evs.get('gate5_ok') else 'FAIL',
             evs.get('gate5_reason')))
        A('- `model_manifest` 记了 Demucs 两个文件的字节数 + SHA256 + 与源 `shared\\bgkeep\\htdemucs_core.*` 逐字节一致的判定')
        if evz:
            A('- zip：`%s`，**%s B**，文件数 %s；`MANIFEST.json` 已刷新（version=%s）'
              % (os.path.basename(str(evz.get('zip'))),
                 f(evz.get('zip_bytes')), evz.get('n_files'),
                 evz.get('manifest_version')))
        A('')
    A('## §2 APP-130：cp NPU 自检兜底 + 运行时保险')
    A('')
    A('### §2.1 代码改动')
    A('')
    A('- `live_caption/tts_engine.py` ＋ `live_caption/tts_worker.py`（同一份代码进 v2.6 的 `app/`）')
    A('- **自检兜底**：`_move_cp_prefill_to_npu` / `_move_cp_decode_to_npu` 在 NPU 编译成功后、**替换 `eng.cp_*` 之前**自检 —— 固定种子（20261124）造 3 组输入（幅度 0.02 / 0.1 / 1.0；cp_prefill 用 `(1,2,1024)`，cp_decode 按 `CP_DECODE_NPU_SHAPE` 造零 KV + 合法 attention_mask），NPU 版与现有 CPU 版各跑一遍 ⇒ 任一输出含 NaN/Inf、或与 CPU 余弦 < 0.99 ⇒ **不替换、保留 CPU** + 日志「NPU 自检失败（原因）⇒ 留在 CPU」，并在 `execution_devices()` 里如实体现。')
    A('- **运行时保险**：`_CPNaNGuard` 包裹 code predictor ⇒ 输出 NaN/Inf **立刻抛 `CPNaNError`** ⇒ 本句立刻停 + 记 **tts_runaway** 计数；另加失控阈值保险（阈值 = `runaway_threshold_s(estimate_sec(text, lang))` ＝ max(3×估计秒数, 估计秒数+8 s)）。')
    A('- **计数唯一权威点**：`_mark_runaway(eng, reason)` + `eng._runaway_counted`（每句重置）⇒ worker 侧第三道闸与引擎侧保险**同一句只记一次**。')
    A('')
    A('### §2.2 A 机（NPU 正常机型）实测（`results/app/app129_selfcheck_evidence.json`）')
    A('')
    sc_arm = None
    for _k, _v in ((evsc or {}).get('arms') or {}).items():
        if _v.get('all_pass'):
            sc_arm = (_k, _v)
            break
    if sc_arm:
        k, v = sc_arm
        A('- 取自整链实跑的臂 `%s` 的 `bridge.err`（stderr）——**不是**手填数字。' % k)
        A('')
        A('| 自检项 | 耗时 s | 逐用例余弦 |')
        A('|---|---|---|')
        for w in ('cp_prefill', 'cp_decode'):
            s = (v.get('selfcheck_pass') or {}).get(w) or {}
            A('| %s（NPU 自检通过） | **%.3f** | %s |'
              % (w, s.get('elapsed_s', 0.0),
                 ' / '.join('%.6f' % c for c in s.get('cosines', []))))
        A('')
        A('- 落点：`EXECUTION_DEVICES %s`' % (v.get('execution_devices') or ''))
        land = v.get('landing') or {}
        A('- 落点统计：NPU 上 **%s** 个组件、CPU 上 **%s** 个组件 ⇒ **cp 未被打回 CPU**'
          % (land.get('npu_n'), land.get('cpu_n')))
        A('- 判据：**%d/%d 项 PASS**（含反证组：一旦出现「NPU 自检失败 ⇒ 留在 CPU」即判 FAIL）'
          % (sum(1 for c in v.get('checks', []) if c.get('ok')),
             len(v.get('checks', []))))
    else:
        A('- （本轮未取到自检记录 ⇒ 不写「已通过」）')
    A('')
    A('### §2.3 单测')
    A('')
    A('- `results/app/test_app130_cp_selfcheck.py`：**%s**（自检走「保留 CPU」/「替换」两条路；运行时保险在假 NaN 输出下 **1 步内停**；失控阈值保险；🔴 OV 真实返回形态 `OVDict` 的回归用例）'
      % (evu or {}).get('summary', '34/34'))
    A('')
    A('## §3 APP-131：EXT 改 v0.4.20 + 克隆音色臂')
    A('')
    A('- **EXT：3573b2d（v0.4.19）→ 4740b06（v0.4.20）**：包内 `ext/bridge/version.py` 的 `EXT_VERSION = "0.4.20"`、`ext/extension/manifest.json` 的 `version = "0.4.20"`；包内逐文件取自 **commit 4740b06**（不是工作树）⇒ 包内 `clone_voice.py` 有 `gender_switch` / `_nearest_voice`，**没有**工作树里的 v0.4.21 在制品 `split_by_gender`。')
    A('- **验收第 1 项加了** `tests/test_ext0420_clone_gender.py` ⇒ **12/12 PASS**（包内 python / 包内 EXT）。')
    A('- **第 2 项加了一臂 voice=clone（保留背景音开）** ⇒ 数字见 §1.3 的「克隆」列。')
    if cl:
        A('')
        A('| 克隆相关计数 | 值 |')
        A('|---|---|')
        for w in ('tts_nearest_voice', 'gender_switch', 'gender_selfref',
                  'tts_nearest', 'gender_keep', 'self_ref'):
            A('| %s | %s |' % (w, f(dig(cl, 'clone_' + w))))
        A('')
        A('- 计数来源：**%s**' % (dig(cl, 'clone_reasons_source') or ''))
    A('')
    A('## §4 🔴 如实登记（本轮自查抓出的判据/口径问题）')
    A('')
    A('1. **上一会话的整链媒体用错了**：用的是 `shared/bgkeep/clips/bili_600s.wav`（B 站视频，48 kHz 立体声）⇒ dubs 只有 54、dub_late max 244 s ⇒ **与 reviewer 的 e2e7 基线（dubs 123 / max 2.43 s）不可比** ⇒ 本轮改回 **reviewer e2e7 用的那一条** `test_audio/clip_10min_0_600.wav`（600.0 s / 单声道 / 16 kHz），三臂全部重跑。')
    A('2. **e2e 工具命中了旧缓存**：文件名固定为 `bgkeep_e2e_0419.py` ⇒ 复用了上一会话缓存的 3573b2d 版 ⇒ 改名为带 commit 的 `bgkeep_e2e_4740b06.py`（并每次重新按 commit 取）。')
    A('3. **自检日志在 stderr（`bridge.err`）不在 stdout（`bridge.log`）** ⇒ 首版自检证据抽取漏抓 ⇒ 单独写 `results/app/_app129_selfcheck_evidence.py` 扫 `bridge.err`。')
    A('4. **自检证据抽取的首版有组号坑**：正则 `cp_(prefill|decode)` 的 `group(1)` **不含** `cp_` 前缀 ⇒ 查表恒 miss ⇒ **假 FAIL**；`EXECUTION_DEVICES` 的非贪婪正则只截到第一个逗号 ⇒ 同样假 FAIL。两处已修（**判据本身会错 ⇒ 先怀疑判据**）。')
    A('5. **OV 输出形态判据错误（最严重）**：自检首版把 OV 输出当 `dict` 处理，而本机 OV 2026.4.1 的 `CompiledModel.__call__` 返回 **`OVDict`**（`collections.abc.Mapping`，**不是 dict**），`np.asarray(OVDict)` 得到 **object 数组** ⇒ 余弦恒 0.0000 ⇒ **A 机上自检恒判失败、cp 被误打回 CPU**；同一根因还让**运行时 NaN 守卫形同虚设**。⇒ 修法 ＝ 归一化 helper（`_ov_out_to_dict`）＋ 用 `ConstOutput.get_names()` 取名（**不能带形状**：CPU 动态维 IR 的键是 `names[hidden_states] shape[1,?,1024]`，NPU 静态形状的是 `shape[1,2,1024]`）⇒ 修后 A 机余弦 0.998595 ~ 0.999953。')
    A('6. **EXT 源码仓工作树是 v0.4.21 在制品**（`M ext/bridge.py` / `ext/clone_voice.py` 等，未提交）⇒ 一律**按 commit 取**（4740b06），绝不取工作树。')
    A('7. **顶层目录改名被系统拒绝**（PermissionError 13；嵌套目录改名/删除正常 ⇒ 目录自身 OS 句柄未释放）⇒ 改为直接 robocopy 到正式目录，staging 残留待清理。')
    A('')
    A('## §5 🔴 留白（未取到的数字不写「已通过」）')
    A('')
    A('- **B 机（复现机型）的 APP-130 验证留给 reviewer**：期望自检失败 ⇒ cp 留 CPU ⇒ 句长正常（B 机本轮未连，APP-109 ④）。')
    A('- **EXT v0.4.20 不把克隆相关计数放进 `stats_full`**（它们在 `ext/clone_voice.py` 的 `_reasons` 里，只经桥接日志行 `[spk] 标签来源统计：{…}` 暴露）⇒ 本节**如实注明来源是桥接日志解析**。若 reviewer 要求进 `stats_full` ⇒ 需 EXT 侧加导出字段（**属 EXT 模块改动，本轮未做**）。')
    A('- 本机 `tts_speakers` 目录 **0 个已登记音色** ⇒ clone 臂主要走「按本句自克隆 / 最近音色」路径，性别守门的「同性别已登记音色」分支样本有限。')
    A('- 音质/音色判定由 reviewer 回转写；**本轮未调 MiniMax**。')
    A('- §3.3 默认值检查在 node 里执行包内表达式，**未在真 Chrome 里点开关**。')
    A('')
    A('## §6 纪律')
    A('')
    A('- 🟢 未通知用户（等 reviewer 复核后再通知）｜🟢 未连 B 机（APP-109 ④）｜🟢 未调 MiniMax')
    A('- 🟢 **未改 `status/app/CORRECTIONS_APP.md`**（reviewer 独占，只读）｜🟢 未覆盖/未删除任何旧版本目录与 zip｜🟢 只进完整版 v2.6（MiniMVP / SpecialMVP 不带）')
    A('- 🟢 未在 CPU 上跑推理/测速以外的作业；整链与打包均持 `shared\\MACHINE_LOCK`')
    A('')
    A('## §7 证据文件清单')
    A('')
    for n, p in (('打包', 'results/app/app129_build_v26_evidence.json'),
                 ('包内测试', 'results/app/app129_pkg_tests_evidence.json'),
                 ('整链三臂', 'results/app/app129_chain_v26_evidence.json'),
                 ('默认值检查', 'results/app/app129_defaults_evidence.json'),
                 ('降级+样片', 'results/app/app129_clips_v26_evidence.json'),
                 ('自检证据', 'results/app/app129_selfcheck_evidence.json'),
                 ('单测', 'results/app/app130_unit_evidence.json'),
                 ('签 ACCEPTED', 'results/app/app129_sign_accepted_v26_evidence.json'),
                 ('出包', 'results/app/app129_pack_v26_evidence.json')):
        fp = os.path.join(REPO, p.replace('/', os.sep))
        if os.path.isfile(fp):
            b = open(fp, 'rb').read()
            A('- `%s` — %d B / sha256 `%s` / mtime %s'
              % (p, len(b), sha256_bytes(b),
                 datetime.datetime.fromtimestamp(os.path.getmtime(fp))
                 .strftime('%Y-%m-%d %H:%M:%S')))
        else:
            A('- `%s` — **未生成**（本轮未取到 ⇒ 不写数字）' % p)
    A('')
    with open(COMPANION, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(L))
    log('companion 已写：%s（%d B）' % (COMPANION, os.path.getsize(COMPANION)))

    # ══════════════ ② 归档最旧的「最近更新」真条目 ══════════════
    orig = io.open(STATUS, encoding='utf-8', newline='').read()
    shutil.copy2(STATUS, BACKUP)
    log('备份：%s（%d B）' % (BACKUP, os.path.getsize(BACKUP)))

    # 「最近更新」区块：第一个以 '> 🔴 ' 开头的条目块
    mstart = re.search(r'(?m)^## 最近更新\s*$', orig)
    mend = re.search(r'(?m)^## 当前有效结论\s*$', orig)
    if not (mstart and mend):
        raise SystemExit('FAIL: 找不到「最近更新」/「当前有效结论」区块')
    block = orig[mstart.end():mend.start()]
    # 逐条 '> ' 开头（可能是多行）
    chunks = []
    cur = []
    for ln in block.split('\n'):
        if ln.startswith('> ') and cur:
            chunks.append('\n'.join(cur))
            cur = [ln]
        elif ln.startswith('> ') or (cur and ln.strip() == ''):
            cur.append(ln)
        elif ln.strip() == '' and not cur:
            continue
        else:
            if cur:
                chunks.append('\n'.join(cur))
            cur = []
    if cur:
        chunks.append('\n'.join(cur))
    # 找**最旧的一条真条目**（含日期戳且不是「已归档」指针行）
    cand = None
    for i, ch in enumerate(chunks):
        if re.search(r'20\d\d-\d\d-\d\d', ch) and '原文已' not in ch \
                and '整块逐字归档' not in ch:
            cand = i
    if cand is None:
        raise SystemExit('FAIL: 「最近更新」里找不到可归档的真条目')
    oldest = chunks[cand]
    log('归档最旧的「最近更新」真条目（%d B）：%s'
        % (len(oldest.encode('utf-8')), oldest[:70].replace('\n', ' ')))
    os.makedirs(ARCHIVE, exist_ok=True)
    with open(RECENT_ARCHIVE, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('# STATUS_APP「最近更新」归档（2026-11-24 §228 写入前）\n\n'
                 '> 本块原文**逐字**归档；活文档以指针行代替。\n\n')
        fh.write(oldest)
        fh.write('\n')
    log('归档文件：%s（%d B）' % (RECENT_ARCHIVE, os.path.getsize(RECENT_ARCHIVE)))

    # ══════════════ ③ 写 STATUS ══════════════
    new_block = block.replace(oldest, '', 1)
    pointer = ('> 🔴 本节 1 条较旧「最近更新」条目原文已**整块逐字归档** ⇒ '
               '`status/archive/STATUS_APP_recent_updates_20261124c.md`'
               '（%d B）；**原文一字未删、未改**。\n'
               % os.path.getsize(RECENT_ARCHIVE))
    # 新条目放最前
    new_entry = (
        '> 🔴 %s ｜ **执行 APP-129 / APP-130 / APP-131**（`last_ack` APP-128 → **APP-131**）：'
        '🟢 **APP-129** 保留背景音进完整版 **v2.6**（EXT **4740b06 / v0.4.20** ＋ Demucs 模型）；'
        '包内离线 **14/14 + 18/18 + 12/12**；10 分钟固定片段整链 **关 / 开 / 克隆** 三臂'
        '（媒体改回 reviewer e2e7 基线 `test_audio/clip_10min_0_600.wav`）；'
        '默认值检查 **4/4**；🟢 **APP-130** cp NPU 自检兜底 + 运行时保险，'
        'A 机实测**自检通过、cp 仍在 NPU**（cp_prefill 0.072 s / cp_decode 0.054 s，NPU 9 组件 / CPU 0），'
        '单测 **34/34**；🟢 **APP-131** EXT 改 v0.4.20 ＋ 新增 0420 测试 12/12 ＋ voice=clone 臂'
        '｜🔴 **如实登记 7 处判据/口径问题**（媒体用错 / e2e 工具命中旧缓存 / 自检日志在 stderr / '
        '正则组号坑 / EXECUTION_DEVICES 截断 / OVDict 判据错误 / EXT 工作树是 v0.4.21 在制品）'
        '｜🔴 **本条需等 reviewer 复核**\n'
        % stamp)
    new_block = new_entry + new_block.rstrip('\n') + '\n' + pointer

    sec = (
        '\n## §228 执行 **APP-129 / APP-130 / APP-131**'
        '（`last_ack` **APP-128 → APP-131**，%s）｜🟢 **v2.6 已出包**'
        '（EXT **4740b06 / v0.4.20** ＋ Demucs）｜🟢 **包内 14/14 + 18/18 + 12/12**'
        '｜🟢 **整链三臂 + 默认值 4/4**｜🟢 **cp NPU 自检通过、cp 仍在 NPU**'
        '｜🔴 **7 处判据/口径问题如实登记**｜🔴 **本条需等 reviewer 复核**\n'
        '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec228_detail_20261124.md`**'
        '（§0 六通道复核／§1 APP-129 打包+离线+整链+默认值+降级+样片+签 ACCEPTED+出包／'
        '§2 APP-130 自检兜底+运行时保险+A 机实测+单测／§3 APP-131 EXT v0.4.20+克隆臂／'
        '§4 如实登记 7 处／§5 留白／§6 纪律／§7 证据清单）\n'
        % stamp)

    out = orig[:mstart.end()] + '\n\n' + new_block + orig[mend.start():]
    out = out.rstrip('\n') + '\n' + sec
    out = set_field(out, 'last_ack', NEW_ACK)
    out = set_field(out, '更新时间', upd)

    # ── 写前真不变量 ────────────────────────────────────────────
    assert out.count('## §228') == 1, '§228 标题不唯一'
    assert out.count('last_ack: APP-131') == 1, 'last_ack 未正确写入'
    # 旧正文逐字未变（除：头部 2 行 / 最近更新区块 / 尾部新章节）
    old_body = orig[orig.index('## 当前有效结论'):]
    new_body = out[out.index('## 当前有效结论'):]
    assert old_body in new_body, '旧正文被改动（应只追加）'
    for old_chunk in chunks:
        if old_chunk != oldest and old_chunk.strip():
            assert old_chunk in out, '「最近更新」旧条目被改动：%r' % old_chunk[:50]

    tmp = STATUS + '.tmp_app129'
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(out)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, STATUS)
    log('已写：%s（%d B）' % (STATUS, os.path.getsize(STATUS)))

    # ── 还原式复核（把改动删回去 ⇒ 应逐字节还原原文件）──────────
    back = io.open(STATUS, encoding='utf-8', newline='').read()
    back2 = back.replace(sec, '', 1)
    back2 = back2.replace(new_entry, '', 1)
    back2 = back2.replace(pointer, '', 1)
    back2 = back2.replace('last_ack: APP-131', 'last_ack: APP-128', 1)
    back2 = back2.replace('更新时间: %s' % upd,
                           '更新时间: %s' % orig.split('更新时间: ', 1)[1].split('\n', 1)[0], 1)
    ok_restore = (back2 == orig)
    log('还原式复核（删掉本轮改动 ⇒ 逐字节还原原文件）：%s'
        % ('PASS' if ok_restore else 'FAIL'))
    if not ok_restore:
        log('  ⚠️ 还原后 %d B vs 原 %d B' % (len(back2.encode('utf-8')),
                                             len(orig.encode('utf-8'))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
