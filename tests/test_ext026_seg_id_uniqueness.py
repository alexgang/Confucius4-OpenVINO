"""test_ext026_seg_id_uniqueness.py — ★ EXT-026 第 5 条自测：段 id 跨会话唯一

## 这个文件要验什么（reviewer EXT-026 明文）

> **代码小缺陷，顺手修**：player.js 的 `seenDubIds` 一直不清，而段 id 是
> `seg_{s0}`/`seg_{abs0}`（每个会话从 0 开始）。player 页不关、offscreen 路径
> 重新开始一个会话时，新会话的段 id 和旧会话撞了，会被当成重复**静默丢掉**
> （又是"没配音"）。改法二选一：段 id 带上会话前缀，或者收到新会话的
> hello_ack 时清空 seenDubIds。**加一个单测。**

⇒ 本文件做**三组**验证：

  A. **服务端**：段 id 带**会话前缀** ⇒ 两个会话的同一段 id **不同**
     （`Session.public_seg_id`）
  B. **服务端**：前缀是**纯数字**且 id 末尾**仍可解析成数字**
     ⇒ `tools/compare_ext011_cores.py` 的
     `int(str(r["id"]).split("_")[-1])` 仍能用（回归保护）
  C. **插件侧**（node 沙箱跑 **真** player.js 的真函数）：
     收到**新会话**的 hello_ack ⇒ 清空 `seenDubIds`
     ⇒ 旧会话的段 id 在新会话里**不会再被当成重复**而丢掉

## ★ 可证伪（铁律：自测要能区分「真通过」与「假通过」）

  * C 组有**反证**：把「清空」这一步去掉后，同一条断言**必须变红**；
  * A 组有**对照组**：两个**不同**会话的 id 必须不同，
    而**同一**会话内重复调用必须相同（幂等）。

不跑推理 / 不占 GPU·NPU / **不创建共享锁**（纯逻辑 + node 沙箱）。

运行：
    python tests/test_ext026_seg_id_uniqueness.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from ext.bridge import Session

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  — " + detail) if (detail and not cond) else ""))


# ═══════════════════════════════════════════════════════════════════
# A 组：服务端 —— 段 id 带会话前缀
# ═══════════════════════════════════════════════════════════════════
def test_server_seg_id_has_session_prefix() -> None:
    print("\n[A] ★ 服务端：对外段 id 带会话前缀（跨会话不撞号）")
    s1 = Session("tok")
    s2 = Session("tok")

    id1 = s1.public_seg_id("seg_0")
    id2 = s2.public_seg_id("seg_0")

    check("★ A1 段 id 带会话前缀（不再是裸的 seg_0）",
          id1 != "seg_0", "实测 %r" % id1)
    check("★ A2 ★ 两个会话的同一段 id **不同**（跨会话不撞号）",
          id1 != id2, "%r vs %r" % (id1, id2))
    check("★ A3 同一会话内重复调用**幂等**（不会每次都变）",
          s1.public_seg_id("seg_0") == id1
          and s1.public_seg_id("seg_0") == id1,
          "%r vs %r" % (id1, s1.public_seg_id("seg_0")))
    check("★ A4 前缀是**纯数字**（不能含 hex 字母）",
          re.match(r"^seg_\d+_\d+$", id1) is not None,
          "实测 %r" % id1)
    # ★ 对照组：同一会话的不同段仍然不同（前缀没把段号吃掉）
    check("★ A5 同一会话的不同段 id 仍不同",
          s1.public_seg_id("seg_0") != s1.public_seg_id("seg_16000"),
          "%r / %r" % (s1.public_seg_id("seg_0"),
                       s1.public_seg_id("seg_16000")))


# ═══════════════════════════════════════════════════════════════════
# B 组：回归保护 —— id 末尾仍可解析成数字
# ═══════════════════════════════════════════════════════════════════
def test_seg_id_tail_still_numeric() -> None:
    print("\n[B] ★ 回归：id 末尾仍可解析成数字（compare_ext011_cores 的口径）")
    s = Session("tok")
    for raw in ("seg_0", "seg_16000", "seg_960000"):
        pid = s.public_seg_id(raw)
        tail = str(pid).split("_")[-1]
        try:
            n = int(tail)
            ok = True
        except Exception:
            n = None
            ok = False
        check("★ B1 %r ⇒ 末尾可 int()（= %s）" % (raw, raw.split("_")[-1]),
              ok, "实测 id=%r tail=%r" % (pid, tail))
        check("★ B2 %r ⇒ 末尾数字与原始段号一致" % raw,
              ok and n == int(raw.split("_")[-1]),
              "实测 %r vs %r" % (n, raw.split("_")[-1]))
    # ★ 实测 compare_ext011_cores.py 里那个工具的**真实排序逻辑**
    check("★ B3 compare_ext011_cores 的排序键可解析（不抛 ValueError）",
          all(isinstance(int(str(s.public_seg_id("seg_%d" % v)).split("_")[-1]), int)
              for v in (0, 16000, 960000)),
          "")


# ═══════════════════════════════════════════════════════════════════
# C 组：插件侧（node 沙箱跑真 player.js）—— 新会话清空 seenDubIds
# ═══════════════════════════════════════════════════════════════════
def test_plugin_session_reset_harness() -> None:
    print("\n[C] ★ 插件侧行为级（node 沙箱跑 player.js 的**真函数**）")
    harness = os.path.join(ROOT, "tests", "ext026_segid_harness.js")
    node = shutil.which("node") or ""
    if not node:
        check("node 可用（跳过本组）", True, "node 不可用")
        return
    player = os.path.join(ROOT, "extension", "player.js")
    r = subprocess.run([node, harness, player],
                       capture_output=True, encoding="utf-8",
                       errors="replace", timeout=180)
    out = r.stdout or ""
    print(out.rstrip())
    check("★★★ C-harness 全部通过（rc=0）",
          r.returncode == 0, "rc=%d；输出尾部：%s" % (r.returncode, out[-800:]))
    check("C-harness 至少跑了 10 项断言",
          out.count("[PASS]") >= 10, "PASS 数=%d" % out.count("[PASS]"))
    check("C-harness 里没有 FAIL", "[FAIL]" not in out, out[-400:])


def main() -> int:
    print("=" * 68)
    print("EXT-026 自测（第 5 条）：段 id 跨会话唯一 / 新会话清空 seenDubIds")
    print("=" * 68)
    for fn in (test_server_seg_id_has_session_prefix,
               test_seg_id_tail_still_numeric,
               test_plugin_session_reset_harness):
        try:
            fn()
        except Exception:
            traceback.print_exc()
            check("★ %s 未抛异常" % fn.__name__, False, "见上方 traceback")

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
