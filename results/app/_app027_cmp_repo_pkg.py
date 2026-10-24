import hashlib, os, sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino\live_caption'
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4\app'
FILES = ['translator.py', 'live_caption_app.py', 'tts_worker.py', 'tts_service.py']


def norm(b):
    return b.replace(b'\r\n', b'\n')


for f in FILES:
    pa = os.path.join(REPO, f)
    pb = os.path.join(PKG, f)
    if not (os.path.exists(pa) and os.path.exists(pb)):
        print(f, 'MISSING', os.path.exists(pa), os.path.exists(pb))
        continue
    a = open(pa, 'rb').read()
    b = open(pb, 'rb').read()
    na, nb = norm(a), norm(b)
    print('%-20s raw_same=%-5s norm_same=%-5s repo=%d pkg=%d repo_sha=%s pkg_sha=%s' % (
        f, a == b, na == nb, len(a), len(b),
        hashlib.sha256(na).hexdigest()[:16], hashlib.sha256(nb).hexdigest()[:16]))
    if na != nb:
        la = na.split(b'\n')
        lb = nb.split(b'\n')
        print('   repo_lines=%d pkg_lines=%d' % (len(la), len(lb)))
        import difflib
        d = list(difflib.unified_diff(
            [x.decode('utf-8', 'replace') for x in lb],
            [x.decode('utf-8', 'replace') for x in la],
            fromfile='pkg', tofile='repo', n=1))
        for line in d[:80]:
            print('   ' + line)
