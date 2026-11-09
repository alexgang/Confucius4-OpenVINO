#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app293_rc4_docs_patch.py —— **rc4 文档定点改写**（断链写，rc3 一字不动）。

## 要改什么

`README_perftest.txt` 里版本串出现 **7 次** ⇒ 不是唯一命中 ⇒
`_app291` 的「唯一命中断言」正确地**没有改它**（这是对的：
唯一命中规则防的是误伤，但此处是**版本升级**，本来就该多处改）。

⇒ 本脚本**按上下文逐条精确替换**（每条都带足够上下文 ⇒ 唯一命中），
并且**先断链再写**（硬链接 ⇒ 原地写会改到 rc3！）。

## 同时补的「NPU ASR 已可用」说明（用户需求 2/3/4 的交付面）

rc4 新增了 3 个 NPU IR ⇒ `README_perftest.txt` 里要写清：
* `--check` 现在会显示「Intel NPU · INT8 模型齐全」；
* NPU ASR 的用法（`--engine npu_int8`）；
* **编译缓存不在包内**（目标机首次运行现编）⇒ 符合用户要求 4；
* 🔴 **Meteor Lake 风险**（app290 探针实测结论）：decoder **必须**用
  `NPU_USE_NPUW` + `NPUW_LLM`；实测「不开 NPUW」编不过（动态形状），
  ⇒ 若目标机 NPUW 不可用则 NPU ASR 起不来 ⇒ **先用 iGPU 档做功能验收**。

## 用法
```
.venv/Scripts/python.exe results/app/_app293_rc4_docs_patch.py --dry-run
.venv/Scripts/python.exe results/app/_app293_rc4_docs_patch.py --run
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
RC3 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
RC4 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
EVID = os.path.join(HERE, 'app293_rc4_docs_patch_evidence.json')

#: 🔴 逐条精确替换（每条带上下文 ⇒ 唯一命中）
PATCHES = (
    # 标题
    ('Confucius4 LiveCaption · MiniMVP v1.0-rc3 —— 性能测试版说明',
     'Confucius4 LiveCaption · MiniMVP v1.0-rc4 —— 性能测试版说明'),
    # 定位段
    ('这是 **MiniMVP v1.0-rc3 的性能测试构建**，用于在其他机器上测',
     '这是 **MiniMVP v1.0-rc4 的性能测试构建**，用于在其他机器上测'),
    # 已知问题 1
    ('⚠️ **rc3 的 A+C（后台编译 + 首句先出）方案尚未做设备级验证**，\n'
     '        所以 rc3 的首次启动可能仍是「等全部编完才出声」。',
     '⚠️ **rc4 的 A+C（后台编译 + 首句先出）方案尚未做设备级验证**，\n'
     '        所以 rc4 的首次启动可能仍是「等全部编完才出声」。'),
    # 已知问题 2
    ('rc2 实测 6 次启动里崩 2 次；**rc3 未做有效复测**。',
     'rc2 实测 6 次启动里崩 2 次；**rc4 未做有效复测**。'),
    # 性能实测段
    ('实测结果（rc3，设备级 3(a) 验收，76 段全部出声）：',
     '实测结果（rc3，设备级 3(a) 验收，76 段全部出声；rc4 未改 ASR 侧）：'),
    # 首次编译说明
    ('· 首次 NPU 编译     1209.3 s（rc2 实测；rc3 未复测）',
     '· 首次 NPU 编译     1209.3 s（rc2 实测；rc4 未复测）'),
)

#: 🔴 rc4 新增段落（插在「已知问题」列表之前）
NPU_SECTION = """【rc4 新增：全 NPU ASR 已随包】
  rc3 只带了 **GPU 版 ASR**（encoder-int8 + decoder-gpu-int8）⇒ `--check` 显示
  「Intel NPU · INT8 缺 编码器、解码器」。**rc4 补齐了 3 个 NPU IR**：
      · models/encoder-fp16      （= ov-encoder-segment-reviewer，fp16 encoder）
      · models/decoder-npu-int8   （= qwen3-lm-int8sym-cleanie-ov，因果 LM，INT8）
      · models/decoder-npu-int4   （= c089_int4/R4，INT4 实验档）
  ⇒ rc4 的 `--check` 应显示「**Intel NPU · INT8  模型齐全**」。
  · iGPU 版模型（encoder-int8 / decoder-gpu-int8）**保留** ⇒ 两档可对比。
  · 用法：`python\\python.exe app\\live_caption_app.py --engine npu_int8 --check`
    或跑 5 分钟时加 `--engine npu_int8 --asr-device NPU`。

【🔴 目标机兼容性提醒（务必先读）】
  · **编译缓存不在包内**（实测包内 0 个 .blob）⇒ 缓存写在
    %LOCALAPPDATA%\\Confucius4LiveCaption\\npu_cache
    ⇒ **目标机首次运行时现场编译**（不会带任何 Panther Lake 专属产物）。
  · **NPU decoder 必须用 NPUW**（实测，见 app290 探针）：
      · decoder 开 `NPU_USE_NPUW` + `NPUW_LLM` ⇒ ✅ 编译成功，落在 NPU；
      · decoder 不开 NPUW ⇒ ❌ `to_shape was called on a dynamic shape`；
      · encoder 冻结形状后**不需要** NPUW ⇒ ✅ 走普通 NPU 编译即可。
    ⇒ 若目标机（不同代际 NPU）的 NPUW 不可用，**NPU ASR 起不来**；
      此时请先用 iGPU 档（`--engine gpu_int8`）做功能验收。

"""


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def unlink_then_write(p: str, data: bytes) -> None:
    tmp = p + '.app293.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    args = ap.parse_args()

    res = {'script': os.path.basename(__file__), 'rc4': RC4, 'rc3': RC3,
           'dry_run': not args.run, 'patches': []}
    p4 = os.path.join(RC4, 'README_perftest.txt')
    p3 = os.path.join(RC3, 'README_perftest.txt')
    if not os.path.isfile(p4):
        res['verdict'] = 'RC4_PERFTEST_MISSING'
        _write(res)
        return 2

    txt = open(p4, 'rb').read().decode('utf-8')
    rc3_before = open(p3, 'rb').read()

    for old, new in PATCHES:
        n = txt.count(old)
        applied = False
        if n == 1:
            txt = txt.replace(old, new, 1)
            applied = True
        res['patches'].append({'old': old[:60], 'count': n, 'applied': applied})

    # 插入 NPU 段落（锚点：「【已知问题】」之前）
    anchor = '【已知问题】（实测记录，请勿当 bug 报给我们，先看这里）'
    if NPU_SECTION.split('\n')[0] not in txt and anchor in txt:
        txt = txt.replace(anchor, NPU_SECTION + anchor, 1)
        res['npu_section_inserted'] = True
    else:
        res['npu_section_inserted'] = False

    res['unapplied'] = [x for x in res['patches'] if not x['applied']]
    print('== 定点替换 ==')
    for x in res['patches']:
        print('  count=%d applied=%s  %s' % (x['count'], x['applied'],
                                            x['old'][:50]))
    print('NPU 段落插入：%s' % res['npu_section_inserted'])

    if args.dry_run:
        res['verdict'] = 'DRY_RUN'
        _write(res)
        return 0

    # 🔴 断链后写 ⇒ rc3 不受影响
    unlink_then_write(p4, txt.encode('utf-8'))

    # ── 复核 ─────────────────────────────────────────────────
    rc3_after = open(p3, 'rb').read()
    chk = {
        'rc3_bytes_unchanged': (rc3_before == rc3_after),
        'rc3_sha256': sha_bytes(rc3_after),
        'rc3_still_has_rc3': (b'v1.0-rc3' in rc3_after),
        'rc4_has_rc4': (b'v1.0-rc4' in open(p4, 'rb').read()),
        'rc4_inode_differs': (os.stat(p4).st_ino != os.stat(p3).st_ino),
    }
    chk['pass'] = all(v for k, v in chk.items() if k != 'rc3_sha256')
    res['checks'] = chk
    res['verdict'] = 'PATCHED_OK' if chk['pass'] else 'PATCH_FAILED'
    print('== 复核 ==')
    for k, v in chk.items():
        if k != 'rc3_sha256':
            print('  %-22s %s' % (k, v))
    _write(res)
    print('★ %s' % res['verdict'])
    return 0 if chk['pass'] else 1


def _write(obj: dict) -> None:
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    raise SystemExit(main())
