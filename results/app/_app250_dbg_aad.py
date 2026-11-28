# -*- coding: utf-8 -*-
"""调试 AAD：试多种组合 ⇒ 哪个能解出合法 token（能解 ⇒ 形态正确）。"""
import base64
import hashlib
import hmac
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CONN = os.path.expanduser(
    r"~/.workbuddy/connectors/f63d67d6-b484-49bf-96a0-0cd63bc3138b")
creds = json.load(open(os.path.join(CONN, ".credentials.v3.json"), encoding="utf-8"))
master = open(os.path.join(CONN, ".master.key"), "rb").read()
user_id = os.path.basename(CONN)
enc = creds["encryption"]
salt = base64.b64decode(enc["salt"])


def hkdf(ikm, salt, info, length=32):
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out, t = b"", b""
    i = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        out += t
        i += 1
    return out[:length]


key = hkdf(master + user_id.encode("utf-8"), salt,
           b"workbuddy-oauth-credentials-v1", 32)

server_key = "qq-mail|8e55080c6c967571"
for field in ("accessToken", "refreshToken"):
    e = creds["mcpOAuth"][server_key][field]
    iv = base64.b64decode(e["iv"])
    tag = base64.b64decode(e["tag"])
    ct = base64.b64decode(e["ct"])
    aads = [
        ("%s|%s|%s" % (user_id, server_key, field)),
        ("%s|%s|%s" % (user_id, "qq-mail", field)),
        ("%s|%s|%s" % (user_id, server_key, field)).lower(),
        ("%s|%s" % (server_key, field)),
        (field),
        ("%s|%s|%s" % (server_key, user_id, field)),
    ]
    for a in aads:
        try:
            pt = AESGCM(key).decrypt(iv, ct + tag, a.encode("utf-8"))
            print("✅ field=%s AAD=%r ⇒ 长度 %d 前 12: %s"
                  % (field, a, len(pt), pt[:12]))
        except Exception:
            pass
