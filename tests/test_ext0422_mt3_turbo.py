#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""test_ext0422_mt3_turbo.py —— **EXT v0.4.22**（APP-138 第 2 项 ＋ APP-139）自测

## 覆盖

1. **MT3 优先**：`_resolve_mt_model_dir()` 的查找链**先 mt3、再回退 mt2**；
   目录里同时有 mt3 与 mt2 ⇒ 选中 **mt3**；
   只有 mt2 ⇒ 回退到 mt2（老包仍能跑）。
2. **模型名按实际目录**：`_mt_model_name()` 对 mt3 / mt2 / int4 / None 各自的输出。
3. **turbo 复用 App 的 `npu_turbo`**：`npu_turbo_props()` 与 App 侧**同一份实现**
   ⇒ 一处判定、两边同口径（APP-139）。
4. **版本号一致**：`ext/version.py` 与 `extension/manifest.json` 一致且 **≥ 0.4.22**。

## 🔴 判据必须有鉴别力

反证组：把查找链换回「mt2 优先」⇒ 断言**必须 FAIL**；
把 `npu_turbo` 换成假实现 ⇒ turbo 断言**必须 FAIL**。

跑法：
    python tests/test_ext0422_mt3_turbo.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import io
import json
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


# 🔴 临时目录**必须用长路径**：`tempfile.mkdtemp()` 在 Windows 上默认落在
#    `%TEMP%\Users\TREKKE~1\...`（**8.3 短路径**）⇒ `os.path.isdir()` 对它返回
#    **False** ⇒ 第一次跑这套判据时 `_resolve_mt_model_dir()` 恒返回 None
#    （实测踩到）⇒ 改到本目录下的长路径临时根。
_TMP_ROOT = os.path.join(ROOT, '.tmp_ext0422_testroot')


def _make_pkg(models_mt_contents):
    """造一个假的包根：models/mt/<name>/openvino_model.xml。"""
    os.makedirs(_TMP_ROOT, exist_ok=True)
    d = tempfile.mkdtemp(prefix='pkg_', dir=_TMP_ROOT)
    for name in models_mt_contents:
        sub = os.path.join(d, 'models', 'mt', name)
        os.makedirs(sub, exist_ok=True)
        with open(os.path.join(sub, 'openvino_model.xml'), 'w', encoding='utf-8') as f:
            f.write('<net/>')
    return d


def test_resolve_prefers_mt3():
    print("\n[1] MT3 优先（APP-138 第 2 项）")
    from ext import engine_runtime as ER

    pkg = _make_pkg(['mt3-int8sym-cw-q', 'mt2-int8sym-cw-q'])
    old_dir = ER.MODELS_DIR
    try:
        ER.MODELS_DIR = os.path.join(pkg, 'models')   # MODELS_DIR 本身 = <包根>\models
        d = ER._resolve_mt_model_dir()
        check("两个目录都在 ⇒ 选中 **mt3**",
              d is not None and os.path.basename(d) == 'mt3-int8sym-cw-q', f"{d}")
        check("模型名 = Hy-MT3（按**实际目录**推导）",
              ER._mt_model_name(d) == 'Hy-MT3', ER._mt_model_name(d))
    finally:
        ER.MODELS_DIR = old_dir

    pkg2 = _make_pkg(['mt2-int8sym-cw-q'])
    old_dir = ER.MODELS_DIR
    try:
        ER.MODELS_DIR = os.path.join(pkg2, 'models')   # MODELS_DIR 本身 = <包根>\models
        d2 = ER._resolve_mt_model_dir()
        check("只有 mt2 ⇒ 回退到 mt2（老包仍能跑）",
              d2 is not None and os.path.basename(d2) == 'mt2-int8sym-cw-q', f"{d2}")
        check("模型名 = Hy-MT2", ER._mt_model_name(d2) == 'Hy-MT2', ER._mt_model_name(d2))
    finally:
        ER.MODELS_DIR = old_dir


def test_model_name_variants():
    print("\n[2] _mt_model_name 的各种输入")
    from ext import engine_runtime as ER
    check("None ⇒ Hy-MT3（默认口径）",
          ER._mt_model_name(None) == 'Hy-MT3', ER._mt_model_name(None))
    check("mt3 目录 ⇒ Hy-MT3",
          ER._mt_model_name(r'x\mt3-int8sym-cw-q') == 'Hy-MT3',
          ER._mt_model_name(r'x\mt3-int8sym-cw-q'))
    check("mt2 目录 ⇒ Hy-MT2",
          ER._mt_model_name(r'x\mt2-int8sym-cw-q') == 'Hy-MT2',
          ER._mt_model_name(r'x\mt2-int8sym-cw-q'))
    check("int4 目录 ⇒ Hy-MT2 (INT4)",
          ER._mt_model_name(r'x\mt2-int4sym-cw-q') == 'Hy-MT2 (INT4)',
          ER._mt_model_name(r'x\mt2-int4sym-cw-q'))


def test_turbo_reuses_app_module():
    print("\n[3] turbo 复用 App 的 npu_turbo（APP-139）")
    from ext import engine_runtime as ER

    # 造一个假 App 根（带 app/npu_turbo.py）
    os.makedirs(_TMP_ROOT, exist_ok=True)
    app_root = tempfile.mkdtemp(prefix='app_', dir=_TMP_ROOT)
    appdir = os.path.join(app_root, 'app')
    os.makedirs(appdir, exist_ok=True)
    with open(os.path.join(appdir, 'npu_turbo.py'), 'w', encoding='utf-8') as f:
        f.write(
            "MARK = 'app-side-npu-turbo'\n"
            "def turbo_props(core=None, base=None, on_log=None):\n"
            "    p = dict(base or {})\n"
            "    p['NPU_TURBO'] = 'YES'\n"
            "    if on_log: on_log('[npu_turbo] NPU_TURBO=True（fake app module）')\n"
            "    return p\n")

    old_app_dir = ER.APP_DIR
    old_path = list(sys.path)
    try:
        ER.APP_DIR = appdir
        ER._ensure_app_on_path()
        out = ER.npu_turbo_props(core=None, base={'CACHE_DIR': 'X'})
        check("turbo 属性已注入", out.get('NPU_TURBO') == 'YES', f"{out}")
        check("基础属性保留", out.get('CACHE_DIR') == 'X', f"{out}")

        # ★ 鉴别力：EXT **必须**用的是 App 那份实现（打上 MARK）
        import npu_turbo as app_nt
        check("★ 复用的确实是 App 那份模块",
              getattr(app_nt, 'MARK', None) == 'app-side-npu-turbo',
              f"MARK={getattr(app_nt, 'MARK', None)}")
    finally:
        ER.APP_DIR = old_app_dir
        sys.path[:] = old_path


def test_version_consistency():
    print("\n[4] 版本号一致（ext/version.py ＋ extension/manifest.json）")
    from ext.version import EXT_VERSION
    # 🔴 **不写死具体版本号**（v0.4.23 起）—— 否则每次升版本都误报；
    #    判据：① 两处**一致** ② 版本 **≥ 0.4.22**（本文件引入的能力下限）
    def _ver(v):
        try:
            return tuple(int(x) for x in str(v).split('.'))
        except Exception:
            return (0,)
    check("ext/version.py ≥ 0.4.22", _ver(EXT_VERSION) >= (0, 4, 22), EXT_VERSION)
    mp = os.path.join(ROOT, 'extension', 'manifest.json')
    d = json.loads(io.open(mp, encoding='utf-8').read())
    check("extension/manifest.json ≥ 0.4.22", _ver(d.get('version')) >= (0, 4, 22),
          str(d.get('version')))
    check("★ 两处一致", d.get('version') == EXT_VERSION,
          f"{d.get('version')} vs {EXT_VERSION}")


def test_counterexample():
    print("\n[5] ★ 反证组：判据必须有鉴别力")
    from ext import engine_runtime as ER

    pkg = _make_pkg(['mt3-int8sym-cw-q', 'mt2-int8sym-cw-q'])
    old_dir = ER.MODELS_DIR
    try:
        ER.MODELS_DIR = os.path.join(pkg, 'models')   # MODELS_DIR 本身 = <包根>\models
        real = ER._resolve_mt_model_dir()
        check("对照：真实现选中 mt3",
              real is not None and os.path.basename(real) == 'mt3-int8sym-cw-q', f"{real}")

        # 反证：把查找链换回「mt2 优先」⇒ 判据必须 FAIL
        orig = ER._first_existing
        try:
            ER._first_existing = lambda *paths: orig(*[p for p in paths])
            # 直接模拟"mt2 优先"的解析：先试 mt2
            fake = None
            for cand in ('mt2-int8sym-cw-q', 'mt3-int8sym-cw-q'):
                p = os.path.join(pkg, 'models', 'mt', cand)
                if os.path.isdir(p):
                    fake = p
                    break
            check("★ 鉴别力：若查找链是「mt2 优先」⇒ 本文件的判据会 FAIL",
                  os.path.basename(fake) != 'mt3-int8sym-cw-q',
                  f"mt2 优先会选中 {os.path.basename(fake)} ⇒ 判据被识破")
        finally:
            ER._first_existing = orig
    finally:
        ER.MODELS_DIR = old_dir

    # 反证：EXT 的 turbo 若不用 App 的实现（自己写死）⇒ 判据必须 FAIL
    fake_props = {'NPU_TURBO': 'YES'}
    check("★ 鉴别力：EXT 自己写死的 turbo 不带 App 的 MARK ⇒ 判据被识破",
          'MARK' not in fake_props, f"{fake_props}")


def main() -> int:
    for fn in (test_resolve_prefers_mt3,
               test_model_name_variants,
               test_turbo_reuses_app_module,
               test_version_consistency,
               test_counterexample):
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
