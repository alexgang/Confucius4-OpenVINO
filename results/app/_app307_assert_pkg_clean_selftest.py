r"""_app307 — `live_caption/assert_pkg_clean.py` 的判据自检（含反证）。

🔴 PASS ≠ 正确：必须用**已知有缺陷的真实旧包**能识破；
   并用干净临时目录证明不误伤 preset_A / babelvox 库代码 / tokenizer。
不占设备、不删任何文件。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.expanduser('~')
EV = os.path.join(HERE, '_app307_assert_pkg_clean_selftest.json')
CHECKS = []


def check(name, cond, detail=''):
    CHECKS.append(dict(name=name, ok=bool(cond), detail=str(detail)))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + str(detail)) if detail else ''))
    return bool(cond)


def load():
    p = os.path.join(REPO, 'live_caption', 'assert_pkg_clean.py')
    spec = importlib.util.spec_from_file_location('assert_pkg_clean_mod', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def touch(root, rel, data=b'x'):
    p = os.path.join(root, *rel.split('/'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(data)


def main():
    print('=' * 72)
    print('_app307 — 建包阶段洁净度闸门自检（APP-077① + APP-078③）')
    print('=' * 72)
    m = load()

    # ① 已知有缺陷的真实旧包必须被识破（PASS ≠ 正确的核心反证）
    print('\n[1] 真实旧包（已知有缺陷）必须判 FAIL')
    for v in ('2.0', '2.1', '2.2'):
        pkg = os.path.join(HOME, 'Confucius4_LiveCaption_v' + v)
        bad = m.scan(pkg)
        n_token = len([b for b in bad if 'token' in b[1]])
        n_voice = len([b for b in bad if 'voice' in b[1]])
        check('v%s 判出 1 个固定 token' % v, n_token == 1, n_token)
        check('v%s 判出 8 个第三方音色文件' % v, n_voice == 8, n_voice)
        check('v%s assert_clean 返回 1（拒绝交付）' % v,
              m.assert_clean(pkg) == 1)

    # ② 干净目录不误伤
    print('\n[2] 干净临时目录（不误伤）')
    with tempfile.TemporaryDirectory(prefix='app307_clean_') as tmp:
        touch(tmp, 'models/qwen3tts/voices/preset_A.wav', b'RIFF')
        touch(tmp, 'python/Lib/site-packages/babelvox/cli.py', b'# code')
        touch(tmp, 'python/Lib/site-packages/babelvox/data/other.json', b'{}')
        touch(tmp, 'models/decoder-gpu-int8/tokenizer_config.json', b'{}')
        touch(tmp, 'ext/bridge/bridge_launcher.py', b'# launcher')
        bad = m.scan(tmp)
        check('干净目录 0 违规', not bad, str(bad))
        check('assert_clean 返回 0（允许交付）', m.assert_clean(tmp) == 0)

    # ③ 逐个注入缺陷 ⇒ 判据必须能识破
    print('\n[3] 注入反证（判据非恒真）')
    with tempfile.TemporaryDirectory(prefix='app307_bad_') as tmp:
        touch(tmp, 'ext/bridge_token.txt', b'gcJcbNA0szeY2QEn2H2idxvfutQkxlkx')
        check('注入固定 token ⇒ 被判出',
              len([b for b in m.scan(tmp) if b[1].endswith('token')]) == 1)
        for nm in ('cindy', 'lou', 'phil', 'steve'):
            for ext in ('json', 'npy'):
                touch(tmp, 'python/Lib/site-packages/babelvox/data/speakers/'
                      '%s.%s' % (nm, ext), b'x')
        check('注入 8 个第三方音色 ⇒ 全被判出',
              len([b for b in m.scan(tmp) if 'voice' in b[1]]) == 8)
        # 不该误伤的同名/近名文件
        touch(tmp, 'python/Lib/site-packages/babelvox/data/speakers/README.md',
              b'doc')
        touch(tmp, 'python/Lib/site-packages/babelvox/data/speakers/'
              'cindy_backup.json', b'{}')
        after = len([b for b in m.scan(tmp) if 'voice' in b[1]])
        check('README.md / cindy_backup.json 不被误伤（仍是 8）',
              after == 8, after)

    n_pass = sum(1 for c in CHECKS if c['ok'])
    n_fail = len(CHECKS) - n_pass
    out = dict(tool='_app307_assert_pkg_clean_selftest',
               app='APP-077(1)+APP-078(3)',
               ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               checks=CHECKS, n_pass=n_pass, n_fail=n_fail,
               verdict='PASS' if n_fail == 0 else 'FAIL',
               note=('v2.3 起建包脚本复制完目录后必须调用 '
                     '`python live_caption/assert_pkg_clean.py <新包目录>`；'
                     '违规 ⇒ 拒绝交付。本模块**只检查不删除**，'
                     '旧包不原地改（APP-055 / APP-078 ④）。'))
    with open(EV, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\nverdict = %s (%d PASS / %d FAIL)  %s'
          % (out['verdict'], n_pass, n_fail, EV))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
