"""utf8_io.py — ★ EXT-017①：中文 Windows 控制台**乱码**的根治

## 用户原话（EXT-017）

> 实时配音桥接运行报错：1，乱码；2，start 命令后无任何输出。

## 根因（★ 本轮实测，不是推测）

本机中文 Windows 的控制台代码页实测是 **gb2312**（`ConsoleOutputCP=gb2312`），
而 Python 3.7+ 在**中文 Windows**上默认把 stdout/stderr 的编码设成
**GBK（cp936）**（PEP 528 之前的遗留行为）。

⇒ 于是本项目日志里大量使用的符号会直接**抛异常**：

| 字符 | 在 GBK 下 | 实测结果 |
|---|---|---|
| `⇒` | U+21D2 | `UnicodeEncodeError` |
| `🔴` | U+1F534 | `UnicodeEncodeError` |
| `⛔` | U+26D4 | `UnicodeEncodeError` |
| `★` | U+2605 | ✅ 能编码（GBK 里有） |
| 中文 | — | ✅ 能编码 |

★ **关键**：抛的是 `UnicodeEncodeError`，不是「显示成问号」。
   ⇒ 一条日志写不出去 ⇒ `print()` 抛异常 ⇒ **整个进程崩掉**，
   或者（更糟）日志**中断在那一行**，用户看到的就是「日志到一半没了」。

## 本模块的处置（三层，全都要）

1. **环境变量层**（`PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`）：
   让 Python 整个进程用 UTF-8 —— 但这要求**在解释器启动前**就设好，
   ⇒ 由启动器（`tools/ext_launcher.py`）和 `.cmd` 负责。
2. **运行时兜底层**（本模块）：
   即使环境变量没生效（例如用户自己在 cmd 里跑），也不能因为一条日志崩掉。
   ⇒ `safe_print()` 把不可编码的字符**降级替换**，绝不抛异常。
3. **控制台层**（`chcp 65001`）：
   让 Windows 控制台本身切到 UTF-8 —— 由 `.cmd` 负责。

## 铁律

* 本模块**不依赖任何第三方库**（只用标准库 `os` / `sys`）；
* `safe_print()` **绝不抛异常**（这是它存在的全部意义）；
* 不改任何其他模块的文件。
"""
from __future__ import annotations

import os
import sys
from typing import Optional

#: 会被 GBK 拒绝、必须替换的字符的替代物。
#: 用 ASCII 兜底 ⇒ 任何代码页都能显示。
_REPLACEMENT = "?"


def _sanitize(text: str, encoding: Optional[str] = None) -> str:
    """把 `text` 里**当前 stdout 编码无法表示**的字符替换掉。

    参数
    ----
    text
        原始文本。
    encoding
        目标编码；``None`` ⇒ 用当前 stdout 的编码（取不到则 utf-8）。

    返回
    ----
    str
        **保证可以被目标编码表示**的文本（不会抛异常）。
    """
    if not isinstance(text, str):
        text = str(text)
    if not encoding:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return text
    except (UnicodeEncodeError, LookupError):
        pass
    # 逐字符过滤：保留能编码的，替换不能编码的。
    out = []
    for ch in text:
        try:
            ch.encode(encoding)
            out.append(ch)
        except (UnicodeEncodeError, LookupError):
            out.append(_REPLACEMENT)
    return "".join(out)


def safe_print(msg: str = "", *, stream=None, encoding: Optional[str] = None,
               **kwargs) -> bool:
    """打印一行，**绝不因编码问题抛异常**。

    ★ 与 `print()` 的区别：
      * `print("🔴 失败")` 在 GBK 控制台上 ⇒ **UnicodeEncodeError（进程崩）**；
      * `safe_print("🔴 失败")` ⇒ 输出 `? 失败`，**进程继续跑**。

    Returns
    -------
    bool
        是否**真的写出去**了（`False` ⇒ 连兜底都失败，例如流已关闭）。
    """
    st = stream if stream is not None else sys.stdout
    enc = encoding or getattr(st, "encoding", None) or "utf-8"
    text = _sanitize(str(msg), enc)
    try:
        st.write(text + "\n")
        try:
            st.flush()
        except Exception:
            pass
        return True
    except Exception:
        # 最后兜底：用 ASCII 再写一次（连 Unicode 字符都不带）。
        try:
            ascii_text = text.encode("ascii", "replace").decode("ascii")
            st.write(ascii_text + "\n")
            try:
                st.flush()
            except Exception:
                pass
            return True
        except Exception:
            return False


def configure_process_env(env: Optional[dict] = None) -> dict:
    """给子进程环境补上 UTF-8 相关变量（EXT-017① 的「环境变量层」）。

    设置：

    * ``PYTHONUTF8=1`` —— 让 Python 整个运行时用 UTF-8（PEP 540）；
    * ``PYTHONIOENCODING=utf-8`` —— 强制 stdout/stderr 用 UTF-8。

    ★ 注意：这两个变量必须在**解释器启动前**生效，
      所以调用方要**先设好环境再 Popen**（不能靠 `os.environ` 事后改）。

    Parameters
    ----------
    env
        目标环境字典；``None`` ⇒ 用 `os.environ` 的副本。

    Returns
    -------
    dict
        传入了变量的那个字典（原地修改后返回）。
    """
    target = os.environ if env is None else env
    target["PYTHONUTF8"] = "1"
    target["PYTHONIOENCODING"] = "utf-8"
    # PYTHONLEGACYWINDOWSSTDIO 会让 Python 用 ANSI 码页写控制台 ⇒ 明确关掉。
    target["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    return target


def console_code_page() -> str:
    """读当前控制台代码页（诊断用；读不到返回 "?"）。

    ★ 只用标准库 `ctypes`（`kernel32.GetConsoleOutputCP`），
      不引入任何依赖。
    """
    try:
        import ctypes
        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        return "cp%d" % int(cp)
    except Exception:
        return "?"


def describe() -> dict:
    """诊断摘要（写进日志/STATUS，便于 reviewer 核对真实环境）。"""
    return {
        "stdout_encoding": getattr(sys.stdout, "encoding", None),
        "stderr_encoding": getattr(sys.stderr, "encoding", None),
        "console_output_cp": console_code_page(),
        "python_utf8_mode": os.environ.get("PYTHONUTF8"),
        "pythonioencoding": os.environ.get("PYTHONIOENCODING"),
        "filesystem_encoding": getattr(sys, "getfilesystemencoding", lambda: None)(),
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(describe(), ensure_ascii=False, indent=2))
    safe_print("🔴 乱码兜底自检：这条应该显示 ? 而不是崩掉")
