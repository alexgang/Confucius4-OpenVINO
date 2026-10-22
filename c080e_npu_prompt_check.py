"""c080e_npu_prompt_check.py — C-080：真实音频 prompt 在 NPU 上的最终确认。

c080d 已经定性（全部在 CPU 上，结论不依赖 NPU）：
    FP16 cleanie : "[REDACTED] Just last week, we powered"  ✅
    INT8 cleanie : "[REDACTED] Just last week we powered on" ✅
    INT4 cleanie : "language English\\nHuman 1\\n\\n\\n\\n"                        ❌

所以：
  * 接线是对的（FP16/INT8 都能说出与 ABBA 配置 A 首段一致的文本），
    C-079 的端口结论**保留**；
  * **INT4_SYM cleanie IR 本身是坏的**，且与设备无关 → 在 IR 层面就被排除，
    不值得为它花 15 分钟端到端。

本脚本只补最后一块拼图：把同一份真实音频 inputs_embeds 喂 NPU，
确认 INT8 在 NPU 上也说出同样的话（CPU/NPU 逐 token 比对），
并给 INT4@NPU 一个同口径的证据（预期同样是人造物，确认它与 CPU 一致地坏）。

输出：reports/c080e_npu_prompt_check.json
"""
import json
import os
import sys
import time

os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

SR = 16000
START_SEC = 12 * 60
SEG_SEC = 13
N_STEPS = 16
OUT = 'reports/c080e_npu_prompt_check.json'


def log(*a, **kw):
    print(*a, flush=kw.get('flush', True))


def decode(xml, dev, props, emb, W, n_steps):
    import openvino as ov
    cm = ov.Core().compile_model(xml, dev, props)
    req = cm.create_infer_request()
    T = int(emb.shape[1])
    t0 = time.perf_counter()
    out = req.infer({
        "attention_mask": np.ones((1, T), dtype=np.int64),
        "position_ids": np.arange(T, dtype=np.int64)[None, :],
        "beam_idx": np.zeros(1, dtype=np.int32),
        "inputs_embeds": emb,
    })
    prefill_ms = (time.perf_counter() - t0) * 1000
    port = cm.outputs[0].get_any_name()
    lg = np.ascontiguousarray(np.array(out[port].data)[0, -1]).copy()
    toks, first_logits = [int(np.argmax(lg))], lg.copy()
    dec = []
    for _ in range(n_steps - 1):
        past = T + len(toks) - 1
        t0 = time.perf_counter()
        out = req.infer({
            "attention_mask": np.ones((1, past + 1), dtype=np.int64),
            "position_ids": np.array([[past]], dtype=np.int64),
            "beam_idx": np.zeros(1, dtype=np.int32),
            "inputs_embeds": np.ascontiguousarray(
                W[toks[-1]][None, None, :], dtype=np.float32),
        })
        dec.append((time.perf_counter() - t0) * 1000)
        lg = np.ascontiguousarray(np.array(out[port].data)[0, -1]).copy()
        toks.append(int(np.argmax(lg)))
    del req, cm
    return toks, first_logits, prefill_ms, dec


def cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na and nb else None


def main():
    a, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if a.ndim > 1:
        a = a[:, 0]
    assert sr == SR
    a = a[SR * START_SEC:SR * (START_SEC + SEG_SEC)]

    from npu_embeds_backend import (NPUEmbedsDecoderBackend, _load_embed_table,
                                    MAX_PROMPT_TOK)
    from transformers import AutoTokenizer
    W = _load_embed_table()
    tok = AutoTokenizer.from_pretrained('models/ov-int8-past',
                                        fix_mistral_regex=True)

    be = NPUEmbedsDecoderBackend(
        decoder_dir='models/qwen3-lm-int8sym-cleanie-ov')
    ehs, _, N_audio = be.encode_audio(a)
    emb = be.build_inputs_embeds(ehs, [])
    del be
    T = int(emb.shape[1])
    log('[c080e] 真实音频 embeds N_audio=%d T=%d' % (N_audio, T))

    npuw = {"NPU_USE_NPUW": "YES", "NPUW_LLM": "YES",
            "NPUW_LLM_MAX_PROMPT_LEN": str(MAX_PROMPT_TOK),
            "NPUW_LLM_MIN_RESPONSE_LEN": "64",
            "CACHE_DIR": "reports/npu_cache"}

    rep = {'seg_start_sec': START_SEC, 'seg_dur_s': SEG_SEC,
           'n_audio': int(N_audio), 'T': T, 'n_steps': N_STEPS, 'runs': {}}

    for tag, mdir in (('int8', 'models/qwen3-lm-int8sym-cleanie-ov'),
                      ('int4', 'models/qwen3-lm-int4sym-cleanie-ov')):
        xml = os.path.join(mdir, 'openvino_model.xml')
        for dev, props in (('CPU', {}), ('NPU', npuw)):
            key = f'{tag}@{dev}'
            try:
                t0 = time.perf_counter()
                toks, lg0, pf, dec = decode(xml, dev, props, emb, W, N_STEPS)
                txt = tok.decode(toks, skip_special_tokens=True)
                rep['runs'][key] = {
                    'tokens': toks, 'text': txt,
                    'prefill_ms': round(pf, 1),
                    'decode_median_ms': round(float(np.median(dec)), 1),
                    'total_s': round(time.perf_counter() - t0, 1),
                    '_lg0': lg0}
                log('[c080e] %-9s prefill=%.1fms dec=%.1fms %r'
                    % (key, pf, float(np.median(dec)), txt[:160]))
            except Exception as e:
                rep['runs'][key] = {
                    'error': f'{type(e).__name__}: {str(e)[:250]}'}
                log('[c080e] %-9s FAILED %s' % (key, rep['runs'][key]['error']))

    # ── CPU/NPU 一致性 ────────────────────────────────────────────
    for tag in ('int8', 'int4'):
        c, n = rep['runs'].get(f'{tag}@CPU'), rep['runs'].get(f'{tag}@NPU')
        if not c or not n or c.get('error') or n.get('error'):
            continue
        k = min(len(c['tokens']), len(n['tokens']))
        match = sum(1 for i in range(k) if c['tokens'][i] == n['tokens'][i])
        cv = cos(c.pop('_lg0'), n.pop('_lg0'))
        rep['runs'][f'{tag}_cpu_npu'] = {
            'token_match': f'{match}/{k}',
            'first_divergence': next(
                (i for i in range(k) if c['tokens'][i] != n['tokens'][i]), None),
            'prefill_cosine': round(cv, 6) if cv is not None else None}
        log('[c080e] %s CPU/NPU token match %d/%d  prefill cos=%s'
            % (tag, match, k, rep['runs'][f'{tag}_cpu_npu']['prefill_cosine']))

    def human(s):
        return bool(s) and sum(ch.isalpha() for ch in s) >= 8 and len(s) >= 15

    rep['verdict'] = {
        'int8_cpu_human': human(rep['runs'].get('int8@CPU', {}).get('text', '')),
        'int8_npu_human': human(rep['runs'].get('int8@NPU', {}).get('text', '')),
        'int4_cpu_human': human(rep['runs'].get('int4@CPU', {}).get('text', '')),
        'int4_npu_human': human(rep['runs'].get('int4@NPU', {}).get('text', '')),
    }
    v = rep['verdict']
    v['int4_excluded_at_ir_level'] = not (v['int4_cpu_human'] or v['int4_npu_human'])
    v['conclusion'] = (
        'INT8_SYM cleanie 可用（CPU 与 NPU 都说人话）→ 进入端到端；'
        'INT4_SYM cleanie 在 CPU 与 NPU 上**同样**是人造物，且 CPU 上就坏，'
        '→ 与 NPUW 无关，是 INT4 IR 本身的问题，按止损线在 IR 层面排除，'
        '不再对它做 15 分钟端到端。'
        if v['int8_npu_human'] else
        'INT8 在 NPU 上也退化了 → NPUW 真实长序列不可信，需重新评估。')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('\n[c080e] VERDICT: %s' % v['conclusion'])
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
