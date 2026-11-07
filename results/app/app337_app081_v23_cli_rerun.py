#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app337 — APP-080 ⑥ / APP-081 4d+4e：CLI SPE 前 5 分钟**夹具修正后的重跑**。

首轮 `app332` CLI 判 PARTIAL（rc=0 但 `n_tts_jsonl_rows=0`、TTS「提交 0 播完 0」）。
🔴 根因（本脚本已定位，非 v2.3 功能缺陷）：
  `live_caption_app.py` 的 `--translate` 默认值是 `'off'`（L7659）；
  首轮命令**漏传 `--translate zh`** ⇒ `mt.active=False` ⇒ 无定稿译文 ⇒
  CLI 的 `tts.submit()` 只在 `mt.pop_outbox()` 的 `kind in ('final','fix')`
  分支（L7116-7134）与收尾分支（L7167-7182）里调用 ⇒ **一次都不触发**。
  ⇒ 首轮「零段检查 0 命中」是**弱标记恒真**（没有配音自然没有零段告警），
    按判据工程纪律不得据此写 PASS。

本重跑：
  ① 显式 `--translate zh`，设备显式指定为非 CPU（GPU.0 / NPU / NPU）；
  ② 保留 `--tts-voice follow_speaker` ⇒ 复证 APP-081 4e 回落日志；
  ③ 零段检查改用**逐句遥测本体特征**（`n_samples` / `peak` / `dropped` /
     `error` / `read_delta`），并聚合日志「最终统计」的提交/播完/空句；
  ④ 反证：用首轮缺陷产物（tts_rows=0）与注入的零段假行验证判据能识破，
     干净行不得误伤（防恒真、防「PASS ≠ 正确」）；
  ⑤ 全部输出用 app337 前缀，**不覆盖 app332 首轮任何证据**。

🔴 纪律：持 MACHINE_LOCK + 复核归属/存活 + 安静窗口；后台启动 + addpid；
   不在 CPU 跑推理；ASR WER 由 reviewer 用 MiniMax 回转写（三态 None）。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import pkg_paths  # noqa: E402 —— 包目录名单一下数据源（§48 闸门）
import machine_lock_app  # noqa: E402

VER = '2.3'
CLEAN = r'C:\v23_cleantest'
PKG = os.path.join(CLEAN, pkg_paths.PKG_NAME_PREFIX + VER)
SPE_WAV = os.path.join(HERE, '_app264_SPE_1500s.wav')
P = lambda n: os.path.join(HERE, 'app337_v23_cli_rerun_' + n)
OUT_JSON = os.path.join(HERE, 'app337_v23_cli_rerun.json')
FIRST = os.path.join(HERE, 'app332_v23_cli.json')
BACKLOG = os.path.join(HERE, 'tts_backlog_curve.csv')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def stat_of(p):
    st = os.stat(p)
    return {'bytes': st.st_size,
            'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime(
                '%Y-%m-%d %H:%M:%S'),
            'sha256': sha256_file(p)}


def zero_segment_reason(row):
    """零段/无效配音的**本体特征**判定，返回原因列表（空 = 正常）。"""
    bad = []
    try:
        n = int(row.get('n_samples') or 0)
    except (TypeError, ValueError):
        n = 0
    try:
        pk = float(row.get('peak') or 0)
    except (TypeError, ValueError):
        pk = 0.0
    if n <= 0:
        bad.append('n_samples<=0')
    if pk <= 0:
        bad.append('peak<=0')
    if row.get('dropped'):
        bad.append('dropped')
    if row.get('error'):
        bad.append('error=' + str(row.get('error'))[:60])
    return bad


def counterproof(first_ev):
    """🔴 反证：判据必须能识破「已知有缺陷的旧产物/注入缺陷」，且不误伤干净行。"""
    cases = []
    # ① 首轮真实缺陷产物：完全没有配音提交
    n_first = first_ev.get('n_tts_jsonl_rows') if first_ev else None
    cases.append({'id': 'CP_first_run_no_tts',
                  'injected': 'app332_v23_cli.json: n_tts_jsonl_rows=%r' % n_first,
                  'detected': (n_first == 0),
                  'identified': (n_first == 0)})
    # ② 注入零段假行
    fake_zero = {'n_samples': 0, 'peak': 0.0, 'dropped': False, 'error': None}
    cases.append({'id': 'CP_zero_samples_row',
                  'injected': json.dumps(fake_zero, ensure_ascii=False),
                  'detected': bool(zero_segment_reason(fake_zero)),
                  'identified': bool(zero_segment_reason(fake_zero))})
    # ③ 注入丢弃行
    fake_drop = {'n_samples': 24000, 'peak': 0.3, 'dropped': True,
                 'error': None}
    cases.append({'id': 'CP_dropped_row',
                  'injected': json.dumps(fake_drop, ensure_ascii=False),
                  'detected': bool(zero_segment_reason(fake_drop)),
                  'identified': bool(zero_segment_reason(fake_drop))})
    # ④ 干净行不得误伤
    clean = {'n_samples': 24960, 'peak': 0.42, 'rms': 0.08,
             'dropped': False, 'error': None, 'read_delta': 24960}
    z = zero_segment_reason(clean)
    cases.append({'id': 'CP_clean_row_not_flagged',
                  'injected': json.dumps(clean, ensure_ascii=False),
                  'detected': bool(z), 'identified': not z})
    return cases


def main():
    # 🔴 长作业后台启动 ⇒ 立刻把真实 PID 落盘，供 session_lease addpid 登记
    with open(os.path.join(HERE, '_app337_run.pid'), 'w', encoding='utf-8') as _pf:
        _pf.write(str(os.getpid()))
    ev = {'tool': 'app337', 'app': 'APP-080 ⑥ / APP-081 4d+4e',
          'at_start': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'reason': ('首轮 app332 CLI 漏传 --translate zh ⇒ MT 未启用 ⇒ '
                     'tts.submit 从不触发；零段检查弱标记恒真 ⇒ 判据修正后重跑'),
          'pkg': PKG}
    py = os.path.join(PKG, 'python', 'python.exe')
    app = os.path.join(PKG, 'app', 'live_caption_app.py')
    for k, p in [('python', py), ('app', app), ('spe_wav', SPE_WAV)]:
        if not os.path.isfile(p):
            ev['verdict'] = 'FAIL_MISSING'
            ev['missing'] = k
            json.dump(ev, open(OUT_JSON, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            print('[app337] FAIL_MISSING', k)
            return 2

    # 不覆盖仓库既有证据：把首轮 backlog 曲线另存
    if os.path.isfile(BACKLOG):
        bak = os.path.join(HERE, 'app332_v23_cli_backlog_curve.csv')
        if not os.path.isfile(bak):
            shutil.copy2(BACKLOG, bak)
            ev['backlog_backup'] = bak

    log = P('output.txt')
    tts_jsonl = P('tts.jsonl')
    out_txt = P('final.txt')
    spk_jsonl = P('spk_seg.jsonl')
    cmd = [py, app, '--cli', '--file', SPE_WAV, '--max-seconds', '300',
           '--translate', 'zh',                       # 🔴 首轮漏传的参数
           '--asr-device', 'GPU.0', '--mt-device', 'NPU',
           '--tts-device', 'NPU',                     # 🔴 显式非 CPU
           '--tts', 'on', '--tts-voice', 'follow_speaker',
           '--speaker', 'off', '--out', out_txt,
           '--tts-jsonl', tts_jsonl, '--spk-seg-jsonl', spk_jsonl]
    ev['cmd'] = cmd

    # 🔴 持锁 → 复核归属与存活 → 安静窗口 → 再复核 → 开跑
    lk = machine_lock_app.LockHeld(module='app-v23-cli-rerun',
                                   timeout=3600, poll=15)
    if not lk.acquire():
        ev['verdict'] = 'FAIL_NO_LOCK'
        json.dump(ev, open(OUT_JSON, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        print('[app337] FAIL_NO_LOCK')
        return 3
    try:
        ev['lock_intact_before'] = list(lk.intact())
        qok, qinfo = lk.wait_quiet(quiet_seconds=45.0, timeout=1800.0)
        ev['quiet_window'] = {'ok': qok, 'info': qinfo}
        ev['lock_intact_after_quiet'] = list(lk.intact())
        if not qok or not ev['lock_intact_after_quiet'][0]:
            ev['verdict'] = 'FAIL_NO_QUIET_WINDOW'
            json.dump(ev, open(OUT_JSON, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            print('[app337] FAIL_NO_QUIET_WINDOW')
            return 4

        t0 = time.time()
        stop_evt = threading.Event()
        prog = P('progress.json')

        def watchdog():
            # 🔴 后台长作业每 15 s 落一次进度：主会话可分次轮询，
            #    即便进程被外部清理也能从进度文件判断停在哪一步。
            while not stop_evt.wait(15.0):
                try:
                    snap = {'at': datetime.datetime.now().strftime(
                                '%Y-%m-%d %H:%M:%S'),
                            'elapsed_s': round(time.time() - t0, 1),
                            'log_bytes': (os.path.getsize(log)
                                          if os.path.isfile(log) else 0),
                            'tts_jsonl_rows': 0,
                            'state': 'RUNNING', 'pid': os.getpid()}
                    if os.path.isfile(tts_jsonl):
                        with open(tts_jsonl, encoding='utf-8',
                                  errors='ignore') as jf:
                            snap['tts_jsonl_rows'] = sum(1 for x in jf if x.strip())
                    with open(prog, 'w', encoding='utf-8') as pf:
                        json.dump(snap, pf, ensure_ascii=False, indent=2)
                except Exception:
                    pass

        wd = threading.Thread(target=watchdog, daemon=True)
        wd.start()
        try:
            with open(log, 'wb') as f:
                try:
                    r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT,
                                       cwd=PKG, timeout=1800)
                    rc = r.returncode
                except subprocess.TimeoutExpired:
                    rc = -9
        finally:
            stop_evt.set()
            wd.join(timeout=2.0)
        wall = round(time.time() - t0, 1)
        try:
            with open(prog, 'w', encoding='utf-8') as pf:
                json.dump({'state': 'DONE', 'rc': rc, 'wall_s': wall,
                           'at': datetime.datetime.now().strftime(
                               '%Y-%m-%d %H:%M:%S')},
                          pf, ensure_ascii=False, indent=2)
        except Exception:
            pass
        ev['lock_intact_after_run'] = list(lk.intact())
    finally:
        lk.release()
        ev['lock'] = 'RELEASED'

    # 新生成的 backlog 曲线另存，不留在通用名上
    if os.path.isfile(BACKLOG):
        shutil.copy2(BACKLOG, P('backlog_curve.csv'))

    txt = open(log, 'rb').read().decode('utf-8', errors='replace')
    lines = txt.splitlines()
    fallback = [l for l in lines if '[v23]' in l and '回落预设 A' in l]
    zero_log = [l.strip() for l in lines
                if re.search(r'(?i)(zero[_ -]?audio|零段|没有可用的音色|empty audio)',
                             l)]
    rtf_lines = [l.strip() for l in lines
                 if re.search(r'(?i)RTF|backlog|积压|实时率', l)]
    spk_conf_err = [l.strip() for l in lines
                    if 'note_final() got an unexpected keyword' in l]
    m_final = re.search(
        r'最终统计（close 后）：提交\s*(\d+)\s+播完\s*(\d+)\s+丢弃\s*(\d+)\s+'
        r'关闭作废\s*(\d+)\s+空句\s*(\d+)\s+失败\s*(\d+)', txt)
    stats = {}
    if m_final:
        stats = dict(zip(('submitted', 'played', 'dropped', 'void_on_close',
                          'empty_sentences', 'failed'),
                         (int(x) for x in m_final.groups())))

    rows = []
    if os.path.isfile(tts_jsonl):
        for ln in open(tts_jsonl, encoding='utf-8', errors='replace'):
            if not ln.strip():
                continue
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                rows.append({'_parse_error': ln[:120]})
    zero_rows = []
    for i, row in enumerate(rows):
        why = zero_segment_reason(row)
        if why:
            zero_rows.append({'row': i, 'reasons': why,
                              'id': row.get('id'), 'text': str(row.get('text'))[:60]})

    first_ev = (json.load(open(FIRST, encoding='utf-8'))
                if os.path.isfile(FIRST) else None)
    cp = counterproof(first_ev)
    n_cp = sum(1 for c in cp if c['identified'])

    n_rows = len(rows)
    submitted = stats.get('submitted')
    played = stats.get('played')
    have_audio = (n_rows > 0 and submitted is not None and submitted > 0
                  and played is not None and played > 0)
    zero_ok = (len(zero_rows) == 0 and not zero_log
               and stats.get('empty_sentences', 0) == 0)
    fallback_ok = len(fallback) >= 1
    rtf_ok = len(rtf_lines) >= 1
    cp_ok = (n_cp == len(cp))
    devices_ok = not any(re.search(r'(?i)设备\s*CPU|device=CPU|在 CPU 上', l)
                         for l in lines)
    lock_ok = bool(ev.get('lock_intact_after_quiet', [False])[0]
                   and ev.get('lock_intact_after_run', [False])[0])

    ev.update({
        'at_end': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'rc': rc, 'wall_s': wall,
        'log': log, 'log_stat': stat_of(log),
        'clone_fallback_log_lines': fallback[:10],
        'n_clone_fallback_log_lines': len(fallback),
        'n_zero_audio_log_lines': len(zero_log),
        'zero_audio_log_lines': zero_log[:20],
        'n_rtf_backlog_log_lines': len(rtf_lines),
        'rtf_backlog_log_lines': rtf_lines[:20],
        'n_spk_conf_signature_errors': len(spk_conf_err),
        'spk_conf_signature_error_sample': spk_conf_err[:3],
        'tts_final_stats': stats,
        'tts_jsonl': tts_jsonl, 'n_tts_jsonl_rows': n_rows,
        'zero_segment_check': {
            'criteria': '逐句本体特征 n_samples>0 / peak>0 / not dropped / not error '
                        '+ 日志最终统计 提交>0 播完>0 空句=0（非弱标记）',
            'n_bad_rows': len(zero_rows), 'bad_rows': zero_rows[:20],
            'verdict': zero_ok},
        'final_text': out_txt,
        'final_text_bytes': os.path.getsize(out_txt) if os.path.isfile(out_txt) else 0,
        'asr_wer': None,
        'asr_wer_note': '质量判定由 reviewer 用 MiniMax 回转写；本轮只落盘 CLI 定稿文本，'
                        '不自行调用 MiniMax、不在 CPU 上算 WER（三态：无法判定）',
        'devices_not_cpu': devices_ok,
        'lock_chain_ok': lock_ok,
        'counterproof': cp,
        'counterproof_identified': '%d/%d' % (n_cp, len(cp)),
        'checks': {'rc0': rc == 0, 'fallback': fallback_ok,
                   'have_audio': have_audio, 'zero_ok': zero_ok,
                   'rtf': rtf_ok, 'counterproof': cp_ok,
                   'devices_not_cpu': devices_ok, 'lock_chain': lock_ok},
        'artifacts': {k: (stat_of(v) if os.path.isfile(v) else None)
                      for k, v in [('log', log), ('tts_jsonl', tts_jsonl),
                                   ('final_text', out_txt),
                                   ('spk_jsonl', spk_jsonl),
                                   ('backlog_curve', P('backlog_curve.csv'))]},
        'output_tail': lines[-15:],
    })
    all_ok = all(ev['checks'].values())
    ev['verdict'] = 'PASS' if all_ok else 'PARTIAL'
    json.dump(ev, open(OUT_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print('[app337] %s rc=%d wall=%.1fs rows=%d submitted=%s played=%s '
          'zero_bad=%d fallback=%d cp=%d/%d ⇒ %s'
          % (ev['verdict'], rc, wall, n_rows, submitted, played,
             len(zero_rows), len(fallback), n_cp, len(cp), OUT_JSON))
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
