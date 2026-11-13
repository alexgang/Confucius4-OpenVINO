# -*- coding: utf-8 -*-
r"""_app487 — **APP-102 §2.3 / APP-101 §3.2**：rc8 自带引擎上的 10 语种冒烟。

在 **rc8 包目录**上跑（用包内 python）：
* 每种目标语言 3 句：MT 出译文、TTS 出 wav，wav 落盘并列路径/时长；
* en→en 走原样透传（skipped=True 且逐字一致）；
* 记录 TTS 的 language 参数、撞帧数上限次数；
* `_patch_app_langs`（EXT v0.4.8）调用前后对 4 张语言表做快照，**新增键数须为 0**。

设备作业 ⇒ 持 MACHINE_LOCK；json 写 lock 的 module/pid/started/ended/timing_valid。
用法（必须用包内 python）：
    <rc8>/python/python.exe -s results/app/_app487_app102_10lang_smoke.py
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc11')
OUTROOT = os.path.join(HERE, 'app528_app107_rc11_10lang_smoke')
WAVDIR = os.path.join(OUTROOT, 'wav')
REPORT = os.path.join(HERE, 'app528_app107_rc11_10lang_smoke.json')
MAIN_SMOKE = os.path.join(HERE, 'app526_app107_rc11_acceptance.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

LANGS = ['zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'pt', 'it', 'ru']
SENTENCES = [
    'Welcome back to the show.',
    'Can you give us an example?',
    'It takes two minutes.',
]


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def acquire_lock(tag):
    payload = 'app %d %s %s' % (os.getpid(), now(), tag)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, payload.encode('utf-8'))
        os.close(fd)
        return payload
    except FileExistsError:
        return None


def release_own_lock(payload):
    try:
        if os.path.exists(LOCK) and open(LOCK, encoding='utf-8',
                                         errors='replace').read() == payload:
            os.remove(LOCK)
            return True
    except Exception:
        pass
    return False


def main():
    os.makedirs(WAVDIR, exist_ok=True)
    app_dir = os.path.join(PKG, 'app')
    sys.path.insert(0, app_dir)
    sys.path.insert(0, PKG)
    os.environ['EXT_APP_ROOT'] = PKG

    ev = {'at': now(), 'pkg': PKG, 'correction': 'APP-107 §2（10 语种冒烟，INT8-CW）',
          'langs': LANGS, 'n_sentences': len(SENTENCES),
          'lock': {'module': 'app', 'pid': os.getpid(),
                   'started': None, 'ended': None, 'timing_valid': False}}

    # ── ① 语言表快照 + EXT v0.4.8 的 _patch_app_langs ──
    import translator as tr
    import tts_engine as te

    def snap():
        return {
            'translator._LANG_NAME': dict(tr._LANG_NAME),
            'tts_engine.LANG_MAP': dict(te.LANG_MAP),
            'tts_engine.SUPPORTED_LANGS': list(te.SUPPORTED_LANGS),
            'tts_engine._SEC_PER_CHAR': dict(te._SEC_PER_CHAR),
        }

    before = snap()
    ext_info = {}
    try:
        import importlib
        er = importlib.import_module('ext.bridge.engine_runtime')
        er._patch_app_langs()
        ext_info = {'imported': True, 'module': er.__name__,
                    'app_root': getattr(er, 'APP_ROOT', None),
                    'app_dir': getattr(er, 'APP_DIR', None),
                    'patched_flag': getattr(er, '_APP_LANGS_PATCHED', None)}
    except Exception as e:
        ext_info = {'imported': False, 'error': repr(e)}
    after = snap()
    new_keys = {k: sorted(set(after[k]) - set(before[k]))
                for k in before}
    n_new = sum(len(v) for v in new_keys.values())
    ev['lang_table_snapshot'] = {
        'before': {k: sorted(before[k]) for k in before},
        'after': {k: sorted(after[k]) for k in after},
        'new_keys': new_keys, 'n_new_keys': n_new,
        'ext': ext_info,
    }
    ev['new_keys_zero'] = (n_new == 0 and ext_info.get('imported') is True)
    print('[lang] _patch_app_langs 新增键数 =', n_new,
          '| EXT import =', ext_info.get('imported'), flush=True)

    # ── ② 真跑 MT + TTS（持锁）──
    payload = acquire_lock('app107_rc11_10lang_smoke')
    if not payload:
        ev['verdict'] = 'SKIPPED_LOCK_BUSY'
        json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('🔴 MACHINE_LOCK 被占用 ⇒ 不跑设备作业')
        return 1
    ev['lock']['started'] = now()
    try:
        import numpy as np
        mt_dir = os.path.join(PKG, 'models', 'mt', 'mt2-int8sym-cw-q')   # 🔴 APP-107：rc11 只带 INT8
        t0 = time.time()
        mt = tr.HunyuanTranslator(model_dir=mt_dir, device='GPU.0',
                                  on_log=lambda *a: None)
        ev['mt'] = {'model_dir': mt_dir, 'device': 'GPU.0',
                    'load_s': round(getattr(mt, 'load_s', 0.0), 2)}
        eng = te.make_engine(device='GPU.0', on_log=lambda *a: None)
        ref = os.path.join(PKG, 'models', 'qwen3tts', 'voices', 'preset_A.wav')
        spk = te.speaker_embedding(eng, ref_wav=ref, on_log=lambda *a: None)
        ev['tts'] = {'device': 'GPU.0', 'ref_wav': ref,
                     'speaker_embed_shape': list(spk.shape) if spk is not None else None,
                     'load_s': round(time.time() - t0, 2)}
        print('[model] MT+TTS 就绪 %.1f s' % (time.time() - t0), flush=True)

        ev['rows'] = []
        cap_hits = 0
        for code in LANGS:
            blang = te.map_language(code)
            for i, src in enumerate(SENTENCES):
                row = {'lang': code, 'i': i, 'source': src,
                       'tts_language': blang}
                try:
                    r = mt.translate(src, code,
                                     src_hint='en' if code == 'en' else None)
                    out = (r.get('text') or '').strip()
                    row.update(mt_text=out, mt_skipped=bool(r.get('skipped')),
                               mt_nonempty=bool(out))
                    if code == 'en':
                        row['mt_expected'] = (r.get('skipped') is True
                                              and out == src)
                    else:
                        row['mt_expected'] = bool(out) and (out != src)
                except Exception as e:
                    row.update(mt_error=repr(e), mt_nonempty=False,
                               mt_expected=False)
                try:
                    chunks = []
                    sr = 24000
                    for w, s in te.stream(eng, row.get('mt_text') or src,
                                          language=blang,
                                          speaker_embed=spk,
                                          on_log=lambda *a: None):
                        chunks.append(np.asarray(w, dtype=np.float32).reshape(-1))
                        sr = int(s)
                    pcm = (np.concatenate(chunks) if chunks
                           else np.zeros(0, dtype=np.float32))
                    wp = os.path.join(WAVDIR, '%s_%d.wav' % (code, i))
                    with wave.open(wp, 'wb') as f:
                        f.setnchannels(1)
                        f.setsampwidth(2)
                        f.setframerate(sr)
                        f.writeframes(
                            (np.clip(pcm, -1, 1) * 32767).astype('<i2').tobytes())
                    reason = getattr(eng, '_last_end_reason', None)
                    if reason == 'cap':
                        cap_hits += 1
                    row.update(wav=wp, wav_bytes=os.path.getsize(wp),
                               wav_seconds=round(len(pcm) / max(sr, 1), 3),
                               n_chunks=len(chunks), end_reason=reason,
                               tts_ok=len(pcm) > 0)
                except Exception as e:
                    row.update(tts_error=repr(e), tts_ok=False, wav=None)
                ev['rows'].append(row)
                print('  [%s %d] mt=%s tts=%s %.2fs'
                      % (code, i, row.get('mt_expected'),
                         row.get('tts_ok'), row.get('wav_seconds') or 0),
                      flush=True)
        ev['n_cap_hits'] = cap_hits
    finally:
        ev['lock']['ended'] = now()
        ev['lock']['timing_valid'] = True
        ev['lock']['released'] = release_own_lock(payload)

    rows = ev.get('rows', [])
    n_mt = sum(1 for r in rows if r.get('mt_expected'))
    n_tts = sum(1 for r in rows if r.get('tts_ok'))
    ev['n_rows'] = len(rows)
    ev['n_mt_ok'] = n_mt
    ev['n_tts_ok'] = n_tts
    ev['verdict'] = ('PASS' if (len(rows) == 30 and n_mt == 30
                                and n_tts == 30 and ev['new_keys_zero'])
                     else 'PARTIAL')
    json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('[10lang] MT %d/30  TTS %d/30  新键 %d ⇒ %s'
          % (n_mt, n_tts, n_new, ev['verdict']), flush=True)

    # 合并进主冒烟证据（zip 闸门读 verdict）
    try:
        d = json.load(open(MAIN_SMOKE, encoding='utf-8'))
        d['lang_smoke'] = {'report': REPORT, 'verdict': ev['verdict'],
                           'n_mt_ok': n_mt, 'n_tts_ok': n_tts,
                           'n_new_keys': n_new, 'n_cap_hits': cap_hits}
        d['verdict'] = ('PASS' if (d.get('verdict') == 'PASS'
                                   and ev['verdict'] == 'PASS') else 'PARTIAL')
        json.dump(d, open(MAIN_SMOKE, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    except Exception as e:
        print('!! 合并主证据失败：%r' % e)
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
