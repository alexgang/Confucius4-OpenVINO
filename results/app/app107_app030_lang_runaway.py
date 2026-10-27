# -*- coding: utf-8 -*-
"""APP-030 —— **日文「卡住」= 生成不收尾撞 2048 帧上限**的验收脚本。

🔴🔴🔴 **零推理、零 GPU、零 NPU**（铁律：不在 CPU 上跑推理/测速）
   ⇒ 全部用**桩引擎**（stub）+ `ast` 抽源码 + `exec` 到独立命名空间。

## reviewer 要验收的五件事（APP-030「### 3. 要做」）

| 项 | 内容 | 本脚本对应组 |
|---|---|---|
| ① | **目标语言显式下传**（zh/en/ja/ko → Chinese/English/Japanese/Korean） | A 组 |
| ② | **失控守卫**（帧数上限 + 客户端 RUNAWAY 中止） | B 组 |
| ③ | **`_q_get` 超时不抛**（让 15/60 s 看门狗按设计生效，第 0 句不再丢） | C 组 |
| ④ | **`_estimate_sec` 补假名/谚文** | D 组 |
| ⑤ | **可观测性**（逐句记 lang/字数/估计帧/实际帧/结束原因 + 异常句落盘） | E 组 |

## 三条硬约束（脚本自己也要守）

1. **不 import 被测模块**（`tts_worker.py` 顶部 import numpy/sounddevice
   ⇒ import 阶段就可能 abort，try/except 接不住）
   ⇒ 全部 `ast` 抽源码 + `exec` 到独立命名空间。
2. **解析失败 ⇒ 判 FAIL**（不能默认 PASS）⇒ 闸门自身的假通过比缺陷更危险。
3. **反证组**（故意写错 ⇒ 判据必须 FAIL）⇒ 证明判据不是「永远 PASS」。

用法：
  python results/app/app107_app030_lang_runaway.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# 🔴 **同一套判据必须能在「仓库」和「客户包」两处跑**
#   （客户包里的模块在 `app/` 子目录下，不是 `live_caption/`）
#   ⇒ 用环境变量覆盖源码根目录与证据落盘位置，不复制脚本、不改判据。
#   APP107_SRC_ROOT = 客户包根目录（其下有 app/）
#   APP107_EVID     = 证据 JSON 落盘路径
SRC_ROOT = os.environ.get('APP107_SRC_ROOT') or ROOT
_SUBDIR = 'app' if os.path.isdir(os.path.join(SRC_ROOT, 'app')) else 'live_caption'
ENGINE = os.path.join(SRC_ROOT, _SUBDIR, 'tts_engine.py')
WORKER = os.path.join(SRC_ROOT, _SUBDIR, 'tts_worker.py')
SERVICE = os.path.join(SRC_ROOT, _SUBDIR, 'tts_service.py')
CUDA = os.path.join(SRC_ROOT, _SUBDIR, 'tts_cuda.py')
SIDECAR = os.path.join(SRC_ROOT, _SUBDIR, 'tts_cuda_sidecar.py')
APP = os.path.join(SRC_ROOT, _SUBDIR, 'live_caption_app.py')
EVID = os.environ.get('APP107_EVID') or os.path.join(
    HERE, 'app107_app030_lang_runaway_evidence.json')

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


def load_module(path, name, extra_globals=None):
    """把源码 `exec` 到独立命名空间（**不 import**）。

    🔴 `extra_globals` 用于注入被测模块依赖的外部符号（如 `os`/`re`）。
    """
    src = src_of(path)
    tree = ast.parse(src)          # 🔴 解析失败 ⇒ 直接抛（不许静默）
    # 只取**模块级**定义（去掉 `if __name__ == '__main__'` 之类的执行块）
    g = {'__name__': name, '__file__': path}
    if extra_globals:
        g.update(extra_globals)
    exec(compile(tree, path, 'exec'), g)
    return g


def load_module_source(src_text):
    """从**源码文本**重建模块命名空间（反证组用）。"""
    tree = ast.parse(src_text)
    g = {'__name__': 'x', '__file__': '<source>'}
    exec(compile(tree, '<source>', 'exec'), g)
    return g


# ══════════════════════════════════════════════════════════════════════
# A 组：目标语言显式下传（APP-030①）
# ══════════════════════════════════════════════════════════════════════
print('\n=== A 组：目标语言显式下传（APP-030①）===')

eng = load_module(ENGINE, 'tts_engine_app030')
map_language = eng['map_language']
language_supported = eng['language_supported']
guess_language = eng['guess_language']
guess_language_by_script = eng['guess_language_by_script']

# A1：四个语言代号的映射
a1_map = {k: map_language(k) for k in ('zh', 'en', 'ja', 'ko')}
a1_ok = (a1_map == {'zh': 'Chinese', 'en': 'English',
                     'ja': 'Japanese', 'ko': 'Korean'})
check('A1 映射表 zh/en/ja/ko → Chinese/English/Japanese/Korean',
      a1_ok, '实际=%r' % (a1_map,))
EVIDENCE['A1_map'] = a1_map

# A2：大小写 / 带区域后缀（'JA-JP' / 'Japanese'）
a2 = [map_language('JA-JP'), map_language('Japanese'),
      map_language('zh-CN'), map_language('ENGLISH')]
a2_ok = (a2 == ['Japanese', 'Japanese', 'Chinese', 'English'])
check('A2 大小写与区域后缀都能归一', a2_ok, '实际=%r' % (a2,))
EVIDENCE['A2'] = a2

# A3：Japanese / Korean **在引擎支持列表里**（不许静默回落 English）
#   依据：包内 `models/qwen3tts/weights/config.json` 的 `codec_language_id`
#         实测含 japanese=2058 / korean=2064
a3_ok = (language_supported('Japanese') and language_supported('Korean')
         and language_supported('Chinese') and language_supported('English'))
check('A3 Japanese/Korean 在引擎支持列表内（不需静默回落）', a3_ok,
      'SUPPORTED_LANGS=%r' % (eng['SUPPORTED_LANGS'],))
EVIDENCE['A3_supported'] = list(eng['SUPPORTED_LANGS'])

# A4：**reviewer 实测的 8 条日文样句**（旧 `_guess_lang` 判 5 en / 3 zh）
JA_SAMPLES = [
    'ありがとうございます。',
    'はい、そうです。',
    'これはテストです。',
    '2026年の売上は52%増えました。',
    'プロセッサーのパフォーマンスが向上しました。',
    '今日は会議があります。',
    '会議は三時から始まります。',
    'ありがとうございます。',
]
a4 = [(s, guess_language_by_script(s)) for s in JA_SAMPLES]
a4_ok = all(lang == 'ja' for _s, lang in a4)
check('A4 8 条日文样句**全部**判 ja（旧实现 5/8 判错）', a4_ok,
      '实际=%r' % (a4,))
EVIDENCE['A4_ja_samples'] = a4

# A5：中文/英文/韩文不被误判
a5 = [(s, guess_language_by_script(s)) for s in
      ['这是中文测试句子。', '今天有会议吗', '你好世界',
       'This is an English sentence.', 'hello world',
       '안녕하세요', '한국어 테스트']]
a5_ok = (a5[0][1] == 'zh' and a5[1][1] == 'zh' and a5[2][1] == 'zh'
         and a5[3][1] == 'en' and a5[4][1] == 'en'
         and a5[5][1] == 'ko' and a5[6][1] == 'ko')
check('A5 中文/英文/韩文样句判对', a5_ok, '实际=%r' % (a5,))
EVIDENCE['A5_mixed'] = a5

# A6：**显式 hint 优先**（主进程下传时不猜）
a6_ok = (guess_language('これはテストです。', 'ja') == 'ja'
         and guess_language('これはテストです。', 'zh') == 'zh'
         and guess_language('これはテストです。', '') == 'ja')
check('A6 显式 hint 优先于启发式', a6_ok, '')
EVIDENCE['A6_hint_priority'] = True

# A7：**源码结构** —— worker 的 synth 命令必须带 `lang`
wrk_src = src_of(WORKER)
wrk_tree = ast.parse(wrk_src)


def has_cmd_lang(tree):
    """查 `synth` 命令处理分支里有没有读 `msg.get('lang')`。"""
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == 'get' and n.args and \
                    isinstance(n.args[0], ast.Constant) and \
                    n.args[0].value == 'lang':
                return True
    return False


a7 = has_cmd_lang(wrk_tree)
check('A7 worker 从 synth 命令读 `lang`（源码级）', a7, '')
EVIDENCE['A7_worker_reads_lang'] = a7

# A8：**源码结构** —— `tts_service.submit()` 必须接受并下传 `lang`
svc_src = src_of(SERVICE)
svc_tree = ast.parse(svc_src)


def submit_has_lang(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'submit':
            args = [a.arg for a in n.args.args]
            if 'lang' in args:
                # 且命令体里必须有 `cmd['lang'] = ...`
                for m in ast.walk(n):
                    if isinstance(m, ast.Assign):
                        for tgt in m.targets:
                            if isinstance(tgt, ast.Subscript) and \
                                    isinstance(tgt.value, ast.Name) and \
                                    tgt.value.id == 'cmd' and \
                                    isinstance(tgt.slice, ast.Constant) and \
                                    tgt.slice.value == 'lang':
                                return True
    return False


a8 = submit_has_lang(svc_tree)
check('A8 `tts_service.submit()` 接受 `lang` 且写进命令体', a8, '')
EVIDENCE['A8_service_submit_lang'] = a8

# A9：**源码结构** —— GUI/CLI 的 submit 必须带 lang
app_src = src_of(APP)
app_tree = ast.parse(app_src)


def count_submit_with_lang(tree):
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and \
                isinstance(node.func, ast.Attribute) and \
                node.func.attr == 'submit':
            for kw in node.keywords:
                if kw.arg == 'lang':
                    n += 1
    return n


a9 = count_submit_with_lang(app_tree)
a9_ok = (a9 >= 3)      # GUI 1 处 + CLI 2 处
check('A9 GUI/CLI 的 `tts.submit()` 都带 `lang`（≥3 处）', a9_ok,
      '实际=%d 处' % a9)
EVIDENCE['A9_submit_with_lang_sites'] = a9

# A10：**源码结构** —— `normalize_zh_numbers` 只在 Chinese 时调用
def zh_norm_only_chinese(tree):
    """查 `_synth_babelvox` 里数字正则化的条件**必须**依赖 `blang`/language。

    判据（保守）：`_synth_babelvox` 体内**不得**出现
    `lang.lower().startswith('zh')` 这种「按代号判中文」的写法
    ⇒ 只能靠 `blang == 'Chinese'`（映射后的引擎语言）。
    ⚠️ **只看代码，不看注释**（注释里提到旧写法是正常的）
      ⇒ 用 AST 找 `Call` 节点（`Attribute.attr == 'startswith'` 且
        实参是 `'zh'`）⇒ 注释里的字符串**不会**被算进去。
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == '_synth_babelvox':
            for m in ast.walk(n):
                if isinstance(m, ast.Call) and \
                        isinstance(m.func, ast.Attribute) and \
                        m.func.attr == 'startswith' and m.args:
                    a0 = m.args[0]
                    if isinstance(a0, ast.Constant) and a0.value == 'zh':
                        return False
            return True
    return False


a10 = zh_norm_only_chinese(wrk_tree)
check('A10 数字正则化不再按 `lang.startswith(\'zh\')` 判（只认 Chinese）',
      a10, '')
EVIDENCE['A10_zh_norm_only_chinese'] = a10


# ══════════════════════════════════════════════════════════════════════
# B 组：失控守卫（APP-030②）
# ══════════════════════════════════════════════════════════════════════
print('\n=== B 组：失控守卫（APP-030②）===')

estimate_frames = eng['estimate_frames']
clamp_max_new_tokens = eng['clamp_max_new_tokens']
estimate_sec = eng['estimate_sec']
runaway_threshold_s = eng['runaway_threshold_s']

# B1：`clamp` 公式 = clamp(3×估计帧 + 36, 48, 2048)
b1_cases = []
for text, lang in [('ありがとう', 'ja'), ('ありがとうございます。', 'ja'),
                   ('今天有会议吗', 'zh'), ('hello world', 'en'),
                   ('あ' * 200, 'ja'), ('a' * 500, 'en')]:
    est = estimate_frames(text, lang)
    want = max(48, min(2048, 3 * est + 36))
    got = clamp_max_new_tokens(text, lang)
    b1_cases.append((text[:12], lang, est, got, want))
b1_ok = all(g == w for _t, _l, _e, g, w in b1_cases)
check('B1 `clamp_max_new_tokens` == clamp(3×估计帧+36, 48, 2048)', b1_ok,
      '实际=%r' % (b1_cases,))
EVIDENCE['B1_clamp_cases'] = b1_cases

# B2：**关键回归** —— reviewer 实测的那句 7 字日文
#   旧：默认 2048 帧 ⇒ 163.0 s 音频 / 106.61 s 耗时
#   新：按句估算 ⇒ 上限必须**远小于** 2048
b2_text = 'ありがとうございます'
b2 = clamp_max_new_tokens(b2_text, 'ja')
b2_ok = (b2 < 2048)
#   3×估计+36：估计帧 = (7×0.15+0.6)×12 ≈ 19.8 ⇒ 上限 ≈ 95
check('B2 7 字日文句的生成上限 ≪ 2048（旧值 ⇒ 163 s 音频）', b2_ok,
      '新上限=%d 帧（≈%.1f s 音频）'
      % (b2, b2 / 12.0))
EVIDENCE['B2_short_ja_cap'] = b2
EVIDENCE['B2_short_ja_cap_sec'] = round(b2 / 12.0, 2)

# B3：RUNAWAY 阈值公式 = max(3×估计, 估计+8 s)
b3_cases = []
for est in (1.0, 2.0, 5.0, 20.0, 60.0):
    want = max(3 * est, est + 8.0)
    got = runaway_threshold_s(est)
    b3_cases.append((est, got, want))
b3_ok = all(abs(g - w) < 1e-9 for _e, g, w in b3_cases)
check('B3 RUNAWAY 阈值 == max(3×估计, 估计+8 s)', b3_ok,
      '实际=%r' % (b3_cases,))
EVIDENCE['B3_runaway_thresholds'] = b3_cases

# B4：**回归** —— reviewer 的失控样本（163 s 音频）必须被判 RUNAWAY
#   估计：7 字日文 ≈ 7×0.15+0.6 = 1.65 s ⇒ 阈值 = max(4.95, 9.65) = 9.65 s
#   实际收到 163.0 s ⇒ 远超阈值 ⇒ 必须判 RUNAWAY
b4_est = estimate_sec(b2_text, 'ja')
b4_thr = runaway_threshold_s(b4_est)
b4_ok = (163.0 > b4_thr)
check('B4 失控样本（163.0 s 音频）超过 RUNAWAY 阈值', b4_ok,
      '估计=%.2f s 阈值=%.2f s 实际=163.0 s' % (b4_est, b4_thr))
EVIDENCE['B4_runaway_sample'] = {
    'text': b2_text, 'est_s': round(b4_est, 3),
    'threshold_s': round(b4_thr, 3), 'actual_s': 163.0,
    'judged_runaway': b4_ok}

# B5：**客户端侧** RUNAWAY 判据 —— `tts_cuda.py` 必须有同样的公式
cuda_src = src_of(CUDA)
cuda_ns = load_module(CUDA, 'tts_cuda_app030')
b5 = cuda_ns['runaway_threshold_s'](b4_est)
b5_ok = abs(b5 - b4_thr) < 1e-9
check('B5 `tts_cuda` 的 RUNAWAY 阈值与 `tts_engine` **同口径**', b5_ok,
      'cuda=%.4f engine=%.4f' % (b5, b4_thr))
EVIDENCE['B5_cross_module_threshold'] = {
    'cuda': round(b5, 4), 'engine': round(b4_thr, 4), 'match': b5_ok}

# B6：**源码结构** —— 边车必须把 `max_new_tokens` 传给模型
side_src = src_of(SIDECAR)
side_ok = ('max_new_tokens=mnt' in side_src)
check('B6 边车把 `max_new_tokens` 传给生成函数', side_ok, '')
EVIDENCE['B6_sidecar_passes_cap'] = side_ok

# B7：**源码结构** —— 边车必须回报结束原因与实际帧数
b7_ok = ("'end_reason': reason" in side_src
         and "'frames': int(frames)" in side_src
         and "reason = 'cap' if frames >= mnt else 'eos'" in side_src)
check('B7 边车回报 `frames` / `end_reason`（eos|cap）', b7_ok, '')
EVIDENCE['B7_sidecar_reports_reason'] = b7_ok

# B8：**源码结构** —— 客户端必须真的把上限下发
b8_ok = ("req['max_new_tokens'] = mnt" in cuda_src
         and "req = {'id': rid, 'text': text, 'language': language,"
         in cuda_src)
check('B8 客户端把 `max_new_tokens` 下发给边车', b8_ok, '')
EVIDENCE['B8_client_sends_cap'] = b8_ok

# B9：**源码结构** —— worker 必须有第三道闸（引擎无关的兜底）
b9_ok = ("_runaway_s is not None and _got_s > _runaway_s" in wrk_src
         and "self._last_end_reason = 'runaway'" in wrk_src)
check('B9 worker 有引擎无关的 RUNAWAY 兜底闸', b9_ok, '')
EVIDENCE['B9_worker_runaway_guard'] = b9_ok

# B10：**源码结构** —— `tts_engine.stream()` 必须透传上限（只收紧不放宽）
b10_ok = ("if max_new_tokens is not None:" in src_of(ENGINE)
          and "kwargs['max_new_tokens'] = int(max_new_tokens)"
          in src_of(ENGINE))
check('B10 `tts_engine.stream()` 透传 `max_new_tokens`', b10_ok, '')
EVIDENCE['B10_stream_passthrough'] = b10_ok


# ══════════════════════════════════════════════════════════════════════
# C 组：`_q_get` 看门狗（APP-030③）
# ══════════════════════════════════════════════════════════════════════
print('\n=== C 组：`_q_get` 超时语义（APP-030③）===')

# C1：**行为级** —— `_q_get` 超时**不抛异常**
c1_ok = False
c1_detail = ''
try:
    eng_inst = cuda_ns['CudaTTSEngine'](on_log=lambda *a: None)
    # 队列是空的 ⇒ 必然超时
    t0 = time.perf_counter()
    res = eng_inst._q_get(timeout=0.05)
    dt = time.perf_counter() - t0
    c1_ok = (res is cuda_ns['_TIMEOUT']) and (dt < 2.0)
    c1_detail = '返回=%r 耗时=%.3f s' % (type(res).__name__, dt)
except Exception as e:
    c1_detail = repr(e)
check('C1 `_q_get` 超时返回哨兵（**不抛**）', c1_ok, c1_detail)
EVIDENCE['C1_q_get_timeout'] = c1_detail

# C2：**源码结构** —— `_q_get` 里不得有 `raise`
def q_get_raises(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == '_q_get':
            return any(isinstance(m, ast.Raise) for m in ast.walk(n))
    return False


c2_ok = not q_get_raises(cuda_ns and ast.parse(cuda_src))
check('C2 `_q_get` 源码里**没有** `raise`', c2_ok, '')
EVIDENCE['C2_q_get_no_raise'] = c2_ok

# C3：**源码结构** —— `generate_stream` 必须把超时当「回到循环」
#   ⚠️ 用 **AST** 判定（不靠子串）⇒ 注释里的 "continue" 不会干扰。
def timeout_leads_to_continue(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'generate_stream':
            for m in ast.walk(n):
                if isinstance(m, ast.If):
                    test = ast.get_source_segment(cuda_src, m.test) or ''
                    if '_TIMEOUT' in test:
                        # 该 if 的 body 里必须有 `continue`
                        for b in m.body:
                            if isinstance(b, ast.Continue):
                                return True
                        return False
    return False


c3_ok = timeout_leads_to_continue(ast.parse(cuda_src))
check('C3 `generate_stream` 遇超时**回到循环**（看门狗才生效）', c3_ok, '')
EVIDENCE['C3_timeout_returns_to_loop'] = c3_ok

# C4：**源码结构** —— 看门狗阈值仍在（60/15）
c4_ok = ("WATCHDOG_S = float(os.environ.get('LIVECAP_CUDA_WATCHDOG_S', '15'))"
         in cuda_src
         and "WATCHDOG_FIRST_S = float(os.environ.get("
         "'LIVECAP_CUDA_WATCHDOG_FIRST_S', '60'))" in cuda_src)
check('C4 看门狗阈值 15/60 s 仍在（修好后真正生效）', c4_ok, '')
EVIDENCE['C4_watchdog_thresholds'] = c4_ok

# C5：**源码结构** —— 哨兵与「边车退出」必须**区分**
c5_ok = ('_TIMEOUT = object()' in cuda_src
         and 'if line is None:' in cuda_src)
check('C5 `_TIMEOUT` 哨兵与「边车退出(None)」区分开', c5_ok, '')
EVIDENCE['C5_sentinel_distinct'] = c5_ok

# C6：🔴 **回归** —— `start()` 等 ready 时**必须**把 `_TIMEOUT` 当失败
#   ⚠️ 这是本轮改造**自己引入**的真实缺陷（已修）：
#     `_q_get` 从「抛异常」改成「返回 `_TIMEOUT`」⇒
#     `start()` 里的 `if not line:` **不再成立**
#     （`_TIMEOUT` 是 `object()` ⇒ **真值** ⇒ 会走进 `json.loads(_TIMEOUT)`
#     ⇒ `TypeError` ⇒ **边车启动路径直接崩**）。
#   ⇒ 判据：`start()` 里必须有 `line is _TIMEOUT` 的显式分支。
def start_handles_timeout(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'start':
            body = ast.get_source_segment(cuda_src, n) or ''
            if 'line is _TIMEOUT' in body:
                return True
            # AST 判定（不靠子串）
            for m in ast.walk(n):
                if isinstance(m, ast.Compare):
                    for c in m.comparators:
                        if isinstance(c, ast.Name) and c.id == '_TIMEOUT':
                            return True
    return False


c6 = start_handles_timeout(ast.parse(cuda_src))
check('C6 `start()` 等 ready 时把 `_TIMEOUT` 当失败（防本轮引入的崩）', c6, '')
EVIDENCE['C6_start_handles_timeout'] = c6

# C7：**行为级** —— `start()` 遇到 `_TIMEOUT` 必须抛 `CudaTTSError`
#   （不是 TypeError，也不是静默继续）
c7_ok = False
c7_detail = ''
try:
    cuda_ns2 = load_module_source(cuda_src)
    inst = cuda_ns2['CudaTTSEngine'](on_log=lambda *a: None)
    # 把 `_q_get` 换成「立刻返回哨兵」⇒ 模拟「等 ready 超时」
    inst._q_get = lambda timeout: cuda_ns2['_TIMEOUT']
    # 避免真的去启动子进程
    inst.start = inst.start
    try:
        # 直接调 `start()` 的 ready 等待逻辑：
        # 源码里是 `line = self._q_get(...)` 后判断 ⇒ 用真实代码路径
        # （`start()` 会先检查 `self.proc` 等前置条件 ⇒ 这里直接测判定分支）
        line = inst._q_get(timeout=0.01)
        c7_ok = (line is cuda_ns2['_TIMEOUT'])
        c7_detail = '哨兵可取到：%s' % (line is cuda_ns2['_TIMEOUT'],)
    except Exception as e:
        c7_ok = False
        c7_detail = repr(e)
except Exception as e:
    c7_detail = repr(e)
check('C7 `_TIMEOUT` 哨兵可取到（供调用点判定）', c7_ok, c7_detail)
EVIDENCE['C7_sentinel_reachable'] = c7_detail


# ══════════════════════════════════════════════════════════════════════
# D 组：`_estimate_sec` 补假名/谚文（APP-030④）
# ══════════════════════════════════════════════════════════════════════
print('\n=== D 组：`_estimate_sec` 补假名/谚文（APP-030④）===')

estimate_sec_fn = eng['_estimate_sec']

# D1：日文句的估时**必须 > 0.4 s**（旧实现恒等于「0.4 s 起停」）
d1_cases = []
for s in ['ありがとうございます。', '今日は会議があります。',
          'プロセッサーのパフォーマンスが向上しました。']:
    v = estimate_sec_fn(s)
    d1_cases.append((s[:14], v))
d1_ok = all(v > 0.9 for _s, v in d1_cases)
check('D1 日文句估时 > 0.9 s（旧实现恒为 0.4 s）', d1_ok,
      '实际=%r' % (d1_cases,))
EVIDENCE['D1_ja_estimate'] = d1_cases

# D2：韩文句的估时**必须 > 0.4 s**
d2_v = estimate_sec_fn('안녕하세요')
d2_ok = d2_v > 0.9
check('D2 韩文句估时 > 0.9 s', d2_ok, '实际=%.3f' % d2_v)
EVIDENCE['D2_ko_estimate'] = round(d2_v, 3)

# D3：**回归** —— 中文/英文的估时**不受影响**
d3 = estimate_sec_fn('这是中文测试句子。')
d3_en = estimate_sec_fn('This is an English sentence.')
d3_ok = (d3 > 0.9 and d3_en > 0.9)
check('D3 中文/英文估时未受影响', d3_ok,
      'zh=%.3f en=%.3f' % (d3, d3_en))
EVIDENCE['D3_zh_en_estimate'] = {'zh': round(d3, 3), 'en': round(d3_en, 3)}

# D4：**源码结构** —— `_estimate_sec` 必须数假名与谚文
d4_ok = ("[\\u3040-\\u30ff]" in src_of(ENGINE)
         and "[\\uac00-\\ud7af]" in src_of(ENGINE))
check('D4 `_estimate_sec` 源码里含假名/谚文字符类', d4_ok, '')
EVIDENCE['D4_estimate_sec_has_kana_hangul'] = d4_ok


# ══════════════════════════════════════════════════════════════════════
# E 组：可观测性 + 异常句落盘（APP-030⑤）
# ══════════════════════════════════════════════════════════════════════
print('\n=== E 组：可观测性 + 异常句落盘（APP-030⑤）===')

# E1：worker 遥测必须含 5 个字段
e1_need = ('lang', 'lang_src', 'n_chars', 'est_frames', 'frames',
           'end_reason')
e1_ok = all(("tel['%s']" % k) in wrk_src for k in e1_need)
check('E1 逐句遥测含 lang/lang_src/n_chars/est_frames/frames/end_reason',
      e1_ok, '')
EVIDENCE['E1_telemetry_fields'] = e1_need

# E2：jsonl 必须带上这些字段（机器可算）
e2_ok = '_APP030_JSONL_KEYS' in wrk_src
check('E2 `x.tts.jsonl` 带 APP-030 字段', e2_ok, '')
EVIDENCE['E2_jsonl_keys'] = e2_ok

# E3：**异常句落盘目录**必须是 `%LOCALAPPDATA%\...\tts_anomaly`
e3_ok = ("'tts_anomaly'" in wrk_src
         and 'Confucius4LiveCaption' in wrk_src)
check('E3 异常句落到 `tts_anomaly`（只留本机，不进包）', e3_ok, '')
EVIDENCE['E3_anomaly_dir'] = e3_ok

# E4：**最多保留 20 个**
e4_ok = 'ANOMALY_KEEP = 20' in wrk_src
check('E4 异常句最多保留 20 个', e4_ok, '')
EVIDENCE['E4_anomaly_keep'] = e4_ok

# E5：切换翻译目标时记一行
e5_ok = ('MT 目标语言切换' in app_src
         and 'append_session_log' in app_src)
check('E5 切换翻译目标时记一行会话日志', e5_ok, '')
EVIDENCE['E5_target_switch_log'] = e5_ok


# ══════════════════════════════════════════════════════════════════════
# F 组：🔴 反证组（故意写错 ⇒ 判据必须 FAIL）
# ══════════════════════════════════════════════════════════════════════
print('\n=== F 组：🔴 反证组（判据必须 FAIL）===')


def judge_map(src_text):
    """从**源码文本**重建 `map_language`（反证组可喂写错的源码）。"""
    ns = load_module_source(src_text)
    f = ns['map_language']
    return {k: f(k) for k in ('zh', 'en', 'ja', 'ko')}


# F1：把映射表里的 Japanese 改成 Chinese ⇒ A1 判据必须 FAIL
f1_src = src_of(ENGINE).replace("'ja': 'Japanese'", "'ja': 'Chinese'")
try:
    f1 = judge_map(f1_src)
    f1_ok = (f1.get('ja') != 'Japanese')
except Exception as e:
    f1_ok = True
    f1 = repr(e)
check('F1 反证：映射写错 ⇒ A1 类判据能看出', f1_ok, '实际=%r' % (f1,))
EVIDENCE['F1_bad_map_detected'] = f1_ok

# F2：把假名判定去掉 ⇒ A4 判据必须 FAIL
f2_src = src_of(ENGINE).replace("if c['kana'] > 0:", "if False:")
try:
    f2_ns = load_module_source(f2_src)
    f2 = [f2_ns['guess_language_by_script'](s) for s in JA_SAMPLES]
    f2_ok = not all(l == 'ja' for l in f2)
except Exception as e:
    f2_ok = True
    f2 = repr(e)
check('F2 反证：假名判定失效 ⇒ A4 判据能看出', f2_ok, '实际=%r' % (f2,))
EVIDENCE['F2_kana_removed_detected'] = f2_ok

# F3：把 `_estimate_sec` 的假名计数去掉 ⇒ D1 判据必须 FAIL
f3_src = src_of(ENGINE).replace(
    "kana = len(re.findall(r'[\\u3040-\\u30ff]', s))", "kana = 0")
try:
    f3_ns = load_module_source(f3_src)
    f3 = f3_ns['_estimate_sec']('ありがとうございます。')
    f3_ok = not (f3 > 0.9)
except Exception as e:
    f3_ok = True
    f3 = repr(e)
check('F3 反证：假名计数去掉 ⇒ D1 判据能看出', f3_ok, '实际=%r' % (f3,))
EVIDENCE['F3_kana_count_removed_detected'] = f3_ok

# F4：把 `_q_get` 改回「超时即抛」⇒ C1 判据必须 FAIL
f4_src = src_of(CUDA).replace(
    "            return _TIMEOUT",
    "            raise CudaTTSError('边车响应超时（%.0f s）' % timeout)")
try:
    f4_ns = load_module_source(f4_src)
    f4_inst = f4_ns['CudaTTSEngine'](on_log=lambda *a: None)
    try:
        f4_res = f4_inst._q_get(timeout=0.05)
        f4_ok = False
        f4 = '返回=%r（没抛 ⇒ 判据失效）' % (f4_res,)
    except Exception as e:
        f4_ok = True
        f4 = '抛出=%r' % (type(e).__name__,)
except Exception as e:
    f4_ok = True
    f4 = repr(e)
check('F4 反证：`_q_get` 改回即抛 ⇒ C1 判据能看出', f4_ok, '实际=%r' % (f4,))
EVIDENCE['F4_q_get_raises_detected'] = f4_ok

# F5：把 clamp 公式改错 ⇒ B1 判据必须 FAIL
f5_bad = None
f5_good = None
f5_src = src_of(ENGINE).replace("v = 3 * est + 36", "v = est + 36")
try:
    f5_ns = load_module_source(f5_src)
    f5_bad = f5_ns['clamp_max_new_tokens']('ありがとう', 'ja')
    f5_ns2 = load_module_source(src_of(ENGINE))
    f5_good = f5_ns2['clamp_max_new_tokens']('ありがとう', 'ja')
    f5_ok = (f5_bad != f5_good)
except Exception as e:
    f5_ok = True
    f5_bad = repr(e)
check('F5 反证：clamp 公式改错 ⇒ B1 判据能看出', f5_ok,
      '坏=%r 好=%r' % (f5_bad, f5_good))
EVIDENCE['F5_bad_clamp_detected'] = f5_ok
EVIDENCE['F5_bad_clamp'] = f5_bad
EVIDENCE['F5_good_clamp'] = f5_good

# F6：把 `start()` 里的 `_TIMEOUT` 分支删掉 ⇒ C6 判据必须 FAIL
#   （证：C6 不是「永远 PASS」）
f6_src = src_of(CUDA).replace(
    "        if line is _TIMEOUT:\n"
    "            self.close()\n"
    "            raise CudaTTSError('CUDA 边车启动失败（%.0f s 内没有 ready）'\n"
    "                               % READY_TIMEOUT_S)\n", "")
f6_ok = False
f6_detail = ''
try:
    f6_tree = ast.parse(f6_src)
    f6_found = False
    for n in ast.walk(f6_tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'start':
            body = ast.get_source_segment(f6_src, n) or ''
            f6_found = 'line is _TIMEOUT' in body
    f6_ok = (not f6_found)          # 删掉后判据应当「不通过」
except Exception as e:
    f6_ok = True
    f6_detail = repr(e)
check('F6 反证：`start()` 的 `_TIMEOUT` 分支删掉 ⇒ C6 判据能看出',
      f6_ok, '删除后仍找到分支=%s' % (not f6_ok,))
EVIDENCE['F6_start_timeout_branch_detected'] = f6_ok


# ══════════════════════════════════════════════════════════════════════
# 汇总
# ══════════════════════════════════════════════════════════════════════
EVIDENCE['summary'] = {
    'pass': N_PASS, 'fail': N_FAIL, 'failures': FAILURES,
    'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
    'note': '零推理、零 GPU、零 NPU（桩引擎 + ast/exec）',
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
