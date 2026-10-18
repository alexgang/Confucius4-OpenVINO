"""c081a_luid_probe.py — C-081#1：确认 iGPU / NPU 各自的 DEVICE_LUID。

C-081 的核心质疑：`\\GPU Engine(*)` 计数器按 LUID 分实例，NPU 在 WDDM 里
也注册成一个计算适配器、占一个 Compute 引擎。c080i 的正则
`pid_(\\d+)_.*?engtype_(\\w+)` **完全丢弃了 luid 段**，于是 NPU 的占用被
并进了「GPU compute」。本脚本先把 LUID 对应关系钉死。

输出：reports/c081a_luid_map.json
"""
import json
import os
import re
import subprocess
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUT = 'reports/c081a_luid_map.json'


def run_ps(ps, timeout=90):
    try:
        p = subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps],
                           capture_output=True, timeout=timeout)
    except Exception as e:
        return None, repr(e)
    return (p.stdout or b'').decode('utf-8', errors='replace'), None


def ov_luid(device):
    """用 openvino.Core 读 DEVICE_LUID。"""
    import openvino as ov
    core = ov.Core()
    if not core.get_available_devices.__self__ or True:
        devs = core.available_devices
    else:                                    # pragma: no cover
        devs = []
    if device not in devs:
        return {'error': 'device not available', 'available': devs}
    out = {'available': devs}
    for prop in ('DEVICE_LUID', 'DEVICE_NAME', 'DEVICE_TYPE',
                 'GLOBAL_LUID', 'THROUGHPUT', 'FULL_DEVICE_NAME'):
        try:
            out[prop] = core.get_property(device, prop)
        except Exception as e:
            out[prop] = 'ERR: %s' % type(e).__name__
    return out


def wmi_video():
    ps = ("Get-CimInstance Win32_VideoController | ForEach-Object { "
          "'{0}|{1}|{2}|{3}' -f $_.Name, $_.PNPDeviceID, "
          "$_.AdapterCompatibility, $_.VideoProcessor }")
    txt, err = run_ps(ps)
    if err:
        return {'error': err}
    rows = []
    for line in txt.splitlines():
        p = [x.strip() for x in line.split('|')]
        if len(p) >= 2 and p[0]:
            rows.append({'name': p[0], 'pnp_device_id': p[1],
                         'compat': p[2] if len(p) > 2 else '',
                         'video_processor': p[3] if len(p) > 3 else ''})
    return {'controllers': rows}


def live_instances():
    """列出当前**所有** GPU Engine 实例（含 luid/engtype/pid），哪怕占用为 0。

    用 -ErrorAction 兜底：Get-Counter 在没有实例时会报错。
    """
    ps = ("$ErrorActionPreference='SilentlyContinue';"
          "$s=(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' "
          "-SampleInterval 1 -MaxSamples 1).CounterSamples;"
          "$s|ForEach-Object{"
          "if($_.InstanceName -match "
          "'luid_([0-9A-Fa-fx]+)_(\\d+)_(\\d+)_engtype_([\\w\\-]+)_pid_(\\d+)'){"
          "'{0}|{1}|{2}|{3}|{4}|{5}' -f $Matches[1],$Matches[2],$Matches[3],"
          "$Matches[4],$Matches[5],$_.CookedValue}"
          "elseif($_.InstanceName){'UNPARSED|'+$_.InstanceName}}")
    txt, err = run_ps(ps)
    if err:
        return {'error': err}
    seen = {}
    unparsed = []
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        p = line.split('|')
        if p[0] == 'UNPARSED':
            unparsed.append(p[1])
            continue
        if len(p) == 6:
            luid, dev, eng, pid, util = p[0], p[2], p[3], int(p[4]), float(p[5])
            k = (luid, eng)
            rec = seen.setdefault(k, {'luid': luid, 'engtype': eng, 'pids': set(),
                                      'util_max': 0.0})
            rec['pids'].add(pid)
            rec['util_max'] = max(rec['util_max'], util)
    out = []
    for (luid, eng), rec in sorted(seen.items()):
        out.append({'luid': luid, 'engtype': eng,
                    'util_max': round(rec['util_max'], 2),
                    'n_pids': len(rec['pids'])})
    return {'by_luid_engtype': out, 'unparsed': unparsed[:20],
            'n_unparsed': len(unparsed)}


def main():
    rep = {'note': 'C-081#1 iGPU / NPU 的 DEVICE_LUID 对照'}
    log = lambda *a: print(*a, flush=True)

    log('[c081a] openvino Core:')
    for dev in ('GPU', 'GPU.0', 'NPU'):
        r = ov_luid(dev)
        rep.setdefault('ov', {})[dev] = r
        log('  %-7s -> %s' % (dev, r.get('DEVICE_LUID')))

    log('[c081a] Win32_VideoController:')
    rep['wmi_video'] = wmi_video()
    for c in rep['wmi_video'].get('controllers', []):
        log('  %s | %s' % (c['name'], c['pnp_device_id']))

    log('[c081a] live GPU Engine 实例:')
    rep['live'] = live_instances()
    for r in rep['live'].get('by_luid_engtype', []):
        log('  luid=%s engtype=%s util_max=%.1f n_pids=%d'
            % (r['luid'], r['engtype'], r['util_max'], r['n_pids']))

    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
