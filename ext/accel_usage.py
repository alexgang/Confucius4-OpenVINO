r"""iGPU / NPU utilization via PDH '\GPU Engine(*)\Utilization Percentage' (no psutil, no PowerShell).
Adapter = LUID. NPU: any engine type starting with 'neural' (or an adapter with only compute engines).
Intel iGPU: adapter that has a 'gsc' engine. NVIDIA: has 'ofa*' -> ignored.
Per adapter utilization = max over engines of (sum over processes), like Task Manager."""
import ctypes as C
import ctypes.wintypes as W
import re
import threading
import time

_RX = re.compile(r'luid_(0x[0-9a-f]+_0x[0-9a-f]+)_phys_(\d+)_eng_(\d+)_engtype_(.*)$', re.I)


class _FMT(C.Structure):
    _fields_ = [('CStatus', W.DWORD), ('doubleValue', C.c_double)]


class _ITEM(C.Structure):
    _fields_ = [('szName', C.c_wchar_p), ('FmtValue', _FMT)]


class AccelUsage:
    def __init__(self, period=1.0):
        self.period = period
        self.latest = {"igpu_pct": None, "npu_pct": None}
        self._t = None

    def start(self):
        if self._t is None:
            self._t = threading.Thread(target=self._run, name="accel-usage", daemon=True)
            self._t.start()
        return self

    def _run(self):
        try:
            pdh = C.WinDLL('pdh')
            pdh.PdhOpenQueryW.argtypes = [C.c_wchar_p, C.c_size_t, C.POINTER(C.c_void_p)]
            pdh.PdhAddEnglishCounterW.argtypes = [C.c_void_p, C.c_wchar_p, C.c_size_t, C.POINTER(C.c_void_p)]
            pdh.PdhCollectQueryData.argtypes = [C.c_void_p]
            pdh.PdhGetFormattedCounterArrayW.argtypes = [C.c_void_p, W.DWORD, C.POINTER(W.DWORD),
                                                         C.POINTER(W.DWORD), C.c_void_p]
            q = C.c_void_p(); h = C.c_void_p()
            if pdh.PdhOpenQueryW(None, 0, C.byref(q)) != 0:
                return
            if pdh.PdhAddEnglishCounterW(q, r'\GPU Engine(*)\Utilization Percentage', 0, C.byref(h)) != 0:
                return
            pdh.PdhCollectQueryData(q)
            while True:
                time.sleep(self.period)
                try:
                    self.latest = self._sample(pdh, q, h)
                except Exception:
                    pass
        except Exception:
            return

    @staticmethod
    def _sample(pdh, q, h):
        pdh.PdhCollectQueryData(q)
        size = W.DWORD(0); cnt = W.DWORD(0)
        fmt = 0x00000200 | 0x00008000          # PDH_FMT_DOUBLE | PDH_FMT_NOCAP100
        pdh.PdhGetFormattedCounterArrayW(h, fmt, C.byref(size), C.byref(cnt), None)
        if size.value == 0:
            return {"igpu_pct": None, "npu_pct": None}
        buf = C.create_string_buffer(size.value)
        if pdh.PdhGetFormattedCounterArrayW(h, fmt, C.byref(size), C.byref(cnt), buf) != 0:
            return {"igpu_pct": None, "npu_pct": None}
        items = C.cast(buf, C.POINTER(_ITEM))
        eng = {}       # (luid, phys, eng) -> sum
        types = {}     # luid -> set(engtype)
        for i in range(cnt.value):
            it = items[i]
            m = _RX.search(it.szName or '')
            if not m or it.FmtValue.CStatus not in (0, 1):
                continue
            luid, phys, e, et = m.group(1), m.group(2), m.group(3), m.group(4).lower()
            types.setdefault(luid, set()).add(et)
            k = (luid, phys, e)
            eng[k] = eng.get(k, 0.0) + max(0.0, it.FmtValue.doubleValue)
        per = {}
        for (luid, _p, _e), v in eng.items():
            per[luid] = max(per.get(luid, 0.0), v)
        npu = igpu = None
        for luid, ts in types.items():
            if any(t.startswith('neural') for t in ts) or (ts and all(t.startswith('compute') for t in ts)):
                npu = max(npu or 0.0, per.get(luid, 0.0))
            elif 'gsc' in ts:
                igpu = max(igpu or 0.0, per.get(luid, 0.0))
        r = lambda v: None if v is None else round(min(100.0, v), 1)
        return {"igpu_pct": r(igpu), "npu_pct": r(npu)}


if __name__ == '__main__':
    a = AccelUsage(1.0).start()
    for _ in range(6):
        time.sleep(1.0); print(a.latest, flush=True)
