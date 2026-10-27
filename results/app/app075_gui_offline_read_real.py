"""app075 — 真实 GUI 点击路径验证（cp936 父进程）：点「📖 离线朗读…」→ 真的出声。

## 目的

`app074` 验证的是「真实 `TTSService` + 真实 CUDA worker」这条链路，
但**不是**用户实际点的那个按钮。

本脚本起**真实的 `live_caption_app.py` GUI**（Tk），在 cp936 父进程下：
  ① 通过内部方法打开「📖 离线朗读…」对话框（等价于点那个按钮）；
  ② 在对话框里填入文本 → 点「▶ 开始朗读」；
  ③ 等到**真的播出一句**（`n_played >= 1`）；
  ④ 截屏存档。

⚠️ 会真的加载 CUDA 模型并**真的播放声音**（本机默认输出：Realtek 扬声器）。
   不计时 ⇒ 不需要机器锁。

用法：
    <PKG>\\python\\python.exe results\\app\\app075_gui_offline_read_real.py
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
OUT_DIR = r'C:\Users\Trekker-PTL\abba_out'


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
    ap.add_argument('--seconds', type=float, default=200.0)
    ap.add_argument('--text', default='离线朗读验证：这段文字应该被真实朗读出来。')
    args = ap.parse_args()

    pkg = discover_pkg()
    app_dir = os.path.join(pkg, 'app')
    sys.path.insert(0, app_dir)
    os.environ.setdefault('LIVECAP_PKG', pkg)

    print('=' * 78)
    print('app075 · 真实 GUI 点击路径（cp936 父进程）')
    print('=' * 78)
    print('父进程 preferred encoding = %s' % locale.getpreferredencoding(False))
    print('客户包 = %s' % pkg)
    print('-' * 78, flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)

    import tkinter as tk
    import live_caption_app as app_mod

    # 🔴 用**真实的** argparse 定义构造 args（照抄 `main()` 的 add_argument 语义）
    #   —— 不猜字段名，避免 App.__init__ 读到不存在的属性。
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--engine', default='gpu_int8')
    ap.add_argument('--source', default=None)
    ap.add_argument('--device', type=int, default=None)
    ap.add_argument('--system-device', default=None)
    ap.add_argument('--file', default=None)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--loop', action='store_true')
    ap.add_argument('--cli', action='store_true')
    ap.add_argument('--max-seconds', type=float, default=0.0)
    ap.add_argument('--out', default=None)
    ap.add_argument('--font-size', type=int, default=26)
    ap.add_argument('--autostart', action='store_true')
    ap.add_argument('--selftest', type=float, default=0.0)
    ap.add_argument('--selftest-out', default=None)
    ap.add_argument('--selftest-mt-switch', action='store_true')
    ap.add_argument('--list-devices', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--asr-lang', default='auto')
    ap.add_argument('--translate', default='off')
    ap.add_argument('--mt-engine', default='auto')
    ap.add_argument('--mt-ctx', action='store_true')
    ap.add_argument('--mt-glossary', action='store_true')
    ap.add_argument('--mt-draft', action='store_true')
    ap.add_argument('--tts', default='on')
    ap.add_argument('--tts-precision', default='f32')
    ap.add_argument('--tts-voice', default='A')
    ap.add_argument('--tts-out', default=None)
    ap.add_argument('--tts-out-device', default=None)
    ap.add_argument('--asr-device', default=None)
    ap.add_argument('--mt-device', default=None)
    ap.add_argument('--tts-device', default='CUDA')
    args_ns = ap.parse_args()
    # 设备解析（照 main() 的做法）
    import device_config
    _dev_sel, _dev_notes = device_config.get_devices(
        {'asr': args_ns.asr_device, 'mt': args_ns.mt_device,
         'tts': args_ns.tts_device})
    args_ns.asr_device = _dev_sel['asr']
    args_ns.mt_device = _dev_sel['mt']
    args_ns.tts_device = _dev_sel['tts']
    args_ns.device_notes = _dev_notes
    args_ns.source = 'mic'
    print('参数：tts=%s device=%s precision=%s'
          % (args_ns.tts, args_ns.tts_device, args_ns.tts_precision))

    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        print('🔴 起 Tk 失败：%r' % (e,))
        return 2

    # 用 App 的真实 GUI 类
    gui = None
    try:
        cls = getattr(app_mod, 'App', None)
        if cls is None:
            print('🔴 找不到 App 类')
            return 2
        gui = cls(root, args_ns)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('🔴 起 GUI 失败：%r' % (e,))
        return 2

    verdict = 'FAIL（未完成）'
    lines = []
    try:
        # ① 打开离线朗读对话框（等价于点按钮）
        gui._open_offline_reader()
        root.update()
        time.sleep(0.5)
        # ⚠️ `open_dialog()` 把窗口挂在 **master（root）** 上，不是 App 实例上
        dlg = getattr(root, '_offline_dlg', None)
        if dlg is None:
            dlg = getattr(gui, '_offline_dlg', None)
        print('对话框已打开：%s' % (dlg is not None))
        if dlg is None:
            print('🔴 对话框没打开')
            return 2

        # ② 填文本 → 点「开始朗读」
        dlg.txt.delete('1.0', 'end')
        dlg.txt.insert('1.0', args.text)
        root.update()
        t0 = time.time()
        # 🔴🔴 §62：**点击前**抓基线快照 ⇒ 后面用**相对增量**判「本句播完」
        #   （`n_played` 是累计计数 ⇒ 常量阈值 `>= 1` 会把「历史上播过的别的句」
        #    当成本句证据 ⇒ 假通过）。
        svc_pre = getattr(gui, 'tts', None)
        if svc_pre is not None:
            played_before, tel_id_before = played_snapshot(svc_pre.stats())
        else:
            played_before, tel_id_before = 0, None
        dlg._start()
        print('>>> 已点「开始朗读」', flush=True)
        # ⚠️ 若点击前 service 还不存在（`_start()` 里才 `_ensure_svc()` 创建）
        #   ⇒ 点击**后**立刻补基线（`_start()` 是同步提交、播放在**后台线程**）
        #   ⇒ 这个时刻本句**还没播完** ⇒ 基线仍然有效。
        if svc_pre is None:
            svc_now = getattr(gui, 'tts', None)
            if svc_now is not None:
                played_before, tel_id_before = played_snapshot(svc_now.stats())

        # ③ 等真的播出一句
        played = False
        while time.time() - t0 < args.seconds:
            root.update()
            svc = gui.tts
            if svc is not None:
                st = svc.stats()
                # 🔴🔴 2026-10-27 §62 修：**不再**用 `n_played >= 1` 当「已出声」判据
                #   （APP-021⑦ 的同族缺陷）⇒ 必须等**本句**的遥测齐了再停
                #   （**相对增量** ⇒ 不会把「别的句 / 测试音」的遥测当本句）。
                done, why = sentence_played(st, played_before, tel_id_before)
                if done:
                    played = True
                    print('>>> 本句已播完（%s）' % why, flush=True)
                    break
                if st.get('state') == 'error':
                    print('🔴 TTS state=error：%r' % st.get('last_error'))
                    break
            time.sleep(0.2)

        st = gui.tts.stats() if gui.tts is not None else {}
        print('-' * 78)
        print('state=%s played=%s dropped=%s submitted=%s'
              % (st.get('state'), st.get('n_played'), st.get('n_dropped'),
                 st.get('n_submitted')))
        note = dlg.var_note.get() if hasattr(dlg, 'var_note') else ''
        print('对话框提示 = %r' % note)

        # ④ 截屏
        try:
            from PIL import ImageGrab
            shot = os.path.join(OUT_DIR, 'app075_gui_offline_read.png')
            root.update()
            ImageGrab.grab().save(shot)
            print('截图 = %s' % shot)
            lines.append('截图: %s' % shot)
        except Exception as e:
            print('⚠️ 截图失败：%r' % (e,))

        checks = [
            ('① 对话框能打开', True),
            ('② 本句链路级真的出声（read_delta ≥ n_samples 且 peak > 1e-2）',
             evaluate_audible(st.get('last_telemetry'))[0]),
            ('③ 没有「worker 退出」', 'worker 退出' not in note),
            ('④ 没有 worker 级故障原因', not st.get('last_error')),
        ]
        print('-' * 78)
        allok = True
        for name, cond in checks:
            print('%s %s' % ('PASS' if cond else 'FAIL', name))
            allok = allok and cond
        verdict = 'OK GUI 路径通过' if allok else 'FAIL'
        print('判定：%s' % verdict)
        lines.append('[app075] 判定：%s' % verdict)
    except Exception as e:
        import traceback
        traceback.print_exc()
        verdict = 'FAIL（异常）: %r' % (e,)
        lines.append('[app075] %s' % verdict)
    finally:
        try:
            if gui is not None and getattr(gui, 'tts', None) is not None:
                gui.tts.close()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'app', 'app075_gui_offline_read_real.txt')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# app075 真实 GUI 点击路径  %s\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
        f.write('# pkg=%s\n' % pkg)
        f.write('# parent preferred encoding = %s\n'
                % locale.getpreferredencoding(False))
        f.write('\n'.join(lines) + '\n')
        f.write('判定: %s\n' % verdict)
    print('\n日志已写 %s' % out)
    return 0 if verdict.startswith('OK') else 1


if __name__ == '__main__':
    sys.exit(main())
