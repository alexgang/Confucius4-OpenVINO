#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app419_rc6_langs_summary.py —— **APP-098 三.4 汇总**：10 语种 MT + TTS 落盘 json。

## reviewer 三.4 原文
> **10 种语言**：每种 5 句做 MT，每种 2 句做 TTS，wav 落盘，原文和译文存成 json。
> 我会拉回去用 MiniMax 回转写。**目标机不调 MiniMax。**

## 本脚本**只做汇总**（不重跑设备）
* **原文**：英文 5 句（`results/app/app333_en_sents.json`，与 APP-097 同源）
* **译文**：每语种 `subtitles.mt.txt`（真实 App 链路跑出来的，**不是**原文）
  ⚠️ **坑**：`app415` 的 `summary.json` 里 `translations` 取的是 `subtitles.txt`
     ⇒ **那是原文** ⇒ 本脚本改取 `subtitles.mt.txt`。
* **wav**：`_app418_rc6_tts_direct`（APP-097 同款口径：`tts_engine.stream()`）
  的落盘路径 + 时长。

## 判据（每语种）
1. MT 译文**非空**且**行数 ≥ 1**
2. 译文**不等于原文**（逐行比对）⇒ 防「原样返回原文」
3. TTS wav **≥ 2 个**且**时长 > 0**
4. 译文语言**脚本判定**与目标语种一致（zh/ja/ko/ru 用文字系统；
   de/fr/es/pt/it/en 用拉丁字母 + 特征字符）⇒ 只作**参考**，不作硬判据
   （reviewer 拿 MiniMax 回转写做质量判定）

## 用法
```
.venv/Scripts/python.exe results/app/_app419_rc6_langs_summary.py
```
"""
from __future__ import annotations

import datetime
import json
import os
import re
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

LANGS_DIR = os.path.join(HERE, 'app415_rc6_langs')
TTS_DIR = os.path.join(HERE, 'app418_rc6_tts_direct')
SENTS = os.path.join(HERE, 'app333_en_sents.json')
REPORT = os.path.join(HERE, 'app419_rc6_langs_summary.json')
OUT_JSON = os.path.join(HERE, 'app419_rc6_langs_summary_payload.json')

LANGS = ('zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'pt', 'it', 'ru')

#: 每语种的**特征字符**（用于「译文语言」自检；只作参考）
SCRIPT_HINTS = {
    'zh': r'[一-鿿]',
    'ja': r'[぀-ヿ]',
    'ko': r'[가-힯]',
    'ru': r'[Ѐ-ӿ]',
    'de': r'[äöüß]',
    'fr': r'[àâçéèêëîïôùûœ]',
    'es': r'[áéíóúñ¿¡]',
    'pt': r'[ãõáéíóúç]',
    'it': r'[àèéìòù]',
    'en': r'[a-zA-Z]',
}


def wav_info(p):
    try:
        w = wave.open(p, 'rb')
        n = w.getnframes()
        sr = w.getframerate()
        w.close()
        return {'bytes': os.path.getsize(p), 'sr': sr,
                'samples': n, 'dur_s': round(n / sr, 3) if sr else 0.0}
    except Exception as e:
        return {'error': repr(e)}


def main():
    ev = {'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'correction': 'APP-098 三.4',
          'criterion': ('每语种：MT 译文非空且 != 原文；TTS wav ≥ 2 且时长 > 0；'
                        '译文语言自检（脚本/特征字符）'),
          'note': ('译文取自 `subtitles.mt.txt`（真实 App 链路）；'
                   '⚠️ `app415` 的 summary.json 里 translations 取的是 '
                   '`subtitles.txt`（= 原文）⇒ 此处更正'),
          'langs': {}, 'verdict': 'PENDING'}

    src = json.load(open(SENTS, encoding='utf-8'))
    src_texts = [x['text'] if isinstance(x, dict) else str(x) for x in src]
    ev['source_en_n'] = len(src_texts)
    ev['source_en_first5'] = src_texts[:5]

    payload = {'created_at': ev['created_at'], 'langs': {}}
    n_ok = 0
    for lg in LANGS:
        d = os.path.join(LANGS_DIR, lg)
        mt_path = os.path.join(d, 'subtitles.mt.txt')
        trans = []
        if os.path.isfile(mt_path):
            trans = [l.strip() for l in
                     open(mt_path, encoding='utf-8', errors='replace')
                     .read().splitlines() if l.strip()]
        same_as_src = sum(1 for t in trans if t in src_texts)

        # TTS wav
        td = os.path.join(TTS_DIR, lg)
        wavs = []
        if os.path.isdir(td):
            for f in sorted(os.listdir(td)):
                if f.lower().endswith('.wav'):
                    p = os.path.join(td, f)
                    wi = wav_info(p)
                    wi['path'] = p
                    wi['file'] = f
                    wavs.append(wi)

        # 语言自检
        hint = SCRIPT_HINTS.get(lg)
        n_hit = 0
        if hint:
            n_hit = sum(1 for t in trans if re.search(hint, t))

        rec = {
            'lang': lg,
            'n_source_sentences': 5,
            'source_en': src_texts[:5],
            'n_translations': len(trans),
            'translations': trans,
            'n_translation_same_as_source': same_as_src,
            'translation_script_hits': n_hit,
            'translation_script_hint': hint,
            'n_wavs': len(wavs),
            'wavs': wavs,
            'wav_total_dur_s': round(sum(w.get('dur_s', 0) for w in wavs), 3),
        }
        rec['ok'] = bool(trans) and len(trans) >= 1 and same_as_src == 0 \
            and len(wavs) >= 2 and all(w.get('dur_s', 0) > 0 for w in wavs)
        if rec['ok']:
            n_ok += 1
        ev['langs'][lg] = rec
        payload['langs'][lg] = rec

    ev['n_langs'] = len(LANGS)
    ev['n_langs_ok'] = n_ok
    ev['verdict'] = 'PASS' if n_ok == len(LANGS) else 'PARTIAL'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    for lg, r in ev['langs'].items():
        print('%-3s 译文 %d 条（与原文相同 %d）  wav %d（%.2f s）  脚本命中 %d  %s'
              % (lg, r['n_translations'], r['n_translation_same_as_source'],
                 r['n_wavs'], r['wav_total_dur_s'], r['translation_script_hits'],
                 'OK' if r['ok'] else '--'))
    print('[summary] %d/%d 语种 PASS ⇒ %s' % (n_ok, len(LANGS), ev['verdict']))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
