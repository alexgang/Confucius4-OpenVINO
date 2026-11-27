"""APP-157 §3: update v1.2.1 README lag figures in the customer package.
Exact single-hit replacement, backup, atomic write, byte-level post-check, LF preserved.
"""
import os
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\Trekker-PTL\LiveCaption_MiniMVP_v1.2.1')
TAG = 'app157_latency'
ZH_OLD = """- 讲话密集、持续不停顿时，配音会逐渐落后。**v1.2 在本机（Core Ultra 7 356H，TTS=NPU 默认档）
  的 10 分钟连续讲话实测**：滞后中位数 29 s（关背景音）／51 s（开背景音）／95 s（开背景音＋克隆），
  最坏 161 s／225 s／338 s；讲完后会继续播积压内容，媒体结束后约 1.4～3.0 分钟才播完。
  讲话中的停顿能让配音追上；想更跟得上，可关掉「保留背景音」或不使用克隆音色。"""
ZH_NEW = """- 讲话密集、持续不停顿时，配音会逐渐落后。**v1.2.1 在本机（Core Ultra 7 356H，TTS=NPU 默认档）
  的 10 分钟连续讲话实测**：滞后中位数 3 s（关背景音）／12 s（开背景音）／约 4 分钟（开背景音＋克隆），
  最坏 51 s／88 s／约 9.5 分钟；开克隆时媒体结束后还要约 7 分钟才把积压播完。
  克隆音色在 NPU 上合成较慢，讲话密集场景建议不开克隆（克隆默认关闭）；
  讲话中的停顿能让配音追上；想更跟得上，可关掉「保留背景音」。"""
EN_OLD = """- **Dubbing falls behind during dense, continuous speech.** Measured in v1.2 on the same
  reference machine (default TTS = NPU), 10 minutes of non-stop speech: median lag 29 s
  (background off) / 51 s (background on) / 95 s (background on + cloned voice), worst case
  161 s / 225 s / 338 s. Playback continues after the media ends and takes about 1.4–3.0
  minutes to finish the backlog. Pauses let the dubbing catch up; turning background
  keeping or voice cloning off makes it keep up better."""
EN_NEW = """- **Dubbing falls behind during dense, continuous speech.** Measured in v1.2.1 on the same
  reference machine (default TTS = NPU), 10 minutes of non-stop speech: median lag 3 s
  (background off) / 12 s (background on) / ~4 min (background on + cloned voice), worst case
  51 s / 88 s / ~9.5 min. With cloning on, playback continues for about 7 minutes after the
  media ends to drain the backlog. Cloned voices synthesize slowly on NPU, so keep cloning
  off (off by default) for dense speech. Pauses let the dubbing catch up; turning background
  keeping off also helps."""

for name, old, new in (('README_zh.md', ZH_OLD, ZH_NEW), ('README_en.md', EN_OLD, EN_NEW)):
    p = ROOT / name
    bak = Path(r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_removed_bak') / (name + '.bak_' + TAG)
    raw = p.read_bytes()
    assert b'\r\n' not in raw, f'{name} not LF-only'
    text = raw.decode('utf-8')
    assert text.count(old) == 1, f'{name}: old block hit {text.count(old)} times'
    out_bytes = text.replace(old, new).encode('utf-8')
    if not bak.exists():
        shutil.copy2(p, bak)
    tmp = p.with_name(p.name + '.tmp_' + TAG)
    tmp.write_bytes(out_bytes)
    os.replace(tmp, p)
    check = p.read_bytes()
    assert check == out_bytes, f'{name}: post-write byte mismatch'
    assert check.count(b'\r\n') == 0
    assert '29 s' not in check.decode('utf-8') and '161 s' not in check.decode('utf-8')
    print('OK', name, len(raw), '->', len(check), 'bytes; backup', bak.name)
