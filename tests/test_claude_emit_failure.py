"""11-06 (reviewer): one segment's emit raises => later segments must still be released (EXT-043 B1)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ext.pipeline import EnginePipeline, SegmentJob
def _ident(job): return job
def _emit(job):
    if job.index == 2: raise RuntimeError("injected emit failure")
    return {"index": job.index}
pipe = EnginePipeline(asr_fn=_ident, mt_fn=_ident, tts_fn=_ident, emit_fn=_emit)
import numpy as np
for i in range(6):
    pipe.submit(SegmentJob(index=i, seg_id=f"seg_{i}", t_start=float(i), t_end=float(i + 1),
                           audio=np.zeros(160, dtype=np.float32), orig_end=0.0, audio_complete_at=0.0))
out = pipe.wait_all(timeout=20.0); pipe.stop()
got = [t["index"] for t in out]
print("released:", got)
ok = got == [0, 1, 3, 4, 5]
print("RESULT:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
