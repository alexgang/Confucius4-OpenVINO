#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app561_write_status_sec204.py —— 写 STATUS §204（append-only）＋ 归档 §203。

纪律（全部 fail-closed：**任何自检不过 ⇒ 零写入**）：
  · 只**追加** `## §N` 章节，不回头改旧章节；旧结论错了在新章节里写「撤回 §x」；
  · `last_ack` 无新纠偏 ⇒ **保持 APP-109**（不写自己的编号）；
  · 「更新时间」用 **Get-Date 实测值**（由调用方传入）；
  · 压缩：把 §203 正文**整块逐字归档**，活文档保留 §203 **标题行** ＋ 1 行指针；
  · **还原式复核**：把本轮**所有**增量（新增章节 ＋ 新插入行 ＋ 指针行 ＋ 头部
    时间戳行）**逐一逆向还原** ⇒ 必须与开工备份**逐字节相同**；
  · 上限 **40 000 B／300 行**（APP-052④）、纯 LF、无 BOM。
"""
import datetime
import hashlib
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec203_20261114.md')
TS = sys.argv[1] if len(sys.argv) > 1 else '2026-11-14 19:38:17'
MAXB, MAXL = 40000, 300

base = open(STATUS, 'rb').read()
assert b'\r' not in base, '开工文件含 CR（行尾不是纯 LF）'
assert base[:3] != b'\xef\xbb\xbf', '开工文件有 BOM'
base_txt = base.decode('utf-8')

# ── 定位 §203（应是最后一节）──
i203 = base_txt.index('## §203 ')
sec203 = base_txt[i203:]                      # 标题行 ＋ 正文，到 EOF
title203 = sec203.split('\n')[0]
assert base_txt.count(title203) == 1, '§203 标题行不唯一'
assert sec203.rstrip('\n').endswith('⑫') or '⑫' in sec203, '§203 不是最后一节'

# ── 归档件正文块（含标题行）──
block203 = sec203.rstrip('\n')
sha203 = hashlib.sha256(block203.encode('utf-8')).hexdigest()
arch = (
    '# STATUS_APP §203 整块逐字归档（2026-11-14）\n'
    '\n'
    '归档时间：%s\n'
    '归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §204 出空间。\n'
    '正文一字未删（标题行仍留在活文档）。\n'
    '\n'
    '§203 正文块 SHA256（含标题行）：%s（%d B）\n'
    '\n'
    '---- 以下为 §203 原文，逐字 ----\n'
    % (TS, sha203, len(block203.encode('utf-8')))
) + block203 + '\n'

# ── §204 正文 ──
SEC204 = """## §204 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-109**）｜🔴 **修掉交付闸门真缺陷：Special MVP 打 zip 的闸门可被架空**（拿 sp1 的验收结论放行 sp2）｜**参数化＋闸门重写，鉴别力矩阵 6/6 PASS**｜**未打包／未改客户包／未改产品代码**｜**本条需等 reviewer 复核**
> **① 纠偏文件复核（只读、未改、未入库、未提交）**：开工＝收尾 **109 条**／最大 **APP-109**／SHA256 `30a55189…`／**360 842 B**／mtime **2026-11-14 15:38:28** ⇒ **逐字一致 ⇒ SHA 零改动**；`last_ack` **仍 APP-109**（无新纠偏 ⇒ **不写自己的编号**）⇒ **本轮无新条目可执行**。
> **② 其它 5 通道全空**：agent-mail **`not_bound`**（**连续第 7 轮**不可查）｜`conversation_search`（11-14）**0 命中**｜`shared/NOTICE*` 最新仍 **11-05 09:35**（仓库内 `NOTICE*` 0 个）｜git `origin/main...main`＝**0/0**（HEAD `e1cfa6f`）｜`MACHINE_LOCK` **NOT_PRESENT**｜ASR 侧 **27 条／最大 ASR-058**（**无 App 条目**）｜根 `status/CORRECTIONS.md` 最大 **C-135**（10-24）。
> **③【🔴 实质发现（交付闸门层真缺陷）：`results/app/_app537_zip_specialmvp.py` 的验收闸门可被架空 —— 拿 sp1 的验收结论放行 sp2】**：该脚本把 `PKG_NAME`／`DST_PKG`／`ZIP`／`ACCEPT`／`REPORT` **全写死成 sp1**（改前 L20–L25）⇒ 给 sp2 打 zip **必须改源码**，而**最易漏改的恰是 `ACCEPT`（验收证据）**。**实测两种走向**：**T4**「只改 `PKG_NAME`、`ACCEPT` 仍指 sp1」⇒ 闸门 **ALLOW（放行）** ⇒ **fail-open**：**sp2 的 zip 可在从未验证过 sp2 的情况下被打出来**；**T3**「正确指向 sp2 自己的证据」⇒ 闸门 **BLOCK** ⇒ **假 FAIL**：根因是判据用**精确字符串** `verdict != 'PASS'`，而 reviewer 在 §202 ④ 明文规定的口径是 **「PASS（有 1 项未结：退出码异常）」**（未结项单列 `open_issues`、**不并入** PASS 判定）⇒ **两条路都不通**：自己的证据放行不了，误用别人的证据反而能放行。
> **④ 修法（只改交付脚本；产品代码零改动、客户包零改动）**：① **参数化** `--pkg-name`／`--accept`／`--report`／`--zip`／`--check-only`（**sp1 默认行为逐字不变**）② **闸门重写** `check_acceptance`：证据**存在** ＋ 证据的 `pkg` **必须属于正在打包的那个包** ＋ verdict 接受 §202 口径的 `PASS` 与 `PASS（…）`，其它写法一律拒绝 ③ **新增版本标识自洽检查** `check_release_identity`（`release.json.version` ＝ 目录名版本后缀）④ `os.remove(tmp)` 失败改为**明确报错**（本机安全删除 shim 会把删除转回收站并可能失败 ⇒ 原先是「带着半成品包死掉 ＋ 磁盘留 13 GiB 临时文件」）⑤ `--check-only`：**只跑闸门、零写入**。
> **⑤【鉴别力矩阵 `app560`，6 行端到端 ＋ 2 项单元级反证 ⇒ verdict PASS】**：**改前行为取自 `git cat-file blob HEAD:` 原文**（只改三处常量 ＋ 打包前插 `raise SystemExit(0)` 截断 ⇒ **闸门逐字按原样执行、绝不真打 zip/改 README**）；**改后直接跑已修好的脚本**（`--check-only` ⇒ 零写入）。**T1** sp1＋sp1 自己的证据 ⇒ 两边都 ALLOW（**回归护栏**）｜**T2** sp1＋sp2 的证据 ⇒ 两边都 BLOCK（改后原因＝`PKG_MISMATCH`）｜**T3** sp2＋sp2 自己的证据 ⇒ 改前 **BLOCK（假 FAIL）** → 改后 **ALLOW**｜**T4** sp2＋sp1 的证据 ⇒ 改前 **ALLOW（fail-open）** → 改后 **BLOCK**｜**T5** 缺证据 ⇒ 两边都 BLOCK｜**T6** `verdict=FAIL` ⇒ 两边都 BLOCK。**单元级**（`ast` 抽函数单独 exec，避开模块级副作用）：`release.json` 版本**匹配⇒允许／不匹配⇒拒绝**（用**临时假包**，**未触碰真实客户包**）；**真实 sp1／sp2 自洽检查均 PASS**（`1.0-sp1`／`1.0-sp2`）。
> **⑥【形态差异（供 reviewer 参考，本轮未改任何判据）】**：`app/MANIFEST.json` **只有完整版有 `version`**（v2.1＝`2.1`）；**MiniMVP rc11／SpecialMVP sp1／sp2 都没有** ⇒ 这两种形态的版本标识**只**落在 `release.json` ⇒ `pack_v13.py` 闸门②（版本标识一致）**不能直接复用**到这两种形态。
> **⑦【客户包与交付物零改动（实测）】**：**sp1** 41 374 文件／14 232 025 413 B，最新 mtime **11-13 21:25**；**sp2** 41 374 文件／14 232 031 341 B，最新 mtime **11-14 16:40**（§202 ⑤ 同步的 `app/tts_worker.py`）⇒ **本轮（19:3x）零写入**；`shared/specialmvp/` 仍只有 **sp1 zip（14 244 490 059 B）＋ 交付说明**，**无新 tmp／无新 zip**；**完整版 v2.5 仍未打包**。
> **⑧【证据（字节／mtime／SHA256）】**：`results/app/app560_specialmvp_zip_gate_matrix.json`＝**5 476 B**／mtime **2026-11-14 19:37:31**／SHA256 `6429614e…`（`verdict=PASS`、`summary.new_failures=[]`、`discriminators=[T3,T4]`、`writes_to_customer_pkg=0`）；修好的脚本 `results/app/_app537_zip_specialmvp.py`＝**14 063 B**／mtime **2026-11-14 19:36:40**／SHA256 `02b24fd1…`（改前 **7 172 B**／SHA `751d7ed0…`）；反证脚本 `results/app/_app560_specialmvp_zip_gate_matrix.py`＝**11 584 B**／SHA256 `cfedd4a0…`。
> **⑨【纪律】**：**未打包**（sp2 仍无 zip；**用户不通知不打包**）｜**未改客户包**（21 个包目录全部只读）｜**未改产品代码**（`live_caption/`、`pack_v13.py` **零改动**；唯一改动＝**交付脚本**）｜**未改 `CORRECTIONS_APP.md`**（只读、未入库、未提交）｜未跑推理 ⇒ **未取 `MACHINE_LOCK`**｜未调 MiniMax｜未动 B 机文件｜**逐文件** `git add`（未用 `-A`），**未吞**其它模块 **746** 条脏改动。
> **⑩【压缩（APP-052④ 上限 40 000 B／300 行）】**：**§203 正文整块逐字归档** ⇒ `status/archive/STATUS_APP_sec203_20261114.md`（块 SHA256 见该文件末）⇒ 活文档保留 §203 标题行 ＋ 1 行指针。
> **⑪ 本条需等 reviewer 复核**：① §204 ③ 的 fail-open 定性是否认可 ② §204 ④ 的闸门重写（**证据必须属于本包** ＋ **verdict 接受 `PASS（…）`**）是否认可 ③ `release.json` 自洽检查是否认可 ④ §204 ⑥ 是否需**另立闸门** ⑤ 沿用未变：**sp2 的 zip**（须**用户通知**）／§194 ④ 的 `tag` 三分支／**TTS 是否默认不丢句**（6.0→0）／**OPEN-1**（0xC0000409）／10 个缺陷包作废还是标注／**完整版 v2.5 何时打**（必须带收窄）／EXT 换嵌通知／目标机 SHA256 对账（需**开机＋凭据**）。
> **⑫【与 APP-085 §2「待命期不新增 § 章节／不归档／不 commit」的偏离 —— 如实申报】**：本轮**确实无新纠偏**，但产出**一项可复算的交付闸门层真缺陷**（③ fail-open ＋ 假 FAIL）及其**修法与鉴别力矩阵** ⇒ 按任务口径写入本节并按 40 000 B 限额归档 §203 ⇒ **本轮新增 § 章节 1 节（§204）／归档件 1 个**；**未打包**、**未改客户包**、**未改产品代码**。
"""

POINTER203 = ('> 🔴 **本节正文已整块逐字归档** ⇒ '
              '`status/archive/STATUS_APP_sec203_20261114.md`'
              '（块 SHA256 `%s`）；活文档保留 §203 标题行 ＋ 1 行指针。'
              % sha203)

RECENT = ('> 🔴 %s ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-109）**：'
          '6 通道全查空（`CORRECTIONS_APP.md` 109 条/APP-109 逐字未变、'
          'agent-mail 仍 `not_bound`、`conversation_search` 0 命中、'
          '`NOTICE` 最新 11-05、git 0/0、`MACHINE_LOCK` 无）｜'
          '🔴 **修掉交付闸门真缺陷：Special MVP 打 zip 的闸门可被架空**'
          '（脚本把 `ACCEPT` 写死成 sp1 ⇒ 拿 sp1 的验收结论放行 sp2；'
          '且 verdict 精确字符串比较使 sp2 自己的证据反被拒）｜'
          '**参数化＋闸门重写，鉴别力矩阵 6/6 PASS**｜'
          '**未打包／未改客户包／未改产品代码**\n' % TS)

# ── 组装新内容 ──
new = base_txt
# (a) 头部时间戳行
old_ts_line = [l for l in new.split('\n') if l.startswith('更新时间: ')]
assert len(old_ts_line) == 1, '头部「更新时间」行不唯一'
new = new.replace(old_ts_line[0], '更新时间: ' + TS)
# (b) 「最近更新」条目插在标题之后第一行
ru = '## 最近更新\n'
assert new.count(ru) == 1, '「## 最近更新」标题不唯一'
new = new.replace(ru, ru + RECENT)
# (c) §203 正文整块 → 指针行
assert new.count(sec203) == 1, '§203 块定位失败'
new = new.replace(sec203, title203 + '\n\n' + POINTER203 + '\n')
# (d) 追加 §204
new = new.rstrip('\n') + '\n\n' + SEC204

nb = new.encode('utf-8')
nl = nb.count(b'\n')
checks = [
    ('字节上限', len(nb) <= MAXB, '%d B（上限 %d）' % (len(nb), MAXB)),
    ('行数上限', nl <= MAXL, '%d 行（上限 %d）' % (nl, MAXL)),
    ('纯 LF', b'\r' not in nb, 'CR=%d' % nb.count(b'\r')),
    ('无 BOM', nb[:3] != b'\xef\xbb\xbf', ''),
    ('§203 标题行仍在且唯一', new.count(title203) == 1, ''),
    ('§204 为最后一节', new.rstrip('\n').rfind('## §204 ') > new.rstrip('\n').rfind('## §203 '), ''),
    ('最近更新条目在标题后', new.split(ru)[1].split('\n')[0].startswith('> 🔴 %s' % TS), ''),
    ('归档块与开工逐字节一致', block203.encode('utf-8') in arch.encode('utf-8'), ''),
]

# ── 还原式复核：逐一逆向还原本轮**所有**增量 ──
rest = new
# 去掉新增的 §204 章节**连同它前面的 "\n\n" 分隔符**（只切到 '## §204 ' 会
# 留下一个多余的换行 ⇒ 还原后比开工多 1 B ⇒ 假 FAIL，已踩过一次）
cut = rest.rindex('\n\n## §204 ')
rest = rest[:cut] + '\n'
rest = rest.replace(title203 + '\n\n' + POINTER203 + '\n', sec203)
rest = rest.replace(ru + RECENT, ru)                   # 去掉新插入的最近更新行
rest = rest.replace('更新时间: ' + TS, old_ts_line[0])  # 退回头部时间戳
checks.append(('还原式复核（逐字节回到开工）', rest == base_txt,
               '还原后 %d B vs 开工 %d B' % (len(rest.encode('utf-8')), len(base))))

ok = all(c[1] for c in checks)
for name, good, extra in checks:
    print(('  [OK] ' if good else '  [FAIL] ') + name + ('  ' + extra if extra else ''))
if not ok:
    print('\n🔴 自检未全过 ⇒ **零写入**，中止。')
    raise SystemExit(1)

# ── 落盘（**原子写**：先写临时文件再 os.replace）──
# 🔴 教训（已踩）：`open(path, 'w')` **先截断再写** ⇒ 写失败 ⇒ 文件变成 **0 B**
#    （本轮真的发生过：39 598 B → 0 B，靠开工前的备份逐字节还原回 HEAD）。
#    ⇒ 一律「写临时文件 → os.replace」；归档件 **write-once**（已存在则只校验）。
def atomic_write(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(data)
    os.replace(tmp, path)


os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
if os.path.isfile(ARCHIVE):
    # write-once：已存在则**只校验**其 §203 块与开工一致，不重写
    old_arch = open(ARCHIVE, encoding='utf-8').read()
    assert block203 in old_arch, '已存在的归档件与开工 §203 块不一致 ⇒ 中止'
    arch_action = '已存在（write-once，只校验未重写）'
else:
    atomic_write(ARCHIVE, arch)
    arch_action = '新写入'
atomic_write(STATUS, nb.decode('utf-8'))
# 写后自检：落盘内容必须与内存内容逐字节相同
assert open(STATUS, 'rb').read() == nb, '落盘后校验失败（文件与内存不一致）'
print('\n✅ 已写入：')
print('  STATUS_APP.md          %d B / %d 行（开工 %d B）' % (len(nb), nl, len(base)))
print('  §203 归档块 SHA256     %s（%d B）' % (sha203, len(block203.encode('utf-8'))))
print('  归档件 %s  %d B（%s）' % (os.path.relpath(ARCHIVE, REPO),
                                   len(arch.encode('utf-8')), arch_action))
print('  last_ack 保持          APP-109（无新纠偏）')
print('  更新时间               %s' % TS)
