"""c080d_fp16_cleanie.py — C-080 判定：cleanie 说不出人话是**量化**还是**接线**。

c080a/b 已确立（不依赖任何未验证假设）：
  - 音频嵌入确实进入计算（置零后 logits 变化量 1324，cos 0.754）
  - prompt 结构正确：left 8 + audio 169 + right 5 = 182，与生产一致
  - 但 INT4 cleanie 的输出是垃圾，**而且 CPU 上同样是垃圾**
    （`language English\\nHuman 1\\n\\n`）

CPU 也坏 ⇒ **与 NPU / NPUW 无关**。剩下两种可能，一次实验分开：

  (a) 量化把 LM 打坏了  → FP16 cleanie 是人话，INT8/INT4 是垃圾
  (b) 接线/IR 形态错了  → FP16 cleanie 也是垃圾

(b) 若成立，C-079 的整套结论都要重估（它只验证过「两组不同 embedding 给出
不同输出」，从未验证过这个 IR 在真实 ASR prompt 上能否说出人话）。

做法：把 c079b 的图手术原样复制到 **FP16** 的 lastlogit IR 上，得到
`qwen3-lm-fp16sym-cleanie-ov`（同样的 4 端口、同样删 input_ids），
然后在 **CPU** 上喂同一份真实音频 inputs_embeds，贪心解码 16 步。

FP16 在 CPU 上跑 28 层 × 182 token，秒级，不需要 NPU 参与。

输出：reports/c080d_fp16_cleanie.json
"""
import json
import os
import shutil
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

WORK = os.path.dirname(os.path.abspath(__file__))
# FP16 对照源：`qwen3-lm-fp16-ov`（同样 4 端口：input_ids / attention_mask /
# position_ids / beam_idx）。
# ⚠️ `qwen3-lm-fp16-lastlogit-ov` 目录是空的（上一轮导出没落盘），所以这里用
# 全序列 logits 的 FP16 IR。代价是 prefill 慢（182×151936 的 lm_head），
# 但本实验只看**能不能说出人话**，不计时，所以无所谓。
SRC = 'qwen3-lm-fp16-ov'
DST = 'qwen3-lm-fp16-cleanie-ov'
OUT = 'reports/c080d_fp16_cleanie.json'
SR = 16000
START_SEC = 12 * 60
SEG_SEC = 13
N_STEPS = 16
MAX_TOK = 512
HIDDEN = 2048


def log(*a, **kw):
    print(*a, flush=kw.get('flush', True))


def build():
    """c079b 的图手术，原样应用到 FP16 IR。"""
    import openvino as ov
    from openvino import opset15 as ops

    core = ov.Core()
    src_xml = os.path.join(WORK, 'models', SRC, 'openvino_model.xml')
    if not os.path.exists(src_xml):
        return None, {'error': f'{SRC} 不存在，无法做 FP16 对照'}
    model = core.read_model(src_xml)
    g = None
    for n in model.get_ordered_ops():
        if n.get_type_name() == 'Gather' and 'embed_tokens' in n.get_friendly_name():
            g = n
            break
    if g is None:
        return None, {'error': 'embedding gather not found'}

    param = ops.parameter(ov.PartialShape([1, ov.Dimension(1, MAX_TOK), HIDDEN]),
                          ov.Type.f32)
    param.set_friendly_name('inputs_embeds')
    param.output(0).get_tensor().set_names({'inputs_embeds'})
    model.add_parameters([param])
    for u in list(g.output(0).get_target_inputs()):
        u.replace_source_output(param.output(0))

    removed = None
    for p in list(model.inputs):
        if p.get_any_name() != 'input_ids':
            continue
        users = [(u.get_node().get_type_name(), u.get_node().get_friendly_name())
                 for u in p.get_target_inputs()]
        for u in list(p.get_target_inputs()):
            u.replace_source_output(
                ops.constant(np.zeros(1, dtype=np.int64)).output(0))
        model.remove_parameter(p.get_node())
        removed = users
        break

    d = os.path.join(WORK, 'models', DST)
    os.makedirs(d, exist_ok=True)
    for fn in os.listdir(os.path.join(WORK, 'models', SRC)):
        if fn.startswith('openvino_model.'):
            continue
        sp = os.path.join(WORK, 'models', SRC, fn)
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(d, fn))
    ov.save_model(model, os.path.join(d, 'openvino_model.xml'))
    mm = core.read_model(os.path.join(d, 'openvino_model.xml'))
    info = {
        'src': SRC, 'dst': DST,
        'inputs': [(i.get_any_name(), str(i.get_partial_shape()),
                    str(i.get_element_type())) for i in mm.inputs],
        'outputs': [(o.get_any_name(), str(o.get_partial_shape()))
                    for o in mm.outputs],
        'size_mib': round(os.path.getsize(
            os.path.join(d, 'openvino_model.bin')) / 1048576, 1),
        'input_ids_consumers_before_removal': removed,
    }
    log('[c080d] 构建 %s: %s' % (DST, info['inputs']))
    log('[c080d] size=%.1f MiB' % info['size_mib'])
    return os.path.join(d, 'openvino_model.xml'), info


def decode_cpu(xml, emb, W, n_steps, tok):
    import openvino as ov
    cm = ov.Core().compile_model(xml, 'CPU', {})
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
    toks = [int(np.argmax(lg))]
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
    return toks, tok.decode(toks, skip_special_tokens=True)


def main():
    a, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if a.ndim > 1:
        a = a[:, 0]
    assert sr == SR
    a = a[SR * START_SEC:SR * (START_SEC + SEG_SEC)]

    rep = {'seg_start_sec': START_SEC, 'seg_dur_s': SEG_SEC}
    xml, info = build()
    rep['build'] = info
    if xml is None:
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        log('[c080d] 构建失败：%s' % info.get('error'))
        return 1

    from npu_embeds_backend import _load_embed_table
    from transformers import AutoTokenizer
    W = _load_embed_table()
    tok = AutoTokenizer.from_pretrained('models/ov-int8-past',
                                        fix_mistral_regex=True)

    # 真实音频 inputs_embeds（与 c080a/b 完全同一份构造）
    from npu_embeds_backend import NPUEmbedsDecoderBackend
    be = NPUEmbedsDecoderBackend(decoder_dir='models/qwen3-lm-int4sym-cleanie-ov')
    ehs, _, N_audio = be.encode_audio(a)
    emb = be.build_inputs_embeds(ehs, [])
    T = int(emb.shape[1])
    rep['n_audio'] = int(N_audio)
    rep['T'] = T
    log('[c080d] 真实音频 embeds: N_audio=%d T=%d' % (N_audio, T))
    del be

    # FP16 cleanie @CPU —— 决定性对照
    t0 = time.perf_counter()
    try:
        toks, txt = decode_cpu(xml, emb, W, N_STEPS, tok)
        rep['fp16_cleanie_cpu'] = {
            'tokens': toks, 'text': txt,
            'seconds': round(time.perf_counter() - t0, 1)}
        log('[c080d] FP16 cleanie @CPU tokens=%s' % toks)
        log('[c080d] FP16 cleanie @CPU TEXT =%r' % txt[:300])
    except Exception as e:
        rep['fp16_cleanie_cpu'] = {
            'error': f'{type(e).__name__}: {str(e)[:300]}'}
        log('[c080d] FP16 cleanie @CPU FAILED %s'
            % rep['fp16_cleanie_cpu']['error'])

    # 同时把 INT8/INT4 在 CPU 上再跑一遍（同一份 embeds），作为并列证据
    for tag, mdir in (('int8', 'models/qwen3-lm-int8sym-cleanie-ov'),
                      ('int4', 'models/qwen3-lm-int4sym-cleanie-ov')):
        x = os.path.join(WORK, mdir, 'openvino_model.xml')
        try:
            toks, txt = decode_cpu(x, emb, W, N_STEPS, tok)
            rep[f'{tag}_cleanie_cpu'] = {'tokens': toks, 'text': txt}
            log('[c080d] %s cleanie @CPU TEXT=%r' % (tag.upper(), txt[:200]))
        except Exception as e:
            rep[f'{tag}_cleanie_cpu'] = {
                'error': f'{type(e).__name__}: {str(e)[:200]}'}

    def human(s):
        if not s:
            return False
        return sum(c.isalpha() for c in s) >= 8 and len(s) >= 15

    fp = rep.get('fp16_cleanie_cpu', {})
    i8 = rep.get('int8_cleanie_cpu', {})
    i4 = rep.get('int4_cleanie_cpu', {})
    rep['verdict'] = {
        'fp16_human': human(fp.get('text', '')),
        'int8_human': human(i8.get('text', '')),
        'int4_human': human(i4.get('text', '')),
    }
    v = rep['verdict']
    if v['fp16_human'] and not v['int8_human'] and not v['int4_human']:
        rep['verdict']['conclusion'] = (
            '量化是根因：FP16 cleanie 能说人话，INT8/INT4 都是垃圾。'
            '→ cleanie 的端口/接线是对的，C-079 的结论保留；'
            '但现有 INT8/INT4 cleanie IR 精度不可用，端到端 WER 无法测。')
    elif not v['fp16_human']:
        rep['verdict']['conclusion'] = (
            '接线/IR 形态是根因：连 FP16 都是垃圾。'
            '→ C-079「cleanie 路线打通」只证明了端口生效，未证明这条'
            '形态能真正做 ASR；NPU 解码器路线需要重新评估。')
    else:
        rep['verdict']['conclusion'] = (
            'FP16/INT8/INT4 都是人话 → 之前 INT4 的垃圾来自别的变量'
            '（换 embeds 构造或 tokenize 路径），需要复核 c080a/b。')
    log('\n[c080d] VERDICT: %s' % rep['verdict']['conclusion'])

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
