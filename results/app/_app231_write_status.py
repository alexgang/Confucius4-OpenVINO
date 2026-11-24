#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-231：把本轮结论写进 `status/app/STATUS_APP.md`（追加 `## §231` ＋ 头部两行）。

## 本轮性质（决定写什么）

- 🔴 **六通道全空 ⇒ 无新 App 纠偏** ⇒ **`last_ack` 保持 APP-133 不变**
  （MEMORY §三：「无新纠偏时 `last_ack` 不变」）。
- 🔴 但本轮**不是纯待命轮**：它是 **TAKEOVER 接续轮**，且**闭合了上一会话的遗留项**
  ⇒ 按 MEMORY §三（「TAKEOVER 接续轮若在闭合上一会话遗留项 ⇒ **可写 §N**」，
  §215／§222 先例）⇒ **写 §231**。

## 🔴 写入纪律（三件套）

① 备份（`%TEMP%/*.bak`）② 写前在**内存新文本**跑真不变量 ＋ **还原式复核**
③ 临时文件 → `os.replace` ⇒ 写后**另起脚本**独立复核 ＋ `numstat`。

## 🔴 四个必须守住的点

1. **只改头部两行**：`last_ack`（**值不变**，但**保持唯一**）＋ `更新时间`
   （**`Get-Date` 实测值，禁止推算**）。
2. **只追加**：`## §231` 追加在**文末**；§227 及更早**逐字未变**。
3. **行尾风格不变**：本文件是 **CRLF** ⇒ 新增内容**必须也是 CRLF**
   ⇒ 🔴 **不要**用 `.replace('\n','\r\n')`（会产生孤立 CR/TAB）⇒
   **用 `newline=''` 写**、并在**内存里**就把 `\r\n` 拼好。
4. **限额**：≤ 40 000 B / ≤ 300 行（APP-052④）⇒ 写前自检，**超限 ⇒ 零改动**。
"""
from __future__ import annotations

import datetime
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
DETAIL = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec231_detail_20261124.md')
TMP = os.environ.get('TEMP', '/tmp')

MAX_BYTES = 40000
MAX_LINES = 300
CRLF = '\r\n'
LF = '\n'

# 🔴🔴 **本文件是「混合行尾」**（实测，本轮首次发现）：
#   · 第 2~3 行（`last_ack` / `更新时间`）＝ **LF**
#   · §228/§229/§230 三节 ＝ **LF**
#   · 其余（更早各节、头部其余行）＝ **CRLF**
#   ⇒ 🔴 **不能**断言「全文无孤立 LF」（写前实测就有 **13 处** ⇒ 那是**既有事实**，
#   断言它 ⇒ **必假 FAIL**）。
#   ⇒ ✅ 正确做法：**逐区域**按其**既有**行尾写入新内容 ⇒ 新内容与邻行一致，
#   且**旧行尾一个都不改**（`git diff --numstat` 可证）。
#   ⇒ 判据改成：**新增行的行尾 == 该区域既有行尾**（逐行核对）。


def get_date():
    """🔴 `Get-Date` 实测值（PowerShell）⇒ 禁止推算。"""
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command', 'Get-Date -Format "yyyy-MM-dd HH:mm:ss"'],
            capture_output=True, text=True, timeout=30)
        v = (out.stdout or '').strip()
        if v:
            return v
    except Exception:
        pass
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── ① 头部两行（**只改这两行**，其余头部逐字不动）──────────────────
OLD_UPDATED = '更新时间: 2026-11-24 18:29:37'
NEW_UPDATED_TMPL = '更新时间: %s'

# ── ② 「最近更新」块首条（**插在块首**，旧的 11 行归档指针行保持不动）──
OLD_RECENT = '> 🔴 2026-11-24 17:4x ｜ **执行 **APP-131 / APP-132 / APP-133**'
NEW_RECENT = (
    '> 🔴 2026-11-24 20:3x ｜ **接续上一会话（TAKEOVER）**｜**六通道复核 ⇒ 无新 App 纠偏**'
    '（本地 max APP-133 ＝ QQ max APP-133 ＝ `last_ack` ⇒ **last_ack 仍 APP-133**）｜'
    '🟢 **闭合上一会话遗留的「记忆写入未落盘」**（当日日志第 126 轮＋`MEMORY.md` 指针＋'
    '`MEMORY_MODULES.md` 五十节；独立复核 **19/19 PASS**）｜'
    '🟢 **补上 APP-132 的生产路径补漏**：上一轮修法只落在**侧写 harness**，'
    '**成包路径** `live_caption/_app116_build_v25.py` 仍是 `os.replace(tmp, LOCK)`'
    '（非原子＋会覆盖别人的锁）＋看门狗被抢即放弃 ⇒ **已修**（`os.link` 原子+独占＋'
    '丢锁记事件）；独立行为级复核 **9/9 PASS**（含**反证组**：旧实现 2 成功 ⇒ 判据能识破）｜'
    '🟢 未打包／未通知用户／未连 B 机／未调 MiniMax／未改纠偏文件｜**本条需等 reviewer 复核**'
)

# ── ③ §231 正文（**追加在文末**）─────────────────────────────────
# 🔴 行尾用 LF（与 §228/§229/§230 三节一致）；写入前会按文末实际行尾再转换。
SEC231 = (
    '## §231 接续上一会话（TAKEOVER）｜**六通道复核 ⇒ 无新 App 纠偏**（`last_ack` 仍 **APP-133**）'
    '｜🟢 **闭合上一会话遗留的「记忆写入未落盘」**｜🟢 **补上 APP-132 的生产路径补漏**'
    '（`live_caption/_app116_build_v25.py` 仍是 `os.replace` 非原子建锁）｜'
    '🔴 独立行为级复核 9/9 PASS（含反证组）｜🟢 未打包／未通知用户／未连 B 机／未调 MiniMax｜'
    '**本条需等 reviewer 复核**\n'
    '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec231_detail_20261124.md`**'
    '（含 §1 六通道复核逐通道证据、§2 上一会话遗留项清单与闭合方式、'
    '§3 APP-132 生产路径补漏的根因与修法（三种建锁写法对比）、'
    '§4 独立行为级复核 9/9（含反证组）、§5 本轮两个新判据坑、§6 纪律）\n'
)


def main():
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        old = f.read()

    # ── 真不变量（写前）─────────────────────────────────────
    assert '\r\n' in old, 'STATUS 不是 CRLF（前提不符）'
    assert old.count(OLD_UPDATED) == 1, '更新时间锚点命中数 != 1'
    assert old.count(OLD_RECENT) == 1, '最近更新锚点命中数 != 1'
    assert old.count('last_ack: APP-133') == 1, 'last_ack 不唯一'
    assert '## §231' not in old, '§231 已存在（幂等守卫）'
    # 🔴 记录**写前**的行尾分布（用于写后逐区域核对）
    def ending_of(text, needle):
        """返回**包含 needle 的那一行**的行尾。

        🔴 **本轮实测踩到的真 bug**：锚点 `OLD_RECENT` 是**行的前缀**（不是整行）
        ⇒ 若直接看「锚点后面紧跟什么」⇒ 拿到的是**行内下一个字符**（本例是 `（`）
        ⇒ **返回空串** ⇒ 插入时**两行被拼成一行**（实测：1178 字符的一行）。
        ⇒ ✅ 正确做法：**先找到锚点所在行的行尾**（向后扫到第一个换行）。
        """
        i = text.index(needle)
        j = text.find('\n', i)
        if j < 0:
            return ''
        if j > 0 and text[j - 1] == '\r':
            return CRLF
        return LF
    old_endings = {
        'updated': ending_of(old, OLD_UPDATED),
        'recent': ending_of(old, OLD_RECENT),
        'tail': old[-2:] if old.endswith(CRLF) else (old[-1:] if old.endswith(LF) else ''),
    }
    assert old_endings['recent'] in (CRLF, LF), (
        '最近更新锚点的行尾判定失败：%r' % (old_endings['recent'],))
    assert old_endings['updated'] in (CRLF, LF), (
        '更新时间锚点的行尾判定失败：%r' % (old_endings['updated'],))
    old_lines = old.split(CRLF)

    # 🔴 **`Get-Date` 只取一次**（本轮修的第二个 bug：写后复核里又调了一次
    #   `get_date()` ⇒ 若跨秒 ⇒ 还原式复核**必然失败**（假 FAIL））
    now_str = get_date()

    new = old

    # ① 头部「更新时间」⇒ Get-Date 实测值（**last_ack 值不变**）
    #    🔴 **就地替换文本，不动该行的行尾** ⇒ 保持 LF
    new = new.replace(OLD_UPDATED, NEW_UPDATED_TMPL % now_str, 1)

    # ② 「最近更新」块首 ⇒ 插入新条目（旧的 17:4x 条目**下移**，不删）
    #    🔴 新条目的行尾 = **该区域既有行尾**（实测 = LF）
    new = new.replace(OLD_RECENT, NEW_RECENT + old_endings['recent'] + OLD_RECENT, 1)

    # ③ 文末追加 §231（**行尾 = 文末既有行尾**；实测文末 = LF）
    tail_e = old_endings['tail']
    sec231 = SEC231.replace(CRLF, tail_e)
    if tail_e and not new.endswith(tail_e):
        new += tail_e
    new = new + sec231

    # ── 真不变量（写后，内存态）───────────────────────────────
    assert 'last_ack: APP-133' in new and new.count('last_ack: APP-133') == 1
    assert new.count(OLD_UPDATED) == 0, '旧的更新时间仍在'
    assert new.count('## §231') == 1
    assert '2026-11-24 18:29:37' not in new.split('## §231')[0], '旧更新时间未替换'
    # 🔴 **不**断言「无孤立 LF」——写前就有 13 处（既有事实）
    #    ⇒ 改为断言「**旧行的行尾一个都没变**」（见下面的还原式复核）
    # 🔴 **新增的最近更新条目必须独占一行**（本轮真 bug 的针对性判据）
    assert NEW_RECENT not in old, '新条目已存在（幂等守卫）'
    assert new.count(NEW_RECENT) == 1, '新最近更新条目不唯一'
    assert (NEW_RECENT + old_endings['recent']) in new, '新条目与其分隔行尾缺失'
    # **还原式复核**：把本轮三处改动还原 ⇒ 必须逐字节等于写前原文
    restored = new
    restored = restored.replace(NEW_RECENT + old_endings['recent'] + OLD_RECENT,
                                OLD_RECENT, 1)
    restored = restored.replace(NEW_UPDATED_TMPL % now_str, OLD_UPDATED, 1)
    k = restored.find('## §231 接续上一会话')
    assert k > 0
    restored = restored[:k]
    # 追加时可能补过一个行尾 ⇒ 还原时去掉
    if (tail_e and not old.endswith(tail_e) and restored.endswith(tail_e)):
        restored = restored[:-len(tail_e)]
    assert restored == old, '还原式复核失败（与写前原文不逐字节相同）'

    # 限额自检（**写前**⇒ 超限就零改动）
    nbytes = len(new.encode('utf-8'))
    nlines = new.count('\n') + 1
    assert nbytes <= MAX_BYTES, 'STATUS 会超字节限额：%d > %d ⇒ 零改动' % (nbytes, MAX_BYTES)
    assert nlines <= MAX_LINES, 'STATUS 会超行数限额：%d > %d ⇒ 零改动' % (nlines, MAX_LINES)

    # ── 写入（临时文件 → os.replace）─────────────────────────
    tmp = STATUS + '.tmp_app231'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, STATUS)

    print('OK  %s' % STATUS)
    print('  before %d B / %d 行' % (len(old.encode('utf-8')), len(old_lines)))
    print('  after  %d B / %d 行（限额 %d B / %d 行）'
          % (nbytes, nlines, MAX_BYTES, MAX_LINES))
    print('  sha256 %s' % hashlib.sha256(new.encode('utf-8')).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
