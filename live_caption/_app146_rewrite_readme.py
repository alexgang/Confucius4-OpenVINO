"""把候选目录 README 的「改动说明」历史节改写成 **MiniMVP v1.2** 口径。

🔴 为什么要改：候选目录的 README 是**完整版 v2.6 的全文**（含 v2.6/v2.5/…/v1.4
的历史改动说明、CUDA 相关内容、R2T2 措辞）⇒ 与 MiniMVP v1.2 的实际内容**不符**
⇒ 客户看到会误解（APP-146 §3：README/MANIFEST 写 v1.2、Hy-MT3、音色克隆、保留背景音）。

改动：
① 「## v2.6 改动说明」（出现 2 次）… 到「## 系统要求」之前 ⇒ 整段替换为
   **MiniMVP v1.2 改动说明**；
② 「已知限制」里 APP-124 §1 要求的措辞修正（去掉「A 机实测」等内部用语、
   把滞后数字改成实测口径）；
③ 补一条**已知限制**：EXT 插件侧只支持另一种识别模型 ⇒ 本包（只有 Qwen3-ASR-0.6B）
   的 **EXT ASR 不可用**（这是 v1.1.1 README 已载明的既有限制，v1.2 沿用）。

🔴 纪律：写前备份；定点替换 + 唯一命中断言；写后逐字节复核。
"""
import io, os, re, shutil, sys, hashlib, time, json

CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate'
TAG = 'app146_readme'
REPORT = []

ZH_CHANGES = """## MiniMVP v1.2 改动说明

**MiniMVP v1.2**（2026-11-26）。

### 1. 翻译模型升级为 Hy-MT3-1.8B

- 翻译模型由 **Hy-MT2-1.8B** 换成 **Hy-MT3-1.8B**（INT8 按通道量化）。
- **本包只带 Hy-MT3**（`models/mt/mt3-int8sym-cw-q`），不带 Hy-MT2。
- 质量与速度与上一代持平（GPU 约 38.7 tok/s、NPU 约 29.8 tok/s），翻译延迟与原来相当。

### 2. 保留背景音（bgkeep）

- 插件端「保留背景音」**默认开**：用分离模型把背景音乐/音效单独分出来，
  和配音混合后按延迟同步播放。
- 分离模型**随包分发**（`models/bgsep/`）；分离失败时**自动降级**为原声压低，配音照常。

### 3. 音色克隆

- 克隆所需的模型与代码**全部随包**；**包内克隆音色目录为空**（不含任何人的录音），
  首次使用时现场采集。
- 克隆音色跟随男女切换：没有标签的句子按**本句声纹**找最像的已登记音色，
  并有音高性别守门把明显错性别的音色换成同性别最像的。

### 4. EXT 升级到 v0.4.22

- 桥接侧识别模型查找顺序与本包一致（先 Hy-MT3，回退 Hy-MT2）。
- **NPU turbo 默认开启**（可用环境变量 `LIVECAP_NPU_TURBO=0` 关闭）。

### 5. 出厂默认设备（未变）

- **ASR = GPU.0（Intel 集显）／MT = GPU.0／TTS = NPU**，三个模块都可以在界面里改。
- 本包**不含 CUDA**（无 NVIDIA 显卡依赖），语音输出走 OpenVINO 的 NPU 后端。

"""

EN_CHANGES = """## What's new in MiniMVP v1.2

**MiniMVP v1.2** (2026-11-26).

### 1. Translation model upgraded to Hy-MT3-1.8B

- The translation model changes from **Hy-MT2-1.8B** to **Hy-MT3-1.8B**
  (INT8 per-channel).
- **This package ships Hy-MT3 only** (`models/mt/mt3-int8sym-cw-q`).
- Quality and speed are on par with the previous generation
  (~38.7 tok/s on GPU, ~29.8 tok/s on NPU); translation latency is unchanged.

### 2. Keep background audio (bgkeep)

- The plugin's "keep background audio" switch is **on by default**: a separation
  model splits the background music / effects out, and they are mixed with the
  dubbing and played back with the configured delay.
- The separation model **ships inside the package** (`models/bgsep/`); if
  separation fails it **degrades gracefully** to ducking the original audio.

### 3. Voice cloning

- Everything cloning needs **ships inside the package**; the **clone voice
  folder is empty** (it contains nobody's recordings) and voices are captured
  live on first use.
- Clone voices follow male/female switches: unlabelled sentences pick the
  closest registered voice by their own embedding, with a pitch gender gate.

### 4. EXT upgraded to v0.4.22

- The bridge looks up the translation model in the same order as this package
  (Hy-MT3 first, Hy-MT2 as fallback).
- **NPU turbo is on by default** (set `LIVECAP_NPU_TURBO=0` to turn it off).

### 5. Factory default devices (unchanged)

- **ASR = GPU.0 (Intel iGPU) / MT = GPU.0 / TTS = NPU**; all three can be
  changed in the UI.
- This package contains **no CUDA**; speech output runs on the OpenVINO NPU.

"""

# 已知限制：APP-124 §1 的措辞修正（滞后数字 + 内部用语）
ZH_LIMIT_OLD = """- 翻译开启后整体 RTF 会上升约 0.14；若同时把 ASR 和翻译都放集显，机器负载较重时可能出现音频积压。"""
ZH_LIMIT_NEW = """- 讲话密集、持续不停顿时，配音会逐渐落后。10 分钟连续讲话实测，最大滞后约 45 s～2 min，
  讲完后会继续播完积压内容。讲话中的停顿能让配音追上。
- 翻译开启后整体 RTF 会上升约 0.14；若同时把 ASR 和翻译都放集显，机器负载较重时可能出现音频积压。"""

ZH_EXT_LIMIT = """- **插件（EXT）侧的语音识别在本包不可用**：插件侧的引擎接线目前只支持另一种识别模型，
  而本包只带 **Qwen3-ASR-0.6B（stateful）** ⇒ 启动桥接后日志会报引擎构造失败、
  预热不完整，**不会出现**「真实引擎已接线」与「TTS 就绪」。应用本身的字幕、
  翻译与朗读功能**不受影响**。
"""

EN_EXT_LIMIT = """- **Speech recognition in the plugin (EXT) is not available in this package**:
  the plugin-side engine wiring currently supports a different recognition model,
  while this package ships **Qwen3-ASR-0.6B (stateful)** only. After starting
  the bridge the log reports an engine construction failure and warm-up stays
  incomplete. The application's own captions, translation and spoken output are
  **not affected**.
"""


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def write_atomic(p, data):
    tmp = p + '.tmp_' + TAG
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, p)


def rewrite(path, changes_block, marker_from, marker_to, extra_edits, label):
    src = read(path)
    text = src.decode('utf-8')
    NL = '\r\n' if '\r\n' in text else '\n'
    # 🔴 幂等：若已是新形态（本文件的 title 已在），则**跳过**（不重复改写）
    if changes_block.split('\n')[0].strip() in text:
        REPORT.append({'file': path, 'status': 'already_applied',
                       'applied': ['（幂等跳过）']})
        return
    i = text.find(marker_from)
    j = text.find(marker_to, i + 1)
    assert i >= 0, '[%s] 起点标记未找到：%r' % (label, marker_from[:40])
    assert j > i, '[%s] 终点标记未找到' % label
    old_seg = text[i:j]
    new_text = text[:i] + changes_block + text[j:]
    applied = ['改动说明整段替换']
    for old, new, tag in extra_edits:
        o = old.replace('\n', NL)
        n = new.replace('\n', NL)
        cnt = new_text.count(o)
        if cnt != 1:
            REPORT.append({'file': path, 'edit': tag, 'status': 'SKIP',
                           'reason': '命中 %d 次' % cnt})
            continue
        new_text = new_text.replace(o, n, 1)
        applied.append(tag)
    data = new_text.encode('utf-8')
    bak = path + '.bak_' + TAG
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    write_atomic(path, data)
    assert read(path) == data, '写后复核失败'
    REPORT.append({'file': path, 'status': 'patched', 'applied': applied,
                   'bytes_before': len(src), 'bytes_after': len(data),
                   'sha256': hashlib.sha256(data).hexdigest(),
                   'old_segment_bytes': len(old_seg.encode('utf-8'))})


def main():
    zh = os.path.join(CAND, 'README_zh.md')
    rewrite(zh, ZH_CHANGES, '## v2.6 改动说明', '## 系统要求',
            [(ZH_LIMIT_OLD, ZH_LIMIT_NEW, '已知限制·滞后措辞修正'),
             ('第三方组件及许可见 `THIRD_PARTY.md`。',
              ZH_EXT_LIMIT + '\n第三方组件及许可见 `THIRD_PARTY.md`。',
              '已知限制·EXT ASR 不可用')],
            'README_zh')

    en = os.path.join(CAND, 'README_en.md')
    # 英文版：找到改动说明起点与「系统要求」对应的英文节
    m_from = "## What's new in v2.6"
    if m_from not in read(en).decode('utf-8'):
        m_from = "## v2.6 changes"
    rewrite(en, EN_CHANGES, m_from, '## System requirements',
            [("Third-party components and licenses: see `THIRD_PARTY.md`.",
              EN_EXT_LIMIT + "\nThird-party components and licenses: see `THIRD_PARTY.md`.",
              '已知限制·EXT ASR 不可用')],
            'README_en')

    out = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app146_readme_rewrite.json'
    io.open(out, 'w', encoding='utf-8', newline='\n').write(
        json.dumps({'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'steps': REPORT}, ensure_ascii=False, indent=2))
    for r in REPORT:
        print('%-24s %s %s' % (os.path.basename(r['file']), r['status'],
                               r.get('applied', r.get('reason'))))
    print('\n落盘 ->', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
