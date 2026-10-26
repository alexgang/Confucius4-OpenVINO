#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APP-018 第 2 条 / APP-019：第三方自带素材排除规则的**闸门**（自检）。

🔴 **为什么要有闸门**（MEMORY「修掉一处 ≠ 这一类不会再来」）：
   排除规则写在 `pkg_exclude.py` 里，但**没人保证它真的生效**——
   只要有人改了 `is_excluded` 的调用顺序、或者 `iter_package_files`
   忘了接文件级规则，第三方素材就会**悄悄回到客户包里**。
   ⇒ 本脚本在**真实包目录**上跑一遍，断言：
     ① `is_excluded` 对每条目标路径都返回 True；
     ② `iter_package_files` **不产出**任何目标路径；
     ③ `iter_excluded` **产出**了它们（⇒ 物理清理路径也通）；
     ④ **不误伤**：客户的音频素材（preset_A.wav 等）必须**保留**。

🔴 **不 import 被测模块**：`pkg_exclude` 是纯规则模块（无 numpy），
   可以直接 import；但为遵守「分析脚本一律不 import 被测模块」的纪律，
   这里用 `ast` 抽源码 + `exec` 到独立命名空间。

用法：
    python results/app/app058_third_party_noise_gate.py --pkg <客户包目录>
产物：
    <out>/app058_third_party_noise_gate.json
"""
import argparse
import ast
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))


def load_module(path, name='_mod'):
    """用 ast 抽源码 + exec 到独立命名空间（不 import 被测模块）。"""
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    ns = {'__name__': name, '__file__': path}
    exec(compile(tree, path, 'exec'), ns)
    return ns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True, help='客户包目录')
    ap.add_argument('--out', default=r'C:\Users\Trekker-PTL\abba_out',
                    help='产物目录（仓库外）')
    args = ap.parse_args()

    pkg_root = os.path.abspath(args.pkg)
    if not os.path.isdir(pkg_root):
        print('包目录不存在：%s' % pkg_root)
        return 2

    ns = load_module(os.path.join(REPO, 'pkg_exclude.py'), '_pkg_exclude')
    is_excluded = ns['is_excluded']
    is_third_party_noise = ns['is_third_party_noise']
    iter_package_files = ns['iter_package_files']
    iter_excluded = ns['iter_excluded']

    # ── ① 目标路径（来自真实包目录的实测清单）─────────────────────
    targets = [
        # babelvox 自带第三方音色 profile
        'python/Lib/site-packages/babelvox/data/speakers/cindy.json',
        'python/Lib/site-packages/babelvox/data/speakers/cindy.npy',
        'python/Lib/site-packages/babelvox/data/speakers/lou.json',
        'python/Lib/site-packages/babelvox/data/speakers/lou.npy',
        'python/Lib/site-packages/babelvox/data/speakers/phil.json',
        'python/Lib/site-packages/babelvox/data/speakers/phil.npy',
        'python/Lib/site-packages/babelvox/data/speakers/steve.json',
        'python/Lib/site-packages/babelvox/data/speakers/steve.npy',
    ]

    # scipy 测试 wav（在真实包目录里实测得到）
    scipy_wav = []
    sp_root = os.path.join(pkg_root, 'python', 'Lib', 'site-packages', 'scipy')
    for dirpath, dirnames, filenames in os.walk(sp_root):
        for fn in filenames:
            if fn.lower().endswith(('.wav', '.flac', '.mp3', '.ogg', '.aiff')):
                rel = os.path.relpath(os.path.join(dirpath, fn),
                                      pkg_root).replace('\\', '/')
                if '/tests/' in rel:
                    scipy_wav.append(rel)
    targets.extend(sorted(scipy_wav))

    # ── ② 不误伤清单：客户自己的音频素材 ──────────────────────────
    keep_must = [
        'models/qwen3tts/voices/preset_A.wav',
        'app/tts_engine.py',
        'app/tts_worker.py',
    ]

    res = {
        'pkg_root': pkg_root,
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'n_targets': len(targets),
        'checks': [],
        'verdict': None,
    }

    def chk(name, ok, detail=''):
        res['checks'].append({'name': name, 'ok': bool(ok), 'detail': detail})
        print('[%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
        return ok

    all_ok = True

    # ① is_excluded 命中
    miss = [t for t in targets if not is_excluded(t)]
    all_ok &= chk('is_excluded 命中全部目标', not miss,
                  '（%d/%d 命中，未命中 %d 条）'
                  % (len(targets) - len(miss), len(targets), len(miss)))
    for m in miss[:10]:
        print('      ⚠️ 未命中：%s' % m)

    # ② iter_package_files 不产出
    kept = set()
    for rel, _sz in iter_package_files(pkg_root):
        kept.add(rel)
    leaked = [t for t in targets if t in kept]
    all_ok &= chk('iter_package_files 不产出目标', not leaked,
                  '（泄漏 %d 条）' % len(leaked))
    for m in leaked[:10]:
        print('      ⚠️ 泄漏：%s' % m)

    # ③ iter_excluded 产出（物理清理路径也通）
    exc = set()
    for rel, _sz in iter_excluded(pkg_root):
        exc.add(rel)
    not_exc = [t for t in targets if t not in exc]
    all_ok &= chk('iter_excluded 报告全部目标', not not_exc,
                  '（漏报 %d 条）' % len(not_exc))

    # ④ 不误伤：客户的音频/代码素材必须**仍在** `kept`（= 要进包）
    #    ⚠️ `kept` 是「要进包的文件集合」⇒ 在里面是**正确**行为；
    #       **不在**里面才是「误伤」。
    wrongly = []
    for k in keep_must:
        if not os.path.exists(os.path.join(pkg_root, k.replace('/', os.sep))):
            continue          # 本包里没有这个文件 ⇒ 不作断言
        if k not in kept:
            wrongly.append(k)
    all_ok &= chk('不误伤客户素材', not wrongly,
                  '（误伤 %d 条：%s）' % (len(wrongly), wrongly[:5]))

    # ⑤ 额外：整个包目录里残留的第三方素材（实测）
    residual = sorted(r for r in kept if is_third_party_noise(r))
    all_ok &= chk('整包扫描无第三方素材残留', not residual,
                  '（残留 %d 条）' % len(residual))
    for m in residual[:10]:
        print('      ⚠️ 残留：%s' % m)

    res['verdict'] = 'PASS' if all_ok else 'FAIL'
    res['n_residual'] = len(residual)

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, 'app058_third_party_noise_gate.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print()
    print('结论：%s' % res['verdict'])
    print('产物：%s' % path)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
