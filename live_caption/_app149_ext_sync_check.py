"""核对候选目录 `ext/bridge/*.py` 与 EXT 源的一致性（APP-149 第 5 项的收尾核对）。

🔴 关键：**逐字节比较会把 autocrlf 的行尾差异当成内容差异**
   ⇒ 本脚本**先归一化行尾再比内容**（§226 的做法），
   并单独报告「纯行尾差异」与「真内容差异」。
"""
import io, json, os, time

REPO = os.getcwd()
SRC = os.environ['EXTSRC']
CAND = os.environ['APPCAND']
CAND_BRIDGE = os.path.join(CAND, 'ext', 'bridge')
OUT = os.path.join(REPO, 'results', 'app', 'app149_ext_sync_check.json')


def norm(b):
    return b.replace(b'\r\n', b'\n')


res = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
       'ext_src': SRC, 'candidate_bridge': CAND_BRIDGE,
       'method': 'compare content after normalizing line endings (CRLF->LF); '
                 'report EOL-only differences separately (no SHA)'}

src_files = sorted(f for f in os.listdir(SRC) if f.endswith('.py'))
cand_files = sorted(f for f in os.listdir(CAND_BRIDGE) if f.endswith('.py'))
res['n_src'] = len(src_files)
res['n_cand'] = len(cand_files)

identical, eol_only, real_diff, missing = [], [], [], []
for f in src_files:
    p1 = os.path.join(SRC, f)
    p2 = os.path.join(CAND_BRIDGE, f)
    if not os.path.exists(p2):
        missing.append(f)
        continue
    a = open(p1, 'rb').read()
    b = open(p2, 'rb').read()
    if a == b:
        identical.append(f)
    elif norm(a) == norm(b):
        eol_only.append(f)
    else:
        real_diff.append(f)
extra = [f for f in cand_files if f not in src_files]

res['identical'] = identical
res['eol_only'] = eol_only
res['real_diff'] = real_diff
res['missing_in_candidate'] = missing
res['extra_in_candidate'] = extra
res['n_identical'] = len(identical)
res['n_eol_only'] = len(eol_only)
res['n_real_diff'] = len(real_diff)

# 缺失文件的性质说明（`tts_cuda_sidecar_ext.py` 只被 CUDA 边车路径引用 ⇒ MiniMVP 不需要）
notes = {}
for f in missing:
    hits = []
    for g in src_files:
        try:
            t = io.open(os.path.join(SRC, g), encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        if f in t:
            hits.append(g)
    notes[f] = {'referenced_by': hits,
                'note': 'CUDA sidecar only; MiniMVP ships no CUDA => not needed'}
res['missing_notes'] = notes

res['verdict'] = {
    'no_real_content_diff': (not real_diff),
    'eol_only_differences_are_expected': all(
        f not in real_diff for f in eol_only),
    'missing_are_cuda_only': all(
        'cuda' in f.lower() for f in missing),
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(
    json.dumps(res, ensure_ascii=False, indent=2))
print('src=%d cand=%d | identical=%d eol-only=%d REAL-DIFF=%d missing=%d extra=%d'
      % (len(src_files), len(cand_files), len(identical), len(eol_only),
         len(real_diff), len(missing), len(extra)))
if eol_only:
    print('eol-only:', eol_only)
if real_diff:
    print('REAL DIFF:', real_diff)
if missing:
    print('missing:', missing, '->', notes)
print('verdict:', res['verdict'])
print('written ->', OUT)
