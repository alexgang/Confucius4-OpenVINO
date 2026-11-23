#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §2：**给 MiniMVP v1.1.1 打 zip**（新文件名，**不覆盖任何旧 zip**）。

## 为什么不用 `pack_v13.py`
🔴 `pack_v13.py` **启动即把源目录改名到新版本号** ⇒ 中止会白吃版本号
   ⇒ 它是「完整版形态」的打包器，MiniMVP v1.1 的目录名已定 ⇒ 不用它。

## 本脚本的口径
- 文件清单 = **`pkg_exclude.iter_package_files()`**（与出包闸门同一套排除规则
  ⇒ zip 里**不含** `__pycache__`／备份目录／babelvox 示例音色等）；
- 写 `ZIP + '.tmp'` → **校验**（`testzip()` + 关键文件 + 清单一致）
  → `os.replace()` 原子改名 ⇒ **失败时旧 zip 完好无损**；
- 🔴 **绝不删除、绝不覆盖**任何既有 zip / 目录。

## 用法
```
python live_caption/_app120_zip_v11.py --dry-run
python live_caption/_app120_zip_v11.py --apply
```
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
sys.path.insert(0, REPO)

import pkg_exclude                                                  # noqa: E402

PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1.1')
RESULTS = os.path.join(REPO, 'results', 'app')

#: zip 内必须有的关键文件（相对包根）
MUST = [
    'app/live_caption_app.py',
    'app/device_config.py',
    'app/asr06b_stateful_backend.py',
    'app/tts_worker.py',
    'app/MANIFEST.json',
    'models/asr06b-decoder-int8/openvino_model.xml',
    'models/asr06b-encoder-fp16/ov-encoder-06b-fp16-static.xml',
    # 🔴 **目录项**（MT 模型是 12 个文件的目录，不是单个文件）
    #   ⇒ **不能**用 `prefix + rel in namelist` 判存在（zip 的 namelist
    #   **只含文件条目**，目录不会单独出现）
    #   ⇒ 判「该目录**下至少有一个文件**进了 zip」。
    'models/mt/mt2-int8sym-cw-q',
    'models/qwen3tts/voices/preset_A.wav',
    'package_profile.json',
    'release.json',
    'README_zh.md',
    'README_en.md',
    'ACCEPTED.json',
    'Start_LiveCaption.bat',
    'Start_Bridge.bat',
    'Diagnose.bat',
]


def check_must(pkg, names, prefix, must=None):
    """🔴 判「zip 内 MUST 齐全」。

    🔴🔴 **目录项的判法**（2026-11-22 实测踩坑）：zip 的 `namelist` **只含文件条目**，
       目录本身**不会**单独出现 ⇒ 目录型 MUST（如 `models/mt/mt2-int8sym-cw-q`）
       用 `prefix+rel in namelist` 判**永远 False** ⇒ 会把好包误判成「关键文件缺失」。
       ⇒ 目录项改判「该目录**下至少有一个文件**进了 zip」。
    """
    must = MUST if must is None else must
    miss = []
    for m in must:
        if (prefix + m) in names:
            continue
        if os.path.isdir(os.path.join(pkg, m.replace('/', os.sep))):
            if any(x.startswith(prefix + m + '/') for x in names):
                continue
        miss.append(m)
    return miss


def self_test():
    """🔴 **闸门自身的反证自测**（§190「闸门自己的判据也会错」）。

    ① 正例：目录型 MUST 在 zip 里**只有文件** ⇒ **不应**被判缺失；
    ② 反例：真的缺一个文件 ⇒ **必须**被判缺失（证明闸门不是 fail-open）。
    """
    import tempfile
    import shutil
    tmp = tempfile.mkdtemp(prefix='app120_zipselftest_')
    try:
        d = os.path.join(tmp, 'pkg')
        os.makedirs(os.path.join(d, 'models', 'mt', 'mt2-x'))
        with open(os.path.join(d, 'models', 'mt', 'mt2-x', 'config.json'), 'w') as f:
            f.write('{}')
        with open(os.path.join(d, 'app.py'), 'w') as f:
            f.write('# x')
        prefix = 'PKG/'
        names = {prefix + 'app.py', prefix + 'models/mt/mt2-x/config.json'}
        must = ['models/mt/mt2-x', 'app.py']
        miss_ok = check_must(d, names, prefix, must)
        names_bad = {prefix + 'app.py'}          # 删掉目录下的文件
        miss_bad = check_must(d, names_bad, prefix, must)
        cases = [
            ('① 目录型 MUST（有文件）⇒ 不判缺失', miss_ok == [], str(miss_ok)),
            ('② 真的缺文件 ⇒ 判缺失（不 fail-open）',
             miss_bad == ['models/mt/mt2-x'], str(miss_bad)),
        ]
        ok = True
        for n, c, dtl in cases:
            print('  [%s] %s%s' % ('PASS' if c else 'FAIL', n,
                                   '' if c else ' :: ' + dtl))
            ok = ok and c
        print('[self-test] %d/%d PASS' % (sum(1 for _n, c, _d in cases if c), len(cases)))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--level', type=int, default=6)
    ap.add_argument('--apply', action='store_true', help='真正写 zip（默认 dry-run）')
    ap.add_argument('--no-lock', action='store_true',
                    help='不取共享机器锁（默认取；打 zip 是重 IO 作业，会干扰其它模块计时）')
    ap.add_argument('--self-test', action='store_true',
                    help='只跑 MUST 闸门的反证自测（临时目录 ⇒ 零写客户包）')
    args = ap.parse_args()
    if args.self_test:
        print('[self-test] MUST 闸门反证自测（临时目录 ⇒ 零写客户包）')
        return self_test()
    pkg = os.path.abspath(args.pkg)
    if not os.path.isdir(pkg):
        print('FAIL: 包目录不存在 %s' % pkg)
        return 2
    base = os.path.basename(pkg)
    zip_path = os.path.join(HOME, base + '.zip')

    files = list(pkg_exclude.iter_package_files(pkg))
    total_raw = sum(s for _r, s in files)
    print('=== APP-121 §5 打 zip（MiniMVP v1.1.1）===')
    print('包目录：%s' % pkg)
    print('zip 目标：%s' % zip_path)
    print('进包文件：%d 个 / 原始 %d B（%.3f GiB）'
          % (len(files), total_raw, total_raw / 1024 ** 3))
    if os.path.exists(zip_path):
        print('⚠️ 目标 zip **已存在** ⇒ 本脚本**不覆盖**（APP-055：新版本号 ⇒ 新 zip）')
        return 2

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    t0 = time.time()
    tmp = zip_path + '.tmp'
    n = 0
    # 🔴🔴🔳 **共享机器锁**（与 `pack_v13.py` 同一套纪律）：
    #   打 zip 是**重 IO 作业**（6.2 GiB 读写）⇒ 会拖慢别的模块 ⇒ 必须持锁。
    #   🔴 **锁已存在 ⇒ 排队等待，不抢**（`LockHeld` 内部按 timeout 轮询）。
    lk = None
    if not args.no_lock:
        try:
            import machine_lock_app
        except Exception as e:
            print('⚠️ 无法 import machine_lock_app（%r）⇒ 未持共享机器锁' % e)
        else:
            # 🔴🔴 **必须显式 `acquire()`**：`LockHeld.__init__` **不会**取锁
            #   （它只是把参数存下来；`__enter__` 才调 acquire）⇒
            #   只 new 不 acquire ⇒ **裸奔打包**（不持锁 ⇒ 污染别的模块计时）。
            #   实测（2026-11-22 16:34）：第一次跑就是漏了 acquire ⇒
            #   `shared/MACHINE_LOCK` 全程不存在 ⇒ 已中止并重跑。
            print('[lock] 等待共享机器锁（最多等 10800 s）…')
            lk = machine_lock_app.LockHeld(module='app-pack', timeout=10800)
            if not lk.acquire():
                print('!! 未能取得共享机器锁 ⇒ 拒绝打包'
                      '（避免干扰其它模块计时）')
                return 1
            print('[lock] 已取共享机器锁：%s' % machine_lock_app.LOCK)
    try:
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=args.level, allowZip64=True) as zf:
            for rel, size in files:
                full = os.path.join(pkg, rel.replace('/', os.sep))
                zf.write(full, '%s/%s' % (base, rel))
                n += 1
                if n % 2000 == 0:
                    print('  ... %d 文件（%.1f min）'
                          % (n, (time.time() - t0) / 60), flush=True)
        print('写入完成：%d 文件 / %.1f min' % (n, (time.time() - t0) / 60))

        # ── 校验（在临时文件上做；失败则不动任何既有 zip）────────────
        with zipfile.ZipFile(tmp, 'r') as zf:
            bad = zf.testzip()
            names = set(zf.namelist())
            prefix = base + '/'
            miss = check_must(pkg, names, prefix)
            n_in_zip = len([x for x in names if x.startswith(prefix)])
        sz = os.path.getsize(tmp)
        print('testzip() = %s' % ('OK' if bad is None else 'BAD:%s' % bad))
        print('zip 内文件数 = %d（清单 %d）' % (n_in_zip, len(files)))
        print('关键文件缺失 = %s' % (miss or '无'))
        print('压缩后 %d B（%.3f GiB），压缩率 %.1f%%'
              % (sz, sz / 1024 ** 3, sz / total_raw * 100))
        if bad is not None or miss or n_in_zip != len(files):
            os.remove(tmp)
            print('!! 校验失败 ⇒ 已删除临时 zip，未产生任何正式 zip')
            return 1

        os.replace(tmp, zip_path)
    except BaseException as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        print('!! 打包失败（未产生任何正式 zip）：%s: %s'
              % (type(e).__name__, e))
        return 1
    finally:
        # 🔴 **所有退出路径都要放锁**（含校验失败 / 异常）⇒ 否则锁会一直卡住别的模块。
        if lk is not None:
            try:
                lk.release()
                print('[lock] 已放共享机器锁')
            except Exception as e:
                print('⚠️ 放锁失败：%r' % e)

    final_sz = os.path.getsize(zip_path)
    ev = {'script': '_app121_zip_v111.py', 'pkg': pkg, 'zip': zip_path,
          'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
          'n_files': len(files), 'raw_bytes': total_raw,
          'zip_bytes': final_sz,
          'zip_gib': round(final_sz / 1024 ** 3, 3),
          'compress_ratio_pct': round(final_sz / total_raw * 100, 1),
          'wall_s': round(time.time() - t0, 1),
          'prefix': base, 'missing_must': []}
    os.makedirs(RESULTS, exist_ok=True)
    op = os.path.join(RESULTS, 'app121_zip_v111.json')
    tmpj = op + '.tmp'
    with open(tmpj, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    os.replace(tmpj, op)
    print('zip 完成：%s（%d B）' % (zip_path, final_sz))
    print('证据 → %s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
