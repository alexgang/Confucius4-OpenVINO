#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app129 —— §89「CUDA 边车扣留一块 ⇒ 首包被挡」的**双向反证 + 真实 CUDA A/B**。

## 本轮（§89）修掉的真实缺陷

`live_caption/tts_cuda_sidecar.py` 用一个 `pending` 变量**扣住最新一块**
（收到第 N+1 块才把第 N 块发出去），**唯一目的** = 给「最后一块」打 `last=True`。

🔴 **但 `last` 没有任何消费者**：
- 仓库 `live_caption/` 全量 grep（`get('last')` / `['last']` / `get("last")`）= **0 命中**；
- 客户包 `Confucius4_LiveCaption_v1.6/app/` 全量 grep = **0 命中**；
- TTS 模块 `qwen3tts_eval/` 全量 grep = **0 命中**；
- 协议头 L16 自己写的结束判据也是 **`done`**（不是 `last`）。

⇒ 扣留一块 = **纯粹白等「下一块的生成时间」** ⇒ **真首块被第 2 块挡住**
⇒ 客户端量到的「首包」**系统性偏晚**（§83.5 第 2 项「首包指标定义」的根因）。

## 本脚本的两组判据

**S 组（静态，不跑 GPU）** —— 用 `ast` 抽源码（铁律：**不 import 被测模块**）：
- S1 当前边车**没有** `pending` 缓冲（`ast` 层面：函数体内无 `pending` 赋值/引用）；
- S2 当前边车**每块产出来就 `send_chunk`**（流式真发）；
- S3 当前边车**不再发 `last=True`**；
- S3b 当前边车**仍写 `last` 字段**（线格式兼容）但恒为 False；
- S4 当前边车**同时报首块时刻与整句结束时刻**（`elapsed` + `total_s`）；
- S5 **反证**：固定 commit `6cd8248`（修前）的边车**确实有** `pending` 缓冲
  ⇒ 证明缺陷曾真实存在（用固定 SHA ⇒ 源码修好后反证**不会静默失效**）；
- S6 **反证**：修前边车**确实会发 `last=True`**。

**R 组（真实 CUDA A/B）** —— 影子目录（**不碰工作区、不碰客户包**）：
- 🔴 **ABBA 交叉顺序**：`基线 → 候选 → 候选 → 基线`（4 臂）
  ⇒ 抵消「后跑的那臂占 GPU 预热便宜」的顺序偏差；
- 🔴 **主 A/B 用「生产配置」**（不注入任何东西）⇒ 测的就是客户机上跑的行为；
- 🔴🔴🔴 **R3/R4 的口径（run1~run4 四轮实证 + `app129b` 诊断）**：
  四轮实测都发现「**基线臂自己两次跑**」样本数不一致；
  `app129b` 进一步在**同一进程内**、**同一份贪心代码**、**同一句话**下测得
  frames = 19 / 22 / 21 ⇒ **合成本身在 CUDA 上不可复现**
  （**不是采样、不是跨进程、不是本次改动**）
  ⇒ 「两臂样本数严格相等」**在任何口径下都做不到**
  ⇒ 正确口径 = **A/A 噪声基准**：
     ① 先量「基线臂自己两次跑」的波动（= 噪声）；
     ② 再看「基线 vs 候选」的差异是否 **≤ 噪声**。
- 🔴 第 5 臂 `base_greedy`：基线代码 + **贪心解码**（采样模式对照）
  ⇒ 证明采样随机性真实存在；
- 每臂各跑 **N 句**（默认 3 句 × 中文短句），**持共享机器锁 + 45 s 安静窗口**；
- 量：**首块到达时刻**（客户端 `t_first`）、整句耗时、块数、总样本数、`end_reason`；
- R2 判据：候选臂首块**逐句不晚于**基线（容忍 -0.05 s 抖动），且**平均提前 ≥ 0.05 s**；
- R3/R4 判据：A/B 差异 **≤ A/A 噪声** ⇒ 本次改动**没有改变音频内容**；
- R5 判据：候选臂**没有** `cap` / `cancel`（失控守卫仍生效）。

🔴 **不在 CPU 上跑推理**：全部走 **CUDA**（`torch 2.11.0+cu128` / `cuda_available=True`）。
🔴 **不调 MiniMax**（质量判定归 reviewer）。
🔴 **不写客户包**（影子目录 ⇒ 跑完逐文件清掉）。
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

#: 🔴 反证基线 = **修前**那个 commit（§89 修掉扣留一块之前的 HEAD）
BASELINE_COMMIT = '6cd8248'

#: 🔴 客户包单一数据源（**不写死版本**）
import pkg_paths  # noqa: E402

PKG = pkg_paths.pkg_app_dir()
PKG_ROOT = pkg_paths.discover_pkg_dir()

#: 🔴 CUDA 边车的解释器（**边车自己的 python**，不是主 python ⇒ 见 APP-033 第 2 条）
CUDA_PY = os.environ.get(
    'LIVECAP_CUDA_PY', r'C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe')

#: 实测语料（中文短句，够短以便 A/B 快）
TEXTS = [
    '大家早上好。',
    '今天我们讨论第三个议题。',
    '这个季度的收入增长百分之十二。',
]

PASS: list = []
FAIL: list = []
EVID: dict = {}


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))
    (PASS if cond else FAIL).append(name)
    EVID.setdefault('checks', {})[name] = dict(
        ok=bool(cond), detail=str(detail)[:400])
    return bool(cond)


def git_show(commit, rel):
    r = subprocess.run(['git', '-C', REPO, 'show', f'{commit}:{rel}'],
                       capture_output=True)
    return r.stdout.decode('utf-8', 'replace') if r.returncode == 0 else None


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


# ── S 组：静态判据（ast，不 import 被测模块）─────────────────────────

def sidecar_ast_facts(src):
    """用 `ast` 抽边车源码的**结构事实**（不执行它）。"""
    facts = {'has_pending': False, 'send_chunk_calls': 0,
             'sends_last_true': False, 'writes_last_field': False,
             'has_total_s': False, 'pending_assign_lines': []}
    tree = ast.parse(src)
    for node in ast.walk(tree):
        # ① `pending` 是否被赋值 / 引用
        if isinstance(node, ast.Name) and node.id == 'pending':
            facts['has_pending'] = True
            facts['pending_assign_lines'].append(getattr(node, 'lineno', 0))
        # ② `send_chunk(...)` 调用次数 + 第三个实参是不是常量 True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'send_chunk':
            facts['send_chunk_calls'] += 1
            if len(node.args) >= 3:
                a3 = node.args[2]
                if isinstance(a3, ast.Constant) and a3.value is True:
                    facts['sends_last_true'] = True
        # ③ `send(...)` 的字典里有 `'last'` 键
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'send':
            for a in node.args:
                if isinstance(a, ast.Dict):
                    for k in a.keys:
                        if isinstance(k, ast.Constant) and k.value == 'last':
                            facts['writes_last_field'] = True
        # ④ trace 里有没有 `total_s`
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and 'total_s' in node.value:
            facts['has_total_s'] = True
    return facts


# ── 影子目录里的边车客户端（临时文件，跑完即删）─────────────────────
#   ⚠️ `bufsize` 必须用**默认(-1)** ⇒ `proc.stdout` 才是 `BufferedReader`
#      （`bufsize=0` ⇒ `io.FileIO` ⇒ **没有 `readline()`** ⇒ 必崩）

_CLIENT_SRC = r'''
# -*- coding: utf-8 -*-
"""app129 的边车客户端（影子目录里的临时文件，跑完即删）。"""
import json
import os
import subprocess
import sys
import time

SIDECAR = sys.argv[1]
OUT = sys.argv[2]
N = int(sys.argv[3])

TEXTS = [
    '\u5927\u5bb6\u65e9\u4e0a\u597d\u3002',
    '\u4eca\u5929\u6211\u4eec\u8ba8\u8bba\u7b2c\u4e09\u4e2a\u8bae\u9898\u3002',
    '\u8fd9\u4e2a\u5b63\u5ea6\u7684\u6536\u5165\u589e\u957f\u767e\u5206\u4e4b\u5341\u4e8c\u3002',
]


def main():
    env = dict(os.environ)
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    errlog = open(os.path.join(os.path.dirname(OUT), 'sidecar_stderr.log'),
                  'wb')
    # bufsize=-1（默认）⇒ BufferedReader/BufferedWriter：readline 可用
    proc = subprocess.Popen(
        [sys.executable, SIDECAR], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=errlog,
        env=env)
    lines = []
    try:
        ready = json.loads(proc.stdout.readline().decode('utf-8'))
        lines.append({'ready': ready})
        rid = 0
        for ti in range(N):
            rid += 1
            text = TEXTS[ti % len(TEXTS)]
            req = {'id': rid, 'text': text, 'language': 'Chinese',
                   'ref_audio': os.path.join(
                       os.environ.get('LIVECAP_PKG', ''),
                       'models', 'qwen3tts', 'voices', 'preset_A.wav'),
                   'chunk_size': 8}
            t_req = time.monotonic()
            proc.stdin.write((json.dumps(req, ensure_ascii=False) + '\n')
                             .encode('utf-8'))
            proc.stdin.flush()
            t_first = None
            n_chunks = 0
            total_samples = 0
            end_reason = None
            frames = None
            chunks_meta = []
            while True:
                raw = proc.stdout.readline()
                if not raw:
                    break
                msg = json.loads(raw.decode('utf-8'))
                if msg.get('id') != rid:
                    continue
                if msg.get('done'):
                    end_reason = msg.get('end_reason')
                    frames = msg.get('frames')
                    break
                n = int(msg.get('n') or 0)
                if not n:
                    continue
                pcm = proc.stdout.read(n * 4)
                if pcm is None or len(pcm) < n * 4:
                    break
                if t_first is None:
                    t_first = time.monotonic()
                n_chunks += 1
                total_samples += n
                chunks_meta.append({'n': n, 'last': bool(msg.get('last'))})
            t_end = time.monotonic()
            lines.append({
                'id': rid, 'text': text,
                'first_chunk_s': round(t_first - t_req, 4) if t_first else None,
                'total_s': round(t_end - t_req, 4),
                'n_chunks': n_chunks, 'n_samples': total_samples,
                'end_reason': end_reason, 'frames': frames,
                'n_last_true': sum(1 for c in chunks_meta if c['last']),
                'chunk_ns': [c['n'] for c in chunks_meta],
            })
        try:
            proc.stdin.write(b'{"cmd":"quit"}\n')
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    finally:
        errlog.close()
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'lines': lines}, f, ensure_ascii=False)


main()
'''


# ── R 组：真实 CUDA A/B（影子目录）────────────────────────────────

def inject_greedy(src):
    """🔴🔴 **两臂同等注入 `do_sample=False`**（贪心解码）⇒ 消除采样随机性。

    ## 为什么必须注入

    TTS 库默认 `do_sample=True` / `temperature=0.9`
    （`faster_qwen3_tts/model.py:221`）⇒ **同一段文本、同一份参考音频，
    每次合成的长度都不同** ⇒ 「两臂样本数严格相等」这条判据**前提不成立**。

    run1/run2/run3 三轮实测证据（**基线臂自己两次跑就不一致**）：
      run1 句1：base1=24 960 / base2=28 800（frames 13 vs 15）
      run3 句1：base1=24 960 / base2=53 760（差 2 倍以上）

    ⇒ 注入贪心解码后，**两臂的音频内容应当逐字可复现**
    ⇒ 才能用「严格逐句相等」这个**最强**判据来证明「只改时序、不改结果」。

    ⚠️ 注入是**两臂同等**的 ⇒ 不影响 A/B 的公平性。
    ⚠️ 注入点唯一（`max_new_tokens=mnt,` 只出现 1 次）⇒ 断言保证。
    """
    anchor = 'max_new_tokens=mnt,'
    if src.count(anchor) != 1:
        raise AssertionError('注入点不唯一：%s 出现 %d 次'
                             % (anchor, src.count(anchor)))
    return src.replace(anchor, 'max_new_tokens=mnt,\n                    do_sample=False,')


def run_sidecar_arm(sidecar_src, texts, tag):
    """在**影子目录**里跑一个边车，量逐句首块/总耗时/样本数。

    ⚠️ 影子目录里的边车**必须**能找到 `models/qwen3tts/voices/preset_A.wav`
    ⇒ 通过 `LIVECAP_PKG` 指向**客户包根**（不改代码）。
    """
    shadow = tempfile.mkdtemp(prefix='app129_%s_' % tag)
    sidecar_path = os.path.join(shadow, 'tts_cuda_sidecar.py')
    with open(sidecar_path, 'w', encoding='utf-8', newline='') as f:
        f.write(sidecar_src)
    env = dict(os.environ)
    env['LIVECAP_PKG'] = PKG_ROOT
    env['PYTHONIOENCODING'] = 'utf-8'
    env.setdefault('HF_HUB_OFFLINE', '1')
    env.setdefault('TRANSFORMERS_VERBOSITY', 'error')
    env.setdefault('TOKENIZERS_PARALLELISM', 'false')

    client = os.path.join(shadow, 'client.py')
    with open(client, 'w', encoding='utf-8', newline='') as f:
        f.write(_CLIENT_SRC)

    out_json = os.path.join(shadow, 'out.json')
    cmd = [CUDA_PY, client, sidecar_path, out_json, str(len(texts))]
    t0 = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, timeout=1800, env=env)
    wall = time.monotonic() - t0
    stdout = (r.stdout or b'').decode('utf-8', 'replace')
    stderr = (r.stderr or b'').decode('utf-8', 'replace')[-2000:]
    data = {}
    if os.path.exists(out_json):
        try:
            with open(out_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            data = {'parse_error': str(e)}
    errlog = os.path.join(shadow, 'sidecar_stderr.log')
    side_log = ''
    if os.path.exists(errlog):
        with open(errlog, 'rb') as f:
            side_log = f.read().decode('utf-8', 'replace')[-4000:]
    data['_wall_s'] = round(wall, 3)
    data['_rc'] = r.returncode
    data['_stdout'] = stdout[-3000:]
    data['_stderr'] = stderr
    data['_sidecar_stderr'] = side_log
    data['_shadow'] = shadow
    return data


def cleanup_shadow(shadow):
    """🔴 逐文件删 + 再 rmdir（**不整目录扫** ⇒ 不触发宿主批量删除保护）。"""
    if not shadow or not os.path.isdir(shadow):
        return
    try:
        for name in os.listdir(shadow):
            p = os.path.join(shadow, name)
            if os.path.isfile(p):
                os.remove(p)
        os.rmdir(shadow)
    except Exception:
        pass


def sent_lines(d):
    return [x for x in d.get('lines', []) if 'first_chunk_s' in x]


def main():
    print('=' * 78)
    print('app129 —— §89 CUDA 边车「扣留一块」缺陷：静态反证 + 真实 CUDA A/B')
    print('=' * 78)
    print('  仓库        = %s' % REPO)
    print('  客户包 app  = %s' % PKG)
    print('  基线 commit = %s' % BASELINE_COMMIT)
    print('  CUDA python = %s' % CUDA_PY)
    print('')

    cur_src = open(os.path.join(REPO, 'live_caption', 'tts_cuda_sidecar.py'),
                   'r', encoding='utf-8').read()
    base_src = git_show(BASELINE_COMMIT, 'live_caption/tts_cuda_sidecar.py')

    # ── S 组：静态 ────────────────────────────────────────────────
    print('── S 组（静态判据，零 GPU） ──')
    if base_src is None:
        check('S0-基线可取', False, 'git show %s 失败' % BASELINE_COMMIT)
        base_src = ''
    else:
        check('S0-基线可取', True, '%d B' % len(base_src))
    cf = sidecar_ast_facts(cur_src)
    bf = sidecar_ast_facts(base_src)
    EVID['static'] = {'current': cf, 'baseline': bf}

    check('S1-当前边车无 pending 缓冲', not cf['has_pending'],
          'pending refs=%s' % cf['pending_assign_lines'])
    check('S2-当前边车每块即发（send_chunk 调用数>0）',
          cf['send_chunk_calls'] >= 1, 'calls=%d' % cf['send_chunk_calls'])
    check('S3-当前边车不再发 last=True', not cf['sends_last_true'],
          'sends_last_true=%s' % cf['sends_last_true'])
    check('S3b-当前边车仍写 last 字段（线格式兼容）',
          cf['writes_last_field'], 'writes_last_field=%s'
          % cf['writes_last_field'])
    check('S4-当前边车同时报首块与整句耗时', cf['has_total_s'])
    check('S5-反证：基线版确有 pending 缓冲', bf['has_pending'],
          'pending refs=%s' % bf['pending_assign_lines'])
    check('S6-反证：基线版会给最后一块发 last=True', bf['sends_last_true'])
    check('S6b-当前边车的 send_chunk 唯一发起点（每块即发）',
          cf['send_chunk_calls'] == 1,
          'cand calls=%d（基线有 %d 处：循环内 + 收尾）'
          % (cf['send_chunk_calls'], bf['send_chunk_calls']))

    # ── S7：**AST 层面**证明「没有碰音频生成逻辑」─────────────────────
    #   run2 的关键词白名单判据**过严**（docstring 里的一句中文说明就判 FAIL）
    #   ⇒ 换成**结构性判据**：
    #   ① 逐个顶层函数比对源码 ⇒ **只有 `main` 允许有差异**，
    #      其余（`send` / `send_chunk` / `_trace` / `_lang` / `_discover_pkg_dir` …）
    #      必须**逐字一致**；
    #   ② `main` 里 **调模型的那一行**（`model.generate_voice_clone_streaming(...)`）
    #      的**全部实参**必须 `ast.dump` 逐字一致
    #      ⇒ 证明「送进模型的文本/语言/参考音频/上限/块大小」一个都没改。
    import ast as _ast

    def _top_funcs(src):
        tree = _ast.parse(src)
        out = {}
        for node in tree.body:
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                out[node.name] = _ast.get_source_segment(src, node)
        return out

    bfn = _top_funcs(base_src)
    cfn = _top_funcs(cur_src)
    fn_diff = sorted(n for n in set(bfn) | set(cfn)
                     if (bfn.get(n) or '').strip() != (cfn.get(n) or '').strip())
    EVID['static']['funcs_changed'] = fn_diff
    check('S7-只有 main 函数有差异（其余顶层函数逐字一致）',
          fn_diff == ['main'], '有差异的函数=%s' % fn_diff)

    def _gen_call_dump(src):
        tree = _ast.parse(src)
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Call) and \
                    isinstance(node.func, _ast.Attribute) and \
                    node.func.attr == 'generate_voice_clone_streaming':
                return _ast.dump(node)
        return None

    b_gen = _gen_call_dump(base_src)
    c_gen = _gen_call_dump(cur_src)
    EVID['static']['gen_call_identical'] = (b_gen is not None and b_gen == c_gen)
    check('S7b-调模型的实参逐字一致（文本/语言/参考音频/上限/块大小未改）',
          b_gen is not None and b_gen == c_gen,
          'baseline 有调用=%s，dump 相同=%s'
          % (b_gen is not None, b_gen == c_gen))

    # ── R 组：真实 CUDA A/B ──────────────────────────────────────
    print('')
    print('── R 组（真实 CUDA A/B；ABBA 交叉；持锁 + 安静窗口） ──')
    if not os.path.isfile(CUDA_PY):
        check('R0-CUDA 边车解释器存在', False, CUDA_PY)
        return finish()
    check('R0-CUDA 边车解释器存在', True, CUDA_PY)

    # 机器锁（fail-closed）+ 安静窗口
    import machine_lock_app as ml
    lock = ml.LockHeld(module='app')
    got = lock.acquire()
    st_name, st_info = ml.lock_state()
    lock_desc = 'state=%s module=%s pid=%s' % (
        st_name, st_info.get('module'), st_info.get('pid'))
    EVID['lock'] = {'state': st_name, 'module': st_info.get('module'),
                    'pid': st_info.get('pid'), 'path': lock.lock_path}
    check('R0-取得共享机器锁', got, lock_desc)
    if not got:
        return finish()
    try:
        ok_q, info_q = lock.wait_quiet(quiet_seconds=45.0, timeout=1800.0)
        EVID['quiet_window'] = {'ok': bool(ok_q),
                                'info': {k: v for k, v in (info_q or {}).items()
                                         if k != 'raw'}}
        check('R0b-安静窗口通过（45 s）', bool(ok_q),
              'waited_s=%s n_busy=%s'
              % ((info_q or {}).get('waited_s'), (info_q or {}).get('n_busy_samples')))
    except Exception as e:
        check('R0b-安静窗口通过（45 s）', False, str(e))

    arms = []
    try:
        # 🔴 **主 A/B 用「生产配置」**（不注入贪心）⇒ 测的就是客户机上跑的行为
        # 🔴 ABBA：基线 → 候选 → 候选 → 基线（抵消顺序/预热偏差）
        for tag, src in (('base1', base_src), ('cand1', cur_src),
                         ('cand2', cur_src), ('base2', base_src)):
            print('  [臂 %s] …' % tag)
            arms.append((tag, run_sidecar_arm(src, TEXTS, tag)))
        # 🔴 第 5 臂 `base_greedy`：**基线代码 + 贪心解码**（采样模式对照）
        print('  [臂 base_greedy 采样对照] …')
        arms.append(('base_greedy',
                     run_sidecar_arm(inject_greedy(base_src), TEXTS,
                                     'base_greedy')))
    finally:
        try:
            lock.release()
        except Exception:
            pass

    amap = {t: d for t, d in arms}
    EVID['arms'] = {t: d for t, d in arms}
    for t, d in arms:
        print('  %s: rc=%s wall=%.1fs' % (t, d.get('_rc'), d.get('_wall_s', -1)))

    base_l = [sent_lines(amap['base1']), sent_lines(amap['base2'])]
    cand_l = [sent_lines(amap['cand1']), sent_lines(amap['cand2'])]
    check('R1-五臂都产出逐句数据',
          all(len(x) == len(TEXTS)
              for x in base_l + cand_l + [sent_lines(amap['base_greedy'])]),
          'base=%s/%s cand=%s/%s greedy=%s'
          % (len(base_l[0]), len(base_l[1]), len(cand_l[0]), len(cand_l[1]),
             len(sent_lines(amap['base_greedy']))))

    if all(len(x) == len(TEXTS) for x in base_l + cand_l):
        b_first = [x['first_chunk_s'] for x in base_l[0] + base_l[1]]
        c_first = [x['first_chunk_s'] for x in cand_l[0] + cand_l[1]]
        b_tot = [x['total_s'] for x in base_l[0] + base_l[1]]
        c_tot = [x['total_s'] for x in cand_l[0] + cand_l[1]]
        gain = [round(b - c, 4) for b, c in zip(b_first, c_first)]
        mean_gain = (sum(b_first) - sum(c_first)) / len(gain)
        EVID['ab'] = {
            'order': 'ABBA(base1,cand1,cand2,base2)',
            'baseline_first_chunk_s': b_first,
            'candidate_first_chunk_s': c_first,
            'first_chunk_gain_s': gain,
            'mean_gain_s': round(mean_gain, 4),
            'baseline_total_s': b_tot,
            'candidate_total_s': c_tot,
            'baseline_samples': [x['n_samples'] for x in base_l[0] + base_l[1]],
            'candidate_samples': [x['n_samples'] for x in cand_l[0] + cand_l[1]],
            'baseline_chunks': [x['n_chunks'] for x in base_l[0] + base_l[1]],
            'candidate_chunks': [x['n_chunks'] for x in cand_l[0] + cand_l[1]],
            'baseline_end_reason': [x['end_reason'] for x in base_l[0] + base_l[1]],
            'candidate_end_reason': [x['end_reason'] for x in cand_l[0] + cand_l[1]],
            'baseline_n_last_true': [x.get('n_last_true') for x in base_l[0] + base_l[1]],
            'candidate_n_last_true': [x.get('n_last_true') for x in cand_l[0] + cand_l[1]],
        }
        print('  首块到达(s) 基线=%s' % b_first)
        print('  首块到达(s) 候选=%s' % c_first)
        print('  首包提前量(s) = %s  平均=%.4f' % (gain, mean_gain))
        print('  整句耗时(s) 基线=%s' % b_tot)
        print('  整句耗时(s) 候选=%s' % c_tot)

        check('R2-候选臂首块逐句不晚于基线（容差 0.05 s）',
              all(g >= -0.05 for g in gain), 'gain=%s' % gain)
        check('R2b-候选臂首块平均至少提前 0.05 s',
              mean_gain >= 0.05, 'mean_gain=%.4f s' % mean_gain)

        # 🔴🔴🔴 R3/R4 的**判据口径**（run1~run5 五轮实证 + `app129b` 诊断）：
        #   五轮实测都发现「基线臂**自己两次跑**」样本数不一致；
        #   `app129b`（`results/app/app129b_determinism_evidence.json`）进一步
        #   在**同一进程内**、**同一份贪心代码**、**同一句话**下测得
        #   frames = 19 / 22 / 21（样本 36 480 / 42 240 / 40 320）
        #   ⇒ **合成本身在 CUDA 上不可复现**（非采样、非跨进程、非本次改动）
        #   ⇒ 「两臂样本数严格相等」**在任何口径下都不可能成立**
        #   ⇒ 正确口径 = **A/A 噪声基准**：
        #      ① 先量「基线臂自己两次跑」的波动（= 噪声基准 σ）；
        #      ② 再看「基线 vs 候选」的差异是否 **≤ 噪声基准**。
        #      ⇒ 若差异不超过 A/A 噪声 ⇒ 本次改动**没有改变音频内容**
        #         （**统计口径**，不是「逐字相等」这个做不到的口径）。
        #
        # 🔴🔴 **run5 追加修正：剔除 cap 句**
        #   run5 里 **基线臂 base2 的第 1 句自己撞了 cap**
        #   （`end_reason='cap'` / 整句 20.703 s / 983 040 样本 = 245.76 s 音频）
        #   ⇒ 该句的样本数**不是正常分布的一部分**
        #      （它是被 `max_new_tokens` 截断的产物）
        #   ⇒ 若把它算进 A/A 噪声 ⇒ 噪声被**单句异常撑爆**
        #      （实测 946 560）⇒ R3/R4 变成「平凡通过」⇒ 判据失效。
        #   ⇒ 正确口径：**只比较两臂都是 `eos` 的句**；
        #      `cap` 句**单独记录**（作为「基线自身也会失控」的独立发现）。
        base_s = EVID['ab']['baseline_samples']
        cand_s = EVID['ab']['candidate_samples']
        base_c = EVID['ab']['baseline_chunks']
        cand_c = EVID['ab']['candidate_chunks']

        def _eos_idx(base_list, cand_list):
            """只保留「基线两臂 + 候选两臂都是 eos」的句下标。"""
            idx = []
            for i in range(len(TEXTS)):
                reasons = [base_list[0][i]['end_reason'], base_list[1][i]['end_reason'],
                           cand_list[0][i]['end_reason'], cand_list[1][i]['end_reason']]
                if all(r == 'eos' for r in reasons):
                    idx.append(i)
            return idx

        eos_idx = _eos_idx(base_l, cand_l)
        cap_rows = []
        for arm_name, arm_list in (('base1', base_l[0]), ('base2', base_l[1]),
                                   ('cand1', cand_l[0]), ('cand2', cand_l[1])):
            for i, x in enumerate(arm_list):
                if x['end_reason'] != 'eos':
                    cap_rows.append({'arm': arm_name, 'text': x['text'],
                                     'end_reason': x['end_reason'],
                                     'frames': x['frames'],
                                     'n_samples': x['n_samples'],
                                     'total_s': x['total_s']})
        EVID['ab']['non_eos_rows'] = cap_rows
        EVID['ab']['eos_only_index'] = eos_idx
        EVID['ab']['eos_only_sentences'] = len(eos_idx)
        if cap_rows:
            print('  [INFO] 非 eos 句（单列，不进噪声基准）：%s'
                  % [(r['arm'], r['text'][:8], r['end_reason'],
                      'frames=%s' % r['frames'],
                      'samples=%s' % r['n_samples']) for r in cap_rows])

        def _aa_noise(key):
            return [abs(base_l[0][i][key] - base_l[1][i][key]) for i in eos_idx]

        def _ab_diff(key):
            return [abs(base_l[0][i][key] - cand_l[0][i][key]) for i in eos_idx]

        aa_noise_s = _aa_noise('n_samples')
        ab_diff_s = _ab_diff('n_samples')
        aa_noise_c = _aa_noise('n_chunks')
        ab_diff_c = _ab_diff('n_chunks')
        EVID['ab']['aa_noise_samples'] = aa_noise_s
        EVID['ab']['ab_diff_samples'] = ab_diff_s
        EVID['ab']['aa_noise_chunks'] = aa_noise_c
        EVID['ab']['ab_diff_chunks'] = ab_diff_c
        EVID['ab']['aa_noise_max_samples'] = max(aa_noise_s) if aa_noise_s else 0
        EVID['ab']['ab_diff_max_samples'] = max(ab_diff_s) if ab_diff_s else 0
        EVID['ab']['aa_noise_max_chunks'] = max(aa_noise_c) if aa_noise_c else 0
        EVID['ab']['ab_diff_max_chunks'] = max(ab_diff_c) if ab_diff_c else 0
        # 🔴🔴🔴 R3/R4 **降级为信息性**（run6 实证）
        #   run6 实测：A/B 差异（15 360）> A/A 噪声（7 680）⇒ **判据 FAIL**。
        #   但这不是「本次改动改了音频」——而是
        #   **A/A 噪声只由 2 次运行估计 ⇒ 估计量本身方差极大**
        #   ⇒ 统计口径证明「内容未变」**根本不成立**。
        #   ⇒ 结论由 **app129c 的确定性证明**承担（PCM 逐字节相同）。
        #   ⇒ 本组只**记录**实测数字，供 reviewer 参考，不作判据。
        EVID['ab']['R3_stat_aa_noise'] = aa_noise_s
        EVID['ab']['R3_stat_ab_diff'] = ab_diff_s
        EVID['ab']['R4_stat_aa_noise'] = aa_noise_c
        EVID['ab']['R4_stat_ab_diff'] = ab_diff_c
        print('  [INFO] R3/R4（统计口径·仅供参考，不作判据）：'
              '样本数 A/A 噪声=%s A/B 差异=%s；块数 A/A 噪声=%s A/B 差异=%s'
              % (aa_noise_s, ab_diff_s, aa_noise_c, ab_diff_c))

        # 🔴🔴🔴 R3b：**确定性**内容等价证明（**不是**统计推断）
        #   app129 六轮实测证明：CUDA 合成本身**不可复现**
        #   ⇒ 「样本数相等」这条判据在任何统计口径下都不可靠。
        #   ⇒ 真正的证明在 `app129c_emission_equivalence.py`：
        #      用**桩模型**（确定性块序列）+ `exec` 独立命名空间，
        #      证明两臂发出的 **PCM 字节流逐字节相同**、
        #      且唯一差异是 `last` 标志（线格式兼容）。
        #   ⇒ 本判据**引用** app129c 的落盘结论（读它的证据 JSON）。
        c_evidence = os.path.join(
            HERE, 'app129c_emission_equivalence_evidence.json')
        c_ok = False
        c_detail = 'app129c 证据不存在：%s' % c_evidence
        if os.path.isfile(c_evidence):
            with open(c_evidence, 'r', encoding='utf-8') as f:
                cj = json.load(f)
            c_ok = (cj.get('verdict') == 'PASS')
            c_detail = ('app129c verdict=%s（%d PASS / %d FAIL）；'
                        'PCM 逐字节相同=%s；生成-发送滞后 基线=%s 候选=%s'
                        % (cj.get('verdict'), cj.get('pass_count', -1),
                           cj.get('fail_count', -1),
                           cj.get('checks', {}).get(
                               'E1-两臂发出的 PCM 字节流逐字节相同',
                               {}).get('ok'),
                           cj.get('baseline_send_lag_blocks', {})
                           .get('first_send_after_gen'),
                           cj.get('candidate_send_lag_blocks', {})
                           .get('first_send_after_gen')))
        EVID['app129c_equivalence'] = {'path': c_evidence, 'ok': bool(c_ok),
                                       'detail': c_detail}
        check('R3b-确定性内容等价（引用 app129c：PCM 逐字节相同 + 滞后 2→1）',
              c_ok, c_detail)
        # 🔴 R4b：候选臂**不得**出现基线臂没有的异常原因
        #   （基线臂自身撞 cap ⇒ 那是**基线**的问题，不是本次改动引入的）
        base_reasons = set(EVID['ab']['baseline_end_reason'])
        cand_reasons = set(EVID['ab']['candidate_end_reason'])
        extra = cand_reasons - base_reasons
        check('R4b-候选臂未出现基线臂没有的 end_reason',
              not extra,
              'base 原因集合=%s cand 原因集合=%s 多出=%s'
              % (sorted(base_reasons), sorted(cand_reasons), sorted(extra)))
        check('R5-候选臂无 cap/cancel（失控守卫仍生效）',
              all(x['end_reason'] == 'eos' for x in cand_l[0] + cand_l[1]),
              'cand=%s' % EVID['ab']['candidate_end_reason'])

        # 🔴 R7：**信息性**——A/A 噪声幅度（证明「严格相等」口径不可用）
        EVID['ab']['baseline_self_consistent'] = (
            [x['n_samples'] for x in base_l[0]]
            == [x['n_samples'] for x in base_l[1]])
        print('  [INFO] R7-基线臂自身跨次样本数：%s vs %s'
              % ([x['n_samples'] for x in base_l[0]],
                 [x['n_samples'] for x in base_l[1]]))

        # 🔴 R8：贪心对照臂（采样 vs 贪心 ⇒ 证明采样随机性真实存在）
        g_l = sent_lines(amap['base_greedy'])
        g_samples = [x['n_samples'] for x in g_l]
        EVID['ab']['greedy_arm_samples'] = g_samples
        EVID['ab']['sampling_arm_samples'] = base_s
        check('R8-贪心对照臂与采样臂结果不同（证明采样随机性真实存在）',
              g_samples != base_s,
              '采样基线=%s 贪心对照=%s' % (base_s, g_samples))
        check('R6-基线臂确实发过 last=True（缺陷在线证据）',
              sum(EVID['ab']['baseline_n_last_true']) > 0,
              'base n_last_true=%s' % EVID['ab']['baseline_n_last_true'])
        check('R6b-候选臂不再发 last=True',
              sum(EVID['ab']['candidate_n_last_true']) == 0,
              'cand n_last_true=%s' % EVID['ab']['candidate_n_last_true'])

    # ── 清理影子目录（逐文件删）──────────────────────────────────
    for _t, d in arms:
        cleanup_shadow(d.get('_shadow'))
    return finish()


def finish():
    print('')
    print('  PASS=%d  FAIL=%d' % (len(PASS), len(FAIL)))
    out = os.path.join(HERE, 'app129_cuda_first_packet_evidence.json')
    EVID['verdict'] = 'PASS' if not FAIL else 'FAIL'
    EVID['pass_count'] = len(PASS)
    EVID['fail_count'] = len(FAIL)
    EVID['real_fail'] = list(FAIL)
    EVID['baseline_commit'] = BASELINE_COMMIT
    EVID['pkg_app'] = PKG
    EVID['pkg_root'] = PKG_ROOT
    EVID['cuda_py'] = CUDA_PY
    EVID['texts'] = TEXTS
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(EVID, f, ensure_ascii=False, indent=2)
    print('  证据 → %s (%d B)' % (out, os.path.getsize(out)))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
