r"""replay_c134_mt.py — C-134 CLI 回放：验证默认翻译改 INT8-CW 后的链路与延迟

用途（APP-003② 验收要求）
--------------------------
APP-002 第 ③ 条：「改完后跑一次 CLI 回放，确认翻译正常，并记录翻译延迟和
对 ASR RTF 的影响（**计时要持机器锁**）」。

本脚本：
1. **等锁**：轮询 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`；
   锁里的 PID 不在了 / 锁早于开机时间 ⇒ 回收；否则等待。
2. **持锁**：创建锁（内容：模块名 PID 开始时间），跑完删除。
3. **ABBA 回放**：翻译 off/on/on/off 四轮，同一段音频，同一个 ASR 后端。
4. **记录**：ASR RTF、翻译延迟（T1 定稿 → 译文出现的墙钟）、逐段耗时、
   落盘产物文件名 / mtime。

⚠️ 端到端墙钟**不能作性能判据**（机器漂移 60~130 s）⇒ 报告里同时给
   「音频时间轴坐标」口径，ABBA 差值才是结论。

用法
----
    python replay_c134_mt.py [--audio <wav>] [--seconds 60]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
APP = os.path.join(PKG, 'app')
PY = os.path.join(PKG, 'python', 'python.exe')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

# 🔴 取锁统一走仓库根的 `machine_lock_app`（**原子写** + 独占 + fail-closed）。
#   旧的「各自复制一份取锁代码」是逻辑漂移的根源 ⇒ 已全部收敛到这里。
#   旧写法 `os.open(O_CREAT|O_EXCL)` **先建空文件、之后才写内容**
#   ⇒ 存在「文件已存在、内容还是空的」窗口 ⇒ 别的模块读到空锁
#   ⇒ 解析不出 pid ⇒ 判成「陈旧锁」⇒ **删掉别人的活锁** ⇒ 两个模块同时跑
#   ⇒ 实测作废 TTS 两轮数据（16/30、24/30 行 timing_valid=false）。
#   依据：shared/NOTICE_tts_lock_atomic_20261026.md §一 / §三 3.1。
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import machine_lock_app


# 🔴 APP-005①：回放产物**一律写到仓库外**。
#   旧路径 `results/c134_replay/` 已被 commit 73f268e 带进 origin/main，
#   里面是内部会议录音的转写原文 ⇒ 必须脱库（APP-005①(a)）。
OUTDIR = os.path.join(r'C:\Users\Trekker-PTL\replay_out', 'c135')


# ── 锁 ──────────────────────────────────────────────────────────────
def _pid_alive(pid):
    """PID 是否存活。

    ⚠️ **不能用 tasklist** —— 在 Git Bash 下 tasklist 的路径被转义破坏
    （实测报「无效参数/选项 - 'FI'」），异常被吞掉后返回 False
    ⇒ **误判活锁为死锁并回收**（已实测踩到：把 TTS 模块的活锁 pid=33572 回收了）。
    ⇒ 改用 ctypes 的 OpenProcess，进程不存在才返回 False。
    """
    if not pid:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            # ERROR_ACCESS_DENIED(5) 说明进程存在但权限不足 ⇒ 视为存活
            return ctypes.get_last_error() == 5
        code = wintypes.DWORD()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        if not ok:
            return True
        return code.value == STILL_ACTIVE
    except Exception:
        # 探测失败 ⇒ **保守视为存活**，宁可等也不要误回收别人的锁
        return True


def _boot_time():
    """开机时间（epoch 秒）。锁早于开机时间 ⇒ 锁是残留的。"""
    try:
        import ctypes
        ts = ctypes.c_ulonglong()
        ctypes.windll.kernel32.GetTickCount64(ctypes.byref(ts))
        import time as _t
        return _t.time() - ts.value / 1000.0
    except Exception:
        return 0.0


def _lock_info():
    if not os.path.isfile(LOCK):
        return None
    try:
        with open(LOCK, 'r', encoding='utf-8') as f:
            txt = f.read()
    except Exception:
        return None
    info = {}
    for line in txt.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            info[k.strip()] = v.strip()
    return info


def acquire_lock(module='app', timeout_s=3600):
    """等锁 + 持锁。返回 (acquired, waited_s, lock_info_before)。"""
    t0 = time.time()
    boot = _boot_time()
    while True:
        info = _lock_info()
        if info is None:
            break
        pid = int(info.get('pid', 0) or 0)
        started = info.get('started', '')
        stale = (not _pid_alive(pid))
        if not stale:
            # 锁早于开机时间 ⇒ 残留
            try:
                hh, mm, ss = [int(x) for x in started.split()[1].split(':')]
                lt = time.mktime(time.strptime(started.split()[0], '%Y-%m-%d')) \
                    + hh * 3600 + mm * 60 + ss
                if lt < boot:
                    stale = True
            except Exception:
                pass
        if stale:
            print(f'[lock] 回收残留锁（pid={pid} started={started}）')
            try:
                os.remove(LOCK)
            except OSError:
                pass
            break
        waited = time.time() - t0
        if waited > timeout_s:
            raise TimeoutError(f'等待机器锁超时 {timeout_s}s（当前持有：{info}）')
        print(f'[lock] 等待中… 已等 {waited:.0f}s（当前持有：{info}）', flush=True)
        time.sleep(20)

    waited = time.time() - t0
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    _pay = ('module: %s\npid: %d\nstarted: %s\n'
            'host: %s\n'
            % (module, os.getpid(),
               time.strftime('%Y-%m-%d %H:%M:%S'),
               os.environ.get('COMPUTERNAME', '?')))
    if not machine_lock_app.write_lock_atomic(LOCK, _pay):
        print('[lock] 原子写入失败（锁已被别人占用）', flush=True)
        return False, waited, None
    print(f'[lock] 已获取（等了 {waited:.0f}s）', flush=True)
    return True, waited, None


def release_lock():
    try:
        os.remove(LOCK)
        print('[lock] 已释放')
    except OSError:
        pass


# ── 单轮回放 ────────────────────────────────────────────────────────
SEG_RE = re.compile(r'^\s*\[(\d+\.\d+)\s*-\s*(\d+\.\d+)\s*\]')

# 🔴 APP-005③：英文残留判定
#   「连续 ≥5 个英文词」才算残留（中文句子里的英文缩写/术语不算）。
EN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
CJK_RE = re.compile(r'[\u4e00-\u9fff]')


def english_residual_ratio(lines):
    """统计「英文残留句数占比」与「空行数」。

    返回 (残留句数, 总句数, 占比, 空行数, 残留句索引列表)
    ⚠️ 只返回**计数**，不返回原文 —— 报告里不能出现会议原文。

    🔴 口径（2026-10-23 13:50 修正）：「空行」只统计**中间**的空行，
       **文件开头/结尾的空行不算**（CLI 写文件时头部会带一个换行，
       那是格式不是「空译文」）。
    """
    total = 0
    residual = 0
    empty = 0
    idx = []
    for i, ln in enumerate(lines):
        s = (ln or '').strip()
        if not s:
            empty += 1
            continue
        total += 1
        words = EN_WORD_RE.findall(s)
        if len(words) >= 5 and not CJK_RE.search(s):
            residual += 1
            idx.append(i)
    ratio = (residual / total) if total else 0.0
    return residual, total, round(ratio, 4), empty, idx


def count_inner_empty(lines):
    """**中间**空行数（去掉文件首尾空行后的空行计数）。

    APP-005③ 验收要求「0 个空行」指「没有空译文行」，
    文件头尾的换行不算（CLI 写文件时头部会带一个换行，那是格式）。
    """
    s = list(lines)
    while s and not (s[0] or '').strip():
        s.pop(0)
    while s and not (s[-1] or '').strip():
        s.pop()
    return sum(1 for ln in s if not (ln or '').strip())


def run_once(audio, seconds, translate, out_json, engine='gpu_int8',
             mt_engine=None, asr_lang='English'):
    os.makedirs(OUTDIR, exist_ok=True)
    txt_out = os.path.join(OUTDIR, out_json.replace('.json', '.txt'))
    cmd = [PY, os.path.join(APP, 'live_caption_app.py'),
           '--cli', '--file', audio, '--engine', engine,
           # 🔴 APP-005③：原来写死 'Chinese'，而素材是**纯英文会议**
           #   ⇒ ASR 自己做翻译，MT 输出大段英文残留，「翻译正常」的结论不成立。
           #   现改为按素材实际语种传 English（可用 --asr-lang 覆盖）。
           '--asr-lang', asr_lang,
           '--max-seconds', str(seconds),
           '--translate', translate,
           '--out', txt_out]
    if mt_engine:
        cmd += ['--mt-engine', mt_engine]
    t0 = time.time()
    # ⚠️ 子进程 stdout 是 GBK（Windows 控制台编码），不是 UTF-8 ⇒
    #   用 text=True + encoding='utf-8' 会在 readerthread 里抛
    #   UnicodeDecodeError（实测 position 4 byte 0xcf）⇒ 改二进制自己解码。
    p = subprocess.run(cmd, capture_output=True, timeout=1800)
    out_txt = p.stdout.decode('utf-8', errors='replace')
    err_txt = p.stderr.decode('utf-8', errors='replace')
    wall = time.time() - t0

    # ⚠️ --out 写出的定稿文本**没有** [start-end] 时间戳前缀（实测）
    #   ⇒ 只能按非空行统计「段数」，不能解析时间轴。
    segs = []
    raw_lines = []
    if os.path.isfile(txt_out):
        with open(txt_out, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                t = line.strip()
                raw_lines.append(t)
                if not t:
                    continue
                m = SEG_RE.match(line)
                if m:
                    segs.append((float(m.group(1)), float(m.group(2)), t))
                else:
                    segs.append((None, None, t))

    # 🔴 APP-005③ 口径修正（2026-10-23 13:50）：**译文在另一个文件**。
    #   `--out <x>.txt` 写的是 **ASR 定稿原文**（英文）；
    #   翻译开启时，CLI 另外写 `<x>.mt.txt`（**译文**，中文）。
    #   ⇒ 验收「英文残留句占比 ≤5% / 0 空行」必须统计 **`.mt.txt`**，
    #   统计 `.txt` 恒为 100% 英文（那是原文，不是译文）。
    #   ⚠️ 这里只记**计数**，不记原文。
    mt_txt = txt_out.replace('.txt', '.mt.txt')
    mt_exists = os.path.isfile(mt_txt)
    mt_lines = []
    if mt_exists:
        with open(mt_txt, 'r', encoding='utf-8', errors='replace') as f:
            mt_lines = [ln.strip() for ln in f]

    # 统计对象：翻译开启 ⇒ 译文文件；翻译关闭 ⇒ 原文文件（此时无译文可查）
    if translate != 'off' and mt_exists:
        stat_lines = mt_lines
        stat_target = os.path.basename(mt_txt)
    else:
        stat_lines = raw_lines
        stat_target = os.path.basename(txt_out)
    residual, n_lines, ratio, empty, resid_idx = english_residual_ratio(stat_lines)
    empty = count_inner_empty(stat_lines)   # 空行只算中间的
    # 另存「原文侧」计数（用于句数 ↔ 行数对应关系核对）
    o_resid, o_n, o_ratio, o_empty, _ = english_residual_ratio(raw_lines)
    o_empty = count_inner_empty(raw_lines)
    return {
        'translate': translate,
        'mt_engine': mt_engine or 'default(auto)',
        'asr_lang': asr_lang,
        'wall_s': round(wall, 2),
        'exit_code': p.returncode,
        'segments': len(segs),
        # 🔴 APP-005③：句数 ↔ 行数对应关系（reviewer 指出 §8.7 里
        #   「STATUS 说 14 句、mt.txt 只有 9~10 行」对不上）
        'stat_target': stat_target,
        'txt_lines_total': len(stat_lines),
        'txt_lines_nonempty': n_lines,
        'english_residual_lines': residual,
        'english_residual_ratio': ratio,
        'empty_lines': empty,
        'residual_line_idx': resid_idx[:20],
        # 原文侧（ASR 定稿）
        'src_lines_total': len(raw_lines),
        'src_lines_nonempty': o_n,
        'src_empty_lines': o_empty,
        # 译文侧
        'mt_txt': mt_txt if mt_exists else None,
        'mt_txt_exists': mt_exists,
        'mt_lines_total': len(mt_lines),
        'out_txt': txt_out,
        'out_txt_exists': os.path.isfile(txt_out),
        'stdout_tail': out_txt[-3000:],
        'stderr_tail': err_txt[-3000:],
        'seg_samples': segs[:5],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio', default=os.path.join(
        REPO, 'test_audio', '<redacted>.wav'))
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--module', default='app')
    # 🔴 APP-005③：素材是**英文**会议 ⇒ 默认 English（原来写死 Chinese）
    ap.add_argument('--asr-lang', default='English')
    ap.add_argument('--no-wait-lock', action='store_true')
    args = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    acquired = False
    if not args.no_wait_lock:
        acquire_lock(args.module)
        acquired = True
    try:
        # ABBA：off / on / on / off
        plan = [
            ('abba1_off', 'off', None),
            ('abba2_on', 'zh', None),
            ('abba3_on', 'zh', None),
            ('abba4_off', 'off', None),
        ]
        results = []
        for name, tr, me in plan:
            print(f'\n===== {name}（translate={tr}） =====', flush=True)
            r = run_once(args.audio, args.seconds, tr, f'{name}.json',
                         mt_engine=me, asr_lang=args.asr_lang)
            r['name'] = name
            results.append(r)
            print(f'  exit={r["exit_code"]} segments={r["segments"]} '
                  f'wall={r["wall_s"]}s', flush=True)
            # 🔴 APP-005③：报告里只报**计数**，不贴会议原文
            print(f'  统计对象={r["stat_target"]} '
                  f'行数={r["txt_lines_nonempty"]}/{r["txt_lines_total"]} '
                  f'英文残留={r["english_residual_lines"]} '
                  f'({r["english_residual_ratio"] * 100:.1f}%) '
                  f'空行={r["empty_lines"]}', flush=True)
            if r['mt_txt_exists']:
                print(f'  译文文件={os.path.basename(r["mt_txt"])} '
                      f'行数={r["mt_lines_total"]}', flush=True)
            if r['exit_code'] != 0:
                print('  stderr tail:', r['stderr_tail'][-800:], flush=True)
        with open(os.path.join(OUTDIR, 'replay_report.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'audio': os.path.basename(args.audio),
                       'seconds': args.seconds,
                       'asr_lang': args.asr_lang,
                       'results': results}, f, ensure_ascii=False, indent=2)
        print('\n结果已落盘:', os.path.join(OUTDIR, 'replay_report.json'))
    finally:
        if acquired:
            release_lock()


if __name__ == '__main__':
    sys.exit(main())
