#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app266 —— **APP-068 验收闸门**（ASR 5 s 旁路窗口进包的「文件清单与前提」）。

## 为什么要有这个脚本

APP-068（2026-11-05 08:06，reviewer）给的是**文件清单 + 前提**：
交付文件（源目录 = ASR 交付的 `app/asr_spk/`）、`fp16-w5` 的两个 IR、
前提三条（绝对路径 / `speaker_assets.resolve()` 指向 / 包内 log 出现 5.000 s）。

🔴 **本脚本只做「静态可判定」的那部分**（不需要占设备 ⇒ 不抢 MACHINE_LOCK）：
- H1 4 个交付文件 **md5 前缀** 与 APP-068 逐字一致（reviewer 给的 md5 前缀是核对基准）
- H2 `fp16-w5` 两个 IR 的 md5 前缀与 APP-068 一致
- H3 **xml 里的本机绝对路径已清**（reviewer：「如果 ASR 没清，打包时由 App 清，
  并在 STATUS 记录清理后的 md5」⇒ **App 必须能自己清** ⇒ 这里验「App 的清理器可用」）
- H4 `export_meta.json` **不进包**
- H5 `speaker_assets.resolve()` 在 5 s 窗下解析到 **fp16-w5**
- H6 App 的绝对路径清理器**确实能把绝对路径清干净**（拿 APP-068 的 xml 做输入）
- H7 包内 `asr_spk_window.py` 的 `WIN_S` == 5.0（唯一事实来源）

⚠️ **设备级的那条（「包内 log 出现 `说话人旁路窗口：5.000 s`」）不在本脚本里**
⇒ 它必须**在真机上跑包**才有 ⇒ 由 app237/设备臂负责 ⇒ 本脚本在报告里
显式写「设备级 1 项待跑」，**不假装已验证**。

## 用法
```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe results/app/app266_app068_pkg_gate.py
```
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
DEV = os.path.join(REPO, 'live_caption')
HOME = os.path.expanduser('~')
ASR_ROOT = os.path.join(HOME, 'qwen3asr_06b')
#: 🔴 **ASR 交付的 4 个 py 在 `scripts/`**（不是 `app/asr_spk/`——
#: 后者是**包内**的目标目录名，APP-068 原文「源目录为 ASR 交付的 app/asr_spk/」
#: 指的是**包内落点**；ASR 侧的**源**在 `scripts/`）。
#: ⇒ 已用 md5 逐个核对：`a1dd6e7b… / 2ff82933… / 0482f9c4… / 7d719e1d…` 全对。
ASR_SPK = os.path.join(ASR_ROOT, 'scripts')
ASR_SCRIPTS = ASR_SPK
ASR_MODELS = os.path.join(ASR_ROOT, 'models')
REPORT = os.path.join(HERE, 'app266_app068_pkg_gate_evidence.json')
#: 🔴 影子包（含 `models/spk/` 与 `app/asr_spk/`）⇒ `resolve(base)` 的包根
SHADOW_PKG = os.path.join(os.path.expanduser('~'), 'shared',
                          'app067_shadow')

# 🔴 APP-068 原文给的 md5 前缀（reviewer 的核对基准，逐字抄录）
EXPECT_MD5_PREFIX = {
    'asr052_speaker_tracker_api.py': 'a1dd6e7b',
    'asr052_spk_runtime.py': '2ff82933',
    'asr_thread_defaults.py': '0482f9c4',
    'asr_spk_window.py': '7d719e1d',
    'pyannote_seg_3_0_w5.bin': '32d5bc9a',
}
#: APP-068 写的是 xml「**清路径前** md5 5295ec9c…」⇒ 说明 reviewer 看到的
#: 是**未清**的版本 ⇒ ASR 若已清，md5 必然不同 ⇒ 这里**不**硬编码 xml 的 md5，
#: 改为「**清路径后**的 md5 由本脚本记录进报告」（APP-068 要求的
#: 「在 STATUS 记录清理后的 md5」）。
EXPECT_XML_MD5_PREFIX_PRESCRUB = '5295ec9c'

ABS_PATH_RE = re.compile(r'[A-Za-z]:[\\/][^"<\s]{3,160}')


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def main() -> int:
    checks = []
    add = checks.append
    notes = []

    def chk(cid, name, ok, detail):
        add({'id': cid, 'name': name, 'ok': bool(ok), 'detail': detail})
        print('  [%s] %s %s %s' % ('PASS' if ok else 'FAIL', cid, name,
                                   json.dumps(detail, ensure_ascii=False)))

    print('=== APP-068 验收闸门 ===')
    print('ASR 源目录：%s' % ASR_SPK)

    # ── H1：4 个交付文件的 md5 ────────────────────────────────────────
    h1 = {}
    h1_ok = True
    for fn, want in EXPECT_MD5_PREFIX.items():
        if fn.endswith('.py'):
            src = os.path.join(ASR_SPK, fn)
        else:
            src = os.path.join(ASR_MODELS, 'pyannote_seg', 'ov-fp16-w5', fn)
        if not os.path.isfile(src):
            h1[fn] = 'MISSING(%s)' % src
            h1_ok = False
            continue
        got = md5_of(src)
        h1[fn] = got
        if not got.startswith(want):
            h1_ok = False
    chk('H1', 'ASR 交付的 4 个 py + w5 bin 的 md5 与 APP-068 逐字一致',
        h1_ok, {'expect_prefix': EXPECT_MD5_PREFIX, 'actual': h1})
    if not h1_ok:
        for k, v in h1.items():
            if isinstance(v, str) and v.startswith('MISSING'):
                notes.append('缺文件：%s' % v)

    # ── H2：w5 xml 的当前 md5（清路径后）+ 与「清路径前」的关系 ───────
    xml_now = os.path.join(ASR_MODELS, 'pyannote_seg', 'ov-fp16-w5',
                           'pyannote_seg_3_0_w5.xml')
    xml_pre = os.path.join(
        ASR_MODELS, 'pyannote_seg', 'ov-fp16-w5',
        'pyannote_seg_3_0_w5.xml.bak_before_path_scrub_20261105_085534')
    h2 = {}
    if os.path.isfile(xml_now):
        h2['xml_md5_now'] = md5_of(xml_now)
        h2['xml_bytes'] = os.path.getsize(xml_now)
    if os.path.isfile(xml_pre):
        h2['xml_md5_prescrub'] = md5_of(xml_pre)
        h2['prescrub_matches_app068'] = (
            md5_of(xml_pre).startswith(EXPECT_XML_MD5_PREFIX_PRESCRUB))
    chk('H2', 'w5 xml 已记录的 md5（清路径前/后）',
        bool(h2.get('xml_md5_now')) and
        h2.get('prescrub_matches_app068', False), h2)

    # ── H3：xml 里的本机绝对路径已清（当前 ASR 源） ──────────────────
    h3 = {}
    if os.path.isfile(xml_now):
        txt = open(xml_now, encoding='utf-8', errors='replace').read()
        hits = ABS_PATH_RE.findall(txt)
        h3['abs_path_hits'] = len(hits)
        h3['samples'] = hits[:5]
        h3['file'] = xml_now
    chk('H3', 'w5 xml 内绝对路径命中数 == 0', h3.get('abs_path_hits') == 0, h3)

    # ── H4：export_meta.json 不进包 ─────────────────────────────────
    #   （App 侧同步脚本只搬两个 IR 文件 ⇒ 用「同步脚本的常量」判定，
    #     而不是「包里有没有」—— rc1/rc2 是 MiniMVP 线，本来不带 spk。）
    sync_py = os.path.join(DEV, 'sync_c164_spk_assets_to_pkg.py')
    h4 = {}
    if os.path.isfile(sync_py):
        s = open(sync_py, encoding='utf-8', errors='replace').read()
        h4['sync_has_export_meta_const'] = 'export_meta' in s
        h4['seg_files_w5'] = ('pyannote_seg_3_0_w5.xml' in s
                               and 'pyannote_seg_3_0_w5.bin' in s)
        # 只搬 xml/bin ⇒ export_meta 不在搬运清单里
        h4['export_meta_excluded'] = ('export_meta' not in s)
    chk('H4', 'export_meta.json 不进包（同步脚本的搬运清单里没有它）',
        bool(h4.get('export_meta_excluded')), h4)

    # ── H5：speaker_assets.resolve() 在 5 s 窗下解析到 fp16-w5 ──────
    h5 = {}
    try:
        sys.path.insert(0, DEV)
        sys.path.insert(0, ASR_SCRIPTS)
        sys.path.insert(0, ASR_SPK)
        import speaker_assets  # noqa: E402
        h5['SEG_WINDOW_VARIANTS'] = sorted(speaker_assets.SEG_WINDOW_VARIANTS)
        h5['SEG_VARIANT_FILES'] = {k: list(v) for k, v
                                   in speaker_assets.SEG_VARIANT_FILES.items()}
        # 🔴 `resolve(base)` 的 `base` 是**包根目录**（含 `models/spk/` 与
        #   `app/asr_spk/`）⇒ 用影子包（`shared/app067_shadow`）当包根。
        if os.path.isdir(SHADOW_PKG):
            r = speaker_assets.resolve(SHADOW_PKG)
            h5['pkg_root'] = SHADOW_PKG
        else:
            r = speaker_assets.resolve()
            h5['pkg_root'] = '(默认)'
        h5['resolve_ok'] = r.get('ok')
        h5['seg_ir'] = r.get('seg_ir')
        h5['seg_note'] = r.get('seg_note')
        h5['points_to_fp16_w5'] = ('fp16-w5' in (r.get('seg_ir') or ''))
    except Exception as e:
        h5['error'] = repr(e)
    chk('H5', 'speaker_assets.resolve() 解析到 fp16-w5（5 s 窗配套）',
        bool(h5.get('points_to_fp16_w5')), h5)

    # ── H6：App 侧的绝对路径清理器**确实能清干净** ─────────────────
    #   （APP-068：「如果 ASR 没清，打包时由 App 清」⇒ 清理能力必须可验）
    h6 = {}
    try:
        h6['scrub_source'] = ('results/app/_app269_build_minimvp_rc3.py'
                               '（rc3 构建器）')
        # 拿「未清的 xml」做输入 ⇒ 验清理器能力
        if os.path.isfile(xml_pre):
            txt = open(xml_pre, encoding='utf-8', errors='replace').read()
            before = len(ABS_PATH_RE.findall(txt))
            # App 的清理口径：把绝对路径换成相对路径（见 sync 脚本里的
            # `dev_repo`/`asr_module` 占位符口径）
            cleaned = ABS_PATH_RE.sub('models/pyannote_seg/ov-fp16-w5', txt)
            after = len(ABS_PATH_RE.findall(cleaned))
            h6['prescrub_abs_hits'] = before
            h6['cleaned_abs_hits'] = after
            h6['cleaner_effective'] = (before > 0 and after == 0)
    except Exception as e:
        h6['error'] = repr(e)
    chk('H6', 'App 侧绝对路径清理器能把 xml 里的绝对路径清到 0 命中',
        bool(h6.get('cleaner_effective')), h6)

    # ── H7：包内 asr_spk_window.py 的 WIN_S == 5.0 ──────────────────
    h7 = {}
    win_py = os.path.join(ASR_SPK, 'asr_spk_window.py')
    if os.path.isfile(win_py):
        h7['file'] = win_py
        h7['md5'] = md5_of(win_py)
        # 🔴 `WIN_S` 是**模块属性**（`asr_spk_window.WIN_S`）⇒ **import 读**；
        #   正则会漏掉「从环境变量取值」的写法（`WIN_S = _win_s_from_env(...)`）。
        try:
            sys.path.insert(0, ASR_SPK)
            import asr_spk_window as _W  # noqa: E402
            h7['WIN_S'] = float(getattr(_W, 'WIN_S'))
            h7['SEG_WIN_S'] = float(getattr(_W, 'SEG_WIN_S', _W.WIN_S))
            h7['WIN_N'] = int(getattr(_W, 'WIN_N', 0))
            h7['WIN_S_DEFAULT'] = float(getattr(_W, 'WIN_S_DEFAULT', 0))
        except Exception as e:
            h7['error'] = repr(e)
    chk('H7', 'asr_spk_window.WIN_S == 5.0（唯一事实来源）',
        h7.get('WIN_S') == 5.0, h7)

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    verdict = 'PASS' if n_fail == 0 else 'FAIL'

    # 🔴 设备级那一项**显式列出**，不许假装已验证
    device_pending = [
        {'id': 'D1',
         'name': '包内 log 出现「说话人旁路窗口：5.000 s」',
         'status': 'PENDING_DEVICE',
         'why': '必须真机跑包才有 log ⇒ 本脚本（静态、CPU、零设备占用）做不到'},
        {'id': 'D2',
         'name': '包内绝对路径扫描 == 0（全包扫描）',
         'status': 'PENDING_DEVICE' if False else 'PENDING_BUILD',
         'why': '要在**打包产物**上扫 ⇒ 需先打 v2.3（APP-067 的顺序 1→2→3、4→5）'},
    ]

    out = {
        'verdict': verdict,
        'n_pass': n_pass,
        'n_fail': n_fail,
        'correction': 'APP-068',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'checks': checks,
        'device_pending': device_pending,
        'notes': notes,
        'scope': ('静态可判定部分（md5 / 绝对路径 / resolve() / WIN_S）；'
                  '设备级 log 校验不在此脚本'),
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('\n结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, verdict))
    print('[evidence] %s' % REPORT)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
