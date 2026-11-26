import io, json, os, sys, time
REPO = os.getcwd()
CAND = os.environ['APPCAND']
OUT = os.path.join(REPO, 'results', 'app', 'app149_asr_load_check.json')
sys.path.insert(0, CAND)
sys.path.insert(0, os.path.join(CAND, 'app'))
res = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'candidate': CAND,
       'python': sys.executable}
import ext.bridge.engine_runtime as ER
res['engine_runtime_file'] = ER.__file__
res['asr_family'] = ER._asr_family()
res['asr_label'] = ER._asr_label(ER._asr_family())
print('engine_runtime:', ER.__file__)
print('_asr_family() =', res['asr_family'], '| label:', res['asr_label'])
LOGS = []
eng = ER.RuntimeEngine(target_lang='zh', asr_device='GPU.0', mt_device='GPU.0',
                        tts_device='NPU', on_log=lambda m: LOGS.append(str(m)))
t0 = time.time()
try:
    eng._load_asr()
    res['asr_loaded'] = True
    res['asr_load_sec'] = round(time.time() - t0, 1)
    res['backend_class'] = type(eng._asr_backend).__name__
    need = ['init_streaming_state', 'generate_with_prefix', 'tokenizer', 'name']
    res['missing_interface'] = [n for n in need if not hasattr(eng._asr_backend, n)]
    res['logs'] = LOGS
    print('ASR OK (%.1fs):' % res['asr_load_sec'], res['backend_class'])
    print('missing interface:', res['missing_interface'])
    for l in LOGS:
        print('  [log]', l[:160])
except Exception as e:
    import traceback; traceback.print_exc()
    res['asr_loaded'] = False
    res['error'] = '%s: %s' % (type(e).__name__, e)
    res['logs'] = LOGS
    print('ASR FAILED:', res['error'])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
print('written ->', OUT)
sys.exit(0 if res.get('asr_loaded') else 1)
