"""APP-157: move (never delete) all *.bak_* out of the v1.2.1 package into an audit dir."""
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

PKG = Path(r'C:\Users\Trekker-PTL\LiveCaption_MiniMVP_v1.2.1')
AUDIT = Path(r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_removed_bak')
OUT = Path(r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_removed_bak.json')

AUDIT.mkdir(parents=True, exist_ok=True)
baks = sorted(p for p in PKG.rglob('*') if p.is_file() and '.bak' in p.name.lower())
assert len(baks) == 8, f'unexpected bak count {len(baks)}'
items = []
for p in baks:
    rel = p.relative_to(PKG).as_posix()
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    st = p.stat()
    item = {'rel': rel, 'bytes': st.st_size,
            'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'sha256': h}
    dst = AUDIT / rel.replace('/', '__')
    assert not dst.exists(), f'dst exists: {dst}'
    shutil.move(str(p), str(dst))
    assert not p.exists(), f'move failed (source alive): {p}'
    item['audit_path'] = str(dst)
    items.append(item)
    print('MOVED', rel, '->', dst.name, flush=True)

left = [p.relative_to(PKG).as_posix() for p in PKG.rglob('*')
        if p.is_file() and '.bak' in p.name.lower()]
assert not left, f'still in package: {left}'
ev = {'pkg': str(PKG), 'audit_dir': str(AUDIT), 'n_moved': len(items),
      'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'items': items}
OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding='utf-8')
print('OK', len(items), 'moved; evidence', OUT)
