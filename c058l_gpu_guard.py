"""c058l_gpu_guard.py — C-059 环境提醒：RTF 作业期间的 GPU 独占性监控

reviewer 提醒（C-059 末节）：
  「在你的 61 分钟 int4lmhead 作业运行期间看到目标机上出现了 rt-translator
    客户端（10:48 起），日志每 2 秒一行 wait_for_running: state=loading……
    它现在没占用 GPU，但服务一加载就会和你的测量抢 iGPU，**污染 RTF / P95
    （WER 不受影响）**。请：
    (1) 在每个要报告 RTF 的 61 分钟作业期间记录**非本作业**的 GPU 占用，
        写进该作业的结果文件；
    (2) 一旦出现其他进程的 compute/3d 占用明显升高，该次 RTF 作废并重跑；
    (3) **不要结束这个进程**（不是我们的），发现冲突就写进 STATUS 告诉用户。」

本脚本每秒采样一次 GPU 引擎占用，区分「本作业 PID」与「其它 PID」，
把其它进程的峰值写进 `reports/c058_gpu_guard_<tag>.json`。

**C-081#3 修正**：原来只按 PID 过滤、不看 LUID。NPU 在 WDDM 里也注册成
一个计算适配器并占 `engtype_compute` 实例组，所以「其它进程在 NPU 上的
占用」会被误判成「抢 iGPU」。现在按 LUID 分桶：NPU 占用单列
（`npu_other_peak_util_by_pid`），`rtf_valid` 只看 iGPU。这不影响历史
RTF 结论 —— 历次guard 跑出来的 `other_peak_util_by_pid` 全为空、
`n_conflict_samples_util_gt_5` 都是 0，即当时并没有其它进程在 NPU 上跑，
误判没有实际发生；但口径本身确实是错的，已修。

只读监控，不结束任何进程。
用法：
  .venv python c058l_gpu_guard.py <my_pid[,my_pid2,...]> <tag> [seconds] [cmd_pattern]

  `cmd_pattern` 是可选的命令行标记（不含 PID 时也能用）。子进程 PID 每轮都变的
  作业（例如 C-062#2 的 ABBA 交替运行，`c062r_abba_speed.py`）用它动态排除
  自己的子进程 —— 每 15 s 按 `Win32_Process.CommandLine` 重新收集一次，
  等价于传全量 PID 且不会漏。例：
    .venv python c058l_gpu_guard.py 0 c062_abba 7500 c062r_abba_speed.py
"""
import os
import sys
import json
import time
import subprocess

SEP = '|'

# c081a_luid_map.json 实测（core.get_property(device, 'DEVICE_LUID') 的低位 DWORD）
LUID_IGPU = '0x00012e84'      # Intel iGPU，对应 OpenVINO 'GPU.0'
LUID_NPU = '0x000144f0'       # Intel NPU，对应 OpenVINO 'NPU'



def sample_once():
    """用 Get-Counter 采样一次，返回 [(pid, luid, engtype, util), ...]

    C-081#3：原来这里用的是 `pid_(\\d+)_.*?engtype_(\\w+)`，**丢掉了 luid
    段**，只按 PID 过滤。但 `\\GPU Engine(*)` 的实例是按**适配器 LUID**
    分组的，NPU 在 WDDM 里也注册成一个计算适配器、独占一组
    `engtype_compute` 实例 —— 于是「其它进程在 NPU 上的占用」会被当成
    「其它进程在 GPU 上的争用」，产生假警报（RTF 被误判作废）。

    实例名实测格式：
        pid_11776_luid_0x00000000_0x00012e84_phys_0_eng_5_engtype_compute
    本机 LUID（c081a_luid_map.json 实测）：
        0x00000000_0x00012e84 = Intel iGPU (GPU.0)
        0x00000000_0x000144f0 = Intel NPU  (NPU)
    现在按 luid 分桶统计，NPU 单独成列，不计入 GPU 争用。
    """
    ps = (
        "$s=(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' "
        "-SampleInterval 1 -MaxSamples 1).CounterSamples;"
        "$s|Where-Object{$_.CookedValue -gt 0.5}|ForEach-Object{"
        "if($_.InstanceName -match "
        "'pid_(\\d+)_luid_(0x[0-9A-Fa-f]+)_(0x[0-9A-Fa-f]+)_.*?engtype_([A-Za-z0-9]+)'){"
        "'{pid}|{luid}|{eng}|{util}' -f $Matches[1],"
        "'{0}_{1}' -f $Matches[2],$Matches[3],$Matches[4],$_.CookedValue}"
        "elseif($_.InstanceName -match 'pid_(\\d+)_.*?engtype_([A-Za-z0-9]+)'){"
        # 兜底：没有 luid 段的实例归到 unknown，按 GPU 计（保持旧行为）
        "'{0}|unknown|{1}|{2}' -f $Matches[1],$Matches[2],$_.CookedValue}}"
    )
    try:
        out = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', ps],
            capture_output=True, timeout=30)
    except Exception:
        return []
    # PowerShell 输出走本地代码页（GBK），必须按 errors='replace' 解码
    text = (out.stdout or b'').decode('utf-8', errors='replace')
    res = []
    for line in text.splitlines():
        parts = line.strip().split(SEP)
        if len(parts) == 4:
            try:
                res.append((int(parts[0]), parts[1].lower(),
                            parts[2], float(parts[3])))
            except ValueError:
                pass
    return res


def classify_luid(luid):
    """把 luid 归到 'gpu' / 'npu' / 'other'。可在 argv 覆盖。"""
    l = luid.lower()
    if l.endswith(LUID_NPU):
        return 'npu'
    if l.endswith(LUID_IGPU):
        return 'gpu'
    if l == 'unknown':
        return 'gpu'
    return 'other'


def pids_matching(pattern):
    """返回命令行含 `pattern` 的进程 PID 集合。

    C-062#2 需要：交替运行的每轮都是**独立子进程**，PID 每次都变，
    手工传 PID 列表不现实。改为按命令行标记排除，效果等价且不会漏。
    """
    if not pattern:
        return set()
    ps = ("Get-CimInstance Win32_Process | "
          "Where-Object { $_.CommandLine -like '*{pattern}*' } | "
          "ForEach-Object { $_.ProcessId }")
    try:
        out = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', ps],
            capture_output=True, timeout=60)
    except Exception:
        return set()
    text = (out.stdout or b'').decode('utf-8', errors='replace')
    res = set()
    for line in text.splitlines():
        line = line.strip()
        if line.isdigit():
            res.add(int(line))
    return res


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    my_pids = {int(x) for x in sys.argv[1].split(',') if x.strip()}
    tag = sys.argv[2]
    seconds = int(sys.argv[3]) if len(sys.argv) > 3 else 5400
    # 可选第 4 个参数：命令行标记。每轮 PID 都变的作业（如 c062r 的 ABBA 交替
    # 运行）用它动态排除自己的子进程，等价于传全量 PID 且不会漏。
    cmd_pattern = sys.argv[4] if len(sys.argv) > 4 else None

    os.makedirs('reports', exist_ok=True)
    op = f'reports/c058_gpu_guard_{tag}.json'

    others_max = {}          # pid -> peak util（只含 **iGPU** compute/copy）
    npu_others_max = {}      # C-081#3：pid -> peak util（NPU 上的其它进程占用）
    other_luid_max = {}      # 既非 iGPU 也非 NPU 的适配器
    ignored_3d = {}          # pid -> peak 3d（桌面合成器底噪，仅记录不计争用）
    n_samples = 0
    conflict_samples = 0     # 其它进程在 **iGPU** 上 compute/copy 明显升高的次数
    npu_samples = 0          # 其它进程在 NPU 上 compute/copy >5% 的次数
    t0 = time.time()
    t_start = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f'[guard:{tag}] monitoring {seconds}s, my_pids={sorted(my_pids)} '
          f'cmd_pattern={cmd_pattern!r} -> {op}', flush=True)
    print(f'[guard:{tag}] LUID 口径：iGPU=*{LUID_IGPU}  NPU=*{LUID_NPU} '
          f'（NPU 占用单列，不计 GPU 争用）', flush=True)

    seen_pids = set(my_pids)
    last_refresh = 0.0
    while time.time() - t0 < seconds:
        # C-062#2：子进程 PID 每轮都变，每 15 s 按命令行标记重新收集一次
        if cmd_pattern and time.time() - last_refresh > 15:
            found = pids_matching(cmd_pattern)
            if found:
                seen_pids |= found
            last_refresh = time.time()
        rows = sample_once()
        n_samples += 1
        for pid, luid, eng, util in rows:
            if pid in seen_pids:
                continue
            e = eng.lower()
            kind = classify_luid(luid)
            if e in ('compute', 'copy'):
                if kind == 'gpu':
                    # C-060#3：只把 compute / copy 引擎计为争用
                    others_max[pid] = max(others_max.get(pid, 0.0), util)
                    if util > 5.0:
                        conflict_samples += 1
                elif kind == 'npu':
                    # C-081#3：NPU 上的其它进程占用**不算** iGPU 争用
                    # （本作业的 decoder 就在 NPU 上，不能自相残杀）
                    npu_others_max[pid] = max(npu_others_max.get(pid, 0.0), util)
                    if util > 5.0:
                        npu_samples += 1
                else:
                    key = '%s|%s' % (luid, pid)
                    other_luid_max[key] = max(other_luid_max.get(key, 0.0), util)
            elif e == '3d':
                # 3d 是桌面合成器的常驻底噪（dwm 峰值约 20%，另有 CefRenderer、
                # WorkBuddy 等），不过滤会产生假警报 —— 只记录不计争用。
                ignored_3d[pid] = max(ignored_3d.get(pid, 0.0), util)
        time.sleep(2)

    summary = {
        'tag': tag, 'my_pids': sorted(my_pids),
        'cmd_pattern': cmd_pattern,
        'all_own_pids_seen': sorted(seen_pids),
        'start_time': t_start,                       # C-060#3：便于与逐段墙钟对齐
        'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'seconds': round(time.time() - t0, 1),
        'n_samples': n_samples,
        'conflict_engines': ['compute', 'copy'],
        # C-081#3：口径声明。以前这里只按 PID 过滤、不看 LUID，会把 NPU
        # 的占用算成「其它进程抢 GPU」。现在 NPU 单独成列。
        'luid_scope': {'gpu': LUID_IGPU, 'npu': LUID_NPU,
                       'note': 'conflict/rtf_valid 只统计 iGPU LUID 的 '
                               'compute/copy；NPU 占用见 npu_other_peak_util_by_pid'},
        'ignored_3d_baseline': {str(k): round(v, 2) for k, v in
                                sorted(ignored_3d.items(), key=lambda kv: -kv[1])},
        'other_peak_util_by_pid': {str(k): round(v, 2) for k, v in
                                   sorted(others_max.items(), key=lambda kv: -kv[1])},
        'npu_other_peak_util_by_pid': {str(k): round(v, 2) for k, v in
                                       sorted(npu_others_max.items(),
                                              key=lambda kv: -kv[1])},
        'other_luid_peak_util': {k: round(v, 2) for k, v in
                                 sorted(other_luid_max.items(),
                                        key=lambda kv: -kv[1])},
        'n_conflict_samples_util_gt_5': conflict_samples,
        'n_npu_samples_util_gt_5': npu_samples,
        # 判据：出现其它进程在 **iGPU** 上 compute/copy 占用 >5% → RTF 作废。
        # NPU 上的其它进程占用不参与判定（C-081#3）。
        'rtf_valid': conflict_samples == 0,
    }
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f'\n[guard:{tag}] done: {json.dumps(summary, ensure_ascii=False)}',
          flush=True)
    print(f'[guard:{tag}] saved -> {op}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
