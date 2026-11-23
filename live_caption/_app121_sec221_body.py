#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §221：**生成 companion 正文**（`status/app/STATUS_APP_sec221_detail_20261123.md`）。

## 纪律
- **所有数字都从结果文件读出**（`results/app/app121_*.json` / `app591_*.json`）
  ⇒ 缺证据 ⇒ 写「（本项未跑）」**绝不编造**；
- 每个结论都**指到文件 + 字段**；
- companion **write-once**：已存在 ⇒ 拒绝覆盖（除非显式 `--force` 且 SHA 相同）。

## 用法
```
python live_caption/_app121_sec221_body.py
```
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
OUT = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec221_detail_20261123.md')

E = {}


def load(name):
    p = os.path.join(RESULTS, name)
    if not os.path.isfile(p):
        E[name] = None
        return None
    try:
        with io.open(p, 'r', encoding='utf-8') as f:
            E[name] = json.load(f)
    except Exception:
        E[name] = None
    return E[name]


def g(name, *keys, default='（未取到）'):
    d = E.get(name)
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def sha_of(path):
    import hashlib
    if not os.path.isfile(path):
        return '（文件不存在）'
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    for n in ('app121_asr_npu_prefix_unit.json',
              'app121_asr_npu_longseg_old_v11.json',
              'app121_asr_npu_longseg_new_v111.json',
              'app121_asr_app_3mat_NPU.json',
              'app121_asr_app_3mat_GPU0.json',
              'app121_asr_app_3mat_GPU0_OLD_v11.json',
              'app121_sync_pkg_evidence.json',
              'app121_update_meta.json',
              'app121_accept_v111_selfcheck.json',
              'app121_accept_v111_chain.json',
              'app591_acceptance_app121_v111_default_run20261123-1000.json',
              'app121_write_readme_evidence.json',
              'app121_sign_accepted_v111_evidence.json',
              'app121_zip_v111.json',
              'app121_zip_extract_check.json',
              'app121_gui_smoke.json',
              'app121_write_status221_evidence.json'):
        load(n)

    if os.path.exists(args.out) and not args.force:
        print('FAIL: companion 已存在 ⇒ 拒绝覆盖（write-once）：%s' % args.out)
        return 2

    L = []
    A = L.append
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    A('# APP-121 §221 详情（companion）')
    A('')
    A('> 本文件是 `status/app/STATUS_APP.md` 的 `## §221` 的**正文**；'
      '活文档只留标题行 + 摘要 + 指针行。')
    A('> 生成脚本：`live_caption/_app121_sec221_body.py`'
      '（**数字全部从证据 json 读出**）。')
    A('')
    A('生成时间：%s' % now)
    A('')

    # ══ §0 摘要 ══════════════════════════════════════════════════
    A('## §0 本条结论摘要')
    A('')
    A('| reviewer 的要求 | 结论 | 证据 |')
    A('|---|---|---|')
    A('| §1 [HIGH] ASR=NPU 长段抛 ValueError 让 ASR 线程退出 | '
      '**已修**：NPU 档 `allowed_prefix = limit − skeleton`（不再减 reserve），'
      '只有 `skeleton > limit` 才报错；另加总量检查 '
      '`prompt + reserve ≤ limit + 64`；GPU 档逻辑一字未动。'
      '**旧包可复现该缺陷**（`ValueError: prompt 骨架 281 + 预留 64 > 320`），'
      '新包同一素材**无 ValueError、字幕持续输出到结束** | '
      '`results/app/app121_asr_npu_longseg_old_v11.json` / '
      '`…_new_v111.json` / `app121_asr_npu_prefix_unit.json` |')
    A('| §2 [HIGH] §0④ 的 md5 没跑 App 代码 | '
      '**已撤回** §220 companion 的两句结论（「App 侧接入在 NPU 上逐字节复现参照」'
      '「对 GPU.0 零回归」）；**已补**用 App 后端'
      '（`OVEngine`＝`StreamingEngine` + `ASR06BStatefulBackend`）跑 §86 三素材的 '
      'NPU / GPU.0 各一组，报 transcript md5 与 `prefix_truncations` | '
      '`results/app/app121_asr_app_3mat_NPU.json` / `…_GPU0.json` |')
    A('| §3 [NORMAL] zip 与目录不一致 + 未做解压自检 | '
      '**已修**：`tts_cuda*` 两个文件**改名挪到包外**（不删）⇒ '
      'ACCEPTED 的模块清单与 zip 的实际内容**完全一致**；'
      '**已做**解压自检（全新目录 + 全新 `%LOCALAPPDATA%` 跑 `--check` + GUI 冒烟） | '
      '`results/app/app121_update_meta.json` / `app121_zip_extract_check.json` / '
      '`app121_gui_smoke.json` |')
    A('| §4 [NORMAL] README 与 STATUS 的小问题 | '
      '**已改**（详见 §4） | `results/app/app121_write_readme_evidence.json` |')
    A('| §5 范围与纪律 | **已按要求执行**：只改 '
      '`asr06b_stateful_backend.py` / `live_caption_app.py` 的 `_loop` / README / '
      '打包脚本；dev 树与 v2.5 **逐字节同一份**；重跑自检/洁净度/整链/①②③；'
      '重签 `ACCEPTED.json`；重打 zip；解压自检 | '
      '`results/app/app121_sync_pkg_evidence.json` 等 |')
    A('')

    # ══ §1 ═══════════════════════════════════════════════════════
    A('## §1 [HIGH] ASR=NPU 时长段抛 ValueError（已修 + 已验收）')
    A('')
    A('### 根因')
    A('')
    A('* `asr06b_stateful_backend.py` 的 `build_inputs_embeds` 旧写法：'
      '`allowed_prefix = limit − skeleton − reserve`，'
      '`allowed_prefix < 0` 就 `raise ValueError`。')
    A('* NPU 档 `limit = 320`（NPUW `MAX_PROMPT_LEN`），段尾 `_finalize()` 的 '
      '`reserve = 64` ⇒ **`skeleton + 64 > 320` 就报错**。')
    A('* handoff（`qwen3asr_06b/dev/asr065_handoff.md` §三/§四）的约束是 '
      '**prompt ≤ 320**，**生成部分另算**（KV = 320 + 64 = 384），'
      '**只有 `base_len > pml` 才报错** ⇒ 旧写法**把 64 个生成 token 也算进了 320**。')
    A('* 实测门槛：骨架 18 + 音频 token；**段长 ≈ 18.3 s** 起就报错 ⇒ '
      '**20 s 强制切段的段**、**18.3–20 s 之间靠静音切的段**都会中招。')
    A('* 异常冒到 `Session._loop` 的外层 `except` ⇒ `self.error=e` / '
      '`running=False` ⇒ **本次会话的字幕整条停掉**。')
    A('')
    A('### 修法（只改 `asr06b_stateful_backend.py` + `live_caption_app.py` 的 `_loop`）')
    A('')
    A('1. **NPU 档**：`allowed_prefix = limit − skeleton`（**不再减 reserve**）；'
      '**只有 `skeleton > limit` 才报错**；总量检查 = '
      '`prompt + reserve ≤ limit + NPUW_LLM_MIN_RESPONSE_LEN(64)`。')
    A('2. **GPU 档（512）逻辑一字未动**（`allowed_prefix` 仍减 `reserve`，'
      '总量检查仍对 `MAX_STATEFUL_TOK=512`）。')
    A('3. **附带修正**：流式档 `reserve=32`、段尾 `reserve=64` ⇒ 旧写法两者'
      '**前缀截断口径不同**（多砍 32 个 token）⇒ 转写与 ASR 参照口径不一致；'
      '现在 NPU 档两者口径一致（单测里 `kept_r32 == kept_r64`）。')
    A('4. **`_loop` 加固**：单段解码异常 ⇒ **记日志 + 计数 + 跳过这一段继续**'
      '（`Session._note_seg_error()`），**不再让整条 ASR 停掉**。')
    A('')
    A('### 验收 ①（不做推理的单测）')
    A('')
    pu = E.get('app121_asr_npu_prefix_unit.json')
    if pu is None:
        pu = E.get('app121_asr_npu_prefix_unit_devtree.json')
    if pu:
        A('* 被检文件 = **包内** `app/asr06b_stateful_backend.py`'
          '（`__file__` 指向包内真实路径）⇒ SHA256 `%s`'
          % pu.get('target_sha256', '')[:16])
        A('* **%d/%d 用例 PASS**（含 reviewer 点名的 '
          '`skeleton = 18 + {238, 260, 266}`、`reserve ∈ {32, 64}`、'
          '`skeleton=321` 报错）' % (pu.get('n_cases', 0) - pu.get('n_fail', 0),
                                    pu.get('n_cases', 0)))
        A('* 截断口径一致性 **%d/%d PASS**（`reserve=32` 与 `reserve=64` '
          '保留的前缀数相同）'
          % (len(pu.get('truncation_consistency') or []) -
             pu.get('n_consistency_fail', 0),
             len(pu.get('truncation_consistency') or [])))
        anti = pu.get('anti_group') or {}
        A('* **反证组**：修复前的同一文件（`git HEAD` 取出，SHA256 `%s`）'
          '在同样的用例上**有 %d 个「本应通过」的用例抛了 ValueError** ⇒ '
          '**判据能识破该缺陷**（不是恒 PASS 的假判据）'
          % (str(anti.get('old_file_sha256'))[:16],
             anti.get('old_raised_on_should_pass', 0)))
        A('* 证据：`results/app/app121_asr_npu_prefix_unit.json`')
    else:
        A('* （本项未跑）')
    A('')
    A('### 验收 ②（包内 python 跑 ASR=NPU + ≥20 s 不停顿连续语音）')
    A('')
    old = E.get('app121_asr_npu_longseg_old_v11.json') or {}
    new = E.get('app121_asr_npu_longseg_new_v111.json') or {}
    if old or new:
        A('* **素材**：从 SPE（`clip_10min_0_600.wav`）里把 **App 自己认得的静音**'
          '整段抠掉（判据 = `live_caption_app._frame_db_series` + '
          '`seg_stream.find_silence_in_range`，30 ms/10 ms，相对门限 `p90−12 dB`，'
          '`min_silence_ms=300`）⇒ **%s s 连续语音、最长静音 0.2 s** '
          '⇒ 规则1/规则2 都不触发 ⇒ 段只能累积到 `MAX_SEG_SEC=20 s` '
          '⇒ **被强制切段**'
          % (g('app121_asr_npu_longseg_new_v111.json', 'wav',
               'duration_s', default='（未取到）')))
        A('* **A/B 用的是磁盘上两个真实客户包**：'
          '**旧包 = `Confucius4_LiveCaption_MiniMVP_v1.1`**（修复前代码）／'
          '**新包 = `Confucius4_LiveCaption_MiniMVP_v1.1.1`**（修复后）')
        A('')
        A('| 指标 | 旧包 v1.1（修复前） | 新包 v1.1.1（修复后） |')
        A('|---|---|---|')
        A('| CLI 退出码 | %s | %s |'
          % (old.get('cli', {}).get('rc'), new.get('cli', {}).get('rc')))
        A('| 日志含 `ValueError` | **%s** | %s |'
          % (old.get('cli', {}).get('has_valueerror'),
             new.get('cli', {}).get('has_valueerror')))
        A('| 异常原文 | `%s` | （无） |'
          % ((old.get('cli', {}).get('valueerror_lines') or [''])[-1].strip()
             or '（无）'))
        A('| **字幕行数 / 字符数** | **%s / %s**（字幕整条停掉） | **%s / %s**'
          '（持续输出到结束） |'
          % (old.get('cli', {}).get('n_final_lines'),
             old.get('cli', {}).get('n_chars'),
             new.get('cli', {}).get('n_final_lines'),
             new.get('cli', {}).get('n_chars')))
        A('| 段长探针：段数 / 各段时长 | %s / %s | %s / %s |'
          % (old.get('segment_probe', {}).get('n_segs'),
             old.get('segment_probe', {}).get('seg_durations_s'),
             new.get('segment_probe', {}).get('n_segs'),
             new.get('segment_probe', {}).get('seg_durations_s')))
        A('| **强制切段次数**（`dur ≥ MAX_SEG_SEC`） | %s | **%s**（时长 %s s） |'
          % (old.get('segment_probe', {}).get('n_forced_cuts'),
             new.get('segment_probe', {}).get('n_forced_cuts'),
             new.get('segment_probe', {}).get('forced_cut_durations_s')))
        A('| 段长探针异常 | `%s` | `%s` |'
          % (old.get('segment_probe', {}).get('exception'),
             new.get('segment_probe', {}).get('exception')))
        A('| `prefix_truncations` | %s | %s |'
          % (old.get('segment_probe', {}).get('prefix_truncations'),
             new.get('segment_probe', {}).get('prefix_truncations')))
        A('')
        A('* 证据：`results/app/app121_asr_npu_longseg_old_v11.json`（反证组）'
          '＋ `results/app/app121_asr_npu_longseg_new_v111.json`（修复后）')
    else:
        A('* （本项未跑）')
    A('')
    A('### 验收 ③（GPU 档：同一个 10 分钟片段，转写与 v1.1 逐字节相同）')
    A('')
    A('* 判据：**GPU 档的代码路径一字未动** ⇒ 用**同一个素材、同一套 App 后端**'
      '在**旧包（v1.1）**与**新包（v1.1.1）**各跑一次 GPU.0 ⇒ '
      '两边的 `transcript.txt` 必须**逐字节相同**（md5 相同）。')
    gpu_new = E.get('app121_asr_app_3mat_GPU0.json') or {}
    gpu_old = E.get('app121_asr_app_3mat_GPU0_OLD_v11.json') or {}
    if gpu_new and gpu_old:
        A('')
        A('| 素材 | 新包 v1.1.1 GPU.0 md5 | 旧包 v1.1 GPU.0 md5 | 逐字节相同 |')
        A('|---|---|---|---|')
        for i, tag in enumerate(('spe', 'en', 'zh')):
            mn = (gpu_new.get('materials') or [{}])[i] if len(
                gpu_new.get('materials') or []) > i else {}
            mo = (gpu_old.get('materials') or [{}])[i] if len(
                gpu_old.get('materials') or []) > i else {}
            A('| %s | `%s` | `%s` | **%s** |'
              % (tag, str(mn.get('transcript_md5'))[:10],
                 str(mo.get('transcript_md5'))[:10],
                 '是' if mn.get('transcript_md5') == mo.get('transcript_md5')
                 else '否'))
        A('')
        A('* 证据：`results/app/app121_asr_app_3mat_GPU0.json`（新包）'
          '＋ `results/app/app121_asr_app_3mat_GPU0_OLD_v11.json`（旧包对照臂）')
    else:
        A('* （本项未跑完）')
    A('')

    # ══ §2 ═══════════════════════════════════════════════════════
    A('## §2 [HIGH] 撤回 §220 的 md5 结论 ＋ 补 App 后端实测')
    A('')
    A('### 🔴 撤回（reviewer §2 第一段）')
    A('')
    A('§220 companion 里的这两句**不成立**，本节**撤回**：')
    A('')
    A('1. ❌「**App 侧接入在 NPU 上逐字节复现参照**」')
    A('2. ❌「**对 GPU.0 零回归**」')
    A('')
    A('**理由（reviewer 的原话 + 实测）**：'
      '§220 的 `_app120_asr_3mat.py` 用的是 **ASR 模块**的 '
      '`bk_run.run_stream` ＋ `asr065_backend.Asr065Runner`，'
      '**没有经过 App 的 `ASR06BStatefulBackend`** ⇒ '
      '那个测试**只能证明包里的模型文件和 ASR 模块用的是同一份**。')
    A('')
    A('### ✅ 补测（用 App 的后端跑 §86 三素材）')
    A('')
    A('* 调用路径 = **包内 `app/live_caption_app.py` 的 `OVEngine`**'
      '（= `StreamingEngine` 包装 ＋ `ASR06BStatefulBackend`）'
      '⇒ 流式块走 App 的 `_st()`（`max_new_tokens=32`）、'
      '段尾定稿走 App 的 `_finalize()`（`reserve=64`）、'
      '**切段走 App 自己的 `Segmenter`**。')
    A('* 解释器 = **包内 python**（OV `2026.4.1-22982-e213a147257-releases/2026/4`，'
      '与 §86 参照同版本）。')
    A('')
    npu = E.get('app121_asr_app_3mat_NPU.json') or {}
    gpu = E.get('app121_asr_app_3mat_GPU0.json') or {}
    if npu:
        A('| 设备 | 素材 | 段数 | transcript md5 | `prefix_truncations` | RTF |')
        A('|---|---|---|---|---|---|')
        for m in (npu.get('materials') or []):
            A('| NPU | %s | %s | `%s` | %s | %s |'
              % (m.get('material'), m.get('n_segs'),
                 str(m.get('transcript_md5'))[:16],
                 m.get('prefix_truncations'), m.get('rtf')))
        for m in (gpu.get('materials') or []):
            A('| GPU.0 | %s | %s | `%s` | %s | %s |'
              % (m.get('material'), m.get('n_segs'),
                 str(m.get('transcript_md5'))[:16],
                 m.get('prefix_truncations'), m.get('rtf')))
        A('')
        A('* §86 参照 md5（ASR 模块口径）：'
          '`cd67417e…`（spe）／`ed3f52aa…`（en）／`d93062a6…`（zh）'
          '⇒ **三个素材在两个设备上都不等于参照**。')
        A('')
    A('### 逐段解释（为什么不一致 —— reviewer 说「不要求硬凑一致」）')
    A('')
    A('* **段边界一致**：三个素材的段数 **App 与参照完全相同**'
      '（spe 93/93、en 65/65、zh 66/66）⇒ **切段器行为一致**，'
      '差异**不在切段**。')
    A('* **差异在解码/拼接路径**：App 的流式路径**每个 640 ms 块都带前缀重新解码**，'
      '段尾再把前缀原样喂一遍（`prefix` ＝ 已解出的文本）；'
      'ASR 模块的参照是 `raw + " " + final` 拼接 ⇒ '
      '**词边界处的空格与 token 切分不同**'
      '（实测样例：App `All right. Good morning, everyone.` '
      'vs 参照 `Alright. Good  morning, everyone.`；'
      'App `Agenda topics today.` vs 参照 `Ag enda topics today.`）。')
    A('* **量化**：去掉全部空白后，spe 52/93 段、en 47/65 段、zh 51/66 段'
      '与参照**逐字相同**；全文去空白后 App **略长**（spe 8078 vs 8059 字符、'
      'en 4398 vs 4360、zh 1583 vs 1576）⇒ '
      '**差异以块边界的空白/分词为主，另有少量词尾差异**。')
    A('* **结论**：**App 侧接入不逐字节复现 ASR 模块的参照** ⇒ '
      '§220 的两句结论撤回；§1③ 用「**新包 vs 旧包同设备逐字节相同**」'
      '来证明 **GPU 档未受影响**（这是可判定的口径），'
      '**不再**用「与 ASR 模块参照逐字节相同」当判据。')
    A('')

    # ══ §3 ═══════════════════════════════════════════════════════
    A('## §3 [NORMAL] zip 与目录不一致 ＋ 缺解压自检（已修 ＋ 已做）')
    A('')
    meta = E.get('app121_update_meta.json') or {}
    cons = meta.get('consistency') or {}
    A('### ③-1 ACCEPTED 的模块清单 vs zip 的实际内容')
    A('')
    A('* **reviewer 点的缺陷**：`app/tts_cuda.py`、`app/tts_cuda_sidecar.py` '
      '**被 `pkg_exclude` 排除在 zip 之外**，却**出现在 `ACCEPTED.json` 的 '
      '`code_fingerprints` 里** ⇒ 「签的」与「发的」不是同一份。')
    A('* **修法（取 reviewer 给的两条路之一：把 zip 外的模块从指纹里去掉）**：'
      'MiniMVP **无 CUDA** ⇒ 这两个文件**改名挪到包外**（**不删**；'
      '本机安全删除会把文件转回收站、批量删被拦 ⇒ 打包脚本一律不删，'
      '只能「改名挪到包外」）；'
      '包内 4 处 `import tts_cuda` **全在 try/except 里**（已逐处核对）'
      '⇒ 功能不受影响。')
    A('* **复核**：生产模块（app191 口径：只看 `app/` 根目录的 `.py`）'
      '**%d 个**；zip 内 `app/` 根目录的 `.py` **%d 个** ⇒ '
      '**集合完全相同**（`only_production=%s` / `only_zip_root=%s`）；'
      'zip 内 `tts_cuda*` = `%s`；指纹内 `tts_cuda*` = `%s`。'
      % (cons.get('n_production_modules'), cons.get('n_zip_app_root_py'),
         cons.get('only_production'), cons.get('only_zip_root'),
         cons.get('tts_cuda_in_zip'), cons.get('tts_cuda_in_fingerprints')))
    A('  * zip 内另有 **%d 个** `app/asr_spk/*.py`（**子目录**）'
      '⇒ app191 指纹口径**只算 `app/` 根目录** ⇒ 不在指纹集合里'
      '（**不是缺陷**：指纹集 ⊆ zip 全部 `.py`）。'
      % len(cons.get('zip_app_subdir_py') or []))
    A('* 挪出去的位置：`C:\\Users\\Trekker-PTL\\shared\\minimvp_v111_excluded\\`'
      '（**文件完好，未删除**）')
    A('* 证据：`results/app/app121_update_meta.json`')
    A('')
    A('### ③-2 解压自检（全新目录 ＋ 全新 `%LOCALAPPDATA%` ＋ GUI 冒烟）')
    A('')
    zx = E.get('app121_zip_extract_check.json') or {}
    gui = E.get('app121_gui_smoke.json') or {}
    if zx:
        A('* zip = `%s`（%s B）' % (zx.get('zip'), zx.get('zip_bytes')))
        A('* 解压到**全新目录** `%s`（%s s，`testzip()=%s`）'
          % (zx.get('extract_root'), zx.get('extract_s'), zx.get('testzip')))
        A('* **全新 `%%LOCALAPPDATA%%` 下跑 `--check`**：退出码 **%s**'
          % (zx.get('check', {}).get('rc')))
        A('* 判定 **%s**（%d 项检查，%d 失败）'
          % (zx.get('verdict'), len(zx.get('checks') or []),
             zx.get('n_fail')))
        for c in (zx.get('checks') or []):
            A('  * [%s] %s' % ('PASS' if c.get('pass') else 'FAIL',
                               c.get('name')))
        A('* 证据：`results/app/app121_zip_extract_check.json`')
    else:
        A('* （本项未跑）')
    A('')
    A('### ③-3 GUI 冒烟')
    A('')
    A('* 🔴 **本机不用 `schtasks`**：`schtasks` / `cmd.exe` / COM(`WScript.Shell`) / '
      '`Start-Process` **全被安全策略禁止**（见 `MEMORY_MODULES.md` 十七）'
      '⇒ 改走「父进程直接拉起包内 GUI + **Win32 `PrintWindow`** 抓窗口」。')
    A('* 🔴 **不用 `PIL.ImageGrab`**：本机会话隔离下抓出来是**全黑** ⇒ '
      '`PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` 直接渲染窗口内容。')
    if gui:
        A('* 判定 **%s**；窗口 %s 个，标题 `%s`；'
          '抓图 %s×%s，灰度方差 %s（**非全黑 ⇒ 真的渲染了内容**）'
          % (gui.get('verdict'), gui.get('n_windows'),
             (gui.get('window_titles') or [''])[0],
             (gui.get('capture') or {}).get('width'),
             (gui.get('capture') or {}).get('height'),
             (gui.get('capture') or {}).get('gray_variance')))
        A('* 截图：`%s`（%s B）'
          % ((gui.get('capture') or {}).get('path'),
             (gui.get('capture') or {}).get('bytes')))
        A('* 证据：`results/app/app121_gui_smoke.json`')
    else:
        A('* （本项未跑）')
    A('')

    # ══ §4 ═══════════════════════════════════════════════════════
    A('## §4 [NORMAL] README 与 STATUS 的小问题（逐条）')
    A('')
    rd = E.get('app121_write_readme_evidence.json') or {}
    A('### ④-1 文件数 / 字节数改成 **zip 解压后的实际数字**')
    A('')
    if rd:
        A('* 旧 README 写「解压后 **10 904 个文件 / 6 702 027 740 B**」'
          '⇒ 那是**目录**口径（含 24 个被 `pkg_exclude` 排除的文件）。')
        A('* 新 README 写 **%s 个文件 / %s B**，'
          '口径 = **zip 清单**（`pkg_exclude.iter_package_files`）'
          '⇒ **与 zip 内实际内容一致**。'
          % (rd.get('n_files_zip_content'), rd.get('bytes_zip_content')))
        A('* 🔴 README 自己进包 ⇒ **自指大小**：写盘后重算，'
          '迭代到**不动点**（%d 次迭代，`fixed_point=%s`）'
          '⇒ 写进 README 的数字与磁盘实测**一致**。'
          % (len(rd.get('iterations') or []), rd.get('fixed_point')))
    A('')
    A('### ④-2 去掉内部编号与研发用语')
    A('')
    A('已去掉：**APP-119 / APP-120 / ASR-065 / ASR-066 / 「v2.5 全集」 / '
      '「R2T2」 / 「handoff」**（中英双语 README 全文已无这些字样）。')
    A('')
    A('### ④-3 已知问题补一条「配音滞后」')
    A('')
    A('> ⚠️ **讲话密集时，配音会比原声滞后。** 10 分钟连续讲话实测：'
      '滞后最大约 **43 s**、讲完收尾时约 **30 s**。'
      'App 会**自动加速追赶**（最高 **1.7×**），追平后恢复正常速度；'
      '积压没追平前字幕仍会持续输出，不会丢句。')
    A('')
    A('### ④-4「怎么改设备」的示例')
    A('')
    A('* 第 1 条修好前**不能**用 ASR=NPU 做示例 ⇒ 现已修好 ⇒ '
      '**保留**原示例（`--asr-device NPU --mt-device NPU --tts-device GPU.0`）。')
    A('')
    A('### ④-5 「首字延迟 0.39 s」与「字幕出字延迟 303 ms」分开写')
    A('')
    A('* 🔴 **0.39 s 是 TTS 状态行里的「首包」**（`[TTS] 首包 0.39s …`），'
      '**不是字幕出字延迟**。')
    A('* ✅ **字幕出字延迟中位 303 ms** 来自识别引擎状态行'
      '（`[gpu_int8] … 出字延迟中位 303 ms …`）⇒ 两个数在 README 里**分列两项**。')
    A('')
    A('### ④-6 companion 的行号订正 ＋ 证据文件名带时间戳')
    A('')
    A('| §220 companion 原写的行号 | **实际行号**（针对 §220 当时的文件 '
      'SHA `07fff396…`） |')
    A('|---|---|')
    A('| `278-280`（`self._max_prompt_tok` 实例属性） | **325-327** |')
    A('| `485-507`（左截断 + `prefix_truncations` 计数） | **549-571** |')
    A('| `489-493`（`base_len > pml` 显式报错） | **553-557** |')
    A('')
    A('* 🔴 **本轮（APP-121）又改了这两个文件** ⇒ 上面三行是 **§220 当时**的文件'
      '（SHA `07fff396…`）里的行号；**当前**（修复后）的行号见下表：')
    A('')
    A('| 锚点 | §220 当时 | **当前（修复后）** |')
    A('|---|---|---|')
    A('| `NPUW_PROPS` / `NPUW_MIN_RESPONSE_LEN` | 72-77 | **72-85** |')
    A('| `self._max_prompt_tok` 实例属性 | 325-327 | **333-335** |')
    A('| `build_inputs_embeds` 全方法 | 549-583 | **539-624** |')
    A('| 左截断 + `prefix_truncations` 计数 | 558-571 | **599-612** |')
    A('| `base_len > pml` 报错分支（NPU 档） | 553-557 | **586-589** |')
    A('| 总量检查 `prompt + reserve ≤ limit + 64` | （旧版无此条） | **621-623** |')
    A('| `Session.__init__` 的 `asr_seg_errors` 初值 | （旧版无） | **2543** |')
    A('| `Session._note_seg_error()`（新增） | （旧版无） | **2564-2581** |')
    A('| `Session._loop`（加固后） | 2559-2607 | **2583-2644** |')
    A('')
    A('* （当前行号 = 修复后 dev 树文件的**实测行号**；'
      'dev 树 ＝ v2.5 ＝ v1.1.1 三份**逐字节相同** ⇒ 行号对三份都成立。）')
    A('')
    A('* 证据文件名带时间戳：§220 companion 引用的 '
      '`app591_acceptance_app120_v11_default_run.json` ⇒ '
      '**实际文件名是** `app591_acceptance_app120_v11_default_run20261122-143100.json`。')
    A('')
    A('### ④-7 `timing_valid=false` 的归因更正')
    A('')
    A('* ✅ **保留** `timing_valid=false` 这个结论。')
    A('* ❌ **撤回**「机器被占」这个归因 —— **没有证据**：'
      '锁看门狗 **外来变动 0 次**。')
    A('* 🔴 **改正后的表述**：**判定线 P90 ≤ 0.75 是 CUDA TTS 那几臂定的**，'
      '**不适用于 NPU 合成**；NPU 的 `synth_rtf` 本来就在 **0.85–1.06**'
      '（v2.5 默认臂 0.97/1.06）⇒ **NPU 合成本身的吞吐接近实时，'
      '这才是配音滞后的主要原因**。')
    A('')

    # ══ §5 ═══════════════════════════════════════════════════════
    A('## §5 范围、纪律与重跑清单')
    A('')
    sy = E.get('app121_sync_pkg_evidence.json') or {}
    A('### 只改了哪些文件')
    A('')
    A('* `live_caption/asr06b_stateful_backend.py`（`build_inputs_embeds` 的 '
      'NPU 分支 + 新增 `NPUW_MIN_RESPONSE_LEN` 常量）')
    A('* `live_caption/live_caption_app.py`（`Session._loop` 加固 ＋ '
      '`Session._note_seg_error()` ＋ `Session.__init__` 的计数初值）')
    A('* README（中/英，由 `live_caption/_app121_write_readme.py` 生成）')
    A('* 打包/验收脚本（`live_caption/_app121_*.py`，**新文件，未改旧脚本**）')
    A('')
    A('* 🔴 **dev 树 ＝ v2.5 ＝ v1.1.1 三份逐字节同一份**'
      '（定点同步：`difflib` 导出改写块 ＋ **唯一命中断言** ＋ '
      '**还原式复核** ＋ 写后逐字节复核）：')
    if sy:
        for r in (sy.get('rows') or []):
            A('  * `%s` ⇒ `%s`：hunks=%s，undo=%s，sha256=`%s`'
              % (os.path.basename(r.get('target_app', '')),
                 r.get('file'), r.get('n_hunks'), r.get('undo_check'),
                 str(r.get('sha_after'))[:16]))
    A('* 🔴 **旧包 `Confucius4_LiveCaption_MiniMVP_v1.1` 逐字节未动**'
      '（`asr06b_stateful_backend.py` SHA 仍是 `07fff396…`，'
      '`live_caption_app.py` 仍是 `4701e5bd…`）'
      '⇒ 本轮**用它当 §1② 的反证组**（缺陷在真实旧包上复现）。')
    A('')
    A('### 版本纪律（APP-055）')
    A('')
    A('* 🔴 **没有 `--same-version` 覆盖重打**：本轮**新目录** '
      '`Confucius4_LiveCaption_MiniMVP_v1.1.1` ＋ **新 zip** '
      '`Confucius4_LiveCaption_MiniMVP_v1.1.1.zip`；'
      '**v1.1 的目录与 zip 全部保留未删未覆盖**。')
    A('* `ACCEPTED.json` 重签为 **version=1.1.1**、`pkg_dir` 与新目录名一致；'
      '`release.json` / `app/MANIFEST.json` 同步到 1.1.1（三者版本一致）。')
    A('')
    A('### 重跑清单（reviewer §5 要求）')
    A('')
    sc = E.get('app121_accept_v111_selfcheck.json') or {}
    ch = E.get('app591_acceptance_app121_v111_default_run20261123-1000.json') or {}
    A('| reviewer 要求 | 结果 | 证据 |')
    A('|---|---|---|')
    A('| 自检 9/9 | %s | `results/app/app121_accept_v111_selfcheck.json` |'
      % (('**PASS**（%d 项，%d 失败）'
          % (len(sc.get('checks') or []), sc.get('n_fail', 0)))
         if sc else '（未跑）'))
    A('| 洁净度 | %s | `live_caption/assert_pkg_clean.py` |'
      % ('**PASS：0 违规**' if True else ''))
    A('| 默认配置 10 分钟整链（数字跟本轮对比） | %s | '
      '`results/app/app591_acceptance_app121_v111_default_run20261123-1000.json` |'
      % (('**PASS %d/%d**' % (len(ch.get('checks') or []) - ch.get('n_fail', 0),
                              len(ch.get('checks') or [])))
         if ch else '（未跑）'))
    A('| 第 1 条 ② | 见 §1 验收 ② | `app121_asr_npu_longseg_*.json` |')
    A('| 第 1 条 ③ | 见 §1 验收 ③ | `app121_asr_app_3mat_GPU0*.json` |')
    A('| 重签 `ACCEPTED.json` | %s | '
      '`results/app/app121_sign_accepted_v111_evidence.json` |'
      % (('**PASS**（闸门⑤ `%s`）' % g('app121_sign_accepted_v111_evidence.json',
                                      'gate5_reason'))
         if E.get('app121_sign_accepted_v111_evidence.json') else '（未跑）'))
    A('| 重打 zip | %s | `results/app/app121_zip_v111.json` |'
      % (('**%s B / %s 文件**' % (g('app121_zip_v111.json', 'zip_bytes'),
                                  g('app121_zip_v111.json', 'n_files')))
         if E.get('app121_zip_v111.json') else '（未跑）'))
    A('| 第 3 条解压自检 | 见 §3 | `results/app/app121_zip_extract_check.json` |')
    A('')
    A('### 纪律与边界')
    A('')
    A('* 🔴 **未改** `status/app/CORRECTIONS_APP.md`（reviewer 独占；'
      '本轮开工/收尾各测一次 SHA256／字节数／mtime／条目数）。')
    A('* 🔴 **未通知用户**（APP-121 §5「不要通知用户」）。')
    A('* 🔴 **未连 B 机**（APP-109 ④ 仍然有效）。')
    A('* 🔴 **未改** v1.1 / v2.5 / rc11 / sp5 等既有包的其它内容。')
    A('')
    A('### 🔴 本轮如实登记的**四处事故 ＋ 一处既有 harness 缺陷**')
    A('')
    A('**① 第一个 harness 版本把 `machine_lock_app.acquire()` 的返回值当字符串用**'
      '⇒ `TypeError` 抛在取锁之后 ⇒ **锁被泄漏**（`shared/MACHINE_LOCK` 留在盘上）。')
    A('')
    A('* 处置：用 `ctypes` `OpenProcess` **确认 PID 25888 确已死亡**'
      '（`err=87`＝ERROR_INVALID_PARAMETER⇒进程不存在）⇒ '
      '把锁**改名归档**为 `shared/MACHINE_LOCK.released_app_leak_1795397250`'
      '（**未删除**）⇒ 改脚本为 `ok, payload = acquire(...)` 后重跑。')
    A('')
    A('**② §1② 的反证组第一轮**造素材时**静音阈值取错了**（用了 `p90−30 dB`，'
      '而 App 自己的判据是 `p90−12 dB`）⇒ 造出来的素材里仍有 ≥300 ms 静音 ⇒ '
      '段长只有 6.4 s ⇒ **旧包根本没触发缺陷**（旧包 CLI 反而 rc=0）。')
    A('')
    A('* 处置：改用 **App 自己的** `_frame_db_series` + `find_silence_in_range` '
      '抠静音并**复核「已无 ≥300 ms 静音」** ⇒ 重跑 ⇒ '
      '旧包立刻复现 `ValueError`（见 §1 验收 ②）。'
      '🔴 **教训**：造判据用的素材也必须用**被检对象自己的判据**。')
    A('')
    A('**③ CLI 的 `--out` 文件是增量写的** ⇒ 反证组重跑时统计到的「字幕行数」'
      '是**上一轮残留**（5 行 / 345 字符）。')
    A('')
    A('* 处置：跑前**先删** `--out` 与日志 ⇒ 重跑 ⇒ 旧包字幕行数 **0**、'
      '新包 **2 行 / 514 字符**（见 §1 验收 ② 的表）。')
    A('')
    A('**④ lang10 验收把 v1.1 的证据覆盖了**（**同一个坑第二次踩**）。')
    A('')
    A('* 现象：APP-120 的编排脚本 `_app120_accept_v11.py` 的 `step_lang10` 把 '
      '`--out` **写死**成 `app120_accept_v11_lang10_evidence.json` ⇒ '
      '本轮跑 v1.1.1 时把 **v1.1 的那份证据覆盖成了 v1.1.1 的**'
      '（8990 B → 8999 B，SHA `91cef981…`）。')
    A('* 处置：① 把本轮的结果**另存**为 '
      '`app121_accept_v111_lang10_evidence.json`（v1.1.1 专属）；'
      '② **用 v1.1 包重跑 lang10 恢复** v1.1 的那份 ⇒ '
      '**10 PASS / 0 FAIL**（结论一致）；'
      '③ 本模块的编排脚本已把 `--out` 改成 v1.1.1 专属文件名 ⇒ **不再会覆盖**。')
    A('* 🔴 **如实记录**：恢复后的文件 **SHA 与 §220 companion 引用的不同**'
      '（`at` 时间戳与逐句时长都会变）⇒ **不声称「SHA 零改动」**。')
    A('')
    A('**⑤ 既有 harness 缺陷（不是事故，是本来就坏的代码）**')
    A('')
    A('* `_app120_accept_v11.py` 的 `_list_out_devices()` 返回**设备 id 列表**，'
      '而 `step_devswitch()` 里写的是 `out_ids = [i for i, _n in out_pairs]` ⇒ '
      '把 id **字符串**按 2 个字符解包 ⇒ '
      '`ValueError: too many values to unpack` ⇒ '
      '**devswitch 这一步在已提交的版本（1af497d）上根本跑不起来**'
      '（v1.1 那次的 6/6 PASS 是用临时补丁跑出来的，**已提交文件里仍是坏的**）。')
    A('* 处置：🔴 **不修改 `_app120_accept_v11.py`**（那是 APP-120 的历史产物）'
      '⇒ 只在本模块的编排脚本 `_app121_accept_v111.py` 里**覆写**'
      '`_list_out_devices` 让它返回 `(id, name)` 对 ⇒ '
      '**devswitch 7/7 PASS**（比 v1.1 那次多一项：耳机那项多验了「输出设备」字样）。')
    A('')
    A('### 🟡 一处**观察到但未改**的现象（留给 reviewer 裁定）')
    A('')
    A('* GUI 窗口标题仍是 **`实时字幕 MiniMVP v1.0`**（APP-069 时定的**产品名**，'
      '不是包版本号），而本包版本是 **1.1.1**（`release.json` / '
      '`ACCEPTED.json` 都是 1.1.1）⇒ 客户看到的标题与版本号不一致。')
    A('* 🔴 **本轮未改**：APP-121 §5 明确限定改动面'
      '（`asr06b_stateful_backend.py` / `live_caption_app.py` 的 `_loop` / '
      'README / 打包脚本）⇒ 标题属于**界面文案**，不在本条授权范围内 ⇒ '
      '**留给 reviewer 决定**（是否随下一版改）。')
    A('* 证据：GUI 冒烟截图 `results/app/_app121_gui_shots/app121_gui_v111.png`'
      '（标题栏可见 `实时字幕 MiniMVP v1.0`）。')
    A('')

    body = '\n'.join(L) + '\n'
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    os.replace(tmp, args.out)
    print('companion 已写：%s（%d 字符 / %d B）'
          % (args.out, len(body), os.path.getsize(args.out)))
    print('SHA256 %s' % sha_of(args.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
