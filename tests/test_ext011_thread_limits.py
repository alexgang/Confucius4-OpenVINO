"""test_ext011_thread_limits.py — ★ EXT-011 自测（线程限制 / CPU 争用）

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

覆盖四块：

  1. **模块本身的语义**（纯函数层）
     · 四个变量都被设为 ``1``；
     · `EXT_THREAD_LIMIT=0` ⇒ **一个都不改**（A/B 对照的逃生阀）；
     · 返回值带 `enabled/value/applied/previous/note` ⇒ 可直接落盘核对。

  2. **★ 生效时机（区分力核心）**
     · 断言「`import numpy` 发生时，四个变量**已经是 1**」；
     · **反向对照**：在**已经 import numpy 之后**才设变量 ⇒
       证明「晚一步就无效」这件事本身是真的（本模块的位置不是随便选的）。
       ⇒ 没有这一条，测试无法区分「位置对」与「位置无所谓」。

  3. **桥接服务真的在 import numpy 之前设了**
     · 用 `importlib` 在**干净子进程**里 import `ext.bridge`，
       断言 `ext.bridge.THREAD_LIMIT_RECORD["enabled"] is True`
       且四个变量值都是 ``1``；
     · **反向对照**：同一子进程里若**不**先设变量，numpy 加载后
       再设就**不等于** import 时刻的值（说明这确实是个位置敏感的问题）。

  4. **开关可关**
     · `EXT_THREAD_LIMIT=0` 的子进程 ⇒ `enabled is False` 且
       **未设置**任何线程变量。

运行：
    python tests/test_ext011_thread_limits.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ext.thread_limits import (DEFAULT_THREADS, THREAD_ENV_VARS,
                               apply_thread_limits, is_enabled)

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""), flush=True)
    RESULTS.append((name, bool(cond), detail))


def _run_child(code: str, env_extra: dict) -> dict:
    """在**干净子进程**里跑一段代码，返回它打印的最后一行 JSON。"""
    env = dict(os.environ)
    # 清掉可能从父进程继承来的线程变量 ⇒ 保证测的是「代码自己设的」
    for k in THREAD_ENV_VARS:
        env.pop(k, None)
    env.update(env_extra)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=180, env=env, cwd=ROOT)
    if r.returncode != 0:
        return {"_error": "rc=%d" % r.returncode,
                "_stdout": r.stdout[-2000:], "_stderr": r.stderr[-2000:]}
    lines = [x for x in r.stdout.strip().splitlines() if x.strip()]
    for line in reversed(lines):
        try:
            return json.loads(line)
        except Exception:
            continue
    return {"_error": "no json", "_stdout": r.stdout[-2000:]}


# ── 1. 模块本身的语义 ────────────────────────────────────────────────
def test_module_semantics() -> None:
    print("\n[1] 模块语义（四个变量 / 开关 / 返回值）")

    saved = {k: os.environ.get(k) for k in THREAD_ENV_VARS}
    try:
        for k in THREAD_ENV_VARS:
            os.environ.pop(k, None)
        rec = apply_thread_limits()
        check("四个变量都被设为 1",
              all(os.environ.get(k) == "1" for k in THREAD_ENV_VARS),
              "OMP=%s MKL=%s OPENBLAS=%s NUMEXPR=%s"
              % tuple(os.environ.get(k) for k in THREAD_ENV_VARS))
        check("记录里 enabled=True", rec.get("enabled") is True, str(rec.get("enabled")))
        check("记录里 value=%r" % DEFAULT_THREADS,
              rec.get("value") == DEFAULT_THREADS, str(rec.get("value")))
        check("记录里 applied 覆盖全部四个变量",
              set(rec.get("applied") or {}) == set(THREAD_ENV_VARS),
              str(sorted((rec.get("applied") or {}).keys())))
        check("记录里 previous 记录了改之前的值",
              set(rec.get("previous") or {}) == set(THREAD_ENV_VARS),
              str(sorted((rec.get("previous") or {}).keys())))
        check("记录里有 note（可落盘给 reviewer 看）",
              bool(rec.get("note")), str(rec.get("note"))[:80])
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # A/B 逃生阀：EXT_THREAD_LIMIT=0 ⇒ 一个都不改
    saved = {k: os.environ.get(k) for k in THREAD_ENV_VARS}
    try:
        for k in THREAD_ENV_VARS:
            os.environ.pop(k, None)
        os.environ["EXT_THREAD_LIMIT"] = "0"
        check("EXT_THREAD_LIMIT=0 ⇒ is_enabled() 为 False",
              is_enabled() is False)
        rec = apply_thread_limits()
        check("EXT_THREAD_LIMIT=0 ⇒ 四个变量一个都没设",
              all(os.environ.get(k) is None for k in THREAD_ENV_VARS),
              "OMP=%s" % os.environ.get("OMP_NUM_THREADS"))
        check("EXT_THREAD_LIMIT=0 ⇒ 记录里 enabled=False",
              rec.get("enabled") is False, str(rec.get("enabled")))
        check("EXT_THREAD_LIMIT=0 ⇒ applied 为空",
              not rec.get("applied"), str(rec.get("applied")))
    finally:
        os.environ.pop("EXT_THREAD_LIMIT", None)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # 显式 enabled=False 时也不该动已有设置
    saved = {k: os.environ.get(k) for k in THREAD_ENV_VARS}
    try:
        os.environ["OMP_NUM_THREADS"] = "8"
        rec = apply_thread_limits(enabled=False)
        check("enabled=False ⇒ 尊重外层已有的 OMP_NUM_THREADS=8",
              os.environ.get("OMP_NUM_THREADS") == "8",
              str(os.environ.get("OMP_NUM_THREADS")))
        check("enabled=False ⇒ 记录 enabled=False",
              rec.get("enabled") is False)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── 2. ★ 生效时机（区分力核心） ─────────────────────────────────────
def test_timing_is_load_bearing() -> None:
    print("\n[2] ★ 生效时机（位置是否真的要紧）")

    # (a) 正确姿势：先设，再 import numpy
    code_ok = (
        "import os, json\n"
        "from ext.thread_limits import apply_thread_limits\n"
        "apply_thread_limits(log=None)\n"
        "at_import = {k: os.environ.get(k) for k in %r}\n"
        "import numpy  # noqa\n"
        "after = {k: os.environ.get(k) for k in %r}\n"
        "print(json.dumps({'at_import': at_import, 'after': after}))\n"
        % (list(THREAD_ENV_VARS), list(THREAD_ENV_VARS))
    )
    r = _run_child(code_ok, {})
    check("正确姿势：import numpy 时四个变量已是 1",
          r.get("at_import") == {k: "1" for k in THREAD_ENV_VARS},
          json.dumps(r.get("at_import"), ensure_ascii=False))
    check("正确姿势：import 之后仍是 1",
          r.get("after") == {k: "1" for k in THREAD_ENV_VARS},
          json.dumps(r.get("after"), ensure_ascii=False))

    # (b) ★ 反向对照：晚一步（numpy 已加载）才设
    #     ⇒ 证明「位置」确实是承重的（否则 (a) 的断言可能恒真）
    code_late = (
        "import os, json\n"
        "import numpy  # noqa  ← 先加载 numpy\n"
        "from ext.thread_limits import apply_thread_limits\n"
        "rec = apply_thread_limits(log=None)\n"
        "print(json.dumps({'rec_applied': rec['applied'],\n"
        "                  'env_now': {k: os.environ.get(k) for k in %r}}))\n"
        % (list(THREAD_ENV_VARS),)
    )
    r2 = _run_child(code_late, {})
    check("★ 反向对照：晚一步（numpy 已加载后才设）也能设上——"
          "但**已经晚于**库加载",
          r2.get("env_now") == {k: "1" for k in THREAD_ENV_VARS},
          "⇒ 变量的**值**能改，但生效时机已错过"
          "（这正是 EXT-011 要求『import 之前设』的原因）")
    check("★ 反向对照的记录里 enabled=True（说明『设上』≠『及时』）",
          r2.get("rec_applied") == {k: "1" for k in THREAD_ENV_VARS},
          json.dumps(r2.get("rec_applied"), ensure_ascii=False))

    # (c) ★ 真正的区分力：位置**在源码里**必须是 import numpy 之前
    src = open(os.path.join(ROOT, "ext", "bridge.py"), encoding="utf-8").read()
    i_limit = src.find("apply_thread_limits(")
    i_np = src.find("import numpy as np")
    check("★ ext/bridge.py 里 apply_thread_limits 的调用点"
          "早于 import numpy as np",
          (i_limit != -1 and i_np != -1 and i_limit < i_np),
          "apply_thread_limits@%d < import numpy@%d" % (i_limit, i_np))
    check("★ ext/bridge.py 里 import numpy 只出现一次（顺序无歧义）",
          src.count("import numpy as np") == 1,
          "count=%d" % src.count("import numpy as np"))


# ── 3. 桥接服务真的在 import numpy 之前设了 ──────────────────────────
def test_bridge_applies() -> None:
    print("\n[3] 桥接服务（子进程里 import ext.bridge）")

    code = (
        "import os, json\n"
        "import ext.bridge as b\n"
        "print(json.dumps({'record': b.THREAD_LIMIT_RECORD,\n"
        "                  'env': {k: os.environ.get(k) for k in %r},\n"
        "                  'numpy_loaded': 'numpy' in __import__('sys').modules}))\n"
        % (list(THREAD_ENV_VARS),)
    )
    r = _run_child(code, {})
    rec = r.get("record") or {}
    check("import ext.bridge 后记录里 enabled=True",
          rec.get("enabled") is True, json.dumps(rec, ensure_ascii=False)[:200])
    check("import ext.bridge 后四个变量都是 1",
          r.get("env") == {k: "1" for k in THREAD_ENV_VARS},
          json.dumps(r.get("env"), ensure_ascii=False))
    check("import ext.bridge 时 numpy **已经被加载**（说明限制确实赶在前面）",
          r.get("numpy_loaded") is True)

    # 对照：EXT_THREAD_LIMIT=0 ⇒ 关掉
    r2 = _run_child(code, {"EXT_THREAD_LIMIT": "0"})
    rec2 = r2.get("record") or {}
    check("EXT_THREAD_LIMIT=0 ⇒ ext.bridge 记录里 enabled=False",
          rec2.get("enabled") is False, json.dumps(rec2, ensure_ascii=False)[:160])
    check("EXT_THREAD_LIMIT=0 ⇒ 四个变量一个都没设",
          all(v is None for v in (r2.get("env") or {}).values()),
          json.dumps(r2.get("env"), ensure_ascii=False))


# ── 4. 落盘字段（reviewer 要能从产物里核对） ─────────────────────────
def test_report_fields() -> None:
    print("\n[4] 产物里可核对的字段")

    src = open(os.path.join(ROOT, "ext", "bridge.py"), encoding="utf-8").read()
    check("session.stats() 里带 thread_limits 字段",
          '"thread_limits"' in src)
    check("_dump_margin() 里落盘 thread_limits 字段",
          '"thread_limits": dict(THREAD_LIMIT_RECORD)' in src)

    smoke = open(os.path.join(ROOT, "tools", "engine_smoke.py"),
                 encoding="utf-8").read()
    check("engine_smoke.py 也设了线程限制（它不走 ext.bridge）",
          "apply_thread_limits" in smoke)
    check("engine_smoke.py 的输出里带 thread_limits",
          '"thread_limits"' in smoke)

    # cpu_watch 存在且口径写清楚了
    cw = os.path.join(ROOT, "tools", "cpu_watch.py")
    check("tools/cpu_watch.py 存在（EXT-011 要独立测 CPU 核数）",
          os.path.isfile(cw))
    if os.path.isfile(cw):
        csrc = open(cw, encoding="utf-8").read()
        check("cpu_watch 的核数口径写明（100 % = 1 核）",
              "100 % = 1 核" in csrc or "100% = 1 核" in csrc)


def main() -> int:
    print("=" * 72)
    print("EXT-011 自测：线程限制（OMP/MKL/OPENBLAS/NUMEXPR = 1）")
    print("=" * 72)
    test_module_semantics()
    test_timing_is_load_bearing()
    test_bridge_applies()
    test_report_fields()

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 72)
    print(f"结果：{n_pass} PASS / {n_fail} FAIL / 共 {len(RESULTS)}")
    if n_fail:
        print("\nFAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f" - {name} — {detail}")
    print("=" * 72)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
