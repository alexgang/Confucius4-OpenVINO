r"""app282 — APP-072 §2 闸门③ 前半：**`--check` 自检**（对解压副本跑，输出落盘）。

## 为什么单独写脚本

上一轮的 `--check` 是手工敲的 ⇒ **输出没落盘** ⇒ 报告里只能写「跑过了」，
违反「结论必须引用结果文件与其中的原始字段」。

本脚本把 `--check` 的 stdout/stderr **原样落盘**成 txt ＋ 解析成 json。

## 用法

    .venv/Scripts/python.exe results/app/_app282_rc3_check_arm.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CLEANTEST = r'C:\minimvp_cleantest'
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3'

# 判定用的关键串（**必须**是 `--check` 真实输出的子串 ⇒ 跑完自动校验）
RE_ENV_OK = re.compile(r'环境正常')
RE_ASR_BACKENDS = re.compile(r'ASR 可用后端\s*(\d+)')
RE_GPU = re.compile(r'GPU\.0')
RE_NPU = re.compile(r'\bNPU\b')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=os.path.join(CLEANTEST, PKG_NAME))
    ap.add_argument('--out', default=os.path.join(
        HERE, 'app282_rc3_check_evidence.json'))
    ap.add_argument('--log', default=os.path.join(
        HERE, 'app282_rc3_check_output.txt'))
    args = ap.parse_args()

    pkg = args.pkg
    if not os.path.isdir(pkg):
        raise SystemExit('解压副本不存在：%s' % pkg)

    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    cmd = [py, app, '--check']

    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['LIVECAP_PKG'] = pkg

    t0 = time.time()
    proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=1800)
    wall = time.time() - t0
    text = proc.stdout.decode('utf-8', errors='replace')

    with open(args.log, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)

    m_asr = RE_ASR_BACKENDS.search(text)
    checks = [
        ('① `--check` 退出码为 0', proc.returncode == 0,
         {'rc': proc.returncode, 'wall_s': round(wall, 2)}),
        ('② 输出含「环境正常」', bool(RE_ENV_OK.search(text)),
         {'matched': bool(RE_ENV_OK.search(text))}),
        ('③ 探测到 Intel 集显 GPU.0', bool(RE_GPU.search(text)),
         {'n_gpu0_hits': len(RE_GPU.findall(text))}),
        ('④ 探测到 NPU', bool(RE_NPU.search(text)),
         {'n_npu_hits': len(RE_NPU.findall(text))}),
        ('⑤ 报出 ASR 可用后端数', bool(m_asr),
         {'n_asr_backends': (int(m_asr.group(1)) if m_asr else None)}),
    ]
    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_fail = len(checks) - n_pass
    out = {'script': '_app282_rc3_check_arm.py',
           'correction': 'APP-072 §2 闸门③（--check 部分）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': pkg, 'cmd': cmd, 'rc': proc.returncode,
           'wall_s': round(wall, 2),
           'log': args.log,
           'log_bytes': os.path.getsize(args.log),
           'log_sha256': _sha(args.log),
           'output_text': text,
           'checks': [{'name': n, 'verdict': ok, 'detail': d}
                      for n, ok, d in checks],
           'n_pass': n_pass, 'n_fail': n_fail,
           'verdict': 'PASS' if n_fail == 0 else 'FAIL'}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for n, ok, d in checks:
        print('  [%s] %s  %s' % ('PASS' if ok else 'FAIL', n,
                                  json.dumps(d, ensure_ascii=False)))
    print('\n结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[log] %s' % args.log)
    print('[evidence] %s' % args.out)
    return 0 if n_fail == 0 else 1


def _sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


if __name__ == '__main__':
    sys.exit(main())
