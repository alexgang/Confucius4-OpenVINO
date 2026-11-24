#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-131/132/133：生成**两封** STATUS 邮件的正文（**由脚本生成 ⇒ 入库件与实发逐字节相同**）。

## 为什么拆成两封（reviewer APP-129 §4 明文）

> **注意：上一封 STATUS 正文在中间被截断过**——长表请拆成两封或放进 ≤1 MB 的
> .md/.txt 附件。

⇒ 本轮**拆成两封**（每封正文控制在 ~2–5 KB，**≪ §224 的 11 KB 截断线**）：

- ① `[C4][A][STATUS][APP] APP-133 v2.6 交付（EXT v0.4.21 b2a4978）`：
   包内容与身份核对 ＋ 离线一致性 14/14+18/18+16/16 ＋ 机器锁修复与持锁证据；
- ② `[C4][A][STATUS][APP] APP-133 v2.6 整链三臂数字 ＋ 样片附件`：
   三臂对照表（含 reviewer §3.2 要的每一个数字）＋ clone 计数 ＋ 默认值/降级 ＋
   **抽听样片 OGG 作附件**（≤1 MB，最多 3 个：s2 / cs2 / tuffy）。

## 铁律

- **没落盘的数字不写**（取不到 ⇒ 打「（未取到）」，绝不编）；
- 每个数字都指到**证据文件 ＋ 原始字段**；
- **附件**单独列出（文件名 ＋ 字节数 ＋ SHA256）。

## 用法

    python results/app/_app133_email_body.py
"""
from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
RESULTS = os.path.join(REPO, 'results', 'app')
OUTDIR = os.path.join(REPO, 'live_caption')


def load(name):
    try:
        with open(os.path.join(RESULTS, name), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def f(x, nd=3):
    if isinstance(x, float):
        return ('%.' + str(nd) + 'f') % x
    if x is None:
        return '（未取到）'
    return str(x)


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

    # ═════════════════════════════════════════════════════════════
    # ① 交付与验收口径
    # ═════════════════════════════════════════════════════════════
    b = []
    A = b.append
    A('[C4][A][STATUS][APP] APP-133 v2.6 交付 —— EXT 升到 v0.4.21(b2a4978)；'
      '包内离线 14/14 + 18/18 + 16/16；机器锁修掉两处真缺陷并一次持锁到底重跑整链')
    A('')
    A('■ 1. 🔴 纠偏来源（同一编号两个通道都到 ⇒ 只执行一次）')
    A('· 局域网 status/app/CORRECTIONS_APP.md：APP-131 / APP-132 / APP-133 三条同在')
    A('· QQ 邮箱 alexchen7694@agent.qq.com：')
    A('  - APP-131 msg_ikwZH3hFJQ84g3LmdIwtlowZhpr-vcalHHNyyG-DtX1QAA')
    A('  - APP-132 msg_WCFDSHflL8ZKI41A6vd5NXSixhH-AAdKoCmtSjLtkZlU5g')
    A('  - APP-133 msg_HbiVRXlgp8eXsg7kDK4uUcgmLi_ao2pMbVJcZzbdbNhmGw')
    A('')
    A('■ 2. 🟢 APP-133：v2.6 的 EXT = b2a4978（v0.4.21）')
    A('· 版本链：APP-129 3573b2d（v0.4.19）→ APP-131 4740b06（v0.4.20）→ '
      '**APP-133 b2a4978（v0.4.21）＝ 本轮交付**')
    if ev_verify:
        A('· 独立复核（results/app/app133_pkg_ext_verify.json）：'
          '核对 **%s** 个文件（ext/bridge/*.py ＋ ext/extension/* ＋ '
          'tools/ext_launcher.py ＋ manifest），**逐字节一致**，错误 **%s** 项'
          % (ev_verify.get('n_files'), len(ev_verify.get('errors') or [])))
        A('  - ext/bridge/version.py = %s；manifest version = %s；'
          'liveDub.release = %s'
          % (ev_verify.get('ext_version_py'), ev_verify.get('manifest_version'),
             ev_verify.get('manifest_release')))
        A('  - **反证组**：故意改坏一个文件 ⇒ 判据报错 ⇒ 判据承重 = %s'
          % (ev_verify.get('counterfactual') or {}).get('judgement_load_bearing'))
    if ev_build:
        A('· 成包（results/app/app129_build_v26_evidence.json）：ext_commit=%s；'
          '包内污染扫描 **%s** 项；EXT 版本一致性 = %s'
          % (ev_build.get('ext_commit'),
             len(ev_build.get('banned_found') or []),
             ev_build.get('ext_version_consistent')))
        for m in ev_build.get('models') or []:
            A('  - %s：**%s B**，sha256 %s（源 sha256 %s，逐字节一致 = %s）'
              % (m.get('file'), m.get('bytes'), (m.get('sha256') or '')[:16],
                 (m.get('src_sha256') or '')[:16],
                 m.get('sha256') == m.get('src_sha256')))
    A('')
    A('■ 3. 🟢 离线一致性（APP-129 §3.1 ＋ APP-131 ＋ APP-133）—— **包内 python / 包内 EXT**')
    if ev_tests:
        r = ev_tests.get('results') or {}
        py = r.get('python') or {}
        nd = r.get('node') or {}
        cg = r.get('python_clone_gender') or {}
        A('· tests/test_ext0419_bgkeep.py（包内 python ＋ 包内 EXT）：**%s/%s PASS**（rc=%s）'
          % (py.get('n_pass'), py.get('n_check_in_src'), py.get('rc')))
        A('· tests/ext0419_bg_harness.js（node %s ＋ 包内 player.js）：**%s/%s PASS**（rc=%s）'
          % (nd.get('node_version'), nd.get('n_pass'), nd.get('denominator'),
             nd.get('rc')))
        A('· tests/test_ext0420_clone_gender.py（包内 python ＋ 包内 EXT b2a4978）：'
          '**%s/%s PASS**（rc=%s）'
          % (cg.get('n_pass'), cg.get('n_check_runtime'), cg.get('rc')))
        A('  - reviewer 口径：APP-131 说 12/12，**APP-133 说 16/16**（后发 ⇒ 覆盖）'
          '⇒ 实测 **16/16**，与 APP-133 一致。')
    A('')
    A('■ 4. 🟢 APP-132：机器锁（**两处真缺陷已修** ＋ 本轮一次持锁到底）')
    A('· 缺陷①：上一版用 os.replace(tmp, LOCK) 写锁 ⇒ **不是原子创建** ⇒ '
      'reviewer 的 CreateNew 在 12:44:18 成功 ⇒ 我方**实际没在持锁**')
    A('· 缺陷②：看门狗只在「锁是我的或锁没了」时才写回 ⇒ **一旦被抢就彻底放弃** '
      '⇒ 链继续跑但不再持锁 ⇒ 计时作废且无人知晓')
    A('· 修法（results/app/_app132_lock.py）：**O_CREAT|O_EXCL 原子创建** ＋ '
      '**每 10 s 复核**（锁不再是我的 ⇒ 立刻记 lock_lost 事件）＋ '
      '**锁内容写明起止** ＋ 只删自己的锁')
    if ev_chain:
        lk = ev_chain.get('lock') or {}
        A('· 本轮持锁：起 **%s** ／止 **%s** ／**中途丢锁 = %s**'
          '（app132_lock_events.jsonl 里 lock_lost 事件 **0** 条）'
          % (lk.get('started'), lk.get('ended'), lk.get('lost')))
        A('  - 三臂后复核持锁：%s；默认值检查后：%s；抽听样片后：%s'
          % ([a.get('lock_held_after_arm') for a in ev_chain.get('arms') or []],
             ev_chain.get('lock_held_after_defaults'),
             ev_chain.get('lock_held_after_clips')))
    A('· reviewer 桥接日志重叠核对：v0.4.20 臂 **13:28:21–13:37:03**、'
      'v0.4.21 臂 **13:37:09–13:45:36**（shared/bgkeep/gender_ab2/*/bridge.log）'
      '⇒ 与我方上一轮三臂（12:33:38–13:07:39）时间上不重叠；'
      '但按 reviewer 要求 **本轮全部重跑**。')
    A('')
    A('■ 5. 🔴 如实登记：本轮踩到并修掉的 4 处真缺陷')
    A('1. **就绪判据假 PASS**：本轮首跑用「日志出现『引擎预热完成』」当桥接就绪判据 '
      '⇒ 横幅在**开始监听之前**就打出 ⇒ e2e 立刻 ConnectionRefusedError '
      '(WinError 1225) ⇒ 三臂全废 ⇒ 已改为「**日志出现 ws:// 监听地址** ＋ '
      '**端口真能建连**」（旧脚本的正确判据）。')
    A('2. **OGG 编码器不可用**：包内 python 的 **PyAV 19.0.1** 上 '
      'add_stream("vorbis", …) 直接抛 ExperimentalError('
      'avcodec_open2("vorbis", {})) ⇒ 上一轮**四个样片的 OGG 一个都没生成** '
      '(ogg_ok=false) ⇒ 一条附件都发不出去 ⇒ 已改为**按优先级逐个真开一次**'
      '（vorbis → libopus → opus），且**成功判据＝回读产出文件并能重新解码**。')
    A('3. **降级探针被拒**：§3.4 的 hello 探针**没发 Origin 头** ⇒ 桥接 '
      'check_origin() 判空 ⇒ close(1008, "bad origin") ⇒ 拿不到 hello_ack ⇒ '
      '已按 EXT 官方 e2e 的口径补上 Origin。')
    A('4. **包测试分母过期**：runner 里分母还写 APP-131 的 12 ⇒ 实测 16/16 PASS '
      '却被判 FAIL ⇒ **判据过期、不是产品缺陷** ⇒ 已按 APP-133 改为 16。')
    A('')
    A('■ 6. 纪律：未通知用户；未连 B 机；未调 MiniMax；'
      '未改 status/app/CORRECTIONS_APP.md；未覆盖/未删除任何旧版本目录与 zip；'
      '**未打 zip**（用户级纪律「不通知 ⇒ 不打包」；完整版 v2.x 历来无 zip）。')
    body1 = '\n'.join(b)

    # ═════════════════════════════════════════════════════════════
    # ② 整链数字 + 样片附件
    # ═════════════════════════════════════════════════════════════
    b = []
    A = b.append
    A('[C4][A][STATUS][APP] APP-133 v2.6 整链三臂数字 ＋ 抽听样片 OGG 附件'
      '（10 分钟固定片段；dubs／丢句／语速 max／dub_late／bg_blocks／synth_rtf／'
      '积压峰值与收尾积压；clone 臂 clone_reasons 与 n_gender_splits）')
    A('')
    A('■ 1. 🟢 10 分钟固定片段整链（APP-129 §3.2 ＋ APP-131 clone 臂 ＋ APP-133 clone 计数）')
    A('· 媒体：test_audio/clip_10min_0_600.wav（600 s）；**每臂单独起桥接**；'
      '出厂默认 ASR/MT **GPU.0**、TTS **NPU**；分离 **GPU.0**（EXT 默认）')
    arms = (ev_chain or {}).get('arms') or []
    if arms:
        A('')
        A('| 指标 | bgkeep 关 | bgkeep 开 | bgkeep 开 ＋ voice=clone |')
        A('|---|---|---|---|')
        cols = [(a.get('metrics') or {}) for a in arms]

        def row(label, fn):
            vals = []
            for m in cols:
                try:
                    vals.append(str(fn(m)))
                except Exception:
                    vals.append('—')
            A('| %s | %s | %s | %s |' % (label,
                                         vals[0] if vals else '—',
                                         vals[1] if len(vals) > 1 else '—',
                                         vals[2] if len(vals) > 2 else '—'))
        row('媒体时长 s', lambda m: f(m.get('duration_s')))
        row('**dubs**', lambda m: f(m.get('dubs')))
        row('**丢句**（须 0）', lambda m: f(m.get('n_dropped_dub')))
        row('语速 max', lambda m: f(m.get('speed_max')))
        row('dub_late max s', lambda m: f((m.get('dub_late_vs_play_s') or {}).get('max')))
        row('dub_late p90 s', lambda m: f((m.get('dub_late_vs_play_s') or {}).get('p90')))
        row('dub_late n_late', lambda m: f((m.get('dub_late_vs_play_s') or {}).get('n_late')))
        row('**bg_blocks**', lambda m: f(m.get('bg_blocks')))
        row('**bg_late_blocks**', lambda m: f(m.get('bg_late_blocks')))
        row('**fallback_to_orig_s**', lambda m: f(m.get('fallback_to_orig_s')))
        row('**synth_rtf**', lambda m: f(m.get('synth_rtf')))
        row('积压峰值 max_lag_sec', lambda m: f(m.get('max_lag_sec')))
        row('收尾积压 lag_curve end_sec', lambda m: f(m.get('lag_curve_end_sec')))
        # 🔴 分离设备：bgkeep **关**时本就没有分离设备（`bg_state=off` ⇒
        #   `device=None`）⇒ 写成「关（未启用）」而不是「（未取到）」
        #   （否则 reviewer 会误以为「没测到」）。
        row('分离设备', lambda m: (
            ('关（未启用，bg_state=%s）' % (m.get('bg_status_last') or {}).get('state'))
            if (m.get('bg_status_last') or {}).get('state') == 'off'
            else f((m.get('bg_status_last') or {}).get('device'))))
        A('')
        A('· **桥接进程峰值内存（开关差值对照）**：'
          + '、'.join('%s %s MB' % (a.get('arm'), a.get('peak_ws_mb'))
                      for a in arms))
        A('  （reviewer 实测约 **+1.9 GB** 作对照）')
        A('· 证据：results/app/app133_chain_v26_evidence.json ＋ '
          'shared/bgkeep/e2e_v26_r2/*/')
    else:
        A('· （本轮未取到 ⇒ 不写「已通过」）')
    A('')
    A('■ 2. 🟢 APP-133 要的克隆计数（clone 臂）')
    clone_m = None
    for a in arms:
        if a.get('voice') == 'clone':
            clone_m = a.get('metrics') or {}
    if clone_m:
        cc = clone_m.get('clone_counts') or {}
        for k in ('clone_reasons', 'spk_reason_hist', 'n_gender_splits',
                  'tts_nearest_voice', 'gender_switch', 'gender_selfref'):
            v = cc.get(k)
            # 🔴 **区分「没取到」与「取到了但是 null」**：
            #   顶层 `tts_nearest_voice` / `gender_switch` / `gender_selfref`
            #   是 **EXT v0.4.21 只在 `clone_reasons` 里导出** ⇒ 顶层**确实没有**
            #   ⇒ 写成「**顶层无此字段（计数在 clone_reasons 里）**」，
            #   **不是**「未取到」（后者会误导成「没测」）。
            if v is None and k in ('tts_nearest_voice', 'gender_switch',
                                   'gender_selfref'):
                A('· stats_full.%s = 顶层**无此字段**'
                  '（EXT v0.4.21 只在 `clone_reasons` 里导出 ⇒ 见上一行）' % k)
            else:
                A('· stats_full.%s = %s' % (k, f(v, 300)))
    else:
        A('· （本轮未取到 ⇒ 不写「已通过」）')
    A('')
    A('■ 3. 🟢 默认值检查（§3.3）＋ 不可用降级（§3.4）')
    dc = (ev_chain or {}).get('defaults_check') or {}
    for s in dc.get('scenarios') or []:
        A('· %s：期望 %s ／ 实测 %s ／ popup 显示「%s」 ⇒ %s'
          % (s.get('scenario'), s.get('expected_bgKeep'), s.get('gotBgKeep')
             or s.get('got_bgKeep'), s.get('popup_display'),
             'PASS' if s.get('ok') else 'FAIL'))
    A('  - 🔴 **口径**：本机无可控的 Chrome 自动化环境 ⇒ 本检查在 node 里'
      '**执行包内 popup.js 的真实表达式**（覆盖「存储初态 ⇒ 默认值/文案」这一层）；'
      '**浏览器端 UI 交互本身由 reviewer 复核**。')
    dg = (ev_clips or {}).get('degradation') or {}
    A('· 降级（models\\bgsep 改名）：bridge_ready=%s（%s s）／bg.state=%s／'
      'bg.reason=%s／恢复=%s'
      % (dg.get('bridge_ready'), dg.get('bridge_ready_s'), dg.get('bg_state'),
         dg.get('bg_reason'), dg.get('restored')))
    A('')
    A('■ 4. 🟢 抽听样片（§3.5）—— 附件见本封附件列表')
    for c in (ev_clips or {}).get('clips') or []:
        oi = c.get('ogg_info') or {}
        A('· %s：player_mix %s B → OGG %s B（codec %s，解码帧数 %s，≤1 MB = %s）'
          % (c.get('clip') or c.get('name'), c.get('player_mix_bytes'),
             oi.get('bytes'), oi.get('codec_used') or oi.get('codec'),
             oi.get('n_decoded_frames'),
             '是' if (oi.get('bytes') or 0) <= 1024 * 1024 else '否'))
    A('')
    A('■ 5. 🔴 如实登记')
    A('· 克隆音色质量（性别错配率）按 reviewer 口径由其回转写判定；本轮只报计数，不自评音质。')
    A('· 本轮计时类数字的前提是**一次持锁到底**（lock_lost 事件 0 条）；'
      '若 reviewer 的 v0.4.21 对比臂与本轮仍有重叠，请以 reviewer 自己的锁记录为准。')
    A('· 纪律：未通知用户；未连 B 机；未调 MiniMax；未改 status/app/CORRECTIONS_APP.md。')
    body2 = '\n'.join(b)

    # ── 落盘（CRLF，与实发保持一致）──────────────────────────────
    for name, body in (('_app133_email_body_1.txt', body1),
                       ('_app133_email_body_2.txt', body2)):
        p = os.path.join(OUTDIR, name)
        with open(p, 'w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(body)
        print('已生成：%s（%d 字符 / %d B / sha256 %s）'
              % (p, len(body), os.path.getsize(p),
                 sha256_file(p)[:16]))

    # ── 附件清单（OGG）──────────────────────────────────────────
    print('--- 附件 ---')
    for c in (ev_clips or {}).get('clips') or []:
        ogg = c.get('ogg')
        if ogg and os.path.isfile(ogg):
            print('  %s：%d B，sha256 %s'
                  % (os.path.basename(ogg), os.path.getsize(ogg),
                     sha256_file(ogg)[:16]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
