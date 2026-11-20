#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **APP-119 §3 验收：10 分钟整链两臂**的**包装器**。

只做三件事（**不新建判据脚本** —— 判据仍是既有的 `_app588_sp4_acceptance.py`，
APP-110 §1 纪律）：

  ① 把自己的 PID 登记进**会话租约**（长作业 ⇒ 别的会话 BUSY，不会重复跑）；
  ② 用**产品同款调用路径**跑既有验收脚本（它自己管 MACHINE_LOCK）；
  ③ 跑完把结果 json 的**关键数字**摘出来（便于 STATUS / 邮件直接引用）。

臂：
  * ``default`` —— **新出厂默认**：ASR=GPU.0 / MT=GPU.0 / TTS=NPU
    （APP-119 §3 验收第 1 条：必须 PASS）
  * ``allnpu``  —— **极端组合**：ASR=NPU / MT=NPU / TTS=NPU
    （APP-119 §3 验收第 2 条：只要能启动、不崩、不静默换设备；记录 RTF /
      积压 / 丢句 / NPU 编译耗时 / 进程内存）
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PKG = r'C:\Users\Trekker-PLT'    # 占位（下面用真路径）
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'
LEASE = r'C:\Users\Trekker-PTL\shared\tools\session_lease.py'
TOKEN = '3579d2f8'   # 本会话租约 token（🔴 前会话 5dda28b6 已死）

ARMS = {
    'default': ('GPU.0', 'GPU.0', 'NPU'),
    'allnpu': ('NPU', 'NPU', 'NPU'),
}


def register_pid():
    try:
        r = subprocess.run([sys.executable, LEASE, 'addpid', 'app', TOKEN,
                            str(os.getpid())], capture_output=True, text=True,
                           timeout=60)
        print('[lease] addpid rc=%s %s' % (r.returncode,
                                           (r.stdout or '').strip()), flush=True)
    except Exception as e:
        print('[lease] addpid 失败：%r' % e, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', required=True, choices=list(ARMS))
    ap.add_argument('--lang', default='zh')
    ap.add_argument('--run-id', default='')
    ap.add_argument('--note', default='')
    args = ap.parse_args()

    asr, mt, tts = ARMS[args.arm]
    run_id = args.run_id or time.strftime('%Y%m%d-%H%M%S')
    tag = 'app119_%s' % args.arm
    register_pid()
    cmd = [sys.executable, os.path.join(HERE, '_app588_sp4_acceptance.py'),
           '--pkg', PKG,
           '--asr-device', asr, '--mt-device', mt, '--tts-device', tts,
           '--lang', args.lang, '--tag', tag, '--run-id', run_id,
           '--lock-note', 'app119-%s' % args.arm]
    print('[arm:%s] %s' % (args.arm, ' '.join(cmd)), flush=True)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=HERE)
    el = time.time() - t0
    print('[arm:%s] 验收脚本 rc=%s，耗时 %.1f s' % (args.arm, p.returncode, el),
          flush=True)

    out_json = os.path.join(HERE, 'app591_acceptance_%s_run%s.json'
                            % (tag, run_id))
    if not os.path.isfile(out_json):
        print('[arm:%s] FAIL：结果 json 不存在 %s' % (args.arm, out_json))
        return 3
    with open(out_json, encoding='utf-8') as f:
        ev = json.load(f)
    tel = ev.get('telemetry') or {}
    sc = ev.get('sentence_counts') or {}
    keys = ['verdict', 'rc', 'elapsed_s', 'timing_valid', 'n_fail']
    summary = {k: ev.get(k) for k in keys}
    summary['telemetry'] = {
        k: tel.get(k) for k in (
            'n_sent', 'n_drop_total_any_reason', 'speed_p50', 'speed_p95',
            'speed_max', 'synth_rtf_p50', 'synth_rtf_p90', 'synth_rtf_max',
            'play_lag_max', 'play_lag_end', 'rtf_ewma_max')
    }
    summary['sentence_counts'] = sc
    summary['tts_ready'] = ev.get('tts_ready')
    summary['backlog_cleared_rel_s'] = ev.get('backlog_cleared_rel_s')
    summary['checks'] = [{'name': c['name'], 'pass': c['pass'],
                          'detail': c.get('detail')}
                         for c in ev.get('checks', [])]
    summary['artifacts'] = ev.get('artifacts')
    summary['lock_evidence'] = ev.get('lock_evidence')
    summary['out_json'] = out_json
    s_path = os.path.join(HERE, 'app119_%s_summary.json' % args.arm)
    tmp = s_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    os.replace(tmp, s_path)
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:4000])
    print('[arm:%s] 摘要：%s' % (args.arm, s_path))
    return p.returncode


if __name__ == '__main__':
    sys.exit(main())
