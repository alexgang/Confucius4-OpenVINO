# -*- coding: utf-8 -*-
"""验证客户包的路径解析：全部相对包根目录，无任何开发机绝对路径。

检查点：
  1) 源码里不含任何硬编码的开发机路径
  2) MODELS 指向 <包根>/models
  3) 每个 ASR 后端的 enc/dec 都解析到**真实存在**的目录
  4) 解析出的目录里含 backend 真正会读的文件
  5) NPU 侧的 embed_tokens / tokenizer 也解析到位
  6) 翻译模型（translator.py）路径同样相对
"""
import os, sys, ast


def _latest_pkg_root():
    """自动发现最新的客户包目录（按版本号排序），避免每次升级改脚本。"""
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    cands = []
    for d in os.listdir(parent):
        if d.startswith('Confucius4_LiveCaption_v') and os.path.isdir(os.path.join(parent, d)):
            ver = d.rsplit('_v', 1)[-1]
            try:
                cands.append((tuple(int(x) for x in ver.split('.')), d))
            except ValueError:
                pass
    if not cands:
        raise SystemExit('找不到客户包目录')
    cands.sort()
    return os.path.join(parent, cands[-1][1])


PKG = _latest_pkg_root()
APP = os.path.join(PKG, 'app')

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + ('   ' + str(extra) if extra else ''))
    if not cond:
        fails.append(name)


# ① 源码无硬编码
BAD = ['Trekker-PTL', 'C:\\Users\\', 'C:/Users/', 'WorkBuddy\\Worktrees']
for fn in ('live_caption_app.py', 'translator.py', 'segment_encoder_backend.py',
           'backends.py', 'npu_embeds_backend.py', 'npu_delivery_backend.py',
           'streaming_asr.py', 'audio_source.py', 'seg_stream.py'):
    p = os.path.join(APP, fn)
    if not os.path.exists(p):
        continue
    src = open(p, encoding='utf-8').read()
    hit = [b for b in BAD if b in src]
    check(f'{fn} 无硬编码开发机路径', not hit, hit)

# ② 导入并检查 MODELS
sys.path.insert(0, APP)
import live_caption_app as A

check('MODELS 指向包根 models/',
      A.MODELS == os.path.join(A.PKG_ROOT, 'models'), A.MODELS)
check('PKG_ROOT 是包根目录', A.PKG_ROOT == PKG, A.PKG_ROOT)
check('MODELS 目录真实存在', os.path.isdir(A.MODELS))
check('MODELS 是绝对路径（由包根推导，非相对当前目录）',
      os.path.isabs(A.MODELS), A.MODELS)

# ③ 每个 ASR 后端路径可解析
print()
print('ASR 后端路径解析：')
for key, cfg in A.ENGINES.items():
    if cfg['kind'] == 'cuda':
        print(f'  {key:<12} (CUDA: 需要外部 audio.cpp，本包不带) '
              f'CUDA_CLI={"有" if A.CUDA_CLI and os.path.exists(A.CUDA_CLI) else "无"}')
        continue
    enc = A._model_path(cfg['enc'])
    dec = A._model_path(cfg['dec'])
    enc_ok = os.path.isdir(enc)
    dec_ok = os.path.isdir(dec)
    print(f'  {key:<12} enc={enc_ok and "OK" or "MISS"}  dec={dec_ok and "OK" or "MISS"}')
    print(f'               enc -> {enc}')
    print(f'               dec -> {dec}')
    check(f'{key} 的 enc 目录存在', enc_ok, enc)
    check(f'{key} 的 dec 目录存在', dec_ok, dec)

    # ④ 目录里含 backend 真正读的文件
    if cfg['kind'] == 'ov':
        check(f'{key} enc 含 openvino_encoder_model.xml',
              os.path.exists(os.path.join(enc, 'openvino_encoder_model.xml')))
        check(f'{key} dec 含 openvino_decoder_model.xml',
              os.path.exists(os.path.join(dec, 'openvino_decoder_model.xml')))
        check(f'{key} dec 含 tokenizer.json（AutoTokenizer 从这里读）',
              os.path.exists(os.path.join(dec, 'tokenizer.json')))
        check(f'{key} dec 含 chat_template.jinja',
              os.path.exists(os.path.join(dec, 'chat_template.jinja')))
        check(f'{key} dec 含 preprocessor_config.json（FeatureExtractor）',
              os.path.exists(os.path.join(dec, 'preprocessor_config.json')))
    else:
        check(f'{key} dec 含 openvino_model.xml',
              os.path.exists(os.path.join(dec, 'openvino_model.xml')))

# ⑤ NPU 侧附属资源
print()
npy = A._model_path('qwen3-lm-int8sym-cleanie-ov/embed_tokens_f16.npy')
check('NPU embed_tokens_f16.npy 解析到真实文件', os.path.isfile(npy), npy)
tok = A._model_path('ov-int8-past')
check('NPU tokenizer_dir 解析到真实目录', os.path.isdir(tok), tok)
check('NPU tokenizer_dir 含 tokenizer.json',
      os.path.exists(os.path.join(tok, 'tokenizer.json')))
check('NPU tokenizer_dir 含 chat_template.jinja',
      os.path.exists(os.path.join(tok, 'chat_template.jinja')))

# ⑥ 翻译模型（translator.py）
import translator as T
print()
print('翻译模型路径：')
for k, v in T.MT_ENGINES.items():
    m = v.get('model')
    if m is None:
        print(f'  {k:<14} (跟随默认)')
        continue
    ok = os.path.isdir(m)
    print(f'  {k:<14} {"OK  " if ok else "MISS"} {m}')
    check(f'翻译后端 {k} 模型目录存在', ok, m)
check('翻译 DEFAULT_MODEL 存在', os.path.isdir(T.DEFAULT_MODEL), T.DEFAULT_MODEL)

print()
print('=' * 64)
if fails:
    print('FAILED %d 项：' % len(fails))
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('ALL PASS')
