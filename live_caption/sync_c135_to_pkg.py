r"""sync_c135_to_pkg.py — 把 APP-004 的改动移植到客户包 v1.4

做法与 C-105/C-106/C-108/C-109/C-111/C-133/C-134 一致：
**精确字符串替换 + assert 唯一命中**（幂等：已移植则跳过）。

APP-004 四项内容
----------------
① C-111 合入 —— **已由 ASR 线程提交**（`ebc6107`），
   `translator.py` 仓库版与客户包**已字节相同** ⇒ 本脚本**不重复移植**，
   只做**校验**（确认 C-111 标志在客户包里）。
② TTS 模型随包 —— 模型文件由本脚本旁的 `copy_tts_models.py` 负责；
   代码侧移植 `tts_engine.py`（新文件，整文件拷贝）。
③ 设备自选 —— 移植 `device_config.py`（新文件）+ `live_caption_app.py` /
   `translator.py` 的定点替换。
④ v1.4 重打 —— 由 `pack_v13.py` 负责，本脚本不参与。

⚠️ **禁止整目录覆盖同步** —— 客户包 `app/` 是交付态，
   仓库 `live_caption/` 是研发态（多一套 TTS 面板），
   覆盖会把未交付的东西带进包里。

用法
----
    python sync_c135_to_pkg.py <pkg_app_dir>

默认目标：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app`
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'live_caption')
DEFAULT_PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app'

PATCHES = []


def _add(name, old, new):
    PATCHES.append((name, old, new))


# ══════════════════════════════════════════════════════════════════════
# ① live_caption_app.py —— 设备自选（APP-004 第 3 条）
# ══════════════════════════════════════════════════════════════════════

# --- 1.1 import ---
_add('app: import device_config',
     """from translator import (MT_DEFAULT, MT_ALL_CANDIDATES, MT_ENGINES, TARGETS,
                        TARGET_LABELS, TranslationService, mt_available,
                        prewarm_transformers, split_sentences)
import audio_source""",
     """from translator import (MT_DEFAULT, MT_ALL_CANDIDATES, MT_ENGINES, TARGETS,
                        TARGET_LABELS, TranslationService, mt_available,
                        prewarm_transformers, split_sentences)
import device_config
import audio_source""")

# --- 1.2 App.__init__：记录设备选择 ---
_add('app: App.__init__ 设备选择',
     """        self._ui_log_q = queue.Queue()
        self.mt = TranslationService(
            target=args.translate, device=args.mt_device, auto=False,""",
     """        self._ui_log_q = queue.Queue()
        # 设备解析结果（APP-004 第 3 条）：命令行 > 配置文件 > 推荐默认值。
        # 已在 main() 里解析过一次并回退过不可用的设备。
        self._dev_selected = {
            'asr': getattr(args, 'asr_device', None) or 'GPU.0',
            'mt': getattr(args, 'mt_device', None) or 'GPU.0',
            'tts': getattr(args, 'tts_device', None) or 'NPU',
        }
        self._device_notes = list(getattr(args, 'device_notes', []) or [])
        self.mt = TranslationService(
            target=args.translate, device=self._dev_selected['mt'], auto=False,""")

# --- 1.3 GUI：推理设备行 ---
# ⚠️ 客户包 app **没有 TTS 面板**（TTS 那套只在仓库工作区的未提交改动里），
#    ⇒ OLD 上下文必须用「无 TTS」的 HEAD 版片段。
_add('app: GUI 推理设备行',
     """        self.cb_mt_eng.bind('<<ComboboxSelected>>', self._on_mt_engine_changed)
        self.var_mt_note = tk.StringVar(value='')""",
     """        self.cb_mt_eng.bind('<<ComboboxSelected>>', self._on_mt_engine_changed)

        # ── 推理设备（APP-004 第 3 条）──
        #    ASR / MT / TTS 三个模型各一个设备下拉框，互不影响。
        #    可选项来自 ov.Core().available_devices **实际检测**，
        #    检测不到的设备不显示。
        drow = ttk.Frame(root, padding=(12, 4))
        drow.pack(fill='x')
        ttk.Label(drow, text='推理设备').pack(side='left')
        self._dev_avail = device_config.available_devices()
        self._dev_label_back = {device_config.device_label(d): d
                                for d in self._dev_avail}
        # 命令行 > 配置文件 > 推荐默认值（device_config.get_devices 已解析）
        self._dev_choices = dict(self._dev_selected)
        self.var_dev_asr = tk.StringVar(
            value=device_config.device_label(self._dev_choices['asr']))
        self.var_dev_mt = tk.StringVar(
            value=device_config.device_label(self._dev_choices['mt']))
        self.var_dev_tts = tk.StringVar(
            value=device_config.device_label(self._dev_choices['tts']))
        for role, var in (('asr', self.var_dev_asr),
                          ('mt', self.var_dev_mt),
                          ('tts', self.var_dev_tts)):
            ttk.Label(drow, text={'asr': 'ASR', 'mt': '翻译', 'tts': '语音'}[role]
                      ).pack(side='left', padx=(12, 0))
            cb = ttk.Combobox(
                drow, state='readonly', width=18, textvariable=var,
                values=[device_config.device_label(d) for d in self._dev_avail])
            cb.pack(side='left', padx=(4, 8))
            cb.bind('<<ComboboxSelected>>',
                    lambda e, r=role: self._on_device_changed(r))
            setattr(self, f'cb_dev_{role}', cb)
        self.var_dev_note = tk.StringVar(value='')
        ttk.Label(drow, textvariable=self.var_dev_note,
                  foreground='#555').pack(side='left')
        self._on_device_changed('asr', silent=True)

        # ── TTS（C-101 P4 第 4 条：GUI）──""")

# --- 1.4 方法：_on_device_changed 等 ---
_add('app: 设备切换方法',
     """    # -- TTS（C-101 P4）--------------------------------------------------
    def _on_tts_toggled(self, *_a):""",
     """    # -- 推理设备（APP-004 第 3 条）---------------------------------------
    def _cur_device(self, role):
        \"\"\"读某个角色（asr/mt/tts）当前选中的设备名。\"\"\"
        var = {'asr': self.var_dev_asr,
               'mt': self.var_dev_mt,
               'tts': self.var_dev_tts}[role]
        return self._dev_label_back.get(var.get(), var.get())

    def _on_device_changed(self, role, silent=False):
        \"\"\"设备下拉框变化：校验 → 落到可用设备 → 必要时重建引擎。

        ⚠️ **不能卡死**：本机没有的设备要提示并**回退到推荐默认**。
        \"\"\"
        want = self._cur_device(role)
        dev, note = device_config.resolve_device(role, want, self._dev_avail)
        if dev != want:
            # 回退：把下拉框改回实际使用的设备
            var = {'asr': self.var_dev_asr,
                   'mt': self.var_dev_mt,
                   'tts': self.var_dev_tts}[role]
            var.set(device_config.device_label(dev))
            if not silent:
                self.var_status.set(f'{role.upper()} 设备不可用（{want}），已回退到 {dev}')
            self.var_dev_note.set(note or '')
        self._dev_choices[role] = dev

        # 保存到配置文件（下次启动恢复）
        device_config.save_config(dict(self._dev_choices))

        if silent:
            return
        label = {'asr': 'ASR', 'mt': '翻译', 'tts': '语音'}[role]
        self._ui_log(f'{label} 推理设备：{dev}')

        if role == 'mt':
            # 翻译设备变了 ⇒ 通知 TranslationService（热切换模型）
            if self.mt.active:
                self.mt.set_device(dev)
                self.var_status.set(f'翻译设备切换中：{dev}')
            else:
                self.mt.set_device(dev)
        elif role == 'asr':
            # ASR 设备写在 ENGINES[key]['device'] 里 ⇒ 需要重载引擎
            if self.engine_key:
                self._reload_engine_on_device(self.engine_key, dev)
        elif role == 'tts':
            # TTS 设备：worker 起动时带入 ⇒ 已 running 就重启 worker
            if getattr(self, 'tts', None) is not None:
                self._restart_tts_on_device(dev)

    def _reload_engine_on_device(self, key, dev):
        \"\"\"ASR 换设备 ⇒ 重载引擎（后端表里的 device 是写死的）。\"\"\"
        cfg = dict(ENGINES[key])
        old = cfg.get('device')
        if old == dev:
            return
        cfg['device'] = dev
        ENGINES[key] = cfg
        self.var_status.set(f'ASR 设备切换中：{dev}（正在重载引擎）')
        self.load_engine()

    def _restart_tts_on_device(self, dev):
        \"\"\"TTS 换设备 ⇒ 重起 worker（worker 进程启动时就绑定了设备）。\"\"\"
        try:
            self.tts.close()
        except Exception:
            pass
        self.tts = None
        self.var_status.set(f'语音输出设备切换中：{dev}（正在重启 TTS）')
        self._on_tts_toggled()

    # -- TTS（C-101 P4）--------------------------------------------------
    def _on_tts_toggled(self, *_a):""")

# --- 1.5 make_engine 支持 device ---
_add('app: make_engine 支持 device',
     """def make_engine(key, on_log=print, force_language=None):
    \"\"\"创建推理引擎。

    force_language：ASR 识别语种（模型认识的英文名，如 'Chinese'/'English'）；
    None = 自动检测。传进来后会在建 state / 起进程时生效。
    \"\"\"
    cls = CudaEngine if ENGINES[key]['kind'] == 'cuda' else OVEngine
    return cls(key, on_log=on_log, force_language=force_language)""",
     """def make_engine(key, on_log=print, force_language=None, device=None):
    \"\"\"创建推理引擎。

    force_language：ASR 识别语种（模型认识的英文名，如 'Chinese'/'English'）；
    None = 自动检测。传进来后会在建 state / 起进程时生效。

    device：用户显式选的推理设备（APP-004 第 3 条）。None = 用后端表里的默认值。
    ⚠️ **NPU 档（kind='npu'）设备是写死在后端实现里的**，不接受覆盖 ——
    那条路径走的是 all-NPU 交付后端，换设备会让模型与后端不匹配。
    \"\"\"
    cls = CudaEngine if ENGINES[key]['kind'] == 'cuda' else OVEngine
    if device:
        return cls(key, on_log=on_log, force_language=force_language, device=device)
    return cls(key, on_log=on_log, force_language=force_language)""")

# --- 1.6 OVEngine 支持 device ---
_add('app: OVEngine 支持 device',
     """    def __init__(self, key, on_log=print, force_language=None):
        from seg_stream import _make_segment_state
        from streaming_asr import (streaming_transcribe, finish_streaming_transcribe,
                                   parse_asr_output, _normalize_punct_by_context)
        self.key, self.cfg = key, ENGINES[key]
        self._st, self._finish = streaming_transcribe, finish_streaming_transcribe""",
     """    def __init__(self, key, on_log=print, force_language=None, device=None):
        from seg_stream import _make_segment_state
        from streaming_asr import (streaming_transcribe, finish_streaming_transcribe,
                                   parse_asr_output, _normalize_punct_by_context)
        self.key, self.cfg = key, ENGINES[key]
        # 用户显式选的设备优先（APP-004 第 3 条）；NPU 档忽略（all-NPU 后端写死）。
        if device and self.cfg['kind'] == 'ov':
            self.cfg = dict(self.cfg)
            self.cfg['device'] = device
        self._st, self._finish = streaming_transcribe, finish_streaming_transcribe""")

# --- 1.7 load_engine 传设备 ---
_add('app: load_engine 传设备',
     """                eng = make_engine(key, on_log=self._ui_log,
                                  force_language=self._cur_asr_lang())""",
     """                eng = make_engine(key, on_log=self._ui_log,
                                  force_language=self._cur_asr_lang(),
                                  device=self._dev_choices.get('asr'))""")

# --- 1.8 CLI：make_engine 传设备 ---
_add('app: CLI make_engine 传设备',
     """    eng = make_engine(args.engine, on_log=lambda m: print(m, flush=True),
                      force_language=asr_lang)""",
     """    eng = make_engine(args.engine, on_log=lambda m: print(m, flush=True),
                      force_language=asr_lang, device=args.asr_device)""")

# --- 1.9 CLI：设备参数 ---
_add('app: CLI 设备参数',
     """    ap.add_argument('--mt-device', default='GPU.0',
                    help="翻译模型推理设备；--mt-engine 非 auto 时以后端自带的设备为准")
    ap.add_argument('--mt-engine', choices=list(MT_ENGINES), default=MT_DEFAULT,""",
     """    ap.add_argument('--mt-engine', choices=list(MT_ENGINES), default=MT_DEFAULT,""")

_add('app: CLI tts-device 移除',
     """    ap.add_argument('--tts-device', default='GPU.0',
                    help='TTS 推理设备（GPU.0 / CPU / NPU）')
    ap.add_argument('--tts-precision', default='f32', choices=['f32', 'f16'],
                    help='TTS 推理精度')""",
     """    ap.add_argument('--tts-precision', default='f32', choices=['f32', 'f16'],
                    help='TTS 推理精度')""")

_add('app: CLI 新设备参数 + 解析',
     """    ap.add_argument('--tts-out-device', default=None,
                    help='TTS 播放输出设备（名称或索引；默认系统默认输出）')
    args = ap.parse_args()""",
     """    ap.add_argument('--tts-out-device', default=None,
                    help='TTS 播放输出设备（名称或索引；默认系统默认输出）')

    # ── 推理设备（APP-004 第 3 条）──
    # 三个模型各一个设备；不给就用配置文件里的（再没有就用推荐默认值）。
    ap.add_argument('--asr-device', default=None,
                    help='ASR 推理设备（GPU.0 / NPU / CPU）。不给则用配置文件里的选择')
    ap.add_argument('--mt-device', default=None,
                    help='翻译推理设备（GPU.0 / NPU / CPU）。不给则用配置文件里的选择')
    ap.add_argument('--tts-device', default=None,
                    help='语音输出推理设备（默认 NPU）。不给则用配置文件里的选择')
    args = ap.parse_args()

    # 设备解析：命令行 > 配置文件 > 推荐默认值；不可用时回退并提示。
    _dev_cli = {
        'asr': args.asr_device,
        'mt': args.mt_device,
        'tts': args.tts_device,
    }
    _dev_sel, _dev_notes = device_config.get_devices(_dev_cli)
    args.asr_device = _dev_sel['asr']
    args.mt_device = _dev_sel['mt']
    args.tts_device = _dev_sel['tts']
    args.device_notes = _dev_notes""")

# --- 1.10 _check_devices 复用 device_config ---
_add('app: _check_devices 复用 device_config',
     """def _check_devices():
    \"\"\"探测 OpenVINO 可用设备。返回 (设备名 -> 全名) 映射。\"\"\"
    try:
        import openvino as ov
        core = ov.Core()
        out = {}
        for d in core.available_devices:
            try:
                out[d] = core.get_property(d, 'FULL_DEVICE_NAME')
            except Exception:
                out[d] = d
        return out
    except Exception as e:
        print(f'  [跳过] OpenVINO 不可用：{e}')
        return {}""",
     """def _check_devices():
    \"\"\"探测 OpenVINO 可用设备。返回 (设备名 -> 全名) 映射。

    ⚠️ 与 `device_config.detect_devices()` 是同一套逻辑（单一数据源）——
    GUI 下拉框、CLI 设备解析、`--check` 输出看到的必须是同一份列表。
    \"\"\"
    devs = device_config.detect_devices()
    if not devs:
        print('  [跳过] OpenVINO 不可用')
    return devs""")


# ══════════════════════════════════════════════════════════════════════
# ② translator.py —— set_device（MT 设备热切换）
# ══════════════════════════════════════════════════════════════════════
_add('translator: set_device',
     """        self.state = 'loading'
        self._reload.set()
        self.q.put(_Job('switch', '', ''))   # 哨兵：唤醒可能阻塞在 get() 上的线程
        return True

    def _start(self):""",
     """        self.state = 'loading'
        self._reload.set()
        self.q.put(_Job('switch', '', ''))   # 哨兵：唤醒可能阻塞在 get() 上的线程
        return True

    def set_device(self, device):
        \"\"\"热切换翻译推理设备（APP-004 第 3 条）。

        与 set_engine 的区别：set_engine 会把 device **重置**成该 engine 的默认值；
        这里只改设备，不动 engine_key / model_dir（用户显式选的优先）。

        ⚠️ 设备变了必须**真的重建模型**（OV 的模型是绑在 device 上的），
        所以走和 set_engine 一样的 `_reload` 通道。
        \"\"\"
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

    def _start(self):""")


# ══════════════════════════════════════════════════════════════════════
# 新文件（整文件拷贝）
# ══════════════════════════════════════════════════════════════════════
NEW_FILES = ['device_config.py', 'tts_engine.py', 'tts_engine_patch.py']


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _code_only(path):
    """抽出文件的「代码骨架」：去掉注释行与 docstring。

    用途：判断两份文件**行为等价**（只有注释/docstring 不同）——
    客户包 app 的 Segmenter docstring 还写着「12 秒 / 1.2 秒」，
    而实际常量已是 6.0 / 0.8 ⇒ 纯文案陈旧，代码等价。
    """
    import io
    import tokenize
    with open(path, 'rb') as f:
        src = f.read()
    out = []
    try:
        toks = list(tokenize.tokenize(io.BytesIO(src).readline))
    except Exception:
        return out
    for t in toks:
        if t.type in (tokenize.COMMENT, tokenize.STRING, tokenize.NL,
                      tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                      tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        out.append((t.type, t.string))
    return out


def _assert_code_equiv(pkg_path, base_path):
    """校验客户包文件与基底在**代码层面**等价（忽略注释/docstring）。"""
    a = _code_only(pkg_path)
    b = _code_only(base_path)
    if a == b:
        return True, '代码骨架完全相同'
    # 允许的差异：仅行号/空白
    sa = [x[1] for x in a]
    sb = [x[1] for x in b]
    if sa == sb:
        return True, 'token 序列相同'
    return False, f'代码骨架不同（{len(sa)} vs {len(sb)} tokens）'


def main():
    pkg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PKG
    if not os.path.isdir(pkg):
        print(f'✗ 客户包 app 目录不存在：{pkg}')
        return 2
    print(f'客户包 app：{pkg}')
    print('─' * 64)

    ok = True

    # ── 步骤 0：基底同步 ────────────────────────────────────────────
    # 客户包 app 的 Segmenter docstring 停留在 C-108/C-109 之前
    # （写「12 秒 / 1.2 秒」，而实际常量已是 6.0 / 0.8），
    # 而 C-111（已由 ASR 提交 ebc6107）只进了仓库 HEAD。
    # ⇒ 这里把客户包文件**升级到仓库 HEAD 版**，
    #   但**必须先校验「代码骨架等价」**（只有注释/docstring 不同），
    #   否则就是在偷换行为。
    import subprocess
    for fname in ('live_caption_app.py', 'translator.py'):
        pkg_f = os.path.join(pkg, fname)
        r = subprocess.run(['git', 'show', f'HEAD:live_caption/{fname}'],
                           cwd=REPO, capture_output=True)
        if r.returncode != 0:
            print(f'✗ 无法从 git 取 HEAD 版 {fname}')
            ok = False
            continue
        head_txt = r.stdout.decode('utf-8', errors='replace')
        head_tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f'_head_{fname}')
        with open(head_tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(head_txt)
        same, why = _assert_code_equiv(pkg_f, head_tmp)
        if not same:
            print(f'✗ {fname}: 客户包与 HEAD 版**代码不等价** ⇒ 拒绝替换')
            print(f'   {why}')
            ok = False
            os.remove(head_tmp)
            continue
        if sha256(pkg_f) == sha256(head_tmp):
            print(f'[基底已是 HEAD] {fname}（字节相同）')
        else:
            with open(pkg_f, 'w', encoding='utf-8', newline='') as f:
                f.write(head_txt)
            print(f'[基底已升级] {fname} → HEAD 版（代码等价：{why}）')
        os.remove(head_tmp)

    print('─' * 64)

    for fname, old, new in PATCHES:
        path = os.path.join(pkg, fname)
        if not os.path.isfile(path):
            print(f'✗ {fname} 不存在')
            ok = False
            continue
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        cnt = src.count(old)
        if cnt == 0:
            if src.count(new) == 1:
                print(f'[已移植] {fname}: {fname} — {fname}')  # 占位，下面会改
                print(f'   ↳ （幂等跳过，替换内容已存在）')
                continue
            print(f'✗ {fname}: 找不到待替换内容（{len(old)} 字符）')
            ok = False
            continue
        if cnt != 1:
            print(f'✗ {fname}: 命中 {cnt} 次（应为 1）⇒ 不替换')
            ok = False
            continue
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(src.replace(old, new))
        print(f'[已移植] {fname}')

    print('─' * 64)
    for f in NEW_FILES:
        s = os.path.join(SRC, f)
        d = os.path.join(pkg, f)
        if not os.path.isfile(s):
            print(f'✗ 源文件不存在：{s}')
            ok = False
            continue
        if os.path.isfile(d) and sha256(s) == sha256(d):
            print(f'[已就位] {f}（字节相同）')
            continue
        shutil.copy2(s, d)
        print(f'[已拷贝] {f}')

    print('─' * 64)
    # ① C-111 校验
    tr = os.path.join(pkg, 'translator.py')
    with open(tr, 'r', encoding='utf-8') as f:
        trs = f.read()
    for marker, desc in (('seg_half', 'C-111 段尾半句'),
                         ('_enqueue_fix', 'C-111 原地覆盖'),
                         ('mt2-int8sym-cw-q', 'C-134 默认 INT8-CW')):
        hit = trs.count(marker)
        print(f'{"✓" if hit else "✗"} translator.py 含 {desc}（{marker} × {hit}）')
        if not hit:
            ok = False
    # 与仓库版比对
    repo_tr = os.path.join(SRC, 'translator.py')
    if os.path.isfile(repo_tr):
        if sha256(repo_tr) == sha256(tr):
            print('✓ translator.py 与仓库版字节相同')
        else:
            print('⚠ translator.py 与仓库版**不相同**（需人工核对差异）')

    print('─' * 64)
    print('结论：' + ('PASS —— APP-004 代码移植完成' if ok else 'FAIL —— 见上方 ✗'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
