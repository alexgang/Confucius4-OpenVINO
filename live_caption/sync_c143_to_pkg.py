#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c143_to_pkg.py — 把「MT §56 三处修复 + H-013 tokenizer」定点同步到客户包。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包，C-133 教训）；
- **替换后必须与仓库版逐字一致（归一化换行）才写盘**。

## 要同步的变更（全部来自 MT 模块移交说明）

来源：`shared/NOTICE_mt_to_app_20261024.md` 通知 5（§5.4 修改摘要）+ 通知 4（§4.2）；
MT 侧产物 `hy_bench/runs/c111_half/c111_fix_tests.json`（10/10 PASS）、
`hy_bench/runs/c111_half/c111_service_verify.json`（13/13 PASS）。

### ① `app/translator.py` —— `load_mt_tokenizer()` 新增（H-013）

MT 侧新增 `load_mt_tokenizer()`：传 `fix_mistral_regex=False` 消掉
`transformers` 的 mistral 探测警告。
- MT 实测：传 `False` ⇒ 分词 ids **30/30 逐条不变**、decode 回原文 30/30 一致；
- 传 `True` ⇒ 30 句里 **4 句 ids 变**（token 672→678）⇒ **会改 MT 输出** ⇒ 属质量变更；
- ⇒ 取 `False`；老版本 transformers 不认该参数时**退回不传**（行为不变，只留警告）。

### ② `app/translator.py` —— `CACHE_MAX` 400 → 4000（§56 缺陷③）

旧值 400 ⇒ 长会话（>400 句单元）**前段译文被 LRU/FIFO 淘汰** ⇒ 显示层取不到译文。
- 实测（260902_SPE 会议回放，225 段 / 61 分钟）：674 个句单元，`done` 只留 400
  ⇒ **前 274 条被淘汰**（674 − 400 = 274，与实测漏译数逐位吻合）。
- 内存代价：4000 × ≈200 B ≈ **0.8 MB** ⇒ 相对模型显存可忽略。
- ⚠️ 顺带修好了 `done_fix` 的同源淘汰（MT 侧已一并改）。

### ③ `app/translator.py` —— `_seen` 全局去重改「翻译去重 + 显示不去重」（§56 缺陷①）

旧行为：`if k in self._seen: continue` ⇒ **同一句话第二次出现就整句丢弃**
⇒ 会议实录实测 **38 句 / 3,312 字**真实内容被丢（用户投诉的「前半句丢失」）。
新行为：
- **翻译层**：同一句只翻一次（`done[key]` 一份译文）⇒ **不重复翻译、调用次数不增**；
- **显示层**：每次出现都建一个句单元 ⇒ 说话人真的又说了一遍，字幕就该显示两遍。

⚠️ 关键：`submit()` **和** `flush()` **两处都要改**（只改一处 ⇒ 收尾时再丢一句）。

### ④（App 侧，不在本脚本）`live_caption_app.py` 的 `clear()`

MT 通知 4.3 点名：`clear()` 只清 `seg_keys/seg_carry/seg_half`，
**没清 `self.mt.units` / `_seen` / `_pend` / `done`** ⇒ 清屏后旧句单元仍在
⇒ 渲染层会把**上一场**的译文混进新场次。
⇒ 属 App 侧改动，在仓库 `live_caption_app.py` 里改 + 本脚本一并同步。

## 实测证据（MT 侧产物，App 未复跑 GPU）

- `hy_bench/runs/c111_half/c111_fix_tests.json` ⇒ **10/10 PASS**
  （SPE 守恒 41,895/41,895、显示单元 674→712、翻译调用 674 不增、淘汰 0）；
- `hy_bench/runs/c111_half/c111_service_verify.json` ⇒ **13/13 PASS**
  （直接驱动真实 `TranslationService` 类）；
- `hy_bench/runs/c111_half/c111_variants_v4_SPE.json`（433,168 B / 2026-10-25 00:20）
  ⇒ §59.3 的 **5 项必查项 5/5 PASS**（空 hyp 0 / 唯一 key 674 / 单元 712 /
  翻译调用 674 / `src_chars=orig_chars=41,895`）。

## 用法
    python live_caption/sync_c143_to_pkg.py            # 执行
    python live_caption/sync_c143_to_pkg.py --check    # 只校验不写
    python live_caption/sync_c143_to_pkg.py --report <报告输出路径>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'live_caption')

# 包外备份目录（绝不能放包内）
BACKUP_DIR = r'C:\Users\Trekker-PTL\pkg_backup_app014'

# ── 要同步的文件 ──────────────────────────────────────────────────────
FILES = ['translator.py', 'live_caption_app.py', 'tts_worker.py']

# ── 定点替换清单：(标签, 文件, OLD, NEW) ─────────────────────────────
# 每条 OLD 都必须在包内**唯一命中**（assert count == 1）才允许替换。

PATCHES = [
    (
        # ① H-013：新增 load_mt_tokenizer（放在 A1 翻译内核之前）
        'P1-load-mt-tokenizer',
        'translator.py',
        """    return time.perf_counter() - t0


# ── A1 翻译内核""",
        """    return time.perf_counter() - t0


def load_mt_tokenizer(AutoTokenizer, model_dir):
    \"\"\"加载 Hy-MT2 的 tokenizer，**消掉 `fix_mistral_regex` 警告**。

    ★ H-013（2026-10-24）：App 日志里的那条警告来自 **MT 侧**加载
      Hy-MT2 tokenizer（`transformers/tokenization_utils_base.py` 的
      mistral 探测分支），**不是 TTS 的问题**（TTS 已确认并转达）。

    ★ 为什么传 **False** 而不是 True：
      - 传 `False` = 消警告，且**分词逐字不变**（MT 侧实测 30/30 句 ids 相同，
        预分词器不变）；
      - 传 `True`  = 换成 mistral 的预分词器，**会改分词**（实测 30 句里 4 句 ids 变，
        token 总数 672→678；变的都是「英文数字+单位粘连」如 `[REDACTED]`），
        ⇒ **会改变 MT 输出**，属质量变更，必须用 chrF 口径对照后才能决定；
      - 且 `decode` 回原文 **30/30 一致** ⇒ `False` 无任何语义损失。
      ⇒ 结论：**传 False**（消警告 + 零行为变化 + 零风险）。

    ⚠️ 容错：老版本 transformers 可能**不认** `fix_mistral_regex` 这个参数
      （形参在 4.57.6 才有）⇒ 传参失败就退回不传（行为与以前一致，只是警告还在）。
    \"\"\"
    try:
        return AutoTokenizer.from_pretrained(model_dir, fix_mistral_regex=False)
    except TypeError:
        # 老版本 transformers 不支持该参数 ⇒ 不传（保留原警告，行为不变）
        return AutoTokenizer.from_pretrained(model_dir)


# ── A1 翻译内核""",
    ),
    (
        # ① H-013：HunyuanTranslator.__init__ 改用 load_mt_tokenizer
        'P2-use-load-mt-tokenizer',
        'translator.py',
        """        self.tok = AutoTokenizer.from_pretrained(self.model_dir)
""",
        """        self.tok = load_mt_tokenizer(AutoTokenizer, self.model_dir)
""",
    ),
    (
        # ② §56 缺陷③：CACHE_MAX 400 → 4000
        'P3-cache-max-4000',
        'translator.py',
        """    CACHE_MAX = 400            # 译文缓存条数上限（FIFO）
""",
        """    # 🔴🔴 **`CACHE_MAX` 从 400 提到 4000（2026-10-24 21:20 修复）**
    #   **旧值 400 会让长会话的前段译文被淘汰** ⇒ 显示层拿不到译文。
    #   实测（260902_SPE 会议回放，225 段 / 61 分钟）：产出 **674 个句单元**，
    #   而 `done` 只留最后 400 条 ⇒ **前 274 条被淘汰**（674 − 400 = 274，**逐位吻合**）
    #   ⇒ 症状 = 「前面的段落没有译文 / 漏译 40.7%」。
    #   **内存代价**：每条约 = 原文 key + 中文译文 ≈ 200 B ⇒ 4000 条 ≈ 0.8 MB，
    #   相对 ASR/MT 模型显存可忽略 ⇒ 宁可多留，不可丢。
    #   ⚠️ 真正的上限是**会话长度**，不是内存；`clear()` 会清空。
    CACHE_MAX = 4000           # 译文缓存条数上限（FIFO）—— 覆盖 4~6 小时长会议
""",
    ),
    (
        # ③ §56 缺陷①：submit() 里的 `_seen` 全局丢弃 → 翻译去重 + 显示不去重
        'P4-seen-submit',
        'translator.py',
        """        for s in ready:
            k = norm_key(s)
            if not k or k in self._seen:
                continue
            self._seen.add(k)
""",
        """        for s in ready:
            k = norm_key(s)
            if not k:
                continue
            # 🔴🔴 **重复句不再被丢弃（§50.2 / §54.4 定案，2026-10-24 21:12 修复）**
            #   **旧行为（`k in self._seen` ⇒ 整句跳过）会丢真实内容**：
            #   ASR 复读是真实存在的（260902_SPE 会议实录实测 225 段里有 **38 句**
            #   是「同一句被重复说」，共 **3,312 字**），全局去重把它们**整段丢弃**
            #   ⇒ 内容级守恒失败（实测 orig 41,895 → 保留 38,583，**缺 3,312 字**）。
            #   ⇒ 用户报的「前半句丢失」在会议场景会复现。
            #
            #   **新行为 = 「翻译去重 + 显示不去重」**：
            #   · 翻译：同一句话**只翻一次**（`done[key]` 一份译文，译文必然相同
            #     ⇒ 不重复翻译、不增加调用次数）；
            #   · 显示：每次出现都**建一个句单元** ⇒ 说话人真的又说了一遍，
            #     字幕就该显示两遍 ⇒ 内容级守恒 100%。
            #   ⇒ `mt_units()` 能逐处渲染，`mt_of_seg(seg)` 按段取到自己的那一份。
            if k in self._seen:
                # 已翻过 ⇒ 不重复入队，但**保留显示单元**（内容不能丢）
                self.units.append(dict(key=k, src=s, seg=seg, mt=None))
                if seg is not None:
                    self.seg_keys.setdefault(seg, [])
                    if k not in self.seg_keys[seg]:
                        self.seg_keys[seg].append(k)
                continue
            self._seen.add(k)
""",
    ),
    (
        # ③ §56 缺陷①：flush() 同步（漏改会在收尾再丢一句）
        'P5-seen-flush',
        'translator.py',
        """        if k not in self._seen:
            self._seen.add(k)
            self.units.append(dict(key=k, src=pend, seg=seg, mt=None))
            self.q.put(_Job('final', k, pend, seg=seg))
            if seg is not None:
                self.seg_keys.setdefault(seg, [])
                if k not in self.seg_keys[seg]:
                    self.seg_keys[seg].append(k)
                self.seg_half[seg] = False
            return [k]
        # 已经翻过了（理论上不会走到）—— 只把译文重新标成可朗读
""",
        """        # 🔴 与 `submit()` 一致：**重复句不丢弃**（翻译去重 + 显示不去重）
        if k not in self._seen:
            self._seen.add(k)
            self.units.append(dict(key=k, src=pend, seg=seg, mt=None))
            self.q.put(_Job('final', k, pend, seg=seg))
            if seg is not None:
                self.seg_keys.setdefault(seg, [])
                if k not in self.seg_keys[seg]:
                    self.seg_keys[seg].append(k)
                self.seg_half[seg] = False
            return [k]
        # 已翻过 ⇒ 不重复入队，但**保留显示单元**（内容不能丢，见 submit() 里的说明）
        self.units.append(dict(key=k, src=pend, seg=seg, mt=None))
        if seg is not None:
            self.seg_keys.setdefault(seg, [])
            if k not in self.seg_keys[seg]:
                self.seg_keys[seg].append(k)
            self.seg_half[seg] = False
        # 已经翻过了（理论上不会走到）—— 只把译文重新标成可朗读
""",
    ),
    (
        # ④ App 侧：clear() 只清 3 个字典 ⇒ 清屏后旧句单元/旧译文/旧半句残留
        'P6-app-clear-reset',
        'live_caption_app.py',
        """    def clear(self):
        self.final_text = ''
        self.blocks = []
        self.mt.seg_keys.clear()
        self.mt.seg_carry.clear()
        self.mt.seg_half.clear()
        self._render('')
""",
        """    def clear(self):
        self.final_text = ''
        self.blocks = []
        self._reset_mt_session()
        self._render('')

    def _reset_mt_session(self):
        \"\"\"🔴🔴 清空**整个 MT 会话状态**（不只 3 个字典）。

        ★ **旧行为是真 bug**（MT 移交说明 §4.3 点名）：
          原来只清 `seg_keys` / `seg_carry` / `seg_half`
          ⇒ **没清** `units`（句单元列表）、`_seen`（已提交句集合）、
          `_pend`（跨段缓冲）、`done` / `done_fix`（译文缓存）。
          ⇒ 点「清空」之后：
            · `mt.units` 里**上一场**的句单元还在 ⇒ 渲染层会把旧译文混进新场次；
            · `_seen` 还在 ⇒ 新场次里出现的**同一句**会被当成「已翻过」
              ⇒ **不翻译、不进显示单元** ⇒ 新场次的这句话**直接丢失**；
            · `_pend` 里还挂着上一场的半句 ⇒ 新场次第一段会**接到上一场的尾巴后面**
              ⇒ 出现「前半句丢失 / 跨行重复」；
            · `done` 里还留着旧译文 ⇒ 同一句在新场次**读到上一场的旧译文**。
          ⇒ 这些和 `translator._loop()` 里「换模型后清缓存」是同一套字段，
            这里按同样口径清（**不重载模型**，只重置会话状态）。

        ⚠️ 用 `getattr(..., None)` 防御：字段名是 `translator.py` 的内部约定，
          万一将来改名 ⇒ 跳过而不是抛异常把「清空」按钮搞崩。
        \"\"\"
        mt = self.mt
        # ── 字典类（原来清的 3 个 + 译文缓存）──
        for name in ('seg_keys', 'seg_carry', 'seg_half'):
            d = getattr(mt, name, None)
            if isinstance(d, dict):
                d.clear()
        for name in ('done', 'done_fix'):
            d = getattr(mt, name, None)
            if hasattr(d, 'clear'):
                d.clear()
        # ── 列表 / 集合 / 标量 ──
        units = getattr(mt, 'units', None)
        if isinstance(units, list):
            units.clear()
        seen = getattr(mt, '_seen', None)
        if isinstance(seen, set):
            seen.clear()
        if hasattr(mt, '_pend'):
            mt._pend = ''
        if hasattr(mt, '_half'):
            mt._half = None
        if hasattr(mt, 'draft'):
            mt.draft = ''
        if hasattr(mt, '_last_src'):
            mt._last_src = ''
""",
    ),
    (
        # ⑤ TTS-006：tts_worker 在**分句之前**做中文数字正则化
        #    （TTS 模块 STATUS_TTS §27 明确：分句按字数估帧数 ⇒ 若先分句再正则化，
        #     估的是「数字」的字数，而实际读的是「五十二」的 3 个字 ⇒ 帧数上限被低估）
        #    ⚠️ TTS-008 已验收通过（A 全达标）⇒ 但**客户包里那份一直缺**（§24 遗留项）
        'P7-tts-worker-zhnorm',
        'tts_worker.py',
        """        blang = 'Chinese' if lang.lower().startswith('zh') else 'English'

        # 长句切分（保守上限 478 帧 ≈ 39.8 s）""",
        """        blang = 'Chinese' if lang.lower().startswith('zh') else 'English'

        # 🔴🔴 TTS-006：**中文数字正则化要在分句之前**
        #   （分句按字数估帧数 ⇒ 若先分句再正则化，估的是「数字」的字数，
        #    而实际读的是「五十二」的 3 个字 ⇒ 帧数上限会被低估）
        #   ⇒ 这里先正则化，再 split_long_text。
        #   ⚠️ `tts_engine.stream()` 里也有一层（幂等 ⇒ 不重复转换），
        #   那层负责覆盖**其它 stream 调用方**。
        if lang.lower().startswith('zh'):
            text = tts_engine.normalize_zh_numbers(text)

        # 长句切分（保守上限 478 帧 ≈ 39.8 s）""",
    ),
    (
        # ⑥ 🔴 **内部素材脱敏**：MT 移交的注释里带了内部会议音频编号
        #    （`260902_SPE`）⇒ `pack_v13.py --dry-run` 的内部素材闸门
        #    **FAIL**（APP-006 第 6 步的打包前检查）。
        #    ⚠️ **不能靠加豁免绕过** —— 豁免会掩盖真泄露；
        #      正确处置 = 注释里去掉内部资产编号，保留技术结论。
        #    ⇒ 「260902_SPE 会议回放 / 会议实录」→「内部 61 分钟会议回放 / 会议实录」
        'P8-desensitize-meeting-id',
        'translator.py',
        """    #   实测（260902_SPE 会议回放，225 段 / 61 分钟）：产出 **674 个句单元**，""",
        """    #   实测（内部 61 分钟会议回放，225 段）：产出 **674 个句单元**，""",
    ),
    (
        'P8b-desensitize-meeting-id-2',
        'translator.py',
        """            #   ASR 复读是真实存在的（260902_SPE 会议实录实测 225 段里有 **38 句**""",
        """            #   ASR 复读是真实存在的（内部 61 分钟会议实录实测 225 段里有 **38 句**""",
    ),
]


def discover_pkg_app() -> str:
    """自动发现最大版本的客户包 app 目录。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = r'C:\Users\Trekker-PTL'
    best = None
    best_key = None
    for name in os.listdir(root):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        app = os.path.join(root, name, 'app')
        if not os.path.isdir(app):
            continue
        ver = name.rsplit('_v', 1)[-1]
        try:
            key = tuple(int(x) for x in ver.split('.'))
        except ValueError:
            continue
        if best_key is None or key > best_key:
            best_key = key
            best = app
    if best is None:
        raise SystemExit('[客户包] 未找到 Confucius4_LiveCaption_vX.Y/app')
    return best


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def norm(text: str) -> str:
    """归一化换行符（仓库 CRLF / 包内 LF 混用 ⇒ 比代码必须归一化）。"""
    return text.replace('\r\n', '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None, help='客户包 app 目录（默认自动发现）')
    ap.add_argument('--check', action='store_true', help='只校验不写')
    ap.add_argument('--report', default=None, help='报告输出路径')
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg_app()
    src_dir = SRC

    print(f'客户包 app : {pkg}')
    print(f'仓库源目录 : {src_dir}')
    print(f'同步文件   : {", ".join(FILES)}')
    print()

    pkg_texts = {}
    repo_texts = {}
    for rel in FILES:
        tpath = os.path.join(pkg, rel)
        spath = os.path.join(src_dir, rel)
        if not os.path.isfile(tpath):
            raise SystemExit(f'!! 包内找不到 {rel}')
        if not os.path.isfile(spath):
            raise SystemExit(f'!! 仓库找不到 {rel}')
        with open(tpath, 'r', encoding='utf-8', newline='') as f:
            pkg_texts[rel] = f.read()
        with open(spath, 'r', encoding='utf-8', newline='') as f:
            repo_texts[rel] = f.read()

    sha_pkg_before = {rel: sha256(os.path.join(pkg, rel)) for rel in FILES}
    mtime_before = {rel: os.path.getmtime(os.path.join(pkg, rel)) for rel in FILES}

    # ── 逐块判定状态（NEW 优先，避免「OLD ⊂ NEW」的追加型替换误判）──
    states = []
    for tag, rel, old, new in PATCHES:
        pt = pkg_texts[rel]
        if new in pt:
            states.append((tag, rel, 'already'))
        elif old in pt:
            states.append((tag, rel, 'pending'))
        else:
            raise SystemExit(
                f'!! [{tag}] 旧代码块与新代码块**都不在**包内 ⇒ 中止（不猜）')

    n_already = sum(1 for _, _, s in states if s == 'already')
    n_pending = sum(1 for _, _, s in states if s == 'pending')
    for tag, rel, s in states:
        print(f'[state] {tag} ({rel}): {s}')

    if n_pending == 0:
        print('[skip] 包内已是新代码（幂等，无需改动）')
        status = 'already_synced'
    else:
        # ── 校验每个待替换的 OLD 唯一命中 ───────────────────────────────
        for tag, rel, old, _new in PATCHES:
            if any(t == tag and s == 'pending' for t, _, s in states):
                n = pkg_texts[rel].count(old)
                if n != 1:
                    raise SystemExit(
                        f'!! [{tag}] 旧代码块命中 {n} 次（必须恰好 1 次）⇒ 中止')
        print(f'[ok] {n_pending} 个待替换块唯一命中（count == 1）；'
              f'已应用 {n_already} 个')

        if args.check:
            print('[check] --check 模式，不写盘')
            status = 'would_sync'
        else:
            new_texts = dict(pkg_texts)
            state_map = {t: s for t, _, s in states}
            for tag, rel, old, new in PATCHES:
                if state_map[tag] == 'already':
                    continue          # 已应用 ⇒ 不重复替换
                new_texts[rel] = new_texts[rel].replace(old, new, 1)
                assert new_texts[rel].count(new) == 1, \
                    f'[{tag}] 替换后新代码块命中数 != 1'

            # 🔴 **替换后必须与仓库版逐字一致（归一化换行）才写盘**
            for rel in FILES:
                if norm(new_texts[rel]) != norm(repo_texts[rel]):
                    raise SystemExit(
                        f'!! {rel} 替换后与仓库版**不一致** ⇒ 中止（不写盘）')
            print('[ok] 替换结果与仓库版逐字一致（归一化换行）')

            # ── 备份（包外）────────────────────────────────────────────
            os.makedirs(BACKUP_DIR, exist_ok=True)
            tag_stamp = time.strftime('%Y%m%d_%H%M%S')
            for rel in FILES:
                bk = os.path.join(
                    BACKUP_DIR,
                    f'{os.path.basename(os.path.dirname(pkg))}_{rel}.{tag_stamp}.bak')
                shutil.copy2(os.path.join(pkg, rel), bk)
                print(f'[ok] 已备份到包外: {bk}')
            for rel in FILES:
                with open(os.path.join(pkg, rel), 'w', encoding='utf-8',
                          newline='') as f:
                    f.write(new_texts[rel])
            print('[ok] 已写入定点替换')
            status = 'synced'

    # ── 汇总报告 ────────────────────────────────────────────────────────
    print()
    report = dict(status=status, pkg=pkg, files=FILES,
                  n_patches=len(PATCHES), n_pending=n_pending,
                  n_already=n_already, per_file={})
    for rel in FILES:
        tpath = os.path.join(pkg, rel)
        spath = os.path.join(src_dir, rel)
        sha_after = sha256(tpath)
        with open(tpath, 'r', encoding='utf-8', newline='') as f:
            t_norm = norm(f.read())
        with open(spath, 'r', encoding='utf-8', newline='') as f:
            r_norm = norm(f.read())
        identical = (t_norm == r_norm)
        info = dict(
            sha_pkg_before=sha_pkg_before[rel],
            sha_pkg_after=sha_after,
            sha_repo=sha256(spath),
            bytes=os.path.getsize(tpath),
            mtime=os.path.getmtime(tpath),
            mtime_before=mtime_before[rel],
            identical_to_repo=identical,
        )
        report['per_file'][rel] = info
        print(f'--- {rel} ---')
        print(f'  包内 SHA256 : {sha_pkg_before[rel][:16]}… -> {sha_after[:16]}…')
        print(f'  仓库 SHA256 : {info["sha_repo"][:16]}…')
        print(f'  包内字节    : {info["bytes"]}   mtime {info["mtime"]:.0f}')
        print(f'  与仓库逐字相同(归一化换行): {identical}')

    print()
    print(f'状态 : {status}')
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f'报告已写: {args.report}')

    return 0 if status in ('synced', 'already_synced', 'would_sync') else 1


if __name__ == '__main__':
    sys.exit(main())
