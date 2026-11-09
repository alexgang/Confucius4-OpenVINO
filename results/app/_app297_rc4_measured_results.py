#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app297_rc4_measured_results.py —— **把实测数字写进 rc4 的 README_perftest.txt**。

## 为什么要有这个脚本

用户验收要求 3 明确要「报 WER / RTF / 首字延迟 / 峰值内存 / 包体积增量」。
⇒ 这些数字必须**随包可查**（客户在别的机器上跑，能对照本机基线）。

## 🔴 纪律
* **断链后写**（rc4 与 rc3 共享 inode ⇒ 原地写会改到 rc3！）。
* 数字**全部来自已落盘的证据 json**，**不推算**：
  * `app294_rc4_npu_acceptance_evidence.json`（RTF / 延迟 / 峰值内存）
  * `app295_rc4_wer_compare_evidence.json`（WER）
  * `app296_rc4_exec_device_evidence.json`（实际执行设备）
  * `app291_minimvp_rc4_build_evidence.json`（体积）

用法：
    .venv/Scripts/python.exe results/app/_app297_rc4_measured_results.py
"""
from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
RC3 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
RC4 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
EVID = os.path.join(HERE, 'app297_rc4_measured_results_evidence.json')

E294 = os.path.join(HERE, 'app294_rc4_npu_acceptance_evidence.json')
E295 = os.path.join(HERE, 'app295_rc4_wer_compare_evidence.json')
E296 = os.path.join(HERE, 'app296_rc4_exec_device_evidence.json')
E291 = os.path.join(HERE, 'app291_minimvp_rc4_build_evidence.json')

ANCHOR = '【🔴 目标机兼容性提醒（务必先读）】'

BLOCK = """【rc4 实测基线（本机，Panther Lake Ultra 7 356H / OV 2026.4.1 随包）】
  素材：SPE_0000_0500.wav（300.0 s 英文 SPE）｜命令见下方「步骤 2」
  ⇒ 目标机跑同一命令即可与下表对照。

  ┌ 档位                     RTF      出字延迟中位   最大积压   峰值内存   段数
  │ ASR=NPU（TTS off）      0.803    540 ms          1.1 s   5212.6 MB   46
  │ ASR=GPU.0（TTS off）    0.696    376 ms          1.2 s   4819.5 MB   46
  │ ASR=NPU + TTS=NPU       1.264    55362 ms       84.4 s   5213.1 MB   46

  ⚠️ **第三行不是 ASR 慢**：ASR 与 TTS **抢同一个 NPU** ⇒ 积压 84 s。
     ⇒ **全 NPU 家家桶（TTS 也走 NPU）当前不可用于实时字幕**；
     ⇒ 要么 TTS 走 iGPU（`--tts-device GPU.0`），要么只用 NPU 做 ASR。
  ⚠️ **峰值内存含 OV 编译期**（≈5 GB）⇒ 建议 ≥16 GB。

  【WER（英文，词级）】
    参考 = 同一段音频的离线转写（921 词）⇒ 两档**可比**：
      · ASR=NPU   WER 15.5266 %（143 处编辑 / 819 词）
      · ASR=GPU.0 WER 14.5494 %（134 处编辑 / 820 词）
      · **NPU 直接对 GPU.0：WER 2.5610 %（21 处编辑）** ⇒ 两档输出高度一致
    ⚠️ 该参考是**同模型族离线转写**，**非人工逐字校对稿**
       ⇒ 绝对 WER 仍需以人工校对稿为准。

  【实际执行设备（OpenVINO EXECUTION_DEVICES 直证）】
    · encoder = NPU   · decoder = NPU   ⇒ 两者都真的落在 NPU 上。

  【包体积】
    rc3 6.68 GB → rc4 9.97 GB（**+3.28 GB**，全部是补进去的 3 个 NPU IR）；
    文件数 10 474 → 10 510；**包内 0 个预编译 blob**（编译缓存写用户目录）。

"""


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    e294 = json.load(open(E294, encoding='utf-8'))
    e295 = json.load(open(E295, encoding='utf-8'))
    e296 = json.load(open(E296, encoding='utf-8'))
    e291 = json.load(open(E291, encoding='utf-8'))

    p4 = os.path.join(RC4, 'README_perftest.txt')
    p3 = os.path.join(RC3, 'README_perftest.txt')
    rc3_before = open(p3, 'rb').read()
    txt = open(p4, 'rb').read().decode('utf-8')

    res = {'script': os.path.basename(__file__),
           'npu_exec_devices': (e296.get('encoder_exec_devices'),
                                e296.get('decoder_exec_devices')),
           'exec_verdict': e296.get('verdict'),
           'wer': {a: e295['arms'][a].get('wer_vs_ref')
                   for a in ('npu', 'igpu')},
           'wer_npu_vs_igpu': e295.get('wer_npu_vs_igpu'),
           'perf': {a: e295['perf'][a] for a in e295.get('perf', {})},
           'size': e295.get('size')}

    if '【rc4 实测基线' in txt:
        print('ℹ 已在包里 ⇒ 不重复插入')
    else:
        assert txt.count(ANCHOR) == 1, '锚点不唯一 ⇒ 不改'
        txt = txt.replace(ANCHOR, BLOCK + ANCHOR, 1)
        tmp = p4 + '.app297.tmp'
        with open(tmp, 'wb') as f:
            f.write(txt.encode('utf-8'))
        os.replace(tmp, p4)

    rc3_after = open(p3, 'rb').read()
    res['checks'] = {
        'rc3_bytes_unchanged': (rc3_before == rc3_after),
        'rc3_inode_differs': (os.stat(p4).st_ino != os.stat(p3).st_ino),
        'rc4_has_measured_block': ('【rc4 实测基线' in
                                   open(p4, encoding='utf-8').read()),
    }
    res['checks']['pass'] = all(res['checks'].values())
    res['verdict'] = ('DOCS_OK' if res['checks']['pass'] else 'DOCS_FAILED')
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({'checks': res['checks'], 'verdict': res['verdict']},
                     ensure_ascii=False))
    return 0 if res['checks']['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
