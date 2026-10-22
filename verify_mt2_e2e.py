"""v1.3 客户包内翻译端到端实测：直接调用**包内** translator + **包内** MT2 模型。

目的：确认打包后的 v1.3 包能真正加载 Hy-MT2-1.8B 并输出译文（而不是只通过 --check）。
运行：<包>/python/python.exe -s verify_mt2_e2e.py [device]
"""
import os
import sys
import time

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
sys.path.insert(0, os.path.join(PKG, 'app'))

import translator as T  # noqa: E402

SENTS = [
    'The U.S. economy grew 3.5 percent last quarter.',
    'Dr. Smith joined at 9 a.m. today.',
    'We shipped the 28 core modules to customers.',
    'It cost 1.5 million dollars in total.',
    'Please translate this sentence into Chinese.',
]


def main():
    print('=' * 70)
    print('v1.3 翻译端到端实测（包内模型 + 包内代码）')
    print('=' * 70)
    print('PKG            =', PKG)
    print('DEFAULT_MODEL  =', T.DEFAULT_MODEL)
    print('模型目录存在   :', os.path.isdir(T.DEFAULT_MODEL))
    print('可用 MT 后端   :', list(T.MT_ENGINES.keys()))
    print()

    device = sys.argv[1] if len(sys.argv) > 1 else 'GPU.0'
    tr = T.HunyuanTranslator(device=device)
    print(f'加载完成 {tr.load_s:.1f}s  device={device}')
    print()

    lats, ttfts, empties = [], [], []
    for s in SENTS:
        r = tr.translate(s, 'zh')
        lats.append(r['lat_ms'])
        ttfts.append(r['ttft_ms'])
        if not r['text'].strip():
            empties.append(s)
        print(f'原文: {s}')
        print(f'译文: {r["text"]}')
        print(f'      lat={r["lat_ms"]:.0f}ms ttft={r["ttft_ms"]:.0f}ms '
              f'in={r["n_in"]} out={r["n_out"]}')
        print()

    lats.sort()
    ttfts.sort()
    n = len(lats)
    med = lats[n // 2] if n % 2 else (lats[n // 2 - 1] + lats[n // 2]) / 2
    medt = ttfts[n // 2] if n % 2 else (ttfts[n // 2 - 1] + ttfts[n // 2]) / 2
    print('-' * 70)
    print(f'共 {n} 句  延迟中位 {med:.0f} ms  TTFT 中位 {medt:.0f} ms  最大 {lats[-1]:.0f} ms')
    print(f'空输出 {len(empties)} 句')

    print()
    print('断句自检（包内 split_sentences，应为新版逻辑）：')
    for s in SENTS:
        print('  ', T.split_sentences(s))

    tr.close()
    print()
    ok = (not empties) and med < 5000
    print('结论：', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
