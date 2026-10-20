r"""live_caption/translator.py — Hunyuan-1.8B-Instruct 按句实时翻译（C-098 阶段 A）

A1  HunyuanTranslator：openvino_genai LLMPipeline。集显基准实测 GenAI 49.7 tok/s /
    TTFT 56 ms，比 optimum-intel（34.2 tok/s / 76 ms）快约 45%，所以 App 走 GenAI。
A2  TranslationService：单工作线程 + 按句调度 + dict 缓存(FIFO) + 尾巴草稿。
A3  MT_ENGINES：翻译侧的「设备 × 量化」可选项，与 App 里 ASR 的 ENGINES 同构，
    支持运行时热切换（set_engine）。实测结论见 hy_bench\STATUS_hy.md：
      · int4_asym g128（现有模型）在 **NPU 上不可用**（乱码 + 慢 100 倍），只能跑 GPU；
      · **per-channel（-cw）是 NPU 可用的关键**，INT4_SYM cw 在 NPU 上 42.7 tok/s、零乱码；
      · ASR 与翻译同抢一个 NPU 时出字延迟会涨到 2.8 倍，所以两边设备要能分开选。

模型目录只读；可用环境变量 LIVECAP_MT_MODEL 覆盖 'auto' 用的模型目录。
"""
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
MODELS = os.environ.get('LIVECAP_MODELS', os.path.join(ROOT, 'models'))


def _first_existing(*candidates):
    """返回第一个存在的目录；全都不存在就返回第一个（用于给出可读的报错路径）。"""
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return candidates[0] if candidates else None


# 翻译模型目录的查找顺序（先客户包，再开发机）：
#   1) 环境变量 LIVECAP_MT_MODEL / LIVECAP_MT_CW_ROOT（显式覆盖，最高优先级）
#   2) 客户包内 <root>/models/mt-int4sym-cw-q 等（发布包自带）
#   3) 开发机 <用户目录>\hy_bench\ov\<name>（本仓库导出产物）
#   4) 开发机 <用户目录>\.openvino\models\Hunyuan-1.8B-Instruct-ov-int4
# 模型目录只读；找不到时 MT_ENGINES 里的路径仍然保留，GUI 会标注「缺模型」。
_HY_ROOT = os.environ.get(
    'LIVECAP_MT_CW_ROOT',
    _first_existing(
        os.path.join(MODELS, 'mt'),                 # 客户包：models/mt/int4sym-cw-q
        os.path.join(os.path.dirname(os.path.dirname(APP_DIR)), 'hy_bench', 'ov'),
        os.path.join(ROOT, 'hy_bench', 'ov'),
    ))
DEFAULT_MODEL = os.environ.get(
    'LIVECAP_MT_MODEL',
    _first_existing(
        os.path.join(MODELS, 'mt', 'int4sym-cw-q'),  # 客户包自带（per-channel，GPU/NPU 通吃）
        os.path.join(MODELS, 'mt-int4sym-cw-q'),
        os.path.join(MODELS, 'Hunyuan-1.8B-Instruct-ov-int4'),
        os.path.join(os.path.expanduser('~'), '.openvino', 'models',
                     'Hunyuan-1.8B-Instruct-ov-int4'),
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
_LEGACY_INT4 = None
for _cand in (os.path.join(MODELS, 'mt', 'Hunyuan-1.8B-Instruct-ov-int4'),
              os.path.join(MODELS, 'Hunyuan-1.8B-Instruct-ov-int4')):
    if os.path.isdir(_cand):
        _LEGACY_INT4 = _cand
        break

# 候选翻译后端：(key, label, device, 模型目录解析结果, 说明)
# 只有**本机真实存在**的模型才进下拉 —— 客户机上不该出现「缺模型」的项。
# int8sym-cw-q 备用件开发机有、客户包不带（1.7 GB），客户机上会自动消失。
_MT_CANDIDATES = [
    ('gpu_int4cw', 'Intel GPU · INT4-CW', 'GPU.0', 'int4sym-cw-q',
     'INT4_SYM 按通道，约 993 MB。49.4 tok/s，加载比旧模型快（11.0→5.4 s）；GPU/NPU 通吃'),
    ('npu_int4cw', 'Intel NPU · INT4-CW', 'NPU', 'int4sym-cw-q',
     'NPU 推荐：42.7 tok/s、零乱码，约 993 MB。ASR 请留在 GPU/NPU 另一侧以免争抢'),
    ('npu_int8cw', 'Intel NPU · INT8-CW', 'NPU', 'int8sym-cw-q',
     'NPU 备用：27.6 tok/s、1.7 GB，质量与 INT4 持平但慢 35%'),
]

MT_ENGINES = OrderedDict()
MT_ENGINES['auto'] = dict(
    label='自动 · INT4-CW 模型', device=None, model=None,
    note='模型目录取 LIVECAP_MT_MODEL（或包内自带模型），设备取 --mt-device（默认 GPU.0）')
for _k, _label, _dev, _name, _note in _MT_CANDIDATES:
    _m = _cw_model(_name)
    if os.path.isdir(_m):
        MT_ENGINES[_k] = dict(label=_label, device=_dev, model=_m, note=_note)
if _LEGACY_INT4:
    MT_ENGINES['gpu_int4'] = dict(
        label='Intel GPU · INT4（旧）', device='GPU.0', model=_LEGACY_INT4,
        note='Hunyuan int4_asym g128。GPU 上 TTFT 最快（20–122 ms）；NPU 上不可用')
MT_DEFAULT = 'auto'


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
_SENT_END = '.?!。？！；;…'
_SENT_RE = re.compile(r'[^' + re.escape(_SENT_END) + r']*[' + re.escape(_SENT_END) +
                      r']+|[^' + re.escape(_SENT_END) + r']+')
_CJK = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')
_KANA = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff]')
_HANGUL = re.compile(r'[\u1100-\u11ff\uac00-\ud7af]')
_LATIN = re.compile(r'[A-Za-z]')
MIN_SENT_CHARS = 4


def split_sentences(text):
    """按句末标点切句；可见字符少于 MIN_SENT_CHARS 的碎片并进上一句。"""
    out = []
    for piece in _SENT_RE.findall(text or ''):
        if not piece.strip():
            continue
        if out and len(re.sub(r'\s', '', piece)) < MIN_SENT_CHARS:
            out[-1] += piece
        else:
            out.append(piece.strip())
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
    """段/句是否以句末标点收尾（C-099① 用来判断段尾是不是半句）。"""
    s = (text or '').rstrip().rstrip('"\'）)》」』')
    return bool(s) and s[-1] in _SENT_END


# ── prompt / 清洗 ───────────────────────────────────────────────────────
_LANG_NAME = {'zh': 'Chinese', 'en': 'English', 'ja': 'Japanese', 'ko': 'Korean'}
_SYS = ("You are a professional translator. Translate the user's text from {src} to {dst}. "
        "Output ONLY the translated text, nothing else - no explanations, no notes, no tags.")
# C-099②：带上一句原文做上下文，减少术语/指代错误（"hit QS"→「达到了极限」、
# "lose share"→「丢失了很多股份」这类）。上下文明确标注「仅供参考，不要翻译」。
_SYS_CTX = ("You are a professional translator. Translate the user's text from {src} to {dst}. "
            "The previous sentence is given as context ONLY - do NOT translate it, do NOT "
            "repeat it, and do NOT let it change the meaning of the sentence you translate. "
            "Use it only to resolve ambiguous terms and references. "
            "Output ONLY the translated text, nothing else - no explanations, no notes, no tags.")
_TAG_RE = re.compile(r'<\|[^<>]{0,60}\|>')
CTX_MAX_CHARS = 160          # 上下文截断长度（控制 prompt 长度，避免延迟涨太多）


def build_messages(text, tgt, src=None, ctx=None):
    src_name = _LANG_NAME.get(src or '', 'the source language')
    if ctx:
        ctx = ' '.join((ctx or '').split())[:CTX_MAX_CHARS]
        sys_p = _SYS_CTX.format(src=src_name, dst=_LANG_NAME[tgt])
        user = (f'Previous sentence (context only, do not translate): "{ctx}"\n\n'
                f'Translate this sentence: {text}')
    else:
        sys_p = _SYS.format(src=src_name, dst=_LANG_NAME[tgt])
        user = text
    return [{'role': 'system', 'content': sys_p},
            {'role': 'user', 'content': text}]


def extract_answer(raw):
    """去掉 think 段、answer 标签、Hunyuan 特殊 token，只留译文正文。"""
    s = raw or ''
    s = re.sub(r'<think>.*?</think>', '', s, flags=re.S)      # 完整 think 块
    s = re.sub(r'<think>.*$', '', s, flags=re.S)              # 未闭合 think
    if '</answer>' in s:
        s = s.split('</answer>')[0]
    s = s.replace('<answer>', '').replace('</answer>', '')
    s = _TAG_RE.sub('', s)
    s = s.replace('\ufffd', '')
    return s.strip().strip('"').strip()


# ── A1 翻译内核 ─────────────────────────────────────────────────────────
class HunyuanTranslator:
    """GenAI LLMPipeline 包一层：贪心、repetition_penalty 1.05、stop 在 </answer>。"""

    def __init__(self, model_dir=None, device='GPU.0', cache_dir=None, on_log=print):
        import openvino_genai as og
        from transformers import AutoTokenizer
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
        self.gc.repetition_penalty = 1.05
        self.gc.apply_chat_template = False       # prompt 自己渲染
        self.gc.stop_strings = {'</answer>'}
        self.load_s = time.perf_counter() - t0
        self.n_calls = 0

    def render(self, text, tgt, src=None, ctx=None):
        return self.tok.apply_chat_template(
            build_messages(text, tgt, src, ctx=ctx), tokenize=False,
            add_generation_prompt=True, enable_thinking=False)

    def translate(self, text, tgt, on_token=None, ctx=None):
        """返回 dict(text, lat_ms, ttft_ms, n_in, n_out, skipped)。"""
        src = detect_lang(text)
        if tgt != 'off' and src and src == tgt:
            return dict(text=text, lat_ms=0.0, ttft_ms=0.0, n_in=0, n_out=0, skipped=True)
        prompt = self.render(text, tgt, src, ctx=ctx)
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

    # 草稿默认【开启】，间隔 1.5s + 积压暂停（C-100③ 实测的唯一压线安全配置）。
    # 用户反馈：关掉草稿后实时预览体验明显变差，预览优先，故默认开。
    # 缓解矩阵（gpu_int8 ASR + GPU 翻译，60s ABBA 各 2 次，每次全新进程）：
    #   间隔 0.8s 无暂停     RTF +0.274  积压 +0.30s   ← 原始值，明显超阈值
    #   间隔 0.8s+积压暂停   RTF +0.246  积压 +0.60s   ← 单独限流不够
    #   间隔 1.5s+积压暂停   RTF +0.144  积压 +0.25s   ← 默认（压线通过）
    #   草稿全关            RTF +0.042  积压 +0.05s（噪声级）
    # 机理：草稿每次翻译近一整句 partial，间隔密时占满翻译线程，per-token 回调
    # 经 GIL 与 ASR 会话线程争抢（翻译挪 NPU 也一样超阈值 → 是 CPU/GIL 争抢，非显存争用）。
    # 要最大 ASR 余量时关掉：LIVECAP_NO_DRAFT=1。
    DRAFT_ON = os.environ.get('LIVECAP_NO_DRAFT') != '1'
    DRAFT_MIN_GAP = float(os.environ.get('LIVECAP_DRAFT_GAP', '1.5'))  # 草稿最少间隔（秒）
    DRAFT_PAUSE_BACKLOG = 0.5  # ASR 积压超过这个秒数就暂停草稿（C-100③）
    CACHE_MAX = 400            # 译文缓存条数上限（FIFO）

    def __init__(self, target='off', device='GPU.0', model_dir=None, on_log=print,
                 auto=True, engine_key=None, use_ctx=False):
        """auto=False 时不立刻起加载线程（GUI 用它等 ASR 引擎就绪后再加载，
        避免两个模型在同一 GPU 上并行编译——实测会把 GUI 卡死）。"""
        self.on_log = on_log
        self.engine_key = engine_key or MT_DEFAULT
        self.target = target
        self.device = device
        self.model_dir = model_dir
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
        if self.active and self.th is None:
            self._start()
        if not self.active:
            self.draft = ''

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
        if not self.active or self.th is None:
            return True                      # 还没起线程，下次 set_target 时生效
        self.state = 'loading'
        self._reload.set()
        self.q.put(_Job('switch', '', ''))   # 哨兵：唤醒可能阻塞在 get() 上的线程
        return True

    def _start(self):
        self.state = 'loading'
        self._reload.clear()
        self.th = threading.Thread(target=self._loop, daemon=True)
        self.th.start()

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

    def maybe_draft(self, text, asr_backlog=0.0):
        """尾巴草稿：队列空闲、内容有变化、距上次 >= DRAFT_MIN_GAP 才提交。

        C-100③：默认【开启】，间隔 1.5s + ASR 有积压时暂停（定稿翻译不受影响）。
        实测草稿是 GUI 下 RTF 上涨的唯一主因：每次草稿都近一整句的翻译算力，
        0.8s 间隔下翻译线程被占满，经 GIL 与 ASR 会话线程争抢（RTF +0.274）。
        1.5s + 积压暂停压到 +0.144（积压 +0.25s），是唯一既保住实时预览、
        又不破 0.15 阈值的配置；全关是 +0.042 但预览体验明显变差，故仅作
        LIVECAP_NO_DRAFT=1 的压测/极限余量开关。
        """
        if not self.active or self.state != 'ready':
            return
        if not self.DRAFT_ON:
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
            r = tr.translate(job.text, svc.target, ctx=ctx)
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
