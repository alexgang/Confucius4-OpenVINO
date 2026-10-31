#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app191_write_status.py —— 把 §121 章节追加进 status/app/STATUS_APP.md。

🔴🔴🔴 纪律（§104 / §118 / §119 的教训，全部落在代码里）：
1. **只追加**：新章节追加在**文件末尾**（`## §1` 之前插过一次 ⇒ 实测插错，已还原重做）。
2. **旧正文逐字未变**：用「旧正文整块在新文件里 `indexOf` 出现」判据
   （**不能用 `endsWith`** —— 追加块前多一个空行 ⇒ 误报）。
3. **头部用「首个章节锚点」切片**：`i_s1` = 第一个 `### §` 的下标
   ⇒ `lines[i_s1:]` 原样保留（用「最后一个 §N」⇒ §1~§N 全丢）。
   ⚠️ §111 压缩后章节标题是 **三级**（`### §N`）⇒ 锚点用 `### §`。
4. **行尾归一化后再写回**（本文件实测 **纯 LF** ⇒ 但不假设）。
5. **`set_field` 的 value 不能自带 `key: ` 前缀**（否则写两遍）。
6. **「最近更新」≤ 15 行** ⇒ 超了**裁掉最旧的**（不是失败）。
7. **「已改字段」列表**：`last_ack` 取值不变时**不会**出现 ⇒ 断言要单独校验其取值。
"""
from __future__ import annotations

import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BODY_FILE = os.path.join(HERE, '_sec121_body.md')
BACKUP = STATUS + '.bak_sec121'

NEW_UPDATED = '2026-11-01 06:32'
LAST_ACK = 'APP-051'

RECENT_LINE = (
    '- 2026-11-01 06:32 **§121 无新纠偏条目（`last_ack` 仍 APP-051）** ⇒ 按 APP-046 继续做，'
    '**收 git 尾时实跑 `app076` 抓到 2 个 FAIL** ⇒ 追查确认**两个都是「判据自身缺陷」**：'
    '① 🔴 `audible_criterion_lint` 的 **E9 误报**（`ast.walk` 把 `-1` 拆成 `1` ⇒ '
    '**守恒不变式** `n_played + n_dropped == n_submitted` 被当成弱判据）'
    '⇒ 改为「比较器常量只认 comparator 本身」＋「左值是 BinOp ⇒ 守恒式不命中」⇒ **鉴别力 10/10**；'
    '② 🔴 `app076` 的 **A8 过期断言**（APP-028② 已把播放路径的 `played` emit 挪到看门狗 '
    '`_finish_played`，而 A8 只扫 `synth()` ⇒ 抓到的是**落盘分支**）⇒ 改为**按函数作用域判定 ＋ 三态**'
    '＋**必须至少有一个适用路径**（防空转）⇒ **注入法 4/4**；③ 顺手修掉 `app092` 的 **C2 子串匹配弱判据**'
    '（输出别处出现 "0 FAIL" 就会误判合规 ⇒ 反证成立）⇒ 改为解析汇总行；'
    '④ 连带修掉 `app187` 因 §120 正文引用一次性写入器而判 MISSING ⇒ 把该脚本的**写死仓库根**修掉'
    '（向上查找）并**入库**（与仓库既有 79 个 `_*.py` 先例一致）⇒ `app187` 恢复 **50/0**；'
    '⑤ 回归 `app076` **49/0**（修前 47/2）、`app092` **24/0**、`app186` **25/0**、`app187` 50/0 + 9/0、'
    '`app188/189` PASS、`app190` 8/8、`app168` 21/0、`app107` 42/0'
)


def norm(b: bytes) -> str:
    return b.decode('utf-8')


def main():
    with open(STATUS, 'rb') as f:
        raw = f.read()
    crlf = raw.count(b'\r\n') > 0
    text = norm(raw)
    if crlf:
        text = text.replace('\r\n', '\n')

    with open(BODY_FILE, 'r', encoding='utf-8') as f:
        new_body = f.read()

    lines = text.split('\n')

    # ── 首个章节锚点（§1）──
    i_s1 = None
    for i, ln in enumerate(lines):
        if ln.startswith('### §') or ln.startswith('## §'):
            i_s1 = i
            break
    if i_s1 is None:
        raise SystemExit('[FAIL] 找不到章节锚点')
    head = lines[:i_s1]
    old_body = '\n'.join(lines[i_s1:])

    # ── 头部字段 ──
    # 🔴🔴🔴 §120 实测踩坑：`set_field` 必须在**同一个字符串**上链式调用
    #   （本轮首版每次都重新 `'\n'.join(head)` ⇒ **第二次调用把第一次的更新覆盖了**
    #   ⇒ 「更新时间」没被改上 ⇒ 被新增的断言当场拦下 ⇒ 未写盘）。
    def make_setter(src):
        def set_field(key, value):
            pat = re.compile(r'^(%s:\s*)(.*)$' % re.escape(key), re.M)
            hits = pat.findall(src)
            if len(hits) != 1:
                raise SystemExit('[FAIL] 字段 %s 出现 %d 次（要求恰好 1）'
                                 % (key, len(hits)))
            # 🔴 value 不得自带前缀
            if value.startswith(key + ':'):
                raise SystemExit('[FAIL] value 自带 key 前缀')
            return pat.sub(lambda m: m.group(1) + value, src)
        return set_field

    head_txt = '\n'.join(head)
    head_txt = make_setter(head_txt)('更新时间', NEW_UPDATED)
    head_txt = make_setter(head_txt)('last_ack', LAST_ACK)
    head_lines = head_txt.split('\n')

    # ── 「最近更新」区块 ──
    # 🔴🔴🔴 §120 实测踩坑（**差点又犯 §119 那个坑**）：
    #   「最近更新」**不是**头部末尾的最后一个区块 ⇒ 后面还有
    #   「## 当前有效结论」/「## 未完成纠偏」/「## 最近章节」等**大段内容**。
    #   ⇒ 区块边界必须找**下一个 `## ` 标题**（不是取到头部末尾）
    #   ⇒ 否则会把后面的大段内容整块丢掉（实测丢了 51 行）。
    try:
        i_rec = head_lines.index('## 最近更新')
    except ValueError:
        raise SystemExit('[FAIL] 找不到「## 最近更新」')
    i_rec_end = len(head_lines)
    for j in range(i_rec + 1, len(head_lines)):
        if head_lines[j].startswith('## '):
            i_rec_end = j
            break
    rec_block = head_lines[i_rec + 1:i_rec_end]
    tail_after_rec = head_lines[i_rec_end:]      # 🔴 必须原样保留
    # 裁掉尾部空行
    while rec_block and not rec_block[-1].strip():
        rec_block.pop()
    # 🔴🔴🔴 **§121 实测修正（原实现丢了「条目之间的空行」）**：
    #   原实现 `items = [x for x in rec_block if x.strip().startswith('- ')]`
    #   ⇒ **只保留 `- ` 开头的行** ⇒ 区块里**条目之间的空行被丢掉**
    #   ⇒ 实测：§118 与 §117 之间原本有一个空行（§120 手工恢复过一次）
    #      ⇒ §121 又被吃掉了 ⇒ `git diff` 多出一行删除（违反「旧正文逐字未删」）。
    #   ⇒ 修法：**保留区块内的全部行（含空行）**，只按「`- ` 条目数」限 15。
    items = list(rec_block)
    items = [RECENT_LINE] + items
    # 🔴 超限裁最旧的（按**条目数**算，不是按行数算）
    while sum(1 for x in items if x.strip().startswith('- ')) > 15:
        for i in range(len(items) - 1, -1, -1):
            if items[i].strip().startswith('- '):
                del items[i]
                break
    # 裁完可能留下孤立空行在尾部 ⇒ 再裁一次
    while items and not items[-1].strip():
        items.pop()
    n_entries = sum(1 for x in items if x.strip().startswith('- '))
    if n_entries > 15:
        raise SystemExit('[FAIL] 「最近更新」条目数 %d > 15' % n_entries)
    new_head = (head_lines[:i_rec + 1] + items + ['']
                + tail_after_rec)           # 🔴 后面的大段内容原样带上

    # ── 组装（🔴 必须 head + new_body + 旧正文）──
    out = '\n'.join(new_head) + '\n' + old_body.rstrip('\n') + '\n' + new_body
    if crlf:
        out = out.replace('\n', '\r\n')

    # ── 校验（旧正文整块在新文件里出现）──
    chk = norm(out.encode('utf-8'))
    if crlf:
        chk = chk.replace('\r\n', '\n')
    if old_body.rstrip('\n') not in chk:
        raise SystemExit('[FAIL] 旧正文未整块保留')
    if '### §121' not in chk:
        raise SystemExit('[FAIL] §121 章节未写入')
    if chk.count('### §') != text.count('### §') + 1:
        raise SystemExit('[FAIL] 章节数不对：%d -> %d'
                         % (text.count('### §'), chk.count('### §')))
    # 🔴🔴🔴 「头部里的每个 `## ` 区块都必须还在」⇒ 防「整块丢失」
    #   （本轮首次跑就丢了「## 当前有效结论」等 51 行 ⇒ 这条断言当场拦下）
    for h in re.findall(r'^## .+$', '\n'.join(head), re.M):
        if h not in chk:
            raise SystemExit('[FAIL] 头部区块丢失：%s' % h[:60])
    # 🔴 头部字段确实被更新
    if not re.search(r'^更新时间: 2026-11-01 06:32$', chk, re.M):
        raise SystemExit('[FAIL] 「更新时间」未更新')
    if not re.search(r'^last_ack: APP-051$', chk, re.M):
        raise SystemExit('[FAIL] 「last_ack」取值不对')

    # ── 备份后写盘 ──
    shutil.copy2(STATUS, BACKUP)
    with open(STATUS, 'wb') as f:
        f.write(out.encode('utf-8'))

    print('[OK] §121 已追加：%d B -> %d B（章节 %d -> %d）'
          % (len(raw), len(out.encode('utf-8')),
             text.count('### §'), chk.count('### §')))
    print('[OK] 备份: %s' % BACKUP)
    return 0


if __name__ == '__main__':
    sys.exit(main())
