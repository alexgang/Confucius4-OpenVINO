"""EXT 克隆说话人音色（reviewer 2026-11-08，用户要求接入）。

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
# 11-09 A/B: ICL reference = ONE whole sentence of 4.0-7.0 s. >= 8.7 s or 2 concatenated sentences
#   (6.9 s) => the model speaks English / pinyin-accented Chinese (CER 0.34-0.87);
#   < 4 s => similarity only at x-vector level.
REF_FIRST_S = 4.0      # shortest sentence accepted as ICL reference
REF_MAX_S = 7.0        # longest sentence accepted as ICL reference
REF_UPGRADE_GAIN = 1.0 # one upgrade to a sentence >= cur + 1.0 s, then frozen
# 11-09 user run: ICL references from real audio hit the frame cap in 22/60 calls (noise, garbled,
#   backlog) => x-vector clone by default; ICL only with EXT_CLONE_ICL=1.
CLONE_ICL = os.environ.get("EXT_CLONE_ICL", "0").strip() == "1"
XV_FIRST_S = 3.0       # x-vector speaker reference: first at >= 3 s of clean labelled sentences
XV_UPGRADE_S = 8.0     # one upgrade at >= 8 s, then frozen
XV_MAX_S = 10.0
# 11-09 user: "timbre keeps adjusting; the first one was closest" => anchor on the first good dub
CLONE_ANCHOR = os.environ.get("EXT_CLONE_ANCHOR", "0").strip() == "1"   # off until measured
ANCHOR_MIN_S, ANCHOR_MAX_S = 4.0, 7.0
ANCHOR_MIN_CHARS = 12
ANCHOR_SEC_PER_CHAR = (0.17, 0.32)      # natural Chinese speaking rate (rejects runaway / clipped)
SELF_REF_MIN_S = 1.5   # sentence-own-audio x-vector clone (before the speaker has a voice)
# 11-09 speaker-change split (calibrated on dialog3 tight/normal: 24/32 change segments cut, 0/66 false)
SPLIT_MIN_SEG_S = 3.2
SPLIT_WIN_S = (1.6, 2.0, 2.5)
SPLIT_MIN_SIM = 0.30
SPLIT_MIN_MARGIN = 0.10


def _seg_int(seg_id) -> int:
    return int(str(seg_id).rsplit("_", 1)[-1])


class CloneVoices:
    def __init__(self, on_log=print):
        from .engine_runtime import _ensure_app_on_path
        _ensure_app_on_path()
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
        self.dir = os.path.join(os.environ.get("LOCALAPPDATA", "."),
                                "LiveDubEXT", "clone_voices")
        os.makedirs(self.dir, exist_ok=True)
        for _f in os.listdir(self.dir):            # references are per session
            try:
                os.remove(os.path.join(self.dir, _f))
            except OSError:
                pass
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
                if self.__dict__.get("_split_enc") is None:
                    self._split_encoder()          # compile here, never on the receive thread
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
            if float(r.get("spk_conf") or 0) < 0.5 or cover < 0.7 or not (
                    1.5 <= dur <= (REF_MAX_S if CLONE_ICL else XV_MAX_S)):
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
            if cur > 0 and (self._upgraded.get(spk) or
                            (CLONE_ICL and cur + REF_UPGRADE_GAIN > REF_MAX_S) or
                            (not CLONE_ICL and cur >= XV_UPGRADE_S)):
                continue
            if CLONE_ICL:
                # one sentence only (concatenated references broke the Chinese pronunciation)
                ok = [c for c in cands if REF_FIRST_S <= c[1] <= REF_MAX_S]
                if not ok:
                    continue
                best = max(ok, key=lambda c: (c[1], c[0]))
                need = REF_FIRST_S if cur <= 0 else cur + REF_UPGRADE_GAIN
                if best[1] < need:
                    continue
                pick, acc = [best], best[1]
            else:
                # x-vector: most recent clean sentences up to XV_MAX_S
                pick, acc = [], 0.0
                for c in reversed(cands):
                    if acc + c[1] > XV_MAX_S and pick:
                        break
                    pick.append(c); acc += c[1]
                pick.reverse()
                need = XV_FIRST_S if cur <= 0 else XV_UPGRADE_S
                if acc < need or (cur > 0 and acc < cur + 2.0):
                    continue
            gap = np.zeros(int(0.2 * SR), dtype=np.float32)
            pcm = np.concatenate([x for c in pick for x in (c[2], gap)])[:-gap.size]
            text = " ".join(c[3] for c in pick)
            refined = spk in self.paths
            self.n_reg += 1
            path = os.path.join(self.dir, "%s_%d.wav" % (spk, self.n_reg))
            with wave.open(path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
            if CLONE_ICL:
                with open(path + ".txt", "w", encoding="utf-8") as f:
                    f.write(text)
            elif os.path.exists(path + ".txt"):
                os.remove(path + ".txt")
            if cur > 0:
                self._upgraded[spk] = True
            self._ref_dur[spk] = acc
            self.tab.mark_embedded(spk, refined=refined)
            self.paths[spk] = path
            self._latest = spk
            self._log("[spk] %s 音色%s（整句 %d 句 %.1f s%s）" % (
                spk, "升级" if refined else "已登记", len(pick), acc,
                " + 文本，ICL" if CLONE_ICL else "，x-vector"))

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

    def self_ref(self, seg_id) -> Optional[str]:
        """11-09: x-vector reference = THIS sentence's own audio (no transcript => x-vector mode).
        Used while the sentence's speaker has no ICL voice yet, so the clone starts with the first
        dubbed sentence instead of preset A / another speaker's voice."""
        seg = _seg_int(seg_id)
        span = self._span.get(seg)
        with self._lock:
            buf, t0 = self._buf, self._buf_t0
        pcm = None
        if span:
            i0 = int((span[0] - t0) * SR); i1 = int((span[1] - t0) * SR)
            if 0 <= i0 < i1 <= buf.size:
                pcm = buf[i0:i1]
        if pcm is None:
            item = self._seg_pcm.get(seg)
            pcm = item[0] if item else None
        if pcm is None or pcm.size < int(SELF_REF_MIN_S * SR):
            return None
        if pcm.size > int(8.0 * SR):
            m = (pcm.size - int(8.0 * SR)) // 2
            pcm = pcm[m:m + int(8.0 * SR)]
        path = os.path.join(self.dir, "self_%d.wav" % seg)
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
        q = self.__dict__.setdefault("_self_files", [])
        q.append(path)
        while len(q) > 30:
            try:
                os.remove(q.pop(0))
            except OSError:
                pass
        self._reasons["self_ref"] = self._reasons.get("self_ref", 0) + 1
        return path

    # ── 11-09: speaker-change split (receive thread, clone mode) ─────────────────
    def _split_encoder(self):
        """Own WeSpeaker encoder instance (the bypass one sits behind the tracker lock)."""
        enc = self.__dict__.get("_split_enc")
        if enc is None and not self.__dict__.get("_split_enc_failed"):
            tr = getattr(self.br, "_tracker", None)
            src = getattr(tr, "_enc", None) if tr is not None else None
            ir = getattr(tr, "wes_ir", None) if tr is not None else None
            if src is None or not ir:
                return None
            try:
                enc = type(src)(ir, getattr(src, "device", "GPU.0"), range_lo=60)
                z = np.zeros(int(max(SPLIT_WIN_S) * SR), np.float32) + 1e-3
                for w in SPLIT_WIN_S:                 # one compile per window length
                    enc.embed(z[:int(w * SR)], SR)
                self._split_enc = enc
            except Exception as e:
                self._split_enc_failed = True
                self._log("[spk] 说话人切分不可用：%s" % e)
                return None
        return enc

    def _centroids(self):
        tr = getattr(self.br, "_tracker", None)
        clu = getattr(tr, "_clu", None) if tr is not None else None
        if clu is not None and tr._lock.acquire(timeout=0.05):
            try:
                cs = [np.asarray(c, np.float64).reshape(-1) for c in clu.centroids]
                self._cents = [c / (np.linalg.norm(c) + 1e-9) for c in cs]
            finally:
                tr._lock.release()
        return self.__dict__.get("_cents") or []

    def _ident(self, enc, cents, x):
        v = np.asarray(enc.embed(x, SR), np.float64).reshape(-1)
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = sorted(((float(v @ c), k) for k, c in enumerate(cents)), reverse=True)
        if sims[0][0] >= SPLIT_MIN_SIM and sims[0][0] - sims[1][0] >= SPLIT_MIN_MARGIN:
            return sims[0][1], sims[0][0] - sims[1][0]
        return None, 0.0

    def _best_cut(self, enc, cents, x):
        L = x.size / float(SR)
        lo, hi = SPLIT_WIN_S[0], L - SPLIT_WIN_S[0]
        if hi < lo:
            return None

        def score(t):
            m = int(t * SR)
            wl = max(w for w in SPLIT_WIN_S if w <= t + 1e-6)
            wr = max(w for w in SPLIT_WIN_S if w <= L - t + 1e-6)
            kl, ml = self._ident(enc, cents, x[m - int(wl * SR):m])
            kr, mr = self._ident(enc, cents, x[m:m + int(wr * SR)])
            return min(ml, mr) if (kl is not None and kr is not None and kl != kr) else None

        best = None
        for t in np.arange(lo, hi + 1e-6, 0.5):            # coarse 0.5 s, then refine +-0.25 s
            sc = score(t)
            if sc is not None and (best is None or sc > best[0]):
                best = (sc, t)
        if best is None:
            return None
        for t in (best[1] - 0.25, best[1] + 0.25):
            if lo <= t <= hi:
                sc = score(t)
                if sc is not None and sc > best[0]:
                    best = (sc, t)
        # snap to the quietest 20 ms frame within +-0.25 s
        c = int(best[1] * SR); fr = int(0.02 * SR)
        a0 = max(int(lo * SR), c - int(0.25 * SR)); a1 = min(int(hi * SR), c + int(0.25 * SR))
        if a1 - a0 > fr:
            e = [float(np.mean(x[i:i + fr] ** 2)) for i in range(a0, a1 - fr, fr // 2)]
            c = a0 + int(np.argmin(e)) * (fr // 2) + fr // 2
        return c

    def split_by_speaker(self, buf, segs):
        """Split [(s0, s1), ...] (sample offsets into buf) at speaker changes; outer bounds unchanged."""
        if not segs or not any((b - a) >= int(SPLIT_MIN_SEG_S * SR) for a, b in segs):
            return segs
        cents = self._centroids()
        if len(cents) < 2:
            return segs
        import time as _t
        _t0 = _t.perf_counter()
        enc = self.__dict__.get("_split_enc")   # built on the clone thread
        if enc is None:
            return segs
        out = []
        for a, b in segs:
            parts = [(a, b)]
            for _round in range(2):
                nxt = []
                for p0, p1 in parts:
                    c = None
                    if p1 - p0 >= int(SPLIT_MIN_SEG_S * SR):
                        try:
                            c = self._best_cut(enc, cents, np.asarray(buf[p0:p1], np.float32))
                        except Exception as e:
                            self._log("[spk] 说话人切分失败：%s" % e)
                    if c:
                        nxt += [(p0, p0 + c), (p0 + c, p1)]
                        self._reasons["spk_split"] = self._reasons.get("spk_split", 0) + 1
                    else:
                        nxt.append((p0, p1))
                if len(nxt) == len(parts):
                    break
                parts = nxt
            out += parts
        _dt = _t.perf_counter() - _t0
        st = self.__dict__.setdefault("_split_stats", [0, 0.0, 0.0])
        st[0] += 1; st[1] += _dt; st[2] = max(st[2], _dt)
        if _dt > 0.5 or st[0] % 20 == 0:
            self._log("[spk] 说话人切分：本次 %.2f s（%d 段 -> %d 段）；累计 %d 次 平均 %.3f s 最大 %.2f s"
                      % (_dt, len(segs), len(out), st[0], st[1] / st[0], st[2]))
        return out

    def offer_dub(self, spk, voice_path, text, pcm24k, sr: int = 24000) -> None:
        """11-09 anchor: the speaker's first good Chinese dub becomes his fixed ICL reference."""
        if not CLONE_ANCHOR or not spk or not pcm24k or not voice_path:
            return
        anch = self.__dict__.setdefault("_anchored", {})
        if spk in anch or self.paths.get(spk) != voice_path:
            return                      # already anchored / dub not made with his registered voice
        import re as _re
        n = len(_re.sub(r"[\s\W_]+", "", text or ""))
        x = np.frombuffer(pcm24k, dtype="<i2")
        dur = x.size / float(sr)
        if n < ANCHOR_MIN_CHARS or not (ANCHOR_MIN_S <= dur <= ANCHOR_MAX_S):
            return
        if not (ANCHOR_SEC_PER_CHAR[0] <= dur / n <= ANCHOR_SEC_PER_CHAR[1]):
            return
        self.n_reg += 1
        path = os.path.join(self.dir, "%s_anchor_%d.wav" % (spk, self.n_reg))
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(sr))
            w.writeframes(x.tobytes())
        with open(path + ".txt", "w", encoding="utf-8") as f:
            f.write(text.strip())
        anch[spk] = path
        self._upgraded[spk] = True
        self._ref_dur[spk] = 99.0          # frozen: no further upgrades
        self.paths[spk] = path
        self._log("[spk] %s 音色锚定（首句中文配音 %.1f s / %d 字 + 文本；之后固定）" % (spk, dur, n))

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
