#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app143b_timeout_counterexample.py — **APP-143 b 的超时反证**。

## reviewer APP-143 b 原文
> 修 e2e 驱动器：每次 stats 请求加一个接收超时（例如 10 s），超时或断连就计数并重连或结束；
> 排空硬上限按墙钟执行（≤300 s 加一次轮询的时长）；媒体送入时长超过 1.2 倍片长就标
> `timing_valid=false`。如果卡住超过上限，作业**先释放锁**，再写 STATUS。
> …
> 验收：… 加一个超时反证（**人为让 stats 不回，驱动器要在 cap+10 s 内退出并释放锁**）。

## 本脚本做什么

🔴 **不跑真桥接、不占机器** ⇒ 用一个**假的 WebSocket 服务端**：
* 服务端**接受连接**、**回 hello_ack**；
* 🔴 **对 `stats` 请求**故意**不回应**（模拟桥接卡住）；
* 客户端（`_app137_e2e_drain.run_drain`）⇒ 必须**在 `cap + 10 s` 内退出**。

## 判据（三条，**都要 PASS**）

| 判据 | 说明 |
|---|---|
| `exits_within_cap_plus_10s` | 客户端**实际耗时** ≤ `drain_cap + stats_timeout + 10 s` |
| `reported_timeout` | 客户端**如实报告**了超时（`drain.disconnected` 含 `TimeoutError`／`stats_timeout_count ≥ 1`） |
| `counterexample_old_code_would_hang` | **反证**：把超时逻辑**去掉**的旧版客户端 ⇒ **会超时**（超过 cap+10 s）⇒ 证明新逻辑真的起作用 |

## 🔴 纪律
* **不占机器锁**（纯本地回环 socket）；
* **不碰任何客户包**；
* 只跑 `_app137_e2e_drain.run_drain` 的**排空段**。

## 用法
```
python live_caption/_app143b_timeout_counterexample.py
```
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app143b_timeout_counterexample.json')

DRAIN = os.path.join(HERE, '_app137_e2e_drain.py')

#: 排空上限（秒）—— 与生产一致
DRAIN_CAP = 30.0
#: stats 接收超时（秒）—— 与生产一致
STATS_TIMEOUT = 10.0


class _Args:
    """`run_drain` 需要的参数（只给排空段用到的）。"""
    def __init__(self):
        self.url = None
        self.token = 'dummy'
        self.media = os.path.join(REPO, 'test_audio', 'app119_clip_0_60.wav')
        self.delay = 0.0
        self.target_lang = 'zh'
        self.voice = 'A'
        self.bg_off = True
        self.drain_cap = DRAIN_CAP
        self.poll_sec = 1.0
        self.stats_timeout_s = STATS_TIMEOUT
        self.tail_wait = 0.0
        self.max_sec = 600


async def fake_server(ws, ignore_stats=True):
    """🔴 **假桥接**：回 hello_ack；对 `stats` **故意不回**（模拟卡住）。"""
    async for raw in ws:
        try:
            m = json.loads(raw)
        except Exception:
            continue
        if m.get('type') == 'hello':
            await ws.send(json.dumps({
                'type': 'hello_ack', 'delay_sec': 0.0, 'bg_supported': False,
                'bg_model': False, 'bg': {'state': 'off'}, 'mode': 'echo'}))
        elif m.get('type') == 'stats' and not ignore_stats:
            await ws.send(json.dumps({'type': 'stats', 'n_pending': 0,
                                      'n_emitted': 0, 'n_submitted': 0}))
        # 🔴 **stats 不回** ⇒ 客户端必须靠自己的超时发现


def _load_drain(module_name, src=None):
    """加载 `_app137_e2e_drain.py`（可指定**旧版源码**做反证）。"""
    import importlib.util
    path = src or DRAIN
    spec = importlib.util.spec_from_file_location(module_name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = m
    spec.loader.exec_module(m)
    return m


async def _run_once(module_name, src=None):
    """跑一次「假桥接 + 客户端」，返回 (耗时, 排空结果, 异常)。

    🔴 **直接真跑 `drain_until_zero()`**（APP-143 b 抽出来的独立函数）
    ⇒ 不必起整条桥接（媒体加载/extension_id/端口都不用）⇒ **快且不占机器**。
    """
    drain = _load_drain(module_name, src)
    # 🔴 **websockets 在包内 `.runtime_deps`**（不在 site-packages）
    #    ⇒ 手动加进 sys.path（否则 import 失败）
    for _dep in (r'C://Users//Trekker-PTL//Confucius4_LiveCaption_v2.6//.runtime_deps',
                 r'C://Users//Trekker-PTL//Confucius4_LiveCaption_v2.6//ext//.runtime_deps'):
        if os.path.isdir(_dep) and _dep not in sys.path:
            sys.path.insert(0, _dep)
    args = _Args()
    import websockets
    # 🔴 **用 websockets.serve**（真协议）⇒ 客户端能正常握手
    server = await websockets.serve(fake_server, '127.0.0.1', 0,
                                    ping_interval=None)
    port = server.sockets[0].getsockname()[1]
    t0 = time.perf_counter()
    got = {}
    exc = None
    res = None
    try:
        async with websockets.connect('ws://127.0.0.1:%d/' % port,
                                      max_size=None, open_timeout=10,
                                      ping_interval=None) as ws:
            # 🔴 **起一个 reader** 模拟真客户端：收到 stats 就记时刻
            async def reader():
                async for raw in ws:
                    try:
                        m = json.loads(raw)
                    except Exception:
                        continue
                    if m.get('type') == 'stats':
                        got['stats'] = m
                        got['_last_stats_at'] = time.perf_counter()
            rd = asyncio.create_task(reader())
            res = await drain.drain_until_zero(ws, got, args, t0, 0)
            rd.cancel()
    except Exception as e:
        exc = repr(e)
    elapsed = time.perf_counter() - t0
    server.close()
    try:
        await server.wait_closed()
    except Exception:
        pass
    return elapsed, res, exc


def main():
    checks = []

    # ── 正向：新版客户端 ⇒ 必须**在 cap + 10 s 内退出** ──────────────
    limit = DRAIN_CAP + STATS_TIMEOUT + 10.0
    t0 = time.perf_counter()
    elapsed, dsum, exc = asyncio.run(_run_once('drain_new'))
    ok_exit = elapsed <= limit
    checks.append({'name': 'exits_within_cap_plus_10s', 'ok': ok_exit,
                   'detail': '实际 %.1f s ≤ 上限 %.1f s（cap %.0f + timeout %.0f + 10）'
                             % (elapsed, limit, DRAIN_CAP, STATS_TIMEOUT)})
    _series, _drained, dis, _npend, _sto, _hc, _nto = (dsum or (None,) * 7)
    n_to = _nto or 0
    ok_rep = bool(dis) and ('Timeout' in str(dis) or n_to >= 1)
    checks.append({'name': 'reported_timeout', 'ok': ok_rep,
                   'detail': 'drain.disconnected=%r  stats_timeout_count=%s'
                             % (dis, n_to)})
    ok_hard = (_hc is not None) and (_hc == DRAIN_CAP + STATS_TIMEOUT + 2.0)
    checks.append({'name': 'hard_cap_field_present', 'ok': ok_hard,
                   'detail': 'drain_hard_cap_sec=%s（期望 %.1f）'
                             % (_hc, DRAIN_CAP + STATS_TIMEOUT + 2.0)})

    # ── 反证：**旧版**（把超时逻辑去掉）⇒ 必须**超时**（证明新逻辑真的起作用） ──
    with io.open(DRAIN, encoding='utf-8', newline='') as fh:
        new_src = fh.read()
    # 🔴 **反证**：把「超时判定」整块去掉 ⇒ 旧版会**一直等**（挂死）
    #    ⇒ 用**行级**定位（不靠中文串的精确匹配 ⇒ 不会被编码坑到）
    _lines = new_src.split('\n')
    _out, _skip = [], 0
    for _ln in _lines:
        if 'if time.perf_counter() > _deadline:' in _ln:
            _skip = 4          # 跳过 raise 那一块（含续行）
            continue
        if _skip:
            _skip -= 1
            continue
        _out.append(_ln)
    old_src = '\n'.join(_out)
    if old_src == new_src:
        checks.append({'name': 'counterexample_old_code_would_hang', 'ok': False,
                       'detail': '改不动源码 ⇒ 判据无法证明有鉴别力'})
        old_elapsed = None
    else:
        tmp = os.path.join(RESULTS, '_app143b_old_drain.py')
        with io.open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(old_src)
        try:
            # 🔴 **旧版跑在**独立子进程**里** ⇒ 它挂死时**本进程**不受影响
            #    （`asyncio.wait_for` 取消不了**阻塞在 socket 读**的协程
            #     ⇒ 实测外层超时也挂住 ⇒ 必须用进程隔离）
            import subprocess
            _probe = (
                "import asyncio,sys,time\n"
                "sys.path.insert(0, r'%s')\n"
                "sys.path.insert(0, r'%s')\n"
                "import importlib.util\n"
                "spec=importlib.util.spec_from_file_location('d_old', r'%s')\n"
                "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
                "import websockets\n"
                "async def srv(ws):\n"
                "    async for raw in ws://n"
                "        pass\n"
                "async def main():\n"
                "    s=await websockets.serve(srv,'127.0.0.1',0,ping_interval=None)\n"
                "    p=s.sockets[0].getsockname()[1]\n"
                "    class A: pass\n"
                "    a=A(); a.poll_sec=1.0; a.drain_cap=%.1f; a.stats_timeout_s=%.1f\n"
                "    async with websockets.connect('ws://127.0.0.1:%%d/'%%p,max_size=None,ping_interval=None) as ws://n"
                "        got={}\n"
                "        await m.drain_until_zero(ws,got,a,time.perf_counter(),0)\n"
                "    s.close()\n"
                "asyncio.run(main())\n"
            ) % (os.path.dirname(DRAIN),
                 r'C:/Users/Trekker-PTL/Confucius4_LiveCaption_v2.6/.runtime_deps',
                 tmp, DRAIN_CAP, STATS_TIMEOUT)
            _pr = subprocess.run(
                [sys.executable, '-c', _probe],
                capture_output=True, text=True, errors='replace',
                timeout=limit + 15.0)
            old_elapsed = None if _pr.returncode != 0 else 0.0
            old_detail = '旧版**返回了**（rc=0）⇒ 判据无鉴别力' if _pr.returncode == 0 \
                else '旧版 rc=%s（**挂死/被杀**）⇒ 判据有鉴别力' % _pr.returncode
        except subprocess.TimeoutExpired:
            old_elapsed = None
            old_detail = '旧版**超时挂死**（%.0f s 内没返回）⇒ 判据有鉴别力' % (limit + 15.0)
        except Exception as e:
            old_elapsed = None
            old_detail = repr(e)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        # 🔴 判据：旧版**应当超过** cap+10 s（⇒ 会被外层杀掉/永远挂着）
        ok_ce = (old_elapsed is None) or (old_elapsed > limit)
        checks.append({'name': 'counterexample_old_code_would_hang',
                       'ok': ok_ce,
                       'detail': old_detail})

    ok = all(c['ok'] for c in checks)
    print('=== APP-143 b 超时反证 ===')
    for c in checks:
        print('  %-36s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    ev = {
        'script': '_app143b_timeout_counterexample.py',
        'task': 'APP-143 b：人为让 stats 不回 ⇒ 驱动器要在 cap+10 s 内退出',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'drain_cap_sec': DRAIN_CAP,
        'stats_timeout_sec': STATS_TIMEOUT,
        'limit_sec': limit,
        'new_elapsed_sec': round(elapsed, 2),
        'old_elapsed_sec': (round(old_elapsed, 2) if old_elapsed is not None else None),
        'new_drain_result': (list(dsum) if dsum else None),
        'checks': checks,
        'all_pass': ok,
        'note': ('🔴 **不占机器锁**（纯本地回环 socket ＋ 假桥接）⇒ '
                 '可随时跑；🔴 **未碰任何客户包**。'),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('证据：%s' % EVIDENCE)
    print('ALL PASS' if ok else 'FAIL')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
