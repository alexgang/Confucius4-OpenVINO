#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app290_npu_props_variants.py —— **NPU 属性变体探针**（Meteor Lake 可移植性）。

## 起因（app289 探针结果）

在 **Panther Lake**（本机，Ultra 7 356H / NPU arch 5010 / 驱动 20114005）实测：

| 臂 | 结果 | 原因 |
|---|---|---|
| encoder + NPUW | ❌ | `StatefulToStateless` 要求 `beam_idx` ⇒ NPUW 把 encoder 当 LLM 了 |
| encoder + plain | ❌ | `IE.Reshape doesn't support dynamic shapes` ⇒ **没冻结形状** |
| decoder + NPUW | ✅ 8.79 s，EXECUTION_DEVICES=NPU | |
| decoder + plain | ❌ | `to_shape was called on a dynamic shape` |

⇒ **两个关键结论**：
1. **decoder 必须走 NPUW**（plain 编不过动态形状）⇒
   「去掉 NPU 专用配置」这条路对 decoder **走不通**。
2. **encoder 必须先冻结形状**（`npu_delivery_backend._freeze_encoder_for_npu`）
   ⇒ app289 探针漏了这一步 ⇒ 它的 encoder 两臂都失败是**探针缺陷**，
   不是产品缺陷。本脚本补上冻结。

## 本脚本要回答的（决定 rc4 的回落策略）

* **decoder 能不能只开 `NPU_USE_NPUW`（不开 `NPUW_LLM`）？**
  ⇒ 若能 ⇒ 目标机（Meteor Lake）可以用**更保守**的属性集。
* **decoder 用 plain（完全不开 NPUW）能不能靠 reshape 救回来？**
  ⇒ 若能 ⇒ 目标机 NPUW 不可用时有**第二条路**。
* **encoder 冻结后 + plain 能不能编？**
  ⇒ 若能 ⇒ encoder 完全不需要 NPUW（只 decoder 需要）⇒ 风险面更小。

## 🔴 纪律
* 持 MACHINE_LOCK；只编译不推理；缓存写独立临时目录。

用法：
    .venv/Scripts/python.exe results/app/_app290_npu_props_variants.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
EVID = os.path.join(HERE, 'app290_npu_props_variants_evidence.json')
SRC_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.4')
ENC_DIR = os.path.join(SRC_PKG, 'models', 'encoder-fp16')
DEC_DIR = os.path.join(SRC_PKG, 'models', 'decoder-npu-int8')
MAX_FRAMES = 2400


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


def freeze_encoder(core, model, max_frames: int):
    """🔴 与 `npu_delivery_backend._freeze_encoder_for_npu` **同一口径**。"""
    import openvino as ov
    smap = {model.input(0): ov.PartialShape([1, 128, max_frames]),
            model.input(1): ov.PartialShape([1])}
    frozen = model.reshape(smap)
    return frozen if frozen is not None else model


def try_compile(core, model, props, label, device='NPU') -> dict:
    t0 = time.perf_counter()
    try:
        cm = core.compile_model(model, device, props)
    except Exception as e:
        return {'label': label, 'ok': False,
                'wall_s': round(time.perf_counter() - t0, 2),
                'error': ('%s: %s' % (type(e).__name__, str(e)))[:700]}
    wall = round(time.perf_counter() - t0, 2)
    out = {'label': label, 'ok': True, 'wall_s': wall, 'props': props}
    try:
        devs = cm.get_property('EXECUTION_DEVICES')
        out['execution_devices'] = list(devs) if isinstance(devs, (list, tuple)) \
            else str(devs)
    except Exception as e:
        out['execution_devices'] = 'ERR:%s' % e
    del cm
    return out


def main() -> int:
    res = {'script': os.path.basename(__file__), 'ts': now(),
           'purpose': 'NPU 属性变体探针：找 Meteor Lake 可用的最小属性集'}
    pid = acquire_lock('app290_npu_props_variants')
    if pid < 0:
        print('🔴 拿不到锁 ⇒ 放弃')
        res['verdict'] = 'LOCK_BUSY'
        _write(res)
        return 2
    print('🔒 MACHINE_LOCK pid=%d' % pid, flush=True)
    try:
        import openvino as ov
        core = ov.Core()
        res['ov_version'] = ov.__version__
        for k, p in (('npu_full_name', 'FULL_DEVICE_NAME'),
                     ('npu_driver', 'NPU_DRIVER_VERSION'),
                     ('npu_arch', 'DEVICE_ARCHITECTURE')):
            try:
                res[k] = core.get_property('NPU', p)
            except Exception as e:
                res[k] = 'ERR:%s' % e

        cache = os.path.join(tempfile.gettempdir(), 'app290_npu_probe_cache')
        os.makedirs(cache, exist_ok=True)

        npuw_all = {'NPU_USE_NPUW': 'YES', 'NPUW_LLM': 'YES',
                    'NPUW_LLM_MAX_PROMPT_LEN': '512',
                    'NPUW_LLM_MIN_RESPONSE_LEN': '64',
                    'CACHE_DIR': cache}
        npuw_only = {'NPU_USE_NPUW': 'YES', 'CACHE_DIR': cache}
        plain = {'PERFORMANCE_HINT': 'LATENCY', 'CACHE_DIR': cache}

        arms = []
        # ── encoder（先冻结形状，与产品同一口径）────────────────
        em = core.read_model(
            model=os.path.join(ENC_DIR, 'openvino_encoder_model.xml'),
            weights=os.path.join(ENC_DIR, 'openvino_encoder_model.bin'))
        frozen = freeze_encoder(core, em, MAX_FRAMES)
        print('▶ encoder 冻结后 + plain…', flush=True)
        arms.append({'model': 'encoder-fp16', **try_compile(
            core, frozen, plain, 'encoder+frozen+plain')})
        print('▶ encoder 冻结后 + NPUW…', flush=True)
        arms.append({'model': 'encoder-fp16', **try_compile(
            core, frozen, npuw_only, 'encoder+frozen+NPUW_only')})

        # ── decoder ───────────────────────────────────────────
        dm = core.read_model(os.path.join(DEC_DIR, 'openvino_model.xml'))
        print('▶ decoder + NPUW(全)…', flush=True)
        arms.append({'model': 'decoder-npu-int8', **try_compile(
            core, dm, npuw_all, 'decoder+NPUW_all')})
        print('▶ decoder + NPUW(仅)…', flush=True)
        arms.append({'model': 'decoder-npu-int8', **try_compile(
            core, dm, npuw_only, 'decoder+NPUW_only')})
        print('▶ decoder + plain…', flush=True)
        arms.append({'model': 'decoder-npu-int8', **try_compile(
            core, dm, plain, 'decoder+plain')})
        res['arms'] = arms

        by = {a['label']: a for a in arms}
        res['verdict'] = {
            'encoder_plain_ok': by['encoder+frozen+plain']['ok'],
            'decoder_npuw_all_ok': by['decoder+NPUW_all']['ok'],
            'decoder_npuw_only_ok': by['decoder+NPUW_only']['ok'],
            'decoder_plain_ok': by['decoder+plain']['ok'],
        }
        print('★ %s' % json.dumps(res['verdict'], ensure_ascii=False),
              flush=True)
    finally:
        release_lock()
    _write(res)
    print(json.dumps({'out': EVID}, ensure_ascii=False))
    return 0


def _write(obj: dict) -> None:
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    raise SystemExit(main())
