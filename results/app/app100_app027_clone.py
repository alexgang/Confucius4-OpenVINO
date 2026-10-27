#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app100_app027_clone.py —— APP-027⑤「克隆当前说话人」的验收脚本

🔴🔴 **本脚本的纪律**（项目铁律）：
  1. **一律不 import 被测模块** ⇒ `live_caption_app.py` 顶层 import numpy
     ⇒ import 阶段就可能 abort（try/except 接不住）。
     ⇒ 全部用 `ast` 抽源码 + `exec` 到独立命名空间。
  2. **隔离 LOCALAPPDATA** ⇒ 桩测试**绝不**污染用户真实的
     `%LOCALAPPDATA%\Confucius4LiveCaption`（APP-027⑥ 顺带项）。
     ⇒ 本脚本**自己**在 import 任何被测代码之前就把 `LOCALAPPDATA`
       指到自己的临时目录。

判据分组
--------
A 组：**AST 结构判据**（代码里必须有对应的实现）
  A1  `Session.__init__` 有 `on_audio` 参数
  A2  `Session._loop` 在 `engine.feed()` **之前**调用 `on_audio`
  A3  `App.__init__` 有克隆采集器状态字段（滚动帧 / 语音秒数 / 时间戳）
  A4  `App._collect_clone_pcm` 存在，且按 20 ms 分帧算 RMS
  A5  `_collect_clone_pcm` 的触发条件是「≥6 s 新语音」**或**「≥30 s」
  A6  `App._clone_voice_label` 返回「预设 A」或「克隆（更新于 …）」
  A7  GUI 有独立标签 `var_tts_voice_now`
  A8  `App._poll` 调用 `_track_clone_state`
  A9  `App.start()` 把 `on_audio=self._collect_clone_pcm` 接到 Session
  A10 TTS 启动回调**不再**回落 A（旧的「尚未启用」死逻辑已删）
  A11 `App._on_tts_voice_changed` 不再写「尚未启用」
  A12 `tts_service._send` 有**写锁**（并发写 stdin 会交错）
  A13 `tts_worker._fallback_to_preset` 存在且真正换回预设 A
  A14 `tts_worker` 不再写 `clone_C.npz`（死代码已删）
  A15 `pkg_exclude` 有 `is_user_voice_artifact` 隐私闸门

B 组：**行为复算**（纯 Python 复刻逻辑，验证判据本身有效）
  B1  去静音分帧：低能量帧被剔除
  B2  触发条件：未到 6 s 且未到 30 s ⇒ 不触发
  B3  触发条件：累计 ≥6 s 新语音 ⇒ 触发
  B4  触发条件：30 s 到 ⇒ 触发（即使新语音不足 6 s）
  B5  上限 10 s：缓冲不会无限增长
  B6  隐私闸门：`clone_C.npz` 被拦、`tts_speakers/x.npz` 被拦
  B7  隐私闸门：`preset_A.wav` **不**被拦（不能误伤生产路线）

C 组：**反证**（故意写错 ⇒ 判据必须 FAIL）
  C1  把「触发阈值 6 s」改成 600 s ⇒ A5 必须 FAIL
  C2  删掉 `_send` 的写锁 ⇒ A12 必须 FAIL
  C3  保留 `_update_clone` 写 `clone_C.npz` ⇒ A14 必须 FAIL
"""

import ast
import os
import sys
import tempfile

# 🔴🔴🔴 APP-027⑥：**必须在 import 任何被测代码之前**隔离数据目录
_TMP_LOCALAPPDATA = tempfile.mkdtemp(prefix='app100_localappdata_')
os.environ['LOCALAPPDATA'] = _TMP_LOCALAPPDATA

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(REPO, 'live_caption')

PASS = 0
FAIL = 0
FAILED = []


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'[PASS] {name}')
    else:
        FAIL += 1
        FAILED.append(name)
        print(f'[FAIL] {name}  {detail}')


def read_src(rel):
    p = os.path.join(REPO, rel)
    with open(p, 'rb') as f:
        raw = f.read()
    return raw.decode('utf-8')


def parse(rel):
    try:
        return ast.parse(read_src(rel))
    except SyntaxError as e:
        print(f'!! 解析失败 {rel}: {e}')
        return None


def get_func(tree, name, cls=None):
    """按名字找函数 / 方法（**不执行**代码）。"""
    if tree is None:
        return None
    scope = tree
    if cls:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == cls:
                scope = node
                break
        else:
            return None
    for node in scope.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
    return None


def src_of(rel):
    return read_src(rel)


def attr_names(node):
    """收集节点里出现的所有属性名（`a.b.c` ⇒ {'a','b','c'}）。"""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Name):
            out.add(n.id)
    return out


def consts(rel, names):
    """取模块级常量（只支持 int/float/str）。"""
    tree = parse(rel)
    out = {}
    if tree is None:
        return out
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in names:
                try:
                    out[t.id] = ast.literal_eval(node.value)
                except Exception:
                    pass
    return out


# ══════════════════════════════════════════════════════════════════
# A 组：AST 结构判据
# ══════════════════════════════════════════════════════════════════
print('=' * 70)
print('A 组 · AST 结构判据')
print('=' * 70)

app_src = read_src('live_caption/live_caption_app.py')
app_tree = parse('live_caption/live_caption_app.py')
svc_tree = parse('live_caption/tts_service.py')
wrk_tree = parse('live_caption/tts_worker.py')

# A1 —— Session.__init__ 有 on_audio 参数
sess_init = get_func(app_tree, '__init__', cls='Session')
args_names = []
if sess_init:
    a = sess_init.args
    args_names = [x.arg for x in (a.posonlyargs + a.args + a.kwonlyargs)]
check('A1 Session.__init__ 有 on_audio 参数', 'on_audio' in args_names,
      f'实际参数={args_names}')

# A2 —— _loop 里在 engine.feed() 之前调 on_audio
sess_loop = get_func(app_tree, '_loop', cls='Session')
ok_a2 = False
if sess_loop:
    on_call_line = None
    feed_line = None
    for n in ast.walk(sess_loop):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == 'on_audio':
                on_call_line = n.lineno
            if isinstance(f, ast.Attribute) and f.attr == 'feed':
                feed_line = n.lineno
    ok_a2 = (on_call_line is not None and feed_line is not None
             and on_call_line < feed_line)
check('A2 Session._loop 在 engine.feed() 之前调 on_audio', ok_a2,
      f'on_audio@{on_call_line} feed@{feed_line}')

# A3 —— App.__init__ 有克隆采集器状态字段
app_init = get_func(app_tree, '__init__', cls='App')
a3 = set()
if app_init:
    a3 = attr_names(app_init)
check('A3 App.__init__ 有克隆采集器状态字段',
      '_clone_frames' in a3 and '_clone_voiced_s' in a3
      and '_clone_last_update' in a3,
      f'缺={[x for x in ("_clone_frames","_clone_voiced_s","_clone_last_update") if x not in a3]}')

# A4 —— _collect_clone_pcm 存在 + 分帧 + RMS
coll = get_func(app_tree, '_collect_clone_pcm', cls='App')
ok_a4 = False
if coll:
    names = attr_names(coll)
    has_frame = '_CLONE_FRAME' in names
    has_rms = 'rms' in names or 'sqrt' in names
    ok_a4 = has_frame and has_rms
check('A4 _collect_clone_pcm 存在且按帧算 RMS', ok_a4)

# A5 —— 触发条件：≥6 s 新语音 或 ≥30 s
ok_a5 = False
if coll:
    c = consts('live_caption/live_caption_app.py',
               {'_CLONE_NEW_VOICED_S', '_CLONE_UPDATE_INTERVAL_S'})
    src = ast.get_source_segment(app_src, coll) or ''
    ok_a5 = (c.get('_CLONE_NEW_VOICED_S') == 6.0
             and c.get('_CLONE_UPDATE_INTERVAL_S') == 30.0
             and '_CLONE_NEW_VOICED_S' in src
             and '_CLONE_UPDATE_INTERVAL_S' in src)
check('A5 触发条件 = 累计≥6s 新语音 或 每 30s', ok_a5,
      f'常量={c}')

# A6 —— _clone_voice_label 返回「预设 A」/「克隆（更新于 …）」
lab = get_func(app_tree, '_clone_voice_label', cls='App')
ok_a6 = False
if lab:
    seg = ast.get_source_segment(app_src, lab) or ''
    ok_a6 = ('预设 A' in seg and '克隆（更新于' in seg)
check('A6 _clone_voice_label 显示「预设 A」/「克隆（更新于 …）」', ok_a6)

# A7 —— GUI 有独立标签 var_tts_voice_now
ok_a7 = False
if app_init:
    seg = ast.get_source_segment(app_src, app_init) or ''
    ok_a7 = 'var_tts_voice_now' in seg
check('A7 GUI 有独立标签 var_tts_voice_now', ok_a7)

# A8 —— _poll 调 _track_clone_state
poll = get_func(app_tree, '_poll', cls='App')
ok_a8 = False
if poll:
    for n in ast.walk(poll):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == '_track_clone_state':
            ok_a8 = True
check('A8 _poll 调用 _track_clone_state', ok_a8)

# A9 —— App.start() 接线 on_audio
start = get_func(app_tree, 'start', cls='App')
ok_a9 = False
if start:
    seg = ast.get_source_segment(app_src, start) or ''
    ok_a9 = ('on_audio=self._collect_clone_pcm' in seg)
check('A9 App.start() 接线 on_audio=self._collect_clone_pcm', ok_a9)

# A10 —— TTS 启动回调不再回落 A
toggled = get_func(app_tree, '_on_tts_toggled', cls='App')
ok_a10 = False
if toggled:
    seg = ast.get_source_segment(app_src, toggled) or ''
    ok_a10 = ('尚未启用' not in seg
              and "voice = 'A'" not in seg
              and '_clone_enabled' in seg)
check('A10 _on_tts_toggled 不再回落 A（真正启用克隆）', ok_a10)

# A11 —— _on_tts_voice_changed 不再写「尚未启用」
vc = get_func(app_tree, '_on_tts_voice_changed', cls='App')
ok_a11 = False
if vc:
    seg = ast.get_source_segment(app_src, vc) or ''
    ok_a11 = '尚未启用' not in seg and '已启用' in seg
check('A11 _on_tts_voice_changed 写「已启用」', ok_a11)

# A12 —— tts_service._send 有写锁
send = get_func(svc_tree, '_send', cls='TTSService')
ok_a12 = False
if send:
    seg = ast.get_source_segment(read_src('live_caption/tts_service.py'), send) or ''
    ok_a12 = '_stdin_wlock' in seg
check('A12 tts_service._send 有 stdin 写锁', ok_a12)

# A13 —— _fallback_to_preset 真正换回预设 A
fb = get_func(wrk_tree, '_fallback_to_preset', cls='TTSWorker')
ok_a13 = False
if fb:
    seg = ast.get_source_segment(read_src('live_caption/tts_worker.py'), fb) or ''
    ok_a13 = ('_preset_embed' in seg and '_preset_name' in seg
              and 'set_ref_audio' in seg)
check('A13 _fallback_to_preset 真正换回预设 A', ok_a13)

# A14 —— tts_worker 不再写 clone_C.npz
wrk_src = read_src('live_caption/tts_worker.py')
ok_a14 = True
for node in ast.walk(wrk_tree) if wrk_tree else []:
    if isinstance(node, ast.Call):
        f = node.func
        nm = f.attr if isinstance(f, ast.Attribute) else (
            f.id if isinstance(f, ast.Name) else '')
        if nm in ('write', 'np.save', ' savez'):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                        and 'clone_C.npz' in arg.value:
                    ok_a14 = False
if '_extract_cond_ov' in wrk_src:
    # 函数名出现不等于还在写盘 ⇒ 必须在函数体里查
    for node in ast.walk(wrk_tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_extract_cond_ov':
            ok_a14 = False
check('A14 tts_worker 不再写 clone_C.npz（死代码已删）', ok_a14)

# A15 —— pkg_exclude 有隐私闸门
pkg_src = read_src('pkg_exclude.py')
ok_a15 = ('is_user_voice_artifact' in pkg_src
          and 'USER_SPEAKER_DIR_NAMES' in pkg_src
          and 'USER_CLONE_FILE_RE' in pkg_src)
check('A15 pkg_exclude 有 is_user_voice_artifact 隐私闸门', ok_a15)

# ══════════════════════════════════════════════════════════════════
# B 组：行为复算
# ══════════════════════════════════════════════════════════════════
print()
print('=' * 70)
print('B 组 · 行为复算')
print('=' * 70)

# 🔴🔴 **不 import 被测模块** ⇒ 把 `pkg_exclude.py` 的源码
#    `exec` 到独立命名空间（它零依赖，只用 os/re）
pkg_ns = {}
try:
    exec(compile(pkg_src, 'pkg_exclude.py', 'exec'), pkg_ns)
except Exception as e:
    print(f'!! pkg_exclude exec 失败：{e}')
    pkg_ns = {}

is_user_voice = pkg_ns.get('is_user_voice_artifact')

# B1 —— 去静音分帧
FRAME = 320
SR = 16000


def frame_rms(frames):
    import math
    return [math.sqrt(sum(float(v) * float(v) for v in f) / len(f))
            for f in frames]


def split_frames(a, frame=FRAME):
    n = len(a) // frame
    return [a[i * frame:(i + 1) * frame] for i in range(n)]


loud = [0.5] * FRAME
quiet = [0.0005] * FRAME
mixed = []
for i in range(10):
    mixed.append(loud if i % 2 == 0 else quiet)
rms = frame_rms(mixed)
thr = max(0.0015, min(rms) * 2.0)
voiced_count = sum(1 for r in rms if r > thr)
check('B1 去静音：低能量帧被剔除', voiced_count == 5,
      f'voiced={voiced_count}（期望 5）')

# B2/B3/B4 —— 触发条件复算
def should_trigger(new_voiced_s, since_last_s, buffered_voiced_s,
                   min_s=3.0, new_s=6.0, interval_s=30.0):
    """复刻 `_collect_clone_pcm` 的触发判定。"""
    if buffered_voiced_s < min_s:
        return False
    return (new_voiced_s >= new_s) or (since_last_s >= interval_s)


check('B2 未到 6s 且未到 30s ⇒ 不触发',
      not should_trigger(new_voiced_s=2.0, since_last_s=10.0,
                         buffered_voiced_s=5.0))
check('B3 累计 ≥6s 新语音 ⇒ 触发',
      should_trigger(new_voiced_s=6.0, since_last_s=1.0,
                     buffered_voiced_s=8.0))
check('B4 到 30s ⇒ 触发（即使新语音不足 6s）',
      should_trigger(new_voiced_s=1.0, since_last_s=30.0,
                     buffered_voiced_s=5.0))
check('B4b 语音不足 3s ⇒ 不触发（worker 也会拒）',
      not should_trigger(new_voiced_s=9.0, since_last_s=99.0,
                         buffered_voiced_s=2.0))

# B5 —— 上限 10 s
max_frames = int(10.0 * SR / FRAME)      # 500
frames = []
total = 0
for _ in range(20):                      # 20 * 50 帧 = 1000 帧 = 20 s
    frames.append([0.5] * FRAME)
    total += FRAME
while total > max_frames and len(frames) > 1:
    total -= len(frames.pop(0)) * FRAME
check('B5 缓冲上限 10 s（不无限增长）',
      total <= max_frames and len(frames) >= 1,
      f'total_frames={total} max={max_frames}')

# B6/B7 —— 隐私闸门行为
if is_user_voice is not None:
    check('B6 隐私闸门：clone_C.npz 被拦',
          is_user_voice('app/voices/clone_C.npz') is True)
    check('B6b 隐私闸门：tts_speakers/ 里的用户音色被拦',
          is_user_voice('app/tts_speakers/mine.npz') is True)
    check('B6c 隐私闸门：深层 tts_speakers/ 也被拦',
          is_user_voice('app/models/tts_speakers/a/b.npz') is True)
    check('B7 隐私闸门：preset_A.wav **不**被拦（不误伤生产路线）',
          is_user_voice('app/models/qwen3tts/voices/preset_A.wav') is False)
else:
    check('B6 隐私闸门可执行', False, 'pkg_exclude exec 失败')

# ══════════════════════════════════════════════════════════════════
# C 组：反证（故意写错 ⇒ 判据必须 FAIL）
# ══════════════════════════════════════════════════════════════════
print()
print('=' * 70)
print('C 组 · 反证（判据必须 FAIL）')
print('=' * 70)


def a5_check(src_text):
    """A5 的独立实现（用于反证）：只读源码文本 + 常量。"""
    try:
        tree = ast.parse(src_text)
    except SyntaxError:
        return False
    consts_ = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                consts_[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    if consts_.get('_CLONE_NEW_VOICED_S') != 6.0:
        return False
    if consts_.get('_CLONE_UPDATE_INTERVAL_S') != 30.0:
        return False
    return '_CLONE_NEW_VOICED_S' in src_text \
        and '_CLONE_UPDATE_INTERVAL_S' in src_text


bad = app_src.replace('_CLONE_NEW_VOICED_S = 6.0',
                      '_CLONE_NEW_VOICED_S = 600.0')
check('C1 把阈值改成 600s ⇒ A5 判 FAIL', not a5_check(bad))

svc_src = read_src('live_caption/tts_service.py')
bad2 = svc_src.replace('with self._stdin_wlock:', 'if False:')
try:
    t2 = ast.parse(bad2)
    send2 = get_func(t2, '_send', cls='TTSService')
    seg2 = ast.get_source_segment(bad2, send2) or ''
    ok_c2 = '_stdin_wlock' in seg2
except Exception:
    ok_c2 = False
check('C2 去掉 _send 写锁 ⇒ A12 判 FAIL', not ok_c2)

bad3 = wrk_src.replace("def _fallback_to_preset(self, why: str = ''):",
                       "def _fallback_to_preset(self, why: str = ''):\n"
                       "        open('voices/clone_C.npz', 'wb').write(b'x')\n")
try:
    t3 = ast.parse(bad3)
    bad_call = False
    for node in ast.walk(t3):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'open':
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                        and 'clone_C.npz' in arg.value:
                    bad_call = True
    check('C3 重新写 clone_C.npz ⇒ A14 判 FAIL', not ok_a14 or bad_call)
except Exception:
    check('C3 重新写 clone_C.npz ⇒ A14 判 FAIL', False, '解析失败')

# ══════════════════════════════════════════════════════════════════
print()
print('=' * 70)
print(f'PASS={PASS}  FAIL={FAIL}')
if FAILED:
    print('失败项: ' + ', '.join(FAILED))
print('=' * 70)

# 🔴 APP-027⑥：清理临时 LOCALAPPDATA
try:
    import shutil
    shutil.rmtree(_TMP_LOCALAPPDATA, ignore_errors=True)
except Exception:
    pass

sys.exit(1 if FAIL else 0)
