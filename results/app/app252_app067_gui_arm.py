#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app252 — APP-067 ④ 的**设备级 GUI 臂**（reviewer：app233「只有 CLI」）。

> 没有 ABBA，也没有 GUI 那一次；

## 本脚本做什么
1. 用**影子包**启动**真 GUI**（加载 ASR/MT/TTS 模型 ⇒ **占 GPU/NPU**）
   —— 回放「男+女混合 SPE 片段」，`--speaker on` + `--tts-voice follow_speaker`；
2. 运行中用 **Win32 `PrintWindow`** 抓 GUI 窗口（🔴 `PIL.ImageGrab` 本机全黑
   ⇒ 不用它），并做**像素级守卫**（不是黑图才算数）；
3. 收 GUI 自测产物（`<engine_key>_gui.txt`）＋ 逐句 jsonl ＋ 会话日志；
4. 判定：clone 占比 / 「没有可用引擎」/ 说话人标签 / RTF 等。

## 纪律
* 🔴 **占设备 ⇒ 必须持 `MACHINE_LOCK`**（本脚本自己拿、自己放，fail-closed）。
* 抓屏用 `results/app/win_capture.py`（**三级降级 + 黑图守卫**）。

## 用法
```
python results/app/app252_app067_gui_arm.py --run
```
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

SHADOW = os.path.join(HOME, 'shared', 'app067_shadow')
MIX_WAV = os.path.join(HOME, 'shared', 'app_listen', 'v23_clone',
                       'SPE_mix_3303_3603.wav')
OUT_DIR = os.path.join(HERE, 'app252_gui_out')
OUT_JSON = os.path.join(HERE, 'app252_app067_gui_arm_evidence.json')
TITLE_KEY = '实时字幕'

user32 = ctypes.windll.user32


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_hwnds():
    """枚举**可见**窗口（标题含关键字）⇒ [(hwnd, title)]。"""
    out = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if TITLE_KEY in buf.value:
            out.append((int(hwnd), buf.value))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def grab(path):
    """抓 GUI 窗口（**黑图守卫**）。"""
    try:
        sys.path.insert(0, os.path.join(HERE))
        wc = _load('win_capture_mod', os.path.join(HERE, 'win_capture.py'))
        hs = find_hwnds()
        if not hs:
            return {'ok': False, 'why': '没找到 GUI 窗口（标题含 %s）' % TITLE_KEY}
        hwnd = hs[-1][0]
        ok = wc.capture_hwnd(hwnd, path)
        info = {'ok': bool(ok), 'hwnd': hwnd, 'titles': [t for _, t in hs]}
        if ok and os.path.isfile(path):
            info['bytes'] = os.path.getsize(path)
            try:
                from PIL import Image
                im = Image.open(path).convert('RGB')
                ex = im.getextrema()
                info['extrema'] = [list(e) for e in ex]
                info['all_black'] = all(e[0] == 0 and e[1] == 0 for e in ex)
            except Exception as e:
                info['pixel_check_error'] = repr(e)
        return info
    except Exception as e:
        return {'ok': False, 'why': repr(e)}


def newest_session_log(after_ts):
    d = os.path.join(os.environ.get('LOCALAPPDATA') or HOME,
                     'Confucius4LiveCaption')
    cands = []
    if os.path.isdir(d):
        for fn in os.listdir(d):
            if fn.startswith('session_') and fn.endswith('.log'):
                p = os.path.join(d, fn)
                if os.path.getmtime(p) >= after_ts - 5:
                    cands.append(p)
    cands.sort(key=lambda p: os.path.getmtime(p))
    return cands[-1] if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pkg', default=SHADOW)
    ap.add_argument('--wav', default=MIX_WAV)
    ap.add_argument('--seconds', type=float, default=300.0,
                    help='GUI 回放多少秒后自测退出')
    ap.add_argument('--shots', default='45,150,260',
                    help='抓屏时刻（秒，逗号分隔）')
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    out = {'script': 'app252_app067_gui_arm.py',
           'correction': 'APP-067 ④（GUI 臂）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args), 'checks': []}

    def add(name, verdict, detail, why=''):
        out['checks'].append({'name': name, 'verdict': verdict,
                              'detail': detail, 'why': why})
        print('  [%s] %s%s' % ({True: 'PASS', False: 'FAIL',
                                None: 'NONE'}[verdict], name,
                               ('  ' + json.dumps(detail, ensure_ascii=False))
                               if detail else ''))

    os.makedirs(OUT_DIR, exist_ok=True)
    py = os.path.join(args.pkg, 'python', 'python.exe')
    app = os.path.join(args.pkg, 'app', 'live_caption_app.py')
    selftest_out = os.path.join(OUT_DIR, 'selftest')
    jsonl = os.path.join(OUT_DIR, 'gui.tts.jsonl')
    log_path = os.path.join(OUT_DIR, 'gui.log')
    cmd = [py, app,
           '--source', 'file', '--file', args.wav,
           '--autostart', '--selftest', str(args.seconds),
           '--selftest-out', selftest_out,
           '--tts', 'on', '--tts-voice', 'follow_speaker',
           '--speaker', 'on',
           '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
           '--tts-device', 'NPU', '--translate', 'zh',
           '--tts-jsonl', jsonl]
    out['cmd'] = cmd
    print('命令：\n  %s' % ' '.join(cmd))

    if args.dry_run:
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
    t_start = time.time()
    shots = sorted({float(x) for x in args.shots.split(',') if x.strip()})
    shot_info = {}
    try:
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        env['LIVECAP_PKG'] = args.pkg
        with open(log_path, 'wb') as lf:
            proc = subprocess.Popen(cmd, env=env, stdout=lf,
                                    stderr=subprocess.STDOUT)
        out['gui_pid'] = proc.pid
        print('[gui] pid=%s 已启动' % proc.pid, flush=True)
        t0 = time.time()
        shot_i = 0
        while proc.poll() is None:
            time.sleep(2.0)
            el = time.time() - t0
            if shot_i < len(shots) and el >= shots[shot_i]:
                p = os.path.join(OUT_DIR, 'gui_shot_%03ds.png'
                                 % int(shots[shot_i]))
                info = grab(p)
                info['at_s'] = round(el, 1)
                shot_info['%03d' % int(shots[shot_i])] = info
                print('[shot] t=%.0fs ⇒ %s' % (el, json.dumps(info,
                                                              ensure_ascii=False)),
                      flush=True)
                shot_i += 1
            if el > args.seconds + 180:
                print('[gui] 超时 ⇒ 强制结束')
                proc.terminate()
                break
        out['rc'] = proc.poll()
        out['gui_wall_s'] = round(time.time() - t0, 1)
        out['shots'] = shot_info
        # 收 GUI 自测产物
        if os.path.isdir(selftest_out):
            out['selftest_files'] = sorted(os.listdir(selftest_out))
            for fn in out['selftest_files']:
                if fn.endswith('.txt'):
                    with open(os.path.join(selftest_out, fn), 'r',
                              encoding='utf-8', errors='replace') as f:
                        out['selftest_txt'] = f.read()[:4000]
        sl = newest_session_log(t_start)
        out['session_log'] = sl
        if sl:
            with open(sl, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            out['session_log_bytes'] = len(text.encode('utf-8', 'replace'))
            out['session_log_head'] = text[:1500]
            n_no_voice = len(re.findall(
                r'没有可用的音色|没有可用引擎|spk 音色登记失败', text))
            n_new_spk = len(re.findall(r'new_spk', text))
            n_label = len(re.findall(r'标签补到', text))
            n_reg = len(re.findall(r'音色已登记|说话人音色登记', text))
            n_fallback = len(re.findall(r'已回落到预设 A', text))
            n_keep = len(re.findall(r'spk_pending⇒keep_last', text))
            out['log_counts'] = {'n_no_voice_error': n_no_voice,
                                 'n_new_spk': n_new_spk, 'n_label': n_label,
                                 'n_voice_registered': n_reg,
                                 'n_fallback_preset': n_fallback,
                                 'n_keep_last': n_keep}
        # 逐句 jsonl ⇒ voice_kind 占比
        if os.path.isfile(jsonl):
            rows = []
            with open(jsonl, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            pass
            okr = [r for r in rows if not r.get('dropped')]
            kinds = {}
            for r in okr:
                k = r.get('voice_kind') or 'unknown'
                kinds[k] = kinds.get(k, 0) + 1
            out['jsonl'] = {'path': jsonl, 'n_rows': len(rows),
                            'n_ok': len(okr), 'voice_kind_counts': kinds,
                            'pct_voice_kind_clone': (
                                round(100.0 * kinds.get('clone', 0) / len(okr), 3)
                                if okr else None),
                            'voice_spk_ids': sorted(
                                {str(r.get('voice_spk')) for r in okr
                                 if r.get('voice_spk')})}
        # ── 判定 ────────────────────────────────────────────────
        j = out.get('jsonl', {})
        pct = j.get('pct_voice_kind_clone')
        add('GUI 臂的 voice_kind=clone 占比 ≥ 80 %',
            (pct is not None and pct >= 80.0),
            {'pct_voice_kind_clone': pct, 'n_rows': j.get('n_rows')})
        lc = out.get('log_counts', {})
        add('GUI 臂的「没有可用引擎/音色登记失败」= 0',
            (lc.get('n_no_voice_error') == 0 if lc else None),
            lc or {})
        add('GUI 臂有说话人标签', (lc.get('n_label', 0) > 0 if lc else None),
            {'n_label': lc.get('n_label') if lc else None})
        ok_shots = [k for k, v in shot_info.items()
                    if v.get('ok') and not v.get('all_black')]
        add('抓到**非黑图**的 GUI 截图', len(ok_shots) > 0,
            {'shots': {k: {'ok': v.get('ok'),
                           'all_black': v.get('all_black')}
                       for k, v in shot_info.items()}})
        add('GUI 臂跑完了（有自测产物或逐句 jsonl）',
            bool(out.get('selftest_files') or j.get('n_rows')),
            {'selftest_files': out.get('selftest_files'),
             'n_rows': j.get('n_rows')})
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % (e,))
    n_pass = sum(1 for c in out['checks'] if c['verdict'] is True)
    n_fail = sum(1 for c in out['checks'] if c['verdict'] is False)
    n_none = sum(1 for c in out['checks'] if c['verdict'] is None)
    out['n_pass'], out['n_fail'], out['n_none'] = n_pass, n_fail, n_none
    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\n结果：%d PASS / %d FAIL / %d NONE ⇒ %s'
          % (n_pass, n_fail, n_none, out['verdict']))
    print('[evidence] %s' % args.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
