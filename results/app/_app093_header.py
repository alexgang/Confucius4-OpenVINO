# -*- coding: utf-8 -*-
"""app092 —— 更新 STATUS_APP.md 头部（last_ack / 更新时间 / 当前任务 / 阻塞 / 最近更新）。

🔴 纪律：
- 头部**只改 4 个字段行**（+ 「最近更新」块）；**不回头改任何旧章节**；
- 「阻塞」行**按前缀找**，不能写死索引；
- 「最近更新」≤15 行 ⇒ 加一行须裁掉**最旧**一行（不是失败）；
- STATUS 是 **LF** 换行 ⇒ 写盘必须 `newline=''`；
- 写后校验：旧正文（第一个 `## §1 ` 之后）**逐字未变**。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')

NOW = '2026-10-29 13:28'   # Get-Date 实测值

TASK_LINE = (
    '当前任务: **§93 🔴🔴 客户包 v1.6 已持锁重打 zip ⇒「已交付」成立（代码 + 包目录 + zip 三方闭环）**'
    '（zip 11 218 138 008 B / mtime 2026-10-29 13:20:04 / SHA256 `376c4832…31b8` / '
    '14 200 文件逐字节一致 / `testzip()` OK / 独立三方只读复核 `app136` **23/23 ×2 MATCH** + 反向自证判据有分辨力）'
    '⇒ 🔴 **自查抓出并修掉 2 个真实缺陷**（① 我本轮新写的 `app136` 与 §91 遗留的 `app132` **写死客户包版本号** '
    '⇒ 触发 §48 闸门 ⇒ **第一次打包被正确拦下** ⇒ 已改用 `pkg_paths` 单一数据源自动发现；'
    '② 打包期间必须等 45 s 安静窗口 ⇒ 我自己的复跑脚本被识别为「在算」⇒ 重新计时）'
    '⇒ ✅ commit **`dc7603b`** ＋ **普通 push**（**非 force**）＋ `HEAD == origin/main` '
    '＋ `CORRECTIONS_APP.md` **未入库**（`git show --name-only --format="" HEAD | grep CORRECTIONS` ⇒ 0 命中）'
    '⇒ ✅ **§92 的五条纠偏（APP-034/035/036/037/038）代码侧 + 交付侧全部闭环** ⇒ 🔴 **本条需等 reviewer 复核**'
)

BLOCK_LINE = (
    '阻塞 / 待用户决定: '
    '① 🔴🔴 **APP-036 真实验收未做**（reviewer 明文要求：SPE 前 5 分钟 NPU 默认配置、**播放模式**重跑 '
    '⇒ ≥100 采样点曲线 ＋ `worker_fifo_wait` P50/P95/max ＋ `end_lag_s` ＋ `n_discard_on_close=0` ＋ 中文/原声时长比值）'
    '⇒ **本轮只做代码侧验收 + 离线模拟 + 打包闭环，未跑推理/测速（守纪律）**；'
    '② 🔴 **APP-037 B1/B2/B3 未做**（CLI `--translate ja` 流水线级 `lang=ja`/`lang_src=explicit` 证据（76± 句 + 逐句 wav）'
    '＋ NPU 组用修好语料（`97a8bb91…`）重跑 29×3 + wav ＋ 日文 GUI 5 分钟）；'
    '③ 🔴 **「已交付」≠「真机跑通」** ⇒ zip 已含最新代码，但 **NPU 真机 5 分钟播放模式重跑仍未做** '
    '⇒ 「用户听得到」**仍不成立** ⇒ 待 reviewer 复核；'
    '④ 🔴 **APP-027 仍未完**（V3-CER / V3-CAMPPlus 归 reviewer、V4 用户实听未做）；'
    '⑤ 🔴 **FTP 已关闭（用户 2026-10-25 决定）⇒ APP-035 不适用** ⇒ **撤回 §90.6/§91.8「v1.6 未发布 FTP ⇒ 待裁定」旧口径**'
    '（本轮**未运行** `publish_ftp.py`、**未开 FTP**、21/2121/8080/80/8000 均无监听、`FTP_Share/` 仍只有 v1.4/v1.5）'
    '⇒ **分发方式 = reviewer 用 SSH/SFTP 拉取本机 zip**（绝对路径 + 字节数 + SHA256 见 §93.6）；'
    '⑥ 🔴 **追赶策略未做**（APP-036 D 明文等用户决定）⇒ 本轮**只给数字**；'
    '⑦ 🔴 **本轮未修改 `CORRECTIONS_APP.md`**（只读、零改动，指纹 100 067 B / mtime 2026-10-29 11:00:14 / '
    'SHA256 `838b3171…5e827`）、未向 MiniMax、未跑 `verify_pkg_zip.py`、**未用 `git add -A`**（逐文件 add）'
)

RECENT_LINE = (
    '13:28 §93 🔴🔴 **客户包 v1.6 已持锁重打 zip ⇒「已交付」成立（代码 + 包目录 + zip 三方闭环）** ⇒ '
    '✅ zip **11 218 138 008 B / mtime 13:20:04 / SHA256 `376c4832…31b8`**（较旧版 +8 538 B ⇒ 确实换了内容）'
    '＋ **14 200 文件逐字节一致** ＋ `testzip()` OK ＋ 打包脚本 PASS（md5 `f78d7fd3…cd90a`）'
    '⇒ ✅ **独立只读三方复核 `app136` PASS**（仓库⇄包目录 23/23 ＋ 包目录⇄zip 23/23 ＋ 3 个改动文件三方指纹全 MATCH）'
    '⇒ ✅ **反向自证**：注入 1 处真实差异 ⇒ 判据 **FAIL** 且精确定位到 `tts_worker.py` ⇒ 恢复后复跑 PASS（判据不恒真）'
    '⇒ 🔴 **自查抓出 2 个真实缺陷**（`app136`/`app132` **写死客户包版本号** ⇒ 触发 §48 闸门 ⇒ **第一次打包被正确拦下** '
    '⇒ 改用 `pkg_paths` 单一数据源；② 打包须等 45 s 安静窗口 ⇒ 自跑复现脚本被识别「在算」⇒ 重新计时）'
    '⇒ ✅ 同步后**包内代码复跑** `app133`/`app134` 各 **50/50 PASS**'
    '⇒ ✅ commit **`dc7603b`** ＋ 普通 push ＋ `HEAD == origin/main` ＋ `CORRECTIONS_APP.md` 未入库'
    '⇒ ⛔ **APP-036/037 真机 NPU 实测未做（守纪律）⇒「用户听得到」仍不成立**、⛔ **APP-027 未完**'
    '⇒ 🔴 **本条需等 reviewer 复核**'
)


def main():
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        s = f.read()

    # 备份（包外）
    bak = os.path.join(os.path.dirname(REPO), 'status_app_backup_before_s93_header.md')
    with open(bak, 'w', encoding='utf-8', newline='') as f:
        f.write(s)

    # 旧正文（第一个 '## §1 ' 之后）—— 必须逐字不变
    i = s.index('\n## §1 ')
    head_old, body_old = s[:i], s[i:]

    h = head_old

    # 1) last_ack
    h, n = re.subn(r'(?m)^last_ack:.*$', 'last_ack: APP-038', h)
    assert n == 1, 'last_ack 替换次数 = %d' % n

    # 2) 更新时间
    h, n = re.subn(r'(?m)^更新时间:.*$', '更新时间: ' + NOW, h)
    assert n == 1, '更新时间 替换次数 = %d' % n

    # 3) 当前任务（按前缀找）
    h, n = re.subn(r'(?m)^当前任务:.*$', TASK_LINE, h)
    assert n == 1, '当前任务 替换次数 = %d' % n

    # 4) 阻塞 / 待用户决定（按前缀找，不能写死索引）
    h, n = re.subn(r'(?m)^阻塞 / 待用户决定:.*$', BLOCK_LINE, h)
    assert n == 1, '阻塞行 替换次数 = %d' % n

    # 5) 最近更新：在**全文**上做（§1 锚点不在 head 里）
    full = h + body_old
    m = re.search(r'(## 最近更新\n)(.*?)(\n\n## §1 )', full, re.S)
    assert m, '未找到「最近更新」块'
    lines = [l for l in m.group(2).split('\n') if l.strip()]
    before_n = len(lines)
    lines = [RECENT_LINE] + lines
    if len(lines) > 15:
        lines = lines[:15]
    full = full[:m.start(2)] + '\n'.join(lines) + full[m.end(2):]

    new = full
    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(new)

    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        after = f.read()
    b = after.encode('utf-8')

    m2 = re.search(r'## 最近更新\n(.*?)\n\n## §1 ', after, re.S)
    lines2 = [l for l in m2.group(1).split('\n') if l.strip()]

    print('备份 = %s' % bak)
    print('last_ack = %s' % re.search(r'(?m)^last_ack:.*$', after).group(0))
    print('更新时间 = %s' % re.search(r'(?m)^更新时间:.*$', after).group(0))
    print('最近更新行数 = %d（改前 %d）' % (len(lines2), before_n))
    print('  第一行 = %s' % lines2[0][:60])
    print('  最后一行 = %s' % lines2[-1][:60])
    with open(bak, 'r', encoding='utf-8', newline='') as f:
        prev = f.read()
    _anchor = '\n## §1 '
    _prev_body = prev[prev.index(_anchor):]
    _now_body = after[after.index(_anchor):]
    print('旧正文逐字未变 = %s' % (_now_body == _prev_body))
    print('CRLF = %d' % b.count(b'\r\n'))
    print('字节 = %d' % len(b))
    print('SHA256 = %s' % hashlib.sha256(b).hexdigest())
    ok = (_now_body == _prev_body and b.count(b'\r\n') == 0
          and len(lines2) <= 15 and 'last_ack: APP-038' in after
          and lines2[0].startswith('13:28 §93'))
    print()
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
