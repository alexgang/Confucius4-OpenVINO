"""app069 — 离线朗读模块自检（**不加载任何模型、不 import 被测模块的重依赖**）。

## 为什么要有这个脚本

`live_caption/offline_reader.py` 的核心难点**不是**解析文件，而是**节流**：
`tts_service._update_backlog()` 在「pending 估算时长 > 8 s」时会把**最旧的未播句
整句丢弃**。如果不节流，一次把整篇文档 submit 进去 ⇒ 长文档几乎全被丢掉
（用户看到的现象会是「点了朗读，只念了最后一句」）。

本脚本用一个**复刻了那条丢句规则**的假 service（`FakeTTSService`）来证明：
1. 裸提交 ⇒ 大量丢句（复现坑）；
2. `OfflineReader` 节流 ⇒ **丢 0 句，且每段都被播到**；
3. 分段器满足硬约束（每段 ≤ 预算、不超 `MAX_TEXT_CHARS`、原文守恒）；
4. 文件解析（txt/gb18030/docx/srt/md）真的能出文本；
5. `stop()` 只撤**本次朗读**的句子（负数 seg 打标），不动 MT 的句子。

## 🔴 为什么用假 service 而不是真 TTSService

- 真 service 要起子进程加载 TTS 模型（几分钟）⇒ 无法在自检里跑；
- 🔴 铁律：分析脚本**不要 import 被测模块**（连带 numpy/openvino ⇒ 进程可能在
  import 阶段 abort）。这里只从**源码字符串**里读出 `BACKLOG_MAX_S` 的默认值，
  不 import `tts_service`。

用法：
    python results/app/app069_offline_reader_selftest.py [--out <txt>]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, 'live_caption'))

import offline_reader as OR          # noqa: E402  （纯标准库，import 安全）

TMP = os.path.join(os.environ.get('TEMP', '.'), 'app069_selftest')
LINES = []
N_PASS = N_FAIL = 0


def say(s=''):
    print(s)
    LINES.append(s)


def check(name, ok, detail=''):
    global N_PASS, N_FAIL
    if ok:
        N_PASS += 1
        say(f'  PASS  {name}' + (f'  [{detail}]' if detail else ''))
    else:
        N_FAIL += 1
        say(f'  FAIL  {name}' + (f'  [{detail}]' if detail else ''))


def read_backlog_max_from_source() -> float:
    """从 `tts_service.py` 源码里读 `BACKLOG_MAX_S` 的默认值（不 import 模块）。"""
    p = os.path.join(_REPO, 'live_caption', 'tts_service.py')
    src = open(p, 'r', encoding='utf-8', errors='replace').read()
    m = re.search(r"BACKLOG_MAX_S\s*=\s*float\(\s*os\.environ\.get\(\s*"
                  r"'LIVECAP_TTS_BACKLOG_MAX'\s*,\s*'([\d.]+)'", src)
    return float(m.group(1)) if m else 8.0


def read_max_chars_from_source() -> int:
    p = os.path.join(_REPO, 'live_caption', 'tts_service.py')
    src = open(p, 'r', encoding='utf-8', errors='replace').read()
    m = re.search(r"MAX_TEXT_CHARS\s*=\s*int\(\s*os\.environ\.get\(\s*"
                  r"'LIVECAP_TTS_MAX_CHARS'\s*,\s*'(\d+)'", src)
    return int(m.group(1)) if m else 200


# ══════════════════════════════════════════════════════════════════════
# 假 service：复刻 tts_service 的「积压丢句」+「串行播放」，不加载模型
# ══════════════════════════════════════════════════════════════════════
class FakeTTSService:
    """`lock` / `pending` / `state` / `submit` / `cancel` / 三个计数。

    🔴 `_update_backlog()` 是**逐条复刻**真实现的：
       pending 估算 > BACKLOG_MAX_S ⇒ 从**最旧**的开始丢，累计丢到
       `acc > BACKLOG_MAX_S * 0.5` 为止（真实现见 tts_service.py L725-760）。
    播放用 `speed` 倍速模拟（duration/speed），且**播放期间该项仍在 pending 里**
    （真实现是收到 `played` 事件才清 pending）⇒ 本测试比真实情况**更严**。
    """

    def __init__(self, backlog_max: float, speed: float = 25.0):
        self.lock = threading.RLock()
        self.pending = {}
        self.state = 'ready'
        self.n_submitted = self.n_played = self.n_dropped = 0
        self.backlog_max = float(backlog_max)
        self.speed = float(speed)
        self.played_segs = []
        self._next = 0
        self._player_stop = threading.Event()
        self._player = None

    # -- 生命周期 --
    def start_player(self):
        self._player = threading.Thread(target=self._play_loop, daemon=True)
        self._player.start()

    def stop_player(self):
        self._player_stop.set()
        if self._player:
            self._player.join(2.0)

    def _play_loop(self):
        while not self._player_stop.is_set():
            with self.lock:
                jid = next(iter(self.pending), None)
                item = dict(self.pending[jid]) if jid is not None else None
            if item is None:
                time.sleep(0.005)
                continue
            dur = OR.est_seconds(item['text']) / self.speed
            t_end = time.time() + dur
            while time.time() < t_end and not self._player_stop.is_set():
                time.sleep(0.002)
            with self.lock:
                if self.pending.pop(jid, None) is not None:
                    self.n_played += 1
                    self.played_segs.append(item.get('seg'))

    # -- 接口 --
    def submit(self, text, seg=None):
        text = (text or '').strip()
        if not text:
            return
        with self.lock:
            jid = self._next
            self._next += 1
            self.pending[jid] = dict(seg=seg, text=text)
            self.n_submitted += 1
        self._update_backlog()

    def cancel(self, jid):
        with self.lock:
            if self.pending.pop(jid, None) is not None:
                self.n_dropped += 1

    def _update_backlog(self):
        with self.lock:
            items = list(self.pending.items())
        if not items:
            return
        est = sum(OR.est_seconds(it['text']) for _, it in items)
        if est <= self.backlog_max:
            return
        ids, acc = [], 0.0
        with self.lock:
            for jid, it in self.pending.items():
                acc += OR.est_seconds(it['text'])
                ids.append(jid)
                if acc > self.backlog_max * 0.5:
                    break
            for jid in ids:
                self.pending.pop(jid, None)
        self.n_dropped += len(ids)


# ══════════════════════════════════════════════════════════════════════
# 测试语料
# ══════════════════════════════════════════════════════════════════════
CN_DOC = (
    '孔子与儒家思想的现代价值。'
    '在今天的会议上，我们讨论了三个议题：第一，产品交付的时间节点；'
    '第二，语音合成的质量与延迟之间的取舍；第三，客户现场的运维成本。'
    '经过讨论，大家一致认为应当优先保证正确性，再考虑性能优化，'
    '因为一条错误的译文比一句话晚到三秒钟要糟糕得多。'
    '接下来由工程团队给出具体的实施计划，并在下周一之前完成评审。'
)
EN_DOC = ('The quick brown fox jumps over the lazy dog. '
          'Dr. Smith said the meeting starts at 3.14 p.m. sharp. '
          'We will review the latency numbers, and then decide. '
          'This sentence is intentionally longer than the others so that '
          'the splitter has to consider breaking it at a comma boundary.')


def long_cn(n_sent=120):
    parts = []
    for i in range(n_sent):
        parts.append(f'这是第{i + 1}句用于测试节流的合成文本，内容没有真实含义。')
    return ''.join(parts)


# ══════════════════════════════════════════════════════════════════════
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        _REPO, 'results', 'app', 'app069_offline_reader_selftest.txt'))
    args = ap.parse_args()

    os.makedirs(TMP, exist_ok=True)
    backlog_max = read_backlog_max_from_source()
    max_chars = read_max_chars_from_source()

    say('=' * 78)
    say('app069 离线朗读自检（不加载模型）')
    say(f'ts={time.strftime("%Y-%m-%d %H:%M:%S")}')
    say(f'从源码读到：BACKLOG_MAX_S={backlog_max}  MAX_TEXT_CHARS={max_chars}')
    say(f'模块参数：SEG_BUDGET_S={OR.SEG_BUDGET_S}  PEND_BUDGET_S={OR.PEND_BUDGET_S}'
        f'  AHEAD_MAX={OR.AHEAD_MAX}')
    say('=' * 78)

    # ── A. 参数自洽（先证明「预算 < 阈值」这个前提成立）──
    say('\n[A] 参数自洽性')
    check('单段预算 < 积压阈值', OR.SEG_BUDGET_S < backlog_max,
          f'{OR.SEG_BUDGET_S} < {backlog_max}')
    check('pending 总预算 < 积压阈值', OR.PEND_BUDGET_S < backlog_max,
          f'{OR.PEND_BUDGET_S} < {backlog_max}')
    check('2 段 × 单段预算 ≤ pending 预算',
          2 * OR.SEG_BUDGET_S <= OR.PEND_BUDGET_S + 0.2,
          f'{2 * OR.SEG_BUDGET_S:.1f} vs {OR.PEND_BUDGET_S}')

    # ── B. 分段器硬约束 ──
    say('\n[B] 分段器 split_for_tts')
    segs = OR.split_for_tts(CN_DOC)
    check('中文文档能切出多段', len(segs) >= 3, f'{len(segs)} 段')
    check('每段估算 ≤ 预算',
          all(OR.est_seconds(s) <= OR.SEG_BUDGET_S + 1e-6 for s in segs),
          f'max={max(OR.est_seconds(s) for s in segs):.2f}s')
    check('每段长度 ≤ MAX_TEXT_CHARS（不被静默截断）',
          all(len(s) <= max_chars for s in segs),
          f'max_len={max(len(s) for s in segs)} / {max_chars}')
    check('没有空段', all(s.strip() for s in segs))
    strip_w = lambda t: re.sub(r'\s+', '', t)
    check('原文守恒（去空白后逐字相同）',
          strip_w(''.join(segs)) == strip_w(CN_DOC),
          f'{len(strip_w("".join(segs)))} vs {len(strip_w(CN_DOC))}')

    e_segs = OR.split_for_tts(EN_DOC)
    check('英文缩写 Mr./Dr. 不切句',
          not any(s.strip().lower().startswith('smith') for s in e_segs),
          f'{len(e_segs)} 段')
    check('英文版本号 3.14 不切句',
          not any(re.fullmatch(r'\d+\.?\s*', s.strip()) for s in e_segs))
    check('英文每段 ≤ 预算',
          all(OR.est_seconds(s) <= OR.SEG_BUDGET_S + 1e-6 for s in e_segs),
          f'max={max(OR.est_seconds(s) for s in e_segs):.2f}s')

    long_seg = ('这一句话非常长' * 12) + '。'
    one = OR.split_for_tts(long_seg)
    check('超长单句被拆开（否则会被丢弃）',
          len(one) >= 2 and all(OR.est_seconds(s) <= OR.SEG_BUDGET_S + 1e-6
                               for s in one),
          f'{len(one)} 段 / max={max(OR.est_seconds(s) for s in one):.2f}s')

    # ── C. 复现坑：裸提交 ⇒ 大量丢句 ──
    say('\n[C] 对照：一次性 submit 整篇（复现坑）')
    doc = long_cn(120)
    raw_segs = OR.split_for_tts(doc)
    svc0 = FakeTTSService(backlog_max, speed=25.0)
    svc0.start_player()
    t0 = time.time()
    for s in raw_segs:
        svc0.submit(s, seg=OR.OFFLINE_SEG_BASE)
    time.sleep(1.0)
    svc0.stop_player()
    naive_dropped, naive_played = svc0.n_dropped, svc0.n_played
    say(f'  → 提交 {svc0.n_submitted} 段 / 已播 {naive_played} / '
        f'丢 {naive_dropped}（{time.time() - t0:.1f}s）')
    check('裸提交确实会大量丢句（坑被复现）',
          naive_dropped > naive_played,
          f'丢 {naive_dropped} > 播 {naive_played}')

    # ── D. 节流后：丢 0 句且每段都被播到 ──
    say('\n[D] OfflineReader 节流（同样 120 段）')
    svc1 = FakeTTSService(backlog_max, speed=25.0)
    svc1.start_player()
    rd = OR.OfflineReader(svc1)
    n = rd.start(doc)
    ok = rd.wait(timeout=180)
    # 等播放器把最后几段念完
    t_end = time.time() + 60
    while time.time() < t_end:
        with svc1.lock:
            if not svc1.pending:
                break
        time.sleep(0.05)
    svc1.stop_player()
    snap = rd.snapshot()
    say(f'  → 段数 {n} / 已提交 {snap["n_fed"]} / 已播 {svc1.n_played} / '
        f'丢 {svc1.n_dropped} / done={snap["done"]}')
    check('喂句线程正常结束', ok and snap['done'] and not snap['error'])
    check('全部段都提交了', snap['n_fed'] == n, f'{snap["n_fed"]}/{n}')
    check('丢句 = 0（节流生效）', svc1.n_dropped == 0, f'dropped={svc1.n_dropped}')
    check('每段都播到了（无跳过）', svc1.n_played == n, f'{svc1.n_played}/{n}')
    check('不变式 n_played + n_dropped == n_submitted',
          svc1.n_played + svc1.n_dropped == svc1.n_submitted,
          f'{svc1.n_played}+{svc1.n_dropped} vs {svc1.n_submitted}')
    check('提交顺序与段序一致（不跳句、不乱序）',
          svc1.played_segs == [OR.OFFLINE_SEG_BASE - i for i in range(n)])

    # ── E. stop() 只撤本次朗读的句子 ──
    say('\n[E] stop() 的撤句边界')
    svc2 = FakeTTSService(backlog_max, speed=2.0)
    svc2.start_player()
    # 先塞 3 条「MT 的句子」（seg ≥ 0），模拟会议正在翻译。
    # ⚠️ 每句必须**很短**：3 条加起来要远低于积压阈值，否则会被
    #    `_update_backlog()` 自己丢掉最旧的那条（实测 3×15 字 = 9 s > 8 s
    #    ⇒ 丢了 1 条，让「stop 误杀」的结论变成假阳性）。
    for k in range(3):
        svc2.submit('好的。', seg=k)
    n_mt_before = svc2.n_submitted
    rd2 = OR.OfflineReader(svc2)
    rd2.start(long_cn(40))
    time.sleep(0.4)
    rd2.stop()
    ok_stop = rd2.wait(timeout=10)
    # 🔴 必须**先停播放器再快照**：播放器还在跑的时候，快照里的「待播」
    #    可能在这之后被播掉 ⇒ 同一个 jid 既算「待播」又算「已播」
    #    （实测就是 2+2=4 > 3 的假阳性）。
    svc2.stop_player()
    with svc2.lock:
        mt_left = [it for it in svc2.pending.values()
                   if isinstance(it.get('seg'), int) and it['seg'] >= 0]
    mt_played = sum(1 for s in svc2.played_segs if isinstance(s, int) and s >= 0)
    say(f'  → MT 提交 {n_mt_before} 条；停止后：已播 {mt_played} + 仍待播 '
        f'{len(mt_left)} = {mt_played + len(mt_left)}')
    check('stop() 不误杀 MT 的句子（一条不少）',
          mt_played + len(mt_left) == n_mt_before,
          f'{mt_played}+{len(mt_left)} vs {n_mt_before}')
    check('stop() 后喂句线程已退出', ok_stop)

    # ── F. 文件解析 ──
    say('\n[F] 文件解析')
    p_txt = os.path.join(TMP, 'a_utf8.txt')
    open(p_txt, 'w', encoding='utf-8').write(CN_DOC)
    r = OR.extract_text(p_txt)
    check('UTF-8 txt 读取', r['n_chars'] > 100 and '孔子' in r['text'],
          f'{r["n_chars"]} 字 / {r["encoding"]} / {r["n_seg"]} 段')

    p_gbk = os.path.join(TMP, 'b_gb18030.txt')
    open(p_gbk, 'wb').write(CN_DOC.encode('gb18030'))
    r = OR.extract_text(p_gbk)
    check('GB18030 回退（不乱码）',
          r['encoding'] == 'gb18030' and '孔子' in r['text'],
          f'{r["encoding"]} / {r["n_chars"]} 字')

    p_md = os.path.join(TMP, 'c.md')
    open(p_md, 'w', encoding='utf-8').write(
        '# 标题\n\n- 列表项一\n- 列表项二\n\n'
        '正文里有 `代码` 和 [链接文字](https://example.com) 要念出来。\n\n'
        '```\nprint("这行不该被念")\n```\n')
    r = OR.extract_text(p_md)
    t = r['text']
    check('Markdown 标题/列表符被去掉', '#' not in t and '- 列表项' not in t)
    check('链接保留文字、去掉 URL',
          '链接文字' in t and 'example.com' not in t)
    check('代码块内容不朗读', '这行不该被念' not in t)

    p_srt = os.path.join(TMP, 'd.srt')
    open(p_srt, 'w', encoding='utf-8').write(
        '1\n00:00:01,000 --> 00:00:03,000\n第一行字幕\n\n'
        '2\n00:00:03,200 --> 00:00:05,000\n第一行字幕\n\n'
        '3\n00:00:05,200 --> 00:00:07,000\n第三行字幕\n')
    r = OR.extract_text(p_srt)
    check('SRT 去掉序号/时间轴', '-->' not in r['text'] and '00:00' not in r['text'])
    check('SRT 相邻重复只留一条', r['text'].count('第一行字幕') == 1,
          repr(r['text'][:40]))

    p_docx = os.path.join(TMP, 'e.docx')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>'
           '<w:p><w:r><w:t>第一段：离线朗读测试。</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>第二段：含</w:t></w:r><w:r><w:t>多个 run。</w:t>'
           '</w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(p_docx, 'w') as z:
        z.writestr('word/document.xml', xml)
    r = OR.extract_text(p_docx)
    check('docx 段落解析（纯标准库）',
          '第一段' in r['text'] and '第二段' in r['text'],
          repr(r['text'][:40]))
    check('docx 多个 run 拼接完整', '含多个 run' in r['text'])

    p_doc = os.path.join(TMP, 'f.doc')
    open(p_doc, 'wb').write(b'\xd0\xcf\x11\xe0old word')
    try:
        OR.extract_text(p_doc)
        check('.doc（老格式）明确报错', False, '没有抛异常')
    except Exception as e:
        check('.doc（老格式）明确报错', True, type(e).__name__)

    try:
        OR.extract_text(os.path.join(TMP, 'not_exist.txt'))
        check('不存在的文件明确报错', False)
    except RuntimeError:
        check('不存在的文件明确报错', True)

    # ── G. 空/边界 ──
    say('\n[G] 边界')
    check('空文本切出 0 段', OR.split_for_tts('') == [])
    check('纯空白切出 0 段', OR.split_for_tts('   \n\n\t ') == [])
    svc3 = FakeTTSService(backlog_max)
    rd3 = OR.OfflineReader(svc3)
    check('空文本 start() 返回 0 段', rd3.start('') == 0)
    check('空文本不提交任何句子', svc3.n_submitted == 0)
    check('est_seconds 与 service 公式一致（中文 5 字/秒）',
          abs(OR.est_seconds('一二三四五') - 1.0) < 1e-9,
          f'{OR.est_seconds("一二三四五"):.3f}')

    # ── 汇总 ──
    say('\n' + '=' * 78)
    say(f'结果：PASS {N_PASS} / FAIL {N_FAIL}')
    say('=' * 78)
    say(f'说明：本自检**没有加载任何 TTS 模型**，用的是复刻丢句规则的假 service；'
        f'真实 TTS 的端到端验证见 App 的人工朗读冒烟。')
    out = args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(LINES) + '\n')
    print(f'\n已写 {out}')
    return 0 if N_FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
