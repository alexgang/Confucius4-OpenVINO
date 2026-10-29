#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app142 — APP-041/042 在**客户包**内的复跑验收（包内代码必须同样通过）。

🔴 **为什么需要这一步**（本项目铁律）：
  仓库里通过 ≠ 包里通过 —— 仓库 ⇄ 客户包是**两份独立副本**
  ⇒ 定点同步可能漏块、可能换行不同、可能某个文件没同步到
  ⇒ 必须**在包内路径上**把同一套判据再跑一遍。

🔴 **本脚本只读**（不改包、不写包）。
🔴 **不 import 被测模块**（顶层 numpy ⇒ abort）⇒ 用 `ast` + `exec`。
🔴 **双向反证**：注入缺陷 ⇒ 对应判据必须 FAIL（判据不恒真）。
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = r'C:\Users\Trekker-PTL'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app142_app042_pkg_evidence.json')

RESULTS = []


def rec(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)[:600]})
    print(('PASS ' if ok else 'FAIL ') + name
          + ('  :: ' + str(detail)[:300] if detail else ''))
    return bool(ok)


def discover_pkg():
    import re
    cands = []
    for name in os.listdir(HOME):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        m = re.search(r'_v(\d+(?:\.\d+)+)', name)
        if not m:
            continue
        p = os.path.join(HOME, name)
        if os.path.isdir(p):
            cands.append((tuple(int(x) for x in m.group(1).split('.')), p))
    cands.sort()
    if not cands:
        raise SystemExit('找不到客户包目录')
    return cands[-1][1]


def norm(s):
    return s.replace('\r\n', '\n').replace('\r', '\n')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def read(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


def exec_ns(src, path, name):
    import types
    ns = {'__name__': name, '__file__': path}
    exec(compile(src, path, 'exec'), ns)
    mod = types.ModuleType(name)
    mod.__dict__.update(ns)
    return mod


# ── 基频估计 ─────────────────────────────────────────────────────────
def est_f0(x, sr, fmin=80.0, fmax=600.0):
    import numpy as np
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    if x.size < 512:
        return 0.0
    x = x - x.mean()
    if np.allclose(x, 0):
        return 0.0
    n = x.size
    m = 1
    while m < n:
        m *= 2
    f = np.fft.rfft(x, m)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    if ac[0] <= 0:
        return 0.0
    ac = ac / ac[0]
    lo = int(sr / fmax)
    hi = min(n - 1, int(sr / fmin))
    if hi <= lo:
        return 0.0
    k = int(np.argmax(ac[lo:hi])) + lo
    if 0 < k < n - 1:
        a0, a1, a2 = ac[k - 1], ac[k], ac[k + 1]
        d = a0 - 2 * a1 + a2
        delta = 0.5 * (a0 - a2) / d if d != 0 else 0.0
    else:
        delta = 0.0
    return sr / (k + delta)


def make_tone(sr=24000, dur=2.0, f0=200.0):
    import numpy as np
    t = np.arange(int(sr * dur)) / sr
    x = (0.5 * np.sin(2 * np.pi * f0 * t)
         + 0.3 * np.sin(2 * np.pi * 2 * f0 * t))
    return (x / np.max(np.abs(x))).astype('float32')


def main():
    pkg = discover_pkg()
    app_dir = os.path.join(pkg, 'app')
    print('=' * 72)
    print('app142 — APP-041/042 客户包内复跑验收')
    print('客户包：%s' % pkg)
    print('=' * 72)

    files = {
        'live_caption_app.py': os.path.join(app_dir, 'live_caption_app.py'),
        'tts_service.py': os.path.join(app_dir, 'tts_service.py'),
        'tts_worker.py': os.path.join(app_dir, 'tts_worker.py'),
        'time_stretch.py': os.path.join(app_dir, 'time_stretch.py'),
    }
    ok = True
    # P1：四个文件都在包内
    for name, p in files.items():
        ok &= rec('P1 包内存在 %s' % name, os.path.exists(p), p)

    # P2：包内代码与仓库**逐字一致**（归一化换行）
    for name, p in files.items():
        repo_p = os.path.join(REPO, 'live_caption', name)
        if not os.path.exists(repo_p):
            ok &= rec('P2 仓库存在 %s' % name, False, repo_p)
            continue
        same = norm(read(p)) == norm(read(repo_p))
        ok &= rec('P2 包内 %s 与仓库**逐字一致**（归一化换行）' % name, same,
                  'sha_pkg=%s sha_repo=%s'
                  % (sha256_file(p)[:16], sha256_file(repo_p)[:16]))

    # P3：包内 time_stretch 的 WSOLA 保音高（真跑）
    if os.path.exists(files['time_stretch.py']):
        ts = exec_ns(read(files['time_stretch.py']),
                     files['time_stretch.py'], 'ts_pkg')
        sr = 24000
        x = make_tone(sr=sr, dur=2.0, f0=200.0)
        f0_in = est_f0(x, sr)
        for sp in (1.10, 1.25, 1.30):
            st = ts.StreamWSOLA(speed=sp, sr=sr)
            outs = []
            for i in range(0, x.size, sr // 4):
                outs.append(st.process(x[i:i + sr // 4]))
            outs.append(st.flush())
            ys = [o for o in outs if len(o)]
            y = __import__('numpy').concatenate(ys) if ys else None
            if y is None:
                ok &= rec('P3 包内 WSOLA speed=%s 有输出' % sp, False, '空')
                continue
            ratio = y.size / float(x.size)
            f0_out = est_f0(y, sr)
            ok &= rec('P3 包内 WSOLA speed=%.2f 时长比 ≈ 1/%.2f'
                      % (sp, sp), abs(ratio - 1.0 / sp) < 0.04,
                      f'ratio={ratio:.4f}')
            ok &= rec('P3 包内 WSOLA speed=%.2f **音高不变**' % sp,
                      abs(f0_out - f0_in) / f0_in < 0.02,
                      f'f0 {f0_in:.2f}→{f0_out:.2f}')
        # speed=1.0 恒等
        st = ts.StreamWSOLA(speed=1.0, sr=sr)
        ok &= rec('P3 包内 speed=1.0 **逐位原样**',
                  __import__('numpy').array_equal(
                      __import__('numpy').asarray(st.process(x),
                                                 dtype='float32'), x),
                  '逐位一致')

    # P4：包内静态锚点（APP-041 启动 + APP-042 加速）
    app_src = read(files['live_caption_app.py'])
    svc_src = read(files['tts_service.py'])
    wrk_src = read(files['tts_worker.py'])
    ok &= rec('P4 包内 App 有 APP-041 启动机制',
              ('_maybe_startup_tts' in app_src)
              and ('_arm_startup_tts' in app_src)
              and ('_tts_startup_failed' in app_src), '三件套齐')
    ok &= rec('P4 包内 App 有 APP-042 目标时刻登记',
              ('_seg_target_wall' in app_src)
              and ('target_play_at=' in app_src), '登记 + 传递')
    ok &= rec('P4 包内 service 有 speed 下发',
              ("cmd['speed']" in svc_src) and ('speed_for_lag' in svc_src),
              '算 + 下发')
    ok &= rec('P4 包内 worker 有 StreamWSOLA',
              ('StreamWSOLA' in wrk_src) and ("msg.get('speed')" in wrk_src),
              '流式 WSOLA + 命令解析')
    ok &= rec('P4 包内 worker 遥测含 play_lag_s',
              "tel['play_lag_s']" in wrk_src, '遥测字段齐')

    # P5：反证（注入缺陷 ⇒ 判据必须 FAIL）
    ts_src = read(files['time_stretch.py'])
    mutated = ts_src.replace(
        "        if self.sp <= 1.0:\n"
        "            # 1.0× ⇒ **原样透传**（不缓冲、不变换 ⇒ 零风险）\n"
        "            return arr.copy()",
        "        # 反证：把流式 WSOLA 换成线性重采样（**会变调**）\n"
        "        import numpy as _np2\n"
        "        _idx = _np2.linspace(0, arr.size - 1,\n"
        "                             max(1, int(round(arr.size / self.sp))))\n"
        "        return _np2.interp(_idx, _np2.arange(arr.size), arr)"
        "        .astype('float32')\n"
        "        if self.sp <= 1.0:\n"
        "            return arr.copy()")
    if mutated != ts_src:
        import numpy as np
        ts2 = exec_ns(mutated, files['time_stretch.py'], 'ts_mut')
        sr = 24000
        x = make_tone(sr=sr, dur=2.0, f0=200.0)
        f0_in = est_f0(x, sr)
        st = ts2.StreamWSOLA(speed=1.25, sr=sr)
        outs = []
        for i in range(0, x.size, sr // 4):
            outs.append(st.process(x[i:i + sr // 4]))
        outs.append(st.flush())
        ys = [o for o in outs if len(o)]
        y = np.concatenate(ys) if ys else np.zeros(0, dtype=np.float32)
        f0_out = est_f0(y, sr)
        pitch_fail = (abs(f0_out - f0_in) / f0_in) >= 0.02
        ok &= rec('P5 反证：换成线性重采样 ⇒ **音高判据 FAIL**（判据不恒真）',
                  pitch_fail,
                  f'f0 {f0_in:.2f}→{f0_out:.2f} '
                  f'偏差={abs(f0_out-f0_in)/f0_in*100:.1f}%')
    else:
        ok &= rec('P5 反证：变异失败（源码形态与预期不符）', False,
                  '未匹配到目标代码块')

    # P6：反证（删掉包内 service 的 speed 下发 ⇒ 静态判据 FAIL）
    mutated_svc = svc_src.replace("cmd['speed'] = round(_sp, 4)",
                                   "# 反证：删掉 speed 下发")
    ok &= rec('P6 反证：删掉包内 cmd[speed] ⇒ P4 判据 **FAIL**（不恒真）',
              mutated_svc != svc_src
              and "cmd['speed']" not in mutated_svc,
              '静态判据被打掉')

    n_pass = sum(1 for r in RESULTS if r['ok'])
    n_fail = sum(1 for r in RESULTS if not r['ok'])
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    data = {
        'script': os.path.basename(__file__),
        'correction': 'APP-041/042',
        'pkg': pkg,
        'verdict': verdict,
        'n_pass': n_pass,
        'n_fail': n_fail,
        'n_total': len(RESULTS),
        'pkg_files': {n: {'bytes': os.path.getsize(p),
                          'mtime': os.path.getmtime(p),
                          'sha256': sha256_file(p)}
                      for n, p in files.items() if os.path.exists(p)},
        'results': RESULTS,
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('-' * 72)
    print(f'合计 {n_pass} PASS / {n_fail} FAIL  ⇒  verdict={verdict}')
    print('证据：' + OUT)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
