#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app250 — APP-067 ④ 的**设备级 ABBA 复测** ＋ ② 的采集器。

## 为什么（reviewer 原文，APP-067 ④）
> app233 只跑了 off / preset / clone 三个臂各一次，只有 CLI：
> - 没有 ABBA，也没有 GUI 那一次；
> - ASR RTF 增量 +0.122，超出 +0.10 的限值，需要 ABBA 复测确认；

⇒ 本脚本在**同一段「男+女混合 SPE 片段」**上按 **ABBA** 顺序跑：
`off → clone → clone → off` ＋ 一次 `preset`（当 ② 的对照组）。

## 口径纪律
* **解析口径复用 app223**（`parse_summary` / `parse_log` / `parse_jsonl`）
  ⇒ 与上一轮 +0.122 的数字**同一把尺** ⇒ 前后可比。
* **A/B 两臂必须在同一次持锁会话内连续跑**（跨会话漂移 ±5 %）⇒ 本脚本一次跑完。
* 判据**三态**：True / False / None（无法判定）⇒「无法判定」≠「不合格」。

## 额外产物（供 APP-067 ②）
* `--spk-seg-jsonl` ⇒ 逐段（seg / t0 / t1 / spk）
* `--tts-dump-dir` ⇒ 逐句 wav（`seg_<jid>_NNNN.wav`）

## 用法
```
python results/app/app250_app067_abba_device.py --run
python results/app/app250_app067_abba_device.py --dry-run
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
OUT_DIR = os.path.join(HERE, 'app250_device_out')
OUT_JSON = os.path.join(HERE, 'app250_app067_abba_device_evidence.json')


def _load_app223():
    """加载 app223 的解析层（**同一口径**，不重写正则）。"""
    p = os.path.join(HERE, 'app223_app061_device_acceptance.py')
    spec = importlib.util.spec_from_file_location('app223_mod', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arm_cmd(pkg, arm, wav, out_wav, out_jsonl, out_txt, duration,
            seg_jsonl=None, dump_dir=None):
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


def run_arm(pkg, arm, wav, duration, tag='', want_seg=False, want_dump=False):
    ensure_out_dir()
    stem = os.path.join(OUT_DIR, '%s%s' % (arm, tag))
    out_wav = stem + '.wav'
    out_jsonl = stem + '.tts.jsonl'
    out_txt = stem + '.txt'
    log_path = stem + '.log'
    seg_jsonl = (stem + '.seg.jsonl') if want_seg else None
    dump_dir = (stem + '.wavparts') if want_dump else None
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
    if seg_jsonl and os.path.isfile(seg_jsonl):
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
    for p in (out_wav, out_jsonl, out_txt, log_path, seg_jsonl):
        if p and os.path.isfile(p):
            res.setdefault('artifacts', []).append(
                dict(path=p, bytes=os.path.getsize(p),
                     mtime=time.strftime('%Y-%m-%d %H:%M:%S',
                                         time.localtime(os.path.getmtime(p)))))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pkg', default=SHADOW)
    ap.add_argument('--wav', default=MIX_WAV)
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--arms', default='tts_off,tts_on_clone,tts_on_clone,'
                                      'tts_off,tts_on_preset')
    ap.add_argument('--skip-quiet', action='store_true')
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    global ARMS, parse_summary, parse_log, parse_jsonl
    m = _load_app223()
    ARMS = m.ARMS
    parse_summary, parse_log, parse_jsonl = m.parse_summary, m.parse_log, m.parse_jsonl

    out = {'script': 'app250_app067_abba_device.py',
           'correction': 'APP-067 ④（ABBA + GUI 臂）＋ ②（采集器）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args),
           'reused_parser_from': 'app223_app061_device_acceptance.py',
           'arms_order': [a.strip() for a in args.arms.split(',') if a.strip()]}

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
    print('[lock] 已取得：%r' % (payload,))
    try:
        if not args.skip_quiet:
            ok_q, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                    timeout=900.0, verbose=True)
            out['quiet_window'] = {'ok': ok_q, 'info': str(qinfo)}
            print('[lock] 安静窗口 ok=%s' % ok_q)
            if not ok_q:
                print('[lock] !! 没有安静窗口 ⇒ 不开跑')
                out['verdict'] = 'NO_QUIET_WINDOW'
                with open(args.out, 'w', encoding='utf-8') as f:
                    json.dump(out, f, ensure_ascii=False, indent=1)
                return 4
        arms = {}
        for i, arm in enumerate(out['arms_order']):
            print('\n===== 臂 %d/%d：%s（%s）=====' %
                  (i + 1, len(out['arms_order']), arm,
                   time.strftime('%H:%M:%S')), flush=True)
            r = run_arm(args.pkg, arm, args.wav, args.duration,
                        tag='_%d' % i,
                        want_seg=(arm != 'tts_off'),
                        want_dump=(arm != 'tts_off'))
            arms['%s#%d' % (arm, i)] = r
            print('  rc=%s wall=%s s  rtf=%s  rows=%s  seg_rows=%s'
                  % (r['rc'], r['runner_wall_s'],
                     r['summary'].get('rtf'), r['jsonl'].get('n_rows'),
                     r.get('seg_rows_n')), flush=True)
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
    print('\n===== 判定 =====')
    for c in out.get('judgement', {}).get('checks', []):
        print('  [%s] %s  %s' % ({True: 'PASS', False: 'FAIL',
                                  None: 'NONE'}[c['verdict']],
                                 c['name'], json.dumps(c['detail'],
                                                      ensure_ascii=False)))
    j = out.get('judgement', {})
    print('结果：%s PASS / %s FAIL / %s NONE ⇒ %s'
          % (j.get('n_pass'), j.get('n_fail'), j.get('n_none'),
             j.get('verdict')))
    return 0


def read_jsonl_rows(path):
    """读逐句 jsonl 的原始行（**不加工**）⇒ 用于「同一批句子」的逐句比对。"""
    rows = []
    if not path or not os.path.isfile(path):
        return rows
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def judge(arms):
    """ABBA 判定（**三态**）。"""
    checks = []

    def add(name, verdict, detail, why=''):
        checks.append({'name': name, 'verdict': verdict,
                       'detail': detail, 'why': why})

    def rtf(r):
        return (r or {}).get('summary', {}).get('rtf')

    keys = list(arms.keys())
    offs = [k for k in keys if k.startswith('tts_off')]
    clones = [k for k in keys if k.startswith('tts_on_clone')]
    presets = [k for k in keys if k.startswith('tts_on_preset')]

    # ① ASR RTF 增量：**配对**（ABBA：off#0 vs clone#1、clone#2 vs off#3）
    pairs = []
    if len(offs) >= 2 and len(clones) >= 2:
        pairs = [(offs[0], clones[0]), (clones[1], offs[1])]
    elif offs and clones:
        pairs = [(offs[0], clones[0])]
    deltas = []
    for o, c in pairs:
        ro, rc = rtf(arms[o]), rtf(arms[c])
        if ro is None or rc is None:
            add('① ASR RTF 增量（%s vs %s）≤ +0.10' % (o, c), None, {},
                '缺汇总行的 RTF ⇒ 无法判定')
            continue
        d = round(rc - ro, 4)
        deltas.append({'off': o, 'clone': c, 'rtf_off': ro, 'rtf_clone': rc,
                       'delta': d})
        add('① ASR RTF 增量（%s vs %s）≤ +0.10' % (o, c), d <= 0.10,
            {'rtf_off': ro, 'rtf_clone': rc, 'delta': d, 'limit': 0.10})
    if deltas:
        mean_d = round(sum(x['delta'] for x in deltas) / len(deltas), 4)
        add('①b ABBA 平均 RTF 增量 ≤ +0.10', mean_d <= 0.10,
            {'mean_delta': mean_d, 'n_pairs': len(deltas), 'limit': 0.10})

    # ② clone 臂：voice_kind=clone 占比 ≥ 80 % + 「没有可用引擎」= 0
    for k in clones:
        r = arms[k]
        j = r.get('jsonl', {})
        lv = r.get('log', {})
        pct = j.get('pct_voice_kind_clone')
        add('② %s 的 voice_kind=clone 占比 ≥ 80 %%' % k,
            (pct is not None and pct >= 80.0),
            {'pct_voice_kind_clone': pct, 'n_rows': j.get('n_rows')})
        add('② %s 的「没有可用引擎/音色登记失败」= 0' % k,
            (lv.get('n_no_voice_error') == 0),
            {'n_no_voice_error': lv.get('n_no_voice_error')})

    # ③ clone 臂 vs preset 臂：**同一批句子**（② 的对照组前提）
    if clones and presets:
        ct = [row.get('text') for row in
              read_jsonl_rows(arms[clones[0]].get('jsonl_path'))]
        pt = [row.get('text') for row in
              read_jsonl_rows(arms[presets[0]].get('jsonl_path'))]
        if ct and pt:
            same = (ct == pt)
            n_same = sum(1 for a, b in zip(ct, pt) if a == b)
            add('③ clone 臂与 preset 臂是**同一批句子**（逐句一致）', same,
                {'n_clone_rows': len(ct), 'n_preset_rows': len(pt),
                 'n_equal_positional': n_same})
        else:
            add('③ clone 臂与 preset 臂是同一批句子', None, {},
                '某一臂没有逐句文本 ⇒ 无法判定')

    # ④ 段表：clone 臂的 seg 表有 spk 标签的段数
    for k in clones:
        r = arms[k]
        rows = r.get('seg_rows') or []
        n_lbl = sum(1 for x in rows if x.get('spk'))
        n_span = sum(1 for x in rows if x.get('t0') is not None)
        add('④ %s 的段表：%d 段有音频区间、%d 段有说话人标签'
            % (k, n_span, n_lbl),
            (n_span > 0 and n_lbl > 0),
            {'n_seg_rows': len(rows), 'n_with_span': n_span,
             'n_with_spk': n_lbl})

    n_pass = sum(1 for c in checks if c['verdict'] is True)
    n_fail = sum(1 for c in checks if c['verdict'] is False)
    n_none = sum(1 for c in checks if c['verdict'] is None)
    return {'checks': checks, 'n_pass': n_pass, 'n_fail': n_fail,
            'n_none': n_none,
            'verdict': 'PASS' if n_fail == 0 else 'FAIL',
            'rtf_deltas': deltas}


if __name__ == '__main__':
    sys.exit(main())
