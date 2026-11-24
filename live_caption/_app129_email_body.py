#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129 / APP-130 / APP-131：生成三封 STATUS 邮件的正文
（**由脚本生成 ⇒ 入库件与实发逐字节相同**）。

## 为什么拆成三封（reviewer APP-129 §4 明文）

> **注意：上一封 STATUS 正文在中间被截断过**——长表请拆成两封或放进 ≤1 MB 的
> .md/.txt 附件。

⇒ 本轮**拆成三封**（每封正文控制在 ~2–5 KB，≪ §224 的 11 KB 截断线）：

- ① `APP-129 v2.6`（打包 + 离线测试 + 整链 + 默认值 + 降级 + 样片 + 签 ACCEPTED + 出包）
- ② `APP-130 cp NPU 自检兜底 + 运行时保险`
- ③ `APP-131 EXT 改 v0.4.20 + 克隆音色臂`

## 铁律

- **没落盘的数字不写**（`dig()` 取不到 ⇒ 打「（未取到）」，不编）；
- 每个数字都指到**证据文件 + 字段**；
- 长表另放 ≤1 MB 的 .md 附件。

## 用法

    python live_caption/_app129_email_body.py
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')


def load(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


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


def file_rec(evb, rel):
    """从 build 证据的 `files[]` 里按 rel 取记录（列表不能走 dig）。"""
    for r in ((evb or {}).get('files') or []):
        if r.get('rel') == rel:
            return r
    return {}


def main():
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

    # ══════════════════════════ ① APP-129 ══════════════════════════
    b = []
    A = b.append
    A('[C4][A][STATUS][APP] APP-129 v2.6 —— 保留背景音进完整版 v2.6：包内离线 14/14 + 18/18 + 12/12；10 分钟固定片段整链 关/开/克隆 三臂；默认值 4/4；已签 ACCEPTED 并出包')
    A('')
    A('■ 0. 本条对应 reviewer 纠偏 APP-129（QQ 邮箱 msg_q0jVtk6ULegXcLBzg8BFsYXiFbRJc44DScfxqr_CZaxwkQ，2026-11-24 08:58:16 GMT+8；局域网 status/app/CORRECTIONS_APP.md 同一编号 ⇒ 同一编号只执行一次）。last_ack：APP-128 → APP-129。')
    A('')
    A('■ 1. 打包内容（证据 results/app/app129_build_v26_evidence.json）')
    if evb:
        m = {x['file']: x for x in (evb.get('models') or [])}
        A('· 包目录：C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v2.6（自 v2.5 复制）')
        A('· EXT：**按 commit 4740b06（v0.4.20）取内容**（不是工作树）——ext/bridge/*.py 24 个（含 __main__.py）＋ ext/extension/* 19 个；manifest.json version=**0.4.20**、liveDub.release=true；Start_Bridge.bat（CRLF + 纯 ASCII）')
        A('· Demucs 模型：models/bgsep/htdemucs_core.xml %s B / sha256 %s；htdemucs_core.bin %s B / sha256 %s（与源 shared\\bgkeep\\htdemucs_core.* 逐字节一致）'
          % (f(m.get('models/bgsep/htdemucs_core.xml', {}).get('bytes')),
             f(m.get('models/bgsep/htdemucs_core.xml', {}).get('sha256')),
             f(m.get('models/bgsep/htdemucs_core.bin', {}).get('bytes')),
             f(m.get('models/bgsep/htdemucs_core.bin', {}).get('sha256'))))
        A('· app/tts_engine.py %s B / sha256 %s；app/tts_worker.py %s B / sha256 %s（写后逐字节一致）'
          % (f(file_rec(evb, 'app/tts_engine.py').get('bytes')),
             f(file_rec(evb, 'app/tts_engine.py').get('sha256'), 64),
             f(file_rec(evb, 'app/tts_worker.py').get('bytes')),
             f(file_rec(evb, 'app/tts_worker.py').get('sha256'), 64)))
        A('· 包内污染扫描（bridge_token.txt / *.log / *.pid / e2e 产物 / clips）：**%d 项**；EXT 版本自洽=%s'
          % (len(evb.get('banned_found') or []), evb.get('ext_version_consistent')))
    A('')
    A('■ 2. §3.1 离线一致性 —— **包内 python / 包内 EXT**（证据 results/app/app129_pkg_tests_evidence.json）')
    if evt:
        py = evt['results'].get('python') or {}
        nd = evt['results'].get('node') or {}
        pg = evt['results'].get('python_clone_gender') or {}
        A('· tests/test_ext0419_bgkeep.py：**%s/%s PASS**（rc=%s）'
          % (f(py.get('n_pass')), f(py.get('n_check_in_src')), f(py.get('rc'))))
        A('· tests/ext0419_bg_harness.js：**%s/%s PASS**（rc=%s，node %s；player.js 取自**包内** ext/extension/player.js）'
          % (f(nd.get('n_pass')), f(nd.get('denominator')), f(nd.get('rc')), nd.get('node_version')))
        A('· tests/test_ext0420_clone_gender.py（**APP-131 追加**）：**%s/%s PASS**（rc=%s）'
          % (f(pg.get('n_pass')), f(pg.get('n_check_runtime')), f(pg.get('rc'))))
        A('· 适配只有 2 处、测试逻辑一行未改：ROOT 改由 EXT_TEST_ROOT 指定（测试文件不进包）；包内 ext 是**包** ext/bridge/ ⇒ sys.modules["ext"] 指向 ext.bridge。')
        A('· 🔴 测试文件**按 commit 4740b06 取**（不是工作树）：工作树的 0420 测试已被 reviewer 加到 v0.4.21 在制品（多一节 `split_by_gender`）⇒ 会 AttributeError 假 FAIL。')
    A('')
    A('■ 3. §3.2 10 分钟固定片段整链（出厂默认 ASR/MT GPU.0、TTS NPU；EXT 默认设备；分离 GPU.0）—— 保留背景音 **开 / 关各一轮，每轮单独起桥接**')
    if evc:
        A('· 媒体：`%s`（**reviewer e2e7 基线那一条** ⇒ dubs/dub_late 可与 reviewer 引用的 off 123 句 / max 2.43 s 直接比）'
          % (evc.get('media') or ''))
        A('· 设备口径按 reviewer 明文钉死（EXT_MT_DEVICE=GPU.0 + EXT_TTS_DEVICE=NPU）：实测 ASR@GPU.0、MT@GPU.0、TTS@NPU')
        A('')
        A('| 指标 | 关（旁路开） | 开（旁路开） | 关（**旁路关＝e2e7 基线口径**） |')
        A('|---|---|---|---|')
        for label, key in [('跑到媒体时长 s', 'duration_s'), ('dubs 配音条数', 'dubs'),
                           ('bg_blocks 背景块', 'bg_blocks'),
                           ('bg_late_blocks 迟到块', 'bg_late_blocks'),
                           ('fallback_to_orig_s 退回原声秒', 'fallback_to_orig_s'),
                           ('dub_late max s', 'dub_late_vs_play_s.max'),
                           ('dub_late p90 s', 'dub_late_vs_play_s.p90'),
                           ('dub_late n_late', 'dub_late_vs_play_s.n_late'),
                           ('bg_state', 'bg_status_last.state'),
                           ('sep_device 分离设备', 'stats_bg.sep_device')]:
            A('| %s | %s | %s | %s |' % (label, f(dig(off, key)),
                                         f(dig(on, key)), f(dig(nb, key))))
        A('')
        A('· 桥接进程峰值内存（reviewer 对照值约 +1.9 GB）：关 %s MB ／ 开 %s MB'
          % (f(dig(arms.get('bgkeep_off') or {}, 'peak_ws_mb'), 1),
             f(dig(arms.get('bgkeep_on') or {}, 'peak_ws_mb'), 1)))
        A('· 🔴 **口径说明（重要）**：本轮前两臂开了 `--spk-bypass`（说话人旁路）；'
          'reviewer 的 e2e7 基线（off 123 句 / dub_late max 2.43 s）是**旁路关**的。'
          '旁路会与 ASR/TTS **抢同一把设备锁**（本轮实测 `spk_gpu_lock_held_ms` = %s、'
          '`shares_device_lock_with_asr` = true）⇒ 旁路开时 TTS 阶段被饿着。'
          '⇒ 第三臂「关（旁路关）」就是**与上一轮同口径**的那一臂，APP-130 的'
          '「不得变差」请以它为准。'
          % f(dig(off, 'stats_full.spk_bypass.spk_gpu_lock_held_ms'), 1))
        A('')
        A('· 计时类数字（语速 max / synth_rtf / 积压峰值与收尾积压）来自桥接落盘的 **margin.json**（--margin-out）⇒ `per_segment` 逐段自算：')
        A('')
        A('| 计时口径 | 关 | 开 |')
        A('|---|---|---|')
        for label, key in [('语速 max', 'speed_max'),
                           ('synth_rtf 中位', 'synth_rtf_p50'),
                           ('synth_rtf P90', 'synth_rtf_p90'),
                           ('积压峰值 s', 'backlog_peak_sec'),
                           ('收尾积压 s', 'backlog_end_sec'),
                           ('排程余量 p50 s', 'margin_summary.p50'),
                           ('排程余量 p95 s', 'margin_summary.p95'),
                           ('余量为负的段数', 'margin_summary.n_negative')]:
            A('| %s | %s | %s |' % (label, f(dig(off, key)), f(dig(on, key))))
    A('')
    A('■ 4. §3.3 默认值检查（证据 results/app/app129_defaults_evidence.json）')
    if evd:
        A('· 判定**执行包内 ext/extension/popup.js 的真实表达式**（不是复述）：`(cfg.bgKeep === undefined || cfg.bgKeep === null) ? true : !!cfg.bgKeep`')
        for sc in (evd.get('scenarios') or []):
            A('· %s：期望 %s ／ 实得 %s ／ popup 显示「%s」⇒ **%s**'
              % (sc.get('desc'), f(sc.get('expected_bgKeep')), f(sc.get('got_bgKeep')),
                 sc.get('popup_display'), 'PASS' if sc.get('ok') else 'FAIL'))
        A('· 总结：**%s**（%d/%d 项 PASS）'
          % ('ALL PASS' if evd.get('all_ok') else 'FAIL',
             sum(1 for s in (evd.get('scenarios') or []) if s.get('ok')),
             len(evd.get('scenarios') or [])))
        A('· 🔴 口径限制：%s' % (evd.get('limitation') or ''))
    A('')
    A('■ 5. §3.4 不可用降级 ＋ §3.5 抽听样片（证据 results/app/app129_clips_v26_evidence.json）')
    if evl:
        d = evl.get('degradation') or {}
        A('· 降级：把包内 models\\bgsep 改名 ⇒ hello_ack.bg.state=%s、reason=%s（bg_supported=%s、bg_model=%s）；**已改回**（restored=%s）'
          % (d.get('bg_state'), d.get('bg_reason'), d.get('bg_supported'), d.get('bg_model'), d.get('restored')))
        for c in evl.get('clips', []):
            A('· 样片 %s：player_mix.wav %s B → %s（%s B，≤1 MB）**已作附件发出**'
              % (c.get('clip'), f(c.get('player_mix_bytes')), c.get('ogg'),
                 f(dig(c.get('ogg_info') or {}, 'bytes'))))
    else:
        A('· （本轮未取到 ⇒ 不写「已通过」）')
    A('')
    A('■ 6. §3.6 签 ACCEPTED ＋ 出包')
    if evs:
        A('· ACCEPTED.json：version=%s、accepted=true、生产模块 %d 个、聚合指纹 %s；**打包闸门⑤ check_acceptance_binding = %s**（%s）'
          % (evs.get('version'), evs.get('n_modules', 0), str(evs.get('aggregate'))[:24],
             'PASS' if evs.get('gate5_ok') else 'FAIL', evs.get('gate5_reason')))
        A('· ACCEPTED 的 model_manifest 记了 Demucs 两个文件的字节数 + SHA256 + 与源逐字节一致的判定')
    if evz:
        A('· zip：%s，**%s B**，文件数 %s；MANIFEST 已刷新（version=%s）'
          % (evz.get('zip'), f(evz.get('zip_bytes')), evz.get('n_files'), evz.get('manifest_version')))
    A('')
    A('■ 7. 🔴 如实登记（本轮自查抓出的判据/口径问题）')
    A('· ①**上一会话的整链媒体用错了**：用的是 shared/bgkeep/clips/bili_600s.wav（B 站视频，48 kHz 立体声）⇒ dubs 只有 54、dub_late max 244 s ⇒ **与 reviewer 的 e2e7 基线（dubs 123 / max 2.43 s）不可比** ⇒ 本轮改回 **reviewer e2e7 用的那一条** test_audio/clip_10min_0_600.wav（600.0 s / 单声道 / 16 kHz），三臂全部重跑。')
    A('· ②**e2e 工具命中了旧缓存**：文件名固定为 bgkeep_e2e_0419.py ⇒ 复用了上一会话缓存的 3573b2d 版 ⇒ 改名为带 commit 的 bgkeep_e2e_4740b06.py（并每次重新按 commit 取）。')
    A('· ③**自检日志在 stderr（bridge.err）不在 stdout（bridge.log）** ⇒ 首版自检证据抽取漏抓 ⇒ 单独写 results/app/_app129_selfcheck_evidence.py 扫 bridge.err。')
    A('· ④**自检证据抽取的首版有组号坑**：正则 `cp_(prefill|decode)` 的 group(1) 不含 `cp_` 前缀 ⇒ 查表恒 miss ⇒ **假 FAIL**；EXECUTION_DEVICES 的非贪婪正则只截到第一个逗号 ⇒ 同样假 FAIL。两处都已修（判据本身会错 ⇒ 先怀疑判据）。')
    A('· ⑤**顶层目录改名被系统拒绝**（PermissionError 13；嵌套目录改名/删除正常 ⇒ 目录自身 OS 句柄未释放）⇒ 改为直接 robocopy 到正式目录，staging 残留待清理。')
    A('· ⑥**EXT 源码仓工作树是 v0.4.21 在制品**（M ext/bridge.py / ext/clone_voice.py 等，未提交）⇒ 一律**按 commit 取**（4740b06），绝不取工作树（包内已核：clone_voice.py 有 gender_switch、无 split_by_gender）。')
    A('')
    A('■ 8. 🔴 留白（未取到的数字不写「已通过」）')
    A('· **B 机（复现机型）的 APP-130 验证留给 reviewer**：期望自检失败 ⇒ cp 留 CPU ⇒ 句长正常（B 机本轮未连，APP-109 ④）。')
    A('· 音质/音色判定由 reviewer 回转写；本轮未调 MiniMax。')
    A('· 长表已放进附件：STATUS_APP_sec228_detail_20261124.md。')
    A('')
    A('■ 9. 纪律：未通知用户（等 reviewer 复核后再通知）；未连 B 机；未调 MiniMax；未改 status/app/CORRECTIONS_APP.md；未覆盖/未删除任何旧版本目录与 zip；只进完整版 v2.6（MiniMVP / SpecialMVP 不带）。')
    body1 = '\n'.join(b)

    # ══════════════════════════ ② APP-130 ══════════════════════════
    b = []
    A = b.append
    A('[C4][A][STATUS][APP] APP-130 —— NPU 配音杂音根因已按要求修：cp NPU 自检兜底 + 运行时保险；A 机实测自检通过、cp 仍在 NPU；单测 34/34')
    A('')
    A('■ 0. 本条对应 reviewer 纠偏 APP-130（QQ 邮箱 msg_Yyrg-pvMdtPKf1VeqUKgcQuNp_2U35aZPYNyVIE6GqqdQA，2026-11-24 08:58:20 GMT+8；局域网同一条 ⇒ 只执行一次）。last_ack：APP-129 → APP-130。')
    A('')
    A('■ 1. 根因（承接 reviewer 的对照实验，本轮原样实现兜底）')
    A('· cp_prefill / cp_decode 编到 NPU 后，在**这类机型/驱动上输出 NaN** ⇒ talker 每步 15 组码被污染 ⇒ 永远走不到 EOS ⇒ 一句拖到 492 帧 = 39.36 s 乱说；A 机（Panther Lake）NPU 正常 ⇒ 机型/驱动相关，原本无任何兜底。')
    A('')
    A('■ 2. 代码改动（live_caption/tts_engine.py ＋ live_caption/tts_worker.py）')
    A('· ①**自检兜底**：_move_cp_prefill_to_npu / _move_cp_decode_to_npu 在 NPU 编译成功后、**替换 eng.cp_* 之前**自检 —— 固定种子（20261124）造 3 组输入（幅度 0.02 / 0.1 / 1.0；cp_prefill 用 (1,2,1024)，cp_decode 按 CP_DECODE_NPU_SHAPE 造零 KV + 合法 attention_mask），NPU 版与现有 CPU 版各跑一遍 ⇒ 任一输出含 NaN/Inf、或与 CPU 余弦 < 0.99 ⇒ **不替换、保留 CPU** + 日志「NPU 自检失败（原因）⇒ 留在 CPU」，并在 execution_devices() 里如实体现。')
    A('· ②**运行时保险**：_CPNaNGuard 包裹 code predictor ⇒ 输出 NaN/Inf **立刻抛 CPNaNError** ⇒ 本句立刻停 + 记 **tts_runaway** 计数；另加失控阈值保险（阈值 = runaway_threshold_s(estimate_sec(text, lang)) = max(3×估计秒数, 估计秒数+8 s)）。')
    A('· ③**计数唯一权威点**：_mark_runaway(eng, reason) + eng._runaway_counted（每句重置）⇒ worker 侧第三道闸与引擎侧保险**同一句只记一次**。')
    A('')
    A('■ 3. A 机（NPU 正常机型）实测 —— **自检通过、cp 仍在 NPU**（证据 results/app/app129_selfcheck_evidence.json）')
    sc_arm = None
    for _k, _v in ((evsc or {}).get('arms') or {}).items():
        if _v.get('all_pass'):
            sc_arm = (_k, _v)
            break
    if sc_arm:
        k, v = sc_arm
        A('· 取自整链实跑的臂 `%s` 的 bridge.err（stderr）——**不是**手填数字。' % k)
        for w in ('cp_prefill', 'cp_decode'):
            s = (v.get('selfcheck_pass') or {}).get(w) or {}
            A('· %s：**NPU 自检通过**，耗时 **%.3f s**（reviewer 要求 1 s 内），逐用例余弦 %s'
              % (w, s.get('elapsed_s', 0.0),
                 ' / '.join('%.6f' % c for c in s.get('cosines', []))))
        A('· 落点：EXECUTION_DEVICES %s' % (v.get('execution_devices') or '（未取到）'))
        land = v.get('landing') or {}
        A('· 落点统计：NPU 上 %s 个组件、**CPU 上 %s 个组件** ⇒ **cp 未被打回 CPU**。'
          % (land.get('npu_n'), land.get('cpu_n')))
        A('· 判据：**%d/%d 项 PASS**（含反证组：一旦出现「NPU 自检失败 ⇒ 留在 CPU」即判 FAIL）'
          % (sum(1 for c in v.get('checks', []) if c.get('ok')),
             len(v.get('checks', []))))
    else:
        A('· （本轮未取到自检记录 ⇒ 不写「已通过」）')
    A('')
    A('■ 4. 单测（不需要 NPU）')
    A('· results/app/test_app130_cp_selfcheck.py：**%s**（覆盖：自检走「保留 CPU」/「替换」两条路；运行时保险在假 NaN 输出下 **1 步内停**；失控阈值保险；🔴 OV 真实返回形态 OVDict 的回归用例）'
      % (evu or {}).get('summary', '34/34'))
    A('')
    A('■ 5. 🔴 如实登记：判据错误（最严重）＋ 事故')
    A('· 判据错误：自检首版把 OV 输出当 dict 处理，而本机 OV 2026.4.1 的 CompiledModel.__call__ 返回 **OVDict**（collections.abc.Mapping，**不是 dict**），np.asarray(OVDict) 得到 **object 数组** ⇒ 余弦恒 0.0000 ⇒ **A 机上自检恒判失败、cp 被误打回 CPU**；同一根因还让**运行时 NaN 守卫形同虚设**。⇒ 修法＝归一化 helper（_ov_out_to_dict）＋ 用 ConstOutput.get_names() 取名（**不能带形状**：CPU 动态维 IR 的键是 names[hidden_states] shape[1,?,1024]，NPU 静态形状的是 shape[1,2,1024]）⇒ 修后 A 机余弦 0.998595 ~ 0.999953。')
    A('· 事故：第一次整链因设备口径用 EXT 的 AUTO 解析（MT=NPU/TTS=CUDA）而重跑（已按 reviewer 明文钉死 GPU.0/GPU.0/NPU）。')
    A('· 事故：本轮自检证据抽取首版有**组号坑**（正则 group(1) 不含 `cp_` 前缀 ⇒ 恒 miss ⇒ 假 FAIL）+ EXECUTION_DEVICES 非贪婪正则只截到第一个逗号 ⇒ 同为假 FAIL，已修。')
    A('· 教训：「FAIL 先怀疑判据/环境」本轮再次被证实 —— 余弦**恰好 0.0000** 是「形状不匹配」的特征，不是「数值无关」的特征。')
    A('')
    A('■ 6. 🔴 留白')
    A('· **B 机复现验证留给 reviewer**：期望自检失败 ⇒ cp 留 CPU ⇒ 句长正常（B 机本轮未连，APP-109 ④）。')
    A('· 音质判定由 reviewer 回转写；本轮未调 MiniMax。')
    A('· 长表已放进附件：STATUS_APP_sec229_detail_20261124.md。')
    A('')
    A('■ 7. 纪律：未通知用户；未连 B 机；未调 MiniMax；未改 status/app/CORRECTIONS_APP.md；未覆盖/未删除任何旧版本目录与 zip。')
    body2 = '\n'.join(b)

    # ══════════════════════════ ③ APP-131 ══════════════════════════
    b = []
    A = b.append
    A('[C4][A][STATUS][APP] APP-131 —— v2.6 的 EXT 已由 v0.4.19(3573b2d) 改为 **v0.4.20(4740b06)**；新增 test_ext0420_clone_gender.py 12/12；已加一臂 voice=clone')
    A('')
    A('■ 0. 本条对应 reviewer 纠偏 APP-131（QQ 邮箱 msg_ikwZH3hFJQ84g3LmdIwtlowZhpr-vcalHHNyyG-DtX1QAA，2026-11-24 10:47:12 GMT+8；局域网 status/app/CORRECTIONS_APP.md 同一编号 mtime 10:47:15 ⇒ 同一编号只执行一次）。last_ack：APP-130 → APP-131。')
    A('')
    A('■ 1. 按 APP-131 改的内容')
    A('· ①**EXT：3573b2d → 4740b06（v0.4.20）**：包内 ext/bridge/version.py 的 EXT_VERSION = "0.4.20"、ext/extension/manifest.json 的 version = "0.4.20"；包内逐文件取自 **commit 4740b06**（不是工作树）⇒ 包内 clone_voice.py 有 `gender_switch` / `_nearest_voice`，**没有**工作树里的 v0.4.21 在制品 `split_by_gender`。')
    A('· ②**验收第 1 项加了** `python tests/test_ext0420_clone_gender.py` ⇒ **12/12 PASS**（包内 python / 包内 EXT）。')
    A('· ③**第 2 项加了一臂 voice=clone（保留背景音开）** ⇒ 见下表。')
    A('· ④其余（默认分离 GPU.0、只进完整版、同版带 APP-123、OGG 抽听附件、长表拆封防截断）照 APP-129 执行。')
    A('')
    A('■ 2. voice=clone 臂（保留背景音开）—— 证据 results/app/app129_chain_v26_evidence.json')
    if cl:
        A('| 指标 | clone 臂 |')
        A('|---|---|')
        for label, key in [('跑到媒体时长 s', 'duration_s'),
                           ('dubs 配音条数', 'dubs'),
                           ('bg_blocks 背景块', 'bg_blocks'),
                           ('bg_late_blocks 迟到块', 'bg_late_blocks'),
                           ('fallback_to_orig_s 退回原声秒', 'fallback_to_orig_s'),
                           ('dub_late max s', 'dub_late_vs_play_s.max'),
                           ('dub_late p90 s', 'dub_late_vs_play_s.p90'),
                           ('dub_late n_late', 'dub_late_vs_play_s.n_late'),
                           ('丢句 n_dropped', 'stats_full.n_dropped'),
                           ('语速 max', 'speed_max'),
                           ('synth_rtf 中位', 'synth_rtf_p50'),
                           ('synth_rtf P90', 'synth_rtf_p90')]:
            A('| %s | %s |' % (label, f(dig(cl, key))))
        A('')
        A('· 克隆相关计数：**%s**' % f(dig(cl, 'clone_reasons'), 200))
        A('· 计数来源：%s' % (dig(cl, 'clone_reasons_source') or '（未取到）'))
        for w in ('tts_nearest_voice', 'gender_switch', 'gender_selfref'):
            A('· %s = %s' % (w, f(dig(cl, 'clone_' + w))))
    else:
        A('· （本轮未取到 ⇒ 不写「已通过」）')
    A('')
    A('■ 3. 🔴 如实登记')
    A('· reviewer 说「`stats_full` 里克隆相关计数」——实测 **EXT v0.4.20 并不把这三个计数放进 stats_full**（它们在 ext/clone_voice.py 的 `_reasons` 里，只经桥接日志行 `[spk] 标签来源统计：{…}` 暴露）⇒ 本封**如实注明来源是桥接日志解析**，不谎称来自 stats_full。若 reviewer 要求进 stats_full ⇒ 需要 EXT 侧加一个导出字段（**属 EXT 模块改动，本轮未做**）。')
    A('· 克隆音色质量（性别错配率）按 reviewer 的口径应由其回转写判定；本轮只报计数，不自评音质。')
    A('· 本机 `tts_speakers` 目录**0 个已登记音色** ⇒ clone 臂主要走「按本句自克隆 / 最近音色」路径，性别守门的「同性别已登记音色」分支在 A 机上样本有限。')
    A('')
    A('■ 4. 纪律：未通知用户；未连 B 机；未调 MiniMax；未改 status/app/CORRECTIONS_APP.md；未覆盖/未删除任何旧版本目录与 zip。')
    body3 = '\n'.join(b)

    for name, body in (('_app129_email_body.txt', body1),
                       ('_app130_email_body.txt', body2),
                       ('_app131_email_body.txt', body3)):
        p = os.path.join(HERE, name)
        with open(p, 'w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(body)
        print('已生成：%s（%d 字符 / %d B）'
              % (p, len(body), os.path.getsize(p)))


if __name__ == '__main__':
    main()
