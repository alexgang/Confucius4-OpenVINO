#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_app426_write_status171.py — 追加 STATUS §171（APP 巡检：历史影响定界）

【纪律】
* 只**追加** `## §N` 章节；旧正文一字不删。
* 头部只做定点替换（last_ack 不变＝APP-098；更新时间用实测值）。
* 先写临时文件 ⇒ 原子替换 ⇒ 写后独立复核（旧正文逐字未变 + 新节命中 + 行尾未破）。
"""

import io
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')

STAMP = sys.argv[1] if len(sys.argv) > 1 else time.strftime('%Y-%m-%d %H:%M:%S')

FULL_BODY = """
## §171 巡检（last_ack=APP-098，{stamp}）｜**无新纠偏**；把 §170 ⑨ 两项「历史影响未评估」**定界完毕**（D1 零交付物受影响／**D2 影响已交付的 rc5**）｜**本条需等 reviewer 复核**

> 🔴 **本轮无新 reviewer 纠偏指令**：`CORRECTIONS_APP.md` 仍 **97 条 / 最大 APP-097**（SHA256 `36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2`／285 671 B／mtime 2026-11-10 11:49:26），开工＝收尾指纹一致 ⇒ **可称「SHA 零改动」**（全程只读、未改、未提交）。
> `last_ack` 已是 **APP-098**（上一会话执行完毕，commit `4637861`／2026-11-11 00:25:45）⇒ **本轮无编号更大的新条目可执行**；`shared/` 下无新增 `NOTICE_*`。
> 🔴 **本轮不是空转**：§170 ⑨ 明列两项「历史影响未评估」⇒ 本轮把它们**从猜测变成事实**（纯静态 + 桩内行为级复现，**未占设备、未持锁、未在 CPU 跑推理**）。

### ① D1「GUI 布局被吞」⇒ **历史影响 = 零交付物受影响**

| 项 | 结论 | 来源产物 / 字段 |
|---|---|---|
| 真正机制 | `874924a` 把 `App.__init__` 的**后半段（GUI 布局：`root.title`／`root.geometry`／全部控件构建／`prewarm_transformers()`／`self.load_engine()`）并进了 `_clone_nearest` 的方法体**；`_clone_nearest` 是 `App` 的**兄弟方法**，**不是嵌套函数** ⇒ 🔴 **此点纠正旧记忆里「误插进 `App.__init__` 中间 ⇒ 嵌套」的措辞** | `results/app/app425_hist_scan3.json` → `commits[]`；样本 `results/app/_app425_hist/{broken_874924a_app.py,parent_app.py,fixed_ba76ea5_app.py}` |
| 实测特征 | `874924a`：`App.__init__` stmt=**24**、布局调用（pack/grid/migrate）=**0**，而 `_clone_nearest` stmt=**261** 且含 **69** 个布局调用｜父提交 `b1496ba`：`__init__` stmt=282、布局调用 69、`_clone_nearest` **不存在**｜修复后 `ba76ea5`：`__init__` stmt=286、布局调用 69 | 同上（AST 判定） |
| 缺陷窗口 | 仅 **2 个 commit 快照**：`874924a`（11-09 12:26:26）与 `1cc86b2`（11-10 06:30:12）⇒ 修复于 `ba76ea5`（11-10 16:00:50） | `app425_hist_scan3.json` → `all_d1_broken` |
| **交付物影响** | 🔴 **15 个包逐个 AST 判定 ⇒ 0 个中招**（含真包 v2.4 与 MiniMVP rc5/rc6/rc7）⇒ **历史影响 = 零** | `app425_hist_scan3.json` → `summary.d1_broken_packages` = `[]`；`packages[].d1` |
| 为何交付物干净 | MiniMVP rc5/rc6 的 `app/live_caption_app.py` 来自 **rc4→rc3 一路「字符串补丁」打出的独立血脉**（**不是 dev 树快照**）⇒ 与 dev 树缺陷窗口无交集；rc7 走 dev 树定点覆盖 ⇒ 已含 `ba76ea5` 的搬移修复 | §170 ④「架构事实」＋ rc5 构建脚本 `results/app/_app310_build_minimvp_rc5.py`（`BASE_PKG=…-rc4` ⇒ `shutil.copytree` ⇒ `patch_live_caption_app()`） |
| 窗口内验收证据 | ① `app372_app091_subtitle_shot`（11-10 02:19，**在窗口内**）⇒ `{"shot": null, "caption_shots": [], "main_shots": []}` ⇒ **一张图都没产出**（正是空壳症状）；当时**未归因**，§164 只登记「未做」⇒ **属早期失败、非错误结论**｜② `app331_app093_gui_shot`（11-10 15:52，**也在窗口内**）⇒ `verdict=PASS` **成立且有效**（跑的是影子包 `after_fix_tmp`，已含 `_app334` 的搬移修复，**不是缺陷快照**）⇒ **窗口内没有任何 PASS 结论被污染** | `results/app/app372_app091_subtitle_shot/subtitle_layout.json`；`results/app/app331_app093_gui_shot.json` → `verdict`；§164 归档件第 31 行；§167 归档件 ① |

### ② 🔴 D2「asr06b 档位 label 撞车」⇒ **历史影响 = 已交付的 rc5 中招**（新发现，§170 未定位到 rc5）

| 项 | 结论 | 来源产物 / 字段 |
|---|---|---|
| 真正机制 | `kind=='asr06b'` 在引擎表里存在，但 `build_asr_options` 只比较 `kind=='cuda'`／`'npu'` ⇒ **asr06b 落入末尾「遍历所有设备」笛卡尔积分支** ⇒ 两个引擎档产出**同一条 label** ⇒ GUI 的 `_cur_asr_opt()` **靠 label 反查**（先命中先返回）⇒ 永远取第一条 ⇒ **静默错档**；且 NPU 档因循环内 `continue` 跳过 NPU ⇒ **NPU 档在 GUI 下拉里根本不存在** | `live_caption/live_caption_app.py` → `build_asr_options()`（rc7 内 736–753 行含修复版注释）＋ `_cur_asr_opt()`（3483–3489） |
| 判定方法 | **行为级**：把包内 `build_asr_options` 的**真实源码**抽出，在桩环境（`_model_path` 指向包内**真实** `models/`、`_asr_ir_ready=True`、`device_config` 打桩）里**真跑一遍** ⇒ 统计输出 label 是否重复 | `results/app/_app425_hist_scan3.py` → `run_build_asr_options()`；结果 `results/app/app425_hist_scan3.json` |
| **rc5** | 🔴 **BUG**：设备 `['GPU.0','NPU']` ⇒ 4 个选项，**重复 label = `['Intel GPU（集显） · INT8']`**（另含 2 个 CUDA 选项 `NVIDIA GPU（CUDA） · Q8_0`／`Q4_K`） | `app425_hist_scan3.json` → `packages[]`（rc5）＋ `zip_level.rc5` |
| **rc6** | 🔴 **BUG**：设备 `['GPU.0','NPU']` ⇒ 2 个选项，**两条 label 完全相同** | 同上（rc6） |
| **rc7** | ✅ **OK**：2 个选项 ⇒ `['Intel GPU（集显） · INT8', 'Intel NPU · INT8']`（label 全唯一） | 同上（rc7） |
| 其余 12 个包 | **NA**：ASR 引擎表里**无** `kind=='asr06b'` 条目（v1.13／v1.5／v2.0／v2.1／v2.2／v2.3／v2.4／MiniMVP v1.0／rc1／rc2／rc3／rc4）⇒ **与本缺陷无关** | 同上 → `summary.d2_na_packages` |
| **稳健性** | 两个设备口径（`['GPU.0','NPU']` 与 `['GPU.0','NPU','GPU.1']`）下 **rc5/rc6 均重复、rc7 均不重复** ⇒ 在本机真实配置（iGPU+NPU，APP-088）下同样成立 | 同上（`run_build_asr_options` 双口径复跑） |
| **zip 级复核** | 交付口径 =「zip 内含本轮代码」（看 mtime）⇒ 三个 zip 的 `app/live_caption_app.py` **单独抽出真跑**：rc5 zip（4 424 246 739 B／11-10 11:52:30／成员 418 478 B／**zip≡目录**）⇒ **BUG**｜rc6 zip（4 420 655 558 B／11-10 21:19:18／成员 475 504 B／**zip≡目录**）⇒ **BUG**｜rc7 zip（4 420 655 883 B／11-11 00:03:15／成员 476 874 B／**zip≡目录**）⇒ **OK** | `app425_hist_scan3.json` → `zip_level` |
| **dev 树 git 史** | `ENGINES_ASR06B` **只在 `4637861`（11-11 00:25）进过 dev 树**，且**同一提交里就带着修复** ⇒ dev 树从未出现「有缺陷无修复」的提交状态 ⇒ **本缺陷的全部历史载体就是 rc5／rc6 两个包** | `git log -S 'ENGINES_ASR06B' -- live_caption/live_caption_app.py` ⇒ 仅 `4637861`；`4637861`/`ba76ea5`/`377876f` 的 `asr06b` 计数 = 16／0／0 |
| **为何 rc5 验收没抓到** | rc5 设备验收（`_app312_rc5_device_acceptance.py::build_cmd`）走 `--cli` + 显式 `--engine`／`--asr-device` ⇒ **完全绕开 GUI 下拉与 label 反查** ⇒ 该缺陷对 rc5 的 CLI 验收**结构性不可见**；且磁盘上**无任何 rc5 GUI 截图产物** ⇒ **rc5 的 GUI 路径从未被验收过** | `results/app/_app312_rc5_device_acceptance.py` → `build_cmd()`（`--cli` 在参数表首位） |
| **交付影响** | 🔴 **rc5 已交付 reviewer**（§165，APP-096 验收通过并已 push）⇒ 该包 **GUI 的 ASR 档位存在静默错档**（**CLI 路径不受影响**）｜rc6 已登记「含缺陷、未交付」｜**rc7 已修**（唯一可交付的 MiniMVP 包） | §165 归档件（rc5 已出包＋验收）＋ §170 归档件 ⑨ |

### ③ 🔴 本轮把 D2 判据改了**三轮**才对（每版都有自身缺陷）——「闸门自己的判据也会是错的」又撞一次

* **v1 缺陷**：① 用 `ast.literal_eval` 读引擎表 ⇒ 真表的值是 `dict(...)` 调用 ⇒ 抛异常 ⇒ **表被读成空** ⇒ 假阴性（rc5/rc6 有缺陷被判 NA）；② 判据依赖表名 `ENGINES_ASR06B` ⇒ rc5 把 `kind='asr06b'` 直接写在 `ENGINES` 里 ⇒ **rc5 假阴性**。
* **v2 缺陷**：① 收集时**没只筛 asr06b** ⇒ 把所有 kind 都算命中 ⇒ **假阳性**（v1.13…rc4 全被判 BUG）；② 行为级执行时用**自己写的** `_model_path` 桩 ⇒ 没走 `_MODEL_ALIASES` ⇒ 0.6B 模型被误判「不在位」⇒ `active_asr_engines()` 走错引擎表。
* **v3 定案**：AST 直读引擎表（兼容 `dict(...)`／`{...}`）**只筛 `kind=='asr06b'`**；行为级执行时把 `__file__` 设成**包内真实路径** ⇒ `APP_DIR`/`PKG_ROOT`/`MODELS`/`_MODEL_ALIASES`/`_model_path` **全部取真实值** ⇒ 「0.6B 是否就位」成为**事实判定**。
* **反证组（判据有鉴别力）**：用 **AST 定位调用点**的定点手术把 rc7 的 `if cfg['kind'] == 'asr06b':` 换成 `if False:`（🔴 **用替换不用删行**：删行会掏空 `if` 块 ⇒ `SyntaxError` ⇒ 假 FAIL；🔴 **全文该串出现 2 次**，全文替换会误伤另一处）⇒ **完整 rc7 = OK（label 全唯一）／破坏后 = BUG（重复 `['Intel GPU（集显） · INT8','NVIDIA 独显 · INT8']`）** ⇒ **判据能识破「已知有缺陷」且不误报「已知已修」** ⇒ 结论可信。
* 判据文件：`results/app/_app425_hist_scan3.py`（定案版，含反证组＋zip 级复核）｜结果：`results/app/app425_hist_scan3.json`｜v1/v2/v3 前身也留档（`_app425_hist_impact.py`／`_app425_hist_scan.py`／`_app425_hist_scan2.py`）——**三版都有缺陷，留档以备复核**。

### ④ 🔴 本轮另记一个**新的运行风险**（非纠偏项）

* **C: 磁盘 100 % 占用，仅剩 17 G**（1.9 T）⇒ **下一次打包（v2.5 或新 MiniMVP 版）需约 10–15 G ⇒ 空间不足会直接失败**。
* 体量实测：`shared/minimvp` = **31 G**（6 个 zip：rc3 5.59 G／rc3_rev2 5.59 G／rc4 8.61 G／rc5 4.42 G／rc6 4.42 G／rc7 4.42 G）｜MiniMVP 目录 6.8+3.3+5.6+5.6+5.6 G｜真包 v1.13=13 G、v1.5=13 G、v2.4=3.1 G、`v2.4.zip`=11 G。
* 🔴 **本轮未删除任何文件**（删除交付物不在本轮授权内，且「任何旧版本目录和 zip 都不覆盖、不删除」是硬纪律）⇒ **请 reviewer / 用户决定清理哪些**。

### ⑤ 本轮未做 / 停下等 reviewer

* 🔴 **未打包 v2.5**（APP-055 + **用户级铁律：用户不通知 ⇒ 不主动打包**；且 GUI 布局缺陷的同步策略仍等 reviewer 裁定）。
* 🔴 **未修 rc5／rc6 的 D2 缺陷**：旧版本目录与 zip 一律不覆盖、不删除、不原地改 ⇒ 只能「打新版本号」⇒ 属打包动作 ⇒ 本轮不做。
* 🔴 **未通知用户、未调 MiniMax**（质量判定由 reviewer 回转写；目标机不调）。
* 🔴 **未改 §3.5 音色归属判据**（三人真值余弦 0.957–0.972 ⇒ 不可分 ⇒ 不自行换判据）；**未改 `_SEC_PER_CHAR` 默认值**（阈值取舍由 reviewer 报主会话请用户决定）。
* 🔴 **未改任何生产代码、未改任何客户包** ⇒ 本轮**只产出证据与定界结论**，零行为变更。
""".replace("{stamp}", STAMP)

# 🔴 APP-052④：STATUS 正文整块逐字归档 ⇒ STATUS 里只留速查摘要 + 归档指针
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec171_20261111.md')
ARCHIVE_BODY = FULL_BODY.replace("{stamp}", STAMP)


def write_archive():
    """把 §171 正文**整块逐字**写入归档件（write-once：已存在则不改）。"""
    if os.path.exists(ARCHIVE):
        raise RuntimeError('归档件已存在，拒绝覆盖：%s' % ARCHIVE)
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    data = ARCHIVE_BODY.encode('utf-8')
    with io.open(ARCHIVE, 'wb') as f:
        f.write(data)
    import hashlib
    return len(data), hashlib.sha256(data).hexdigest()


SUMMARY = """
## §171 巡检（last_ack=APP-098，{stamp}）｜**无新纠偏**；把 §170 ⑨ 两项「历史影响未评估」**定界完毕**（D1 零交付物受影响／**D2 影响已交付的 rc5**）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec171_20261111.md`（{nbytes} B／块 SHA256 `{sha}`）。
> 🔴 **速查**：**本轮无新 reviewer 纠偏**（`CORRECTIONS_APP.md` 仍 97 条／最大 APP-097，SHA `36af1620…`／285 671 B／mtime 11-10 11:49:26，开工＝收尾一致 ⇒ **SHA 零改动**；`last_ack` 已是 APP-098）｜**① D1（GUI 布局被吞）历史影响 = 零交付物受影响**：缺陷只在 dev 树的 **2 个 commit 快照**（`874924a`／`1cc86b2`）里，**15 个包逐个 AST 判定 0 中招**（含真包 v2.4 与 rc5/rc6/rc7）；窗口内 `app372` 截图全空（当时未归因）、`app331` 的 PASS 跑的是已修影子包 ⇒ **无 PASS 结论被污染**｜**② 🔴 D2（asr06b 档位 label 撞车）历史影响 = 已交付的 rc5 中招**（§170 未定位到 rc5）：**行为级判定**（把包内 `build_asr_options` 真源码在桩环境里**真跑一遍**统计 label 重复）⇒ **rc5 = BUG**（`Intel GPU（集显） · INT8` 重复）／**rc6 = BUG**（两条 label 完全相同）／**rc7 = OK**（`Intel GPU（集显） · INT8` + `Intel NPU · INT8`）／**其余 12 包 = NA**（无 0.6B 档）；**双设备口径稳健**（`GPU.0+NPU` 与 `GPU.0+NPU+GPU.1` 均同）；**zip 级复核同结论**（rc5/rc6/rc7 三个 zip 的 `app_py` 单独抽出真跑，且 **zip ≡ 目录**）；**dev 树 git 史**：`ENGINES_ASR06B` 只在 `4637861` 进过 dev 树且**同一提交即带修复** ⇒ **历史载体只有 rc5/rc6 两个包**；**rc5 为何没抓到** ⇒ 其验收走 `--cli` + 显式 `--engine` ⇒ **绕开 GUI 下拉**，且**磁盘无任何 rc5 GUI 截图** ⇒ GUI 路径从未验收｜**③ 🔴 D2 判据改了三轮才对**（v1 `literal_eval` 读表失败 ⇒ 假阴性；v2 未只筛 asr06b ⇒ 假阳性；v3 定案＝AST 直读 + `__file__` 指向包内真实路径 ⇒ 模型就位成为事实判定）＋**反证组**（AST 定位把 rc7 的 asr06b 分支换成 `if False:` ⇒ OK→BUG）⇒ **判据有鉴别力**｜**④ 新风险：C 盘 100 %、仅剩 17 G** ⇒ 下次打包空间不足（**本轮未删任何文件**）｜**未打包 v2.5、未改生产代码、未改客户包、未通知用户、未调 MiniMax**。
> 🔴 **证据**：`results/app/app425_hist_scan3.json`（15 包 + 71 commit + zip 级 + 反证组）／`app425_hist_impact_final.json`（定界结论）／`_app425_hist_scan3.py`（定案判据，v1/v2 前身亦留档）／`_app426_write_status171.py`。
"""



def main():
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        orig = f.read()
    assert '\r\n' not in orig, 'STATUS 不是 LF，拒绝写入（避免行尾被破）'
    orig_lines = orig.split('\n')

    # —— 头部定点替换：只动「更新时间」与「当前任务」两行 ——
    head_ts = '更新时间: 2026-11-11 00:24:37'
    assert orig.count(head_ts) == 1, '更新时间锚点不唯一'
    new_ts = '更新时间: ' + STAMP
    out = orig.replace(head_ts, new_ts)

    # 当前任务行（第 5 行整行替换）
    lines = out.split('\n')
    idx = next(i for i, l in enumerate(lines) if l.startswith('当前任务:'))
    old_task_line = lines[idx]          # 🔴 先存**旧值**，供写后复核用
    lines[idx] = ('当前任务: **巡检无新纠偏**（`last_ack=APP-098`；纠偏文件仍是 97 条 / 最大 APP-097 '
                  '⇒ 无编号更大的新条目）｜**本轮把 §170 ⑨ 两项「历史影响未评估」定界完毕**：'
                  '**D1（GUI 布局被吞）历史影响 = 零交付物受影响**（缺陷只在 dev 树的 2 个 commit 快照里，'
                  '15 个包逐个 AST 判定 0 中招；窗口内 PASS 结论也未被污染）｜'
                  '**D2（asr06b 档位 label 撞车）历史影响 = 已交付的 rc5 中招**（rc5/rc6 GUI 静默错档；'
                  'rc7 已修；其余 12 包 NA；zip 级复核一致）｜**D2 判据改了三轮才对**（v1 假阴性／v2 假阳性／v3 定案，'
                  '带反证组）｜**新风险：C 盘 100 %、仅剩 17 G ⇒ 下次打包空间不足**（本轮未删任何文件）｜'
                  '**未打包 v2.5、未改生产代码、未改客户包、未通知用户、未调 MiniMax**｜结果见 §171｜**本条需等 reviewer 复核**')
    out = '\n'.join(lines)

    # —— 归档 §171 正文（write-once）⇒ 拿到字节数与块 SHA ——
    nbytes, sha = write_archive()

    # —— 追加 §171 速查摘要（正文已整块归档）——
    assert out.endswith('\n')
    out = out + SUMMARY.replace("{stamp}", STAMP).replace(
        "{nbytes}", str(nbytes)).replace("{sha}", sha).lstrip('\n')

    # —— 写临时文件 ⇒ **先在临时文件上做完所有复核** ⇒ 通过才原子替换 ——
    tmp = STATUS + '.tmp_app426'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)

    # —— 复核（在临时文件上做；不通过就删临时文件、**原文件保持不动**）——
    with io.open(tmp, 'r', encoding='utf-8', newline='') as f:
        now = f.read()
    try:
        assert '\r\n' not in now, '行尾被破'
        assert '## §171' in now, '新节未命中'
        assert now.count('## §171') == 1, '新节重复'
        idx171 = now.index('## §171')
        assert now[idx171:].rstrip('\n').startswith('## §171 巡检'), '新节内容异常'
        now_lines = now.split('\n')
        changed_header = {head_ts, old_task_line}
        missing = [l for l in orig_lines
                   if l and l not in now_lines and l not in changed_header]
        assert not missing, '旧正文有行丢失：%r' % missing[:3]
        assert head_ts not in now_lines, '旧的更新时间仍在'
        assert new_ts in now_lines, '新的更新时间未写入'
        # 限额（APP-052④）：≤40000 B / ≤300 行
        nbytes = len(now.encode('utf-8'))
        nlines = len(now_lines)
        assert nbytes <= 40000, '超字节限额：%d' % nbytes
        assert nlines <= 300, '超行数限额：%d' % nlines
    except AssertionError:
        os.remove(tmp)
        if os.path.exists(ARCHIVE):
            os.remove(ARCHIVE)          # 🔴 回滚归档件 ⇒ 磁盘保持一致
        print('!! 复核未通过 ⇒ 已删除临时文件并回滚归档件，原 STATUS 保持不动')
        raise

    shutil.move(tmp, STATUS)

    print('WROTE %s' % STATUS)
    print('bytes: %d -> %d' % (len(orig.encode('utf-8')), nbytes))
    print('lines: %d -> %d' % (len(orig_lines), nlines))
    print('section_171_present: True')


if __name__ == '__main__':
    main()
