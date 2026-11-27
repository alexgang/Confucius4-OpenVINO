"""APP-157: preserve the defective v1.2.1 zip (contains .bak_* + stale README) as an audit copy."""
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

ZIP = Path(r'C:\Users\Trekker-PTL\LiveCaption_MiniMVP_v1.2.1.zip')
DST = ZIP.with_name('LiveCaption_MiniMVP_v1.2.1.defective_20261127_1634.zip')
OUT = Path(r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_defective_zip_quarantine.json')
assert ZIP.exists() and not DST.exists()
st = ZIP.stat()
h = hashlib.sha256()
with ZIP.open('rb') as f:
    while True:
        b = f.read(1024 * 1024)
        if not b:
            break
        h.update(b)
ev = {'old': str(ZIP), 'bytes': st.st_size,
      'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
      'sha256': h.hexdigest(), 'reason': 'contains 8 *.bak_* and stale v1.2 README lag figures',
      'quarantined_to': str(DST),
      'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
shutil.move(str(ZIP), str(DST))
assert not ZIP.exists() and DST.exists()
OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(ev, ensure_ascii=False, indent=2))
