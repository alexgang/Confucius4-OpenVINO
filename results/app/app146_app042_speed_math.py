# -*- coding: utf-8 -*-
"""APP-042 速度公式 / 目标墙钟口径的**离线数学验证**（app146）。

**为什么要离线验**：真机实测要抢共享锁、耗 5 分钟；而「速度公式」与
「lag→speed 映射」是**纯函数** ⇒ 可以先用离线单测把数学口径钉死，
再等锁做真机确认。⇒ 两层证据互不替代。

**纪律**
- 🔴 验收脚本**不 import 被测模块的顶层**（顶层 numpy 会让 import 阶段 abort）
  ⇒ `time_stretch` 只依赖 numpy/wave ⇒ 本机有 numpy ⇒ 可直接 import；
  但 `live_caption_app` 顶层依赖太重 ⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间。
- 🔴 判据必须**不恒真** ⇒ 带反证组。

## 验证点

V1  `speed_for_lag(lag)` 在 lag ≤ 3 s 时 = 1.0（APP-042 原文）
V2  lag = 15 s 时 = 1.30（上限）
V3  lag > 15 s 时**截断**到 1.30（不越界）
V4  lag < 2 s 时回 1.0（**滞回**）
V5  线性段：lag = 7 s ⇒ 1.0 + (7-3)*0.025 = 1.10
V6  相邻句限幅：单次变化 ≤ 0.1×
V7  WSOLA 保音高：拉伸后**基频**不变（对比原音频）
V8  CLI 目标墙钟口径：`t0 + audio_s`；`audio_s` 增长 ⇒ 目标墙钟同比增长
"""
import ast
import json
import math
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
TS = os.path.join(REPO, 'live_caption', 'time_stretch.py')
APP = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
OUT = os.path.join(REPO, 'results', 'app',
                   'app146_app042_speed_math_evidence.json')


def load_ts():
    """用 `ast` 抽 `time_stretch` 的**纯函数部分** + `exec` 到独立命名空间。

    ⚠️ 顶层有 numpy 依赖 ⇒ 若本机无 numpy 则整个方案做不了
      ⇒ 先检测；若无 numpy ⇒ 明确报「做不了」，**不静默跳过**。
    """
    src = open(TS, encoding='utf-8').read()
    tree = ast.parse(src)
    keep = []
    for node in tree.body:
        # 🔴🔴 **必须保留 `Import`/`ImportFrom`** ——
        #   `time_stretch.py` 顶层有 `import numpy as np`
        #   ⇒ 只保留 def/class/assign ⇒ exec 后 `np` **未定义**
        #   ⇒ `time_stretch()` 内部 `np.xxx` ⇒ **NameError**
        #   ⇒ 判 V7 假 FAIL（**脚本自身缺陷**，不是产品缺陷）。
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import,
                             ast.ImportFrom)):
            keep.append(node)
        elif isinstance(node, ast.Assign):
            keep.append(node)
    mod = ast.Module(body=keep, type_ignores=[])
    ns = {'__name__': 'ts_isolated'}
    # 🔴 被测模块顶层 `import numpy as np` ⇒ exec 的命名空间必须能拿到 numpy
    #   ⇒ 提前 import 并塞进 ns（否则 exec 里 `import numpy as np` 虽能跑，
    #     但 `time_stretch` 内部引用的是模块级 np ⇒ 不会有问题；
    #     真正的问题是本脚本自己的 `np` 作用域 ⇒ 下面单独处理）。
    try:
        exec(compile(mod, TS, 'exec'), ns)
    except ImportError as e:
        return None, 'numpy 不可用：%s' % e
    return ns, None


try:
    import numpy as np
except ImportError:      # 🔴 无 numpy ⇒ 判 V7 失败并**明说**，不静默跳过
    np = None


def main():
    ns, err = load_ts()
    if ns is None:
        ev = {'script': 'app146_app042_speed_math', 'verdict': False,
              'fatal': err}
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        print('!! %s' % err)
        return 1

    sfl = ns['speed_for_lag']
    checks = []

    def ck(cid, name, ok, got, want):
        checks.append({'id': cid, 'name': name, 'pass': bool(ok),
                       'got': got, 'want': want})

    # V1 lag ≤ 3 s ⇒ 1.0
    v = [round(float(sfl(lag)), 6) for lag in (0.0, 1.0, 2.0, 3.0)]
    ck('V1', 'lag ≤ 3 s ⇒ speed = 1.0', all(abs(x - 1.0) < 1e-9 for x in v),
       v, '全 1.0')

    # V2 lag = 15 s ⇒ 1.30
    #   🔴 **判据口径修正（自踩坑）**：`speed_for_lag` 还受
    #     **「相邻句变化 ≤ 0.1×」** 的步长限制 ⇒ **单次调用**从 prev=1.0
    #     最多只能到 **1.1** ⇒ 直接断言「单次 = 1.30」是**判据写错**。
    #   ⇒ 正确口径：**逐句累积**（每句 prev = 上一句结果）⇒ 收敛到 1.30。
    def ramp(lag, steps, prev=1.0):
        p = prev
        for _ in range(steps):
            p = float(sfl(lag, prev_speed=p))
        return p
    v = round(ramp(15.0, 12), 6)
    ck('V2', 'lag = 15 s ⇒ 累积收敛到 1.30（单次受 0.1× 限幅）',
       abs(v - 1.30) < 1e-6, v, 1.30)

    # V3 lag > 15 s ⇒ 截断（同样走累积）
    v = [round(ramp(lag, 12), 6) for lag in (20.0, 60.0, 999.0)]
    ck('V3', 'lag > 15 s ⇒ 截断到 1.30', all(abs(x - 1.30) < 1e-6 for x in v),
       v, '全 1.30')

    # V4 滞回：降速需 lag < 2 s
    #    ⇒ 上一次 1.2 时，lag = 2.5 s 应**保持**（不降）；lag = 1.5 s 才回 1.0
    v_hold = round(float(sfl(2.5, prev_speed=1.2)), 6)
    v_drop = round(float(sfl(1.5, prev_speed=1.2)), 6)
    # ⚠️ 「降到 1.0」也受 0.1× 限幅 ⇒ 需**连续两句**才能真正回到 1.0
    v_drop2 = round(float(sfl(1.5, prev_speed=v_drop)), 6)
    ck('V4', '滞回：lag=2.5 保持 / lag=1.5 连两句回到 1.0',
       (v_hold > 1.0) and (abs(v_drop2 - 1.0) < 1e-9),
       {'lag2.5': v_hold, 'lag1.5_first': v_drop, 'lag1.5_second': v_drop2},
       'hold>1.0 且 两句后=1.0')

    # V5 线性段
    v = round(float(sfl(7.0)), 6)
    ck('V5', '线性段 lag=7 s ⇒ 1.10', abs(v - 1.10) < 1e-6, v, 1.10)

    # V6 相邻句限幅（step ≤ 0.1）
    #    ⇒ 从 prev=1.0 起、lag 极大（一次想跳到 1.3）⇒ 实际只允许 +0.1
    v = round(float(sfl(999.0, prev_speed=1.0)), 6)
    ck('V6', '相邻句单次变化 ≤ 0.1×', abs(v - 1.1) < 1e-6, v, 1.1)

    # V7 WSOLA 保音高
    v7 = None
    try:
        if np is None:
            raise ImportError('本解释器无 numpy ⇒ V7 客观做不了')
        sr = 24000
        t = np.arange(sr) / sr
        # 基频 220 Hz 的基音 + 几个谐波
        x = (0.6 * np.sin(2 * np.pi * 220 * t)
             + 0.25 * np.sin(2 * np.pi * 440 * t)
             + 0.15 * np.sin(2 * np.pi * 660 * t)).astype(np.float32)
        y = ns['time_stretch'](x, 1.2, sr)
        # 基频估计：自相关
        def f0(sig):
            sig = np.asarray(sig, dtype=np.float64)
            sig = sig - sig.mean()
            n = len(sig)
            # 粗搜 150~300 Hz
            lo, hi = int(sr / 300), int(sr / 150)
            best, bl = 0.0, 0
            for lag in range(lo, hi):
                c = float(np.dot(sig[:-lag], sig[lag:])) / (n - lag)
                if c > best:
                    best, bl = c, lag
            return sr / bl
        f_in, f_out = f0(x), f0(y)
        v7 = {'f_in': round(f_in, 2), 'f_out': round(f_out, 2),
              'ratio': round(f_out / f_in, 4),
              'in_len': int(len(x)), 'out_len': int(len(y))}
        ck('V7', 'WSOLA 拉伸后基频不变（变调检测）',
           abs(v7['ratio'] - 1.0) < 0.05 and len(y) < len(x),
           v7, 'ratio≈1.0 且变短')
    except Exception as e:
        ck('V7', 'WSOLA 拉伸后基频不变（变调检测）', False,
           'EXC %s' % e, 'ratio≈1.0')

    # V8 CLI 目标墙钟口径：t0 + audio_s
    app_src = open(APP, encoding='utf-8').read()
    ok8 = ('_cli_wall0 = time.time()' in app_src
           and 'return _cli_wall0 + a' in app_src
           and 'a = float(s.audio_s) if s is not None else 0.0' in app_src)
    ck('V8', 'CLI 目标墙钟口径 = t0 + audio_s', ok8,
       '源码含 _cli_wall0=time.time() / return _cli_wall0 + a / audio_s 取值',
       '三者齐备')

    # ── 反证组：判据不恒真 ──
    cf = []
    # 反证 1：把 speed_for_lag 的公式改成恒 1.0 ⇒ V2/V3/V5/V6 必须 FAIL
    def fake_sfl(lag, prev_speed=1.0):
        return 1.0
    def framp(f, lag, steps, prev=1.0):
        pp = prev
        for _ in range(steps):
            pp = float(f(lag, prev_speed=pp))
        return pp
    f2 = round(framp(fake_sfl, 15.0, 12), 6)
    f5 = round(float(fake_sfl(7.0)), 6)
    cf.append(('CF1', '公式恒 1.0 ⇒ V2/V5 应 FAIL',
               not (abs(f2 - 1.30) < 1e-6) and not (abs(f5 - 1.10) < 1e-6),
               {'v2_ramp': f2, 'v5': f5}, 'V2/V5 均 FAIL'))
    # 反证 2：去掉相邻句限幅 ⇒ V6 应 FAIL
    def fake_sfl2(lag, prev_speed=1.0):
        return max(1.0, min(1.30, 1.0 + (lag - 3.0) * 0.025))
    f6 = round(float(fake_sfl2(999.0, prev_speed=1.0)), 6)
    f6b = round(framp(fake_sfl2, 999.0, 12), 6)
    cf.append(('CF2', '去掉限幅 ⇒ V6 应 FAIL（单次即到 1.3）',
               (abs(f6 - 1.1) > 1e-6) and (abs(f6b - 1.30) < 1e-6),
               {'single': f6, 'ramp': f6b}, '单次≠1.1 且 累积=1.30'))
    # 反证 3：CLI 目标墙钟源码缺失 ⇒ V8 应 FAIL
    cf.append(('CF3', 'CLI 目标墙钟源码缺失 ⇒ V8 应 FAIL',
               not ('_cli_wall0 = time.time()' in app_src.replace(
                   '_cli_wall0 = time.time()', '')),
               '剥离后 V8 条件不成立', 'V8 FAIL'))

    # 🔴 **反证组语义**：`ok=True` 表示「**判据成功识破了这个假实现**」
    #   ⇒ 反证组的**期望是 ok=True**（假实现必须被抓住）
    #   ⇒ 「反证组有 FAIL」= 有假实现**没被抓住** ⇒ 判据不恒真 ⇒ 不可信。
    real_failed = [c['id'] for c in checks if not c['pass']]
    cf_notcaught = [cid for cid, _n, ok, _g, _w in cf if not ok]

    verdict = (not real_failed) and not cf_notcaught

    ev = {
        'script': 'app146_app042_speed_math',
        'checks': checks,
        'real_failed': real_failed,
        'counterfactual': [{'id': cid, 'name': n, 'pass': bool(ok),
                            'got': g, 'want': w} for cid, n, ok, g, w in cf],
        'counterfactual_not_caught': cf_notcaught,
        'verdict': verdict,
        'verdict_rule': 'REAL 组全 PASS 且 反证组的假实现**全部被识破**',
        'note': '离线数学验证；不替代真机实测',
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)

    for c in checks:
        print('  [%s] %s %s -- got=%s want=%s'
              % ('PASS' if c['pass'] else 'FAIL', c['id'], c['name'],
                 c['got'], c['want']))
    print('反证组：')
    for cid, n, ok, g, w in cf:
        print('  [{}] {} -- got={} want={}'.format(
            'PASS' if ok else 'FAIL', cid, n, g, w))
    print('（反证组 ok=True = 判据成功识破该假实现 ⇒ 期望全部 ok=True）')
    print('counterfactual_not_caught = %s （应为空）' % cf_notcaught)
    print('VERDICT: %s' % ('PASS' if verdict else 'FAIL'))
    return 0 if verdict else 1


if __name__ == '__main__':
    sys.exit(main())
