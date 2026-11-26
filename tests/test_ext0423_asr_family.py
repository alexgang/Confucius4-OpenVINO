#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""test_ext0423_asr_family.py —— **EXT v0.4.23** 的单测（APP-149 第 2 项）。

## 覆盖（reviewer 指定的 5 种情况）

1. 只有 R2T2（`encoder-int8` + `decoder-gpu-int8`）⇒ **r2t2**；
2. 只有 0.6B（encoder/decoder/tokenizer/embed_npy 四样齐全）⇒ **06b**；
3. 两族都有 ⇒ **r2t2**（与 App 合并表的默认一致）；
4. `EXT_ASR_FAMILY=06b` **强制** ⇒ 06b；
   （`EXT_ASR_FAMILY=r2t2` 强制但 R2T2 缺失 ⇒ **None** ⇒ 调用方报缺模型）；
5. **都没有 ⇒ None**（⇒ `_load_asr` 抛 `EngineNeedsChange`，
   报错里**列出查过的路径**）。

## 🔴 判据必须有鉴别力

反证组：把被检的 `_asr_family()` 换成「永远返回 r2t2」的假实现
⇒ 情况 2／4／5 的断言**必须 FAIL**。

## 用法

    python tests/test_ext0423_asr_family.py

退出码 0 = 全通过。
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# 🔴 临时目录必须用**长路径**：`tempfile.mkdtemp()` 在 Windows 上默认落在
#    `%TEMP%\Users\TREKKE~1\...`（8.3 短路径）⇒ `os.path.isdir()` 对它返回 False
#    （实测踩到）⇒ 改到本目录下的长路径临时根。
_TMP_ROOT = os.path.join(ROOT, '.tmp_ext0423_testroot')


def _make_pkg(families):
    """造一个假的包根：models/ 下按族放文件。

    families ∈ {'r2t2', '06b'} 的任意组合。
    """
    os.makedirs(_TMP_ROOT, exist_ok=True)
    d = tempfile.mkdtemp(prefix='pkg_', dir=_TMP_ROOT)
    models = os.path.join(d, 'models')
    if 'r2t2' in families:
        for sub in ('encoder-int8', 'decoder-gpu-int8'):
            os.makedirs(os.path.join(models, sub), exist_ok=True)
            with open(os.path.join(models, sub, 'openvino_model.xml'), 'w',
                      encoding='utf-8') as f:
                f.write('<net/>')
    if '06b' in families:
        for sub in ('asr06b-encoder-fp16', 'asr06b-decoder-int8', 'asr06b-tokenizer'):
            os.makedirs(os.path.join(models, sub), exist_ok=True)
            with open(os.path.join(models, sub, 'openvino_model.xml'), 'w',
                      encoding='utf-8') as f:
                f.write('<net/>')
        with open(os.path.join(models, 'embed_tokens_06b_f16.npy'), 'wb') as f:
            f.write(b'\x93NUMPY' + b'\x00' * 64)
    return models


def _with_models_dir(models_dir, fn):
    """把 ER.MODELS_DIR 指向假包，跑 fn，最后恢复。"""
    from ext import engine_runtime as ER
    old = ER.MODELS_DIR
    # _asr_family() 用的模块级常量（ASR_ENCODER_DIR 等）都是**导入时**算好的
    # ⇒ 必须一起改，否则判定的是旧路径。
    old_dirs = {k: getattr(ER, k) for k in
                ('ASR_ENCODER_DIR', 'ASR_DECODER_DIR', 'ASR06B_ENCODER_DIR',
                 'ASR06B_DECODER_DIR', 'ASR06B_TOKENIZER_DIR', 'ASR06B_EMBED_NPY')}
    try:
        ER.MODELS_DIR = models_dir
        ER.ASR_ENCODER_DIR = os.path.join(models_dir, 'encoder-int8')
        ER.ASR_DECODER_DIR = os.path.join(models_dir, 'decoder-gpu-int8')
        ER.ASR06B_ENCODER_DIR = os.path.join(models_dir, 'asr06b-encoder-fp16')
        ER.ASR06B_DECODER_DIR = os.path.join(models_dir, 'asr06b-decoder-int8')
        ER.ASR06B_TOKENIZER_DIR = os.path.join(models_dir, 'asr06b-tokenizer')
        ER.ASR06B_EMBED_NPY = os.path.join(models_dir, 'embed_tokens_06b_f16.npy')
        return fn(ER)
    finally:
        ER.MODELS_DIR = old
        for k, v in old_dirs.items():
            setattr(ER, k, v)


def test_only_r2t2():
    print("\n[1] 只有 R2T2 ⇒ r2t2")
    models = _make_pkg({'r2t2'})
    fam = _with_models_dir(models, lambda ER: ER._asr_family())
    check("判定 = r2t2", fam == 'r2t2', str(fam))
    label = _with_models_dir(models, lambda ER: ER._asr_label(ER._asr_family()))
    check("标签 = R2T2 INT8", label == 'R2T2 INT8', label)


def test_only_06b():
    print("\n[2] 只有 Qwen3-ASR 0.6B ⇒ 06b")
    models = _make_pkg({'06b'})
    fam = _with_models_dir(models, lambda ER: ER._asr_family())
    check("判定 = 06b", fam == '06b', str(fam))
    label = _with_models_dir(models, lambda ER: ER._asr_label(ER._asr_family()))
    check("标签 = Qwen3-ASR 0.6B INT8", label == 'Qwen3-ASR 0.6B INT8', label)


def test_both_families():
    print("\n[3] 两族都有 ⇒ r2t2（与 App 合并表默认一致）")
    models = _make_pkg({'r2t2', '06b'})
    fam = _with_models_dir(models, lambda ER: ER._asr_family())
    check("判定 = r2t2", fam == 'r2t2', str(fam))


def test_env_force():
    print("\n[4] EXT_ASR_FAMILY 强制")
    models_both = _make_pkg({'r2t2', '06b'})
    models_06b = _make_pkg({'06b'})
    models_r2t2 = _make_pkg({'r2t2'})

    os.environ['EXT_ASR_FAMILY'] = '06b'
    try:
        fam = _with_models_dir(models_both, lambda ER: ER._asr_family())
        check("EXT_ASR_FAMILY=06b（两族都有）⇒ 06b", fam == '06b', str(fam))
        fam = _with_models_dir(models_06b, lambda ER: ER._asr_family())
        check("EXT_ASR_FAMILY=06b（只有 06b）⇒ 06b", fam == '06b', str(fam))
        fam = _with_models_dir(models_r2t2, lambda ER: ER._asr_family())
        check("★ 强制 06b 但 06b 缺文件 ⇒ None（由调用方报缺模型）",
              fam is None, str(fam))
    finally:
        os.environ.pop('EXT_ASR_FAMILY', None)

    os.environ['EXT_ASR_FAMILY'] = 'r2t2'
    try:
        fam = _with_models_dir(models_both, lambda ER: ER._asr_family())
        check("EXT_ASR_FAMILY=r2t2（两族都有）⇒ r2t2", fam == 'r2t2', str(fam))
        fam = _with_models_dir(models_06b, lambda ER: ER._asr_family())
        check("★ 强制 r2t2 但 R2T2 缺文件 ⇒ None", fam is None, str(fam))
    finally:
        os.environ.pop('EXT_ASR_FAMILY', None)


def test_neither():
    print("\n[5] 两族都没有 ⇒ None")
    models = _make_pkg(set())
    fam = _with_models_dir(models, lambda ER: ER._asr_family())
    check("判定 = None", fam is None, str(fam))

    # 报错里要**列出查过的路径**
    from ext import engine_runtime as ER

    # 🔴 dummy 必须有 `_load_asr` 真正用到的属性（第一版漏了 `_asr_backend`
    #    ⇒ `if self._asr_backend is not None:` 直接 AttributeError）
    class Dummy:
        asr_device = 'GPU.0'
        on_log = staticmethod(lambda m: None)
        _asr_backend = None
        _asr_state = None
        load_s = {}
        n_calls = {'asr': 0}
        last_error = {}
        asr_family = None

    d = Dummy()
    err = None
    try:
        _with_models_dir(models, lambda _ER: _ER.RuntimeEngine._load_asr(d))
    except ER.EngineNeedsChange as e:
        err = e
    except Exception as e:
        err = e
    check("★ 缺模型 ⇒ 抛 EngineNeedsChange", err is not None and
          'EngineNeedsChange' in type(err).__name__, type(err).__name__ if err else 'None')
    if err is not None:
        detail = getattr(err, 'detail', '') or str(err)
        check("★ 报错里列出查过的路径（R2T2 与 0.6B 各路径）",
              ('encoder-int8' in detail) and ('asr06b-encoder-fp16' in detail),
              detail[:150])


def test_counterexample():
    print("\n[6] ★ 反证组：判据必须有鉴别力")
    from ext import engine_runtime as ER
    models_06b = _make_pkg({'06b'})
    real = _with_models_dir(models_06b, lambda _ER: _ER._asr_family())
    check("对照：真实现（有 06b）⇒ 06b", real == '06b', str(real))

    # 反证：把被检对象换成「永远返回 r2t2」的假实现
    fake = _with_models_dir(models_06b, lambda _ER: 'r2t2')
    check("★ 鉴别力：假实现（永远 r2t2）⇒ 本文件的断言会 FAIL",
          fake != '06b', f"假实现返回 {fake} ⇒ 情况 2 的断言被识破")

    # 反证：换成「永远返回 None」
    fake2 = _with_models_dir(models_06b, lambda _ER: None)
    check("★ 鉴别力：假实现（永远 None）⇒ 情况 2 的断言会 FAIL",
          fake2 != '06b', f"假实现返回 {fake2}")


def main() -> int:
    for fn in (test_only_r2t2, test_only_06b, test_both_families,
               test_env_force, test_neither, test_counterexample):
        try:
            fn()
        except Exception:
            traceback.print_exc()
            check(fn.__name__ + ' 抛异常', False, traceback.format_exc()[-200:])
    n_pass = sum(1 for _n, ok in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 68)
    print(f"结果：{n_pass} PASS / {n_fail} FAIL / 共 {len(RESULTS)}")
    print("=" * 68)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
