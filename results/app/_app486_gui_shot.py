# -*- coding: utf-8 -*-
r"""APP-102 §2.4：rc8 GUI 启动一次并截图（不加载模型、不占设备）。

判据：ASR 下拉只有两档且都是 stateful 引擎；克隆音色置灰且不列克隆项；
目标语言 10 种；截图必须非空白（PrintWindow + 像素级守卫）。
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
        engine='gpu_int8', tts=None, tts_voice='A', tts_precision='f32',
        tts_out_device=None, speaker='off', tts_device=None, mt_device=None,
        asr_device=None, tts_source='mt', mt_engine=None, font_size=26,
        max_seconds=0.0, out=None, autostart=False, selftest=0.0,
        selftest_out=None, selftest_mt_switch=False, list_devices=False,
        check=False, cli=False, device=None, system_device=None, speed=1.0,
        loop=False, mt_ctx=False, mt_glossary=False, tts_out=None,
        tts_dump_dir=None, tts_jsonl=None,
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
    # 🔴 口径（APP-097）：下拉共 11 项 = 1 个「关闭」+ **10 种目标语言**。
    #    只看语言数，不能把「关闭」算成第 11 种语言。
    out['target_langs_10'] = (len(_langs) == 10 and 'off' in _all_targets)
    out['default_devices'] = dict(getattr(app, '_dev_choices', {}) or {})

    # 🔴 capture_hwnd 内部会自己调 wintypes_hwnd ⇒ 这里必须传 **int**，
    #    传已转换的 HWND 对象会二次转换并抛 TypeError（本轮实测踩过）。
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
                                     out['shot_not_blank'])) else 'FAIL')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in
                      ('n_asr_options', 'asr_two_stateful',
                       'clone_disabled', 'n_target_langs',
                       'shot_not_blank', 'shot_bytes', 'verdict')},
                     ensure_ascii=False))
    try:
        root.destroy()
    except Exception:
        pass
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
