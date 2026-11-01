"""test_ext028_dub_audio_chain.py — ★★★ EXT-028 ①：逐段音频链路（服务端那一半）

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

## 覆盖 EXT-028 第 1 条里「服务端这一侧」的三件事

| # | 要求 | 断言 |
|---|---|---|
| ① | 桥接下发前把 **PCM 原样**存下来（(b) 份） | `test_dump_writes_tts_and_ws_files`（真落盘 ⇒ 核对文件数/字节数） |
| ② | (a) TTS 原始输出与 (b) WS 发出字节**格式自洽**（采样率/声道/int16LE） | `test_dump_meta_is_self_consistent`、`test_wav_header_is_valid` |
| ③ | 定位失真所需的**可核对性**：清单（manifest）写清每段的采样率/字节数/时长 | `test_manifest_lists_segments` |

## ★★ 为什么必须真落盘再核对

EXT-028 要求「逐段对比三份音频，找出是哪一环开始失真」。
⇒ 只在内存里断言「我调用了 dump_segment」**不够** ——
  必须**真的把文件写出来**，再按字节数 / WAV 头 / manifest 交叉核对，
  否则「落盘」这件事本身可能是假的。

## ★★ 反证（区分「真通过」与「假通过」）

* `test_dump_rejects_empty` —— 没音频就**不落盘**（不留空文件）。
  ⇒ 若实现改成「空也落盘」，本断言必须 FAIL。
* `test_dump_is_bounded` —— 段数超上限时**删最旧的**并计数。
  ⇒ 若实现去掉淘汰逻辑，本断言必须 FAIL。

运行：
    python tests/test_ext028_dub_audio_chain.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ext.audio_dump import (MAX_DUMP_SEGMENTS, WAV_HEADER_BYTES,
                            pcm16_to_wav_bytes)
from ext.bridge import Session

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))


# ══════════════════════════════════════════════════════════════════
# ① WAV 头（(a) 份）—— 手写 44 字节 RIFF/WAVE
# ══════════════════════════════════════════════════════════════════
def test_wav_header_is_valid() -> None:
    """手写的 WAV 头必须**逐字段**正确（reviewer 可直接 `xxd` 看）。"""
    pcm = bytes(range(256)) * 4      # 1024 字节 = 512 个 int16 样本
    wav = pcm16_to_wav_bytes(pcm, 24000, 1)
    check("★ WAV 总长 = 44 + 数据长", len(wav) == WAV_HEADER_BYTES + len(pcm),
          f"{len(wav)}")
    check("★ RIFF 标识", wav[0:4] == b"RIFF", repr(wav[0:4]))
    check("★ WAVE 标识", wav[8:12] == b"WAVE", repr(wav[8:12]))
    check("★ fmt 标识", wav[12:16] == b"fmt ", repr(wav[12:16]))
    check("★ data 标识", wav[36:40] == b"data", repr(wav[36:40]))
    riff_size = struct.unpack("<I", wav[4:8])[0]
    check("★ RIFF 长度字段 = 文件长 - 8", riff_size == len(wav) - 8,
          f"{riff_size} vs {len(wav)-8}")
    data_size = struct.unpack("<I", wav[40:44])[0]
    check("★ data 长度字段 = 数据字节数", data_size == len(pcm),
          f"{data_size} vs {len(pcm)}")
    fmt = struct.unpack("<IHHIIHH", wav[16:36])
    check("★ fmt: PCM(1) / 单声道 / 24000 Hz / 16 bit",
          fmt[0] == 16 and fmt[1] == 1 and fmt[2] == 1
          and fmt[3] == 24000 and fmt[5] == 2 and fmt[6] == 16,
          str(fmt))
    check("★ 采样率 24000 ⇒ 1 s 音频 = 48000 字节",
          len(pcm16_to_wav_bytes(b"\x00" * 48000, 24000, 1))
          == WAV_HEADER_BYTES + 48000)


# ══════════════════════════════════════════════════════════════════
# ② 落盘：(a) TTS 原始输出 + (b) WS 下发字节
# ══════════════════════════════════════════════════════════════════
def test_dump_writes_tts_and_ws_files() -> None:
    """★ 必须**真的落盘**，且文件大小与字节数对得上。"""
    from ext.audio_dump import AudioDump
    with tempfile.TemporaryDirectory() as td:
        dump = AudioDump(td)
        tts_pcm = b"\x11\x22" * 24000          # 24000 样本 = 1 s @24k
        ws_pcm = b"\x33\x44" * 20000           # 20000 样本 ≈ 0.833 s
        info = dump.dump_segment("seg_123_456", tts_pcm=tts_pcm,
                                 ws_pcm=ws_pcm, sample_rate=24000,
                                 channels=1)
        check("★ dump_segment 返回落盘信息", info is not None)
        if not info:
            return
        files = info["files"]
        check("★ (a) TTS 原始输出落成 .wav",
              "tts_wav" in files, str(sorted(files.keys())))
        check("★ (b) WS 下发字节落成 .pcm",
              "ws_pcm" in files, str(sorted(files.keys())))
        if "tts_wav" in files:
            p = files["tts_wav"]["path"]
            check("★ (a) 文件真的存在", os.path.isfile(p), p)
            check("★ (a) 文件字节数 = 44 + PCM 长度",
                  os.path.getsize(p) == WAV_HEADER_BYTES + len(tts_pcm),
                  f"{os.path.getsize(p) if os.path.isfile(p) else -1}")
            check("★ (a) 时长 = 1.0 s",
                  abs(files["tts_wav"]["duration_sec"] - 1.0) < 1e-6,
                  f"{files['tts_wav']['duration_sec']}")
        if "ws_pcm" in files:
            p = files["ws_pcm"]["path"]
            check("★ (b) 文件真的存在", os.path.isfile(p), p)
            check("★ (b) 文件字节数 = PCM 长度（**原样**，没被『规范』）",
                  os.path.getsize(p) == len(ws_pcm),
                  f"{os.path.getsize(p) if os.path.isfile(p) else -1}")
            with open(p, "rb") as f:
                raw = f.read()
            check("★ (b) 内容与送进去的字节**逐字节相同**",
                  raw == ws_pcm)
            # 配套 .json 元信息
            mp = files["ws_pcm"].get("meta_path")
            check("★ (b) 有配套 .json 元信息", bool(mp) and os.path.isfile(mp),
                  str(mp))
            if mp and os.path.isfile(mp):
                with open(mp, encoding="utf-8") as f:
                    meta = json.load(f)
                check("★ 元信息写清 sample_rate / channels / format",
                      meta.get("sample_rate") == 24000
                      and meta.get("channels") == 1
                      and meta.get("format") == "s16le"
                      and meta.get("byte_order") == "little-endian",
                      str(meta))


def test_dump_meta_is_self_consistent() -> None:
    """★ 元信息里的采样率/字节数/时长必须**互相自洽**（可交叉核对）。"""
    from ext.audio_dump import AudioDump
    with tempfile.TemporaryDirectory() as td:
        dump = AudioDump(td)
        n_samples = 24000
        pcm = b"\x00\x01" * n_samples
        info = dump.dump_segment("seg_1", tts_pcm=pcm, ws_pcm=pcm,
                                 sample_rate=24000, channels=1)
        w = info["files"]["tts_wav"]
        b = info["files"]["ws_pcm"]
        check("★ (a)/(b) 时长一致", abs(w["duration_sec"] - b["duration_sec"]) < 1e-9)
        check("★ 时长 = 样本数 / 采样率",
              abs(w["duration_sec"] - n_samples / 24000.0) < 1e-6,
              f"{w['duration_sec']}")
        check("★ (a) 的 pcm_bytes 与 (b) 的 bytes 都是 48000",
              w["pcm_bytes"] == 48000 and b["bytes"] == 48000,
              f"{w['pcm_bytes']}/{b['bytes']}")


def test_dump_rejects_empty() -> None:
    """★ 没有音频就**不落盘**（不留空文件）—— 「没落盘的东西不能写已交付」。"""
    from ext.audio_dump import AudioDump
    with tempfile.TemporaryDirectory() as td:
        dump = AudioDump(td)
        info = dump.dump_segment("seg_empty", tts_pcm=b"", ws_pcm=b"",
                                 sample_rate=24000)
        check("★ 空音频 ⇒ 返回 None（没落盘）", info is None, str(info))
        files = [f for _r, _d, fs in os.walk(td) for f in fs]
        check("★ 目录里没有任何文件", not files, str(files))


def test_dump_is_bounded() -> None:
    """★ 段数超上限 ⇒ 删最旧的并计数（磁盘不会无限涨）。"""
    from ext.audio_dump import AudioDump
    with tempfile.TemporaryDirectory() as td:
        dump = AudioDump(td, max_segments=3)
        for i in range(6):
            dump.dump_segment("seg_%d" % i, tts_pcm=b"\x01\x02" * 100,
                              ws_pcm=b"\x03\x04" * 100, sample_rate=24000)
        check("★ 超出上限后只留 3 段", len(dump._written) == 3,
              f"{dump._written}")
        check("★ 淘汰被计数（不静默）", dump.n_dropped == 3,
              f"{dump.n_dropped}")
        on_disk = [f for _r, _d, fs in os.walk(td) for f in fs]
        # 每段 2 个文件（wav + pcm）+ 3 个 json + 1 manifest
        check("★ 磁盘上的段文件数有界（≤ 3×2 + 3）",
              len([f for f in on_disk if f.endswith(".wav")]) == 3,
              str(sorted(on_disk)))


def test_manifest_lists_segments() -> None:
    """★ manifest 必须写清每段的采样率/字节数/时长（reviewer 直接核对）。"""
    from ext.audio_dump import AudioDump
    with tempfile.TemporaryDirectory() as td:
        dump = AudioDump(td)
        for i in range(3):
            dump.dump_segment("seg_%d" % i, tts_pcm=b"\x01\x02" * 2400,
                              ws_pcm=b"\x03\x04" * 2400, sample_rate=24000)
        mp = dump.write_manifest()
        check("★ manifest 路径存在", bool(mp) and os.path.isfile(mp), str(mp))
        if not mp or not os.path.isfile(mp):
            return
        with open(mp, encoding="utf-8") as f:
            data = json.load(f)
        check("★ manifest 有 3 段", data.get("n_segments") == 3,
              f"{data.get('n_segments')}")
        segs = data.get("segments") or []
        ok = all(
            s.get("sample_rate") == 24000
            and (s.get("files", {}).get("tts_wav", {}).get("bytes") or 0) > 0
            and (s.get("files", {}).get("ws_pcm", {}).get("bytes") or 0) > 0
            for s in segs)
        check("★ 每段都写清了采样率与字节数", ok, str(segs[:1]))
        # ★ 反证：manifest 必须与磁盘上的文件**对得上**（不能只写数字）
        disk_wav = sorted(f for f in os.listdir(td) if f.endswith(".wav"))
        man_wav = sorted(os.path.basename(s["files"]["tts_wav"]["path"])
                         for s in segs)
        check("★ manifest 里的文件名与磁盘一致（可交叉核对）",
              disk_wav == man_wav, f"{disk_wav} vs {man_wav}")


# ══════════════════════════════════════════════════════════════════
# ③ 桥接侧：下行消息必须带 sample_rate（EXT-028 的根因 D1）
# ══════════════════════════════════════════════════════════════════
def test_downlink_declares_sample_rate() -> None:
    """★ 下行 `tts` 消息必须带 `sample_rate`（服务端是权威）。

    ★★ 这是 EXT-028 的**根因 D1**：
      服务端**不声明** ⇒ 插件按 `|| 16000` 重建 24 kHz PCM
      ⇒ 快 1.5× + 升调 ≈7 个半音 ⇒ 用户「基本听不清」。
    """
    import inspect
    from ext import bridge as B

    src = inspect.getsource(B)
    # 找到构造 tts 下行消息的地方
    check("★ bridge.py 里 tts 消息带 sample_rate 字段",
          '"sample_rate"' in src, "")

    # ★ 直接验行为：让一个桩引擎产出一段，走 finalize 拿到任务 dict
    sess = Session("tok", delay_sec=10.0)
    task = sess._finalize_segment(
        seg_id="seg_0", t_start=0.0, t_end=3.0, orig_end=1.0,
        audio_complete_at=1.0, text="hello", tgt="你好", spk=None, voice="A",
        pcm24k=b"\x00\x01" * 24000, speech_sec=1.0,
        asr_s=0.1, mt_s=0.1, tts_s=0.5, ready_at=2.0, error=None)
    # `_finalize_segment` 返回 list
    tasks = task if isinstance(task, list) else [task]
    check("★ finalize 产出了任务", bool(tasks), f"{len(tasks)}")
    if not tasks:
        return
    t = tasks[0]
    check("★ 任务里 sample_rate = 24000（TTS 输出率）",
          t.get("sample_rate") == 24000, f"{t.get('sample_rate')}")
    check("★ 任务里 pcm_format = s16le",
          t.get("pcm_format") == "s16le", f"{t.get('pcm_format')}")
    check("★ 任务里 pcm_channels = 1",
          t.get("pcm_channels") == 1, f"{t.get('pcm_channels')}")
    check("★ 任务里有 pcm24k 载荷", bool(t.get("pcm24k")),
          f"len={len(t.get('pcm24k') or '')}")


def test_audio_dump_hooked_into_finalize() -> None:
    """★ `_finalize_segment` 必须**真的**调 `audio_dump.dump_segment`（落盘）。"""
    from ext.audio_dump import AudioDump
    with tempfile.TemporaryDirectory() as td:
        dump = AudioDump(td)
        sess = Session("tok", delay_sec=10.0, audio_dump=dump)
        sess._finalize_segment(
            seg_id="seg_hook", t_start=0.0, t_end=3.0, orig_end=1.0,
            audio_complete_at=1.0, text="hello", tgt="你好", spk=None,
            voice="A", pcm24k=b"\x00\x01" * 2400, speech_sec=0.1,
            asr_s=0.1, mt_s=0.1, tts_s=0.5, ready_at=2.0, error=None)
        on_disk = sorted(os.listdir(td))
        wavs = [f for f in on_disk if f.endswith(".wav")]
        pcms = [f for f in on_disk if f.endswith(".pcm")]
        check("★ finalize 后 (a) wav 已落盘", len(wavs) == 1, str(on_disk))
        check("★ finalize 后 (b) pcm 已落盘", len(pcms) == 1, str(on_disk))
        # ⚠️ 落盘用的是 `public_seg_id(seg_id)` ⇒ 真实文件名形如
        #   `seg_<会话前缀>_<数字>_tts.wav`（会话前缀见 `public_seg_id`）
        #   ⇒ 这里只断言「含数字后缀 + _tts.wav」，不断言完整格式。
        check("★ 落盘文件名符合 `seg_<前缀>_<数字>_tts.wav` 形态",
              bool(wavs) and wavs[0].endswith("_tts.wav")
              and wavs[0].startswith("seg_"), str(wavs))
        check("★ (b) 的元信息 json 也落盘了",
              any(f.endswith("_ws.json") for f in on_disk), str(on_disk))


def main() -> int:
    print("=" * 68)
    print("EXT-028 逐段音频链路自测（服务端侧）")
    print("=" * 68)
    for fn in (test_wav_header_is_valid,
               test_dump_writes_tts_and_ws_files,
               test_dump_meta_is_self_consistent,
               test_dump_rejects_empty,
               test_dump_is_bounded,
               test_manifest_lists_segments,
               test_downlink_declares_sample_rate,
               test_audio_dump_hooked_into_finalize):
        try:
            fn()
        except Exception:
            check(f"{fn.__name__} 抛异常", False, traceback.format_exc())
    n_pass = sum(1 for _n, ok, _d in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 68)
    print(f"结果：{n_pass} PASS / {n_fail} FAIL / 共 {len(RESULTS)}")
    if n_fail:
        print("\nFAIL 明细：")
        for n, ok, d in RESULTS:
            if not ok:
                print(f" - {n} — {d}")
    print("=" * 68)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
