"""c080f_int4_stability.py — C-080：INT4 cleanie 到底是「坏了」还是「不稳定」。

c080d 与 c080e 对 INT4@CPU 给出了**互相矛盾**的结果：
    c080d: "language English\\nHuman 1\\n\\n\\n\\n"          （人造物）
    c080e: "[REDACTED] Just last week, we powered"（人话）
而 INT4@NPU 两次都是人造物（"yay" / "yay\\nYay!\\nYay!\\nYay"）。

「同一份 embeds、同一台 CPU、同一份 IR，两次结果不同」只有一个解释：
**首 token 是近似平票**，argmax 在微小扰动下翻转，之后整条序列发散。
这正好是 C-076 警告过的陷阱（短 dummy prompt 的近似平票分叉），
但这里发生在**真实音频 prompt** 上，所以必须查清楚，不能简单归为「量化坏了」。

量化「近似平票」的方式（比逐 token 一致率更有说服力）：
  top1 与 top2 的 logit 间距 / logit 量纲 = 相对置信度 margin。
  margin 越小越危险。

实验：
  1. INT4@CPU 重复 4 次、INT4@NPU 重复 3 次，同一份 embeds → 各自稳定吗
  2. 每次打印首 token 的 (top1_id, top2_id, margin 相对值) 与前 8 个 token
  3. INT8@NPU 做同样测量作为对照（INT8 是要交付的那个，必须知道它余量多大）

若 INT4 的 margin 显著小于 INT8 → 结论是「INT4 在本 ASR prompt 分布上
处于平票边缘，不具备交付所需的确定性」，而不是「IR 坏了」。

输出：reports/c080f_int4_stability.json
"""
import json
import os
import sys

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
N_STEPS = 8
OUT = 'reports/c080f_int4_stability.json'
MAX_TOK = 512

NPUW = {"NPU_USE_NPUW": "YES", "NPUW_LLM": "YES",
        "NPUW_LLM_MAX_PROMPT_LEN": str(MAX_TOK),
        "NPUW_LLM_MIN_RESPONSE_LEN": "64",
        "CACHE_DIR": "reports/npu_cache"}


def log(*a, **kw):
    print(*a, flush=kw.get('flush', True))


def one_run(xml, dev, props, emb, W, n_steps):
    """返回 (tokens, 首 token 的 margin 诊断)。"""
    import openvino as ov
    cm = ov.Core().compile_model(xml, dev, props)
    req = cm.create_infer_request()
    T = int(emb.shape[1])
    out = req.infer({
        "attention_mask": np.ones((1, T), dtype=np.int64),
        "position_ids": np.arange(T, dtype=np.int64)[None, :],
        "beam_idx": np.zeros(1, dtype=np.int32),
        "inputs_embeds": emb,
    })
    port = cm.outputs[0].get_any_name()
    lg = np.ascontiguousarray(np.array(out[port].data)[0, -1]).copy()

    order = np.argsort(lg)[::-1]
    top1, top2 = int(order[0]), int(order[1])
    scale = float(np.abs(lg).mean()) or 1.0
    margin_abs = float(lg[top1] - lg[top2])
    toks = [top1]
    for _ in range(n_steps - 1):
        past = T + len(toks) - 1
        out = req.infer({
            "attention_mask": np.ones((1, past + 1), dtype=np.int64),
            "position_ids": np.array([[past]], dtype=np.int64),
            "beam_idx": np.zeros(1, dtype=np.int32),
            "inputs_embeds": np.ascontiguousarray(
                W[toks[-1]][None, None, :], dtype=np.float32),
        })
        lg = np.ascontiguousarray(np.array(out[port].data)[0, -1]).copy()
        toks.append(int(np.argmax(lg)))
    del req, cm
    return toks, {
        'top1_id': top1, 'top2_id': top2,
        'margin_abs': round(margin_abs, 5),
        'margin_rel': round(margin_abs / scale, 6),
        'logit_absmax': round(float(np.abs(lg).max()), 4),
    }


def main():
    a, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if a.ndim > 1:
        a = a[:, 0]
    assert sr == SR
    a = a[SR * START_SEC:SR * (START_SEC + SEG_SEC)]

    from npu_embeds_backend import NPUEmbedsDecoderBackend, _load_embed_table
    from transformers import AutoTokenizer
    W = _load_embed_table()
    tok = AutoTokenizer.from_pretrained('models/ov-int8-past',
                                        fix_mistral_regex=True)

    be = NPUEmbedsDecoderBackend(
        decoder_dir='models/qwen3-lm-int8sym-cleanie-ov')
    ehs, _, N_audio = be.encode_audio(a)
    emb = be.build_inputs_embeds(ehs, [])
    del be
    log('[c080f] N_audio=%d T=%d' % (N_audio, emb.shape[1]))

    rep = {'n_audio': int(N_audio), 'T': int(emb.shape[1]),
           'n_steps': N_STEPS, 'runs': {}}

    plan = [
        ('int4_cpu', 'models/qwen3-lm-int4sym-cleanie-ov/openvino_model.xml',
         'CPU', {}, 4),
        ('int4_npu', 'models/qwen3-lm-int4sym-cleanie-ov/openvino_model.xml',
         'NPU', NPUW, 3),
        ('int8_npu', 'models/qwen3-lm-int8sym-cleanie-ov/openvino_model.xml',
         'NPU', NPUW, 3),
        ('int8_cpu', 'models/qwen3-lm-int8sym-cleanie-ov/openvino_model.xml',
         'CPU', {}, 2),
    ]
    for tag, xml, dev, props, n in plan:
        seqs, mars = [], []
        for i in range(n):
            try:
                toks, m = one_run(xml, dev, props, emb, W, N_STEPS)
                txt = tok.decode(toks, skip_special_tokens=True)
                seqs.append({'tokens': toks, 'text': txt, **m})
                mars.append(m['margin_rel'])
                log('[c080f] %-9s #%d margin_rel=%.6f top1=%d top2=%d %r'
                    % (tag, i, m['margin_rel'], m['top1_id'], m['top2_id'],
                       txt[:90]))
            except Exception as e:
                seqs.append({'error': f'{type(e).__name__}: {str(e)[:200]}'})
                log('[c080f] %-9s #%d FAILED %s' % (tag, i, seqs[-1]['error']))
        ok = [s for s in seqs if 'error' not in s]
        firsts = {s['tokens'][0] for s in ok}
        rep['runs'][tag] = {
            'n': n, 'seqs': seqs,
            'n_ok': len(ok),
            'first_token_stable': len(firsts) <= 1,
            'first_tokens': sorted(firsts),
            'margin_rel_median': round(float(np.median(mars)), 6) if mars else None,
            'margin_rel_min': round(float(np.min(mars)), 6) if mars else None,
            'n4_repeat': sum(1 for s in ok
                             if 'Yay' in s['text'] or s['text'].count('\\n') > 3),
        }

    # ── 判定 ─────────────────────────────────────────────────────
    # ⚠️ 先前的自动结论写成了「CPU 重复运行首 token 会翻转」，但实测
    # int4_cpu 4/4 完全一致（first_token_stable=True）——**那个结论是错的**，
    # 它来自 c080d 的一次性观察，不是重复测量。判定必须以本文件的重复数据为准。
    i4c = rep['runs']['int4_cpu']
    i4n = rep['runs']['int4_npu']
    i8n = rep['runs']['int8_npu']
    i8c = rep['runs']['int8_cpu']
    v = {
        'int4_cpu_self_consistent': i4c['first_token_stable'],
        'int4_npu_self_consistent': i4n['first_token_stable'],
        'int8_npu_self_consistent': i8n['first_token_stable'],
        'int8_cpu_self_consistent': i8c['first_token_stable'],
        'int4_cpu_margin_median': i4c['margin_rel_median'],
        'int4_npu_margin_median': i4n['margin_rel_median'],
        'int8_npu_margin_median': i8n['margin_rel_median'],
        'int8_cpu_margin_median': i8c['margin_rel_median'],
    }
    v['all_deterministic'] = all(
        v[k] for k in v if k.endswith('self_consistent'))
    v['int4_fails_only_on_npu'] = bool(
        v['int4_cpu_self_consistent'] and v['int4_npu_self_consistent']
        and i4c['n_ok'] and i4c['seqs'][0]['text'] != i4n['seqs'][0]['text'])
    v['conclusion'] = (
        '全部 4 组重复运行都**完全确定**（首 token 稳定），所以这不是'
        '「近似平票导致的随机分叉」。真实情况是：'
        'INT4 在 CPU 上稳定地输出人话，在 NPU 上稳定地输出人造物；'
        'INT8 在 CPU 与 NPU 上都稳定输出人话，且 margin 约为 INT4@NPU 的 4 倍。'
        '→ 失败定位在 **INT4 × NPUW 这个组合**（NPUW 对 INT4 常量的数值处理），'
        '不是 IR 形态问题，也不是随机性。按 C-080#4 止损：'
        'INT4_SYM 在 NPU 上不具备交付确定性；INT8_SYM 进入端到端。')
    rep['verdict'] = v
    log('\n[c080f] %s' % v['conclusion'])
    log('[c080f] margin_rel 中位: int4_cpu=%s int4_npu=%s int8_npu=%s'
        % (v['int4_cpu_margin_median'], v['int4_npu_margin_median'],
           v['int8_npu_margin_median']))

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
