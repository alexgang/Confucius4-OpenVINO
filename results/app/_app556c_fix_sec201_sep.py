import os
import re

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BACKUP = (r'C:\Users\Trekker-PTL\AppData\Local\Temp'
          r'\STATUS_APP.before_sec202.bak')

new = open(STATUS, encoding='utf-8').read()
old = open(BACKUP, encoding='utf-8').read()


def sec(t, key):
    """返回 (标题行, 分隔符, 正文, 整块)。分隔符＝标题行之后的那个空行。"""
    idx = [(m.start(), m.group(0)) for m in re.finditer(r'^## .*$', t, re.M)]
    for i, (pos, title) in enumerate(idx):
        if title.startswith('## ' + key + ' '):
            end = idx[i + 1][0] if i + 1 < len(idx) else len(t)
            nl = t.index('\n', pos)
            title_line = t[pos:nl]
            raw = t[nl + 1:end].rstrip('\n')
            if raw.startswith('\n'):
                sep, body = '\n\n', raw[1:]
            else:
                sep, body = '\n', raw
            return title_line, sep, body, t[pos:end].rstrip('\n')
    raise RuntimeError(key)


fixed = new
for key in ('§200', '§201'):
    t_old, sep_old, _b_old, _blk_old = sec(old, key)
    t_new, sep_new, b_new, _blk_new = sec(fixed, key)
    if sep_old == sep_new:
        print('%-8s 分隔符一致（%r）⇒ 不动' % (key, sep_old))
        continue
    cur = t_new + sep_new + b_new
    want = t_new + sep_old + b_new
    if fixed.count(cur) != 1:
        raise RuntimeError('%s 命中 %d 次' % (key, fixed.count(cur)))
    fixed = fixed.replace(cur, want, 1)
    print('%-8s 分隔符 %r → %r（还原开工布局）' % (key, sep_new, sep_old))

if fixed != new:
    with open(STATUS, 'w', encoding='utf-8', newline='\n') as f:
        f.write(fixed)
    b = open(STATUS, 'rb').read()
    print('已改写：bytes=%d lines=%d CRLF=%d'
          % (len(b), b.count(b'\n'), b.count(b'\r\n')))
else:
    print('无需改写')
