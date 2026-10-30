"""test_ext016_compression.py — ★ EXT-016：压缩 STATUS 与 CORRECTIONS 的自测

## EXT-016 原文（2026-10-30 12:49）

> 用户要求："各模块的 CORRECTIONS 和 STATUS 内容太大，会消耗很多 token，建议压缩一下。"
> ① **STATUS 拆分**：现有 STATUS 原样移到 `status/archive/STATUS_<模块>_upto_<YYYYMMDD>.md`
>    （只读归档，不删内容），新建精简版 STATUS，**≤ 300 行 / ≤ 40 KB**。
> ② **CORRECTIONS 压缩**：已完成的纠偏全文移到 `status/archive/CORRECTIONS_<模块>_closed_upto_<YYYYMMDD>.md`；
>    CORRECTIONS 文件只保留：顶部索引表 + 进行中全文 + 最近 5 条全文。
>    **编号和标题格式保持不变**，reviewer 的推送工具会继续往文件末尾追加。
>    **如果你的幂等闸门或脚本解析这个文件，要确认压缩后仍然正常。**

## 本文件的判定原则（★ 与历史经验一致）

* **行为级**优先：闸门必须**真跑**并断言真实退出码；不能只检查文件存在。
* **有区分力**：每条关键断言都要能区分「真压缩」与「假压缩」——
  例如只把文件截短到 40 KB 但**内容没归档**、或**索引表缺条目**、或
  **闸门解析失败**，都必须被**真跑到**才算失败。
* **真实退出码**：取真实 `rc`，不 pipe（`| tail` 会洗掉 rc）。

运行：
    python tests/test_ext016_compression.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

STATUS = os.path.join(ROOT, "status", "STATUS_EXT.md")
CORRECTIONS = os.path.join(ROOT, "status", "CORRECTIONS_EXT.md")
ARCHIVE_DIR = os.path.join(ROOT, "status", "archive")
STATUS_ARCHIVE = os.path.join(ARCHIVE_DIR, "STATUS_EXT_upto_20261030.md")
CORR_ARCHIVE = os.path.join(ARCHIVE_DIR, "CORRECTIONS_EXT_closed_upto_20261030.md")
GATE = os.path.join(ROOT, "tools", "next_instruction.py")

MAX_STATUS_BYTES = 40 * 1024
MAX_STATUS_LINES = 300
N_KEEP_FULL = 5          # 最近 5 条全文
N_CLOSED = 14            # EXT-001..EXT-014 归档
LAST_NUM = 17            # 最新编号 EXT-017

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _size(path: str) -> int:
    return os.path.getsize(path)


ENTRY_RE = re.compile(
    r"^##\s+(EXT-(\d+))\s*(\[[^\]]*\])?\s*"
    r"(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?)?\s*[—\-–:：]?\s*(.*)$",
    re.MULTILINE,
)


# ── ① 精简版 STATUS 的大小与结构 ─────────────────────────────
def test_status_size_and_structure() -> None:
    check("精简版 STATUS 存在", os.path.isfile(STATUS))
    if not os.path.isfile(STATUS):
        return
    nbytes = _size(STATUS)
    with open(STATUS, "r", encoding="utf-8") as f:
        nlines = sum(1 for _ in f)
    check(f"精简版 STATUS ≤ 40 KB（实测 {nbytes} B / 上限 {MAX_STATUS_BYTES} B）",
          nbytes <= MAX_STATUS_BYTES)
    check(f"精简版 STATUS ≤ 300 行（实测 {nlines} 行 / 上限 {MAX_STATUS_LINES} 行）",
          nlines <= MAX_STATUS_LINES)

    text = _read(STATUS)
    head = text.split("\n## ", 1)[0]
    head_lines = [ln for ln in head.split("\n")]
    check(f"头部 ≤ 15 行（实测 {len(head_lines)} 行）",
          len(head_lines) <= 15, f"{len(head_lines)} 行")
    check("头部含 last_ack 字段", re.search(r"^last_ack:\s*EXT-\d+\s*$",
                                          head, re.MULTILINE) is not None)
    check("头部含「已压缩」说明并指向 archive",
          "archive/STATUS_EXT_upto_20261030.md" in head)
    for sec in ("## 当前有效结论", "## 未完成纠偏清单", "## 最近章节"):
        check(f"精简版含规定章节「{sec}」", sec in text)
    # 结论表每个数字要注明来源文件
    check("「当前有效结论」表存在且含来源文件列",
          "来源文件" in text)
    # 被推翻的旧结论不应作为「当前有效结论」出现
    concl_start = text.find("## 当前有效结论")
    concl_end = text.find("## 未完成纠偏清单")
    concl = text[concl_start:concl_end] if concl_start >= 0 and concl_end > concl_start else ""
    check("被撤回的 0.9264 未出现在「当前有效结论」表里",
          "0.9264" not in concl)


# ── ② 归档文件存在且内容完整 ─────────────────────────────
def test_archives_exist() -> None:
    check("STATUS 归档存在", os.path.isfile(STATUS_ARCHIVE))
    if os.path.isfile(STATUS_ARCHIVE):
        sz = _size(STATUS_ARCHIVE)
        check(f"STATUS 归档非空且足够大（实测 {sz} B）", sz > 100 * 1024)
        t = _read(STATUS_ARCHIVE)
        check("STATUS 归档保留全部历史章节 §1~§10",
              all(f"## §{n}" in t for n in list(range(1, 11)) + ["5.8", "5.9", "5.10"]))
        check("STATUS 归档保留旧 last_ack 痕迹（EXT-017）",
              "last_ack: EXT-017" in t)

    check("CORRECTIONS 已关闭条目归档存在", os.path.isfile(CORR_ARCHIVE))
    if os.path.isfile(CORR_ARCHIVE):
        t = _read(CORR_ARCHIVE)
        nums = sorted({int(m.group(2)) for m in ENTRY_RE.finditer(t)})
        check(f"归档含 EXT-001~EXT-{N_CLOSED:03d}（实测 {len(nums)} 条）",
              nums == list(range(1, N_CLOSED + 1)), f"实际 {nums}")
        check("归档保留了原条目全文（不止标题）",
              _size(CORR_ARCHIVE) > 20 * 1024, f"{_size(CORR_ARCHIVE)} B")


# ── ③ 压缩后的 CORRECTIONS 结构 ─────────────────────────────
def test_corrections_compressed() -> None:
    check("压缩后 CORRECTIONS 存在", os.path.isfile(CORRECTIONS))
    if not os.path.isfile(CORRECTIONS):
        return
    text = _read(CORRECTIONS)
    sz = _size(CORRECTIONS)
    check(f"压缩后 CORRECTIONS 明显变小（实测 {sz} B）", sz < 20 * 1024)

    full = sorted({int(m.group(2)) for m in ENTRY_RE.finditer(text)})
    expect_full = list(range(LAST_NUM - N_KEEP_FULL + 1, LAST_NUM + 1))
    check(f"只保留最近 {N_KEEP_FULL} 条全文（实测 EXT-{full}）",
          full == expect_full, f"实际 {full}，期望 {expect_full}")

    check("含顶部索引表", "## 索引表" in text)
    check("含「进行中的纠偏」分区", "## 进行中的纠偏" in text)
    idx_start = text.find("## 索引表")
    idx_end = text.find("## 进行中的纠偏")
    idx = text[idx_start:idx_end] if idx_start >= 0 and idx_end > idx_start else ""
    missing = [n for n in range(1, 18) if f"EXT-{n:03d}" not in idx]
    check(f"索引表覆盖全部 17 个编号（缺 {missing}）", not missing)
    check("索引表含「状态」列", "状态" in idx)

    # 标题格式必须保持不变（reviewer 推送工具依赖）
    check("保留条目标题格式仍为 `## EXT-<编号> [级别] 日期 — 标题`",
          all(re.match(r"^## EXT-\d{3} \[[A-Z]+\] \d{4}-\d{2}-\d{2}",
                       ln) for ln in text.split("\n")
                       if ln.startswith("## EXT-")))
    check("索引表不与条目标题冲突（索引表用表格行，不用 ## 标题）",
          not re.search(r"^## EXT-001\b", text, re.MULTILINE))


# ── ④ ★ 压缩后闸门仍能正常解析（行为级） ──────────────────
def test_gate_still_works() -> None:
    check("闸门脚本存在", os.path.isfile(GATE))
    if not os.path.isfile(GATE):
        return
    py = sys.executable
    proc = subprocess.run([py, GATE, "--json"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")
    rc = proc.returncode
    out = (proc.stdout or "").strip()
    check(f"闸门退出码合法（rc ∈ {0,1,2}，实测 {rc}）", rc in (0, 1, 2))
    check(f"闸门输出可解析为 JSON（实测 {out[:90]}…）",
          out.startswith("{"))
    import json
    try:
        data = json.loads(out)
    except Exception as e:
        check("闸门输出是合法 JSON", False, str(e))
        return
    check("闸门输出含 action 字段", "action" in data)
    check(f"闸门能识别出最新条目 EXT-017（实测 {data.get('latest', {}).get('id')}）",
          data.get("latest", {}).get("id") == "EXT-017")
    check("闸门能解析出 last_ack=17（实测 %s）" % data.get("last_ack"),
          data.get("last_ack") == 17)
    check("压缩后闸门判定为「已执行过」⇒ 本轮不重复执行",
          data.get("action") == "skip" and rc == 1,
          f"action={data.get('action')} rc={rc}")

    # ★ 区分力：把 CORRECTIONS 换成「无法解析」的文件 ⇒ 闸门必须 exit 2
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        bak_c = os.path.join(td, "c.bak")
        bak_s = os.path.join(td, "s.bak")
        import shutil
        shutil.copy2(CORRECTIONS, bak_c)
        shutil.copy2(STATUS, bak_s)
        try:
            with open(CORRECTIONS, "w", encoding="utf-8") as f:
                f.write("# 只有标题，没有任何 EXT 条目\n")
            p2 = subprocess.run([py, GATE, "--json"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8")
            check(f"★ 区分力：纠偏文件不可解析时闸门必须 exit 2（实测 {p2.returncode}）",
                  p2.returncode == 2)
        finally:
            shutil.copy2(bak_c, CORRECTIONS)
            shutil.copy2(bak_s, STATUS)
    # 恢复后闸门仍应正常
    p3 = subprocess.run([py, GATE, "--json"], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8")
    check(f"恢复后闸门回到 exit 1（实测 {p3.returncode}）", p3.returncode == 1)


# ── ⑤ 归档未被压缩破坏（内容真的搬走了，不是复制后删了） ──────
def test_archive_not_truncated() -> None:
    if not (os.path.isfile(STATUS_ARCHIVE) and os.path.isfile(CORR_ARCHIVE)):
        return
    st = _read(STATUS_ARCHIVE)
    ct = _read(CORR_ARCHIVE)
    check("归档 STATUS 里仍有 §11 之前的大量明细（未被截断）",
          st.count("\n### ") > 40, f"{st.count(chr(10) + '### ')} 个三级标题")
    check("归档 CORRECTIONS 保留条目正文（每个条目有正文行）",
          all(len(seg.split("\n")) > 2 for seg in ct.split("## EXT-")[1:]))
    check("精简版 STATUS 不含历史全文（确实变小了）",
          _size(STATUS) < _size(STATUS_ARCHIVE) / 10)


def main() -> int:
    print("=" * 68)
    print("EXT-016 自测：压缩 STATUS 与 CORRECTIONS（大小/结构/归档/闸门可解析）")
    print("=" * 68)
    for fn in (test_status_size_and_structure, test_archives_exist,
               test_corrections_compressed, test_gate_still_works,
               test_archive_not_truncated):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            RESULTS.append((fn.__name__, False, str(e)))
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    if nfail:
        print("\nFAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(" - %s — %s" % (name, detail))
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
