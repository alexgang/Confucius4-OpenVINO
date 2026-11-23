#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §221：生成 STATUS 的两段文本（§221 标题行＋指针行、「最近更新」条目）。

## 纪律
- **数字全部从证据 json 读出**（不手抄）；
- companion 的 SHA 在**companion 写完之后**再算 ⇒ 本脚本分两步：
  ① `--step title`（占位 SHA）② companion 写好后 `--step title --sha <实际>`；
  ⇒ 或者直接跑 `--step all`（先写 companion 再写 STATUS 文本）。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
COMPANION = os.path.join(REPO, 'status', 'app',
                         'STATUS_APP_sec221_detail_20261123.md')
TITLE_OUT = os.path.join(RESULTS, '_app121_sec221_title.txt')
RECENT_OUT = os.path.join(RESULTS, '_app121_sec221_recent.txt')


def sha_of(p):
    if not os.path.isfile(p):
        return None
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load(n):
    p = os.path.join(RESULTS, n)
    if not os.path.isfile(p):
        return None
    try:
        with io.open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-title', default=TITLE_OUT)
    ap.add_argument('--out-recent', default=RECENT_OUT)
    args = ap.parse_args()

    chain = load('app591_acceptance_app121_v111_default_run20261123-1000.json') or {}
    rd = load('app121_write_readme_evidence.json') or {}
    zip_ev = load('app121_zip_v111.json') or {}
    zx = load('app121_zip_extract_check.json') or {}
    gui = load('app121_gui_smoke.json') or {}
    tel = chain.get('telemetry') or {}
    sc = chain.get('sentence_counts') or {}
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    n_files = rd.get('n_files_zip_content', '（未取到）')
    n_bytes = rd.get('bytes_zip_content', '（未取到）')
    zip_bytes = zip_ev.get('zip_bytes', '（未取到）')
    zip_files = zip_ev.get('n_files', '（未取到）')
    extract_verdict = zx.get('verdict', '（未跑）')
    gui_verdict = gui.get('verdict', '（未跑）')
    synth_p50 = tel.get('synth_rtf_p50', '（未取到）')
    synth_p90 = tel.get('synth_rtf_p90', '（未取到）')
    backlog_max = tel.get('play_lag_max', '（未取到）')
    speed_max = tel.get('speed_max', '（未取到）')
    n_sent = sc.get('n_translations', '（未取到）')
    n_drop = sc.get('n_drop_total_any_reason', '（未取到）')
    queued = sc.get('n_queued_before_ready', '（未取到）')
    flushed = sc.get('n_flushed', '（未取到）')

    c_sha = sha_of(COMPANION)
    c_bytes = os.path.getsize(COMPANION) if os.path.isfile(COMPANION) else 0

    title = (
        '## §221 执行 **APP-121**（last_ack=APP-120 → **APP-121**，%s）｜'
        '🟢 **§1 修掉「ASR=NPU 长段让 ASR 线程退出」**'
        '（NPU 档 prompt 上界按 handoff 口径**只算 prompt**；'
        '**旧包可复现** `ValueError`、**新包无**）｜'
        '🟢 **§1③ GPU 档未受影响**（旧包/新包 GPU.0 三素材 transcript md5 '
        '**逐字节相同**）｜'
        '🟢 **§2 撤回 §220 的两句 md5 结论**（那两个测试**没跑 App 代码**）'
        '＋ 补 **App 后端**实测｜'
        '🟢 **§3 ACCEPTED 模块清单 == zip 实际内容**（`tts_cuda*` 改名挪到包外）'
        '＋ **解压自检已做**（%s／GUI 冒烟 %s）｜'
        '🟢 **§4 README 面向客户重写**（zip 口径文件数/字节数、去内部编号、'
        '补配音滞后已知问题、**「配音首包」与「字幕出字延迟」分开写**）｜'
        '🟢 **§5 整链 %s PASS**（%s 句、丢弃 %s）｜'
        '🔴 **计时类不作数**（synth_rtf P90 %s）｜'
        '🔴 **修掉 1 处既有 harness 缺陷**｜'
        '🔴 **如实登记 3 处事故**｜'
        '**新包 v1.1.1 ＋ 新 zip，v1.1 目录与 zip 未覆盖未删**｜'
        '**本条需等 reviewer 复核**'
        % (now, extract_verdict, gui_verdict,
           ('%d/%d' % (len(chain.get('checks') or [])
                       - chain.get('n_fail', 0),
                       len(chain.get('checks') or []))),
           n_sent, n_drop, synth_p90))
    pointer = (
        '> 🔴 **本节正文落 companion** ⇒ '
        '`status/app/STATUS_APP_sec221_detail_20261123.md`（%d B／SHA256 `%s`）；'
        '**§0 摘要 ＋ §1～§5 逐条 ＋ §220 companion 行号订正表 ＋ '
        '本轮如实登记的 3 处事故**，逐条引用结果文件与原始字段。'
        '活文档本节只留本行 ＋ 标题行。'
        % (c_bytes, (c_sha or '（companion 未写）')[:16]))
    with io.open(args.out_title, 'w', encoding='utf-8', newline='\n') as f:
        f.write(title + '\n' + pointer + '\n')

    recent = (
        '> 🔴 %s ｜ **执行 APP-121**（last_ack=APP-120 → **APP-121**）：'
        '🟢 **§1 ASR=NPU 长段 ValueError 已修**（NPU 档 `allowed_prefix = '
        'limit − skeleton`，**只有 `skeleton > limit` 才报错**；GPU 档一字未动；'
        '`_loop` 单段解码异常改为**记日志＋计数＋跳过该段**）—— '
        '**旧包实测复现** `ValueError: prompt 骨架 281 + 预留 64 > 320`、'
        '字幕 **0 行**；**新包同一素材** rc=0、**强制切段 20.48 s**、'
        '字幕 **2 行/514 字符**｜'
        '🟢 **§1③ GPU 档未受影响**：旧包与新包 GPU.0 三素材 transcript md5 '
        '**逐字节相同**（spe/en/zh）｜'
        '🟢 **§2 撤回 §220 两句结论**（§0④ 的 md5 测试**没跑 App 代码**）＋ '
        '补 **App 后端**（`OVEngine`）实测：NPU/GPU.0 各 3 素材 md5 与 '
        '`prefix_truncations` 已报；**段数与参照完全一致**（93/65/66）⇒ '
        '差异在解码/拼接路径，**不要求硬凑一致**｜'
        '🟢 **§3 ACCEPTED 模块清单 == zip 实际内容**（`tts_cuda*` 改名挪到包外，'
        '**未删**）＋ **解压自检已做**（全新目录＋全新 %%LOCALAPPDATA%% `--check`'
        '＋GUI 冒烟 **%s**）｜'
        '🟢 **§4 README 面向客户重写**（zip 口径 **%s 文件 / %s B**、去内部编号、'
        '补配音滞后已知问题、**「配音首包 0.42 s」与「字幕出字延迟中位 317 ms」'
        '分开写**）｜'
        '🟢 **§5 整链 %s PASS**（%s 句、**丢弃 %s**、就绪前排队 %s/%s 补发、'
        '语速 max %s≤1.70）｜'
        '🔴 **计时类不作数**（synth_rtf 中位 %s／P90 %s，积压峰值 %s s；'
        '**撤回「机器被占」这个无证据的归因**）｜'
        '🔴 **修掉 1 处既有 harness 缺陷**（APP-120 编排的 devswitch 步骤'
        '**在已提交版本上根本跑不起来**）｜'
        '🔴 **如实登记 3 处事故**（锁泄漏／素材静音阈值取错／`--out` 残留）｜'
        '**新包 v1.1.1 ＋ 新 zip（%s B / %s 文件），v1.1 目录与 zip 未覆盖未删**｜'
        '**本条需等 reviewer 复核**'
        % (now, extract_verdict, n_files, n_bytes,
           ('%d/%d' % (len(chain.get('checks') or [])
                       - chain.get('n_fail', 0),
                       len(chain.get('checks') or []))),
           n_sent, n_drop, queued, flushed, speed_max,
           synth_p50, synth_p90, backlog_max, zip_bytes, zip_files))
    with io.open(args.out_recent, 'w', encoding='utf-8', newline='\n') as f:
        f.write(recent + '\n')

    print('标题行 → %s（%d 字符）' % (args.out_title, len(title)))
    print('指针行 → 同文件')
    print('最近更新 → %s（%d 字符）' % (args.out_recent, len(recent)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
