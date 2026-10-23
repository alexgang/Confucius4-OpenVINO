#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_tts_deploy.py —— 回答 APP-001/§4.4 待确认项②：

**Qwen3-TTS 在客户包（v1.3）里到底能不能跑？跑起来要多大的体积？**

## 为什么需要这个脚本
客户包 `Confucius4_LiveCaption_v1.3` 自带 Python 3.12.10 + 一套 site-packages。
Qwen3-TTS 走 PyPI `babelvox` 1.7.1，它的依赖声明与客户包现状**对不上**：

| 依赖 | babelvox 声明 | 客户包现状 | 结论 |
|---|---|---|---|
| transformers | `>=5.0` | **4.57.6** | ⚠️ 版本号不满足，但实际能否用要实测 |
| huggingface_hub | `>=1.0` | **0.36.2** | ⚠️ 同上 |
| numpy | `>=2.0` | 2.4.6 | ✅ |
| openvino | `>=2025.4` | 2026.4.1 | ✅ |
| scipy / librosa / num2words / defusedxml | 必需 | **全缺** | ❌ 需新增 |

本脚本**不修改客户包**，全部装到临时 `--target` 目录，用 `PYTHONPATH` 叠加验证。

## 用法
```
# 1) 装依赖到临时 target（不碰客户包）
"C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.3/python/python.exe" \
    -m pip install --target <TMP>/target babelvox==1.7.1 librosa scipy num2words defusedxml

# 2) 跑本脚本
python verify_tts_deploy.py --target <TMP>/target \
    --export-dir <HF>/models--djwarf--babelvox-openvino-int8/snapshots/<hash>
```

## 结论口径
本脚本只回答**功能可行性 + 体积**，**不报性能**（APP-001 铁律：
不在 CPU 上跑推理或测速，CPU 只用于单组件诊断）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
DEFAULT_PKG_PY = os.path.join(DEFAULT_PKG, 'python', 'python.exe')


def _du_mb(path: str) -> float:
    """目录体积（MB）。跨平台够用即可。"""
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return round(total / 1048576.0, 1)


def check_env(pkg_py: str) -> dict:
    """客户包原生环境（无任何改动）的版本快照。"""
    code = (
        "import importlib.metadata as md\n"
        "out={}\n"
        "for p in ['transformers','numpy','huggingface_hub','openvino','openvino_genai']:\n"
        "    try: out[p]=md.version(p)\n"
        "    except Exception: out[p]=None\n"
        "print(json.dumps(out, ensure_ascii=False))\n"
    ).replace('json.dumps', '__import__("json").dumps')
    r = subprocess.run([pkg_py, '-c', code], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {'_error': r.stderr[-500:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--target', required=True,
                    help='pip --target 目录（babelvox + 依赖装在这里）')
    ap.add_argument('--export-dir', required=True,
                    help='babelvox IR 本地目录（HF snapshot，含 int8/ 与 weights/）')
    ap.add_argument('--out', default=os.path.join(HERE, 'results', 'tts_deploy_verify.json'))
    ap.add_argument('--skip-synth', action='store_true',
                    help='只做 import 检查，不加载 IR 合成（更省时间）')
    args = ap.parse_args()

    pkg_py = os.path.join(args.pkg, 'python', 'python.exe')
    if not os.path.isfile(pkg_py):
        print(f'[FAIL] 找不到客户包 python：{pkg_py}')
        return 2

    report: dict = {
        'pkg': args.pkg,
        'pkg_py': pkg_py,
        'target': args.target,
        'export_dir': args.export_dir,
        'checked_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    # ── 1. 客户包原生环境 ──────────────────────────────────────
    print('[1/5] 客户包原生环境版本快照 ...')
    report['pkg_native_versions'] = check_env(pkg_py)
    print('      ', report['pkg_native_versions'])

    # ── 2. target 体积 ─────────────────────────────────────────
    print('[2/5] 统计 target 体积 ...')
    report['target_mb'] = _du_mb(args.target)
    big = []
    if os.path.isdir(args.target):
        for d in sorted(os.listdir(args.target)):
            p = os.path.join(args.target, d)
            if os.path.isdir(p):
                mb = _du_mb(p)
                if mb >= 1:
                    big.append((mb, d))
    report['target_top'] = [{'mb': mb, 'name': n} for mb, n in sorted(big, reverse=True)[:12]]

    # ── 3. IR 体积 ─────────────────────────────────────────────
    print('[3/5] 统计 IR 体积 ...')
    ir = {}
    for sub in ('int8', 'weights'):
        p = os.path.join(args.export_dir, sub)
        if os.path.isdir(p):
            ir[sub] = _du_mb(p)
    report['ir_mb'] = ir
    report['ir_mb']['total'] = round(sum(ir.values()), 1)

    # ── 4. import + 合成 ───────────────────────────────────────
    env = dict(os.environ)
    env['PYTHONPATH'] = args.target
    env['HF_HUB_OFFLINE'] = '1'
    code = r'''
import os, json, time, sys
os.environ["HF_HUB_OFFLINE"] = "1"
r = {"numpy": None, "transformers": None}
try:
    import numpy; r["numpy"] = numpy.__version__
except Exception as e:
    r["_err_numpy"] = repr(e)
try:
    import transformers; r["transformers"] = transformers.__version__
except Exception as e:
    r["_err_transformers"] = repr(e)
try:
    from babelvox.pipeline import BabelVox
    r["import_babelvox"] = "OK"
except Exception as e:
    r["import_babelvox"] = type(e).__name__ + ": " + str(e)
    print(json.dumps(r, ensure_ascii=False)); sys.exit(0)
try:
    t0 = time.time()
    tts = BabelVox(model_path="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
                   export_dir=EXPORT_DIR, device="CPU", precision="int8",
                   cache_dir=CACHE_DIR)
    r["load_s"] = round(time.time() - t0, 1)
    r["load_ok"] = True
except Exception as e:
    import traceback
    r["load_ok"] = False
    r["load_err"] = traceback.format_exc()[-800:]
    print(json.dumps(r, ensure_ascii=False)); sys.exit(0)
try:
    t0 = time.time()
    chunks = []
    for wav, sr in tts.generate_stream(TEXT, language="Chinese", chunk_frames=12):
        chunks.append((len(wav), sr))
    r["stream_chunks"] = len(chunks)
    r["stream_chunk_sizes"] = [c[0] for c in chunks]
    r["stream_sr"] = chunks[0][1] if chunks else None
    r["stream_total_s"] = round(sum(c[0] for c in chunks) / 24000.0, 2) if chunks else None
    r["stream_s"] = round(time.time() - t0, 1)
except Exception as e:
    import traceback
    r["stream_err"] = traceback.format_exc()[-800:]
print(json.dumps(r, ensure_ascii=False))
'''
    # ⚠️ 参数注入**必须用 json.dumps**（不能用 repr）——
    #    repr() 对含中文/引号的字符串会产出不可解析的 Python 字面量。
    code = (code.replace('EXPORT_DIR', json.dumps(args.export_dir))
                .replace('CACHE_DIR', json.dumps(os.path.join(args.target, '_ov_cache')))
                .replace('TEXT', json.dumps('这是一句部署验证测试。', ensure_ascii=False)))

    print('[4/5] import + 端到端合成（CPU，仅验功能，不报性能）...')
    r = subprocess.run([pkg_py, '-c', code], capture_output=True, text=True,
                       env=env)
    payload = {}
    # ⚠️ stdout 里 JSON **不一定在最后一行**（前面有 transformers 的警告行），
    #    而且多行 JSON 会各自以 '{' 开头 ⇒ 要逐行试解，取**能成功解出且含已知键**的那条。
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith('{'):
            continue
        try:
            cand = json.loads(line)
        except Exception:
            continue
        if isinstance(cand, dict) and ('import_babelvox' in cand or 'numpy' in cand):
            payload = cand
    report['runtime'] = payload
    report['runtime_stdout_tail'] = r.stdout.strip().splitlines()[-12:]
    if r.returncode != 0 and not payload:
        report['runtime_stderr'] = r.stderr[-1200:]
    print('      import_babelvox =', payload.get('import_babelvox'))
    print('      load_ok =', payload.get('load_ok'),
          '| stream_chunks =', payload.get('stream_chunks'),
          '| sr =', payload.get('stream_sr'))

    # ── 5. 现有链路兼容性（numpy 被顶高后）────────────────────
    print('[5/5] 现有 app 模块在叠加 target 后能否 import ...')
    app_dir = os.path.join(args.pkg, 'app')
    compat = {}
    if os.path.isdir(app_dir):
        code2 = (
            "import sys; sys.path.insert(0, APPDIR)\n"
            "import numpy; print('numpy', numpy.__version__)\n"
            "for m in MODS:\n"
            "    try:\n"
            "        __import__(m); print('OK', m)\n"
            "    except Exception as e:\n"
            "        print('FAIL', m, type(e).__name__, e)\n"
        ).replace('APPDIR', repr(app_dir)).replace(
            'MODS', repr(['audio_source', 'seg_stream', 'segment_encoder_backend',
                          'npu_delivery_backend', 'npu_embeds_backend',
                          'translator', 'backends']))
        r2 = subprocess.run([pkg_py, '-c', code2], capture_output=True, text=True,
                            env=env, cwd=app_dir)
        compat['stdout'] = r2.stdout.strip().splitlines()
        compat['returncode'] = r2.returncode
        report['app_compat'] = compat
        print('      ', compat.get('stdout'))

    # ── 落盘 ───────────────────────────────────────────────────
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'\n[OK] 报告已写入 {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
