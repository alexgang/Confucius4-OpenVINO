"""APP-086(2)：建**影子包**（before / after 两臂）——**不动用户正在测试的安装目录**。

🔴 为什么用影子包（APP-055 / MEMORY §十）：
  * 开发树 `live_caption/` 里**没有** TTS / MT / 说话人模型（只有 ASR 的 OV 模型）
    ⇒ 必须在**包的结构**里跑 CLI。
  * 用户正在测试的 `Confucius4_LiveCaption_v2.4` **禁止原地改**
    ⇒ 影子包 = 真包的 `app/`（拷贝）＋ `models/`、`python/`（**目录联接，零拷贝**）
    ⇒ 运行时 `PKG_ROOT` 的相对路径仍然成立（模型、旁路资产都找得到）。
  * `before` 臂 = 真包 v2.4 的代码（= 当前交付给用户的行为）
    （实测：v2.4 的 `app/live_caption_app.py` 与 dev HEAD 只差 5 行 GUI 文案）
  * `after` 臂 = 真包 app/ ＋ 本轮改动的 3 个文件
    （`live_caption_app.py` / `clone_voice.py` / `tts_worker.py`）

用法：python app362_app086_build_shadow.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

PKG = r'C:\Users\Trekker-PLT'.replace('PLT', 'PTL')
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4'
DEV = r'C:\Users\Trekker-PTL\confucius4-openvino\live_caption'
BASE = r'C:\Users\Trekker-PTL\_app_shadow'
CHANGED = ('live_caption_app.py', 'clone_voice.py', 'tts_worker.py')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def build(arm):
    d = os.path.join(BASE, arm)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    shutil.copytree(os.path.join(PKG, 'app'), os.path.join(d, 'app'),
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('models', 'python'):
        link = os.path.join(d, name)
        target = os.path.join(PKG, name)
        r = subprocess.run(['cmd', '/c', 'mklink', '/J', link, target],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('mklink %s failed: %s %s' % (name, r.stdout, r.stderr))
    return d


def main() -> int:
    out = {'pkg': PKG, 'dev': DEV, 'base': BASE, 'arms': {}}
    for arm in ('before', 'after'):
        d = build(arm)
        app = os.path.join(d, 'app')
        if arm == 'after':
            for f in CHANGED:
                shutil.copy2(os.path.join(DEV, f), os.path.join(app, f))
        out['arms'][arm] = {
            'dir': d,
            'app_py': {f: {'sha256': sha(os.path.join(app, f)),
                           'bytes': os.path.getsize(os.path.join(app, f))}
                       for f in CHANGED if os.path.exists(os.path.join(app, f))},
            'n_app_py': len([x for x in os.listdir(app) if x.endswith('.py')]),
            'models_junction': os.path.isdir(os.path.join(d, 'models')),
            'python_junction': os.path.isdir(os.path.join(d, 'python')),
            'manifest_present': os.path.exists(os.path.join(app, 'MANIFEST.json')),
        }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'app362_app086_shadow_manifest.json'),
              'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
