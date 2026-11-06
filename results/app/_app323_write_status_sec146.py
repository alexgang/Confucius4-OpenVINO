r"""_app323 — 按 APP-052④ 压缩 §145 正文并定点写入 STATUS_APP.md §146。

纪律：头部只定点改 3 行（last_ack 保持 APP-080 不变）；末尾只追加新章节；
旧正文整块逐字归档（归档件可逐字命中）；写前自检「反向还原==旧全文」＋
章节不减＋LF 未破＋限额内；临时文件 os.replace 原子替换；写后磁盘逐字节复核。
写前自检不过 ⇒ STATUS 一个字节都不落盘。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(ROOT, 'status', 'archive',
                       'STATUS_APP_sec145_20261107.md')
OUT = os.path.join(HERE, '_app323_write_status_sec146.json')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
EVIDENCE = os.path.join(HERE, '_app322_v23_pkg_baseline_dryrun.json')
NOW = '2026-11-07 02:59:44'  # PowerShell Get-Date 实测值（禁止推算）

LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha(b):
    return hashlib.sha256(b).hexdigest()


def stat_of(path):
    b = open(path, 'rb').read()
    st = os.stat(path)
    return dict(path=path, bytes=len(b),
                mtime=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(
                    timespec='seconds'),
                sha256=sha(b))


def read_utf8(path):
    return open(path, 'rb').read().decode('utf-8')


def main():
    old_b = open(STATUS, 'rb').read()
    old = old_b.decode('utf-8')
    checks = []

    def chk(cond, name, detail):
        checks.append(dict(name=name, ok=bool(cond), detail=detail))

    # ── 纠偏文件收尾复核（步骤 4，实时采集）───────────────────────────
    cb = open(CORR, 'rb').read()
    cs = cb.decode('utf-8', errors='replace')
    corr = dict(sha256=sha(cb), bytes=len(cb),
                mtime=datetime.datetime.fromtimestamp(
                    os.stat(CORR).st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                n_headings=len(re.findall(r'^##\s*APP-\d{3}', cs, re.M)),
                max_id=max(int(x) for x in re.findall(r'APP-(\d{3})', cs)))
    BASE = dict(sha256='b3ae9ea9fb72282bbf619dd26b73de688f8c771911bd0b56e0faf8f392b937d5',
                bytes=224562, mtime='2026-11-06 21:40:34', n_headings=80,
                max_id=80)
    corr_same = all(corr[k] == BASE[k] for k in BASE)
    chk(corr_same, 'corrections_closing_recheck_unchanged',
        'closing=%s' % (corr,))

    # ── 定位 §145 正文块并整块逐字归档 ────────────────────────────────
    m = re.search(r'^## §145 ', old, re.M)
    chk(m is not None, 'sec145_located', 'pos=%s' % (m.start() if m else None))
    if m is None:
        raise SystemExit(2)
    head_part = old[:m.start()]
    sec145 = old[m.start():]
    blk_b = sec145.encode('utf-8')
    blk_sha = sha(blk_b)
    archive_text = (
        '# 归档：STATUS_APP §145 正文（逐字保留，APP-052④）\n\n'
        '> 归档时间：2026-11-07 02:59:44；块 SHA256 `%s`；块字节数 %d；块行数 %d。\n'
        '> 原文自下一行起**一字未改**，用于反向还原与逐字命中核验。\n\n'
        % (blk_sha, len(blk_b), sec145.count('\n') + 1)) + sec145
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    tmp_arc = ARCHIVE + '.tmp'
    with open(tmp_arc, 'w', encoding='utf-8', newline='\n') as f:
        f.write(archive_text)
    os.replace(tmp_arc, ARCHIVE)
    arc_b = open(ARCHIVE, 'rb').read()
    chk(blk_b in arc_b, 'archive_contains_verbatim_block',
        'block_sha=%s arc_bytes=%d' % (blk_sha, len(arc_b)))

    quick = (
        '> 🔴 §145 正文（21 行／5 212 B／块 SHA256 `%s`）已**整块逐字归档** ⇒ '
        '`status/archive/STATUS_APP_sec145_20261107.md`；速查：`_app320` 18/0・反证 7/7，'
        '`pack_v13.py`＋22 个建包脚本对 `PKG_INCLUDE_FILES` 引用数 0 ⇒ 打包链路 NOT_WIRED，'
        'APP-075/079/080 停 reviewer 复核、v2.3 未打包。\n' % (blk_sha,))

    # ── 头部 3 行定点替换（唯一命中断言）──────────────────────────────
    lines = head_part.splitlines(True)
    targets = {'更新时间': None, '当前任务': None, '已压缩': None}
    for i, ln in enumerate(lines):
        for key in targets:
            if ln.startswith(key + ':'):
                chk(targets[key] is None, 'header_unique_' + key,
                    'duplicate line %d' % (i + 1))
                targets[key] = i
    chk(all(v is not None for v in targets.values()), 'header_3_lines_found',
        'indices=%s' % (targets,))
    hdr_changes = []

    def set_line(key, new_text):
        i = targets[key]
        o = lines[i]
        chk(head_part.count(o) == 1, 'header_replace_unique_' + key,
            'count=%d' % (head_part.count(o),))
        hdr_changes.append((o, new_text))
        lines[i] = new_text

    set_line('更新时间', '更新时间: %s\n' % (NOW,))
    set_line('当前任务',
             '当前任务: **§146 无新纠偏（last_ack=APP-080）｜APP-080 构建期补丁对 v2.2 包内基底只读 '
             'dry-run 对账 33/0 ＋ 反证 8/8；14/18 锚点命中 ⇒ 须先升级新包基底，'
             'APP-075/079/080 仍停 reviewer 复核，v2.3 未打包**\n')
    old_compress = lines[targets['已压缩']]
    set_line('已压缩', old_compress.rstrip('\n') +
             '｜**§146 压缩**：§145 正文整块逐字归档 ⇒ '
             '`status/archive/STATUS_APP_sec145_20261107.md`\n')
    head_changed = ''.join(lines)
    chk('last_ack: APP-080' in head_changed, 'last_ack_unchanged_APP080',
        '本轮无新编号，last_ack 保持 APP-080')

    # ── 产物清单（写 STATUS 时磁盘实测）───────────────────────────────
    art_paths = [
        os.path.join(HERE, '_app322_v23_pkg_baseline_dryrun.py'),
        EVIDENCE,
        ARCHIVE,
        os.path.abspath(__file__),
    ]
    arts = [stat_of(p) for p in art_paths]
    art_rows = '\n'.join(
        '| `%s` | %s | %d | `%s` |' % (
            os.path.relpath(a['path'], ROOT).replace('\\', '/'),
            a['mtime'], a['bytes'], a['sha256'])
        for a in arts)
    ev = json.load(open(EVIDENCE, encoding='utf-8'))
    f = ev['facts']

    sec146 = f'''## §146 无新纠偏（last_ack=APP-080）｜APP-080 补丁对包内基底只读 dry-run 对账 33/0 ＋ 反证 8/8（{NOW}）

- **步骤 1–2**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，只读／未改／未提交）开工 SHA `b3ae9ea9…f392b937d5`／224 562 B／mtime 2026-11-06 21:40:34／**80 条**（APP-001..080 无缺号，`max_id=80`）；`last_ack: APP-080` 对齐 ⇒ **无编号大于 last_ack 的新条目，步骤 3 无条可执行**。
- **APP-046② 不空转**：`results/app/_app322_v23_pkg_baseline_dryrun.json` ⇒ `verdict={ev['verdict']}`／`n_pass={ev['n_pass']}`／`n_fail={ev['n_fail']}`／`n_unknown={ev['n_unknown']}`／`counterproof_identified={ev['counterproof_identified']}`（8/8 全被识破，逐条明细见该 JSON 的 `counterproof` 字段）。纯 CPU 静态：`facts.machine_lock_present={str(f['machine_lock_present']).lower()}`／未推理／未调 MiniMax／未打包。
- 🔴 **本轮新结论（APP-080 ⑤ 前置条件，需 reviewer 复核）**：`facts.dev_hits` ⇒ dev 三份源文件 **{f['total_anchors']}/{f['total_anchors']} 锚点唯一命中**，补丁后 `verify_source=True`／`ast.parse` 通过／5 个函数 `__doc__` 保持／行尾还原；`facts.pkg_v22_hits` 对真实 `Confucius4_LiveCaption_v2.2/app/` **只读**副本 ⇒ `pkg_v22_unique_anchors={f['pkg_v22_unique_anchors']}`／`total_anchors={f['total_anchors']}`、缺 `P03-checkbox`／`P04-hint`／`P05-startup`／`P08-onchange`（全在 `live_caption_app.py`；`tts_service.py` 3/3、`tts_worker.py` 4/4 全命中）⇒ `pkg_v22_direct_patch_applicable={str(f['pkg_v22_direct_patch_applicable']).lower()}` ⇒ **直接对 v2.2 包内副本套 §143 补丁会 AssertionError**。🔴 按「FAIL 先怀疑判据／环境」记**基底版本差异，非产品缺陷**（包内 mtime 2026-11-02 01:33、dev 11-05/11-06）⇒ **v2.3 打新版本前置条件**：新包目录 3 份源文件须先按「骨架等价校验后升级基底」同步到 dev 基底，再应用 18 锚点补丁；`PKG_INCLUDE_FILES` 仍 **NOT_WIRED**（§145 接入待办）。
- **只读纪律**：`facts.pkg_v22_before` / `pkg_v22_after` 逐文件 `sha256` 与 `bytes` 相等（`live_caption_app.py` 361 384 B／`tts_service.py` 127 483 B／`tts_worker.py` 229 782 B）；反证 E5 证明「写包」会被识破。旧 zip 本轮未重复全量实算（§142 已留证）⇒ 不新写「一字节未动」。
- **git / 限额只读核查**：`facts.git` ⇒ `head={f['git']['head']}`／`ahead={f['git']['ahead']}`／`branch={f['git']['branch']}`／`corrections_status='{f['git']['corrections_status']}'`（reviewer 未提交，本轮只读）；`facts.status_before` ⇒ 写前 **{f['status_before']['bytes']} B／{f['status_before']['lines']} 行**（余量仅 86 B）⇒ 按 APP-052④ 先压缩。
- ⛔ **停止点**：APP-075「需 Opus 复核」・APP-079「需 reviewer 复核」・APP-080 ⑤⑥「reviewer 复核通过后才通知用户」⇒ 未自行推进 ⑤⑥、**v2.3 不打包**；未打新版本目录与 zip／未改客户安装目录与 .lnk／未建 `MACHINE_LOCK`／未在 CPU 跑推理测速。**没落盘的不写「已交付」**。
- **写入纪律（APP-052④）**：§145 正文（21 行／5 212 B／块 SHA256 `{blk_sha}`）**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec145_20261107.md`，原位留速查行；头部仅定点改 `更新时间`／`当前任务`／`已压缩` 3 行，`last_ack` 保持 APP-080；末尾只追加本章节；写前自检「反向还原==旧全文・归档件逐字命中・章节不减・LF 未破・≤40 000 B / ≤300 行」＋临时文件 `os.replace` 原子替换＋写后磁盘逐字节复核 ⇒ `results/app/_app323_write_status_sec146.json`。
- **纠偏文件收尾复核（步骤 4）**：SHA `{corr['sha256']}`／{corr['bytes']} B／{corr['mtime']}／**{corr['n_headings']} 条**（最大 APP-{corr['max_id']:03d}）⇒ 与开工逐字一致，**reviewer 本轮未追加**；全程只读／未改／未提交，可称零改动。
- **产物清单（写 STATUS 时磁盘实测，共 {len(arts)} 个文件）**：
| 文件 | mtime | 字节数 | SHA256 |
|---|---|---|---|
{art_rows}
- **git**：逐文件 `git add`（禁 `-A`）⇒ main 普通 push、不 force；不提交 `CORRECTIONS_APP.md`，不吞其它模块。
'''

    new = head_changed + quick + '\n' + sec146
    new_b = new.encode('utf-8')

    # ── 写前自检 ─────────────────────────────────────────────────────
    chk(b'\r\n' not in new_b, 'no_crlf', 'CRLF count=%d' % (new_b.count(b'\r\n'),))
    chk(len(new_b) <= LIMIT_BYTES, 'within_40000_bytes',
        'new_bytes=%d limit=%d' % (len(new_b), LIMIT_BYTES))
    chk(new_b.count(b'\n') <= LIMIT_LINES, 'within_300_lines',
        'new_lines=%d limit=%d' % (new_b.count(b'\n'), LIMIT_LINES))
    old_secs = re.findall(r'^## §\d+', old, re.M)
    new_secs = re.findall(r'^## §\d+', new, re.M)
    # 🔴 APP-052④：被归档章节的标题随正文一起搬进归档件（§141/§142/§144 同口径），
    #    「章节不减」的正确判据 = 未归档章节标题全部原序保留 + 新章节追加在末尾。
    expected_secs = [s for s in old_secs if s != '## §145'] + ['## §146']
    chk(new_secs == expected_secs,
        'sections_not_reduced_and_appended',
        'old=%s new=%s expected=%s' % (old_secs, new_secs, expected_secs))
    chk(blk_b in arc_b, 'verbatim_block_in_archive', 'block sha=%s' % (blk_sha,))

    # 反向还原：去掉 §146、速查行换回原块、头部 3 行还原 ⇒ 应等于旧全文
    restored = new[:new.index('## §146 ')]
    tail = quick + '\n'
    chk(restored.endswith(tail), 'restore_quick_tail', 'tail matches')
    if restored.endswith(tail):
        restored = restored[:-len(tail)] + sec145
    for o, n in reversed(hdr_changes):
        chk(restored.count(n) == 1, 'restore_header_unique',
            'new line count=%d' % (restored.count(n),))
        restored = restored.replace(n, o, 1)
    chk(restored.encode('utf-8') == old_b, 'reverse_restore_equals_old_fulltext',
        'restored=%d old=%d equal=%s' % (len(restored.encode('utf-8')),
                                         len(old_b), restored.encode('utf-8') == old_b))

    n_fail = sum(1 for c in checks if not c['ok'])
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    report = dict(tool='_app323_write_status_sec146', verdict=verdict,
                  n_checks=len(checks), n_fail=n_fail, checks=checks,
                  status_before=dict(bytes=len(old_b),
                                     lines=old_b.count(b'\n') + 1,
                                     sha256=sha(old_b)),
                  status_after_planned=dict(bytes=len(new_b),
                                            lines=new_b.count(b'\n') + 1,
                                            sha256=sha(new_b)),
                  archived_block=dict(file=os.path.relpath(ARCHIVE, ROOT).replace('\\', '/'),
                                      bytes=len(blk_b), lines=sec145.count('\n') + 1,
                                      sha256=blk_sha),
                  corrections_closing_recheck=corr,
                  corrections_equals_opening=corr_same,
                  artifacts=arts,
                  status_written=False)

    if verdict == 'PASS':
        tmp = STATUS + '.tmp_sec146'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(new)
        os.replace(tmp, STATUS)
        disk_b = open(STATUS, 'rb').read()
        chk(disk_b == new_b, 'post_write_disk_byte_equal',
            'disk=%d planned=%d' % (len(disk_b), len(new_b)))
        report['status_written'] = True
        report['post_write_disk_equal'] = (disk_b == new_b)
        report['n_fail'] = sum(1 for c in checks if not c['ok'])
        report['verdict'] = 'PASS' if report['n_fail'] == 0 else 'FAIL'
        report['checks'] = checks
    else:
        report['note'] = '写前自检未全过 ⇒ STATUS 一个字节都未落盘；归档件已生成。'

    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict=report['verdict'],
                          n_checks=report['n_checks'], n_fail=report['n_fail'],
                          status_written=report['status_written'],
                          before=report['status_before'],
                          after=report['status_after_planned'],
                          archive_bytes=len(blk_b),
                          corr_same=corr_same,
                          failing=[c['name'] for c in checks if not c['ok']]),
                     ensure_ascii=False, indent=2))
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
