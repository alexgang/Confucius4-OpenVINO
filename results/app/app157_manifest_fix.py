"""APP-153 §5: MANIFEST n_files/bytes must match the package at zip time."""
import json
import os
import shutil
from pathlib import Path

PKG = Path(r'C:\Users\Trekker-PTL\LiveCaption_MiniMVP_v1.2.1')
MF = PKG / 'app' / 'MANIFEST.json'
BAKDIR = Path(r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_removed_bak')
BAK = BAKDIR / 'MANIFEST.json.bak_app157_counts'
TAG = '.tmp_app157_counts'

files = [p for p in PKG.rglob('*') if p.is_file()]
n_files = len(files)
n_bytes = sum(p.stat().st_size for p in files)
raw = MF.read_bytes()
d = json.loads(raw.decode('utf-8'))
old = (d['n_files'], d['bytes'])
assert old != (n_files, n_bytes), 'already correct'
d['n_files'], d['bytes'] = n_files, n_bytes
new_raw = (json.dumps(d, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
if not BAK.exists():
    shutil.copy2(MF, BAK)
tmp = MF.with_name(MF.name + TAG)
tmp.write_bytes(new_raw)
os.replace(tmp, MF)
assert MF.read_bytes() == new_raw
d2 = json.loads(MF.read_bytes().decode('utf-8'))
assert (d2['n_files'], d2['bytes']) == (n_files, n_bytes)
print('MANIFEST', old, '->', (n_files, n_bytes), 'bytes', len(raw), '->', len(new_raw))
