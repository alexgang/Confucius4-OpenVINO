import os
import pkg_paths          # noqa: E402  （单一数据源）


def _find_repo_root(start):
    """向上查找仓库根（祖先目录含 `live_caption/` ＋ `pkg_paths.py`）。

    ⇒ **不写死仓库根**（§118/§119 铁律：写死 ⇒ fresh clone 里是假象）。
    """
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('向上查找仓库根失败：%s' % start)
        cur = parent
import sys

REPO = REPO
sys.path.insert(0, REPO)
import shortcut_update as su

PKG = pkg_paths.discover_pkg_dir()
VER = "1.13"

r = su.update_desktop_shortcut(PKG, VER)
print("ok      =", r.get("ok"))
print("reason  =", r.get("reason"))
print("lnk     =", r.get("lnk_path"))
print("target  =", r.get("target"))
print("removed =", r.get("removed"))
print("com     =", r.get("com"))
print("flags   =", hex(r.get("linkflags") or -1))

v = su.verify_lnk(r.get("lnk_path", ""), PKG)
print("verify  =", v.get("ok"), v.get("checks"))
