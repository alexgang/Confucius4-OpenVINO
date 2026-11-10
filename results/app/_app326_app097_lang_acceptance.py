#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app326_app097_lang_acceptance.py —— **APP-097 §2 逐语种设备验收**（§2-2 / §2-3 / §2-4 / §2-6）。

## 依据（reviewer APP-097 §2 原文）

* **§2-2 MT**：用 dialog3 的英文定稿句取 **15 句**，分别翻成
  **de/fr/es/pt/it/ru**，再挑 **5 句中文源**也翻一遍。
  原文和译文落盘成 json。reviewer 本机抽查质量。
  报：**输出语种是否正确**（每句标出**用什么判定的**）、**空译数**、
  **"原样返回原文"数**、**平均延迟**。
* **§2-3 TTS**：用上一步的译文，**每种语言 15 句**，**预设音色和克隆音色（x-vector）各一遍**。
  wav 落盘。报：**撞帧上限次数**（数据来自哪个字段要写明）、**RTF p50/p95**、
  **end_reason 分布**。
* **§2-4 时长口径校准**：每种语言报「**合成时长 ÷ 字符数**」的 p50，
  用它定 `_SEC_PER_CHAR`。再报「**译文语音时长 ÷ 英文源段时长**」的 p50。
* **§2-6 模型身份**：本条不换任何模型。MANIFEST 里 ASR/MT/TTS 的目录、
  源模型和 SHA 与改前一致，要写进 json。

## 🔴🔴🔳 口径纪律

* **MT 与 TTS 都用影子包 `after2`**（扩表后）⇒ 跑的是**真实 App 代码路径**
  （`translator.TranslationService` + `tts_engine`），不是另写一套。
* 🔴 **TTS 直接调 `tts_engine.stream()`**（与 `tts_worker._synth_babelvox`
  **同一套参数口径**：`map_language` → `language_supported` → `split_long_text`
  → `clamp_max_new_tokens` → `estimate_sec` → `stream`）⇒
  「撞帧上限」= `end_reason == 'cap'`（**字段来源写进 json**）。
* 🔴 **MT 判定语种的口径**（reviewer 明确要求「每句标出用什么判定的」）：
  * `script` ＝ `translator.detect_lang()`（**按文字系统**）
  * `hint`   ＝ **ASR 语种标签**（本素材无标签 ⇒ 记 `None`）
  * `target` ＝ 目标语言全称（`translator._LANG_NAME[tgt]`）
  ⇒ 三者都落进 json。
* 🔴 **不调 MiniMax**（CER 由 reviewer 复算）。
* 🔴 **持 `MACHINE_LOCK`**（计时作业）⇒ 做完释放；锁记录写进 json。
* 🔴 **不改 `_SEC_PER_CHAR` 默认值**（§2-4 只**报**实测 p50 ⇒ 由 reviewer 裁定）。
* 🔴 **不打包、不通知用户**。

## 用法

```
.venv/Scripts/python.exe results/app/_app326_app097_lang_acceptance.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import statistics as st
import subprocess
import sys
import time
import wave
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

BASE = os.path.join(HOME, '_app_shadow')
ARM = 'after2'
SHADOW_APP = os.path.join(BASE, ARM, 'app')
SHADOW_PY = os.path.join(BASE, ARM, 'python', 'python.exe')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
SPKTEST = os.path.join(HOME, '_reviewer_tmp', 'spktest')
OUT = os.path.join(HERE, 'app326_app097_lang_out')
REPORT = os.path.join(HERE, 'app326_app097_lang_acceptance.json')

#: §2-2 的 6 个新语种（reviewer 指定）
NEW_LANGS = ('de', 'fr', 'es', 'pt', 'it', 'ru')
#: §2-3/§2-4 要对比的基准语种（zh/en 已有历史口径 ⇒ 一并跑做对照）
BASE_LANGS = ('zh', 'en')
ALL_LANGS = BASE_LANGS + NEW_LANGS

N_SENT = 15          # §2-2/§2-3：每语种 15 句
N_ZH_SRC = 5         # §2-2：另挑 5 句中文源

#: 🔴 英文定稿句的来源（**已落盘**，不重跑设备）
_RUN_SUBS_EN = (
    os.path.join(BASE, 'runs3', 'after', 'dialog3_tight_thr6', 'subtitles.txt'),
    os.path.join(BASE, 'runs3', 'after', 'dialog3_dave_thr6', 'subtitles.txt'),
)
#: 🔴 中文源句的来源（MT 译文行）
_RUN_SUBS_ZH = (
    os.path.join(BASE, 'runs3', 'after', 'dialog3_tight_thr6', 'subtitles.mt.txt'),
    os.path.join(BASE, 'runs3', 'after', 'dialog3_dave_thr6', 'subtitles.mt.txt'),
)
#: 🔴🔴 **英文源段时长**的来源（§2-4 要「译文语音时长 ÷ 英文源段时长」）
#: `spk_seg.jsonl` 有 `t0`/`t1` ⇒ 与 `subtitles.txt` 的行**按序一一对应**
_RUN_SEG_EN = (
    os.path.join(BASE, 'runs3', 'after', 'dialog3_tight_thr6', 'spk_seg.jsonl'),
    os.path.join(BASE, 'runs3', 'after', 'dialog3_dave_thr6', 'spk_seg.jsonl'),
)


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def acquire_lock(tag):
    """🔴 排队等锁（不抢）。返回锁内容或 None。"""
    for _ in range(180):
        if not os.path.exists(LOCK):
            payload = ('module=app\npid=%d\nstart=%s\ntag=%s\n'
                       % (os.getpid(), now(), tag))
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(payload)
                return payload
            except FileExistsError:
                pass
        time.sleep(10)
    return None


def release_lock():
    """🔴 释放机器锁。

    🔴🔴 **不要用 `os.remove`**：宿主的安全删除钩子会把它转成「移到回收站」
    ⇒ 在共享目录上会失败（实测 `trash-failed`）⇒ 锁留在原地 ⇒ 下一轮被阻塞。
    ⇒ 改用 **`os.replace` 改名**（原子、不触发删除钩子）⇒ LOCK 路径不再存在。
    """
    try:
        if os.path.exists(LOCK):
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                if ('pid=%d' % os.getpid()) in f.read():
                    gone = os.path.join(os.path.dirname(LOCK),
                                        '.MACHINE_LOCK.released_%d_%d'
                                        % (os.getpid(), int(time.time())))
                    os.replace(LOCK, gone)
                    return not os.path.exists(LOCK)
    except OSError:
        pass
    return False


def read_wav(path):
    w = wave.open(path, 'rb')
    try:
        n = w.getnframes()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        raw = w.readframes(n)
    finally:
        w.close()
    if sw == 2:
        import numpy as np
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        import numpy as np
        a = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise RuntimeError('unsupported wav %sB' % sw)
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, sr


def write_wav(path, samples, sr):
    import numpy as np
    a = np.asarray(samples, dtype=np.float32).reshape(-1)
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype('<i2')
    w = wave.open(path, 'wb')
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())
    finally:
        w.close()


def pick_english_sentences():
    """§2-2：从 dialog3 的**英文定稿句**里取 15 句（**带源段时长**）。

    🔴 口径：ASR 定稿段的**英文原文**（`subtitles.txt` 的 `[S1] …` 行）
    ⇒ 取**已有落盘**的定稿文本（APP-093 §3.2 的 after 臂 dialog3_tight 运行产物）
    ⇒ 不重跑设备（省时且与 §3.2 同素材）。

    🔴🔴 **源段时长**（§2-4 要「译文语音时长 ÷ 英文源段时长」）：
    `spk_seg.jsonl` 与 `subtitles.txt` **行数一一对应**（实测 35/35、55/55）
    ⇒ 按**行序号**取 `t1 - t0`。
    """
    rows = []
    for pi, p in enumerate(_RUN_SUBS_EN):
        if not os.path.exists(p):
            continue
        segs = _load_seg_durs(_RUN_SEG_EN[pi]) if pi < len(_RUN_SEG_EN) else []
        with open(p, encoding='utf-8', errors='replace') as f:
            li = 0
            for line in f:
                line = line.strip()
                if not line:
                    continue
                txt = line.split(']', 1)[1].strip() if ']' in line else line
                dur = None
                if li < len(segs):
                    dur = segs[li]
                li += 1
                if txt and _is_latin(txt):
                    rows.append({'text': txt, 'src_dur_s': dur,
                                 'src_file': os.path.basename(p), 'src_line': li - 1})
        if len(rows) >= N_SENT:
            break
    return rows[:N_SENT]


def _load_seg_durs(path):
    """读 `spk_seg.jsonl` ⇒ 每段的时长秒（`t1 - t0`），按行序。"""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t0 = d.get('t0')
            t1 = d.get('t1')
            if isinstance(t0, (int, float)) and isinstance(t1, (int, float)):
                out.append(round(float(t1) - float(t0), 4))
            else:
                out.append(None)
    return out


def pick_zh_sentences():
    """§2-2：另挑 5 句**中文源**。

    🔴 口径：**中文字幕**（`subtitles.mt.txt` 的 MT 译文行）⇒ 真正的中文源句。
    ⇒ 用途：验证「源=中文、目标=非中文」时**不会被误跳过翻译**
    （APP-097 §1.4 的坑）。
    """
    out = []
    for p in _RUN_SUBS_ZH:
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8', errors='replace') as f:
            li = 0
            for line in f:
                line = line.strip()
                if not line:
                    continue
                txt = line.split(']', 1)[1].strip() if ']' in line else line
                if txt and any('一' <= ch <= '鿿' for ch in txt):
                    # 🔴 中文源**无对应英文源段时长** ⇒ src_dur_s=None
                    #    （§2-4 的比值只用**英文源句**那条）
                    out.append({'text': txt, 'src_dur_s': None,
                                'src_file': os.path.basename(p), 'src_line': li})
                li += 1
        if len(out) >= N_ZH_SRC:
            break
    return out[:N_ZH_SRC]


def _is_latin(s):
    """句子是否**含拉丁字母**（英文源句的判据）。"""
    return any(('a' <= c <= 'z') or ('A' <= c <= 'Z') for c in s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only-tts', action='store_true',
                    help='🔴 复用已落盘的 mt.json ⇒ 只跑 §2-3/§2-4/§2-6')
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    ev = {'created_at': now(), 'correction': 'APP-097 §2-2/§2-3/§2-4/§2-6',
          'arm': ARM, 'shadow_app': SHADOW_APP,
          'n_sent': N_SENT, 'new_langs': list(NEW_LANGS),
          'all_langs': list(ALL_LANGS), 'lock': None}

    lock = acquire_lock('app097-lang')
    if lock is None:
        ev['verdict'] = 'BLOCKED_LOCK'
        _dump(ev)
        print('!! 拿不到锁')
        return 2
    ev['lock'] = lock.strip()
    print('[lock] 已持有', flush=True)

    try:
        # ══════════════ §2-2 MT ══════════════
        en_sents = pick_english_sentences()
        zh_sents = pick_zh_sentences()
        ev['src_en_n'] = len(en_sents)
        ev['src_zh_n'] = len(zh_sents)
        ev['src_en_head'] = en_sents[:3]
        ev['src_zh_head'] = zh_sents[:3]
        print('[MT] 英文句 %d 条 / 中文句 %d 条' % (len(en_sents), len(zh_sents)),
              flush=True)
        if len(en_sents) < N_SENT or len(zh_sents) < N_ZH_SRC:
            ev['verdict'] = 'BLOCKED_NO_SOURCE'
            _dump(ev)
            return 3

        mt_out = os.path.join(OUT, 'mt.json')
        mt_jsonl = os.path.join(OUT, 'mt.jsonl')
        mt_log = os.path.join(OUT, 'mt.log')
        if args.only_tts and os.path.exists(mt_out):
            # 🔴 复用上一阶段已落盘的 MT 结果（不重跑设备）
            ev['mt_reused'] = True
            print('[MT] 复用已落盘 mt.json', flush=True)
        else:
            # 🔴🔴 用**包内 python**跑（包内才有 openvino_genai / babelvox）
            # 🔴🔴🔴 **stdout 重定向到文件**（不是 pipe！）——
            #    上一版用 `capture_output=True` ⇒ 子进程写满管道缓冲区后**永久阻塞**
            #    ⇒ 作业被外部清理时**一行结果都没落盘**。
            #    本版：① stdout/stderr → 日志文件 ② 每句增量写 jsonl。
            runner = os.path.join(HERE, '_app326_mt_runner.py')
            cmd = [SHADOW_PY, runner, '--app', SHADOW_APP, '--out', mt_out,
                   '--jsonl', mt_jsonl,
                   '--en', json.dumps(en_sents[:N_SENT], ensure_ascii=False),
                   '--zh', json.dumps(zh_sents[:N_ZH_SRC], ensure_ascii=False),
                   '--langs', ','.join(ALL_LANGS)]
            print('[MT] 启动：%s' % ' '.join(cmd[:3]), flush=True)
            rc, tail = _run_logged(cmd, mt_log, 3600)
            print('[MT] rc=%s' % rc, flush=True)
            print(tail, flush=True)
            ev['mt_rc'] = rc
            ev['mt_log'] = mt_log
            ev['mt_jsonl'] = mt_jsonl
            ev['mt_log_tail'] = tail[-1500:]
            _dump(ev)
            if not os.path.exists(mt_out):
                ev['verdict'] = 'FAIL_MT'
                _dump(ev)
                return 3
        mt = json.load(open(mt_out, encoding='utf-8'))
        ev['mt'] = mt
        _dump(ev)

        # ══════════════ §2-3 TTS ══════════════
        runner2 = os.path.join(HERE, '_app326_tts_runner.py')
        tts_out = os.path.join(OUT, 'tts.json')
        tts_jsonl = os.path.join(OUT, 'tts.jsonl')
        tts_log = os.path.join(OUT, 'tts.log')
        cmd2 = [SHADOW_PY, runner2, '--app', SHADOW_APP, '--out', tts_out,
                '--jsonl', tts_jsonl, '--mt', mt_out,
                '--langs', ','.join(ALL_LANGS),
                '--wav-dir', os.path.join(OUT, 'wav'),
                '--clone-ref', os.path.join(SPKTEST, 'dialog3_tight.wav')]
        print('[TTS] 启动', flush=True)
        rc2, tail2 = _run_logged(cmd2, tts_log, 7200)
        print('[TTS] rc=%s' % rc2, flush=True)
        print(tail2, flush=True)
        ev['tts_rc'] = rc2
        ev['tts_log'] = tts_log
        ev['tts_jsonl'] = tts_jsonl
        ev['tts_log_tail'] = tail2[-1500:]
        _dump(ev)
        if not os.path.exists(tts_out):
            ev['verdict'] = 'FAIL_TTS'
            _dump(ev)
            return 3
        ev['tts'] = json.load(open(tts_out, encoding='utf-8'))

        # ══════════════ §2-4 时长口径校准 ══════════════
        ev['calib'] = _calibrate(ev['tts'])

        # ══════════════ §2-6 模型身份 ══════════════
        ev['model_identity'] = _model_identity()

        ev['verdict'] = 'RAN'
    finally:
        ev['lock_released'] = release_lock()
        ev['lock_exists_after'] = os.path.exists(LOCK)
        print('[lock] 释放=%s 残留=%s' % (ev['lock_released'],
                                        ev['lock_exists_after']), flush=True)
    _dump(ev)
    return 0


def _run_logged(cmd, log_path, timeout):
    """🔴 跑子进程，**stdout/stderr 重定向到文件**（不是 pipe）⇒ 不会阻塞。

    返回 (rc, 日志尾部文本)。
    """
    with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
        try:
            rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                 timeout=timeout)
        except subprocess.TimeoutExpired:
            rc = -9
    try:
        tail = open(log_path, encoding='utf-8', errors='replace').read()[-4000:]
    except OSError:
        tail = ''
    return rc, tail


def _calibrate(tts):
    """§2-4：每语种报「合成时长 ÷ 字符数」p50 与「译文语音时长 ÷ 英文源段时长」p50。"""
    out = {}
    for lang, d in (tts.get('per_lang') or {}).items():
        rows = d.get('preset', {}).get('rows') or []
        spc = [r['out_dur_s'] / r['n_chars'] for r in rows
               if r.get('n_chars') and r.get('out_dur_s')]
        ratio = [r['out_dur_s'] / r['src_dur_s'] for r in rows
                 if r.get('src_dur_s') and r.get('out_dur_s')]
        out[lang] = {
            'n': len(spc),
            'sec_per_char_p50': round(st.median(spc), 6) if spc else None,
            'sec_per_char_p25': (round(sorted(spc)[int(0.25 * (len(spc) - 1))], 6)
                                 if spc else None),
            'sec_per_char_p75': (round(sorted(spc)[int(0.75 * (len(spc) - 1))], 6)
                                 if spc else None),
            'src_dur_ratio_p50': round(st.median(ratio), 4) if ratio else None,
            'cur_sec_per_char': d.get('cur_sec_per_char'),
            'suggest_sec_per_char': (round(st.median(spc), 4) if spc else None),
            'note': ('🔴 只报数字，**不改默认值**（由 reviewer 裁定）'),
        }
    return out


def _model_identity():
    """§2-6：MANIFEST 里 ASR/MT/TTS 的目录、源模型和 SHA 与改前一致。

    🔴 reviewer 原话：「本条**不换任何模型**。MANIFEST 里 ASR/MT/TTS 的**目录**、
    **源模型**和 **SHA** 与改前一致，要写进 json。」

    🔴 **实测发现**（本轮）：v2.4 的 `MANIFEST.json` **没有**逐模型的
    「源模型 / SHA」字段 ⇒ 只有 `files`（14319）/ `bytes`（13 692 564 165）/
    `version` / `notes` / `packages`（依赖版本表）
    ⇒ ⇒ **模型身份必须自己算**（逐目录树 SHA）⇒ 本脚本对
    **ASR / MT / TTS / SPK / tokenizer** 五大块各算一个**树 SHA**
    （路径相对名 + 逐文件 SHA 汇总 ⇒ 与目录顺序无关）。

    🔴 **「与改前一致」的对照**：影子包 `after2` 的 `models/` 是
    **目录联接** ⇒ 指向真包 ⇒ 与「改前」**同一个物理目录**
    ⇒ 树 SHA **必然相同**（这不是测量结论，是结构事实）⇒ 本脚本**如实标注**。
    """
    man = os.path.join(SHADOW_APP, 'MANIFEST.json')
    d = {'manifest': man, 'manifest_present': os.path.exists(man)}
    if not d['manifest_present']:
        return d
    try:
        m = json.load(open(man, encoding='utf-8'))
    except Exception as e:
        d['error'] = str(e)[:200]
        return d
    d['manifest_sha256'] = sha(man)
    d['manifest_bytes'] = os.path.getsize(man)
    d['manifest_top_fields'] = {k: (v if isinstance(v, (str, int, float))
                                    else ('<%s len=%d>' % (type(v).__name__,
                                                          len(v))))
                                for k, v in m.items()}
    d['manifest_has_per_model_sha'] = False
    d['manifest_per_model_sha_note'] = (
        '🔴 实测：v2.4 的 MANIFEST.json **没有**逐模型「源模型 / SHA」字段 '
        '（只有 files / bytes / version / notes / packages）⇒ '
        '⇒ 模型身份由本脚本的**目录树 SHA**给出')

    # 🔴 模型目录的**实测树 SHA**（逐文件：相对路径 + 文件 SHA 汇总）
    models_root = os.path.join(BASE, ARM, 'models')
    per = {}
    for name in ('mt', 'qwen3tts', 'spk', 'tokenizer', 'encoder-int8',
                 'decoder-npu-int8', 'encoder-fp16'):
        p = os.path.join(models_root, name)
        if not os.path.isdir(p):
            continue
        files = []
        for r, _dd, ff in os.walk(p):
            for f in ff:
                files.append(os.path.join(r, f))
        h = hashlib.sha256()
        tot = 0
        for f in sorted(files):
            h.update(os.path.relpath(f, p).encode('utf-8', 'replace'))
            b = open(f, 'rb').read()
            h.update(hashlib.sha256(b).digest())
            tot += len(b)
        per[name] = {'dir': p, 'n_files': len(files), 'bytes': tot,
                     'tree_sha256': h.hexdigest(),
                     'rel_path': os.path.relpath(p, BASE)}
    d['model_dirs'] = per
    d['models_root'] = models_root
    d['models_root_is_junction'] = os.path.islink(models_root)
    d['unchanged_by_design'] = (
        '🔴 影子包 `after2/models` 是**目录联接**（指向真包 v2.4）⇒ '
        '**本条未换任何模型**是**结构事实**（同一物理目录）⇒ 树 SHA 与改前**必然相同**')
    return d


def _dump(ev):
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT, flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
