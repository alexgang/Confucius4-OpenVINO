#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app332 — APP-081 第 4d/4e：v2.3 交付包 ⑥ 全套验收（分阶段、每项落盘）。

用法（各阶段可独立跑，便于后台启动 + 分次轮询）：
  python app332_app081_v23_verify.py --stage zip_sha
  python app332_app081_v23_verify.py --stage unzip_check
  python app332_app081_v23_verify.py --stage blacklist
  python app332_app081_v23_verify.py --stage gui
  python app332_app081_v23_verify.py --stage cli
  python app332_app081_v23_verify.py --stage summary

原始结果文件（写进 results/app/）：
  app332_v23_zip_sha.json / app332_v23_unzip_check.json + _check_output.txt
  app332_v23_blacklist.json / app332_v23_gui.json + 2 张 PNG
  app332_v23_cli.json + _cli_output.txt + tts.jsonl
  app332_v23_verify_summary.json
🔴 质量判定（ASR WER / 音质）由 reviewer 用 MiniMax 回转写，本脚本不自行调用 MiniMax。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import pkg_paths  # noqa: E402 —— 包目录名的单一数据源（§48 闸门）

# 🔴 不写死完整客户包目录名 ⇒ 用前缀常量 + 版本号拼接
VER = '2.3'
PKG_NAME = pkg_paths.PKG_NAME_PREFIX + VER
HOME = pkg_paths.PKG_ROOT_DEFAULT
ZIP = os.path.join(HOME, PKG_NAME + '.zip')
CLEAN = r'C:\v23_cleantest'
PKG = os.path.join(CLEAN, PKG_NAME)
SPE_WAV = os.path.join(HERE, '_app264_SPE_1500s.wav')
P = lambda n: os.path.join(HERE, 'app332_v23_' + n)


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


def dump(name, obj):
    p = P(name)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return p


def stage_zip_sha():
    if not os.path.isfile(ZIP):
        return {'verdict': 'FAIL_NO_ZIP', 'zip': ZIP}
    with zipfile.ZipFile(ZIP) as zf:
        names = zf.namelist()
    ev = {'stage': 'zip_sha', 'zip': ZIP, **stat_of(ZIP),
          'n_zip_entries': len(names),
          'n_files': len([n for n in names if not n.endswith('/')]),
          'top_level': sorted(set(n.split('/')[0] for n in names))[:5],
          'has_babelvox_demo': any(
              re.search(r'babelvox/data/speakers/(cindy|lou|phil|steve)\.', n)
              for n in names),
          'has_bridge_token': any(n.endswith('bridge_token.txt') for n in names),
          'verdict': 'PASS'}
    ev['verdict'] = ('PASS' if not ev['has_babelvox_demo']
                     and not ev['has_bridge_token'] else 'FAIL')
    print('[zip_sha]', ev['verdict'], ev['bytes'], 'B /', ev['n_zip_entries'],
          'entries / sha', ev['sha256'][:16])
    dump('zip_sha.json', ev)
    return ev


def stage_unzip_check():
    if not os.path.isfile(ZIP):
        return {'verdict': 'FAIL_NO_ZIP'}
    t0 = time.time()
    if not os.path.isdir(PKG):
        os.makedirs(CLEAN, exist_ok=True)
        with zipfile.ZipFile(ZIP) as zf:
            zf.extractall(CLEAN)
    n_files = sum(len(fs) for _r, _d, fs in os.walk(PKG))
    py = os.path.join(PKG, 'python', 'python.exe')
    app = os.path.join(PKG, 'app', 'live_caption_app.py')
    log = P('unzip_check_output.txt')
    ev = {'stage': 'unzip_check', 'clean_dir': CLEAN, 'pkg': PKG,
          'n_extracted_files': n_files, 'unzip_wall_s': round(time.time() - t0, 1),
          'py': py, 'exists_py': os.path.isfile(py),
          'exists_app': os.path.isfile(app)}
    if os.path.isfile(py) and os.path.isfile(app):
        cmd = [py, app, '--check']
        t1 = time.time()
        with open(log, 'wb') as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT,
                               cwd=PKG, timeout=900)
        ev.update({'cmd': cmd, 'rc': r.returncode,
                   'check_wall_s': round(time.time() - t1, 1),
                   'log': log, **{'log_stat': stat_of(log)}})
        txt = open(log, 'rb').read().decode('utf-8', errors='replace')
        ev['n_ok_lines'] = len(re.findall(r'\[ OK \]', txt))
        ev['n_fail_lines'] = len(re.findall(r'\[FAIL\]|\[ NG \]', txt))
        ev['output_tail'] = txt.strip().splitlines()[-8:]
        ev['verdict'] = ('PASS' if r.returncode == 0
                         and ev['n_fail_lines'] == 0 else 'FAIL')
    else:
        ev['verdict'] = 'FAIL_MISSING_FILES'
    print('[unzip_check]', ev['verdict'], n_files, 'files, rc=',
          ev.get('rc'), 'OK lines=', ev.get('n_ok_lines'))
    dump('unzip_check.json', ev)
    return ev


BLACKLIST = {
    'meeting': re.compile(r'(?i)(260902_SPE|_spoken|SPE_\d+.*\.wav$)'),
    'clone_wav': re.compile(r'(?i)(clone.*\.(wav|npz)$|tts_speakers/)'),
    'babelvox_demo': re.compile(
        r'(?i)babelvox/data/speakers/(cindy|lou|phil|steve)\.(json|npy)$'),
    'bridge_token': re.compile(r'(?i)(^|/)bridge_token\.txt$'),
    'torch_cuda': re.compile(r'(?i)(^|/)(torch|cuda)[/_].*\.(dll|pyd|cu|cuh)$'),
}
TEXT_EXT = {'.py', '.md', '.json', '.txt', '.bat', '.xml', '.cfg', '.ini',
            '.jinja', '.yaml', '.yml'}
DEV_PATH_RE = re.compile(r'(?i)(C:\\Users\\Trekker-PTL|hy_bench|confucius4-openvino)')


def stage_blacklist():
    if not os.path.isdir(PKG):
        return {'verdict': 'FAIL_NO_UNZIP'}
    hits = {k: [] for k in list(BLACKLIST) + ['dev_path_in_text',
                                              'rule_self_reference']}
    n_files, total = 0, 0
    for r, _d, fs in os.walk(PKG):
        for f in fs:
            p = os.path.join(r, f)
            rel = os.path.relpath(p, PKG).replace('\\', '/')
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = 0
            n_files += 1
            total += sz
            for k, cre in BLACKLIST.items():
                if cre.search(rel) and len(hits[k]) < 30:
                    hits[k].append({'path': rel, 'bytes': sz})
            if os.path.splitext(f)[1].lower() in TEXT_EXT and sz < 4_000_000:
                try:
                    txt = open(p, 'rb').read().decode('utf-8', errors='ignore')
                except OSError:
                    continue
                for m in DEV_PATH_RE.finditer(txt):
                    # 🔴 三态口径：`app/v23_preset_only.py` 的
                    #    `BLACKLIST_PATTERNS` / `PKG_EXCLUDE_PATTERNS` 里
                    #    **本来就写着** `hy_bench` 等关键词（检测规则本身），
                    #    不是「硬编码开发路径」⇒ 单独分列、如实记录、不静默放过；
                    #    判据仍对**其它所有文件**生效。
                    line_start = txt.rfind('\n', 0, m.start()) + 1
                    line_end = txt.find('\n', m.end())
                    line = txt[line_start:line_end if line_end > 0 else len(txt)]
                    is_rule = (rel.endswith('v23_preset_only.py')
                               and ("r'(?i)" in line or 'r"(?i)' in line
                                    or 'PATTERNS' in txt[max(0, m.start() - 400):
                                                         m.start()]))
                    bucket = ('rule_self_reference' if is_rule
                              else 'dev_path_in_text')
                    if len(hits[bucket]) < 30:
                        hits[bucket].append(
                            {'path': rel, 'match': m.group(0)[:80],
                             'line': line.strip()[:120]})
    n_real = sum(len(v) for k, v in hits.items()
                 if k != 'rule_self_reference')
    n_self = len(hits['rule_self_reference'])
    ev = {'stage': 'blacklist', 'pkg': PKG, 'n_files': n_files,
          'total_bytes': total, 'n_hits_real': n_real,
          'n_rule_self_reference': n_self, 'hits': hits,
          'rule_self_reference_note':
              'app/v23_preset_only.py 的 BLACKLIST_PATTERNS/PKG_EXCLUDE_PATTERNS '
              '是黑名单规则本身（内含 hy_bench 等关键词），不是硬编码开发路径；'
              '如实单列，判据对其它文件照常生效',
          'checks': [{'name': k, 'verdict': len(v) == 0, 'n': len(v)}
                     for k, v in hits.items()
                     if k != 'rule_self_reference'],
          'verdict': 'PASS' if n_real == 0 else 'FAIL'}
    print('[blacklist]', ev['verdict'], n_files, 'files, real_hits=',
          n_real, 'rule_self_ref=', n_self)
    for k, v in hits.items():
        if v:
            print('   ', k, v[:3])
    dump('blacklist.json', ev)
    return ev


def stage_gui():
    """调用包内 python 跑 app333（真 GUI + PrintWindow 抓图）。"""
    # GUI 脚本需 PIL / pywin32 / openvino ⇒ 用仓库 .venv；
    # 它自己把 sys.path 指向**干净解压目录的 app/** ⇒ import 的是包内源码。
    py = os.path.join(REPO, '.venv', 'Scripts', 'python.exe')
    script = os.path.join(HERE, 'app333_app081_v23_gui_shots.py')
    if not (os.path.isfile(py) and os.path.isfile(script)):
        return {'verdict': 'FAIL_MISSING'}
    out_json = P('gui.json')
    log = P('gui_output.txt')
    with open(log, 'wb') as f:
        r = subprocess.run([py, script, '--pkg', PKG, '--out-json', out_json,
                            '--out-dir', os.path.join(HERE, 'app332_v23_gui_shots')],
                           stdout=f, stderr=subprocess.STDOUT, cwd=PKG, timeout=900)
    ev = {'stage': 'gui', 'rc': r.returncode, 'log': log,
          'out_json': out_json,
          'out_json_exists': os.path.isfile(out_json)}
    if os.path.isfile(out_json):
        inner = json.load(open(out_json, encoding='utf-8'))
        ev['inner'] = inner
        ev['verdict'] = 'PASS' if r.returncode == 0 and inner.get('verdict') == 'PASS' else 'FAIL'
    else:
        ev['verdict'] = 'FAIL_NO_EVIDENCE'
    print('[gui]', ev['verdict'], 'rc=', r.returncode)
    dump('gui_wrapper.json', ev)
    return ev


def stage_cli():
    """CLI SPE 前 5 分钟 + APP-080 ② 旧 clone 设置回落日志实测（同一次运行）。"""
    py = os.path.join(PKG, 'python', 'python.exe')
    app = os.path.join(PKG, 'app', 'live_caption_app.py')
    if not (os.path.isfile(py) and os.path.isfile(app) and os.path.isfile(SPE_WAV)):
        return {'verdict': 'FAIL_MISSING'}
    log = P('cli_output.txt')
    tts_jsonl = P('cli_tts.jsonl')
    out_txt = P('cli_final.txt')
    spk_jsonl = P('cli_spk_seg.jsonl')
    cmd = [py, app, '--cli', '--file', SPE_WAV, '--max-seconds', '300',
           '--tts', 'on', '--tts-voice', 'follow_speaker',
           '--speaker', 'off', '--out', out_txt,
           '--tts-jsonl', tts_jsonl, '--spk-seg-jsonl', spk_jsonl]
    t0 = time.time()
    with open(log, 'wb') as f:
        try:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT,
                               cwd=PKG, timeout=1800)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = -9
    wall = round(time.time() - t0, 1)
    txt = open(log, 'rb').read().decode('utf-8', errors='replace')
    fallback = [l for l in txt.splitlines() if '[v23]' in l and '回落预设 A' in l]
    n_zero = len(re.findall(r'(?i)(zero[_ -]?audio|零段|没有可用的音色|empty audio)', txt))
    rtf_lines = [l.strip() for l in txt.splitlines()
                 if re.search(r'(?i)RTF|backlog|积压|wall_s|实时率', l)][:20]
    n_rtf = len(rtf_lines)
    zero_lines = [l.strip() for l in txt.splitlines()
                  if re.search(r'(?i)(zero[_ -]?audio|零段|没有可用的音色|empty audio)',
                               l)][:20]
    n_seg = 0
    if os.path.isfile(tts_jsonl):
        n_seg = sum(1 for l in open(tts_jsonl, encoding='utf-8', errors='replace')
                    if l.strip())
    ev = {
        'stage': 'cli', 'cmd': cmd, 'rc': rc, 'wall_s': wall,
        'log': log, 'log_stat': stat_of(log),
        'clone_fallback_log_lines': fallback[:10],
        'n_clone_fallback_log_lines': len(fallback),
        'n_zero_audio_log_lines': n_zero,
        'zero_audio_log_lines': zero_lines,
        'n_rtf_backlog_log_lines': n_rtf,
        'rtf_backlog_log_lines': rtf_lines,
        'tts_jsonl': tts_jsonl, 'n_tts_jsonl_rows': n_seg,
        'final_text': out_txt,
        'final_text_bytes': os.path.getsize(out_txt) if os.path.isfile(out_txt) else 0,
        'asr_wer': None,
        'asr_wer_note': '质量判定由 reviewer 用 MiniMax 回转写；本轮只落盘 CLI 定稿文本，'
                        '不自行调用 MiniMax、不在 CPU 上算 WER（三态：无法判定）',
        'output_tail': txt.strip().splitlines()[-15:],
        'artifacts': {k: (stat_of(v) if os.path.isfile(v) else None)
                      for k, v in [('log', log), ('tts_jsonl', tts_jsonl),
                                   ('final_text', out_txt), ('spk_jsonl', spk_jsonl)]},
    }
    ev['clone_fallback_verdict'] = ('PASS' if fallback and rc == 0 else 'FAIL')
    ev['verdict'] = ('PASS' if rc == 0 and fallback and n_seg > 0 else 'PARTIAL')
    print('[cli]', ev['verdict'], 'rc=', rc, 'wall=', wall,
          'fallback_lines=', len(fallback), 'tts_rows=', n_seg)
    dump('cli.json', ev)
    return ev


def stage_summary():
    names = ['zip_sha', 'unzip_check', 'blacklist', 'gui', 'cli']
    parts, verdicts = {}, {}
    for n in names:
        p = P(n + '.json' if n != 'gui' else 'gui_wrapper.json')
        if os.path.isfile(p):
            d = json.load(open(p, encoding='utf-8'))
            parts[n] = {'path': p, 'verdict': d.get('verdict'),
                        'sha256': stat_of(p)['sha256'],
                        'bytes': stat_of(p)['bytes']}
            verdicts[n] = d.get('verdict')
        else:
            parts[n] = {'path': p, 'verdict': 'MISSING'}
            verdicts[n] = 'MISSING'
    ev = {'tool': 'app332', 'app': 'APP-081 4d/4e',
          'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'stages': parts, 'verdicts': verdicts,
          'all_pass': all(v == 'PASS' for v in verdicts.values())}
    dump('verify_summary.json', ev)
    print('[summary]', json.dumps(verdicts, ensure_ascii=False))
    return ev


def stage_all_locked():
    """APP-081 4d 明文：持 MACHINE_LOCK + session_lease 做 ⑥ 全套。

    排队等打包进程释放锁（不抢锁、不 kill 别人的进程）；逐阶段写进度文件，
    便于主会话分次轮询 + beat。
    """
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from machine_lock_app import LockHeld
    # 🔴 先等**正式 zip**（原子改名完成）出现，再取锁：
    #    打包进程持锁压缩时 `.zip.tmp` 不算数；打包失败丢弃 tmp ⇒ 不空跑。
    deadline = time.time() + 2700.0
    while not os.path.isfile(ZIP) and time.time() < deadline:
        print('[wait_zip] 等待正式 zip：%s（每 20 s）' % ZIP, flush=True)
        time.sleep(20)
    if not os.path.isfile(ZIP):
        return {'verdict': 'FAIL_NO_ZIP_TIMEOUT'}
    print('[wait_zip] 正式 zip 已出现，开始排队取锁', flush=True)
    lk = LockHeld(module='app-v23-verify', timeout=10800.0)
    if not lk.acquire():
        return {'verdict': 'FAIL_NO_LOCK'}
    order = [('zip_sha', stage_zip_sha), ('unzip_check', stage_unzip_check),
             ('blacklist', stage_blacklist), ('gui', stage_gui),
             ('cli', stage_cli)]
    progress = {'started_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stages': {}, 'lock': 'HELD'}
    try:
        for name, fn in order:
            progress['stages'][name] = 'RUNNING'
            dump('progress.json', progress)
            try:
                r = fn()
                progress['stages'][name] = r.get('verdict', 'UNKNOWN')
            except Exception as e:
                progress['stages'][name] = 'EXCEPTION: %r' % (e,)
                dump('exception_%s.json' % name,
                     {'stage': name, 'exception': repr(e)})
            dump('progress.json', progress)
            print('[all_locked] %s ⇒ %s' % (name, progress['stages'][name]),
                  flush=True)
        summ = stage_summary()
        progress['summary'] = summ
        progress['stages']['summary'] = 'DONE'
        progress['lock'] = 'TO_RELEASE'
        dump('progress.json', progress)
        return summ
    finally:
        lk.release()


STAGES = {'zip_sha': stage_zip_sha, 'unzip_check': stage_unzip_check,
          'blacklist': stage_blacklist, 'gui': stage_gui, 'cli': stage_cli,
          'summary': stage_summary, 'all_locked': stage_all_locked}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True, choices=list(STAGES))
    a = ap.parse_args()
    ev = STAGES[a.stage]()
    print(json.dumps({'stage': a.stage, 'verdict': ev.get('verdict')},
                     ensure_ascii=False))
