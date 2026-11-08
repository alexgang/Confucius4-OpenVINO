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
        self.dir = os.path.join(os.environ.get("LOCALAPPDATA", "."),
                                "LiveDubEXT", "clone_voices")
        os.makedirs(self.dir, exist_ok=True)
        self.n_reg = 0
        try:
            self.br.ensure_started()
        except Exception as e:
            on_log("[spk] 旁路启动失败（克隆回落预设 A）：%s" % e)

    # ── ASR 线程：每段定稿后调用 ──────────────────────────────
    def on_segment(self, seg_id, audio, t_start: float, t_end: float) -> None:
        a = np.asarray(audio)
        if a.dtype == np.int16:
            a = a.astype(np.float32) / 32768.0
        a = a.astype(np.float32).reshape(-1)
        with self._lock:
            self._buf = np.concatenate((self._buf, a))[-int(KEEP_S * SR):]
            self._buf_t0 = float(t_end) - self._buf.size / float(SR)
        self.br.feed(a, t_end)
        r = self.br.on_final(_seg_int(seg_id), t_start, t_end)
        if r and r.get("spk"):
            self._note(_seg_int(seg_id), r["spk"], r.get("spk_conf"), r.get("clean_ranges"))
        self.pump()

    def _note(self, seg, spk, conf, ranges) -> None:
        self._spks.add(spk)
        self.tab.note_final(seg, spk, ranges or [], spk_conf=conf)

    def pump(self) -> None:
        if not self._pump_lock.acquire(blocking=False):
            return
        try:
            self._pump()
        finally:
            self._pump_lock.release()

    def _pump(self) -> None:
        try:
            for seg, r in self.br.poll_results() or []:
                if r and r.get("spk"):
                    self._note(seg, r["spk"], r.get("spk_conf"), r.get("clean_ranges"))
            for seg, spk, conf, ranges in self.br.retry_pending() or []:
                if spk:
                    self._note(seg, spk, conf, ranges)
        except Exception as e:
            self._log("[spk] 取标签失败：%s" % e)
        for spk in list(self._spks):
            try:
                rngs, key = self.tab.registration_ticket(spk)
                if not rngs or key == self._reg_key.get(spk):
                    continue
                with self._lock:
                    buf, t0 = self._buf, self._buf_t0
                pcm = self.br.pcm_for_ranges(rngs, keep=buf, max_s=10.0, keep_t0=t0)
                if pcm is None or pcm.size < int(self.sv.MIN_S * SR):
                    continue
                refined = spk in self.paths
                self.n_reg += 1
                path = os.path.join(self.dir, "%s_%d.wav" % (spk, self.n_reg))
                with wave.open(path, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(SR)
                    w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
                a, b = rngs[0]
                self.tab.mark_registered(spk, a, b)
                self.tab.mark_embedded(spk, refined=refined)
                self._reg_key[spk] = key
                self.paths[spk] = path
                self._log("[spk] %s 音色%s（%.1f s 参考）" % (
                    spk, "已细化" if refined else "已登记", pcm.size / float(SR)))
            except Exception as e:
                self._log("[spk] %s 登记失败（回落预设 A）：%s" % (spk, e))

    # ── TTS 线程：合成前调用 ──────────────────────────────────
    def voice_for(self, seg_id) -> Optional[str]:
        self.pump()
        spk = self.tab.voice_for_sentence(_seg_int(seg_id))
        return self.paths.get(spk) if spk else None

    def spk_of(self, seg_id) -> str:
        return self.tab.spk_of(_seg_int(seg_id))

    def close(self) -> None:
        try:
            self.br.stop()
        except Exception:
            pass
