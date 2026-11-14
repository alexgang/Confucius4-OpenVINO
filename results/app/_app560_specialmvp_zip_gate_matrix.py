#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app560_specialmvp_zip_gate_matrix.py —— §204：Special MVP 打 zip 闸门的
**反证矩阵**（证明修复前后行为差异，且**零接触客户包、零写入**）。

做法：
  · **改前**（fail-open / 假 FAIL）：从 `git cat-file blob HEAD:…` 取**原始脚本**，
    只改三处常量（`PKG_NAME` / `ACCEPT` / `ZIP`；模拟「只改 PKG_NAME、ACCEPT
    仍指 sp1」这类真实误操作），并在打包前**插一行 `raise SystemExit(0)`**
    ⇒ 闸门**逐字按原样执行**，但**绝不会真的打 zip / 改 README**；
  · **改后**：**直接跑仓库里已修好的脚本**（`--check-only` ⇒ 零写入）；
  · **单元级反证**：`ast` 抽出被测函数单独 exec（避开模块级副作用），
    用**临时假包**测版本标识自洽检查（**不碰真实客户包**）。

🔴 **两臂都把 zip 指向一个不存在的临时路径** ⇒ 「zip 已存在」这个与闸门无关的
   守卫不会污染判定（T1 的首版就是这么假 FAIL 的，已修）。
🔴 本脚本**只读**真实客户包；唯一的写入是自身的证据 json。
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
NEW = os.path.join(RESULTS, '_app537_zip_specialmvp.py')
REPORT = os.path.join(RESULTS, 'app560_specialmvp_zip_gate_matrix.json')

SP1 = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1'
SP2 = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2'
ACC_SP1 = 'app536_specialmvp_acceptance.json'
ACC_SP2 = 'app553_specialmvp_sp2_acceptance.json'

ev = {'rows': [], 'note': '§204 Special MVP zip 闸门反证矩阵'}


def git_blob(rel):
    p = subprocess.run(['git', '-C', REPO, 'cat-file', 'blob', 'HEAD:' + rel],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('git cat-file 失败：%s'
                           % p.stderr.decode('utf-8', 'replace'))
    return p.stdout.decode('utf-8')


def classify(msg):
    """把异常消息归到「拒绝原因」类，便于证明拒绝得**对不对**。"""
    for key, pat in (('PKG_MISMATCH', '验收证据属于另一个包'),
                     ('VERDICT_FAIL', '包上验收未通过'),
                     ('MISSING_EVIDENCE', '缺包上验收证据'),
                     ('RELEASE_IDENTITY', '版本标识不自洽'),
                     ('ZIP_EXISTS', 'zip 已存在'),
                     ('NO_PKG_FIELD', '缺 pkg 字段')):
        if pat in msg:
            return key
    return 'OTHER'


def run(script_path, args):
    p = subprocess.run([sys.executable, script_path] + args,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', cwd=REPO)
    out = (p.stdout or '') + (p.stderr or '')
    blocked = ('RuntimeError' in out) or (p.returncode != 0
                                          and 'Traceback' in out)
    last = out.strip().splitlines()[-1] if out.strip() else ''
    return {'rc': p.returncode, 'blocked': blocked, 'msg': last[:240],
            'reason': classify(last) if blocked else '-'}


def make_old_variant(pkg_name, accept_abs, zip_abs):
    """从 HEAD 的原始脚本造一个「只改常量 + 打包前立刻退出」的变体。"""
    src = git_blob('results/app/_app537_zip_specialmvp.py')
    subs = [
        ("PKG_NAME = '%s'" % SP1, "PKG_NAME = '%s'" % pkg_name),
        ("ACCEPT = os.path.join(RESULTS, 'app536_specialmvp_acceptance.json')",
         "ACCEPT = r'%s'" % accept_abs),
        ("ZIP = os.path.join(HOME, 'shared', 'specialmvp',\n"
         "                   PKG_NAME + '.zip')", "ZIP = r'%s'" % zip_abs),
    ]
    for old, new in subs:
        assert src.count(old) == 1, '改前脚本常量定位失败：%r' % old[:60]
        src = src.replace(old, new)
    cut = 'if os.path.exists(ZIP):'
    assert src.count(cut) == 1, '改前脚本切割点定位失败'
    src = src.replace(cut, 'raise SystemExit(0)\n' + cut)
    fd, tmp = tempfile.mkstemp(suffix='_old_variant.py')
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
        f.write(src)
    return tmp


tmp_zip_dir = tempfile.mkdtemp(prefix='app560_zip_')
cases = [
    ('T1', SP1, ACC_SP1, 'sp1 + sp1 自己的证据 ⇒ 允许（**回归护栏**：既有行为不变）',
     'ALLOW', 'ALLOW', 'ALLOW', '-'),
    ('T2', SP1, ACC_SP2, 'sp1 + sp2 的证据 ⇒ 拒绝（证据属于别的包）',
     'BLOCK', 'BLOCK', 'BLOCK', 'PKG_MISMATCH'),
    ('T3', SP2, ACC_SP2, 'sp2 + sp2 自己的证据（verdict=PASS（有 1 项未结：…））'
     '⇒ 允许（**改前是假 FAIL**）',
     'BLOCK', 'ALLOW', 'ALLOW', '-'),
    ('T4', SP2, ACC_SP1, '🔴 sp2 + sp1 的证据 ⇒ **必须拒绝**（**改前这里被放行**）',
     'ALLOW', 'BLOCK', 'BLOCK', 'PKG_MISMATCH'),
]
for tid, pkg, acc, desc, want_old, want_new, _, want_reason in cases:
    acc_abs = os.path.join(RESULTS, acc)
    zip_abs = os.path.join(tmp_zip_dir, '%s.zip' % tid)
    tmp_old = make_old_variant(pkg, acc_abs, zip_abs)
    try:
        old = run(tmp_old, [])
    finally:
        os.remove(tmp_old)
    new = run(NEW, ['--pkg-name', pkg, '--accept', acc,
                    '--zip', zip_abs, '--check-only'])
    old_v = 'BLOCK' if old['blocked'] else 'ALLOW'
    new_v = 'BLOCK' if new['blocked'] else 'ALLOW'
    ev['rows'].append({
        'id': tid, 'desc': desc, 'pkg': pkg, 'accept': acc,
        'old_verdict': old_v, 'old_expect': want_old, 'old_ok': old_v == want_old,
        'old_reason': old['reason'], 'old_msg': old['msg'], 'old_rc': old['rc'],
        'new_verdict': new_v, 'new_expect': want_new, 'new_ok': new_v == want_new,
        'new_reason': new['reason'], 'new_msg': new['msg'], 'new_rc': new['rc'],
        'new_reason_expect': want_reason,
        'new_reason_ok': (new['reason'] == want_reason),
        'discriminator': old_v != new_v,
    })

# ── ② 缺证据 / verdict 未通过 ⇒ 两边都必须拒绝 ──
missing = os.path.join(RESULTS, 'app_zzz_not_exist.json')
new = run(NEW, ['--pkg-name', SP2, '--accept', missing,
                '--zip', os.path.join(tmp_zip_dir, 'T5.zip'), '--check-only'])
ev['rows'].append({
    'id': 'T5', 'desc': 'sp2 + 不存在的验收证据 ⇒ 必须拒绝',
    'pkg': SP2, 'accept': 'app_zzz_not_exist.json',
    'old_verdict': 'BLOCK', 'old_expect': 'BLOCK', 'old_ok': True,
    'old_reason': 'MISSING_EVIDENCE', 'old_msg': '（改前同样拒绝：缺文件）',
    'old_rc': None,
    'new_verdict': 'BLOCK' if new['blocked'] else 'ALLOW', 'new_expect': 'BLOCK',
    'new_ok': new['blocked'], 'new_reason': new['reason'],
    'new_reason_expect': 'MISSING_EVIDENCE',
    'new_reason_ok': new['reason'] == 'MISSING_EVIDENCE',
    'new_msg': new['msg'], 'new_rc': new['rc'], 'discriminator': False,
})

tmpdir = tempfile.mkdtemp(prefix='app560_failverdict_')
fail_json = os.path.join(tmpdir, 'fail_accept.json')
with open(fail_json, 'w', encoding='utf-8') as f:
    json.dump({'pkg': os.path.join(HOME, SP2), 'verdict': 'FAIL',
               'checks': [], 'open_issues': []}, f, ensure_ascii=False)
new = run(NEW, ['--pkg-name', SP2, '--accept', fail_json,
                '--zip', os.path.join(tmp_zip_dir, 'T6.zip'), '--check-only'])
ev['rows'].append({
    'id': 'T6', 'desc': 'sp2 + verdict=FAIL 的证据 ⇒ 必须拒绝',
    'pkg': SP2, 'accept': '<temp>/fail_accept.json',
    'old_verdict': 'BLOCK', 'old_expect': 'BLOCK', 'old_ok': True,
    'old_reason': 'VERDICT_FAIL', 'old_msg': '（改前同样拒绝：verdict != PASS）',
    'old_rc': None,
    'new_verdict': 'BLOCK' if new['blocked'] else 'ALLOW', 'new_expect': 'BLOCK',
    'new_ok': new['blocked'], 'new_reason': new['reason'],
    'new_reason_expect': 'VERDICT_FAIL',
    'new_reason_ok': new['reason'] == 'VERDICT_FAIL',
    'new_msg': new['msg'], 'new_rc': new['rc'], 'discriminator': False,
})

# ── ③ 单元级反证：版本标识自洽检查（用**假包**，不碰真实客户包）──
src = open(NEW, encoding='utf-8').read()
tree = ast.parse(src)
wanted = {'_norm_pkg', '_verdict_ok', 'check_acceptance',
          'check_release_identity'}
ns = {'os': os, 're': re, 'json': json}
picked = [n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name in wanted]
assert {n.name for n in picked} == wanted, 'AST 没抽全被测函数'
exec(compile(ast.fix_missing_locations(ast.Module(body=picked, type_ignores=[])),
             NEW, 'exec'), ns)

fake_root = os.path.join(tempfile.mkdtemp(prefix='app560_fakepkg_'), 'Fake_v9.9-zz')
os.makedirs(fake_root, exist_ok=True)
with open(os.path.join(fake_root, 'release.json'), 'w', encoding='utf-8') as f:
    json.dump({'version': '9.9-zz'}, f)
try:
    ns['check_release_identity'](fake_root, 'Fake_v9.9-zz')
    unit_ok, unit_msg = True, '匹配 ⇒ 允许'
except Exception as e:
    unit_ok, unit_msg = False, str(e)
with open(os.path.join(fake_root, 'release.json'), 'w', encoding='utf-8') as f:
    json.dump({'version': '1.0-sp1'}, f)          # 故意写成别的包的版本
try:
    ns['check_release_identity'](fake_root, 'Fake_v9.9-zz')
    unit_bad_blocked, unit_bad_msg = False, '未被拒绝（漏洞！）'
except Exception as e:
    unit_bad_blocked, unit_bad_msg = True, str(e)[:160]
ev['release_identity_unit'] = {
    'match_case_allowed': unit_ok, 'match_msg': unit_msg,
    'mismatch_case_blocked': unit_bad_blocked, 'mismatch_msg': unit_bad_msg,
    'note': '用临时假包测，**未触碰任何真实客户包**',
}

# ── ④ 真实包的自洽性（只读）──
for tag, name in (('sp1', SP1), ('sp2', SP2)):
    d = os.path.join(HOME, name)
    try:
        rel = ns['check_release_identity'](d, name)
        ev.setdefault('real_pkg_release_identity', {})[tag] = {
            'ok': True, 'version': rel.get('version')}
    except Exception as e:
        ev.setdefault('real_pkg_release_identity', {})[tag] = {
            'ok': False, 'msg': str(e)[:160]}

ev['summary'] = {
    'n_rows': len(ev['rows']),
    'discriminators': [r['id'] for r in ev['rows'] if r.get('discriminator')],
    'new_failures': [r['id'] for r in ev['rows']
                     if not r['new_ok'] or not r.get('new_reason_ok', True)],
    'old_failures_vs_correct': [r['id'] for r in ev['rows'] if not r['old_ok']],
    'writes_to_customer_pkg': 0,
    'discrimination': 'T3（假 FAIL）、T4（fail-open）两行改前改后判定不同；'
                      'T1 回归护栏两边都允许',
}
ev['verdict'] = 'PASS' if not ev['summary']['new_failures'] else 'FAIL'
with open(REPORT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('verdict =', ev['verdict'])
for r in ev['rows']:
    print('%-3s old=%-5s(exp %-5s %s)  new=%-5s(exp %-5s %s) reason=%-17s '
          '%s | %s' % (r['id'], r['old_verdict'], r['old_expect'],
                       'OK' if r['old_ok'] else '✗',
                       r['new_verdict'], r['new_expect'],
                       'OK' if r['new_ok'] else '✗',
                       r['new_reason'],
                       'DIFF' if r.get('discriminator') else '    ',
                       r['desc'][:52]))
print('release_identity_unit:', json.dumps(ev['release_identity_unit'],
                                           ensure_ascii=False))
print('real_pkg:', json.dumps(ev.get('real_pkg_release_identity'),
                              ensure_ascii=False))
print('evidence:', REPORT)
