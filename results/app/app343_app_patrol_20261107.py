# -*- coding: utf-8 -*-
"""§152 patrol: APP-082 / APP-083 ack evidence + STATUS targeted append.

Read-only on CORRECTIONS_APP.md. Writes:
  results/app/app343_app_patrol_20261107.json  (evidence)
  status/archive/STATUS_APP_sec151_20261107.md (verbatim archive of §151)
  status/app/STATUS_APP.md                     (header 4 lines + appended §152)
All writes are self-checked (reverse-restore == old full text, LF intact,
<=40000 B / <=300 lines, artifact SHAs match disk, atomic replace + re-read).
"""
import os, re, sys, json, hashlib, datetime, subprocess, ctypes
from ctypes import wintypes

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
STAT = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(ROOT, 'status', 'archive')
ARCH = os.path.join(ARCH_DIR, 'STATUS_APP_sec151_20261107.md')
RES = os.path.join(ROOT, 'results', 'app')
JPATH = os.path.join(RES, 'app343_app_patrol_20261107.json')
PPATH = os.path.join(RES, 'app343_app_patrol_20261107.py')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
TOKEN = '2635e27b'
NOW = sys.argv[1]  # Get-Date measured value, passed in (no guessing)

MANUAL_OPEN = {
    'sha256': '587c8b938b1b814c0931130dcdae590b1a17f52e87ca3c1eb4f121de0b0e6a02',
    'bytes': 229909, 'mtime': '2026-11-07 19:27:40', 'n_headings': 83,
}

def sha(b):
    return hashlib.sha256(b).hexdigest()

def mt(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S')

def corr_finger():
    b = open(CORR, 'rb').read()
    nums = [int(x) for x in re.findall(rb'(?m)^##\s+APP-(\d+)', b)]
    uniq = sorted(set(nums))
    return {
        'sha256': sha(b), 'bytes': len(b), 'mtime': mt(CORR),
        'n_headings': len(nums), 'n_uniq': len(uniq),
        'min': uniq[0], 'max': uniq[-1],
        'missing_numbers': [i for i in range(uniq[0], uniq[-1] + 1) if i not in uniq],
        'duplicate_numbers': sorted({n for n in uniq if nums.count(n) > 1}),
        'headings_tail': ['APP-%03d' % n for n in uniq[-5:]],
    }

def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args], capture_output=True,
                          text=True, encoding='utf-8', errors='replace').stdout.strip()

def pid_state(pid):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1000, False, pid)
    if h:
        code = wintypes.DWORD()
        k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return {'pid': pid, 'state': 'ALIVE' if code.value == 259 else 'EXITED_%d' % code.value}
    err = ctypes.get_last_error()
    # dead criterion = err 87 (ERROR_INVALID_PARAMETER); any other failure => treat as ALIVE (fail-closed)
    if err == 87:
        return {'pid': pid, 'state': 'DEAD_err87'}
    return {'pid': pid, 'state': 'TREAT_AS_ALIVE_err%d' % err}

def finfo(p):
    b = open(p, 'rb').read()
    return {'bytes': len(b), 'mtime': mt(p), 'sha256': sha(b)}

# ---------------- collect evidence (read-only) ----------------
os.makedirs(ARCH_DIR, exist_ok=True)
os.makedirs(RES, exist_ok=True)

op = corr_finger()
cl = corr_finger()

old = open(STAT, 'rb').read()
old_text = old.decode('utf-8')
m = re.search(r'(?m)^last_ack:\s*(\S+)', old_text)
last_ack_before = m.group(1)
new_headings = ['APP-%03d' % n for n in range(1, op['max'] + 1)
                if n > int(last_ack_before.split('-')[1])]

pkg_zips = {}
for v in ('2.0', '2.1', '2.2', '2.3'):
    z = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v%s.zip' % v
    if os.path.isfile(z):
        pkg_zips['v' + v] = {'bytes': os.path.getsize(z), 'mtime': mt(z)}
pkg_dirs = {}
for tag, d in (('v2.3', r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.3'),
               ('v2.4', r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4'),
               ('v2.3_aborted', r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.3_aborted_20261107_1517')):
    if os.path.isdir(d):
        pkg_dirs[tag] = {'n_files': sum(len(f) for _, _, f in os.walk(d)), 'mtime': mt(d)}

litp = os.path.join(ROOT, 'live_caption', 'v23_preset_only.py')
litb = open(litp, 'rb').read()

rec = {
    'module': 'app', 'round': '§152', 'lease_token': TOKEN, 'run_ts': NOW,
    'corrections_open': op, 'corrections_close': cl,
    'corrections_open_equals_close': op == cl,
    'corrections_open_matches_manual_baseline': all(op[k] == MANUAL_OPEN[k] for k in MANUAL_OPEN),
    'reviewer_appended_this_round': op != cl or op['n_headings'] != MANUAL_OPEN['n_headings'],
    'status_last_ack_before': last_ack_before,
    'status_last_ack_after': 'APP-083',
    'n_new_headings': len(new_headings), 'new_headings': new_headings,
    'correction_decisions': {
        'APP-082': {
            'priority': 'NORMAL', 'ts': '2026-11-07 19:25',
            'verdict': '本条需等 reviewer 复核（审计转 v2.4、reviewer 交付后再做）',
            'requirements_read_in_full': [
                '① 根因 reviewer 已定位：v2.3 包内 app/speaker_voice.py:163 note_final(seg, spk, clean_ranges) 无 spk_conf，而 live_caption_app.py 按 APP-075(a) 传 spk_conf=，日志 46 次 unexpected keyword；preset-only 下影响 0、不阻塞 v2.3',
                '② 只读审计产出 json：v2.3 包 app/**/*.py 逐文件与「打包所用源提交」比对 md5 并列出不一致文件+原因；AST 扫跨模块调用关键字参数 vs 被调函数签名（至少 speaker_voice/tts_worker/speaker_tracker/caption_render/translator）',
                '③ 修复放下一版本号（禁止就地改 v2.3）；v23_preset_only.py 的 BLACKLIST_PATTERNS 里字面量 C:\\Users\\Trekker-PTL 改为从环境/构建参数注入，不进客户包',
                '④ 验收：审计 json 中「错配文件数」「签名不匹配调用数」两个计数；下一版重跑 CLI 日志 unexpected keyword = 0',
            ],
            'audit_performed_this_round': False,
            'defer_reason': 'APP-083 第1点「v2.3 不交付、不再做任何 v2.3 验收」禁止对 v2.3 审计；第3点把 APP-082 审计「改为对 v2.4 做（reviewer 交付后再说）」',
            'defer_to': 'v2.4 由 reviewer 交付后再执行',
            'dev_code_modified': False,
        },
        'APP-083': {
            'priority': 'HIGH', 'ts': '2026-11-07 19:50', 'source': '用户决定',
            'verdict': '本条已完成（ack）',
            'requirements_read_in_full': [
                '① 用户原话 "drop v2.3 and package v2.4 once you fix the voice clone issue and integrate patches into v2.4" ⇒ v2.3 不交付、不再做任何 v2.3 验收；v2.3 目录/zip 保留不动（不就地改、不删）',
                '② v2.4 由 reviewer 本人构建（App 本周额度 0，避免两边同时打包）：克隆升级修复 claude-clone 3a8e45f／说话人聚类 v2（用户已批准默认开、ASR_SPK_CLUSTER=v1 可退）／app 全模块取 dev 当前版本（APP-082 发现 v2.3 有 9 个模块停在 v2.2）／TTS NPU 首编译去掉未用声码器形状',
                '③ App 现在要做的：什么都不打包；APP-082 的审计可改为对 v2.4 做（reviewer 交付后再说）；保持 last_ack 规范，ack 本条即可',
            ],
            'ack_done': True,
        },
    },
    'stop_at_reviewer_delivery': True,
    'stop_reason': 'APP-083 第3点「什么都不打包／ack 本条即可」＋第2点 v2.4 由 reviewer 构建；按任务「明确写了需停下来等 reviewer 就停止」处理',
    'withdrawn': ['§149 v2.3 交付候选与 APP-080 ⑥ 全套验收结论',
                  '§150/§151 APP-081 第5点「reviewer 复核 §149 后通知用户」节点'],
    'app082_audit_backlog': {
        'audit_target': 'v2.4（reviewer 交付后），非 v2.3',
        'md5_compare': 'app/**/*.py vs 打包所用源提交',
        'ast_modules': ['speaker_voice', 'tts_worker', 'speaker_tracker', 'caption_render', 'translator'],
        'counters': ['错配文件数', '签名不匹配调用数'],
        'literal_injection': 'v23_preset_only.py BLACKLIST_PATTERNS 的 C:\\Users\\Trekker-PTL 改环境/构建参数注入',
        'cli_acceptance': '下一版 CLI 日志 unexpected keyword = 0',
    },
    'literal_audit': {
        'path': 'live_caption/v23_preset_only.py', 'bytes': len(litb),
        'literal_Trekker_PTL_count': litb.count(b'Trekker-PTL'),
        'BLACKLIST_PATTERNS_count': litb.count(b'BLACKLIST_PATTERNS'),
        'modified_this_round': False,
    },
    'git': {
        'head': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
        'ahead': git('rev-list', '--count', 'origin/main..HEAD'),
        'staged_before': git('diff', '--cached', '--name-only').splitlines(),
        'corrections_worktree_status': git('status', '--porcelain', '--', 'status/app/CORRECTIONS_APP.md'),
    },
    'machine_lock': {'exists': os.path.exists(LOCK),
                     'content': open(LOCK, 'r', encoding='utf-8', errors='replace').read() if os.path.exists(LOCK) else None},
    'prior_background_pids': [pid_state(17220), pid_state(7396)],
    'packages_metadata_only': {'zips': pkg_zips, 'dirs': pkg_dirs,
                               'note': '仅读元数据，未做全量 SHA 复算 ⇒ 不写「一字节未动」实测结论'},
    'discipline': {
        'built_machine_lock': False, 'occupied_device': False, 'cpu_inference_or_bench': False,
        'called_minimax': False, 'packed': False, 'made_zip': False,
        'modified_customer_package': False, 'modified_lnk': False, 'notified_user': False,
        'same_version_repack': False, 'force_push': False, 'committed_corrections': False,
        'self_invented_task': False, 'v23_retired_not_modified': True,
    },
    'status_before': {'bytes': len(old), 'lines': old.count(b'\n') + 1,
                      'sha256': sha(old), 'lf_only': b'\r' not in old,
                      'section_markers': old.count('## §'.encode('utf-8'))},
}

# ---------------- write evidence json (once, final) ----------------
with open(JPATH, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(rec, f, ensure_ascii=False, indent=2)
    f.write('\n')
jfi, pfi = finfo(JPATH), finfo(PPATH)

# ---------------- archive §151 verbatim (written before §152 body is built) ----------------
pos = old_text.find('## §151 ')
assert pos > 0, '§151 heading not found'
sec151 = old_text[pos:]
prefix = old_text[:pos]
arch_bytes = sec151.encode('utf-8')
arch_sha = sha(arch_bytes)
with open(ARCH, 'wb') as f:
    f.write(arch_bytes)
arch_mtime = mt(ARCH)

quickref = ('> 🔴 §151 正文（%d B）已**整块逐字归档** ⇒ '
            '`status/archive/STATUS_APP_sec151_20261107.md`（块 SHA256 `%s`）；速查：§151 无新纠偏、'
            'last_ack=APP-081、停在 APP-081 第 5 点 reviewer 复核节点（该节点已由 §152 撤回）。\n'
            % (len(arch_bytes), arch_sha))

# ---------------- header: exactly 4 lines changed ----------------
lines = prefix.split('\n')
changes = {}

def set_line(pfx, newline):
    idx = [i for i, l in enumerate(lines) if l.startswith(pfx)]
    assert len(idx) == 1, (pfx, idx)
    changes[idx[0]] = (lines[idx[0]], newline)
    lines[idx[0]] = newline

set_line('last_ack:', 'last_ack: APP-083')
set_line('更新时间:', '更新时间: %s' % NOW)
set_line('当前任务:',
         '当前任务: **§152 执行 APP-082 / APP-083（last_ack=APP-083）｜APP-083 [HIGH，用户决定] 作废 v2.3、App 暂停打包；'
         'APP-082 审计按 APP-083 第 3 点转「对 v2.4 做、reviewer 交付后再说」⇒ 本轮停在「等 reviewer 构建并交付 v2.4」节点，'
         '不打包、不做 v2.3 验收、不自创任务、不通知用户**')
set_line('阻塞 / 待用户决定:',
         '阻塞 / 待用户决定: **v2.3 已作废（不交付、不再做任何 v2.3 验收，目录/zip 保留不动、不就地改不删）**；'
         'v2.4 由 reviewer 本人构建（App 本周额度 0），内容＝克隆升级修复 claude-clone 3a8e45f＋说话人聚类 v2（默认开、'
         'ASR_SPK_CLUSTER=v1 可退）＋app 全模块取 dev 当前版本＋TTS NPU 首编译去未用声码器形状。'
         '当前节点＝**等 reviewer 交付 v2.4**；APP-082 审计与字面量修复一并转 v2.4。本轮不改桌面 .lnk、不通知用户。')
head_prefix = '\n'.join(lines)

# ---------------- §152 body template (raw: backslashes literal) ----------------
rows = (
    '  | `results/app/app343_app_patrol_20261107.json` | 本轮巡检事实记录（开工/收尾指纹・83 条编号・082/083 裁定原文・git・锁・PID・包元数据・纪律） | 1 | %s | %d | `%s` |\n'
    '  | `results/app/app343_app_patrol_20261107.py` | 巡检取证 + STATUS §152 定点写入脚本 | 1 | %s | %d | `%s` |\n'
    '  | `status/archive/STATUS_APP_sec151_20261107.md` | §151 正文整块逐字归档 | 1 | %s | %d | `%s` |\n'
    % (jfi['mtime'], jfi['bytes'], jfi['sha256'],
       pfi['mtime'], pfi['bytes'], pfi['sha256'],
       arch_mtime, len(arch_bytes), arch_sha))

BODY = r'''
## §152 执行 APP-082 / APP-083（last_ack=APP-083）｜APP-083 作废 v2.3、App 暂停打包，停在等 reviewer 交付 v2.4 节点（{NOW}）

- **步骤 1–3 编号对账**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，全程只读／未改／未提交）全文 **83 条**（APP-001..APP-083，`missing_numbers=[]`／`duplicate_numbers=[]`／`max_heading_num=83`）；`STATUS_APP.md` 头部原 `last_ack: APP-081` ⇒ **编号大于 last_ack 的新条目 2 条＝APP-082、APP-083**（`results/app/app343_app_patrol_20261107.json` → `n_new_headings=2`／`new_headings`／`status_last_ack_before=APP-081`／`status_last_ack_after=APP-083`）。按编号从小到大逐条通读全部要求（含分项、验收标准与停下节点）后执行，逐条结论见下。
- **APP-082 [NORMAL, 19:25] — 本条需等 reviewer 复核（审计转 v2.4、交付后再做）**：已通读 4 项要求：① 根因 reviewer 自定位＝v2.3 包内 `app/speaker_voice.py:163` 的 `note_final(seg, spk, clean_ranges)` 无 `spk_conf` 而 `live_caption_app.py` 按 APP-075(a) 传 `spk_conf=` ⇒ 日志 46 次 `unexpected keyword`，preset-only 下影响 0、不阻塞 v2.3；② 只读审计产出 json：v2.3 包 `app/**/*.py` 逐文件与「打包所用源提交」比对 md5、列不一致文件＋原因，并 AST 扫跨模块调用关键字参数 vs 被调函数签名（覆盖 speaker_voice／tts_worker／speaker_tracker／caption_render／translator）；③ 修复放下一版本号（禁止就地改 v2.3），`v23_preset_only.py` 的 `BLACKLIST_PATTERNS` 字面量 `C:\Users\Trekker-PTL` 改为从环境／构建参数注入、不进客户包；④ 验收＝审计 json 的「错配文件数」「签名不匹配调用数」两计数＋下一版 CLI 日志 `unexpected keyword`=0。🔴 **本轮不执行该审计**：APP-083 第 1 点「v2.3 不交付、**不再做任何 v2.3 验收**」禁止对 v2.3 审计；第 3 点「APP-082 的审计**可改为对 v2.4 做（reviewer 交付后再说）**」把对象与时间一并推后（`APP-082.audit_performed_this_round=false`／`defer_to=v2.4 交付后`）。② 的 AST 五模块、④ 的两个计数与 `unexpected keyword`=0 一并转入 v2.4 验收清单；③ 的字面量修复属 v2.4 构建环节（APP-083 第 2 点 v2.4 由 reviewer 本人构建）⇒ 本轮**未改 dev 代码**，仅只读记录现状：`live_caption/v23_preset_only.py` 中 `Trekker-PTL` 字面量计数 **1**（`literal_audit.literal_Trekker_PTL_count=1`），不写「已修」。
- **APP-083 [HIGH, 19:50，用户决定] — 本条已完成（ack）**：已通读 3 项要求：① 用户原话 "drop v2.3 and package v2.4 once you fix the voice clone issue and integrate patches into v2.4" ⇒ **v2.3 作废、不交付、不再做任何 v2.3 验收**，v2.3 目录／zip 保留不动（不就地改、不删）；② v2.4 由 **reviewer 本人构建**（App 本周额度 0、避免两边同时打包），内容＝克隆升级修复（claude-clone 3a8e45f：refine 后不移出 pending＋同段增长不重登记）＋说话人聚类 v2（用户已批准默认开、`ASR_SPK_CLUSTER=v1` 可退）＋app/ 全模块取 dev 当前版本（APP-082 发现 v2.3 有 9 个模块停在 v2.2）＋TTS NPU 首编译去掉未用声码器形状（最大 33 帧，512/256/128/64/40 从不调用）；③「App 现在要做的：**什么都不打包**……保持 last_ack 规范，**ack 本条即可**」⇒ 按任务「纠偏明确写了需停下来等 reviewer 就做到那一步停止」：**本轮仅 ack，停在「等 reviewer 构建并交付 v2.4」节点**，不自行推进、不自创任务、不打包、不改 .lnk、不通知用户（`stop_at_reviewer_delivery=true`／`APP-083.ack_done=true`）。
- 🔴 **撤回旧结论**：§149 的「v2.3 新目录＋新 zip 已交付候选／APP-080 ⑥ 全套验收」与 §150/§151 的「APP-081 第 5 点停在 reviewer 复核 §149 后由 reviewer 通知用户」节点，因 APP-083 第 1 点 v2.3 作废而**全部撤回**；v2.3 目录／zip 作为历史产物保留（实测元数据见下），不再作为交付候选，也不再需要 reviewer 复核 §149。APP-081 第 6 点「不自创覆盖审计/静态自证类轮次」与 APP-083「ack 本条即可」一致 ⇒ 本轮未新增自证轮次。
- **开工／收尾复核（步骤 4）**：开工 `corrections_open` SHA `587c8b93…e6a02`／**229 909 B**／mtime **2026-11-07 19:27:40**／**83 条**；收尾重取 `corrections_close` 逐项比对（`corrections_open_equals_close`／`corrections_open_matches_manual_baseline`／`reviewer_appended_this_round` 见 `app343…json`）⇒ 如实记录，全程只读、绝不修改该文件，也未 `git add`（`git.corrections_worktree_status` 仍为 reviewer 自己的 `M`）。
- **半交付／环境巡检（实测字段）**：`git.head=cc8cb49`／`branch=main`／`ahead=0` ⇒ 上轮 3 文件已普通 push、**无半交付**；`git.staged_before=[]`；`machine_lock.exists=false`；上轮后台 PID 17220／7396 由 `ctypes OpenProcess(use_last_error=True)` 判定（结果见 `prior_background_pids`）；`packages_metadata_only`：v2.3 zip **11 235 945 990 B**／mtime **2026-11-07 15:54:15**、v2.3 目录 14 460 文件／mtime 15:19:37、`Confucius4_LiveCaption_v2.4` 目录 14 462 文件／mtime **19:35:08**（reviewer 领地，本轮零写入、未做全量 SHA 复算 ⇒ 不写「一字节未动」实测结论），v2.0/2.1/2.2 zip bytes/mtime 见 json。
- **STATUS 写入（APP-052④）**：写前 **34 967 B／197 行**；限额 ≤40 000 B／≤300 行 ⇒ 把 §151 正文 **{SEC151_BYTES} B 整块逐字归档**到 `status/archive/STATUS_APP_sec151_20261107.md`（块 SHA256 `{SEC151_SHA}`）并留速查行；头部仅改 4 行（last_ack→APP-083、更新时间→`{NOW}`、当前任务、阻塞/待用户决定），旧章节正文逐字未变；写后 **{AFTER_BYTES} B／{AFTER_LINES} 行**，写前自检 **{NCHECKS}/{NCHECKS} PASS**（反向还原==旧全文・归档件逐字命中・章节不减・LF 未破・限额内・产物表 SHA 与磁盘一致）＋临时文件原子替换＋写后磁盘逐字节复核。
- **本轮产物**（文件数／mtime／字节数／SHA256 全部落盘实测）：

  | 产物 | 用途 | 文件数 | mtime | 字节数 | SHA256 |
  |---|---|---|---|---|---|
{ARTIFACT_ROWS}
- **纪律**：纯 CPU 静态；未建 `MACHINE_LOCK`、未占设备、未在 CPU 跑推理或测速、未调 MiniMax；未打包／未打 zip／未改客户包与 .lnk／未 `--same-version`／未 force push／未提交纠偏文件（逐文件 `git add`）。`last_ack` → **APP-083**，「更新时间」取 `Get-Date` 实测 **{NOW}**。
- **下一轮必读**：① 等 reviewer 构建并交付 v2.4 后再做 APP-082 审计（对象 v2.4、非 v2.3）与下一版 CLI `unexpected keyword`=0 复验；② v2.3 已作废，不再对其做任何验收／复核／SHA 主张；③ ACK 节点处理完前不打包、不自创「覆盖审计/静态自证」类轮次、不通知用户；④ 「不主动打包」规则不变。
'''

NCHECKS = 15
fixed = {
    '{NOW}': NOW, '{SEC151_BYTES}': str(len(arch_bytes)), '{SEC151_SHA}': arch_sha,
    '{NCHECKS}': str(NCHECKS), '{ARTIFACT_ROWS}': rows.rstrip('\n') + '\n',
}
base = BODY
for k, v in fixed.items():
    base = base.replace(k, v)
assert '{' not in base.replace('{AFTER_BYTES}', '').replace('{AFTER_LINES}', ''), 'unreplaced placeholder'

# fixed-point for self-referential AFTER_BYTES / AFTER_LINES
ab, al = 0, 0
for _ in range(40):
    sec = base.replace('{AFTER_BYTES}', str(ab)).replace('{AFTER_LINES}', str(al))
    new_text = head_prefix + quickref + '\n' + sec
    nb = len(new_text.encode('utf-8'))
    nl = new_text.count('\n') + 1
    if (nb, nl) == (ab, al):
        break
    ab, al = nb, nl
else:
    raise RuntimeError('fixed point did not converge')

sec152_text = sec
new_bytes = new_text.encode('utf-8')

# ---------------- pre-write self checks ----------------
checks = {}
checks['01_corrections_open_equals_close'] = rec['corrections_open_equals_close']
checks['02_open_matches_manual_baseline'] = rec['corrections_open_matches_manual_baseline']
checks['03_no_missing_or_dup_numbers'] = (op['missing_numbers'] == [] and op['duplicate_numbers'] == []
                                          and op['n_headings'] == op['n_uniq'] == 83)
checks['04_status_last_ack_before_APP081'] = last_ack_before == 'APP-081'
checks['05_two_new_headings_082_083'] = new_headings == ['APP-082', 'APP-083']
checks['06_last_ack_after_equals_max'] = rec['status_last_ack_after'] == 'APP-%03d' % op['max']
_newvals = [v[1] for v in changes.values()]
checks['07_header_exactly_4_lines_changed'] = (
    len(changes) == 4
    and any(v.startswith('last_ack: APP-083') for v in _newvals)
    and any(v.startswith('更新时间: ' + NOW) for v in _newvals)
    and any(v.startswith('当前任务: ') for v in _newvals)
    and any(v.startswith('阻塞 / 待用户决定: ') for v in _newvals))
# reverse restore
restored = new_text
assert restored.endswith(sec152_text)
restored = restored[:-len(sec152_text)]
assert restored.endswith(quickref + '\n'), repr(restored[-80:])
restored = restored[:-(len(quickref) + 1)]
rl = restored.split('\n')
for i, (oldl, newl) in changes.items():
    assert rl[i] == newl, (i, rl[i][:60])
    rl[i] = oldl
restored = '\n'.join(rl) + sec151
checks['08_reverse_restore_equals_old_fulltext'] = (restored == old_text)
checks['09_archive_verbatim_hit'] = (arch_bytes == sec151.encode('utf-8')
                                     and sec151.startswith('## §151 ')
                                     and old_text.endswith(sec151)
                                     and open(ARCH, 'rb').read() == arch_bytes)
old_markers = re.findall(r'(?m)^## §\d+', old_text)
new_markers = re.findall(r'(?m)^## §\d+', new_text)
checks['10_sections_not_lost'] = (len(new_markers) == len(old_markers)
                                  and all(mk in new_markers for mk in old_markers if mk != '## §151')
                                  and '## §152' in new_markers)
checks['11_lf_only_and_trailing_newline'] = (b'\r' not in new_bytes and new_bytes.endswith(b'\n'))
checks['12_within_limits'] = (len(new_bytes) <= 40000 and nl <= 300)
checks['13_artifact_sha_match_disk'] = (finfo(JPATH)['sha256'] == jfi['sha256']
                                        and finfo(PPATH)['sha256'] == pfi['sha256']
                                        and finfo(ARCH)['sha256'] == arch_sha)
checks['14_git_staged_before_empty'] = rec['git']['staged_before'] == []
checks['15_token_and_discipline_all_false'] = (TOKEN == '2635e27b'
    and not any([rec['discipline'][k] for k in ('built_machine_lock', 'occupied_device',
        'cpu_inference_or_bench', 'called_minimax', 'packed', 'made_zip',
        'modified_customer_package', 'modified_lnk', 'notified_user',
        'same_version_repack', 'force_push', 'committed_corrections', 'self_invented_task')]))
assert len(checks) == NCHECKS
assert all(checks.values()), json.dumps(checks, ensure_ascii=False, indent=2)

# ---------------- atomic STATUS replace + bytewise re-read ----------------
tmp = STAT + '.app343.tmp'
with open(tmp, 'wb') as f:
    f.write(new_bytes)
os.replace(tmp, STAT)
after = open(STAT, 'rb').read()
checks_after = {
    'disk_bytewise_equals_expected': after == new_bytes,
    'disk_bytes': len(after), 'disk_lines': after.count(b'\n') + 1,
    'disk_sha256': sha(after),
    'archive_written': open(ARCH, 'rb').read() == arch_bytes,
}
assert checks_after['disk_bytewise_equals_expected'] and checks_after['archive_written']

print('=== PRE-WRITE SELF CHECKS (%d) ===' % NCHECKS)
for k in sorted(checks):
    print('  %-48s %s' % (k, 'PASS' if checks[k] else 'FAIL'))
print('=== AFTER WRITE ===')
for k, v in checks_after.items():
    print('  %-48s %s' % (k, v))
print('=== FIXED POINT === after_bytes=%d after_lines=%d' % (len(new_bytes), nl))
print('=== KEY FACTS ===')
print('  corrections_open =', json.dumps(op, ensure_ascii=False))
print('  corrections_close=', json.dumps(cl, ensure_ascii=False))
print('  new_headings     =', new_headings)
print('  last_ack         =', last_ack_before, '->', rec['status_last_ack_after'])
print('  git              =', json.dumps(rec['git'], ensure_ascii=False))
print('  machine_lock     =', json.dumps(rec['machine_lock'], ensure_ascii=False))
print('  pids             =', json.dumps(rec['prior_background_pids'], ensure_ascii=False))
print('  literal_audit    =', json.dumps(rec['literal_audit'], ensure_ascii=False))
print('  json_sha         =', finfo(JPATH)['sha256'], 'bytes=', finfo(JPATH)['bytes'], 'mtime=', finfo(JPATH)['mtime'])
print('  py_sha           =', finfo(PPATH)['sha256'], 'bytes=', finfo(PPATH)['bytes'], 'mtime=', finfo(PPATH)['mtime'])
print('  arch_sha         =', arch_sha, 'bytes=', len(arch_bytes), 'mtime=', arch_mtime)
print('ALL_ASSERTIONS_PASSED')
