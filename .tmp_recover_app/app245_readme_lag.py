#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""§245：按 APP-150 §2 用**实测滞后**改写候选包 README（中/英）。

reviewer 原文（APP-150 §2 末条）：
> 报媒体结束时的积压秒数和排空用时。如果明显超过 v1.1.1 说明里写的「讲话密集时滞后约 1–2 分钟」，
> README 和发客户说明要按实测改写。

实测（`results/app/app245_gate_metrics.json`，10 分钟片段，TTS=NPU 默认档）：

| 臂 | 滞后 p50 | p90 | 最大 | 排空用时 |
|---|---|---|---|---|
| 关背景音 | 29.2 s | 100.6 s | 160.8 s | 84.3 s |
| 开背景音 | 51.2 s | 166.9 s | 224.8 s | 116.6 s |
| 开 + 克隆 | 95.0 s | 274.2 s | 337.9 s | 177.8 s |

🔴 纪律：先备份 → 唯一命中断言 → 行尾纯 LF 保持 → `ast` 无关（md）⇒ 用逐字节复核。
"""
import io
import os
import shutil
import sys

CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate'

ZH_OLD = ("- 讲话密集、持续不停顿时，配音会逐渐落后。10 分钟连续讲话实测，最大滞后约 45 s～2 min，\n"
          "  讲完后会继续播完积压内容。讲话中的停顿能让配音追上。")
ZH_NEW = ("- 讲话密集、持续不停顿时，配音会逐渐落后。**v1.2 在本机（Core Ultra 7 356H，TTS=NPU 默认档）\n"
          "  的 10 分钟连续讲话实测**：滞后中位数 29 s（关背景音）／51 s（开背景音）／95 s（开背景音＋克隆），\n"
          "  最坏 161 s／225 s／338 s；讲完后会继续播积压内容，媒体结束后约 1.4～3.0 分钟才播完。\n"
          "  讲话中的停顿能让配音追上；想更跟得上，可关掉「保留背景音」或不使用克隆音色。")

EN_ANCHOR = ("- Validated on one hardware platform (Core Ultra 7 356H) only.\n")
EN_NEW = (EN_ANCHOR +
          "- **Dubbing falls behind during dense, continuous speech.** Measured in v1.2 on the same\n"
          "  reference machine (default TTS = NPU), 10 minutes of non-stop speech: median lag 29 s\n"
          "  (background off) / 51 s (background on) / 95 s (background on + cloned voice), worst case\n"
          "  161 s / 225 s / 338 s. Playback continues after the media ends and takes about 1.4–3.0\n"
          "  minutes to finish the backlog. Pauses let the dubbing catch up; turning background\n"
          "  keeping or voice cloning off makes it keep up better.\n")


def patch(name, old, new, must_have_new):
    p = os.path.join(CAND, name)
    with io.open(p, encoding='utf-8', newline='') as fh:
        src = fh.read()
    if must_have_new in src:
        print('SKIP %s：已是新版' % name)
        return True
    if src.count(old) != 1:
        print('FAIL %s：锚点命中 %d 次' % (name, src.count(old)))
        return False
    out = src.replace(old, new, 1)
    # 真不变量
    assert '\r' not in out, 'CRLF 被引入'
    assert out.count(new) == 1
    assert must_have_new in out
    assert len(out) > len(src)
    bak = p + '.bak_app245_lag'
    shutil.copy2(p, bak)
    tmp = p + '.app245.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(out)
    os.replace(tmp, p)
    with io.open(p, encoding='utf-8', newline='') as fh:
        after = fh.read()
    ok = (after == out and after.count('\r') == 0)
    print('%s %s：%d -> %d B（备份 %s）'
          % ('OK' if ok else 'FAIL', name, len(src.encode()), len(after.encode()),
             os.path.basename(bak)))
    return ok


def main():
    a = patch('README_zh.md', ZH_OLD, ZH_NEW, '滞后中位数 29 s')
    b = patch('README_en.md', EN_ANCHOR, EN_NEW, 'median lag 29 s')
    return 0 if (a and b) else 3


if __name__ == '__main__':
    sys.exit(main())
