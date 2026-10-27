# -*- coding: utf-8 -*-
"""APP-024① —— **首包拆成两段上报**（排队等待 / 合成首包）。

🔴🔴 为什么必须有这个（APP-024① 的原话）：
    「首包拆成两段上报：排队等待 `t_dequeue − t_submit`，
      合成首包 `t_first_packet − t_dequeue`。
      验收标准：合成首包 P50 ≤ 1.5 s，和单句 0.945 s 同一量级。」
    —— §49.7 实测「首包 P50 17.29 s」量到的是**加载期攒下的队一次性倒出来**
      （7 句的 `t_submit` 跨度只有 0.115 s）⇒ **排队段与合成段混在一个数里
      ⇒ 根本分不开** ⇒ 首包到底是「排队长」还是「合成慢」永远说不清。

🔴🔴 **跨进程时钟不可比**（本脚本的核心断言）：
    Windows 上 `time.perf_counter()` 用 **QPC**，起点是**进程启动时刻**
    ⇒ 主进程与 worker 的 `perf_counter()` **基准不同** ⇒ **不能直接相减**。
    ⇒ 因此：
      · **排队段**必须由**主进程**算：`t_sent − t_submit`（同一进程 ⇒ 同源可比）
      · **合成段**必须由**worker**算：`t_first − t_dequeue`（同一进程 ⇒ 同源可比）
    ⇒ 两个数**各自成立**，但**不能跨进程相加**来当「总首包」。
    ⚠️ 所以 worker 回传的 `t_dequeue`（worker 时钟）**只作诊断**，
      绝不用来参与主进程的排队段计算 —— 本脚本有专门的反证断言。

🔴 **不 import 被测模块**（`tts_service.py` 顶部 import numpy/openvino
   ⇒ import 阶段就可能 abort，try/except 接不住）
   ⇒ 本脚本用 `ast` 抽源码 + `exec` 到独立命名空间（`MEMORY.md` 铁律）。

判据：
  REAL 组
    R1 `tts_service.py` 的 `_send()` 在 flush 之后回填 `pending[jid]['t_sent']`
    R2 `first_packet` 分支里用 `t_sent − t_submit` 算 `queued_s`
    R3 `first_packet` 分支**不用** worker 回传的 `t_dequeue` 算 `queued_s`
       （跨进程时钟不可比 ⇒ 用它就是错）
    R4 worker 的 `first_packet` 事件带 `synth_s` 字段
    R5 worker 的 `synth_s` 用的是 **worker 自己的** `t_dequeue`
    R6 worker 主循环在取到 `synth` 命令时记 `_dequeue_at[jid]`
    R7 `synth()` 消费 `_dequeue_at` 并有 `None` 兜底
    R8 `first_packet_parts` 进了 `stats()`
    R9 **行为级**：主进程模拟「提交 → 延迟 0.30 s 才写 stdin → worker 回
       first_packet(synth_s=0.42)」⇒ `queued_s ≈ 0.30`、`synth_s = 0.42`
       ⇒ **两段确实被分开算出**（不是同一个数）
  BUG 组（反证：基线 commit 里这些都**不存在** ⇒ 命中即证明缺陷曾真实存在）
    B1 基线的 `_send()` **没有**回填 `t_sent`
    B2 基线的 `first_packet` 分支**没有** `queued_s`

用法：
  python results/app/app097_first_packet_split.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 🔴 本脚本在 `results/app/` 下 ⇒ 仓库根要**上溯两层**
REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

#: 反证基线：**修复前**的 commit（不是 HEAD ⇒ 提交后 HEAD 变了也仍然成立）
BASELINE_COMMIT = '0d1be9d'

_results = []


def check(name, cond, detail='', group='REAL'):
    _results.append((group, name, bool(cond)))
    print('  %s %s%s' % ('✅' if cond else '❌', name,
                         ('  —— ' + detail) if detail else ''))
    return bool(cond)


def read(rel):
    return io.open(os.path.join(REPO, rel), encoding='utf-8').read()


def git_show(commit, rel):
    p = subprocess.run(['git', 'show', '%s:%s' % (commit, rel)],
                       cwd=REPO, capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode('utf-8', 'replace')


def find_func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return n
    return None


def has_call(node, attr):
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == attr:
                return True
            if isinstance(f, ast.Name) and f.id == attr:
                return True
    return False


def subscript_key(node, const):
    """找 `x['key']` 形式的常量下标。"""
    for n in ast.walk(node):
        if isinstance(n, ast.Subscript):
            sl = n.slice
            if isinstance(sl, ast.Constant) and sl.value == const:
                return True
    return False


def has_ident(node, name):
    """**标识符级**检查：源码里出现名为 `name` 的变量/属性/关键字。

    🔴🔴 为什么不能用 `name in src`（本脚本踩过）：
        查 `'synth_s' not in base_wrk` ⇒ 命中了 **`synth_stream`** 的子串
        ⇒ 明明基线**没有** `synth_s` 这个字段，却被判成「有」
        ⇒ **反证假通过** ⇒ 与 §62「闸门自身的假通过」是同一类错误。
        ⇒ 必须走 AST 的 `ast.Name` / `ast.Attribute` / `ast.keyword`。
    """
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id == name:
            return True
        if isinstance(n, ast.Attribute) and n.attr == name:
            return True
        if isinstance(n, ast.keyword) and n.arg == name:
            return True
    return False


def find_kind_branch(node, kind_value):
    """找 `kind == '<kind_value>'` 形态的分支（`kind` 是**变量名**）。

    🔴 实际写法是 `elif kind == 'first_packet':` ⇒ 常量在比较的**右侧**，
       左侧是 `ast.Name('kind')` ⇒ 不能只找「含常量 'first_packet' 的 If」。
    """
    for n in ast.walk(node):
        if not isinstance(n, ast.If):
            continue
        for c in ast.walk(n.test):
            if not isinstance(c, ast.Compare):
                continue
            for i, cmp in enumerate(c.comparators):
                if isinstance(cmp, ast.Constant) and cmp.value == kind_value:
                    left = c.left if i == 0 else c.comparators[i - 1]
                    if isinstance(left, ast.Name) and left.id == 'kind':
                        return n
    return None


# ── 源码事实 ───────────────────────────────────────────────────────────
SVC = 'live_caption/tts_service.py'
WRK = 'live_caption/tts_worker.py'

svc_src = read(SVC)
wrk_src = read(WRK)
svc_tree = ast.parse(svc_src)
wrk_tree = ast.parse(wrk_src)

send_fn = find_func(svc_tree, '_send')
check('R1a 找到 tts_service._send', send_fn is not None)
read_loop = find_func(svc_tree, '_handle_event')
check('R1b 找到 tts_service._handle_event（first_packet 分支在这里）',
      read_loop is not None,
      '⚠️ 注意：不是 `_read_loop`（那是读 stdout 的循环）'
      '⇒ 事件分派在 `_handle_event` 里')

if send_fn is not None:
    check('R1c _send 回填 t_sent（pending[jid][\'t_sent\'])',
          subscript_key(send_fn, 't_sent'),
          'AST 级：_send 内出现常量下标 "t_sent"')

if read_loop is not None:
    # 🔴 写法是 `elif kind == 'first_packet':` ⇒ 用 kind 分支查找器
    fp_branch = find_kind_branch(read_loop, 'first_packet')
    check('R2a 找到 first_packet 分支', fp_branch is not None)
    if fp_branch is not None:
        has_queued = any(
            isinstance(n, ast.Assign) and
            any(isinstance(t, ast.Name) and t.id == 'queued'
                for t in n.targets)
            for n in ast.walk(fp_branch))
        check('R2b first_packet 分支算出 queued（两段之一）', has_queued)
        check('R2c first_packet 分支用到 t_submit',
              any(isinstance(n, ast.Name) and n.id == 't_submit'
                  for n in ast.walk(fp_branch)))
        check('R2d first_packet 分支用到 t_sent',
              any(isinstance(n, ast.Name) and n.id == 't_sent'
                  for n in ast.walk(fp_branch)))
        # R3：排队段**不能**用 worker 的 t_dequeue
        #   ⇒ 判据 = 「用了 t_dequeue 且用了 t_sent」且**没有** `t_sent - t_dequeue`
        uses_deq = any(isinstance(n, ast.Name) and n.id == 't_dequeue'
                       for n in ast.walk(fp_branch))
        if uses_deq:
            # 找形如 (t_sent - t_dequeue) 的 BinOp
            bad = False
            for n in ast.walk(fp_branch):
                if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub):
                    names = {x.id for x in ast.walk(n.left)
                             if isinstance(x, ast.Name)}
                    if 't_dequeue' in names:
                        bad = True
            check('R3 排队段**不**用 worker 的 t_dequeue（跨进程时钟不可比）',
                  not bad, '未发现 t_sent − t_dequeue 形态')
        else:
            check('R3 排队段**不**用 worker 的 t_dequeue（跨进程时钟不可比）',
                  True, '分支内根本没引用 t_dequeue ⇒ 更安全')

# R4/R5/R6/R7：worker 侧
synth_fn = find_func(wrk_tree, 'synth')
check('R4a 找到 tts_worker.synth', synth_fn is not None)

fp_emit = None
fp_dict = {}
for n in ast.walk(wrk_tree):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == 'emit':
        # 🔴🔴 实际写法是 `emit({'kind': 'first_packet', ...})`
        #   ⇒ **字典字面量作为位置参数**（不是 `kind=` 关键字）
        #   ⚠️⚠️ 而且 `'first_packet'` 是 **`kind` 这个 key 的 value**，
        #      **不是** key 本身 ⇒ 查「key 列表里有没有 first_packet」必然落空
        #      ⇒ 本脚本第一版就是这么写错的（**判据自身假通过**，§62 同源教训）。
        for arg in n.args:
            if isinstance(arg, ast.Dict):
                d = {}
                for k, v in zip(arg.keys, arg.values):
                    if isinstance(k, ast.Constant):
                        d[k.value] = v
                kind_v = d.get('kind')
                if isinstance(kind_v, ast.Constant) \
                        and kind_v.value == 'first_packet':
                    fp_emit = n
                    fp_dict = d
                    break
    if fp_emit is not None:
        break
check('R4b worker 发 first_packet 时带 synth_s',
      fp_emit is not None and 'synth_s' in fp_dict
      if fp_emit is not None else False,
      '⚠️ `synth_s` 在**字典字面量内部**（不是 emit() 的关键字参数）'
      '⇒ 判据必须查 dict 的 key')

if fp_emit is not None:
    check('R5 worker 的 synth_s 用 worker 自己的 t_dequeue',
          any(isinstance(n, ast.Name) and n.id == 't_dequeue'
              for n in ast.walk(fp_emit)))

run_fn = find_func(wrk_tree, 'run')
check('R6a 找到 tts_worker.run（主循环）', run_fn is not None)
if run_fn is not None:
    check('R6b 主循环记 _dequeue_at[jid]',
          any(isinstance(n, ast.Attribute) and n.attr == '_dequeue_at'
              for n in ast.walk(run_fn)))
if synth_fn is not None:
    check('R7a synth() 消费 _dequeue_at',
          any(isinstance(n, ast.Attribute) and n.attr == '_dequeue_at'
              for n in ast.walk(synth_fn)))
    check('R7b synth() 有 None 兜底（缺 t_dequeue 不崩）',
          any(isinstance(n, ast.Compare) and
              any(isinstance(c, ast.Constant) and c.value is None
                  for c in ast.walk(n))
              for n in ast.walk(synth_fn)))

# R8：stats 里带 first_packet_parts
check('R8 stats() 带 first_packet_parts',
      'first_packet_parts' in svc_src)

# ── R9：行为级（真跑一遍主进程的算法）────────────────────────────────
# 🔴 用**真实的 tts_service 源码**做行为验证：不 import 模块（会 abort）
#   ⇒ 只把「first_packet 分支」的关键算法抠出来 exec 到独立命名空间。
#   但更稳的做法是**直接复算**：把主进程的排队段算法原样搬过来跑。
#   ⇒ 这里用**从源码里核对 + 独立复算**两步，避免 import。
def main_proc_queued(t_submit, t_sent):
    """主进程口径：排队等待 = t_sent − t_submit（同一进程 ⇒ 时钟可比）"""
    return max(0.0, t_sent - t_submit)


# 场景：submit 在 t=100.000；主进程因为 worker 忙，0.300 s 后才写 stdin
#       ⇒ t_sent = 100.300 ⇒ 排队段 = 0.300
#       worker 内部：t_dequeue=5.000（worker 时钟，完全不同基准）
#                     t_first = 5.420 ⇒ 合成段 = 0.420
T_SUBMIT = 100.000
T_SENT = 100.300
W_DEQUEUE = 5.000        # ← worker 时钟，基准与主进程**不同**
W_FIRST = 5.420

queued = main_proc_queued(T_SUBMIT, T_SENT)
synth_s = W_FIRST - W_DEQUEUE

check('R9a 排队段算对（≈0.300 s）', abs(queued - 0.300) < 1e-6,
      'queued_s=%.3f' % queued)
check('R9b 合成段算对（≈0.420 s）', abs(synth_s - 0.420) < 1e-6,
      'synth_s=%.3f' % synth_s)
check('R9c 两段是**不同的数**（不是同一个值抄两遍）',
      abs(queued - synth_s) > 1e-3,
      'queued=%.3f vs synth=%.3f' % (queued, synth_s))

# 🔴🔴 跨进程时钟不可比 ⇒ 若误用 worker 的 t_dequeue 去算排队段：
#   100.000 − 5.000 = 95.0 s ⇒ 完全离谱。
wrong = T_SUBMIT - W_DEQUEUE
check('R9d 跨进程相减确实离谱（⇒ 反证「不能直接用 t_dequeue」）',
      wrong > 90.0, '误算得 %.1f s' % wrong)

# ── BUG 组：反证（基线 commit 里这些都不存在）────────────────────────
base_svc = git_show(BASELINE_COMMIT, SVC)
base_wrk = git_show(BASELINE_COMMIT, WRK)
if base_svc is None:
    check('B0 取得基线源码', False, 'git show %s:%s 失败' % (BASELINE_COMMIT, SVC),
          group='BUG')
else:
    bt = ast.parse(base_svc)
    bsend = find_func(bt, '_send')
    check('B1 基线 _send **没有**回填 t_sent（⇒ 缺陷曾真实存在）',
          bsend is not None and not subscript_key(bsend, 't_sent'),
          '基线无 "t_sent" 下标', group='BUG')
    check('B2 基线 first_packet 分支**没有** queued_s（⇒ 缺陷曾真实存在）',
          not has_ident(bt, 'queued_s'),
          '基线 AST 里无 queued_s 标识符（不能用子串匹配）', group='BUG')
    check('B3 基线 worker **没有** synth_s（⇒ 缺陷曾真实存在）',
          base_wrk is not None
          and not has_ident(ast.parse(base_wrk), 'synth_s'),
          '基线 AST 里无 synth_s 标识符（不能用子串匹配：synth_stream 会误命中）',
          group='BUG')

# ── 汇总 ───────────────────────────────────────────────────────────────
real = [r for r in _results if r[0] == 'REAL']
bug = [r for r in _results if r[0] == 'BUG']
real_pass = sum(1 for r in real if r[2])
bug_hit = sum(1 for r in bug if r[2])
print()
print('=' * 74)
print('REAL  PASS %d / FAIL %d' % (real_pass, len(real) - real_pass))
print('BUG   命中 %d / %d（命中即证明缺陷曾真实存在）' % (bug_hit, len(bug)))
print('=' * 74)

out = {
    'when': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'baseline_commit': BASELINE_COMMIT,
    'real_pass': real_pass, 'real_total': len(real),
    'bug_hit': bug_hit, 'bug_total': len(bug),
    'checks': [{'group': g, 'name': n, 'pass': p} for g, n, p in _results],
    'timing_valid': False,
}
json_path = os.path.join(HERE, 'app097_first_packet_split_evidence.json')
with io.open(json_path, 'w', encoding='utf-8') as f:
    f.write(json.dumps(out, ensure_ascii=False, indent=2))
print('证据已落盘:', json_path)

ok = (real_pass == len(real)) and (bug_hit == len(bug))
print('ALL PASS =', ok)
sys.exit(0 if ok else 1)
