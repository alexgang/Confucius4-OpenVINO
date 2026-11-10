#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app326_mt_runner.py —— **APP-097 §2-2 MT 逐语种**（在**包内 python** 里跑）。

🔴 为什么单独一个 runner：MT 需要 `openvino_genai` + 包内模型 ⇒
只能在**影子包的 python** 里跑（开发树的 python 没有这些依赖）。

🔴 口径：**直接用 App 自己的 `translator` 模块**
（`HunyuanTranslator` ＝ `TranslationService` 的内核）⇒ 跑的是**真实代码路径**。

## 报什么（reviewer §2-2 明文）

* **输出语种是否正确**（每句标出**用什么判定的**）：
  * `src_by_script` ＝ `translator.detect_lang(text)`（**按文字系统**）
  * `src_hint`     ＝ **ASR 语种标签**（本素材无 ⇒ `None`）
  * `tgt`          ＝ 目标语言代号
  * `tgt_full`     ＝ `translator._LANG_NAME[tgt]`（**模型认的英文全称**）
  * `out_lang_by_script` ＝ 对**译文**再判一次（校验输出语种）
* **空译数**：译文 strip 后为空
* **"原样返回原文"数**：译文 == 原文（**逐字**，去首尾空白后）
* **平均延迟**：平均 `lat_ms`
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--app', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--en', required=True)
    ap.add_argument('--zh', required=True)
    ap.add_argument('--langs', required=True)
    ap.add_argument('--jsonl', default=None,
                    help='🔴 增量落盘路径（每句一行）⇒ 父进程被杀也不丢已跑结果')
    args = ap.parse_args()

    sys.path.insert(0, args.app)
    os.chdir(args.app)

    import translator as T

    en_sents = json.loads(args.en)
    zh_sents = json.loads(args.zh)
    langs = [x for x in args.langs.split(',') if x]

    # 🔴 源句可以是**纯字符串**，也可以是**带 src_dur_s 的字典**（§2-4 需源段时长）
    def _norm(x):
        if isinstance(x, dict):
            return (x.get('text') or '',
                    x.get('src_dur_s'),
                    x.get('src_file'),
                    x.get('src_line'))
        return (x or '', None, None, None)

    en_sents = [_norm(x) for x in en_sents]
    zh_sents = [_norm(x) for x in zh_sents]

    out = {'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'app': args.app,
           'mt_model_dir': None, 'device': 'GPU.0',
           'n_en': len(en_sents), 'n_zh': len(zh_sents),
           'langs': langs, 'rows': [], 'summary': {}}

    # 🔴 设备：MT 用 GPU.0（APP-002 默认：Hy-MT2 INT8-CW，设备 GPU.0）
    tr = T.HunyuanTranslator(device='GPU.0', on_log=lambda *a, **k: print(
        '[mt]', *a, flush=True))
    out['mt_model_dir'] = tr.model_dir
    print('[mt] model=%s load_s=%.1f' % (tr.model_dir, tr.load_s), flush=True)

    def one(text, tgt, src_label, src_dur_s=None, src_file=None, src_line=None):
        src_by_script = T.detect_lang(text)
        t0 = time.perf_counter()
        try:
            r = tr.translate(text, tgt)
            err = None
        except Exception as e:
            r = {'text': '', 'lat_ms': 0.0, 'ttft_ms': 0.0,
                 'n_in': 0, 'n_out': 0, 'skipped': False}
            err = '%s: %s' % (type(e).__name__, str(e)[:200])
        wall = (time.perf_counter() - t0) * 1000.0
        t = r.get('text') or ''
        stripped = t.strip()
        same = (stripped == (text or '').strip())
        return {
            'src_label': src_label,
            'src': text,
            'src_dur_s': src_dur_s,     # 🔴 英文源段时长（§2-4 的分母）
            'src_file': src_file,
            'src_line': src_line,
            'tgt': tgt,
            'tgt_full': T._LANG_NAME.get(tgt),
            'src_by_script': src_by_script,
            'src_hint': None,          # 🔴 本素材无 ASR 语种标签
            'out': t,
            'out_lang_by_script': T.detect_lang(stripped),
            'lat_ms': r.get('lat_ms'),
            'wall_ms': round(wall, 2),
            'ttft_ms': r.get('ttft_ms'),
            'n_in': r.get('n_in'),
            'n_out': r.get('n_out'),
            'skipped': bool(r.get('skipped')),
            'empty': (not stripped),
            'same_as_src': bool(same),
            'error': err,
        }

    # 🔴🔴 增量落盘：每句写一行 jsonl ⇒ 父进程被杀**不丢已跑结果**
    # （本轮实测：上一版把 stdout 全收进 pipe 且从不排空 ⇒ 子进程写满管道缓冲区后
    #   **永久阻塞** ⇒ 作业被外部清理时一行结果都没落盘）
    jf = None
    if args.jsonl:
        jf = open(args.jsonl, 'w', encoding='utf-8')

    for lang in langs:
        for i, (s, sd, sf, sl) in enumerate(en_sents):
            rec = one(s, lang, 'en', sd, sf, sl)
            out['rows'].append(rec)
            if jf:
                jf.write(json.dumps(rec, ensure_ascii=False) + '\n')
                jf.flush()
                os.fsync(jf.fileno())
            print('[mt] %s en#%d ok' % (lang, i), flush=True)
        for i, (s, sd, sf, sl) in enumerate(zh_sents):
            rec = one(s, lang, 'zh', sd, sf, sl)
            out['rows'].append(rec)
            if jf:
                jf.write(json.dumps(rec, ensure_ascii=False) + '\n')
                jf.flush()
                os.fsync(jf.fileno())
            print('[mt] %s zh#%d ok' % (lang, i), flush=True)
    if jf:
        jf.close()

    # ── 汇总（reviewer §2-2 要的 4 个数）──
    summary = {}
    for lang in langs:
        rows = [r for r in out['rows'] if r['tgt'] == lang]
        en = [r for r in rows if r['src_label'] == 'en']
        zh = [r for r in rows if r['src_label'] == 'zh']
        lats = [r['lat_ms'] for r in rows
                if isinstance(r.get('lat_ms'), (int, float))]
        # 🔴 「输出语种是否正确」：译文的脚本判定应与目标语言的**文字系统**一致
        #    （拉丁语系 de/fr/es/pt/it 彼此**不可分** ⇒ 对它们只判「是拉丁」）
        def out_ok(r):
            o = r['out_lang_by_script']
            if r['tgt'] == 'zh':
                return o == 'zh'
            if r['tgt'] == 'ru':
                return o == 'ru'
            if r['tgt'] in ('ja', 'ko'):
                return o == r['tgt']
            # 拉丁语系：目标 de/fr/es/pt/it/en ⇒ 译文必须是拉丁（非拉丁 ⇒ FAIL）
            return o == 'en' and not r['empty']
        summary[lang] = {
            'tgt_full': T._LANG_NAME.get(lang),
            'n': len(rows),
            'n_empty': sum(1 for r in rows if r['empty']),
            'n_same_as_src': sum(1 for r in rows if r['same_as_src']),
            'n_skipped': sum(1 for r in rows if r['skipped']),
            'n_error': sum(1 for r in rows if r['error']),
            'avg_lat_ms': (round(sum(lats) / len(lats), 1) if lats else None),
            'max_lat_ms': (round(max(lats), 1) if lats else None),
            'n_out_lang_ok': sum(1 for r in rows if out_ok(r)),
            'out_lang_ok_rate': (round(
                sum(1 for r in rows if out_ok(r)) / len(rows), 4)
                if rows else None),
            'n_empty_en': sum(1 for r in en if r['empty']),
            'n_same_en': sum(1 for r in en if r['same_as_src']),
            'n_empty_zh': sum(1 for r in zh if r['empty']),
            'n_same_zh': sum(1 for r in zh if r['same_as_src']),
            'zh_skipped_rate': (round(
                sum(1 for r in zh if r['skipped']) / len(zh), 4) if zh else None),
            '判定口径': 'src_by_script=translator.detect_lang(); '
                        'src_hint=None(本素材无ASR语种标签); '
                        'out_lang_by_script=对译文再判',
        }
    out['summary'] = summary

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[mt] wrote %s' % args.out, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
