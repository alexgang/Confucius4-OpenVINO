# -*- coding: utf-8 -*-
r"""_app493 GUI 截图（APP-104 §1 的 GUI 侧验收）。

在**残留旧配置**（asr=GPU.0/mt=GPU.0/tts=NPU）下启动 rc9 包里的 GUI：
  * 设备必须是 **ASR=NPU / MT=GPU.0 / TTS=GPU.0**（旧出厂默认被忽略）；
  * 不得出现「ASR 与 MT 都放在 GPU」提示；
  * 截图必须非黑图（PrintWindow + 像素级守卫）。

🔴 不加载模型（stub 掉 `load_engine`）⇒ 不占设备。
"""
from __future__ import annotations

import json
import os
import sys
import time

PKG = sys.argv[1]
OUT_PNG = sys.argv[2]
OUT_JSON = sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PKG, 'app'))
sys.path.insert(0, HERE)

import tkinter as tk                       # noqa: E402
import live_caption_app as lca             # noqa: E402
import translator                          # noqa: E402
from win_capture import capture_hwnd  # noqa: E402


class A:
    pass


def make_args():
    a = A()
    for k, v in dict(
        source='mic', translate='en', asr_lang='auto', file=None,
        # 🔴 APP-104 §1：engine 默认 **None**（= 按解析出的 ASR 设备自动选）
        engine=None, tts=None, tts_voice='A', tts_precision='f32',
        tts_out_device=None, speaker='off', tts_device=None, mt_device=None,
        asr_device=None, tts_source='mt', mt_engine=None, font_size=26,
        max_seconds=0.0, out=None, autostart=False, selftest=0.0,
        selftest_out=None, selftest_mt_switch=False, list_devices=False,
        check=False, cli=False, device=None, system_device=None, speed=1.0,
        loop=False, mt_ctx=False, mt_glossary=False, tts_out=None,
        tts_dump_dir=None, tts_jsonl=None, device_notes=[],
    ).items():
        setattr(a, k, v)
    return a


def main():
    out = {'pkg': PKG, 'shot': OUT_PNG}
    root = tk.Tk()
    root.geometry('1280x800+0+0')
    lca.App.load_engine = lambda self: None
    translator.TranslationService.set_engine = lambda self, k: True
    translator.TranslationService.set_device = lambda self, d: True
    app = lca.App(root, make_args())
    root.update_idletasks()
    root.update()
    time.sleep(1.2)
    root.update()
    root.deiconify()

    opts = list(getattr(app, '_asr_opts', []) or [])
    out['asr_options'] = [
        {'id': o.get('id'), 'label': o.get('label'),
         'engine': o.get('engine'), 'device': o.get('device'),
         'note': o.get('note', '')} for o in opts]
    out['n_asr_options'] = len(opts)
    out['asr_two_stateful'] = (
        len(opts) == 2
        and all('stateful' in (o.get('note', '') + o.get('label', ''))
                for o in opts)
        and {o.get('engine') for o in opts} == {'gpu_int8', 'npu_int8'})
    voice = getattr(app, 'cb_tts_voice', None)
    out['tts_voice_state'] = str(voice.cget('state')) if voice else None
    out['tts_voice_values'] = list(voice.cget('values')) if voice else []
    out['clone_disabled'] = (
        out['tts_voice_state'] == 'disabled'
        and not any('克隆' in str(x) for x in out['tts_voice_values']))
    _all_targets = list(getattr(lca, 'TARGETS', ()) or ())
    _langs = [x for x in _all_targets if x != 'off']
    out['n_target_entries'] = len(_all_targets)
    out['target_lang_codes'] = _langs
    out['n_target_langs'] = len(_langs)
    out['target_langs_10'] = (len(_langs) == 10 and 'off' in _all_targets)

    # 🔴 APP-104 §1：GUI 里显示的设备必须是**迁移后的出厂默认**
    out['default_devices'] = dict(getattr(app, '_dev_choices', {}) or {})
    out['devices_migrated'] = out['default_devices'] == {
        'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0'}
    notes = list(getattr(app, '_device_notes', []) or [])
    out['device_notes'] = notes
    out['migration_note'] = any('已忽略旧配置里的设备项' in n for n in notes)
    try:
        status = str(app.var_status.get())
    except Exception:
        status = ''
    out['status_text'] = status
    out['no_asr_mt_same_gpu_warning'] = ('ASR 与 MT 都放在' not in status)

    hwnd = int(root.winfo_id())
    ok = capture_hwnd(hwnd, OUT_PNG)
    out['capture_ok'] = bool(ok)
    out['shot_exists'] = os.path.isfile(OUT_PNG)
    out['shot_bytes'] = (os.path.getsize(OUT_PNG)
                         if out['shot_exists'] else 0)
    try:
        from PIL import Image
        im = Image.open(OUT_PNG).convert('RGB')
        ext = im.getextrema()
        out['shot_extrema'] = ext
        out['shot_not_blank'] = (out['shot_bytes'] > 5000
                                 and any(lo != hi for lo, hi in ext))
        out['shot_size'] = list(im.size)
    except Exception as e:
        out['shot_not_blank'] = False
        out['shot_error'] = repr(e)

    out['verdict'] = ('PASS' if all((out['asr_two_stateful'],
                                     out['clone_disabled'],
                                     out['target_langs_10'],
                                     out['shot_not_blank'],
                                     out['devices_migrated'],
                                     out['no_asr_mt_same_gpu_warning']))
                      else 'FAIL')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in
                      ('n_asr_options', 'asr_two_stateful',
                       'clone_disabled', 'n_target_langs',
                       'default_devices', 'devices_migrated',
                       'migration_note', 'no_asr_mt_same_gpu_warning',
                       'shot_not_blank', 'shot_bytes', 'verdict')},
                     ensure_ascii=False))
    try:
        root.destroy()
    except Exception:
        pass
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
