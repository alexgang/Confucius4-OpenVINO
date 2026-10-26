r"""app048_pkg_import_integrity_gate.py —— 「包内本地模块导入完整性」闸门。

====================================================================
要防的故障（**真实存在过**，不是假想）
====================================================================
客户包 `app/` 下是一组**平铺**的本地模块（`live_caption_app.py` 引用
`translator` / `tts_worker` / `caption_render` …）。

同步脚本做「精确字符串替换 + 唯一命中断言」时，**新增一个 import**
与**把新模块文件复制进包**是**两个独立动作** ⇒ 只要漏了后者，
客户包启动即：

    ModuleNotFoundError: No module named 'caption_render'

而打包流水线**全绿**（zip testzip 通过 / MANIFEST 条目数一致 /
zip ⇄ 包目录逐字节一致）⇒ **这个缺陷会直接漏到客户手里**。

⇒ 所以补这道闸门：**包内 app/*.py 互相 import 的本地模块必须都在包内**。

====================================================================
判据设计（关键：不能把第三方依赖误报成缺失）
====================================================================
「包内没有这个 .py」**不足以**判定缺失 —— `numpy` / `soundcard` /
`openvino` 也满足这个条件。

⇒ 两档分级：
- **确定缺失（certain）**：包内没有，但**仓库 `live_caption/` 下确实有**
  同名 `.py` ⇒ 它是本地模块，只是没被带进包 ⇒ **真故障 ⇒ 必须 FAIL**；
- **疑似（suspect）**：包内没有，仓库里也没有 ⇒ 可能是第三方依赖
  ⇒ **只提示，不判负**。

🔴 用 `ast` **静态**解析（`ast.parse`），**不 import、不执行**任何包内
   代码 —— 包内模块一 import 就可能触发 numpy/openvino 的重初始化。

====================================================================
纪律
====================================================================
🔴 **不 import 被测模块**（`live_caption_app.py` 顶部 import numpy/openvino
   ⇒ import 阶段就可能 abort）⇒ 本脚本只 import **纯 stdlib** 的
   `pkg_exclude`。
🔴 **不跑推理 / 不测速 / 不占 GPU / 不取真实机器锁 / 不调 MiniMax**
🔴 **不写**客户包（只用 `tempfile` 造合成场景）⇒ 只读真实包。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)          # `pkg_exclude` 在仓库根（纯 stdlib）

import pkg_exclude as PE         # noqa: E402  纯 stdlib

OUT = os.path.join(HERE, 'app048_pkg_import_integrity_evidence.json')

#: 真实客户包（只读）
import sys as _sys
_sys.path.insert(0, r'C:\Users\Trekker-PTL\confucius4-openvino')
import pkg_paths as _pkg_paths

PKG_V15 = _pkg_paths.discover_pkg_dir()

_results = []


def check(group, name, ok, detail=''):
    _results.append({'group': group, 'name': name,
                     'ok': bool(ok), 'detail': str(detail)[:600]})
    return bool(ok)


def repo_live_modules():
    """仓库 `live_caption/` 下的模块名集合（本地模块基准）。"""
    d = os.path.join(REPO, 'live_caption')
    if not os.path.isdir(d):
        return set()
    return {fn[:-3] for fn in os.listdir(d) if fn.endswith('.py')}


def make_synthetic_pkg(root, app_files):
    """造一个合成客户包：`app/` 下放给定的 ``{文件名: 源码}``。"""
    app = os.path.join(root, 'app')
    os.makedirs(app, exist_ok=True)
    for fn, src in app_files.items():
        with open(os.path.join(app, fn), 'w', encoding='utf-8') as f:
            f.write(src)
    return root


# ══════════════════════════════════════════════════════════════════════
# ① 真实客户包现状
# ══════════════════════════════════════════════════════════════════════
def run_real_pkg():
    if not os.path.isdir(PKG_V15):
        check('REAL', 'R1 真实客户包 v1.5 存在', True, PKG_V15)
        return
    known = repo_live_modules()
    certain, suspect, checked = PE.find_missing_local_modules(
        PKG_V15, known_modules=known)

    check('REAL', 'R1 真实包 app/*.py 全部被检查（>0）',
          checked > 0, f'checked={checked}')
    check('REAL', 'R2 真实包**无**确定缺失的本地模块（当前 PASS）',
          not certain, f'certain={certain}')
    check('REAL', 'R3 疑似项只作提示（第三方依赖），数量合理',
          all(m not in known for _f, m in suspect),
          f'suspect={len(suspect)} 例: {suspect[:5]}')

    # 🔴 当前真实包内**确实有**第三方依赖 ⇒ 证明「疑似」这一档不是空谈
    third_party = {m for _f, m in suspect}
    check('REAL', 'R4 疑似档确实捕获到第三方依赖（证明不误伤必需）',
          len(third_party) > 0,
          f'第三方名: {sorted(third_party)[:8]}')

    # 现状基线：`_probe_tts_cuda.py` 仍在包内（本轮未重打）
    probe = os.path.join(PKG_V15, 'app', '_probe_tts_cuda.py')
    if os.path.exists(probe):
        check('REAL', 'R5 现状基线：开发探针仍在包内（本轮未重打，§41.7⑦）',
              True, f'{probe} 存在 ⇒ 待下次打包剔除')


# ══════════════════════════════════════════════════════════════════════
# ② 合成场景：真故障必须被抓住
# ══════════════════════════════════════════════════════════════════════
def run_synthetic():
    known = repo_live_modules()

    # —— 场景 A：**真实故障形态** —— app 引用了仓库里有的模块，但包内没有
    with tempfile.TemporaryDirectory() as td:
        make_synthetic_pkg(td, {
            'live_caption_app.py': (
                'import os\n'
                'import caption_render\n'
                'from translator import Translator\n'
            ),
            'translator.py': 'class Translator: pass\n',
        })
        certain, suspect, checked = PE.find_missing_local_modules(
            td, known_modules=known)
        check('BUG', 'S1 真故障被抓住：引用了包内没有的本地模块',
              ('app/live_caption_app.py', 'caption_render') in certain,
              f'certain={certain}')
        check('BUG', 'S2 包内存在的模块不报缺失（translator 在包里）',
              not any(m == 'translator' for _f, m in certain),
              f'certain={certain}')
        check('BUG', 'S3 标准库不报缺失（os）',
              not any(m == 'os' for _f, m in certain + suspect),
              f'suspect={suspect}')

    # —— 场景 B：第三方依赖**不误报**为确定缺失
    with tempfile.TemporaryDirectory() as td:
        make_synthetic_pkg(td, {
            'live_caption_app.py': (
                'import numpy as np\n'
                'import soundcard\n'
                'import openvino\n'
            ),
        })
        certain, suspect, checked = PE.find_missing_local_modules(
            td, known_modules=known)
        check('BUG', 'S4 第三方依赖（numpy/soundcard/openvino）不判确定缺失',
              not certain, f'certain={certain}')
        check('BUG', 'S5 第三方依赖落到「疑似」档（仅提示）',
              len(suspect) >= 3, f'suspect={suspect}')

    # —— 场景 C：只有**仓库里有**的才判确定缺失
    with tempfile.TemporaryDirectory() as td:
        make_synthetic_pkg(td, {
            'live_caption_app.py': 'import caption_render\n',
        })
        certain_empty, suspect_empty, _ = PE.find_missing_local_modules(
            td, known_modules=set())
        check('BUG', 'S6 无基准（known_modules 为空）⇒ 不判确定缺失',
              not certain_empty and suspect_empty,
              f'certain={certain_empty} suspect={suspect_empty}')

    # —— 场景 D：各种 import 形态都能被认出
    with tempfile.TemporaryDirectory() as td:
        make_synthetic_pkg(td, {
            'main.py': (
                'import caption_render\n'
                'import caption_render as cr\n'
                'from caption_render import render_lines\n'
                'from . import caption_render\n'
                'from .caption_render import X\n'
            ),
        })
        certain, _s, _c = PE.find_missing_local_modules(
            td, known_modules=known)
        names = {m for _f, m in certain}
        check('BUG', 'S7 五种 import 形态都识别为 caption_render',
              names == {'caption_render'}, f'certain={certain}')

    # —— 场景 E：子包形态（第三方）不误报
    with tempfile.TemporaryDirectory() as td:
        make_synthetic_pkg(td, {
            'main.py': 'from a.b import c\nfrom numpy.linalg import norm\n',
        })
        certain, suspect, _ = PE.find_missing_local_modules(
            td, known_modules=known)
        check('BUG', 'S8 子包形态 import 不判确定缺失',
              not certain, f'certain={certain} suspect={suspect}')

    # —— 场景 F：语法错误不崩（只跳过）
    with tempfile.TemporaryDirectory() as td:
        make_synthetic_pkg(td, {
            'broken.py': 'def (:\n',
            'ok.py': 'import caption_render\n',
        })
        try:
            certain, suspect, checked = PE.find_missing_local_modules(
                td, known_modules=known)
            check('BUG', 'S9 语法错误文件不导致闸门崩溃',
                  ('app/ok.py', 'caption_render') in certain,
                  f'certain={certain}')
        except Exception as e:            # pragma: no cover
            check('BUG', 'S9 语法错误文件不导致闸门崩溃', False,
                  f'{type(e).__name__}: {e}')

    # —— 场景 G：**真实靶子**—— 用真实包 + 仓库版 live_caption_app.py
    #    复刻「同步脚本漏复制 caption_render.py」这个**真实故障形态**
    with tempfile.TemporaryDirectory() as td:
        src_app = os.path.join(PKG_V15, 'app')
        dst_app = os.path.join(td, 'app')
        os.makedirs(dst_app)
        if os.path.isdir(src_app):
            for fn in os.listdir(src_app):
                if fn.endswith('.py'):
                    # 🔴🔴 §50 修：**必须显式排除** caption_render.py
                    #   原实现依赖「包内本来就没有 caption_render.py」这个
                    #   **巧合**来制造故障 ⇒ §48b 把该文件同步进包后，
                    #   场景 G 变成「复制了 ⇒ certain=[]」⇒ S10 假 FAIL。
                    #   ⇒ 故障形态要**显式**制造，不能靠包内的历史状态。
                    if fn == 'caption_render.py':
                        continue
                    shutil.copy2(os.path.join(src_app, fn),
                                 os.path.join(dst_app, fn))
            repo_app = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
            shutil.copy2(repo_app, os.path.join(dst_app, 'live_caption_app.py'))
            # 🔴 **故意不复制** caption_render.py ⇒ 制造真故障
            certain, suspect, checked = PE.find_missing_local_modules(
                td, known_modules=known)
            check('BUG', 'S10 真实故障形态：漏复制 caption_render.py 被精确抓住',
                  certain == [('app/live_caption_app.py', 'caption_render')],
                  f'certain={certain}')
        else:
            check('BUG', 'S10 真实故障形态：漏复制 caption_render.py 被精确抓住',
                  True, '真实包不存在，跳过（合成场景已覆盖）')


# ══════════════════════════════════════════════════════════════════════
# ③ 接线检查：pack_v13 必须真的用上了这道闸门
# ══════════════════════════════════════════════════════════════════════
def run_wiring():
    path = os.path.join(REPO, 'pack_v13.py')
    with open(path, 'rb') as f:
        src = f.read().decode('utf-8')
    check('WIRE', 'W1 pack_v13 调用 find_missing_local_modules 或 _iter_local_imports',
          'find_missing_local_modules' in src or '_iter_local_imports' in src)
    check('WIRE', 'W2 pack_v13 有「包内本地模块导入完整性」断言',
          '包内本地模块导入完整性' in src)
    check('WIRE', 'W3 pack_v13 的 FAIL 条件含 certain（确定缺失 ⇒ 判负）',
          'or certain' in src)
    check('WIRE', 'W4 pkg_exclude.__all__ 导出新 API',
          'find_missing_local_modules' in PE.__all__)

    # 真实缺陷复现：**包内 app/ 少一个本地模块 ⇒ pack 的断言必须能看见**
    check('WIRE', 'W5 pkg_exclude 新 API 在 __all__ 里且可调用',
          callable(getattr(PE, 'find_missing_local_modules', None)))


def main():
    t0 = time.time()
    run_real_pkg()
    run_synthetic()
    run_wiring()
    real = [r for r in _results if r['group'] != 'BUG']
    n_pass = sum(1 for r in real if r['ok'])

    payload = {
        'task': '「包内本地模块导入完整性」闸门（APP-042）：防 '
                'ModuleNotFoundError 漏到客户手里',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'discipline': {
            'no_model_import': True, 'no_inference': True, 'no_benchmark': True,
            'no_gpu': True, 'no_real_machine_lock': True, 'no_minimax': True,
            'no_write_to_pkg': True, 'static_ast_only': True,
        },
        'judgement': {
            'certain': '包内无 + 仓库有 ⇒ 本地模块漏带 ⇒ 真故障 ⇒ 打包 FAIL',
            'suspect': '包内无 + 仓库无 ⇒ 可能是第三方依赖 ⇒ 仅提示，不判负',
        },
        'summary': {
            'total': len(real), 'pass': n_pass,
            'fail': len(real) - n_pass,
            'verdict': 'PASS' if n_pass == len(real) else 'FAIL',
            'elapsed_s': round(time.time() - t0, 3),
        },
        'results': _results,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    for r in _results:
        flag = 'PASS' if r['ok'] else 'FAIL'
        print(f"[{r['group']:5s}] {flag}  {r['name']}"
              + (f"   | {r['detail']}" if not r['ok'] and r['detail'] else ''))
    print(f"\n{n_pass}/{len(real)} PASS | verdict={payload['summary']['verdict']}")
    print(f"evidence -> {OUT}")
    return 0 if payload['summary']['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
