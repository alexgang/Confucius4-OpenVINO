"""app074 — 端到端验证：cp936 父进程下，真实 `TTSService` + 真实 CUDA worker 不再误判退出。

## 目的

`app073` 用**假 worker** 复现并验证了根因（编码不匹配 ⇒ `UnicodeDecodeError`
⇒ 被 `except: pass` 吞掉 ⇒ 误判「worker 退出（rc=None）」）。

本脚本做**端到端确证**：用**包内 python**（无 `PYTHONUTF8` ⇒ cp936 父进程）
起**真实** `TTSService`（走真实 `tts_worker.py` 子进程 + 真实 CUDA 边车），
确认：
  ① worker 能正常 `ready`（不再一启动就「退出」）；
  ② 日志里的中文/符号被**正确读出**（不再抛解码异常）；
  ③ 提交一句后能**真的播出来**（`n_played >= 1`）；
  ④ 全程**没有**出现「worker 退出」。

## 与 app071 的差别

`app071` 是在 **UTF-8 父进程**下跑的（`python` 默认 UTF-8 模式或带 `PYTHONUTF8=1`）
⇒ **恰好绕过了这个 bug** ⇒ 所以当时「一切正常」，无法复现用户的报错。
本脚本**故意**用 cp936 父进程 ⇒ 复现用户的真实启动条件。

⚠️ 会真的加载 CUDA 模型（≈20–30 s）并占 GPU 显存；**不计时**、不写 timing
⇒ 不需要机器锁（数值/质量作业不需锁）。

用法：
    <PKG>\\python\\python.exe results\\app\\app074_tts_e2e_cp936.py
"""
from __future__ import annotations

import argparse
import locale
import os
import sys
import time

# 🔴🔴 2026-10-27 §62：**「真的出声」的唯一判据来源**（APP-021⑦ 的直接执行）
#   ⚠️ 旧判据 `n_played >= 1` 是 APP-021 点名**作废**的弱判据
#   （`played` 只表示「写进缓冲」⇒ 不代表出声；且探针随后 `close()` 会 kill worker
#     ⇒ 那句话可能整句还在缓冲里就被杀掉 ⇒ 什么都没证明）。
#   ⇒ 现在用 APP-021 明文指定的硬判据：**n_read 增量 ≥ 本句样本数** 且 **峰值 > 1e-2**。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_audible_criterion import (  # noqa: E402
    audible_verdict, describe_criterion, evaluate_audible,
    played_snapshot, sentence_played)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HOME = r'C:\Users\Trekker-PTL'


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
    if not cands:
        raise SystemExit('找不到客户包')
    return sorted(cands)[-1][1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='CUDA')
    ap.add_argument('--precision', default='bf16')
    ap.add_argument('--voice', default='A')
    ap.add_argument('--seconds', type=float, default=150.0)
    ap.add_argument('--text', default='这是一次离线朗读测试，用来确认语音输出是否正常。')
    args = ap.parse_args()

    pkg = discover_pkg()
    app_dir = os.path.join(pkg, 'app')
    sys.path.insert(0, app_dir)
    os.environ.setdefault('LIVECAP_PKG', pkg)

    # 🔴🔴🔴 **必须复刻 `live_caption_app.py` L57-58**：
    #       os.environ.setdefault('PYTHONUTF8', '1')
    #       os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    #   这两行是真实 App 启动时**必然**执行的 ⇒ 它们让 **worker 子进程写 UTF-8**；
    #   而本进程的 `locale.getpreferredencoding()` 仍是 **cp936**
    #   （环境变量只在解释器**启动前**才影响本进程 ⇒ 运行时 setdefault 改不了）。
    #   ⇒ **父进程 cp936 解码 / worker UTF-8 写出** ⇒ 编码不匹配 ⇒ 炸。
    #   ⚠️ 少了这两行，worker 会继承 cp936 写 GBK ⇒ 父子**恰好匹配** ⇒ 不复现
    #      （我第一版就漏了这两行 ⇒ 反证假通过，已修正）。
    os.environ.setdefault('PYTHONUTF8', '1')
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    print('=' * 78)
    print('app074 · 端到端：cp936 父进程 + 真实 TTSService + 真实 CUDA worker')
    print('=' * 78)
    print('父进程 preferred encoding = %s   （关键：必须是 cp936 才复现用户条件）'
          % locale.getpreferredencoding(False))
    print('父进程 PYTHONIOENCODING   = %s' % os.environ.get('PYTHONIOENCODING'))
    print('客户包 = %s' % pkg)
    print('-' * 78, flush=True)

    import tts_service
    import audio_source

    oid = audio_source.default_output_device_id()
    print('输出端点 id = %s' % oid)

    t0 = time.time()
    lines = []

    def on_log(m):
        s = '%7.2fs %s' % (time.time() - t0, m)
        print(s, flush=True)
        lines.append(s)

    svc = None
    verdict = 'FAIL（未完成）'
    try:
        svc = tts_service.TTSService(
            device=args.device, voice=args.voice, out_device=oid,
            precision=args.precision, on_log=on_log)

        t_end = time.time() + args.seconds
        submitted = False
        while time.time() < t_end:
            st = svc.stats()
            if st.get('state') == 'error':
                break
            if st.get('state') == 'ready' and not submitted:
                print('%7.2fs >>> state=ready，提交一句' % (time.time() - t0), flush=True)
                # 🔴🔴 §62：**提交前**抓快照 ⇒ 后面用**相对增量**判「本句播完」
                #   （`n_played` 是累计计数 ⇒ 常量阈值 `>= 1` 会把「历史上播过
                #    的别的句」当本句证据 ⇒ 假通过）。
                played_before, tel_id_before = played_snapshot(st)
                svc.submit(args.text, seg=0)
                submitted = True
                t_end = min(t_end, time.time() + 90)
            # 🔴🔴 2026-10-27 §62 修：**不再**用 `n_played >= 1` 当「已出声」判据
            #   （APP-021⑦ 的同族缺陷）⇒ 必须等**本句**的遥测齐了再停。
            if submitted:
                done, why = sentence_played(st, played_before, tel_id_before)
                if done:
                    print('%7.2fs >>> 本句已播完（%s）'
                          % (time.time() - t0, why), flush=True)
                    break
            time.sleep(0.3)

        st = svc.stats()
        print('-' * 78)
        print('最终 state=%s played=%s dropped=%s submitted=%s'
              % (st.get('state'), st.get('n_played'), st.get('n_dropped'),
                 st.get('n_submitted')))
        print('last_error = %r' % st.get('last_error'))

        all_log = '\n'.join(lines)
        exited = 'worker 退出' in all_log
        print('日志里出现过「worker 退出」：%s' % exited)

        checks = [
            ('① worker 成功 ready（没一启动就退出）',
             st.get('state') in ('ready', 'idle') and not exited),
            ('② 中文/符号日志被正确读出（无 UnicodeDecodeError）',
             'UnicodeDecodeError' not in all_log),
            ('③ 本句链路级真的出声（read_delta ≥ n_samples 且 peak > 1e-2）',
             evaluate_audible(st.get('last_telemetry'))[0]),
            ('④ 全程没有「worker 退出」', not exited),
            ('⑤ 没有残留的 worker 级故障原因', not st.get('last_error')),
        ]
        print('-' * 78)
        allok = True
        for name, cond in checks:
            print('%s %s' % ('PASS' if cond else 'FAIL', name))
            allok = allok and cond
        verdict = 'OK 端到端通过' if allok else 'FAIL'
        print('判定：%s' % verdict)
        lines.append('[app074] 判定：%s' % verdict)
    except Exception as e:
        import traceback
        traceback.print_exc()
        verdict = 'FAIL（异常）: %r' % (e,)
        lines.append('[app074] %s' % verdict)
    finally:
        if svc is not None:
            try:
                svc.close()
            except Exception:
                pass

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'app', 'app074_tts_e2e_cp936.txt')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# app074 端到端（cp936 父进程）  %s\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
        f.write('# pkg=%s device=%s precision=%s\n' % (pkg, args.device, args.precision))
        f.write('# parent preferred encoding = %s\n'
                % locale.getpreferredencoding(False))
        f.write('\n'.join(lines) + '\n')
    print('\n日志已写 %s' % out)
    return 0 if verdict.startswith('OK') else 1


if __name__ == '__main__':
    sys.exit(main())
