#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app296_rc4_exec_device.py —— **rc4 包内 NPU 后端的「实际执行设备」直证**。

## 用户验收要求（原文）

> - 从干净目录解压后用 NPU 模式启动 ASR，**日志里 encoder 和 decoder 的
>   实际执行设备都是 NPU**；

## 为什么需要这个脚本（App 日志不够）

App 的 CLI 日志只打了一行 `[npu_int8] 加载 3.0 s，设备 NPU`
⇒ 那是 **App 自己声称的**（`self.device_desc = 'NPU'`），
**不是** OpenVINO 层面的事实。

⇒ 本脚本**在干净目录里**用**包内自己的 python**，
按 App 的同一路径 `npu_delivery_backend.make_delivery_all_npu_backend()`
把后端造出来，然后**读编译产物的 `EXECUTION_DEVICES` 属性**：

    be.enc  → encoder 的实际落点
    be.dec  → decoder 的实际落点

⚠️ **必须是「包内 python」**：包内 python 带的是**随包发版的 OV 2026.4.1**，
而开发机 .venv 的 OV 版本可能不同 ⇒ 验收要用**客户环境的那一份**。

## 🔴 纪律
* 在**干净目录**（`C:\\minimvp_rc4_clean\\...`）里跑 ⇒ 不碰用户安装目录。
* 持 `MACHINE_LOCK`（编译要占 NPU）。
* 缓存写**独立临时目录** ⇒ 不污染用户已有缓存（也不复用 Panther Lake 的
  产物来冒充可移植性证据）。

用法：
    C:\\minimvp_rc4_clean\\Confucius4_LiveCaption_MiniMVP_v1.0-rc4\\python\\python.exe \
        results/app/_app296_rc4_exec_device.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
PKG = os.path.join('C:\\', 'minimvp_rc4_clean',
                   'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
EVID = os.path.join(REPO, 'results', 'app',
                    'app296_rc4_exec_device_evidence.json')


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


def exec_devices(cm) -> object:
    try:
        d = cm.get_property('EXECUTION_DEVICES')
        return list(d) if isinstance(d, (list, tuple)) else str(d)
    except Exception as e:
        return 'ERR:%s' % e


def main() -> int:
    res = {'script': os.path.basename(__file__), 'ts': now(), 'pkg': PKG,
           'python': sys.executable}
    sys.path.insert(0, os.path.join(PKG, 'app'))
    os.chdir(os.path.join(PKG, 'app'))

    pid = acquire_lock('app296_rc4_exec_device')
    if pid < 0:
        print('🔴 拿不到锁 ⇒ 放弃')
        res['verdict'] = 'LOCK_BUSY'
        _write(res)
        return 2
    print('🔒 MACHINE_LOCK pid=%d' % pid, flush=True)
    try:
        import numpy as np
        import openvino as ov
        res['ov_version'] = ov.__version__
        core = ov.Core()
        res['available_devices'] = list(core.available_devices)
        for k, p in (('npu_full_name', 'FULL_DEVICE_NAME'),
                     ('npu_driver', 'NPU_DRIVER_VERSION'),
                     ('npu_arch', 'DEVICE_ARCHITECTURE')):
            try:
                res[k] = core.get_property('NPU', p)
            except Exception as e:
                res[k] = 'ERR:%s' % e

        # 🔴 与 App **同一路径**：npu_delivery_backend.make_delivery_all_npu_backend
        from npu_delivery_backend import make_delivery_all_npu_backend
        import npu_embeds_backend
        # embedding 表：从包内 models/ 根读（App 的同一做法）
        npy = os.path.join(PKG, 'models', 'embed_tokens_f16.npy')
        npu_embeds_backend._load_embed_table = \
            lambda: np.asarray(np.load(npy), dtype=np.float32)

        # 🔴🔴 **模型目录必须按 App 的 `_MODEL_ALIASES` 解析**
        # （第一版直接用 `DEFAULT_ENCODER_DIR` ⇒ 找的是**开发机目录名**
        #   `models/ov-encoder-segment-reviewer` ⇒ 包内不存在 ⇒ read_model 失败）
        # App 的解析链（live_caption_app.py::_model_path）：
        #   逻辑名 → 别名列表 → <包根>/models/<别名> → 否则 <包根>/models/<逻辑名>
        _ALIASES = {
            'ov-encoder-segment-reviewer': ['encoder-fp16'],
            'qwen3-lm-int8sym-cleanie-ov': ['decoder-npu-int8'],
            'c089_int4/R4': ['decoder-npu-int4'],
            'ov-int8-past': ['decoder-gpu-int8'],
        }

        def model_path(logical: str) -> str:
            models = os.path.join(PKG, 'models')
            for alias in _ALIASES.get(logical, []):
                p = os.path.join(models, *alias.split('/'))
                if os.path.exists(p):
                    return p
            return os.path.join(models, *logical.split('/'))

        cache = os.path.join(tempfile.gettempdir(), 'app296_npu_cache')
        os.makedirs(cache, exist_ok=True)
        enc_dir = model_path('ov-encoder-segment-reviewer')
        dec_dir = model_path('qwen3-lm-int8sym-cleanie-ov')
        # tokenizer 目录 = decoder-gpu-int8（_MODEL_ALIASES: ov-int8-past）
        tok_dir = model_path('ov-int8-past')
        res['resolved_dirs'] = {'encoder': enc_dir, 'decoder': dec_dir,
                                'tokenizer': tok_dir}
        for k, p in res['resolved_dirs'].items():
            print('  %-10s -> %s  exists=%s' % (k, p, os.path.isdir(p)),
                  flush=True)

        t0 = time.perf_counter()
        be = make_delivery_all_npu_backend(
            encoder_dir=enc_dir, decoder_dir=dec_dir,
            tokenizer_dir=tok_dir, npu_cache=cache)
        res['backend_build_s'] = round(time.perf_counter() - t0, 2)
        res['npu_enc_compile_s'] = getattr(be, 'npu_enc_compile_s', None)
        res['npu_dec_compile_s'] = getattr(be, 'npu_compile_s', None)
        res['npu_props'] = getattr(be, '_npu_props', None)

        res['encoder_exec_devices'] = exec_devices(be.enc)
        res['decoder_exec_devices'] = exec_devices(be.dec)

        # 🔴 判据：**两个都必须只含 NPU**
        # ⚠️ OV 的 `EXECUTION_DEVICES` 在本版本返回**字符串** `'NPU'`
        #    （不是 list）⇒ 判据要两种形态都认，否则会**假 FAIL**。
        def only_npu(v):
            if isinstance(v, str):
                parts = [x.strip() for x in v.split(',') if x.strip()]
            elif isinstance(v, (list, tuple)):
                parts = [str(x) for x in v]
            else:
                return False
            return (len(parts) > 0
                    and all(p.upper().startswith('NPU') for p in parts))
        res['encoder_on_npu_only'] = only_npu(res['encoder_exec_devices'])
        res['decoder_on_npu_only'] = only_npu(res['decoder_exec_devices'])
        res['verdict'] = ('EXEC_ON_NPU_OK'
                          if res['encoder_on_npu_only']
                          and res['decoder_on_npu_only']
                          else 'EXEC_NOT_ALL_NPU')
        print('★ encoder EXECUTION_DEVICES = %s'
              % res['encoder_exec_devices'])
        print('★ decoder EXECUTION_DEVICES = %s'
              % res['decoder_exec_devices'])
        print('★ %s' % res['verdict'])
    except Exception as e:
        import traceback
        res['error'] = traceback.format_exc()[:2000]
        res['verdict'] = 'ERROR'
        print(res['error'], flush=True)
    finally:
        release_lock()

    _write(res)
    print(json.dumps({'out': EVID, 'verdict': res.get('verdict')},
                     ensure_ascii=False))
    return 0


def _write(obj: dict) -> None:
    os.makedirs(os.path.dirname(EVID), exist_ok=True)
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    raise SystemExit(main())
