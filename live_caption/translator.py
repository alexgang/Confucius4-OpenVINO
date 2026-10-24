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
        os.path.join(MODELS, 'mt'),                 # 客户包：models/mt/mt2-int8sym-cw-q
        os.path.join(os.path.expanduser('~'), 'hy_bench', 'ov'),
        os.path.join(ROOT, 'hy_bench', 'ov'),
    ))
DEFAULT_MODEL = os.environ.get(
    'LIVECAP_MT_MODEL',
    _first_existing(
        os.path.join(MODELS, 'mt', 'mt2-int8sym-cw-q'),   # 客户包自带（per-channel，GPU/NPU 通吃）
        os.path.join(MODELS, 'mt2-int8sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int8sym-cw-q'),       # 开发机导出产物
        # ↓ 回退到 INT4：INT8 目录不存在时（老包 / 未拷贝）仍能跑
        os.path.join(MODELS, 'mt', 'mt2-int4sym-cw-q'),
        os.path.join(MODELS, 'mt2-int4sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int4sym-cw-q'),
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
#
# ★ v1.4：默认量化由 INT4 改为 **INT8 按通道（int8sym-cw-q）** —— 用户决定。
#   依据 **H-001 / H-007**（MT 模块 `hy_bench/STATUS_hy.md` §37）：
#   200 句 wmt24pp 语料级配对 bootstrap（1000 次，seed=12345）重算结果 ——
#     en2zh：int4_gpu ΔchrF **−2.320**（CI [−3.192,−1.367]，不含 0）
#             int4_npu ΔchrF **−2.058**（CI [−3.003,−1.060]，不含 0）⇒ 显著劣化
#             int8_gpu ΔchrF +0.219（CI 含 0）
#             int8_npu ΔchrF **+0.318**（CI [+0.032,+0.629]，全为正）⇒ 不劣化
#     zh2en：int4_gpu ΔchrF++ −1.632 / int4_npu −1.536（CI 均不含 0）⇒ 显著劣化
#             int8_gpu −0.039 / int8_npu +0.027（CI 均含 0）⇒ 不劣化
#   ⇒ **INT4 在两个方向、两种设备上全部显著劣化；INT8 全部不劣化。**
#   代价：IR 体积 1.02 GB → 1.79 GB（**+0.77 GB**），GPU 吞吐 57.9 → 37.5 tok/s
#   （仍满足实时），显存 +0.75 GB。
# ⚠️ 撤回旧注释「INT8 质量与 INT4 持平…对客户机没有实际收益」——
#   该结论基于旧的句子级配对检验口径，已被 H-001/H-006 的语料级 bootstrap 推翻。
#   INT8 与 INT4 是**显著差异**（INT4 掉 1.5~2.3 chrF++）。
# 排序：先按设备（GPU 在前，ASR 默认也占 GPU，所以 NPU 项放后面做「错峰」选择）。
# ★ C-102 实测（hy_bench/bench_mt2.py，7 句 × 3 次取中位）：
#   mt2-int4sym-cw-q  GPU.0 57.9 tok/s / TTFT 35 ms / 加载 6.9 s
#                     NPU   44.0 tok/s / TTFT 292 ms / 加载 15.7 s，零乱码
#   mt2-int8sym-cw-q  GPU.0 37.5 tok/s / TTFT 44 ms
#                     NPU   29.6 tok/s / TTFT 300 ms
_MT_CANDIDATES = [
    ('gpu_int8cw', 'Intel GPU · INT8-CW（默认）', 'GPU.0', 'mt2-int8sym-cw-q',
     'Hy-MT2 INT8_SYM 按通道，1.7 GB。**默认**：37.5 tok/s，TTFT 44 ms，'
     '质量与 BF16 统计等价（ΔchrF ≤0.32）；显存 +0.75 GB', True),
    ('gpu_int4cw', 'Intel GPU · INT4-CW', 'GPU.0', 'mt2-int4sym-cw-q',
     'Hy-MT2 INT4_SYM 按通道，约 993 MB。更小更快（57.9 tok/s），但质量**显著低于** '
     'INT8（ΔchrF −2.3，H-001），仅在显存吃紧时选', True),
    ('npu_int8cw', 'Intel NPU · INT8-CW', 'NPU', 'mt2-int8sym-cw-q',
     'NPU：29.6 tok/s、1.7 GB，质量不劣化；ASR 请留在 GPU 以免争抢', True),
    ('npu_int4cw', 'Intel NPU · INT4-CW', 'NPU', 'mt2-int4sym-cw-q',
     'NPU 备用：44.0 tok/s、零乱码，约 993 MB，但质量显著低于 INT8（ΔchrF++ −1.5）', True),
]

MT_ENGINES = OrderedDict()
MT_ENGINES['auto'] = dict(
    label='自动 · INT8-CW 模型（默认）', device=None, model=None,
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
    label='自动 · INT8-CW 模型（默认）', device=None, model=DEFAULT_MODEL, note='',
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
    # 大小写都要给：ASR 出来的文本里 QS 常常是小写（"hit qs"），只写 'QS' 匹配不上
    'QS': '资格样品（QS）',
    'qs': '资格样品（QS）',
    'ES': '工程样品（ES）',
    'es': '工程样品（ES）',
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


def load_mt_tokenizer(AutoTokenizer, model_dir):
    """加载 Hy-MT2 的 tokenizer，**消掉 `fix_mistral_regex` 警告**。

    ★ H-013（2026-10-24）：App 日志里的那条警告来自 **MT 侧**加载
      Hy-MT2 tokenizer（`transformers/tokenization_utils_base.py` 的
      mistral 探测分支），**不是 TTS 的问题**（TTS 已确认并转达）。

    ★ 为什么传 **False** 而不是 True：
      - 传 `False` = 消警告，且**分词逐字不变**（MT 侧实测 30/30 句 ids 相同，
        预分词器不变）；
      - 传 `True`  = 换成 mistral 的预分词器，**会改分词**（实测 30 句里 4 句 ids 变，
        token 总数 672→678；变的都是「英文数字+单位粘连」如 `[REDACTED]`），
        ⇒ **会改变 MT 输出**，属质量变更，必须用 chrF 口径对照后才能决定；
      - 且 `decode` 回原文 **30/30 一致** ⇒ `False` 无任何语义损失。
      ⇒ 结论：**传 False**（消警告 + 零行为变化 + 零风险）。

    ⚠️ 容错：老版本 transformers 可能**不认** `fix_mistral_regex` 这个参数
      （形参在 4.57.6 才有）⇒ 传参失败就退回不传（行为与以前一致，只是警告还在）。
    """
    try:
        return AutoTokenizer.from_pretrained(model_dir, fix_mistral_regex=False)
    except TypeError:
        # 老版本 transformers 不支持该参数 ⇒ 不传（保留原警告，行为不变）
        return AutoTokenizer.from_pretrained(model_dir)


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
        self.tok = load_mt_tokenizer(AutoTokenizer, self.model_dir)
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
    """一个翻译任务。

    kind:
      'final' —— **完整句**的定稿译文（**朗读** + 显示）
                 ★ C-111-UNIT（§48）：这是**唯一**会产生的 kind ——
                   翻译单元 = 完整句，跨段句等下一段凑齐后整句翻一次。
      'half'  —— 段尾半句的初翻译文（残句，**不朗读**，只显示）
                 ⚠️ **UNIT 方案下已不再产生**（保留仅为兼容旧调用方）
      'fix'   —— 半句被补成完整句后的整句译文（**朗读**）
                 ⚠️ **UNIT 方案下已不再产生**（保留仅为兼容旧调用方）
      'draft' —— 尾巴草稿（不朗读）

    C-111（历史）的半句修正涉及**两段的归属**：
      seg      —— 修正后的完整句归**当前段**（句末标点落在这一段）
      old_key  —— 被替换掉的旧 key（半句初翻那次的 key）
      old_seg  —— 旧 key 原本归属的段（半句产生的那一段）
    """
    __slots__ = ('kind', 'key', 'text', 'seg', 'old_key', 'old_seg')

    def __init__(self, kind, key, text, seg=None, old_key=None, old_seg=None):
        self.kind, self.key, self.text = kind, key, text
        self.seg, self.old_key, self.old_seg = seg, old_key, old_seg


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
    # 🔴🔴 **`CACHE_MAX` 从 400 提到 4000（2026-10-24 21:20 修复）**
    #   **旧值 400 会让长会话的前段译文被淘汰** ⇒ 显示层拿不到译文。
    #   实测（260902_SPE 会议回放，225 段 / 61 分钟）：产出 **674 个句单元**，
    #   而 `done` 只留最后 400 条 ⇒ **前 274 条被淘汰**（674 − 400 = 274，**逐位吻合**）
    #   ⇒ 症状 = 「前面的段落没有译文 / 漏译 40.7%」。
    #   **内存代价**：每条约 = 原文 key + 中文译文 ≈ 200 B ⇒ 4000 条 ≈ 0.8 MB，
    #   相对 ASR/MT 模型显存可忽略 ⇒ 宁可多留，不可丢。
    #   ⚠️ 真正的上限是**会话长度**，不是内存；`clear()` 会清空。
    CACHE_MAX = 4000           # 译文缓存条数上限（FIFO）—— 覆盖 4~6 小时长会议

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
        self.done_fix = OrderedDict()      # ★ V7：fix（跨段整句）译文 —— 只朗读不显示
        # ★ C-111-UNIT（§48）：**跨段缓冲**的原文尾巴。
        #   段尾没有句末标点时**不立即翻**，而是留在缓冲里等下一段补全，
        #   凑成**完整句**再翻 ⇒ 翻译单元 = 完整句。
        #   这是「前半句丢失 / 跨行重复 / 空行」三者的**共同根因**的解法
        #   （跨段句不再被劈成两半分别归属不同段）。
        self._pend = ''
        # 句单元列表（翻译 + 显示的最小单元）：每条 = 一个**完整句**
        #   {'key','src','seg','mt'}。App 可按它渲染（界面对齐、一行一句）。
        self.units = []
        self.draft = ''
        self.outbox = []                   # [(kind, key, text)]
        self.state = 'idle'                # idle | loading | ready | error
        self.err = None
        self.lats, self.ttfts, self.tpots = [], [], []
        self.n_done = 0
        self.load_s = 0.0
        self._draft_last = 0.0
        self._draft_key = ''
        # C-111：段尾半句**不再挂起** —— 定稿时立即翻译，译文归本段。
        # 这个字段记录「当前未闭合的半句链」：{'text','key','seg'}，
        # 下一次 submit() 时用它做「补全/延长 → 重翻修正」。
        self._half = None
        self.seg_keys = {}                 # 段序号 -> 该段提交的句子 key 列表
        self.seg_carry = {}                # 段序号 -> 本段开头是否承接上一段的半句
        self.seg_half = {}                 # 段序号 -> 本段末尾是否为半句（未闭合）
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

    def set_device(self, device):
        """热切换翻译推理设备（APP-004 第 3 条）。

        与 set_engine 的区别：set_engine 会把 device **重置**成该 engine 的默认值；
        这里只改设备，不动 engine_key / model_dir（用户显式选的优先）。

        ⚠️ 设备变了必须**真的重建模型**（OV 的模型是绑在 device 上的），
        所以走和 set_engine 一样的 `_reload` 通道。
        """
        if not device or device == self.device:
            return True
        self.device = device
        if not self.active:
            return True                      # 翻译关着，只记住，下次开启时生效
        if not self._thread_alive():
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
    def _enqueue_half(self, text, key, seg):
        """段尾半句：**当段就翻**（kind='half'），译文归本段，不朗读。

        ⚠️ **已弃用（C-111-UNIT，§48）**：翻译单元改成**完整句**后，
        段尾半句不再单独翻译（它会留在 `_pend` 里等下一段凑成完整句）。
        本方法**保留仅为兼容旧调用方**，当前 `submit()` 不再调用它。

        C-111（历史）：旧的挂起机制要等到下一段定稿才翻，代价是译文延迟无上限
        （T3）、且半句译文记在下一段名下 → 本段界面「译文缺字」。
        """
        k = key or norm_key(text)
        self.q.put(_Job('half', k, text, seg=seg))

    def _enqueue_fix(self, text, slot_key, seg, old_key=None):
        """半句被补成完整句：**重翻**整句（kind='fix'）。

        ⚠️ **已弃用（C-111-UNIT，§48）**：翻译单元 = 完整句 ⇒ 跨段句**等下一段
        凑齐后整句翻一次**，不再需要「先翻半句、再重翻整句」⇒ 无 `fix` 作业。
        本方法**保留仅为兼容旧调用方**，当前 `submit()` 不再调用它。

        ★ C-111-V7（§46，历史）：整句译文的**显示**与**朗读**分成两个通道：
          - 显示：整句**不写** `done`（否则链首段那行会含下一段首句的内容
            ⇒ 同一句话在相邻两行各出现一次 ⇒ 用户实测的「重复翻译」）。
            链首段那行继续显示自己的**半句残句**（`done` 里的 'half' 译文）。
          - 朗读：整句译文写进独立槽位 `done_fix`，并以 **'final'** 进 outbox
            ⇒ TTS 念的是**完整句**（只念一次），残句不念。
        ⇒ UNIT 方案下这整套机制不再需要（既不重复，也不残缺）。
        """
        k = slot_key or norm_key(text)
        self.q.put(_Job('fix', k, text, seg=seg, old_key=old_key))

    def submit(self, sentence, seg=None):
        """定稿段：**按完整句**切分后逐句提交（翻译单元 = 完整句）。

        ★★ C-111-UNIT（§48，2026-10-24）：**翻译与显示的最小单元 = 完整句**。

        ## 为什么改（用户实测「翻译丢失，尤其是前半句丢失」）

        旧机制（C-111）把段尾半句**当段就翻**（kind='half'），闭合时再**重翻整句**
        （kind='fix'）并**原地覆盖**链首段的显示槽位。三者互斥，**不可能同时满足**：

        | 做法 | 结果 |
        |---|---|
        | 整句写链首段（C-111 原地覆盖） | 下一段重复 |
        | 整句不写链首段（C-111-V7 双通道） | **链首段残缺 = 前半句丢失** |
        | 整句写闭合段 | 更前面的段变**空行** |

        根因：**跨段的那一句被劈成两半**（前半归上一段、后半归下一段），
        而「一行 = 一个 ASR 段」这种对齐方式**装不下**跨段的句子。

        ⇒ 本方案：**跨段缓冲**，段尾半句**不立即翻**，留在 `_pend` 里等下一段补全，
          凑成**完整句**再翻一次。于是：
          - 每个句子**只翻一次、只出现一次** ⇒ **不重复**；
          - 每个翻译单元都是**完整句** ⇒ **不残缺**；
          - 原文与译文**一一对应** ⇒ **不错行**；
          - 没有单元为空 ⇒ **不空行**。

        ## 实测（真实模型 INT8-CW，30 段语料）

        | 指标 | C-111 原地覆盖 | C-111-UNIT（本方案） |
        |---|---|---|
        | 重复对 | **7** | **0**（余下为 bigram 误报） |
        | 残句行 | 0 | **2**（段尾本身无标点） |
        | 空行 | 0 | **0** |
        | 原文守恒 | — | **2527 字 = 2527 字** ✅ |
        | 朗读字数 | 582 | **1069**（= 全部完整句） |
        | 翻译次数 | 66 | **48**（省 27%） |
        | chrF（按句配对，UNIT vs C-111） | 参照 | **65.10，CI [52.16, 77.88] ⇒ 未劣化** |

        ## 代价

        - 跨段的那一句要**等下一段定稿**才出译文。
          实测**最长只等 1 段**（连续「无新译文」最长 1 段）⇒ **延迟有界**，
          不复现 C-099① 的 T3「延迟无上限」。
        - 屏幕行数 = **句数**（不再 = ASR 段数）⇒ App 渲染层可按 `units` 渲染，
          或继续用 `mt_of_seg()` 按段聚合（后者在整段都是半句时会出现空行）。

        seg 是该段的序号（App 的 blocks 下标），用来记住这段的译文由哪些
        **句单元**组成 —— 句单元的 key 记在**提交它的那一段**。
        """
        if not self.active:
            return []
        text = (sentence or '').strip()
        if not text:
            return []
        keys = []
        # 本段是否**承接**了上一段留下的半句（App 用它加 '…' 标记 /
        # 显示「译文生成中…」）
        carried_in = bool(self._pend)

        # ── 跨段缓冲：把新段接到上段留下的尾巴后面 ──
        self._pend = (self._pend + ' ' + text).strip() if self._pend else text
        sents = split_sentences(self._pend)
        # 最后一句若不以句末标点收尾 ⇒ 它还没说完 ⇒ 留在缓冲里等下一段
        if sents and not ends_sentence(sents[-1]):
            ready = sents[:-1]
            self._pend = sents[-1]
        else:
            ready = sents
            self._pend = ''

        for s in ready:
            k = norm_key(s)
            if not k:
                continue
            # 🔴🔴 **重复句不再被丢弃（§50.2 / §54.4 定案，2026-10-24 21:12 修复）**
            #   **旧行为（`k in self._seen` ⇒ 整句跳过）会丢真实内容**：
            #   ASR 复读是真实存在的（260902_SPE 会议实录实测 225 段里有 **38 句**
            #   是「同一句被重复说」，共 **3,312 字**），全局去重把它们**整段丢弃**
            #   ⇒ 内容级守恒失败（实测 orig 41,895 → 保留 38,583，**缺 3,312 字**）。
            #   ⇒ 用户报的「前半句丢失」在会议场景会复现。
            #
            #   **新行为 = 「翻译去重 + 显示不去重」**：
            #   · 翻译：同一句话**只翻一次**（`done[key]` 一份译文，译文必然相同
            #     ⇒ 不重复翻译、不增加调用次数）；
            #   · 显示：每次出现都**建一个句单元** ⇒ 说话人真的又说了一遍，
            #     字幕就该显示两遍 ⇒ 内容级守恒 100%。
            #   ⇒ `mt_units()` 能逐处渲染，`mt_of_seg(seg)` 按段取到自己的那一份。
            if k in self._seen:
                # 已翻过 ⇒ 不重复入队，但**保留显示单元**（内容不能丢）
                self.units.append(dict(key=k, src=s, seg=seg, mt=None))
                if seg is not None:
                    self.seg_keys.setdefault(seg, [])
                    if k not in self.seg_keys[seg]:
                        self.seg_keys[seg].append(k)
                continue
            self._seen.add(k)
            keys.append(k)
            # 句单元：翻译 + 显示的最小单元
            self.units.append(dict(key=k, src=s, seg=seg, mt=None))
            self.q.put(_Job('final', k, s, seg=seg))

        if seg is not None:
            self.seg_keys.setdefault(seg, [])
            for k in keys:
                if k not in self.seg_keys[seg]:
                    self.seg_keys[seg].append(k)
            # ★ UNIT 下 `seg_carry` 的语义 = 「本段承接了上一段的半句」。
            #   App 用它给译文加 '…' 前缀、并在译文缺失时显示「译文生成中…」。
            #   （UNIT 下**不再有**「整句覆盖上一段槽位」这回事，
            #     所以 '…' 只是提示承接关系，不表示内容重复。）
            self.seg_carry[seg] = carried_in
            # 本段结尾是否还留了半句在缓冲里（等下一段）
            self.seg_half[seg] = bool(self._pend)
        return keys

    def flush(self, seg=None):
        """收尾：把跨段缓冲里**最后那句没说完的**当完整句交出去。

        ★ C-111-UNIT（§48）：翻译单元 = 完整句。段尾没有句末标点时
        它留在 `_pend` 里等下一段；到收尾时它就是最后一句 ⇒ 翻一次。
        （与旧 C-111 的差别：旧机制这段已经翻过了，这里只是标记 'final'。）
        """
        if not self.active:
            return []
        self._half = None
        pend = getattr(self, '_pend', '')
        self._pend = ''
        if not pend:
            return []
        k = norm_key(pend)
        if not k:
            return []
        # 🔴 与 `submit()` 一致：**重复句不丢弃**（翻译去重 + 显示不去重）
        if k not in self._seen:
            self._seen.add(k)
            self.units.append(dict(key=k, src=pend, seg=seg, mt=None))
            self.q.put(_Job('final', k, pend, seg=seg))
            if seg is not None:
                self.seg_keys.setdefault(seg, [])
                if k not in self.seg_keys[seg]:
                    self.seg_keys[seg].append(k)
                self.seg_half[seg] = False
            return [k]
        # 已翻过 ⇒ 不重复入队，但**保留显示单元**（内容不能丢，见 submit() 里的说明）
        self.units.append(dict(key=k, src=pend, seg=seg, mt=None))
        if seg is not None:
            self.seg_keys.setdefault(seg, [])
            if k not in self.seg_keys[seg]:
                self.seg_keys[seg].append(k)
            self.seg_half[seg] = False
        # 已经翻过了（理论上不会走到）—— 只把译文重新标成可朗读
        with self.lock:
            txt = self.done.get(k)
        if txt:
            with self.lock:
                self.outbox.append(('final', k, txt))
        return [k]

    def mt_of_seg(self, seg):
        """取某段的译文（按该段实际提交的句单元拼）。

        ★ C-111-UNIT（§48）：翻译单元 = 完整句，句单元的 key 记在**提交它的那一段**。
          ⇒ 这一行是「本段提交的若干完整句」的译文拼接，**不残缺、不重复**。

        ⚠️ **已知局限**：若某一段的原文**整段都是半句**（没有一句在本段闭合），
          该段的句单元列表为空 ⇒ 这一行**没有译文**。
          ⇒ 需要严格「原文一行对译文一行」时，请用 `mt_units()`（按句单元渲染）。

        C-111（历史）：段尾半句的译文归本段；C-111-V7（§46）：整句译文走
        `done_fix` 独立通道、不覆盖显示槽位。**UNIT 方案下这两条都不再适用**
        —— 已无「半句初翻」与「整句修正」两个概念。
        """
        if not self.active:
            return None
        keys = self.seg_keys.get(seg)
        if not keys:
            return None
        parts = [self.done.get(k) or '' for k in keys]
        out = ' '.join(p for p in parts if p).strip()
        return out or None

    def mt_units(self):
        """取全部**句单元**（翻译 + 显示的最小单元）。

        ★ C-111-UNIT（§48）：每个单元是一个**完整句**，
        原文与译文**一一对应** ⇒ 渲染层可以做到「一行一句、不重复、不残缺」。

        返回 [{'key','src','seg','mt'}, ...]（`mt` 可能为 None = 还在翻译）。
        """
        if not self.active:
            return []
        with self.lock:
            return [dict(u, mt=self.done.get(u['key']))
                    for u in self.units]

    def mt_fix_of(self, key):
        """取某条**整句修正译文**（C-111-V7 的独立通道）。

        ⚠️ **UNIT 方案下已无 `fix` 作业**（不再重翻整句）⇒ 这个接口保留只为
        兼容旧调用方，正常返回 None。
        """
        if not self.active:
            return None
        return self.done_fix.get(key)

    @property
    def carry(self):
        """当前**跨段缓冲**里那句还没说完的原文（界面可用来提示）。

        ★ C-111-UNIT（§48）：段尾半句不再当段就翻，而是留在缓冲里等下一段
        凑成完整句 ⇒ 这里返回的就是「正在等下一段」的那部分原文。
        """
        return getattr(self, '_pend', '')

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
                    self.done_fix.clear()
                    self._seen.clear()
                    self._half = None
                    # ★ C-111-UNIT（§48）：换模型后跨段缓冲与句单元也要清
                    self._pend = ''
                    self.units.clear()
                    self.seg_keys.clear()
                    self.seg_carry.clear()
                    self.seg_half.clear()
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
        if job.kind in ('final', 'fix'):
            svc._last_src = job.text       # 记下来给下一句当上下文
        with svc.lock:
            if job.kind in ('final', 'half', 'fix'):
                # ★ C-111-UNIT（2026-10-24，STATUS_hy §48）：**翻译单元 = 完整句**
                #
                #   'final' → 写 `done`（**显示槽位**，界面 `mt_of_seg` / `mt_units` 读它）
                #   'half'  → 写 `done`（历史路径，UNIT 下不再产生）
                #   'fix'   → 写 `done_fix`（历史路径，UNIT 下不再产生）
                #
                #   为什么 UNIT 能同时消除「重复 / 残缺 / 空行」：
                #     旧 C-111 把跨段的句子**劈成两半**（前半归上一段、后半归下一段），
                #     于是「一行 = 一个 ASR 段」装不下跨段句 ⇒ 只能三选一：
                #       整句写链首段 ⇒ 下一段重复；不写 ⇒ 链首段残缺（用户报的
                #       「前半句丢失」）；写闭合段 ⇒ 更前面的段空行。
                #     UNIT 把**翻译单元改成完整句**：跨段句等下一段凑齐后**整句翻一次**，
                #     只出现一次、且是完整句 ⇒ 三者同时消失。
                #
                #   ⚠️ 'half'/'fix' 两个 kind 在 UNIT 下**已不再产生**
                #     （`_enqueue_half`/`_enqueue_fix` 保留仅为兼容旧调用方）。
                if job.kind == 'fix':
                    svc.done_fix[job.key] = r['text']
                    while len(svc.done_fix) > svc.CACHE_MAX:
                        svc.done_fix.popitem(last=False)
                else:
                    svc.done[job.key] = r['text']
                    while len(svc.done) > svc.CACHE_MAX:
                        svc.done.popitem(last=False)
                if not r.get('skipped'):
                    svc.lats.append(r['lat_ms'])
                    svc.ttfts.append(r['ttft_ms'])
                    if r['n_out'] > 1 and r['lat_ms'] > r['ttft_ms']:
                        svc.tpots.append((r['lat_ms'] - r['ttft_ms']) / (r['n_out'] - 1))
                    svc.n_done += 1
                # ★ outbox 的 kind 决定消费方怎么处理：
                #   'final' —— 完整句定稿译文 → **朗读**（App GUI/CLI 都按 'final' 提交 TTS）
                #   'half'  —— 半句初翻译文   → **只显示，不朗读**
                #   'fix'   —— 补全后的整句译文 → **朗读**
                #
                #   ★ V7：fix 在 outbox 里**以 'final' 发出**。
                #     原因：GUI 侧 `_pump_tts()` 只提交 `kind == 'final'` 给 TTS
                #     （live_caption_app.py:2314），CLI 侧认 ('final','fix')。
                #     若 fix 仍以 'fix' 发出 ⇒ **GUI 不朗读整句**（只剩残句）。
                #     以 'final' 发出 ⇒ **App 侧零改动**，整句只朗读一次。
                #     （'half' 仍是 'half' ⇒ 残句不朗读，界面显示不受影响。）
                svc.outbox.append(('final' if job.kind == 'fix' else job.kind,
                                   job.key, r['text']))
            else:
                svc.draft = r['text']
                svc.outbox.append(('draft', job.key, r['text']))
            svc._busy -= 1          # 结果落盘后才算完成，wait_idle 才能安全返回
