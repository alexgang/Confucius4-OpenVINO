# -*- coding: utf-8 -*-
r"""_app482 — 写 STATUS §181（接单 APP-101 / APP-102）。

纪律：
  * 只做「定点替换块 + 唯一命中断言」；写后把每个 new 逆换回 old 必须逐字等于原文。
  * §178–§180 三节正文整块逐字归档（write-once），活文档每节只留 1 行速查（APP-101 §1.d）。
  * 写前自检：纯 LF / 限额 / 归档件不存在；任一 FAIL ⇒ 源文件零改动。
  * 写后自检：≤40000 B / ≤300 行 / 无裸 CR / 章节数不减 / 归档 SHA 与指针一致。
"""
import hashlib
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
P = os.path.join(REPO, r'status\app\STATUS_APP.md')
ARCH_REL = 'status/archive/STATUS_APP_sec178_180_20261112.md'
ARCH = os.path.join(REPO, *ARCH_REL.split('/'))
NOW = '2026-11-12 09:46:41'   # Get-Date 实测

b0 = open(P, 'rb').read()
assert b'\r' not in b0, 'ABORT: 源活文档不是纯 LF'
t0 = b0.decode('utf-8')
assert len(b0) <= 40000 and len(t0.splitlines()) <= 300, 'ABORT: 源文件已超限'
assert not os.path.exists(ARCH), 'ABORT: 归档件已存在（write-once，不得覆盖）'

pairs = []


def rep(t, old, new):
    assert t.count(old) == 1, f'ABORT: 锚点命中 {t.count(old)} 次（须恰好 1）: {old[:60]!r}'
    pairs.append((old, new))
    return t.replace(old, new, 1)


t = t0

# ── 1. 头部：更新时间 / 当前任务 / 阻塞行 / 已压缩行 ──────────────────
t = rep(t, '更新时间: 2026-11-11 18:55:00', f'更新时间: {NOW}')

old_task = [ln for ln in t0.splitlines() if ln.startswith('当前任务:')]
assert len(old_task) == 1
t = rep(t, old_task[0],
    '当前任务: **接单 APP-101 / APP-102**（reviewer 11-12 08:59:56 追加；纠偏文件 **102 条 / 最大 APP-102** / SHA `f5346cbd…` / 325 733 B）｜APP-102 用户决定「直接打 rc8」⇒ 本轮已完成**不依赖设备**的静态前置（EXT v0.4.8 @`817abcb` 暂存、stateful 模型身份核对、MiniMVP TTS 默认改 GPU.0）｜**stateful 后端接入／4 臂短冒烟／10 语种冒烟／rc8 打包与验收未做**（需持 `MACHINE_LOCK` 长作业）⇒ **未打 rc8／未打 v2.5／未 ack**｜详见 §181')

old_block = [ln for ln in t0.splitlines() if ln.startswith('阻塞 / 待用户决定:')]
assert len(old_block) == 1
t = rep(t, old_block[0],
    '阻塞 / 待用户决定: 🔴 **`last_ack` 暂保持 `APP-100`**：APP-101 §6 要求「开始时先写 APP-101」，但同节又要求第 3/4 节做完才逐项写 PASS/FAIL；为免下一轮巡检把未完成的 §3/§4 当作已执行完而跳过 ⇒ **不虚报 ack，请 reviewer 裁定**｜🔴 APP-101 §4 草案与 App `ASRBackend` 契约 3 处不一致（prompt 硬上界 512／EOS 多 `151673`／runner 用 torch embedding 而 App 只有 npy）⇒ **列出报 reviewer，未自行改 ASR 侧**｜🔴 rc8 需 4 臂设备冒烟（GPU/NPU）＋10 语种冒烟＋GUI 截图＋包上验收 ⇒ 需专门持锁长作业会话｜🔴 交付配置表已按 §1.b 更新（v2.4／rc7 为磁盘最新，v2.5／rc8 未打包）；§3.5 判据失效已由 wespeaker 解决，旧阻塞项已清除｜**倍率地板** 与 **`tts_late_drop_sec`** 仍未裁定')

old_compr = [ln for ln in t0.splitlines() if ln.startswith('已压缩:')]
assert len(old_compr) == 1
arch_sha_ph = '{ARCH_SHA}'
t = rep(t, old_compr[0], old_compr[0] +
    f'｜**§178–§180 压缩**（APP-101 §1.d「每节不超过 3 行速查」）：三节正文整块逐字归档 ⇒ `{ARCH_REL}`（块 SHA256 `{arch_sha_ph}`）；活文档三节各留 1 行速查')

# ── 2. 最近更新：追加 1 行 ────────────────────────────────────────────
t = rep(t, '## 最近更新\n',
    '## 最近更新\n'
    f'> 🔴 {NOW} ｜ **接单 APP-101 / APP-102**（纠偏 102 条／SHA `f5346cbd…`／325 733 B／mtime 08:59:56）｜静态前置落盘：EXT v0.4.8 @`817abcb` 暂存、stateful 模型身份核对、MiniMVP TTS 默认改 GPU.0｜**stateful 后端／4 臂冒烟／10 语种冒烟／rc8 未做**（需持锁长作业）⇒ **未 ack、未打 rc8**，详见 §181\n')

# ── 3. 交付配置表（APP-101 §1.b：直接改写当前有效结论） ───────────────
old_tts = [ln for ln in t0.splitlines() if ln.startswith('| 语音输出设备 |')]
assert len(old_tts) == 1
t = rep(t, old_tts[0],
    '| 语音输出设备 | 🔴 **APP-101 §0.3 / APP-102 §0（用户 11-12 决定）**：完整版 TTS 与克隆（说话人编码器／x-vector）→ **GPU.0**；MiniMVP TTS → **GPU.0**（克隆置灰）｜**dev 树已改**、**未进任何客户包** ⇒ 须随 v2.5 / rc8 新版本号出 | `live_caption/device_config.py:69-74` → `_DEFAULT_DEVICES_MINIMVP[tts]=GPU.0`（`ast.parse` OK）；`CORRECTIONS_APP.md` → APP-101 §0.3 / APP-102 §0；旧「TTS 走 NPU」实测 `app048_layout_1920x1080.png` **已过期** |')

old_tail = [ln for ln in t0.splitlines() if ln.startswith('| 说话人识别旁路 |')]
assert len(old_tail) == 1
t = rep(t, old_tail[0], old_tail[0] + '\n'
    '| MiniMVP 默认设备（新） | ASR **NPU** / MT **GPU.0** / TTS **GPU.0**；`device_config.DEFAULT_DEVICES` 为唯一事实来源，GUI `_dev_selected` 与 CLI `get_devices()` 同源（无第二份字面量） | `live_caption/device_config.py:69-74`；`_DEFAULT_DEVICES_FULL` 三档仍全 GPU.0 |\n'
    '| 磁盘最新完整版包 | `Confucius4_LiveCaption_v2.4/` 与 `Confucius4_LiveCaption_v2.4.zip`（**11 235 954 241 B** / 2026-11-07 23:04）在位；**v2.5 未打包**；v1.5 / v1.13 / v2.0–v2.3 / `v2.3_aborted_20261107_1517` 均保留未删 | 磁盘实测 `ls -d` / `ls -la`（2026-11-12 09:47） |\n'
    '| 磁盘最新 MiniMVP 包 | `Confucius4_LiveCaption_MiniMVP_v1.0-rc7/` 在位；**rc6 已按 APP-099 移入回收站**（可逆）；**rc8 未打包**（APP-102 要求「直接打 rc8」⇒ 前置冒烟未完成，本轮未打） | 磁盘实测 `ls -d`（2026-11-12 09:47）；`CORRECTIONS_APP.md` → APP-102 §3 |')

# ── 4. §178–§180 整块逐字归档 + 三节速查 + 新增 §181 ─────────────────
m = re.search(r'^## §178.*?(?=\Z)', t, re.M | re.S)
assert m, 'ABORT: 找不到 §178 标题'
block = t[m.start():]
assert len(re.findall(r'^## §\d+', block, re.M)) == 3, 'ABORT: 归档块章节数不是 3'
arch_bytes = block.encode('utf-8')
arch_sha = hashlib.sha256(arch_bytes).hexdigest()

new_tail = (
    f'## §178 巡检（last_ack=APP-100，2026-11-11 18:55:00）｜**6 处 git 半交付已补交**\n'
    f'> 🔴 正文整块逐字归档 ⇒ `{ARCH_REL}`（SHA256 `{arch_sha}`）；结论：补交 6 处漏提交产物（`app468` FAIL=0／MISSING=0／反证 3/3）。\n\n'
    f'## §179 勘误（2026-11-11 18:55:00）｜撤回「判据 177 行」\n'
    f'> 🔴 同上归档件；§178 的自指行数快照作废。\n\n'
    f'## §180 勘误（2026-11-11 18:55:00）｜撤回「184 行＝稳态真值」\n'
    f'> 🔴 同上归档件；结论只引用不变量（FAIL=0／MISSING=0／反证 3/3）。\n\n'
    f'## §181 接单 APP-101 / APP-102（{NOW}）｜静态前置完成；设备作业与 rc8 未做\n'
    f'> 🔴 **已做**（证据 `results/app/app482_app101_102_model_identity.json`）：EXT v0.4.8 @`817abcbe…` 用 `git archive` 暂存 `_ext_v048_stage`（167 文件／`ext/accel_usage.py` 在位／manifest `version=0.4.8`）；decoder bin SHA `0059531a…d6a3` 与 reviewer 一致、IR `inputs_embeds [1,1..512,1024]`、hidden 1024／28 层、encoder bin `0b7463d6…` 前缀一致；`device_config.py:69-74` MiniMVP `tts` `NPU`→`GPU.0`（`ast.parse` OK、GUI/CLI 同源）。\n'
    f'> 🔴 **未做**（需持 `MACHINE_LOCK` 长作业，**不虚报**）：`backends_stateful.py` 后端／`make_backend` 分派／`manifest_gen` 源目录／rc8 打包脚本、4 臂短冒烟、10 语种冒烟、GUI 截图、rc8 目录+zip 与包上验收 ⇒ **未打 rc8／v2.5、未通知用户、未调 MiniMax、未占设备**；`last_ack` 保持 `APP-100`（理由见头部），**等 reviewer 裁定**。\n'
)
t = rep(t, block, new_tail)

# 归档 SHA 占位符回填（占位符只出现在「已压缩」行，唯一）
assert t.count(arch_sha_ph) == 1, 'ABORT: 归档 SHA 占位符命中数不为 1'
# 把占位符替换也登记成一对，保证逆换校验成立
pairs = [(o, n.replace(arch_sha_ph, arch_sha)) for o, n in pairs]
t = t.replace(arch_sha_ph, arch_sha)

# ── 5. 写前自检 ───────────────────────────────────────────────────────
nb = t.encode('utf-8')
n_secs = len(re.findall(r'^## §\d+', t, re.M))
o_secs = len(re.findall(r'^## §\d+', t0, re.M))
checks = {
    'bytes<=40000': len(nb) <= 40000,
    'lines<=300': len(t.splitlines()) <= 300,
    'no_CR': b'\r' not in nb,
    'sections_not_fewer': n_secs >= o_secs,
    'arch_sha_declared': arch_sha in t,
    'last_ack_kept': 'last_ack: APP-100' in t,
    'timestamp': f'更新时间: {NOW}' in t,
    'sec181_present': '## §181 ' in t,
}
# 旧正文逐字未变：把每个 new 逆换回 old
rev = t
for old, new in reversed(pairs):
    assert rev.count(new) == 1, f'ABORT: 逆换校验失败，new 命中 {rev.count(new)} 次: {new[:50]!r}'
    rev = rev.replace(new, old, 1)
checks['old_body_verbatim'] = (rev == t0)

bad = [k for k, v in checks.items() if not v]
print('=== 写前自检 ===')
for k, v in checks.items():
    print(f'  {k}: {"PASS" if v else "FAIL"}')
print(f'  bytes {len(b0)} -> {len(nb)} / lines {len(t0.splitlines())} -> {len(t.splitlines())} / sections {o_secs} -> {n_secs}')
if bad:
    print('ABORT（源文件零改动、归档件未创建）:', bad)
    sys.exit(1)

# ── 6. 落盘（先归档后活文档；临时文件 + os.replace） ──────────────────
tmp_a = ARCH + '.tmp'
with open(tmp_a, 'w', encoding='utf-8', newline='\n') as f:
    f.write(block)
os.replace(tmp_a, ARCH)
tmp_p = P + '.tmp'
with open(tmp_p, 'w', encoding='utf-8', newline='\n') as f:
    f.write(t)
os.replace(tmp_p, P)

# ── 7. 写后独立复核 ───────────────────────────────────────────────────
vb = open(P, 'rb').read()
va = open(ARCH, 'rb').read()
post = {
    'live_bytes<=40000': len(vb) <= 40000,
    'live_lines<=300': len(vb.decode('utf-8').splitlines()) <= 300,
    'live_no_CR': b'\r' not in vb,
    'archive_verbatim': va == arch_bytes,
    'archive_sha': hashlib.sha256(va).hexdigest() == arch_sha,
    'archive_pointer_matches': arch_sha in vb.decode('utf-8'),
    'live_sections': len(re.findall(r'^## §\d+', vb.decode('utf-8'), re.M)) == n_secs,
}
print('=== 写后复核 ===')
for k, v in post.items():
    print(f'  {k}: {"PASS" if v else "FAIL"}')
print('ARCH', ARCH, len(va), 'B', arch_sha)
print('LIVE', P, len(vb), 'B')
sys.exit(0 if all(post.values()) else 1)
