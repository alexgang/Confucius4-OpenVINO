# -*- coding: utf-8 -*-
"""§142 STATUS 定点写入：头部仅改 2 行 + 末尾仅追加 1 章节。

校验：唯一命中断言 / 旧正文逐字未变 / 章节数不减 / LF 未破 /
      写后 ≤40000 B 且 ≤300 行 / 先临时文件再原子替换 / 写后磁盘逐字复核。
"""
import os
import re
import json
import hashlib
import subprocess
import datetime

ROOT = 'C:/Users/Trekker-PTL/confucius4-openvino'
STATUS = ROOT + '/status/app/STATUS_APP.md'
OUT = ROOT + '/results/app/_app313_write_status_sec142.json'


def now_str():
    try:
        return subprocess.check_output(
            ['powershell', '-NoProfile', '-Command',
             'Get-Date -Format "yyyy-MM-dd HH:mm:ss"'],
            text=True, timeout=30).strip()
    except Exception:
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


NOW = now_str()

NEW_L5 = ('当前任务: **§142 无新纠偏（`CORRECTIONS_APP.md` 78 条 = `last_ack: APP-078`）** '
          '—— 按 APP-046 ② 不空转，做「版本纪律 + 证据落盘」静态自证'
          '（`_app312` **26 PASS / 0 FAIL**、反证 **4/4**、3 个旧包 zip SHA256 实算全等）；'
          '🔴 **APP-075 仍停在「需 Opus 复核」节点** ⇒ 按 APP-046 ④ 停止，不自行推进、v2.3 不打包；'
          '🔴 1 项历史证据 `app048_layout_1920x1080.png` 仓库内未落盘 ⇒ 记「无法判定」，需 reviewer 确认存放位置')

SECTION = r'''
## §142 无新纠偏（last_ack=APP-078）｜版本纪律与证据落盘静态自证 26/0（__NOW__）

- **开工结论：无编号大于 `last_ack` 的新纠偏**。`status/app/CORRECTIONS_APP.md` **78 条**（APP-001..APP-078；开工 SHA `bbc95c43…d82af` / **220 735 B** / 2026-11-06 13:31:54）＝ 头部 `last_ack: APP-078`；租约 `acquire app` **exit 0**（TOKEN `6bf382c0`，**无 TAKEOVER**）、`MACHINE_LOCK` 本轮 `NOT_PRESENT`（未占设备）。按 APP-046 ②「不空转」改做不占设备的静态证据自证；按 ④ 卡在「需 reviewer/用户决定」的项一律不自行推进。
- **自证脚本与结果**：`results/app/_app312_sec142_static_recheck.py`（**9 149 B** / 2026-11-06 20:52:55 / SHA256 `dcac15f21753b669b822a5dd6d416cbce4abe78ce12d3f6250fee2bb6633b8a2`）→ `results/app/_app312_sec142_static_recheck.json`（**16 762 B** / 2026-11-06 20:53:23 / SHA256 `2a70cdfb86d70df4ebec0662690e981e065d54cf94f000e30475bc16ca93884c`）⇒ **`verdict=PASS` / `n_pass=26` / `n_fail=0` / `counterproof_identified=4/4`**（原始字段）。四组：A 纠偏基线 + 编号 1..78 连续无重复 + `last_ack=78` 对齐（7 条）；B git 纪律（3 条）；C 证据落盘点验（4 条）；D 3 个旧包 zip 实算（12 条）。🔴 **反证 E1–E4 复用 A5/C2/D-1/A7 的同一判据函数**（`j_ids` / `j_missing` / `j_zip_sha` / `j_ack`），分别注入「全零 SHA / 删掉 APP-040 编号 / 空 unresolved 声明 / `last_ack=77`」⇒ **4/4 全被识破**（`identified=true`）⇒ 判据非恒真。
- **旧包「一字节未动」实算复核**（`_app312` → `zip_audit[].sha256_measured` vs `results/app/DELIVERY_2.x.json` → `sha256` / `bytes` / `mtime`）：**v2.0** `8198924f9aed30010c0fb80f472278f322f160c9b63cbe7861001dbda056eed9` / **11 233 134 015 B** / 2026-11-01 17:49:21；**v2.1** `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4` / **11 233 135 359 B** / 2026-11-01 20:38:13；**v2.2** `ea5c5c850f8836a7edab982611cdd59d0ba0e83f8d5ff880cc797b7c67c23b75` / **11 233 149 299 B** / 2026-11-02 01:54:03 ⇒ **3/3 的 SHA256、字节数、mtime 与基准全等**，`status_anchor_hit=true` 三包皆命中 STATUS 表锚点 ⇒ §141「旧包目录与 zip 一字节未动」首次拿到全量实算支撑。全程只读、未打包、未打 zip、未改任何安装目录。
- **证据文件落盘点验**（`_app312` → `evidence_files[]` 26 项，每项附 `bytes` / `mtime` / `sha256`）：STATUS「当前有效结论」表抽到 **27** 个证据文件 token，`n_found=26`；🔴 **1 个 unresolved**：`app048_layout_1920x1080.png` 在 `results/app/`、`results/`、`status/app/`、仓库根、`status/archive/` 多目录检索均未找到 ⇒ 按三态记为**「无法判定」，不判不合格、也不写成已落盘**；该引用属 APP-048 时代的历史截图，可能在客户包或 reviewer 本机，**需 reviewer 确认存放位置**（本轮不擅自改判、不删 STATUS 引用）。抽取正则已修正为保留可选前导下划线（否则 `_app310` / `_app311` 被误报缺失 ⇒ 属「FAIL 先怀疑判据」）。
- **半交付与纪律**（`_app312` → `git`）：`head=4306e10132d1c7ea473c299eceba7e1ce5ff416b`、`ahead_origin_main=0`、`staged_count=0` ⇒ **无半交付漏项**；`corrections_worktree='M status/app/CORRECTIONS_APP.md'` 是 **reviewer 的未提交改动** ⇒ 本轮只读、未改、未提交，提交时逐文件 `git add` **绝不带它**；工作区另有其它模块大量未提交改动（c0xx 系列等）⇒ **一个都没吞**。未在 CPU 跑推理/测速、未调 MiniMax、未创建 `MACHINE_LOCK`、未改桌面 .lnk、未动 `v23_clone/`。
- 🔴 **APP-075 本条需等 reviewer 复核**（纠偏原文 L1463「需 Opus 复核：待 r2 交付后（F0/x-vector 复核）」）：r2 已交付（**54 文件／20 175 499 B**）但 F0 闸门 **21 PASS / 19 FAIL / 6 NONE**、19 个 FAIL 全是 `male→female`；`app299` 仍是 `offline_stat_embed`（`verdict=FAIL`）⇒ **真 x-vector 余弦矩阵未产出、第 2 臂 preset 对照未跑** ⇒ 本轮不自行判定通过、不往下推进、**v2.3 不打包**。待复核清单（同 §141）：r2 F0 表／APP-074 结论改正（目录≠zip）／3 个旧包 `bridge_token.txt` 清单／本轮未打包。
- 🔴 **纠偏文件收尾复核（全程只读、未改、未提交）**：开工 SHA `bbc95c43…d82af`／220735 B／2026-11-06 13:31:54／**78 条** ⇒ 收尾 SHA `bbc95c4382f29fa3c8b4f1b49ff644339b025f78447a3bb263e6b680ad4d82af`／220735 B／2026-11-06 13:31:54／**78 条**（最大 APP-078）⇒ **一致（reviewer 本轮未追加，可称零改动）**；`last_ack` 保持 **APP-078**（无新编号可推进）。
- **写入纪律**（见 `_app313_write_status_sec142.json`）：头部仅定点改「更新时间」「当前任务」**两行**；末尾仅追加本章节；旧正文逐字未变、章节数不减、LF 行尾未破、写后 ≤ 40000 B / ≤ 300 行；先临时文件再 `os.replace` 原子替换，写后磁盘逐字复核。
'''.replace('__NOW__', NOW)


old_raw = open(STATUS, 'rb').read()
old_text = old_raw.decode('utf-8')
lines = old_text.split('\n')

idx_upd = [i for i, l in enumerate(lines) if l.startswith('更新时间: ')]
idx_task = [i for i, l in enumerate(lines) if l.startswith('当前任务: ')]
assert len(idx_upd) == 1 and idx_upd[0] == 3, '更新时间行不唯一或位置异常'
assert len(idx_task) == 1 and idx_task[0] == 4, '当前任务行不唯一或位置异常'
OLD_L4, OLD_L5 = lines[3], lines[4]
assert OLD_L4 == '更新时间: 2026-11-06 19:58:30', '头部更新时间与预期不符'
assert OLD_L5.startswith('当前任务: **§141'), '头部当前任务不是 §141'
assert old_text.count(OLD_L4) == 1 and old_text.count(OLD_L5) == 1, '唯一命中断言失败'

old_body_text = '\n'.join(lines[:3] + lines[5:])
old_body_sha = hashlib.sha256(old_body_text.encode('utf-8')).hexdigest()

NEW_L4 = '更新时间: ' + NOW
expected = old_text.replace(OLD_L4, NEW_L4, 1).replace(OLD_L5, NEW_L5, 1)
new_text = expected + SECTION

# ---- 写入前校验 ----
expected_lines = lines[:3] + [NEW_L4, NEW_L5] + lines[5:]
assert new_text == '\n'.join(expected_lines) + SECTION, '只发生两处替换 + 末尾追加'
new_lines = new_text.split('\n')
assert new_lines[:len(expected_lines)] == expected_lines, '旧正文逐行未变'
sec_old = len(re.findall(r'(?m)^## §\d+', old_text))
sec_new = len(re.findall(r'(?m)^## §\d+', new_text))
assert sec_new == sec_old + 1, '章节数异常'
nb = len(new_text.encode('utf-8'))
nl = new_text.count('\n')
assert b'\r\n' not in new_text.encode('utf-8'), 'CRLF 混入'
assert nb <= 40000 and nl <= 300, '超出 APP-052④ 限额'
assert new_text.endswith('\n'), '文件末尾 LF 丢失'

# ---- 原子写 ----
tmp = STATUS + '.tmp_sec142'
with open(tmp, 'wb') as f:
    f.write(new_text.encode('utf-8'))
os.replace(tmp, STATUS)

# ---- 写后磁盘复核 ----
disk_raw = open(STATUS, 'rb').read()
disk_text = disk_raw.decode('utf-8')
assert disk_text == new_text, '写后磁盘逐字复核失败'
assert disk_text.endswith(SECTION), '追加章节未落在末尾'
restored = (disk_text[:-len(SECTION)]
            .replace(NEW_L4, OLD_L4, 1)
            .replace(NEW_L5, OLD_L5, 1))
assert restored == old_text, '反向还原后与开工原文不一致'
assert not os.path.exists(tmp), '临时文件未清理'

out = {
    'written_at': NOW,
    'path': STATUS,
    'old_bytes': len(old_raw), 'new_bytes': len(disk_raw),
    'old_lines': old_text.count('\n'), 'new_lines': disk_raw.count(b'\n'),
    'head_lines_replaced': [OLD_L4, NEW_L4, OLD_L5[:40] + '…', NEW_L5[:40] + '…'],
    'old_body_sha256': old_body_sha,
    'old_body_verbatim_kept': restored == old_text,
    'sections_before': sec_old, 'sections_after': sec_new,
    'crlf_broken': b'\r\n' in disk_raw,
    'within_limits': nb <= 40000 and nl <= 300,
    'atomic_replace': True,
    'disk_verbatim_verified': True,
    'verdict': 'PASS',
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('OUT=' + OUT)
print('NOW=' + NOW)
print('VERDICT=PASS old=' + str(len(old_raw)) + 'B/' + str(old_text.count('\n')) + 'L'
      + ' new=' + str(len(disk_raw)) + 'B/' + str(disk_raw.count(b'\n')) + 'L'
      + ' sections=' + str(sec_old) + '->' + str(sec_new))
