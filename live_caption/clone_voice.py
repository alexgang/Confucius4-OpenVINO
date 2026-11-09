"""APP-086(2)：克隆说话人音色编排层（由 live_dub_ext claude-dev:ext/clone_voice.py 移植）。

移植口径：a 无标签不沿用上一句音色 / b 临时标签 / c 先出临时音色 /
d 整句 clean + ASR 文本走 ICL / e 参考冻结（最多一次升级）/ f 克隆工作移出 ASR 线程。
只读参考 EXT，不改 EXT 源码；App 适配仅 3 处：模块路径、音色落盘目录、本说明。

复用 v2.4 App 的同一套实现（只读引用 APP_DIR）：
  * speaker_tracker.SpeakerBridge —— ASR 侧说话人旁路（cluster v2），不阻塞定稿；
  * speaker_voice.SpeakerVoiceTable —— 按句绑定 spk、登记门槛（连续 ≥2.5 s、conf≥0.5）。
登记到的参考音频写成 wav（用户 11-08：克隆音色允许落盘），路径交给 TTS：
CUDA 边车用 set_ref_audio(path)，NPU 用 speaker x-vector。
标签/音色没到 ⇒ 返回 None ⇒ 调用方用预设 A（10-28 方案 A：TTS 不等说话人）。
"""
from __future__ import annotations

import os
import threading
import wave
from typing import Optional

import numpy as np

SR = 16000
KEEP_S = 90.0
REF_FIRST_S = 3.0      # first registration as soon as >= 3 s of clean labelled sentences
REF_UPGRADE_S = 8.0    # one upgrade when >= 8 s, then the reference is frozen


def _seg_int(seg_id) -> int:
    return int(str(seg_id).rsplit("_", 1)[-1])


class CloneVoices:
    def __init__(self, on_log=print):
        # APP-086(2): App dev 树里 speaker_tracker / speaker_voice 与本模块同目录，
        # 不需要 EXT 的 engine_runtime 路径引导（EXT 源码只读参考，未改）。
        import sys as _sys
        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in _sys.path:
            _sys.path.insert(0, _here)
        import speaker_tracker
        import speaker_voice
        self._log = on_log
        self.sv = speaker_voice
        self.br = speaker_tracker.SpeakerBridge(
            on_log=lambda m: on_log("[spk] %s" % m), enabled=True)
        self.tab = speaker_voice.SpeakerVoiceTable(
            on_event=lambda k, p: on_log("[spk] %s %s" % (k, p)))
        self._lock = threading.Lock()
        self._pump_lock = threading.Lock()
        self._buf = np.zeros(0, dtype=np.float32)
        self._buf_t0 = 0.0
        self._spks = set()
        self._reg_key = {}
        self.paths = {}
        self._latest = None
        self._span = {}
        self._reasons = {}
        self._seg_pcm = {}       # seg -> (pcm16k float32, ASR text), last 80 sentences
        self._cands = {}         # spk -> [(seg, dur, pcm, text)] reference-quality sentences
        self._ref_dur = {}
        self._upgraded = {}
        # APP-086(4): 克隆音色一律不进客户包 ⇒ 只落开发机用户目录（包外）。
        self.dir = os.path.join(os.environ.get("LIVECAP_CLONE_VOICES_DIR")
                                or os.environ.get("LOCALAPPDATA", "."),
                                "Confucius4LiveCaption", "clone_voices")
        os.makedirs(self.dir, exist_ok=True)
        self.n_reg = 0
        try:
            self.br.ensure_started()
        except Exception as e:
            on_log("[spk] 旁路启动失败（克隆回落预设 A）：%s" % e)
        # 11-08 test 5: all clone work on its own thread (never in the ASR stage / GPU lock)
        import queue as _queue
        self._q = _queue.Queue()
        self._unlabelled = {}          # seg -> time.monotonic() when finalized by ASR
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._worker, name="clone-voices", daemon=True)
        self._th.start()

    # ── ASR 线程：每段定稿后调用 ──────────────────────────────
    def on_segment(self, seg_id, audio, t_start: float, t_end: float, text: str = "") -> None:
        a = np.asarray(audio)
        if a.dtype == np.int16:
            a = a.astype(np.float32) / 32768.0
        a = a.astype(np.float32).reshape(-1)
        with self._lock:
            self._buf = np.concatenate((self._buf, a))[-int(KEEP_S * SR):]
            self._buf_t0 = float(t_end) - self._buf.size / float(SR)
        self._q.put((_seg_int(seg_id), a, float(t_start), float(t_end), str(text or "")))

    def _worker(self) -> None:
        import queue as _queue, time as _t
        while not self._stop.is_set():
            try:
                seg, a, t_start, t_end, text = self._q.get(timeout=0.25)
            except _queue.Empty:
                seg = None
            try:
                if seg is not None:
                    self._span[seg] = (t_start, t_end)
                    self.br.feed(a, t_end)
                    self._unlabelled[seg] = _t.monotonic()
                    self._seg_pcm[seg] = (a, text)
                    if len(self._seg_pcm) > 80:
                        self._seg_pcm.pop(next(iter(self._seg_pcm)))
                    self._handle(seg, self.br.on_final(seg, t_start, t_end))
                    # 11-08 test 6: provisional label right away (bypass label arrives 2-8 s later
                    #   and overrides it); stricter threshold than the final fallback.
                    if not self.tab.spk_of(seg):
                        _p = self._nearest(seg, min_sim=0.4)
                        if _p:
                            self.tab.note_final(seg, _p, [], spk_conf=0.2)
                            self._reasons["provisional"] = self._reasons.get("provisional", 0) + 1
                self._pump()
                # still unlabelled 6 s after ASR (bypass pending / refused) => nearest speaker
                now = _t.monotonic()
                for sg, ts in list(self._unlabelled.items()):
                    if self.tab.spk_of(sg):
                        self._unlabelled.pop(sg, None)
                    elif now - ts > 6.0:
                        self._unlabelled.pop(sg, None)
                        self._fallback(sg, "timeout")
            except Exception as e:
                self._log("[spk] 克隆线程异常：%s" % e)

    def _handle(self, seg, r) -> None:
        if not r:
            return
        if r.get("spk"):
            self._note(seg, r["spk"], r.get("spk_conf"), r.get("clean_ranges"))
            self._reasons["label"] = self._reasons.get("label", 0) + 1
            self._candidate(seg, r)
            return
        if r.get("pending"):
            return
        self._unlabelled.pop(seg, None)
        self._fallback(seg, str(r.get("reason") or "none"))

    def _fallback(self, seg, why) -> None:
        self._reasons[why] = self._reasons.get(why, 0) + 1
        spk = self._nearest(seg)
        if spk:
            self._reasons["fallback"] = self._reasons.get("fallback", 0) + 1
            # bind only (no clean ranges, low conf) => never seeds/refines a voice registration
            self.tab.note_final(seg, spk, [], spk_conf=0.2)
        n = sum(v for k, v in self._reasons.items() if k != "fallback")
        if n and n % 20 == 0:
            self._log("[spk] 标签来源统计：%s" % self._reasons)

    def _candidate(self, seg, r) -> None:
        """A whole sentence usable as clone reference: bypass label (not fallback), conf >= 0.5,
        clean speech covers >= 80 % of it, 1.5-12 s, and we still hold its audio + ASR text."""
        try:
            span = self._span.get(seg); item = self._seg_pcm.get(seg)
            if not span or not item or not item[1].strip():
                return
            dur = span[1] - span[0]
            cover = sum(max(0.0, float(b) - float(a))
                        for a, b in (r.get("clean_ranges") or [])) / max(dur, 1e-6)
            if float(r.get("spk_conf") or 0) < 0.5 or cover < 0.7 or not (1.5 <= dur <= 12.0):
                return
            self._cands.setdefault(r["spk"], []).append((seg, dur, item[0], item[1].strip()))
        except Exception as e:
            self._log("[spk] 参考句记录失败：%s" % e)

    def _register_sentences(self) -> None:
        """11-08 test 6: reference = whole clean sentences + their transcript (ICL clone).
        Frozen: first at >= REF_FIRST_S, one upgrade at >= REF_UPGRADE_S, then never changes
        (each new reference changed the timbre - user heard the same speaker drift)."""
        for spk, cands in list(self._cands.items()):
            cur = self._ref_dur.get(spk, 0.0)      # ICL reference seconds (interim = 0)
            if cur > 0 and (cur >= REF_UPGRADE_S or self._upgraded.get(spk)):
                continue
            total = sum(c[1] for c in cands)
            need = REF_FIRST_S if cur <= 0 else REF_UPGRADE_S
            if total < need:
                continue
            pick, acc = [], 0.0
            for c in reversed(cands):            # most recent sentences first, up to 12 s
                if acc + c[1] > 12.0 and pick:
                    break
                pick.append(c); acc += c[1]
            pick.reverse()
            gap = np.zeros(int(0.2 * SR), dtype=np.float32)
            pcm = np.concatenate([x for c in pick for x in (c[2], gap)])[:-gap.size]
            text = " ".join(c[3] for c in pick)
            refined = spk in self.paths
            self.n_reg += 1
            path = os.path.join(self.dir, "%s_%d.wav" % (spk, self.n_reg))
            with wave.open(path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
            with open(path + ".txt", "w", encoding="utf-8") as f:
                f.write(text)
            if cur > 0:
                self._upgraded[spk] = True
            self._ref_dur[spk] = acc
            self.tab.mark_embedded(spk, refined=refined)
            self.paths[spk] = path
            self._latest = spk
            self._log("[spk] %s 音色%s（整句 %d 句 %.1f s + 文本，ICL）" % (
                spk, "升级" if refined else "已登记", len(pick), acc))

    def _nearest(self, seg, min_sim: float = 0.2) -> Optional[str]:
        """11-08 test 4: the bypass leaves not-clean / overlap / too-long sentences unlabelled
        (42/57 in the user run) and they inherited the previous speaker's voice (man dubbed with a
        woman's voice). Embed the sentence and take the nearest existing speaker centroid."""
        span = self._span.get(seg)
        tr = getattr(self.br, "_tracker", None)
        if not span or tr is None or getattr(tr, "_enc", None) is None or getattr(tr, "_clu", None) is None:
            return None
        with self._lock:
            buf, t0 = self._buf, self._buf_t0
        i0 = int((span[0] - t0) * SR); i1 = int((span[1] - t0) * SR)
        if i0 < 0 or i1 > buf.size or i1 - i0 < int(1.0 * SR):
            return None
        pcm = buf[i0:i1]
        if pcm.size > int(6.0 * SR):            # encoder has a compiled upper bound; middle 6 s
            m = (pcm.size - int(6.0 * SR)) // 2
            pcm = pcm[m:m + int(6.0 * SR)]
        try:
            with tr._lock:
                v = np.asarray(tr._enc.embed(pcm, SR), dtype=np.float64).reshape(-1)
                clu = tr._clu
                cents = list(clu.centroids)
                labels = [clu._label(k) for k in range(len(cents))]
        except Exception as e:
            self._log("[spk] 兜底标签失败：%s" % e)
            return None
        if not cents:
            return None
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = [float(np.dot(v, np.asarray(c).reshape(-1))) for c in cents]
        k = int(np.argmax(sims))
        return labels[k] if sims[k] >= min_sim else None

    def _note(self, seg, spk, conf, ranges) -> None:
        self._spks.add(spk)
        self.tab.note_final(seg, spk, ranges or [], spk_conf=conf)

    def pump(self) -> None:
        """kept for callers; the clone thread pumps continuously."""
        return None

    def _pump(self) -> None:
        try:
            for seg, r in self.br.poll_results() or []:
                self._handle(seg, r)
            for seg, spk, conf, ranges in self.br.retry_pending() or []:
                if spk:
                    self._note(seg, spk, conf, ranges)
        except Exception as e:
            self._log("[spk] 取标签失败：%s" % e)
        try:
            self._register_sentences()
        except Exception as e:
            self._log("[spk] 登记失败（沿用已有音色）：%s" % e)
        try:
            self._register_interim()
        except Exception as e:
            self._log("[spk] 临时登记失败：%s" % e)

    def _register_interim(self) -> None:
        """Interim x-vector voice from the bypass clean ranges (App gate: >= 2.5 s continuous,
        conf >= 0.5) for speakers that have no voice yet; replaced once by the ICL reference."""
        for spk in list(self._spks):
            if spk in self.paths:
                continue
            rngs, key = self.tab.registration_ticket(spk)
            if not rngs:
                continue
            with self._lock:
                buf, t0 = self._buf, self._buf_t0
            pcm = self.br.pcm_for_ranges(rngs, keep=buf, max_s=10.0, keep_t0=t0)
            if pcm is None or pcm.size < int(self.sv.MIN_S * SR):
                continue
            self.n_reg += 1
            path = os.path.join(self.dir, "%s_%d.wav" % (spk, self.n_reg))
            with wave.open(path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
            a, b = rngs[0]
            self.tab.mark_registered(spk, a, b)
            self.tab.mark_embedded(spk, refined=False)
            self.paths[spk] = path
            self._latest = spk
            self._log("[spk] %s 临时音色（x-vector，%.1f s 干净段；整句 ICL 参考就绪后替换）"
                      % (spk, pcm.size / float(SR)))

    # ── TTS 线程：合成前调用 ──────────────────────────────────
    def voice_for(self, seg_id, wait: float = 0.0) -> Optional[str]:
        import time as _t
        end = _t.perf_counter() + max(0.0, wait)
        while True:
            spk = self.tab.voice_for_sentence(_seg_int(seg_id))
            if spk and spk in self.paths:
                return self.paths[spk]
            if _t.perf_counter() >= end:
                break
            _t.sleep(0.2)
        # 11-08 self-test: still no label => embed this sentence now and take the nearest
        #   registered speaker (inheriting the previous sentence's voice gave the first sentence
        #   of every new turn the previous speaker's voice).
        if not self.tab.spk_of(_seg_int(seg_id)):
            spk = self._nearest(_seg_int(seg_id), min_sim=0.25)
            if spk and spk in self.paths:
                self._reasons["tts_nearest"] = self._reasons.get("tts_nearest", 0) + 1
                return self.paths[spk]
        return None

    def latest_path(self) -> Optional[str]:
        """Most recently registered reference (used before any sentence has a label)."""
        return self.paths.get(self._latest) if self._latest else None

    def has_voice_label(self, seg_id) -> bool:
        """The sentence has a speaker label but that speaker has no voice yet."""
        spk = self.tab.spk_of(_seg_int(seg_id))
        return bool(spk) and spk not in self.paths

    def spk_of(self, seg_id) -> str:
        return self.tab.spk_of(_seg_int(seg_id))

    def close(self) -> None:
        self._stop.set()
        try:
            self.br.stop()
        except Exception:
            pass
