"""APP §27 交付侧证据汇总（只读，不跑推理/测速，不改任何交付物）。"""
import hashlib, json, os, subprocess, zipfile, datetime

ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4.zip'
FTPCOPY = r'C:\Users\Trekker-PTL\FTP_Share\Confucius4_LiveCaption_v1.4.zip'
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app027_delivery_evidence.json'


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def stat(p):
    st = os.stat(p)
    return {'bytes': st.st_size, 'mtime': datetime.datetime.fromtimestamp(st.st_mtime).isoformat()}


res = {'generated_at': datetime.datetime.now().isoformat(timespec='seconds')}

res['zip_main'] = dict(path=ZIP, **stat(ZIP), sha256=sha256(ZIP))
res['zip_ftp_copy'] = dict(path=FTPCOPY, **stat(FTPCOPY), sha256=sha256(FTPCOPY))
res['zip_ftp_sha_match'] = res['zip_main']['sha256'] == res['zip_ftp_copy']['sha256']
res['zip_sizes_match'] = res['zip_main']['bytes'] == res['zip_ftp_copy']['bytes']

# zip 结构
with zipfile.ZipFile(ZIP) as z:
    names = z.namelist()
    res['zip_entries'] = len(names)
    res['zip_testzip_bad_entry'] = z.testzip()
    # EOCD 签名（独立于 zipfile 的第二判据）
    with open(ZIP, 'rb') as f:
        f.seek(max(0, res['zip_main']['bytes'] - 65536))
        tail = f.read()
    res['zip_eocd_signature_found'] = b'PK\x05\x06' in tail

# MANIFEST
mf = os.path.join(PKG, 'app', 'MANIFEST.json')
if not os.path.exists(mf):
    mf = os.path.join(PKG, 'MANIFEST.json')
res['manifest_path'] = mf
if os.path.exists(mf):
    m = json.load(open(mf, encoding='utf-8'))
    res['manifest_version'] = m.get('version')
    res['manifest_files'] = m.get('files')
    res['manifest_bytes'] = m.get('bytes')

# 内部素材 / 音频素材
spoken = []
audio = []
for root, dirs, files in os.walk(PKG):
    for fn in files:
        p = os.path.join(root, fn)
        rel = os.path.relpath(p, PKG)
        if '_spoken' in fn:
            spoken.append(rel)
        if fn.lower().endswith(('.wav', '.flac', '.mp3', '.m4a')):
            audio.append(rel)
res['spoken_files'] = spoken
res['audio_files_count'] = len(audio)
res['audio_files_non_testdata'] = sorted(
    a for a in audio
    if not a.replace('\\', '/').startswith('python/Lib/site-packages/')
)

# 音色目录
vd = os.path.join(PKG, 'models', 'qwen3tts', 'voices')
res['voices_dir'] = sorted(os.listdir(vd)) if os.path.isdir(vd) else None

# 关键文件 SHA256（仓库 ⇄ 包目录，归一化换行）
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino\live_caption'
KEY = ['translator.py', 'live_caption_app.py', 'tts_worker.py', 'tts_service.py']
cmp_res = {}
for f in KEY:
    a = os.path.join(REPO, f)
    b = os.path.join(PKG, 'app', f)
    if os.path.exists(a) and os.path.exists(b):
        na = open(a, 'rb').read().replace(b'\r\n', b'\n')
        nb = open(b, 'rb').read().replace(b'\r\n', b'\n')
        cmp_res[f] = {
            'repo_bytes': os.path.getsize(a),
            'pkg_bytes': os.path.getsize(b),
            'repo_norm_sha256': hashlib.sha256(na).hexdigest(),
            'pkg_norm_sha256': hashlib.sha256(nb).hexdigest(),
            'equal': na == nb,
        }
res['repo_vs_pkg_key_files'] = cmp_res
res['repo_vs_pkg_all_equal'] = all(v['equal'] for v in cmp_res.values())

# 客户包 README 关键标注
rm = os.path.join(PKG, 'README_zh.md')
if os.path.exists(rm):
    lines = open(rm, encoding='utf-8', errors='replace').read().splitlines()
    marks = {}
    for i, ln in enumerate(lines, 1):
        for key, needle in [('app008_guard_rel', 'LIVECAP_GUARD_REL'),
                            ('app008_pending_qc', '待质量复核'),
                            ('app010_experimental', '实验性功能'),
                            ('app010_default_off', '默认关闭')]:
            if needle in ln:
                marks.setdefault(key, []).append(i)
    res['readme_markers_lines'] = marks

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print(json.dumps(res, ensure_ascii=False, indent=2))
