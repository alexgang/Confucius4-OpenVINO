#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app589_three_forms_defaults_check.py —— APP-113 §4 的「三种形态共用代码要核
MiniMVP/完整版默认值是否随之生效」**静态核对**。

🔴 **口径**：**读各包内 app/*.py 的真实文本**（不是读开发树）⇒ 回答的是
   「**现役的每个包**里的那些默认值到底是多少」。
🔴 **不 import 客户包模块**（客户包 venv 依赖各不相同，import 会假 FAIL）
   ⇒ 只做**文本/AST 级**判定（判据与 §210 ⑩ 同口径）。
"""
import hashlib
import json
import os
import re
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
DEV = os.path.join(REPO, 'live_caption')
RESULTS = os.path.join(REPO, 'results', 'app')
OUT = os.path.join(RESULTS, 'app589_three_forms_defaults.json')

TARGETS = [
    ('dev 树（唯一事实来源）', DEV),
    ('SpecialMVP sp4（本轮新包）',
     os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp4', 'app')),
    ('SpecialMVP sp3（冻结）',
     os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp3', 'app')),
    ('MiniMVP rc11（已交付）',
     os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc11', 'app')),
    ('MiniMVP rc10（已交付）',
     os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc10', 'app')),
    ('完整版 v2.1（当前交付版）',
     os.path.join(HOME, 'Confucius4_LiveCaption_v2.1', 'app')),
    ('完整版 v2.4',
     os.path.join(HOME, 'Confucius4_LiveCaption_v2.4', 'app')),
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def num_in(txt, pat):
    m = re.search(pat, txt)
    return float(m.group(1)) if m else None


def probe(appdir):
    """读包内 5 个文件 ⇒ 抽取 APP-113 关心的默认值。"""
    out = {'files': {}, 'missing': []}
    def rd(name):
        p = os.path.join(appdir, name)
        if not os.path.isfile(p):
            out['missing'].append(name)
            return ''
        out['files'][name] = {'bytes': os.path.getsize(p),
                              'sha256': sha256_file(p)}
        return open(p, encoding='utf-8', errors='replace').read()

    dc = rd('device_config.py')
    ts = rd('time_stretch.py')
    tw = rd('tts_worker.py')
    sv = rd('tts_service.py')
    app = rd('live_caption_app.py')

    out['tts_late_drop_sec'] = num_in(dc, r"'tts_late_drop_sec':\s*([\d.]+)")
    out['tts_speed_max_zh'] = num_in(dc, r"'tts_speed_max_zh':\s*([\d.]+)")
    out['SPEED_MAX'] = num_in(ts, r'^SPEED_MAX\s*=\s*([\d.]+)', )
    if out['SPEED_MAX'] is None:
        out['SPEED_MAX'] = num_in(ts, r'SPEED_MAX\s*=\s*([\d.]+)')
    out['ZH_SPEED_MAX'] = num_in(ts, r'ZH_SPEED_MAX\s*=\s*([\d.]+)')
    out['worker_late_drop_guard'] = ('self._late_drop_sec > 0.0' in tw)
    out['worker_late_drop_mentions'] = len(re.findall(r'late_drop', tw))
    out['worker_fallback_2_00'] = ('return (1.0, 2.00)' in tw)
    out['service_comment_2_00'] = ('1.00–**2.00**' in sv)
    # §1 / §2 特征
    out['has_TtsReadyQueue'] = ('class TtsReadyQueue' in app)
    out['has_pending_queue'] = ('self._tts_pending_q = TtsReadyQueue' in app)
    out['has_overflow_counter'] = ('n_drop_not_ready_overflow' in app)
    out['app_no_longer_skips'] = ('本句**不排队**' not in app)
    out['cli_no_longer_skips'] = ('_skip_nr += 1' not in app)
    out['has_parallel_boot'] = ('_boot_tts_parallel' in app)
    out['parallel_only_cuda'] = ("_tts_dev.upper().startswith('CUDA')" in app)
    # 出厂默认设备（device_config 的三形态表；老包只有扁平 DEFAULT_DEVICES）
    out['default_devices'] = {}
    for form in ('FULL', 'MINIMVP', 'SPECIALMVP'):
        m = re.search(r'_DEFAULT_DEVICES_%s:[^=]*=\s*\{(.*?)\}' % form, dc,
                      re.S)
        if m:
            out['default_devices'][form] = dict(
                re.findall(r"'(\w+)':\s*'([^']+)'", m.group(1)))
    m = re.search(r'^DEFAULT_DEVICES:[^=]*=\s*\{(.*?)\}', dc, re.S | re.M)
    if m:
        out['default_devices']['FLAT_OLD'] = dict(
            re.findall(r"'(\w+)':\s*'([^']+)'", m.group(1)))
    return out


def main():
    ev = {'created': time.strftime('%Y-%m-%d %H:%M:%S'),
          'purpose': 'APP-113 §4：三种形态共用代码 ⇒ MiniMVP/完整版默认值是否随之生效',
          'rows': [], 'notes': []}
    for name, d in TARGETS:
        if not os.path.isdir(d):
            ev['rows'].append({'target': name, 'path': d, 'exists': False})
            continue
        r = probe(d)
        r['target'] = name
        r['path'] = d
        r['exists'] = True
        ev['rows'].append(r)
    # ── 结论表 ──
    tbl = []
    for r in ev['rows']:
        if not r.get('exists'):
            continue
        tbl.append({
            'target': r['target'],
            'late_drop': r.get('tts_late_drop_sec'),
            'speed_max_zh': r.get('tts_speed_max_zh'),
            'SPEED_MAX': r.get('SPEED_MAX'),
            'ZH_SPEED_MAX': r.get('ZH_SPEED_MAX'),
            'has_TtsReadyQueue': r.get('has_TtsReadyQueue'),
            'has_parallel_boot': r.get('has_parallel_boot'),
            'default_devices': r.get('default_devices'),
        })
    ev['table'] = tbl
    # ── §2 并行只对 CUDA 生效 ⇒ 各形态是否走并行 ──
    par = {}
    for r in ev['rows']:
        if not r.get('exists'):
            continue
        dd = r.get('default_devices') or {}
        tts_dev = (dd.get('SPECIALMVP') or {}).get('tts')
        if not tts_dev:
            tts_dev = (dd.get('MINIMVP') or {}).get('tts')
        if not tts_dev:
            tts_dev = (dd.get('FULL') or {}).get('tts')
        if not tts_dev:
            tts_dev = (dd.get('FLAT_OLD') or {}).get('tts')
        par[r['target']] = {
            'tts_device_default': tts_dev,
            'parallel_applies': bool(tts_dev and
                                     str(tts_dev).upper().startswith('CUDA')),
        }
    ev['parallel_applicability'] = par
    ev['notes'] = [
        '§2 的「ASR/TTS 并行」**只对 TTS 档位 = CUDA 的形态生效**'
        '（Special MVP：TTS=CUDA ⇒ 生效）；'
        'MiniMVP（TTS=NPU）与完整版（TTS=GPU.0）⇒ **保持原串行顺序**'
        '（沿用「auto=False 防 GPU 编译死锁」：同一张卡上不并行编译）。',
        '§3 的「非中文上限 1.30 → 2.00」在**共享的 time_stretch.py** 里 ⇒ '
        '**任何形态下次出包时都会带上**；但**已交付的包仍是旧值**（不就地改，APP-055）。',
        '§1 的「就绪前排队」在共享的 live_caption_app.py 里 ⇒ 同上。',
    ]
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    for t in tbl:
        print('%-28s late_drop=%-6s zh_max=%-6s SPEED_MAX=%-6s ZH_MAX=%-6s '
              'queue=%-5s parallel=%-5s' %
              (t['target'][:28], t['late_drop'], t['speed_max_zh'],
               t['SPEED_MAX'], t['ZH_SPEED_MAX'], t['has_TtsReadyQueue'],
               t['has_parallel_boot']))
    print('-> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
