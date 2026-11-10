# -*- coding: utf-8 -*-
"""APP-093 §4 / APP-052④：定点更新 STATUS_APP.md 头部 + 追加 §164 + 压缩归档。

纪律：
  * 只动头部字段 + 「最近更新」索引层；所有 `## §N` 旧章节正文逐字不动。
  * 追加 §164，旧结论错了在新章节写「撤回 §x」，不回改 §162。
  * 归档 6 条旧「最近更新」原文，逐字保留 + 块 SHA256。
  * 写前/写后双重校验：章节数、旧正文逐字、行尾、限额；临时文件 + 原子替换。
用法：python app397_app093_write_status.py "<Get-Date 实测 yyyy-MM-dd HH:mm:ss>"
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import sys

ROOT = 'C:/Users/Trekker-PTL/confucius4-openvino'
STATUS = ROOT + '/status/app/STATUS_APP.md'
ARCH_REL = 'status/archive/STATUS_APP_recent_updates_upto_20261110.md'
ARCH = ROOT + '/' + ARCH_REL
UPDATE_TS = sys.argv[1]

S162_ARCH_REL = 'status/archive/STATUS_APP_sec162_20261110.md'

ART = [
    ARCH_REL,
    S162_ARCH_REL,
    'results/app/app395_app093_static_diag.py',
    'results/app/app395_app093_lag_decomposition.json',
    'results/app/app396_app093_before_arm_scores.json',
    'results/app/app394_app092_overload_analysis.json',
    'results/app/app393_app089_scores_before_dialog3.json',
    'results/app/app382_app092_overload_analysis.py',
]


def meta(rel):
    p = ROOT + '/' + rel
    b = open(p, 'rb').read()
    return (os.path.basename(rel), len(b),
            datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S'),
            hashlib.sha256(b).hexdigest())


raw = open(STATUS, 'rb').read()
assert b'\r' not in raw, 'STATUS has CR bytes; abort (line-ending guard)'
t = raw.decode('utf-8')
L = t.split('\n')

# ---- 旧章节正文基线 ----
secs = list(re.finditer(r'^##\s+§(\d+)[^\n]*$', t, re.M))
old_secs = {}
for i, m in enumerate(secs):
    e = secs[i + 1].start() if i + 1 < len(secs) else len(t)
    old_secs[m.group(1)] = t[m.start():e]
assert len(old_secs) == 9, 'unexpected section count: %d' % len(old_secs)

# ---- 归档「最近更新」6 条旧原文（逐字） ----
assert L[9] == '## 最近更新', 'recent-updates anchor moved'
arch_lines = L[11:17]
assert len(arch_lines) == 6
assert arch_lines[0].startswith('> 🔴 2026-11-10 ｜ **MiniMVP rc4 已建**'), arch_lines[0][:60]
assert arch_lines[-1].startswith('> 🔴 2026-11-09 2026-11-09 09:24:27'), arch_lines[-1][:60]
arch_block = '\n'.join(arch_lines) + '\n'
arch_sha = hashlib.sha256(arch_block.encode('utf-8')).hexdigest()
arch_doc = (
    '# STATUS_APP「最近更新」旧条目归档（2026-11-10，APP-093 轮次）\n\n'
    '> 以下 6 行原文从 STATUS_APP.md 整块逐字移出，仅用于压缩（APP-052④）；'
    '块 SHA256 `%s`，共 %d B。未删任何字节。\n\n' % (arch_sha, len(arch_block.encode('utf-8')))
) + arch_block
with open(ARCH, 'wb') as f:
    f.write(arch_doc.encode('utf-8'))
assert arch_block in open(ARCH, encoding='utf-8').read(), 'archive does not contain verbatim block'

# ---- 头部定点替换 ----
idx_line = ('> 🔴 本节 6 条较旧「最近更新」原文（rc4 已建／APP-086②／§139-140 索引／'
            '2026-11-05 及更早索引／APP-085／APP-086-088 ack）已**整块逐字归档** ⇒ '
            '`%s`（块 SHA256 `%s`）；本节只留 rc4 zip 与 APP-093。' % (ARCH_REL, arch_sha))
new_update = (
    '> 🔴 2026-11-10 08:49 ｜ **APP-093 [HIGH] 已 ack**（reviewer 08:13 中途追加，92→93 条）：'
    '§162 复核「移植结构接受／验收不通过」⇒ **app394 `verdict=FAIL` 如实入册**、`app391…json` 幻影产物撤回、'
    '`tts_late_drop_sec` 默认保持 6.0；§3.1 静态诊断＋§3.4 before 补算已落盘（app395／app396）⇒ '
    '设备作业（阈值 A/B・过载臂重做・切段・GUI 截图）本轮未跑 ⇒ **本条需等 reviewer 复核**；未打 v2.5、未通知用户。'
)
assert L[2] == 'last_ack: APP-092'
assert L[3].startswith('更新时间: ')
L[2] = 'last_ack: APP-093'
L[3] = '更新时间: ' + UPDATE_TS
L[4] = ('当前任务: **APP-093 已 ack**：§162 复核结论如实更正（app394 verdict=FAIL／app391 幻影产物撤回／RTF 按素材分列）'
        '＋§3.1 静态滞后诊断＋§3.4 before 臂静态补算已落盘 ⇒ **设备作业未完成，本条需等 reviewer 复核**｜MiniMVP rc4 zip 已交付（§163）')
L[5] = ('阻塞 / 待用户决定: **APP-093 §3 的 2/3/5/6/7 未完成**（阈值 A/B 6 组・过载臂重做・音色真值余弦・切段 RTF・GUI 截图）'
        '⇒ 需 MACHINE_LOCK 长作业；正常跑跳过率取舍请 reviewer 拿 §3.1/3.2 数字报主会话由用户决定｜**未打 v2.5、未通知用户**')
L[11:17] = [idx_line]          # 先归档替换（此时 L[11:17] 仍是原第 12-17 行）
L.insert(10, new_update)       # 再插入到「## 最近更新」标题之后、rc4 zip 之前
assert L[10] == new_update and L[11].startswith('> 🔴 2026-11-10 07:41') and L[12] == idx_line

base = '\n'.join(L)

# ---- APP-052④ 压缩：§162 正文整块逐字归档，STATUS 留索引（§164 更正之） ----
S162_ARCH = ROOT + '/' + S162_ARCH_REL
m162 = re.search(r'^##\s+§162[^\n]*$', base, re.M)
m163 = re.search(r'^##\s+§163[^\n]*$', base, re.M)
assert m162 and m163 and m162.start() < m163.start()
s162_block = base[m162.start():m163.start()]
s162_sha = hashlib.sha256(s162_block.encode('utf-8')).hexdigest()
s162_nbytes = len(s162_block.encode('utf-8'))
s162_doc = (
    '# STATUS_APP §162 正文归档（2026-11-10，APP-093 轮次）\n\n'
    '> 原文整块逐字移出，仅用于压缩（APP-052④）；块 SHA256 `%s`，共 %d B。'
    '§164 已撤回本节 ③④⑤ 的错误结论；原文未删一字。\n\n' % (s162_sha, s162_nbytes)
) + s162_block
with open(S162_ARCH, 'wb') as f:
    f.write(s162_doc.encode('utf-8'))
assert s162_block in open(S162_ARCH, encoding='utf-8').read()
s162_index = (
    base[m162.start():m162.end()] + '\n\n'
    '> 🔴 **本节正文已整块逐字归档** ⇒ `%s`（%d B／块 SHA256 `%s`）；'
    '**§164 已撤回本节 ③④⑤ 的错误结论**（`app394.verdict=FAIL`／`app391…json` 幻影产物／「RTF≈0.90」笼统口径）。'
    '原文未删一字，按「只追加、不回改旧结论」纪律以索引替代。\n\n'
) % (S162_ARCH_REL, s162_nbytes, s162_sha)
base = base[:m162.start()] + s162_index + base[m163.start():]

# ---- 产物清单 ----
art_lines = []
for rel in ART:
    name, n, mt, sha = meta(rel)
    art_lines.append('- `%s`｜%d B｜%s｜SHA256 `%s`' % (name, n, mt, sha))
art_txt = '\n'.join(art_lines)

BODY = r'''
## §164 执行 APP-093（last_ack=APP-093）｜§162 复核：验收 **FAIL** 如实入册、静态诊断＋STATUS 更正已完成 ⇒ 设备作业未跑，**本条需等 reviewer 复核**（2026-11-10 08:49）

> 🔴 **reviewer 中途追加新纠偏**：开工 `CORRECTIONS_APP.md` SHA `3ab8d2b8…`／261 180 B／mtime 2026-11-09 16:49:57／**92 条**（max APP-092）⇒ 收尾 `0917747c…`／**267 771 B**／mtime **2026-11-10 08:13:20**／**93 条**（新增 **APP-093 [HIGH]**）。**不声称 SHA 零改动**；全程只读、未改、未提交。按 APP-093 §4 先写 `last_ack=APP-093` 并加最近更新一行。

### ① 撤回／更正 §162（只追加，不回改旧章节）
* **验收结论是 FAIL**：`app394_app092_overload_analysis.json`（`ts=2026-11-10 06:53:05`，晚于 §162 的 06:29）→ `verdict=FAIL`／`n_pass=5`／`n_fail=2`；`checks[0].ok=false`（(d) `normal.n_late_drop=3`／54 ＝ **5.56 %**）、`checks[5].ok=false`（(c) `overload.recovery_s_after_overload=null` 且 `n_voiced_rows=2` ⇒ 数据不足）。§162 ③/④ 未写 FAIL，按 APP-093 §2a 在此明写；今后判据失败必须入 STATUS。
* **撤回 §162 ④「本机 TTS 有效 RTF≈0.90」笼统口径**，按素材分列（`app395.main_after_normal_runs.*.fields.synth_rtf.p50`／`app396.scores[].synth_rtf_p50`）：after tight **0.9056**／after dave **0.9901**／before tight **0.8919**／before dave **0.9634**；dialog3 before/after 0.884/0.891（reviewer 原文）。
* **撤回 §162 ⑤ 幻影产物**：`results/app/app391_app089_before_and_overload.json` 磁盘不存在（`ls` No such file；只有 `app391_run.log` 35 364 B）⇒ 违反「没落盘不能写已交付」；真实证据为 `app393_app089_scores_before_dialog3.json`＋`app394_app092_overload_analysis.json`。按「只追加」纪律本轮未删改 §162 原文，是否允许直接删改请 reviewer 裁定。
* `app388_app089_scores_after_all.json`：`n_late_drop` dialog3 **3**／dialog3_tight **21（27 %）**／dialog3_dave **30（36 %）**，均不满足 APP-092 §3(d)「≈0」。
* **§162 正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec162_20261110.md`（5 052 B／块 SHA256 见归档件与产物清单）；STATUS 只留标题＋索引。原文未删一字，按「只追加、不回改旧结论」纪律处理。

### ② APP-093 §3.1 静态诊断（已完成，`app395`，反证 3/3）
* `defaults_untouched.tts_late_drop_sec=6.0`（实读 `app394.late_drop_threshold_s`）、`device_job=false`、未调 MiniMax。
* after tight 21/78＝26.92 %：`synth_rtf.p50=0.9056`／p90 0.9884、`speed.p50=1.1`、`worker_fifo_wait_s.p50=0.0`、`t_submit-t_recv` p50 **0.97 s**／p90 **4.0002 s**、`play_lag_s` p50 5.831／p95 8.4764、`in_dur_s` max 7.44 s、`out_dur_s/in_dur_s` p50 0.913。
* after dave 30/84＝35.71 %：`synth_rtf.p50=0.9901`／p90 1.1043、`n_speed_floor_conflict_last=53`、`worker_fifo_wait_s.p50=0.0`、`t_submit-t_recv` p50 0.298／p90 2.9692 s、`play_lag_s` p50 8.9725／p95 12.9602、`in_dur_s` max 10.64 s、`out_dur_s/in_dur_s` p50 0.9118。
* **结论**：跳过首要原因＝**TTS 合成吞吐不足**（RTF p50≈0.9–1.0、倍率被 1.10 floor 封顶，1.10–1.5× 曲线未生效）；**队列不是瓶颈**；MT 段为次级贡献（tight p90 4.0 s）。
* 🔴 **口径待裁定**：APP-093 §3.1「App 段长 12–20 s」与 `tts.jsonl.in_dur_s` 实测 max 7.44／10.64 s 不符，疑为「ASR 定稿/合并段」vs「TTS 输入段」口径差异；**未自行改判据**（`app395.main_after_normal_runs.*.reviewer_assumption_check`）。

### ③ APP-093 §3.4 before 臂补齐（静态补算，`app396`，未重跑设备）
* before tight：`run_rc=0`／78 行／字幕 35／`synth_rtf_p50=0.8919`／`play_lag_s_p50=16.5585`、p95 20.2544／`end_reason_counts` 全 eos／`n_hit_frame_cap=0`；before dave：`run_rc=0`／84 行／字幕 55／`synth_rtf_p50=0.9634`／`play_lag_s_p50=33.532`、p95 53.8113／`end_reason_counts` 全 eos／`n_hit_frame_cap=0`。
* 两目录 `run_manifest.json` 齐全且 `wav_sha256` 与 after 逐字一致（`45afb448…`／`b2da188a…`）⇒ 复用已落盘数据静态补算；`late_drop_field_present=false` ⇒ `n_late_drop=0` 是结构性非测量值；`spk_match_rate=null`（真值余弦列 §3.5 待办）。若 reviewer 要求重跑，下轮持锁执行。
* §2e：撞帧上限 **0**，依据 `tts.jsonl.frames` 全空（`n_frames_nonempty=0`）＋ `end_reason` 全 eos，字段来源已写进 json；`app385` 无 `lock`／`timing_valid` 字段，本补算 `lock_record=null` 并注明非计时跑。

### ④ 未完成 ⇒ **本条需等 reviewer 复核**
| APP-093 §3 项 | 状态 / 原因 |
|---|---|
| 2 阈值 A/B（6/10/15 × tight/dave，6 组） | 未跑：需 MACHINE_LOCK＋NPU 长作业；默认值保持 6.0，未自改 |
| 3 过载臂重做（0–60 s 1.0×／60–150 s 过载／150 s+ 1.0×） | 未跑：同上；`--speed 2.0` 全文件无「过载结束」⇒ (c) 结构性不可测 |
| 5 音色归属真值余弦（before/after × dialog3/tight） | 未做：需 x-vector 与 truth.json 三人参考比 |
| 6 切段（tight `n_split=0` 的相似度/margin 分布＋开关 ASR RTF） | 未做：RTF 需设备跑 |
| 7 GUI 三行字幕截图 png | 未做：需 `schtasks /it` GUI；`app372…/subtitle_layout.json` 现 `shot=null`、`gui.log` 0 B |
| 4 CER 回转写 | 不做：reviewer 用 MiniMax，本机不调 |
* 正常跑跳过率取舍由 reviewer 拿 §3.1/3.2 数字报主会话请用户决定；**本轮未打 v2.5、未通知用户、未打包、未改客户包、未调 MiniMax、未在 CPU 跑推理/测速、未持 MACHINE_LOCK**（纯静态，无设备作业）。

### ⑤ 产物（8 个文件；mtime 为本地实测）
@@ART@@
* 压缩复核（APP-052④）：追加后 **@@BYTES@@ B / @@LINES@@ 行 ≤40000 B / ≤300 行**；6 条旧「最近更新」原文整块逐字归档 ⇒ `@@ARCH@@`（块 SHA256 `@@ARCHSHA@@`），§162 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec162_20261110.md`；写前/写后断言：除 §162 外 8 个旧 `## §N` 章节正文逐字未变、§162 原文在归档件逐字命中、章节数 9→10、行尾无 CR；临时文件＋原子替换。
'''

BODY = (BODY.replace('@@ART@@', art_txt)
            .replace('@@ARCH@@', ARCH_REL)
            .replace('@@ARCHSHA@@', arch_sha))

# ---- 自指大小：占位符不动点迭代 ----
b_est, l_est = 0, 0
final = None
for _ in range(10):
    cand = base + BODY.replace('@@BYTES@@', str(b_est)).replace('@@LINES@@', str(l_est))
    nb, nl = len(cand.encode('utf-8')), len(cand.split('\n'))
    if (nb, nl) == (b_est, l_est):
        final = cand
        break
    b_est, l_est = nb, nl
assert final is not None, 'self-referential size did not converge'

# ---- 写前校验 ----
new_secs = {}
m2 = list(re.finditer(r'^##\s+§(\d+)[^\n]*$', final, re.M))
for i, m in enumerate(m2):
    e = m2[i + 1].start() if i + 1 < len(m2) else len(final)
    new_secs[m.group(1)] = final[m.start():e]
assert len(new_secs) == 10, 'section count != 10: %d' % len(new_secs)
# 追加新章节会改变「末章到文件尾」的块边界 ⇒ 用「旧正文逐字命中」作判据
# §162 正文按 APP-052④ 整块移入归档件 ⇒ 其原文在归档件里逐字命中
arch162_txt = open(S162_ARCH, encoding='utf-8').read()
for k, v in old_secs.items():
    if k == '162':
        assert v in arch162_txt, 'sec162 original not verbatim in archive'
    else:
        assert v in final, 'old section body not verbatim: §%s' % k
assert '164' in new_secs and 'last_ack: APP-093' in final
assert final.index('## §163') < final.index('## §164')
assert len(final.encode('utf-8')) <= 40000, 'over 40000 B: %d' % len(final.encode('utf-8'))
assert len(final.split('\n')) <= 300, 'over 300 lines: %d' % len(final.split('\n'))
assert b'\r' not in final.encode('utf-8')
assert arch_block in open(ARCH, encoding='utf-8').read()

# ---- 临时文件 + 原子替换 ----
tmp = STATUS + '.tmp_app397'
with open(tmp, 'wb') as f:
    f.write(final.encode('utf-8'))
os.replace(tmp, STATUS)

# ---- 写后复核 ----
chk = open(STATUS, 'rb').read()
assert b'\r' not in chk
ct = chk.decode('utf-8')
cs = list(re.finditer(r'^##\s+§(\d+)[^\n]*$', ct, re.M))
assert len(cs) == 10
for k, v in old_secs.items():
    if k == '162':
        assert v in arch162_txt, 'post-write sec162 archive check failed'
    else:
        assert v in ct, 'post-write verbatim check failed §%s' % k
print('OK STATUS bytes=%d lines=%d sections=%d' % (len(chk), len(ct.split('\n')), len(cs)))
print('OK archive=%s bytes=%d sha256=%s' % (ARCH_REL, os.path.getsize(ARCH), arch_sha))
print('OK self_reported bytes/lines =', b_est, l_est)
print('OK last_ack=APP-093 update_time=%s' % UPDATE_TS)
