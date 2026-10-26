"""app072 — §52 回归测试：① 输出设备解析「同一 id ⇒ 同一设备」② 故障必带原因。

## 为什么要有这个测试

用户报的症状只有一句「TTS worker 故障（error）⇒ 朗读中止」。查下来有两层缺陷：

**① 设备解析结果不稳定**（`app071` 实测日志为证）
   同一个 WASAPI 端点 id：主线程解析 → 「播放索引 3」；
   `_reopen_player()`（在 `_safe_load` **线程**里）再解析 → 「无法识别 ⇒ 改用系统默认」。
   原因 = `soundcard` 取扬声器列表要 COM，那个线程没初始化过 ⇒ 异常被吞。
   后果 = 用户在下拉里选的设备被**悄悄换掉**；若默认设备也不可用 ⇒ 播放流打不开
   ⇒ **worker 级 error** ⇒ 整场中止。

**② 故障不带原因**
   worker 级 error 的 message 已经发到主进程，但只塞进 `self.err`，界面从不显示
   ⇒ 用户和我都只能看到「worker 故障」四个字。

## 本脚本测什么（全部不加载 TTS 模型）

| 段 | 测的东西 | 手法 |
|---|---|---|
| A | `resolve_out_device` 在主线程/子线程给出**相同**结果，且第二次走缓存 | 直接调 worker 模块的函数（import tts_worker 是安全的：它顶层不 import numpy） |
| B | worker 级 error ⇒ `stats()['last_error']` 有原文 + `tts_worker_error.log` 落盘 | 把 `tts_service._WORKER` 换成一个「立刻报错」的假 worker 进程 |
| C | 对话框在 error 状态下**显示原因**并启用「↻ 重试」；重试成功后能开始朗读 | 真 Tk + 假 service（`state='error'` → 重试后变 `ready`） |

用法（用包内 python，有 tkinter/soundcard/sounddevice）：
    <PKG>\\python\\python.exe results\\app\\app072_tts_error_reason_test.py
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
HOME = r'C:\Users\Trekker-PTL'
LINES = []
N_PASS = N_FAIL = 0


def say(s=''):
    print(s)
    LINES.append(s)


def check(name, ok, detail=''):
    global N_PASS, N_FAIL
    if ok:
        N_PASS += 1
        say(f'  PASS  {name}' + (f'  [{detail}]' if detail else ''))
    else:
        N_FAIL += 1
        say(f'  FAIL  {name}' + (f'  [{detail}]' if detail else ''))


def discover_pkg() -> str:
    cands = []
    for name in os.listdir(HOME):
        if name.startswith('Confucius4_LiveCaption_v') and \
                os.path.isdir(os.path.join(HOME, name, 'app')):
            try:
                cands.append((float(name.rsplit('_v', 1)[1]),
                              os.path.join(HOME, name)))
            except Exception:
                pass
    return sorted(cands)[-1][1]


# 假 worker：只说一句 worker 级 error 然后等 stdin（不退出，模拟真实 worker 行为）
FAKE_WORKER = r'''
import json, sys, time
sys.stdout.write(json.dumps({"kind": "error",
                             "message": "合成侧假故障：用于测试 last_error"},
                            ensure_ascii=False) + "\n")
sys.stdout.flush()
for line in sys.stdin:      # 真实 worker 报完错也不退进程（§47 教训）
    time.sleep(0.05)
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        _REPO, 'results', 'app', 'app072_tts_error_reason_test.txt'))
    args = ap.parse_args()

    pkg = discover_pkg()
    sys.path.insert(0, os.path.join(pkg, 'app'))
    os.environ.setdefault('LIVECAP_PKG', pkg)
    say('=' * 78)
    say('app072 §52 回归测试（不加载 TTS 模型）')
    say(f'ts={time.strftime("%Y-%m-%d %H:%M:%S")} pkg={pkg}')
    say(f'python={sys.version.split()[0]}')
    say('=' * 78)

    # ══ A. 设备解析稳定性 ══════════════════════════════════════════════
    say('\n[A] resolve_out_device：同一 id ⇒ 同一设备（主线程 vs 子线程）')
    import audio_source
    import tts_worker
    outs = audio_source.list_output_devices()
    oid = audio_source.default_output_device_id()
    say(f'  端点 id = {oid}')
    say(f'  可选输出 {len(outs)} 个')
    main_res = tts_worker.resolve_out_device(oid)
    say(f'  主线程解析 ⇒ {main_res}')
    box = {}

    def _in_thread():
        box['res'] = tts_worker.resolve_out_device(oid)
    th = threading.Thread(target=_in_thread)
    th.start()
    th.join(10)
    sub_res = box.get('res')
    say(f'  子线程解析 ⇒ {sub_res}')
    check('主线程能解析出设备（不是 None）', main_res[0] is not None, str(main_res))
    # ⚠️ 只比**设备**，不比 note：第二次的 note 会带「（缓存）」后缀（那正是我们要的）
    check('子线程解析出的**设备**与主线程相同',
          bool(sub_res) and sub_res[0] == main_res[0],
          f'{sub_res} vs {main_res}')
    check('第二次走缓存（note 含「缓存」）',
          bool(sub_res) and '缓存' in sub_res[1], str(sub_res))
    # 反证：清掉缓存后，在**全新线程**里首次解析也必须拿到设备（CoInitializeEx 生效）
    with tts_worker._OUT_DEV_LOCK:
        tts_worker._OUT_DEV_CACHE.clear()
    box2 = {}

    def _cold_thread():
        box2['res'] = tts_worker.resolve_out_device(oid)
    t2 = threading.Thread(target=_cold_thread)
    t2.start()
    t2.join(10)
    cold = box2.get('res')
    say(f'  清缓存后子线程首次解析 ⇒ {cold}')
    check('冷缓存 + 子线程也能解析（COM 初始化生效）',
          bool(cold) and cold[0] is not None, str(cold))

    # ══ B. 故障必带原因 ════════════════════════════════════════════════
    say('\n[B] worker 级故障 ⇒ last_error + 落盘日志')
    import tts_service
    tmp_w = os.path.join(tempfile.gettempdir(), '_app072_fake_worker.py')
    with open(tmp_w, 'w', encoding='utf-8') as f:
        f.write(FAKE_WORKER)
    orig_worker = tts_service._WORKER
    tts_service._WORKER = tmp_w
    # 日志文件先备份/清掉，避免旧内容干扰断言
    logp = os.path.join(os.environ.get('LOCALAPPDATA', HOME),
                        'Confucius4LiveCaption', 'tts_worker_error.log')
    old = b''
    if os.path.isfile(logp):
        old = open(logp, 'rb').read()
    svc = None
    try:
        svc = tts_service.TTSService(device='CUDA', voice='A', precision='f16',
                                     on_log=lambda m: None)
        t_end = time.time() + 20
        while time.time() < t_end and svc.state != 'error':
            time.sleep(0.1)
        st = svc.stats()
        say(f'  state={st["state"]}  last_error={st.get("last_error")!r}')
        check('state 变成 error', st['state'] == 'error')
        check('stats() 带出 worker 级错误原文（含「假故障」）',
              bool(st.get('last_error')) and '假故障' in str(st['last_error']),
              str(st.get('last_error'))[:60])
        check('日志尾巴有内容（≥1 行）', len(svc.log_tail) >= 1,
              f'{len(svc.log_tail)} 行')
        ok_file = os.path.isfile(logp) and os.path.getsize(logp) > len(old)
        check('tts_worker_error.log 已追加', ok_file,
              f'{logp} {os.path.getsize(logp) if os.path.isfile(logp) else -1} B')
        if ok_file:
            body = open(logp, 'r', encoding='utf-8', errors='replace').read()
            check('日志文件里有原因与设备信息',
                  '假故障' in body and 'device=CUDA' in body,
                  f'{len(body)} 字符')
    finally:
        tts_service._WORKER = orig_worker
        if svc is not None:
            try:
                svc.close()
            except Exception:
                pass
        try:
            os.remove(tmp_w)
        except Exception:
            pass

    # ══ C. 对话框：显示原因 + 重试 ═════════════════════════════════════
    say('\n[C] 对话框在 error 下显示原因并可重试')
    try:
        import tkinter as tk
        import offline_reader as OR
        import offline_reader_gui as G
    except Exception as e:
        check('tkinter 可用', False, repr(e))
        return _finish(args)

    class FakeErrSvc:
        """卡在 error 的 service（stats 带 last_error）。"""
        def __init__(self):
            self.lock = threading.RLock()
            self.pending = {}
            self.state = 'error'
            self.n_submitted = self.n_played = self.n_dropped = 0
            self.log_tail = ['10:00:00 [TTS] 模型加载失败：演示原因']

        def stats(self):
            return dict(state=self.state, n_played=self.n_played,
                        n_dropped=self.n_dropped,
                        n_submitted=self.n_submitted,
                        last_error='模型加载失败：演示原因（CUDA 边车启动超时）')

        def submit(self, text, seg=None):
            with self.lock:
                self.pending[len(self.pending)] = dict(seg=seg, text=text)
                self.n_submitted += 1
            self.n_played += 1
            with self.lock:
                self.pending.pop(next(iter(self.pending)), None)

        def cancel(self, jid):
            with self.lock:
                if self.pending.pop(jid, None) is not None:
                    self.n_dropped += 1

    root = tk.Tk()
    root.geometry('240x120+2600+2600')
    root.update()
    bad = FakeErrSvc()
    good = FakeErrSvc()
    good.state = 'ready'
    state = {'cur': bad, 'n_ensure': 0}

    def ensure():
        """第 1 次：重启**也失败**（模拟 CUDA 环境缺失/加载仍失败）；
        第 2 次（用户点「↻ 重试」）：成功。"""
        state['n_ensure'] += 1
        if state['n_ensure'] == 1:
            return bad
        state['cur'] = good
        return good
    dlg = G.OfflineReaderDialog(root, lambda: state['cur'], ensure,
                                on_log=lambda m: None,
                                get_reason=lambda: (
                                    state['cur'].stats().get('last_error'),
                                    state['cur'].log_tail))
    root.update()
    dlg.geometry('920x660+40+40')
    for _ in range(30):
        root.update()
        time.sleep(0.02)
    dlg.txt.insert('1.0', '这是一段测试文本。第二句在这里。')
    dlg.btn_start.invoke()
    root.update()
    note = dlg.var_note.get()
    say(f'  重启仍失败时的提示：{note!r}')
    check('提示里带出了**具体原因**', '演示原因' in note, note[:60])
    check('重试按钮已启用', str(dlg.btn_retry['state']) == 'normal')
    dlg.btn_retry.invoke()
    for _ in range(60):
        root.update()
        if dlg._reader is not None and dlg._reader.n_fed > 0:
            break
        time.sleep(0.03)
    check('重试后换到好的 service 并开始朗读',
          dlg._reader is not None and dlg._reader.n_fed >= 1,
          f'fed={getattr(dlg._reader, "n_fed", None)}')
    check('重试成功后不再显示错误',
          '🔴' not in dlg.var_note.get(), dlg.var_note.get()[:40])
    dlg._on_close()
    try:
        root.destroy()
    except Exception:
        pass

    return _finish(args)


def _finish(args) -> int:
    say('\n' + '=' * 78)
    say(f'结果：PASS {N_PASS} / FAIL {N_FAIL}')
    say('⚠️ 本测试不加载 TTS 模型：A 段直接调设备解析，B 段用「假 worker」进程，'
        'C 段用假 service。真实音频仍由人工朗读确认。')
    say('=' * 78)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(LINES) + '\n')
    print(f'已写 {args.out}')
    return 0 if N_FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
