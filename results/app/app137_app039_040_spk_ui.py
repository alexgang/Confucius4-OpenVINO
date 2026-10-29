# -*- coding: utf-8 -*-
"""🔴🔴 APP-039 / APP-040（**App 侧可执行部分**）验收脚本。

## 本轮改了什么（及其依据）

| # | 缺陷 | reviewer 依据 | 修法 |
|---|---|---|---|
| D1 | 「显示说话人」开关**默认关闭** | APP-040④「GUI 加一个开关，**默认打开**」 | `value=False` ⇒ `value=True` |
| D2 | 说话人标签**只加在原文行**，译文行没有 | APP-040④「原文**和译文**字幕每句前面都显示说话人标签」 | `_render` 给 `mt` / `mt_draft` 也加前缀（按 `seg` 回查） |
| D3 | `_spk_by_seg` 存的是 `(spk, spk_conf)` 元组，渲染层当 id 用 ⇒ 标签会显示成 `[('S1', 0.87)]` | APP-040④（标签正确性） | `caption_render.spk_id_of()` + `live_caption_app._spk_id()` 归一化 |
| D4 | 同一个说话人**没有固定颜色** | APP-040④「同一个人颜色固定」 | `_spk_color()` 确定性配色（**不用 `hash`**，否则随进程变） |
| D5 | 克隆模式**没标「实验」** | APP-039「克隆模式先标'实验'」 | 下拉文案 / 帮助 / 状态提示 ⇒ 「跟随说话人（克隆·实验）」 |
| D6 | GUI **不显示**「本句用的是哪个 spk」 | APP-039「GUI 上显示每句实际用的是哪个 spk 和哪个音色」 | `_spk_now_label()`（没标注时**如实显示「—（未标注）」**） |

## 🔴 本轮**不做**什么（APP-039/040 明文停在这里）

- **音色按句绑定 spk + 说话人音色表（检测到换人才取样）**：
  APP-039 明文「spk 来源 = ASR 的说话人旁路接口……**在接口交付前，
  不要自己再写一套持续采样的方案**」⇒ `shared/spe_qa_spk.json`（ASR-028）
  与 ASR-029 接口**均未交付** ⇒ 本轮**不改采样策略**（`clone_collector` 零改动）。
- **验收实测**（SPE Q&A 段多人对话、CAMPPlus 余弦、声纹计算次数）：
  需持锁跑 NPU/播放路径 ⇒ 属「计时或测速作业」⇒ 本轮**不跑**（守纪律）。

## 判据设计（REAL / BUG / BASELINE 三组）

- **REAL**：修后必须成立（不成立 = 没修好）。
- **BUG**：缺陷**仍然存在**才会命中 ⇒ 命中即 FAIL。
- **BASELINE**：用**固定 commit `f724769`** 的源码跑同一套场景 ⇒
  必须 FAIL（证明缺陷**曾经真实存在**）。
  ⚠️ 用 `HEAD` 会失效（改完 HEAD 就是修复版）⇒ 这里写死基线 commit。

🔴🔴 **不 `import` 被测模块**（顶层 numpy 会让 import 阶段 abort）
⇒ 一律 `ast` 抽源码 + `exec` 进独立命名空间。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))          # confucius4-openvino
APP_REL = 'live_caption/live_caption_app.py'
CR_REL = 'live_caption/caption_render.py'
# 🔴 反证基线：**修前**那份源码（本轮开工时的 HEAD）
BASE_COMMIT = 'f724769'

N_OK = 0
N_FAIL = 0
ROWS = []


def check(group, name, ok, detail=''):
    global N_OK, N_FAIL
    ok = bool(ok)
    if ok:
        N_OK += 1
    else:
        N_FAIL += 1
    ROWS.append({'group': group, 'name': name, 'ok': ok, 'detail': str(detail)[:400]})
    print('  [%s] %s %s  <- %s' % (group, 'PASS' if ok else 'FAIL', name,
                                   str(detail)[:200]))


def read(path):
    with io.open(path, encoding='utf-8') as f:
        return f.read()


def git_show(commit, rel):
    out = subprocess.check_output(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                                  stderr=subprocess.STDOUT)
    return out.decode('utf-8')


# ── 桩：Tk Text / StringVar / BooleanVar ─────────────────────────────
class FakeTxt:
    def __init__(self):
        self.inserted = []      # [(text, tags)]
        self.tags = {}

    def insert(self, _idx, text, *tags):
        t = tags[0] if tags else ()
        if isinstance(t, str):
            t = (t,)
        self.inserted.append((text, tuple(t)))

    def tag_configure(self, name, **kw):
        self.tags[name] = kw

    def tag_names(self):
        return tuple(self.tags)

    def configure(self, *_a, **_k):
        pass

    def delete(self, *_a):
        pass

    def see(self, *_a):
        pass


class FakeVar:
    def __init__(self, v):
        self._v = v

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class FakeSelf:
    """只放 `_render` 真正会碰到的属性。"""

    def __init__(self, lines, show_spk, spk_by_seg):
        self.txt = FakeTxt()
        self.var_show_spk = FakeVar(show_spk)
        self._lines = lines
        self._spk_by_seg = spk_by_seg
        self.overlay = None

    def _render_lines(self):
        return list(self._lines)


def build_ns(app_src, cr_src):
    """🔴 用 `ast` 抽出需要的函数 + 常量，`exec` 进独立命名空间（**不 import**）。"""
    ns = {'__name__': 'sandbox'}
    # 渲染层：只 import 了 `re` ⇒ 整个模块源码可直接 exec
    exec(compile(cr_src, 'caption_render.py', 'exec'), ns)

    tree = ast.parse(app_src)
    wanted_mod = {'_spk_id', '_spk_color'}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in wanted_mod:
            exec(compile(ast.Module(body=[n], type_ignores=[]), 'app', 'exec'), ns)
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if getattr(tg, 'id', None) == '_SPK_COLOR_PALETTE':
                    exec(compile(ast.Module(body=[n], type_ignores=[]), 'app', 'exec'), ns)

    cls = None
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name == 'App':
            cls = n
            break
    got = {}
    if cls is not None:
        for f in cls.body:
            if isinstance(f, ast.FunctionDef) and f.name in ('_render', '_spk_now_label',
                                                             '_spk_tag'):
                exec(compile(ast.Module(body=[f], type_ignores=[]), 'app', 'exec'), ns)
                got[f.name] = ns[f.name]
    ns['_got'] = got
    return ns


def attach(ns, obj, names):
    for nm in names:
        fn = ns.get(nm)
        if fn is None:
            raise AttributeError(nm)
        setattr(obj, nm, (lambda f: (lambda *a, **k: f(obj, *a, **k)))(fn))


# ── 场景数据 ────────────────────────────────────────────────────────
# ⚠️ 与真实 `render_lines` 一致：**只有 src 行带 `spk`**，mt 行没有
LINES = [
    {'kind': 'src', 'text': 'Hello everyone.', 'seg': 0, 'draft': False, 'spk': 'S1'},
    {'kind': 'mt', 'text': '大家好。', 'seg': 0, 'draft': False},
    {'kind': 'src', 'text': 'Thanks for having me.', 'seg': 1, 'draft': False, 'spk': 'S2'},
    {'kind': 'mt_draft', 'text': '谢谢邀请我。', 'seg': 1, 'draft': True},
    {'kind': 'src', 'text': 'Any questions?', 'seg': 2, 'draft': False, 'spk': None},
    {'kind': 'mt', 'text': '有问题吗？', 'seg': 2, 'draft': False},
]
# 🔴 App 侧实际写入形态 = **元组**（`(spk, spk_conf)`）
SPK_BY_SEG = {0: ('S1', 0.91), 1: ('S2', 0.77)}


def expected_mt_rows():
    """`(插入行的下标顺序, 该行所属 seg, 期望标签)` —— 只对**有 spk 的段**有期望。

    🔴 为什么要显式区分「有 spk」与「没 spk」：第一次写判据时把「没 spk 的译文行」
    也算进「缺标签」⇒ **判据恒 FAIL**（它本来就该没标签）⇒ 属**判据缺陷**，
    不是产品缺陷（见 STATUS §94：判据必须自己也过「是否分辨得出来」这一关）。
    """
    out = []
    for l in LINES:
        if l['kind'] not in ('mt', 'mt_draft'):
            continue
        # ⚠️ **必须是扁平值**：返回 `(seg, spk)` 会让 `for r, s in zip(...)`
        #    解包出 `s=(2, None)` ⇒ 元组恒为真 ⇒ 「没 spk 的行」被当成
        #    「有 spk」⇒ 判据恒 FAIL（本轮首跑踩到，属**判据自身缺陷**）。
        out.append(_spk_id_expected(SPK_BY_SEG.get(l['seg'])))
    return out


def _spk_id_expected(v):
    return v[0] if isinstance(v, (tuple, list)) and v else v


def mt_rows_of(inserted):
    """按顺序取出译文行的文本（与 `expected_mt_rows()` 同序）。"""
    return [t for t, _g in inserted if '〔译〕' in t]


def run_real(app_src, cr_src):
    ns = build_ns(app_src, cr_src)

    # R1 说话人 id 归一化
    f = ns.get('spk_id_of')
    if f is None:
        check('REAL', 'R1 spk_id_of 存在', False, 'missing spk_id_of')
    else:
        check('REAL', 'R1 spk_id_of 元组/字符串/空值三种形态',
              f(('S1', 0.87)) == 'S1' and f('S2') == 'S2'
              and f(None) is None and f(()) is None and f([]) is None,
              'tuple=%r str=%r none=%r' % (f(('S1', 0.87)), f('S2'), f(None)))

    # R2 渲染层：元组值不会泄漏成标签
    rl = ns.get('render_lines')
    blocks = ['a', 'b']
    units = [{'key': 'k1', 'src': 'b', 'seg': 1, 'mt': '译文', 'kind': 'final',
              'unit_id': 'C:1:1'}]
    out_tuple = rl(blocks, units, granularity='seg',
                   spk_by_seg={0: ('S1', 0.9)})
    out_str = rl(blocks, units, granularity='seg', spk_by_seg={0: 'S1'})
    s0 = [l for l in out_tuple if l['kind'] == 'src'][0]
    check('REAL', 'R2 render_lines 元组值 ⇒ spk 仍为 id（不是元组）',
          s0.get('spk') == 'S1' and not isinstance(s0.get('spk'), (tuple, list)),
          'spk=%r' % (s0.get('spk'),))
    check('REAL', 'R2b 旧调用方（str 值）行为逐位不变',
          [l for l in out_str if l['kind'] == 'src'][0].get('spk') == 'S1',
          'ok')

    # R3 原文行 + 译文行都带标签（APP-040④）
    fake = FakeSelf(LINES, True, dict(SPK_BY_SEG))
    attach(ns, fake, ['_render', '_spk_now_label', '_spk_tag'])
    fake._render(None)
    ins = fake.txt.inserted
    src_rows = [t for t, _ in ins if t.startswith('[S')]
    mt_rows = mt_rows_of(ins)
    exp = expected_mt_rows()
    want = [r for r, s in zip(mt_rows, exp) if s]        # 该段**有** spk
    plain = [r for r, s in zip(mt_rows, exp) if not s]   # 该段**没有** spk
    check('REAL', 'R3 原文行带说话人标签',
          any(t.startswith('[S1] Hello') for t, _ in ins)
          and any(t.startswith('[S2] Thanks') for t, _ in ins),
          'src=%r' % (src_rows,))
    check('REAL', 'R3b 译文行**也**带说话人标签（APP-040④）',
          len(want) == 2 and want[0].startswith('    [S1] 〔译〕')
          and want[1].startswith('    [S2] 〔译〕'),
          'mt_with_spk=%r' % (want,))
    check('REAL', 'R3c 没有 spk 的段 ⇒ 不加标签（不编造）',
          any(t.startswith('Any questions?') for t, _ in ins)
          and len(plain) == 1 and plain[0].startswith('    〔译〕有问题吗？'),
          'mt_no_spk=%r' % (plain,))

    # R4 标签颜色：同一个人固定 + 不同人不同色
    tags_used = [g for _t, g in ins if g]
    check('REAL', 'R4 标签走 Tk tag（同一说话人颜色固定）',
          any('spk_S1' in g for g in tags_used)
          and any('spk_S2' in g for g in tags_used)
          and 'spk_S1' in fake.txt.tags and 'spk_S2' in fake.txt.tags,
          'tags=%r' % (sorted(set(g for g in tags_used)),))
    col = ns.get('_spk_color')
    if col is None:
        check('REAL', 'R4b 配色确定性（不随进程变）', False, 'missing _spk_color')
    else:
        src_seg = ast.get_source_segment(app_src, _find_func(ast.parse(app_src), '_spk_color'))
        check('REAL', 'R4b 配色确定性（**不用 hash** ⇒ 不随进程变）',
              'hash(' not in (src_seg or '') and col('S1') == col('S1')
              and col('S1') != col('S2') and col('S1').startswith('#'),
              'S1=%s S2=%s' % (col('S1'), col('S2')))

    # R5 开关关掉 ⇒ 回归旧行为（仍是**可选的**）
    fake2 = FakeSelf(LINES, False, dict(SPK_BY_SEG))
    attach(ns, fake2, ['_render', '_spk_now_label', '_spk_tag'])
    fake2._render(None)
    check('REAL', 'R5 开关关闭 ⇒ 一个标签都不加（回归旧行为）',
          not any(t.startswith('[S') for t, _ in fake2.txt.inserted),
          'rows=%r' % ([t[:20] for t, _ in fake2.txt.inserted],))

    # R6 本句说话人标签（APP-039）
    fake3 = FakeSelf(LINES, True, {})
    attach(ns, fake3, ['_render', '_spk_now_label', '_spk_tag'])
    e = fake3._spk_now_label()
    fake4 = FakeSelf(LINES, True, dict(SPK_BY_SEG))
    attach(ns, fake4, ['_render', '_spk_now_label', '_spk_tag'])
    s = fake4._spk_now_label()
    check('REAL', 'R6 本句说话人：无标注 ⇒ 如实显示「未标注」；有 ⇒ 显示 id',
          '未标注' in e and s == '说话人：S2',
          'empty=%r set=%r' % (e, s))

    # R7 开关默认打开（APP-040④）
    d = _var_default(ast.parse(app_src), 'var_show_spk')
    check('REAL', 'R7 「显示说话人」默认打开（APP-040④ 明文）',
          d is True, 'default=%r' % (d,))

    # R8 克隆模式标注实验（APP-039）
    lbl = _voice_label(app_src, 'follow_speaker')
    check('REAL', 'R8 克隆模式标注「实验」（APP-039 明文）',
          lbl is not None and '实验' in lbl, 'label=%r' % (lbl,))


def _find_func(tree, name, cls=None):
    if cls is None:
        for n in tree.body:
            if isinstance(n, ast.FunctionDef) and n.name == name:
                return n
            if isinstance(n, ast.ClassDef):
                r = _find_func(n, name, cls=n.name)
                if r is not None:
                    return r
        return None
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _var_default(tree, attr):
    """找 `self.<attr> = tk.BooleanVar(value=X)` 里的 X。"""
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Attribute) and tg.attr == attr:
                    v = n.value
                    if isinstance(v, ast.Call):
                        for kw in v.keywords:
                            if kw.arg == 'value' and isinstance(kw.value, ast.Constant):
                                return kw.value.value
    return '__missing__'


def _voice_label(app_src, key):
    """从 `self._tts_voice_label = {...}` 里取显示文案（不执行 `__init__`）。"""
    tree = ast.parse(app_src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Attribute) and tg.attr == '_tts_voice_label':
                    try:
                        d = ast.literal_eval(n.value)
                    except Exception:
                        return None
                    return d.get(key)
    return None


def run_bug(app_src, cr_src):
    """BUG 组：命中 = 缺陷**仍然存在** ⇒ FAIL。"""
    ns = build_ns(app_src, cr_src)
    fake = FakeSelf(LINES, True, dict(SPK_BY_SEG))
    attach(ns, fake, ['_render', '_spk_now_label', '_spk_tag'])
    fake._render(None)
    ins = fake.txt.inserted

    got = mt_rows_of(ins)
    exp = expected_mt_rows()
    mt_without = [r for r, s in zip(got, exp) if s and not r.lstrip().startswith('[S')]
    check('BUG', 'B1 译文字幕缺说话人标签（APP-040④）', len(mt_without) == 0,
          'missing=%r' % (mt_without,))

    check('BUG', 'B2 元组泄漏成标签文本（如 [(\'S1\', 0.91)]）',
          not any("('" in t for t, _ in ins),
          'rows=%r' % ([t[:40] for t, _ in ins],))

    d = _var_default(ast.parse(app_src), 'var_show_spk')
    check('BUG', 'B3 开关默认是关的', d is not False, 'default=%r' % (d,))

    lbl = _voice_label(app_src, 'follow_speaker') or ''
    check('BUG', 'B4 克隆模式没标「实验」', '实验' in lbl, 'label=%r' % (lbl,))

    fake0 = FakeSelf(LINES, True, {})
    attach(ns, fake0, ['_render', '_spk_now_label', '_spk_tag'])
    check('BUG', 'B5 没标注时编造/隐匿说话人', '未标注' in fake0._spk_now_label(),
          'label=%r' % (fake0._spk_now_label(),))


def run_baseline():
    """🔴 反证：同一套场景对**修前源码**（固定 commit）必须 FAIL。"""
    try:
        app_src = git_show(BASE_COMMIT, APP_REL)
        cr_src = git_show(BASE_COMMIT, CR_REL)
    except Exception as e:
        check('BASELINE', 'E0 取到基线源码', False, 'git show 失败：%s' % e)
        return
    check('BASELINE', 'E0 取到基线源码（commit %s）' % BASE_COMMIT,
          len(app_src) > 1000 and len(cr_src) > 1000,
          'app=%dB cr=%dB' % (len(app_src), len(cr_src)))

    ns = build_ns(app_src, cr_src)

    # E1 元组泄漏（基线没有 spk_id_of）
    rl = ns['render_lines']
    out = rl(['a', 'b'],
             [{'key': 'k1', 'src': 'b', 'seg': 1, 'mt': '译文', 'kind': 'final',
               'unit_id': 'C:1:1'}],
             granularity='seg', spk_by_seg={0: ('S1', 0.9)})
    s0 = [l for l in out if l['kind'] == 'src'][0]
    check('BASELINE', 'E1 基线：元组原样当标签 ⇒ 缺陷曾真实存在',
          isinstance(s0.get('spk'), tuple),
          'baseline spk=%r' % (s0.get('spk'),))

    # E2 基线 `_render` 不给译文行加标签
    fake = FakeSelf(LINES, True, dict(SPK_BY_SEG))
    try:
        attach(ns, fake, ['_render'])
        fake._render(None)
        got = mt_rows_of(fake.txt.inserted)
        exp = expected_mt_rows()
        mt_without = [r for r, s in zip(got, exp) if s
                      and not r.lstrip().startswith('[S')]
        check('BASELINE', 'E2 基线：译文行没有说话人标签 ⇒ 缺陷曾真实存在',
              len(mt_without) == 2, 'missing=%r' % (mt_without,))
    except Exception as e:
        check('BASELINE', 'E2 基线：译文行没有说话人标签', False,
              'exc=%s: %s' % (type(e).__name__, e))

    # E3 基线默认关闭
    d = _var_default(ast.parse(app_src), 'var_show_spk')
    check('BASELINE', 'E3 基线：开关默认关闭 ⇒ 缺陷曾真实存在',
          d is False, 'baseline default=%r' % (d,))

    # E4 基线没标实验
    lbl = _voice_label(app_src, 'follow_speaker') or ''
    check('BASELINE', 'E4 基线：克隆模式未标「实验」 ⇒ 缺陷曾真实存在',
          '实验' not in lbl, 'baseline label=%r' % (lbl,))


def run_judge_selftest(app_src, cr_src):
    """🔴🔴 **判据自证**：把修复**退回去**，REAL 组必须 FAIL。

    否则「判据恒真」⇒ 验收毫无意义（§36/§45 的教训：
    「审计脚本跑出 PASS ≠ 脚本是对的」⇒ 必须**双向反证**）。
    """
    global N_OK, N_FAIL, ROWS
    save_ok, save_fail, save_rows = N_OK, N_FAIL, ROWS
    N_OK, N_FAIL, ROWS = 0, 0, []

    # 注入①：译文行不再加说话人前缀（退回旧行为）
    inj = app_src.replace("'    ' + pre + '〔译〕'", "'    〔译〕'")
    if inj == app_src:
        check('JUDGE', 'J0 能注入缺陷（译文行前缀）', False, 'anchor not found')
    else:
        run_real(inj, cr_src)
        names = {r['name']: r['ok'] for r in ROWS}
        check('JUDGE', 'J1 退回「译文行不加标签」 ⇒ R3b 必须 FAIL（判据不恒真）',
              names.get('R3b 译文行**也**带说话人标签（APP-040④）') is False,
              'R3b=%r' % (names.get('R3b 译文行**也**带说话人标签（APP-040④）'),))

    # 注入②：开关默认改回 False
    N_OK, N_FAIL, ROWS = 0, 0, []
    inj2 = app_src.replace('tk.BooleanVar(value=True)', 'tk.BooleanVar(value=False)')
    if inj2 == app_src:
        check('JUDGE', 'J2 能注入缺陷（默认关闭）', False, 'anchor not found')
    else:
        run_real(inj2, cr_src)
        names = {r['name']: r['ok'] for r in ROWS}
        check('JUDGE', 'J2 退回「默认关闭」 ⇒ R7 必须 FAIL（判据不恒真）',
              names.get('R7 「显示说话人」默认打开（APP-040④ 明文）') is False,
              'R7=%r' % (names.get('R7 「显示说话人」默认打开（APP-040④ 明文）'),))

    N_OK, N_FAIL, ROWS = save_ok, save_fail, save_rows


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--app', default=None,
                    help='被测 `live_caption_app.py` 路径（默认仓库；'
                         '传客户包里的那份可对**包内代码**跑同一套断言）')
    ap.add_argument('--cr', default=None, help='被测 `caption_render.py` 路径')
    ap.add_argument('--no-baseline', action='store_true',
                    help='跳过 BASELINE 组（对客户包跑时用，避免与仓库 git 混淆）')
    a = ap.parse_args()
    app_path = a.app or os.path.join(REPO, APP_REL)
    cr_path = a.cr or os.path.join(REPO, CR_REL)
    app_src = read(app_path)
    cr_src = read(cr_path)
    print('=' * 78)
    print('APP-039 / APP-040 验收（App 侧可执行部分）')
    print('  app: %s  %d B  sha256=%s' % (APP_REL, len(app_src.encode('utf-8')),
                                          hashlib.sha256(app_src.encode('utf-8')).hexdigest()[:16]))
    print('  cr : %s  %d B  sha256=%s' % (CR_REL, len(cr_src.encode('utf-8')),
                                          hashlib.sha256(cr_src.encode('utf-8')).hexdigest()[:16]))
    print('  baseline commit: %s' % BASE_COMMIT)
    print('=' * 78)
    print('\n--- REAL 组（修后必须成立）---')
    run_real(app_src, cr_src)
    print('\n--- BUG 组（命中 = 缺陷仍在 ⇒ FAIL）---')
    run_bug(app_src, cr_src)
    print('\n--- JUDGE 组（注入缺陷 ⇒ REAL 必须 FAIL，证明判据不恒真）---')
    run_judge_selftest(app_src, cr_src)
    if a.no_baseline:
        print('\n--- BASELINE 组：已按 --no-baseline 跳过 ---')
    else:
        print('\n--- BASELINE 组（修前源码必须 FAIL ⇒ 证明缺陷曾存在）---')
        run_baseline()

    verdict = 'PASS' if N_FAIL == 0 else 'FAIL'
    print('\n结果：REAL+BUG %d PASS / %d FAIL ｜ verdict=%s' % (N_OK, N_FAIL, verdict))

    ev = {
        'script': os.path.basename(__file__),
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'baseline_commit': BASE_COMMIT,
        'app_sha256': hashlib.sha256(app_src.encode('utf-8')).hexdigest(),
        'cr_sha256': hashlib.sha256(cr_src.encode('utf-8')).hexdigest(),
        'n_pass': N_OK, 'n_fail': N_FAIL, 'verdict': verdict,
        'rows': ROWS,
    }
    tag = '_pkg' if a.app else ''
    out = os.path.join(HERE, 'app137_app039_040%s_evidence.json' % tag)
    with io.open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('证据落盘：%s' % out)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
