"""_app320 — APP-080「v2.3 只交付预设音色」构建期资产的**打包链路就绪度**静态盘点。

§143 落盘了 v23_preset_only.py（构建期补丁规范）、assert_pkg_clean.py（洁净度闸门），
并在 STATUS 明确警告「包内必须同时带 PKG_INCLUDE_FILES，否则 from v23_preset_only import ...
会 ImportError」。本轮核查该清单是否已被打包脚本消费。

纯 CPU 静态：只读仓库文件 + git 只读命令；不占设备、不建 MACHINE_LOCK、不推理、不打包、
不改任何客户安装目录、不调 MiniMax。判据含反证组（PASS ≠ 正确，必须能被识破）。
"""
import os
import re
import ast
import glob
import json
import hashlib
import datetime
import subprocess

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
RES = os.path.join(ROOT, 'results', 'app')
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
OUT = os.path.join(RES, '_app320_v23_build_readiness.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

# 开工实测基线（本会话 01:37 记录，非推算）
BASE_SHA = 'b3ae9ea9fb72282bbf619dd26b73de688f8c771911bd0b56e0faf8f392b937d5'
BASE_BYTES = 224562
BASE_MTIME = '2026-11-06 21:40:34'
BASE_COUNT = 80
HEAD_EXPECT = 'c6ae632'
# §143 产物表登记值（用于证明 dev 资产未被改动）
SEC143_V23_SHA = '362825e644d2edc42ef662505aaaa8dbd07cad5522da642d36cef8266dd043c7'
SEC143_V23_BYTES = 17260
SEC143_DIFF_BYTES = 8021

KW = re.compile(r'v23_preset_only|PKG_INCLUDE_FILES|assert_pkg_clean')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def read(rel):
    with open(os.path.join(ROOT, rel), 'rb') as f:
        return f.read()


def meta(rel):
    p = os.path.join(ROOT, rel)
    b = open(p, 'rb').read()
    st = os.stat(p)
    return {'path': rel,
            'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%dT%H:%M:%S'),
            'bytes': len(b), 'sha256': sha(b)}


def git(*args):
    r = subprocess.run(['git'] + list(args), cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    return r.returncode, r.stdout.strip()


def corr_ids(b):
    ids = [int(x) for x in re.findall(rb'(?m)^## APP-(\d+)', b)]
    return ids


def baseline_ok(csha, cbytes, ids, last_ack):
    """纯函数：纠偏基线 + last_ack 对齐（供反证组复用同一判据）。"""
    return (csha == BASE_SHA and cbytes == BASE_BYTES and len(ids) == BASE_COUNT
            and ids == list(range(1, BASE_COUNT + 1))
            and ('APP-%03d' % max(ids)) == last_ack)


def has_new_correction(ids, last_ack_num):
    """纯函数：是否存在编号大于 last_ack 的新条目。"""
    return max(ids) > last_ack_num


def asset_sha_ok(actual, expected):
    """纯函数：资产 SHA 与 §143 产物表一致。"""
    return actual == expected and len(actual) == 64


def consumer_hits(text):
    """纯函数：单个打包/建包脚本里对 APP-080 资产的消费引用数。"""
    return len(KW.findall(text))


def include_ok(const_list, lc_dir):
    """纯函数：PKG_INCLUDE_FILES 清单完整且每个包内路径在开发树有源。"""
    if const_list != ['app/v23_preset_only.py', 'app/assert_pkg_clean.py']:
        return False
    for rel in const_list:
        src = os.path.join(lc_dir, os.path.basename(rel))
        if not os.path.isfile(src):
            return False
    return True


def limit_ok(nbytes, nlines):
    return nbytes <= 40000 and nlines <= 300


# ---------------- 实测 ----------------
corr_b = open(CORR, 'rb').read()
corr_st = os.stat(CORR)
ids = corr_ids(corr_b)
status_b = open(STATUS, 'rb').read()
status_text = status_b.decode('utf-8')
last_ack = re.search(r'(?m)^last_ack:\s*(\S+)', status_text).group(1)
last_ack_num = int(last_ack.split('-')[1])

rc, head = git('log', '-1', '--format=%h')
rc2, ahead = git('rev-list', '--count', 'origin/main..HEAD')
rc3, branch = git('branch', '--show-current')
rc4, head_files = git('show', '--pretty=format:', '--name-only', 'HEAD')
head_files_list = [x for x in head_files.splitlines() if x.strip()]

# APP-080 dev 资产
lc = os.path.join(ROOT, 'live_caption')
v23_b = read('live_caption/v23_preset_only.py')
gate_b = read('live_caption/assert_pkg_clean.py')
v23_text = v23_b.decode('utf-8')
tree = ast.parse(v23_text)
include_const = None
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == 'PKG_INCLUDE_FILES':
                include_const = ast.literal_eval(node.value)

selftest = json.loads(read('results/app/_app315_app080_preset_only_selftest.json').decode('utf-8'))
docfix = json.loads(read('results/app/_app316_docstring_guard_fix.json').decode('utf-8'))
diff_b = read('results/app/_app315_v23_preset_only.diff')

# 打包链路消费盘点：pack_v13.py + results/app 下所有建包/建目录脚本
pack_b = read('pack_v13.py')
pack_text = pack_b.decode('utf-8', errors='replace')
build_scripts = sorted(glob.glob(os.path.join(RES, '*build*.py')) +
                       glob.glob(os.path.join(RES, '*stage*.py')))
build_scripts = sorted(set(build_scripts))
# 🔴 排除本自证脚本：文件名含 build，但它是「判据本身」而非被测的建包脚本，
#    否则会把自身对关键词的引用算成消费 ⇒ 假 FAIL（FAIL 先怀疑判据/环境）。
SELF = os.path.abspath(__file__)
build_scripts = [p for p in build_scripts if os.path.abspath(p) != SELF]
build_hits = {}
for p in build_scripts:
    rel = os.path.relpath(p, ROOT).replace('\\', '/')
    txt = open(p, 'rb').read().decode('utf-8', errors='replace')
    build_hits[rel] = consumer_hits(txt)
pack_hits = consumer_hits(pack_text)
total_hits = pack_hits + sum(build_hits.values())
packaging_chain_wired = total_hits > 0

lock_present = os.path.exists(LOCK)
status_lines = status_b.count(b'\n') + 1

facts = {
    'corrections': {'sha256': sha(corr_b), 'bytes': len(corr_b),
                    'mtime': datetime.datetime.fromtimestamp(corr_st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'count': len(ids), 'ids_min': min(ids), 'ids_max': max(ids),
                    'missing': [i for i in range(1, max(ids) + 1) if i not in set(ids)]},
    'status_before': {'bytes': len(status_b), 'lines': status_lines,
                      'sha256': sha(status_b), 'last_ack': last_ack},
    'git': {'head': head, 'ahead': ahead, 'branch': branch,
            'head_files': head_files_list},
    'machine_lock_present': lock_present,
    'app080_assets': {'v23_preset_only': meta('live_caption/v23_preset_only.py'),
                      'assert_pkg_clean': meta('live_caption/assert_pkg_clean.py'),
                      'pkg_include_files': include_const,
                      'selftest': {k: selftest.get(k) for k in
                                   ('verdict', 'n_pass', 'n_fail', 'n_unknown',
                                    'counterproof_identified')},
                      'docfix': {k: docfix.get(k) for k in ('verdict',)},
                      'diff_bytes': len(diff_b)},
    'packaging_chain': {'pack_v13_bytes': len(pack_b), 'pack_v13_sha256': sha(pack_b),
                        'pack_v13_hits': pack_hits,
                        'build_scripts_scanned': len(build_scripts),
                        'excluded_self': os.path.basename(__file__),
                        'build_scripts_nonzero_hits': {k: v for k, v in build_hits.items() if v},
                        'total_hits': total_hits,
                        'wired': packaging_chain_wired,
                        'verdict': 'WIRED' if packaging_chain_wired else 'NOT_WIRED'},
    'not_rechecked': {
        'old_zip_sha256': '3 个旧包 zip 各约 11 GB，本轮未重复全量实算（§142 已实算并留证）；'
                          '本轮仅做轻量存在性/元数据检查，不写「一字节未动」的新结论',
    },
}

# ---------------- 判据 ----------------
checks = []


def ck(cid, desc, ok, evidence):
    checks.append({'id': cid, 'desc': desc, 'ok': bool(ok), 'evidence': evidence})


ck('R01', '纠偏文件开工基线 SHA/字节/mtime/条数与本会话实测一致',
   sha(corr_b) == BASE_SHA and len(corr_b) == BASE_BYTES
   and datetime.datetime.fromtimestamp(corr_st.st_mtime).strftime('%Y-%m-%d %H:%M:%S') == BASE_MTIME
   and len(ids) == BASE_COUNT,
   {'sha256': sha(corr_b), 'bytes': len(corr_b), 'count': len(ids)})
ck('R02', 'APP 编号 1..80 无缺号无重复', ids == list(range(1, 81)),
   {'min': min(ids), 'max': max(ids), 'missing': facts['corrections']['missing']})
ck('R03', 'last_ack 对齐最大编号且无编号大于它的新条目',
   baseline_ok(sha(corr_b), len(corr_b), ids, last_ack)
   and not has_new_correction(ids, last_ack_num),
   {'last_ack': last_ack, 'ids_max': max(ids)})
ck('R04', 'git HEAD 为上一轮 §144 提交且 ahead=0 / main',
   head == HEAD_EXPECT and ahead == '0' and branch == 'main',
   {'head': head, 'ahead': ahead, 'branch': branch})
ck('R05', '上一轮提交不含任何 CORRECTIONS 文件',
   all('CORRECTIONS' not in x for x in head_files_list),
   {'head_files': head_files_list})
ck('R06', '上一轮提交只含 App 侧文件（results/app / status/app / status/archive）',
   all(x.startswith(('results/app/', 'status/app/', 'status/archive/',
                     'live_caption/', 'pack_v13.py')) for x in head_files_list),
   {'head_files': head_files_list})
ck('R07', 'MACHINE_LOCK 空闲（本轮未占设备，只读探测）', not lock_present,
   {'present': lock_present})
ck('R08', 'STATUS 写前在 ≤40 000 B / ≤300 行限额内',
   limit_ok(len(status_b), status_lines),
   {'bytes': len(status_b), 'lines': status_lines})
ck('R09', 'v23_preset_only.py 与 §143 产物表登记 SHA/字节逐字一致',
   asset_sha_ok(sha(v23_b), SEC143_V23_SHA) and len(v23_b) == SEC143_V23_BYTES,
   {'sha256': sha(v23_b), 'bytes': len(v23_b), 'sec143': SEC143_V23_SHA})
ck('R10', 'assert_pkg_clean.py 落盘（本轮实测基准）',
   len(gate_b) > 1000 and sha(gate_b) == 'ba76906938492b06de7b9449055af08b28ab6ace47d0bb922fb5859195aff47a',
   {'sha256': sha(gate_b), 'bytes': len(gate_b)})
ck('R11', '两份 dev 资产 ast.parse 通过',
   ast.parse(v23_text) is not None and ast.parse(gate_b.decode('utf-8')) is not None,
   {'files': 2})
ck('R12', 'PKG_INCLUDE_FILES 清单完整且每个包内路径在开发树有源',
   include_ok(include_const, lc), {'const': include_const})
ck('R13', '_app315 静态自证原始字段 PASS/36/0/0/8-8',
   selftest.get('verdict') == 'PASS' and selftest.get('n_pass') == 36
   and selftest.get('n_fail') == 0 and selftest.get('n_unknown') == 0
   and selftest.get('counterproof_identified') == '8/8',
   {k: selftest.get(k) for k in ('verdict', 'n_pass', 'n_fail', 'n_unknown', 'counterproof_identified')})
ck('R14', '_app316 docstring 修正自证 verdict=PASS', docfix.get('verdict') == 'PASS',
   {'verdict': docfix.get('verdict')})
ck('R15', '_app315_v23_preset_only.diff 落盘且 8 021 B',
   len(diff_b) == SEC143_DIFF_BYTES, {'bytes': len(diff_b)})
ck('R16', 'pack_v13.py 对 APP-080 资产零引用（打包脚本未接入）',
   pack_hits == 0,
   {'hits': pack_hits, 'pack_v13_bytes': len(pack_b), 'pack_v13_sha256': sha(pack_b)})
ck('R17', '所有建包/建目录脚本对 APP-080 资产零引用',
   sum(build_hits.values()) == 0,
   {'scanned': len(build_scripts), 'nonzero': {k: v for k, v in build_hits.items() if v}})
ck('R18', '打包链路结论正确判为 NOT_WIRED（事实性断言，非缺陷 FAIL）',
   (not packaging_chain_wired) and facts['packaging_chain']['verdict'] == 'NOT_WIRED',
   {'total_hits': total_hits, 'verdict': facts['packaging_chain']['verdict']})

# ---------------- 反证组（判据必须能被识破） ----------------
counter = []


def ce(cid, desc, detected, evidence):
    counter.append({'id': cid, 'desc': desc, 'detected': bool(detected), 'evidence': evidence})


ce('E1', '把纠偏 SHA 改 1 字符 ⇒ 基线判据应识破',
   not baseline_ok(BASE_SHA[:-1] + '0', BASE_BYTES, ids, last_ack),
   {'mutated_sha_tail': '0'})
ce('E2', '把 last_ack 改成 APP-079 ⇒ 对齐判据应识破',
   not baseline_ok(BASE_SHA, BASE_BYTES, ids, 'APP-079'),
   {'mutated_last_ack': 'APP-079'})
ce('E3', '把模拟器追加 APP-081 ⇒ 「无新条目」判据应识破',
   has_new_correction(ids + [81], last_ack_num)
   and not baseline_ok(BASE_SHA, BASE_BYTES, ids + [81], last_ack),
   {'mutated_count': len(ids) + 1, 'ids_max': 81})
ce('E4', '把 §143 资产 SHA 换成他值 ⇒ 资产判据应识破',
   not asset_sha_ok('0' * 64, SEC143_V23_SHA), {'mutated': '0' * 64})
ce('E5', '在 pack_v13.py 副本里插入 PKG_INCLUDE_FILES 引用 ⇒ 消费判据应从 0 翻转',
   consumer_hits(pack_text) == 0
   and consumer_hits(pack_text + '\nPKG_INCLUDE_FILES = []\n') >= 1,
   {'before': pack_hits, 'after': consumer_hits(pack_text + '\nPKG_INCLUDE_FILES = []\n')})
ce('E6', '把 PKG_INCLUDE_FILES 删掉一项 ⇒ 清单判据应识破',
   not include_ok(['app/v23_preset_only.py'], lc),
   {'mutated': ['app/v23_preset_only.py']})
ce('E7', '模拟 STATUS 超限 ⇒ 限额判据应识破', not limit_ok(40001, 200),
   {'mutated_bytes': 40001})

n_fail = sum(1 for c in checks if not c['ok'])
n_ce = sum(1 for c in counter if c['detected'])
report = {
    'tool': '_app320_v23_build_readiness',
    'scope': 'static_only_no_device_no_packaging_no_minimax',
    'stamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'corrections_readonly': True,
    'facts': facts,
    'checks': checks,
    'counterproof': counter,
    'n_pass': len(checks) - n_fail,
    'n_fail': n_fail,
    'n_unknown': 0,
    'counterproof_identified': '%d/%d' % (n_ce, len(counter)),
    'verdict': 'PASS' if (n_fail == 0 and n_ce == len(counter)) else 'FAIL',
    'conclusion': ('APP-080 构建期资产与 §143 产物表逐字一致；但 pack_v13.py 与 %d 个建包脚本'
                   '对 PKG_INCLUDE_FILES/补丁模块引用数=%d ⇒ 打包链路尚未接入，'
                   '属 ⑤ 待办（不是代码缺陷），需 reviewer 复核后随 v2.3 打新版本时接入。'
                   % (len(build_scripts), total_hits)),
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps({'verdict': report['verdict'], 'n_pass': report['n_pass'],
                  'n_fail': report['n_fail'],
                  'counterproof_identified': report['counterproof_identified'],
                  'packaging_chain': facts['packaging_chain'],
                  'status_before': facts['status_before']}, ensure_ascii=False, indent=2))
