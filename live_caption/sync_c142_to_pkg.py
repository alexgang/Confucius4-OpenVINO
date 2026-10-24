#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c142_to_pkg.py — 把「TTS 错误隔离修复」同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包，C-133 教训）；
- **替换后必须与仓库版逐字一致（归一化换行）才写盘**。

## 要同步的变更

### ① `app/tts_service.py` —— **句子级 error 误杀整个服务**（2026-10-24 §22）

`TTSService._handle_event()` 把 worker 发来的 `kind=='error'` **一律**当成
「worker 整体挂了」⇒ `self.state = 'error'`。

但 worker 的 `error` 事件有**两类**：
- **句子级**（带 `'id': jid`）：这一句合成失败 / 播放缓冲写满 / 播放写入失败；
- **worker 级**（**不带** `'id'`）：模型加载失败 / 播放设备打开失败。

⇒ 旧实现让**一句话失败就杀死整个会话的语音输出**，后果三条：
1. `active` 变 False ⇒ CLI `if tts.active: tts.submit(...)` **从此不再提交**；
   GUI 的 `submit()` 里 `ready = (state=='ready')` 为 False ⇒ 命令进 `_queue`
   ⇒ `_flush_queue()` **只在 ready 事件时调用** ⇒ 永远不发出去 ⇒ **一声不响**；
2. `pending[jid]` **永不清除**（该路径上 worker 不发 `played`）
   ⇒ `drain()` 必定超时（GUI 白等 30 s / CLI 白等 120 s）；
3. `_queue` **无上限** ⇒ 内存无界增长。

修法：**按有没有 `id` 区分** —— 带 `id` ⇒ 只清这一句 + 计丢句 + **服务继续**；
不带 `id` ⇒ 维持原语义（判死）。另加 `_inflight` 集合，
worker 崩溃时把在途句子清掉并计丢句（否则 `drain()` 必超时）。

### ② `app/tts_worker.py` —— 两处**句子级** error 补上 `'id': jid`

`tts_worker.py` 的「没有可用的音色」两处 `emit({'kind':'error', ...})`
**丢了句子身份** ⇒ 主进程无法区分两类错误 ⇒ 修 ① 无从生效。

## 实测证据（见 `results/app/`）

- `test_tts_error_isolation.py` ⇒ 修复前 **8 项 FAIL**（state=error / pending 悬挂 /
  drain 超时 20 s / `_queue` 增长 20）；修复后 **19/19 PASS**（drain 0.0 s）；
- `test_tts_stderr.py`（§20）⇒ **9/9 PASS**（未受影响）；
- `test_tts_restart_regression.py`（§21）⇒ **9/9 PASS**（未受影响）；
- `test_tts_close_orphan.py`（§21）⇒ **PASS，无孤儿**（未受影响）；
- `test_tts_restart_nop.py`（§21）⇒ **PASS**（未受影响）。

## 用法
    python live_caption/sync_c142_to_pkg.py            # 执行
    python live_caption/sync_c142_to_pkg.py --check    # 只校验不写
    python live_caption/sync_c142_to_pkg.py --report <报告输出路径>
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
FILES = ['tts_service.py', 'tts_worker.py']

# ── 定点替换清单：(标签, 文件, OLD, NEW) ─────────────────────────────
# 每条 OLD 都必须在包内**唯一命中**（assert count == 1）才允许替换。

PATCHES = [
    (
        'P1-service-inflight-init',
        'tts_service.py',
        """        self.pending: 'OrderedDict[int, dict]' = OrderedDict()
        self._next_id = 0
""",
        """        self.pending: 'OrderedDict[int, dict]' = OrderedDict()
        # 🔴 2026-10-24 §22 修：**已下发 worker、等待结果**的句子 id。
        #   用途：worker 崩溃时，这些句子永远等不到 `played`/`error`
        #   ⇒ 挂在 `pending` 上**永不消失** ⇒ `drain()` 必定超时
        #   （GUI 白等 30 s / CLI 白等 120 s）。
        #   worker 重启后，未下发的（`_queue` 里的）会补发，
        #   但**已下发的那批**是真的丢了 ⇒ 必须在崩溃时清掉并计丢句。
        self._inflight: set = set()
        self._next_id = 0
""",
    ),
    (
        'P2-service-crash-lost',
        'tts_service.py',
        """        with self.lock:
            if dead_proc is not None and self.proc is dead_proc:
                self.proc = None
        self._restarted = True
""",
        """        with self.lock:
            if dead_proc is not None and self.proc is dead_proc:
                self.proc = None
            # 🔴 2026-10-24 §22 修：**已下发给（已死）worker 的句子永远等不到
            #   `played`/`error`** ⇒ 它们会一直挂在 `pending` 上
            #   ⇒ `drain()` 必定超时（GUI 白等 30 s / CLI 白等 120 s）。
            #   ⇒ 崩溃时把这些句子清掉并**计丢句**（诚实记账）。
            lost = sorted(self._inflight)
            self._inflight.clear()
            for jid in lost:
                self.pending.pop(jid, None)
        if lost:
            self.n_dropped += len(lost)
            self.on_log(f'[TTS] worker 崩溃，{len(lost)} 句在途译文丢失（已计丢句）')
        self._restarted = True
""",
    ),
    (
        'P3-service-submit-dead-guard',
        'tts_service.py',
        """            ready = (self.state == 'ready')
        cmd = {'cmd': 'synth', 'id': jid, 'text': text}
        if ready:
            self._send(cmd)
        else:
""",
        """            ready = (self.state == 'ready')
            dead = (self.state == 'error')
        cmd = {'cmd': 'synth', 'id': jid, 'text': text}
        if ready:
            with self.lock:
                self._inflight.add(jid)
            self._send(cmd)
        elif dead:
            # 🔴 2026-10-24 §22 修：worker 级故障后 `state == 'error'`，
            #   此时 `_flush_queue()` **永远不会被调用**（它只在 `ready` 事件时跑）
            #   ⇒ 旧实现把命令无限堆进 `_queue` ⇒ **内存无界增长**。
            #   现在：直接计丢句并清掉 pending，**不排队**。
            with self.lock:
                self.pending.pop(jid, None)
            self.n_dropped += 1
            self.on_log('[TTS] worker 已故障（error），该句不提交（已计丢句）')
        else:
""",
    ),
    (
        'P4-service-flush-queue-inflight',
        'tts_service.py',
        """        for cmd in q:
            self._send(cmd)
""",
        """        for cmd in q:
            jid = cmd.get('id')
            if jid is not None:
                with self.lock:
                    self._inflight.add(jid)
            self._send(cmd)
""",
    ),
    (
        'P5-service-error-classify',
        'tts_service.py',
        """        elif kind == 'error':
            self.state = 'error'
            self.err = msg.get('message', 'unknown')
            self.on_log(f'[TTS] 错误：{self.err}')
""",
        """        elif kind == 'error':
            # 🔴🔴 2026-10-24 §22 修：**必须区分「句子级」与「worker 级」错误**。
            #
            # worker 的 `error` 事件有两类（见 `tts_worker.py`）：
            #   - **句子级**：带 `'id': jid`（合成失败 / 播放缓冲写满 / 播放写入失败）
            #   - **worker 级**：**不带** `'id'`（模型加载失败 / 播放设备打开失败）
            #
            # 旧实现**一律**当成 worker 级 ⇒ `self.state = 'error'`，后果有三条：
            #   ① **整个会话的语音输出永久死掉**：
            #      `active` 变 False ⇒ CLI 的 `if tts.active: tts.submit(...)`
            #      从此不再提交；GUI 的 `submit()` 里 `ready = (state=='ready')`
            #      为 False ⇒ 命令进 `_queue` ⇒ `_flush_queue()` **只在 ready
            #      事件时调用** ⇒ 永远不发出去 ⇒ 静默堆积、**一声不响**。
            #   ② `pending[jid]` **永不清除**（这条路径上 worker 不发 `played`）
            #      ⇒ `drain()` 的 `pending_n == 0` 永远为假 ⇒ **收尾必超时**
            #      （GUI 白等 30 s / CLI 白等 120 s）。
            #   ③ `_queue` **无上限** ⇒ 内存无界增长。
            #
            # 修法：带 `id` ⇒ 句子级 ⇒ 只清这一句 + 计丢句 + **服务继续**
            #       不带 `id` ⇒ worker 级 ⇒ 维持原语义（判死 + 重启由 `_read_loop` 管）。
            msg_id = msg.get('id')
            message = msg.get('message', 'unknown')
            if msg_id is not None:
                # ── 句子级：这一句失败，**不影响后面的句子** ──────────────
                with self.lock:
                    self.pending.pop(msg_id, None)
                    self._inflight.discard(msg_id)
                self.n_dropped += 1
                self.on_log(f'[TTS] 第 {msg_id} 句合成失败（已丢弃，语音输出继续）：'
                            f'{message}')
            else:
                # ── worker 级：模型/播放设备等整体故障 ────────────────────
                self.state = 'error'
                self.err = message
                # worker 已死 ⇒ 在途与待发的句子都不会再有结果
                # ⇒ 必须清掉，否则 `drain()` 必定超时（GUI 30 s / CLI 120 s 白等）。
                with self.lock:
                    orphan = sorted(self.pending.keys())
                    self.pending.clear()
                    self._inflight.clear()
                    n_queued = len(self._queue)
                    self._queue.clear()
                if orphan or n_queued:
                    self.n_dropped += len(orphan)
                    self.on_log(f'[TTS] worker 故障，{len(orphan)} 句未完成'
                                f'（已计丢句），{n_queued} 句待发作废')
                self.on_log(f'[TTS] 错误：{self.err}')
""",
    ),
    (
        'P6-service-played-inflight',
        'tts_service.py',
        """        elif kind == 'played':
            jid = msg.get('id')
            with self.lock:
                self.pending.pop(jid, None)
            self.n_played += 1
""",
        """        elif kind == 'played':
            jid = msg.get('id')
            with self.lock:
                self.pending.pop(jid, None)
                self._inflight.discard(jid)
            self.n_played += 1
""",
    ),
    (
        'P7-worker-no-voice-babelvox',
        'tts_worker.py',
        """            if self.speaker_embed is None and not self.speaker_name:
                emit({'kind': 'error', 'message': '没有可用的音色'})
                return
""",
        """            if self.speaker_embed is None and not self.speaker_name:
                # 🔴 2026-10-24 §22：**句子级**错误必须带 `id`
                #   （主进程据此判定「这一句失败」而不是「worker 整体挂了」）
                emit({'kind': 'error', 'message': '没有可用的音色', 'id': jid})
                return
""",
    ),
    (
        'P8-worker-no-voice-ov',
        'tts_worker.py',
        """            if key not in self.conds:
                emit({'kind': 'error', 'message': f'没有可用的音色：{key}'})
                return
""",
        """            if key not in self.conds:
                # 🔴 2026-10-24 §22：**句子级**错误必须带 `id`（同上一处）
                emit({'kind': 'error', 'message': f'没有可用的音色：{key}', 'id': jid})
                return
""",
    ),
]


def discover_pkg_app(home: str = r'C:\Users\Trekker-PTL') -> str:
    """按 `Confucius4_LiveCaption_vX.Y` 自动发现**版本号最大**的包。

    🔴 必须排除 `.bak` / `backup` / `_pre_` 目录（长期记忆铁律：
       验证脚本不得写死版本号/包路径）。
    """
    best = None
    best_key = None
    for name in os.listdir(home):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        low = name.lower()
        if '.bak' in low or 'backup' in low or '_pre_' in low:
            continue
        app = os.path.join(home, name, 'app')
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

    # 读包内与仓库的内容
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

    # ── 逐块判定状态 ────────────────────────────────────────────────────
    # ⚠️ **不能**用「全部 OLD 都不在包里」判幂等：某些 OLD 是 NEW 的**子串**
    #    （追加型替换）⇒ 替换后 OLD 仍然在包里。
    # ⇒ 必须**逐块**判定，且 **NEW 优先**（NEW 在 ⇒ 已应用）。
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
            for tag, rel, old, new in PATCHES:
                if dict((t, s) for t, _, s in states)[tag] == 'already':
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
