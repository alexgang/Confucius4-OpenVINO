#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app333_app097_regress.py —— **APP-097 §2-5 回归**。

## reviewer §2-5 原文
> **回归**：
> * zh 目标在 dialog3 上跑一次正常速度，跳过句数、字幕行数、合成 RTF 要和扩表前一致
>   （给出 before/after 两份 json）。
> * ja/ko 各 5 句冒烟。

## 关键设计（🔴 为什么「扩表前 / 扩表后」能严格对照）

* 影子包 `after2_pre` = **扩表前**代码（`SUPPORTED_LANGS` 只有 4 种）
* 影子包 `after2`     = **扩表后**代码（10 种）
* 两者 `models/` 是**同一个物理目录**（realpath 相同）⇒ **模型完全相同**
  ⇒ 差异只可能来自**代码**（语言表）⇒ 对照干净。

## 跑什么
1. **zh 回归**：两个影子包各跑一次 `dialog3.wav`（目标 zh、正常速度 1.0×），
   命令行与既有 runs2/runs3 **同口径**（ASR iGPU / MT iGPU / TTS NPU f16），
   比较：**跳过句数**（`late_drop`）、**字幕行数**、**合成 RTF p50/p95**。
2. **ja/ko 冒烟**：在 **after2**（扩表后）上各 5 句，
   走**真实 TTS 代码路径**（`map_language` → `split_long_text` →
   `clamp_max_new_tokens` → `estimate_sec` → `stream`）。

## 🔴 为什么 ja/ko 用 TTS 直跑而不是整场 App 跑
reviewer 只要求「各 5 句冒烟」⇒ 用 §2-3 已验证过的 `_app326_tts_runner.py`
（**同一套参数链**）⇒ 复用它、不引入新口径。

## 锁
本脚本是**设备跑**（NPU/iGPU）⇒ **必须持 MACHINE_LOCK** ⇒ 锁记录写进 json。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics as st
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
BASE = os.path.join(HOME, '_app_shadow')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
OUTROOT = os.path.join(HERE, 'app333_app097_regress')
REPORT = os.path.join(HERE, 'app333_app097_regress.json')
TTS_RUNNER = os.path.join(HERE, '_app326_tts_runner.py')


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def acquire_lock(tag):
    for _ in range(180):
        if not os.path.exists(LOCK):
            payload = ('module=app\npid=%d\nstart=%s\ntag=%s\n'
                       % (os.getpid(), now(), tag))
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(payload)
                return payload
            except FileExistsError:
                pass
        time.sleep(10)
    return None


def release_lock():
    try:
        if os.path.exists(LOCK):
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                if ('pid=%d' % os.getpid()) in f.read():
                    gone = os.path.join(
                        os.path.dirname(LOCK),
                        '.MACHINE_LOCK.released_%d_%d' % (os.getpid(), int(time.time())))
                    os.replace(LOCK, gone)
                    return not os.path.exists(LOCK)
    except OSError:
        pass
    return False


def build_cmd(root, out, wav, tgt='zh'):
    """🔴 与既有 runs2/runs3 **同口径**（ASR iGPU / MT iGPU / TTS NPU f16 / 克隆跟随说话人）。"""
    return [
        os.path.join(root, 'python', 'python.exe'),
        os.path.join(root, 'app', 'live_caption_app.py'),
        '--cli', '--file', wav,
        '--speaker', 'on', '--tts', 'on', '--tts-voice', 'follow_speaker',
        '--tts-precision', 'f16', '--tts-device', 'NPU',
        '--translate', tgt, '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--out', os.path.join(out, 'subtitles.txt'),
        '--tts-out', os.path.join(out, 'mix.wav'),
        '--tts-jsonl', os.path.join(out, 'tts.jsonl'),
        '--tts-dump-dir', os.path.join(out, 'dump'),
        '--spk-seg-jsonl', os.path.join(out, 'spk_seg.jsonl'),
    ]


def read_jsonl(p):
    rows = []
    if not os.path.exists(p):
        return rows
    with open(p, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    return round(s[int(q * (len(s) - 1))], 4)


def run_zh_arm(arm, root, out, wav):
    """跑一次 zh 目标正常速度 ⇒ 返回该臂的统计。"""
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    clone_dir = os.path.join(out, 'clone_voices')
    os.makedirs(clone_dir, exist_ok=True)
    env = dict(os.environ)
    env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir
    cmd = build_cmd(root, out, wav)
    log = os.path.join(out, 'run.log')
    print('▶ zh 回归 %s' % arm, flush=True)
    t0 = time.perf_counter()
    with open(log, 'w', encoding='utf-8', errors='replace') as lf:
        lf.write('# cmd=%s\n# started=%s\n' % (json.dumps(cmd), now()))
        lf.flush()
        # 🔴 stdout → 文件（不是 pipe）⇒ 不会管道死锁
        rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT,
                             env=env, cwd=root)
    wall = round(time.perf_counter() - t0, 1)

    rows = read_jsonl(os.path.join(out, 'tts.jsonl'))
    segs = read_jsonl(os.path.join(out, 'spk_seg.jsonl'))
    rtfs = [r['synth_rtf'] for r in rows
            if isinstance(r.get('synth_rtf'), (int, float))]
    n_late = sum(1 for r in rows if r.get('late_drop'))
    n_dropped = sum(1 for r in rows if r.get('dropped'))
    sub_path = os.path.join(out, 'subtitles.txt')
    n_sub = 0
    if os.path.exists(sub_path):
        with open(sub_path, encoding='utf-8', errors='replace') as f:
            n_sub = sum(1 for line in f if line.strip())
    asr_rtf = None
    try:
        txt = open(log, encoding='utf-8', errors='replace').read()
        for tok in ('RTF(计算)', 'RTF'):
            i = txt.rfind(tok)
            if i >= 0:
                seg = txt[i:i + 120]
                import re
                m = re.search(r'(\d+\.\d+)', seg)
                if m:
                    asr_rtf = float(m.group(1))
                    break
    except OSError:
        pass
    return {
        'arm': arm, 'root': root, 'out': out, 'rc': rc, 'wall_s': wall,
        'log': log, 'tts_jsonl': os.path.join(out, 'tts.jsonl'),
        'n_tts_rows': len(rows),
        'n_segments': len(segs),
        'n_subtitle_lines': n_sub,
        'n_late_drop': n_late,
        'n_dropped': n_dropped,
        'n_error': sum(1 for r in rows if r.get('error')),
        'synth_rtf_p50': pct(rtfs, 0.50),
        'synth_rtf_p95': pct(rtfs, 0.95),
        'synth_rtf_mean': round(st.mean(rtfs), 4) if rtfs else None,
        'asr_rtf_from_log': asr_rtf,
        'cmd': cmd,
        'log_tail': open(log, encoding='utf-8', errors='replace').read()[-1800:]
        if os.path.exists(log) else '',
    }


def run_smoke(lang, root, out, n_sent=5):
    """ja/ko 各 5 句冒烟（走 §2-3 同一套 TTS 参数链）。"""
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    py = os.path.join(root, 'python', 'python.exe')
    app = os.path.join(root, 'app')
    mt_path = os.path.join(HERE, 'app333_smoke_%s_mt.json' % lang)
    # 造一份最小 mt.json：英文源句 → 目标语种（用真实 MT 引擎翻）
    mt_runner = os.path.join(HERE, '_app326_mt_runner.py')
    mt_out = os.path.join(out, 'mt.json')
    mt_log = os.path.join(out, 'mt.log')
    # 🔴 `_app326_mt_runner.py` 的签名是 `--en <json> --zh <json> --langs <csv>`
    #    （源句列表以 **JSON 字符串**传入）
    en_sents = json.load(open(os.path.join(HERE, 'app333_en_sents.json'),
                              encoding='utf-8'))[:n_sent]
    zh_sents = json.load(open(os.path.join(HERE, 'app333_zh_sents.json'),
                              encoding='utf-8'))[:n_sent]
    cmd_mt = [py, mt_runner, '--app', app, '--out', mt_out,
              '--en', json.dumps(en_sents, ensure_ascii=False),
              '--zh', json.dumps(zh_sents, ensure_ascii=False),
              '--langs', lang]
    with open(mt_log, 'w', encoding='utf-8', errors='replace') as lf:
        rc_mt = subprocess.call(cmd_mt, stdout=lf, stderr=subprocess.STDOUT)
    cmd_tts = [py, TTS_RUNNER, '--app', app, '--out',
               os.path.join(out, 'tts.json'), '--mt', mt_out,
               '--langs', lang,
               '--wav-dir', os.path.join(out, 'wav'),
               '--clone-ref', os.path.join(SPKTEST, 'dialog3_tight.wav')]
    tts_log = os.path.join(out, 'tts.log')
    with open(tts_log, 'w', encoding='utf-8', errors='replace') as lf:
        rc_tts = subprocess.call(cmd_tts, stdout=lf, stderr=subprocess.STDOUT)
    tts_json = os.path.join(out, 'tts.json')
    res = {}
    if os.path.exists(tts_json):
        try:
            res = json.load(open(tts_json, encoding='utf-8'))
        except ValueError:
            pass
    per = (res.get('per_lang') or {}).get(lang) or {}
    rows = per.get('preset', {}).get('rows') or []
    rtfs = [r['synth_rtf'] for r in rows
            if isinstance(r.get('synth_rtf'), (int, float))]
    return {
        'lang': lang, 'rc_mt': rc_mt, 'rc_tts': rc_tts,
        'out': out, 'tts_json': tts_json if os.path.exists(tts_json) else None,
        'mt_json': mt_out if os.path.exists(mt_out) else None,
        'n_rows': len(rows),
        'n_empty': sum(1 for r in rows if not r.get('out_dur_s')),
        'rtf_p50': pct(rtfs, 0.50),
        'rtf_p95': pct(rtfs, 0.95),
        'end_reason_dist': per.get('preset', {}).get('end_reason_dist'),
        'exec_devices': res.get('exec_devices'),
        'log_tail': open(tts_log, encoding='utf-8', errors='replace').read()[-1500:]
        if os.path.exists(tts_log) else '',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-zh', action='store_true')
    args = ap.parse_args()

    ev = {
        'created_at': now(),
        'correction': 'APP-097 §2-5 回归（zh before/after + ja/ko 冒烟）',
        'criterion': ('zh 目标在 dialog3 上跑正常速度，扩表前后的'
                      '「跳过句数 / 字幕行数 / 合成 RTF」一致；ja/ko 各 5 句冒烟'),
        'device_job': True,
        'method': ('两个影子包各跑一次（`after2_pre`＝扩表前 / `after2`＝扩表后）；'
                   '两者 models/ 是**同一物理目录** ⇒ 模型相同 ⇒ 差异只来自代码'),
        'outroot': OUTROOT,
    }

    lock = acquire_lock('app097-regress')
    if lock is None:
        ev['verdict'] = 'BLOCKED_LOCK'
        _dump(ev)
        print('!! 拿不到锁')
        return 2
    ev['lock_record'] = {
        'module': 'app', 'pid': os.getpid(), 'start': now(),
        'tag': 'app097-regress', 'file': LOCK, 'content': lock.strip(),
    }
    print('[lock] 已持有', flush=True)

    try:
        wav = os.path.join(SPKTEST, 'dialog3.wav')
        roots = {'before': os.path.join(BASE, 'after2_pre'),
                 'after': os.path.join(BASE, 'after2')}
        ev['roots'] = {k: {'path': v,
                           'models_realpath': os.path.realpath(
                               os.path.join(v, 'models'))}
                       for k, v in roots.items()}
        ev['roots']['same_models_dir'] = (
            ev['roots']['before']['models_realpath'].lower()
            == ev['roots']['after']['models_realpath'].lower())
        ev['lang_table'] = {}
        for k, v in roots.items():
            te = os.path.join(v, 'app', 'tts_engine.py')
            ev['lang_table'][k] = {
                'file': te, 'sha256': sha(te),
                'supported_langs_line': next(
                    (ln.strip() for ln in open(te, encoding='utf-8',
                                               errors='replace')
                     if ln.startswith('SUPPORTED_LANGS')), None),
            }

        ev['zh_regress'] = {}
        if not args.skip_zh:
            for arm in ('before', 'after'):
                out = os.path.join(OUTROOT, 'zh_%s' % arm)
                ev['zh_regress'][arm] = run_zh_arm(arm, roots[arm], out, wav)
                with open(LOCK, encoding='utf-8', errors='replace') as f:
                    if ('pid=%d' % os.getpid()) not in f.read():
                        ev['verdict'] = 'LOCK_LOST'
                        _dump(ev)
                        print('!! 锁已丢失', flush=True)
                        return 3

        # ── zh before/after 对照判定 ──
        if ev['zh_regress']:
            b = ev['zh_regress']['before']
            a = ev['zh_regress']['after']
            ev['zh_compare'] = {
                'metric_rows': [
                    {'metric': 'n_late_drop', 'before': b['n_late_drop'],
                     'after': a['n_late_drop']},
                    {'metric': 'n_dropped', 'before': b['n_dropped'],
                     'after': a['n_dropped']},
                    {'metric': 'n_tts_rows', 'before': b['n_tts_rows'],
                     'after': a['n_tts_rows']},
                    {'metric': 'n_segments', 'before': b['n_segments'],
                     'after': a['n_segments']},
                    {'metric': 'n_subtitle_lines', 'before': b['n_subtitle_lines'],
                     'after': a['n_subtitle_lines']},
                    {'metric': 'synth_rtf_p50', 'before': b['synth_rtf_p50'],
                     'after': a['synth_rtf_p50']},
                    {'metric': 'synth_rtf_p95', 'before': b['synth_rtf_p95'],
                     'after': a['synth_rtf_p95']},
                    {'metric': 'asr_rtf_from_log', 'before': b['asr_rtf_from_log'],
                     'after': a['asr_rtf_from_log']},
                ],
                'same_late_drop': b['n_late_drop'] == a['n_late_drop'],
                'same_subtitle_lines': (b['n_subtitle_lines']
                                        == a['n_subtitle_lines']),
                'same_segments': b['n_segments'] == a['n_segments'],
                'rtf_delta_p50': (round(a['synth_rtf_p50'] - b['synth_rtf_p50'], 4)
                                  if b['synth_rtf_p50'] is not None
                                  and a['synth_rtf_p50'] is not None else None),
                'note': ('🔴 RTF 允许小幅漂移（同一机器不同会话 ±5 %）；'
                         '「跳过句数 / 字幕行数 / 段数」必须**逐项一致**'),
            }

        # ── ja / ko 冒烟 ──
        ev['smoke'] = {}
        for lang in ('ja', 'ko'):
            out = os.path.join(OUTROOT, 'smoke_%s' % lang)
            ev['smoke'][lang] = run_smoke(lang, roots['after'], out, n_sent=5)

        ev['verdict'] = 'RAN'
    finally:
        ev['lock_released'] = release_lock()
        ev['lock_exists_after'] = os.path.exists(LOCK)
        print('[lock] 释放=%s 残留=%s' % (ev['lock_released'],
                                        ev['lock_exists_after']), flush=True)
    _dump(ev)
    return 0


def _dump(ev):
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT, flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
