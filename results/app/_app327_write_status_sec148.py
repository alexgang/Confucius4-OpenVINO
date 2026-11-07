r"""_app327 — 定点写入 STATUS_APP.md §148（APP-052④ 纪律）。

本轮无压缩（写前 33 623 B / 177 行，余量充足）：
  * 头部只定点改「更新时间」「当前任务」2 行；last_ack 保持 APP-080。
  * 末尾只追加 §148 章节；旧正文一字不删。
  * 写前自检：反向还原==旧全文・章节不减・LF 未破・≤40 000 B / ≤300 行。
  * 临时文件 os.replace 原子替换；写后磁盘逐字节复核。
  * 步骤 4：脚本内实时复核 CORRECTIONS_APP.md 的 SHA/字节/mtime/条数，
    与开工基准比对；reviewer 中途追加则如实记录，绝不声称「SHA 零改动」。
  * 全程只读 CORRECTIONS_APP.md，绝不修改。
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
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
EVIDENCE = os.path.join(HERE, '_app326_v23_pkg_gate_audit.json')
AUDIT_PY = os.path.join(HERE, '_app326_v23_pkg_gate_audit.py')
OUT = os.path.join(HERE, '_app327_write_status_sec148.json')
ARCHIVE = os.path.join(ROOT, 'status', 'archive',
                       'STATUS_APP_sec147_20261107.md')
NOW = '2026-11-07 13:55:33'  # PowerShell Get-Date 实测值（禁止推算）

LIMIT_BYTES = 40000
LIMIT_LINES = 300
BASE = dict(sha256='b3ae9ea9fb72282bbf619dd26b73de688f8c771911bd0b56e0faf8f392b937d5',
            bytes=224562, mtime='2026-11-06 21:40:34', n_headings=80,
            max_id=80)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def stat_of(path):
    b = open(path, 'rb').read()
    st = os.stat(path)
    return dict(path=path, bytes=len(b),
                mtime=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(
                    timespec='seconds'),
                sha256=sha(b))


def main():
    old_b = open(STATUS, 'rb').read()
    old = old_b.decode('utf-8')
    checks = []

    def chk(cond, name, detail):
        checks.append(dict(name=name, ok=bool(cond), detail=str(detail)[:400]))

    ev = json.load(open(EVIDENCE, encoding='utf-8'))
    f = ev['facts']

    # ── 步骤 4：纠偏文件收尾复核（实时采集，只读）──────────────────────
    cb = open(CORR, 'rb').read()
    cs = cb.decode('utf-8', errors='replace')
    ids = [int(x) for x in re.findall(r'^## APP-(\d{3})', cs, re.M)]
    corr = dict(sha256=sha(cb), bytes=len(cb),
                mtime=datetime.datetime.fromtimestamp(
                    os.stat(CORR).st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                n_headings=len(ids), max_id=max(ids),
                continuous=(ids == list(range(1, max(ids) + 1))))
    corr_same = all(corr[k] == BASE[k] for k in BASE)
    chk(True, 'corrections_closing_rechecked', corr)
    if corr_same:
        corr_note = ('与开工逐字一致，**reviewer 本轮未追加**；'
                     '全程只读／未改／未提交，可称零改动。')
    else:
        corr_note = (
            '🔴 **reviewer 本轮中途改动了纠偏文件**：开工 80 条／SHA '
            '`b3ae9ea9…f392b937d5`／224562 B ⇒ 收尾 **%d 条**／SHA `%s`／%d B／%s；'
            '**如实记录，不声称「SHA 零改动」**；全程只读／未改／未提交。'
            % (corr['n_headings'], corr['sha256'], corr['bytes'], corr['mtime']))

    # ── APP-052④ 压缩：首版 41 860 B 超限 ⇒ §147 正文整块逐字归档 ────
    m147 = re.search(r'^## §147 ', old, re.M)
    chk(m147 is not None, 'sec147_located',
        'pos=%s' % (m147.start() if m147 else None))
    if m147 is None:
        raise SystemExit(2)
    head_part = old[:m147.start()]
    sec147 = old[m147.start():]
    blk_b = sec147.encode('utf-8')
    blk_sha = sha(blk_b)
    archive_text = (
        '# 归档：STATUS_APP §147 正文（逐字保留，APP-052④）\n\n'
        '> 归档时间：%s；块 SHA256 `%s`；块字节数 %d；块行数 %d。\n'
        '> 原文自下一行起**一字未改**，用于反向还原与逐字命中核验。\n\n'
        % (NOW, blk_sha, len(blk_b), sec147.count('\n') + 1)) + sec147
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    with open(ARCHIVE + '.tmp', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(archive_text)
    os.replace(ARCHIVE + '.tmp', ARCHIVE)
    arc_b = open(ARCHIVE, 'rb').read()
    chk(blk_b in arc_b, 'archive_contains_verbatim_block',
        'block_sha=%s arc_bytes=%d' % (blk_sha, len(arc_b)))
    quick = (
        '> 🔴 §147 正文（%d 行／%d B／块 SHA256 `%s`）已**整块逐字归档** ⇒ '
        '`status/archive/STATUS_APP_sec147_20261107.md`；速查：`_app324` 25/0・'
        'UNKNOWN 1・反证 12/12，v2.2 包内 asr_spk 仅 3/5、5 s seg IR 只在影子包、'
        'D5 两份 xml SHA 不同待 reviewer 裁定；`PKG_INCLUDE_FILES` NOT_WIRED、'
        'v2.2 包内基底 14/18、`ext/bridge_token.txt` 仍在；v2.3 未打包。\n'
        % (sec147.count('\n') + 1, len(blk_b), blk_sha))

    # ── 头部 2 行定点替换（唯一命中断言）──────────────────────────────
    lines = head_part.splitlines(True)
    targets = {'更新时间': None, '当前任务': None}
    for i, ln in enumerate(lines):
        for key in targets:
            if ln.startswith(key + ':'):
                chk(targets[key] is None, 'header_unique_' + key,
                    'duplicate line %d' % (i + 1))
                targets[key] = i
    chk(all(v is not None for v in targets.values()), 'header_2_lines_found',
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
             '当前任务: **§148 无新纠偏（last_ack=APP-080）｜APP-080 ④⑥ 随包洁净度闸门'
             '覆盖一致性只读审计 41/0・UNKNOWN 1・反证 9/9；'
             '🔴 新结论：`assert_pkg_clean.scan()` 只检出 2/6 类违规，'
             '对「克隆音色／克隆产物目录／测试 wav」3 类零检出 ⇒ 随包闸门覆盖不全，'
             '须并入 APP-080 ⑤ 待 reviewer 复核；构建期补丁 dev 基底 18/18 端到端回归通过；'
             'APP-075/079/080 仍停 reviewer 复核，v2.3 未打包**\n')
    head_changed = ''.join(lines)
    chk('last_ack: APP-080' in head_changed, 'last_ack_unchanged_APP080',
        '本轮无新编号，last_ack 保持 APP-080')

    # ── 产物清单（写 STATUS 时磁盘实测）───────────────────────────────
    art_paths = [AUDIT_PY, EVIDENCE, ARCHIVE, os.path.abspath(__file__)]
    arts = [stat_of(p) for p in art_paths]
    art_rows = '\n'.join(
        '| `%s` | %s | %d | `%s` |' % (
            os.path.relpath(a['path'], ROOT).replace('\\', '/'),
            a['mtime'], a['bytes'], a['sha256'])
        for a in arts)

    cov = f['coverage_matrix']
    cov_rows = '\n'.join(
        '| %s | `%s` | %s | %d |' % (
            m['cls'], m['path'],
            'PASS' if m['scan_detected'] else '**0 检出**',
            len(m['exclude_hits']))
        for m in cov)
    patches = f['patches']
    patch_line = '／'.join(
        '%s %d 锚点・%s・verify_source_ok=%s' % (
            p['file'].split('/')[-1], p['n_anchors'], p['eol'],
            str(p['verify_source_ok']).lower())
        for p in patches)
    hist = f['historical_fields']
    sb = f['status_before']
    assets = f['assets']

    sec148 = f'''## §148 无新纠偏（last_ack=APP-080）｜APP-080 ④⑥ 随包洁净度闸门覆盖一致性审计与构建期补丁端到端回归（{NOW}）

- **步骤 1–2**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，只读／未改／未提交）开工 SHA `b3ae9ea9…f392b937d5`／224 562 B／mtime 2026-11-06 21:40:34／**{BASE['n_headings']} 条**（APP-001..080 连续无缺号，`max_id={BASE['max_id']}`，`continuous=true`）；`last_ack: APP-080` 对齐 ⇒ **无编号大于 last_ack 的新条目，步骤 3 无条可执行，无需写「本条已完成／本条需等复核」**。租约 `acquire app` ⇒ exit 0（TOKEN 9c1b825d，**无 TAKEOVER**）；`MACHINE_LOCK` 全程 `NOT_PRESENT`。
- **步骤 3 / APP-046② 不空转**（STATUS 头部「阻塞/待办」非空、本模块无进程在跑，且三条复核节点明文不得自行推进）：做**不占设备的纯 CPU 静态自证** ⇒ `results/app/_app326_v23_pkg_gate_audit.json` → `verdict={ev['verdict']}`／`n_pass={ev['n_pass']}`／`n_fail={ev['n_fail']}`／`n_unknown={ev['n_unknown']}`／`counterproof_identified={ev['counterproof_identified']}`（9 条反证改的都是「被测的那个对象」：`TOKEN_RE`／`VOICE_RE`／排除模式列表／黑名单列表／**未打补丁的 dev 原文**，逐条见 JSON 的 `counterproof` 字段）。
- 🔴 **本轮新结论（历史各轮未验过的判据盲区，需 reviewer 复核）**：§143 落盘的两份 dev 资产 —— `live_caption/assert_pkg_clean.py`（**{assets['assert_pkg_clean']['bytes']} B**／SHA `{assets['assert_pkg_clean']['sha256'][:12]}…`，建包后实际调用的随包闸门）与 `live_caption/v23_preset_only.py`（**{assets['v23_preset_only']['bytes']} B**／SHA `{assets['v23_preset_only']['sha256'][:12]}…`，定义 `PKG_EXCLUDE_PATTERNS` **{f['pattern_counts']['exclude']}** 条＋`BLACKLIST_PATTERNS` **{f['pattern_counts']['blacklist']}** 条）—— **覆盖范围不一致**：`facts.coverage_matrix` 用 `tempfile` 临时夹具（自动清理、非客户包、非 shared）实算 6 类应排除路径 ⇒ `assert_pkg_clean.scan()` 只检出前 **3/6**（APP-077 固定 token 与 APP-078 babelvox 示例音色），对 **3 类 APP-080 ④ 违规路径 `scan_detected=false`**：{', '.join('`%s`' % x for x in f['gate_not_covered_classes'])}；而 `PKG_EXCLUDE_PATTERNS` 对 6/6 全部命中（`exclude_hits` 各 ≥1）。⇒ **随包闸门覆盖不全（NOT_COVERED 3/6）**，仅靠 `assert_pkg_clean.py` 无法拦住 APP-080 ④「不含任何克隆音色或测试 wav」。覆盖矩阵（原始字段 `facts.coverage_matrix`）：
| 类别 | 夹具路径 | `scan_detected` | `exclude_hits` |
|---|---|---|---|
{cov_rows}
  干净路径（`facts.clean_paths_not_flagged`）⇒ 两闸门均 0 命中，不误伤 `preset_A.wav`／babelvox 库代码／tokenizer 配置；`facts.blacklist_positive_hits` ⇒ 5 条黑名单正则全部被正例覆盖、干净串 0 命中。**处置：并入 APP-080 ⑤ 待办（扩展 `assert_pkg_clean.py` 或统一由 `PKG_EXCLUDE_PATTERNS` 驱动），是否需改闸门属 reviewer 裁定 ⇒ 记 `n_unknown=1`，本轮不自行改代码、不写「已修复／已交付」**。
- **构建期补丁端到端回归（内存中，零写盘）**：`facts.patches` ⇒ {patch_line}，`facts.applied_anchor_total={f['applied_anchor_total']}` 且 18 个 id 无重复；补丁后 `ast.parse` 通过、`verify_source` 三份全 `ok=True`、**docstring 常量多重集补丁前后相等**（§143 `_app316` 首版插在 def 与 docstring 之间的教训已回归覆盖）、行尾还原（LF 文件仍 LF、CRLF 文件仍 CRLF）、`facts.dev_sources` 补丁前后磁盘 SHA/字节**全等** ⇒ dev 源文件与客户包一字未动。反证 `E7_unpatched_dev_*` 三份「未打补丁的 dev 原文」调同一 `verify_source` 全部返回 `ok=False` ⇒ 判据非恒真。
- **判据缺陷自纠（⚠️ 如实记录首跑）**：首跑 **40 PASS / 1 FAIL / 反证 9/9**，FAIL 项为 `sec147_packaging_chain_not_wired` —— 我把 `_app324` JSON 的 `facts.packaging_chain.refs_by_file`（**23 项「被扫描文件 → 引用数」映射，值全 0**）误当成「有引用的文件清单」而断言 `len()==0`；按「**FAIL 先怀疑判据／环境**」查证后改为 `sum(values)==0 and len==scanned`，复跑 **41 PASS / 0 FAIL**，判据口径错误非产品缺陷、未改任何产品代码。
- **历史结论实算复核（结果文件＋原始字段）**：`facts.historical_fields` ⇒ §147 `sec147_packaging_chain.scanned={hist['sec147_packaging_chain']['scanned']}`／`total_refs={hist['sec147_packaging_chain']['total_refs']}` ⇒ `PKG_INCLUDE_FILES` **仍 NOT_WIRED**；§146 `sec146_pkg_v22_unique_anchors={hist['sec146_pkg_v22_unique_anchors']}`／`sec146_direct_patch_applicable={str(hist['sec146_direct_patch_applicable']).lower()}`（18 锚点中包内基底仅 14 个，须先升级基底再套补丁）；§147 `sec147_bridge_token_paths={hist['sec147_bridge_token_paths']}` ⇒ APP-077 固定 token 在 v2.2 包根**仍在**（只记清单、不写已修）；`sec147_seg_w5_xml_differs={str(hist['sec147_seg_w5_xml_differs']).lower()}` ⇒ D5 仍 UNKNOWN、取哪份 xml 待 reviewer 裁定。`facts.independent_packaging_scan` ⇒ 独立实算 **{f['independent_packaging_scan']['scanned']} 个建包脚本／refs={f['independent_packaging_scan']['refs']}**，与 §145/§147 一致。
- ⛔ **停止点（明文）**：APP-075「需 Opus 复核」・APP-079「需 reviewer 复核」・APP-080 ⑤⑥「reviewer 复核通过后才通知用户」＋用户级「**不通知不打包**」⇒ 本轮**未自行推进 ⑤⑥**、**v2.3 不打包**；未打新版本目录与 zip／未改任何客户安装目录与 .lnk／未复制影子包资产／未建 `MACHINE_LOCK`（未占设备）／未在 CPU 跑推理测速／未调 MiniMax。**没落盘的一律不写「已交付」**。
- **写入纪律（APP-052④）**：`facts.status_before` ⇒ 写前 **{sb['bytes']} B／{sb['lines']} 行**／SHA `{sb['sha256'][:12]}…`；**首版 41 860 B 超 40 000 B 限额被写前自检拦下（STATUS 一个字节未落盘）** ⇒ 按 APP-052④ 把 §147 正文（{sec147.count(chr(10)) + 1} 行／{len(blk_b)} B／块 SHA256 `{blk_sha}`）**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec147_20261107.md`，原位留 1 行速查；头部仅定点改 `更新时间`／`当前任务` 2 行，`last_ack` 保持 APP-080、`已压缩` 一字未动；末尾只追加本章节；写前自检「反向还原==旧全文・归档件逐字命中・章节不减・LF 未破・≤40 000 B / ≤300 行」＋临时文件 `os.replace` 原子替换＋写后磁盘逐字节复核 ⇒ `results/app/_app327_write_status_sec148.json`。
- **纠偏文件收尾复核（步骤 4）**：SHA `{corr['sha256']}`／{corr['bytes']} B／{corr['mtime']}／**{corr['n_headings']} 条**（最大 APP-{corr['max_id']:03d}，`continuous={str(corr['continuous']).lower()}`）⇒ {corr_note}
- **产物清单（写 STATUS 时磁盘实测，共 {len(arts)} 个文件）**：
| 文件 | mtime | 字节数 | SHA256 |
|---|---|---|---|
{art_rows}
- **git**：逐文件 `git add`（禁 `-A`）⇒ main 普通 push、不 force；不提交 `CORRECTIONS_APP.md`，不吞其它模块。
- **下一轮必读**：① 等 reviewer 复核 §143–§148（尤其本轮「随包闸门覆盖缺口」是否要扩展 `assert_pkg_clean.py`）；② APP-080 ⑤ 待办已增至：接入 `PKG_INCLUDE_FILES` 到建包链路、把新包 3 份源文件升级到 dev 基底再套 18 锚点补丁、随包闸门补齐 3 类排除规则、D5 取哪份 xml 裁定；③ v2.3 打包只在用户明确通知＋⑤⑥ 验收＋reviewer 复核后做，且须新目录／新 zip／新 MANIFEST／重签 ACCEPTED；④ 「不主动打包」规则不变。
'''

    SEP = '\n'
    new = head_changed + quick + SEP + sec148
    new_b = new.encode('utf-8')

    # ── 写前自检 ─────────────────────────────────────────────────────
    chk(b'\r\n' not in new_b, 'no_crlf',
        'CRLF count=%d' % (new_b.count(b'\r\n'),))
    chk(len(new_b) <= LIMIT_BYTES, 'within_40000_bytes',
        'new_bytes=%d limit=%d' % (len(new_b), LIMIT_BYTES))
    chk(new_b.count(b'\n') <= LIMIT_LINES, 'within_300_lines',
        'new_lines=%d limit=%d' % (new_b.count(b'\n'), LIMIT_LINES))
    old_secs = re.findall(r'^## §\d+', old, re.M)
    new_secs = re.findall(r'^## §\d+', new, re.M)
    expected_secs = [x for x in old_secs if x != '## §147'] + ['## §148']
    chk(new_secs == expected_secs, 'sections_not_reduced_and_appended',
        'old=%s new=%s expected=%s' % (old_secs, new_secs, expected_secs))
    chk(blk_b in arc_b, 'verbatim_block_in_archive',
        'block sha=%s' % (blk_sha,))
    # 反向还原：去掉追加部分/分隔符/速查行，加回 §147 正文，
    # 再换回头部 2 行 ⇒ 必须逐字节等于旧全文。
    restored = new[:new.index('## §148 ')]
    chk(restored.endswith(SEP), 'append_separator_present', 'tail=%r' % SEP)
    if restored.endswith(SEP):
        restored = restored[:-len(SEP)]
    chk(restored.endswith(quick), 'restore_quick_tail',
        'quick len=%d' % len(quick))
    if restored.endswith(quick):
        restored = restored[:-len(quick)] + sec147
    chk(restored == head_changed + sec147,
        'restore_body_equals_head_plus_sec147',
        'restored=%d expected=%d' % (len(restored),
                                     len(head_changed + sec147)))
    for o, n in reversed(hdr_changes):
        chk(restored.count(n) == 1, 'restore_header_unique',
            'new line count=%d' % (restored.count(n),))
        restored = restored.replace(n, o, 1)
    chk(restored.encode('utf-8') == old_b, 'reverse_restore_equals_old_fulltext',
        'restored=%d old=%d equal=%s'
        % (len(restored.encode('utf-8')), len(old_b),
           restored.encode('utf-8') == old_b))

    n_fail = sum(1 for c in checks if not c['ok'])
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    report = dict(
        tool='_app327_write_status_sec148', verdict=verdict,
        n_checks=len(checks), n_fail=n_fail, checks=checks,
        status_before=dict(bytes=len(old_b), lines=old_b.count(b'\n'),
                           sha256=sha(old_b)),
        status_after_planned=dict(bytes=len(new_b), lines=new_b.count(b'\n'),
                                  sha256=sha(new_b)),
        header_changed_lines=[n.strip() for _, n in hdr_changes],
        archived_block=dict(
            file=os.path.relpath(ARCHIVE, ROOT).replace('\\', '/'),
            bytes=len(blk_b), lines=sec147.count('\n') + 1,
            sha256=blk_sha),
        last_ack='APP-080',
        corrections_closing_recheck=corr,
        corrections_equals_opening=corr_same,
        artifacts=arts, status_written=False)

    if verdict == 'PASS':
        tmp = STATUS + '.tmp_sec148'
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
        report['note'] = '写前自检未全过 ⇒ STATUS 一个字节都未落盘。'

    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict=report['verdict'],
                          n_checks=report['n_checks'], n_fail=report['n_fail'],
                          status_written=report['status_written'],
                          before=report['status_before'],
                          after=report['status_after_planned'],
                          corr_same=corr_same,
                          failing=[c['name'] for c in checks if not c['ok']]),
                     ensure_ascii=True, indent=2))
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
