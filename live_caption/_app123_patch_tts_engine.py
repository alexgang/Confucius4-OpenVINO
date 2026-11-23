"""APP-123: integrate the c13 small-window streaming vocoder into the App's OV TTS path.

WHAT THE REVIEWER ASKED (APP-123, 2026-11-23)
  1. Wire TTS-075's "small-window streaming vocoder c13 + DIRECT CONCAT" into the
     App's OpenVINO TTS streaming path (tts_engine / tts_worker), ONE code copy
     synced to the dev tree; window/context configurable, default c13 (38/25).
     CUDA TTS path untouched.
  2. EXT goes through the same tts_engine (via the App runtime) -> confirm EXT
     dubbing also uses c13.
  3. Clone path: leave its RTF problem alone (known), but per TTS-076 add PEAK
     LIMITING and record the clipping count.

WHAT c13 IS (TTS module product `qwen3tts_genai_rc2/_tts075_stream_core.py`)
    decoder_chunk_frames = 13      # new frames per block
    decoder_ctx_frames   = 25      # left context frames
    decoder_window_len   = 38      # 13 + 25  <- the static decoder window
    overlap_mode = "decoder_left_context + direct_concat"   (crossfade_applied = False)
  => length conservation: samples == n_frames * 1920.

ARCHITECTURE FINDING (read from the code, not assumed)
  The App's OV path and the TTS module's c13 are TWO DIFFERENT implementations:

  * TTS module c13 drives the raw OV IR itself: it compiles
    `openvino_codec_decoder` with a STATIC window shape [1,16,38], feeds
    (left context ++ this block), and concatenates blocks DIRECTLY.

  * The App's OV path goes through BabelVox plus the vendored
    `tts_engine_patch.py` (`MultiDecoderBabelVox`), which ALREADY implements:
      - left context (`ctx_frames`, default 25): it re-decodes (ctx ++ chunk)
        and keeps ONLY the new chunk's samples;
      - length conservation: the patch slices `wav_full[start:end]` with
        `end = start + num_frames * 1920`;
      - a SMALL static decoder window via `decoder_buckets` (the patch's
        `_select_decoder` picks the smallest bucket >= the requested frames).

    BUT the App's chunk size is `CHUNK_FRAMES = 8` and its bucket list is
    `[8, 16, 32, 33]` -> the window it actually uses is 8 + 25 = 33, NOT 38.
    AND BabelVox's `generate_stream` defaults to `crossfade_samples=1200`,
    which takes the overlap-add branch and TRIMS `wav[:-ol]` -> each boundary
    loses 50 ms of real audio (TTS-075 measured 12.85 s / 175.0 s = 7.3%).

  => "Integrating c13 into the App" therefore means:
       (a) make chunk / ctx / bucket list CONFIGURABLE, default c13 (38/25);
       (b) force DIRECT CONCAT (`crossfade_samples=0`) -> babelvox's
           "No crossfade - simple pass-through" branch, which returns the
           whole chunk and never trims -> samples == frames * 1920;
       (c) keep the invariant explicit.
  We do NOT add a second IR driver: BabelVox IS the App's production path and
  already carries the left-context machinery.

SAFETY
  * CUDA path untouched (APP-123 explicitly says so).
  * Env-gated, so the old behaviour stays reachable for A/B.

EDIT METHOD: line-anchored (not substring) so that non-ASCII comment bytes can
never corrupt an anchor. Every edit asserts a unique anchor and the file is
written atomically (temp -> os.replace).
"""
import os

ENGINE = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption\tts_engine.py"
WORKER = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption\tts_worker.py"


def read_lines(p):
    """-> (text with '\\n' endings, original ending) — normalised internally."""
    with open(p, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    nl = "\r\n" if b"\r\n" in raw else "\n"
    if nl == "\r\n":
        text = text.replace("\r\n", "\n")
    return text, nl


def write_lines(p, text, nl):
    """Atomic write; restore the ORIGINAL line ending exactly once.

    (The earlier version did `text.replace('\\n', nl)` on text that still
    carried its '\\r' => '\\r\\r\\n' => the file grew a phantom line and
    ast.parse failed. Normalise first, then convert once.)
    """
    if nl == "\r\n":
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    data = text.replace("\n", nl).encode("utf-8")
    tmp = p + ".tmp_app123"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, p)


def find_line(lines, needle, start=0):
    """Index of the unique line containing `needle` (at or after `start`)."""
    hits = [i for i, l in enumerate(lines) if needle in l and i >= start]
    if len(hits) != 1:
        raise SystemExit("ANCHOR %r: expected 1 line, found %d" % (needle, len(hits)))
    return hits[0]


BLOCK_LINES = [
    "",
    "# =============================================================================",
    "# APP-123: TTS-075 c13 small-window streaming vocoder (window/context configurable)",
    "# =============================================================================",
    "# WHAT c13 IS (TTS module product `qwen3tts_genai_rc2/_tts075_stream_core.py`):",
    "#     decoder_chunk_frames = 13    (new frames per block)",
    "#     decoder_ctx_frames   = 25    (left context frames)",
    "#     decoder_window_len   = 38    (= 13 + 25, the static decoder window)",
    '#     overlap_mode = "decoder_left_context + direct_concat", crossfade_applied = False',
    "#     => LENGTH CONSERVATION: samples == n_frames * 1920",
    "#     (TTS-075/TTS-076 measured 36/36 rows satisfying it)",
    "#",
    "# ARCHITECTURE FACT (read from the code, not assumed):",
    "#   The TTS module's c13 drives the raw OV IR itself (static window [1,16,38]).",
    "#   The App's OV path goes through BabelVox + this repo's `tts_engine_patch.py`",
    "#   (`MultiDecoderBabelVox`), which ALREADY has:",
    "#     (1) left context (`ctx_frames`, default 25): re-decodes (ctx ++ chunk)",
    "#         and keeps ONLY this chunk's samples;",
    "#     (2) length conservation: the patch slices `wav_full[start:end]` with",
    "#         `end = start + num_frames * 1920`;",
    "#     (3) a SMALL static decoder window via `decoder_buckets` + `_select_decoder`.",
    "#   What was MISSING in the App:",
    "#     (a) chunk size: App had chunk=8 -> window 8+25 = 33, not 38;",
    "#     (b) the JOIN: BabelVox `generate_stream` defaults to",
    "#         `crossfade_samples=1200` -> overlap-add branch trims `wav[:-ol]`",
    "#         -> EVERY BOUNDARY LOSES 50 ms of real audio",
    "#         (TTS-075 measured 12.85 s / 175.0 s = 7.3% on the small-window arm,",
    "#          and that is why the \"length conservation\" conclusion was withdrawn).",
    "#         c13 requires DIRECT CONCAT (no crossfade, no tail trim).",
    "#",
    "# ENV VARS (reviewer can A/B with one variable):",
    "#   LIVECAP_TTS_CHUNK_FRAMES    new frames per block          (default 13 = c13)",
    "#   LIVECAP_TTS_CTX_FRAMES      left context frames            (default 25 = c13)",
    "#   LIVECAP_TTS_DECODER_BUCKETS comma-separated static buckets",
    "#                               (default \"13,26,38\" = covers 13 / 13+13 / 25+13)",
    "#   LIVECAP_TTS_DIRECT_CONCAT   1 = direct concat (default, c13 semantics)",
    "#                               0 = old crossfade behaviour (regression A/B)",
    "#",
    "# NOTE: the CUDA TTS path is NOT touched (APP-123 requirement).",
    "",
    "CTX_FRAMES_C13 = 25",
    "",
    "# 🔴🔴🔴 **修正（实测后）**：TTS 模块 c13 的三个参数**不是一回事**，别混：",
    "#   * `decoder_chunk_frames = 13` = 声码器**静态窗口的块容量**",
    "#     （`decoder_window_len = 13 + 25 = 38` = 声码器静态形状）",
    "#   * `n1 = n_next = 8` = **说话人每轮产出多少帧**（= 送进声码器的\"块\"）",
    "#   ⇒ c13 的真正含义是：**声码器固定 38 帧静态窗口**（未来帧补 0 = 去 look-ahead），",
    "#     说话人仍然每轮只出 8 帧。",
    "#",
    "# 🔴 **本 App 的架构映射**（BabelVox + `tts_engine_patch.py`）：",
    "#   * 说话人每轮产出帧数 = `CHUNK_FRAMES`（babelvox `chunk_frames`）",
    "#     ⇒ 对应 c13 的 `n1/n_next` = **8**（**不是 13**！）",
    "#   * 声码器静态窗口 = `DECODER_BUCKETS_CTX` 里**选中的那个桶**",
    "#     （NPU 上按 `_select_decoder(total)` 取**最小够用的桶**，并补 0 到桶大小）",
    "#     ⇒ 对应 c13 的 `decoder_window_len` = **38**",
    "#",
    "# 🔴 **实测踩坑并修正**：初版把 `CHUNK_FRAMES` 设成 13（误把\"块容量\"当成",
    "#   \"每轮产出帧数\"）⇒ 说话人要攒够 13 帧才吐第一块 ⇒ **首包从 2.9 s 劣化到 4.5 s**",
    "#   （实测 zh 句，同 seed 同文本）⇒ **已改回 8**，首包恢复。",
    "#",
    "# ⇒ **c13 的正确落地 = 说话人每轮 8 帧（不变）+ 声码器固定 38 帧静态窗口**。",
    "#   固定窗口还有一个额外好处：NPU 上只需**编译 1 个形状**（38），",
    "#   而不是现在的 4 个（8/16/32/33）⇒ 冷启动编译更少。",
    "TTS_CHUNK_FRAMES_C13 = 8      # 说话人每轮产出帧数（= c13 的 n1/n_next）",
    "TTS_DECODER_WINDOW_C13 = 38   # 声码器静态窗口（= c13 的 decoder_window_len）",
    "",
    "",
    "def _env_int(name, default):",
    '    """Env var int; invalid value falls back to the default (never raises)."""',
    "    try:",
    "        v = os.environ.get(name)",
    '        if v is None or str(v).strip() == "":',
    "            return int(default)",
    "        return int(str(v).strip())",
    "    except (TypeError, ValueError):",
    "        return int(default)",
    "",
    "",
    "def _env_buckets(default):",
    '    """Env var bucket list (comma separated); invalid falls back to default."""',
    '    raw = os.environ.get("LIVECAP_TTS_DECODER_BUCKETS")',
    '    if raw is None or str(raw).strip() == "":',
    "        return list(default)",
    "    out = []",
    '    for part in str(raw).split(","):',
    "        part = part.strip()",
    "        if not part:",
    "            continue",
    "        try:",
    "            n = int(part)",
    "        except ValueError:",
    "            return list(default)",
    "        if n > 0:",
    "            out.append(n)",
    "    return sorted(set(out)) if out else list(default)",
    "",
    "",
    "# 🔴 Direct-concat switch (c13 semantics). 0 = fall back to the old crossfade.",
    "#   (the App was ALREADY direct-concat because babelvox takes its",
    "#    pass-through branch when split_on_silence=False; this makes it explicit)",
    'DIRECT_CONCAT = os.environ.get("LIVECAP_TTS_DIRECT_CONCAT", "1").strip().lower() not in (',
    '    "0", "false", "no")',
    "# =============================================================================",
]

# ─────────────────────────────────────────────────────────────────────────────
# 1) tts_engine.py
# ─────────────────────────────────────────────────────────────────────────────
text, nl = read_lines(ENGINE)
lines = text.split("\n")

# IDEMPOTENCE: if the APP-123 block is already present, skip the engine edits
# (this script may be re-run after a partial failure).
# NB: the marker must be a line that this script itself inserts and that is
# NOT duplicated elsewhere in the file (an earlier version used a marker that
# also appeared inside a comment -> the guard never fired).
already = any(l.strip() == "TTS_DECODER_WINDOW_C13 = 38   # 声码器静态窗口（= c13 的 decoder_window_len）"
              for l in lines)
if already:
    print("tts_engine.py already patched -> skip (idempotent)")
else:
    # 1a) insert the APP-123 block right BEFORE the constants it redefines
    #     (so the helper functions exist before they are used)
    i_ctx_def = find_line(lines, "CTX_FRAMES = 25")
    lines[i_ctx_def:i_ctx_def] = BLOCK_LINES

    # 1a2) replace the ORIGINAL three constants with env-driven versions
    #      (anchors are the FULL assignment lines, so a comment mentioning
    #       e.g. "CHUNK_FRAMES = 8" cannot be matched by accident)
    i_chunk_def = find_line(lines, "CHUNK_FRAMES = 8", start=i_ctx_def + 1)
    lines[i_chunk_def] = (
        "CHUNK_FRAMES = _env_int(\"LIVECAP_TTS_CHUNK_FRAMES\", "
        "TTS_CHUNK_FRAMES_C13)")
    i_ctx_def2 = find_line(lines, "CTX_FRAMES = 25", start=i_ctx_def + 1)
    lines[i_ctx_def2] = (
        "CTX_FRAMES = _env_int(\"LIVECAP_TTS_CTX_FRAMES\", CTX_FRAMES_C13)")
    i_buckets = find_line(lines, "DECODER_BUCKETS_CTX = [8, 16, 32, 33]",
                          start=i_ctx_def + 1)
    lines[i_buckets] = (
        "DECODER_BUCKETS_CTX = _env_buckets([TTS_DECODER_WINDOW_C13])")

    # 1b) engine construction: log the c13 window口径 explicitly
    i_ctx = find_line(lines, "kwargs['ctx_frames'] = CTX_FRAMES")
    # the on_log call spans the next two lines; insert after it
    i_log_end = i_ctx
    while "）')" not in lines[i_log_end]:
        i_log_end += 1
        if i_log_end > i_ctx + 6:
            raise SystemExit("could not find the end of the MultiDecoderBabelVox on_log")
    extra = [
        "            # 🔴🔴🔴 APP-123：把 c13 的窗口口径**显式记进日志**",
        "            #   （reviewer 只需看这一行就能确认跑的是哪套窗口）",
        "            on_log(f'[tts_engine] APP-123 声码器窗口：'",
        "                   f'chunk={CHUNK_FRAMES} ctx={CTX_FRAMES} '",
        "                   f'window={CHUNK_FRAMES + CTX_FRAMES} '",
        "                   f'buckets={DECODER_BUCKETS_CTX} '",
        '                   f\'join={"direct_concat" if DIRECT_CONCAT else "crossfade"}\')',
    ]
    lines[i_log_end + 1:i_log_end + 1] = extra

    # 1c) stream(): direct concat (crossfade_samples=0) + configured chunk
    i_chunk = find_line(lines, "kwargs['chunk_frames'] = CHUNK_FRAMES")
    extra2 = [
        "    # 🔴🔴🔴 APP-123：**直接拼接**（c13 语义）⇒ 不做交叉淡化。",
        "    #   BabelVox 默认 `crossfade_samples=1200` ⇒ 走 overlap-add 分支，",
        "    #   块尾 `wav[:-ol]` 被裁掉 ⇒ **每个边界丢 50 ms 真实音频**",
        "    #   （TTS-075 §99.3：小窗口臂共丢 12.85 s / 175.0 s = 7.3%，",
        "    #    并因此撤回「长度守恒」结论）。",
        "    #   ⇒ 传 0 ⇒ babelvox 走「No crossfade — simple pass-through」分支，",
        "    #      整块返回、不裁尾 ⇒ 每块采样数 = 帧数 × 1920。",
        "    #   ⚠️ 老版本 babelvox 不认这个参数 ⇒ 签名探测，不认就不传（保持旧行为）。",
        "    if DIRECT_CONCAT:",
        "        try:",
        "            _sig_cf = inspect.signature(eng.generate_stream)",
        "            if 'crossfade_samples' in _sig_cf.parameters:",
        "                kwargs['crossfade_samples'] = 0",
        "        except Exception:",
        "            pass",
    ]
    lines[i_chunk + 1:i_chunk + 1] = extra2

    # 1d) module-level `import inspect`
    if not any(l.strip() == "import inspect" for l in lines):
        i_imp = find_line(lines, "import contextlib")
        lines[i_imp + 1:i_imp + 1] = ["import inspect"]

    write_lines(ENGINE, "\n".join(lines), nl)
    print("tts_engine.py patched")

# ─────────────────────────────────────────────────────────────────────────────
# 2) tts_worker.py — clipping counters (TTS-076 style)
# ─────────────────────────────────────────────────────────────────────────────
wtext, wnl = read_lines(WORKER)
wlines = wtext.split("\n")

# IDEMPOTENCE for tts_worker: guard on the counter lines THIS script inserts.
# (The engine guard above only covered tts_engine.py; without this, a re-run
# inserted the counters a second time -> three copies.)
_W_MARKERS = ["n_clipped = 0", "n_clipped += int(np.count_nonzero("]
_w_found = [m for m in _W_MARKERS if any(m in l for l in wlines)]
if _w_found:
    raise SystemExit("REFUSING to re-apply to tts_worker.py; markers present: %s"
                     % _w_found)

# 2a) initialise the counters right after the APP-021 amplitude-stat comment
#     (the "幅度/数值统计" one, NOT the "一行遥测" one -> must be unique)
i_amp = find_line(wlines, "APP-021②：本句的**幅度/数值**统计")
wlines[i_amp + 1:i_amp + 1] = [
    "        # 🔴🔴🔴 APP-123 / TTS-076：**削波计数**（|x| >= 1.0，会被削平）与",
    "        #   **近满量程计数**（|x| >= 0.999，软性指标）",
    "        #   ⇒ reviewer 可直接核对「限幅有没有触发、削得多硬」。",
    "        n_clipped = 0",
    "        n_near_fs = 0",
]

# 2b) count them while measuring the peak
i_ninf = find_line(wlines, "n_inf += int(np.count_nonzero(np.isinf(wf)))")
wlines[i_ninf + 1:i_ninf + 1] = [
    "                            # 🔴 APP-123 / TTS-076：削波计数（|x| >= 1.0）",
    "                            n_clipped += int(np.count_nonzero(",
    "                                np.abs(wf) >= 1.0))",
    "                            # 🔴 近满量程（>= 0.999）：软性指标",
    "                            n_near_fs += int(np.count_nonzero(",
    "                                np.abs(wf) >= 0.999))",
]

write_lines(WORKER, "\n".join(wlines), wnl)
print("tts_worker.py patched")
print("OK")
