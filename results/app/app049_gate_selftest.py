#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app049_gate_selftest.py —— 闸门**自检**：证明它**能抓到**真缺陷（不是假闸门）。

🔴 **「自检 PASS」≠「全面无缺陷」**（长期记忆铁律）
   ⇒ 闸门必须能**独立复现真故障形态**，否则它只是「什么都没查」。

做法：在**临时副本**里制造两类真缺陷 ⇒ 闸门必须**逐条抓出**；
      再把副本还原 ⇒ 闸门必须**回到 PASS**。
      （**不碰仓库真实文件** ⇒ 用临时目录做，零污染。）
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, 'app049_pkg_path_hardcode_gate.py')

PASS = []
FAIL = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))
    (PASS if cond else FAIL).append(name)


def run_gate(repo_root):
    """在给定仓库根上跑闸门，返回 (rc, stdout)。

    🔴 `APP049_REPO_ROOT` 让闸门扫描**指定**的根（而不是它 `__file__` 所在的仓库）
    ⇒ 自检才能在「注入缺陷的临时副本」上验证闸门真的能抓。
    """
    env = dict(os.environ)
    env['PYTHONPATH'] = repo_root
    env['APP049_REPO_ROOT'] = repo_root
    r = subprocess.run([sys.executable, GATE], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=300,
                       cwd=repo_root, env=env)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def main():
    print('=' * 72)
    print('§48 闸门自检：证明闸门能抓到真缺陷')
    print('=' * 72)

    # ── 基线：干净仓库应 PASS ──
    rc, out = run_gate(REPO)
    check('S1 干净仓库闸门 PASS', rc == 0,
          'rc=%d' % rc)
    check('S2 基线输出含「0 处违规」', '0 处违规' in out)

    # ── 在**临时副本**里制造缺陷 ⇒ 闸门必须抓到 ──
    tmp = tempfile.mkdtemp(prefix='app049_selftest_')
    try:
        # 只复制闸门扫描需要的两个根（省时间）
        for rel in ('results/app', 'live_caption'):
            src = os.path.join(REPO, rel.replace('/', os.sep))
            dst = os.path.join(tmp, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copytree(src, dst, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__'))
        # 闸门还需要 pkg_paths（在仓库根）
        shutil.copy2(os.path.join(REPO, 'pkg_paths.py'),
                     os.path.join(tmp, 'pkg_paths.py'))

        # 缺陷 A：**活跃验收脚本**里写死包版本
        fa = os.path.join(tmp, 'results', 'app', 'test_selftest_hardcoded.py')
        with open(fa, 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n'
                    'PKG = r"C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v9.9"\n')
        # 缺陷 B：**会进包的生产模块**里写死包路径
        fb = os.path.join(tmp, 'live_caption', 'tts_service.py')
        with open(fb, 'a', encoding='utf-8') as f:
            f.write('\nPKG = r"C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v9.9"\n')

        rc2, out2 = run_gate(tmp)
        check('S3 注入缺陷后闸门 FAIL', rc2 != 0, 'rc=%d' % rc2)
        check('S4 抓到类别 A（活跃验收脚本）',
              'test_selftest_hardcoded.py' in out2 and '[A]' in out2)
        check('S5 抓到类别 B（会进包的生产模块）',
              'tts_service.py' in out2 and '[B]' in out2)
        check('S6 报出违规数 = 2', '违规 2 处' in out2)

        # ── 移除缺陷 ⇒ 必须回到 PASS（闸门不能「一次命中就永久红」）──
        os.remove(fa)
        with open(fb, 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n')
        rc3, out3 = run_gate(tmp)
        check('S7 移除缺陷后闸门回到 PASS', rc3 == 0, 'rc=%d' % rc3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('=' * 72)
    print('PASS %d / FAIL %d' % (len(PASS), len(FAIL)))
    if FAIL:
        print('失败项：%s' % FAIL)
    print('总判定：%s' % ('PASS' if not FAIL else 'FAIL'))
    print('=' * 72)

    ev = os.path.join(HERE, 'app049_gate_selftest_evidence.json')
    with open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(pass_list=PASS, fail_list=FAIL,
                       verdict='PASS' if not FAIL else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print('证据已落盘：%s' % ev)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
