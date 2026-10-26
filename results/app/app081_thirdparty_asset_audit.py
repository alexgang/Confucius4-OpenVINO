import os
import re
import sys

root = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
spk = []
sci = []
wavs = []
for dp, dn, fn in os.walk(root):
    for f in fn:
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, root).replace(os.sep, '/')
        if 'babelvox/data/speakers' in rel:
            spk.append(rel)
        if re.search(r'scipy/.*/tests?/.*\.(wav|flac|ogg|mp3)$', rel, re.I):
            sci.append(rel)
        if f.lower().endswith('.wav'):
            wavs.append(rel)

print('散包目录 babelvox speakers:', len(spk))
for x in spk[:10]:
    print('   ', x)
print('散包目录 scipy 测试音频:', len(sci))
for x in sci[:10]:
    print('   ', x)
print('散包目录 全部 wav:', len(wavs))
for x in wavs[:40]:
    print('   ', x)
