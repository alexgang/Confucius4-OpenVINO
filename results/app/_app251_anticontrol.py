#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_anticontrol.py —— §251 **反证组**：证明 app049 闸门**仍能抓真缺陷**。

🔴 **「白名单放行」最大的风险＝把闸门放水放成永远绿**
   ⇒ 本脚本是 §251 白名单增补的**必要配套**，不是可选。

做法（**不碰仓库真实文件** ⇒ 零污染）：
  * 在**临时副本**里制造两类真缺陷（与闸门自检 `app049_gate_selftest.py` 同形）：
      类别 A：活跃验收脚本里写死包版本
      类别 B：会进包的生产模块里写死包路径
  * 闸门必须 **exit≠0 且逐条点名**（⇒ 判据有鉴别力）
  * 再造**一个未白名单的**新脚本 ⇒ 必须仍被抓 ⇒ **不是**「白名单放行了真缺陷」
  * 移除缺陷 ⇒ 闸门必须回到 PASS（不是「一次命中就永久红」）

🔴 **临时副本只复制闸门真正会扫的文件（`*.py`）**
   —— 旧实现整树 `copytree`，**会跟随 Windows junction 走进 AppData 的真实缓存**
   ⇒ 实测复制出 **160 GB**、把 C: 盘写满到 **100%**（§251 实测事故）。
   ⇒ 本脚本只复制 `.py` ⇒ 副本只有几 MB ⇒ 既快又不会撑爆磁盘。
   （闸门只判 `.py` 文件 ⇒ 只复制 `.py` **不影响闸门行为**。）
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


def copy_py_only(src_root, dst_root):
    """只复制 ``*.py``（保留相对结构）⇒ 不跟随 junction、不撑爆磁盘。"""
    n = 0
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d not in ('__pycache__', '.git')]
        rel = os.path.relpath(dirpath, src_root)
        out_dir = os.path.join(dst_root, rel) if rel != '.' else dst_root
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            os.makedirs(out_dir, exist_ok=True)
            shutil.copy2(os.path.join(dirpath, fn),
                         os.path.join(out_dir, fn))
            n += 1
    return n


def run_gate(repo_root, gate_path=None):
    """跑闸门。

    🔴 `gate_path` 必须可指定**闸门脚本自身**——否则永远跑真实仓库那份，
       「用修复前的闸门跑同一副本」这种鉴别力检查就**永远测不到**（§251 反证坑）。
    """
    env = dict(os.environ)
    env['PYTHONPATH'] = repo_root
    env['APP049_REPO_ROOT'] = repo_root
    script = gate_path or GATE
    r = subprocess.run([sys.executable, script], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=600,
                       cwd=repo_root, env=env)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def main():
    print('=' * 72)
    print('§251 反证组：app049 闸门在白名单增补后**仍能抓真缺陷**')
    print('=' * 72)

    # ── 真实仓库：应当 PASS（§251 修完的状态）──
    rc, out = run_gate(REPO)
    check('A1 真实仓库闸门 PASS', rc == 0, 'rc=%d' % rc)
    check('A2 基线含「0 处违规」', '0 处违规' in out)

    tmp = tempfile.mkdtemp(prefix='app251_anticontrol_')
    try:
        n_py = 0
        for rel in ('results/app', 'live_caption'):
            src = os.path.join(REPO, rel.replace('/', os.sep))
            dst = os.path.join(tmp, rel.replace('/', os.sep))
            os.makedirs(dst, exist_ok=True)
            n_py += copy_py_only(src, dst)
        shutil.copy2(os.path.join(REPO, 'pkg_paths.py'),
                     os.path.join(tmp, 'pkg_paths.py'))
        print('  （临时副本：%d 个 .py 文件）' % n_py)

        # ── 缺陷 1：类别 A（活跃验收脚本写死包版本）──
        fa = os.path.join(tmp, 'results', 'app', 'test_app251_hardcoded.py')
        with open(fa, 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n'
                    'PKG = r"C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v9.9"\n')

        # ── 缺陷 2：类别 B（会进包的生产模块写死包路径）──
        fb = os.path.join(tmp, 'live_caption', 'tts_service.py')
        with open(fb, 'a', encoding='utf-8') as f:
            f.write('\nPKG = r"C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v9.9"\n')

        rc2, out2 = run_gate(tmp)
        check('B1 注入缺陷后闸门 FAIL', rc2 != 0, 'rc=%d' % rc2)
        check('B2 抓到类别 A（活跃验收脚本）',
              'test_app251_hardcoded.py' in out2 and '[A]' in out2)
        check('B3 抓到类别 B（会进包的生产模块）',
              'tts_service.py' in out2 and '[B]' in out2)
        check('B4 报出违规数 = 2', '违规 2 处' in out2)

        # ── 缺陷 3：**未白名单的**新脚本 ⇒ 仍被抓（证明不是「放水放成永远绿」）──
        #   🔴 文件名**必须命中 ACTIVE_RE**（`^test_|_gate|_check|_verify|_probe`）
        #      ⇒ 否则它按定义就是「一次性历史脚本」⇒ 闸门**本就不该**报它
        #      （这是闸门的**设计**，不是漏洞）。
        fc = os.path.join(tmp, 'results', 'app', 'test_app251_new_unlisted.py')
        with open(fc, 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n'
                    'PKG = r"C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v9.9"\n')
        rc3, out3 = run_gate(tmp)
        check('B5 未白名单的新脚本仍被抓（闸门未被放水）',
              rc3 != 0 and 'test_app251_new_unlisted.py' in out3, 'rc=%d' % rc3)

        # ── 移除缺陷 ⇒ 必须回到 PASS ──
        os.remove(fa)
        os.remove(fc)
        with open(fb, 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n')
        rc4, out4 = run_gate(tmp)
        check('B6 移除缺陷后闸门回到 PASS', rc4 == 0, 'rc=%d' % rc4)

        # ── 反证组自身的鉴别力：把「真实仓库」换成**未修的白名单**⇒ 必须 FAIL ──
        #   （证明 A1 的 PASS 不是「因为判据失灵才 PASS」）
        bak = os.path.join(HERE, 'app049_pkg_path_hardcode_gate.py.bak_app251')
        if os.path.isfile(bak):
            tmp2 = tempfile.mkdtemp(prefix='app251_bak_')
            try:
                for rel in ('results/app', 'live_caption'):
                    src = os.path.join(REPO, rel.replace('/', os.sep))
                    dst = os.path.join(tmp2, rel.replace('/', os.sep))
                    os.makedirs(dst, exist_ok=True)
                    copy_py_only(src, dst)
                shutil.copy2(os.path.join(REPO, 'pkg_paths.py'),
                             os.path.join(tmp2, 'pkg_paths.py'))
                # 🔴 必须**显式指定**要跑「修复前」那份闸门脚本本身，
                #    否则 run_gate 默认跑真实仓库那份 ⇒ 这个鉴别力检查永远测不到。
                rc5, _ = run_gate(tmp2, gate_path=bak)
                check('B7 修复前的闸门在同一副本上 FAIL（判据有鉴别力）',
                      rc5 != 0, 'rc=%d' % rc5)
            finally:
                shutil.rmtree(tmp2, ignore_errors=True)
        else:
            check('B7 修复前的闸门在同一副本上 FAIL（判据有鉴别力）', False,
                  '缺备份 %s' % bak)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('=' * 72)
    print('PASS %d / FAIL %d' % (len(PASS), len(FAIL)))
    if FAIL:
        print('失败项：%s' % FAIL)
    print('总判定：%s' % ('PASS' if not FAIL else 'FAIL'))
    print('=' * 72)

    ev = os.path.join(HERE, 'app251_anticontrol.json')
    with open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(pass_list=PASS, fail_list=FAIL,
                       verdict='PASS' if not FAIL else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print('证据已落盘：%s' % ev)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
