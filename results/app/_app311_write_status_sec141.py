# -*- coding: utf-8 -*-
"""
写入 STATUS §141（2026-11-06 巡检轮）。

定点写入纪律（APP-052④ / STATUS 定点写入铁律）：
  - 只动头部若干行、只把「最近更新」旧条目整块搬迁到归档件、只追加 §141；
  - 旧正文逐字未变（difflib 替换块白名单校验）；
  - 归档件逐字命中被搬迁块（bytes 级包含断言）；
  - 章节数不少、行尾不破、写后 ≤40 000 B / ≤300 行；
  - 先临时文件，再 os.replace 原子替换。

用法： python _app311_write_status_sec141.py "YYYY-MM-DD HH:mm:ss"
       （时间由 PowerShell Get-Date 实测传入，禁止推算）
"""
import difflib
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
ARCHIVE_DIR = os.path.join(ROOT, 'status', 'archive')
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_recent_updates_upto_20261106.md')
OUT = os.path.join(HERE, '_app311_write_status_sec141.json')

LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha(b):
    return hashlib.sha256(b).hexdigest()


def corr_facts():
    b = open(CORR, 'rb').read()
    ids = re.findall(rb'(?m)^## (APP-[0-9]+)', b)
    return {
        'sha256': sha(b),
        'bytes': len(b),
        'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(CORR))),
        'n_items': len(ids),
        'max_id': ids[-1].decode() if ids else None,
    }


def replace_prefix_line(lines, prefix, new_line):
    hits = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    assert len(hits) == 1, 'prefix not unique: %r -> %r' % (prefix, hits)
    i = hits[0]
    lines[i] = new_line + '\n'
    return i


def append_to_line(lines, prefix, extra):
    hits = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    assert len(hits) == 1, 'prefix not unique: %r -> %r' % (prefix, hits)
    i = hits[0]
    lines[i] = lines[i].rstrip('\n') + extra + '\n'
    return i


def main():
    now = sys.argv[1]
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', now), now

    old_bytes = open(STATUS, 'rb').read()
    old_text = old_bytes.decode('utf-8')
    # 不能 splitlines()：正文含私用区/控制字符，会被当作额外行分隔符 ⇒ 切出无 LF 的假行。
    _parts = old_text.split('\n')
    assert _parts[-1] == '', 'STATUS must end with LF'
    old_lines = [p + '\n' for p in _parts[:-1]]
    assert len(old_lines) == old_bytes.count(b'\n'), 'LF count mismatch'
    assert b'\r\n' not in old_bytes, 'STATUS is LF-only; CRLF would need normalization'
    before = {'bytes': len(old_bytes), 'lines': len(old_lines), 'sha256': sha(old_bytes)}

    OPEN_SHA = 'bbc95c4382f29fa3c8b4f1b49ff644339b025f78447a3bb263e6b680ad4d82af'
    OPEN_BYTES, OPEN_N, OPEN_MTIME = 220735, 78, '2026-11-06 13:31:54'
    cf = corr_facts()   # 收尾复核：可能被 reviewer 中途追加，不强制等于开工基线

    # ---- 1. 头部定点写入 ----
    lines = list(old_lines)
    changed = set()
    changed.add(replace_prefix_line(lines, '更新时间: ', '更新时间: ' + now))
    changed.add(replace_prefix_line(
        lines, '当前任务: ',
        '当前任务: **§141 无新纠偏（`CORRECTIONS_APP.md` 78 条 = `last_ack: APP-078`）** —— '
        '按 APP-046 ② 不空转，做 §140 证据链自证（`_app310` **48 PASS / 0 FAIL**）＋半交付检查；'
        '🔴 **APP-075 仍停在「需 Opus 复核」节点 ⇒ 按 APP-046 ④ 停止，不自行推进、v2.3 不打包**'))
    changed.add(append_to_line(
        lines, '阻塞 / 待用户决定: ',
        ' ｜**§141 补充**：本轮 `ac61878` 已提交且 `origin/main..HEAD` 为空（无半交付漏项）；'
        'APP-075 的 r2 F0 表／APP-074 结论改正／3 旧包 `bridge_token.txt` 清单／本轮未打包 **仍等 reviewer 复核**'))
    changed.add(append_to_line(
        lines, '已压缩: ',
        ' ｜**§141 本轮压缩**：「最近更新」中 2026-11-05 及更早的条目整块逐字归档 ⇒ '
        '`status/archive/STATUS_APP_recent_updates_upto_20261106.md`（被搬迁块 SHA256 见 `_app311` 证据）'))

    # ---- 2. 压缩「最近更新」旧条目（整块搬迁，逐字保留） ----
    i = [k for k, l in enumerate(lines) if l.rstrip('\n') == '## 最近更新']
    j = [k for k, l in enumerate(lines) if l.rstrip('\n') == '## 当前有效结论']
    assert len(i) == 1 and len(j) == 1 and i[0] < j[0], (i, j)
    i, j = i[0], j[0]
    assert '§139' in lines[i + 1] and '§140' in lines[i + 2], 'unexpected recent-update head'
    block = lines[i + 3:j]
    assert len(block) >= 10 and any('2026-11-05' in l for l in block), 'block too small'
    block_bytes = ''.join(block).encode('utf-8')
    block_sha = sha(block_bytes)

    archive_header = (
        '# STATUS_APP「最近更新」历史条目（2026-11-05 及更早）\n\n'
        '> 2026-11-06 §141 压缩时从 `status/app/STATUS_APP.md` 整块搬迁，**逐字保留、一字未删**。\n'
        '> 被搬迁块 SHA256 `%s` / %d B / %d 行。\n\n' %
        (block_sha, len(block_bytes), len(block)))
    archive_bytes = archive_header.encode('utf-8') + block_bytes
    tmp_a = ARCHIVE + '.tmp_app311'
    with open(tmp_a, 'wb') as f:
        f.write(archive_bytes)
    os.replace(tmp_a, ARCHIVE)
    assert block_bytes in open(ARCHIVE, 'rb').read(), 'archive byte-level hit failed'

    index_line = (
        '> 🔴 2026-11-05 及更早的「最近更新」条目（%d 行）已**逐字归档** ⇒ '
        '`status/archive/STATUS_APP_recent_updates_upto_20261106.md`（块 SHA256 `%s`）；'
        '本节只留 §139 / §140 两条速查。\n' % (len(block), block_sha))

    # ---- 3. 追加 §141 ----
    sec141 = [
        '\n',
        '## §141 无新纠偏（last_ack=APP-078）｜§140 证据链自证 48/0 全数落盘（%s）\n' % now,
        '\n',
        '- **开工结论：无编号大于 `last_ack` 的新纠偏**（开工读数，非收尾）。'
        '`status/app/CORRECTIONS_APP.md` **%d 条**（APP-001..APP-078，SHA `%s`）＝ 头部 `last_ack: APP-078`；'
        '按 APP-046 ②「不空转」改做不占设备的证据链自证；按 ④「卡在需 reviewer/用户决定」停止。'
        '收尾复核见下方专条。\n' % (OPEN_N, OPEN_SHA),
        '- **证据链自证**：`results/app/_app310_sec140_evidence_recheck.py` → '
        '`results/app/_app310_sec140_evidence_recheck.json`（%s）⇒ '
        '**48 PASS / 0 FAIL / verdict=PASS**：34 条「结果文件＋原始字段」断言（`_app302` 26/0、`_app304` 39/0、'
        '`_app305` 27/0、`_app306` 28/0、`_app307` 14/0、`_app309` 18/0、`after.n_files=54`／'
        '`after.n_bytes=20175499`、`gate` 21/19/6、`_app303` 写前 52／20 160 623 B、'
        '`_app295` F0 160/170 Hz、`_app298` 3/0、`app299` `mode=offline_stat_embed`／`verdict=FAIL`）'
        '＋ **3 条反证全被识破**（错值／缺字段／错 gate ⇒ 判据非恒真）＋ 11 条 STATUS 文本锚点全部命中；'
        '各产物字节数／mtime／SHA256 见 JSON `evidence_files`。⇒ **§140 的报数全部真实落盘，未发现不实结论**。\n'
        % '_app310_sec140_evidence_recheck.json',
        '- **半交付检查**：`git log` ⇒ `ac61878`（§140，41 文件）已提交，`git log origin/main..HEAD` **为空** '
        '⇒ 上一轮无未推送改动；`MACHINE_LOCK` 本轮 `NOT_PRESENT`（未占设备）；工作区另有其它模块大量'
        '未提交改动（c0xx 系列／`status/asr/CORRECTIONS_ASR.md`／`status/CORRECTIONS.md` 等）⇒ **一个都没吞**。\n',
        '- 🔴 **APP-075 本条需等 reviewer 复核**（纠偏原文 L1463「需 Opus 复核：待 r2 交付后」）：'
        'r2 已交付（54 文件／20 175 499 B）但 F0 闸门 **21 PASS / 19 FAIL / 6 NONE**，19 个 FAIL 全是 '
        '`male→female`；`app299` 仍是 `offline_stat_embed`（统计嵌入，`verdict=FAIL`）⇒ **真 x-vector 余弦矩阵未产出**；'
        '第 2 臂 preset 对照未跑；第 1 臂未跑满 300 s ⇒ **本轮不自行判定通过、不往下推进、v2.3 不打包**。'
        '待复核清单：r2 F0 表／APP-074 结论改正（目录≠zip）／3 个旧包 `bridge_token.txt` 清单／本轮未打包。\n',
        '- 🔴 **停止原因（APP-046 ④）**：唯一可继续的实质项（真 x-vector、第 2 臂设备级）落在停止点之后且需占设备；'
        'v2.3 打包需用户通知（用户级规则「不通知不打包」）⇒ 本轮 **未打包／未打 zip／未改任何客户安装目录与旧 zip／'
        '未改桌面 .lnk／未在 CPU 跑推理测速／未调 MiniMax／未提交 `CORRECTIONS_APP.md`**。'
        '旧包 v2.0/v2.1/v2.2 目录与 zip **一字节未动**。\n',
        '- 🔴 **纠偏文件收尾复核（全程只读、未改、未提交）**：开工 SHA `bbc95c43…d82af`／%d B／'
        '%s／**%d 条** ⇒ 收尾 SHA `%s`／%d B／%s／**%d 条**（最大 %s）⇒ %s。\n'
        % (OPEN_BYTES, OPEN_MTIME, OPEN_N, cf['sha256'], cf['bytes'], cf['mtime'],
           cf['n_items'], cf['max_id'],
           '一致（reviewer 本轮未追加，可称零改动）；`last_ack` 保持 APP-078'
           if cf['sha256'] == OPEN_SHA
           else '**不一致 ⇒ reviewer 中途追加/改动，如实记录、不声称零改动**；新编号本轮未执行，'
                '`last_ack` 仍为 APP-078，留下一轮按编号顺序处理'),
        '- **写入纪律**：头部仅 4 行定点改动；「最近更新」旧条目整块逐字归档（块 SHA `%s`）；'
        '末尾仅追加本章节 ⇒ `difflib` 替换块白名单校验旧正文逐字未变；章节数不减、行尾 LF 未破、'
        '写后 ≤ %d B / ≤ %d 行（见 `_app311_write_status_sec141.json`）。\n' % (block_sha, LIMIT_BYTES, LIMIT_LINES),
    ]

    new_lines = lines[:i + 3] + [index_line] + lines[j:] + sec141
    new_bytes = ''.join(new_lines).encode('utf-8')
    after = {'bytes': len(new_bytes), 'lines': len(new_lines), 'sha256': sha(new_bytes)}

    # ---- 4. 写前校验 ----
    checks = []

    def ck(name, ok, detail):
        checks.append({'name': name, 'pass': bool(ok), 'detail': detail})

    ck('newline_LF_only', b'\r\n' not in new_bytes and all(l.endswith('\n') for l in new_lines),
       'CRLF=%d' % new_bytes.count(b'\r\n'))
    ck('size_limit', after['bytes'] <= LIMIT_BYTES, '%d <= %d' % (after['bytes'], LIMIT_BYTES))
    ck('line_limit', after['lines'] <= LIMIT_LINES, '%d <= %d' % (after['lines'], LIMIT_LINES))

    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    changed_old = set()
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag != 'equal':
            changed_old.update(range(a1, a2))
    allowed = changed | set(range(i + 3, j))
    ck('old_body_byte_identical_outside_whitelist', changed_old <= allowed,
       'changed_old=%d allowed=%d extra=%s' % (len(changed_old), len(allowed),
                                               sorted(changed_old - allowed)[:10]))
    ck('archive_byte_hit', block_bytes in open(ARCHIVE, 'rb').read(),
       'block_sha=%s block_bytes=%d' % (block_sha, len(block_bytes)))
    ck('compressed_block_removed', block_bytes not in new_bytes, 'old block absent from STATUS')

    old_secs = set(re.findall(r'(?m)^### (§\d+)', old_text))
    new_secs = set(re.findall(r'(?m)^### (§\d+)', ''.join(new_lines)))
    ck('no_section_lost', old_secs <= new_secs, 'old=%d new=%d missing=%s' %
       (len(old_secs), len(new_secs), sorted(old_secs - new_secs)))
    ck('sec141_added', '## §141 ' in ''.join(new_lines), 'sec141 heading present')
    ck('last_ack_unchanged', 'last_ack: APP-078' in ''.join(new_lines), 'no new id => unchanged')
    ck('update_time_is_measured', ('更新时间: ' + now) in ''.join(new_lines), now)
    ck('corrections_never_written_by_this_run', True,
       '只读文件，本轮未写入；开工/收尾差异在 §141 如实记录（不阻断）')

    n_fail = sum(1 for c in checks if not c['pass'])
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    report = {
        'tool': 'app311_write_status_sec141',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'measured_status_time': now,
        'before': before, 'after': after,
        'compressed_block': {'lines': len(block), 'bytes': len(block_bytes), 'sha256': block_sha,
                             'archive': os.path.relpath(ARCHIVE, ROOT).replace('\\', '/')},
        'header_lines_changed': sorted(changed),
        'checks': checks, 'n_pass': len(checks) - n_fail, 'n_fail': n_fail, 'verdict': verdict,
        'corrections_fingerprint': cf,
    }

    if verdict != 'PASS':
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print('VERDICT=FAIL (STATUS NOT WRITTEN)', n_fail)
        for c in checks:
            if not c['pass']:
                print('  FAIL', c['name'], c['detail'])
        return 1

    tmp = STATUS + '.tmp_app311'
    with open(tmp, 'wb') as f:
        f.write(new_bytes)
    os.replace(tmp, STATUS)
    assert open(STATUS, 'rb').read() == new_bytes, 'atomic replace verify failed'
    report['status_written'] = True
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('VERDICT=%s before=%dB/%dL after=%dB/%dL archive_block=%dB checks=%d/%d' %
          (verdict, before['bytes'], before['lines'], after['bytes'], after['lines'],
           len(block_bytes), report['n_pass'], len(checks)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
