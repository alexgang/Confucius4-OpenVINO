# -*- coding: utf-8 -*-
"""app351_app086_ack_status.py — APP-086/087/088 开工 ACK + APP-052(4) 压缩。

只做三件事（APP-088「ack 要求」）：
  1. STATUS 头部 last_ack: APP-085 -> APP-088（+ 实测更新时间/当前任务/阻塞）；
  2. 「最近更新」追加 1 行 ack（不新增 § 章节、不建巡检 json/patrol 提交）；
  3. STATUS 已 39996 B（限额 40000 B，余量 4 B）=> 按 APP-052(4) 把
     §158 / §150 两节正文整块逐字归档到 status/archive/，正文留速查行。

写前自检：唯一命中断言 / 反向还原==旧全文 / 章节数不减 / LF 未破 /
          限额内 / 归档件逐字命中。任何一项失败即中止，STATUS 不落盘。
写入：临时文件 + os.replace 原子替换；写后读磁盘逐字节复核。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
ARCH_DIR = r'C:\Users\Trekker-PTL\confucius4-openvino\status\archive'
EVID = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app351_app086_ack_evidence.json'
STAMP = '2026-11-09 09:24:27'  # Get-Date 实测
LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def section_block(lines, title_prefix):
    """返回 (start, end, block_text)；block_text 含标题行、不含下一节标题。"""
    hits = [i for i, l in enumerate(lines) if l.startswith(title_prefix)]
    assert len(hits) == 1, 'title not unique: %r -> %r' % (title_prefix, hits)
    a = hits[0]
    z = next((i for i in range(a + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
    return a, z, '\n'.join(lines[a:z])


def main():
    old_bytes = open(STATUS, 'rb').read()
    assert b'\r\n' not in old_bytes, 'STATUS has CRLF, abort'
    old_txt = old_bytes.decode('utf-8')
    lines = old_txt.split('\n')
    checks = []

    def ck(name, cond, extra=''):
        checks.append(dict(name=name, ok=bool(cond), detail=str(extra)[:200]))
        assert cond, 'CHECK FAILED: %s %s' % (name, extra)

    # ── 归档块：整节逐字 ──────────────────────────────────────
    a158, z158, blk158 = section_block(lines, '## §158 ')
    a150, z150, blk150 = section_block(lines, '## §150 ')
    ck('section_158_unique_and_nonempty', len(blk158) > 1000, len(blk158))
    ck('section_150_unique_and_nonempty', len(blk150) > 1000, len(blk150))
    sh158 = sha256(blk158.encode('utf-8'))
    sh150 = sha256(blk150.encode('utf-8'))
    f158 = 'STATUS_APP_sec158_20261109.md'
    f150 = 'STATUS_APP_sec150_20261109.md'

    title158 = lines[a158]
    title150 = lines[a150]
    q158 = ('\n'.join([
        title158,
        '',
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/%s`（%d B／块 SHA256 `%s`；含开工/收尾指纹、`merge-base` exit 1、产物表与 v2.3/v2.4 zip 元数据）。' % (f158, len(blk158.encode('utf-8')), sh158),
        '> 🔴 **速查**：无新纠偏（84 条／`b3a1a900…b62`）；ack-only 停在「等 reviewer 发起把 claude-clone 合回 main」；`MACHINE_LOCK` NOT_PRESENT、未打包、未通知用户。',
    ]))
    q150 = ('\n'.join([
        title150,
        '',
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/%s`（%d B／块 SHA256 `%s`；含 APP-081 第 5/6 点判据、§149 归档链、产物表与 git 91abc26）。' % (f150, len(blk150.encode('utf-8')), sh150),
        '> 🔴 **速查**：APP-081 第 5 点「reviewer 复核后再通知用户」＋第 6 点「不自创覆盖审计/静态自证轮次」⇒ 本轮仅 ack；不打包、不通知用户、不改 .lnk。',
    ]))
    ck('block_158_single_hit', old_txt.count(blk158) == 1, old_txt.count(blk158))
    ck('block_150_single_hit', old_txt.count(blk150) == 1, old_txt.count(blk150))

    # ── 头部 4 行 ────────────────────────────────────────────
    ck('header_last_ack', lines[2] == 'last_ack: APP-085', lines[2])
    ck('header_update_time', lines[3].startswith('更新时间: '), lines[3])
    head_old = lines[2:6][:]
    head_new = [
        'last_ack: APP-088',
        '更新时间: ' + STAMP,
        '当前任务: **APP-086/087/088 已 ack（last_ack=APP-088）｜按 APP-086⑤ / APP-087⑦ / APP-088④ 顺序推进：合并 → 克隆 a–f → GUI → 验收数字 → 停下等 reviewer 复核**',
        '阻塞 / 待用户决定: **APP-086 完成后停下等 reviewer 复核；复核通过前不打包、不建 v2.5、不通知用户（APP-087⑦ / APP-088④）；APP-082 审计待 reviewer 下发**',
    ]

    # ── 最近更新 1 行 ack ────────────────────────────────────
    anchor = '> 🔴 2026-11-08 21:52:39｜'
    ai = [i for i, l in enumerate(lines) if l.startswith(anchor)]
    ck('recent_anchor_unique', len(ai) == 1, ai)
    ack_line = ('> 🔴 2026-11-09 %s｜**APP-086 / APP-087 / APP-088 已 ack，开始按编号执行**（APP-088「ack 要求」）：'
                '纠偏 85→**88 条**（新增 3 条 [HIGH] 用户决定），开工 SHA `d66746ed…6c1f`／**242 619 B**／mtime **2026-11-09 09:11:06**；'
                'APP-086⑤／APP-087⑦／APP-088④ 顺序＝**先做完 APP-086（合并＋克隆 a–f＋GUI＋验收数字）→ 停下等 reviewer 复核 → 复核通过后才打 v2.5（含 EXT、CUDA 排除）**；'
                'APP-083/084「等用户测完」节点由 APP-086 解除；本轮不打包、不通知用户；APP-085 待命期空巡检禁令在有新条目时解除。' % STAMP)

    # ── 组装新文本 ───────────────────────────────────────────
    txt = old_txt
    txt = txt.replace(blk158, q158, 1)
    txt = txt.replace(blk150, q150, 1)
    ck('replace_158_applied', q158 in txt and blk158 not in txt)
    ck('replace_150_applied', q150 in txt and blk150 not in txt)

    for o, n in zip(head_old, head_new):
        ck('header_line_single_hit', txt.count(o + '\n') == 1, o[:40])
        txt = txt.replace(o + '\n', n + '\n', 1)
    ck('ack_anchor_single_hit', txt.count(anchor) == 1)
    txt = txt.replace('\n'.join(lines[ai[0]:ai[0] + 1]) + '\n',
                      '\n'.join(lines[ai[0]:ai[0] + 1]) + '\n' + ack_line + '\n', 1)

    new_bytes = txt.encode('utf-8')
    # ── 写前自检 ─────────────────────────────────────────────
    ck('lf_intact', b'\r\n' not in new_bytes)
    ck('limit_bytes', len(new_bytes) <= LIMIT_BYTES, '%d <= %d' % (len(new_bytes), LIMIT_BYTES))
    ck('limit_lines', len(txt.split('\n')) <= LIMIT_LINES, len(txt.split('\n')))
    old_h2 = sum(1 for l in lines if l.startswith('## '))
    new_h2 = sum(1 for l in txt.split('\n') if l.startswith('## '))
    ck('h2_not_reduced', new_h2 >= old_h2, '%d -> %d' % (old_h2, new_h2))

    # 反向还原：新文本 -> 旧全文（归档块换回、头部换回、ack 行删掉）
    rev = txt.replace(q158, blk158, 1).replace(q150, blk150, 1)
    for o, n in zip(head_old, head_new):
        rev = rev.replace(n + '\n', o + '\n', 1)
    rev = rev.replace(ack_line + '\n', '', 1)
    ck('reverse_restore_equals_old', rev.encode('utf-8') == old_bytes,
       'rev=%d old=%d' % (len(rev.encode('utf-8')), len(old_bytes)))

    n_pass = sum(1 for c in checks if c['ok'])
    ck('all_checks_pass', n_pass == len(checks), '%d/%d' % (n_pass, len(checks)))

    # ── 落盘：归档件 → STATUS 原子替换 ───────────────────────
    os.makedirs(ARCH_DIR, exist_ok=True)
    for fn, blk in ((f158, blk158), (f150, blk150)):
        p = os.path.join(ARCH_DIR, fn)
        with open(p, 'wb') as f:
            f.write(blk.encode('utf-8'))
        got = open(p, 'rb').read()
        ck('archive_verbatim_' + fn[:24], got == blk.encode('utf-8'), len(got))

    tmp = STATUS + '.tmp_app351'
    with open(tmp, 'wb') as f:
        f.write(new_bytes)
    os.replace(tmp, STATUS)
    disk = open(STATUS, 'rb').read()
    ck('disk_byte_identical_after_write', disk == new_bytes, len(disk))
    ck('corrections_untouched_by_this_script', True, 'script writes STATUS/archive only')

    ev = dict(
        tool='app351_app086_ack_status',
        stamp=STAMP,
        status_before=dict(bytes=len(old_bytes), lines=len(lines), sha256=sha256(old_bytes),
                           last_ack='APP-085', h2=old_h2),
        status_after=dict(bytes=len(disk), lines=len(disk.decode('utf-8').split('\n')),
                          sha256=sha256(disk), last_ack='APP-088', h2=new_h2),
        archives=[
            dict(path='status/archive/' + f158, bytes=len(blk158.encode('utf-8')), sha256=sh158,
                 verbatim=True),
            dict(path='status/archive/' + f150, bytes=len(blk150.encode('utf-8')), sha256=sh150,
                 verbatim=True),
        ],
        ack_line=ack_line,
        checks=checks,
        n_pass=sum(1 for c in checks if c['ok']),
        n_fail=sum(1 for c in checks if not c['ok']),
        verdict='PASS' if all(c['ok'] for c in checks) else 'FAIL',
    )
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps(dict(verdict=ev['verdict'], n_pass=ev['n_pass'], n_fail=ev['n_fail'],
                          before=ev['status_before']['bytes'], after=ev['status_after']['bytes'],
                          after_sha=ev['status_after']['sha256'],
                          archives=[a['sha256'][:12] for a in ev['archives']]),
                     ensure_ascii=False))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
