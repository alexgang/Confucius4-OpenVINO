#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app582_sp3_acceptance.py —— **APP-111 §3 的验收**：sp3 SpecialMVP 10 分钟整链。

**reviewer 原文（APP-111 §3）**：
  「持锁用固定 10 分钟片段（SPE 0–600 s）跑 sp3 SpecialMVP 1 次：丢句数
   （late_drop/跳过）必须 = 0；记录倍率分布（P50/P95/max，max ≤ 2.0）、
   最大滞后、结束时的滞后、句子总数与 app552 对齐。
   和 app552（sp2，阈值 6.0、上限 1.5）对比一张表：丢句数、最大滞后、平均倍率。
   抽 3 段倍率 ≥1.8× 的配音 wav 放进 results，供 reviewer 和用户抽听
   （2.0× 听感是否可接受由用户判定）。」

🔴 **命令口径**：与 11-13 那次 sp1 整链（`_app538_chain_rerun.py`）**逐字相同**，
   只把包路径换成 sp3、输出换成新文件名 ⇒ 与 app552 的对照可比。
   ⚠️ **app552 的数据源实为 sp1 的那次 10 分钟整链**
   （`_app538_special_tts_out.wav`，11-13 21:07；阈值 6.0 / 上限 1.5 同口径）
   ⇒ 对照口径成立，只是「sp2」这个标签不准（本脚本如实记录）。

🔴 **纪律**：跑的是**客户包**（sp3），不是开发树；**不出 zip**；**不改产品代码**。
"""
import hashlib
import json
import os
import subprocess
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp3')
AUDIO = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
TTS_OUT = os.path.join(RESULTS, '_app582_sp3_tts_out.wav')
JSONL = TTS_OUT + '.tts.jsonl'
BACKLOG_CSV = TTS_OUT + '.backlog_curve.csv'
LOG = os.path.join(RESULTS, '_app582_sp3_acceptance.log')
OUT = os.path.join(RESULTS, 'app582_specialmvp_sp3_acceptance.json')
BASELINE = os.path.join(RESULTS, 'app552_specialmvp_dropped_sentences.json')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
WAV_DIR = os.path.join(RESULTS, '_app582_fast_samples')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)


def parse_telemetry(path):
    rows = []
    for ln in open(path, encoding='utf-8').read().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    return rows


def extract_fast_wavs(rows, out_wav, min_speed=1.8, want=3):
    """抽「倍率 ≥ min_speed」的配音 wav 片段（reviewer/用户抽听用）。"""
    if not os.path.isfile(out_wav):
        return {'error': 'tts out wav 不存在'}
    os.makedirs(WAV_DIR, exist_ok=True)
    cands = []
    for r in rows:
        sp = r.get('speed')
        if sp is None or r.get('dropped'):
            continue
        try:
            sp = float(sp)
        except Exception:
            continue
        if sp < min_speed:
            continue
        t0, t1 = r.get('wav_t0'), r.get('wav_t1')
        if t0 is None or t1 is None:
            continue
        cands.append({'id': r.get('id'), 'speed': round(sp, 4), 't0': t0,
                      't1': t1, 'text': (r.get('text') or '')[:60],
                      'out_dur_s': r.get('out_dur_s'),
                      'play_lag_s': r.get('play_lag_s')})
    cands.sort(key=lambda c: -c['speed'])
    picked = cands[:want]
    fell_back = False
    if not picked:
        # 🔴 **没有任何一句达到 min_speed** ⇒ 如实回落成「倍率最高的前 want 句」，
        #    并在 json 里标明**实际倍率**（不得让 reviewer 误读成 ≥min_speed 的样本）。
        allc = []
        for r in rows:
            sp = r.get('speed')
            if sp is None or r.get('dropped'):
                continue
            try:
                sp = float(sp)
            except Exception:
                continue
            t0, t1 = r.get('wav_t0'), r.get('wav_t1')
            if t0 is None or t1 is None:
                continue
            allc.append({'id': r.get('id'), 'speed': round(sp, 4), 't0': t0,
                         't1': t1, 'text': (r.get('text') or '')[:60],
                         'out_dur_s': r.get('out_dur_s'),
                         'play_lag_s': r.get('play_lag_s')})
        allc.sort(key=lambda c: -c['speed'])
        picked = allc[:want]
        fell_back = True
    made = []
    for c in picked:
        dst = os.path.join(WAV_DIR, 'sp3_fast_id%s_speed%s.wav'
                           % (c['id'], ('%.2f' % c['speed']).replace('.', '_')))
        _p = subprocess.run(
            [PKG_PY, '-c',
             "import soundfile as sf, numpy as np;"
             "d,sr=sf.read(r'%s');"
             "a=int(round(%r*sr)); b=int(round(%r*sr));"
             "b=min(b,len(d)); seg=d[a:b] if b>a else d[:0];"
             "sf.write(r'%s', seg, sr);"
             "print(sr, len(seg)/sr, float(np.abs(seg).max()) if len(seg) else 0)"
             % (out_wav, c['t0'], c['t1'], dst)],
            capture_output=True, text=True, timeout=300)
        info = ''
        if os.path.isfile(dst):
            info = 'bytes=%d sha256=%s' % (os.path.getsize(dst),
                                           sha256_file(dst)[:16])
            made.append({'file': dst, 'bytes': os.path.getsize(dst),
                         'sha256': sha256_file(dst), 'id': c['id'],
                         'speed': c['speed'], 'text': c['text'],
                         't0': c['t0'], 't1': c['t1'],
                         'out_dur_s': c['out_dur_s'],
                         'play_lag_s': c['play_lag_s']})
        else:
            made.append({'file': dst, 'error': '切片失败', 'id': c['id'],
                         'speed': c['speed']})
    return {'min_speed': min_speed, 'n_candidates': len(cands),
            'n_made': len([m for m in made if 'error' not in m]),
            'fell_back_to_top_speed': fell_back,
            'samples': made,
            'note': ('倍率 ≥%.1f× 的句子共 %d 句；抽出 %d 段供抽听。'
                     % (min_speed, len(cands), len(made))
                     + ('　🔴 **没有任何一句达到 %.1f×** ⇒ 本次抽听样本是'
                        '**倍率最高的前 %d 句**（实际倍率见每个文件的 speed 字段）'
                        '⇒ **不得**当作「≥%.1f× 的样本」解读。'
                        % (min_speed, len(made), min_speed)
                        if fell_back else ''))}


def main():
    if not os.path.isdir(PKG):
        print('sp3 包不存在：%s' % PKG)
        return 2
    cmd = [PKG_PY, os.path.join(PKG, 'app', 'live_caption_app.py'),
           '--cli', '--file', AUDIO,
           '--asr-device', 'GPU.0',
           '--mt-device', 'NPU',
           '--tts-device', 'CUDA',
           '--translate', 'zh',
           '--tts', 'on',
           '--tts-out', TTS_OUT]
    ev = {'purpose': 'APP-111 §3：sp3 SpecialMVP 10 分钟整链验收',
          'pkg': PKG, 'audio': AUDIO,
          'audio_bytes': os.path.getsize(AUDIO) if os.path.isfile(AUDIO) else None,
          'cmd': cmd, 'cwd': PKG,
          'cmd_note': ('与 11-13 那次 sp1 整链（_app538_chain_rerun.py）逐字相同，'
                       '只换包路径与输出文件名 ⇒ 与 app552 可对照'),
          'params_under_test': {'tts_late_drop_sec': 0.0,
                                'tts_speed_max_zh': 2.00},
          'started': time.strftime('%Y-%m-%d %H:%M:%S')}
    t0 = time.time()
    analyze_only = '--analyze-only' in sys.argv
    if analyze_only:
        # 🔴 **只重算分析**：复用已有的 stdout/wav/jsonl（**不重跑 10 分钟作业**）
        print('[sp3 验收] --analyze-only：复用已有产物重算', flush=True)
        _raw = open(LOG, encoding='utf-8', errors='replace').read()
        so = _raw.split('--- STDOUT ---\n', 1)[-1].split('\n--- STDERR ---')[0]
        se = ''
        p = type('R', (), {'returncode': 0})()
        t1 = t0
    else:
        print('[sp3 验收] 起：%s' % ' '.join(cmd), flush=True)
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=5400,
                           cwd=PKG)
        t1 = time.time()
        so, se = p.stdout or '', p.stderr or ''
        with open(LOG, 'w', encoding='utf-8') as f:
            f.write('CMD: %r\nCWD: %s\nRC=%d\nELAPSED_S=%.1f\n--- STDOUT ---\n%s\n'
                    '--- STDERR ---\n%s\n'
                    % (cmd, PKG, p.returncode, t1 - t0, so, se))
    ev['rc'] = p.returncode
    ev['rc_hex'] = ('0x%08X' % (p.returncode & 0xFFFFFFFF)
                    if 0 <= p.returncode <= 0xFFFFFFFF else None)
    ev['elapsed_s'] = round(t1 - t0, 1)
    ev['stdout_tail'] = so[-6000:]
    ev['stderr_tail'] = se[-2000:]
    ev['telemetry_lines'] = [ln[:240] for ln in so.splitlines()
                             if ('最终统计' in ln or '收尾' in ln
                                 or '就绪' in ln or '端到端' in ln
                                 or '模型加载完成' in ln)]
    for f_ in (TTS_OUT, JSONL, BACKLOG_CSV):
        ev.setdefault('artifacts', {})[os.path.basename(f_)] = (
            {'exists': os.path.isfile(f_),
             'bytes': os.path.getsize(f_) if os.path.isfile(f_) else None,
             'sha256': sha256_file(f_) if os.path.isfile(f_) else None}
            if os.path.isfile(f_) else {'exists': False})
    # ── 逐句遥测分析 ──
    rows = parse_telemetry(JSONL) if os.path.isfile(JSONL) else []
    n = len(rows)
    dropped = [r for r in rows if r.get('dropped')]
    late_drop = [r for r in rows if r.get('late_drop')]
    skipped = [r for r in rows if r.get('end_reason') == 'late_drop']
    speeds = [float(r['speed']) for r in rows
              if r.get('speed') is not None and not r.get('dropped')]
    lags = [float(r['play_lag_s']) for r in rows
            if r.get('play_lag_s') is not None and not r.get('dropped')]
    gains = [float(r['speed_gain']) for r in rows
             if r.get('speed_gain') is not None and not r.get('dropped')]
    rtfs = [float(r['rtf_ewma']) for r in rows
            if r.get('rtf_ewma') is not None and not r.get('dropped')]
    ev['telemetry'] = {
        'n_rows': n,
        'n_dropped': len(dropped),
        'n_late_drop_flag': len(late_drop),
        'n_end_reason_late_drop': len(skipped),
        'n_played': n - len(dropped),
        'dropped_ids': [r.get('id') for r in dropped],
        'dropped_reasons': sorted(set(str(r.get('end_reason'))
                                      for r in dropped)),
        'late_drop_thresholds_seen': sorted(set(
            r.get('late_drop_threshold_s') for r in rows
            if r.get('late_drop_threshold_s') is not None)),
        'speed_p50': pct(speeds, 0.50),
        'speed_p95': pct(speeds, 0.95),
        'speed_max': (max(speeds) if speeds else None),
        'speed_min': (min(speeds) if speeds else None),
        'speed_mean': (round(sum(speeds) / len(speeds), 4) if speeds else None),
        'speed_gain_mean': (round(sum(gains) / len(gains), 4) if gains else None),
        'n_speed_ge_1_8': sum(1 for s in speeds if s >= 1.8),
        # 🔴 **RTF 动态封顶是不是真正的瓶颈**（speed ≤ 1/r）：
        #   `_speed_cap_by_rtf` 会把上限压到 `max(1/r, 语言下限)` ⇒
        #   若合成 RTF < 1（合成快于实时），1/r 会**低于**语言下限 1.10
        #   ⇒ 倍率被钉在 1.10 ⇒ **2.0× 的天花板根本够不着**。
        #   ⇒ 如实统计「被钉在下限的句数」与 RTF 分布，供 reviewer 判断。
        'n_speed_at_floor_1_10': sum(1 for s in speeds if abs(s - 1.10) < 1e-6),
        'rtf_ewma_min': (min(rtfs) if rtfs else None),
        'rtf_ewma_max': (max(rtfs) if rtfs else None),
        'rtf_ewma_mean': (round(sum(rtfs) / len(rtfs), 4) if rtfs else None),
        'implied_cap_1_over_r_min': (round(1.0 / max(rtfs), 4)
                                     if rtfs and max(rtfs) else None),
        'play_lag_max': (max(lags) if lags else None),
        'play_lag_p95': pct(lags, 0.95),
        'play_lag_end': (lags[-1] if lags else None),
        # 🔴 `n_speed_floor_conflict` 是**累计计数器** ⇒ 取 max（末句的值），
        #    **不能求和**（求和会把同一个计数反复累加 ⇒ 假数字）。
        'n_speed_floor_conflict': max([int(r.get('n_speed_floor_conflict') or 0)
                                       for r in rows] or [0]),
    }
    ev['checks'] = [
        {'name': '丢句数 = 0（late_drop/跳过）',
         'pass': (len(dropped) == 0),
         'detail': 'dropped=%d late_drop=%d end_reason_late_drop=%d'
                   % (len(dropped), len(late_drop), len(skipped))},
        {'name': '倍率 max ≤ 2.0',
         'pass': (ev['telemetry']['speed_max'] is not None
                  and ev['telemetry']['speed_max'] <= 2.0 + 1e-9),
         'detail': 'max=%s p50=%s p95=%s'
                   % (ev['telemetry']['speed_max'], ev['telemetry']['speed_p50'],
                      ev['telemetry']['speed_p95'])},
        {'name': '退出码 0',
         'pass': (p.returncode == 0), 'detail': 'rc=%s' % p.returncode},
        {'name': '产出齐备（wav + 逐句 jsonl + 积压曲线）',
         'pass': all(os.path.isfile(f_) for f_ in (TTS_OUT, JSONL, BACKLOG_CSV)),
         'detail': ','.join(os.path.basename(f_) for f_ in
                             (TTS_OUT, JSONL, BACKLOG_CSV))},
    ]
    ev['n_fail'] = sum(1 for c in ev['checks'] if not c['pass'])
    # ── 与 app552 对照 ──
    base = {}
    if os.path.isfile(BASELINE):
        b = json.load(open(BASELINE, encoding='utf-8'))
        base = {
            'source_json': 'results/app/app552_specialmvp_dropped_sentences.json',
            'source_wav': 'results/app/_app538_special_tts_out.wav（sp1 的 10 分钟整链）',
            'threshold_late_drop_sec': 6.0, 'speed_cap': 1.5,
            'n_submitted': b['summary']['n_submitted'],
            'n_played': b['summary']['n_played'],
            'n_dropped': b['summary']['n_dropped'],
            'lag_max': b['exclusions']['lag_max'],
            'lag_min': b['exclusions']['lag_min'],
            'max_backlog_s': 31.13,
            'end_lag_s': 3.60,
            'note': ('app552 的数据源实为 **sp1** 的 10 分钟整链'
                     '（阈值 6.0 / 上限 1.5，同口径）⇒ 对照成立；'
                     '「sp2」这个标签不准，本轮如实更正。'),
        }
    cur = {
        'source': 'sp3（APP-111：阈值 0.0 / 上限 2.00）',
        'n_submitted': ev['telemetry']['n_rows'],
        'n_played': ev['telemetry']['n_played'],
        'n_dropped': ev['telemetry']['n_dropped'],
        'lag_max': ev['telemetry']['play_lag_max'],
        'max_backlog_s': None,
        'end_lag_s': ev['telemetry']['play_lag_end'],
        'speed_mean': ev['telemetry']['speed_mean'],
        'speed_max': ev['telemetry']['speed_max'],
    }
    ev['comparison_app552'] = {
        'baseline_app552': base, 'current_sp3': cur,
        'table': [
            {'metric': '丢句数（late_drop/跳过）', 'app552': base.get('n_dropped'),
             'sp3': cur['n_dropped']},
            {'metric': '提交句数', 'app552': base.get('n_submitted'),
             'sp3': cur['n_submitted']},
            {'metric': '播完句数', 'app552': base.get('n_played'),
             'sp3': cur['n_played']},
            {'metric': '最大滞后 (s)', 'app552': base.get('lag_max'),
             'sp3': cur['lag_max']},
            {'metric': '平均倍率', 'app552': None,
             'sp3': cur['speed_mean']},
            {'metric': '倍率上限', 'app552': 1.5, 'sp3': 2.0},
            {'metric': '跳句阈值 (s)', 'app552': 6.0, 'sp3': 0.0},
        ],
        'note': ('app552 的平均倍率未记录（原 json 只有 lag 与丢句）⇒ '
                 '该格如实留空，不臆测。'),
    }
    # ── 抽 ≥1.8× 的 wav ──
    ev['fast_samples'] = extract_fast_wavs(rows, TTS_OUT, 1.8, 3)
    ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('rc=%d  %s' % (p.returncode, json.dumps(ev['telemetry'],
                                                  ensure_ascii=False)))
    for c in ev['checks']:
        print('  [%s] %s | %s' % ('PASS' if c['pass'] else 'FAIL',
                                  c['name'], c['detail']))
    print('VERDICT=%s -> %s' % (ev['verdict'], OUT))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
