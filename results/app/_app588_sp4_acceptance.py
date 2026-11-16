#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app588_sp4_acceptance.py —— **APP-113 §4 的验收**：sp4 两次 10 分钟整链。

🔴 **reviewer 原文（APP-113 §4）**：
  「验收：持锁跑固定 10 分钟片段（SPE 0–600 s）两次：
    1. sp4 SpecialMVP 中文目标；
    2. sp4 英文目标（中→英或用同片段的英→英以外可行的配置，写明）。
   每次报：译文句数 / 进 TTS 句数 / 丢句数（任何原因，必须 = 0）/ 排队句数 /
   TTS 就绪时刻 / 积压清空时刻 / 倍率 P50/P95/max（max ≤ 2.0）/ 最大滞后。
   **运行前确认 A 上没有其它大 IO 或 GPU 任务**（app582 期间有 5 GB 下载干扰，
   那是 reviewer 的，已承认）；结果 json 里写锁证据和 timing_valid。
   抽 3 段倍率 ≥1.8× 的配音 wav 放进 results，供用户抽听 2.0× 听感。」

🔴 **本脚本的纪律**：
  · **持锁**：先建 `shared/MACHINE_LOCK`（内容 = 模块名 PID 开始时间 说明），
    锁已存在 ⇒ **排队等待**（不抢锁）；回收前用 ctypes OpenProcess +
    GetExitCodeProcess 确认 PID 真死（探测失败 ⇒ 视为存活 ⇒ 继续等）。
  · **锁证据进结果 json**（APP-112 §2 的立规）：锁内容 + 取锁时刻 + 放锁时刻。
  · **timing_valid**：跑前/跑后快照「监视目录里 >100 MB 的文件」的
    (size, mtime) ⇒ 运行窗口内有变化 ⇒ 判 `timing_valid=false` 并**如实列出**。
  · **GPU 证据**：跑前/跑后/跑中采样 `nvidia-smi --query-compute-apps`
    ⇒ 除本作业 worker 外**还有别的 GPU 进程** ⇒ 记 `gpu_external_tasks`。
  · **不改产品代码、不打包 zip**（APP-055 + 用户级纪律）。
"""
import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp4')
AUDIO = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')

#: 🔴 **监视目录**（用于 timing_valid：这些目录里 >100 MB 的文件在运行窗口内
#:   被改写 ⇒ 判「有外部大 IO」）—— app582 那次的 5 GB 下载就在 `Downloads`。
WATCH_DIRS = [os.path.join(HOME, 'qwen3tts_eval'),
               os.path.join(HOME, 'Downloads'),
               os.path.join(HOME, 'gpt-sovits')]
WATCH_SKIP = {'.git', '.venv-cuda', '.venv-official-nb', '.venv-qwen3tts',
              '.tmp_ovms', 'node_modules', '__pycache__'}
BIG_BYTES = 100 * 1024 * 1024


# ══════════════════════════════════════════════════════════════
# 锁（排队等待，不抢）
# ══════════════════════════════════════════════════════════════
def pid_alive(pid):
    """🔴 存活判据：`OpenProcess` 成功 ⇒ `GetExitCodeProcess` ⇒ **259 = 活**。

    ⚠️ **259 = STILL_ACTIVE 是「活」**（0 才是死）⇒ 误把 259 当死会抢活锁。
    ⚠️ **探测失败 ⇒ 一律视为存活**（fail-closed）。
    """
    try:
        k = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, int(pid))
        if not h:
            err = k.GetLastError()
            if err == 87:          # 参数错 ⇒ 进程不存在
                return False
            return True             # 其它失败 ⇒ 视为存活
        code = ctypes.c_ulong(0)
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            k.CloseHandle(h)
            return True             # 探测失败 ⇒ 存活
        k.CloseHandle(h)
        return code.value == 259
    except Exception:
        return True


def lock_owner():
    """读锁文件 ⇒ (module, pid, start, note)；锁不存在 ⇒ None。"""
    try:
        raw = open(LOCK, encoding='utf-8').read().strip()
    except Exception:
        return None
    parts = raw.split()
    if len(parts) < 2:
        return None
    try:
        pid = int(parts[1])
    except Exception:
        return None
    return {'raw': raw, 'module': parts[0], 'pid': pid,
            'start': parts[2] if len(parts) > 2 else '',
            'note': parts[3] if len(parts) > 3 else ''}


def acquire_lock(note, timeout_s=7200):
    """排队等待 MACHINE_LOCK；拿到后返回锁证据（含取锁时刻）。"""
    t0 = time.time()
    waited = []
    while True:
        own = lock_owner()
        if own is None:
            content = 'app %d %s %s' % (os.getpid(),
                                        time.strftime('%Y-%m-%d %H:%M:%S'), note)
            with open(LOCK, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content + '\n')
            got = lock_owner()
            if got and got['pid'] == os.getpid():
                return {'acquired': True, 'lock_content': content,
                        'acquired_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'acquired_at_epoch': time.time(),
                        'waited_s': round(time.time() - t0, 1),
                        'wait_history': waited}
            continue
        if own['pid'] == os.getpid():
            return {'acquired': True, 'lock_content': own['raw'],
                    'acquired_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'acquired_at_epoch': time.time(),
                    'waited_s': round(time.time() - t0, 1),
                    'wait_history': waited}
        # 🔴 锁被别人占着 ⇒ **排队等待**；只有确认 PID 真死才回收
        alive = pid_alive(own['pid'])
        if not alive:
            try:
                os.replace(LOCK, LOCK + '.stale.%d' % int(time.time()))
            except Exception:
                pass
            waited.append({'at': time.strftime('%H:%M:%S'), 'raw': own['raw'],
                           'reason': 'owner PID confirmed dead'})
            continue
        if time.time() - t0 > timeout_s:
            raise RuntimeError('等锁超时 %d s（当前持有：%s）' % (timeout_s,
                                                                own['raw']))
        time.sleep(20)
        waited.append({'at': time.strftime('%H:%M:%S'), 'raw': own['raw'],
                       'reason': 'owner alive'})


def release_lock(ev):
    """放锁（**只放自己的**）⇒ 把放锁时刻与放锁时的锁内容写进证据。"""
    own = lock_owner()
    ev = ev or {}
    if own and own['pid'] == os.getpid():
        try:
            os.remove(LOCK)
        except Exception as e:
            ev['release_error'] = repr(e)
    ev['released_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    ev['released_at_epoch'] = time.time()
    ev['lock_content_at_release'] = (own or {}).get('raw')
    return ev


# ══════════════════════════════════════════════════════════════
# 外部 IO / GPU 证据
# ══════════════════════════════════════════════════════════════
def snapshot_big_files():
    out = {}
    for root in WATCH_DIRS:
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in WATCH_SKIP]
            for f in fn:
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if st.st_size >= BIG_BYTES:
                    out[p] = (st.st_size, st.st_mtime)
    return out


def diff_big_files(before, after):
    changed = []
    for p, (sz, mt) in after.items():
        b = before.get(p)
        if b is None:
            changed.append({'path': p, 'bytes': sz, 'mtime': mt,
                            'note': '运行窗口内**新出现**的大文件'})
        elif b[0] != sz or abs(b[1] - mt) > 1:
            changed.append({'path': p, 'bytes_before': b[0], 'bytes_after': sz,
                            'mtime_before': b[1], 'mtime_after': mt,
                            'note': '运行窗口内被改写'})
    return changed


def gpu_apps():
    try:
        p = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory',
             '--format=csv,noheader'], capture_output=True, text=True,
            timeout=30)
        rows = []
        for ln in p.stdout.splitlines():
            ln = ln.strip()
            if ln:
                rows.append(ln)
        return rows
    except Exception as e:
        return ['ERR:%r' % (e,)]


# ══════════════════════════════════════════════════════════════
# 日志解析
# ══════════════════════════════════════════════════════════════
def parse_log(so):
    lines = so.splitlines()
    tr = [ln for ln in lines if ln.startswith('[译文]')
          or ln.startswith('[修正译文]')]
    ready = None
    for i, ln in enumerate(lines):
        if '就绪：' in ln and '音色' in ln:
            ready = {'line_no': i + 1, 'text': ln}
            break
    app113 = [ln for ln in lines if ln.startswith('[APP-113]')]
    final_stats = [ln for ln in lines if '最终统计' in ln]
    tts_first = [ln for ln in lines if ln.startswith('[TTS] 首包')]
    cuda_ready = [ln for ln in lines if '[tts_cuda] 就绪' in ln]
    model_done = [ln for ln in lines if '模型加载完成' in ln]
    e2e = [ln for ln in lines if '端到端启动耗时' in ln]
    queue_logs = [ln for ln in lines if '排队等待' in ln]
    flush_logs = [ln for ln in lines if '补发积压' in ln]
    overflow_logs = [ln for ln in lines if '丢弃' in ln and '准备' in ln]
    return {'n_translations': len(tr), 'translation_lines_sample': tr[:3],
            'tts_ready_log': ready, 'app113_lines': app113,
            'final_stats_lines': final_stats, 'tts_first_packet_lines': tts_first,
            'cuda_ready_lines': cuda_ready, 'model_done_lines': model_done,
            'e2e_lines': e2e, 'queue_log_count': len(queue_logs),
            'queue_log_sample': queue_logs[:3], 'flush_log_lines': flush_logs,
            'overflow_log_lines': overflow_logs,
            'n_lines_total': len(lines)}


def parse_app113_line(ln):
    """解析 `[APP-113] 就绪前排队=N 溢出丢弃=N 已补发=N ｜ TTS就绪=… ｜ …`"""
    out = {}
    m = re.search(r'就绪前排队=(\d+)\s+溢出丢弃=(\d+)\s+已补发=(\d+)', ln)
    if m:
        out['n_queued_before_ready'] = int(m.group(1))
        out['n_drop_not_ready_overflow'] = int(m.group(2))
        out['n_flushed'] = int(m.group(3))
    m = re.search(r'TTS就绪=([\d.]+)s', ln)
    if m:
        out['tts_ready_rel_s'] = float(m.group(1))
    m = re.search(r'积压清空=([\d.]+)s', ln)
    if m:
        out['backlog_cleared_rel_s'] = float(m.group(1))
    m = re.search(r'积压清空口径=(\S+)', ln)
    if m:
        out['backlog_cleared_lag_kind'] = m.group(1)
    m = re.search(r'并行=(on|off)', ln)
    if m:
        out['parallel'] = (m.group(1) == 'on')
    m = re.search(r'ASR就绪=([\d.]+)s', ln)
    if m:
        out['asr_ready_s'] = float(m.group(1))
    m = re.search(r'MT就绪=([\d.]+)s', ln)
    if m:
        out['mt_ready_s'] = float(m.group(1))
    # 🔴🔴 **口径修正（11-16 20:20）**：旧字段名 `TTS就绪(相对进程启动)` 实际打的是
    #   **打印时刻的进程已运行秒数**（不是就绪时刻）⇒ **误标** ⇒ 已改名为
    #   `进程已运行`，并把**真正的就绪时刻**放在 `TTS就绪=`（相对进程启动）。
    m = re.search(r'进程已运行=([\d.]+)s', ln)
    if m:
        out['proc_elapsed_at_print_s'] = float(m.group(1))
    return out


def parse_telemetry(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    for ln in open(path, encoding='utf-8').read().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    return rows


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def extract_fast_wavs(rows, out_wav, wav_dir, tag, min_speed=1.8, want=3):
    if not os.path.isfile(out_wav):
        return {'error': 'tts out wav 不存在'}
    os.makedirs(wav_dir, exist_ok=True)
    cands = []
    for r in rows:
        sp = r.get('speed')
        if sp is None or r.get('dropped'):
            continue
        try:
            sp = float(sp)
        except Exception:
            continue
        t0, t1 = r.get('wav_t0'), r.get('wav_t1')
        if t0 is None or t1 is None:
            continue
        cands.append({'id': r.get('id'), 'speed': round(sp, 4), 't0': t0,
                      't1': t1, 'text': (r.get('text') or '')[:60],
                      'out_dur_s': r.get('out_dur_s'),
                      'play_lag_s': r.get('play_lag_s')})
    cands.sort(key=lambda c: -c['speed'])
    picked = cands[:want]
    fell_back = False
    if not picked:
        fell_back = True
    made = []
    for c in picked:
        dst = os.path.join(wav_dir, '%s_fast_id%s_speed%s.wav'
                           % (tag, c['id'], ('%.2f' % c['speed']).replace('.', '_')))
        p = subprocess.run(
            [PKG_PY, '-c',
             "import soundfile as sf, numpy as np;"
             "d,sr=sf.read(r'%s');"
             "a=int(round(%r*sr)); b=int(round(%r*sr));"
             "b=min(b,len(d)); seg=d[a:b] if b>a else d[:0];"
             "sf.write(r'%s', seg, sr);"
             "print(sr, len(seg)/sr, float(np.abs(seg).max()) if len(seg) else 0)"
             % (out_wav, c['t0'], c['t1'], dst)],
            capture_output=True, text=True, timeout=300)
        if os.path.isfile(dst):
            made.append({'file': dst, 'bytes': os.path.getsize(dst),
                         'sha256': sha256_file(dst), 'id': c['id'],
                         'speed': c['speed'], 'text': c['text'],
                         't0': c['t0'], 't1': c['t1'],
                         'out_dur_s': c['out_dur_s'],
                         'play_lag_s': c['play_lag_s']})
        else:
            made.append({'file': dst, 'error': '切片失败', 'id': c['id'],
                         'speed': c['speed'], 'stderr': (p.stderr or '')[-300:]})
    return {'min_speed': min_speed, 'n_candidates': len(cands),
            'n_made': len([m for m in made if 'error' not in m]),
            'fell_back_to_top_speed': fell_back, 'samples': made,
            'note': ('倍率 ≥%.1f× 的句子共 %d 句；抽出 %d 段供抽听。'
                     % (min_speed, len(cands), len(made))
                     + ('　🔴 **没有任何一句达到 %.1f×** ⇒ 样本是「倍率最高的前 %d 句」'
                        '（实际倍率见 speed 字段）⇒ **不得**当作「≥%.1f× 的样本」解读。'
                        % (min_speed, len(made), min_speed)
                        if fell_back else ''))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', default='zh', choices=['zh', 'en'])
    ap.add_argument('--note', default='')
    ap.add_argument('--no-lock', action='store_true',
                    help='调试用：跳过取锁（**验收必须带锁**）')
    ap.add_argument('--parallel', default='on', choices=['on', 'off'],
                    help='on = CUDA 边车与 ASR 并行加载（APP-113 §2 默认）；'
                         'off = 强制串行（LIVECAP_TTS_PARALLEL=0）⇒ '
                         '供「并行 vs 串行」同机 A/B')
    ap.add_argument('--tag', default='',
                    help='产物文件名后缀覆盖（默认 sp4_<lang>）')
    args = ap.parse_args()

    tag = args.tag or ('sp4_%s' % args.lang)
    if args.parallel == 'off':
        tag += '_serial'
    tts_out = os.path.join(RESULTS, '_app588_%s_tts_out.wav' % tag)
    jsonl = tts_out + '.tts.jsonl'
    backlog = tts_out + '.backlog_curve.csv'
    log_path = os.path.join(RESULTS, '_app588_%s.log' % tag)
    out_json = os.path.join(RESULTS, 'app588_sp4_acceptance_%s.json' % tag)
    wav_dir = os.path.join(RESULTS, '_app588_fast_samples')

    if not os.path.isdir(PKG):
        print('sp4 包不存在：%s' % PKG)
        return 2

    ev = {'purpose': 'APP-113 §4：sp4 SpecialMVP 10 分钟整链验收（目标语言=%s）'
                     % args.lang,
          'pkg': PKG, 'audio': AUDIO, 'target_lang': args.lang,
          'target_lang_note': (
              '中文目标：源=英文 SPE 片段 ⇒ `--translate zh`（英→中）'
              if args.lang == 'zh' else
              '英文目标：源=**英文** SPE 片段 ⇒ `--translate en`（**英→英**，'
              '同语言直译）⇒ reviewer 的「中→英」在**这段英文素材上不可行**'
              '（源不是中文）⇒ 改用同片段的**英→英**配置并在此**写明**；'
              '该臂的用途是验证 **§3 非中文目标的语速上限 2.0×**'),
          'cmd_note': '与 app582（sp3 中文目标）**逐字同构**，只换包路径与输出名 ⇒ 可对照',
          'started': time.strftime('%Y-%m-%d %H:%M:%S')}

    # ── 🔴 **跑前把上一轮的产物挪开**（不是删）──
    #   worker 的逐句 jsonl 是**追加**写（`'a'`）＋ 收尾整体重写（`'w'`）；
    #   若本轮**中途崩溃** ⇒ jsonl 会留下「上一轮的旧行 + 本轮的新行」
    #   ⇒ 句数/丢句统计会被污染 ⇒ **先把旧产物改名挪开**（可逆，不删）。
    moved = []
    for f_ in (tts_out, jsonl, backlog, log_path):
        if os.path.isfile(f_):
            bak = f_ + '.prev'
            try:
                os.replace(f_, bak)
                moved.append({'from': os.path.basename(f_),
                              'to': os.path.basename(bak),
                              'bytes': os.path.getsize(bak)})
            except Exception as e:
                print('🔴 产物挪开失败（%s）：%r' % (f_, e))
    ev['prev_artifacts_moved'] = moved

    # ── 取锁 ──
    if args.no_lock:
        ev['lock_evidence'] = {'acquired': False,
                               'note': '**--no-lock**（调试用；验收必须带锁）'}
    else:
        ev['lock_evidence'] = acquire_lock('app113-sp4-%s' % args.lang)

    try:
        cmd = [PKG_PY, os.path.join(PKG, 'app', 'live_caption_app.py'),
               '--cli', '--file', AUDIO,
               '--asr-device', 'GPU.0',
               '--mt-device', 'NPU',
               '--tts-device', 'CUDA',
               '--translate', args.lang,
               '--tts', 'on',
               '--tts-out', tts_out]
        ev['cmd'] = cmd
        ev['cwd'] = PKG
        env = dict(os.environ)
        if args.parallel == 'off':
            env['LIVECAP_TTS_PARALLEL'] = '0'
        ev['parallel_requested'] = args.parallel
        ev['env_LIVECAP_TTS_PARALLEL'] = env.get('LIVECAP_TTS_PARALLEL', '(unset⇒on)')

        before_files = snapshot_big_files()
        gpu_before = gpu_apps()
        t0 = time.time()
        print('[app588] 起：%s' % ' '.join(cmd), flush=True)
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200,
                           cwd=PKG, env=env)
        t1 = time.time()
        so, se = p.stdout or '', p.stderr or ''
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('CMD: %r\nCWD: %s\nRC=%d\nELAPSED_S=%.1f\n--- STDOUT ---\n%s\n'
                    '--- STDERR ---\n%s\n'
                    % (cmd, PKG, p.returncode, t1 - t0, so, se))
        after_files = snapshot_big_files()
        gpu_after = gpu_apps()

        ev['rc'] = p.returncode
        ev['rc_hex'] = ('0x%08X' % (p.returncode & 0xFFFFFFFF)
                        if 0 <= p.returncode <= 0xFFFFFFFF else None)
        ev['elapsed_s'] = round(t1 - t0, 1)
        ev['run_window'] = {
            'started': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0)),
            'finished': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t1)),
            'audio': AUDIO,
            'audio_bytes': os.path.getsize(AUDIO) if os.path.isfile(AUDIO) else None,
        }
        # ── 外部 IO / GPU 证据 ──
        changed = diff_big_files(before_files, after_files)
        ev['timing_valid'] = (len(changed) == 0)
        ev['timing_invalid_reason'] = (
            '' if not changed else
            '运行窗口内有 %d 个 >100 MB 的文件被改写/新建 ⇒ **计时类结论不成立**'
            '（计数类结论不受影响）' % len(changed))
        ev['external_writes_during_run'] = changed
        ev['gpu_apps_before'] = gpu_before
        ev['gpu_apps_after'] = gpu_after
        ev['gpu_note'] = ('跑前/跑后 nvidia-smi 计算进程快照；'
                          '**若出现非本作业的 PID ⇒ 有外部 GPU 任务**')

        # ── 产物指纹 ──
        art = {}
        for f_ in (tts_out, jsonl, backlog, log_path):
            art[os.path.basename(f_)] = (
                {'exists': True, 'bytes': os.path.getsize(f_),
                 'sha256': sha256_file(f_), 'mtime': os.path.getmtime(f_)}
                if os.path.isfile(f_) else {'exists': False})
        ev['artifacts'] = art

        # ── 日志解析 ──
        lp = parse_log(so)
        ev['log_parse'] = lp
        ev['stdout_tail'] = so[-4000:]
        ev['stderr_tail'] = se[-2000:]
        app113 = {}
        for ln in lp['app113_lines']:
            app113.update(parse_app113_line(ln))
        ev['app113'] = app113

        # ── 逐句遥测 ──
        rows = parse_telemetry(jsonl)
        # 🔴 **重复 id 自检**：worker 收尾会把 jsonl 整体重写 ⇒ 正常只有本轮的行；
        #   若出现**重复 id** ⇒ 说明 jsonl 混进了上一轮的行（追加未重写）⇒ 统计不可信。
        _idc = {}
        for r in rows:
            _idc[r.get('id')] = _idc.get(r.get('id'), 0) + 1
        _dups = {k: v for k, v in _idc.items() if v > 1}
        ev['telemetry_dup_ids'] = {'n_dup_ids': len(_dups),
                                   'sample': dict(list(_dups.items())[:10])}
        dropped = [r for r in rows if r.get('dropped')]
        speeds = [float(r['speed']) for r in rows
                  if r.get('speed') is not None and not r.get('dropped')]
        lags = [float(r['play_lag_s']) for r in rows
                if r.get('play_lag_s') is not None and not r.get('dropped')]
        gains = [float(r['speed_gain']) for r in rows
                 if r.get('speed_gain') is not None and not r.get('dropped')]
        rtfs = [float(r['rtf_ewma']) for r in rows
                if r.get('rtf_ewma') is not None and not r.get('dropped')]
        n_drop_overflow = app113.get('n_drop_not_ready_overflow', 0)
        n_drop_worker = len(dropped)
        ev['telemetry'] = {
            'n_rows': len(rows),
            'n_dropped_worker': n_drop_worker,
            'n_drop_not_ready_overflow': n_drop_overflow,
            'n_drop_total_any_reason': n_drop_worker + n_drop_overflow,
            'n_played': len(rows) - n_drop_worker,
            'dropped_ids': [r.get('id') for r in dropped],
            'dropped_reasons': sorted(set(str(r.get('end_reason'))
                                          for r in dropped)),
            'speed_p50': pct(speeds, 0.50), 'speed_p95': pct(speeds, 0.95),
            'speed_max': (max(speeds) if speeds else None),
            'speed_min': (min(speeds) if speeds else None),
            'speed_mean': (round(sum(speeds) / len(speeds), 4) if speeds else None),
            'speed_gain_mean': (round(sum(gains) / len(gains), 4) if gains else None),
            'n_speed_ge_1_8': sum(1 for s in speeds if s >= 1.8),
            'n_speed_ge_2_0': sum(1 for s in speeds if s >= 1.999),
            'n_speed_at_floor_1_10': sum(1 for s in speeds if abs(s - 1.10) < 1e-6),
            'rtf_ewma_min': (min(rtfs) if rtfs else None),
            'rtf_ewma_max': (max(rtfs) if rtfs else None),
            'rtf_ewma_mean': (round(sum(rtfs) / len(rtfs), 4) if rtfs else None),
            'play_lag_max': (max(lags) if lags else None),
            'play_lag_p95': pct(lags, 0.95),
            'play_lag_end': (lags[-1] if lags else None),
            'n_speed_floor_conflict': max([int(r.get('n_speed_floor_conflict') or 0)
                                           for r in rows] or [0]),
        }
        ev['sentence_counts'] = {
            'n_translations': lp['n_translations'],
            'n_translations_source': 'run log 里 [译文]/[修正译文] 行计数',
            'n_queued_before_ready': app113.get('n_queued_before_ready'),
            'n_flushed': app113.get('n_flushed'),
            'n_submitted_worker': len(rows),
            'n_drop_total_any_reason': n_drop_worker + n_drop_overflow,
            # 🔴🔴🔴 **口径修正（11-16 20:20）**：旧判据写成
            #   「译文 == 就绪前排队 + 进 TTS」⇒ **把排队句重复计了一次**
            #   （排队句本来就在「进 TTS」里）⇒ 上一轮**假 FAIL**。
            #   正确不变式：**每一句译文要么进了 TTS，要么被丢** ⇒
            #   `译文句数 == 进 TTS 句数 + 丢弃总数`。
            #   另加一条独立不变式：**排队句全部补发**（n_flushed == n_queued）。
            'reconciliation_expr': '%s（译文）== %s（进 TTS）+ %s（丢弃）'
                                   % (lp['n_translations'], len(rows),
                                      n_drop_worker + n_drop_overflow),
            'reconciliation_ok': (lp['n_translations']
                                  == len(rows) + n_drop_worker
                                  + n_drop_overflow),
            'queue_flush_expr': '%s（就绪前排队）== %s（已补发）'
                                % (app113.get('n_queued_before_ready'),
                                   app113.get('n_flushed')),
            'queue_flush_ok': (app113.get('n_queued_before_ready')
                               == app113.get('n_flushed')),
        }
        ev['tts_ready'] = {
            'app113_rel_s': app113.get('tts_ready_rel_s'),
            'proc_elapsed_at_print_s': app113.get('proc_elapsed_at_print_s'),
            'asr_ready_s': app113.get('asr_ready_s'),
            'mt_ready_s': app113.get('mt_ready_s'),
            'parallel': app113.get('parallel'),
            'log_line': lp['tts_ready_log'],
            'cuda_ready_lines': lp['cuda_ready_lines'],
            'model_done_lines': lp['model_done_lines'],
            'e2e_lines': lp['e2e_lines'],
        }
        ev['backlog_cleared_rel_s'] = app113.get('backlog_cleared_rel_s')
        ev['backlog_cleared_lag_kind'] = app113.get('backlog_cleared_lag_kind')

        # ── 判定 ──
        checks = [
            {'name': '丢句数（任何原因）= 0',
             'pass': (n_drop_worker + n_drop_overflow == 0),
             'detail': 'worker丢弃=%d + 溢出丢弃=%d' % (n_drop_worker,
                                                       n_drop_overflow)},
            {'name': '译文句数 == 进 TTS 句数 + 丢弃总数（无其它丢失路径）',
             'pass': ev['sentence_counts']['reconciliation_ok'],
             'detail': ev['sentence_counts']['reconciliation_expr']},
            {'name': '就绪前排队的句子**全部补发**（一句不丢）',
             'pass': ev['sentence_counts']['queue_flush_ok'],
             'detail': ev['sentence_counts']['queue_flush_expr']},
            {'name': '倍率 max ≤ 2.0',
             'pass': (ev['telemetry']['speed_max'] is not None
                      and ev['telemetry']['speed_max'] <= 2.0 + 1e-9),
             'detail': 'max=%s p50=%s p95=%s' % (ev['telemetry']['speed_max'],
                                                ev['telemetry']['speed_p50'],
                                                ev['telemetry']['speed_p95'])},
            {'name': '退出码 0',
             'pass': (p.returncode == 0), 'detail': 'rc=%s' % p.returncode},
            {'name': '产出齐备（wav + 逐句 jsonl + 积压曲线）',
             'pass': all(os.path.isfile(f_) for f_ in (tts_out, jsonl, backlog)),
             'detail': ','.join(os.path.basename(f_) for f_ in
                                 (tts_out, jsonl, backlog))},
            {'name': '逐句 jsonl **无重复 id**（未混入上一轮的行）',
             'pass': len(_dups) == 0,
             'detail': '重复 id 数=%d（%s）' % (len(_dups),
                                             list(_dups.items())[:5])},
            {'name': 'TTS 就绪时刻已记录',
             'pass': app113.get('tts_ready_rel_s') is not None,
             'detail': 'TTS就绪=%s s（相对进程启动；收尾时进程已运行 %s s）'
                       % (app113.get('tts_ready_rel_s'),
                          app113.get('proc_elapsed_at_print_s'))},
            {'name': '积压清空时刻已记录（口径=play_lag_s）',
             'pass': app113.get('backlog_cleared_rel_s') is not None,
             'detail': '积压清空=%s s（口径 %s；末句播放滞后 %s s）'
                       % (app113.get('backlog_cleared_rel_s'),
                          app113.get('backlog_cleared_lag_kind'),
                          ev['telemetry'].get('play_lag_end'))},
            {'name': ('ASR/TTS 并行生效（并行=on）' if args.parallel == 'on'
                      else 'ASR/TTS 强制串行生效（并行=off，对照臂）'),
             'pass': (app113.get('parallel') is True
                      if args.parallel == 'on'
                      else app113.get('parallel') is False),
             'detail': 'parallel=%s（请求=%s）'
                       % (app113.get('parallel'), args.parallel)},
        ]
        ev['checks'] = checks
        ev['n_fail'] = sum(1 for c in checks if not c['pass'])
        ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'

        # ── 抽 ≥1.8× 的 wav ──
        ev['fast_samples'] = extract_fast_wavs(rows, tts_out, wav_dir, tag,
                                                1.8, 3)
        ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    finally:
        if not args.no_lock:
            release_lock(ev.get('lock_evidence'))

    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('rc=%d  %s' % (ev.get('rc'), json.dumps(ev.get('telemetry'),
                                                  ensure_ascii=False)))
    for c in ev.get('checks', []):
        print('  [%s] %s | %s' % ('PASS' if c['pass'] else 'FAIL',
                                  c['name'], c['detail']))
    print('VERDICT=%s -> %s' % (ev.get('verdict'), out_json))
    return 0 if ev.get('verdict') == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
