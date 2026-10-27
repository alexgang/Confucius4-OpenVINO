"""app077 — APP-021 验收 A + B：**真实** CUDA + **真实**声卡 + 真实遥测。

APP-021（2026-10-26 15:25）要求：

- **验收 A**（不需要人）：拿一段 30 字左右的中文，用 CUDA 走离线朗读链路，
  **落盘 wav**。贴出时长、峰值、RMS(dBFS)、NaN 个数。
  期望峰值 > 0.05、时长和文本基本对得上。wav 路径写进 STATUS。
- **验收 B**（不需要人）：贴出 `sd.query_devices()` 的全表、所选设备的
  index/hostapi/name，以及 440 Hz 测试时 `n_cb`/`n_read` 的增量
  （应 ≈ 24000×1 s）。

本脚本把这两条**一次跑完**，并额外给出：
  - 每句遥测（peak / rms_dbfs / nan / cb_delta / read_delta / underflow）
  - `n_read` 增量 ≥ 本句样本数 的判据（APP-021⑦ 改后的 app071 判据）
  - wav 的独立复核（不依赖 worker 的自报数字 ⇒ **自己再算一遍**）

## 🔴 判据边界（必须诚实）
本脚本能证明「**音频确实被播放回调取走了**、幅度是多少」，
但**不能证明「用户耳朵听到了」** ⇒ 人耳确认仍属验收 C。
⇒ 本脚本**不**输出「能出声」这类结论，只给**可核对的硬数字**。

## 跑法
    <PKG>\\python\\python.exe results\\app\\app077_tts_acceptance_ab.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# 🔴🔴 2026-10-27 §62：**「真的出声」的唯一判据来源**（APP-021⑦ 的直接执行）
#   ⚠️ 旧判据 `n_played >= 1` 是 APP-021 点名**作废**的弱判据
#   ⇒ 现在用 APP-021 明文指定的硬判据：**n_read 增量 ≥ 本句样本数** 且 **峰值 > 1e-2**。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_audible_criterion import (  # noqa: E402
    audible_verdict, describe_criterion, evaluate_audible,
    played_snapshot, sentence_played, sentence_failed)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HOME = r'C:\Users\Trekker-PTL'
TEXT = '这是一次离线朗读测试，用来确认语音输出是否正常。'


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
    ap.add_argument('--seconds', type=float, default=200.0)
    ap.add_argument('--text', default=TEXT)
    ap.add_argument('--dump-dir', default=None)
    args = ap.parse_args()

    pkg = discover_pkg()
    app_dir = os.path.join(pkg, 'app')
    sys.path.insert(0, app_dir)
    os.environ.setdefault('LIVECAP_PKG', pkg)
    # 🔴 复刻 `live_caption_app.py` L57-58（真实 App 启动必执行）
    os.environ.setdefault('PYTHONUTF8', '1')
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    dump_dir = args.dump_dir or os.path.join(
        os.environ.get('LOCALAPPDATA', HOME), 'Confucius4LiveCaption',
        'tts_dump_%s' % time.strftime('%Y%m%d_%H%M%S'))

    print('=' * 78)
    print('app077 · APP-021 验收 A/B（真实 CUDA + 真实声卡 + 真实遥测）')
    print('=' * 78)
    print('客户包 = %s' % pkg)
    print('落盘目录 = %s' % dump_dir)
    print('-' * 78, flush=True)

    import numpy as np
    import sounddevice as sd
    import tts_service

    # ── 验收 B 之一：sd.query_devices() 全表 ──────────────────────
    print('【验收 B】sd.query_devices() 全表：')
    devs = sd.query_devices()
    table = []
    for i, d in enumerate(devs):
        row = dict(i=i, name=d['name'], hostapi=d['hostapi'],
                   max_out=d['max_output_channels'],
                   default_samplerate=d['default_samplerate'])
        table.append(row)
        print('  [%d] %-46s hostapi=%d max_out=%d sr=%s'
              % (i, d['name'], d['hostapi'], d['max_output_channels'],
                 d['default_samplerate']))
    try:
        default_out = sd.default.device
    except Exception:
        default_out = None
    print('  默认输出设备 = %r' % (default_out,))

    import audio_source
    oid = audio_source.default_output_device_id()
    print('  soundcard 端点 id = %s' % oid)

    # 解析成 sounddevice 的 index（复刻 tts_worker.resolve_out_device 的口径）
    ns_tw = {}
    tw_path = os.path.join(app_dir, 'tts_worker.py')
    with open(tw_path, encoding='utf-8') as f:
        tw_src = f.read()
    # 不 exec 整个 worker（会拉重依赖）⇒ 只取 resolve_out_device 需要的逻辑：
    # 直接调它（包内 app 已在 sys.path）
    import tts_worker
    sd_dev, how = tts_worker.resolve_out_device(oid)
    print('  解析结果：sd_device=%r 方式=%s' % (sd_dev, how))
    if sd_dev is not None:
        d = devs[sd_dev]
        print('  所选设备 index=%s hostapi=%s name=%s'
              % (sd_dev, d['hostapi'], d['name']))
    else:
        print('  所选设备 =（系统默认）')

    t0 = time.time()
    lines = []

    def on_log(m):
        s = '%7.2fs %s' % (time.time() - t0, m)
        print(s, flush=True)
        lines.append(s)

    svc = None
    results = {}
    try:
        svc = tts_service.TTSService(
            device=args.device, voice=args.voice, out_device=oid,
            precision=args.precision, on_log=on_log, dump_dir=dump_dir)

        # ── 等 ready ───────────────────────────────────────────────
        t_end = time.time() + args.seconds
        while time.time() < t_end:
            st = svc.stats()
            if st.get('state') in ('error', 'ready'):
                break
            time.sleep(0.3)
        st = svc.stats()
        print('%7.2fs >>> state=%s' % (time.time() - t0, st.get('state')))
        if st.get('state') == 'error':
            print('🔴 worker 级故障：%r' % st.get('last_error'))
            results['state'] = 'error'
            results['last_error'] = st.get('last_error')
        else:
            # ── 验收 B 之二：440 Hz 测试声音 ────────────────────────
            print('%7.2fs >>> 发「测试声音」指令（1 s 440 Hz）'
                  % (time.time() - t0))
            svc.test_tone()
            tone = None
            t_tone_end = time.time() + 30
            while time.time() < t_tone_end:
                tel = svc.stats().get('last_telemetry') or {}
                if tel.get('read_delta') is not None and \
                        tel.get('out_desc') and tel.get('n_cb', 0) > 0:
                    tone = tel
                    if tel.get('read_delta', 0) > 0:
                        break
                time.sleep(0.2)
            print('%7.2fs >>> 测试声音遥测：%r' % (time.time() - t0, tone))
            results['test_tone'] = tone

            # ── 验收 A：真实合成一句 + 落盘 wav ────────────────────
            print('%7.2fs >>> 提交一句（%d 字）' % (time.time() - t0,
                                              len(args.text)))
            # 🔴🔴 §62：**提交前**抓基线快照 ⇒ 后面用**相对增量**判「本句播完」
            #   ⚠️ 本脚本**先发过「🔊 测试声音」**⇒ `last_telemetry` 已被
            #      **测试音**覆盖 ⇒ 若只看 `last_telemetry` 会把**测试音的遥测**
            #      当成本句的证据 ⇒ **假通过** ⇒ 必须用相对增量 + id 校验。
            played_before, tel_id_before = played_snapshot(svc.stats())
            failed_before = int(svc.stats().get('n_failed') or 0)
            svc.submit(args.text, seg=0)
            t_play_end = time.time() + 120
            while time.time() < t_play_end:
                st = svc.stats()
                done, why = sentence_played(st, played_before, tel_id_before)
                if done:
                    print('%7.2fs >>> 本句已播完（%s）'
                          % (time.time() - t0, why))
                    break
                if sentence_failed(st, failed_before):
                    print('%7.2fs >>> 本句失败' % (time.time() - t0))
                    break
                if st.get('state') == 'error':
                    break
                time.sleep(0.3)
            st = svc.stats()
            print('%7.2fs >>> state=%s played=%s dropped=%s failed=%s'
                  % (time.time() - t0, st.get('state'), st.get('n_played'),
                     st.get('n_dropped'), st.get('n_failed')))
            print('           last_telemetry = %r'
                  % st.get('last_telemetry'))
            print('           last_sentence_error = %r'
                  % st.get('last_sentence_error'))
            results['state'] = st.get('state')
            results['n_played'] = st.get('n_played')
            results['n_failed'] = st.get('n_failed')
            results['last_telemetry'] = st.get('last_telemetry')
            results['last_sentence_error'] = st.get('last_sentence_error')

        # ── 验收 A：复核 wav（**自己再算一遍**）────────────────────
        wavs = []
        if os.path.isdir(dump_dir):
            for fn in sorted(os.listdir(dump_dir)):
                if fn.lower().endswith('.wav'):
                    wavs.append(os.path.join(dump_dir, fn))
        print('-' * 78)
        print('【验收 A】落盘 wav：%d 个' % len(wavs))
        wav_report = []
        for p in wavs:
            try:
                import soundfile as sf
                data, sr = sf.read(p, always_2d=False)
                a = np.asarray(data, dtype=np.float64).reshape(-1)
                peak = float(np.max(np.abs(a))) if a.size else 0.0
                rms = float(np.sqrt(np.mean(a ** 2))) if a.size else 0.0
                rms_db = (20.0 * np.log10(rms)) if rms > 0 else -99.0
                n_nan = int(np.count_nonzero(np.isnan(a)))
                n_inf = int(np.count_nonzero(np.isinf(a)))
                rec = dict(path=p, sr=int(sr), dur_s=round(a.size / sr, 3),
                           n_samples=int(a.size), peak=round(peak, 6),
                           rms=round(rms, 6), rms_dbfs=round(rms_db, 2),
                           n_nan=n_nan, n_inf=n_inf)
            except Exception as e:
                rec = dict(path=p, error='%s: %s' % (type(e).__name__, e))
            wav_report.append(rec)
            print('  %s' % json.dumps(rec, ensure_ascii=False))
        results['wavs'] = wav_report

        # ── 判据 ──────────────────────────────────────────────────
        tel = results.get('last_telemetry') or {}
        tone = results.get('test_tone') or {}
        checks = [
            ('A1 worker 成功 ready', results.get('state') in ('ready', 'idle')),
            ('A2 本句链路级真的出声（read_delta ≥ n_samples 且 peak > 1e-2）',
             evaluate_audible(results.get('last_telemetry'))[0]),
            ('A3 有句子级失败', not (results.get('n_failed') or 0)),
            ('A4 遥测里 n_read 增量 ≥ 本句样本数（音频真被取走）',
             (tel.get('read_delta') or 0) >= (tel.get('n_samples') or 1)),
            ('A5 本句峰值 > 1e-2（不是静音合成）',
             (tel.get('peak') or 0.0) > 1e-2),
            ('A6 本句没有 NaN/Inf',
             (tel.get('n_nan_inf') or 0) == 0),
            ('A7 wav 已落盘', len(wav_report) > 0),
            ('A8 wav 峰值 > 0.05', any(
                (w.get('peak') or 0) > 0.05 for w in wav_report)),
            ('A9 wav 时长与文本基本相符（0.5–15 s）', any(
                0.5 <= (w.get('dur_s') or 0) <= 15.0 for w in wav_report)),
            ('B1 测试声音有遥测（out_desc / n_cb / n_read）',
             bool(tone.get('out_desc')) and
             (tone.get('cb_delta') or 0) > 0),
            ('B2 测试声音 n_read 增量 ≈ 24000×1 s（±2400）',
             abs((tone.get('read_delta') or 0) - 24000) <= 2400),
        ]
        print('-' * 78)
        allok = True
        for name, cond in checks:
            print('%s %s' % ('PASS' if cond else 'FAIL', name))
            allok = allok and bool(cond)
        verdict = 'OK' if allok else 'FAIL'
        print('判定：%s' % verdict)
        results['verdict'] = verdict
        results['checks'] = [{'name': n, 'ok': bool(c)} for n, c in checks]
    except Exception as e:
        import traceback
        traceback.print_exc()
        results['verdict'] = 'FAIL（异常）: %r' % (e,)
    finally:
        if svc is not None:
            try:
                svc.close()
            except Exception:
                pass

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'app077_tts_acceptance_ab.txt')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# app077 APP-021 验收 A/B  %s\n'
                % time.strftime('%Y-%m-%d %H:%M:%S'))
        f.write('# pkg=%s device=%s precision=%s\n'
                % (pkg, args.device, args.precision))
        f.write('# dump_dir=%s\n' % dump_dir)
        f.write('# 设备全表：\n')
        for r in table:
            f.write('  %s\n' % json.dumps(r, ensure_ascii=False))
        f.write('\n--- 运行日志 ---\n')
        f.write('\n'.join(lines) + '\n')
        f.write('\n--- 结构化结果 ---\n')
        f.write(json.dumps(results, ensure_ascii=False, indent=2))
    with open(out.replace('.txt', '.json'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write(json.dumps(dict(table=table, **results),
                        ensure_ascii=False, indent=2))
    print('\n证据已写 %s' % out)
    return 0 if results.get('verdict') == 'OK' else 1


if __name__ == '__main__':
    sys.exit(main())
