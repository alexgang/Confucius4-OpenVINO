"""app_root.py — ★ 定位实时字幕 App 的安装目录（**版本自适应**）

## 为什么需要这个文件（★ 缺陷 22，本轮实测抓到的真缺陷）

本模块原先把 App 路径**硬编码**成
`C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.6`（`ext/engine_runtime.py`
与 4 个 `tools/*.py` 各写一份）。

**实测**：2026-10-29 App 升级到 **v1.7**（`v1.6` 目录**已被删除**，
只剩 `v1.6.zip` 压缩包）⇒ 所有硬编码 v1.6 的地方**全部失效**：

* `ext/engine_runtime.py` ⇒ `available()` 三项 `probe_ok` 变 False、
  引擎加载直接失败；
* `tests/test_ext_selfcheck.py` 的「App 的 tts_engine 可 import」用例
  ⇒ **FAIL**（本轮自测实测到：102 项里 1 FAIL）。

⇒ 修法：**按目录实际存在情况解析**，不再硬编码版本号。
   规则（照抄 App 的目录命名）：
   1. 环境变量 `EXT_APP_ROOT` 显式指定 ⇒ 优先（**显式覆盖永远优先**）；
   2. 否则在 `C:\\Users\\Trekker-PTL` 下找 `Confucius4_LiveCaption_v*` 目录，
   **按版本号从大到小**挑第一个**结构完整**的
   （结构完整 = 同时有 `app/`、`models/`、`python/python.exe`）；
   3. 找不到 ⇒ 返回 `None`（调用方**显式报错**，绝不静默用旧路径）。

## 铁律

* **只读**：本模块只**读** App 的目录与文件，**不改**对方任何文件；
* **不猜**：解析不出来就返回 `None` 并让调用方显式报错；
* 环境变量 `EXT_APP_ROOT` 的优先级最高（便于离线复现与 CI）。
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

# 候选根目录（App 安装在用户目录下）
# ★★ EXT-031 ②：**不再写死开发机用户目录**。
#   默认 = 当前用户主目录（发行包里 App 装在**装它的那个用户**下）；
#   环境变量 `EXT_APP_SEARCH_ROOT` 可显式指定搜索根（离线复现 / CI）。
_USER_ROOT = (os.environ.get("EXT_APP_SEARCH_ROOT", "").strip()
              or os.path.expanduser("~"))
_PREFIX = "Confucius4_LiveCaption_v"
_VER_RE = re.compile(r"^Confucius4_LiveCaption_v(\d+(?:\.\d+)*)$")


def _ver_key(name: str) -> tuple:
    """把版本号变成可比较的元组（'1.7' → (1, 7)）。"""
    m = _VER_RE.match(name)
    if not m:
        return ()
    return tuple(int(x) for x in m.group(1).split("."))


def _is_complete(root: str) -> bool:
    """结构完整吗？（有 app/ + models/ + python/python.exe 才算可用）"""
    return (os.path.isdir(os.path.join(root, "app"))
            and os.path.isdir(os.path.join(root, "models"))
            and os.path.isfile(os.path.join(root, "python", "python.exe")))


def candidate_roots() -> List[str]:
    """列出候选 App 目录（**按版本从新到旧**）。"""
    out: List[str] = []
    try:
        names = os.listdir(_USER_ROOT)
    except Exception:
        names = []
    for nm in names:
        if not _VER_RE.match(nm):
            continue
        full = os.path.join(_USER_ROOT, nm)
        if os.path.isdir(full):
            out.append(full)
    out.sort(key=lambda p: _ver_key(os.path.basename(p)), reverse=True)
    return out


def resolve_app_root(explicit: Optional[str] = None) -> Optional[str]:
    """解析 App 安装目录。

    Parameters
    ----------
    explicit : str or None
        显式指定路径（一般传环境变量 `EXT_APP_ROOT`）。

    Returns
    -------
    str or None
        App 根目录；解析不到返回 **None**（调用方须显式报错）。
    """
    env = explicit if explicit is not None else os.environ.get("EXT_APP_ROOT")
    if env:
        env = env.strip()
        if env and os.path.isdir(env):
            return env
        # 显式指定但目录不存在 ⇒ **不静默回退**（显式配置错了必须暴露）
        return None
    for root in candidate_roots():
        if _is_complete(root):
            return root
    return None


def app_python(app_root: str) -> str:
    """App 自带解释器路径。"""
    return os.path.join(app_root, "python", "python.exe")


def app_path(*parts: str) -> Optional[str]:
    """拼 **App 包内**的路径（版本自适应）。

    ★★ EXT-031 ② 的核心：**引擎/模型路径一律从 App 包根相对解析**
      ⇒ 发行包里不依赖任何开发机绝对路径。

    Returns
    -------
    str | None
        拼好的路径；App 解析不到（`resolve_app_root()` 返回 None）⇒ **None**
        （调用方须显式处理，**绝不**臆造路径）。
    """
    root = resolve_app_root()
    if not root:
        return None
    return os.path.join(root, *parts)


def package_root() -> str:
    """**本插件自身**的包根目录（`live_dub_ext/` 目录）。

    ★ 用于一切「相对包根」的路径（发行包里插件目录名可能变）。
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def describe_app_root(app_root: Optional[str]) -> dict:
    """诊断信息（写进 STATUS / 日志，便于核对到底用了哪个版本）。"""
    cands = candidate_roots()
    return {
        "resolved": app_root,
        "resolved_version": (os.path.basename(app_root)
                             if app_root else None),
        "candidates": [{"path": p,
                        "version": os.path.basename(p),
                        "complete": _is_complete(p)} for p in cands],
        "env_override": os.environ.get("EXT_APP_ROOT"),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(describe_app_root(resolve_app_root()),
                     ensure_ascii=False, indent=2))
