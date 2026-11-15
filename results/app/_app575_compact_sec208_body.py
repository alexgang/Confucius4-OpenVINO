#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app575 —— 把 `_app573_write_status_sec208.py` 里的 `SEC208_BODY` **逐行压紧**。

🔴 **为什么**：活文档限额 **40 000 B**（APP-052④）⇒ §208 的活文档正文必须压到
   ~4.1 kB（**完整正文在 companion**，活文档只留摘要 —— 与 §207 同一做法）。

🔴 **做法**：**按行首标记**（`> **①` … `> **⑫` ＋ 指针行）定位并整行替换
   ⇒ 不依赖长字符串精确匹配 ⇒ 不会因为一个字符差异整块失败。
   每次替换都断言「命中 1 次」⇒ 命中 0 次 ⇒ fail-closed 零写入。
   ⚠️ 首行与赋值语句同行（`SEC208_BODY = r'''> ...`）⇒ **只替换引号之后的部分**。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, '_app573_write_status_sec208.py')

NEW = {
 'ptr': '> 🔴 **完整正文**（证据字段／矩阵全表／反证组／逐条理由）见 **companion** ⇒ `status/app/STATUS_APP_sec208_detail_20261115.md`（正文块 **{cbytes} B**／SHA256 `{csha}`）⇒ 活文档只留摘要（限额 **40 000 B**）。',
 '1': '> **① 纠偏文件复核（只读、未改、未入库、未提交）**：开工＝收尾**逐字一致** ⇒ SHA256 `30a55189…`／**360 842 B**／mtime **11-14 15:38:28**／**109 条**／最大 **APP-109** ⇒ **SHA 零改动**；`last_ack` **仍 APP-109**。**② 其它 5 通道全空**：agent-mail 工具层仍 **`not_bound`**（**第 11 轮** ⇒ **查不了**，不是「查了为空」）｜`conversation_search` **0**｜`NOTICE` **11-05 09:35**｜git **0/0**（HEAD `39c503a`）｜ASR 最大 **ASR-058**（无 App 条目）｜根 **C-135**；全盘扫 11-15 09:00 后仓库内**只有我自己的改动** ⇒ reviewer 未产出新文件；**`MACHINE_LOCK` 全程 NOT_PRESENT**。',
 '3': '> **③【真缺陷（闸门层 · 完整版形态）】**`pack_v13.py`（=**v2.5 要用的脚本**）**全程零验收绑定**：`ACCEPTED.json` 全仓**只有 `shortcut_update.py` 读**（且在 **zip 写完之后**才跑）；会查漂移的 `app191_acceptance_code_binding_gate.py` **从未被调用** ⇒ **验收证据不参与出包决策 ⇒ 验收后改包照样能出包**。§204–§207 只审过 Special MVP／MiniMVP ⇒ **完整版从未被审过**。',
 '4': '> **④【鉴别力矩阵 `app571`，15/15 PASS（12 矩阵 ＋ 3 反证组）】**改前臂＝`git cat-file blob HEAD:pack_v13.py` 逐字原文、改后臂＝工作区；两臂**同款桩**、在**临时假包**上**真跑 `_run()`**，观测口径＝**真的产出了 zip 没有** ⇒ **改前 4 臂全 fail-open**（T1 无 ACCEPTED／T2 版本不符／T3 验收后改一字 ⇒ rc=0 **且真的产出 zip**），改后 ⇒ **rc=1、0 字节 zip**；T4 合法包两臂都出包且 md5 相同；**AST 直读表**证实改前臂**全文件**无函数读 `ACCEPTED.json`；**反证组 3/3**。',
 '5': '> **⑤【修法（只改交付脚本 `pack_v13.py`；产品代码零改动）】**新增**打包前闸门⑤** `check_acceptance_binding()`：**身份绑定**（`NO_ACCEPTED`／`NOT_ACCEPTED`／`VERSION_MISMATCH`／`PKG_MISMATCH`）＋ **内容绑定**（`NO_CONTENT_BINDING`／`CONTENT_MISMATCH`／`CONTENT_SET_MISMATCH`／聚合指纹兜底），**两层都 fail-closed**；接在闸门④之后、`do_dry_run` 之前 ⇒ `--dry-run` 也反映真实可打性；另加 `acceptance_gate_selftest()`（9 臂反证自测，随脚本走）＋ CLI `--self-test-acceptance`（**目录改名前**早退 ⇒ 不吃版本号）。',
 '6': '> **⑥【绑定范围：复用既有格式，验收侧一字不改】**绑定范围＝包内 `app/` **生产模块**（`.py`，排除 dev-only）⇒ 与 **app191 口径一致** ⇒ 直接复用既有 `ACCEPTED.json` 的 `code_fingerprints`／`code_fingerprint` ⇒ **不动验收侧脚本**；⚠️ README／NOTICE／MANIFEST.json **不在范围内**（打包会重写 ⇒ 字节必不同）。**⑦【真包零漂移 ⇒ 交付物未受损（如实记录，不夸大）】**真 v2.1／v2.2／v2.4 指纹与当前包内容**逐模块一致**（28/28、28/28、29/29）⇒ 本缺陷是**闸门层潜在 fail-open**，**不是**已发生的交付污染；真包**只读**判定 **PASS**（非假 FAIL），变异只在**临时副本**上做 ⇒ 真包**零写入**。',
 '8': '> **⑧【证据】**`app571_ful_version_acceptance_gate_matrix.json`＝**10 956 B**／**10:17:14**／`9777ec82…`（`n_pass=15`／`n_fail=0`）；修好的 `pack_v13.py`＝**111 670 B**／**diff 258 插入 0 删除**（纯增量）／**纯 CRLF、无裸 LF、无 BOM**。',
 '9': '> **⑨【回答 §207 ⑪④：`_app500`（rc10 模板）**不**改】**① rc10 的 zip **已交付且已复核** ⇒ 改历史脚本不能改变已交付物；② APP-055 禁止重打包 ⇒ rc10 不会重建；③ **反而有害**：搬进 `_app500` ⇒「重跑 rc10 构建」会被挡死（同 §207 ⑧ `NO_CONTENT_BINDING`）。**改为保证缺陷不再继承**：rc12 应复制 **rc11 的 `_app524`（已修）**，其内置 `acceptance_gate_selftest` ⇒ **自测跟着走**。🔴 请确认该链向约定。',
 '10': '> **⑩【纪律】****未打包**（sp2 仍无 zip；用户不通知不打包）｜**零客户包写入**（21 个包目录写入 0 文件）｜**未改产品代码**（`live_caption/` 零改动）｜**未改 `CORRECTIONS_APP.md`**｜未跑推理 ⇒ 未取 `MACHINE_LOCK`｜未调 MiniMax｜**逐文件** `git add`。**⑫【偏离如实申报】**本轮**确实无新纠偏**，但产出**一项可复算的交付闸门层真缺陷**及修法、矩阵与反证组 ⇒ 写入本节并按限额**归档 §207**（整块逐字）⇒ 新增 § 章节 1 节／归档件 1 个／companion 1 个／客户包写入 0 文件／未打包。',
 '11': '> **⑪ 本条需等 reviewer 复核**：① 「完整版从未被审过／闸门层 fail-open」定性 ② 闸门⑤改法 ③ 绑定范围 ④ **`_app500` 不改** ＋ 链向约定 ⑤ **闸门⑤会拦「合法但未重签 ACCEPTED」的包** ⇒ 是否留出口（`--allow-unaccepted`）**请裁定** ⑥ 沿用未变：sp2 的 zip／§194 ④ `tag`／TTS 默认不丢句／OPEN-1／10 个缺陷包／**v2.5 何时打**（必须带收窄）／EXT 换嵌／目标机 SHA256 对账／§206 ⑨③ `cuda_env` 范围。',
 '7': '',
 '12': '',
}

MARK = {
 # 🔴 锚点**不含 emoji**（shell/编码会把 emoji 弄成两个码位 ⇒ 匹配恒 0）
 'ptr': '**完整正文**（全部证据字段',
 '1': '**① 纠偏文件复核',
 '3': '**③【真缺陷',
 '4': '**④【鉴别力矩阵',
 '5': '**⑤【修法',
 '6': '**⑥【绑定范围',
 '7': '**⑦【真包零漂移',
 '8': '**⑧【证据】',
 '9': '**⑨【回答',
 '10': '**⑩【纪律】',
 '11': '**⑪ 本条需等 reviewer 复核',
 '7': '**⑦【真包零漂移',
 '12': '**⑫【偏离如实申报】',
}


def main():
    with open(TARGET, 'rb') as f:
        orig = f.read()
    text = orig.decode('utf-8')
    lines = text.split('\n')
    hits = 0
    for i, line in enumerate(lines):
        for key, mark in MARK.items():
            # 🔴 用 `in` 而不是 `startswith`：部分行**以 `> 🔴 ` 开头**，
            #    标记串不在行首（emoji 锚点也不可靠）⇒ 用「唯一子串」判定。
            if mark in line:
                pre = ''
                rest = line
                # 🔴 首行可能与赋值语句同行（`SEC208_BODY = r'''> ...`）
                #    ⇒ **只替换引号之后的部分**，否则会把开引号一起弄掉
                mq = re.match(r"^(\s*SEC208_BODY\s*=\s*r''')(.*)$", line)
                if mq:
                    pre, rest = mq.group(1), mq.group(2)
                if rest.strip() != NEW[key].strip():
                    lines[i] = pre + NEW[key]
                hits += 1
                break
    if hits != len(MARK):
        print('!! FAIL-CLOSED：命中 %d 行（应 %d）⇒ 零写入'
              % (hits, len(MARK)))
        return 1
    new = '\n'.join(lines).encode('utf-8')
    if new == orig:
        print('[skip] 内容未变')
        return 0
    d = os.path.dirname(TARGET)
    fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
    os.close(fd)
    with open(tmp, 'wb') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, TARGET)
    m_new = re.search(r"SEC208_BODY = r'''(.*?)'''", new.decode('utf-8'), re.S)
    m_old = re.search(r"SEC208_BODY = r'''(.*?)'''", orig.decode('utf-8'), re.S)
    print('[ok] 压紧 %d 行｜body %d B ⇒ %d B'
          % (hits, len(m_old.group(1).encode('utf-8')),
             len(m_new.group(1).encode('utf-8'))))
    print('[ok] 文件 %d B ⇒ %d B｜sha %s'
          % (len(orig), len(new), hashlib.sha256(new).hexdigest()[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
