"""_smoke_common.py — 冒烟测试脚本的公共头（路径全部**相对仓库根**推导）

★ 为什么有这��文件（EXT-022 已定②）：
  `pw_accept1-4` 原先是临时脚本（`.tmp/` 下），里面**写死了绝对路径**
  ⇒ 换机器/换目录就跑不了 ⇒ 不可复现。
  ⇒ 现在统一从 `__file__` 推导仓库根 ⇒ 任何 clone 都能直接跑。

★ 定位（重要，别误用）：
  这些脚本只是**冒烟测试**（插件页能打开、设置能存、hello 能上报）。
  **浏览器端人工验收由用户亲自做**（英文网页视频 + 本地 mp4，各 1 分钟，
  带**用户手势**的 tabCapture）⇒ **不要**用这些脚本替代用户的验收。
"""
from __future__ import annotations

import os
import sys

# tests/smoke/_smoke_common.py → 仓库根
SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))

if SMOKE_DIR not in sys.path:
    sys.path.insert(0, SMOKE_DIR)


def profile_dir(name: str) -> str:
    """每次实测用**唯一**的 profile 子目录（结束即删，不入库）。"""
    return os.path.join(ROOT, ".tmp", "pw_ext", name)
