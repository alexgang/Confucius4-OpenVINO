#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app415_rc6_langs.py —— **APP-098 三.4：rc6 的 10 语言验收**。

## reviewer 三.4 原文
> **10 种语言**：每种 5 句做 MT，每种 2 句做 TTS，wav 落盘，原文和译文存成 json。
> 我会拉回去用 MiniMax 回转写。**目标机不调 MiniMax。**

## 🔴🔴🔳 纪律
* **目标机绝不调 MiniMax**（本脚本里没有 MiniMax 的任何调用 ⇒ 只做合成 + 落盘）。
* **设备作业 ⇒ 持 MACHINE_LOCK**。
* 素材：复用 §167/APP-097 已用过的英文定稿句（`results/app/app333_en_sents.json`）
  ⇒ 与 APP-097 的数字**同源可比**。

## 用法
```
.venv/Scripts/python.exe results/app/_app415_rc6_langs.py --pkg <rc6 目录> --lock
```
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)

OUTROOT = os.path.join(HERE, 'app415_rc6_langs')
REPORT = os.path.join(HERE, 'app415_rc6_langs.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

#: 🔴 APP-097 的 10 种目标语言（顺序＝Qwen3-TTS `codec_language_id` 的顺序）
LANGS = ('zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'pt', 'it', 'ru')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def pid_alive(pid):
    import ctypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    if not ok:
        return True
    return code.value == STILL_ACTIVE


def acquire_lock(tag):
    payload = 'app %d %s %s' % (os.getpid(), now(), tag)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, payload.encode('utf-8'))
        os.close(fd)
        return payload
    except FileExistsError:
        return None


def release_lock():
    try:
        if os.path.exists(LOCK):
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                info = f.read()
            m = re.match(r'\S+\s+(\d+)\s', info)
            if m and pid_alive(int(m.group(1))):
                print('🔴 锁的 PID 还活着 ⇒ 不删锁')
                return False
            os.remove(LOCK)
            print('[lock] 已释放')
            return True
    except Exception as e:
        print('[lock] 释放异常：%r' % e)
    return False


def load_sentences():
    """取 APP-097 用过的英文定稿句（**同源** ⇒ 与 §167 的数字可比）。

    🔴 `app333_en_sents.json` 的结构 = **list of dict**（`{'text': ..., ...}`）
    ⇒ 不能直接当字符串列表用（第一版会拿到 dict 的 str()）⇒ 这里**取 `text` 字段**。
    """
    for cand in (os.path.join(HERE, 'app333_en_sents.json'),
                 os.path.join(REPO, 'results', 'app', 'app333_en_sents.json')):
        if not os.path.isfile(cand):
            continue
        d = json.load(open(cand, encoding='utf-8'))
        out = []
        if isinstance(d, list):
            for x in d:
                if isinstance(x, str):
                    out.append(x)
                elif isinstance(x, dict) and x.get('text'):
                    out.append(str(x['text']))
        elif isinstance(d, dict):
            for k in ('sentences', 'sents', 'en', 'lines'):
                v = d.get(k)
                if isinstance(v, list):
                    for x in v:
                        if isinstance(x, str):
                            out.append(x)
                        elif isinstance(x, dict) and x.get('text'):
                            out.append(str(x['text']))
                    break
        if out:
            return out, cand
    return [], None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--lock', action='store_true')
    ap.add_argument('--mt-sents', type=int, default=5)
    # 🔴 APP-099 四.5：每种语言 **5 句 MT + 5 个 TTS wav**（旧口径是 2 句，
    #    reviewer §2e 已指出 app419 每语种只有 2 个 wav 属验收不足）。
    #    ⚠️ 这里改的是**测试脚本的复验句数**，不是生产默认值/判据阈值。
    ap.add_argument('--tts-sents', type=int, default=5)
    args = ap.parse_args()
    PKG = args.pkg
    py = os.path.join(PKG, 'python', 'python.exe')
    app = os.path.join(PKG, 'app', 'live_caption_app.py')
    os.makedirs(OUTROOT, exist_ok=True)

    ev = {'created_at': now(), 'pkg': PKG, 'langs': list(LANGS),
          'mt_sents_per_lang': args.mt_sents,
          'tts_sents_per_lang': args.tts_sents,
          'per_lang': {}, 'verdict': 'PENDING'}

    sents, sent_src = load_sentences()
    ev['sentences_source'] = sent_src
    ev['n_sentences_available'] = len(sents)
    if len(sents) < max(args.mt_sents, args.tts_sents):
        print('🔴 英文素材不足（%d 句）' % len(sents))
        ev['verdict'] = 'FAIL_NO_SENTENCES'
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        return 2

    lock_payload = None
    if args.lock:
        lock_payload = acquire_lock('rc6_langs')
        if not lock_payload:
            print('🔴 MACHINE_LOCK 已被占用 ⇒ 本轮不跑设备作业')
            ev['verdict'] = 'SKIPPED_LOCK_BUSY'
            with open(REPORT, 'w', encoding='utf-8') as f:
                json.dump(ev, f, ensure_ascii=False, indent=1)
            return 1
        ev['lock'] = lock_payload
        print('[lock] 已获取：%s' % lock_payload)

    try:
        for lang in LANGS:
            d = os.path.join(OUTROOT, lang)
            os.makedirs(d, exist_ok=True)
            # 🔴 **MT 臂**：5 句英文 → 目标语言；wav 落盘（--tts-dump-dir）
            mt_json = os.path.join(d, 'mt.json')
            cmd = [py, '-s', app, '--cli',
                   '--engine', 'npu_int8', '--asr-device', 'NPU',
                   '--translate', lang, '--mt-device', 'GPU.0',
                   '--tts', 'on', '--tts-voice', 'A', '--tts-device', 'NPU',
                   '--file', os.path.join(HERE, '_app415_src.wav'),
                   '--max-seconds', '0',
                   '--out', os.path.join(d, 'subtitles.txt'),
                   '--tts-dump-dir', d,
                   '--tts-jsonl', os.path.join(d, 'tts.jsonl')]
            logp = os.path.join(d, 'run.log')
            print('[lang] %s …' % lang)
            t0 = time.time()
            with open(logp, 'wb') as lf:
                p = subprocess.run(cmd, cwd=PKG, stdout=lf,
                                   stderr=subprocess.STDOUT, timeout=1800)
            dt = round(time.time() - t0, 1)
            # 🔴 收集落盘产物
            wavs = sorted(f for f in os.listdir(d) if f.lower().endswith('.wav'))
            rec = {
                'lang': lang, 'exit_code': p.returncode, 'seconds': dt,
                'log_path': logp, 'log_bytes': os.path.getsize(logp),
                'n_wav': len(wavs), 'wavs': wavs,
                'subtitles_path': os.path.join(d, 'subtitles.txt'),
                'tts_jsonl': os.path.join(d, 'tts.jsonl'),
            }
            if os.path.exists(rec['subtitles_path']):
                st = open(rec['subtitles_path'], encoding='utf-8',
                          errors='replace').read()
                rec['n_subtitle_chars'] = len(st.strip())
                rec['has_output'] = bool(st.strip())
            else:
                rec['has_output'] = False
            ev['per_lang'][lang] = rec
            print('   exit=%s %ss wav=%d 输出=%s'
                  % (p.returncode, dt, len(wavs), rec.get('has_output')))
    finally:
        if args.lock:
            release_lock()

    # ── 汇总 json（原文 + 译文 + wav 路径）────────────────────────
    summary = {'created_at': now(), 'pkg': PKG, 'langs': list(LANGS),
               'sentences_source': sent_src, 'per_lang': {}}
    for lang in LANGS:
        d = os.path.join(OUTROOT, lang)
        subs = []
        sp = os.path.join(d, 'subtitles.txt')
        if os.path.exists(sp):
            subs = [l for l in open(sp, encoding='utf-8',
                                    errors='replace').read().splitlines() if l.strip()]
        wavs = sorted(f for f in os.listdir(d) if f.lower().endswith('.wav')) \
            if os.path.isdir(d) else []
        summary['per_lang'][lang] = {
            'n_source_sentences': args.mt_sents,
            'n_source_tts_sentences': args.tts_sents,
            'source_en': sents[:args.mt_sents],
            'translations': subs,
            'n_translations': len(subs),
            'wavs': wavs,
            'n_wavs': len(wavs),
        }
    sp = os.path.join(OUTROOT, 'summary.json')
    with open(sp, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    ev['summary_path'] = sp

    n_ok = sum(1 for r in ev['per_lang'].values()
               if r.get('has_output') and r.get('n_wav', 0) > 0)
    ev['n_langs'] = len(ev['per_lang'])
    ev['n_langs_ok'] = n_ok
    ev['verdict'] = 'PASS' if n_ok == len(LANGS) else 'PARTIAL'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[langs] %d/%d 语种有输出+wav ⇒ %s'
          % (n_ok, len(LANGS), ev['verdict']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
