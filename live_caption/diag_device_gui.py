"""APP-007：三分区「设备+精度」组合下拉的 GUI 冒烟测试（不开窗口）。

做法：建一个隐藏的 Tk root，构造 App，然后检查三个组合 Combobox 的内容。
⚠️ 不加载模型、不加载引擎、不起 TTS —— 纯界面层检查。

覆盖的关键不变量：
  1. 三个分区各有**一个**组合下拉（不再是「引擎下拉 + 设备下拉」两排）；
  2. 每个下拉的选项**非空**；
  3. **label 全局唯一**（GUI 靠 label 反查 engine/device/precision，
     重复 label ⇒ 静默选错引擎 —— MT 的 INT8-CW 在 GPU/NPU 上就是这种情况）；
  4. **id 唯一**，且 id 与 (engine, device, precision) 自洽；
  5. 初值在选项内，且反查得到的 engine/device/precision 与选项一致；
  6. 选项里的设备**全部来自实际检测**（检测不到的不显示）；
  7. NPU 不与 f32 同时出现（TTS 精度约束）；
  8. ASR 的 NPU 档**设备写死 NPU**（不接受覆盖）；
  9. 配置持久化落盘。

跑法（不需要 GPU、不需要模型、不需要机器锁）：
    .venv\\Scripts\\python.exe live_caption\\diag_device_gui.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAILS = []


def check(name, cond, detail=''):
    print(f'  [{"PASS" if cond else "FAIL"}] {name}' + (f'  {detail}' if detail else ''))
    if not cond:
        FAILS.append(name)


class _Args:
    translate = 'off'
    mt_engine = 'auto'
    mt_ctx = False
    mt_glossary = False
    mt_draft = False
    asr_lang = 'auto'
    engine = 'gpu_int8'
    source = 'mic'
    device = None
    system_device = None
    file = None
    speed = 1.0
    loop = False
    overlay = True
    font_size = 26
    asr_device = 'GPU.0'
    mt_device = 'GPU.0'
    tts_device = 'NPU'
    device_notes = []
    tts = 'off'
    tts_voice = 'A'
    tts_precision = 'f32'
    tts_out_device = None


def main():
    import tkinter as tk
    from live_caption_app import App
    import device_config as dc

    root = tk.Tk()
    root.withdraw()

    app = App(root, _Args())
    root.update_idletasks()

    avail = dc.available_devices()
    labels_avail = {dc.device_label(d): d for d in avail}
    print(f'  可用设备：{avail}')

    specs = (
        ('asr', 'cb_asr_combo', 'var_asr_combo', app._asr_opts),
        ('mt', 'cb_mt_combo', 'var_mt_combo', app._mt_opts),
        ('tts', 'cb_tts_combo', 'var_tts_combo', app._tts_opts),
    )

    for role, cbname, varname, opts in specs:
        print(f'\n== {role} 分区 ==')
        cb = getattr(app, cbname)
        var = getattr(app, varname)
        vals = list(cb['values'])
        print(f'    选项：{vals}')

        check(f'{role}: 只有一个组合下拉',
              not any(hasattr(app, n) for n in
                      (f'cb_dev_{role}', f'var_dev_{role}')))
        check(f'{role}: 下拉框有选项', len(vals) >= 1, str(vals))
        check(f'{role}: 选项与内部表一致',
              vals == [o['label'] for o in opts], str(vals))

        # ③ label 唯一
        dup = {v for v in vals if vals.count(v) > 1}
        check(f'{role}: label 全局唯一（可反查）', not dup, f'重复：{dup}')

        # ④ id 唯一
        ids = [o['id'] for o in opts]
        check(f'{role}: id 唯一', len(ids) == len(set(ids)), str(ids))

        # ⑥ 设备来自实际检测
        devs = {o['device'] for o in opts}
        unknown = {d for d in devs
                   if d not in avail and str(d).upper() not in ('NPU', 'CUDA')}
        check(f'{role}: 设备全部来自实际检测', not unknown, f'未知：{unknown}')

        # ⑤ 初值在选项内 + 反查一致
        cur = var.get()
        check(f'{role}: 初值在选项内', cur in vals, f'{cur}')
        opt = next((o for o in opts if o['label'] == cur), None)
        check(f'{role}: 初值可反查到选项', opt is not None, f'{cur}')
        if opt is not None:
            check(f'{role}: 反查的 id 自洽',
                  opt['id'] in ids and opt['device'] and opt['precision'],
                  f"{opt['id']} / dev={opt['device']} / prec={opt['precision']}")
            check(f'{role}: _dev_choices 与初值一致',
                  app._dev_choices.get(role) == opt['device'],
                  f"{app._dev_choices.get(role)} vs {opt['device']}")

    # ⑦ NPU 不与 f32 同时出现（TTS）
    bad = [o['label'] for o in app._tts_opts
           if str(o['device']).upper() == 'NPU' and o['precision'] == 'f32']
    check('TTS: NPU + f32 不出现', not bad, str(bad))

    # ⑧ ASR 的 NPU 档设备写死 NPU
    bad = [o['label'] for o in app._asr_opts
           if o['engine'].startswith('npu_') and o['device'] != 'NPU']
    check('ASR: NPU 档设备写死 NPU', not bad, str(bad))

    # ⑨ 配置持久化
    p = dc.CONFIG_PATH
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception:
        d = {}
    check('配置已落盘', isinstance(d, dict) and 'mt' in d, f'{p} -> {d}')

    # ── 事件路径：切 ASR 组合不应崩 ──
    print('\n== 事件路径 ==')
    try:
        if len(app._asr_opts) >= 2:
            app.var_asr_combo.set(app._asr_opts[-1]['label'])
            app._on_asr_combo_changed()
            root.update_idletasks()
            check('ASR 组合切换不抛异常', True)
        else:
            check('ASR 组合切换不抛异常', True, '（只有 1 个选项，跳过）')
    except Exception as e:
        check('ASR 组合切换不抛异常', False, f'{type(e).__name__}: {e}')

    try:
        if len(app._mt_opts) >= 2:
            app.var_mt_combo.set(app._mt_opts[-1]['label'])
            app._on_mt_combo_changed()
            root.update_idletasks()
            check('翻译组合切换不抛异常', True)
        else:
            check('翻译组合切换不抛异常', True, '（只有 1 个选项，跳过）')
    except Exception as e:
        check('翻译组合切换不抛异常', False, f'{type(e).__name__}: {e}')

    try:
        if len(app._tts_opts) >= 2:
            app.var_tts_combo.set(app._tts_opts[-1]['label'])
            app._on_tts_combo_changed()
            root.update_idletasks()
            check('语音组合切换不抛异常', True)
        else:
            check('语音组合切换不抛异常', True, '（只有 1 个选项，跳过）')
    except Exception as e:
        check('语音组合切换不抛异常', False, f'{type(e).__name__}: {e}')

    # 翻译切换后设备应等于用户选的那个（顺序铁律：先 set_engine 后 set_device）
    if len(app._mt_opts) >= 2:
        want = app._mt_opts[-1]
        check('翻译切换后 device == 用户选择',
              app.mt.device == want['device'],
              f"{app.mt.device} vs {want['device']}")
        check('翻译切换后 engine_key 匹配',
              app.mt.engine_key == want['engine'],
              f"{app.mt.engine_key} vs {want['engine']}")

    root.destroy()
    print()
    if FAILS:
        print(f'ALL FAIL ({len(FAILS)}): ' + ', '.join(FAILS))
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
