"""APP-126 step 5: collect the e2e numbers into a single evidence json.

Sources:
  * shared/bgkeep/e2e8/<arm>/bgkeep_e2e.json  (our run, arms we executed)
  * shared/bgkeep/e2e7/<arm>/bgkeep_e2e.json  (reviewer's run, read-only)
  * shared/bgkeep/e2e8/<arm>/bridge.log        (clone-mode speaker check)

Per-arm口径 (APP-126 section 5):
  bg_blocks, bg_contiguous, bg_late_blocks, fallback_to_orig_s, dubs,
  dub_late_vs_play_s, dub_shift_msgs/applied, stats_bg.sep_rtf_p50/p90
plus: clip_s2 first dub shift_to ~ 14.7-14.8 s, and for clone_* the
speaker-segmentation fields (fp16-w5 loaded, no "segment inference failed",
speaker label count > 0).
"""
import json
import os
import re

E8 = r"C:\Users\Trekker-PTL\shared\bgkeep\e2e8"
E7 = r"C:\Users\Trekker-PTL\shared\bgkeep\e2e7"
OUT = r"C:\Users\Trekker-PTL\confucius4-openvino\results\app\app126_bgkeep_e2e8_evidence.json"

ARMS = ["clip_cs2", "clip_s1", "clip_s2", "clip_tuffy",
        "clone_s1", "clone_s2", "clone_cs2"]


def load(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        return {"__error__": "json load failed: %s" % e}


def pick(j, arm):
    if j is None:
        return {"status": "MISSING"}
    if "__error__" in j:
        return {"status": "ERROR", "detail": j["__error__"]}
    sb = j.get("stats_bg") or {}
    dlv = j.get("dub_late_vs_play_s") or {}
    out = {
        "status": "OK",
        "media": j.get("media"),
        "duration_s": j.get("duration_s"),
        "delay_sec": j.get("delay_sec"),
        "bg_blocks": j.get("bg_blocks"),
        "bg_contiguous": j.get("bg_contiguous"),
        "bg_covered_s": j.get("bg_covered_s"),
        "bg_late_blocks": j.get("bg_late_blocks"),
        "bg_late_at": j.get("bg_late_at"),
        "fallback_to_orig_s": j.get("fallback_to_orig_s"),
        "dubs": j.get("dubs"),
        "dub_late_vs_play_s": dlv,
        "dub_shift_msgs": j.get("dub_shift_msgs"),
        "dub_shift_applied": j.get("dub_shift_applied"),
        "bg_margin_min_s": j.get("bg_margin_min_s"),
        "bg_margin_p10_s": j.get("bg_margin_p10_s"),
        "bg_margin_median_s": j.get("bg_margin_median_s"),
        "sep_device": sb.get("sep_device"),
        "sep_rtf_p50": sb.get("sep_rtf_p50"),
        "sep_rtf_p90": sb.get("sep_rtf_p90"),
        "sep_compile_s": sb.get("sep_compile_s"),
        "bg_up_gaps": sb.get("bg_up_gaps"),
        "bg_blocks_sent": sb.get("bg_blocks_sent"),
        "bg_state": sb.get("bg_state"),
        "bg_lead_sec": sb.get("bg_lead_sec"),
        "bg_clone_from_vocals": sb.get("bg_clone_from_vocals"),
        "bg_clone_fallback_orig": sb.get("bg_clone_fallback_orig"),
        "bg_onset_shifted": sb.get("bg_onset_shifted"),
        "bg_onset_no_vocals": sb.get("bg_onset_no_vocals"),
        "bg_status_last": j.get("bg_status_last"),
    }
    # speaker-related fields inside stats_full
    sf = j.get("stats_full") or {}
    spk = {k: v for k, v in sf.items() if "spk" in str(k).lower() or "spk" in str(v).lower()}
    out["stats_full_spk_fields"] = spk
    # dub_items: first dub's shift_to (APP-126 wants ~14.7-14.8 s for clip_s2)
    items = j.get("dub_items") or []
    out["n_dub_items"] = len(items)
    if items:
        first = items[0]
        out["first_dub"] = {
            "k": first.get("k"),
            "t_start": first.get("t_start"),
            "shift_to": first.get("shift_to"),
            "voice": first.get("voice"),
        }
        shifts = [(it.get("k"), it.get("shift_to")) for it in items
                  if it.get("shift_to") is not None]
        out["n_items_with_shift_to"] = len(shifts)
        out["shift_to_list"] = shifts
    return out


def log_checks(logpath):
    if not os.path.exists(logpath):
        return {"status": "MISSING"}
    txt = open(logpath, encoding="utf-8", errors="replace").read()
    needles = {
        "seg_model_line": r"分段模型[^\n]*",
        "seg_infer_fail": r"分段推理失败[^\n]*",
        "shape_err": r"(形状|IR 输入长度|IR输入长度)[^\n]*",
        "fp16_w5": r"fp16-w5[^\n]*",
        "bg_start": r"背景分离器启动[^\n]*",
        "bg_keep": r"保留背景音[^\n]*",
    }
    res = {"log_bytes": len(txt.encode("utf-8"))}
    for k, pat in needles.items():
        hits = re.findall(pat, txt)
        res[k] = hits[:6]
        res[k + "_count"] = len(hits)
    # speaker label counts
    res["n_seg_lines"] = len(re.findall(r"^\[bridge .*\] 段 seg_", txt, re.M))
    res["n_spk_label_lines"] = len(re.findall(r"(spk|说话人)", txt))
    return res


out = {
    "generated_by": os.path.basename(__file__),
    "e8_our_run": {},
    "e7_reviewer_run_readonly": {},
    "clone_log_checks": {},
}

for arm in ARMS:
    out["e8_our_run"][arm] = pick(load(os.path.join(E8, arm, "bgkeep_e2e.json")), arm)
    out["clone_log_checks"][arm] = log_checks(os.path.join(E8, arm, "bridge.log"))

for arm in ["off", "on_gpu", "on_cpu", "clip_cs2", "clip_s1", "clip_s2", "clip_tuffy"]:
    out["e7_reviewer_run_readonly"][arm] = pick(
        load(os.path.join(E7, arm, "bgkeep_e2e.json")), arm)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

# ---- console summary (APP-126 section 5口径) -------------------------------
print("== e8 (our run) ==")
hdr = ("arm", "blocks", "contig", "late", "fallback_s", "dubs", "shift_msgs/applied",
       "rtf_p50", "rtf_p90", "device")
print("%-11s %6s %7s %5s %10s %5s %18s %8s %8s %6s" % hdr)
for arm in ARMS:
    d = out["e8_our_run"][arm]
    if d.get("status") != "OK":
        print("%-11s %s" % (arm, d.get("status")))
        continue
    print("%-11s %6s %7s %5s %10s %5s %18s %8s %8s %6s" % (
        arm, d["bg_blocks"], d["bg_contiguous"], d["bg_late_blocks"],
        d["fallback_to_orig_s"], d["dubs"],
        "%s/%s" % (d["dub_shift_msgs"], d["dub_shift_applied"]),
        d["sep_rtf_p50"], d["sep_rtf_p90"], d["sep_device"]))

print()
print("== clip_s2 first-dub shift_to (APP-126 wants ~14.7-14.8 s) ==")
d = out["e8_our_run"]["clip_s2"]
print("  first_dub =", json.dumps(d.get("first_dub"), ensure_ascii=False))
print("  shift_to list =", json.dumps(d.get("shift_to_list"), ensure_ascii=False))

print()
print("== clone mode: speaker segmentation checks ==")
for arm in ["clone_s1", "clone_s2", "clone_cs2"]:
    lc = out["clone_log_checks"][arm]
    sf = out["e8_our_run"][arm].get("stats_full_spk_fields", {})
    print("  %s: seg_model=%s | seg_infer_fail_count=%s | fp16_w5_count=%s | spk_fields=%s"
          % (arm, (lc.get("seg_model_line") or ["<none>"])[:1],
             lc.get("seg_infer_fail_count"), lc.get("fp16_w5_count"),
             json.dumps(sf, ensure_ascii=False)[:400]))

print()
print("== e7 (reviewer run, read-only) ==")
for arm, d in out["e7_reviewer_run_readonly"].items():
    if d.get("status") != "OK":
        print("  %-11s %s" % (arm, d.get("status")))
        continue
    print("  %-11s blocks=%s contig=%s late=%s fallback_s=%s dubs=%s rtf_p50=%s rtf_p90=%s dev=%s"
          % (arm, d["bg_blocks"], d["bg_contiguous"], d["bg_late_blocks"],
             d["fallback_to_orig_s"], d["dubs"], d["sep_rtf_p50"], d["sep_rtf_p90"],
             d["sep_device"]))

print()
print("OUT:", OUT, os.path.getsize(OUT), "bytes")
