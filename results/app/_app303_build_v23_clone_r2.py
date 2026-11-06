r"""_app303_build_v23_clone_r2.py — APP-075(e) 交付 `shared/app_listen/v23_clone_r2/`。

## 交付内容
* `clone_r2.wav`   —— 第 1 臂（跟随说话人）逐句配音按 jid 顺序拼接的整段 wav（便于抽听）
* `wav/*.wav`      —— 46 个逐句配音 wav（原始落盘件，逐字节复制）
* `seg.jsonl`      —— 设备实测段表（含 spk / spk_conf / t0 / t1）
* `submit.jsonl`   —— jid→seg 映射（标签晚到的真实顺序）
* `f0_by_sentence.csv` / `.json` —— **逐句 F0 表**（配音 F0 中位 + 原声 F0 中位 + 闸门）
* `gate.json`      —— F0 闸门判定 + 反证组
* `manifest.json`  —— 文件数 / mtime / 字节 / SHA256

## 口径与边界（🔴 必须如实写，不许含糊）
1. **F0 算法**：复用 `app246_app067_spk_gender_segment.py` 的 `f0_autocorr`
   （含八度误差修正）⇒ 与 `_app295_f0_verify.json` **同一把尺**。
2. **闸门**：男 < 160 Hz、女 > 170 Hz（reviewer APP-075(e) 原文）。
   原声性别**不按 spk 标签猜**（APP-075 的核心发现：标签晚到 ⇒ 标签与音频
   性别会错开），而是**从原声切片实测 F0** 得出。
3. **反证**：旧 `v23_clone/wav_clone/male_0*_clone.wav`（reviewer 报「男声
   听上去是女声」的三段）用同一把尺必须被测成 >170 Hz ⇒ 判据非恒真。
4. 🔴 **本轮未完成项（必须写进 STATUS，不得宣称已交付）**：
   * 第 2 臂（预设 A 对照）**未跑** —— 后台设备作业在会话中断时被杀，
     `app301_device_out/` 只有 `tts_on_clone_0.*`；
   * **真 x-vector 余弦矩阵未产出** —— `app299_app075_reg_diag` 是
     `offline_stat_embed`（纯 CPU 统计嵌入），其自述「**不能**替代 reviewer
     的真 x-vector 判据」，且硬判据 FAIL（cos_S2_S2=0.745841 <
     cos_S2_S1=0.772995）⇒ 需 reviewer 用真 x-vector 复核。
   ⇒ **本条 APP-075 标注「需等 reviewer 复核」，v2.3 不打包。**

不占设备、不加载模型、不推理、不测速（F0 自相关是纯 CPU 静态分析）。
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.expanduser('~')
SRC = os.path.join(HERE, 'app301_device_out')
STEM = 'tts_on_clone_0'
PARTS = os.path.join(SRC, STEM + '.wavparts')
OUT = os.path.join(HOME, 'shared', 'app_listen', 'v23_clone_r2')
OLD = os.path.join(HOME, 'shared', 'app_listen', 'v23_clone')
MIX = os.path.join(OLD, 'SPE_mix_3303_3603.wav')
EV = os.path.join(HERE, '_app303_build_v23_clone_r2.json')

F0_MALE_MAX = 160.0
F0_FEMALE_MIN = 170.0


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_f0_mod():
    p = os.path.join(HERE, 'app246_app067_spk_gender_segment.py')
    spec = importlib.util.spec_from_file_location('app246_f0', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def median(vals):
    if not vals:
        return None
    s = sorted(vals)
    return float(s[len(s) // 2])


def cls(f0):
    if f0 is None:
        return 'unknown'
    if f0 < F0_MALE_MAX:
        return 'male'
    if f0 > F0_FEMALE_MIN:
        return 'female'
    return 'ambiguous'


def wav_f0(m246, path):
    a, sr, nf = m246.read_wav(path)
    vals = m246.segment_f0(a, sr, 0.0, nf / float(sr))
    return median(vals), len(vals), nf / float(sr)


def main():
    t0 = time.time()
    print('=' * 72)
    print('_app303 — 生成 APP-075(e) v23_clone_r2 交付')
    print('=' * 72)
    assert os.path.isdir(PARTS), '第 1 臂逐句 wav 不存在：%s' % PARTS
    assert not os.path.exists(OUT), 'r2 目录已存在 ⇒ 拒绝覆盖（APP-055）：%s' % OUT
    os.makedirs(OUT)
    wav_dir = os.path.join(OUT, 'wav')
    os.makedirs(wav_dir)

    m246 = load_f0_mod()

    # ── ① 段表 / jid→seg 映射 ──────────────────────────────────
    seg_rows = [json.loads(l) for l in open(
        os.path.join(SRC, STEM + '.seg.jsonl'), encoding='utf-8') if l.strip()]
    seg_by_id = {int(r['seg']): r for r in seg_rows}
    submit = [json.loads(l) for l in open(
        os.path.join(SRC, STEM + '.seg.jsonl.submit.jsonl'),
        encoding='utf-8') if l.strip()]
    jid2seg = {int(r['jid']): int(r['seg']) for r in submit}
    tts_rows = {}
    p = os.path.join(SRC, STEM + '.tts.jsonl')
    if os.path.isfile(p):
        for l in open(p, encoding='utf-8'):
            if l.strip():
                r = json.loads(l)
                tts_rows[int(r['id'])] = r

    # ── ② 原声切片（用于「按实测 F0 定性别」，不猜标签）──────────
    mix_a, mix_sr, mix_nf = m246.read_wav(MIX)

    # ── ③ 逐句配音 wav 复制 + 拼接 + F0 ────────────────────────
    pat = re.compile(r'^seg_(\d+)_(\d+)\.wav$', re.I)
    items = []
    for fn in sorted(os.listdir(PARTS)):
        m = pat.match(fn)
        if not m:
            continue
        jid, idx = int(m.group(1)), int(m.group(2))
        src = os.path.join(PARTS, fn)
        dst = os.path.join(wav_dir, fn)
        shutil.copy2(src, dst)
        items.append((jid, idx, fn, src, dst))
    items.sort(key=lambda x: (x[0], x[1]))
    print('逐句 wav: %d 个' % len(items))

    out_rows = []
    for jid, idx, fn, src, dst in items:
        f0_dub, n_frames, dur = wav_f0(m246, dst)
        seg = jid2seg.get(jid)
        sr_row = seg_by_id.get(seg)
        f0_orig = None
        n_orig = 0
        if sr_row and sr_row.get('t0') is not None and sr_row.get('t1') is not None:
            vals = m246.segment_f0(mix_a, mix_sr,
                                   float(sr_row['t0']), float(sr_row['t1']))
            f0_orig, n_orig = median(vals), len(vals)
        tr = tts_rows.get(jid, {})
        out_rows.append(dict(
            jid=jid, wav_index=idx, file=fn, seg=seg,
            spk=(sr_row or {}).get('spk'),
            spk_conf=(sr_row or {}).get('spk_conf'),
            seg_t0=(sr_row or {}).get('t0'), seg_t1=(sr_row or {}).get('t1'),
            voice_kind=tr.get('voice_kind'), voice_spk=tr.get('voice_spk'),
            clone_active=tr.get('clone_active'),
            dub_dur_s=round(dur, 3), dub_n_voiced_frames=n_frames,
            dub_f0_median_hz=None if f0_dub is None else round(f0_dub, 2),
            dub_f0_class=cls(f0_dub),
            orig_f0_median_hz=None if f0_orig is None else round(f0_orig, 2),
            orig_f0_class=cls(f0_orig), orig_n_voiced_frames=n_orig,
            bytes=os.path.getsize(dst), sha256=sha256_file(dst)))

    # 拼接整段（同一格式断言，不加静音 ⇒ 与逐句表一一对应）
    fmt = None
    with wave.open(items[0][3], 'rb') as w:
        fmt = (w.getnchannels(), w.getsampwidth(), w.getframerate())
    concat = os.path.join(OUT, 'clone_r2.wav')
    with wave.open(concat, 'wb') as wo:
        wo.setnchannels(fmt[0]); wo.setsampwidth(fmt[1]); wo.setframerate(fmt[2])
        for _jid, _idx, _fn, src, _dst in items:
            with wave.open(src, 'rb') as wi:
                assert (wi.getnchannels(), wi.getsampwidth(), wi.getframerate()) == fmt
                wo.writeframes(wi.readframes(wi.getnframes()))
    print('拼接整段：%s (%d B)' % (concat, os.path.getsize(concat)))

    # 🔴 补漏（_app309）：submit 的真实源文件名是
    #    tts_on_clone_0.seg.jsonl.submit.jsonl，**不是** tts_on_clone_0.submit.jsonl。
    #    旧写法 `if os.path.isfile(s): copy2(...)` 会**静默跳过**，导致 r2 缺
    #    jid→seg 映射（APP-067 ①(b) 标签晚到的关键诊断材料）。
    #    ⇒ 改成显式映射 + `assert`，缺源直接失败，不允许静默漏拷。
    _JSONL_SRC = {
        'seg.jsonl': STEM + '.seg.jsonl',
        'submit.jsonl': STEM + '.seg.jsonl.submit.jsonl',
        'tts.jsonl': STEM + '.tts.jsonl',
    }
    for name, src_name in _JSONL_SRC.items():
        s = os.path.join(SRC, src_name)
        assert os.path.isfile(s), '源 jsonl 缺失（禁止静默跳过）：%s' % s
        shutil.copy2(s, os.path.join(OUT, name))

    # ── ④ F0 闸门 ──────────────────────────────────────────────
    # 判据：对「原声实测为男声」的句子，配音 F0 必须 <160；
    #       对「原声实测为女声」的句子，配音 F0 必须 >170。
    # ⚠️ 只统计 clone_active / voice_kind=clone 的句子（预设 A 本来就是
    #    固定音色，拿它判男/女不成立 ⇒ 三态 None = 无法判定）。
    gate_rows = []
    for r in out_rows:
        is_clone = (r['clone_active'] is True
                    or r['voice_kind'] == 'clone')
        if not is_clone:
            gate_rows.append(dict(jid=r['jid'], applicable=False,
                                  verdict=None, reason='not_clone_sentence'))
            continue
        oc, dc = r['orig_f0_class'], r['dub_f0_class']
        if oc in ('unknown', 'ambiguous') or r['dub_f0_median_hz'] is None:
            gate_rows.append(dict(jid=r['jid'], applicable=True,
                                  verdict=None, reason='f0_undetermined',
                                  orig_class=oc))
            continue
        if oc == 'male':
            ok = r['dub_f0_median_hz'] < F0_MALE_MAX
        else:
            ok = r['dub_f0_median_hz'] > F0_FEMALE_MIN
        gate_rows.append(dict(jid=r['jid'], applicable=True, verdict=ok,
                              reason='%s->%s' % (oc, dc),
                              orig_class=oc, dub_class=dc,
                              orig_f0=r['orig_f0_median_hz'],
                              dub_f0=r['dub_f0_median_hz']))
    n_true = sum(1 for g in gate_rows if g['verdict'] is True)
    n_false = sum(1 for g in gate_rows if g['verdict'] is False)
    n_none = sum(1 for g in gate_rows if g['verdict'] is None)

    # ── ⑤ 反证：旧产物（已知男声被播成女声）必须被识破 ──────────
    disc = []
    old_dir = os.path.join(OLD, 'wav_clone')
    old_male = sorted(f for f in os.listdir(old_dir)
                      if f.startswith('male_') and f.endswith('.wav'))
    for fn in old_male:
        f0, n, d = wav_f0(m246, os.path.join(old_dir, fn))
        disc.append(dict(file=fn, f0_median_hz=None if f0 is None else round(f0, 2),
                         f0_class=cls(f0), n_voiced_frames=n, dur_s=round(d, 3),
                         reviewer_reported='male_voice_sounds_female'))
    # 反证成立 = 至少一个「标称男声」的旧 wav 被测成女声（>170）
    disc_ok = any(d['f0_class'] == 'female' for d in disc)
    print('反证组（旧 male_* wav）：', [(d['file'], d['f0_median_hz'],
                                     d['f0_class']) for d in disc])

    # ── ⑥ 落盘表 + manifest ────────────────────────────────────
    cols = ['jid', 'wav_index', 'file', 'seg', 'spk', 'spk_conf',
            'seg_t0', 'seg_t1', 'voice_kind', 'voice_spk', 'clone_active',
            'dub_dur_s', 'dub_n_voiced_frames', 'dub_f0_median_hz',
            'dub_f0_class', 'orig_f0_median_hz', 'orig_f0_class',
            'orig_n_voiced_frames', 'bytes', 'sha256']
    with open(os.path.join(OUT, 'f0_by_sentence.csv'), 'w',
              newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r.get(k) for k in cols})
    with open(os.path.join(OUT, 'f0_by_sentence.json'), 'w',
              encoding='utf-8') as f:
        json.dump(dict(criterion=dict(male_max_hz=F0_MALE_MAX,
                                      female_min_hz=F0_FEMALE_MIN),
                       f0_algorithm='app246 f0_autocorr (octave-corrected)',
                       n_sentences=len(out_rows), rows=out_rows),
                  f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, 'gate.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(criterion='APP-075(e) F0 gate: male<160Hz / female>170Hz',
                       verdict_counts=dict(true=n_true, false=n_false,
                                           none=n_none),
                       applicable=sum(1 for g in gate_rows if g['applicable']),
                       rows=gate_rows,
                       counter_evidence=dict(
                           description='旧 v23_clone/wav_clone male_* 用同一把尺',
                           ok=disc_ok, rows=disc),
                       caveat=('原声性别按切片实测 F0 判定，不按 spk 标签；'
                               '非 clone 句子标 None（无法判定）不计入分母')),
                  f, ensure_ascii=False, indent=1)

    files = []
    for dp, _dn, fns in os.walk(OUT):
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, OUT).replace('\\', '/')
            files.append(dict(rel=rel, bytes=os.path.getsize(full),
                              mtime=os.path.getmtime(full),
                              sha256=sha256_file(full)))
    manifest = dict(created_by='_app303_build_v23_clone_r2.py',
                    correction='APP-075(e)',
                    ts=time.strftime('%Y-%m-%d %H:%M:%S'),
                    out_dir=OUT, n_files=len(files),
                    n_bytes=sum(x['bytes'] for x in files),
                    source_arm=STEM,
                    n_sentences=len(out_rows),
                    n_seg_rows=len(seg_rows), n_submit_rows=len(submit),
                    wav_format=dict(nch=fmt[0], sampwidth=fmt[1], sr=fmt[2]),
                    concat_wav=dict(rel='clone_r2.wav',
                                    bytes=os.path.getsize(concat),
                                    sha256=sha256_file(concat)),
                    gate=dict(true=n_true, false=n_false, none=n_none,
                              counter_evidence_ok=disc_ok),
                    incomplete=(
                        '第 2 臂 preset 对照未跑（后台作业被会话中断杀掉）；'
                        '真 x-vector 余弦矩阵未产出（app299 是 offline_stat_embed，'
                        '硬判据 FAIL）⇒ 本条需等 reviewer 复核；v2.3 不打包'),
                    files=files)
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    # 证据文件（在仓库 results/app 下，不进客户包）
    with open(EV, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print('\n交付目录：%s' % OUT)
    print('文件数 %d / %d B' % (len(files), sum(x['bytes'] for x in files)))
    print('F0 闸门: %d PASS / %d FAIL / %d NONE；反证组 %s'
          % (n_true, n_false, n_none, 'PASS' if disc_ok else 'FAIL'))
    print('elapsed %.1f s' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
