#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app581_open1_sp1_rerun.py —— APP-110 §0③：**用 sp1 原命令原样重跑 1 次**。

**reviewer 原文**：
  「要做：从 app536 的 cmd 和会话日志核实 sp1 那次 MT/TTS 的实际设备，写进 STATUS。
    然后持锁、用 **sp1 原命令原样**（同一个 10 分钟片段）重跑 1 次。
    · 如果仍是 rc=0：OPEN-1 记为「未复现（原始 1 次 abort；之后 sp2 三臂加
      sp1 复跑 0/4）」，open_issue 保留，**停止定位**，不再加臂。
      不要改 WER、LocalDumps 等系统设置。
    · 如果复现：附上 rc、退出前最后 50 行日志和事件日志查询结果，报 reviewer，
      不要自行修改。」

🔴 **「sp1 原命令」的出处（不是猜的）**：
   `results/app/_app538_chain_rerun.py`（11-13 21:07 跑的就是它）里的 `cmd` 逐字：
       [<sp1>\\python\\python.exe, <sp1>\\app\\live_caption_app.py,
        '--cli', '--file', <test_audio\\clip_10min_0_600.wav>,
        '--asr-device', 'GPU.0', '--mt-device', 'NPU',
        '--tts-device', 'CUDA', '--translate', 'zh', '--tts', 'on',
        '--tts-out', <results\\app\\_app538_special_tts_out.wav>]
       cwd = <sp1>
   ⇒ 那一次 rc=3221226505 (0xC0000409)，elapsed 616.6 s。

🔴 **唯一与原命令的差别**：`--tts-out` 换成新文件名
   （`_app581_sp1_rerun_tts_out.wav`）⇒ **不覆盖 11-13 的原始证据**
   （`_app538_special_tts_out.wav` 29 416 364 B 保持原样）。其余**逐字相同**。

🔴 **只读**：只查 Windows Application 事件日志（ID 1000/1001）与 WER 报告目录，
   **不写 WER、不动 LocalDumps、不改任何系统设置**（reviewer 明文）。
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
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1')
AUDIO = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
REAL_CFG = os.path.join(HOME, 'AppData', 'Local', 'Confucius4LiveCaption',
                        'device_config.json')
WER_DIR = r'C:\ProgramData\Microsoft\Windows\WER\ReportArchive'
TTS_OUT = os.path.join(RESULTS, '_app581_sp1_rerun_tts_out.wav')
LOG = os.path.join(RESULTS, '_app581_sp1_rerun.log')
OUT_JSON = os.path.join(RESULTS, 'app581_open1_sp1_rerun.json')

#: 11-13 那次（_app538_chain_rerun.py）的命令 —— **逐字照抄**
ORIGINAL_CMD = [
    os.path.join(PKG, 'python', 'python.exe'),
    os.path.join(PKG, 'app', 'live_caption_app.py'),
    '--cli', '--file', AUDIO,
    '--asr-device', 'GPU.0',
    '--mt-device', 'NPU',
    '--tts-device', 'CUDA',
    '--translate', 'zh',
    '--tts', 'on',
    '--tts-out', TTS_OUT,
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as h_:
        pass
    return h.hexdigest()


def sha256_of(p):
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
            'sha256': sha256_of(REAL_CFG), 'mtime': st.st_mtime}


def eventlog_window(t0, t1):
    """查 Application 日志里 ID 1000（Application Error）/ 1001（WER）。"""
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
    return (p.stdout or '').strip()


def wer_scan(since_ts):
    """**只读**扫 WER 报告目录里新出现的报告（faulting module）。"""
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
                    if (ln.startswith('Sig[') or 'DynamicSig' in ln) \
                            and 'Name' in ln:
                        item.setdefault('sig', []).append(ln.strip())
                    if ln.startswith('AppPath=') or ln.startswith('AppName='):
                        item.setdefault('app', []).append(ln.strip())
            except Exception:
                pass
        out.append(item)
    return out


def main():
    if not os.path.isdir(PKG):
        print('sp1 包不存在：%s' % PKG)
        return 2
    if not os.path.isfile(AUDIO):
        print('10 分钟片段不存在：%s' % AUDIO)
        return 2
    before = real_cfg_state()
    cmd = list(ORIGINAL_CMD)
    ev = {
        'purpose': 'APP-110 §0③：用 sp1 原命令原样复跑 1 次（同一 10 分钟片段）',
        'pkg': PKG, 'audio': AUDIO,
        'audio_bytes': os.path.getsize(AUDIO),
        'cmd': cmd,
        'cmd_diff_vs_original': (
            '仅 --tts-out 换成 %s（避免覆盖 11-13 原始证据 '
            '_app538_special_tts_out.wav）；其余逐字相同'
            % os.path.basename(TTS_OUT)),
        'original_run_ref': ('results/app/_app538_chain_rerun.py（11-13 21:07）'
                             '⇒ rc=3221226505, elapsed=616.6 s'),
        'started': time.strftime('%Y-%m-%d %H:%M:%S'),
        'real_cfg_before': before,
    }
    t0 = time.time()
    print('[sp1 复跑] 起：%s' % ' '.join(cmd), flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=5400,
                       cwd=PKG)
    t1 = time.time()
    after = real_cfg_state()
    so, se = p.stdout or '', p.stderr or ''
    with open(LOG, 'w', encoding='utf-8') as f:
        f.write('CMD: %r\nCWD: %s\nRC=%d\nELAPSED_S=%.1f\n'
                '--- STDOUT ---\n%s\n--- STDERR ---\n%s\n'
                % (cmd, PKG, p.returncode, t1 - t0, so, se))
    so_lines = so.splitlines()
    se_lines = se.splitlines()
    ev.update({
        'rc': p.returncode,
        'rc_hex': ('0x%08X' % (p.returncode & 0xFFFFFFFF)
                   if 0 <= p.returncode <= 0xFFFFFFFF else None),
        'elapsed_s': round(t1 - t0, 1),
        'start': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0)),
        'end': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t1)),
        'tts_out_exists': os.path.isfile(TTS_OUT),
        'tts_out_bytes': (os.path.getsize(TTS_OUT)
                          if os.path.isfile(TTS_OUT) else None),
        'real_cfg_after': after,
        'real_cfg_unchanged': (before.get('sha256') == after.get('sha256')),
        'stdout_last50': so_lines[-50:],
        'stderr_last50': se_lines[-50:],
        'stdout_tail': so[-6000:],
        'stderr_tail': se[-3000:],
        'log': LOG,
        'eventlog_query': eventlog_window(t0, t1),
        'wer_reports': wer_scan(t0 - 600),
        'device_evidence': {
            'mt': [ln[:200] for ln in so_lines if '翻译' in ln and '设备' in ln],
            'tts_cuda_sidecar': [ln[:200] for ln in so_lines
                                 if 'tts_cuda' in ln][:5],
            'asr': [ln[:200] for ln in so_lines if '[ASR]' in ln][:5],
        },
        'tts_final_stats': [ln[:240] for ln in so_lines
                             if '最终统计' in ln or '收尾' in ln],
    })
    ev['reproduced'] = (p.returncode == 3221226505)
    if ev['reproduced']:
        ev['open1_status'] = '**复现**（rc=3221226505）⇒ 报 reviewer，不自行修改'
    else:
        ev['open1_status'] = (
            '未复现（原始 1 次 abort；之后 sp2 三臂加 sp1 复跑 0/4）'
            '⇒ open_issue 保留，**停止定位**，不再加臂')
    ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[sp1 复跑] rc=%d (%.1f s) reproduced=%s'
          % (p.returncode, t1 - t0, ev['reproduced']), flush=True)
    print('  → %s' % OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
