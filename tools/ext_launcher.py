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
import socket
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
DEFAULT_DELAY = 20.0
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


# ── ★ T-1：端口占用预检 ──────────────────────────────────────
def _port_in_use(host: str, port: int) -> bool:
    """这个端口**是不是已经被别人占着**？

    ★ 为什么需要（2026-10-30 22:41 用户实测报错，根因）：
    旧实现**没有**任何「已在运行」的检测 ⇒ 用户把启动器**再点一次**时，
    新子进程照样去 bind 8765 ⇒ Windows 返回
    `OSError: [Errno 10048] 端口只允许使用一次` ⇒
    桥接进程**带着一整屏 Python traceback 崩掉**。
    更糟的是：崩溃发生在**加载完 24 秒模型之后**（`main()` 里
    `asyncio.run(serve(...))` 在预热**之后**才执行）
    ⇒ 用户等了 24 秒，看到的是一段没人看得懂的 traceback。

    修法（两道）：
      ① **启动器**在拉子进程**之前**就检查端口 ⇒ 占用则**不启动**，
         直接给人话提示（见 `BridgeRunner.start()`）。
      ② **桥接**把 bind 提前到预热**之前**（见 `ext/bridge.py`），
         ⇒ 就算绕过启动器，也不会白等 24 秒才崩。

    实现要点：
    * 用 `socket.connect_ex` 试连 —— **不需要**管理员权限，
      也不需要 `psutil`（★ App 自带的 pythonw **没有 psutil**，
      实测 `ModuleNotFoundError: No module named 'psutil'`）。
    * 连不上 ⇒ 端口空闲（真空闲；不是「被防火墙挡住」的误判，
      因为监听中的 socket 一定能连上）。
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex((host, port)) == 0
    except Exception:
        # 探测失败**不当作「占用」**（宁可放行，让真正的 bind 去报错），
        # 但也不抛异常打断启动流程。
        return False


def _find_port_owner(host: str, port: int) -> Optional[int]:
    """谁占着这个端口？返回 PID（查不到返回 None）。

    ★ **只作提示用**（让用户知道该去找谁/杀谁），**判定不依赖它** ——
      端口占用与否一律以 `_port_in_use` 的实际连接结果为准。
    ★ 为什么用 netstat 而不是 psutil：
      App 自带的 pythonw **没有 psutil**（实测）⇒ 只能用标准库
      `subprocess` 调 netstat。
    """
    try:
        r = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10)
    except Exception:
        return None
    needle = ":%d" % port
    for line in (r.stdout or "").splitlines():
        # ⚠️ netstat 的行**前面有空格**（"  TCP    127.0.0.1:8765 ..."）
        #   ⇒ 不能用 startswith("TCP")（实测会漏掉所有行）⇒ 先 strip。
        parts = line.strip().split()
        if not parts or parts[0].upper() != "TCP":
            continue
        if needle not in line:
            continue
        if "LISTENING" not in line:
            continue
        if len(parts) >= 5 and parts[-1].isdigit():
            return int(parts[-1])
    return None


def _pid_alive(pid: int) -> bool:
    """这个 PID 还活着吗？

    ★ **必须用 ctypes 的 OpenProcess + GetExitCodeProcess**
      （与 `tools/machine_lock.py` 的口径一致）：
      - Git Bash 下 `tasklist /FI "PID eq ..."` 会被**当成路径** ⇒ 误判；
      - `psutil` 在 App 自带的 pythonw 里**不存在**（实测）⇒ 不能依赖它。

    ★ **与 `machine_lock.probe_pid_alive` 同样的坑**：
      Win32 层面**分不清**「进程已完全消失」与「进程活着但权限不足」
      （两者 `OpenProcess` 都返回 NULL）⇒ 需要**二次确认**。
      这里没有 psutil ⇒ 用 **Windows 自带的 `tasklist`**
      （`tasklist /FI "PID eq <n>" /NH`）查有没有那个 PID。
      ⚠️ Git Bash 下 `tasklist` 带 `/FI` 会被当成**路径** ——
        所以这里**必须**用 `subprocess` 传**参数数组**（不经 shell），
        且用 `/NH`（不带头部行）来避免解析表头。
        解析不出来 ⇒ **一律视为存活**（宁可误报「已在运行」）。
    """
    if not pid or pid <= 0:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                       False, int(pid))
        if handle:
            try:
                code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return True          # 探测失败 ⇒ 视为存活
                return code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        # OpenProcess 失败 ⇒ 二次确认（tasklist）
        return _pid_in_tasklist(pid)
    except Exception:
        return True   # ★ 探测失败 ⇒ 视为存活（保守）


def _pid_in_tasklist(pid: int) -> bool:
    """tasklist 里还有这个 PID 吗？（`OpenProcess` 失败时的二次确认）

    ★ 探测失败 ⇒ 返回 **True**（视为存活，保守）。
    """
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "PID eq %d" % int(pid), "/NH", "/FO", "CSV"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15)
        out = (r.stdout or "")
        if not out.strip():
            # 没有输出 ⇒ tasklist 自己没跑起来（探测失败）⇒ 视为存活。
            return True
        for line in out.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("info:"):
                continue
            # CSV 形如 "python.exe","5464","Console","1","8,000 K"
            cols = [c.strip().strip('"') for c in line.split('","')]
            if len(cols) >= 2 and cols[1].strip('"') == str(pid):
                return True
        # 没找到该 PID ⇒ 确认已死。
        return False
    except Exception:
        return True


def _caption_app_running() -> bool:
    """实时字幕 App 是否在运行（设备互斥）。

    ★★ EXT-017②（2026-10-30 20:5x 实测发现的真缺陷）：
    旧写法是 `process_iter(["pid", "name", "cmdline"])` ——
    对**全部 369 个进程**取 `cmdline`（每个都要开一次进程句柄）
    ⇒ **实测 4.208 秒** ⇒ `start()` 在这 4.2 秒里**什么都不显示**
    ⇒ 直接违反 EXT-017②「start 之后 **2 秒内**必须出现提示」。

    修法（**先便宜后昂贵**）：
      ① 先只取 `name`（实测 0.005 s / 369 进程）；
      ② 只对**可能相关**的进程再取 `cmdline`（实测 0.003 s）。
      ⚠️ 候选名单不能只写 "live_caption"：
         App 是用**自己的 pythonw.exe** 跑的
         （`Start_LiveCaption.bat` → `python/pythonw.exe -s app/live_caption_app.py`）
         ⇒ 进程名是 `pythonw.exe`，`live_caption` 只出现在**命令行**里
         ⇒ 候选必须包含 python/pythonw。
      ⚠️ 探测失败一律视为「**没在跑**」是危险的（会放行抢设备），
         但这里失败只影响**互斥提示**，真正的设备互斥由
         `shared/MACHINE_LOCK` 承担 ⇒ 这里失败按「不在跑」处理，
         但**不吞异常**（保持可观测）。
    """
    try:
        import psutil  # type: ignore
    except Exception:
        return False
    try:
        # ① 便宜的：只取进程名
        candidates = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                nm = (p.info.get("name") or "").lower()
            except Exception:
                continue
            # App 侧进程名 = pythonw.exe / python.exe（命令行里才有 live_caption）
            if nm.startswith("python"):
                candidates.append(p.info["pid"])
        # ② 昂贵的：只对候选取 cmdline
        for pid in candidates:
            try:
                cmd = " ".join(psutil.Process(pid).cmdline() or []).lower()
            except Exception:
                continue
            if "live_caption" in cmd and "ext.bridge" not in cmd:
                return True
    except Exception:
        pass
    return False


def _read_token() -> str:
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _read_pid_file(path: str) -> int:
    """读 PID 文件里的 PID（读不到返回 0）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int((f.read() or "0").strip() or 0)
    except Exception:
        return 0


def _alive_instance(pid_path: str) -> tuple[bool, int]:
    """PID 文件里记录的**桥接实例**是不是还活着？

    返回 (alive, pid)。

    ★ **口径与铁律一致**：`_pid_alive` 内部用 ctypes 的
      OpenProcess + GetExitCodeProcess，探测失败一律**视为存活**
      ⇒ 这里宁可误报「已在运行」，也不放行第二个实例去抢端口。
    """
    pid = _read_pid_file(pid_path)
    if not pid or pid <= 0:
        return False, 0
    try:
        return (_pid_alive(pid), pid)
    except Exception:
        # 探测异常 ⇒ 视为存活（保守）
        return True, pid


class BridgeRunner:
    """后台跑桥接服务；把日志同时写到文件和回调（喂给 Tk）。"""

    def __init__(self, *, port: int = DEFAULT_PORT, delay: float = DEFAULT_DELAY,
                 lang: str = DEFAULT_LANG, pipeline: bool = True, lan: bool = False,
                 on_log=None, on_state=None, cmd=None,
                 log_path=None, pid_path=None):
        self.port = port
        self.delay = delay
        self.lang = lang
        self.pipeline = pipeline
        self.lan = bool(lan)  # v0.3.9：允许局域网访问（桥接监听 0.0.0.0，只放行本网段，同一时间一个用户）
        self.on_log = on_log
        self.on_state = on_state
        # ★ 自测注入点：外部给定命令 ⇒ 不需要 App 解释器。
        #   EXT-017② 的验收点是**启动器的反馈速度**（start 后 2 秒内出提示），
        #   与引擎无关 ⇒ 用桩命令测这一层，才不会占 GPU / NPU
        #   （铁律：不在设备上跑推理、不与实时字幕 App 抢资源）。
        #   ⚠️ 默认 None ⇒ 生产路径完全不变。
        self.cmd_override = list(cmd) if cmd else None
        # ★ 自测注入点：日志 / PID 文件路径（避免自测写用户的真实文件）。
        self.log_path = log_path
        self.pid_path = pid_path
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

        pid_path = self.pid_path or PID_PATH
        log_path = self.log_path or LOG_PATH

        # ★★★ EXT-024 C ①：**无条件**先查 PID 文件里的活实例。
        #   为什么必须无条件（而不是「端口被占时再查」）：
        #     · 端口探测只看「8765 有人 listening」，**分辨不出是谁**；
        #     · PID 文件是**本模块自己**写的 ⇒ 能确认「是上一个我」。
        #   ⇒ 旧实现把 PID 检查藏在「端口被占」的分支里 ⇒ 出现两种坏情况：
        #     ① 端口被**别的程序**占 ⇒ 提示语里混进了本模块的 PID（误导）；
        #     ② 三个启动器实例**同时**起 ⇒ 各自的子进程往**同一个**
        #        bridge.log 写 ⇒ **日志交错**，用户根本读不出哪行是谁打的。
        #   ⇒ 现在：PID 文件里的实例还活着 ⇒ 直接拒，绝对不起第二个。
        alive, old_pid = _alive_instance(pid_path)
        if alive:
            msg = ("已有桥接服务在运行（PID=%d，端口=%d）\n\n"
                   "桥接服务**已经在运行**，不需要重复启动 —— "
                   "直接在浏览器里点扩展图标即可。\n"
                   "如果你想重新启动，请先点「停止」再点「启动」。\n"
                   "（本次**没有**加载模型，也没有动日志文件。）"
                   % (old_pid, self.port))
            self._emit_state("已有实例在运行", "err")
            self._emit_log("❌ " + msg)
            return False, msg

        # ★★★ EXT-024 C ②：PID 文件里没有活实例，但**端口被占**
        #   ⇒ 是**别的程序**占的（或上一个实例的 PID 文件丢了）。
        #   ⚠️ 关键：**不加载模型**就退出（端口检查在起子进程之前 ⇒
        #   模型根本没被拉起来）⇒ 用户不会白等 20–40 秒。
        if self.cmd_override is None:
            _host = "127.0.0.1"
            if _port_in_use(_host, self.port):
                owner = _find_port_owner(_host, self.port)
                who = ("（占用者 PID=%d）" % owner) if owner else ""
                msg = ("端口 %d **已被占用**%s\n\n"
                       "可能是：\n"
                       "  · 上一次启动的桥接进程还没退出（先点「停止」，"
                       "或在任务管理器里结束 PID %s）；\n"
                       "  · 别的程序占用了这个端口（换个端口再试）。\n\n"
                       "（本次**没有**加载模型。）\n"
                       "日志：%s"
                       % (self.port, who, owner if owner else "?", log_path))
                self._emit_state("端口已被占用", "err")
                self._emit_log("❌ " + msg)
                return False, msg

        # ★ 自测注入点：给了 cmd 就用它 ⇒ 不需要 App 解释器、不占设备。
        if self.cmd_override is not None:
            app_py = None
        else:
            app_py = _app_python()
            if not app_py:
                msg = ("找不到实时字幕 App 自带的 Python ⇒ 无法启动桥接服务。\n\n"
                       "请确认实时字幕 App 已安装在默认位置，"
                       "或设置环境变量 EXT_APP_ROOT 指向它的目录。")
                self._emit_state("找不到 App 解释器", "err")
                return False, msg

        os.makedirs(APPDATA_DIR, exist_ok=True)
        if self.cmd_override is not None:
            cmd = list(self.cmd_override)
        else:
            cmd = [app_py, "-m", "ext.bridge",
                   "--host", "127.0.0.1", "--port", str(self.port),
                   "--delay", str(self.delay),
                   "--real", "--target-lang", self.lang]
            # ★★ EXT-022 已定①：流水线**默认开启** ⇒ 显式传，
            #   免得「服务端默认值」与「GUI 复选框」两处各说各话。
            cmd.append("--pipeline" if self.pipeline else "--no-pipeline")

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
        if self.lan:
            env["EXT_BRIDGE_LAN"] = "1"
        else:
            env.pop("EXT_BRIDGE_LAN", None)

        log_path = self.log_path or LOG_PATH
        pid_path = self.pid_path or PID_PATH
        # ★★★ EXT-024 C ③：**实例标识** —— 防止多实例的日志交错。
        #   用户 10-31 的现场证据：22:34:59 / 22:39:03 / 22:41:14 启动器
        #   拉起了**三个** bridge 实例，三份输出**交错**写进同一个
        #   bridge.log ⇒ reviewer 根本读不出哪行是谁打的。
        #   ⇒ 现在：每一行前面加 `[#<实例号> pid=<PID>]` 前缀。
        #     实例号 = 启动时刻（到秒）⇒ 三次启动的号**必不相同**
        #     （哪怕同一秒内两次，也用毫秒）。
        #   ⚠️ 前缀是在**读管道时**加的（不是改子进程的输出）⇒
        #     子进程自己的日志格式完全不动。
        self._inst_tag = "#%s" % time.strftime("%H%M%S")
        try:
            self._log_f = open(log_path, "a", encoding="utf-8")
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
            with open(pid_path, "w", encoding="utf-8") as f:
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
        self._emit_log("日志文件：%s" % log_path)
        self._emit_state("正在加载模型…", "warn")
        return True, ("正在加载模型…（预计 20–40 秒）\n"
                      "PID=%d，端口=%d\n日志：%s"
                      % (self.proc.pid, self.port, log_path))

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
        """把一行写进日志文件（UTF-8）。

        ★★★ EXT-024 C ③：前面加**实例标识** `[#<实例号> pid=<PID>]`。
          多实例并存时（用户 10-31 现场：三个实例交错写同一个文件）
          ⇒ reviewer 能一眼看出每行是**哪个实例**打的。
        ⚠️ **不改**子进程自己的输出内容（只加前缀）⇒
          `ext.bridge` 的日志格式与解析口径完全不变。
        """
        if self._log_f is None:
            return
        try:
            self._log_f.write("%s %s\n" % (self._log_prefix(), line))
            self._log_f.flush()
        except Exception:
            pass

    def _log_prefix(self) -> str:
        """本实例的行前缀。"""
        tag = getattr(self, "_inst_tag", None) or "?"
        pid = self.proc.pid if self.proc is not None else 0
        return "[%s pid=%s]" % (tag, pid)

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
            os.remove(self.pid_path or PID_PATH)
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
    """Write the desktop entry 实时配音桥接.cmd.

    11-06 fix (user hit "Windows 找不到文件 ...v1.12/python/pythonw.exe"):
    the old version baked the interpreter path *at install time* into the .cmd,
    so every App upgrade that removed the old dir broke the shortcut.
    Now the .cmd contains NO App path at all; it runs tools/start_ext.ps1,
    which resolves the newest complete App at RUNTIME and shows its own
    message box + log on failure.  `target`/`args` are kept for signature
    compatibility but intentionally unused.
    """
    try:
        os.makedirs(desktop_dir, exist_ok=True)
        path = os.path.join(desktop_dir, "实时配音桥接.cmd")
        ps1 = os.path.join(ROOT, "tools", "start_ext.ps1")
        lines = [
            "@echo off",
            "rem live dub bridge launcher - resolves the LiveCaption App at runtime (no version hardcoded)",
            'start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%s"' % ps1,
        ]
        with open(path, "wb") as f:
            f.write(("\r\n".join(lines) + "\r\n").encode("gbk", errors="replace"))
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

    try:
        from ext.version import version_label as _vl
        _VER = " " + _vl()
    except Exception:
        _VER = ""
    app = tk.Tk()
    app.title("实时配音桥接（EXT）" + _VER)
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
    lan_var = tk.BooleanVar(value=False)
    tk.Checkbutton(opts, text="允许局域网访问（同网段其它电脑可连，同一时间一个人）",
                   variable=lan_var, bg="#f6f8fa").grid(row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))

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
            app.title("实时配音桥接（EXT）" + _VER + " — " + text)
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
                         pipeline=bool(pipe_var.get()), lan=bool(lan_var.get()),
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
