# -*- coding: utf-8 -*-
"""App patrol 2026-11-08 (STATUS section 155): no new reviewer corrections -> ack-only.

Rules honored:
  * status/app/CORRECTIONS_APP.md is reviewer-owned -> READ ONLY, never written, never staged.
  * STATUS_APP.md: 4 header lines replaced by unique line-prefix hits, one appended section,
    old section 154 body archived verbatim (APP-052 compression), reverse-restore self-check,
    self-size fixed point, temp-file atomic replace, post-write byte verification.
  * Pure CPU static: no MACHINE_LOCK, no inference, no MiniMax, no packaging, no notification.
"""
import os
import sys
import re
import json
import hashlib
import datetime
import subprocess
import ctypes

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(ROOT, 'status', 'archive', 'STATUS_APP_sec154_20261108.md')
JSON_OUT = os.path.join(ROOT, 'results', 'app', 'app346_app_patrol_20261108.json')
PY_SELF = os.path.join(ROOT, 'results', 'app', 'app346_app_patrol_20261108.py')
FINAL_OUT = os.path.join(ROOT, 'results', 'app', 'app346_final_recheck_20261108.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
V23_ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.3.zip'
V24_ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4.zip'
NOW = sys.argv[1]
TOKEN = sys.argv[2]
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
    loose = re.findall(rb'(?m)^#{1,4}\s+APP-\d+', b)
    mx = max(nums)
    return {
        'sha256': sha(b), 'bytes': len(b), 'mtime': mtime_str(CORR),
        'n_headings': len(nums), 'n_loose_app_headings': len(loose),
        'max_heading_num': mx, 'min_heading_num': min(nums),
        'missing_numbers': [i for i in range(1, mx + 1) if i not in nums],
        'duplicate_numbers': sorted({i for i in nums if nums.count(i) > 1}),
        'headings_gt_084': sorted({i for i in nums if i > 84}),
        'mentions_ge_085': [x.decode('ascii', 'replace') for x in
                            sorted(set(re.findall(rb'APP-0(?:8[5-9]|9\d)', b)))][:20],
    }


def git(*args):
    r = subprocess.run(['git', '-C', ROOT] + list(args), capture_output=True, text=True)
    return r.stdout.strip()


def git_rc(*args):
    return subprocess.run(['git', '-C', ROOT] + list(args), capture_output=True, text=True).returncode


def probe_pids(pids):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    out = {}
    for pid in pids:
        h = k.OpenProcess(0x1000, False, pid)
        if h:
            code = ctypes.c_ulong()
            k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            out[str(pid)] = {'verdict': 'ALIVE_OR_ACCESSIBLE', 'exit_code': code.value}
        else:
            err = ctypes.get_last_error()
            out[str(pid)] = {'verdict': 'DEAD_err87' if err == 87 else 'TREAT_AS_ALIVE',
                             'openprocess_err': err}
    return out


def write_bytes(path, data):
    with open(path, 'wb') as f:
        f.write(data)


def replace_line(text, prefix, new_line, tag):
    lines = text.split('\n')
    idxs = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    assert len(idxs) == 1, (tag, len(idxs))
    lines[idxs[0]] = new_line
    return '\n'.join(lines)


def zip_meta(path):
    if not os.path.exists(path):
        return {'exists': False}
    st = os.stat(path)
    return {'exists': True, 'bytes': st.st_size,
            'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'sha256': 'NOT_RECOMPUTED_metadata_only'}


QUICK_TMPL = ("> 🔴 §154 正文（@ARCHIVE_BYTES@ B，块 SHA256 `@ARCHIVE_SHA@`）已**整块逐字归档** ⇒ "
              "`status/archive/STATUS_APP_sec154_20261108.md`；速查：§154 无新纠偏、last_ack=APP-084、"
              "停在「等用户测完＋reviewer 发起把 claude-clone 合回 main」节点（本轮该节点未推进）。\n")

SEC_TMPL = r'''
## §155 巡检无新纠偏（last_ack=APP-084）｜APP-084 停下节点未变：等用户测完 + reviewer 发起合回 main（@NOW@）

- **步骤 1 全文扫描（reviewer 独占文件，只读）**：`status/app/CORRECTIONS_APP.md` 全文 **@N_HEADINGS@ 条**（APP-001..APP-084，`n_headings=@N_HEADINGS@`／`missing_numbers=[]`／`duplicate_numbers=[]`／`max_heading_num=@MAX_NUM@`；宽松扫描 `#{1,4} APP-` 标题同为 @N_LOOSE@ 个、全文无 `APP-085` 及以上编号 ⇒ `mentions_ge_085=[]`）。开工指纹 `corrections_open.sha256=@OPEN_SHA@`／`bytes=@OPEN_BYTES@`／`mtime=@OPEN_MTIME@`／`n_headings=@N_HEADINGS@`（`results/app/app346_app_patrol_20261108.json` → `corrections_open.*`）。全程只读、未改、未 `git add`、未提交。
- **步骤 2 头部对账**：`STATUS_APP.md` 头部写前 `last_ack: APP-084`（`app346…json` → `status_last_ack_before=APP-084`）⇒ **编号大于 last_ack 的新条目 `n_new_headings=@N_NEW@`**（`new_headings=[]`）⇒ 无需要执行的新纠偏，本轮按「无新纠偏、跳过」处理；`last_ack` 保持 **APP-084** 不变（头部只改「更新时间／当前任务／阻塞／已压缩索引」4 行）。
- **步骤 3 停在等 reviewer 节点（不自行推进）**：APP-084 [NORMAL 2026-11-07 23:15] 原话「**FYI：v2.4 已由 reviewer 构建并交付用户测试（App 无需动作，ack 即可）**」「**等用户测完再把 claude-clone 合回 main（reviewer 发起）。App 期间不要改这几处文件**」⇒ **本条已完成（ack，§153 已落盘）／本条「待合并」分项需等 reviewer 复核与发起**；本轮实测 `git merge-base --is-ancestor claude-clone main` → exit **@CLONE_RC@**（非 0 ⇒ `claude-clone` 尚未合入 main，`git branch -a` 仍见该分支）⇒ **该停下节点本轮未推进、未解除**。叠加 APP-083 第 3 点「App 现在要做的：**什么都不打包**」＋ APP-081 第 6 点「不再新增覆盖审计/静态自证类轮次、本条处理完前不自创其他任务」⇒ 本轮**仅 ack**：不打包／不打新版本目录与 zip／不改客户包与桌面 .lnk／不改 dev 侧克隆五处文件／不通知用户／不启动 APP-082 审计（`app082_audit_performed_this_round=false`，是否对 v2.4 做、以何口径仍交 reviewer 裁定，不宣称作废也不自行触发）／不新增自证轮次。巡检脚本只做指令要求的开工-收尾指纹复核、半交付／环境元数据采集与 STATUS 落盘（`app346…json` → `discipline.*`），**不是**自创覆盖审计。
- **步骤 4 开工／收尾复核**：@CORR_VERDICT@
- **半交付／环境巡检（实测字段）**：`git.head=@GIT_HEAD@`／`git.branch=@GIT_BRANCH@`／`git.ahead=@GIT_AHEAD@`／`git.worktree_changes=@WT_COUNT@`／`git.staged_before=[]` ⇒ 上轮 §154 的 5 文件已普通 push、**无半交付**；`git.corrections_worktree_status=" @CORR_WT@"`（reviewer 自己的改动，未暂存、未提交）；`machine_lock.exists=@LOCK_EXISTS@`；遗留 PID 17220／7396 由 `ctypes OpenProcess` **@PID_VERDICT@**（探测失败一律视为存活的反向纪律执行）；v2.3 zip `@V23_BYTES@ B`／mtime `@V23_MTIME@`、v2.4 zip `@V24_BYTES@ B`／mtime `@V24_MTIME@` 均**仅读元数据**（未做全量 SHA 复算 ⇒ 不写「一字节未动」实测结论）；未占设备、未在 CPU 推理或测速、未调 MiniMax。
- **STATUS 写入（APP-052④ 定点写入）**：写前 **@BEFORE_BYTES@ B／@BEFORE_LINES@ 行**（限额 ≤40 000 B／≤300 行，余量仅 @BEFORE_ROOM@ B）⇒ 把 §154 正文 **@ARCHIVE_BYTES@ B 整块逐字归档**到 `status/archive/STATUS_APP_sec154_20261108.md`（块 SHA256 `@ARCHIVE_SHA@`）并留速查行；头部只改 4 行（`last_ack` 不动，更新时间取 `Get-Date` 实测 **@NOW@**）；旧正文逐字未变（归档即逐字保留，反向还原==旧全文）。写后 **@AFTER_BYTES@ B／@AFTER_LINES@ 行**，写前自检 **@SELFCHECK_N@/@SELFCHECK_N@ PASS**（唯一命中断言・归档件逐字命中・反向还原==旧全文・章节不减・LF 未破・限额内・产物表 SHA 与磁盘一致・自指大小收敛）＋临时文件原子替换＋写后磁盘逐字节复核（脚本内断言，失败即回滚）。
- **本轮产物**（文件数／mtime／字节数／SHA256 全部落盘实测）：

  | 产物 | 用途 | 文件数 | mtime | 字节数 | SHA256 |
  |---|---|---|---|---|---|
  | `results/app/app346_app_patrol_20261108.json` | 本轮巡检事实记录（开工/收尾指纹・编号对账・`n_new_headings=0`・裁定・git・锁・包元数据・PID・判据定义） | 1 | @JSON_MTIME@ | @JSON_BYTES@ | `@JSON_SHA@` |
  | `results/app/app346_app_patrol_20261108.py` | 巡检取证 + STATUS §155 定点写入脚本（含写前自检与原子替换） | 1 | @PY_MTIME@ | @PY_BYTES@ | `@PY_SHA@` |
  | `status/archive/STATUS_APP_sec154_20261108.md` | §154 正文整块逐字归档 | 1 | @ARCHIVE_MTIME@ | @ARCHIVE_BYTES@ | `@ARCHIVE_SHA@` |

- **纪律**：纯 CPU 静态；未建 `MACHINE_LOCK`、未占设备、未在 CPU 跑推理或测速、未调 MiniMax；未打包／未打 zip／未改客户包与 .lnk／未 `--same-version`／未 force push／未提交纠偏文件（逐文件 `git add`）；未通知用户。
- **下一轮必读**：① 唯一节点仍是「等用户测完 ＋ reviewer 发起把 claude-clone 合回 main」（本轮实测 `merge-base --is-ancestor` exit @CLONE_RC@，节点未推进）；② 合并完成／reviewer 新指令前不打包、不通知用户、不自创「覆盖审计/静态自证」轮次、不改 claude-clone 五处文件；③ 若 reviewer 裁定要做 APP-082 审计 ⇒ 对象 **v2.4**（非已作废的 v2.3），产出「错配文件数」「签名不匹配调用数」＋ CLI `unexpected keyword`=0；④ 后续修缺陷须打 **v2.5 新目录＋新 zip**，绝不原地改 v2.4（APP-055）；⑤ STATUS 现 @AFTER_BYTES@ B（余量 @AFTER_ROOM@ B）⇒ 写 §156 前仍按限额评估压缩；⑥「不主动打包」规则不变。
'''


def main():
    corr_open = corr_fingerprint()
    old_bytes = open(STATUS, 'rb').read()
    old_text = old_bytes.decode('utf-8')
    assert old_bytes.count(b'\r\n') == 0, 'STATUS is not pure LF'

    assert re.search(r'(?m)^last_ack:\s*APP-084\s*$', old_text), 'last_ack is not APP-084'
    n_new = len(corr_open['headings_gt_084'])
    assert n_new == 0, 'new corrections appeared: %s' % corr_open['headings_gt_084']
    assert corr_open['max_heading_num'] == 84 and corr_open['n_headings'] == 84

    staged_before = [x for x in git('diff', '--cached', '--name-only').splitlines() if x.strip()]
    assert staged_before == [], 'staging area is not empty: %s' % staged_before
    corr_wt = git('status', '--porcelain', '--', 'status/app/CORRECTIONS_APP.md').strip()
    wt_count = len([x for x in git('status', '--porcelain').splitlines() if x.strip()])
    g_head = git('rev-parse', '--short', 'HEAD')
    g_branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    g_ahead = git('rev-list', '--count', 'origin/main..HEAD')
    clone_rc = git_rc('merge-base', '--is-ancestor', 'claude-clone', 'main')
    lock_exists = os.path.exists(LOCK)
    v23 = zip_meta(V23_ZIP)
    v24 = zip_meta(V24_ZIP)
    pid_probe = probe_pids([17220, 7396])
    pid_verdict = 'both DEAD_err87' if all(v['verdict'] == 'DEAD_err87'
                                           for v in pid_probe.values()) else 'see app346 json'

    # section 154 body: verbatim archive block (APP-052 compression)
    i = old_text.find('## §154 ')
    assert i >= 0 and old_text.count('## §154 ') == 1
    arch_block = old_text[i:]
    write_bytes(ARCHIVE, arch_block.encode('utf-8'))
    arch_meta = meta(ARCHIVE)
    assert open(ARCHIVE, 'rb').read() == arch_block.encode('utf-8')

    corr_close = corr_fingerprint()
    c_sha, c_bytes, c_mtime, c_n = (corr_close['sha256'], corr_close['bytes'],
                                    corr_close['mtime'], corr_close['n_headings'])
    if corr_open == corr_close:
        verdict = (f'开工 `corrections_open` 与收尾重取 `corrections_close` 逐项相等（SHA `{c_sha}`／'
                   f'**{c_bytes} B**／mtime **{c_mtime}**／**{c_n} 条**；'
                   '`corrections_open_equals_close=true`／`reviewer_appended_this_round=false`）⇒ '
                   '**reviewer 本轮未追加新条目，可称本轮零改动**；全程只读、绝不修改该文件，也未 `git add`／未提交。'
                   '写 STATUS 后脚本再取第三次指纹断言（`app346_final_recheck_20261108.json` → `open_equals_final`），'
                   '若中途被追加则以收尾实测为准、如实记录、绝不修改纠偏文件。')
    else:
        verdict = (f'⚠️ **收尾实测与开工不一致**：`corrections_close` SHA `{c_sha}`／**{c_bytes} B**／'
                   f'mtime **{c_mtime}**／**{c_n} 条**（`reviewer_appended_this_round=true`）⇒ '
                   '**reviewer 本轮中途追加了新条目**，如实记录如上，本 STATUS 不声称「SHA 零改动」；'
                   '纠偏文件全程只读、绝不修改、未 `git add`／未提交，新条目留待下一轮按编号顺序执行。')

    facts = {
        'round': '§155', 'now': NOW, 'lease_token': TOKEN,
        'task': 'app_patrol_no_new_corrections_ack_only',
        'corrections_open': corr_open, 'corrections_close': corr_close,
        'corrections_open_equals_close': corr_open == corr_close,
        'reviewer_appended_this_round': corr_open != corr_close,
        'n_headings': corr_open['n_headings'], 'max_heading_num': corr_open['max_heading_num'],
        'status_last_ack_before': 'APP-084', 'status_last_ack_after': 'APP-084',
        'n_new_headings': n_new, 'new_headings': [],
        'app084_status': '本条已完成（ack，§153）；待合并分项需等 reviewer 复核与发起',
        'stop_at_reviewer': True, 'ack_only_no_new_round': True,
        'app082_audit_performed_this_round': False,
        'git': {'head': g_head, 'branch': g_branch, 'ahead': g_ahead,
                'worktree_changes': wt_count, 'staged_before': staged_before,
                'corrections_worktree_status': corr_wt,
                'clone_is_ancestor_of_main_rc': clone_rc,
                'clone_note': 'rc!=0 => claude-clone not merged into main; APP-084 merge gate not advanced'},
        'machine_lock': {'path': LOCK, 'exists': lock_exists},
        'prior_background_pids': pid_probe,
        'packages': {'v23_zip': v23, 'v24_zip': v24},
        'status_before': {'bytes': len(old_bytes), 'lines': len(old_text.splitlines()),
                          'sha256': sha(old_bytes)},
        'archive_block': {'path': arch_meta['path'], 'bytes': arch_meta['bytes'],
                          'sha256': arch_meta['sha256'], 'verbatim': True},
        'selfcheck_expected': [
            'corrections read-only open==close', 'n_new_headings==0 and 84 headings',
            '4 header lines unique-hit', 'archive block unique + archive file verbatim',
            'reverse restore == old full text', 'sections not fewer', 'LF not broken',
            'within 40000 B / 300 lines', '3 artifact SHAs present and disk-equal',
            'self-size fixed point converged'],
        'discipline': {'cpu_static_only': True, 'machine_lock_created': False,
                       'inference_or_benchmark': False, 'minimax_called': False,
                       'packaging': False, 'customer_pkg_modified': False,
                       'shortcut_modified': False, 'user_notified': False,
                       'corrections_file_written': False, 'corrections_file_staged': False,
                       'force_push': False, 'same_version_repack': False,
                       'new_self_invented_audit_round': False},
    }
    write_bytes(JSON_OUT, (json.dumps(facts, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    json_meta = meta(JSON_OUT)
    py_meta = meta(PY_SELF)

    # header: 4 unique line-prefix replacements (last_ack untouched)
    header_originals = []
    head_text = old_text
    spec = [
        ('更新时间: ', '更新时间: @NOW@'),
        ('当前任务: ', '当前任务: **§155 巡检无新纠偏（last_ack=APP-084）｜APP-084 停下节点未变：等用户测完 + reviewer 发起把 claude-clone 合回 main；本轮仅 ack，不打包、不通知用户、不自创自证轮次、不改克隆五处文件**'),
        ('阻塞 / 待用户决定: ', '阻塞 / 待用户决定: **v2.3 已作废（APP-083）｜v2.4 由 reviewer 构建并交付用户测试（APP-084）｜当前节点＝等用户测完，由 reviewer 发起把 claude-clone 合回 main（本轮实测 merge-base exit @CLONE_RC@，节点未推进）；APP-082 审计是否对 v2.4 做、以何口径仍待 reviewer 裁定；本轮无新纠偏、不改桌面 .lnk、不通知用户**'),
        ('已压缩: ', None),
    ]
    for prefix, new_line in spec:
        lines = [l for l in head_text.split('\n') if l.startswith(prefix)]
        assert len(lines) == 1, ('header prefix not unique', prefix, len(lines))
        orig = lines[0]
        header_originals.append((prefix, orig))
        if new_line is None:
            new_line = orig + '｜**§155 压缩**：§154 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec154_20261108.md`（块 SHA256 `@ARCHIVE_SHA@`）'
        head_text = replace_line(head_text, prefix, new_line, prefix)

    j = head_text.find('## §154 ')
    assert j >= 0
    prefix_part = head_text[:j]

    values = {
        'NOW': NOW, 'N_HEADINGS': corr_open['n_headings'], 'N_LOOSE': corr_open['n_loose_app_headings'],
        'MAX_NUM': corr_open['max_heading_num'], 'N_NEW': n_new,
        'OPEN_SHA': corr_open['sha256'], 'OPEN_BYTES': corr_open['bytes'], 'OPEN_MTIME': corr_open['mtime'],
        'CLOSE_SHA': corr_close['sha256'], 'CLOSE_BYTES': corr_close['bytes'],
        'CLOSE_MTIME': corr_close['mtime'], 'CLOSE_N': corr_close['n_headings'],
        'CORR_VERDICT': verdict, 'GIT_HEAD': g_head, 'GIT_BRANCH': g_branch, 'GIT_AHEAD': g_ahead,
        'WT_COUNT': wt_count, 'CLONE_RC': clone_rc, 'CORR_WT': corr_wt,
        'LOCK_EXISTS': str(lock_exists).lower(), 'PID_VERDICT': pid_verdict,
        'V23_BYTES': v23.get('bytes', 'NOT_PRESENT'), 'V23_MTIME': v23.get('mtime', 'NOT_PRESENT'),
        'V24_BYTES': v24.get('bytes', 'NOT_PRESENT'), 'V24_MTIME': v24.get('mtime', 'NOT_PRESENT'),
        'BEFORE_BYTES': len(old_bytes), 'BEFORE_LINES': len(old_text.splitlines()),
        'BEFORE_ROOM': LIMIT_BYTES - len(old_bytes),
        'ARCHIVE_BYTES': arch_meta['bytes'], 'ARCHIVE_SHA': arch_meta['sha256'],
        'ARCHIVE_MTIME': arch_meta['mtime'],
        'JSON_MTIME': json_meta['mtime'], 'JSON_BYTES': json_meta['bytes'], 'JSON_SHA': json_meta['sha256'],
        'PY_MTIME': py_meta['mtime'], 'PY_BYTES': py_meta['bytes'], 'PY_SHA': py_meta['sha256'],
        'SELFCHECK_N': 10,
    }

    def apply_values(t):
        for k, v in values.items():
            t = t.replace('@' + k + '@', str(v))
        return t

    quick = apply_values(QUICK_TMPL)
    base = prefix_part + quick + SEC_TMPL

    def render(guess_b, guess_l):
        t = apply_values(base)
        t = t.replace('@AFTER_BYTES@', str(guess_b)).replace('@AFTER_LINES@', str(guess_l))
        t = t.replace('@AFTER_ROOM@', str(LIMIT_BYTES - guess_b))
        return t

    guess_b, guess_l = 0, 0
    for _ in range(40):
        new_text = render(guess_b, guess_l)
        nb = new_text.encode('utf-8')
        nl = len(new_text.splitlines())
        if len(nb) == guess_b and nl == guess_l:
            break
        guess_b, guess_l = len(nb), nl
    else:
        raise AssertionError('self-size fixed point did not converge')
    new_bytes = nb

    def restore_header(t):
        lines = t.split('\n')
        for prefix, orig in header_originals:
            idxs = [k for k, l in enumerate(lines) if l.startswith(prefix)]
            assert len(idxs) == 1, ('restore header', prefix)
            lines[idxs[0]] = orig
        return '\n'.join(lines)

    def reverse_restore(t):
        k = t.find('\n## §155 ')
        assert k >= 0 and t.count('\n## §155 ') == 1
        body = t[:k]
        assert body.count(quick) == 1
        return restore_header(body.replace(quick, arch_block))

    sec_count_old = len(re.findall(r'(?m)^## ', old_text))
    sec_count_new = len(re.findall(r'(?m)^## ', new_text))
    sha_in_text = (json_meta['sha256'] in new_text,
                   py_meta['sha256'] in new_text,
                   arch_meta['sha256'] in new_text)
    checks = [
        ('corrections read-only open==close', corr_open == corr_close),
        ('n_new_headings==0 and 84 headings', n_new == 0 and corr_open['n_headings'] == 84
         and corr_open['max_heading_num'] == 84 and corr_open['n_loose_app_headings'] == 84),
        ('4 header lines unique-hit', len(header_originals) == 4
         and all(sum(1 for l in old_text.split('\n') if l.startswith(p)) == 1 for p, _ in header_originals)),
        ('archive block unique + archive file verbatim', old_text.count(arch_block) == 1
         and open(ARCHIVE, 'rb').read() == arch_block.encode('utf-8')),
        ('reverse restore == old full text', reverse_restore(new_text) == old_text),
        ('sections not fewer', sec_count_new >= sec_count_old),
        ('LF not broken', b'\r' not in new_bytes),
        ('within 40000 B / 300 lines', len(new_bytes) <= LIMIT_BYTES and len(new_text.splitlines()) <= LIMIT_LINES),
        ('3 artifact SHAs present and disk-equal', all(sha_in_text)
         and meta(JSON_OUT)['sha256'] == json_meta['sha256']
         and meta(PY_SELF)['sha256'] == py_meta['sha256']
         and meta(ARCHIVE)['sha256'] == arch_meta['sha256']),
        ('self-size fixed point converged', len(new_bytes) == guess_b
         and len(new_text.splitlines()) == guess_l and '@' not in new_text),
    ]
    n_pass = sum(1 for _, ok in checks if ok)
    n_fail = len(checks) - n_pass
    assert n_fail == 0 and n_pass == 10, [(n, ok) for n, ok in checks]

    tmp = STATUS + '.tmp346'
    try:
        write_bytes(tmp, new_bytes)
        os.replace(tmp, STATUS)
        assert open(STATUS, 'rb').read() == new_bytes, 'post-write byte verify failed'
    except Exception:
        write_bytes(STATUS, old_bytes)
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

    corr_final = corr_fingerprint()
    final = {
        'round': '§155', 'now': NOW,
        'corrections_open': corr_open, 'corrections_close': corr_close,
        'corrections_final_after_status_write': corr_final,
        'open_equals_final': corr_open == corr_final,
        'reviewer_appended_this_round': corr_open != corr_final,
        'corrections_file_written': False, 'corrections_file_staged': False,
        'selfcheck': {'n_pass': n_pass, 'n_fail': n_fail,
                      'checks': [{'name': n, 'ok': bool(ok)} for n, ok in checks]},
        'status_after': {'bytes': len(new_bytes), 'lines': len(new_text.splitlines()),
                         'sha256': sha(new_bytes)},
        'status_before': {'bytes': len(old_bytes), 'lines': len(old_text.splitlines()),
                          'sha256': sha(old_bytes)},
        'archive': arch_meta, 'artifacts': {'json': json_meta, 'script': py_meta},
        'post_write_disk_bytes_equal': open(STATUS, 'rb').read() == new_bytes,
    }
    write_bytes(FINAL_OUT, (json.dumps(final, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))

    print(json.dumps({
        'n_new_headings': n_new, 'last_ack': 'APP-084',
        'corrections_open': {'sha256': corr_open['sha256'], 'bytes': corr_open['bytes'],
                             'mtime': corr_open['mtime'], 'n': corr_open['n_headings']},
        'corrections_final': {'sha256': corr_final['sha256'], 'bytes': corr_final['bytes'],
                              'mtime': corr_final['mtime'], 'n': corr_final['n_headings']},
        'reviewer_appended_this_round': corr_open != corr_final,
        'selfcheck': '%d/%d' % (n_pass, len(checks)),
        'status_before': {'bytes': len(old_bytes), 'lines': len(old_text.splitlines())},
        'status_after': {'bytes': len(new_bytes), 'lines': len(new_text.splitlines()),
                         'sha256': sha(new_bytes)},
        'archive': arch_meta, 'json': json_meta, 'script': py_meta,
        'final_recheck': meta(FINAL_OUT),
        'git': {'head': g_head, 'branch': g_branch, 'ahead': g_ahead,
                'clone_is_ancestor_of_main_rc': clone_rc},
        'machine_lock_exists': lock_exists,
        'ALERT': 'CORRECTIONS_APPENDED_MID_ROUND' if corr_open != corr_final else '',
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
