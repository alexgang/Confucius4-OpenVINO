"""c066_npu_stage0.py — C-066/C-067/C-068 阶段 0：NPU 环境与算子支持探测

只读探测，**不改驱动、不改系统安全设置、不用 torch**（C-066 铁律）。

做四件事：
  1. `core.available_devices` 是否含 NPU；记录 FULL_DEVICE_NAME /
     DEVICE_ARCHITECTURE / 驱动版本 / tiles / 内存。
  2. 对编码器 IR 与解码器 IR 各做一次 `core.query_model(model, "NPU")`，
     列出 NPU 不支持的算子（重点核对 reviewer 预筛里的 SDPA 带掩码 与 MVN）。
  3. 检查已装 `openvino-genai` 版本及 NPU 相关能力。
  4. C-068：在 openvino / openvino_genai 包里搜 `qwen3_asr` / `QWEN3_ASR`；
     列 `SUPPORTED_PROPERTIES` 看是否含 `NPUW_QWEN3_ASR_MAX_ENCODER_LEN`。

用法：.venv python c066_npu_stage0.py
输出：reports/c066_npu_stage0.json
"""
import json
import os
import re
import subprocess
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import openvino as ov

# ⚠️ 必须指到具体的 `.xml`。传目录名时 OV 会先按 TF SavedModel 解析，
# 报 `Could not open the file: "...\\saved_model.pb"`。
# 注意 `ov-int4-lmhead-past` 目录里也有一份 `openvino_encoder_model.xml`
# （导出时误留的 FP16 encoder 拷贝），所以解码器要显式写 `openvino_decoder_model.xml`。
ENCODER = 'models/ov-encoder-segment-reviewer/openvino_encoder_model.xml'
DECODERS = {
    'decoder_INT8': 'models/ov-int8-past/openvino_decoder_model.xml',
    'decoder_INT4_full': 'models/ov-int4-lmhead-past/openvino_decoder_model.xml',
}
INT4_ENCODER = ('models/ov-encoder-segment-reviewer-int4/'
                'openvino_encoder_model.xml')
OUT = 'reports/c066_npu_stage0.json'


def probe_device(core):
    info = {'available_devices': core.available_devices,
            'has_NPU': 'NPU' in core.available_devices}
    for d in core.available_devices:
        rec = {}
        for prop in ('FULL_DEVICE_NAME', 'DEVICE_ARCHITECTURE', 'DEVICE_TYPE',
                     'NPU_DRIVER_VERSION', 'NPU_COMPILER_VERSION',
                     'NPU_MAX_TILES', 'NPU_DEVICE_TOTAL_MEM_SIZE',
                     'OPTIMIZATION_CAPABILITIES'):
            try:
                rec[prop] = str(core.get_property(d, prop))
            except Exception:
                rec[prop] = None
        info.setdefault('devices', {})[d] = rec

    # C-068#2：主线是否有 Qwen3-ASR NPU 专用属性
    try:
        sp = core.get_property('NPU', 'SUPPORTED_PROPERTIES')
        sp_list = sorted(sp.keys())
        info['supported_properties'] = sp_list
        info['qwen3_related_props'] = [
            k for k in sp_list
            if 'QWEN' in k.upper() or 'ASR' in k.upper()]
        info['npuw_related_props'] = [
            k for k in sp_list if 'NPUW' in k.upper()]
        info['has_QWEN3_ASR_prop'] = bool(info['qwen3_related_props'])
        info['cache_dir_writable'] = 'CACHE_DIR' in sp
    except Exception as e:
        info['supported_properties_error'] = str(e)[:300]
    return info


def set_log_quiet(core):
    """OpenVINO 2026.4 没有顶层 `ov.set_log_level`；日志级别是普通 property。"""
    from openvino import properties as p
    try:
        core.set_property({'LOG_LEVEL': p.log.Level.ERROR})
    except Exception:
        try:
            core.set_property('LOG_LEVEL', 'ERROR')
        except Exception:
            pass


def query(core, model_path, label):
    """对单个 IR 做 query_model。

    ⚠️ 2026.4.1 的 `Core.query_model(model, device)` 返回的是
    **`dict{参数名: 设备名}`**（不是老文档里的 `(supported, unsupported)` 二元组）。
    它回答的是「每个参数会被放到哪个设备」，不直接给算子支持表。

    所以这里做两件事：
      1. 记下 dict 的统计（多少参数留在 CPU / 落到 NPU）—— 这本身很有信息量：
         如果大量参数留在 CPU，说明该算子集在 NPU 上不受支持，编译会回退。
      2. 再跑一次**真实 `compile_model`**，把报错全文记下来 ——
         那才是 C-066 阶段 1/3 真正会遇到的失败原因。
    """
    print(f'\n[c066] query_model({label}, "NPU") ...', flush=True)
    rec = {'model': model_path}
    try:
        model = core.read_model(model_path)
    except Exception as e:
        rec['read_error'] = str(e)[:500]
        return rec
    rec['n_ops'] = len(model.get_ops())
    try:
        rec['param_count'] = len(model.get_parameters())
        rec['param_types'] = sorted(
            {str(p_.get_element_type()) for p_ in model.get_parameters()})
    except Exception:
        pass

    # ---- 1) query_model：参数 -> 设备 ----
    try:
        assign = core.query_model(model, 'NPU')
        rec['query_return_type'] = type(assign).__name__
        if isinstance(assign, dict):
            devs = {}
            for k, v in assign.items():
                devs[str(v)] = devs.get(str(v), 0) + 1
            rec['param_device_hist'] = devs
            rec['n_params_on_npu'] = sum(
                n for d, n in devs.items() if 'NPU' in d)
            off = {k: v for k, v in list(assign.items())
                   if 'NPU' not in str(v)}
            rec['n_params_not_on_npu'] = len(off)
            rec['sample_params_not_on_npu'] = dict(
                list(off.items())[:15])
        else:
            rec['query_raw'] = str(assign)[:2000]
    except Exception as e:
        rec['query_error'] = str(e)[:2000]

    # ---- 2) 真实编译：算子级失败原因在这里 ----
    # C-066：打开 CACHE_DIR（NPU 首次编译可能要几分钟，且会写缓存）。
    print(f'[c066] compile_model({label}, "NPU") ...', flush=True)
    cache = os.path.abspath(os.path.join('reports', 'npu_cache'))
    os.makedirs(cache, exist_ok=True)
    try:
        cm = core.compile_model(model, 'NPU', {'CACHE_DIR': cache})
        rec['compile'] = 'OK'
        rec['cache_dir'] = cache
        try:
            rec['compiled_devices'] = str(cm.get_devices_with_config())
        except Exception:
            pass
    except Exception as e:
        rec['compile'] = 'FAILED'
        rec['compile_error'] = str(e)[:4000]
    return rec


def check_genai():
    """C-067#3：已装 openvino-genai 的版本与 NPU 能力。"""
    rec = {}
    try:
        import openvino_genai as ovg
        rec['version'] = getattr(ovg, '__version__', 'unknown')
        rec['path'] = getattr(ovg, '__file__', '')
        rec['has_LLM_pipeline'] = hasattr(ovg, 'LLMPipeline')
        rec['has_Pipeline'] = hasattr(ovg, 'Pipeline')
        rec['has_Speech2TextPipeline'] = hasattr(ovg, 'Speech2TextPipeline')
    except Exception as e:
        rec['error'] = str(e)[:200]
    return rec


def search_qwen3_asr():
    """C-068#1：在已装包里搜 qwen3_asr / QWEN3_ASR（含 dll/pyd）。"""
    import glob
    roots = []
    try:
        import openvino as o
        roots.append(os.path.dirname(os.path.dirname(o.__file__)))
    except Exception:
        pass
    try:
        import openvino_genai as g
        roots.append(os.path.dirname(os.path.dirname(g.__file__)))
    except Exception:
        pass

    pat = re.compile(rb'qwen3_asr|QWEN3_ASR|Qwen3ASR', re.I)
    hits, scanned = [], 0
    for root in set(roots):
        for ext in ('*.py', '*.pyd', '*.dll', '*.xml', '*.json'):
            for p in glob.glob(os.path.join(root, '**', ext),
                               recursive=True):
                    # 跳过巨大的模型权重目录
                    if 'model' in p.lower() and p.lower().endswith(('.bin',)):
                        continue
                    try:
                        if os.path.getsize(p) > 400 * 1024 * 1024:
                            continue
                        with open(p, 'rb') as f:
                            data = f.read()
                        scanned += 1
                        if pat.search(data):
                            hits.append(p)
                    except Exception:
                        continue
    return {'roots': sorted(set(roots)), 'files_scanned': scanned,
            'hits': sorted(set(hits))}


def main():
    core = ov.Core()
    set_log_quiet(core)

    out = {'openvino_version': ov.__version__,
           'stage': 'C-066/C-067/C-068 阶段 0（只读探测）',
           'device': probe_device(core),
           'models': {}}

    out['models']['encoder_FP16'] = query(core, ENCODER, 'encoder_FP16')
    out['models']['encoder_INT4'] = query(core, INT4_ENCODER, 'encoder_INT4')
    for name, path in DECODERS.items():
        out['models'][name] = query(core, path, name)

    out['openvino_genai'] = check_genai()
    print('\n[c066] 搜 qwen3_asr / QWEN3_ASR ...', flush=True)
    out['qwen3_asr_search'] = search_qwen3_asr()

    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('\n' + '=' * 70)
    d = out['device']
    print(f"NPU 可用: {d['has_NPU']}   devices={d['available_devices']}")
    n = d['devices'].get('NPU', {})
    print(f"  FULL_DEVICE_NAME     = {n.get('FULL_DEVICE_NAME')}")
    print(f"  DEVICE_ARCHITECTURE  = {n.get('DEVICE_ARCHITECTURE')}")
    print(f"  NPU_DRIVER_VERSION   = {n.get('NPU_DRIVER_VERSION')}")
    print(f"  NPU_COMPILER_VERSION = {n.get('NPU_COMPILER_VERSION')}")
    print(f"  NPU_MAX_TILES        = {n.get('NPU_MAX_TILES')}")
    print(f"  设备内存             = "
          f"{int(n.get('NPU_DEVICE_TOTAL_MEM_SIZE') or 0)/2**30:.1f} GiB")
    print(f"  OPTIMIZATION_CAPS    = {n.get('OPTIMIZATION_CAPABILITIES')}")
    print(f"  CACHE_DIR 可写       = {d.get('cache_dir_writable')}")
    print(f"  Qwen3-ASR 专用属性   = {d.get('qwen3_related_props') or '无'}")
    print(f"  NPUW 相关属性        = {d.get('npuw_related_props') or '无'}")
    print('-' * 70)
    for k, v in out['models'].items():
        print(f"{k}: ops={v.get('n_ops')} params={v.get('param_count')}")
        if 'param_device_hist' in v:
            print(f"   参数落点: {v['param_device_hist']}")
            print(f"   在 NPU 上={v.get('n_params_on_npu')} "
                  f"不在 NPU 上={v.get('n_params_not_on_npu')}")
            if v.get('sample_params_not_on_npu'):
                print(f"   不在 NPU 的样例: "
                      f"{list(v['sample_params_not_on_npu'].items())[:5]}")
        print(f"   compile_model -> {v.get('compile')}")
        if v.get('compile_error'):
            print(f"   compile_error: {v['compile_error'][:600]}")
        if v.get('query_error'):
            print(f"   query_error: {v['query_error'][:300]}")
    print('-' * 70)
    print(f"openvino-genai: {out['openvino_genai']}")
    s = out['qwen3_asr_search']
    print(f"qwen3_asr 搜索: 扫 {s['files_scanned']} 个文件, 命中 {len(s['hits'])}")
    for h in s['hits'][:10]:
        print(f"   HIT {h}")
    print(f"\nsaved -> {OUT}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
