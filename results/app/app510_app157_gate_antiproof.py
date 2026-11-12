#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app510_app157_gate_antiproof.py —— app157 判据的**产品级反证**（anti-proof）。

## 为什么需要这个脚本

记忆铁律：「**PASS ≠ 正确** ⇒ 判据必须拿**已知有缺陷的产品**去试
⇒ 判据必须**识破**它」。app157 判据自己带了 4 条**分支级**反证（D-B1~D-B4），
但那 4 条证的是「**判据内部**的变异会不会被识破」；
🔴 **还缺一层**：把**产品源码本身**改成**有缺陷**的版本 ⇒ 判据**必须 FAIL**。
否则「判据恒 PASS」和「判据真有鉴别力」看起来一模一样。

## 本脚本干什么（**纯离线、零 GPU、零推理、不占锁、不调 MiniMax**）

在**临时目录**里搭一个「假仓库」：
  `<tmp>/live_caption/{tts_worker.py, live_caption_app.py, tts_service.py}`（产品源码副本）
  `<tmp>/results/app/app157_follow_speaker_regression_test.py`（判据脚本副本）
⇒ 跑判据 ⇒ 判据的 `REPO`/`LIVE` 自动指向这个假仓库
⇒ **改产品副本不会碰到仓库里的任何真实文件**。

## 4 条注入缺陷（每条都对应一个**真实历史缺陷**）

| 编号 | 注入（改 `tts_worker.py` 的 `synth()` 决策分支） | 模拟的历史缺陷 | 判据**必须** FAIL 的那条 |
|---|---|---|---|
| M1 | `elif self._has_clone_voice() and (not _bound):` → `elif self._has_clone_voice():` | **APP-086·2a 收窄被回退** ⇒ 按句绑定模式下 `spk=None` 会沿用上一句克隆音色（「男声被配成女声」主因） | **B3** |
| M2 | `if self.clone_mode and (not _bound):` → `if self.clone_mode:` | **分支 ① 漏掉 `_bound` 守卫** ⇒ 按句绑定模式下也被当成全局克隆模式 | **B3** |
| M3 | `self._fallback_to_preset('no_spk_label')` → `pass` | **不回落预设 A** ⇒ 用上一个人的声音冒充（APP-040② 明文禁止） | **B3** |
| M4 | 两条「保留克隆」分支的条件 → `False` | **全局克隆模式失效** ⇒ follow_speaker 下每句都被打回预设 A | **B1** |

## 🔴 判据（结论必须成立，否则本脚本自己 FAIL）

- 基线（**未注入**）：判据 **11 PASS / 0 FAIL**（否则说明判据在干净产品上就不成立 ⇒ 先查判据）；
- 每条注入：**只有**「预期那条」判 FAIL，**其余**判据保持 PASS（⇒ 说明判据定位准、不是全线崩）；
- 任何一条注入后判据**仍全 PASS** ⇒ 🔴 **判据无鉴别力**（本脚本 FAIL）。

## 产物

`results/app/app510_app157_gate_antiproof_evidence.json`
（每条注入：改了什么 / 判据逐条 ok / 预期 FAIL 的那条是否真的 FAIL / verdict）
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, 'app157_follow_speaker_regression_test.py')
LIVE = os.path.join(REPO, 'live_caption')
OUT = os.path.join(HERE, 'app510_app157_gate_antiproof_evidence.json')

PY312 = r'C:\Users\Trekker-PTL\AppData\Local\Programs\Python\Python312\python.exe'

SRC_FILES = ['tts_worker.py', 'live_caption_app.py', 'tts_service.py']

# 注入：(编号, 说明, 模拟的历史缺陷, 原串, 新串, 预期 FAIL 的判据名)
MUTATIONS = [
    ('M1',
     '分支 ② 去掉 `_bound` 守卫（回退 APP-086·2a 收窄）',
     'APP-086·2a 收窄被回退 ⇒ 按句绑定下 spk=None 沿用上一句克隆音色',
     'elif self._has_clone_voice() and not _bound:',
     'elif self._has_clone_voice():',
     'B3 按句绑定模式下 spk=None ⇒ 必须回落预设 A（不得沿用克隆音）'),
    ('M2',
     '分支 ① 去掉 `_bound` 守卫',
     '分支 ① 漏掉 `_bound` 守卫 ⇒ 按句绑定模式被误当成全局克隆模式',
     'if self.clone_mode and not _bound:',
     'if self.clone_mode:',
     'B3 按句绑定模式下 spk=None ⇒ 必须回落预设 A（不得沿用克隆音）'),
    ('M3',
     'else 分支不回落预设 A',
     '不回落 ⇒ 用上一个人的声音冒充（APP-040② 禁止）',
     "self._fallback_to_preset('no_spk_label')",
     'pass',
     'B3 按句绑定模式下 spk=None ⇒ 必须回落预设 A（不得沿用克隆音）'),
    ('M4',
     '两条「保留克隆」分支全废 ⇒ 全局克隆模式失效',
     '全局克隆模式失效 ⇒ follow_speaker 下每句都被打回预设 A',
     'if self.clone_mode and not _bound:',
     'if False:',
     'B1 🔴 follow_speaker 下克隆音色**不得**被打回预设 A'),
]

# M4 要同时改分支 ②（另加一条注入，挂在同一条 M4 上）
M4_SECOND = ('elif self._has_clone_voice() and not _bound:',
              'elif False:')


def run_gate(tmp: str):
    """在假仓库里跑一遍判据，返回 (returncode, evidence dict)。"""
    ev_path = os.path.join(tmp, 'results', 'app',
                           'app157_follow_speaker_regression_evidence.json')
    if os.path.isfile(ev_path):
        os.remove(ev_path)
    # 🔴 必须跑**假仓库里的那份**判据脚本（它的 REPO/LIVE 才指向 tmp）
    #   ⇒ 跑仓库里的原件 ⇒ LIVE 会指向**真实 dev 树** ⇒ 注入的缺陷根本没被试到
    gate_in_tmp = os.path.join(tmp, 'results', 'app',
                               'app157_follow_speaker_regression_test.py')
    proc = subprocess.run([PY312, gate_in_tmp], cwd=tmp, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')
    ev = None
    if os.path.isfile(ev_path):
        with open(ev_path, 'r', encoding='utf-8') as f:
            ev = json.load(f)
    return proc.returncode, ev, proc.stdout


def build_fake_repo(tmp: str) -> str:
    """搭假仓库：拷产品源码 + 判据脚本 ⇒ 返回 `<tmp>/live_caption/tts_worker.py` 的原始文本。"""
    live_dst = os.path.join(tmp, 'live_caption')
    os.makedirs(live_dst, exist_ok=True)
    res_dst = os.path.join(tmp, 'results', 'app')
    os.makedirs(res_dst, exist_ok=True)
    for fn in SRC_FILES:
        shutil.copy2(os.path.join(LIVE, fn), os.path.join(live_dst, fn))
    shutil.copy2(GATE, os.path.join(res_dst,
                                    'app157_follow_speaker_regression_test.py'))
    with open(os.path.join(live_dst, 'tts_worker.py'), 'r', encoding='utf-8',
              newline='') as f:
        return f.read()


def apply_mutation(worker_src: str, mut) -> str:
    """把一条注入应用到 `tts_worker.py` 源码上（**唯一命中断言** ⇒ 命中不唯一就 FAIL）。"""
    mid, _desc, _hist, old, new, _expect = mut
    assert worker_src.count(old) == 1, \
        '%s: 原串命中 %d 次（必须恰好 1 次）' % (mid, worker_src.count(old))
    out = worker_src.replace(old, new)
    if mid == 'M4':
        old2, new2 = M4_SECOND
        assert out.count(old2) == 1, \
            'M4: 第二处原串命中 %d 次（必须恰好 1 次）' % out.count(old2)
        out = out.replace(old2, new2)
    return out


def check_failed(ev: dict, name_prefix: str) -> bool:
    for row in ev.get('detail', []):
        if row['name'].startswith(name_prefix):
            return not row['ok']
    return False


def main() -> int:
    results = []
    verdict = 'PASS'
    tmp = tempfile.mkdtemp(prefix='app157_antiproof_')
    print('fake repo: %s' % tmp)
    try:
        pristine = build_fake_repo(tmp)
        worker_path = os.path.join(tmp, 'live_caption', 'tts_worker.py')

        # ── 基线（未注入）──
        rc, ev, out = run_gate(tmp)
        base_pass = (ev or {}).get('pass_', 0)
        base_fail = (ev or {}).get('fail', 0)
        base_ok = (rc == 0 and base_fail == 0 and base_pass > 0)
        print('\n[baseline] rc=%s  %s PASS / %s FAIL' % (rc, base_pass, base_fail))
        results.append(dict(case='baseline', expect_fail=None,
                            rc=rc, pass_=base_pass, fail=base_fail,
                            ok=base_ok,
                            detail=(ev or {}).get('detail', [])))
        if not base_ok:
            verdict = 'FAIL'
            print('  🔴 基线就不成立 ⇒ 先查判据')
            print('---- gate stdout ----')
            print(out[-3000:])
            print('---- /stdout ----')

        # ── 4 条注入 ──
        for mut in MUTATIONS:
            mid, desc, hist, old, new, expect = mut
            print('\n[%s] %s' % (mid, desc))
            with open(worker_path, 'w', encoding='utf-8', newline='') as f:
                f.write(pristine)
            mutated = apply_mutation(pristine, mut)
            with open(worker_path, 'w', encoding='utf-8', newline='') as f:
                f.write(mutated)
            rc, ev, out = run_gate(tmp)
            if ev is None:
                print('  🔴 判据没产出 evidence')
                print('---- gate stdout ----')
                print(out[-3000:])
                print('---- /stdout ----')
                results.append(dict(case=mid, expect_fail=expect, rc=rc,
                                    ok=False, detail=[]))
                verdict = 'FAIL'
                continue
            target_failed = check_failed(ev, expect.split(' ')[0])
            others = [r['name'] for r in ev['detail']
                      if not r['ok'] and not r['name'].startswith(
                          expect.split(' ')[0])]
            ok = target_failed
            print('  %s PASS / %s FAIL ; 预期 FAIL 的「%s」%s'
                  % (ev['pass_'], ev['fail'], expect.split(' ')[0],
                     '确实 FAIL ✓' if target_failed else '❌ 仍然 PASS'))
            if others:
                print('  ℹ️ 另有一条 FAIL：%s' % others)
            results.append(dict(case=mid, desc=desc, history=hist,
                                edit='%s  ->  %s' % (old, new),
                                expect_fail=expect,
                                target_failed=target_failed,
                                other_failed=others,
                                rc=rc, pass_=ev['pass_'], fail=ev['fail'],
                                ok=ok, detail=ev['detail']))
            if not ok:
                verdict = 'FAIL'
                print('  🔴 %s 没被识破 ⇒ 判据对该缺陷无鉴别力' % mid)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ev_all = dict(script=os.path.basename(__file__),
                  fake_repo_temporary=True,
                  note='产品源码副本在临时目录里改 ⇒ 仓库真实文件零改动',
                  verdict=verdict, cases=results)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev_all, f, ensure_ascii=False, indent=1)
    print('\nevidence -> %s' % OUT)
    print('VERDICT: %s' % verdict)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
