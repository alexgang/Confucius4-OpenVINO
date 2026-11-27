"""APP-157 §6：在隔离解压出的那份包上起一次 EXT 桥接，确认从新包名找到 app 根和模型。
用 machine_lock.py run 持锁（占 GPU/NPU），2 分钟硬超时自动杀进程树并释放锁。
产品同款路径：-m ext.bridge --real --pipeline。
"""
import json
import os
import subprocess
import time

ROOT = r'C:\Users\Trekker-PTL'
PKG = os.path.join(r'C:\Temp', 'verify_v121_app157', 'LiveCaption_MiniMVP_v1.2.1')
PY = os.path.join(PKG, 'python', 'python.exe')
LOCK = os.path.join(ROOT, 'shared', 'tools', 'machine_lock.py')
OUT = os.path.join(ROOT, 'confucius4-openvino', 'results', 'app', 'app157_bridge_check.json')
LOG = os.path.join(ROOT, 'confucius4-openvino', 'results', 'app', 'app157_bridge_check.log')


def main():
    assert os.path.isfile(PY) and os.path.isdir(os.path.join(PKG, 'ext', 'bridge')), PKG
    env = dict(os.environ)
    env['EXT_APP_ROOT'] = PKG
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    # 产品同款：ext_launcher.py 把包根 + .runtime_deps 放进 PYTHONPATH
    # （`ext` 是 PEP 420 namespace package，子包是 ext/bridge/）
    env['PYTHONPATH'] = os.pathsep.join(
        [PKG, os.path.join(PKG, '.runtime_deps')] +
        ([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    cmd = [PY, LOCK, 'run', '--module', 'app',
           '--note', 'app157 isolated extracted bridge startup',
           '--wait-min', '20', '--timeout-min', '2', '--',
           PY, '-m', 'ext.bridge', '--real', '--pipeline',
           '--target-lang', 'zh', '--port', '8791']
    t0 = time.time()
    p = subprocess.run(cmd, cwd=PKG, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=600)
    text = (p.stdout or b'').decode('utf-8', errors='replace')
    with open(LOG, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    keys = {k: (k in text) for k in ('ASR 就绪', 'MT 就绪', 'Qwen3-ASR 0.6B',
                                     'Hy-MT3', 'Traceback')}
    ev = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
          'pkg': PKG, 'cmd': cmd, 'rc': p.returncode,
          'elapsed_s': round(time.time() - t0, 1),
          'landmarks': keys,
          'ok': keys['ASR 就绪'] and keys['MT 就绪']
                and keys['Qwen3-ASR 0.6B'] and keys['Hy-MT3']
                and not keys['Traceback'],
          'log': LOG}
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print(json.dumps(keys, ensure_ascii=False))
    print('结论 %s -> %s' % ('PASS' if ev['ok'] else 'FAIL', OUT))
    return 0 if ev['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
