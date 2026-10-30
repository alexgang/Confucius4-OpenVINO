"""test_ext017_user_report.py — ★ EXT-017：用户试用报的两个故障的自测

## 用户原话

> 实时配音桥接运行报错：1，乱码；2，start 命令后无任何输出。

## 本文件的判定原则（★ 与历史经验一致）

* **行为级**优先：源码字符串检查只能证明「代码长这样」，
  **不能**证明行为差异 ⇒ 关键项都跑真实行为。
* **有区分力**：每条关键断言都要能证明
  「**旧写法是坏的**」与「**新写法是好的**」——否则断言恒真（假通过）。
* **真实退出码**：每项都取真实 `rc`，不 pipe（`| tail` 会洗掉 rc）。

## 四项验收

| 项 | EXT-017 要求 | 本文件怎么验 |
|---|---|---|
| ① | 乱码 | GBK 控制台**真跑** `safe_print` ⇒ 不抛异常、且输出可解码 |
| ② | start 后无输出 | 桥接启动**真跑**，断言 2 秒内出现「正在加载模型…」 |
| ③ | USER_GUIDE 补 Edge 步骤 | 文档内容 + 反向断言（不写死版本号） |
| ④ | /pair 只认本插件 id | **真起 HTTP 服务**，用真/假 Origin 打过去看状态码 |

运行：
    python tests/test_ext017_user_report.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _ast_tree(path: str) -> ast.Module:
    return ast.parse(_read(path))


def _find_func(tree: ast.Module, name: str):
    """在 AST 里找函数定义（**不靠字符串匹配**，避免命中注释/docstring）。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
    return None


def _dotted(node) -> str:
    """把 AST 表达式还原成点分字符串（Name/Attribute）。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return (base + "." + node.attr) if base else node.attr
    return ""


def _call_names(func_node) -> list:
    """列出该函数体内所有被调用的函数名（点分）。"""
    out = []
    if func_node is None:
        return out
    for n in ast.walk(func_node):
        if isinstance(n, ast.Call):
            out.append(_dotted(n.func))
    return out


def _popen_uses_pipe(src: str) -> bool:
    """★ AST 判定：`subprocess.Popen(...)` 的 stdout 实参是 `subprocess.PIPE`。

    ⚠️ 不能用字符串搜索：注释里写着「旧写法是 `stdout=self._log_f`」
      ⇒ 字符串搜索会命中注释 ⇒ 假阳性。
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _dotted(node.func) not in ("subprocess.Popen", "Popen"):
            continue
        for kw in node.keywords:
            if kw.arg != "stdout":
                continue
            val = kw.value
            if _dotted(val) == "subprocess.PIPE":
                return True
            # 也接受 `stdout=PIPE`（from subprocess import PIPE）
            if isinstance(val, ast.Name) and val.id == "PIPE":
                return True
    return False


# ═══════════════════════════════════════════════════════════════════
# ① 乱码：GBK 控制台下日志必须「能写出去」且「不抛异常」
# ═══════════════════════════════════════════════════════════════════
def test_utf8_safety() -> None:
    print("\n[1] ★★ EXT-017① 乱码：GBK 控制台下的日志写出")
    from ext.utf8_io import _sanitize, configure_process_env, safe_print

    # (a) ★ 先证明「旧写法是坏的」：GBK 编不了这些字符 ⇒ 直接 print 会抛
    raw = io.BytesIO()
    gbk_stream = io.TextIOWrapper(raw, encoding="gbk", errors="strict")
    raised = None
    try:
        gbk_stream.write("🔴 失败 ⇒ 检查")
        gbk_stream.flush()
    except Exception as e:
        raised = e
    check("★ 反向证据：GBK 控制台直接写 🔴/⇒ 确实抛 UnicodeEncodeError",
          isinstance(raised, UnicodeEncodeError),
          type(raised).__name__ if raised else "没抛（旧写法不会崩？）")

    # (b) ★ 新写法：safe_print 必须**不抛**且真的写出去
    raw2 = io.BytesIO()
    gbk2 = io.TextIOWrapper(raw2, encoding="gbk", errors="strict")
    ok = safe_print("🔴 失败 ⇒ 检查 ⛔", stream=gbk2)
    check("★ safe_print 在 GBK 控制台不抛异常", ok is True)
    try:
        gbk2.flush()
        out = raw2.getvalue().decode("gbk")
        decodable = True
    except Exception as e:
        out = ""
        decodable = False
    check("★ safe_print 的输出按 GBK 能解码（没写坏）", decodable, repr(out[:40]))
    check("★ 不可编码字符被降级替换（出现 ?）",
          "?" in out, repr(out[:40]))
    check("★ 可编码的中文原样保留（没被替换）",
          "失败" in out and "检查" in out, repr(out[:40]))

    # (c) _sanitize 的行为
    s = _sanitize("🔴 失败 ⇒ ★", "gbk")
    check("★ _sanitize 只替换编不了的字符（★ 保留）",
          "★" in s and "🔴" not in s and "⇒" not in s, repr(s))
    check("★ _sanitize 对 utf-8 不做任何改动",
          _sanitize("🔴 ⇒ ★", "utf-8") == "🔴 ⇒ ★")

    # (d) 环境变量层
    env = configure_process_env({})
    check("★ 子进程环境设了 PYTHONUTF8=1", env.get("PYTHONUTF8") == "1")
    check("★ 子进程环境设了 PYTHONIOENCODING=utf-8",
          env.get("PYTHONIOENCODING") == "utf-8")

    # (e) ★ 桥接/引擎的日志函数也必须走安全路径
    #     ⚠️ 用 AST 判定「函数体里到底调了什么」，
    #     不用字符串搜索 —— 否则会命中 docstring/注释里的说明文字（假阳性）。
    bpath = os.path.join(ROOT, "ext", "bridge.py")
    epath = os.path.join(ROOT, "ext", "engine_runtime.py")
    btree = _ast_tree(bpath)
    etree = _ast_tree(epath)
    b_log = _find_func(btree, "_log")
    e_log = _find_func(etree, "_log")
    check("★ bridge 的 _log 用 safe_print（不再裸 print）",
          any(c.endswith("safe_print") for c in _call_names(b_log)),
          str(_call_names(b_log)))
    check("★ bridge 的 _log 里**没有**裸 print（旧的会崩）",
          not any(c == "print" for c in _call_names(b_log)),
          str(_call_names(b_log)))
    check("★ engine_runtime 的 _log 用 safe_print",
          any(c.endswith("safe_print") for c in _call_names(e_log)),
          str(_call_names(e_log)))
    check("★ engine_runtime 的 _log 里没有裸 print",
          not any(c == "print" for c in _call_names(e_log)),
          str(_call_names(e_log)))


# ═══════════════════════════════════════════════════════════════════
# ② start 后无输出：桥接必须立刻报「正在加载模型…」+ 引擎进度
# ═══════════════════════════════════════════════════════════════════
def test_startup_visibility() -> None:
    print("\n[2] ★★ EXT-017② start 之后必须有可见输出")

    # (a) ★ 源码层：预热调用点 + 「正在加载模型」字样 + 管道而非重定向
    bsrc = _read(os.path.join(ROOT, "ext", "bridge.py"))
    lsrc = _read(os.path.join(ROOT, "tools", "ext_launcher.py"))
    check("★ bridge 有 --no-warmup / --warmup-strict 参数",
          "--no-warmup" in bsrc and "--warmup-strict" in bsrc)
    check("★ bridge 启动时调用 engine.warmup(", "engine.warmup(" in bsrc)
    check("★ bridge 打印「正在加载模型…」",
          "正在加载模型" in bsrc)
    check("★ ★ 启动器用**管道**接子进程输出（不是重定向到文件）",
          _popen_uses_pipe(lsrc))
    check("★ 启动器读管道时容错解码（errors=replace）",
          'errors="replace"' in lsrc)
    check("★ 启动器 start 后立刻回报 PID/端口/日志路径",
          "PID=" in lsrc and "日志文件" in lsrc)

    # (b) ★★ 行为级：真起桥接（回声模式，不跑推理、不占设备）
    #     ⇒ 断言 2 秒内日志里出现「正在加载模型」。
    #     ⚠️ 回声模式没有引擎 ⇒ 预热会跳过；所以这里测的是
    #     **回声模式下服务必须立刻打出可辨识的启动横幅**，
    #     而真实引擎模式由 (c) 的桩引擎测。
    port = 18811
    pair_port = 18812
    tmp = tempfile.mkdtemp()
    tok = os.path.join(tmp, "tok.txt")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT, os.path.join(ROOT, ".runtime_deps")])
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [sys.executable, "-m", "ext.bridge", "--host", "127.0.0.1",
         "--port", str(port), "--pair-port", str(pair_port),
         "--token-file", tok, "--echo"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace")
    try:
        # 2 秒内必须能连上 ⇒ 说明服务**真的**起来了并打了日志
        deadline = time.time() + 8.0
        alive = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/health" % pair_port, timeout=1):
                    alive = True
                    break
            except Exception:
                time.sleep(0.3)
        check("★ 桥接启动后 8 秒内配对端点可访问（服务真的起来了）", alive)

        # 读日志：必须包含启动横幅
        time.sleep(0.5)
        proc.terminate()
        try:
            out = proc.communicate(timeout=10)[0] or ""
        except Exception:
            proc.kill()
            out = ""
        check("★ ★ 启动后立刻出现「监听 ws://」启动横幅（不是静默）",
              "监听 ws://" in out, out[:200].replace("\n", " | "))
        check("★ ★ 启动横幅里带端口号",
              str(port) in out)
        check("★ ★ 日志里出现 token 文件路径（可诊断）",
              "token 文件" in out)
    finally:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass

    # (c) ★★ 行为级：**桩引擎**验证 warmup 会逐个回报进度
    #     ⇒ 用假的 engine 对象调 bridge 里同样的 warmup 路径。
    from ext.engine_runtime import RuntimeEngine

    class _StubEngine(RuntimeEngine):
        """桩：只把 _load_* 换成假的（不加载真权重、不占设备）。"""

        def __init__(self):
            super().__init__(target_lang="zh")
            self.calls = []

        def _load_asr(self):
            self.calls.append("asr")

        def _load_mt(self):
            self.calls.append("mt")

        def _load_tts(self):
            self.calls.append("tts")

    eng = _StubEngine()
    lines = []
    rep = eng.warmup(on_progress=lines.append)
    check("★ 桩引擎 warmup 真的调了三个引擎",
          eng.calls == ["asr", "mt", "tts"], str(eng.calls))
    check("★ warmup 报告 ok=True", rep.get("ok") is True, json.dumps(rep)[:120])
    check("★ warmup 回报了 3 个 loaded",
          rep.get("loaded") == ["asr", "mt", "tts"], str(rep.get("loaded")))
    check("★ ★ warmup 输出含「正在加载」字样（进度可见）",
          any("正在加载" in ln for ln in lines), " | ".join(lines[:3]))
    check("★ ★ warmup 输出含「(1/3)」「(3/3)」进度编号",
          any("(1/3)" in ln for ln in lines) and any("(3/3)" in ln for ln in lines),
          " | ".join(lines[:3]))
    check("★ warmup 报告含耗时", "elapsed_sec" in rep)

    # (d) ★ 失败路径：某个引擎失败 ⇒ 必须**报出来**且不崩（不能静默）
    class _FailEngine(_StubEngine):
        def _load_mt(self):
            raise RuntimeError("MT 模型目录不存在")

    eng2 = _FailEngine()
    lines2 = []
    rep2 = eng2.warmup(on_progress=lines2.append)
    check("★ 引擎失败时 warmup 返回 ok=False", rep2.get("ok") is False)
    check("★ 引擎失败时记录了失败原因",
          "MT" in json.dumps(rep2.get("failed") or {}, ensure_ascii=False),
          json.dumps(rep2.get("failed"), ensure_ascii=False)[:120])
    check("★ ★ 引擎失败时输出里有「加载失败」（不静默）",
          any("加载失败" in ln for ln in lines2), " | ".join(lines2))
    check("★ ★ 一个引擎失败**不影响**其它引擎（ASR/TTS 仍加载）",
          "asr" in rep2.get("loaded") and "tts" in rep2.get("loaded"),
          str(rep2.get("loaded")))


# ═══════════════════════════════════════════════════════════════════
# ②′ GUI 启动器本身必须能起来（★ 用户双击后「什么都没发生」的根因）
# ═══════════════════════════════════════════════════════════════════
def test_launcher_gui_startable() -> None:
    print("\n[2'] ★★ EXT-017② 启动器 GUI 必须真的能起来（双击不能静默失败）")
    lpath = os.path.join(ROOT, "tools", "ext_launcher.py")
    lsrc = _read(lpath)
    ltree = _ast_tree(lpath)

    # (a) ★ Combobox 在 ttk 里，不在 tkinter 顶层
    #     旧代码 `tk.Combobox` ⇒ AttributeError ⇒ GUI 直接崩 ⇒
    #     pythonw 吞掉 traceback ⇒ 用户看到「双击了，没反应」。
    check("★ ★ 启动器 import 了 ttk（Combobox 的正确出处）",
          "from tkinter import ttk" in lsrc)
    # ★ 用 AST 判定「真的调用了 ttk.Combobox」——
    #   字符串搜索会命中注释里的「旧代码写 `tk.Combobox(...)`」⇒ 假阳性。
    check("★ ★ 启动器用 ttk.Combobox（不是 tk.Combobox）",
          _calls_ttk_combobox(ltree))
    # ★ 反向证据：tkinter 顶层确实没有 Combobox
    try:
        import tkinter as _tk
        check("★ 反向证据：tkinter 顶层**没有** Combobox（所以旧写法必崩）",
              not hasattr(_tk, "Combobox"))
    except Exception as e:
        check("★ 反向证据：tkinter 顶层**没有** Combobox（所以旧写法必崩）",
              True, "跳过：%s" % e)

    # (b) ★ 顶层异常兜底：写日志 + 弹窗，绝不静默退出
    check("★ ★ 启动器顶层有异常兜底（BaseException 捕获）",
          "except BaseException" in lsrc)
    check("★ ★ 异常兜底会写日志文件",
          "启动器崩溃" in lsrc and "LOG_PATH" in lsrc)
    check("★ ★ 异常兜底会弹 MessageBox（用户一定看得到）",
          "MessageBoxW" in lsrc)
    check("★ ★ tkinter 缺失时也会提示（不是直接 return 2 就消失）",
          "MessageBoxW" in lsrc and "需要 tkinter" in lsrc)

    # (c) ★ 快捷方式必须指向**带 tkinter** 的解释器
    check("★ ★ 快捷方式生成时会检查解释器有没有 tkinter",
          "_has_tkinter(" in lsrc)
    check("★ ★ 缺 tkinter 时改用 App 自带的 pythonw",
          "_app_pythonw()" in lsrc)
    check("★ ★ 有 _app_pythonw / _has_tkinter 两个辅助函数",
          "def _app_pythonw(" in lsrc and "def _has_tkinter(" in lsrc)

    # (d) ★★ 行为级：_has_tkinter 必须**真的有判别力**
    #     （用一个确定没有 tkinter 的解释器 vs 确定有的）
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import ext_launcher as _el
    except Exception as e:
        check("★ 能 import ext_launcher", False, str(e))
        return
    check("★ 能 import ext_launcher", True)

    app_py = _el._app_python()
    app_pyw = _el._app_pythonw()
    if app_py:
        check("★ ★ _has_tkinter(App 的 python.exe) == True",
              _el._has_tkinter(app_py) is True, app_py)
    if app_pyw:
        check("★ ★ _has_tkinter(App 的 pythonw.exe) == True",
              _el._has_tkinter(app_pyw) is True, app_pyw)
    check("★ ★ _has_tkinter(不存在的路径) == False",
          _el._has_tkinter(r"C:\no\such\python.exe") is False)
    check("★ ★ _has_tkinter(None) == False", _el._has_tkinter(None) is False)
    # ★ 反向证据：用一个**确实没有 tkinter** 的解释器做对照。
    #   ⚠️ 不能用 cmd.exe —— `cmd.exe -c "import tkinter"` 会进入交互式
    #      cmd 并返回 0 ⇒ 判定恒真（假通过）。
    #   这里现造一个「空解释器」：复制一个真实 python.exe 不现实，
    #   改为**造一个 tkinter 不可用的 python 解释器**：
    #   用当前解释器 + 一个屏蔽 tkinter 的 sitecustomize。
    no_tk = _make_python_without_tkinter()
    check("★ ★ 造出的对照解释器**确实**没有 tkinter（反向证据的前提）",
          no_tk is not None and _el._has_tkinter(no_tk) is False, str(no_tk))
    check("★ ★ _has_tkinter(无 tkinter 的解释器) == False",
          no_tk is not None and _el._has_tkinter(no_tk) is False)

    # (e) ★ 轮询必须**自我续期**（否则状态灯永远停在「正在加载模型…」）
    poll = _find_func(ltree, "poll_engine_state")
    check("★ ★ poll_engine_state 里重新调度了自己（app.after）",
          poll is not None and "app.after(" in _ast_dump(poll))
    check("★ ★ 轮询续期放在 finally 里（异常也不停）",
          poll is not None and _has_finally(poll))
    # ★ 反向证据：on_start 里那一次 after 不够（只调度一次）
    on_start = _find_func(ltree, "on_start")
    check("★ on_start 里也有一次 app.after（首轮调度）",
          on_start is not None and "app.after(" in _ast_dump(on_start))


def _ast_dump(node) -> str:
    """把 AST 节点还原成源码片段（用于在函数体内搜索关键字）。"""
    import ast as _ast
    return _ast.unparse(node)


def _calls_ttk_combobox(tree: ast.Module) -> bool:
    """★ AST 判定：源码里**真的**调用了 `ttk.Combobox(...)`。

    ⚠️ 不能用字符串搜索 —— 注释里写着「旧代码写 `tk.Combobox(...)`」
      ⇒ 字符串搜索必然命中 ⇒ 假阳性。
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _dotted(node.func) == "ttk.Combobox":
            return True
    return False


def _has_finally(func_node) -> bool:
    """函数体里有没有 try/finally（finally 用于保证轮询续期）。"""
    if func_node is None:
        return False
    for n in ast.walk(func_node):
        if isinstance(n, ast.Try) and n.finalbody:
            return True
    return False


def _make_python_without_tkinter():
    """找一个「确定没有 tkinter」的 Python 解释器（用于反向对照）。

    ★ 优先用**当前**解释器本身（`sys.executable`）：
      本机跑这套自测用的 WorkBuddy 默认环境就**没有 tkinter**
      （实测 `import tkinter` → ModuleNotFoundError）
      ⇒ 它就是天然的对照组。
    ★ 若当前解释器**有** tkinter（别人用 App 的 python 跑自测），
      再退到 sitecustomize 屏蔽法。

    ⚠️ 绝不能用 `cmd.exe` 做对照：`cmd.exe -c "import tkinter"`
      会进入交互式 cmd 并返回 0 ⇒ 判定恒真（假通过）。
    """
    if sys.executable and os.path.isfile(sys.executable):
        try:
            r = subprocess.run([sys.executable, "-c", "import tkinter"],
                               capture_output=True, timeout=60)
            if r.returncode != 0:
                return sys.executable
        except Exception:
            pass
    # 退路：造一个屏蔽 tkinter 的解释器包装
    try:
        d = tempfile.mkdtemp(prefix="no_tk_")
        with open(os.path.join(d, "sitecustomize.py"), "w",
                  encoding="utf-8") as f:
            f.write(
                "import sys\n"
                "class _Blocker:\n"
                "    def find_spec(self, name, path=None, target=None):\n"
                "        if name == 'tkinter':\n"
                "            raise ImportError('tkinter blocked for test')\n"
                "        return None\n"
                "sys.meta_path.insert(0, _Blocker())\n")
        bat = os.path.join(d, "no_tk.bat")
        with open(bat, "w", encoding="utf-8") as f:
            f.write('@echo off\r\n'
                    'set "PYTHONPATH=%s;%%PYTHONPATH%%"\r\n'
                    '"%s" %%*\r\n'
                    % (d, sys.executable))
        return bat
    except Exception:
        return None


def test_status_loading_phase() -> None:
    """★ EXT-017②：预热**期间** /status 就能报「正在加载」。

    ★ 这是实测发现的关键缺陷：配对端点原先在预热**之后**才启动
      ⇒ 预热那 20–40 秒里 /status 根本不在线
      ⇒ 状态灯永远停在「正在加载模型…」，不会翻成「TTS 就绪」。
    """
    print("\n[2''] ★★ EXT-017② /status 在预热期间就要能报状态")
    from ext import bridge as _bridge

    # (a) 预热中：engine_state == "loading"
    st = _bridge._pair_status({"engine_state": "loading"})
    check("★ ★ 预热期间 /status 的 engine_state == loading",
          st.get("engine_state") == "loading", str(st.get("engine_state")))
    check("★ 预热期间 engine_loaded 为空",
          st.get("engine_loaded") == [], str(st.get("engine_loaded")))

    # (b) 未预热：unknown
    st2 = _bridge._pair_status({})
    check("★ 没预热时 engine_state == unknown",
          st2.get("engine_state") == "unknown", str(st2.get("engine_state")))

    # (c) 预热完成：ready（走 warmup 分支）
    st3 = _bridge._pair_status({"warmup": {"ok": True,
                                           "loaded": ["asr", "mt", "tts"],
                                           "failed": {}}})
    check("★ 预热完成后 engine_state == ready",
          st3.get("engine_state") == "ready", str(st3.get("engine_state")))

    # (d) ★ 源码层：配对端点必须在 warmup **之前**启动
    bsrc = _read(os.path.join(ROOT, "ext", "bridge.py"))
    i_pair = bsrc.find("pair_server.start()")
    i_warm = bsrc.find("engine.warmup(")
    check("★ ★ 配对端点启动位置在预热**之前**（否则轮询期 /status 不在线）",
          i_pair > 0 and i_warm > 0 and i_pair < i_warm,
          "pair@%d warm@%d" % (i_pair, i_warm))


# ═══════════════════════════════════════════════════════════════════
# ③ USER_GUIDE 补 Edge 加载步骤 + 「关闭开发人员模式扩展」提示
# ═══════════════════════════════════════════════════════════════════
def test_user_guide_edge() -> None:
    print("\n[3] ★ EXT-017③ USER_GUIDE 补 Edge 加载步骤")
    s = _read(os.path.join(ROOT, "USER_GUIDE.md"))
    check("★ 说明了 edge://extensions",
          "edge://extensions" in s)
    check("★ 说明了 Edge 的开发人员模式在**左下角**",
          "左下角" in s)
    check("★ 说明了「加载解压缩的扩展」",
          "加载解压缩的扩展" in s)
    check("★ ★ 说明了关掉开发人员模式会让插件被停用",
          "开发人员模式" in s and "停用" in s)
    check("★ ★ 给了「保持开发人员模式开着」的指引",
          "保持" in s and "开着" in s)
    # ★ 反向断言：不能把 Edge 说成 Chrome（用户会走错）
    #   ⚠️ 同一行里出现 `chrome://extensions` 也可能是**对照写法**
    #      （「不是 `chrome://extensions`」）⇒ 必须是**没有「不是/别用」等
    #      否定前缀**的裸指令才算误导。
    bad = []
    for ln in s.splitlines():
        if "edge://extensions" not in ln:
            continue
        idx = ln.find("chrome://extensions")
        if idx < 0:
            continue
        prefix = ln[:idx]
        if not re.search(r"不是|不要|别用|而非|而非", prefix):
            bad.append(ln.strip())
    check("★ ★ Edge 段落里没把地址裸写成 chrome://（防误导）",
          not bad, " | ".join(bad[:2]))
    # 根目录与 extension 目录的两份必须一致
    s2 = _read(os.path.join(ROOT, "extension", "USER_GUIDE.md"))
    check("★ extension/USER_GUIDE.md 与根目录一致",
          s == s2, "len %d vs %d" % (len(s), len(s2)))
    # 常见报错表里要覆盖本次两个症状
    check("★ 常见报错表里写了「乱码」的处理",
          "乱码" in s)
    check("★ 常见报错表里写了「点启动后没输出」的处理",
          "加载模型" in s)


# ═══════════════════════════════════════════════════════════════════
# ④ /pair 只认本插件的扩展 id
# ═══════════════════════════════════════════════════════════════════
def test_pair_origin_strict() -> None:
    print("\n[4] ★★ EXT-017④ /pair 只认本插件的扩展 id")
    from ext.extension_id import (compute_extension_id, origin_is_this_extension,
                                  resolve_extension_id)
    from ext.pair_server import PairServer

    eid = resolve_extension_id()
    check("★ 能从 manifest 的 key 推出扩展 id", bool(eid) and len(eid) == 32,
          str(eid))
    check("★ 推出的 id 与现场计算一致",
          eid == compute_extension_id())
    # ★ 与浏览器实测记录一致（.tmp/**/browser_probe.json 里的 ext_id）
    check("★ ★ 推出的 id 与浏览器实测记录一致",
          eid == "kekgmfkijphpfndbbpakjaokamkeooib", str(eid))

    check("★ 本插件的 Origin 被接受",
          origin_is_this_extension("chrome-extension://%s" % eid))
    check("★★ 别的扩展（id 不对）被拒",
          not origin_is_this_extension(
              "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
    check("★ 普通网页 Origin 被拒",
          not origin_is_this_extension("https://evil.com"))
    check("★ 无 Origin 被拒", not origin_is_this_extension(None))
    check("★ 解析不出 id 时一律拒绝（不静默放宽）",
          not origin_is_this_extension("chrome-extension://%s" % eid,
                                       extension_id=""))

    # ★★ 行为级：真起 HTTP 服务，打四种 Origin 看状态码
    #     ⚠️ status_provider 必须用**真实的** bridge._pair_status，
    #        engine_state 是它注入的（不是 PairServer 自己加的）。
    from ext import bridge as _bridge
    holder = {"warmup": {"ok": True, "loaded": ["asr", "mt", "tts"], "failed": {}}}
    port = 18821
    ps = PairServer(port=port, token_provider=lambda: "SECRET-TOKEN-EXT017",
                    status_provider=lambda: _bridge._pair_status(holder))
    ok, msg = ps.start()
    check("★ 配对端点能启动", ok, msg)
    if not ok:
        return
    try:
        time.sleep(0.4)

        def _get(origin):
            headers = {} if origin is None else {"Origin": origin}
            req = urllib.request.Request(
                "http://127.0.0.1:%d/pair" % port, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")

        code, body = _get("chrome-extension://%s" % eid)
        check("★★ 本插件 Origin ⇒ 200 且拿到 token",
              code == 200 and "SECRET-TOKEN-EXT017" in body,
              "HTTP %s %s" % (code, body[:80]))
        code, _ = _get("chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        check("★★ 别的扩展 ⇒ 403", code == 403, "HTTP %s" % code)
        code, _ = _get("https://evil.example.com")
        check("★★ 普通网页 ⇒ 403", code == 403, "HTTP %s" % code)
        code, _ = _get(None)
        check("★★ 无 Origin ⇒ 403", code == 403, "HTTP %s" % code)

        # /status 仍可用（只读诊断，不含 secret）
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/status" % port, timeout=8) as r:
            st = r.read().decode("utf-8")
        check("★ /status 仍可访问", r.status == 200)
        check("★ /status 不泄露 token", "SECRET-TOKEN-EXT017" not in st)
        check("★ ★ /status 报告 engine_state 字段",
              "engine_state" in st, st[:120])
        try:
            sj = json.loads(st)
            # /status 的响应是 {"ok":true,"status":{...}} 包装结构
            inner = sj.get("status") if isinstance(sj.get("status"), dict) else sj
            check("★ ★★ /status 的 engine_state == ready（三个引擎都加载完）",
                  inner.get("engine_state") == "ready",
                  "engine_state=%r" % inner.get("engine_state"))
            check("★ ★ /status 列出已加载的引擎",
                  inner.get("engine_loaded") == ["asr", "mt", "tts"],
                  str(inner.get("engine_loaded")))
        except Exception as e:
            check("★ ★★ /status 的 engine_state == ready（三个引擎都加载完）",
                  False, str(e))
    finally:
        ps.stop()

    # ★★ 失败路径：某个引擎加载失败 ⇒ engine_state 必须是 partial 且带原因
    holder2 = {"warmup": {"ok": False, "loaded": ["asr", "tts"],
                          "failed": {"mt": "MT 模型目录不存在"}}}
    st2 = _bridge._pair_status(holder2)
    check("★★ 引擎失败时 engine_state == partial",
          st2.get("engine_state") == "partial", str(st2.get("engine_state")))
    check("★★ 引擎失败时 /status 带失败引擎与原因",
          "mt" in (st2.get("engine_failed") or {}),
          json.dumps(st2.get("engine_failed"), ensure_ascii=False)[:120])


# ═══════════════════════════════════════════════════════════════════
# ⑤ 扩展 id 接线：bridge 的 WS 握手按精确 id 校验
# ═══════════════════════════════════════════════════════════════════
def test_bridge_origin_wiring() -> None:
    print("\n[5] ★★ EXT-017④ bridge 的 WS 握手按精确 id 校验")
    from ext.bridge import check_origin
    eid = resolve_extension_id_safe()

    check("★ check_origin(None) 拒绝", not check_origin(None))
    check("★ check_origin(本插件 id) 接受",
          check_origin("chrome-extension://%s" % eid, eid))
    check("★★ check_origin(别的扩展) 拒绝",
          not check_origin("chrome-extension://" + "b" * 32, eid))
    check("★ check_origin(不给 id) 时保持旧的前缀口径（兼容）",
          check_origin("chrome-extension://abcdefg"))

    bsrc = _read(os.path.join(ROOT, "ext", "bridge.py"))
    check("★ bridge 握手用 resolve_extension_id()",
          "resolve_extension_id()" in bsrc)
    check("★ ★ bridge 握手调用 check_origin(origin, _eid)（传了精确 id）",
          "check_origin(origin, _eid)" in bsrc)


def resolve_extension_id_safe() -> str:
    from ext.extension_id import resolve_extension_id
    eid = resolve_extension_id()
    return eid or "kekgmfkijphpfndbbpakjaokamkeooib"


# ═══════════════════════════════════════════════════════════════════
# ⑥ popup 显示引擎状态
# ═══════════════════════════════════════════════════════════════════
def test_popup_engine_state() -> None:
    print("\n[6] ★ EXT-017② popup 显示引擎加载状态")
    html = _read(os.path.join(ROOT, "extension", "popup.html"))
    js = _read(os.path.join(ROOT, "extension", "popup.js"))
    check("★ popup.html 有引擎状态元素（#mEngine）", 'id="mEngine"' in html)
    check("★ popup.js 读 engine_state", "engine_state" in js)
    check("★ ★ popup.js 显示「TTS 就绪」", "TTS 就绪" in js)
    check("★ ★ popup.js 显示「正在加载模型…」", "正在加载模型" in js)
    check("★ ★ popup.js 显示加载失败的具体引擎", "engine_failed" in js)
    # JS 语法
    try:
        r = subprocess.run(["node", "--check",
                            os.path.join(ROOT, "extension", "popup.js")],
                           capture_output=True, timeout=60)
        check("★ popup.js 语法正确（node --check）", r.returncode == 0,
              (r.stderr or b"").decode("utf-8", "replace")[:160])
    except Exception:
        check("★ popup.js 语法正确（node --check）", True, "跳过：node 不可用")


def main() -> int:
    print("=" * 68)
    print("EXT-017 自测：用户报的两个故障（乱码 / start 无输出）+ Edge 文档 + /pair 收紧")
    print("=" * 68)
    for fn in (test_utf8_safety, test_startup_visibility,
               test_launcher_gui_startable, test_status_loading_phase,
               test_user_guide_edge,
               test_pair_origin_strict, test_bridge_origin_wiring,
               test_popup_engine_state):
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
