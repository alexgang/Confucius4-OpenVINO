#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app588_sp4_acceptance.py —— **整链 10 分钟验收**（APP-113 §4 建，APP-114 §4 改判据）。

🔴 **reviewer 原文（APP-113 §4，本脚本的原型）**：
  「验收：持锁跑固定 10 分钟片段（SPE 0–600 s）两次：sp4 SpecialMVP 中文目标；
    sp4 英文目标。每次报：译文句数 / 进 TTS 句数 / 丢句数（任何原因，必须 = 0）/
    排队句数 / TTS 就绪时刻 / 积压清空时刻 / 倍率 P50/P95/max（max ≤ 2.0）/
    最大滞后。」

🔴 **reviewer 原文（APP-114 §4，本轮的改动面）**：
  「每臂都要满足：**speed max ≤ 1.70**（从逐句 tts.jsonl 原始字段计算）、
    **丢句（任何原因）= 0**、译文句数 == 进 TTS 句数、排队句数 == 补发句数、rc=0。
    每臂都要报：speed P50/P95/max 和 ≥1.6× 的句数；**lag max / lag end /
    积压清空时刻**（口径用 play_lag_s）；TTS 就绪时刻、ASR 就绪时刻、边车加载时间；
    `timing_valid` 以及外部大 IO 检查结果。……
    **抽 3 段 1.6–1.7× 的配音样本给用户抽听，标注真实倍率。**
    把三臂的 tts.jsonl、backlog_curve.csv、run log 原样留在 results/app/
    （**不覆盖**），供 reviewer 本机复算。」
  另 §2.2：「从现在起每臂的产物文件名都要带时间戳或 run 编号，**禁止覆盖**。」
  另 §2.4：「在结果 json 里附上每句倍率的**直方图**（或排序后的前 15 个值），
    说明为什么相等。」

🔴 **本脚本的纪律**：
  · **复用** APP-113 的同一个脚本（**不新建闸门/矩阵/判据脚本**，APP-110 §1）
    ⇒ 只改**判据本身**（倍率上限 2.0→1.70、产物名带 run 编号不覆盖、
      倍率直方图、抽听样本按真实倍率标注）+ 加 `--pkg` 参数以指向 sp5；
  · **持锁**：先建 `shared/MACHINE_LOCK`（内容 = 模块名 PID 开始时间 说明），
    锁已存在 ⇒ **排队等待**（不抢锁）；回收前用 ctypes OpenProcess +
    GetExitCodeProcess 确认 PID 真死（探测失败 ⇒ 视为存活 ⇒ 继续等）。
  · **锁证据进结果 json**（APP-112 §2 的立规）：锁内容 + 取锁时刻 + 放锁时刻。
  · **timing_valid**：跑前/跑后快照「监视目录里 >100 MB 的文件」的
    (size, mtime) ⇒ 运行窗口内有变化 ⇒ 判 `timing_valid=false` 并**如实列出**。
  · **GPU 证据**：跑前/跑后采样 `nvidia-smi --query-compute-apps`。
  · **preflight（AST 直读，不 import）**：跑之前先确认**被测包**里的
    `time_stretch.SPEED_MAX / ZH_SPEED_MAX = 1.70`、`_TTS_QUEUE_OVERFLOW_S is None`
    ⇒ 验收结果确实落在「被测对象当前内容」上（§205 纪律）。
  · **不改产品代码、不打包 zip**（APP-055 + 用户级纪律）。
"""
import argparse
import ast
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
PKG_DEFAULT = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp5')
AUDIO = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')

#: 🔴 **APP-114 §1**：语速上限（**所有目标语言**）
SPEED_CAP = 1.70

#: 🔴 **监视目录**（用于 timing_valid：这些目录里 >100 MB 的文件在运行窗口内
#:   被改写 ⇒ 判「有外部大 IO」）
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


class LockWatch(threading.Thread):
    """🔴 APP-115 §3.2：**运行期间盯锁文件**（只读采样，不改锁）。

    ⚠️ 目的：若锁在运行中**被别人动过**（删除／改写／抢走），本看门狗
      记下**改动时刻 + 当时的内容**（谁动的：模块名 + PID + 说明）⇒
      APP-115 §3.2「如果锁又丢了…就查是谁动了锁」有据可查，不靠猜。
    ⚠️ 采样读**原始文本**（不解析）⇒ 别人的锁格式（`ext …`）也能照原样记录。
    """

    def __init__(self, interval=10.0):
        super().__init__(daemon=True)
        self.interval = float(interval)
        self._stop = threading.Event()
        self.samples = []
        self.events = []
        self.started_at = time.strftime('%Y-%m-%d %H:%M:%S')

    def _read_raw(self):
        try:
            with open(LOCK, encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            return None

    def run(self):
        last = '\x00INIT'
        while not self._stop.wait(self.interval):
            raw = self._read_raw()
            rec = {'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'raw': raw}
            self.samples.append(rec)
            if raw != last:
                self.events.append(rec)
                last = raw

    def stop(self):
        self._stop.set()

    def summary(self, own_raw):
        """⇒ 落进验收 json 的看门狗摘要。"""
        foreign = [e for e in self.events
                   if e['raw'] is None or e['raw'] != own_raw]
        return {
            'interval_s': self.interval,
            'started_at': self.started_at,
            'stopped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'n_samples': len(self.samples),
            'n_events': len(self.events),
            'own_lock_content': own_raw,
            'n_foreign_events': len(foreign),
            'foreign_events': foreign[:20],
            'first_sample': self.samples[0] if self.samples else None,
            'last_sample': self.samples[-1] if self.samples else None,
            'note': ('🔴 报告项（APP-115 §3.2）：运行期间每 %g s 只读采样锁文件；'
                     '`foreign_events` = 锁内容**不再是本作业**的时刻 ⇒ '
                     '锁被谁动过（内容里带模块名 + PID + 说明）。'
                     % self.interval),
        }


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
# preflight：被测包的「语速上限 / 队列语义」（AST 直读，不 import）
# ══════════════════════════════════════════════════════════════
def preflight(pkg):
    """跑之前先确认**被测对象当前内容**（§205：证据必须描述被检对象）。"""
    out = {'pkg': pkg, 'ok': False}
    app_dir = os.path.join(pkg, 'app')
    try:
        src = open(os.path.join(app_dir, 'time_stretch.py'),
                   encoding='utf-8').read()
        tree = ast.parse(src)
        consts = {}
        for n in tree.body:
            if isinstance(n, ast.Assign):
                for tgt in n.targets:
                    nm = getattr(tgt, 'id', None)
                    if nm in ('SPEED_MAX', 'ZH_SPEED_MAX', 'SPEED_MIN',
                              'ZH_SPEED_MIN', 'LAG_DEADZONE_S',
                              'SPEED_PER_LAG_S', 'LAG_HYSTERESIS_S',
                              'MAX_STEP_CHANGE'):
                        consts[nm] = ast.literal_eval(n.value)
        out['speed_constants'] = consts
        out['speed_max_ok'] = (consts.get('SPEED_MAX') == SPEED_CAP
                               and consts.get('ZH_SPEED_MAX') == SPEED_CAP)
        out['gain_curve_unchanged'] = (
            consts.get('LAG_DEADZONE_S') == 3.0
            and consts.get('SPEED_PER_LAG_S') == 0.025
            and consts.get('LAG_HYSTERESIS_S') == 2.0
            and consts.get('MAX_STEP_CHANGE') == 0.1
            and consts.get('SPEED_MIN') == 1.0
            and consts.get('ZH_SPEED_MIN') == 1.10)
        lca = open(os.path.join(app_dir, 'live_caption_app.py'),
                   encoding='utf-8').read()
        t2 = ast.parse(lca)
        q = None
        for n in t2.body:
            if isinstance(n, ast.Assign):
                for tgt in n.targets:
                    if getattr(tgt, 'id', None) == '_TTS_QUEUE_OVERFLOW_S':
                        q = ast.literal_eval(n.value)
        out['queue_overflow_s'] = q
        out['queue_no_time_drop'] = (q is None)
        out['has_clear_on_worker_failure'] = ('clear_on_worker_failure'
                                              in lca)
    except Exception as e:
        out['error'] = repr(e)
        return out
    out['ok'] = bool(out.get('speed_max_ok') and out.get('gain_curve_unchanged')
                     and out.get('queue_no_time_drop')
                     and out.get('has_clear_on_worker_failure'))
    return out


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
    asr_load = [ln for ln in lines if '加载' in ln and 'gpu_int8' in ln]
    mt_ready = [ln for ln in lines if '翻译模型就绪' in ln]
    worker_fail = [ln for ln in lines if 'worker 失败/退出' in ln]
    return {'n_translations': len(tr), 'translation_lines_sample': tr[:3],
            'tts_ready_log': ready, 'app113_lines': app113,
            'final_stats_lines': final_stats, 'tts_first_packet_lines': tts_first,
            'cuda_ready_lines': cuda_ready, 'model_done_lines': model_done,
            'e2e_lines': e2e, 'queue_log_count': len(queue_logs),
            'queue_log_sample': queue_logs[:3], 'flush_log_lines': flush_logs,
            'overflow_log_lines': overflow_logs,
            'asr_load_lines': asr_load, 'mt_ready_lines': mt_ready,
            'worker_failure_lines': worker_fail,
            'n_lines_total': len(lines)}


def parse_app113_line(ln):
    """解析 `[APP-113] 就绪前排队=N 溢出丢弃=N 已补发=N ｜ worker失败丢弃=N ｜ …`"""
    out = {}
    m = re.search(r'就绪前排队=(\d+)\s+溢出丢弃=(\d+)\s+已补发=(\d+)', ln)
    if m:
        out['n_queued_before_ready'] = int(m.group(1))
        out['n_drop_not_ready_overflow'] = int(m.group(2))
        out['n_flushed'] = int(m.group(3))
    # 🔴 APP-114 §2.1：**worker 失败/退出清空**的句数（唯一允许丢弃的路径）
    m = re.search(r'worker失败丢弃=(\d+)', ln)
    if m:
        out['n_drop_worker_failed'] = int(m.group(1))
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


def speed_histogram(speeds, step=0.05):
    """🔴 APP-114 §2.4：**逐句倍率直方图**（回答「P95 为什么等于 max」）。"""
    if not speeds:
        return {'n': 0, 'bins': []}
    bins = {}
    for s in speeds:
        k = round(round(s / step) * step, 4)
        bins[k] = bins.get(k, 0) + 1
    out = [{'speed_bin': k, 'n': v} for k, v in sorted(bins.items())]
    top = sorted(speeds, reverse=True)
    n_at_max = sum(1 for s in speeds if abs(s - top[0]) < 1e-9)
    p95 = pct(speeds, 0.95)
    return {
        'n': len(speeds),
        'step': step,
        'bins': out,
        'n_distinct_bins': len(out),
        'max': top[0],
        'n_at_max': n_at_max,
        'p95': p95,
        'p95_equals_max': (p95 is not None and abs(p95 - top[0]) < 1e-9),
        'why_p95_equals_max': (
            'P95 == max ⇒ 排序后第 95 百分位落在**最高倍率那一档**：'
            '本臂 **%d/%d 句都停在同一个最高倍率 %.4f×** ⇒ 该档占比 %.1f %% '
            '⇒ P95 与 max 必然相等（不是统计口径错）。'
            % (n_at_max, len(speeds), top[0], 100.0 * n_at_max / len(speeds))
            if p95 is not None and abs(p95 - top[0]) < 1e-9 else
            'P95(%s) < max(%s) ⇒ 未落在同一档。' % (p95, top[0])),
        'top15_sorted_desc': [round(x, 4) for x in top[:15]],
        'top15_note': '排序后的前 15 个逐句倍率（降序）⇒ 可直接核对 P95/max。',
    }


def extract_fast_wavs(rows, out_wav, wav_dir, tag, lo=1.60, hi=1.70, want=3,
                      pkg_py=None):
    """🔴 APP-114 §4：抽 **3 段 1.6–1.7×** 的配音样本，**标注真实倍率**。

    ⚠️ §2.3：「§212⑤ 写『候选 164 句（≥1.8×），抽出 3 段』，但这一臂
      `n_speed_ge_1_8=0`，抽出的样本是 1.53×/1.37× ⇒ 改成按实际倍率的真实标注。」
    ⇒ **没有命中目标档时**必须**如实标注**实际倍率，不得宣称是 ≥1.6× 的样本。
    """
    if not os.path.isfile(out_wav):
        return {'error': 'tts out wav 不存在'}
    os.makedirs(wav_dir, exist_ok=True)
    played = []
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
        played.append({'id': r.get('id'), 'speed': round(sp, 4), 't0': t0,
                       't1': t1, 'text': (r.get('text') or '')[:60],
                       'out_dur_s': r.get('out_dur_s'),
                       'play_lag_s': r.get('play_lag_s')})
    band = [c for c in played if lo - 1e-9 <= c['speed'] <= hi + 1e-9]
    fell_back = False
    if not band:
        fell_back = True
        band = sorted(played, key=lambda c: -c['speed'])[:want]
    picked = sorted(band, key=lambda c: -c['speed'])[:want]
    made = []
    for c in picked:
        dst = os.path.join(wav_dir, '%s_fast_id%s_speed%s.wav'
                           % (tag, c['id'], ('%.2f' % c['speed']).replace('.', '_')))
        p = subprocess.run(
            [pkg_py, '-c',
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
                         'speed': c['speed'],
                         'speed_label': ('真实倍率 %.4f×' % c['speed']),
                         'in_target_band': (lo - 1e-9 <= c['speed'] <= hi + 1e-9),
                         'text': c['text'], 't0': c['t0'], 't1': c['t1'],
                         'out_dur_s': c['out_dur_s'],
                         'play_lag_s': c['play_lag_s']})
        else:
            made.append({'file': dst, 'error': '切片失败', 'id': c['id'],
                         'speed': c['speed'], 'stderr': (p.stderr or '')[-300:]})
    note = ('目标档 **%.2f–%.2f×** 命中 **%d 句** ⇒ 抽出 %d 段（文件名与 '
            'speed 字段均为**真实倍率**）。'
            % (lo, hi, len([c for c in played if lo - 1e-9 <= c['speed'] <= hi + 1e-9]),
               len(made)))
    if fell_back:
        note += ('　🔴 **本臂没有任何一句落在目标档** ⇒ 抽的是「倍率最高的 %d 句」'
                 '（真实倍率见各样本 speed / speed_label）⇒ **不得**当作'
                 '「1.6–1.7× 的样本」解读。' % len(made))
    return {'target_band': [lo, hi], 'n_played_rows': len(played),
            'n_in_band': len([c for c in played
                              if lo - 1e-9 <= c['speed'] <= hi + 1e-9]),
            'n_made': len([m for m in made if 'error' not in m]),
            'fell_back_to_top_speed': fell_back, 'samples': made, 'note': note}


def queue_probe(pkg):
    """🔴 APP-114 §2.1 的**行为级**判据：真跑被测包里的 `TtsReadyQueue`。

    ⇒ ① 入队 5 句 ⇒ 把入队时刻改到 **300 s 前**（远超旧阈值 120 s）
      ⇒ **仍应全部保留、丢弃 0**（旧实现会按最旧优先丢弃）；
    ⇒ ② `clear_on_worker_failure()` ⇒ 应清空并计数。
    ⚠️ **不 import 被测模块**（它会拉起整套依赖）⇒ 用 **AST 直读 + exec**
      把 `TtsReadyQueue` / `_TTS_QUEUE_OVERFLOW_S` / `_TTS_BACKLOG_CLEAR_S`
      单独取出来跑（§205：证据必须属于被检对象 ⇒ 从**包内**文件取）。
    """
    out = {'pkg': pkg, 'ok': False}
    app_dir = os.path.join(pkg, 'app')
    path = os.path.join(app_dir, 'live_caption_app.py')
    try:
        import threading
        import time as _time
        src = open(path, encoding='utf-8').read()
        tree = ast.parse(src)
        want = {'TtsReadyQueue', '_TTS_QUEUE_OVERFLOW_S', '_TTS_BACKLOG_CLEAR_S'}
        nodes = []
        for n in tree.body:
            nm = getattr(n, 'name', None)
            if nm in want:
                nodes.append(n)
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if getattr(t, 'id', None) in want:
                        nodes.append(n)
        ns = {'threading': threading, 'time': _time, '__name__': 'app591_probe'}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), path, 'exec'), ns)
        Q = ns['TtsReadyQueue']
        out['overflow_s'] = ns['_TTS_QUEUE_OVERFLOW_S']
        logs = []
        q = Q(on_log=logs.append)
        for i in range(5):
            q.push((lambda i=i: None), meta={'i': i})
        st1 = q.stats()
        # 把入队时刻改到 300 s 前（模拟「等了很久仍未就绪」）
        with q._lock:
            for i, item in enumerate(q._q):
                q._q[i] = (_time.time() - 300.0, item[1], item[2])
        q.enforce_overflow()
        q.poll(False)
        st2 = q.stats()
        n_cleared = q.clear_on_worker_failure('app591 probe')
        st3 = q.stats()
        out['n_pushed'] = 5
        out['after_push'] = {'n_pending': st1['n_pending'],
                             'n_drop_not_ready_overflow':
                                 st1['n_drop_not_ready_overflow']}
        out['after_300s_stale'] = {'n_pending': st2['n_pending'],
                                   'n_drop_not_ready_overflow':
                                       st2['n_drop_not_ready_overflow'],
                                   'n_drop_worker_failed':
                                       st2['n_drop_worker_failed']}
        out['after_worker_failure'] = {'n_pending': st3['n_pending'],
                                        'n_drop_worker_failed':
                                            st3['n_drop_worker_failed'],
                                        'n_cleared': n_cleared}
        out['log'] = logs[-1] if logs else ''
        out['ok'] = (st2['n_pending'] == 5
                     and st2['n_drop_not_ready_overflow'] == 0
                     and st2['n_drop_worker_failed'] == 0
                     and st3['n_pending'] == 0
                     and st3['n_drop_worker_failed'] == 5
                     and n_cleared == 5)
        out['criterion'] = ('入队 5 句 ⇒ 把入队时刻改到 300 s 前（> 旧阈值 120 s）'
                            '⇒ 仍保留 5 句、丢弃 0；'
                            'worker 失败 ⇒ 清空 5 句且计数 = 5')
    except Exception as e:
        out['error'] = repr(e)
    return out


def finalize_app115(ev):
    """🔴 **APP-115 §3.2**：两项**报告项**（**不是新闸门**）+ timing_valid 判定。

    ① 「放锁时锁内容是否还是本作业」——读 `lock_evidence.lock_content_at_release`
       （放锁那一刻的锁原文）⇒ 丢失 ⇒ `None`。
    ② 「synth_rtf 中位 / P90」——**逐句** `synth_rtf`（与 reviewer 的算法一致：
       线性插值分位数）⇒ 可直接对表。

    🔴 **判定规则是 reviewer 给的**（APP-115 §3.2）：
       丢句 0 + max≤1.70 + **RTF P90 ≤ 0.75** ⇒ `timing_valid=true`；
       锁丢了 / RTF 异常 ⇒ `timing_valid=false` + 如实写原因。
    ⚠️ 本函数**只加报告项 + 改 timing_valid**，**不新增任何判定门槛**
       （`report_only=True` 的条目不进 `n_fail`）。
    """
    if not isinstance(ev, dict):
        return ev
    lock_ev = ev.get('lock_evidence') or {}
    at_release = lock_ev.get('lock_content_at_release')
    own_pid = os.getpid()
    lock_at_release_ok = False
    if at_release:
        parts = str(at_release).split()
        try:
            lock_at_release_ok = (int(parts[1]) == own_pid)
        except Exception:
            lock_at_release_ok = (at_release == lock_ev.get('lock_content'))
    tel = ev.get('telemetry') or {}
    p50 = tel.get('synth_rtf_p50')
    p90 = tel.get('synth_rtf_p90')
    n_gt1 = tel.get('synth_rtf_n_gt_1')
    n_rtf = tel.get('synth_rtf_n')
    lw = ev.get('lock_watch') or {}

    # ── timing_valid（沿用「外部大 IO」条件 + APP-115 新增两条）──
    reasons = []
    ext_writes = ev.get('external_writes_during_run') or []
    if ext_writes:
        reasons.append('运行窗口内有 %d 个 >100 MB 的文件被改写/新建' % len(ext_writes))
    if not lock_at_release_ok:
        reasons.append('锁在运行中丢失（放锁时锁内容=%r，**不是本作业 PID %d**）'
                       % (at_release, own_pid))
    if p90 is not None and float(p90) > 0.75:
        reasons.append('synth_rtf P90=%.3f > 0.75（合成 RTF 异常 ⇒ 机器被占）'
                       % float(p90))
    ev['timing_valid'] = (len(reasons) == 0)
    ev['timing_invalid_reason'] = (
        '' if not reasons else
        '；'.join(reasons) + ' ⇒ **计时类结论不成立**（计数类结论不受影响）')

    items = [
        {'name': '放锁时锁内容是否还是本作业（**报告项**：APP-115 §3.2）',
         'pass': True, 'report_only': True,
         'detail': ('放锁时锁内容=%r ⇒ 仍是本作业(PID %d)=**%s**；'
                    '运行期间锁看门狗：采样 %s 次 / 内容变动 %s 次 / '
                    '**非本作业的内容变动 %s 次**%s')
                    % (at_release, own_pid, lock_at_release_ok,
                       lw.get('n_samples'), lw.get('n_events'),
                       lw.get('n_foreign_events'),
                       ('；外来变动时刻：%s'
                        % [(e.get('at'), e.get('raw')) for e in
                           (lw.get('foreign_events') or [])][:5])
                       if lw.get('n_foreign_events') else '')},
        {'name': 'synth_rtf 中位 / P90（**报告项**：APP-115 §3.2；判定线 P90≤0.75）',
         'pass': True, 'report_only': True,
         'detail': ('synth_rtf 中位=%s P90=%s max=%s；RTF>1 的句数=%s / 共 %s 句'
                    % (p50, p90, tel.get('synth_rtf_max'), n_gt1, n_rtf))},
    ]
    checks = ev.get('checks')
    if isinstance(checks, list):
        checks = [c for c in checks
                  if not str(c.get('name', '')).startswith(
                      ('放锁时锁内容', 'synth_rtf 中位'))]
        checks.extend(items)
        ev['checks'] = checks
        ev['reports'] = [c for c in checks if c.get('report_only')]
        ev['n_fail'] = sum(1 for c in checks
                           if not c['pass'] and not c.get('report_only'))
        ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
    rr = ev.get('required_report')
    if isinstance(rr, dict):
        rr['timing_valid'] = ev['timing_valid']
        rr['timing_invalid_reason'] = ev['timing_invalid_reason']
        rr['lock_content_at_release'] = at_release
        rr['lock_at_release_is_own_job'] = lock_at_release_ok
        rr['synth_rtf_p50'] = p50
        rr['synth_rtf_p90'] = p90
        rr['synth_rtf_max'] = tel.get('synth_rtf_max')
        rr['synth_rtf_n_gt_1'] = n_gt1
        rr['synth_rtf_n'] = n_rtf
        rr['lock_watch_events'] = lw.get('foreign_events')
        rr['note'] = (rr.get('note', '') +
                      '｜**APP-115 §3.2**：新增两项报告项（放锁时锁内容是否还是本作业 / '
                      'synth_rtf 中位+P90）；`timing_valid` 另加两条条件'
                      '（锁未丢 + RTF P90≤0.75）⇒ 计时类结论只在锁未被动过且 RTF 正常时成立。')
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', default='zh', choices=['zh', 'en'])
    ap.add_argument('--note', default='')
    ap.add_argument('--no-lock', action='store_true',
                    help='调试用：跳过取锁（**验收必须带锁**）')
    ap.add_argument('--parallel', default='on', choices=['on', 'off'],
                    help='on = CUDA 边车与 ASR 并行加载（APP-113 §2 默认）；'
                         'off = 强制串行（LIVECAP_TTS_PARALLEL=0）')
    ap.add_argument('--tag', default='',
                    help='产物文件名后缀覆盖（默认 <pkg>_<lang>）')
    ap.add_argument('--pkg', default=PKG_DEFAULT,
                    help='被测包目录（APP-114 ⇒ sp5）')
    ap.add_argument('--run-id', default='',
                    help='run 编号（默认 = 时间戳）⇒ **产物名唯一、禁止覆盖**')
    ap.add_argument('--extra-evidence', default='',
                    help='额外的证据 json 路径 ⇒ **合并进本臂的结果 json**'
                         '（例如冷启动臂的「缓存挪开」记录）')
    ap.add_argument('--lock-note', default='',
                    help='🔴 APP-115：写进 MACHINE_LOCK 的说明（默认 app114-<lang>）'
                         '⇒ 让别的模块看锁就知道是谁在跑')
    args = ap.parse_args()

    PKG = args.pkg
    PKG_PY = os.path.join(PKG, 'python', 'python.exe')
    tag = args.tag or ('%s_%s' % (os.path.basename(PKG).replace(
        'Confucius4_LiveCaption_SpecialMVP_v1.0-', 'sp'), args.lang))
    if args.parallel == 'off':
        tag += '_serial'
    # 🔴 APP-114 §2.2：**产物文件名带 run 编号（时间戳）** ⇒ 禁止同名覆盖
    run_id = args.run_id or time.strftime('%Y%m%d-%H%M%S')
    prefix = '_app591_%s_run%s' % (tag, run_id)
    tts_out = os.path.join(RESULTS, '%s_tts_out.wav' % prefix)
    jsonl = tts_out + '.tts.jsonl'
    backlog = tts_out + '.backlog_curve.csv'
    log_path = os.path.join(RESULTS, '%s.log' % prefix)
    out_json = os.path.join(RESULTS, 'app591_acceptance_%s_run%s.json'
                            % (tag, run_id))
    wav_dir = os.path.join(RESULTS, '_app591_fast_samples')

    if not os.path.isdir(PKG):
        print('包不存在：%s' % PKG)
        return 2
    for f_ in (tts_out, jsonl, backlog, log_path, out_json):
        if os.path.exists(f_):
            print('FAIL: 产物已存在（禁止覆盖，APP-114 §2.2）：%s' % f_)
            return 2

    ev = {'purpose': 'APP-114 §4：SpecialMVP 10 分钟整链验收（目标语言=%s）'
                     % args.lang,
          'pkg': PKG, 'audio': AUDIO, 'target_lang': args.lang,
          'run_id': run_id,
          'artifact_prefix': prefix,
          'artifact_note': '产物文件名带 run 编号（时间戳）⇒ **不覆盖**上一轮',
          'target_lang_note': (
              '中文目标：源=英文 SPE 片段 ⇒ `--translate zh`（英→中）'
              if args.lang == 'zh' else
              '英文目标：源=**英文** SPE 片段 ⇒ `--translate en`（**英→英**，'
              '同语言直译）⇒ reviewer 的「中→英」在**这段英文素材上不可行**'
              '（源不是中文）⇒ 改用同片段的**英→英**配置并在此**写明**；'
              '该臂的用途是验证 **§1 非中文目标的语速上限 1.70×**'),
          'speed_cap_expected': SPEED_CAP,
          'started': time.strftime('%Y-%m-%d %H:%M:%S')}

    # ── preflight：被测包的代码事实 ──
    pf = preflight(PKG)
    ev['preflight'] = pf
    qp = queue_probe(PKG)
    ev['queue_probe'] = qp
    pf['queue_probe_ok'] = qp.get('ok')
    if args.extra_evidence and os.path.isfile(args.extra_evidence):
        try:
            with open(args.extra_evidence, encoding='utf-8') as f:
                ev['extra_evidence'] = json.load(f)
        except Exception as e:
            ev['extra_evidence'] = {'error': repr(e),
                                     'path': args.extra_evidence}
    if not pf.get('ok'):
        print('FAIL: preflight 不通过（被测包不是 APP-114 的代码）⇒ 零运行')
        print(json.dumps(pf, ensure_ascii=False, indent=1))
        return 3
    if not qp.get('ok'):
        print('FAIL: 队列行为探针不通过（§2.1 未生效）⇒ 零运行')
        print(json.dumps(qp, ensure_ascii=False, indent=1))
        return 3

    # ── 取锁 ──
    if args.no_lock:
        ev['lock_evidence'] = {'acquired': False,
                               'note': '**--no-lock**（调试用；验收必须带锁）'}
    else:
        ev['lock_evidence'] = acquire_lock(args.lock_note
                                           or ('app114-%s' % args.lang))
    # 🔴 APP-115 §3.2：**锁看门狗**（运行期间只读采样 ⇒ 锁被谁动过有据可查）
    lock_watch = None
    own_lock_content = (ev.get('lock_evidence') or {}).get('lock_content')
    if own_lock_content:
        lock_watch = LockWatch(interval=10.0)
        lock_watch.start()

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
        print('[app591] 起：%s' % ' '.join(cmd), flush=True)
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

        # 🔴 APP-115 §3.2：停看门狗 ⇒ 记「运行结束时锁是否还是本作业」
        if lock_watch is not None:
            lock_watch.stop()
            ev['lock_watch'] = lock_watch.summary(own_lock_content)
            ev['lock_watch']['stopped_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        own_end = lock_owner()
        ev['lock_intact_at_run_end'] = bool(
            own_end and own_end.get('pid') == os.getpid())
        ev['lock_owner_at_run_end'] = (own_end or {}).get('raw')

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
        # 🔴 APP-115 §3.2：**逐句 synth_rtf**（中位 / P90 / RTF>1 句数）
        #   ⚠️ 与 reviewer 的算法一致（同一批 jsonl ⇒ 数值可直接对表）
        sr = [float(r['synth_rtf']) for r in rows
              if r.get('synth_rtf') is not None and not r.get('dropped')]
        n_drop_overflow = app113.get('n_drop_not_ready_overflow', 0)
        n_drop_worker_failed = app113.get('n_drop_worker_failed', 0)
        n_drop_worker = len(dropped)
        ev['telemetry'] = {
            'n_rows': len(rows),
            'n_dropped_worker': n_drop_worker,
            'n_drop_not_ready_overflow': n_drop_overflow,
            'n_drop_worker_failed': n_drop_worker_failed,
            'n_drop_total_any_reason': (n_drop_worker + n_drop_overflow
                                         + n_drop_worker_failed),
            'n_played': len(rows) - n_drop_worker,
            'dropped_ids': [r.get('id') for r in dropped],
            'dropped_reasons': sorted(set(str(r.get('end_reason'))
                                          for r in dropped)),
            'speed_p50': pct(speeds, 0.50), 'speed_p95': pct(speeds, 0.95),
            'speed_max': (max(speeds) if speeds else None),
            'speed_min': (min(speeds) if speeds else None),
            'speed_mean': (round(sum(speeds) / len(speeds), 4) if speeds else None),
            'speed_gain_mean': (round(sum(gains) / len(gains), 4) if gains else None),
            'n_speed_ge_1_6': sum(1 for s in speeds if s >= 1.6),
            'n_speed_ge_1_7': sum(1 for s in speeds if s >= 1.7 - 1e-9),
            'n_speed_ge_1_8': sum(1 for s in speeds if s >= 1.8),
            'n_speed_ge_2_0': sum(1 for s in speeds if s >= 2.0 - 1e-9),
            'n_speed_at_floor_1_10': sum(1 for s in speeds if abs(s - 1.10) < 1e-6),
            'rtf_ewma_min': (min(rtfs) if rtfs else None),
            'rtf_ewma_max': (max(rtfs) if rtfs else None),
            'rtf_ewma_mean': (round(sum(rtfs) / len(rtfs), 4) if rtfs else None),
            # 🔴 APP-115 §3.2 报告项②：逐句合成 RTF
            'synth_rtf_n': len(sr),
            'synth_rtf_p50': pct(sr, 0.50),
            'synth_rtf_p90': pct(sr, 0.90),
            'synth_rtf_max': (max(sr) if sr else None),
            'synth_rtf_min': (min(sr) if sr else None),
            'synth_rtf_n_gt_1': sum(1 for x in sr if x > 1.0),
            'synth_rtf_n_ge_0_75': sum(1 for x in sr if x > 0.75),
            'play_lag_max': (max(lags) if lags else None),
            'play_lag_p95': pct(lags, 0.95),
            'play_lag_end': (lags[-1] if lags else None),
            'n_speed_floor_conflict': max([int(r.get('n_speed_floor_conflict') or 0)
                                           for r in rows] or [0]),
        }
        # 🔴 APP-114 §2.4：逐句倍率直方图 + 排序前 15
        ev['speed_histogram'] = speed_histogram(speeds)
        ev['sentence_counts'] = {
            'n_translations': lp['n_translations'],
            'n_translations_source': 'run log 里 [译文]/[修正译文] 行计数',
            'n_queued_before_ready': app113.get('n_queued_before_ready'),
            'n_flushed': app113.get('n_flushed'),
            'n_submitted_worker': len(rows),
            'n_drop_total_any_reason': (n_drop_worker + n_drop_overflow
                                        + n_drop_worker_failed),
            'reconciliation_expr': '%s（译文）== %s（进 TTS）+ %s（丢弃）'
                                   % (lp['n_translations'], len(rows),
                                      n_drop_worker + n_drop_overflow
                                      + n_drop_worker_failed),
            'reconciliation_ok': (lp['n_translations']
                                  == len(rows) + n_drop_worker
                                  + n_drop_overflow + n_drop_worker_failed),
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
            'asr_load_lines': lp['asr_load_lines'],
            'mt_ready_lines': lp['mt_ready_lines'],
        }
        ev['backlog_cleared_rel_s'] = app113.get('backlog_cleared_rel_s')
        ev['backlog_cleared_lag_kind'] = app113.get('backlog_cleared_lag_kind')

        # ── 判定（APP-114 §4 的判据）──
        n_drop_total = (n_drop_worker + n_drop_overflow + n_drop_worker_failed)
        checks = [
            {'name': '丢句数（任何原因）= 0',
             'pass': (n_drop_total == 0),
             'detail': 'worker丢弃=%d + 溢出丢弃=%d + worker失败丢弃=%d'
                       % (n_drop_worker, n_drop_overflow, n_drop_worker_failed)},
            {'name': '译文句数 == 进 TTS 句数 + 丢弃总数（无其它丢失路径）',
             'pass': ev['sentence_counts']['reconciliation_ok'],
             'detail': ev['sentence_counts']['reconciliation_expr']},
            {'name': '就绪前排队的句子**全部补发**（一句不丢）',
             'pass': ev['sentence_counts']['queue_flush_ok'],
             'detail': ev['sentence_counts']['queue_flush_expr']},
            {'name': '倍率 max ≤ %.2f（APP-114 §1）' % SPEED_CAP,
             'pass': (ev['telemetry']['speed_max'] is not None
                      and ev['telemetry']['speed_max'] <= SPEED_CAP + 1e-9),
             'detail': 'max=%s p50=%s p95=%s'
                       % (ev['telemetry']['speed_max'],
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
            {'name': '积压清空时刻（**报告项**：APP-114 §4「lag 数字只报告、'
                     '不设判定门槛」）',
             'pass': True, 'report_only': True,
             'detail': '积压清空=%s s（口径 %s；末句播放滞后 %s s；'
                       'lag max=%s s）'
                       % (app113.get('backlog_cleared_rel_s'),
                          app113.get('backlog_cleared_lag_kind'),
                          ev['telemetry'].get('play_lag_end'),
                          ev['telemetry'].get('play_lag_max'))},
            {'name': ('ASR/TTS 并行生效（并行=on）' if args.parallel == 'on'
                      else 'ASR/TTS 强制串行生效（并行=off，对照臂）'),
             'pass': (app113.get('parallel') is True
                      if args.parallel == 'on'
                      else app113.get('parallel') is False),
             'detail': 'parallel=%s（请求=%s）'
                       % (app113.get('parallel'), args.parallel)},
            {'name': 'preflight：被测包的语速上限=%.2f / 队列不按时间丢句'
                     % SPEED_CAP,
             'pass': bool(pf.get('ok')),
             'detail': 'speed_constants=%s queue_overflow_s=%s'
                       % (pf.get('speed_constants'), pf.get('queue_overflow_s'))},
            {'name': '队列行为探针（§2.1）：300 s 过期仍不丢句；'
                     'worker 失败才清空',
             'pass': bool(qp.get('ok')),
             'detail': '300s后保留=%s 丢弃=%s；worker失败清空=%s 计数=%s'
                       % (qp.get('after_300s_stale', {}).get('n_pending'),
                          qp.get('after_300s_stale', {}).get(
                              'n_drop_not_ready_overflow'),
                          qp.get('after_worker_failure', {}).get('n_cleared'),
                          qp.get('after_worker_failure', {}).get(
                              'n_drop_worker_failed'))},
        ]
        ev['checks'] = checks
        # 🔴 APP-114 §4：「lag 数字**只报告，不设判定门槛**」
        #   ⇒ 带 `report_only` 的条目**不进判定**（只出现在报告里）。
        ev['reports'] = [c for c in checks if c.get('report_only')]
        ev['n_fail'] = sum(1 for c in checks
                           if not c['pass'] and not c.get('report_only'))
        ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
        # ── APP-114 §4 明确要求「报」的指标（集中成一节，便于 reviewer 复算）──
        ev['required_report'] = {
            'speed_p50': ev['telemetry']['speed_p50'],
            'speed_p95': ev['telemetry']['speed_p95'],
            'speed_max': ev['telemetry']['speed_max'],
            'n_speed_ge_1_6': ev['telemetry']['n_speed_ge_1_6'],
            'n_speed_ge_1_7': ev['telemetry']['n_speed_ge_1_7'],
            'play_lag_max': ev['telemetry']['play_lag_max'],
            'play_lag_end': ev['telemetry']['play_lag_end'],
            'backlog_cleared_rel_s': ev['backlog_cleared_rel_s'],
            'backlog_cleared_lag_kind': ev['backlog_cleared_lag_kind'],
            'tts_ready_rel_s': app113.get('tts_ready_rel_s'),
            'asr_ready_s': app113.get('asr_ready_s'),
            'mt_ready_s': app113.get('mt_ready_s'),
            'sidecar_load_line': (lp['cuda_ready_lines'] or [None])[0],
            'timing_valid': ev['timing_valid'],
            'external_writes_during_run': ev['external_writes_during_run'],
            'gpu_apps_before': ev['gpu_apps_before'],
            'gpu_apps_after': ev['gpu_apps_after'],
            'note': ('lag / 积压清空**只报告**（APP-114 §4：追赶会变慢，'
                     'lag 数字不设判定门槛）⇒ 判定项只有 丢句=0 / 译文==进TTS / '
                     '排队==补发 / max≤1.70 / rc=0 / 产出齐备 / 无重复 id / '
                     '就绪时刻已记录 / 并行生效 / preflight / 队列探针。'),
        }

        # ── 抽 1.6–1.7× 的 wav（真实倍率标注）──
        ev['fast_samples'] = extract_fast_wavs(rows, tts_out, wav_dir, prefix,
                                                1.60, 1.70, 3, PKG_PY)
        ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    finally:
        if not args.no_lock:
            release_lock(ev.get('lock_evidence'))
        # 🔴 APP-115 §3.2：**放锁之后**才补报告项（放锁时刻的锁内容此时才有）
        finalize_app115(ev)

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
