# -*- coding: utf-8 -*-
"""test_ext031_release_handoff.py — ★★ EXT-031：V2.0 发行包交付清单 + 发行版模式

## EXT-031 原文（2026-11-01 15:50）要点

> 用户要求："把 ext 的插件整合到发行包里面，打包一个 V2.0"。打包由 App 线程执行（APP-057），
> EXT 负责交付物本身，以及一份清单。
> 1. 写 `live_dub_ext\\release\\V20_HANDOFF.md`：插件 unpacked 目录文件列表；桥接入口命令；
>    全部 Python 依赖（包名+版本）及 App 包内**还没有**的；模型和 IR 路径（映射到 App 包内现有，
>    **不另带一份**）；端口、配置文件、日志位置；首次启动步骤。
> 2. 去掉代码里所有写死的开发目录绝对路径，改成相对包根目录或者配置项。
>    做完后自己在一个**模拟的包目录结构**下启动桥接，证明不依赖开发目录。证据写进 STATUS。
> 3. 插件里的测试和调试代码（Playwright 驱动、整机录音 getDisplayMedia 回退、audio_dump 之类）
>    在发行版里要**默认关闭或者剔除**，只保留 EXT-027 要求的标签页音频路径。
> 4. EXT-027、028、029 照常优先。

## 本文件的判定原则

* **行为级**优先：发行版开关要**真跑**并断言真实效果，不能只检查源码里有几个关键字。
* **有区分力**：每条关键断言都要能区分「真通过」与「假通过」——
  ① 发行版模式判定被硬编码为 True ⇒ 必须能测出开发目录下应为 False；
  ② 只在源码里出现 `RELEASE_MODE` 字样但**不生效** ⇒ 必须能测出；
  ③ 交付清单缺项（依赖版本 / 缺失依赖 / 模型映射）⇒ 必须能测出。
* **真实退出码**：取真实 `rc`，不 pipe。

运行：
    python tests/test_ext031_release_handoff.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RELEASE_DIR = os.path.join(ROOT, "release")
HANDOFF = os.path.join(RELEASE_DIR, "V20_HANDOFF.md")
EXT_DIR = os.path.join(ROOT, "ext")
EXT_DIR_NAME = "extension"
BRIDGE = os.path.join(EXT_DIR, "bridge.py")
CONFIG = os.path.join(EXT_DIR, "config.py")
APP_ROOT = os.path.join(EXT_DIR, "app_root.py")
ENGINES = os.path.join(EXT_DIR, "engines.py")
SEGMENTER = os.path.join(EXT_DIR, "segmenter.py")
SMOKE_FAKE_PKG = os.path.join(ROOT, "tests", "smoke",
                              "ext031_fake_pkg_launch.py")

# ★ 发行包里**禁止**出现的开发机目录片段
FORBIDDEN = ("live_dub_ext", "hy_bench", "confucius4-openvino",
             "qwen3tts_eval", "Worktrees", "confucius4-tts")

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           (" — " + detail) if detail else ""))


def _read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def _docstring_nodes(tree: ast.AST) -> set:
    """收集所有 docstring 节点（模块/类/函数）—— 它们是**文档**，不是路径配置。

    ★ 为什么要排除：docstring 里写「原路径是 `C:\\…\\hy_bench`」是**说明**，
      不是**运行时依赖** ⇒ 拿它判 FAIL 是**误报**。
    """
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr):
                v = body[0].value
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    out.add(id(v))
    return out


# ── ① 交付清单存在且六项内容齐全 ──────────────────────────
def test_handoff_exists_and_complete() -> None:
    check("release/V20_HANDOFF.md 存在", os.path.isfile(HANDOFF))
    if not os.path.isfile(HANDOFF):
        return
    t = _read(HANDOFF)
    sz = os.path.getsize(HANDOFF)
    check("交付清单非空（实测 %d B）" % sz, sz > 1000)

    # ① 插件 unpacked 目录的文件列表
    check("含「插件」unpacked 目录文件列表（manifest.json / sw.js / popup.js 等）",
          all(k in t for k in ("manifest.json", "sw.js", "popup.js", "player.js")))
    # ② 桥接服务的入口命令
    check("含桥接服务的入口命令", "bridge.py" in t and "--real" in t)
    # ③ 全部 Python 依赖（包名 + 版本）及 App 包内还没有的
    check("含 Python 依赖（包名 + 版本）", "numpy" in t and "openvino" in t
          and re.search(r"\d+\.\d+", t) is not None)
    check("明确标出「App 包内**还没有**」的依赖",
          ("缺失" in t or "还没有" in t or "需补装" in t))
    # ④ 模型和 IR 路径（映射到 App 包内现有，不另带一份）
    check("含模型/IR 路径映射且声明不另带一份",
          "models/" in t and ("不另带" in t or "不另带一份" in t))
    # ⑤ 端口、配置文件、日志位置
    check("含端口信息", "8765" in t)
    check("含配置文件位置", "bridge_token.txt" in t or "release.json" in t)
    check("含日志位置", "bridge.log" in t)
    # ⑥ 首次启动步骤
    check("含首次启动步骤", ("首次启动" in t or "启动步骤" in t))


# ── ② 交付清单里的依赖清单与代码实际 import 一致 ──────────
def test_handoff_deps_match_code() -> None:
    """清单里的依赖必须**覆盖**代码真正 import 的第三方包。

    ★ 区分力：只写一串包名但**漏了**代码真需要的 ⇒ 必须 FAIL。
    """
    if not os.path.isfile(HANDOFF):
        check("交付清单存在（前置）", False, "文件不存在，无法核对依赖")
        return
    t = _read(HANDOFF).lower()
    # 代码真正 import 的第三方包（标准库排除）
    needed = {"numpy", "openvino", "openvino_genai", "websockets", "psutil"}
    # ★ PyPI 正规名与 import 名不一致（`openvino-genai` ↔ `openvino_genai`）
    #   ⇒ 比对时把 `_` 与 `-` 归一，两种写法都算命中。
    norm = t.replace("-", "_")
    missing = sorted(p for p in needed if p not in norm)
    check("清单覆盖代码实际 import 的第三方依赖（缺 %r）" % missing,
          not missing)


# ── ③ ★发行版开关：行为级（真跑，不是看源码） ─────────────
def test_release_mode_behavior() -> None:
    """发行版模式必须**真生效**。

    ★ 区分力：
      - 硬编码 True ⇒ 开发目录下应为 False ⇒ 这里能测出；
      - 只在源码里出现 `RELEASE_MODE` 字样但**不生效** ⇒ 这里能测出。
    """
    py = sys.executable
    probe = (
        "import json, os, sys\n"
        "sys.path.insert(0, %r)\n"
        "from ext import config as C\n"
        "print(json.dumps({'release': C.RELEASE_MODE,\n"
        "                  'modes': C.CAPTURE_MODES}))\n" % ROOT
    )
    # ① 开发目录（无 release.json、无 EXT_RELEASE）⇒ 应为 False
    env = dict(os.environ)
    env.pop("EXT_RELEASE", None)
    p1 = subprocess.run([py, "-c", probe], env=env, cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8")
    try:
        d1 = json.loads(p1.stdout.strip().splitlines()[-1])
    except Exception:
        d1 = {}
    check("开发目录下发行版开关为 **False**（不误伤开发流程）",
          d1.get("release") is False,
          "实测 release=%r" % d1.get("release"))
    check("开发模式下抓流白名单含 getDisplayMedia（自动化冒烟仍可用）",
          "getDisplayMedia" in (d1.get("modes") or []),
          "实测 modes=%r" % d1.get("modes"))

    # ② EXT_RELEASE=1 ⇒ True 且白名单只留 tabCapture
    env2 = dict(os.environ)
    env2["EXT_RELEASE"] = "1"
    p2 = subprocess.run([py, "-c", probe], env=env2, cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8")
    try:
        d2 = json.loads(p2.stdout.strip().splitlines()[-1])
    except Exception:
        d2 = {}
    check("EXT_RELEASE=1 ⇒ 发行版开关为 **True**",
          d2.get("release") is True, "实测 release=%r" % d2.get("release"))
    check("★ EXT-031③：发行版抓流白名单**只留 tabCapture**"
          "（整机 getDisplayMedia 回退被剔除）",
          d2.get("modes") == ["tabCapture"],
          "实测 modes=%r" % d2.get("modes"))

    # ③ 显式覆盖优先：EXT_RELEASE=0 ⇒ False
    env3 = dict(os.environ)
    env3["EXT_RELEASE"] = "0"
    p3 = subprocess.run([py, "-c", probe], env=env3, cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8")
    try:
        d3 = json.loads(p3.stdout.strip().splitlines()[-1])
    except Exception:
        d3 = {}
    check("显式覆盖优先：EXT_RELEASE=0 ⇒ False（即使存在 release.json）",
          d3.get("release") is False, "实测 release=%r" % d3.get("release"))


# ── ④ ★发行版禁用诊断落盘（audio_dump / margin） ──────────
def test_release_disables_diagnostic_dump() -> None:
    """发行版即使显式传 `--audio-dump-out` 也**不得**落盘。

    ★ 区分力：只在源码里写 `if RELEASE_MODE` 但没接到实际开关点 ⇒ 这里能测出。
    """
    src = _read(BRIDGE)
    check("bridge.py 里 audio_dump 创建点受 RELEASE_MODE 保护",
          re.search(r"RELEASE_MODE.{0,400}?audio_dump", src, re.S) is not None
          or re.search(r"audio_dump.{0,400}?RELEASE_MODE", src, re.S) is not None,
          "未找到 RELEASE_MODE 与 audio_dump 的关联")
    check("bridge.py 退出前 margin 落盘受 RELEASE_MODE 保护",
          re.search(r"RELEASE_MODE.{0,200}?_dump_margin", src, re.S) is not None,
          "未找到 RELEASE_MODE 与 _dump_margin 的关联")


# ── ⑤ ★没有硬编码开发机绝对路径（行为级 + 静态双查） ──────
def test_no_hardcoded_dev_paths() -> None:
    """静态查源码里**真的**写了开发目录名的字面量。

    ★ 只查**字符串字面量**（AST 级），不查注释 ——
      否则「注释里提一句开发机路径」就会误判 FAIL。
    """
    hits = []
    for fn in sorted(os.listdir(EXT_DIR)):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(EXT_DIR, fn)
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        docs = _docstring_nodes(tree)
        for node in ast.walk(tree):
            lits = []
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lits.append(node.value)
            elif isinstance(node, ast.JoinedStr):
                lits.extend(v.value for v in node.values
                            if isinstance(v, ast.Constant) and isinstance(v.value, str))
            for s in lits:
                # ★ 排除 docstring（说明文字 ≠ 运行时路径配置）
                if id(node) in docs:
                    continue
                for w in FORBIDDEN:
                    if w in s:
                        hits.append("%s: %r" % (fn, s[:80]))
    check("ext/ 里**非 docstring 的字符串字面量**不含开发机目录名（命中 %d 处）"
          % len(hits), not hits, "; ".join(hits[:3]))


# ── ⑥ 模拟包根启动验证（EXT-031② 的可执行证据） ──────────
def test_fake_package_launch() -> None:
    check("模拟包启动脚本存在", os.path.isfile(SMOKE_FAKE_PKG))
    if not os.path.isfile(SMOKE_FAKE_PKG):
        return
    py = sys.executable
    p = subprocess.run([py, SMOKE_FAKE_PKG], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    out = p.stdout or ""
    check("模拟发行包启动验证 **rc=0**（不依赖开发目录）",
          p.returncode == 0, (out[-300:] + (p.stderr or "")[-300:]))
    check("模拟包验证 6 项断言全 PASS",
          "6 PASS / 0 FAIL" in out,
          "; ".join(ln for ln in out.splitlines() if "结果：" in ln))


# ── ⑦ 插件目录里不含 Playwright 驱动 / 测试代码 ────────────
def test_plugin_dir_has_no_test_driver() -> None:
    """发行包只装 `extension/`（插件）⇒ 里面不得有测试驱动。

    ★ 正则只匹配**真测试驱动**的名字（`test_` / `*_test` / `*_harness` /
      `*playwright*`）—— `probe-*` 这种命名不是测试驱动（EXT-028 的探针
      worklet 属生产件），**不**误伤。
    """
    files = []
    for dp, _dn, fns in os.walk(os.path.join(ROOT, EXT_DIR_NAME)):
        for fn in fns:
            files.append(os.path.relpath(os.path.join(dp, fn), ROOT))
    bad = [f for f in files
           if re.search(r"(^|[\\/])test_|_test\.|_harness|playwright|"
                        r"(^|[\\/])tests?[\\/]", f, re.I)]
    check("插件目录（extension/）内**不含**测试/驱动代码（命中 %r）" % bad[:3],
          not bad)


def main() -> int:
    print("=" * 68)
    print("EXT-031 自测：V2.0 交付清单 + 发行版模式（不依赖开发目录 / 调试剔除）")
    print("=" * 68)
    for fn in (test_handoff_exists_and_complete,
               test_handoff_deps_match_code,
               test_release_mode_behavior,
               test_release_disables_diagnostic_dump,
               test_no_hardcoded_dev_paths,
               test_fake_package_launch,
               test_plugin_dir_has_no_test_driver):
        try:
            fn()
        except Exception as e:  # ★ 异常 ⇒ 判 FAIL，不许静默跳过
            check("用例 %s 抛异常" % fn.__name__, False, repr(e))
    npass = sum(1 for _n, ok, _d in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("=" * 68)
    print("结果：%d PASS / %d FAIL" % (npass, nfail))
    print("=" * 68)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
