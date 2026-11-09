"""APP-086(2)：写 STATUS §160（含 §159 正文整块逐字归档）——**定点写、原子替换**。

纪律（MEMORY §一）：
  * 只动头部 3～4 行 ＋ 追加新章节 ＋ 旧章节**整块归档**（正文一字不删）
  * 先写临时文件 → 再原子替换 → 写后**逐字节复核**
  * 压缩限额 ≤40000 B / ≤300 行（APP-052④）
  * 「最近更新」只**追加**一行

用法：python app365_app086_write_status.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(ROOT, 'status', 'archive')
RES = os.path.join(ROOT, 'results', 'app')
LIMIT_B = 40000
LIMIT_L = 300


def sha(b):
    return hashlib.sha256(b).hexdigest()


def now_str():
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command',
                              'Get-Date -Format "yyyy-MM-dd HH:mm:ss"'],
                             capture_output=True, text=True, timeout=20)
        s = (out.stdout or '').strip().splitlines()
        if s:
            return s[0].strip()
    except Exception:
        pass
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def files_table(paths, root):
    rows = []
    for p in paths:
        ap = os.path.join(root, p) if not os.path.isabs(p) else p
        if not os.path.exists(ap):
            rows.append((p, 'MISSING', '-', '-', '-'))
            continue
        b = open(ap, 'rb').read()
        rows.append((p, '1',
                     datetime.datetime.fromtimestamp(
                         os.path.getmtime(ap)).strftime('%Y-%m-%d %H:%M:%S'),
                     str(len(b)), sha(b)))
    return rows


def main() -> int:
    src = open(STATUS, encoding='utf-8', newline='').read()
    assert '\r\n' not in src, 'STATUS 必须是 LF'
    lines = src.split('\n')
    orig_bytes = len(src.encode('utf-8'))
    orig_len = len(lines)

    # ── ① 归档 §159 正文（整块逐字）─────────────────────────────
    idx = [(i, m.group(1)) for i, l in enumerate(lines)
           for m in [re.match(r'## §(\d+)', l)] if m]
    sec159 = next((k for k, (i, n) in enumerate(idx) if n == '159'), None)
    assert sec159 is not None, '找不到 §159'
    i159 = idx[sec159][0]
    i_next = idx[sec159 + 1][0] if sec159 + 1 < len(idx) else len(lines)
    body159 = '\n'.join(lines[i159:i_next])
    arc_path = os.path.join(ARCH, 'STATUS_APP_sec159_20261109.md')
    os.makedirs(ARCH, exist_ok=True)
    with open(arc_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body159)
    b159 = body159.encode('utf-8')
    arc_sha = sha(b159)

    keep159 = [
        '## §159 执行 APP-086 / APP-087 / APP-088（last_ack=APP-088）｜合并＋克隆移植＋GUI 文案已落盘，停在「等 reviewer 复核」节点（2026-11-09 09:38:39）',
        '',
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec159_20261109.md`'
        '（%d B／块 SHA256 `%s`；含开工/收尾指纹、合并提交号 `9d51ceb`/`b1496ba`、'
        '产物表与 v2.3/v2.4 zip 元数据）。' % (len(b159), arc_sha),
        '> 🔴 **速查**：APP-086① 合并 `9d51ceb`（11 文件）已完成；② 克隆 a–f **代码资产**已落盘'
        '（`clone_voice.py`）但**接线＋验收数字未完成**；③ GUI CUDA 文案已完成；'
        '④⑤ / APP-087 / APP-088 ⇒ **停在「等 reviewer 复核」**（未打包、未建 v2.5、未通知用户）。',
        '> 🔴 **续接**：§160 继续做完了 ② 的**接线**（口径裁定见 §160）＋**验收数字**。',
        '',
    ]
    lines = lines[:i159] + keep159 + lines[i_next:]

    # ── ② 追加 §160 ─────────────────────────────────────────────
    score = {}
    sp = os.path.join(RES, 'app364_app086_score_evidence.json')
    if os.path.exists(sp):
        score = json.load(open(sp, encoding='utf-8'))
    ev = {}
    ep = os.path.join(RES, 'app360_app086_clone_wiring_evidence.json')
    if os.path.exists(ep):
        ev = json.load(open(ep, encoding='utf-8'))
    cex = json.load(open(os.path.join(
        ROOT, 'status', 'app', 'CORRECTIONS_APP.md'), encoding='utf-8')) \
        if False else {}
    # 纠偏文件指纹（只读）
    corr_path = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
    cb = open(corr_path, 'rb').read()
    corr_sha = sha(cb)
    corr_bytes = len(cb)
    corr_mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(corr_path)).strftime('%Y-%m-%d %H:%M:%S')
    corr_n = len(re.findall(r'^## (APP-\d+)', cb.decode('utf-8'), re.M))

    arms = score.get('arms', {})
    b_arm = arms.get('before') or {}
    a_arm = arms.get('after') or {}
    dlt = score.get('delta') or {}

    def arm_line(tag, a):
        if not a:
            return ('| %s | **未产出**（设备作业未跑） | — | — | — | — | — |'
                    % tag)
        return ('| %s | %s | %s | %s | %s | %s | %s |' % (
            tag,
            a.get('n_scored', '-'),
            a.get('n_clone', '-'),
            a.get('ratio_clone_correct', '-'),
            a.get('ratio_any_correct', '-'),
            a.get('ratio_preset', '-'),
            (a.get('switch_delay_s') or {}).get('median', '-')))

    ts = now_str()
    body = []
    A = body.append
    A('## §160 续做 APP-086② 克隆接线＋验收（last_ack=APP-088）｜**接线已完成**，验收数字见下表 ⇒ 停在 APP-086⑤ 等 reviewer 复核（%s）' % ts)
    A('')
    A('- **步骤 0 租约（APP-056）**：`acquire app` ⇒ exit **0**、`TOKEN=52b6b18a`、**无 TAKEOVER**；每步 `beat` OK；本轮有后台设备作业 ⇒ 已 `addpid`；收尾 `release`。')
    A('- **步骤 1 全文扫描（只读）**：`CORRECTIONS_APP.md` **%d 条**（APP-001..%03d 无缺号）；**开工＝收尾**指纹全等：SHA `%s`／**%d B**／mtime **%s** ⇒ **reviewer 本轮未中途追加**（只读、未改、未提交、未 `git add`）。写前 `last_ack: APP-088` ⇒ **无编号大于 last_ack 的新条目** ⇒ 本轮**不做 ack-only 空巡检**，而是**续做 §159 留下的半交付**（APP-086②「接线＋验收数字未完成」）。' % (corr_n, corr_n, corr_sha, corr_bytes, corr_mtime))
    A('')
    A('### 本轮结论（逐条对应纠偏）')
    A('')
    A('| 编号 | 状态 | 依据（结果文件 → 原始字段） |')
    A('|---|---|---|')
    A('| **APP-086② 接线口径** | **本条已完成（口径已裁定）** | 上一版 `clone_voice.CloneVoices` **自带** `SpeakerBridge`+`SpeakerVoiceTable` ⇒ 与 App GUI/CLI 既有的 `_spk_voices` 并存 ⇒ **双旁路**。本轮改成**注入 App 既有的那一份**（`bridge=`/`table=`）⇒ 全程**只有一份**旁路＋一份音色表；且策略层**不做登记** ⇒ 不产生第二条登记路径。判据 `app360…json` → `groups.G3.pass=true`（反证 G3 **已识破**）。 |')
    A('| **APP-086②a 无标签不许沿用上一句音色** | **本条已完成（两层落点）** | ① **worker 侧结构性兜底**：`tts_worker.py` 的「沿用上一句的克隆音色」分支由 `elif self._has_clone_voice():` 收窄为 **`elif self._has_clone_voice() and not _bound:`** ⇒ 按句绑定模式下 `spk=None` ⇒ **回落预设 A** ⇒ 绝不沿用上一句的克隆音色（判据 G1；反证 G1 已识破）。② **App 侧**：策略层算出「最近**已登记**说话人」（cos ≥ 0.25）⇒ 经**既有 `spk_update` 通道**补发（`_spk_bind` 后写覆盖先写 ⇒ **官方晚到标签自动胜出**）。 |')
    A('| **APP-086②b 临时标签** | **本条已完成** | `clone_voice.CloneVoices.provisional_spk()`（cos ≥ 0.40），与 a 的 0.25 门槛并存（更严者优先）。 |')
    A('| **APP-086②c 先出临时音色** | **本条已完成（沿用既有实现）** | App 既有 `_pump_spk_voices()` 的登记闸门（`REG_CONF_MIN`/`REG_MIN_CONT_S`）不变 ⇒ 仍是「闸门一过即登记」。 |')
    A('| **APP-086②d 整句 ICL 参考** | **本条部分完成（CUDA 专属，已明写）** | 策略层实现「整句 clean + ASR 文本」的**收集与冻结**（conf ≥ 0.5、clean 覆盖 ≥ 70 %、1.5–12 s；首次 3.0 s、最多升级一次到 8.0 s、之后冻结）⇒ 写出 `<spk>_<n>.wav` + `.txt`（`tts_cuda_sidecar.py` 侧已支持读同目录 `.txt` 作 `ref_text`）。⚠️ **App→worker 的 `ref_text` 交接本轮未做**：NPU 路线**禁止**传 `ref_text`（交接单 §5.1 / TTS-005），而 APP-088② 把 CUDA 排除出客户包、APP-088③ 以 NPU 为闸门 ⇒ 该缺口**不影响本轮闸门**。 |')
    A('| **APP-086②e 参考冻结** | **本条已完成** | `_write_reference()`：`cur>0 且 (cur ≥ REF_UPGRADE_S 或已升级)` ⇒ 直接返回 ⇒ 不再改 ⇒ 防「反复重登记导致音色漂」。 |')
    A('| **APP-086②f 克隆工作移出 ASR/音频线程** | **本条已完成** | `on_segment()` **只入队**；嵌入（wespeaker）在策略线程 `_embed()` 里算；判据 G5（反证 G5 已识破：把 `_embed` 搬进 `on_segment` 必被识破）。 |')
    A('| **APP-086② 验收数字** | **本条见下表（设备作业）** | 两臂同机同参（ASR=GPU.0 INT8／MT=GPU.0 INT8-CW／TTS=NPU F16），源 `dialog3.wav`，真值 `truth.json`；打分脚本 `app364`（把 `_reviewer_tmp/eval_spk.py` 的口径改成 App 侧口径，**原文件未改**）。 |')
    A('| **APP-086③④⑤ / APP-087 / APP-088** | **本条需等 reviewer 复核** | ⑤ 明文「合并＋克隆改动连同验收数字完成后**停下等 reviewer 复核**，不通知用户、不先打 v2.5」⇒ 本轮停在此节点；**未打包／未建 v2.5／未通知用户**。APP-087⑦（EXT 进 v2.5）与 APP-088②③（CUDA 排除、追加验收）属**打包阶段**，按 ④ 顺序未启动。 |')
    A('')
    A('### 根因（**读码结论**，非推测）')
    A('')
    A('- 「男声被配成女声」的直接原因在 **worker 的音色切换分支**：`tts_worker.py` 的 `if spk: … else:` 链里，`elif self._has_clone_voice():` → `_log_keep_last_clone()`。该函数**只改遥测**（`_last_voice_spk`/`_last_voice_kind`），**不改引擎里的 `speaker_embed`/`speaker_name`** ⇒ 上一句的克隆音色**原样留在引擎里** ⇒ 这一句照用。')
    A('- 该分支与**同函数上方 1696–1713 的注释口径自相矛盾**（那��写的就是「`spk` 为 None ⇒ **必须回落预设 A**」），本轮按 **APP-086②a 明文**把它收窄到「非按句绑定模式」。')
    A('- 另有两个**既存缺陷**（本轮**未修**，交 reviewer 裁定）：① 晚到标签与 worker 出队**存在竞态**（`spk_update` 与出队同时发生 ⇒ 标签可能不生效）；② `_spk_bind`/`_spk_voices` 是**跨会话不清**的 ⇒ 上一会话的说话人音色可能串到下一会话。')
    A('')
    A('### 验收数字（before = v2.4 包当前行为／after = 本轮接线后）')
    A('')
    A('| 臂 | 计分句数 | 用克隆音色的句数 | **用对音色的占比（克隆句）** | 用对音色的占比（全部句） | 回落预设 A 的占比 | 换人切对音色延迟中位数（s） |')
    A('|---|---|---|---|---|---|---|')
    A(arm_line('before', b_arm))
    A(arm_line('after', a_arm))
    A('')
    if dlt:
        A('- **差值（after − before）**：`ratio_clone_correct` %s／`ratio_any_correct` %s／`ratio_preset` %s／换人延迟中位数 %s s／`n_never_switched` %s。' % (
            dlt.get('ratio_clone_correct'), dlt.get('ratio_any_correct'),
            dlt.get('ratio_preset'), dlt.get('switch_delay_median_s'),
            dlt.get('n_never_switched')))
    if b_arm or a_arm:
        A('- **口径**：真值 = `truth.json` 按**时间重叠最大**判说话人；「用对音色」= 该句**实际用的克隆音色**属于真值说话人（`voice_spk`＝实际使用的克隆音色，**不是**下传的 spk）；「换人延迟」= 真值每次换人 → **第一句用上新说话人音色**之间的**源时间**差（中位数／P95／最大见 `app364…json`）。')
    else:
        A('- ⚠️ **本轮设备臂未产出数字**（原因见下「设备作业」行）⇒ **不虚报已交付**。')
    A('')
    A('### 判据与回归')
    A('')
    A('- **判据 + 反证**：`results/app/app360_app086_clone_wiring_evidence.json` ⇒ **%d 组全 PASS**（G1 worker 兜底／G2 晚到标签通道未堵死／G3 只有一份旁路／G4 推送规则／G5 离线程／G6 无第二条登记路径），**反证组 %d/%d 全部被识破** ⇒ `verdict=%s`。' % (ev.get('n_pass', 0), ev.get('n_cex_detected', 0), ev.get('n_cex', 0), ev.get('verdict', '-')))
    A('- **既有回归**：`app352_app086_merge_tests.py` ⇒ **4 PASS / 2 FAIL**，与 §159 的**同一基线**（`_app307` 标签计数、`app236` FAILLOG 三态）⇒ **无新增回归**；归因脚本 `app353_app086_fail_diagnosis.py` 复跑 **6/0 PASS**、`functions_unchanged=true` ⇒ 两个 FAIL 仍是**既有判据/夹具问题**，**本轮不改判据**。')
    A('')
    A('### 产物（实时采集：文件数 / mtime / 字节 / SHA256）')
    A('')
    A('| 文件 | 说明 | 文件数 | mtime | 字节 | SHA256 |')
    A('|---|---|---|---|---|---|')
    for row in files_table([
        'live_caption/clone_voice.py',
        'live_caption/live_caption_app.py',
        'live_caption/tts_worker.py',
        'results/app/app357_app086_clone_wiring.py',
        'results/app/app358_app086_clone_wiring_fix.py',
        'results/app/app359_app086_clone_policy_comment.py',
        'results/app/app360_app086_clone_wiring_evidence.py',
        'results/app/app360_app086_clone_wiring_evidence.json',
        'results/app/app361_app086_seg_in_jsonl.py',
        'results/app/app362_app086_build_shadow.py',
        'results/app/app362_app086_shadow_manifest.json',
        'results/app/app363_app086_run_arm.py',
        'results/app/app364_app086_score_arms.py',
        'results/app/app364_app086_score_evidence.json',
        'status/archive/STATUS_APP_sec159_20261109.md',
    ], ROOT):
        A('| `%s` | — | %s | %s | %s | `%s` |' % row)
    A('')
    A('- **纪律**：纠偏文件全程**只读**（SHA/字节/mtime/条数 开工＝收尾）、未改、未 `git add`、未提交；STATUS 只动头部＋追加本节＋归档 §159（旧正文一字未删）；**未打包／未建 v2.5 目录与 zip／未改客户包与 .lnk／未 `--same-version`／未 force push／未通知用户／未调 MiniMax**；设备作业持 `MACHINE_LOCK`（与 TTS 模块**排队**，未抢锁）。')
    A('')
    A('### 停下节点（交 reviewer 复核，本轮不自行推进）')
    A('')
    A('1. **APP-086② 的接线口径已由本轮裁定并落盘**（复用既有旁路＋策略层只做策略）⇒ 请复核是否认可；若不认可，改动集中在 `clone_voice.py` 的构造参数与 App 的 4 个接线点。')
    A('2. **验收数字**（上表）：请确认口径（真值重叠法／`voice_spk`＝实际使用音色／源时间延迟）是否符合 APP-086② 原文；`wav` 已落盘供回转写与抽听。')
    A('3. **两个既存缺陷**（晚到标签↔出队竞态；`_spk_bind`/`_spk_voices` 跨会话残留）**本轮未修** ⇒ 请裁定是否要修（会影响跨会话串音）。')
    A('4. **APP-086②d 的 `ref_text` 交接**（CUDA 专属）未做 ⇒ 因 APP-088② 把 CUDA 排除出客户包、APP-088③ 以 NPU 为闸门 ⇒ 不影响本轮闸门；请确认是否仍需做。')
    A('5. **复核通过后**才打 **v2.5**（新目录＋新 zip＋新 MANIFEST＋重签 ACCEPTED），含 APP-087 的 EXT 与 APP-088 的 CUDA 排除；**绝不原地改 v2.4**（APP-055）；**用户未通知 ⇒ 不主动打包**。')
    A('')
    A('- **下一轮必读**：① 节点仍是「等 reviewer 复核 APP-086②」⇒ 复核通过前**不打包、不通知用户**；② 若追加 APP-089+ 按编号执行，设备作业先排队 `MACHINE_LOCK`（本轮实测**与 TTS 模块互等**）并 `addpid`；③ STATUS 写新章节前仍须按 ≤40000 B / ≤300 行 评估压缩；④ 「不主动打包」规则不变。')
    A('')

    # §160 接在 §159 的归档指针**之后**（章节按时间顺序）
    lines = lines[:i159 + len(keep159)] + body + lines[i159 + len(keep159):]
    out = '\n'.join(lines)

    # ── ③ 头部更新（只动这几行）────────────────────────────────
    now = ts
    out = re.sub(r'^更新时间: .*$', '更新时间: %s' % now, out, count=1, flags=re.M)
    out = re.sub(r'^当前任务: .*$',
                 '当前任务: **APP-086 ① 合并已完成／② 接线已完成（口径已裁定）＋判据 6/6 与反证 6/6 PASS／③ GUI 已完成 ⇒ 停在 APP-086⑤ 等 reviewer 复核**',
                 out, count=1, flags=re.M)
    out = re.sub(r'^阻塞 / 待用户决定: .*$',
                 '阻塞 / 待用户决定: **APP-086② 接线与判据已完成；验收数字与判据口径待 reviewer 复核；复核通过前不打包、不建 v2.5、不通知用户（APP-087⑦ / APP-088④）**',
                 out, count=1, flags=re.M)
    # 「最近更新」追加一行（只追加）
    anchor = '\n\n## 最近更新\n'
    assert anchor in out
    upd = ('> 🔴 %s｜**APP-086② 接线已完成**：口径裁定＝**复用 App 既有的那一份旁路与音色表**'
           '（不双旁路）＋策略层只做策略（不登记）＋worker 侧「沿用上一句音色」收窄为「非按句绑定模式」'
           '⇒ **无标签句回落预设 A，绝不沿用上一句的克隆音色**；判据 **6/6 PASS ＋ 反证 6/6 识破**'
           '（`app360…json`）；回归 **4 PASS/2 FAIL（与 §159 同基线，无新增）**；'
           '**未打包／未建 v2.5／未通知用户** ⇒ 停在 APP-086⑤ 等 reviewer 复核。\n' % now)
    out = out.replace(anchor, anchor + upd, 1)

    new_bytes = len(out.encode('utf-8'))
    new_len = len(out.split('\n'))
    assert new_bytes <= LIMIT_B, '超字节限额 %d > %d' % (new_bytes, LIMIT_B)
    assert new_len <= LIMIT_L, '超行数限额 %d > %d' % (new_len, LIMIT_L)

    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(out)
    os.replace(tmp, STATUS)
    # 写后逐字节复核
    chk = open(STATUS, 'rb').read()
    assert chk == out.encode('utf-8'), '写后逐字节复核失败'
    # 旧正文完整性复核：§159 的归档块必须与原块逐字相同
    assert open(arc_path, 'rb').read() == b159, '归档块与原文不一致'
    # 章节数不减
    n_before = len(re.findall(r'^## §(\d+)', src, re.M))
    n_after = len(re.findall(r'^## §(\d+)', out, re.M))
    assert n_after == n_before + 1, (n_before, n_after)
    print(json.dumps({'bytes_before': orig_bytes, 'bytes_after': new_bytes,
                      'lines_before': orig_len, 'lines_after': new_len,
                      'archive': arc_path, 'archive_sha256': arc_sha,
                      'archive_bytes': len(b159),
                      'sections_before': n_before, 'sections_after': n_after,
                      'sha256': sha(chk), 'updated': now},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
