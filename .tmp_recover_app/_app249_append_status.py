r"""_app249_append_status.py —— 在 `STATUS_APP.md` 末尾**追加** §249 指针行 ＋ 更新头部两行。

## 为什么不用 Edit 工具（§236 坑⑥）

`Edit` 工具会把整份文件**统一规整成 LF** ⇒ 本文件是**混合行尾**（71 CRLF + 43 LF）
⇒ 用 Edit 改 1 行会让 **71 个 CRLF 全消失** ⇒ 违反「行尾风格不变」＋「旧正文逐字未变」。

⇒ 本脚本**在字节层**做：以写前备份为基底 ⇒
  * 只**替换**头部两行（`last_ack` / `更新时间`）——**用字节级精确替换**，
    保留该行**原有行尾**（CRLF 还是 LF）；
  * 末尾**追加**新节（用文件尾部那一行的行尾风格：CRLF）；
  * 断言：**旧正文逐字节未变**（除头部两行 + 新增节）。

## 写前不变量

1. `CRLF` 计数 **只允许因新增内容而增加**，旧行的 CRLF **一个不少**；
2. 旧正文（去掉头部两行）**逐字节等于**写前备份的对应部分；
3. 新节追加在文末（不改任何旧节）。
"""

from __future__ import annotations

import io
import os
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BAK = os.path.join(REPO, 'status', 'app',
                   'STATUS_APP.md.bak_app249_sec249_20260727_2140')


def log(m):
    print(m, flush=True)


def main():
    before = open(STATUS, 'rb').read()
    if not os.path.exists(BAK):
        shutil.copy2(STATUS, BAK)
        log('备份 → %s' % BAK)

    text = before.decode('utf-8')
    lines = text.splitlines(keepends=True)

    # ── 定位头部两行 ──────────────────────────────────────────
    i_ack = i_time = None
    for i, ln in enumerate(lines):
        if ln.startswith('last_ack:'):
            i_ack = i
        elif ln.startswith('更新时间:'):
            i_time = i
    if i_ack is None or i_time is None:
        log('🔴 [FAIL] 找不到头部 last_ack / 更新时间 行')
        return 1

    def eol_of(s):
        if s.endswith('\r\n'):
            return '\r\n'
        if s.endswith('\n'):
            return '\n'
        return ''

    ack_eol = eol_of(lines[i_ack])
    time_eol = eol_of(lines[i_time])

    new_ack = 'last_ack: APP-157（＋LOCK-002）' + ack_eol
    new_time = '更新时间: 2026-11-27 21:40' + time_eol

    old_ack = lines[i_ack]
    old_time = lines[i_time]
    if 'APP-157' not in old_ack:
        log('🔴 [FAIL] 头部 last_ack 不是 APP-157：%r' % old_ack)
        return 1

    # ── 追加 §249 指针行（用文件尾部那一行的行尾风格）────────────
    tail_eol = '\r\n' if before.endswith(b'\r\n') else '\n'
    sec249 = (
        '## §249 六通道复核（**无新 App 纠偏**，`last_ack` 仍 **APP-157**）｜'
        '🔴 **修掉 §248 的 2 处真缺陷**：'
        '① 脱敏**重做**（121 文件 / 1 987 处；独立终检 **4 判据全 PASS**；'
        '**§248 弄坏的 12 个 JSON 已归零**、漏掉的 ~45 行/文件已补齐）｜'
        '② APP-153 §5 的修复**接回生产路径**（dev 树 ↔ 包内 `app/*.py` 差异 **4 → 0**）'
        + tail_eol +
        '> 🔴 正文全文 ⇒ `status/app/STATUS_APP_sec249_detail_20261127.md`'
        '（§0 顺序、§1 六通道证据、§2 两处真缺陷＋根因、§3 脱敏重做＋4 判据、'
        '§4 生产路径回灌、§5 未做/待裁定、§6 纪律、§7 收尾指纹）' + tail_eol
    )

    # ── 组装新文件（字节层）──────────────────────────────────
    out = []
    for i, ln in enumerate(lines):
        if i == i_ack:
            out.append(new_ack)
        elif i == i_time:
            out.append(new_time)
        else:
            out.append(ln)
    new_text = ''.join(out) + sec249
    data = new_text.encode('utf-8')

    # ── 写前不变量 ───────────────────────────────────────────
    b_crlf = before.count(b'\r\n')
    a_crlf = data.count(b'\r\n')
    assert a_crlf >= b_crlf, 'CRLF 变少了：%d → %d' % (b_crlf, a_crlf)

    # 旧正文（除头部两行）逐字节未变
    # 🔴 注意：不能用「join 后比」——因为**头部那两行可能没有行尾**
    #    （`更新时间` 行后面紧跟正文首行）⇒ join 会把两段拼在一起 ⇒ 假不等。
    # ⇒ 改成**逐行逐字节比**（每行单独比，最后一行可能没有行尾 ⇒ 照样可比）。
    old_body_lines = [l.encode('utf-8') for j, l in enumerate(lines)
                      if j not in (i_ack, i_time)]
    new_body_lines = [l.encode('utf-8') for j, l in enumerate(out)
                      if j not in (i_ack, i_time)]
    # out 与 lines 同长度 ⇒ new_body_lines 比 old_body_lines 多**末尾 sec249 的行**
    n_old = len(old_body_lines)
    assert new_body_lines[:n_old] == old_body_lines, '旧正文被改动了！'

    # 头部两行只改了内容、行尾保留
    assert new_ack.encode('utf-8').endswith(ack_eol.encode('utf-8'))
    assert new_time.encode('utf-8').endswith(time_eol.encode('utf-8'))

    tmp = STATUS + '.tmp_app249'
    with io.open(tmp, 'wb') as fh:
        fh.write(data)
    os.replace(tmp, STATUS)
    assert open(STATUS, 'rb').read() == data, '写后逐字节复核失败'

    log('✔ 已追加 §249：%d → %d B（CRLF %d → %d）'
        % (len(before), len(data), b_crlf, a_crlf))
    log('  头部 last_ack 行尾=%r  更新时间 行尾=%r  追加行尾=%r'
        % (ack_eol, time_eol, tail_eol))
    return 0


if __name__ == '__main__':
    sys.exit(main())
