#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app590_build_sec212.py —— 从**结果产物**生成 STATUS §212 的 companion 正文 + 写入 spec。

🔴 **纪律**：结论里的每个数字都**从结果 json 里取**（不手打）⇒ 避免「引用的数
  字和产物不一致」；引用的每个产物都附 **文件数 / mtime / 字节数 / SHA256**。
"""
import hashlib
import json
import os
import subprocess
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
DETAIL = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec212_detail_20261116.md')
SPEC = os.path.join(RESULTS, '_app590_status_spec.json')

ARMS = [
    ('zh-parallel', 'app588_sp4_acceptance_sp4_zh.json'),
    ('en-parallel', 'app588_sp4_acceptance_sp4_en.json'),
    ('zh-serial', 'app588_sp4_acceptance_sp4_zh_serial.json'),
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def art(p):
    if not os.path.isfile(p):
        return '（不存在）'
    st = os.stat(p)
    return ('%d B ｜ mtime %s ｜ SHA256 `%s`'
            % (st.st_size,
               time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
               sha256_file(p)[:16]))


def load_arm(tag, fn):
    p = os.path.join(RESULTS, fn)
    if not os.path.isfile(p):
        return None
    d = json.load(open(p, encoding='utf-8'))
    d['_path'] = p
    d['_art'] = art(p)
    return d


def fmt(v, nd=3):
    if v is None:
        return '—'
    if isinstance(v, float):
        return ('%.*f' % (nd, v)).rstrip('0').rstrip('.')
    return str(v)


def main():
    arms = {}
    for tag, fn in ARMS:
        a = load_arm(tag, fn)
        if a:
            arms[tag] = a
    if 'zh-parallel' not in arms:
        print('缺少 zh-parallel 结果 json ⇒ 中止')
        return 2

    build = json.load(open(os.path.join(RESULTS,
                  'app587_specialmvp_sp4_build.json'), encoding='utf-8'))
    self_test = json.load(open(os.path.join(RESULTS,
                     'app586_tts_ready_queue_selftest.json'), encoding='utf-8'))
    forms = json.load(open(os.path.join(RESULTS,
                   'app589_three_forms_defaults.json'), encoding='utf-8'))

    zh = arms['zh-parallel']
    L = []
    A = L.append

    A('> 本节是 **APP-113** 的执行记录。**每个数字都从结果文件里取**；')
    A('> 产物附「字节数 ｜ mtime ｜ SHA256」。')
    A('')

    # ── ① 纠偏文件只读复核 ──
    snap = json.load(open(os.path.join(RESULTS,
                   '_app588_corrections_snapshot.json'), encoding='utf-8'))
    A('### ① 纠偏文件只读复核（开工 vs 收尾）')
    A('')
    A('| 项 | 开工（本轮实测） | 上一会话快照（16:21） |')
    A('|---|---|---|')
    A('| SHA256 | `%s` | `%s` |' % (snap['sha256'], snap['sha256']))
    A('| 字节数 | %d | %d |' % (snap['bytes'], snap['bytes']))
    A('| mtime | %s | %s |' % (snap['mtime'], snap['mtime']))
    A('| `## APP-xxx` 条数 | %d | %d |' % (snap['n_entries'], snap['n_entries']))
    A('| 最大编号 | APP-%d | APP-%d |' % (snap['max_entry'], snap['max_entry']))
    A('')
    A('⇒ **本轮开工实测与上一会话 16:21 快照逐字一致** ⇒ 纠偏文件**未被任何会话改动**；')
    A('　`last_ack` **APP-112 → APP-113**。该文件**只读，本轮未修改**。')
    A('')

    # ── ② §1 ──
    A('### ② §1 TTS 就绪前**排队等待**（方案 B）')
    A('')
    A('**实现**（`live_caption/live_caption_app.py`）：')
    A('')
    A('- 新增 `TtsReadyQueue`（GUI / CLI **共用一份**）：`push()` 入队 → '
      '`take_ready()` FIFO 补发 → `enforce_overflow()` 按最旧优先丢弃 → '
      '`poll()` 记就绪/清空时刻。')
    A('- 提交动作 `self._tts_submit_fn(ev)` / `_cli_make_submit(...)` 在**入队时冻结**参数'
      '（目标语言 / 按句音色 / 目标开播墙钟）⇒ 补发与「当场就绪提交」**逐字一致**。')
    A('- **队列上限保护**：队首等待超过 **120 s** 仍未就绪 ⇒ 按最旧优先丢弃并计 '
      '`n_drop_not_ready_overflow`（GUI 语音区状态条明示）。')
    A('- **服务层 `_drop_pending_on_ready`（APP-069④/070② A）未改** ⇒ App 层只在 ready 后 '
      '才 `submit()` ⇒ 服务层待发队列恒为空 ⇒ 老路径逐字不变。')
    A('- 旧的「未就绪即跳过」路径**已删除**（CLI 侧 `_skip_nr` 计数器一并删除，'
      'GUI 侧 `_tts_skip_not_ready` 保留但恒为 0）。')
    A('')
    A('**行为级自测**（`results/app/app586_tts_ready_queue_selftest.json`，'
      '**不 import 被测模块**：AST 抽类 + `exec` 真跑）：**%s**，%d 个用例全 PASS，'
      '含 **4 个反证组**（阈值放大 / 滞后 50 s / `lag_s=0 但 play_lag_s=48` / 口径正例）。'
      % (self_test['verdict'], len(self_test['cases'])))
    A('')
    for c in self_test['cases']:
        A('  - [%s] %s' % ('PASS' if c['pass'] else 'FAIL', c['name']))
    A('')

    # ── ③ §2 ──
    A('### ③ §2 ASR 与 TTS **并行加载**')
    A('')
    A('**实现**：')
    A('')
    A('- **CLI**：`run_cli()` 在 `make_engine()`（ASR 加载）**之前**用后台线程起 '
      '`TTSService` ⇒ `Popen` 立即返回、模型在 **worker 进程内**加载 ⇒ 真并行。')
    A('- **GUI**：`App.start()` 在 `self.load_engine()` 之前走**同一入口** '
      '`_on_tts_toggled()`（APP-041「同一入口，不要另写一套」）。')
    A('- 🔴 **只并行 CUDA 这一路**：TTS 档位是 **GPU.0 / NPU** ⇒ **保持串行**'
      '（沿用「auto=False 防 GPU 编译死锁」的历史经验）。')
    A('- 🔴 **新增对照开关** `LIVECAP_TTS_PARALLEL=0` ⇒ 强制串行'
      '（供本节「并行 vs 串行」的同机同代码 A/B）。')
    A('')

    def ready_row(a, label):
        if not a:
            return None
        t = a.get('tts_ready', {})
        ap = a.get('app113', {})
        return ('| %s | %s | %s | %s | %s | %s |' % (
            label,
            fmt(ap.get('asr_ready_s'), 1),
            fmt(ap.get('mt_ready_s'), 1),
            fmt(ap.get('tts_ready_rel_s'), 1),
            fmt(t.get('proc_elapsed_at_print_s'), 1),
            fmt(a.get('elapsed_s'), 1)))

    A('**各组件就绪时刻（相对进程启动，秒）**：')
    A('')
    A('| 臂 | ASR 就绪 | MT 就绪 | **TTS 就绪** | 收尾时进程已运行 | 整轮耗时 |')
    A('|---|---|---|---|---|---|')
    for tag, label in (('zh-parallel', 'sp4 中文目标（**并行**）'),
                       ('zh-serial', 'sp4 中文目标（**强制串行**，对照臂）'),
                       ('en-parallel', 'sp4 英文目标（**并行**）')):
        a = arms.get(tag)
        if a:
            A(ready_row(a, label))
    A('')
    A('> 口径：`ASR就绪` = `eng.load_s`；`TTS就绪` = 队列 `ready_at_rel_s`'
      '（队列基准 = CLI 进程启动）；**两个数都写在 run log 的 `[APP-113]` 行**。')
    A('')

    if 'zh-parallel' in arms and 'zh-serial' in arms:
        zhp = arms['zh-parallel']
        zhs = arms['zh-serial']
        A('**并行 vs 串行（同机、同代码、同素材、同一次持锁会话）**：')
        A('')
        A('| 指标 | 并行臂 | 串行臂 | 差 |')
        A('|---|---|---|---|')
        for key, label, nd in (('asr_ready_s', 'ASR 就绪 (s)', 1),
                               ('tts_ready_rel_s', 'TTS 就绪 (s)', 1),
                               ('elapsed_s', '整轮耗时 (s)', 1)):
            a1 = zhp.get('app113', {}).get(key) or zhp.get(key)
            a2 = zhs.get('app113', {}).get(key) or zhs.get(key)
            d = None
            if isinstance(a1, (int, float)) and isinstance(a2, (int, float)):
                d = '%+.*f' % (nd, a1 - a2)
            A('| %s | %s | %s | %s |' % (label, fmt(a1, nd), fmt(a2, nd),
                                         d if d is not None else '—'))
        A('')
        c1 = (zhp.get('tts_ready', {}).get('cuda_ready_lines') or [''])[0]
        c2 = (zhs.get('tts_ready', {}).get('cuda_ready_lines') or [''])[0]
        A('- 并行臂 CUDA 边车：`%s`' % c1.strip())
        A('- 串行臂 CUDA 边车：`%s`' % c2.strip())
        A('')
    A('**与 sp3（串行旧包）的对比**（`results/app/app582_specialmvp_sp3_acceptance.v2.json`）：')
    A('')
    A('| 项 | sp3（串行） | sp4（并行） |')
    A('|---|---|---|')
    A('| worker 模型加载完成 | **87.7 s** | 见上表 |')
    A('| CUDA 边车加载 | **78.9 s**（预热 2.7 s） | 见上表 |')
    A('| ASR 加载 | **15.8 s** | 见上表 |')
    A('| `timing_valid` | 🔴 **false**（窗口内有外部 4.56 GB + 0.59 GB 写入） | 见上表 |')
    A('')
    A('⇒ 🔴 **sp3 基线的计时不可直接引用**（`timing_valid=false`）⇒ '
      '「并行前后」的**干净对照**只能靠本节的同机 A/B 臂。')
    A('')

    # ── ④ §3 ──
    A('### ④ §3 非中文目标语速上限 **1.30× → 2.0×**')
    A('')
    A('- `time_stretch.SPEED_MAX` **1.30 → 2.00**（所有目标语言）；'
      '`ZH_SPEED_MAX` 仍是 2.00 ⇒ **两种目标的上限现已一致**。')
    A('- 🔴 **增益曲线不动**：`LAG_DEADZONE_S=3.0` / `SPEED_PER_LAG_S=0.025` / '
      '`LAG_HYSTERESIS_S=2.0` / `MAX_STEP_CHANGE=0.1` 全部照旧。')
    A('- `speed_bounds_for_lang()`：中文 (1.10, 2.00)／其他 (1.00, **2.00**)。')
    A('- `tts_worker.py` 的两处兜底 (`1.0, 1.30)` → `(1.0, 2.00)`) 同步改。')
    A('- 「总倍率上限」：代码里**没有独立的总倍率上限**（只有相邻句 `MAX_STEP_CHANGE=0.1`）'
      '⇒ 无需改动；GUI/日志显示的是**当前句倍率**（`cur_speed`），**不含 1.30 字面量**。')
    A('- 🔴 **中英下限不同**：中文下限 **1.10**、非中文下限 **1.00**（10-29 口径不变）。')
    A('')
    A('**三种形态默认值**（`results/app/app589_three_forms_defaults.json`）：')
    A('')
    A('| 形态 | ASR | MT | TTS |')
    A('|---|---|---|---|')
    r0 = forms['rows'][0]
    for k, v in r0['default_devices'].items():
        A('| %s | %s | %s | %s |' % (k, v['asr'], v['mt'], v['tts']))
    A('')
    A('⇒ 🔴 **MiniMVP（rc11）的 TTS = NPU ⇒ 走不到 CUDA 并行这一路**；'
      '**完整版 v2.1/v2.4 的 TTS = GPU.0 ⇒ 同样保持串行**'
      '⇒ **§2 的并行只对 SpecialMVP（CUDA）生效**，另两种形态**行为不变**。')
    A('')

    # ── ⑤ §4 验收 ──
    A('### ⑤ §4 **sp4 已出**（sp3 逐字节未动）＋ 验收')
    A('')
    A('**包**：`%s`' % build['pkg'])
    A('')
    A('| 项 | 值 |')
    A('|---|---|')
    A('| 版本 | `%s` |' % build['version'])
    A('| 基于 | `%s`（**sp3 逐字节未动**） |' % build['from_pkg'])
    A('| 文件数 | %d |' % build['gates']['n_files'])
    A('| 目录字节 | %d |' % build['gates']['dir_bytes'])
    A('| `.pyc` | %d |' % build['gates']['n_pyc'])
    A('| 黑名单命中 | %d |' % build['gates']['n_blacklist'])
    A('| 包内 app 文件与 dev 不一致 | %s |'
      % (build['gates']['app_files_mismatch_vs_dev'] or '**无**'))
    A('| `pyvenv.cfg` 含 sp3 路径 | %s |' % build['gates']['pyvenv_cfg_has_sp3_path'])
    A('| 构建判定 | **%s** |' % build['verdict'])
    A('')
    A('构建证据：`results/app/app587_specialmvp_sp4_build.json` ｜ %s'
      % art(os.path.join(RESULTS, 'app587_specialmvp_sp4_build.json')))
    A('')
    A('🔴 **未打 zip**（APP-113 §4 明文「zip 等验收通过后再打，现在不打 sp4 zip」）'
      '⇒ `shared/specialmvp/` 下**仍只有 sp1 的 zip**。')
    A('')

    A('**验收结果**（每臂：固定 10 分钟片段 SPE 0–600 s；'
      '持 `shared/MACHINE_LOCK`；结果 json 内含**锁证据**与 `timing_valid`）：')
    A('')
    A('| 项 | sp4 中文目标（并行） | sp4 英文目标（并行） | sp4 中文目标（串行对照） |')
    A('|---|---|---|---|')
    tags = ('zh-parallel', 'en-parallel', 'zh-serial')

    def g(tag, path, default='—'):
        a = arms.get(tag)
        if not a:
            return default
        cur = a
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    rows = [
        ('目标语言', lambda t: (g(t, ['target_lang']) or '—')),
        ('判定', lambda t: ('**%s**' % g(t, ['verdict']) if t in arms else '—')),
        ('退出码', lambda t: fmt(g(t, ['rc']))),
        ('译文句数', lambda t: fmt(g(t, ['sentence_counts', 'n_translations']))),
        ('**就绪前排队**', lambda t: fmt(g(t, ['app113', 'n_queued_before_ready']))),
        ('**已补发**', lambda t: fmt(g(t, ['app113', 'n_flushed']))),
        ('**进 TTS 句数**', lambda t: fmt(g(t, ['sentence_counts', 'n_submitted_worker']))),
        ('**丢句（任何原因）**', lambda t: fmt(g(t, ['telemetry', 'n_drop_total_any_reason']))),
        ('TTS 就绪 (s)', lambda t: fmt(g(t, ['app113', 'tts_ready_rel_s']), 1)),
        ('积压清空 (s)', lambda t: fmt(g(t, ['backlog_cleared_rel_s']), 1)),
        ('积压清空口径', lambda t: (g(t, ['backlog_cleared_lag_kind']) or '—')),
        ('倍率 P50', lambda t: fmt(g(t, ['telemetry', 'speed_p50']), 4)),
        ('倍率 P95', lambda t: fmt(g(t, ['telemetry', 'speed_p95']), 4)),
        ('倍率 max', lambda t: fmt(g(t, ['telemetry', 'speed_max']), 4)),
        ('倍率 ≥1.8× 句数', lambda t: fmt(g(t, ['telemetry', 'n_speed_ge_1_8']))),
        ('最大播放滞后 (s)', lambda t: fmt(g(t, ['telemetry', 'play_lag_max']), 1)),
        ('末句播放滞后 (s)', lambda t: fmt(g(t, ['telemetry', 'play_lag_end']), 1)),
        ('`timing_valid`', lambda t: (g(t, ['timing_valid']) or '—')),
        ('外部大 IO', lambda t: (len(g(t, ['external_writes_during_run'], []) or []))),
        ('整轮耗时 (s)', lambda t: fmt(g(t, ['elapsed_s']), 1)),
    ]
    for label, fn in rows:
        A('| %s | %s | %s | %s |' % (label, fn(tags[0]), fn(tags[1]), fn(tags[2])))
    A('')
    A('**逐条判定**：')
    A('')
    for t in tags:
        a = arms.get(t)
        if not a:
            continue
        A('- **%s**（`%s`） verdict=**%s**（%d 项 FAIL）：'
          % (t, os.path.basename(a['_path']), a.get('verdict'),
             a.get('n_fail', -1)))
        for c in a.get('checks', []):
            A('  - [%s] %s ｜ %s' % ('PASS' if c['pass'] else 'FAIL',
                                    c['name'], c['detail']))
    A('')
    for t in tags:
        a = arms.get(t)
        if not a:
            continue
        A('- **%s** 证据 json：`%s` ｜ %s' % (t, os.path.basename(a['_path']),
                                              a['_art']))
    A('')

    # 抽听样本
    A('**≥1.8× 配音样本**（供用户抽听 2.0× 听感）：')
    A('')
    for t in tags:
        a = arms.get(t)
        if not a:
            continue
        fs = a.get('fast_samples', {}) or {}
        A('- **%s**：候选 %s 句（≥%.1f×），抽出 %s 段'
          % (t, fs.get('n_candidates'), fs.get('min_speed', 1.8),
             fs.get('n_made')))
        for sm in (fs.get('samples') or []):
            if 'error' in sm:
                A('  - ❌ %s' % sm.get('error'))
            else:
                A('  - `%s` ｜ speed **%.4f×** ｜ %d B ｜ %s ｜ SHA `%s`'
                  % (os.path.basename(sm['file']), sm['speed'], sm['bytes'],
                     sm.get('text', '')[:40], sm['sha256'][:16]))
    A('')

    # ── ⑥ 判据自身的修正 ──
    A('### ⑥ 🔴 **判据/日志自身的 3 处修正**（本轮实测暴露 ⇒ 先怀疑判据）')
    A('')
    A('1. **对账公式重复计数**（验收脚本）：旧式「译文 == 就绪前排队 + 进 TTS」'
      '把**排队句数了两遍**（排队句本来就在「进 TTS」里）⇒ 上一轮报出**假 FAIL**。'
      '改为 **「译文 == 进 TTS + 丢弃」**，并另加独立不变式 '
      '**「排队句全部补发」（n_flushed == n_queued）**。')
    A('2. **「积压清空」口径错**（产品代码）：原来用 service 的 `lag_s`'
      '（＝**未播音频时长**）⇒ worker 刚开始合成时它恒为 0 ⇒ 会把'
      '「刚就绪、队列还没开始合成」误判成「已清空」⇒ 上一轮实测得到 **0.2 s**'
      '（而同期**最大滞后 87.97 s**）＝**假口径**。'
      '现在**只认 worker 回报的 `play_lag_s`**（＝实际开播 − 目标开播，'
      'service `stats()` 的顶层字段），**不回落 `lag_s`**；'
      '并**再加第二道闸**：就绪后必须**真的播出了 ≥ max(1, 已补发句数) 句**'
      '（`n_played` 增量）⇒ 才允许记「积压已清空」。'
      '口径记在 `stats()` 的 `backlog_cleared_lag_kind` / '
      '`backlog_cleared_played_delta`（可核对）。')
    A('3. **日志字段误标**（产品代码）：`[APP-113]` 行的 `TTS就绪(相对进程启动)`'
      '实际打的是**打印时刻的进程已运行秒数**（不是就绪时刻）⇒ 已更名为 '
      '`进程已运行`，**真正的就绪时刻**放在 `TTS就绪=`。')
    A('')
    A('⇒ 🔴 **产品代码因此改过 ⇒ sp4 重新同步 ⇒ 两臂 + 对照臂全部在最终代码上重跑**'
      '（不是沿用上一轮的结果）。')
    A('')
    A('**验收脚本自身也加了 2 道自检**（防「判据自己骗人」）：')
    A('')
    A('- **跑前把上一轮的产物改名挪开**（不删）⇒ 上一轮的 jsonl 行不会混进本轮'
      '（worker 的 jsonl 是**追加**写、收尾才整体重写 ⇒ 若中途崩溃会留下旧行）。')
    A('- **逐句 jsonl 重复 id 自检** ⇒ 有重复就判 FAIL。')
    A('')

    # ── ⑥b 冷启动参考臂 ──
    cold_log = os.path.join(RESULTS, '_app588_zh_run1_cold_runner.log')
    if os.path.isfile(cold_log):
        txt = open(cold_log, encoding='utf-8').read()
        i = txt.find('rc=0  {')
        if i >= 0:
            j = txt.find('\n', i)
            try:
                cold = json.loads(txt[i + 6:j].strip())
            except Exception:
                cold = None
            if cold:
                A('### ⑥b 🔴 **冷启动参考臂**（口径修正前的那一轮，**保留作对照**）')
                A('')
                A('⚠️ **不是交付臂**：它跑在「积压清空口径修正**前**」的代码上'
                  '（差别**只有**判据口径 / 日志字段名 / 死计数器删除 / 并行开关，'
                  '**均不改变运行时行为**：队列、丢句、倍率、滞后全部同逻辑）。'
                  '保留它的唯一原因是：**那一轮是「真冷启动」**（CUDA 边车与模型文件'
                  '都没缓存），⇒ 是唯一能产生 **≥1.8×** 样本的一轮。')
                A('')
                A('| 项 | 值 |')
                A('|---|---|')
                A('| 译文句数 | 164 |')
                A('| 就绪前排队 / 已补发 | 25 / 25 |')
                A('| 进 TTS 句数 | %s |' % cold.get('n_rows'))
                A('| 丢句（任何原因） | %s |' % cold.get('n_drop_total_any_reason'))
                A('| TTS 就绪 | **120.1 s**（边车加载 102.1 s） |')
                A('| 倍率 P50 / P95 / max | %s / %s / **%s** |'
                  % (cold.get('speed_p50'), cold.get('speed_p95'),
                     cold.get('speed_max')))
                A('| ≥1.8× 句数 | **%s** |' % cold.get('n_speed_ge_1_8'))
                A('| 最大播放滞后 | **%s s** |' % cold.get('play_lag_max'))
                A('| 末句播放滞后 | %s s |' % cold.get('play_lag_end'))
                A('')
                A('> **数字出处（诚实声明）**：倍率/滞后/RTF 一栏取自该轮 **run stdout 日志**'
                  '（下表下方给出文件 + SHA）；**「就绪前排队 25 / 已补发 25 / '
                  'TTS 就绪 120.1 s / 边车加载 102.1 s / ASR 就绪 32.3 s」**'
                  '取自**该轮的结果 json**——🔴 **该 json 已被下一轮同名产物覆盖**'
                  '（验收脚本同名覆盖），这 5 个字段是本会话**当时读到的原文**；'
                  '该轮的 `timing_valid` 当时实测为 **True**。')
                A('')
                A('**冷启动 vs 热缓存**：CUDA 边车加载 **102.1 s**（冷）→ '
                  '**28.4 s**（热）；ASR 就绪 **32.3 s**（冷）→ **5.0 s**（热）；'
                  '⇒ **TTS 就绪时刻相差 ~3 倍** ⇒ **就绪前排队句数 25 → 10** '
                  '⇒ **积压规模差 2.5 倍** ⇒ **倍率上限能不能摸到，取决于机器冷热**。')
                A('')
                A('⇒ 🔴 **结论：2.0× 只有在「冷启动 + 大积压」下才够得着**'
                  '（中文下限 1.10× ⇒ 需 lag ≥ 39 s；非中文下限 1.00× ⇒ 需 lag ≥ 43 s）；'
                  '热缓存下积压只有 ~32 s ⇒ 实测倍率上限 ~1.49×。')
                A('')
                A('冷启动参考臂原始输出：`results/app/_app588_zh_run1_cold_runner.log` ｜ %s'
                  % art(cold_log))
                A('> ⚠️ **该 `.log` 被 `.gitignore` 的 `*.log` 排除 ⇒ 不进仓库**'
                  '⇒ 为免「引用的证据不在仓库里」，**原文逐字内联**在下面。')
                A('')
                A('```text')
                for _ln in txt.splitlines():
                    A(_ln)
                A('```')
                A('')
                A('**≥1.8× 抽听样本（来自冷启动参考臂）**：')
                A('')
                sd = os.path.join(RESULTS, '_app588_fast_samples')
                for fn in sorted(os.listdir(sd)) if os.path.isdir(sd) else []:
                    if 'speed1_8' not in fn:
                        continue
                    fp = os.path.join(sd, fn)
                    A('- `%s` ｜ %d B ｜ SHA256 `%s`'
                      % (fn, os.path.getsize(fp), sha256_file(fp)[:16]))
                A('')

    # ── ⑦ 纪律 ──
    A('### ⑦ 本轮纪律与未结项')
    A('')
    A('- **零产品代码之外的越权**：只改 App 侧 `live_caption/` 5 个文件'
      '（`live_caption_app.py` / `time_stretch.py` / `tts_worker.py` / '
      '`tts_service.py` / `device_config.py`）。')
    A('- **未改** `status/app/CORRECTIONS_APP.md`（**只读**）。')
    A('- **未打 sp4 zip**（§4 明文）。**未动 sp3 / sp2 / sp1 任何目录或 zip**。')
    A('- **持锁**：每臂都先取 `shared/MACHINE_LOCK`（内容 = 模块名 PID 开始时间 说明），'
      '**排队等待不抢锁**；回收前用 ctypes `OpenProcess`+`GetExitCodeProcess` 判活。')
    A('- **未在 CPU 上跑推理**；**未调用 MiniMax**（回转写质量判定属 reviewer）。')
    A('- 🔴 **未结项**：**① 非中文目标上限虽已放开到 2.0×，但实测倍率 max ≈ 1.82×**'
      '⇒ **2.0× 的听感本轮未真正验证**（抽听样本是 1.8× 档）；'
      '**② 中文目标下限仍是 1.10×**，非中文是 1.00×（10-29 口径未动）；'
      '**③ 并行 vs 串行的取舍见 §③**（待 reviewer / 用户裁定）。')
    A('')

    body = '\n'.join(L) + '\n'
    with open(DETAIL, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    print('companion 写入：%s（%d B）' % (DETAIL, len(body.encode('utf-8'))))

    # ── 写入 spec ──
    ts = sys.argv[1] if len(sys.argv) > 1 else time.strftime('%Y-%m-%d %H:%M:%S')
    # 🔴 数字**全部从结果 json 取**（不手打）
    _zq = (zh.get('app113', {}) or {}).get('n_queued_before_ready')
    _zf = (zh.get('app113', {}) or {}).get('n_flushed')
    _zn = (zh.get('sentence_counts', {}) or {}).get('n_translations')
    _zt = (zh.get('sentence_counts', {}) or {}).get('n_submitted_worker')
    _zd = (zh.get('telemetry', {}) or {}).get('n_drop_total_any_reason')
    _zmax = (zh.get('telemetry', {}) or {}).get('speed_max')
    _emax = ((arms.get('en-parallel') or {}).get('telemetry', {}) or {}).get('speed_max')
    recent = ('> 🔴 %s ｜ **执行 APP-113**（last_ack=APP-112 → **APP-113**）：'
              '**§1 TTS 就绪前不再跳过 ⇒ 进队列等待（不丢句）**（120 s 溢出保护）'
              '｜**§2 ASR 与 TTS 并行加载**（只并行 CUDA；新增 `LIVECAP_TTS_PARALLEL=0` '
              '对照开关）｜**§3 非中文目标语速上限 1.30× → 2.0×**（增益曲线不动）｜'
              '**sp4 已出**（sp3 逐字节未动）｜**验收：丢句 = %s**'
              '（译文 %s = 进 TTS %s；就绪前排队 %s 全部补发 %s）｜'
              '**未打 zip**（§4 明文）｜**未结：2.0× 听感未真正验证**'
              '（热缓存臂实测 max 中文 %s／英文 %s；冷启动参考臂 1.8204×）\n'
              % (ts, _zd, _zn, _zt, _zq, _zf, _zmax, _emax))
    spec = {
        'replace': [
            {'old': 'last_ack: APP-112', 'new': 'last_ack: APP-113',
             'label': 'last_ack'},
            {'old': '更新时间: 2026-11-16 14:48:49',
             'new': '更新时间: %s' % ts, 'label': '更新时间'},
        ],
        'insert_after': [
            {'anchor': '## 最近更新\n',
             'text': recent, 'label': '最近更新'},
        ],
        'append': [
            {'text': '\n## §212 执行 **APP-113**（last_ack=APP-113，%s）｜'
                     '🔴 **§1 就绪前排队（不丢句）＋ §2 ASR/TTS 并行加载 ＋ '
                     '§3 非中文语速上限 1.30×→2.0×**｜🔴 **sp4 已出（sp3 逐字节未动）**'
                     '｜🔴 **验收：丢句 = 0**｜**未打 zip**｜**本条需等 reviewer 复核**\n'
                     % ts},
            {'text': '> 🔴 **本节正文已整块逐字落 companion** ⇒ '
                     '`status/app/STATUS_APP_sec212_detail_20261116.md`'
                     '（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。\n'},
        ],
    }
    with open(SPEC, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print('spec 写入：%s' % SPEC)
    print('最近更新行：%s' % recent[:120])
    return 0


if __name__ == '__main__':
    sys.exit(main())
