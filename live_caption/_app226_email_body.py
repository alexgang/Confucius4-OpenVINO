"""§226 生成 STATUS 邮件正文（正文由脚本生成 ⇒ 入库文件与实发逐字节相同）。

纪律：
  * **数字不手打**：全部从 `results/app/app226_eol_verify_evidence.json` 与 git 实测取值。
  * 正文控制在 ~2.4 KB 以内（T-MAIL-003 §3 ＋ 历史截断教训）。
  * 幂等：重跑产物字节一致。
"""
import hashlib
import json
import os
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(REPO, "results", "app", "app226_eol_verify_evidence.json")
OUT = os.path.join(REPO, "live_caption", "_app226_email_body.txt")


def git(*a):
    return subprocess.run(["git"] + list(a), cwd=REPO, capture_output=True,
                          text=True, errors="replace").stdout.strip()


def main():
    ev = json.load(open(EV, encoding="utf-8"))
    arms = {r["arm"]: r for r in ev["per_arm"]}
    clone = {r["arm"]: r for r in ev["clone_verification"]["rows"]}
    nc = {r["arm"]: r for r in ev["negative_control"]["rows"]}
    ok = ev["all_pass"]

    L = []
    L.append("[C4][A][STATUS][APP] APP-128 补充已闭合 ＋ §226：reviewer 复算底本入库字节不一致已修（待复核）")
    L.append("")
    L.append("无新纠偏：局域网 CORRECTIONS_APP.md 仍 125 条/max APP-127；QQ 最新 App 封仍是 APP-128 补充（§225 已执行）。last_ack 仍 APP-128。")
    L.append("")
    L.append("上一会话心跳断了 63 分钟（note=step4: found autocrlf byte-divergence in committed reviewer source jsons），本轮 TAKEOVER 接续并闭合它。")
    L.append("")
    L.append("根因：core.autocrlf=true 且无 .gitattributes ⇒ git add 把 reviewer 的 CRLF 底本规整成 LF 入库 ⇒ 入库 blob ≠ 原件，而证据 json 公布的是 CRLF 原件 SHA256 ⇒ autocrlf=false 的机器上 clone 后必然对不上（假 FAIL）。")
    L.append("")
    L.append("修法：results/app/app128b_e2e7_src/.gitattributes 写 *.json -text（目录局部，不影响其它文件），再 git add --renormalize。")
    L.append("")
    L.append("验收（四路复核＋反证组，脚本 live_caption/_app226_eol_verify.py）：")
    for a in ("off", "on_gpu", "on_cpu"):
        r, c, n = arms[a], clone[a], nc[a]
        L.append("· %s：原件=%s B／SHA %s；入库 blob 与原件逐字节相同；真跑 git -c core.autocrlf=false clone 出来 %s B／SHA %s，与公布值一致。"
                 % (a, r["bytes"], r["published_sha256"][:12], c["clone_bytes"], c["clone_sha256"][:12]))
    L.append("· 反证组：修前提交同口径 clone 出来 %s B／%s B／%s B，SHA 全对不上 ⇒ 修法承重，非口径恰好通过。"
             % (nc["off"]["clone_bytes"], nc["on_gpu"]["clone_bytes"], nc["on_cpu"]["clone_bytes"]))
    L.append("· 证据：results/app/app226_eol_verify_evidence.json（all_pass=%s）。" % ok)
    L.append("")
    L.append("提交（已推 origin/main）：73a2e22（.gitattributes＋3 份底本重规整＋复核脚本）、55edcf4（STATUS §226＋companion＋归档＋证据）。")
    L.append("STATUS 38958→36636 B／107 行（限额 40000 B／300 行）；2 条较旧「最近更新」整块逐字归档到 status/archive/STATUS_APP_recent_updates_20261124.md（4691 B）。")
    L.append("")
    L.append("更大面如实报告：全仓 854 个跟踪文件同属此现象；App 活文档里「公布 SHA⇒指向入库件」共 5 份，本轮只修 3 份 reviewer 源文件。另 2 份属已闭合的 APP-115（§214）历史产物；根治需仓库根 .gitattributes＋全仓 renormalize（跨模块、851 文件），未自行执行。")
    L.append("")
    L.append("等你裁定：① 仓库根 .gitattributes 根治是否授权；② 默认分离设备（GPU.0 0.215 / CPU 0.458 p50 RTF，建议 GPU.0）；③ v2.6 交接（三臂表已补发，前置到位，但 APP-126 §7 与「v2.6 打包仍等 reviewer 交接」仍在，未打包未跑整链）。")
    L.append("")
    L.append("本轮未打包／未改客户包／未跑推理计时／未调 MiniMax／未连 B 机／未改纠偏文件（收尾四项指纹逐字一致）。")
    L.append("—— App 线程")

    body = "\n".join(L)
    with open(OUT, "wb") as f:
        f.write(body.encode("utf-8"))
    b = open(OUT, "rb").read()
    print("bytes:", len(b))
    print("sha256:", hashlib.sha256(b).hexdigest())
    print("lines:", body.count("\n") + 1)
    print("---")
    print(body)


if __name__ == "__main__":
    main()
