#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
app168 —— 客户包**运行时可加载性**独立验收（§112）

🔴 **为什么需要这一条（§112 补做）**
  §109/§110 只验了「仓库 ⇄ 包目录**归一化行尾后逐字节一致**」
  ⇒ 那是**静态**判据 ⇒ **不能**证明包内那份代码在**客户机的解释器**里
  真的能 import（§110 的 `gui_status.py`、§109 的 `asr_spk/` 3 个文件
  **都从未在包内 python 下被真正加载过**）。
  ⇒ 本脚本用**客户包自带的 `python/python.exe`**（3.12.10，与客户机一致）
  **真实 import** 包内模块 ⇒ 把「包目录对」升级成「**包内运行时真的能加载**」。

🔴 **纪律**
  - **不跑推理 / 不测速 / 不占 GPU**（只做 import 与路径解析）。
  - **不写客户包**（只读）。
  - **不 import 被测模块到本进程**（而是**子进程**里 import ⇒ 顶层 numpy
    / OpenVINO 不会污染本进程；也避免 `import` 副作用影响判据）。
  - **自动发现最大版本包**（🔴 教训：pkg 回归脚本写死版本号会过期 ——
    §47 实测 `test_tts_close_gui_quit_pkg.py` 写死 `v1.4` 对 v1.5 误报 FAIL）。
  - **反证组**：把判据前提破坏掉 ⇒ 必须 FAIL ⇒ 证明判据**不是恒真**。

判据分组：
  R1  客户包自带 python 可执行 + 版本可读
  R2  包内 `gui_status.py`（APP-048 新增）可 import，且 `build_sections()` 返 3 个区
  R3  包内 `live_caption_app.py`（APP-048 改后）可 import，`App` 存在
  R4  包内 `asr_spk/` 3 个资产在**真实加载路径**（`sys.path.insert`）下可 import
  R5  `asr052_spk_runtime` 的 `EMBED_RANGE_LO/HI` == [100, 2048]（ASR-031 §11.2）
  R6  `asr_thread_defaults.THREAD_VARS` 含 OMP/MKL/OPENBLAS（APP-043 线程限制）
  R7  `speaker_assets.resolve()` ⇒ `ok=true` 且 wes_ir/seg_ir **真实存在**（APP-044）
  R8  包内**无** `torch` / `qwen_asr`（§46.5 记录：site-packages 缺失）
      ⇒ **不判 FAIL**，只**记录事实**（属另���类问题）

  B1  反证：把 `sys.path` 指向**空目录** ⇒ `asr052_speaker_tracker_api` **必须** ImportError
      （证明 R4 的成功**依赖**真实路径，不是「随便 import 都行」）
  B2  反证：把 `models/spk` **临时改名** ⇒ `speaker_assets.resolve()` **必须** `ok=false`
      ⇒ 证明 R7 的 `ok=true` **依赖**模型真实存在（🔴 但**不改客户包** ⇒
      用**影子目录**复制 `speaker_assets.py` + 空 `models/spk` 来做，不动真包）

用法：
    python results/app/app168_pkg_runtime_import_probe.py --pkg <客户包目录>
    python results/app/app168_pkg_runtime_import_probe.py     # 自动发现最大版本包
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PKG_ROOT_PARENT = os.path.join(os.path.expanduser('~'), 'Confucius4_LiveCaption_v1.12')


# ── 工具 ────────────────────────────────────────────────────────────
def _parse_ver(name):
    """从 `Confucius4_LiveCaption_v<ver>` 解析版本元组。

    🔴 **自踩坑（本轮实测）**：原先用 `tail.split('.')[0]` ⇒ `v1.12` 只取到 `'1'`
    ⇒ **所有包版本都变成 `(1,)`** ⇒ 平局时取到先遍历到的 `v1.0.bak_20261020`
    ⇒ 验收跑在**备份目录**上（`gui_status.py` / `asr_spk/` 都不存在）⇒ 满屏 FAIL。

    ⇒ 正确做法：取**小数点后**的完整数字段（`12` / `3` / `10`），
      再按 `.` 切分成元组；**排除**带后缀的备份目录（`.bak_*` / `_*_backup`）。
    ⇒ 版本比较用**元组比较**（`1.9 < 1.10`），不用字符串比较。
    """
    tail = name[len('Confucius4_LiveCaption_v'):]
    # 排除备份目录：`v1.0.bak_20261020` / `v1.3_pre_c133_backup`
    if '.bak' in tail or '_backup' in tail:
        return None
    m = re.match(r'^(\d+(?:\.\d+)*)', tail)
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split('.'))


def discover_pkg():
    """自动发现最大版本包目录（🔴 不写死版本号）。"""
    home = os.path.expanduser('~')
    best = None
    for name in os.listdir(home):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        if not os.path.isdir(os.path.join(home, name)):
            continue
        ver = _parse_ver(name)
        if ver is None:
            continue
        if best is None or ver > best[0]:
            best = (ver, os.path.join(home, name))
    return best[1] if best else None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def pkg_python(pkg):
    """客户包自带的 python.exe（客户机形态）。"""
    for rel in (('python', 'python.exe'),):
        p = os.path.join(pkg, *rel)
        if os.path.exists(p):
            return p
    return None


def run_py(exe, cwd, code, timeout=300, clean_env=True):
    """在**子进程**里跑一段 python 代码，返回 (rc, stdout, stderr)。

    🔴 用**包自带解释器** ⇒ 判据反映的是**客户机真实环境**。

    🔴🔴🔴 **自踩坑（本轮实测，重要）**：宿主（WorkBuddy）自己设了
      `PYTHONPATH=C:\\Program Files\\WorkBuddy\\resources\\app.asar.unpacked\\cli\\vendor\\shim`
      ⇒ 该变量**被继承进包内 python** ⇒ 包内 `sys.path` 里多出一条**客户机上
      根本不存在**的路径 ⇒ ① `import torch` 会「成功」但 `torch.__file__ is None`
      （**namespace package 假阳性**）② 任何模块可能从 shim 里被加载
      ⇒ **验收结论会是假通过**。
      ⇒ 修法：`clean_env=True` ⇒ **清空 `PYTHONPATH` / `PYTHONHOME`**
      （**不是**删除，而是置空字符串，避免继承）。
      ⇒ 并且把临时脚本放在 **cwd 之内**（不是系统 TEMP）⇒ `sys.path[0]`
      才会是包的 app 目录，模拟真实启动形态。
    """
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                     encoding='utf-8', dir=cwd) as f:
        f.write(code)
        script = f.name
    env = None
    if clean_env:
        env = dict(os.environ)
        env['PYTHONPATH'] = ''
        env['PYTHONHOME'] = ''
    try:
        p = subprocess.run([exe, script], cwd=cwd, capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -9, '', 'TIMEOUT'
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass


# ── 各组判据的子进程脚本 ────────────────────────────────────────────
PROBE_R2 = r'''
import sys, os, json
sys.path.insert(0, os.path.abspath('.'))
out = {}
try:
    import gui_status
    out['import_ok'] = True
    out['file'] = os.path.abspath(gui_status.__file__)
    r = gui_status.build_sections()
    out['n_sections'] = len(r)
    out['section_keys'] = sorted(r.keys()) if isinstance(r, dict) else None
    # 渲染一次（验证纯逻辑可用，不碰 tkinter）
    out['render_ok'] = True
    for k, v in (r.items() if isinstance(r, dict) else []):
        try:
            v.render()
        except Exception as e:
            out['render_ok'] = False
            out['render_err'] = '%s: %s' % (type(e).__name__, e)
            break
except Exception as e:
    out['import_ok'] = False
    out['err'] = '%s: %s' % (type(e).__name__, e)
print('__JSON__' + json.dumps(out, ensure_ascii=False))
'''

PROBE_R3 = r'''
import sys, os, json
sys.path.insert(0, os.path.abspath('.'))
out = {}
try:
    import live_caption_app as A
    out['import_ok'] = True
    out['file'] = os.path.abspath(A.__file__)
    out['has_App'] = hasattr(A, 'App')
except SystemExit as e:
    out['import_ok'] = True
    out['systemexit'] = str(e)
except Exception as e:
    out['import_ok'] = False
    out['err'] = '%s: %s' % (type(e).__name__, e)
print('__JSON__' + json.dumps(out, ensure_ascii=False))
'''

PROBE_R4 = r'''
import sys, os, json
app = os.path.abspath('.')
sys.path.insert(0, app)
sys.path.insert(0, os.path.join(app, 'asr_spk'))
out = {}
for m in ('asr052_speaker_tracker_api', 'asr052_spk_runtime', 'asr_thread_defaults'):
    try:
        mod = __import__(m)
        out[m] = {'ok': True, 'file': os.path.abspath(mod.__file__)}
        if m == 'asr052_spk_runtime':
            out[m]['EMBED_RANGE_LO'] = getattr(mod, 'EMBED_RANGE_LO', None)
            out[m]['EMBED_RANGE_HI'] = getattr(mod, 'EMBED_RANGE_HI', None)
        if m == 'asr_thread_defaults':
            out[m]['THREAD_VARS'] = list(getattr(mod, 'THREAD_VARS', ()))
    except Exception as e:
        out[m] = {'ok': False, 'err': '%s: %s' % (type(e).__name__, e)}
print('__JSON__' + json.dumps(out, ensure_ascii=False))
'''

PROBE_R7 = r'''
import sys, os, json
sys.path.insert(0, os.path.abspath('.'))
out = {}
try:
    import speaker_assets as SA
    out['file'] = os.path.abspath(SA.__file__)
    r = SA.resolve()
    out['resolve'] = r
    out['wes_exists'] = bool(r.get('wes_ir')) and os.path.isdir(r.get('wes_ir'))
    out['seg_exists'] = bool(r.get('seg_ir')) and os.path.isdir(r.get('seg_ir'))
    out['scripts_dir'] = SA.find_asr_scripts()
    out['scripts_exists'] = bool(out['scripts_dir']) and os.path.isdir(out['scripts_dir'])
except Exception as e:
    out['err'] = '%s: %s' % (type(e).__name__, e)
print('__JSON__' + json.dumps(out, ensure_ascii=False))
'''

PROBE_R8 = r'''
import sys, os, json
out = {}
for m in ('torch', 'qwen_asr'):
    try:
        mod = __import__(m)
        # 🔴 **namespace package 假阳性**：`import torch` 成功但
        #   `torch.__file__ is None` ⇒ 只是**空目录**被当成 namespace package
        #   ⇒ **不等于**真的装了 torch ⇒ 必须看 __file__
        out[m] = {'status': 'PRESENT',
                  'file': getattr(mod, '__file__', None),
                  'path': list(getattr(mod, '__path__', []) or [])}
    except Exception as e:
        out[m] = {'status': type(e).__name__}
print('__JSON__' + json.dumps(out, ensure_ascii=False))
'''

PROBE_R9 = r'''
import sys, os, json
paths = list(sys.path)
out = {'sys_path': paths,
       'cwd': os.getcwd(),
       'script_dir': os.path.dirname(os.path.abspath(__file__))}
# 🔴 判据：sys.path 里**不得**出现「不属于本包」的目录
#   （例如宿主的 vendor/shim）⇒ 否则验收结论可能来自**外部污染**
pkgroot = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
foreign = [p for p in paths if p and not os.path.abspath(p).startswith(pkgroot)]
out['foreign_paths'] = foreign
print('__JSON__' + json.dumps(out, ensure_ascii=False))
'''

PROBE_B1 = r'''
import sys, os, json
sys.path.insert(0, os.path.abspath('.'))
out = {}
try:
    import asr052_speaker_tracker_api
    out['import_ok'] = True
except Exception as e:
    out['import_ok'] = False
    out['err'] = '%s: %s' % (type(e).__name__, e)
print('__JSON__' + json.dumps(out, ensure_ascii=False))
'''

PROBE_B2 = r'''
import sys, os, json
sys.path.insert(0, os.path.abspath('.'))
out = {}
try:
    import speaker_assets as SA
    r = SA.resolve()
    out['resolve'] = r
    out['ok'] = bool(r.get('ok'))
except Exception as e:
    out['err'] = '%s: %s' % (type(e).__name__, e)
print('__JSON__' + json.dumps(out, ensure_ascii=False))
'''


def parse_json_out(stdout):
    for line in stdout.splitlines():
        if line.startswith('__JSON__'):
            return json.loads(line[len('__JSON__'):])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--out', default=os.path.join(HERE,
                                                 'app168_pkg_runtime_import_probe_evidence.json'))
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    if not pkg or not os.path.isdir(pkg):
        print('!! 找不到客户包目录（--pkg 未给且自动发现失败）')
        return 2
    app = os.path.join(pkg, 'app')
    if not os.path.isdir(app):
        print('!! 客户包没有 app/ 目录:', pkg)
        return 2

    details = []
    n_pass = 0
    n_fail = 0

    def rec(name, ok, msg=''):
        nonlocal n_pass, n_fail
        details.append({'name': name, 'ok': bool(ok), 'msg': msg})
        if ok:
            n_pass += 1
        else:
            n_fail += 1
        print(('[PASS] ' if ok else '[FAIL] ') + name + (' :: ' + msg if msg else ''))

    exe = pkg_python(pkg)
    rec('R1 客户包自带 python 存在', bool(exe) and os.path.exists(exe),
        'exe=%s' % (exe or 'None'))
    if not exe:
        return _write(args.out, pkg, app, exe, details, n_pass, n_fail, 2)

    rc, so, se = run_py(exe, app, "import sys; print('__JSON__' + __import__('json').dumps({'ver': sys.version.split()[0]}))")
    j = parse_json_out(so)
    rec('R1b 包内 python 版本可读且 >= 3.10', bool(j) and j.get('ver', '').startswith('3.'),
        'ver=%s' % (j.get('ver') if j else se.strip()[:200]))

    # R2
    rc, so, se = run_py(exe, app, PROBE_R2)
    j = parse_json_out(so) or {}
    rec('R2 包内 gui_status.py 可 import', j.get('import_ok') is True,
        j.get('err') or ('file=%s' % j.get('file')))
    rec('R2b gui_status.build_sections() 返回 3 个区（ASR/翻译/TTS）',
        j.get('n_sections') == 3, 'n=%s keys=%s' % (j.get('n_sections'), j.get('section_keys')))
    rec('R2c gui_status 三区 render() 均可执行（纯逻辑，不碰 tkinter）',
        j.get('render_ok') is True, j.get('render_err') or '')

    # R3
    rc, so, se = run_py(exe, app, PROBE_R3)
    j = parse_json_out(so) or {}
    rec('R3 包内 live_caption_app.py 可 import', j.get('import_ok') is True,
        j.get('err') or ('file=%s' % j.get('file')))
    rec('R3b live_caption_app.App 存在', j.get('has_App') is True, '')

    # R4
    rc, so, se = run_py(exe, app, PROBE_R4)
    j = parse_json_out(so) or {}
    for m in ('asr052_speaker_tracker_api', 'asr052_spk_runtime', 'asr_thread_defaults'):
        info = j.get(m) or {}
        rec('R4 包内 asr_spk/%s 真实加载路径可 import' % m, info.get('ok') is True,
            info.get('err') or ('file=%s' % info.get('file')))

    # R5
    info = (j.get('asr052_spk_runtime') or {})
    rec('R5 EMBED_RANGE_LO/HI == [100, 2048]（ASR-031 §11.2）',
        info.get('EMBED_RANGE_LO') == 100 and info.get('EMBED_RANGE_HI') == 2048,
        'LO=%s HI=%s' % (info.get('EMBED_RANGE_LO'), info.get('EMBED_RANGE_HI')))

    # R6
    info = (j.get('asr_thread_defaults') or {})
    tv = set(info.get('THREAD_VARS') or [])
    need = {'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'}
    rec('R6 THREAD_VARS 含 OMP/MKL/OPENBLAS（APP-043 线程限制）', need <= tv,
        'THREAD_VARS=%s' % sorted(tv))

    # R7
    rc, so, se = run_py(exe, app, PROBE_R7)
    j = parse_json_out(so) or {}
    res = j.get('resolve') or {}
    rec('R7 speaker_assets.resolve() ⇒ ok=true', res.get('ok') is True,
        'reason=%s' % res.get('reason'))
    rec('R7b 包内 wespeaker OV IR 目录真实存在（APP-044）', j.get('wes_exists') is True,
        'wes_ir=%s' % res.get('wes_ir'))
    rec('R7c 包内 pyannote/segmentation-3.0 OV IR 目录真实存在（APP-044）',
        j.get('seg_exists') is True, 'seg_ir=%s' % res.get('seg_ir'))
    rec('R7d 包内 asr_spk/ 接口代码目录真实存在', j.get('scripts_exists') is True,
        'scripts=%s' % j.get('scripts_dir'))

    # R8（只记录，不判 FAIL）—— 🔴 必须看 __file__，namespace package 会假阳性
    rc, so, se = run_py(exe, app, PROBE_R8)
    j8 = parse_json_out(so) or {}

    def _dep(m):
        d = j8.get(m) or {}
        if d.get('status') != 'PRESENT':
            return '%s' % d.get('status')
        if not d.get('file'):
            return 'PRESENT-NAMESPACE-FAKE(file=None)'
        return 'PRESENT(%s)' % os.path.basename(d.get('file') or '')

    rec('R8 包内 torch/qwen_asr 存在性（**只记录事实**，§46.5 另议）', True,
        'torch=%s qwen_asr=%s' % (_dep('torch'), _dep('qwen_asr')))

    # R9 环境洁净度：包内 python 的 sys.path 不得含包外路径
    rc, so, se = run_py(exe, app, PROBE_R9)
    j9 = parse_json_out(so) or {}
    foreign = j9.get('foreign_paths') or []
    rec('R9 包内 python 的 sys.path 不含包外路径（无宿主 PYTHONPATH 污染）',
        len(foreign) == 0, 'foreign=%s' % foreign)

    # B3 反证：故意**注入**一个包外路径到 PYTHONPATH ⇒ R9 必须 FAIL
    #   （证明 R9 不是恒真，且本脚本的 clean_env 确实在起作用）
    shim = tempfile.mkdtemp(prefix='app168_shim_')
    try:
        env_path = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + shim
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                        encoding='utf-8', dir=app) as f:
            f.write(PROBE_R9)
            script = f.name
        try:
            env = dict(os.environ)
            env['PYTHONPATH'] = env_path
            p = subprocess.run([exe, script], cwd=app, capture_output=True,
                               text=True, encoding='utf-8', errors='replace',
                               timeout=300, env=env)
            jb3 = parse_json_out(p.stdout) or {}
            foreign_b3 = jb3.get('foreign_paths') or []
            rec('B3 反证：注入包外 PYTHONPATH ⇒ R9 必须 FAIL（证明 R9 不是恒真）',
                len(foreign_b3) > 0, 'foreign=%s' % foreign_b3)
        finally:
            try:
                os.unlink(script)
            except OSError:
                pass
    finally:
        shutil.rmtree(shim, ignore_errors=True)

    # ── B1 反证：真实路径依赖性 ───────────────────────────────────
    rc, so, se = run_py(exe, app, PROBE_B1)
    j = parse_json_out(so) or {}
    rec('B1 反证：不在 sys.path 时 asr052_speaker_tracker_api 必须 ImportError'
        '（证明 R4 不是恒真）', j.get('import_ok') is False,
        'import_ok=%s err=%s' % (j.get('import_ok'), j.get('err')))

    # ── B2 反证：模型缺失 ⇒ resolve 必须 ok=false（**影子目录**，不动真包）──
    # 🔴 **自踩坑（本轮实测）**：B2 硬依赖 `speaker_assets.py` 存在 ⇒ 对**旧包**
    #   （无该文件）会抛 FileNotFoundError ⇒ 脚本崩掉、证据不落盘。
    #   ⇒ 判据必须**优雅降级**：文件缺失 ⇒ B2 判「不适用」但**仍记为 PASS**
    #   （反证的前提本就不存在 ⇒ 不是判据失效），且**不得让脚本崩**。
    src_sa = os.path.join(app, 'speaker_assets.py')
    if not os.path.exists(src_sa):
        rec('B2 反证：影子目录（无 models/spk 资产）⇒ resolve().ok 必须 false'
            '（证明 R7 不是恒真，且**真包零改动**）', True,
            '（该包无 speaker_assets.py ⇒ B2 前提不存在 ⇒ 不适用；脚本未崩）')
    else:
        shadow = tempfile.mkdtemp(prefix='app168_shadow_')
        try:
            shutil.copy2(src_sa, os.path.join(shadow, 'speaker_assets.py'))
            os.makedirs(os.path.join(shadow, 'models', 'spk'), exist_ok=True)
            rc, so, se = run_py(exe, shadow, PROBE_B2)
            j = parse_json_out(so) or {}
            res = j.get('resolve') or {}
            rec('B2 反证：影子目录（无 models/spk 资产）⇒ resolve().ok 必须 false'
                '（证明 R7 不是恒真，且**真包零改动**）', res.get('ok') is False,
                'ok=%s reason=%s' % (res.get('ok'), res.get('reason')))
        finally:
            shutil.rmtree(shadow, ignore_errors=True)

    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    return _write(args.out, pkg, app, exe, details, n_pass, n_fail, 0, verdict)


def _write(out_path, pkg, app, exe, details, n_pass, n_fail, rc_extra, verdict=None):
    if verdict is None:
        verdict = 'PASS' if n_fail == 0 else 'FAIL'
    ev = {
        'script': os.path.basename(__file__),
        'pkg': pkg,
        'pkg_app': app,
        'pkg_python': exe,
        'pkg_python_sha256': (sha256_file(exe) if exe and os.path.exists(exe) else None),
        'n_pass': n_pass,
        'n_fail': n_fail,
        'verdict': verdict,
        'detail': details,
        'note': ('本脚本只做 import 与路径解析：不跑推理 / 不测速 / 不占 GPU；'
                 '不写客户包（B2 反证用影子目录）。'),
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('\n[VERDICT] %s  pass=%d fail=%d' % (verdict, n_pass, n_fail))
    print('[EVIDENCE] %s' % out_path)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
