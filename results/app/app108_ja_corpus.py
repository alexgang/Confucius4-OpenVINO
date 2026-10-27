# -*- coding: utf-8 -*-
"""APP-030 实测用**日文测试语料**（reviewer 明文规格）。

## reviewer 的规格（APP-030「### 4. 验收」A/B 项）

> 准备 ≥20 句日文测试句
> - ≥5 句 **≤8 字纯假名短句**
> - ≥4 句 **含数字/日期/百分比**
> - ≥4 句 **片假名长词**
> - ≥3 句 **≥60 字长句**，其中 **1 句无标点**
> - ≥3 句 **混英文缩写**（CPU/AI）

🔴 **为什么要专门造这份语料**：reviewer 的原始实测里，
「短的纯假名句最危险」（id=65 只有 7 字 ⇒ 判 en ⇒ 用 English token 读假名
⇒ 分布外 ⇒ EOS 不稳 ⇒ 偶发撞 2048 帧上限）。
⇒ **必须包含「短的纯假名句」才能复现原缺陷**。

🔴 **语料落盘位置**：`shared/`（APP-026 规定各模块共用同一份素材）
   ⇒ 放 `shared/` 而不是仓库内（回放产物一律写仓库外，APP-005①）。
🔴 **不入客户包**：在 `shared/` 下 ⇒ 天然不在包内；
   且不含任何会议内容（**自造句**）⇒ 不触发内部素材闸门。

## 其它语言的回归语料（中文/英文各 10 句）

APP-030 明文：「中文和英文各 10 句回归：改后帧数/s/字与改前一致（无回退）」。
"""

JA_SENTENCES = [
    # ── ① ≤8 字纯假名短句（≥5 句）—— **原缺陷的高发区** ──────────
    'ありがとう',
    'こんにちは',
    'おはようございます',
    'はい、そうです',
    'そうします',
    'わかりました',
    'すみません',
    '，动きます',

    # ── ② 含数字/日期/百分比（≥4 句）────────────────────────────
    '2026年の売上は52%増えました',
    '会議は3時から始まります',
    '価格は1980円です',
    '在庫は1000個あります',
    '効率は15パーセント向上しました',
    '2026年10月27日にリリースします',

    # ── ③ 片假名长词（≥4 句）────────────────────────────────────
    '.Processor UNAVAILABLE',   # 占位，下面替换
    'ハードウェアアクセラレーションが有効になりました',
    'ソフトウェアアップデートが必要です',
    'コンパイラ最適化.toggleをオンにしてください',
    'ネットワーク Throughput が低下しました',
    '“GPIOingenius” の再起動が必要です',

    # ── ④ ≥60 字长句（≥3 句，其中 1 句无标点）──────────────────
    '今天的会议主要讨论第四季度的产品路线图'
    '，包括新的芯片量产计划'
    '、客户样品交付时间表'
    '，以及市场份额的进一步提升计划和后续的研发投入安排',
    'ええ、那天是我们团队第一次一起讨论这个项目'
    '，大家都很兴奋'
    '，所以就决定马上开始做原型验证'
    '，然后在下个季度给出初步的结果'
    '，同时把风险点也列出来供大家评审',
    # ⚠️ **无标点**的长句（reviewer 明文要求「其中 1 句无标点」）
    '今夜は engineers がすべての '
    'semiconductor design と process optimization を'
    '完了させその報告書を'
    'すべての engineers へ電子メールで送ります',
    '彼は昨日の会議で、新しいアーキテクチャの'
    '設計方針について'
    ' teams の具体的な実装方法 '
    'と必要な検証項目を詳しく説明し'
    '質問にも逐一答えました',

    # ── ⑤ 混英文缩写（≥3 句）────────────────────────────────────
    'CPUとGPUの性能を比較します',
    'AIモデルの推論速度は速いです',
    'このAPIはNPUに対応しています',
    'VRAMの使用量を測定します',
    'FP16とINT8の精度差を確認します',
]

# ⚠️ 上面的占位符必须被替换掉（不能留在语料里）。
_JA_PLACEHOLDER_FIX = [
    ('.Processor UNAVAILABLE', 'プロセッサーが利用できません'),
]


def _fix(sentences):
    out = []
    for s in sentences:
        for a, b in _JA_PLACEHOLDER_FIX:
            s = s.replace(a, b)
        out.append(s)
    return out


JA = _fix(JA_SENTENCES)

ZH_SENTENCES = [
    '这是中文回归测试句子，用来验证帧数与每字秒数没有回退。',
    '今天的会议主要讨论第四季度产品路线图和客户样品交付时间表。',
    '请把这段文字转换成英文并朗读出来。',
    '系统性能在压力测试后下降了百分之十五左右。',
    '人工智能模型的推理速度取决于硬件加速器的配置。',
    '芯片的功耗优化是这一代产品最重要的指标之一。',
    '我们需要在下个季度完成流片并交付工程样品。',
    '这段文字的长度大约是二十个汉字左右。',
    '语音输出的首包延迟与合成时间成线性关系。',
    '质量份额和客户样品数量都要如实记录。',
]

EN_SENTENCES = [
    'This is an English regression sentence used to verify frame counts.',
    'The meeting today covers the product roadmap for the fourth quarter.',
    'Please convert this paragraph into English and read it aloud.',
    'System performance dropped by about fifteen percent under load.',
    'The inference speed of the model depends on the accelerator setup.',
    'Chip power efficiency is the most important metric this generation.',
    'We need to finish tape out and deliver engineering samples.',
    'This sentence contains roughly twenty English words in total.',
    'First packet latency is proportional to the synthesis time.',
    'Market share and customer sample counts must be recorded honestly.',
]


def stats():
    """返回语料的实测统计（供 STATUS 引用，不含推理）。"""
    import unicodedata

    def counts(s):
        kana = sum(1 for c in s if 0x3040 <= ord(c) <= 0x30FF)
        han = sum(1 for c in s if 0x4E00 <= ord(c) <= 0x9FFF)
        latin = sum(1 for c in s if c.isascii() and c.isalpha())
        return kana, han, latin

    short_kana = [s for s in JA
                  if len(s) <= 8 and counts(s)[0] > 0 and counts(s)[1] == 0]
    with_num = [s for s in JA if any(c.isdigit() for c in s)]
    long60 = [s for s in JA if len(s) >= 60]
    no_punct = [s for s in long60
                if not any(c in '。、，,.!？?' for c in s)]
    with_abbr = [s for s in JA
                 if any(a in s for a in ('CPU', 'GPU', 'AI', 'API', 'NPU',
                                        'VRAM', 'FP16', 'INT8'))]
    katakana_long = [s for s in JA
                     if counts(s)[0] >= 4 and len(s) >= 12]
    return dict(
        ja_total=len(JA), zh_total=len(ZH_SENTENCES), en_total=len(EN_SENTENCES),
        ja_short_kana=len(short_kana), ja_with_number=len(with_num),
        ja_katakana_long=len(katakana_long), ja_ge60=len(long60),
        ja_ge60_no_punct=len(no_punct), ja_with_abbr=len(with_abbr),
        ja_short_kana_list=short_kana,
        ja_no_punct_examples=no_punct[:2],
    )


if __name__ == '__main__':
    import json
    import os
    print(json.dumps(stats(), ensure_ascii=False, indent=2))
    out = os.path.join(os.environ.get('LIVECAP_SHARED', r'C:\Users\Trekker-PTL\shared'),
                       'app030_ja_corpus.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dict(ja=JA, zh=ZH_SENTENCES, en=EN_SENTENCES),
                  f, ensure_ascii=False, indent=2)
    print('语料已写入:', out)
