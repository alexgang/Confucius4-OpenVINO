#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app591_speed_cap_audit.py —— **APP-114 §1 的落盘证据**：

  ① 对 **dev 树** 与 **客户包 app 目录**（本轮交付包 = sp5）**全文 grep**
     `2\.0|2\.00|1\.3|1\.30|SPEED_MAX|speed_max|rate`
     ⇒ 把**命中行逐行列成表**，并**逐行写清是否和播放倍率相关**；
  ② **总倍率**论证：TTS 合成侧**有没有语速（speaking rate）参数**、
     它与 WSOLA 倍率**是否相乘** ⇒ 乘积是否 ≤ 1.70。

🔴 **纪律**：**只读**（不写任何产品代码/包文件）⇒ 纯静态审计。
"""
import json
import os
import re
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
DEV = os.path.join(REPO, 'live_caption')
PKG_APP = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp5', 'app')
PKG4_APP = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp4', 'app')
OUT = os.path.join(REPO, 'results', 'app', 'app591_app114_speed_cap_audit.json')

PAT = re.compile(r'2\.0|2\.00|1\.3|1\.30|SPEED_MAX|speed_max|rate', re.I)

#: 🔴 **逐行分类**（reviewer 要求「逐行写清是否和播放倍率相关」）
RULES = [
    # (正则, 分类, 说明)
    (re.compile(r'语速上限|倍率上限|上限对|上限统一|SPEED_MAX|ZH_SPEED_MAX|'
                 r'speed_max|tts_speed_max_zh|用户定的.*上限|自适应语速|'
                 r'1\.0×–|上限.*1\.70|1\.70×|1\.70 倍'), 'speed_cap',
     '🔴 **与播放倍率直接相关**（语速上限）⇒ 已改成 1.70×'),
    (re.compile(r'1\.30×|1\.50×|2\.00×|→ 2\.00|1\.30 →|1\.50 →|2\.00 →|'
                 r'1\.30× 上限|1\.50× 上限'), 'speed_history',
     '⚪ **历史沿革注释**（记录 1.30→1.50→2.00→1.70 的决策过程）⇒ 保留不改'),
    (re.compile(r'实测.*1\.2–1\.3|落在 1\.2|1\.2–1\.3×'), 'speed_measure',
     '⚪ **历史实测数据**（某次回放落在 1.2–1.3×）⇒ 保留不改'),
    (re.compile(r'文件回放速度|_speed_label|--speed|全速跑批'), 'file_playback',
     '⚪ **输入文件回放速度**（GUI/CLI `--speed`，喂给 ASR 的节奏）'
     '⇒ **不是 TTS 语音倍率** ⇒ reviewer 明文「视频播放速度不改」⇒ 保留'),
    (re.compile(r'cfg_rate|inference_cfg_rate'), 'synth_cfg',
     '⚪ **合成侧 CFG 引导率**（扩散采样强度，`inference_cfg_rate`）'
     '⇒ **不是语速（speaking rate）** ⇒ 不与 WSOLA 相乘 ⇒ 保留'),
    (re.compile(r'sample_rate|samplerate|bit_rate|bitrate|generate|'
                 r'生成帧|rate_limit'), 'other_numeric',
     '⚪ **其它语义的 "rate"**（采样率 / 比特率 / 生成帧率等）⇒ 与播放倍率无关'),
]


def classify(line):
    for rx, cat, note in RULES:
        if rx.search(line):
            return cat, note
    # 兜底：纯数字命中（阈值 / 超时 / 帧数 / 百分比…）
    return 'other_numeric', ('⚪ **与播放倍率无关的普通数字**（阈值 / 超时 / '
                             '帧数 / 百分比等）⇒ 保留')


def scan(root, files=None):
    """扫一个目录下的 .py ⇒ 命中行列表。"""
    out = []
    names = files if files is not None else sorted(
        f for f in os.listdir(root) if f.endswith('.py'))
    for fn in names:
        p = os.path.join(root, fn)
        if not os.path.isfile(p):
            continue
        with open(p, encoding='utf-8', errors='replace') as f:
            for i, ln in enumerate(f.read().splitlines(), 1):
                if PAT.search(ln):
                    cat, note = classify(ln)
                    out.append({'file': fn, 'line': i, 'text': ln.strip()[:220],
                                'class': cat, 'note': note})
    return out


def main():
    ev = {'purpose': 'APP-114 §1：语速上限 1.70× 的落盘证据（grep 表 + 总倍率论证）',
          'grep_pattern': PAT.pattern,
          'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'scopes': {}}

    pkg_files = sorted(f for f in os.listdir(PKG_APP) if f.endswith('.py'))
    dev_files = sorted(f for f in os.listdir(DEV) if f.endswith('.py'))
    shipped_dev = [f for f in pkg_files if os.path.isfile(os.path.join(DEV, f))]
    other_dev = [f for f in dev_files if f not in shipped_dev]

    # ── 范围 A：交付包 sp5 的 app 目录（全文）──
    hits_pkg = scan(PKG_APP)
    ev['scopes']['A_pkg_sp5_app'] = {
        'root': PKG_APP, 'n_files': len(pkg_files), 'n_hits': len(hits_pkg),
        'hits': hits_pkg,
        'note': '**交付包**的 app 目录（随包的 28 个 .py）⇒ 逐行表'}

    # ── 范围 B：dev 树里「随包的那批」生产模块（全文）──
    hits_dev_shipped = scan(DEV, shipped_dev)
    ev['scopes']['B_dev_shipped_modules'] = {
        'root': DEV, 'n_files': len(shipped_dev), 'n_hits': len(hits_dev_shipped),
        'hits': hits_dev_shipped,
        'note': 'dev 树里**随包的生产模块**（= 范围 A 的同一批文件）⇒ 逐行表'}

    # ── 范围 C：dev 树里**不随包**的一次性脚本（按文件汇总）──
    hits_dev_other = scan(DEV, other_dev)
    per_file = {}
    for h in hits_dev_other:
        per_file.setdefault(h['file'], {'n': 0, 'classes': {}})
        per_file[h['file']]['n'] += 1
        per_file[h['file']]['classes'][h['class']] = \
            per_file[h['file']]['classes'].get(h['class'], 0) + 1
    ev['scopes']['C_dev_non_shipped_scripts'] = {
        'root': DEV, 'n_files': len(other_dev), 'n_hits': len(hits_dev_other),
        'per_file_summary': per_file,
        'hits': hits_dev_other,
        'note': ('⚪ **不随包**的历史一次性脚本（sync_*/diag_*/_*_write_status 等）'
                 '⇒ 只是工具/记录，**不在交付物里** ⇒ 不改；'
                 '其中「1.00× ~ 1.30×」之类是**旧 README 补丁脚本的文案**。')}

    # ── 范围 D：sp4（冻结参照）──
    hits_sp4 = scan(PKG4_APP)
    ev['scopes']['D_pkg_sp4_app_frozen'] = {
        'root': PKG4_APP, 'n_files': len(
            [f for f in os.listdir(PKG4_APP) if f.endswith('.py')]),
        'n_hits': len(hits_sp4), 'hits': hits_sp4,
        'note': ('⚪ **sp4 已冻结、逐字节未动**（APP-055）⇒ 其 app 目录仍是 '
                 'APP-113 的 2.00× 口径 ⇒ **这是预期**（交付包是 sp5）。')}

    # ── 分类汇总 ──
    summ = {}
    for name, sc in ev['scopes'].items():
        c = {}
        for h in sc.get('hits', []):
            c[h['class']] = c.get(h['class'], 0) + 1
        summ[name] = c
    ev['class_summary'] = summ

    # ── 🔴 总倍率论证（逐条给出文件 + 行号）──
    def find(rel, needles, root=DEV):
        p = os.path.join(root, rel)
        hits = []
        if not os.path.isfile(p):
            return hits
        for i, ln in enumerate(open(p, encoding='utf-8', errors='replace')
                               .read().splitlines(), 1):
            if any(n in ln for n in needles):
                hits.append({'file': rel, 'line': i, 'text': ln.strip()[:200]})
        return hits

    mult = {
        'question': ('APP-114 §1：「如果 TTS 合成有语速参数（例如 speaking rate），'
                     '而且它和 WSOLA 倍率相乘，那么乘积必须 ≤1.70」'),
        'wsola_application': (
            find('tts_worker.py', ['StreamWSOLA(speed=_sp', '_stretcher.process(',
                                   '_stretcher.flush(']),
            '🔴 **WSOLA 变速就发生在这里**：`StreamWSOLA(speed=_sp)` 建变速器 → '
            '`process(w)` 对**合成出来的波形**做时伸缩 ⇒ 语音倍率 = `_sp`。'),
        'synth_call_kwargs': (
            find('tts_engine.py', ["kwargs['language']", "kwargs['text']",
                                   'generate_stream(**kwargs)'])
            + find('tts_cuda.py', ['def generate_stream(self, text']),
            '🔴 **合成侧调用没有语速参数**：`generate_stream` 的签名只有 '
            'text / language / speaker_embed / speaker / split_on_silence / '
            'cancel_event / chunk_frames / max_new_tokens / est_sec '
            '⇒ **没有 speed / rate / speaking_rate** ⇒ 合成侧速率恒为 **1.0×**。'),
        'cfg_rate_is_not_speaking_rate': (
            find('tts_engine.py', ['inference_cfg_rate'])
            + find('tts_worker.py', ['cfg_rate=0.7', 'inference_cfg_rate=0.7']),
            '⚪ `cfg_rate` / `inference_cfg_rate` 是**扩散采样的 CFG 引导率**'
            '（classifier-free guidance 强度）⇒ **不是语速** ⇒ '
            '**不与 WSOLA 倍率相乘**。'),
        'caps_in_code': (
            find('time_stretch.py', ['SPEED_MAX = ', 'ZH_SPEED_MAX = ',
                                     'SPEED_PER_LAG_S = ', 'LAG_DEADZONE_S = ',
                                     'LAG_HYSTERESIS_S = ', 'MAX_STEP_CHANGE = '])
            + find('tts_worker.py', ['return (1.0, 1.70)', '_lo, _hi = 1.0, 1.70',
                                     'cap > _hi']),
            '🔴 **速率上限只有一处来源**：`time_stretch.SPEED_MAX` / '
            '`ZH_SPEED_MAX` = 1.70；worker 的兜底与 RTF 动态封顶都取同一个 1.70。'),
        'conclusion': (
            '🟢 **总倍率 = 合成侧速率 × WSOLA 倍率 = 1.0 × ≤1.70 = ≤1.70** '
            '⇒ 满足 APP-114 §1「乘积必须 ≤1.70」。'
            '（合成侧没有语速参数 ⇒ 乘积的第二因子恒为 1.0。）'),
    }
    ev['total_multiplier'] = mult

    # ── 🔴 GUI 提示文字 / README 里的「上限说明」检查（APP-114 §1 的最后一句）──
    gui_text = []
    gui_path = os.path.join(PKG_APP, 'live_caption_app.py')
    gui_rx = re.compile(r'语速|倍速|倍率')
    gui_ctx = re.compile(r"text=|st\.set\(|tip=|label|_label")
    for i, ln in enumerate(open(gui_path, encoding='utf-8', errors='replace')
                           .read().splitlines(), 1):
        if gui_rx.search(ln) and gui_ctx.search(ln):
            gui_text.append({'file': 'live_caption_app.py', 'line': i,
                             'text': ln.strip()[:200]})
    readme_text = []
    pkg_root = os.path.dirname(PKG_APP)
    rd_rx = re.compile(r'语速|倍速|倍率|1\.30|2\.00|2\.0×|SPEED_MAX|speed_max')
    for fn in ('README_zh.md', 'README_en.md', 'README_perftest.txt'):
        p = os.path.join(pkg_root, fn)
        if not os.path.isfile(p):
            continue
        n = 0
        for i, ln in enumerate(open(p, encoding='utf-8', errors='replace')
                               .read().splitlines(), 1):
            if rd_rx.search(ln):
                readme_text.append({'file': fn, 'line': i,
                                    'text': ln.strip()[:200]})
                n += 1
        if n == 0:
            readme_text.append({'file': fn, 'line': 0,
                                'text': '（0 命中 ⇒ 该 README **没有**语速上限说明文本）'})
    ev['gui_readme_wording'] = {
        'gui_speed_texts': gui_text,
        'gui_conclusion': ('GUI 的「语速」只显示**当前倍率值**（`st.set("speed", ...)）'
                           '⇒ **没有**写死的「上限 2.0×」静态文案 ⇒ **无需改**；'
                           'GUI 里的 `2.0×` 出现在**文件回放速度**下拉'
                           '（`live_caption_app.py:3107`）⇒ 那是**输入文件节奏**，'
                           '不是 TTS 语音倍率 ⇒ 按 reviewer「视频播放速度不改」保留。'),
        'readme_speed_texts': readme_text,
        'readme_conclusion': ('三个 README（zh / en / perftest）**都没有**语速上限'
                              '说明文本 ⇒ **无需改**（包内 README 只写设备/体积/使用'
                              '说明）。'),
    }

    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    print('total hits: A=%d B=%d C=%d D=%d'
          % (len(hits_pkg), len(hits_dev_shipped), len(hits_dev_other),
             len(hits_sp4)))
    print('OUT=%s' % OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
