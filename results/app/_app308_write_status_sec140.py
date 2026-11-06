r"""_app308 — 定点写 STATUS_APP.md 的 §140（APP-049 / APP-052 ④ 纪律）。

🔴 只动**头部 5 行** + 「已压缩」行尾追加 + 「最近更新」列表头插 1 行
   + 末尾**只追加** §140 **速查章节**（完整正文在归档件）。
🔴 旧正文（§1..§139）**逐字不动**；写后验收：
   ① 章节数 +1 ② 旧正文两段整块逐字相同 ③ 行尾未破
   ④ ≤40 000 B / ≤300 行 ⑤ 归档件逐字命中且含完整 SHA
先写临时文件，再 os.replace 原子替换；验收不过 ⇒ **不写**。
"""
from __future__ import annotations

import hashlib
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                       'STATUS_APP_sec140_20261106.md')
EV = os.path.join(HERE, '_app308_write_status_sec140.json')

STAMP = '2026-11-06 13:59:48'     # Get-Date 实测（PowerShell，写入前重取）

NEW_HEAD = {
    2: 'last_ack: APP-078\n',
    3: '更新时间: %s\n' % STAMP,
    4: ('当前任务: **§140 APP-075 / 076 / 077 / 078 逐条执行** —— '
        'APP-076/077/078 **本条已完成**；🔴 **APP-075 本条需等 reviewer 复核**'
        '（`v23_clone_r2/` 最终落盘 **54 文件／20 175 499 B**（manifest 自记'
        '与磁盘一致；`_app309` 补齐曾静默漏拷的 `submit.jsonl`，**18/0**），'
        '但 F0 闸门 **21 PASS / 19 FAIL / 6 NONE**，19 个 FAIL 全是 `male→female` ⇒ '
        '克隆男声变女声**未修复**；真 x-vector 余弦矩阵未产出、第 2 臂未跑）'
        '｜APP-076 md5 对照 **39/0**＋app193 正则第一个值 0.6＋MiniMVP「不适用」'
        '｜APP-077① 打包闸门 **26/0**＋3 个旧包清单＋MiniMVP 无 token；'
        '② 版本无关启动器 **27/0**｜APP-078（reviewer 13:31 中途追加）'
        '**28/0**＋建包闸门 **14/0** ⇒ **改正 §139「v2.x 不违规」结论**\n'),
    5: ('阻塞 / 待用户决定: 🔴🔴 **APP-075 未闭环（BLOCKING）**：r2 已交付但 '
        'F0 闸门未通过，`app299` 是 `offline_stat_embed`（统计嵌入，硬判据 '
        'cos_S2_S2=0.745841 < cos_S2_S1=0.772995 ⇒ FAIL）⇒ **真 x-vector '
        '需 reviewer 复核**；第 2 臂（preset 对照）因设备作业被会话中断杀死未跑'
        '（已用 ctypes err=87 确证 PID 死并回收孤儿锁）→ **按 APP-075「需 Opus '
        '复核」节点停止，不自行判定通过，v2.3 不打包**｜🔴 **v2.3 打包待办**：'
        '5 个 ASR 文件＋`models/spk/pyannote_seg_3_0/fp16-w5/`＋'
        '`assert_pkg_clean.py` 闸门＋桥接 .lnk 指向 `bridge_bootstrap`（本轮'
        '**未打包、未落进任何包**）｜🔴 **reviewer 本轮中途追加 APP-078**：'
        '纠偏文件开工 77 条 / SHA `3f759ebe…7f359` ⇒ 收尾 **78 条** / '
        'SHA `bbc95c43…d82af`（全程只读未改，**不得声称零改动**）｜'
        '旧包 v2.0/v2.1/v2.2 目录与 zip **一字节未动**，受影响清单见 §140，'
        '等 reviewer 转告用户｜本轮需 reviewer 复核：r2 F0 表 / '
        'APP-074 结论改正 / 3 个旧包清单 / 未打包\n'),
    6: None,   # 「已压缩」行：尾部追加归档件名（定点替换，见下）
}

# 🔴 APP-052④：主文件只留**速查**；完整正文逐字留在 ARCHIVE。
SEC140 = '''

### §140 ✅ APP-076/077/078 已完成 ｜ 🔴 APP-075 需等 reviewer 复核（2026-11-06 13:59）

> 全文（4 条证据／md5 表／3 旧包清单／8 音色与 r2 顶层文件**完整 SHA256**／日志原文／口径订正）**逐字归档** ⇒ `status/archive/STATUS_APP_sec140_20261106.md`；本节仅速查。
> 🔴 `CORRECTIONS_APP.md` 只读未改：开工 `3f759ebe…7f359`／219 810 B／77 条 ⇒ 收尾 `bbc95c43…d82af`／220 735 B／**78 条**（中途追加 APP-078）；**SHA/字节/条数均变，不声称零改动**。
> 🔴 **APP-075 需等复核**：r2 最终 **54 文件／20 175 499 B**（manifest 自记＝磁盘；`_app309` **18/0** 补齐静默漏拷的 `submit.jsonl`，旧「52／20 160 623 B」为写前口径）；F0 **21/19/6**，19 FAIL 全 `male→female`，S2 已登记仍串女声；真 x-vector 未产出、第 2 臂未跑 ⇒ **v2.3 不打包**。
> 🔴 **APP-076 已完成**：`_app304` **39/0**（5 文件 md5／`ASR_FILES` 4→5／0.6 同源／app193 正则／克隆门槛未放宽）；MiniMVP「不适用」。v2.3 带 5 文件＋`fp16-w5/`。
> 🔴 **APP-077 已完成**：`_app302` **26/0**（3 旧 zip 同值 `bridge_token.txt`，完整清单见归档件 §3；MiniMVP 无 token）＋`pkg_exclude` 两处独立拦；`_app305` **27/0**（版本无关启动器）；**未生成桌面 .lnk**，待 v2.3 接线。
> 🔴 **APP-078 已完成**（13:31 追加）：`_app306` **28/0** —— **目录 ≠ zip**（3 安装目录各 8 音色，3 zip 均 0；完整 SHA 见归档件 §4①）⇒ **改正 §139「v2.x 不违规」：只对 zip 成立**；`assert_pkg_clean.py`＋`_app307` **14/0**；旧包一字节未动。
> 🔴 **纪律**：未打包／未打 zip／只读扫描旧包／未改 .lnk／未动 `v23_clone/`／未在 CPU 跑推理测速／未调 MiniMax／未提交纠偏文件／逐文件 `git add`＋main 普通 push。**没落盘的不写已交付**。
'''


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def main():
    raw = open(STATUS, 'rb').read()
    assert b'\r\n' not in raw, 'STATUS 是 LF，出现 CRLF ⇒ 行尾已破'
    lines = raw.decode('utf-8').splitlines(True)
    # 🔴 在「最近更新」列表中间插 1 行会把连续旧正文**切成两段**，
    #    用整块 `old_body in out` 会假 FAIL ⇒ 改为两段各自整块原样保留。
    old_head = ''.join(lines[7:11])     # 头部之后 .. 「## 最近更新」标题
    old_tail = ''.join(lines[11:])      # 旧更新列表 + §1..§139 全部正文
    before_sections = [l for l in lines if l.startswith('### §')]

    # ① 头部 5 行定点替换
    for idx, val in NEW_HEAD.items():
        if val is None:
            continue
        assert lines[idx].startswith(
            {2: 'last_ack:', 3: '更新时间:', 4: '当前任务:',
             5: '阻塞 / 待用户决定:'}[idx]), '头部锚点不匹配：%d' % idx
        lines[idx] = val
    # 「已压缩」行：尾部追加本轮归档件（定点、唯一命中）
    assert lines[6].startswith('已压缩:')
    lines[6] = lines[6].rstrip('\n') + (
        '｜**§140 正文归档**到 '
        '`status/archive/STATUS_APP_sec140_20261106.md`\n')

    # ② 「最近更新」列表**头插**一行（旧行一字不动）
    assert lines[9].startswith('## 最近更新')
    new_line = ('- %s **§140 已写** ⇒ **APP-076/077/078 本条已完成**'
                '（39/0｜26/0＋27/0｜28/0＋14/0）、**APP-075 需等 reviewer 复核**'
                '（r2 最终 54 文件／20 175 499 B，`_app309` 18/0 补齐 `submit.jsonl`，'
                'F0 21/19/6 未通过）；**改正 §139**（目录≠zip）；'
                '**reviewer 中途追加 APP-078**（77→78 条，SHA 变化如实记录）；'
                '⛔ **v2.3 不打包、旧包一字节未动**\n' % STAMP)
    lines.insert(11, new_line)

    # ③ 末尾**只追加** §140 速查章节
    out = ''.join(lines) + SEC140

    # ── 验收 ────────────────────────────────────────────────────
    b = out.encode('utf-8')
    checks = []
    after_lines = out.splitlines(True)
    after_sections = [l for l in after_lines if l.startswith('### §')]
    checks.append(dict(name='章节数不少于写前', ok=len(after_sections)
                       == len(before_sections) + 1,
                       detail='%d -> %d' % (len(before_sections),
                                            len(after_sections))))
    # 旧正文两段均须逐字出现，且 tail 不被重复/改写
    checks.append(dict(name='旧正文逐字未变（两段整块原样保留）',
                       ok=(old_head in out and old_tail in out
                           and out.count(old_tail) == 1),
                       detail='head=%d tail=%d' % (len(old_head),
                                                   len(old_tail))))
    checks.append(dict(name='新增更新行插在「最近更新」标题之后、旧列表之前',
                       ok=(out.find(new_line) > out.find(old_head)
                           and out.find(new_line) < out.find(old_tail))))
    checks.append(dict(name='§139 旧章节标题仍在',
                       ok=any('§139' in l for l in after_sections)))
    checks.append(dict(name='§140 新章节已追加',
                       ok=any('§140' in l for l in after_sections)))
    checks.append(dict(name='行尾未破（纯 LF）', ok=b'\r\n' not in b))
    checks.append(dict(name='≤40 000 B（APP-052④）', ok=len(b) <= 40000,
                       detail=len(b)))
    checks.append(dict(name='≤300 行（APP-052④）',
                       ok=len(after_lines) <= 300, detail=len(after_lines)))
    checks.append(dict(name='last_ack = APP-078',
                       ok='last_ack: APP-078\n' in out))
    checks.append(dict(name='更新时间为 Get-Date 实测',
                       ok=('更新时间: %s\n' % STAMP) in out))
    arch = open(ARCHIVE, 'rb').read()
    arch_txt = arch.decode('utf-8')
    checks.append(dict(name='归档件存在且非空', ok=len(arch) > 5000,
                       detail='%d B / SHA %s' % (len(arch), sha256(arch)[:16])))
    checks.append(dict(name='§140 指向归档件路径逐字命中',
                       ok='status/archive/STATUS_APP_sec140_20261106.md' in out))
    checks.append(dict(name='归档件含 8 音色完整 SHA（非省略号）',
                       ok=('eebf32802121d2c87334845dcb1e8b470f02ac85fecd158'
                           '39bf45ef4a78c7751') in arch_txt))
    checks.append(dict(name='归档件含 r2 最终 54 文件口径',
                       ok='20 175 499' in arch_txt and '54 文件' in arch_txt))
    n_fail = sum(1 for c in checks if not c['ok'])
    for c in checks:
        print('  [%s] %s %s' % ('PASS' if c['ok'] else 'FAIL',
                                c['name'], c.get('detail', '')))
    ev = dict(tool='_app308_write_status_sec140', ts=time.strftime(
        '%Y-%m-%d %H:%M:%S'), before_bytes=len(raw), after_bytes=len(b),
        before_lines=len(raw.decode('utf-8').splitlines(True)),
        after_lines=len(after_lines),
        old_body_bytes=len((old_head + old_tail).encode('utf-8')),
        sec140_bytes=len(SEC140.encode('utf-8')),
        archive_bytes=len(arch), archive_sha256=sha256(arch),
        checks=checks, n_fail=n_fail,
        verdict='PASS' if n_fail == 0 else 'FAIL')
    if n_fail:
        print('!! 验收未过 ⇒ **不写** STATUS（保持原文件不动）')
        with open(EV, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        return 1

    tmp = STATUS + '.app308_tmp'
    with open(tmp, 'wb') as f:
        f.write(b)
    os.replace(tmp, STATUS)
    # 写后复核：磁盘读回与内存一致
    back = open(STATUS, 'rb').read()
    assert back == b, '写后读回不一致'
    print('\n已写 STATUS：%d B / %d 行（限额 40 000 B / 300 行）'
          % (len(back), len(after_lines)))
    print('归档件：%s（%d B）' % (ARCHIVE, len(arch)))
    with open(EV, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
