#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-056：量化「App 的 TTS 首包」与「TTS 模块单测首包」差一个数量级的根因。

## reviewer 的问题（APP-018 第 1 条）
> App 里唯一的实测还是 §15（首包 P50 5.5 s、丢句 57%），和 TTS 模块单独实测的结果
> （持锁 RTF 0.79–0.86、首包约 0.5 s）差了一个数量级，**问题出在 App 的集成层**。

## 本探针要证明的事（**不假设，只测**）
假设 H1：**App 的 worker 把整句合成完才发 `first_packet`、才写播放缓冲**
        ⇒ App 报的「首包」其实是**整句合成耗时**，而不是首包延迟
        ⇒ 这正好等于「TTS 模块的 RTF × 句长」，**与 TTS 模块的 0.5 s 首包不矛盾**。

### 判据（三个数）
| 指标 | 含义 | 期望（若 H1 成立） |
|---|---|---|
| `t_first_block` | **第一块**音频可用的时刻（真实流式首包） | ≈ TTS 模块的 0.5 s |
| `t_all_blocks` | 整句合成完成时刻 | ≈ RTF × 句长（几秒） |
| `app_reported_first_packet` | App 现在**报出来的**首包 | **≈ `t_all_blocks`**，而不是 `t_first_block` |

⇒ 若 `app_reported_first_packet ≈ t_all_blocks` 且 `t_first_block << t_all_blocks`
   ⇒ **H1 成立**：App 报的「首包 5.5 s」是**整句耗时**，流式能力被白白浪费。

## 纪律
- 🔴 **持共享机器锁**（这是计时作业，且要与 ASR/MT 隔离）。
- 🔴 **不 import 被测模块**（`tts_worker` 顶部连带 numpy/openvino）⇒ 用 `ast` 抽
  `_synth_babelvox` 及其依赖的纯逻辑，或直接调 `tts_engine.stream()`（**引擎层是真实路径**）。
- 🔴 产物写**仓库外**。

用法（客户包 python）：
    python results/app/app056_tts_streaming_gap.py --text "这是一次语音输出的自测，用来确认朗读功能可以正常工作。"
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

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

ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
OUT_DIR = r'C:\Users\Trekker-PTL\abba_out'
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

DEFAULT_TEXT = '这是一次语音输出的自测，用来确认朗读功能可以正常工作。'


def _pid_alive(pid: int) -> bool:
    """PID 是否存活（Windows：OpenProcess 探测；不用 tasklist /FI）。"""
    import ctypes
    k = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if k.GetExitCodeProcess(h, ctypes.byref(code)):
            return code.value == 259          # STILL_ACTIVE
        return False
    finally:
        k.CloseHandle(h)


def acquire_lock(module='app', timeout_s=3600.0):
    """取共享机器锁（**fail-closed**：读不到/解析不出就等，不猜）。"""
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    t0 = time.time()
    while True:
        if not os.path.exists(LOCK):
                _pay = ('module: %s\npid: %d\nstarted: %s\n'
                        'host: %s\n'
                        % (module, os.getpid(),
                           time.strftime('%Y-%m-%d %H:%M:%S'),
                           os.environ.get('COMPUTERNAME', '?')))
                if machine_lock_app.write_lock_atomic(LOCK, _pay):
                    print('[lock] 已取得 %s' % LOCK)
                    return True
        # 已有锁 ⇒ 读它
        try:
            raw = io.open(LOCK, 'r', encoding='utf-8', errors='replace').read()
        except Exception:
            raw = ''
        pid = None
        for ln in raw.split('\n'):
            if 'PID=' in ln.upper():
                try:
                    pid = int(ln.upper().split('PID=')[1].split()[0].strip())
                except Exception:
                    pid = None
                break
        if pid and not _pid_alive(pid):
            print('[lock] 陈旧锁（pid=%d 已死）→ 回收' % pid)
            try:
                os.remove(LOCK)
            except OSError:
                pass
            continue
        if time.time() - t0 > timeout_s:
            print('[lock] 等锁超时 ⇒ 放弃')
            return False
        print('[lock] 等待中…（已等 %.0fs）' % (time.time() - t0), flush=True)
        time.sleep(10.0)


def release_lock():
    try:
        os.remove(LOCK)
        print('[lock] 已释放')
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--text', default=DEFAULT_TEXT)
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--voice', default='A')
    ap.add_argument('--no-lock', action='store_true')
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(PKG, 'app'))
    os.chdir(PKG)

    if not args.no_lock and not acquire_lock('app-056'):
        return 2

    rec = {'text': args.text, 'device': args.device, 'precision': args.precision}
    try:
        import numpy as np
        import tts_engine

        print('\n=== 加载引擎（生产配置：NPU INT8 + cp_decode NPU + 25 帧左上下文 + spkonly）===')
        t0 = time.perf_counter()
        eng = tts_engine.make_engine(device=args.device, precision=args.precision,
                                     on_log=lambda m: print('  ' + m))
        t_load = time.perf_counter() - t0
        rec['load_s'] = round(t_load, 2)
        print('  加载完成 %.1f s' % t_load)

        # spkonly：预计算参考 wav 的 speaker embedding（只算一次）
        ref = tts_engine.preset_voice_path()
        spk = tts_engine.speaker_embedding(eng, ref,
                                          on_log=lambda m: print('  ' + m))
        rec['ref_wav'] = ref
        rec['spk_shape'] = list(spk.shape) if spk is not None else None
        print('  speaker embedding: %s' % (rec['spk_shape'],))

        # 预热（排除首次编译/首帧开销）
        print('\n=== 预热（一次，模拟真实会话的第一句）===')
        t0 = time.perf_counter()
        _warm = list(tts_engine.stream(eng, '预热。', language='Chinese',
                                       speaker_embed=spk))
        rec['warmup_s'] = round(time.perf_counter() - t0, 2)
        print('  预热 %.1f s' % rec['warmup_s'])

        # ── 正式测量：逐块计时 ────────────────────────────────────────
        print('\n=== 正式测量（逐块计时）===')
        t_start = time.perf_counter()
        blocks = []
        for wav_chunk, srate in tts_engine.stream(
                eng, args.text, language='Chinese', speaker_embed=spk):
            t_now = time.perf_counter()
            w = np.asarray(wav_chunk, dtype=np.float32).reshape(-1)
            blocks.append({'t': round(t_now - t_start, 4), 'n': int(w.size),
                           'sr': int(srate)})
            print('  块 %2d：t=%.3f s  样本=%d (%.2f s)'
                  % (len(blocks), blocks[-1]['t'], w.size, w.size / float(srate)))
        t_all = time.perf_counter() - t_start

        total_samples = sum(b['n'] for b in blocks)
        rec.update({
            'n_blocks': len(blocks),
            't_first_block': blocks[0]['t'] if blocks else None,
            't_all_blocks': round(t_all, 4),
            'audio_s': round(total_samples / 24000.0, 3),
            'rtf': round(t_all / (total_samples / 24000.0), 4) if total_samples else None,
            'blocks': blocks,
        })
        print('\n  第一块可用 t = %.3f s   ← **真实流式首包**' % rec['t_first_block'])
        print('  整句完成 t = %.3f s   （音频 %.2f s，RTF %.3f）'
              % (t_all, rec['audio_s'], rec['rtf']))
        print('  ⇒ App 现在报的「首包」= **整句完成**（因为 first_packet 在'
              ' concatenate 之后才 emit）⇒ 报 %.3f s' % t_all)
        rec['app_reported_first_packet'] = round(t_all, 4)
        rec['gap_x'] = (round(t_all / rec['t_first_block'], 2)
                        if rec['t_first_block'] else None)
        print('  ⇒ **差距 %.1f×**（App 报的 vs 真实首包）' % (rec['gap_x'] or 0))

        rec['verdict'] = (rec['t_first_block'] is not None
                          and rec['t_all_blocks'] > 2 * rec['t_first_block'])
        rec['verdict_note'] = (
            'H1 成立：App 把整句合成完才发 first_packet/写缓冲 ⇒ '
            '报的首包 = 整句耗时（%.2f s），真实流式首包只有 %.2f s ⇒ '
            '**流式能力被完全浪费**；改造成边合成边写可把首包降到 ~%.2f s'
            % (t_all, rec['t_first_block'] or 0, rec['t_first_block'] or 0)
            if rec['verdict'] else
            'H1 不成立：第一块与整句完成时间接近 ⇒ 首包不是瓶颈')
        print('\n结论：%s — %s' % ('PASS' if rec['verdict'] else 'FAIL',
                                   rec['verdict_note']))
    except Exception as e:
        import traceback
        traceback.print_exc()
        rec['error'] = '%s: %s' % (type(e).__name__, e)
        rec['verdict'] = False
    finally:
        if not args.no_lock:
            release_lock()

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'app056_tts_streaming_gap.json')
    io.open(out, 'w', encoding='utf-8').write(
        json.dumps(rec, ensure_ascii=False, indent=1))
    print('\n结果：', out)
    return 0 if rec.get('verdict') else 1


if __name__ == '__main__':
    sys.exit(main())
