# -*- coding: utf-8 -*-
"""app133 —— APP-037 C：**句首标点规范化** 的单测 + 反证。

## reviewer APP-037 C 原文

> 「句首标点（§80.7 第 1 项）reviewer 裁定：在 **tts_worker 合成前统一规范化**：
>   去掉句首的标点和空白（全角/半角），去掉后为空就不合成，记 `end_reason=empty`，
>   **不计丢句**。三道失控守卫保持不变。
>   加单测：句首"，"、"、"、"。"、"…"和纯标点各 1 条。」

## 本脚本验什么

| 组 | 内容 | 判据 |
|---|---|---|
| **A** | `_strip_lead_punct` 纯函数 | 句首「，」「、」「。」「…」各 1 条 ＋ 纯标点 1 条 ＋ 半角 ＋ 空白 ＋ **不误伤数字/字母/汉字** |
| **B** | `TTSWorker.synth` 的**空句早退路径** | 剥后为空 ⇒ `end_reason='empty'` ＋ 发 `kind='empty'` ＋ **不发 `played`** ＋ **不发句子级 `error`** ＋ jsonl 行有 `end_reason=empty` 且 `n_samples=0` |
| **C** | `TTSService` 的 `kind=='empty'` 处理 | `n_empty += 1` ＋ **不计 `n_dropped`** ＋ **从 `pending` 摘除**（否则 `drain()` 必超时）＋ 三段式不变式 `n_played + n_dropped + n_empty == n_submitted` |
| **D** | **正常句不受影响** | 有内容 ⇒ 剥掉的只有句首标点，**句中/句尾标点保留** ⇒ 语义零影响 |
| **反证** | 三条**源码级**反证 | ① 剥标点逻辑失效 ⇒ A 组必 FAIL；② 空句改发 `played` ⇒ B 组必 FAIL；③ 空句改计丢句 ⇒ C 组必 FAIL |

## 🔴 纪律

- **不 import 被测模块**（`tts_worker` 的 `import numpy` 在函数体内，
  但 `tts_service` 顶层会拉 `subprocess` 等）⇒ 一律 **`ast` 抽源码 + `exec`**
  到独立命名空间（§「验收脚本一律不 import 被测模块」）。
- **必须用带 numpy 的解释器**（`synth()` 函数体第一行就是 `import numpy as np`）
  ⇒ 本机 **system 3.12**（numpy 2.5.4）可用；
  **managed 3.13 无 numpy** ⇒ 会在 `synth()` 内 `ModuleNotFoundError`
  ⇒ 那是**解释器差异**不是产品缺陷（§「先分『代码缺陷』还是『解释器差异』」）。
- **零推理、零 GPU、零 NPU、零声卡** ⇒ 只走「空句」分支（不进任何引擎）。

## 用法

    <py312> results/app/app133_app037c_lead_punct.py
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC_ROOT = os.environ.get('APP133_SRC_ROOT') or REPO
_SUBDIR = 'app' if os.path.isdir(os.path.join(SRC_ROOT, 'app')) else 'live_caption'

WORKER_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'tts_worker.py')
SERVICE_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'tts_service.py')

EVID_PATH = os.environ.get('APP133_EVID') or os.path.join(
    HERE, 'app133_app037c_lead_punct_evidence.json')

EVID = {'script': 'app133_app037c_lead_punct.py',
        'src_root': SRC_ROOT, 'subdir': _SUBDIR,
        'python': sys.executable,
        'groups': {}, 'checks': []}


def check(group, name, ok, detail=''):
    ok = bool(ok)
    EVID['checks'].append({'group': group, 'name': name, 'pass': ok,
                           'detail': str(detail)})
    EVID.setdefault('groups', {}).setdefault(group, []).append(bool(ok))
    print('  [%s] %-6s %s — %s' % ('PASS' if ok else 'FAIL', group, name,
                                    detail))
    return ok


# ── 源码装载（**不 import 被测模块**）──────────────────────────────
def load_ns(path, name):
    """`ast` 抽源码 + `exec` 到独立命名空间。"""
    src = open(path, 'r', encoding='utf-8').read()
    tree = ast.parse(src, filename=path)
    # 🔴 去掉 `if __name__ == '__main__':` 块 ⇒ 绝不触发 main()
    body = [n for n in tree.body
            if not (isinstance(n, ast.If)
                    and isinstance(n.test, ast.Compare)
                    and getattr(n.test.left, 'id', None) == '__name__')]
    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {'__name__': name, '__file__': path}
    exec(compile(mod, path, 'exec'), ns)
    return ns, src


def load_ns_src(src_text, name, path):
    """同上，但用**改写过的源码**（反证组用）。"""
    tree = ast.parse(src_text, filename=path)
    body = [n for n in tree.body
            if not (isinstance(n, ast.If)
                    and isinstance(n.test, ast.Compare)
                    and getattr(n.test.left, 'id', None) == '__name__')]
    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {'__name__': name, '__file__': path}
    exec(compile(mod, path, 'exec'), ns)
    return ns


# ── A 组：`_strip_lead_punct` 纯函数 ──────────────────────────────
CASES = [
    # (输入, 期望输出, 说明)
    ('，你好', '你好', '句首全角逗号'),
    ('、你好', '你好', '句首全角顿号'),
    ('。你好', '你好', '句首全角句号'),
    ('…你好', '你好', '句首省略号'),
    ('，、。…', '', '**纯标点** ⇒ 剥后为空'),
    (',你好', '你好', '句首半角逗号'),
    ('. 你好', '你好', '句首半角句号 + 空白'),
    ('　你好', '你好', '句首全角空格'),
    ('\n\t你好', '你好', '句首换行/制表'),
    ('  ', '', '纯空白 ⇒ 空'),
    ('', '', '空串'),
    ('2026年の売上', '2026年の売上', '**不误伤**数字'),
    ('Hello, world', 'Hello, world', '**不误伤**半角逗号在句中'),
    ('你好，世界', '你好，世界', '**不误伤**句中标点'),
    ('你好。', '你好。', '**不剥**句尾标点'),
    ('（你好）', '（你好）', '**不剥**括号（不在剥离集合）'),
]


def group_a(ns):
    fn = ns['_strip_lead_punct']
    g = 'A'
    for text, expect, why in CASES:
        got, stripped = fn(text)
        check(g, 'strip(%r)' % text, got == expect,
              '⇒ %r（期望 %r）｜%s｜剥掉 %r' % (got, expect, why, stripped))
    # 剥离集合必须覆盖 reviewer 点名的 4 个
    chars = ns['_LEAD_PUNCT_CHARS']
    for ch in ('\uff0c', '\u3001', '\u3002', '\u2026'):
        check(g, '集合含 %r' % ch, ch in chars, 'reviewer 点名的句首标点')
    # 半角也要
    for ch in (',', '.', '!', '?', ';', ':'):
        check(g, '集合含半角 %r' % ch, ch in chars, '全角/半角都要')


# ── B 组：`TTSWorker.synth` 的空句早退路径 ───────────────────────
def make_fake_worker(ns, jsonl_path):
    """造一个**只够跑空句分支**的假 worker 实例。"""
    W = ns['TTSWorker']
    w = object.__new__(W)          # 🔴 不跑 __init__（那会加载模型）
    w._dequeue_at = {}
    w._recv_at = {}
    w._enqueue_at = {}
    w._last_lang = None
    w._last_lang_src = None
    w._last_end_reason = None
    w._last_lead_punct = ''
    w._last_lead_punct_n = 0
    w._last_clone_active = False
    w._last_clone_mode = None
    w._last_clone_audio_s = 0.0
    w._last_spk = None
    w._last_spk_conf = None
    w._last_est_frames = None
    w._last_max_new_tokens = None
    w.player = None                # 空句路径不碰播放器
    w.out_wav = None
    w.dump_dir = None
    w.sr = 24000
    w.voice = 'A'
    w.conds = {}
    w.engine = None
    w.ov_rt = None
    w._clone_active = False
    w._clone_mode = None
    w._clone_audio_s = 0.0
    w._stop = type('S', (), {'is_set': staticmethod(lambda: False)})()
    w._jsonl_rows = []
    w._jsonl_path = jsonl_path
    w._timeline = []
    w._t0 = None
    w._synth_lock = __import__('threading').Lock()
    w._is_cancelled = lambda jid: False
    return w


def run_synth(ns, w, jid, text, lang='zh'):
    """跑一次 synth，捕获 emit 的事件序列。"""
    emitted = []
    ns['emit'] = lambda obj: emitted.append(obj)
    ns['log'] = lambda m: None
    w.synth(jid, text, None, None, lang, None)
    return emitted


def group_b(ns, tmpd):
    g = 'B'
    jsonl = os.path.join(tmpd, 'b_empty.tts.jsonl')
    w = make_fake_worker(ns, jsonl)

    # ── B1：纯标点 ⇒ 空句 ──
    emitted = run_synth(ns, w, 1, '，、。…')
    kinds = [e.get('kind') for e in emitted]
    check(g, '空句不发 played', 'played' not in kinds,
          '事件序列 = %s' % kinds)
    check(g, '空句不发句子级 error',
          not any(e.get('kind') == 'error' for e in emitted),
          '事件序列 = %s' % kinds)
    check(g, '空句发 kind=empty', 'empty' in kinds,
          '事件序列 = %s' % kinds)
    check(g, 'worker 内部 end_reason=empty',
          getattr(w, '_last_end_reason', None) == 'empty',
          '实际 = %r' % getattr(w, '_last_end_reason', None))
    check(g, '记录剥掉的标点',
          getattr(w, '_last_lead_punct', '') == '，、。…',
          '实际 = %r' % getattr(w, '_last_lead_punct', ''))

    # ── B2：jsonl 行 ──
    rows = []
    if os.path.exists(jsonl):
        with open(jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    check(g, 'jsonl 有 1 行', len(rows) == 1, '实际 = %d' % len(rows))
    if rows:
        r = rows[0]
        check(g, 'jsonl end_reason=empty', r.get('end_reason') == 'empty',
              '实际 = %r' % r.get('end_reason'))
        check(g, 'jsonl n_samples=0', r.get('n_samples') == 0,
              '实际 = %r' % r.get('n_samples'))
        check(g, 'jsonl lead_punct_stripped 非空',
              bool(r.get('lead_punct_stripped')),
              '实际 = %r' % r.get('lead_punct_stripped'))
        check(g, 'jsonl lead_punct_chars=4',
              r.get('lead_punct_chars') == 4,
              '实际 = %r' % r.get('lead_punct_chars'))

    # ── B3：正常句**不应**被空句分支吃掉 ──
    #   ⚠️ 正常句会进引擎路径 ⇒ 这里只验证「**没被空句早退**」：
    #   即事件里**没有** kind='empty'（哪怕后面因无引擎而报 error）。
    emitted2 = run_synth(ns, w, 2, '你好，世界')
    kinds2 = [e.get('kind') for e in emitted2]
    check(g, '正常句不走 empty 分支', 'empty' not in kinds2,
          '事件序列 = %s' % kinds2)


# ── C 组：`TTSService` 的 empty 事件处理 ──────────────────────────
def group_c(ns):
    g = 'C'
    S = ns['TTSService']

    def new_svc(n_submitted=0):
        """用**真实 `__init__`** 造 service（`auto=False` ⇒ 不起 worker、不碰硬件）
        ⇒ 不会漏掉任何实例属性（踩过一次：漏 `_source_end_t` ⇒ AttributeError）。"""
        svc = S(device='GPU.0', on_log=lambda m: None, auto=False)
        svc.n_submitted = n_submitted
        return svc

    svc = new_svc(n_submitted=3)
    # 提交 3 句：1 句空句（id=1）、1 句已播（id=0）、1 句在途（id=2）
    svc.pending[0] = dict(seg=0, text='你好', t=0.0)
    svc.pending[1] = dict(seg=1, text='，', t=0.0)
    svc.pending[2] = dict(seg=2, text='世界', t=0.0)
    svc._inflight.add(1)

    svc._handle_event({'kind': 'empty', 'id': 1})

    check(g, 'n_empty += 1', svc.n_empty == 1, '实际 = %d' % svc.n_empty)
    check(g, '**不计丢句**（n_dropped 不变）', svc.n_dropped == 0,
          '实际 = %d' % svc.n_dropped)
    check(g, '从 pending 摘除（drain 不会必超时）', 1 not in svc.pending,
          'pending keys = %s' % list(svc.pending.keys()))
    check(g, '从 _inflight 摘除', 1 not in svc._inflight,
          '_inflight = %s' % list(svc._inflight))

    # 🔴 三段式不变式只在**全部句子都已了结**时成立
    #   ⇒ 先把另外两句也了结（id=0 / id=2 走 `played`）。
    svc._handle_event({'kind': 'played', 'id': 0})
    svc._handle_event({'kind': 'played', 'id': 2})
    check(g, '三段式不变式 n_played+n_dropped+n_empty==n_submitted',
          svc.n_played + svc.n_dropped + svc.n_empty == svc.n_submitted,
          '%d + %d + %d == %d' % (svc.n_played, svc.n_dropped, svc.n_empty,
                                 svc.n_submitted))

    # 🔴 对照：普通句子级 error **必须**计丢句（否则会被误改成不计）
    svc2 = new_svc(n_submitted=1)
    svc2.pending[7] = dict(seg=0, text='x', t=0.0)
    svc2._handle_event({'kind': 'error', 'id': 7, 'message': 'boom'})
    check(g, '**对照**：普通句子级 error 仍计丢句', svc2.n_dropped == 1,
          'n_dropped = %d' % svc2.n_dropped)


# ── D 组：正常句语义零影响 ───────────────────────────────────────
def group_d(ns):
    g = 'D'
    fn = ns['_strip_lead_punct']
    for text, expect in (('你好，世界', '你好，世界'),
                         ('你好。', '你好。'),
                         ('2026年の売上', '2026年の売上'),
                         ('Hello, world', 'Hello, world')):
        got, _ = fn(text)
        check(g, '不改变内容 %r' % text, got == expect,
              '⇒ %r' % got)


# ── 反证组：源码级注入 ⇒ 判据必须 FAIL ───────────────────────────
def group_x(ns, src_worker, src_service, tmpd):
    g = 'X'
    # ① 剥标点逻辑失效（还原成「不剥」）
    broken = src_worker.replace(
        "    if not text:\n        return '', ''",
        "    if not text:\n        return '', ''\n    return text, ''  # <<反证注入>>",
        1)
    if broken != src_worker:
        ns_b = load_ns_src(broken, 'app133_x_worker', WORKER_PATH)
        fn = ns_b['_strip_lead_punct']
        got, _ = fn('，你好')
        check(g, '① 剥标点失效 ⇒ A 组判据必 FAIL', got != '你好',
              '注入后 strip(%r) = %r（≠ 期望）' % ('，你好', got))
    else:
        check(g, '① 剥标点失效 ⇒ A 组判据必 FAIL', False,
              '❌ 注入点未命中 ⇒ 反证无效')

    # ② 空句改发 `played`
    broken2 = src_worker.replace(
        "            emit({'kind': 'empty', 'id': jid,\n"
        "                  'message': '句首标点剥离后为空，未合成'})",
        "            emit({'kind': 'played', 'id': jid,\n"
        "                  'message': '<<反证注入>> 假装播了'})",
        1)
    if broken2 != src_worker:
        ns_b2 = load_ns_src(broken2, 'app133_x_worker2', WORKER_PATH)
        jsonl = os.path.join(tmpd, 'x2.tts.jsonl')
        w = make_fake_worker(ns_b2, jsonl)
        emitted = run_synth(ns_b2, w, 1, '，、。…')
        kinds = [e.get('kind') for e in emitted]
        check(g, '② 空句改发 played ⇒ B 组判据必 FAIL', 'played' in kinds,
              '注入后事件 = %s' % kinds)
    else:
        check(g, '② 空句改发 played ⇒ B 组判据必 FAIL', False,
              '❌ 注入点未命中 ⇒ 反证无效')

    # ③ 空句改计丢句（service 侧 n_empty → n_dropped）
    broken3 = src_service.replace(
        "            if was_pending:\n                self.n_empty += 1",
        "            if was_pending:\n                self.n_dropped += 1  # <<反证注入>>",
        1)
    if broken3 != src_service:
        ns_b3 = load_ns_src(broken3, 'app133_x_service', SERVICE_PATH)
        S = ns_b3['TTSService']
        svc = S(device='GPU.0', on_log=lambda m: None, auto=False)
        svc.n_submitted = 1
        svc.pending[1] = dict(seg=0, text='，', t=0.0)
        svc._handle_event({'kind': 'empty', 'id': 1})
        check(g, '③ 空句改计丢句 ⇒ C 组判据必 FAIL',
              svc.n_dropped == 1 and svc.n_empty == 0,
              '注入后 n_dropped=%d n_empty=%d（应被判 FAIL）'
              % (svc.n_dropped, svc.n_empty))
    else:
        check(g, '③ 空句改计丢句 ⇒ C 组判据必 FAIL', False,
              '❌ 注入点未命中 ⇒ 反证无效')


def main():
    print('=' * 78)
    print('app133 —— APP-037 C：句首标点规范化（单测 + 反证）')
    print('=' * 78)
    print('解释器 = %s' % sys.executable)
    try:
        import numpy  # noqa: F401
        print('numpy = %s（可用）' % numpy.__version__)
    except Exception as e:
        print('numpy 不可用：%s' % e)
        print('❌ 本脚本必须用**带 numpy** 的解释器（synth() 体内 import numpy）')
        EVID['fatal'] = 'numpy missing: %s' % e
        _dump()
        return 2

    ns_w, src_w = load_ns(WORKER_PATH, 'app133_worker')
    ns_s, src_s = load_ns(SERVICE_PATH, 'app133_service')

    tmpd = tempfile.mkdtemp(prefix='app133_')
    try:
        group_a(ns_w)
        group_b(ns_w, tmpd)
        group_c(ns_s)
        group_d(ns_w)
        group_x(ns_w, src_w, src_s, tmpd)
    except Exception:
        traceback.print_exc()
        EVID['fatal'] = traceback.format_exc()
        _dump()
        return 1

    _dump()
    return 0


def _dump():
    tot = len(EVID['checks'])
    ok = sum(1 for c in EVID['checks'] if c['pass'])
    EVID['summary'] = {'total': tot, 'pass': ok, 'fail': tot - ok}
    with open(EVID_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(EVID, f, ensure_ascii=False, indent=2)
    print('-' * 78)
    print('合计 %d 项：PASS %d / FAIL %d' % (tot, ok, tot - ok))
    print('证据 = %s' % EVID_PATH)


if __name__ == '__main__':
    sys.exit(main())
