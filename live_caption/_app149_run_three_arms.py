"""APP-149 第 7 项 / APP-146 第 4 项：**三轮重跑**（EXT v0.4.23 ＋ 候选目录）。

🔴 与上一轮（v0.4.22）的差别：
* 候选目录现在是 **EXT v0.4.23**（ASR 支持 0.6B）⇒ 三轮**这次会有真实 ASR/MT/TTS 数据**；
* **TTS=NPU 档**（= MiniMVP 出厂默认）＋ MT=GPU.0（= 出厂默认）；
* 门禁（APP-150 §2）：**n_error 必须为 0**、`asr_segments`/`mt_segments`/`tts_segments`
  都 > 0 且与提交段数一致。

输出：`shared/bgkeep/e2e_app149/three_arms/<arm>/<arm>_1/`
"""
import json
import os
import subprocess
import sys
import time

REPO = os.getcwd()
ENVF = os.path.join(REPO, '.tmp_recover_app', 'env.sh')
for line in open(ENVF, encoding='utf-8'):
    line = line.strip()
    if line.startswith('export ') and '=' in line:
        k, v = line[7:].split('=', 1)
        os.environ[k] = v.strip('"')

CAND = os.environ['APPCAND']
DRIVER = os.environ['DRIVER']
MEDIA10 = os.environ['MEDIA10']
ROOT = os.path.join(os.environ['E2EROOT'], 'three_arms')
OUT = os.path.join(REPO, 'results', 'app', 'app149_three_arms.json')

ENV_NPU = 'EXT_TTS_DEVICE=NPU|EXT_MT_DEVICE=GPU.0'
ARMS = [
    ('bgkeep_off', ENV_NPU, True, 'A'),
    ('bgkeep_on', ENV_NPU, False, 'A'),
    ('bgkeep_on_clone', ENV_NPU, False, 'clone'),
]

results = []
for name, env_extra, bg_off, voice in ARMS:
    print('\n' + '=' * 70, flush=True)
    print('== arm %s  bg_off=%s voice=%s' % (name, bg_off, voice), flush=True)
    print('=' * 70, flush=True)
    cmd = [sys.executable, DRIVER, '--app', CAND,
           '--root', os.path.join(ROOT, name),
           '--arms', '%s:%s' % (name, env_extra),
           '--media', MEDIA10, '--drain-cap', '300', '--tail-wait', '30',
           '--voice', voice, '--lock-wait-s', '7000']
    if bg_off:
        cmd.append('--bg-off')
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    dt = round(time.time() - t0, 1)
    rec = {'arm': name, 'bg_off': bg_off, 'voice': voice,
           'rc': p.returncode, 'elapsed_s': dt, 'env': env_extra}
    jf = os.path.join(ROOT, name, name + '_1', 'bgkeep_e2e.json')
    if os.path.isfile(jf):
        j = json.load(open(jf, encoding='utf-8'))
        st = j.get('stats_full') or {}
        pl = st.get('pipeline') or {}
        dr = j.get('drain') or {}
        dl = j.get('dub_late_final_summary') or {}
        rec.update({
            'json': jf,
            'dubs': j.get('dubs'),
            'n_submitted': pl.get('n_submitted'),
            'n_emitted': pl.get('n_emitted'),
            'n_error': pl.get('n_error'),
            'n_pending': pl.get('n_pending'),
            'asr_segments': st.get('asr_segments'),
            'mt_segments': st.get('mt_segments'),
            'tts_segments': st.get('tts_segments'),
            'n_pending_at_media_end': dr.get('n_pending_at_media_end'),
            'n_pending_after_drain': dr.get('n_pending_after_drain'),
            'drained_to_zero': dr.get('drained_to_zero'),
            'drain_elapsed_sec': dr.get('drain_elapsed_sec'),
            'timing_valid': dr.get('timing_valid'),
            'stats_timeout_count': dr.get('stats_timeout_count'),
            'dub_late_max': dl.get('max'), 'dub_late_p90': dl.get('p90'),
            'synth_rtf': (j.get('synth_rtf') or {}).get('synth_rtf'),
            'n_segments_with_tts': (j.get('synth_rtf') or {}).get('n_segments_with_tts'),
            'peak_ws_mb': j.get('peak_ws_mb'),
            'clone_reasons': st.get('clone_reasons'),
            'bg_state': st.get('bg_state'),
            'speaker': st.get('speaker'),
        })
    else:
        rec['json'] = None
        rec['error'] = 'no bgkeep_e2e.json'
    logp = os.path.join(ROOT, name, name + '_1', 'bridge.log')
    errp = os.path.join(ROOT, name, name + '_1', 'bridge.err')
    for key, path in (('log_ready', logp), ('err_ready', errp)):
        hits = []
        if os.path.isfile(path):
            for l in open(path, encoding='utf-8', errors='replace'):
                if '就绪' in l or 'turbo 已生效' in l or 'NPU_TURBO=' in l:
                    hits.append(l.rstrip())
        rec[key] = hits[:40]
    evp = os.path.join(ROOT, name, '_lock_events.jsonl')
    if os.path.isfile(evp):
        rec['lock_events'] = [json.loads(l) for l in
                              open(evp, encoding='utf-8') if l.strip()]
    results.append(rec)
    print('== arm %s done rc=%s elapsed=%ss' % (name, p.returncode, dt), flush=True)
    print('   n_error=%s asr_seg=%s dubs=%s rtf=%s' % (
        rec.get('n_error'), rec.get('asr_segments'), rec.get('dubs'),
        rec.get('synth_rtf')), flush=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    json.dump({'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
               'candidate': CAND, 'media': MEDIA10,
               'media_duration_sec': 600, 'drain_cap_sec': 300,
               'arms': results}, f, ensure_ascii=False, indent=2)
print('\nwritten -> %s' % OUT)

# 门禁汇总
print('\n=== 门禁（APP-150 §2）===')
gate_ok = True
for r in results:
    ok = (r.get('n_error') == 0
          and (r.get('asr_segments') or 0) > 0
          and (r.get('mt_segments') or 0) > 0
          and (r.get('tts_segments') or 0) > 0
          and r.get('drained_to_zero') is True)
    r['gate_pass'] = ok
    gate_ok = gate_ok and ok
    print('  %-18s n_error=%-4s asr=%-5s mt=%-5s tts=%-5s drained=%-6s %s'
          % (r['arm'], r.get('n_error'), r.get('asr_segments'),
             r.get('mt_segments'), r.get('tts_segments'),
             r.get('drained_to_zero'), 'PASS' if ok else 'FAIL'))
with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    json.dump({'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
               'candidate': CAND, 'media': MEDIA10,
               'media_duration_sec': 600, 'drain_cap_sec': 300,
               'gate_all_pass': gate_ok, 'arms': results}, f,
              ensure_ascii=False, indent=2)
print('\n门禁总判定：%s' % ('PASS' if gate_ok else 'FAIL'))
