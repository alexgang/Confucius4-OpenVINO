#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app199_app054_ab_run.py —— 【APP-054 ③】A/B 两臂实测（旁路开 / 关）。

## 做什么

用**同一条命令**跑两臂（reviewer 指定的命令形态）：

```
--cli --file <SPE 5 分钟切片> --engine gpu_int8 --translate off --tts off
       --asr-device GPU.0 --max-seconds 300 --out <每臂各自的 txt>
```

| 臂 | 旁路 | 期望 |
|---|---|---|
| `off` | 关（默认） | 基线：墙钟 ≈ 音频时长；积压小；出字延迟中位小 |
| `on`  | 开 | **墙钟 ≤ 音频 + 3 s**；**最大积压 ≤ 2 s**；**出字延迟中位相比 off 增加 ≤ 200 ms** |

🔴 **跑在影子包上**（`shared/app053054_shadow`）⇒ **不改用户正在测试的安装目录**
   （APP-054 ⑤ 明文）。
🔴 **不自己调 MiniMax**（质量判定交 reviewer）。
🔴 **不跑 CPU 推理**：ASR 设备由 `--asr-device GPU.0` 指定。

## 计时口径（守「比值必须用同会话内的臂」）

🔴 **两臂必须在同一会话内连续跑** ⇒ solo 漂移（历史实测 ±5%）不影响比值。
🔴 锁：全程持 `shared/MACHINE_LOCK`（`module: app`）。

## 输出

`results/app/app199_app054_ab_evidence.json`

## 用法

    python results/app/app199_app054_ab_run.py [--arms off,on]
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
REPO = os.path.dirname(os.path.dirname(HERE))


def find_repo_root(start: str) -> str:
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('向上查找仓库根失败：%s' % start)
        cur = parent


# ══════════════════════════════════════════════════════════════════════
# 🔴 输出解析：出字延迟 / 积压
# ══════════════════════════════════════════════════════════════════════
# 🔴 **权威来源 = CLI 自己打的汇总行**（`live_caption_app.py` L5688-5689）：
#
#   `[gpu_int8] 音频 300.0s  墙钟 300.6s  RTF(计算) 0.685
#                出字延迟中位 375 ms  最大积压 1.2s  段 46`
#
# ⇒ reviewer 的 perfdiag 表格（「墙钟 / RTF(计算) / 出字延迟中位 / 最大积压」）
#   **就是从这一行取的** ⇒ 本解析器用**同一口径**，不另立标准。
#
# ⚠️ `[perfdiag] arm=… wall=…` 是**编排器自己**的墙钟（含进程启动）⇒
#   **与汇总行的「墙钟」口径不同** ⇒ 两个都记，**报数以汇总行为准**
#   （reviewer 的表格用的是汇总行那一列）。

_RE_SUMMARY = re.compile(
    r'\[(?P<engine>[^\]]+)\]\s*音频\s+(?P<audio>[0-9.]+)s\s*'
    r'墙钟\s+(?P<wall>[0-9.]+)s\s*'
    r'RTF\(计算\)\s+(?P<rtf>[0-9.]+)\s*'
    r'出字延迟中位\s+(?P<lat>[0-9.]+|None)\s*ms\s*'
    r'最大积压\s+(?P<backlog>[0-9.]+)s\s*'
    r'段\s+(?P<segs>[0-9]+)')


def parse_output(path: str) -> dict:
    """解析一臂的 CLI 输出 ⇒ 墙钟 / RTF / 出字延迟 / 最大积压。"""
    out = {'file': path, 'exists': False}
    if not os.path.isfile(path):
        return out
    out['exists'] = True
    out['bytes'] = os.path.getsize(path)
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    # ① 权威汇总行
    m = _RE_SUMMARY.search(text)
    if m:
        out['summary_found'] = True
        out['engine'] = m.group('engine')
        out['audio_s'] = float(m.group('audio'))
        out['wall_s'] = float(m.group('wall'))
        out['rtf'] = float(m.group('rtf'))
        lat = m.group('lat')
        out['first_char_latency_ms'] = (
            None if lat == 'None' else float(lat))
        out['max_backlog_s'] = float(m.group('backlog'))
        out['n_segs'] = int(m.group('segs'))
    else:
        out['summary_found'] = False
        for k in ('audio_s', 'wall_s', 'rtf', 'first_char_latency_ms',
                  'max_backlog_s', 'n_segs'):
            out[k] = None

    # ② 编排器墙钟（含进程启动 ⇒ 与汇总行口径**不同**，两个都记）
    m = re.search(r'\[perfdiag\]\s*arm=(\S+)\s+wall=([0-9.]+)s', text)
    out['runner_wall_s_marker'] = float(m.group(2)) if m else None

    # ③ 说话人标签计数（APP-053 ③ 要在这臂里报覆盖率）
    n_spk = len(re.findall(r'\[spk\]\s*标签补到', text))
    n_reason = len(re.findall(r'\[spk\]\s*第\s*\d+\s*段无说话人标签', text))
    out['n_spk_label_backfilled'] = n_spk
    out['n_spk_no_label_reasons'] = n_reason
    out['spk_lines_sample'] = re.findall(r'\[spk\][^\n]*', text)[:8]

    # ④ 字幕文件里的标签（真正显示给用户的）
    cli_txt = path + '.cli.txt'
    if os.path.isfile(cli_txt):
        with open(cli_txt, 'r', encoding='utf-8', errors='replace') as f:
            sub = f.read()
        out['cli_txt_bytes'] = os.path.getsize(cli_txt)
        out['cli_n_lines'] = len([x for x in sub.splitlines() if x.strip()])
        out['cli_n_spk_tagged_lines'] = len(
            re.findall(r'\[S\d+\]', sub))
    return out


def run_arm(arm: str, shadow: str, wav: str, out_txt: str,
            pkg_python: str) -> dict:
    """跑一臂 ⇒ 返回结果 dict。"""
    app = os.path.join(shadow, 'app')
    runner = os.path.join(HERE, '_app199_arm_runner.py')
    cmd = [pkg_python, runner, arm, app, wav, out_txt]
    env = dict(os.environ)
    # 🔴 宿主 `PYTHONPATH` 会污染包内 python（§112 已证）⇒ **置空**
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    # 🔴 旁路要能定位包内资产 ⇒ 指向影子包
    env['LIVECAP_PKG'] = shadow
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    wall = time.perf_counter() - t0
    res = parse_output(out_txt)
    res.update(arm=arm, runner_wall_s=round(wall, 2),
               rc=proc.returncode)
    res['stdout_tail'] = (proc.stdout or '')[-3000:]
    res['stderr_tail'] = (proc.stderr or '')[-3000:]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='off,on')
    ap.add_argument('--shadow', default=None)
    ap.add_argument('--wav', default=None)
    args = ap.parse_args()

    repo = find_repo_root(HERE)
    shadow = args.shadow or os.path.join(
        os.path.expanduser('~'), 'shared', 'app053054_shadow')
    wav = args.wav or os.path.join(os.path.expanduser('~'), 'shared',
                                   'SPE_0000_0500.wav')
    pkg_python = os.path.join(
        os.path.expanduser('~'), 'Confucius4_LiveCaption_v1.13',
        'python', 'python.exe')

    if not os.path.isdir(os.path.join(shadow, 'app')):
        print('影子包不存在：%s ⇒ 先跑 app198_build_shadow_pkg.py' % shadow)
        return 2
    if not os.path.isfile(wav):
        print('切片不存在：%s' % wav)
        return 2

    outdir = os.path.join(HERE, 'app199_ab_out')
    os.makedirs(outdir, exist_ok=True)

    arms = [a.strip() for a in args.arms.split(',') if a.strip()]
    results = []
    for arm in arms:
        out_txt = os.path.join(outdir, 'arm_%s.txt' % arm)
        if os.path.exists(out_txt):
            os.remove(out_txt)
        print('\n===== 臂 %s 开始（%s）=====' % (arm, time.strftime('%H:%M:%S')))
        r = run_arm(arm, shadow, wav, out_txt, pkg_python)
        print('  rc=%s wall=%s s  audio=%s s  rc_out=%s'
              % (r.get('rc'), r.get('wall_s'), r.get('audio_consumed_s'),
                 r.get('wall_from')))
        if r.get('rc') != 0:
            print('  --- stderr tail ---')
            print(r.get('stderr_tail', '')[-2000:])
        results.append(r)

    # ── 汇总 + APP-054 ③ 验收判据 ──
    by = {r['arm']: r for r in results}
    summary = {}
    checks = []

    def chk(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))

    if 'off' in by and 'on' in by:
        o, n = by['off'], by['on']
        chk('两臂都跑完且有汇总行',
            o.get('summary_found') and n.get('summary_found'),
            dict(off_found=o.get('summary_found'),
                 on_found=n.get('summary_found')))
        # ① 旁路开时墙钟 ≤ 音频 + 3 s
        wn = n.get('wall_s')
        an = n.get('audio_s')
        chk('APP-054 ③ 旁路开时墙钟 ≤ 音频 + 3 s',
            (wn is not None and an is not None and wn <= an + 3.0),
            dict(wall_s=wn, audio_s=an,
                 limit=(None if an is None else round(an + 3.0, 1))))
        # ② 最大积压 ≤ 2 s
        bn = n.get('max_backlog_s')
        chk('APP-054 ③ 旁路开时最大积压 ≤ 2 s',
            (bn is not None and bn <= 2.0),
            dict(max_backlog_s=bn, limit=2.0))
        # ③ 出字延迟中位相比旁路关时增加 ≤ 200 ms
        lo = o.get('first_char_latency_ms')
        ln = n.get('first_char_latency_ms')
        delta = (None if (lo is None or ln is None) else round(ln - lo, 2))
        chk('APP-054 ③ 出字延迟中位相比旁路关时增加 ≤ 200 ms',
            (delta is not None and delta <= 200.0),
            dict(off_ms=lo, on_ms=ln, delta_ms=delta, limit=200.0))
        summary['wall_off_s'] = o.get('wall_s')
        summary['wall_on_s'] = wn
        summary['wall_delta_s'] = (None if (wn is None or o.get('wall_s') is None)
                                    else round(wn - o['wall_s'], 2))
        summary['max_backlog_off_s'] = o.get('max_backlog_s')
        summary['max_backlog_on_s'] = bn
        summary['latency_off_ms'] = lo
        summary['latency_on_ms'] = ln
        summary['latency_delta_ms'] = delta
        summary['rtf_off'] = o.get('rtf')
        summary['rtf_on'] = n.get('rtf')
        summary['n_segs_off'] = o.get('n_segs')
        summary['n_segs_on'] = n.get('n_segs')
        summary['n_spk_backfilled_on'] = n.get('n_spk_label_backfilled')
        summary['cli_n_spk_tagged_lines_on'] = n.get('cli_n_spk_tagged_lines')
        summary['cli_n_lines_on'] = n.get('cli_n_lines')
    else:
        chk('两臂都跑完', False, dict(arms=list(by.keys())))

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = dict(script='app199_app054_ab_run.py', correction='APP-054',
               shadow=shadow, wav=wav, arms=results, summary=summary,
               checks=checks, n_pass=n_pass, n_fail=n_fail,
               verdict='PASS' if n_fail == 0 else 'FAIL',
               ts=time.strftime('%Y-%m-%d %H:%M:%S'))
    with open(os.path.join(HERE, 'app199_app054_ab_evidence.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('\n===== 验收判据 =====')
    for c in checks:
        print('  [%s] %s  %s'
              % ('PASS' if c['ok'] else 'FAIL', c['name'],
                 json.dumps(c['detail'], ensure_ascii=False)))
    print('结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[evidence] %s'
          % os.path.join(HERE, 'app199_app054_ab_evidence.json'))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
