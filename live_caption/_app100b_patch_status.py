#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app100b_patch_status.py — §100 补充：把 §100.7.1/§100.7.2 追加到 §100 章节末尾。

## 为什么需要补丁（而不是重写 §100）

§100 已随 commit `ff031da` 入库 ⇒ **不能改它的既有正文**（铁律：只追加）。
本轮补充了两条**实测事实**：
- §100.7.1：包目录层面已闭环（4 文件与仓库逐字节一致）
- §100.7.2：重打 v1.12 因**目录被外部会话活占用**而中止（干净的失败）

⇒ 做法：**在 §100 章节末尾追加小节**（§100.12），并更新**头部 3 个字段**。

## 🔴 铁律（同 §100 写入器）

- STATUS 是**纯 CRLF** ⇒ **bytes 级定点替换**；
- 头部字段只在**第一个 `## §` 之前**替换；正则用 `[^\r\n]*`（**否则 `.` 会吞掉 `\r`**）；
- 「最近更新」**≤ 15 行** ⇒ 超了裁最旧的；
- 写后自检：**原有章节一个不少** ＋ **旧正文逐字未变**；
- ⚠️ **不碰 `last_ack`**（仍为 APP-044，本轮无更大编号）。
"""
from __future__ import annotations

import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
SECTION = os.path.join(REPO, 'results', 'app', '_app100_section.md')

NEW_UPD_TIME = '2026-10-30 09:48'
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
    '⇒ ✅ **包目录层面已闭环**（4 文件与仓库**逐字节一致**：含 §101 回归修复 + APP-044 的 '
    '`speaker_assets.py`）⇒ 🔴🔴🔴 **zip 仍是半交付**（`app156` 复核 **4 PASS / 4 FAIL**）'
    '⇒ 🔴 **重打 v1.12 失败**（v1.11 目录被 **PID 27744** `ext.bridge` 活占用 ⇒ '
    '`PermissionError WinError 5` ⇒ **干净的失败**：无 v1.12 目录、无 `zip.tmp`、v1.11 完好）'
    '⇒ 🔴 **不抢锁、不杀进程、不写「已交付」**'
    '⇒ 🔴 **断链 G 首版有 BLOCKING 回归**（打死 APP-027⑤ `follow_speaker`）⇒ 已由 **§101.4** '
    '模式感知版修掉 ⇒ **以 §101.4 为准**'
)

NEW_BLOCK = (
    '① 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（APP-042 明文要求，本模块不得自做）；'
    '② 🔴 **用户实听 3 段 1.2–1.3× 配音未做**（3 段 wav 已落盘 '
    '`results/app/app042_soak_run4/clips_1p2_to_1p3/`，但 `.gitignore` 忽略 `*.wav` ⇒ 不入库）；'
    '③ 🔴 **客户包 v1.11 的 zip 是半交付**（含 §100 修复，**不含** §101 回归修复与 APP-044 的 '
    '`speaker_assets.py` / 16 MB 资产）⇒ 需重打；'
    '④ 🔴 **重打包的两个阻塞都在外部**：① `shared/MACHINE_LOCK` 由 `EXT-p1-real` PID 40840 '
    '（09:42:44）持有，`OpenProcess` 判 **alive**；② v1.11 目录被 **PID 27744** '
    '（`...v1.11\python\python.exe -m ext.bridge`）**活占用** ⇒ 同卷改名 `PermissionError WinError 5` '
    '⇒ **需外部会话先释放目录与锁**才能闭环（本轮不抢锁、不杀进程）；'
    '⑤ 🔴 **APP-043 真机验收未做**（SPE Q&A densest_5min / APP-041 `pythonw` 冷启动 / '
    'GUI 路径 APP-042 / 3 段 1.2–1.3× 配音）；'
    '⑥ 🔴 **APP-044 精度形态待 reviewer 裁定**（FP16 还是 FP32 ⇒ 代码无需改，换目录重打即可）'
    '＋ **16 MB 资产尚未进 zip** ⇒ 客户机旁路**仍会关闭**；'
    '⑦ 🔴 **APP-039/040 真机 NPU 双说话人音色按句切换未做**（仅离线 `app150`/`app155`/`app157`）；'
    '⑧ 🔴 **§100 已入库**（commit `ff031da` / 10 文件 / +1866−16 / 普通 push ＋ `HEAD == origin/main`）'
    '⇒ 仅 `status/app/STATUS_APP.md` 仍待补本轮补充小节；'
    '⑨ 🔴 **本轮未修改** `CORRECTIONS_APP.md`（只读；本轮中途被 reviewer 追加 APP-043/044 ⇒ '
    'SHA256 `c50dcdd1…` → `08e231a2…` / 108 783 B → 111 198 B / mtime 2026-10-30 08:50:04）'
)

APPEND_BODY = """
### 100.12 🔴 **补充（2026-10-30 09:48）：包目录已闭环 ＋ 重打 v1.12 因目录被活占用而中止**

> ⚠️ 本小节**追加**于 §100 入库（commit `ff031da`）之后 ⇒ **不改 §100 的既有正文**。

#### 100.12.1 ✅ **包目录层面已闭环**（与仓库逐字节一致）

- 🔴 实测（09:45，归一化 LF 后 SHA256 前 16 位）：
  | 文件 | 仓库 | 包内 v1.11 | 判定 |
  |---|---|---|---|
  | `live_caption_app.py` | `e5440190eadcef1f` | `e5440190eadcef1f` | ✅ MATCH |
  | `tts_worker.py` | `73c756420fd1c1ee` | `73c756420fd1c1ee` | ✅ MATCH |
  | `speaker_tracker.py` | `4b03f19fbaf127e8` | `4b03f19fbaf127e8` | ✅ MATCH |
  | `speaker_assets.py` | `e4d655a69e7dfdcd` | `e4d655a69e7dfdcd` | ✅ MATCH |
  ⇒ ⇒ **包目录 = 仓库**（含 §100 断链 G/H/I/J ＋ §101 回归修复 ＋ APP-044 的 `speaker_assets.py`）
  ⇒ **「已交付」在包目录层面成立**；**仅 zip 层面仍不成立**（见 §100.7）。

#### 100.12.2 🔴 **重打 v1.12 的尝试：因目录被外部会话活占用而中止**（**干净的失败**）

- **命令**：`python pack_v13.py --version 1.12 --lock-timeout 7200`（自动等锁，不抢）
  ⇒ 版本号推算正确：`discover_max_version()=1.11` ⇒ `bump_version()=1.12`。
- 🔴 **失败点**：源目录同卷改名 `Confucius4_LiveCaption_v1.11` → `...v1.12` 时
  **`PermissionError: [WinError 5] 拒绝访问`**。
- 🔴 **根因（实测）**：`Win32_Process` 查到 **PID 27744** 正在运行
  `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.11\\python\\python.exe -m ext.bridge
  --host 127.0.0.1 --port 8792 --delay 10.0 --real --target-lang en`
  ⇒ **该目录被外部会话（`EXT-p1-real`）活占用** ⇒ 不可改名。
  ⇒ **本模块不杀别人的进程**（铁律：别人活只能等不能杀）⇒ **放弃重打**。
- ✅ **失败是干净的**（无半成品）：
  | 检查 | 结果 |
  |---|---|
  | `Confucius4_LiveCaption_v1.12` 目录 | **不存在**（未产生半成品）|
  | `*.zip.tmp` 残留 | **无** |
  | v1.11 目录完好性 | `app/` 28 个 `.py` ＋ `MANIFEST.json` 22 582 B（09:15）均在位 |
  | `shared/MACHINE_LOCK` | 仍由 `EXT-p1-real` PID 40840（09:42:44）持有；`OpenProcess` 判 **alive, exit code 259** ⇒ **未抢锁** |
- ⇒ **结论**：**zip 的闭环需要外部会话先释放 v1.11 目录 ＋ 释放机器锁**，才能重打。
  ⇒ 本轮**不写「已交付」**（zip 层面），**不抢锁**，**不杀进程**。
"""


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def main() -> int:
    orig = read_bytes(STATUS)
    first_sec = orig.find(b'\r\n## \xc2\xa7')
    assert first_sec > 0, '❌ 找不到章节起点'
    head = orig[:first_sec]
    body = orig[first_sec:]

    # 🔴 头部区可能混有裸 LF（§101 会话留下的）⇒ 归一化（**只动头部区**）
    n_bare_head = head.count(b'\n') - head.count(b'\r\n')
    if n_bare_head:
        head = head.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        print('⚠️ 头部区裸 LF %d 个 ⇒ 已归一化' % n_bare_head)

    head_s = head.decode('utf-8')

    def set_field(text, key, value):
        # 🔴🔴🔴 正则**必须排除 `\r`**：`(?m)^key: .*$` 的 `.` 会吞掉行尾 `\r`
        #   （`$` 匹配 `\n` 之前）⇒ 替换后该行变裸 LF ⇒ 文件不再纯 CRLF。
        pat = re.compile(r'(?m)^%s: [^\r\n]*' % re.escape(key))
        assert pat.search(text), '❌ 头部区找不到字段 %s' % key
        return pat.sub(lambda _m: '%s: %s' % (key, value), text, count=1)

    head_s = set_field(head_s, '更新时间', NEW_UPD_TIME)
    head_s = set_field(head_s, '当前任务', NEW_TASK)
    head_s = set_field(head_s, '阻塞 / 待用户决定', NEW_BLOCK)

    lines = head_s.split('\r\n')
    ru_idx = None
    for i, ln in enumerate(lines):
        # ⚠️ 标题实测可能是 `## ## 最近更新` ⇒ 只能用 `replace('#','')` 全量去 #
        if ln.replace('#', '').strip() == '最近更新':
            ru_idx = i
            break
    assert ru_idx is not None, '❌ 找不到「最近更新」'
    upd = []
    j = ru_idx + 1
    while j < len(lines) and lines[j].strip():
        upd.append(lines[j])
        j += 1
    new_line = (
        '%s §100 🔴🔴🔳 **补充：包目录已闭环（4 文件与仓库逐字节一致）＋ 重打 v1.12 因 '
        'v1.11 目录被外部会话 PID 27744（ext.bridge）活占用而中止（干净的失败：无 v1.12 目录 / '
        '无 zip.tmp / v1.11 完好）＋ 锁仍由 EXT-p1-real PID 40840 持有（alive）⇒ 不抢锁、不杀进程**'
        '⇒ **zip 仍是半交付 ⇒ 不写「已交付」** ⇒ ✅ §100 已入库（commit `ff031da`）'
        '⇒ 🔴 **本条需等 reviewer 复核**') % NEW_UPD_TIME
    upd.insert(0, new_line)
    if len(upd) > 15:
        upd = upd[:15]
    lines = lines[:ru_idx + 1] + upd + lines[j:]
    head_new = '\r\n'.join(lines)

    # ── 追加 §100.12 到**文件末尾**（§100 章节之后）─────────────────
    add = APPEND_BODY.replace('\r\n', '\n').replace('\n', '\r\n').strip('\r\n')
    add_b = add.encode('utf-8')
    assert add_b.count(b'\r\n') == add_b.count(b'\n'), '❌ 追加小节不是纯 CRLF'
    new_body = body.rstrip(b'\r\n') + b'\r\n' + add_b + b'\r\n'

    out = head_new.encode('utf-8') + new_body

    # 🔴 自检
    head_b = head_new.encode('utf-8')
    assert head_b.count(b'\r\n') == head_b.count(b'\n'), '❌ 头部区不是纯 CRLF'
    def _nlf(x):
        return x.replace(b'\r\n', b'\n')
    assert _nlf(out[len(head_b):]).startswith(_nlf(body)), '❌ 旧正文被改动'
    osecs = [s.decode() for s in re.findall(rb'^## \xc2\xa7(\d+)', orig, flags=re.M)]
    nsecs = [s.decode() for s in re.findall(rb'^## \xc2\xa7(\d+)', out, flags=re.M)]
    for s in osecs:
        assert s in nsecs, '❌ 原有章节 §%s 丢失' % s
    assert nsecs.count('100') == 1, '❌ §100 重复'
    for k in ('last_ack', '更新时间', '当前任务', '阻塞 / 待用户决定'):
        assert ('%s: %s:' % (k, k)) not in head_new, '❌ 头部 %s 重复前缀' % k
    assert len(upd) <= 15, '❌ 最近更新超 15 行'

    with open(STATUS, 'wb') as f:
        f.write(out)
    back = read_bytes(STATUS)
    assert back == out, '❌ 写盘后内容不一致'
    print('✅ 已追加 §100.12')
    print('   字节 %d → %d' % (len(orig), len(back)))
    print('   章节数 %d → %d' % (len(osecs), len(nsecs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
