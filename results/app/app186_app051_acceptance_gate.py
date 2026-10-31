#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app186 —— APP-051② / APP-043：**真机验收总闸门**（汇总 5 项子验收）。

🔴🔴🔴 **为什么必须有这个脚本（而不是「看一眼证据就写 ACCEPTED.json」）**：
  APP-051② 要求「**接着做 APP-043 真机验收** …；**验收通过后**写 ACCEPTED.json」。
  ⇒ 「验收通过」必须有**一个明确的判据**，而不是**人工印象**。
  ⇒ 本脚本把 APP-043 的 5 个子项各自已有的**落盘证据**收上来，
    逐项核对「证据存在 + verdict=PASS + 指向的是 **v1.13 包**」，
    **全部通过才给出 `accepted=true`**。

🔴 **纪律**：**纯离线**（只读各证据 JSON）⇒ 不占机器锁、不跑推理、不碰 GPU。

## APP-043 / APP-051② 的 5 个子项与对应证据
  ① pythonw.exe 冷启动（用户启动方式）
     → `results/app/app181_pythonw_coldstart_v2_evidence.json`
  ② SPE Q&A 双说话人克隆（按句绑定 spk）
     → `results/app/app175_app043_clone_acceptance_evidence.json`
  ③ GUI 加速播放（APP-042 自适应加速，接通 + 公式自洽）
     → `results/app/app179_app042_gui_accel_evidence.json`（链路）
       `results/app/app183_app042_formula_evidence.json`（公式）
  ④ APP-048 状态栏两种分辨率截图
     → `results/app/app185_app048_gui_layout_pkg_evidence.json`（**在 v1.13 包内跑**）
  ⑤ 3 段 1.2–1.3× 配音实听素材
     → `results/app/app184_app051_accel_listen_manifest.json`

🔴 **「在目标包上跑」是硬要求**：
  ① ③ ④ 的证据里都有 `pkg` 字段 ⇒ 必须指向**本次验收的那个包目录**
  （由 `pkg_paths` 自动发现的最大版本包，不写死版本号 ⇒ §48）。
  ⚠️ `app165`（旧）跑的是**仓库**源码 ⇒ 不算 ⇒ 用 `app185`。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HOME = os.path.expanduser('~')
REPO = os.path.join(HOME, 'confucius4-openvino')
EV = os.path.join(REPO, 'results', 'app')

# 🔴🔴 §48：**包目录/版本号一律走单一数据源**，不写死版本
#    ⇒ 写死会在升版后指着旧包跑 ⇒ 报出假回归（§47.6 事故）。
#    ⇒ `--pkg` 可显式指定；不给则由 `pkg_paths` 自动发现**最大版本**的包。
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import pkg_paths as _pkg_paths  # noqa: E402  §48 单一数据源

#: 默认包目录（可被 `--pkg` 覆盖）：由 `pkg_paths` 发现，**不写死版本号**
PKG_DIR = ''
PKG_VER = ''

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:600]})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  —— %s' % detail) if detail else ''))
    return ok


def load(name):
    p = os.path.join(EV, name)
    if not os.path.isfile(p):
        return None, p
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f), p
    except Exception:
        return None, p


def on_pkg(ev, key='pkg'):
    """证据里的包路径是否指向**本次验收的那个包**（按目录名精确比对）。

    🔴 用**目录名精确相等**，不用子串包含 ⇒ 免得「v1.13 的路径里含 v1.3」
    这类前缀误判（`in` 判据会把 `..._v1.3` 当成含 `..._v1.13`）。
    """
    if not isinstance(ev, dict):
        return False, '证据不是 dict'
    v = ev.get(key)
    if not v:
        return False, '证据里没有 %r 字段' % key
    want = os.path.basename(os.path.normpath(PKG_DIR)).lower()
    got = os.path.basename(os.path.normpath(str(v))).lower()
    # 🔴 证据里可能记的是**包根**（`..._v1.13`）也可能是**包内 app 目录**
    #    （`..._v1.13/app`）⇒ 两种都算指向同一个包。
    ok = (want == got
          or got == want + os.sep + 'app'
          or got == want + '/app')
    return ok, '%s = %s（期望包目录名 = %s）' % (key, v, want)


def main():
    # 🔴 `EV` 在下面 `--out` 的默认参数里已被使用 ⇒ `global` 必须**先于**它
    global EV, PKG_DIR, PKG_VER
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None,
                    help='客户包目录（默认由 pkg_paths 自动发现**最大版本**的包）')
    ap.add_argument('--ev', default=None,
                    help='证据目录（默认 results/app）⇒ 供**鉴别力实测**在'
                         '临时副本上跑同一判据（注入已知缺陷必须 FAIL）')
    ap.add_argument('--out', default=os.path.join(EV, 'app186_app051_acceptance_gate_evidence.json'))
    ap.add_argument('--write-accepted', action='store_true',
                    help='验收通过时，往**包目录**写 ACCEPTED.json（APP-045② 的门）')
    args = ap.parse_args()

    # 🔴 证据目录可覆盖（鉴别力实测用）⇒ 必须在 `load()` 生效前改掉模块级 EV
    if args.ev:
        EV = os.path.abspath(args.ev)

    # 🔴 包目录定案：显式 `--pkg` > 环境变量 > 自动发现（§48 单一数据源）
    PKG_DIR = _pkg_paths.resolve_pkg_dir(args.pkg)
    if not os.path.isdir(os.path.join(PKG_DIR, 'app')):
        print('!! 客户包目录无效（缺 app/）：%s' % PKG_DIR)
        return 2
    _m = re.search(r'_v(\d+(?:\.\d+)*)$', os.path.basename(os.path.normpath(PKG_DIR)))
    PKG_VER = _m.group(1) if _m else _pkg_paths.pkg_version()

    print('=' * 70)
    print('APP-051② / APP-043 真机验收总闸门（目标包 v%s）' % PKG_VER)
    print('=' * 70)

    items = []

    # ── ① pythonw 冷启动 ───────────────────────────────────────────
    ev, p = load('app181_pythonw_coldstart_v2_evidence.json')
    ok1 = check('① pythonw 冷启动证据存在', ev is not None, p)
    if ok1:
        ok1 &= check('① pythonw 冷启动 verdict=PASS',
                     ev.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev.get('verdict'),
                                                       ev.get('n_pass'),
                                                       ev.get('n_fail')))
        o, d = on_pkg(ev)
        ok1 &= check('① pythonw 冷启动跑在 **v%s 包**上' % PKG_VER, o, d)
        obs = ev.get('observations') or []
        ok1 &= check('① 两次独立冷启动（cold1/cold2）都截到**有内容的客户区**',
                     len(obs) >= 2 and all(
                         (o2.get('shot_stats') or {}).get('client_n_colors', 0) >= 8
                         for o2 in obs),
                     'client_n_colors = %r' % [((o2.get('shot_stats') or {})
                                               .get('client_n_colors'))
                                              for o2 in obs])
    items.append(('pythonw_coldstart', ev))

    # ── ② SPE Q&A 双说话人克隆 ─────────────────────────────────────
    ev2, p2 = load('app175_app043_clone_acceptance_evidence.json')
    ok2 = check('② SPE Q&A 双说话人克隆证据存在', ev2 is not None, p2)
    if ok2:
        ok2 &= check('② 克隆验收 verdict=PASS',
                     ev2.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev2.get('verdict'),
                                                        ev2.get('n_pass'),
                                                        ev2.get('n_fail')))
        o, d = on_pkg(ev2)
        ok2 &= check('② 克隆验收跑在 **v%s 包**上' % PKG_VER, o, d)
        inv = ev2.get('n_played', 0) + ev2.get('n_dropped', 0) == ev2.get('n_submitted', -1)
        ok2 &= check('② 不变式 n_played + n_dropped == n_submitted', inv,
                     '%s + %s == %s' % (ev2.get('n_played'), ev2.get('n_dropped'),
                                        ev2.get('n_submitted')))
        ok2 &= check('② 有句子真的用了**克隆音色**（voice_kind=clone）',
                     (ev2.get('n_clone_rows') or 0) > 0,
                     'n_clone_rows = %r' % ev2.get('n_clone_rows'))
        ok2 &= check('② 有**按句绑定**的 spk 标签（voice_spk）',
                     (ev2.get('n_spk_tagged_lines') or 0) > 0,
                     'n_spk_tagged_lines = %r' % ev2.get('n_spk_tagged_lines'))
    items.append(('spe_qa_clone', ev2))

    # ── ③ GUI 加速播放（链路 + 公式）───────────────────────────────
    ev3, p3 = load('app179_app042_gui_accel_evidence.json')
    ok3 = check('③ GUI 加速播放（链路）证据存在', ev3 is not None, p3)
    if ok3:
        ok3 &= check('③ GUI 加速链路 verdict=PASS',
                     ev3.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev3.get('verdict'),
                                                        ev3.get('n_pass'),
                                                        ev3.get('n_fail')))
        o, d = on_pkg(ev3)
        ok3 &= check('③ GUI 加速跑在 **v%s 包**上' % PKG_VER, o, d)
        ok3 &= check('③ 真的触发了加速（speed>1.0 的句子存在）',
                     (ev3.get('n_accel_rows') or 0) > 0,
                     'n_accel_rows = %r / rows = %r' % (ev3.get('n_accel_rows'),
                                                        ev3.get('n_rows')))
    ev3f, p3f = load('app183_app042_formula_evidence.json')
    ok3 &= check('③ 加速倍率**公式一致性**证据存在（app183）', ev3f is not None, p3f)
    if ev3f:
        ok3 &= check('③ 公式一致性 verdict=PASS',
                     ev3f.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev3f.get('verdict'),
                                                        ev3f.get('n_pass'),
                                                        ev3f.get('n_fail')))
    items.append(('gui_accel', ev3))

    # ── ④ APP-048 两种分辨率截图（**必须在包内跑**）─────────────────
    ev4, p4 = load('app185_app048_gui_layout_pkg_evidence.json')
    ok4 = check('④ APP-048 分辨率截图证据存在（包内跑的 app185）',
                ev4 is not None, p4)
    if ok4:
        ok4 &= check('④ 布局验收 verdict=PASS',
                     ev4.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev4.get('verdict'),
                                                        ev4.get('n_pass'),
                                                        ev4.get('n_fail')))
        # 🔴 `pkg_under_test` 记的是**包内 app 目录**（`<pkg>/app`）
        #    ⇒ 必须比对它的**父目录**（= 包根），否则直接比 basename 会不相等。
        _put = str(ev4.get('pkg_under_test', ''))
        _put_pkg_root = os.path.dirname(os.path.normpath(_put))
        ok4 &= check('④ **跑在客户包内代码**上（不是仓库源码）',
                     os.path.basename(_put_pkg_root).lower()
                     == os.path.basename(os.path.normpath(PKG_DIR)).lower(),
                     'pkg_under_test = %r（其包根 = %r）' % (_put, _put_pkg_root))
        shots = ev4.get('shots') or []
        names = [os.path.basename(str(s.get('path', ''))) for s in shots]
        ok4 &= check('④ 两种分辨率截图都在（1920×1080 / 1280×720）',
                     'app048_layout_1920x1080.png' in names
                     and 'app048_layout_1280x720.png' in names,
                     'shots = %r' % names)
        ok4 &= check('④ 失败态与正常态**像素级不同**（不是同一张图）',
                     (ev4.get('diff_pixels_normal_vs_failed') or 0) > 0,
                     'diff_px = %r' % ev4.get('diff_pixels_normal_vs_failed'))
    items.append(('gui_layout_2res', ev4))

    # ── ⑤ 3 段 1.2–1.3× 配音实听素材 ──────────────────────────────
    ev5, p5 = load('app184_app051_accel_listen_manifest.json')
    ok5 = check('⑤ 1.2–1.3× 实听素材证据存在', ev5 is not None, p5)
    if ok5:
        ok5 &= check('⑤ 实听素材 verdict=PASS', ev5.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev5.get('verdict'),
                                                        ev5.get('n_pass'),
                                                        ev5.get('n_fail')))
        clips = ev5.get('clips') or []
        ok5 &= check('⑤ 切出 ≥3 段且含 1.2× 与 1.3×',
                     len(clips) >= 3
                     and any(abs(c.get('speed', 0) - 1.2) < 1e-6 for c in clips)
                     and any(abs(c.get('speed', 0) - 1.3) < 1e-6 for c in clips),
                     'speeds = %r' % [c.get('speed') for c in clips])
        # 🔴 文件必须**真实存在**且字节数 > 0（MEMORY：没落盘的东西不能写「已交付」）
        all_exist = True
        for c in clips:
            fp = os.path.join(ev5.get('listen_dir', ''), c.get('file', ''))
            if not (os.path.isfile(fp) and os.path.getsize(fp) == c.get('bytes')):
                all_exist = False
        ok5 &= check('⑤ 每段 wav **真实落盘**且字节数与 manifest 一致',
                     all_exist, 'clips = %d' % len(clips))
    items.append(('accel_listen', ev5))

    # ── 总判定 ─────────────────────────────────────────────────────
    overall = all([ok1, ok2, ok3, ok4, ok5])
    print('\n' + '=' * 70)
    print('子项：①pythonw=%s ②克隆=%s ③加速=%s ④分辨率=%s ⑤实听=%s'
          % (ok1, ok2, ok3, ok4, ok5))
    print('PASS %d  FAIL %d  verdict=%s'
          % (PASS, FAIL, 'PASS' if overall else 'FAIL'))
    print('=' * 70)

    accepted = bool(overall and FAIL == 0)

    result = {
        'script': os.path.basename(__file__),
        'correction': 'APP-051② / APP-043（真机验收总闸门）',
        'pkg_dir': PKG_DIR,
        'pkg_version': PKG_VER,
        'sub_items': {
            '1_pythonw_coldstart': bool(ok1),
            '2_spe_qa_clone': bool(ok2),
            '3_gui_accel': bool(ok3),
            '4_gui_layout_2res': bool(ok4),
            '5_accel_listen_1.2_1.3': bool(ok5),
        },
        'checks': CHECKS, 'n_pass': PASS, 'n_fail': FAIL,
        'accepted': accepted,
        'verdict': 'PASS' if accepted else 'FAIL',
        'note': '「accepted」= 5 个子项**全部**证据存在 + verdict=PASS + '
                '指向 v%s 包；**音质/不变调/可懂仍由用户实听 + reviewer 判定**' % PKG_VER,
    }

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print('[evidence] %s' % args.out)

    if args.write_accepted and accepted:
        import datetime
        acc_path = os.path.join(PKG_DIR, 'ACCEPTED.json')
        payload = {
            'accepted': True,
            'version': PKG_VER,
            'pkg_dir': PKG_DIR,
            # 🔴 时间用**实测值**（不推算）
            'accepted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'corrections': ['APP-043', 'APP-045', 'APP-048', 'APP-051'],
            'evidence': {
                'gate': os.path.basename(args.out),
                'pythonw_coldstart': 'results/app/app181_pythonw_coldstart_v2_evidence.json',
                'spe_qa_clone': 'results/app/app175_app043_clone_acceptance_evidence.json',
                'gui_accel': 'results/app/app179_app042_gui_accel_evidence.json',
                'gui_accel_formula': 'results/app/app183_app042_formula_evidence.json',
                'gui_layout_2res': 'results/app/app185_app048_gui_layout_pkg_evidence.json',
                'accel_listen': 'results/app/app184_app051_accel_listen_manifest.json',
            },
            'scope': '链路 + 结构 + 数字自洽；**音质/不变调/可懂由用户实听与 reviewer 判定**',
        }
        with open(acc_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print('[accepted] 已写 %s（%d B）' % (acc_path, os.path.getsize(acc_path)))
    elif args.write_accepted:
        print('[accepted] 🔴 验收未全部通过 ⇒ **不写** ACCEPTED.json')

    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
