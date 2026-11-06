"""定点写入 STATUS_APP.md 的 §144（APP-052④：先整块逐字归档旧条目，再只改头部 + 只追加章节）。
首版 40 813 B 超 40 000 B 限额被写前自检拦下（STATUS 未落盘）⇒ 本版把「最近更新」的
§139/§140 两条长条目整块逐字搬迁到 status/archive/，原位只留 1 行速查。
写前自检：旧正文逐字保留 / 章节不减 / LF 未破 / 限额 / 归档件逐字命中；通过后才临时文件原子替换，
写后从磁盘逐字节复核。
"""
import os
import re
import json
import hashlib
import datetime

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
RES = os.path.join(ROOT, 'results', 'app')
OUT = os.path.join(RES, '_app319_write_status_sec144.json')
ARCHIVE_REL = 'status/archive/STATUS_APP_recent_updates_upto_20261107.md'
ARCHIVE = os.path.join(ROOT, ARCHIVE_REL)
STAMP = '2026-11-07 00:29:43'  # PowerShell Get-Date 实测值，非推算

ARTIFACTS = [
    'results/app/_app318_sec143_evidence_recheck.py',
    'results/app/_app318_sec143_evidence_recheck.json',
    ARCHIVE_REL,
]


def meta(rel):
    p = os.path.join(ROOT, rel)
    b = open(p, 'rb').read()
    st = os.stat(p)
    return {
        'path': rel,
        'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%dT%H:%M:%S'),
        'bytes': len(b),
        'sha256': hashlib.sha256(b).hexdigest(),
    }


old_bytes = open(STATUS, 'rb').read()
old_text = old_bytes.decode('utf-8')
old_lines = old_text.split('\n')

# ---- 1. 定位「最近更新」段里要归档的 2 条原文 ----
i_recent = [i for i, l in enumerate(old_lines) if l.startswith('## 最近更新')]
assert len(i_recent) == 1, '## 最近更新 标题必须唯一'
i_recent = i_recent[0]
i_next = next((j for j in range(i_recent + 1, len(old_lines)) if old_lines[j].startswith('## ')), None)
assert i_next is not None
block_idx = [i for i in range(i_recent + 1, i_next) if old_lines[i].startswith('- 2026-')]
assert len(block_idx) == 2, '待归档条目必须恰好 2 行'
block_text = '\n'.join(old_lines[i] for i in block_idx) + '\n'
block_sha = hashlib.sha256(block_text.encode('utf-8')).hexdigest()

SPEEDLINE = ('> 🔴 §139 / §140 两条「最近更新」原文（2 行）已**整块逐字归档** ⇒ '
             '`status/archive/STATUS_APP_recent_updates_upto_20261107.md`（块 SHA256 `' + block_sha + '`）；'
             '速查：§139 APP-073/074 冒烟 7/0＋rev2 最终 SHA `90ae8b9d…`；'
             '§140 APP-076/077/078 39/0・26/0＋27/0・28/0＋14/0，APP-075 需等复核。')

archive_text = (
    '# STATUS_APP「最近更新」条目归档（§144 写入前整块逐字搬迁，' + STAMP + '）\n\n'
    '> 🔴 以下 2 行原文逐字保留，一字未删、行尾未改；原文件原位只留 1 行速查。\n'
    '> 来源：`status/app/STATUS_APP.md` 的 `## 最近更新`（§139 / §140 两条）。\n'
    '> 块 SHA256：`' + block_sha + '`\n\n'
    '```text\n' + block_text + '```\n')
archive_bytes = archive_text.encode('utf-8')
with open(ARCHIVE, 'wb') as f:
    f.write(archive_bytes)

# ---- 2. §144 正文 ----
arts = [meta(x) for x in ARTIFACTS]
table = ['| 文件 | mtime | 字节数 | SHA256 |', '|---|---|---|---|']
for a in arts:
    table.append('| `%s` | %s | %d | `%s` |' % (a['path'], a['mtime'], a['bytes'], a['sha256']))

section_lines = [
    '',
    '## §144 无新纠偏（last_ack=APP-080）｜§143 报数证据链静态自证 23/0 ＋ 反证 7/7（' + STAMP + '）',
    '',
    '- **步骤 1–2**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，只读／未改／未提交）开工＝收尾 SHA `b3ae9ea9…f392b937d5`／224 562 B／mtime 2026-11-06 21:40:34／**80 条**（1..80 无缺号）⇒ **逐字一致，本轮未追加**；`last_ack: APP-080` 对齐最大编号 ⇒ **无新条目，步骤 3 无条可执行**。',
    '- **APP-046② 不空转**：`results/app/_app318_sec143_evidence_recheck.json` ⇒ `verdict=PASS`／`n_pass=23`／`n_fail=0`／`n_unknown=0`／`counterproof_identified=7/7`；`checks[].ok` 覆盖 §143 产物表 **12/12** 文件 mtime／字节／SHA256（`artifacts[].reported_match`）、4 个结果 JSON 原始字段（`_app314` PASS/10/0/4-4・`_app315` PASS/36/0/0/8-8・`_app316` PASS・`_app317` PASS＋`corrections.identical=true`）、写前 STATUS 38 020 B／186 行／LF、git HEAD `cd2c435`／`origin/main..HEAD=0`／上轮提交不含纠偏文件；`counterproof[].detected` **7/7**（改 SHA・字节・n_pass・last_ack・模拟追加・超限・删产物行）⇒ 判据非恒真。纯 CPU 静态：未建 `MACHINE_LOCK`／未推理／未调 MiniMax。⚠️ 为写 §144 前快照，写后 `更新时间` 变化属预期。',
    '- ⛔ **停止点**：APP-075「需 Opus 复核」、APP-079「需 reviewer 复核」、APP-080 ⑤⑥「复核通过后才通知用户／v2.3 发布前不再为克隆占用设备」⇒ 本轮 **未打包／未打新版本目录与 zip／未改客户安装目录与旧 zip／未改 .lnk／未改 `live_dub_ext`**；**v2.3 不打包**。',
    '- **写前自检**：首版 **40 813 B** 超限（STATUS 未落盘）⇒ 按 APP-052④ 把「最近更新」§139/§140 两条原文整块逐字归档到 `status/archive/STATUS_APP_recent_updates_upto_20261107.md`（块 SHA `' + block_sha + '`），原位留 1 行速查。',
    '- **产物清单（写 STATUS 时磁盘实测，共 ' + str(len(arts)) + ' 个文件）**：',
] + table + [
    '',
    '- **写入**：头部定点改 `更新时间`／`当前任务`／`已压缩` 3 行＋原位速查＋末尾只追加本章节；自检「反向还原==旧全文」・章节不减・LF 未破・限额内＋临时文件原子替换＋写后逐字节复核 ⇒ `_app319_write_status_sec144.json`。git 逐文件 add、main 普通 push、不提交 `CORRECTIONS_APP.md`、不吞其它模块。',
]
SECTION = '\n'.join(section_lines) + '\n'

# ---- 3. 构造新文本 ----
def one(prefix):
    idx = [i for i, l in enumerate(old_lines) if l.startswith(prefix)]
    assert len(idx) == 1, prefix + ' 行必须唯一命中'
    return idx[0]


idx_time, idx_task, idx_comp = one('更新时间:'), one('当前任务:'), one('已压缩:')
old_time_line, old_task_line, old_comp_line = (old_lines[i] for i in (idx_time, idx_task, idx_comp))
new_time_line = '更新时间: ' + STAMP
new_task_line = '当前任务: **§144 无新纠偏（last_ack=APP-080）｜§143 证据链静态自证 23/0 ＋ 反证 7/7；APP-075/079/080 停在 reviewer 复核节点，v2.3 未打包**'
new_comp_line = old_comp_line + '｜**§144 压缩**：「最近更新」§139/§140 两条整块逐字归档 ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261107.md`'

lines = list(old_lines)
lines[idx_time] = new_time_line
lines[idx_task] = new_task_line
lines[idx_comp] = new_comp_line
lines[block_idx[0]:block_idx[-1] + 1] = [SPEEDLINE]
mid_text = '\n'.join(lines)
new_text = mid_text + SECTION
new_bytes = new_text.encode('utf-8')

# 反向还原：去掉追加段 → 换回 3 行头部 → 速查行换回 2 行原文 → 应逐字等于旧全文
restored = new_text[:-len(SECTION)]
restored = restored.replace(new_time_line, old_time_line, 1)
restored = restored.replace(new_task_line, old_task_line, 1)
restored = restored.replace(new_comp_line, old_comp_line, 1)
restored = restored.replace(SPEEDLINE + '\n', block_text, 1)

checks = []


def ck(cid, desc, ok, evidence):
    checks.append({'id': cid, 'desc': desc, 'ok': bool(ok), 'evidence': evidence})


ck('W01', '头部 3 行与归档块均唯一命中并定点替换',
   (mid_text.count(new_time_line) == 1 and mid_text.count(new_task_line) == 1
    and mid_text.count(new_comp_line) == 1 and mid_text.count(SPEEDLINE) == 1),
   {'old_time': old_time_line, 'block_lines': len(block_idx)})
ck('W02', '反向还原后与旧全文逐字相等（旧正文一字未删）', restored == old_text,
   {'old_bytes': len(old_bytes), 'restored_bytes': len(restored.encode('utf-8'))})
ck('W03', '归档件含旧条目原文逐字命中', block_text.encode('utf-8') in archive_bytes,
   {'block_sha256': block_sha, 'archive_bytes': len(archive_bytes)})
ck('W04', '章节数不减', len(re.findall(r'(?m)^## ', new_text)) >= len(re.findall(r'(?m)^## ', old_text)),
   {'old': len(re.findall(r'(?m)^## ', old_text)), 'new': len(re.findall(r'(?m)^## ', new_text))})
ck('W05', 'LF 行尾未破', b'\r\n' not in new_bytes, {'crlf': new_bytes.count(b'\r\n')})
ck('W06', '限额 ≤40 000 B / ≤300 行', len(new_bytes) <= 40000 and new_text.count('\n') + 1 <= 300,
   {'bytes': len(new_bytes), 'lines': new_text.count('\n') + 1})
ck('W07', '§144 章节恰好追加一次', new_text.count('## §144 ') == 1, {'count': new_text.count('## §144 ')})
ck('W08', 'last_ack 保持 APP-080（无新编号）',
   re.search(r'(?m)^last_ack:\s*(\S+)', new_text).group(1) == 'APP-080',
   {'last_ack': re.search(r'(?m)^last_ack:\s*(\S+)', new_text).group(1)})

n_fail = sum(1 for c in checks if not c['ok'])
verdict = 'PASS' if n_fail == 0 else 'FAIL'
report = {
    'tool': '_app319_write_status_sec144',
    'stamp_source': 'PowerShell Get-Date 实测',
    'stamp': STAMP,
    'first_attempt': {'planned_bytes': 40813, 'limit': 40000, 'status_written': False,
                      'note': '写前自检拦下，STATUS 未落盘'},
    'before': {'bytes': len(old_bytes), 'lines': old_text.count('\n') + 1,
               'sections': len(re.findall(r'(?m)^## ', old_text)),
               'sha256': hashlib.sha256(old_bytes).hexdigest()},
    'after_planned': {'bytes': len(new_bytes), 'lines': new_text.count('\n') + 1,
                      'sections': len(re.findall(r'(?m)^## ', new_text))},
    'archive': {'path': ARCHIVE_REL, 'bytes': len(archive_bytes),
                'sha256': hashlib.sha256(archive_bytes).hexdigest(), 'block_sha256': block_sha},
    'head_lines_changed': 3,
    'artifacts': arts,
    'checks': checks,
    'n_pass': len(checks) - n_fail,
    'n_fail': n_fail,
    'verdict': verdict,
    'status_written': False,
    'atomic_replace': False,
}

if verdict != 'PASS':
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({'verdict': verdict, 'checks': checks}, ensure_ascii=False, indent=2))
    raise SystemExit(2)

tmp = STATUS + '.tmp_app319'
with open(tmp, 'wb') as f:
    f.write(new_bytes)
os.replace(tmp, STATUS)
report['atomic_replace'] = True

disk = open(STATUS, 'rb').read()
report['status_written'] = (disk == new_bytes)
report['after_disk'] = {'bytes': len(disk), 'lines': disk.count(b'\n') + 1,
                        'sha256': hashlib.sha256(disk).hexdigest(), 'crlf': disk.count(b'\r\n')}
ck('W09', '写后磁盘逐字节与计划一致', report['status_written'], report['after_disk'])
report['n_pass'] = sum(1 for c in checks if c['ok'])
report['n_fail'] = sum(1 for c in checks if not c['ok'])
report['verdict'] = 'PASS' if report['n_fail'] == 0 else 'FAIL'
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps({'verdict': report['verdict'], 'n_pass': report['n_pass'], 'n_fail': report['n_fail'],
                  'before': report['before'], 'after': report['after_planned'],
                  'after_disk': report['after_disk'], 'archive': report['archive'],
                  'artifacts': arts}, ensure_ascii=False, indent=2))
