#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129 §3.4 + §3.5：**不可用降级检查** ＋ **抽听样片（OGG 附件）**。

## §3.4 不可用降级（reviewer 明文）

> 临时把包里的 `models\\bgsep` 改名 → popup 显示「不可用：背景分离模型缺失…」，
> 配音照常（原声压低），恢复后正常。

⇒ 本脚本：**改名 → 起桥接 → hello 看 bg 状态 ⇒ 停桥接 → 改回来**
   （`finally` 保证一定改回来；改名前后各记一次目录存在性 + 文件数）。

## §3.5 抽听样片（reviewer 明文）

> 用包内桥接跑 `tools/bgkeep_e2e.py` 对 `shared\\bgkeep\\clips\\{cs2,s1,s2,tuffy}.wav`
> 各一段，`player_mix.wav` 转成 **≤1 MB 的 OGG** 作为附件发 reviewer
> （**最多 3 个**，优先 **s2、cs2、tuffy**）。

⇒ 编码用 **PyAV（包内 python 自带）** 走 libvorbis，码率按长度自适应，
   **保证 OGG ≤ 1 MB**（超了就降码率重编）。

## 纪律

- 每条臂**单独起桥接**；桥接 **cwd = 臂目录** ⇒ `bridge_token.txt` 落在**包外**；
- 持共享机器锁（占设备）；
- 不动 `live_dub_ext` 源码仓（**只读**）。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.dirname(REPO)
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import _app116_build_v25 as B  # noqa: E402

PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
EXT_REPO = os.path.join(HOME, 'live_dub_ext')
CLIPS = os.path.join(HOME, 'shared', 'bgkeep', 'clips')
OUT_ROOT = os.path.join(HOME, 'shared', 'bgkeep', 'e2e_v26')
RESULTS = os.path.join(REPO, 'results', 'app')
BGSEP = os.path.join(PKG, 'models', 'bgsep')
BGSEP_OFF = os.path.join(PKG, 'models', 'bgsep_disabled_probe')

#: reviewer 指定优先顺序（最多 3 个）
CLIP_ORDER = ['s2', 'cs2', 'tuffy', 's1']
MAX_CLIPS = 3
MAX_OGG_BYTES = 1024 * 1024


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, 'app129_clips_v26.log'), 'a',
                  encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def e2e_tool():
    out = os.path.join(os.environ.get('TEMP', HOME), 'bgkeep_e2e_0419.py')
    if os.path.isfile(out):
        return out
    p = subprocess.run(['git', '-C', EXT_REPO, 'show',
                        '3573b2d:tools/bgkeep_e2e.py'], capture_output=True)
    if p.returncode != 0:
        return None
    with open(out, 'wb') as f:
        f.write(p.stdout)
    return out


def bridge_env():
    env = dict(os.environ)
    env['EXT_APP_ROOT'] = PKG
    env['EXT_APP_SEARCH_ROOT'] = PKG
    env['PYTHONPATH'] = PKG + os.pathsep + os.path.join(PKG, '.runtime_deps')
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('EXT_BG_DEVICE', None)
    # 🔴🔴 设备口径：reviewer 明文「出厂默认：ASR/MT GPU.0、TTS NPU」
    #   ⇒ EXT 的 AUTO 默认会解析成 MT=NPU / TTS=CUDA 边车 ⇒ 必须显式钉死。
    env['EXT_MT_DEVICE'] = 'GPU.0'
    env['EXT_TTS_DEVICE'] = 'NPU'
    # 🔴 e2e 工具需要 `ext.extension_id`（包内它在 `ext/bridge/` 下）⇒ 路径垫片
    shim = make_ext_shim()
    env['PYTHONPATH'] = shim + os.pathsep + env['PYTHONPATH']
    return env


def make_ext_shim():
    """建 `ext` 垫片包：`__path__` 追加 `<pkg>/ext` 与 `<pkg>/ext/bridge`。"""
    shim = os.path.join(OUT_ROOT, '_extshim')
    extdir = os.path.join(shim, 'ext')
    os.makedirs(extdir, exist_ok=True)
    init = (
        '# 🔴 包内布局垫片（打包侧加，不改 EXT 代码）\n'
        'import os as _os\n'
        '_PKG = %r\n'
        '__path__.append(_os.path.join(_PKG, "ext"))\n'
        '__path__.append(_os.path.join(_PKG, "ext", "bridge"))\n' % PKG)
    with open(os.path.join(extdir, '__init__.py'), 'w', encoding='utf-8',
              newline='') as f:
        f.write(init)
    return shim


def start_bridge(cwd, logname='bridge.log'):
    os.makedirs(cwd, exist_ok=True)
    env = bridge_env()
    args = [PKG_PY, '-X', 'utf8', '-m', 'ext.bridge', '--real', '--pipeline',
            '--port', '8765', '--delay', '20', '--target-lang', 'zh',
            '--spk-bypass']
    p = subprocess.Popen(args, cwd=cwd, env=env,
                         stdout=open(os.path.join(cwd, logname), 'wb'),
                         stderr=open(os.path.join(cwd, 'bridge.err'), 'wb'))
    t0 = time.time()
    while time.time() - t0 < 420:
        if p.poll() is not None:
            return p, False, round(time.time() - t0, 1)
        try:
            txt = open(os.path.join(cwd, logname), encoding='utf-8',
                       errors='replace').read()
            if 'ws://127.0.0.1:8765' in txt:
                return p, True, round(time.time() - t0, 1)
        except Exception:
            pass
        time.sleep(5)
    return p, False, round(time.time() - t0, 1)


def stop_bridge(p):
    try:
        p.terminate()
        p.wait(timeout=20)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def hello_probe(cwd):
    """用包内 python 发一个 hello，问 bg 状态（用于 §3.4 的降级判定）。"""
    tool = e2e_tool()
    if not tool:
        return None
    env = bridge_env()
    code = (
        'import asyncio, json, base64, os, sys\n'
        'import websockets\n'
        'async def main():\n'
        '    tok = open(sys.argv[1], encoding="utf-8").read().strip()\n'
        '    async with websockets.connect("ws://127.0.0.1:8765") as ws:\n'
        '        await ws.send(json.dumps({"type": "hello", "role": "uplink",\n'
        '            "bg_keep": True, "bg_sample_rate": 48000, "bg_channels": 2,\n'
        '            "target_lang": "zh", "voice": "A", "token": tok}))\n'
        '        for _ in range(30):\n'
        '            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))\n'
        '            if m.get("type") == "hello_ack":\n'
        '                print(json.dumps(m, ensure_ascii=False)); return\n'
        '    print("{}")\n'
        'asyncio.run(main())\n')
    tp = os.path.join(cwd, '_hello_probe.py')
    with open(tp, 'w', encoding='utf-8') as f:
        f.write(code)
    try:
        p = subprocess.run([PKG_PY, '-X', 'utf8', tp,
                            os.path.join(cwd, 'bridge_token.txt')],
                           capture_output=True, text=True, timeout=120,
                           cwd=cwd, env=env)
        txt = (p.stdout or '').strip().splitlines()
        for line in reversed(txt):
            if line.startswith('{'):
                return json.loads(line)
        return {'raw': (p.stdout or '')[-800:], 'err': (p.stderr or '')[-800:]}
    except Exception as e:
        return {'error': repr(e)}


# ── OGG 编码（PyAV libvorbis；目标 ≤1 MB）─────────────────────────────
def wav_to_ogg(wav, ogg, max_bytes=MAX_OGG_BYTES):
    """把 wav 转成 ≤max_bytes 的 OGG。返回 (ok, info)。"""
    import wave as _w
    with _w.open(wav, 'rb') as f:
        sr = f.getframerate()
        ch = f.getnchannels()
        n = f.getnframes()
        dur = n / float(sr)
    bitrate = 96000
    for _try in range(6):
        rc = _encode_av(wav, ogg, sr, ch, bitrate)
        if rc is None:
            return False, {'error': 'PyAV 编码失败'}
        sz = os.path.getsize(ogg)
        if sz <= max_bytes:
            return True, {'bytes': sz, 'bitrate': bitrate, 'dur_s': round(dur, 1),
                          'sample_rate': sr, 'channels': ch}
        bitrate = max(24000, int(bitrate * 0.6))
    sz = os.path.getsize(ogg)
    return sz <= max_bytes, {'bytes': sz, 'bitrate': bitrate,
                             'dur_s': round(dur, 1)}


def _encode_av(wav, ogg, sr, ch, bitrate):
    try:
        import av
        import numpy as np
        with av.open(wav) as inp:
            in_stream = inp.streams.audio[0]
            resampler = av.audio.resampler.AudioResampler(
                format='s16', layout='stereo' if ch == 2 else 'mono',
                rate=sr)
            with av.open(ogg, 'w', format='ogg') as out:
                out_stream = out.add_stream('vorbis', rate=sr)
                out_stream.bit_rate = bitrate
                for frame in inp.decode(in_stream):
                    for rf in resampler.resample(frame):
                        for pkt in out_stream.encode(rf):
                            out.mux(pkt)
                for pkt in out_stream.encode(None):
                    out.mux(pkt)
        return True
    except Exception as e:
        print('av encode fail:', repr(e))
        return None


# ── §3.4 不可用降级 ──────────────────────────────────────────────────
def check_degradation():
    rec = {'name': 'degradation_models_bgsep_missing', 'ts':
           datetime.datetime.now().isoformat(timespec='seconds')}
    if not os.path.isdir(BGSEP):
        rec['error'] = 'models/bgsep 不存在'
        return rec
    cwd = os.path.join(OUT_ROOT, 'degrade')
    os.makedirs(cwd, exist_ok=True)
    rec['before'] = {'dir': os.path.isdir(BGSEP),
                     'files': sorted(os.listdir(BGSEP))}
    renamed = False
    try:
        os.rename(BGSEP, BGSEP_OFF)
        renamed = True
        rec['renamed'] = True
        log('§3.4 models/bgsep 已改名（⇒ 缺失态）')
        p, ready, rs = start_bridge(cwd)
        rec['bridge_ready'] = ready
        rec['bridge_ready_s'] = rs
        if ready:
            ack = hello_probe(cwd)
            rec['hello_ack'] = ack
            bg = (ack or {}).get('bg') or {}
            rec['bg_state'] = bg.get('state')
            rec['bg_reason'] = bg.get('reason')
            rec['bg_supported'] = (ack or {}).get('bg_supported')
            rec['bg_model'] = (ack or {}).get('bg_model')
            log('§3.4 hello_ack.bg = %s' % json.dumps(bg, ensure_ascii=False))
        stop_bridge(p)
    finally:
        if renamed:
            try:
                os.rename(BGSEP_OFF, BGSEP)
                log('§3.4 models/bgsep 已改回')
            except Exception as e:
                rec['restore_error'] = repr(e)
                log('🔴 §3.4 改回失败：%r' % (e,))
    rec['after'] = {'dir': os.path.isdir(BGSEP),
                    'files': sorted(os.listdir(BGSEP)) if os.path.isdir(BGSEP) else None}
    rec['restored'] = rec['after']['dir'] is True
    return rec


# ── §3.5 抽听样片 ────────────────────────────────────────────────────
def make_clip(name):
    """跑一条样片臂 ⇒ player_mix.wav ⇒ ≤1 MB 的 OGG。"""
    wav = os.path.join(CLIPS, '%s.wav' % name)
    if not os.path.isfile(wav):
        log('🔴 片段缺失：%s' % wav)
        return None
    cwd = os.path.join(OUT_ROOT, 'clip_%s' % name)
    os.makedirs(cwd, exist_ok=True)
    rec = {'clip': name, 'media': wav, 'dir': cwd,
           'ts': datetime.datetime.now().isoformat(timespec='seconds')}
    p, ready, rs = start_bridge(cwd)
    rec['bridge_ready'] = ready
    rec['bridge_ready_s'] = rs
    if not ready:
        stop_bridge(p)
        return rec
    tool = e2e_tool()
    env = bridge_env()
    cmd = [PKG_PY, '-X', 'utf8', tool, '--media', wav, '--port', '8765',
           '--delay', '20', '--target-lang', 'zh', '--voice', 'A',
           '--token-file', os.path.join(cwd, 'bridge_token.txt'),
           '--out', cwd, '--tail-wait', '40']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                           cwd=cwd, env=env)
        rec['e2e_rc'] = r.returncode
        with open(os.path.join(cwd, 'e2e_stdout.txt'), 'w', encoding='utf-8') as f:
            f.write((r.stdout or '') + (r.stderr or ''))
    except subprocess.TimeoutExpired:
        rec['e2e_rc'] = 'TIMEOUT'
    stop_bridge(p)

    mix = os.path.join(cwd, 'player_mix.wav')
    rec['player_mix_exists'] = os.path.isfile(mix)
    if rec['player_mix_exists']:
        rec['player_mix_bytes'] = os.path.getsize(mix)
        ogg = os.path.join(RESULTS, 'app129_listen_%s.ogg' % name)
        ok, info = wav_to_ogg(mix, ogg)
        rec['ogg'] = ogg
        rec['ogg_ok'] = bool(ok)
        rec['ogg_info'] = info
        log('§3.5 %s：player_mix=%d B → ogg=%s（%s）'
            % (name, rec['player_mix_bytes'], ogg,
               json.dumps(info, ensure_ascii=False)))
    # 指标
    jf = os.path.join(cwd, 'bgkeep_e2e.json')
    if os.path.isfile(jf):
        try:
            d = json.load(open(jf, encoding='utf-8'))
            rec['metrics'] = {k: d.get(k) for k in
                              ('duration_s', 'dubs', 'bg_blocks',
                               'bg_late_blocks', 'fallback_to_orig_s',
                               'dub_late_vs_play_s')}
            rec['metrics']['bg_status_last'] = d.get('bg_status_last')
        except Exception as e:
            rec['metrics_error'] = repr(e)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-degrade', action='store_true')
    args = ap.parse_args()
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': PKG, 'clips': [], 'degradation': None}
    lock = B.acquire_lock('app bgkeep v2.6 clips+degrade')
    try:
        if not args.skip_degrade:
            rep['degradation'] = check_degradation()
        for name in CLIP_ORDER[:MAX_CLIPS]:
            r = make_clip(name)
            if r:
                rep['clips'].append(r)
            with open(os.path.join(RESULTS, 'app129_clips_v26_evidence.json'),
                      'w', encoding='utf-8') as f:
                json.dump(rep, f, ensure_ascii=False, indent=2)
    finally:
        B.release_lock(lock)
    log('证据：results/app/app129_clips_v26_evidence.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
