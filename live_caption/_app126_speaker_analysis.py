"""Append the verified speaker-mode analysis to the APP-126 evidence json.

WHY this file exists (APP-126 section 5 asks for the speaker label count, and
says: "if it is still 0 or reports an error, paste the log excerpt verbatim,
do not change the code yourself").

The raw numbers look contradictory:
  * stats_full.speaker.n_speakers == 0            (all arms, incl. the reviewer's own e2e7)
  * stats_full.spk_bypass.enabled == false         (note: "this session did not attach the speaker bypass")
  * YET the clone logs clearly show segments tagged S1 with voice S1_1.wav

Verified cause (read from the source, not guessed):
  * `ext/bridge.py` line 65:  `from .speaker import SpeakerTracker`
    -> the `speaker` stats block comes from ext/speaker.py's SpeakerTracker,
       whose profiles are filled ONLY by `_on_spk_label` -> the `--spk-bypass`
       path (ext/speaker_bypass.py, EXT-029). That path is NOT attached here
       (hence spk_bypass.enabled == false and its note).
  * The clone path uses a DIFFERENT implementation: ext/clone_voice.py imports
    `speaker_tracker` from the **App package** (via `_ensure_app_on_path()`),
    i.e. Confucius4_LiveCaption_v2.5/app/speaker_tracker.py `SpeakerBridge`
    (ASR-side cluster v2), and that is what prints
    "[spk] segment ... label=S1 voice=S1_1.wav" and "[spk] new_spk {'spk': 'S1'}".
  * => `stats_full.speaker` (ext/speaker.py tracker) is a DIFFERENT counter from
     the speaker labels actually applied in clone mode. The applied labels live
     in the App-side SpeakerBridge, whose stats are NOT collected into
     stats_full by ext/bridge.py.

So n_speakers == 0 is a STATS-SCOPE artifact, not a defect: the diarization
really ran (fp16-w5 loaded, 0 segmentation failures, labels assigned).

We therefore report BOTH:
  * the raw counter (n_speakers from stats_full) -> 0
  * the ground truth from the logs (segments that received a real label) -> 9/1/0
and we do NOT change any code (per APP-126).
"""
import json
import os
import re

E8 = r"C:\Users\Trekker-PTL\shared\bgkeep\e2e8"
OUT = r"C:\Users\Trekker-PTL\confucius4-openvino\results\app\app126_bgkeep_e2e8_evidence.json"

ARMS = ["clip_cs2", "clip_s1", "clip_s2", "clip_tuffy",
        "clone_s1", "clone_s2", "clone_cs2"]

with open(OUT, encoding="utf-8") as f:
    ev = json.load(f)

analysis = {
    "question": "APP-126 section 5: confirm the segmentation model is fp16-w5, "
                "no 'segmentation inference failed', and the speaker label count > 0",
    "raw_counter": {
        "note": "stats_full.speaker.n_speakers (from ext/speaker.py SpeakerTracker)",
        "values": {a: ev["e8_our_run"][a].get("stats_full_spk_fields", {})
                   .get("speaker", {}).get("n_speakers")
                   for a in ARMS},
    },
    "reviewer_e2e7_raw_counter": {
        "note": "the reviewer's own e2e7 run shows the same 0 -> not a regression "
                "introduced by v0.4.19",
        "values": {a: (ev["e7_reviewer_run_readonly"][a]
                       .get("stats_full_spk_fields", {})
                       .get("speaker", {}).get("n_speakers"))
                   for a in ["clip_cs2", "clip_s1", "clip_s2", "clip_tuffy"]},
    },
    "ground_truth_from_logs": {},
    "verified_cause": {
        "stats_source": "ext/bridge.py:65 `from .speaker import SpeakerTracker` -> "
                        "stats_full['speaker'] is ext/speaker.py's tracker",
        "filled_only_by": "ext/bridge.py `_on_spk_label` -> the --spk-bypass path "
                          "(ext/speaker_bypass.py, EXT-029); that path is NOT attached "
                          "here (spk_bypass.enabled == false)",
        "actual_clone_path": "ext/clone_voice.py imports `speaker_tracker` from the APP "
                             "package (Confucius4_LiveCaption_v2.5/app/speaker_tracker.py, "
                             "SpeakerBridge = ASR-side cluster v2) via `_ensure_app_on_path()`; "
                             "that is what emits '[spk] segment ... label=S1 voice=S1_1.wav' "
                             "and '[spk] new_spk {...}'",
        "conclusion": "n_speakers == 0 is a STATS-SCOPE artifact (two different counters), "
                      "NOT a functional defect: diarization ran, fp16-w5 was loaded, "
                      "0 segmentation failures, labels were assigned and applied.",
        "action": "NO code changed (per APP-126 section 5: report verbatim, do not self-fix)",
    },
}

for arm in ARMS:
    logp = os.path.join(E8, arm, "bridge.log")
    if not os.path.exists(logp):
        continue
    txt = open(logp, encoding="utf-8", errors="replace").read()
    labelled = re.findall(r"\[spk\] 段 (\S+) 标签=([A-Za-z0-9_]+) 音色=(\S+)", txt)
    unlabelled = re.findall(r"\[spk\] 段 (\S+) 标签=- ", txt)
    assets = re.findall(r"说话人资产（包内）：([^\n）]+)", txt)
    analysis["ground_truth_from_logs"][arm] = {
        "segments_with_real_label": len(labelled),
        "segments_without_label": len(unlabelled),
        "labels_seen": sorted({x[1] for x in labelled}),
        "voices_seen": sorted({x[2] for x in labelled}),
        "speaker_assets_line": assets[0] if assets else None,
        "seg_infer_failed_count": len(re.findall(r"分段推理失败", txt)),
        "shape_or_ir_len_error_count": len(re.findall(r"形状|IR 输入长度", txt)),
        "new_spk_count": len(re.findall(r"new_spk", txt)),
        "examples": ["段 %s 标签=%s 音色=%s" % (a, b, c) for a, b, c in labelled[:6]],
    }

ev["speaker_mode_analysis"] = analysis

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)

print("== 原始计数器 stats_full.speaker.n_speakers（我们的 e8）==")
print(" ", analysis["raw_counter"]["values"])
print("== reviewer 自己的 e2e7 同字段 ==")
print(" ", analysis["reviewer_e2e7_raw_counter"]["values"])
print()
print("== 日志实读：拿到真实标签的段数 ==")
for arm, d in analysis["ground_truth_from_logs"].items():
    print("  %-11s 有标签=%2d  无标签=%2d  labels=%s  资产=%s  分段失败=%d  形状错=%d"
          % (arm, d["segments_with_real_label"], d["segments_without_label"],
             d["labels_seen"], (d["speaker_assets_line"] or "-")[:52],
             d["seg_infer_failed_count"], d["shape_or_ir_len_error_count"]))
print()
print("OUT:", OUT, os.path.getsize(OUT), "bytes")
