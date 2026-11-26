"""Download the LOCK-001 attachment (machine_lock.py.txt) straight to disk.

Reuses the credential/rpc helpers from app129_dl/_send.py so the base64 never
passes through a human (manual transcription is always wrong - 222/224).

Run with an interpreter that has `cryptography`:
    C:\\Users\\Trekker-PTL\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python

Writes: C:\\Users\\Trekker-PTL\\shared\\tools\\machine_lock.py
Checks : exact byte size, AST parses, sha256 printed for the STATUS record.
"""
import ast
import base64
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'app129_dl'))
import _send  # noqa: E402

MSG = 'msg_djwiubxX0MiOhxxIbtTN_j3QLwG7NZ4UQsnPA96DMypnuQ'
ATT = 'att_WkYwMDI2X2dmdk5KWk9NZFNZdUhXc0FfSH4yMjEw'
EXPECT_SIZE = 8831
OUT = r'C:\Users\Trekker-PTL\shared\tools\machine_lock.py'


def find_blob(r):
    """result.content[0].text -> JSON -> data.content (base64)."""
    try:
        inner = json.loads(r['result']['content'][0]['text'])
        v = inner.get('data', {}).get('content')
        if isinstance(v, str) and len(v) > 1000:
            return v
    except Exception as e:
        print('shape A failed:', repr(e))
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ('content', 'base64') and isinstance(v, str) and len(v) > 1000:
                    return v
                got = walk(v)
                if got:
                    return got
        elif isinstance(o, list):
            for v in o:
                got = walk(v)
                if got:
                    return got
        elif isinstance(o, str) and len(o) > 1000 and o.lstrip().startswith('{'):
            try:
                return walk(json.loads(o))
            except Exception:
                return None
        return None
    return walk(r)


def main():
    token = _send.decrypt_token()
    print('token ok len=%d' % len(token))
    try:
        r = _send.rpc(token, 'tools/call',
                      {'name': 'DownloadAttachment',
                       'arguments': {'message_id': MSG, 'attachment_id': ATT}}, 1)
    finally:
        _send.wipe(_send.TOKEN_FILE)
    if r.get('error'):
        print('ERR', json.dumps(r, ensure_ascii=False)[:800])
        return 2
    blob = find_blob(r)
    if not blob:
        print('NO base64 payload:', json.dumps(r, ensure_ascii=False)[:500])
        return 3
    raw = base64.b64decode(blob)
    print('decoded %d B (expect %d)' % (len(raw), EXPECT_SIZE))
    if len(raw) != EXPECT_SIZE:
        print('FAIL size mismatch -> 不写盘')
        return 4
    src = raw.decode('utf-8')
    ast.parse(src)                      # 语法自检，失败即中止
    if 'def main' not in src or 'MACHINE_LOCK' not in src:
        print('FAIL content sanity (no main/MACHINE_LOCK) -> 不写盘')
        return 5
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(raw)
    os.replace(tmp, OUT)
    print('WROTE', OUT)
    print('sha256=', hashlib.sha256(raw).hexdigest())
    print('sha1  =', hashlib.sha1(raw).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
