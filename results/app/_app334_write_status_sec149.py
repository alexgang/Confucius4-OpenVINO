#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app334 — 写 STATUS_APP §149（APP-081）：头部定点替换 + 末尾只追加。

纪律（APP-052④ / APP-055 / 用户指令）：
  * 头部只改 4 行：`last_ack` / `更新时间` / `当前任务` / `阻塞 / 待用户决定`
    （APP-081 第 2 点：作废旧「APP-075 未闭环 ⇒ v2.3 不打包」段，重写为 APP-080 进度）；
  * 末尾**只追加** §149 章节；旧 §N 章节正文一字不改；
  * 写前自检：旧正文逐字未变・章节数不减・LF 未破・≤40 000 B / ≤300 行；
  * 临时文件 + os.replace 原子替换 + 写后磁盘逐字节复核；
  * 章节正文来自 `results/app/_app334_sec149_body.md`（由本轮实测数据填写）。
用法： python _app334_write_status_sec149.py --time "2026-11-07 HH:MM:SS"
      （--time 必须由 PowerShell `Get-Date -Format` 实测取得，禁止推算）
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BODY = os.path.join(HERE, '_app334_sec149_body.md')
OUT = os.path.join(HERE, '_app334_write_status_sec149.json')

NEW_HEAD = {
    'last_ack:': 'last_ack: APP-081',
    '更新时间:': None,          # --time 注入
    '当前任务:': (
        '当前任务: **§149 执行 APP-081（last_ack=APP-081）｜v2.3 已按「只交付预设音色」'
        '打新目录＋新 zip（不动 v2.0/2.1/2.2）；闸门回归 18/0・反证 3/3；'
        '建包 14 463→14 460 文件（剔除 9 违规＋新增 6）・18 锚点补丁全通过・'
        '洁净度 0 违规；⑥ 验收：zip SHA／干净目录 --check／GUI 100%+150%／'
        'CLI（r2 重跑 70 句零段 0）均 PASS，黑名单三态 UNKNOWN（1 项口径歧义待裁定），'
        'ASR WER=null 待 reviewer；原始结果文件与产物清单见 §149**'),
    '阻塞 / 待用户决定:': (
        '阻塞 / 待用户决定: APP-081 第 2 点已作废旧的「APP-075 未闭环 BLOCKING / 需 Opus 复核 / '
        'v2.3 不打包」整段——APP-071/075/079 是克隆修复，APP-080 明文转后续版本、'
        'v2.3 不为克隆占设备，与 v2.3 无关。当前节点 = **reviewer 复核 §149 的 '
        '⑥ 全套原始结果文件（自算 zip SHA、抽查 zip 内容、看 100%/150% 截图）'
        '⇒ 复核通过后才由 reviewer 通知用户**；本轮不改桌面 .lnk、不通知用户。'
        'D5 已按 APP-081 第 3 点裁定取 dev 当前 fp16-w5（xml SHA 见 §149），不再问 reviewer。'),
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--time', required=True)
    a = ap.parse_args()
    NEW_HEAD['更新时间:'] = '更新时间: ' + a.time

    raw = open(STATUS, 'rb').read()
    old_text = raw.decode('utf-8')
    old_lines = old_text.split('\n')
    body = open(BODY, encoding='utf-8').read().rstrip('\n')
    assert body.startswith('## §149'), '§149 正文必须以 ## §149 开头'
    assert old_text.endswith('\n'), 'STATUS 必须以 LF 结尾'

    # ① 头部定点替换（按前缀唯一命中）
    head_changes, new_lines = [], []
    for ln in old_lines:
        key = next((k for k in NEW_HEAD if ln.startswith(k)), None)
        if key:
            assert sum(1 for x in old_lines if x.startswith(key)) == 1, \
                '头部锚点非唯一：%s' % key
            new_lines.append(NEW_HEAD[key])
            head_changes.append({'key': key, 'old': ln[:80],
                                 'new': NEW_HEAD[key][:80]})
        else:
            new_lines.append(ln)
    assert len(head_changes) == 4, '头部应改 4 行，实际 %d' % len(head_changes)

    # ② APP-052④ 压缩：§148 正文整块逐字归档，原位留 1 行速查
    head_before_archive = '\n'.join(new_lines)
    idx = next((i for i, l in enumerate(new_lines) if l.startswith('## §148')),
               None)
    assert idx is not None, '未找到 §148 章节'
    block_lines = list(new_lines[idx:])
    while block_lines and block_lines[-1] == '':
        block_lines.pop()
    block = '\n'.join(block_lines)
    block_bytes = block.encode('utf-8')
    block_sha = sha(block_bytes)
    archive_rel = 'status/archive/STATUS_APP_sec148_20261107.md'
    archive_abs = os.path.join(REPO, archive_rel)
    archive_txt = (
        '# 归档：STATUS_APP §148 正文（逐字保留，APP-052④）\n\n'
        '> 归档时间：%s；块 SHA256 `%s`；块字节数 %d；块行数 %d。\n'
        '> 原文自下一行起**一字未改**，用于反向还原与逐字命中核验。\n\n'
        '%s\n' % (a.time, block_sha, len(block_bytes), len(block_lines), block))
    os.makedirs(os.path.dirname(archive_abs), exist_ok=True)
    with open(archive_abs, 'w', encoding='utf-8', newline='\n') as f:
        f.write(archive_txt)
    quick = ('> 🔴 §148 正文（%d B／块 SHA256 `%s`）已**整块逐字归档** ⇒ `%s`；'
             '速查：`_app326` 41 PASS/0 FAIL・反证 9/9，随包闸门仅检出 2/6 类违规'
             '（APP-081 第 3 点已修复）。'
             % (len(block_bytes), block_sha, archive_rel))
    new_lines[idx:] = [quick, '']
    head_and_body = '\n'.join(new_lines)
    new_text = head_and_body + '\n' + body + '\n'
    out = new_text.encode('utf-8')

    # ③ 写前自检
    checks = []

    def chk(cond, name, detail=''):
        checks.append({'name': name, 'pass': bool(cond), 'detail': detail})

    chk(new_text.startswith('\n'.join(new_lines[:7]) + '\n'),
        'head_prefix_intact')
    restored = head_and_body.replace(quick, block, 1)
    chk(restored == head_before_archive, 'reverse_restore_equals_old_body',
        'restored=%d old=%d' % (len(restored), len(head_before_archive)))
    arch = open(archive_abs, encoding='utf-8').read()
    chk(block in arch, 'archive_block_verbatim')
    chk(('块 SHA256 `%s`' % block_sha) in arch, 'archive_sha_recorded')
    chk(quick in new_text, 'quick_reference_in_status')
    n_old_sections = sum(1 for l in old_lines if l.startswith('## §'))
    n_new_sections = sum(1 for l in new_text.split('\n') if l.startswith('## §'))
    chk(n_new_sections >= n_old_sections, 'section_count_not_decreased',
        '%d -> %d' % (n_old_sections, n_new_sections))
    chk(b'\r' not in out, 'LF_not_broken')
    chk(len(out) <= 40000, 'size_limit_40000', 'bytes=%d' % len(out))
    n_lines = len(new_text.split('\n')) - 1
    chk(n_lines <= 300, 'line_limit_300', 'lines=%d' % n_lines)
    chk('APP-081' in new_lines[2], 'last_ack_APP_081')
    chk('APP-075 未闭环（BLOCKING）' not in new_lines[5],
        'old_blocking_paragraph_removed')

    n_fail = sum(1 for c in checks if not c['pass'])
    ev = {'tool': '_app334', 'app': 'APP-081', 'time_source': 'Get-Date 实测',
          'time': a.time,
          'status_before': {'bytes': len(raw), 'lines': len(old_lines) - 1,
                            'sha256': sha(raw)},
          'head_changes': head_changes,
          'archive': {'path': archive_rel, 'block_bytes': len(block_bytes),
                      'block_lines': len(block_lines),
                      'block_sha256': block_sha,
                      'file_bytes': os.path.getsize(archive_abs),
                      'file_sha256': sha(open(archive_abs, 'rb').read())},
          'section_body': {'path': BODY,
                           'bytes': len(body.encode('utf-8')),
                           'sha256': sha(body.encode('utf-8'))},
          'checks': checks, 'n_pass': len(checks) - n_fail, 'n_fail': n_fail,
          'would_be': {'bytes': len(out), 'lines': n_lines, 'sha256': sha(out)}}
    if n_fail:
        ev['verdict'] = 'FAIL_PRECHECK'
        print('[FAIL] 写前自检未通过 ⇒ STATUS 一个字节未落盘')
        for c in checks:
            if not c['pass']:
                print('   -', c['name'], c['detail'])
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        return 1

    # ④ 原子替换 + 写后逐字节复核
    tmp = STATUS + '._app334_tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
    back = open(tmp, 'rb').read()
    assert back == out, '临时文件写后逐字节复核失败'
    os.replace(tmp, STATUS)
    disk = open(STATUS, 'rb').read()
    chk(disk == out, 'disk_byte_identical_after_write')
    ev['status_after'] = {'bytes': len(disk),
                          'lines': len(disk.decode('utf-8').split('\n')) - 1,
                          'sha256': sha(disk)}
    ev['verdict'] = 'PASS' if disk == out else 'FAIL_POSTCHECK'
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[%s] STATUS %d B / %d 行 → %d B / %d 行，写前自检 %d/%d'
          % (ev['verdict'], len(raw), len(old_lines) - 1, len(disk),
             ev['status_after']['lines'], ev['n_pass'], len(checks)))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
