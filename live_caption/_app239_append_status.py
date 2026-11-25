#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app239_append_status.py — **§239 追加进 `STATUS_APP.md`**（含必要的压缩）。

## 本轮做两件事

1. **追加** `## §239`（索引行 ＋ 指针行）—— 只在**文末**追加；
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
python live_caption/_app239_append_status.py --apply
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
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_recent_updates_20261125b.md')
BACKUP = STATUS + '.bak_app239_sec239'
RESULT = os.path.join(REPO, 'results', 'app', 'app239_status_verify.json')

LIMIT = 40000

BLOCK = (
    "## §239 执行 **APP-134 b**（`last_ack` 仍 **APP-137**）｜🟢 **ABBA 四臂全 PASS**"
    "（on→off→off→on，**全 rc=0／`lock_lost`=0**）：噪声地板（同配置两次之差）"
    "p50 **10.28%**／p90 **21.53%**／max_lag **43.95%**；配置效应（守卫的影响）"
    "p50 **5.89%**／p90 **4.08%**／max_lag **18.73%** ⇒ **三项都落在噪声地板内**"
    "⇒ **未见「NaN 守卫」导致变差**｜🔴🔴 **但 reviewer 的「≤5%」判据本轮不可达**"
    "（噪声地板本身就 >5%）⇒ **本轮测不出「≤5%」的结论** ⇒ 如实登记，"
    "**不把「在噪声内」写成「已证明 ≤5%」**｜🟢 **噪声不是外部负载造成的**"
    "（四臂 ASR 加载 10.0–11.1 s，拥挤度一致）⇒ 噪声来自**运行自身随机性**"
    "（10 分钟连续负载下 NPU 共享/热态/累积排压）｜🟢 **影子包**（`models/`/`python/`/`ext/` "
    "走 **Windows 目录联接 ⇒ 零拷贝**，`app/` 真拷贝 ⇒ **只 ~2 MB**）＋ "
    "`guard_off` 用 **21f7c39 之前的 tts_engine**（reviewer 明文允许）"
    "⇒ 🔴 **真包 `app/tts_engine.py` 逐字未动**（`bbbc166a…` vs 影子 `224c05bc…`）"
    "｜🔴 **本轮修掉 3 个真缺陷**：① **keepalive ping 超时**（桥接单线程 asyncio 在 NPU "
    "合成段要 10–16 s ⇒ 客户端默认 20 s ping 超时直接 1011 断连、**10 分钟臂全丢**）"
    "⇒ 改 `ping_interval=None`（工具自己轮询 stats 兼作心跳）＋ 排空循环捕获断连并记 "
    "`drain.disconnected`；② e2e 驱动器从 PowerShell 改写成 **Python**（本机 "
    "`Path`/`PATH`/`path` 三键并存 ⇒ `Process.Start` 撞「字典关键字重复」）；"
    "③ 🔴🔴 **ABBA 四臂用了重复臂名 ⇒ 数据互相覆盖**（arm2/arm3 写同一个目录 ⇒ "
    "该轮**整体作废**，目录改名 `..._VOIDED` 留取证）⇒ 臂目录名改 **臂名_序号**、"
    "配置名写进 `_summary.json` 的 `arm_config`、分析脚本**分组一律读 arm_config**"
    "｜🔴 **未完成**：APP-134 c、APP-137 §3 后半、APP-135 §5"
    "｜🟢 **未打包 zip**／未改任何客户包／未调 MiniMax／未连 B 机"
    "｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）｜**本条需等 reviewer 复核**\n"
    "> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec239_detail_20261125.md`**"
    "（含 §0 本轮性质、§1 **3 个真缺陷**的根因/修法/复核、§2 影子包做法与**四臂实测表**"
    "（含 reviewer 要的 **cp 自检数字**）＋ §2.3 **诚实标注的结论**、§3 未完成/待裁定 5 项、"
    "§4 纪律自查、§5 下一轮）\n"
)

#: 🔴 **被归档的「最近更新」条目**（**较旧**的那些）
ARCHIVE_MARKERS = [
    '> 🔴 2026-11-25 07:38:13',
    '> 🔴 2026-11-25 05:52:38',
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
    if len(arch_lines) != len(ARCHIVE_MARKERS):
        for c in checks:
            print('  %-40s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                      c['detail']))
        return 3

    arch_block = '\n'.join(arch_lines)
    pointer = ('> 🔴 **本节较旧「最近更新」条目（%d 条：11-25 07:38／05:52）原文已'
               '**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_20261125b.md`'
               '（**逐字保留，内容一字未删**）**；本行以下为较新条目。**'
               % len(arch_lines))
    new_mid = '\n'.join(keep_lines)
    ni = new_mid.find('\n')
    new_mid = new_mid[:ni + 1] + pointer + '\n' + new_mid[ni + 1:]

    # ── 追加 §239（**头部 last_ack/更新时间 不动**） ─────────────────
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
    # 🔴 反证：篡改归档块里某条时间戳 ⇒ 校验必须 FAIL
    tampered = arch_block.replace('2026-11-25 07:38:13', '2026-11-25 07:38:14', 1)
    chk('counterexample_detected',
        not all(m in tampered for m in ARCHIVE_MARKERS),
        '篡改归档块时间戳后校验 FAIL（符合预期）⇒ 判据有鉴别力')

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
    if os.path.exists(ARCHIVE):
        print('⚠️ 归档件已存在 ⇒ **不覆盖**（write-once）：%s' % ARCHIVE)
        return 3
    arch_body = (
        '# STATUS_APP「最近更新」归档（2026-11-25 第二批）\n\n'
        '> 本块**逐字**归档自 `status/app/STATUS_APP.md` 的「最近更新」区块。\n'
        '> 归档时点：写入 §239 时 `STATUS_APP.md` 将超 APP-052④ 的 40 000 B 限额 ⇒ 压缩。\n'
        '> 归档条目：%d 条（%s）\n'
        '> 🔴 **内容一字未删、未改**；活文档留 1 行指针。\n\n'
        '## 归档条目（逐字）\n\n'
        '%s\n'
        % (len(arch_lines),
           '、'.join(m.replace('> 🔴 ', '') for m in ARCHIVE_MARKERS),
           arch_block)
    )
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
        {'name': 'archive_written', 'ok': len(archb) > 0,
         'detail': '%d B / sha %s' % (len(archb), hashlib.sha256(archb).hexdigest()[:16])},
        {'name': 'archive_contains_all_markers',
         'ok': all(m.encode('utf-8') in archb for m in ARCHIVE_MARKERS),
         'detail': '%d 条逐字在归档里' % len(ARCHIVE_MARKERS)},
        {'name': 'section_239_present', 'ok': '## §239' in now.decode('utf-8'),
         'detail': ''},
        {'name': 'last_ack_still_app137',
         'ok': 'last_ack: APP-137' in now.decode('utf-8'), 'detail': ''},
    ]
    ev = {
        'script': '_app239_append_status.py',
        'task': 'APP-134 b 的 §239 追加 ＋ 「最近更新」压缩（限额 ≤40000 B）',
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
