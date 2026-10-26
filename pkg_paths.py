r"""pkg_paths.py —— 客户包路径的**单一数据源**（自动发现，不写死版本）

为什么要有这个模块
------------------
真实事故（2026-10-26，STATUS §47.6 最后一条）
------------------------------------------------
`results/app/test_tts_close_gui_quit_pkg.py` 把客户包版本**写死**成
`Confucius4_LiveCaption_v1.4`。包一升到 v1.5，这个「包内验收脚本」
就指着**旧包**跑 ⇒ 报出 3 项 FAIL ⇒ 看起来像**真回归**，
实际只是**脚本过期**（真实缺陷一个也没有）。

⇒ 教训：**验收脚本不能把被验收对象的版本写死**。
⇒ 这不是「改一处」的事：全仓库有 **18 个**活用的验收/回归脚本写死了包版本，
还有 **2 个会进包的生产模块**写死了包路径（客户机上一旦版本不匹配就找不到音色文件）。

所以规则只在这里写一份（**单一数据源**），所有脚本与生产代码都 `import` 它：

  - `discover_pkg_dir()`   —— 自动发现**最大版本**的客户包目录；
  - `pkg_app_dir()`       —— 包内的 `app/` 目录；
  - `pkg_version()`       —— 发现的版本号；
  - `resolve_pkg_dir()`   —— 显式指定 > 环境变量 > 自动发现（三级优先）。

纪律
----
* **刻意零依赖**（只用 stdlib、不 import 仓库里的任何其他模块），
  这样从任意 CWD 用 `python <脚本路径>` 运行都能找到它
  （与 `pkg_exclude.py` 同一条纪律）。
* **不写死版本号**：找不到包时**抛异常**，绝不静默回退到某个旧版本
  ⇒ 否则又会把「指错对象」伪装成「验收通过」。
* **不 import 被测模块**（本模块只做路径解析，零副作用）。
"""

from __future__ import annotations

import os

__all__ = [
    'PKG_NAME_PREFIX',
    'PKG_ROOT_DEFAULT',
    'ENV_PKG',
    'discover_pkg_dir',
    'pkg_app_dir',
    'pkg_version',
    'resolve_pkg_dir',
    'repo_root',
]

#: 客户包目录名的固定前缀（版本号部分**不写死**）
PKG_NAME_PREFIX = 'Confucius4_LiveCaption_v'

#: 客户包默认所在目录（父目录，可被环境变量覆盖）
PKG_ROOT_DEFAULT = r'C:\Users\Trekker-PTL'

#: 环境变量名（显式指定包目录时用）
ENV_PKG = 'LIVECAP_PKG'


def _ver_key(ver: str):
    """版本号 → 可比较的元组（`1.10` > `1.9`，不是字符串比较）。"""
    parts = []
    for chunk in ver.split('.'):
        try:
            parts.append(int(chunk))
        except ValueError:
            return None
    return tuple(parts) if parts else None


def discover_pkg_dir(pkg_root: str = None) -> str:
    """自动发现**最大版本**的客户包目录（要求该目录下有 `app/`）。

    返回包目录的绝对路径。

    找不到 ⇒ 抛 `FileNotFoundError`（**不静默回退**到任何旧版本）。
    """
    root = os.path.abspath(pkg_root or os.environ.get(
        'LIVECAP_PKG_ROOT', PKG_ROOT_DEFAULT))

    best = None
    best_key = None
    if os.path.isdir(root):
        for name in os.listdir(root):
            if not name.startswith(PKG_NAME_PREFIX):
                continue
            ver = name[len(PKG_NAME_PREFIX):]
            key = _ver_key(ver)
            if key is None:
                continue
            # 必须真的有 app/ —— 否则只是个残留目录或备份
            if not os.path.isdir(os.path.join(root, name, 'app')):
                continue
            if best_key is None or key > best_key:
                best_key = key
                best = os.path.join(root, name)

    if best is None:
        raise FileNotFoundError(
            '[客户包] 在 %s 下未找到 %sX.Y（含 app/ 的）客户包目录'
            % (root, PKG_NAME_PREFIX))
    return os.path.abspath(best)


def pkg_version(pkg_dir: str = None) -> str:
    """返回包目录的版本号（如 `1.5`）。"""
    d = os.path.abspath(pkg_dir) if pkg_dir else discover_pkg_dir()
    name = os.path.basename(d.rstrip('\\/'))
    if not name.startswith(PKG_NAME_PREFIX):
        raise ValueError('不是客户包目录（名字不以 %s 开头）：%s'
                         % (PKG_NAME_PREFIX, d))
    return name[len(PKG_NAME_PREFIX):]


def pkg_app_dir(pkg_dir: str = None) -> str:
    """返回包内的 `app/` 目录绝对路径。"""
    d = os.path.abspath(pkg_dir) if pkg_dir else discover_pkg_dir()
    app = os.path.join(d, 'app')
    if not os.path.isdir(app):
        raise FileNotFoundError('[客户包] 缺 app/ 目录：%s' % app)
    return app


def resolve_pkg_dir(pkg_dir: str = None) -> str:
    """三级优先解析包目录：**显式指定 > 环境变量 > 自动发现**。

    ⚠️ 环境变量 `LIVECAP_PKG` 在生产代码里也被用来指「包根目录」
    （`tts_cuda.py` 把它设成 `__file__` 的上上级）⇒ 一致。
    """
    if pkg_dir:
        return os.path.abspath(pkg_dir)
    env = os.environ.get(ENV_PKG, '').strip()
    if env and os.path.isdir(os.path.join(env, 'app')):
        return os.path.abspath(env)
    return discover_pkg_dir()


def repo_root() -> str:
    """仓库根目录（本文件位于仓库根）。"""
    return os.path.dirname(os.path.abspath(__file__))
