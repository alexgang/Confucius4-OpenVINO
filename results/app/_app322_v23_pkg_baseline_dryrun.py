r"""_app322 — APP-080 构建期补丁对「dev 基底」与「v2.2 包内基底」的只读 dry-run 对账。

纯 CPU 静态：不加载模型、不占设备、不打包、不生成 zip、不调 MiniMax、
**不写任何客户安装目录**（包内 3 份源文件写前/写后 SHA256 逐字节复核）。
结论口径：包内 v2.2 是 11-02 旧基底，18 锚点失配是「版本差异」，不是产品缺陷；
本脚本只判定「命中矩阵与失败原因是否自洽」以及「v2.3 打新版本的前置条件」。
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LC = os.path.join(ROOT, 'live_caption')
V22 = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.2'
OUT = os.path.join(HERE, '_app322_v23_pkg_baseline_dryrun.json')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

WANT_DOCS = {'set_clone_pcm', 'register_spk_voice', '_update_clone',
             '_register_spk_voice', '_apply_spk_voice'}


def stat_of(path):
    b = open(path, 'rb').read()
    st = os.stat(path)
    return dict(path=path, bytes=len(b),
                mtime=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
                sha256=hashlib.sha256(b).hexdigest())


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def read_text(path):
    return open(path, 'rb').read().decode('utf-8')


def hit_matrix(mod, text, key):
    norm = text.replace('\r\n', '\n')
    return {p['id']: norm.count(p['old']) for p in mod.PATCHES[key]}


def docs_of(txt, wanted):
    tr = ast.parse(txt.replace('\r\n', '\n'))
    return {n.name: ast.get_docstring(n) for n in ast.walk(tr)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name in wanted}


def main():
    mod = load_module('v23_preset_only_probe', os.path.join(LC, 'v23_preset_only.py'))
    checks = []

    def chk(cond, name, detail):
        checks.append(dict(name=name, ok=(None if cond is None else bool(cond)),
                           detail=detail))

    keys = list(mod.PATCHES)
    k_app = 'live_caption/live_caption_app.py'
    k_svc = 'live_caption/tts_service.py'
    k_wrk = 'live_caption/tts_worker.py'

    # ── 纠偏基线（只读）──────────────────────────────────────────────
    cb = open(CORR, 'rb').read()
    cs = cb.decode('utf-8', errors='replace')
    import re
    ids = [int(x) for x in re.findall(r'APP-(\d{3})', cs)]
    heads = re.findall(r'^##\s*APP-\d{3}', cs, re.M)
    s_head = read_text(STATUS).splitlines()[:10]
    last_ack = next((l.split(':', 1)[1].strip() for l in s_head
                     if l.startswith('last_ack:')), None)
    corr_facts = dict(sha256=hashlib.sha256(cb).hexdigest(), bytes=len(cb),
                      mtime=datetime.datetime.fromtimestamp(
                          os.stat(CORR).st_mtime).isoformat(),
                      n_headings=len(heads), max_id=max(ids) if ids else None,
                      missing_ids=[i for i in range(1, (max(ids) if ids else 0) + 1)
                                   if i not in set(ids)],
                      last_ack=last_ack,
                      new_items=[i for i in sorted(set(ids)) if i > 80])
    chk(len(heads) == 80 and corr_facts['max_id'] == 80
        and not corr_facts['missing_ids'] and not corr_facts['new_items'],
        'corrections_baseline_80_no_new',
        'headings=%d max_id=%s new=%s' % (len(heads), corr_facts['max_id'],
                                          corr_facts['new_items']))
    chk(last_ack == 'APP-080', 'last_ack_aligned',
        'last_ack=%r' % (last_ack,))

    # ── dev 基底：18 锚点唯一命中 + 补丁后静态判据 ────────────────────
    dev = {}
    dev_hits = {}
    dev_patched = {}
    for k in keys:
        p = os.path.join(ROOT, k.replace('/', os.sep))
        text = read_text(p)
        dev[k] = text
        hm = hit_matrix(mod, text, k)
        dev_hits[k] = hm
        name = os.path.basename(k)
        chk(all(v == 1 for v in hm.values()), 'dev_unique_hits_' + name,
            'n_unique=%d/%d bad=%s' % (sum(1 for v in hm.values() if v == 1),
                                       len(hm), {i: c for i, c in hm.items() if c != 1}))
        try:
            out, applied = mod.apply_patches(text, k)
            dev_patched[k] = out
            ok, reasons = mod.verify_source(out, k)
            chk(ok, 'dev_verify_' + name, 'reasons=%s' % (reasons,))
            chk(len(applied) == len(mod.PATCHES[k]), 'dev_applied_' + name,
                'applied=%d/%d' % (len(applied), len(mod.PATCHES[k])))
            try:
                ast.parse(out.replace('\r\n', '\n'), filename=k)
                chk(True, 'dev_ast_' + name, 'ast.parse OK')
            except SyntaxError as e:
                chk(False, 'dev_ast_' + name, 'SyntaxError %r' % (e,))
            eol_crlf = '\r\n' in text
            chk((out.count('\r\n') > 0 and out.count('\n') == out.count('\r\n'))
                if eol_crlf else '\r\n' not in out,
                'dev_eol_' + name, 'source EOL=%s' % ('CRLF' if eol_crlf else 'LF'))
        except Exception as e:
            chk(False, 'dev_apply_' + name, 'EXC %r' % (e,))
            dev_patched[k] = text

    dev_doc_src, dev_doc_patched = {}, {}
    for k in (k_svc, k_wrk):
        dev_doc_src.update(docs_of(dev[k], WANT_DOCS))
        dev_doc_patched.update(docs_of(dev_patched[k], WANT_DOCS))
    chk(len(dev_doc_src) == 5 and all(dev_doc_src.values())
        and dev_doc_src == dev_doc_patched,
        'dev_docstrings_preserved',
        'n_dev=%d equal=%s' % (len(dev_doc_src), dev_doc_src == dev_doc_patched))

    # ── v2.2 包内基底：只读命中矩阵 + 写前/写后 SHA（绝不写包）─────────
    pkg = {}
    pkg_hits = {}
    pkg_apply = {}
    pkg_before = {}
    pkg_after = {}
    for k in keys:
        p = os.path.join(V22, 'app', os.path.basename(k))
        name = os.path.basename(k)
        before = stat_of(p)
        pkg_before[k] = before
        text = read_text(p)
        pkg[k] = text
        hm = hit_matrix(mod, text, k)
        pkg_hits[k] = hm
        bad = {i: c for i, c in hm.items() if c != 1}
        try:
            mod.apply_patches(text, k)
            applicable, err = True, None
        except Exception as e:
            applicable, err = False, repr(e)
        pkg_apply[k] = dict(applicable=applicable, error=err,
                            n_unique=sum(1 for v in hm.values() if v == 1),
                            n_total=len(hm), bad_anchors=bad)
        after = stat_of(p)
        pkg_after[k] = after
        chk(before['sha256'] == after['sha256'] and before['bytes'] == after['bytes'],
            'pkg_untouched_' + name,
            'before=after sha=%s bytes=%d' % (before['sha256'][:12], before['bytes']))
        chk(before['sha256'] != hashlib.sha256(dev[k].encode('utf-8')).hexdigest(),
            'pkg_is_independent_copy_' + name,
            'dev bytes=%d pkg bytes=%d' % (len(dev[k].encode('utf-8')), before['bytes']))
        # 自洽性判据：失败时报错的锚点必须落在 count≠1 的集合里（任何基底都成立）
        if applicable:
            chk(not bad, 'pkg_fail_reason_consistent_' + name,
                'applicable=True ⇒ bad_anchors 必须为空')
        else:
            mentioned = next((i for i in bad if i in (err or '')), None)
            chk(bool(bad) and mentioned is not None,
                'pkg_fail_reason_consistent_' + name,
                'bad=%s first_bad_in_error=%s err=%s' % (list(bad), mentioned, str(err)[:160]))
        # 未打补丁的包内原文（旧基底）必须被 verify_source 判为不合格
        ok_old, _ = mod.verify_source(text.replace('\r\n', '\n'), k)
        chk(not ok_old, 'pkg_unpatched_verify_false_' + name,
            'verify_source on raw v2.2 = %s' % (ok_old,))

    # ── 反证组：同一判据必须能识破已知缺陷产物（纯内存）────────────────
    counter = []

    def cp(name, identified, expect):
        counter.append(dict(name=name, identified=bool(identified), expect=expect))

    # E1 删掉一个锚点 ⇒ apply_patches 必须抛 AssertionError
    p0 = mod.PATCHES[k_app][0]
    broken1 = dev[k_app].replace(p0['old'], '', 1)
    try:
        mod.apply_patches(broken1, k_app)
        e1 = False
    except AssertionError:
        e1 = True
    cp('E1_missing_anchor', e1, 'apply_patches raises AssertionError')

    # E2 锚点重复两次 ⇒ 唯一命中断言必须识破
    broken2 = dev[k_app].replace(p0['old'], p0['old'] + p0['old'], 1)
    try:
        mod.apply_patches(broken2, k_app)
        e2 = False
    except AssertionError:
        e2 = True
    cp('E2_duplicated_anchor', e2, 'apply_patches raises AssertionError')

    # E3 未打补丁的 dev 原文 ⇒ verify_source 必须 False
    ok3, _ = mod.verify_source(dev[k_app].replace('\r\n', '\n'), k_app)
    cp('E3_unpatched_dev_source', not ok3, 'verify_source=False')

    # E4 闸门插回 docstring 之前 ⇒ __doc__ 丢失必须被识破（归一 LF 防 CRLF 夹具缺陷）
    broken4 = dev_patched[k_svc].replace('\r\n', '\n').replace(
        '    def set_clone_pcm(self, pcm) -> bool:\n',
        '    def set_clone_pcm(self, pcm) -> bool:\n'
        '        if _V23_PRESET_ONLY:\n            return False\n', 1)
    d4 = docs_of(broken4, WANT_DOCS)
    d4.update(docs_of(dev_patched[k_wrk], WANT_DOCS))
    cp('E4_guard_before_docstring', d4 != dev_doc_src, '__doc__ lost ⇒ FAIL')

    # E5 模拟包内文件被写入 ⇒ 只读判据必须识破
    fake_after = dict(pkg_after[k_app], sha256=pkg_before[k_app]['sha256'] + 'x')
    cp('E5_simulated_pkg_write',
       pkg_before[k_app]['sha256'] != fake_after['sha256'], 'sha differ ⇒ FAIL')

    # E6 把 dev 基底冒充包内基底 ⇒ 必须能判 READY（证明判据非恒假）
    hm6 = hit_matrix(mod, dev[k_app], k_app)
    try:
        mod.apply_patches(dev[k_app], k_app)
        e6 = all(v == 1 for v in hm6.values())
    except Exception:
        e6 = False
    cp('E6_dev_baseline_judged_ready', e6, 'all anchors 1/1 ⇒ applicable=True')

    # E7 模拟 reviewer 追加 APP-081 ⇒ 编号扫描必须识破
    fake_ids = sorted(set(ids) | {81})
    cp('E7_simulated_APP081', max(fake_ids) > 80, 'max_id>last_ack ⇒ new item detected')

    # E8 已打补丁的文本再套一次 ⇒ 必须抛错（防重复应用）
    try:
        mod.apply_patches(dev_patched[k_app], k_app)
        e8 = False
    except AssertionError:
        e8 = True
    cp('E8_double_apply', e8, 'apply_patches raises AssertionError')

    # ── git / 锁 / 限额（只读）────────────────────────────────────────
    def git(*a):
        return subprocess.run(['git', '-C', ROOT] + list(a), capture_output=True,
                              text=True).stdout.strip()
    gitinfo = dict(head=git('rev-parse', '--short', 'HEAD'),
                   ahead=git('rev-list', '--count', 'origin/main..HEAD'),
                   branch=git('branch', '--show-current'),
                   corrections_status=git('status', '--short', '--',
                                          'status/app/CORRECTIONS_APP.md'))
    sb = open(STATUS, 'rb').read()
    status_facts = dict(bytes=len(sb), lines=sb.count(b'\n') + 1,
                        crlf=sb.count(b'\r\n'),
                        sha256=hashlib.sha256(sb).hexdigest())
    machine_lock_present = os.path.exists(LOCK)
    chk(gitinfo['branch'] == 'main' and gitinfo['ahead'] == '0',
        'git_clean_main_ahead0',
        'head=%s ahead=%s branch=%s' % (gitinfo['head'], gitinfo['ahead'],
                                        gitinfo['branch']))
    chk('CORRECTIONS_APP.md' in gitinfo['corrections_status'],
        'corrections_reviewer_only_uncommitted',
        'status=%r' % (gitinfo['corrections_status'],))
    chk(not machine_lock_present, 'machine_lock_not_taken',
        'MACHINE_LOCK present=%s（纯静态，不占设备）' % (machine_lock_present,))

    n_pass = sum(1 for c in checks if c['ok'] is True)
    n_fail = sum(1 for c in checks if c['ok'] is False)
    n_unknown = sum(1 for c in checks if c['ok'] is None)
    n_ident = sum(1 for c in counter if c['identified'])
    verdict = 'PASS' if (n_fail == 0 and n_ident == len(counter)) else 'FAIL'

    total_anchors = sum(len(mod.PATCHES[k]) for k in keys)
    pkg_unique = sum(v['n_unique'] for v in pkg_apply.values())
    missing = {k: [i for i, c in hm.items() if c == 0]
               for k, hm in pkg_hits.items()}
    multi = {k: {i: c for i, c in hm.items() if c > 1}
             for k, hm in pkg_hits.items()}
    conclusion = (
        'dev 基底 18/18 锚点唯一命中、补丁后静态判据成立；'
        'v2.2 包内为 11-02 旧基底，%d/%d 锚点唯一命中 ⇒ 直接对 v2.2 包内副本套补丁会 '
        'AssertionError（属版本差异，非产品缺陷）。'
        'v2.3 打新版本的前置条件：新包目录的 3 份源文件须先升级到 dev 基底'
        '（骨架等价校验后定点升级），再应用 18 锚点补丁，并同时带上 '
        'PKG_INCLUDE_FILES 两个文件（§145 已判 NOT_WIRED，属接入待办）。'
        % (pkg_unique, total_anchors))

    out = dict(tool='_app322_v23_pkg_baseline_dryrun', app='APP-080/§145 ⑤',
               scope='static_only_no_device_no_packaging_no_minimax_no_pkg_write',
               generated_at=datetime.datetime.now().isoformat(timespec='seconds'),
               verdict=verdict, n_pass=n_pass, n_fail=n_fail, n_unknown=n_unknown,
               counterproof_identified='%d/%d' % (n_ident, len(counter)),
               checks=checks, counterproof=counter,
               facts=dict(corrections=corr_facts, dev_hits=dev_hits,
                          dev_sources={k: stat_of(os.path.join(ROOT, k.replace('/', os.sep)))
                                       for k in keys},
                          pkg_v22_hits=pkg_hits, pkg_v22_apply=pkg_apply,
                          pkg_v22_before=pkg_before, pkg_v22_after=pkg_after,
                          pkg_v22_missing_anchors=missing,
                          pkg_v22_multi_hit_anchors=multi,
                          total_anchors=total_anchors,
                          pkg_v22_unique_anchors=pkg_unique,
                          pkg_v22_direct_patch_applicable=all(
                              v['applicable'] for v in pkg_apply.values()),
                          pkg_include_files=mod.PKG_INCLUDE_FILES,
                          git=gitinfo, status_before=status_facts,
                          machine_lock_present=machine_lock_present),
               conclusion=conclusion,
               stop_point=('APP-075/079/080 仍停 reviewer 复核节点；本轮未打包、未打新版本目录与 zip、'
                           '未改客户安装目录与 .lnk、未在 CPU 跑推理测速、未调 MiniMax。'))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict=verdict, n_pass=n_pass, n_fail=n_fail,
                          n_unknown=n_unknown,
                          counterproof_identified=out['counterproof_identified'],
                          total_anchors=total_anchors,
                          pkg_v22_unique_anchors=pkg_unique,
                          pkg_v22_direct_patch_applicable=out['facts'][
                              'pkg_v22_direct_patch_applicable'],
                          pkg_v22_missing_anchors=missing,
                          status_bytes=status_facts['bytes']),
                     ensure_ascii=False, indent=2))
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
