"""§143 报数证据链静态自证（APP-046② 不空转；纯 CPU / 只读 / 不 import 被测模块 / 不占设备）。

本轮巡检无新纠偏（last_ack=APP-080，CORRECTIONS 80 条），故复核上一轮 §143 的：
  A 纠偏文件开工/收尾基线（SHA256 / 字节 / mtime / 条数 / 编号连续）
  B STATUS §143 产物表 12 个文件的 mtime / 字节数 / SHA256 是否与 STATUS 报数一致
  C 4 个结果 JSON 的原始字段（verdict / n_pass / n_fail / counterproof_identified）是否与报数一致
  D STATUS 头部对齐、限额、章节、git 纪律（无半交付 / 上轮提交不含纠偏文件）
并对每条判据构造篡改输入作为反证（判据必须能识破，证明非恒真）。
"""
import os
import re
import json
import hashlib
import datetime
import subprocess

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
RES = os.path.join(ROOT, 'results', 'app')
OUT = os.path.join(RES, '_app318_sec143_evidence_recheck.json')

# 本轮 00:26 开工实测基线（硬编码进判据，收尾复核须与之逐字相同）
BASE = {
    'sha256': 'b3ae9ea9fb72282bbf619dd26b73de688f8c771911bd0b56e0faf8f392b937d5',
    'bytes': 224562,
    'mtime': '2026-11-06 21:40:34',
    'count': 80,
    'max_no': 80,
}

# §143 正文报出的 4 个结果文件的原始字段
REPORTS = {
    '_app314_app079_static_triage.json': {'verdict': 'PASS', 'n_pass': 10, 'n_fail': 0, 'counterproof_identified': '4/4'},
    '_app315_app080_preset_only_selftest.json': {'verdict': 'PASS', 'n_pass': 36, 'n_fail': 0, 'n_unknown': 0, 'counterproof_identified': '8/8'},
    '_app316_docstring_guard_fix.json': {'verdict': 'PASS'},
    '_app317_write_status_sec143.json': {'verdict': 'PASS'},
}

ROW_RE = re.compile(
    r'^\|\s*`([^`]+)`\s*\|\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s*\|\s*(\d+)\s*\|\s*`([0-9a-f]{64})`\s*\|\s*$',
    re.M)


def fp(path, fmt='%Y-%m-%dT%H:%M:%S'):
    b = open(path, 'rb').read()
    st = os.stat(path)
    return {
        'sha256': hashlib.sha256(b).hexdigest(),
        'bytes': len(b),
        'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime(fmt),
    }


def load_json(name):
    with open(os.path.join(RES, name), encoding='utf-8') as f:
        return json.load(f)


# ---- 判据（接受快照参数，便于反证注入篡改输入） ----
def crit_baseline(b, nums):
    return (b['sha256'] == BASE['sha256'] and b['bytes'] == BASE['bytes']
            and b['mtime'] == BASE['mtime'] and len(nums) == BASE['count']
            and nums == list(range(1, BASE['count'] + 1)) and max(nums) == BASE['max_no'])


def crit_artifacts(rows):
    if len(rows) != 12 or len({r['path'] for r in rows}) != 12:
        return False
    for r in rows:
        p = os.path.join(ROOT, r['path'])
        if not os.path.isfile(p):
            return False
        f = fp(p)
        if f['sha256'] != r['sha256'] or f['bytes'] != int(r['bytes']) or f['mtime'] != r['mtime']:
            return False
    return True


def crit_reports(reps):
    for name, exp in REPORTS.items():
        d = reps.get(name)
        if not isinstance(d, dict):
            return False
        for k, v in exp.items():
            if d.get(k) != v:
                return False
    return True


def crit_alignment(head, nums):
    return head.get('last_ack') == 'APP-%03d' % max(nums)


def crit_limits(info):
    return info['bytes'] <= 40000 and info['lines'] <= 300 and info['crlf'] == 0


# ---- 采集 ----
corr_bytes = open(CORR, 'rb').read()
corr_fp = {
    'sha256': hashlib.sha256(corr_bytes).hexdigest(),
    'bytes': len(corr_bytes),
    'mtime': datetime.datetime.fromtimestamp(os.stat(CORR).st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
}
nums = [int(x) for x in re.findall(rb'(?m)^## APP-(\d+)', corr_bytes)]

status_bytes = open(STATUS, 'rb').read()
status_text = status_bytes.decode('utf-8')
status_info = {
    'bytes': len(status_bytes),
    'lines': status_text.count('\n') + 1,
    'crlf': status_bytes.count(b'\r\n'),
    'sections': len(re.findall(r'(?m)^## ', status_text)),
}
head = {}
m = re.search(r'(?m)^last_ack:\s*(\S+)', status_text)
head['last_ack'] = m.group(1) if m else None
m = re.search(r'(?m)^更新时间:\s*(.+)', status_text)
head['updated_at'] = m.group(1).strip() if m else None

rows = [{'path': a, 'mtime': b, 'bytes': int(c), 'sha256': d}
        for a, b, c, d in ROW_RE.findall(status_text)]
reps = {n: load_json(n) for n in REPORTS}

artifact_details = []
for r in rows:
    p = os.path.join(ROOT, r['path'])
    if os.path.isfile(p):
        f = fp(p)
        artifact_details.append({
            'path': r['path'], 'disk_bytes': f['bytes'], 'disk_mtime': f['mtime'], 'disk_sha256': f['sha256'],
            'reported_match': (f['sha256'] == r['sha256'] and f['bytes'] == r['bytes'] and f['mtime'] == r['mtime']),
        })
    else:
        artifact_details.append({'path': r['path'], 'disk_bytes': None, 'disk_mtime': None,
                                 'disk_sha256': None, 'reported_match': False})

# ---- git 静态纪律（失败记「无法判定」，不伪装成产品 FAIL） ----
def git_out(args):
    try:
        r = subprocess.run(['git', '-C', ROOT] + args, capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


head_files = git_out(['show', '--pretty=format:', '--name-only', 'HEAD'])
ahead = git_out(['rev-list', '--count', 'origin/main..HEAD'])
git_info = {
    'head': git_out(['rev-parse', '--short', 'HEAD']),
    'ahead': ahead,
    'head_files_n': len([x for x in head_files.splitlines() if x.strip()]) if head_files is not None else None,
    'corrections_in_head_commit': (('status/app/CORRECTIONS_APP.md' in head_files) if head_files is not None else None),
}

checks = []


def ck(cid, desc, ok, evidence):
    checks.append({'id': cid, 'desc': desc, 'ok': ok, 'evidence': evidence})


ck('C01', 'CORRECTIONS 开工基线 SHA/字节/mtime/条数/编号连续 全等', crit_baseline(corr_fp, nums),
   {'sha256': corr_fp['sha256'], 'bytes': corr_fp['bytes'], 'mtime': corr_fp['mtime'],
    'count': len(nums), 'min': min(nums), 'max': max(nums)})
ck('C02', 'STATUS 头部 last_ack 与纠偏最大编号对齐', crit_alignment(head, nums),
   {'last_ack': head['last_ack'], 'max_no': max(nums)})
ck('C03', 'STATUS §143 产物表解析出 12 行且路径互异', len(rows) == 12 and len({r['path'] for r in rows}) == 12,
   {'n_rows': len(rows)})
ck('C04', '12 个产物的 mtime/字节/SHA256 与 STATUS 报数逐条一致', crit_artifacts(rows),
   {'matched': sum(1 for x in artifact_details if x['reported_match']), 'total': len(artifact_details)})
ck('C05', '4 个结果 JSON 的原始字段与 §143 报数一致', crit_reports(reps),
   {n: {k: d.get(k) for k in REPORTS[n]} for n, d in reps.items()})
ck('C06', 'STATUS 限额 ≤40000 B / ≤300 行 且 LF 行尾未破', crit_limits(status_info), status_info)
ck('C07', '§143 章节存在且章节数不减（≥7）', '## §143' in status_text and status_info['sections'] >= 7,
   {'sections': status_info['sections'], 'has_sec143': '## §143' in status_text})
ck('C08', 'STATUS 更新时间与 _app317 落盘时间一致',
   head['updated_at'] == reps['_app317_write_status_sec143.json'].get('generated_at'),
   {'status_updated_at': head['updated_at'], 'app317_generated_at': reps['_app317_write_status_sec143.json'].get('generated_at')})
ck('C09', '_app317 写 STATUS 自检 verdict=PASS 且纠偏文件开工/收尾 identical',
   reps['_app317_write_status_sec143.json'].get('verdict') == 'PASS'
   and reps['_app317_write_status_sec143.json'].get('corrections', {}).get('identical') is True,
   {'verdict': reps['_app317_write_status_sec143.json'].get('verdict'),
    'identical': reps['_app317_write_status_sec143.json'].get('corrections', {}).get('identical')})
ck('C10', '上轮提交不含 CORRECTIONS_APP.md', git_info['corrections_in_head_commit'] is False,
   git_info)
ck('C11', 'origin/main..HEAD = 0（无半交付）', ahead == '0', {'ahead': ahead})
for i, d in enumerate(artifact_details, 1):
    ck('A%02d' % i, '产物 %s 磁盘元数据匹配' % d['path'], d['reported_match'], d)

# ---- 反证：篡改输入后判据必须返回 False ----
cp = []


def cpk(cid, mutation, detected):
    cp.append({'id': cid, 'mutation': mutation, 'detected': detected})


bad = [dict(r) for r in rows]
bad[0]['sha256'] = '0' * 64
cpk('E1', '把产物表第 1 行 SHA256 改成全 0', crit_artifacts(bad) is False)

bad = [dict(r) for r in rows]
bad[3]['bytes'] = bad[3]['bytes'] + 1
cpk('E2', '把产物表第 4 行字节数 +1', crit_artifacts(bad) is False)

bad = dict(reps)
bad['_app314_app079_static_triage.json'] = dict(reps['_app314_app079_static_triage.json'], n_pass=9)
cpk('E3', '把 _app314 的 n_pass 从 10 改成 9', crit_reports(bad) is False)

bad = dict(corr_fp, sha256='f' * 64, bytes=corr_fp['bytes'] + 1)
cpk('E4', '模拟 reviewer 中途追加条目（SHA/字节变化）', crit_baseline(bad, nums) is False)

bad = dict(head, last_ack='APP-079')
cpk('E5', '把 last_ack 改成 APP-079（未追平）', crit_alignment(bad, nums) is False)

bad = dict(status_info, bytes=42007)
cpk('E6', '模拟 STATUS 超 40 000 B 限额', crit_limits(bad) is False)

cpk('E7', '删掉产物表最后一行（模拟产物漏落盘）', crit_artifacts(rows[:-1]) is False)

n_pass = sum(1 for c in checks if c['ok'] is True)
n_fail = sum(1 for c in checks if c['ok'] is False)
n_unknown = sum(1 for c in checks if c['ok'] is None)
n_detected = sum(1 for c in cp if c['detected'])
verdict = 'PASS' if (n_fail == 0 and n_unknown == 0 and n_detected == len(cp)) else 'FAIL'

report = {
    'tool': '_app318_sec143_evidence_recheck',
    'app': 'APP',
    'scope': '§143 报数证据链静态自证（无新纠偏；不占设备）',
    'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'machine_lock': 'NOT_USED (static CPU only, no model loaded)',
    'corrections_baseline': dict(corr_fp, count=len(nums), min_no=min(nums), max_no=max(nums)),
    'status': dict(status_info, last_ack=head['last_ack'], updated_at=head['updated_at']),
    'git': git_info,
    'artifacts': artifact_details,
    'reported_fields': {n: {k: d.get(k) for k in REPORTS[n]} for n, d in reps.items()},
    'checks': checks,
    'n_pass': n_pass,
    'n_fail': n_fail,
    'n_unknown': n_unknown,
    'counterproof': cp,
    'counterproof_identified': '%d/%d' % (n_detected, len(cp)),
    'verdict': verdict,
    'note': '只读项目文件；不 import 被测模块；不创建 MACHINE_LOCK；不在 CPU 跑推理；未调 MiniMax。',
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps({k: report[k] for k in ('verdict', 'n_pass', 'n_fail', 'n_unknown',
                                         'counterproof_identified', 'counterproof')}, ensure_ascii=False, indent=2))
