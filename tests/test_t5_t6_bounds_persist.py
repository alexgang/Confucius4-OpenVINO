"""test_t5_t6_bounds_persist.py — ★ 自发任务 T-5 / T-6 自测

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

## 背景（为什么做这件事）

闸门 `tools/next_instruction.py --json` → **exit 1**（latest=EXT-026 /
last_ack=26）⇒ 没有新纠偏指令；但按 **EXT-014 ②**（常设规则「`last_ack`
追平后仍要继续下一项」）⇒ 继续 STATUS「未完成纠偏清单」里的 **P2 待办**
（`克隆音色 / ducking / 字幕 / 设置持久化 / 暂停拖动 / 30 分钟不崩 …`）。

⇒ 其中**不需要 reviewer 决策、也不需要真实引擎**的两项本轮做掉：

| 编号 | 项 | 发现的真缺陷 |
|---|---|---|
| **T-5** | **30 分钟不崩 / 内存不持续增长** | ① 服务端 `Session._frame_arrival_delays` **每帧追加、永不裁剪**（47 帧/秒 ⇒ 30 分钟 ≈ 8.5 万条/会话）；② `Session._seg_orig_end` / `_seg_ready` **只写不读** ⇒ 每段永久留两个 key；③ 插件 `player.js` / `offscreen.js` 的 `gapDetail` **只追加、永不裁剪** ⇒ 网络抖动时无限增长 |
| **T-6** | **设置持久化** | `popup.js` 的 `saveCfg()` **只在点「开始」时**被调用 ⇒ 用户改了「目标语言 / 延迟 D / 原声压低量 / 字幕开关」后**直接关掉弹窗** ⇒ 改动**全部丢失** |

## 本文件的判定原则

* **行为级优先**：插件侧用 **node 沙箱**跑 `player.js` / `popup.js` 的
  **真实函数**（`tests/t5_t6_bounds_persist_harness.js`）；
  服务端用**真起桥接服务**（回声模式，不跑推理）+ 真喂帧。
* **有区分力**：每组都配**反证**（把接线拆掉 ⇒ 必须 FAIL），
  避免「恒真断言」把回归掩盖掉。
* **口径不变**：T-5 的统计口径（`n_frames_measured` / `late_ratio` /
  `max` / `mean`）**必须与裁剪前一致** ⇒ 断言会比对**同一份喂帧**在
  「有界」与「无界」两种实现下的读数是否相同。
* **真实退出码**：取真实 `rc`，不 pipe（`| tail` 会洗掉 rc）。

运行：
    python tests/test_t5_t6_bounds_persist.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EXT_DIR = os.path.join(ROOT, "extension")
HARNESS = os.path.join(ROOT, "tests", "t5_t6_bounds_persist_harness.js")
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if (detail and not cond) else ""))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _node() -> str:
    return shutil.which("node") or ""


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ══════════════════════════════════════════════════════════════
# A 组：插件侧行为级（node 沙箱跑 player.js / popup.js 的真函数）
# ══════════════════════════════════════════════════════════════
def test_plugin_behavior() -> None:
    print("\n[A] ★ 插件侧行为级：node 沙箱跑 player.js / popup.js 的真实函数")
    node = _node()
    if not node:
        check("node 可用（跳过本组）", True, "node 不可用")
        return
    check("★ harness 存在", os.path.isfile(HARNESS), HARNESS)
    if not os.path.isfile(HARNESS):
        return

    r = subprocess.run([node, HARNESS], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    out = (r.stdout or "")
    check(f"★ harness 退出码 0（实测 rc={r.returncode}）", r.returncode == 0,
          (out or r.stderr or "")[-800:])
    m = re.search(r"结果：(\d+) PASS / (\d+) FAIL / 共 (\d+)", out)
    check("★ harness 打印了汇总行", m is not None, out[-300:])
    if m:
        npass, nfail, ntot = int(m.group(1)), int(m.group(2)), int(m.group(3))
        check(f"★ harness 全通过（{npass} PASS / {nfail} FAIL / 共 {ntot}）",
              nfail == 0 and ntot > 0, f"实测 {npass}/{nfail}/{ntot}")
        check("★ harness 覆盖了「gapDetail 有界」",
              "gapDetail 灌 10 000 条后被裁到" in out)
        check("★ harness 覆盖了「改了设置且没点开始 ⇒ 已落盘」",
              "改了设置**且没点开始**" in out)
        check("★ harness 覆盖了「裁剪块短路 ⇒ 无限增长」反证",
              "确实会无限增长" in out)
        check("★ harness 覆盖了「不挂监听 ⇒ 不写盘」反证",
              "不会**写盘" in out or "不挂监听时" in out)

    # ★★ 反证：把 player.js 的裁剪短路 ⇒ harness 必须 FAIL
    #   ⇒ 若仍 PASS ⇒ harness 没有区分力。
    with tempfile.TemporaryDirectory() as td:
        broken = os.path.join(td, "player_broken.js")
        src = _read(os.path.join(EXT_DIR, "player.js"))
        s2 = src.replace(
            "if (upState.gapDetail.length > GAP_DETAIL_CAP) {",
            "if (false) { /* 反证：裁剪被短路 */")
        if s2 == src:
            check("★ 反证准备：能在 player.js 里找到裁剪点", False,
                  "没找到裁剪接线点")
        else:
            with open(broken, "w", encoding="utf-8") as f:
                f.write(s2)
            r2 = subprocess.run([node, HARNESS, broken], cwd=ROOT,
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=120)
            out2 = (r2.stdout or "")
            check(f"★★ 反证：改坏 player.js 的裁剪后 harness 必须 FAIL"
                  f"（实测 rc={r2.returncode}）",
                  r2.returncode != 0,
                  "harness 对坏实现仍报 PASS ⇒ 没有区分力")

    # ★★ 反证：把 popup.js 的绑定函数改坏 ⇒ harness 必须 FAIL
    with tempfile.TemporaryDirectory() as td:
        broken = os.path.join(td, "popup_broken.js")
        src = _read(os.path.join(EXT_DIR, "popup.js"))
        # ⚠️ **行尾符无关**：仓库里的 .js 可能被 git 以 CRLF 检出
        #   ⇒ 正则里不能写死 `\n` ⇒ 统一用 `\r?\n`。
        s2 = re.sub(r"function bindPersistListeners\(\) \{[\s\S]*?\r?\n\}\r?\n",
                    "function bindPersistListeners() { /* 反证 */ }\n", src)
        if s2 == src:
            check("★ 反证准备：能在 popup.js 里找到绑定函数", False,
                  "没找到 bindPersistListeners")
        else:
            with open(broken, "w", encoding="utf-8") as f:
                f.write(s2)
            r2 = subprocess.run([node, HARNESS,
                                 os.path.join(EXT_DIR, "player.js"), broken],
                                cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=120)
            out2 = (r2.stdout or "")
            check(f"★★ 反证：改坏 popup.js 的绑定后 harness 必须 FAIL"
                  f"（实测 rc={r2.returncode}）",
                  r2.returncode != 0,
                  "harness 对坏实现仍报 PASS ⇒ 没有区分力")


# ══════════════════════════════════════════════════════════════
# B 组：服务端「内存不持续增长」（真起桥接服务 + 真喂帧）
# ══════════════════════════════════════════════════════════════
def test_server_bounded() -> None:
    print("\n[B] ★ 服务端：逐帧到达延迟必须**有界**，且统计口径不变")
    try:
        from ext import bridge as B  # noqa: F401
        from ext import config as C
    except Exception as e:
        check("★ ext.bridge 可导入", False, str(e))
        return

    check("★ 配置里有 FRAME_DELAY_HISTORY 常量",
          hasattr(C, "FRAME_DELAY_HISTORY") and C.FRAME_DELAY_HISTORY > 0,
          str(getattr(C, "FRAME_DELAY_HISTORY", None)))
    check("★ 配置里有 SEG_TIMING_HISTORY 常量",
          hasattr(C, "SEG_TIMING_HISTORY") and C.SEG_TIMING_HISTORY > 0,
          str(getattr(C, "SEG_TIMING_HISTORY", None)))

    sess = B.Session(token="t", delay_sec=10.0, engine=None)
    # ★ 灌足够多的帧，触发裁剪。
    #   ⚠️ **确定性**：显式设 `t0` 并用**固定偏移**的 `recv_at`
    #   ⇒ `arrival_delay` 完全确定（不掺墙钟噪声）⇒ 下面对照有意义。
    base_t0 = 1000.0
    sess.t0 = base_t0
    n_frames = C.FRAME_DELAY_HISTORY * 3 + 500
    import numpy as np
    for i in range(n_frames):
        pcm = np.zeros(1600, dtype=np.float32)
        raw = (pcm * 32767).astype("<i2").tobytes()
        recv_at = base_t0 + (i * 1600) / 16000.0 + 0.25
        sess.on_pcm_frame({
            "seq": i,
            "sample_index": i * 1600,
            "pcm": base64.b64encode(raw).decode("ascii"),
        }, recv_at=recv_at)

    check(f"★ 灌 {n_frames} 帧后，_frame_arrival_delays 被裁到 ≤ "
          f"{C.FRAME_DELAY_HISTORY}",
          len(sess._frame_arrival_delays) <= C.FRAME_DELAY_HISTORY,
          f"实测 {len(sess._frame_arrival_delays)} 条")

    fad = sess.stats().get("feed_arrival_delay") or {}
    check("★ 统计口径：n_frames_measured 统计的是**全部**帧（不是窗口大小）",
          int(fad.get("n_frames_measured") or 0) >= n_frames,
          f"实测 {fad.get('n_frames_measured')}（灌了 {n_frames} 帧）")
    check("★ 统计口径：late_ratio 有值且在 [0,1]",
          fad.get("late_ratio") is not None
          and 0.0 <= float(fad["late_ratio"]) <= 1.0,
          f"实测 {fad.get('late_ratio')}")
    check("★ 统计口径：mean_delay_sec 有值",
          fad.get("mean_delay_sec") is not None,
          f"实测 {fad.get('mean_delay_sec')}")
    check("★ 统计口径：max_delay_sec ≥ mean_delay_sec",
          float(fad.get("max_delay_sec") or 0)
          >= float(fad.get("mean_delay_sec") or 0),
          f"max={fad.get('max_delay_sec')} mean={fad.get('mean_delay_sec')}")
    check("★ 统计口径：last_delay_sec 有值（窗口末条）",
          fad.get("last_delay_sec") is not None,
          f"实测 {fad.get('last_delay_sec')}")
    check("★ 如实暴露保留窗口大小（history_window / history_kept）",
          int(fad.get("history_window") or 0) == C.FRAME_DELAY_HISTORY
          and int(fad.get("history_kept") or 0) <= C.FRAME_DELAY_HISTORY,
          f"window={fad.get('history_window')} kept={fad.get('history_kept')}")

    # ★★ 口径对照：同一份喂帧，**有界**与**无界**的统计必须一致
    #   ⇒ 无界 = 把裁剪上限临时调到极大（等价于「不裁剪」）
    #
    # ⚠️ **确定性**：两个 session 的 `t0` 是**各自构造时刻**的
    #   `time.perf_counter()` ⇒ 直接喂帧会因 t0 不同而算出不同的
    #   `arrival_delay` ⇒ 比对就会读到**墙钟噪声**（不是口径差异）。
    #   ⇒ 做法：① 显式把两个 session 的 `t0` 设成**同一个值**；
    #     ② 用**同一组 recv_at**（`t0 + 固定偏移`）喂 ⇒
    #     `arrival_delay` 完全确定 ⇒ 比对才有意义。
    sess2 = B.Session(token="t", delay_sec=10.0, engine=None)
    old_cap = C.FRAME_DELAY_HISTORY
    try:
        C.FRAME_DELAY_HISTORY = 10 ** 9      # 相当于「不裁剪」
        # ③ 把两个 session 的 t0 对齐到**同一个基准点**
        base_t0 = 1000.0
        sess.t0 = base_t0
        sess2.t0 = base_t0
        # ④ 用**同一组 recv_at** 喂（固定偏移 ⇒ delay 确定）
        for i in range(n_frames):
            pcm = np.zeros(1600, dtype=np.float32)
            raw = (pcm * 32767).astype("<i2").tobytes()
            msg = {
                "seq": i,
                "sample_index": i * 1600,
                "pcm": base64.b64encode(raw).decode("ascii"),
            }
            recv_at = base_t0 + (i * 1600) / 16000.0 + 0.25
            sess2.on_pcm_frame(msg, recv_at=recv_at)
    finally:
        C.FRAME_DELAY_HISTORY = old_cap
    fad2 = sess2.stats().get("feed_arrival_delay") or {}
    for k in ("n_frames_measured", "n_frames_late_gt_1s", "late_ratio",
              "max_delay_sec", "mean_delay_sec"):
        check(f"★ 口径对照：裁剪前后 `{k}` 相同",
              fad.get(k) == fad2.get(k),
              f"有界={fad.get(k)} 无界={fad2.get(k)}")
    check("★ 口径对照：裁剪前后 `last_delay_sec` 相同",
          fad.get("last_delay_sec") == fad2.get("last_delay_sec"),
          f"有界={fad.get('last_delay_sec')} 无界={fad2.get('last_delay_sec')}")
    check("★ 口径对照：裁剪前后 `history_kept` 更小（有界才真的裁了）",
          int(fad.get("history_kept") or 0) < int(fad2.get("history_kept") or 0),
          f"有界={fad.get('history_kept')} 无界={fad2.get('history_kept')}")


# ══════════════════════════════════════════════════════════════
# C 组：服务端段级时刻表必须**有界**
# ══════════════════════════════════════════════════════════════
def test_seg_timing_bounded() -> None:
    print("\n[C] ★ 服务端：段级时刻表必须**有界**（原来只写不读）")
    try:
        from ext import bridge as B
        from ext import config as C
    except Exception as e:
        check("★ ext.bridge 可导入", False, str(e))
        return

    sess = B.Session(token="t", delay_sec=10.0, engine=None)
    # 直接灌段级时刻表（模拟收了很多段）
    for i in range(C.SEG_TIMING_HISTORY * 3 + 100):
        sess._seg_orig_end[f"seg_{i}"] = float(i)
        sess._seg_ready[f"seg_{i}"] = float(i) + 0.5
        sess._trim_seg_timing_history()

    check(f"★ _seg_orig_end 被裁到 ≤ {C.SEG_TIMING_HISTORY}",
          len(sess._seg_orig_end) <= C.SEG_TIMING_HISTORY,
          f"实测 {len(sess._seg_orig_end)}")
    check(f"★ _seg_ready 被裁到 ≤ {C.SEG_TIMING_HISTORY}",
          len(sess._seg_ready) <= C.SEG_TIMING_HISTORY,
          f"实测 {len(sess._seg_ready)}")
    check("★ 裁剪后仍保留**最近**的段",
          max(sess._seg_orig_end.keys()) ==
          f"seg_{C.SEG_TIMING_HISTORY * 3 + 99}",
          f"实测最大 key={max(sess._seg_orig_end.keys()) if sess._seg_orig_end else '无'}")

    # ★★ 反证：把裁剪函数改坏（直接 return）⇒ 必然无限增长
    sess2 = B.Session(token="t", delay_sec=10.0, engine=None)
    broken = B.Session._trim_seg_timing_history
    try:
        B.Session._trim_seg_timing_history = lambda self: None
        for i in range(C.SEG_TIMING_HISTORY * 3 + 100):
            sess2._seg_orig_end[f"seg_{i}"] = float(i)
            sess2._trim_seg_timing_history()
    finally:
        B.Session._trim_seg_timing_history = broken
    check("★★ 反证：裁剪被短路后 _seg_orig_end **确实会无限增长**"
          "（证明上面断言有区分力）",
          len(sess2._seg_orig_end) > C.SEG_TIMING_HISTORY,
          f"实测 {len(sess2._seg_orig_end)}")


# ══════════════════════════════════════════════════════════════
# D 组：设置持久化 —— 源码层口径 + 与既有 T-3 的一致性
# ══════════════════════════════════════════════════════════════
def test_persist_wiring_source() -> None:
    print("\n[D] ★ 设置持久化：popup.js 的接线（源码层口径）")
    popup = _read(os.path.join(EXT_DIR, "popup.js"))

    check("★ popup.js 有 bindPersistListeners 函数",
          "function bindPersistListeners" in popup)
    check("★ popup.js 的 persistCfgNow 真的写 chrome.storage.local",
          re.search(r"async function persistCfgNow[\s\S]*?"
                    r"chrome\.storage\.local\.set", popup) is not None)
    check("★ popup.js 挂了 change 监听（即时落盘）",
          re.search(r"addEventListener\('change'", popup) is not None)
    check("★ popup.js 挂了 input 监听（文本框防抖落盘）",
          re.search(r"addEventListener\('input'", popup) is not None)
    check("★ popup.js 的 bindPersistListeners 被真正调用",
          re.search(r"^bindPersistListeners\(\);", popup, re.M) is not None)
    check("★ popup.js 的落盘值经过归一（normalizeLang）",
          re.search(r"targetLang:\s*normalizeLang\(", popup) is not None)
    check("★ popup.js 的落盘值经过归一（normalizeVoice）",
          re.search(r"voice:\s*normalizeVoice\(", popup) is not None)
    check("★ popup.js 的输入走防抖（不每敲一键写一次盘）",
          "PERSIST_DEBOUNCE_MS" in popup)

    # ★ 8 个设置控件都要被绑定
    ids = ["ws", "token", "delay", "lang", "voice", "duck", "subs", "player"]
    m = re.search(r"const ids = \[([^\]]*)\]", popup)
    check("★ 绑定函数列出了全部 8 个设置控件",
          m is not None and all(f"'{i}'" in m.group(1) for i in ids),
          m.group(1) if m else "没找到 ids 列表")

    # ★ 与 T-3 的一致性：saveCfg 必须也走归一后的 readCfg
    check("★ popup.js 的 saveCfg 复用 readCfg（两条写盘路径口径一致）",
          re.search(r"async function saveCfg\(\) \{[\s\S]*?readCfg\(\)",
                    popup) is not None)


def main() -> int:
    print("=" * 72)
    print("T-5 / T-6 自测：内存不持续增长（无界列表有界化）"
          " + 设置持久化（改了立刻落盘）")
    print("=" * 72)
    for fn in (test_plugin_behavior, test_server_bounded,
               test_seg_timing_bounded, test_persist_wiring_source):
        try:
            fn()
        except Exception as e:
            traceback.print_exc()
            RESULTS.append((fn.__name__, False, str(e)))
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 72)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    if nfail:
        print("\nFAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(" - %s — %s" % (name, detail))
    print("=" * 72)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
