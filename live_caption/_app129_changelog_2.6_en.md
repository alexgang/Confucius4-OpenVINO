## v2.6 changes

**Full edition v2.6** (not included in MiniMVP / SpecialMVP).

### 1. Keep background audio (bgkeep) in the full edition

- The plugin's "keep background audio" switch is **on by default** (including for
  users upgrading from v0.4.18; a manually disabled switch stays disabled).
- **Default separation device = GPU.0 (FP32)**; override with the environment
  variable `EXT_BG_DEVICE=CPU`; if GPU compilation fails it falls back to CPU
  automatically.
- The Demucs separation model ships **inside the package**:
  `models/bgsep/htdemucs_core.xml` / `.bin` (sizes and SHA256 are recorded in
  `ACCEPTED.json` under `model_manifest`).
- If the model is missing the feature **degrades gracefully**: the popup shows
  "unavailable: background separation model missing…", dubbing keeps working
  (original audio, ducked), and it recovers once the model is back.

### 2. EXT upgraded to v0.4.20 (4740b06)

- **Clone voices follow male/female switches**: in clone mode an unlabelled
  sentence takes the most similar registered voice by **its own embedding**; a
  **pitch gender gate** (male ≤155 Hz, female ≥190 Hz) replaces a clearly
  wrong-gender voice with the most similar voice **of the same gender**
  (if none exists, the sentence clones itself).
- With slack (>9 s) the bridge waits up to 3 s for a label; with background
  audio kept, sentence audio is handed to the clone manager immediately.

### 3. APP-123: small window + direct concatenation

- Vocoder window: `chunk=8` / left context `25` frames / window `38` frames.
- Joining is direct concatenation (`crossfade=0`) — no more 50 ms lost at
  every boundary.

### 4. APP-130: NPU self-check fallback + runtime guard for the code predictor

- On some machines the NPU code predictor (`cp_prefill` / `cp_decode`) outputs
  NaN ⇒ corrupted codes ⇒ the talker never reaches EOS and a sentence runs to
  the frame limit (39 s of gibberish).
- **Self-check fallback**: after moving the code predictor to the NPU a
  self-check runs first (fixed seed, 3 input cases, per-case cosine against the
  CPU build); if it fails the code predictor **stays on CPU** and the device
  report says so.
- **Runtime guard**: if a step outputs NaN/Inf the **sentence stops
  immediately** and a `tts_runaway` counter is incremented, instead of running
  to the frame limit.

### 5. Misc

- The package contains no `bridge_token.txt` / `*.log` / `*.pid` / e2e
  artifacts / clips.
