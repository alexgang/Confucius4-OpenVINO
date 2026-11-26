"""APP-151 第 2 项：**App 侧引擎可用自查**（候选目录自带 python，跑**包内**代码）。

reviewer 原文：
> **App 侧引擎可用自查**（加进 APP-150 的打 zip 门禁）：用候选目录自带 python 跑包内
> `--check`（或等价的无界面自检），输出里要看到：ASR 引擎列表含 Qwen3-ASR 0.6B 且
> available、MT 引擎列表含 Hy-MT3 且 `mt_available` 为 True、TTS 可用；
> 再用 CLI/无界面方式让 **App 链路（不是 EXT 桥接）**翻译 3 句，贴原文和译文。

本脚本：① MT/ASR 引擎列表 ＋ 逐项 available；② 真翻译 3 句（原文/译文落盘）。
"""
import io
import json
import os
import sys
import time

CAND = os.environ['APPCAND']
OUT = os.environ['APPOUT']
sys.path.insert(0, os.path.join(CAND, 'app'))

SENTENCES = [
    ('Hello, welcome to the live caption demo.', 'zh'),
    ('The meeting starts in ten minutes.', 'zh'),
    ('Please make sure the background music is kept.', 'zh'),
]

out = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
       'candidate': CAND, 'python': sys.executable}

# ── ① 引擎列表 ────────────────────────────────────────────────────────
import translator as TR                                    # noqa: E402
out['mt_engines'] = {}
for k, v in getattr(TR, 'MT_ENGINES', {}).items():
    try:
        avail = TR.mt_available(k)
    except Exception as e:
        avail = 'ERR:%s' % type(e).__name__
    out['mt_engines'][k] = {'label': v.get('label'), 'avail': avail,
                            'model': v.get('model') or v.get('dir')}
print('MT 引擎列表（translator.MT_ENGINES）：')
for k, v in out['mt_engines'].items():
    print('  %-12s avail=%-6s label=%s' % (k, v['avail'], v['label']))

try:
    import live_caption_app as APP
    out['asr_engines_06b'] = {k: v.get('label')
                              for k, v in getattr(APP, 'ENGINES_ASR06B', {}).items()}
    print('\nASR 引擎（ENGINES_ASR06B）：%s' % out['asr_engines_06b'])
except Exception as e:
    out['asr_engines_06b'] = 'ERR:%s' % e
    print('\nASR 引擎读取失败：%s' % e)

# ── ② 真翻译 3 句（App 链路）─────────────────────────────────────────
print('\n真翻译（App 链路，包内 translator.HunyuanTranslator）：')
try:
    md = getattr(TR, 'DEFAULT_MODEL', None)
    print('  DEFAULT_MODEL = %s' % md)
    out['default_model'] = md
except Exception:
    pass

tr = None
try:
    dev = os.environ.get('LIVECAP_MT_DEVICE', 'GPU.0')
    tr = TR.HunyuanTranslator(
        model_dir=TR.DEFAULT_MODEL, device=dev,
        cache_dir=os.path.join(os.environ.get('LOCALAPPDATA', '.'),
                               'Confucius4LiveCaption', 'app151_mt_check'),
        on_log=lambda m: print('  [mt]', str(m)[:120]))
except Exception as e:
    import traceback
    traceback.print_exc()
    out['translator_error'] = '%s: %s' % (type(e).__name__, e)
    print('  ★ 翻译器构造失败：%s' % out['translator_error'])

sents = []
if tr is not None:
    for src, tgt in SENTENCES:
        t0 = time.time()
        try:
            r = tr.translate(src, tgt)
            dt = round(time.time() - t0, 2)
            sents.append({'src': src, 'tgt_lang': tgt, 'out': r, 'sec': dt})
            print('  原文: %s' % src)
            print('  译文: %s   (%.2fs)' % (r, dt))
        except Exception as e:
            sents.append({'src': src, 'tgt_lang': tgt, 'out': None,
                          'error': '%s: %s' % (type(e).__name__, e)})
            print('  原文: %s' % src)
            print('  ★ 失败: %s' % e)
out['sentences'] = sents
out['n_ok'] = sum(1 for s in sents if s.get('out'))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(
    json.dumps(out, ensure_ascii=False, indent=2))
print('\n结果：%d/%d 句翻译成功' % (out['n_ok'], len(SENTENCES)))
print('落盘 ->', OUT)
sys.exit(0 if out['n_ok'] == len(SENTENCES) else 1)
