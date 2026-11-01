#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""🔍 一次性探针：验证 app186 的「回滚」机制**真的有效**。

**为什么必须测失败路径**（MEMORY 铁律：闸门必须自带鉴别力自检）：
「先签后验」是新引入的事务语义 ⇒ 只测成功路径**证明不了**它安全
⇒ 必须人为制造 ⑥ 失败 ⇒ 验证 ACCEPTED.json **被还原**。

**做法**（只改**影子副本**，不碰真包）：
  1. 把真包复制到临时目录
  2. 在影子包里**注入一个真实逻辑缺陷**（改一个真实模块的常量）
  3. 跑 app186（指向影子包）⇒ ⑥ 必须 FAIL
  4. 验证影子包的 ACCEPTED.json **被还原成原字节**
"""
import hashlib
import pkg_paths          # noqa: E402  （单一数据源）


def _find_repo_root(start):
    """向上查找仓库根（祖先目录含 `live_caption/` ＋ `pkg_paths.py`）。

    ⇒ **不写死仓库根**（§118/§119 铁律：写死 ⇒ fresh clone 里是假象）。
    """
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('向上查找仓库根失败：%s' % start)
        cur = parent
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = REPO
PKG = pkg_paths.discover_pkg_dir()
RESULTS = os.path.join(REPO, 'results', 'app')

tmp = tempfile.mkdtemp(prefix='app186_rollback_')
shadow = os.path.join(tmp, 'shadow_app_pkg')
print('[tmp] %s' % tmp)

# 只复制必要部分：ACCEPTED.json + app/（不复制 11 GB 的 models/results）
os.makedirs(shadow, exist_ok=True)
shutil.copy2(os.path.join(PKG, 'ACCEPTED.json'),
             os.path.join(shadow, 'ACCEPTED.json'))
shutil.copytree(os.path.join(PKG, 'app'), os.path.join(shadow, 'app'))

acc_path = os.path.join(shadow, 'ACCEPTED.json')
with open(acc_path, 'rb') as f:
    before_bytes = f.read()
before_sha = hashlib.sha256(before_bytes).hexdigest()
print('[before] ACCEPTED.json bytes=%d sha=%s' % (len(before_bytes),
                                                  before_sha[:32]))

# 注入真实逻辑缺陷：改 gui_status.py 里的一个真实常量
tgt = os.path.join(shadow, 'app', 'gui_status.py')
with open(tgt, 'r', encoding='utf-8') as f:
    src = f.read()
needle = "SEP = '"
i = src.index(needle)
j = src.index('\n', i)
old_line = src[i:j]
src2 = src[:i] + "SEP = 'INJECTED_DEFECT_BY_ROLLBACK_PROBE'" + src[j:]
with open(tgt, 'w', encoding='utf-8') as f:
    f.write(src2)
print('[inject] %s ⇒ %r' % (old_line.strip(), 'INJECTED_DEFECT...'))

# 跑 app186，指向影子包
out_json = os.path.join(RESULTS, '_probe_rollback_evidence.json')
env = dict(os.environ)
proc = subprocess.run(
    [sys.executable, os.path.join(RESULTS, 'app186_app051_acceptance_gate.py'),
     '--pkg', shadow, '--out', out_json, '--write-accepted'],
    capture_output=True, text=True, env=env, cwd=REPO)

print('--- app186 尾部输出 ---')
tail = [ln for ln in proc.stdout.splitlines()
        if ('FAIL' in ln or 'PASS ' in ln or '事务' in ln or '回滚' in ln
            or '提交' in ln or '子项' in ln)]
for ln in tail[-25:]:
    print('  ' + ln)
print('  exit=%d' % proc.returncode)

# ── 验证回滚 ──
with open(acc_path, 'rb') as f:
    after_bytes = f.read()
after_sha = hashlib.sha256(after_bytes).hexdigest()
print()
print('=== 回滚验证 ===')
print('  after bytes=%d sha=%s' % (len(after_bytes), after_sha[:32]))
same = (after_bytes == before_bytes)
print('  ACCEPTED.json 是否被**原样还原**？ %s' % ('✅ 是' if same else '🔴 否'))
if not same:
    try:
        a = json.loads(after_bytes.decode('utf-8'))
        print('  after 里 code_fingerprint = %r'
              % a.get('code_fingerprint'))
        print('  after 里 accepted_at      = %r' % a.get('accepted_at'))
    except Exception as e:
        print('  解析失败：%r' % e)

# 清理
shutil.rmtree(tmp, ignore_errors=True)
print()
print('[cleanup] 已删除影子副本 %s' % tmp)
