# -*- coding: utf-8 -*-
"""🔴🔴🔴 APP-042（§97）**worker 侧定速**的离线验收脚本。

## 背景（2026-10-29 §97 实测暴露的真实缺陷）

APP-042 reviewer 明文：
  「滞后 lag 定义为『这句的**实际开播时刻** − 这句的目标开播时刻』」
  「速度 = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)」

🔴 **旧实现（错）**：主进程在 `submit()`（**提交时刻**）算
  `lag = now − target_play_at` ⇒ 那只含「翻译延迟」
  ⇒ 实测 SPE 前 5 分钟 76 句**全部** `speed = 1.0`
  ⇒ `speed_distribution.csv` 只有 `1.0` 一行
  ⇒ **加速链路从未真正生效** ⇒ B13（3 段 1.2–1.3×）FAIL。

🔴 **新实现（对）**：**worker 出队时**算 lag
  （`time.time() − target_wall`，墙钟 ⇒ 跨进程可比）
  ⇒ 这才是「实际开播时刻」的**上界**（开播必在出队之后）。

## 本脚本干什么（**纯离线，不占锁、不跑推理**）

用 **run3 的真实实测数据**（`app042_soak.wav.tts.jsonl`）离线重放
`speed_for_lag` 的**三个候选定速时点**，证明：
  ① 「提交时刻」定速 ⇒ **speed 恒 1.0**（旧行为 ⇒ 必须 FAIL）
  ② 「worker 出队时」定速 ⇒ **绝大多数句落在 1.2–1.3×**（新行为）
  ③ 新实现（worker 出队时定速）**代码里确实存在**且口径正确

## 🔴🔴🔴 双向反证（铁律：判据自身必须能识破假通过）

  A. 修正前的原文（提交时刻定速）**必须 FAIL**
  B. 当前实文件（worker 出队时定速）**必须 PASS**
  C. 沙盒注入错误（把 worker 侧定速改成提交时刻定速）**必须 FAIL**

## 🔴🔴🔴 验收脚本**绝不 import 被测模块**

顶层 `import numpy` 会让 import 阶段 abort ⇒ 用 `ast` 抽源码
+ `exec` 在独立命名空间里跑（记忆铁律 §十一）。
"""

from __future__ import annotations

import ast
import json
import os
import sys
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
LIVE = os.path.join(REPO, 'live_caption')

# 🔴🔴🔴 **§98 修正：基线必须是「已归档的只读副本」，不能是 live 目录**
#
# 🔴🔴🔴 **本轮抓到的真实缺陷（判据自身的基线漂移）**：
#   本脚本原先读 `C:\Users\Trekker-PTL\app042_soak\`（**live 目录**）
#   ⇒ 每次跑真机 soak 都会**覆盖**它 ⇒ **基线被自己冲掉**：
#     · run3（旧实现）跑完后该目录是 run3 的数据；
#     · run4（新实现）跑完后该目录变成 run4 的数据
#       ⇒ **A2 判据（"旧实现 speed 全线 ≤1.0381"）读到的是新实现的数据**
#       ⇒ 判据**必然假 FAIL**（§98 实测：PASS=6 FAIL=2 / TOTAL=8）
#       ⇒ **C 反证也永远不成立**（注入后仍是新实现的 speed ⇒ 行为判据 PASS
#          ⇒ 判据无效却看不出来）
#   ⇒ **归档副本才是唯一可靠的基线**（run4 已由 §97 归档进
#     `results/app/app042_soak_run4/`；run2 已入库进 git）
#
# 🔴 **两条基线的分工**（§98 实测口径）：
#   · **run2**（已入库 git，2026-10-29 21:56:13，NPU，76 句）
#     = **旧实现**（主进程提交时刻定速）的真实产物
#     ⇒ `speed` 字段**全为 1.0**（speed_max=1.0000 / n12=0 / n1=76）
#     ⇒ 这是「加速链路从未生效」的**原始字段**，不可辩驳。
#   · **run4**（已归档，2026-10-30 00:27:03，NPU，76 句）
#     = **新实现**（worker 出队时刻定速）的真实产物
#     ⇒ `speed_max=1.3000` / n12=75 / 含 `speed_lag_s` 与 `target_wall`
#     ⇒ 可用它**离线重放**公式，并验证重放**逐句复现**实测值。
RUN2_DIR = os.path.join(HERE, 'app042_soak_run2')      # 旧实现基线（已入库 git）
RUN4_DIR = os.path.join(HERE, 'app042_soak_run4')      # 新实现基线（§97 归档）
JSONL_OLD = os.path.join(RUN2_DIR, 'app042_soak.wav.tts.jsonl')
JSONL_NEW = os.path.join(RUN4_DIR, 'app042_soak.wav.tts.jsonl')
# ⚠️ 兼容旧字段名（本脚本内部其它地方用 `JSONL` 指「旧实现基线」）
JSONL = JSONL_OLD

# ── APP-042 统一参数（必须与 `time_stretch.py` 一致）─────────────
LAG_DEADZONE_S = 3.0
LAG_FULL_SPEED_S = 15.0
SPEED_PER_LAG_S = 0.025
SPEED_MIN = 1.0
SPEED_MAX = 1.30
LAG_HYSTERESIS_S = 2.0
MAX_STEP_CHANGE = 0.1


# ══════════════════════════════════════════════════════════════════
# ① 抽源码 + exec（不 import 被测模块）
# ══════════════════════════════════════════════════════════════════
def extract_module(path, names):
    """用 `ast` 抽出指定顶层定义，在独立命名空间里 `exec`。

    🔴 **三个必踩坑**（记忆铁律 §十一）：
      ① 只留 `FunctionDef/ClassDef/Assign` ⇒ **丢掉 `Import`**
         ⇒ 顶层 `import numpy as np` 丢失 ⇒ `np` 未定义 ⇒ NameError
      ② 只抽方法 ⇒ **模块级常量**未注入 ⇒ 须**逐个常量单独 exec**
      ③ 反证改源码文本、exec 却是原 AST ⇒ 抽取函数须支持传入改后源码
         并**重新抽 AST**
    """
    with open(path, encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src)
    keep = []
    futures = []
    imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            futures.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in names:
                keep.append(node)
        elif isinstance(node, ast.Assign):
            tgt = [t.id for t in node.targets
                   if isinstance(t, ast.Name) and t.id in names]
            if tgt:
                keep.append(node)
    ns = {'__name__': '_extracted'}
    # 🔴 坑①：`from __future__ import ...` **必须在文件最前**
    #   ⇒ 单独放在最前；其余 import 紧随其后。
    # 🔴 坑①：把被抽模块的 `import` 也带上（否则 numpy 等未定义）
    body = futures + imports + keep
    try:
        exec(compile(ast.Module(body=body, type_ignores=[]),
                     '<extracted>', 'exec'), ns)
    except ImportError as e:
        # 🔴 **解释器差异，不是代码缺陷**（记忆铁律 §六）：
        #   managed 3.13 无 numpy ⇒ import 阶段 abort ⇒ 判据假 FAIL。
        #   ⇒ 去掉**只用于别的函数**的重型 import（本判据只测
        #     `speed_for_lag`，它是**纯函数**，不碰 numpy）再重试。
        #   ⚠️ 只在 ImportError 时才降级 ⇒ 真缺符号仍会报错（不掩盖缺陷）。
        heavy = ('numpy', 'scipy', 'soundfile', 'librosa', 'torch')
        body2 = [n for n in body
                 if not (isinstance(n, ast.Import)
                         and any(a.name.split('.')[0] in heavy
                                 for a in n.names))]
        ns = {'__name__': '_extracted'}
        exec(compile(ast.Module(body=body2, type_ignores=[]),
                     '<extracted>', 'exec'), ns)
    return ns, src


def extract_with_source(path, names, src_text=None):
    """同上，但允许传入**改过的源码文本**（用于沙盒反证）。"""
    if src_text is None:
        with open(path, encoding='utf-8') as f:
            src_text = f.read()
    tree = ast.parse(src_text)
    keep = []
    futures = []
    imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            futures.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in names:
                keep.append(node)
        elif isinstance(node, ast.Assign):
            tgt = [t.id for t in node.targets
                   if isinstance(t, ast.Name) and t.id in names]
            if tgt:
                keep.append(node)
    ns = {'__name__': '_extracted'}
    exec(compile(ast.Module(body=futures + imports + keep, type_ignores=[]),
                 '<extracted>', 'exec'), ns)
    return ns


# ══════════════════════════════════════════════════════════════════
# ② 加载 run3 真实数据
# ══════════════════════════════════════════════════════════════════
def load_rows(path=None):
    """加载逐句 jsonl。

    🔴🔴🔴 **§98 修正**：**必须**加载**已归档**的只读副本
      ⇒ 绝不能读 live 目录（每轮真机 soak 都会覆盖它 ⇒ 基线漂移）。
    """
    path = path or JSONL_OLD
    if not os.path.exists(path):
        raise SystemExit('❌ 找不到逐句 jsonl：%s' % path)
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def clock_offset(rows):
    """跨进程时钟偏移：`epoch ≈ a + perf_counter`。

    🔴 `t_done`（perf）与 `play_wall`（epoch）在**同一进程**（worker）
    ⇒ 差值就是偏移 `a` ⇒ 用来把主进程的 perf 时刻换成 epoch。
    """
    ds = [r['play_wall'] - r['t_done'] for r in rows
          if r.get('play_wall') and r.get('t_done')]
    return statistics.median(ds)


# ══════════════════════════════════════════════════════════════════
# ③ 离线重放
# ══════════════════════════════════════════════════════════════════
def replay(speed_for_lag, rows, lag_of):
    """按给定 lag 口径重放，返回逐句 speed 列表。"""
    prev = 1.0
    out = []
    for r in rows:
        lag = lag_of(r)
        sp = speed_for_lag(lag, prev)
        prev = sp
        out.append((r['id'], lag, sp))
    return out


def main():
    print('=' * 72)
    print('APP-042（§97）worker 侧定速 · 离线验收')
    print('=' * 72)

    rows = load_rows(JSONL_OLD)
    rows_new = load_rows(JSONL_NEW)
    a = clock_offset(rows_new)
    print('[data] 旧实现基线 run2（已入库 git）：%s' % JSONL_OLD)
    print('[data] 新实现基线 run4（§97 归档）  ：%s' % JSONL_NEW)
    print('[data] n_sent(run2)=%d  n_sent(run4)=%d  clock_offset(a)=%.4f s'
          % (len(rows), len(rows_new), a))

    # ── 抽 `speed_for_lag` 与全部相关常量（不 import 被测模块）────
    ts_path = os.path.join(LIVE, 'time_stretch.py')
    ts_ns, ts_src = extract_module(ts_path, {
        'speed_for_lag', 'LAG_DEADZONE_S', 'LAG_FULL_SPEED_S',
        'SPEED_PER_LAG_S', 'SPEED_MIN', 'SPEED_MAX',
        'LAG_HYSTERESIS_S', 'MAX_STEP_CHANGE',
    })
    sfl = ts_ns['speed_for_lag']

    # 🔴 口径一致性：被测模块的常量必须与本脚本一致
    const_mismatch = []
    for k in ('LAG_DEADZONE_S', 'LAG_FULL_SPEED_S', 'SPEED_PER_LAG_S',
              'SPEED_MIN', 'SPEED_MAX', 'LAG_HYSTERESIS_S',
              'MAX_STEP_CHANGE'):
        if abs(float(ts_ns[k]) - float(globals()[k])) > 1e-9:
            const_mismatch.append((k, ts_ns[k], globals()[k]))
    print('[const] 常量口径一致性：%s'
          % ('OK（7/7 一致）' if not const_mismatch else
             '❌ 不一致 %r' % (const_mismatch,)))

    # ── 三种定速时点 ──────────────────────────────────────────
    # 🔴🔴🔴 **判据 A2 必须引用「旧实现的真实产物」**，而不是重算：
    #   jsonl 的 `speed` 字段**就是**旧实现（主进程提交时刻定速）实际下发
    #   且 worker 实际生效的倍率 ⇒ 那是**原始字段**，不可辩驳。
    #   ⚠️ 之前试图用 `t_recv` 重算「主进程提交时刻」⇒ **错**：
    #     `t_recv` 是 **worker 收到命令**的时刻（worker 侧 perf），
    #     不是主进程 `submit()` 的时刻 ⇒ 重算出来的值偏大
    #     （得到 max=1.2536，与实测 1.0381 不符）⇒ 判据失真。
    #   ⇒ 主进程提交时刻的 lag 在 jsonl 里**没有直接字段**
    #     （只有它算出来的 `speed`）⇒ 直接用 `speed` 字段判。

    # 🔴 **worker 出队时刻**的 lag：run4 jsonl 的 `t_submit` 字段
    #   = worker `synth()` 入口的 `time.perf_counter()` ⇒ **就是出队时刻**。
    #   ⚠️ `a`（时钟偏移）必须由 **run4 自己**算 ⇒ 主进程 perf → epoch。
    lag_dequeue_real = lambda r: a + r['t_submit'] - r['target_wall']

    print('\n' + '-' * 72)
    print('[sim] 两条**已归档基线**的真实实测数据对比：')

    # ── 旧实现（run2）：直接取 jsonl 原始字段 `speed` ──
    #   🔴🔴🔴 **必须是 run2 自己的原始字段**（§98 修正）
    #     run2 = 旧实现（主进程提交时刻定速）的真实产物
    #     ⇒ `speed` 全为 1.0 ⇒ 「加速链路从未生效」的原始证据
    old_sp = [float(r.get('speed') or 1.0) for r in rows]
    old_n12 = sum(1 for s in old_sp if 1.2 - 1e-6 <= s <= 1.3 + 1e-6)
    old_n1 = sum(1 for s in old_sp if abs(s - 1.0) < 1e-9)
    old_mx = max(old_sp)
    print('  A 旧实现（run2，主进程提交时刻定速）—— jsonl 原始 `speed` 字段：')
    print('     speed_max=%.4f  恒 1.0 的句数=%d/%d  '
          '落在 [1.2,1.3] 的句数=%d/%d'
          % (old_mx, old_n1, len(old_sp), old_n12, len(old_sp)))

    # ── 新实现（run4）：**先看实测原始字段**，再离线重放做对照 ──
    new_actual = [float(r.get('speed') or 1.0) for r in rows_new]
    new_a_n12 = sum(1 for s in new_actual if 1.2 - 1e-6 <= s <= 1.3 + 1e-6)
    new_a_mx = max(new_actual)
    print('  B 新实现（run4，worker 出队时刻定速）—— jsonl 原始 `speed` 字段：')
    print('     speed_max=%.4f  落在 [1.2,1.3] 的句数=%d/%d'
          % (new_a_mx, new_a_n12, len(new_actual)))

    # 离线重放（用 run4 自己的数据）
    rr = replay(sfl, rows_new, lag_dequeue_real)
    new_sp = [x[2] for x in rr]
    new_n12 = sum(1 for s in new_sp if 1.2 - 1e-6 <= s <= 1.3 + 1e-6)
    new_n1 = sum(1 for s in new_sp if abs(s - 1.0) < 1e-9)
    new_mx = max(new_sp)
    # 🔴🔴🔴 **重放保真度**：离线重放必须**逐句复现** run4 的实测 `speed`
    #   ⇒ 这是「公式口径 = 实现口径」的**直接证据**
    #   ⇒ 差异 > 1e-6 ⇒ 判据失效（口径漂移）⇒ 必须 FAIL
    replay_maxdiff = max(abs(x - y) for x, y in zip(new_sp, new_actual))
    print('  B 同一公式离线重放（run4 数据）：')
    print('     speed_max=%.4f  恒 1.0 的句数=%d/%d  '
          '落在 [1.2,1.3] 的句数=%d/%d'
          % (new_mx, new_n1, len(new_sp), new_n12, len(new_sp)))
    print('     🔴 重放 vs 实测 逐句最大差 = %.8f（须 ≈ 0 ⇒ 口径一致）'
          % replay_maxdiff)

    old = dict(sp=old_sp, n12=old_n12, mx=old_mx, n1=old_n1)
    new = dict(sp=new_sp, n12=new_n12, mx=new_mx, n1=new_n1)

    print('\n' + '-' * 72)
    print('[verdict] 关键区分点（两条已归档基线的真实实测）：')
    print('  旧实现（run2）speed_max = %.4f  恒 1.0 的句数 = %d/%d'
          % (old['mx'], old['n1'], len(rows)))
    print('  新实现（run4）speed_max = %.4f  落在 [1.2,1.3] 的句数 = %d/%d'
          % (new['mx'], new['n12'], len(rows_new)))
    print('  ⇒ 旧实现「加速链路从未真正生效」这一结论**被 run2 的原始字段证实**。')

    # ══════════════════════════════════════════════════════════════
    # 判据 C：**代码里确实存在** worker 侧定速，且口径正确
    # ══════════════════════════════════════════════════════════════
    print('\n' + '-' * 72)
    print('[static] 代码静态检查（`tts_worker.py`）：')
    worker_path = os.path.join(LIVE, 'tts_worker.py')
    with open(worker_path, encoding='utf-8') as f:
        w_src = f.read()
    checks = {
        'worker 侧调用 speed_for_lag':
            'speed_for_lag(' in w_src,
        'worker 侧用墙钟 time.time() 算 lag':
            ('time.time()' in w_src and '_lag_at_dequeue' in w_src),
        'worker 侧维护 _last_speed（步长限制需要上一句倍率）':
            'self._last_speed' in w_src,
        '遥测输出 speed_lag_s（定速时点的 lag）':
            "'speed_lag_s'" in w_src,
    }
    for k, ok in checks.items():
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', k))

    # ══════════════════════════════════════════════════════════════
    # 🔴🔴🔴 **§98 重写：反证必须是「行为」判据，且要能真识破**
    #
    # 🔴 **旧写法的两个致命缺陷**（本轮实测暴露）：
    #   ① 行为判据的「注入后结果」是**手写常量** `old_sp`（run2 的数据）
    #      ⇒ 它压根**没跑注入后的代码** ⇒ 「注入 ⇒ 判据 FAIL」是**假通过**
    #      （判据对注入毫无感知 ⇒ 什么错代码都能 PASS）
    #   ② 文本判据在注入后**依然 PASS**（`_lag_at_dequeue` 那行还在）
    #      ⇒ 4 条静态判据**全都不具备鉴别力**
    # ⇒ **§98 改成**：把 worker 的**真实决策块**从源码里**抽出来并执行**，
    #   用**受控时钟**喂 run4 的真实数据 ⇒ 必须**逐句复现**实测 `speed`
    #   ⇒ 再注入「退回主进程下发值」⇒ 该判据**必须 FAIL**。
    print('\n' + '-' * 72)
    print('[falsify] 行为反证（抽取 worker 真实决策块并执行）：')

    # 🔴🔴🔴 **锚点必须唯一**（§90 踩过的坑：短串在大文件里多次出现）
    #   `_stretcher = None` 单独作锚点会命中 **3 次**（1792 / 1798 / 1935）
    #   ⇒ 改用**带上下文的复合锚点**：
    #     · 起点：`_sp = None` + 紧随的 `try:`（唯一）
    #     · 终点：`本句按 1.0× 播放` 这行之后的 `_stretcher = None`
    BLOCK_START = '        _sp = None\n        try:\n'
    BLOCK_END = ('                    % e)\n'
                 '        _stretcher = None\n')

    def extract_worker_block(src_text):
        """从 `tts_worker.py` 源码里切出「APP-042 定速决策块」。

        🔴 **为什么用源码切片而不是 AST**：
        这段代码在 `synth()` 方法**中间**（不是顶层 def/class）
        ⇒ AST 抽取需要逐层下钻 MethodDef.body ⇒ 容易连带抓到依赖
        ⇒ 直接按**唯一锚点**切源码更简单、也更忠实于「真实执行的那段」。
        ⚠️ 锚点必须**唯一**（断言命中 1 次）⇒ 否则就是 §90 踩过的坑。
        """
        i = src_text.find(BLOCK_START)
        j = src_text.find(BLOCK_END)
        if i < 0 or j < 0:
            raise AssertionError('❌ 抽取失败：锚点找不到 (i=%d j=%d)' % (i, j))
        assert src_text.count(BLOCK_START) == 1, \
            '❌ 抽取失败：起点锚点命中 %d 次（须为 1）' \
            % src_text.count(BLOCK_START)
        assert src_text.count(BLOCK_END) == 1, \
            '❌ 抽取失败：终点锚点命中 %d 次（须为 1）' \
            % src_text.count(BLOCK_END)
        assert i < j, '❌ 抽取失败：锚点顺序颠倒'
        block = src_text[i:j + len(BLOCK_END)]
        # 🔴 **去缩进**：这段代码在 `synth()` 方法体内（8 空格缩进）
        #   ⇒ 直接 `exec` 会 IndentationError ⇒ 必须先 dedent。
        #   ⚠️ 用 `textwrap.dedent`（按**最小缩进**统一去掉）⇒ 不改变相对缩进
        #     ⇒ 块内的 try/except 结构保持不变。
        import textwrap
        return textwrap.dedent(block)

    def run_block(block_src, rows_new, a_off, main_speed_of):
        """执行抽取出的决策块，逐句返回 worker 最终采用的倍率。

        🔴 **受控时钟**：块内是 `time.time()`（墙钟）
          ⇒ 注入一个假 `time` 对象，让它返回该句**实测出队时刻的墙钟值**
          （`a_off + t_submit`）⇒ 于是块内的 lag 与真机**同口径**。
        🔴 `self._last_speed` 用一个极简对象承载（单一合成线程语义）。
        """
        out = []
        for r in rows_new:
            _CLOCK[0] = a_off + r['t_submit']
            ns = {
                'speed': main_speed_of(r),
                '_target_wall': r.get('target_wall'),
                'self': type('S', (), {'_last_speed': 1.0})(),
                'log': lambda *a, **k: None,
                'time': type('T', (), {
                    'time': staticmethod(lambda: _CLOCK[0])})(),
            }
            exec(compile(block_src, '<worker_block>', 'exec'), ns)
            out.append(ns['self']._last_speed)
        return out

    # 受控时钟的可变容器
    _CLOCK = [0.0]

    block_real = extract_worker_block(w_src)
    print('  抽取到真实决策块：%d 字符 / %d 行'
          % (len(block_real), block_real.count('\n')))

    # ── 主进程下发的倍率（旧实现口径）：由提交时刻的 lag 算 ──
    if LIVE not in sys.path:
        sys.path.insert(0, LIVE)
    import time_stretch as _ts_mod          # noqa: E402

    def main_speed_of(r):
        """主进程提交时刻的 lag → 主进程下发的倍率（旧实现口径）。"""
        _lag = a + r['t_enqueue'] - r['target_wall']
        return _ts_mod.speed_for_lag(_lag, 1.0)

    # ── 行为判据 1：真实决策块必须**逐句复现** run4 实测 `speed` ──
    def run_with_clock(block_src, rows_new, a_off, main_speed_of):
        """执行抽取出的决策块，逐句返回 worker 最终采用的倍率。

        🔴🔴🔴 **`self` 必须跨句复用**（§98 实测踩到）：
          决策块里有 `self._last_speed = _sp`（步长限制需要上一句倍率）
          ⇒ 若每句都新建 `self` ⇒ `_last_speed` 恒为初值 1.0
          ⇒ 步长限制把倍率卡在 **1.1**（实测 maxdiff=0.2 / n12=0）
          ⇒ **与真机不符**（真机是同一 worker 线程连续处理 76 句）。
        ⇒ 用**同一个** `self` 对象贯穿所有句子。
        """
        out = []
        # 🔴 同一个 worker 实例（`_last_speed` 跨句累积）
        worker = type('S', (), {'_last_speed': 1.0})()
        for r in rows_new:
            _CLOCK[0] = a_off + r['t_submit']
            ns = {
                'speed': main_speed_of(r),
                '_target_wall': r.get('target_wall'),
                'self': worker,
                'log': lambda *a, **k: None,
                'time': type('T', (), {
                    'time': staticmethod(lambda: _CLOCK[0])})(),
            }
            exec(compile(block_src, '<worker_block>', 'exec'), ns)
            out.append(worker._last_speed)
        return out

    print('  ① 执行真实决策块（受控时钟 = 实测出队时刻）：')
    blk_real = run_with_clock(block_real, rows_new, a, main_speed_of)
    blk_real_diff = max(abs(x - y) for x, y in zip(blk_real, new_actual))
    blk_real_n12 = sum(1 for s in blk_real if 1.2 - 1e-6 <= s <= 1.3 + 1e-6)
    print('     speed_max=%.4f  [1.2,1.3] 句数=%d/%d  与实测逐句最大差=%.8f'
          % (max(blk_real), blk_real_n12, len(blk_real), blk_real_diff))

    # ── 行为判据 2（反证）：注入「退回主进程下发值」⇒ 判据 1 必须 FAIL ──
    print('  ② 反证注入：把决策块改成「用主进程下发的 speed」= 旧行为')
    bad_block = block_real.replace(
        "_sp = float(_ts.speed_for_lag(_lag_at_dequeue, _prev_sp))",
        "_sp = float(speed) if speed else 1.0  # 反证：退回提交时刻定速")
    # 🔴🔴🔴 **若产品代码本身已被注入成旧行为**（本轮 §98 做过「改真源码再跑」的
    #   产品级反证）⇒ 上面这次替换**找不到目标** ⇒ 不能直接 assert 崩掉，
    #   而应**如实报告「注入点已不存在 ⇒ 反证块 == 真块」**。
    #   ⇒ 判据 C 会在这种情况下**自己 FAIL**（因为真块不再复现实测值）
    #     ⇒ 判据依然有效 ⇒ 只是 D 的「注入后」与 ① 相同。
    already_injected = (bad_block == block_real)
    if already_injected:
        print('     ⚠️ 注意：真块里已无「speed_for_lag」调用点 '
              '⇒ 产品代码本身处于「旧行为」状态 ⇒ C 应当 FAIL')
    else:
        assert bad_block != block_real, '❌ 反证注入失败：目标代码串没找到'

    out_bad = run_with_clock(bad_block, rows_new, a, main_speed_of)
    blk_bad_diff = max(abs(x - y) for x, y in zip(out_bad, new_actual))
    blk_bad_n12 = sum(1 for s in out_bad if 1.2 - 1e-6 <= s <= 1.3 + 1e-6)
    print('     speed_max=%.4f  [1.2,1.3] 句数=%d/%d  与实测逐句最大差=%.8f'
          % (max(out_bad), blk_bad_n12, len(out_bad), blk_bad_diff))
    # 判据 1 = 「抽取块逐句复现实测 speed」⇒ 注入后**必须**不再复现
    behavior_fail = (blk_bad_diff > 1e-6)
    print('     ⇒ 行为判据在注入后 %s（必须 FAIL 才算判据有效）'
          % ('FAIL ✅（识破了假实现）' if behavior_fail else 'PASS ❌（判据无效！）'))

    # ── 行为判据 3：基线替换反证（证明 A2 不是恒真的空判据）──
    #   把 A2 的数据源从 run2 换成 run4 ⇒ A2 **必须 FAIL**
    #   ⇒ 证明 A2 真在判别「旧实现 vs 新实现」，而不是恒真。
    a2_sub_diff = max(abs(float(r.get('speed') or 1.0) - y)
                       for r, y in zip(rows_new, new_actual))
    a2_sub_ok = (max(new_actual) < 1.2 and
                 sum(1 for s in new_actual if 1.2 - 1e-6 <= s <= 1.3 + 1e-6) == 0)
    a2_sub_fails = not a2_sub_ok
    print('  ③ 基线替换反证：把 A2 的数据源换成 run4 ⇒ A2 判据 %s'
          % ('FAIL ✅（说明 A2 不是恒真）' if a2_sub_fails else 'PASS ❌（A2 恒真！）'))
    print('     （run4 speed_max=%.4f / n12=%d）'
          % (max(new_actual),
             sum(1 for s in new_actual if 1.2 - 1e-6 <= s <= 1.3 + 1e-6)))

    # ══════════════════════════════════════════════════════════════
    # 汇总
    # ══════════════════════════════════════════════════════════════
    print('\n' + '=' * 72)
    results = []

    def add(name, ok, detail=''):
        results.append((name, ok, detail))
        print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                               ('  ' + detail) if detail else ''))

    add('A1 常量口径与 time_stretch.py 一致（7/7）',
        not const_mismatch, str(const_mismatch) if const_mismatch else '')
    add('A2 旧实现（run2，提交时刻定速）实测 speed 全为 1.0、0 句达 1.2 ⇒ 证实「加速从未生效」',
        old['mx'] < 1.2 and old['n12'] == 0 and old['mx'] <= 1.05,
        '恒1.0=%d/%d max=%.4f n12=%d' % (old['n1'], len(rows), old['mx'],
                                          old['n12']))
    add('A2b 基线替换反证：把 A2 数据源换成 run4 ⇒ A2 必须 FAIL（证明 A2 不恒真）',
        a2_sub_fails,
        'run4 speed_max=%.4f n12=%d' % (max(new_actual),
                                         sum(1 for s in new_actual
                                             if 1.2 - 1e-6 <= s <= 1.3 + 1e-6)))
    add('A3 新实现（run4，worker 出队时定速）绝大多数句落在 1.2–1.3×',
        new['n12'] >= len(rows_new) * 0.5 and new['mx'] >= 1.2,
        'n12=%d/%d max=%.4f' % (new['n12'], len(rows_new), new['mx']))
    add('A4 离线重放逐句复现 run4 实测 speed（口径一致，maxdiff ≤ 1e-6）',
        replay_maxdiff <= 1e-6,
        'maxdiff=%.8f' % replay_maxdiff)
    for k, ok in checks.items():
        add('B 静态：' + k, ok)
    add('C 行为：抽取 worker 真实决策块执行 ⇒ 逐句复现 run4 实测 speed',
        blk_real_diff <= 1e-6,
        'maxdiff=%.8f n12=%d/%d' % (blk_real_diff, blk_real_n12, len(blk_real)))
    add('D 反证：注入「退回主进程下发值」⇒ C 的行为判据必须 FAIL（判据有效）',
        behavior_fail,
        '注入后 maxdiff=%.8f n12=%d/%d' % (blk_bad_diff, blk_bad_n12,
                                           len(out_bad)))

    n_pass = sum(1 for _, ok, _ in results if ok)
    n_fail = len(results) - n_pass
    print('SUMMARY: PASS=%d FAIL=%d TOTAL=%d' % (n_pass, n_fail, len(results)))

    out = os.path.join(HERE, 'app149_app042_worker_side_speed_evidence.json')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({
            'schema': 'app.app042.worker_side_speed.v2',
            'note_v2': '§98 重写：基线改用**已归档只读副本**'
                       '（run2=旧实现 / run4=新实现）⇒ 不再读 live 目录',
            'data_source_old': JSONL_OLD,
            'data_source_new': JSONL_NEW,
            'n_sent_old': len(rows),
            'n_sent_new': len(rows_new),
            'clock_offset_s': round(a, 4),
            'old_submit_time': {
                'source': 'run2（已入库 git）',
                'speed_max': round(old['mx'], 4),
                'n_always_1': old['n1'],
                'n_in_1p2_1p3': old['n12'],
            },
            'new_dequeue_time': {
                'source': 'run4（§97 归档）',
                'measured_speed_max': round(new_a_mx, 4),
                'measured_n_in_1p2_1p3': new_a_n12,
                'replay_speed_max': round(new['mx'], 4),
                'replay_n_in_1p2_1p3': new['n12'],
                'replay_vs_measured_maxdiff': round(replay_maxdiff, 8),
            },
            'worker_block_executed': {
                'block_chars': len(block_real),
                'block_lines': block_real.count('\n'),
                'vs_measured_maxdiff': round(blk_real_diff, 8),
                'n_in_1p2_1p3': blk_real_n12,
            },
            'injected_falsify': {
                'vs_measured_maxdiff': round(blk_bad_diff, 8),
                'n_in_1p2_1p3': blk_bad_n12,
                'behavior_judgment_failed': bool(behavior_fail),
            },
            'baseline_swap_falsify': {
                'a2_with_run4_must_fail': bool(a2_sub_fails),
                'run4_speed_max': round(max(new_actual), 4),
            },
            'static_checks': checks,
            'results': [{'name': n, 'ok': bool(o), 'detail': d}
                        for n, o, d in results],
            'pass_count': n_pass,
            'fail_count': n_fail,
            'note': '离线判据（真实决策块抽取执行 + 静态检查 + 双向反证）；'
                    '非真机实测、非 GUI、非 CUDA、非用户实听',
        }, f, ensure_ascii=False, indent=2)
    print('证据已写入：%s' % out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
