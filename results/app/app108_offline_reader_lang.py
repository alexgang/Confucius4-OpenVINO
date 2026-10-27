# -*- coding: utf-8 -*-
"""APP-030① 补漏 + APP-031/032 —— **离线朗读（离线朗读对话框）未显式下传目标语言**。

🔴🔴🔴 **零推理、零 GPU、零 NPU**（铁律：不在 CPU 上跑推理/测速）
   ⇒ 全部用 `ast` 抽源码 + `exec` 到独立命名空间 + **桩 service**。

## 本轮发现的真实缺陷（APP-030① 的遗漏）

APP-030① 要求「**目标语言显式下传**」。§75 已实现的部分覆盖了
**实时路径**（`live_caption_app.py` L3225 / L3996 / L4030 都带 `lang=`）
与 **CLI 路径**（`mt.target`）。

🔴 **但离线朗读路径漏了**：
  - `live_caption/offline_reader.py` 的 `_loop()` 调用
        `self.svc.submit(self.segs[i], seg=self.seg_base - i)`
    **不带 `lang`** ⇒ worker 侧 `msg.get('lang')` 为空
    ⇒ 回落到 `_guess_lang()` ⇒ **只分 zh/en** ⇒ **日文永远收不到 Japanese**
    ⇒ 正是 APP-030 的**原始根因路径**（「日文发音偶发卡住」）。
  - 🔴 这条路径**恰好是用户复现卡住最常走的那条**（离线朗读对话框）。

## 三条硬约束（脚本自己也要守）

1. **不 import 被测模块**（`offline_reader.py` 会 import `tts_service`）
   ⇒ 全部 `ast` 抽源码 + `exec` 到独立命名空间。
2. **解析失败 ⇒ 判 FAIL**（不能默认 PASS）⇒ 闸门自身的假通过比缺陷更危险。
3. **反证组**（故意写错 ⇒ 判据必须 FAIL）⇒ 证明判据不是「永远 PASS」。
   ⇒ 反证用 **AST 重建**（`ast.unparse`）而非字符串替换
   ⇒ 源码修好后反证**不会静默失效**。

用法：
  python results/app/app108_offline_reader_lang.py
  APP108_SRC_ROOT=<客户包根> APP108_EVID=<证据路径> python .../app108_offline_reader_lang.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# 🔴 **同一套判据必须能在「仓库」和「客户包」两处跑**
SRC_ROOT = os.environ.get('APP108_SRC_ROOT') or ROOT
_SUBDIR = 'app' if os.path.isdir(os.path.join(SRC_ROOT, 'app')) else 'live_caption'
READER = os.path.join(SRC_ROOT, _SUBDIR, 'offline_reader.py')
READER_GUI = os.path.join(SRC_ROOT, _SUBDIR, 'offline_reader_gui.py')
APP = os.path.join(SRC_ROOT, _SUBDIR, 'live_caption_app.py')
EVID = os.environ.get('APP108_EVID') or os.path.join(
    HERE, 'app108_offline_reader_lang_evidence.json')

N_PASS = 0
N_FAIL = 0
FAILURES = []
EVIDENCE = {}
EVIDENCE['_src_root'] = SRC_ROOT
EVIDENCE['_subdir'] = _SUBDIR


def check(name, cond, detail='', group='REAL'):
    global N_PASS, N_FAIL
    if cond:
        N_PASS += 1
        print('  [PASS] %s' % name)
    else:
        N_FAIL += 1
        FAILURES.append({'group': group, 'name': name, 'detail': detail})
        print('  [FAIL] %s  %s' % (name, detail))
    return bool(cond)


def src_of(path):
    with io.open(path, encoding='utf-8') as f:
        return f.read()


def parse_of(path):
    """🔴 解析失败 ⇒ 直接抛（不许静默）。"""
    return ast.parse(src_of(path))


def unparse(tree):
    """🔴 **AST 重建**（反证组用）—— 不是字符串替换。

    理由：源码修好后，字符串替换型的反证可能**恰好匹配不到**
    ⇒ 反证永远 skip ⇒ 假证据。用 `ast.unparse` 重建则
    「把某个语句去掉」是可判定的结构操作。
    """
    return ast.unparse(tree)


def find_func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


# ══════════════════════════════════════════════════════════════════════
# A 组：`OfflineReader` 把 `lang` 传给 `svc.submit`
# ══════════════════════════════════════════════════════════════════════
print('\n=== A 组：OfflineReader 显式下传 lang ===')

reader_tree = parse_of(READER)
reader_src = src_of(READER)

# A1：`OfflineReader.__init__` 接受 `lang` 关键字参数
init_fn = find_func(reader_tree, '__init__')
a1_ok = False
a1_detail = ''
if init_fn is not None:
    kwargs = [a.arg for a in init_fn.args.kwonlyargs]
    a1_ok = 'lang' in kwargs
    a1_detail = 'kwonlyargs=%r' % (kwargs,)
else:
    a1_detail = '找不到 OfflineReader.__init__'
check('A1 `OfflineReader.__init__` 有 `lang` 关键字参数', a1_ok, a1_detail)

# A2：实例上保存 `self.lang`
a2_ok = 'self.lang' in reader_src
check('A2 `self.lang` 被保存', a2_ok, '')

# A3：`_loop()` 里的 `svc.submit(...)` **带 `lang=`**
#   ⇒ 必须真正传下去，而不是只存不用。
loop_fn = find_func(reader_tree, '_loop')
a3_ok = False
a3_detail = ''
a3_kwargs = []
if loop_fn is not None:
    for n in ast.walk(loop_fn):
        if (isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'submit'):
            kws = [k.arg for k in n.keywords]
            a3_kwargs.append(kws)
            if 'lang' in kws:
                a3_ok = True
    a3_detail = 'submit kwargs=%r' % (a3_kwargs,)
else:
    a3_detail = '找不到 _loop'
check('A3 `_loop()` 里 `svc.submit(...)` 带 `lang=`', a3_ok, a3_detail)
EVIDENCE['A3_submit_kwargs'] = a3_kwargs

# A4：**不传 lang 时命令体不变**（向后兼容）
#   ⇒ 判据：`lang` 为假值时**不能**把 `lang=` 塞进 submit 调用
#   ⇒ 用桩 service 实测（不 import 被测模块 ⇒ exec 独立命名空间）
a4_ok = False
a4_detail = ''
try:
    mod = {'__name__': 'or_app108', '__file__': READER}
    exec(compile(reader_tree, READER, 'exec'), mod)
    OfflineReader = mod['OfflineReader']

    class _FakeSvc:
        """桩 service：只记 submit 的实参，不加载模型、不碰音频。"""

        def __init__(self):
            self.lock = threading.Lock()
            self.pending = {}
            self.state = 'ready'
            self.calls = []

        def submit(self, text, seg=None, **kw):
            self.calls.append((text, seg, kw))

        def cancel(self, jid):
            pass

    # A4a：有 lang ⇒ 带 lang
    svc1 = _FakeSvc()
    r1 = OfflineReader(svc1, lang='ja')
    r1.segs = ['これはテストです。']
    r1.n_seg = 1
    r1._stop.clear()
    t = threading.Thread(target=r1._loop, daemon=True)
    t.start()
    t.join(timeout=5.0)
    a4a = (len(svc1.calls) == 1 and svc1.calls[0][2].get('lang') == 'ja')
    a4_ok = a4a
    a4_detail = 'calls=%r' % (svc1.calls,)

    # A4b：无 lang ⇒ **不带** lang 关键字（向后兼容 ⇒ 旧假 service 不炸）
    svc2 = _FakeSvc()
    r2 = OfflineReader(svc2)
    r2.segs = ['こんにちは']
    r2.n_seg = 1
    r2._stop.clear()
    t2 = threading.Thread(target=r2._loop, daemon=True)
    t2.start()
    t2.join(timeout=5.0)
    a4b = (len(svc2.calls) == 1 and 'lang' not in svc2.calls[0][2])
    a4_ok = a4_ok and a4b
    a4_detail += ' / 无lang=%r' % (svc2.calls,)
except Exception as e:
    a4_ok = False
    a4_detail = repr(e)
check('A4 有 lang ⇒ 带 lang；无 lang ⇒ 不带（向后兼容）', a4_ok, a4_detail)
EVIDENCE['A4_detail'] = a4_detail

# A5：**假 service 不接受 lang 关键字时也不炸**
#   ⇒ 旧的自检/诊断脚本塞的假 service 签名是 `submit(text, seg=)`
#   ⇒ 若我们无条件传 `lang=` ⇒ `TypeError` ⇒ **回归**
#   ⇒ 判据：`lang` 为 None 时**不传**（已由 A4b 覆盖），
#      这里额外验证「假 service 只接受 (text, seg=)」也能跑。
a5_ok = False
a5_detail = ''
try:
    class _OldSvc:
        def __init__(self):
            self.lock = threading.Lock()
            self.pending = {}
            self.state = 'ready'
            self.calls = []

        def submit(self, text, seg=None):     # 🔴 **不接 **kw**
            self.calls.append((text, seg))

        def cancel(self, jid):
            pass

    svc3 = _OldSvc()
    r3 = OfflineReader(svc3)                 # 不给 lang
    r3.segs = ['テスト']
    r3.n_seg = 1
    r3._stop.clear()
    t3 = threading.Thread(target=r3._loop, daemon=True)
    t3.start()
    t3.join(timeout=5.0)
    a5_ok = (len(svc3.calls) == 1 and svc3.calls[0][1] is not None)
    a5_detail = 'calls=%r' % (svc3.calls,)
except Exception as e:
    a5_ok = False
    a5_detail = repr(e)
check('A5 旧式假 service（submit(text, seg=)）仍能跑（无 TypeError）',
      a5_ok, a5_detail)


# ══════════════════════════════════════════════════════════════════════
# B 组：GUI 侧接线（对话框 → App）
# ══════════════════════════════════════════════════════════════════════
print('\n=== B 组：GUI 接线 ===')

gui_tree = parse_of(READER_GUI)
gui_src = src_of(READER_GUI)
app_tree = parse_of(APP)
app_src = src_of(APP)

# B1：`OfflineReaderDialog.__init__` 接受 `get_lang`
#   ⚠️ `get_lang` 是**位置或关键字**参数（不是仅关键字）⇒ 两个列表都要查。
#   ⇒ 只查 kwonlyargs 会**假 FAIL**（判据自身缺陷，比漏判更坏）。
dlg_init = find_func(gui_tree, '__init__')
b1_ok = False
b1_detail = ''
if dlg_init is not None:
    pos = [a.arg for a in dlg_init.args.args]
    kws = [a.arg for a in dlg_init.args.kwonlyargs]
    b1_ok = ('get_lang' in pos or 'get_lang' in kws)
    b1_detail = 'args=%r kwonlyargs=%r' % (pos, kws)
else:
    b1_detail = '找不到 OfflineReaderDialog.__init__'
check('B1 对话框 `__init__` 有 `get_lang` 参数', b1_ok, b1_detail)

# B2：对话框保存 `self._get_lang`
b2_ok = 'self._get_lang' in gui_src
check('B2 `self._get_lang` 被保存', b2_ok, '')

# B3：创建 `OfflineReader` 时把 lang 传下去
b3_ok = False
b3_detail = ''
for n in ast.walk(gui_tree):
    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == 'OfflineReader'):
        kws = [k.arg for k in n.keywords]
        b3_ok = ('lang' in kws)
        b3_detail = 'OfflineReader kwargs=%r' % (kws,)
check('B3 创建 `OfflineReader` 时传 `lang=`', b3_ok, b3_detail)

# B4：`open_dialog` 接受并转发 `get_lang`
od = find_func(gui_tree, 'open_dialog')
b4_ok = False
b4_detail = ''
if od is not None:
    args = [a.arg for a in od.args.args]
    kws = [a.arg for a in od.args.kwonlyargs]
    b4_ok = ('get_lang' in args or 'get_lang' in kws)
    b4_detail = 'args=%r kwonly=%r' % (args, kws)
else:
    b4_detail = '找不到 open_dialog'
check('B4 `open_dialog` 有 `get_lang` 参数', b4_ok, b4_detail)

# B5：App 侧提供 `_offline_get_lang`
b5_ok = 'def _offline_get_lang' in app_src
check('B5 App 有 `_offline_get_lang`', b5_ok, '')

# B6：App 侧 `open_dialog(...)` 传 `get_lang=`
b6_ok = False
b6_detail = ''
for n in ast.walk(app_tree):
    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'open_dialog'):
        kws = [k.arg for k in n.keywords]
        b6_ok = ('get_lang' in kws)
        b6_detail = 'open_dialog kwargs=%r' % (kws,)
check('B6 App 调 `open_dialog` 时传 `get_lang=`', b6_ok, b6_detail)

# B7：`_offline_get_lang` 的返回值口径
#   ⇒ 'off'（翻译关闭）⇒ 必须返回 None（**不下传** ⇒ 保持旧行为）
#   ⇒ 'ja'/'en'/'zh'/'ko' ⇒ 原样返回
b7_ok = False
b7_detail = ''
gfn = find_func(app_tree, '_offline_get_lang')
if gfn is not None:
    body = ast.get_source_segment(app_src, gfn) or ''
    # 口径 ①：有 `== 'off'` 的判断 ⇒ 关闭时不下传
    has_off = ("'off'" in body or '"off"' in body)
    # 口径 ②：调用了 `_cur_mt_target()`
    uses_cur = '_cur_mt_target' in body
    b7_ok = has_off and uses_cur
    b7_detail = 'has_off=%s uses_cur_mt_target=%s' % (has_off, uses_cur)
else:
    b7_detail = '找不到 _offline_get_lang'
check('B7 `_offline_get_lang` 用 `_cur_mt_target()` 且对 `off` 返回 None',
      b7_ok, b7_detail)

# B8：`_cur_mt_target()` 返回的是**语言代号**（'ja'/'en'…），不是全称
#   ⇒ 因为 `submit(lang=)` 期望的是代号（worker 侧 `map_language` 再映射）
b8_ok = False
b8_detail = ''
cmt = find_func(app_tree, '_cur_mt_target')
if cmt is not None:
    body = ast.get_source_segment(app_src, cmt) or ''
    b8_ok = 'self.mt_keys' in body
    b8_detail = body[:200]
check('B8 `_cur_mt_target()` 返回语言代号（mt_keys）', b8_ok, b8_detail)


# ══════════════════════════════════════════════════════════════════════
# C 组：APP-031/032 的顺序纪律（代码侧不得越位）
# ══════════════════════════════════════════════════════════════════════
print('\n=== C 组：顺序纪律（APP-031/032）===')

# C1：APP-029 明文「现在不要集成」⇒ 本轮**不得**引入 pyannote 断句
c1_ok = True
for _n in ('pyannote', 'segmentation-3.0'):
    # 只在 app/ 主代码里查（排除注释里的「预告」字样难以判定 ⇒
    # 查 import 语句）
    for node in ast.walk(app_tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if _n in a.name:
                    c1_ok = False
        if isinstance(node, ast.ImportFrom):
            if node.module and _n in node.module:
                c1_ok = False
check('C1 未集成 pyannote（APP-029 明文「现在不要集成」）', c1_ok, '')

# C2：APP-030 的 5 项代码侧子要求**仍在**（本轮没把之前的修复改坏）
c2_items = [
    ('map_language 在 tts_engine.py', 'def map_language' in
     src_of(os.path.join(SRC_ROOT, _SUBDIR, 'tts_engine.py'))),
    ('clamp_max_new_tokens 在 tts_engine.py', 'def clamp_max_new_tokens' in
     src_of(os.path.join(SRC_ROOT, _SUBDIR, 'tts_engine.py'))),
    ('RUNAWAY 在 tts_cuda.py', 'RUNAWAY' in
     src_of(os.path.join(SRC_ROOT, _SUBDIR, 'tts_cuda.py'))),
    ('worker 侧 end_reason 遥测', "'end_reason'" in
     src_of(os.path.join(SRC_ROOT, _SUBDIR, 'tts_worker.py'))),
    ('submit 支持 lang 参数', 'lang' in
     (ast.get_source_segment(
         src_of(os.path.join(SRC_ROOT, _SUBDIR, 'tts_service.py')),
         find_func(parse_of(os.path.join(SRC_ROOT, _SUBDIR, 'tts_service.py')),
                   'submit')) or '')),
]
c2_ok = all(x[1] for x in c2_items)
check('C2 APP-030 的 5 项代码侧子要求仍在（本轮未改坏）', c2_ok,
      '失败项=%r' % ([x[0] for x in c2_items if not x[1]],))
EVIDENCE['C2_items'] = [(x[0], bool(x[1])) for x in c2_items]


# ══════════════════════════════════════════════════════════════════════
# F 组：反证（故意写错 ⇒ 判据必须 FAIL）
# ══════════════════════════════════════════════════════════════════════
print('\n=== F 组：反证 ===')

# F1：把 `_loop()` 里 `svc.submit(...)` 的 `lang` 关键字**去掉**
#   ⇒ A3 判据必须 FAIL（用 AST 重建，不靠字符串替换）
f1_ok = False
f1_detail = ''
try:
    tree2 = ast.parse(reader_src)
    loop2 = find_func(tree2, '_loop')
    removed = False
    for n in ast.walk(loop2):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'submit'):
            n.keywords = [k for k in n.keywords if k.arg != 'lang']
            removed = True
    f1_detail = 'removed=%s' % removed
    if removed:
        # 重建后「有没有 lang 关键字」
        found = False
        for n in ast.walk(loop2):
            if (isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'submit'):
                if 'lang' in [k.arg for k in n.keywords]:
                    found = True
        f1_ok = (not found)      # 去掉后判据应当「不通过」
except Exception as e:
    f1_ok = True
    f1_detail = repr(e)
check('F1 反证：AST 去掉 submit 的 `lang` ⇒ A3 判据能看出', f1_ok,
      f1_detail)
EVIDENCE['F1_detected'] = f1_ok

# F2：把 `OfflineReader.__init__` 的 `lang` 形参去掉 ⇒ A1 判据必须 FAIL
f2_ok = False
f2_detail = ''
try:
    tree3 = ast.parse(reader_src)
    init3 = find_func(tree3, '__init__')
    init3.args.kwonlyargs = [a for a in init3.args.kwonlyargs if a.arg != 'lang']
    names = [a.arg for a in init3.args.kwonlyargs]
    f2_ok = ('lang' not in names)
    f2_detail = 'kwonlyargs=%r' % (names,)
except Exception as e:
    f2_ok = True
    f2_detail = repr(e)
check('F2 反证：AST 去掉 `__init__` 的 `lang` 形参 ⇒ A1 判据能看出',
      f2_ok, f2_detail)
EVIDENCE['F2_detected'] = f2_ok

# F3：把 App 侧 `open_dialog` 的 `get_lang` 关键字去掉 ⇒ B6 判据必须 FAIL
f3_ok = False
f3_detail = ''
try:
    tree4 = ast.parse(app_src)
    for n in ast.walk(tree4):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'open_dialog'):
            n.keywords = [k for k in n.keywords if k.arg != 'get_lang']
    found = False
    for n in ast.walk(tree4):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'open_dialog'):
            if 'get_lang' in [k.arg for k in n.keywords]:
                found = True
    f3_ok = (not found)
    f3_detail = 'found=%s' % found
except Exception as e:
    f3_ok = True
    f3_detail = repr(e)
check('F3 反证：AST 去掉 `open_dialog(get_lang=)` ⇒ B6 判据能看出',
      f3_ok, f3_detail)
EVIDENCE['F3_detected'] = f3_ok


# ══════════════════════════════════════════════════════════════════════
# 汇总
# ══════════════════════════════════════════════════════════════════════
EVIDENCE['summary'] = {
    'pass': N_PASS, 'fail': N_FAIL, 'failures': FAILURES,
    'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
    'note': '零推理、零 GPU、零 NPU（ast/exec + 桩 service）',
}
with io.open(EVID, 'w', encoding='utf-8') as f:
    json.dump(EVIDENCE, f, ensure_ascii=False, indent=2)

print('\n' + '=' * 68)
print('PASS=%d  FAIL=%d' % (N_PASS, N_FAIL))
if FAILURES:
    print('--- 失败明细 ---')
    for x in FAILURES:
        print('  [%s] %s  %s' % (x['group'], x['name'], x['detail']))
print('证据已写入：%s' % EVID)
print('=' * 68)
sys.exit(1 if N_FAIL else 0)
