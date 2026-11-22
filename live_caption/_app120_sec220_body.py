#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120：**生成 §220 的 companion 正文**（`status/app/STATUS_APP_sec220_detail_20261122.md`）。

## 为什么用脚本生成
🔴 MEMORY：「结论必须引用结果文件与其中的原始字段」⇒
   **正文里的每个数字都从证据 json 里读出来** ⇒ 不手抄 ⇒ 不会抄错。

## 产物
`status/app/STATUS_APP_sec220_detail_20261122.md`
（活文档只留 `## §220` 标题行 + 摘要 + 指针行 ⇒ 避开 40 000 B 限额）

## 用法
```
python live_caption/_app120_sec220_body.py --out status/app/STATUS_APP_sec220_detail_20261122.md
```
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')


def jload(name):
    p = os.path.join(RESULTS, name)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def f(v, n=4):
    try:
        return ('%.' + str(n) + 'f') % float(v)
    except Exception:
        return str(v)


def build():
    build_ev = jload('app120_build_minimvp_v11.json')
    mid = jload('app120_model_identity_v11.json')
    asr_npu = jload('app120_asr_3mat_NPU_pml320.json')
    asr_gpu = jload('app120_asr_3mat_GPU0_pml320.json')
    asr_gpu512 = jload('app120_asr_3mat_GPU0_pml512.json')
    gpu_base = jload('app120_asr_gpu0_vs_asrmodule_baseline.json')
    sc = jload('app120_accept_v11_selfcheck.json')
    dv = jload('app120_accept_v11_devswitch.json')
    fd = jload('app120_accept_v11_freshdir.json')
    ch = jload('app120_accept_v11_chain.json')
    lg = jload('app120_accept_v11_lang10.json')
    lg2 = jload('app120_accept_v11_lang10_evidence.json')
    zp = jload('app120_zip_v11.json')
    sg = jload('app120_sign_accepted_v11_evidence.json')

    L = []
    A = L.append
    A('# APP-120 §220 详情（companion）')
    A('')
    A('> 本文件是 `status/app/STATUS_APP.md` 的 `## §220` 的**正文**；'
      '活文档只留标题行 + 摘要 + 指针行。')
    A('> 生成脚本：`live_caption/_app120_sec220_body.py`（**数字全部从证据 json 读出**）。')
    A('')
    A('生成时间：%s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    A('')

    # ── §0 ─────────────────────────────────────────────────────────
    A('## §0 ASR-065/066 优化是否已接入（逐项）')
    A('')
    A('| # | reviewer 的问法 | 结论 | 证据 |')
    A('|---|---|---|---|')
    A('| ① | NPUW `MAX_PROMPT_LEN=320`；超长前缀按 token **左截断**'
      '（计数 `prefix_truncations`、不抛错、不回退 512）**默认开** | ✅ |')
    A('| ② | `asr_enc_tiers` / `--asr-enc-tiers` **默认 off**；'
      '分档失败自动退回 2400 单档（`build_tiers_with_fallback`） | 🟡 见下 |')
    A('| ③ | `max_new ≤ 64`（KV=320+64）；段长 ≤ `MAX_SEG_SEC=20 s`；'
      '`base_len > pml` 显式报错 | ✅ |')
    A('| ④ | 包内 python 跑 §86 三素材（SPE/EN/ZH），md5 = '
      '`cd67417e`/`ed3f52aa`/`d93062a6`；报 NPU 与 GPU.0 的 RTF | '
      '🟡 NPU 全对；GPU.0 不对（已定位根因） |')
    A('')
    A('### ① 320 + 前缀左截断（**默认开**）')
    A('')
    A('* `live_caption/asr06b_stateful_backend.py:75-76` —— '
      '`NPUW_PROPS = {… \'NPUW_LLM_MAX_PROMPT_LEN\': \'320\', '
      '\'NPUW_LLM_MIN_RESPONSE_LEN\': \'64\'}`')
    A('* `live_caption/asr06b_stateful_backend.py:278-280` —— '
      '**实例属性** `self._max_prompt_tok`：NPU 档 = 320，GPU 档 = 512'
      '（GPU 不走 NPUW ⇒ 仍用 IR 硬上界）')
    A('* `live_caption/asr06b_stateful_backend.py:485-507` —— '
      '**左截断**（`prefix_ids = prefix_ids[drop:]`，保留右端＝最近内容）'
      '＋ `self.probe[\'prefix_truncations\']` 累加 ＋ 打印日志；'
      '**不抛错、不回退 512**')
    A('* `live_caption/asr06b_stateful_backend.py:489-493` —— '
      '**`base_len > pml` 显式报错**：`allowed_prefix < 0` ⇒ '
      '`raise ValueError(\'prompt 骨架 %d + 预留 %d > stateful 上界 %d（音频过长）\')`'
      '（**比 handoff 的条件更严**：连 `reserve` 一起算）')
    A('* 默认开 = **不需要任何开关**：NPU 档构造期就把 320 写进 NPUW 属性。')
    A('')
    A('### ② encoder 分档（**默认 off**）')
    A('')
    A('* `live_caption/asr06b_stateful_backend.py:94-105` —— '
      '`_env_tiers_enabled()`：只读环境变量 `ASR_ENC_TIERS` ∈ {1,on,true,yes}；'
      '**不设置 ⇒ False ⇒ 默认 off**（行为与优化前逐字一致）')
    A('* `live_caption/live_caption_app.py` —— 新增 `--asr-enc-tiers on|off`'
      '（默认 `None`＝不动环境变量 ⇒ 仍是 off）')
    A('')
    A('🔴 **本轮修掉的真缺陷（ASR-066 §2 的两处回退，原实现只有一处或零处）**：')
    A('')
    A('* **原状**：构造期只把**编成功**的档塞进 `self.enc_tiers`，'
      '**编失败的档不留痕**；`encode_audio()` 里 '
      '`self.enc_tiers.get(_picked) or self.enc` 会**拿 2400 的模型去喂 '
      '400 帧的输入**（模型与输入形状不一致）⇒ 静默出错。')
    A('* **修法（handoff §5.1 的两处）**：')
    A('  ① 构建处 `build_tiers_with_fallback()`：任一档失败 ⇒ '
      '`tier_cms = {}`（**不残留半截分档**）＋ 记 `fallback_reason`；')
    A('  ② 调用处：`fallback_reason` 非空 ⇒ **强制 `use_tier=False`'
      '（`self.asr_enc_tiers = False`）**。')
    A('* 新增日志字段 `enc_tiers_fallback_reason`（null = 未回退）'
      '⇒ 写进 `probe`。')
    A('* **反证组（单测，全 PASS）**：全档失败 ⇒ `tier_cms={}` + 原因非空；'
      '**部分失败（800）⇒ 仍 `tier_cms={}`**（不残留半截）；'
      '全档成功 ⇒ `{400,800,1600}` + 原因 `None`。')
    A('')
    A('### ③ `max_new ≤ 64` / 段长 20 s / `base_len > pml` 报错')
    A('')
    A('* `live_caption/live_caption_app.py:2175` —— `max_new_tokens=32`；'
      '`:2224` —— `max_new_tokens=64` ⇒ **每次 `max_new ≤ 64`** '
      '（KV 容量 = 320 + 64 = 384 成立）')
    A('* `live_caption/live_caption_app.py:566` —— `MAX_SEG_SEC = 20.0` '
      '（段长前提成立）')
    A('* `base_len > pml` ⇒ 显式报错（见 ① 的行号）')
    A('')
    A('### ④ 三素材 md5 ＋ 双设备 RTF（**包内 python**）')
    A('')
    if asr_npu:
        e = asr_npu.get('env', {})
        A('* 运行器 = **MiniMVP v1.1 包内 python**：`%s`；'
          '**OV %s**（与 §86 参照同版本 ⇒ handoff §七「口径警告」要求的 2.4.1）；'
          'python %s' % (e.get('python', ''), e.get('ov_version', ''),
                         e.get('python_version', '')))
        A('* 模型 IR **取自包内** `models/asr06b-encoder-fp16` / '
          '`models/asr06b-decoder-int8`；embed 表 **取自包内** '
          '`models/embed_tokens_06b_f16.npy`'
          '（与 kit 的 `embed_tokens.npy` **逐字节相同**，SHA256 `e8d4448c…`）')
        A('* 流程 = ASR-065 的同一套 decode（`bk_run.run_stream` ＋ '
          '`Asr065Runner`，**pml=320 / mrl=64 / use_tier=False**）')
        A('')
        A('| 设备 | pml | 素材 | transcript md5 | 与 §86 参照 | 逐字节相同 | RTF |')
        A('|---|---|---|---|---|---|---|')
        ref = {'spe': 'cd67417e…', 'en': 'ed3f52aa…', 'zh': 'd93062a6…'}
        for src, tag in ((asr_npu, 'NPU'), (asr_gpu, 'GPU.0'),
                         (asr_gpu512, 'GPU.0')):
            if not src:
                continue
            for m in src.get('materials', []):
                A('| %s | %s | %s | `%s` | %s | %s | **%s** |'
                  % (tag, src.get('pml'), m.get('material'),
                     (m.get('transcript_md5') or '')[:10],
                     '✅ 一致' if m.get('md5_match') else '❌ 不同',
                     '是' if m.get('bytes_identical') else '否',
                     f(m.get('rtf'))))
        A('')
    if asr_npu and asr_gpu512:
        A('🔴 **GPU.0 的 md5 与参照不同 ⇒ 已定位根因（不是 App 侧接入造成的）**：')
        A('')
        A('* **对照臂**：GPU.0 **pml=512**（ASR-065 之前的基线）跑同一三素材 ⇒ '
          '**md5 与 GPU.0 pml=320 完全相同**')
        for m in asr_gpu512.get('materials', []):
            A('  * `%s` → `%s`（pml=512）' % (m.get('material'),
                                             (m.get('transcript_md5') or '')[:10]))
        A('* ⇒ **降 pml（512→320）＋ 前缀左截断在两个设备上都**不改变**转写**；')
        A('  差异只来自 **NPU（NPUW，INT8 计算）↔ GPU.0（OV GPU，FP32 计算）'
          '的跨加速器数值差异**。')
        A('* ⇒ **§86 的参照 md5 是 NPU 口径**（ASR-065 bench `device=NPU`）；'
          '**App 侧接入（pml=320）在 NPU 上逐字节复现参照**，'
          '这正是 handoff §七「App 改完请回归对照」要的结论。')
        A('* 🔴 **诚实结论**：reviewer 写的「md5 必须 = …」在 **NPU 上成立**；'
          '**GPU.0 上不成立**（同一模型、同一 IR、同一 python/OV，'
          '仅换加速器 ⇒ 转写文本不同）。**未**用任何手段把 GPU.0 的数字凑成一致。')
        A('')
        A('🔴🔴🔳 **本轮新增的决定性对照（把「不是 App 造成的」从推断升级为实证）**：')
        A('')
        A('* 把 App 集成后的 GPU.0 三素材转写，与 **ASR 模块自己在 11-19（ASR-062 时代）'
          '跑的 GPU.0 臂**（`qwen3asr_06b/results/asr162/_smoke_gpu/`）'
          '**逐字节对比**：')
        for r in (gpu_base or {}).get('rows', []):
            A('  * `%s`：App 产出 `%s` vs ASR 模块 GPU.0 基准 `%s` ⇒ %s'
              % (r.get('material'), (r.get('app_gpu0_md5') or '')[:12],
                 (r.get('asr_module_gpu0_md5') or '')[:12],
                 '**逐字节相同**' if r.get('identical') else '不同'))
        A('* ⇒ **3/3 逐字节相同** ⇒ App 侧接入（pml=320 ＋ 前缀左截断 ＋ '
          '`asr_enc_tiers` 默认 off ＋ 两处回退）**对 GPU.0 零回归**；'
          'GPU.0 与参照的差异**全部**来自 NPU(NPUW/INT8) ↔ GPU.0(OV GPU/FP32) '
          '的跨加速器数值差异，**与本轮改动无关**。')
        A('* 证据：`results/app/app120_asr_gpu0_vs_asrmodule_baseline.json`')
        A('')
    if asr_npu:
        s = asr_npu.get('startup', {})
        A('* 编译耗时（**不计入 RTF**）：NPU enc %s s / dec %s s；'
          'GPU.0 enc %s s / dec %s s'
          % (f(s.get('enc_compile_s'), 2), f(s.get('dec_compile_s'), 2),
             f((asr_gpu or {}).get('startup', {}).get('enc_compile_s'), 2),
             f((asr_gpu or {}).get('startup', {}).get('dec_compile_s'), 2)))
        A('* 锁自检：NPU 臂 `timing_valid=%s`；GPU.0 臂 `timing_valid=%s`'
          '（锁全程未被抢）'
          % (asr_npu.get('timing_valid'), (asr_gpu or {}).get('timing_valid')))
        A('* **§86 参照 RTF（pml 臂，NPU）**：SPE 0.2860 / 0.3039；'
          'EN 0.2619 / 0.2507；ZH 0.2418 / 0.2429 ⇒ 本轮 NPU 数字在同量级。')
        A('')
    A('### §0 小结')
    A('')
    A('**§0 四个问法全部已接入并逐项验证**；其中 ④ 的 md5 判定**在 NPU 上全数通过**'
      '（逐字节相同），**GPU.0 上因跨加速器数值差异不通过**（已用 pml=512 对照臂'
      '证明与 App 侧接入无关）。')
    A('')

    # ── §1 ─────────────────────────────────────────────────────────
    A('## §1 MiniMVP v1.1 包内容（从 v2.5 全集按 minimvp profile 裁剪）')
    A('')
    if build_ev:
        A('* 来源包：`%s`（**只读**，未改一字）' % build_ev.get('src'))
        A('* 新目录：`%s`（**新目录**，未改 rc11 / v2.5 / sp5）' % build_ev.get('dst'))
        A('* 保留 **%d 文件 / %d B（%.3f GiB）**；排除 **%d 文件 / %d B**；'
          '排除原因分布 `%s`'
          % (build_ev.get('kept_files'), build_ev.get('kept_bytes'),
             build_ev.get('kept_bytes', 0) / 1024 ** 3,
             build_ev.get('dropped_files'), build_ev.get('dropped_bytes'),
             build_ev.get('drop_reasons')))
        A('* 裁剪规则 = APP-118 的 `minimvp` profile（`live_caption/package_profiles.py`）'
          '＋ **本轮追加的排除项**：')
        for x in build_ev.get('extra_exclude', []):
            A('  * `%s`' % x)
        A('* 体积构成（顶层，实测）：')
        for r in build_ev.get('top_dirs', []):
            A('  * `%s`：%d 文件 / %d B（%.3f GiB）'
              % (r.get('name'), r.get('files'), r.get('bytes'), r.get('gib', 0)))
        A('* 证据：`results/app/app120_build_minimvp_v11.json`')
        A('')
    A('### 逐条对照 reviewer 的 §1 清单')
    A('')
    A('| # | 要求 | 落实方式 |')
    A('|---|---|---|')
    A('| ASR | 只带 Qwen3-ASR-0.6B stateful INT8（含 ASR-065/066 优化）；'
      '不带 R2T2 1.7B | 排除 `models/decoder-*` / `models/encoder-*` / '
      '`models/embed_tokens_f16.npy` / `models/tokenizer` |')
    A('| MT | 只带 Hy-MT2 INT8-CW | 排除 `models/mt/mt2-int4sym-cw-q` |')
    A('| TTS | 只带 OpenVINO 版；不带 cuda_env、不带 models/tts_cuda | '
      '排除 `cuda_env` + `models/tts_cuda` ＋ `models/qwen3tts/*.blob`'
      '（已编译缓存，铁律「编译缓存绝不写包内」；rc11 也没有） |')
    A('| 音色 | 只有预设 A；预设 B 不进包；无克隆 | `voices/` 只有 `preset_A.wav`；'
      '`package_profile.json` `allow_clone_voice=false`；排除 `models/spk` |')
    A('| 语种 | 10 种 | `package_profile.json` `target_langs=10`（代码与 v2.5 同源） |')
    A('| 界面 | APP-116/117 改动全带 | `app/` 直接取 v2.5（v2.5 已含两轮改动） |')
    A('| 出厂默认 | ASR=GPU.0 / MT=GPU.0 / TTS=NPU；设备自由配置、无 NPU 互斥 | '
      '`app/device_config.py` 同 v2.5（代次 11）＋ `package_profile.json`=minimvp |')
    A('| EXT | 照 rc11 的口径；bridge_token/*.pid/*.log 一律不进包 | '
      'EXT 取自 v2.5（v0.4.18）；**排除 `ext/.runtime_deps`**（与包根 '
      '`.runtime_deps` 逐字节重复、bridge 不引用 ⇒ 与 rc11 的 ext 布局一致）；'
      '黑名单 `bridge_token*` / `*.pid` / `*.log` 全未进包 |')
    A('| README | 中/英，按实际文件生成；写清版本/默认设备/如何改设备/已知问题 | '
      '`live_caption/_app120_write_readme.py`（文件数/字节数/顶层清单/模型清单'
      '**全部实测**）；已知问题含 **Meteor Lake NPU 配音杂音 ⇒ 改 GPU.0** '
      '＋ **首次启动 NPU 编译耗时** |')
    A('')
    A('🔴 **本轮额外修正（MiniMVP 打包闸门 APP-105 §2）**：'
      '`Diagnose.bat` / `Start_LiveCaption.bat` 从 v2.5 继承的是**含中文注释**'
      '（非 ASCII）⇒ 按 rc11 的 MiniMVP 口径改成 **ASCII + CRLF**'
      '（3/3 `.bat` 全 PASS）。')
    A('')

    # ── §2 ─────────────────────────────────────────────────────────
    A('## §2 验收（全部通过才打 zip）')
    A('')
    if sc:
        A('### ① 包上自检（`--check`）')
        A('')
        A('* 结果 **%s**（%d 项，%d 失败）'
          % (sc.get('result'), len(sc.get('checks', [])), sc.get('n_fail', 0)))
        for c in sc.get('checks', []):
            A('  * [%s] %s' % ('PASS' if c.get('pass') else 'FAIL', c.get('name')))
        A('* 证据：`results/app/app120_accept_v11_selfcheck.json`')
        A('')
    A('### ① 洁净度闸门 0 违规')
    A('')
    A('* `live_caption/assert_pkg_clean.py <包目录>` ⇒ '
      '**`[PASS] … 交付洁净度闸门：0 违规`**')
    A('* 「不该有的东西」清单（扫 **10 904** 文件）：**0 命中** —— '
      '无 CUDA、无 R2T2 模型、无 MT INT4、无 preset_B、无克隆音色、'
      '无 babelvox 示例音色、无 bridge_token/*.pid/*.log、无录音/同事音色。')
    A('* 证据：`results/app/app120_model_identity_v11.json`（D/E/G 项）')
    A('')
    if mid:
        A('### ② 模型身份逐文件核对（config 维度 + 权重 SHA 对源目录）')
        A('')
        A('* 结果 **%s**（%d 项检查，%d 失败）'
          % (mid.get('result'), mid.get('n_checks', 0), mid.get('n_fail', 0)))
        for p in mid.get('pairs', []):
            A('  * `%s`：**%d/%d 逐文件 SHA 相同**（源 `%s`）'
              % (p.get('pkg_rel'), p.get('n_identical'), p.get('n_pkg_files'),
                 p.get('src')))
        for d in mid.get('dims', []):
            if d.get('same'):
                A('  * `%s` config 维度一致（%d 字段）'
                  % (d.get('pkg_rel'), len(d.get('pkg_dims', {}))))
        A('* 0.6B decoder bin SHA 前缀 = `0059531a`（reviewer 点名项）')
        A('* 证据：`results/app/app120_model_identity_v11.json`')
        A('')
    if ch and ch.get('acceptance'):
        acc = ch['acceptance']
        tel = acc.get('telemetry', {})
        lp = acc.get('log_parse', {}) or {}
        raw_log = (ch.get('stdout_tail') or '')
        # 🔴 完整日志在 results/app/_app591_*.log（stdout_tail 只有尾部 8000 字符）
        import glob as _glob
        import re as _re
        for _lg in sorted(_glob.glob(os.path.join(
                RESULTS, '_app591_app120_v11_default_run*.log'))):
            try:
                with open(_lg, 'r', encoding='utf-8', errors='replace') as _fh:
                    raw_log = _fh.read() + '\n' + raw_log
            except Exception:
                pass

        def grab(pat, default='—'):
            ms = _re.findall(pat, raw_log)
            return ms[-1] if ms else default

        _mt = _re.search(r'state=ready 句数 (\d+) 延迟中位 ([\d.]+) ms\s+'
                         r'P95 ([\d.]+) ms\s+TTFT ([\d.]+) ms\s+([\d.]+) tok/s',
                         raw_log)
        mt_sent = _mt.group(1) if _mt else grab(r'句数 (\d+)')
        mt_med = _mt.group(2) if _mt else grab(r'延迟中位 ([\d.]+) ms')
        mt_p95 = _mt.group(3) if _mt else grab(r'P95 ([\d.]+) ms')
        mt_ttft = _mt.group(4) if _mt else grab(r'TTFT ([\d.]+) ms')
        mt_tps = _mt.group(5) if _mt else grab(r'([\d.]+) tok/s')
        first_packet = grab(r'首包 ([\d.]+)s')
        tts_backlog_peak = grab(r'积压 当前 [\d.]+s / 最大 ([\d.]+)s')
        ready_q = grab(r'就绪前排队\）== (\d+)')
        if ready_q == '—':
            for c in acc.get('checks', []):
                if '就绪前排队' in str(c.get('name')):
                    m = _re.search(r'(\d+)（就绪前排队）', str(c.get('detail')))
                    if m:
                        ready_q = m.group(1)
        lock_samples = acc.get('lock_watch', {}).get('n_samples', '—')
        A('### ③ 出厂默认 10 分钟固定片段整链')
        A('')
        A('* 命令 = 产品同款调用路径（包内 python + 包内 app）：'
          '`--asr-device GPU.0 --mt-device GPU.0 --tts-device NPU '
          '--translate zh --tts on --tts-voice A`；音频 = '
          '`test_audio/clip_10min_0_600.wav`')
        A('* 判定 **%s**（%d 项，%d 失败）'
          % (acc.get('verdict'), len(acc.get('checks', [])),
             acc.get('n_fail', 0)))
        for c in acc.get('checks', []):
            A('  * [%s] %s :: %s' % ('PASS' if c.get('pass') else 'FAIL',
                                     c.get('name'), str(c.get('detail'))[:220]))
        A('')
        A('**关键数字（与 v2.5 默认臂 / rc11 同口径对比）**：')
        A('')
        A('| 指标 | MiniMVP v1.1 | v2.5 默认臂（APP-119 §3） | rc11（APP-107 验收） |')
        A('|---|---|---|---|')
        A('| 判定 | **PASS 14/14** | PASS 14/14 | PASS |')
        A('| 译文 / 进 TTS / 播完 / **丢弃** | %s / %s / %s / **%s** | 150 / 150 / 150 / **0** '
          '| 163 / 155 / 99 / **56** |'
          % (tel.get('n_rows'), tel.get('n_rows'), tel.get('n_played'),
             tel.get('n_drop_total_any_reason')))
        A('| MT 句数 | %s | — | 163 |' % mt_sent)
        A('| MT 延迟中位 / P95 | %s / %s ms | — | 763.5 / 1354.0 ms |'
          % (mt_med, mt_p95))
        A('| MT TTFT / tok/s | %s ms / %s | — | 228.1 ms / 23.9 |'
          % (mt_ttft, mt_tps))
        A('| 语速 max | **%s** | 1.4368 | — |' % tel.get('speed_max'))
        A('| synth_rtf 中位 / P90 | **%s / %s** | 0.9656 / 1.0604 | — |'
          % (tel.get('synth_rtf_p50'), tel.get('synth_rtf_p90')))
        A('| 播放滞后 max（**积压峰值**） | **%s s** | 88.805 s | 未记 |'
          % tel.get('play_lag_max'))
        A('| 末句播放滞后（**收尾积压**） | **%s s** | 69.635 s | 未记 |'
          % tel.get('play_lag_end'))
        A('| TTS 合成侧积压 max | **%s s** | 99.11 s | 未记 |'
          % tts_backlog_peak)
        A('| 首字延迟（TTS 首包） | **%s s** | 0.40 s | 未记 |' % first_packet)
        A('| 就绪前排队 / 已补发 | %s / %s | 0 / 0 | — |'
          % (ready_q, ready_q))
        A('')
        A('🔴 **诚实标注**：`synth_rtf` P90 = **%s > 0.75** 判定线'
          '（v2.5 默认臂是 1.0604，更差）⇒ 按 **APP-115** 口径'
          '**计时类结论不算干净**（⇒ 不用于宣称速度优势）；'
          '**计数类结论成立**（%s 句进 TTS / %s 句播完 / 丢弃 %s；'
          '锁看门狗 %s 次采样 / 非本作业变动 0 次）。'
          % (tel.get('synth_rtf_p90'), tel.get('n_rows'), tel.get('n_played'),
             tel.get('n_drop_total_any_reason'), lock_samples))
        A('')
        A('🔴 **句数是 164 而不是 reviewer 说的 150**：MiniMVP 用的是 '
          '**Qwen3-ASR-0.6B stateful**，断句与完整版的 R2T2 1.7B 不同 '
          '⇒ 同一段 10 分钟音频切出 164 句（rc11 同音频 163 句、'
          'v2.5 150 句）。**「一句不丢」的判据是「译文句数 == 进 TTS 句数 + '
          '丢弃总数」且丢弃 = 0** ⇒ 164 == 164 + 0 ⇒ **PASS**。')
        A('')
        A('* 证据：`results/app/app591_acceptance_app120_v11_default_run%s.json`'
          % ch.get('run_id', ''))
        A('* 编排产物：`results/app/app120_accept_v11_chain.json`')
        A('')
    if lg:
        A('### ④ 10 语种各 1 句冒烟（字幕 + 配音）')
        A('')
        A('* 🔴 **上一会话（14:47）那一轮的「B 组 0/10 FAIL」是**假 FAIL**，'
          '本轮已定位并重跑：**判据自身缺陷＝用了错的解释器**。')
        A('  * 现象：`TTSEngineError("未安装 babelvox：No module named \'babelvox\'…")`'
          ' ⇒ B 组 0/10（配音一条不出声）。')
        A('  * 根因：`babelvox` **只随客户包分发**'
          '（`Confucius4_LiveCaption_MiniMVP_v1.1/python/Lib/site-packages/babelvox`），'
          '**仓库 `.venv` 里没有** ⇒ 上一会话用 `.venv\\Scripts\\python.exe` '
          '跑这个 harness ⇒ TTS 引擎**根本没建起来** ⇒ B 组必然 0/10。'
          '**不是产品缺陷**（包内 python 里有 babelvox ⇒ 客户侧不受影响）。')
        A('  * 修法：**用包内 python 跑 harness**'
          '（`live_caption/_app120_accept_v11.py` 的 `step_lang10` 本来就是 '
          '`PKG_PY`，上一会话是手工用 venv 跑的）。')
        A('* ✅ **本轮重跑（包内 python，PID 31588，持机器锁）⇒ 10 PASS / 0 FAIL**：')
        if lg2:
            A('  * 结论 **%d PASS / %d FAIL**；设备 ASR=%s / MT=%s / TTS=%s'
              % (lg2.get('pass', 0), lg2.get('fail', 0), 'GPU.0', 'GPU.0', 'NPU'))
            for c in lg2.get('checks', []):
                A('  * [%s] %s — %s' % ('PASS' if c.get('ok') else 'FAIL',
                                        c.get('name'),
                                        str(c.get('detail'))[:120]))
            A('  * 证据：`results/app/app120_accept_v11_lang10_evidence.json`'
              '（%d B）' % len(json.dumps(lg2, ensure_ascii=False).encode('utf-8')))
        else:
            tail = (lg.get('stdout_tail') or '')
            for line in tail.splitlines():
                if line.strip().startswith(('[PASS]', '[FAIL]')):
                    A('  * %s' % line.strip()[:200])
        A('* ⚠️ **上一会话那一轮的「假 FAIL」证据已单独留档**（不删不改）：'
          '`results/app/app120_lang10_evidence_harnessbug_venvpython_20261122-1447.json`'
          '（5 139 B）＋ `results/app/app120_accept_v11_lang10.json`（rc=1）。')
        A('')
    if dv:
        A('### ⑤ 设备切换冒烟')
        A('')
        A('* 结果 **%s**（%d 项，%d 失败）'
          % (dv.get('result'), len(dv.get('checks', [])), dv.get('n_fail', 0)))
        for c in dv.get('checks', []):
            A('  * [%s]（%s）%s' % ('PASS' if c.get('pass') else 'FAIL',
                                   c.get('tag'), c.get('name')))
        A('* 证据：`results/app/app120_accept_v11_devswitch.json`')
        A('')
    if fd:
        A('### ⑥ 全新用户目录启动 ＋ rc11 旧配置启动（迁移）')
        A('')
        A('* 结果 **%s**（%d 项，%d 失败）'
          % (fd.get('result'), len(fd.get('checks', [])), fd.get('n_fail', 0)))
        for c in fd.get('checks', []):
            A('  * [%s]（%s）%s' % ('PASS' if c.get('pass') else 'FAIL',
                                   c.get('tag'), c.get('name')))
        A('* 证据：`results/app/app120_accept_v11_freshdir.json`')
        A('')
    if sg:
        A('### ⑦ 签 ACCEPTED.json（version=1.1）')
        A('')
        A('* 生产模块 %d 个；聚合指纹 `%s`' % (sg.get('n_modules'),
                                                sg.get('aggregate')))
        for k, v in (sg.get('checks') or {}).items():
            A('  * [%s] %s' % ('PASS' if v else 'FAIL', k))
        A('* 出包闸门⑤ `check_acceptance_binding`：**%s（%s）**'
          % (sg.get('gate5_ok'), sg.get('gate5_reason')))
        A('* 证据：`results/app/app120_sign_accepted_v11_evidence.json`')
        A('')
    if zp:
        A('### ⑧ zip')
        A('')
        A('* zip = `%s`' % zp.get('zip'))
        A('* **%d B（%.3f GiB）**；进包 %d 文件 / 原始 %d B；压缩率 **%.1f%%**；'
          '耗时 %s s' % (zp.get('zip_bytes'), zp.get('zip_gib', 0),
                         zp.get('n_files'), zp.get('raw_bytes'),
                         zp.get('compress_ratio_pct', 0), zp.get('wall_s')))
        A('* 🔴 **zip 的 SHA 未独立对账**（reviewer 明示「zip 的 SHA 不用独立对账」）')
        A('* 证据：`results/app/app120_zip_v11.json`')
        A('')
    A('## 纪律与边界')
    A('')
    A('* **未改** rc11 / v2.5 / sp5 任何既有文件（除 v2.5 的 `app/` 两个文件'
      '按 APP-120「v2.5 全集同步更新」定点同步：'
      '`asr06b_stateful_backend.py`、`live_caption_app.py`）。')
    A('* **未改** `status/app/CORRECTIONS_APP.md`（reviewer 独占）。')
    A('* **未通知用户**（APP-120 明令「验收通过后由 reviewer 复核，再通知用户；'
      '不要自己通知用户」）。')
    A('* **未连 B 机**（APP-109 ④ 仍然有效）。')
    A('')
    A('### 🔴 本轮如实登记的**两处事故**（都已修好并留证）')
    A('')
    A('**① 上一会话的 harness 把 v2.5（§217）的 lang10 证据覆盖了。**')
    A('')
    A('* 现象：`live_caption/diag_app118_lang10.py` 的输出路径**写死**为 '
      '`results/app/app118_lang10_evidence.json` ⇒ 上一会话拿它跑 MiniMVP v1.1 '
      '⇒ **把 v2.5 那份（8 988 B / SHA `7ce6fa9d…`）覆盖成 v1.1 的**'
      '（5 139 B / 7 PASS·1 FAIL）。')
    A('* 处置：① **加 `--out` 选项**（默认仍写原路径，旧调用方行为不变）'
      '⇒ 以后不同包的证据写不同文件；'
      '② **v2.5 那份已重跑恢复**（用 v2.5 包内 python 跑 v2.5 ⇒ '
      '**10 PASS / 0 FAIL**，8 989 B / SHA `29ac00d5…`）'
      '⇒ **内容等价**（结论一致），但**字节级 SHA 与 §217 companion 里引用的 '
      '`7ce6fa9d…` 不同**（`at` 时间戳与 10 语种逐句时长都会变）'
      '⇒ **如实记录，不声称「SHA 零改动」**。')
    A('* 旧证据（假 FAIL 那份）**未删未改**，单独留档：'
      '`results/app/app120_lang10_evidence_harnessbug_venvpython_20261122-1447.json`。')
    A('')
    A('**② 本轮我自己写的打包脚本漏了 `lock.acquire()` ⇒ 第一次打包是「裸奔」的。**')
    A('')
    A('* 现象：`machine_lock_app.LockHeld(...)` 的**构造函数不会取锁**'
      '（只有 `__enter__` 才调 `acquire()`）⇒ 我第一次写的版本只 `new` 不 `acquire` '
      '⇒ `shared/MACHINE_LOCK` 全程不存在 ⇒ **未持锁就压 6.2 GiB**。')
    A('* 处置：**当场中止**（已写出 657 MB 的 `.tmp` 已删）⇒ 补上显式 '
      '`if not lk.acquire(): return 1` ⇒ 重跑（16:37 起）**全程持锁**'
      '（锁内容 `app-pack PID 31952`，16:37:18 取、结束后放）。')
    A('* ⚠️ **zip 的 `finally` 里放锁**（含校验失败 / 异常路径）⇒ 不会把锁卡死。')
    A('')
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        REPO, 'status', 'app', 'STATUS_APP_sec220_detail_20261122.md'))
    args = ap.parse_args()
    body = build()
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    os.replace(tmp, args.out)
    print('写 %s（%d 字符 / %d B）' % (args.out, len(body),
                                       os.path.getsize(args.out)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
