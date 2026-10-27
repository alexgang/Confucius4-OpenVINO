"""offline_reader.py — 离线朗读：把「上传的文件」或「对话框里输入的文本」直接交给 TTS 播报。

## 定位

App 原有的语音输出只有一条链路：**ASR → 字幕 → MT 译文 → TTS**（`_pump_tts()`）。
本模块补的是**第二条入口**：文本**不经过 ASR、也不经过 MT**，直接进 `TTSService.submit()`。
适用场景：离线念文档 / 念会议纪要 / 念一段临时输入的文字。

## 🔴 四个必须踩对的坑（都是实测出来的，不是推测）

1. **必须节流提交**（🔴 APP-028② 之后，这一条的理由**变了**）。
   旧理由：`_update_backlog()` 会在积压超 `BACKLOG_MAX_S = 8` 时
   **整句丢弃**最旧的未播句 ⇒ 一次性把整篇文档 submit 进去，
   除最后几句全被丢掉（实测口径见 `results/app/app069_offline_reader_selftest.txt`：
   一次性提交 120 段 ⇒ 丢 118 段；本节流后 ⇒ 丢 0 段）。
   🔴 **APP-028② 之后**：`tts_service._update_backlog()` 的**丢句分支已整段删除**
   ⇒ 不再会因为积压丢句。
   ⇒ **节流仍然保留**，但理由变成：
     ① 合成端是**连续推理**、音频进**无界内存队列**
        ⇒ 一次性提交几百段 ⇒ 队列内存会涨到几百秒音频；
     ② 离线朗读是「念文档」⇒ **边念边提交**本来就符合直觉，
        用户能立刻听到第一段（而不是等全部合成完）。
   ⇒ 阈值口径**不变**（`SEG_BUDGET_S` / `PEND_BUDGET_S`），
     仍按「pending 总时长」节流 ⇒ 只是从「防丢句」变成「防内存涨 + 保首段快出」。

2. **单段本身也不能超过阈值**。旧实现里丢弃判据是「pending 总估算 > 8 s」，
   而**只有一段 pending 时也会判**：一段 36 s 的音频 ⇒ `est=36 > 8` ⇒
   循环里 `acc=36 > 4` ⇒ 这一段**自己就把自己丢了**。
   ⇒ 每段目标时长 `SEG_BUDGET_S = 3.4 s`（≈17 个汉字），
   同时在飞最多 2 段（`PEND_BUDGET_S = 7.0 < 8`）留出安全余量。
   🔴 APP-028② 之后这段不再会被「自己丢掉」，但**单段太长仍然不好**
   （合成一段要很久 ⇒ 首段迟迟不出声）⇒ 阈值继续保留。

3. **`submit()` 会静默截断**。`MAX_TEXT_CHARS = 200`（`LIVECAP_TTS_MAX_CHARS`），
   超过就 `text[:200]` —— 不报错、不提示。分段必须自己保证远小于这个数，
   否则长句会被**无声砍掉尾巴**。

4. **文件解析只用标准库**。客户包 `site-packages` 里**没有** python-docx / pypdf
   （实测 `ls` 确认）⇒ `.docx` 用 `zipfile` + `ElementTree` 解
   `word/document.xml`；`.pdf` 只有在装了 PyMuPDF / pypdf 时才解析，
   否则**明确报错**并提示转换，绝不返回空文本让用户以为「文件是空的」。

## 口径一致性

`est_seconds()` **刻意复刻** `tts_service._update_backlog()` 的公式
（`cjk/5.0 + other/15.0`），这样本模块算出的「段时长」与 service 自己的
「积压」是**同一把尺子**；换公式会导致节流失效或过度节流。
"""
from __future__ import annotations

import os
import re
import threading
import time
import zipfile
from typing import Dict, List, Optional

__all__ = [
    'OFFLINE_SEG_BASE', 'SEG_BUDGET_S', 'PEND_BUDGET_S', 'AHEAD_MAX',
    'est_seconds', 'split_for_tts', 'extract_text', 'OfflineReader',
    'SUPPORTED_EXT', 'suggest_name',
]

# ── 记账标记 ────────────────────────────────────────────────────────────
# 离线朗读提交的句子用**负数 seg** 打标，与 MT 的 seg（0..N）严格不冲突。
# 「停止」时只 cancel 这一段区间里的 jid ⇒ **不会误杀正在进行的会议译文**。
OFFLINE_SEG_BASE = -1_000_000

# ── 节流参数（见模块 docstring 坑 1/2）─────────────────────────────────
# 🔴 APP-028②：`_update_backlog()` 的**丢句分支已删除** ⇒ 这三个阈值
#   **不再用于「防丢句」**，改用于「防无界队列内存涨 + 让首段尽快出声」。
#   口径与数值**保持不变**（避免行为漂移）。
SEG_BUDGET_S = 3.4        # 单段目标音频时长（秒）
PEND_BUDGET_S = 7.0       # pending 总时长上限（秒）
AHEAD_MAX = 1             # 同时最多「预排」几段（1 = 当前段 + 下一段）

SUPPORTED_EXT = ('.txt', '.md', '.markdown', '.log', '.srt', '.vtt',
                 '.docx', '.docm', '.pdf')

_CJK_LO, _CJK_HI = '\u4e00', '\u9fff'

# 英文句号白名单：这些缩写后面的 '.' 不当作句子结束
_ABBREV = {'mr', 'mrs', 'ms', 'dr', 'prof', 'st', 'vs', 'etc', 'e.g', 'i.e',
           'fig', 'no', 'inc', 'ltd', 'jr', 'sr', 'u.s', 'a.m', 'p.m', 'approx'}


def est_seconds(text: str) -> float:
    """估算一段文本的播放时长（秒）。

    ⚠️ **公式必须与 `tts_service._update_backlog()` 逐字一致**
    （中文 ~5 字/秒，其余 ~15 字符/秒）—— 否则节流守不住那个 8 s 阈值。
    """
    cjk = sum(1 for ch in text if _CJK_LO <= ch <= _CJK_HI)
    other = len(text) - cjk
    return cjk / 5.0 + other / 15.0


# ── 文本清洗（只做「念出来会难听」的部分，不重写内容）─────────────────
_RE_MD_LINK = re.compile(r'!?\[([^\]\n]*)\]\(([^)\n]*)\)')
_RE_MD_CODE = re.compile(r'```.*?```', re.S)
# ⚠️ **只去掉「夹在非字母数字之间」的强调符**：
#    旧写法 `[`*_~]{1,3}` 会把 `a_b`、`3*4`、`C:\temp` 里的符号也吃掉
#    ⇒ 念出来是错的（实测自检 F 段 3 条 FAIL 就是这个）。
#    加 lookbehind/lookahead 后：`**粗体**`、`` `代码` `` 照去，`a_b`、`3*4` 保留。
_RE_MD_INLINE = re.compile(r'(?<![0-9A-Za-z])[_*`~]{1,3}(?![0-9A-Za-z])')

# 明确**不能**按文本读的扩展名 ⇒ 直接给可操作提示（别拿 latin-1 硬解出乱码）
_BINARY_HINT = {
    '.doc': '这是 Word 97-2003 老格式（二进制）⇒ 请另存为 .docx 或 .txt',
    '.rtf': 'RTF 富文本不支持 ⇒ 请另存为 .txt 或 .docx',
    '.xls': 'Excel 表格不支持朗读 ⇒ 请另存为 .csv/.txt',
    '.xlsx': 'Excel 表格不支持朗读 ⇒ 请另存为 .csv/.txt',
    '.ppt': 'PPT 不支持朗读 ⇒ 请把要念的文字另存为 .txt 或 .docx',
    '.pptx': 'PPT 不支持朗读 ⇒ 请把要念的文字另存为 .txt 或 .docx',
    '.zip': '压缩包不支持朗读 ⇒ 请先解压再选择其中的文本文件',
}


def _strip_markup(text: str) -> str:
    """去掉 Markdown 标记：代码块、链接语法、行首 #/>/- 列表符、强调符号。

    ⚠️ **不要过度清洗**：只去掉「念出来是噪音」的符号，
    正文一个字都不删（否则会和用户看到的文档不一致）。
    """
    text = _RE_MD_CODE.sub(' ', text)
    text = _RE_MD_LINK.sub(lambda m: m.group(1) or m.group(2), text)
    text = _RE_MD_INLINE.sub('', text)
    out = []
    for ln in text.splitlines():
        ln = re.sub(r'^\s{0,3}#{1,6}\s*', '', ln)      # 标题符
        ln = re.sub(r'^\s{0,3}>\s?', '', ln)            # 引用符
        ln = re.sub(r'^\s{0,3}[-+*]\s+', '', ln)        # 无序列表
        out.append(ln)
    return '\n'.join(out)


def _strip_subtitle(text: str) -> str:
    """去掉 SRT/VTT 的序号、时间轴与滚动重复行。"""
    keep = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.upper().startswith('WEBVTT'):
            continue
        if '-->' in s:
            continue
        if re.fullmatch(r'\d{1,6}', s):
            continue
        # 滚动字幕常见「上一行残留」⇒ 只去**相邻**重复，不做全局去重
        # （MEMORY 铁律：ASR 复读是真实内容，全局按文本去重会丢信息）
        if keep and keep[-1] == s:
            continue
        keep.append(s)
    return '\n'.join(keep)


# ── 分段 ────────────────────────────────────────────────────────────────
_SENT_END_HARD = '。！？!?；;…\n'


def _is_sentence_end(text: str, i: int) -> bool:
    """`text[i]` 是否构成句末（英文 '.' 要额外判断，避免切开 3.14 / Mr.）。"""
    ch = text[i]
    if ch in _SENT_END_HARD:
        return True
    if ch != '.':
        return False
    # 后面必须是空白 / 结尾 / 收尾引号括号
    nxt = text[i + 1:i + 2]
    if nxt and nxt not in ' \t\n\r"\'”’）」』':
        return False
    # 前面是数字 ⇒ 小数、版本号、序号，不切
    if i and text[i - 1].isdigit():
        return False
    # 缩写白名单
    j = i
    while j > 0 and (text[j - 1].isalnum() or text[j - 1] in '.&'):
        j -= 1
    if text[j:i].lower().strip('.') in _ABBREV:
        return False
    return True


def _hard_split(piece: str, budget: float) -> List[str]:
    """把一段「本身超预算」的文本切成若干 ≤ budget 的片（优先切在停顿处）。

    🔴 **必须精确**：这里不是「凑到差不多」就行 —— 切出来的段一旦 > budget，
    单段自己就超预算（合成很久 ⇒ 首段迟迟不出声）。
    ⇒ 所以先求「不超过预算的最长前缀」，再在这个前缀里**回找**停顿符；
    停顿符太靠前（< 前缀一半）就按前缀硬切。
    """
    out: List[str] = []
    rest = piece
    pause = '，,、：:；; '
    while rest:
        acc = ''
        for ch in rest:
            if acc and est_seconds(acc + ch) > budget:
                break
            acc += ch
        if not acc:                      # 单字符就超预算（极短 budget）
            acc = rest[0]
        if len(acc) >= len(rest):        # 剩余部分本来就够短
            out.append(rest.strip())
            break
        best = -1
        for c in pause:
            k = acc.rfind(c)
            if k > best:
                best = k
        cut = best + 1 if best >= len(acc) // 2 else len(acc)
        out.append(rest[:cut].strip())
        rest = rest[cut:]
    return [p for p in out if p]


def split_for_tts(text: str, budget_s: float = SEG_BUDGET_S) -> List[str]:
    """把文本切成「适合逐句送 TTS」的段（每段估算 ≤ budget_s 秒）。

    两级策略：
    1. 先按**句末标点**切；
    2. 只在单句**本身超预算**时，才退到逗号/空格切（坑 2：超预算的段会被丢弃）。

    ⚠️ 不做「跨段合并到刚好满」的贪心 —— 相邻短句合并会让一段接近 3.4 s，
    在飞 2 段时逼近 8 s 阈值；宁可多切一次，也不去赌那个余量。
    """
    text = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    text = _strip_markup(text)
    # 全角空格/制表等 → 空格；保留换行作为段落边界
    text = text.replace('\u3000', ' ').replace('\t', ' ')

    # ── 第一级：按句末标点切 ──
    pieces, cur = [], ''
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        cur += ch
        # 连续的句末符（！？ 连用）一起吞掉，别切成两段
        if _is_sentence_end(text, i):
            j = i + 1
            while j < n and text[j] in _SENT_END_HARD:
                cur += text[j]
                j += 1
            # 顺带吞掉紧跟的收尾引号/括号
            while j < n and text[j] in '"\'”’）」』':
                cur += text[j]
                j += 1
            pieces.append(cur)
            cur = ''
            i = j
            continue
        i += 1
    if cur:
        pieces.append(cur)

    # ── 第二级：清洗空白 + 超预算的单句再切 ──
    segs: List[str] = []
    for p in pieces:
        p = re.sub(r'[ ]{2,}', ' ', p).strip()
        if not p:
            continue
        if est_seconds(p) <= budget_s:
            segs.append(p)
        else:
            segs.extend(_hard_split(p, budget_s))
    return segs


# ── 文件解析 ────────────────────────────────────────────────────────────
def _read_text_file(path: str) -> Dict:
    """按 utf-8-sig → gb18030 → utf-16 → latin-1 顺序试编码（报出用了哪个）。

    🔴 **先判二进制**：latin-1 对任何字节都不会抛 `UnicodeDecodeError`
    ⇒ 没有这道闸门，`.doc`/`.xls` 会被「成功」解成乱码并念出来
    （自检 F 段实测：`.doc` 被当成文本读，一条 FAIL）。
    """
    raw = open(path, 'rb').read()
    head = raw[:4096]
    # UTF-16 文本天然含 \x00 ⇒ 先排除它再判二进制
    is_utf16 = head[:2] in (b'\xff\xfe', b'\xfe\xff') or \
        (len(head) > 2 and head[1:2] == b'\x00' and head[0:1] != b'\x00')
    if not is_utf16 and b'\x00' in head:
        raise RuntimeError(
            '这个文件看起来是二进制（含 NUL 字节），不是文本文件 ⇒ '
            '请选择 .txt / .md / .docx，或先另存为纯文本')
    for enc in ('utf-8-sig', 'gb18030', 'utf-16', 'latin-1'):
        try:
            return {'text': raw.decode(enc), 'encoding': enc, 'note': ''}
        except UnicodeDecodeError:
            continue
    return {'text': raw.decode('utf-8', 'replace'), 'encoding': 'utf-8?',
            'note': '编码无法判定，已用替换字符解码'}


def _docx_text(path: str) -> str:
    """解析 .docx —— 只用标准库（包内没有 python-docx）。

    `word/document.xml` 里：`<w:p>` 是段落、`<w:t>` 是文本 run、
    `<w:tab/>` 是制表（≈空格）、`<w:br/>` 是段内换行。
    ⇒ 先把段落/换行/制表转成 `\\n` 与空格，再**剥掉所有标签**，最后反转义实体。
    """
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n == 'word/document.xml']
        if not names:
            raise RuntimeError('不是合法的 .docx（缺 word/document.xml）')
        xml = z.read('word/document.xml').decode('utf-8', 'replace')
    xml = xml.replace('<w:tab/>', ' ').replace('<w:tab />', ' ')
    xml = xml.replace('<w:br/>', '\n').replace('<w:br />', '\n')
    xml = re.sub(r'</w:p\s*>', '\n', xml)
    xml = re.sub(r'<[^>]+>', '', xml)          # 剥标签
    xml = (xml.replace('&lt;', '<').replace('&gt;', '>')
              .replace('&quot;', '"').replace('&apos;', "'")
              .replace('&amp;', '&'))
    return xml


def _pdf_text(path: str) -> str:
    """解析 .pdf —— 包内**没有** PDF 库，装了才用，否则明确报错。"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        try:
            return '\n'.join(pg.get_text() for pg in doc)
        finally:
            doc.close()
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        return '\n'.join((pg.extract_text() or '') for pg in PdfReader(path).pages)
    except ImportError:
        pass
    raise RuntimeError(
        '客户包里没有 PDF 解析库（PyMuPDF / pypdf 都没有）⇒ '
        '请先把 PDF 另存为 .txt 或 .docx，再从这里打开')


def extract_text(path: str) -> Dict:
    """从文件读出可朗读文本。

    返回 `{path, name, ext, text, n_chars, est_s, encoding, note}`；
    **解析失败抛 RuntimeError（带可操作提示）**，绝不返回空文本冒充成功。
    """
    if not path or not os.path.isfile(path):
        raise RuntimeError(f'文件不存在：{path}')
    ext = os.path.splitext(path)[1].lower()
    if ext in _BINARY_HINT:
        raise RuntimeError(f'{ext} 不能直接朗读：{_BINARY_HINT[ext]}')
    note = ''
    if ext in ('.srt', '.vtt'):
        r = _read_text_file(path)
        text, enc = _strip_subtitle(r['text']), r['encoding']
        note = '已去掉字幕序号/时间轴'
    elif ext in ('.docx', '.docm'):
        text, enc = _docx_text(path), 'xml'
        note = '按 docx 段落解析（无 python-docx，纯标准库）'
    elif ext == '.pdf':
        text, enc = _pdf_text(path), 'pdf'
    elif ext in ('.md', '.markdown'):
        r = _read_text_file(path)
        # 🔴 Markdown **在这里就把标记去掉**（而不是只在切段时去）：
        #    对话框里要显示的就是「将要念出来的文字」，否则用户看到的
        #    和听到的对不上（`#`、`**`、代码块都不会被念）。
        text, enc = _strip_markup(r['text']), r['encoding']
        note = '已去掉 Markdown 标记（标题符/链接语法/代码块）'
    else:
        # .txt / .log / 无扩展名 / 未知扩展名 ⇒ 纯文本（含二进制闸门）
        r = _read_text_file(path)
        text, enc = r['text'], r['encoding']
        if ext in ('', '.txt', '.log', '.text'):
            note = r['note']
        else:
            note = f'未知扩展名 {ext}，按纯文本读取（{enc}）'
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    n_seg = len(split_for_tts(text))
    return {'path': path, 'name': os.path.basename(path), 'ext': ext,
            'text': text, 'n_chars': len(text.strip()),
            'est_s': round(est_seconds(text), 1), 'n_seg': n_seg,
            'encoding': enc, 'note': note}


def suggest_name(path: str) -> str:
    base = os.path.basename(path or '')
    return os.path.splitext(base)[0] or '朗读'


# ── 节流喂句控制器（无 GUI 依赖，可单独跑测试）────────────────────────
class OfflineReader:
    """把一串段**按积压预算**喂给 TTSService。

    职责单一：只做「什么时候 submit 下一段」，不碰 Tk、不碰音频。
    `svc` 只需 duck-type 三个东西：`submit(text, seg=)`、`pending`、`lock`、
    可选 `state`、`cancel(jid)` —— 这样自检可以塞假 service 进去
    （**不需要加载模型**，也不需要 import 被测模块的重依赖）。

    线程模型：`start()` 起一个 daemon 线程喂句；状态只写本对象字段，
    GUI 侧轮询 `snapshot()` 更新界面 ⇒ **不存在跨线程 Tk 调用**。
    """

    def __init__(self, svc, *, ahead: int = AHEAD_MAX,
                 pend_budget: float = PEND_BUDGET_S,
                 seg_budget: float = SEG_BUDGET_S,
                 seg_base: int = OFFLINE_SEG_BASE,
                 on_log=None):
        self.svc = svc
        self.ahead = max(0, int(ahead))
        self.pend_budget = float(pend_budget)
        self.seg_budget = float(seg_budget)
        self.seg_base = int(seg_base)
        self.on_log = on_log or (lambda m: None)

        self.segs: List[str] = []
        self.n_fed = 0
        self.n_seg = 0
        self.done = False
        self.stopped = False
        self.error: Optional[str] = None
        self.last_msg = ''
        self._stop = threading.Event()
        self._th: Optional[threading.Thread] = None

    # -- 对外 ---------------------------------------------------------
    def start(self, text_or_segs) -> int:
        """开始朗读。返回段数（0 = 没有可念的内容）。"""
        if isinstance(text_or_segs, str):
            segs = split_for_tts(text_or_segs, self.seg_budget)
        else:
            segs = [s for s in (text_or_segs or []) if s and s.strip()]
        self.segs = segs
        self.n_seg = len(segs)
        self.n_fed = 0
        self.done = False
        self.stopped = False
        self.error = None
        if not segs:
            self.last_msg = '没有可朗读的文本'
            self.done = True
            return 0
        self._stop.clear()
        self._th = threading.Thread(target=self._loop, name='offline-reader',
                                    daemon=True)
        self._th.start()
        return len(segs)

    def stop(self, cancel_pending: bool = True):
        """停止：先置标志，再撤掉**本次朗读**还没播的段（不动 MT 的句子）。"""
        self.stopped = True
        self._stop.set()
        if cancel_pending:
            self._cancel_pending()

    def wait(self, timeout: Optional[float] = None) -> bool:
        th = self._th
        if th is None:
            return True
        th.join(timeout)
        return not th.is_alive()

    def snapshot(self) -> Dict:
        try:
            with self.svc.lock:
                n_pend = len(self.svc.pending)
        except Exception:
            n_pend = -1
        return dict(n_fed=self.n_fed, n_seg=self.n_seg, n_pend=n_pend,
                    done=self.done, stopped=self.stopped,
                    error=self.error, msg=self.last_msg,
                    state=getattr(self.svc, 'state', '?'))

    # -- 内部 ---------------------------------------------------------
    def _pend_est(self) -> float:
        """当前 pending 的总估算时长（与 service 的积压同尺子）。"""
        try:
            with self.svc.lock:
                items = list(self.svc.pending.values())
        except Exception:
            return 0.0
        return sum(est_seconds(it.get('text', '')) for it in items)

    def _cancel_pending(self):
        """cancel 掉**属于本次离线朗读**的未播段（seg ≤ OFFLINE_SEG_BASE）。"""
        svc = self.svc
        if not hasattr(svc, 'cancel'):
            return
        try:
            with svc.lock:
                victims = [jid for jid, it in svc.pending.items()
                           if isinstance(it.get('seg'), int)
                           and it['seg'] <= self.seg_base]
        except Exception:
            return
        for jid in victims:
            try:
                svc.cancel(jid)
            except Exception as e:
                self.on_log(f'cancel {jid} 失败：{e!r}')

    def _loop(self):
        try:
            i = 0
            n = self.n_seg
            last_beat = time.time()
            while i < n:
                if self._stop.is_set():
                    break
                st = getattr(self.svc, 'state', 'ready')
                if st == 'error':
                    self.error = 'TTS worker 故障（error）⇒ 朗读中止'
                    self.last_msg = self.error
                    self.on_log(self.error)
                    break
                # 坑 1/2：只在「总 pending 时长 + 下一段」仍低于阈值时才喂
                pend_n = -1
                try:
                    with self.svc.lock:
                        pend_n = len(self.svc.pending)
                except Exception:
                    pass
                pend = self._pend_est()
                nxt = est_seconds(self.segs[i])
                if pend_n <= self.ahead and (pend + nxt) <= self.pend_budget:
                    self.svc.submit(self.segs[i], seg=self.seg_base - i)
                    i += 1
                    self.n_fed = i
                    last_beat = time.time()
                    continue
                # 停滞提示（模型还在加载 / 直播占用 TTS 队列）
                now = time.time()
                if now - last_beat > 15.0:
                    last_beat = now
                    self.last_msg = (f'等待 TTS（{st}）：待播 {pend_n} 段 / '
                                     f'积压 {pend:.1f}s')
                    self.on_log(self.last_msg)
                time.sleep(0.10)
            if i >= n and not self._stop.is_set():
                self.last_msg = f'已全部提交（{n} 段），等待播完'
            self.done = True
        except Exception as e:
            self.error = f'{type(e).__name__}: {e}'
            self.last_msg = self.error
            self.on_log(f'离线朗读异常：{e!r}')
            self.done = True
        finally:
            if self.stopped:
                self._cancel_pending()
