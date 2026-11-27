"""APP-157 §4：查清多出来的 2 个测试失败（test_ext_selfcheck / test_p1_plumbing）
是「v0.4.25 引起的」还是「换成 v1.2.1 包的 python/路径（包名去掉 Confucius4）引起的」。

2x2 对照（每格都**真跑**那两个测试文件，**抓失败用例名**）：
  行 = EXT 代码版本：v0.4.23 (commit c955411) / v0.4.25 (HEAD 32ff975)
  列 = 解释器：v1.2 包内 python / v1.2.1 包内 python

判据：**失败用例名集合**比 rc/fail 计数更承重（能看出是同一条还是新的一条）。

纪律：这两个测试**不跑推理 / 不占 GPU·NPU / 不抢共享锁**（见两个文件的头注释）
⇒ 不需要 MACHINE_LOCK。
"""
import json
import os
import re
import shutil
import subprocess
import time

EXT_REPO = r'C:\Users\Trekker-PTL\live_dub_ext'
WORKTREE = r'C:\Users\Trekker-PTL\confucius4-openvino\.tmp_recover_app\_ext_v0423'
PY_V12 = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2\python\python.exe'
PY_V121 = r'C:\Users\Trekker-PTL\LiveCaption_MiniMVP_v1.2.1\python\python.exe'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_test_matrix.json'
TESTS = ['test_ext_selfcheck.py', 'test_p1_plumbing.py']


def log(m):
    print(m, flush=True)


def ensure_worktree():
    if os.path.isdir(os.path.join(WORKTREE, '.git')) or os.path.isfile(os.path.join(WORKTREE, '.git')):
        return
    if os.path.isdir(WORKTREE):
        shutil.rmtree(WORKTREE, ignore_errors=True)
    log('== 建 v0.4.23 worktree ==')
    r = subprocess.run(['git', 'worktree', 'add', '--detach', WORKTREE, 'c955411'],
                       cwd=EXT_REPO, capture_output=True, text=True)
    log((r.stdout or '').strip() or (r.stderr or '').strip())
    if r.returncode != 0:
        raise SystemExit('worktree 失败')


def run_one(code_dir, py, test):
    env = dict(os.environ)
    env['PYTHONUTF8'] = '1'
    t0 = time.time()
    try:
        r = subprocess.run([py, os.path.join(code_dir, 'tests', test)],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=900, env=env, cwd=code_dir)
        out = (r.stdout or '') + (r.stderr or '')
        rc = r.returncode
    except subprocess.TimeoutExpired:
        out, rc = 'TIMEOUT', -9
    m = re.search(r'结果：(\d+) PASS / (\d+) FAIL / 共 (\d+)', out)
    npass = int(m.group(1)) if m else None
    nfail = int(m.group(2)) if m else None
    names = []
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r'^(✗|✘|x |FAIL|\[FAIL\]|失败)', s) or ' FAIL ' in s:
            names.append(s[:160])
    return {'rc': rc, 'pass': npass, 'fail': nfail, 'sec': round(time.time() - t0, 1),
            'fail_lines': names[:40]}


def main():
    ensure_worktree()
    matrix = {}
    combos = [('v0.4.23', WORKTREE, PY_V12, 'v1.2'),
              ('v0.4.23', WORKTREE, PY_V121, 'v1.2.1'),
              ('v0.4.25', EXT_REPO, PY_V12, 'v1.2'),
              ('v0.4.25', EXT_REPO, PY_V121, 'v1.2.1')]
    for code_ver, code_dir, py, pkg in combos:
        for test in TESTS:
            key = '%s|%s|%s' % (code_ver, pkg, test)
            log('== %s ==' % key)
            res = run_one(code_dir, py, test)
            log('   rc=%s pass=%s fail=%s (%.1fs)' % (res['rc'], res['pass'], res['fail'], res['sec']))
            for n in res['fail_lines'][:6]:
                log('      %s' % n)
            matrix[key] = res
            json.dump(matrix, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log('DONE -> %s' % OUT)


if __name__ == '__main__':
    main()
