"""§226 独立复核：已发箱回执正文 == 入库正文文件（逐字节）。

用途：T-MAIL-003 §2＋历史截断教训（§224 的 11 KB 正文中间被截断 ⇒ reviewer 要补发）
⇒ 发完**必须**在已发箱 `GetMessage` 逐行核对，确认未截断。

用法：python live_caption/_app226_verify_mail.py <已发箱 body 原文的 txt 路径>
"""
import hashlib
import html
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCH = os.path.join(REPO, "live_caption", "_app226_email_body.txt")


def main():
    if len(sys.argv) < 2:
        print("usage: _app226_verify_mail.py <sent_body.txt>")
        return 2
    sent = open(sys.argv[1], encoding="utf-8").read()
    part = sent.split("---------- Original ----------")[0]
    m = re.search(r'<div style="white-space: pre-wrap; word-break: break-word;">(.*?)</div>',
                  part, re.S)
    if not m:
        print("FAIL: 未找到回复正文 div")
        return 1
    txt = m.group(1).replace("<br />", "\n").replace("<br/>", "\n")
    txt = html.unescape(txt)
    arch = open(ARCH, encoding="utf-8").read()

    print("archived  bytes:", len(arch.encode("utf-8")),
          "sha256:", hashlib.sha256(arch.encode("utf-8")).hexdigest())
    print("delivered bytes:", len(txt.encode("utf-8")),
          "sha256:", hashlib.sha256(txt.encode("utf-8")).hexdigest())
    same = txt == arch
    print("IDENTICAL       :", same)
    if not same:
        import difflib
        for l in list(difflib.unified_diff(arch.split("\n"), txt.split("\n"),
                                           "archived", "delivered", lineterm=""))[:40]:
            print(l)
        return 1
    lines = [x for x in txt.split("\n") if x.strip()]
    print("non-empty lines:", len(lines))
    print("first:", lines[0][:78])
    print("last :", lines[-1][:78])
    print("RESULT: PASS（未截断，入库 == 实发）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
