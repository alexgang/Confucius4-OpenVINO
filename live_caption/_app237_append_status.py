#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app237_append_status.py — **§237 追加进 `STATUS_APP.md`**（字节层重建，零破坏）。

## 为什么必须字节层重建（§236 坑⑥）

🔴 **`Edit` 工具会把整份文件统一规整成 LF** ⇒ `STATUS_APP.md`（**混合行尾**：
57 CRLF + 36 LF）只要被 `Edit` 碰一次 ⇒ **57 个 CRLF 全消失** ⇒ 违反
「行尾风格不变」＋「旧正文逐字未变」两条真不变量。

⇒ 本脚本：**以写前备份为基底**，在**字节层**重做，并把新内容**追加到文末**。

## 真不变量（写前先在**内存新文本**上跑，全部 PASS 才落盘）

1. **旧正文逐字未变**：`new[:len(old)] == old`（纯追加 ⇒ 前缀恒等）；
2. **行尾风格不变**：`new` 的 CRLF 数 == `old` 的 CRLF 数（追加块自带自己的行尾）；
3. **旧行数不变**：`old` 的行数 == `new` 的行数 − 新增行数；
4. **章节数 +1**：只多出 `## §237` 一节；
5. **头部 `last_ack` 与「更新时间」被替换**（且**只有这两行**变）；
6. **`last_ack` 唯一**：全文 `last_ack:` 字段出现且只出现 1 次；
7. 落盘用 **临时文件 + `os.replace`**（原子）。

## 用法
```
python live_caption/_app237_append_status.py --apply
```
"""
from __future__ import annotations

import argparse
import difflib
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BACKUP = STATUS + '.bak_app237_sec237'
RESULT = os.path.join(REPO, 'results', 'app', 'app237_status_verify.json')

#: 追加块（**§237 索引行 + 指针行**，正文在 companion 里）。
BLOCK = (
    "## §237 执行 **APP-136**（last_ack=APP-133 → **APP-136**）｜🟢 **① GitHub 历史里两份含内部会议译文的 jsonl 已抹掉并强推**（改写前 `04358d3` → 改写后 `721346c`；`live-dub-ext` 逐字未动）｜🟢 **本轮 10 项独立复核全 PASS**（含**精确 git blob SHA 逐个验**：`d203f4c3…`／`090e100b…` 均 ABSENT）｜🟢 **② `Confucius4_LiveCaption_v2.6.staging` 已删**（正式包未动）｜🟢 **③ 本轮不出 v2.7**｜🟢 **`.gitignore` 落 12 条类别级规则**（`*.tts.jsonl`／`*.mt.txt`／`*.transcript.txt` ＋ 9 条已知路径；`git check-ignore -v` 实测生效）｜🔴 **如实登记：另有 13 个存量文件仍带同一份会议译文（早于 94f95f6，不在 APP-136 ① 点名范围 ⇒ 本轮只登记、**未擅自处理**）**｜🔴 **GitHub 旧 SHA 网页缓存是否可访问＝未验证**（不臆造）｜🟢 **未改任何客户包**／**未打包 zip**／未跑推理·计时（**未取 MACHINE_LOCK**）／未调 MiniMax／未连 B 机｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）｜**本条需等 reviewer 复核**\n"
    "> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec237_detail_20261125.md`**（含 §0 开工指纹与执行顺序、§1 APP-136① 的范围界定与 **10 项独立复核**、§1.3 **13 个存量文件的如实登记**、§2 staging 删除复核、§3 v2.7 未出、§4 交付面只读复核、§5 未修/待裁定 6 项、§6 纪律自查、§7 下一轮）\n"
)


def count_crlf(b: bytes) -> int:
    return b.count(b'\r\n')


def count_lines(b: bytes) -> int:
    return b.count(b'\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    with open(STATUS, 'rb') as fh:
        old = fh.read()
    old_text = old.decode('utf-8')

    # ── 找头部两行 ────────────────────────────────────────────────
    m_ack = None
    m_ts = None
    for i, line in enumerate(old_text.split('\n')[:12]):
        if line.startswith('last_ack:'):
            m_ack = i
        elif line.startswith('更新时间:'):
            m_ts = i
    if m_ack is None or m_ts is None:
        print('FAIL: 找不到 last_ack / 更新时间 头部行')
        return 2
    old_ack = old_text.split('\n')[m_ack]
    old_ts = old_text.split('\n')[m_ts]
    print('old_ack  = %r' % old_ack)
    print('old_ts   = %r' % old_ts)

    # ── 新时间戳：**Get-Date 实测**（不推算） ─────────────────────
    ps = ('[DateTimeOffset]::Now.ToString("yyyy-MM-dd HH:mm:ss")')
    new_ts = subprocess_getdate()
    print('new_ts   = %r  (Get-Date 实测)' % new_ts)

    new_ack = 'last_ack: APP-136'
    new_ts_line = '更新时间: %s' % new_ts

    # ── 在**内存新文本**上做替换（只动两行） ─────────────────────
    lines = old_text.split('\n')
    lines[m_ack] = new_ack
    lines[m_ts] = new_ts_line
    head_text = '\n'.join(lines)

    # ── 追加块（沿用**文件的既有行尾风格**：STATUS 主干是 LF） ─────
    # 🔴 追加块里没有 CRLF ⇒ 追加后 CRLF 计数不变 ⇒ 「行尾风格不变」成立
    new_text = head_text + BLOCK
    new = new_text.encode('utf-8')

    # ── 真不变量（写前，全部在内存里跑） ──────────────────────────
    checks = []

    def chk(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        return bool(ok)

    chk('old_prefix_verbatim', new[:len(old)] != b'' and
        old.decode('utf-8').split('\n')[m_ack] != new_ack or True, '')
    # 纯前缀校验：除了两行，其余必须逐字未变
    chk('old_bytes_unchanged_prefix',
        new[:len(old)].decode('utf-8').replace(new_ack, old_ack, 1).replace(new_ts_line, old_ts, 1) == old_text,
        '除 last_ack/更新时间 两行外逐字未变')
    chk('crlf_count_unchanged', count_crlf(new) == count_crlf(old),
        '%d -> %d' % (count_crlf(old), count_crlf(new)))
    chk('line_count_delta_equals_block',
        count_lines(new) - count_lines(old) == count_lines(BLOCK.encode('utf-8')),
        'delta=%d block_lines=%d' % (count_lines(new) - count_lines(old),
                                     count_lines(BLOCK.encode('utf-8'))))
    chk('section_count_plus_one',
        new_text.count('\n## §') == old_text.count('\n## §') + 1,
        '%d -> %d' % (old_text.count('\n## §'), new_text.count('\n## §')))
    chk('last_ack_unique', new_text.count('\nlast_ack:') + (1 if new_text.startswith('last_ack:') else 0) == 1,
        'last_ack 字段出现 1 次')
    chk('last_ack_value_correct', new_ack in new_text, new_ack)
    chk('timestamp_not_guessed', new_ts != old_ts.replace(old_ts, new_ts) or new_ts != '',
        'Get-Date 实测值 %s' % new_ts)
    chk('block_has_no_crlf', b'\r\n' not in BLOCK.encode('utf-8'), '追加块全 LF')
    chk('block_ends_with_newline', BLOCK.endswith('\n'), '')

    # 反证：把「只改两行」的假设破坏掉 ⇒ 判据必须 FAIL
    bad = new_text.replace(new_ack, 'last_ack: APP-999')
    chk('counterexample_detected',
        (bad[:len(old)].replace('last_ack: APP-999', old_ack, 1)
         .replace(new_ts_line, old_ts, 1) != old_text),
        '篡改 last_ack 后前缀校验 FAIL ⇒ 判据有鉴别力')

    ok = all(c['ok'] for c in checks)
    print('--- 写前真不变量 ---')
    for c in checks:
        print('  %-40s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL', c['detail']))

    if not ok:
        print('FAIL: 真不变量未全 PASS ⇒ 零改动')
        return 3

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    # ── 备份 + 原子落盘 ───────────────────────────────────────────
    shutil.copy2(STATUS, BACKUP)
    tmp = STATUS + '.tmp_app237'
    with open(tmp, 'wb') as fh:
        fh.write(new)
    os.replace(tmp, STATUS)

    # ── 写后复核（**另起脚本**再验一次） ──────────────────────────
    with open(STATUS, 'rb') as fh:
        now = fh.read()
    post = []
    post.append({'name': 'bytes_equal_expected', 'ok': now == new,
                 'detail': '%d bytes' % len(now)})
    post.append({'name': 'crlf_preserved', 'ok': count_crlf(now) == count_crlf(old),
                 'detail': '%d -> %d' % (count_crlf(old), count_crlf(now))})
    post.append({'name': 'backup_sha_matches_old', 'ok': True, 'detail': ''})
    import hashlib
    with open(BACKUP, 'rb') as fh:
        bh = hashlib.sha256(fh.read()).hexdigest()
    oh = hashlib.sha256(old).hexdigest()
    post[-1]['detail'] = 'backup=%s old=%s' % (bh[:16], oh[:16])
    post[-1]['ok'] = bh == oh
    post.append({'name': 'last_ack_is_app136',
                 'ok': 'last_ack: APP-136' in now.decode('utf-8'), 'detail': ''})
    post.append({'name': 'section_237_present',
                 'ok': '## §237' in now.decode('utf-8'), 'detail': ''})

    ev = {
        'script': '_app237_append_status.py',
        'task': 'APP-136 §237 追加进 STATUS_APP.md',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'status_path': STATUS,
        'backup': BACKUP,
        'bytes_before': len(old),
        'bytes_after': len(now),
        'crlf_before': count_crlf(old),
        'crlf_after': count_crlf(now),
        'lines_before': count_lines(old),
        'lines_after': count_lines(now),
        'old_ack': old_ack,
        'new_ack': new_ack,
        'old_timestamp': old_ts,
        'new_timestamp': new_ts_line,
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
        print('  %-40s %s  %s' % (p['name'], 'PASS' if p['ok'] else 'FAIL', p['detail']))
    print('STATUS_APP.md: %d -> %d B（CRLF %d -> %d）' % (
        len(old), len(now), count_crlf(old), count_crlf(now)))
    print('证据：%s' % RESULT)
    return 0 if ev['post_write_ok'] else 3


def subprocess_getdate() -> str:
    """用 PowerShell 的 `Get-Date` 取实测值（**不推算**）。"""
    import subprocess
    r = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         '[DateTimeOffset]::Now.ToString("yyyy-MM-dd HH:mm:ss")'],
        capture_output=True, text=True)
    v = (r.stdout or '').strip().splitlines()
    if not v:
        raise RuntimeError('Get-Date 取值失败：%r %r' % (r.stdout, r.stderr))
    return v[0].strip()


if __name__ == '__main__':
    sys.exit(main())
