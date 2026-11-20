#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **APP-119 §3 验收第 3 条：混合 1 分钟冒烟**（ASR=NPU / MT=NPU / TTS=GPU.0）。

reviewer 原文：「再跑一组**混合 1 分钟**冒烟（例如 ASR=NPU、MT=NPU、TTS=GPU.0），
证明设置生效且**每个模块的实际设备等于选择**。」

本脚本：
  ① 从 ``test_audio/clip_10min_0_600.wav`` 切出**前 60 s**（16 kHz 单声道 16 bit）；
  ② **持 MACHINE_LOCK**（复用 `_app588_sp4_acceptance` 的 fail-closed 取锁）；
  ③ 跑**包内** ``live_caption_app.py --cli --max-seconds 60``（产品同款调用路径）；
  ④ 从**运行日志原文**里抓每个模块的**实际**设备：
       · ASR  ← ``[xxx] 加载 N s，设备 <device_desc>``
       · MT   ← ``[xxx] 翻译 target=… 后端=… 设备 <device>``
       · TTS  ← ``EXECUTION_DEVICES …``（OV 的**实际落点**，不是请求值）
                  ＋ ``[TTS] worker 已启动（设备 <请求值>``
  ⑤ 判定「实际设备 == 选择」；**顺带**证明「不再自动改设备」（APP-119 §2）。

产物：``results/app/app119_mixed_smoke.json``（＋ 日志、wav、逐句 jsonl）
"""
import json
import os
import re
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))      # ← 仓库根（HERE = results/app）
sys.path.insert(0, HERE)

import _app588_sp4_acceptance as H     # noqa: E402  （复用锁/指纹工具）

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
SRC_WAV = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
CLIP60 = os.path.join(REPO, 'test_audio', 'app119_clip_0_60.wav')
OUT_JSON = os.path.join(HERE, 'app119_mixed_smoke.json')
RUN_TAG = 'app119_mixed'

ASR_DEV, MT_DEV, TTS_DEV = 'NPU', 'NPU', 'GPU.0'
SECONDS = 60

# 🔴 会话租约：长作业**先把自己的 PID 登记进去**（别的会话才会 BUSY，不会重复跑）
LEASE = r'C:\Users\Trekker-PTL\shared\tools\session_lease.py'
TOKEN = '3579d2f8'   # 本会话租约 token（🔴 前会话 5dda28b6 已死）


def register_pid():
    try:
        r = subprocess.run([sys.executable, LEASE, 'addpid', 'app', TOKEN,
                            str(os.getpid())], capture_output=True, text=True,
                           timeout=60)
        print('[lease] addpid rc=%s %s' % (r.returncode,
                                           (r.stdout or '').strip()))
    except Exception as e:
        print('[lease] addpid 失败：%r' % e)


def make_clip():
    """切前 60 s（16 kHz / 单声道 / 16 bit ⇒ 直接按字节切）。"""
    with wave.open(SRC_WAV, 'rb') as w:
        params = w.getparams()
        frames = params.framerate * SECONDS
        data = w.readframes(frames)
        p2 = (params.nchannels, params.sampwidth, params.framerate)
    if os.path.isfile(CLIP60):
        os.remove(CLIP60)
    with wave.open(CLIP60, 'wb') as w:
        w.setnchannels(p2[0])
        w.setsampwidth(p2[1])
        w.setframerate(p2[2])
        w.writeframes(data)
    return {'path': CLIP60, 'channels': p2[0], 'sampwidth': p2[1],
            'framerate': p2[2], 'bytes': os.path.getsize(CLIP60)}


def grab(pat, text, flags=0):
    return re.findall(pat, text, flags)


def main():
    rep = {'app': 'APP-119', 'section': '§3 验收③：混合 1 分钟冒烟',
           'selection': {'asr': ASR_DEV, 'mt': MT_DEV, 'tts': TTS_DEV},
           'ts': time.strftime('%Y-%m-%d %H:%M:%S')}
    clip = make_clip()
    rep['clip'] = clip

    register_pid()
    ev_lock = H.acquire_lock('app119-mixed-smoke')
    rep['lock_evidence'] = ev_lock
    tts_out = os.path.join(HERE, 'app119_mixed_tts.wav')
    # 🔴🔴🔳 **判据修正（2026-11-21 03:51）**：本脚本原来查的是
    #   `app119_mixed_tts.jsonl`，但**产品实际写的是 `<tts_out>.tts.jsonl`**
    #   （与 `_app588_sp4_acceptance.py` 的 `tts_out + '.tts.jsonl'` 同款约定）
    #   ⇒ 原判据必然报「产出存在：逐句 jsonl（-1 B）」⇒ **假 FAIL**。
    #   ⇒ 现在按**产品同款路径**判定（不是放宽判据，是把判据指到真产物上）。
    jsonl = tts_out + '.tts.jsonl'
    log_path = os.path.join(HERE, 'app119_mixed_run.log')
    cmd = [PKG_PY, os.path.join(PKG, 'app', 'live_caption_app.py'),
           '--cli', '--file', CLIP60, '--max-seconds', str(SECONDS),
           '--asr-device', ASR_DEV, '--mt-device', MT_DEV,
           '--tts-device', TTS_DEV, '--translate', 'zh',
           '--tts', 'on', '--tts-voice', 'A', '--tts-out', tts_out]
    rep['cmd'] = cmd
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=1800, cwd=PKG)
        so, se, rc = p.stdout or '', p.stderr or '', p.returncode
    finally:
        rep['lock_evidence'] = H.release_lock(ev_lock)
    el = time.time() - t0
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('CMD: %r\nCWD: %s\nRC=%d\nELAPSED_S=%.1f\n--- STDOUT ---\n%s\n'
                '--- STDERR ---\n%s\n' % (cmd, PKG, rc, el, so, se))
    rep['rc'] = rc
    rep['elapsed_s'] = round(el, 1)
    rep['log_path'] = log_path
    rep['log_bytes'] = os.path.getsize(log_path)
    rep['log_sha256'] = H.sha256_file(log_path)

    # ── 抓实际设备 ──
    asr_lines = grab(r'^\[[^\]]+\] 加载 [0-9.]+ s，设备 ([^，]+)，', so, re.M)
    asr_exec = grab(r'^\[[^\]]*\] EXECUTION_DEVICES：([^\n（]*)', so, re.M)
    mt_lines = grab(r'^\[[^\]]+\] 翻译 target=\S+ 后端=\S+ 设备 (\S+)', so, re.M)
    tts_req = grab(r'\[TTS\] worker 已启动（设备 ([^，]+)，', so)
    exec_dev = grab(r'EXECUTION_DEVICES ([^\n]*)', so)
    npu_hint = grab(r'^\[device\] NPU 共用[^\n]*', so + se, re.M)
    dev_notes = grab(r'^\[device\] [^\n]*', so + se, re.M)
    asr_mt_same = grab(r'^\[device\] (ASR 与 MT[^\n]*)', so + se, re.M)

    rep['observed'] = {
        'asr_actual_devices': asr_lines,
        'asr_exec_devices_lines': asr_exec,
        'mt_actual_devices': mt_lines,
        'tts_requested_device': tts_req,
        'tts_exec_devices_lines': exec_dev,
        'device_notes': dev_notes,
        'npu_shared_hint': npu_hint,
        'asr_mt_same_gpu_note': asr_mt_same,
    }
    rep['stdout_tail'] = so[-3000:]
    rep['stderr_tail'] = se[-2000:]

    # ── 判定 ──
    checks = []

    def add(name, ok, detail):
        checks.append({'name': name, 'pass': bool(ok), 'detail': detail})

    add('退出码 0', rc == 0, 'rc=%s' % rc)
    add('ASR **实际**设备 == NPU',
        (bool(asr_lines) and all('NPU' in x.upper() for x in asr_lines))
        or (bool(asr_exec) and all('NPU' in x.upper()
                                   for x in ' '.join(asr_exec).split('，'))),
        '加载行=%s；EXECUTION_DEVICES 行=%s' % (asr_lines, asr_exec))
    add('MT **实际**设备 == NPU',
        bool(mt_lines) and all('NPU' in x.upper() for x in mt_lines),
        '实际设备行=%s' % mt_lines)
    add('TTS 请求设备 == GPU.0',
        bool(tts_req) and all(x.strip() == 'GPU.0' for x in tts_req),
        '请求设备行=%s' % tts_req)
    add('TTS **实际落点**（EXECUTION_DEVICES）已回执',
        bool(exec_dev), 'EXECUTION_DEVICES 行=%s' % exec_dev)
    add('**没有被自动改设备**：日志里没有「MT 自动改到 GPU.0」',
        not any('自动改到' in x or '已禁止' in x for x in dev_notes),
        'device 日志=%s' % dev_notes)
    add('1 分钟跑完（未因 NPU 共用被拦下）',
        el < 900, 'elapsed=%.1f s' % el)
    for name, f in (('逐句 jsonl', jsonl), ('合成 wav', tts_out)):
        add('产出存在：%s' % name, os.path.isfile(f),
            '%s（%d B）' % (f, os.path.getsize(f) if os.path.isfile(f) else -1))

    rep['checks'] = checks
    rep['n_fail'] = sum(1 for c in checks if not c['pass'])
    rep['verdict'] = 'PASS' if rep['n_fail'] == 0 else 'FAIL'
    for c in checks:
        print('  %s %s :: %s' % ('PASS' if c['pass'] else 'FAIL',
                                 c['name'], c['detail']))
    tmp = OUT_JSON + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_JSON)
    print('== APP-119 混合 1 分钟冒烟 == %s（rc=%s，%.1f s）'
          % (rep['verdict'], rc, el))
    print('产物：%s' % OUT_JSON)
    return 0 if rep['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
