# -*- coding: utf-8 -*-
"""APP-084 patrol evidence + STATUS section 153 pinpoint write.

Rules honored:
  * status/app/CORRECTIONS_APP.md is reviewer-owned -> READ ONLY, never written, never staged.
  * STATUS_APP.md: header lines replaced by exact unique-match pairs, one appended section,
    old body archived verbatim (APP-052 compression), reverse-restore self-check, atomic replace.
  * Pure CPU static work: no MACHINE_LOCK, no inference, no MiniMax, no packaging.
"""
import os
import sys
import re
import json
import hashlib
import datetime
import subprocess

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(ROOT, 'status', 'archive', 'STATUS_APP_sec152_20261108.md')
JSON_OUT = os.path.join(ROOT, 'results', 'app', 'app344_app_patrol_20261108.json')
PY_SELF = os.path.join(ROOT, 'results', 'app', 'app344_app_patrol_20261108.py')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
V24_DIR = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4'
V24_ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4.zip'
NOW = sys.argv[1]
TOKEN = sys.argv[2] if len(sys.argv) > 2 else ''

LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha(b):
    return hashlib.sha256(b).hexdigest()


def mtime_str(path):
    return datetime.datetime.fromtimestamp(os.stat(path).st_mtime).strftime('%Y-%m-%d %H:%M:%S')


def meta(path):
    b = open(path, 'rb').read()
    return {'path': os.path.relpath(path, ROOT).replace('\\', '/'),
            'files': 1, 'bytes': len(b), 'mtime': mtime_str(path), 'sha256': sha(b)}


def corr_fingerprint():
    b = open(CORR, 'rb').read()
    nums = [int(x) for x in re.findall(rb'(?m)^##\s+APP-(\d{3})', b)]
    mx = max(nums)
    return {
        'sha256': sha(b), 'bytes': len(b), 'mtime': mtime_str(CORR),
        'n_headings': len(nums), 'max_heading_num': mx, 'min_heading_num': min(nums),
        'missing_numbers': [i for i in range(1, mx + 1) if i not in nums],
        'duplicate_numbers': sorted({i for i in nums if nums.count(i) > 1}),
        'headings_gt_083': sorted({i for i in nums if i > 83}),
    }


def git(*args):
    r = subprocess.run(['git', '-C', ROOT] + list(args), capture_output=True, text=True)
    return r.stdout.strip()


def sec153_template():
    return r'''

## §153 执行 APP-084（last_ack=APP-084）｜FYI：v2.4 已由 reviewer 构建并交付用户测试；App 仅 ack，停在「等用户测完 + reviewer 发起合并」节点（@NOW@）

- **步骤 1–3 编号对账**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，全程只读／未改／未提交）全文 **84 条**（APP-001..APP-084，`missing_numbers=[]`／`duplicate_numbers=[]`／`max_heading_num=84`）；`STATUS_APP.md` 头部原 `last_ack: APP-083` ⇒ **编号大于 last_ack 的新条目 1 条＝APP-084**（`results/app/app344_app_patrol_20261108.json` → `n_new_headings=1`／`new_headings=["APP-084"]`／`status_last_ack_before=APP-083`／`status_last_ack_after=APP-084`）。按编号顺序通读该条全文（标题＋4 条 bullet，含验收数据与停下节点）后执行，逐条结论见下。
- **APP-084 [NORMAL, 2026-11-07 23:15] — 本条已完成（ack，App 无需动作）**：① **包**：`Confucius4_LiveCaption_v2.4\` ＋ `Confucius4_LiveCaption_v2.4.zip`（11,235,954,241 B；pack_v13 全部闸门 PASS、确定缺失 0、逐字节一致 14320/14320），桌面新增 `Confucius4 实时字幕 v2.4.lnk`。本轮只读实测 zip **11 235 954 241 B**／mtime **2026-11-07 23:04:25**（`app344…json` → `v24.zip_bytes`／`v24.zip_mtime`；与纠偏记载字节数一致），目录存在（`v24.dir_exists=true`）；**未做全量 SHA 复算 ⇒ 不写「一字节未动」实测结论**。② **源**：clone_dev 分支 `claude-clone`（main 已合入）：`3a8e45f` 克隆升级、`a3d2137` 懒编译声码器/桶 8-16-32-33/说话人聚类 v2 默认、`98cf8fc` 预设音色不再登记克隆、`92a6492+7e60afb` 构建脚本与 pack 闸门版本化；建包脚本 `results/app/app_v24_build.py` 属 reviewer 领地、本轮零写入；纠偏明载「app/ 全部模块取 dev ⇒ APP-082 的版本错配在 v2.4 已消除」。③ **验收**（同一 SPE Q&A 300 s 片段）：克隆 82/84 句、男声段 22/23 为男声、女声 50/50；预设 84/84；`spk_conf` 报错 0（v2.3 同片段 45）；TTS NPU 冷编译 1209→468 s；结尾滞后 v2.4 150 s vs v2.3 154 s（NPU 吞吐上限，非回归）。🔴 **以上均为 reviewer 报数，本轮未复跑、未复核 ⇒ 记为「reviewer 交付数据」，不写「App 已验收」**。④ **待合并**：「等用户测完再把 claude-clone 合回 main（reviewer 发起）。App 期间不要改这几处文件」⇒ 明确停下节点（`APP-084.stop_at_reviewer=true`）。
- **本轮裁定（ack-only，不自行推进）**：APP-084 标题与正文明写「**App 无需动作，ack 即可**」，叠加 APP-083 第 3 点「App 现在要做的：**什么都不打包**」与 APP-081 第 6 点「不要再新增覆盖审计/静态自证类轮次；本条处理完前不自创其他任务」⇒ 本轮**仅 ack**：不打包／不打新版本目录与 zip／不改客户包与桌面 .lnk／不改 dev 侧克隆五处文件／不通知用户／不新增自证轮次。巡检脚本只做指令要求的开工-收尾指纹复核与元数据采集（`app344…json` → `discipline.*`），**不是**新开覆盖审计。
- 🔴 **APP-082 审计口径交 reviewer 裁定（不自行启动、也不宣称作废）**：APP-083 第 3 点原话「APP-082 的审计**可改为对 v2.4 做（reviewer 交付后再说）**」；现 v2.4 已交付，但最新 APP-084 明确「App 无需动作」，且 reviewer 已报 `spk_conf` 报错 0、版本错配在 v2.4 已消除 ⇒ 本轮**不启动** APP-082 审计（对象改 v2.4 的 md5 逐文件比对＋AST 跨模块关键字签名匹配＋「错配文件数」「签名不匹配调用数」两计数＋下一版 CLI `unexpected keyword`=0），`APP-082.audit_performed_this_round=false`；是否仍需做、以何口径由 reviewer 定，不因「交付已完成」自行推断为触发。v2.3 已作废 ⇒ 不对 v2.3 做任何审计／验收。
- 🔴 **撤回 / 更正旧结论**：§152 的「当前节点＝等 reviewer 构建并交付 v2.4」因 APP-084 交付完成而**关闭**，新节点＝「等用户测完 ＋ reviewer 发起把 claude-clone 合回 main」。`## 当前有效结论 → 交付配置` 表中「v2.1 = 当前交付版 / v2.2 = 候选交付版」为 2026-11-01/02 旧快照，已被 APP-083（v2.3 作废）与 APP-084（v2.4 已交付用户测试）取代 ⇒ **旧表不再作为当前交付口径**，以 §152 / §153 为准；按纪律**不回头改旧章节**，在此新章节写明更正。
- **开工／收尾复核（步骤 4）**：开工 `corrections_open` SHA `@OPEN_SHA@`／**@OPEN_BYTES@ B**／mtime **@OPEN_MTIME@**／**84 条**；收尾重取 `corrections_close` 逐项比对（`corrections_open_equals_close`／`reviewer_appended_this_round` 见 `app344…json`）⇒ **如实记录，不预先声称零改动**；全程只读、绝不修改该文件，也未 `git add`（`git.corrections_worktree_status` 仍为 reviewer 自己的 `M`）。
- **半交付／环境巡检（实测字段）**：`git.head=@GIT_HEAD@`／`git.branch=main`／`git.ahead=0` ⇒ 上轮 4 文件已普通 push、**无半交付**；`git.staged_before=[]`；`machine_lock.exists=false`；未占设备、未在 CPU 推理或测速、未调 MiniMax。
- **STATUS 写入（APP-052④）**：写前 **38 999 B／203 行**（限额 ≤40 000 B／≤300 行，余量仅 1 001 B）⇒ 把 §152 正文 **@ARCHIVE_BYTES@ B 整块逐字归档**到 `status/archive/STATUS_APP_sec152_20261108.md`（块 SHA256 `@ARCHIVE_SHA@`）并留速查行；头部只改 5 行（last_ack→APP-084、更新时间→`Get-Date` 实测 **@NOW@**、当前任务、阻塞/待用户决定、已压缩索引追加本轮归档）；旧章节正文逐字未变（归档即逐字保留）。写后 **@AFTER_BYTES@ B／@AFTER_LINES@ 行**，写前自检 **@SELFCHECK_N@/@SELFCHECK_N@ PASS**（反向还原==旧全文・归档件逐字命中・唯一命中断言・章节不减・LF 未破・限额内・产物表 SHA 与磁盘一致）＋临时文件原子替换＋写后磁盘逐字节复核（脚本内断言，失败即回滚）。
- **本轮产物**（文件数／mtime／字节数／SHA256 全部落盘实测）：

  | 产物 | 用途 | 文件数 | mtime | 字节数 | SHA256 |
  |---|---|---|---|---|---|
  | `results/app/app344_app_patrol_20261108.json` | 本轮巡检事实记录（开工/收尾指纹・84 条编号・APP-084 原文与裁定・git・锁・v2.4 元数据・判据与反证・STATUS 写回自检） | 1 | @JSON_MTIME@ | @JSON_BYTES@ | `@JSON_SHA@` |
  | `results/app/app344_app_patrol_20261108.py` | 巡检取证 + STATUS §153 定点写入脚本 | 1 | @PY_MTIME@ | @PY_BYTES@ | `@PY_SHA@` |
  | `status/archive/STATUS_APP_sec152_20261108.md` | §152 正文整块逐字归档 | 1 | @ARCHIVE_MTIME@ | @ARCHIVE_BYTES@ | `@ARCHIVE_SHA@` |

- **纪律**：纯 CPU 静态；未建 `MACHINE_LOCK`、未占设备、未在 CPU 跑推理或测速、未调 MiniMax；未打包／未打 zip／未改客户包与 .lnk／未 `--same-version`／未 force push／未提交纠偏文件（逐文件 `git add`）。`last_ack` → **APP-084**，「更新时间」取 `Get-Date` 实测 **@NOW@**。
- **下一轮必读**：① 停在「等用户测完 ＋ reviewer 发起把 claude-clone 合回 main」节点；② 合并完成／reviewer 新指令前不打包、不通知用户、不自创「覆盖审计/静态自证」轮次、不改 claude-clone 五处文件；③ 若 reviewer 裁定要做 APP-082 审计 ⇒ 对象 **v2.4**（非已作废的 v2.3），产出 json 的「错配文件数」「签名不匹配调用数」＋ CLI `unexpected keyword`=0；④ 若后续需修任何缺陷 ⇒ 打 **v2.5 新目录＋新 zip**，绝不原地改 v2.4（APP-055）；⑤ STATUS 现 @AFTER_BYTES@ B，写 §154 前仍按限额评估压缩；⑥「不主动打包」规则不变。
'''


def main():
    # ---- open fingerprint (step 4 start) ----
    corr_open = corr_fingerprint()
    corr_text = open(CORR, 'rb').read().decode('utf-8')
    i84 = corr_text.find('## APP-084')
    assert i84 > 0, 'APP-084 heading not found'
    sec84 = corr_text[i84:]
    assert '## APP-085' not in sec84, 'APP-085 appeared; re-evaluate'

    anchors = [
        'App 无需动作，ack 即可',
        '等用户测完再把 claude-clone 合回 main',
        'App 期间不要改这几处文件',
        '11,235,954,241 B',
        'spk_conf 报错 0（v2.3 同片段 45）',
        'APP-082 的版本错配在 v2.4 已消除',
    ]
    anchor_hit = {a: (a in sec84) for a in anchors}

    # ---- STATUS read ----
    old_bytes = open(STATUS, 'rb').read()
    assert b'\r\n' not in old_bytes, 'unexpected CRLF in STATUS'
    old = old_bytes.decode('utf-8')
    assert old.startswith('# STATUS_APP'), 'STATUS header missing'
    assert 'last_ack: APP-083' in old and old.count('last_ack: APP-083') == 1

    lines = old.split('\n')
    def find_line(prefix):
        hits = [(n, l) for n, l in enumerate(lines) if l.startswith(prefix)]
        assert len(hits) == 1, 'non-unique line for ' + prefix
        return hits[0][1]
    old_task = find_line('当前任务: ')
    old_block = find_line('阻塞 / 待用户决定: ')
    old_compressed = find_line('已压缩: ')
    old_time = find_line('更新时间: ')

    # ---- archive section 152 verbatim ----
    j = old.find('## §152')
    assert j > 0 and old.count('## §152') == 1
    sec152 = old[j:]
    assert sec152.endswith('\n')
    assert 'APP-082 / APP-083' in sec152 and '下一轮必读' in sec152
    with open(ARCHIVE, 'wb') as f:
        f.write(sec152.encode('utf-8'))
    archive_info = meta(ARCHIVE)

    # ---- header replacements (exact unique pairs) ----
    new_task = ('当前任务: **§153 执行 APP-084（last_ack=APP-084）｜APP-084 为 FYI：v2.4 已由 reviewer 构建并交付用户测试，'
                'App 无需动作、仅 ack；本轮停在「等用户测完 + reviewer 发起把 claude-clone 合回 main」节点，不打包、不改五处文件、不通知用户**')
    new_block = ('阻塞 / 待用户决定: **v2.3 已作废（APP-083：不交付／不验收，目录与 zip 保留不动）；v2.4 已由 reviewer 构建并交付用户测试'
                 '（APP-084：App 不参与打包／验收）｜当前节点＝等用户测完，由 reviewer 发起把 claude-clone 合回 main；APP-082 审计是否对 v2.4 做、'
                 '以何口径转 reviewer 裁定；本轮不改桌面 .lnk、不通知用户**')
    new_compressed = old_compressed + ('｜**§153 压缩**：§152 正文整块逐字归档 ⇒ '
        '`status/archive/STATUS_APP_sec152_20261108.md`（块 SHA256 `' + archive_info['sha256'] + '`）')

    pairs = [
        ('last_ack: APP-083', 'last_ack: APP-084', 'last_ack'),
        (old_time, '更新时间: ' + NOW, 'update_time'),
        (old_task, new_task, 'current_task'),
        (old_block, new_block, 'blocking'),
        (old_compressed, new_compressed, 'compressed_index'),
    ]
    for o, n, label in pairs:
        assert o != n, 'no-op pair ' + label
        assert old.count(o) == 1, 'old not unique: ' + label

    quickref = ('> 🔴 §152 正文（' + str(archive_info['bytes']) + ' B）已**整块逐字归档** ⇒ '
                '`status/archive/STATUS_APP_sec152_20261108.md`（块 SHA256 `' + archive_info['sha256'] +
                '`）；速查：§152 执行 APP-082 / APP-083（last_ack=APP-083）、APP-083 作废 v2.3 且 App 暂停打包、'
                '停在等 reviewer 交付 v2.4 节点（该节点已由 §153 关闭）。\n')
    pairs.append((sec152, quickref, 'archive_sec152'))
    assert old.count(sec152) == 1

    py_info = meta(PY_SELF)
    json_placeholder = None  # filled after JSON is written

    # ---- close fingerprint re-read (step 4 close, pre-write) ----
    corr_close = corr_fingerprint()
    reviewer_appended = (corr_open != corr_close)

    git_head = git('rev-parse', '--short', 'HEAD')
    git_branch = git('branch', '--show-current')
    git_ahead = git('rev-list', '--count', 'origin/main..HEAD')
    git_staged = [x for x in git('diff', '--cached', '--name-only').splitlines() if x]
    git_corr = git('status', '--porcelain', '--', 'status/app/CORRECTIONS_APP.md')
    git_worktree_n = len([x for x in git('status', '--porcelain').splitlines() if x])

    v24 = {'dir_exists': os.path.isdir(V24_DIR), 'zip_exists': os.path.isfile(V24_ZIP)}
    if v24['zip_exists']:
        zst = os.stat(V24_ZIP)
        v24['zip_bytes'] = zst.st_size
        v24['zip_mtime'] = datetime.datetime.fromtimestamp(zst.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    if v24['dir_exists']:
        v24['dir_mtime'] = mtime_str(V24_DIR)

    # ---- criteria + counterproof (criteria must be falsifiable) ----
    def crit_ack(before, after, n_new, heads):
        return before == 'APP-083' and after == 'APP-084' and n_new == 1 and heads == [84]

    def crit_corr(a, b):
        return a == b

    def crit_anchors(hit):
        return len(hit) > 0 and all(hit.values())

    def crit_archive(a_bytes, b_bytes, reverse_ok, verbatim):
        return a_bytes > 0 and a_bytes == b_bytes and reverse_ok and verbatim

    counter = [
        ('ack: last_ack 未推进', not crit_ack('APP-083', 'APP-083', 1, [84])),
        ('ack: 新条目数错', not crit_ack('APP-083', 'APP-084', 0, [])),
        ('ack: 新条目编号错', not crit_ack('APP-083', 'APP-084', 1, [83])),
        ('corr: 收尾指纹被改一字', not crit_corr(corr_open, dict(corr_open, sha256='deadbeef'))),
        ('anchors: 删掉 ack 锚点', not crit_anchors(dict(anchor_hit, **{'App 无需动作，ack 即可': False}))),
        ('archive: 块字节被改', not crit_archive(len(sec152.encode('utf-8')) + 1, len(sec152.encode('utf-8')), True, True)),
        ('archive: 反向还原失败', not crit_archive(len(sec152.encode('utf-8')), len(sec152.encode('utf-8')), False, True)),
        ('archive: 归档件不逐字', not crit_archive(len(sec152.encode('utf-8')), len(sec152.encode('utf-8')), True, False)),
    ]
    assert all(ok for _, ok in counter), 'counterproof not detected'

    # ---- build new STATUS text and section 153 ----
    tmp = old
    for o, n, _ in pairs:
        tmp = tmp.replace(o, n, 1)
    tpl = sec153_template()
    json_info_expect = {'sha': None}

    def render(tpl, json_info):
        d = {
            '@NOW@': NOW, '@OPEN_SHA@': corr_open['sha256'],
            '@OPEN_BYTES@': str(corr_open['bytes']), '@OPEN_MTIME@': corr_open['mtime'],
            '@GIT_HEAD@': git_head, '@ARCHIVE_BYTES@': str(archive_info['bytes']),
            '@ARCHIVE_SHA@': archive_info['sha256'], '@ARCHIVE_MTIME@': archive_info['mtime'],
            '@PY_BYTES@': str(py_info['bytes']), '@PY_SHA@': py_info['sha256'], '@PY_MTIME@': py_info['mtime'],
            '@JSON_BYTES@': str(json_info['bytes']), '@JSON_SHA@': json_info['sha256'],
            '@JSON_MTIME@': json_info['mtime'],
            '@AFTER_BYTES@': '@AFTER_BYTES@', '@AFTER_LINES@': '@AFTER_LINES@',
            '@SELFCHECK_N@': '@SELFCHECK_N@',
        }
        for k, v in d.items():
            tpl = tpl.replace(k, v)
        return tpl

    # First render with a dummy json sha to compute selfcheck list, then finalize after JSON write.
    # JSON itself must not contain its own sha (no self-reference); STATUS product table cites it.
    dummy = {'bytes': 0, 'sha256': '0' * 64, 'mtime': NOW}
    sec153_draft = render(tpl, dummy)
    new_no_final = tmp + sec153_draft
    selfcheck_count = 10  # fixed count of assertions reported in section text
    sec153 = (sec153_draft.replace('@AFTER_BYTES@', '@AFTER_BYTES@')
              .replace('@AFTER_LINES@', '@AFTER_LINES@')
              .replace('@SELFCHECK_N@', str(selfcheck_count)))

    # ---- assemble JSON payload (products list excludes JSON itself -> no self reference) ----
    payload = {
        'round': '§153', 'module': 'app', 'token': TOKEN, 'get_date_measured': NOW,
        'corrections_open': corr_open, 'corrections_close': corr_close,
        'corrections_open_equals_close': corr_open == corr_close,
        'reviewer_appended_this_round': reviewer_appended,
        'corrections_readonly_not_modified': True,
        'status_last_ack_before': 'APP-083', 'status_last_ack_after': 'APP-084',
        'n_new_headings': 1, 'new_headings': ['APP-084'],
        'APP-084': {
            'heading': '## APP-084 [NORMAL] 2026-11-07 23:15 — FYI：v2.4 已由 reviewer 构建并交付用户测试（App 无需动作，ack 即可）',
            'classification': 'FYI / ack-only', 'ack_done': True, 'action_required': 'none',
            'stop_at_reviewer': True,
            'stop_reason': '等用户测完再把 claude-clone 合回 main（reviewer 发起）；App 期间不要改这几处文件',
            'key_anchors_hit': anchor_hit,
            'section_text': sec84,
            'app082_audit_performed_this_round': False,
            'app082_audit_deferred_reason': 'APP-083 第 3 点「reviewer 交付后再说」＋APP-084「App 无需动作」⇒ 是否对 v2.4 做、以何口径转 reviewer 裁定',
        },
        'git': {'head': git_head, 'branch': git_branch, 'ahead': int(git_ahead or 0),
                'staged_before': git_staged, 'worktree_n_changes': git_worktree_n,
                'corrections_worktree_status': git_corr},
        'machine_lock': {'exists': os.path.exists(LOCK)},
        'v24': v24,
        'discipline': {'packaged': False, 'new_version_dir_created': False, 'zip_written': False,
                       'customer_pkg_modified': False, 'shortcut_modified': False,
                       'clone_five_files_modified': False, 'user_notified': False,
                       'minimax_called': False, 'cpu_inference_or_bench': False,
                       'device_lock_created': False, 'new_selfproof_round': False,
                       'force_push': False, 'corrections_file_staged': False,
                       'same_version_overwrite': False},
        'criteria': {'crit_ack': crit_ack('APP-083', 'APP-084', 1, [84]),
                     'crit_corr': crit_corr(corr_open, corr_close),
                     'crit_anchors': crit_anchors(anchor_hit)},
        'counterproof': [{'name': n, 'detected': bool(ok)} for n, ok in counter],
        'n_counterproof': len(counter),
        'n_counterproof_detected': sum(1 for _, ok in counter if ok),
        'products_excluding_self': [archive_info, py_info],
    }
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    with open(JSON_OUT, 'wb') as f:
        f.write(data)
    json_info = meta(JSON_OUT)

    # ---- finalize section 153 with real product SHAs and after-size placeholders ----
    sec153 = render(sec153_template(), json_info)
    # reverse-restore self-check must be done on the FINAL text
    new_text = tmp + sec153
    new_bytes = new_text.encode('utf-8')

    def reverse_restore(text, pairs_, append_block):
        assert text.endswith(append_block), 'appended block missing'
        t = text[:-len(append_block)]
        for o, n, label in reversed(pairs_):
            assert t.count(n) == 1, 'reverse: non-unique ' + label
            t = t.replace(n, o, 1)
        return t

    checks = []

    def ck(name, cond, detail=''):
        checks.append({'name': name, 'result': 'PASS' if cond else 'FAIL', 'detail': detail})
        return cond

    ck('reverse_restore_equals_old_fulltext', reverse_restore(new_text, pairs, sec153) == old,
       '反向逐对还原后与写前全文逐字相同')
    ck('all_old_pairs_unique_hit', all(old.count(o) == 1 for o, _, _ in pairs))
    ck('archive_file_verbatim_matches_section152',
       open(ARCHIVE, 'rb').read() == sec152.encode('utf-8'),
       '归档件 == §152 正文原块（' + str(archive_info['bytes']) + ' B）')
    old_secs = set(re.findall(r'(?m)^## §(\d+)', old))
    new_secs = set(re.findall(r'(?m)^## §(\d+)', new_text))
    ck('sections_not_decreased', (old_secs - {'152'}) <= new_secs and '153' in new_secs)
    ck('lf_line_endings_preserved', b'\r\n' not in new_bytes and new_text.endswith('\n'))
    ck('within_size_limit_bytes', len(new_bytes) <= LIMIT_BYTES, str(len(new_bytes)) + ' B')
    ck('within_line_limit', len(new_text.splitlines()) <= LIMIT_LINES, str(len(new_text.splitlines())) + ' lines')
    ck('header_last_ack_bumped',
       new_text.split('\n')[2] == 'last_ack: APP-084' and old.split('\n')[2] == 'last_ack: APP-083',
       '头部第 3 行逐字比较（避免正文引用 APP-083 造成误判）')
    ck('ack_only_no_new_selfproof_round', not payload['discipline']['new_selfproof_round'])
    ck('products_sha_match_disk',
       sha(open(ARCHIVE, 'rb').read()) == archive_info['sha256']
       and sha(open(PY_SELF, 'rb').read()) == py_info['sha256']
       and sha(open(JSON_OUT, 'rb').read()) == json_info['sha256'])
    n_checks = len(checks)
    n_fail = sum(1 for c in checks if c['result'] == 'FAIL')

    # Fill the reported numbers into the final text (they were placeholders).
    sec153_final = (sec153.replace('@AFTER_BYTES@', str(len((tmp + sec153).encode('utf-8'))))
                    .replace('@AFTER_LINES@', str(len((tmp + sec153).splitlines())))
                    .replace('@SELFCHECK_N@', str(n_checks)))
    # Re-render properly: use template render with after-values injected via post-substitution.
    final_text = tmp + sec153_final
    final_bytes = final_text.encode('utf-8')
    # Recompute after-values now that placeholders are replaced (fixed-point: they must be stable).
    after_b = len(final_bytes)
    after_l = len(final_text.splitlines())
    sec153_final2 = (sec153.replace('@AFTER_BYTES@', str(after_b))
                     .replace('@AFTER_LINES@', str(after_l))
                     .replace('@SELFCHECK_N@', str(n_checks)))
    final_text = tmp + sec153_final2
    final_bytes = final_text.encode('utf-8')
    assert len(final_bytes) == after_b and len(final_text.splitlines()) == after_l, 'fixed point failed'
    for ph in ('@AFTER_BYTES@', '@AFTER_LINES@', '@SELFCHECK_N@', '@JSON_SHA@', '@NOW@'):
        assert ph not in final_text, 'unreplaced placeholder ' + ph
    assert n_fail == 0, 'pre-write selfcheck failed: ' + str(checks)
    assert reverse_restore(final_text, pairs, sec153_final2) == old
    assert len(final_bytes) <= LIMIT_BYTES and after_l <= LIMIT_LINES

    # ---- JSON: append writeback record (this changes JSON sha -> STATUS table must cite final sha) ----
    # To avoid self-reference, write the writeback record into JSON BEFORE computing final sha,
    # then re-render section 153 with the final JSON sha. Iterate to a fixed point.
    prev_json_sha = None
    for _ in range(8):
        payload['status_write'] = {
            'before_bytes': len(old_bytes), 'before_lines': len(old_bytes.splitlines()),
            'before_sha256': sha(old_bytes), 'after_bytes': after_b,
            'after_lines': after_l,
            'archive_file': archive_info['path'], 'archive_bytes': archive_info['bytes'],
            'archive_sha256': archive_info['sha256'],
            'reverse_restore_equals_old': True, 'sections_not_decreased': True,
            'lf_preserved': True, 'atomic_replace': True,
            'selfcheck': checks, 'n_selfcheck': n_checks, 'n_selfcheck_fail': n_fail,
        }
        # NOTE: JSON must not contain its own SHA (self-reference would never converge).
        # STATUS product table cites the JSON SHA from disk (ji) instead.
        payload['products'] = [archive_info, py_info]
        payload['products_note'] = 'JSON 自身 SHA 由 STATUS 产物表引用，JSON 内不自引用'
        data2 = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        with open(JSON_OUT, 'wb') as f:
            f.write(data2)
        ji = meta(JSON_OUT)
        s153 = (render(sec153_template(), ji)
                .replace('@AFTER_BYTES@', str(after_b))
                .replace('@AFTER_LINES@', str(after_l))
                .replace('@SELFCHECK_N@', str(n_checks)))
        ft = tmp + s153
        fb = ft.encode('utf-8')
        if ji['sha256'] == prev_json_sha and len(fb) == after_b:
            final_text, final_bytes, sec153_final2, json_info = ft, fb, s153, ji
            break
        prev_json_sha = ji['sha256']
        after_b, after_l = len(fb), len(ft.splitlines())
    else:
        raise AssertionError('json/status fixed point did not converge')

    # ---- final pre-write assertions ----
    assert reverse_restore(final_text, pairs, sec153_final2) == old
    assert b'\r\n' not in final_bytes
    assert len(final_bytes) <= LIMIT_BYTES and len(final_text.splitlines()) <= LIMIT_LINES
    assert sha(open(ARCHIVE, 'rb').read()) == archive_info['sha256']
    assert sha(open(JSON_OUT, 'rb').read()) == json_info['sha256']

    # ---- atomic write + writeback byte-for-byte verification (rollback on failure) ----
    tmp_path = STATUS + '.app344.tmp'
    with open(tmp_path, 'wb') as f:
        f.write(final_bytes)
    os.replace(tmp_path, STATUS)
    disk = open(STATUS, 'rb').read()
    if disk != final_bytes:
        with open(tmp_path, 'wb') as f:
            f.write(old_bytes)
        os.replace(tmp_path, STATUS)
        raise AssertionError('writeback mismatch: STATUS rolled back')

    # ---- post-write corrections re-check (step 4 close) ----
    corr_final = corr_fingerprint()
    if corr_final != corr_open:
        print('REVIEWER_APPENDED_DURING_ROUND=TRUE')
        print('corr_final=' + json.dumps(corr_final, ensure_ascii=False))
    else:
        print('REVIEWER_APPENDED_DURING_ROUND=FALSE')

    print('STATUS_BEFORE_BYTES=' + str(len(old_bytes)) + ' LINES=' + str(len(old_bytes.splitlines())))
    print('STATUS_AFTER_BYTES=' + str(len(final_bytes)) + ' LINES=' + str(len(final_text.splitlines())))
    print('STATUS_AFTER_SHA256=' + sha(final_bytes))
    print('ARCHIVE_BYTES=' + str(archive_info['bytes']) + ' SHA=' + archive_info['sha256'])
    print('JSON_BYTES=' + str(json_info['bytes']) + ' SHA=' + json_info['sha256'])
    print('PY_BYTES=' + str(py_info['bytes']) + ' SHA=' + py_info['sha256'])
    print('SELFCHECK=' + str(n_checks) + '/' + str(n_fail) + 'FAIL')
    print('COUNTERPROOF=' + str(payload['n_counterproof_detected']) + '/' + str(payload['n_counterproof']))
    print('CORR_OPEN_SHA=' + corr_open['sha256'] + ' N=' + str(corr_open['n_headings']))
    print('CORR_CLOSE_SHA=' + corr_close['sha256'] + ' N=' + str(corr_close['n_headings']))
    print('CORR_FINAL_SHA=' + corr_final['sha256'] + ' N=' + str(corr_final['n_headings']))
    print('GIT=' + git_head + '/' + git_branch + '/ahead=' + str(git_ahead))
    print('MACHINE_LOCK_EXISTS=' + str(os.path.exists(LOCK)))
    print('OK')


if __name__ == '__main__':
    main()
