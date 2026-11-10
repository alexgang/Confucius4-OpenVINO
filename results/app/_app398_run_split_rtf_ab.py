# -*- coding: utf-8 -*-
"""APP-093 §3.6 补做：**换人切段 开/关 的 ASR RTF 对照**（设备跑，持 MACHINE_LOCK）。

🔴 **要回答的问题**（APP-089 §2c-3 / APP-093 §3.6 原文）：
> 「验收时要证明 ASR RTF 没变差」／「再报切段开/关的 ASR RTF」

🔴 **口径（重要）**
* App 里「换人切段」**只有克隆模式一个总闸**（`live_caption_app.py:7538`）
  ⇒ 没有独立的「切段开关」⇒ **严格 A/B = 影子包里的只读探针**
  （`LIVECAP_PROBE_NOSPLIT=1` ⇒ `request_split` 提前返回 ⇒ 其余代码路径完全相同）。
* 臂：
  - **A1/A2** 切段路径**开**（克隆模式 + 探针不抑制）
  - **C1/C2** 切段路径**关**（克隆模式 + 探针抑制 `request_split`）＝ **严格 A/B**
  - **B**   克隆/切段**整体关**（`--tts-voice A`）＝ **背景对照**
* 顺序 **A1 → C1 → C2 → A2 → B**（ABBA 抵消线性漂移；顺序对照 ≠ ABBA）。

🔴 **纪律**
* 持 `C:\\Users\\Trekker-PTL\\shared\\MACHINE_LOCK`（O_CREAT|O_EXCL 原子拿）；
  锁已存在 ⇒ **排队等，不抢**。
* 跑**影子包** `after_split` ⇒ 不碰用户正在测试的安装目录。
* 不在 CPU 上推理/测速；不调 MiniMax（回转写交 reviewer）。
* 每个数字都写来源 json 的路径和字段名。

用法：python _app398_run_split_rtf_ab.py [--lease-token TOKEN]
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

SHADOW = r'C:\Users\Trekker-PTL\_app_shadow\after_split'
OUTROOT = r'C:\Users\Trekker-PTL\_app_shadow\runs5\after_split'
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
MATERIAL = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest\dialog3_tight.wav'
EVID = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app'
OUT_JSON = os.path.join(EVID, 'app398_app093_split_rtf_ab.json')
PROGRESS = os.path.join(EVID, 'app398_progress.json')
PIDFILE = os.path.join(EVID, '_app398_run.pid')

# 臂定义（顺序即执行顺序）
ARMS = [
    ('A1', 'split_on',  False, 'follow_speaker'),
    ('C1', 'split_off', True,  'follow_speaker'),
    ('C2', 'split_off', True,  'follow_speaker'),
    ('A2', 'split_on',  False, 'follow_speaker'),
    ('B',  'clone_off', False, 'A'),
]


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def acquire_lock(tag: str, wait_s: int = 2400) -> int:
    """排队等锁（不抢）。返回 pid；失败返回 -1。"""
    t0 = time.time()
    announced = False
    while time.time() - t0 < wait_s:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write('module=app\npid=%d\nstart=%s\ntag=%s\n'
                        % (os.getpid(), now(), tag))
            return os.getpid()
        except FileExistsError:
            if not announced:
                try:
                    cur = open(LOCK, encoding='utf-8', errors='replace').read()
                except Exception:
                    cur = '(unreadable)'
                print('🔴 MACHINE_LOCK 已存在 ⇒ 排队等待（不抢）：\n%s' % cur,
                      flush=True)
                announced = True
            time.sleep(20)
    return -1


def release_lock() -> None:
    try:
        if os.path.exists(LOCK):
            cur = open(LOCK, encoding='utf-8', errors='replace').read()
            if ('pid=%d' % os.getpid()) in cur:
                os.remove(LOCK)
                print('🔓 MACHINE_LOCK 已释放', flush=True)
    except Exception as e:
        print('⚠️ 释放 MACHINE_LOCK 失败：%s' % e, flush=True)


RTF_RE = re.compile(r'RTF\(计算\)\s*([0-9.]+)')
ASR_RE = re.compile(r'音频\s*([0-9.]+)s\s+墙钟\s*([0-9.]+)s\s+RTF\(计算\)\s*'
                    r'([0-9.]+)\s+出字延迟中位\s*(\d+)\s*ms\s+'
                    r'最大积压\s*([0-9.]+)s\s+段\s*(\d+)')


def parse_run(out: str) -> dict:
    log = os.path.join(out, 'run.log')
    txt = open(log, encoding='utf-8', errors='replace').read()
    r = {'log_path': log, 'log_bytes': os.path.getsize(log)}

    ms = list(ASR_RE.finditer(txt))
    if ms:
        m = ms[-1]
        r['asr_line'] = m.group(0)
        r['asr_audio_s'] = float(m.group(1))
        r['asr_wall_s'] = float(m.group(2))
        r['asr_rtf'] = float(m.group(3))
        r['asr_first_token_latency_ms'] = int(m.group(4))
        r['asr_max_backlog_s'] = float(m.group(5))
        r['asr_n_seg'] = int(m.group(6))
    else:
        r['asr_line'] = None
        r['asr_rtf'] = None

    # 探针计数
    r['n_probe_request'] = txt.count('[split-probe] request')
    r['n_probe_bail'] = txt.count('[split-probe] bail')
    r['n_probe_done'] = txt.count('[split-probe] done')
    r['split_enc_ready_logged'] = ('说话人切分编码器已就绪' in txt)
    r['split_unavailable_logged'] = ('说话人切分不可用' in txt)
    r['probe_lines_sample'] = [ln.strip() for ln in txt.splitlines()
                               if '[split-probe]' in ln][:6]
    # 设备证据
    r['exec_devices_lines'] = [ln.strip() for ln in txt.splitlines()
                               if 'EXECUTION_DEVICES' in ln][:8]
    r['device_head_lines'] = [ln.strip() for ln in txt.splitlines()
                              if ('Intel' in ln and ('NPU' in ln or 'GPU' in ln))
                              ][:6]

    # spk_seg.jsonl
    sp = os.path.join(out, 'spk_seg.jsonl')
    if os.path.exists(sp):
        rows = []
        for line in open(sp, encoding='utf-8', errors='replace'):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
        r['spk_seg'] = {
            'path': sp, 'bytes': os.path.getsize(sp), 'sha256': sha256_file(sp),
            'n_rows': len(rows),
            'n_split_dist': dict(collections.Counter(
                row.get('n_split') for row in rows)),
            'spk_dist': dict(collections.Counter(
                row.get('spk') for row in rows)),
            'n_mixed_spk': sum(1 for row in rows if row.get('mixed_spk')),
        }

    # tts.jsonl
    tj = os.path.join(out, 'tts.jsonl')
    if os.path.exists(tj):
        rows = []
        for line in open(tj, encoding='utf-8', errors='replace'):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
        rtfs = [float(r0['synth_rtf']) for r0 in rows
                if r0.get('synth_rtf') not in (None, '')]
        rtfs.sort()

        def p50(v):
            if not v:
                return None
            k = len(v) // 2
            return v[k] if len(v) % 2 else (v[k - 1] + v[k]) / 2.0
        r['tts'] = {
            'path': tj, 'bytes': os.path.getsize(tj), 'sha256': sha256_file(tj),
            'n_rows': len(rows),
            'synth_rtf_p50': p50(rtfs),
            'end_reason_dist': dict(collections.Counter(
                str(r0.get('end_reason')) for r0 in rows)),
            'n_late_drop': sum(1 for r0 in rows if r0.get('late_drop')),
            'n_clone_voice_rows': sum(
                1 for r0 in rows if r0.get('voice_kind') == 'clone'),
        }

    arts = {}
    for dp, _dn, fn in os.walk(out):
        for f in fn:
            p2 = os.path.join(dp, f)
            arts[os.path.relpath(p2, out).replace('\\', '/')] = {
                'bytes': os.path.getsize(p2),
                'sha256': sha256_file(p2),
                'mtime': datetime.datetime.fromtimestamp(
                    os.path.getmtime(p2)).strftime('%Y-%m-%d %H:%M:%S'),
            }
    r['artifacts'] = arts
    r['n_artifacts'] = len(arts)
    return r


def run_arm(arm: str, kind: str, nosplit: bool, voice: str) -> dict:
    out = os.path.join(OUTROOT, arm)
    os.makedirs(out, exist_ok=True)
    cmd = [
        os.path.join(SHADOW, 'python', 'python.exe'),
        os.path.join(SHADOW, 'app', 'live_caption_app.py'),
        '--cli', '--file', MATERIAL,
        '--speaker', 'on', '--tts', 'on', '--tts-voice', voice,
        '--tts-precision', 'f16', '--tts-device', 'NPU',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--out', os.path.join(out, 'subtitles.txt'),
        '--tts-out', os.path.join(out, 'mix.wav'),
        '--tts-jsonl', os.path.join(out, 'tts.jsonl'),
        '--tts-dump-dir', os.path.join(out, 'dump'),
        '--spk-seg-jsonl', os.path.join(out, 'spk_seg.jsonl'),
    ]
    env = dict(os.environ)
    clone_dir = os.path.join(out, 'clone_voices')
    os.makedirs(clone_dir, exist_ok=True)
    env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir
    if nosplit:
        env['LIVECAP_PROBE_NOSPLIT'] = '1'
    else:
        env.pop('LIVECAP_PROBE_NOSPLIT', None)

    log_path = os.path.join(out, 'run.log')
    started = now()
    print('▶ [%s] kind=%s nosplit=%s voice=%s' % (arm, kind, nosplit, voice),
          flush=True)
    t0 = time.time()
    rc = -1
    with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
        lf.write('# cmd=%s\n# started=%s\n' % (json.dumps(cmd), started))
        lf.write('# env LIVECAP_PROBE_NOSPLIT=%s\n'
                 % env.get('LIVECAP_PROBE_NOSPLIT', '(unset)'))
        lf.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             encoding='utf-8', errors='replace',
                             bufsize=1, env=env, cwd=SHADOW)
        for line in p.stdout:
            lf.write(line)
            lf.flush()
            if ('RTF(计算)' in line or '[split-probe]' in line
                    or '换人' in line or '切段' in line):
                print(line.rstrip(), flush=True)
        rc = p.wait()
    dur = time.time() - t0
    finished = now()
    print('✔ [%s] rc=%d %.1f s' % (arm, rc, dur), flush=True)

    res = parse_run(out)
    res.update({'arm': arm, 'kind': kind, 'nosplit_probe': nosplit,
                'tts_voice': voice, 'rc': rc, 'cmd': cmd,
                'started': started, 'finished': finished,
                'wall_s': round(dur, 1),
                'material': MATERIAL,
                'material_sha256': sha256_file(MATERIAL),
                'material_bytes': os.path.getsize(MATERIAL),
                'out_dir': out})
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--lease-token', default='')
    args = ap.parse_args()

    with open(PIDFILE, 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    print('pid=%d lease_token=%s' % (os.getpid(), args.lease_token), flush=True)

    os.makedirs(OUTROOT, exist_ok=True)
    pid = acquire_lock('app093_split_rtf_ab')
    if pid < 0:
        print('🔴 排队超时未拿到 MACHINE_LOCK ⇒ 本轮放弃（不抢锁）', flush=True)
        with open(PROGRESS, 'w', encoding='utf-8') as f:
            json.dump({'status': 'lock_timeout', 'at': now()}, f,
                      ensure_ascii=False, indent=1)
        return 2
    print('🔒 MACHINE_LOCK pid=%d' % pid, flush=True)

    runs = []
    lock_record = {'module': 'app', 'pid': pid, 'start': now(),
                   'lock_path': LOCK,
                   'lock_content': open(LOCK, encoding='utf-8',
                                        errors='replace').read()}
    try:
        for arm, kind, nosplit, voice in ARMS:
            r = run_arm(arm, kind, nosplit, voice)
            runs.append(r)
            with open(PROGRESS, 'w', encoding='utf-8') as f:
                json.dump({'status': 'running', 'at': now(),
                           'done': [x['arm'] for x in runs],
                           'rtf': {x['arm']: x.get('asr_rtf') for x in runs}},
                          f, ensure_ascii=False, indent=1)
    finally:
        release_lock()

    def rtf(arm):
        for r in runs:
            if r['arm'] == arm:
                return r.get('asr_rtf')
        return None

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return (sum(vals) / len(vals)) if vals else None

    a = [rtf('A1'), rtf('A2')]
    c = [rtf('C1'), rtf('C2')]
    b = rtf('B')
    summary = {
        'asr_rtf_split_on': {'A1': a[0], 'A2': a[1], 'mean': mean(a)},
        'asr_rtf_split_off_strict': {'C1': c[0], 'C2': c[1], 'mean': mean(c)},
        'asr_rtf_clone_off_context': {'B': b},
        'delta_split_on_minus_off_strict': (
            (mean(a) - mean(c)) if (mean(a) is not None and mean(c) is not None)
            else None),
        'delta_split_on_minus_clone_off': (
            (mean(a) - b) if (mean(a) is not None and b is not None) else None),
    }

    out = {
        'created_at': now(),
        'correction': 'APP-093 §3.6（切段开/关 的 ASR RTF 对照）',
        'question': ('APP-089 §2c-3「验收时要证明 ASR RTF 没变差」/'
                     'APP-093 §3.6「再报切段开/关的 ASR RTF」'),
        'method': ('影子包 after_split；同一次持锁会话内 ABBA 顺序跑 '
                   'A1(切段开)→C1(切段关)→C2(切段关)→A2(切段开)→B(克隆整体关)；'
                   '材料 dialog3_tight.wav；ASR RTF 取 run.log 尾行「RTF(计算)」'),
        'device_job': True,
        'lock_record': lock_record,
        'lock_released': not os.path.exists(LOCK),
        'shadow': {
            'root': SHADOW,
            'app_from': r'C:\Users\Trekker-PTL\_app_shadow\after2\app',
            'live_caption_app_py': 'dev HEAD (25b1626c…)',
            'clone_voice_py': 'dev HEAD + 只读探针（见 app398_probe_patch.diff）',
            'models_python': '联接 → Confucius4_LiveCaption_v2.4',
        },
        'probe': {
            'file': 'results/app/app398_probe_patch.diff',
            'env_switch': 'LIVECAP_PROBE_NOSPLIT=1 ⇒ request_split 提前返回',
            'note': '探针**只加日志 + 一个 env 门控提前返回**；不改任何判定/阈值',
        },
        'arms': runs,
        'summary': summary,
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(PROGRESS, 'w', encoding='utf-8') as f:
        json.dump({'status': 'done', 'at': now(), 'summary': summary}, f,
                  ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1), flush=True)
    print('OUT=%s' % OUT_JSON, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
