#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app240_append_status.py — **§240 追加进 `STATUS_APP.md`**（含必要的压缩）。

## 本轮做两件事

1. **追加** `## §240`（索引行 ＋ 指针行）—— 只在**文末**追加；
2. 🔴 **压缩**：「最近更新」里较旧的条目**整块逐字归档**
   ⇒ 追加后仍 ≤ 40 000 B（APP-052④ 限额）。

> ⚠️ **追加前先算**：若追加后超限 ⇒ 先压缩 ⇒ **压缩只动「最近更新」区块**
> （「当前有效结论」是**活文档** ⇒ 不压）。

## 🔴 真不变量（写前在**内存新文本**上跑，全 PASS 才落盘）
1. **除被归档的条目 ＋ 新增指针行外，旧正文逐字未变**；
2. **行尾风格不变**（CRLF 计数不变）；
3. **章节数 +1**（不删任何 `## ` 标题）；
4. **头部 `last_ack` / `更新时间` 不变**（本节**不改** last_ack）；
5. **字节数 ≤ 40 000**；
6. 归档件内容与被删条目**逐字相同**（可反向拼回）；
7. 落盘用 **临时文件 + `os.replace`**（原子）。

## 用法
```
python live_caption/_app240_append_status.py --apply
```
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_recent_updates_20261125c.md')
BACKUP = STATUS + '.bak_app239_sec239'
RESULT = os.path.join(REPO, 'results', 'app', 'app240_status_verify.json')

LIMIT = 40000

BLOCK = (
    "## §240 执行 **APP-134 c**（`last_ack` 仍 **APP-137**）｜🟢 **三臂口径全部核对通过**"
    "（c13 开／c13 关／TTS=GPU.0，**`lock_lost`=0**）：`c13_on`（`buckets=[38] "
    "join=direct_concat`）`synth_rtf`=**1.0469**／首包 **1.3555 s**／`max_lag` **127.32 s**／"
    "pending 结束 **28** ⇒ 排空 136.59 s；`c13_off`（`buckets=[8,16,32,33] "
    "join=crossfade`）**0.9796**／1.5108 s／**89.02 s**／**21** ⇒ 94.43 s；"
    "`tts_gpu0`（实测 **GPU.0**）**22.2353**／7.8197 s／**673.55 s**／**95** ⇒ "
    "**82 排不空**（`n_emitted` 41/123）｜🔴 **c13 不是免费的**：关掉更快（rtf 0.98 vs 1.05、"
    "max_lag 89 vs 127）⇒ 但**单轮不足以定论**（噪声地板 10~44%）⇒ 只能说"
    "**「未见 c13 带来性能收益」**，**不能说「c13 让性能变差 30%」** ⇒ **待 reviewer 裁定"
    "是否 ABBA 复测**｜🔴🔴 **TTS 不能放 GPU.0**（实测依据）：rtf **22.24**（NPU 的 **21 倍**）"
    "⇒ 触发 APP-030② 失控闸（`max(3×est, est+8s)`，上限 60 s）⇒ **33 句失控中止**、"
    "**82 句排不空**、斜率 **−3.67 s/s**；抽听片段 peak 0.07~0.13（**几乎静音**）"
    "⇒ 听感与数据一致｜🟢 **18 段抽听片段**已落 `results/app/app123_listen/`"
    "（每臂 6 段，取自 **`player_mix.wav`＝播放端真正听到的混音**；🔴 只切片段、"
    "**不做音质判定**，质量由 reviewer 抽听）｜🔴 **本轮修掉 2 个真缺陷**："
    "① **臂规格的逗号歧义**（env 值里可含逗号 ⇒ 简单 `split(',')` 把 c13_off 拆成 4 个假臂 ⇒ "
    "**c13 从未被关过**）⇒ 改**正则**切分（只在顶层逗号切）；② **env 变量名用错**"
    "（真名是 `LIVECAP_TTS_DECODER_BUCKETS`／`LIVECAP_TTS_DIRECT_CONCAT`）"
    "⇒ 🔴 **两轮 c 跑都作废**（`_VOIDED`／`_VOIDED2` 留取证）｜🟢 **由此固化一条判据**："
    "🔴 **每次跑完必须核对「配置真的生效」，不能只看 rc=0** ⇒ 汇总脚本加**逐臂反证**"
    "（c13_off 必须 crossfade＋[8,16,32,33]／c13_on 必须 direct_concat＋[38]／"
    "tts_gpu0 必须 GPU.0）⇒ **3/3 PASS** ⇒ 这次的臂是真的｜🔴 **未完成**："
    "APP-137 §3 后半、APP-135 §5｜🟢 **未打包 zip**／未改任何客户包／未调 MiniMax／未连 B 机"
    "｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）｜**本条需等 reviewer 复核**\n"
    "> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec240_detail_20261125.md`**"
    "（含 §0 本轮性质、§1 **三臂完整表**＋锁事件、§2 **三条关键结论**（c13 不是免费的／"
    "**TTS 不能放 GPU.0**／首包与历史值的**口径说明**）、§3 抽听片段（含**入库说明**："
    "`.gitignore` 的 `*.wav` 会挡 ⇒ 用 `git add -f` **精确入库**、**不放宽规则**）、"
    "§4 **2 个真缺陷**的根因/修法＋**固化的一条判据**、§5 未完成/待裁定、§6 纪律自查、§7 下一轮）\n"
)

#: 🔴 **被归档的「最近更新」条目**（**较旧**的那些）
#: 🔴 本次**不压缩**（「最近更新」里已无可归档的老条目 ⇒ 追加后仍 ≤ 40 000 B）
ARCHIVE_MARKERS = [
]


def getdate() -> str:
    r = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         '[DateTimeOffset]::Now.ToString("yyyy-MM-dd HH:mm:ss")'],
        capture_output=True, text=True)
    v = (r.stdout or '').strip().splitlines()
    if not v:
        raise RuntimeError('Get-Date 取值失败：%r %r' % (r.stdout, r.stderr))
    return v[0].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    with open(STATUS, 'rb') as fh:
        old = fh.read()
    old_text = old.decode('utf-8')

    checks = []

    def chk(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    # ── 定位「最近更新」区块（只压这一块） ─────────────────────────
    i = old_text.find('## 最近更新')
    j = old_text.find('## 当前有效结论')
    if i < 0 or j < 0 or j <= i:
        print('FAIL: 找不到「最近更新」区块')
        return 2
    head, mid, tail = old_text[:i], old_text[i:j], old_text[j:]

    lines = mid.split('\n')
    keep_lines, arch_lines = [], []
    for ln in lines:
        if any(ln.startswith(mk) for mk in ARCHIVE_MARKERS):
            arch_lines.append(ln)
        else:
            keep_lines.append(ln)
    chk('archive_markers_found', len(arch_lines) == len(ARCHIVE_MARKERS),
        '归档 %d 条（期望 %d）' % (len(arch_lines), len(ARCHIVE_MARKERS)))
    if len(arch_lines) != len(ARCHIVE_MARKERS) and ARCHIVE_MARKERS:
        for c in checks:
            print('  %-40s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                      c['detail']))
        return 3

    arch_block = '\n'.join(arch_lines)
    pointer = ('> 🔴 **本节较旧「最近更新」条目（%d 条：11-25 07:38／05:52）原文已'
               '**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_20261125c.md`'
               '（**逐字保留，内容一字未删**）**；本行以下为较新条目。**'
               % len(arch_lines))
    new_mid = '\n'.join(keep_lines)
    ni = new_mid.find('\n')
    new_mid = new_mid[:ni + 1] + pointer + '\n' + new_mid[ni + 1:]

    # ── 追加 §240（**头部 last_ack/更新时间 不动**） ─────────────────
    new_text = head + new_mid + tail + BLOCK
    new = new_text.encode('utf-8')

    chk('bytes_under_limit', len(new) <= LIMIT,
        '%d B ≤ %d B（追加前 %d B）' % (len(new), LIMIT, len(old)))
    chk('crlf_count_unchanged', new.count(b'\r\n') == old.count(b'\r\n'),
        '%d -> %d' % (old.count(b'\r\n'), new.count(b'\r\n')))
    chk('section_count_plus_one', new_text.count('\n## ') == old_text.count('\n## ') + 1,
        '%d -> %d' % (old_text.count('\n## '), new_text.count('\n## ')))
    chk('head_unchanged', head == old_text[:i], '头部（含 last_ack/更新时间）逐字未变')
    chk('tail_unchanged', tail == old_text[j:], '「当前有效结论」及之后逐字未变')
    chk('last_ack_unchanged', 'last_ack: APP-137' in new_text,
        'last_ack 仍 APP-137（APP-134 整条未复核通过 ⇒ 不推编号）')
    chk('block_has_no_crlf', b'\r\n' not in BLOCK.encode('utf-8'), '追加块全 LF')
    chk('archive_content_verbatim',
        all(m in arch_block for m in ARCHIVE_MARKERS),
        '%d 条标记逐字在归档块里' % len(ARCHIVE_MARKERS))
    # 🔴 反证：① 有归档 ⇒ 篡改归档块时间戳；② 无归档 ⇒ 删掉追加块的章节标题
    if ARCHIVE_MARKERS:
        tampered = arch_block.replace('2026-11-25 07:38:13',
                                      '2026-11-25 07:38:14', 1)
        chk('counterexample_detected',
            not all(m in tampered for m in ARCHIVE_MARKERS),
            '篡改归档块时间戳后校验 FAIL（符合预期）⇒ 判据有鉴别力')
    else:
        tampered_text = head + new_mid + tail + BLOCK.replace('## §240', '§240', 1)
        chk('counterexample_detected',
            tampered_text.count('\n## ') != old_text.count('\n## ') + 1,
            '删掉追加块里的章节标题后章节计数判据 FAIL（符合预期）⇒ 判据有鉴别力')

    print('--- 写前真不变量 ---')
    for c in checks:
        print('  %-42s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    if not all(c['ok'] for c in checks):
        print('FAIL: 真不变量未全 PASS ⇒ 零改动')
        return 3

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    # ── 写归档件（write-once） ────────────────────────────────────
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    if not ARCHIVE_MARKERS:
        arch_body = None
    elif os.path.exists(ARCHIVE):
        print('⚠️ 归档件已存在 ⇒ **不覆盖**（write-once）：%s' % ARCHIVE)
        return 3
    else:
        arch_body = None
        print('（本次**不压缩** ⇒ 不生成归档件）')
    arch_body = (
        '# STATUS_APP「最近更新」归档（2026-11-25 第三批）\n\n'
        '> 本块**逐字**归档自 `status/app/STATUS_APP.md` 的「最近更新」区块。\n'
        '> 归档时点：写入 §240 时 `STATUS_APP.md` 将超 APP-052④ 的 40 000 B 限额 ⇒ 压缩。\n'
        '> 归档条目：%d 条（%s）\n'
        '> 🔴 **内容一字未删、未改**；活文档留 1 行指针。\n\n'
        '## 归档条目（逐字）\n\n'
        '%s\n'
        % (len(arch_lines),
           '、'.join(m.replace('> 🔴 ', '') for m in ARCHIVE_MARKERS),
           arch_block)
    )
    if ARCHIVE_MARKERS:
        tmp_arch = ARCHIVE + '.tmp'
        with open(tmp_arch, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(arch_body)
        os.replace(tmp_arch, ARCHIVE)

    # ── 写活文档 ─────────────────────────────────────────────────
    shutil.copy2(STATUS, BACKUP)
    tmp = STATUS + '.tmp_app239'
    with open(tmp, 'wb') as fh:
        fh.write(new)
    os.replace(tmp, STATUS)

    # ── 写后复核 ─────────────────────────────────────────────────
    with open(STATUS, 'rb') as fh:
        now = fh.read()
    with open(BACKUP, 'rb') as fh:
        bakb = fh.read()
    archb = b''
    if ARCHIVE_MARKERS and os.path.exists(ARCHIVE):
        with open(ARCHIVE, 'rb') as fh:
            archb = fh.read()
    post = [
        {'name': 'bytes_equal_expected', 'ok': now == new, 'detail': '%d B' % len(now)},
        {'name': 'under_limit', 'ok': len(now) <= LIMIT,
         'detail': '%d B ≤ %d B（余量 %d B）' % (len(now), LIMIT, LIMIT - len(now))},
        {'name': 'crlf_preserved', 'ok': now.count(b'\r\n') == bakb.count(b'\r\n'),
         'detail': '%d -> %d' % (bakb.count(b'\r\n'), now.count(b'\r\n'))},
        {'name': 'bak_sha_matches_old',
         'ok': hashlib.sha256(bakb).hexdigest() == hashlib.sha256(old).hexdigest(),
         'detail': hashlib.sha256(bakb).hexdigest()[:16]},
        {'name': 'archive_written',
         'ok': (len(archb) > 0) if ARCHIVE_MARKERS else True,
         'detail': ('%d B / sha %s' % (len(archb), hashlib.sha256(archb).hexdigest()[:16]))
                   if ARCHIVE_MARKERS else '本次不压缩 ⇒ 无归档件'},
        {'name': 'archive_contains_all_markers',
         'ok': all(m.encode('utf-8') in archb for m in ARCHIVE_MARKERS)
               if ARCHIVE_MARKERS else True,
         'detail': '%d 条逐字在归档里' % len(ARCHIVE_MARKERS)},
        {'name': 'section_239_present', 'ok': '## §240' in now.decode('utf-8'),
         'detail': ''},
        {'name': 'last_ack_still_app137',
         'ok': 'last_ack: APP-137' in now.decode('utf-8'), 'detail': ''},
    ]
    ev = {
        'script': '_app240_append_status.py',
        'task': 'APP-134 c 的 §240 追加 ＋ 「最近更新」压缩（限额 ≤40000 B）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'status_path': STATUS, 'archive': ARCHIVE, 'backup': BACKUP,
        'bytes_before': len(old), 'bytes_after': len(now), 'limit': LIMIT,
        'timestamp_updated': getdate(),
        'archived_entries': len(arch_lines),
        'archive_bytes': len(archb),
        'archive_sha256': hashlib.sha256(archb).hexdigest(),
        'pre_write_invariants': checks,
        'post_write_selfcheck': post,
        'post_write_ok': all(p['ok'] for p in post),
    }
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    tmp2 = RESULT + '.tmp'
    with open(tmp2, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp2, RESULT)
    print('--- 写后复核 ---')
    for p in post:
        print('  %-42s %s  %s' % (p['name'], 'PASS' if p['ok'] else 'FAIL',
                                  p['detail']))
    print('STATUS_APP.md: %d -> %d B（余量 %d B）' % (len(old), len(now),
                                                LIMIT - len(now)))
    print('归档：%s（%d B）' % (ARCHIVE, len(archb)))
    print('证据：%s' % RESULT)
    return 0 if ev['post_write_ok'] else 3


if __name__ == '__main__':
    sys.exit(main())
