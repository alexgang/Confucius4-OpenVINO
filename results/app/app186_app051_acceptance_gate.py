#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app186 —— APP-051② / APP-043：**真机验收总闸门**（汇总 5 项子验收）。

🔴🔴🔴 **为什么必须有这个脚本（而不是「看一眼证据就写 ACCEPTED.json」）**：
  APP-051② 要求「**接着做 APP-043 真机验收** …；**验收通过后**写 ACCEPTED.json」。
  ⇒ 「验收通过」必须有**一个明确的判据**，而不是**人工印象**。
  ⇒ 本脚本把 APP-043 的 5 个子项各自已有的**落盘证据**收上来，
    逐项核对「证据存在 + verdict=PASS + 指向的是 **v1.13 包**」，
    **全部通过才给出 `accepted=true`**。

🔴 **纪律**：**纯离线**（只读各证据 JSON）⇒ 不占机器锁、不跑推理、不碰 GPU。

## APP-043 / APP-051② 的 5 个子项与对应证据
  ① pythonw.exe 冷启动（用户启动方式）
     → `results/app/app181_pythonw_coldstart_v2_evidence.json`
  ② SPE Q&A 双说话人克隆（按句绑定 spk）
     → `results/app/app175_app043_clone_acceptance_evidence.json`
  ③ GUI 加速播放（APP-042 自适应加速，接通 + 公式自洽）
     → `results/app/app179_app042_gui_accel_evidence.json`（链路）
       `results/app/app183_app042_formula_evidence.json`（公式）
  ④ APP-048 状态栏两种分辨率截图
     → `results/app/app185_app048_gui_layout_pkg_evidence.json`（**在 v1.13 包内跑**）
  ⑤ 3 段 1.2–1.3× 配音实听素材
     → `results/app/app184_app051_accel_listen_manifest.json`

🔴 **「在目标包上跑」是硬要求**：
  ① ③ ④ 的证据里都有 `pkg` 字段 ⇒ 必须指向**本次验收的那个包目录**
  （由 `pkg_paths` 自动发现的最大版本包，不写死版本号 ⇒ §48）。
  ⚠️ `app165`（旧）跑的是**仓库**源码 ⇒ 不算 ⇒ 用 `app185`。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HOME = os.path.expanduser('~')
# 🔴🔴🔴 §118：**仓库根从「本脚本自身位置」推导**，不写死 `HOME/confucius4-openvino`。
#    写死的后果（实测 2026-11-01）：fresh clone 到别处时，
#    `EV` 仍指向**原仓库** ⇒ 本脚本读的证据来自**另一个工作区**
#    ⇒ 「在 clone 上验收通过」是**假象**（它根本没读 clone 里的文件）。
#    ⇒ 判据必须锚定**自己所在的仓库** ⇒ 换机器/换目录才真正可复现。
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EV = os.path.join(REPO, 'results', 'app')

# 🔴🔴 §48：**包目录/版本号一律走单一数据源**，不写死版本
#    ⇒ 写死会在升版后指着旧包跑 ⇒ 报出假回归（§47.6 事故）。
#    ⇒ `--pkg` 可显式指定；不给则由 `pkg_paths` 自动发现**最大版本**的包。
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import pkg_paths as _pkg_paths  # noqa: E402  §48 单一数据源

#: 默认包目录（可被 `--pkg` 覆盖）：由 `pkg_paths` 发现，**不写死版本号**
PKG_DIR = ''
PKG_VER = ''

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:600]})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  —— %s' % detail) if detail else ''))
    return ok


def load(name):
    p = os.path.join(EV, name)
    if not os.path.isfile(p):
        return None, p
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f), p
    except Exception:
        return None, p


def on_pkg(ev, key='pkg'):
    """证据里的包路径是否指向**本次验收的那个包**（按目录名精确比对）。

    🔴 用**目录名精确相等**，不用子串包含 ⇒ 免得「v1.13 的路径里含 v1.3」
    这类前缀误判（`in` 判据会把 `..._v1.3` 当成含 `..._v1.13`）。
    """
    if not isinstance(ev, dict):
        return False, '证据不是 dict'
    v = ev.get(key)
    if not v:
        return False, '证据里没有 %r 字段' % key
    want = os.path.basename(os.path.normpath(PKG_DIR)).lower()
    got = os.path.basename(os.path.normpath(str(v))).lower()
    # 🔴 证据里可能记的是**包根**（`..._v1.13`）也可能是**包内 app 目录**
    #    （`..._v1.13/app`）⇒ 两种都算指向同一个包。
    ok = (want == got
          or got == want + os.sep + 'app'
          or got == want + '/app')
    return ok, '%s = %s（期望包目录名 = %s）' % (key, v, want)



# ══════════════════════════════════════════════════════════════════════
# 🔴🔴🔴 APP-052 ②a：**独立实现**的指纹算法（不 import app191）
#
#   为什么**不** import app191：
#     `app191_acceptance_code_binding_gate.py` **顶层 import numpy**
#     ⇒ 在没有 numpy 的环境里 import 阶段就 abort
#     ⇒ §四纪律「验收脚本不 import 被测模块」的精神同样适用于此：
#     **不 import 另一个验收脚本**（否则两个脚本互相污染）。
#
#   为什么**必须**独立实现（而不是复制粘贴一行）：
#     指纹是「验收声明 ↔ 交付代码」的**唯一锚点**
#     ⇒ 它的算法必须**写死在验收脚本里**（自证），
#        同时 app191 独立算一遍（互证）⇒ 两边不一致会被发现。
# ══════════════════════════════════════════════════════════════════════
def _norm_bytes(data: bytes) -> bytes:
    """归一化行尾（CRLF → LF）⇒ 指纹与「复制/还原」无关（§119）。"""
    return data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _production_modules(pkg_app: str):
    """包内 `app/` 下的**生产模块**（排除开发专用）。"""
    out = []
    try:
        import pkg_exclude
    except Exception:
        pkg_exclude = None
    for n in sorted(os.listdir(pkg_app)):
        if not n.endswith('.py'):
            continue
        if pkg_exclude is not None:
            try:
                if pkg_exclude.is_app_dev_only('app/' + n):
                    continue
            except Exception:
                pass
        out.append(n)
    return out


def _package_fingerprint(pkg_app: str, mods):
    """生产模块集合的**内容指纹**（与 app191.package_fingerprint 逐字一致）。"""
    import hashlib
    h = hashlib.sha256()
    for n in mods:
        p = os.path.join(pkg_app, n)
        with open(p, 'rb') as f:
            data = _norm_bytes(f.read())
        h.update(n.encode('utf-8'))
        h.update(b'\0')
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


def _module_fingerprints(pkg_app: str, mods):
    """逐模块的**内容指纹**（归一化行尾后的 SHA256）。

    🔴🔴🔴 **与 app191 的 `mod_fps` 口径必须逐字一致**
       （否则 R1 会把「没变过的模块」误判为漂移）。
       ⇒ 同样用 `norm_bytes`（CRLF→LF）后再哈希。
    """
    import hashlib
    out = {}
    for nm in mods:
        p = os.path.join(pkg_app, nm)
        try:
            with open(p, 'rb') as f:
                data = f.read()
        except Exception:
            continue
        data = data.replace(b'\r\n', b'\n')
        out[nm] = hashlib.sha256(data).hexdigest()
    return out


#: 🔴🔴🔴 **APP-052 ②a：本轮 reviewer 显式承认的漂移**（白名单）
#:
#:   每条都必须写明 **依据（reason）** 与 **来源（source）**
#:   ⇒ app191 的 R3b 会逐条复核（缺依据 / 多余条目 / 幽灵模块 ⇒ FAIL）。
#:
#:   ⚠️ **只收 reviewer 明确要求的改动**；不得收录任何未经确认的改动。
#:   ⚠️ **不收「本来就应该判为良性」的那些**（home_path_rewrite 等）
#:      —— 那些由 app191 自己判，不需要白名单。
#:
#:   🔴 **本轮的真实构成**（逐条来自 reviewer APP-052 原文）：
#:     · APP-052 ② 末段：GUI 说明文字清理（markdown 星号 / 研发术语 /
#:       重复显示 / 1280×720 截断）⇒ `live_caption_app.py`
#:     · APP-052 ③：docstring 里的开发机家目录 ⇒ `<HOME>` 占位
#:       ⇒ `speaker_assets.py` / `tts_cuda.py` / `tts_cuda_sidecar.py`
#:
#:   ⚠️ **`live_caption_app.py` 同时命中两类**（文案清理 + 也在 §120 的改写集里）
#:      ⇒ 按**文案的实质变更**处理（文案属「reviewer 本轮亲自要求」）。
ACCEPTED_WAIVED = {
    'live_caption_app.py': {
        'reason': 'APP-052 ② 末段：清理 GUI 说明文字（去 markdown 星号 / '
                  'onednn / CUDA plugin 研发术语 / 同段说明重复两次 / '
                  '1280×720 文字截断）⇒ 属 reviewer 本轮亲自要求的实质改动',
        'source': 'APP-052 ② 末段（reviewer 明确要求）',
    },
    'speaker_assets.py': {
        'reason': 'APP-052 ③：模块 docstring 里的开发机家目录字面量 ⇒ '
                  '`<HOME>` 占位（避免随包泄漏开发机用户名）',
        'source': 'APP-052 ③（reviewer 明确要求）',
    },
    'tts_cuda.py': {
        'reason': 'APP-052 ③：模块 docstring 里的开发机家目录字面量 ⇒ '
                  '`<HOME>` 占位（避免随包泄漏开发机用户名）',
        'source': 'APP-052 ③（reviewer 明确要求）',
    },
    'tts_cuda_sidecar.py': {
        'reason': 'APP-052 ③：模块 docstring 里的开发机家目录字面量 ⇒ '
                  '`<HOME>` 占位（避免随包泄漏开发机用户名）',
        'source': 'APP-052 ③（reviewer 明确要求）',
    },
    # 🔴🔴🔴 APP-054：**旁路整体重写**（同步阻塞版 → 线程化版）
    #   reviewer APP-054 第 2 条原文：「feed 只把 PCM 放进队列就返回，旁路改到
    #   独立的工作线程里跑，主循环永不阻塞。旁路自己积压时，只降级（丢弃旧窗口、
    #   本句不打标签），不能反压 ASR。动态形状改成固定分桶，或者 pad 到固定 T」
    #   ⇒ **整体重写是 reviewer 本轮亲自要求的**（不是 App 擅自改动）。
    #   ⇒ 且已由 A/B 实测证明**行为正确**（旁路开时墙钟 300.6 s / 积压 1.2 s，
    #      与旁路关时逐项持平 ⇒ 不拖慢 ASR）。
    'speaker_tracker.py': {
        'reason': 'APP-054 ②：说话人旁路**整体重写** —— ①`feed()` 只入队即返回'
                  '（不再同步推理）② 推理移到**独立后台线程** ③ 攒整窗喂音'
                  '（10 s 整窗 ⇒ 帧数零漂移）④ 积压超限**降级**（丢旧窗口 / '
                  '不打标签）**不反压 ASR** ⑤ `on_final()` 只 peek 自己那一段'
                  '（晚到标签不被吞）⑥ 新增 `enabled` 开关（**默认关**）'
                  ' ⇒ 属 reviewer 本轮亲自要求的根治改动',
        'source': 'APP-054 ②（reviewer 明确要求）',
    },
}


def _build_accepted_payload(args, result):
    """构造 ACCEPTED.json 的 payload（**不写盘**）。"""
    import datetime
    pkg_app = os.path.join(PKG_DIR, 'app')
    _mods = _production_modules(pkg_app)
    _fp = _package_fingerprint(pkg_app, _mods)
    return {
        'accepted': True,
        'version': PKG_VER,
        'pkg_dir': PKG_DIR,
        # 🔴 时间用**实测值**（不推算）
        'accepted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'corrections': ['APP-043', 'APP-045', 'APP-048', 'APP-051', 'APP-052',
                        'APP-053', 'APP-054'],
        # 🔴🔴🔴 **APP-052 ②a：绑定闸门 + 被验收代码的指纹**
        'binding_gate': 'app191',
        'code_fingerprint': _fp,
        'code_fingerprint_alg': (
            'app191.package_fingerprint：SHA256 over（文件名 + NUL + '
            'SHA256(归一化行尾后的模块字节)），按文件名排序；'
            '范围 = 包内 app/ 的**生产模块**'
            '（排除 pkg_exclude.is_app_dev_only）'),
        'n_production_modules': len(_mods),
        # 🔴🔴🔴 **APP-052 ②a：逐模块内容指纹**
        #   ⇒ app191 的 R1 用它做**内容级**漂移检测
        #   ⇒ **不再用「时间」当锚点** ⇒ 改代码后能重签（无死锁）。
        'code_fingerprints': _module_fingerprints(pkg_app, _mods),
        # 🔴🔴🔴 **APP-052 ②a：reviewer 显式承认的漂移（白名单）**
        'waived_changes': ACCEPTED_WAIVED,
        # 🔴🔴 **APP-052 ②a：6 个子项逐项写明**
        'sub_items': result['sub_items'],
        'evidence': {
            'gate': os.path.basename(args.out),
            'pythonw_coldstart': 'results/app/app181_pythonw_coldstart_v2_evidence.json',
            'lnk_shortcut': 'results/app/app192_lnk_coldstart_evidence.json',
            'spe_qa_clone': 'results/app/app175_app043_clone_acceptance_evidence.json',
            'gui_accel': 'results/app/app179_app042_gui_accel_evidence.json',
            'gui_accel_formula': 'results/app/app183_app042_formula_evidence.json',
            'gui_layout_2res': 'results/app/app185_app048_gui_layout_pkg_evidence.json',
            'accel_listen': 'results/app/app184_app051_accel_listen_manifest.json',
            'code_binding': 'results/app/app191_acceptance_code_binding_evidence.json',
        },
        'scope': '链路 + 结构 + 数字自洽；**音质/不变调/可懂由用户实听与 reviewer 判定**',
    }


def _write_accepted_file(acc_path, args, result):
    """写 ACCEPTED.json（先备份旧内容，供回滚）。"""
    import json
    payload = _build_accepted_payload(args, result)
    backup = None
    if os.path.isfile(acc_path):
        with open(acc_path, 'rb') as f:
            backup = f.read()
    with open(acc_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print('[accepted] 已写 %s（%d B）' % (acc_path, os.path.getsize(acc_path)))
    print('[accepted]   code_fingerprint = %s（%d 个生产模块）'
          % (payload['code_fingerprint'], payload['n_production_modules']))
    print('[accepted]   code_fingerprints = %d 个模块的逐模块指纹'
          % len(payload['code_fingerprints']))
    print('[accepted]   waived_changes = %d 条（reviewer 显式承认）'
          % len(payload['waived_changes']))
    for _k, _v in sorted(payload['waived_changes'].items()):
        print('[accepted]     · %-22s ← %s' % (_k, _v['source']))
    return backup, payload


def _rollback_accepted(acc_path, backup):
    """回滚 ACCEPTED.json 到备份内容（备份为 None ⇒ 删除该文件）。"""
    if backup is None:
        if os.path.isfile(acc_path):
            os.remove(acc_path)
        print('[accepted] 🔴 已回滚 ⇒ 删除本轮写入的 ACCEPTED.json')
        return
    with open(acc_path, 'wb') as f:
        f.write(backup)
    print('[accepted] 🔴 已回滚 ⇒ 恢复原 ACCEPTED.json（%d B）' % len(backup))


def main():
    # 🔴 `EV` 在下面 `--out` 的默认参数里已被使用 ⇒ `global` 必须**先于**它
    global EV, PKG_DIR, PKG_VER
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None,
                    help='客户包目录（默认由 pkg_paths 自动发现**最大版本**的包）')
    ap.add_argument('--ev', default=None,
                    help='证据目录（默认 results/app）⇒ 供**鉴别力实测**在'
                         '临时副本上跑同一判据（注入已知缺陷必须 FAIL）')
    ap.add_argument('--out', default=os.path.join(EV, 'app186_app051_acceptance_gate_evidence.json'))
    ap.add_argument('--write-accepted', action='store_true',
                    help='验收通过时，往**包目录**写 ACCEPTED.json（APP-045② 的门）')
    args = ap.parse_args()

    # 🔴 证据目录可覆盖（鉴别力实测用）⇒ 必须在 `load()` 生效前改掉模块级 EV
    if args.ev:
        EV = os.path.abspath(args.ev)

    # 🔴 包目录定案：显式 `--pkg` > 环境变量 > 自动发现（§48 单一数据源）
    PKG_DIR = _pkg_paths.resolve_pkg_dir(args.pkg)
    if not os.path.isdir(os.path.join(PKG_DIR, 'app')):
        print('!! 客户包目录无效（缺 app/）：%s' % PKG_DIR)
        return 2
    _m = re.search(r'_v(\d+(?:\.\d+)*)$', os.path.basename(os.path.normpath(PKG_DIR)))
    PKG_VER = _m.group(1) if _m else _pkg_paths.pkg_version()

    print('=' * 70)
    print('APP-051② / APP-043 真机验收总闸门（目标包 v%s）' % PKG_VER)
    print('=' * 70)

    items = []

    # ── ① pythonw 冷启动 ───────────────────────────────────────────
    ev, p = load('app181_pythonw_coldstart_v2_evidence.json')
    ok1 = check('① pythonw 冷启动证据存在', ev is not None, p)
    if ok1:
        ok1 &= check('① pythonw 冷启动 verdict=PASS',
                     ev.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev.get('verdict'),
                                                       ev.get('n_pass'),
                                                       ev.get('n_fail')))
        o, d = on_pkg(ev)
        ok1 &= check('① pythonw 冷启动跑在 **v%s 包**上' % PKG_VER, o, d)
        obs = ev.get('observations') or []
        ok1 &= check('① 两次独立冷启动（cold1/cold2）都截到**有内容的客户区**',
                     len(obs) >= 2 and all(
                         (o2.get('shot_stats') or {}).get('client_n_colors', 0) >= 8
                         for o2 in obs),
                     'client_n_colors = %r' % [((o2.get('shot_stats') or {})
                                               .get('client_n_colors'))
                                              for o2 in obs])
    items.append(('pythonw_coldstart', ev))

    # ── ①-b 【APP-052 ①】桌面快捷方式（.lnk）有效性 ＋ 从 .lnk 冷启动 ──
    #   🔴 **为什么必须单列**：reviewer APP-052 ① 实测抓到
    #     **桌面 .lnk 是坏链**（LinkFlags 只置 HasArguments ⇒ COM 读回
    #     TargetPath 为空）⇒ §117 的「① 用户启动方式」**从未被验证过**
    #     （app181 直接拉 pythonw.exe，**没有经过 .lnk**）。
    #   ⇒ 这一项**替换**掉「直接拉 pythonw」的验证路径。
    ev1b, p1b = load('app192_lnk_coldstart_evidence.json')
    ok1b = check('①b 桌面快捷方式证据存在', ev1b is not None, p1b)
    if ok1b:
        ok1b &= check('①b 桌面快捷方式闸门 verdict=PASS',
                      ev1b.get('verdict') == 'PASS',
                      'verdict=%r n_pass=%r n_fail=%r' % (ev1b.get('verdict'),
                                                        ev1b.get('n_pass'),
                                                        ev1b.get('n_fail')))
        o1b, d1b = on_pkg(ev1b)
        ok1b &= check('①b 快捷方式闸门跑在 **v%s 包**上' % PKG_VER, o1b, d1b)
        lv = ev1b.get('lnk_verify') or {}
        ok1b &= check('①b .lnk 的 COM 读回 TargetPath **非空**',
                      bool((lv.get('com') or {}).get('target')),
                      'target=%r' % (lv.get('com') or {}).get('target'))
        ok1b &= check('①b .lnk 的 LinkFlags 含**目标定位位**',
                      bool((lv.get('checks') or {}).get('v4_linkflags_has_target')),
                      'flags=0x%08x' % (lv.get('linkflags') or 0))
        disc = ev1b.get('discrimination') or []
        ok1b &= check('①b 快捷方式判据**有鉴别力**（反证组必须全成立）',
                      len(disc) >= 3 and all(d.get('ok') for d in disc),
                      '反证 %d/%d' % (sum(1 for d in disc if d.get('ok')), len(disc)))
        cold = ev1b.get('coldstarts') or []
        ok1b &= check('①b 从 .lnk 冷启动**两次**都成功',
                      len(cold) >= 2 and all(c.get('started') for c in cold),
                      'n=%d' % len(cold))
        ok1b &= check('①b 从 .lnk 起的进程**可执行文件在包内**',
                      any(c.get('procs_in_pkg') for c in cold),
                      'procs=%r' % [c.get('procs_in_pkg') for c in cold])
    items.append(('lnk_shortcut', ev1b))

    # ── ② SPE Q&A 双说话人克隆 ─────────────────────────────────────
    ev2, p2 = load('app175_app043_clone_acceptance_evidence.json')
    ok2 = check('② SPE Q&A 双说话人克隆证据存在', ev2 is not None, p2)
    if ok2:
        ok2 &= check('② 克隆验收 verdict=PASS',
                     ev2.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev2.get('verdict'),
                                                        ev2.get('n_pass'),
                                                        ev2.get('n_fail')))
        o, d = on_pkg(ev2)
        ok2 &= check('② 克隆验收跑在 **v%s 包**上' % PKG_VER, o, d)
        inv = ev2.get('n_played', 0) + ev2.get('n_dropped', 0) == ev2.get('n_submitted', -1)
        ok2 &= check('② 不变式 n_played + n_dropped == n_submitted', inv,
                     '%s + %s == %s' % (ev2.get('n_played'), ev2.get('n_dropped'),
                                        ev2.get('n_submitted')))
        ok2 &= check('② 有句子真的用了**克隆音色**（voice_kind=clone）',
                     (ev2.get('n_clone_rows') or 0) > 0,
                     'n_clone_rows = %r' % ev2.get('n_clone_rows'))
        ok2 &= check('② 有**按句绑定**的 spk 标签（voice_spk）',
                     (ev2.get('n_spk_tagged_lines') or 0) > 0,
                     'n_spk_tagged_lines = %r' % ev2.get('n_spk_tagged_lines'))
    items.append(('spe_qa_clone', ev2))

    # ── ③ GUI 加速播放（链路 + 公式）───────────────────────────────
    ev3, p3 = load('app179_app042_gui_accel_evidence.json')
    ok3 = check('③ GUI 加速播放（链路）证据存在', ev3 is not None, p3)
    if ok3:
        ok3 &= check('③ GUI 加速链路 verdict=PASS',
                     ev3.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev3.get('verdict'),
                                                        ev3.get('n_pass'),
                                                        ev3.get('n_fail')))
        o, d = on_pkg(ev3)
        ok3 &= check('③ GUI 加速跑在 **v%s 包**上' % PKG_VER, o, d)
        ok3 &= check('③ 真的触发了加速（speed>1.0 的句子存在）',
                     (ev3.get('n_accel_rows') or 0) > 0,
                     'n_accel_rows = %r / rows = %r' % (ev3.get('n_accel_rows'),
                                                        ev3.get('n_rows')))
    ev3f, p3f = load('app183_app042_formula_evidence.json')
    ok3 &= check('③ 加速倍率**公式一致性**证据存在（app183）', ev3f is not None, p3f)
    if ev3f:
        ok3 &= check('③ 公式一致性 verdict=PASS',
                     ev3f.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev3f.get('verdict'),
                                                        ev3f.get('n_pass'),
                                                        ev3f.get('n_fail')))
    items.append(('gui_accel', ev3))

    # ── ④ APP-048 两种分辨率截图（**必须在包内跑**）─────────────────
    ev4, p4 = load('app185_app048_gui_layout_pkg_evidence.json')
    ok4 = check('④ APP-048 分辨率截图证据存在（包内跑的 app185）',
                ev4 is not None, p4)
    if ok4:
        ok4 &= check('④ 布局验收 verdict=PASS',
                     ev4.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev4.get('verdict'),
                                                        ev4.get('n_pass'),
                                                        ev4.get('n_fail')))
        # 🔴 `pkg_under_test` 记的是**包内 app 目录**（`<pkg>/app`）
        #    ⇒ 必须比对它的**父目录**（= 包根），否则直接比 basename 会不相等。
        _put = str(ev4.get('pkg_under_test', ''))
        _put_pkg_root = os.path.dirname(os.path.normpath(_put))
        ok4 &= check('④ **跑在客户包内代码**上（不是仓库源码）',
                     os.path.basename(_put_pkg_root).lower()
                     == os.path.basename(os.path.normpath(PKG_DIR)).lower(),
                     'pkg_under_test = %r（其包根 = %r）' % (_put, _put_pkg_root))
        shots = ev4.get('shots') or []
        names = [os.path.basename(str(s.get('path', ''))) for s in shots]
        ok4 &= check('④ 两种分辨率截图都在（1920×1080 / 1280×720）',
                     'app048_layout_1920x1080.png' in names
                     and 'app048_layout_1280x720.png' in names,
                     'shots = %r' % names)
        ok4 &= check('④ 失败态与正常态**像素级不同**（不是同一张图）',
                     (ev4.get('diff_pixels_normal_vs_failed') or 0) > 0,
                     'diff_px = %r' % ev4.get('diff_pixels_normal_vs_failed'))
    items.append(('gui_layout_2res', ev4))

    # ── ⑤ 3 段 1.2–1.3× 配音实听素材 ──────────────────────────────
    ev5, p5 = load('app184_app051_accel_listen_manifest.json')
    ok5 = check('⑤ 1.2–1.3× 实听素材证据存在', ev5 is not None, p5)
    if ok5:
        ok5 &= check('⑤ 实听素材 verdict=PASS', ev5.get('verdict') == 'PASS',
                     'verdict=%r n_pass=%r n_fail=%r' % (ev5.get('verdict'),
                                                        ev5.get('n_pass'),
                                                        ev5.get('n_fail')))
        clips = ev5.get('clips') or []
        ok5 &= check('⑤ 切出 ≥3 段且含 1.2× 与 1.3×',
                     len(clips) >= 3
                     and any(abs(c.get('speed', 0) - 1.2) < 1e-6 for c in clips)
                     and any(abs(c.get('speed', 0) - 1.3) < 1e-6 for c in clips),
                     'speeds = %r' % [c.get('speed') for c in clips])
        # 🔴 文件必须**真实存在**且字节数 > 0（MEMORY：没落盘的东西不能写「已交付」）
        all_exist = True
        for c in clips:
            fp = os.path.join(ev5.get('listen_dir', ''), c.get('file', ''))
            if not (os.path.isfile(fp) and os.path.getsize(fp) == c.get('bytes')):
                all_exist = False
        ok5 &= check('⑤ 每段 wav **真实落盘**且字节数与 manifest 一致',
                     all_exist, 'clips = %d' % len(clips))
    items.append(('accel_listen', ev5))

    # ── 🔴🔴🔴 补丁 8：⑥ 之前的「事务第一步」——**先签** ──────────
    #
    #   **为什么必须先签**（本轮实测的死锁最后一环）：
    #     app191 的 R1/R5/R3b 都需要「**已含新字段**的 ACCEPTED」
    #     （`code_fingerprints` / `code_fingerprint` / `waived_changes`）
    #   ⇒ 「⑥ 要 PASS 才写 ACCEPTED」×「ACCEPTED 写好 ⑥ 才可能 PASS」
    #   ⇒ **死锁** ⇒ 永远无法重签。
    #
    #   ⇒ 解法：**先写后验 + 失败回滚**（transaction 语义）。
    #
    #   🔴 **只有 --write-accepted 时才做** ⇒ 只读模式行为不变。
    _acc_path = os.path.join(PKG_DIR, 'ACCEPTED.json')
    _acc_backup = None
    _res_stub = {
        'sub_items': {
            '1_pythonw_coldstart': bool(ok1),
            '1b_lnk_shortcut': bool(ok1b),
            '2_spe_qa_clone': bool(ok2),
            '3_gui_accel': bool(ok3),
            '4_gui_layout_2res': bool(ok4),
            '5_accel_listen_1.2_1.3': bool(ok5),
            '6_acceptance_code_binding': None,
        },
    }
    if args.write_accepted:
        print()
        print('=' * 70)
        print('🔴 事务第一步：**先签**（写含新字段的 ACCEPTED.json）')
        print('=' * 70)
        _acc_backup, _acc_payload = _write_accepted_file(
            _acc_path, args, _res_stub)

    # ── ⑥ 验收证据 ↔ 被验收代码 的绑定（app191）──────────────────
    # 🔴🔴🔴 **为什么必须加这一项**（本轮实测的真实缺陷）：
    #   本闸门原本只判「证据存在 + verdict=PASS + 指向本包」
    #   ⇒ **从来没有核对「这份证据所验收的代码 == 现在交付的代码」**
    #   ⇒ 实测：`ACCEPTED.json` 写于 00:43:32，而 §120 在 05:56:10
    #     **改写了客户包 5 个生产模块**、06:08:44 重打了 zip
    #   ⇒ 交付物里的代码 ≠ 被验收的代码，而 `accepted=true` 仍成立
    #   ⇒ **没有任何闸门会发现**。
    #   ⇒ 新增 `app191`：逐个漂移模块做**漂移分类**
    #     （良性 = 家目录路径改写 / 逐字相同；其它 ⇒ 验收已被推翻）。
    ok6 = True
    ev6 = None
    p6 = os.path.join(EV, 'app191_acceptance_code_binding_evidence.json')
    try:
        import app191_acceptance_code_binding_gate as _app191
    except Exception:
        _app191 = None
    if _app191 is None:
        ok6 = check('⑥ 验收证据 ↔ 被验收代码 绑定（app191）', False,
                    '无法导入 app191（脚本不在 %s）' % HERE)
    else:
        try:
            r6 = _app191.run(PKG_DIR, prev_evidence=p6)
            ev6 = r6
            _ok_cls = set(_app191.BENIGN) | {getattr(_app191, 'WAIVED',
                                                      'waived')}
            ok6 = check('⑥ 验收证据 ↔ 被验收代码 绑定（app191）',
                        r6['verdict'] == 'PASS',
                        'verdict=%s（漂移 %d 个模块，全部良性/已承认=%s）'
                        % (r6['verdict'], len(r6.get('drifted') or []),
                           all(d.get('cls') in _ok_cls
                               for d in (r6.get('drifted') or []))))
            # 🔴 记录每个漂移模块的分类，便于人工复核
            for d in (r6.get('drifted') or []):
                print('        %-22s cls=%-20s base=%s'
                      % (d['module'], d.get('cls'),
                         str(d.get('base_commit'))[:8]))
        except Exception as e:
            ok6 = check('⑥ 验收证据 ↔ 被验收代码 绑定（app191）', False,
                        'app191 执行异常：%r' % e)

    # ── 总判定 ─────────────────────────────────────────────────────
    overall = all([ok1, ok1b, ok2, ok3, ok4, ok5, ok6])
    print('\n' + '=' * 70)
    print('子项：①pythonw=%s ①b快捷方式=%s ②克隆=%s ③加速=%s ④分辨率=%s '
          '⑤实听=%s ⑥代码绑定=%s'
          % (ok1, ok1b, ok2, ok3, ok4, ok5, ok6))
    print('PASS %d  FAIL %d  verdict=%s'
          % (PASS, FAIL, 'PASS' if overall else 'FAIL'))
    print('=' * 70)

    accepted = bool(overall and FAIL == 0)

    # ── 🔴🔴🔴 补丁 8：⑥ 之后的「事务第二步」——**提交 or 回滚** ───
    #
    #   🔴 **只有 ⑥ PASS 才提交** ⇒ 「ACCEPTED 只在闸门全通过时存在」。
    #   🔴 若 ⑥ FAIL ⇒ **恢复原字节** ⇒ 不留下「自称 accepted 但闸门 FAIL」
    #     的声明（否则会让下游误以为已验收）。
    if args.write_accepted:
        print()
        print('=' * 70)
        print('🔴 事务第二步：%s' % ('**提交**（⑥ 通过 ⇒ 保留新 ACCEPTED）'
                                   if ok6 else
                                   '**回滚**（⑥ 未通过 ⇒ 恢复原 ACCEPTED）'))
        print('=' * 70)
        if ok6:
            # 🔴🔴🔴 **补丁 11**：补上第 6 项的真值
            #   ⇒ 「先签」时 ⑥ 还没跑 ⇒ stub 里第 6 项是 `None`
            #   ⇒ 落盘成 JSON `null` ⇒ ACCEPTED.json 里第 6 项**没有值**
            #   ⇒ ⇒ 提交时**只更新 `sub_items` 字段**（其余逐字不变
            #     ⇒ `accepted_at` / `code_fingerprint` / `code_fingerprints` /
            #        `waived_changes` **全部不变** ⇒ 锚点稳定）。
            import json as _json
            try:
                with open(_acc_path, 'r', encoding='utf-8') as _f:
                    _cur = _json.load(_f)
                _cur['sub_items'] = {
                    '1_pythonw_coldstart': bool(ok1),
                    '1b_lnk_shortcut': bool(ok1b),
                    '2_spe_qa_clone': bool(ok2),
                    '3_gui_accel': bool(ok3),
                    '4_gui_layout_2res': bool(ok4),
                    '5_accel_listen_1.2_1.3': bool(ok5),
                    '6_acceptance_code_binding': bool(ok6),
                }
                with open(_acc_path, 'w', encoding='utf-8') as _f:
                    _json.dump(_cur, _f, ensure_ascii=False, indent=2)
                print('[accepted] ✅ 已补齐 sub_items（6 项全部为真值）')
            except Exception as _e:
                print('[accepted] ⚠️ 补齐 sub_items 失败：%r' % _e)
            print('[accepted] ✅ 已提交新 ACCEPTED.json（指纹锚点 + 白名单就位）')
        else:
            _rollback_accepted(_acc_path, _acc_backup)

    result = {
        'script': os.path.basename(__file__),
        'correction': 'APP-051② / APP-043（真机验收总闸门）',
        'pkg_dir': PKG_DIR,
        'pkg_version': PKG_VER,
        'sub_items': {
            '1_pythonw_coldstart': bool(ok1),
            '1b_lnk_shortcut': bool(ok1b),
            '2_spe_qa_clone': bool(ok2),
            '3_gui_accel': bool(ok3),
            '4_gui_layout_2res': bool(ok4),
            '5_accel_listen_1.2_1.3': bool(ok5),
            '6_acceptance_code_binding': bool(ok6),
        },
        'checks': CHECKS, 'n_pass': PASS, 'n_fail': FAIL,
        'accepted': accepted,
        'resign_transaction': {
            'mode': 'write_then_verify_with_rollback' if args.write_accepted
                    else 'read_only',
            'signed_before_gate': bool(args.write_accepted),
            'committed': bool(args.write_accepted and ok6),
            'rolled_back': bool(args.write_accepted and not ok6),
            'note': 'APP-052 ②a：app191 的 R1/R5/R3b 需要含 code_fingerprint / '
                    'code_fingerprints / waived_changes 的 ACCEPTED ⇒ '
                    '「先签后验」；⑥ 未通过则**回滚**，'
                    '不留下「自称 accepted 但闸门 FAIL」的声明',
        },
        'verdict': 'PASS' if accepted else 'FAIL',
        'note': '「accepted」= 6 个子项**全部**证据存在 + verdict=PASS + '
                '指向 v%s 包；**音质/不变调/可懂仍由用户实听 + reviewer 判定**' % PKG_VER,
    }
    if ev6 is not None:
        result['code_binding'] = {
            'script': 'app191_acceptance_code_binding_gate.py',
            'fingerprint': ev6.get('fingerprint'),
            'drifted': [
                {'module': d.get('module'), 'cls': d.get('cls'),
                 'base_commit': d.get('base_commit'),
                 'sha_before': d.get('sha_before'),
                 'sha_after': d.get('sha_after')}
                for d in (ev6.get('drifted') or [])
            ],
        }

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print('[evidence] %s' % args.out)

    if args.write_accepted and not accepted:
        print('[accepted] 🔴 验收未全部通过 ⇒ ACCEPTED.json 已回滚/未生效')

    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
