"""win_gpu_perf.py — 用 PDH 直读 Windows GPU 性能计数器（ctypes，无第三方依赖）

为什么不用 typeperf
-------------------
`typeperf -o out.csv` 只在 `-sc N` 采样跑满、进程**正常退出**时才写盘。
中途 `taskkill /F` / `terminate()` 会把缓冲全部丢掉，CSV 直接不存在。
而基准跑多久事先并不知道（CPU 腿比 iGPU 腿慢 10 倍）。

PDH 可以在后台线程里按固定间隔增量采样，随时停、随时拿数据。

用法
----
    q = GpuQuery([r'\\GPU Engine(*)\\Utilization Percentage',
                  r'\\GPU Adapter Memory(*)\\Dedicated Usage',
                  r'\\GPU Adapter Memory(*)\\Shared Usage'])
    q.sample()          # -> {'...\\GPU Engine(pid_...)\\Utilization Percentage': 12.3, ...}
    q.close()

实例名里带 `luid_0x00000000_0x00012EAE`，可与 OpenVINO 的
`core.get_property(dev, 'DEVICE_LUID')` 对照，把计数器映射回具体 GPU。
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes as wt

_pdh = None
PDH_FMT_DOUBLE = 0x00000200
PDH_MORE_DATA = 0x800007D2   # pdhmsg.h：缓冲区不够，返回所需大小
PDH_NO_DATA = 0x800007D5
PDH_INVALID_DATA = 0x800007D6


def _dll():
    global _pdh
    if _pdh is None:
        _pdh = ctypes.WinDLL('pdh.dll')

        class _FmtValue(ctypes.Structure):
            # CStatus(DWORD) + 4B padding + double（x64 下联合体 8 字节对齐）
            _fields_ = [('CStatus', wt.DWORD), ('doubleValue', ctypes.c_double)]

        _pdh._FmtValue = _FmtValue
        _pdh.PdhOpenQueryW.argtypes = [wt.LPCWSTR, wt.DWORD,
                                       ctypes.POINTER(wt.HANDLE)]
        _pdh.PdhOpenQueryW.restype = wt.DWORD
        _pdh.PdhAddEnglishCounterW.argtypes = [wt.HANDLE, wt.LPCWSTR, wt.DWORD,
                                               ctypes.POINTER(wt.HANDLE)]
        _pdh.PdhAddEnglishCounterW.restype = wt.DWORD
        _pdh.PdhCollectQueryData.argtypes = [wt.HANDLE]
        _pdh.PdhCollectQueryData.restype = wt.DWORD
        _pdh.PdhGetFormattedCounterValue.argtypes = [
            wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.DWORD),
            ctypes.POINTER(_FmtValue)]
        _pdh.PdhGetFormattedCounterValue.restype = wt.DWORD
        _pdh.PdhExpandWildCardPathW.argtypes = [wt.LPCWSTR, wt.LPCWSTR,
                                                wt.LPWSTR,
                                                ctypes.POINTER(wt.DWORD)]
        _pdh.PdhExpandWildCardPathW.restype = wt.DWORD
        _pdh.PdhCloseQuery.argtypes = [wt.HANDLE]
        _pdh.PdhCloseQuery.restype = wt.DWORD
    return _pdh


def _raise_for(rc, where):
    if rc not in (0, PDH_MORE_DATA):
        raise RuntimeError(f'PDH {where} failed: 0x{rc & 0xFFFFFFFF:08X}')


def expand_wildcard(path: str):
    """把 `\\GPU Engine(*)\\...` 展开成具体实例路径列表。"""
    d = _dll()
    size = wt.DWORD(0)
    rc = d.PdhExpandWildCardPathW(None, path, None, ctypes.byref(size))
    _raise_for(rc, 'expand(probe)')
    buf = ctypes.create_unicode_buffer(size.value)
    rc = d.PdhExpandWildCardPathW(None, path, buf, ctypes.byref(size))
    _raise_for(rc, 'expand(get)')
    # 返回的是 MULTI_SZ（以空串结尾的连续字符串）。注意 buf[i] 取到的是
    # 单个字符，不是整段；要 buf[:] 才能拿到含内嵌 \x00 的原文。
    return [s for s in buf[:].split('\x00') if s]


class GpuQuery:
    """一组 PDH 计数器，支持增量采样。"""

    def __init__(self, counter_paths, luid_filter=None):
        d = _dll()
        self.paths = []
        for p in counter_paths:
            if '*' in p:
                self.paths += expand_wildcard(p)
            else:
                self.paths.append(p)
        if luid_filter:
            self.paths = [p for p in self.paths
                          if luid_filter.lower() in p.lower()]
        self._hq = wt.HANDLE()
        rc = d.PdhOpenQueryW(None, 0, ctypes.byref(self._hq))
        _raise_for(rc, 'OpenQuery')
        self._handles = []
        for p in self.paths:
            h = wt.HANDLE()
            rc = d.PdhAddEnglishCounterW(self._hq, p, 0, ctypes.byref(h))
            if rc != 0:
                h = None
            self._handles.append(h)
        # 第一次采集只用于建立基线（部分计数器首值为 0）
        d.PdhCollectQueryData(self._hq)

    def sample(self):
        d = _dll()
        rc = d.PdhCollectQueryData(self._hq)
        if rc != 0:
            return {}
        out = {}
        for p, h in zip(self.paths, self._handles):
            if h is None:
                continue
            v = d._FmtValue()
            rc = d.PdhGetFormattedCounterValue(
                h, PDH_FMT_DOUBLE, None, ctypes.byref(v))
            if rc == 0 and v.CStatus == 0:
                out[p] = v.doubleValue
        return out

    def close(self):
        if self._hq:
            try:
                _dll().PdhCloseQuery(self._hq)
            except Exception:
                pass
            self._hq = None


def peak_for(paths, luid):
    """便利函数：起一个 GpuQuery 并按 interval 采样，返回各路径峰值。"""
    q = GpuQuery(paths, luid_filter=luid)
    peaks = {}
    try:
        for _ in range(3):
            for k, v in q.sample().items():
                peaks[k] = max(peaks.get(k, 0.0), v)
    finally:
        q.close()
    return peaks


def luid_low(device: str):
    """OpenVINO 设备的 LUID LowPart（十六进制字符串，大写，8 位）。"""
    try:
        import openvino as ov
        raw = ov.Core().get_property(device, 'DEVICE_LUID')
        if isinstance(raw, str):          # 本版返回的是十六进制字符串
            b = bytes.fromhex(raw)
        else:
            b = bytes(raw)
        return f'0x{int.from_bytes(b[:4], "little"):08X}'
    except Exception:
        return None


if __name__ == '__main__':
    import time
    print('LUID:', {d: luid_low(d) for d in ('GPU.0', 'GPU.1')})
    q = GpuQuery([r'\GPU Engine(*)\Utilization Percentage',
                  r'\GPU Adapter Memory(*)\Dedicated Usage',
                  r'\GPU Adapter Memory(*)\Shared Usage'])
    print(f'{len(q.paths)} 个计数器实例')
    for _ in range(5):
        vals = q.sample()
        top = sorted(vals.items(), key=lambda kv: -kv[1])[:3]
        print(' | '.join(f'{p.split(chr(92))[-2][:38]}={v:.1f}'
                         for p, v in top))
        time.sleep(0.5)
    q.close()
