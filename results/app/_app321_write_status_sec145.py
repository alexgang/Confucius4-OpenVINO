"""定点写入 STATUS_APP.md 的 §145（APP-052④：写前先整块逐字归档旧正文，再只改头部 + 只追加章节）。

STATUS 写前 39 577 B / 200 行，距 40 000 B 仅 423 B ⇒ 必须压缩：
  * 块 A：§144 正文（最后一章，15 行）整块逐字归档，原位留 1 行速查；
  * 块 B：§143 产物清单表格（14 行）整块逐字归档，原位留 1 行速查；
  * 块 C：头部「已压缩」旧索引行（逐轮累积、约 1.9 KB）整块逐字归档，头部改短版指向归档件。
首版只归档 A+B 时自检 40 720 B 超限（STATUS 未落盘）⇒ 加块 C 后达标。
写前自检：反向还原==旧全文 / 章节数不减 / LF 未破 / 限额 / 归档件逐字命中 /
§145 引用字段与 _app320 JSON 原始字段一致；通过后才临时文件原子替换，写后磁盘逐字节复核。
"""
import os
import re
import json
import hashlib
import datetime

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
RES = os.path.join(ROOT, 'results', 'app')
OUT = os.path.join(RES, '_app321_write_status_sec145.json')
ARCHIVE_A_REL = 'status/archive/STATUS_APP_sec144_20261107.md'
ARCHIVE_B_REL = 'status/archive/STATUS_APP_sec143_artifacts_20261107.md'
ARCHIVE_C_REL = 'status/archive/STATUS_APP_compress_index_upto_20261107.md'
ARCHIVE_A = os.path.join(ROOT, ARCHIVE_A_REL)
ARCHIVE_B = os.path.join(ROOT, ARCHIVE_B_REL)
ARCHIVE_C = os.path.join(ROOT, ARCHIVE_C_REL)
STAMP = '2026-11-07 01:45:30'  # PowerShell Get-Date 实测值，非推算

ARTIFACTS = [
    'results/app/_app320_v23_build_readiness.py',
    'results/app/_app320_v23_build_readiness.json',
    ARCHIVE_A_REL,
    ARCHIVE_B_REL,
    ARCHIVE_C_REL,
]

evidence = json.load(open(os.path.join(RES, '_app320_v23_build_readiness.json'), encoding='utf-8'))
F = evidence['facts']
PC = F['packaging_chain']


def meta(rel):
    p = os.path.join(ROOT, rel)
    b = open(p, 'rb').read()
    st = os.stat(p)
    return {'path': rel,
            'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%dT%H:%M:%S'),
            'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}


old_bytes = open(STATUS, 'rb').read()
old_text = old_bytes.decode('utf-8')
old_lines = old_text.split('\n')


def one(prefix):
    idx = [j for j, l in enumerate(old_lines) if l.startswith(prefix)]
    assert len(idx) == 1, prefix + ' 行必须唯一命中'
    return idx[0]


idx_time, idx_task, idx_comp = one('更新时间:'), one('当前任务:'), one('已压缩:')
old_time_line, old_task_line, old_comp_line = (old_lines[j] for j in (idx_time, idx_task, idx_comp))
new_time_line = '更新时间: ' + STAMP
new_task_line = ('当前任务: **§145 无新纠偏（last_ack=APP-080）｜APP-080 打包链路就绪度静态盘点 18/0 ＋ 反证 7/7；'
                 '打包链路 NOT_WIRED 列入 ⑤ 待办，APP-075/079/080 仍停 reviewer 复核，v2.3 未打包**')
new_comp_line = ('已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；'
                 '限额 ≤40000 B / ≤300 行（APP-052④）｜**§145 压缩**：§144 正文＋§143 产物表 ⇒ '
                 '`' + ARCHIVE_A_REL + '` ／ `' + ARCHIVE_B_REL + '`')

# ---- 1. 定位三块待归档原文（均在原始 old_text 上，避免索引漂移） ----
i144 = [j for j, l in enumerate(old_lines) if l.startswith('## §144 ')]
i143 = [j for j, l in enumerate(old_lines) if l.startswith('## §143 ')]
assert len(i144) == 1 and len(i143) == 1, '§143/§144 标题必须各自唯一命中'
block_a = '\n'.join(old_lines[i144[0]:])  # 到文件末尾；split 的末尾空串已自带行尾 \n
assert block_a.endswith('\n'), '§144 块必须以原文件行尾结束'
t = next(j for j in range(i143[0], len(old_lines))
         if old_lines[j].startswith('| 文件 | mtime | 字节数 | SHA256 |'))
e = t
while e < len(old_lines) and old_lines[e].startswith('|'):
    e += 1
block_b = '\n'.join(old_lines[t:e]) + '\n'
block_c = old_comp_line + '\n'  # 头部旧「已压缩」行（定点改前的原文）
for name, blk in (('A', block_a), ('B', block_b), ('C', block_c)):
    assert old_text.count(blk) == 1, '块 %s 必须唯一命中' % name
sha_a = hashlib.sha256(block_a.encode('utf-8')).hexdigest()
sha_b = hashlib.sha256(block_b.encode('utf-8')).hexdigest()
sha_c = hashlib.sha256(block_c.encode('utf-8')).hexdigest()

SPEED_A = ('> 🔴 §144 正文（15 行）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec144_20261107.md`'
           '（块 SHA256 `' + sha_a + '`）；速查：`_app318` 对 §143 产物表 12/12 自证 **23/0 ＋ 反证 7/7**，'
           'APP-075/079/080 停在 reviewer 复核节点，v2.3 未打包。')
SPEED_B = ('> 🔴 §143 产物清单（14 行表格）已**整块逐字归档** ⇒ '
           '`status/archive/STATUS_APP_sec143_artifacts_20261107.md`（块 SHA256 `' + sha_b + '`）；'
           '12 个文件的 mtime／字节／SHA256 见归档件，§144 `_app318` 已逐项自证。')


def write_archive(path, title, block, bsha):
    txt = ('# ' + title + '（§145 写入前整块逐字搬迁，' + STAMP + '）\n\n'
           '> 🔴 以下原文逐字保留，一字未删、行尾未改；原文件原位只留 1 行速查或短版头部。\n'
           '> 块 SHA256：`' + bsha + '`\n\n```text\n' + block + '```\n')
    with open(path, 'wb') as f:
        f.write(txt.encode('utf-8'))


write_archive(ARCHIVE_A, 'STATUS_APP §144 正文归档', block_a, sha_a)
write_archive(ARCHIVE_B, 'STATUS_APP §143 产物清单表格归档', block_b, sha_b)
write_archive(ARCHIVE_C, 'STATUS_APP 头部「已压缩」旧索引行归档', block_c, sha_c)

# ---- 2. §145 正文（引用 _app320 原始字段，控制在限额内） ----
arts = [meta(x) for x in ARTIFACTS]
table = ['| 文件 | mtime | 字节数 | SHA256 |', '|---|---|---|---|']
for a in arts:
    table.append('| `%s` | %s | %d | `%s` |' % (a['path'], a['mtime'], a['bytes'], a['sha256']))

section_lines = [
    '',
    '## §145 无新纠偏（last_ack=APP-080）｜APP-080 打包链路就绪度静态盘点 18/0 ＋ 反证 7/7（' + STAMP + '）',
    '',
    '- **步骤 1–2**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，只读／未改／未提交）开工＝收尾 '
    'SHA `b3ae9ea9…f392b937d5`／224 562 B／mtime 2026-11-06 21:40:34／**80 条**（APP-001..080 无缺号无重复）'
    '⇒ `facts.corrections` 同值；`last_ack: APP-080` 对齐最大编号 ⇒ **无编号大于 last_ack 的新条目，步骤 3 无条可执行**。',
    '- **APP-046② 不空转**：`results/app/_app320_v23_build_readiness.json` ⇒ `verdict=PASS`／`n_pass=18`／'
    '`n_fail=0`／`n_unknown=0`／`counterproof_identified=7/7`（7 条反证全被识破，含模拟追加 '
    'APP-081・插消费引用・改 SHA・删 include 项）。纯 CPU 静态：'
    '`facts.machine_lock_present=false`／未推理／未调 MiniMax／未打包／未改客户安装目录与旧 zip／未改 .lnk／未改 `live_dub_ext`。',
    '- 🔴 **本轮新结论（APP-080 ⑤ 待办，需 reviewer 复核）**：`facts.packaging_chain` ⇒ '
    '`pack_v13_bytes=72531`／`pack_v13_sha256=2e7a232e…`／`pack_v13_hits=0`／'
    '`build_scripts_scanned=22`／`build_scripts_nonzero_hits={}`／`total_hits=0`／`wired=false`／'
    '`verdict=NOT_WIRED` ⇒ **§143 警示的「包内必须同时带 `PKG_INCLUDE_FILES=[app/v23_preset_only.py, '
    'app/assert_pkg_clean.py]`」尚未被 `pack_v13.py` 或任何建包脚本消费**。两份 dev 资产与 §143 产物表逐字一致：'
    '`facts.app080_assets.v23_preset_only.sha256=362825e6…`／`bytes=17260`；'
    '`assert_pkg_clean.sha256=ba769069…`／`bytes=3458`；`pkg_include_files` 两路径在开发树均有源、`ast.parse` 通过；'
    '`selftest`＝`PASS/36/0/0/8-8`、`docfix.verdict=PASS`、`diff_bytes=8021`。'
    '⇒ **不是代码缺陷，是接入待办**：v2.3 打新版本时须把构建期补丁应用到包内 3 份源文件并复制 2 个随包文件，'
    '否则 `from v23_preset_only import …` 会 ImportError。',
    '- 🔴 **判据缺陷已自纠（非产品缺陷）**：`_app320` 首跑 `FAIL/2` —— glob `*build*.py` 把**本自证脚本自身**'
    '算进被测集合（29 次自引用）⇒ 假 FAIL；按「FAIL 先怀疑判据」排除自身'
    '（`excluded_self=_app320_v23_build_readiness.py`）后复跑 **18/0、反证 7/7**。',
    '- **git / 限额只读核查**：`facts.git` ⇒ `head=c6ae632`／`ahead=0`／`branch=main`／`head_files` 5 个全在 '
    '`results/app/`・`status/app/`・`status/archive/` ⇒ 无半交付、上轮提交不含 `CORRECTIONS`、未吞其它模块；'
    '`facts.status_before` ⇒ 写前 **39 577 B／200 行**／SHA `ec9e5673…`（限额仅余 423 B）。',
    '- ⛔ **停止点**：APP-075「需 Opus 复核」・APP-079「需 reviewer 复核」・APP-080 ⑤⑥'
    '「reviewer 复核通过后才通知用户／v2.3 发布前不再为克隆占用设备」⇒ 本轮未自行推进 ⑤⑥、**v2.3 不打包**；'
    '新待办「打包链路接入」并入 ⑤ 等复核。3 个旧包 zip 本轮**未重复全量实算**（§142 已实算留证，'
    '`facts.not_rechecked` 如实说明）⇒ 不写新的「一字节未动」结论。',
    '- **写入纪律（APP-052④）**：写 §145 前把 §144 正文（15 行／' + str(len(block_a.encode('utf-8'))) +
    ' B／块 SHA `' + sha_a + '`）、§143 产物清单表（' + str(e - t) + ' 行／' +
    str(len(block_b.encode('utf-8'))) + ' B／块 SHA `' + sha_b + '`）与头部旧「已压缩」行（' +
    str(len(block_c.encode('utf-8'))) + ' B／块 SHA `' + sha_c + '`）**整块逐字归档**，'
    '原位留速查/短版；头部仅定点改 `更新时间`／`当前任务`／`已压缩` 3 行；末尾只追加本章节；'
    '自检「反向还原==旧全文」・章节不减・LF 未破・限额内＋原子替换＋写后逐字节复核 ⇒ '
    '`_app321_write_status_sec145.json`；首版 A+B **40 720 B** 超限被拦（STATUS 未落盘）。',
    '- **纠偏文件收尾复核**：开工＝收尾 SHA `b3ae9ea9…f392b937d5`／224 562 B／2026-11-06 21:40:34／'
    '**80 条**（最大 APP-080）⇒ reviewer 本轮未追加；全程只读／未改／未提交，可称零改动；'
    '若收尾后出现新条目按步骤 4 如实记录。',
    '- **产物清单（写 STATUS 时磁盘实测，共 ' + str(len(arts)) + ' 个文件）**：',
] + table + [
    '',
    '- **git**：逐文件 `git add`（禁 `-A`）⇒ main 普通 push、不 force；不提交 '
    '`CORRECTIONS_APP.md`（其 `M` 属 reviewer），不吞其它模块。',
]
SECTION = '\n'.join(section_lines) + '\n'

# ---- 3. 构造新文本（字符串级唯一命中替换） ----
mid = old_text.replace(block_b, SPEED_B + '\n', 1)
mid = mid.replace(block_a, SPEED_A + '\n', 1)
mid = mid.replace(old_time_line + '\n', new_time_line + '\n', 1)
mid = mid.replace(old_task_line + '\n', new_task_line + '\n', 1)
mid = mid.replace(old_comp_line + '\n', new_comp_line + '\n', 1)
new_text = mid + SECTION
new_bytes = new_text.encode('utf-8')

# 反向还原：去追加段 → 换回头部 3 行 → 换回两块原文 → 应逐字等于旧全文
restored = new_text[:-len(SECTION)]
restored = restored.replace(new_time_line + '\n', old_time_line + '\n', 1)
restored = restored.replace(new_task_line + '\n', old_task_line + '\n', 1)
restored = restored.replace(new_comp_line + '\n', old_comp_line + '\n', 1)
restored = restored.replace(SPEED_B + '\n', block_b, 1)
restored = restored.replace(SPEED_A + '\n', block_a, 1)

checks = []


def ck(cid, desc, ok, ev):
    checks.append({'id': cid, 'desc': desc, 'ok': bool(ok), 'evidence': ev})


ck('W01', '头部 3 行与三块归档原文均唯一命中并定点替换',
   (all(old_text.count(x) == 1 for x in (block_a, block_b, block_c))
    and mid.count(new_time_line) == 1 and mid.count(new_task_line) == 1
    and mid.count(new_comp_line) == 1 and mid.count(SPEED_A) == 1 and mid.count(SPEED_B) == 1),
   {'block_a_lines': len(old_lines[i144[0]:]), 'block_b_lines': e - t,
    'block_c_bytes': len(block_c.encode('utf-8'))})
ck('W02', '反向还原后与旧全文逐字相等（旧正文一字未删）', restored == old_text,
   {'old_bytes': len(old_bytes), 'restored_bytes': len(restored.encode('utf-8'))})
ck('W03', '三个归档件均含原文逐字命中',
   all(blk.encode('utf-8') in open(path, 'rb').read()
       for blk, path in ((block_a, ARCHIVE_A), (block_b, ARCHIVE_B), (block_c, ARCHIVE_C))),
   {'sha_a': sha_a, 'sha_b': sha_b, 'sha_c': sha_c})
ck('W04', '章节数不减', len(re.findall(r'(?m)^## ', new_text)) >= len(re.findall(r'(?m)^## ', old_text)),
   {'old': len(re.findall(r'(?m)^## ', old_text)), 'new': len(re.findall(r'(?m)^## ', new_text))})
ck('W05', 'LF 行尾未破', b'\r\n' not in new_bytes, {'crlf': new_bytes.count(b'\r\n')})
ck('W06', '限额 ≤40 000 B / ≤300 行',
   len(new_bytes) <= 40000 and new_text.count('\n') + 1 <= 300,
   {'bytes': len(new_bytes), 'lines': new_text.count('\n') + 1})
ck('W07', '§145 章节恰好追加一次', new_text.count('## §145 ') == 1,
   {'count': new_text.count('## §145 ')})
ck('W08', 'last_ack 保持 APP-080（无新编号）',
   re.search(r'(?m)^last_ack:\s*(\S+)', new_text).group(1) == 'APP-080',
   {'last_ack': re.search(r'(?m)^last_ack:\s*(\S+)', new_text).group(1)})
ck('W09', '§145 引用字段与 _app320 JSON 原始字段一致',
   (evidence['verdict'] == 'PASS' and evidence['n_pass'] == 18 and evidence['n_fail'] == 0
    and evidence['counterproof_identified'] == '7/7'
    and PC['total_hits'] == 0 and PC['verdict'] == 'NOT_WIRED'
    and PC['pack_v13_bytes'] == 72531 and PC['pack_v13_hits'] == 0
    and PC['build_scripts_scanned'] == 22
    and F['status_before']['bytes'] == 39577 and F['git']['head'] == 'c6ae632'),
   {'evidence_verdict': evidence['verdict'], 'total_hits': PC['total_hits'],
    'scanned': PC['build_scripts_scanned'], 'head': F['git']['head']})

n_fail = sum(1 for c in checks if not c['ok'])
verdict = 'PASS' if n_fail == 0 else 'FAIL'
report = {
    'tool': '_app321_write_status_sec145',
    'stamp_source': 'PowerShell Get-Date 实测',
    'stamp': STAMP,
    'first_attempt': {'planned_bytes': 40720, 'limit': 40000, 'status_written': False,
                      'note': '仅归档 A+B 时超限，写前自检拦下；追加归档块 C 后达标'},
    'before': {'bytes': len(old_bytes), 'lines': old_text.count('\n') + 1,
               'sections': len(re.findall(r'(?m)^## ', old_text)),
               'sha256': hashlib.sha256(old_bytes).hexdigest()},
    'after_planned': {'bytes': len(new_bytes), 'lines': new_text.count('\n') + 1,
                      'sections': len(re.findall(r'(?m)^## ', new_text))},
    'archives': [
        {'path': r, 'bytes': len(open(os.path.join(ROOT, r), 'rb').read()),
         'sha256': hashlib.sha256(open(os.path.join(ROOT, r), 'rb').read()).hexdigest(),
         'block_sha256': s, 'block_bytes': len(b.encode('utf-8'))}
        for r, s, b in ((ARCHIVE_A_REL, sha_a, block_a),
                        (ARCHIVE_B_REL, sha_b, block_b),
                        (ARCHIVE_C_REL, sha_c, block_c))
    ],
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
    print(json.dumps({'verdict': verdict, 'checks': checks,
                      'after_planned': report['after_planned']}, ensure_ascii=False, indent=2))
    raise SystemExit(2)

tmp = STATUS + '.tmp_app321'
with open(tmp, 'wb') as f:
    f.write(new_bytes)
os.replace(tmp, STATUS)
report['atomic_replace'] = True

disk = open(STATUS, 'rb').read()
report['status_written'] = (disk == new_bytes)
report['after_disk'] = {'bytes': len(disk), 'lines': disk.count(b'\n') + 1,
                        'sha256': hashlib.sha256(disk).hexdigest(), 'crlf': disk.count(b'\r\n')}
ck('W10', '写后磁盘逐字节与计划一致', report['status_written'], report['after_disk'])
report['n_pass'] = sum(1 for c in checks if c['ok'])
report['n_fail'] = sum(1 for c in checks if not c['ok'])
report['verdict'] = 'PASS' if report['n_fail'] == 0 else 'FAIL'
report['checks'] = checks
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps({'verdict': report['verdict'], 'n_pass': report['n_pass'], 'n_fail': report['n_fail'],
                  'before': report['before'], 'after': report['after_planned'],
                  'after_disk': report['after_disk'], 'archives': report['archives'],
                  'artifacts': arts}, ensure_ascii=False, indent=2))
