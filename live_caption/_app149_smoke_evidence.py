import io, json, os, time
REPO = os.getcwd()
ROOT = os.environ['E2EROOT']
d = os.path.join(ROOT, 'smoke', 'smoke_1')
jf = os.path.join(d, 'bgkeep_e2e.json')
j = json.load(open(jf, encoding='utf-8'))
st = j.get('stats_full') or {}
pl = st.get('pipeline') or {}
dr = j.get('drain') or {}
res = {
 'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
 'what': 'APP-149 item 6: 60 s smoke on the candidate package (EXT v0.4.23)',
 'candidate': os.environ['APPCAND'],
 'media': os.environ['MEDIA'],
 'bridge_log': os.path.join(d, 'bridge.log'),
 'bridge_err': os.path.join(d, 'bridge.err'),
 'json': jf,
 'gate': {
   'n_error_zero': pl.get('n_error') == 0,
   'asr_segments_gt_0': (st.get('asr_segments') or 0) > 0,
   'mt_segments_gt_0': (st.get('mt_segments') or 0) > 0,
   'tts_segments_gt_0': (st.get('tts_segments') or 0) > 0,
   'dubs_gt_0': (j.get('dubs') or 0) > 0,
 },
 'metrics': {
   'dubs': j.get('dubs'), 'n_submitted': pl.get('n_submitted'),
   'n_emitted': pl.get('n_emitted'), 'n_error': pl.get('n_error'),
   'n_pending': pl.get('n_pending'),
   'asr_segments': st.get('asr_segments'),
   'mt_segments': st.get('mt_segments'),
   'tts_segments': st.get('tts_segments'),
   'synth_rtf': (j.get('synth_rtf') or {}).get('synth_rtf'),
   'n_segments_with_tts': (j.get('synth_rtf') or {}).get('n_segments_with_tts'),
   'bg_state': st.get('bg_state'),
   'n_pending_at_media_end': dr.get('n_pending_at_media_end'),
   'n_pending_after_drain': dr.get('n_pending_after_drain'),
   'drained_to_zero': dr.get('drained_to_zero'),
   'drain_elapsed_sec': dr.get('drain_elapsed_sec'),
   'timing_valid': dr.get('timing_valid'),
 },
 'ready_lines': [],
 'turbo_lines': [],
 'note': 'The smoke used a 60 s clip with --drain-cap 120; the 3 pending segments '
         'at the end are because the drain window was short - the full three-arm '
         'run uses a 10 min clip with a 300 s drain cap (APP-149 item 7).',
}
for key, path in (('ready_lines', os.path.join(d, 'bridge.err')),
                  ('turbo_lines', os.path.join(d, 'bridge.err'))):
    if os.path.isfile(path):
        for l in open(path, encoding='utf-8', errors='replace'):
            if '就绪' in l and 'ASR' in l:
                res['ready_lines'].append(l.rstrip())
            elif '就绪' in l and 'MT' in l:
                res['ready_lines'].append(l.rstrip())
            elif 'turbo 已生效' in l or 'NPU_TURBO=' in l:
                res['turbo_lines'].append(l.rstrip())
res['gate_all_pass'] = all(res['gate'].values())
OUT = os.path.join(REPO, 'results', 'app', 'app149_smoke_60s.json')
os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
print('gate:', res['gate'], '=>', res['gate_all_pass'])
print('ready lines:')
for l in res['ready_lines'][:6]:
    print('  ', l[:150])
print('turbo lines: %d' % len(res['turbo_lines']))
print('written ->', OUT)
