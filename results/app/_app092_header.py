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

NOW = '2026-10-29 13:01'   # Get-Date 实测值

TASK_LINE = (
    '当前任务: **§92 🔴🔴 APP-034/035/036/037/038 五条新纠偏全部执行完毕（代码侧）⇒ '
    '遥测口径 4 处已改（APP-036 C1–C4：排队真口径 / 积压曲线采样 / `end_lag_s` 真实定义 / `n_discard_on_close`）'
    '＋ 句首标点已规范化（APP-037 C：剥离后为空 ⇒ 不合成、**不计丢句**、发 `kind=empty` 事件）'
    '＋ APP-036 D 已给出离线模拟数字（R=1.1293 ⇒ v=1.0 时 `lag@300s`=38.98 s，与 reviewer 速率模型 38.8 s 交叉校验通过）'
    '＋ APP-035「FTP 已关闭」口径已纠正（**撤回 §90.6/§91.8 旧口径**）'
    '＋ APP-034「TTS 队列不等 spk」已核查（App 侧未调用 `spk_update`）'
    '＋ APP-038「NPU 编译缓存」reviewer 明文「不需要专门去测」⇒ 仅登记风险** ⇒ '
    '✅ `app133` **50/50（仓库）＋ 50/50（客户包内那份）**、`app134` **50/50（仓库）＋ 50/50（客户包内那份）**（各含反证）'
    '⇒ ✅ 客户包定点同步（32 块唯一命中 + 幂等 3/3 ALREADY + 仓库⇄包目录归一化 LF 后 3/3 MATCH）'
    '⇒ 🔴 **本条需等 reviewer 复核**'
)

BLOCK_LINE = (
    '阻塞 / 待用户决定: '
    '① 🔴🔴 **APP-036 真实验收未做**（reviewer 明文要求：SPE 前 5 分钟 NPU 默认配置、**播放模式**重跑 '
    '⇒ ≥100 采样点曲线 ＋ `worker_fifo_wait` P50/P95/max ＋ `end_lag_s` ＋ `n_discard_on_close=0` ＋ 中文/原声时长比值）'
    '⇒ **本轮只做代码侧验收 + 离线模拟，未跑推理/测速（守纪律）**；'
    '② 🔴 **APP-037 B1/B2/B3 未做**（CLI `--translate ja` 流水线级 `lang=ja`/`lang_src=explicit` 证据（76± 句 + 逐句 wav）'
    '＋ NPU 组用修好语料（`97a8bb91…`）重跑 29×3 + wav ＋ 日文 GUI 5 分钟）；'
    '③ 🔴 **v1.6 zip 未重打**（客户包**目录**已定点同步且 3/3 MATCH，但 zip 仍是旧代码 ⇒ **本轮不写「已交付」**）'
    '⇒ 是否重打待 reviewer 裁定；'
    '④ 🔴 **APP-027 仍未完**（V3-CER / V3-CAMPPlus 归 reviewer、V4 用户实听未做）；'
    '⑤ 🔴 **FTP 已关闭（用户 2026-10-25 决定）⇒ APP-035 不适用** ⇒ **撤回 §90.6/§91.8「v1.6 未发布 FTP ⇒ 待裁定」旧口径**'
    '（本轮**未运行** `publish_ftp.py`、**未开 FTP**、21/2121/8080/80/8000 均无监听、`FTP_Share/` 仍只有 v1.4/v1.5）；'
    '⑥ 🔴 **本轮未修改 `CORRECTIONS_APP.md`**（只读、零改动，指纹 100 067 B / mtime 2026-10-29 11:00:14 / '
    'SHA256 `838b3171…5e827`）、未向 MiniMax、未跑 `verify_pkg_zip.py`、**未用 `git add -A`**（逐文件 add）'
)

RECENT_LINE = (
    '13:01 §92 🔴🔴 **APP-034/035/036/037/038 五条新纠偏全部执行完毕（代码侧）** ⇒ '
    '✅ **APP-036 C1–C4 遥测口径 4 处已改**（排队真口径 `worker_fifo_wait_total_s` / 积压曲线采样 ≥100 点 + csv / '
    '`end_lag_s` 真实定义「最后播完 − 源音频结束」/ `n_discard_on_close` + close 后最终统计）'
    '⇒ ✅ **APP-037 C 句首标点已规范化**（剥离后为空 ⇒ 不合成 + 不计丢句 + 发 `kind=empty`）'
    '⇒ ✅ **APP-036 D 离线模拟已出数字**（R=1.1293；v=1.0/1.1/1.2/1.3 ⇒ `lag@300s`=38.98/22.84/18.24/13.64 s）'
    '⇒ ✅ **APP-035 FTP 口径已纠正并撤回 §90.6/§91.8**（FTP 已关闭 ⇒ 不适用）'
    '⇒ ✅ `app133` **50/50 ×2 处**、`app134` **50/50 ×2 处**（各含反证 ⇒ 判据不恒真）'
    '⇒ ✅ 定点同步 **32 块唯一命中 + 幂等 3/3 ALREADY + 3/3 MATCH**'
    '⇒ 🔴 **自查抓出 2 个真实缺陷**（`ctypes.get_last_error()` 陷阱 ＋ `machine_lock_app.release()` 漏传 payload ⇒ 锁删不掉）'
    '⇒ ⛔ **APP-036/037 真实 NPU 实测未做（守纪律）**、⛔ **zip 未重打 ⇒ 不写「已交付」**'
    '⇒ 🔴 **本条需等 reviewer 复核**'
)


def main():
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        s = f.read()

    # 备份（包外）
    bak = os.path.join(os.path.dirname(REPO), 'status_app_backup_before_s92_header.md')
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
    print('旧正文逐字未变 = %s' % after[i:] == body_old)
    print('CRLF = %d' % b.count(b'\r\n'))
    print('字节 = %d' % len(b))
    print('SHA256 = %s' % hashlib.sha256(b).hexdigest())
    ok = (after[i:] == body_old and b.count(b'\r\n') == 0
          and len(lines2) <= 15 and 'last_ack: APP-038' in after
          and lines2[0].startswith('13:01 §92'))
    print()
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
