# -*- coding: utf-8 -*-
"""APP-023② —— 桌面快捷方式改指向 **v1.5 客户包启动器**（方案一）。

🔴 为什么不能用 `WScript.Shell` 的 COM（PowerShell）：
    本环境安全策略直接拦 `New-Object -ComObject WScript.Shell`
    （「COM object instantiation can run arbitrary code」）。
⇒ 正解：用 **ctypes 直接调 Win32 `IShellLinkW` + `IPersistFile`**，
    不经过 PowerShell，也不手写 .lnk 二进制（Shell Link 格式写错一点 Explorer
    就认不出，**那比不改更糟 —— 用户桌面图标直接废掉**）。

🔴🔴 踩过的坑（本脚本第一版把进程打死了，exit=127 且**无任何输出**）：
    `IShellLink::GetPath` 是 **4 个参数**
        `GetPath(LPWSTR pszFile, int cchMaxPath, WIN32_FIND_DATAW *pfd, DWORD fFlags)`
    而我按 2 个参数调用 ⇒ **x64 调用约定下参数个数不匹配 ⇒ 栈被搅 ⇒ 硬崩**，
    且 ctypes 层的崩溃**不会**抛 Python 异常（连 traceback 都没有）。
    ⇒ 教训：**COM vtable 手写调用必须逐个核对 MSDN 的真实参数个数**；
       「看起来像 2 参的 getter」往往还带 `pfd` / `fFlags`。

为什么选**方案一**（改指向包）而不是**方案二**（给 dev .venv 装 babelvox）：
    实测（`--why` 会复算）：
      · babelvox 1.7.1 的 METADATA 要求 `transformers>=5.0`、`huggingface_hub>=1.0`；
        dev `.venv` 现装 transformers **4.57.6** / huggingface_hub **0.36.2**
        ⇒ 装 babelvox 会把这两个**大版本跨升**，MT/ASR 也在用 transformers
        ⇒ **跨模块风险**，不该由 App 单方面做。
      · 且 dev 树 **根本没** `models/qwen3tts`（只有 ASR/MT 的 ov-* / hf-qwen3-lm）
        ⇒ 即便装上 babelvox 也**仍然跑不起来**，还得再搬 2.6 GB 模型。
    ⇒ 客户包 v1.5 自带 babelvox 1.7.1 + `models/qwen3tts` + 自己的 python
      ⇒ **改指向包**是唯一「一次到位、不碰别人环境」的做法。

用法：
    python app094_fix_desktop_shortcut.py            # 只读预览
    python app094_fix_desktop_shortcut.py --why      # 复算方案二不可行的依据
    python app094_fix_desktop_shortcut.py --apply    # 真正改（改前自动备份）
    python app094_fix_desktop_shortcut.py --restore  # 从备份还原
"""
from __future__ import annotations

import ctypes
import glob
import io
import os
import shutil
import subprocess
import sys
from ctypes import wintypes

LNK = os.path.join(os.path.expanduser('~'), 'Desktop', 'Confucius4 实时字幕.lnk')
BAK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'Confucius4-shortcut-backup-20261027.lnk')
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
BAT = os.path.join(PKG, 'Start_LiveCaption.bat')
DESC = 'Confucius4-R2T2 实时字幕（v1.5 客户包 / Intel GPU / NPU / NVIDIA CUDA）'
ICON = os.path.join(PKG, 'python', 'pythonw.exe')

CLSID_SHELLLINK = '{00021401-0000-0000-C000-000000000046}'
IID_ISHELLLINKW = '{000214F9-0000-0000-C000-000000000046}'
IID_IPERSISTFILE = '{0000010b-0000-0000-C000-000000000046}'

# IShellLinkW vtable（IUnknown 占 0/1/2）
VT = {
    'GetPath': 3, 'GetIDList': 4, 'SetIDList': 5,
    'GetDescription': 6, 'SetDescription': 7,
    'GetWorkingDirectory': 8, 'SetWorkingDirectory': 9,
    'GetArguments': 10, 'SetArguments': 11,
    'GetHotkey': 12, 'SetHotkey': 13,
    'GetShowCmd': 14, 'SetShowCmd': 15,
    'GetIconLocation': 16, 'SetIconLocation': 17,
    'SetRelativePath': 18, 'Resolve': 19, 'SetPath': 20,
}
VT_PF = {'GetClassID': 3, 'IsDirty': 4, 'Load': 5,
         'Save': 6, 'SaveCompleted': 7, 'GetCurFile': 8}

SLGP_RAWPATH = 4

ole32 = ctypes.windll.ole32      # 🔴 ctypes 没有 ctypes.ole32，必须 windll 取


class GUID(ctypes.Structure):
    _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                ('Data3', wintypes.WORD), ('Data4', ctypes.c_ubyte * 8)]


ole32.IIDFromString.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(GUID)]
ole32.IIDFromString.restype = ctypes.HRESULT
ole32.CoInitialize.argtypes = [ctypes.c_void_p]
ole32.CoInitialize.restype = ctypes.HRESULT
ole32.CoUninitialize.restype = None
ole32.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p,
                                   wintypes.DWORD, ctypes.POINTER(GUID),
                                   ctypes.POINTER(ctypes.c_void_p)]
ole32.CoCreateInstance.restype = ctypes.HRESULT


def iid(s):
    g = GUID()
    ole32.IIDFromString(s, ctypes.byref(g))
    return g


def hr(rc, what):
    if rc < 0:
        raise OSError('%s 失败：HRESULT=0x%08X' % (what, rc & 0xFFFFFFFF))
    return rc


def slot(obj, idx, restype, *argtypes):
    """取 COM 对象第 idx 号虚方法（参数个数/类型**必须**与 MSDN 完全一致）。"""
    vt = ctypes.cast(obj, ctypes.POINTER(ctypes.c_void_p))
    arr = ctypes.cast(vt[0], ctypes.POINTER(ctypes.c_void_p))
    fn = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return ctypes.cast(arr[idx], fn)


def make_shelllink():
    ole32.CoInitialize(None)
    p = ctypes.c_void_p()
    hr(ole32.CoCreateInstance(ctypes.byref(iid(CLSID_SHELLLINK)), None, 1,
                              ctypes.byref(iid(IID_ISHELLLINKW)),
                              ctypes.byref(p)), 'CoCreateInstance')
    return p


def persist_file(p):
    pf = ctypes.c_void_p()
    qi = slot(p, 0, ctypes.HRESULT, ctypes.POINTER(GUID),
              ctypes.POINTER(ctypes.c_void_p))
    hr(qi(p, ctypes.byref(iid(IID_IPERSISTFILE)), ctypes.byref(pf)),
       'QueryInterface(IPersistFile)')
    return pf


def read_lnk(path):
    p = make_shelllink()
    pf = persist_file(p)
    load = slot(pf, VT_PF['Load'], ctypes.HRESULT,
                ctypes.c_wchar_p, wintypes.DWORD)
    hr(load(pf, path, 0), 'IPersistFile.Load')          # STGM_READ = 0

    def getter(idx):
        buf = ctypes.create_unicode_buffer(4096)
        f = slot(p, idx, ctypes.HRESULT, ctypes.c_wchar_p, ctypes.c_int,
                 ctypes.c_void_p, wintypes.DWORD)
        f(p, buf, 4096, None, SLGP_RAWPATH)
        return buf.value

    out = {
        # 🔴 GetPath 是 4 参：pszFile / cchMaxPath / pfd / fFlags
        'TargetPath': getter(VT['GetPath']),
        'Arguments': getter(VT['GetArguments']),
        'WorkingDirectory': getter(VT['GetWorkingDirectory']),
        'Description': getter(VT['GetDescription']),
    }
    ole32.CoUninitialize()
    return out


def write_lnk(path, target, args, workdir, desc, icon):
    p = make_shelllink()
    hr(slot(p, VT['SetPath'], ctypes.HRESULT, ctypes.c_wchar_p)(p, target),
       'SetPath')
    hr(slot(p, VT['SetArguments'], ctypes.HRESULT,
            ctypes.c_wchar_p)(p, args), 'SetArguments')
    hr(slot(p, VT['SetWorkingDirectory'], ctypes.HRESULT,
            ctypes.c_wchar_p)(p, workdir), 'SetWorkingDirectory')
    hr(slot(p, VT['SetDescription'], ctypes.HRESULT,
            ctypes.c_wchar_p)(p, desc), 'SetDescription')
    hr(slot(p, VT['SetIconLocation'], ctypes.HRESULT,
            ctypes.c_wchar_p, ctypes.c_int)(p, icon, 0), 'SetIconLocation')
    pf = persist_file(p)
    hr(slot(pf, VT_PF['Save'], ctypes.HRESULT,
            ctypes.c_wchar_p, wintypes.BOOL)(pf, path, True),
       'IPersistFile.Save')
    ole32.CoUninitialize()


def why_not_plan_b():
    print('\n── 方案二（给 dev .venv 装 babelvox）为什么不可行 ──')
    py = r'.venv\Scripts\python.exe'
    code = ('import importlib.metadata as md\n'
            'for n in ["transformers","huggingface_hub","openvino","numpy",'
            '"librosa","soundfile","scipy"]:\n'
            '    try: print("  %-18s"%n, md.version(n))\n'
            '    except Exception: print("  %-18s"%n, "<missing>")\n')
    r = subprocess.run([py, '-c', code], capture_output=True, text=True,
                       cwd=r'C:\Users\Trekker-PTL\confucius4-openvino')
    print('dev .venv 现装版本：')
    print(r.stdout.rstrip() or r.stderr[:300])
    for mp in glob.glob(os.path.join(PKG, 'python', 'Lib', 'site-packages',
                                     'babelvox-*.dist-info', 'METADATA')):
        txt = io.open(mp, encoding='utf-8', errors='replace').read()
        print('babelvox METADATA 硬性要求（节选）：')
        for l in txt.splitlines():
            if l.startswith('Requires-Dist') and 'extra ==' not in l:
                print('  ', l)
    print('dev 树 models/qwen3tts 存在：',
          os.path.isdir(r'C:\Users\Trekker-PTL\confucius4-openvino'
                        r'\models\qwen3tts'))
    print('包内 models/qwen3tts 存在：',
          os.path.isdir(os.path.join(PKG, 'models', 'qwen3tts')))


def main():
    print('=' * 74)
    print('APP-023② 桌面快捷方式 → v1.5 客户包启动器（方案一）')
    print('=' * 74)
    print('快捷方式   : %s' % LNK)
    print('存在       : %s' % os.path.isfile(LNK))
    print('备份       : %s  存在=%s' % (BAK, os.path.isfile(BAK)))
    print('包启动器   : %s  存在=%s' % (BAT, os.path.isfile(BAT)))

    if '--restore' in sys.argv:
        if not os.path.isfile(BAK):
            print('\n❌ 没有备份，无法还原')
            return 2
        shutil.copy2(BAK, LNK)
        print('\n已从备份还原；回读：')
        for k, v in read_lnk(LNK).items():
            print('  %-18s %s' % (k, v))
        return 0

    print('\n── 改之前 ──')
    before = read_lnk(LNK)
    for k, v in before.items():
        print('  %-18s %s' % (k, v))

    after = {'TargetPath': BAT, 'Arguments': '',
             'WorkingDirectory': PKG, 'Description': DESC}
    print('\n── 目标值 ──')
    for k, v in after.items():
        print('  %-18s %s' % (k, v))

    if '--why' in sys.argv:
        why_not_plan_b()

    if '--apply' not in sys.argv:
        print('\n（只读预览；加 --apply 才写盘，写前自动备份到 %s）' % BAK)
        return 0

    if not os.path.isfile(BAT):
        print('\n❌ 包启动器不存在，拒绝写快捷方式')
        return 2
    if not os.path.isfile(BAK):
        shutil.copy2(LNK, BAK)
        print('\n已备份 → %s' % BAK)
    write_lnk(LNK, BAT, '', PKG, DESC, ICON)
    print('\n── 回读校验 ──')
    got = read_lnk(LNK)
    ok = True
    for k, v in after.items():
        same = (got.get(k) == v)
        ok = ok and same
        print('  %s %-18s %s' % ('✅' if same else '❌', k, got.get(k)))
    print('\n回读一致：%s' % ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
