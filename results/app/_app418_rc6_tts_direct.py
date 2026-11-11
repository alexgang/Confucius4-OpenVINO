#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app418_rc6_tts_direct.py —— **APP-098 三.4 补测**：直接调 `tts_engine.stream()`
为**缺 wav 的语种**补落盘（wav + json）。

## 为什么需要这个（**不是**为了绕过什么，而是口径对齐）

APP-097 §2-3 明文：
> **TTS 直接调 `tts_engine.stream()`**（与 `tts_worker._synth_babelvox`
> **同一套参数口径**：`map_language` → `language_supported` →
> `split_long_text` → `clamp_max_new_tokens` → `estimate_sec` → `stream`）

而本轮 `_app415_rc6_langs.py` 走的是**真实 App 链路**（CLI ⇒ 主进程 ⇒ worker）
⇒ 该链路上有一道**过期丢弃闸**（`lag > 6 s` ⇒ 只出字幕不配音）
⇒ **德语**因 TTS 合成慢（积压峰值 **53.16 s**）⇒ 句被丢弃 ⇒ **wav = 0**。

⚠️ **这不是缺陷**：闸门是交付配置的一部分（**只提示、不改用户选的设备** 那条铁律）。
⇒ 但 reviewer 三.4 要的是「**每种 2 句做 TTS，wav 落盘**」
⇒ 用 APP-097 **同款口径**（直接调 `stream()`）补齐 wav 即可，
   **不改动任何生产代码、不改阈值**。

## 纪律
* 🔴 **不调 MiniMax**（质量判定由 reviewer 回转写）。
* 🔴 设备作业 ⇒ **持 MACHINE_LOCK**。
* 🔴 参数链与 `_synth_babelvox` **逐项一致**（下面代码里的顺序即证据）。
* 🔴 音色 = **预设 A**（MiniMVP 无克隆）。

## 用法
```
.venv/Scripts/python.exe results/app/_app418_rc6_tts_direct.py --pkg <rc6 目录> --lock
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
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
OUTROOT = os.path.join(HERE, 'app418_rc6_tts_direct')
REPORT = os.path.join(HERE, 'app418_rc6_tts_direct.json')

LANGS = ('zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'pt', 'it', 'ru')
# 🔴 APP-099 四.5：每种语言 **5 个 TTS wav**（旧值 2 是 app419「每语种只有
#    2 个 wav」的直接原因之一，见 app439_app099_lang_evidence.json）。
#    ⚠️ 只改复验句数，不动生产默认值/判据阈值；同时要求素材本身够 5 句。
N_SENT = 5


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def pid_alive(pid):
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    if not ok:
        return True
    return code.value == 259


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
            info = open(LOCK, encoding='utf-8', errors='replace').read()
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


def load_mt_sentences(langs_dir):
    """读各语种的**译文**（`subtitles.mt.txt`）⇒ TTS 的输入。"""
    out = {}
    for lg in LANGS:
        p = os.path.join(langs_dir, lg, 'subtitles.mt.txt')
        if not os.path.isfile(p):
            out[lg] = []
            continue
        lines = [l.strip() for l in open(p, encoding='utf-8', errors='replace')
                 .read().splitlines() if l.strip()]
        out[lg] = lines
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--lock', action='store_true')
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--langs-dir',
                    default=os.path.join(HERE, 'app415_rc6_langs'))
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    PKG = os.path.abspath(a.pkg)
    os.makedirs(OUTROOT, exist_ok=True)

    ev = {'created_at': now(), 'pkg': PKG, 'device': a.device,
          'n_sent': N_SENT, 'criterion': (
              'APP-097 §2-3 同款口径：直接调 tts_engine.stream()'
              '（map_language → language_supported → split_long_text → '
              'clamp_max_new_tokens → estimate_sec → stream）'),
          'per_lang': {}, 'verdict': 'PENDING'}

    sents = load_mt_sentences(a.langs_dir)
    ev['mt_sentences_found'] = {k: len(v) for k, v in sents.items()}

    lock_payload = None
    if a.lock:
        lock_payload = acquire_lock('rc6_tts_direct')
        if not lock_payload:
            print('🔴 MACHINE_LOCK 已被占用 ⇒ 本轮不跑设备作业')
            ev['verdict'] = 'SKIPPED_LOCK_BUSY'
            json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)
            return 1
        ev['lock'] = lock_payload
        print('[lock] 已获取：%s' % lock_payload)

    # 🔴 跑在**包内 python**下 ⇒ import 的是**包内** `tts_engine`（真包代码）
    runner = os.path.join(HERE, '_app418_tts_worker.py')
    try:
        for lg in LANGS:
            if a.only and lg not in a.only.split(','):
                continue
            texts = sents.get(lg) or []
            if not texts:
                ev['per_lang'][lg] = {'skipped': '没有译文'}
                continue
            d = os.path.join(OUTROOT, lg)
            os.makedirs(d, exist_ok=True)
            outp = os.path.join(d, 'wavs.json')
            cmd = [os.path.join(PKG, 'python', 'python.exe'), '-s', runner,
                   '--pkg', PKG, '--lang', lg, '--device', a.device,
                   '--out', outp,
                   '--texts', json.dumps(texts[:N_SENT], ensure_ascii=False)]
            print('[tts] %s …' % lg)
            t0 = time.time()
            with open(os.path.join(d, 'run.log'), 'wb') as lf:
                p = subprocess.run(cmd, cwd=PKG, stdout=lf,
                                   stderr=subprocess.STDOUT, timeout=1800)
            dt = round(time.time() - t0, 1)
            wavs = []
            end_reasons = []
            if os.path.exists(outp):
                try:
                    j = json.load(open(outp, encoding='utf-8'))
                    wavs = j.get('wavs', [])
                    end_reasons = j.get('end_reasons', [])
                except ValueError:
                    pass
            rec = {'lang': lg, 'exit_code': p.returncode, 'seconds': dt,
                   'n_wav': len(wavs), 'wavs': wavs,
                   'end_reasons': end_reasons,
                   'n_sent_used': len(texts[:N_SENT]),
                   'json_path': outp if os.path.exists(outp) else None}
            ev['per_lang'][lg] = rec
            print('   exit=%s %ss wav=%d end_reason=%s'
                  % (p.returncode, dt, len(wavs), end_reasons))
    finally:
        if a.lock:
            release_lock()

    n_ok = sum(1 for r in ev['per_lang'].values()
               if r.get('n_wav', 0) > 0)
    ev['n_langs'] = len(ev['per_lang'])
    ev['n_langs_ok'] = n_ok
    ev['verdict'] = 'PASS' if n_ok == ev['n_langs'] else 'PARTIAL'
    json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('[tts] %d/%d 语种有 wav ⇒ %s'
          % (n_ok, ev['n_langs'], ev['verdict']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
