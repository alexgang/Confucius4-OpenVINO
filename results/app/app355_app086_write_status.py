# -*- coding: utf-8 -*-
"""app355_app086_write_status.py — 追加 STATUS_APP.md §159（APP-086/087/088）。

纪律：只改头部 3 行 + 末尾追加一个 `## §N` 章节；旧正文一字不删。
写前自检：唯一命中断言 / 反向还原==旧全文 / 章节数不减 / LF 未破 /
          限额内 / 产物表 SHA 与磁盘一致。原子替换 + 写后逐字节复核。
产物表由脚本实时采集（文件数 / mtime / 字节 / SHA256），不手写数字。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
EVID = os.path.join(REPO, 'results', 'app', 'app355_app086_write_status_evidence.json')
STAMP = '2026-11-09 09:38:39'  # Get-Date 实测
LIMIT_BYTES, LIMIT_LINES = 40000, 300

ARTIFACTS = [
    ('results/app/app351_app086_ack_status.py', 'ACK + APP-052④ 压缩写入脚本（自检 24/0）'),
    ('results/app/app351_app086_ack_evidence.json', 'ACK 写前自检/归档指纹原始字段'),
    ('status/archive/STATUS_APP_sec158_20261109.md', '§158 正文整块逐字归档'),
    ('status/archive/STATUS_APP_sec150_20261109.md', '§150 正文整块逐字归档'),
    ('results/app/app352_app086_merge_tests.py', '合并后回归运行器（ast + 6 闸门 + 前后 SHA 快照）'),
    ('results/app/app352_app086_merge_test_evidence.json', '回归原始字段（rc/wall/stdout_tail）'),
    ('results/app/app352_rerun/', '本轮重跑输出另存目录（5 文件，既有证据已恢复）'),
    ('results/app/app353_app086_fail_diagnosis.py', '两处 FAIL 归因脚本（反证基线=当前被测对象）'),
    ('results/app/app353_app086_fail_diagnosis.json', 'FAIL 归因原始字段（6/0 PASS）'),
    ('results/app/app354_app086_clone_port.py', 'EXT→App 定点移植脚本（a–f 8 组反证）'),
    ('results/app/app354_app086_clone_port_evidence.json', '移植原始字段（33/0、8/8、包零写入）'),
    ('live_caption/clone_voice.py', 'APP-086② a–f 克隆编排层（新增）'),
    ('live_caption/tts_cuda_sidecar.py', 'APP-086②(d) ICL 参考 + 0.6/20 采样（定点改 26 行）'),
    ('live_caption/live_caption_app.py', 'APP-086③ CUDA 选项文案（定点改 3 行）'),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def collect():
    rows = []
    for rel, desc in ARTIFACTS:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if os.path.isdir(p):
            files = [os.path.join(dp, fn) for dp, _d, fs in os.walk(p) for fn in fs]
            n = len(files)
            size = sum(os.path.getsize(x) for x in files)
            h = sha(b''.join(open(x, 'rb').read() for x in sorted(files)))
            mt = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S')
        elif os.path.isfile(p):
            b = open(p, 'rb').read()
            n, size, h = 1, len(b), sha(b)
            mt = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            n, size, h, mt = 0, 0, 'MISSING', '-'
        rows.append(dict(path=rel, desc=desc, n=n, mtime=mt, bytes=size, sha256=h))
    return rows


def main():
    old = open(STATUS, 'rb').read()
    assert b'\r\n' not in old, 'STATUS CRLF abort'
    old_txt = old.decode('utf-8')
    lines = old_txt.split('\n')
    checks = []

    def ck(name, ok, detail=''):
        checks.append(dict(name=name, ok=bool(ok), detail=str(detail)[:240]))
        assert ok, 'CHECK FAILED: %s %s' % (name, detail)

    rows = collect()
    ck('all_artifacts_present', all(r['sha256'] != 'MISSING' for r in rows),
       '%d/%d' % (sum(r['sha256'] != 'MISSING' for r in rows), len(rows)))

    # 头部 3 行（last_ack 已是 APP-088，不动）
    ck('header_last_ack_still_088', lines[2] == 'last_ack: APP-085' or lines[2] == 'last_ack: APP-088',
       lines[2])
    ck('header_update_line', lines[3].startswith('更新时间: '), lines[3])
    head_old = lines[3:6][:]
    head_new = [
        '更新时间: ' + STAMP,
        '当前任务: **APP-086 ① 合并已完成／② 代码资产已落盘（接线＋验收数字未完成）／③ GUI 已完成 ⇒ 停在 APP-086⑤ 等 reviewer 复核**',
        '阻塞 / 待用户决定: **APP-086 验收数字与主循环接线待设备会话；复核通过前不打包、不建 v2.5、不通知用户（APP-087⑦ / APP-088④）**',
    ]

    table = '\n'.join(
        '| `%s` | %s | %d | %s | %d | `%s` |' %
        (r['path'], r['desc'], r['n'], r['mtime'], r['bytes'], r['sha256'])
        for r in rows)

    body = '''## §159 执行 APP-086 / APP-087 / APP-088（last_ack=APP-088）｜合并＋克隆移植＋GUI 文案已落盘，停在「等 reviewer 复核」节点（%s）

- **步骤 0 租约（APP-056）**：`acquire app` ⇒ exit **0**、`TOKEN=8bd109ab`、**无 TAKEOVER**；每步 `beat` OK；本轮无长作业故未 `addpid`；收尾 `release`。纯 CPU 静态 ⇒ `MACHINE_LOCK` 全程 **NOT_PRESENT**（实测 `exists=false`），未占设备／未在 CPU 推理或测速／未调 MiniMax。
- **步骤 1 全文扫描（只读）**：`CORRECTIONS_APP.md` **88 条**（APP-001..088 无缺号），开工＝收尾＝写后三次指纹全等：SHA `d66746ed00be0cc1bb24bcc05ef74428ebbaccba1487c2d6cd07a2b02ded6c1f`／**242 619 B**／mtime **2026-11-09 09:11:06** ⇒ **reviewer 本轮未中途追加**（只读、未改、未提交）。写前 `last_ack: APP-085` ⇒ **3 条新条目 APP-086 / 087 / 088**（均 [HIGH] 用户决定）。
- **ACK（APP-088 明文要求）**：`last_ack` APP-085→**APP-088** ＋「最近更新」追加 **1 行**（`app351` 24/0 PASS）；STATUS 39 996 B→**30 017 B** ⇒ 按 APP-052④ 把 §158（5 694 B）／§150（6 255 B）正文**整块逐字归档**，反向还原==旧全文、章节数 9→9 不减、LF 未破、写后磁盘逐字节复核。

### 三条纠偏逐条状态（本条已完成 / 本条需等 reviewer 复核）

| 编号 | 状态 | 依据（结果文件 → 原始字段） |
|---|---|---|
| **APP-086① 合并** | **本分项已完成** | `git log -1` = `9d51ceb APP-086(1): merge claude-clone (7e60afb) v2.4 build into main`；`git merge-base --is-ancestor claude-clone main` rc **0**；`git show --stat` **11 文件 / +1 405 行**／`ort` 无冲突。clone_dev 3 个未提交改动已看清（`app170_version_identity_gate_evidence.json`、`app_v24_build_evidence.json` 为 v2.3→v2.4 证据刷新，`DELIVERY_2.4.json` 为新增交付记录）⇒ 属 reviewer 工作区未提交资产，**未纳入合并、未改 clone_dev、交 reviewer 处理**。 |
| **APP-086① 测试** | **本分项已完成** | `app352_app086_merge_test_evidence.json`：8 个合并 .py `ast` **8/8 PASS**；6 个既有纯 CPU 闸门 **4 PASS / 2 FAIL**；两处 FAIL 由 `app353_app086_fail_diagnosis.json`（**6/0 PASS**）证明为**既有判据/夹具问题、非合并回归**：`app307` 真实 `scan()` 返回 9 项违规但 label 为 `FALLBACK: <正则>`，判据按 `'voice' in label` 计数 ⇒ 命中 **0**（`assert_pkg_clean.py` 在 `92bdbae..9d51ceb` **逐字节未变**）；`app236` 静态 9 PASS + 反证 9 PASS，`verdict=FAIL` 来自 FAILLOG 夹具 hits `{"engine_not_ready":0,"registered":1}`（成功日志≠失败日志 ⇒ 三态应为 UNKNOWN），6 个被检查函数源码合并前后逐字相同。**本轮不改判据，口径交 reviewer 裁定。** 5 个被测试脚本重写的既有证据已**另存** `results/app/app352_rerun/` 并恢复，未覆盖仓库原证据。 |
| **APP-086② 克隆 a–f** | **代码资产已完成；接线与验收数字未完成** | `app354_app086_clone_port_evidence.json`：**33 PASS / 0 FAIL**、**8/8 组判据含反证**（逐项破坏锚点 ⇒ 判据必须 FAIL）。新增 `live_caption/clone_voice.py`（15 691 B）完整实现 a 无标签不沿用上一句音色（`min_sim=0.25`）／b 临时标签（`min_sim=0.4`）／c 先出临时音色（`registration_ticket`）／d 整句 clean（conf≥0.5、cover≥0.7、1.5–12 s）+ ASR 文本走 ICL／e 参考冻结（`REF_FIRST_S=3.0`、`REF_UPGRADE_S=8.0`）／f 克隆全在 `clone-voices` 线程；`tts_cuda_sidecar.py` 生成调用改 `xvec_only=not _ref_text` + `ref_text`，采样 **0.6 / 20**。只读 `live_dub_ext claude-dev`，**未切分支、未改 EXT**；`package_untouched=true`（v2.4 包内 3 文件 SHA 前后全等）。🔴 **未完成**：主循环（GUI/CLI）接线与「带真值多人对话改前/改后 NPU（闸门）+ CUDA（可选）」验收数字、wav 落盘 `shared/app_listen/` —— 属设备作业，须持 `MACHINE_LOCK` 另起后台会话，本轮**不虚报已交付**。 |
| **APP-086③ GUI** | **本分项已完成** | `build_tts_options()` 的 CUDA 选项在 APP-061②/062③ 已存在（dev 树 `disabled`+`why`，包内 `if not _in_customer_package()` ⇒ **整个选项不出现**，满足 APP-088②「隐藏而非置灰」）；本轮定点补 `需要另装 CUDA 环境` 文案（`git diff` **3 行**）；默认仍 NPU（`or 'NPU'` 未改）；GUI 布局重排未启动。`ast.parse` 全过、行尾原样（app CRLF / sidecar LF，`git diff --stat` 3 + 26 行，无行尾噪声）。 |
| **APP-086④ / ⑤** | **本条需等 reviewer 复核** | ④ 本轮**未打包**（符合 APP-087⑦/088④ 顺序）；⑤ 明文「合并＋克隆改动连同验收数字完成后停下等 reviewer 复核，不通知用户、不先打 v2.5」⇒ **本轮停在此节点**，且验收数字未出 ⇒ 复核所需清单见下。 |
| **APP-087** | **本条需等 reviewer 复核** | 已 ack；⑦ 明文「先做完 APP-086 → 停下等复核 → 复核通过后再打 v2.5（新目录＋新 zip，含 `<pkg>\\live_dub_ext\\`）」⇒ v2.5 打包、EXT 来源 `master@7f2a5d6`、25/25 回放、zip 统计、体积增量**全部未启动**。未改 EXT 仓库（只读 `git show`），未发现需报的 EXT bug。 |
| **APP-088** | **本条需等 reviewer 复核** | 已 ack；① 本地开发树保留 CUDA/NV5050 选项**已满足**（默认 NPU）；② v2.5 只含 iGPU/NPU（排除 `tts_cuda_sidecar_ext.py`、CUDA venv、torch、faster-qwen3-tts，包内 GUI 只列 GPU/NPU）与 ③ 追加验收数字属**打包阶段**，按 ④ 顺序未启动。 |

- **撤回旧节点**：APP-083③ / APP-084「等用户测完 v2.4 再合 / App 期间不要改克隆相关文件」由 **APP-086 明文解除** ⇒ §152–§158 的「等 reviewer 发起合并」节点关闭；APP-085 待命期禁空巡检在**有新条目时**不适用，但本轮未建任何 `patrol` 脚本／未做覆盖审计式自证。

### 停下节点：交 reviewer 复核的清单（本轮不自行推进）

1. **APP-086② 接线口径**：`clone_voice.CloneVoices` 自带 `SpeakerBridge` + `SpeakerVoiceTable`，与 App 现有 GUI/CLI 各一份 `_spk_voices` 实例并存 ⇒ 直接替换会双旁路。请裁定「独立编排层替换」还是「把 a–f 行为并回现有表」；本轮只落盘模块，**未改主循环**。
2. **验收数字（APP-086② + APP-088③）**：改前/改后「用对音色的句子占比」「换人后切到正确音色的延迟（秒）」，**以 NPU 为闸门**、CUDA 可选；须持 `MACHINE_LOCK` 后台跑 `dialog3.wav`+`truth.json`，`eval_spk.py` 复制到 `results/app` 再改，wav 落 `shared/app_listen/` 交回转写。
3. **两处既有判据口径**（`app307` label 计数 / `app236` FAILLOG 三态）是否修正，由 reviewer 定。
4. **APP-086 复核通过后**才打 **v2.5**（新目录＋新 zip＋新 MANIFEST＋重签 ACCEPTED），含 APP-087 的 EXT 与 APP-088 的 CUDA 排除；**绝不原地改 v2.4**（APP-055）。用户未通知 ⇒ 不主动打包（用户级长期记忆）。

### 产物（实时采集：文件数 / mtime / 字节 / SHA256）

| 文件 | 说明 | 文件数 | mtime | 字节 | SHA256 |
|---|---|---|---|---|---|
%s

- **纪律**：纠偏文件全程只读、未改、未 `git add`、未提交；STATUS 只改头部 3 行＋追加本节，旧正文一字未删；未打包／未建 v2.5 目录与 zip／未改客户包与 .lnk／未 `--same-version`／未 force push／未通知用户／未调 MiniMax／未在 CPU 推理或测速；`MACHINE_LOCK` 全程 NOT_PRESENT。
- **git**：合并提交 `9d51ceb`（11 文件全 App 侧）；本轮 App 侧文件与 STATUS 在本节落盘后按「逐文件 `git add`」普通提交并 push，commit hash 见 `git log -1`（本节不回填，避免改旧章节）；暂存守卫：无 `CORRECTIONS_APP.md`、无 ASR/MT/TTS 其它模块文件。
- **下一轮必读**：① 节点仍是「等 reviewer 复核 APP-086」＋「接线口径裁定」＋「验收数字设备作业」；复核通过前**不打包、不通知用户**；② 若追加 APP-089+ 按编号执行，设备作业先排队 `MACHINE_LOCK` 并 `addpid`；③ STATUS 写 §160 前仍须按限额评估压缩；④ 「不主动打包」规则不变。
''' % (STAMP, table)

    txt = old_txt
    for o, n in zip(head_old, head_new):
        ck('header_line_unique', txt.count(o + '\n') == 1, o[:36])
        txt = txt.replace(o + '\n', n + '\n', 1)
    txt_pre = txt                      # 追加前的精确文本（用于反向还原）
    if not txt.endswith('\n'):
        txt += '\n'
    txt = txt + '\n' + body
    new_bytes = txt.encode('utf-8')

    ck('lf_intact', b'\r\n' not in new_bytes)
    ck('limit_bytes', len(new_bytes) <= LIMIT_BYTES, '%d<=%d' % (len(new_bytes), LIMIT_BYTES))
    ck('limit_lines', len(txt.split('\n')) <= LIMIT_LINES, len(txt.split('\n')))
    old_h2 = sum(1 for l in lines if l.startswith('## '))
    new_h2 = sum(1 for l in txt.split('\n') if l.startswith('## '))
    ck('h2_not_reduced', new_h2 == old_h2 + 1, '%d->%d' % (old_h2, new_h2))
    ck('section159_single', txt.count('## §159 ') == 1)
    # 反向还原：按追加前字符长度精确裁掉本节，再逐字还原头部 3 行
    rev = txt[:len(txt_pre)]
    for o, n in zip(head_old, head_new):
        rev = rev.replace(n + '\n', o + '\n', 1)
    ck('reverse_restore_equals_old', rev.encode('utf-8') == old,
       'rev=%d old=%d' % (len(rev.encode('utf-8')), len(old)))

    n_pass = sum(1 for c in checks if c['ok'])
    ck('all_checks_pass', n_pass == len(checks), '%d/%d' % (n_pass, len(checks)))

    tmp = STATUS + '.tmp_app355'
    with open(tmp, 'wb') as f:
        f.write(new_bytes)
    os.replace(tmp, STATUS)
    disk = open(STATUS, 'rb').read()
    ck('disk_byte_identical', disk == new_bytes)

    ev = dict(tool='app355_app086_write_status', stamp=STAMP,
              status_before=dict(bytes=len(old), lines=len(lines), sha256=sha(old)),
              status_after=dict(bytes=len(disk), lines=len(disk.decode('utf-8').split('\n')),
                                sha256=sha(disk)),
              artifacts=rows, checks=checks,
              n_pass=sum(1 for c in checks if c['ok']),
              n_fail=sum(1 for c in checks if not c['ok']),
              verdict='PASS' if all(c['ok'] for c in checks) else 'FAIL')
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps(dict(verdict=ev['verdict'], n_pass=ev['n_pass'], n_fail=ev['n_fail'],
                          before=ev['status_before']['bytes'], after=ev['status_after']['bytes'],
                          h2='%d->%d' % (old_h2, new_h2)), ensure_ascii=False))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
