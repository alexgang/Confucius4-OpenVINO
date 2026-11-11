#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app286_rc3_unzip_smoke.py —— APP-073(a) / APP-074(a)：**解压副本冒烟**。

## 做什么

reviewer 的两条纠偏（APP-073 / APP-074）都要求**在 zip 的解压副本上**
再跑一遍冒烟，而不是在「未剪的 rc3 目录」上：

> (a) 把 zip 解压到全新目录（非 shared），在该副本跑：`--check`，
>     加 CLI 60 s（用任何自备 wav，`--tts on --tts-voice A --tts-device NPU
>     --speaker off`），先拿 MACHINE_LOCK；落盘 tts.jsonl 的 wav 非零段数、
>     log 无 Traceback。

本脚本做**恰好这些事**，不多做：

1. `--check`（不占设备，几秒）⇒ rc / 「环境正常」/ GPU.0 / NPU / ASR 后端数。
2. CLI 60 s：`--tts on --tts-voice A --tts-device NPU --speaker off`
   ⇒ 落盘 `tts.jsonl`（逐句遥测）、`perf_run.log`、配音 wav。
3. **判据**（reviewer 原话 ⇒ 逐字落实）：
   * **wav 非零段数 > 0**（`tts.jsonl` 逐句 `wav_rms_db`/`wav_peak` 达标
     ⇒ 真的出声了，不是空跑）。
   * **log 无 `Traceback`**。
   * **音色 A 未回落**：`tts.jsonl` 的 `voice_kind` 全为 `preset`
     （若回落成别的音色 ⇒ 说明 `--tts-voice A` 在剪后的包里失效）。
4. **反证**：同一判据跑 rc2 的旧产物（`app253_minimvp_out/`）
   ⇒ 必须 FAIL（证明判据非恒真）。

## 🔴 设备纪律

* 本脚本**自己**取机器锁（`machine_lock_app`）⇒ 与别的模块互斥。
* 跑的是 **NPU TTS + GPU.0 ASR/MT** ⇒ **占设备** ⇒ 必须持锁。
* 取到锁后**再等一道安静窗口**（CPU 增量分类器）⇒ 别在别人在算时开跑。

## 用法

```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe \
    results/app/_app286_rc3_unzip_smoke.py --run
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

# 🔴🔴 **复用既有内容判据**（app268，APP-068/069①(c) 的 4 条硬判据）
#   ⇒ 不在本脚本里另立一套标准（避免判据漂移）。
#   ⚠️ app268 顶层 import numpy ⇒ 本脚本**必须**用仓库 `.venv` 跑。
import app268_app069_content_criterion as CRIT  # noqa: E402

DEFAULT_PKG = os.path.join(HOME, 'rc3_smoke_20261105',
                           'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
#: 自备 wav（reviewer：「用任何自备 wav」）⇒ 用 SPE 音频的前 60 s
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
REPORT = os.path.join(HERE, 'app286_rc3_unzip_smoke_evidence.json')
LOG = os.path.join(HERE, 'app286_rc3_unzip_smoke.log')
CHECK_LOG = os.path.join(HERE, 'app286_rc3_unzip_check_output.txt')
WORK = os.path.join(HERE, 'app286_rc3_unzip_out')

RE_ENV_OK = re.compile(r'环境正常')
RE_ASR_BACKENDS = re.compile(r'ASR 可用后端\s*(\d+)')
RE_GPU = re.compile(r'GPU\.0')
RE_NPU = re.compile(r'\bNPU\b')
RE_TRACEBACK = re.compile(r'Traceback \(most recent call last\)')

#: 内容判据阈值（与 APP-068/069①(c) 的 app268 同口径 ⇒ 不引入第二套标准）
RMS_DB_MIN = -45.0
PEAK_MIN = 0.05


def sha256_file(path, chunk=4 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def file_info(path):
    if not os.path.isfile(path):
        return {'exists': False}
    return {'exists': True, 'bytes': os.path.getsize(path),
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(os.path.getmtime(path))),
            'sha256': sha256_file(path)}


def read_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def judge_tts(rows):
    """逐句判定「这段 wav 是不是真的有声音」。

    🔴 与 app268 同口径（rms_db > -45 且 peak > 0.05）。
    """
    ok_rows = [r for r in rows if not r.get('dropped')]
    bad = []
    for r in ok_rows:
        pk = r.get('wav_peak', r.get('peak'))
        rdb = r.get('wav_rms_db')
        if rdb is None:
            rms = r.get('rms')
            rdb = (20.0 * math.log10(rms)) if rms else None
        if (pk is None or pk <= PEAK_MIN or rdb is None or rdb <= RMS_DB_MIN):
            bad.append(r.get('id'))
    kinds = sorted({r.get('voice_kind') for r in ok_rows})
    return {
        'n_rows': len(rows),
        'n_ok': len(ok_rows),
        'n_dropped': len(rows) - len(ok_rows),
        'n_nonzero_wav': len(ok_rows) - len(bad),
        'n_zero_wav': len(bad),
        'zero_wav_ids': bad[:40],
        'voice_kinds': [k for k in kinds if k is not None],
        'rms_db_min': RMS_DB_MIN,
        'peak_min': PEAK_MIN,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--wav', default=SPE)
    ap.add_argument('--duration', type=float, default=60.0)
    ap.add_argument('--out', default=REPORT)
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    out = {'script': '_app286_rc3_unzip_smoke.py',
           'correction': 'APP-073(a) + APP-074(a)（解压副本冒烟）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': a.pkg, 'wav': a.wav, 'duration': a.duration,
           'harness_pid': os.getpid()}

    # 🔴 落 PID 文件 ⇒ 后台跑时可用 `session_lease.py addpid` 登记
    #   （新会话据此判 BUSY ⇒ 不会重复启动同一个作业）
    try:
        pidfile = os.path.join(HERE, 'app286_rc3_unzip_smoke.pid')
        with open(pidfile, 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))
        out['pidfile'] = pidfile
    except Exception as e:
        out['pidfile_error'] = repr(e)

    if not os.path.isdir(a.pkg):
        raise SystemExit('解压副本不存在：%s' % a.pkg)
    if not os.path.isfile(a.wav):
        raise SystemExit('自备 wav 不存在：%s' % a.wav)

    os.makedirs(WORK, exist_ok=True)
    py = os.path.join(a.pkg, 'python', 'python.exe')
    app = os.path.join(a.pkg, 'app', 'live_caption_app.py')
    tts_wav = os.path.join(WORK, 'perf_tts.wav')
    tts_jsonl = os.path.join(WORK, 'perf_tts.jsonl')
    out_txt = os.path.join(WORK, 'perf_transcript.txt')
    spk_jsonl = os.path.join(WORK, 'perf_spk_seg.jsonl')

    # ── 闸门①：解压副本里**确实没有** babelvox 示例音色（APP-074 的前提）──
    speakers_dir = os.path.join(
        a.pkg, 'python', 'Lib', 'site-packages', 'babelvox', 'data', 'speakers')
    speaker_files = []
    if os.path.isdir(speakers_dir):
        for fn in sorted(os.listdir(speakers_dir)):
            speaker_files.append(fn)
    out['babelvox_speakers_dir_exists'] = os.path.isdir(speakers_dir)
    out['babelvox_speaker_files'] = speaker_files
    # 预设音色 A 的参考 wav 必须在（这才是 `--tts-voice A` 真正吃的东西）
    out['preset_A'] = file_info(os.path.join(
        a.pkg, 'models', 'qwen3tts', 'voices', 'preset_A.wav'))

    # ── 闸门②：`--check`（不占设备）────────────────────────────────
    # 🔴 APP-099 四.5：「编码测试在清空 `PYTHON*` 的进程里做」。
    #   旧实现只 pop 了 PYTHONPATH/PYTHONHOME ⇒ PYTHONIOENCODING、PYTHONUTF8
    #   仍会把编码「修好」，测不出包内入口 `sys.stdout.reconfigure` 是否生效。
    #   ⇒ 现在清空**所有** PYTHON* 前缀变量，并把清掉的键如实写进 json。
    _py_vars = sorted(k for k in os.environ if k.upper().startswith('PYTHON'))
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith('PYTHON')}
    env['LIVECAP_PKG'] = a.pkg
    out['encoding_clean_env'] = {
        'removed_keys': _py_vars,
        'n_removed': len(_py_vars),
        'criterion': 'APP-099 四.5：清空所有 PYTHON* 后，`--check` 的中文输出仍须可 utf-8 解码',
        'why': ('包内入口 live_caption_app.py 自带 sys.stdout.reconfigure('
                "encoding='utf-8', errors='replace')；bat 里的 "
                'PYTHONIOENCODING 只是第二道保险，不能靠它掩盖入口缺陷'),
    }
    check_cmd = [py, app, '--check']
    out['check_cmd'] = check_cmd
    t0 = time.time()
    cp = subprocess.run(check_cmd, env=env, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, timeout=1800)
    check_text = cp.stdout.decode('utf-8', errors='replace')
    check_wall = time.time() - t0
    with open(CHECK_LOG, 'w', encoding='utf-8', newline='\n') as f:
        f.write(check_text)
    m_asr = RE_ASR_BACKENDS.search(check_text)
    check_checks = [
        ('① `--check` 退出码为 0', cp.returncode == 0,
         {'rc': cp.returncode, 'wall_s': round(check_wall, 2)}),
        ('② 输出含「环境正常」', bool(RE_ENV_OK.search(check_text)),
         {'matched': bool(RE_ENV_OK.search(check_text))}),
        ('③ 探测到 Intel 集显 GPU.0', bool(RE_GPU.search(check_text)),
         {'n_gpu0_hits': len(RE_GPU.findall(check_text))}),
        ('④ 探测到 NPU', bool(RE_NPU.search(check_text)),
         {'n_npu_hits': len(RE_NPU.findall(check_text))}),
        ('⑤ 报出 ASR 可用后端数', bool(m_asr),
         {'n_asr_backends': (int(m_asr.group(1)) if m_asr else None)}),
    ]
    out['check'] = {
        'log': CHECK_LOG, 'log_bytes': os.path.getsize(CHECK_LOG),
        'log_sha256': sha256_file(CHECK_LOG),
        'checks': [{'name': n, 'verdict': ok, 'detail': d}
                   for n, ok, d in check_checks],
        'n_pass': sum(1 for _, ok, _ in check_checks if ok),
        'n_fail': sum(1 for _, ok, _ in check_checks if not ok),
    }
    for n, ok, d in check_checks:
        print('  [%s] %s  %s' % ('PASS' if ok else 'FAIL', n,
                                  json.dumps(d, ensure_ascii=False)))

    # ── CLI 60 s（占设备 ⇒ 持锁 + 安静窗口）──────────────────────
    cmd = [py, app, '--cli', '--file', a.wav,
           '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
           '--translate', 'zh', '--mt-device', 'GPU.0',
           '--mt-engine', 'gpu_int4cw',
           '--tts', 'on', '--tts-voice', 'A', '--tts-device', 'NPU',
           '--speaker', 'off',
           '--max-seconds', str(a.duration),
           '--tts-out', tts_wav,
           '--tts-jsonl', tts_jsonl,
           '--out', out_txt,
           '--spk-seg-jsonl', spk_jsonl]
    out['cli_cmd'] = cmd
    print('CLI 命令：\n  %s' % ' '.join(cmd))

    if a.dry_run or not a.run:
        print('（未加 --run ⇒ 不跑设备作业）')
        out['verdict'] = 'DRY_RUN'
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 0

    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未取得机器锁 ⇒ 退出')
        out['verdict'] = 'LOCK_BUSY'
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3
    out['lock_payload'] = payload
    try:
        # 取到锁**不等于**机器空闲 ⇒ 再等一道安静窗口
        # 🔴 `exclude_pids` 排掉**自己**（本 harness 持锁在等 ⇒ 不算干扰源）
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(
            quiet_seconds=45.0, timeout=900.0, poll=15.0, verbose=True,
            exclude_pids=(os.getpid(),))
        out['quiet_window'] = {'ok': ok_quiet, 'info': qinfo}
        print('[quiet] ok=%s waited_s=%.1f' % (
            ok_quiet, (qinfo or {}).get('waited_s', -1)))
        if not ok_quiet:
            out['verdict'] = 'NOT_QUIET'
            with open(a.out, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
            return 4

        # 锁还在吗？内容还是我这一份吗？
        # 🔴 `lock_intact` 返回 **(ok: bool, reason: str)** ⇒ 不是状态串
        ok_intact, reason = ml.lock_intact()
        out['lock_intact_before_run'] = {'ok': ok_intact, 'reason': reason}
        print('[lock] intact=%s（%s）' % (ok_intact, reason))
        if not ok_intact:
            out['verdict'] = 'LOCK_LOST'
            with open(a.out, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
            return 5

        t0 = time.perf_counter()
        with open(LOG, 'wb') as lf:
            proc = subprocess.Popen(cmd, env=env, stdout=lf,
                                    stderr=subprocess.STDOUT)
        out['cli_pid'] = proc.pid
        rc = proc.wait()
        wall = time.perf_counter() - t0
        out['cli_rc'] = rc
        out['cli_wall_s'] = round(wall, 2)
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % (e,))

    # ── 判据 ────────────────────────────────────────────────────────
    with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
        log_text = f.read()
    out['cli_log'] = file_info(LOG)
    out['cli_log_n_traceback'] = len(RE_TRACEBACK.findall(log_text))

    rows = read_jsonl(tts_jsonl)
    out['tts_jsonl'] = file_info(tts_jsonl)
    out['tts_wav'] = file_info(tts_wav)
    out['tts_out_txt'] = file_info(out_txt)
    out['spk_jsonl'] = file_info(spk_jsonl)
    judged = judge_tts(rows)
    out['tts_judge'] = judged
    print('[tts] %s' % json.dumps(judged, ensure_ascii=False))

    # 音色 A 确实没回落？
    voice_ok = bool(judged['voice_kinds']) and set(
        judged['voice_kinds']) <= {'preset'}
    out['voice_a_not_fallen_back'] = voice_ok

    checks = [
        ('① `--check` 5 条全过', out['check']['n_fail'] == 0,
         {'n_pass': out['check']['n_pass'],
          'n_fail': out['check']['n_fail']}),
        ('② CLI 退出码为 0', out['cli_rc'] == 0,
         {'rc': out['cli_rc'], 'wall_s': out['cli_wall_s']}),
        ('③ log 无 Traceback', out['cli_log_n_traceback'] == 0,
         {'n_traceback': out['cli_log_n_traceback']}),
        ('④ tts.jsonl 有出声段（非零段数 > 0）',
         judged['n_nonzero_wav'] > 0,
         {'n_nonzero_wav': judged['n_nonzero_wav'],
          'n_zero_wav': judged['n_zero_wav'],
          'n_ok': judged['n_ok']}),
        ('⑤ 音色 A 未回落（voice_kind ⊆ preset）', voice_ok,
         {'voice_kinds': judged['voice_kinds']}),
        ('⑥ 解压副本内无 babelvox 示例音色（剪后包真实状态）',
         out['babelvox_speakers_dir_exists'] is False,
         {'speakers_dir_exists': out['babelvox_speakers_dir_exists'],
          'n_files': len(speaker_files)}),
        ('⑦ 预设音色 A 参考 wav 存在', out['preset_A']['exists'],
         out['preset_A']),
    ]
    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_fail = len(checks) - n_pass
    out['checks'] = [{'name': n, 'verdict': ok, 'detail': d}
                     for n, ok, d in checks]
    out['n_pass'] = n_pass
    out['n_fail'] = n_fail

    # ── 🔴 内容判据（复用 app268 的 4 条硬判据，不另立标准）────────
    if os.path.isfile(tts_wav) and os.path.isfile(tts_jsonl):
        crit = CRIT.evaluate(tts_wav, tts_jsonl, 'rc3_unzip_smoke')
        out['content_criterion'] = {
            'verdict': crit.get('verdict'),
            'n_damaged_sentences': crit.get('n_damaged_sentences'),
            'C2_zero_runs_ge_0p3': crit.get('C2_zero_runs_ge_0p3'),
            'C1_ok': crit.get('C1_ok'),
            'C2_ok': crit.get('C2_ok'),
            'C3_ok': crit.get('C3_ok'),
            'C4_ok': crit.get('C4_ok'),
            'n_rows': crit.get('n_rows'),
            'wav_dur_s': crit.get('wav_dur_s'),
        }
        print('[内容判据] %s' % json.dumps(out['content_criterion'],
                                       ensure_ascii=False))
    else:
        out['content_criterion'] = {'skipped': True,
                                    'reason': 'wav 或 jsonl 未落盘'}

    # ── 🔴 反证：同一判据跑 rc2 旧产物 ⇒ 必须 FAIL（受损句 == 24）──
    rc2_dir = os.path.join(HERE, 'app253_minimvp_out')
    rc2_wav = os.path.join(rc2_dir, 'minimvp_tts.wav')
    rc2_jsonl = os.path.join(rc2_dir, 'minimvp.tts.jsonl')
    if os.path.isfile(rc2_wav) and os.path.isfile(rc2_jsonl):
        rc2 = CRIT.evaluate(rc2_wav, rc2_jsonl, 'rc2_old_counterproof')
        out['counter_proof'] = {
            'label': 'rc2_old_wav（同一判据 ⇒ 必须 FAIL）',
            'verdict': rc2.get('verdict'),
            'n_damaged_sentences': rc2.get('n_damaged_sentences'),
            'C2_zero_runs_ge_0p3': rc2.get('C2_zero_runs_ge_0p3'),
            'ok': (rc2.get('verdict') == 'FAIL'
                   and rc2.get('n_damaged_sentences') == 24),
        }
        print('[反证] rc2 旧产物：%s' %
              json.dumps(out['counter_proof'], ensure_ascii=False))
    else:
        out['counter_proof'] = {'label': 'rc2_old_wav', 'skipped': True,
                                'reason': 'rc2 旧产物不在本机（未做反证）'}

    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    out['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print()
    for n, ok, d in checks:
        print('  [%s] %s  %s' % ('PASS' if ok else 'FAIL', n,
                                  json.dumps(d, ensure_ascii=False)))
    print('\n结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[log] %s' % LOG)
    print('[evidence] %s' % a.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
