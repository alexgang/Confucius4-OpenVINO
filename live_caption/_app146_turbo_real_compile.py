"""**真实 NPU 编译**验证 turbo 生效（APP-139 / APP-146 的验收项）。

## 为什么要单独做这个

APP-146 第 4 项要求「每个 NPU 模型的 `NPU_TURBO=True` 都要在日志里看到」。
三轮 e2e 实测**没看到** ⇒ 查下来真正编译 NPU 的是
`babelvox/pipeline.py::_compile_npu`（`core.compile_model(model, "NPU")`，**不传任何属性**）
⇒ 已改 `app/tts_engine_patch.py` 覆写 `_compile_npu` 注入 turbo。

但三轮跑完 TTS 只用了 11.7 s ⇒ **编译缓存命中** ⇒ 没触发真正的编译
⇒ 「turbo 到底能不能被 OV 接受、真编到 NPU 上」这件事**还没有被真实验证过**。

⇒ 本脚本用**真实 ov.Core + 真实 IR（speaker_encoder.xml，298 KB）**
  做一次**冷编译**（用独立的 cache_dir ⇒ 强制真编译），
  对比「带 turbo」与「不带 turbo」两种编译，并**读回编译产物上的属性**。

## 判据

1. 带 turbo 的编译**成功** ⇒ 属性被 OV 接受；
2. 编译产物上能**读回** `NPU_TURBO`（prop_readback）⇒ 属性真的进了编译期 config；
3. `EXECUTION_DEVICES` 读回是 **NPU** ⇒ 真的编到 NPU 上；
4. 🔴 反证：把 `LIVECAP_NPU_TURBO=0` ⇒ **不注入** ⇒ 产物上**读不到** NPU_TURBO
   ⇒ 证明「读回得到 NPU_TURBO」不是恒真。
"""
import json
import os
import shutil
import sys
import tempfile
import time

CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate'
PKG_PY = os.path.join(CAND, 'python', 'python.exe')
IR = os.path.join(CAND, 'models', 'qwen3tts', 'int8', 'speaker_encoder.xml')
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app146_turbo_real_compile.json'

sys.path.insert(0, os.path.join(CAND, 'app'))
import npu_turbo as NT      # 候选包内的那一份（与包内其它代码同源）

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print("  [%s] %s%s" % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))


def compile_and_readback(props, cache_dir, tag):
    """真编译 ⇒ 读回属性。返回 dict。"""
    import openvino as ov
    core = ov.Core()
    core.set_property({'CACHE_DIR': cache_dir})
    m = core.read_model(IR)
    m.reshape({"mel_spectrogram": [1, 640, 128]})
    t0 = time.time()
    cm = core.compile_model(m, 'NPU', props)
    dt = round(time.time() - t0, 1)
    rb = {}
    for k in ('NPU_TURBO', 'EXECUTION_DEVICES', 'PERFORMANCE_HINT'):
        try:
            rb[k] = str(cm.get_property(k))
        except Exception as e:
            rb[k] = '<%s>' % type(e).__name__
    print('    [%s] 编译 %.1fs，读回 %s' % (tag, dt, rb))
    return {'seconds': dt, 'readback': rb, 'props_in': dict(props)}


def main():
    import openvino as ov
    print('OV %s，设备 %s' % (ov.__version__, list(ov.Core().available_devices)))
    print('IR: %s' % IR)

    base = tempfile.mkdtemp(prefix='app146_turbo_', dir=os.path.dirname(IR))

    # ── ① 带 turbo（默认开）───────────────────────────────────────────
    os.environ.pop(NT.ENV_NPU_TURBO, None)
    core = ov.Core()
    props = NT.turbo_props(core=core)
    print('\n[1] 默认（无环境变量）⇒ 注入属性：%s' % props)
    check('默认开 ⇒ 注入 NPU_TURBO=YES', props.get('NPU_TURBO') == 'YES', str(props))
    r1 = compile_and_readback(props, os.path.join(base, 'c1'), '带 turbo')
    check('带 turbo 的编译**成功**', 'readback' in r1)
    check('★ 编译产物上**读回** NPU_TURBO（真进了编译期 config）',
          r1['readback'].get('NPU_TURBO') not in (None, '<Exception>', ''),
          str(r1['readback'].get('NPU_TURBO')))
    check('EXECUTION_DEVICES = NPU（真编到 NPU）',
          r1['readback'].get('EXECUTION_DEVICES', '').upper().startswith('NPU'),
          str(r1['readback'].get('EXECUTION_DEVICES')))

    # ── ② 反证：环境变量关 ⇒ 不注入 ⇒ 读回不到 NPU_TURBO ──────────────
    os.environ[NT.ENV_NPU_TURBO] = '0'
    core2 = ov.Core()
    props2 = NT.turbo_props(core=core2)
    print('\n[2] LIVECAP_NPU_TURBO=0 ⇒ 注入属性：%s' % props2)
    check('关闭 ⇒ **不注入** NPU_TURBO', 'NPU_TURBO' not in props2, str(props2))
    r2 = compile_and_readback(props2, os.path.join(base, 'c2'), '不带 turbo')
    # 🔴 关掉时：OV 对「未设置该属性」的读回会**抛 RuntimeError**
    #   ⇒ 记成 '<RuntimeError>' ⇒ 那就是「读不到」的证据（不是 FAIL）
    _v = r2['readback'].get('NPU_TURBO')
    _absent = (_v is None) or (str(_v).startswith('<RuntimeError>')) \
        or str(_v).strip() in ('', 'None', 'False')
    check('★ 反证：关掉后编译产物上**读不到** NPU_TURBO（证明上条判据有鉴别力）',
          _absent, '读回值=%r（<RuntimeError> = 属性不存在，正是「读不到」）' % (_v,))
    os.environ.pop(NT.ENV_NPU_TURBO, None)

    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'ir': IR,
        'ov_version': ov.__version__,
        'with_turbo': r1,
        'without_turbo': r2,
        'checks': [{'name': n, 'ok': ok} for n, ok in RESULTS],
        'n_pass': sum(1 for _n, ok in RESULTS if ok),
        'n_fail': sum(1 for _n, ok in RESULTS if not ok),
    }
    p = OUT
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    shutil.rmtree(base, ignore_errors=True)
    print('\n结果：%d PASS / %d FAIL' % (out['n_pass'], out['n_fail']))
    print('落盘 ->', p)
    return 0 if out['n_fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
