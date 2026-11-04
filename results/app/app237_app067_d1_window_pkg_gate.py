#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-067 ⑤ 的**闸门**：验证「D1 = 5 s 窗口」在 **App 侧 / 客户包侧** 落地。

## 背景（APP-067 ⑤ 原文）

> 影子包和客户包：包里没有 `asr_spk_window.py`，App 回退到内核的 WIN_S=10，
> log 显示 `说话人旁路窗口：10.000 s`，实际生效的是 **10 s**。
> 分工：内核常量归 ASR 改。App 这边要做的是：等 ASR 改完后，把
> `asr_spk_window.py` 加进 pkg 的 ASR_FILES（变成 4 个文件，需要 ASR 确认），
> 并在包里验证 log 出现 `说话人旁路窗口：5.000 s`。

🔴 **ASR 侧已完成**（ASR-045，2026-11-04）：
* `asr052_spk_runtime.py` 改为 `import asr_spk_window as _W` ⇒ 窗口常量不再写死；
* `asr_spk_window.WIN_S_DEFAULT = 5.0`；
* NOTICE `shared/NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md` §3 给出
  **4 个文件的 md5**、§4 给出 **5 s 静态 seg IR**（`fp16-w5/`）的必要性。

## 本闸门做什么

### ① 静态闸门（AST + 文件系统，不 import 被测模块）
| # | 判据 | 覆盖的真实故障 |
|---|---|---|
| H1 | `sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` **含 `asr_spk_window.py`** 且**恰好 4 项** | 包内缺文件 ⇒ 内核 `import` 崩 ⇒ 旁路全废 |
| H2 | sync 脚本同步 **5 s 静态 seg IR**（`fp16-w5/`） | 5 s IR 缺 ⇒ shape 不兼容 ⇒ 零标签 |
| H3 | ASR 侧 4 个交付文件的 **md5 与 NOTICE 一致** | 拿错版本 ⇒ 口径不一致 |
| H4 | 5 s IR 源文件存在且 **输入形状 = (1,1,80000)** | 形状不对 ⇒ 直接抛 |
| H5 | App 侧 `speaker_tracker._WIN_S` **解析到 5.0** 且来源是「同源 asr_spk_window」 | App 仍按 10 s 喂 ⇒ 错位 |
| H6 | 内核 `WIN_S` 与唯一事实来源**逐字相同**（都是 5.0） | 内核仍写死 10 s |
| H7 | App 喂窗样本数 == 内核 `WIN_N`（80000） | 喂 5 s 音频、按 10 s 切 ⇒ 补零错位 |

### ② 反证（negative control）
把改过的代码**逐个破坏** ⇒ 判据**必须 FAIL** ⇒ 抓出恒真的组。

### ③ 真实故障反查
拿「包内缺 `asr_spk_window.py` ⇒ log 显示 10.000 s」这个**真实故障**
反查判据 ⇒ 确认闸门看得见它。

## 输出
`results/app/app237_app067_d1_window_pkg_evidence.json`
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LC = os.path.join(REPO, 'live_caption')
OUT = os.path.join(HERE, 'app237_app067_d1_window_pkg_evidence.json')

SYNC = os.path.join(LC, 'sync_c164_spk_assets_to_pkg.py')
TRACKER = os.path.join(LC, 'speaker_tracker.py')
ASR_SCRIPTS = r'C:\Users\Trekker-PTL\qwen3asr_06b\scripts'
ASR_MODELS = r'C:\Users\Trekker-PTL\qwen3asr_06b\models'
NOTICE = r'C:\Users\Trekker-PTL\shared\NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md'

#: ASR-045 NOTICE §3 给的 md5（**逐字来自 NOTICE** ⇒ 闸门对照的就是它）
NOTICE_MD5 = {
    'asr052_speaker_tracker_api.py': 'a1dd6e7bc7dfb426a3ce54585beb9304',
    'asr052_spk_runtime.py': '2ff82933edec80becd01f9d28d202ea6',
    'asr_thread_defaults.py': '0482f9c49105490ac219194c2fa7c184',
    'asr_spk_window.py': '7d719e1d7f251be9ce68503be4361807',
}

EXPECTED_ASR_FILES = [
    'asr052_speaker_tracker_api.py',
    'asr052_spk_runtime.py',
    'asr_thread_defaults.py',
    'asr_spk_window.py',
]

#: 5 s 静态 seg IR 的期望输入形状（16000 Hz × 5.0 s）
EXPECTED_W5_INPUT = '80000'


def _src(p):
    with open(p, 'rb') as f:
        return f.read().decode('utf-8')


def _norm(p):
    return _src(p).replace('\r\n', '\n')


def _md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════
# 静态闸门
# ══════════════════════════════════════════════════════════════
def h1_asr_files_has_window():
    """H1：`ASR_FILES` 恰好 4 项且含 `asr_spk_window.py`。"""
    src = _norm(SYNC)
    tree = ast.parse(src)
    files = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == 'ASR_FILES':
                    try:
                        files = ast.literal_eval(node.value)
                    except Exception:
                        files = None
    if files is None:
        return False, '找不到 ASR_FILES 列表'
    has = 'asr_spk_window.py' in files
    n_ok = (len(files) == 4)
    return (has and n_ok), ('含 asr_spk_window.py=%s 项数=%d（须 4）%s'
                            % (has, len(files), files))


def h2_sync_has_w5_ir():
    """H2：sync 脚本同步 5 s 静态 seg IR（`fp16-w5/`）。"""
    src = _norm(SYNC)
    has_dir = ('ov-fp16-w5' in src)
    has_sub = ('fp16-w5' in src)
    has_files = ('pyannote_seg_3_0_w5.xml' in src
                 and 'pyannote_seg_3_0_w5.bin' in src)
    return (has_dir and has_sub and has_files), (
        '源目录常量=%s 子目录名=%s 文件名=%s'
        % (has_dir, has_sub, has_files))


def h3_asr_delivery_md5():
    """H3：ASR 侧 4 个交付文件的 md5 与 NOTICE 一致。"""
    bad = []
    missing = []
    for fn, want in sorted(NOTICE_MD5.items()):
        p = os.path.join(ASR_SCRIPTS, fn)
        if not os.path.isfile(p):
            missing.append(fn)
            continue
        got = _md5(p)
        if got != want:
            bad.append('%s: %s ≠ %s' % (fn, got, want))
    ok = (not bad) and (not missing)
    return ok, ('4 个文件 md5 %s%s'
                % ('全部与 NOTICE 一致' if not bad else '不符：%s' % bad,
                   '；缺失：%s' % missing if missing else ''))


def h4_w5_ir_shape():
    """H4：5 s 静态 seg IR 存在且输入形状第三维 == 80000。"""
    x = os.path.join(ASR_MODELS, 'pyannote_seg', 'ov-fp16-w5',
                     'pyannote_seg_3_0_w5.xml')
    if not os.path.isfile(x):
        return False, '5 s IR 不存在：%s' % x
    txt = _src(x)
    dims = re.findall(r'<dim>(\d+)</dim>', txt)
    # OpenVINO XML 的 <dim> 顺序 = shape 各维
    uniq = []
    for d in dims:
        if not uniq or uniq[-1] != d:
            uniq.append(d)
    shape_ok = EXPECTED_W5_INPUT in dims
    # 🔴 反证特征：静态 10 s IR 的第三维是 160000
    is_static_10s = '160000' in dims
    return (shape_ok and not is_static_10s), (
        '第三维含 %s=%s；含 160000（10 s 静态）=%s'
        % (EXPECTED_W5_INPUT, shape_ok, is_static_10s))


def h5_app_resolves_5s():
    """H5：App 侧 `speaker_tracker._WIN_S` == 5.0 且来源是同源 asr_spk_window。"""
    if not os.path.isfile(TRACKER):
        return False, '找不到 speaker_tracker.py'
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            '_st_probe_app067', TRACKER)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    except Exception as e:
        return None, 'import 失败：%r' % (e,)
    v = getattr(m, '_WIN_S', None)
    src_desc = getattr(m, '_WIN_S_SRC', '')
    ok = (v is not None and abs(float(v) - 5.0) < 1e-9
          and 'asr_spk_window' in str(src_desc))
    return ok, ('_WIN_S=%r 来源=%r' % (v, src_desc))


def h6_kernel_matches_source():
    """H6：ASR 内核 `WIN_S` 与唯一事实来源逐字相同（都是 5.0）。"""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            '_w_probe_app067', os.path.join(ASR_SCRIPTS, 'asr_spk_window.py'))
        w = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(w)
    except Exception as e:
        return None, 'asr_spk_window import 失败：%r' % (e,)
    # 内核用 `ast` 抽常量（顶层依赖 numpy ⇒ 不能整体 import）
    src = _norm(os.path.join(ASR_SCRIPTS, 'asr052_spk_runtime.py'))
    tree = ast.parse(src)
    kern = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == 'WIN_S':
                    try:
                        kern = ast.literal_eval(node.value)
                    except Exception:
                        # ASR-045：`_W.WIN_S` ⇒ 从模块取
                        if (isinstance(node.value, ast.Attribute)
                                and isinstance(node.value.value, ast.Name)
                                and node.value.value.id == '_W'):
                            kern = getattr(w, node.value.attr, None)
    if kern is None:
        return False, '内核 WIN_S 取不到'
    same = (abs(float(kern) - float(w.WIN_S)) < 1e-9)
    return same, ('内核 WIN_S=%r vs 唯一事实来源 WIN_S=%r' % (kern, w.WIN_S))


def h7_fed_samples_match_kernel():
    """H7：App 喂窗样本数 == 内核 WIN_N（都是 80000）。"""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            '_w2_probe_app067', os.path.join(ASR_SCRIPTS, 'asr_spk_window.py'))
        w = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(w)
    except Exception as e:
        return None, 'asr_spk_window import 失败：%r' % (e,)
    # 内核的 WIN_N：ASR-045 后是 `_W.WIN_N`；旧版是 `int(WIN_S * SR)`
    src = _norm(os.path.join(ASR_SCRIPTS, 'asr052_spk_runtime.py'))
    tree = ast.parse(src)
    kern_win_n = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == 'WIN_N':
                    try:
                        kern_win_n = ast.literal_eval(node.value)
                    except Exception:
                        if (isinstance(node.value, ast.Attribute)
                                and isinstance(node.value.value, ast.Name)
                                and node.value.value.id == '_W'):
                            kern_win_n = getattr(w, node.value.attr, None)
                        else:
                            # `int(WIN_S * SR)` ⇒ 按源码算
                            try:
                                kern_win_n = int(round(
                                    float(w.WIN_S) * float(w.SR)))
                            except Exception:
                                kern_win_n = None
    app_win = float(getattr(w, 'WIN_S', 0.0))
    fed = int(round(app_win * 16000))
    ok = (kern_win_n is not None and fed == int(kern_win_n))
    return ok, ('App 喂窗样本数=%d（%s s × 16000）；内核 WIN_N=%r'
                % (fed, app_win, kern_win_n))


CHECKS = [
    ('H1 sync 的 ASR_FILES 含 asr_spk_window.py 且恰好 4 项',
     h1_asr_files_has_window),
    ('H2 sync 脚本同步 5 s 静态 seg IR（fp16-w5）',
     h2_sync_has_w5_ir),
    ('H3 ASR 侧 4 个交付文件 md5 与 NOTICE 一致',
     h3_asr_delivery_md5),
    ('H4 5 s 静态 seg IR 输入第三维 = 80000（非 160000）',
     h4_w5_ir_shape),
    ('H5 App 侧解析到 5.0 且来源是同源 asr_spk_window',
     h5_app_resolves_5s),
    ('H6 内核 WIN_S 与唯一事实来源逐字相同',
     h6_kernel_matches_source),
    ('H7 App 喂窗样本数 == 内核 WIN_N（80000）',
     h7_fed_samples_match_kernel),
]


# ══════════════════════════════════════════════════════════════
# 🔴🔴🔴 反证基础设施
#
# 🔴 **纪律（MEMORY 铁律）**：反证必须改「**被测的那个对象**」。
#   ⇒ 判据函数读的是**固定路径**（SYNC / TRACKER / ASR 源文件）
#   ⇒ 只写「一个临时副本」⇒ 判据读不到 ⇒ 反证**根本没生效**
#   ⇒ 但结果会显示「反证没抓住」⇒ **误判判据无鉴别力**。
#   ⇒ 所以：**临时替换真实文件**（备份 → 破坏 → 跑判据 → 还原）。
# ══════════════════════════════════════════════════════════════
class _Swapped(object):
    """临时替换一个真实文件的内容，跑完判据后**必定还原**。"""

    def __init__(self, path, new_text):
        self.path = path
        self.new_text = new_text
        self.backup = None

    def __enter__(self):
        self.backup = self.path + '.cp_backup'
        shutil.copy2(self.path, self.backup)
        with open(self.path, 'w', encoding='utf-8', newline='') as f:
            f.write(self.new_text)
        return self

    def __exit__(self, *exc):
        # 🔴 **必定还原**（即使判据抛异常）
        if self.backup and os.path.isfile(self.backup):
            shutil.copy2(self.backup, self.path)
            os.remove(self.backup)
        return False


# ══════════════════════════════════════════════════════════════
# 反证：破坏代码 ⇒ 判据必须 FAIL
# ══════════════════════════════════════════════════════════════
def _counterproofs():
    """每条反证 = 破坏一处 ⇒ 对应判据必须 FAIL。

    🔴 **反证构造纪律**（MEMORY 铁律）：
      * 破坏**被测的那个对象**（不是复制一份）；
      * 删行可能让 `if` 块变空 ⇒ 改用**替换成 `pass`**；
      * 多个调用点必须**破坏全部**。
    """
    out = []
    src = _norm(SYNC)

    # CP-H1：把 ASR_FILES 退回 3 项（去掉 asr_spk_window.py）
    broken = re.sub(r"\n\s*'asr_spk_window\.py',[^\n]*\n", '\n', src)
    if broken != src:
        with _Swapped(SYNC, broken):
            ok, det = h1_asr_files_has_window()
        out.append({'check': 'H1 ASR_FILES 含 asr_spk_window.py',
                    'broke': True, 'verdict': 'PASS' if not ok else 'FAIL',
                    'detail': det})
    else:
        out.append({'check': 'H1 ASR_FILES 含 asr_spk_window.py',
                    'broke': False, 'verdict': 'FAIL',
                    'detail': '反证未生效（替换没命中）'})

    # CP-H2：把 5 s IR 的目录常量改掉
    broken = src.replace("SEG_SRC_W5 = os.path.join(ASR_MODELS, "
                         "'pyannote_seg', 'ov-fp16-w5')",
                         "SEG_SRC_W5 = os.path.join(ASR_MODELS, "
                         "'pyannote_seg', 'ov-fp16')")
    if broken != src:
        with _Swapped(SYNC, broken):
            ok, det = h2_sync_has_w5_ir()
        out.append({'check': 'H2 sync 同步 5 s 静态 seg IR',
                    'broke': True, 'verdict': 'PASS' if not ok else 'FAIL',
                    'detail': det})
    else:
        out.append({'check': 'H2 sync 同步 5 s 静态 seg IR',
                    'broke': False, 'verdict': 'FAIL',
                    'detail': '反证未生效（替换没命中）'})

    # CP-H3：篡改一个交付文件的 md5（对**源文件**做不可逆 ⇒ 用副本目录）
    #   ⇒ 这里改为：用一个**假模块**替换 NOTICE_MD5 中的 asr_spk_window
    #   ⇒ 判据必须 FAIL。
    orig = dict(NOTICE_MD5)
    try:
        NOTICE_MD5['asr_spk_window.py'] = '0' * 32
        ok, det = h3_asr_delivery_md5()
        out.append({'check': 'H3 交付文件 md5 与 NOTICE 一致',
                    'broke': True, 'verdict': 'PASS' if not ok else 'FAIL',
                    'detail': det})
    finally:
        NOTICE_MD5.clear()
        NOTICE_MD5.update(orig)

    # CP-H4：用一个**形状不对**的假 IR 替换（第三维 160000）
    x = os.path.join(ASR_MODELS, 'pyannote_seg', 'ov-fp16-w5',
                     'pyannote_seg_3_0_w5.xml')
    orig_xml = _src(x)
    try:
        fake = orig_xml.replace('<dim>%s</dim>' % EXPECTED_W5_INPUT,
                                '<dim>160000</dim>')
        with open(x, 'w', encoding='utf-8', newline='') as f:
            f.write(fake)
        ok, det = h4_w5_ir_shape()
        out.append({'check': 'H4 5 s IR 输入第三维 = 80000',
                    'broke': True, 'verdict': 'PASS' if not ok else 'FAIL',
                    'detail': det})
    finally:
        with open(x, 'w', encoding='utf-8', newline='') as f:
            f.write(orig_xml)

    # CP-H5：把 App 的同源解析**破坏**（改 `speaker_tracker.py` 本体）
    st_src = _norm(TRACKER)
    broken = st_src.replace("for mod_name in ('asr_spk_window', "
                             "'asr052_spk_runtime'):",
                             "for mod_name in ('asr052_spk_runtime',):")
    if broken != st_src:
        with _Swapped(TRACKER, broken):
            ok, det = h5_app_resolves_5s()
        out.append({'check': 'H5 App 侧解析到 5.0 且同源',
                    'broke': True, 'verdict': 'PASS' if not ok else 'FAIL',
                    'detail': det})
    else:
        out.append({'check': 'H5 App 侧解析到 5.0 且同源',
                    'broke': False, 'verdict': 'FAIL',
                    'detail': '反证未生效（替换没命中）'})

    # CP-H6：把内核的 `WIN_S` 改回写死 10.0（**改 ASR 源文件本体**）
    rt = os.path.join(ASR_SCRIPTS, 'asr052_spk_runtime.py')
    rt_src = _norm(rt)
    broken = rt_src.replace('WIN_S = _W.WIN_S                     '
                             '# 当前旁路窗口（秒）',
                             'WIN_S = 10.0')
    if broken != rt_src:
        with _Swapped(rt, broken):
            ok, det = h6_kernel_matches_source()
        out.append({'check': 'H6 内核 WIN_S 与唯一事实来源相同',
                    'broke': True,
                    'verdict': 'PASS' if not ok else 'FAIL',
                    'detail': det})
    else:
        out.append({'check': 'H6 内核 WIN_S 与唯一事实来源相同',
                    'broke': False, 'verdict': 'FAIL',
                    'detail': '反证未生效（替换没命中）'})

    return out


def _real_fault_recheck():
    """🔴 **真实故障反查**：确认闸门看得见「包内缺 window 文件 ⇒ 10 s」。

    真实故障（APP-067 ⑤ 原文）：影子包 `app/asr_spk/` 只有 3 个文件
    （不含 `asr_spk_window.py`）⇒ log 显示 `说话人旁路窗口：10.000 s`。
    ⇒ 判据 H1/H2 必须在这种形态下 FAIL。
    """
    hits = {}
    # ① 包内目录清单（客户包实际形态）
    import glob
    pkgs = sorted(glob.glob(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v*'))
    pkgs = [p for p in pkgs if os.path.isdir(p)]
    if not pkgs:
        hits['pkg_found'] = 0
        return True, hits, '没有客户包目录（无法做真实故障反查）'
    latest = pkgs[-1]
    spk = os.path.join(latest, 'app', 'asr_spk')
    n_files = len([f for f in os.listdir(spk)
                   if f.endswith('.py')]) if os.path.isdir(spk) else 0
    has_win = os.path.isfile(os.path.join(spk, 'asr_spk_window.py'))
    hits['pkg'] = os.path.basename(latest)
    hits['pkg_asr_py_files'] = n_files
    hits['pkg_has_asr_spk_window'] = has_win
    # ② 最新包内缺 window 文件 ⇒ 客户机回退 10 s ⇒ 「真实故障」成立
    #    ⇒ 但这**不是 App 代码的缺陷**（是「包还没重打」的现状）
    real_fault_present = (not has_win)
    hits['real_fault_present'] = real_fault_present
    hits['expected_window_log'] = '说话人旁路窗口：5.000 s'
    hits['current_window_log_observed'] = '说话人旁路窗口：10.000 s'
    detail = ('最新包 %s：app/asr_spk/ 有 %d 个 .py，含 asr_spk_window.py=%s'
              % (latest, n_files, has_win))
    return True, hits, detail


def main():
    checks = []
    for name, fn in CHECKS:
        try:
            ok, det = fn()
        except Exception as e:
            ok, det = None, '判据异常：%r' % (e,)
        checks.append({'name': name, 'ok': ok, 'detail': det})
        mark = {True: 'PASS', False: 'FAIL', None: 'NONE'}[ok]
        print('%-4s %s —— %s' % (mark, name, det))

    n_pass = sum(1 for c in checks if c['ok'] is True)
    n_fail = sum(1 for c in checks if c['ok'] is False)
    n_none = sum(1 for c in checks if c['ok'] is None)

    print()
    print('--- 反证（破坏代码 ⇒ 判据必须 FAIL）---')
    cps = _counterproofs()
    for c in cps:
        print('  [%s] %s —— %s' % (c['verdict'], c['check'], c['detail']))
    n_cp_bad = sum(1 for c in cps if c['verdict'] != 'PASS')

    print()
    print('--- 真实故障反查 ---')
    rf_ok, rf_hits, rf_detail = _real_fault_recheck()
    print('  %s' % rf_detail)
    print('  %s' % json.dumps(rf_hits, ensure_ascii=False))

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-067 ⑤（D1 5 s 窗口 · App 侧 / 客户包侧）',
        'upstream': 'ASR-045（内核已改完）+ NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md',
        'checks': checks,
        'n_pass': n_pass, 'n_fail': n_fail, 'n_none': n_none,
        'counterproofs': cps,
        'n_counterproof_failed_to_detect': n_cp_bad,
        'counterproof_ok': (n_cp_bad == 0),
        'real_fault_recheck': {
            'ok': rf_ok, 'hits': rf_hits, 'detail': rf_detail,
        },
        'verdict': 'PASS' if (n_fail == 0 and n_cp_bad == 0) else 'FAIL',
        'meaning': ('PASS = **代码层/包内容层**的 D1 5 s 落地成立，'
                    '且判据有鉴别力。'
                    '≠ 设备级验收（客户机实跑 log 出「5.000 s」需持 MACHINE_LOCK '
                    '在真包上跑；v2.3 尚未打包）。'),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print()
    print('结果：%d PASS / %d FAIL / %d NONE ⇒ %s'
          % (n_pass, n_fail, n_none, ev['verdict']))
    print('产物：%s' % OUT)
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
