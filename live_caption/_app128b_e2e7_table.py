"""APP-128 补充（reviewer 2026-11-23 12:52:07Z 邮件）—— 从 reviewer 自己的 e2e7 产物里
读出三臂表（off / on_gpu / on_cpu），生成补发邮件正文 + 可复算的证据 json。

reviewer 指定的字段（邮件原文）：
    shared/bgkeep/e2e7/{off,on_gpu,on_cpu}/bgkeep_e2e.json
    -> dub_late_vs_play_s.max / p90 / n_late
    -> bg_late_blocks
    -> stats_bg.sep_rtf_p50 / sep_rtf_p90

纪律：
  * 只读 reviewer 产物，不改任何源文件（源在 shared/bgkeep/e2e7，不在仓库内）。
  * 每个数字都要能在**原始 JSON 文本**里逐字命中（独立交叉校验，不是只信解析结果）。
  * 正文由数据生成（不是手打数字）⇒ 邮件正文与证据 json 必然一致。
  * 幂等：重跑产物字节一致（除 mtime 外无时间戳字段）。
"""
import hashlib
import json
import os
import shutil
import time

E2E7 = os.path.join("C:\\", "Users", "Trekker-PTL", "shared", "bgkeep", "e2e7")
ARMS = ["off", "on_gpu", "on_cpu"]
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSON = os.path.join(REPO, "results", "app", "app128b_e2e7_table_evidence.json")
OUT_SRC = os.path.join(REPO, "results", "app", "app128b_e2e7_src")
OUT_BODY = os.path.join(REPO, "live_caption", "_app128b_email_body.txt")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def fmt(v):
    """把 JSON 里的数值格式化成正文里的字面量；None => 未开分离。"""
    if v is None:
        return None
    if isinstance(v, bool):
        raise TypeError("bool 不该出现在本表里")
    return repr(v) if isinstance(v, float) else str(v)


def extract(arm):
    p = os.path.join(E2E7, arm, "bgkeep_e2e.json")
    raw = open(p, "rb").read()
    text = raw.decode("utf-8")
    j = json.loads(text)
    dl = j["dub_late_vs_play_s"]
    sb = j["stats_bg"]
    row = {
        "arm": arm,
        "source_rel": "shared/bgkeep/e2e7/%s/bgkeep_e2e.json" % arm,
        "source_bytes": len(raw),
        "source_sha256": sha256_bytes(raw),
        "source_mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p))),
        "dubs": j["dubs"],
        "dub_late_max": dl["max"],
        "dub_late_p90": dl["p90"],
        "n_late": dl["n_late"],
        "bg_late_blocks": j["bg_late_blocks"],
        "sep_rtf_p50": sb["sep_rtf_p50"],
        "sep_rtf_p90": sb["sep_rtf_p90"],
        # 交叉信息（非表列，用于判定口径是否同源）
        "bg_state": sb["bg_state"],
        "bg_keep": sb["bg_keep"],
        "sep_device": sb["sep_device"],
        "n_speakers": j["stats_full"]["speaker"]["n_speakers"],
    }
    # 独立交叉校验：每个数值都必须在原始 JSON 文本里逐字出现
    checks = []
    for label, val in (
        ("dubs", row["dubs"]),
        ("dub_late_max", row["dub_late_max"]),
        ("dub_late_p90", row["dub_late_p90"]),
        ("n_late", row["n_late"]),
        ("bg_late_blocks", row["bg_late_blocks"]),
        ("sep_rtf_p50", row["sep_rtf_p50"]),
        ("sep_rtf_p90", row["sep_rtf_p90"]),
    ):
        if val is None:
            checks.append({"field": label, "value": None, "literal_in_raw": True,
                           "note": "未开分离，JSON 里是 null"})
            continue
        lit = fmt(val)
        ok = lit in text
        checks.append({"field": label, "value": val, "literal": lit, "literal_in_raw": ok})
    row["raw_text_crosscheck"] = checks
    row["_raw_text"] = text
    return row


def main():
    rows = [extract(a) for a in ARMS]
    for r in rows:
        bad = [c for c in r["raw_text_crosscheck"] if not c["literal_in_raw"]]
        if bad:
            raise SystemExit("交叉校验失败 %s: %r" % (r["arm"], bad))
        r.pop("_raw_text")

    # 复算底本入库：把 reviewer 的三份原始 json 复制进仓库（只读复制，不改源）
    os.makedirs(OUT_SRC, exist_ok=True)
    for a in ARMS:
        shutil.copyfile(os.path.join(E2E7, a, "bgkeep_e2e.json"),
                        os.path.join(OUT_SRC, "%s_bgkeep_e2e.json" % a))

    lines = []
    lines.append("| 臂 | dubs | dub_late max | dub_late p90 | n_late | bg_late_blocks | sep_rtf p50/p90 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        p50, p90 = r["sep_rtf_p50"], r["sep_rtf_p90"]
        if p50 is None and p90 is None:
            sep = "—（bg off，未分离）"
        else:
            sep = "%s / %s" % (fmt(p50), fmt(p90))
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["arm"], fmt(r["dubs"]), fmt(r["dub_late_max"]), fmt(r["dub_late_p90"]),
            fmt(r["n_late"]), fmt(r["bg_late_blocks"]), sep))
    lines.append("")
    lines.append("来源：shared/bgkeep/e2e7/{off,on_gpu,on_cpu}/bgkeep_e2e.json")
    lines.append("字段：dub_late_vs_play_s.max / p90 / n_late；bg_late_blocks；stats_bg.sep_rtf_p50 / sep_rtf_p90")
    body = "\n".join(lines)

    evidence = {
        "correction": "APP-128 补充（reviewer 2026-11-23 12:52:07Z 邮件：STATUS 正文被截断，请单独补发 e2e7 三臂表）",
        "mail_subject": "[C4][A][STATUS][APP] APP-128 e2e7 三臂表",
        "arms": rows,
        "email_body": body,
        "email_body_bytes": len(body.encode("utf-8")),
        "email_body_sha256": sha256_bytes(body.encode("utf-8")),
        "read_only": True,
        "notes": "数字全部来自 reviewer 自己的 e2e7 产物；每个值都在原始 JSON 文本里逐字命中（raw_text_crosscheck）。",
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
        f.write("\n")
    # 正文文件与邮件正文**逐字节相同**（不额外补换行）⇒ 「入库 == 实发」
    with open(OUT_BODY, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)

    print("=== EMAIL BODY ===")
    print(body)
    print("=== BODY BYTES ===", len(body.encode("utf-8")))
    print("=== BODY SHA256 ===", sha256_bytes(body.encode("utf-8")))
    for r in rows:
        print(r["arm"], "sha256", r["source_sha256"][:16], "bytes", r["source_bytes"],
              "mtime", r["source_mtime"])


if __name__ == "__main__":
    main()
