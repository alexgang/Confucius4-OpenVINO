#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§247：`_app148_zip_consistency.py` 修判据后的**反证组**（判据必须有鉴别力）。

背景：原脚本把 zip 条目（带顶层目录前缀）直接和目录相对路径比 ⇒ **10893 条全不匹配
⇒ 假 FAIL**。修法＝先剥前缀、且要求「所有条目都带前缀」。修判据最容易修成
「恒 PASS」，所以必须用坏样例证伪：

| case | 构造 | 期望 |
|---|---|---|
| c1 | 正常（2 文件、带前缀、内容一致） | **PASS**（rc=0） |
| c2 | zip 多一个文件 | **FAIL**（only_in_zip=1） |
| c3 | zip 缺一个文件 | **FAIL**（only_in_dir=1） |
| c4 | 同名文件内容更长 ⇒ 大小不同 | **FAIL**（size_differs=1） |
| c5 | zip 不带顶层前缀 | **FAIL**（all_entries_have_top_prefix=False） |
| c6 | 反证「真包」：用真实 v1.2 zip 跑一次 | **PASS**（rc=0，10893/10893） |
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, '_app148_zip_consistency.py')
REAL_ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.zip'
REAL_CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app247_zip_consistency_counterexample.json'


def load_mod():
    spec = importlib.util.spec_from_file_location('_zipcons', TARGET)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_case(root, name, files, prefix, extra=None, skip=None, grow=None):
    """files: {rel: bytes}；prefix: 是否带顶层目录前缀；extra: 额外只进 zip 的文件"""
    d = os.path.join(root, name + '_dir')
    os.makedirs(d, exist_ok=True)
    for rel, data in files.items():
        p = os.path.join(d, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)
    z = os.path.join(root, name + '.zip')
    top = (os.path.basename(d) + '/') if prefix else ''
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel, data in files.items():
            if skip and rel == skip:
                continue
            if grow and rel == grow:
                data = data + b'X' * 16
            zf.writestr(top + rel, data)
        for rel, data in (extra or {}).items():
            zf.writestr(top + rel, data)
    return z, d


def run(m, z, d, out_path):
    old_out = m.OUT
    m.OUT = out_path
    try:
        rc = m.main(z, d)
    finally:
        m.OUT = old_out
    data = {}
    if os.path.isfile(out_path):
        with open(out_path, encoding='utf-8') as f:
            data = json.load(f)
    return rc, data


def main():
    m = load_mod()
    root = tempfile.mkdtemp(prefix='app247_zipcons_')
    base = {'a.txt': b'hello', 'sub/b.bin': bytes(range(64))}
    cases = []

    z, d = make_case(root, 'c1_ok', base, prefix=True)
    rc, data = run(m, z, d, os.path.join(root, 'c1.json'))
    cases.append({'case': 'c1 正常', 'expect': 'PASS', 'rc': rc,
                  'verdict': data.get('verdict')})

    z, d = make_case(root, 'c2_extra', base, prefix=True,
                     extra={'zzz.txt': b'extra'})
    rc, data = run(m, z, d, os.path.join(root, 'c2.json'))
    cases.append({'case': 'c2 zip 多一个文件', 'expect': 'FAIL', 'rc': rc,
                  'only_in_zip': (data.get('only_in_zip') or {}).get('count'),
                  'verdict': data.get('verdict')})

    z, d = make_case(root, 'c3_missing', base, prefix=True, skip='a.txt')
    rc, data = run(m, z, d, os.path.join(root, 'c3.json'))
    cases.append({'case': 'c3 zip 缺一个文件', 'expect': 'FAIL', 'rc': rc,
                  'only_in_dir': (data.get('only_in_dir') or {}).get('count'),
                  'verdict': data.get('verdict')})

    z, d = make_case(root, 'c4_size', base, prefix=True, grow='a.txt')
    rc, data = run(m, z, d, os.path.join(root, 'c4.json'))
    cases.append({'case': 'c4 同名不同大小', 'expect': 'FAIL', 'rc': rc,
                  'size_differs': (data.get('size_differs') or {}).get('count'),
                  'verdict': data.get('verdict')})

    z, d = make_case(root, 'c5_noprefix', base, prefix=False)
    rc, data = run(m, z, d, os.path.join(root, 'c5.json'))
    cases.append({'case': 'c5 zip 无顶层前缀', 'expect': 'FAIL', 'rc': rc,
                  'entries_without_prefix':
                      (data.get('entries_without_prefix') or {}).get('count'),
                  'verdict': data.get('verdict')})

    if os.path.isfile(REAL_ZIP):
        rc, data = run(m, REAL_ZIP, REAL_CAND, os.path.join(root, 'c6.json'))
        cases.append({'case': 'c6 真实 v1.2 zip', 'expect': 'PASS', 'rc': rc,
                      'n_zip': data.get('n_zip_entries'),
                      'n_dir': data.get('n_dir_files'),
                      'verdict': data.get('verdict')})

    ok = True
    print('=== 反证组 ===')
    for c in cases:
        want_pass = (c['expect'] == 'PASS')
        got_pass = (c['rc'] == 0)
        good = (want_pass == got_pass)
        ok = ok and good
        print('  [%s] %-18s 期望 %-4s 实际 rc=%s'
              % ('PASS' if good else 'FAIL', c['case'], c['expect'], c['rc']))
        print('        verdict=%s' % json.dumps(c.get('verdict'),
                                                ensure_ascii=False))

    res = {'generated_at': __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
           'target': TARGET, 'cases': cases, 'all_as_expected': ok}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\n落盘 ->', OUT)
    print('结论：%s' % ('PASS（判据有鉴别力）' if ok else 'FAIL'))
    try:
        shutil.rmtree(root)
    except Exception as e:
        print('（临时目录未删：%s ⇒ %s）' % (root, e))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
