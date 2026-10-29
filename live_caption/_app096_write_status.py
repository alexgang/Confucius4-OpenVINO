# -*- coding: utf-8 -*-
"""把 §96 追加进 status/app/STATUS_APP.md（只追加 + 头部字段改写）。

**纪律**
- 🔴 纠偏文件 `CORRECTIONS_APP.md` **只读**，本脚本**绝不碰它**。
- 🔴 只**追加** `## §N` 章节，不回头改旧章节。
- 🔴 写后校验：① 原有章节**一个不少**；② 旧正文**逐字未变**（逐字比对）。
- 🔴 头部「最近更新」**≤15 行** ⇒ 新的写最上面，**超限就裁掉最旧的**。
- 🔴 「更新时间」用 `Get-Date` 实测值（本脚本调 PowerShell 取），禁止推算。
- 🔴 STATUS 是 LF ⇒ 写盘必须 `newline=''`。
"""
import io
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BODY = os.path.join(REPO, 'results', 'app', '_s96_body_mine.md')
BACKUP = os.path.join(REPO, 'results', 'app', '_status96_backup.md')

SECTION_NO = 96


def get_date():
    """用 PowerShell `Get-Date` 取实测值（禁止推算）。"""
    for cmd in (['powershell', '-NoProfile', '-Command', 'Get-Date -Format "yyyy-MM-dd HH:mm"'],
                ['powershell.exe', '-NoProfile', '-Command', 'Get-Date -Format "yyyy-MM-dd HH:mm"']):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            s = (r.stdout or '').strip().splitlines()
            if r.returncode == 0 and s and s[0].strip():
                return s[0].strip()
        except Exception:
            continue
    raise SystemExit('!! 取不到 Get-Date 实测值，拒绝写盘')


def main():
    now = get_date()
    print('Get-Date 实测 = %s' % now)

    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        old = f.read()
    old_norm = old.replace('\r\n', '\n')

    with open(BODY, 'r', encoding='utf-8', newline='') as f:
        body = f.read().replace('\r\n', '\n').rstrip('\n')

    # ── 备份（原样，字节级）──
    with open(BACKUP, 'wb') as f:
        f.write(old.encode('utf-8'))

    # ── 1) 旧章节清单（追加前）──
    old_secs = re.findall(r'^## §(\d+)', old_norm, re.M)

    # ── 2) 追加新章节到**文件末尾** ──
    new = old_norm.rstrip('\n') + '\n\n' + body + '\n'

    # ── 3) 头部字段改写 ──
    #    「最近更新」区块：从「## 最近更新」下一行 → 第一个「## §」标题行之前
    m = re.search(r'(?m)^## 最近更新\s*$', new)
    if not m:
        raise SystemExit('!! 找不到「## 最近更新」标题')
    start = m.end()
    m2 = re.search(r'(?m)^## §', new[start:])
    if not m2:
        raise SystemExit('!! 找不到「## §」标题')
    block = new[start:start + m2.start()]
    lines = [l for l in block.split('\n') if l.strip()]
    new_line = ('%s §96 🔴 **APP-042 真机实测暴露并修掉「CLI 路径加速链路永不触发」的真机缺陷**'
                '（run2 证据：jsonl 76 行 `target_wall` 0 条 / `play_lag_s` 0 条 / speed 全 1.0'
                ' ⇒ 撤回 §95「全链已接通」表述）⇒ ✅ 修复：`_cli_wall0` + `_cli_target_wall()` + '
                '三处 `tts.submit(..., target_play_at=)`（CLI 与 GUI 同口径，墙钟 `time.time()`）'
                '⇒ ✅ 闸门 `app145` REAL 9/9 + 反证 FAIL（判据不恒真）'
                '⇒ ✅ 验收脚本判据自身缺陷已修（全角冒号 ⇒ `pick()` 恒 None ⇒ B4/B6 假 FAIL）'
                '⇒ ✅ 定点同步 v1.8 包目录（`sync_c159`：`[SYNCED]` + 幂等 `[ALREADY]`，'
                '归一化 SHA `a9c95777…`）⇒ ⛔ **zip 未重打 ⇒ 不写「已交付」**、'
                '⛔ reviewer 回转写 / 用户实听未做 ⇒ 🔴 **本条需等 reviewer 复核**'
                ) % now
    lines = [new_line] + lines[:14]          # 🔴 硬约束 ≤15 行
    new_block = '\n' + '\n'.join(lines) + '\n\n'
    new = new[:start] + new_block + new[start + m2.start():]

    # last_ack（已执行完的最大 APP 编号）—— APP-042 未变
    new = re.sub(r'(?m)^last_ack:.*$', 'last_ack: APP-042', new, count=1)
    # 「当前任务」/「阻塞」两行要改写成**本轮**的状态（否则仍停在 §95）
    cur_task = ('当前任务: **§96 🔴 APP-042 真机实测暴露并修掉「CLI 路径加速链路永不触发」的真机缺陷**'
                '（run2 证据：jsonl 76 行 `target_wall` 0 条 / `play_lag_s` 0 条 / speed 全 1.0'
                '⇒ **撤回 §95「全链已接通」表述**）⇒ ✅ 已修：`_cli_wall0` + `_cli_target_wall()` + '
                'CLI 三处 `tts.submit(..., target_play_at=)`（与 GUI 同口径，墙钟 `time.time()`）'
                '⇒ ✅ 已定点同步客户包 **v1.8 包目录**（`sync_c159`：`[SYNCED]` + 幂等 `[ALREADY]`，'
                '归一化 SHA `a9c95777…`）⇒ ✅ 闸门 `app145` REAL 9/9 + 反证识破、'
                '`app146` REAL 8/8 + 反证 3/3 ⇒ ⛔ **zip 未重打 ⇒ 不写「已交付」**'
                '（zip 内实测仍是旧代码）、⛔ **修复后的真机实测仍在等 ASR 释放共享机器锁** ⇒ 🔴 **本条需等 reviewer 复核**')
    new = re.sub(r'(?m)^当前任务:.*$', lambda _m: cur_task, new, count=1)

    blocked = ('阻塞 / 待用户决定: ① 🔴 **修复后的 APP-042 真机实测仍在等锁**'
               '（SPE 前 5 分钟、默认设备摆放、持锁：滞后曲线起点/峰值/结尾、各倍率时间占比、'
               '**丢句 = 0**、挑 3 段 1.2–1.3× 配音落盘给用户抽听）⇒ 本轮 `shared/MACHINE_LOCK` 被 **ASR** 持有'
               '（`asr PID 41264 started 2026-10-29 21:56:33 task=asr028-ref-diarize`，'
               'ctypes `exitcode=259` ⇒ **活锁**）⇒ **不抢不删**，fail-closed 排队中；'
               '② 🔴 **zip 未重打** ⇒ 客户包 zip 内仍是修复前代码 ⇒ **本轮不写「已交付」**；'
               '③ 🔴 **reviewer 回转写 + 用户实听未做**（APP-042 明文要求，本模块不得自做）；'
               '④ 🔴 **APP-041 桌面快捷方式 → `pythonw.exe` 冷启动真机验收未做**；'
               '⑤ 🔴 **APP-039/040 核心未做**（卡 ASR 说话人旁路接口未交付）；'
               '⑥ 🔴 本轮**未修改** `CORRECTIONS_APP.md`（只读）')
    new = re.sub(r'(?m)^阻塞 / 待用户决定:.*$', lambda _m: blocked, new, count=1)
    # 「更新时间」用实测值
    new = re.sub(r'(?m)^更新时间:.*$', '更新时间: %s' % now, new, count=1)

    # ── 4) 写盘后校验 ──
    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(new)

    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        chk = f.read().replace('\r\n', '\n')

    # ① 原有章节一个不少
    new_secs = re.findall(r'^## §(\d+)', chk, re.M)
    missing = [s for s in old_secs if s not in new_secs]
    # ② 旧正文逐字未变
    old_body = old_norm[old_norm.index('## §1'):]
    old_body_kept = old_body in chk
    # ③ 最近更新 ≤15 行
    m3 = re.search(r'(?m)^## 最近更新\s*$', chk)
    m4 = re.search(r'(?m)^## §', chk[m3.end():])
    nlines = len([l for l in chk[m3.end():m3.end() + m4.start()].split('\n') if l.strip()])
    # ④ 头部字段
    la = re.search(r'(?m)^last_ack:\s*(\S+)', chk).group(1)
    up = re.search(r'(?m)^更新时间:\s*(.+)$', chk).group(1).strip()

    print('原有章节数 = %d  追加后 = %d' % (len(old_secs), len(new_secs)))
    print('原有章节缺失 = %s' % (missing or '无 ✅'))
    print('旧正文逐字未变 = %s' % old_body_kept)
    print('最近更新行数 = %d （要求 ≤15）' % nlines)
    print('last_ack = %s' % la)
    print('更新时间 = %s' % up)
    ok = (not missing) and old_body_kept and nlines <= 15 and la == 'APP-042' and up == now
    print('校验结论 = %s' % ('PASS ✅' if ok else 'FAIL ❌'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
