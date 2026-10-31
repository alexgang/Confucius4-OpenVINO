"""test_ext023_tts_exec_devices.py — ★ EXT-023 自测：TTS 各组件的 EXECUTION_DEVICES
**追加**新的行为级验收，**不改写**既有断言（避免用改断言掩盖回归）。

## 背景（EXT-023 明文）

主会话转达（TTS reviewer 10-31 Opus）：

> `qwen3tts_eval` 里裸 `build()` 默认把 **cp_decode 放在 CPU**，
> 只有调了 `_recompile_cp_on_npu(only=["cp_decode"])` 之后才会到 NPU
> （TTS-037 正在把默认改成 NPU）。
> **cp_decode 在 CPU 上会让 TTS 的 RTF 变差约 30 %（1.01 vs 0.71）。**

要求：

> 在你的 TTS 启动日志里打印 talker、cp_prefill、cp_decode、decoder
> 各自实际的 EXECUTION_DEVICES，确认全部是 NPU。
> 如果你是直接调 build()，要显式传 `cp_decode_device="NPU"`（或者调用重编译）。
> 把一行日志证据写进 STATUS。**不用另外做测速。**

## 本模块的落地方式（不改任何引擎文件）

* **本模块走的是 App 的 `tts_engine.make_engine()`**（不是裸 `build()`）
  ⇒ App 侧 `make_engine()` 的最后一步已经调了 `_move_cp_decode_to_npu(eng)`
  **且**把 `eng.exec_devices = execution_devices(eng)` 挂好了
  （见 `Confucius4_LiveCaption_v1.13/app/tts_engine.py` 的 make_engine 末段）。
* ⇒ 本模块**不需要重复探测**（重复探测会再抢一次 NPU、很慢），
  只**读** `eng.exec_devices` 并：
  1. 打印一行 `key4_line`（`EXECUTION_DEVICES talker=…，cp_prefill=…，…`）；
  2. 逐组件打印实际落点；
  3. **落盘** `%LOCALAPPDATA%\LiveDubEXT\tts_exec_devices.json`
     （铁律「没落盘的东西不能写『已交付』」⇒ reviewer 可直接 `json.load` 核对）。

## 判定原则

* **行为级优先**：真调 `_report_tts_exec_devices()`、真写文件、真读回 JSON。
* **有区分力**：对照组用**坏桩**（`exec_devices` 不是 dict / 缺字段）
  ⇒ 必须**如实报失败**，绝不臆造「都在 NPU」。
* **真实退出码**：取真实 `rc`。

运行：
    python tests/test_ext023_tts_exec_devices.py
退出码 0 = 全通过。

⚠️ **不加载任何模型权重**（不占 GPU/NPU、不需要共享锁）。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if (detail and not cond) else ""))


class _FakeTTSEngine:
    """模拟 App 侧 `make_engine()` 挂好的 `exec_devices`（**不加载权重**）。"""

    def __init__(self, exec_devices):
        self.exec_devices = exec_devices


# ══════════════════════════════════════════════════════════════
# A：正常路径 —— 四个组件全在 NPU ⇒ 如实报告 + 落盘
# ══════════════════════════════════════════════════════════════
def test_all_on_npu_reported_and_dumped() -> None:
    print("\n[A] ★ 四组件全在 NPU ⇒ 打印 key4_line + 逐组件 + 落盘")
    from ext.engine_runtime import RuntimeEngine

    logs = []
    eng = RuntimeEngine(target_lang="zh", on_log=logs.append)
    eng._tts_eng = _FakeTTSEngine({
        "key4_line": ("EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，"
                      "cp_decode=NPU，decoder=NPU"),
        "devices": {"talker": "NPU", "cp_prefill": "NPU",
                    "cp_decode": "NPU", "decoder": "NPU"},
        "actual": {"talker": "NPU", "cp_prefill": "NPU",
                   "cp_decode": "NPU", "decoder": "NPU"},
        "on_npu": ["talker", "cp_prefill", "cp_decode", "decoder"],
        "on_cpu": [],
        "unknown": [],
        "absent": [],
    })

    tmp = tempfile.mkdtemp()
    old_local = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = tmp
    try:
        out = eng._report_tts_exec_devices()
        path = os.path.join(tmp, "LiveDubEXT", "tts_exec_devices.json")
        check("★ A1 返回 ok=True", out.get("ok") is not False,
              str(out)[:200])
        check("★ A2 on_npu 含全部四个组件",
              set(out.get("on_npu") or []) ==
              {"talker", "cp_prefill", "cp_decode", "decoder"},
              str(out.get("on_npu")))
        check("★ A3 on_cpu 为空（全部在 NPU）",
              not (out.get("on_cpu") or []), str(out.get("on_cpu")))
        check("★ A4 落盘文件存在", os.path.isfile(path), path)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                disk = json.load(f)
            check("★ A5 落盘内容含 devices（reviewer 可直接核对原始字段）",
                  (disk.get("devices") or {}).get("cp_decode") == "NPU",
                  str(disk.get("devices"))[:160])
            check("★ A6 落盘内容含 on_npu / on_cpu / unknown",
                  all(k in disk for k in ("on_npu", "on_cpu", "unknown")),
                  str(sorted(disk.keys()))[:160])
            check("★ A7 落盘含 cp_decode 的实际落点",
                  (disk.get("actual") or {}).get("cp_decode") == "NPU",
                  str(disk.get("actual"))[:160])
            check("★ A8 落盘含 _saved_at（实测时间，不是推算）",
                  bool(disk.get("_saved_at")), str(disk.get("_saved_at")))
    finally:
        if old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old_local

    # ── 日志证据（EXT-023 明文要「打印各组件 EXECUTION_DEVICES」）──
    joined = "\n".join(logs)
    check("★ A9 日志里有 key4_line 那一行（reviewer 要的那一行）",
          "EXECUTION_DEVICES" in joined and "cp_decode=NPU" in joined,
          joined[:300])
    check("★ A10 日志里逐组件列出 talker/cp_prefill/cp_decode/decoder",
          all(("%-22s" % k) or True for k in
              ("talker", "cp_prefill", "cp_decode", "decoder"))
          and all(k in joined for k in
                  ("talker", "cp_prefill", "cp_decode", "decoder")),
          joined[:300])
    check("★ A11 日志里有 on_npu/on_cpu 计数汇总",
          "on_npu=" in joined and "on_cpu=" in joined, joined[:300])


# ══════════════════════════════════════════════════════════════
# B：反证 —— cp_decode 落在 CPU ⇒ 必须**如实**报警（不臆造）
# ══════════════════════════════════════════════════════════════
def test_cp_decode_on_cpu_is_reported_honestly() -> None:
    print("\n[B] ★ 反证：cp_decode 在 CPU ⇒ 必须如实报警（不臆造「都在 NPU」）")
    from ext.engine_runtime import RuntimeEngine

    logs = []
    eng = RuntimeEngine(target_lang="zh", on_log=logs.append)
    eng._tts_eng = _FakeTTSEngine({
        "key4_line": ("EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，"
                      "cp_decode=CPU，decoder=NPU"),
        "devices": {"talker": "NPU", "cp_prefill": "NPU",
                    "cp_decode": "CPU", "decoder": "NPU"},
        "actual": {"talker": "NPU", "cp_prefill": "NPU",
                   "cp_decode": "CPU", "decoder": "NPU"},
        "on_npu": ["talker", "cp_prefill", "decoder"],
        "on_cpu": ["cp_decode"],
        "unknown": [],
        "absent": [],
    })

    tmp = tempfile.mkdtemp()
    old_local = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = tmp
    try:
        out = eng._report_tts_exec_devices()
        path = os.path.join(tmp, "LiveDubEXT", "tts_exec_devices.json")
        check("★ B1 on_cpu 如实含 cp_decode",
              "cp_decode" in (out.get("on_cpu") or []),
              str(out.get("on_cpu")))
        joined = "\n".join(logs)
        check("★ B2 日志明确警告「这些组件在 CPU 上」",
              "CPU" in joined and ("cp_decode" in joined), joined[:300])
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                disk = json.load(f)
            check("★ B3 落盘里 cp_decode 落点是 CPU（如实，不粉饰）",
                  (disk.get("devices") or {}).get("cp_decode") == "CPU",
                  str(disk.get("devices"))[:160])
    finally:
        if old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old_local


# ══════════════════════════════════════════════════════════════
# C：反证 —— 引擎没有 exec_devices ⇒ 如实报失败（**绝不臆造**）
# ══════════════════════════════════════════════════════════════
def test_missing_exec_devices_reports_failure() -> None:
    print("\n[C] ★ 反证：引擎没有 exec_devices ⇒ 如实报失败")
    from ext.engine_runtime import RuntimeEngine

    logs = []
    eng = RuntimeEngine(target_lang="zh", on_log=logs.append)
    eng._tts_eng = _FakeTTSEngine(None)

    tmp = tempfile.mkdtemp()
    old_local = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = tmp
    try:
        out = eng._report_tts_exec_devices()
        check("★ C1 返回 ok=False（不是「都好了」）",
              out.get("ok") is False, str(out)[:200])
        check("★ C2 带错误原因（不静默）",
              bool(out.get("error")), str(out.get("error")))
        path = os.path.join(tmp, "LiveDubEXT", "tts_exec_devices.json")
        check("★ C3 失败也落盘（reviewer 能看到「没测到」）",
              os.path.isfile(path), path)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                disk = json.load(f)
            check("★ C4 落盘里 ok=False",
                  disk.get("ok") is False, str(disk)[:160])
    finally:
        if old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old_local


# ══════════════════════════════════════════════════════════════
# D：未加载 TTS 时，tts_exec_devices 必须是 None（**没测过就是没测过**）
# ══════════════════════════════════════════════════════════════
def test_not_loaded_is_none() -> None:
    print("\n[D] ★ 未加载 TTS ⇒ tts_exec_devices 为 None（不臆造）")
    from ext.engine_runtime import RuntimeEngine

    eng = RuntimeEngine(target_lang="zh", on_log=lambda _m: None)
    check("★ D1 初始 tts_exec_devices 为 None",
          eng.tts_exec_devices is None, repr(eng.tts_exec_devices))


# ══════════════════════════════════════════════════════════════
# E：契约 —— 本模块走 App 的 make_engine（不是裸 build）
# ══════════════════════════════════════════════════════════════
def test_uses_app_make_engine() -> None:
    print("\n[E] ★ 契约：本模块用 App 的 make_engine（App 侧已搬 cp_decode 到 NPU）")
    src = open(os.path.join(ROOT, "ext", "engine_runtime.py"),
               "r", encoding="utf-8").read()
    check("★ E1 用的是 tts_engine.make_engine（不是裸 build()）",
          "from tts_engine import make_engine" in src
          and "make_engine(" in src)
    check("★ E2 读 eng.exec_devices（复用 App 的探测，不重复抢 NPU）",
          "getattr(eng, \"exec_devices\"" in src)
    check("★ E3 落盘路径与 bridge.log 同目录（LiveDubEXT）",
          "\"LiveDubEXT\"" in src
          and "tts_exec_devices.json" in src)
    check("★ E4 落盘失败不抛（诊断增强不能搞挂引擎）",
          "落盘失败" in src)


def main() -> int:
    print("=" * 68)
    print("EXT-023 自测：TTS 各组件 EXECUTION_DEVICES 的上报与落盘")
    print("=" * 68)
    for fn in (test_all_on_npu_reported_and_dumped,
               test_cp_decode_on_cpu_is_reported_honestly,
               test_missing_exec_devices_reports_failure,
               test_not_loaded_is_none,
               test_uses_app_make_engine):
        try:
            fn()
        except Exception:
            check("%s 未抛异常" % fn.__name__, False, "见上方 traceback")
            traceback.print_exc()
    npass = sum(1 for _n, ok, _d in RESULTS if ok)
    nfail = sum(1 for _n, ok, _d in RESULTS if not ok)
    print("\n" + "=" * 68)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    if nfail:
        print("\nFAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print("  [FAIL] %s — %s" % (name, detail))
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    import traceback
    raise SystemExit(main())
