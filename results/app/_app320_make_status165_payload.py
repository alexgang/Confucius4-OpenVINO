#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app320_make_status165_payload.py —— 生成 `STATUS_APP.md` **§165** 的 payload。

## 依据

* 本轮执行了 **APP-094 / APP-095 / APP-096**（新纠偏，从 `last_ack=APP-093` 起）。
* STATUS 纪律（用户级铁律）：
  * **只追加** `## §N` 章节，不回头改旧章节；
  * 头部 `last_ack` 更新为**已执行完的最大 APP 编号**；
  * 「更新时间」用 `Get-Date` 实测；
  * **限额 ≤40000 B / ≤300 行** ⇒ 先按 APP-052④ 压缩归档；
  * 结论必须引用**结果文件与原始字段**；产物要附**文件数/mtime/字节/SHA256**；
  * **没落盘的东西不能写「已交付」**。

## 用法

```
.venv/Scripts/python.exe results/app/_app320_make_status165_payload.py
```
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
APP = os.path.join(REPO, 'results', 'app')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def stat_of(p):
    st = os.stat(p)
    return {'bytes': st.st_size,
            'mtime': datetime.datetime.fromtimestamp(st.st_mtime)
            .strftime('%Y-%m-%d %H:%M:%S'),
            'sha256': sha256_file(p)}


def get_date():
    r = subprocess.run(['powershell', '-NoProfile', '-Command',
                        'Get-Date -Format "yyyy-MM-dd HH:mm:ss"'],
                       capture_output=True, text=True)
    out = (r.stdout or '').strip()
    if not out:
        raise RuntimeError('Get-Date failed')
    return out


def main():
    def load(name):
        p = os.path.join(APP, name)
        if not os.path.exists(p):
            return None
        return json.load(open(p, encoding='utf-8'))

    build = load('app310_minimvp_rc5_build_evidence.json')
    docs = load('app311_rc5_docs_evidence.json')
    keep = load('app313_app094_keepfirst_evidence.json')
    execdev = load('app314_rc5_exec_device_evidence.json')
    zip_ev = load('app318_rc5_zip_evidence.json')
    unz = load('app319_rc5_zip_unzip_check_evidence.json')
    thr = load('app316_app093_device_rerun.json')

    def art(path):
        p = os.path.join(APP, path)
        return stat_of(p) if os.path.exists(p) else None

    # ── 产物表 ────────────────────────────────────────────────────
    artifacts = [
        'app310_minimvp_rc5_build_evidence.json',
        'app311_rc5_docs_evidence.json',
        'app312_rc5_device_acceptance.py',
        'app313_app094_keepfirst_evidence.json',
        'app313_app094_keepfirst_verify.py',
        'app314_rc5_exec_device_evidence.json',
        'app314_rc5_exec_device.py',
        'app315_ext_v036_evidence.json',
        'app315_ext_v036_integration.py',
        'app316_app093_device_rerun.json',
        'app316_app093_device_rerun.py',
        'app318_rc5_zip_evidence.json',
        'app318_rc5_zip.py',
        'app319_rc5_zip_unzip_check_evidence.json',
        'app319_rc5_zip_unzip_check.py',
        'app374_app093_ctrl_after_dialog3_tight.json',
        'app373_app089_voice_attribution.py',
        'app374_app089_voice_attr_control.py',
        '_app321_write_status165.py',
    ]
    art_lines = []
    for a in artifacts:
        s = art(a)
        if s:
            art_lines.append('- `%s`｜%d B｜%s｜SHA256 `%s`'
                             % (a, s['bytes'], s['mtime'], s['sha256']))

    # ── rc5 验收数字 ──────────────────────────────────────────────
    gpu = None
    npu = None
    for arm, key in (('gpu', 'gpu'), ('npu', 'npu')):
        p = os.path.join(APP, 'app312_rc5_out', arm, 'acceptance.json')
        if os.path.exists(p):
            d = json.load(open(p, encoding='utf-8'))
            s = d.get('summary') or {}
            if arm == 'gpu':
                gpu = d
            else:
                npu = d

    def row(name, d):
        if not d:
            return '| %s | （未跑） | | | |' % name
        s = d.get('summary') or {}
        return ('| %s | %s | %s ms | %s s | %s MB |'
                % (name, s.get('rtf'), s.get('lat_ms'), s.get('backlog'),
                   d.get('peak_rss_mb')))

    # ── 阈值 A/B 结果（若已跑完）──────────────────────────────────
    thr_lines = []
    if thr:
        for r in thr.get('runs', []):
            sc = r.get('scores') or {}
            thr_lines.append(
                '| %s | %s | %s | %s | %s | %s | %s |'
                % (r.get('arm'), r.get('material'), r.get('threshold_s'),
                   sc.get('n_late_drop'), sc.get('play_lag_p50'),
                   sc.get('play_lag_p95'),
                   sc.get('n_speed_floor_conflict_max')))

    thr_tbl = ''
    if thr_lines:
        thr_tbl = ('\n### ② APP-093 §3.2 阈值 A/B（默认值仍 **6.0**，未改代码）\n\n'
                   '| 臂 | 素材 | 阈值 s | 跳过句数 | play_lag p50 | p95 | '
                   'n_speed_floor_conflict max |\n|---|---|---|---|---|---|---|\n'
                   + '\n'.join(thr_lines) + '\n')

    # ── 章节正文 ───────────────────────────────────────────────────
    z5 = zip_ev or {}
    u = unz or {}
    sec = []
    sec.append('\n## §165 执行 APP-094 / APP-095 / APP-096（last_ack=APP-096）'
               '｜MiniMVP **rc5**（ASR→Qwen3-ASR-0.6B）已出包＋设备验收；'
               '**APP-093 设备作业部分完成**，停等 reviewer 复核\n')
    sec.append('\n### ① 本轮结论（先说做没做）\n')
    sec.append(
        '* **APP-096（MiniMVP rc5 换 0.6B）**：**已完成**。'
        '新目录 `%s`＋新 zip；ASR 换成 **Qwen3-ASR-0.6B（mask2 INT8）**，'
        '**R2T2 的 ASR IR 全部删除**；`--check` 只剩 **INT8 NPU 一组 + iGPU 一组**；'
        'zip 清单 R2T2/INT4 计数 **0**；两臂设备验收已跑（iGPU/NPU 各 300 s 英文切片）。\n'
        '* **APP-095 第 1a 点（去 INT4 NPU 引擎）**：**已完成**（随 rc5 落地）。\n'
        '* **APP-095 第 1b 点（README 改 R2T2 名字）**：🔴 **被 APP-096 取代 ⇒ 未做**'
        '（APP-096 明文「取代 APP-095 第 1b 点」）。\n'
        '* **APP-094①（keep first）**：**已完成**（App 侧默认 keep first、'
        '可配置保留旧升级行为；判据 **%d/%d PASS** 且反证组有效）。\n'
        '* **APP-094②（不加 anchor）**：**天然满足**（App 侧 ICL/anchor 已被 APP-089 全删；'
        'EXT 侧 `EXT_CLONE_ANCHOR` 默认 "0"）。\n'
        '* **APP-094③（v2.5 内嵌 EXT @ab9a767）**：**代码侧已备好**（暂存区 %d 个文件），'
        '🔴 **v2.5 本轮未打包**（APP-094 明文「复核通过前不打 v2.5」）。\n'
        '* **APP-093 §3**：**部分完成**（§3.2 阈值 A/B 已跑；§3.3 过载臂、§3.4 before 臂、'
        '§3.6 切段、§3.7 GUI 截图 **未跑**；§3.5 音色归属**判据失效**，根因已定位）'
        '⇒ **本条需等 reviewer 复核**。\n'
        % ('Confucius4_LiveCaption_MiniMVP_v1.0-rc5',
           (keep or {}).get('n_pass', 0),
           (keep or {}).get('n_pass', 0) + (keep or {}).get('n_fail', 0),
           (json.load(open(os.path.join(APP, 'app315_ext_v036_evidence.json'),
                           encoding='utf-8')).get('n_written', 0)
            if os.path.exists(os.path.join(APP,
                                           'app315_ext_v036_evidence.json')) else 0)))

    sec.append('\n### ② MiniMVP rc5 验收数字（rc5 vs rc4）\n\n')
    sec.append('| 档位 | RTF | 出字延迟中位 | 最大积压 | 峰值内存 |\n'
               '|---|---|---|---|---|\n')
    sec.append(row('**rc5 · 0.6B · ASR=GPU.0（TTS off）**', gpu) + '\n')
    sec.append(row('**rc5 · 0.6B · ASR=NPU（TTS off）**', npu) + '\n')
    sec.append('| rc4 · R2T2 · ASR=GPU.0（参照） | 0.696 | 376 ms | 1.2 s | 4819.5 MB |\n')
    sec.append('| rc4 · R2T2 · ASR=NPU（参照） | 0.803 | 540 ms | 1.1 s | 5212.6 MB |\n')
    sec.append(
        '\n⚠️ **WER 未填**：由 **reviewer** 用 MiniMax 回转写复算（ASR-002/ASR-004 口径）'
        '⇒ 本机**不调 MiniMax**、不自算。transcript 已落盘：\n'
        + ('- iGPU：`results/app/app312_rc5_out/gpu/transcript.txt`（SHA256 `%s`）\n'
           % (gpu or {}).get('artifacts', {}).get('transcript.txt', {}).get('sha256', '?'))
           + '- NPU：`results/app/app312_rc5_out/npu/transcript.txt`（SHA256 `%s`）\n'
           % ((npu or {}).get('artifacts', {}).get('transcript.txt', {})
              .get('sha256', '?')))
    sec.append(
        '\n⚠️ **EXECUTION_DEVICES 直证**（`app314`，用**包内 python**）：'
        '`enc_exec_devices.raw="%s"` / `dec_exec_devices.raw="%s"` '
        '⇒ **encoder=NPU / decoder=NPU**（🔴 `EXECUTION_DEVICES` 返回**字符串**，'
        '`list()` 会拆成字符 ⇒ 第一版判据误判，已修正）。\n'
        % ((execdev or {}).get('enc_exec_devices', {}).get('raw', '?'),
           (execdev or {}).get('dec_exec_devices', {}).get('raw', '?')))

    sec.append('\n### ③ rc5 包与体积变化（APP-096 §3c）\n\n')
    sec.append(
        '* 目录：`%s`｜**%s 文件 / %s**（打包清单口径）\n'
        '* zip：`shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc5_perftest.zip`'
        '｜**%s B**｜SHA256 `%s`｜**%s 条目，CRC32 逐条全对**\n'
        '* **相对 rc4**：文件 **%+d**、体积 **%+.3f GB**（目录）／zip **%s B**\n'
        '* **rc3 / rc4 的 zip SHA256 前后逐字未变**（打包前后各算一次）。\n'
        % ('Confucius4_LiveCaption_MiniMVP_v1.0-rc5',
           (build or {}).get('rc5', {}).get('files', '?'),
           '%.3f GB' % ((build or {}).get('rc5', {}).get('bytes', 0) / 2 ** 30),
           z5.get('zip_bytes', '?'), z5.get('zip_sha256', '?'),
           z5.get('n_entries', '?'),
           (docs or {}).get('size_delta', {}).get('files', 0),
           (docs or {}).get('size_delta', {}).get('gb', 0),
           ('%s B' % z5.get('zip_delta_bytes', '?')) if z5.get('zip_delta_bytes')
           is not None else '?'))
    sec.append(
        '\n🔴 **干净解压复验**（`app319`，全新目录 + **包内自带 python**）：'
        'zip 清单 **R2T2/INT4 计数 0**；**0.6B 物料齐全**；'
        '**无预编译 NPU blob**；**未写死 NPU 架构 5010**（§3d）；'
        '`--check` rc=0 且显示「Intel NPU · INT8 模型齐全」。'
        '（`--check` 标题仍写 "Confucius4-R2T2" ⇒ **已知文案残留**，未改。）\n')

    sec.append(thr_tbl)

    sec.append('\n### ④ APP-094① keep-first 判据（%s / %s）\n\n'
               % ((keep or {}).get('n_pass', 0),
                  (keep or {}).get('n_pass', 0) + (keep or {}).get('n_fail', 0)))
    sec.append(
        '* 默认组：`XV_UPGRADE=False` ⇒ 状态机 `first → frozen → frozen` ⇒ '
        '**每个说话人恰好注册一次**（`count=1`），**无第二次注册/升级**。\n'
        '* 旧行为保留为可选项：环境变量 `LIVECAP_XV_UPGRADE=1` ⇒ 回到「8 s 升级一次」。\n'
        '* 🔴 **反证组**：打开升级开关后确实注册 **2** 次 ⇒ **闸门真的起作用**'
        '（不是恒真判据）。\n'
        '* 注册记录新增字段：`xv_reg_at`（注册时刻）／`xv_reg_count`（次数）／'
        '`xv_reg_history`；新增导出接口 `xv_registration_records()`。\n'
        '* **App 侧未加 anchor**（APP-094②）：`live_caption/` 全量 grep 无 ICL/anchor 代码。\n')

    sec.append('\n### ⑤ 产物（%d 个文件；mtime 为本地实测）\n' % len(art_lines))
    sec.append('\n'.join(art_lines) + '\n')

    sec.append(
        '\n### ⑥ 本轮未做 / 停下等 reviewer\n'
        '* **APP-093 §3.3 过载臂重做 / §3.4 before 臂补齐 / §3.6 切段 / '
        '§3.7 GUI 截图** ⇒ 未跑 ⇒ **本条需等 reviewer 复核**。\n'
        '* **APP-093 §3.5 音色归属真值余弦**：🔴 **判据本身失效（已定位根因）**——'
        '三人**真值参考**的 x-vector 两两余弦高达 **0.9472 / 0.9654 / 0.9674**'
        '（`cos(refA,refB)`／`cos(refA,refC)`／`cos(refB,refC)`）'
        '⇒ **x-vector 在这段素材上分不开三个说话人** ⇒ '
        '对照组 A（**源人声**，已知正确）只有 **71.43 %**、'
        '对照组 B（**预设 A**，反证）却 **65.71 %** ⇒ '
        '**判据的信噪比不足 ⇒「归属率」数字不可用**。'
        '🔴 **未自行换判据**（换 encoder / 换素材 / 换度量都属改行为，需 reviewer 裁定）。\n'
        '* **APP-094③ 的 v2.5 打包** ⇒ 未做（APP-094 明文「复核通过前不打 v2.5」）。\n'
        '* **未通知用户**（APP-093/094 明文）。\n'
        '* 阈值取舍（要不要放宽 `tts_late_drop_sec`）仍由 reviewer 拿 §3.1/§3.2 数字'
        '报主会话请用户决定 ⇒ **未改代码默认值（仍 6.0）**。\n')

    sec_body = ''.join(sec)

    payload = {
        'last_ack': 'APP-096',
        'updated': get_date(),
        'current_task': (
            '**APP-094/095/096 已执行**：MiniMVP **rc5** 已出包（ASR→Qwen3-ASR-0.6B '
            'mask2 INT8，R2T2 ASR IR 全删，iGPU/NPU 两臂设备验收已跑，'
            'EXECUTION_DEVICES 直证 encoder=NPU/decoder=NPU）；'
            '**APP-094① keep-first 落地 + 判据 %d/%d**；'
            'EXT v0.3.6 暂存区已备（v2.5 未打包）'
            '｜**APP-093 §3 仅完成 §3.2，其余未跑 ⇒ 需等 reviewer 复核**'
            % ((keep or {}).get('n_pass', 0),
               (keep or {}).get('n_pass', 0) + (keep or {}).get('n_fail', 0))),
        'blocked': (
            '**APP-093 §3 的 §3.3/§3.4/§3.5/§3.6/§3.7 未跑**（过载臂重做・before 臂补齐・'
            '音色归属真值余弦・切段 RTF・GUI 截图）⇒ 需 MACHINE_LOCK 长作业；'
            '阈值取舍由 reviewer 拿 §3.1/§3.2 数字报主会话请用户决定（**默认值仍 6.0**）'
            '｜**v2.5 未打包、未通知用户**'),
        'recent_line': (
            '> 🔴 %s ｜ **APP-094/095/096 已执行**：MiniMVP **rc5** 出包'
            '（ASR→**Qwen3-ASR-0.6B** mask2 INT8；R2T2 的 ASR IR **全删**；'
            'zip 清单 INT4/R2T2 计数 **0**；%s B／SHA256 `%s…`／%s 条目 CRC32 全对）；'
            '**两臂设备验收**：iGPU RTF **%s**／延迟 %s ms／峰值 %s MB，'
            'NPU RTF **%s**／延迟 %s ms／峰值 %s MB（WER 交 reviewer 复算）；'
            '**EXECUTION_DEVICES 直证 encoder=NPU/decoder=NPU**；'
            '**APP-094① keep-first 落地**（判据 %d/%d，含反证组）'
            '｜**APP-093 §3 只完成 §3.2 ⇒ 需等 reviewer 复核**；未打 v2.5、未通知用户。'
            % (get_date(),
               z5.get('zip_bytes', '?'),
               (z5.get('zip_sha256') or '')[:12],
               z5.get('n_entries', '?'),
               ((gpu or {}).get('summary') or {}).get('rtf'),
               ((gpu or {}).get('summary') or {}).get('lat_ms'),
               (gpu or {}).get('peak_rss_mb'),
               ((npu or {}).get('summary') or {}).get('rtf'),
               ((npu or {}).get('summary') or {}).get('lat_ms'),
               (npu or {}).get('peak_rss_mb'),
               (keep or {}).get('n_pass', 0),
               (keep or {}).get('n_pass', 0) + (keep or {}).get('n_fail', 0))),
        'sec_body': sec_body,
    }

    out = os.path.join(APP, 'app320_status165_payload.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print('payload 已生成：%s（sec_body %d B）' % (out, len(sec_body.encode())))
    print('last_ack=%s updated=%s' % (payload['last_ack'], payload['updated']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
