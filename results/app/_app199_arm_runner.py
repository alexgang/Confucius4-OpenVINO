#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app199_arm_runner.py —— 【APP-054 ③】A/B 单臂执行器（被 app199 调用）。

🔴 **用 `--speaker off|on` 切臂**（不是 stub 打桩）⇒
   ① 测的是**真实代码路径**（真开关）⇒ 更接近交付形态；
   ② reviewer 的基线臂是「stub 打桩」⇒ 本臂是**更严格**的对照
      （连「构造 bridge」都不做）。

用法：
    python _app199_arm_runner.py <arm> <shadow_app_dir> <wav> <out_txt>
"""
from __future__ import annotations

import os
import runpy
import sys
import time

arm = sys.argv[1]
app_dir = os.path.abspath(sys.argv[2])
wav = os.path.abspath(sys.argv[3])
out_txt = os.path.abspath(sys.argv[4])

sys.path.insert(0, app_dir)

out_cli = out_txt + '.cli.txt'
sys.argv = [
    'live_caption_app.py', '--cli', '--file', wav,
    '--engine', 'gpu_int8', '--translate', 'off', '--tts', 'off',
    '--asr-device', 'GPU.0', '--max-seconds', '300',
    '--speaker', arm,
    '--out', out_cli,
]

t0 = time.perf_counter()
try:
    with open(out_txt, 'w', encoding='utf-8', errors='replace') as log:
        _old_out, _old_err = sys.stdout, sys.stderr

        class _Tee:
            def __init__(self, *streams):
                self.streams = streams

            def write(self, s):
                for st in self.streams:
                    try:
                        st.write(s)
                    except Exception:
                        pass
                return len(s)

            def flush(self):
                for st in self.streams:
                    try:
                        st.flush()
                    except Exception:
                        pass

        sys.stdout = _Tee(log, _old_out)
        sys.stderr = _Tee(log, _old_err)
        try:
            runpy.run_path(os.path.join(app_dir, 'live_caption_app.py'),
                           run_name='__main__')
        finally:
            sys.stdout, sys.stderr = _old_out, _old_err
finally:
    wall = time.perf_counter() - t0
    with open(out_txt, 'a', encoding='utf-8', errors='replace') as log:
        log.write('\n[perfdiag] arm=%s wall=%.1fs\n' % (arm, wall))
    print('[perfdiag] arm=%s wall=%.1fs' % (arm, wall), flush=True)
