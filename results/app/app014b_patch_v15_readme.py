r"""app014b_patch_v15_readme.py —— 客户包 README 升到 v1.5（APP-014②）

做了什么
--------
把客户包的 `README_zh.md` / `README_en.md` 改成 v1.5：

1. 标题版本号 `v1.4` → `v1.5`；
2. 开篇简介追加 **v1.5** 一句；
3. 在 `## v1.4 改动说明`（英文 `## What's new in v1.4`）**之前**插入
   `## v1.5 改动说明`（本轮四条改动）；
4. 🔴 修掉 **「Intel GPU 2」** 这个**不存在的设备名**（本轮 App 侧已修，
   README 的设备表格没跟着改 ⇒ 客户会看到不存在的设备）；
5. 「已知限制」补一条：接缝去重的真实收益量级（不要夸大）。

🔴 三条纪律（§33.6 的教训）
--------------------------
- **程序化锚点，零手抄**：整段替换一律用「标题 → 下一个 `## `」定位；
  表格行用**行首标记**（`| **ASR** |`）定位 ⇒ **不抄整行原文**。
  上一轮手抄英文 OLD 串命中 0 次、白跑一轮。
- **幂等**：每条规则都有 mark（文件里**真实存在**的特征串）⇒ 第二次跑全部跳过。
- **不制造 `\r\r\n`**：读写都用 `newline=''` ⇒ 行尾风格原样保留
  （§33 修 README 双 CR 炸弹的教训）。

用法
----
    python app014b_patch_v15_readme.py --pkg <客户包目录>
    python app014b_patch_v15_readme.py --pkg <目录> --check-only
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

# ── 备份目录（**必须在包外**）──────────────────────────────────────────
BACKUP_DIR = r'C:\Users\Trekker-PTL\git_backup\pkg_readme_v15_backup'

# ── v1.5 改动说明（中英双语）──────────────────────────────────────────
V15_SECTION_ZH = """## v1.5 改动说明

本轮重点是**把几个「看起来能用、其实有坑」的地方修掉**，并让界面显示的信息
与本机真实硬件一致。

### ① 设备列表按本机真实硬件显示（修掉「Intel GPU 2」）

以前设备下拉里有一个叫「**Intel GPU 2**」的条目 —— **这台机器上并不存在这个
设备**，它其实是**英伟达独显**被写死成了 Intel 的名字。现在下拉里直接显示
OpenVINO 报告的**硬件全名**，例如：

| 设备 | 实际含义 |
|---|---|
| `Intel(R) Graphics (iGPU)` | Intel 集成显卡（本项目的推荐档） |
| `NVIDIA GeForce RTX 5050 Laptop GPU (dGPU)` | 英伟达独立显卡 |
| `Intel(R) AI Boost` | Intel NPU |
| `CPU` | 仅作兜底，不在默认列表中 |

查不到全名时才回落到简写标签。**下拉里出现的每一个设备都是本机真实检测到的**，
不会出现虚构条目。

### ② 语音分区新增 NVIDIA CUDA 选项（附诚实警示）

「语音输出」分区在检测到英伟达设备时会多出一条 **NVIDIA GPU（CUDA）**。

> ⚠️ **请注意**：本包内的 OpenVINO **没有安装 CUDA plugin**（`openvino` 包内
> 没有任何 cuda 组件）⇒ 该选项在英伟达卡上**仍然走 Intel GPU plugin
> （Level Zero）**，**并不是真正的 CUDA 后端**。
> 实测（真实 INT8 TTS IR）：**集显 7/7 编译成功**，**英伟达独显 3/7 成功**
> —— `code_predictor` / `cp_decode` / `cp_prefill` / `talker_decode` 在
> FP16↔FP32 reorder 节点上会报「Could not find a suitable kernel」。
> ⇒ **建议在 Intel 集显上跑语音输出。**

### ③ 修掉段接缝处的重复词

屏幕字幕在**两段语音的接缝处**偶尔会冒出一个重复词（例如上一句结尾和下一句
开头是同一个词，显示成了两个）。原因：旧去重只尝试 3 个词和 2 个词的重复，
而实测段边界的重复分布是 —— 3 词及以上 **0** 处、2 词 **0** 处、**1 词 36~42 处**
⇒ **旧逻辑一次都没命中过**，重复词 100% 漏到了屏幕上。

现在改为**整词级 1~3 词**匹配，并且只在**确实是被切断的词**时才删
（判据：下一段首词是大写开头（说明重新起句），或上一段末尾没有句末标点
（说明同一句话被切开））。若上一句确实说完、下一句又真的重复了一遍
（会议里的复读很常见），则**保留**，不会误删。

### ④ 译文语音输出（TTS）转为正式功能，默认开启

原先标注为「实验性」，现在**去掉实验性标注、默认开启**：

- 界面「语音输出」分区可开关、选设备与推理精度（F32 / F16）、选播放设备。
- **默认开启**；不需要朗读可在界面取消勾选，或用命令行 `--tts off`。
- ⚠️ **请佩戴耳机，避免回授** —— TTS 从系统输出设备播放，若 ASR 同时采集
  系统声音，TTS 的声音会被**再采回去**，造成回声 / 自激 / 重复词。

"""

V15_SECTION_EN = """## What's new in v1.5

This round fixes a few things that *looked* fine but were not, and makes the
device list match the hardware that is actually present.

### ① The device list now reflects the real hardware (the "Intel GPU 2" ghost is gone)

The device drop-down used to contain an entry called **"Intel GPU 2"** — a
device that **does not exist on this machine**. It was actually the *NVIDIA*
discrete GPU, mislabelled as an Intel part. The drop-down now shows the
hardware full name reported by OpenVINO, e.g.:

| Device | What it really is |
|---|---|
| `Intel(R) Graphics (iGPU)` | Intel integrated graphics (the recommended tier) |
| `NVIDIA GeForce RTX 5050 Laptop GPU (dGPU)` | NVIDIA discrete graphics |
| `Intel(R) AI Boost` | Intel NPU |
| `CPU` | Fallback only, not in the default list |

The short label is used only when the full name cannot be queried. **Every
device in the drop-down is actually detected on this machine** — no invented
entries.

### ② A NVIDIA CUDA option was added to the speech section (with an honest caveat)

When an NVIDIA device is detected, the **Speech output** section gains one
extra entry: **NVIDIA GPU (CUDA)**.

> ⚠️ **Please note**: the OpenVINO build shipped in this package **does not
> include the CUDA plugin** (there is no `cuda` component in the `openvino`
> package) ⇒ on an NVIDIA card this option **still runs through the Intel GPU
> plugin (Level Zero)** and is **not a real CUDA backend**.
> Measured on the real INT8 TTS IR: **7/7 models compile on the iGPU**, but
> **only 3/7 on the NVIDIA dGPU** — `code_predictor` / `cp_decode` /
> `cp_prefill` / `talker_decode` fail with *"Could not find a suitable
> kernel"* at the FP16↔FP32 reorder nodes.
> ⇒ **Running speech output on the Intel iGPU is recommended.**

### ③ Repeated words at segment seams are fixed

The on-screen captions occasionally showed a repeated word **right at the seam
between two speech segments** (e.g. the previous sentence ends with a word and
the next one starts with the same word, so it appeared twice). Cause: the old
de-duplication only tried 3-word and 2-word repeats, but the measured
distribution of repeats at segment boundaries is — 3+ words **0**, 2 words
**0**, **1 word 36~42** ⇒ **the old logic never matched once**, so 100% of the
duplicates reached the screen.

It now matches at word level for 1~3 words, and only removes a word when it
really was a **split word** (judged by: the next segment starts with a
capitalised word — meaning a new sentence begins — or the previous segment does
not end with sentence-final punctuation — meaning one sentence was cut in
half). If the previous sentence really ended and the next one genuinely
repeats it (common in meeting transcripts), it is **kept** — no false
deletions.

### ④ Spoken translations (TTS) is now a full feature and is on by default

It used to be labelled *experimental*; the label is gone and it is **enabled by
default**:

- The **Speech output** section can switch it on/off, pick the device and
  precision (F32 / F16), and pick the playback device.
- **On by default**; untick it in the UI, or pass `--tts off` on the command
  line, if you do not want the narration.
- ⚠️ **Please wear headphones to avoid feedback** — TTS plays through the
  system output device; if ASR is capturing system audio at the same time, the
  TTS audio is **captured back**, causing echo / self-oscillation / repeated
  words.

"""

# 🔴 假设备串 —— 两条语言都要清零
FAKE_DEVICE = 'Intel GPU 2'


# ── IO 辅助（保留行尾风格）────────────────────────────────────────────
def read_text(path):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_text(path, txt):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def backup(path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(BACKUP_DIR, os.path.basename(path) + '.bak_' + stamp)
    shutil.copy2(path, dst)
    return dst


def find_line(txt, prefix):
    """按**行首标记**定位一行，返回 (行号, 整行)。找不到返回 (None, None)。"""
    for i, ln in enumerate(txt.split('\n')):
        if ln.startswith(prefix):
            return i, ln
    return None, None


def replace_table_row(txt, prefix, new_row, fname, name, applied, skipped):
    """替换一行表格行（用**行首标记**定位 ⇒ 不抄整行原文）。"""
    lines = txt.split('\n')
    hits = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    if len(hits) != 1:
        raise SystemExit(
            f'表格行未唯一命中（{len(hits)} 次）：{fname} / {name}\n'
            f'  prefix={prefix!r}')
    i = hits[0]
    old_row = lines[i]
    if old_row == new_row:
        skipped.append((fname, name, '幂等跳过（已是目标行）'))
        return txt
    lines[i] = new_row
    applied.append((fname, name, f'替换表格行 L{i + 1}'))
    return '\n'.join(lines)


def insert_before_section(txt, anchor, new_block, mark, fname, name,
                          applied, skipped):
    """在 `anchor`（章节标题行）**之前**插入一段。"""
    if mark and mark in txt:
        skipped.append((fname, name, '幂等跳过（mark 已在）'))
        return txt
    lines = txt.split('\n')
    hits = [i for i, ln in enumerate(lines) if ln == anchor]
    if len(hits) != 1:
        raise SystemExit(
            f'章节标题未唯一命中（{len(hits)} 次）：{fname} / {name}\n'
            f'  anchor={anchor!r}')
    i = hits[0]
    out = '\n'.join(lines[:i]) + '\n' + new_block + '\n' + '\n'.join(lines[i:])
    applied.append((fname, name, f'在 L{i + 1} 前插入 v1.5 段'))
    return out


def patch_readme(fname, txt, applied, skipped):
    is_zh = fname.startswith('README_zh')

    # ① 标题版本号
    old_title = ('# Confucius4-R2T2 实时字幕（技术评估版 v1.4）' if is_zh else
                 '# Confucius4-R2T2 Live Captions (technical evaluation build v1.4)')
    new_title = ('# Confucius4-R2T2 实时字幕（技术评估版 v1.5）' if is_zh else
                 '# Confucius4-R2T2 Live Captions (technical evaluation build v1.5)')
    if new_title in txt:
        skipped.append((fname, '标题版本号', '幂等跳过'))
    else:
        if txt.count(old_title) != 1:
            raise SystemExit(f'标题未唯一命中：{fname}')
        txt = txt.replace(old_title, new_title, 1)
        applied.append((fname, '标题版本号', 'replace'))

    # ② 开篇简介追加 v1.5 一句
    #    锚点 = 简介段的**末尾短语**（中/英各自措辞，唯一命中）
    if is_zh:
        anchor = '并可朗读译文**。全部本地运行，不联网。'
        new_para = ('并可朗读译文**。**v1.5 起设备列表按本机真实硬件显示（修掉不存在的'
                    '「Intel GPU 2」）、语音分区新增 NVIDIA CUDA 选项、修掉段接缝处的'
                    '重复词，译文语音输出转为正式功能并默认开启**。全部本地运行，不联网。')
        mark = 'v1.5 起设备列表按本机真实硬件显示'
    else:
        anchor = 'and translations can be spoken aloud.**'
        new_para = ('and translations can be spoken aloud.** **In v1.5 the device list '
                    'reflects the hardware actually present (the non-existent '
                    '"Intel GPU 2" is gone), the speech section gains a NVIDIA '
                    'CUDA option, repeated words at segment seams are fixed, and '
                    'spoken translations is now a full feature that is on by '
                    'default**.')
        mark = 'In v1.5 the device list'
    if mark in txt:
        skipped.append((fname, '开篇简介追加 v1.5', '幂等跳过'))
    else:
        if txt.count(anchor) != 1:
            raise SystemExit(
                f'开篇简介锚点未唯一命中（{txt.count(anchor)} 次）：{fname}\n'
                f'  anchor={anchor!r}')
        txt = txt.replace(anchor, new_para, 1)
        applied.append((fname, '开篇简介追加 v1.5', 'replace'))

    # ③ 插入 v1.5 改动说明段（在 v1.4 改动说明段**之前**）
    v14_anchor = '## v1.4 改动说明' if is_zh else "## What's new in v1.4"
    v15_sec = V15_SECTION_ZH if is_zh else V15_SECTION_EN
    txt = insert_before_section(
        txt, v14_anchor, v15_sec,
        '## v1.5 改动说明' if is_zh else "## What's new in v1.5",
        fname, '插入 v1.5 改动说明段', applied, skipped)

    # ④ 🔴 修掉设备表格里的「Intel GPU 2」
    #    定位方式 = **行首标记**（`| **ASR** |` / `| **ASR 识别** |` 等）
    if is_zh:
        specs = [
            ('| **ASR 识别** |',
             '| **ASR 识别** | 本机实际检测到的设备全名（如 Intel(R) Graphics (iGPU) / '
             'NVIDIA GeForce RTX 5050 Laptop GPU (dGPU) / Intel(R) AI Boost）× INT8 / INT4 | '
             'NPU 档的设备固定为 NPU（all-NPU 交付后端不接受覆盖） |'),
            ('| **翻译** |',
             '| **翻译** | 本机实际检测到的设备全名 × INT8-CW / INT4-CW | '
             'Hy-MT2 的两种量化产物，GPU / NPU 通吃 |'),
            ('| **语音输出** |',
             '| **语音输出** | 本机实际检测到的设备全名 × F32 / F16 | '
             'NPU 不支持 F32，组合会自动过滤；检测到 NVIDIA 设备时另列一条 '
             'NVIDIA GPU（CUDA） |'),
        ]
    else:
        specs = [
            ('| **ASR** |',
             '| **ASR** | The full names of the devices actually detected on this machine '
             '(e.g. Intel(R) Graphics (iGPU) / NVIDIA GeForce RTX 5050 Laptop GPU (dGPU) / '
             'Intel(R) AI Boost) × INT8 / INT4 | The NPU tiers are pinned to NPU '
             '(the all-NPU delivery backend does not accept an override) |'),
            ('| **Translation** |',
             '| **Translation** | The full names of the devices actually detected on this '
             'machine × INT8-CW / INT4-CW | Both Hy-MT2 quantized builds work on GPU and NPU |'),
            ('| **Speech output** |',
             '| **Speech output** | The full names of the devices actually detected on this '
             'machine × F32 / F16 | NPU does not support F32, so that combination is filtered '
             'out; one extra NVIDIA GPU (CUDA) entry is listed when an NVIDIA device is detected |'),
        ]
    for prefix, new_row in specs:
        txt = replace_table_row(txt, prefix, new_row, fname,
                                '修掉不存在的「Intel GPU 2」', applied, skipped)

    # ⑤ 「已知限制」补一条：接缝去重的真实收益量级（不夸大）
    lim_anchor = ('- 段切分按能量静音判断，长时间无停顿的讲话会在 20 s 处强制切段，切点附近偶尔会断词。'
                  if is_zh else
                  '- Segmentation uses energy-based silence detection; long speech without '
                  'pauses is cut at 20 s, which occasionally splits a word.')
    lim_new = (lim_anchor + '\n'
               + ('- 段接缝处的重复词已在 v1.5 修掉，但收益量级有限：'
                  '在 61 分钟会议素材上，WER 约改善 0.26~0.32 个百分点'
                  '（配对 bootstrap 95% CI 为负）。剩余误差主要来自识别本身，'
                  '不是切段重复。'
                  if is_zh else
                  '- Repeated words at segment seams were fixed in v1.5, but the gain is '
                  'modest: on 61-minute meeting material the WER improves by about '
                  '0.26~0.32 percentage points (paired bootstrap 95% CI is negative). '
                  'The remaining error comes mainly from recognition itself, not from '
                  'segmentation duplicates.'))
    lim_mark = ('段接缝处的重复词已在 v1.5 修掉' if is_zh else
                'Repeated words at segment seams were fixed in v1.5')
    if lim_mark in txt:
        skipped.append((fname, '已知限制补接缝去重量级', '幂等跳过'))
    else:
        if txt.count(lim_anchor) != 1:
            raise SystemExit(
                f'已知限制锚点未唯一命中（{txt.count(lim_anchor)} 次）：{fname}')
        txt = txt.replace(lim_anchor, lim_new, 1)
        applied.append((fname, '已知限制补接缝去重量级', 'replace'))

    # ⑥ 终检：**设备表格行**里不能再出现假设备名
    #    ⚠️ v1.5 说明段**正文**里提及「Intel GPU 2」是**允许的**
    #    （那是在解释「这个不存在的设备被修掉了」）⇒ 只查表格行。
    bad_rows = [ln for ln in txt.split('\n')
                if ln.startswith('|') and FAKE_DEVICE in ln]
    if bad_rows:
        raise SystemExit(
            f'❌ 设备表格里仍有假设备串「{FAKE_DEVICE}」：{fname}\n'
            f'   {bad_rows}\n'
            '   ⇒ 改写逻辑有漏，请检查后再打包。')
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True, help='客户包目录')
    ap.add_argument('--check-only', action='store_true', help='只报告，不写盘')
    args = ap.parse_args()

    applied, skipped = [], []
    report = []
    for fname in ('README_zh.md', 'README_en.md'):
        path = os.path.join(args.pkg, fname)
        if not os.path.isfile(path):
            raise SystemExit(f'找不到 {path}')
        txt = read_text(path)
        new_txt = patch_readme(fname, txt, applied, skipped)
        changed = new_txt != txt
        report.append(dict(file=fname, before_len=len(txt),
                           after_len=len(new_txt), changed=changed))
        if args.check_only:
            print(f'[check] {fname}: {len(txt)} -> {len(new_txt)} 字符，'
                  f'{"会改写" if changed else "无变化"}')
            continue
        if changed:
            b = backup(path)
            write_text(path, new_txt)
            chk = read_text(path)
            if chk != new_txt:
                raise SystemExit(f'{fname} 写盘后内容不一致')
            print(f'[ok] {fname} 已改写（{len(txt)} -> {len(new_txt)} 字符）'
                  f'\n     备份：{b}')
        else:
            print(f'[skip] {fname} 无变化')

    print()
    print(f'应用 {len(applied)} 条：')
    for a in applied:
        print('   +', a[0], '/', a[1], '/', a[2])
    print(f'跳过 {len(skipped)} 条：')
    for s in skipped:
        print('   -', s[0], '/', s[1], '/', s[2])

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'app014b_v15_readme_patch.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dict(applied=applied, skipped=skipped, report=report),
                  f, ensure_ascii=False, indent=1)
    print()
    print('证据：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
