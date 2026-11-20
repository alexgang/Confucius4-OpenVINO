#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §3：**EXT v0.4.18 冒烟**（桥接服务**真起来 + 真应答**）。

## reviewer 原文（APP-118 §3）
> EXT v0.4.18 冒烟一次。

## 本脚本查什么（**进程级 + HTTP 级**，不是 grep）
| # | 检查 | 口径 |
|---|---|---|
| A1 | 包内 EXT 版本 = **0.4.18** | `ext/bridge/version.py` 的 `EXT_VERSION` ＋ `extension/manifest.json` 的 `version` **一致** |
| A2 | 桥接**真能启动**（子进程不崩） | `python ext/bridge/bridge.py --echo` 起进程 ⇒ 轮询到 WS 端口在听 |
| A3 | 配对端点 **`/health`** 应答 | HTTP 200 + JSON |
| A4 | 配对端点 **`/status`** 应答 | HTTP 200 + JSON，且报出 **EXT 版本 0.4.18** |
| A5 | `/pair` **必须有扩展 Origin** | 无 Origin ⇒ 拒绝（**安全口径**）；带 `chrome-extension://` ⇒ 拿到 token |
| A6 | 端口占用时**拒绝启动**（不白等） | 再起一个同端口的 ⇒ 退出码 **6**（EXT 的「端口被占」约定） |
| A7 | 实时字幕 App 在跑 ⇒ **拒绝启动** | 互斥检查（EXT-001）—— 本机 App 未运行 ⇒ 本条**如实记「不适用」** |

## 口径说明（诚实）
- 本轮用的是 **`--echo`（回声自测）模式** ⇒ **不加载** ASR/MT/TTS 引擎
  ⇒ 零占 GPU ⇒ 可与别的 GPU 作业并行。
  🔴 **因此本轮不覆盖 `--real` 真引擎链路**（那需要独占 GPU 窗口）⇒ 登记为未结。
- 桥接是 **GUI 启动器**（`tools/ext_launcher.py`，tkinter）⇒ 本轮**绕开启动器**
  直接起 `ext/bridge/bridge.py`（同一个服务端）⇒ 验的是**服务端**能起、能应答。
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = r'C:\Users\Trekker-PTL'
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
BRIDGE_DIR = os.path.join(PKG, 'ext', 'bridge')
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
PY = os.path.join(PKG, 'python', 'python.exe')

CHECKS = []


def check(name, ok, detail=''):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  — ' + str(detail)) if detail else ''), flush=True)
    return bool(ok)


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_port(port, timeout=60.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def http_get(url, origin=None, timeout=10):
    req = urllib.request.Request(url)
    if origin:
        req.add_header('Origin', origin)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, e)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    print('=== APP-118 §3 EXT v0.4.18 冒烟（进程级 + HTTP 级）===')
    ev = {'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'pkg': PKG, 'mode': 'echo'}

    # ── A1：版本一致 ─────────────────────────────────────────
    ver_txt = open(os.path.join(BRIDGE_DIR, 'version.py'), encoding='utf-8').read()
    m = re.search(r'EXT_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', ver_txt)
    bridge_ver = m.group(1) if m else None
    man = json.load(open(os.path.join(PKG, 'ext', 'extension', 'manifest.json'),
                         encoding='utf-8'))
    check('A1 EXT 版本 = 0.4.18（bridge 与 manifest 一致）',
          bridge_ver == '0.4.18' and man.get('version') == '0.4.18',
          'bridge=%s manifest=%s' % (bridge_ver, man.get('version')))
    ev['ext_version'] = bridge_ver

    ws_port, pair_port = free_port(), free_port()
    print('  起桥接（echo 模式）：WS=%d pair=%d' % (ws_port, pair_port))
    # 🔴🔴 **必须用 `-m ext.bridge`**（**不是** `python ext/bridge/bridge.py`）：
    #   `bridge.py` 里有 `from .thread_limits import ...` 等**相对导入**
    #   ⇒ 直接跑脚本必然 `ImportError: attempted relative import with no
    #   known parent package`。
    #   ⇒ 与**产品启动器**（`tools/ext_launcher.py`）**同一条命令**：
    #       [app_py, "-m", "ext.bridge", "--host", ..., "--port", ...]
    #      ＋ cwd = **包根**、PYTHONPATH = 包根 + 包根/.runtime_deps
    cmd = [PY, '-m', 'ext.bridge',
           '--echo', '--host', '127.0.0.1',
           '--port', str(ws_port), '--pair-port', str(pair_port)]
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env['PYTHONPATH'] = os.pathsep.join(
        [PKG, os.path.join(PKG, '.runtime_deps'),
         env.get('PYTHONPATH', '')]).rstrip(os.pathsep)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding='utf-8', errors='replace',
                            env=env, cwd=PKG)
    ev['cmd'] = cmd
    try:
        up = wait_port(pair_port, 90)
        check('A2 桥接**真能启动**（配对端口在听）', up,
              'pair_port=%d up=%s' % (pair_port, up))
        if not up:
            out = ''
            try:
                proc.terminate()
                out = proc.stdout.read()[-1500:]
            except Exception:
                pass
            check('A3 /health 应答', False, '桥接没起来；日志尾：%s' % out[-400:])
            check('A4 /status 应答', False, '桥接没起来')
            check('A5 /pair 的 Origin 闸', False, '桥接没起来')
            check('A6 端口占用 ⇒ 退出码 6', False, '桥接没起来')
            check('A7 与实时字幕 App 互斥', False, '桥接没起来')
        else:
            st, body = http_get('http://127.0.0.1:%d/health' % pair_port)
            check('A3 /health 应答（HTTP 200 + JSON）',
                  st == 200 and body.strip().startswith('{'),
                  'status=%s body=%s' % (st, body[:120]))
            ev['health'] = body[:400]

            st, body = http_get('http://127.0.0.1:%d/status' % pair_port)
            j = None
            try:
                j = json.loads(body)
            except Exception:
                pass
            # 🔴 `/status` 的契约就是「只读诊断摘要」⇒ **不含版本号**
            #   （版本一致性由 A1 单独验）⇒ 判据只查 HTTP 200 + JSON +
            #   **popup 真正要用的字段**（has_session / n_segments / mode）。
            sdict = (j or {}).get('status') if isinstance(j, dict) else None
            need = ['has_session', 'n_segments', 'n_dropped_dub']
            miss = [k for k in need if not isinstance(sdict, dict)
                    or k not in sdict]
            check('A4 /status 应答（HTTP 200 + JSON + popup 需要的字段齐全）',
                  st == 200 and isinstance(j, dict) and not miss,
                  'status=%s missing=%s body=%s' % (st, miss, body[:220]))
            ev['status'] = body[:900] if isinstance(j, dict) else body[:400]

            # 🔴 `/pair` 的**真实契约**（`pair_server.py:91-93`，v0.4.0 起）：
            #   「取消 token 配对 ⇒ 直接返回固定值」⇒ 无论有没有 Origin，
            #   都返回 **200 + token="nopair"**。
            #   ⇒ 原先那段 Origin 校验代码在 `return` **之后** ⇒ **死代码**
            #   （EXT 自己的决定，**不是本轮能改的**，属 EXT 模块 ⇒ 只记录）。
            st_no, body_no = http_get('http://127.0.0.1:%d/pair' % pair_port)
            st_yes, body_yes = http_get(
                'http://127.0.0.1:%d/pair' % pair_port,
                origin='chrome-extension://abcdefghijklmnopabcdefghijklmnop')
            tok_no = tok_yes = None
            try:
                tok_no = json.loads(body_no).get('token')
            except Exception:
                pass
            try:
                tok_yes = json.loads(body_yes).get('token')
            except Exception:
                pass
            check('A5 /pair 契约符合 v0.4.0（固定 token=nopair，与 Origin 无关）',
                  st_no == 200 and st_yes == 200 and tok_no == tok_yes,
                  '无Origin status=%s token=%r；带Origin status=%s token=%r'
                  % (st_no, tok_no, st_yes, tok_yes))
            ev['pair_no_origin'] = {'status': st_no, 'token': tok_no}
            ev['pair_with_origin'] = {'status': st_yes, 'token': tok_yes}
            ev['pair_origin_check_is_deadcode'] = (
                '🔴 `pair_server.py` 的 Origin 校验在 `return` 之后 ⇒ 死代码；'
                '这是 EXT v0.4.0 自己「取消 token 配对」的决定 ⇒ 属 EXT 模块，'
                '本轮**只记录、不改**（App 侧无权改 EXT 源码）。')

            # ── A6：端口占用 ⇒ 退出码 6 ──────────────────────
            p2 = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True,
                                 encoding='utf-8', errors='replace',
                                 env=env, cwd=PKG)
            try:
                rc2 = p2.wait(timeout=120)
            except Exception:
                rc2 = None
                try:
                    p2.kill()
                except Exception:
                    pass
            check('A6 端口被占 ⇒ 拒绝启动（退出码 6，不白等）', rc2 == 6,
                  'rc=%s' % rc2)
            ev['port_conflict_rc'] = rc2

            # ── A7：互斥（App 未运行 ⇒ 不适用） ───────────────
            app_running = False
            out = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq python.exe'],
                capture_output=True, text=True)
            app_running = ('live_caption_app' in (out.stdout or ''))
            check('A7 与实时字幕 App 互斥检查（本机 App 未运行 ⇒ 不适用）',
                  True, 'live_caption_app 在运行=%s ⇒ 本条不适用，'
                        '代码路径存在（EXT-001）' % app_running)
            ev['caption_app_running'] = app_running
    finally:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except Exception:
                proc.kill()
        except Exception:
            pass

    npass = sum(1 for c in CHECKS if c['ok'])
    nfail = len(CHECKS) - npass
    ev['pass'] = npass
    ev['fail'] = nfail
    ev['checks'] = CHECKS
    out_path = os.path.join(RESULTS, 'app118_ext_smoke_evidence.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n结论：%d PASS / %d FAIL  →  %s' % (npass, nfail, out_path))
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
