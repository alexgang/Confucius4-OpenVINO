#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §5：**完整流水线**（复制 → 定点同步 → 打包 → 验收 → 音色评测）。

阶段（每阶段**各自取/放机器锁** ⇒ 别的模块可以在阶段之间插队；
但**任何时刻**同一台机器上只有一个模块在跑）：

  ① copy  ：v2.4 ⇒ **v2.5.staging** ⇒ 改名 v2.5（**不覆盖旧目录**）
             ＋ 定点同步 dev 树的 App 侧运行时模块（逐文件 SHA256 + ast.parse 复核）
  ② pack  ：`pack_v13.py --version 2.5 --no-rename-pkg-dir --no-lock`
             （同步版本身份 / MANIFEST / README 改动说明 / 打包 / 逐文件 SHA256 复核 /
               重签 ACCEPTED）
  ③ worker：§1 的 **worker 指令通路**端到端验证（起真实 worker 进程）
  ④ accept：**10 分钟整链验收**（zh + en 两臂，产出逐句 jsonl 与验收 json）
  ⑤ eval  ：§2 的 **预设 A/B 的 CER/WER 对比** + 抽听样本

🔴 **不覆盖/不删除任何旧版本目录与 zip**（v2.4 原封不动）。
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
PY = sys.executable
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'

BUILD = os.path.join(HERE, '_app116_build_v25.py')
WORKER_SWITCH = os.path.join(HERE, 'diag_app116_worker_switch.py')
ACCEPT = os.path.join(RESULTS, '_app588_sp4_acceptance.py')
EVAL = os.path.join(HERE, '_app116_eval_preset.py')
SIGN = os.path.join(HERE, '_app116_sign_accepted.py')


def log(m):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), m), flush=True)


def run(cmd, timeout=7200, cwd=REPO):
    log('RUN %s' % ' '.join(os.path.basename(str(c)) for c in cmd))
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       cwd=cwd)
    out = (p.stdout or '') + (p.stderr or '')
    log('  rc=%d 用时 %.0f s' % (p.returncode, time.time() - t0))
    return p.returncode, out


def main():
    run_id = time.strftime('%Y%m%d-%H%M%S')
    rep = {'run_id': run_id, 'pkg': PKG, 'phases': {}}

    # ① 复制 + 定点同步
    rc, out = run([PY, BUILD, '--stage', 'copy'], timeout=10800)
    rep['phases']['copy_sync'] = {'rc': rc, 'tail': out[-4000:]}
    if rc != 0:
        log('🔴 复制/同步失败 ⇒ 中止')
        _dump(rep)
        return 1

    # ② worker 指令通路（§1）：起真实 worker 进程验证 set_out_device
    rc, out = run([PY, WORKER_SWITCH, '--pkg', PKG], timeout=3600)
    rep['phases']['worker_switch'] = {'rc': rc, 'tail': out[-4000:]}

    # ③ 10 分钟整链验收（zh / en 两臂；脚本自己取锁 ⇒ 锁证据完整）
    #    🔴 必须在**签 ACCEPTED 之前**跑（闸门⑤ 的语义 = 「交付包 == 被验收过的包」）
    accept_ok = True
    for lang in ('zh', 'en'):
        rc, out = run([PY, ACCEPT, '--pkg', PKG, '--lang', lang,
                       '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
                       '--tts-device', 'GPU.0',
                       '--run-id', '%s-%s' % (run_id, lang),
                       '--tag', 'app116_v25', '--lock-note',
                       'app116-v25-%s' % lang], timeout=10800)
        rep['phases']['accept_%s' % lang] = {'rc': rc, 'tail': out[-6000:]}
        if rc != 0:
            accept_ok = False
    if not accept_ok:
        log('🔴 整链验收有臂失败 ⇒ **不签 ACCEPTED**（闸门⑤ 语义）'
            '⇒ 仍继续打包（让 reviewer 看到失败证据），但如实记录')
    else:
        # ④ 重签 ACCEPTED.json（APP-055）
        rc, out = run([PY, SIGN], timeout=1800)
        rep['phases']['sign_accepted'] = {'rc': rc, 'tail': out[-3000:]}
        if rc != 0:
            log('🔴 重签 ACCEPTED 失败 ⇒ 打包必被闸门⑤ 拦下（fail-closed）')

    # ⑤ 打包（zip + 逐文件 SHA256 复核 + 闸门全跑）
    rc, out = run([PY, BUILD, '--stage', 'pack'], timeout=10800)
    rep['phases']['pack'] = {'rc': rc, 'tail': out[-8000:]}

    # ⑥ 预设 A/B 评测（§2）
    rc, out = run([PY, EVAL], timeout=10800)
    rep['phases']['preset_eval'] = {'rc': rc, 'tail': out[-6000:]}

    _dump(rep)
    log('=== 流水线结束 ===')
    return 0


def _dump(rep):
    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, 'app116_pipeline_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % out)


if __name__ == '__main__':
    sys.exit(main())
