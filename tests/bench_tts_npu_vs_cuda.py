"""11-06 reviewer bench: same Chinese sentences, TTS on NPU vs CUDA sidecar. Prints synth sec, audio sec, RTF."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ext.engine_runtime import RuntimeEngine
TEXTS = ["农民企业家们自己经营自己的事业，然后我们由大公司来建立这些社区。",
         "财富，不过我认为我们有可能做到这一点，我并不确定，但我觉得我们可以。",
         "尝试一下成本很低。如果不行，再试试别的办法。而且大部分时候，你会发现新的机会。",
         "借助一张纸或某个语言模型的帮助，你可以创造出各种类型的内容。",
         "要做的话，就是想办法去完成它。我认为几乎每个人都有一些需要处理的问题。"]
dev = sys.argv[1]
logs = []
eng = RuntimeEngine(target_lang="zh", tts_device=dev, on_log=lambda m: logs.append(str(m)))
t = time.perf_counter(); eng._load_tts(); load = time.perf_counter() - t
eng.tts("预热一下。", voice="A", target_lang="zh")
rows = []
for x in TEXTS:
    t = time.perf_counter(); pcm, sec = eng.tts(x, voice="A", target_lang="zh"); el = time.perf_counter() - t
    rows.append((round(el, 2), round(sec, 2), round(el / sec, 3) if sec else None))
tot_el = sum(r[0] for r in rows); tot_sec = sum(r[1] for r in rows)
print(json.dumps({"device_req": dev, "device_used": eng.tts_device, "load_s": round(load, 1), "rows": rows,
                  "total_synth_s": round(tot_el, 2), "total_audio_s": round(tot_sec, 2),
                  "rtf": round(tot_el / tot_sec, 3) if tot_sec else None,
                  "log_tail": [l[:160] for l in logs if "TTS" in l][-3:]}, ensure_ascii=False))
try:
    e = eng._tts_eng; (getattr(e, "close", None) or (lambda: None))()
except Exception: pass
