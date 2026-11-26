"""APP-149 第 5 项 ＋ APP-150 §3：**更新候选目录 README**。

① 删掉「插件（EXT）侧的语音识别在本包不可用」那段（EXT v0.4.23 已支持 0.6B）
   ⇒ 改为写明 **EXT 用的是包内的 Qwen3-ASR 0.6B**；
② APP-150 §3：「设备配置 / 常见问题」里加 **NPU 排障两行**
   （NPU 配音有杂音/异常 ⇒ 改 TTS=GPU.0，或设 `LIVECAP_NPU_TURBO=0`），
   **用客户能看懂的话**，不出现内部编号。

🔴 纪律：定点替换 + 唯一命中断言；写前备份；写后逐字节复核。
"""
import io
import os
import shutil

CAND = os.environ['APPCAND']
TAG = 'app149_readme'

ZH_OLD = """- **插件（EXT）侧的语音识别在本包不可用**：插件侧的引擎接线目前只支持另一种识别模型，
  而本包只带 **Qwen3-ASR-0.6B（stateful）** ⇒ 启动桥接后日志会报引擎构造失败、
  预热不完整，**不会出现**「真实引擎已接线」与「TTS 就绪」。应用本身的字幕、
  翻译与朗读功能**不受影响**。
"""

ZH_NEW = """- **插件（EXT）用的识别模型就是本包里的 Qwen3-ASR-0.6B**（stateful，INT8）：
  桥接启动时会自动识别本包带的是哪一种识别模型并加载对应的引擎，
  所以「应用」和「插件」两条路用的是同一套识别模型，不会出现两边不一致。
"""

EN_OLD = """- **Speech recognition in the plugin (EXT) is not available in this package**:
  the plugin-side engine wiring currently supports a different recognition model,
  while this package ships **Qwen3-ASR-0.6B (stateful)** only. After starting
  the bridge the log reports an engine construction failure and warm-up stays
  incomplete. The application's own captions, translation and spoken output are
  **not affected**.
"""

EN_NEW = """- **The plugin (EXT) uses the Qwen3-ASR-0.6B model that ships in this package**
  (stateful, INT8): the bridge detects which recognition model the package
  contains and loads the matching engine, so the application and the plugin use
  the same recognition model.
"""

# APP-150 §3：NPU 排障两行（插在「已知限制」之前 ⇒ 更醒目；用客户能懂的话）
ZH_TROUBLE = """## 设备配置与常见问题

- **语音输出（朗读）用的是 NPU 时，如果听到杂音、忽快忽慢或声音异常**：
  先在界面里把「语音输出」的设备改成 **GPU.0（Intel 集显）**，再试一次；
  如果仍然异常，可以把环境变量 `LIVECAP_NPU_TURBO` 设为 `0` 后重新启动，
  这会关闭 NPU 的加速模式（部分机型或较旧的驱动上加速模式可能带来杂音）。
- **识别不出声音或识别很慢**：确认「ASR 识别」的设备是 **GPU.0（Intel 集显）**，
  并确认电脑的麦克风没有被静音。

"""

EN_TROUBLE = """## Device setup and common questions

- **If the spoken output (NPU) has noise, uneven speed or sounds distorted**:
  first switch "Speech output" to **GPU.0 (Intel iGPU)** in the UI and try again.
  If it still sounds wrong, set the environment variable `LIVECAP_NPU_TURBO` to
  `0` and restart — this turns off the NPU acceleration mode (which can cause
  noise on some models or with older drivers).
- **If nothing is recognised or recognition is very slow**: make sure "ASR" is
  set to **GPU.0 (Intel iGPU)** and that the microphone is not muted.

"""


def patch(path, edits):
    raw = io.open(path, encoding='utf-8', newline='').read()
    NL = '\r\n' if '\r\n' in raw else '\n'
    text = raw
    applied = []
    for old, new, tag in edits:
        o = old.replace('\n', NL)
        n = new.replace('\n', NL)
        cnt = text.count(o)
        if cnt != 1:
            print('   ★ [%s] 命中 %d 次 ⇒ 跳过' % (tag, cnt))
            continue
        text = text.replace(o, n, 1)
        applied.append(tag)
    data = text.encode('utf-8')
    bak = path + '.bak_' + TAG
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    tmp = path + '.tmp_' + TAG
    io.open(tmp, 'wb').write(data)
    os.replace(tmp, path)
    assert io.open(path, 'rb').read() == data, '写后复核失败：%s' % path
    print('   %s：%s' % (os.path.basename(path), applied))
    return applied


def main():
    zh = os.path.join(CAND, 'README_zh.md')
    en = os.path.join(CAND, 'README_en.md')
    print('更新 README：')
    patch(zh, [
        (ZH_OLD, ZH_NEW, '删「EXT ASR 不可用」段＋改写'),
        ('## 已知限制\n', ZH_TROUBLE + '## 已知限制\n', '加 NPU 排障两行'),
    ])
    patch(en, [
        (EN_OLD, EN_NEW, '删「EXT ASR not available」段＋改写'),
        ('## Known limitations\n', EN_TROUBLE + '## Known limitations\n',
         '加 NPU 排障两行'),
    ])
    print('OK')


if __name__ == '__main__':
    main()
