#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app563_zip_content_binding_matrix.py —— §205 的鉴别力矩阵。

🔴 **本轮修的真缺陷（交付闸门层）**：
   §204 修的是「**验收证据属于哪个包**」（`acc['pkg']` 必须等于目标包目录）。
   但 **Special MVP 的验收证据里 sha256 出现 0 次**（只有 "28 个 .py，不一致 0 个"
   这类计数）⇒ 出包闸门**对包内容一个字节都没验证** ⇒
   **验收之后再改包（同步新代码 / 手改文件），照样能出包**，
   而验收记录会（不实地）声称这份包已被验收过。
   ⇒ §205：证据必须带 `pkg_content`（验收时逐文件 SHA256），闸门逐条重算比对。

🔴 **鉴别力怎么做的（避免「自证清白」）**：
  · **改前臂**取自 **`git cat-file blob 8b6775d:results/app/_app537_zip_specialmvp.py`**
    的**原文**（§204 那一版，**逐字**）⇒ 用 `ast.get_source_segment` 抽出函数源码
    再 `exec`（**不 import**，避免模块级副作用）⇒ 改前闸门逐字按原样执行；
  · **改后臂**直接跑**磁盘上修好的脚本**的同名函数；
  · 两臂都只读：**不碰任何客户包**（只读 sp2 的绑定范围文件来复制到临时目录），
    **不打 zip**，**不写客户包**，只写自己的证据 JSON。

🔴 **用例（9 行）**：
  T1 改前臂：证据 pkg 指向**根本不存在的目录** + verdict PASS ⇒ **ALLOW**
     ⇒ **证明改前闸门连「包在不在」都不查**（内容验证 = 0 字节）；
  T2 改前臂：sp1 的证据 vs sp2 目标 ⇒ BLOCK（§204 的修复在改前臂里已有，回归护栏）；
  T3 改后臂：sp1 的证据 vs sp2 目标 ⇒ BLOCK（同上，改后仍成立）；
  T4 改后臂：**无 `pkg_content`** 的证据（pkg = 真 sp2）⇒ BLOCK（fail-closed）；
  T5 改后臂：**临时副本里改坏 1 个文件** ⇒ BLOCK（内容已变）；
  T6 改后臂：**临时副本原封不动** ⇒ ALLOW（证明不是一律拦）；
  T7 改后臂：验收后**新增 1 个 .py** ⇒ BLOCK（反向集合校验）；
  T8 改后臂：verdict=FAIL ⇒ BLOCK（回归护栏）；
  T9 改后臂：真 sp2 证据 vs 真 sp2 目录 ⇒ ALLOW（真实链路端到端）。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = r'C:\Users\Trekker-PTL'
SP2 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2')
SP1 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1')
GATE_REL = 'results/app/_app537_zip_specialmvp.py'
BEFORE_COMMIT = '8b6775d'          # §204 那一版（改前的闸门）
ACC_SP2 = os.path.join(HERE, 'app553_specialmvp_sp2_acceptance.json')
ACC_SP1 = os.path.join(HERE, 'app536_specialmvp_acceptance.json')
OUT = os.path.join(HERE, 'app563_zip_content_binding_matrix.json')
COMMON_FNS = ('_norm_pkg', '_verdict_ok', 'check_acceptance',
              'check_release_identity')
NEW_FNS = COMMON_FNS + ('sha256_file', 'check_content_binding')


def blob(rel, commit):
    p = subprocess.run(['git', 'cat-file', 'blob', '%s:%s' % (commit, rel)],
                       cwd=REPO, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('取 blob 失败 %s:%s -> %s'
                           % (commit, rel, p.stderr.decode()[:200]))
    return p.stdout.decode('utf-8')


def load_fns(src, names):
    """从源码**原文**（ast.get_source_segment）抽出函数并 exec ⇒ 不 import。"""
    src = src.replace('\r\n', '\n')
    tree = ast.parse(src)
    ns = {'os': os, 'json': json, 're': __import__('re'), 'hashlib': hashlib,
          'sys': sys, 'RuntimeError': RuntimeError}
    got = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in names:
            seg = ast.get_source_segment(src, n)
            if not seg:
                raise RuntimeError('抽不到 %s 的源码' % n.name)
            exec(compile(seg, '<%s@extract>' % n.name, 'exec'), ns)
            got.append(n.name)
    missing = [x for x in names if x not in got]
    if missing:
        raise RuntimeError('源码里缺函数：%s' % missing)
    return ns


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def run_gate(ns, pkg_dir, accept_path):
    """跑闸门：**只**验「验收」这一步（内容绑定是 §205 新增的那一步）。"""
    try:
        ns['check_acceptance'](pkg_dir, accept_path)
    except Exception as e:
        return False, '%s: %s' % (type(e).__name__, e)
    if 'check_content_binding' in ns:
        try:
            acc = json.load(open(accept_path, encoding='utf-8'))
            ns['check_content_binding'](pkg_dir, acc)
        except Exception as e:
            return False, '%s: %s' % (type(e).__name__, e)
    return True, 'ALLOW'


def main():
    ev = {'script': os.path.basename(__file__),
          'note': '§205 鉴别力矩阵：改前臂＝8b6775d 的闸门原文；改后臂＝磁盘上修好的'
                  '闸门；零写客户包、零 zip',
          'before_commit': BEFORE_COMMIT,
          'rows': []}
    tmp = tempfile.mkdtemp(prefix='app563_')
    try:
        before_src = blob(GATE_REL, BEFORE_COMMIT)
        after_src = open(os.path.join(REPO, GATE_REL), encoding='utf-8').read()
        ev['before_bytes'] = len(before_src)
        ev['after_bytes'] = len(after_src)
        ev['before_has_content_binding'] = 'check_content_binding' in before_src
        ev['after_has_content_binding'] = 'check_content_binding' in after_src
        nb = load_fns(before_src, COMMON_FNS)
        na = load_fns(after_src, NEW_FNS)

        def row(cid, desc, expect, got, why=''):
            ok = (expect == got)
            ev['rows'].append({'id': cid, 'desc': desc, 'expect': expect,
                               'got': got, 'pass': ok, 'why': why})
            print('  %-4s %-58s expect=%-5s got=%-5s %s'
                  % (cid, desc[:58], expect, got, 'OK' if ok else '*** MISMATCH ***'))
            return ok

        print('#' * 78)
        print('# 改前/改后闸门：内容绑定鉴别力')
        print('#' * 78)
        print('  改前臂 = %s 的 %s（%d B，含内容绑定=%s）'
              % (BEFORE_COMMIT, GATE_REL, ev['before_bytes'],
                 ev['before_has_content_binding']))
        print('  改后臂 = 磁盘上的 %s（%d B，含内容绑定=%s）'
              % (GATE_REL, ev['after_bytes'],
                 ev['after_has_content_binding']))

        # ── T1：改前臂 + 证据 pkg 指向**不存在的目录** ⇒ ALLOW（漏洞实锤）──
        ghost = os.path.join(tmp, 'no_such_package_dir')
        ghost_acc = os.path.join(tmp, 'ghost_accept.json')
        with open(ghost_acc, 'w', encoding='utf-8') as f:
            json.dump({'pkg': ghost, 'verdict': 'PASS', 'checks': [],
                       'open_issues': []}, f, ensure_ascii=False)
        got, why = run_gate(nb, ghost, ghost_acc)
        row('T1', '改前臂：证据 pkg 指向**不存在的目录** ⇒ 期望 ALLOW（漏洞实锤）',
            'ALLOW', 'ALLOW' if got else 'BLOCK', why)

        # ── T2/T3：sp1 的证据 vs sp2 目标 ⇒ 两臂都 BLOCK ──
        got_b, why_b = run_gate(nb, SP2, ACC_SP1)
        row('T2', '改前臂：sp1 的验收证据 vs sp2 目标 ⇒ 期望 BLOCK',
            'BLOCK', 'ALLOW' if got_b else 'BLOCK', why_b)
        got_a, why_a = run_gate(na, SP2, ACC_SP1)
        row('T3', '改后臂：sp1 的验收证据 vs sp2 目标 ⇒ 期望 BLOCK',
            'BLOCK', 'ALLOW' if got_a else 'BLOCK', why_a)

        # ── 造一个「临时包副本」（只复制绑定范围，不碰真包）──
        real_acc = json.load(open(ACC_SP2, encoding='utf-8'))
        pc = real_acc.get('pkg_content')
        if not isinstance(pc, dict) or not pc.get('files'):
            raise RuntimeError('sp2 的验收证据没有 pkg_content ⇒ §205 的验收'
                               '脚本没跑过，先重跑再跑本矩阵')
        tmpl = os.path.join(tmp, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2')
        for rel in pc['files']:
            src = os.path.join(SP2, rel.replace('/', os.sep))
            dst = os.path.join(tmpl, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

        def synth(pkg_path, files, verdict='PASS'):
            p = os.path.join(tmp, 'synth_%d.json' % len(ev['rows']))
            with open(p, 'w', encoding='utf-8') as f:
                json.dump({'pkg': pkg_path, 'verdict': verdict,
                           'checks': [], 'open_issues': [],
                           'pkg_content': {'alg': 'sha256', 'files': files,
                                           'n_files': len(files)}},
                          f, ensure_ascii=False)
            return p

        # ── T4：证据**没有** pkg_content ⇒ 改后臂 BLOCK（fail-closed）──
        p4 = os.path.join(tmp, 'nobind.json')
        with open(p4, 'w', encoding='utf-8') as f:
            json.dump({'pkg': SP2, 'verdict': 'PASS', 'checks': [],
                       'open_issues': []}, f, ensure_ascii=False)
        got_a, why_a = run_gate(na, SP2, p4)
        row('T4', '改后臂：证据**无 pkg_content** ⇒ 期望 BLOCK（fail-closed）',
            'BLOCK', 'ALLOW' if got_a else 'BLOCK', why_a)
        got_b, why_b = run_gate(nb, SP2, p4)
        row('T4b', '改前臂：同一份「无绑定」证据 ⇒ 期望 ALLOW（证明差别就在这）',
            'ALLOW', 'ALLOW' if got_b else 'BLOCK', why_b)

        # ── T5：临时副本里**改坏 1 个文件** ⇒ BLOCK ──
        victim = sorted(pc['files'])[0]
        with open(os.path.join(tmpl, victim.replace('/', os.sep)), 'ab') as f:
            f.write(b'\n# tampered by app563\n')
        p5 = synth(tmpl, pc['files'])
        got_a, why_a = run_gate(na, tmpl, p5)
        row('T5', '改后臂：临时副本**改坏 1 个文件** ⇒ 期望 BLOCK',
            'BLOCK', 'ALLOW' if got_a else 'BLOCK', why_a)
        ev['rows'][-1]['victim'] = victim

        # ── T6：临时副本原封不动 ⇒ ALLOW ──
        shutil.rmtree(tmpl)
        for rel in pc['files']:
            src = os.path.join(SP2, rel.replace('/', os.sep))
            dst = os.path.join(tmpl, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        p6 = synth(tmpl, pc['files'])
        got_a, why_a = run_gate(na, tmpl, p6)
        row('T6', '改后臂：临时副本**原封不动** ⇒ 期望 ALLOW（不是一律拦）',
            'ALLOW', 'ALLOW' if got_a else 'BLOCK', why_a)

        # ── T7：验收后**新增 1 个 .py** ⇒ BLOCK（反向集合校验）──
        with open(os.path.join(tmpl, 'app', 'zz_new_module.py'), 'w',
                  encoding='utf-8') as f:
            f.write('# added after acceptance\n')
        p7 = synth(tmpl, pc['files'])
        got_a, why_a = run_gate(na, tmpl, p7)
        row('T7', '改后臂：验收后**新增 1 个 .py** ⇒ 期望 BLOCK（反向集合校验）',
            'BLOCK', 'ALLOW' if got_a else 'BLOCK', why_a)

        # ── T8：verdict=FAIL ⇒ 两臂都 BLOCK ──
        p8 = synth(SP2, pc['files'], verdict='FAIL')
        got_a, why_a = run_gate(na, SP2, p8)
        row('T8', '改后臂：verdict=FAIL ⇒ 期望 BLOCK',
            'BLOCK', 'ALLOW' if got_a else 'BLOCK', why_a)
        got_b, why_b = run_gate(nb, SP2, p8)
        row('T8b', '改前臂：verdict=FAIL ⇒ 期望 BLOCK',
            'BLOCK', 'ALLOW' if got_b else 'BLOCK', why_b)

        # ── T9：真 sp2 证据 vs 真 sp2 目录 ⇒ 改后臂 ALLOW（真实链路端到端）──
        got_a, why_a = run_gate(na, SP2, ACC_SP2)
        row('T9', '改后臂：真 sp2 证据 vs 真 sp2 目录 ⇒ 期望 ALLOW',
            'ALLOW', 'ALLOW' if got_a else 'BLOCK', why_a)
        got_b, why_b = run_gate(nb, SP2, ACC_SP2)
        row('T9b', '改前臂：真 sp2 证据 vs 真 sp2 目录 ⇒ 期望 ALLOW（内容未验证）',
            'ALLOW', 'ALLOW' if got_b else 'BLOCK', why_b)

        n_pass = sum(1 for r in ev['rows'] if r['pass'])
        ev['n_rows'] = len(ev['rows'])
        ev['n_pass'] = n_pass
        ev['n_fail'] = len(ev['rows']) - n_pass
        ev['verdict'] = 'PASS' if n_pass == len(ev['rows']) else 'FAIL'
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        print('\nevidence -> %s' % OUT)
        print('VERDICT: %s（%d/%d）' % (ev['verdict'], n_pass, len(ev['rows'])))
        return 0 if ev['verdict'] == 'PASS' else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
