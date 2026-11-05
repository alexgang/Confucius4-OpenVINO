#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§137 STATUS 定点写入（APP-052 ④ / bytes 级纪律）。

只动三处：① 头部「更新时间」 ② 「最近更新」插入一行 ③ 文件末尾追加 §137 章节。
旧正文逐字未变（写后做反向还原校验）；先写临时文件再原子替换；限额 ≤40 000 B / ≤300 行。
"""
import os
import re

P = r'C:/Users/Trekker-PTL/confucius4-openvino/status/app/STATUS_APP.md'
ARCHIVE = 'status/archive/STATUS_APP_sec137_20261105.md'
STAMP = '2026-11-05 13:37'          # Get-Date 实测（PowerShell）

SEC137 = '''
### §137 ✅ **无新纠偏（70 条 = last_ack APP-070）⇒ 按 APP-046 从 §136 断点续做** ｜ **APP-069⑥ 已完成｜①③④ 需等 reviewer 复核**（2026-11-05 13:37）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec137_20261105.md`（逐字保留，含 **14 个产物**的字节数／mtime／SHA256 清单）。
> 🔴 开工/收尾 `CORRECTIONS_APP.md`：**SHA `3c06baa98d3f612a…`／206 686 B／mtime 09:35:14／70 条**（APP-001..APP-070）⇒ **无编号 > last_ack 的新条目**，收尾与开工**逐字相同**（reviewer 未追加；本轮只读、未改、未提交）。**TAKEOVER 第 4 次**（上租约 `0c4889a6` 心跳停 11:11、`alive=False`）⇒ 从断点续做，**未重做** rc3／3(a)／`--check` 10/10。

| # | 事项 | 结论 | 证据（文件 → 原始字段） |
|---|---|---|---|
| ① | **APP-069⑥ MT INT4 vs INT8** | **本条已完成**：GPU.0／同一 `translate()`／46 段 ⇒ `exact_same_pct=4.35`（2/46）、`chrf_mean=74.029`、`chrf_median=76.697`、`n_different=44`（20 条差异样例落盘）、`wall_int4_s=19.85`／`wall_int8_s=28.91` | `app273_mt_int4_vs_int8_evidence.json`（9 482 B／SHA `29eb9d07731ec9c3…`）＋ `.tsv`（14 513 B／47 行）＋ `app273_mt_compare_run.log` |
| ② | **⑥ 夹具缺陷反证** | 首跑 `APP273_EXIT=2`（**0 段**）：原按 `lang='en'` 读 `minimvp.tts.jsonl`，而 76 行全是中文译文（`lang='zh'`）⇒ 真实英文定稿 = `app253_minimvp_out/minimvp.txt` **46 行**（`summary.segs=46`）；定点修正（唯一命中＋`ast.parse`＋写后逐字节复核） | `app274_app069_loader_fix_evidence.json` **4 PASS / 0 FAIL**（F3 反证：旧口径 0 段）＋ `_app274_fix_app273_loader.py` |
| ③ | 🔴 **口径差异** | reviewer 写 76 段，本机英文定稿仅 **46**（76 = TTS 侧中文译文句数）⇒ 按 46 跑、**未切句凑 76／未改参照**；`chrf_impl` = `SequenceMatcher.ratio()*100`（**非 sacrebleu chrF**）⇒ **需等 reviewer 复核** | `app273…evidence.json` → `source.scope_note`／`source.reviewer_expected_n_segments=76`／`chrf_impl` |
| ④ | **APP-069② GUI 臂** | **需等 reviewer 复核**：`--check` **10/10 零崩溃**（§136）；GUI 有效启动 **0/10**，2 次验证均 `loaded=false`／`rc=1`／`wall≈90.5 s`／日志 1 行 ⇒ **harness 超时被 terminate，非产品崩溃**（`crashed=false`、rc≠3221226505）；已补音频源（§135 `app259` L261）＋ `PYTHONUNBUFFERED`，本会话仍取不到「模型加载完成」 | `app276_app069_gui_harness_fix_evidence.json` **4/0**；`app272_crash_out/app272_crash_stats_evidence.json` → `n_runs=12`／`n_crash_0xC0000409=0`／`crash_rate_pct=0.0`／`verdict=INCOMPLETE`／`by_phase.gui.n=2` |
| ⑤ | **设备纪律** | 3 次设备作业均先探安静窗口（20 s，`QUIET True`）＋持 `MACHINE_LOCK`；**回收 2 个孤儿锁**（asr PID 46528／app PID 47088，均 `OpenProcess err=87` 确证死）⇒ 项目 fail-closed 脚本 `--reclaim` | `app273_mt_compare_run.log`／`app272_gui_phase_run*.log`／`app275_gui_probe.log` |

🔴 **仍待办（§136 未清项，不越界）**：⛔ **APP-070① 删 IR**（**975.9 MB vs reviewer 估 567 MB 待裁定**；顺序 清单→删→e2e ⇒ **一个文件都没删**）｜⛔ **APP-070② A+C 设备指标**／**APP-069④ (i)–(iv)**（冷启 ≈ 20 min）｜⛔ **APP-069⑦ rc3 zip**（依赖 ② 完成＋用户通知）｜⛔ **APP-069① reviewer 回转写 MER ≤ 8 %**（不自行调 MiniMax）｜⛔ **v2.3 继续暂缓**。
🔴 **未通知用户／未改桌面快捷方式／未动 v2.1、v2.2、rc1、rc2 一字节**（rc3 目录为 §136 构建，本轮未改）；本轮产物 **14 个**（全量元数据见归档件），**未打任何 zip**。
'''.strip('\n')

RECENT = ('- 2026-11-05 13:37 **§137 已写** ⇒ 无新纠偏（70 条 = APP-070）⇒ 从 §136 断点续做：'
          '**APP-069⑥ MT INT4/INT8 对比已完成**（46 段／4.35 % 相同／chrF 74.029；夹具 0 段缺陷已修＋反证 4/0）｜'
          '**APP-069② GUI 臂未完成**（有效启动 0/10，2 次 harness 超时、非产品崩溃）｜回收 2 个孤儿锁｜'
          '`CORRECTIONS_APP.md` 收尾 SHA 与开工逐字相同\n')

b = open(P, 'rb').read()
assert b'\r\n' not in b, 'STATUS 行尾应为 LF（本机此文件的实测状态）'

old_time = b'\xe6\x9b\xb4\xe6\x96\xb0\xe6\x97\xb6\xe9\x97\xb4: 2026-11-05 11:20\n'
# 用 unicode 构造，避免手写字节串
old_time = '更新时间: 2026-11-05 11:20\n'.encode('utf-8')
new_time = ('更新时间: %s\n' % STAMP).encode('utf-8')
anchor = '## 最近更新\n'.encode('utf-8')
assert b.count(old_time) == 1, ('更新时间锚点', b.count(old_time))
assert b.count(anchor) == 1, ('最近更新锚点', b.count(anchor))

b2 = b.replace(old_time, new_time, 1)
b2 = b2.replace(anchor, anchor + RECENT.encode('utf-8'), 1)
sec = SEC137.encode('utf-8')
b3 = b2.rstrip(b'\n') + b'\n\n' + sec + b'\n'

# ── 写后校验（旧正文逐字未变 + 章节不少 + 限额 + 行尾） ──
idx = b3.index('### §137'.encode('utf-8'))
restored = (b3[:idx].rstrip(b'\n') + b'\n')
restored = restored.replace(new_time, old_time, 1)
restored = restored.replace(anchor + RECENT.encode('utf-8'), anchor, 1)
assert restored == b, '反向还原 ≠ 原文件（旧正文被改）'
old_sections = re.findall(rb'^### \xc2\xa7\d+', b, re.M)
for t in old_sections:
    assert b3.count(t) == b.count(t), ('旧章节丢失', t)
assert b3.count('### §137'.encode('utf-8')) == 1
assert len(b3) <= 40000, ('超限 B', len(b3))
assert len(b3.splitlines()) <= 300, ('超限行', len(b3.splitlines()))
assert b'\r\n' not in b3
assert os.path.isfile(os.path.join(r'C:/Users/Trekker-PTL/confucius4-openvino', ARCHIVE))

tmp = P + '.tmp'
with open(tmp, 'wb') as f:
    f.write(b3)
os.replace(tmp, P)
assert open(P, 'rb').read() == b3
print('OK §137 写入：bytes %d -> %d / lines %d -> %d（旧正文逐字未变 / 章节不少 / LF 未破 / 限额内）'
      % (len(b), len(b3), len(b.splitlines()), len(b3.splitlines())))
