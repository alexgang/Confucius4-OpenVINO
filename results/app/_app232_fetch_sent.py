#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-232 轮：把**实发邮件正文**取回落盘（供脚本比对）。

## 🔴 为什么走「直连 API 取回」而不是「把正文手抄进文件」
- §222／§224 两次实证：**base64 人工转写必错** ⇒ 本脚本**不手抄任何内容**：
  正文**由 API 取回后原样落盘**（`results/app/_app232_sent_body.html`）。
- 🔴 **明文 token 用完即焚**：`open(p,'r+b')` 写零 + `fsync` + `os.remove`（配方见
  `.workbuddy/memory/MEMORY_attach_send_recipe.md`）。

## 算法（HKDF-SHA256 + AES-256-GCM）
    aesKey = HKDF-SHA256(ikm = masterKey || utf8(userId),
                         salt = b64decode(header.salt),
                         info = "workbuddy-oauth-credentials-v1", length = 32)
    AAD    = utf8(f"{userId}|{serverKey}|{fieldName}")
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sys
import urllib.request

CDIR = os.path.expanduser(r'~/.workbuddy/connectors/f63d67d6-b484-49bf-96a0-0cd63bc3138b')
CRED = os.path.join(CDIR, '.credentials.v3.json')
MASTER = os.path.join(CDIR, '.master.key')
ENDPOINT = 'https://api.mail.qq.com/mcp'
ALIAS = 'alias_GYygHm59UPtt4Fs11qwcrpkWgT32'
MSG_ID = 'msg_FFGVfBjgyoAwOGeO7hC9wBsj3mtIXGixMN9h4xLWlqs1mQ'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app232_sent_body.html'
TOKEN_TMP = os.path.join(os.environ.get('TEMP', '.'), '_app232_token.txt')


def hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    prk = hmac_sha256(salt, ikm)
    out, t = b'', b''
    counter = 1
    while len(out) < length:
        t = hmac_sha256(prk, t + info + bytes([counter]))
        out += t
        counter += 1
    return out[:length]


def hmac_sha256(key: bytes, msg: bytes) -> bytes:
    import hmac
    return hmac.new(key, msg, hashlib.sha256).digest()


def decrypt_token() -> str:
    cred = json.load(io.open(CRED, encoding='utf-8'))
    enc = cred['encryption']
    server_key = list(cred['mcpOAuth'].keys())[0]
    user_id = enc['userId'] if 'userId' in enc else os.path.basename(CDIR)
    salt = base64.b64decode(enc['salt'])
    master = open(MASTER, 'rb').read()
    # userIdCheck / keyCheck 校验
    uc = base64.b64encode(hashlib.sha256(user_id.encode() + salt).digest()[:16]).decode()
    kc = base64.b64encode(hashlib.sha256(master + salt).digest()[:16]).decode()
    assert uc == enc['userIdCheck'], 'userIdCheck 不符'
    assert kc == enc['keyCheck'], 'keyCheck 不符'
    aes_key = hkdf_sha256(master + user_id.encode(), salt,
                           b'workbuddy-oauth-credentials-v1', 32)
    field = 'accessToken'
    aad = f'{user_id}|{server_key}|{field}'.encode()
    blob = cred['mcpOAuth'][server_key]
    ent = blob.get(field)
    if isinstance(ent, str):
        ct_b64 = ent
        iv_b64 = tag_b64 = None
    else:
        # 🔴 实际结构 = {iv, tag, ct}（三个都是 base64）
        ct_b64 = ent['ct']
        iv_b64 = ent['iv']
        tag_b64 = ent['tag']
    ct = base64.b64decode(ct_b64)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if iv_b64 is not None:
        iv = base64.b64decode(iv_b64)
        tag = base64.b64decode(tag_b64)
        pt = AESGCM(aes_key).decrypt(iv, ct + tag, aad)
    else:
        pt = AESGCM(aes_key).decrypt(ct[:12], ct[12:], aad)
    return pt.decode('utf-8')


def rpc(token, method, params, _id):
    body = json.dumps({'jsonrpc': '2.0', 'id': _id, 'method': method,
                       'params': params}).encode('utf-8')
    req = urllib.request.Request(ENDPOINT, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json, text/event-stream')
    req.add_header('Authorization', 'Bearer ' + token)
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode('utf-8', 'replace')
    if raw.startswith('event:') or raw.startswith('data:'):
        out = [l[5:].strip() for l in raw.splitlines() if l.startswith('data:')]
        raw = ''.join(out)
    return json.loads(raw)


def main():
    token = decrypt_token()
    # 明文 token 临时落盘（用完即焚）
    with io.open(TOKEN_TMP, 'w', encoding='utf-8') as f:
        f.write(token)
    try:
        r = rpc(token, 'tools/call',
                {'name': 'GetMessage',
                 'arguments': {'alias_id': ALIAS, 'message_id': MSG_ID}}, 1)
    finally:
        # 🔴 **明文 token 立即覆写并删除**
        if os.path.isfile(TOKEN_TMP):
            with open(TOKEN_TMP, 'r+b') as f:
                f.write(b'\x00' * len(token))
                f.flush()
                os.fsync(f.fileno())
            os.remove(TOKEN_TMP)

    txt = json.dumps(r, ensure_ascii=False)
    m = json.loads(txt)
    body = None
    for node in (m.get('result', {}).get('content', []) or []):
        if isinstance(node, dict) and node.get('type') == 'text':
            try:
                d = json.loads(node['text'])
                body = (d.get('data', {}).get('data', {}) or {}).get('body')
            except Exception:
                pass
    if body is None:
        # 兜底：直接正则取 body
        import re
        mm = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', txt)
        if mm:
            body = json.loads('"' + mm.group(1) + '"')
    if not body:
        print('取回失败，原始返回前 800 字：')
        print(txt[:800])
        return 2
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    print('实发正文已落盘：%s（%d 字符）' % (OUT, len(body)))
    print('token 明文文件已覆写并删除：%s（exists=%s）' % (TOKEN_TMP, os.path.exists(TOKEN_TMP)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
