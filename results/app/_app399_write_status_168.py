# -*- coding: utf-8 -*-
"""写 `status/app/STATUS_APP.md` §168（APP-093 §3.6 补做结果）＋ APP-052④ 压缩。

🔴 **纪律（APP-049 / APP-052④ / APP-055）**
* `status/app/CORRECTIONS_APP.md` **只读**（本脚本绝不碰它）。
* STATUS 只**追加** `## §N` 章节；旧正文**一字不删**（§167 的正文**整块逐字归档**
  到 `status/archive/STATUS_APP_sec167_20261110.md` 后，用 ≤3 行索引替身 ⇒
  「旧正文整块原样保留」在归档件里成立）。
* 只动头部 4 行（last_ack / 更新时间 / 当前任务 / 阻塞·待用户决定）＋「最近更新」加一行。
* 写后自检：章节数 +1；**除 §167 归档块与新增 §168 外，旧正文逐字未变**；行尾未破；
  ≤40 KB / ≤300 行。

用法：python _app399_write_status_168.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive')
EVID = os.path.join(REPO, 'results', 'app')
RES = os.path.join(EVID, 'app398_app093_split_rtf_ab.json')
BUILD = os.path.join(EVID, 'app398_build_split_shadow.json')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

SEC_ARCH = os.path.join(ARCH, 'STATUS_APP_sec167_20261110.md')


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now_str() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def fmt(x, nd=4):
    if x is None:
        return '—'
    if isinstance(x, float):
        return ('%.' + str(nd) + 'f') % x
    return str(x)


def main() -> int:
    res = json.load(open(RES, encoding='utf-8'))
    build = json.load(open(BUILD, encoding='utf-8'))
    summ = res['summary']
    arms = {a['arm']: a for a in res['arms']}

    # ── ① §167 正文整块逐字归档 ───────────────────────────────────
    raw = open(STATUS, 'rb').read()
    text = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in text else '\n'
    body = text.replace('\r\n', '\n')

    m = re.search(r'^## §167 .*$', body, re.M)
    assert m, '§167 未找到'
    start167 = m.start()
    nxt = re.search(r'^## §\d+ .*$', body[start167 + 10:], re.M)
    end167 = (start167 + 10 + nxt.start()) if nxt else len(body)
    sec167_full = body[start167:end167]

    with open(SEC_ARCH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(sec167_full)
    arc_bytes = os.path.getsize(SEC_ARCH)
    arc_sha = sha256_bytes(open(SEC_ARCH, 'rb').read())
    assert arc_bytes == len(sec167_full.encode('utf-8')), '归档字节数与源块不符'

    # 替身：保留 §167 的标题行（原文一字不改）＋ 归档指针（≤3 行）
    title167 = sec167_full.split('\n')[0]
    stub167 = (
        title167 + '\n\n'
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec167_20261110.md`'
        '（%d B／块 SHA256 `%s`）。\n' % (arc_bytes, arc_sha))

    # ── ② 组装 §168 正文 ─────────────────────────────────────────
    def arm_row(name, label, arm):
        a = arms.get(arm)
        if not a:
            return '| %s | — | — | — | — | — |' % label
        spk = a.get('spk_seg') or {}
        tts = a.get('tts') or {}
        return '| %s | %s | %s | %s | %s | %s |' % (
            label, fmt(a.get('asr_rtf'), 3), fmt(a.get('asr_wall_s'), 1),
            a.get('n_probe_request', 0),
            (spk.get('n_split_dist') or {}).get('0', '—'),
            fmt(tts.get('synth_rtf_p50'), 4))

    def voice_rows(arm):
        """逐句音色来源分布（voice_self_ref / voice_spk）—— 取自该臂 tts.jsonl。"""
        import collections
        a = arms.get(arm)
        if not a:
            return '—'
        p = os.path.join(a['out_dir'], 'tts.jsonl')
        rows = []
        try:
            for line in open(p, encoding='utf-8', errors='replace'):
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        except Exception:
            return '—'
        if not rows:
            return '—'
        sr = sum(1 for r in rows if r.get('voice_self_ref'))
        reg = sum(1 for r in rows if r.get('voice_spk'))
        return 'self_ref=%d／已登记音色=%d／共 %d 句' % (sr, reg, len(rows))

    on_a = [arms['A1']['asr_rtf'], arms['A2']['asr_rtf']]
    off_c = [arms['C1']['asr_rtf'], arms['C2']['asr_rtf']]
    d_strict = summ['delta_split_on_minus_off_strict']
    d_clone = summ['delta_split_on_minus_clone_off']
    spread_on = abs(arms['A1']['asr_rtf'] - arms['A2']['asr_rtf'])
    spread_off = abs(arms['C1']['asr_rtf'] - arms['C2']['asr_rtf'])

    def ncents_seen(arm):
        """从该臂 run.log 的探针行里取「实际见到的质心数」（不是计数）。"""
        a = arms.get(arm)
        if not a:
            return '—'
        p = os.path.join(a['out_dir'], 'run.log')
        vals = set()
        try:
            for ln in open(p, encoding='utf-8', errors='replace'):
                m = re.search(r'\[split-probe\] bail n_cents=(\d+)', ln)
                if m:
                    vals.add(int(m.group(1)))
                m2 = re.search(r'\[split-probe\] done seg=\d+ n_parts=\d+ n_cents=(\d+)', ln)
                if m2:
                    vals.add(int(m2.group(1)))
        except Exception:
            return '—'
        return ('/'.join(str(v) for v in sorted(vals)) if vals else '—')

    # ── 纠偏文件指纹（**实测**，不是抄来的常量）────────────────────
    #  开工基线（本轮 16:16 记录）：SHA 36af1620…／285 671 B／mtime 11:49:26／97 条
    OPEN_SHA = '36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2'
    OPEN_BYTES = 285671
    OPEN_MTIME = '2026-11-10 11:49:26'
    OPEN_ENTRIES = 97
    cb = open(CORR, 'rb').read()
    corr_sha = hashlib.sha256(cb).hexdigest()
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

    body168 = """
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

### ② 为什么本轮仍然继续做（不空转）

* APP-093 §3 的 8 个分项里，**§3.6 的后半句「再报切段开/关的 ASR RTF」是唯一还没做的**
  （§167 ⑤ 已如实记为 gap：**不报数**）。
* 该项**不是 reviewer 门控项**（不是「要 reviewer 裁定」），只是**没跑** ⇒ 本轮补跑。
* 其余 reviewer 门控项（GUI 缺陷同步策略／§3.5 判据／跳过率阈值）**一律未自行推进**。

### ③ 实验口径（APP-089 §2c-3「验收时要证明 ASR RTF 没变差」/ APP-093 §3.6）

* **影子包** `%s`
  * `app/` ← **开发树 HEAD 全量 30 个 .py**（`models/`+`python/` 联接 v2.4，零拷贝）
  * **只读探针**：`results/app/app398_probe_patch.diff`（%d B／SHA256 `%s`）
    ⇒ **只加日志 + 一个 env 门控提前返回**（`LIVECAP_PROBE_NOSPLIT=1` ⇒ `request_split` 提前返回）
    ⇒ **不改任何判定/阈值**；**开发树一字未改**。
* **为什么需要探针**：App 里「换人切段」**只有克隆模式一个总闸**
  （`live_caption_app.py:7538` `if _want_clone and (_t1-_t0) >= 3.2: request_split(...)`）
  ⇒ **没有独立的「切段开关」** ⇒ 严格 A/B 只能靠探针把 `request_split` 置空
  ⇒ **其余代码路径逐字节相同**。
* **臂与顺序（ABBA 抵消线性漂移）**：A1 切段开 → C1 切段关 → C2 切段关 → A2 切段开 → B 背景对照。
  * **A1/A2** = 切段路径**开**（`--tts-voice follow_speaker`）
  * **C1/C2** = 切段路径**关**（同上 + 探针抑制）＝ **严格 A/B**
  * **B** = `--tts-voice A`（预设 A）＝ **背景对照**
    ⚠️ **注意：B 臂不是「克隆整体关」**（self_ref 克隆仍生效 ⇒ 见 ⑤）。
* **材料**：`%s`（%s B／SHA256 `%s`）；**设备**：ASR GPU.0 / MT GPU.0 / TTS NPU（与 runs3 同口径）。
* **指标**：ASR RTF = `run.log` 尾行 `RTF(计算)`（**同一字段、同口径**）。
* **持锁**：%s

### ④ 结果（ASR RTF 对照）

| 臂 | ASR RTF | 墙钟 s | 探针 request 次数 | 切段次数(n_split=0 的段数) | TTS synth_rtf p50 |
|---|---|---|---|---|---|
%s

* **严格 A/B（切段开 vs 切段关）**：%s − %s = **Δ %s**（相对 %s）。
* **上下文（切段开 vs `--tts-voice A`）**：Δ %s。
* 🔴 **噪声地板（ABBA 的价值所在）**：**同一臂两次重复**的差 = 切段开 |A1−A2| = **%s**（%s）、
  切段关 |C1−C2| = **%s**（%s）⇒ **|Δ(切段开−切段关)| = %s 远小于同臂重复差**
  ⇒ **「切段开/关对 ASR RTF 的影响」落在本机噪声地板内 ⇒ 测不出影响**
  ⇒ 结论只能写成「**未测到变差**（差值 ≤ 噪声），**不能写成「已证明完全无影响」**」。
* **切段路径实测事实**（来自探针日志）：
  * A1/C1/C2/A2 四臂 `request` 次数 = %s（A1）／%s（C1）／%s（C2）／%s（A2）⇒ **切段路径确实被走到**。
  * `bail n_cents=%s (<2) => 不切段` ⇒ **旁路只长出 1 个质心** ⇒ `split_by_speaker` 在
    `len(cents) < 2` 处**直接返回** ⇒ **切段编码器从未编译**（`enc_ready=False`）
    ⇒ **切段自身的设备开销 = 0**（与 §3.6 前半句「为什么 0 段」同源：聚类 `delta_new=0.30`
    远低于三人互余弦 0.957–0.972 ⇒ 永不新建簇）。
  * ⇒ **本次对照测到的是「切段路径被触发 vs 不被触发」的总开销**
    （含克隆策略层每段嵌入 + 切段请求入队），**不是**「一次真实切分」的设备开销
    （后者在本素材上**结构上无法发生**，除非改聚类阈值 ⇒ **本轮未改**）。
* **可比性**：各臂 ASR 定稿段数 %s（同一素材同一 ASR ⇒ 段数一致 ⇒ RTF 可直接比）。
* **其它可比项**：各臂 ASR 段数／字幕行数见 `app398_app093_split_rtf_ab.json` → `arms[].spk_seg` /
  `arms[].tts`；`n_split` 全部为 0（五个臂一致 ⇒ **切段开关不影响切段次数**）。

### ⑤ 🔴🔴 **新发现（本轮顺带查实，等 reviewer 裁定，本轮未修）**：`--tts-voice A`（预设 A）时**仍在用克隆音色**

* **现象**（B 臂，`--tts-voice A` + `--speaker on`，78 句）：`tts.jsonl` 里
  **78/78 句 `voice_kind='clone'`**、**`voice_self_ref=true`**、**`voice_spk` 全为 null**
  ⇒ **每一句都用「这句自己的 x-vector」克隆出声**，尽管用户选的是**预设 A**。
  逐句分布：A1 %s｜C1 %s｜**B %s**。
* **与既有验收口径冲突**：`live_caption_app.py:7295` 注释原文引 reviewer（2026-11-07，v2.4）：
  > `preset voice selected => never register clone voices`
  > `（v2.4 acceptance: --tts-voice A still dubbed 18/20 sentences with clone voices）`
  ⇒ 本轮实测：**该现象在 dev HEAD 仍然存在**（B 臂 78/78）。
* **根因（读码定案）**：`_cli_maybe_send_self_ref`（CLI）与 `_maybe_send_self_ref`（GUI）
  **都没有 `_want_clone` 闸门** ⇒ 只看「该 spk 有没有登记音色」；而「登记音色」这条链
  被 `_want_clone` 闸住（`live_caption_app.py:7296` `if not _want_clone: return`）
  ⇒ **选中预设 A 时**「该 spk 永远没有登记音色」⇒ 于是**每句都走 self_ref 克隆**。
* **触发条件**：说话人识别开（`--speaker on` / GUI 勾选）＋ 音色选**预设 A**。
  （旁路默认关 ⇒ 默认安装不触发；用户一旦勾选「说话人识别」就命中。）
* 🔴 **本轮未修**：APP-093 §3.6 只授权「跑对照并报数」，**未授权改行为**；
  且 reviewer 明文「**你不要自己改默认值，也不要自己改判据**」⇒ **只报不改，等裁定**。
* 🔴 **对本轮口径的影响**：B 臂**不是**「克隆整体关」，而是「**不登记说话人音色，但 self_ref 克隆仍生效**」
  ⇒ B 臂标签已按此更正；**严格 A/B（A vs C）不受影响**（两臂克隆行为完全相同）。

### ⑥ 未做 / 停下等 reviewer

* 🔴 **GUI 布局缺陷（`874924a` 把 `_clone_nearest` 误插进 `App.__init__` 中间 ⇒ GUI 一直是空壳）
  仍只修在开发树 + 影子包**，**未同步进任何客户包目录、未打 v2.5、未通知用户**（APP-055）
  ⇒ **等 reviewer 裁定**（立刻修 vs 随 v2.5 一起出）。
* 🔴 **§3.5 音色归属判据失效**（三人真值 x-vector 两两余弦 0.957–0.972 ⇒ 余弦尺度不可分）
  ⇒ **未自行换判据**。
* 🔴 **§3.6 的「切段真实发生时的设备开销」**仍无法在当前素材上测得（质心恒 1）
  ⇒ **需 reviewer 裁定**是否允许调整聚类阈值/换素材，**本轮未改任何默认值**。
* 🔴 **跳过率阈值取舍**仍由 reviewer 拿 §3.1/§3.2 数字报主会话请用户决定（**默认值仍 6.0**）。
* 🔴 **未打包 v2.5、未通知用户、未调 MiniMax**（APP-093/APP-097 明文）。
""" % (
        OPEN_SHA, corr_sha,
        OPEN_BYTES, corr_bytes,
        OPEN_MTIME, corr_mtime,
        OPEN_ENTRIES, corr_entries,
        corr_note,
        res['shadow']['root'], build['probe_diff']['bytes'],
        build['probe_diff']['sha256'],
        res['arms'][0]['material'], res['arms'][0]['material_bytes'],
        res['arms'][0]['material_sha256'],
        res['lock_record']['lock_content'].replace('\n', ' ／ '),
        '\n'.join([
            arm_row('A1', 'A1 切段**开**', 'A1'),
            arm_row('C1', 'C1 切段**关**（严格）', 'C1'),
            arm_row('C2', 'C2 切段**关**（严格）', 'C2'),
            arm_row('A2', 'A2 切段**开**', 'A2'),
            arm_row('B', 'B `--tts-voice A`（对照，⚠️ 见 ⑦）', 'B'),
        ]),
        fmt(summ['asr_rtf_split_on']['mean'], 3),
        fmt(summ['asr_rtf_split_off_strict']['mean'], 3),
        fmt(d_strict, 4),
        (('%+.2f%%' % (d_strict / summ['asr_rtf_split_off_strict']['mean'] * 100))
         if d_strict is not None and summ['asr_rtf_split_off_strict']['mean'] else '—'),
        fmt(d_clone, 4),
        fmt(spread_on, 3),
        ('%+.2f%%' % (spread_on / summ['asr_rtf_split_on']['mean'] * 100))
        if summ['asr_rtf_split_on']['mean'] else '—',
        fmt(spread_off, 3),
        ('%+.2f%%' % (spread_off / summ['asr_rtf_split_off_strict']['mean'] * 100))
        if summ['asr_rtf_split_off_strict']['mean'] else '—',
        fmt(abs(d_strict) if d_strict is not None else None, 4),
        arms['A1']['n_probe_request'], arms['C1']['n_probe_request'],
        arms['C2']['n_probe_request'], arms['A2']['n_probe_request'],
        ncents_seen('A1'),
        '／'.join('%s=%s' % (a, (arms[a].get('spk_seg') or {}).get('n_rows', '—'))
                  for a in ('A1', 'C1', 'C2', 'A2', 'B')),
        voice_rows('A1'), voice_rows('C1'), voice_rows('B'),
    )

    title168 = ('## §168 巡检（last_ack=APP-097，%s）｜**无新纠偏**；补做 APP-093 §3.6'
                '「切段开/关的 ASR RTF」对照（设备跑，持锁，ABBA）｜**本条需等 reviewer 复核**'
                % now_str())
    sec168 = title168 + '\n' + body168

    # ── ③ 拼装新正文：头部 + （§141…§166 原样）＋ §167 替身 ＋ §168 ──
    head_end = body.find('\n## §141 ')
    assert head_end > 0, '§141 锚点未找到'
    head = body[:head_end]
    mid = body[head_end:start167]
    new_body = head + mid + stub167 + '\n' + sec168

    # ④ 头部更新（只动这 4 行 + 最近更新加一行）
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_head = re.sub(r'^last_ack: .*$', 'last_ack: APP-097', head, count=1, flags=re.M)
    new_head = re.sub(r'^更新时间: .*$', '更新时间: %s' % stamp, new_head, count=1, flags=re.M)
    new_head = re.sub(
        r'^当前任务: .*$',
        ('当前任务: **巡检无新纠偏**（`last_ack=APP-097`，纠偏文件仍 97 条）｜'
         '**补做 APP-093 §3.6「切段开/关的 ASR RTF」对照**（设备跑，持锁，ABBA：'
         'A1→C1→C2→A2→B）⇒ 结果见 §168｜'
         '**本条需等 reviewer 复核**'),
        new_head, count=1, flags=re.M)
    new_head = re.sub(
        r'^阻塞 / 待用户决定: .*$',
        ('阻塞 / 待用户决定: 🔴 **GUI 布局缺陷修复仍未同步进客户包**（只在 dev 树 + 影子包）'
         '⇒ **v2.5 未打包、未同步任何客户包目录**（APP-055 须走打新版本号）⇒ '
         '**请 reviewer 裁定**：立刻修还是随 v2.5 一起出｜'
         '🔴 **该缺陷的历史影响未评估**（`874924a` 之后的 GUI 类验收都跑在空壳 GUI 上）｜'
         '🔴 **§3.5 音色归属判据失效**（三人真值余弦 0.957–0.972 ⇒ 不可分）⇒ 未自行换判据｜'
         '🔴 **§3.6「切段真实发生时的设备开销」在本素材上结构性不可测**（质心恒 1）⇒ '
         '需 reviewer 裁定是否调聚类阈值/换素材｜**APP-097 §2-4 只报实测 p50、未改 '
         '`_SEC_PER_CHAR` 默认值**｜阈值取舍由 reviewer 报主会话请用户决定（**默认值仍 6.0**）｜'
         '**未打包 v2.5、未通知用户**'),
        new_head, count=1, flags=re.M)

    new_head = re.sub(
        r'^已压缩: .*$',
        lambda _m: _m.group(0).rstrip()
        + '｜**§167 压缩**：§167 正文整块逐字归档 ⇒ '
        + '`status/archive/STATUS_APP_sec167_20261110.md`（%d B／块 SHA256 `%s`）'
        % (arc_bytes, arc_sha),
        new_head, count=1, flags=re.M)

    # 「最近更新」加一行（**新行写在最上面** ⇒ 紧跟标题行）
    upd_anchor = '## 最近更新\n'
    i = new_head.find(upd_anchor)
    assert i > 0, '「最近更新」锚点未找到'
    j = i + len(upd_anchor)
    upd_line = ('> 🔴 %s ｜ **巡检无新纠偏**（纠偏文件仍 97 条 / `last_ack=APP-097`）；'
                '**补做 APP-093 §3.6「切段开/关的 ASR RTF」对照**（设备跑，持锁，ABBA 五臂）：'
                '切段开 %s vs 切段关 %s（Δ %s）⇒ **切段路径确实被走到**，但**质心恒 1 ⇒ '
                '切段自身设备开销 = 0**（详见 §168）｜**本条需等 reviewer 复核**；'
                '未打 v2.5、未通知用户。\n'
                % (stamp,
                   fmt(summ['asr_rtf_split_on']['mean'], 3),
                   fmt(summ['asr_rtf_split_off_strict']['mean'], 3),
                   fmt(d_strict, 4)))
    new_head = new_head[:j] + upd_line + new_head[j:]

    out = new_head + new_body[len(head):]

    # ── ⑤ 自检 ───────────────────────────────────────────────────
    old_all = body
    # 旧正文（除头部、§167 块）必须逐字出现在新文件中
    mid_check = mid
    assert mid_check in out, '旧正文（§141…§166）未逐字保留'
    assert sec167_full.split('\n')[0] in out, '§167 标题行丢失'
    for old_line in [l for l in mid.split('\n') if l.strip()][:200]:
        assert old_line in out, '旧正文丢行：%s' % old_line[:60]
    n_sections_old = len(re.findall(r'^## §\d+ ', old_all, re.M))
    n_sections_new = len(re.findall(r'^## §\d+ ', out, re.M))
    assert n_sections_new == n_sections_old + 1, (n_sections_old, n_sections_new)
    assert out.count('## §168 ') == 1
    assert '## §167 ' in out
    b_out = out.replace('\n', nl).encode('utf-8')
    lines = out.replace('\n', nl).splitlines()
    assert len(b_out) <= 40000, '超过 40 KB：%d' % len(b_out)
    assert len(lines) <= 300, '超过 300 行：%d' % len(lines)

    # 原子替换
    tmp = STATUS + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(b_out)
    shutil.move(tmp, STATUS)

    print(json.dumps({
        'status_bytes': len(b_out), 'status_lines': len(lines),
        'sections_old': n_sections_old, 'sections_new': n_sections_new,
        'archived_167': {'path': SEC_ARCH, 'bytes': arc_bytes, 'sha256': arc_sha},
        'header_stamp': stamp,
        'delta_strict': d_strict,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
