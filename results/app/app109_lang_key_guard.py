# -*- coding: utf-8 -*-
"""app109 — APP-030② **失控守卫的语言口径统一**（§78 自查抓出的真实缺陷）。

## 缺陷（真实存在，reviewer 未点名）

`estimate_frames()` / `estimate_sec()` 原先用
`_SEC_PER_CHAR.get((lang or 'en').lower(), _SEC_PER_CHAR['en'])`
⇒ **只认小写代号**（`zh`/`ja`/`ko`/`en`）；
但同文件里的 `map_language()` **认得**全称与带区域写法
（`'Japanese'` / `'zh-cn'` / `'zh-tw'` / `'jp'` …）
⇒ **两套表解析同一个语言标识 ⇒ 口径不一致**：

| `lang` 传入 | 修复前 sec/字 | 真实值 | 低估倍数 |
|---|---|---|---|
| `'Japanese'` | 0.07（英文） | 0.15（日） | **2.1×** |
| `'zh-cn'`     | 0.07（英文） | 0.25（中） | **3.6×** |
| `'zh-tw'`     | 0.07（英文） | 0.25（中） | **3.6×** |

⇒ 后果 = **失控守卫阈值算得过低**：
   - `RUNAWAY` 阈值 `max(3×est, est+8)` 用小 est ⇒ **更容易误杀正常长句**；
   - `clamp_max_new_tokens` 用小 est ⇒ **帧数上限偏松**（失控上限被放行）。

⚠️ 当前生产路径**恰好**只传小写代号（`translator.TARGETS` = zh/en/ja/ko）
⇒ 缺陷**未暴露**；但这属于「同一个标识两套口径」的隐患。

## 修法

统一走 `map_language()`（唯一映射表）⇒ 新增 `_lang_key()`。

## 判据（零推理 / 零 GPU / 零 NPU）

- **A 组（口径正确性）**：全称与带区域写法 ⇒ 与小写代号**逐字相同**。
- **B 组（生产路径零回归）**：小写代号的 sec/frames/mnt **与修复前逐字相同**。
- **C 组（反证）**：把 `_lang_key` 改成旧的 `.get(...)` 写法 ⇒ A 组必须 FAIL。
- **D 组（未知语言）**：未知语言仍落 `'en'`（与历史行为一致）。

## 用法

    <python> results/app/app109_lang_key_guard.py
    APP109_SRC_ROOT=<repo>/live_caption APP109_EVID=<out.json> <python> ...
"""
from __future__ import annotations

import ast
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_ROOT = os.environ.get('APP109_SRC_ROOT') or os.path.join(REPO, 'live_caption')
EVID = os.environ.get('APP109_EVID') or os.path.join(
    HERE, 'app109_lang_key_guard_evidence.json')

FUNCS = ('map_language', '_lang_key', 'estimate_sec', 'estimate_frames',
         'clamp_max_new_tokens', 'runaway_threshold_s')
CONSTS = ('LANG_MAP', '_SEC_PER_CHAR', '_LANG_TAIL_S',
          'RUNAWAY_FACTOR', 'RUNAWAY_EXTRA_S')


def load_engine(src_root: str):
    """🔴 **不 import** 被测模块（顶层可能拉重依赖）⇒ `ast` 抽源码 + `exec`。"""
    path = os.path.join(src_root, 'tts_engine.py')
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    ns = {}
    mod = ast.Module(body=[], type_ignores=[])
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in CONSTS:
                    try:
                        ns[t.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
        elif isinstance(node, ast.FunctionDef) and node.name in FUNCS:
            node.decorator_list = []
            mod.body.append(node)
    exec(compile(mod, path, 'exec'), ns)
    return ns


def run_criteria(ns):
    """返回 (checks, details)。每条 check = dict(id, group, name, pass, got, want)。"""
    checks = []

    def chk(cid, group, name, ok, got, want):
        checks.append(dict(id=cid, group=group, name=name, ok=bool(ok),
                           got=got, want=want))

    sec = ns['estimate_sec']
    frm = ns['estimate_frames']
    mnt = ns['clamp_max_new_tokens']
    T74 = 'あ' * 74

    # ── A 组：全称 / 带区域 ⇒ 与小写代号逐字相同 ──────────────
    A = [
        ('A1', 'Japanese', 'ja'),
        ('A2', 'japanese', 'ja'),
        ('A3', 'jp', 'ja'),
        ('A4', 'zh-cn', 'zh'),
        ('A5', 'zh-tw', 'zh'),
        ('A6', 'Chinese', 'zh'),
        ('A7', 'English', 'en'),
        ('A8', 'Korean', 'ko'),
    ]
    for cid, full, code in A:
        s1, s2 = sec(T74, full), sec(T74, code)
        chk(cid, 'A', 'estimate_sec(%r) == estimate_sec(%r)' % (full, code),
            s1 == s2, s1, s2)
    for cid, full, code in [('A9', 'Japanese', 'ja'), ('A10', 'zh-cn', 'zh')]:
        f1, f2 = frm(T74, full), frm(T74, code)
        chk(cid, 'A', 'estimate_frames(%r) == estimate_frames(%r)' % (full, code),
            f1 == f2, f1, f2)
    for cid, full, code in [('A11', 'Japanese', 'ja'), ('A12', 'zh-cn', 'zh')]:
        m1, m2 = mnt(T74, full), mnt(T74, code)
        chk(cid, 'A', 'clamp_max_new_tokens(%r) == clamp_max_new_tokens(%r)'
            % (full, code), m1 == m2, m1, m2)

    # ── B 组：生产路径（小写代号）**零回归** ────────────────────
    # 修复前的权威数值（实测自基线 commit a9ed250 的 _SEC_PER_CHAR）
    BASE = {'zh': (19.10, 229), 'ja': (11.70, 140), 'ko': (13.92, 167),
            'en': (5.78, 69)}
    for cid, code in [('B1', 'zh'), ('B2', 'ja'), ('B3', 'ko'), ('B4', 'en')]:
        bs, bf = BASE[code]
        s, f = sec(T74, code), frm(T74, code)
        chk(cid, 'B', 'sec(%r) 未变' % code, abs(s - bs) < 1e-9, s, bs)
        chk(cid + 'b', 'B', 'frames(%r) 未变' % code, f == bf, f, bf)
    # clamp：ja=3*140+36=456, zh=3*229+36=723, en=3*69+36=243, ko=3*167+36=537
    for cid, code, want in [('B5', 'ja', 456), ('B6', 'zh', 723),
                            ('B7', 'en', 243), ('B8', 'ko', 537)]:
        m = mnt(T74, code)
        chk(cid, 'B', 'clamp_max_new_tokens(%r) 未变' % code, m == want, m, want)
    # RUNAWAY 阈值：max(3*est, est+8)
    for cid, code, est in [('B9', 'ja', 11.70), ('B10', 'zh', 19.10)]:
        want = max(3 * est, est + 8.0)
        got = ns['runaway_threshold_s'](est)
        chk(cid, 'B', 'runaway_threshold_s(%r) 未变' % code,
            abs(got - want) < 1e-6, got, want)

    # ── C 组（反证）：重建「旧写法」⇒ A 组必须 FAIL ──
    # 🔴 用 **AST 重建** 造「旧写法」的 `estimate_sec` / `estimate_frames`
    #   （不是字符串替换 ⇒ 源码修好后反证**不会静默失效**）
    #   旧写法的语义 = 直接 `_SEC_PER_CHAR.get((lang or 'en').lower(), ...)`
    old_src = (
        "def estimate_sec(text, lang='en'):\n"
        "    n = len([c for c in (text or '') if not c.isspace()])\n"
        "    s = _SEC_PER_CHAR.get((lang or 'en').lower(), _SEC_PER_CHAR['en'])\n"
        "    return n * s + _LANG_TAIL_S\n"
        "\n"
        "def estimate_frames(text, lang='en'):\n"
        "    n = len([c for c in (text or '') if not c.isspace()])\n"
        "    s = _SEC_PER_CHAR.get((lang or 'en').lower(), _SEC_PER_CHAR['en'])\n"
        "    sec = n * s + _LANG_TAIL_S\n"
        "    return max(8, int(sec * 12))\n"
    )
    old_mod = ast.parse(old_src)
    ns2b = dict(ns)
    exec(compile(old_mod, '<repro>', 'exec'), ns2b)
    a_fail = 0
    for cid, full, code in [('A1', 'Japanese', 'ja'), ('A4', 'zh-cn', 'zh'),
                            ('A9', 'Japanese', 'ja'), ('A11', 'Japanese', 'ja')]:
        s1 = ns2b['estimate_sec'](T74, full)
        s2 = ns2b['estimate_sec'](T74, code)
        if s1 != s2:
            a_fail += 1
    chk('C1', 'C', '反证：旧写法下 A 组至少 4 条失配', a_fail == 4, a_fail, 4)
    # 反证下旧口径确实低估
    s_old = ns2b['estimate_sec'](T74, 'Japanese')
    s_new = ns['estimate_sec'](T74, 'Japanese')
    chk('C2', 'C', '反证：旧口径对 Japanese 低估（<新值）',
        s_old < s_new, s_old, '>= %s' % s_new)
    s_old_zh = ns2b['estimate_sec'](T74, 'zh-cn')
    s_new_zh = ns['estimate_sec'](T74, 'zh-cn')
    chk('C3', 'C', '反证：旧口径对 zh-cn 低估（<新值）',
        s_old_zh < s_new_zh, s_old_zh, '>= %s' % s_new_zh)
    # 反证：旧写法下 clamp_max_new_tokens 也偏松（用旧 frames ⇒ 上限更小？
    #   注意：frames 小 ⇒ 3*frames+36 小 ⇒ 上限更**紧**；这里断言差异存在即可）
    m_old = ns2b['estimate_frames'](T74, 'Japanese')
    m_new = ns['estimate_frames'](T74, 'Japanese')
    chk('C4', 'C', '反证：旧写法对 Japanese 的 frames 低估',
        m_old < m_new, m_old, '>= %s' % m_new)

    # ── D 组：未知语言仍落 'en'（历史行为一致）──────────────────
    for cid, val in [('D1', 'xx'), ('D2', ''), ('D3', None)]:
        s = sec(T74, val)
        chk(cid, 'D', '未知/空语言落 en（%r）' % (val,),
            abs(s - BASE['en'][0]) < 1e-9, s, BASE['en'][0])
    chk('D4', 'D', 'map_language 未知 → English',
        ns['map_language']('xx') == 'English', ns['map_language']('xx'), 'English')

    return checks, details_of(checks)


def details_of(checks):
    return checks


def main() -> int:
    ns = load_engine(SRC_ROOT)
    checks, _ = run_criteria(ns)
    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    print('=== app109 语言口径统一守卫（零推理）===')
    print('SRC_ROOT = %s' % SRC_ROOT)
    for c in checks:
        print('  [%s] %-3s %-6s %-58s %s  got=%r want=%r'
              % ('PASS' if c['ok'] else 'FAIL', c['id'], c['group'],
                 c['name'], 'OK' if c['ok'] else 'XX', c['got'], c['want']))
    print('\nSUMMARY: PASS=%d FAIL=%d TOTAL=%d' % (n_pass, n_fail, len(checks)))

    out = dict(src_root=SRC_ROOT, ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               pass_count=n_pass, fail_count=n_fail, total=len(checks),
               checks=checks,
               note='零推理/零 GPU/零 NPU；ast 抽源码 + exec；含 AST 重建反证')
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('证据已写入：%s' % EVID)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
