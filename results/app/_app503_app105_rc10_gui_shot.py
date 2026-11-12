# -*- coding: utf-8 -*-
r"""_app503 — **APP-105 rc10 GUI 截图**（§7 的 GUI 侧验收）。

在**包目录**上直接 import 包的 ``app/live_caption_app.py`` 启动 GUI（**不加载模型**
⇒ 不占设备），验收：

  * 出厂默认 = **ASR=GPU.0 / MT=GPU.0 / TTS=NPU**（APP-105 §7 的第 2 代默认）；
  * ASR 下拉框仍是**两档 stateful**、克隆置灰、目标语言 10 种；
  * 状态栏**不得**出现旧告警「ASR 与 MT 都放在 …」（§7 已把它改成一行日志）；
  * 残留旧配置 ⇒ GUI 的 ``device_notes`` 里**必须**有「已忽略旧配置里的设备项」
    （§5 观察项：GUI 也要看得见）；
  * 截图非黑图（PrintWindow + 像素级守卫）。

用法：
    python results/app/_app503_app105_rc10_gui_shot.py <包目录> <png> <json>
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
import device_config                       # noqa: E402
from win_capture import capture_hwnd      # noqa: E402

#: APP-105 §7 的出厂默认（第 2 代）
EXPECT_DEFAULTS = {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}


class A:
    pass


def make_args(device_notes=None):
    a = A()
    for k, v in dict(
        source='mic', translate='en', asr_lang='auto', file=None,
        engine=None, tts=None, tts_voice='A', tts_precision='f32',
        tts_out_device=None, speaker='off', tts_device=None, mt_device=None,
        asr_device=None, tts_source='mt', mt_engine=None, font_size=26,
        max_seconds=0.0, out=None, autostart=False, selftest=0.0,
        selftest_out=None, selftest_mt_switch=False, list_devices=False,
        check=False, cli=False, device=None, system_device=None, speed=1.0,
        loop=False, mt_ctx=False, mt_glossary=False, tts_out=None,
        tts_dump_dir=None, tts_jsonl=None, device_notes=list(device_notes or []),
    ).items():
        setattr(a, k, v)
    return a


def main():
    out = {'pkg': PKG, 'shot': OUT_PNG,
           'expected_defaults': EXPECT_DEFAULTS}
    # 🔴 用**包里的** device_config 跑一次真实的 get_devices()
    #    ⇒ 残留旧配置会被识别出来（这正是要验的迁移路径）。
    try:
        devs, notes = device_config.get_devices()
    except Exception as e:
        devs, notes = {}, ['<get_devices 失败：%r>' % e]
    out['pkg_default_devices'] = dict(devs)
    out['real_device_notes'] = list(notes)
    out['stale_config_detected'] = any(
        '已忽略旧配置里的设备项' in n for n in notes)
    out['defaults_version'] = getattr(device_config, 'CONFIG_DEFAULTS_VERSION',
                                      None)

    root = tk.Tk()
    root.geometry('1280x800+0+0')
    lca.App.load_engine = lambda self: None
    translator.TranslationService.set_engine = lambda self, k: True
    translator.TranslationService.set_device = lambda self, d: True
    app = lca.App(root, make_args(notes))
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
    out['asr_engine_set'] = getattr(app, 'engine_key', None)
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

    # 🔴 §7：GUI 里显示的设备必须是**新出厂默认**
    out['default_devices'] = dict(getattr(app, '_dev_choices', {}) or {})
    out['devices_are_new_default'] = out['default_devices'] == EXPECT_DEFAULTS
    notes_gui = list(getattr(app, '_device_notes', []) or [])
    out['device_notes'] = notes_gui
    out['migration_note_visible'] = any(
        '已忽略旧配置里的设备项' in n for n in notes_gui)
    try:
        status = str(app.var_status.get())
    except Exception:
        status = ''
    out['status_text'] = status
    # 🔴 §7：旧告警文案**不得**再出现在状态栏
    out['no_old_warning'] = ('ASR 与 MT 都放在' not in status
                             and '建议把 ASR 放 NPU' not in status)

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

    out['checks'] = {
        'asr_two_stateful': out['asr_two_stateful'],
        'clone_disabled': out['clone_disabled'],
        'target_langs_10': out['target_langs_10'],
        'shot_not_blank': out['shot_not_blank'],
        'devices_are_new_default': out['devices_are_new_default'],
        'no_old_warning': out['no_old_warning'],
        'pkg_defaults_new': (devs == EXPECT_DEFAULTS),
        'defaults_version_9': (out['defaults_version'] == 9),
        'migration_note_visible_if_stale': (
            (not out['stale_config_detected'])
            or out['migration_note_visible']),
    }
    out['verdict'] = ('PASS' if all(out['checks'].values()) else 'FAIL')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out['checks'], ensure_ascii=False, indent=1))
    print('VERDICT', out['verdict'])
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
