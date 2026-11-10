# -*- coding: utf-8 -*-
r"""_app421 — **rc6 的 README_perftest.txt 重写**（APP-098 二.5）。

## 为什么重写（reviewer 点名的三处自相矛盾）

1. **体积写「rc5 9.97 GB」** ⇒ 实测：zip **4.42 GB**、解压后 **5.94 GB**
   ⇒ 「9.97 GB」是**把模型目录的字节数当成了压缩后体积**（口径错误）。
2. **写「rc5 未改 ASR 侧」** ⇒ 实际 **rc5 已经把 ASR 换成 Qwen3-ASR-0.6B**
   （APP-096）⇒ 这句话**直接是错的**（而基准表还是 rc3 的数字）。
3. **基准表是 rc3 的数字** ⇒ rc5/rc6 的 ASR 已换模型 ⇒ 旧数字**不能代表本包**。

## 口径纪律

* 🔴 **凡是数字都写明来源**（实测值 + 测量对象 + 测量机器）。
* 🔴 **B 机（Meteor Lake）的实测**是 reviewer 给的 ⇒ 原样记录并标注来源。
* 🔴 **不编造本机（A 机 Panther Lake）的新数字** ⇒ A 机的数字**保留但标注**
  「那是 rc3 的 ASR（R2T2）下测的，**不能代表本包**」。

用法：
    from _app421_rc6_readme import write_readme
"""

import os

#: 🔴 reviewer 在 B 机（Meteor Lake 155H）实测给出的数字（**原样记录**）
METEOR_LAKE = {
    'machine': 'Intel Core Ultra 7 155H（Meteor Lake，iGPU + NPU）',
    'asr_iGPU_rtf': 2.71,
    'asr_NPU_rtf': 3.35,
    'both_iGPU': ('ASR 与 MT **都放 iGPU** ⇒ 跑 **268 s** 后报 '
                  '`CL_OUT_OF_RESOURCES`（GPU 资源耗尽）⇒ 崩溃'),
    'conclusion': ('⇒ **不能实时**（RTF 2.71 / 3.35 都 > 1）'
                   '；且 ASR+MT 同占 iGPU 会崩 ⇒ ASR 必须放 NPU'),
}


def write_readme(pkg_dir, model_identity, ev, zip_bytes=None):
    """按实测重写 ``<包根>/README_perftest.txt``。

    🔴🔴🔳 **口径与 zip 脚本完全一致**（同一份清单来源 = `pkg_exclude`）
       ⇒ **「解压后 N 个文件 / X GB」** 与 zip 里的条目数**逐字对得上**
       ⇒ 不会重犯 rc5 那类「README 数字与实际不符」的缺陷（APP-073(c) 同类）。
    """
    import json
    import os
    import sys

    # 🔴 **单一数据源**：与 zip 脚本用**同一个** `pkg_exclude.iter_package_files`
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    import pkg_exclude as PE
    files = list(PE.iter_package_files(pkg_dir))
    n = len(files)
    b = sum(s for _r, s in files)

    models = os.path.join(pkg_dir, 'models')
    mn = 0
    mb = 0
    for dp, _dn, fn in os.walk(models):
        for f in fn:
            p = os.path.join(dp, f)
            mn += 1
            try:
                mb += os.path.getsize(p)
            except OSError:
                pass

    mi_lines = []
    for rel, info in sorted(model_identity.items()):
        if not info.get('exists'):
            continue
        mi_lines.append('  · %-34s ← %s（%s）' % (
            rel, info['source_model'], info['artifact']))

    if zip_bytes:
        zip_line = ('  · **zip**：**%.2f GB**（%d 字节，实测；打包后写回本文件，'
                    '压缩级不同会差几 KB）'
                    % (zip_bytes / 1e9, zip_bytes))
    else:
        zip_line = '  · **zip**：打包后由构建脚本写回本文件（精确字节数见 DELIVERY json）'

    txt = _TEMPLATE.format(
        version=ev.get('version', '1.0-rc6'),
        n_files=n,
        pkg_gb=round(b / 1e9, 3),
        pkg_gib=round(b / 1024 ** 3, 3),
        zip_line=zip_line,
        model_gb=round(mb / 1e9, 3),
        model_files=mn,
        ml_meteor=METEOR_LAKE['machine'],
        ml_iGPU=METEOR_LAKE['asr_iGPU_rtf'],
        ml_npu=METEOR_LAKE['asr_NPU_rtf'],
        ml_both=METEOR_LAKE['both_iGPU'],
        ml_concl=METEOR_LAKE['conclusion'],
        model_identity='\n'.join(mi_lines),
    )
    p = os.path.join(pkg_dir, 'README_perftest.txt')
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(txt)
    return {'path': p, 'bytes': os.path.getsize(p), 'n_entries': n,
            'pkg_bytes': b, 'pkg_gb': round(b / 1e9, 3),
            'pkg_gib': round(b / 1024 ** 3, 3),
            'model_bytes': mb, 'model_files': mn,
            'model_identity_lines': len(mi_lines)}


_TEMPLATE = r'''========================================================================
  Confucius4 LiveCaption · MiniMVP v{version} —— 性能测试版说明
========================================================================

【本包定位】
  这是 **MiniMVP v{version} 的性能测试构建**，用于在其他机器上测
  ASR / MT / TTS 的实时性能，**不是正式发布版**。
  · 正式验收、桌面快捷方式、其余 bug 修复 → 留到下一版。
  · 本版（rc6）**已修**（APP-098）：
      ① 三个后端**全部去掉 NVIDIA/CUDA 选项**（含 audio.cpp CUDA 与 CUDA TTS）
         ⇒ 只剩 Intel GPU / Intel NPU 两档；
      ② 克隆音色在 GUI 上**置灰**（提示「MiniMVP 不提供音色克隆」），
         默认用预设音色 A；CLI 传 `follow_speaker` 会**回落 A 并打一行日志**；
      ③ 目标语言扩到 **10 种**（zh/en/ja/ko/de/fr/es/pt/it/ru）；
      ④ 修**编码崩溃**：英文 Windows 上把输出重定向到文件时打印中文
         不再报 UnicodeEncodeError（入口处 reconfigure UTF-8）；
      ⑤ 删掉 **R2T2 残留** `models/tokenizer/`（hidden 2048；0.6B 读的是
         `asr06b-tokenizer`）；
      ⑥ ASR 编译完 encoder/decoder 后**打印 EXECUTION_DEVICES**；
      ⑦ ASR 与 MT **都放 GPU** 时给提示（建议 ASR 放 NPU），
         **不偷偷改用户选的设备**；
      ⑧ 本文件（README_perftest）按**实测**重写（体积/基准/新增 B 机实测）。
  · 本版**未修**（已知问题见「已知问题」一节）。

【包体积（实测，rc6）】
  · **解压后**：{n_files} 个文件 / **{pkg_gb} GB**（{pkg_gib} GiB）
      其中 `models/` = {model_files} 个文件 / {model_gb} GB
{zip_line}
  ⚠️ **口径更正（APP-098 二.5）**：旧版 README 写「rc5 9.97 GB」是
     **错的** —— 那是**模型目录字节数**被当成了**压缩后体积**。
     ⇒ 现在**压缩包与解压体积分开写**，且都以**实测**为准；
     ⇒ 「解压后 N 个文件 / X GB」与 zip 的条目数**同一份清单来源**
       （`pkg_exclude`）⇒ **数字必然对得上**。

【本包的 ASR：Qwen3-ASR-0.6B（mask2 INT8）】
  ⚠️ **更正**：旧版 README 写「rc5 未改 ASR 侧」**是错的** ——
     **rc5 就已经换成 0.6B 了**（APP-096），
     所以**旧基准表（rc3 的数字，R2T2 时代）不能代表本包**。
  【模型身份（MANIFEST 同源）】
{model_identity}
  · ASR 两个 bin 的 SHA256（验收 json → `asr_bin_sha`）：
      decoder 7FBEB8EF999DDFBA… / encoder 0B7463D6F952DD64…

【🔴 B 机（Meteor Lake 155H）实测 —— 结论：不能实时】
  机器：{ml_meteor}
  · **0.6B ASR，iGPU**：RTF **{ml_iGPU}**
  · **0.6B ASR，NPU**：RTF **{ml_npu}**
  · {ml_both}
  ⇒ {ml_concl}
  ⚠️ 这组数字**来自 reviewer 在 B 机的实测**（非本包自测）。
  ⚠️ **本包自带的 ASR 就是 0.6B** ⇒ 上面的 RTF **就是本包 ASR 的真实水平**。

【已知问题（rc6）】
  · ASR 在 iGPU/NPU 上 RTF 都 > 1 ⇒ **不能实时**（见上一节）。
  · ASR 与 MT 同占 iGPU 会 `CL_OUT_OF_RESOURCES` 崩溃 ⇒ **ASR 放 NPU**。
  · 首次 NPU 编译耗时很长（实测见验收 json）。
  · 克隆音色：本包**不提供**（GUI 置灰 / CLI 回落 A）。

【本机（A 机 Panther Lake）旧基准 —— ⚠️ 仅供参照，不能代表本包】
  机器：Intel Core Ultra 7 356H（Panther Lake，iGPU + NPU 第 5 代）
  音频：SPE 前 5 分钟（内部测试音频，**不在本包内**）
  ⚠️⚠️ **下列数字是 rc3 的 ASR（R2T2）下测的** ⇒ 本包 ASR 已换成 0.6B
     ⇒ **这些数字不能用来判断本包的性能** ⇒ 请以 B 机实测与目标机复测为准。
    · 总墙钟            381.86 s（音频 300 s）
    · ASR   RTF(计算)   0.833
             出字延迟中位 627 ms
             最大积压     1.8 s
             段数         46
    · MT    延迟中位    687.1 ms
             P95          1295.8 ms
             TTFT         190.3 ms
             吞吐         25.4 tok/s
    · TTS   合成 RTF 中位 1.0162   P95 1.3799   最大 1.5603
             首包延迟中位 0.5763 s   P95 0.8136 s   最大 1.0705 s
             提交 76 / 播完 76 / 丢弃 0 / 空句 0 / 失败 0
             **最大积压 105.12 s**
             结尾滞后 68.97 s
    · 配音内容判据      PASS（76 段全部非静音、无全零段）
    · 峰值内存          5212.6 MB（rc5 实测，ASR=NPU 臂，含 OV 编译期）
    · CPU 峰值/均值     本机未采集 ⇒ 请在目标机采一份

【许可与归属】
  见 `THIRD_PARTY.md`。
'''
