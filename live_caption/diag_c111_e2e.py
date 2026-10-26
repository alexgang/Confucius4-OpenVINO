r"""diag_c111_e2e.py — C-111 翻译层改动的**真实翻译模型**端到端对照

★ 切段规则**不动**（用户决策）⇒ ASR 侧完全不变 ⇒ 直接复用 C-109 的定稿产物
  （72 段真实 12 分钟演讲），只对比**翻译层**的两种行为：
  A) 旧机制（C-099① 挂起）：段尾半句不翻，等下一段首句拼起来一起翻
  B) 新机制（C-111 当段即翻 + 补全后修正）

对比指标：
  1. **翻译次数**：新机制多翻半句与修正，翻译负载增加多少
  2. **总墙钟 / 每段延迟**：翻译线程是否被压垮
  3. **译文产出时刻**：段定稿 → 该段译文出现的延迟（T3 痛点）
  4. **outbox 事件构成**：final / half / fix 各多少（决定 TTS 朗读次数）

⚠️ 本脚本是**测速**作业 —— 必须先持有 C:\Users\Trekker-PTL\shared\MACHINE_LOCK。
   本脚本**自己申请并释放**该锁（ASR-001 的共享机器锁规则）：
   锁已存在且持有者 PID 存活 ⇒ 直接退出（不抢、不排队、不干扰别的模块）；
   锁已存在但 PID 已不在 / 锁早于开机时间 ⇒ 回收后继续。

用法：
  python diag_c111_e2e.py
"""
from __future__ import annotations

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import translator as T

RUNS = r'C:/Users/Trekker-PTL/hy_bench/runs/c109_minseg6'
OUT = r'C:/Users/Trekker-PTL/hy_bench/runs/c111_half'
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



def _boot_time():
    """开机时间（Windows）。用于判定锁是否早于开机 ⇒ 可回收。"""
    try:
        import ctypes
        from ctypes import wintypes

        class SYSTEMTIME(ctypes.Structure):
            _fields_ = [('wYear', wintypes.WORD), ('wMonth', wintypes.WORD),
                        ('wDay', wintypes.WORD), ('wDayOfWeek', wintypes.WORD),
                        ('wHour', wintypes.WORD), ('wMinute', wintypes.WORD),
                        ('wSecond', wintypes.WORD),
                        ('wMilliseconds', wintypes.WORD)]
        st = SYSTEMTIME()
        ctypes.windll.kernel32.GetLocalTime(ctypes.byref(st))
        return time.mktime((st.wYear, st.wMonth, st.wDay,
                            st.wHour, st.wMinute, st.wSecond, 0, 0, -1))
    except Exception:
        return 0.0


def _pid_alive(pid):
    """PID 是否存活（不依赖 psutil）。"""
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        code = wintypes.DWORD()
        k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return code.value == STILL_ACTIVE
    except Exception:
        return False


def acquire_lock(tag='asr'):
    """申请共享机器锁。返回 True=拿到，False=锁被别的模块持有。"""
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    if os.path.exists(LOCK):
        info = {}
        try:
            with open(LOCK, encoding='utf-8') as f:
                for line in f:
                    if ':' in line:
                        k, v = line.split(':', 1)
                        info[k.strip()] = v.strip()
        except Exception:
            pass
        pid = int(info.get('pid', '0') or 0)
        started = info.get('started', '')
        alive = _pid_alive(pid) if pid else False
        boot = _boot_time()
        stale = (not alive)
        # 锁早于开机时间 ⇒ 上次运行残留的孤儿锁
        if not stale and started:
            try:
                st = time.mktime(time.strptime(started, '%Y-%m-%d %H:%M:%S'))
                if st < boot:
                    stale = True
            except Exception:
                pass
        if not stale:
            print(f'[lock] 机器锁被 {info.get("module", "?")} '
                  f'(PID {pid}) 持有 ⇒ 本作业跳过（不抢锁）', flush=True)
            return False
        print(f'[lock] 回收孤儿锁（PID {pid} alive={alive}）', flush=True)
        try:
            os.remove(LOCK)
        except Exception:
            pass
    _pay = ('module: %s\npid: %d\nstarted: %s\n'
            'host: %s\n'
            % (tag, os.getpid(),
               time.strftime('%Y-%m-%d %H:%M:%S'),
               os.environ.get('COMPUTERNAME', '?')))
    if not machine_lock_app.write_lock_atomic(LOCK, _pay):
        print('[lock] 原子写入失败（锁已被别人占用）', flush=True)
        return False
    return True


def release_lock():
    try:
        if os.path.exists(LOCK):
            with open(LOCK, encoding='utf-8') as f:
                if f'pid: {os.getpid()}' in f.read():
                    os.remove(LOCK)
    except Exception:
        pass


class OldCarrySvc:
    """C-099① 旧挂起机制的**忠实复刻**（用同一个真实翻译引擎）。

    与新机制的差异只有两点：
      * 段尾半句不翻，挂起到下一段
      * 挂起的半句译文归属**下一段**
    """

    def __init__(self, svc):
        self.svc = svc
        self.carry = ''
        self.seg_keys = {}
        self.seg_carry = {}

    def submit(self, sentence, seg=None):
        text = (sentence or '').strip()
        if not text:
            return []
        if self.carry:
            text = self.carry + ' ' + text
            self.carry = ''
            carried_in = True
        else:
            carried_in = False
        sents = T.split_sentences(text)
        has_carry = False
        if sents and not T.ends_sentence(sents[-1]):
            self.carry = sents[-1]
            sents = sents[:-1]
            has_carry = True
        keys = []
        for s in sents:
            k = T.norm_key(s)
            if not k or k in self.svc._seen:
                continue
            self.svc._seen.add(k)
            keys.append(k)
            if k in self.svc.done:
                continue
            self.svc.q.put(T._Job('final', k, s))
        if seg is not None:
            self.seg_keys[seg] = keys
            self.seg_carry[seg] = has_carry or carried_in
        return keys

    def flush(self, seg=None):
        if not self.carry:
            return []
        s, self.carry = self.carry, ''
        k = T.norm_key(s)
        if k and k not in self.svc._seen:
            self.svc._seen.add(k)
            if k not in self.svc.done:
                self.svc.q.put(T._Job('final', k, s))
        if seg is not None:
            self.seg_keys.setdefault(seg, [])
            if k not in self.seg_keys[seg]:
                self.seg_keys[seg].append(k)
        return [k] if k else []

    def mt_of_seg(self, seg):
        keys = self.seg_keys.get(seg)
        if not keys:
            return None
        parts = [self.svc.done.get(k) or '' for k in keys]
        out = ' '.join(p for p in parts if p).strip()
        return out or None


def reset_svc(svc):
    svc._seen.clear()
    svc.done.clear()
    svc._half = None
    svc.seg_keys.clear()
    svc.seg_carry.clear()
    svc.seg_half.clear()
    svc.outbox.clear()


def run_one(svc, finals, old_mode):
    """跑一遍定稿序列，返回统计。"""
    reset_svc(svc)
    adapter = OldCarrySvc(svc) if old_mode else svc
    t0 = time.perf_counter()
    per_seg = []
    for i, txt in enumerate(finals):
        ts = time.perf_counter()
        adapter.submit(txt, seg=i)
        # 等这一段的翻译全部出结果（模拟「串行消费」的上界）
        while svc.pending:
            time.sleep(0.01)
        per_seg.append(time.perf_counter() - ts)
    adapter.flush(seg=len(finals) - 1)
    svc.wait_idle(600)
    wall = time.perf_counter() - t0
    out = svc.pop_outbox()
    kinds = {}
    for k, _, _ in out:
        kinds[k] = kinds.get(k, 0) + 1
    lat = svc.lats[:]
    return dict(wall=wall, n_trans=len(out), kinds=kinds,
                per_seg=per_seg, out=out, lat=lat,
                done=dict(svc.done),
                seg_keys=dict(adapter.seg_keys if old_mode else svc.seg_keys),
                mt_of_seg=adapter.mt_of_seg)


def main():
    if not acquire_lock('asr'):
        raise SystemExit('机器锁被别的模块持有，本次跳过（请稍后重跑）')
    try:
        _main()
    finally:
        release_lock()


def _main():
    with open(os.path.join(RUNS, 'min6.0_cut0.8.json'), encoding='utf-8') as f:
        c109 = json.load(f)
    finals = c109['finals']
    print(f'C-109 定稿：{len(finals)} 段', flush=True)

    svc = T.TranslationService(target='zh', engine_key='gpu_int4cw',
                               on_log=lambda m: print('MT:', m, flush=True))
    for _ in range(600):
        if svc.state in ('ready', 'error'):
            break
        time.sleep(0.5)
    print(f'翻译模型 state={svc.state} load={svc.load_s:.1f}s', flush=True)
    if svc.state != 'ready':
        raise SystemExit('翻译模型未就绪')

    print('\n=== A) 旧机制（C-099① 挂起）===\n', flush=True)
    a = run_one(svc, finals, old_mode=True)
    print(f'  A 完成：翻译 {a["n_trans"]} 次，墙钟 {a["wall"]:.1f}s', flush=True)

    print('\n=== B) 新机制（C-111 当段即翻 + 补全后修正）===\n', flush=True)
    b = run_one(svc, finals, old_mode=False)
    print(f'  B 完成：翻译 {b["n_trans"]} 次，墙钟 {b["wall"]:.1f}s', flush=True)

    # ── 报告 ──
    def stat(x):
        v = sorted(x)
        return dict(med=round(v[len(v) // 2], 3),
                    p95=round(v[int(len(v) * 0.95)], 3),
                    mx=round(v[-1], 3))

    sa, sb = stat(a['per_seg']), stat(b['per_seg'])
    print('\n' + '=' * 74)
    print('C-111 端到端对照（真实翻译模型 INT4-CW，同一份 C-109 定稿 72 段）')
    print('=' * 74)
    print(f'\n[翻译负载]')
    print(f'  翻译次数   旧 {a["n_trans"]:4d}   新 {b["n_trans"]:4d}'
          f'   ({(b["n_trans"] - a["n_trans"]) / max(1, a["n_trans"]) * 100:+.1f}%)')
    print(f'  事件构成   旧 {a["kinds"]}')
    print(f'            新 {b["kinds"]}')
    print(f'  总墙钟     旧 {a["wall"]:.1f}s   新 {b["wall"]:.1f}s')
    print(f'  段提交→译完 中位 旧 {sa["med"]}s  新 {sb["med"]}s'
          f'   P95 旧 {sa["p95"]}s  新 {sb["p95"]}s')
    print(f'  最大       旧 {sa["mx"]}s  新 {sb["mx"]}s')

    # TTS 会朗读的次数（final + fix）
    said_a = a['kinds'].get('final', 0)
    said_b = b['kinds'].get('final', 0) + b['kinds'].get('fix', 0)
    print(f'\n[TTS 朗读次数]  旧 {said_a}   新 {said_b}'
          f'   （半句不朗读，只有完整句与修正版朗读）')

    # ── fix key 唯一性（C-111 回归：半句链闭合后 _half 未清空 ⇒ 槽位被反复修正）──
    fix_keys = [key for k, key, _ in b['out'] if k == 'fix']
    dup = {}
    for k in fix_keys:
        dup[k] = dup.get(k, 0) + 1
    dup = {k: c for k, c in dup.items() if c > 1}
    print(f'\n[fix key 唯一性]  fix 事件 {len(fix_keys)} 次，唯一 key '
          f'{len(set(fix_keys))} 个'
          f'   {"✓ 无重复" if not dup else "✗ 有重复: " + str(list(dup.items())[:5])}')
    bykey = {}
    for k, key, txt in b['out']:
        bykey.setdefault(key, []).append(k)
    bad_seq = []
    for key, seq in bykey.items():
        term = [x for x in seq if x in ('final', 'fix')]
        if len(term) > 1 or (term and seq.index(term[0]) != len(seq) - 1):
            bad_seq.append((key, seq))
    print(f'[事件序列合法性]  {"✓ 全部合法" if not bad_seq else "✗ %d 个异常: %s" % (len(bad_seq), bad_seq[:5])}')

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'c111_e2e.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(n_seg=len(finals),
                       old=dict(wall=a['wall'], n_trans=a['n_trans'],
                                kinds=a['kinds'], per_seg=a['per_seg'],
                                lat=a['lat']),
                       new=dict(wall=b['wall'], n_trans=b['n_trans'],
                                kinds=b['kinds'], per_seg=b['per_seg'],
                                lat=b['lat']),
                       fix_key_total=len(fix_keys),
                       fix_key_unique=len(set(fix_keys)),
                       fix_key_dup=dup,
                       bad_sequence_keys=[[k, s] for k, s in bad_seq],
                       old_out=a['out'], new_out=b['out']),
                  f, ensure_ascii=False, indent=1)
    print(f'\n已写 {OUT}/c111_e2e.json')


if __name__ == '__main__':
    main()
