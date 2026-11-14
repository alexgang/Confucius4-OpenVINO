#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app551_open1_two_arm.py —— APP-108 §3：**0xC0000409 退出码**的两臂对照。

**reviewer 原文**：
  「持锁跑 10 分钟片段，两臂：MT=NPU+TTS off、MT=GPU.0+TTS=CUDA。
    看哪一臂会 abort，并附 Windows 事件日志（Application Error / WER 的
    faulting module）。在定位之前，验收结论改写为「PASS（有 1 项未结：
    退出码异常）」，不要写 13/13。」

🔴 **实测口径**：
  · 两臂**同机、同包、同一段 10 分钟音频**（`test_audio/clip_10min_0_600.wav`）；
  · 设备组合由 **CLI 显式指定** ⇒ 不受 `device_config.json` 影响；
  · 真实 `%LOCALAPPDATA%\\Confucius4LiveCaption\\device_config.json`
    **跑前跑后各取一次 SHA**（CLI 路径**不调** `save_config` ⇒ 应不变）；
  · 每臂**前后**各查一次 Windows Application 事件日志
    （ID 1000 = Application Error / ID 1001 = WER）⇒ 抓 faulting module；
  · 另扫 `C:\\ProgramData\\Microsoft\\Windows\\WER\\ReportArchive` 里
    与 0xC0000409 相关的新报告。

用法：
    python _app551_open1_two_arm.py <包目录>
"""
import hashlib
import json
import os
import subprocess
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
AUDIO = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
REAL_CFG = os.path.join(HOME, 'AppData', 'Local', 'Confucius4LiveCaption',
                        'device_config.json')
WER_DIR = r'C:\ProgramData\Microsoft\Windows\WER\ReportArchive'

ARMS = [
    {'id': 'A_mt_npu_tts_off',
     'desc': 'MT=NPU + TTS off（完全不碰 CUDA）',
     'args': ['--mt-device', 'NPU', '--tts', 'off']},
    {'id': 'B_mt_gpu0_tts_cuda',
     'desc': 'MT=GPU.0 + TTS=CUDA（真 CUDA 边车）',
     'args': ['--mt-device', 'GPU.0', '--tts-device', 'CUDA', '--tts', 'on']},
    {'id': 'C_mt_npu_tts_cuda',
     'desc': 'MT=NPU + TTS=CUDA（**阳性对照**＝ sp1 原始 abort 的那一组，'
             '同时就是 **sp2 的出厂默认**）',
     'args': ['--mt-device', 'NPU', '--tts-device', 'CUDA', '--tts', 'on']},
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def real_cfg_state():
    if not os.path.isfile(REAL_CFG):
        return {'exists': False}
    st = os.stat(REAL_CFG)
    return {'exists': True, 'bytes': st.st_size,
            'sha256': sha256_file(REAL_CFG), 'mtime': st.st_mtime}


def eventlog_window(t0, t1):
    """查 Application 日志里 ID 1000 / 1001 的条目（窗口前后各放宽）。"""
    s = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0 - 120))
    e = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t1 + 180))
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Get-WinEvent -FilterHashtable @{LogName='Application';"
        "StartTime=(Get-Date '%s');EndTime=(Get-Date '%s')} -ErrorAction "
        "SilentlyContinue | Where-Object { $_.Id -eq 1000 -or $_.Id -eq 1001 } "
        "| ForEach-Object { "
        "'=== Id={0} Provider={1} Time={2:yyyy-MM-dd HH:mm:ss} ===' -f "
        "$_.Id,$_.ProviderName,$_.TimeCreated; $_.Message }"
        % (s, e))
    p = subprocess.run(['powershell', '-NoProfile', '-NonInteractive',
                        '-Command', ps], capture_output=True, text=True,
                       timeout=300)
    txt = (p.stdout or '')
    return txt.strip()


def wer_scan(since_ts):
    """扫 WER 报告目录里新出现的 0xC0000409 相关报告（faulting module）。"""
    out = []
    if not os.path.isdir(WER_DIR):
        return out
    try:
        names = os.listdir(WER_DIR)
    except Exception:
        return out
    for n in names:
        p = os.path.join(WER_DIR, n)
        try:
            mt = os.path.getmtime(p)
        except Exception:
            continue
        if mt < since_ts:
            continue
        item = {'dir': n, 'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                                 time.localtime(mt))}
        rp = os.path.join(p, 'Report.wer')
        if os.path.isfile(rp):
            try:
                txt = open(rp, encoding='utf-8', errors='replace').read()
                for ln in txt.splitlines():
                    if ln.startswith('Sig[') and 'Name' in ln:
                        item.setdefault('sig', []).append(ln.strip())
                    if 'DynamicSig' in ln and 'Name' in ln:
                        item.setdefault('sig', []).append(ln.strip())
                    if ln.startswith('AppPath=') or ln.startswith('AppName='):
                        item.setdefault('app', []).append(ln.strip())
            except Exception:
                pass
        out.append(item)
    return out


def run_arm(pkg, arm, ev):
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    out_wav = os.path.join(RESULTS, '_app551_%s_tts.wav' % arm['id'])
    out_txt = os.path.join(RESULTS, '_app551_%s_out.txt' % arm['id'])
    cmd = [py, app, '--cli', '--file', AUDIO,
           '--asr-device', 'GPU.0',
           '--translate', 'zh'] + arm['args'] + \
          ['--tts-out', out_wav, '--out', out_txt]
    before = real_cfg_state()
    t0 = time.time()
    print('[arm %s] 起：%s' % (arm['id'], ' '.join(cmd)), flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=5400,
                       cwd=os.path.join(pkg, 'app'))
    t1 = time.time()
    after = real_cfg_state()
    so, se = p.stdout or '', p.stderr or ''
    logp = os.path.join(RESULTS, '_app551_%s.log' % arm['id'])
    with open(logp, 'w', encoding='utf-8') as f:
        f.write('CMD: %r\nRC=%d\nELAPSED_S=%.1f\n--- STDOUT ---\n%s\n'
                '--- STDERR ---\n%s\n' % (cmd, p.returncode, t1 - t0, so, se))
    tel = [ln for ln in so.splitlines() if ln.startswith('    [TTS]')]
    rec = {
        'id': arm['id'], 'desc': arm['desc'], 'cmd': cmd,
        'rc': p.returncode,
        'rc_hex': ('0x%08X' % (p.returncode & 0xFFFFFFFF)
                   if p.returncode < 0 else None),
        'elapsed_s': round(t1 - t0, 1),
        'start': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0)),
        'end': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t1)),
        'tts_out_exists': os.path.isfile(out_wav),
        'tts_out_bytes': (os.path.getsize(out_wav)
                          if os.path.isfile(out_wav) else None),
        'out_txt_exists': os.path.isfile(out_txt),
        'out_txt_bytes': (os.path.getsize(out_txt)
                          if os.path.isfile(out_txt) else None),
        'real_cfg_before': before, 'real_cfg_after': after,
        'real_cfg_unchanged': (before.get('sha256') == after.get('sha256')),
        'stdout_tail': so[-6000:], 'stderr_tail': se[-3000:],
        'tts_telemetry_lines': tel[-20:],
        'log': logp,
        'eventlog': eventlog_window(t0, t1),
        'wer_reports': wer_scan(t0 - 600),
    }
    print('[arm %s] rc=%d (%.1f s)  eventlog=%d B'
          % (arm['id'], p.returncode, t1 - t0, len(rec['eventlog'])),
          flush=True)
    return rec


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pkg = sys.argv[1]
    # 🔴 可选：环境变量 `ARM_SELECT` 只跑指定的臂（逗号分隔 id 片段），
    #    `OUT_NAME` 指定输出文件名 ⇒ 阳性对照臂可单独跑、不覆盖前面的证据。
    sel = os.environ.get('ARM_SELECT', '')
    out_name = os.environ.get('OUT_NAME', 'app551_open1_two_arm.json')
    arms = ARMS
    if sel:
        parts = [s.strip() for s in sel.split(',') if s.strip()]
        arms = [a for a in ARMS if any(p in a['id'] for p in parts)]
    out = os.path.join(RESULTS, out_name)
    ev = {'pkg': pkg, 'audio': AUDIO,
          'audio_bytes': (os.path.getsize(AUDIO)
                          if os.path.isfile(AUDIO) else None),
          'arm_select': sel or '(all)',
          'started': time.strftime('%Y-%m-%d %H:%M:%S'),
          'real_cfg_before': real_cfg_state(), 'arms': []}
    for arm in arms:
        try:
            ev['arms'].append(run_arm(pkg, arm, ev))
        except Exception as e:
            ev['arms'].append({'id': arm['id'], 'error': repr(e)})
    ev['real_cfg_after'] = real_cfg_state()
    rcs = [a.get('rc') for a in ev['arms'] if 'rc' in a]
    ev['rcs'] = rcs
    ev['aborted_arms'] = [a['id'] for a in ev['arms']
                          if a.get('rc') == 3221226505]
    ev['all_ok_arms'] = [a['id'] for a in ev['arms'] if a.get('rc') == 0]
    ev['verdict_note'] = (
        'PASS（有 1 项未结：退出码异常）—— 退出码 3221226505 (0xC0000409) '
        '**不并入 PASS 判定**（APP-108 §3）')
    ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('rcs=%s  aborted=%s  -> %s' % (rcs, ev['aborted_arms'], out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
