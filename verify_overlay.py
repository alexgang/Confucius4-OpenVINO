# -*- coding: utf-8 -*-
"""verify_overlay.py — 验证「屏幕字幕（overlay）」的译文显示。

背景（真实缺陷）：
  `_render` 里算 overlay 译文尾行时写的是
      `for b in self.blocks[-3:]`  —— 迭代出的是**原文文本**
  但 `_mt_of(seg)` 需要的是**段序号**（blocks 的下标），查 seg_keys 自然查不到，
  结果是屏幕字幕的译文行**永远为空**（主文本区的译文正常，所以很难发现）。
  用户反馈：「关闭草稿译文后，屏幕字幕上仍然应该显示出定稿英文的译文」。

同时验证第二处：草稿预览与定稿译文**分行**显示 —— 原来的
  `mt_tail or draft` 会让定稿译文把草稿预览顶掉（草稿开关等于白开）。

无 Tk 模拟（不需要显示器）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'live_caption'))

import translator as T
import live_caption_app as A

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + ('   ' + str(extra) if extra else ''))
    if not cond:
        fails.append(name)


# ── 假翻译器：立刻返回「【译】原文」 ─────────────────────────────────
class FakeTr:
    def __init__(self, *a, **kw):
        self.load_s = 0.1

    # ⚠️ 签名必须与 translator.py::_run_jobs 的调用一致：
    #    `tr.translate(job.text, svc.target, ctx=ctx, glossary=gl)`
    #    少了 glossary 会抛 TypeError，而 TypeError 被 svc.err 吞掉
    #    ⇒ 译文全空、断言全红，却看不到任何报错（2026-10-23 APP-007 排查发现）。
    def translate(self, text, tgt, on_token=None, ctx=None, glossary=None):
        return dict(text='【译】' + text, lat_ms=1.0, ttft_ms=1.0,
                    n_in=1, n_out=1, skipped=False)

    def close(self):
        pass


T.HunyuanTranslator = FakeTr


class FakeTxt:
    def __init__(self):
        self.buf = []

    def configure(self, **kw):
        pass

    def delete(self, *a):
        self.buf = []

    def insert(self, w, text, tag=None):
        self.buf.append((tag, text))

    def see(self, *a):
        pass

    def dump(self):
        return ''.join(t for _, t in self.buf)


class FakeOverlay:
    """复刻 CaptionOverlay.show 的**两行**（APP-007：定稿译文 / 实时识别）。"""

    def __init__(self):
        self.lines = ('', '')          # lines[0]=定稿译文, lines[1]=实时识别

    def show(self, mt='', partial=''):
        self.lines = (mt, partial)


class FakeApp:
    _render = A.App._render

    def __init__(self, draft=False):
        self.mt = T.TranslationService(target='zh', device='GPU.0', auto=True,
                                       engine_key='gpu_int4cw', draft=draft)
        self.mt.wait_idle(30)
        self.final_text = ''
        self.blocks = []
        self.overlay = FakeOverlay()
        self.txt = FakeTxt()

    def _mt_of(self, seg):
        return self.mt.mt_of_seg(seg)

    def _on_final(self, text):
        self.final_text += text + '\n'
        self.blocks.append(text)
        self.mt.submit(text, seg=len(self.blocks) - 1)


SEGS = [
    'Hello world, this is the first segment.',
    'The second segment talks about performance.',
    'The third segment wraps things up.',
]


# ── ① 关闭草稿时，屏幕字幕必须有定稿译文（用户反馈的核心） ──────────
app = FakeApp(draft=False)
for s in SEGS:
    app._on_final(s)
    app.mt.wait_idle(30)
app._render('partial text so far')

check('① 关闭草稿：主文本区有译文', '〔译〕' in app.txt.dump())
check('① 关闭草稿：overlay 译文行非空', bool(app.overlay.lines[0].strip()),
      repr(app.overlay.lines[0]))
check('① 关闭草稿：overlay 译文含第一段译文', '【译】Hello world' in app.overlay.lines[0])
check('① 关闭草稿：overlay 译文含最后一段译文', '【译】The third segment' in app.overlay.lines[0])
check('① 关闭草稿：overlay 只有两行（无草稿行）', len(app.overlay.lines) == 2,
      repr(app.overlay.lines))

# ── ② 开启草稿时，定稿译文同样要在（不能因为开了草稿就丢） ──────────
app2 = FakeApp(draft=True)
for s in SEGS:
    app2._on_final(s)
    app2.mt.wait_idle(30)
app2._render('partial text so far')
check('② 开启草稿：overlay 译文行非空', bool(app2.overlay.lines[0].strip()),
      repr(app2.overlay.lines[0]))

# ── ③ 草稿预览不再上屏幕字幕（APP-007 删掉了第四行） ─────────────────
app3 = FakeApp(draft=True)
app3._on_final('First segment here.')
app3.mt.wait_idle(30)
app3.mt.draft = '【草稿预览】未定稿那半句的翻译'
app3._render('partial unfinished')
check('③ 定稿译文行非空', bool(app3.overlay.lines[0].strip()), repr(app3.overlay.lines[0]))
check('③ overlay 只有两行', len(app3.overlay.lines) == 2, repr(app3.overlay.lines))
check('③ 草稿预览不再进 overlay', '草稿预览' not in app3.overlay.lines[0]
      and '草稿预览' not in app3.overlay.lines[1], repr(app3.overlay.lines))
check('③ 译文行与实时行内容不同',
      app3.overlay.lines[0] != app3.overlay.lines[1])

# ── ④ 关闭草稿时残留的草稿不能出现在 overlay 上 ──────────────────────
app4 = FakeApp(draft=False)
app4._on_final('First segment here.')
app4.mt.wait_idle(30)
app4.mt.draft = '不该出现的残留草稿'
app4._render('partial unfinished')
check('④ 关闭草稿：残留草稿不进 overlay', len(app4.overlay.lines) == 2
      and '残留草稿' not in app4.overlay.lines[0]
      and '残留草稿' not in app4.overlay.lines[1], repr(app4.overlay.lines))
check('④ 关闭草稿：残留草稿不进主文本区', '不该出现的残留草稿' not in app4.txt.dump())

# ── ⑤ 段数不足 3 段时也要正常（range 边界） ──────────────────────────
app5 = FakeApp(draft=False)
app5._on_final('Only one segment.')
app5.mt.wait_idle(30)
app5._render('partial')
check('⑤ 只有 1 段：overlay 译文行非空', bool(app5.overlay.lines[0].strip()),
      repr(app5.overlay.lines[0]))
check('⑤ 只有 1 段：译文内容正确', '【译】Only one segment.' in app5.overlay.lines[0])

# ── ⑥ 没有定稿时不报错（overlay 译文行空即可） ──────────────────────
app6 = FakeApp(draft=False)
app6._render('partial only')
check('⑥ 无定稿：overlay 译文行为空', app6.overlay.lines[0] == '')
check('⑥ 无定稿：overlay 实时行有内容', app6.overlay.lines[1] == 'partial only')

# ── ⑦ 源码层面：不得再用「拿原文当 key」的写法 ─────────────────────
src = open(os.path.join(HERE, 'live_caption', 'live_caption_app.py'),
           encoding='utf-8').read()
check('⑦ 源码不再有 self._mt_of(b) for b in self.blocks',
      '_mt_of(b) for b in self.blocks' not in src)
check('⑦ 源码不再有 mt_tail or draft（会互相顶替）',
      'mt_tail or draft' not in src)

# ── ⑧ APP-007：屏幕字幕只保留两行（定稿译文 + 实时识别） ────────────
check('⑧ overlay 只有两行 Label（删掉了定稿原文与草稿预览）',
      'self.final = tk.Label' not in src
      and 'self.draft = tk.Label' not in src)
check('⑧ overlay 的 show 签名是两参',
      'def show(self, mt=\'\', partial=\'\')' in src)
check('⑧ overlay 高度按 2 行算',
      'h = 2 * line + 30' in src)
check('⑧ overlay 调用是两参', 'self.overlay.show(mt_tail, partial)' in src)

print()
print('=' * 60)
if fails:
    print('FAILED %d 项：%s' % (len(fails), fails))
    sys.exit(1)
print('ALL PASS')
