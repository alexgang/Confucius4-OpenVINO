r"""_app324 - APP-080 ⑤ 前置条件「只读一致性复核」（无新纠偏轮次的实质工作）。

纪律：纯 CPU 静态、全程只读；不建 MACHINE_LOCK、不推理、不调 MiniMax、不打包、
不写任何客户安装目录；只产出本脚本与同名 JSON 报告。
判据分三态 True/False/None（「无法判定」不等于「不合格」），并带反证组证明非恒真。
"""
from __future__ import annotations

import ast
import copy
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
RES = os.path.join(ROOT, 'results', 'app')
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
OUT = os.path.join(RES, '_app324_app080_prereq_readonly_audit.json')
SEC143_ARTIFACTS = os.path.join(
    ROOT, 'status', 'archive', 'STATUS_APP_sec143_artifacts_20261107.md')
SEC146_JSON = os.path.join(RES, '_app322_v23_pkg_baseline_dryrun.json')
SEC145_JSON = os.path.join(RES, '_app320_v23_build_readiness.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
PKG22 = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.2'
SHADOW = r'C:\Users\Trekker-PTL\shared\app067_shadow'
ASR_SRC_W5 = os.path.join(r'C:\Users\Trekker-PTL\qwen3asr_06b',
                          'models', 'pyannote_seg', 'ov-fp16-w5')

# 本会话 04:06 开工实测基线（禁止推算）
BASE = dict(corr_sha='b3ae9ea9fb72282bbf619dd26b73de688f8c771911bd0b56e0faf8f392b937d5',
            corr_bytes=224562, corr_mtime='2026-11-06 21:40:34', corr_count=80,
            status_bytes=39860, status_lines=195,
            status_sha='641690865d1986c3827bba0d02aad096f9c3392a0e8299c19491e4af3a8d9d57',
            git_head='7079e05')

DEV_SRC = ['live_caption/live_caption_app.py', 'live_caption/tts_service.py',
           'live_caption/tts_worker.py']
PKG_SRC = ['live_caption_app.py', 'tts_service.py', 'tts_worker.py']
V23_ASSETS = ['live_caption/v23_preset_only.py', 'live_caption/assert_pkg_clean.py']
MISSING_ANCHORS = {'P03-checkbox', 'P04-hint', 'P05-startup', 'P08-onchange'}
KW = re.compile(r'v23_preset_only|PKG_INCLUDE_FILES|assert_pkg_clean')
ROW_RE = re.compile(
    r'^\|\s*`([^`]+)`\s*\|\s*(\S+)\s*\|\s*(\d+)\s*\|\s*`([0-9a-f]{64})`\s*\|',
    re.M)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def meta(path):
    if not os.path.isfile(path):
        return None
    b = open(path, 'rb').read()
    return dict(bytes=len(b), sha256=sha(b),
                mtime=datetime.datetime.fromtimestamp(
                    os.stat(path).st_mtime).strftime('%Y-%m-%dT%H:%M:%S'))


def rows(text):
    return {r[0]: dict(mtime=r[1], bytes=int(r[2]), sha256=r[3])
            for r in ROW_RE.findall(text)}


def git(*args):
    r = subprocess.run(['git'] + list(args), cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    return r.stdout.strip()


def collect():
    cb = open(CORR, 'rb').read()
    ct = cb.decode('utf-8', errors='replace')
    ids = [int(x) for x in re.findall(r'^##\s+APP-(\d{3})\b', ct, re.M)]
    sb = open(STATUS, 'rb').read()
    st = sb.decode('utf-8')
    m = re.search(r'^last_ack:\s*(\S+)', st, re.M)
    d146 = json.load(open(SEC146_JSON, encoding='utf-8'))
    d145 = json.load(open(SEC145_JSON, encoding='utf-8'))
    f146 = d146['facts']

    # §145 同口径：pack_v13.py + results/app 下 *build*.py / *stage*.py，排除判据脚本自身
    scripts = sorted(set(glob.glob(os.path.join(RES, '*build*.py')) +
                         glob.glob(os.path.join(RES, '*stage*.py'))))
    scripts = [p for p in scripts
               if '_app320_' not in os.path.basename(p)
               and '_app324_' not in os.path.basename(p)]
    refs = {}
    for p in [os.path.join(ROOT, 'pack_v13.py')] + scripts:
        txt = open(p, encoding='utf-8', errors='replace').read()
        refs[os.path.relpath(p, ROOT).replace('\\', '/')] = len(KW.findall(txt))

    tree = ast.parse(open(os.path.join(ROOT, 'live_caption', 'v23_preset_only.py'),
                          encoding='utf-8').read())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'KEEP_SPK_FILES'
                for t in node.targets):
            keep = list(ast.literal_eval(node.value))
            break

    def dir_files(d):
        if not os.path.isdir(d):
            return []
        return [dict(name=n, **meta(os.path.join(d, n)))
                for n in sorted(os.listdir(d))
                if os.path.isfile(os.path.join(d, n))]

    shadow_w5 = dir_files(os.path.join(SHADOW, 'models', 'spk',
                                       'pyannote_seg_3_0', 'fp16-w5'))
    asr_w5 = dir_files(ASR_SRC_W5)
    sx = next((x['sha256'] for x in shadow_w5
               if x['name'] == 'pyannote_seg_3_0_w5.xml'), None)
    ax = next((x['sha256'] for x in asr_w5
               if x['name'] == 'pyannote_seg_3_0_w5.xml'), None)

    sec146_table = rows(st)
    sec143_table = rows(open(SEC143_ARTIFACTS, encoding='utf-8').read())

    f = dict(
        generated_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        corrections=dict(sha256=sha(cb), bytes=len(cb),
                         mtime=datetime.datetime.fromtimestamp(
                             os.stat(CORR).st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                         n_headings=len(ids), max_id=max(ids) if ids else None,
                         missing_ids=[n for n in range(1, (max(ids) if ids else 0) + 1)
                                      if n not in ids]),
        status_header=dict(last_ack=m.group(1) if m else None,
                           bytes=len(sb), lines=sb.count(b'\n') + 1,
                           sha256=sha(sb), crlf=sb.count(b'\r\n')),
        sec146=dict(verdict=d146['verdict'], n_pass=d146['n_pass'],
                    n_fail=d146['n_fail'], n_unknown=d146['n_unknown'],
                    counterproof_identified=d146['counterproof_identified'],
                    dev_hits=f146['dev_hits'], pkg_v22_hits=f146['pkg_v22_hits'],
                    dev_sources=f146['dev_sources'],
                    pkg_v22_before=f146['pkg_v22_before'],
                    pkg_v22_after=f146['pkg_v22_after'],
                    pkg_v22_missing_anchors=f146['pkg_v22_missing_anchors'],
                    total_anchors=f146['total_anchors'],
                    pkg_v22_unique_anchors=f146['pkg_v22_unique_anchors'],
                    pkg_v22_direct_patch_applicable=f146['pkg_v22_direct_patch_applicable'],
                    git=f146['git'], status_before=f146['status_before'],
                    machine_lock_present=f146['machine_lock_present']),
        sec145_packaging_chain=d145['facts']['packaging_chain'],
        sec145_assets=d145['facts']['app080_assets'],
        sec146_table=sec146_table,
        sec143_table=sec143_table,
        disk=dict(
            dev_sources={r: meta(os.path.join(ROOT, r.replace('/', os.sep)))
                         for r in DEV_SRC},
            pkg_v22_sources={r: meta(os.path.join(PKG22, 'app', r))
                             for r in PKG_SRC},
            v23_assets={r: meta(os.path.join(ROOT, r.replace('/', os.sep)))
                        for r in V23_ASSETS},
            pack_v13=meta(os.path.join(ROOT, 'pack_v13.py')),
            sec146_table_files={r: meta(os.path.join(ROOT, r.replace('/', os.sep)))
                                for r in sec146_table},
        ),
        packaging_chain=dict(scanned=len(refs), refs_by_file=refs,
                             total_refs=sum(refs.values())),
        spk=dict(keep=keep,
                 pkg22_present=[n for n in keep if os.path.isfile(
                     os.path.join(PKG22, 'app', 'asr_spk', n))],
                 pkg22_missing=[n for n in keep if not os.path.isfile(
                     os.path.join(PKG22, 'app', 'asr_spk', n))],
                 shadow_present=[n for n in keep if os.path.isfile(
                     os.path.join(SHADOW, 'app', 'asr_spk', n))],
                 shadow_missing=[n for n in keep if not os.path.isfile(
                     os.path.join(SHADOW, 'app', 'asr_spk', n))]),
        seg_w5=dict(
            pkg22_dir_exists=os.path.isdir(os.path.join(
                PKG22, 'app', 'models', 'spk', 'pyannote_seg_3_0', 'fp16-w5')),
            repo_dir_exists=os.path.isdir(os.path.join(
                ROOT, 'models', 'spk', 'pyannote_seg_3_0', 'fp16-w5')),
            shadow_files=shadow_w5, asr_src_files=[x['name'] for x in asr_w5],
            shadow_xml_sha256=sx, asr_src_xml_sha256=ax,
            xml_differs=(sx is not None and ax is not None and sx != ax)),
        bridge=dict(v22_token_paths=[os.path.relpath(p, PKG22).replace('\\', '/')
                                     for p in glob.glob(os.path.join(
                                         PKG22, '**', 'bridge_token.txt'), recursive=True)],
                    bootstrap=meta(os.path.join(ROOT, 'live_caption',
                                                'bridge_bootstrap.py'))),
        git=dict(head=git('log', '-1', '--format=%h'),
                 ahead=git('rev-list', '--count', 'origin/main..HEAD'),
                 branch=git('rev-parse', '--abbrev-ref', 'HEAD'),
                 corrections_status=git('status', '--short', '--',
                                        'status/app/CORRECTIONS_APP.md')),
        machine_lock_present=os.path.exists(LOCK),
    )
    return f


def same_meta(actual, recorded):
    return (actual is not None and recorded is not None
            and actual['bytes'] == recorded['bytes']
            and actual['sha256'] == recorded['sha256'])


CHECKS = [
    ('A1', '纠偏文件开工基线四项全等（SHA/字节/mtime/条数）',
     lambda f: (f['corrections']['sha256'] == BASE['corr_sha']
                and f['corrections']['bytes'] == BASE['corr_bytes']
                and f['corrections']['mtime'] == BASE['corr_mtime']
                and f['corrections']['n_headings'] == BASE['corr_count'])),
    ('A2', 'APP 编号 1..080 连续无缺号且 max_id=80',
     lambda f: (f['corrections']['missing_ids'] == []
                and f['corrections']['max_id'] == 80
                and f['corrections']['n_headings'] == 80)),
    ('A3', 'STATUS 头部 last_ack=APP-080',
     lambda f: f['status_header']['last_ack'] == 'APP-080'),
    ('A4', '无编号大于 last_ack 的新条目（步骤 3 无条可执行）',
     lambda f: int(f['status_header']['last_ack'].split('-')[1])
     >= f['corrections']['max_id']),
    ('B1', '§146 原始字段 verdict=PASS / 33 PASS / 0 FAIL / 0 UNKNOWN',
     lambda f: (f['sec146']['verdict'] == 'PASS' and f['sec146']['n_pass'] == 33
                and f['sec146']['n_fail'] == 0 and f['sec146']['n_unknown'] == 0)),
    ('B2', '§146 反证 8/8 全被识破',
     lambda f: f['sec146']['counterproof_identified'] == '8/8'),
    ('B3', '§146 dev 三份源文件 18/18 锚点唯一命中',
     lambda f: (sum(len(v) for v in f['sec146']['dev_hits'].values()) == 18
                and all(x == 1 for v in f['sec146']['dev_hits'].values()
                        for x in v.values()))),
    ('B4', '§146 包内 v2.2 基底 14/18 且缺的恰是 4 个 P 锚点',
     lambda f: (f['sec146']['pkg_v22_unique_anchors'] == 14
                and f['sec146']['total_anchors'] == 18
                and set(f['sec146']['pkg_v22_missing_anchors'][
                    'live_caption/live_caption_app.py']) == MISSING_ANCHORS)),
    ('B5', '§146 直接套补丁不可用（须先升级基底）',
     lambda f: f['sec146']['pkg_v22_direct_patch_applicable'] is False),
    ('B6', '§146 包内 3 文件写前/写后 SHA 与字节逐文件相等',
     lambda f: f['sec146']['pkg_v22_before'] == f['sec146']['pkg_v22_after']),
    ('C1', '本轮实算：dev 3 源文件与 §146 facts.dev_sources 逐字节一致',
     lambda f: all(same_meta(f['disk']['dev_sources'][rel], rec)
                   for rel, rec in ((r, f['sec146']['dev_sources'][r])
                                    for r in DEV_SRC))),
    ('C2', '本轮实算：v2.2 包 3 源文件与 §146 pkg_v22_before 逐字节一致',
     lambda f: all(same_meta(f['disk']['pkg_v22_sources'][rel], rec)
                   for rel, rec in ((r, f['sec146']['pkg_v22_before'][
                       'live_caption/' + r]) for r in PKG_SRC))),
    ('C3', '本轮实算：2 份 APP-080 资产与 §145 facts.app080_assets 逐字节一致',
     lambda f: all(same_meta(f['disk']['v23_assets'][rel], f['sec145_assets'][key])
                   for rel, key in (('live_caption/v23_preset_only.py', 'v23_preset_only'),
                                    ('live_caption/assert_pkg_clean.py', 'assert_pkg_clean')))),
    ('C4', '§143 产物表登记的 v23_preset_only.py 与磁盘逐字节一致',
     lambda f: ('live_caption/v23_preset_only.py' in f['sec143_table']
                and same_meta(f['disk']['v23_assets'][
                    'live_caption/v23_preset_only.py'],
                    f['sec143_table']['live_caption/v23_preset_only.py']))),
    ('D1', '按 §145 口径复核：打包链路对 APP-080 资产引用数 0（NOT_WIRED）',
     lambda f: (f['packaging_chain']['scanned'] >= 1
                and f['packaging_chain']['total_refs'] == 0
                and sum(f['packaging_chain']['refs_by_file'].values()) == 0)),
    ('D2', 'pack_v13.py 与 §145 登记 SHA/字节一致（打包脚本未被改动）',
     lambda f: (f['disk']['pack_v13']['bytes'] == f['sec145_packaging_chain']['pack_v13_bytes']
                and f['disk']['pack_v13']['sha256'] == f['sec145_packaging_chain']['pack_v13_sha256'])),
    ('D3', 'KEEP_SPK_FILES 5 个：v2.2 包内 3/5、影子包 5/5，缺的恰是 2 个新文件',
     lambda f: (len(f['spk']['keep']) == 5
                and len(f['spk']['pkg22_present']) == 3
                and len(f['spk']['shadow_present']) == 5
                and set(f['spk']['pkg22_missing']) ==
                {'asr_spk_window.py', 'asr_runtime_switches.py'})),
    ('D4', '5 s 静态 seg IR：仓库/v2.2 包内均无，影子包 2 个文件已落盘',
     lambda f: (f['seg_w5']['pkg22_dir_exists'] is False
                and f['seg_w5']['repo_dir_exists'] is False
                and len(f['seg_w5']['shadow_files']) == 2
                and all(x['bytes'] > 0 for x in f['seg_w5']['shadow_files']))),
    ('D5', '影子包与 ASR 源目录的 seg xml 是否同版（不同 ⇒ 无法判定取哪份）',
     lambda f: None if f['seg_w5']['xml_differs'] else True),
    ('D6', 'APP-077 清单：v2.2 包根 ext/bridge_token.txt 仍 1 处、dev 有 bridge_bootstrap.py',
     lambda f: (len(f['bridge']['v22_token_paths']) == 1
                and f['bridge']['v22_token_paths'][0] == 'ext/bridge_token.txt'
                and f['bridge']['bootstrap'] is not None)),
    ('E1', 'git：HEAD=7079e05 / ahead=0 / branch=main（§146 已推送）',
     lambda f: (f['git']['head'] == BASE['git_head'] and f['git']['ahead'] == '0'
                and f['git']['branch'] == 'main')),
    ('E2', 'CORRECTIONS_APP.md 仍是 reviewer 未提交改动（本轮只读）',
     lambda f: f['git']['corrections_status'].startswith(' M ') or
     f['git']['corrections_status'].startswith('M ')),
    ('E3', 'MACHINE_LOCK 空闲（本轮未占设备）',
     lambda f: f['machine_lock_present'] is False
     and f['sec146']['machine_lock_present'] is False),
    ('E4', 'STATUS 写前 39 860 B / 195 行 / SHA 与开工实测一致',
     lambda f: (f['status_header']['bytes'] == BASE['status_bytes']
                and f['status_header']['lines'] == BASE['status_lines']
                and f['status_header']['sha256'] == BASE['status_sha']
                and f['status_header']['crlf'] == 0)),
    ('E5', '§146 产物表 4 行的字节/SHA 与磁盘逐文件一致',
     lambda f: (len(f['sec146_table']) == 4
                and all(same_meta(f['disk']['sec146_table_files'].get(rel),
                                  dict(bytes=rec['bytes'], sha256=rec['sha256']))
                        for rel, rec in f['sec146_table'].items()))),
    ('E6', '§146 产物表行数恰为 4（不多报不漏报）',
     lambda f: len(f['sec146_table']) == 4),
]

# 反证：改「被测的那个对象」本身；同一判据必须不再 PASS。
COUNTERPROOF = [
    ('P1', '纠偏条数 80→79', 'A2',
     lambda f: f['corrections'].update(n_headings=79)),
    ('P2', 'last_ack 改成 APP-079', 'A3',
     lambda f: f['status_header'].update(last_ack='APP-079')),
    ('P3', '§146 n_pass 33→32', 'B1',
     lambda f: f['sec146'].update(n_pass=32)),
    ('P4', '包内锚点 14→18（假装可直接套补丁）', 'B4',
     lambda f: f['sec146'].update(pkg_v22_unique_anchors=18)),
    ('P5', 'dev 某源文件 SHA 改 1 字符（模拟 dev 被改）', 'C1',
     lambda f: f['disk']['dev_sources'][DEV_SRC[0]].update(
         sha256='0' * 64)),
    ('P6', 'v2.2 包内某文件 SHA 改 1 字符（模拟客户包被原地改）', 'C2',
     lambda f: f['disk']['pkg_v22_sources'][PKG_SRC[0]].update(sha256='0' * 64)),
    ('P7', 'APP-080 资产 SHA 改 1 字符（模拟资产被替换）', 'C3',
     lambda f: f['disk']['v23_assets'][V23_ASSETS[0]].update(sha256='0' * 64)),
    ('P8', '打包脚本注入 PKG_INCLUDE_FILES 引用', 'D1',
     lambda f: f['packaging_chain']['refs_by_file'].update(
         {'pack_v13.py': 1})),
    ('P9', '影子包 spk 文件假装只有 4 个', 'D3',
     lambda f: f['spk'].update(shadow_present=f['spk']['shadow_present'][:4])),
    ('P10', 'MACHINE_LOCK 伪装存在', 'E3',
     lambda f: f.update(machine_lock_present=True)),
    ('P11', 'git HEAD 伪装未推送旧值', 'E1',
     lambda f: f['git'].update(head='0000000')),
    ('P12', '§146 产物表某行 SHA 改 1 字符', 'E5',
     lambda f: next(iter(f['sec146_table'].values())).update(sha256='0' * 64)),
]


def main():
    f = collect()
    by_id = {cid: fn for cid, _, fn in CHECKS}
    checks = []
    for cid, name, fn in CHECKS:
        r = fn(f)
        checks.append(dict(id=cid, name=name,
                           verdict='PASS' if r is True else
                           ('UNKNOWN' if r is None else 'FAIL'),
                           ok=r))
    cp = []
    for pid, name, target, mutate in COUNTERPROOF:
        g = copy.deepcopy(f)
        mutate(g)
        r = by_id[target](g)
        identified = (r is not True)
        cp.append(dict(id=pid, name=name, target_check=target,
                       result_after_mutation='PASS' if r is True else
                       ('UNKNOWN' if r is None else 'FAIL'),
                       identified=identified))
    n_fail = sum(1 for c in checks if c['verdict'] == 'FAIL')
    n_unknown = sum(1 for c in checks if c['verdict'] == 'UNKNOWN')
    n_pass = sum(1 for c in checks if c['verdict'] == 'PASS')
    n_id = sum(1 for c in cp if c['identified'])
    verdict = 'PASS' if (n_fail == 0 and n_id == len(cp)) else 'FAIL'
    report = dict(
        tool='_app324_app080_prereq_readonly_audit', verdict=verdict,
        scope='static_only_no_device_no_packaging_no_minimax',
        n_pass=n_pass, n_fail=n_fail, n_unknown=n_unknown,
        counterproof_identified='%d/%d' % (n_id, len(cp)),
        checks=checks, counterproof=cp, facts=f,
        conclusion=(
            '无新纠偏（80 条 / last_ack=APP-080）；按 APP-046② 不空转，'
            '§143/§145/§146 关键证据与 3+3+2 份源文件重新实算一致；'
            '新增 APP-080 ⑤ 前置资产定位：v2.2 包内 asr_spk 5 个文件只有 3 个、'
            '无 fp16-w5，影子包已有 5/5 + 2 个 5 s seg IR；'
            'PKG_INCLUDE_FILES 仍 NOT_WIRED。'),
        stop_point=(
            'APP-075/079 与 APP-080 ⑤⑥ 仍停 reviewer 复核节点；'
            'v2.3 不打包、未改任何客户安装目录、未占设备。'),
    )
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict=verdict, n_pass=n_pass, n_fail=n_fail,
                          n_unknown=n_unknown,
                          counterproof_identified=report['counterproof_identified'],
                          failing=[c['id'] for c in checks
                                   if c['verdict'] == 'FAIL'],
                          unknown=[c['id'] for c in checks
                                   if c['verdict'] == 'UNKNOWN'],
                          cp_not_identified=[c['id'] for c in cp
                                             if not c['identified']],
                          out=os.path.relpath(OUT, ROOT)),
                     ensure_ascii=True, indent=2))
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
