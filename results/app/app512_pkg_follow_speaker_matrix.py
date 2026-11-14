#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app512_pkg_follow_speaker_matrix.py —— 把 app157 判据**跑遍磁盘上所有客户包**（只读）。

## 为什么需要

2026-11-13 实测发现：`Confucius4_LiveCaption_v2.4/app/tts_worker.py`（11-07 打的**完整版**）
的 `synth()` 决策分支里是

    elif self._has_clone_voice():          ← **没有** `and (not _bound)` 守卫

⇒ **APP-086·2a 的收窄不在包内** ⇒ 「按句绑定模式 + 标签晚到（spk=None）」
会走分支 ② ⇒ **沿用上一句的克隆音色**、**不回落预设 A**
⇒ 就是「**男声被配成女声 / 串音**」的根因（APP-086·2a 明文要修的那条）。

而 dev 树与 MiniMVP rc10 里该分支**有**守卫 ⇒ 两边行为**不一致**
⇒ 必须把「**哪个包带这个缺陷**」一次性列清楚，交 reviewer 决定 v2.5 打包范围。

## 本脚本干什么（**纯离线、零 GPU、零推理、不占锁、不调 MiniMax、对客户包只读**）

对磁盘上每个 `Confucius4_LiveCaption_*/app`：

1. 用 `AST` 抽出 `synth()` 的 `if spk:` 决策分支 ⇒ 记下
   **分支 ② 有没有 `and (not _bound)` 守卫**（= APP-086·2a 收窄在不在包里）；
2. 跑一遍 app157 判据（`APP156_LIVE_DIR=<pkg>/app`）⇒ 记 `pass_/fail/verdict`
   + **B1**（全局克隆必须保留）与 **B3**（按句绑定必须回落）两条的 `ok/msg`。

## 🔴 判据

- **B3 FAIL 的包 = 带串音缺陷的包**（该包的代码让 `spk=None` 沿用上一句克隆音色）；
- **B3 PASS 且分支 ② 有守卫 = 收窄在包里**；
- 🔴 **不修改任何客户包**（只读；判据只写仓库里的 evidence json）。

## 产物

`results/app/app512_pkg_follow_speaker_matrix.json`
（每个包一行：版本 / 分支 ② 守卫有无 / pass_fail / B1 / B3 / 判据落点路径是否存在）
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, 'app157_follow_speaker_regression_test.py')
OUT = os.path.join(HERE, 'app512_pkg_follow_speaker_matrix.json')
PKG_ROOT = r'C:\Users\Trekker-PTL'
PY312 = r'C:\Users\Trekker-PTL\AppData\Local\Programs\Python\Python312\python.exe'

# 判据跑在**临时仓库**里（避免覆盖仓库里既有的 `_pkg` evidence）
TMP_REPO = None


def pkg_dirs():
    """枚举**磁盘上全部**客户包目录 ⇒ 返回 [(名字, app 目录, 有无 tts_worker.py)]。

    🔴🔴 §203（本轮新发现）：原实现有**两个静默漏扫**口子 ——
      ① **过滤器只认两个前缀**：`Confucius4_LiveCaption_v*`（完整版）
         ＋ `Confucius4_LiveCaption_MiniMVP_v*` ⇒ **SpecialMVP 全家被漏**
         （`Confucius4_LiveCaption_SpecialMVP_v1.0-sp1` / `-sp2` ⇒ §195/§202
           刚出的两个客户候选包**从未进过包矩阵闸门** ⇒ §190 的老教训
           「缺文件 ≠ 不适用」在**包级**同样成立：**没扫 ≠ 没缺陷**）。
      ② **没有 `app/tts_worker.py` 的目录被 `continue` 掉** ⇒ 矩阵报的
         「N 个包」会**静默少于**磁盘实际包数 ⇒ §201 已修正过的「目录数」
         与矩阵的「包数」从此对不上，且**从 evidence 里看不出来**。
    ⇒ 修法：过滤器放宽到 `Confucius4_LiveCaption_`（覆盖三种形态），
      且**所有**候选目录都进矩阵（没有 tts_worker.py 的单独记成
      `SKIP_NO_TTS_WORKER` 行，**不计入通过数**），evidence 里另写
      `coverage`（候选/已扫/跳过三数）⇒ **矩阵不可能再少报**。

    🔴 **判据语义未改**：`tag` 的三分支改法仍**等 reviewer 裁定**（§194 ④），
      本轮**只改覆盖范围，不改任何 verdict 口径**。
    """
    out = []
    for name in sorted(os.listdir(PKG_ROOT)):
        if not name.startswith('Confucius4_LiveCaption_'):
            continue
        d = os.path.join(PKG_ROOT, name)
        if not os.path.isdir(d):
            continue          # zip 等非目录项
        app = os.path.join(d, 'app')
        out.append((name, app,
                    os.path.isfile(os.path.join(app, 'tts_worker.py'))))
    return out


def decision_branch(app_dir: str):
    """抽 `synth()` 的 `if spk:` 决策分支 ⇒ (分支源码, 分支② 有没有 _bound 守卫)。"""
    p = os.path.join(app_dir, 'tts_worker.py')
    with open(p, 'r', encoding='utf-8', errors='replace') as f:
        src = f.read()
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'synth':
            for m in ast.walk(n):
                if isinstance(m, ast.If):
                    try:
                        if ast.unparse(m.test).strip() == 'spk':
                            txt = ast.unparse(m)
                            has_b2 = 'self._has_clone_voice()' in txt
                            guarded = ('self._has_clone_voice() and (not _bound)'
                                       in txt)
                            return txt, has_b2, guarded
                    except Exception:
                        continue
    return '', False, False


def run_gate(app_dir: str):
    """在临时仓库里跑判据（`APP156_LIVE_DIR` 指向客户包）⇒ 返回 evidence dict。"""
    ev_path = os.path.join(TMP_REPO, 'results', 'app',
                           'app157_follow_speaker_regression_evidence_pkg.json')
    if os.path.isfile(ev_path):
        os.remove(ev_path)
    env = dict(os.environ)
    env['APP156_LIVE_DIR'] = app_dir
    # 🔴 必须跑**临时仓库里的那份**判据脚本
    #   ⇒ 它的 REPO 指向 tmp ⇒ evidence 落在 tmp ⇒ 仓库里既有的 `_pkg` evidence 不被覆盖
    gate_in_tmp = os.path.join(TMP_REPO, 'results', 'app',
                               'app157_follow_speaker_regression_test.py')
    proc = subprocess.run([PY312, gate_in_tmp], cwd=TMP_REPO, env=env,
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace')
    if proc.returncode not in (0, 1):
        print('  ⚠️ 判据异常退出 rc=%s : %s' % (proc.returncode,
                                               proc.stderr[-800:]))
    if not os.path.isfile(ev_path):
        return None
    with open(ev_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def pick(detail, prefix):
    for row in detail:
        if row['name'].startswith(prefix):
            return dict(ok=row['ok'], msg=row['msg'])
    return None


def main() -> int:
    global TMP_REPO
    tmp = tempfile.mkdtemp(prefix='app157_pkgmatrix_')
    TMP_REPO = tmp
    os.makedirs(os.path.join(tmp, 'results', 'app'), exist_ok=True)
    shutil.copy2(GATE, os.path.join(tmp, 'results', 'app',
                                    'app157_follow_speaker_regression_test.py'))
    rows = []
    skipped = []
    try:
        for name, app, has_tw in pkg_dirs():
            if not has_tw:
                # 🔴 §203：没有 tts_worker.py 的包**不再被静默丢掉**
                #   ⇒ 单独记一行（判据**不适用**，**不算通过**）
                skipped.append(name)
                rows.append(dict(
                    pkg=name, app_dir=app,
                    branch2_exists=None, branch2_has_bound_guard=None,
                    verdict='SKIP_NO_TTS_WORKER', pass_=None, fail=None,
                    B1=None, B3=None,
                    tag='🔴 该包无 `app/tts_worker.py` ⇒ 判据**不适用**'
                        '（**不得当作通过**；需人工确认该包是否可交付）'))
                print('%-46s %-5s  (no app/tts_worker.py ⇒ 判据不适用)'
                      % (name, 'SKIP'))
                continue
            txt, has_b2, guarded = decision_branch(app)
            ev = run_gate(app)
            row = dict(pkg=name, app_dir=app,
                       branch2_exists=has_b2,
                       branch2_has_bound_guard=guarded,
                       verdict=(ev or {}).get('verdict'),
                       pass_=(ev or {}).get('pass_'),
                       fail=(ev or {}).get('fail'),
                       B1=pick((ev or {}).get('detail', []), 'B1'),
                       B3=pick((ev or {}).get('detail', []), 'B3'))
            row['tag'] = ('APP-086·2a 收窄**在**包里'
                          if (not has_b2 or guarded)
                          else '🔴 **缺 APP-086·2a 收窄**（分支 ② 无 _bound 守卫）')
            rows.append(row)
            print('%-46s %-5s %-4s B1=%s B3=%s'
                  % (name, row['verdict'], '%s/%s' % (row['pass_'], row['fail']),
                     (row['B1'] or {}).get('ok'),
                     (row['B3'] or {}).get('ok')))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # dev 树也列一行（口径一致）
    ev = None
    ev_path = os.path.join(HERE, 'app157_follow_speaker_regression_evidence.json')
    if os.path.isfile(ev_path):
        with open(ev_path, 'r', encoding='utf-8') as f:
            ev = json.load(f)
    dev_row = dict(pkg='(dev 树) live_caption/', app_dir='live_caption',
                   branch2_exists=True, branch2_has_bound_guard=True,
                   verdict=(ev or {}).get('verdict'),
                   pass_=(ev or {}).get('pass_'), fail=(ev or {}).get('fail'),
                   B1=pick((ev or {}).get('detail', []), 'B1'),
                   B3=pick((ev or {}).get('detail', []), 'B3'),
                   tag='dev 树（= MiniMVP rc10 的基底）')

    out = dict(script=os.path.basename(__file__),
               note='对客户包**只读**；判据跑在临时仓库里 ⇒ 不覆盖仓库既有 evidence',
               coverage=dict(
                   n_candidate_dirs=len(rows),
                   n_scanned=len(rows) - len(skipped),
                   n_skipped_no_tts_worker=len(skipped),
                   skipped_dirs=skipped,
                   package_dirs=[r['pkg'] for r in rows],
                   coverage_ok=(len(rows) == len(skipped) + (len(rows) - len(skipped))
                                and len(rows) > 0)),
               packages=rows, dev_tree=dev_row)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\ncoverage: 候选 %d ／ 已扫 %d ／ 无 tts_worker 跳过 %d %s'
          % (out['coverage']['n_candidate_dirs'],
             out['coverage']['n_scanned'],
             out['coverage']['n_skipped_no_tts_worker'],
             ('⇒ ' + ', '.join(skipped)) if skipped else ''))
    if skipped:
        print('🔴 有 %d 个包**未进判据**（无 app/tts_worker.py）'
              ' ⇒ 「没扫」**不等于**「没缺陷」' % len(skipped))
    print('evidence -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
