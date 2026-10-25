"""app053_regression_check.py —— 用**候选 caption_render** 跑既有回归。

目的：证明 §44 拟实现的「跨段上限」修复**不破坏**既有验收：
  - `results/app/test_app015_caption_render.py`（§41 的 REAL 23/23 + BUG 5/5）
  - `results/app/app047_app_gate_test.py`（§41 的离线闸门）

做法：造一个「影子 live_caption 目录」⇒ 只放**候选** `caption_render.py`
      ⇒ 把两个回归脚本的 `sys.path` 指向影子目录 ⇒ 跑
      ⇒ **不碰工作区的 `live_caption/caption_render.py`**。

纪律：纯离线、不 import 被测模块、不跑推理、不占 GPU、不取机器锁。
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
SHADOW = os.path.join(HERE, '_app053_shadow')
CAND = os.path.join(HERE, 'app053_caption_render_segcap_candidate.py')
REGRESSIONS = ('test_app015_caption_render.py', 'app047_app_gate_test.py')

ORIG_SYS = "sys.path.insert(0, os.path.join(REPO, 'live_caption'))"


def main():
    if os.path.exists(SHADOW):
        shutil.rmtree(SHADOW)
    os.makedirs(os.path.join(SHADOW, 'live_caption'))
    shutil.copy(CAND, os.path.join(SHADOW, 'live_caption', 'caption_render.py'))

    results = []
    for name in REGRESSIONS:
        src_path = os.path.join(REPO, 'results', 'app', name)
        src = io.open(src_path, encoding='utf-8').read()
        if ORIG_SYS not in src:
            print(f'!! {name}: 未找到 sys.path 锚点 ⇒ 跳过')
            continue
        shadow_path = os.path.join(SHADOW, name).replace('\\', '/')
        src = src.replace(ORIG_SYS, f"sys.path.insert(0, r'{shadow_path.rsplit('/', 1)[0]}/live_caption')")
        # 🔴🔴 **关键**：`app047` 用**相对/绝对路径读仓库文件**
        #   （`results/pack_v13.py`、`pkg_exclude.py` 等）⇒ 影子脚本里的
        #   `REPO` 必须仍指向**真实仓库根**（不能指向影子目录）。
        #   ⇒ 把 `REPO = ...` 这一行**改写**为真实仓库根。
        real_repo = REPO.replace('\\', '/')
        src = re.sub(r"^REPO = .*$",
                     f"REPO = r'{real_repo}'",
                     src, count=1, flags=re.M)
        dst = os.path.join(SHADOW, name)
        io.open(dst, 'w', encoding='utf-8', newline='\n').write(src)
        print(f'== 跑 {name}（候选 caption_render）==')
        r = subprocess.run([sys.executable, dst], capture_output=True,
                           text=True, encoding='utf-8')
        lines = [l for l in r.stdout.split('\n')
                 if 'verdict' in l.lower() or 'PASS' in l or 'FAIL' in l]
        for l in lines[-8:]:
            print('   ', l)
        print('    exit =', r.returncode)
        if r.returncode != 0:
            print('    STDERR:', r.stderr[-1200:])
        results.append({'script': name, 'exit': r.returncode,
                        'tail': lines[-8:]})
        print()

    ok = all(r['exit'] == 0 for r in results)
    print(f'== 回归总判定：{"PASS" if ok else "FAIL"}'
          f'（{sum(1 for r in results if r["exit"] == 0)}/{len(results)} 脚本 exit=0）')
    shutil.rmtree(SHADOW, ignore_errors=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
