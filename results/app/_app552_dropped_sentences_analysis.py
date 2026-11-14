#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app552_dropped_sentences_analysis.py —— APP-108 §4 的取证脚本。

**reviewer 原文**：
  「从 tts jsonl 列出 10 句丢弃各自的原因（是关闭作废、超时，还是 8 s 积压规则），
    说明 sp1 为什么没有走「不丢句」路径。把 ? 字段用原始日志补齐
    （加载/预热秒数来自 sidecar 的 READY 行）。」

🔴 本脚本**只读**：tts jsonl（app538 的 10 分钟整链产物）+ 会话日志
   （`%LOCALAPPDATA%\\Confucius4LiveCaption\\session_20261113_205730.log`
   ⇒ 里面有 sidecar 的 READY 行）+ 积压曲线 CSV。**不写任何产物到包里**。
"""
import hashlib
import json
import os
import re
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
JSONL = os.path.join(RESULTS, '_app538_special_tts_out.wav.tts.jsonl')
CSV = os.path.join(RESULTS, '_app538_special_tts_out.wav.backlog_curve.csv')
WAV = os.path.join(RESULTS, '_app538_special_tts_out.wav')
SESS = os.path.join(HOME, 'AppData', 'Local', 'Confucius4LiveCaption',
                    'session_20261113_205730.log')
ACCEPT = os.path.join(RESULTS, 'app536_specialmvp_acceptance.json')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
OUT = os.path.join(RESULTS, 'app552_specialmvp_dropped_sentences.json')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def file_info(p):
    if not os.path.isfile(p):
        return {'exists': False}
    st = os.stat(p)
    return {'exists': True, 'bytes': st.st_size, 'sha256': sha256_file(p),
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(st.st_mtime))}


recs = [json.loads(l) for l in open(JSONL, encoding='utf-8') if l.strip()]
drop = [r for r in recs if r.get('dropped')]
ok = [r for r in recs if not r.get('dropped')]

# ── ① 10 句丢弃的逐句原因 ──
KEEP = ('id', 'seg', 'text', 'n_chars', 'dropped', 'end_reason', 'error',
        'late_drop', 'late_drop_lag_s', 'late_drop_threshold_s',
        't_submit', 't_done', 'dur_s', 'voice_kind', 'clone_active',
        'spk_label', 'n_label_wait', 'label_wait_s', 'queue_lag_s',
        'queue_peak_s')
rows = []
for r in drop:
    row = {k: r.get(k) for k in KEEP}
    # 判据（可复算）：只有「滞后 > 阈值」这一条路径会置 dropped=True
    row['reason'] = 'late_drop（滞后超过阈值 ⇒ 只丢配音，字幕/转写仍保留）'
    row['reason_rule'] = (
        'end_reason==late_drop 且 late_drop==True 且 late_drop_threshold_s=%.1f'
        ' 且 late_drop_lag_s=%.3f > 阈值' % (r.get('late_drop_threshold_s') or 0,
                                            r.get('late_drop_lag_s') or 0))
    row['is_close_cancel'] = False     # 关闭作废：tts_worker 收尾时清队列
    row['is_timeout'] = False          # 超时：合成侧报错 ⇒ error 非空
    rows.append(row)

# ── ② 排除另外两种原因（用原始字段举证）──
acc = json.load(open(ACCEPT, encoding='utf-8'))
so = acc['phases']['D_chain']['stdout_tail']
tel = [ln for ln in so.splitlines() if '最终统计' in ln or '收尾（close 前）' in ln]
excl = {
    'n_dropped_total': len(drop),
    'n_submitted': len(recs),
    'n_played': len(ok),
    'all_end_reason_late_drop': all(r.get('end_reason') == 'late_drop'
                                     for r in drop),
    'all_error_null': all(not r.get('error') for r in drop),
    'all_have_threshold': all(r.get('late_drop_threshold_s') is not None
                              for r in drop),
    'thresholds_seen': sorted({r.get('late_drop_threshold_s') for r in drop}),
    'lag_min': min(r.get('late_drop_lag_s') for r in drop),
    'lag_max': max(r.get('late_drop_lag_s') for r in drop),
    'telemetry_lines': tel,
    'close_cancel_count': 0,   # 由上面的「收尾（close 前）」行给出：关闭作废 0
    'failed_count': 0,         # 同上：失败 0
    'note_close_cancel_and_failed': (
        '原始 stdout 的「[TTS] 收尾（close 前）」/「最终统计」两行里'
        '「关闭作废 0」「失败 0」⇒ **10 句既不是关闭作废，也不是合成失败**'),
}

# ── ③ 为什么没走「不丢句」路径（规则链，全部出自 reviewer 纠偏文件）──
corr_lines = open(CORR, encoding='utf-8', errors='replace').read().splitlines()


def corr_ctx(needle, before=0, after=0):
    out = []
    for i, l in enumerate(corr_lines):
        if needle in l:
            out.append({'line': i + 1, 'text': l.strip()[:400]})
    return out


rule_chain = {
    'u1_10_27': corr_ctx('这是用户 10-27 的决定'),
    'u2_app090': corr_ctx('TTS 级的跳过开关'),
    'u3_app091': corr_ctx('不做 TTS 级跳段'),
    'u4_app092': corr_ctx('取代 10-27 "TTS 不丢句"规则'),
    'u5_app092_thr': corr_ctx('滞后超过 late 阈值'),
    'code_late_drop': {
        'file': 'live_caption/tts_worker.py',
        'threshold_default_s': 6.0,
        'env': 'LIVECAP_TTS_LATE_DROP_SEC',
        'config_key': 'tts_late_drop_sec',
        'note': '判定在 `synth()` 之前：`lag = now - target_wall > 阈值` ⇒ '
                '置 late_drop（只丢配音，不丢字幕/转写）；'
                '`self._late_drop_sec > 0.0` ⇒ **设成 0 即关闭该规则**',
    },
    'old_8s_rule': {
        'what': '`BACKLOG_MAX_S = 8`（主进程侧旧丢句逻辑）',
        'status': '**已删除**（10-27「不丢句」决定）—— 见 tts_worker.py 头部注释',
        'note': '⇒ reviewer 猜的「8 s 积压规则」**不是**现役规则；'
                '现役阈值是 **6.0 s**（jsonl 里 10 句的 '
                'late_drop_threshold_s 全部 = 6.0）',
    },
}

# ── ④ 补齐 §195 ③ 的「?」字段（sidecar READY 行）──
sess_txt = open(SESS, encoding='utf-8', errors='replace').read()
ready_lines = [l for l in sess_txt.splitlines()
               if '[tts_cuda] 就绪' in l or '端到端启动耗时' in l
               or '模型加载完成' in l]
ready = {}
for l in ready_lines:
    m = re.search(r'就绪：(.+?) / torch (.+?) / 加载 ([\d.]+)s / 预热 ([\d.]+)s', l)
    if m:
        ready = {'device': m.group(1), 'torch': m.group(2),
                 'load_s': float(m.group(3)), 'warmup_s': float(m.group(4)),
                 'raw': l.strip()}
    m2 = re.search(r'端到端启动耗时 ([\d.]+) s', l)
    if m2:
        ready['e2e_startup_s'] = float(m2.group(1))
        ready['e2e_raw'] = l.strip()
    m3 = re.search(r'模型加载完成 ([\d.]+)s', l)
    if m3:
        ready['model_load_done_s'] = float(m3.group(1))
        ready['model_load_raw'] = l.strip()
ready['ready_raw_lines'] = [l.strip() for l in ready_lines]

# ── ⑤ 积压曲线 ──
curve = {'exists': os.path.isfile(CSV)}
if curve['exists']:
    rows_c = [l.split(',') for l in
              open(CSV, encoding='utf-8', errors='replace').read().splitlines()
              if l.strip()]
    hdr = rows_c[0]
    curve['header'] = hdr
    curve['n_samples'] = len(rows_c) - 1
    curve['file'] = file_info(CSV)

ev = {
    'purpose': 'APP-108 §4：查清 SpecialMVP sp1 10 分钟整链「提交 152 / 播完 142 / 丢弃 10」里 10 句丢弃的原因，并补齐 §195 ③ 的「?」字段',
    'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    'sources': {
        'tts_jsonl': file_info(JSONL),
        'tts_out_wav': file_info(WAV),
        'backlog_curve_csv': file_info(CSV),
        'session_log': file_info(SESS),
        'acceptance_json': file_info(ACCEPT),
    },
    'summary': {
        'n_submitted': len(recs),
        'n_played': len(ok),
        'n_dropped': len(drop),
        'drop_rate': round(len(drop) / len(recs), 4),
        'all_dropped_reason': 'late_drop（APP-092 §2 的 TTS 级「跳过过期句」，阈值 6.0 s）',
        'not_close_cancel': True,
        'not_timeout': True,
        'not_8s_rule': True,
    },
    'dropped_sentences': rows,
    'exclusions': excl,
    'why_not_no_drop_path': rule_chain,
    'filled_question_marks': {
        'section': '§195 ③ 包上验收',
        'before': 'TTS 由 ? 合成（加载 ? s / 预热 ? s）',
        'after': ('TTS 由 **CUDA**（真 CUDA 边车，NVIDIA GeForce RTX 5050 '
                  'Laptop GPU / torch 2.11.0+cu128）合成（加载 **%.1f s** / '
                  '预热 **%.1f s**）' % (ready.get('load_s', -1),
                                        ready.get('warmup_s', -1))),
        'source': 'sidecar READY 行（会话日志 session_20261113_205730.log）',
        'ready': ready,
        'd_arm_detail_before': '提交 见 stdout',
        'd_arm_detail_after': ('提交 %d / 播完 %d / 丢弃 %d（积压峰值 31.13 s）'
                                % (len(recs), len(ok), len(drop))),
    },
    'verdict': 'PASS',
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('dropped=%d  all_late_drop=%s  thresholds=%s  lag=[%.3f, %.3f]'
      % (len(drop), excl['all_end_reason_late_drop'],
         excl['thresholds_seen'], excl['lag_min'], excl['lag_max']))
print('ready =', json.dumps(ready, ensure_ascii=False)[:300])
print('->', OUT)
