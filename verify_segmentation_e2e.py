"""端到端验证：用真实翻译模型跑断句改造前后的对比。

目的：确认改造不只是「切分好看」，而是**译文真的变好**。

跑法：
    python verify_segmentation_e2e.py
"""
import os
import sys
import time

sys.path.insert(0, 'live_caption')
import translator as T


def legacy_split(text):
    """旧版断句（保留一份做对照）：见改造前的 _SENT_RE 逻辑。"""
    import re
    SENT_END = '.?!。？！；;…'
    SENT_RE = re.compile(r'[^' + re.escape(SENT_END) + r']*[' + re.escape(SENT_END) +
                          r']+|[^' + re.escape(SENT_END) + r']+')
    out = []
    for piece in SENT_RE.findall(text or ''):
        if not piece.strip():
            continue
        if out and len(re.sub(r'\s', '', piece)) < 4:
            out[-1] += piece
        else:
            out.append(piece.strip())
    return out


CASES = [
    ('It cost 1.5 million dollars. We raised 3.2 billion last year.',
     '小数点'),
    ('The U.S. economy grew 3.5 percent. The U.K. market fell slightly.',
     '点分缩写'),
    ('Dr. Smith joined at 9 a.m. today. Prof. Wang will present at 3 p.m.',
     '称谓与时间缩写'),
    ('We shipped no. It works. The team is happy.',
     '高风险短词'),
]


def main():
    print('=' * 68)
    print(' 端到端：断句改造前 vs 改造后（真实翻译模型）')
    print('=' * 68)

    dev = T.MT_ENGINES.get('auto', {}).get('model') or T.DEFAULT_MODEL
    if not os.path.isdir(dev):
        print(' 翻译模型目录不存在：%s' % dev)
        return 2
    print(' 模型目录：%s' % dev)

    tr = T.HunyuanTranslator(dev, 'GPU')
    try:
        for text, label in CASES:
            print('\n' + '-' * 68)
            print(' 【%s】' % label)
            print(' 原文：%s' % text)

            old = legacy_split(text)
            new = T.split_sentences(text)
            print(' 旧切分：%r' % (old,))
            print(' 新切分：%r' % (new,))

            print(' -- 逐句翻译对比 --')
            for i, s in enumerate(new):
                t0 = time.time()
                r = tr.translate(s, 'zh')
                dt = (time.time() - t0) * 1000
                print('   新[%d] %s' % (i, s))
                print('        -> %s  (%.0f ms)' % (r, dt))
            for i, s in enumerate(old):
                if s in new:
                    continue
                t0 = time.time()
                r = tr.translate(s, 'zh')
                dt = (time.time() - t0) * 1000
                print('   旧[%d] %s' % (i, s))
                print('        -> %s  (%.0f ms)' % (r, dt))
    finally:
        try:
            tr.close()
        except Exception:
            pass

    print('\n' + '=' * 68)
    print(' 端到端对比结束')
    print('=' * 68)
    return 0


if __name__ == '__main__':
    sys.exit(main())
