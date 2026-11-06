#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app301 — APP-075(e) 的**设备级 r2 实测**：跑 clone 臂 ＋ preset 对照臂。

## 为什么另起脚本（不直接复用 app250）
* app250 是 **ABBA**（5 臂）⇒ 目的不同（RTF 增量），且它把产物写死在
  `results/app/app250_device_out/` ⇒ **会覆盖旧证据**（§135 的 ABBA 产物）
  ⇒ 🔴 本轮**另存**到 `results/app/app301_device_out/`（旧证据一字不动）。
* 本轮只跑 **2 臂**：`clone`（跟随说话人 + 开旁路）＋ `preset`（预设 A 对照）
  ⇒ 产物直接喂 APP-075(d) 的 `v23_clone_r2/`。

## 🔴 本轮与 app250 的**关键差异**（⇒ 上一轮的离线结论**不能**直接复用）
影子包已换成 **APP-075(a) 登记门槛 + ASR-050（`min_clean_ratio` 0.6）＋ 5 s 窗**
⇒ ① 登记只认「`spk_conf ≥ 0.5` ＋ 落在 `clean_ranges` 内 ＋ 挖掉切换点 ±0.5 s
＋ 连续 ≥ 2.5 s」的**最长**合格段；② 旁路标签率会变（0.8→0.6）⇒ 段数会变。
⇒ 设备级结果**可能与** `_app293/_app294/_app299`（旧包 0.8 + 10 s 窗）**不同**
⇒ 这正是必须做设备级复测的原因。

## 锁纪律（APP-064）
* 占 NPU/GPU ⇒ **先拿 `MACHINE_LOCK`**，再探安静窗口（`wait_quiet_window_cpu`）。
* 后台启动由调用方（`run_in_background: true`）负责 ⇒ 脚本自己**不**脱离父进程。

## 产物
* `results/app/app301_device_out/clone_1.*` / `preset_1.*`
* `results/app/app301_app075_r2_device_evidence.json`

## 用法
```
python results/app/_app301_app075_r2_device.py --run
```
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

SHADOW = os.path.join(HOME, 'shared', 'app067_shadow')
MIX_WAV = os.path.join(HOME, 'shared', 'app_listen', 'v23_clone',
                       'SPE_mix_3303_3603.wav')
OUT_DIR = os.path.join(HERE, 'app301_device_out')
OUT_JSON = os.path.join(HERE, 'app301_app075_r2_device_evidence.json')


def _load_app223():
    """复用 app223 的解析层（**同一口径**，与 app250 一致）。"""
    p = os.path.join(HERE, 'app223_app061_device_acceptance.py')
    spec = importlib.util.spec_from_file_location('app223_mod', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arm_cmd(pkg, arm, wav, out_wav, out_jsonl, out_txt, duration,
            seg_jsonl=None, dump_dir=None):
    """🔴 与 app250 **同一条命令构造**（只换臂名）。
    臂定义沿用 app223 的 `ARMS`（同一把尺 ⇒ 前后可比）。
    """
    tts, voice, speaker, _ = ARMS[arm]
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    cmd = [py, app,
           '--cli', '--file', wav, '--engine', 'gpu_int8',
           '--translate', 'zh',
           '--tts', tts,
           '--tts-voice', voice,
           '--speaker', speaker,
           '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
           '--tts-device', 'NPU',
           '--max-seconds', str(duration),
           '--tts-out', out_wav,
           '--tts-jsonl', out_jsonl,
           '--out', out_txt]
    if seg_jsonl:
        cmd += ['--spk-seg-jsonl', seg_jsonl]
    if dump_dir:
        cmd += ['--tts-dump-dir', dump_dir]
    return cmd


def ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)
    gi = os.path.join(OUT_DIR, '.gitignore')
    if not os.path.isfile(gi):
        with open(gi, 'w', encoding='utf-8') as f:
            f.write('*\n')


def run_arm(pkg, arm, wav, duration, tag=''):
    ensure_out_dir()
    stem = os.path.join(OUT_DIR, '%s%s' % (arm, tag))
    out_wav = stem + '.wav'
    out_jsonl = stem + '.tts.jsonl'
    out_txt = stem + '.txt'
    log_path = stem + '.log'
    seg_jsonl = stem + '.seg.jsonl'
    dump_dir = stem + '.wavparts'
    cmd = arm_cmd(pkg, arm, wav, out_wav, out_jsonl, out_txt, duration,
                  seg_jsonl, dump_dir)
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['LIVECAP_PKG'] = pkg
    t0 = time.perf_counter()
    with open(log_path, 'wb') as lf:
        proc = subprocess.run(cmd, env=env, stdout=lf,
                              stderr=subprocess.STDOUT)
    wall = time.perf_counter() - t0
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    res = {'arm': arm, 'tag': tag, 'pkg': pkg, 'cmd': cmd,
           'rc': proc.returncode, 'runner_wall_s': round(wall, 2),
           'log_path': log_path, 'log_bytes': os.path.getsize(log_path),
           'wav_path': out_wav, 'jsonl_path': out_jsonl,
           'txt_path': out_txt, 'seg_jsonl_path': seg_jsonl,
           'dump_dir': dump_dir,
           'summary': parse_summary(text), 'log': parse_log(text),
           'jsonl': parse_jsonl(out_jsonl)}
    if os.path.isfile(seg_jsonl):
        rows = []
        with open(seg_jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
        res['seg_rows'] = rows
        res['seg_rows_n'] = len(rows)
        res['seg_jsonl_bytes'] = os.path.getsize(seg_jsonl)
    n_dump = 0
    if os.path.isdir(dump_dir):
        n_dump = len([f for f in os.listdir(dump_dir)
                      if f.endswith('.wav')])
    res['n_dump_wav'] = n_dump
    return res


def judge(arms):
    """三态判定（True / False / None）。
    🔴 本轮**只**判「跑没跑通」这一层；
    **F0 闸门与余弦矩阵由 app302（离线）判**，口径分层，避免一个脚本两头背锅。
    """
    checks = []

    def add(name, verdict, detail):
        checks.append({'name': name, 'verdict': verdict, 'detail': detail})

    for k, r in arms.items():
        add('%s 跑通（rc=0）' % k, r.get('rc') == 0,
            {'rc': r.get('rc'), 'wall_s': r.get('runner_wall_s')})
        j = r.get('jsonl', {}) or {}
        add('%s 有逐句 jsonl' % k, (j.get('n_rows') or 0) > 0,
            {'n_rows': j.get('n_rows')})
        add('%s 有逐句 wav 落盘' % k, (r.get('n_dump_wav') or 0) > 0,
            {'n_dump_wav': r.get('n_dump_wav')})
        lv = r.get('log', {}) or {}
        add('%s 无「没有可用引擎/音色登记失败」' % k,
            lv.get('n_no_voice_error') == 0,
            {'n_no_voice_error': lv.get('n_no_voice_error')})

    c = arms.get('tts_on_clone')
    if c:
        rows = c.get('seg_rows') or []
        add('clone 臂有逐段标签（seg/spk/spk_conf）',
            len(rows) > 0 and all(('spk' in r and 'spk_conf' in r)
                                  for r in rows[:5]),
            {'n_rows': len(rows)})

    n_pass = sum(1 for x in checks if x['verdict'] is True)
    n_fail = sum(1 for x in checks if x['verdict'] is False)
    n_none = sum(1 for x in checks if x['verdict'] is None)
    return {'checks': checks, 'n_pass': n_pass, 'n_fail': n_fail,
            'n_none': n_none,
            'verdict': ('PASS' if n_fail == 0 and n_none == 0
                        else ('FAIL' if n_fail else 'NONE'))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pkg', default=SHADOW)
    ap.add_argument('--wav', default=MIX_WAV)
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--arms', default='tts_on_clone,tts_on_preset')
    ap.add_argument('--skip-quiet', action='store_true')
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    global ARMS, parse_summary, parse_log, parse_jsonl
    m = _load_app223()
    ARMS = m.ARMS
    parse_summary, parse_log, parse_jsonl = (m.parse_summary, m.parse_log,
                                             m.parse_jsonl)

    out = {'script': '_app301_app075_r2_device.py',
           'correction': 'APP-075(e) 设备级 r2（clone 臂 + preset 对照）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args),
           'reused_parser_from': 'app223_app061_device_acceptance.py',
           'arms_order': [a.strip() for a in args.arms.split(',') if a.strip()],
           'note': ('本轮影子包 = APP-075(a) 登记门槛 + ASR-050(0.6) + 5 s 窗'
                    ' ⇒ 与 app250（0.8 + 10 s 窗）**不可直接比**')}

    if not os.path.isfile(args.wav):
        print('!! 找不到音频：%s' % args.wav)
        return 2

    if args.dry_run:
        for arm in out['arms_order']:
            print(' '.join(arm_cmd(args.pkg, arm, args.wav, 'X.wav', 'X.jsonl',
                                   'X.txt', args.duration, 'X.seg.jsonl',
                                   'X.parts')))
        print('（--dry-run：没有跑设备作业）')
        return 0
    if not args.run:
        print('（未加 --run ⇒ 不跑设备作业）')
        return 0

    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未取得机器锁 ⇒ 退出')
        out['verdict'] = 'LOCK_BUSY'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3
    print('[lock] 已取得：%r' % (payload,), flush=True)
    try:
        if not args.skip_quiet:
            ok_q, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                    timeout=900.0, verbose=True)
            out['quiet_window'] = {'ok': ok_q, 'info': str(qinfo)}
            print('[lock] 安静窗口 ok=%s' % ok_q, flush=True)
            if not ok_q:
                out['verdict'] = 'NO_QUIET_WINDOW'
                with open(args.out, 'w', encoding='utf-8') as f:
                    json.dump(out, f, ensure_ascii=False, indent=1)
                return 4
        arms = {}
        for i, arm in enumerate(out['arms_order']):
            print('\n===== 臂 %d/%d：%s（%s）====='
                  % (i + 1, len(out['arms_order']), arm,
                     time.strftime('%H:%M:%S')), flush=True)
            r = run_arm(args.pkg, arm, args.wav, args.duration, tag='_%d' % i)
            arms['%s#%d' % (arm, i)] = r
            print('  rc=%s wall=%s s rows=%s seg_rows=%s dump_wav=%s'
                  % (r['rc'], r['runner_wall_s'],
                     r['jsonl'].get('n_rows'), r.get('seg_rows_n'),
                     r.get('n_dump_wav')), flush=True)
        out['arms'] = arms
        out['judgement'] = judge(arms)
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % (e,))
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[evidence] %s' % args.out)
    j = out.get('judgement', {})
    print('\n===== 判定 =====')
    for c in j.get('checks', []):
        print('  [%s] %s  %s' % ({True: 'PASS', False: 'FAIL',
                                  None: 'NONE'}[c['verdict']],
                                 c['name'], json.dumps(c['detail'],
                                                      ensure_ascii=False)))
    print('结果：%s PASS / %s FAIL / %s NONE ⇒ %s'
          % (j.get('n_pass'), j.get('n_fail'), j.get('n_none'),
             j.get('verdict')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
