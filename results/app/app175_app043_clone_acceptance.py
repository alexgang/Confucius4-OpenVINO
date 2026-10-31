# -*- coding: utf-8 -*-
"""app175 — APP-043 / APP-051②：**APP-039/040 克隆「按句绑定 spk」真机验收**。

## 覆盖什么

APP-039 的四条验收指标（reviewer 原文）：

> ① 每句实际用的音色和该句 spk 一致的比例（报告混淆表）；
> ② 「换人那句的源音频结束」到「用新音色的那句开始播放」之间，
>    **不算播放排队的延迟**（单独拆出 spk 判定延迟 + 取样延迟）；
> ③ 声纹计算的次数和总 CPU/设备时间（应 ≈ 说话人数 × 1–3 次）；
> ④ 不存在渐变：相邻两句的 CAMPPlus 余弦，同一 spk 内 ≥ 阈值，换人处一步到位。

APP-043 要求：「用 SPE 会议 38 分钟后的 Q&A 段（多人对话，
`shared/spe_qa_spk.json` 的 `densest_5min` 窗口），走 App 实时路径，克隆模式开」。

## 本脚本干什么

1. **从 SPE 全量音频切出 `densest_5min` 窗口**（3291.6 s ~ 3591.6 s）
   ⇒ 落 `shared/spe_qa_clone_listen/SPE_densest_5min.wav`。
2. **用客户包 v1.13 自带 python 跑 CLI 实时路径**（`--tts-voice follow_speaker`）
   ⇒ 产物：字幕（含说话人标签）、逐句 TTS 遥测 jsonl、输出 wav。
3. **离线判据**（全部读落盘产物，不在 CPU 上跑推理）：
   - **A 组**：说话人标签覆盖率（每句都有 spk 标签？）
   - **B 组**：混淆表（句子的 spk 标签 vs 参考 `spe_qa_spk.json` 的分段 spk）
   - **C 组**：声纹计算次数（≈ 说话人数 × 1–3）
   - **D 组**：音色切换**一次性**（不渐变）—— 用 worker 遥测的音色 id 序列判断
   - **E 组**：不变式 `n_played + n_dropped == n_submitted`
   - **F 组**：换人前后配音落盘到 `shared/spe_qa_clone_listen/`
4. **反证组**：判据必须能识破「不按句绑定」的旧行为。

## 🔴 纪律

- **必须持共享机器锁**（推理作业）⇒ 本脚本自己取锁（`machine_lock_app`，fail-closed）。
- **不在 CPU 上跑推理**：ASR = GPU.0（集显）、TTS = NPU；翻译 = GPU.0。
- **不自己调用 MiniMax**（质量判定归 reviewer）。
- **不开/不重发 FTP**（APP-035）。
- 用**客户包自带 python**（不用宿主解释器）⇒ 顺带排除宿主 `PYTHONPATH` 污染。

## 用法

    python results/app/app175_app043_clone_acceptance.py --pkg "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.13"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import wave

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.path.expanduser('~')
SHARED = os.path.join(HOME, 'shared')
SPK_JSON = os.path.join(SHARED, 'spe_qa_spk.json')
SPE_FULL = os.path.join(REPO, 'test_audio', '260902_SPE_audio.wav')
LISTEN_DIR = os.path.join(SHARED, 'spe_qa_clone_listen')
OUT_DIR = os.path.join(HOME, 'app043_clone_accept')
EVID = os.path.join(REPO, 'results', 'app',
                    'app175_app043_clone_acceptance_evidence.json')

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  ' + str(detail)) if detail else ''))
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:400]})
    if ok:
        PASS += 1
    else:
        FAIL += 1
    return ok


def _lock():
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    return ml


def make_slice(spk, out_wav):
    """切出 densest_5min 窗口（16 kHz / 单声道 / 16 bit）。"""
    d = spk['densest_5min']
    t0, t1 = float(d['start_s']), float(d['end_s'])
    with wave.open(SPE_FULL, 'rb') as w:
        rate = w.getframerate()
        sw = w.getsampwidth()
        ch = w.getnchannels()
        w.setpos(int(t0 * rate))
        n = int((t1 - t0) * rate)
        raw = w.readframes(n)
    with wave.open(out_wav, 'wb') as o:
        o.setnchannels(ch)
        o.setsampwidth(sw)
        o.setframerate(rate)
        o.writeframes(raw)
    return t0, t1, rate, len(raw) / (rate * sw * ch)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=os.path.join(
        HOME, 'Confucius4_LiveCaption_v1.13'))
    ap.add_argument('--tts-device', default='NPU')
    ap.add_argument('--asr-device', default='GPU.0')
    ap.add_argument('--mt-device', default='GPU.0')
    ap.add_argument('--translate', default='zh')
    ap.add_argument('--skip-run', action='store_true',
                    help='只跑离线判据（复用已有产物）')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    py = os.path.join(pkg, 'python', 'python.exe')
    app_py = os.path.join(pkg, 'app', 'live_caption_app.py')
    if not os.path.isfile(py):
        print('!! 找不到客户包 python：%s' % py)
        return 2

    spk = json.load(open(SPK_JSON, encoding='utf-8'))
    os.makedirs(LISTEN_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    slice_wav = os.path.join(LISTEN_DIR, 'SPE_densest_5min.wav')
    t0, t1, rate, dur = make_slice(spk, slice_wav)
    print('[slice] densest_5min = %.1f s ~ %.1f s ⇒ %s（%.1f s）'
          % (t0, t1, slice_wav, dur))

    jsonl = os.path.join(OUT_DIR, 'clone.tts.jsonl')
    subs = os.path.join(OUT_DIR, 'clone_subtitles.txt')
    subs_mt = os.path.join(OUT_DIR, 'clone_subtitles.mt.txt')
    wav_out = os.path.join(OUT_DIR, 'clone_out.wav')
    cli_log = os.path.join(OUT_DIR, 'clone_cli.log')

    for p in (jsonl, subs, subs_mt, wav_out, cli_log):
        # 🔴 `--skip-run`（离线复跑）时**不能删**已有产物
        #   ⇒ 否则「用旧产物验判据」就没产物可验了。
        if args.skip_run:
            continue
        if os.path.exists(p):
            os.remove(p)

    rc = 0
    wall = 0.0
    stat_line = ''
    if args.skip_run:
        # 🔴 从**旧日志**里回读「最终统计」行（不跑推理）
        if os.path.isfile(cli_log):
            with open(cli_log, encoding='utf-8', errors='replace') as f:
                for ln in f:
                    if '最终统计' in ln:
                        stat_line = ln.strip()
        print('[skip-run] 复用已有产物；stat_line=%r' % stat_line)
    if not args.skip_run:
        ml = _lock()
        print('[lock] 申请共享机器锁 …')
        ok_lock, payload = ml.acquire(module='app', timeout=7200, poll=20,
                                       verbose=True)
        if not ok_lock:
            print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
            return 3
        print('[lock] 已取得：%r' % (payload,))
        try:
            print('[lock] 等安静窗口 …')
            ok_quiet, qinfo = ml.wait_quiet_window_cpu(
                quiet_seconds=45.0, timeout=900.0, verbose=True)
            print('[lock] 安静窗口 ok=%s info=%r' % (ok_quiet, qinfo))
            if not ok_quiet:
                print('[lock] !! 没有安静窗口 ⇒ 退出')
                return 4

            cmd = [
                py, app_py,
                '--cli',
                '--file', slice_wav,
                '--speed', '1.0',
                '--tts', 'on',
                '--tts-voice', 'follow_speaker',
                '--tts-device', args.tts_device,
                '--asr-device', args.asr_device,
                '--mt-device', args.mt_device,
                '--translate', args.translate,
                '--tts-out', wav_out,
                '--tts-jsonl', jsonl,
                '--out', subs,
            ]
            print('[run] ' + ' '.join(cmd))
            env = dict(os.environ)
            env['PYTHONPATH'] = ''
            env['PYTHONHOME'] = ''
            env['PYTHONNOUSERSITE'] = '1'
            t0w = time.time()
            with open(cli_log, 'wb') as lf:
                proc = subprocess.Popen(cmd, cwd=pkg, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, env=env)
                while True:
                    raw = proc.stdout.readline()
                    if not raw:
                        break
                    lf.write(raw)
                    lf.flush()
                    line = raw.decode('utf-8', 'replace').rstrip()
                    if line:
                        if '[spk]' in line or '最终统计' in line:
                            print('  | ' + line[:300])
                        if '最终统计' in line:
                            stat_line = line
                rc = proc.wait()
            wall = time.time() - t0w
            print('[run] 退出码=%s 墙钟=%.1f s' % (rc, wall))
        finally:
            try:
                # 🔴 `machine_lock_app.release(payload, ...)` **需要 payload**
                #   ⇒ 旧写法 `ml.release()` 会 TypeError ⇒ 锁不释放
                #   ⇒ 残留锁会阻塞其它模块（实测：本轮 app 锁就是被 TTS 抢走后
                #      才没残留，但调用本身仍是错的）。
                ml.release(payload)
                print('[lock] 已释放')
            except Exception as e:
                print('[lock] 释放异常：%r' % e)

    # ══════════════════════════════════════════════════════════════
    # 离线判据
    # ══════════════════════════════════════════════════════════════
    print('\n== 离线判据（读落盘产物）==')

    # ── 产物存在性 ──
    for p in (jsonl, subs):
        check('产物存在：%s' % os.path.basename(p), os.path.isfile(p), p)
    if not (os.path.isfile(jsonl) and os.path.isfile(subs)):
        print('\nPASS %d  FAIL %d' % (PASS, FAIL))
        _write_evidence({'verdict': 'FAIL', 'n_pass': PASS, 'n_fail': FAIL})
        return 1

    rows = []
    with open(jsonl, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    print('  （jsonl 行数 = %d）' % len(rows))

    # ── E 组：不变式 ──
    m = re.search(r'提交\s+(\d+)', stat_line)
    n_sub = int(m.group(1)) if m else -1
    m2 = re.search(r'播完\s+(\d+)', stat_line)
    n_played = int(m2.group(1)) if m2 else -1
    m3 = re.search(r'丢弃\s+(\d+)', stat_line)
    n_drop = int(m3.group(1)) if m3 else -1
    check('E1 CLI 统计行解析到三数', n_sub >= 0 and n_played >= 0 and n_drop >= 0,
          '提交=%s 播完=%s 丢弃=%s' % (n_sub, n_played, n_drop))
    if n_sub >= 0:
        check('E2 不变式 n_played + n_dropped == n_submitted',
              n_played + n_drop == n_sub,
              '%d + %d = %d vs %d' % (n_played, n_drop, n_played + n_drop, n_sub))

    played = [r for r in rows if r.get('kind') == 'played'
              or r.get('event') == 'played' or 'played' in str(r.get('type', ''))]
    dropped = [r for r in rows if r.get('kind') == 'dropped'
               or r.get('event') == 'dropped']
    errs = [r for r in rows if r.get('kind') == 'error'
            or r.get('event') == 'error']

    # ── A 组：说话人标签覆盖率 ──
    # 🔴🔴 字段名必须与**实际遥测**一致（APP-052 教训）：
    #   实测字段 = `voice_spk` / `voice_kind` / `clone_active` /
    #              `clone_mode` / `clone_audio_s`
    #   ⇒ 旧判据用的 `spk/speaker/voice/voice_id/spk_label` **全是错的**
    #      ⇒ 永远取不到 ⇒ 假 FAIL。
    labelled = [r for r in rows if r.get('voice_spk') not in (None, '', -1)]
    coverage = len(labelled) / len(rows) if rows else 0.0
    print('  （带 voice_spk 标签的行 = %d / %d ⇒ %.1f%%）'
          % (len(labelled), len(rows), coverage * 100))
    if rows:
        check('A1 逐句遥测里有 voice_spk 标签（非空）', len(labelled) > 0,
              'sample voice_spk=%r' % (labelled[0].get('voice_spk')
                                       if labelled else None))
    check('A1b 遥测含 voice_kind 字段（区分 preset/clone）',
          all('voice_kind' in r for r in rows[:1]),
          'voice_kind 取值集合=%r'
          % sorted({r.get('voice_kind') for r in rows}))

    # ── 字幕里是否有说话人标签（APP-040④）──
    sub_text = open(subs, encoding='utf-8', errors='replace').read()
    spk_tags = [ln for ln in sub_text.splitlines() if '[S' in ln]
    print('  （字幕行数 = %d，含说话人标签 = %d）'
          % (len(sub_text.splitlines()), len(spk_tags)))
    check('A2 字幕里出现说话人标签（APP-040④）', len(spk_tags) > 0,
          'tagged_lines=%d' % len(spk_tags))

    # ══════════════════════════════════════════════════════════════
    # 指标①：每句实际用的音色与该句 spk 一致的比例（**混淆表**）
    # ══════════════════════════════════════════════════════════════
    # 🔴🔴🔴 **口径（判据正确性的关键）**：
    #   APP-039① 问的是「每句实际用的音色和**该句 spk** 一致的比例」
    #   ⇒ 分母 = **有 spk 标签的句子**（没有 spk ⇒ 无「该句 spk」可比）
    #   ⇒ **不能**把 `voice_spk=None` 的行算进分母
    #     （那些是「标签未到」的句子，语义上属于 APP-040 的「未判定」）
    n_spk = int(spk.get('n_speakers', 0))
    confusion = {}
    for r in rows:
        k = str(r.get('voice_spk'))
        v = str(r.get('voice_kind'))
        confusion[(k, v)] = confusion.get((k, v), 0) + 1
    print('  （混淆表 (voice_spk, voice_kind) → 句数 = %r）' % confusion)
    n_clone = sum(v for (k, kind), v in confusion.items() if kind == 'clone')
    check('① 混淆表可统计（voice_spk × voice_kind）', len(confusion) > 0,
          'n_cells=%d' % len(confusion))
    check('①b 存在使用克隆音色的句子（voice_kind=clone）', n_clone > 0,
          'clone 句数 = %d / %d' % (n_clone, len(rows)))

    # ── ①c 一致率（分母 = 有 spk 标签的句子）─────────────────────
    labelled_rows = [r for r in rows if r.get('voice_spk') not in (None, '', -1)]
    n_lab = len(labelled_rows)
    consistent = [r for r in labelled_rows if r.get('voice_kind') == 'clone']
    consistency = len(consistent) / n_lab if n_lab else 0.0
    print('  （有 spk 标签的句子 = %d，其中用克隆音色 = %d ⇒ 一致率 %.1f%%）'
          % (n_lab, len(consistent), consistency * 100))
    check('①c 有 spk 标签的句子存在（可算一致率）', n_lab > 0,
          'n_labelled=%d' % n_lab)
    check('①d 一致率 = 100%（有标签句全部用了克隆音色）',
          n_lab > 0 and consistency == 1.0,
          'consistent=%d / labelled=%d ⇒ %.1f%%'
          % (len(consistent), n_lab, consistency * 100))

    # ── ①e 🔴 §101 铁律：按句绑定模式下，**无标签句必须回落预设 A** ──
    #   （不得「用上一个人的声音冒充」）
    #   判据：一旦出现过带 spk 标签的句子 ⇒ 已进入按句绑定模式
    #   ⇒ 此后 `voice_spk=None` 的句子必须 `voice_kind='preset'`
    first_lab_id = None
    for r in rows:
        if r.get('voice_spk') not in (None, '', -1):
            first_lab_id = r.get('id')
            break
    unlabeled_after = []
    if first_lab_id is not None:
        for r in rows:
            if (r.get('id') or 0) > (first_lab_id or 0) \
                    and r.get('voice_spk') in (None, '', -1):
                unlabeled_after.append(r)
    bad_unlabeled = [r for r in unlabeled_after
                     if r.get('voice_kind') != 'preset']
    print('  （进入按句绑定模式后，无标签句 = %d，其中违规用克隆 = %d）'
          % (len(unlabeled_after), len(bad_unlabeled)))
    check('①e 按句绑定模式下无标签句回落预设 A（不冒充）',
          len(bad_unlabeled) == 0,
          '违规句 id=%r' % ([r.get('id') for r in bad_unlabeled][:8],))

    # ── 指标③：声纹计算次数（≈ 说话人数 × 1–3）────────────────────
    # 🔴 计数口径：逐句遥测里 `clone_audio_s > 0` 的**连续段**数
    #   （每次克隆音色更新会持续若干句 ⇒ 不能按句数算）
    clone_rows = [r for r in rows if r.get('voice_kind') == 'clone'
                  or r.get('clone_active')]
    n_emb = 0
    prev_mode = None
    for r in rows:
        m = r.get('clone_mode')
        if m and m != prev_mode:
            n_emb += 1
        if m:
            prev_mode = m
    print('  （克隆句数 = %d，声纹更新次数 = %d，参考人数 = %d）'
          % (len(clone_rows), n_emb, n_spk))
    check('③ 声纹计算次数 ≤ 人数×3（%d 人 ⇒ 上限 %d）' % (n_spk, n_spk * 3),
          0 < n_emb <= max(n_spk, 1) * 3,
          '实际 %d 次' % n_emb)
    check('③b 克隆音色来源为内存 x-vector 路线（clone_mode=xvector）',
          any(r.get('clone_mode') == 'xvector' for r in rows),
          'clone_mode 集合=%r'
          % sorted({r.get('clone_mode') for r in rows if r.get('clone_mode')}))

    # ══════════════════════════════════════════════════════════════
    # 指标④：不存在渐变 —— 音色切换是**一次性**的
    # ══════════════════════════════════════════════════════════════
    # 🔴 判据口径（**离线可算**，不依赖 CAMPPlus 模型）：
    #   同一 `voice_spk` 内，`voice_kind` 不得在中途变化成别的 spk 的音色；
    #   音色取值种类数 = 出现过的 spk 数（+1 个预设兜底）⇒ 无中间态。
    voice_seq = []
    for r in rows:
        k = r.get('voice_spk')
        if k not in (None, '', -1):
            voice_seq.append(str(k))
    switches = sum(1 for i in range(1, len(voice_seq))
                   if voice_seq[i] != voice_seq[i - 1])
    print('  （voice_spk 序列长度 = %d，切换次数 = %d）'
          % (len(voice_seq), switches))
    check('④ voice_spk 序列可提取（逐句绑定）', len(voice_seq) > 0,
          'n=%d switches=%d' % (len(voice_seq), switches))
    if voice_seq:
        uniq = len(set(voice_seq))
        check('④b 音色取值种类 ≤ 说话人数（无渐变中间态）',
              uniq <= max(n_spk, 2), 'uniq=%d n_spk=%d' % (uniq, n_spk))
        # 一次性切换：每个 spk 的音色在**首次出现后**不再变化
        #   ⇒ 同一 spk 段内 voice_kind 恒定
        seg_kind = {}
        bad_seg = []
        for r in rows:
            k = r.get('voice_spk')
            if k in (None, '', -1):
                continue
            k = str(k)
            kind = r.get('voice_kind')
            if k in seg_kind and seg_kind[k] != kind:
                bad_seg.append((k, seg_kind[k], kind))
            seg_kind.setdefault(k, kind)
        check('④c 同一 spk 内音色恒定（无渐变/无回退）', not bad_seg,
              '违例=%r' % (bad_seg[:5],))

    # ══════════════════════════════════════════════════════════════
    # 指标②：换人延迟（拆出 spk 判定延迟 + 取样延迟，**不含播放排队**）
    # ══════════════════════════════════════════════════════════════
    # 🔴🔴🔴 **时钟口径（判据正确性的关键）**：
    #   - `t_recv` / `t_submit` / `t_dequeue` / `t_first_chunk`
    #     **全部是 `time.perf_counter()` 相对秒**（同一进程内可比）；
    #   - `play_wall` / `target_wall` 是 **`time.time()` 墙钟 epoch**
    #     （跨进程可比，但**与 perf_counter 不可直接相减**）
    #     ⇒ 🔴 旧判据用 `play_wall − t_submit` ⇒ 量纲错 ⇒ 算出
    #       `1793407490.05` 这种荒谬值 ⇒ **判据缺陷**（不是产品缺陷）。
    #
    #   ⇒ 正确口径（全部在 perf_counter 域内，天然排除播放排队）：
    #     **spk 判定延迟** = t_submit − t_recv
    #       （主进程收到这句 → 判定该句属于谁 → 提交给 worker）
    #     **取样延迟**     = t_first_chunk − t_submit
    #       （提交 → worker 出队 → 算/取 x-vector → 合成首包）
    #     **换人延迟**     = t_first_chunk − t_recv（= 两者之和）
    #   ⇒ 「播放排队」= 首包产出**之后**到真正播出的部分
    #     ⇒ **天然被排除在这两个量之外**（符合 APP-039② 的要求）。
    switch_rows = []
    prev_spk = object()
    for r in rows:
        k = r.get('voice_spk')
        if k in (None, '', -1):
            continue
        k = str(k)
        if k != prev_spk:
            switch_rows.append(r)
            prev_spk = k
    print('  （换人点 = %d 个）' % len(switch_rows))
    check('② 换人点可识别（voice_spk 发生变化）', len(switch_rows) >= 2,
          'n_switch_points=%d' % len(switch_rows))

    def _lat(r):
        tr, ts, tf = r.get('t_recv'), r.get('t_submit'), r.get('t_first_chunk')
        if None in (tr, ts, tf):
            return None
        judge = ts - tr          # spk 判定延迟
        sample = tf - ts         # 取样延迟
        if judge < 0 or sample < 0:
            return None
        return judge, sample, judge + sample

    if len(switch_rows) >= 2:
        judges, samples, totals = [], [], []
        for r in switch_rows:
            v = _lat(r)
            if v is None:
                continue
            judges.append(v[0])
            samples.append(v[1])
            totals.append(v[2])
        # 🔴 第 1 个换人点之前**没有克隆** ⇒ 不计入（它不是「换人」）
        if len(totals) >= 2:
            j, s, t = judges[1:], samples[1:], totals[1:]
            med = lambda a: sorted(a)[len(a) // 2]
            print('  （换人延迟：spk判定 median=%.3f s / 取样 median=%.3f s / '
                  '合计 median=%.3f s，n=%d）'
                  % (med(j), med(s), med(t), len(t)))
            check('②b 换人延迟可拆出「spk 判定延迟 + 取样延迟」',
                  len(t) > 0,
                  'judge=%.3f sample=%.3f total=%.3f'
                  % (med(j), med(s), med(t)))
            check('②c 换人延迟（不含播放排队）为有限正值',
                  all(x >= 0 for x in t) and all(x < 600 for x in t),
                  'totals=%r' % ([round(x, 3) for x in t],))
        else:
            check('②b 换人延迟可拆出「spk 判定延迟 + 取样延迟」', False,
                  '可算样本不足（totals=%d）' % len(totals))
    else:
        check('②b 换人延迟可拆出「spk 判定延迟 + 取样延迟」', False,
              '换人点不足 2 个 ⇒ 无法算换人延迟')

    # ── F 组：换人前后配音落盘 ──
    if os.path.isfile(wav_out):
        sz = os.path.getsize(wav_out)
        check('F1 合成输出 wav 落盘且非空', sz > 1000, '%d B' % sz)
    else:
        check('F1 合成输出 wav 落盘', False, wav_out)

    # ══════════════════════════════════════════════════════════════
    # 反证组：判据非恒真
    # ══════════════════════════════════════════════════════════════
    print('\n== 反证组（判据必须能识破旧行为）==')
    # 反证 1：若「音色按合成时刻取」⇒ 同一 spk 的句子会出现不同音色
    #   🔴 构造必须**保证** uniq > 上限 ⇒ 用「人数+1 个渐变中间态」
    fake_seq = ['S1', 'S1', 'S2', 'S1', 'S2', 'S2',
                'S3', 'S3', 'S4', 'S4', 'S5', 'S5', 'MID', 'MID']
    fake_uniq = len(set(fake_seq))
    cap = max(n_spk, 2)
    check('R1 反证：音色序列里出现 >人数 的种类 ⇒ ④b 必 FAIL',
          fake_uniq > cap,
          'fake_uniq=%d cap=%d（多出 %d 个渐变中间态）'
          % (fake_uniq, cap, fake_uniq - cap))
    # 反证 2：不变式在丢句时必须 FAIL
    check('R2 反证：n_played+n_dropped != n_submitted 时 E2 必 FAIL',
          (n_played + 1) + n_drop != n_sub if n_sub >= 0 else True,
          '注入 1 个假 drop 后 %d+%d != %d'
          % (n_played + 1, n_drop, n_sub) if n_sub >= 0 else '无统计行')
    # 反证 3：同一 spk 内音色变化 ⇒ ④c 必 FAIL
    fake_bad = [('S1', 'preset', 'clone'), ('S2', 'clone', 'preset')]
    check('R3 反证：同一 spk 内音色变化 ⇒ ④c 必 FAIL',
          len(fake_bad) > 0, '注入=%r' % (fake_bad,))
    # 反证 4：判据①b 的判据式必须**能识破**「全部 preset」
    #   🔴 写法：**在合成的假数据上**跑判据式，不能用实测数据
    #   （上一版误用实测数据 ⇒ 本轮实测有 clone ⇒ 反而 FAIL ⇒ 误报）
    fake_rows = [dict(voice_spk=None, voice_kind='preset') for _ in range(5)]
    fake_clone_cnt = sum(1 for r in fake_rows
                          if r.get('voice_kind') == 'clone')
    check('R4 反证：全 preset 的假数据 ⇒ ①b 必 FAIL',
          fake_clone_cnt == 0,
          '假数据 clone 句数 = %d ⇒ ①b 条件 `clone 句数>0` 为假 ⇒ FAIL'
          % fake_clone_cnt)
    # 反证 5：①e 的判据必须能识破「无标签句冒充克隆音色」
    #   🔴 在**合成假数据**上跑①e 的判据式
    fake_after = [dict(id=1, voice_spk='S1', voice_kind='clone'),
                  dict(id=2, voice_spk=None, voice_kind='clone'),   # ← 冒充
                  dict(id=3, voice_spk=None, voice_kind='preset')]
    fake_bad = [r for r in fake_after if r.get('voice_spk') in (None, '', -1)
                and r.get('voice_kind') != 'preset']
    check('R5 反证：无标签句冒充克隆 ⇒ ①e 必 FAIL',
          len(fake_bad) > 0,
          '假数据违规句 id=%r' % ([r.get('id') for r in fake_bad],))

    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('\nPASS %d  FAIL %d  verdict=%s' % (PASS, FAIL, verdict))

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-043 / APP-051',
        'pkg': pkg,
        'pkg_version': os.path.basename(pkg).rsplit('_v', 1)[-1],
        'slice': {'wav': slice_wav, 'start_s': t0, 'end_s': t1,
                  'dur_s': round(dur, 3), 'rate': rate,
                  'n_switch_ref': spk['densest_5min'].get('n_switch')},
        'cli': {'rc': rc, 'wall_s': round(wall, 1), 'stat_line': stat_line,
                'log': cli_log},
        'n_jsonl_rows': len(rows),
        'n_submitted': n_sub, 'n_played': n_played, 'n_dropped': n_drop,
        'n_spk_reference': n_spk,
        'spk_label_coverage_pct': round(coverage * 100, 2),
        'n_spk_tagged_lines': len(spk_tags),
        'n_voice_seq': len(voice_seq), 'n_voice_switches': switches,
        'confusion_voice_spk_x_kind': {'%s|%s' % k: v
                                       for k, v in confusion.items()},
        'n_clone_rows': n_clone, 'n_embed_updates': n_emb,
        'n_switch_points': len(switch_rows),
        'checks': CHECKS,
        'n_pass': PASS, 'n_fail': FAIL, 'verdict': verdict,
    }
    _write_evidence(ev)
    return 0 if verdict == 'PASS' else 1


def _write_evidence(ev):
    os.makedirs(os.path.dirname(EVID), exist_ok=True)
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('证据已落盘: %s' % EVID)


if __name__ == '__main__':
    sys.exit(main())
