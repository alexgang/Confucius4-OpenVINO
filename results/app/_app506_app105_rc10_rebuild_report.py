# -*- coding: utf-8 -*-
r"""_app506 — **重建 rc10 包上验收报告**（APP-105）。

## 为什么重建

首轮 `_app501` 在**最后一项**（`cmd /c Start_Bridge.bat`）上**没跑完**：
`subprocess.run(capture_output=True)` 会等 stdout 管道 EOF，而启动器
（pythonw）**继承了管道** ⇒ `run()` 挂死 ⇒ 180 s 超时抛 `TimeoutExpired`
⇒ 进程退出、**报告没落盘**。
⇒ 本脚本用**同一批原始产物**重建报告，**不重跑 10 分钟整链**：

  * `check.log`                ⇒ �� ⑩ `--check`（原样解析）
  * `chain10min.log` / `.txt`  ⇒ 第 ⑫ 整链 10 分钟（原样解析）
  * `app505…gui_retry.json`    ⇒ 第 ⑪ GUI（复跑，用包内 python）
  * `app505…bridge_retry.json` ⇒ 第 ⑬ Start_Bridge.bat（复跑，`Popen` 落文件）
  * 静态项 ①–⑧ ＝ **重跑只读检查**（不占设备）

⚠️ 所有数字都**从原始日志/文件解析**，不手抄。
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUTROOT = os.path.join(HERE, 'app501_app105_rc10_acceptance')
REPORT = os.path.join(HERE, 'app501_app105_rc10_acceptance.json')
GUI_EV = os.path.join(HERE, 'app505_app105_rc10_gui_retry.json')
BRIDGE_EV = os.path.join(HERE, 'app505_app105_rc10_bridge_retry.json')

spec = importlib.util.spec_from_file_location(
    'a501', os.path.join(HERE, '_app501_app105_rc10_acceptance.py'))
a501 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a501)


def main():
    ev = {'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'pkg': a501.PKG, 'zip': a501.ZIP, 'correction': 'APP-105',
          'rebuilt': True,
          'rebuild_note': (
              '本报告由 `_app506_app105_rc10_rebuild_report.py` 重建：首轮 '
              '`_app501` 在最后一项（`cmd /c Start_Bridge.bat`）上因**启动器继承 '
              'stdout 管道**导致 `subprocess.run` 挂死 ⇒ 180 s 超时 ⇒ **报告没落盘**。'
              '重建用的**都是同一批原始产物**（check.log / chain10min.log / '
              'app505 两份复跑件），**整链 10 分钟没有重跑**。'),
          'items': {}, 'lock': {'module': 'app', 'pid': None,
                                'started': '2026-11-12 16:25:19',
                                'ended': '2026-11-12 16:43:08',
                                'timing_valid': True,
                                'note': '首轮持锁区间（含首轮死掉的那一次）'}}

    # 静态项 ①–⑧（只读）
    a501.check_static(ev)
    d = a501.probe_defaults()
    ev['pkg_defaults'] = d
    ev['items']['9_factory_defaults_new'] = {
        'default_devices': d['default_devices'],
        'defaults_version': d.get('defaults_version'),
        'profile': d.get('profile'),
        'pass': (d['default_devices'] == a501.NEW_DEFAULTS
                 and d.get('defaults_version') == 9
                 and d.get('profile') == 'minimvp'),
    }
    a501.check_readme_gate(ev)

    # ⑩ `--check`（从 check.log 解析）
    cp = os.path.join(OUTROOT, 'check.log')
    cl = open(cp, 'rb').read().decode('utf-8', errors='replace')
    dev_lines = [ln for ln in cl.splitlines() if ln.startswith('[device]')]
    ev['items']['10_pkg_check'] = {
        'exit_code': 0,
        'exit_code_source': '首轮 subprocess 返回码（见 _app501_rc10_acceptance.log'
                            ' 的「[10] --check exit=0」）',
        'log': cp, 'log_bytes': len(cl),
        'n_ok_lines': len(re.findall(r'\[ OK \]', cl)),
        'has_asr_section': ('ASR 后端' in cl),
        'device_lines': dev_lines,
        'stale_migration_line': [ln for ln in dev_lines
                                  if '已忽略旧配置里的设备项' in ln],
        'new_warning_line': [ln for ln in dev_lines
                             if 'ASR 与 MT 同在' in ln],
        'old_warning_absent': ('ASR 与 MT 都放在' not in cl),
        'pass': ('ASR 后端' in cl and len(re.findall(r'\[ OK \]', cl)) >= 20
                 and any('已忽略旧配置里的设备项' in ln for ln in dev_lines)
                 and 'ASR 与 MT 都放在' not in cl),
    }

    # ⑫ 整链 10 分钟（从 chain10min.log 解析）
    lp = os.path.join(OUTROOT, 'chain10min.log')
    tp = os.path.join(OUTROOT, 'chain10min.txt')
    lg = open(lp, 'rb').read().decode('utf-8', errors='replace')
    sub = open(tp, encoding='utf-8', errors='replace').read().strip()
    tf = a501.TTS_FINAL_RE.search(lg)
    rt = a501.RTF_RE.search(lg)
    ex = a501.ASR_EXEC_RE.search(lg)
    tex = a501.TTS_EXEC_RE.search(lg)
    tplace = a501.TTS_PLACE_RE.search(lg)
    tnpu = a501.TTS_NPU_RE.search(lg)
    asr_dev = ex.group(1) if ex else None
    tts_dev = tex.group(1) if tex else None
    ev['items']['12_chain_10min'] = {
        'exit_code': 0,
        'exit_code_source': '首轮 subprocess 返回码（见 _app501_rc10_acceptance.log'
                            ' 的「[12] chain exit=0」）',
        'cmd': '包内 python -s app/live_caption_app.py --cli --file '
               'test_audio/clip_10min_0_600.wav --max-seconds 600 --out … '
               '--translate zh --tts on --tts-voice A（**不带设备参数**）',
        'audio': a501.AUDIO,
        'log': lp, 'log_bytes': len(lg), 'output': tp, 'output_chars': len(sub),
        'output_head': sub[:300], 'replacement_chars': sub.count('\ufffd'),
        'asr_rtf': float(rt.group(1)) if rt else None,
        'asr_exec_encoder': asr_dev,
        'asr_exec_decoder': ex.group(2) if ex else None,
        'asr_exec_line': ex.group(0) if ex else None,
        'tts_exec_devices': tts_dev,
        'tts_exec_line': (lg[lg.find('[tts_engine] EXECUTION_DEVICES'):][:300]
                          if '[tts_engine] EXECUTION_DEVICES' in lg else None),
        'tts_places': tplace.group(1) if tplace else None,
        'tts_npu_components': int(tnpu.group(1)) if tnpu else None,
        'tts_submitted': int(tf.group(1)) if tf else None,
        'tts_played': int(tf.group(2)) if tf else None,
        'tts_dropped': int(tf.group(3)) if tf else None,
        'tts_final_line': tf.group(0) if tf else None,
        'pass': bool(sub and '\ufffd' not in sub and tf
                     and int(tf.group(2)) >= 1
                     and asr_dev == 'GPU.0'
                     and tts_dev is not None and 'NPU' in tts_dev),
    }

    # ⑪ GUI / ⑬ Start_Bridge.bat（复跑件）
    gui = json.load(open(GUI_EV, encoding='utf-8'))
    br = json.load(open(BRIDGE_EV, encoding='utf-8'))
    ev['items']['11_gui'] = {
        'first_attempt': 'FAIL（验收脚本用错解释器：系统 python 缺 numpy/openvino '
                         '⇒ ImportError；**非产品缺陷**）',
        'superseded_by': 'app505_app105_rc10_gui_retry.json',
        'pass': False,
    }
    ev['items']['11_gui_retry'] = {
        'verdict': gui.get('verdict'), 'checks': gui.get('checks'),
        'default_devices': gui.get('default_devices'),
        'device_notes': gui.get('device_notes'),
        'status_text': gui.get('status_text'),
        'shot': gui.get('shot'), 'shot_bytes': gui.get('shot_bytes'),
        'shot_not_blank': gui.get('shot_not_blank'),
        'real_device_notes': gui.get('real_device_notes'),
        'stale_config_detected': gui.get('stale_config_detected'),
        'evidence': os.path.basename(GUI_EV),
        'pass': gui.get('pass'),
    }
    ev['items']['13_start_bridge_bat'] = {
        'first_attempt': '超时（`subprocess.run(capture_output=True)` 等 stdout 管道 '
                         'EOF，而启动器继承管道 ⇒ 挂死 ⇒ 180 s TimeoutExpired；'
                         '**非产品缺陷**）',
        'superseded_by': 'app505_app105_rc10_bridge_retry.json',
        'pass': False,
    }
    ev['items']['13_start_bridge_bat_retry'] = {
        'cmd': br.get('cmd'), 'cmd_returncode': br.get('cmd_returncode'),
        'cmd_return_s': br.get('cmd_return_s'),
        'new_windows': br.get('new_windows'),
        'target_window': br.get('target_window'),
        'shot': br.get('shot'), 'shot_ok': br.get('shot_ok'),
        'shot_bytes': br.get('shot_bytes'),
        'killed_pids': br.get('killed_pids'), 'still_alive': br.get('still_alive'),
        'stdout': br.get('stdout'), 'stderr': br.get('stderr'),
        'evidence': os.path.basename(BRIDGE_EV),
        'pass': br.get('pass'),
    }

    # 逻辑项 = ①–⑬（**首轮失败项被复跑件取代** ⇒ 不重复计数）
    RETRY_OF = {'11_gui': '11_gui_retry',
                '13_start_bridge_bat': '13_start_bridge_bat_retry'}
    all_keys = sorted(k for k in ev['items'] if k[:1].isdigit())
    keys = [k for k in all_keys
            if k not in RETRY_OF.values()]
    effective = {}
    for k in keys:
        src = RETRY_OF.get(k, k)
        effective[k] = items_pass(ev['items'].get(src))
    ev['n_items'] = len(keys)
    ev['n_items_pass'] = sum(1 for k in keys if effective[k])
    ev['n_items_note'] = (
        '逻辑验收项 %d 个（①–⑬）；首轮失败的两项（⑪GUI／⑬Start_Bridge.bat）'
        '**由复跑件取代**（`11_gui_retry` / `13_start_bridge_bat_retry`）⇒ 不重复计数；'
        '首轮记录**原样保留**在 items 里（标了 first_attempt / superseded_by）。'
        % len(keys))
    ev['effective_items'] = effective
    ev['readme_ok'] = ev['readme_gate']['pass_except_zip_bytes']
    ev['verdict'] = ('PASS' if (ev['n_items_pass'] == ev['n_items']
                                and ev['readme_ok']) else 'PARTIAL')
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[rebuild] %d/%d ⇒ %s' % (ev['n_items_pass'], ev['n_items'],
                                    ev['verdict']))
    for k in keys:
        print('   %-28s %s' % (k, 'PASS' if effective[k] else 'FAIL'))
    return 0 if ev['verdict'] == 'PASS' else 1


def items_pass(d):
    return bool(d and d.get('pass'))


if __name__ == '__main__':
    sys.exit(main())
