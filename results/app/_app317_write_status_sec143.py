r"""_app317 — 按 APP-052④ 压缩归档 §141/§142，头部定点改 3 行，末尾追加 §143。

纪律：只写 status/app/STATUS_APP.md；旧正文逐字保留（§141/§142 整块搬到
status/archive/）；临时文件 os.replace 原子替换 + 写后逐字节复核；
CORRECTIONS_APP.md 全程只读。用法：python _app317_write_status_sec143.py "YYYY-MM-DD HH:MM:SS"
（时间由 PowerShell Get-Date 实测传入，禁止推算）。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
ARCHIVE = os.path.join(ROOT, 'status', 'archive',
                       'STATUS_APP_sec141_142_20261106.md')
UNFIN_ARCHIVE = os.path.join(ROOT, 'status', 'archive',
                             'STATUS_APP_unfinished_corrections_upto_20261106.md')
BODY = os.path.join(HERE, '_app317_sec143_body.md')
REPORT = os.path.join(HERE, '_app317_write_status_sec143.json')

# 开工基线（本轮 23:11 实测，非推算）
OPEN = dict(sha256='b3ae9ea9fb72282bbf619dd26b73de688f8c771911bd0b56e0faf8f392b937d5',
            bytes=224562, mtime='2026-11-06T21:40:34',
            n_entries=80, max_id='APP-080')

ARTIFACTS = [
    'live_caption/v23_preset_only.py',
    'results/app/_app314_app079_static_triage.py',
    'results/app/_app314_app079_static_triage.json',
    'results/app/_app315_app080_preset_only_selftest.py',
    'results/app/_app315_app080_preset_only_selftest.json',
    'results/app/_app315_v23_preset_only.diff',
    'results/app/_app316_docstring_guard_fix.py',
    'results/app/_app316_docstring_guard_fix.json',
    'results/app/_app317_sec143_body.md',
    'results/app/_app317_write_status_sec143.py',
    'status/archive/STATUS_APP_sec141_142_20261106.md',
    'status/archive/STATUS_APP_unfinished_corrections_upto_20261106.md',
]

COMPACT2 = r'''## 未完成纠偏

> 🔴 本表（APP-043..APP-054 与 3 行关键指标）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_unfinished_corrections_upto_20261106.md`；正文一字未删。
> 🔴 **速查**：APP-045/047/048/049/050 已闭合；APP-043/051/052/053/054 均「已完成、待 reviewer 复核」；🔴 APP-048 仍缺「运行中」截图、APP-053 仍缺转写区 `[Sx]` 前缀截图、APP-043 仍需用户实听 3 段素材。
'''

COMPACT = r'''## §141 无新纠偏（last_ack=APP-078）｜§140 证据链自证 48/0 全数落盘（2026-11-06 19:58:30）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec141_142_20261106.md`（§141 全文，逐字保留）。
> 🔴 **速查**：`_app310` **48 PASS / 0 FAIL**（34 条「结果文件＋原始字段」断言／3 条反证全被识破／11 条 STATUS 锚点命中）；`ac61878` 已提交、`origin/main..HEAD=0`；APP-075 停在「需 Opus 复核」⇒ v2.3 不打包。

## §142 无新纠偏（last_ack=APP-078）｜版本纪律与证据落盘静态自证 26/0（2026-11-06 20:55:30）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec141_142_20261106.md`（§142 全文，逐字保留）。
> 🔴 **速查**：`_app312` **26/0**＋反证 **4/4**；3 个旧包 zip 全量 SHA256 与 `DELIVERY_2.x.json` 基准全等；🔴 1 项历史证据 `app048_layout_1920x1080.png` 仓库内未落盘 ⇒ 记「无法判定」，**需 reviewer 确认存放位置**。
'''

HEAD_LINES = {
    'last_ack:': 'last_ack: APP-080',
    '更新时间:': None,   # 由 Get-Date 实测值填
    '当前任务:': ('当前任务: **§143 APP-079 静态归因 + APP-080「v2.3 只交付预设音色」'
                 '构建期补丁与静态自证（_app314 10/0、_app315 36/0、反证 8/8）** —— '
                 '两条均停在「需 reviewer 复核」节点；v2.3 **未打包**、旧包一字节未动'),
}


def stat(path):
    b = open(path, 'rb').read()
    st = os.stat(path)
    return dict(path=path, bytes=len(b),
                mtime=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds'),
                sha256=hashlib.sha256(b).hexdigest())


def corr_state():
    b = open(CORR, 'rb').read()
    ids = re.findall(rb'(?m)^## (APP-\d+)', b)
    st = os.stat(CORR)
    return dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest(),
                mtime=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds'),
                n_entries=len(ids), max_id=(max(x.decode() for x in ids) if ids else None))


def main():
    now = sys.argv[1] if len(sys.argv) > 1 else None
    assert now and re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', now), \
        'need Get-Date measured timestamp as argv[1]'
    checks = []

    def chk(cond, name, detail=''):
        assert isinstance(cond, bool)
        checks.append(dict(name=name, ok=cond, detail=detail))
        assert cond, 'FAILED %s: %s' % (name, detail)

    raw = open(STATUS, 'rb').read()
    text = raw.decode('utf-8')
    chk(b'\r\n' not in raw, 'source_eol_lf', 'CRLF=0')
    old_size, old_lines = len(raw), text.count('\n') + 1

    # ── 头部：只定点改 3 行 ──────────────────────────────────────────
    lines = text.split('\n')
    head_changes = []
    for i, line in enumerate(lines[:12]):
        for prefix, new in HEAD_LINES.items():
            if line.startswith(prefix):
                new_line = ('更新时间: ' + now) if new is None else new
                head_changes.append(dict(line_no=i + 1, before=line[:60],
                                         after=new_line[:60]))
                lines[i] = new_line
                break
    chk(len(head_changes) == 3, 'head_exactly_3_lines',
        'changed=%s' % [c['line_no'] for c in head_changes])
    text2 = '\n'.join(lines)

    # ── 额外压缩：把「未完成纠偏」旧表整块逐字归档（腾出 §143 所需空间）──
    a = re.search(r'(?m)^## 未完成纠偏', text2).start()
    b = re.search(r'(?m)^## 最近章节', text2).start()
    unfin_block = text2[a:b]
    compact2 = COMPACT2.replace('\r\n', '\n')
    chk(compact2.startswith('## 未完成纠偏') and compact2.endswith('\n'),
        'compact2_shape')
    with open(UNFIN_ARCHIVE, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# 归档：STATUS_APP「未完成纠偏」表（2026-11-06，逐字保留）\n\n'
                + unfin_block)
    chk(unfin_block in open(UNFIN_ARCHIVE, 'rb').read().decode('utf-8'),
        'unfin_archive_verbatim',
        'bytes=%d' % len(unfin_block.encode('utf-8')))
    text2 = text2[:a] + compact2 + text2[b:]
    unfin_stat = stat(UNFIN_ARCHIVE)

    # ── §141/§142 正文整块逐字归档 ────────────────────────────────────
    m = re.search(r'(?m)^## §141 ', text2)
    chk(m is not None, 'sec141_anchor_found')
    start = m.start()
    old_block = text2[start:]
    s_recent = re.search(r'(?m)^## 最近更新', text2).start()
    s_unfin = re.search(r'(?m)^## 未完成纠偏', text2).start()
    s_recentchap = re.search(r'(?m)^## 最近章节', text2).start()
    mid1 = text2[s_recent:s_unfin]
    mid2 = text2[s_recentchap:start]
    compact = COMPACT.replace('\r\n', '\n')
    chk(compact.endswith('\n'), 'compact_ends_with_lf')

    archive_text = ('# 归档：STATUS_APP §141 + §142 正文（2026-11-06，逐字保留，'
                    '由 APP-052④ 压缩归档生成）\n\n' + old_block)
    with open(ARCHIVE, 'w', encoding='utf-8', newline='\n') as f:
        f.write(archive_text)
    arc = open(ARCHIVE, 'rb').read().decode('utf-8')
    chk(old_block in arc, 'archive_contains_old_block_verbatim',
        'old_block_bytes=%d' % len(old_block.encode('utf-8')))
    arc_stat = stat(ARCHIVE)

    # ── 收尾复核纠偏文件 + 产物实测 ───────────────────────────────────
    close = corr_state()
    same = (close['sha256'] == OPEN['sha256'] and close['bytes'] == OPEN['bytes']
            and close['mtime'] == OPEN['mtime'] and close['n_entries'] == OPEN['n_entries'])
    if same:
        tail = ('收尾 SHA `b3ae9ea9…f392b937d5`／224 562 B／2026-11-06 21:40:34／**80 条**'
                '（最大 APP-080）⇒ **与开工逐字一致（reviewer 本轮未追加）**，全程只读、未改、未提交')
    else:
        tail = ('收尾 SHA `%s`／%d B／%s／**%d 条**（最大 %s）⇒ 🔴 **与开工不一致，'
                'reviewer 本轮中途追加/改动了纠偏文件，如实记录、不声称零改动**'
                % (close['sha256'], close['bytes'], close['mtime'],
                   close['n_entries'], close['max_id']))

    arts = [stat(os.path.join(ROOT, p.replace('/', os.sep))) for p in ARTIFACTS]
    for a in arts:
        a['path'] = os.path.relpath(a['path'], ROOT).replace('\\', '/')
    rows = ['', '| 文件 | mtime | 字节数 | SHA256 |', '|---|---|---|---|']
    for a in arts:
        rows.append('| `%s` | %s | %d | `%s` |'
                    % (a['path'], a['mtime'], a['bytes'], a['sha256']))
    artifacts_md = '\n'.join(rows)

    body = open(BODY, 'rb').read().decode('utf-8').replace('\r\n', '\n')
    chk(body.count('{{NOW}}') == 1 and body.count('{{CORR_TAIL}}') == 1
        and body.count('{{ARTIFACTS}}') == 1 and body.count('{{N_ARTIFACTS}}') == 1,
        'placeholder_unique')
    body = (body.replace('{{NOW}}', now)
                .replace('{{CORR_TAIL}}', tail)
                .replace('{{N_ARTIFACTS}}', str(len(arts)))
                .replace('{{ARTIFACTS}}', artifacts_md))
    chk('{{' not in body, 'no_placeholder_left')
    if not body.endswith('\n'):
        body += '\n'

    new_text = text2[:start] + compact + '\n' + body
    data = new_text.encode('utf-8')
    new_size, new_lines = len(data), new_text.count('\n') + 1

    # ── 写入自检 ─────────────────────────────────────────────────────
    chk(mid1 in new_text, 'old_body_part1_verbatim',
        'bytes=%d' % len(mid1.encode('utf-8')))
    chk(mid2 in new_text, 'old_body_part2_verbatim',
        'bytes=%d' % len(mid2.encode('utf-8')))
    chk(new_text.startswith('# STATUS_APP\n\nlast_ack: APP-080\n更新时间: ' + now + '\n'),
        'header_exact')
    chk(len(re.findall(r'(?m)^## ', new_text)) >= len(re.findall(r'(?m)^## ', text)),
        'section_count_not_reduced',
        'old=%d new=%d' % (len(re.findall(r'(?m)^## ', text)),
                           len(re.findall(r'(?m)^## ', new_text))))
    chk(b'\r\n' not in data, 'output_eol_lf')
    chk(new_size <= 40000, 'size_le_40000', 'bytes=%d' % new_size)
    chk(new_lines <= 300, 'lines_le_300', 'lines=%d' % new_lines)
    chk('## §143 ' in new_text and text.count('## §143 ') == 0,
        'sec143_appended_once')
    chk('§141 无新纠偏' in new_text and '§142 无新纠偏' in new_text,
        'sec141_142_titles_kept')

    tmp = STATUS + '.tmp_app317'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, STATUS)
    back = open(STATUS, 'rb').read()
    chk(back == data, 'readback_byte_equal', 'bytes=%d' % len(back))
    st_stat = stat(STATUS)

    report = dict(tool='_app317_write_status_sec143', app='APP-079/APP-080',
                  verdict='PASS', generated_at=now,
                  status=dict(before=dict(bytes=old_size, lines=old_lines,
                                          sha256=hashlib.sha256(raw).hexdigest()),
                              after=st_stat, lines=new_lines),
                  archive=arc_stat, unfin_archive=unfin_stat,
                  unfin_block=dict(bytes=len(unfin_block.encode('utf-8')),
                                   sha256=hashlib.sha256(unfin_block.encode('utf-8')).hexdigest()),
                  compact_block_sha256=hashlib.sha256(compact.encode('utf-8')).hexdigest(),
                  old_block=dict(bytes=len(old_block.encode('utf-8')),
                                 sha256=hashlib.sha256(old_block.encode('utf-8')).hexdigest()),
                  corrections=dict(open=OPEN, close=close, identical=same),
                  head_changes=head_changes, artifacts=arts,
                  checks=checks)
    with open(REPORT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict='PASS', n_checks=len(checks),
                          status_before=[old_size, old_lines],
                          status_after=[new_size, new_lines],
                          archive_bytes=arc_stat['bytes'],
                          corrections_identical=same,
                          close=close,
                          n_artifacts=len(arts)), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
