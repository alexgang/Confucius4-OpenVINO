"""app053_append_status44.py —— 把 §44 追加到 STATUS_APP.md（幂等 + 硬约束）。

🔴 纪律（§43 的教训）：
  - **必须保留 head**（前 24 行）⇒ `out = head + new_body`；
  - 「最近更新」≤ **15 行**是硬约束；
  - 头部只改 4 个字段行（`last_ack` / `更新时间` / `当前任务` / `阻塞 / 待用户决定`）；
  - 写前备份、写后校验章节数与头部。
"""
from __future__ import annotations

import io
import os
import re
import shutil

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
BODY = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_sec44_body.md'
BAK = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_STATUS_APP_before_sec44.bak'

NEW_TASK = ('**§44 🔴🔴 查出「草稿→正式稿」配对存在**跨段离群错配** ⇒ 正式稿译文被搬到'
            '**几十段之外**（MT 通知 13 的「假前缀」在 **App 渲染层同样成立** ⇒ 通知 13 §13.1 '
            '「产品不受影响」的结论在 App 层**不成立**）：产品现版 95 对里 **2 对**离群 —— '
            '`DRAFT::That`(seg22)→seg107（跨 **85** 段）、`DRAFT::Okay`(seg6)→seg39（跨 **33** 段）'
            '⇒ 后果：正式稿译文被**搬到错误的段**（用户可见错位）⇒ 根因：'
            '`norm_src` 删撇号 ⇒ 假前缀成立 + 排序键**无「段相邻性」这一维** ⇒ '
            '**修法已就绪**：加 `MAX_SEG_SPAN = 2`（依据 `caption_render` 自身 docstring '
            '已写明的「草稿 seg = 段尾半句所在段 / 正式稿 seg = 凑齐后提交段」）⇒ 实测 '
            '**配对数 95→95（零损失）/ 覆盖率 0.8716 不变 / 跨段 max 85→2 / 错配 2→0 / 倒流 0 / '
            '一对一不破 / 短草稿替换能力保留** + 既有 `test_app015` **23/23 + BUG 5/5 零回归** ⇒ '
            '🔴 **本轮未改产品代码**（候选另存 + M9 替换块已备好 ⇒ **等 reviewer 裁定**）')

NEW_BLOCK = ('① 🔴 **等 reviewer 裁定**：是否采纳「跨段上限 '
             '`MAX_SEG_SPAN = 2`」（候选 `results/app/app053_caption_render_segcap_candidate.py` '
             '+ M9 替换块 `results/app/app053_m9_assertion_candidate.txt` 已备好，'
             '实测零损失零回归）；② 🔴 **需回复 MT 通知 13**：其 §13.1「产品不受影响」'
             '**在 App 渲染层不成立**（确有跨段 85/33 段错配），但其 §13.4 的「词边界」'
             '**抓不住** `Okay`（逗号 ⇒ 词边界合法）⇒ 建议改用「跨段距离」判据；'
             '③ ✅ **v1.5 已出包** ⇒ 方案 C 未进包 ⇒ 本缺陷**当前不影响已交付 v1.5**；'
             '④ 🔴 **§42.3 修复待用户实机确认**（GUI 日志应出现「输出设备解析 … → 播放索引 N」'
             '与「实际输出: <设备名>」）；⑤ 🔴 **§43 闸门修复待端到端验证**'
             '（需下一次 `pack_v13.py` 真实跑一次）；⑥ ⛔ **OV 的 CUDA plugin 不引入**（§39.5 不变）；'
             '⑦ ⛔ **APP-017「检查点 3」**由并发 App 会话在做 ⇒ 本会话不重复跑；'
             '⑧ ⛔ **WER +2.6pp 主因**未定位；'
             '⑨ ✅ **APP-015 方案 C 渲染层验收 23/23**，但 `translator.py` 合入仍待 MT 移交'
             '（APP-009② / H-014，App 不代提交）；⑩ ⛔ 包体 10.45 GiB 优化未做；'
             '⑪ ⛔ V7 残句代价待确认；⑫ ⛔ 集显 F32 TTS 慢（首包 33.9 s）')

NEW_UPDATES = [
    '01:56 §44 🔴🔴 **查出「草稿→正式稿」配对的跨段离群错配**：产品现版 95 对里 **2 对**离群（`That` 跨 **85** 段、`Okay` 跨 **33** 段）⇒ **正式稿译文被搬到错误的段**（用户可见错位）',
    '01:56 §44 🔴 **通知 13 的「假前缀」在 App 渲染层同样成立** ⇒ 其 §13.1「产品不受影响」的结论**在 App 层不成立**（已核实）',
    '01:56 §44 🔴 **根因**：`norm_src` 删撇号 ⇒ 假前缀成立 + 排序键**无「段相邻性」这一维** ⇒ 两条草稿都只有 4 字符',
    '01:56 §44 ✅ **修法已就绪**：加 `MAX_SEG_SPAN = 2`（依据 `caption_render` 自身 docstring 已写明的段相邻语义）⇒ **配对数 95→95 零损失 / 覆盖率不变 / 跨段 max 85→2 / 错配 2→0**',
    '01:56 §44 ✅ **零回归**：既有 `test_app015` **REAL 23/23 + BUG 5/5 PASS**；`app047` 唯一 FAIL = **M9 前提已过期**（已备替换块 ⇒ 实测 **29/29 PASS**）',
    '01:56 §44 🔴 **「词边界」判据抓不住 `Okay`**（逗号 ⇒ 词边界合法）⇒ 通知 13 §13.4 的第 2 步**单独用不足** ⇒ 已回告 MT',
    '01:56 §44 ✅ **方案 C 未进交付包**（v1.5 包内 `caption_render` 命中 **0**）⇒ 本缺陷**当前不影响已交付 v1.5** ⇒ 未重打包、未发 FTP',
    '01:56 §44 🔴 **本轮未改产品代码** ⇒ `live_caption/caption_render.py` 保持 HEAD 原样 ⇒ 等 reviewer 裁定',
]

OLD_UPDATES = [
    '01:45 §43 🔴🔴 **修掉「安静窗口闸门把在等锁的协作方误判成干扰源」⇒ 互等死锁**',
    '01:45 §43 ✅ **修法**：按 **CPU 时间增量**（`GetProcessTimes`）分三类 —— `busy` / `idle` / `unknown`',
    '01:45 §43 ✅ **首次采样只建基线、不下结论** ⇒ 解决 MT 通知 12 §12.5 的「第一次必然判 dirty」',
    '01:45 §43 ✅ **验收 REAL 18/18 PASS + BUG 3/3 命中** ⇒ **未回归**',
    '01:45 §43 ✅ 同口径推广到 App 自己的「检查点 3」闸门',
    '01:45 §43 ✅ **`app052` 回环证据补齐 4 例** ⇒ ② 层通过',
    '01:45 §43 ✅ **交付侧只读复核**：v1.5 zip 11 216 089 426 B / 13 982 条目 ⇒ 不重打包',
]


def main():
    src = io.open(STATUS, encoding='utf-8').read()
    lines = src.split('\n')

    # ── 1) 找 head 与正文分界 ────────────────────────────────────────
    idx = None
    for i, l in enumerate(lines):
        if l.startswith('## §1 '):
            idx = i
            break
    assert idx is not None, '未找到 ## §1'
    head = lines[:idx]
    body = lines[idx:]
    print(f'head 行数 = {len(head)}，正文起始行 = {idx + 1}')

    # ── 2) 幂等：若已有 §44 ⇒ 跳过追加 ───────────────────────────────
    already = any(l.startswith('## §44') for l in body)
    if already:
        print('已存在 §44 ⇒ 跳过追加（幂等）')
    else:
        body = body + io.open(BODY, encoding='utf-8').read().split('\n')

    # ── 3) 头部 4 字段行 ────────────────────────────────────────────
    def set_field(text, key, value):
        pat = re.compile(r'^(' + re.escape(key) + r':).*$', re.M)
        assert len(pat.findall(text)) == 1, f'{key} 行命中 {len(pat.findall(text))} 次'
        return pat.sub(lambda m: m.group(1) + ' ' + value, text, count=1)

    headtext = '\n'.join(head)
    headtext = set_field(headtext, 'last_ack', 'APP-017')
    headtext = set_field(headtext, '更新时间', '2026-10-26 01:56')
    headtext = set_field(headtext, '当前任务', NEW_TASK)
    headtext = set_field(headtext, '阻塞 / 待用户决定', NEW_BLOCK)
    head = headtext.split('\n')

    # ── 4) 「最近更新」区块 ≤ 15 行 ──────────────────────────────────
    try:
        s = head.index('## 最近更新')
    except ValueError:
        raise SystemExit('未找到「## 最近更新」')
    e = s + 1
    while e < len(head) and not head[e].startswith('## '):
        e += 1
    merged = NEW_UPDATES + OLD_UPDATES
    assert len(merged) <= 15, f'最近更新 {len(merged)} 行 > 15 ⇒ abort'
    # 🔴 保留区块尾部原有的**空行**（基线里「最后一条更新」与「## §1」之间有 1 个空行）
    #   ⇒ 找出 e 之前的连续空行，一并保留。
    tail_blanks = 0
    k = e
    while k - 1 > s and head[k - 1].strip() == '':
        tail_blanks += 1
        k -= 1
    upd = ['## 最近更新'] + [f'- {m}' for m in merged] + [''] * max(tail_blanks, 1)
    head = head[:s] + upd + head[e:]
    print(f'最近更新行数 = {len(merged)}（上限 15），尾部空行 = {max(tail_blanks, 1)}')

    # ── 5) 写盘 ──────────────────────────────────────────────────────
    shutil.copy(STATUS, BAK)
    print(f'已备份 → {BAK}（{os.path.getsize(BAK)} B）')
    out = '\n'.join(head) + '\n'.join(body)
    io.open(STATUS, 'w', encoding='utf-8', newline='\n').write(out)
    print(f'已写入 {STATUS}（{os.path.getsize(STATUS)} B）')

    # ── 6) 写后校验 ──────────────────────────────────────────────────
    chk = io.open(STATUS, encoding='utf-8').read()
    n_sec = len(re.findall(r'^## §', chk, re.M))
    print(f'章节数 = {n_sec}')
    assert 'last_ack: APP-017' in chk, '头部 last_ack 丢失'
    assert '更新时间: 2026-10-26 01:56' in chk, '头部更新时间丢失'
    assert '## §44' in chk, '§44 未写入'
    # 旧正文逐字未变：追加模式下应满足「**旧正文是新正文的前缀**」
    # （🔴 首版这里写成 `old_body == new_body` ⇒ 追加后必然不等 ⇒ 误报 abort；
    #    正确判据 = 前缀关系 + 新增内容恰好是 §44。）
    old_src = io.open(BAK, encoding='utf-8').read()
    old_body = old_src[old_src.index('## §1 '):].rstrip('\n')
    new_body = chk[chk.index('## §1 '):].rstrip('\n')
    is_prefix = new_body.startswith(old_body)
    added = new_body[len(old_body):] if is_prefix else ''
    print(f'旧正文是新正文的前缀 = {is_prefix}')
    print(f'新增内容长度 = {len(added)}，以 §44 开头 = {added.lstrip().startswith("## §44")}')
    assert is_prefix, '旧正文被改动 ⇒ abort'
    assert added.lstrip().startswith('## §44'), '新增内容不是 §44 ⇒ abort'
    assert '## §44' in chk, '§44 未写入'
    print('✅ 校验通过')


if __name__ == '__main__':
    main()
