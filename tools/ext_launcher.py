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
        env["PYTHONIOENCODING"] = "utf-8"
        # ★ EXT-011：线程限制（必须在 numpy/openvino import 之前 —— 由
        #   ext.bridge 自己在 import 前设；这里只确保**不被外部环境关掉**）。
        env.pop("EXT_THREAD_LIMIT", None)

        try:
            self._log_f = open(LOG_PATH, "a", encoding="utf-8")
            self.proc = subprocess.Popen(
                cmd, cwd=ROOT, stdout=self._log_f,
                stderr=subprocess.STDOUT, env=env,
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
        self._emit_state("启动中…", "warn")
        return True, "正在启动桥接服务（日志：%s）" % LOG_PATH

    def _pump(self) -> None:
        """把子进程输出**逐行**读出来（转发到日志文件 + UI）。"""
        if self.proc is None or self._log_f is None:
            return
        # 子进程的 stdout 已经重定向到日志文件了；这里改为**旁路**读取
        # ⇒ 不能再从管道读（会互相抢）。改为**轮询日志文件尾部**。
        pos = 0
        while not self._stop.is_set() and self.proc.poll() is None:
            try:
                with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    if chunk:
                        pos = f.tell()
                        for line in chunk.splitlines():
                            if line.strip():
                                self._emit_log(line)
            except Exception:
                pass
            time.sleep(0.6)
        # 最后再读一次尾巴
        try:
            with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                chunk = f.read()
                for line in chunk.splitlines():
                    if line.strip():
                        self._emit_log(line)
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
    """
    try:
        os.makedirs(desktop_dir, exist_ok=True)
        path = os.path.join(desktop_dir, "实时配音桥接.cmd")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("@echo off\r\n")
            f.write("rem %s\r\n" % description)
            f.write('start "" "%s" %s\r\n' % (target, args))
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
        p = _make_shortcut(desktop, pyw,
                           '"%s"' % os.path.abspath(__file__),
                           "实时翻译配音 —— 桥接服务（EXT-012）")
        if p:
            print("已创建桌面快捷方式：%s" % p)
            return 0
        print("创建桌面快捷方式失败", file=sys.stderr)
        return 1

    # ── GUI 模式 ────────────────────────────────────────────────
    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except Exception as e:
        print("需要 tkinter（GUI）：%s" % e, file=sys.stderr)
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
    cb_lang = tk.Combobox(opts, textvariable=lang_var, width=8, state="readonly",
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
    raise SystemExit(main())
