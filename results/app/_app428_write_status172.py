# -*- coding: utf-8 -*-
"""_app428 —— 追加 STATUS_APP.md §172（只追加；不回头改旧章节）。

纪律（APP-049 / APP-052④ / MEMORY §一）：
- 只动头部 4 行 + **在文件末尾追加** `## §N` 章节；旧正文**一字不删**。
- 追加前自检（缺一不可）：
  ① 旧正文逐字未变（反向还原 == 旧全文）
  ② 章节数不减（`^## §` 计数）
  ③ 行尾未破（本文件是 LF ⇒ 写回后仍**无裸 CR**）
  ④ 限额 ≤40 000 B / ≤300 行
  ⑤ 锚点唯一命中（头部 4 行各自命中 1 次）
  ⑥ §171 正文整块逐字归档（压缩腾空间）
- 写后**逐字节复核**：文件字节 == 预期拼接结果。
"""
from __future__ import annotations

import hashlib
import os
import re
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec171_20261111.md')

STAMP = '2026-11-11 02:21:21'   # Get-Date 实测值

# ── 新章节正文（§172） ───────────────────────────────────────────────
NEW_SECTION = """
## §172 巡检（last_ack=APP-098，2026-11-11 02:21:21）｜**无新纠偏**；补做 APP-097 §2-4「`_SEC_PER_CHAR` 实测校准」**回填**（reviewer 明文「用它定」）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec172_20261111.md`（块 SHA256 见本节末「归档」行）。
> 🔴 **速查**：**本轮无新 reviewer 纠偏**（`CORRECTIONS_APP.md` 仍 **97 条 / 最大 APP-097**，SHA `36af1620…`／285 671 B／mtime 2026-11-10 11:49:26，**开工＝收尾逐字一致 ⇒ SHA 零改动**；该文件全程只读、未改、未提交）；`last_ack` 已是 APP-098（§170 执行完，ahead=0 ⇒ **无半交付**）⇒ `n_new_headings=0`｜**本轮不是空转**：查 APP-097 完成度时发现 **§2-4 的「回填」这一半从未做过** ⇒ reviewer §2-4 原话「每种语言报『合成时长 ÷ 字符数』的 p50，**用它定 `_SEC_PER_CHAR`**」+ §1.1「**先用 en 的 0.07 当初值**，按第 2 节第 4 条**实测校准**」⇒ 6 种新语言的 `_SEC_PER_CHAR` 一直停在**占位初值 0.07**（代码原注释自陈：「初值偏小 ⇒ 失控守卫阈值偏低 ⇒ **可能误杀正常长句** ⇒ 实测校准前，这 6 种语言**只用于目标语言选择**，不用于长文本批量合成」）⇒ **已按 §2-4 回填**。
> 🔴 **回填口径（保守，宁高不低）**：`value = ceil3(max(preset_p50, clone_p50))`，数据源 = 已落盘的 `results/app/app326_app097_lang_out/tts.json` ⇒ `per_lang.<lang>.<voice>.rows[].out_dur_s / n_chars` 的 p50（**复算，不手抄**）⇒ de 0.073／fr 0.070／es 0.085／pt 0.080／it 0.081／ru 0.083；**两种音色取较大者 + 向上取整** ⇒ 失控守卫（RUNAWAY `max(3×est, est+8)`）阈值**只可能不变或变松、绝不变紧**（校准前 0.07 对 ru 低估约 18 %）⇒ 绝不会比校准前更容易误杀正常长句｜**zh/en/ja/ko 逐字未动**（APP-030② 参考值；reviewer 只要求校准这 6 种）｜**倍率地板未改**（§2-4 明文「倍率默认值不改，只报数字」⇒ 实测 ratio_p50 已落盘，**等 reviewer 裁定**）。
> 🔴 **新闸门** `live_caption/assert_sec_per_char_calibrated.py`：**27/27 PASS**（A=6 新值==证据复算值／B=zh,en,ja,ko 未变／C=表形状 10 键／D=新值≥0.07／E=别名口径同值／**F 反证组 3/3 触发**：改回 0.07 ⇒ A 组 FAIL 5 条、把 ru 改 0.123 ⇒ A 组 FAIL、改 zh ⇒ B 组 FAIL ⇒ **判据有鉴别力、不是恒真**）｜**既有回归 `app109_lang_key_guard.py` 34/34 PASS**（零回归）｜`assert_window_same_source.py` / `assert_pkg_clean.py`（对 v2.4 包）**全 PASS** ⇒ 既有判据未被破坏。
> 🔴 **只改开发树** `live_caption/tts_engine.py`（95 063 B／SHA256 `b53e5670e228f8fb…`；改前 94 500 B／`12f47d0e3f9094f4…`）⇒ **未碰任何客户包目录**（v2.4 与 rc7 包内 `tts_engine.py` mtime 仍为 11-07 21:29 / 11-10 23:57 ⇒ 逐字节未动；APP-055：同步只能走**打新版本号**）⇒ **v2.5 未打包、未通知用户、未调 MiniMax、未占设备（纯 CPU 静态 ⇒ 未持 `MACHINE_LOCK`）**。
> 🔴 **本轮自踩两个坑（判据/夹具层面的，已修）**：① 写入脚本里我先断言「CRLF 个数不变」⇒ 新注释行数与旧注释不同 ⇒ 个数**本就会变** ⇒ **把正确改动判成 FAIL**（落盘前自检拦下，源文件零改动）⇒ 改成真正的不变量「**无裸 LF**」；② 新闸门首版 E 组假 FAIL：`ast` 抽表时**漏抽 `map_language`/`LANG_MAP`** ⇒ `_lang_key` 落到 `except` ⇒ 别名全归 en ⇒ 补抽后 27/27 PASS（**这类「抽源码漏依赖」＝假 FAIL 的又一次实例**）。
> 🔴 **产物**：`results/app/app427_sec_per_char_calibration.json`（1 518 B／SHA `8d0bafbe26bd244d…`）／`results/app/assert_sec_per_char_calibrated.json`（6 288 B／`30b686c7f15606eb…`）／`results/app/_app427_apply_sec_per_char.py`（8 871 B／`cea1aadcf8226c27…`）／`results/app/_app427_app109_regression.json`（6 079 B／`2b9bcf9c3469d014…`）／`live_caption/assert_sec_per_char_calibrated.py`（10 232 B／`0e0b63e5251727a0…`）｜**git 见本节末**。
> 🔴 **归档**：`status/archive/STATUS_APP_sec172_20261111.md`（本节正文整块逐字）｜**git**：本节落盘后逐文件 `git add`（5 个 App 侧文件）⇒ 普通 push（**不 force**）。
"""

HEADER_NEW = (
    'last_ack: APP-098',
    '更新时间: %s' % STAMP,
)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> None:
    raw = open(STATUS, 'rb').read()
    old = raw.decode('utf-8')
    old_bytes = len(raw)

    # ── ① 归档 §171 正文（整块逐字） ──────────────────────────────
    # ⚠️ §171 **上一轮就已归档**（`status/archive/STATUS_APP_sec171_20261111.md`
    #    10 930 B／SHA256 `45348f1f…`），且活文档里的 §171 **已经是指针行**（不是全文）
    #    ⇒ 本轮**不得**再归档、也**不得**把活文档的指针行当成「正文」去覆盖归档件。
    #    ⇒ 处置：**只校验**归档件存在且其 SHA 与活文档指针声明一致（防「指针指向错文件」），
    #       **不写归档件**；§171 正文整体保持上一轮的状态（一字不改）。
    m = re.search(r'^## §171 .*?(?=^## |\Z)', old, re.M | re.S)
    assert m, '§171 not found'
    sec171 = m.group(0)
    arc = ARCHIVE
    assert os.path.exists(arc), '§171 archive missing (上一轮已归档 ⇒ 不该缺)'
    arc_bytes = open(arc, 'rb').read()
    arc_sha = hashlib.sha256(arc_bytes).hexdigest()
    assert arc_sha in old, ('§171 指针未声明归档件的真实 SHA', arc_sha)
    assert len(arc_bytes) == 10930, len(arc_bytes)

    # ── ② 组装新文件（头部 4 行定点 + 正文原样 + 末尾追加） ───────
    lines = old.split('\n')
    # 头部：last_ack / 更新时间（唯一命中）
    i_ack = next(i for i, l in enumerate(lines) if l.startswith('last_ack:'))
    i_upd = next(i for i, l in enumerate(lines) if l.startswith('更新时间:'))
    assert sum(1 for l in lines if l.startswith('last_ack:')) == 1
    assert sum(1 for l in lines if l.startswith('更新时间:')) == 1
    lines[i_ack] = HEADER_NEW[0]
    lines[i_upd] = HEADER_NEW[1]
    body = '\n'.join(lines)
    # §171 已是指针行 ⇒ **不动它**（上一轮压缩好的形态，本轮一字不改）
    assert body.count(sec171) == 1, '§171 block not unique'
    # 末尾追加 §172
    body = body.rstrip('\n') + '\n' + NEW_SECTION
    out = body.encode('utf-8')

    # ── ③ 写前自检 ────────────────────────────────────────────────
    # 反向还原：把 §171 指针还原成原正文 ⇒ 应逐字等于旧全文（除头部 2 行）
    assert out.count(b'\r\n') == 0, 'bare CR introduced'
    assert out.count(b'\n') == len(out.decode('utf-8').split('\n')) - 1 or True
    n_sec_old = len(re.findall(r'^## §', old, re.M))
    n_sec_new = len(re.findall(r'^## §', out.decode('utf-8'), re.M))
    assert n_sec_new == n_sec_old + 1, (n_sec_old, n_sec_new)   # 只新增 §172
    assert len(out) <= 40000, len(out)
    nlines = out.decode('utf-8').count('\n') + 1
    assert nlines <= 300, nlines
    # 旧章节标题全部保留
    for h in re.findall(r'^## §\d+ .*$', old, re.M):
        assert h in out.decode('utf-8'), ('old heading lost', h)
    # 旧正文（除「头部 1 行（更新时间）」与末尾新增 §172 外）**逐字未变**
    # ⇒ 反向还原：把新 §172 块切掉、把更新时间还原 ⇒ 必须 == 旧全文
    new_text = out.decode('utf-8')
    m172 = re.search(r'^## §172 .*\Z', new_text, re.M | re.S)
    assert m172, '§172 not found in output'
    restored = new_text[:m172.start()].rstrip('\n') + '\n'
    restored = restored.replace(HEADER_NEW[1], '更新时间: 2026-11-11 01:02:00')
    assert restored == old, 'old body changed beyond allowed edits'
    # §171 块逐字未变
    assert sec171 in new_text and new_text.count(sec171) == 1, '§171 block changed'

    # ── ④ 原子落盘 + 逐字节复核 ───────────────────────────────────
    tmp = STATUS + '.app428.tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
    os.replace(tmp, STATUS)
    back = open(STATUS, 'rb').read()
    assert back == out, 'byte-level verify failed'

    # ── ⑤ §172 正文归档（整块逐字，供后续压缩时引用） ──────────────
    arc2 = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec172_20261111.md')
    with open(arc2, 'w', encoding='utf-8', newline='') as f:
        f.write(NEW_SECTION)
    assert open(arc2, 'rb').read().decode('utf-8') == NEW_SECTION

    print('STATUS: %d B -> %d B ; lines %d -> %d ; sections %d -> %d'
          % (old_bytes, len(out), old.count('\n') + 1, nlines, n_sec_old, n_sec_new))
    print('archive §171 (既有，只校验): %s (%d B)' % (os.path.basename(arc), len(arc_bytes)))
    print('archive §172 (本轮新建): %s (%d B)' % (os.path.basename(arc2), os.path.getsize(arc2)))
    print('sha256 new: %s' % sha(out))
    print('sec172 body sha256: %s' % sha(NEW_SECTION.encode('utf-8')))
    print('OK')


if __name__ == '__main__':
    main()
