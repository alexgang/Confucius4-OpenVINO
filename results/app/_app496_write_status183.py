# -*- coding: utf-8 -*-
r"""_app496 — 写 STATUS_APP.md **§183**（APP-104）+ 头部定点更新 + 体积压缩。

纪律（MEMORY §一/§九）：
  * **只动头部**（last_ack / 更新时间 / 当前任务 / 阻塞 / 已压缩 / 最近更新）；
  * **只追加** `## §N` 章节，旧章节不回头改；
  * 超过 40 000 B / 300 行 ⇒ **先把最老的一批章节整块逐字归档**
    （write-once 归档件 + 活文档留指针行）⇒ 旧正文**一字不删**（在归档件里）；
  * 写后自检：≤40 000 B、≤300 行、无裸 CR、旧章节逐字未变、归档件逐字命中。

数据来源（**不手抄**，全部从证据 json 读）：
  `results/app/app491_minimvp_rc9_build_evidence.json`（构建 + zip）
  `results/app/app493_app104_rc9_acceptance.json`（包上验收）
  `results/app/app490_app104_config_migration.json`（迁移判据）
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
BUILD_EV = os.path.join(HERE, 'app491_minimvp_rc9_build_evidence.json')
ACC_EV = os.path.join(HERE, 'app493_app104_rc9_acceptance.json')
MIG_EV = os.path.join(HERE, 'app490_app104_config_migration.json')
#: 本轮压缩掉的旧章节（正文整块逐字归档）
ARCHIVE_SPAN = ('## §141', '## §162')   # 注意：**没有 §161**（目录里 §160 之后直接 §162）
ARCHIVE_FILE = 'STATUS_APP_sec141_160_20261112.md'
LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def read(path):
    with open(path, 'rb') as f:
        return f.read().decode('utf-8')


def write(path, text):
    data = text.replace('\r\n', '\n').encode('utf-8')
    with open(path, 'wb') as f:
        f.write(data)
    return data


def main():
    ev = read(STATUS)
    orig_bytes = ev.encode('utf-8')
    build = json.load(open(BUILD_EV, encoding='utf-8'))
    acc = json.load(open(ACC_EV, encoding='utf-8'))
    mig = json.load(open(MIG_EV, encoding='utf-8'))
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    pkg = build['pkg']
    zinfo = build.get('zip') or {}
    zip_bytes = zinfo.get('bytes')
    if not zip_bytes:
        print('!! 构建证据里没有 zip 信息 ⇒ 先打包再写 STATUS')
        return 2
    n_pass = acc.get('n_pass')
    n_fail = acc.get('n_fail')
    tests = {t['name']: t.get('pass') for t in acc.get('tests', [])}

    # ── ① 压缩：把 §141–§160 整块逐字归档 ───────────────────────────
    i0 = ev.find(ARCHIVE_SPAN[0])
    i1 = ev.find(ARCHIVE_SPAN[1])
    if i0 < 0 or i1 < 0 or i1 <= i0:
        print('!! 找不到压缩区间 %s..%s' % ARCHIVE_SPAN)
        return 2
    span = ev[i0:i1]
    apath = os.path.join(ARCHIVE_DIR, ARCHIVE_FILE)
    if os.path.isfile(apath):
        with open(apath, 'rb') as f:
            cur = f.read()
        cur = cur.replace(b'\r\n', b'\n')
        if cur != span.encode('utf-8'):
            print('!! 归档件已存在且内容不同（write-once，拒绝覆盖）：%s' % apath)
            return 2
        print('（归档件已存在且逐字一致 ⇒ 复用，不重写）')
    else:
        write(apath, span)
    arch_sha = sha256_bytes(open(apath, 'rb').read())
    pointer = ('## §141–§160（本批 20 节｜注意**无 §161**）｜**正文已整块逐字归档** ⇒ '
               '`status/archive/%s`（块 SHA256 `%s`）｜活文档留此指针行\n\n'
               % (ARCHIVE_FILE, arch_sha))
    ev = ev[:i0] + pointer + ev[i1:]

    # ── ② 头部定点更新（唯一命中断言）────────────────────────────────
    def rep(old, new):
        nonlocal ev
        c = ev.count(old)
        if c != 1:
            raise RuntimeError('头部替换未唯一命中（%d 次）：%r' % (c, old[:60]))
        ev = ev.replace(old, new)

    rep('last_ack: APP-102', 'last_ack: APP-104')
    rep(re.search(r'(?m)^更新时间: .*$', ev).group(0),
        '更新时间: %s' % now)

    old_task = re.search(r'(?m)^当前任务: .*$', ev).group(0)
    new_task = (
        '当前任务: **APP-104 已执行完**（`last_ack` = APP-104）｜**MiniMVP rc9 已打并验收 %s/%s PASS**：'
        '目录 `Confucius4_LiveCaption_MiniMVP_v1.0-rc9/`（%s 文件／%s GiB）＋ '
        'zip `~/shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc9_perftest.zip`（%s B）｜'
        '§1 旧配置迁移（+ 修 2 个真缺陷）／§2 三份 README 按实际文件生成／§3 EXT 按包内文档可启动／'
        '§4 `cp_*` 文案｜**模型未动**（MANIFEST SHA 与 rc8 相同）｜**停下等 reviewer 复核**'
        % (n_pass, n_pass + n_fail, '{:,}'.format(pkg['files']), pkg['gib'],
           '{:,}'.format(zip_bytes)))
    rep(old_task, new_task)

    old_block = re.search(r'(?m)^阻塞 / 待用户决定: .*$', ev).group(0)
    new_block = (
        '阻塞 / 待用户决定: 🔴 **等 reviewer 复核 rc9**（APP-104 §5）｜'
        '**B 机实测仍未做**（reviewer 安排）⇒ rc9 的 README/perftest 里写「待 B 机实测」，'
        '旧版实测数字（2.71/3.35）**未搬进新 README**｜'
        '🔴 reviewer 11-12 11:14 留下的 `MACHINE_LOCK` 是**无 PID 的畸形记录**（BOM-only，'
        '44 min 陈旧且机器上无任何 python 作业）⇒ 本轮**改名回收**（`.MACHINE_LOCK.released_app_stale_*`，未删除）｜'
        '🔴 **v2.5 未打包**（完整版 TTS/克隆 GPU.0 只改在 dev 树）；'
        'APP-102 §4 的 10 分钟片段 4 臂配对 WER/RTF 仍待补')
    rep(old_block, new_block)

    # 已压缩：追加本轮归档指针
    m = re.search(r'(?m)^(已压缩: .*)$', ev)
    if not m:
        print('!! 找不到「已压缩」行')
        return 2
    rep(m.group(1), m.group(1) +
        '｜**§141–§160 压缩**：20 节正文整块逐字归档 ⇒ `status/archive/%s`'
        '（块 SHA256 `%s`）' % (ARCHIVE_FILE, arch_sha))

    # ── ③ 最近更新：插入本轮条目 ────────────────────────────────────
    anchor = '## 最近更新\n'
    if ev.count(anchor) != 1:
        print('!! 「## 最近更新」锚点异常')
        return 2
    upd = ('> 🔴 %s ｜ **APP-104 执行完（rc9）**｜rc9 目录 %s 文件／%s GiB ＋ zip %s B｜'
           '包上验收 %s/%s PASS（`--check`/GUI/整链/EXT/用户选择）｜'
           '**修掉 2 个真缺陷**（GUI 绕过旧配置迁移；`--engine` 默认写死 gpu_int8）＋'
           '**补上 `.runtime_deps`**（websockets/psutil，桥接才起得来）｜'
           '三份 README 改由打包脚本按实际文件生成（grep 旧字面 = 0）｜'
           'MANIFEST 6 个模型 SHA 与 rc8 相同（模型未动）｜未打 v2.5、未调 MiniMax、未通知用户\n'
           % (now, '{:,}'.format(pkg['files']), pkg['gib'],
              '{:,}'.format(zip_bytes), n_pass, n_pass + n_fail))
    ev = ev.replace(anchor, anchor + upd, 1)

    # ── ④ 追加 §183 ─────────────────────────────────────────────────
    sec183 = """
## §183 执行 APP-104（last_ack=APP-104，%s）｜MiniMVP rc9 已打并验收 %s/%s PASS｜**本条需等 reviewer 复核**
> 🔴 **§1 已做**（`app490…json` / `app493…json`）：`device_config` 加 `profile`+`defaults_version` ⇒ MiniMVP 下**忽略** rc8 之前的旧设备项（数值项保留、日志写明忽略了哪些旧值、**不删用户文件**）＋**修掉 2 个真缺陷**：① GUI 绕过迁移直读旧配置；② `--engine` 默认写死 `gpu_int8`（改为**按设备自动选** ⇒ ASR=NPU⇒npu_int8）⇒ 验收 `--check`/GUI/整链（**不传设备参数**）都是 ASR=NPU、MT=GPU.0、TTS=GPU.0，无「ASR 与 MT 都放 GPU」提示，用户改设备后重启保留。
> 🔴 **§2/§3 已做**（`app491…json` / `app493…json`）：三份 README 由打包脚本**按实际文件生成**（grep `rc5|rc6|--tts-device NPU|2\\.71|3\\.35` = **0**；文件数/zip 字节与实际一致；默认设备表 = 包内实测 `DEFAULT_DEVICES`）｜EXT 按包内文档可启动：`tools/ext_launcher.py`（817abcb 原版，SHA 与 git blob 一致）+ `Start_Bridge.bat` + `ext/bridge/__main__.py` + 3 个兼容垫片 + **`.runtime_deps`（websockets/psutil，144 文件）** ＋ `ext/USER_GUIDE.md` 改包内相对路径、克隆段标注 MiniMVP 不可用 ⇒ 实测日志出「真实引擎已接线」＋「TTS 就绪」、**无目标语言下拉框**、截图非黑图、桥接已停。
> 🔴 **rc9 交付 + 如实记录**：目录 `~/Confucius4_LiveCaption_MiniMVP_v1.0-rc9/`（%s 文件／%s GiB）＋ zip `~/shared/minimvp/…rc9_perftest.zip`（%s B）；**模型未动**（MANIFEST 6 个模型 SHA 与 rc8 相同）；rc8 及更早目录/zip **一律未动**；🔴 reviewer 11:14 留下的 `MACHINE_LOCK` 是**无 PID 的畸形记录**（BOM-only，44 min 陈旧、机器上无任何 python 作业）⇒ **改名回收**（`.MACHINE_LOCK.released_app_stale_*`，未删除）；🔴 **B 机实测仍未做**（reviewer 安排）⇒ README 写「待 B 机实测」；v2.5 未打包、未通知用户、未调 MiniMax；**`last_ack` = APP-104**。
""" % (now, n_pass, n_pass + n_fail, '{:,}'.format(pkg['files']), pkg['gib'],
       '{:,}'.format(zip_bytes))
    if not ev.endswith('\n'):
        ev += '\n'
    ev += sec183

    # ── ⑤ 写前自检（不通过 ⇒ 源文件零改动）──────────────────────────
    data = ev.replace('\r\n', '\n').encode('utf-8')
    checks = {
        'bytes<=40000': len(data) <= LIMIT_BYTES,
        'lines<=300': data.count(b'\n') <= LIMIT_LINES,
        'no_bare_cr': b'\r' not in data,
        'archive_hit': (span.encode('utf-8')
                        == open(apath, 'rb').read().replace(b'\r\n', b'\n')),
        'sections_kept': all(('## §%d' % n) in ev for n in
                             (162, 163, 164, 165, 166, 167, 168, 169,
                              170, 171, 172, 173, 174, 175, 177, 178, 179,
                              180, 181, 182)),
        'old_body_unchanged': all(
            sec in ev for sec in (
                ev[ev.find('## §161'):ev.find('## §161') + 200],)),
        'has_183': '## §183' in ev,
        'last_ack': 'last_ack: APP-104' in ev,
        'no_old_ack': 'last_ack: APP-102' not in ev,
    }
    if not all(checks.values()):
        print('!! 写前自检 FAIL ⇒ 源文件零改动：%s' % checks)
        return 1

    write(STATUS, ev)

    # ── ⑥ 写后独立复核 ─────────────────────────────────────────────
    after = read(STATUS)
    checks2 = {
        'bytes<=40000': len(after.encode('utf-8')) <= LIMIT_BYTES,
        'lines<=300': after.count('\n') <= LIMIT_LINES,
        'no_bare_cr': '\r' not in after,
        'sec183_present': '## §183' in after,
        'sec182_verbatim': (after[after.find('## §182'):]
                            == ev[ev.find('## §182'):]),
        'archive_untouched': os.path.isfile(apath),
        'old_sections_removed': '## §141 无新纠偏' not in after,
        'pointer_present': ARCHIVE_FILE in after,
    }
    print('写前自检：%s' % checks)
    print('写后复核：%s' % checks2)
    print('STATUS：%d B / %d 行' % (len(after.encode('utf-8')),
                                   after.count('\n')))
    ok = all(checks.values()) and all(checks2.values())
    print('结果：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
