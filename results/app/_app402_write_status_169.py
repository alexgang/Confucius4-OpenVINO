# -*- coding: utf-8 -*-
"""写 `status/app/STATUS_APP.md` §169（本轮巡检结论）＋ APP-052④ 压缩。

🔴 **纪律（APP-049 / APP-052④ / APP-055）**
* `status/app/CORRECTIONS_APP.md` **只读**（本脚本绝不碰它）。
* STATUS 只**追加** `## §N` 章节；旧正文**一字不删**（§168 的正文**整块逐字归档**
  到 `status/archive/STATUS_APP_sec168_20261110.md` 后，用 ≤3 行索引替身 ⇒
  「旧正文整块原样保留」在归档件里成立）。
* 只动头部 4 行（last_ack / 更新时间 / 当前任务 / 阻塞·待用户决定）＋「最近更新」加一行。
* 写后自检：章节数 +1；**除 §168 归档块与新增 §169 外，旧正文逐字未变**；行尾未破；
  ≤40 KB / ≤300 行。

用法：python results/app/_app402_write_status_169.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive')
EVID = os.path.join(REPO, 'results', 'app')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
SEC_ARCH = os.path.join(ARCH, 'STATUS_APP_sec168_20261110.md')

WIN_JSON = os.path.join(EVID, 'app400_window_samesource_check.json')
CIT_JSON = os.path.join(EVID, 'status_citations_sweep_20261110.json')
CMT_JSON = os.path.join(EVID, 'app401_comment_only_proof.json')

# ── 开工基线（本轮 17:55 记录，实测）────────────────────────────────
OPEN_SHA = '36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2'
OPEN_BYTES = 285671
OPEN_MTIME = '2026-11-10 11:49:26'
OPEN_ENTRIES = 97


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now_str() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def main() -> int:
    win = json.load(open(WIN_JSON, encoding='utf-8'))
    cit = json.load(open(CIT_JSON, encoding='utf-8'))
    cmt = json.load(open(CMT_JSON, encoding='utf-8'))

    # ── ① §168 正文整块逐字归档 ───────────────────────────────────
    raw = open(STATUS, 'rb').read()
    text = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in text else '\n'
    body = text.replace('\r\n', '\n')

    m = re.search(r'^## §168 .*$', body, re.M)
    assert m, '§168 未找到'
    start168 = m.start()
    nxt = re.search(r'^## §\d+ .*$', body[start168 + 10:], re.M)
    end168 = (start168 + 10 + nxt.start()) if nxt else len(body)
    sec168_full = body[start168:end168]

    # 头部（首个 `## ` 之前）与章节正文分开：**头部本轮要改 4 行**，
    # 「旧正文逐字未变」的校验只针对**章节正文**（头部改动是明文允许的）。
    h_match = re.search(r'^## ', body, re.M)
    assert h_match, '未找到首个 `## ` 标题'
    header_part = body[:h_match.start()]
    sections_prefix = body[h_match.start():start168]

    with open(SEC_ARCH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(sec168_full)
    arc_bytes = os.path.getsize(SEC_ARCH)
    arc_sha = sha256_bytes(open(SEC_ARCH, 'rb').read())
    assert arc_bytes == len(sec168_full.encode('utf-8')), '归档字节数与源块不符'

    # 替身：保留 §168 的标题行（原文一字不改）＋ 归档指针（≤3 行）
    title168 = sec168_full.split('\n')[0]
    stub168 = (
        title168 + '\n\n'
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec168_20261110.md`'
        '（%d B／块 SHA256 `%s`）。\n' % (arc_bytes, arc_sha))

    # ── ② 纠偏文件指纹（**实测**）────────────────────────────────
    cb = open(CORR, 'rb').read()
    corr_sha = sha256_bytes(cb)
    corr_bytes = len(cb)
    corr_mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(CORR)).strftime('%Y-%m-%d %H:%M:%S')
    corr_entries = len(re.findall(r'^## APP-\d+', cb.decode('utf-8'), re.M))
    corr_same = (corr_sha == OPEN_SHA and corr_bytes == OPEN_BYTES
                 and corr_mtime == OPEN_MTIME and corr_entries == OPEN_ENTRIES)
    corr_note = ('🔴 **收尾复核与开工基线完全一致** ⇒ reviewer 本轮中途**未追加**新条目'
                 if corr_same else
                 '🔴 **收尾复核与开工基线不一致**（reviewer 本轮中途追加了内容）'
                 '⇒ **如实记录，不声称「SHA 零改动」**')

    # ── ③ §169 正文 ──────────────────────────────────────────────
    wchecks = {c['name']: c for c in win['checks']}
    cchecks = {c['name']: c for c in cmt['checks']}
    n_win_pass = win['n_pass']
    n_win_fail = win['n_fail']
    n_cit_bad = cit['n_bad_live']
    n_cit_arch = cit['n_archive_findings']
    n_cit_files = cit['n_files_scanned']
    n_cit_cited = cit['n_cited_unique_live']
    n_cit_ok = cit['n_ok_live']
    n_cit_known = cit['n_known_phantom_live']
    n_cit_ph = cit['n_placeholder_live']
    n_cmt_pass = cmt['n_pass']
    n_cmt_fail = cmt['n_fail']
    stmts = next(d['detail'] for d in cmt['checks'] if d['name'] == 'stmt_multiset_same')

    body169 = """
### ① 开工/收尾基线（纠偏文件**只读**）

| 项 | 开工基线 | 收尾复核（实测） |
|---|---|---|
| `status/app/CORRECTIONS_APP.md` SHA256 | `%s` | `%s` |
| 字节数 | %d | %d |
| mtime | %s | %s |
| `## APP-xxx` 条数 | %d | %d |

* %s
* 🔴 **无编号 > APP-097 的新条目** ⇒ 本轮**无新纠偏可执行**；`last_ack` 保持 **APP-097**。
* 🔴 纠偏文件全程**只读、未改、未提交**。

### ② 本轮做了什么（**不是巡检脚本空转** ⇒ 补做了 App 职责内的两件真缺陷）

* 本轮**无新纠偏**，但按 APP-093 ②(d)「**产物缺失或与 STATUS 不一致**」这条
  （reviewer 已在 §164 就抓到过同类「引用了不存在的 json」），
  **逐条核对了 STATUS 引用的产物是否真的在磁盘上** ⇒ **查出 2 个真缺陷**（详见 ③④）。
* ② 处两项都是 **App 模块自己的代码/文档缺陷**，**不需要 reviewer 裁定口径**
  ⇒ 属「可自行补做」的 App 职责内事项（与 reviewer 门控项不冲突）。

### ③ 🔴 缺陷一：§167 归档件引用了一个**磁盘上不存在**的产物路径（同 APP-093 ②(d) 类）

* **现象**：`status/archive/STATUS_APP_sec167_20261110.md` §④ 表格里写的是
  `results/app/_app326_app097_lang_out/mt.json`
  ⇒ **该路径不存在**（多了一个前导下划线；`git log --all --diff-filter=A` 证明
  **该路径从未在任何 commit 里存在过** ⇒ 不是被删，是**从未写对**）。
* **真实文件**：`results/app/app326_app097_lang_out/mt.json`（122 674 B）。
* **数字本身是对的**（逐字段复核 `summary`）：8 语种 × 20 句 = **160 行**；
  **n_empty 全 8 语种合计 0**；**n_error 合计 0**；
  `out_lang_ok_rate` **8 语种全为 1.0**；`zh_skipped_rate = 1.0`
  ⇒ **§167 ④ 的结论完全成立**，**只是路径写错**（⇒ **不是**「幻影产物」，与 app391 性质不同）。
* **处置**：**归档件按「逐字冻结」不改**（`status/archive/STATUS_APP_sec*` 全部 write-once）
  ⇒ **在本节写明正确路径**，并加一道**可复跑的静态闸门**把这类缺陷**今后自动拦住**
  （见 ⑤ 的 `live_caption/assert_status_citations.py`）。

### ④ 🔴 缺陷二：App 侧旁路窗长的**注释与 ASR 现状不符**（含一句**会误导后人改坏代码**）

* **ASR 现状**（实测客户包 v2.4 的 `app/asr_spk/asr_spk_window.py`）：
  `WIN_S_DEFAULT = 5.0`／`WIN_S = 5.0`／`WIN_N = 80000`／
  `KNOWN_WINDOWS = {10.0: (589, 58.9), 5.0: (293, 58.6)}`。
* **dev 树 `live_caption/speaker_tracker.py` 的注释却仍写着**：
  「ASR 侧 `asr052_spk_runtime.WIN_S = 10.0`（`WIN_N = 160000` 样本）」、
  「喂满一整窗时帧数恰好 **589**」、「读不到时退回 10.0（**= ASR 侧默认值**）」。
  ⇒ ① 与 ASR 现状**不符**；② 最要紧的是最后那句**「= ASR 侧默认值」是错的**
  （ASR 默认早已是 **5.0**）⇒ **会诱导后人把 `_WIN_S_DEFAULT` 从 10.0 改成 5.0**。
* 🔴 **但 10.0 这个值本身是对的、不能改**：它与 `speaker_assets.find_seg_ir()`
  在「窗长读不到」时的 IR 兜底**配套**
  （`SEG_PRECISITIES` 首项 `fp16` = **160000 样本 = 10 s**）
  ⇒ 两边都退到 10 s ⇒ shape 仍匹配。
  **若把它改成 5.0** ⇒ App 喂 5 s 而 IR 仍是 10 s 的 `fp16`
  ⇒ **输入 shape 不兼容 ⇒ 旁路静默降级、零标签**（= APP-067⑤ 同款故障形态）。
* **处置**：**只改注释**（把「10.0 = ASR 默认值」这句假陈述改成「10.0 = 与 IR 兜底配套」），
  **不动任何可执行代码** ⇒ 用 AST 证明（见 ⑤ 的 `app401`）。

### ⑤ 本轮新增的 3 道**可复跑静态闸门**（纯 CPU / 静态 / 不占 GPU·NPU / 不需 MACHINE_LOCK）

| 闸门 | 作用 | 本轮结果 | 产物 |
|---|---|---|---|
| `live_caption/assert_status_citations.py` | **STATUS 引用产物路径必须能在磁盘上定位**（把 APP-093 ②(d) 机械化） | 活文档 **%d 条引用 / %d 条可定位 / %d 条坏引用 ⇒ PASS**；归档件 %d 条旧笔误**只登记不判 FAIL**（归档件是冻结的历史正文） | `results/app/status_citations_sweep_20261110.json`（%d B） |
| `live_caption/assert_window_same_source.py` | **旁路窗长必须与 ASR 唯一事实来源同源**，且**兜底窗长必须与 IR 兜底配套** | **%d PASS / %d FAIL ⇒ PASS**（含 2 条反证组：ASR 默认改 7.0 ⇒ App 跟随 7.0；把兜底改成 5.0 ⇒ 判据必须 FAIL） | `results/app/app400_window_samesource_check.json`（%d B） |
| `results/app/_app401_comment_only_proof.py` | 证明本轮对 `speaker_tracker.py` 的改动**只动注释**（AST 口径） | **%d PASS / %d FAIL ⇒ PASS**（%s） | `results/app/app401_comment_only_proof.json`（%d B） |

* 🔴 **闸门自身的判据被本轮修掉过一次**：第一版 `assert_window_same_source.py` 的判据是
  「兜底 == ASR 当前默认值」⇒ 实测 **FAIL** ⇒ 但该判据**本身是错的**
  （会把 10.0 诱导改成 5.0 ⇒ 破坏 IR 配套）⇒ 已改成
  「**兜底窗长 == IR 兜底窗长**」并补了反证组 ⇒ 现 **%d/%d PASS**。
  ⇒ **这是「判据自身缺陷」的一次实例，已如实记录，未把错的判据留进仓库。**

### ⑥ 未做 / 停下等 reviewer（本轮**一律未自行推进**）

* 🔴 **GUI 布局缺陷**（`874924a` 把 `_clone_nearest` 误插进 `App.__init__` ⇒ GUI 一直是空壳）
  仍**只修在开发树 + 影子包** ⇒ **未同步进任何客户包目录、未打 v2.5、未通知用户**
  （APP-055）⇒ **等 reviewer 裁定**（立刻修 vs 随 v2.5 一起出）。
* 🔴 **§3.5 音色归属判据失效**（三人真值 x-vector 两两余弦 0.957–0.972 ⇒ 余弦尺度不可分）
  ⇒ **未自行换判据**。
* 🔴 **§3.6 的「切段真实发生时的设备开销」**仍无法在当前素材上测得（质心恒 1）
  ⇒ **需 reviewer 裁定**是否允许调聚类阈值/换素材，**本轮未改任何默认值**。
* 🔴 **跳过率阈值取舍**仍由 reviewer 拿 §3.1/§3.2 数字报主会话请用户决定（**默认值仍 6.0**）。
* 🔴 **未打包 v2.5、未通知用户、未调 MiniMax、未改任何默认值**。
""" % (
        OPEN_SHA, corr_sha, OPEN_BYTES, corr_bytes, OPEN_MTIME, corr_mtime,
        OPEN_ENTRIES, corr_entries, corr_note,
        n_cit_cited, n_cit_ok, n_cit_bad, n_cit_arch,
        len(open(CIT_JSON, 'rb').read()),
        n_win_pass, n_win_fail, len(open(WIN_JSON, 'rb').read()),
        n_cmt_pass, n_cmt_fail, stmts, len(open(CMT_JSON, 'rb').read()),
        n_win_pass, n_win_pass + n_win_fail,
    )

    # ── ④ 组装新文件 ────────────────────────────────────────────
    # 结构（每块都**可逆** ⇒ 末尾 reconstruct() 反向还原后必须逐字等于旧全文）：
    #   [新头部] + [旧章节正文(§168 之前，含新增的「最近更新」一行)]
    #   + [§168 替身] + [新增 §169]

    # 头部 6 行（last_ack / 更新时间 / 当前任务 / 阻塞 / 已压缩）
    hdr_lines = header_part.split('\n')
    assert hdr_lines[2].startswith('last_ack:'), '头部结构异常：%r' % hdr_lines[2]
    hdr_lines[2] = 'last_ack: APP-097'
    assert hdr_lines[3].startswith('更新时间:'), '头部结构异常：%r' % hdr_lines[3]
    hdr_lines[3] = '更新时间: ' + now_str()
    assert hdr_lines[4].startswith('当前任务:'), '头部结构异常：%r' % hdr_lines[4]
    hdr_lines[4] = ('当前任务: **巡检无新纠偏**（`last_ack=APP-097`，纠偏文件仍 97 条）｜'
                    '**本轮查出并修掉 2 个 App 侧真缺陷**（§167 归档件引用了不存在的产物路径；'
                    '`speaker_tracker.py` 旁路窗长注释与 ASR 现状不符且含会误导改坏代码的假陈述）'
                    '＋ 新增 3 道可复跑静态闸门 ⇒ 结果见 §169｜**本条需等 reviewer 复核**')
    assert hdr_lines[5].startswith('阻塞 / 待用户决定:'), '头部结构异常：%r' % hdr_lines[5]
    hdr_lines[5] = hdr_lines[5]  # 阻塞行**本轮不变**（未新增门控项）
    assert hdr_lines[6].startswith('已压缩:'), '头部结构异常：%r' % hdr_lines[6]
    hdr_lines[6] = hdr_lines[6].rstrip() + (
        '｜**§168 压缩**：§168 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec168_20261110.md`'
        '（%d B／块 SHA256 `%s`）' % (arc_bytes, arc_sha))
    new_header = '\n'.join(hdr_lines)

    # 「最近更新」加一行（插到 `## 最近更新` 之后的第一条 `> ` 前）
    recent_line = (
        '> 🔴 ' + now_str() + ' ｜ **巡检无新纠偏**（纠偏文件仍 97 条 / `last_ack=APP-097`）；'
        '**查出并修掉 2 个 App 侧真缺陷**：① §167 归档件引用了**磁盘上不存在**的路径 '
        '`results/app/_app326_app097_lang_out/mt.json`（真实路径 `results/app/app326_app097_lang_out/mt.json`，'
        '122 674 B；**§167 ④ 的数字逐字段复核全部成立** ⇒ 只是路径写错）｜'
        '② `speaker_tracker.py` 注释仍写「ASR 侧默认 10 s / 589 帧 / 兜底 10.0 = ASR 侧默认值」'
        '⇒ **与 ASR 现状（5.0 / 293 帧）不符**，且「= ASR 侧默认值」这句**假陈述会诱导把兜底改成 5.0 '
        '⇒ 破坏 IR 配套 ⇒ 旁路静默降级** ⇒ **只改注释、不动代码**（AST 证明 %d/%d PASS）｜'
        '新增 3 道静态闸门（引用路径可定位 %d/%d PASS、窗长同源+兜底配套 %d/%d PASS、注释-only AST 证明）'
        '｜**本条需等 reviewer 复核**；未打 v2.5、未通知用户、未调 MiniMax、未改任何默认值。'
        % (n_cmt_pass, n_cmt_pass + n_cmt_fail, n_cit_ok, n_cit_ok + n_cit_bad,
           n_win_pass, n_win_pass + n_win_fail))
    ru = sections_prefix.find('## 最近更新')
    assert ru >= 0, '未找到「## 最近更新」'
    ins = sections_prefix.find('\n> ', ru)
    assert ins >= 0, '「最近更新」下未找到条目行'
    new_sections_prefix = (
        sections_prefix[:ins + 1] + recent_line + '\n' + sections_prefix[ins + 1:])

    sec169_head = (
        '\n## §169 巡检（last_ack=APP-097，%s）｜**无新纠偏**；查出并修掉 2 个 App 侧真缺陷'
        '（§167 归档件引用了不存在的产物路径／旁路窗长注释与 ASR 现状不符）＋ 新增 3 道静态闸门'
        '｜**本条需等 reviewer 复核**\n' % now_str())
    new_body = (new_header + new_sections_prefix + stub168 + sec169_head + body169)

    # ── ⑤ 写前自检 ──────────────────────────────────────────────
    new_lines = new_body.split('\n')
    n_sec_old = len(re.findall(r'^## ', body, re.M))
    n_sec_new = len(re.findall(r'^## ', new_body, re.M))
    assert n_sec_new == n_sec_old + 1, '章节数异常：%d → %d（应 +1）' % (n_sec_old, n_sec_new)
    # §168 的标题行逐字保留
    assert title168 in new_body, '§168 标题行未保留'
    # 行尾未破
    assert '\r\n' not in new_body, '写入了 CRLF'
    # 限额
    nb = len(new_body.encode('utf-8'))
    assert nb <= 40000, '超过 40 KB：%d' % nb
    assert len(new_lines) <= 300, '超过 300 行：%d' % len(new_lines)

    # 🔴 **反向还原校验**（最强的一条）：把本轮的 4 处改动逐条还原 ⇒ 必须逐字等于旧全文
    def reconstruct(nb_):
        x = nb_
        x = x.replace(new_header, header_part, 1)      # 还原头部 6 行
        x = x.replace(recent_line + '\n', '', 1)        # 删掉「最近更新」新增行
        x = x.replace(stub168, sec168_full, 1)          # 还原 §168 正文
        i = x.find('\n## §169 ')
        assert i > 0, '未找到 §169 段'
        # 🔴 `x[:i]` 已经以 '\n' 结尾（§168 正文原本就以换行收尾）
        #    ⇒ 这里**不能再补 '\n'**（否则多 1 字节）。
        x = x[:i]                                          # 删掉 §169 段
        return x

    restored = reconstruct(new_body)
    assert restored == body, '反向还原 != 旧全文（差 %d 字节）' % (len(restored) - len(body))

    # ── ⑥ 落盘（临时文件 + 原子替换）────────────────────────────
    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_body)
    os.replace(tmp, STATUS)

    # 写后复核
    after = open(STATUS, 'rb').read().decode('utf-8')
    assert after == new_body, '写后逐字节复核不一致'
    out = {
        'ts': now_str(),
        'status_bytes': len(after.encode('utf-8')),
        'status_lines': len(after.split('\n')),
        'n_sections': n_sec_new,
        'sec168_archive': os.path.relpath(SEC_ARCH, REPO).replace('\\', '/'),
        'sec168_archive_bytes': arc_bytes,
        'sec168_archive_sha256': arc_sha,
        'sec168_block_sha256': sha256_bytes(sec168_full.encode('utf-8')),
        'old_body_unchanged': True,
        'reverse_restore_ok': True,
        'eol': 'LF',
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
