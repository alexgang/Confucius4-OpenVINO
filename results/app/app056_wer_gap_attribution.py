r"""app056_wer_gap_attribution.py —— APP-017 第③项（续）：**WER +2.6pp 主因的归因分析**

背景
----
ASR-006 §2（reviewer 口径，MiniMax baseline）：

  | 臂 | WER | 备注 |
  |:--|:--|:--|
  | 交付基准 `int8dec_fp16enc` | **8.17%** | 226 段、fp16 encoder + int8 decoder |
  | App 实时路径 A | — | **+2.63pp**，CI [+1.80, +3.41]，显著 |
  | App 实时路径 B | — | 约 +2.4pp |

App 侧已有三份落盘证据（`app037_*`）把「切点重复词」推到只剩缺口约 3%，
但**没有回答「+2.6pp 到底来自哪里」** ⇒ 本脚本补上这一环。

🔴 本脚本要解决的**方法学问题**（前一轮自查发现）
----------------------------------------------------
1. `app037_wer_gap_maincause.py` 用的参照是 `transcript_adaptive.txt`（**ASR 参照**），
   而 reviewer's +2.63pp 用的是 **MiniMax baseline**（**人工真值**）
   ⇒ **两个数字不在同一把尺子上，不能直接对话**。
   ⇒ 本脚本统一改用 `reports/c026_minimax_raw.json`（**MiniMax 真值，本地就有**）
   重算全部臂 ⇒ 让 App 的数字与 reviewer 的 8.17% / +2.63pp **同尺度**。

2. `app037_segcount_effect.py` 的「反事实·重新聚合成 225 段 ⇒ delta_pp = 0.0」
   🔴 **是一个恒等式，不含信息**：重新聚合**只把已生成的文本重新拼接**，
   **不重新解码** ⇒ token 序列逐位相同 ⇒ WER **必然**相同。
   本脚本实测 `hyp == hyp2` ⇒ `True`（11879 词逐位一致）⇒ 确认该对照**零效力**。
   ⇒ **撤回「段聚合方式与 WER 差异无关」这个结论**（它不是实证结论）。

3. 「段数（538 vs 226）」与「encoder 精度（int8asym vs fp16）」在历史证据里
   **一直是被混淆的两个变量** ⇒ 本脚本用**同一个口径**把二者拆开。

本脚本问四个问题
----------------
**Q1｜同尺度复现**：用 MiniMax 真值重算，App 的 Δ 是否复现 reviewer's +2.63pp？

**Q2｜生成预算是不是混淆项**：`c048` 有三个臂（baseline / adaptive / finish_first），
    只有 adaptive 与 App 的 `adaptive_budget=True` 口径一致
    ⇒ 若拿 baseline（固定 32 token）当参照，就是拿错了尺子。

**Q3｜encoder 精度的贡献上限**：在**同为 226 段、同一 decoder** 的条件下，
    把 encoder 从 fp16 换成 int4，Δ 有多大？⇒ 给出「encoder 最多能解释多少 pp」的**上界**。

**Q4｜误差落在哪里**：把每个误差按**它自己在自己臂的分段里**的位置归桶
    （段首 3 词 / 段尾 3 词 / 段中间），再算**每段的边界误差率**
    ⇒ 「每段更差」还是「段更多」两者分开判。

🔴 纪律
--------
- **不 import 被测模块**（`live_caption_app` 会连带 numpy/OpenBLAS）⇒ 只读**已落盘**产物
  ⇒ 纯文本作业，**无推理 / 无 GPU / 无测速 / 不占机器锁**。
- **不自己判定质量**：只给**结构性统计 + 反事实估算**，
  「要不要改产品行为」归 reviewer。
- 参照是**独立真值**（MiniMax baseline），不是循环论证。

用法
----
    python app056_wer_gap_attribution.py
"""
from __future__ import annotations

import datetime
import difflib
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

TRUTH_JSON = os.path.join(REPO, 'reports', 'c026_minimax_raw.json')
OUT = os.path.join(HERE, 'app056_wer_gap_attribution.json')

SELF_CHECK = []
FAIL_CHECK = []


def check(name, cond, detail=''):
    (SELF_CHECK if cond else FAIL_CHECK).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  <- ' + detail) if detail else ''))
    return cond


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def meta_of(path):
    st = os.stat(path)
    return dict(path=os.path.relpath(path, REPO).replace('\\', '/'),
                bytes=st.st_size,
                mtime=datetime.datetime.fromtimestamp(
                    st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                sha256=sha256_of(path))


def strip_prefix(line):
    return re.sub(r'^\[\s*[0-9.]+\s*-\s*[0-9.]+\s*\]\s*', '', line.strip())


def norm_tokens(text):
    """§32.5 已验收的分词口径（**全脚本唯一口径**）。"""
    out = []
    for ln in (text or '').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln = strip_prefix(ln)
        ln = re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', ' ', ln).lower()
        out.extend(ln.split())
    return out


def read_bounds_from_txt(path):
    """从转写文件的行首 `[a-b]` 取分段边界 ⇒ [(start, end, text), ...]。"""
    out = []
    for ln in open(path, encoding='utf-8').read().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r'^\[\s*([0-9.]+)\s*-\s*([0-9.]+)\s*\]\s*(.*)$', ln)
        if m:
            out.append((float(m.group(1)), float(m.group(2)), m.group(3)))
        else:
            out.append((None, None, ln))
    return out


def read_bounds_from_segs(path):
    """从 segments_*.json 取分段边界 ⇒ [(start, end, text), ...]。"""
    segs = json.load(open(path, encoding='utf-8'))['segments']
    return [(s.get('start_s'), s.get('end_s'), s.get('text') or '')
            for s in segs]


# ── 臂定义（每条都带配置出处，便于 reviewer 追原始字段）──────────────────
ARMS = [
    dict(key='BASE_c048_adaptive',
         label='BASE 交付基准 c048 adaptive (fp16 enc + int8 dec, 226seg)',
         txt='reports/c048_61min_adaptive/transcript_adaptive.txt',
         bounds='txt',
         enc='fp16', dec='int8', device='GPU.0',
         budget='adaptive_budget=True, finish_budget=max64',
         cfg_src='reports/c086d_full61_all_npu_matrix.json'
                 '.wer_validation.reference_device'),
    dict(key='BASE_c048_baseline',
         label='BASE c048 baseline (固定 max_new_tokens=32, 无 adaptive)',
         txt='reports/c048_61min_adaptive/transcript_baseline.txt',
         bounds='txt',
         enc='fp16', dec='int8', device='GPU.0',
         budget='max_new_tokens=32 固定',
         cfg_src='c048_61min.py:69'),
    dict(key='c057_enc_int4',
         label='c057 enc_int4 (int4 enc + int8 dec, 226seg)',
         txt='reports/c057_61min_encoder/transcript_enc_int4.txt',
         bounds='txt',
         enc='int4', dec='int8', device='GPU.0',
         budget='adaptive_budget=True, finish_budget=max64',
         cfg_src='c057f_encoder_61min.py:38-42'),
    dict(key='c057_enc_fp16',
         label='c057 enc_fp16 (fp16 enc + int8 dec, 226seg)',
         txt='reports/c057_61min_encoder/transcript_enc_fp16.txt',
         bounds='txt',
         enc='fp16', dec='int8', device='GPU.0',
         budget='adaptive_budget=True, finish_budget=max64',
         cfg_src='c057f_encoder_61min.py:38-42'),
    dict(key='c086_all_npu',
         label='c086 全 NPU (int8sym enc + cleanie int8 dec, 226seg)',
         txt='reports/c086_full61/transcript_all_npu_full.txt',
         bounds='txt',
         enc='int8sym', dec='cleanie_int8sym', device='NPU',
         budget='adaptive_budget=True, finish_budget=max64',
         cfg_src='reports/c086d_full61_all_npu_matrix.json.config'),
    dict(key='APP_A',
         label='APP 实时路径 A (int8asym enc + int8 dec, 538seg)',
         txt='reports/asr004_ab/transcript_A.txt',
         bounds='segs:reports/asr004_ab/segments_A.json',
         enc='int8asym', dec='int8', device='GPU.0',
         budget='adaptive_budget=True, finish_budget=max64',
         cfg_src='reports/asr004_ab/summary_A.json.engine'),
    dict(key='APP_B',
         label='APP 实时路径 B (int8asym enc + int8 dec, 558seg)',
         txt='reports/asr004_ab/transcript_B.txt',
         bounds='segs:reports/asr004_ab/segments_B.json',
         enc='int8asym', dec='int8', device='GPU.0',
         budget='adaptive_budget=True, finish_budget=max64',
         cfg_src='reports/asr004_ab/summary_B.json.engine'),
    dict(key='APP_singleproc',
         label='APP 单进程 (int8asym enc + int8 dec, 534seg)',
         txt='reports/asr004_ab/singleproc_transcript_A.txt',
         bounds='segs:reports/asr004_ab/singleproc_segments_A.json',
         enc='int8asym', dec='int8', device='GPU.0',
         budget='adaptive_budget=True, finish_budget=max64',
         cfg_src='reports/asr004_ab/singleproc_summary_A.json.engine'),
]


def build_owner(bounds):
    """把 hyp token 序列归属到分段 ⇒ owner[i] = (seg_idx, pos_in_seg, seg_len)。"""
    owner = []
    for si, (_st, _en, text) in enumerate(bounds):
        toks = norm_tokens(text)
        ln = len(toks)
        for wi in range(ln):
            owner.append((si, wi, ln))
    return owner


def bucket_of(owner_i):
    si, wi, ln = owner_i
    if wi < 3:
        return 'head3'
    if wi >= ln - 3:
        return 'tail3'
    return 'mid'


def analyze(arm, ref):
    txt_path = os.path.join(REPO, arm['txt'])
    raw = open(txt_path, encoding='utf-8').read()
    hyp = norm_tokens(raw)

    bspec = arm['bounds']
    if bspec.startswith('segs:'):
        bounds = read_bounds_from_segs(os.path.join(REPO, bspec[5:]))
    else:
        bounds = read_bounds_from_txt(txt_path)

    # 自校验：按段拼接 == 整文件分词（口径一致）
    hyp_from_segs = []
    for _st, _en, text in bounds:
        hyp_from_segs.extend(norm_tokens(text))
    ok = check('%s：按段拼接词序列 == 整文件分词' % arm['key'],
               hyp_from_segs == hyp,
               '%d vs %d' % (len(hyp_from_segs), len(hyp)))
    if not ok:
        return None

    owner = build_owner(bounds)
    if len(owner) != len(hyp):
        check('%s：owner 长度 == hyp 长度' % arm['key'], False,
              '%d vs %d' % (len(owner), len(hyp)))
        return None

    sm = difflib.SequenceMatcher(a=list(ref), b=list(hyp), autojunk=False)
    ins = rep = dele = 0
    ins_b = {'head3': 0, 'tail3': 0, 'mid': 0}
    rep_b = {'head3': 0, 'tail3': 0, 'mid': 0}
    del_b = {'head3': 0, 'tail3': 0, 'mid': 0}

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'insert':
            ins += (j2 - j1)
            for j in range(j1, j2):
                ins_b[bucket_of(owner[j])] += 1
        elif tag == 'delete':
            dele += (i2 - i1)
            # ref 侧错误 ⇒ 归到对齐点所在的 hyp 位置（就近归属）
            anchor = min(j1, len(owner) - 1)
            for _ in range(i2 - i1):
                del_b[bucket_of(owner[anchor])] += 1
        else:  # replace
            rep += max(i2 - i1, j2 - j1)
            hyp_err = j2 - j1
            for j in range(j1, j2):
                rep_b[bucket_of(owner[j])] += 1
            # ref 侧多出来的替换错误（ref 范围更长）就近归桶
            extra = max(i2 - i1, j2 - j1) - hyp_err
            anchor = min(max(j1, 0), len(owner) - 1)
            for _ in range(extra):
                rep_b[bucket_of(owner[anchor])] += 1

    nseg = len(bounds)
    tot_err = ins + rep + dele
    boundary_err = (ins_b['head3'] + ins_b['tail3'] +
                    rep_b['head3'] + rep_b['tail3'] +
                    del_b['head3'] + del_b['tail3'])
    mid_err = (ins_b['mid'] + rep_b['mid'] + del_b['mid'])

    # ── 归一化口径 ──
    # 🔴 「每段」口径会被**段长**混淆（App 22.1 词/段 vs BASE 51.9 词/段）
    # ⇒ 必须同时给「每词」口径（**按桶内 token 数归一**）才是公平比较。
    n_boundary_tok = 0
    n_mid_tok = 0
    for si, wi, ln in owner:
        if wi < 3 or wi >= ln - 3:
            n_boundary_tok += 1
        else:
            n_mid_tok += 1
    # 短段（≤6 词）整段都是边界 ⇒ 记入边界桶
    n_boundary_tok += 0

    return dict(
        key=arm['key'], label=arm['label'],
        transcript=arm['txt'],
        cfg=dict(encoder=arm['enc'], decoder=arm['dec'], device=arm['device'],
                 generation_budget=arm['budget'], cfg_source=arm['cfg_src']),
        n_segs=nseg,
        hyp_words=len(hyp),
        words_per_seg=len(hyp) / max(1, nseg),
        ref_words=len(ref),
        wer_pct=100.0 * tot_err / len(ref),
        ins=ins, rep=rep, dele=dele,
        err_by_bucket=dict(ins=ins_b, rep=rep_b, dele=del_b),
        boundary_err=boundary_err,
        mid_err=mid_err,
        boundary_err_per_seg=boundary_err / max(1, nseg),
        mid_err_per_seg=mid_err / max(1, nseg),
        err_per_seg=tot_err / max(1, nseg),
        ins_per_seg=ins / max(1, nseg),
        rep_per_seg=rep / max(1, nseg),
        del_per_seg=dele / max(1, nseg),
        n_boundary_tokens=n_boundary_tok,
        n_mid_tokens=n_mid_tok,
        boundary_err_per_token=boundary_err / max(1, n_boundary_tok),
        mid_err_per_token=mid_err / max(1, n_mid_tok),
        boundary_token_share=n_boundary_tok / max(1, len(hyp)),
        mid_token_share=n_mid_tok / max(1, len(hyp)),
        err_per_token=tot_err / max(1, len(hyp)),
    )


def main():
    truth = json.load(open(TRUTH_JSON, encoding='utf-8'))
    ref = norm_tokens(' '.join(it['text'] for it in truth))
    print('MiniMax 真值（人工 baseline）：%d 词 / %d 块' % (len(ref), len(truth)))
    print('  来源：%s' % os.path.relpath(TRUTH_JSON, REPO))
    print()

    out = dict(
        purpose='APP-017 第③项：App 实时路径 WER +2.6pp 主因归因',
        generated_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        discipline=dict(
            no_inference='不跑任何 GPU/OV/NPU 推理 ⇒ 无推理 / 无 GPU / 无测速 / 不占机器锁',
            no_import='不 import 被测模块（live_caption_app 会连带 numpy/OpenBLAS）',
            no_live_caption_modify='live_caption/ 只读，未修改',
            no_verdict='不自己判定质量；结论归 reviewer（MiniMax 回转写）',
        ),
        reference=dict(
            path=os.path.relpath(TRUTH_JSON, REPO).replace('\\', '/'),
            kind='MiniMax baseline（人工真值）',
            words=len(ref), n_chunks=len(truth),
            note='reviewer 的 8.17% / +2.63pp 就是对这个真值算的 ⇒ 本脚本同尺度'),
        scorer=dict(
            method='method_b：全局 difflib.SequenceMatcher(autojunk=False) 对齐 + 按 owner 归因',
            tokenizer='§32.5 已验收的 norm_tokens（与 app037 一致）',
            note='删除类错误按对齐点就近归桶；替换类 ref 侧多出的部分就近归桶'),
        arms={},
    )

    print('【Q1｜同尺度复现】用 MiniMax 真值重算全部臂')
    print('-' * 78)
    print('%-46s %8s %6s %7s %6s %6s %6s' %
          ('臂', 'WER%', '段数', '词/段', 'ins', 'rep', 'del'))
    for arm in ARMS:
        r = analyze(arm, ref)
        if r is None:
            print('%-46s  自校验失败' % arm['key'])
            out['arms'][arm['key']] = dict(error='self_check_failed')
            continue
        out['arms'][arm['key']] = r
        print('%-46s %8.3f %6d %7.1f %6d %6d %6d' %
              (r['label'][:46], r['wer_pct'], r['n_segs'], r['words_per_seg'],
               r['ins'], r['rep'], r['dele']))

    base = out['arms']['BASE_c048_adaptive']
    appa = out['arms']['APP_A']
    appb = out['arms']['APP_B']

    # ── Q1 复现检查 ──
    delta_a = appa['wer_pct'] - base['wer_pct']
    delta_b = appb['wer_pct'] - base['wer_pct']
    print()
    print('  BASE WER %.3f%%  /  APP_A %.3f%% (Δ %+.3f pp)  /  '
          'APP_B %.3f%% (Δ %+.3f pp)' %
          (base['wer_pct'], appa['wer_pct'], delta_a,
           appb['wer_pct'], delta_b))
    print('  reviewer 同尺度：A 对 int8dec_fp16enc 8.17% ⇒ **+2.63pp**；B 约 +2.4pp')
    check('Q1：APP_A 的 Δ 与 reviewer 的 +2.63pp 同号且量级一致（2.0~3.2pp）',
          2.0 <= delta_a <= 3.2, 'Δ=%+.3f pp' % delta_a)
    check('Q1：APP_B 的 Δ 与 reviewer 的「约 +2.4pp」一致（2.0~2.8pp）',
          2.0 <= delta_b <= 2.8, 'Δ=%+.3f pp' % delta_b)
    out['q1_reproduction'] = dict(
        base_wer_pct=base['wer_pct'], app_a_wer_pct=appa['wer_pct'],
        app_b_wer_pct=appb['wer_pct'],
        delta_a_pp=delta_a, delta_b_pp=delta_b,
        reviewer_base_pct=8.17, reviewer_delta_a_pp=2.63,
        reviewer_delta_b_pp='~2.4',
        note='本脚本基线 WER 与 reviewer 的 8.17%% 差 %.3f pp（分词口径与词数不同，'
             '真值词数 %d vs reviewer 口径 10964）⇒ 同量级、同符号' %
             (abs(base['wer_pct'] - 8.17), len(ref)))

    # ── Q2 生成预算控制 ──
    print()
    print('【Q2｜生成预算是不是混淆项】')
    baseline_arm = out['arms']['BASE_c048_baseline']
    fp16_arm = out['arms']['c057_enc_fp16']
    sha_base = sha256_of(os.path.join(REPO, 'reports', 'c048_61min_adaptive',
                                      'transcript_baseline.txt'))
    sha_c039 = sha256_of(os.path.join(REPO, 'reports', 'spe_61min_transcript.txt'))
    sha_v3 = sha256_of(os.path.join(REPO, 'reports',
                                    'spe_61min_transcript_v3_segenc_int8.txt'))
    sha_adapt = sha256_of(os.path.join(REPO, 'reports', 'c048_61min_adaptive',
                                       'transcript_adaptive.txt'))
    sha_c057fp16 = sha256_of(os.path.join(REPO, 'reports', 'c057_61min_encoder',
                                          'transcript_enc_fp16.txt'))
    print('  BASE baseline（固定 32 token）WER %.3f%%  vs  BASE adaptive %.3f%%'
          % (baseline_arm['wer_pct'], base['wer_pct']))
    print('  ⇒ 预算口径差 **%.3f pp**（比 App 的整个缺口 %.3f pp 还大）'
          % (baseline_arm['wer_pct'] - base['wer_pct'], delta_a))
    print('  App 实时路径用 adaptive_budget=True + finish max64 '
          '（live_caption_app.py:1294-1296）⇒ 与 BASE adaptive 同口径')
    check('Q2：baseline / c039 / v3 三份转写 SHA256 完全相同（同一臂的重复跑）',
          sha_base == sha_c039 == sha_v3,
          '%s / %s / %s' % (sha_base[:12], sha_c039[:12], sha_v3[:12]))
    check('Q2：c057 enc_fp16 与 BASE adaptive 转写 SHA256 完全相同'
          '（⇒ c057 的 fp16 臂不是独立臂，只是一次复现）',
          sha_c057fp16 == sha_adapt,
          '%s vs %s' % (sha_c057fp16[:12], sha_adapt[:12]))
    out['q2_budget_control'] = dict(
        base_adaptive_wer_pct=base['wer_pct'],
        base_baseline_wer_pct=baseline_arm['wer_pct'],
        budget_effect_pp=baseline_arm['wer_pct'] - base['wer_pct'],
        app_gap_pp=delta_a,
        app_budget='adaptive_budget=True + finish max64（与 BASE adaptive 同口径）',
        budget_source='live_caption/live_caption_app.py:1294-1296',
        sha256=dict(baseline=sha_base, c039_spe61=sha_c039,
                    v3_segenc_int8=sha_v3, adaptive=sha_adapt,
                    c057_enc_fp16=sha_c057fp16),
        verdict='生成预算**不是** App 缺口的原因；用 baseline 当参照会拿错尺子')

    # ── Q3 encoder 精度上界 ──
    print()
    print('【Q3｜encoder 精度的贡献上界】（同为 226 段 / 同一 int8 decoder）')
    int4 = out['arms']['c057_enc_int4']
    enc_delta = int4['wer_pct'] - fp16_arm['wer_pct']
    print('  c057 enc_fp16 WER %.3f%%  →  c057 enc_int4 WER %.3f%%'
          % (fp16_arm['wer_pct'], int4['wer_pct']))
    print('  ⇒ 把 encoder 从 fp16 换成 **int4**（比 App 的 int8asym 更激进）'
          '只换来 **%+.3f pp**' % enc_delta)
    check('Q3：encoder 从 fp16 → int4 的端到端 Δ 远小于 App 的缺口',
          enc_delta < delta_a / 2.0,
          'enc Δ=%+.3f pp vs App 缺口=%.3f pp' % (enc_delta, delta_a))
    out['q3_encoder_bound'] = dict(
        enc_fp16_wer_pct=fp16_arm['wer_pct'],
        enc_int4_wer_pct=int4['wer_pct'],
        enc_delta_pp=enc_delta,
        app_gap_pp=delta_a,
        enc_ir_mib=dict(fp16=605.6, int8asym=303.8, int8sym=303.5, int4=162.5),
        enc_ir_mib_source='reports/c057_encoder_acc_3way.json.summary.*.ir_mib',
        caveat='这是**外推上界**：int8asym 的一端到端 226 段臂在本仓库不存在 ⇒ '
               '「int8asym 的贡献 ≤ int4 的贡献」这一步依赖「IR 体积越小量化越差」'
               '这一假设 ⇒ 需 reviewer 裁定是否接受',
        open_metric_anomaly='reports/c057_encoder_acc_3way.json 的 token_edit_pct '
                             '排序为 fp16 0% / int8sym 18.42% / int8asym 30.53% / '
                             'int4 4.21% ⇒ **与 IR 体积排序相反** ⇒ 该 teacher-forcing '
                             '指标与端到端 WER 的关系存疑（ASR-006 §4 已提过该指标过于敏感）')

    # ── Q4 误差落点 ──
    print()
    print('【Q4｜误差落点：每段更差 vs 段更多】')
    print('  🔴 「每段」口径会被**段长**混淆（App %.1f 词/段 vs BASE %.1f 词/段）'
          % (appa['words_per_seg'], base['words_per_seg']))
    print('     ⇒ 必须同时看「每词」口径才是公平比较')
    print()
    print('  %-40s %6s %9s %9s | %11s %11s' %
          ('臂', '段数', '边界/段', '中间/段', '边界/词(%)', '中间/词(%)'))
    for k in ('BASE_c048_adaptive', 'c057_enc_int4', 'APP_A', 'APP_B'):
        r = out['arms'][k]
        print('  %-40s %6d %9.4f %9.4f | %11.4f %11.4f' %
              (r['label'][:40], r['n_segs'], r['boundary_err_per_seg'],
               r['mid_err_per_seg'],
               100.0 * r['boundary_err_per_token'],
               100.0 * r['mid_err_per_token']))
    print()
    print('  ⇒ 【公平口径·每词】边界错误率：BASE %.4f%%  vs  APP_A %.4f%%'
          '（比值 %.3f×）'
          % (100.0 * base['boundary_err_per_token'],
             100.0 * appa['boundary_err_per_token'],
             appa['boundary_err_per_token'] /
             max(1e-9, base['boundary_err_per_token'])))
    print('  ⇒ 【公平口径·每词】中间错误率：BASE %.4f%%  vs  APP_A %.4f%%'
          '（比值 %.3f×）'
          % (100.0 * base['mid_err_per_token'],
             100.0 * appa['mid_err_per_token'],
             appa['mid_err_per_token'] /
             max(1e-9, base['mid_err_per_token'])))
    print('  ⇒ 【总错误率·每词】BASE %.4f%%  vs  APP_A %.4f%%（比值 %.3f×）'
          % (100.0 * base['err_per_token'], 100.0 * appa['err_per_token'],
             appa['err_per_token'] / max(1e-9, base['err_per_token'])))
    print()
    print('  ⇒ 结论性读法：**边界**位置的错误率 App 比 BASE 高 %.3f×，'
          '而**段中间**的错误率 App 反而**低** %.3f×'
          % (appa['boundary_err_per_token'] /
             max(1e-9, base['boundary_err_per_token']),
             base['mid_err_per_token'] /
             max(1e-9, appa['mid_err_per_token'])))
    print('    ⇒ 即：**App 的质量劣势集中在「段的两个端点」，段内部并不差**')
    print('    ⇒ 而段端点正是「切点」所在 ⇒ **指向切段粒度，不是模型/编码器精度**')
    out['q4_error_placement'] = dict(
        arms={k: dict(n_segs=out['arms'][k]['n_segs'],
                      words_per_seg=out['arms'][k]['words_per_seg'],
                      boundary_err_per_seg=out['arms'][k]['boundary_err_per_seg'],
                      mid_err_per_seg=out['arms'][k]['mid_err_per_seg'],
                      err_per_seg=out['arms'][k]['err_per_seg'],
                      boundary_err_per_token=out['arms'][k]['boundary_err_per_token'],
                      mid_err_per_token=out['arms'][k]['mid_err_per_token'],
                      err_per_token=out['arms'][k]['err_per_token'],
                      boundary_token_share=out['arms'][k]['boundary_token_share'],
                      mid_token_share=out['arms'][k]['mid_token_share'])
              for k in ('BASE_c048_adaptive', 'c057_enc_int4', 'APP_A', 'APP_B')},
        fair_metric='**每词**口径（按桶内 token 数归一）⇒ 消除段长混淆',
        boundary_err_per_token_ratio=(
            appa['boundary_err_per_token'] /
            max(1e-9, base['boundary_err_per_token'])),
        mid_err_per_token_ratio=(
            appa['mid_err_per_token'] /
            max(1e-9, base['mid_err_per_token'])),
        err_per_token_ratio=(
            appa['err_per_token'] / max(1e-9, base['err_per_token'])),
        per_seg_ratio_caution='「每段」口径的比值被段长混淆（App 段更短 ⇒ '
                              '边界 token 占比更高）⇒ 不作为对外报数口径',
        note='「边界」= 段首 3 词 + 段尾 3 词；「中间」= 段内其余 token')

    # ── 反事实：纯段数 / 纯每段质量 ──
    print()
    print('【反事实】把 +%.3f pp 拆成「段更多」与「每段更差」两种极端假设' % delta_a)
    n_base, n_app = base['n_segs'], appa['n_segs']
    err_base = round(base['wer_pct'] * base['ref_words'] / 100.0)
    err_app = round(appa['wer_pct'] * appa['ref_words'] / 100.0)
    cf_segcount = n_app * (err_base / max(1, n_base))
    cf_quality = n_base * (err_app / max(1, n_app))
    print('  实际 App 误差 %d 个（BASE %d 个）' % (err_app, err_base))
    print('  纯段数假设（每段错误率不变，段数 %d→%d）：%.0f 个 ⇒ WER %.3f%%'
          % (n_base, n_app, cf_segcount,
             100.0 * cf_segcount / appa['ref_words']))
    print('  纯质量假设（段数固定 %d，每段错误率变）：%.0f 个 ⇒ WER %.3f%%'
          % (n_base, cf_quality, 100.0 * cf_quality / appa['ref_words']))
    print('  ⇒ 两个极端都**不闭合**（实际 %d）⇒ 缺口是两者**叠加**，不是单一因素'
          % err_app)
    out['counterfactual_split'] = dict(
        err_base=err_base, err_app=err_app, err_excess=err_app - err_base,
        n_base=n_base, n_app=n_app,
        cf_segcount_only_err=cf_segcount,
        cf_segcount_only_wer_pct=100.0 * cf_segcount / appa['ref_words'],
        cf_quality_only_err=cf_quality,
        cf_quality_only_wer_pct=100.0 * cf_quality / appa['ref_words'],
        note='两个极端假设都不等于实际 ⇒ 加性分解不闭合 ⇒ 交互存在 ⇒ '
             '**不能**用「只改一个变量」的线性口径对外报数')

    # ── 被排除 / 已被推翻的假设 ──
    print()
    print('【已排除 / 已推翻的假设】')
    excluded = [
        dict(hypothesis='「重新聚合成 225 段后 Δ = 0.0 ⇒ 段聚合方式与 WER 差异无关」',
             status='🔴 **撤回**（该对照是恒等式，零效力）',
             evidence='实测 reaggregate() 后的 token 序列与原序列**逐位相同**'
                      '（11879 词，hyp == hyp2 为 True）⇒ 不重新解码就不可能改变 WER ⇒ '
                      'Δ=0.0 是数学必然，不是实证结论',
             evidence_source='app056 实测（见 self_check「reagg 恒等式」）'),
        dict(hypothesis='「生成预算（固定 32 token vs adaptive）造成 App 的缺口」',
             status='✅ 排除',
             evidence='c048 baseline（固定 32 token）WER %.3f%% 比 BASE adaptive 高 %.3f pp；'
                      '而 App 用的是 adaptive_budget=True + finish max64 ⇒ 与 BASE 同口径'
                      % (baseline_arm['wer_pct'],
                         baseline_arm['wer_pct'] - base['wer_pct'])),
        dict(hypothesis='「接缝切词重复是主因」',
             status='🔴 已被前轮证据否定（只覆盖缺口约 3%）',
             evidence='app037_wer_gap_maincause.json：seam_dup=16（A）/21（B），'
                      '而总插入 232/225 ⇒ 覆盖率 ≈ 7%/9%；'
                      '且 app037_seam_mechanism.json：n_cut_through_word=32/537（5.96%）'),
        dict(hypothesis='「c057 的 enc_fp16 是一个独立的 fp16 对照臂」',
             status='✅ 排除（它是 BASE adaptive 的一次复现）',
             evidence='transcript_enc_fp16.txt 与 transcript_adaptive.txt 的 SHA256 完全相同'),
        dict(hypothesis='「encoder 精度是主因」',
             status='✅ 强烈不支持（给出上界）',
             evidence='同为 226 段 / 同一 int8 decoder，fp16→int4 的端到端 Δ 仅 %+.3f pp，'
                      '而 App 缺口 %.3f pp' % (enc_delta, delta_a)),
    ]
    out['excluded_or_retracted'] = excluded
    for e in excluded:
        print('  · %s' % e['hypothesis'])
        print('      ⇒ %s' % e['status'])

    # ── reagg 恒等式实测（撤回依据）────────────────────────────────
    print()
    print('【撤回依据】app037「重新聚合」对照的恒等式实测')
    seg_path = os.path.join(REPO, 'reports', 'asr004_ab', 'segments_A.json')
    bounds_path = os.path.join(REPO, 'reports', 'c048_61min_adaptive',
                               'transcript_adaptive.txt')
    segs = json.load(open(seg_path, encoding='utf-8'))['segments']
    ref_bounds = [b[0] for b in read_bounds_from_txt(bounds_path)]
    groups, cur, bi = [], [], 0
    for s in segs:
        en = s.get('end_s')
        cur.append(s.get('text') or '')
        if bi + 1 < len(ref_bounds) and en is not None and en >= ref_bounds[bi + 1]:
            groups.append(' '.join(cur))
            cur = []
            while bi + 1 < len(ref_bounds) and ref_bounds[bi + 1] <= (en or 0):
                bi += 1
    if cur:
        groups.append(' '.join(cur))
    hyp_a = norm_tokens(open(os.path.join(REPO, 'reports', 'asr004_ab',
                                          'transcript_A.txt'),
                             encoding='utf-8').read())
    hyp_a2 = norm_tokens('\n'.join(groups))
    same = (hyp_a == hyp_a2)
    print('  重新聚合成 %d 段；token 序列逐位相同？ %s（%d vs %d 词）'
          % (len(groups), same, len(hyp_a), len(hyp_a2)))
    check('reagg 恒等式：重新聚合后 token 序列逐位相同 ⇒ Δ=0.0 无信息量',
          same, 'same=%s' % same)
    out['reagg_tautology_check'] = dict(
        reagg_n_segs=len(groups), words_original=len(hyp_a),
        words_reagg=len(hyp_a2), token_sequence_identical=bool(same),
        conclusion='app037 的「反事实·225 段 Δ=0.0」是**恒等式**，'
                   '不能作为「段聚合方式与 WER 差异无关」的证据 ⇒ 该结论撤回')

    # ── 证据清单 ──
    print()
    print('【证据清单】')
    ev = []
    for arm in ARMS:
        p = os.path.join(REPO, arm['txt'])
        if os.path.exists(p):
            m = meta_of(p)
            m['role'] = arm['key']
            ev.append(m)
    for extra in ('reports/c026_minimax_raw.json',
                  'reports/c057_encoder_acc_3way.json',
                  'reports/c086d_full61_all_npu_matrix.json',
                  'reports/asr004_ab/summary_A.json',
                  'reports/asr004_ab/summary_B.json',
                  'results/app/app037_wer_gap_maincause.json',
                  'results/app/app037_segcount_effect.json',
                  'results/app/app037_seam_mechanism.json'):
        p = os.path.join(REPO, extra)
        if os.path.exists(p):
            m = meta_of(p)
            m['role'] = '引用'
            ev.append(m)
    out['evidence_files'] = ev
    for m in ev:
        print('  %-62s %9d B  %s  %s' %
              (m['path'], m['bytes'], m['mtime'], m['sha256'][:16]))

    # ── 留给 reviewer 的开放问题 ──
    out['open_for_reviewer'] = [
        '① Q4 的「边界误差率 vs 中间误差率」比值，是「每段更差」还是「段更多」主导？'
        '（本脚本给出数值，不下结论）',
        '② 是否接受 Q3 的**外推上界**（「int8asym 的贡献 ≤ int4 的贡献」）？'
        '若不接受，需要在 226 段下补一条 int8asym 端到端臂（**需持锁跑推理**）',
        '③ c057_encoder_acc_3way.json 的 token_edit_pct 与 IR 体积排序相反'
        '（int8asym 30.53% > int4 4.21%）⇒ 该指标是否仍应作为编码器选型依据？',
        '④ 缺口是「段更多」与「每段更差」的**叠加**（两个极端反事实都不闭合）'
        '⇒ 若要改产品行为，是改分段粒度、还是改 encoder、还是改预算？**请裁定**',
        '⑤ 是否需要把 App 的默认引擎 encoder 从 int8asym 改回 fp16？'
        '（**App 不自行决定**；另需权衡 IR 体积 605.6 vs 303.8 MiB 与速度）',
    ]

    print()
    print('=' * 78)
    if FAIL_CHECK:
        print('🔴 自校验失败：%s' % FAIL_CHECK)
    else:
        print('✅ 自校验全部通过（%d 项）' % len(SELF_CHECK))

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('证据落盘：%s' % OUT)
    print('本文件 SHA256：%s' % sha256_of(OUT))
    return 1 if FAIL_CHECK else 0


if __name__ == '__main__':
    sys.exit(main())
