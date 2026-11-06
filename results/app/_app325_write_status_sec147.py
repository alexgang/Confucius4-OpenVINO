r"""_app325 — 按 APP-052④ 压缩 §146 正文并定点写入 STATUS_APP.md §147。

纪律：头部只定点改 3 行（last_ack 保持 APP-080 不变）；末尾只追加新章节；
旧正文整块逐字归档；写前自检「反向还原==旧全文」+ 章节不减 + LF 未破 + 限额内；
临时文件 os.replace 原子替换；写后磁盘逐字节复核。自检不过 ⇒ STATUS 一个字节都不落盘。
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
                       'STATUS_APP_sec146_20261107.md')
ARCHIVE2 = os.path.join(ROOT, 'status', 'archive',
                        'STATUS_APP_sec143_20261107.md')
OUT = os.path.join(HERE, '_app325_write_status_sec147.json')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
EVIDENCE = os.path.join(HERE, '_app324_app080_prereq_readonly_audit.json')
AUDIT_PY = os.path.join(HERE, '_app324_app080_prereq_readonly_audit.py')
NOW = '2026-11-07 04:13:00'  # PowerShell Get-Date 实测值（禁止推算）

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


def main():
    old_b = open(STATUS, 'rb').read()
    old = old_b.decode('utf-8')
    checks = []

    def chk(cond, name, detail):
        checks.append(dict(name=name, ok=bool(cond), detail=detail))

    ev = json.load(open(EVIDENCE, encoding='utf-8'))
    f = ev['facts']

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
    # 复核本身是必做项；是否与开工一致不作为「禁止写 STATUS」的闸门，
    # 否则 reviewer 中途追加条目时反而无法如实落盘（步骤 4 要求如实记录）。
    chk(True, 'corrections_closing_rechecked', 'closing=%s' % (corr,))
    if corr_same:
        corr_note = ('与开工逐字一致，**reviewer 本轮未追加**；'
                     '全程只读／未改／未提交，可称零改动。')
    else:
        corr_note = (
            '🔴 **reviewer 本轮中途改动了纠偏文件**：开工 80 条／SHA '
            '`b3ae9ea9…f392b937d5`／224562 B ⇒ 收尾 **%d 条**／SHA `%s`／%d B／%s；'
            '**如实记录，不声称「SHA 零改动」**；全程只读／未改／未提交。'
            % (corr['n_headings'], corr['sha256'], corr['bytes'], corr['mtime']))

    # ── 定位 §146 正文块并整块逐字归档 ────────────────────────────────
    m = re.search(r'^## §146 ', old, re.M)
    chk(m is not None, 'sec146_located', 'pos=%s' % (m.start() if m else None))
    if m is None:
        raise SystemExit(2)
    sec146 = old[m.start():]
    blk_b = sec146.encode('utf-8')
    blk_sha = sha(blk_b)
    archive_text = (
        '# 归档：STATUS_APP §146 正文（逐字保留，APP-052④）\n\n'
        '> 归档时间：%s；块 SHA256 `%s`；块字节数 %d；块行数 %d。\n'
        '> 原文自下一行起**一字未改**，用于反向还原与逐字命中核验。\n\n'
        % (NOW, blk_sha, len(blk_b), sec146.count('\n') + 1)) + sec146
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    with open(ARCHIVE + '.tmp', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(archive_text)
    os.replace(ARCHIVE + '.tmp', ARCHIVE)
    arc_b = open(ARCHIVE, 'rb').read()
    chk(blk_b in arc_b, 'archive_contains_verbatim_block',
        'block_sha=%s arc_bytes=%d' % (blk_sha, len(arc_b)))

    # ── 定位 §143 旧正文块（二次压缩，首版 42 844 B 超限被拦）─────────
    m143 = re.search(r'^## §143 ', old, re.M)
    chk(m143 is not None, 'sec143_located',
        'pos=%s' % (m143.start() if m143 else None))
    if m143 is None:
        raise SystemExit(2)
    head_part = old[:m143.start()]
    mid = old[m143.start():m.start()]
    mid_b = mid.encode('utf-8')
    mid_sha = sha(mid_b)
    archive2_text = (
        '# 归档：STATUS_APP §143 正文＋§144/§145 速查行（逐字保留，APP-052④）\n\n'
        '> 归档时间：%s；块 SHA256 `%s`；块字节数 %d；块行数 %d。\n'
        '> 原文自下一行起**一字未改**，用于反向还原与逐字命中核验。\n\n'
        % (NOW, mid_sha, len(mid_b), mid.count('\n') + 1)) + mid
    with open(ARCHIVE2 + '.tmp', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(archive2_text)
    os.replace(ARCHIVE2 + '.tmp', ARCHIVE2)
    arc2_b = open(ARCHIVE2, 'rb').read()
    chk(mid_b in arc2_b, 'archive2_contains_verbatim_block',
        'block_sha=%s arc2_bytes=%d' % (mid_sha, len(arc2_b)))

    quick2 = (
        '> 🔴 §143 正文＋§144/§145 速查行（%d 行／%d B／块 SHA256 `%s`）已**整块逐字归档** ⇒ '
        '`status/archive/STATUS_APP_sec143_20261107.md`；速查：APP-079 静态归因 10/0、'
        'APP-080 构建期补丁 36/0・反证 8/8、docstring 修正、界面/运行时/旁路/包内容四项；'
        '⑤⑥ 停 reviewer 复核、v2.3 未打包。\n'
        % (mid.count('\n') + 1, len(mid_b), mid_sha))

    quick = (
        '> 🔴 §146 正文（%d 行／%d B／块 SHA256 `%s`）已**整块逐字归档** ⇒ '
        '`status/archive/STATUS_APP_sec146_20261107.md`；速查：`_app322` 33/0・反证 8/8，'
        'dev 18/18 锚点唯一命中、v2.2 包内基底仅 14/18（缺 P03/P04/P05/P08）⇒ '
        'v2.3 打新版本须先升级包内 3 份源文件基底再套 18 锚点补丁，v2.3 未打包。\n'
        % (sec146.count('\n') + 1, len(blk_b), blk_sha))

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
             '当前任务: **§147 无新纠偏（last_ack=APP-080）｜APP-080 ⑤ 前置资产只读盘点＋'
             '§143–§146 证据链实算复核 25/0・UNKNOWN 1・反证 12/12；'
             '5/5 spk 文件与 2 个 fp16-w5 IR 仅存在于影子包，v2.2 包内 3/5 且无 IR；'
             'APP-075/079/080 仍停 reviewer 复核，v2.3 未打包**\n')
    old_compress = lines[targets['已压缩']]
    set_line('已压缩', old_compress.rstrip('\n') +
             '｜**§147 压缩（首版 42 844 B 超限被拦，STATUS 未落盘 ⇒ 二次压缩）**：'
             '§146 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec146_20261107.md`；'
             '§143 正文＋§144/§145 速查行整块逐字归档 ⇒ '
             '`status/archive/STATUS_APP_sec143_20261107.md`\n')
    head_changed = ''.join(lines)
    chk('last_ack: APP-080' in head_changed, 'last_ack_unchanged_APP080',
        '本轮无新编号，last_ack 保持 APP-080')

    # ── 产物清单（写 STATUS 时磁盘实测）───────────────────────────────
    art_paths = [AUDIT_PY, EVIDENCE, ARCHIVE, ARCHIVE2,
                 os.path.abspath(__file__)]
    arts = [stat_of(p) for p in art_paths]
    art_rows = '\n'.join(
        '| `%s` | %s | %d | `%s` |' % (
            os.path.relpath(a['path'], ROOT).replace('\\', '/'),
            a['mtime'], a['bytes'], a['sha256'])
        for a in arts)

    s = f['sec146']
    pc = f['packaging_chain']
    spk = f['spk']
    seg = f['seg_w5']
    br = f['bridge']
    g = f['git']
    hdr = f['status_header']
    dev = f['disk']['dev_sources']
    pkg = f['disk']['pkg_v22_sources']
    v23 = f['disk']['v23_assets']
    shadow_bin = next(x for x in seg['shadow_files']
                      if x['name'] == 'pyannote_seg_3_0_w5.bin')
    shadow_xml = next(x for x in seg['shadow_files']
                      if x['name'] == 'pyannote_seg_3_0_w5.xml')

    sec147 = f'''## §147 无新纠偏（last_ack=APP-080）｜APP-080 ⑤ 前置资产只读盘点与 §143–§146 证据链实算复核（{NOW}）

- **步骤 1–2**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，只读／未改／未提交）开工 SHA `b3ae9ea9…f392b937d5`／224 562 B／mtime 2026-11-06 21:40:34／**{BASE['n_headings']} 条**（APP-001..080 无缺号，`max_id={BASE['max_id']}`）；`last_ack: APP-080` 对齐 ⇒ **无编号大于 last_ack 的新条目，步骤 3 无条可执行**。租约 `acquire app` ⇒ exit 0（TOKEN b24ad7b3，**无 TAKEOVER**）。
- **APP-046② 不空转**：`results/app/_app324_app080_prereq_readonly_audit.json` ⇒ `verdict={ev['verdict']}`／`n_pass={ev['n_pass']}`／`n_fail={ev['n_fail']}`／`n_unknown={ev['n_unknown']}`／`counterproof_identified={ev['counterproof_identified']}`（12 条反证改的都是「被测的那个对象」，逐条明细见该 JSON 的 `counterproof` 字段）。纯 CPU 静态：`facts.machine_lock_present={str(f['machine_lock_present']).lower()}`／未推理／未调 MiniMax／未打包。`n_unknown=1` 是 **D5 三态**（见下），按「无法判定 ≠ 不合格」如实记录。
- 🔴 **本轮新结论（APP-080 ⑤ 前置资产定位，需 reviewer 复核）**：`facts.spk` ⇒ `KEEP_SPK_FILES`（从 `live_caption/v23_preset_only.py` 用 `ast.literal_eval` 现读，**不 import 被测模块**）共 **{len(spk['keep'])} 个**；真实 `Confucius4_LiveCaption_v2.2/app/asr_spk/` 仅 **{len(spk['pkg22_present'])}/5**（缺 `asr_spk_window.py`／`asr_runtime_switches.py`），而影子包 `shared/app067_shadow/app/asr_spk/` **{len(spk['shadow_present'])}/5 全在** ⇒ STATUS 头部「ASR 文件 3→5 随 v2.3」的待办**尚未并入任何包**。`facts.seg_w5` ⇒ 5 s 静态 seg IR `models/spk/pyannote_seg_3_0/fp16-w5/` 在**仓库与 v2.2 包内均不存在**（`pkg22_dir_exists=false`／`repo_dir_exists=false`），影子包内已落盘 **2 个文件**：`{shadow_bin['name']}` **{shadow_bin['bytes']} B**／SHA `{shadow_bin['sha256']}`、`{shadow_xml['name']}` **{shadow_xml['bytes']} B**／SHA `{shadow_xml['sha256']}`（合计 **{shadow_bin['bytes'] + shadow_xml['bytes']} B**）；ASR 源目录 `qwen3asr_06b/models/pyannote_seg/ov-fp16-w5/` 另 4 个文件。🔴 **D5 = UNKNOWN**：影子包 xml SHA `{seg['shadow_xml_sha256']}` 与 ASR 源 xml SHA `{seg['asr_src_xml_sha256']}` **不同**（`xml_differs=true`，源目录另有 `pyannote_seg_3_0_w5.xml.bak_before_path_scrub_20261105_085534`）⇒ **取哪一份 xml 须 reviewer 裁定，本轮不自行决定、不复制、不写包**。影子包仅作为「源资产已落盘」证据，**不是已交付**。
- **§143–§146 证据链实算复核（结果文件＋原始字段）**：`facts.sec146` ⇒ `verdict={s['verdict']}`／`n_pass={s['n_pass']}`／`n_fail={s['n_fail']}`／`counterproof_identified={s['counterproof_identified']}`／`total_anchors={s['total_anchors']}`／`pkg_v22_unique_anchors={s['pkg_v22_unique_anchors']}`／`pkg_v22_direct_patch_applicable={str(s['pkg_v22_direct_patch_applicable']).lower()}`，缺锚点恰为 `P03-checkbox`／`P04-hint`／`P05-startup`／`P08-onchange`，`pkg_v22_before == pkg_v22_after` ⇒ §146 结论全部复现。本轮**重新实算**：dev 三份源文件（`live_caption_app.py` {dev['live_caption/live_caption_app.py']['bytes']} B／`{dev['live_caption/live_caption_app.py']['sha256'][:12]}…`、`tts_service.py` {dev['live_caption/tts_service.py']['bytes']} B、`tts_worker.py` {dev['live_caption/tts_worker.py']['bytes']} B）与 §146 `facts.dev_sources` **逐字节一致**；v2.2 包内三份（`{pkg['live_caption_app.py']['bytes']}`／`{pkg['tts_service.py']['bytes']}`／`{pkg['tts_worker.py']['bytes']}` B）与 `facts.pkg_v22_before` **逐字节一致** ⇒ 「客户包这 3 个源文件一字节未动」有新实算支撑（**仅限这 3 个文件，不是全包**）；`live_caption/v23_preset_only.py`（{v23['live_caption/v23_preset_only.py']['bytes']} B／`{v23['live_caption/v23_preset_only.py']['sha256'][:12]}…`）与 `assert_pkg_clean.py`（{v23['live_caption/assert_pkg_clean.py']['bytes']} B）与 §145 `facts.app080_assets` 及 §143 产物表一致；§146 产物表 4 行与磁盘逐文件一致。
- **打包链路复核（§145 同口径）**：`facts.packaging_chain` ⇒ 扫描 **{pc['scanned']} 个文件**（`pack_v13.py` ＋ 22 个 `results/app/*build*.py`/`*stage*.py`，排除判据脚本自身），`total_refs={pc['total_refs']}` ⇒ **NOT_WIRED**；`pack_v13.py` **72 531 B**／SHA `2e7a232e…` 与 §145 登记一致 ⇒ 接入 `PKG_INCLUDE_FILES`（`app/v23_preset_only.py`＋`app/assert_pkg_clean.py`）**仍是 ⑤ 待办**，本轮未改打包脚本。
- **APP-077 清单复核（只读）**：`facts.bridge.v22_token_paths` ⇒ v2.2 包根 **`ext/bridge_token.txt` 仍 1 处**（`app/` 内 0 处；历史固定 token 违规**未修**，⑤ 新包须不带）；dev `live_caption/bridge_bootstrap.py` **{br['bootstrap']['bytes']} B**／SHA `{br['bootstrap']['sha256']}` 已落盘。⇒ **只写清单核实，不写「已修复／已交付」**。
- **git / 限额只读核查**：`facts.git` ⇒ `head={g['head']}`／`ahead={g['ahead']}`／`branch={g['branch']}`／`corrections_status='{g['corrections_status']}'`（reviewer 未提交，本轮只读）；`facts.status_header` ⇒ 写前 **{hdr['bytes']} B／{hdr['lines']} 行**／SHA `{hdr['sha256'][:12]}…`（余量仅 {40000 - hdr['bytes']} B）⇒ 按 APP-052④ 先压缩。
- ⛔ **停止点**：APP-075「需 Opus 复核」・APP-079「需 reviewer 复核」・APP-080 ⑤⑥「reviewer 复核通过后才通知用户」⇒ 未自行推进 ⑤⑥、**v2.3 不打包**；未打新版本目录与 zip／未改任何客户安装目录与 .lnk／未复制影子包资产／未建 `MACHINE_LOCK`（未占设备）／未在 CPU 跑推理测速／未调 MiniMax。**没落盘的一律不写「已交付」**。
- **写入纪律（APP-052④）**：**首版 42 844 B 超 40 000 B 限额被写前自检拦下（STATUS 一个字节未落盘）** ⇒ 二次压缩：§146 正文（{sec146.count(chr(10)) + 1} 行／{len(blk_b)} B／块 SHA256 `{blk_sha}`）整块逐字归档 ⇒ `status/archive/STATUS_APP_sec146_20261107.md`，§143 正文＋§144/§145 速查行（{mid.count(chr(10)) + 1} 行／{len(mid_b)} B／块 SHA256 `{mid_sha}`）整块逐字归档 ⇒ `status/archive/STATUS_APP_sec143_20261107.md`，两处原位各留 1 行速查；头部仅定点改 `更新时间`／`当前任务`／`已压缩` 3 行，`last_ack` 保持 APP-080；末尾只追加本章节；写前自检「反向还原==旧全文・两个归档件逐字命中・章节不减・LF 未破・≤40 000 B / ≤300 行」＋临时文件 `os.replace` 原子替换＋写后磁盘逐字节复核 ⇒ `results/app/_app325_write_status_sec147.json`。
- **纠偏文件收尾复核（步骤 4）**：SHA `{corr['sha256']}`／{corr['bytes']} B／{corr['mtime']}／**{corr['n_headings']} 条**（最大 APP-{corr['max_id']:03d}）⇒ {corr_note}
- **产物清单（写 STATUS 时磁盘实测，共 {len(arts)} 个文件）**：
| 文件 | mtime | 字节数 | SHA256 |
|---|---|---|---|
{art_rows}
- **git**：逐文件 `git add`（禁 `-A`）⇒ main 普通 push、不 force；不提交 `CORRECTIONS_APP.md`，不吞其它模块。
'''

    new = head_changed + quick2 + '\n' + quick + '\n' + sec147
    new_b = new.encode('utf-8')

    # ── 写前自检 ─────────────────────────────────────────────────────
    chk(b'\r\n' not in new_b, 'no_crlf', 'CRLF count=%d' % (new_b.count(b'\r\n'),))
    chk(len(new_b) <= LIMIT_BYTES, 'within_40000_bytes',
        'new_bytes=%d limit=%d' % (len(new_b), LIMIT_BYTES))
    chk(new_b.count(b'\n') <= LIMIT_LINES, 'within_300_lines',
        'new_lines=%d limit=%d' % (new_b.count(b'\n'), LIMIT_LINES))
    old_secs = re.findall(r'^## §\d+', old, re.M)
    new_secs = re.findall(r'^## §\d+', new, re.M)
    expected_secs = [x for x in old_secs
                     if x not in ('## §143', '## §146')] + ['## §147']
    chk(new_secs == expected_secs, 'sections_not_reduced_and_appended',
        'old=%s new=%s expected=%s' % (old_secs, new_secs, expected_secs))
    chk(blk_b in arc_b, 'verbatim_block_in_archive', 'block sha=%s' % (blk_sha,))
    chk(mid_b in arc2_b, 'verbatim_block2_in_archive', 'block sha=%s' % (mid_sha,))

    restored = new[:new.index('## §147 ')]
    tail = quick2 + '\n' + quick + '\n'
    chk(restored.endswith(tail), 'restore_quick_tail', 'tail matches')
    if restored.endswith(tail):
        restored = restored[:-len(tail)] + mid + sec146
    for o, n in reversed(hdr_changes):
        chk(restored.count(n) == 1, 'restore_header_unique',
            'new line count=%d' % (restored.count(n),))
        restored = restored.replace(n, o, 1)
    chk(restored.encode('utf-8') == old_b, 'reverse_restore_equals_old_fulltext',
        'restored=%d old=%d equal=%s' % (len(restored.encode('utf-8')),
                                         len(old_b), restored.encode('utf-8') == old_b))

    n_fail = sum(1 for c in checks if not c['ok'])
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    report = dict(tool='_app325_write_status_sec147', verdict=verdict,
                  n_checks=len(checks), n_fail=n_fail, checks=checks,
                  status_before=dict(bytes=len(old_b),
                                     lines=old_b.count(b'\n') + 1,
                                     sha256=sha(old_b)),
                  status_after_planned=dict(bytes=len(new_b),
                                            lines=new_b.count(b'\n') + 1,
                                            sha256=sha(new_b)),
                  archived_block=dict(file=os.path.relpath(ARCHIVE, ROOT).replace('\\', '/'),
                                      bytes=len(blk_b), lines=sec146.count('\n') + 1,
                                      sha256=blk_sha),
                  archived_block2=dict(file=os.path.relpath(ARCHIVE2, ROOT).replace('\\', '/'),
                                       bytes=len(mid_b), lines=mid.count('\n') + 1,
                                       sha256=mid_sha),
                  corrections_closing_recheck=corr,
                  corrections_equals_opening=corr_same,
                  artifacts=arts,
                  status_written=False)

    if verdict == 'PASS':
        tmp = STATUS + '.tmp_sec147'
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
                     ensure_ascii=True, indent=2))
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
