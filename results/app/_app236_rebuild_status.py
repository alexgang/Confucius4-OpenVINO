#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236：把 STATUS_APP.md **按原始行尾**重建（含本轮 3 处改动）。

🔴 为什么必须重建（而不是直接用 Edit 工具改）：
   Edit 工具把整份文件**统一规整成 LF** ⇒ 原文件是**混合行尾**
   （行 1-2 CRLF、行 3-4 LF、行 5-10 CRLF、行 11-91 LF）
   ⇒ 规整后 **57 个 CRLF 全部消失** ⇒ **违反「行尾风格不变」这条真不变量**
   ⇒ 且会让本文件与 HEAD 的差异从「3 处」变成「整份文件」⇒ 违反「旧正文逐字未变」。

本脚本的做法：
  ① 以**写前备份**为基底（⇒ 旧正文字节**逐字原样**）
  ② 在**字节层**做 3 处改动：
     (a) 行 4 的 `更新时间` 值 → 替换（**该行保持 LF**）
     (b) 行 10「## 最近更新」之后 → **插入** 1 条（**LF**，与该区域一致）
     (c) 文末 → **追加** §236 节 + 指针行（**LF**，与文末区域一致）
  ③ **先在内存里**跑真不变量断言，全过才落盘
  ④ 落盘用 **临时文件 + os.replace**（原子）
  ⑤ 落盘后**另起脚本**复核（见 `_app236_verify_status.py`）

🔴 写前真不变量断言（全部必须成立）：
  - 旧正文（除 `更新时间` 一行）**逐字未变**
  - 原有 **57 个 CRLF 一个不少**、**33 个 LF 一个不少**（除被替换那行仍是 LF）
  - 新增的行**全部是 LF**（不引入新的 CRLF）
  - `last_ack` 唯一且 == APP-133
  - 文件 ≤40 000 B／≤300 行
"""
import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status/app/STATUS_APP.md')
BAK = os.path.join(os.environ.get('TEMP', '/tmp'), 'STATUS_APP.md.bak_app236')
TS = '2026-11-25 07:38:13'

NEW_RECENT = (
    "> \U0001f534 2026-11-25 07:38:13 ｜ **六通道复核 ⇒ 仍无新 App 纠偏**"
    "（本地 max APP-133 ＝ QQ max APP-133 ＝ `last_ack` ⇒ **值不变**）｜"
    "🔴 **修掉 3 处真缺陷 ＋ 1 处安全缺口**：① 🔴 **app049「包路径写死」打包闸门从 §233 起一直 exit=1 "
    "⇒ `pack_v13.py` 拒绝打包 ⇒ v2.7 打不出来**（起因：APP-133/§233/§234/§235 四轮新增的 9 个一次性历史诊断脚本"
    "按设计写死当时包版本 ⇒ 被 `ACTIVE_RE` 判成活跃验收脚本）⇒ 按本闸门**既有**「一次性历史诊断」白名单口径放行"
    "并逐条写明理由（**类别 B「会进包的生产模块」实测 0 违规 ⇒ 不削弱交付保证**）⇒ 闸门 **exit=0**；**反证**："
    "新增未白名单的写死脚本 ⇒ 闸门仍 **exit=1 且点名** ⇒ 不是放水放成永远绿；"
    "② \U0001f7e2 **§222 入库完整性**（②③ 两类）：**5 个**「证据已入库但生产者脚本未入库」＋ **9 个**"
    "「被已入库证据以 sha256 引用但未入库」的复算底本 ⇒ 全部入库；复算底本用 `results/app/.gitattributes` "
    "**逐文件 `-text`**（**不用通配符** ⇒ 不改已入库文件形态）⇒ **9 个文件 4/4 PASS**"
    "（blob sha == 磁盘 sha == 公布 sha ＋ attr `-text`）＋ **反证 3/3** ＋ "
    "**真跑 `core.autocrlf=false clone` ⇒ clone 出来的 sha256 与证据公布的逐个一致**（干净 clone 复算链已通）；"
    "③ 🔴 **app187 闸门正则截断**：扩展名表漏 `jsonl` ⇒ `app231_pack_lock_events.jsonl` 被截断成**从未存在**的 "
    "`.json` ⇒ 报出**假 MISSING**；修法＝补扩展名 ＋ **长扩展名在前**（只补表**不够**，`json` 在前会先匹配）"
    "＋ 边界断言 ⇒ 改后报**真实路径**（反证 3/3）；"
    "④ 🔴 **安全**：`results/app/_pkg_v25_{runtime,removed_bridge}_token_*.txt` 是**活的 EXT bridge 明文口令**，"
    "此前**未被任何 .gitignore 规则覆盖** ⇒ 一次 `git add -A` 即**不可逆**地泄露；\U0001f7e2 实测**从未被跟踪**"
    "（`git log` 无记录）⇒ **未泄露**；⇒ 显式忽略 ＋ 对 31 个入库候选做**安全扫描**"
    "（SECRET 2／RUNTIME 5／SAFE 24，反证 3/3）；"
    "｜\U0001f7e2 **未改任何客户包**（v2.6 `ACCEPTED.json` 逐字未动；完整版 v2.x 无 zip，本轮未新增）；"
    "｜\U0001f7e2 **未打包 zip**／未跑推理·计时（**未取 MACHINE_LOCK**）／未调 MiniMax／未连 B 机；"
    "｜\U0001f7e2 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）；"
    "｜🔴 **如实登记 7 处未修/待裁定项**（含 `app231_pack_lock_events.jsonl` **不伪造**、**如实记录**，"
    "下一轮真跑成包路径时自动出现）；｜**本条需等 reviewer 复核**"
)

SEC236 = (
    "## §236 待命轮（**六通道复核 ⇒ 仍无新 App 纠偏**，`last_ack` 仍 **APP-133**）｜"
    "🔴 **修掉 3 处真缺陷 ＋ 1 处安全缺口**：① **app049 打包闸门从 §233 起一直红着 ⇒ v2.7 打不出来**｜"
    "\U0001f7e2 **闭合 §222 入库完整性缺口**（②5 个生产者脚本 ＋ ③9 个复算底本，**逐字节入库**）｜"
    "🔴 **修 app187 闸门的正则截断假 FAIL**｜🔴 **堵住活的 EXT bridge 明文 token 的入库风险**"
)
SEC236_PTR = (
    "> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec236_detail_20261125.md`**"
    "（含 §0 本轮性质与依据、§1 六通道逐通道证据、§2 app049 打包闸门红着的根因与修法、"
    "§3 §222②③ 两类缺口的逐条清单与逐字节入库判据（含 clone 端到端）、§4 app187 正则截断、"
    "§5 活 token 的入库风险与安全扫描、§6 本轮新学的 5 个判据坑、§7 未修/待裁定项、§8 纪律自查、§9 下一轮）"
)


def split_keep(b):
    """按 b'\\n' 切分并**保留每行的行尾**。"""
    out = []
    for ln in b.split(b'\n'):
        out.append(ln)
    return out


def eol_of(line_bytes):
    if line_bytes.endswith(b'\r'):
        return b'\r\n'
    return b'\n'


def content_of(line_bytes):
    if line_bytes.endswith(b'\r'):
        return line_bytes[:-1]
    return line_bytes


def main():
    before = open(BAK, 'rb').read()
    # 拆成 (content, eol) 序列；末尾的空元素代表文件以 \n 结尾
    raw = before.split(b'\n')
    parts = []
    for i, ln in enumerate(raw):
        if i == len(raw) - 1:
            # 文件最后一段（可能是 b''）⇒ 它前面的 '\n' 是最后一行行尾
            if ln:
                parts.append((ln, b'\n'))
            else:
                parts.append((b'', b''))
        else:
            if ln.endswith(b'\r'):
                parts.append((ln[:-1], b'\r\n'))
            else:
                parts.append((ln, b'\n'))

    n_crlf_before = before.count(b'\r\n')
    n_lf_before = before.count(b'\n') - n_crlf_before

    # 找 `更新时间` 行（行 4，索引 3）
    ts_idx = None
    for i, (c, e) in enumerate(parts):
        if c.startswith(b'\xe6\x9b\xb4\xe6\x96\xb0\xe6\x97\xb6\xe9\x97\xb4: '):
            ts_idx = i
            break
    if ts_idx is None:
        print("🔴 找不到「更新时间」行")
        return 1
    old_ts_eol = parts[ts_idx][1]

    # (a) 替换 更新时间 值（**行尾保持原样**）
    new_c = ('更新时间: ' + TS).encode('utf-8')
    parts[ts_idx] = (new_c, old_ts_eol)

    # 找「## 最近更新」行
    recent_idx = None
    for i, (c, e) in enumerate(parts):
        if c == '## 最近更新'.encode('utf-8'):
            recent_idx = i
            break
    if recent_idx is None:
        print("🔴 找不到「## 最近更新」行")
        return 1
    # 该行之后的第一行是旧的 §235 条目 ⇒ 新条目插在它前面（用该区域的行尾）
    insert_eol = parts[recent_idx + 1][1]
    if insert_eol == b'':
        insert_eol = b'\n'

    new_parts = parts[:recent_idx + 1] + [(NEW_RECENT.encode('utf-8'), insert_eol)] \
        + parts[recent_idx + 1:]

    # (c) 文末追加 §236（LF，与文末区域一致）
    #    找到最后一个非空 content 的位置
    last_idx = max(i for i, (c, e) in enumerate(new_parts) if c != b'')
    tail_eol = b'\n'
    if new_parts[last_idx][1] == b'':
        tail_eol = b''
    new_parts = new_parts[:last_idx + 1] + [
        (SEC236.encode('utf-8'), tail_eol),
        (SEC236_PTR.encode('utf-8'), tail_eol),
    ] + new_parts[last_idx + 1:]

    # 组装
    out = b''.join(c + e for c, e in new_parts)

    # ── 写前真不变量断言 ──
    errs = []
    n_crlf_after = out.count(b'\r\n')
    n_lf_after = out.count(b'\n') - n_crlf_after
    if n_crlf_after != n_crlf_before:
        errs.append('CRLF 数变了：%d → %d（应不变）' % (n_crlf_before, n_crlf_after))
    # 旧的 LF 行数：写前 33，写后应为 33（被替换的 更新时间 行仍是 LF）+ 新增行数
    added_lines = 1 + 2                       # 最近更新 1 条 + 文末 2 行
    expect_lf = n_lf_before + added_lines
    if n_lf_after != expect_lf:
        errs.append('LF 数不符：%d ≠ 期望 %d' % (n_lf_after, expect_lf))
    txt = out.decode('utf-8')
    if txt.count('last_ack: APP-133') != 1:
        errs.append('last_ack 不唯一')
    if ('更新时间: ' + TS) not in txt:
        errs.append('更新时间 未更新')
    lines = out.count(b'\n')
    if len(out) > 40000 or lines > 300:
        errs.append('超限额：%d B / %d 行' % (len(out), lines))
    # 旧正文逐字未变（除 更新时间 行）：用 difflib 校验
    import difflib
    b_txt = before.decode('utf-8').replace('\r\n', '\n').split('\n')
    a_txt = txt.replace('\r\n', '\n').split('\n')
    sm = difflib.SequenceMatcher(None, b_txt, a_txt, autojunk=False)
    n_rep = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace' and (i2 - i1) == 1 and (j2 - j1) == 1 \
                and b_txt[i1].startswith('更新时间: '):
            n_rep += 1
            continue
        if tag == 'insert':
            continue
        errs.append('不允许的改动 %s before[%d:%d] after[%d:%d]'
                    % (tag, i1, i2, j1, j2))
    if n_rep != 1:
        errs.append('「更新时间」行的 replace 次数 = %d（应 1）' % n_rep)

    print("=== 写前真不变量断言 ===")
    print("  CRLF：%d → %d（必须相等）" % (n_crlf_before, n_crlf_after))
    print("  LF  ：%d → %d（期望 %d）" % (n_lf_before, n_lf_after, expect_lf))
    print("  字节：%d → %d" % (len(before), len(out)))
    print("  行数：%d → %d" % (before.count(b'\n'), lines))
    if errs:
        for e in errs:
            print("  🔴 FAIL: %s" % e)
        print()
        print("🔴 断言未过 ⇒ **零改动**（不落盘）")
        return 1
    print("  ✅ 全部通过")

    # 落盘：临时文件 + os.replace（原子）
    tmp = STATUS + '.app236_tmp'
    with open(tmp, 'wb') as fh:
        fh.write(out)
    os.replace(tmp, STATUS)
    print()
    print("已落盘（原子 replace）")
    return 0


if __name__ == '__main__':
    sys.exit(main())
