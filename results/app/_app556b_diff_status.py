import re, os
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
old = open(r'C:\Users\Trekker-PTL\AppData\Local\Temp\STATUS_APP.before_sec202.bak',
           encoding='utf-8').read()
new = open(os.path.join(REPO, 'status', 'app', 'STATUS_APP.md'),
           encoding='utf-8').read()


def blk_of(fname):
    t = open(os.path.join(REPO, 'status', 'archive', fname),
             encoding='utf-8').read()
    m = re.search(r'^---- 以下为.*原文，逐字 ----$', t, re.M)
    return t[m.end() + 1:].rstrip('\n')


for kind, fname in [('S200', 'STATUS_APP_sec200_20261114.md'),
                     ('S201', 'STATUS_APP_sec201_20261114.md'),
                     ('REC', 'STATUS_APP_recent_updates_20261114.md')]:
    blk = blk_of(fname)
    ptr = [l for l in new.split('\n')
           if ('status/archive/' + fname) in l and l.startswith('> ')][0]
    if kind.startswith('S'):
        title = blk.split('\n')[0]
        body = blk[len(title):].lstrip('\n')
        new = new.replace(title + '\n\n' + ptr, '\x00PH\x00', 1)
        new = new.replace('\x00PH\x00', title + '\n\n' + body, 1)
    else:
        new = new.replace(ptr, '\x00PH\x00', 1)
        new = new.replace('\x00PH\x00', blk, 1)

old_ack = re.search(r'^last_ack: APP-(\d+)$', old, re.M).group(1)
old_ts = re.search(r'^更新时间: (.*)$', old, re.M).group(1)
new = re.sub(r'^last_ack: APP-\d+$', 'last_ack: APP-' + old_ack, new, count=1,
             flags=re.M)
new = re.sub(r'^更新时间: .*$', '更新时间: ' + old_ts, new, count=1, flags=re.M)
new = '\n'.join([l for l in new.split('\n')
                 if not (l.startswith('> 🔴 2026-11-14 ')
                         and '执行 APP-108' in l)])
i = new.find('\n## §202 ')
if i >= 0:
    new = new[:i]
print('len old', len(old), 'len new', len(new))
for k in range(min(len(old), len(new))):
    if old[k] != new[k]:
        print('FIRST DIFF at', k)
        print('OLD:', repr(old[max(0, k - 120):k + 120]))
        print('NEW:', repr(new[max(0, k - 120):k + 120]))
        break
else:
    print('common prefix identical')
    print('old tail:', repr(old[len(new):][:400]))
    print('new tail:', repr(new[len(old):][:400]))
