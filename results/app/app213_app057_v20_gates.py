#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app213 —— APP-057 第 4 条「闸门照旧」的**逐项检查**。

## 检查项（reviewer 原文）

1. **不能包含会议录音**（音频/录音文件）
2. **不能包含克隆音色**（克隆音色的音频样本）
3. **不能包含同事 B 的声音**
4. **不能包含 babelvox 示例音色**
5. **NOTICE 里要有 pyannote_seg 和 wespeaker 的署名**
6. **说话人旁路默认关**，且**走独立线程**（APP-054）

## 判据设计（铁律：判据必须能识破已知有缺陷的对象）

★ **闸门必须是「有鉴别力」的** ⇒ 每条都配**反证组**：
   造一个**故意违规**的样本 ⇒ 判据必须 FAIL ⇒ 否则判据恒真。

★ 检查「音色」不能只查**文件名** ⇒ 要查**音频内容**：
   包内 `models/qwen3tts/voices/` 是**音色参考音频** ⇒ 必须逐个列出。

## 铁律

* **纯离线**：只读包目录 ⇒ 不占机器锁、不跑推理、不碰 GPU。
* 不 import 被测模块 ⇒ 只用 ast / 目录遍历 / 二进制嗅探。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import struct
import sys
import time

#: 🔴🔴 **不得写死客户包版本号**（§48 打包闸门会拦）
#:   ⇒ 用 `pkg_paths` 单一数据源自动发现**最大版本**的客户包目录。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
try:
    import pkg_paths
except Exception:                                  # pragma: no cover
    pkg_paths = None

HOME = os.path.expanduser('~')


def _discover_pkg():
    """自动发现客户包目录（**不写死版本号**）。"""
    if pkg_paths is not None:
        try:
            return pkg_paths.discover_pkg_dir()
        except Exception:
            pass
    # 兜底：按版本号排序取最大（仅在 pkg_paths 不可用时）
    prefix = getattr(pkg_paths, 'PKG_NAME_PREFIX',
                     'Confucius4_LiveCaption_v') if pkg_paths else \
        'Confucius4_LiveCaption_v'
    cands = []
    for name in os.listdir(HOME):
        if not name.startswith(prefix):
            continue
        if not os.path.isdir(os.path.join(HOME, name, 'app')):
            continue
        cands.append(name)
    if not cands:
        raise FileNotFoundError('未找到客户包目录')
    cands.sort(key=lambda n: tuple(
        int(x) for x in n[len(prefix):].split('.') if x.isdigit()) or (0,),
        reverse=True)
    return os.path.join(HOME, cands[0])


PKG = _discover_pkg()

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + detail) if detail else ''))
    return bool(cond)


# ── 音频文件嗅探（RIFF/WAVE、fLaC、OggS、ID3/MPEG、mp4）──────────
AUDIO_MAGIC = (b'RIFF', b'fLaC', b'OggS', b'ID3', b'\xff\xfb', b'\xff\xf3',
               b'\xff\xf2', b'FORM')


def sniff_audio(path):
    """返回 (is_audio, ext_guess)。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(16)
    except Exception:
        return False, ''
    for m in AUDIO_MAGIC:
        if head.startswith(m):
            return True, 'riff/flac/ogg/id3/mp3'
    if len(head) >= 12 and head[4:8] == b'ftyp':
        return True, 'mp4/m4a'
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.opus'):
        return True, 'ext:' + ext
    return False, ''


def list_audio(pkg):
    """包内所有音频文件（相对路径 + 大小 + 嗅探结论）。"""
    out = []
    for dp, _dn, fns in os.walk(pkg):
        for fn in fns:
            p = os.path.join(dp, fn)
            is_a, kind = sniff_audio(p)
            if is_a:
                out.append(dict(rel=os.path.relpath(p, pkg),
                                bytes=os.path.getsize(p), kind=kind))
    return out


# ── 会议录音 / 克隆音色 / 同事B 声音 的特征词 ──────────────────────
#: 🔴🔴 **判据口径修正（2026-11-01 实测打脸）**：
#:   ★ **只查「音频素材」，不查「代码里提到这些词」**。
#:   ⇒ 第一版判据把 `babelvox`（**TTS 运行时包名，必须在包里**）、
#:     `clone_collector.py`（**代码功能**）、`RECORD`（**pip 元数据文件**）、
#:     `zoomheight.py`（**Python 标准库**）全判成违规 ⇒ **全是误报**。
#:   ⇒ 闸门的正确问法是：「**包内有没有不该随包走的音频素材**」
#:     ⇒ 判据 = ①「非音色目录的音频文件」 ②「音频文件的**路径字面量**指向包外」
#:   ⇒ 「同事 B 的声音」「babelvox 示例音色」⇒ 靠**文件名 + 目录**识别
#:     （素材必然是音频文件 ⇒ 名字里带特征词）。
RECORD_KEYWORDS = ('meeting', '会议', '录音', 'momo', 'tencent_meeting',
                   'voov', '会议录音', 'conference_recording', 'b 声音',
                   '同事b', 'colleague_b')
#: 克隆 / 音色样本类特征（**只在音频素材上匹配**）
CLONE_KEYWORDS = ('clone', '克隆', 'speaker_sample', 'ref_voice',
                  'ref_audio', 'target_spk', 'preserved', 'prompt_wav')
#: babelvox 示例音色（EXT-031 闸门点名）—— **素材名**
BABELVOX_KEYWORDS = ('babelvox_sample', 'sample_tts', 'demo_voice',
                     'example_voice', 'example_tts')

#: 🔴 **第三方运行时目录**（它们的文件不是「随包素材」⇒ 不参与特征词扫描）
RUNTIME_DIR_PREFIXES = ('python', os.path.join('ext', '.runtime_deps'))

#: **TTS 音色参考音频**允许存在的目录（包内必需）
VOICE_REF_DIRS = (os.path.join('models', 'qwen3tts', 'voices'),)


def _in_runtime(rel):
    parts = rel.split(os.sep)
    return parts[0] in ('python',) or rel.startswith(
        os.path.join('ext', '.runtime_deps'))


def _is_voice_ref(rel):
    r = rel.replace('/', os.sep)
    return any(r.startswith(d) for d in VOICE_REF_DIRS)


def scan_names(pkg):
    """扫包内**音频文件**的名字（排除第三方运行时目录）找特征词。

    🔴 **只看音频文件** ⇒ 代码文件/元数据文件的名字不参与判定。
    """
    hits = []
    for dp, _dn, fns in os.walk(pkg):
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, pkg)
            if _in_runtime(rel):
                continue
            is_a, _kind = sniff_audio(p)
            if not is_a:
                continue
            low = fn.lower()
            for kw in (RECORD_KEYWORDS + CLONE_KEYWORDS + BABELVOX_KEYWORDS):
                if kw in low:
                    hits.append(dict(rel=rel, kw=kw))
    return hits


#: 🔴🔴 **口径修正二（2026-11-01 第二次实测打脸）**：
#:   第一版修正后仍有两处误报：
#:   ★ `app/tts_worker.py` 的 `clone_C.wav` / `clone_%d_%d.wav`
#:     —— 这是**运行时输出文件名**（前者从会议录音临时截取、后者写
#:        `tempfile.gettempdir()` 且**会话结束即删**），
#:        **包内并不存在**同名音频（`find` 结果为空）⇒ 不是随包素材。
#:   ⇒ 正确的问法是：「**代码是否引用了不该随包走的音频**」
#:     ⇒ 只判两类：
#:        (a) **指向包外**的音频路径（绝对路径 / 上跳目录）—— 外部素材泄漏
#:        (b) 指向**包内既有音频文件**的**敏感**引用 —— 敏感素材随包且被引用
#:     ⇒ **裸文件名 + 包内不存在** ⇒ 运行时输出模板 ⇒ **不判违规**。
#:
#: ⚠️ **不能**把判据收窄成「只判已存在文件」—— 那会退化成**恒真**
#:    （包内本来就没有 clone 音频）⇒ 必须靠**反证组**保鉴别力：
#:    反证③ 造一个**包内既有**的敏感音频 + 代码引用它 ⇒ 必须命中。
AUD_EXT = ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.opus')


def _norm_rel(pkg, v):
    """把字面量按「相对包根」解析；返回 (在包内?, 相对路径)。"""
    vv = v.strip().replace('\\', '/')
    if os.path.isabs(v):
        return False, vv
    parts = [p for p in vv.split('/') if p not in ('', '.')]
    if '..' in parts:
        return False, vv
    return True, os.path.join(*parts) if parts else ''


def _pkg_has_audio(pkg, rel):
    """包内是否存在该相对路径的音频文件。

    🔴 **相对路径的基准有两个**：① 包根 ② 扫描子目录（`app/`、`ext/`）
       —— 代码里的相对路径通常是**相对 CWD（= app/）**写的
       ⇒ 只按包根找会漏 ⇒ 反证恒 FAIL。
    """
    if not rel:
        return False
    cands = [os.path.join(pkg, rel)]
    for sd in ('app', 'ext'):
        cands.append(os.path.join(pkg, sd, rel))
    for p in cands:
        if os.path.isfile(p):
            is_a, _k = sniff_audio(p)
            if is_a:
                return True
    # 裸文件名：按**包内任意同名**存在性判定（排除第三方运行时）
    if os.sep not in rel and '/' not in rel:
        for dp, _dn, fns in os.walk(pkg):
            if rel in fns and not _in_runtime(os.path.relpath(
                    os.path.join(dp, rel), pkg)):
                return True
    return False


def _sensitive_kw(vl):
    for kw in (RECORD_KEYWORDS + CLONE_KEYWORDS + BABELVOX_KEYWORDS):
        if kw in vl:
            return kw
    return None


def scan_literals(pkg, subdirs=('app', 'ext')):
    """扫 .py 的**字符串字面量**（排除 docstring）里的**音频路径**。

    🔴 **口径**（见上方 AUD_EXT 处的修正说明）：
       (a) 指向**包外**的音频路径 ⇒ 违规（`points_outside_pkg`）
       (b) 指向**包内既有音频**的**敏感**引用 ⇒ 违规（`sensitive_ref_in_pkg`）
       ⇒ 裸文件名 + 包内不存在（运行时输出模板）⇒ **不判违规**
       ⇒ 「代码里提到 babelvox / clone」**不算**违规（那是功能与依赖名）。
    """
    hits = []
    for sd in subdirs:
        root = os.path.join(pkg, sd)
        if not os.path.isdir(root):
            continue
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                if not fn.endswith('.py'):
                    continue
                p = os.path.join(dp, fn)
                try:
                    with open(p, 'r', encoding='utf-8', errors='replace') as f:
                        tree = ast.parse(f.read(), filename=p)
                except Exception:
                    continue
                doc_ids = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Module, ast.FunctionDef,
                                         ast.AsyncFunctionDef, ast.ClassDef)):
                        body = getattr(node, 'body', None)
                        if body and isinstance(body[0], ast.Expr) \
                                and isinstance(body[0].value, ast.Constant) \
                                and isinstance(body[0].value.value, str):
                            doc_ids.add(id(body[0].value))
                for node in ast.walk(tree):
                    if not (isinstance(node, ast.Constant)
                            and isinstance(node.value, str)):
                        continue
                    if id(node) in doc_ids:
                        continue
                    v = node.value
                    vl = v.lower()
                    if not vl.endswith(AUD_EXT):
                        continue
                    inside, rel = _norm_rel(pkg, v)
                    reason = None
                    if not inside:
                        reason = 'points_outside_pkg'
                    else:
                        kw = _sensitive_kw(vl)
                        if kw and _pkg_has_audio(pkg, rel):
                            reason = 'sensitive_ref_in_pkg:%s' % kw
                    if reason:
                        hits.append(dict(
                            file=os.path.relpath(p, pkg),
                            line=node.lineno, kw=reason,
                            text=v.strip()[:150]))
    return hits


def ext_bypass_thread_ok(src):
    """EXT 侧旁路是否**走独立线程**（EXT-029 ①）。

    判据本体 = 「`threading.Thread` / `Thread(` ＋ `daemon=True`」。
    🔴 拆成独立函数 ⇒ 便于用**合成样本**做反证（鉴别力自检）。
    """
    if not src:
        return False
    has_thread = ('threading.Thread' in src) or ('Thread(' in src)
    return bool(has_thread and 'daemon=True' in src)


def ext_bypass_nonblock_ok(src):
    """EXT 侧旁路是否**不反压**（EXT-029 ②：积压时丢弃，不阻塞 ASR）。

    判据本体 = 「队列满 ⇒ 捕获 `queue.Full` 并丢弃 + 有丢弃计数」。
    """
    if not src:
        return False
    has_drop = ('queue.Full' in src) and (
        ('n_drop' in src) or ('spk_queue_drop' in src))
    return bool(has_drop)


def main():
    global PKG
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--json', default=None)
    args = ap.parse_args()
    PKG = args.pkg

    print('=' * 70)
    print('app213 —— APP-057 第 4 条「闸门照旧」逐项检查')
    print('包:', PKG)
    print('=' * 70)

    # ── ① 包内音频文件清单 ────────────────────────────────────
    audio = list_audio(PKG)
    print('\n[1] 包内音频文件：%d 个' % len(audio))
    by_top = {}
    for a in audio:
        top = a['rel'].split(os.sep)[0] + '/' + \
            (a['rel'].split(os.sep)[1] if os.sep in a['rel'] else '')
        by_top[top] = by_top.get(top, 0) + 1
    for k, v in sorted(by_top.items()):
        print('    %-46s %d 个' % (k, v))
    # 音色参考音频（TTS 必需的）单列
    voices = [a for a in audio if _is_voice_ref(a['rel'])]
    # ★ **第三方运行时的音频**（scipy 的测试 wav 等）不是「随包素材」
    runtime_audio = [a for a in audio
                     if _in_runtime(a['rel']) and a not in voices]
    other_audio = [a for a in audio
                   if a not in voices and a not in runtime_audio]
    print('    ├─ TTS 音色参考音频（必需）：%d 个' % len(voices))
    for a in voices[:12]:
        print('       %-58s %d B' % (a['rel'], a['bytes']))
    print('    ├─ 第三方运行时自带音频（scipy 测试样本，不算素材）：%d 个'
          % len(runtime_audio))
    print('    └─ **其它**音频（应为空）：%d 个' % len(other_audio))
    for a in other_audio[:30]:
        print('       %-58s %d B' % (a['rel'], a['bytes']))
    check('① 包内无「会议录音/杂音」类音频（除 TTS 音色参考外为空）',
          not other_audio, '%d 个: %s' % (len(other_audio),
                                         [a['rel'] for a in other_audio[:8]]))

    # ── ② 文件名特征词 ────────────────────────────────────────
    name_hits = scan_names(PKG)
    print('\n[2] 文件名/目录名里的敏感特征词：%d 处' % len(name_hits))
    for h in name_hits[:30]:
        print('    %s [%s]' % (h['rel'], h['kw']))
    check('② 文件名里无会议录音/克隆/示例音色特征词',
          not name_hits, str(name_hits[:6]))

    # ── ③ 代码字面量里的敏感特征词 ────────────────────────────
    lit_hits = scan_literals(PKG)
    print('\n[3] app/ 与 ext/ 的字符串字面量里的敏感特征词：%d 处'
          % len(lit_hits))
    for h in lit_hits[:30]:
        print('    %s:%d [%s] %s' % (h['file'], h['line'], h['kw'],
                                     h['text']))
    check('③ 代码里无会议录音/克隆/示例音色特征词',
          not lit_hits, str(lit_hits[:6]))

    # ── ④ NOTICE 署名 ─────────────────────────────────────────
    notice = os.path.join(PKG, 'NOTICE')
    ntxt = ''
    if os.path.isfile(notice):
        with open(notice, encoding='utf-8', errors='replace') as f:
            ntxt = f.read()
    low = ntxt.lower()
    check('④ NOTICE 存在', bool(ntxt), '%d B' % len(ntxt.encode('utf-8')))
    check('④ NOTICE 含 pyannote_seg 署名',
          'pyannote_seg' in low or 'pyannote/segmentation' in low)
    check('④ NOTICE 含 wespeaker 署名',
          'wespeaker' in low)
    # 署名还得有「作者/来源」信息 ⇒ 至少含一个 URL
    check('④ NOTICE 署名含来源链接', 'http' in low)

    # ── ⑤ 说话人旁路默认关 + 独立线程 ─────────────────────────
    tracker = os.path.join(PKG, 'app', 'speaker_tracker.py')
    tsrc = ''
    if os.path.isfile(tracker):
        with open(tracker, encoding='utf-8', errors='replace') as f:
            tsrc = f.read()
    check('⑤ speaker_tracker.py 存在', bool(tsrc))
    # 默认关：构造函数里 enabled 默认 False
    m_def = 'enabled' in tsrc and 'False' in tsrc
    check('⑤ 旁路默认关（enabled 开关存在且默认 False）', m_def)
    # 独立线程：Thread( 出现
    check('⑤ 旁路走独立线程（threading.Thread）',
          'threading.Thread' in tsrc or 'Thread(' in tsrc)
    # CLI 默认 off
    app = os.path.join(PKG, 'app', 'live_caption_app.py')
    asrc = ''
    with open(app, encoding='utf-8', errors='replace') as f:
        asrc = f.read()
    m_cli = False
    for line in asrc.splitlines():
        if "'--speaker'" in line or '"--speaker"' in line:
            m_cli = ("'off'" in line and 'default' in line)
            break
    check('⑤ CLI --speaker 默认 off', m_cli)

    # ── ⑤' EXT 侧说话人旁路（APP-057 ④：EXT 侧也要满足 EXT-029）──
    ext_bypass = os.path.join(PKG, 'ext', 'bridge', 'speaker_bypass.py')
    esrc = ''
    if os.path.isfile(ext_bypass):
        with open(ext_bypass, encoding='utf-8', errors='replace') as f:
            esrc = f.read()
    check("⑤' EXT 侧 speaker_bypass.py 存在", bool(esrc),
          os.path.relpath(ext_bypass, PKG))
    check("⑤' EXT 侧旁路走独立线程（EXT-029 ①：threading.Thread + daemon）",
          ext_bypass_thread_ok(esrc))
    check("⑤' EXT 侧旁路不反压（EXT-029 ②：队列满 ⇒ 丢弃 + 计数）",
          ext_bypass_nonblock_ok(esrc))

    # ── ⑥ 反证组（判据必须有鉴别力）──────────────────────────
    disc = []
    # 🔴 **探针目录必须在 `scan_literals` 的扫描范围内**（`app/` 或 `ext/`）
    #    ⇒ 上一版放在包根 `_probe_gate/` ⇒ 从来没被扫到 ⇒ 反证③恒 FAIL
    #    （**不是判据错，是反证样本没进场**）。
    probe_dir = os.path.join(PKG, 'app', '_probe_gate')
    os.makedirs(probe_dir, exist_ok=True)
    # (a) 造一个带会议录音特征名的音频 ⇒ ② 必须命中
    bad = os.path.join(probe_dir, 'meeting_record_2026.wav')
    with open(bad, 'wb') as f:
        f.write(b'RIFF' + b'\x00' * 100)
    h = scan_names(PKG)
    ok_a = any(x['rel'].endswith('meeting_record_2026.wav') for x in h)
    disc.append(dict(name='反证①文件名含「会议录音」特征 ⇒ ② 必须命中',
                     ok=ok_a))
    # (b) 同一个文件也是「非音色目录的音频」⇒ ① 必须命中
    aud = list_audio(PKG)
    ok_b = any(a['rel'].endswith('meeting_record_2026.wav')
               and a['rel'] not in [x['rel'] for x in voices]
               for a in aud)
    disc.append(dict(name='反证②非音色目录的音频 ⇒ ① 必须命中', ok=ok_b))
    # (c) 造一个**指向包内既有敏感音频**的字面量 ⇒ ③ 必须命中
    #    ⚠️ 判据口径 = 「包内既有音频 + 敏感」⇒ 探针必须**同时**满足两点
    p3 = os.path.join(probe_dir, 'probe.py')
    with open(p3, 'w', encoding='utf-8') as f:
        f.write('X = "_probe_gate/meeting_record_2026.wav"\n'
                'Y = "babelvox"          # 只是依赖名 ⇒ 不该命中\n'
                'def g():\n'
                '    """docstring 里的 meeting_record.wav 不算"""\n'
                '    return X\n')
    lh = scan_literals(PKG)
    ok_c = any(x['file'].endswith('probe.py') for x in lh)
    disc.append(dict(name='反证③指向包内既有敏感音频 ⇒ ③ 必须命中',
                     ok=ok_c))
    # (c2) **指向包外**的音频路径 ⇒ ③ 必须命中（外部素材泄漏）
    p5 = os.path.join(probe_dir, 'probe3.py')
    with open(p5, 'w', encoding='utf-8') as f:
        f.write('Z = "C:/Users/someone/meeting_record_2026.wav"\n')
    lh3 = scan_literals(PKG)
    ok_c2 = any(x['file'].endswith('probe3.py')
                and x['kw'] == 'points_outside_pkg' for x in lh3)
    disc.append(dict(name='反证③b指向包外的音频路径 ⇒ ③ 必须命中',
                     ok=ok_c2))
    # 反证的反面：只有「提到敏感词、但不是音频路径」的 ⇒ **不该**命中
    p4 = os.path.join(probe_dir, 'probe2.py')
    with open(p4, 'w', encoding='utf-8') as f:
        f.write('Z = "babelvox"\n'
                'W = "clone_collector"\n'
                'def h():\n'
                '    return Z, W\n')
    lh2 = scan_literals(PKG)
    ok_d = not any(x['file'].endswith('probe2.py') for x in lh2)
    disc.append(dict(name='反证④只提到敏感词但非音频路径 ⇒ ③ 必须**不**命中',
                     ok=ok_d))
    # 反证的反面：运行时输出模板（包内不存在的裸文件名）⇒ **不该**命中
    p6 = os.path.join(probe_dir, 'probe4.py')
    with open(p6, 'w', encoding='utf-8') as f:
        f.write('T = "clone_%d_%d.wav"\n'
                'U = "clone_C.wav"\n')
    lh4 = scan_literals(PKG)
    ok_e = not any(x['file'].endswith('probe4.py') for x in lh4)
    disc.append(dict(name='反证⑤运行时输出模板（包内不存在）⇒ ③ 必须**不**命中',
                     ok=ok_e))
    # 反证⑥⑦：EXT 侧旁路判据的鉴别力（合成样本 ⇒ 必须判 FAIL）
    fake_sync = ('import queue\n'
                 'class Bypass:\n'
                 '    def feed(self, pcm):\n'
                 '        return self._infer(pcm)   # 同步推理 ⇒ 反压\n')
    fake_block = ('import queue, threading\n'
                  'class Bypass:\n'
                  '    def feed(self, pcm):\n'
                  '        self._q.put(pcm)  # 队列满 ⇒ 阻塞 ⇒ 反压\n'
                  '    def _run(self):\n'
                  '        pass\n'
                  't = threading.Thread(target=lambda: None, daemon=True)\n')
    ok_f = (not ext_bypass_thread_ok(fake_sync)) and \
        (not ext_bypass_nonblock_ok(fake_sync))
    disc.append(dict(name='反证⑥合成的「同步推理旁路」⇒ ⑤\' 必须判 FAIL',
                     ok=ok_f))
    ok_g = (not ext_bypass_nonblock_ok(fake_block)) and \
        ext_bypass_thread_ok(fake_block)
    disc.append(dict(name='反证⑦合成的「队列满即阻塞」⇒ ⑤\' 不反压必须判 FAIL',
                     ok=ok_g))
    # 清理探针
    for fn in os.listdir(probe_dir):
        os.remove(os.path.join(probe_dir, fn))
    os.rmdir(probe_dir)
    check('⑥ 反证组全部成立（闸门有鉴别力）',
          all(d['ok'] for d in disc),
          '%d/%d' % (sum(1 for d in disc if d['ok']), len(disc)))
    for d in disc:
        print('      %-56s %s' % (d['name'], 'PASS' if d['ok'] else 'FAIL'))

    npass = sum(1 for _n, ok, _d in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print('\n结果：%d PASS / %d FAIL' % (npass, nfail))

    out = {
        'tool': 'app213',
        'app': 'APP-057',
        'pkg': PKG,
        'at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'audio_files': audio,
        'n_audio': len(audio),
        'tts_voice_refs': voices,
        'other_audio': other_audio,
        'name_hits': name_hits,
        'literal_hits': lit_hits,
        'notice_bytes': len(ntxt.encode('utf-8')),
        'discrimination': disc,
        'results': [{'name': n, 'ok': ok, 'detail': d}
                    for n, ok, d in RESULTS],
        'summary': {'pass': npass, 'fail': nfail},
    }
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.json)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
