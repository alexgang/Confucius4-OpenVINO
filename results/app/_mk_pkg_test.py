import io
import os

src = open('results/app/test_tts_drop_crash.py', encoding='utf-8').read()
old = "sys.path.insert(0, os.path.join(REPO, 'live_caption'))"
new = "sys.path.insert(0, r'C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.4\\app')"
assert src.count(old) == 1, src.count(old)
out = src.replace(old, new)
out = out.replace(
    'test_tts_drop_crash.py —— §29 的**验收 + 反证**脚本。',
    'test_tts_drop_crash_pkg.py —— §29 修复在**客户包内那份**上的独立验收。')
open('results/app/test_tts_drop_crash_pkg.py', 'w', encoding='utf-8').write(out)
print('written', os.path.getsize('results/app/test_tts_drop_crash_pkg.py'))
