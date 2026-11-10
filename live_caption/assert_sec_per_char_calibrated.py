# -*- coding: utf-8 -*-
"""assert_sec_per_char_calibrated —— APP-097 §2-4「`_SEC_PER_CHAR` 实测校准」静态闸门。

## 为什么需要这道闸门（背景）
reviewer APP-097 §2.4 明文：「每种语言报『合成时长 ÷ 字符数』的 p50，**用它定 `_SEC_PER_CHAR`**。」
§1.1 明文：「给 6 种新语言加上每字符秒数（**先用 en 的 0.07 当初值**，按第 2 节第 4 条实测校准）。」

⇒ 6 种新语言（de/fr/es/pt/it/ru）的 `_SEC_PER_CHAR` 必须是**实测校准值**，
   而不是 en 的占位初值 0.07。
🔴 历史缺陷：初值偏小 ⇒ 失控守卫（RUNAWAY `max(3×est, est+8)`）阈值偏低
   ⇒ **可能误杀正常长句**（代码原注释自己写明「实测校准前，这 6 种语言只用于目标语言选择」）。

## 判据（纯 CPU 静态检查：不加载模型、不占 GPU/NPU ⇒ 不需要 MACHINE_LOCK）
- **A 组（值来源正确）**：6 个新值 == 由**已落盘证据** `results/app/app326_app097_lang_out/tts.json`
  复算出的 `ceil3(max(preset_p50, clone_p50))`（不手抄数字 ⇒ 证据改了闸门会跟着变）。
- **B 组（未被误改）**：zh/en/ja/ko 四个既有值**逐字未变**（APP-030② 参考值）。
- **C 组（表形状）**：键集合恰为 10 个（4 + 6），无多余/缺失。
- **D 组（保守性）**：6 个新值**都不低于**占位初值 0.07 ⇒ 守卫阈值只会变松、不会变紧
  ⇒ 绝不会比校准前更容易误杀正常长句。
- **E 组（别名/全称口径未破）**：`_lang_key('german')` 等别名仍归一到规范小写代号
  ⇒ 别名取到的是**同一个**校准值（不是 en 的 0.07）。
- **F 组（反证组）**：把 6 个新值**改回 0.07** ⇒ A 组必须 FAIL；
  把某个新值**改成别的数** ⇒ A 组必须 FAIL。⇒ 证明闸门有鉴别力，不是恒真。

## 用法
    <python> live_caption/assert_sec_per_char_calibrated.py
    APP427_EVID=<out.json> <python> live_caption/assert_sec_per_char_calibrated.py
"""
from __future__ import annotations

import ast
import json
import math
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(HERE, 'tts_engine.py')
EVIDENCE = os.path.join(REPO, 'results', 'app', 'app326_app097_lang_out', 'tts.json')
OUT = os.environ.get('APP427_EVID') or os.path.join(
    REPO, 'results', 'app', 'assert_sec_per_char_calibrated.json')

NEW_LANGS = ('de', 'fr', 'es', 'pt', 'it', 'ru')
KEEP = {'zh': 0.25, 'ja': 0.15, 'ko': 0.18, 'en': 0.07}
PLACEHOLDER = 0.07


def load_ns(src: str) -> dict:
    """🔴 **不 import** 被测模块 ⇒ `ast` 直读表 + 抽函数 `exec`（不触发重依赖）。"""
    tree = ast.parse(src)
    ns: dict = {}
    mod = ast.Module(body=[], type_ignores=[])
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                # 🔴 `LANG_MAP` 必须一起抽出来：`_lang_key()` 内部要用它做别名归一
                #    （漏抽 ⇒ NameError ⇒ E 组假 FAIL）
                if isinstance(t, ast.Name) and t.id in (
                        '_SEC_PER_CHAR', '_LANG_TAIL_S', 'LANG_MAP', '_CANON'):
                    try:
                        ns[t.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
        elif isinstance(node, ast.FunctionDef) and node.name in (
                'map_language', '_lang_key', 'estimate_sec', 'estimate_frames',
                'clamp_max_new_tokens'):
            node.decorator_list = []
            mod.body.append(node)
    exec(compile(mod, SRC, 'exec'), ns)
    return ns


def expected_values(evidence: dict) -> dict:
    """从已落盘证据复算期望值（**不手抄**）。"""
    out = {}
    for lang in NEW_LANGS:
        p50 = {}
        for voice in ('preset', 'clone'):
            rows = evidence['per_lang'][lang][voice]['rows']
            ratios = [r['out_dur_s'] / r['n_chars'] for r in rows if r.get('n_chars')]
            p50[voice] = statistics.median(ratios)
        mx = max(p50['preset'], p50['clone'])
        out[lang] = math.ceil(mx * 1000) / 1000.0
    return out


def run_checks(ns: dict, expect: dict, label: str) -> list:
    checks = []

    def chk(cid, group, name, ok, got, want):
        checks.append(dict(id=cid, group=group, name=name, ok=bool(ok),
                           got=got, want=want))

    tbl = ns['_SEC_PER_CHAR']

    # ── A 组：值 == 证据复算值 ──
    for lang in NEW_LANGS:
        chk('A-' + lang, 'A', 'sec_per_char[%s] == 实测校准值' % lang,
            tbl.get(lang) == expect[lang], tbl.get(lang), expect[lang])

    # ── B 组：既有 4 语言未变 ──
    for lang, want in KEEP.items():
        chk('B-' + lang, 'B', 'sec_per_char[%s] 未变' % lang,
            tbl.get(lang) == want, tbl.get(lang), want)

    # ── C 组：表形状 ──
    chk('C1', 'C', '键集合 == 4 既有 + 6 新增',
        set(tbl) == set(KEEP) | set(NEW_LANGS), sorted(tbl),
        sorted(set(KEEP) | set(NEW_LANGS)))
    chk('C2', 'C', '无 4 语言之外的额外键',
        all(v is not None for v in tbl.values()), len(tbl), 10)

    # ── D 组：保守性（不低于占位初值） ──
    for lang in NEW_LANGS:
        chk('D-' + lang, 'D', 'sec_per_char[%s] >= 占位初值 0.07' % lang,
            tbl.get(lang, 0) >= PLACEHOLDER, tbl.get(lang), '>= %s' % PLACEHOLDER)

    # ── E 组：别名口径 ──
    alias = {'de': 'german', 'fr': 'français', 'es': 'español',
             'pt': 'português', 'it': 'italiano', 'ru': 'русский'}
    for lang, al in alias.items():
        key = ns['_lang_key'](al)
        chk('E-' + lang, 'E', "_lang_key(%r) -> %r 且取到同一校准值" % (al, lang),
            key == lang and ns['estimate_sec']('x' * 100, al) == ns['estimate_sec']('x' * 100, lang),
            (key, ns['estimate_sec']('x' * 100, al)), (lang, ns['estimate_sec']('x' * 100, lang)))

    return checks


def main() -> None:
    src = open(SRC, encoding='utf-8').read()
    evidence = json.load(open(EVIDENCE, encoding='utf-8'))
    expect = expected_values(evidence)

    ns = load_ns(src)
    checks = run_checks(ns, expect, 'live')

    # ── F 组（反证组）：证明 A 组不是恒真 ──
    neg = []
    # F1：把 6 个新值改回占位初值 ⇒ A 组必须 FAIL
    # ⚠️ 期望值是「**至少 5 条** FAIL」而不是 6：
    #    `fr` 的实测校准值**恰好等于** 0.070（ceil3(0.069542) = 0.070）
    #    ⇒ 把 fr 改回 0.07 **不构成差异** ⇒ A-fr 仍然 PASS。
    #    ⇒ 判据写成「>= 6」会**把正确的实现判成 FAIL**（踩过一次：
    #    先写成 >=6 ⇒ 实测 5/6 ⇒ FAIL ⇒ 查代码才发现 fr 的巧合，不是回归）。
    ns_f1 = dict(ns)
    tbl_f1 = dict(ns['_SEC_PER_CHAR'])
    for lang in NEW_LANGS:
        tbl_f1[lang] = PLACEHOLDER
    ns_f1['_SEC_PER_CHAR'] = tbl_f1
    c_f1 = run_checks(ns_f1, expect, 'neg-f1')
    a_fail_f1 = [c for c in c_f1 if c['group'] == 'A' and not c['ok']]
    n_expect_fail = sum(1 for lang in NEW_LANGS if expect[lang] != PLACEHOLDER)
    neg.append(dict(id='F1', name='改回占位初值 0.07 ⇒ A 组必须 FAIL（fr 校准值恰为 0.070 ⇒ 预期 %d 条）'
                          % n_expect_fail,
                     n_a_failed=len(a_fail_f1), want='>= %d' % n_expect_fail,
                     ok=len(a_fail_f1) >= n_expect_fail))
    # F2：把某一个新值改成别的数 ⇒ A 组必须 FAIL
    ns_f2 = dict(ns)
    tbl_f2 = dict(ns['_SEC_PER_CHAR'])
    tbl_f2['ru'] = 0.123
    ns_f2['_SEC_PER_CHAR'] = tbl_f2
    c_f2 = run_checks(ns_f2, expect, 'neg-f2')
    a_fail_f2 = [c for c in c_f2 if c['group'] == 'A' and not c['ok']]
    neg.append(dict(id='F2', name='把 ru 改成 0.123 ⇒ A 组必须 FAIL',
                     n_a_failed=len(a_fail_f2), want='>= 1', ok=len(a_fail_f2) >= 1))
    # F3：改 zh ⇒ B 组必须 FAIL（证明既有语言也被闸门看着）
    ns_f3 = dict(ns)
    tbl_f3 = dict(ns['_SEC_PER_CHAR'])
    tbl_f3['zh'] = 0.30
    ns_f3['_SEC_PER_CHAR'] = tbl_f3
    c_f3 = run_checks(ns_f3, expect, 'neg-f3')
    b_fail_f3 = [c for c in c_f3 if c['group'] == 'B' and not c['ok']]
    neg.append(dict(id='F3', name='把 zh 改成 0.30 ⇒ B 组必须 FAIL',
                     n_b_failed=len(b_fail_f3), want='>= 1', ok=len(b_fail_f3) >= 1))

    all_checks = checks + [dict(id=n['id'], group='F', name=n['name'], ok=n['ok'],
                                got=n['n_a_failed'] if n['id'] != 'F3' else n['n_b_failed'],
                                want=n['want']) for n in neg]
    n_ok = sum(1 for c in all_checks if c['ok'])
    n_bad = sum(1 for c in all_checks if not c['ok'])
    verdict = 'PASS' if n_bad == 0 else 'FAIL'

    res = {
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'app': 'APP-097 §2-4',
        'criterion': 'A=6 新值==证据复算的 ceil3(max(preset,clone)p50)；B=zh/en/ja/ko 未变；'
                     'C=表形状 10 键；D=新值>=0.07（守卫只会变松）；E=别名口径同值；'
                     'F=反证组（改值必须 FAIL）',
        'device_job': False,
        'lock_note': '纯 CPU 静态检查（不加载模型、不占 GPU/NPU）⇒ 不需要 MACHINE_LOCK',
        'src': 'live_caption/tts_engine.py',
        'evidence_source': 'results/app/app326_app097_lang_out/tts.json',
        'expected_values': expect,
        'n_checks': len(all_checks),
        'n_ok': n_ok,
        'n_bad': n_bad,
        'verdict': verdict,
        'checks': all_checks,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    for c in all_checks:
        if not c['ok']:
            print('FAIL %-10s %s | got=%r want=%r' % (c['id'], c['name'], c['got'], c['want']))
    print('%s: %d/%d PASS  (F 反证组 %d/%d 触发)' % (
        verdict, n_ok, len(all_checks),
        sum(1 for n in neg if n['ok']), len(neg)))
    print('WROTE: %s' % OUT)
    sys.exit(0 if verdict == 'PASS' else 1)


if __name__ == '__main__':
    main()
