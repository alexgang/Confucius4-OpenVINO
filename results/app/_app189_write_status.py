#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app189 —— 把 §119 章节**追加**进 `status/app/STATUS_APP.md`（只追加，不改旧章节）。

🔴🔴🔴 **为什么用脚本而不是 Edit 工具**（沿用 §118 的教训）
------------------------------------------------------------
1. **旧正文一字未删**是硬要求 ⇒ 用「首个章节锚点切片」保住整块；
2. **头部字段替换**要避免「value 自带 key 前缀 ⇒ 写两遍」（§29/§112 两次踩坑）；
3. **换行风格**必须先探测（STATUS 有 LF / CRLF 两种历史状态）⇒ 不能假设；
4. 写完要**逐项自检**：章节数 +1、旧正文整块仍在、头部字段各只出现一次。

🔴 **纪律**：本脚本**只写** `status/app/STATUS_APP.md`；**绝不碰** `CORRECTIONS_APP.md`。
"""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BODY = os.path.join(HERE, '_sec119_body.md')

NEW_LAST_ACK = 'APP-051'           # 本轮无新纠偏条目 ⇒ 不变
NEW_UPDATED = '2026-11-01 02:35'   # Get-Date 实测值（2026-11-01 02:35:09）

#: 头部「当前任务」行（整体替换）
NEW_TASK = (
    '**§119 ✅ 无新纠偏条目（`last_ack` 仍 APP-051）** —— 按 **APP-046**「追平后不空转」继续做，'
    '补上 **「包 ⇄ 仓库 生产模块集合一致性」这一维**（§104 第④层的**反向形态**）：'
    '① §118 的 `app187` 只覆盖「STATUS 引用的产物是否入库」，**不覆盖**「客户包 `app/` 里的模块'
    '与仓库 `live_caption/` 的生产模块集合是否一致」② **方向 B**（包有、仓库没有）⇒ 下次重打包'
    '**会把它丢掉** ⇒ 若它是生产模块 ⇒ 客户机突然缺模块 ③ 实测抓到真实案例：'
    '**包目录 `app/_probe_tts_cuda.py`（3 072 B）仓库从未入库**、含写死开发机路径 `REPO = r"C:\\Users\\Trekker-PTL\\confucius4-openvino"`、'
    'v1.13/v1.5/v1.4 三个包目录都有 ⇒ 🔴 **交付 zip 是干净的**（已被 `pkg_exclude` 排除规则挡在 zip 外，'
    'zip 内 `app/` 只有 **28** 个 `.py`），但**包目录层面**（用户实际运行的目录）确实存在开发机路径泄漏 '
    '④ ⇒ **新增 `app188` 闸门**（orphan 阻断 / dev_only_orphan 提醒 / repo_only 不判负；'
    '**复用 `pkg_exclude.is_app_dev_only()` 作权威判定** ＋ 兜底正则由 T5 强制一致）'
    '⇒ ✅ **鉴别力自检 6/6 PASS** ＋ **真实缺陷形态 PASS** ＋ **真 fresh clone 内复验 PASS**'
    '（clone 内 `repo_live` 指向 `Temp/fc188/live_caption` ⇒ §118 的「写死仓库根」**未复发**）'
    '＋ **28/28 生产模块全部入库** ⇒ 详见 **§119**'
)

#: 头部「阻塞 / 待用户决定」行（整体替换）
NEW_BLOCK = (
    '① 🔴 **需用户实听 3 段 1.2–1.3× 配音素材**（`C:\\Users\\Trekker-PTL\\shared\\app_accel_listen\\`：1.2× / 1.3× / 1.3×）'
    '＋ **reviewer 判定音质 / 不变调 / 可懂** —— 本轮 `app186` 总闸门只覆盖**链路 + 结构 + 数字自洽**'
    '（`ACCEPTED.json.scope` 已明写），**质量判定不在其中**；'
    '② 🔴 **§117 待 reviewer 复核 2 项**（① APP-043「通过」口径 ② `app186` 总闸门 25 条判据口径）'
    '—— ③「`app186` 写死包版本」**已于 §118 闭环**；'
    '③ 🔴 **v1.12 / v1.5 等历史 zip 仍是旧内容**（历史包本轮**未重打**、旧包目录**未删除**（破坏性操作需用户确认））；'
    '④ 🔴 **§115 待 reviewer 复核 5 项**（① `EXECUTION_DEVICES` 返回类型口径——**推翻了 §82 的旧解读** '
    '② `absent`/`unknown` 分离 ③ `talker` 聚合所有桶 ④ App 不调 `build()` ⇒ 第②条不适用 '
    '⑤ TTS 模块 `cp_decode_device` 未被消费 ⇒ App 无需改动）；'
    '⑤ 🔴 **§114 待 reviewer 复核 4 项**（CI 判据口径 / 写法差异 vs 真错误拆分规则 / 多 3 句真错误是否提示用户 / 是否用最新包重跑）；'
    '⑥ 🔴 **宿主 `PYTHONPATH` 污染对历史验收结论的影响范围待 reviewer 确认**（§112 已证明它会让 `torch` 假阳性；'
    '§109/§110 为静态字节比对，未受影响）；'
    '⑦ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入，SHA256 `327f8653…39904` 零改动）；'
    '⑧ 🔴 **§113 待 reviewer 复核 4 项**（版本标识闸门口径 / 「改动说明」归为提醒不阻断 / '
    '`sync_c172`「只改身份行不改内容」设计 / v1.13 改动说明排期）；'
    '⑨ 🆕🔴 **`app188` 的判据口径待 reviewer 复核**（① `orphan` 判**阻断**是否过严 '
    '② `repo_only` **不判负**是否可接受 ③ `dev_only_orphan` 是否应完全以 `pkg_exclude` 为准 —— 本轮已用 T5 强制两者一致）；'
    '⑩ 🆕🔴 **95 处「过期包版本」引用的清点结论待 reviewer 复核**（本轮只清点、未改；多数在 docstring ⇒ '
    '需区分「文档举例」与「真写死」后再动 ⇒ 建议另开一轮专项，**不在本轮扩大改动面**）'
)

#: 头部「已压缩」行里的体积口径（**自指** ⇒ 写后要迭代到稳定）
NEW_SIZE_TAIL = '§119 追加后）。'

#: 「最近更新」区块新增的一条
NEW_ENTRY = (
    '- 2026-11-01 02:35 **§119 无新纠偏条目（`last_ack` 仍 APP-051）** ⇒ 按 APP-046 继续做，'
    '补上 **「包 ⇄ 仓库 生产模块集合一致性」这一维**（§104 第④层的**反向形态**）：'
    '① §118 的 `app187` **不覆盖**「客户包 `app/` 的模块 vs 仓库生产模块集合」 '
    '② **方向 B**（包有、仓库没有）⇒ 下次重打包**会丢掉它** ⇒ 客户机可能突然缺模块 '
    '③ 实测抓到真实案例 **包目录 `app/_probe_tts_cuda.py`（3 072 B）仓库从未入库**、含写死开发机路径、'
    'v1.13/v1.5/v1.4 三处都有 ⇒ 🔴 **交付 zip 干净**（`pkg_exclude` 已排除）但**包目录层面**有开发机路径泄漏；'
    '④ ✅ **新增 `app188` 闸门**（orphan 阻断 / dev_only 提醒 / repo_only 不判负，**复用 `pkg_exclude` 权威判定**）'
    '⇒ 鉴别力自检 **6/6** ＋ 真实形态 PASS ＋ **真 fresh clone 复验 PASS**（clone 内 `repo_live` 指向 clone 自己）'
    '＋ **28/28 生产模块全部入库**'
)


def read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    nl = '\r\n' if b'\r\n' in raw else '\n'
    return raw.decode('utf-8'), nl


def set_field(head, key, value):
    """在头部区替换 `key: value`（value **不得**自带 key 前缀）。"""
    assert not value.startswith(key + ':'), 'value 自带 key 前缀 ⇒ 会写两遍'
    pat = re.compile(r'^(%s:\s*)(.*)$' % re.escape(key), re.M)
    hits = pat.findall(head)
    assert len(hits) == 1, '头部字段 %r 出现 %d 次（应为 1）' % (key, len(hits))
    return pat.sub(lambda m: m.group(1) + value, head, count=1)


def set_line(head, prefix, value):
    """把以 `prefix` 开头的那一整行替换成 `prefix + value`。"""
    lines = head.split('\n')
    hits = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    assert len(hits) == 1, '头部行 %r 出现 %d 次（应为 1）' % (prefix, len(hits))
    lines[hits[0]] = prefix + value
    return '\n'.join(lines)


def main():
    text, nl = read_text(STATUS)

    # ── 1. 备份 ──
    bak = os.path.join(tempfile.gettempdir(),
                       'STATUS_APP_before_sec119_%d.md' % os.getpid())
    shutil.copy2(STATUS, bak)
    print('[bak] %s' % bak)

    # ── 2. 切分 ──
    m = re.search(r'(?m)^### §', text)
    assert m, '找不到章节锚点 `### §`'
    i_anchor = m.start()
    head, body = text[:i_anchor], text[i_anchor:]

    n_before = len(re.findall(r'(?m)^### §', body))
    print('[slice] 章节数 %d；头部 %d B；正文 %d B' % (n_before, len(head), len(body)))

    # ── 3. 追加新章节（**只追加在文件末尾**）──
    with open(BODY, 'r', encoding='utf-8') as f:
        new_body = f.read().rstrip('\n')
    out_body = body.rstrip('\n') + '\n\n' + new_body + '\n'

    # ── 4. 改头部（只动头部区）──
    head = set_field(head, 'last_ack', NEW_LAST_ACK)
    head = set_field(head, '更新时间', NEW_UPDATED)
    head = set_line(head, '当前任务: ', NEW_TASK)
    head = set_line(head, '阻塞 / 待用户决定: ', NEW_BLOCK)

    # ── 5. 「最近更新」区块：追加一条 + 裁掉最旧的（硬约束 ≤ 15 行）──
    m2 = re.search(r'(?ms)^## 最近更新\n(.*?)(?=^## |\Z)', head)
    assert m2, '找不到「最近更新」区块'
    block = m2.group(1)
    lines = [l for l in block.split('\n')]
    while lines and not lines[-1].strip():
        lines.pop()
    merged = [NEW_ENTRY] + lines
    assert len(merged) <= 15, '「最近更新」超 15 行（%d）' % len(merged)
    while len(merged) > 15:
        merged.pop()
    new_block = '\n'.join(merged) + '\n\n'
    head = head[:m2.start()] + '## 最近更新\n' + new_block + head[m2.end():]

    # ── 6. 写回（保持原换行风格）──
    out = head + out_body
    with open(STATUS, 'wb') as f:
        f.write(out.replace('\n', nl).encode('utf-8'))

    # ── 7. 自检 ──
    check, cnl = read_text(STATUS)
    n_after = len(re.findall(r'(?m)^### §', check))
    assert n_after == n_before + 1, '章节数 %d ⇒ %d（应 +1）' % (n_before, n_after)
    old_body_core = body.rstrip('\n')
    assert old_body_core in check, '旧正文整块不在新文件里（被改动！）'
    for k in ('last_ack', '更新时间'):
        c = len(re.findall(r'(?m)^%s:' % re.escape(k), check))
        assert c == 1, '头部字段 %r 出现 %d 次' % (k, c)
    assert re.search(r'(?m)^last_ack: APP-051$', check), 'last_ack 取值不对'
    assert re.search(r'(?m)^更新时间: 2026-11-01 02:35$', check), '更新时间取值不对'
    assert check.rstrip().endswith('不在本轮扩大改动面**）。'), '新章节不在末尾'
    print('[ok] 章节 %d ⇒ %d；旧正文整块保留；头部字段各 1 次；字节 %d'
          % (n_before, n_after, len(check.encode('utf-8'))))


if __name__ == '__main__':
    sys.exit(main())
