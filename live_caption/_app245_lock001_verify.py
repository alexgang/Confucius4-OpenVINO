"""LOCK-001 APP 侧安装记录 + 行为验证（证据由脚本真跑产出，不手抄）。

包内 python 运行：
  C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_MiniMVP_v1.2.candidate\\python\\python.exe \
      live_caption/_app245_lock001_verify.py

做 5 件事并落盘 results/app/app245_lock001_install.json：
  c0 status 原文
  c1 单作业 run -> acquired / released / rc=0
  c2 持锁期间 status -> HELD (live job)
  c3 第二作业排队 -> waiting ... acquired
  c4 wrapper 整树被杀 -> 系统锁自动放（STALE / FREE）-> reclaim -> FREE
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

PY = sys.executable
ML = r'C:\Users\Trekker-PTL\shared\tools\machine_lock.py'
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
OUT = os.path.join(REPO, 'results', 'app', 'app245_lock001_install.json')


def call(*args, timeout=180):
    t0 = time.time()
    p = subprocess.run([PY, ML] + list(args), capture_output=True,
                       text=True, encoding='utf-8', errors='replace',
                       timeout=timeout)
    return {'argv': list(args), 'rc': p.returncode,
            'out': (p.stdout or '').strip(), 'err': (p.stderr or '').strip(),
            'elapsed_s': round(time.time() - t0, 2)}


def main():
    res = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'interpreter': PY, 'tool': ML, 'cases': {}, 'all_pass': False}

    st = os.stat(ML)
    raw = open(ML, 'rb').read()
    res['install'] = {'path': ML, 'bytes': len(raw),
                      'sha256': hashlib.sha256(raw).hexdigest(),
                      'sha1': hashlib.sha1(raw).hexdigest(),
                      'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                             time.localtime(st.st_mtime))}

    # c0 status
    c0 = call('status')
    res['cases']['c0_status_free'] = dict(c0, ok=(c0['out'].startswith('FREE')))
    print('c0', c0['out'][:60].replace('\n', ' | '), '->', res['cases']['c0_status_free']['ok'])

    # c1 单作业
    c1 = call('run', '--module', 'app', '--note', 'LOCK-001 自检 c1',
              '--', PY, '-c', 'import time;time.sleep(2);print("job ok")')
    ok1 = (c1['rc'] == 0 and '[machine_lock] acquired' in c1['out']
           and '[machine_lock] released (rc=0)' in c1['out'])
    res['cases']['c1_single_run'] = dict(c1, ok=ok1)
    print('c1 rc=%d acquired=%s released=%s -> %s'
          % (c1['rc'], '[machine_lock] acquired' in c1['out'],
             'released (rc=0)' in c1['out'], ok1))

    # c2/c3 并发：长作业 + status + 排队作业
    proc = subprocess.Popen([PY, ML, 'run', '--module', 'app',
                             '--note', 'LOCK-001 自检 c2/c3', '--',
                             PY, '-c', 'import time;time.sleep(8)'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace')
    holder_pid = None
    for _ in range(40):
        time.sleep(0.25)
        if os.path.isfile(LOCK):
            txt = open(LOCK, encoding='utf-8', errors='replace').read()
            m = re.search(r'^(\w+)\s+(\d+)\s', txt, re.M)
            if m:
                holder_pid = int(m.group(2))
                break
    c2 = call('status')
    st2_ok = ('HELD' in c2['out']) and ('live job' in c2['out'])
    res['cases']['c2_status_held'] = dict(c2, ok=st2_ok, lock_text_holder=holder_pid)
    print('c2', c2['out'].splitlines()[0] if c2['out'] else '', '->', st2_ok)

    t0 = time.time()
    c3 = call('run', '--module', 'asr', '--note', 'LOCK-001 自检 c3 排队',
              '--', PY, '-c', 'print("2nd ok")')
    waited = round(time.time() - t0, 1)
    ok3 = (c3['rc'] == 0 and 'waiting; holder' in c3['out']
           and '[machine_lock] acquired' in c3['out'] and waited >= 3)
    res['cases']['c3_queue'] = dict(c3, ok=ok3, waited_s=waited)
    print('c3 waited=%.1fs waiting_line=%s -> %s'
          % (waited, 'waiting; holder' in c3['out'], ok3))
    try:
        proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()

    # c4 杀整树 -> 系统锁自动释放
    p2 = subprocess.Popen([PY, ML, 'run', '--module', 'app',
                           '--note', 'LOCK-001 自检 c4 被杀', '--',
                           PY, '-c', 'import time;time.sleep(120)'],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace')
    pid = None
    for _ in range(40):
        time.sleep(0.25)
        if os.path.isfile(LOCK):
            txt = open(LOCK, encoding='utf-8', errors='replace').read()
            m = re.search(r'^(\w+)\s+(\d+)\s', txt, re.M)
            if m:
                pid = int(m.group(2))
                break
    c4_pre = call('status')
    killed = None
    if pid:
        kp = subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
        killed = {'pid': pid, 'rc': kp.returncode,
                  'out': (kp.stdout or kp.stderr or '').strip()}
    time.sleep(3)
    c4 = call('status')
    # 锁要么已 FREE，要么被判 STALE（文本残留但无活作业）⇒ 两种都算「不会死锁」
    no_deadlock = c4['out'].startswith('FREE') or 'STALE' in c4['out']
    rec = call('reclaim')
    c4b = call('status')
    ok4 = (no_deadlock and c4b['out'].startswith('FREE'))
    res['cases']['c4_kill_release'] = {'pre_status': c4_pre, 'kill': killed,
                                       'after_kill_status': c4,
                                       'reclaim': rec, 'final_status': c4b,
                                       'ok': ok4}
    print('c4 pre=%s | after=%s | reclaim=%s | final=%s -> %s'
          % ((c4_pre['out'] or '').splitlines()[0] if c4_pre['out'] else '',
             (c4['out'] or '').splitlines()[0] if c4['out'] else '',
             (rec['out'] or '').splitlines()[0] if rec['out'] else '',
             (c4b['out'] or '').splitlines()[0] if c4b['out'] else '', ok4))
    try:
        p2.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        p2.kill()

    res['all_pass'] = all(v.get('ok') for k, v in res['cases'].items())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('ALL_PASS =', res['all_pass'], '->', OUT)
    return 0 if res['all_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
