"""ext_launcher.py — ★ EXT-012：面向用户的「一键启动」桥接服务启动器

## 目标（EXT-012 明文）

> ② 一键启动：桌面快捷方式"实时配音桥接"（pythonw，**默认 --real --pipeline**，
>    启用线程限制，日志写到 %LOCALAPPDATA%），启动后在托盘或小窗口显示状态；
>    和实时字幕 App 互斥时给出明确提示。

## 设计

* **一个进程，两个角色**：
  * 后台线程跑真正的桥接服务（`ext.bridge`，用 **App 自带解释器**启动）；
  * 前台是 Tk 小窗口（状态灯 + 日志尾部 + 停止按钮）。
  * ⇒ 用户**双击桌面快捷方式**就能用，不需要开终端。
* **pythonw**（无控制台窗口）⇒ 脚本里不能有 `print` 到 stdout 的依赖，
  所有日志走**文件** + Tk 文本框。
* **日志位置**：`%LOCALAPPDATA%\\LiveDubEXT\\bridge.log`（EXT-012 明文要求）。
* **互斥**：桥接服务自己会拒绝启动（`ext.bridge` 的 `_caption_app_running`），
  本启动器**额外**先探测并给出**人话提示**（而不是让用户看一个失败的窗口）。

## ⚠️ 铁律

* 本脚本**不跑推理**（真正的推理在桥接服务进程里）；
* 本脚本**不创建共享锁**（计时/测速才需要锁；用户日常使用不是计时作业）；
  ⇒ 桥接服务与实时字幕 App 的**设备互斥**由 `ext.bridge` 自己把关。
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

# ★★ EXT-017①：启动器自身也必须 UTF-8 安全。
#   本机中文 Windows 控制台代码页 = gb2312 ⇒ Python 的 stdout 是 GBK
#   ⇒ 启动器里任何中文/符号输出都可能抛 UnicodeEncodeError。
#   ⇒ 立刻把本进程切到 UTF-8 模式（PEP 540：PYTHONUTF8=1 让
#      **整个解释器**用 UTF-8，包括 stdout/stderr 与文件系统编码）。
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from ext.utf8_io import configure_process_env, safe_print  # noqa: E402

# ── 运行时目录（%LOCALAPPDATA%） ──────────────────────────────────
APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA",
                                         os.path.expanduser("~")),
                            "LiveDubEXT")
LOG_PATH = os.path.join(APPDATA_DIR, "bridge.log")
PID_PATH = os.path.join(APPDATA_DIR, "bridge.pid")
TOKEN_PATH = os.path.join(ROOT, "bridge_token.txt")

# ── 默认参数（EXT-012 明文：默认 --real --pipeline + 线程限制） ──────
DEFAULT_PORT = 8765
DEFAULT_DELAY = 10.0
DEFAULT_LANG = "zh"


def _app_python() -> Optional[str]:
    """桥接服务必须用 **App 自带解释器**（openvino / babelvox 只在那里）。"""
    try:
        from ext.app_root import resolve_app_root
        app_root = resolve_app_root()
    except Exception:
        app_root = None
    if not app_root:
        return None
    p = os.path.join(app_root, "python", "python.exe")
    return p if os.path.isfile(p) else None


def _app_pythonw() -> Optional[str]:
    """★ EXT-017②：App 自带的 **pythonw**（无控制台但带 tkinter）。

    启动器的 GUI 用它最合适：既不弹黑框，又一定有 tkinter。
    """
    try:
        from ext.app_root import resolve_app_root
        app_root = resolve_app_root()
    except Exception:
        app_root = None
    if not app_root:
        return None
    p = os.path.join(app_root, "python", "pythonw.exe")
    return p if os.path.isfile(p) else None


def _has_tkinter(exe: Optional[str]) -> bool:
    """★ EXT-017②：这个解释器**能不能跑 tkinter GUI**？

    实测法：用 `-c "import tkinter"` 试一次 ⇒ 比查目录可靠
    （有些发行版把 tkinter 拆成单独的包）。
    """
    if not exe or not os.path.isfile(exe):
        return False
    try:
        r = subprocess.run([exe, "-c", "import tkinter"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def _caption_app_running() -> bool:
    """实时字幕 App 是否在运行（设备互斥）。"""
    try:
        import psutil  # type: ignore
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(p.info.get("cmdline") or [])
                low = cmd.lower()
                if "live_caption" in low and "ext.bridge" not in low:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _read_token() -> str:
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


class BridgeRunner:
    """后台跑桥接服务；把日志同时写到文件和回调（喂给 Tk）。"""

    def __init__(self, *, port: int = DEFAULT_PORT, delay: float = DEFAULT_DELAY,
                 lang: str = DEFAULT_LANG, pipeline: bool = True,
                 on_log=None, on_state=None):
        self.port = port
        self.delay = delay
        self.lang = lang
        self.pipeline = pipeline
        self.on_log = on_log
        self.on_state = on_state
        self.proc: Optional[subprocess.Popen] = None
        self._log_f = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ── 生命周期 ────────────────────────────────────────────────
    def start(self) -> tuple[bool, str]:
        """启动桥接服务。返回 (ok, message)。"""
        if _caption_app_running():
            msg = ("检测到「实时字幕 App」正在运行 ⇒ 已拒绝启动。\n\n"
                   "两者会抢同一块 GPU / NPU，必须**二选一**：\n"
                   "  · 先关掉实时字幕 App，再点本窗口的「启动」；\n"
                   "  · 或者关掉本窗口，直接用实时字幕 App。")
            self._emit_state("互斥冲突", "err")
            return False, msg

        app_py = _app_python()
        if not app_py:
            msg = ("找不到实时字幕 App 自带的 Python ⇒ 无法启动桥接服务。\n\n"
                   "请确认实时字幕 App 已安装在默认位置，"
                   "或设置环境变量 EXT_APP_ROOT 指向它的目录。")
            self._emit_state("找不到 App 解释器", "err")
            return False, msg

        os.makedirs(APPDATA_DIR, exist_ok=True)
        cmd = [app_py, "-m", "ext.bridge",
               "--host", "127.0.0.1", "--port", str(self.port),
               "--delay", str(self.delay),
               "--real", "--target-lang", self.lang]
        if self.pipeline:
            cmd.append("--pipeline")

        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [ROOT, os.path.join(ROOT, ".runtime_deps")] +
            ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        # ★★ EXT-017①：统一 UTF-8（**必须在解释器启动前**设，事后改无效）。
        #   本机中文 Windows 控制台代码页实测 = gb2312，
        #   而日志里有 `🔴` / `⇒` / `⛔` 这些 GBK 编不了的符号
        #   ⇒ 不设这两个变量时，写日志会抛 UnicodeEncodeError
        #   ⇒ 用户看到的正是「乱码」/ 日志中断。
        configure_process_env(env)
        # ★ EXT-011：线程限制（必须在 numpy/openvino import 之前 —— 由
        #   ext.bridge 自己在 import 前设；这里只确保**不被外部环境关掉**）。
        env.pop("EXT_THREAD_LIMIT", None)

        try:
            self._log_f = open(LOG_PATH, "a", encoding="utf-8")
            # ★★ EXT-017②：用**管道**把子进程 stdout/stderr 接出来，
            #   由后台线程逐行读 ⇒ 同时喂给「窗口」和「日志文件」。
            #   ⚠️ 旧写法是 `stdout=self._log_f`（直接重定向到文件）
            #      ⇒ 子进程的输出**只在文件里**，窗口永远看不到
            #      ⇒ 这正是用户报的「start 之后没有任何输出」。
            #   ⚠️ 必须用 `encoding="utf-8", errors="replace"`：
            #      子进程可能输出 GBK 编不了的字符 ⇒ 读端必须容错，
            #      否则**读线程一崩，整条日志就断了**。
            self.proc = subprocess.Popen(
                cmd, cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                bufsize=1,
                text=True, encoding="utf-8", errors="replace",
                creationflags=(subprocess.CREATE_NO_WINDOW
                               if os.name == "nt" else 0))
        except Exception as e:
            self._emit_state("启动失败", "err")
            return False, "启动桥接服务失败：%s" % e

        try:
            with open(PID_PATH, "w", encoding="utf-8") as f:
                f.write(str(self.proc.pid))
        except Exception:
            pass

        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()
        # ★★ EXT-017②：start 之后**立刻**给出可见反馈 ——
        #   明确告诉用户「正在加载模型」，并给出 PID / 端口 / 日志路径。
        self._emit_log("桥接服务已启动：PID=%d，端口=%d，配对端口=%d"
                       % (self.proc.pid, self.port, self.port + 1))
        self._emit_log("正在加载模型…（预计 20–40 秒，请稍候）")
        self._emit_log("日志文件：%s" % LOG_PATH)
        self._emit_state("正在加载模型…", "warn")
        return True, ("正在加载模型…（预计 20–40 秒）\n"
                      "PID=%d，端口=%d\n日志：%s"
                      % (self.proc.pid, self.port, LOG_PATH))

    def _pump(self) -> None:
        """把子进程输出**逐行**读出来（同时喂给窗口与日志文件）。

        ★ EXT-017②：现在子进程的 stdout 走**管道**，这里直接读管道
          ⇒ 窗口里**立刻**能看到「正在加载模型…」等进度。
          （旧实现把 stdout 重定向到日志文件、再轮询文件尾部
            ⇒ 窗口里什么都没有，只有文件里有。）
        """
        if self.proc is None:
            return
        stream = self.proc.stdout
        if stream is None:
            return
        try:
            for raw in iter(stream.readline, ""):
                if raw == "":
                    break
                line = raw.rstrip("\r\n")
                if not line.strip():
                    continue
                self._write_log_file(line)
                self._emit_log(line)
        except Exception:
            # ★ 读管道失败**不能**让启动器崩（用户还得点「停止」）。
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _write_log_file(self, line: str) -> None:
        """把一行写进日志文件（UTF-8）。"""
        if self._log_f is None:
            return
        try:
            self._log_f.write(line + "\n")
            self._log_f.flush()
        except Exception:
            pass

    def stop(self) -> None:
        self._stop.set()
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=10)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self._emit_state("已停止", "warn")
        try:
            if self._log_f:
                self._log_f.close()
        except Exception:
            pass
        try:
            os.remove(PID_PATH)
        except Exception:
            pass

    # ── 回调 ────────────────────────────────────────────────────
    def _emit_log(self, line: str) -> None:
        if self.on_log:
            try:
                self.on_log(line)
            except Exception:
                pass

    def _emit_state(self, text: str, kind: str) -> None:
        if self.on_state:
            try:
                self.on_state(text, kind)
            except Exception:
                pass


def _make_shortcut(desktop_dir: str, target: str, args: str,
                   description: str) -> Optional[str]:
    """在桌面创建 .lnk 快捷方式。

    ⛔ 不依赖 pywin32（本机**没装**）⇒ 用 Windows 自带的
       `IShellLink` COM 太重 ⇒ 改用**最朴素、零依赖**的做法：
       生成一个 `.cmd` 启动器 + 一个 `.url` 风格的桌面快捷方式不靠 COM 很难，
       ⇒ 采用 **Windows Script Host (.vbs)** 生成 .lnk —— 不行，同样依赖 COM。

    ⇒ **最终方案**：直接写一个 `.cmd` 文件到桌面，双击即可运行。
       Windows 会给 `.cmd` 正常显示图标与名称，用户体验等价于快捷方式，
       且**零依赖**、**不装 pywin32**、**不写注册表**。

    ★★ EXT-017①（乱码修复）：`.cmd` 文件本身也有两个坑：
      1. **文件编码**：`.cmd` 默认按 **OEM 代码页（936/GBK）**解读，
         UTF-8 存的中文注释会显示成乱码 ⇒ 本函数**按 GBK 写**，
         保证在中文 Windows 上 `rem` 注释与 `echo` 提示都能正常显示。
      2. **控制台代码页**：`.cmd` 继承的 cmd.exe 默认代码页是 936 ⇒
         后续 Python 输出若按 UTF-8 写就会显示成乱码 ⇒ **先 `chcp 65001`**。
         （`chcp 65001 >nul` 里的 `>nul` 用来吞掉 chcp 自己的输出。）
    """
    try:
        os.makedirs(desktop_dir, exist_ok=True)
        path = os.path.join(desktop_dir, "实时配音桥接.cmd")
        # ★ 按 **GBK（cp936）** 写：.cmd 默认按 OEM 代码页解读，
        #   UTF-8 内容会变乱码。GBK 是中文 Windows 的原生代码页。
        lines = [
            "@echo off",
            "rem %s" % description,
            "rem ==== EXT-017①：切控制台到 UTF-8，避免中文/符号乱码 ====",
            "chcp 65001 >nul",
            "set PYTHONUTF8=1",
            "set PYTHONIOENCODING=utf-8",
            "start \"\" \"%s\" %s" % (target, args),
        ]
        text = "\r\n".join(lines) + "\r\n"
        with open(path, "wb") as f:
            f.write(text.encode("gbk", errors="replace"))
        return path
    except Exception:
        return None


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # ── 非 GUI 模式：给「安装桌面快捷方式」用 ──
    if "--install-shortcut" in argv:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        # 用 pythonw 启动（无控制台窗口）
        pyw = sys.executable
        cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.isfile(cand):
            pyw = cand
        # ★★ EXT-017②：快捷方式必须指向**带 tkinter** 的解释器！
        #   否则双击后 GUI 起不来；又因为是 pythonw（无控制台），
        #   报错被吞掉 ⇒ 用户看到的是「双击了，什么都没发生」。
        #   实测：WorkBuddy 默认环境的 pythonw **没有 tkinter**；
        #   而实时字幕 App 自带的 pythonw **有 tkinter** ⇒ 优先用它。
        if not _has_tkinter(pyw):
            app_pyw = _app_pythonw()
            if app_pyw and _has_tkinter(app_pyw):
                pyw = app_pyw
        p = _make_shortcut(desktop, pyw,
                           '"%s"' % os.path.abspath(__file__),
                           "实时翻译配音 —— 桥接服务（EXT-012）")
        if p:
            safe_print("已创建桌面快捷方式：%s" % p)
            safe_print("启动解释器：%s（tkinter=%s）"
                       % (pyw, "有" if _has_tkinter(pyw) else "无"))
            return 0
        safe_print("创建桌面快捷方式失败", stream=sys.stderr)
        return 1

    # ── GUI 模式 ────────────────────────────────────────────────
    try:
        import tkinter as tk
        from tkinter import scrolledtext
        # ★★ EXT-017②：`Combobox` 在 **ttk** 里，不在 `tkinter` 顶层！
        #   旧代码写 `tk.Combobox(...)` ⇒ AttributeError ⇒ GUI **直接崩**
        #   ⇒ 用 pythonw 启动时崩溃信息被吞 ⇒ 用户看到「双击了，没反应」。
        #   ⇒ 必须 import ttk 并用 `ttk.Combobox`。
        from tkinter import ttk
    except Exception as e:
        # ★★ EXT-017②：**绝不静默**。
        #   用 pythonw 启动时没有控制台 ⇒ stderr 里的提示**用户看不到**
        #   ⇒ 双击桌面快捷方式后「什么都没有」＝ 用户报告的第二个症状。
        #   ⇒ 这里把原因写进日志文件 + 弹一个系统对话框（MessageBox），
        #      保证**用户一定能看到**出了什么事。
        msg = ("需要 tkinter（GUI）：%s" % e)
        try:
            os.makedirs(APPDATA_DIR, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write("[%s] 启动器无法启动：%s\n"
                        % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
                f.write("    原因：当前解释器 %s 不带 tkinter。\n"
                        "    解决办法：改用实时字幕 App 自带的 Python 启动本脚本，\n"
                        "    或安装 tkinter（pip install tk）。\n" % sys.executable)
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "启动器无法启动：\n\n%s\n\n"
                "（原因：当前解释器没有 tkinter）\n"
                "解决办法：改用实时字幕 App 自带的 Python 启动，\n"
                "或执行 pip install tk。\n\n日志：%s" % (msg, LOG_PATH),
                "实时配音桥接", 0x10)
        except Exception:
            pass
        safe_print(msg, stream=sys.stderr)
        return 2

    os.makedirs(APPDATA_DIR, exist_ok=True)

    app = tk.Tk()
    app.title("实时配音桥接（EXT）")
    app.geometry("620x460")
    app.configure(bg="#f6f8fa")

    state_var = tk.StringVar(value="未启动")
    detail_var = tk.StringVar(value="")

    tk.Label(app, text="实时翻译配音 · 桥接服务", font=("Microsoft YaHei", 14, "bold"),
             bg="#f6f8fa").pack(pady=(12, 2))
    tk.Label(app, textvariable=state_var, font=("Microsoft YaHei", 11),
             bg="#f6f8fa", fg="#1a7f37").pack()
    tk.Label(app, textvariable=detail_var, font=("Microsoft YaHei", 9),
             bg="#f6f8fa", fg="#57606a", wraplength=580).pack(pady=(2, 8))

    # 参数区
    opts = tk.Frame(app, bg="#f6f8fa")
    opts.pack(fill="x", padx=16)
    lang_var = tk.StringVar(value=DEFAULT_LANG)
    delay_var = tk.StringVar(value=str(DEFAULT_DELAY))
    tk.Label(opts, text="目标语言", bg="#f6f8fa").grid(row=0, column=0, sticky="w")
    cb_lang = ttk.Combobox(opts, textvariable=lang_var, width=8, state="readonly",
                           values=["zh", "en", "ja", "ko"])
    cb_lang.grid(row=0, column=1, padx=4)
    tk.Label(opts, text="延迟 D(秒)", bg="#f6f8fa").grid(row=0, column=2, sticky="w", padx=(12, 0))
    tk.Entry(opts, textvariable=delay_var, width=6).grid(row=0, column=3, padx=4)
    tk.Label(opts, text="流水线", bg="#f6f8fa").grid(row=0, column=4, sticky="w", padx=(12, 0))
    pipe_var = tk.BooleanVar(value=True)
    tk.Checkbutton(opts, text="启用（推荐）", variable=pipe_var, bg="#f6f8fa").grid(
        row=0, column=5, sticky="w")

    # 日志区
    log_box = scrolledtext.ScrolledText(app, height=16, font=("Consolas", 9))
    log_box.pack(fill="both", expand=True, padx=16, pady=10)

    buttons = tk.Frame(app, bg="#f6f8fa")
    buttons.pack(fill="x", padx=16, pady=(0, 12))
    runner_box = {}

    def append_log(line: str) -> None:
        try:
            log_box.insert("end", line + "\n")
            log_box.see("end")
        except Exception:
            pass

    def set_state(text: str, kind: str) -> None:
        color = {"ok": "#1a7f37", "err": "#cf222e", "warn": "#9a6700"}.get(kind, "#1f2328")
        try:
            state_var.set(text)
            app.title("实时配音桥接（EXT） — " + text)
            for w in app.winfo_children():
                pass
            lbl = app.winfo_children()[1]
            lbl.configure(fg=color)
        except Exception:
            pass

    # ★★ EXT-017②：轮询配对端点的 /status ⇒ 把「引擎加载状态」显示出来。
    #   用户要能在窗口上直接看到「正在加载模型…」→「TTS 就绪」，
    #   而不用去翻日志文件。
    def poll_engine_state() -> None:
        r = runner_box.get("r")
        if r is None or r.proc is None or r.proc.poll() is not None:
            return
        try:
            import json as _json
            import urllib.request as _req
            with _req.urlopen("http://127.0.0.1:%d/status" % (r.port + 1),
                              timeout=1.5) as resp:
                body = _json.loads(resp.read().decode("utf-8", "replace"))
            st = body.get("status") or {}
            state = st.get("engine_state") or "unknown"
            if state == "ready":
                set_state("TTS 就绪", "ok")
                detail_var.set("三个引擎都已加载，可以开始配音了。")
            elif state == "partial":
                failed = st.get("engine_failed") or {}
                set_state("引擎未就绪", "err")
                detail_var.set("部分引擎加载失败：%s\n日志：%s"
                               % (failed, LOG_PATH))
            elif state == "loading":
                loaded = st.get("engine_loaded") or []
                set_state("正在加载模型…", "warn")
                detail_var.set("正在加载模型…（预计 20–40 秒）\n"
                               "已就绪：%s" % (", ".join(loaded) if loaded else "无"))
        except Exception:
            # 轮询失败**不打扰**用户（桥接可能还没起来）。
            pass
        finally:
            # ★★ EXT-017②：**必须自我续期**。
            #   旧代码只在 on_start 里 `app.after(1000, poll_engine_state)`
            #   调度了**一次** ⇒ 轮询查一次就停 ⇒ 状态灯永远停在
            #   「正在加载模型…」，即使 /status 早已返回 ready。
            #   ⇒ 每轮结束时重新调度自己，直到桥接进程退出。
            try:
                if r is not None and r.proc is not None \
                        and r.proc.poll() is None:
                    app.after(1000, poll_engine_state)
            except Exception:
                pass

    def on_start():
        try:
            delay = float(delay_var.get())
        except Exception:
            delay = DEFAULT_DELAY
        r = BridgeRunner(port=DEFAULT_PORT, delay=delay, lang=lang_var.get(),
                         pipeline=bool(pipe_var.get()),
                         on_log=append_log, on_state=set_state)
        runner_box["r"] = r
        ok, msg = r.start()
        detail_var.set(msg)
        append_log("── " + msg)
        if ok:
            # 每秒轮询一次引擎状态（加载可能要 20–40 秒）。
            app.after(1000, poll_engine_state)

    def on_stop():
        r = runner_box.get("r")
        if r:
            r.stop()
        detail_var.set("已停止")

    b_start = tk.Button(buttons, text="启动", command=on_start, width=12)
    b_start.pack(side="left")
    b_stop = tk.Button(buttons, text="停止", command=on_stop, width=12)
    b_stop.pack(side="left", padx=8)

    tk.Label(app, text="配对 token 由桥接服务自动生成，插件会自动读取，无需手动复制。\n"
                       "在 Chrome 里加载 live_dub_ext\\extension 后，点插件图标即可开始。",
             bg="#f6f8fa", fg="#57606a", font=("Microsoft YaHei", 9),
             justify="left", anchor="w").pack(fill="x", padx=16, pady=(0, 10))

    app.mainloop()
    return 0


if __name__ == "__main__":
    # ★★ EXT-017②：**顶层异常兜底** —— 用 pythonw 启动时没有控制台，
    #   未捕获异常会被**完全吞掉**（用户只看到「双击了，没反应」）。
    #   ⇒ 这里把异常写进日志文件 + 弹 MessageBox，绝不静默退出。
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as _e:  # noqa: BLE001
        import traceback as _tb
        _tb_text = _tb.format_exc()
        try:
            os.makedirs(APPDATA_DIR, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write("[%s] 启动器崩溃：%s\n%s\n"
                        % (time.strftime("%Y-%m-%d %H:%M:%S"),
                           type(_e).__name__, _tb_text))
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "启动器崩溃：\n\n%s: %s\n\n日志：%s"
                % (type(_e).__name__, _e, LOG_PATH),
                "实时配音桥接", 0x10)
        except Exception:
            pass
        raise
