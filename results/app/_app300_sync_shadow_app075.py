#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app300 — 把 **APP-075 / APP-076 的本轮代码**同步进影子包（设备级实测用）。

## 为什么（APP-054⑤ + APP-075(e) + APP-076）
* **不许**在用户正在测试的安装目录（`Confucius4_LiveCaption_v2.2`）里原地改文件
  ⇒ 代码只在仓库 `live_caption/` 改 ⇒ 设备级实测必须在**影子包**上做。
* APP-075(e) 要交 `shared/app_listen/v23_clone_r2/` ⇒ 需要**设备级 clone 臂**跑出
  逐句 wav ＋ 逐段 jsonl ⇒ 影子包必须含**本轮登记门槛代码**。

## 本轮要进影子包的东西（一个都不能少）

| 类别 | 文件 | 来源 | 依据 |
|---|---|---|---|
| App 代码 | `speaker_voice.py` | 仓库 `live_caption/` | APP-075(a) 登记门槛 |
| App 代码 | `live_caption_app.py` | 仓库 `live_caption/` | APP-075(a)(b) 接线（`spk_conf` 透传 / 回落预设 A） |
| ASR 代码 | `asr052_speaker_tracker_api.py` | ASR `scripts/` | **APP-076 / ASR-050**（`min_clean_ratio` 0.8→0.6） |
| ASR 代码 | `asr_runtime_switches.py` | ASR `scripts/` | APP-076（ASR-050 交接单第 ④ 节，**之前不在包内**） |
| ASR 代码 | `asr052_spk_runtime.py` / `asr_thread_defaults.py` / `asr_spk_window.py` | ASR `scripts/` | 不变（保持与本轮一致） |

🔴 **`asr_spk_window.py` / `asr_runtime_switches.py` 之前不在包内**
⇒ 上一轮 APP-075 的**离线**诊断用的是**旧包里的 10 s 窗 + 0.8 门槛**
⇒ 本轮影子包必须换成 **5 s 窗 + 0.6 门槛** ⇒ **设备级结果与离线结论可能不同**
⇒ 这正是必须做设备级复测的原因。

## 硬链接 vs 副本
* 影子包的 `app/*.py` 与真包是**硬链接**（同 inode）⇒ 写入会**回写真包**
  ⇒ 🔴 **凡是要覆盖的文件，一律先 `os.remove` 再 `shutil.copy2`**
  （删硬链接不影响真包；`copy2` 写的是新 inode）。

## 自检（必须全 PASS）
1. 覆盖文件与仓库版**逐字节一致**（SHA256）；
2. `app/asr_spk/` 有 **5 个** `.py`，且 `asr052_speaker_tracker_api.py` 的 md5
   == ASR-050 交接单给的 `61be393ce6343bfa63892ce0c35f5c44`；
3. `asr052_speaker_tracker_api.py` 里 `min_clean_ratio` 默认值 == **0.6**
   （用**正则取第一个匹配**，与 ASR 的跨模块纪律一致）；
4. 影子包里 `speaker_voice.py` 含 **APP-075 特征串**（`REG_CONF_MIN` /
   `registration_ticket` / `mark_fallback`）⇒ 证明测的是本轮新代码；
5. 影子包里 `live_caption_app.py` 含 `spk_conf=spk_conf` 接线特征串。

## 用法
```
python results/app/_app300_sync_shadow_app075.py
```
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
SHADOW = os.path.join(HOME, 'shared', 'app067_shadow')
ASR_ROOT = os.path.join(HOME, 'qwen3asr_06b')
ASR_SCRIPTS = os.path.join(ASR_ROOT, 'scripts')

#: 🔴 本轮改动的 App 侧文件 ⇒ 影子包里必须是**仓库版真副本**
REPO_OVERRIDES = (
    'speaker_voice.py',        # APP-075(a) 登记门槛（核心）
    'live_caption_app.py',     # APP-075(a)(b) 接线
)

#: 🔴 ASR-050 交接单第 ④ 节：**5 个**交付文件
ASR_FILES = (
    'asr052_speaker_tracker_api.py',
    'asr052_spk_runtime.py',
    'asr_thread_defaults.py',
    'asr_spk_window.py',
    'asr_runtime_switches.py',
)

#: 🔴 ASR-050 交接单给出的 md5（唯一事实来源）
ASR050_MD5 = '61be393ce6343bfa63892ce0c35f5c44'

#: 特征串：证明影子包里是**本轮**的新代码
FEATURES = (
    (os.path.join('app', 'speaker_voice.py'), 'REG_CONF_MIN = 0.5',
     'APP-075(a) 登记 conf 门槛'),
    (os.path.join('app', 'speaker_voice.py'), 'registration_ticket',
     'APP-075(a) 登记票（最长合格段）'),
    (os.path.join('app', 'speaker_voice.py'), 'mark_fallback',
     'APP-075(b) 回落预设 A 记日志'),
    (os.path.join('app', 'live_caption_app.py'), 'spk_conf=spk_conf',
     'APP-075(a) spk_conf 透传'),
    (os.path.join('app', 'live_caption_app.py'), '_spk_fallback_seen',
     'APP-075(b) 回落只记一次'),
)


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def replace_with_copy(src, dst):
    """🔴 覆盖 dst 为 src 的**真副本**。

    影子包里 `app/*.py` 与真包是**硬链接** ⇒ 直接 `shutil.copy2(src, dst)`
    会**回写真包**（写穿硬链接）⇒ 必须先 `os.remove`（删链接，不动真包）。
    """
    if os.path.exists(dst):
        os.remove(dst)
    shutil.copy2(src, dst)


def main():
    if not os.path.isdir(SHADOW):
        print('影子包不存在：%s' % SHADOW)
        return 2
    app_dst = os.path.join(SHADOW, 'app')
    asr_dst = os.path.join(app_dst, 'asr_spk')
    print('影子包 =', SHADOW)

    # ── ① App 代码（仓库版真副本）────────────────────────────
    print('\n[1] App 代码 → 影子包')
    for fn in REPO_OVERRIDES:
        src = os.path.join(REPO, 'live_caption', fn)
        dst = os.path.join(app_dst, fn)
        if not os.path.isfile(src):
            print('  !! 仓库缺 %s' % fn)
            return 2
        replace_with_copy(src, dst)
        print('  覆盖：app/%-22s %8d B  sha=%s'
              % (fn, os.path.getsize(dst), sha256(dst)[:16]))

    # 🔴 删掉影子包的 __pycache__（否则可能用旧 .pyc）
    for pc in (os.path.join(app_dst, '__pycache__'),
               os.path.join(asr_dst, '__pycache__')):
        if os.path.isdir(pc):
            shutil.rmtree(pc)
            print('  清缓存：%s' % os.path.relpath(pc, SHADOW))

    # ── ② ASR 交付文件（5 个）───────────────────────────────
    print('\n[2] ASR 交付文件 → app/asr_spk/（ASR-050 / APP-076）')
    os.makedirs(asr_dst, exist_ok=True)
    for fn in ASR_FILES:
        src = os.path.join(ASR_SCRIPTS, fn)
        dst = os.path.join(asr_dst, fn)
        if not os.path.isfile(src):
            print('  !! ASR 侧缺 %s' % fn)
            return 2
        replace_with_copy(src, dst)
        print('  同步：app/asr_spk/%-32s %8d B  md5=%s'
              % (fn, os.path.getsize(dst), md5(dst)))

    # ── ③ 自检 ───────────────────────────────────────────────
    print('\n--- 自检 ---')
    ok = True

    def chk(name, cond, detail=''):
        nonlocal ok
        ok &= bool(cond)
        print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                               (' —— %s' % detail) if detail else ''))

    for fn in REPO_OVERRIDES:
        src = os.path.join(REPO, 'live_caption', fn)
        dst = os.path.join(app_dst, fn)
        chk('app/%s 与仓库版逐字节一致' % fn, sha256(src) == sha256(dst))

    n_py = len([f for f in os.listdir(asr_dst) if f.endswith('.py')])
    chk('app/asr_spk/ 有 5 个 .py（ASR-050 后）', n_py == 5, '实得 %d' % n_py)

    api = os.path.join(asr_dst, 'asr052_speaker_tracker_api.py')
    m = md5(api)
    chk('asr052 md5 == ASR-050 交接单值', m == ASR050_MD5, m)

    # 🔴 默认值现读（**取第一个匹配**）⇒ 与 ASR 的跨模块纪律一致
    txt = open(api, encoding='utf-8', errors='replace').read()
    mm = re.search(r'min_clean_ratio\s*:\s*float\s*=\s*([0-9.]+)', txt)
    chk('asr052 min_clean_ratio 默认值 == 0.6',
        bool(mm) and float(mm.group(1)) == 0.6,
        mm.group(1) if mm else '未找到')

    # 🔴 5 s 窗的唯一事实来源
    win = os.path.join(asr_dst, 'asr_spk_window.py')
    wt = open(win, encoding='utf-8', errors='replace').read()
    chk('asr_spk_window.WIN_S_DEFAULT == 5.0',
        'WIN_S_DEFAULT = 5.0' in wt)

    for rel, feat, desc in FEATURES:
        p = os.path.join(SHADOW, rel)
        hit = False
        if os.path.isfile(p):
            t = open(p, 'rb').read().decode('utf-8', errors='replace')
            hit = feat in t
        chk('影子含特征串（%s）' % desc, hit, rel)

    # 🔴 真包**必须没被动过**（影子覆盖不得回写）
    REAL_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
    if os.path.isdir(REAL_PKG):
        for fn in REPO_OVERRIDES:
            real = os.path.join(REAL_PKG, 'app', fn)
            if os.path.isfile(real):
                chk('真包 app/%s 未被影子覆盖回写（与影子不同源）' % fn,
                    sha256(real) != sha256(os.path.join(app_dst, fn))
                    or os.path.samefile(real, os.path.join(app_dst, fn)) is False,
                    'real sha=%s' % sha256(real)[:12])

    print('\nverdict =', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
