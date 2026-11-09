"""APP-089/090/091/092：建**影子包**（before / after 两臂）——**不动用户正在测试的安装目录**。

🔴 为什么用影子包（APP-055 / MEMORY §十）：
  * 开发树 `live_caption/` 里**没有** TTS / MT / 说话人模型（只有 ASR 的 OV 模型）
    ⇒ 必须在**包的结构**里跑 CLI。
  * 用户正在测试的 `Confucius4_LiveCaption_v2.4` **禁止原地改**
    ⇒ 影子包 = 真包的 `app/`（拷贝）＋ `models/`、`python/`（**目录联接，零拷贝**）
    ⇒ 运行时 `PKG_ROOT` 的相对路径仍然成立（模型、旁路资产都找得到）。

🔴 两臂定义（reviewer APP-089 §4：**before = APP-086 接线版，after = APP-089**）：
  * `before` = 真包 v2.4 的 app/ ＋ **git HEAD（5a0dd8a = APP-086 接线版）**的那几个文件
  * `after`  = 真包 v2.4 的 app/ ＋ **工作树（APP-089/090/091/092 移植后）**的那几个文件
  ⇒ **两臂的差别 = 本轮移植**（不是 v2.4 → HEAD 的差别）。

🔴 只复制**本轮移植涉及的 8 个文件**（不是整目录覆盖 ⇒ 遵守「禁止整目录覆盖同步」）。

用法：python app368_app089_build_shadow.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4'
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
DEV = os.path.join(REPO, 'live_caption')
BASE = r'C:\Users\Trekker-PTL\_app_shadow'

# 🔴 本轮移植涉及的 8 个文件（APP-089/090/091/092）
CHANGED = (
    'clone_voice.py',          # APP-089：ICL 删除 + self_ref + XV_* + split_by_speaker
    'device_config.py',        # APP-090c/091②/092②：tts_speed_min_zh / max_zh / late_drop_sec
    'live_caption_app.py',     # APP-089 b（会话清空）+ APP-091③（字幕条原文小字）
    'speaker_voice.py',        # APP-089 §2c-2：XV_* 说话人参考
    'time_stretch.py',         # APP-090c/091②：中文 1.10–1.50×
    'tts_cuda_sidecar.py',     # APP-089 §2a：不再读 .txt，固定 xvec_only=True
    'tts_service.py',          # APP-090a/092②：n_label_wait / n_late_drop 透传
    'tts_worker.py',           # APP-089 c-1/092②：self_ref 决策 + late_drop
)


def sha(p: str) -> str:
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def git_show(rel: str) -> bytes:
    r = subprocess.run(['git', 'show', 'HEAD:%s' % rel], cwd=REPO,
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('git show HEAD:%s failed: %s' % (rel, r.stderr[:200]))
    return r.stdout


def build(arm: str) -> dict:
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


def fix_cli_unbound(dst: str) -> bool:
    """🔴🔴 **before 臂必须也打这个补丁**（否则跑不了）。

    缺陷（**HEAD 与本轮移植版都有**）：
      `on_nearest=_cli_clone_nearest` 在 `def _cli_clone_nearest` **之前**求值
      ⇒ Python 局部名在函数体执行到该行时还没绑定 ⇒ **UnboundLocalError**
      ⇒ **CLI 整条路径在建策略层时就崩** ⇒ 设备验收根本跑不起来。

    修法：**延迟绑定**（lambda 在调用时才查名字）⇒ 语义等价。
    ⚠️ 这是**崩溃修复**，不是 APP-089/090/091/092 的功能差异
      ⇒ **两臂都打** ⇒ before/after 的差别仍然只来自本轮移植。
    """
    src = open(dst, encoding='utf-8', newline='').read()
    old = '        on_nearest=_cli_clone_nearest)'
    new = ('        on_nearest=lambda seg, spk, sim: '
           '_cli_clone_nearest(seg, spk, sim))')
    if old not in src:
        return False
    assert src.count(old) == 1, 'anchor not unique: %d' % src.count(old)
    open(dst, 'w', encoding='utf-8', newline='').write(src.replace(old, new, 1))
    return True


def main() -> int:
    out = {'pkg': PKG, 'dev': DEV, 'base': BASE,
           'arms': {}, 'changed_files': list(CHANGED)}
    for arm in ('before', 'after'):
        d = build(arm)
        app = os.path.join(d, 'app')
        files = {}
        for f in CHANGED:
            dst = os.path.join(app, f)
            if arm == 'before':
                # 🔴 before = **git HEAD** 的那一版（= APP-086 接线版）
                data = git_show('live_caption/%s' % f)
                with open(dst, 'wb') as fh:
                    fh.write(data)
                # 🔴🔴 **两臂都打 CLI 崩溃修复**（否则 before 臂根本跑不起来）
                if f == 'live_caption_app.py':
                    if not fix_cli_unbound(dst):
                        raise RuntimeError('CLI unbound 修复锚点未命中')
            else:
                shutil.copy2(os.path.join(DEV, f), dst)
            files[f] = {'sha256': sha(dst),
                        'bytes': os.path.getsize(dst),
                        'dev_sha256': sha(os.path.join(DEV, f)),
                        'head_sha256': hashlib.sha256(
                            git_show('live_caption/%s' % f)).hexdigest()}
        out['arms'][arm] = {
            'dir': d,
            'app_py': files,
            'n_app_py': len([x for x in os.listdir(app) if x.endswith('.py')]),
            'models_junction': os.path.isdir(os.path.join(d, 'models')),
            'python_junction': os.path.isdir(os.path.join(d, 'python')),
            'manifest_present': os.path.exists(os.path.join(app, 'MANIFEST.json')),
        }
    # 🔴 断言：两臂必须**确实不同**（否则 before/after 口径没生效）
    a = out['arms']['after']['app_py']
    b = out['arms']['before']['app_py']
    diff = sorted(f for f in CHANGED if a[f]['sha256'] != b[f]['sha256'])
    out['arms_differ_files'] = diff
    out['arms_identical'] = (len(diff) == 0)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'app368_app089_shadow_manifest.json'),
              'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
