#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_anticontrol_material.py —— §251 **反证组**：内部素材闸门在字体修法后
**真检测没被削弱**，且**误报确实消除**。

🔴 修法＝把字体扩展名加进 `SKIP_CONTENT_EXT`（不读其内容）
   ⇒ 最大风险＝**把真检测一起放过了** ⇒ 必须证明：

   ① 真正的会议特征串放进**一个 .txt** ⇒ 闸门**仍必须 FAIL**（内容检测没被削弱）；
   ② 真正的 U+FFFD 乱码放进**一个 .js** ⇒ 闸门**仍必须 FAIL**（乱码检测没被削弱）；
   ③ 字体文件里的**偶然**字节命中 ⇒ 闸门**必须 PASS**（误报消除）；
   ④ 字体文件**名字**命中文件名规则 ⇒ 闸门**仍必须 FAIL**（NAME_PATTERNS 未被绕过）；
   ⑤ 非字体二进制（如 .png）行为**未变**（仍按原口径）。

🔴 **全部在临时目录里做** ⇒ 零污染、零客户包改动。
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
GATE = os.path.join(REPO, 'check_internal_material.py')

PASS = []
FAIL = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))
    (PASS if cond else FAIL).append(name)


def run_gate(pkg):
    r = subprocess.run([sys.executable, GATE, '--pkg', pkg],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=600, cwd=REPO)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def make_pkg(tmp, files):
    """建一个**干净**的临时包目录。

    🔴 每个用例必须用**全新目录** ⇒ 否则前一个用例留下的文件会被后一个用例
       一起扫到 ⇒ 判据**串味**（实测：①的真句让③误判 FAIL）。
    """
    pkg = tempfile.mkdtemp(prefix='pkg_', dir=tmp)
    for rel, content in files.items():
        p = os.path.join(pkg, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        mode = 'wb' if isinstance(content, bytes) else 'w'
        kw = {} if isinstance(content, bytes) else {'encoding': 'utf-8'}
        with open(p, mode, **kw) as f:
            f.write(content)
    return pkg


def main():
    print('=' * 72)
    print('§251 反证组：内部素材闸门（字体修法后）真检测未削弱 / 误报已消除')
    print('=' * 72)

    tmp = tempfile.mkdtemp(prefix='app251_mat_')
    try:
        # ── ① 真正的会议特征串（.txt）⇒ 必须仍被抓 ──
        pkg = make_pkg(tmp, {
            'notes/leak.txt': '本次会议代号 QGS 规格 52core 音频 260902\n',
        })
        rc, out = run_gate(pkg)
        check('C1 真正的会议特征串（.txt）仍被抓', rc == 1, 'rc=%d' % rc)
        check('C2 报出「内容关键词」', '内容关键词' in out)

        # ── ② 真正的 U+FFFD 乱码（.js）⇒ 必须仍被抓 ──
        pkg = make_pkg(tmp, {
            'ext/extension/player.js': '// comment with \ufffd\ufffd\ufffd broken\n',
        })
        rc, out = run_gate(pkg)
        check('C3 真正的 U+FFFD 乱码（.js）仍被抓', rc == 1, 'rc=%d' % rc)
        check('C4 报出「U+FFFD 乱码」', 'U+FFFD' in out)

        # ── ③ 字体里的偶然字节命中 ⇒ 必须 PASS（误报消除）──
        #   构造一个 woff2：里面放**能命中** `\bQ[G]S\b` 的字节
        payload = (b'\x00\x01\x02binarynoise' + b'qgS' +
                   b'\x00\xff\xfe more random bytes \x89PNG\r\n')
        pkg = make_pkg(tmp, {
            'assets/font.woff2': payload,
        })
        rc, out = run_gate(pkg)
        check('C5 字体里的偶然字节命中不再误报（PASS）', rc == 0, 'rc=%d' % rc)

        # ── ④ 字体**文件名**命中规则 ⇒ 必须仍被抓（NAME_PATTERNS 未绕过）──
        pkg = make_pkg(tmp, {
            'assets/preset_B.woff2': b'\x00\x01\x02',
        })
        rc, out = run_gate(pkg)
        check('C6 字体「文件名规则」仍生效（preset_B 被抓）', rc == 1, 'rc=%d' % rc)

        # ── ⑤ 非字体二进制（.png）行为未变（仍按原口径：不读内容）──
        pkg = make_pkg(tmp, {
            'assets/logo.png': b'\x89PNG\r\n\x1a\n' + b'qgS' + b'\x00\xff',
        })
        rc, out = run_gate(pkg)
        check('C7 .png 仍按原口径不读内容（PASS）', rc == 0, 'rc=%d' % rc)

        # ── ⑥ 反证组自身的鉴别力：把真句放进 .txt 再跑一次仍 FAIL（不是「恒 PASS」）──
        pkg = make_pkg(tmp, {
            'notes/real.txt': '内部交付 上周我们 客户样品 份额损失\n',
        })
        rc, out = run_gate(pkg)
        check('C8 中文会议关键词仍被抓（判据有鉴别力）', rc == 1, 'rc=%d' % rc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('=' * 72)
    print('PASS %d / FAIL %d' % (len(PASS), len(FAIL)))
    if FAIL:
        print('失败项：%s' % FAIL)
    print('总判定：%s' % ('PASS' if not FAIL else 'FAIL'))
    print('=' * 72)

    ev = os.path.join(HERE, 'app251_anticontrol_material.json')
    with open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(pass_list=PASS, fail_list=FAIL,
                       verdict='PASS' if not FAIL else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print('证据已落盘：%s' % ev)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
