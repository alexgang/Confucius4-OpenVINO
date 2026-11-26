"""把 EXT v0.4.23 同步进候选目录（APP-149 第 5 项）。

要同步：
* `ext/bridge/engine_runtime.py`（v0.4.23：ASR 支持 0.6B）
* `ext/bridge/version.py`（0.4.23）
* `extension/manifest.json`（0.4.23）
* 候选目录 `release.json` 的 ext.version 也要改

🔴 纪律：写前备份；写后逐字节复核；**只同步这三个文件**（其余 ext/bridge 文件本轮没改）。
"""
import io
import json
import os
import shutil

EXT_SRC = os.environ['EXTSRC']
CAND = os.environ['APPCAND']
TAG = 'app149_v0423'

PAIRS = [
    (os.path.join(EXT_SRC, 'engine_runtime.py'),
     os.path.join(CAND, 'ext', 'bridge', 'engine_runtime.py')),
    (os.path.join(EXT_SRC, 'version.py'),
     os.path.join(CAND, 'ext', 'bridge', 'version.py')),
    (os.path.join(EXT_SRC, os.pardir, 'extension', 'manifest.json'),
     os.path.join(CAND, 'ext', 'extension', 'manifest.json')),
]

for src, dst in PAIRS:
    src = os.path.normpath(src)
    sb = open(src, 'rb').read()
    db = open(dst, 'rb').read() if os.path.exists(dst) else None
    if db == sb:
        print('  [同] %s' % os.path.basename(dst))
        continue
    bak = dst + '.bak_' + TAG
    if not os.path.exists(bak):
        shutil.copy2(dst, bak)
    tmp = dst + '.tmp_' + TAG
    with open(tmp, 'wb') as f:
        f.write(sb)
    os.replace(tmp, dst)
    assert open(dst, 'rb').read() == sb, '写后复核失败：%s' % dst
    print('  [更新] %-22s %d → %d B' % (os.path.basename(dst),
                                        len(db) if db else 0, len(sb)))

# release.json：ext.version → 0.4.23
rp = os.path.join(CAND, 'release.json')
rel = json.loads(open(rp, encoding='utf-8').read())
rel['ext']['version'] = '0.4.23'
rel['ext']['note'] = ('与完整版一致（EXT v0.4.23）：桥接 + 插件'
                      '（含「保留背景音」＋音色克隆）；'
                      'ASR 自动适配包内模型族（R2T2 / Qwen3-ASR 0.6B）')
rel['corrections'] = ['APP-137', 'APP-138', 'APP-139', 'APP-141',
                      'APP-144', 'APP-146', 'APP-147', 'APP-148',
                      'APP-149', 'APP-150', 'APP-151']
data = (json.dumps(rel, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
bak = rp + '.bak_' + TAG
if not os.path.exists(bak):
    shutil.copy2(rp, bak)
tmp = rp + '.tmp_' + TAG
with open(tmp, 'wb') as f:
    f.write(data)
os.replace(tmp, rp)
assert json.loads(open(rp, encoding='utf-8').read())['ext']['version'] == '0.4.23'
print('  [更新] release.json  ext.version -> 0.4.23')
print('OK')
