# -*- coding: utf-8 -*-
"""调试凭据解密：核对 userIdCheck / keyCheck ⇒ 确定 HKDF 的正确形态。"""
import base64
import hashlib
import hmac
import json
import os

CONN = os.path.expanduser(
    r"~/.workbuddy/connectors/f63d67d6-b484-49bf-96a0-0cd63bc3138b")
creds = json.load(open(os.path.join(CONN, ".credentials.v3.json"), encoding="utf-8"))
master = open(os.path.join(CONN, ".master.key"), "rb").read()
user_id = os.path.basename(CONN)
enc = creds["encryption"]
salt = base64.b64decode(enc["salt"])
print("user_id =", user_id)
print("master len =", len(master), "salt len =", len(salt))
print("userIdCheck =", enc["userIdCheck"], " keyCheck =", enc["keyCheck"])


def hkdf(ikm, salt, info, length=32):
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out, t = b"", b""
    i = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        out += t
        i += 1
    return out[:length]


# 配方：ikm = masterKey || utf8(userId)
ikm = master + user_id.encode("utf-8")
info = b"workbuddy-oauth-credentials-v1"
key = hkdf(ikm, salt, info, 32)

# 校验 1：userIdCheck = sha256(utf8(userId) || salt)[:16].b64
c1 = base64.b64encode(hashlib.sha256(user_id.encode("utf-8") + salt).digest()[:16]).decode()
print("userIdCheck 计算值 =", c1, "匹配" if c1 == enc["userIdCheck"] else "不匹配")
# 校验 2：keyCheck = sha256(masterKey || salt)[:16].b64
c2 = base64.b64encode(hashlib.sha256(master + salt).digest()[:16]).decode()
print("keyCheck   计算值 =", c2, "匹配" if c2 == enc["keyCheck"] else "不匹配")
print("key (hex) =", key.hex()[:32], "…")
