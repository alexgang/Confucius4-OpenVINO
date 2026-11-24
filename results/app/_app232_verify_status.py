#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-232 轮：`status/app/STATUS_APP.md` 写入后的**独立复核**（另起脚本）。

## 判据（全部对着**写前备份**比，🔴 不写死记忆里的数字）

1. 限额：≤40 000 B（APP-052④）／≤300 行。
2. `last_ack: APP-133` **仍唯一**（本轮无新纠偏 ⇒ 值不变）。
3. 头部「更新时间」＝ 写脚本记录的实测值（🔴 **不重新取时间**，避免跨秒假 FAIL）。
4. **旧正文逐字未变**：把新文件的 3 处改动**反向还原** ⇒ 必须**逐字节等于**写前备份。
5. **§231 及更早的节逐行逐字节未变**（只追加在文末）。
6. 行尾风格：CRLF 数**完全不变**；孤立 LF 数 +3（1 条「最近更新」＋ 2 行 §232）。
7. 「最近更新」块首是本轮新条目（**旧条目下移未删** ⇒ 旧条目数 +1）。
8. §232 标题行与指针行都在；companion 文件存在且非空。
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
COMP = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec232_detail_20261124.md')
BAK = os.path.join(os.environ.get('TEMP', r'C:\Users\Trekker-PTL\AppData\Local\Temp'),
                   'STATUS_APP.md.bak_app232')
LIM_B = 40000
LIM_L = 300
NEW_TS = '2026-11-24 22:02:37'
OLD_TS = '2026-11-24 20:27:19'


def rb(p):
    with open(p, 'rb') as f:
        return f.read()


def main():
    cur_b = rb(STATUS)
    old_b = rb(BAK)
    cur = cur_b.decode('utf-8')
    old = old_b.decode('utf-8')
    errs = []

    # ① 限额
    if len(cur_b) > LIM_B:
        errs.append('超字节限额 %d > %d' % (len(cur_b), LIM_B))
    if len(cur.split('\n')) > LIM_L:
        errs.append('超行限额 %d > %d' % (len(cur.split('\n')), LIM_L))

    # ② last_ack 唯一
    if cur.count('last_ack: APP-133') != 1:
        errs.append('last_ack 行数 %d != 1' % cur.count('last_ack: APP-133'))

    # ③ 更新时间
    if ('更新时间: ' + NEW_TS) not in cur:
        errs.append('更新时间不是实测值 %s' % NEW_TS)
    if ('更新时间: ' + OLD_TS) in cur:
        errs.append('旧更新时间仍在')

    # ④ 反向还原 ⇒ 必须逐字节等于写前备份
    lines = cur.split('\n')
    # 定位本轮 3 处改动
    ts_line = '更新时间: ' + NEW_TS
    ru_idx = None
    for i, l in enumerate(lines):
        if l.startswith('> 🔴 ' + NEW_TS):
            ru_idx = i
            break
    if ru_idx is None:
        errs.append('找不到本轮的「最近更新」新条目')
    sec_idx = None
    for i, l in enumerate(lines):
        if l.startswith('## §232 '):
            sec_idx = i
            break
    if sec_idx is None:
        errs.append('找不到 §232 标题行')
    if ru_idx is not None and sec_idx is not None:
        restored_lines = lines[:ru_idx] + lines[ru_idx + 1:sec_idx] + lines[sec_idx + 2:]
        restored = '\n'.join(restored_lines)
        restored = restored.replace(ts_line, '更新时间: ' + OLD_TS, 1)
        if restored != old:
            errs.append('反向还原后与写前备份不一致 ⇒ 旧正文被改了')
            # 定位首个差异行（便于排查）
            for i, (a, b) in enumerate(zip(old.split('\n'), restored.split('\n'))):
                if a != b:
                    errs.append('  首个差异行 #%d: %r != %r' % (i, a[:60], b[:60]))
                    break

    # ⑤ §231 及更早逐行未变
    #    🔴 **§232 是追加在 §231 之后** ⇒ 写后 §231 段 = 写前 §231 段 **＋§232 两行**
    #    ⇒ 正确的判据是「**写前 §231 段（整段文本）必须是写后 §231 段的前缀**」。
    #    🔴 **不要逐行等长比较**：写前段末尾那个 '' 是「文件以 \n 结尾」产生的
    #    **换行残留**（不是一行正文）⇒ 逐行比会把它与 §232 标题行错位对齐
    #    ⇒ 误报「第 2 行变了」（本轮实测踩到 ⇒ §225「off-by-one」同族坑）。
    i231 = cur.find('## §231 ')
    if i231 < 0:
        errs.append('§231 标题丢了')
    else:
        old_i231 = old.find('## §231 ')
        if old_i231 >= 0:
            a = cur[i231:]
            b = old[old_i231:]
            if not a.startswith(b):
                errs.append('§231 及更早的正文不是写前的前缀 ⇒ 旧内容被改了')
                for i in range(min(len(a), len(b))):
                    if a[i] != b[i]:
                        errs.append('  首个差异在偏移 %d: %r != %r'
                                    % (i, a[i:i + 50], b[i:i + 50]))
                        break
            else:
                print('§231 及更早：写前整段（%d B）逐字节是写后的前缀 ⇒ 旧内容未变'
                      '（写后在其后追加 %d B）' % (len(b), len(a) - len(b)))

    # ⑥ 行尾风格
    if cur_b.count(b'\r\n') != old_b.count(b'\r\n'):
        errs.append('CRLF 数变了 %d -> %d' % (old_b.count(b'\r\n'), cur_b.count(b'\r\n')))
    lf_new = cur_b.count(b'\n') - cur_b.count(b'\r\n')
    lf_old = old_b.count(b'\n') - old_b.count(b'\r\n')
    if lf_new != lf_old + 3:
        errs.append('孤立 LF 数增量 %d != 3' % (lf_new - lf_old))

    # ⑦ 「最近更新」块：**只数该块内的条目**（块 = '## 最近更新' 到下一个 '## ' 之间）
    #    🔴 **不数全文的 `> 🔴 `** —— 全文里 §231/§232 的指针行也是 `> 🔴 `，
    #    数全文会把「追加 §232」误算成「最近更新 多删/多加了 2 条」（本轮实测踩到）。
    def _ru_count(t):
        i = t.find('## 最近更新')
        if i < 0:
            return -1
        j = t.find('\n## ', i + 1)
        seg = t[i:j if j > 0 else len(t)]
        return len(re.findall(r'(?m)^> ', seg))
    n_old_ru = _ru_count(old)
    n_new_ru = _ru_count(cur)
    if n_new_ru != n_old_ru + 1:
        errs.append('「最近更新」块条目数 %d -> %d（应 +1）' % (n_old_ru, n_new_ru))

    # ⑧ §232 与 companion
    if 'STATUS_APP_sec232_detail_20261124.md' not in cur:
        errs.append('§232 指针行没指向 companion')
    if not (os.path.isfile(COMP) and os.path.getsize(COMP) > 0):
        errs.append('companion 文件缺失或为空')

    print('=== 写前/写后 ===')
    print('写前: %d B／%d 行／CRLF %d／孤立 LF %d' % (
        len(old_b), len(old.split('\n')), old_b.count(b'\r\n'), lf_old))
    print('写后: %d B／%d 行／CRLF %d／孤立 LF %d' % (
        len(cur_b), len(cur.split('\n')), cur_b.count(b'\r\n'), lf_new))
    print('字节余量: %d  行余量: %d' % (LIM_B - len(cur_b), LIM_L - len(cur.split('\n'))))
    print('SHA256(写后)=%s' % hashlib.sha256(cur_b).hexdigest())
    print('companion: %d B' % os.path.getsize(COMP))
    print()
    if errs:
        print('=== FAIL（%d 条）===' % len(errs))
        for e in errs:
            print('  ✗', e)
        return 1
    print('=== PASS ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
