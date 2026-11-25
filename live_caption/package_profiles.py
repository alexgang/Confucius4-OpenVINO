#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §2：**一份代码，三种包靠 profile 裁剪**。

## 用户决定（reviewer APP-118，2026-11-20）
> 完整版 = 默认「全集」环境（加 CUDA TTS / 10 语种 / EXT 与各项修复全部最新），
> **MiniMVP 与 SpecialMVP 以后都从它裁剪**。

⇒ **只有一份 dev 树**（`confucius4-openvino/live_caption/`）；
   打包**只负责「从全集按 profile 挑文件」**。

## 三个 profile 的差异（**只在本文件里定义一次**）
| profile | ASR | MT | TTS | CUDA | 克隆音色 | 语种 |
|---|---|---|---|---|---|---|
| `full` | R2T2 1.7B **＋** Qwen3-ASR 0.6B | INT8-CW（默认）＋ INT4 | OpenVINO（默认）＋ CUDA | ✅ 带 `cuda_env/` | ✅ | 10 |
| `minimvp` | **只有** Qwen3-ASR 0.6B | **只有** INT8-CW | **只有** OpenVINO | ❌ | ❌ | 10 |
| `specialmvp` | **只有** Qwen3-ASR 0.6B | **只有** INT8-CW | OpenVINO ＋ **CUDA** | ✅ 带 `cuda_env/` | ❌ | 10 |

## 用法
```bash
# ① 只看「从全集裁 minimvp 会得到什么」（不写任何文件）
python live_caption/package_profiles.py --profile minimvp --dry-run

# ② 只看体积构成
python live_caption/package_profiles.py --profile minimvp --dry-run --summary
```

## 纪律
- **不删任何东西**（本机有「安全删除 shim」⇒ 删除会被转回收站/被拦）
  ⇒ 裁剪是**「挑文件进清单」**，不是「删文件」；
- `--dry-run` **不写任何文件**；
- 清单用**相对路径**（`/` 分隔）⇒ 跨平台可比。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)

#: 全集（full）客户包 —— 裁剪的**唯一来源**。
FULL_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')

#: 🔴🔴🔳 **profile 定义（唯一事实来源）**
#:   每项 = 「**排除**清单」（相对全集包根，`/` 分隔）。
#:   裁剪 = 全集 − 排除项 ⇒ **不需要删文件**（本机删除会被 shim 拦）。
#:
#:   ⚠️ **`package_profile.json` 是「包形态标记」**（运行时读），
#:      **本文件是「构建期裁剪规则」**（打包时读）⇒ 两者**名字不同、职责不同**。
PROFILE_RULES = {
    'full': {
        'label': '完整版（全集）',
        'exclude': [],
        'marker': {
            'profile': 'full',
            'allow_cuda': True,
            'allow_clone_voice': True,
            'target_langs': 10,
        },
    },
    'minimvp': {
        'label': 'MiniMVP（从全集裁剪）',
        # 🔴 **去掉 R2T2 1.7B**（ASR 只留 0.6B）
        'exclude': [
            'models/decoder-gpu-int4',
            'models/decoder-gpu-int8',
            'models/decoder-npu-int4',
            'models/decoder-npu-int8',
            'models/encoder-fp16',
            'models/encoder-int4',
            'models/encoder-int8',
            'models/embed_tokens_f16.npy',
            # 🔴 **MT 只留 INT8-CW**（去 INT4）
            'models/mt/mt2-int4sym-cw-q',
            # 🔴 **不带 CUDA**
            'cuda_env',
            'models/tts_cuda',
            # 🔴🔴🔴 **APP-137（2026-11-25，用户决定）**：MiniMVP v1.2 起
            #   **并入 EXT 的全部功能（含「保留背景音」）+ 音色克隆** ⇒
            #   下面两行**从排除清单里去掉**：
            #   ① `models/spk` ＝ **克隆链 IR**（pyannote 说话人分段 +
            #      wespeaker x-vector 声纹）⇒ 克隆功能必需；
            #   ② `models/bgsep` ＝ **Demucs OV IR**（GPU.0 FP32）
            #      ⇒ 「保留背景音」必需。
            #   🔴 **客户包铁律不变**：`models/qwen3tts/voices/` 里**只留
            #      预设 A**；**不带**任何录音/克隆音色/同事声音/babelvox 样例/
            #      测试媒体 ⇒ 包内克隆音色目录**必须是空的**（首次使用现场采集）。
            #   ⚠️ **只去掉「模型目录」的排除**；**代码**在 `app/` 下 ⇒
            #      随 app/ 整树带入（clone_voice.py / clone_collector.py /
            #      speaker_*.py）⇒ 无需额外排除。
        ],
        'marker': {
            'profile': 'minimvp',
            'allow_cuda': False,
            # 🔴 APP-137：MiniMVP v1.2 **并入音色克隆** ⇒ 标记写 True。
            #    🔴 **老 MiniMVP 包（v1.1.1）的 marker 里是 false**
            #    ⇒ 读同一份 `package_profile.py` 逻辑时行为**不变**。
            'allow_clone_voice': True,
            # 🔴 APP-137：「保留背景音」**默认开**（与完整版一致）。
            'allow_bgkeep': True,
            # 🔴 APP-137：**APP-123 的 c13 不进 MiniMVP**（还没验收）
            #    ⇒ TTS 走 v2.6 的 APP-130 版（cp NPU 自检 + NaN 守卫），
            #      但**声码器窗口用 c13 之前的旧口径**。
            'tts_c13': False,
            # 🔴 APP-137：**MT 暂时用 Hy-MT2**（MT3 是否替换取决于 H-029）。
            #    这里**留好切换项**：改成 'mt3-int8sym-cw-q' 即可切 MT3。
            'mt_model': 'mt2-int8sym-cw-q',
            'target_langs': 10,
        },
    },
    'specialmvp': {
        'label': 'SpecialMVP（从全集裁剪：minimvp ＋ 加回 CUDA）',
        'exclude': [
            'models/decoder-gpu-int4',
            'models/decoder-gpu-int8',
            'models/decoder-npu-int4',
            'models/decoder-npu-int8',
            'models/encoder-fp16',
            'models/encoder-int4',
            'models/encoder-int8',
            'models/embed_tokens_f16.npy',
            'models/mt/mt2-int4sym-cw-q',
            # ⚠️ **不带 `cuda_env/` 也不带 `models/tts_cuda/`**
            #    ⇒ 这一点与「specialmvp ＝ minimvp ＋ 加回 CUDA」**矛盾**。
            #    ⇒ 实际做法：**specialmvp = minimvp 的排除项 + 不排除 CUDA**
            #    （CUDA 资产在全集里 ⇒ 不排除即保留）⇒ 见下方 `exclude` 注释。
        ],
        'marker': {
            'profile': 'specialmvp',
            'allow_cuda': True,
            'allow_clone_voice': False,
            'target_langs': 10,
        },
    },
}

#: 🔴🔴🔳 **specialmvp 的 CUDA 资产保留**
#:   上面 `exclude` 里**没有** `cuda_env` / `models/tts_cuda`
#:   ⇒ 它们**从全集原样保留** ⇒ specialmvp 天然带 CUDA。
#:   （本条是**刻意的**：specialmvp ＝ minimvp ＋ CUDA，而 CUDA 资产在全集里。）
SPECIALMVP_KEEPS_CUDA = True


def _norm(rel: str) -> str:
    return rel.replace(os.sep, '/').strip('/')


def is_excluded(rel: str, excludes) -> bool:
    """该相对路径是否被排除（**目录前缀**也算命中）。"""
    r = _norm(rel)
    for ex in excludes:
        e = _norm(ex)
        if r == e or r.startswith(e + '/'):
            return True
    return False


def collect(pkg_root: str, excludes):
    """遍历全集包 ⇒ 返回 (保留清单, 排除清单)。

    🔴 **只读** ⇒ 不删任何文件。
    """
    kept, dropped = [], []
    for dp, dns, fns in os.walk(pkg_root):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = _norm(os.path.relpath(full, pkg_root))
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            if is_excluded(rel, excludes):
                dropped.append((rel, size))
            else:
                kept.append((rel, size))
    kept.sort()
    dropped.sort()
    return kept, dropped


def summarize(kept, dropped):
    kb = sum(s for _r, s in kept)
    db = sum(s for _r, s in dropped)
    return {
        'kept_files': len(kept),
        'kept_bytes': kb,
        'kept_gib': round(kb / 1024 ** 3, 3),
        'dropped_files': len(dropped),
        'dropped_bytes': db,
        'dropped_gib': round(db / 1024 ** 3, 3),
    }


def top_dirs(kept, limit=25):
    """按顶层目录汇总体积（给「体积构成」报告用）。"""
    agg = {}
    for rel, size in kept:
        top = rel.split('/')[0] if '/' in rel else '(根文件)'
        agg.setdefault(top, [0, 0])
        agg[top][0] += 1
        agg[top][1] += size
    rows = sorted(agg.items(), key=lambda kv: -kv[1][1])
    return [{'name': k, 'files': v[0], 'bytes': v[1],
             'gib': round(v[1] / 1024 ** 3, 3)} for k, v in rows[:limit]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', required=True, choices=sorted(PROFILE_RULES))
    ap.add_argument('--pkg', default=FULL_PKG,
                    help='全集包目录（默认 v2.5）')
    ap.add_argument('--dry-run', action='store_true',
                    help='只报告，不写任何文件（本脚本本来就不写文件）')
    ap.add_argument('--summary', action='store_true',
                    help='只打体积构成，不逐文件列')
    ap.add_argument('--list', action='store_true',
                    help='逐文件列出保留清单')
    ap.add_argument('--out', default='', help='把清单写成 json')
    args = ap.parse_args()

    pkg = args.pkg
    if not os.path.isdir(pkg):
        print('FAIL: 全集包目录不存在：%s' % pkg)
        return 2
    rule = PROFILE_RULES[args.profile]
    excludes = rule['exclude']

    print('=' * 72)
    print('[profile=%s] %s' % (args.profile, rule['label']))
    print('=' * 72)
    print('全集来源：%s' % pkg)
    print('排除项（%d）：' % len(excludes))
    for ex in excludes:
        print('  − %s' % ex)
    if args.profile == 'specialmvp' and SPECIALMVP_KEEPS_CUDA:
        print('  （保留 `cuda_env/` 与 `models/tts_cuda/` ⇒ specialmvp 天然带 CUDA）')
    print()

    kept, dropped = collect(pkg, excludes)
    summ = summarize(kept, dropped)
    print('裁剪结果（**dry-run，未写任何文件**）：')
    print('  保留：%d 文件 / %d B（%.3f GiB）'
          % (summ['kept_files'], summ['kept_bytes'], summ['kept_gib']))
    print('  排除：%d 文件 / %d B（%.3f GiB）'
          % (summ['dropped_files'], summ['dropped_bytes'], summ['dropped_gib']))
    print()

    print('体积构成（保留部分，按顶层目录）：')
    for r in top_dirs(kept):
        print('  %-18s %8d 文件  %14d B  %8.3f GiB'
              % (r['name'], r['files'], r['bytes'], r['gib']))
    print()

    if args.list:
        print('保留清单（前 200 条）：')
        for rel, size in kept[:200]:
            print('  %14d  %s' % (size, rel))
        if len(kept) > 200:
            print('  …（另有 %d 条）' % (len(kept) - 200))
        print()

    print('包内标记 `package_profile.json`（裁剪后应写成）：')
    print(json.dumps(rule['marker'], ensure_ascii=False, indent=2))

    if args.out:
        out = {
            'profile': args.profile,
            'label': rule['label'],
            'source_pkg': pkg,
            'excludes': excludes,
            'summary': summ,
            'kept': [{'rel': r, 'bytes': s} for r, s in kept],
            'dropped': [{'rel': r, 'bytes': s} for r, s in dropped],
            'marker': rule['marker'],
            'top_dirs': top_dirs(kept, limit=999),
        }
        op = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(op), exist_ok=True)
        tmp = op + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        os.replace(tmp, op)
        print('清单已写：%s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
