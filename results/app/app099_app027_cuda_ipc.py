"""app099 — APP-027③ 验收：CUDA 边车 IPC 协议（rid 过滤 / 不阻塞 / 看门狗 / set_ref / trace）。

🔴🔴 **不 import 被测模块**（项目铁律）⇒ 用 `ast` 抽源码做结构判据，
  协议行为用**自建的假边车**（真子进程 + 真管道）做**端到端**验证。

## A 组（REAL，源码结构）
- A1 `tts_cuda` 有**读者线程**（`_start_reader`）且用 `queue.Queue`
- A2 `generate_stream` **严格按 rid 过滤**（比对 `msg['id']`）
- A3 `generate_stream` 用 `queue.get(timeout=…)`（**真能超时**）
- A4 有**看门狗**：超时 ⇒ 杀并重启边车
- A5 有 `_trace` 逐请求 trace（含 rid / 第一块 / done / 块数 / 异常）
- A6 边车支持 `set_ref` 命令
- A7 旧实现 `_readline` / `_read_exact` **已删除**
- A8 PCM 与 JSON **成对入队**（否则 rid 过滤后 PCM 残留 ⇒ 错位）

## B 组（BUG，端到端真协议）
- B1 正常路径：N 块 + done，块内容与顺序**正确**
- B2 **rid 过滤**：先发旧句（rid=1）并中途放弃，再发新句（rid=2）
      ⇒ 新句收到的**每一块都必须是 rid=2 的内容**（不得混入旧句残留）
- B3 **不无限阻塞**：假边车收到请求后**故意不回任何东西**
      ⇒ `generate_stream` 必须在**有限时间**内抛异常（看门狗触发）
- B4 边车崩溃（exit）⇒ 客户端抛异常而不是挂死
- B5 `set_ref` 命令：边车回 `set_ref: True` 且 `ref_audio` 已切换
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CUDA = os.path.join(ROOT, 'live_caption', 'tts_cuda.py')
SIDE = os.path.join(ROOT, 'live_caption', 'tts_cuda_sidecar.py')

# 🔴🔴🔴 APP-027⑥：**隔离 LOCALAPPDATA**（桩测试绝不污染用户真实目录）
#   `tts_cuda.py` 模块级就会算 `TRACE_PATH`（= %LOCALAPPDATA%\...\tts_cuda_trace.log）
#   ⇒ 不隔离的话，本脚本跑一次就在用户目录里留一个 trace 日志。
#   ⇒ **必须在 exec/import 被测模块之前**设置。
_TMP_LOCALAPPDATA = tempfile.mkdtemp(prefix='app099_localappdata_')
os.environ['LOCALAPPDATA'] = _TMP_LOCALAPPDATA

N_PASS = 0
N_FAIL = 0
FAILURES = []


def check(name, cond, detail='', group='REAL'):
    global N_PASS, N_FAIL
    if cond:
        N_PASS += 1
        print('  [PASS] %s' % name)
    else:
        N_FAIL += 1
        FAILURES.append((group, name, detail))
        print('  [FAIL] %s  %s' % (name, detail))


def src_of(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


cuda_src = src_of(CUDA)
side_src = src_of(SIDE)
cuda_tree = ast.parse(cuda_src)
side_tree = ast.parse(side_src)

print('=== A 组（REAL，源码结构）===')

check('A1 tts_cuda 有读者线程 + queue.Queue',
      '_start_reader' in cuda_src and 'queue.Queue' in cuda_src
      and 'import queue' in cuda_src)

check('A2 generate_stream 严格按 rid 过滤',
      "msg.get('id')" in cuda_src and '!= rid' in cuda_src
      and 'DROP rid' in cuda_src)

check('A3 generate_stream 用 queue.get(timeout=) 真超时',
      'self._q.get(timeout=' in cuda_src
      and 'except queue.Empty' in cuda_src)

check('A4 有看门狗（超时 ⇒ 杀并重启边车）',
      'WATCHDOG_S' in cuda_src and '_restart_sidecar' in cuda_src
      and 'p.kill()' in cuda_src)

check('A5 有逐请求 trace（rid / 第一块 / done / 块数 / 异常）',
      '_trace(' in cuda_src and "'REQ rid=" in cuda_src
      and "'DONE rid=" in cuda_src and "'ERR rid=" in cuda_src)

check('A6 边车支持 set_ref 命令',
      "req.get('cmd') == 'set_ref'" in side_src
      and 'set_ref' in cuda_src)

check('A7 旧 _readline / _read_exact 已删除',
      'def _readline' not in cuda_src and 'def _read_exact' not in cuda_src)

check('A8 PCM 与 JSON 成对入队（q.put((s, pcm))）',
      'q.put((s, pcm))' in cuda_src)

print('=== B 组（BUG，端到端真协议）===')

# ── 自建「假边车」：真子进程 + 真二进制管道 ─────────────────────────
FAKE = textwrap.dedent(r'''
    import json, os, struct, sys, time
    _out = sys.stdout.buffer
    def send(o):
        _out.write((json.dumps(o, ensure_ascii=False) + '\n').encode('utf-8'))
        _out.flush()
    def send_chunk(rid, vals, last):
        a = struct.pack('<%df' % len(vals), *vals)
        send({'id': rid, 'sr': 24000, 'n': len(vals), 'last': last})
        _out.write(a); _out.flush()
    mode = os.environ.get('FAKE_MODE', 'normal')
    cur_ref = 'preset_A'
    send({'ready': True, 'device': 'fake', 'torch': '0', 'model': 'm'})
    for line in sys.stdin.buffer:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line.decode('utf-8'))
        except Exception:
            continue
        cmd = req.get('cmd')
        if cmd == 'quit':
            sys.exit(0)
        if cmd == 'set_ref':
            cur_ref = req.get('ref_audio')
            send({'id': req.get('id'), 'set_ref': True, 'ref_audio': cur_ref})
            continue
        rid = req.get('id')
        if mode == 'silent':
            time.sleep(600)          # 故意**永不**回应
            continue
        if mode == 'crash':
            os._exit(3)
        text = req.get('text') or ''
        # 内容里带上 rid 与 text ⇒ 客户端能核对「有没有串句」
        base = float(rid) * 1000.0
        if mode == 'interleave':
            # 先发一句「旧句」的块（rid=1），再发本句的块
            if rid == 2:
                send_chunk(1, [111.0, 111.0], False)
                send_chunk(1, [112.0, 112.0], True)
                send({'id': 1, 'done': True, 'chunks': 2})
            send_chunk(rid, [base + i for i in range(4)], False)
            send_chunk(rid, [base + 100 + i for i in range(4)], True)
            send({'id': rid, 'done': True, 'chunks': 2})
            continue
        send_chunk(rid, [base + i for i in range(4)], False)
        send_chunk(rid, [base + 100 + i for i in range(4)], True)
        send({'id': rid, 'done': True, 'chunks': 2})
    sys.exit(0)
''')

fake_path = os.path.join(tempfile.gettempdir(), 'app099_fake_sidecar.py')
with open(fake_path, 'w', encoding='utf-8') as f:
    f.write(FAKE)


def make_client(mode, watchdog_s=2.0, watchdog_first_s=3.0):
    """用 exec 把 `tts_cuda.py` 的类加载到独立命名空间（**不 import**）。"""
    import queue as _queue
    import types
    ns = {'__name__': 'app099_tts_cuda', '__file__': CUDA}
    exec(compile(cuda_src, CUDA, 'exec'), ns)
    # 让 `start()` 用假边车
    ns['SIDECAR'] = fake_path
    ns['ENV_PY'] = sys.executable
    ns['READY_TIMEOUT_S'] = 20.0
    ns['WATCHDOG_S'] = watchdog_s
    ns['WATCHDOG_FIRST_S'] = watchdog_first_s
    os.environ['FAKE_MODE'] = mode
    eng = ns['CudaTTSEngine'](on_log=lambda m: None)
    eng._py = sys.executable
    return eng, ns


def collect(eng, text, timeout=30):
    out = []
    for wav, sr in eng.generate_stream(text=text, language='Chinese'):
        out.append((list(wav), sr))
    return out


# B1：正常路径
try:
    eng, ns = make_client('normal')
    eng.start()
    blocks = collect(eng, '你好世界')
    vals = [v for b in blocks for v in b[0]]
    # ⚠️ rid 从 1 开始（`self._rid += 1`）⇒ base = rid*1000 = 1000
    ok_b1 = (len(blocks) == 2 and all(b[1] == 24000 for b in blocks)
             and vals == [1000.0, 1001.0, 1002.0, 1003.0,
                          1100.0, 1101.0, 1102.0, 1103.0])
    check('B1 正常路径：2 块 + done，块内容与顺序正确',
          ok_b1, 'blocks=%d vals=%s' % (len(blocks), vals[:8]))
    eng.close()
except Exception as e:
    check('B1 正常路径：2 块 + done，块内容与顺序正确', False, repr(e))

# B2：rid 过滤（旧句的块不得串进新句）
try:
    eng, ns = make_client('interleave')
    eng.start()
    # 第一句（rid=1）正常消费掉
    collect(eng, '第一句')
    # 第二句（rid=2）：假边车会**先**发旧句（rid=1）的块与 done
    blocks = collect(eng, '新句子')
    vals = [v for b in blocks for v in b[0]]
    # rid=2 ⇒ base=2000 ⇒ 应为 2000,2001,2002,2003,2100,2101,2102,2103
    # 旧句 rid=1 的块是 111,111,112,112 ⇒ **绝不能**出现
    ok_b2 = (len(blocks) == 2
             and vals == [2000.0, 2001.0, 2002.0, 2003.0,
                          2100.0, 2101.0, 2102.0, 2103.0])
    check('B2 rid 过滤：旧句的块与 done 不得串进新句',
          ok_b2, 'vals=%s' % vals)
    eng.close()
except Exception as e:
    check('B2 rid 过滤：旧句的块与 done 不得串进新句', False, repr(e))

# B3：不无限阻塞（假边车永不回应 ⇒ 看门狗必须触发）
try:
    eng, ns = make_client('silent', watchdog_s=2.0, watchdog_first_s=2.0)
    eng.start()
    t0 = time.monotonic()
    err = None
    try:
        collect(eng, '会卡住的句子', timeout=60)
    except Exception as e:
        err = e
    dt = time.monotonic() - t0
    check('B3 边车不回话 ⇒ 看门狗在有限时间内触发（不无限阻塞）',
          err is not None and dt < 30.0,
          'dt=%.1fs err=%r' % (dt, err))
    try:
        eng.close()
    except Exception:
        pass
except Exception as e:
    check('B3 边车不回话 ⇒ 看门狗在有限时间内触发（不无限阻塞）', False,
          repr(e))

# B4：边车崩溃 ⇒ 抛异常而不是挂死
try:
    eng, ns = make_client('crash', watchdog_s=2.0, watchdog_first_s=2.0)
    eng.start()
    err = None
    t0 = time.monotonic()
    try:
        collect(eng, '崩了', timeout=30)
    except Exception as e:
        err = e
    dt = time.monotonic() - t0
    check('B4 边车崩溃 ⇒ 抛异常而不是挂死',
          err is not None and dt < 20.0,
          'dt=%.1fs err=%r' % (dt, err))
    try:
        eng.close()
    except Exception:
        pass
except Exception as e:
    check('B4 边车崩溃 ⇒ 抛异常而不是挂死', False, repr(e))

# B5：set_ref 命令
try:
    eng, ns = make_client('normal')
    eng.start()
    ok_set = eng.set_ref_audio('/tmp/clone_tmp.wav')
    # 客户端应能读到边车的确认（set_ref 会回一条）
    reply = None
    try:
        reply = eng._q.get(timeout=5.0)
    except Exception:
        pass
    check('B5 set_ref：客户端发出命令且边车确认并已切换 ref_audio',
          ok_set and isinstance(reply, str)
          and '"set_ref": true' in reply
          and '/tmp/clone_tmp.wav' in reply,
          'reply=%r ok_set=%s' % (reply, ok_set))
    eng.close()
except Exception as e:
    check('B5 set_ref：客户端发出命令且边车确认并已切换 ref_audio', False,
          repr(e))

print('')
print('=' * 60)
print('PASS=%d  FAIL=%d' % (N_PASS, N_FAIL))
if FAILURES:
    print('--- 失败明细 ---')
    for g, n, d in FAILURES:
        print('  [%s] %s  %s' % (g, n, d))
    # 🔴 APP-027⑥：清理隔离出来的临时 LOCALAPPDATA
    try:
        import shutil
        shutil.rmtree(_TMP_LOCALAPPDATA, ignore_errors=True)
    except Exception:
        pass
    sys.exit(1)
print('全部通过')

# 🔴 APP-027⑥：清理隔离出来的临时 LOCALAPPDATA
try:
    import shutil
    shutil.rmtree(_TMP_LOCALAPPDATA, ignore_errors=True)
except Exception:
    pass
