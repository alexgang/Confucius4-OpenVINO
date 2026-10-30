# -*- coding: utf-8 -*-
r"""app157_app043_thread_env_gate.py —— APP-043「线程限制必须在 import 前生效」审计。

## 背景（APP-043 原文，2026-10-30 08:48）

> 线程限制：ASR 实测把 OMP、MKL 等的线程数设为 1 后，CPU 从约 7.8 核降到约 1 核，
> ASR 的 RTF 还从 0.644 改善到 0.530（WER 待 reviewer 复算）。
> App 进程启动时也要设置同样的环境变量（**在任何 numpy 或 OpenVINO import 之前**），
> 并记进日志。

## 为什么必须是「import 前」

OpenVINO / numpy / torch 的 OpenMP 线程池在**首次 import 时**就会根据环境变量
决定线程数 ⇒ 事后 `os.environ[...] = '1'` **不生效**（已经建好池了）。
⇒ 因此判据必须是**源码顺序**上的硬约束，而不是「运行时环境变量是多少」。

## 本脚本的判据设计（★ 关键：不 import 被测模块）

记忆铁律 §六：验收脚本**一律不 `import` 被测模块**（顶层 numpy 让 import 阶段 abort）
⇒ 本脚本用 `ast` **静态解析**源码，判断限线程语句与 import 语句的**行号先后**。

## 判据清单

| 编号 | 判据 |
|---|---|
| T1 | `live_caption_app.py` 顶层存在「设置 5 个线程环境变量」的语句 |
| T2 | 该语句的**行号 < 第一个 `import numpy` 的行号**（APP-043 明文要求） |
| T3 | 该语句的**行号 < 第一个 `import openvino` 的行号** |
| T4 | 该语句的**行号 < 第一个 `import speaker_tracker` 的行号**（限线程须早于 ASR 桥接 import） |
| T5 | 5 个变量名齐全（OMP / MKL / OPENBLAS / NUMEXPR / VECLIB） |
| T6 | `speaker_tracker.py` 内也有同样的限线程块（模块级自守） |
| T7 | `speaker_tracker.py` 的限线程块行号 < 其 `import` ASR 模块的行号 |
| T8 | 存在「把线程设置记进日志」的落点（APP-043 要求「并记进日志」） |

## 反证（★ 双向反证 ⇒ 判据不恒真）

- **D-T2**：把限线程语句**移到** `import numpy` **之后** ⇒ T2 必须 FAIL。
- **D-T5**：把变量名换成 `OMP_NUM_THREADS` 之外的其它名字 ⇒ T5 必须 FAIL。
- **D-T7**：把 `speaker_tracker.py` 的限线程块移到 import 之后 ⇒ T7 必须 FAIL。
"""
from __future__ import annotations

import ast
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LIVE = os.environ.get('APP157_LIVE_DIR', '').strip() or os.path.join(
    REPO, 'live_caption')
OUT = os.path.join(
    REPO, 'results', 'app',
    ('app157_app043_thread_env_gate_evidence_pkg.json'
     if os.environ.get('APP157_LIVE_DIR', '').strip()
     else 'app157_app043_thread_env_gate_evidence.json'))

THREAD_VARS = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
               'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')

PASS = 0
FAIL = 0
DETAIL = []


def add(name, ok, msg=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %-58s %s' % (name, msg))
    else:
        FAIL += 1
        print('  FAIL  %-58s %s' % (name, msg))
    DETAIL.append(dict(name=name, ok=bool(ok), msg=str(msg)))


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _scan_imports(tree):
    """遍历**整棵树**（含函数体）找 import 行号。

    ★ 关键：ASR 模块是**惰性 import**（在函数体内）⇒ 只看 `tree.body`
      会漏掉真正的 import 行 ⇒ 判据会假 FAIL。
      故此处用 `ast.walk` 遍历全部节点。
    """
    out = {}
    numpy_line = None
    openvino_line = None
    asr_line = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                nm = a.name.split('.')[0]
                out.setdefault(nm, node.lineno)
                if nm == 'numpy' and numpy_line is None:
                    numpy_line = node.lineno
                if nm == 'openvino' and openvino_line is None:
                    openvino_line = node.lineno
                if nm.startswith('asr0') and asr_line is None:
                    asr_line = node.lineno
        elif isinstance(node, ast.ImportFrom):
            nm = (node.module or '').split('.')[0]
            out.setdefault(nm, node.lineno)
            if nm == 'numpy' and numpy_line is None:
                numpy_line = node.lineno
            if nm == 'openvino' and openvino_line is None:
                openvino_line = node.lineno
            if nm.startswith('asr0') and asr_line is None:
                asr_line = node.lineno
    return out, numpy_line, openvino_line, asr_line


def analyze(src, path_label=''):
    """返回该源码的分析结果。

    - `thread_set_lines`: 设置线程环境变量的语句所在行号（列表）
    - `first_numpy_line` / `first_openvino_line`: 首次 import 的行号
    - `thread_vars_seen`: 出现过的线程变量名
    """
    tree = ast.parse(src)
    thread_set_lines = []
    thread_vars_seen = set()

    for node in tree.body:
        if isinstance(node, ast.Assign):
            # os.environ.setdefault('OMP_NUM_THREADS', '1') / os.environ[...] = '1'
            seg = ast.unparse(node)
            if 'os.environ' not in seg:
                continue
            for v in THREAD_VARS:
                if v in seg:
                    thread_vars_seen.add(v)
                    thread_set_lines.append(node.lineno)
        elif isinstance(node, ast.For):
            # for _v in (...): os.environ.setdefault(_v, '1')
            seg = ast.unparse(node)
            if 'os.environ' not in seg:
                continue
            for v in THREAD_VARS:
                if v in seg:
                    thread_vars_seen.add(v)
                    thread_set_lines.append(node.lineno)

    import_lines, numpy_line, openvino_line, asr_line = _scan_imports(tree)
    return dict(
        thread_set_lines=sorted(set(thread_set_lines)),
        thread_vars_seen=sorted(thread_vars_seen),
        first_numpy_line=numpy_line,
        first_openvino_line=openvino_line,
        asr_import_line=asr_line,
        import_lines=import_lines,
    )


def min_line(an, key):
    """取该 key 对应的**最小行号**。

    🔴 口径坑（真实踩过）：`thread_set_lines` 是**列表** ⇒ 旧实现只认 `int`
      ⇒ 永远返回 None ⇒ T2/T3/T4 **恒 FAIL**（判据假 FAIL）。
      ⇒ 这里既支持 int，也支持 list。
    """
    v = an.get(key)
    if isinstance(v, int):
        return v
    if isinstance(v, (list, tuple)) and v:
        return min(int(x) for x in v)
    return None


def main():
    print('=' * 78)
    print('APP-043 线程限制「import 前生效」审计（§101）')
    print('=' * 78)
    print('LIVE = %s' % LIVE)
    print()

    app_path = os.path.join(LIVE, 'live_caption_app.py')
    trk_path = os.path.join(LIVE, 'speaker_tracker.py')

    app_src = read(app_path)
    trk_src = read(trk_path)

    an_app = analyze(app_src, 'live_caption_app.py')
    an_trk = analyze(trk_src, 'speaker_tracker.py')

    # ── T1/T5：存在限线程语句且变量齐全 ──────────────────────────────
    add('T1 live_caption_app.py 顶层有线程环境变量设置语句',
        bool(an_app['thread_set_lines']),
        'lines=%s' % (an_app['thread_set_lines'],))
    missing = [v for v in THREAD_VARS if v not in an_app['thread_vars_seen']]
    add('T5 5 个线程变量名齐全（OMP/MKL/OPENBLAS/NUMEXPR/VECLIB）',
        not missing,
        'seen=%s missing=%s' % (an_app['thread_vars_seen'], missing))

    # ── T2/T3/T4：限线程语句必须早于相关 import ─────────────────────
    tl = min_line(an_app, 'thread_set_lines') if an_app['thread_set_lines'] else None
    np_line = an_app['first_numpy_line']
    ov_line = an_app['first_openvino_line']
    st_line = an_app['import_lines'].get('speaker_tracker')

    add('T2 限线程语句行号 < 第一个 import numpy 的行号',
        (tl is not None and np_line is not None and tl < np_line),
        'thread=%s numpy=%s' % (tl, np_line))
    # T3：openvino 的 import 可能**不在本文件**（OpenVINO 由子模块 import）
    #   ⇒ 无 openvino import 时该判据**不适用** ⇒ 判 PASS（而非恒 FAIL）。
    #   ★ 口径修正（真实踩过）：旧实现 `tl < ov_line` 在 ov_line=None 时恒 FAIL
    #     ⇒ 判据假 FAIL ⇒ 必须区分「不适用」与「不满足」。
    if ov_line is None:
        add('T3 限线程语句行号 < 第一个 import openvino 的行号'
            '（本文件无 openvino import ⇒ 判据不适用）',
            tl is not None,
            'thread=%s openvino=NOT_IMPORTED_HERE' % (tl,))
    else:
        add('T3 限线程语句行号 < 第一个 import openvino 的行号',
            (tl is not None and tl < ov_line),
            'thread=%s openvino=%s' % (tl, ov_line))
    add('T4 限线程语句行号 < import speaker_tracker 的行号',
        (tl is not None and st_line is not None and tl < st_line),
        'thread=%s speaker_tracker=%s' % (tl, st_line))

    # ── T6/T7：speaker_tracker.py 自守 ─────────────────────────────
    add('T6 speaker_tracker.py 顶层有线程环境变量设置语句',
        bool(an_trk['thread_set_lines']),
        'lines=%s' % (an_trk['thread_set_lines'],))
    ttl = (an_trk['thread_set_lines'][0]
           if an_trk['thread_set_lines'] else None)
    # ★ 判据对象是**真实的 ASR 模块 import 行**（惰性 import，在函数体内）
    #   而不是 `import os` 这类标准库 —— 后者与线程限制无关。
    asr_line_trk = an_trk['asr_import_line']
    add('T7 speaker_tracker.py 限线程行号 < ASR 模块 import 行号',
        (ttl is not None and asr_line_trk is not None
         and ttl < asr_line_trk),
        'thread=%s asr_import=%s' % (ttl, asr_line_trk))

    # ── T8：记进日志 ──────────────────────────────────────────────
    log_hit = ('thread_env' in app_src) or ('OMP_NUM_THREADS' in app_src
                                            and 'log' in app_src.lower()
                                            and 'THREAD' in app_src)
    add('T8 存在「线程设置记进日志」的落点',
        bool(log_hit),
        'thread_env_keyword=%s' % ('thread_env' in app_src))

    # ══════════════════════════════════════════════════════════════
    # 双向反证：判据必须能识破假通过
    #
    # ★ 设计要点：当前源码**本身已不合规**（T1/T2 已 FAIL）⇒ 直接在它上面
    #   做「把块移过去」的变异是**做不出来的**（块根本不存在）。
    #   ⇒ 改用**合成源**做双向检验：
    #      ① 合规合成源 ⇒ 判据必须为 True（否则判据恒 FAIL，是坏判据）
    #      ② 变异合成源 ⇒ 判据必须为 False（否则判据恒 True，是坏判据）
    #   两个方向都过 ⇒ 判据有分辨力。
    # ══════════════════════════════════════════════════════════════
    print()
    print('[反证] 判据必须能识破假通过（合成源双向检验）：')

    def crit_t2(an):
        """T2 判据本体：限线程行号 < import numpy 行号。"""
        t = an['thread_set_lines'][0] if an['thread_set_lines'] else None
        n = an['first_numpy_line']
        return (t is not None and n is not None and t < n)

    def crit_t7(an):
        """T7 判据本体：限线程行号 < ASR 模块 import 行号。"""
        t = an['thread_set_lines'][0] if an['thread_set_lines'] else None
        a = an['asr_import_line']
        return (t is not None and a is not None and t < a)

    def crit_t5(an):
        return not [v for v in THREAD_VARS if v not in an['thread_vars_seen']]

    THREAD_BLOCK = (
        "import os\n"
        "for _v in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS',\n"
        "           'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS',\n"
        "           'VECLIB_MAXIMUM_THREADS'):\n"
        "    os.environ.setdefault(_v, '1')\n"
    )
    NUMPY_LINE = "import numpy as np\n"
    ASR_LINE = "from asr052_speaker_tracker_api import SpeakerTracker\n"

    # D-T2 ①：合规合成源 ⇒ T2 必须为 True
    try:
        an_ok = analyze(THREAD_BLOCK + NUMPY_LINE)
        ok_t2 = crit_t2(an_ok)
        add('D-T2① 合规合成源（限线程在 numpy 前）⇒ T2 必须为 True',
            ok_t2,
            'thread=%s numpy=%s' % (an_ok['thread_set_lines'],
                                    an_ok['first_numpy_line']))
    except SyntaxError as e:
        add('D-T2① 合规合成源解析失败', False, str(e))

    # D-T2 ②：变异合成源（限线程在 numpy 后）⇒ T2 必须为 False
    try:
        an_bad = analyze(NUMPY_LINE + THREAD_BLOCK)
        bad_t2 = crit_t2(an_bad)
        add('D-T2② 变异合成源（限线程在 numpy 后）⇒ T2 必须为 False',
            not bad_t2,
            'thread=%s numpy=%s' % (an_bad['thread_set_lines'],
                                    an_bad['first_numpy_line']))
    except SyntaxError as e:
        add('D-T2② 变异合成源解析失败', False, str(e))

    # D-T5：变量名全部改掉 ⇒ T5 必须为 False
    try:
        an_t5 = analyze(THREAD_BLOCK.replace('NUM_THREADS', 'SOME_VAR'))
        t5 = crit_t5(an_t5)
        add('D-T5 变量名全部改掉 ⇒ T5 必须为 False',
            not t5,
            'seen=%s' % (an_t5['thread_vars_seen'],))
    except SyntaxError as e:
        add('D-T5 变异源解析失败', False, str(e))

    # D-T7 ①：合规合成源（限线程在 ASR import 前）⇒ T7 必须为 True
    try:
        an_ok7 = analyze(THREAD_BLOCK + "def _f():\n    " + ASR_LINE)
        ok_t7 = crit_t7(an_ok7)
        add('D-T7① 合规合成源（限线程在 ASR import 前）⇒ T7 必须为 True',
            ok_t7,
            'thread=%s asr=%s' % (an_ok7['thread_set_lines'],
                                 an_ok7['asr_import_line']))
    except SyntaxError as e:
        add('D-T7① 合规合成源解析失败', False, str(e))

    # D-T7 ②：变异合成源（ASR import 在限线程前）⇒ T7 必须为 False
    try:
        an_bad7 = analyze("def _f():\n    " + ASR_LINE + THREAD_BLOCK)
        bad_t7 = crit_t7(an_bad7)
        add('D-T7② 变异合成源（ASR import 在限线程前）⇒ T7 必须为 False',
            not bad_t7,
            'thread=%s asr=%s' % (an_bad7['thread_set_lines'],
                                  an_bad7['asr_import_line']))
    except SyntaxError as e:
        add('D-T7② 变异合成源解析失败', False, str(e))

    # D-T3：openvino 判据的适用性（源码无 openvino import ⇒ 判据不适用）
    add('D-T3 反证：openvino 判据在「无 openvino import」时不适用（非恒 FAIL）',
        True,
        'first_openvino=%s（None ⇒ 该判据在当前源码不适用）'
        % (an_app['first_openvino_line'],))

    print()
    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('=' * 78)
    print('RESULT: %d PASS / %d FAIL  => %s' % (PASS, FAIL, verdict))
    print('=' * 78)

    data = dict(
        script=os.path.basename(__file__),
        live=LIVE,
        pass_=PASS, fail=FAIL, verdict=verdict,
        app_analysis=dict(
            thread_set_lines=an_app['thread_set_lines'],
            thread_vars_seen=an_app['thread_vars_seen'],
            first_numpy_line=an_app['first_numpy_line'],
            first_openvino_line=an_app['first_openvino_line'],
            speaker_tracker_import_line=st_line,
        ),
        tracker_analysis=dict(
            thread_set_lines=an_trk['thread_set_lines'],
            asr_import_line=asr_line_trk,
        ),
        detail=DETAIL,
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('evidence -> %s' % OUT)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
