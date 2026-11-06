# -*- coding: utf-8 -*-
"""一次性脚本：修正 `speaker_voice.py` 里 APP-075 的常量说明注释。

🔴 **为什么要脚本改**：文件里有大量 🔴/🔴🔴 等 emoji ⇒ Edit 工具的
old_string 极易因**字符数不同**而匹配失败 ⇒ 改用**行号定位 + 唯一命中断言**
的定点替换（记忆铁律：仓库 ⇄ 客户包 两份独立副本，只做定点替换）。
"""
import io
import os
import sys

PATH = os.path.join(r'C:\Users\Trekker-PTL\confucius4-openvino',
                    'live_caption', 'speaker_voice.py')

NEW_BLOCK = '''# \U0001f534\U0001f534\U0001f534 APP-071(c) / APP-075(a)：**登记门槛**（防止「用错人的音频登记音色」）
# ══════════════════════════════════════════════════════════════
# \U0001f4cc 背景（实测，见 `results/app/_app293_label_overlap.json`）：
#    ASR 给 seg1（9.6–19.2 s）打的标签是 **S2**，但 `spk_conf=0.1292`
#    ⇒ 该段的**真实说话人是女声**（实测 F0 197.53 Hz，GT = S1）。
#    旧逻辑**不看 `spk_conf`** ⇒ 拿这段女声给「S2」登记了 x-vector
#    ⇒ 之后**所有**男声句子都用女声播出（用户实测「男声听上去也是女声」）。
#
# \U0001f534\U0001f534\U0001f534 APP-075(a) 的要求是**三件事同时成立**才可登记：
#    ① `spk_conf ≥ REG_CONF_MIN`；
#    ② 该段落在 ASR 给的 `clean_ranges` **内**；
#    ③ 去掉**切换点前后 `SWITCH_GUARD_S`** 之后，仍有**连续 ≥ REG_MIN_CONT_S**
#       的音频。
#
# \U0001f534\U0001f534\U0001f534\U0001f534 **实测硬证据：①（conf 门槛）与③（边界守卫）**都**挡不住**
#    **「标签已切给新人、但音频还属于旧人」的那几段**：
#
#    | 段 | 时间(s) | `spk_conf` | 边界守卫 | 真实性别（实测 F0） |
#    |---|---|---|---|---|
#    | seg1 | 9.6–19.2 | 0.1292 | 被挡 | 女 197.53 Hz |
#    | **seg2** | 19.2–25.6 | **0.8996** | **挡不住** | **女 175.82 Hz** |
#    | **seg3** | 25.6–32.0 | **0.9104** | **挡不住** | **女 188.24 Hz** |
#    | seg4 | 32.0–38.4 | 0.3757 | 被挡 | 中性 168.42 Hz |
#    | seg5 | 38.4–44.8 | 0.4016 | 挡不住 | 男 108.84 Hz |
#    | seg6–14 | 44.8–102.4 | 0.73–0.95 | 挡不住 | **男 100–135 Hz** |
#
#    ⇒ S1→S2 的切换点只有 **9.6 s**（S2 的 seg1 之后**再无换人**）
#      ⇒ seg2/seg3（19.2–32.0 s）**离切换点很远** ⇒ **守卫挡不住**
#      ⇒ 且它们的 `spk_conf` 高达 0.90/0.91 ⇒ **conf 门槛也挡不住**
#    ⇒ **①③ 只能挡掉 seg1/seg4 两段**，女声的 seg2/seg3 **必然**成为合格段。
#    ⇒ \U0001f534 **真正能选对人的是「择段策略」**（见 `registration_ticket()`）：
#      **最长**合格段 = 男声 57.6 s（seg6–14）＞ 女声 12.8 s（seg2–3）
#      ⇒ 登记到**对的人**。
#
# \U0001f534 `REG_CONF_MIN`：**登记用的 `spk_conf` 门槛**。
#    依据（`_app292_threshold_probe.json`，app250 设备实测段表）：
#      · 必须 **> 0.3217**（S4 首现段的 conf）⇒ 才能挡住**全部三处**
#        「切换边界首现」的高危段（S2 0.1292 / S3 0.0602 / S4 0.3217）；
#      · 必须 **≤ 0.6** ⇒ 门槛再高，S4 就**再也攒不够 2.5 s 连续合格音频**
#        （实测 0.7 ⇒ S4 最长连续 0.0 s ⇒ 该说话人**永远登记不上**）。
#    ⇒ 可行窗口 **[0.4, 0.6]** ⇒ 取中点 **0.5**（余量最大）。
#    \U0001f534 **口径声明（APP-075(c)）**：该窗口**只来自一份 5 分钟样本**
#      （`SPE_mix_3303_3603.wav`）⇒ 见 §140 的第二份材料复验
#      （ASR-122 `asr122_asr050_regression.json`，900 s / 3 clip / 136 段）。
#    ⚠️ **语义澄清（ASR-048/049 明文）**：`spk_conf` = **与已登记者的最大余弦
#      相似度** ⇒ **低 = 新人**，**不是**「标签不可信」
#      ⇒ 所以门槛的**唯一作用**是「**选哪段音频登记**」（APP-075(b) 明文）
#      ⇒ **绝不**因为首段 conf 低就不登记、不播。
REG_CONF_MIN = 0.5
'''


def main():
    with io.open(PATH, 'r', encoding='utf-8', newline='') as f:
        raw = f.read()
    lines = raw.split('\n')
    # 定位常量块：从「APP-071(c) / APP-075(a)」那行到「REG_CONF_MIN = 0.5」
    start = None
    end = None
    for i, ln in enumerate(lines):
        if start is None and 'APP-071(c) / APP-075(a)' in ln and ln.startswith('#'):
            start = i
        if start is not None and ln.strip() == 'REG_CONF_MIN = 0.5':
            end = i
            break
    assert start is not None, '未找到常量块起点'
    assert end is not None, '未找到 REG_CONF_MIN = 0.5'
    assert end > start, '区间异常'
    print('[定位] 行 %d .. %d' % (start + 1, end + 1))
    old = '\n'.join(lines[start:end + 1])
    assert '0.9104' in old and '全部落在守卫内' in old, '旧块内容不符合预期'
    new_lines = NEW_BLOCK.rstrip('\n').split('\n')
    lines[start:end + 1] = new_lines
    out = '\n'.join(lines)
    # 🔴 行尾保持不变（本仓库工作副本是 LF；用 newline='' 读写可保原样）
    with io.open(PATH, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print('[完成] 写入 %d 行' % len(new_lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
