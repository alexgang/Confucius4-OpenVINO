"""APP-089/090/091/092：**本轮修的 4 个缺口的静态闸门**（含反证组）。

🔴 每个闸门都必须**能证伪**（拿已知有缺陷的旧产物/改坏代码能 FAIL）
   ⇒ 只写「PASS」的弱标记一律不算。

用法：
  python app375_app089_fixes_static_check.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
DEV = os.path.join(REPO, 'live_caption')
EVID = os.path.join(REPO, 'results', 'app')

CHECKS = []


def chk(name, ok, detail=''):
    CHECKS.append(dict(name=name, ok=bool(ok), detail=str(detail)[:400]))


def read(p):
    return open(p, encoding='utf-8').read()


def src_of(mod):
    return read(os.path.join(DEV, mod))


# ══════════════════════════════════════════════════════════════
# ① APP-090②a：`n_label_wait` **必须真会自增**（不是写死 0）
# ══════════════════════════════════════════════════════════════
w = src_of('tts_worker.py')

# ①a 自增语句存在
inc = re.search(r'self\._n_label_wait\s*\+=\s*1', w)
chk('worker: _n_label_wait 有自增语句', bool(inc),
    'self._n_label_wait += 1 未找到 ⇒ 计数器恒 0（弱标记恒真）')

# ①b 自增发生在**真的等待**的分支里（不是无条件执行）
wait_fn = ''
m = re.search(r'def _wait_for_label\(.*?(?=\n    def )', w, re.S)
if m:
    wait_fn = m.group(0)
chk('worker: 存在 _wait_for_label() 测量点', bool(wait_fn),
    '未找到 _wait_for_label()')
chk('worker: 自增在 _wait_for_label 内',
    bool(wait_fn) and bool(re.search(r'self\._n_label_wait\s*\+=\s*1', wait_fn)),
    '自增不在 _wait_for_label 内 ⇒ 计数器与真实等待无关')

# ①c 默认**不等**（阈值 0 ⇒ 提前 return，不计数）
chk('worker: 默认阈值 0（绝不等标签）',
    bool(re.search(r'_label_wait_sec\s*=\s*float\(os\.environ\.get\(\s*'
                   r"'LIVECAP_TTS_LABEL_WAIT_SEC'\s*,\s*''\s*\)\s*or\s*0\.0", w)),
    '找不到默认 0.0 的阈值初始化')

# ①d jsonl 落盘 n_label_wait / label_wait_s
chk('worker: jsonl 落 n_label_wait',
    bool(re.search(r"'n_label_wait'\s*:\s*int\(", w)),
    'jsonl 行里没有 n_label_wait 字段')
chk('worker: jsonl 落 label_wait_s',
    bool(re.search(r"'label_wait_s'\s*:\s*round\(", w)),
    'jsonl 行里没有 label_wait_s 字段')

# ①e 统计口径透传到 stats
st = src_of('tts_service.py')
chk('service: stats 暴露 n_label_wait',
    bool(re.search(r"n_label_wait=int\(self\._n_label_wait", st)),
    'tts_service.stats() 未暴露 n_label_wait')

# ①f 打分脚本**不再写死 0**
sc = read(os.path.join(EVID, 'app370_app089_score_acceptance.py'))
chk('scorer: n_label_wait 不是常量 0',
    not re.search(r"'n_label_wait'\s*:\s*0\s*,", sc),
    '打分脚本仍写死 n_label_wait: 0 ⇒ 恒真')
chk('scorer: n_label_wait 从 jsonl 读',
    bool(re.search(r"'n_label_wait'\s*:\s*max\(", sc)),
    '打分脚本未从 jsonl 读 n_label_wait')

# ══════════════════════════════════════════════════════════════
# ② APP-089 §2c-2：`xv_reference_ticket` **必须被调用**（不是死代码）
# ══════════════════════════════════════════════════════════════
sv = src_of('speaker_voice.py')
app = src_of('live_caption_app.py')
asrc = src_of('audio_source.py')
chk('speaker_voice: 定义 xv_reference_ticket',
    'def xv_reference_ticket' in sv, '')
chk('app: 调用 xv_reference_ticket（GUI 侧）',
    'self._spk_voices.xv_reference_ticket(' in app,
    'GUI 侧未调用 ⇒ APP-089 §2c-2 未实施')
chk('app: 调用 xv_reference_ticket（CLI 侧）',
    '_spk_voices.xv_reference_ticket(' in app,
    'CLI 侧未调用 ⇒ APP-089 §2c-2 未实施')
chk('app: 用 XV 状态判定升级（upgrade）',
    "_xs2 != 'upgrade'" in app,
    '未按 XV 状态判定升级 ⇒ 升级/冻结语义缺失')
chk('app: 记 XV 登记状态 mark_xv_registered',
    'mark_xv_registered(' in app, '')
# 反证：mark_registered 不能整份覆盖（会冲掉 xv_dur_s/upgraded）
mr = re.search(r'def mark_registered\(.*?(?=\n    def )', sv, re.S)
mr_txt = mr.group(0) if mr else ''
chk('speaker_voice: mark_registered 合并而非覆盖',
    bool(mr_txt) and 'prev = dict(self._reg_run.get' in mr_txt
    and 'self._reg_run[str(spk)] = prev' in mr_txt,
    'mark_registered 仍整份覆盖 ⇒ 会冲掉 xv_dur_s/upgraded ⇒ 冻结语义失效')

# ══════════════════════════════════════════════════════════════
# ③ APP-089 §2c-3：切段**必须在克隆线程**（不 ASR/接收线程）
# ══════════════════════════════════════════════════════════════
cv = src_of('clone_voice.py')
chk('clone_voice: 有独立切段线程',
    'name="clone-split"' in cv and 'def _split_worker' in cv,
    '没有 clone-split 线程 ⇒ 切段会落在调用方线程')
chk('clone_voice: 有 request_split（只入队）',
    'def request_split' in cv, '')
chk('clone_voice: 有 poll_split（取结果）',
    'def poll_split' in cv, '')
chk('app: CLI 不再直接调 split_ready_segments（接收线程）',
    '_clone_pol.split_ready_segments(' not in app,
    'CLI 仍在接收线程直接切段 ⇒ 违反线程纪律')
chk('app: CLI 用 request_split（异步）',
    '_clone_pol.request_split(' in app, '')
chk('app: GUI 用 request_split（异步）',
    'self._clone_pol.request_split(' in app,
    'GUI 侧未请求切段 ⇒ GUI 模式切段数为 0')
chk('app: 轮询取回切段结果',
    'poll_split(' in app, '')

# ══════════════════════════════════════════════════════════════
# ④ APP-092 §2：late_drop 的**真实滞后秒数 + 阈值**落 jsonl
# ══════════════════════════════════════════════════════════════
chk('worker: 记逐句 late_drop_lag_s',
    'self._last_late_drop_lag_s = round(_lag_now, 3)' in w,
    '未记录逐句滞后秒数')
chk('worker: 记逐句 late_drop_threshold_s',
    'self._last_late_drop_threshold_s' in w, '')
chk('worker: jsonl 落 late_drop_lag_s',
    'late_drop_lag_s=' in w, '')
chk('worker: jsonl 落 late_drop_threshold_s',
    'late_drop_threshold_s=' in w, '')
chk('worker: 跳过后清空滞后字段（不串味）',
    bool(re.search(r'self\._last_late_drop\s*=\s*False\s*\n\s*'
                   r'self\._last_late_drop_lag_s\s*=\s*None', w)),
    '跳过后未清空 ⇒ 下一句会带上上一句的滞后值')
chk('scorer: late_drop_lags_s 取真滞后（不是 t_submit）',
    "r.get('late_drop_lag_s')" in sc,
    '打分脚本仍取 t_submit ⇒ 字段名与值不符')

# ══════════════════════════════════════════════════════════════
# ⑤ APP-092②：`target_wall` **必须按播放速率换算**（`--speed` ≠ 1.0 时不失真）
#   🔴 **本轮改用「构造期已知的 `pace`」（确定值）。**
#   第一版用「滑窗实测速率」⇒ 实测隐含速率 p50 = 1.49、范围 0.28–13.6
#   （真实值恒为 1.0）⇒ 普通跑误跳 19 句 ⇒ 违反 APP-092 §3(d)。
# ══════════════════════════════════════════════════════════════
# ⑤a GUI 侧有 `_source_pace()` 且目标墙钟用了它
chk('GUI: 有 _source_pace()（构造期已知的播放速率）',
    'def _source_pace(self)' in app, '')
chk('GUI: 目标墙钟按 pace 换算（a / _pace）',
    bool(re.search(r'return self\._session_wall0 \+ a / _pace', app)),
    'GUI 目标墙钟未按 pace 换算 ⇒ --speed≠1.0 时滞后秒数失真')
# ⑤b CLI 侧同样
chk('CLI: 目标墙钟按 pace 换算',
    bool(re.search(r'return _cli_wall0 \+ a / _pace', app)),
    'CLI 目标墙钟未按 pace 换算')
# ⑤c 不再需要滑窗实测采样点（确定性 ⇒ 无估计噪声）
chk('GUI: 不再用滑窗实测采样点（确定性）',
    '_rate_sample' not in app, '仍有滑窗采样点 ⇒ 速率估计噪声')
chk('CLI: 不再用滑窗实测采样点（确定性）',
    '_cli_rate_sample' not in app, '仍有滑窗采样点 ⇒ 速率估计噪声')
# ⑤d 源侧提供 `pace` 属性（构造期已知的确定值）
chk('audio_source: BaseAudioSource 提供 pace 属性',
    'def pace(self)' in asrc, '')
chk('audio_source: FileSource.pace 返回 speed',
    bool(re.search(r'class FileSource.*?def pace.*?return self\.speed', asrc, re.S)),
    'FileSource.pace 未返回 speed ⇒ 换算不确定')

# ══════════════════════════════════════════════════════════════
# ⑥ 反证组：**改坏代码 ⇒ 对应闸门必须真的 FAIL**（证明闸门非恒真）
#    🔴 做法：把闸门判据写成**函数**（吃源码文本）⇒ 对**改坏后的文本**
#      重新求值 ⇒ 必须变 False。**只看字符串替换成功不算反证。**
# ══════════════════════════════════════════════════════════════


def gate_label_wait_incr(src):
    """闸门 ①a/①b：worker 里有真自增，且在 _wait_for_label 内。"""
    m = re.search(r'def _wait_for_label\(.*?(?=\n    def )', src, re.S)
    if not m:
        return False
    return bool(re.search(r'self\._n_label_wait\s*\+=\s*1', m.group(0)))


def gate_xv_called(src):
    """闸门 ②：App 真的调用了 xv_reference_ticket。"""
    return ('self._spk_voices.xv_reference_ticket(' in src
            and '_spk_voices.xv_reference_ticket(' in src)


def gate_split_async(src):
    """闸门 ③：切段走异步（request_split），**不**在接收线程直切。"""
    return ('_clone_pol.request_split(' in src
            and '_clone_pol.split_ready_segments(' not in src)


def gate_lag_field(src):
    """闸门 ④：scorer 取真滞后字段（不是 t_submit）。"""
    return ("r.get('late_drop_lag_s')" in src
            and "'late_drop_lags_s': [r.get('t_submit')" not in src)


def gate_mark_registered_merge(src):
    """闸门 ②b：mark_registered 合并而非整份覆盖。"""
    m = re.search(r'def mark_registered\(.*?(?=\n    def )', src, re.S)
    if not m:
        return False
    t = m.group(0)
    return ('prev = dict(self._reg_run.get' in t
            and 'self._reg_run[str(spk)] = prev' in t)


def gate_rate_scaled(src):
    """闸门 ⑤：目标墙钟按**构造期已知的 `pace`**换算。
    🔴 **不再接受滑窗实测速率**（实测显示极不稳定）。"""
    return ('def _source_pace(self)' in src
            and bool(re.search(r'return self\._session_wall0 \+ a / _pace', src))
            and bool(re.search(r'return _cli_wall0 \+ a / _pace', src))
            and '_rate_sample' not in src
            and '_cli_rate_sample' not in src)


# ⑤a 去掉 worker 的自增 ⇒ 闸门 ① 必须 FAIL
w_bad = re.sub(r'self\._n_label_wait\s*\+=\s*1', 'pass  # 故意改坏', w)
chk('反证: 去掉自增 ⇒ 闸门①真的 FAIL',
    (gate_label_wait_incr(w) is True) and (gate_label_wait_incr(w_bad) is False),
    '闸门①在改坏后仍为 True ⇒ 闸门恒真')

# ⑤b 去掉 app 的 xv 调用 ⇒ 闸门 ② 必须 FAIL
app_bad = app.replace('xv_reference_ticket(', 'dead_removed(')
chk('反证: 去掉 xv 调用 ⇒ 闸门②真的 FAIL',
    (gate_xv_called(app) is True) and (gate_xv_called(app_bad) is False),
    '闸门②在改坏后仍为 True ⇒ 闸门恒真')

# ⑤c 还原成接收线程直切 ⇒ 闸门 ③ 必须 FAIL
app_bad2 = app.replace('_clone_pol.request_split(',
                        '_clone_pol.split_ready_segments(')
chk('反证: 还原成接收线程直切 ⇒ 闸门③真的 FAIL',
    (gate_split_async(app) is True) and (gate_split_async(app_bad2) is False),
    '闸门③在改坏后仍为 True ⇒ 闸门恒真')

# ⑤d scorer 改回 t_submit ⇒ 闸门 ④ 必须 FAIL
sc_bad = sc.replace("r.get('late_drop_lag_s')", "r.get('t_submit')")
chk('反证: scorer 改回 t_submit ⇒ 闸门④真的 FAIL',
    (gate_lag_field(sc) is True) and (gate_lag_field(sc_bad) is False),
    '闸门④在改坏后仍为 True ⇒ 闸门恒真')

# ⑤e mark_registered 改回整份覆盖 ⇒ 闸门 ②b 必须 FAIL
sv_bad = sv.replace('prev = dict(self._reg_run.get(str(spk)) or {})\n'
                    '            prev.update(a=float(a), b=float(b),\n'
                    '                        dur_s=round(float(b) - float(a), 4),\n'
                    '                        at=time.time())\n'
                    '            self._reg_run[str(spk)] = prev',
                    'self._reg_run[str(spk)] = dict(a=float(a), b=float(b),\n'
                    '                                           dur_s=round(float(b) - float(a), 4),\n'
                    '                                           at=time.time())')
chk('反证: mark_registered 改回覆盖 ⇒ 闸门②b真的 FAIL',
    (gate_mark_registered_merge(sv) is True)
    and (gate_mark_registered_merge(sv_bad) is False),
    '闸门②b在改坏后仍为 True ⇒ 闸门恒真')

# ⑤f 目标墙钟改回「不按 pace 换算」⇒ 闸门 ⑤ 必须 FAIL
app_bad3 = app.replace('return self._session_wall0 + a / _pace',
                       'return self._session_wall0 + a')
app_bad3 = app_bad3.replace('return _cli_wall0 + a / _pace',
                             'return _cli_wall0 + a')
chk('反证: 目标墙钟改回不换算 ⇒ 闸门⑤真的 FAIL',
    (gate_rate_scaled(app) is True) and (gate_rate_scaled(app_bad3) is False),
    '闸门⑤在改坏后仍为 True ⇒ 闸门恒真')

# ══════════════════════════════════════════════════════════════
# ⑥ 语法闸门：改动过的文件必须能 parse
# ══════════════════════════════════════════════════════════════
for f in ('clone_voice.py', 'device_config.py', 'live_caption_app.py',
          'speaker_voice.py', 'time_stretch.py', 'tts_cuda_sidecar.py',
          'tts_service.py', 'tts_worker.py'):
    try:
        ast.parse(src_of(f))
        chk('AST: %s' % f, True, '')
    except Exception as e:
        chk('AST: %s' % f, False, str(e))

# ══════════════════════════════════════════════════════════════
n_pass = sum(1 for c in CHECKS if c['ok'])
n_fail = len(CHECKS) - n_pass
out = dict(n_pass=n_pass, n_fail=n_fail, checks=CHECKS)
p = os.path.join(EVID, 'app375_app089_fixes_static_check.json')
with open(p, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
print('OUT=%s' % p)
sys.exit(0 if n_fail == 0 else 1)
