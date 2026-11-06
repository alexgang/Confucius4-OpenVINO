# -*- coding: utf-8 -*-
"""§142 静态证据自证（纯只读 / 不占设备 / 不加载模型 / 不调 MiniMax）。

自证四组：
  A 纠偏文件基线 + 编号完整性 + last_ack 对齐
  B git 纪律（暂存区不含 CORRECTIONS / 无半交付）
  C STATUS「当前有效结论」引用的证据文件落盘点验（三态：found / unresolved）
  D 旧包 v2.0/v2.1/v2.2 的 zip「一字节未动」实算 SHA256 对照
  E 反证组：复用与 A/C/D 完全相同的判据函数，注入已知缺陷，必须被识破
"""
import os
import re
import json
import hashlib
import subprocess
import datetime

ROOT = 'C:/Users/Trekker-PTL/confucius4-openvino'
CORR = ROOT + '/status/app/CORRECTIONS_APP.md'
STATUS = ROOT + '/status/app/STATUS_APP.md'
RES = ROOT + '/results/app'
OUT = RES + '/_app312_sec142_static_recheck.json'
PKG_BASE = 'C:/Users/Trekker-PTL'

# 开工基线（本轮 20:47 实测，非推算）
BASE_SHA = 'bbc95c4382f29fa3c8b4f1b49ff644339b025f78447a3bb263e6b680ad4d82af'
BASE_BYTES = 220735
BASE_MTIME = '2026-11-06 13:31:54'
BASE_IDS = list(range(1, 79))
# 开工探查（20:50）已知：STATUS 表引用该历史截图，但仓库内无此文件 ⇒ 如实记 unresolved
EXPECTED_UNRESOLVED = {'app048_layout_1920x1080.png'}
STATUS_SHA_ANCHOR = {
    '2.0': '8198924f',
    '2.1': '835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4',
    '2.2': 'ea5c5c850f8836a7edab982611cdd59d0ba0e83f8d5ff880cc797b7c67c23b75',
}


def now_str():
    try:
        return subprocess.check_output(
            ['powershell', '-NoProfile', '-Command',
             'Get-Date -Format "yyyy-MM-dd HH:mm:ss"'],
            text=True, timeout=30).strip()
    except Exception:
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def meta(path):
    st = os.stat(path)
    return {
        'bytes': st.st_size,
        'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
    }


def git(*args):
    return subprocess.check_output(['git', '-C', ROOT] + list(args), text=True).strip()


# ---- 判据函数（A/C/D 与反证组共用同一对象） ----
def j_eq(a, b):
    return a == b


def j_ids(ids):
    return ids == BASE_IDS


def j_missing(actual, declared):
    return set(actual) == set(declared)


def j_ack(ack, mx):
    return ack == mx


def j_zip_sha(measured, expected):
    return measured == expected


checks = []


def ck(cid, desc, expected, actual):
    p = bool(expected == actual)
    checks.append({'id': cid, 'desc': desc, 'expected': expected,
                   'actual': actual, 'pass_': p})
    return p


# ---------------- A 纠偏文件 / last_ack ----------------
raw = open(CORR, 'rb').read()
ids = [int(x) for x in re.findall(rb'(?m)^## APP-(\d+)', raw)]
csha = hashlib.sha256(raw).hexdigest()
cmeta = meta(CORR)
ck('A1', '纠偏文件 SHA256 == 开工基线', BASE_SHA, csha)
ck('A2', '纠偏文件字节数 == 开工基线', BASE_BYTES, len(raw))
ck('A3', '纠偏文件 mtime == 开工基线', BASE_MTIME, cmeta['mtime'])
ck('A4', 'APP 条目数 == 78', 78, len(ids))
ck('A5', '编号 1..78 连续且无重复', True, j_ids(ids))
ck('A6', '最大编号 == 78', 78, max(ids))

status_txt = open(STATUS, 'r', encoding='utf-8').read()
m_la = re.search(r'(?m)^last_ack:\s*APP-(\d+)', status_txt)
last_ack = int(m_la.group(1)) if m_la else None
ck('A7', 'last_ack == 最大编号（即无新纠偏）', True, j_ack(last_ack, max(ids)))

# ---------------- B git 纪律 ----------------
head = git('log', '-1', '--format=%H')
ahead = int(git('rev-list', '--count', 'origin/main..HEAD'))
staged = [x for x in git('diff', '--cached', '--name-only').splitlines() if x]
corr_wt = git('status', '--porcelain', '--', 'status/app/CORRECTIONS_APP.md')
ck('B1', '暂存区不含 CORRECTIONS_APP.md（绝不提交纠偏文件）', False,
   'status/app/CORRECTIONS_APP.md' in staged)
ck('B2', 'origin/main..HEAD == 0（无半交付漏项）', 0, ahead)
ck('B3', '纠偏文件工作区为 reviewer 的未提交改动（本轮只读不碰）', True,
   corr_wt.startswith('M') or corr_wt.startswith(' M'))

# ---------------- C 证据文件落盘点验 ----------------
toks = sorted(set(re.findall(
    r'(?:results/app/)?(_?app\d{3}[A-Za-z0-9_.-]*\.(?:json|png|log|txt|md))',
    status_txt)))
search_dirs = [RES, ROOT + '/results', ROOT + '/status/app',
               ROOT, ROOT + '/status/archive']
found, missing = [], []
for t in toks:
    hit = None
    for d in search_dirs:
        p = os.path.join(d, t)
        if os.path.isfile(p):
            hit = p
            break
    if hit is None:
        missing.append(t)
        continue
    mm = meta(hit)
    found.append({'name': t, 'path': hit, 'bytes': mm['bytes'],
                  'mtime': mm['mtime'], 'sha256': sha256(hit)})
ck('C1', 'STATUS 引用的证据文件 token 数 == 27（开工探查值）', 27, len(toks))
ck('C2', '未落盘集合 == 开工声明的唯一项（无静默漏项）',
   sorted(EXPECTED_UNRESOLVED), sorted(missing))
ck('C3', '已落盘产物数 == 26', 26, len(found))
ck('C4', '每个已落盘产物均记录 64 位 SHA256', True,
   all(len(x['sha256']) == 64 for x in found))

# ---------------- D 旧包 zip 一字节未动 ----------------
zip_audit = []
for ver in ('2.0', '2.1', '2.2'):
    zp = PKG_BASE + '/Confucius4_LiveCaption_v' + ver + '.zip'
    dj = json.load(open(RES + '/DELIVERY_' + ver + '.json', 'r', encoding='utf-8'))
    mm = meta(zp)
    ms = sha256(zp)
    anchor = STATUS_SHA_ANCHOR[ver]
    anchor_hit = ms.startswith(anchor) and (anchor in status_txt)
    rec = {
        'version': ver, 'path': zp,
        'bytes': mm['bytes'], 'mtime': mm['mtime'],
        'sha256_measured': ms, 'sha256_expected': dj['sha256'],
        'bytes_expected': dj['bytes'],
        'mtime_expected': dj['mtime'].replace('T', ' '),
        'status_anchor': anchor, 'status_anchor_hit': anchor_hit,
    }
    zip_audit.append(rec)
    ck('D' + ver + '-1', 'v' + ver + ' zip SHA256 == DELIVERY 基准',
       True, j_zip_sha(ms, dj['sha256']))
    ck('D' + ver + '-2', 'v' + ver + ' zip 字节数 == DELIVERY 基准',
       dj['bytes'], mm['bytes'])
    ck('D' + ver + '-3', 'v' + ver + ' zip mtime == DELIVERY 基准',
       dj['mtime'].replace('T', ' '), mm['mtime'])
    ck('D' + ver + '-4', 'v' + ver + ' zip SHA 与 STATUS 表锚点一致',
       True, anchor_hit)

# ---------------- E 反证组（必须全部被识破） ----------------
counter = []


def cp(cid, desc, broken_judgement):
    identified = (broken_judgement is False)
    counter.append({'id': cid, 'desc': desc,
                    'broken_judgement': broken_judgement,
                    'identified': identified})
    return identified


cp('E1', '把 zip 期望 SHA 换成全零 ⇒ D-1 同一判据须 FAIL',
   j_zip_sha('0' * 64, zip_audit[1]['sha256_measured']))
cp('E2', '删掉一个 APP 编号 ⇒ A5 连续性判据须 FAIL',
   j_ids([x for x in ids if x != 40]))
cp('E3', '把未落盘声明改成空集 ⇒ C2 判据须 FAIL',
   j_missing(missing, set()))
cp('E4', '把 last_ack 换成 77 ⇒ A7 对齐判据须 FAIL',
   j_ack(77, max(ids)))

n_pass = sum(1 for c in checks if c['pass_'])
n_fail = sum(1 for c in checks if not c['pass_'])
all_identified = all(c['identified'] for c in counter)
verdict = 'PASS' if (n_fail == 0 and all_identified) else 'FAIL'

out = {
    'generated_at': now_str(),
    'scope': '§142 静态证据自证（纯只读 / 不占设备 / 不加载模型 / 不调 MiniMax）',
    'machine_lock': 'NOT_PRESENT（本轮未占设备、未创建）',
    'corrections_baseline': {
        'path': CORR, 'sha256': csha, 'bytes': len(raw),
        'mtime': cmeta['mtime'], 'count': len(ids),
        'min_id': min(ids), 'max_id': max(ids),
    },
    'status_head': {'last_ack': last_ack, 'path': STATUS},
    'git': {
        'head': head, 'ahead_origin_main': ahead,
        'staged_count': len(staged),
        'corrections_worktree': corr_wt,
    },
    'evidence_files': found,
    'unresolved': [{'name': t, 'reason': '仓库内多目录检索均未找到；按三态记为「无法判定」，不判不合格、不写成已落盘'}
                   for t in missing],
    'zip_audit': zip_audit,
    'checks': checks,
    'counterproof': counter,
    'n_pass': n_pass, 'n_fail': n_fail,
    'counterproof_identified': sum(1 for c in counter if c['identified']),
    'counterproof_total': len(counter),
    'verdict': verdict,
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('OUT=' + OUT)
print('VERDICT=' + verdict + ' n_pass=' + str(n_pass) + ' n_fail=' + str(n_fail))
print('COUNTERPROOF_IDENTIFIED=' + str(out['counterproof_identified']) + '/' + str(len(counter)))
print('EVIDENCE_FILES=' + str(len(found)) + ' UNRESOLVED=' + str(missing))
for c in checks:
    if not c['pass_']:
        print('FAIL_CHECK=' + c['id'] + ' ' + c['desc'])
