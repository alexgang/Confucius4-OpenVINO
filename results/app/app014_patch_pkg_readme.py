# -*- coding: utf-8 -*-
"""APP-014①：客户包 README 的**定点**改写 —— TTS 从「实验性」改为**正式功能**。

🔴 **纪律**（与 `app010_patch_pkg_readme.py` 完全一致）：
   仓库 `live_caption/` ≠ 客户包 `app/` ⇒ **严禁整目录覆盖同步**。
   本脚本只做**精确字符串替换**，每条规则都断言**唯一命中**。

🔴 **幂等性铁律**：
   「把 A 替换成 A'，其中 A' **包含 A**」这种**嵌套替换**在第二次运行时
   **旧串仍然命中** ⇒ 重复替换 ⇒ README 里出现多份标注。
   ⇒ 本脚本每条规则带一个 **mark**（新串里的特征串）：
     * mark 已存在 ⇒ **幂等跳过**；
     * 否则 old 必须**恰好命中 1 次** ⇒ 否则报错中止（不猜）。

🔴 **本轮要改的**（APP-014 第 1 条：TTS 改为正式功能）：
   ① TTS 段标题：「实验性功能，默认关闭」⇒「正式功能，默认开启」；
   ② 删掉整块「⚠️ 本项为实验性功能…」警告块；
   ③ 「默认关闭」⇒「**默认开启**」+ 加「⚠️ 请佩戴耳机，避免回授」提示；
   ④ 「已知限制」里的「TTS 为实验性功能」⇒ 改写为「TTS 已通过抽听验收（正式功能）」；
   ⑤ 🔴 **顺带修掉一处真实 bug**：「已知限制」里「段切分按能量静音判断…」**重复了两行**
      （APP-010 的 `insert_after` 规则把 anchor 又插了一遍）。

用法：
    python app014_patch_pkg_readme.py <pkg_root>
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

PKG = (sys.argv[1] if len(sys.argv) > 1
       else r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app014_pkg_readme_patch.json')

# ── 🔴🔴🔴 **TTS 段：程序化锚点**（不手抄原文！）────────────────────────
#    旧做法：把「标题 + 警告块 + 原说明段」整段手抄成 OLD 串
#    ⇒ 本轮已实测踩中：英文原文措辞与中文不同 ⇒ 手抄必然命中 0 次。
#    新做法：**按标题定位到下一个 `## `** ⇒ 整段自动取出 ⇒ 零抄写风险。
ZH_TTS_TITLE = '### ⑤ 译文语音输出'
EN_TTS_TITLE = '### ⑤ Spoken translations'

ZH_TTS_NEW = """### ⑤ 译文语音输出（**正式功能，默认开启**）

译文由 TTS（Qwen3-TTS / BabelVox）朗读。模型随包分发，**离线可跑，无需联网安装**。

- 界面「语音输出」分区可开关、选设备与推理精度（F32 / F16）、选播放设备（外放到耳机）。
- **默认开启**；如不需要朗读，可在界面取消勾选「开启」，或用命令行 `--tts off`。
- ⚠️ **请佩戴耳机，避免回授** —— TTS 从系统输出设备播放，若 ASR 同时采集系统声音，
  TTS 的声音会被**再采回去**，造成回声 / 自激 / 重复词。
- ASR 采集通路与 TTS 播放通路相互独立，避免回声与自拾音干扰。
- **只随包分发音色 A（预设音色）** —— 音色 B 与克隆音色素材按交付要求不进包，界面里也不提供这两项。
"""
ZH_TTS_MARK = '### ⑤ 译文语音输出（**正式功能，默认开启**）'

EN_TTS_NEW = """### ⑤ Spoken translations (**a full feature, on by default**)

Translations are spoken by TTS (Qwen3-TTS / BabelVox). The model ships with the package and
**runs offline — no network install needed**.

- The "Speech output" area can switch it on and choose the device, inference precision
  (F32 / F16) and playback device (e.g. output to headphones).
- **On by default**; uncheck "开启" in the UI, or pass `--tts off` on the command line, to
  disable spoken output.
- ⚠️ **Please wear headphones to avoid feedback** — TTS plays through the system output device.
  If ASR captures system audio at the same time, the TTS audio is **captured back**, causing
  echo / self-oscillation / repeated words.
- The ASR capture path and the TTS playback path are independent, so there is no echo or
  self-pickup interference.
- **Only voice A (the preset voice) is bundled** — voice B and cloned-voice assets are
  deliberately not part of the package, so they are not offered in the UI either.
"""
EN_TTS_MARK = '### ⑤ Spoken translations (**a full feature, on by default**)'

# ── ② 「已知限制」里的 TTS 条目 ⇒ 正式功能版 ─────────────────────────────
ZH_LIMIT_OLD = """- **语音输出（TTS）为实验性功能**：当前存在杂音、音色突变、重复词，音质尚未通过抽听验收；
  默认关闭，字幕与翻译不受影响。
"""
ZH_LIMIT_NEW = """- **语音输出（TTS）已是正式功能，默认开启**；音质问题（杂音 / 音色突变 / 重复词）已修复并
  通过用户抽听验收。仍建议**佩戴耳机**使用，避免 TTS 声音被 ASR 回采。
"""

EN_LIMIT_OLD = """- **Speech output (TTS) is experimental**: the current path shows noise, abrupt timbre changes and repeated words; audio quality has not passed the listening-test acceptance. It is off by default; subtitles and translation are unaffected.
"""
EN_LIMIT_NEW = """- **Speech output (TTS) is now a full feature and is on by default**; the audio-quality issues
  (noise / abrupt timbre changes / repeated words) have been fixed and passed the listening test.
  Using **headphones** is still recommended so that the TTS audio is not captured back by ASR.
"""

# ── ③ 🔴 修掉「段切分…」重复两行的真实 bug ───────────────────────────
ZH_DUP_OLD = """- 段切分按能量静音判断，长时间无停顿的讲话会在 20 s 处强制切段，切点附近偶尔会断词。
- 段切分按能量静音判断，长时间无停顿的讲话会在 20 s 处强制切段，切点附近偶尔会断词。
"""
ZH_DUP_NEW = """- 段切分按能量静音判断，长时间无停顿的讲话会在 20 s 处强制切段，切点附近偶尔会断词。
"""

EN_DUP_OLD = """- Segmentation uses energy-based silence detection; long speech without pauses is cut at 20 s, which occasionally splits a word.
- Segmentation uses energy-based silence detection; long speech without pauses is cut at 20 s, which occasionally splits a word.
"""
EN_DUP_NEW = """- Segmentation uses energy-based silence detection; long speech without pauses is cut at 20 s, which occasionally splits a word.
"""

# kind='replace'：old → new（要求 old 命中恰好 1 次）
JOBS = {
    'README_zh.md': [
        ('TTS 段改正式功能', 'section', ZH_TTS_TITLE, ZH_TTS_NEW, ZH_TTS_MARK),
        ('已知限制 TTS 条目', 'replace', ZH_LIMIT_OLD, ZH_LIMIT_NEW,
         '已是正式功能，默认开启'),
        ('修重复的段切分行', 'dedup', ZH_DUP_OLD, ZH_DUP_NEW,
         '- 段切分按能量静音判断，长时间无停顿的讲话会在 20 s 处强制切段，切点附近偶尔会断词。\n'),
    ],
    'README_en.md': [
        ('TTS 段改正式功能', 'section', EN_TTS_TITLE, EN_TTS_NEW, EN_TTS_MARK),
        ('已知限制 TTS 条目', 'replace', EN_LIMIT_OLD, EN_LIMIT_NEW,
         'is now a full feature and is on by default'),
        ('修重复的段切分行', 'dedup', EN_DUP_OLD, EN_DUP_NEW,
         '- Segmentation uses energy-based silence detection; long speech without pauses is cut at 20 s, which occasionally splits a word.\n'),
    ],
}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    log = {'pkg': PKG, 'jobs': []}
    for fname, rules in JOBS.items():
        path = os.path.join(PKG, fname)
        if not os.path.isfile(path):
            log['jobs'].append({'file': fname, 'status': 'MISSING'})
            print('!! 文件不存在:', path)
            continue
        with open(path, 'rb') as f:
            raw = f.read()
        nl = '\r\n' if b'\r\n' in raw else '\n'
        txt = raw.decode('utf-8').replace('\r\n', '\n')

        applied, skipped = [], []
        for name, kind, a, b, mark in rules:
            if kind == 'section':
                # 🔴 **程序化定位整段**（标题 → 下一个 `## `）⇒ 不手抄原文
                if mark in txt:
                    skipped.append({'rule': name, 'reason': '标记已存在 ⇒ 幂等跳过'})
                    print('  [幂等跳过] %s / %s' % (fname, name))
                    continue
                cnt = txt.count(a)
                if cnt != 1:
                    raise SystemExit('段标题未唯一命中（%d 次）：%s / %s'
                                     % (cnt, fname, name))
                i = txt.index(a)
                j = txt.find('\n## ', i)
                if j < 0:
                    raise SystemExit('找不到段尾（下一个 `## `）：%s / %s' % (fname, name))
                old_seg = txt[i:j]
                txt = txt[:i] + b + txt[j:]
                applied.append(name)
                print('  [已应用] %s / %s（旧段 %d 字 → 新段 %d 字）'
                      % (fname, name, len(old_seg), len(b)))
                continue
            if kind == 'dedup':
                # 🔴 **专用去重判据**（重复的两行**不紧邻** ⇒ 不能按「相邻对」判）：
                #    看**单行**（mark）出现几次：
                #      1 次 ⇒ 已无重复 ⇒ 幂等跳过；
                #      2 次 ⇒ 去掉**第 2 次**；
                #      >2 ⇒ 异常 ⇒ 中止。
                cnt = txt.count(mark)
                if cnt == 1:
                    skipped.append({'rule': name, 'reason': '已无重复 ⇒ 幂等跳过'})
                    print('  [幂等跳过] %s / %s' % (fname, name))
                    continue
                if cnt != 2:
                    raise SystemExit('重复行出现 %d 次（期望 2）：%s / %s'
                                     % (cnt, fname, name))
                # 🔴 去掉**第 2 次**出现（保留第 1 次）
                i1 = txt.index(mark)
                i2 = txt.index(mark, i1 + len(mark))
                txt = txt[:i2] + txt[i2 + len(mark):]
                applied.append(name)
                print('  [已应用] %s / %s（去掉第 2 处重复）' % (fname, name))
                continue
            if mark in txt:
                skipped.append({'rule': name, 'reason': '标记已存在 ⇒ 幂等跳过'})
                print('  [幂等跳过] %s / %s' % (fname, name))
                continue
            cnt = txt.count(a)
            if cnt != 1:
                raise SystemExit('锚点未唯一命中（%d 次）：%s / %s' % (cnt, fname, name))
            txt = txt.replace(a, b)
            applied.append(name)
            print('  [已应用] %s / %s' % (fname, name))

        out = txt.replace('\n', nl).encode('utf-8')
        with open(path, 'wb') as f:
            f.write(out)

        # 🔴 写盘后重新读回校验
        with open(path, 'rb') as f:
            back = f.read().decode('utf-8').replace('\r\n', '\n')
        verify = []
        for name, kind, a, b, mark in rules:
            if kind == 'section':
                # 🔴 **程序化定位整段**（标题 → 下一个 `## `）⇒ 不手抄原文
                if mark in txt:
                    skipped.append({'rule': name, 'reason': '标记已存在 ⇒ 幂等跳过'})
                    print('  [幂等跳过] %s / %s' % (fname, name))
                    continue
                cnt = txt.count(a)
                if cnt != 1:
                    raise SystemExit('段标题未唯一命中（%d 次）：%s / %s'
                                     % (cnt, fname, name))
                i = txt.index(a)
                j = txt.find('\n## ', i)
                if j < 0:
                    raise SystemExit('找不到段尾（下一个 `## `）：%s / %s' % (fname, name))
                old_seg = txt[i:j]
                txt = txt[:i] + b + txt[j:]
                applied.append(name)
                print('  [已应用] %s / %s（旧段 %d 字 → 新段 %d 字）'
                      % (fname, name, len(old_seg), len(b)))
                continue
            if kind == 'dedup':
                # 去重规则：单行必须**恰好 1 次**
                v = {'rule': name, 'single_count': back.count(mark)}
                v['ok'] = (v['single_count'] == 1)
                verify.append(v)
                if not v['ok']:
                    raise SystemExit('写盘后校验失败: %s / %s -> %s'
                                     % (fname, name, v))
                continue
            # 🔴 **三态判据**（不能只看 mark）：
            #   ① mark 命中 ⇒ 新内容在（可能被跳过 ⇒ 也算已应用）
            #   ② old 不再命中 ⇒ 旧内容已消失
            #   ③ new（b）命中 ⇒ 目标内容在
            #   ⇒ 满足 (① 或 ②) 且 ③ ⇒ PASS
            v = {'rule': name, 'mark_count': back.count(mark),
                 'old_count': back.count(a), 'new_count': back.count(b)}
            v['ok'] = (v['new_count'] >= 1
                       and (v['mark_count'] >= 1 or v['old_count'] == 0))
            verify.append(v)
            if not v['ok']:
                raise SystemExit('写盘后校验失败: %s / %s -> %s' % (fname, name, v))

        log['jobs'].append({
            'file': fname,
            'status': 'PATCHED' if applied else 'NO_CHANGE',
            'applied': applied,
            'skipped': skipped,
            'verify': verify,
            'bytes_before': len(raw),
            'bytes_after': len(out),
            'sha256_before': sha256_bytes(raw),
            'sha256_after': sha256_bytes(out),
        })

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print()
    print('证据落盘:', OUT)
    n = sum(1 for j in log['jobs'] if j['status'] == 'PATCHED')
    print('改写 %d 个文件' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
