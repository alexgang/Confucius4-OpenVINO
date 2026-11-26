"""行为级真跑：用**真实 ov.Core** 验证 `npu_turbo` 的实际行为（APP-139）。

判据不是「静态看代码」，而是**真跑**：
1. 真实 Core 上 `resolve_npu_turbo()` ⇒ 期望 actual=True 且注入 NPU_TURBO；
2. `LIVECAP_NPU_TURBO=0` ⇒ 期望 actual=False 且不注入；
3. ★ **反证**：把真 Core 换成一个「NPU 不在设备表」的假 Core
   ⇒ 必须退回（actual=False、不注入）⇒ 判据有鉴别力；
4. ★ **反证**：把真 Core 换成一个「属性表里没有 NPU_TURBO」的假 Core
   ⇒ 必须退回；
5. 实测本机 NPU 的 `SUPPORTED_PROPERTIES` 里到底有没有 `NPU_TURBO`
   ⇒ **如实登记**（若没有 ⇒ 报告「本机不支持」而不是「已开」）。
"""
import io, json, os, sys, time

HERE = r'C:\Users\Trekker-PTL\confucius4-openvino\live_caption'
sys.path.insert(0, HERE)

import npu_turbo as NT

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print("  [%s] %s%s" % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))


class FakeNoNpu:
    def available_devices(self):
        return ['CPU', 'GPU.0']

    def get_property(self, device, prop):
        return ['NPU_TURBO', 'CACHE_DIR']


class FakeNoTurboProp:
    def available_devices(self):
        return ['CPU', 'NPU']

    def get_property(self, device, prop):
        return ['CACHE_DIR', 'PERFORMANCE_HINT']


def main():
    import openvino as ov
    core = ov.Core()
    devs = list(core.available_devices)
    print('\n[0] 实测环境：OV %s，设备 %s' % (ov.__version__, devs))

    # ① 真实 Core：属性表里有没有 NPU_TURBO
    has_turbo_prop = False
    try:
        sp = core.get_property('NPU', 'SUPPORTED_PROPERTIES')
        has_turbo_prop = 'NPU_TURBO' in list(sp)
        print('    NPU SUPPORTED_PROPERTIES：%d 项，NPU_TURBO 在内 = %s'
              % (len(list(sp)), has_turbo_prop))
    except Exception as e:
        print('    NPU 属性表读取失败：%s' % type(e).__name__)
    check('本机 NPU 存在', any(str(d).upper().startswith('NPU') for d in devs), str(devs))

    # ② 真实 Core ⇒ 默认开
    old = os.environ.pop(NT.ENV_NPU_TURBO, None)
    try:
        props, actual, reason = NT.resolve_npu_turbo(core=core)
        print('    真实判定：actual=%s reason=%s props=%s' % (actual, reason, props))
        if has_turbo_prop:
            check('真实 Core：默认开 ⇒ actual=True', actual is True, str(actual))
            check('真实 Core：注入了 NPU_TURBO=YES',
                  props.get(NT.NPU_TURBO_PROP) == NT.NPU_TURBO_ON, str(props))
        else:
            check('真实 Core：本机 NPU 不支持该属性 ⇒ 退回（actual=False）',
                  actual is False and NT.NPU_TURBO_PROP not in props,
                  'actual=%s reason=%s' % (actual, reason))
        check('理由非空（能说明为什么）', bool(reason), reason)

        # ③ 真实 Core ⇒ 环境变量关 ⇒ 不注入
        os.environ[NT.ENV_NPU_TURBO] = '0'
        props0, actual0, reason0 = NT.resolve_npu_turbo(core=core)
        check('真实 Core：LIVECAP_NPU_TURBO=0 ⇒ 不注入',
              actual0 is False and NT.NPU_TURBO_PROP not in props0,
              'actual=%s props=%s' % (actual0, props0))
        os.environ.pop(NT.ENV_NPU_TURBO, None)

        # ④ 反证：假 Core（无 NPU）⇒ 必须退回
        props_f, actual_f, reason_f = NT.resolve_npu_turbo(core=FakeNoNpu())
        check('★ 反证：无 NPU 的 Core ⇒ 退回（不注入）',
              actual_f is False and NT.NPU_TURBO_PROP not in props_f,
              'actual=%s reason=%s' % (actual_f, reason_f))

        # ⑤ 反证：假 Core（属性表没有 NPU_TURBO）⇒ 必须退回
        props_g, actual_g, reason_g = NT.resolve_npu_turbo(core=FakeNoTurboProp())
        check('★ 反证：属性表无 NPU_TURBO ⇒ 退回（不注入）',
              actual_g is False and NT.NPU_TURBO_PROP not in props_g,
              'actual=%s reason=%s' % (actual_g, reason_g))

        # ⑥ turbo_props 合并 + 日志打实际值（真实 Core）
        logs = []
        merged = NT.turbo_props(core=core, base={'CACHE_DIR': 'X'}, on_log=logs.append)
        check('turbo_props 保留基础属性', merged.get('CACHE_DIR') == 'X', str(merged))
        check('turbo_props 日志打了实际值',
              len(logs) == 1 and ('NPU_TURBO=True' in logs[0] or 'NPU_TURBO=False' in logs[0]),
              str(logs))
    finally:
        os.environ.pop(NT.ENV_NPU_TURBO, None)
        if old is not None:
            os.environ[NT.ENV_NPU_TURBO] = old

    n_pass = sum(1 for _n, ok in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'ov_version': ov.__version__,
        'devices': devs,
        'npu_supported_props_count': len(list(core.get_property('NPU', 'SUPPORTED_PROPERTIES'))),
        'npu_turbo_in_supported_props': has_turbo_prop,
        'n_pass': n_pass, 'n_fail': n_fail, 'n_total': len(RESULTS),
        'checks': [{'name': n, 'ok': ok} for n, ok in RESULTS],
    }
    p = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app139_npu_turbo_real_ov.json'
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(out, ensure_ascii=False, indent=2))
    print('\n结果：%d PASS / %d FAIL / 共 %d' % (n_pass, n_fail, len(RESULTS)))
    print('落盘 ->', p)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
