#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_close_gui_quit_pkg.py —— §31 验收脚本的**客户包版**。

## 为什么要有这个脚本

🔴 **「仓库里测过」≠「包里的那份是对的」**（长期记忆铁律）
⇒ 关键修复必须**对包内那份单独跑同一套断言**。

本脚本把 `test_tts_close_gui_quit.py` 的全部 REAL 断言**指向客户包目录**
⇒ 证明包内那份 `tts_service.py` / `live_caption_app.py` /
`device_config.py` / `audio_source.py` 真的带上了 §31 的修复。

## 纪律

- **桩 worker**：不跑任何推理、不测速、不占 GPU；
- **不 import 被测模块的重依赖**：包内 `tts_service.py` 只 import stdlib；
- GUI 侧用 `ast` 抽取 `quit()` 源码做**静态**判定（不开 Tk 窗口）。

## 用法

    python results/app/test_tts_close_gui_quit_pkg.py
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
REPO = os.path.dirname(os.path.dirname(HERE))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4'
PKG_APP = os.path.join(PKG, 'app')

# 🔴 **必须**把 `sys.path` 指向**客户包** ⇒ import 到的是包内那份
sys.path.insert(0, PKG_APP)

REAL_FAIL = []
EVIDENCE = {}

STUB = os.path.join(HERE, '_stub_pkg_close_worker.py')

STUB_ALIVE = r'''
import sys, json, os, time
sys.stdout.write(json.dumps({"kind": "ready", "device": "STUB", "voice": "A"}) + "\n")
sys.stdout.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    if msg.get("cmd") == "quit":
        sys.exit(0)
    if msg.get("cmd") == "synth":
        pass
while True:
    time.sleep(0.2)
'''


def real(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        REAL_FAIL.append(name)


def wait_state(svc, want, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False


def wait_for(fn, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return False


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def main():
    if not os.path.isdir(PKG_APP):
        print('!! 客户包目录不存在：%s' % PKG_APP)
        return 1

    print('=' * 72)
    print('§31 验收（客户包版）：包内那份必须带上同样的修复')
    print('（桩 worker，无推理；不跑测速、不占 GPU、不调 MiniMax）')
    print('=' * 72)

    # ── 0 确认 import 到的确实是**包内**那份 ──
    import tts_service
    real('P0 import 到的是客户包那份 tts_service',
         os.path.normcase(os.path.abspath(tts_service.__file__)).startswith(
             os.path.normcase(os.path.abspath(PKG_APP))),
         tts_service.__file__)

    # ── A：close() 计丢句 ──
    print()
    print('[A] 包内 close() 必须清在途句子并计丢句')
    with open(STUB, 'w', encoding='utf-8') as f:
        f.write(STUB_ALIVE)
    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    wait_state(svc, ('ready',), 25.0)
    for i in range(5):
        svc.submit('第 %d 句' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 5)
    n_sub = svc.n_submitted
    svc.close()

    real('PA1 close() 后 pending 清空', len(svc.pending) == 0,
         f'pending={len(svc.pending)}')
    real('PA2 close() 后 _inflight 清空', len(svc._inflight) == 0)
    real('PA3 close() 后 _queue 清空', len(svc._queue) == 0)
    real('PA4 close() 后不变式成立',
         svc.n_played + svc.n_dropped == svc.n_submitted,
         f'played={svc.n_played} dropped={svc.n_dropped} submitted={svc.n_submitted}')
    real('PA5 close() 把在途句子计为丢句',
         svc.n_dropped == 5 and n_sub == 5,
         f'n_dropped={svc.n_dropped} (期望 5)')
    EVIDENCE['pkg_A'] = dict(n_submitted=svc.n_submitted,
                             n_played=svc.n_played,
                             n_dropped=svc.n_dropped)

    # ── B：close() 保留 _dropped_ids ──
    print()
    print('[B] 包内 close() 不得清 _dropped_ids（否则又双记）')
    stub = r'''
import sys, json, time
sys.stdout.write(json.dumps({"kind": "ready", "device": "STUB", "voice": "A"}) + "\n")
sys.stdout.flush()
def later(jid):
    time.sleep(1.2)
    sys.stdout.write(json.dumps({"kind": "played", "id": jid}) + "\n")
    sys.stdout.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    cmd = msg.get("cmd")
    if cmd == "quit":
        sys.exit(0)
    if cmd == "cancel":
        continue
    if cmd == "synth":
        import threading
        threading.Thread(target=later, args=(msg.get("id"),), daemon=True).start()
while True:
    time.sleep(0.2)
'''
    with open(STUB, 'w', encoding='utf-8') as f:
        f.write(stub)
    tts_service._WORKER = STUB

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    wait_state(svc, ('ready',), 25.0)
    for i in range(3):
        svc.submit('第 %d 句' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 3)
    with svc.lock:
        svc.pending.pop(0, None)
        svc._inflight.discard(0)
        svc._dropped_ids.add(0)
    svc.n_dropped += 1
    svc.close()
    real('PB1 close() 保留 _dropped_ids', 0 in svc._dropped_ids,
         f'_dropped_ids={sorted(svc._dropped_ids)}')
    real('PB2 close() 把其余在途句计丢句', svc.n_dropped == 3,
         f'n_dropped={svc.n_dropped} (期望 3)')
    svc._handle_event({'kind': 'played', 'id': 0})
    real('PB3 close() 后到达的 played 改记为已播',
         svc.n_dropped == 2 and svc.n_played == 1,
         f'n_dropped={svc.n_dropped} n_played={svc.n_played}')
    real('PB4 改记后不变式仍成立',
         svc.n_played + svc.n_dropped == svc.n_submitted,
         f'played={svc.n_played} dropped={svc.n_dropped} submitted={svc.n_submitted}')
    EVIDENCE['pkg_B'] = dict(n_dropped=svc.n_dropped,
                             n_played=svc.n_played,
                             n_submitted=svc.n_submitted)

    # ── C：GUI quit() 必须等 MT ──
    print()
    print('[C] 包内 GUI App.quit() 必须等 MT（静态判定，不开 Tk）')
    app_py = os.path.join(PKG_APP, 'live_caption_app.py')
    src = open(app_py, 'r', encoding='utf-8').read()
    tree = ast.parse(src)
    quit_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'quit':
            quit_fn = node
            break
    real('PC0 能定位到 App.quit()', quit_fn is not None)
    if quit_fn is not None:
        fn_src = ast.get_source_segment(src, quit_fn) or ''
        flush_lines = [n.lineno for n in ast.walk(quit_fn)
                       if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute)
                       and n.func.attr == 'flush']
        wait_lines = [n.lineno for n in ast.walk(quit_fn)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == 'wait_idle']
        real('PC1 quit() 里有 mt.flush()', bool(flush_lines), f'行 {flush_lines}')
        real('PC2 quit() 里有 mt.wait_idle()', bool(wait_lines), f'行 {wait_lines}')
        if flush_lines and wait_lines:
            real('PC3 wait_idle 在 flush 之后',
                 min(wait_lines) > min(flush_lines),
                 f'flush@{min(flush_lines)} wait_idle@{min(wait_lines)}')
        real('PC4 wait_idle 有条件守卫（不会白等 180 s）',
             ('if flushed' in fn_src) or ('if self.mt.pending' in fn_src))
        EVIDENCE['pkg_C'] = dict(flush_lines=flush_lines,
                                 wait_lines=wait_lines)

    # ── D：U+FFFD 清零 ──
    print()
    print('[D] 包内两处 U+FFFD 乱码必须清零')
    for p in ('device_config.py', 'audio_source.py'):
        fp = os.path.join(PKG_APP, p)
        raw = open(fp, 'rb').read()
        try:
            s = raw.decode('utf-8')
            ok = True
        except UnicodeDecodeError:
            s = raw.decode('utf-8', errors='replace')
            ok = False
        n = s.count('\ufffd')
        real(f'PD {p} 无 U+FFFD 乱码', n == 0, f'count={n} bytes={len(raw)}')
        EVIDENCE.setdefault('pkg_D', {})[p] = dict(u_fffd=n, bytes=len(raw),
                                                    utf8_ok=ok)

    # ── E：包内 ⇄ 仓库 归一化 SHA 一致 ──
    print()
    print('[E] 包内 ⇄ 仓库 四个文件归一化 SHA256 必须一致')
    for f in ('tts_service.py', 'live_caption_app.py',
              'device_config.py', 'audio_source.py'):
        a = open(os.path.join(REPO, 'live_caption', f), 'rb').read()
        b = open(os.path.join(PKG_APP, f), 'rb').read()
        na = hashlib.sha256(a.replace(b'\r\n', b'\n')).hexdigest()
        nb = hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()
        real(f'PE {f} 归一化 SHA 一致', na == nb,
             f'{na[:16]} vs {nb[:16]}')
        EVIDENCE.setdefault('pkg_E', {})[f] = dict(
            repo_sha_norm=na, pkg_sha_norm=nb, repo_bytes=len(a),
            pkg_bytes=len(b), match=(na == nb))

    print()
    print('=' * 72)
    ok = not REAL_FAIL
    print(f'REAL 失败项：{REAL_FAIL if REAL_FAIL else "无"}')
    print('总判定：' + ('PASS —— 包内那份带上全部 §31 修复'
                        if ok else 'FAIL'))

    ev_path = os.path.join(HERE, 'test_tts_close_gui_quit_pkg_evidence.json')
    with open(ev_path, 'w', encoding='utf-8') as f:
        json.dump(dict(real_fail=REAL_FAIL, evidence=EVIDENCE,
                       verdict='PASS' if ok else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print(f'证据已落盘：{ev_path}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
