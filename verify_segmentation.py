"""断句改造验证：小数点/缩写不误切、段长上限、碎片合并。

跑法：
    python verify_segmentation.py
"""
import re
import sys

sys.path.insert(0, 'live_caption')
from translator import (split_sentences, ends_sentence, MIN_SENT_CHARS,
                        MAX_SEG_WORDS, _find_cut_points, _is_abbrev_boundary,
                        _is_decimal_point, norm_key)

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(('  [ OK ] ' if cond else '  [FAIL] ') + name + (('  -- ' + detail) if detail else ''))
    return bool(cond)


def main():
    print('=' * 66)
    print(' 断句改造验证')
    print('=' * 66)

    print('\n[1] 小数点不误切（此前是已确认的真缺陷）')
    cases = [
        ('It cost 1.5 million dollars.', ['It cost 1.5 million dollars.']),
        ('The U.S. economy grew 3.5 percent.',
         ['The U.S. economy grew 3.5 percent.']),
        ('Pi is 3.14 and e is 2.71.', ['Pi is 3.14 and e is 2.71.']),
        ('Version 1.2.3 is out.', ['Version 1.2.3 is out.']),
    ]
    for text, want in cases:
        got = split_sentences(text)
        check('「%s」切分正确' % text, got == want,
              '得到 %r' % (got,))

    print('\n[2] 缩写不误切')
    cases = [
        ('Dr. Smith joined at 9 a.m. today.',
         ['Dr. Smith joined at 9 a.m. today.']),
        ('Mr. Li met Prof. Wang in the U.S. yesterday.',
         ['Mr. Li met Prof. Wang in the U.S. yesterday.']),
        ('We waited 5 p.m. for the bus.',
         ['We waited 5 p.m. for the bus.']),
    ]
    for text, want in cases:
        got = split_sentences(text)
        check('「%s」切分正确' % text, got == want, '得到 %r' % (got,))

    print('\n[3] 正常句子仍能切开')
    cases = [
        ('Hello world. How are you?', ['Hello world.', 'How are you?']),
        ('It works! Great.', ['It works!', 'Great.']),
        ('第一句。第二句！第三句？', ['第一句。', '第二句！', '第三句？']),
    ]
    for text, want in cases:
        got = split_sentences(text)
        check('「%s」切分正确' % text, got == want, '得到 %r' % (got,))

    print('\n[4] 连续标点合并为一个句末')
    got = split_sentences('Really?! Yes.')
    check('「Really?! Yes.」切成 2 句', got == ['Really?!', 'Yes.'],
          '得到 %r' % (got,))
    got = split_sentences('Wait... really.')
    check('「Wait... really.」切成 2 句', got == ['Wait...', 'really.'],
          '得到 %r' % (got,))

    print('\n[5] 段长上限（业界：8–12 词）')
    long_text = ('This is a very long sentence that keeps going on and on '
                 'without any punctuation at all until it finally ends here.')
    got = split_sentences(long_text)
    check('长句被切成多段', len(got) > 1, '得到 %d 段' % len(got))
    ok = all(len(s.split()) <= MAX_SEG_WORDS for s in got)
    check('每段词数 <= %d' % MAX_SEG_WORDS, ok,
          '实际 %r' % [len(s.split()) for s in got])
    check('长句内容无丢失',
          norm_key(' '.join(got)) == norm_key(long_text),
          '原 %d 词 / 回 %d 词' % (len(long_text.split()),
                                  len(' '.join(got).split())))

    print('\n[6] 段长上限不误伤短句')
    got = split_sentences('Short one. Short two.')
    check('短句不被拆开', got == ['Short one.', 'Short two.'],
          '得到 %r' % (got,))

    print('\n[7] 碎片合并方向')
    # 句末出现短片段，不应被单独切出来
    got = split_sentences('That is very good. Yes.')
    check('「Yes.」不被拆出', 'Yes.' in got and len(got) == 2, '得到 %r' % (got,))
    got = split_sentences('I went home. Then I slept.')
    check('短碎片并回上一句', len(got) == 2, '得到 %r' % (got,))

    print('\n[8] ends_sentence 与切分一致')
    check('「It cost 1.5」是半句（末尾是小数点）',
          ends_sentence('It cost 1.5') is False)
    check('「Dr. Smith」是半句（末尾是缩写点）',
          ends_sentence('Dr. Smith') is False)
    check('「Hello world.」是完整句', ends_sentence('Hello world.') is True)
    check('「你好吗？」是完整句', ends_sentence('你好吗？') is True)
    check('「Really?!」是完整句', ends_sentence('Really?!') is True)
    check('空串是半句', ends_sentence('') is False)

    print('\n[9] 空输入与空白')
    check('空串返回 []', split_sentences('') == [])
    check('纯空格返回 []', split_sentences('   ') == [])
    check('None 返回 []', split_sentences(None) == [])

    print('\n[10] 内部判定函数')
    t = 'It cost 1.5 million.'
    j = t.index('.')          # 第一个点就是小数点
    check('_is_decimal_point 在 1.5 的点上为真',
          _is_decimal_point(t, j) is True,
          '位置 %d' % j)
    check('_is_decimal_point 在句末点上为假',
          _is_decimal_point(t, t.rindex('.')) is False)
    check('_is_abbrev_boundary 在 Dr. 的点上为真',
          _is_abbrev_boundary('Dr. Smith', 2) is True)
    check('_is_abbrev_boundary 在 U.S. 的两个点上都为真',
          _is_abbrev_boundary('The U.S. economy', 5) is True and
          _is_abbrev_boundary('The U.S. economy', 7) is True)
    check('_is_abbrev_boundary 在普通句末为假',
          _is_abbrev_boundary('Hello world.', 11) is False)

    print('\n[11] 中英混排与标点样式')
    got = split_sentences('我们用了 3.5 个 GPU。它很快！')
    check('中英混排数字不误切', got == ['我们用了 3.5 个 GPU。', '它很快！'],
          '得到 %r' % (got,))

    print('\n[12] 缩写表里的高风险短词（防「该断不断」）')
    # 这些词在缩写表里，但出现在句末时必须当句号处理
    risky = [
        ('We shipped no. It works.', ['We shipped no.', 'It works.']),
        ('The max. Is here.', ['The max.', 'Is here.']),
        ('He said e. And left.', ['He said e.', 'And left.']),
        ('Use min. Not avg.', ['Use min.', 'Not avg.']),
        ('Call Dr. Smith now.', ['Call Dr. Smith now.']),
    ]
    for text, want in risky:
        got = split_sentences(text)
        check('「%s」切分正确' % text, got == want, '得到 %r' % (got,))

    print('\n[13] 省略号与中文标点')
    got = split_sentences('嗯……好吧。你说呢？')
    check('中文省略号视为一个句末',
          got == ['嗯……', '好吧。', '你说呢？'], '得到 %r' % (got,))
    got = split_sentences('等等…然后呢？')
    check('单字符省略号视为句末', got == ['等等…', '然后呢？'], '得到 %r' % (got,))

    print('\n[14] 回归：旧版会误切的三例（本次改造的起因）')
    old_bug = [
        ('It cost 1.5 million dollars.',
         ['It cost 1.5 million dollars.']),
        ('The U.S. economy grew 3.5 percent.',
         ['The U.S. economy grew 3.5 percent.']),
        ('Dr. Smith joined at 9 a.m. today.',
         ['Dr. Smith joined at 9 a.m. today.']),
    ]
    for text, want in old_bug:
        got = split_sentences(text)
        check('「%s」不再被误切' % text, got == want, '得到 %r' % (got,))

    print('\n[16] 段长切分优先在从句边界断（保护语义上下文）')
    # 真实案例：按词数硬切会切出 "hit qs."，模型把它当拼写错误解释
    t = ("[REDACTED] Just last week we powered on our the chip "
         "new chip, big milestone in that our the chip has now hit qs. And then that")
    got = split_sentences(t)
    check('没有切出孤立的 "hit qs."',
          not any(s.strip() == 'hit qs.' for s in got), '得到 %r' % (got,))
    check('"hit qs." 所在的那句语义完整',
          any('hit qs.' in s and 'big milestone' in s for s in got),
          '得到 %r' % (got,))
    check('优先在逗号处断开',
          any(s.rstrip().endswith('new chip,') for s in got), '得到 %r' % (got,))
    check('内容无丢失',
          norm_key(' '.join(got)) == norm_key(t))

    print('\n[17] 中文长句按字符上限切')
    from translator import MAX_SEG_CHARS
    zh_long = ('我们今天讨论了很多重要的话题其中包括人工智能技术的最新进展以及它在'
               '工业制造中的实际应用案例还有相关的安全和伦理问题需要认真对待')
    got = split_sentences(zh_long)
    check('中文长句被切开', len(got) > 1, '得到 %d 段' % len(got))
    check('每段字符数 <= %d' % MAX_SEG_CHARS,
          all(len(s) <= MAX_SEG_CHARS for s in got),
          '实际 %r' % [len(s) for s in got])
    check('中文长句内容无丢失',
          ''.join(got).replace(' ', '') == zh_long.replace(' ', ''),
          '原 %d 字 / 回 %d 字' % (len(zh_long), len(''.join(got))))
    got = split_sentences('这是一句短话。')
    check('中文短句不被切', got == ['这是一句短话。'], '得到 %r' % (got,))

    print('\n' + '=' * 66)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(' 结果：%d/%d PASS' % (passed, total))
    if passed != total:
        print(' 失败项：')
        for n, ok, d in results:
            if not ok:
                print('   - %s  (%s)' % (n, d))
    print('=' * 66)
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
