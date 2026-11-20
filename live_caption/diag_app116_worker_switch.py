#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §1：**worker 指令通路**端到端验证（`set_out_device`）。

覆盖 reviewer 要求的「TTS 运行中再切设备」这条路径（真实 worker 进程）：
  ① 用**客户包**的 `tts_worker.py` 起一个真实 worker（带 --out-device=耳机）；
  ② 等 ready ⇒ 读 worker 回的「播放流已启动 / 实际输出」；
  ③ 下发 `set_out_device` ⇒ 切到扬声器 ⇒ 期望 **out_device 事件**里
     `ok=True` 且 `out_desc` 落在扬声器；
  ④ 再切回耳机 ⇒ 期望 `out_desc` 落在耳机；
  ⑤ 下发一个**不存在的设备 id** ⇒ 期望**不静默**：
     要么 ok=False，要么 `fallback` 非空（明说「无法打开 X ⇒ 已改用系统默认」）。

🔴 需要 GPU（worker 会加载 TTS 模型）⇒ **必须持共享机器锁**。
"""
import argparse
import ctypes
import datetime
import json
import os
import subprocess
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
OUT = os.path.join(RESULTS, 'app116_worker_switch')

# Plantronics C320-M / Realtek 扬声器的 WASAPI 端点 id（11-20 本机实测）
HP = '{0.0.0.00000000}.{2e4a781d-034e-4531-926c-cc620edf6d93}'
SPK = '{0.0.0.00000000}.{05fde43c-4ab6-4b3f-bf39-397ffc978640}'

FAILS = []
PASSES = []


def check(name, cond, detail=''):
    (PASSES if cond else FAILS).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  ' + detail) if detail else ''), flush=True)


def log(m):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), m),
          flush=True)


def pid_alive(pid):
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, 0, int(pid))
        if not h:
            return k.GetLastError() != 87
        code = ctypes.c_ulong(0)
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            k.CloseHandle(h)
            return True
        k.CloseHandle(h)
        return code.value == 259
    except Exception:
        return True


def lock_owner():
    try:
        raw = open(LOCK, encoding='utf-8').read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return {'raw': None, 'pid': None, 'unparsed': True}
    parts = raw.split()
    pid = None
    for p in parts:
        if p.isdigit():
            pid = int(p)
            break
    return {'raw': raw, 'pid': pid}


def acquire_lock(note):
    while True:
        own = lock_owner()
        if own is None:
            break
        pid = own.get('pid')
        if pid == os.getpid():
            return own.get('raw')
        if pid and not pid_alive(pid):
            try:
                os.remove(LOCK)
            except Exception:
                pass
            continue
        log('等机器锁（pid=%s 仍存活）' % pid)
        time.sleep(5)
    content = 'app %d %s %s' % (os.getpid(),
                                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                note)
    tmp = LOCK + '.tmp_app116'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(tmp, LOCK)
    log('已取机器锁：%s' % content)
    return content


def release_lock(content):
    own = lock_owner()
    if own and (own.get('raw') == content or own.get('pid') == os.getpid()):
        try:
            os.remove(LOCK)
            log('已放机器锁')
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=os.path.join(HOME, 'Confucius4_LiveCaption_v2.5'))
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    PKG_PY = os.path.join(args.pkg, 'python', 'python.exe')
    worker = os.path.join(args.pkg, 'app', 'tts_worker.py')
    ev = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'pkg': args.pkg, 'events': [], 'startup_log': []}

    content = acquire_lock('app116-worker-switch')
    try:
        cmd = [PKG_PY, worker, '--device', 'GPU.0', '--voice', 'A',
               '--out-device', HP,
               '--out-wav', os.path.join(OUT, 'idle.wav')]
        log('起 worker：%s' % ' '.join(cmd[-6:]))
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                             errors='replace', env=env,
                             cwd=os.path.join(args.pkg, 'app'), bufsize=1)

        def pump(until_kinds, timeout=1200):
            t0 = time.time()
            got = []
            while time.time() - t0 < timeout:
                line = p.stdout.readline()
                if not line:
                    break
                ll = line.strip()
                if ll.startswith('{'):
                    try:
                        msg = json.loads(ll)
                    except Exception:
                        continue
                    got.append(msg)
                    ev['events'].append(msg)
                    if msg.get('kind') in until_kinds:
                        return msg
                else:
                    if ll:
                        ev['startup_log'].append(ll)
            return None

        ready = pump({'ready', 'error'})
        check('worker 就绪', ready is not None and ready.get('kind') == 'ready',
              str(ready)[:160] if ready else 'timeout')
        if not ready:
            raise SystemExit(2)

        # 起始：应当已经开在耳机上
        start_desc = ''
        for lg in ev['startup_log']:
            if '播放流已启动' in lg:
                start_desc = lg
        print('  起始播放流行：%s' % start_desc[:160], flush=True)
        check('① 启动时播放流就落在**所选设备**（耳机）',
              'Plantronics' in start_desc, start_desc[:120])

        def switch(dev, label):
            p.stdin.write(json.dumps({'cmd': 'set_out_device',
                                      'device': dev}) + '\n')
            p.stdin.flush()
            msg = pump({'out_device'}, timeout=120)
            check('② 运行中切到「%s」⇒ 收到 out_device 事件' % label,
                  msg is not None, str(msg)[:160] if msg else 'timeout')
            if msg:
                check('   切到「%s」ok=True' % label, bool(msg.get('ok')),
                      str(msg.get('fallback') or msg.get('error')))
                return msg
            return None

        m1 = switch(SPK, '扬声器')
        if m1:
            check('   切到扬声器后 out_desc 落在 Realtek',
                  'Realtek' in (m1.get('out_desc') or ''),
                  str(m1.get('out_desc')))
            check('   切到扬声器**没有**回落',
                  not m1.get('fallback'), str(m1.get('fallback')))

        m2 = switch(HP, '耳机')
        if m2:
            check('   切回耳机后 out_desc 落在 Plantronics',
                  'Plantronics' in (m2.get('out_desc') or ''),
                  str(m2.get('out_desc')))
            check('   切回耳机**没有**回落',
                  not m2.get('fallback'), str(m2.get('fallback')))

        # ⑤ 不存在的设备 ⇒ 不许静默
        m3 = switch('{0.0.0.00000000}.{deadbeef-0000-0000-0000-000000000000}',
                    '不存在的设备')
        if m3:
            check('③ 不存在的设备**不静默**（ok=False 或 fallback 非空）',
                  (not m3.get('ok')) or bool(m3.get('fallback')),
                  'ok=%s fallback=%r' % (m3.get('ok'), m3.get('fallback')))
            print('  不存在设备的事件：%s' % json.dumps(m3, ensure_ascii=False)[:300],
                  flush=True)

        try:
            p.stdin.write(json.dumps({'cmd': 'quit'}) + '\n')
            p.stdin.flush()
            p.wait(timeout=60)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    finally:
        release_lock(content)

    ev['n_pass'] = len(PASSES)
    ev['n_fail'] = len(FAILS)
    ev['fails'] = FAILS
    out = os.path.join(RESULTS, 'app116_worker_switch_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n=== 汇总 PASS %d / FAIL %d ===' % (len(PASSES), len(FAILS)))
    print('证据：%s' % out)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
