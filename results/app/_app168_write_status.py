#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
app168 配套：把 §112 追加进 status/app/STATUS_APP.md，并更新头部字段。

🔴 纪律（记忆铁律）：
  - 只**追加** `### §112` 章节，**不回头改旧章节**；
  - 头部用「**首个章节锚点**」切片（`## 最近章节` 之前的头部区），
    `lines[i_anchor:]` **原样保留**；
  - 写前 `cp` 备份；写后验「旧正文整块原样在新文件里 `indexOf` 出现」
    （**不能用 endsWith** —— 追加块前多一个空行 ⇒ 误报）；
  - 头部字段替换须**限定头部区**，且 `value` **不能自带 `key: ` 前缀**
    （否则重复前缀）；
  - 「最近更新」区块 ≤ 15 行 ⇒ 超了**裁掉最旧的**；
  - STATUS 是 **LF** 换行（本轮实测 `CRLF count = 0`）⇒ 按实际判别后写回。
"""

import hashlib
import io
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BODY = os.path.join(HERE, '_sec112_body.md')

NEW_TIME = sys.argv[1] if len(sys.argv) > 1 else None

NEW_TASK = (
    '**§112 ✅ 客户包「运行时可加载性」独立验收：21 PASS / 0 FAIL（含 3 条反证）；'
    '抓出并修掉「宿主 PYTHONPATH 污染」使旧结论变假通过**；'
    '本轮**无新纠偏条目**（`last_ack=APP-049` = 最大编号，第 31 次同一口径复核）'
    '⇒ 按 APP-046 规则继续推进 ⇒ **APP-046…049 全部结清**；'
    '**APP-043 真机验收 / APP-045③ / v1.13 打包**仍未做'
    '（守用户 11:30 指令「不通知不打包」）'
)

NEW_BLOCK = (
    '① 🔴 **v1.13 未打包**（用户 11:30 指令：未经通知不主动打包；且 v1.12 zip 生成于 11:20，'
    '**不含** APP-045/047/048 任何改动）⇒ 等用户通知；'
    '② 🔴 **APP-043 真机验收未做**（用户启动方式 `pythonw.exe` 冷启动 / SPE Q&A 双说话人 / '
    'GUI 加速播放 / 3 段 1.2–1.3× 配音给用户实听）⇒ 通过后才写 `ACCEPTED.json`、'
    '才更新桌面快捷方式；'
    '③ 🔴 **桌面快捷方式仍指向 v1.5**（用户当前实测的仍是旧包 ⇒ APP-045 的根因）；'
    '④ 🔴 **APP-048 的「和 v1.13 一起交付」尚未满足**（布局与截图已完成，等 v1.13）；'
    '⑤ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；'
    '⑥ 🔴 **宿主 `PYTHONPATH` 污染对历史验收结论的影响范围待 reviewer 确认**'
    '（§112 已证明它会让 `torch` 假阳性；§109/§110 为静态字节比对，未受影响）；'
    '⑦ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入）'
)

RECENT_NEW = (
    '- 2026-10-30 20:41 **§112 客户包「运行时可加载性」独立验收** ⇒ 新增 '
    '`results/app/app168_pkg_runtime_import_probe.py`（**用客户包自带 python 3.12.10 真实 import 包内模块**）'
    '⇒ **21 PASS / 0 FAIL**（含 B1/B2/B3 三条反证）；'
    '对旧包 **v1.5** 跑同一套 ⇒ **12 FAIL** ⇒ 判据有鉴别力；'
    '🔴 抓出**宿主 `PYTHONPATH` 污染**（包内 python 的 `sys.path` 混入 WorkBuddy shim ⇒ `torch` 假阳性）'
    '⇒ 已置空 `PYTHONPATH` 并新增 R9+B3。'
)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    global NEW_TIME
    if NEW_TIME is None:
        raise SystemExit('用法: python _app168_write_status.py "YYYY-MM-DD HH:MM"')

    with open(STATUS, 'rb') as f:
        raw = f.read()
    crlf = raw.count(b'\r\n')
    text = raw.decode('utf-8')
    nl = '\r\n' if crlf > (raw.count(b'\n') - crlf) else '\n'
    body_lines = text.split(nl)

    # ── 备份 ───────────────────────────────────────────────────────
    bak = STATUS + '.bak_app168'
    shutil.copy2(STATUS, bak)
    print('[bak]', bak, os.path.getsize(bak), 'B')

    # ── 定位头部 / 正文分界（首个章节锚点 = 「## 最近章节」）──────────
    i_anchor = None
    for i, ln in enumerate(body_lines):
        if ln.startswith('## 最近章节'):
            i_anchor = i
            break
    if i_anchor is None:
        raise SystemExit('!! 找不到「## 最近章节」锚点')
    head = body_lines[:i_anchor]
    tail = body_lines[i_anchor:]
    old_body_text = nl.join(tail)
    print('[split] head_lines=%d tail_lines=%d' % (len(head), len(tail)))

    # ── 头部字段定点替换（限定头部区）──────────────────────────────
    def set_field(key, value):
        assert value.count(key + ': ') == 0, \
            'value 自带 key 前缀 ⇒ 会写两遍: %r' % value
        pat = re.compile(r'(?m)^' + re.escape(key) + r': .*$')
        hits = [i for i, ln in enumerate(head) if pat.match(ln)]
        assert len(hits) == 1, '%s 在头部出现 %d 次（应为 1）' % (key, len(hits))
        head[hits[0]] = key + ': ' + value

    set_field('last_ack', 'APP-049')          # 本轮无新条目 ⇒ 不变
    set_field('更新时间', NEW_TIME)
    set_field('当前任务', NEW_TASK)
    set_field('阻塞 / 待用户决定', NEW_BLOCK)

    # ── 「最近更新」区块：插入新条目并裁到 ≤15 行 ───────────────────
    i_recent = None
    for i, ln in enumerate(head):
        if ln.startswith('## 最近更新'):
            i_recent = i
            break
    assert i_recent is not None, '找不到「## 最近更新」'
    i_next = None
    for j in range(i_recent + 1, len(head)):
        if head[j].startswith('## '):
            i_next = j
            break
    if i_next is None:
        i_next = len(head)
    block = head[i_recent + 1:i_next]
    entries = [ln for ln in block if ln.startswith('- ')]
    entries.insert(0, RECENT_NEW)
    while len(entries) > 15:
        entries.pop()          # 裁掉**最旧**的
    assert len(entries) <= 15
    new_block = [''] + entries + ['']
    head = head[:i_recent + 1] + new_block + head[i_next:]

    # ── 追加新章节（**在文件末尾**）────────────────────────────────
    with open(BODY, 'rb') as f:
        sec = f.read().decode('utf-8').rstrip('\n')
    assert '§112' in sec and '### §112' in sec
    # 幂等闸门：不允许出现两个 §112
    assert len(re.findall(r'(?m)^### §112', old_body_text)) == 0, \
        '正文里已有 §112 ⇒ 本轮不该再追加（幂等闸门）'

    out_lines = head + tail + ['', sec, '']
    out_text = nl.join(out_lines)

    # ── 写盘前自检 ─────────────────────────────────────────────────
    assert len(out_text.encode('utf-8')) <= 40 * 1024, \
        '超过 40 KB 限额: %d' % len(out_text.encode('utf-8'))
    assert len(out_lines) <= 300, '超过 300 行限额: %d' % len(out_lines)
    # 旧正文整块原样出现（**不用 endsWith**）
    assert old_body_text in out_text, '旧正文被改动 ⇒ 中止'
    assert out_text.count('### §112') == 1

    with open(STATUS, 'wb') as f:
        f.write(out_text.encode('utf-8'))

    # ── 写盘后复核 ─────────────────────────────────────────────────
    with open(STATUS, 'rb') as f:
        new_raw = f.read()
    new_text = new_raw.decode('utf-8')
    assert old_body_text in new_text, '写盘后旧正文缺失'
    assert len(re.findall(r'(?m)^### §', new_text)) == 4, \
        '章节数应为 4（§109/§110/§111/§112），实得 %d' % len(re.findall(r'(?m)^### §', new_text))
    assert 'last_ack: APP-049' in new_text
    assert '更新时间: ' + NEW_TIME in new_text
    print('[ok] bytes=%d lines=%d CRLF=%d sha256=%s'
          % (len(new_raw), len(new_text.split(nl)), new_raw.count(b'\r\n'),
             sha256_bytes(new_raw)))
    print('[ok] sections:', re.findall(r'(?m)^### §\d+', new_text))


if __name__ == '__main__':
    main()
