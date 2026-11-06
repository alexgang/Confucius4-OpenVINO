r"""v23_preset_only.py — APP-080 用户决定：v2.3 只交付预设音色。

用户原话（APP-080）："ok, deliver only preset voices and take cloning out
of v2.3 for now"。APP-071/075/079 的克隆修复转入后续版本，
"代码保留在 dev 分支，不进 v2.3 包"，且 v2.3 发布前不再为克隆占用设备。

## 实现口径（🔴 需 reviewer 复核）
克隆实现代码在 **dev 里一字不改**（供后续版本继续用）。本模块是**构建期
定点补丁规范**：建 v2.3 包时，对包内 `app/` 副本的 3 个文件做唯一命中断言的
字符串替换，再用 `ast.parse` + 逐字节复核确认。dev 源文件不因此改变。

🔴 本模块**不改任何已发布目录、不生成 zip、不占设备、不加载模型**。
🔴 打进 v2.3 包时必须**同时带上本文件**（`app/v23_preset_only.py`），
   否则包内 `from v23_preset_only import ...` 会 ImportError。

## 为什么用构建期补丁而不是直接删 dev 代码
1. APP-080 明文「代码保留在 dev 分支，不进 v2.3 包」——克隆实现留在 dev，
   v2.3 包内的入口被物理移除/闸门关闭即可；后续版本只要不打这套补丁就能复用。
2. APP-055 禁止原地修改用户正在测试的安装目录；补丁只对**新包目录的副本**生效。
3. 既有的 app204/app227 等历史判据仍按 dev 原文跑，不被本轮改动扰动。

## 行尾纪律（§九）
`live_caption_app.py` 是 LF，`tts_service.py` / `tts_worker.py` 是 CRLF。
`apply_patches()` 读入时统一归一化为 LF 做唯一命中匹配，写回时还原原行尾。
"""
from __future__ import annotations

import ast

PRESET_ONLY = True
PRESET_VOICE = 'A'


def normalize_voice(value, on_log=None):
    """旧配置/命令行残留克隆音色 ⇒ 回落预设 A 并写日志，**绝不报错**。

    APP-080 第 2 条：「默认配置和旧的 device_config/用户设置里如果残留 clone，
    启动时回落到 A 并写日志，不能报错」。任何异常都吞掉并返回 'A'。
    """
    try:
        raw = None if value is None else str(value)
        if raw is None or raw.strip() in ('', PRESET_VOICE, PRESET_VOICE.lower()):
            return PRESET_VOICE
        if on_log is not None:
            on_log('[v23] APP-080：音色残留值 %r 不在 v2.3 交付范围 ⇒ 回落预设 A' % (raw,))
    except Exception:
        pass
    return PRESET_VOICE


# ── 构建期定点补丁（old ⇒ new，old 必须在目标文件里恰好命中 1 次）────────
# 每条都写明对应 APP-080 的分项；`verify_source()` 会在补丁后做静态判据。
_APP_PATCHES = [
    dict(id='P00-import', why='APP-080 ② 运行期闸门与回落函数来自本模块',
         old="import clone_collector\n",
         new="import clone_collector\n"
             "from v23_preset_only import normalize_voice, PRESET_ONLY  # APP-080\n"),
    dict(id='P01-voices', why='APP-080 ① 去掉「跟随说话人（克隆）」下拉选项',
         old="        self.tts_voices = ['A', 'follow_speaker']\n",
         new="        self.tts_voices = ['A']  # APP-080：v2.3 只交付预设音色\n"),
    dict(id='P02-label', why='APP-080 ① 下拉标签里不再出现克隆字样',
         old="        self._tts_voice_label = {'A': '预设 A',\n"
             "                                 'follow_speaker': '跟随说话人（克隆·实验）'}\n",
         new="        self._tts_voice_label = {'A': '预设 A'}  # APP-080\n"),
    dict(id='P03-checkbox', why='APP-080 ① 去掉「用于克隆」字样；旁路改标字幕用途',
         old="            g_adv, text='区分说话人（用于克隆）',\n",
         new="            g_adv, text='区分说话人（字幕标注）',\n"),
    dict(id='P04-hint', why='APP-080 ① 提示语改成字幕标注 + 音色固定',
         old="        ttk.Label(g_adv, text='检测谁在说话，换人时重新克隆音色；'\n"
             "                  '只在音色=跟随说话人时生效',\n",
         new="        ttk.Label(g_adv, text='在字幕上显示 S1/S2 标签；'\n"
             "                  '音色固定为预设 A，不随说话人变化',\n"),
    dict(id='P05-startup', why='APP-080 ② 旧参数残留 clone ⇒ 回落 A 并写日志，不报错',
         old="        try:\n"
             "            _voice0 = str(getattr(args, 'tts_voice', 'A') or 'A')\n"
             "            if _voice0 == 'follow_speaker':\n"
             "                self._enable_speaker_for_clone('GUI 启动参数 --tts-voice follow_speaker')\n"
             "        except Exception:\n"
             "            pass\n",
         new="        try:\n"
             "            # APP-080：残留克隆音色一律回落预设 A（写日志、不报错）。\n"
             "            _voice0 = normalize_voice(getattr(args, 'tts_voice', 'A'),\n"
             "                                      on_log=self._ui_log)\n"
             "            args.tts_voice = _voice0\n"
             "            self.var_tts_voice.set(self._tts_voice_label[_voice0])\n"
             "        except Exception:\n"
             "            pass\n"),
    dict(id='P06-tts-start', why='APP-080 ② 克隆采集器永不启用',
         old="            self._clone_enabled = (voice == 'follow_speaker')\n",
         new="            self._clone_enabled = False  # APP-080：v2.3 固定预设 A\n"),
    dict(id='P07-statusbar', why='APP-080 ① 状态栏不显示克隆音色',
         old="        svc = getattr(self, 'tts', None)\n"
             "        if svc is None:\n"
             "            return '预设 A'\n",
         new="        if PRESET_ONLY:\n"
             "            return '预设 A'  # APP-080\n"
             "        svc = getattr(self, 'tts', None)\n"
             "        if svc is None:\n"
             "            return '预设 A'\n"),
    dict(id='P08-onchange', why='APP-080 ① 音色变化分支只剩预设 A',
         old="        if voice == 'follow_speaker':\n"
             "            self._enable_speaker_for_clone('GUI 选择「跟随说话人」')\n"
             "            self.var_tts_note.set(\n"
             "                '「跟随说话人（克隆）」已启用：'\n"
             "                '换人时取样（首段 ≥1.5 s，3 s 定稿），老说话人复用。')\n"
             "        else:\n"
             "            self.var_tts_note.set('已切换到「预设 A」')\n",
         new="        # APP-080：v2.3 只有预设 A ⇒ 不再有克隆分支。\n"
             "        self.var_tts_note.set('已切换到「预设 A」')\n"),
    dict(id='P09-cli', why='APP-080 ② CLI 旧参数回落 A；choices 保留 ⇒ 不报错',
         old="    _want_clone = (str(getattr(args, 'tts_voice', 'A') or 'A')\n"
             "                   == 'follow_speaker')\n",
         new="    # APP-080：CLI 残留 follow_speaker ⇒ 回落 A 并写日志（不报错）。\n"
             "    _want_clone = False\n"
             "    try:\n"
             "        from v23_preset_only import normalize_voice as _v23_norm\n"
             "        args.tts_voice = _v23_norm(getattr(args, 'tts_voice', 'A'),\n"
             "                                   on_log=lambda m: print(m, flush=True))\n"
             "    except Exception:\n"
             "        args.tts_voice = 'A'\n"),
    dict(id='P10-help', why='APP-080 ① 帮助文本不再宣传克隆',
         old="    ap.add_argument('--tts-voice', default='A', choices=['A', 'follow_speaker'],\n"
             "                    help='音色：预设 A（客户包只随包分发音色 A；'\n"
             "                         '音色 B / 克隆说话人素材按 BRIEF 不进包）；'\n"
             "                         'follow_speaker = 跟随说话人（克隆·实验）—— '\n"
             "                         '🔴🔴 APP-061④：克隆改为「换人时取样」'\n"
             "                         '（首段 ≥1.5 s，3 s 定稿），老说话人复用；'\n"
             "                         '**定时重采集已停用**（旧的「每 30 s 重算」不再执行）；'\n"
             "                         '🔴🔴 APP-061⑤：需配合说话人识别（旁路）'\n"
             "                         '⇒ 旁路关闭时明确提示使用预设 A')\n",
         new="    ap.add_argument('--tts-voice', default='A', choices=['A', 'follow_speaker'],\n"
             "                    help='音色：v2.3 只交付预设 A；'\n"
             "                          'follow_speaker 仅为兼容旧配置保留，'\n"
             "                          '启动即回落 A 并写日志（APP-080）')\n"),
]

_SVC_IMPORT = (
    "from __future__ import annotations\n",
    "from __future__ import annotations\n"
    "from v23_preset_only import PRESET_ONLY as _V23_PRESET_ONLY  # APP-080\n",
)

_SVC_PATCHES = [
    dict(id='S00-import', why='APP-080 ② 运行期闸门', old=_SVC_IMPORT[0], new=_SVC_IMPORT[1]),
    # 🔴 闸门必须插在 **docstring 之后**：插在 def 行与 docstring 之间会把
    #    docstring 挤成「非首语句」⇒ 函数的 __doc__ 变 None（_app316 ast 实测）。
    #    after_docstring=True ⇒ apply_patches() 用 ast 定位 docstring 结束行再插入。
    dict(id='S01-set_clone_pcm', why='APP-080 ② 克隆 PCM 一律不发给 worker',
         old="    def set_clone_pcm(self, pcm) -> bool:\n",
         func='set_clone_pcm', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return False  # APP-080：v2.3 不执行克隆登记\n"),
    dict(id='S02-register_spk_voice', why='APP-080 ② 按说话人登记嗓音一律不执行',
         old="    def register_spk_voice(self, spk: str, pcm) -> bool:\n",
         func='register_spk_voice', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return False  # APP-080\n"),
]

_WORKER_PATCHES = [
    dict(id='W00-import', why='APP-080 ② 运行期闸门', old=_SVC_IMPORT[0], new=_SVC_IMPORT[1]),
    dict(id='W01-update_clone', why='APP-080 ② speaker_enc 的克隆调用不执行',
         old="    def _update_clone(self, pcm):\n",
         func='_update_clone', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return  # APP-080：不提取克隆 x-vector\n"),
    dict(id='W02-register_spk_voice', why='APP-080 ② 克隆嗓音登记不执行',
         old="    def _register_spk_voice(self, msg):\n",
         func='_register_spk_voice', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return  # APP-080\n"),
    dict(id='W03-apply_spk_voice', why='APP-080 ② 旁路触发的音色切换不执行（固定预设 A）',
         old="    def _apply_spk_voice(self, spk):\n",
         func='_apply_spk_voice', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return  # APP-080：音色固定为预设 A\n"),
]

PATCHES = {
    'live_caption/live_caption_app.py': _APP_PATCHES,
    'live_caption/tts_service.py': _SVC_PATCHES,
    'live_caption/tts_worker.py': _WORKER_PATCHES,
}

# 🔴 APP-080 ③：说话人旁路**仍被字幕标注使用**（`--speaker on` ⇒ 字幕 [S1]/[S2]；
# `caption_render.render_lines(spk_by_seg=...)`；`App._retry_spk_labels()`），
# ⇒ 这 5 个 ASR spk 文件与 5 s 静态 seg IR（APP-068）**随 v2.3 保留**，
#   ASR-050 的 `min_clean_ratio` 默认 0.6 也随旁路保留（APP-076）。
KEEP_SPK_FILES = [
    'asr052_speaker_tracker_api.py',
    'asr052_spk_runtime.py',
    'asr_thread_defaults.py',
    'asr_spk_window.py',
    'asr_runtime_switches.py',
]

# APP-080 ④ + APP-077/078：v2.3 包内**禁止出现**的相对路径正则。
PKG_EXCLUDE_PATTERNS = [
    r'(?i)(^|/)bridge_token\.txt$',                                  # APP-077
    r'(?i)python/Lib/site-packages/babelvox/data/speakers/(cindy|lou|phil|steve)\.(json|npy)$',
    r'(?i)(^|/)voices/.*clone.*\.(wav|npz)$',                        # 克隆音色
    r'(?i)(^|/)v23_clone[^/]*/.*\.(wav|npz)$',                        # 克隆产物目录
    r'(?i)(^|/).*(_clone_test|_test)\.wav$',                           # 测试 wav
]

# APP-080 ⑥ 验收用的黑名单扫描关键词（会议录音 / 开发路径 / torch / cuda）。
BLACKLIST_PATTERNS = [
    r'(?i)C:\\Users\\Trekker-PTL',
    r'(?i)hy_bench',
    r'(?i)(^|/)results/.*_spoken',
    r'(?i)(^|/)torch(/|$)',
    r'(?i)(^|/)cuda(/|_|\.)',
]

# 必须随 v2.3 包分发的本轮新增文件（否则包内 import 会失败）。
PKG_INCLUDE_FILES = ['app/v23_preset_only.py', 'app/assert_pkg_clean.py']


def apply_patches(text, file_key):
    """对**单个源文件**应用补丁；返回 (patched_text, applied_ids)。

    * 唯一命中断言：每个 old 在归一化后的文本里必须恰好出现 1 次，否则抛 AssertionError。
    * 行尾：读入归一化 LF，写回还原原行尾（CRLF 副本不会变成 LF）。
    * 补丁后 `ast.parse` 必须通过。
    * 本函数**不写盘**（纯函数），便于反证组复用同一判据。
    """
    if file_key not in PATCHES:
        raise KeyError('unknown file_key: %r' % (file_key,))
    eol = '\r\n' if '\r\n' in text else '\n'
    norm = text.replace('\r\n', '\n')
    applied = []
    for p in PATCHES[file_key]:
        n = norm.count(p['old'])
        if n != 1:
            raise AssertionError('%s: anchor %s hit %d times (need exactly 1)'
                                 % (file_key, p['id'], n))
        if p.get('after_docstring'):
            # 🔴 闸门插到 docstring **之后**（保住 __doc__）；位置由 ast 从
            #    当前文本实时定位 ⇒ docstring 内容以后改了也不会失配。
            tree = ast.parse(norm, filename=file_key)
            node = next((x for x in ast.walk(tree)
                         if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and x.name == p['func']), None)
            if node is None:
                raise AssertionError('%s: %s function %r not found'
                                     % (file_key, p['id'], p['func']))
            first = node.body[0]
            if not (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                raise AssertionError('%s: %s has no leading docstring'
                                     % (file_key, p['id']))
            lines = norm.splitlines(True)
            off = sum(len(x) for x in lines[:first.end_lineno])
            norm = norm[:off] + p['guard'] + norm[off:]
        else:
            norm = norm.replace(p['old'], p['new'], 1)
        applied.append(p['id'])
    ast.parse(norm, filename=file_key)
    out = norm.replace('\n', eol) if eol == '\r\n' else norm
    return out, applied


def verify_source(text, file_key):
    """APP-080 的静态判据（对**补丁后**的文本）。返回 (ok, reasons)。

    🔴 判据必须查「分支本体特征」而不是恒真标记：
       ① `tts_voices` 里只有 A；② GUI 字符串里没有「克隆」；
       ③ 5 个运行期闸门都在；④ 残留值回落函数被真正调用；
       ⑤ `argparse` 仍接受 follow_speaker（旧配置不报错）。
    """
    reasons = []

    def chk(cond, msg):
        if not cond:
            reasons.append(msg)

    if file_key == 'live_caption/live_caption_app.py':
        chk("self.tts_voices = ['A']" in text, 'P01: 音色下拉仍含克隆选项')
        chk("'follow_speaker': '跟随说话人" not in text, 'P02: 下拉标签仍含克隆')
        chk("text='区分说话人（用于克隆）'" not in text, 'P03: 高级区仍有「用于克隆」字样')
        chk("ttk.Label(g_adv, text='检测谁在说话，换人时重新克隆音色；'" not in text,
            'P04: GUI 提示语仍宣传克隆（只查控件本体，注释里的 reviewer 原文不算）')
        chk('normalize_voice(getattr(args, ' in text, 'P05: 启动回落未调用 normalize_voice')
        chk('self._clone_enabled = False' in text, 'P06: 克隆采集器仍可被启用')
        chk("if PRESET_ONLY:\n            return '预设 A'" in text.replace('\r\n', '\n'),
            'P07: 状态栏仍可能显示克隆音色')
        chk("choices=['A', 'follow_speaker']" in text, 'P10: 旧配置会 argparse 报错')
        chk('from v23_preset_only import normalize_voice' in text, 'P00: 缺少回落函数导入')
    elif file_key == 'live_caption/tts_service.py':
        chk(text.count('if _V23_PRESET_ONLY:') == 2, 'S01/S02: 运行期闸门数 ≠ 2')
        chk('from v23_preset_only import PRESET_ONLY' in text, 'S00: 缺少闸门导入')
    elif file_key == 'live_caption/tts_worker.py':
        chk(text.count('if _V23_PRESET_ONLY:') == 3, 'W01/W02/W03: 运行期闸门数 ≠ 3')
        chk('from v23_preset_only import PRESET_ONLY' in text, 'W00: 缺少闸门导入')
    else:
        chk(False, 'unknown file_key')
    return (not reasons), reasons
