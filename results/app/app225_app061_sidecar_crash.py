#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app225 —— 【APP-061② 附带问题】`Fatal Python error: _enter_buffered_busy`。

## 这个问题是什么

reviewer 在 APP-061② 的「附带问题（不阻塞，但要处理）」里点名：

    边车退出时有 `Fatal Python error: _enter_buffered_busy`（21:24:51）。

§127 / §128 **都没处理**它 ⇒ 本轮补上。

## 根因（已实测复现，不是推测）

`sys.stdin.buffer` 是 `BufferedReader`。边车的**命令读取线程**（daemon）
阻塞在 `readline()` 时**持有该缓冲对象的内部锁**。
边车退出 ⇒ CPython 进入 finalizing ⇒ 要 flush/close 同一个 `BufferedReader`
⇒ **抢不到锁** ⇒

    Fatal Python error: _enter_buffered_busy: could not acquire lock for
    <_io.BufferedReader name='<stdin>'> at interpreter shutdown,
    possibly due to daemon threads

⇒ 边车以 `0xC0000005` 崩掉（父进程看到的是「边车莫名死了」）。

## 修法

读取线程**不再用 `sys.stdin.buffer`**，改用**裸 fd** 的 `os.read(0, …)`
⇒ 不持有任何 Python 缓冲对象的锁 ⇒ 退出时不抢锁 ⇒ 不再崩。

## 🔴 判据非恒真（本脚本的核心）

脚本**同时跑两份**子进程代码（**同一台机器、同一批参数、同一套管道**）：

| 组 | 读取方式 | 期望 |
|---|---|---|
| `orig` | `sys.stdin.buffer.readline()`（改前） | **必须崩**（`_enter_buffered_busy` 出现在 stderr） |
| `fixed` | `os.read(0, …)`（改后） | **必须不崩**（rc=0，stderr 无该致命错误） |

⇒ 只有「改后确实不崩」+「改前确实崩」同时成立，才算判据成立
⇒ **不是恒真**（改前那组就会挂）也不是恒假（改后那组就是好的）。

## 用法

    python results/app/app225_app061_sidecar_crash.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_JSON = os.path.join(HERE, 'app225_app061_sidecar_crash_evidence.json')
SIDECAR_REL = 'live_caption/tts_cuda_sidecar.py'
CHILD = os.path.join(HERE, '_app225_child.py')

# 🔴 两份子进程代码**只差读取方式**，其余完全一样 ⇒ A/B 干净。
# 🔴 **结构照抄真实边车**：读取线程（daemon）+ 主循环等队列 + `quit` 唤醒退出
#   ⇒ 退出时读取线程**正阻塞在读 stdin** ⇒ **这才是崩溃现场**。
#   （若父进程先把 stdin 关掉，读取线程会拿到 EOF 退出 ⇒ 就不会崩 ⇒
#     那样测出来的「不崩」是假的。）
CHILD_TMPL = r'''
import json, os, queue, sys, threading

MODE = %(mode)r
_REQ_Q = queue.Queue()


def _read_buffered():
    # 改前实现：阻塞在 BufferedReader.readline() ⇒ 持有内部锁
    # 🔴 **照抄真实边车的控制流**：`quit` 只把 None 塞进队列（唤醒主循环），
    #   **读取线程本身不退出** ⇒ 它马上又阻塞回 `readline()`
    #   ⇒ 主循环退出时，读取线程**正持锁阻塞在读** ⇒ 崩溃现场成立。
    while True:
        try:
            line = sys.stdin.buffer.readline()
        except Exception:
            line = b''
        if not line:
            _REQ_Q.put(None)
            return
        line = line.strip()
        if not line:
            continue
        sys.stderr.write('GOT:%%s\n' %% line.decode('utf-8', 'replace'))
        sys.stderr.flush()
        try:
            req = json.loads(line.decode('utf-8'))
        except Exception:
            continue
        if req.get('cmd') == 'quit':
            _REQ_Q.put(None)
            continue          # 🔴 **不 return**（与真实边车一致）
        _REQ_Q.put(req)


def _read_raw():
    # 改后实现：裸 fd ⇒ 不持有任何 Python 缓冲对象的锁
    buf = b''
    while True:
        try:
            chunk = os.read(0, 65536)
        except Exception:
            chunk = b''
        if not chunk:
            _REQ_Q.put(None)
            return
        buf += chunk
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            line = line.strip()
            if not line:
                continue
            sys.stderr.write('GOT:%%s\n' %% line.decode('utf-8', 'replace'))
            sys.stderr.flush()
            try:
                req = json.loads(line.decode('utf-8'))
            except Exception:
                continue
            if req.get('cmd') == 'quit':
                _REQ_Q.put(None)
                continue      # 🔴 **不 return**（与真实边车一致）
            _REQ_Q.put(req)


fn = _read_buffered if MODE == 'orig' else _read_raw
t = threading.Thread(target=fn, daemon=True)
t.start()
sys.stderr.write('READY\n')
sys.stderr.flush()

# 主循环：等队列；收到 None（quit / EOF）⇒ 退出主函数 ⇒ **触发解释器 finalizing**
while True:
    req = _REQ_Q.get()
    if req is None:
        sys.stderr.write('EXITING\n')
        sys.stderr.flush()
        break
'''

FATAL_MARK = b'_enter_buffered_busy'


def sha256_file(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_child(mode):
    """跑一份子进程 ⇒ 返回 (rc, stderr, got_line)。

    🔴 **不提前关 stdin**：真实场景是「App 发 `quit` ⇒ 边车主循环退出 ⇒
    解释器 finalizing」，而**读取线程此时还阻塞在读 stdin** ⇒ 才会抢锁崩溃。
    ⇒ 若这里 `communicate()` 先把 stdin 关了，读取线程拿到 EOF 退出 ⇒ **测不出崩溃**。
    """
    with open(CHILD, 'w', encoding='utf-8') as f:
        f.write(CHILD_TMPL % {'mode': mode})
    p = subprocess.Popen([sys.executable, CHILD], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(1.2)
    # 父进程这边发两条：先 ping（证明读取线程真的在收数据）⇒ 再 quit（触发退出）
    wrote = 'OK'
    try:
        p.stdin.write(b'{"cmd":"ping"}\n')
        p.stdin.flush()
        time.sleep(0.6)
        p.stdin.write(b'{"cmd":"quit"}\n')
        p.stdin.flush()
        time.sleep(0.8)
    except Exception as e:
        wrote = 'ERR %r' % (e,)
    # 🔴 **故意不 close stdin** ⇒ 让子进程在「stdin 还开着」时退出
    try:
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
    err = p.stderr.read() if p.stderr else b''
    p.stdout.close()
    p.stderr.close()
    return {
        'mode': mode,
        'parent_write': wrote,
        'rc': p.returncode,
        'stderr': err.decode('utf-8', 'replace'),
        'fatal': FATAL_MARK in err,
        'got_line': 'GOT:' in err.decode('utf-8', 'replace'),
    }


def check_sidecar_source():
    """静态核对：开发版边车**确实**改成了裸 fd 读取，且**不再**用
    `sys.stdin.buffer.readline()`。"""
    path = os.path.join(REPO, SIDECAR_REL.replace('/', os.sep))
    res = {'file': path, 'exists': os.path.isfile(path)}
    if not res['exists']:
        res['ok'] = False
        return res
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    res['sha256'] = sha256_file(path)
    res['bytes'] = len(src.encode('utf-8'))
    tree = ast.parse(src)
    # 找 `_start_command_reader` 里的读取调用
    reader = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == '_start_command_reader'):
            reader = node
            break
    uses_buffered = False
    uses_os_read = False
    if reader is not None:
        for n2 in ast.walk(reader):
            if (isinstance(n2, ast.Call)
                    and isinstance(n2.func, ast.Attribute)
                    and n2.func.attr == 'readline'):
                uses_buffered = True
            if (isinstance(n2, ast.Call)
                    and isinstance(n2.func, ast.Attribute)
                    and n2.func.attr == 'read'
                    and isinstance(n2.func.value, ast.Name)
                    and n2.func.value.id == 'os'):
                uses_os_read = True
    res['uses_buffered_readline'] = uses_buffered
    res['uses_os_read'] = uses_os_read
    res['ok'] = (uses_os_read and not uses_buffered)
    return res


def main() -> int:
    out = {'script': 'app225_app061_sidecar_crash.py',
           'correction': 'APP-061② 附带问题（Fatal Python error: _enter_buffered_busy）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'repo': REPO}
    print('===== ① 静态核对（开发版边车已改用裸 fd）=====')
    src_chk = check_sidecar_source()
    out['sidecar_source'] = src_chk
    print('  用 os.read=%r  用 BufferedReader.readline=%r  ⇒ %s'
          % (src_chk.get('uses_os_read'), src_chk.get('uses_buffered_readline'),
             'PASS' if src_chk.get('ok') else 'FAIL'))

    print('===== ② A/B 实测（同一台机、同一套管道，只差读取方式）=====')
    res = {}
    for mode in ('orig', 'fixed'):
        res[mode] = run_child(mode)
        r = res[mode]
        print('  [%s] mode=%s rc=%s fatal=%r got_line=%r'
              % ('PASS' if ((mode == 'orig') == bool(r['fatal']))
                 else 'FAIL', mode, r['rc'], r['fatal'], r['got_line']))
    out['ab'] = res
    if os.path.isfile(CHILD):
        os.remove(CHILD)

    # 🔴 判据成立的条件：**改前确实崩** 且 **改后确实不崩** 且 **改后确实收到数据**
    ok_orig = bool(res['orig']['fatal'])
    ok_fixed = (not res['fixed']['fatal']) and res['fixed']['rc'] == 0
    ok_data = bool(res['fixed']['got_line'])
    out['checks'] = [
        {'name': '改前（BufferedReader.readline）确实崩 _enter_buffered_busy',
         'ok': ok_orig,
         'detail': 'fatal=%r rc=%r' % (res['orig']['fatal'],
                                       res['orig']['rc'])},
        {'name': '改后（os.read）不再崩，且 rc=0',
         'ok': ok_fixed,
         'detail': 'fatal=%r rc=%r' % (res['fixed']['fatal'],
                                       res['fixed']['rc'])},
        {'name': '改后读取线程**真的收到了数据**（不是「不读所以不崩」）',
         'ok': ok_data,
         'detail': 'got_line=%r' % res['fixed']['got_line']},
        {'name': '开发版边车源码：已用 os.read 且不再用 BufferedReader.readline',
         'ok': bool(src_chk.get('ok')),
         'detail': 'uses_os_read=%r uses_buffered_readline=%r'
                   % (src_chk.get('uses_os_read'),
                      src_chk.get('uses_buffered_readline'))},
    ]
    n_pass = sum(1 for c in out['checks'] if c['ok'])
    out['n_pass'] = n_pass
    out['n_fail'] = len(out['checks']) - n_pass
    out['verdict'] = 'PASS' if out['n_fail'] == 0 else 'FAIL'
    print('\n结果：%d PASS / %d FAIL ⇒ %s'
          % (n_pass, out['n_fail'], out['verdict']))
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[evidence] %s' % OUT_JSON)
    return 0 if out['n_fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
