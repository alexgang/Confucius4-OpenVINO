"""audio_dump.py — ★ EXT-028 ①：**逐段落盘三份音频**，用于定位失真发生在哪一环

## 为什么要这个模块（reviewer EXT-028 明文）

> 每段落盘三份音频，逐段对比：
> - (a) 桥接侧 TTS 原始输出 wav；
> - (b) 桥接下发前的 PCM（也就是 WS 发出的那份，按发出的格式原样存）；
> - (c) player 端 MediaRecorder 录到的同一段。
> 三份要对齐时长和采样率，算互相关/SNR，找出是哪一环开始失真：
> 采样率或声道错配、int16/float32 解释错、字节序、chunk 拼接、增益、叠播。

## 三份音频的**确切含义**（不要混淆）

| 编号 | 是什么 | 落盘名 | 采样率 | 回答什么问题 |
|---|---|---|---|---|
| (a) | **TTS 引擎的原始输出**（未经变速/未经任何处理） | `seg_<id>_tts.wav` | 24 kHz | 模型本身对不对 |
| (b) | **WS 实际发出的那份**（经过 WSOLA 变速后、base64 **之前**的字节） | `seg_<id>_ws.pcm` | 24 kHz | 下发环节有没有改坏 |
| (c) | **player 录到的**（由冒烟脚本从 player 落盘） | `player_dub_<id>.webm` | 48 kHz(opus) | 浏览器这一环有没有改坏 |

★ (a) 与 (b) 的差别 = **服务端变速（WSOLA）**的影响。
★ (b) 与 (c) 的差别 = **浏览器解码/重采样/混音/录音**的影响。

## 落盘格式的口径

* (a) 落成 **真 WAV**（44 字节头 + PCM16LE）⇒ 可被任何工具直接读；
* (b) 落成 **裸 PCM**（`.pcm`，little-endian int16）+ 同名 `.json` 记录元信息
  ⇒ 因为它的「格式」本身就是待验证的对象（不该由本模块替它「规范」掉）；
  配套的 `.json` 里写清 `sample_rate` / `channels` / `format` / `bytes`。

## ★ 铁律

* **只落盘，不改音频**：本模块只把**已经是那个字节**的东西写出去；
* **绝不臆造**：没产出的段就不落盘（不留空文件）；
* **有界**：只保留最近 N 段的 dump（防止长会话把磁盘写满），
  超出的**删除**并计数（不是静默）。
"""
from __future__ import annotations

import json
import os
import struct
import threading
from typing import Dict, List, Optional

#: 最多保留多少段的 dump（超出删最旧的）
MAX_DUMP_SEGMENTS = 200

#: WAV 头的字节数
WAV_HEADER_BYTES = 44


def pcm16_to_wav_bytes(pcm: bytes, sample_rate: int,
                       channels: int = 1) -> bytes:
    """把 PCM16LE 裸数据包成 **标准 WAV** 字节。

    ★ 手工写 44 字节头（不用 wave 模块）⇒ 不依赖任何第三方库，
      且输出格式完全可控（reviewer 可直接 `xxd` 看头）。
    """
    if not pcm:
        return b""
    n_ch = max(1, int(channels))
    sr = int(sample_rate)
    byte_rate = sr * n_ch * 2
    block_align = n_ch * 2
    bits = 16
    fmt = b"fmt " + struct.pack(
        "<IHHIIHH", 16, 1, n_ch, sr, byte_rate, block_align, bits)
    data = b"data" + struct.pack("<I", len(pcm)) + pcm
    riff = b"RIFF" + struct.pack("<I", 4 + len(fmt) + len(data)) + b"WAVE"
    return riff + fmt + data


class AudioDump:
    """逐段落盘 TTS 原始输出（a）与 WS 下发字节（b）。

    ★ 用法（bridge 里）::

        dump = AudioDump(out_dir)             # out_dir=None ⇒ 关闭
        dump.dump_segment(seg_id, tts_pcm=pcm_raw, ws_pcm=pcm_out)

    ★ 线程安全：`_finalize_segment` 在流水线模式下可能从**主机侧线程**调用
      ⇒ 用一把锁保护索引（写文件本身在锁外做，避免长时间持锁）。
    """

    def __init__(self, out_dir: Optional[str], *,
                 max_segments: int = MAX_DUMP_SEGMENTS) -> None:
        self.out_dir = out_dir
        self.max_segments = max(1, int(max_segments))
        self._lock = threading.Lock()
        self._written: List[str] = []          # 有序的 seg_id 列表
        self._meta: Dict[str, dict] = {}        # seg_id → 元信息
        self.n_dropped = 0

    # ── 属性 ──────────────────────────────────────────────────
    @property
    def enabled(self) -> bool:
        return bool(self.out_dir)

    def manifest_path(self) -> Optional[str]:
        if not self.out_dir:
            return None
        return os.path.join(self.out_dir, "audio_dump_manifest.json")

    # ── 落盘 ──────────────────────────────────────────────────
    def dump_segment(self, seg_id: str, *, tts_pcm: Optional[bytes],
                     ws_pcm: Optional[bytes], sample_rate: int,
                     channels: int = 1, extra: Optional[dict] = None) -> Optional[dict]:
        """落盘一段的三份（或两份）音频，返回落盘信息。

        Parameters
        ----------
        seg_id
            段的**对外 id**（带会话前缀，如 `seg_12345678_194400`）。
        tts_pcm
            (a) TTS 引擎的**原始输出**字节（未经变速）。可为 None。
        ws_pcm
            (b) **WS 实际发出的**那份字节（base64 之前）。可为 None。
        sample_rate
            这两份 PCM 的采样率（**都**是 TTS 输出率）。
        """
        if not self.out_dir:
            return None
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except OSError:
            return None

        safe = _safe_name(seg_id)
        info: dict = {"seg_id": seg_id, "sample_rate": int(sample_rate),
                      "channels": int(channels), "format": "s16le",
                      "files": {}}
        # ── (a) TTS 原始输出 → WAV ──────────────────────────
        if tts_pcm:
            wav = pcm16_to_wav_bytes(tts_pcm, sample_rate, channels)
            p = os.path.join(self.out_dir, "%s_tts.wav" % safe)
            with open(p, "wb") as f:
                f.write(wav)
            info["files"]["tts_wav"] = {
                "path": p, "bytes": len(wav),
                "pcm_bytes": len(tts_pcm),
                "duration_sec": round(len(tts_pcm) / 2.0
                                      / max(1, sample_rate) * channels, 4),
            }
        # ── (b) WS 下发字节 → 裸 PCM（+ .json 元信息） ────────
        if ws_pcm:
            p = os.path.join(self.out_dir, "%s_ws.pcm" % safe)
            with open(p, "wb") as f:
                f.write(ws_pcm)
            meta_p = os.path.join(self.out_dir, "%s_ws.json" % safe)
            info["files"]["ws_pcm"] = {
                "path": p, "bytes": len(ws_pcm),
                "duration_sec": round(len(ws_pcm) / 2.0
                                      / max(1, sample_rate) * channels, 4),
                "meta_path": meta_p,
            }
        if not info["files"]:
            return None

        # ── 索引（线程安全） ─────────────────────────────────
        with self._lock:
            if seg_id in self._meta:
                self._written.remove(seg_id)
            self._written.append(seg_id)
            self._meta[seg_id] = info
            over = len(self._written) - self.max_segments
            removed = []
            while over > 0:
                old = self._written.pop(0)
                old_info = self._meta.pop(old, None)
                removed.append(old)
                for f in (old_info or {}).get("files", {}).values():
                    # ⚠️ `meta_path` 只有 (b) 那份才有 ⇒ 必须用
                    #   `f.get(key)`（**不能**用 `f[key]`）⇒ 否则淘汰
                    #   (a) 那份时会抛 KeyError ⇒ 整个落盘链崩掉。
                    #   （★ 这是本轮自测实测抓到的真缺陷。）
                    for key in ("path", "meta_path"):
                        p_old = f.get(key)
                        if not p_old:
                            continue
                        try:
                            os.remove(p_old)
                        except OSError:
                            pass
                over -= 1
            if removed:
                self.n_dropped += len(removed)

        # ── (b) 的 .json 元信息（写清格式 ⇒ 不替它"规范"） ──
        if "ws_pcm" in info["files"]:
            wm = {"seg_id": seg_id, "sample_rate": int(sample_rate),
                  "channels": int(channels), "format": "s16le",
                  "byte_order": "little-endian", "bytes": len(ws_pcm),
                  "duration_sec": info["files"]["ws_pcm"]["duration_sec"]}
            if extra:
                wm.update(extra)
            try:
                with open(info["files"]["ws_pcm"]["meta_path"], "w",
                          encoding="utf-8") as f:
                    json.dump(wm, f, ensure_ascii=False, indent=2)
            except OSError:
                pass
        return info

    # ── 清单 ──────────────────────────────────────────────────
    def write_manifest(self, extra: Optional[dict] = None) -> Optional[str]:
        """把落盘清单写成 JSON（供 reviewer 直接核对文件数/字节数）。"""
        p = self.manifest_path()
        if not p:
            return None
        with self._lock:
            segs = []
            for sid in self._written:
                info = dict(self._meta.get(sid) or {})
                segs.append(info)
            data = {
                "n_segments": len(segs),
                "n_dropped": self.n_dropped,
                "max_segments": self.max_segments,
                "segments": segs,
            }
            if extra:
                data.update(extra)
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            return None
        return p


def _safe_name(seg_id: str) -> str:
    """把段 id 变成安全的文件名（只留字母数字/下划线/连字符）。"""
    out = []
    for ch in str(seg_id):
        if ch.isalnum() or ch in "_-":
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out) or "seg"
    return s[:120]
