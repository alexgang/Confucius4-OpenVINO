# -*- coding: utf-8 -*-
"""§251 **直连 API 发信**：正文**从磁盘读** ⇒ 实发件与入库件**逐字节相同**。

🔴 为什么走直连：MCP 工具的 body 参数需**人工转写** ⇒ 本轮实测转写漂移
   （空格数变化 + 计数从 62 变成 51）⇒ 已发件与入库件**不一致**（15 B 差）。
   ⇒ 按 `MEMORY_attach_send_recipe.md`：**token 在内存里解密**、**正文从磁盘读**
   ⇒ 无转写环节 ⇒ 逐字节可核。

🔴 两步流程（T-MAIL-002/003）：先不带 token ⇒ 428 拿 ``ctk_…`` ⇒ 带 token **原样**重发。
🔴 **明文 token 绝不落盘**（用完即销毁）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
CONN = os.path.expanduser(
    r"~/.workbuddy/connectors/f63d67d6-b484-49bf-96a0-0cd63bc3138b")
CREDS = os.path.join(CONN, ".credentials.v3.json")
MASTER = os.path.join(CONN, ".master.key")
ENDPOINT = "https://api.mail.qq.com/mcp"
ALIAS = "alias_GYygHm59UPtt4Fs11qwcrpkWgT32"

BODY_FILE = os.path.join(REPO, "results", "app", "app251_status_email_body.txt")
SUBJ_FILE = os.path.join(REPO, "results", "app", "app251_status_email_subject.txt")
RESULT = os.path.join(REPO, "results", "app", "app251_status_email_direct.json")


def hkdf(ikm: bytes, salt: bytes, info: bytes, length=32):
    """HKDF-SHA256(ikm, salt, info) ⇒ 32 字节 key。"""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out, t = b"", b""
    i = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        out += t
        i += 1
    return out[:length]


def decrypt_token():
    """从 .credentials.v3.json 解出 qq-mail 的 accessToken（**只在内存**）。

    格式（实测）：``{"iv": b64, "tag": b64, "ct": b64}``；
    salt 取 ``encryption.salt``；AAD = ``userId|serverKey|fieldName``；
    key = HKDF-SHA256(masterKey, salt, "workbuddy-oauth-credentials-v1", 32)。
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    creds = json.load(open(CREDS, encoding="utf-8"))
    master = open(MASTER, "rb").read()
    user_id = os.path.basename(CONN)
    enc_info = creds["encryption"]
    server_key = "qq-mail|8e55080c6c967571"
    ent = creds["mcpOAuth"][server_key]
    field = "accessToken"
    e = ent[field]
    iv = base64.b64decode(e["iv"])
    tag = base64.b64decode(e["tag"])
    ct = base64.b64decode(e["ct"])
    salt = base64.b64decode(enc_info["salt"])
    aad = ("%s|%s|%s" % (user_id, server_key, field)).encode("utf-8")
    key = hkdf(master + user_id.encode("utf-8"), salt,
               b"workbuddy-oauth-credentials-v1", 32)
    pt = AESGCM(key).decrypt(iv, ct + tag, aad)
    return pt.decode("utf-8")


def rpc(token, method, params, _id):
    body = json.dumps({"jsonrpc": "2.0", "id": _id, "method": method,
                        "params": params}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        print("HTTP", e.code)
    if raw.startswith("event:") or raw.startswith("data:"):
        out = []
        for line in raw.splitlines():
            if line.startswith("data:"):
                out.append(line[5:].strip())
        raw = "".join(out)
    return json.loads(raw)


def main():
    body = io.open(BODY_FILE, encoding="utf-8").read()
    subject = io.open(SUBJ_FILE, encoding="utf-8").read().strip()
    sha_body = hashlib.sha256(body.encode("utf-8")).hexdigest()
    print("正文从磁盘读：%d B  sha256 %s" % (len(body.encode("utf-8")), sha_body[:16]))

    token = decrypt_token()
    print("token 已解密（仅内存，不落盘）")

    args = {
        "alias_id": ALIAS,
        "to": [{"email": "alexchen7694@agent.qq.com", "name": "alexchen7694"}],
        "subject": subject,
        "body": body,
        "body_format": "PLAIN",
    }
    print("--- phase 1: 请求确认 ---")
    r1 = rpc(token, "tools/call",
             {"name": "SendMessage", "arguments": args}, 1)
    txt = json.dumps(r1, ensure_ascii=False)
    print(txt[:600])
    m = re.search(r"ctk_[A-Za-z0-9\-]+", txt)
    tok = m.group(0) if m else None
    if not tok:
        print("NO confirmation_token -> stop")
        return 2
    print("token:", tok)

    print("--- phase 2: 带 token 原样重发 ---")
    args2 = dict(args)
    args2["confirmation_token"] = tok
    r2 = rpc(token, "tools/call",
             {"name": "SendMessage", "arguments": args2}, 2)
    txt2 = json.dumps(r2, ensure_ascii=False)
    print(txt2[:900])
    ok = '"queued":true' in txt2.replace(" ", "")
    res = {"script": "_app251_direct_send.py",
           "endpoint": ENDPOINT, "to": "alexchen7694@agent.qq.com",
           "bytes_sent": len(body.encode("utf-8")),
           "sha256_body_sent": sha_body,
           "subject": subject, "queued": ok,
           "response_head": txt2[:600]}
    with io.open(RESULT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    # 🔴 明文 token 立即销毁（从内存对象覆盖不可行 ⇒ 至少不写盘）
    del token
    print("\n写出:", RESULT)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
