#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app100_write_status.py — §100：把 §100 章节**追加**进 `status/app/STATUS_APP.md`。

## 🔴🔴🔴 铁律（记忆 §一，逐条对应实现）

1. 🔴 **STATUS_APP.md 工作区是纯 CRLF**（实测 17 942 行全 CRLF）
   ⇒ 写入**必须 bytes 级定点替换**
   ⇒ 绝不能用 `read().split('\n') + '\n'.join()` 写回
   （那会把**整文件行尾**改掉 ⇒ 违反「旧正文逐字未变」）。
2. 🔴 **只追加**新章节到**文件末尾** ⇒ **不回头改旧章节**。
3. 🔴 **头部 4 字段**只改**头部区**（第一个 `## §` 之前）
   ⇒ 因为 `last_ack:` 等字样**在正文里也出现** ⇒ 全文件替换会误伤。
4. 🔴 **头部 value 不能自带 `key: ` 前缀**（否则出现 `last_ack: last_ack: APP-044`）。
5. 🔴 **「最近更新」≤ 15 行** ⇒ 超了**裁最旧的**。
6. 🔴 **新章节追加在末尾**；**章节之间无空行**。
7. 🔴 写后自检：**原有章节一个不少** ＋ **旧正文逐字未变**。
   （⚠️ STATUS 章节编号有既有跳号 ⇒ 完整性断言写「原有章节一个不少」，
     **别写「§1..§N 全在」**。）
8. 🔴 **头部只改 4 字段行**（「阻塞」行按前缀找，不写死索引）。

## 本轮写入内容

- 追加章节：`## §100 ...`（正文在 `results/app/_app100_section.md`）
- 头部：`last_ack`（**保持 APP-044**，§101 已改过）、`更新时间`、`当前任务`、`阻塞 / 待用户决定`
  ⇒ ⚠️ **`last_ack` 不动**：§101 会话已改成 APP-044 ⇒ 本轮**无更大编号**可确认。
"""
from __future__ import annotations

import io
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
SECTION = os.path.join(REPO, 'results', 'app', '_app100_section.md')

NEW_UPD_TIME = '2026-10-30 09:47'
NEW_TASK = (
    '**§100 🔴🔴🔴 APP-039/040 第二轮审计又查出 4 处断链（G/H/I/J）⇒ 已全部修复  '
    '＋ 修掉 4 处「我自己写的验收判据缺陷」＋ 客户包 v1.11 已定点同步并持锁重打 zip**'
    '（巡检：开工时 APP-042 = `last_ack` ⇒ 无新条目，第 27 次同一口径复核；'
    '**本轮中途 reviewer 追加 APP-043/044 ⇒ 由并发会话执行，见 §101**）'
    '⇒ ✅ 断链 **G** `spk=None` 沿用上一个人的音色（串音，违反 APP-040②）'
    '**H** jsonl 缺 `voice_spk`/`voice_kind` ⇒ reviewer 算不出 APP-039 验收①混淆表 '
    '**I** CLI 路径完全没有说话人标签（GUI 有、CLI 无，违反 APP-040④）'
    '**J** ASR 侧 `on_spk_update` 无任何调用方 ⇒ 晚到标签永远不到 '
    '⇒ ✅ 修掉 **4 处判据自身缺陷**（`app155` 的 REPO 路径 / 注入缩进 / 正则误命中 / '
    '**docstring 命中导致判据恒真** ⇒ 改 AST `ast.Call`）＋ 修掉「反证读盘绕过注入」'
    '⇒ ✅ `app155` **36/36 PASS**（反证全命中 + 固定基线 `b741240` 四条全 FAIL）'
    '＋ **包内 v1.11 源码复跑同套判据 36/36** ⇒ ✅ 回归 10 脚本全绿'
    '（`app142` 同步前 20/2 ⇒ **同步后 22/22**）⇒ ✅ 定点同步 3 文件'
    '（归一化后与仓库逐字节一致 + 备份放**包外**）⇒ ✅ **持锁重打 v1.11**'
    '（`app-pack` PID 10540 / 09:07:13 / 安静窗口等 465 s 后通过 / 14 203 文件逐字节一致 / '
    'zip **11 218 213 281 B** / SHA256 `72068c32…17a20` / MANIFEST `version=1.11`）'
    '⇒ 🔴🔴🔴 **zip 是半交付**（`app156` 复核 **4 PASS / 4 FAIL** ⇒ 3 个文件 DIFF + '
    '`speaker_assets.py` 不在 zip 内）⇒ 🔴 **不写「已交付」**'
    '⇒ 🔴 **断链 G 首版有 BLOCKING 回归**（打死 APP-027⑤ `follow_speaker`）⇒ 已由 **§101.4** '
    '模式感知版修掉 ⇒ **以 §101.4 为准**'
)

NEW_BLOCK = (
    '① 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（APP-042 明文要求，本模块不得自做）；'
    '② 🔴 **用户实听 3 段 1.2–1.3× 配音未做**（3 段 wav 已落盘 '
    '`results/app/app042_soak_run4/clips_1p2_to_1p3/`，但 `.gitignore` 忽略 `*.wav` ⇒ 不入库）；'
    '③ 🔴 **客户包 v1.11 的 zip 是半交付**（含 §100 修复，**不含** §101 回归修复与 APP-044 的 '
    '`speaker_assets.py` / 16 MB 资产）⇒ 需重打；'
    '④ 🔴 **重打包需持锁但锁被外部占用**（`EXT-p1-real` PID 41788 / 09:33:28，'
    'ctypes `OpenProcess` 判 **alive**）⇒ **本轮不抢锁、不重打**；'
    '⑤ 🔴 **APP-043 真机验收未做**（SPE Q&A densest_5min / APP-041 `pythonw` 冷启动 / '
    'GUI 路径 APP-042 / 3 段 1.2–1.3× 配音）；'
    '⑥ 🔴 **APP-044 精度形态待 reviewer 裁定**（FP16 还是 FP32 ⇒ 代码无需改，换目录重打即可）'
    '＋ **16 MB 资产尚未进 zip** ⇒ 客户机旁路**仍会关闭**；'
    '⑦ 🔴 **APP-039/040 真机 NPU 双说话人音色按句切换未做**（仅离线 `app150`/`app155`/`app157`）；'
    '⑧ 🔴 **§101 会话与本会话的 App 侧文件仍为未提交状态**（§100 的 3 个文件 + '
    '`speaker_assets.py` + `sync_c162/164/165/166` + `app155/156/157/158` + '
    '`status/app/STATUS_APP.md`）⇒ 需**逐文件** `git add`（**不用 `-A`**）'
    '⇒ **绝不提交** `status/app/CORRECTIONS_APP.md`；'
    '⑨ 🔴 **本轮未修改** `CORRECTIONS_APP.md`（只读；本轮中途被 reviewer 追加 APP-043/044 ⇒ '
    'SHA256 `c50dcdd1…` → `08e231a2…` / 108 783 B → 111 198 B / mtime 2026-10-30 08:50:04）'
)


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def main() -> int:
    orig = read_bytes(STATUS)
    assert orig.count(b'\r\n') == orig.count(b'\n'), '❌ 原文件不是纯 CRLF'
    n_lines_before = orig.count(b'\r\n')

    # ── ① 抓出原章节标题（完整性基线）────────────────────────────
    orig_secs = re.findall(rb'^## \xc2\xa7(\d+)', orig, flags=re.M)
    orig_secs = [s.decode() for s in orig_secs]
    print('原章节数 = %d（编号 %s … %s）'
          % (len(orig_secs), orig_secs[0], orig_secs[-1]))

    # ── ② 找头部区（第一个 `## §` 之前）─────────────────────────
    first_sec = orig.find(b'\r\n## \xc2\xa7')
    assert first_sec > 0, '❌ 找不到章节起点'
    head = orig[:first_sec]
    body = orig[first_sec:]

    # 🔴🔴🔴 头部区**混进了 1 个裸 LF**（§101 会话写入时留下）
    #   ⇒ 必须先归一化为 CRLF，否则整个文件就不是纯 CRLF。
    #   ⚠️ **只归一化头部区**：正文区（body）**一个字节都不许动**
    #   ⇒ 「旧正文逐字未变」仍然成立。
    n_bare_head = head.count(b'\n') - head.count(b'\r\n')
    if n_bare_head:
        head = head.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        print('⚠️ 头部区有 %d 个裸 LF ⇒ 已归一化为 CRLF' % n_bare_head)

    # ── ③ 头部：只改「更新时间」「当前任务」「阻塞 / 待用户决定」────
    #    ⚠️ `last_ack` **不动**（§101 已改成 APP-044 ⇒ 本轮无更大编号）
    head_s = head.decode('utf-8')

    def set_field(text, key, value):
        # 🔴🔴🔴 正则必须**排除 `\r`**：`(?m)^key: .*$` 中 `.` 会**吞掉行尾的 `\r`**
        #   （`$` 匹配 `\n` 之前）⇒ 替换后该行变成**裸 LF** ⇒ 整个文件不再纯 CRLF。
        #   ⇒ 用 `[^\r\n]*` 只吃到 `\r` 之前 ⇒ 行尾 `\r\n` **原样保留**。
        pat = re.compile(r'(?m)^%s: [^\r\n]*' % re.escape(key))
        assert pat.search(text), '❌ 头部区找不到字段 %s' % key
        return pat.sub(lambda _m: '%s: %s' % (key, value), text, count=1)

    head_s = set_field(head_s, '更新时间', NEW_UPD_TIME)
    head_s = set_field(head_s, '当前任务', NEW_TASK)
    head_s = set_field(head_s, '阻塞 / 待用户决定', NEW_BLOCK)

    # ── ④ 「最近更新」：头部末尾的列表 ⇒ 插一行在最前，超 15 行裁最旧
    lines = head_s.split('\r\n')
    ru_idx = None
    for i, ln in enumerate(lines):
        # ⚠️ 实测标题是 `## ## 最近更新`（§101 写入时多了一个 `#`）
        #   ⇒ 🔴 **只能用 `replace('#','')` 全量去掉**才认得出来
        #   （`strip('#')` 只去**两端连续**的 # ⇒ `## ## 最近更新` 会剩 `## 最近更新` ⇒ 不等）
        if ln.replace('#', '').strip() == '最近更新':
            ru_idx = i
            break
    assert ru_idx is not None, '❌ 找不到「最近更新」'
    upd = []
    j = ru_idx + 1
    while j < len(lines) and lines[j].strip():
        upd.append(lines[j])
        j += 1
    new_line = ('%s §100 🔴🔴🔴 **APP-039/040 第二轮审计 4 处断链（G/H/I/J）⇒ 全部修复 ＋ '
                '4 处判据自身缺陷已修 ＋ 客户包 v1.11 持锁重打 zip（**zip 半交付 ⇒ 不写「已交付」）**'
                '**（巡检：开工时 APP-042 = `last_ack` ⇒ 无新条目；中途 reviewer 追加 APP-043/044 ⇒ '
                '见 §101）⇒ ✅ `app155` **36/36**（反证全命中 + 基线 `b741240` 四条全 FAIL）＋ '
                '**包内源码复跑同套判据 36/36** ⇒ ✅ 回归 10 脚本全绿（`app142` 20/2 ⇒ **22/22**）'
                '⇒ ✅ 定点同步 3 文件 ⇒ ✅ **持锁重打 v1.11**（PID 10540 / 安静窗口 465 s / '
                '14 203 文件逐字节一致）⇒ zip **11 218 213 281 B** / SHA256 `72068c32…17a20` '
                '⇒ 🔴 **zip 半交付**（`app156` 4 PASS / 4 FAIL）⇒ 🔴 **断链 G 首版回归由 §101.4 修掉**'
                '⇒ 🔴 **本条需等 reviewer 复核**') % NEW_UPD_TIME
    upd.insert(0, new_line)
    # 🔴 ≤ 15 行 ⇒ 超了裁**最旧的**（末尾）
    if len(upd) > 15:
        upd = upd[:15]
    lines = lines[:ru_idx + 1] + upd + lines[j:]
    head_new = '\r\n'.join(lines)

    # ── ⑤ 追加 §100 章节到**文件末尾** ────────────────────────────
    sec = read_bytes(SECTION).decode('utf-8').replace('\r\n', '\n').replace('\n', '\r\n')
    sec = sec.rstrip('\r\n')
    # 🔴 章节之间**无空行** ⇒ 直接接在正文末尾
    new_body = body + sec.encode('utf-8')
    if not new_body.endswith(b'\r\n'):
        new_body += b'\r\n'

    out = head_new.encode('utf-8') + new_body

    # 🔴 写盘前自检 ────────────────────────────────────────────────
    # ⚠️ **不能要求「整文件纯 CRLF」** ⇒ §101 会话追加的 §101 章节里
    #   **本身就有裸 LF**（它自己写的）⇒ 而正文区**一个字节都不许我改**
    #   （铁律：旧正文逐字未变）⇒
    #   ⇒ 断言范围 = **头部区 + 我新增的 §100 章节**必须纯 CRLF；
    #     正文区残留的裸 LF **如实计数并报出**（不掩盖、也不擅自「修正」别人的正文）。
    n_bare_body_before = body.count(b'\n') - body.count(b'\r\n')
    new_sec_b = sec.encode('utf-8')
    assert new_sec_b.count(b'\r\n') == new_sec_b.count(b'\n'), \
        '❌ 新增章节 §100 不是纯 CRLF'
    head_b = head_new.encode('utf-8')
    assert head_b.count(b'\r\n') == head_b.count(b'\n'), '❌ 头部区不是纯 CRLF'
    print('ℹ️ 正文区原有裸 LF = %d（§101 会话留下 ⇒ 本轮不擅改，只如实计数）'
          % n_bare_body_before)
    # 旧正文逐字未变（**归一化 LF 后**比对 ⇒ 不受行尾风格差异影响）
    old_body_kept = out[len(head_b):]
    def _nlf(x):
        return x.replace(b'\r\n', b'\n')
    assert _nlf(old_body_kept).startswith(_nlf(body)), '❌ 旧正文被改动'    # 原有章节一个不少
    new_secs = [s.decode() for s in re.findall(rb'^## \xc2\xa7(\d+)', out, flags=re.M)]
    for s in orig_secs:
        assert s in new_secs, '❌ 原有章节 §%s 丢失' % s
    assert '100' in new_secs, '❌ §100 未写入'
    assert new_secs.count('100') == 1, '❌ §100 重复'
    # §101 不在我的正文里出现（避免抢它的章节）
    assert b'## \xc2\xa7101' not in sec.encode('utf-8'), '❌ §100 正文含 §101 标题'
    # 头部不能出现「key: key:」
    for k in ('last_ack', '更新时间', '当前任务', '阻塞 / 待用户决定'):
        assert ('%s: %s:' % (k, k)) not in head_new, '❌ 头部 %s 重复前缀' % k
    # 最近更新 ≤ 15 行
    assert len(upd) <= 15, '❌ 最近更新超 15 行'

    with open(STATUS, 'wb') as f:
        f.write(out)

    # ── ⑥ 写盘后复检 ──────────────────────────────────────────────
    back = read_bytes(STATUS)
    assert back == out, '❌ 写盘后内容不一致'
    print('✅ 已写入 §100')
    print('   原字节 %d → 新字节 %d' % (len(orig), len(back)))
    print('   原行数 %d → 新行数 %d' % (n_lines_before, back.count(b'\r\n')))
    print('   章节数 %d → %d' % (len(orig_secs), len(new_secs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
