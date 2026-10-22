r"""live_caption/translator.py — Hy-MT2-1.8B 按句实时翻译（C-102 模型替换）

A1  HunyuanTranslator：openvino_genai LLMPipeline。翻译模型已从通用指令模型
    Hunyuan-1.8B-Instruct 换成**翻译专用** Hy-MT2-1.8B（tencent/Hy-MT2-1.8B，
    架构同为 hunyuan_v1_dense，导出/量化链路不变）。官方 Default Translation
    指令模板（无 system prompt，指令放 user 消息）替代原先自造的通用 prompt。
A2  TranslationService：单工作线程 + 按句调度 + dict 缓存(FIFO) + 尾巴草稿。
A3  MT_ENGINES：翻译侧的「设备 × 量化」可选项，与 App 里 ASR 的 ENGINES 同构，
    支持运行时热切换（set_engine）。MT2 实测结论见 hy_bench\STATUS_hy.md：
      · per-channel（-cw）是 NPU 可用的关键；
      · mt2-int4sym-cw-q：GPU.0 57.9 tok/s / TTFT 35 ms；NPU 44.0 tok/s / TTFT 292 ms，
        零乱码零空输出，比旧 Instruct 模型更快且质量更好；
      · ASR 与翻译同抢一个 NPU 时出字延迟会涨到 2.8 倍，所以两边设备要能分开选。

模型目录只读；可用环境变量 LIVECAP_MT_MODEL 覆盖 'auto' 用的模型目录。
"""
import json
import os
import queue
import re
import threading
import time
from collections import OrderedDict

import numpy as np

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# 包目录结构 / package layout: <root>/app/*.py  <root>/models/...
ROOT = os.path.dirname(APP_DIR)
# 模型根目录：相对包根推导，不写死盘符/用户名。
# LIVECAP_MODELS_DIR 可显式覆盖（与 live_caption_app.py 用同一个变量名）。
MODELS = os.environ.get('LIVECAP_MODELS_DIR',
                        os.environ.get('LIVECAP_MODELS',
                                       os.path.join(ROOT, 'models')))


def _first_existing(*candidates):
    """返回第一个存在的目录；全都不存在就返回第一个（用于给出可读的报错路径）。"""
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return candidates[0] if candidates else None


# 翻译模型目录的查找顺序（先客户包，再开发机）：
#   1) 环境变量 LIVECAP_MT_MODEL / LIVECAP_MT_CW_ROOT（显式覆盖，最高优先级）
#   2) 客户包内 <root>/models/mt/<name>（发布包自带）
#   3) 开发机 <用户目录>/hy_bench/ov/<name>（本仓库导出产物）
# 模型目录只读；找不到时 MT_ENGINES 里的路径仍然保留，GUI 会标注「缺模型」。
# ★ 全部相对推导/用 expanduser，不写死盘符或用户名 —— 解压到任意目录都能跑。
_HY_ROOT = os.environ.get(
    'LIVECAP_MT_CW_ROOT',
    _first_existing(
        os.path.join(MODELS, 'mt'),                 # 客户包：models/mt/mt2-int4sym-cw-q
        os.path.join(os.path.expanduser('~'), 'hy_bench', 'ov'),
        os.path.join(ROOT, 'hy_bench', 'ov'),
    ))
DEFAULT_MODEL = os.environ.get(
    'LIVECAP_MT_MODEL',
    _first_existing(
        os.path.join(MODELS, 'mt', 'mt2-int4sym-cw-q'),   # 客户包自带（per-channel，GPU/NPU 通吃）
        os.path.join(MODELS, 'mt2-int4sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int4sym-cw-q'),       # 开发机导出产物
    ))

# 目标语言下拉：off 表示不翻译
TARGETS = OrderedDict([
    ('off', None), ('zh', 'Chinese'), ('en', 'English'),
    ('ja', 'Japanese'), ('ko', 'Korean'),
])
TARGET_LABELS = OrderedDict([
    ('off', '关闭'), ('zh', '中文'), ('en', 'English'),
    ('ja', '日本語'), ('ko', '한국어'),
])

# ── A3 翻译后端：设备 × 量化 ───────────────────────────────────────────
# model=None 表示「跟随环境变量 / 用默认目录」；device=None 表示「用 --mt-device」。

def _cw_model(name):
    """按通道量化产物的目录解析：客户包 models/mt/<name> → 开发机 hy_bench/ov/<name>。"""
    return _first_existing(
        os.path.join(MODELS, 'mt', name),
        os.path.join(MODELS, 'mt-' + name),
        os.path.join(_HY_ROOT, name),
    )


# 旧的 int4_asym g128 产物：GPU 上 TTFT 最快，但 NPU 上不可用（乱码 + 慢 100 倍）。
# 客户包不带它（per-channel 版本 GPU/NPU 通吃且更小）。
# 只认「包内 models/」下的一份 —— 客户机上不该出现指向开发机目录的项。
# C-102：Hunyuan-1.8B-Instruct 的所有产物已全部由 Hy-MT2 对应产物替换（下表），
# 旧 Instruct 模型目录不再被引用（磁盘上的旧目录未删，仅作回退备份）。
_LEGACY_INT4 = None

# 候选翻译后端：(key, label, device, 模型目录名, 说明, 是否随客户包附带)
# 只有**本机真实存在**的模型才进下拉 —— 客户机上不该出现「缺模型」的项。
# v1.3：客户包**只附带 INT4**（mt2-int4sym-cw-q，993 MB）。
# INT8（1.7 GB）不随包发布 —— 译文质量与 INT4 持平（同义改写级差异），
# 换来的是 +700 MB 显存占用与慢 33%，对客户机没有实际收益。
# 开发机 hy_bench/ov/ 下仍保留 INT8 产物供对比测试。
# 排序：先按设备（GPU 在前，ASR 默认也占 GPU，所以 NPU 项放后面做「错峰」选择）。
# ★ C-102 实测（hy_bench/bench_mt2.py，7 句 × 3 次取中位）：
#   mt2-int4sym-cw-q  GPU.0 57.9 tok/s / TTFT 35 ms / 加载 6.9 s
#                     NPU   44.0 tok/s / TTFT 292 ms / 加载 15.7 s，零乱码
#   mt2-int8sym-cw-q  GPU.0 37.5 tok/s / TTFT 44 ms
#                     NPU   29.6 tok/s / TTFT 300 ms
_MT_CANDIDATES = [
    ('gpu_int4cw', 'Intel GPU · INT4-CW', 'GPU.0', 'mt2-int4sym-cw-q',
     'Hy-MT2 INT4_SYM 按通道，约 993 MB。57.9 tok/s，TTFT 35 ms；GPU/NPU 通吃', True),
    ('gpu_int8cw', 'Intel GPU · INT8-CW', 'GPU.0', 'mt2-int8sym-cw-q',
     'Hy-MT2 INT8_SYM 按通道，1.7 GB。37.5 tok/s，质量与 INT4 持平；显存充足时可用，'
     'ASR 也在 GPU 上会互相争抢', False),
    ('npu_int4cw', 'Intel NPU · INT4-CW', 'NPU', 'mt2-int4sym-cw-q',
     'NPU 推荐：44.0 tok/s、零乱码，约 993 MB。ASR 请留在 GPU/NPU 另一侧以免争抢', True),
    ('npu_int8cw', 'Intel NPU · INT8-CW', 'NPU', 'mt2-int8sym-cw-q',
     'NPU 备用：29.6 tok/s、1.7 GB，质量与 INT4 持平但慢 33%', False),
]

MT_ENGINES = OrderedDict()
MT_ENGINES['auto'] = dict(
    label='自动 · INT4-CW 模型', device=None, model=None,
    note='模型目录取 LIVECAP_MT_MODEL（或包内自带模型），设备取 --mt-device（默认 GPU.0）')
for _k, _label, _dev, _name, _note, _bundled in _MT_CANDIDATES:
    _m = _cw_model(_name)
    if os.path.isdir(_m):
        MT_ENGINES[_k] = dict(label=_label, device=_dev, model=_m, note=_note,
                               bundled=_bundled)
MT_DEFAULT = 'auto'

# 全部候选后端（含**本机没装模型**的）—— 给 --check 环境检查用。
# GUI 下拉只用 MT_ENGINES（本机真实存在的那些）；诊断则需要把缺的也列出来。
# bundled=False 的项表示「**本包不附带**」（不是客户机缺文件），--check 里
# 要区别于「本机缺模型」报出来 —— 否则客户会误以为安装坏了。
MT_ALL_CANDIDATES = OrderedDict()
for _k, _label, _dev, _name, _note, _bundled in _MT_CANDIDATES:
    MT_ALL_CANDIDATES[_k] = dict(
        label=_label, device=_dev, model=_cw_model(_name), note=_note,
        available=os.path.isdir(_cw_model(_name)), bundled=_bundled)
MT_ALL_CANDIDATES['auto'] = dict(
    label='自动 · INT4-CW 模型', device=None, model=DEFAULT_MODEL, note='',
    available=os.path.isdir(DEFAULT_MODEL), bundled=True)


def mt_available(key):
    """模型目录是否在本机存在（GUI 里据此把不可用的项标出来）。

    'auto' 的 model=None 表示「用默认目录」，所以要单独查 DEFAULT_MODEL 是否存在。
    """
    cfg = MT_ENGINES.get(key)
    if not cfg:
        return False
    m = cfg.get('model') or DEFAULT_MODEL
    return os.path.isdir(m)

# ── 分句与语言判别 ──────────────────────────────────────────────────────
# 断句规则参考业界实时翻译的通行做法（ACL N13-1023 / EMNLP 2020 Direct
# Segmentation）：按**句末标点**切、段长控制在 8–12 词附近（与 MT 训练数据的
# 句长分布一致）、碎片并回语义更合理的一侧。
#
# ★ 关键：不能光靠「见到 . 就切」。ASR 输出里的小数点、缩写点、版本号点
#   都会把句子切碎，切碎会直接产出错误译文。这里用「先扫出候选切点，
#   再逐个判定这个点是否真的是句末」的方式处理。
_SENT_END = '.?!。？！；;…'
_CJK = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')
_KANA = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff]')
_HANGUL = re.compile(r'[\u1100-\u11ff\uac00-\ud7af]')
_LATIN = re.compile(r'[A-Za-z]')
MIN_SENT_CHARS = 4

# 段长控制（词数）。业界最优平均段长 8–12 词；这里给一个略宽的区间，
# 超过上限就在最近的合法边界强制切，避免长句偏离 MT 训练分布。
TARGET_SEG_WORDS = (8, 12)
MAX_SEG_WORDS = 20          # 硬上限（含）：超过必须在最近的合法边界断开
MAX_SEG_CHARS = 60          # 中文硬上限（字）：中文没有词边界，按字符数控制

# 常见英文缩写 —— 这些点后面**不是**句末，不能切。
# ★ 这里的词都是**不可能单独作句子成分**的（称谓 / 单位 / 星期 / 头衔）。
#   故意不放 no / min / max / e / g / co / vol 这些 —— 它们本身就是完整
#   英文单词，放进来会导致 "We shipped no. It works." 该断的地方断不开。
_ABBREV = frozenset("""
mr mrs ms dr prof st sr jr rev hon gen col sgt lt capt cmdr adm gov pres
sen rep dept univ vs etc inc ltd corp
jan feb mar apr jun jul aug sep sept oct nov dec
mon tue tues wed thu thur thurs fri sat sun
pp ed eds figs approx est mgmt
""".split())

# 数字/版本号里的点：1.5 / 3.14 / 1.2.3 / v1.0 / 2.0.1
_NUM_DOT = re.compile(r'\d[.,]\d')

# 英文「单词」：允许内部带点（U.S. / a.m.），但不含空格
_WORD_BEFORE = re.compile(r'([A-Za-z]+(?:\.[A-Za-z]+)*\.?)$')


# 英文「单词」：允许内部带点（U.S. / a.m.），但不含空格
_WORD_BEFORE = re.compile(r'([A-Za-z]+(?:\.[A-Za-z]+)*\.?)$')
# 点分链整体匹配：U.S. / a.m. / Dr. / e.g. —— 一条链是一个整体缩写单位
_DOTTED_CHAIN = re.compile(r'[A-Za-z]+(?:\.[A-Za-z]+)*\.?')


def _is_abbrev_boundary(text, i):
    """text[i] 处的 '.' 是否属于缩写/称谓（如 Dr. / U.S. / a.m.）。

    判定依据是**整个点分链**，而不是「点前面那个词」：
      - "U.S." 的两个点同属一条链，任一个都不能切
      - "Dr." 是已知缩写
      - "a.m." / "e.g." 是短链（去掉点后 <= 3 个字母）
    """
    if i >= len(text) or text[i] != '.':
        return False
    # 找出包含 i 的那条点分链
    chain = None
    for m in _DOTTED_CHAIN.finditer(text):
        if m.start() <= i < m.end():
            chain = m.group(0)
            break
    if not chain or '.' not in chain:
        return False
    core = chain.strip('.').lower()
    if not core:
        return False
    # ★ 守卫（对**所有**缩写生效）：缩写点后面必须是「空白 + 大写字母」
    #   （下一个句子的开头）。否则像 "We shipped no." "The max." 这种
    #   普通词结尾的句号会被当成缩写，导致**该断的句子断不开**。
    #   点分链内部例外（U.S. 的第一个点后面是字母，不是句末）。
    after = text[i + 1:i + 4]
    follows_new_sent = bool(re.match(r'\s+[A-Z"\u201c\u2018]', after))
    chain_has_inner_dot = len(core) > len(core.replace('.', ''))
    if not follows_new_sent and not chain_has_inner_dot:
        return False
    # 已知缩写（e.g. / i.e. 这类本身带点的也在表里）
    if core in _ABBREV:
        return True
    # 点分链（U.S. / a.m. / Ph.D.）：去掉点后很短才认。
    # ★ 必须要求链里**真的有内部的点**（len(core) > 去掉点的长度）——
    #   否则 "one."、"two." 这种普通单词也会被误判成缩写（长度 <= 3 就中招）。
    if chain_has_inner_dot and len(core.replace('.', '')) <= 3:
        return True
    # 单字母缩写：必须是**大写**（如 "E." 数学常数、"A." 编号），
    #   小写的 "e." / "g." 是常见英文词尾，按句末处理。
    if len(core) == 1 and not chain_has_inner_dot:
        if not chain.isupper():
            return False
        return bool(re.match(r'\.\s+[A-Z"\u201c\u2018]', after))
    return False


def _is_decimal_point(text, i):
    """text[i] 处的点是否在小数/数字内部（1.5、1.2.3、v1.0、2,000.5）。

    两侧都是数字才算小数点；句末的 "dollars." 左边是字母，不算。
    """
    if i <= 0 or i >= len(text) - 1:
        return False
    return text[i - 1].isdigit() and text[i + 1].isdigit()


def _find_cut_points(text):
    """扫描出**真正**的句末标点位置（返回下标列表）。

    规则：
    - 连续标点（如 "?!"、"..."）合并成一个切点，取最后一个字符位置
    - '.' 若是小数点或缩写点，则跳过（不切）
    - 省略号 '…'、'...' 视为一个句末
    """
    cuts = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch not in _SENT_END:
            i += 1
            continue
        # 连续标点合并：'?!' / '...' / '……' 视为**一个**句末。
        # ★ 但合并段的**最后一个**点才可能是缩写点/小数点，
        #   中间的点一律当作标点的一部分（'...' 是省略号，不是三个句号）。
        j = i
        while j + 1 < n and text[j + 1] in _SENT_END:
            j += 1
        ch = text[j]
        if ch == '.':
            if _is_decimal_point(text, j) or _is_abbrev_boundary(text, j):
                # 末尾这个点不是句末 —— 整组都不切，继续往后找
                i = j + 1
                continue
        cuts.append(j)
        i = j + 1
    return cuts


def split_sentences(text, max_words=None):
    """按句末标点切句。

    与旧版的区别：
    1. 小数点 / 缩写点不再误切（1.5、Dr.、U.S.、a.m. 都保持完整）
    2. 碎片并回的方向改成「看下一段是否更完整」，而不是一律并回上一句
    3. 可选：按词数上限强制切分（业界建议段长对齐 MT 训练分布）
    """
    text = text or ''
    if not text.strip():
        return []
    max_words = max_words if max_words is not None else MAX_SEG_WORDS
    cuts = _find_cut_points(text)
    # 切点 -> 句子（最后一个切点之后的部分若非空，也作为一句）
    pieces = []
    start = 0
    for c in cuts:
        pieces.append(text[start:c + 1])
        start = c + 1
    tail = text[start:]
    if tail.strip():
        pieces.append(tail)
    # 合并不是空白的碎片
    pieces = [p for p in pieces if p.strip()]

    # 段长超限：在最近的**合法**边界（词边界）强制断开
    # ★ forced 标记这些片段是「段长上限强制切出来的」，后面**不许**再被
    #   碎片合并规则合回去 —— 否则中文长句切出来的尾巴（「对待」只有 2 字）
    #   会被并回上一段，等于没切。
    forced = set()
    if max_words:
        capped = []
        for p in pieces:
            # 中文没有空格，按词切不了 -> 改用字符上限
            if _CJK.search(p) and not re.search(r'[A-Za-z]\s', p):
                sub = _split_by_len(p, MAX_SEG_CHARS)
            else:
                sub = _split_by_words(p, max_words)
            if len(sub) > 1:
                forced.update(id(x) for x in sub[1:])
            capped.extend(sub)
        pieces = capped
    # 碎片合并：只有**没有句末标点收尾**的碎片才并回上一句。
    # ★ 以句末标点收尾的一定是完整句，不能合并 ——
    #   否则中文的短句（"好吧。"只有 3 个可见字符）会被并进上一句，
    #   译文就会把两句话黏在一起。
    out = []
    for piece in pieces:
        if not piece.strip():
            continue
        if out and id(piece) not in forced \
                and len(re.sub(r'\s', '', piece)) < MIN_SENT_CHARS \
                and not _ends_with_sent_punct(piece):
            out[-1] += piece
        else:
            out.append(piece.strip())
    return out


def _ends_with_sent_punct(text):
    """文本是否以句末标点收尾（不考虑小数点/缩写点的例外）。"""
    s = (text or '').rstrip().rstrip('"\'）)》」』')
    return bool(s) and s[-1] in _SENT_END


def _split_by_words(text, max_words):
    """把超长的句子按词数上限拆开。

    ★ 优先在**从句边界**断开，而不是机械按词数硬切 ——
      固定长度窗口会破坏语义上下文（ACL N13-1023 明确指出这一点）。
      例："...our 28 core has now hit qs." 若按 20 词硬切，会切成
          "...has now" + "hit qs." —— 后半截语义不完整，模型会把
          "qs" 当成拼写错误来解释。优先在逗号/顿号处断就好得多。
    """
    words = text.split()
    if len(words) <= max_words:
        return [text]
    # 软边界：逗号、顿号、以及分号后的空格（英文里逗号后必有空格）
    soft = []
    for i, w in enumerate(words):
        if w.endswith((',', ';', ':', '，', '、', '；', '：')) and i + 1 < len(words):
            soft.append(i + 1)          # 在这个词**之后**断
    out = []
    start = 0
    while len(words) - start > max_words:
        # 在 [start+max_words//2, start+max_words] 区间里找最靠后的软边界
        lo = start + max_words // 2
        hi = start + max_words
        cand = [b for b in soft if lo < b <= hi]
        cut = cand[-1] if cand else hi
        out.append(' '.join(words[start:cut]))
        start = cut
    if start < len(words):
        out.append(' '.join(words[start:]))
    return out


def _split_by_len(text, max_chars):
    """把超长的**中文**句子按字符数上限拆开。

    中文没有空格，按词切不了，只能按字数切 —— 在最近的标点/停顿处优先断，
    实在没有就在字符上限处断。
    """
    s = text.strip()
    if len(s) <= max_chars:
        return [text]
    out = []
    rest = s
    while len(rest) > max_chars:
        # 在前 max_chars 个字符里找最靠后的句末标点，作为优先断点
        cut = -1
        for k in range(max_chars - 1, max_chars // 2, -1):
            if rest[k] in _SENT_END:
                cut = k
                break
        if cut < 0:
            cut = max_chars - 1          # 没有标点就按上限硬断（<= max_chars 字）
        out.append(rest[:cut + 1].strip())
        rest = rest[cut + 1:].strip()
    if rest:
        out.append(rest)
    return out


def detect_lang(text):
    """粗判语言：ko / ja / zh / en / ''（判别不出）。"""
    if _HANGUL.search(text or ''):
        return 'ko'
    if _KANA.search(text or ''):
        return 'ja'
    if _CJK.search(text or ''):
        return 'zh'
    if _LATIN.search(text or ''):
        return 'en'
    return ''


def norm_key(sentence):
    return ' '.join((sentence or '').split())


def ends_sentence(text):
    """段/句是否以句末标点收尾（C-099① 用来判断段尾是不是半句）。

    与 split_sentences 保持一致：末尾的 '.' 若是小数点或缩写点，
    不算句末（例如 "It cost 1.5" 仍是半句，"Dr. Smith" 也不是）。
    """
    s = (text or '').rstrip().rstrip('"\'）)》」』')
    if not s:
        return False
    # 末尾连续标点整体看待
    i = len(s) - 1
    while i > 0 and s[i] in _SENT_END:
        i -= 1
    tail = s[i + 1:]
    if not tail:
        return False
    if tail[-1] == '.':
        if _is_decimal_point(s, len(s) - 1) or _is_abbrev_boundary(s, len(s) - 1):
            return False
    return True


# ── prompt / 清洗 ───────────────────────────────────────────────────────
_LANG_NAME = {'zh': 'Chinese', 'en': 'English', 'ja': 'Japanese', 'ko': 'Korean'}
# C-102：Hy-MT2 **没有默认 system prompt**，官方指令直接放 user 消息里
# （Default Translation 模板，见 tencent/Hy-MT2-1.8B README）。原先给通用
# Instruct 模型自造的 system prompt 已废弃。
_TRANSLATE_INSTR = ('Translate the following text into {dst}. Note that you should '
                    'only output the translated result without any additional '
                    'explanation:\n\n{text}')
# C-099②：带上一句原文做上下文。用 MT2 的「背景信息」模板（Structured Data 2 的
# 简化版）：上下文明确标注仅供消歧，待翻译文本单独放在 [Source Text] 下。
_TRANSLATE_CTX_INSTR = ('[Background Information]\n{ctx}\n\n'
                        'Translate the following text into {dst}, taking the provided '
                        'background information into consideration. Output ONLY the '
                        'translated text without any additional explanation.\n\n'
                        '[Source Text]\n{text}')
_TAG_RE = re.compile(r'<\|[^<>]{0,60}\|>')
CTX_MAX_CHARS = 160          # 上下文截断长度（控制 prompt 长度，避免延迟涨太多）

# ── H-003 术语表（--mt-glossary）────────────────────────────────────────
# 走 MT2 官方 **Terminology 模板**（README 第 76 行）：先给「参考译法」，再下翻译指令。
# 默认表是芯片/硬件会议场景的术语 —— 起因是「QS」被两个模型都译错（QS =
# Qualification Sample 资格样品，不是 QPS；也不是「击打」）。
GLOSSARY = {
    'QS': '资格样品（QS）',
    'ES': '工程样品（ES）',
    'power on': '点亮',
    'power-on': '点亮',
    'tape-out': '流片',
    'tapeout': '流片',
    'go to market': '推向市场',
    'share': '市场份额',
    'silicon': '芯片',
    'milestone': '里程碑',
}
_GLOSSARY_FILE = os.environ.get('LIVECAP_MT_GLOSSARY', '')
if _GLOSSARY_FILE and os.path.isfile(_GLOSSARY_FILE):
    try:
        GLOSSARY.update(json.load(open(_GLOSSARY_FILE, encoding='utf-8')))
    except Exception:
        pass
_TRANSLATE_TERM_INSTR = ('Reference the following translations:\n{terms}\n\n'
                         'Translate the following text into {dst}. Note that you must '
                         'ONLY output the translated result without any additional '
                         'explanation:\n\n{text}')
_TRANSLATE_TERM_CTX_INSTR = ('Reference the following translations:\n{terms}\n\n'
                             '[Background Information]\n{ctx}\n\n'
                             'Translate the following text into {dst}, taking the provided '
                             'background information into consideration. Output ONLY the '
                             'translated text without any additional explanation.\n\n'
                             '[Source Text]\n{text}')


def build_messages(text, tgt, src=None, ctx=None, glossary=None):
    """渲染成 messages。MT2 无 system prompt：指令与待翻译文本都在 user 消息里。

    glossary：{原文术语: 指定译法} 字典，非空时走官方 Terminology 模板（H-003）。
    """
    terms = ''
    if glossary:
        terms = '\n'.join(f'{k} translates to {v}' for k, v in glossary.items())
    if ctx:
        ctx = ' '.join((ctx or '').split())[:CTX_MAX_CHARS]
        if terms:
            user = _TRANSLATE_TERM_CTX_INSTR.format(terms=terms, ctx=ctx,
                                                    dst=_LANG_NAME[tgt], text=text)
        else:
            user = _TRANSLATE_CTX_INSTR.format(ctx=ctx, dst=_LANG_NAME[tgt], text=text)
    else:
        if terms:
            user = _TRANSLATE_TERM_INSTR.format(terms=terms, dst=_LANG_NAME[tgt], text=text)
        else:
            user = _TRANSLATE_INSTR.format(dst=_LANG_NAME[tgt], text=text)
    return [{'role': 'user', 'content': user}]


def extract_answer(raw):
    """去掉 think 段、answer 标签、Hunyuan 特殊 token，只留译文正文。

    C-102：MT2 不输出 <answer> 包裹与 think 块，但保留清洗逻辑无妨（防御性）。
    """
    s = raw or ''
    s = re.sub(r'<think>.*?</think>', '', s, flags=re.S)      # 完整 think 块
    s = re.sub(r'<think>.*$', '', s, flags=re.S)              # 未闭合 think
    if '</answer>' in s:
        s = s.split('</answer>')[0]
    s = s.replace('<answer>', '').replace('</answer>', '')
    s = _TAG_RE.sub('', s)
    s = s.replace('\ufffd', '')
    return s.strip().strip('"').strip()


# ── A0 transformers 延迟导入的并发安全 ─────────────────────────────────
# transformers 4.57 用的是「延迟导入」（lazy import）：真正 import 某个类时
# 才会去执行子模块的 __init__。如果两个线程**同时**首次 import 同一个类，
# Python 的 import 锁只保证「不会重复执行模块代码」，不保证「属性已经挂好」，
# 于是其中一个线程会拿到：
#     ImportError: cannot import name 'AutoTokenizer' from 'transformers'
#
# 实测：ASR 引擎加载线程（backends.py 里 import transformers）和翻译加载线程
# （本文件里 import transformers）并发首次导入时必现，8 线程并发有 2 个失败。
#
# 这个 ImportError 落在 HunyuanTranslator.__init__ 里 → 翻译状态变成 'error'，
# 表现为「翻译一直加载不起来 / 翻译无法启动」。
#
# 对策：用一个模块级锁把 transformers 的 import 串行化；重试几次兜住
# 极端情况下（前一次 import 还在半途）的窗口。
_TF_IMPORT_LOCK = threading.Lock()


def import_transformers_auto_tokenizer(retries=4):
    """安全地拿到 transformers.AutoTokenizer（并发首次导入不会炸）。

    必须在**主线程、GUI 起来之后**先调一次预热（见 live_caption_app 的
    _prewarm_transformers），这样后台线程再 import 时模块早已就绪。
    """
    last = None
    for _ in range(retries):
        try:
            with _TF_IMPORT_LOCK:
                from transformers import AutoTokenizer
            return AutoTokenizer
        except ImportError as e:
            last = e
            time.sleep(0.2)          # 让前一次 import 收尾再重试
    raise last


def prewarm_transformers():
    """在主线程里预热 transformers / openvino_genai 的导入。

    放到 GUI 启动阶段（引擎加载之前）做，可以彻底避免后台线程之间的
    延迟导入竞态。返回耗时（秒）。
    """
    t0 = time.perf_counter()
    try:
        import_transformers_auto_tokenizer()
    except Exception:
        pass
    try:
        import openvino_genai  # noqa: F401
    except Exception:
        pass
    return time.perf_counter() - t0


# ── A1 翻译内核 ─────────────────────────────────────────────────────────
class HunyuanTranslator:
    """GenAI LLMPipeline 包一层：贪心、repetition_penalty 1.05、stop 在 </answer>。"""

    def __init__(self, model_dir=None, device='GPU.0', cache_dir=None, on_log=print):
        import openvino_genai as og
        AutoTokenizer = import_transformers_auto_tokenizer()
        self.og = og
        self.model_dir = model_dir or DEFAULT_MODEL
        self.device = device
        # 编译缓存放用户可写目录：客户机上 App 可能装在 Program Files（只读）。
        # 实测这个缓存能长到 2.4 GB，不能放包里。
        if not cache_dir:
            cache_root = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
            cache_dir = os.path.join(cache_root, 'Confucius4LiveCaption', 'mt_cache')
        os.makedirs(cache_dir, exist_ok=True)
        on_log(f'加载翻译模型（{device}）…')
        t0 = time.perf_counter()
        self.pipe = og.LLMPipeline(self.model_dir, device,
                                   PERFORMANCE_HINT='LATENCY', CACHE_DIR=cache_dir)
        self.tok = AutoTokenizer.from_pretrained(self.model_dir)
        self.gc = og.GenerationConfig()
        self.gc.do_sample = False
        self.gc.repetition_penalty = 1.05          # MT2 官方推荐值
        self.gc.apply_chat_template = False       # prompt 自己渲染
        # C-102：旧 Instruct 模型译文被 <answer> 标签包裹，靠 stop_strings 截；
        # MT2 直接输出译文正文，EOS 自停即可（extract_answer 仍保留防御性清洗）。
        self.gc.stop_strings = set()
        self.load_s = time.perf_counter() - t0
        self.n_calls = 0

    def render(self, text, tgt, src=None, ctx=None, glossary=None):
        # MT2 的 chat template 不引用 enable_thinking，不传该 kwarg（与旧 Instruct 不同）
        return self.tok.apply_chat_template(
            build_messages(text, tgt, src, ctx=ctx, glossary=glossary), tokenize=False,
            add_generation_prompt=True)

    def translate(self, text, tgt, on_token=None, ctx=None, glossary=None):
        """返回 dict(text, lat_ms, ttft_ms, n_in, n_out, skipped)。"""
        src = detect_lang(text)
        if tgt != 'off' and src and src == tgt:
            return dict(text=text, lat_ms=0.0, ttft_ms=0.0, n_in=0, n_out=0, skipped=True)
        prompt = self.render(text, tgt, src, ctx=ctx, glossary=glossary)
        try:
            n_in = len(self.tok(prompt, add_special_tokens=False).input_ids)
        except Exception:
            n_in = max(1, len(prompt) // 3)
        self.gc.max_new_tokens = max(24, min(256, 2 * n_in + 16))
        ttft = {}
        t0 = time.perf_counter()

        def _cb(chunk):
            ttft.setdefault('t', time.perf_counter())
            if on_token:
                try:
                    on_token(chunk)
                except Exception:
                    pass
            return False

        res = self.pipe.generate([prompt], self.gc, streamer=_cb)
        lat = (time.perf_counter() - t0) * 1000
        raw = res.texts[0] if getattr(res, 'texts', None) else str(res)
        try:
            n_out = int(res.perf_metrics.get_num_generated_tokens())
        except Exception:
            n_out = 0
        self.n_calls += 1
        return dict(text=extract_answer(raw), lat_ms=lat,
                    ttft_ms=(ttft.get('t', t0) - t0) * 1000,
                    n_in=n_in, n_out=n_out, skipped=False)

    def close(self):
        try:
            self.pipe = None
        except Exception:
            pass


# ── A2 调度 ─────────────────────────────────────────────────────────────
class _Job:
    __slots__ = ('kind', 'key', 'text')

    def __init__(self, kind, key, text):
        self.kind, self.key, self.text = kind, key, text


class TranslationService:
    """单工作线程：定稿句按句翻译，尾巴做草稿翻译。全部结果从 outbox 取。

    engine_key 见 MT_ENGINES；device/model_dir 为空时由 engine_key 推导。
    切换 engine_key 会让工作线程重启并加载新模型；换模型后译文缓存作废
    （不同量化产物的输出不一致，不能互相复用）。
    """

    # 草稿译文（尾巴的实时预览）**默认关闭**：草稿每次要翻近一整句 partial，
    # 是 GUI 下 RTF 上涨的主要来源（下面矩阵）。用户明确要求「默认不用打开，
    # 仅仅翻译已经确定的文本」，所以默认只翻定稿文本。
    #
    # 缓解矩阵（gpu_int8 ASR + GPU 翻译，60s ABBA 各 2 次，每次全新进程）：
    #   间隔 0.8s 无暂停     RTF +0.274  积压 +0.30s   ← 原始值，明显超阈值
    #   间隔 0.8s+积压暂停   RTF +0.246  积压 +0.60s   ← 单独限流不够
    #   间隔 1.5s+积压暂停   RTF +0.144  积压 +0.25s   ← 打开草稿时的配置
    #   草稿全关            RTF +0.042  积压 +0.05s（噪声级）  ← 默认
    # 机理：草稿每次翻译近一整句 partial，间隔密时占满翻译线程，per-token 回调
    # 经 GIL 与 ASR 会话线程争抢（翻译挪 NPU 也一样超阈值 → 是 CPU/GIL 争抢，非显存争用）。
    #
    # DRAFT_ON 现在是**实例属性**（不再用类常量），这样界面上的复选框可以
    # 运行时开关，不必重启程序。默认**关闭**；脚本/CI 场景可用环境变量
    # LIVECAP_DRAFT=1 显式打开（GUI 复选框的初始值也可以用 --mt-draft 覆盖）。
    # 注意：原来的 LIVECAP_NO_DRAFT=1 语义已随「默认关闭」失效，故不再读取。
    DRAFT_MIN_GAP = float(os.environ.get('LIVECAP_DRAFT_GAP', '1.5'))  # 草稿最少间隔（秒）
    DRAFT_PAUSE_BACKLOG = 0.5  # ASR 积压超过这个秒数就暂停草稿（C-100③）
    CACHE_MAX = 400            # 译文缓存条数上限（FIFO）

    def __init__(self, target='off', device='GPU.0', model_dir=None, on_log=print,
                 auto=True, engine_key=None, use_ctx=False, draft=None, glossary=False):
        """auto=False 时不立刻起加载线程（GUI 用它等 ASR 引擎就绪后再加载，
        避免两个模型在同一 GPU 上并行编译——实测会把 GUI 卡死）。

        draft：是否翻译「尾巴草稿」（未定稿的实时预览）。None = 用默认值
        （**关**，只翻定稿文本）；True/False 可显式指定。
        """
        self.on_log = on_log
        self.engine_key = engine_key or MT_DEFAULT
        self.target = target
        self.device = device
        self.model_dir = model_dir
        # 草稿译文开关：实例属性，界面复选框可以运行时改。
        # 默认**关闭**（只翻定稿文本）；脚本/CI 可用 LIVECAP_DRAFT=1 打开。
        if draft is None:
            draft = os.environ.get('LIVECAP_DRAFT') == '1'
        self.draft_on = bool(draft)
        self._apply_engine_defaults()
        self.q = queue.Queue()
        self.th = None
        self.lock = threading.Lock()
        self.tr = None
        self.done = OrderedDict()          # norm_key(sentence) -> 译文
        self.draft = ''
        self.outbox = []                   # [(kind, key, text)]
        self.state = 'idle'                # idle | loading | ready | error
        self.err = None
        self.lats, self.ttfts, self.tpots = [], [], []
        self.n_done = 0
        self.load_s = 0.0
        self._draft_last = 0.0
        self._draft_key = ''
        self._carry = ''                   # C-099① 段尾挂起未翻的半句
        self.seg_keys = {}                 # 段序号 -> 该段提交的句子 key 列表
        self.seg_carry = {}                # 段序号 -> 是否有半句并入/挂起
        self.use_ctx = use_ctx             # C-099② 是否带上一句原文做上下文
        # H-003：术语表开关（--mt-glossary）。开时走官方 Terminology 模板，
        # prompt 变长（约 +200 token），延迟会涨，故默认关。
        self.glossary_on = bool(glossary)
        self._last_src = ''                # 上一句原文（上下文用）
        self._seen = set()                 # 已提交过的句子（避免重复入队）
        self._busy = 0                     # 已出队、正在翻译中的任务数
        self._reload = threading.Event()   # 请求工作线程换模型重建
        if self.active and auto:
            self._start()

    def _apply_engine_defaults(self):
        """engine_key 决定 device / model_dir；显式传入的 device、model_dir 优先。"""
        cfg = MT_ENGINES.get(self.engine_key)
        if not cfg:
            return
        if cfg.get('device'):
            self.device = cfg['device']
        if cfg.get('model'):
            self.model_dir = cfg['model']

    # -- 生命周期 --------------------------------------------------------
    @property
    def active(self):
        return self.target != 'off'

    @property
    def device_desc(self):
        """给界面/日志用的一行描述（设备 + 模型）。"""
        cfg = MT_ENGINES.get(self.engine_key)
        base = (cfg or {}).get('label') or self.engine_key
        return f'{base} · {self.device}'

    def set_target(self, target):
        self.target = target
        if self.active and not self._thread_alive():
            self._start()
        if not self.active:
            self.draft = ''

    def _thread_alive(self):
        """翻译工作线程是否还活着。

        注意不能只看 ``self.th is None``：加载失败时线程会退出，但 ``self.th``
        仍然指向那个**已死**的线程对象。于是再选一次翻译语言也不会重启，
        状态永远停在失败/加载中（实测卡在 'error' 且无法恢复）。
        """
        return self.th is not None and self.th.is_alive()

    def set_engine(self, engine_key):
        """热切换翻译后端（设备 × 量化）。目标语言为 off 时只记住，下次开启生效。"""
        if engine_key not in MT_ENGINES:
            self.on_log(f'未知的翻译后端：{engine_key}')
            return False
        if engine_key == self.engine_key:
            return True
        self.engine_key = engine_key
        # 重置为该 engine 的默认值（覆盖上次的 --mt-device）
        cfg = MT_ENGINES[engine_key]
        self.device = cfg.get('device') or 'GPU.0'
        self.model_dir = cfg.get('model')
        if not self.active:
            return True                      # 翻译关着，只记住，下次开启时生效
        if not self._thread_alive():
            # 上次的工作线程已经死了（加载失败退出）：这里必须**真的重启**，
            # 否则状态会停在 'loading' 却没有线程去加载 —— 表现为
            # 「翻译 GPU.0 加载中…」永远不变。
            self.err = None
            self._start()
            return True
        self.state = 'loading'
        self._reload.set()
        self.q.put(_Job('switch', '', ''))   # 哨兵：唤醒可能阻塞在 get() 上的线程
        return True

    def _start(self):
        self.state = 'loading'
        self._reload.clear()
        self.th = threading.Thread(target=self._loop, daemon=True)
        self.th.start()

    def restart(self):
        """强制重启翻译工作线程（加载失败或卡住后的重试入口）。

        与 set_target 的区别：set_target 只在「线程不存在或已死」时才重启，
        而这里会先把旧线程停掉再起新的 —— 覆盖「线程还活着但卡在加载中」
        的情况（用户点重试时需要这个语义）。
        """
        if not self.active:
            return False
        if self.th is not None:
            try:
                self.q.put(None)
                self.th.join(timeout=5)
            except Exception:
                pass
            self.th = None
        # 清掉上一次失败留下的东西，避免旧错误信息误导
        self.err = None
        self._start()
        return True

    def close(self):
        if self.th:
            self.q.put(None)
            self.th.join(timeout=5)
            self.th = None
        self.state = 'idle'

    # -- 提交 ------------------------------------------------------------
    def submit(self, sentence, seg=None):
        """定稿段：分句后逐句提交，命中缓存或已提交过则跳过。

        C-099①：ASR 在 12–20 s 处硬切段，段尾经常是半句。半句单独翻会语义错
        （段尾半句 → 单独译出），所以段尾没有句末标点时**不单独翻**，
        挂起作为前缀并入下一段首句一起翻；flush() 时（最后一段/停止）必须补翻。

        seg 是该段的序号（App 的 blocks 下标），用来记住这段的译文由哪些句子组成
        —— 半句并入下一段后，本段译文会少那一截，渲染时靠 seg_keys 对齐。
        """
        if not self.active:
            return []
        text = (sentence or '').strip()
        if not text:
            return []
        if self._carry:                        # 上一段挂起的半句接在本段开头
            text = self._carry + ' ' + text
            self._carry = ''
            carried_in = True
        else:
            carried_in = False
        sents = split_sentences(text)
        if not sents:
            return []
        has_carry = False
        last = sents[-1]
        if not ends_sentence(last):            # 段尾是半句 -> 挂起，等下一段
            self._carry = last
            sents = sents[:-1]
            has_carry = True
        keys = []
        for s in sents:
            k = norm_key(s)
            if not k or k in self._seen:
                continue
            self._seen.add(k)
            keys.append(k)
            if k in self.done:
                continue
            self.q.put(_Job('final', k, s))
        if seg is not None:
            self.seg_keys[seg] = keys
            self.seg_carry[seg] = has_carry or carried_in
        return keys

    def flush(self, seg=None):
        """收尾：把挂起的半句补翻（C-099①：最后一段或停止时不能丢）。"""
        if not self.active or not self._carry:
            return []
        s, self._carry = self._carry, ''
        k = norm_key(s)
        if not k:
            return []
        if k not in self._seen:
            self._seen.add(k)
            if k not in self.done:
                self.q.put(_Job('final', k, s))
        if seg is not None:
            self.seg_keys.setdefault(seg, [])
            if k not in self.seg_keys[seg]:
                self.seg_keys[seg].append(k)
        return [k] if k else []

    def mt_of_seg(self, seg):
        """取某段的译文（按该段实际提交的句子拼，不含并入下一段的半句）。"""
        if not self.active:
            return None
        keys = self.seg_keys.get(seg)
        if not keys:
            return None
        parts = [self.done.get(k) or '' for k in keys]
        out = ' '.join(p for p in parts if p).strip()
        return out or None

    @property
    def carry(self):
        """当前挂起未翻的半句（界面可用来提示）。"""
        return self._carry

    def set_draft(self, on):
        """开关「草稿译文」（尾巴的实时预览）。

        默认**关闭** —— 只翻译已经定稿的文本。打开后界面会用浅蓝色显示
        还没定稿的那句的实时译文（每次草稿要翻近一整句，是 GUI 下 RTF
        上涨的主要来源：关掉 +0.042，打开 1.5s 间隔 + 积压暂停 +0.144）。
        """
        self.draft_on = bool(on)
        if not self.draft_on:
            # 关掉后立刻丢掉已有的草稿译文，别让界面继续显示旧预览
            with self.lock:
                self.draft = ''
                self._draft_key = ''
        return self.draft_on

    def maybe_draft(self, text, asr_backlog=0.0):
        """尾巴草稿：队列空闲、内容有变化、距上次 >= DRAFT_MIN_GAP 才提交。

        默认【关闭】（只翻定稿文本）—— 用户可在界面复选框里打开。
        打开时的限流配置：间隔 1.5s + ASR 有积压时暂停（定稿翻译不受影响）。
        实测草稿是 GUI 下 RTF 上涨的唯一主因：每次草稿都近一整句的翻译算力，
        0.8s 间隔下翻译线程被占满，经 GIL 与 ASR 会话线程争抢（RTF +0.274）。
        1.5s + 积压暂停压到 +0.144，是唯一既保住实时预览、又不破 0.15
        阈值的配置。
        """
        if not self.active or self.state != 'ready':
            return
        if not self.draft_on:
            return
        if asr_backlog >= self.DRAFT_PAUSE_BACKLOG:
            return
        k = norm_key(text)
        if not k or k == self._draft_key:
            return
        now = time.perf_counter()
        if now - self._draft_last < self.DRAFT_MIN_GAP:
            return
        if self.q.qsize() > 0:
            return
        self._draft_key = k
        self._draft_last = now
        self.q.put(_Job('draft', k, text))

    # -- 取结果 ----------------------------------------------------------
    def get(self, sentence):
        return self.done.get(norm_key(sentence))

    def pop_outbox(self):
        with self.lock:
            out, self.outbox = self.outbox, []
        return out

    @property
    def pending(self):
        return self.q.qsize() + self._busy

    def summary(self):
        def _pct(a, p):
            return float(np.percentile(a, p)) if a else None
        tp = [t for t in self.tpots if t]
        return dict(n=self.n_done, pending=self.pending,
                    lat_med=_pct(self.lats, 50), lat_p95=_pct(self.lats, 95),
                    ttft_med=_pct(self.ttfts, 50),
                    tok_s=float(1000.0 / np.median(tp)) if tp else None)

    def wait_idle(self, timeout=60):
        """等队列排空且在途任务处理完（CLI 收尾用）。"""
        end = time.perf_counter() + timeout
        while time.perf_counter() < end and (self.pending or self.state == 'loading'):
            time.sleep(0.1)

    # -- 工作线程 --------------------------------------------------------
    def _loop(self):
        tr = None
        try:
            while True:
                try:
                    self._reload.clear()
                    tr = HunyuanTranslator(self.model_dir, self.device,
                                          on_log=self.on_log)
                except Exception as e:
                    self.state, self.err = 'error', f'{type(e).__name__}: {e}'
                    self.on_log(f'翻译模型加载失败：{self.err}')
                    return
                self.tr = tr
                self.load_s = tr.load_s
                with self.lock:
                    # 换模型后旧译文不再可信（不同量化产物输出不同），清掉缓存与统计
                    self.done.clear()
                    self._seen.clear()
                    self._carry = ''
                    self.seg_keys.clear()
                    self.seg_carry.clear()
                    self._last_src = ''
                    self.draft = ''
                    self.lats.clear()
                    self.ttfts.clear()
                    self.tpots.clear()
                    self.n_done = 0
                self.state = 'ready'
                self.err = None
                self.on_log(f'翻译模型就绪（{self.device_desc}，加载 {tr.load_s:.1f} s）')
                _run_jobs(self, tr)
                # 旧实例必须在这里立刻释放：GenAI 的 LLMPipeline 持有编译缓存和
                # 设备句柄，不释放的话连续切换会一路吃显存/NPU 内存。
                self.tr = None
                try:
                    tr.close()
                except Exception:
                    pass
                tr = None
                if self._reload.is_set():
                    self.state = 'loading'      # 别让 wait_idle 以为已就绪
                    continue
                return
        finally:
            if tr is not None:
                try:
                    tr.close()
                except Exception:
                    pass


def _run_jobs(svc, tr):
    """处理任务直到收到 None（收工）或 svc._reload 被置位（换模型）。

    单独拆出来是为了让「切换后重建」时旧模型能及时 close 掉——GenAI 的
    LLMPipeline 持有编译缓存和设备句柄，不释放会让 NPU/GPU 显存不降。
    """
    while True:
        try:
            job = svc.q.get(timeout=0.25)
        except queue.Empty:
            if svc._reload.is_set():
                return 'reload'
            continue
        if job is None:
            return None
        if job.kind == 'switch':
            if svc._reload.is_set():
                return 'reload'
            continue                          # 过期哨兵，忽略
        svc._busy += 1
        try:
            # C-099②：带上一句原文做上下文（关掉时 ctx=None，行为与之前一致）
            ctx = svc._last_src if svc.use_ctx else None
            # H-003：术语表（关掉时 glossary=None，行为与之前一致）
            gl = GLOSSARY if svc.glossary_on else None
            r = tr.translate(job.text, svc.target, ctx=ctx, glossary=gl)
        except Exception as e:
            svc.err = f'{type(e).__name__}: {e}'
            svc._busy -= 1
            continue
        if job.kind == 'final':
            svc._last_src = job.text       # 记下来给下一句当上下文
        with svc.lock:
            if job.kind == 'final':
                svc.done[job.key] = r['text']
                while len(svc.done) > svc.CACHE_MAX:
                    svc.done.popitem(last=False)
                if not r.get('skipped'):
                    svc.lats.append(r['lat_ms'])
                    svc.ttfts.append(r['ttft_ms'])
                    if r['n_out'] > 1 and r['lat_ms'] > r['ttft_ms']:
                        svc.tpots.append((r['lat_ms'] - r['ttft_ms']) / (r['n_out'] - 1))
                    svc.n_done += 1
                svc.outbox.append(('final', job.key, r['text']))
            else:
                svc.draft = r['text']
                svc.outbox.append(('draft', job.key, r['text']))
            svc._busy -= 1          # 结果落盘后才算完成，wait_idle 才能安全返回
