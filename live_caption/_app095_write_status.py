#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app095_write_status.py —— 往 status/app/STATUS_APP.md **追加** §95 章节 + 改头部 4 字段。

纪律：
  - 只追加章节，不回头改旧章节；
  - 头部只改 4 字段行（按前缀正则找，不写死索引）；
  - 「最近更新」区块保持 ≤15 行（插入新行、裁掉最旧行）；
  - 写后校验：旧正文逐字未变 + 原有章节一个不少。
  - STATUS 是 LF ⇒ 归一化后写回 newline=''。
"""
import os
import re
import shutil
import datetime

P = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
BODY = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_s95_body_mine.md'

raw = open(P, 'rb').read().decode('utf-8')
raw = raw.replace('\r\n', '\n').replace('\r', '\n')

# ⚠️ 必须用**行锚点**正则找真正的章节标题行（不能用 find('\n## §1 ')）
_m = re.search(r'(?m)^## §\d+ ', raw)
assert _m, '找不到章节起点'
idx = _m.start()
old_sections = raw[idx:]          # 旧正文（含旧章节）
old_head = raw[:idx]              # 头部

# 旧章节编号清单（写前）
old_nums = [int(x) for x in re.findall(r'(?m)^## §(\d+) ', old_sections)]
assert old_nums, '旧正文无章节'
assert old_nums[-1] == 94, '旧正文最大章节不是 94，实际 %s' % old_nums[-1]

body = open(BODY, 'rb').read().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
body = body.rstrip('\n') + '\n'

NOW = '2026-10-29 20:49'

# ---- 改头部 4 字段（value 不带 "key: " 前缀） ----
def set_field(text, key, value):
    pat = re.compile(r'(?m)^' + re.escape(key) + r':.*$')
    ms = pat.findall(text)
    assert len(ms) == 1, '字段 %r 出现 %d 次' % (key, len(ms))
    assert not str(value).startswith(key + ': '), 'value 自带 key 前缀'
    return pat.sub(lambda _m: key + ': ' + value, text, count=1)

head = old_head
head = set_field(head, 'last_ack', 'APP-042')
head = set_field(head, '更新时间', NOW)
head = set_field(head, '当前任务',
    '**§95 🔴 APP-041 + APP-042 已实施：APP-041「启动时默认开启却没初始化」已在产品代码修掉（同一入口 `_on_tts_toggled()`，失败自动回关）；'
    'APP-042「自适应加速播放」全链已接通（WSOLA 保音高 + 统一参数 + 底栏显示）**；'
    '✅ 客户包 **v1.8 已重打**（zip 11 218 155 024 B / SHA256 `0e3b4d26…` / 14 201 条目 / zip⇄包目录 6 590 文件 0 差异 / MANIFEST version=1.8）⇒ **代码侧「已交付」成立**；'
    '⛔ **APP-042 的 SPE 5 分钟真机实测未做**（ASR 持锁 asr027-cpu-rerun-base，本轮守纪律未抢锁）、⛔ **APP-041 的桌面快捷方式真机验收未做** ⇒ 🔴 **本条需等 reviewer 复核**')
head = set_field(head, '阻塞 / 待用户决定',
    '① 🔴 **APP-042 真机验收未做**（SPE 前 5 分钟、默认设备摆放、持锁：滞后曲线起点/峰值/结尾、各倍率时间占比、**丢句 = 0**、挑 3 段 1.2–1.3× 配音落盘给用户抽听确认不变调）⇒ 本轮 `shared/MACHINE_LOCK` 被 **ASR** 持有（`asr PID 23644 started 2026-10-29 20:44:47 task=asr027-cpu-rerun-base`）⇒ **未抢锁**；'
    '② 🔴 **APP-041 真机验收未做**（须走用户真实启动方式：桌面快捷方式 → `pythonw.exe`，冷启动什么都不点直接出声；并测「所选输出设备不存在 ⇒ 开关自动回关闭」）；'
    '③ 🔴 **APP-039/040 核心仍未做**（音色按句绑定 spk + 说话人音色表）⇒ 卡在 ASR 说话人旁路接口未交付（实测 `shared/spe_qa_spk.json` 不存在、`_split_spk()` 恒返 None、`App._spk_by_seg` 恒空）；'
    '④ 🔴 **APP-039/040 实测验收未做**（SPE Q&A 段多人对话走实时路径、混淆表、延迟拆解、声纹次数、CAMPPlus 余弦）；'
    '⑤ 🔴 **APP-036/037 真机实测仍未做**（SPE 前 5 分钟播放模式 + 日文 CLI/GUI）；'
    '⑥ 🔴 **APP-027 仍未完**（V3-CER/CAMPPlus 归 reviewer、V4 用户实听未做）；'
    '⑦ 🔴 FTP 已永久关闭（APP-035）⇒ 分发方式 = reviewer 用 SSH/SFTP 拉取本机 zip（**v1.8**）；'
    '⑧ 🔴 本轮**未修改** `CORRECTIONS_APP.md`（只读，108 783 B / SHA256 `c50dcdd1…`）')

# ---- 「最近更新」区块：插入新行 + 裁掉最旧的，保持 ≤15 行 ----
RE = re.compile(r'(?m)^## 最近更新\s*$')
m = RE.search(head)
assert m, '找不到「最近更新」区块'
start = m.end()
# 区块 = 从 start 到头部末尾（头部后面就是第一个章节）
lines = head[start:].split('\n')
# 去掉开头空行
while lines and lines[0].strip() == '':
    lines.pop(0)
new_line = (NOW + ' §95 🔴 **APP-041 + APP-042 已实施并交付 v1.8**（zip 11 218 155 024 B / 17:37:13 / SHA256 `0e3b4d26…` / 14 201 条目 / zip⇄包目录 6 590 `.py` 逐字节 0 差异 / MANIFEST version=1.8）'
            '⇒ ✅ APP-041「启动时默认开启却没初始化」已修（同一入口 `_on_tts_toggled()`，失败自动回关闭）'
            '⇒ ✅ APP-042「自适应加速播放」全链接通（WSOLA 保音高 + `clamp(1.0+(lag−3)×0.025,1.0,1.30)` + 滞回 + 相邻句 ≤0.1× + 底栏显示语速/播放滞后）'
            '⇒ ✅ 验收 `app139` 21/21、`app140` 22/22、`app141_end_to_end` 24/24、`app141_integration` 62/62、`app142` 22/22（含反证基线 commit `f724769`）'
            '⇒ ⛔ **APP-042 的 SPE 5 分钟真机实测未做**（ASR 持锁，未抢锁）、⛔ **APP-041 桌面快捷方式真机验收未做** ⇒ 🔴 **本条需等 reviewer 复核**')
merged = [new_line] + lines
if len(merged) > 15:
    merged = merged[:15]
assert len(merged) <= 15, len(merged)
head = head[:start] + '\n' + '\n'.join(merged) + '\n\n'

# ---- 组装：head + 旧正文 + 新章节（追加在**文件末尾**） ----
out = head + old_sections.rstrip('\n') + '\n\n' + body

# ---- 写盘前校验 ----
new_nums = [int(x) for x in re.findall(r'(?m)^## §(\d+) ', out)]
assert new_nums[-1] == 95, new_nums[-1]
for n in old_nums:
    assert n in new_nums, '原章节 §%d 丢失' % n
# 旧正文逐字未变：去掉新章节后应与 old_sections 等价
i_new = out.rindex('\n## §95 ')
assert out[:i_new].rstrip('\n') == (head + old_sections).rstrip('\n'), '旧正文被改动'
# 头部字段断言
for k in ('last_ack', '更新时间', '当前任务', '阻塞 / 待用户决定'):
    assert len(re.findall(r'(?m)^' + re.escape(k) + r':', out)) == 1, k
assert re.search(r'(?m)^last_ack: APP-042$', out), 'last_ack 不对'
assert len(re.findall(r'(?m)^## 最近更新\s*$', out)) == 1

bak = P + '.bak_app095'
shutil.copy2(P, bak)
with open(P, 'w', encoding='utf-8', newline='') as f:
    f.write(out)
print('WROTE', P, len(out), 'bytes; sections', len(new_nums), 'backup', bak)
