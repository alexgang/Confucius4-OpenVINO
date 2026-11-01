import hashlib, json, os, datetime, sys
p = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13.zip'
h = hashlib.sha256()
n = 0
with open(p,'rb') as f:
    while True:
        b = f.read(8*1024*1024)
        if not b: break
        h.update(b); n += len(b)
out = {'zip': p, 'bytes': n, 'sha256': h.hexdigest(),
       'mtime': datetime.datetime.fromtimestamp(os.stat(p).st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
       'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
open(r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app215_v113_zip_hash.json','w',encoding='utf-8').write(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps(out,ensure_ascii=False))
