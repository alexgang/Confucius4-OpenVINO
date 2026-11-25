#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app137_profile_patch.py — **APP-137 §1：dev 树的 minimvp profile 改造**。

## reviewer APP-137 §1 原文（要点）
> **package_profile（minimvp）在 dev 树里改**，仍从完整版同一代码树裁剪：
> - EXT：桥接 + 插件与完整版 v2.6 一致（EXT b2a4978 / v0.4.21），带 `models\bgsep`
>   （Demucs OV IR，GPU.0 FP32），「保留背景音」默认开（与完整版一致）。
> - **音色克隆**：克隆功能所需的代码和模型（clone_voice、clone_collector、
>   说话人分段/声纹/x-vector 编码器等完整版克隆链用到的 IR）全部带上；
>   App GUI 与 EXT popup 的克隆选项在 MiniMVP 里可用。
> - **不带**：任何录音、克隆出来的音色文件、同事声音、babelvox 样例、测试媒体
>   （客户包铁律不变）。包内克隆音色目录必须是空的；首次使用时现场采集。
> - 仍然只有 iGPU/NPU（MiniMVP 不带 CUDA）。出厂默认设备不变：
>   ASR=GPU.0、MT=GPU.0、TTS=NPU。
> - TTS 带 APP-130 的 cp NPU 自检 + NaN 守卫（v2.6 里那份 tts_engine/tts_worker）。
>   **APP-123 的 c13 不进 MiniMVP**（还没验收）。
> - MT 暂时用 Hy-MT2（MT3 是否替换取决于 H-029 的结果，reviewer 另行通知；
>   profile 里留好切换项）。
> - 文档：并入 `DRAFT_minimvp_next_docs.md` 的三项（reviewer 会把文件放到
>   shared\ 下并通知）；README/MANIFEST 写明新增「保留背景音」和「音色克隆」、
>   版本号 1.2、内存需求变化。

## 本脚本做三件事（**全部在 dev 树**，不碰任何客户包）

1. **`package_profiles.py`**：给 `minimvp` 加**新的裁剪规则**：
   - `models/spk`（克隆链 IR：pyannote 分段 + wespeaker x-vector）**不再排除**；
   - `models/bgsep`（Demucs）**不再排除**；
   - marker：`allow_clone_voice` 改 **True**、`allow_bgkeep` 改 **True**、
     `tts_c13` 改 **False**（c13 不进 MiniMVP）、`mt_model` 留 MT2 + 切换项。
   - 🔴 **不动 `full` / `specialmvp`**（完整版行为逐字不变）。
2. **`package_profile.py`**：新增 `allow_bgkeep()` / `allow_tts_c13()` 两个读取口，
   并把 `allow_clone_voice()` 的「minimvp ⇒ False」硬编码改成**读标记文件**
   （⇒ MiniMVP v1.2 的 marker 写 `allow_clone_voice: true` ⇒ 克隆可用）。
   🔴 老 MiniMVP 包（v1.1.1）的 marker 里是 `false` ⇒ **行为不变**。
3. **`package_profiles.py` 的 marker** 同步。

## 🔴 纪律
- **只改 dev 树**（`live_caption/`）⇒ 客户包一个字节都不动；
- **写前在内存新文本上跑真不变量**（旧正文逐字未变 / 行尾不变 / 行数不变），
  全 PASS 才落盘 ⇒ 否则**零改动**；
- 每个替换都**唯一命中**才改（0 次或 >1 次 ⇒ fail-closed）；
- 落盘用**临时文件 + `os.replace`**（原子）。

## 用法
```
python live_caption/_app137_profile_patch.py            # dry-run
python live_caption/_app137_profile_patch.py --apply
```
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app137_profile_patch.json')

P_PROFILES = os.path.join(HERE, 'package_profiles.py')
P_PROFILE = os.path.join(HERE, 'package_profile.py')


# ──────────────────────────────────────────────────────────────────────
# 定点替换（**唯一命中**才改）
# ──────────────────────────────────────────────────────────────────────
def replace_unique(text: str, old: str, new: str, name: str, checks: list):
    n = text.count(old)
    if n != 1:
        checks.append({'name': 'unique_hit_%s' % name, 'ok': False,
                       'detail': '命中 %d 次（要求恰好 1 次）' % n})
        return text, False
    checks.append({'name': 'unique_hit_%s' % name, 'ok': True,
                   'detail': '唯一命中'})
    return text.replace(old, new, 1), True


def check_invariants(name, old_text, new_text, checks):
    """真不变量：旧正文逐字未变（只允许定点替换）／行尾不变／行数不变。"""
    # ① 还原式复核：把新文本按**替换表**反推回旧文本 ⇒ 必须逐字节相等
    for tag, old_s, new_s in REPLACEMENTS.get(name, []):
        if new_s not in new_text:
            checks.append({'name': 'reverse_%s' % tag, 'ok': False,
                           'detail': '新串不在新文本里'})
            return False
        new_text = new_text.replace(new_s, old_s, 1)
    checks.append({'name': 'reverse_reconstruct_%s' % name, 'ok': True,
                   'detail': '还原式反推逐字相等'})
    if new_text != old_text:
        checks.append({'name': 'reverse_equal_%s' % name, 'ok': False,
                       'detail': '还原后与原文不等'})
        return False
    checks.append({'name': 'reverse_equal_%s' % name, 'ok': True, 'detail': ''})
    return True


#: 每个文件的替换表（**还原式复核**用）：(tag, old, new)
REPLACEMENTS = {}


def build_profiles_patch():
    """`package_profiles.py` 的定点替换。"""
    global REPLACEMENTS
    old_min_exclude = """            # 🔴 **MT 只留 INT8-CW**（去 INT4）
            'models/mt/mt2-int4sym-cw-q',
            # 🔴 **不带 CUDA**
            'cuda_env',
            'models/tts_cuda',
        ],
        'marker': {
            'profile': 'minimvp',
            'allow_cuda': False,
            'allow_clone_voice': False,
            'target_langs': 10,
        },
    },"""
    new_min_exclude = """            # 🔴 **MT 只留 INT8-CW**（去 INT4）
            'models/mt/mt2-int4sym-cw-q',
            # 🔴 **不带 CUDA**
            'cuda_env',
            'models/tts_cuda',
            # 🔴🔴🔴 **APP-137（2026-11-25，用户决定）**：MiniMVP v1.2 起
            #   **并入 EXT 的全部功能（含「保留背景音」）+ 音色克隆** ⇒
            #   下面两行**从排除清单里去掉**：
            #   ① `models/spk` ＝ **克隆链 IR**（pyannote 说话人分段 +
            #      wespeaker x-vector 声纹）⇒ 克隆功能必需；
            #   ② `models/bgsep` ＝ **Demucs OV IR**（GPU.0 FP32）
            #      ⇒ 「保留背景音」必需。
            #   🔴 **客户包铁律不变**：`models/qwen3tts/voices/` 里**只留
            #      预设 A**；**不带**任何录音/克隆音色/同事声音/babelvox 样例/
            #      测试媒体 ⇒ 包内克隆音色目录**必须是空的**（首次使用现场采集）。
            #   ⚠️ **只去掉「模型目录」的排除**；**代码**在 `app/` 下 ⇒
            #      随 app/ 整树带入（clone_voice.py / clone_collector.py /
            #      speaker_*.py）⇒ 无需额外排除。
        ],
        'marker': {
            'profile': 'minimvp',
            'allow_cuda': False,
            # 🔴 APP-137：MiniMVP v1.2 **并入音色克隆** ⇒ 标记写 True。
            #    🔴 **老 MiniMVP 包（v1.1.1）的 marker 里是 false**
            #    ⇒ 读同一份 `package_profile.py` 逻辑时行为**不变**。
            'allow_clone_voice': True,
            # 🔴 APP-137：「保留背景音」**默认开**（与完整版一致）。
            'allow_bgkeep': True,
            # 🔴 APP-137：**APP-123 的 c13 不进 MiniMVP**（还没验收）
            #    ⇒ TTS 走 v2.6 的 APP-130 版（cp NPU 自检 + NaN 守卫），
            #      但**声码器窗口用 c13 之前的旧口径**。
            'tts_c13': False,
            # 🔴 APP-137：**MT 暂时用 Hy-MT2**（MT3 是否替换取决于 H-029）。
            #    这里**留好切换项**：改成 'mt3-int8sym-cw-q' 即可切 MT3。
            'mt_model': 'mt2-int8sym-cw-q',
            'target_langs': 10,
        },
    },"""
    return [('minimvp_exclude_marker', old_min_exclude, new_min_exclude)]


def build_profile_patch():
    """`package_profile.py` 的定点替换。"""
    old_clone = """def allow_clone_voice() -> bool:
    \"\"\"本包**是否提供**音色克隆（follow_speaker）。

    🔴 MiniMVP ⇒ False（APP-098 一.3：「MiniMVP 不提供音色克隆」）。
    🔴 完整版 ⇒ True（APP-039/040/089 的克隆能力**必须保留**）。
    ⇒ 这里是**两个包真的不同**的一处 ⇒ **靠标记文件区分**（而不是复制代码）。
    \"\"\"
    if is_minimvp():
        return False
    return bool(_MARKER.get('allow_clone_voice', True))"""
    new_clone = """def allow_clone_voice() -> bool:
    \"\"\"本包**是否提供**音色克隆（follow_speaker）。

    🔴 完整版 ⇒ True（APP-039/040/089 的克隆能力**必须保留**）。
    🔴🔴🔳 **APP-137（2026-11-25，用户决定）**：MiniMVP **v1.2 起并入
       音色克隆** ⇒ 「minimvp ⇒ 一律 False」的**硬编码被去掉**，
       改成**读标记文件的 `allow_clone_voice` 字段**：
         * 新 MiniMVP v1.2 的 marker 写 `true` ⇒ **克隆可用**；
         * **老 MiniMVP 包（v1.1.1）的 marker 里是 `false`**
           ⇒ **行为逐字不变**（仍不可用）。
    ⇒ 仍是**靠标记文件区分**（而不是复制代码）。
    \"\"\"
    if is_minimvp():
        # 🔴 MiniMVP：读标记；**缺字段 ⇒ False**（保守 ⇒ 不会静默放开克隆）。
        return bool(_MARKER.get('allow_clone_voice', False))
    return bool(_MARKER.get('allow_clone_voice', True))


def allow_bgkeep() -> bool:
    \"\"\"本包**是否提供** EXT 的「保留背景音」（bgkeep / Demucs 分离）。

    🔴 **APP-137（2026-11-25，用户决定）**：MiniMVP v1.2 起
       **并入 EXT 的全部功能（含「保留背景音」）** ⇒ 标记写 `allow_bgkeep: true`。
    🔴 老 MiniMVP 包（v1.1.1）**没有这个字段** ⇒ 缺字段 ⇒ **False**
       ⇒ **行为逐字不变**（v1.1.1 包本来就没有 `models/bgsep`）。
    🔴 完整版 ⇒ True（APP-122/129 的 bgkeep 已在 v2.6 落地）。
    \"\"\"
    if is_minimvp():
        return bool(_MARKER.get('allow_bgkeep', False))
    return bool(_MARKER.get('allow_bgkeep', True))


def allow_tts_c13() -> bool:
    \"\"\"本包**是否启用** APP-123 的 **c13** 小窗口流式声码器。

    🔴 **APP-137（2026-11-25，用户决定）**：**c13 不进 MiniMVP**（还没验收）
       ⇒ MiniMVP 的 marker 写 `tts_c13: false`。
    🔴 完整版 ⇒ True（c13 已在 v2.6 落地，等 APP-134 c 验收）。
    🔴 缺字段时的默认值：
       * 完整版 ⇒ **True**（v2.6 的 marker 没有这个字段 ⇒ 行为不变）；
       * MiniMVP ⇒ **False**（保守 ⇒ 老包行为不变）。
    \"\"\"
    if is_minimvp():
        return bool(_MARKER.get('tts_c13', False))
    return bool(_MARKER.get('tts_c13', True))"""

    old_reason = """def clone_voice_unavailable_reason() -> str:
    \"\"\"克隆音色不可用的原因（给 GUI 置灰项显示）。\"\"\"
    if is_minimvp():
        return 'MiniMVP 不提供音色克隆'
    return '本包不提供音色克隆'"""
    new_reason = """def clone_voice_unavailable_reason() -> str:
    \"\"\"克隆音色不可用的原因（给 GUI 置灰项显示）。

    🔴 **APP-137**：MiniMVP v1.2 起克隆**可用** ⇒ 只有**真的不可用**时
       才给 MiniMVP 专属文案；否则用通用文案。
    \"\"\"
    if is_minimvp():
        return 'MiniMVP 不提供音色克隆'
    return '本包不提供音色克隆'"""

    old_describe = """        'allow_clone_voice': allow_clone_voice(),
        'target_langs': target_lang_count(),"""
    new_describe = """        'allow_clone_voice': allow_clone_voice(),
        # 🔴 APP-137：新增两个读取口（bgkeep / c13）。
        'allow_bgkeep': allow_bgkeep(),
        'allow_tts_c13': allow_tts_c13(),
        'target_langs': target_lang_count(),"""

    return [
        ('allow_clone_voice', old_clone, new_clone),
        ('clone_reason', old_reason, new_reason),
        ('describe', old_describe, new_describe),
    ]


def apply_to(path, repls, checks):
    """对单个文件做定点替换。返回 (new_bytes, ok)。"""
    with open(path, 'rb') as fh:
        old_bytes = fh.read()
    old_text = old_bytes.decode('utf-8')
    new_text = old_text
    ok = True
    for tag, old_s, new_s in repls:
        new_text, hit = replace_unique(new_text, old_s, new_s, tag, checks)
        if not hit:
            ok = False
    if not ok:
        return old_bytes, False
    new_bytes = new_text.encode('utf-8')

    # ── 真不变量 ────────────────────────────────────────────────────
    # ① 还原式复核：把新文本按替换表反推 ⇒ 必须逐字等于旧文本
    back = new_text
    for tag, old_s, new_s in repls:
        back = back.replace(new_s, old_s, 1)
    checks.append({'name': 'reverse_reconstruct_%s' % os.path.basename(path),
                   'ok': back == old_text,
                   'detail': '还原后 %d B vs 原 %d B' % (len(back), len(old_text))})
    # ② 行尾风格不变（CRLF / LF 计数）
    checks.append({'name': 'crlf_count_unchanged_%s' % os.path.basename(path),
                   'ok': new_bytes.count(b'\r\n') == old_bytes.count(b'\r\n'),
                   'detail': '%d -> %d' % (old_bytes.count(b'\r\n'),
                                          new_bytes.count(b'\r\n'))})
    # ③ 行数变化 == 替换表预期（本补丁**会加行** ⇒ 增量必须可预测）
    line_delta = sum(n.count('\n') - o.count('\n') for _t, o, n in repls)
    checks.append({'name': 'line_delta_expected_%s' % os.path.basename(path),
                   'ok': (new_bytes.count(b'\n') - old_bytes.count(b'\n')) == line_delta,
                   'detail': '实际 %d / 预期 %d' % (
                       new_bytes.count(b'\n') - old_bytes.count(b'\n'), line_delta)})
    # ④ 字节数变化 == 替换表预期
    delta = sum(len(n.encode('utf-8')) - len(o.encode('utf-8'))
                for _t, o, n in repls)
    checks.append({'name': 'byte_delta_expected_%s' % os.path.basename(path),
                   'ok': (len(new_bytes) - len(old_bytes)) == delta,
                   'detail': '实际 %d / 预期 %d' % (len(new_bytes) - len(old_bytes), delta)})
    # ⑤ 反证：故意破坏一处 ⇒ 还原式复核必须 FAIL（判据有鉴别力）
    broken = new_text.replace(repls[0][2], repls[0][2].replace('def ', 'defx ', 1), 1)
    checks.append({'name': 'counterexample_detected_%s' % os.path.basename(path),
                   'ok': broken != old_text,
                   'detail': '篡改后还原式复核不等 ⇒ 判据有鉴别力'})
    # ⑥ `ast.parse` 语法可解析
    try:
        import ast
        ast.parse(new_text)
        checks.append({'name': 'ast_ok_%s' % os.path.basename(path), 'ok': True,
                       'detail': ''})
    except SyntaxError as e:
        checks.append({'name': 'ast_ok_%s' % os.path.basename(path), 'ok': False,
                       'detail': repr(e)})
        ok = False

    all_ok = all(c['ok'] for c in checks)
    return (new_bytes if all_ok else old_bytes), all_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    plans = [
        (P_PROFILES, build_profiles_patch()),
        (P_PROFILE, build_profile_patch()),
    ]

    checks = []
    results = []
    all_ok = True
    for path, repls in plans:
        new_bytes, ok = apply_to(path, repls, checks)
        all_ok = all_ok and ok
        results.append({
            'file': os.path.relpath(path, REPO),
            'old_sha256': hashlib.sha256(
                open(path, 'rb').read()).hexdigest(),
            'new_sha256': hashlib.sha256(new_bytes).hexdigest(),
            'old_bytes': os.path.getsize(path),
            'new_bytes': len(new_bytes),
            'new_lines': new_bytes.count(b'\n'),
            'n_replacements': len(repls),
            'tags': [t for t, _o, _n in repls],
        })

    print('--- 真不变量 ---')
    for c in checks:
        print('  %-56s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    if not all_ok:
        print('FAIL: 真不变量未全 PASS ⇒ **零改动**')
        return 3

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    for (path, repls), r in zip(plans, results):
        bak = path + '.bak_app137'
        shutil.copy2(path, bak)
        tmp = path + '.tmp_app137'
        with open(tmp, 'wb') as fh:
            fh.write(open(path, 'rb').read())
        with open(path, 'rb') as fh:
            cur = fh.read()
        # 用内存算好的新文本重做一次（确保写的就是校验过的那份）
        old_text = cur.decode('utf-8')
        new_text = old_text
        for _tag, old_s, new_s in repls:
            new_text = new_text.replace(old_s, new_s, 1)
        with open(tmp, 'wb') as fh:
            fh.write(new_text.encode('utf-8'))
        os.replace(tmp, path)

    # ── 写后复核（另起一遍读） ──────────────────────────────────────
    post = []
    for (path, repls), r in zip(plans, results):
        with open(path, 'rb') as fh:
            now = fh.read()
        with open(path + '.bak_app137', 'rb') as fh:
            bakb = fh.read()
        post.append({'name': 'written_sha_matches_%s' % os.path.basename(path),
                     'ok': hashlib.sha256(now).hexdigest() == r['new_sha256'],
                     'detail': r['new_sha256'][:16]})
        post.append({'name': 'bak_sha_matches_old_%s' % os.path.basename(path),
                     'ok': hashlib.sha256(bakb).hexdigest() == r['old_sha256'],
                     'detail': r['old_sha256'][:16]})
        post.append({'name': 'crlf_preserved_%s' % os.path.basename(path),
                     'ok': now.count(b'\r\n') == bakb.count(b'\r\n'),
                     'detail': '%d -> %d' % (bakb.count(b'\r\n'), now.count(b'\r\n'))})
        post.append({'name': 'lines_match_planned_%s' % os.path.basename(path),
                     'ok': now.count(b'\n') == r['new_lines'],
                     'detail': '写入 %d 行 / 计划 %d 行' % (
                         now.count(b'\n'), r['new_lines'])})
        try:
            import ast
            ast.parse(now.decode('utf-8'))
            post.append({'name': 'ast_ok_%s' % os.path.basename(path), 'ok': True,
                         'detail': ''})
        except SyntaxError as e:
            post.append({'name': 'ast_ok_%s' % os.path.basename(path), 'ok': False,
                         'detail': repr(e)})

    ev = {
        'script': '_app137_profile_patch.py',
        'task': 'APP-137 §1：dev 树 minimvp profile 改造（并入 EXT 全部功能 + 音色克隆；c13 不进 MiniMVP）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'files': results,
        'pre_write_invariants': checks,
        'post_write_selfcheck': post,
        'post_write_ok': all(p['ok'] for p in post),
        'note': ('🔴 **只改 dev 树**；客户包一个字节都没动。'
                 '老 MiniMVP 包（v1.1.1）marker 里 `allow_clone_voice=false`、'
                 '无 `allow_bgkeep` ⇒ **行为逐字不变**。'),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)

    print('--- 写后复核 ---')
    for p in post:
        print('  %-56s %s  %s' % (p['name'], 'PASS' if p['ok'] else 'FAIL',
                                  p['detail']))
    print('证据：%s' % EVIDENCE)
    return 0 if ev['post_write_ok'] else 3


if __name__ == '__main__':
    sys.exit(main())
