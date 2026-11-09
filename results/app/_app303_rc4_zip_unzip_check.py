#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app303_rc4_zip_unzip_check.py —— **rc4 zip 的落地验收**（解压 + `--check`）。

## 为什么要有这个脚本（用户验收要求 3）

> - **从干净目录解压后**用 NPU 模式启动 ASR，日志里 encoder 和 decoder 的
>   实际执行设备都是 NPU；

zip 造出来 ≠ zip 能用。⇒ 必须**真的解压一遍**再验。

## 本脚本做三件事

① **解压** rc4 zip 到**全新的干净目录**（`C:\\minimvp_rc4_ziptest\\`）
   ⇒ 用**包内自带的 python** 跑 `--check`（不用开发机 python！）。
② 跑 `--check`，抓「**Intel NPU · INT8  模型齐全**」这一行。
③ 再跑一次**执行设备直证**（`npu_delivery_backend` + `EXECUTION_DEVICES`）
   ⇒ 证明**从 zip 解出来的**包，encoder/decoder 仍都落在 NPU。

## 🔴 纪律
* 解压目录**先删后建** ⇒ 绝不复用旧目录（否则「干净」就不成立）。
* 持 `MACHINE_LOCK`（编译要占 NPU）。
* 缓存写**独立临时目录** ⇒ 不复用本机 Panther Lake 的编译产物来冒充证据。

用法：
    .venv/Scripts/python.exe results/app/_app303_rc4_zip_unzip_check.py
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
ZIP = os.path.join(HOME, 'shared', 'minimvp',
                   'Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip')
DEST = r'C:\minimvp_rc4_ziptest'
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4'
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
EVID = os.path.join(HERE, 'app303_rc4_zip_unzip_check_evidence.json')


def now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def acquire_lock(tag: str) -> int:
    for _t in range(3):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write('module=app\npid=%d\nstart=%s\ntag=%s\n'
                        % (os.getpid(), now(), tag))
            return os.getpid()
        except FileExistsError:
            print('🔴 锁已存在 ⇒ 等 20 s', flush=True)
            time.sleep(20)
    return -1


def release_lock() -> None:
    try:
        if os.path.exists(LOCK):
            cur = open(LOCK, encoding='utf-8', errors='replace').read()
            if ('pid=%d' % os.getpid()) in cur:
                os.remove(LOCK)
                print('🔓 锁已释放', flush=True)
    except Exception as e:
        print('⚠️ 释放锁失败：%s' % e, flush=True)


def main() -> int:
    res = {'script': os.path.basename(__file__), 'ts': now(),
           'zip': ZIP, 'dest': DEST}
    if not os.path.isfile(ZIP):
        res['verdict'] = 'ZIP_MISSING'
        _write(res)
        return 2

    # ── ① 解压（先删后建 ⇒ 真「干净」）─────────────────────
    if os.path.isdir(DEST):
        shutil.rmtree(DEST, ignore_errors=True)
    os.makedirs(DEST, exist_ok=True)
    t0 = time.perf_counter()
    zf = zipfile.ZipFile(ZIP)
    infos = [i for i in zf.infolist() if not i.is_dir()]
    zf.extractall(DEST)
    zf.close()
    res['extract_s'] = round(time.perf_counter() - t0, 2)
    res['n_zip_entries'] = len(infos)
    pkg = os.path.join(DEST, PKG_NAME)
    res['pkg'] = pkg
    res['pkg_exists'] = os.path.isdir(pkg)
    py = os.path.join(pkg, 'python', 'python.exe')
    res['pkg_python_exists'] = os.path.isfile(py)
    if not res['pkg_exists'] or not res['pkg_python_exists']:
        res['verdict'] = 'EXTRACT_FAILED'
        _write(res)
        print('🔴 解压后结构不对', flush=True)
        return 2

    pid = acquire_lock('app303_rc4_zip_unzip_check')
    if pid < 0:
        res['verdict'] = 'LOCK_BUSY'
        _write(res)
        print('🔴 拿不到锁 ⇒ 放弃（不抢锁）')
        return 2
    print('🔒 MACHINE_LOCK pid=%d' % pid, flush=True)
    try:
        # ── ② `--check`（用**包内 python**）──────────────────
        t1 = time.perf_counter()
        cp = subprocess.run([py, os.path.join(pkg, 'app', 'live_caption_app.py'),
                             '--check'], cwd=pkg, capture_output=True,
                            text=True, encoding='utf-8', errors='replace',
                            timeout=900)
        res['check_rc'] = cp.returncode
        res['check_wall_s'] = round(time.perf_counter() - t1, 2)
        res['check_output'] = (cp.stdout or '')[-4000:]
        npu_lines = [l.strip() for l in (cp.stdout or '').splitlines()
                     if 'Intel NPU' in l and '模型' in l]
        res['npu_model_lines'] = npu_lines
        res['npu_int8_ready'] = any(
            l.startswith('[ OK ]') and 'Intel NPU · INT8' in l
            and '模型齐全' in l for l in npu_lines)
        print('★ NPU 模型行：%s' % npu_lines, flush=True)

        # ── ③ 执行设备直证（**从 zip 解出来的包**）───────────
        import tempfile
        cache = os.path.join(tempfile.gettempdir(), 'app303_npu_cache')
        os.makedirs(cache, exist_ok=True)
        probe = os.path.join(HERE, '_app303_exec_probe.py')
        with open(probe, 'w', encoding='utf-8', newline='\n') as f:
            f.write(_PROBE_SRC)
        cp2 = subprocess.run([py, probe], cwd=pkg, capture_output=True,
                             text=True, encoding='utf-8', errors='replace',
                             timeout=1800, env=dict(os.environ,
                                                   APP303_NPU_CACHE=cache,
                                                   APP303_PKG=pkg))
        res['probe_rc'] = cp2.returncode
        res['probe_stdout_tail'] = (cp2.stdout or '')[-1500:]
        try:
            with open(os.path.join(HERE, 'app303_exec_probe_out.json'),
                      encoding='utf-8') as f:
                res['probe'] = json.load(f)
        except Exception:
            res['probe'] = None
        res['probe_stderr_tail'] = (cp2.stderr or '')[-800:]
    finally:
        release_lock()

    res['verdict'] = ('UNZIP_CHECK_OK'
                      if res.get('npu_int8_ready')
                      and (res.get('probe') or {}).get('verdict')
                      == 'EXEC_ON_NPU_OK'
                      else 'UNZIP_CHECK_FAILED')
    _write(res)
    print(json.dumps({k: res.get(k) for k in
                      ('extract_s', 'n_zip_entries', 'check_rc',
                       'npu_model_lines', 'npu_int8_ready', 'probe_rc',
                       'verdict')}, ensure_ascii=False, indent=1))
    print('执行设备：%s' % json.dumps(
        (res.get('probe') or {}).get('exec_devices'), ensure_ascii=False))
    return 0 if res['verdict'] == 'UNZIP_CHECK_OK' else 1


_PROBE_SRC = '''# -*- coding: utf-8 -*-
"""app303 执行设备直证（跑在**从 zip 解出来的包**里）。"""
import json, os, sys
PKG = os.environ.get('APP303_PKG')
CACHE = os.environ.get('APP303_NPU_CACHE')
sys.path.insert(0, os.path.join(PKG, 'app'))
os.chdir(os.path.join(PKG, 'app'))
import numpy as np
import openvino as ov
import npu_embeds_backend
from npu_delivery_backend import make_delivery_all_npu_backend
npy = os.path.join(PKG, 'models', 'embed_tokens_f16.npy')
npu_embeds_backend._load_embed_table = lambda: np.asarray(np.load(npy), dtype=np.float32)
AL = {'ov-encoder-segment-reviewer': ['encoder-fp16'],
      'qwen3-lm-int8sym-cleanie-ov': ['decoder-npu-int8'],
      'ov-int8-past': ['decoder-gpu-int8']}
def mp(logical):
    m = os.path.join(PKG, 'models')
    for a in AL.get(logical, []):
        p = os.path.join(m, *a.split('/'))
        if os.path.exists(p):
            return p
    return os.path.join(m, *logical.split('/'))
be = make_delivery_all_npu_backend(
    encoder_dir=mp('ov-encoder-segment-reviewer'),
    decoder_dir=mp('qwen3-lm-int8sym-cleanie-ov'),
    tokenizer_dir=mp('ov-int8-past'), npu_cache=CACHE)
def ed(cm):
    try:
        d = cm.get_property('EXECUTION_DEVICES')
        return list(d) if isinstance(d, (list, tuple)) else str(d)
    except Exception as e:
        return 'ERR:%s' % e
def only(v):
    parts = [x.strip() for x in v.split(',')] if isinstance(v, str) else [str(x) for x in v]
    return len(parts) > 0 and all(p.upper().startswith('NPU') for p in parts)
enc = ed(be.enc); dec = ed(be.dec)
res = {'encoder_exec_devices': enc, 'decoder_exec_devices': dec,
       'encoder_on_npu_only': only(enc), 'decoder_on_npu_only': only(dec),
       'ov_version': ov.__version__, 'cache': CACHE,
       'npu_enc_compile_s': getattr(be, 'npu_enc_compile_s', None),
       'npu_dec_compile_s': getattr(be, 'npu_compile_s', None)}
res['verdict'] = ('EXEC_ON_NPU_OK' if res['encoder_on_npu_only']
                   and res['decoder_on_npu_only'] else 'EXEC_NOT_ALL_NPU')
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'app303_exec_probe_out.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
'''


def _write(obj: dict) -> None:
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    raise SystemExit(main())
