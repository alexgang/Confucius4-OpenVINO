"""§246：归档 §244 头条行 + §245 块（逐字），活文档换指针行，再追加 §246(LOCK-001)。

混合行尾：CRLF 67 / LF 110 ⇒ 全程按 bytes 处理，每行保留原行尾。
不变量（任一 FAIL 即零改动）：
  1) 归档文件里能逐字找到被替换的两块原文
  2) CRLF 计数 = 原 CRLF - 被删行的 CRLF + 新行按参考行尾的 CRLF
  3) 文件 ≤ 40000 B
  4) 首行、last_ack 之外的头部行不变
"""
import hashlib
import io
import os
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
P = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARC244 = os.path.join(REPO, 'status', 'archive',
                      'STATUS_APP_sec244_headline_20261126.md')
ARC245 = os.path.join(REPO, 'status', 'archive',
                      'STATUS_APP_sec245_block_20261126.md')

PTR244 = ("> 🔴 **本节原正文（一整行，含 EXT v0.4.23 / turbo 落 `_compile_npu` / "
          "候选 `app\\*.py` 差异清零 / `--check` 原文 / App 链真翻译 3/3）"
          "**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec244_headline_20261126.md`；"
          "全文另见 `status/app/STATUS_APP_sec244_detail_20261126.md`。"
          "结论：EXT 已推 GitHub `c955411`，单测 16/16；APP-139 turbo 真编译 6/6；"
          "APP-151 同步后差异 0；🔴 当时未做的 60 s 冒烟已由 §245 完成")

PTR245 = ("> 🔴 **本节六行要点整块逐字归档** ⇒ `status/archive/STATUS_APP_sec245_block_20261126.md`"
          "（全文见 `status/app/STATUS_APP_sec245_detail_20261126.md`）；"
          "结论：`drain` 把一次 stats 超时当断连（**已修，5/5 含反证**）⇒ 三轮全 PASS"
          "（dubs 123/123/170、`n_error` 0、排空 True）；滞后 p50 **29/51/95 s** 超说明书 ⇒ README 已改；"
          "样片 3 段 OGG；白名单 **19/19**")

SEC246 = [
    u"## \u00a7246 **LOCK-001**（机器锁死锁修复）APP 侧安装完成｜`last_ack` **APP-151**（＋LOCK-001，不占模块编号）",
    u"> 🟢 **安装**：附件（**8 831 B**）经直连 API 由脚本落盘（无人工转写）⇒ "
    u"`C:\\Users\\Trekker-PTL\\shared\\tools\\machine_lock.py`"
    u"（sha256 `c8eb39be7438043d99fed086b49d2e70ef07af8945680a72969f99ca2b500571`，`ast.parse` 通过）；"
    u"`shared\\README_LOCK.md` 顶部加 LOCK-001 段、旧机制保留备查（339→1 341 B，CRLF 0）。",
    u"> 🟢 **行为验证 5/5**（**包内 python** 跑，证据由脚本产出 ⇒ `results/app/app245_lock001_install.json`）："
    u"① `status`=**FREE** ② 单作业 `[machine_lock] acquired` + `released (rc=0)` ③ 持锁期 `status`=**HELD (live job)** "
    u"④ 第二作业 `waiting; holder…` 后 `acquired`（等 **15.6 s**）⑤ **整树被杀 ⇒ 系统锁自动放**，`status` 判 "
    u"**STALE text lock (no live job)**（不再永久死锁）⇒ `reclaim` 归档 ⇒ **FREE**。",
    u"> 🔴 **未做（如实登记）**：既有取锁代码（`machine_lock_app.py` 的 `write_lock_atomic`、三轮编排脚本的 "
    u"CreateNew/finally 删锁）**尚未改成套 `machine_lock.py run`** ⇒ 下一次计时作业起法改为 "
    u"`run --module app --note … -- <命令>`，并在日志核对 `acquired`／`released (rc=…)` 两行（LOCK-001 验收第 2 条）。",
    u"> 🟢 **STATUS 邮件（T-MAIL-003 必须发）已发并已发箱回读核对**：① 状态报告 **4 918 B**（无附件）"
    u"`msg_0WHS7mI7rDcDNMzVoh300SxFEVirHhdK5bNJe-mx14dbZw` ② 抽听样片 **1 406 B**＋**3 个 OGG 附件**"
    u"（117 114/120 347/122 633 B，sha1 由发送脚本从磁盘现算）"
    u"`msg_v6USGFcIM_QnAict57C6mUoGqbNRX3hJvwEfthNPDAWjoQ`；两封**首/中/尾三地标全部命中、无截断**，"
    u"附件 3/3 与源字节一致。",
]


def main():
    raw = open(P, 'rb').read()
    shutil.copy2(P, P + '.bak_app246')
    lines = raw.split(b'\n')
    crlf0 = raw.count(b'\r\n')

    i244 = next(i for i, l in enumerate(lines) if l.startswith(b'## \xc2\xa7244'))
    i245 = next(i for i, l in enumerate(lines) if l.startswith(b'## \xc2\xa7245'))
    # §245 块 = 标题行到文件最后一个非空行
    j = len(lines) - 1
    while j > i245 and lines[j].strip() == b'':
        j -= 1
    assert i244 < i245 < j, (i244, i245, j)

    old244 = lines[i244]
    old245 = b'\n'.join(lines[i245:j + 1])

    def eol_of(b):
        return b'\r' if b.endswith(b'\r') else b''

    e244, e245 = eol_of(old244), eol_of(lines[i245])

    # ---- 归档（逐字） ----
    os.makedirs(os.path.dirname(ARC244), exist_ok=True)
    with open(ARC244, 'wb') as f:
        f.write(b'# STATUS_APP \xc2\xa7244 \xe5\xa4\xb4\xe6\x9d\xa1\xe8\xa1\x8c'
                b'\xef\xbc\x88\xe9\x80\x90\xe5\xad\x97\xe5\xbd\x92\xe6\xa1\xa3'
                b'\xef\xbc\x8c2026-11-26\xef\xbc\x89\n\n')
        f.write(old244 + b'\n')
    with open(ARC245, 'wb') as f:
        f.write(b'# STATUS_APP \xc2\xa7245 \xe5\x9d\x97'
                b'\xef\xbc\x88\xe9\x80\x90\xe5\xad\x97\xe5\xbd\x92\xe6\xa1\xa3'
                b'\xef\xbc\x8c2026-11-26\xef\xbc\x89\n\n')
        f.write(old245 + b'\n')
    assert old244 in open(ARC244, 'rb').read()
    assert old245 in open(ARC245, 'rb').read()

    # ---- 组装新 lines ----
    new = list(lines[:i244])
    new.append(PTR244.encode('utf-8') + e244)
    new.extend(lines[i244 + 1:i245])
    new.append(lines[i245])                       # §245 标题行原样保留
    new.append(PTR245.encode('utf-8') + e245)
    new.extend(lines[j + 1:])                     # 尾随空行

    # ---- 追加 §246（在最后一个非空行之后） ----
    k = len(new) - 1
    while k >= 0 and new[k].strip() == b'':
        k -= 1
    tail_blank = new[k + 1:]
    body = new[:k + 1]
    for ln in SEC246:
        body.append(ln.encode('utf-8') + e245)
    out = b'\n'.join(body + tail_blank)

    # ---- last_ack / 更新时间 ----
    out = out.replace(b'last_ack: APP-151\r\n',
                      'last_ack: APP-151（＋LOCK-001）\r\n'.encode('utf-8'), 1)
    out = out.replace(b'last_ack: APP-151\n',
                      'last_ack: APP-151（＋LOCK-001）\n'.encode('utf-8'), 1)
    out = out.replace('更新时间: 2026-11-26 20:25'.encode('utf-8'),
                      '更新时间: 2026-11-26 21:52'.encode('utf-8'), 1)

    # ---- 不变量 ----
    crlf_new_expected = (crlf0
                         - (1 if e244 else 0) - old245.count(b'\r\n')
                         + (1 if e244 else 0) + (1 if e245 else 0)
                         + (len(SEC246) if e245 else 0))
    checks = [
        ('归档 244 逐字命中', old244 in open(ARC244, 'rb').read()),
        ('归档 245 逐字命中', old245 in open(ARC245, 'rb').read()),
        ('CRLF 计数符合推算', out.count(b'\r\n') == crlf_new_expected),
        ('体积 ≤ 40000', len(out) <= 40000),
        ('首行未变', out.startswith(b'# STATUS_APP')),
        ('§246 已写入', '## \u00a7246'.encode('utf-8') in out),
    ]
    for name, ok in checks:
        print('%-22s %s' % (name, 'OK' if ok else 'FAIL'))
    if not all(ok for _, ok in checks):
        print('零改动（不写盘）')
        return 2

    with open(P, 'wb') as f:
        f.write(out)
    b = open(P, 'rb').read()
    print('WROTE bytes=%d (was %d, delta %+d) CRLF=%d lines=%d sha256=%s'
          % (len(b), len(raw), len(b) - len(raw), b.count(b'\r\n'),
             b.decode('utf-8').count('\n') + 1, hashlib.sha256(b).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
