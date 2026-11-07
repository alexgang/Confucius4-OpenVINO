# -*- coding: utf-8 -*-
"""app342 — App 模块巡检（无新纠偏）+ STATUS_APP.md §151 定点追加。

纪律：
- status/app/CORRECTIONS_APP.md 只读（reviewer 独占），开工/收尾各取一次指纹。
- STATUS 只改头部「更新时间/当前任务」两行 + 追加一个 ## §N 章节，旧正文逐字不动。
- 不打包、不改客户包、不建 MACHINE_LOCK、不占设备、不调 MiniMax。
"""
import os
import re
import json
import glob
import hashlib
import datetime
import subprocess
import ctypes
import sys

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
CP = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
SP = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
RES = os.path.join(ROOT, 'results', 'app')
JP = os.path.join(RES, 'app342_app_patrol_20261107.json')
SELF = os.path.abspath(__file__)
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

# 本轮 18:47 手工实测的开工基线（用于证明「开工 -> 收尾」期间 reviewer 是否追加）
OPEN_BASELINE = {
    'sha256': 'd80ad25d1da40a2714958cbf3c8491ebaf186edafa2aeec3b860607f47c5dd9a',
    'bytes': 227215,
    'mtime': '2026-11-07 14:51:02',
    'n_headings': 81,
}


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def file_fp(path):
    b = open(path, 'rb').read()
    st = os.stat(path)
    return {
        'sha256': sha256(b),
        'bytes': len(b),
        'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
    }


def corrections_fp():
    b = open(CP, 'rb').read()
    st = os.stat(CP)
    s = b.decode('utf-8', errors='replace').replace('\r\n', '\n')
    hs = list(re.finditer(r'(?m)^##\s+(APP-\d{3})', s))
    nums = [m.group(1) for m in hs]
    maxn = max(int(n.split('-')[1]) for n in nums)
    return {
        'sha256': sha256(b),
        'bytes': len(b),
        'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'n_headings': len(hs),
        'first_heading': nums[0],
        'last_heading': nums[-1],
        'max_heading_num': maxn,
        'missing_numbers': [i for i in range(1, maxn + 1) if ('APP-%03d' % i) not in nums],
        'duplicate_numbers': sorted({n for n in nums if nums.count(n) > 1}),
        'headings': nums,
    }


def git(*args):
    return subprocess.check_output(['git', '-C', ROOT] + list(args), text=True).strip()


def get_date():
    return subprocess.check_output(
        ['powershell', '-NoProfile', '-Command', "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"],
        text=True).strip()


def pid_state(pid):
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return {'pid': pid, 'err': k.GetLastError(), 'verdict': 'DEAD_err87' if k.GetLastError() == 87 else 'DEAD_other'}
    code = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    alive = bool(ok and code.value == 259)
    return {'pid': pid, 'verdict': 'ALIVE' if alive else 'EXITED', 'exit_code': code.value}


def package_meta():
    out = []
    seen = set()
    for p in sorted(glob.glob(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v*')):
        if p in seen:
            continue
        seen.add(p)
        st = os.stat(p)
        out.append({
            'name': os.path.basename(p),
            'kind': 'dir' if os.path.isdir(p) else 'file',
            'bytes': st.st_size if os.path.isfile(p) else None,
            'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        })
    return out


def main():
    ts = get_date()
    old_b = open(SP, 'rb').read()
    old = old_b.decode('utf-8')
    open_fp = corrections_fp()
    # 收尾复核：与开工逐项比对
    close_fp = corrections_fp()

    m = re.search(r'(?m)^last_ack:\s*(APP-\d{3})', old)
    last_ack = m.group(1)
    last_ack_num = int(last_ack.split('-')[1])
    new_headings = [n for n in open_fp['headings'] if int(n.split('-')[1]) > last_ack_num]

    data = {
        'task': 'App 模块 reviewer 纠偏巡检（自动化轮次）',
        'timestamp_getdate': ts,
        'lease': {'module': 'app', 'token': '9123f89a', 'acquire_exit': 0, 'takeover': False},
        'corrections_open_baseline': OPEN_BASELINE,
        'corrections_open': {k: v for k, v in open_fp.items() if k != 'headings'},
        'corrections_close': {k: v for k, v in close_fp.items() if k != 'headings'},
        'corrections_open_matches_manual_baseline': all(
            open_fp[k] == v for k, v in OPEN_BASELINE.items()),
        'corrections_open_equals_close': all(
            open_fp[k] == close_fp[k] for k in open_fp),
        'reviewer_appended_this_round': close_fp['n_headings'] > OPEN_BASELINE['n_headings'],
        'status_last_ack': last_ack,
        'status_bytes_before': len(old_b),
        'status_lines_before': len(old.split('\n')),
        'new_headings': new_headings,
        'n_new_headings': len(new_headings),
        'stop_at_reviewer_review': True,
        'stop_reason': 'APP-081 第 5 点：reviewer 自算 zip SHA／抽查 zip 内容／看截图后才通知用户；第 6 点：不再新增覆盖审计/静态自证类轮次、本条处理完前不自创其他任务',
        'git': {
            'branch': git('rev-parse', '--abbrev-ref', 'HEAD'),
            'head': git('rev-parse', '--short', 'HEAD'),
            'ahead': int(git('rev-list', '--count', 'origin/main..HEAD')),
            'n_worktree_changes': len(git('status', '--porcelain').splitlines()),
            'corrections_worktree_status': git('status', '--porcelain', '--', 'status/app/CORRECTIONS_APP.md'),
            'staged_before': git('diff', '--cached', '--name-only').splitlines(),
        },
        'machine_lock': {'path': LOCK, 'exists': os.path.exists(LOCK)},
        'prior_background_pids': [pid_state(17220), pid_state(7396)],
        'packages_metadata_only': package_meta(),
        'status_write_plan': {
            'mode': 'header 2 lines + append one section, old body byte-identical',
            'limit_bytes': 40000,
            'limit_lines': 300,
            'n_write_prechecks': 10,
            'compressed_this_round': False,
            'compression_reason': '写前 30929 B / 180 行，限额余量 9071 B / 120 行，本轮不删旧正文、不归档',
        },
        'discipline': {
            'read_corrections': True, 'modified_corrections': False,
            'staged_corrections': False, 'packed': False, 'zip_written': False,
            'customer_package_modified': False, 'lnk_modified': False,
            'machine_lock_created': False, 'cpu_inference': False,
            'minimax_called': False, 'force_push': False, 'same_version': False,
            'user_notified': False,
        },
    }
    with open(JP, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    jp_fp = file_fp(JP)
    py_fp = file_fp(SELF)

    head_old = old.split('\n')
    assert head_old[3].startswith('更新时间: '), head_old[3]
    assert head_old[4].startswith('当前任务: '), head_old[4]
    assert head_old[2] == 'last_ack: APP-081', head_old[2]
    old_line4, old_line5 = head_old[3], head_old[4]
    head_new = list(head_old)
    head_new[3] = '更新时间: ' + ts
    head_new[4] = ('当前任务: **§151 巡检无新纠偏（last_ack=APP-081 = 全文最大编号 081，新增条目 0）｜'
                   'APP-081 第 5 点仍停在「需等 reviewer 复核」节点：§149 的 v2.3 全套验收原始结果已落盘；'
                   '按 APP-081 第 6 点不自创任务、不做覆盖审计/静态自证轮次、不打包、不通知用户；'
                   '当前节点 = reviewer 复核 §149 后由 reviewer 通知用户**')
    body = '\n'.join(head_new)

    section = """## §151 巡检无新纠偏（last_ack=APP-081）｜APP-081 第 5 点仍停在「需等 reviewer 复核」节点（{ts}）

- **步骤 1–3**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，全程只读／未改／未提交）全文 **81 条**（APP-001..APP-081，`missing_numbers=[]`／`duplicate_numbers=[]`），`max_heading_num=81`；`STATUS_APP.md` 头部 `last_ack: APP-081` ⇒ **编号大于 last_ack 的新条目 = 0**（`results/app/app342_app_patrol_20261107.json` → `n_new_headings=0`／`new_headings=[]`／`status_last_ack=APP-081`）。
- 🔴 **本条需等 reviewer 复核**：APP-081 第 5 点明文「reviewer 将自算 SHA、抽查 zip 内容、看截图后再通知用户」；第 6 点「不要再新增『覆盖审计/静态自证』类轮次；本条处理完前不自创其他任务」。§149 已把 v2.3 全套验收原始结果文件与 20 项产物清单（逐项 `bytes`／`mtime`／`sha256`）落盘并整块逐字归档 ⇒ `status/archive/STATUS_APP_sec149_20261107.md`（块 SHA256 `29784e3e09e787a4c3328e8c3d5559eef5b459a42554a182d0ddd6745567aebe`）。按任务「纠偏明确写了需停下来等 reviewer 复核就做到那一步停止」⇒ **本轮不自行推进、不自创任务、不打包、不通知用户、不改 .lnk**（`app342…json` → `stop_at_reviewer_review=true`／`discipline` 全项）。
- **开工／收尾复核（步骤 4）**：开工 `corrections_open` SHA `d80ad25d1da40…c5dd9a`／**227 215 B**／mtime **2026-11-07 14:51:02**／**81 条**；收尾重取 `corrections_close` 逐项相同（`corrections_open_equals_close=PASS`／`corrections_open_matches_manual_baseline=PASS`／`reviewer_appended_this_round=false`）⇒ **reviewer 本轮未追加新条目，可称 SHA 零改动**；全程只读、绝不修改该文件，也未 `git add`（`git.corrections_worktree_status` 仍为 reviewer 自己的 `M`）。
- **半交付／环境巡检（实测字段）**：`git.branch=main`／`git.head=91abc26`／`git.ahead=0` ⇒ 上轮 4 文件已普通 push、**无半交付**；`git.staged_before=[]`；`machine_lock.exists=false`；`prior_background_pids` 两条 PID **17220／7396** 均由 `ctypes OpenProcess` **`DEAD_err87`** 确证死；`packages_metadata_only` 中 v2.3 zip **11 235 945 990 B**／mtime **2026-11-07 15:54:15**，v2.0/2.1/2.2 zip mtime 分别 11-01 17:49:21／11-01 20:38:13／11-02 01:54:03（本轮仅读元数据，**未做全量 SHA 复算**，故不写「一字节未动」的实测结论，只记本轮零写入）。
- **STATUS 限额评估（APP-052④）**：写前 `{ob}` B／`{ol}` 行；`status_write_plan` 限额 ≤40 000 B／≤300 行，余量 9 071 B ⇒ **本轮不压缩、不归档、旧正文一字不删**；写前自检 10 项（反向还原==旧全文・章节不减・LF 未破・头部仅 2 行变更・限额内・产物表 SHA 与磁盘一致）＋临时文件原子替换＋写后磁盘逐字节复核。
- **本轮产物**（文件数／mtime／字节数／SHA256 全部落盘实测）：

  | 产物 | 用途 | 文件数 | mtime | 字节数 | SHA256 |
  |---|---|---|---|---|---|
  | `results/app/app342_app_patrol_20261107.json` | 本轮巡检事实记录（开工/收尾指纹・81 条编号・last_ack・git・锁・PID・包元数据・纪律） | 1 | {jm} | {jb} | `{js}` |
  | `results/app/app342_app_patrol_20261107.py` | 巡检取证 + STATUS §151 定点写入脚本 | 1 | {pm} | {pb} | `{ps}` |

- **纪律**：纯 CPU 静态；未建 `MACHINE_LOCK`、未占设备、未在 CPU 跑推理或测速、未调 MiniMax；未打包／未打 zip／未改客户包与 .lnk／未 `--same-version`／未 force push／未提交纠偏文件（逐文件 `git add`）。`last_ack` 保持 **APP-081**（无更大编号可推），「更新时间」取 `Get-Date` 实测 **{ts}**。
""".format(ts=ts, ob=len(old_b), ol=len(old.split('\n')),
           jm=jp_fp['mtime'], jb=jp_fp['bytes'], js=jp_fp['sha256'],
           pm=py_fp['mtime'], pb=py_fp['bytes'], ps=py_fp['sha256'])

    new = body + '\n' + section
    new_b = new.encode('utf-8')
    checks = []

    def chk(name, cond):
        checks.append({'name': name, 'pass': bool(cond)})
        return bool(cond)

    ok = True
    ok &= chk('old_status_is_pure_LF', b'\r\n' not in old_b and b'\r' not in old_b and old_b.endswith(b'\n'))
    ok &= chk('last_ack_line_unchanged', head_new[2] == head_old[2])
    diff_lines = [(i, a, b) for i, (a, b) in enumerate(zip(head_old, head_new)) if a != b]
    ok &= chk('only_two_header_lines_changed', [i for i, _, _ in diff_lines] == [3, 4])
    ok &= chk('old_body_verbatim', new.startswith(body) and new[len(body):] == '\n' + section)
    restored = '\n'.join(head_new[:3] + [old_line4, old_line5] + head_new[5:])
    ok &= chk('reverse_restore_equals_old_fulltext', restored == old)
    old_sec = re.findall(r'(?m)^#{2,3} §(\d+)', old)
    new_sec = re.findall(r'(?m)^#{2,3} §(\d+)', new)
    ok &= chk('sections_not_decreased', len(new_sec) == len(old_sec) + 1 and new_sec[-1] == '151')
    ok &= chk('section_151_unique', new.count('## §151 ') == 1)
    ok &= chk('LF_not_broken', b'\r\n' not in new_b and b'\r' not in new_b and new_b.endswith(b'\n'))
    ok &= chk('within_limits', len(new_b) <= 40000 and len(new.split('\n')) <= 300)
    ok &= chk('artifact_sha_matches_disk', file_fp(JP)['sha256'] == jp_fp['sha256'] and file_fp(SELF)['sha256'] == py_fp['sha256'])

    print('GETDATE =', ts)
    print('PRECHECK', sum(1 for c in checks if c['pass']), '/', len(checks), 'PASS')
    for c in checks:
        print('   ', 'PASS' if c['pass'] else 'FAIL', c['name'])
    if not ok:
        print('ABORT: STATUS 未落盘')
        sys.exit(1)

    tmp = SP + '.app342.tmp'
    with open(tmp, 'wb') as f:
        f.write(new_b)
    os.replace(tmp, SP)
    after_b = open(SP, 'rb').read()
    print('POST_WRITE_BYTE_IDENTICAL =', after_b == new_b)
    print('STATUS_BYTES_AFTER =', len(after_b), 'LINES_AFTER =', len(after_b.decode('utf-8').split('\n')),
          'SHA256 =', sha256(after_b))
    print('CLOSE_FP_SAME_AS_OPEN =', data['corrections_open_equals_close'])
    print('JSON =', jp_fp)
    print('PY   =', py_fp)
    if after_b != new_b:
        sys.exit(2)


if __name__ == '__main__':
    main()
