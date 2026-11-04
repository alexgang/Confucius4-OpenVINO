#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴 建 APP-067 的**影子包**（设备级实测用）—— **测的是本轮代码**。

## 为什么（APP-054 ⑤ + APP-067）
> 不许在用户正在测试的安装目录里原地改文件（APP-054⑤）
> ⇒ 代码只在开发目录 `live_caption/` 改 ⇒ 验证必须在**影子包**上做。

reviewer 在 APP-067 ⑤ 明文要求：
> 「在影子包上重跑 clone 臂」⇒ 影子包必须含**本轮的全部改动**。

## 本轮要进影子包的东西（🔴 一个都不能少）

| 类别 | 文件 | 来源 |
|---|---|---|
| App 代码 | `live_caption_app.py` / `tts_worker.py` / `tts_service.py` / `speaker_tracker.py` | 仓库 `live_caption/` |
| ASR 代码 | `asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py` / **`asr_spk_window.py`** | ASR 仓库 `scripts/`（**4 个**，ASR-045 后） |
| seg IR | `models/spk/pyannote_seg_3_0/fp16-w5/`（5 s 静态 `(1,1,80000)`） | ASR 仓库 `models/pyannote_seg/ov-fp16-w5/` |

## 硬链接 vs 副本（**零拷贝**）
* `app/*.py`（未改动的） ＋ `models/**` ⇒ **硬链接**（零拷贝，不占磁盘）
* **改动过的文件** ⇒ **真副本**（改副本**不会**回写真包 ⇒ 硬链接写入会断开）
* 🔴 `models/spk/pyannote_seg_3_0/fp16-w5/` ⇒ **真副本**（10 MB，可接受）

## 自检（**必须全 PASS** 才开始设备级实测）
1. 每个改动文件与仓库版**逐字节一致**（SHA256）；
2. `asr_spk/` 里有 **4 个** `.py`；
3. `fp16-w5/` 的 IR 存在且输入第三维 = **80000**；
4. 影子包的 `app/tts_worker.py` **含** APP-067 ①(a) 的排队特征串
   （`_pending_spk_voice`）⇒ **证明测的是新代码**；
5. 影子包的 `app/live_caption_app.py` **含** APP-067 ③ 的 `_sync_mt_combo_to_gpu0`
   ⇒ 证明 D4 修复在包里。

## 用法
```
python results/app/_app240_build_app067_shadow.py
```
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
SHADOW = os.path.join(HOME, 'shared', 'app067_shadow')
ASR_ROOT = os.path.join(HOME, 'qwen3asr_06b')
ASR_SCRIPTS = os.path.join(ASR_ROOT, 'scripts')
ASR_MODELS = os.path.join(ASR_ROOT, 'models')

#: 🔴 本轮改动的 App 侧文件 ⇒ 影子包里必须是**仓库版真副本**
REPO_OVERRIDES = (
    'live_caption_app.py',
    'tts_worker.py',
    'tts_service.py',
    'speaker_tracker.py',
    # 🔴 APP-067 ⑤：seg IR **按窗口选变体**（5 s ⇒ fp16-w5）
    #   ⇒ 漏了它 ⇒ 影子包仍加载 10 s 的 fp16 IR ⇒ 旁路零标签
    'speaker_assets.py',
)

#: 🔴 ASR-045 后的 **4 个**交付文件
ASR_FILES = (
    'asr052_speaker_tracker_api.py',
    'asr052_spk_runtime.py',
    'asr_thread_defaults.py',
    'asr_spk_window.py',
)

#: 5 s 静态 seg IR（源 → 包内相对路径）
W5_SRC = os.path.join(ASR_MODELS, 'pyannote_seg', 'ov-fp16-w5')
W5_FILES = ('pyannote_seg_3_0_w5.xml', 'pyannote_seg_3_0_w5.bin')
W5_DST_REL = os.path.join('models', 'spk', 'pyannote_seg_3_0', 'fp16-w5')

#: 🔴 特征串：**证明影子包里是本轮的新代码**
FEATURES = (
    (os.path.join('app', 'tts_worker.py'), '_pending_spk_voice',
     'APP-067 ①(a) worker 加载期排队'),
    (os.path.join('app', 'tts_worker.py'), '_spk_bind',
     'APP-067 ①(b) seg→spk 绑定表'),
    (os.path.join('app', 'live_caption_app.py'), '_sync_mt_combo_to_gpu0',
     'APP-067 ③ combo 同步 GPU.0'),
    (os.path.join('app', 'live_caption_app.py'), '_fit_status_light_width',
     'APP-067 ④ 按钮按像素定宽'),
    (os.path.join('app', 'asr_spk', 'asr_spk_window.py'), 'WIN_S_DEFAULT = 5.0',
     'ASR-045 唯一事实来源 5 s'),
    (os.path.join('app', 'speaker_assets.py'), 'fp16-w5',
     'APP-067 ⑤ seg IR 按窗口选变体'),
)


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def link_tree(src, dst):
    n_link = n_copy = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tgt = dst if rel == '.' else os.path.join(dst, rel)
        if not os.path.isdir(tgt):
            os.makedirs(tgt, exist_ok=True)
        for fn in files:
            s = os.path.join(root, fn)
            d = os.path.join(tgt, fn)
            if os.path.exists(d):
                continue
            try:
                os.link(s, d)
                n_link += 1
            except OSError:
                shutil.copy2(s, d)
                n_copy += 1
    return n_link, n_copy


def main():
    if not os.path.isdir(PKG):
        print('真包不存在：%s' % PKG)
        return 2
    print('真包   =', PKG)
    print('影子包 =', SHADOW)
    os.makedirs(SHADOW, exist_ok=True)

    # ── ① app/（硬链接树）────────────────────────────────────
    app_dst = os.path.join(SHADOW, 'app')
    if os.path.isdir(app_dst):
        shutil.rmtree(app_dst)
    l, c = link_tree(os.path.join(PKG, 'app'), app_dst)
    print('app/   硬链接 %d / 复制 %d' % (l, c))

    # ── ② models/（硬链接树；**不删**已有的，避免重链 10 GB）──
    mod_dst = os.path.join(SHADOW, 'models')
    if not os.path.isdir(mod_dst):
        l, c = link_tree(os.path.join(PKG, 'models'), mod_dst)
        print('models/ 硬链接 %d / 复制 %d' % (l, c))
    else:
        print('models/ 已存在（复用）')

    # ── ③ 顶层文件（硬链接：ACCEPTED/NOTICE/README/bat 等）────
    for fn in os.listdir(PKG):
        s = os.path.join(PKG, fn)
        d = os.path.join(SHADOW, fn)
        if os.path.isfile(s) and not os.path.exists(d):
            try:
                os.link(s, d)
            except OSError:
                shutil.copy2(s, d)

    # ── ③b 包内 python/（**必须有**：CLI 跑的是 `<pkg>/python/python.exe`）──
    #   🔴 836 MB ⇒ **硬链接树**（零拷贝）
    #   ⚠️ 漏了它 ⇒ `FileNotFoundError: python.exe` ⇒ 设备级实测**直接崩**
    #     （本轮踩过：影子包少了 python/ ⇒ app223 的 clone 臂起不来）
    py_dst = os.path.join(SHADOW, 'python')
    if not os.path.isdir(py_dst):
        l, c = link_tree(os.path.join(PKG, 'python'), py_dst)
        print('python/ 硬链接 %d / 复制 %d' % (l, c))
    else:
        print('python/ 已存在（复用）')

    # ── ④ 改动文件 ⇒ **仓库版真副本**（改副本不会回写真包）────
    print()
    for fn in REPO_OVERRIDES:
        src = os.path.join(REPO, 'live_caption', fn)
        dst = os.path.join(app_dst, fn)
        if not os.path.isfile(src):
            print('  !! 仓库缺 %s' % fn)
            return 2
        if os.path.exists(dst):
            os.remove(dst)          # 先删硬链接（**不影响真包**）
        shutil.copy2(src, dst)
        print('  覆盖为仓库版：app/%-24s %8d B  sha=%s'
              % (fn, os.path.getsize(dst), sha256(dst)[:12]))

    # ── ⑤ ASR 交付文件（**4 个**）────────────────────────────
    print()
    asr_dst = os.path.join(app_dst, 'asr_spk')
    os.makedirs(asr_dst, exist_ok=True)
    for fn in ASR_FILES:
        src = os.path.join(ASR_SCRIPTS, fn)
        dst = os.path.join(asr_dst, fn)
        if not os.path.isfile(src):
            print('  !! ASR 侧缺 %s' % fn)
            return 2
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copy2(src, dst)
        print('  同步 ASR：app/asr_spk/%-30s %8d B  sha=%s'
              % (fn, os.path.getsize(dst), sha256(dst)[:12]))

    # ── ⑥ 5 s 静态 seg IR（真副本）───────────────────────────
    print()
    w5_dst = os.path.join(SHADOW, W5_DST_REL)
    os.makedirs(w5_dst, exist_ok=True)
    for fn in W5_FILES:
        src = os.path.join(W5_SRC, fn)
        dst = os.path.join(w5_dst, fn)
        if not os.path.isfile(src):
            print('  !! ASR 侧缺 5 s IR：%s' % src)
            return 2
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copy2(src, dst)
        print('  同步 5 s IR：models/spk/pyannote_seg_3_0/fp16-w5/%-24s %8d B'
              % (fn, os.path.getsize(dst)))

    # ── ⑦ 自检 ────────────────────────────────────────────────
    print()
    print('--- 自检 ---')
    ok = True

    def chk(name, cond, detail=''):
        nonlocal ok
        ok &= bool(cond)
        print('  [%s] %s%s'
              % ('PASS' if cond else 'FAIL', name,
                 (' —— %s' % detail) if detail else ''))

    for fn in REPO_OVERRIDES:
        src = os.path.join(REPO, 'live_caption', fn)
        dst = os.path.join(app_dst, fn)
        same = sha256(src) == sha256(dst)
        chk('app/%s 与仓库版逐字节一致' % fn, same)

    n_py = len([f for f in os.listdir(asr_dst) if f.endswith('.py')])
    chk('app/asr_spk/ 有 4 个 .py（ASR-045 后）', n_py == 4, '实得 %d' % n_py)

    x = os.path.join(w5_dst, 'pyannote_seg_3_0_w5.xml')
    has_w5 = os.path.isfile(x)
    shape_ok = False
    if has_w5:
        import re
        dims = re.findall(r'<dim>(\d+)</dim>', open(x, encoding='utf-8',
                                                   errors='replace').read())
        shape_ok = ('80000' in dims and '160000' not in dims)
    chk('5 s 静态 seg IR 存在且输入第三维 = 80000', has_w5 and shape_ok)

    for rel, feat, desc in FEATURES:
        p = os.path.join(SHADOW, rel)
        hit = False
        if os.path.isfile(p):
            txt = open(p, 'rb').read().decode('utf-8', errors='replace')
            hit = feat in txt
        chk('影子包含特征串（%s）' % desc, hit, rel)

    print()
    print('verdict =', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
