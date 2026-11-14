#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app567_zip_manifest_binding_matrix.py —— §206 鉴别力矩阵（闸门传递绑定）。

🔴 **要证明的事**：出包闸门 `_app537_zip_specialmvp.py` 的「内容绑定」
   （§205）**只覆盖代码 + 元数据（31 个文件）**，而 **7.86 GiB / 96 个模型文件**
   的 SHA256 **只**记在包内 `app/MANIFEST.json` 里 ⇒ 闸门**从不再验证那条
   传递链** ⇒ **验收后把模型文件换掉 / 塞未登记文件，闸门照样放行**，
   而验收记录会（不实地）声称「核模型身份：一致 96，不一致 0」。

🔴 **两臂**：
  · **before** ＝ HEAD blob（`git cat-file blob HEAD:results/app/_app537_zip_specialmvp.py`）
    的**逐字原文**（不是"我以为修复前的行为"）；
  · **after**  ＝ 工作区修复后的脚本。
  两臂都用 **AST 抽出被测函数**（不 import、不执行脚本主体的 argparse/闸门流程
  ⇒ **零副作用、零写客户包**），再对**临时目录里的假包**真跑。

🔴 **纪律**：不碰任何真实客户包；不写客户包；不出 zip；不删文件（安全删除 shim）。
"""
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
GATE_REL = 'results/app/_app537_zip_specialmvp.py'

WANT_FUNCS = ('sha256_file', '_norm_pkg', '_verdict_ok', 'check_acceptance',
              'check_release_identity', 'check_content_binding',
              'check_manifest_model_binding')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_funcs(src, tag):
    """🔴 用 AST **只抽函数定义**再 exec ⇒ 不执行脚本主体（argparse/闸门流程）。

    这是「判据必须真跑被测对象」的写法：抽出来的就是被测函数本体，
    不是复刻品。
    """
    tree = ast.parse(src)
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in WANT_FUNCS]
    got = {n.name for n in keep}
    ns = {'os': os, 'json': json, 'hashlib': hashlib, 're': __import__('re'),
          'sys': sys}
    exec(compile(ast.Module(body=keep, type_ignores=[]), '<%s>' % tag, 'exec'),
         ns)
    return ns


def before_src():
    out = subprocess.run(
        ['git', '-C', REPO, 'cat-file', 'blob', 'HEAD:' + GATE_REL],
        capture_output=True)
    if out.returncode != 0:
        raise RuntimeError('取 HEAD blob 失败：%s' % out.stderr.decode('utf-8', 'replace'))
    return out.stdout.decode('utf-8')


def after_src():
    with open(os.path.join(REPO, GATE_REL.replace('/', os.sep)), encoding='utf-8') as f:
        return f.read()


# ── 假包构造（临时目录；**不碰真实客户包**）──────────────────────────────
PKG_NAME = 'Confucius4_LiveCaption_FakeMVP_v1.0-t1'


def build_fake_pkg(root, pkg_name=PKG_NAME, wrong_models_root=False):
    """造一个结构与 Special MVP 同形的小假包：app/*.py + 元数据 + models/。

    `wrong_models_root=True` ⇒ MANIFEST 的 `pkg_models_root` 指向**别的包**
    （＝ §205 真缺陷① 那一类，**在验收时就已存在** ⇒ 内容绑定查不出来）。
    """
    pkg = os.path.join(root, pkg_name)
    os.makedirs(os.path.join(pkg, 'app'))
    os.makedirs(os.path.join(pkg, 'models', 'm1'))
    files = {
        'app/a.py': b'# a\nprint("a")\n',
        'app/b.py': b'# b\nprint("b")\n',
        'release.json': json.dumps({'version': '1.0-t1'}, indent=1).encode(),
        'package_profile.json': json.dumps({'profile': 'fake'}, indent=1).encode(),
        'models/m1/w.bin': b'WEIGHT-BYTES-ORIGINAL\n',
    }
    for rel, data in files.items():
        with open(os.path.join(pkg, rel.replace('/', os.sep)), 'wb') as f:
            f.write(data)
    manifest = {
        'schema': 'app099-manifest-v1',
        'created_at': '2026-11-14 22:00:00',
        'source_root': root,
        'pkg_models_root': (os.path.join(root, 'OTHERPKG', 'models')
                            if wrong_models_root
                            else os.path.join(pkg, 'models')),
        'n_models': 1,
        'models': {'m1': {'files': [
            {'name': 'w.bin', 'sha256': sha256_file(os.path.join(pkg, 'models', 'm1', 'w.bin'))}]}},
        'computed_sha': True, 'n_mismatches': 0, 'mismatches': [], 'all_match': True,
    }
    with open(os.path.join(pkg, 'app', 'MANIFEST.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return pkg


def build_evidence(pkg, root, verdict='PASS（有 1 项未结：退出码异常）',
                   pkg_override=None, with_content=True):
    """造一份与 `_app553` 同形的验收证据（pkg_content 只含代码+元数据 31 类同款）。"""
    scope = ['app/a.py', 'app/b.py', 'release.json', 'package_profile.json',
             'app/MANIFEST.json']
    ev = {
        'pkg': pkg_override if pkg_override is not None else pkg,
        'version': '1.0-t1',
        'checks': [{'id': 'A1', 'pass': True}, {'id': 'A4', 'pass': True,
                                                'detail': '核模型身份：一致 1，不一致 0'}],
        'open_issues': [{'id': 'OPEN-1', 'title': '长跑退出码未定位'}],
        'n_checks': 2, 'n_fail': 0, 'verdict': verdict,
    }
    if with_content:
        ev['pkg_content'] = {
            'scope': ['app/*.py', 'release.json', 'package_profile.json',
                      'app/MANIFEST.json'],
            'alg': 'sha256',
            'n_files': len(scope),
            'files': {rel: sha256_file(os.path.join(pkg, rel.replace('/', os.sep)))
                      for rel in scope},
            'tree_digest': 'fake',
        }
    p = os.path.join(root, 'accept.json')
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    return p


def run_arm(ns, pkg, accept_path):
    """跑一条臂的闸门 ⇒ 返回 (ALLOW|BLOCK, 原因)。"""
    try:
        ns['check_acceptance'](pkg, accept_path)
        ns['check_release_identity'](pkg, os.path.basename(pkg))
        ns['check_content_binding'](pkg, json.load(open(accept_path, encoding='utf-8')))
        fn = ns.get('check_manifest_model_binding')
        if fn is not None:
            fn(pkg, os.path.basename(pkg))
        return 'ALLOW', ''
    except Exception as e:            # noqa: BLE001 —— 闸门以异常表示「拒绝」
        return 'BLOCK', str(e)[:180]


# ── 12 条鉴别臂 ─────────────────────────────────────────────────────────
def mutate_model_content(pkg):
    p = os.path.join(pkg, 'models', 'm1', 'w.bin')
    with open(p, 'wb') as f:
        f.write(b'WEIGHT-BYTES-TAMPERED\n')


def mutate_add_unregistered(pkg):
    with open(os.path.join(pkg, 'models', 'm1', 'extra.bin'), 'wb') as f:
        f.write(b'EXTRA\n')


def mutate_del_model(pkg):
    os.remove(os.path.join(pkg, 'models', 'm1', 'w.bin'))


def mutate_add_app_py(pkg):
    with open(os.path.join(pkg, 'app', 'new.py'), 'wb') as f:
        f.write(b'# new\n')


def mutate_add_app_subdir_py(pkg):
    os.makedirs(os.path.join(pkg, 'app', 'sub'))
    with open(os.path.join(pkg, 'app', 'sub', 'new.py'), 'wb') as f:
        f.write(b'# new\n')


def mutate_modify_app_py(pkg):
    with open(os.path.join(pkg, 'app', 'a.py'), 'wb') as f:
        f.write(b'# a CHANGED\n')


def mutate_manifest_points_elsewhere(pkg):
    """（保留：用于「验收后再改 MANIFEST」这一变体；内容绑定会抓到它）"""
    mp = os.path.join(pkg, 'app', 'MANIFEST.json')
    m = json.load(open(mp, encoding='utf-8'))
    m['pkg_models_root'] = os.path.join(pkg, '..', 'OTHERPKG', 'models')
    with open(mp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(m, f, ensure_ascii=False, indent=1)


ARMS = [
    # (id, 描述, 变异函数, 证据 kwargs, 期望 before, 期望 after, 构包 kwargs)
    ('T1', '未改动（回归守卫）', None, {}, 'ALLOW', 'ALLOW', {}),
    ('T2', '模型文件内容被换（7.86 GiB 那类的传递绑定）', mutate_model_content, {},
     'ALLOW', 'BLOCK', {}),
    ('T3', 'models/ 下塞未登记文件', mutate_add_unregistered, {}, 'ALLOW', 'BLOCK', {}),
    ('T4', '模型文件被删', mutate_del_model, {}, 'ALLOW', 'BLOCK', {}),
    ('T5', 'app/ 顶层新增 .py', mutate_add_app_py, {}, 'BLOCK', 'BLOCK', {}),
    ('T6', 'app/ 子目录新增 .py', mutate_add_app_subdir_py, {}, 'ALLOW', 'BLOCK', {}),
    ('T7', 'app/a.py 内容被改', mutate_modify_app_py, {}, 'BLOCK', 'BLOCK', {}),
    ('T8', '证据属于另一个包（§204 回归）', None,
     {'pkg_override': r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp1'},
     'BLOCK', 'BLOCK', {}),
    ('T9', '验收 verdict=FAIL', None, {'verdict': 'FAIL（3 项未过）'},
     'BLOCK', 'BLOCK', {}),
    ('T10', '证据无 pkg_content（§205 回归）', None, {'with_content': False},
     'BLOCK', 'BLOCK', {}),
    ('T11', 'MANIFEST 指向别的包的 models（验收时就存在）', None, {},
     'ALLOW', 'BLOCK', {'wrong_models_root': True}),
    ('T12', 'release.json 版本与目录名不符', None, {}, 'BLOCK', 'BLOCK', {}),
]


def main():
    before_ns = load_funcs(before_src(), 'before')
    after_ns = load_funcs(after_src(), 'after')
    assert 'check_manifest_model_binding' not in before_ns, \
        'before 臂不该有 §206 的新函数（HEAD blob 与工作区不一致？）'
    assert 'check_manifest_model_binding' in after_ns, \
        'after 臂缺 §206 的新函数'

    tmp = tempfile.mkdtemp(prefix='app567_fake_')
    rows = []
    try:
        for tid, desc, mut, evkw, exp_b, exp_a, pkgkw in ARMS:
            root = os.path.join(tmp, tid)
            os.makedirs(root)
            pkg = build_fake_pkg(root, **pkgkw)
            accept = build_evidence(pkg, root, **evkw)
            if tid == 'T12':
                rel = json.load(open(os.path.join(pkg, 'release.json'), encoding='utf-8'))
                rel['version'] = '9.9-x'
                with open(os.path.join(pkg, 'release.json'), 'w', encoding='utf-8', newline='\n') as f:
                    json.dump(rel, f, ensure_ascii=False, indent=1)
            if mut:
                mut(pkg)
            b, breason = run_arm(before_ns, pkg, accept)
            a, areason = run_arm(after_ns, pkg, accept)
            ok = (b == exp_b) and (a == exp_a)
            rows.append({'id': tid, 'desc': desc, 'expect_before': exp_b,
                         'before': b, 'expect_after': exp_a, 'after': a,
                         'pass': ok, 'before_reason': breason,
                         'after_reason': areason})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n_pass = sum(1 for r in rows if r['pass'])
    out = {'matrix': 'app567 §206 出包闸门传递绑定鉴别力矩阵',
           'gate': GATE_REL,
           'before_arm': 'HEAD blob（git cat-file blob HEAD:...）逐字原文',
           'after_arm': '工作区修复后脚本',
           'how': 'AST 抽函数（不执行脚本主体）＋ 临时目录假包真跑；零写真实客户包',
           'n_arms': len(rows), 'n_pass': n_pass,
           'n_fail': len(rows) - n_pass,
           'verdict': 'PASS' if n_pass == len(rows) else 'FAIL',
           'rows': rows}
    op = os.path.join(RESULTS, 'app567_zip_manifest_binding_matrix.json')
    with open(op, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for r in rows:
        print('%s %-4s before=%-5s after=%-5s  %s' %
              ('OK ' if r['pass'] else 'FAIL', r['id'], r['before'], r['after'],
               r['desc']))
    print('\n%d/%d PASS ⇒ %s' % (n_pass, len(rows), out['verdict']))
    print('证据：%s' % op)
    return 0 if n_pass == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
