#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §3/§4：把 MiniMVP v1.1.1 的包内元数据改成 **v1.1.1**。

## 做四件事
1. 🔴 **把 `app/tts_cuda.py` / `app/tts_cuda_sidecar.py` 改名挪到包外**
   （**不删**！）—— 理由（APP-121 §3）：
   * MiniMVP **无 CUDA** ⇒ 这两个文件本来就**不进 zip**（`pkg_exclude` 排除）；
   * 但它们**留在包目录里** ⇒ `pack_v13._acc_production_modules()` 会把它们
     算进 `ACCEPTED.json` 的 `code_fingerprints`
     ⇒ **「签的模块清单」里有 zip 里根本没有的文件**（reviewer 点名的缺陷）；
   * 挪走之后：① 包目录与 zip 内容一致；② 指纹集合 == zip 内 `app/*.py` 集合；
     ③ App 里 4 处 `import tts_cuda` **全在 try/except 里**（已逐处核对）
     ⇒ 功能不受影响（MiniMVP 本来就不该有 CUDA 后端）。
   🔴 **铁律**：本机安全删除会把文件转回收站 / 批量删被拦
      ⇒ **打包脚本一律不删** ⇒ 这里用「改名 + 挪到包外」。
2. `release.json`：version → **1.1.1**；`corrections` 加 APP-121；
   `asr_recipe` / 变更清单改成**面向客户**的措辞（去内部编号）。
3. `app/MANIFEST.json`：version → **1.1.1**；files/bytes 重算
   （用 `pkg_exclude.package_stats(..., skip=('app/MANIFEST.json',))`
   ⇒ 与 `iter_package_files` **同一口径**＝ zip 内容口径）。
4. 写证据 json（每个动作的「改前/改后」逐字段留档）。

## 用法
```
python live_caption/_app121_update_meta.py --pkg <v1.1.1 目录> [--apply]
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
sys.path.insert(0, REPO)

import pkg_exclude                                                  # noqa: E402

VERSION = '1.1.1'
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1.1')
#: 挪到包外（**不删**）的目录
OUTSIDE = os.path.join(HOME, 'shared', 'minimvp_v111_excluded')
#: MiniMVP 无 CUDA ⇒ 这两个文件不进 zip ⇒ 必须挪出包目录
MOVE_OUT = ['tts_cuda.py', 'tts_cuda_sidecar.py']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out', default=os.path.join(
        REPO, 'results', 'app', 'app121_update_meta.json'))
    args = ap.parse_args()
    pkg = os.path.abspath(args.pkg)
    if not os.path.isdir(pkg):
        print('FAIL: 包目录不存在 %s' % pkg)
        return 2

    res = {'script': '_app121_update_meta.py',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': pkg, 'version': VERSION, 'applied': bool(args.apply),
           'steps': []}

    # ── ① 挪出 tts_cuda*（改名 + 挪到包外，**不删**）───────────────
    moved = []
    for name in MOVE_OUT:
        src = os.path.join(pkg, 'app', name)
        if not os.path.isfile(src):
            moved.append({'file': name, 'action': 'absent（已不在包目录）'})
            continue
        rec = {'file': name, 'src': src, 'sha_before': sha(src),
               'bytes': os.path.getsize(src)}
        if args.apply:
            os.makedirs(OUTSIDE, exist_ok=True)
            dst = os.path.join(OUTSIDE, name)
            if os.path.exists(dst):
                dst = os.path.join(
                    OUTSIDE, '%s.app121_%s' % (name, time.strftime('%H%M%S')))
            shutil.move(src, dst)
            rec['dst'] = dst
            rec['action'] = 'moved out of package（改名挪到包外，**未删除**）'
            rec['sha_after'] = sha(dst)
        else:
            rec['action'] = 'dry-run：应挪到包外'
        moved.append(rec)
        print('  [%s] %s' % ('MOVE' if args.apply else 'DRY', name))
    res['steps'].append({'step': 'move_out_tts_cuda', 'rows': moved})

    # ── ② release.json ──────────────────────────────────────────
    rp = os.path.join(pkg, 'release.json')
    with open(rp, 'r', encoding='utf-8') as f:
        rel = json.load(f)
    before = json.loads(json.dumps(rel))
    rel['version'] = VERSION
    rel['asr_recipe'] = ('stateful INT8 with KV cache（NPU 上用 NPUW 运行时）；'
                         'NPU 档 prompt 上界 320 + 超长前缀按 token 左截断'
                         '（prefix_truncations 计数）')
    rel['corrections'] = sorted(set(list(rel.get('corrections') or [])
                                    + ['APP-120', 'APP-121']))
    rel['v%s_changes' % VERSION] = [
        '修掉 **NPU 档长段崩溃**：≥18.3 s 的段不再让识别线程退出'
        '（NPU 档 prompt 上界按 handoff 口径只算 prompt，不把生成预留算进去）',
        '单段解码出错**不再中断整条识别**（记日志 + 计数 + 跳过该段）',
        '重打 zip 并做**解压自检**（全新目录 + 全新用户目录跑 --check + GUI 冒烟）',
        'ACCEPTED 的模块清单与 zip 实际内容**完全一致**（无 CUDA 的包不再带 '
        'CUDA 后端模块）',
        'README 面向客户改写：去内部编号、补「密集讲话时配音滞后」已知问题、'
        '区分「配音首包」与「字幕出字延迟」两个数',
    ]
    res['steps'].append({'step': 'release.json',
                         'before': before, 'after': rel,
                         'sha_before': sha(rp)})
    if args.apply:
        write_json(rp, rel)
        res['steps'][-1]['sha_after'] = sha(rp)

    # ── ③ app/MANIFEST.json ─────────────────────────────────────
    mp = os.path.join(pkg, 'app', 'MANIFEST.json')
    with open(mp, 'r', encoding='utf-8') as f:
        man = json.load(f)
    man_before = json.loads(json.dumps(man))
    n_files, n_bytes = pkg_exclude.package_stats(
        pkg, skip=('app/MANIFEST.json',))
    man['version'] = VERSION
    man['files'] = n_files
    man['bytes'] = n_bytes
    man['notes'] = ('MiniMVP v%s：ASR=Qwen3-ASR 0.6B stateful INT8、'
                    'MT=Hy-MT2 INT8-CW、TTS=OpenVINO（无 CUDA）、'
                    '音色只有预设 A、无克隆、10 语种、'
                    '出厂默认 ASR=GPU.0/MT=GPU.0/TTS=NPU。'
                    'files/bytes 与 zip 内容同一口径（不含 MANIFEST 自身）。'
                    % VERSION)
    res['steps'].append({'step': 'app/MANIFEST.json',
                         'before': man_before, 'after': man,
                         'sha_before': sha(mp)})
    if args.apply:
        write_json(mp, man)
        res['steps'][-1]['sha_after'] = sha(mp)

    # ── ④ 复核：ACCEPTED 的模块清单 == zip 内容口径 ───────────────
    import pack_v13 as P
    prod = P._acc_production_modules(os.path.join(pkg, 'app'))
    files = list(pkg_exclude.iter_package_files(pkg))
    # 🔴 app191 口径：`os.listdir(app/)` **只看 app 根目录**（不含子目录）
    zip_root_py = sorted(r.split('/', 1)[1] for r, _s in files
                         if r.startswith('app/') and r.count('/') == 1
                         and r.endswith('.py'))
    zip_all_py = sorted(r.split('/', 1)[1] for r, _s in files
                        if r.startswith('app/') and r.endswith('.py'))
    res['consistency'] = {
        'n_production_modules': len(prod),
        'n_zip_app_root_py': len(zip_root_py),
        'n_zip_app_py_all': len(zip_all_py),
        'zip_app_subdir_py': [x for x in zip_all_py if '/' in x],
        'only_production': sorted(set(prod) - set(zip_root_py)),
        'only_zip_root': sorted(set(zip_root_py) - set(prod)),
        'fingerprint_subset_of_zip': set(prod) <= set(zip_all_py),
        'tts_cuda_in_zip': [x for x in zip_all_py if 'tts_cuda' in x],
        'tts_cuda_in_fingerprints': [x for x in prod if 'tts_cuda' in x],
        'consistent': (set(prod) == set(zip_root_py)
                       and not [x for x in prod if 'tts_cuda' in x]),
    }
    print('  模块集合一致：%s（生产模块 %d 个 / zip app 根目录 .py %d 个；'
          'zip 内 .py 合计 %d 个，其中子目录 %d 个）'
          % (res['consistency']['consistent'], len(prod), len(zip_root_py),
             len(zip_all_py), len(res['consistency']['zip_app_subdir_py'])))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.out)
    print('[app121] 证据 → %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
