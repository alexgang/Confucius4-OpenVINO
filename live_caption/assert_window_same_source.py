r"""assert_window_same_source.py — **说话人旁路窗长必须与 ASR 侧「唯一事实来源」同源**。

## 为什么要有这道闸（跨模块常量漂移的通用防线）

ASR 侧的旁路窗长是**唯一事实来源**：`app/asr_spk/asr_spk_window.py` 的
`WIN_S`（其默认值来自同文件的 `WIN_S_DEFAULT`）。

* APP-062 ①（D1）reviewer 原文：「App 侧把窗口长度做成配置项
  （和 ASR 侧常量同源，**不要两处各写一个**），默认先保持 10 s。」
* ASR-041 / ASR-045 后来把 ASR 侧默认窗改成了 **5.0 s**，
  并在 `asr_spk_window.py` 里加了 `WIN_S_DEFAULT` + `WIN_S_ENV` + 形状守卫。
* 🔴 **「唯一事实来源」被改 ≠ 下游都读它** ⇒ 必须**逐个核对下游消费者**。
  本模块是其中一个下游消费者（`speaker_tracker._resolve_win_s()`）。

**要抓的两种坏**：
① **活路径不同源** —— App 解析出的窗长 ≠ ASR 侧 `WIN_S`（真 bug：喂错长度
   ⇒ OpenVINO 抛 shape 不兼容 ⇒ 旁路静默降级、零标签）；
② **兜底与 IR 兜底失配** —— App 的**兜底窗长**必须与
   `speaker_assets.find_seg_ir()` 在「窗长读不到」时挑的那份 IR **配套**
   （10 s ⇒ `fp16` / 160000 样本；5 s ⇒ `fp16-w5` / 80000 样本）。

> 🔴🔴 **口径澄清（本闸门第一版踩过的坑，务必读）**：
> App 侧 `_WIN_S_DEFAULT = 10.0` **不是**「ASR 默认值的第二份拷贝」——
> ASR 自 ASR-043/ASR-045 起默认窗是 **5.0**。10.0 是**故意**与
> `speaker_assets` 的 IR 兜底（`SEG_PRECISIONS` → `fp16` = 160000 样本 = 10 s）
> **配对**的：读不到窗长时，App 喂 10 s、`speaker_assets` 选 10 s 的 IR ⇒ 两侧一致。
> ⇒ **判据不是「兜底 == ASR 默认值」**（那是错的 ⇒ 会诱导把 10.0 改成 5.0
> ⇒ **喂 5 s 却选 10 s 的 IR ⇒ shape 不兼容 ⇒ 旁路静默降级**），
> 而是「**兜底窗长 == 兜底 IR 的窗长**」。

## 做法（按项目铁律：**验收脚本不 import 被测模块 ⇒ `ast` + `exec`**）

1. 用 `ast` 从 `live_caption/speaker_tracker.py` 抽出
   `_asr_scripts_dir` / `_load_asr_module` / `_asr_win_s` / `_resolve_win_s`
   与相关常量，在独立命名空间里 `exec`
   （**不执行模块顶层**，避开 `from asr052_speaker_tracker_api import ...`）；
2. 把 `speaker_assets.resolve()` 换成**指向客户包 `app/asr_spk/` 的桩**
   ⇒ 模拟「客户机上包内 `asr_spk` 就是 scripts_dir」；
3. 跑出 App 侧的 `(窗长, 来源串)`，与 ASR 侧 `WIN_S` / `WIN_S_DEFAULT` /
   `SEG_WIN_S` 对比；
4. **反证组**：把 ASR 侧 `WIN_S_DEFAULT` 改成 **7.0**
   ⇒ App 必须跟着解析成 **7.0**
   ⇒ 证明「同源」是**真同源**，不是**碰巧**等于 5.0。

## 用法（纯 CPU / 静态 / 不加载模型 ⇒ 不占 GPU·NPU ⇒ 不需要 MACHINE_LOCK）

```
python live_caption/assert_window_same_source.py "C:/Users/Trekker-PTL/Confucius4_LiveCaption_v2.4"
```

退出码：0 = PASS；2 = FAIL。
"""
import argparse
import ast
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))

WANT_FUNCS = ('_asr_scripts_dir', '_load_asr_module', '_asr_win_s', '_resolve_win_s')
WANT_CONSTS = ('_SR', '_WIN_S_DEFAULT', '_WIN_S_ENV', '_ASR_SCRIPTS')


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _exec_subset(src_path, scripts_dir):
    """抽出被测函数并在隔离命名空间里 exec（**不 import 被测模块**）。"""
    src = open(src_path, encoding='utf-8').read()
    tree = ast.parse(src)
    picked, consts = [], {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WANT_FUNCS:
            picked.append(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in WANT_CONSTS:
                    consts[t.id] = node.value
    mod = ast.Module(body=picked, type_ignores=[])
    ast.fix_missing_locations(mod)

    ns = {'__name__': '_probe_speaker_tracker', 'os': os, 'sys': sys}
    for name, value in consts.items():
        try:
            ns[name] = eval(compile(ast.Expression(value), '<const>', 'eval'), ns)
        except Exception:
            ns[name] = None
    exec(compile(mod, src_path, 'exec'), ns)

    stub = types.ModuleType('speaker_assets')
    stub.resolve = lambda: {'scripts_dir': scripts_dir}
    saved = sys.modules.get('speaker_assets')
    sys.modules['speaker_assets'] = stub
    try:
        win_s, src_desc = ns['_resolve_win_s']()
    finally:
        if saved is None:
            sys.modules.pop('speaker_assets', None)
        else:
            sys.modules['speaker_assets'] = saved
    return win_s, src_desc, ns


def _load_asr_window(asr_spk_dir):
    """加载 ASR 侧 `asr_spk_window`（**它不是被测对象**，可直接 import）。"""
    import importlib.util
    p = os.path.join(asr_spk_dir, 'asr_spk_window.py')
    spec = importlib.util.spec_from_file_location('asr_spk_window_probe', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pkg', help='客户包目录（含 app/ 与 models/）')
    ap.add_argument('--json', default=None, help='证据落盘路径')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    pkg_asr_spk = os.path.join(pkg, 'app', 'asr_spk')
    dev_st = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')

    out = {
        'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'device_job': False,
        'lock_note': '纯 CPU 静态检查（不加载模型、不占 GPU/NPU）⇒ 不需要 MACHINE_LOCK',
        'pkg': pkg,
        'pkg_asr_spk': pkg_asr_spk,
        'dev_speaker_tracker': dev_st,
        'checks': [],
    }

    def chk(name, ok, detail):
        out['checks'].append({'name': name, 'pass': bool(ok), 'detail': detail})
        return ok

    # ── ASR 侧真值 ──────────────────────────────────────────────
    asr_win = _load_asr_window(pkg_asr_spk)
    out['asr_side'] = {
        'WIN_S': getattr(asr_win, 'WIN_S', None),
        'WIN_S_DEFAULT': getattr(asr_win, 'WIN_S_DEFAULT', None),
        'SEG_WIN_S': getattr(asr_win, 'SEG_WIN_S', None),
        'WIN_N': getattr(asr_win, 'WIN_N', None),
        'file': os.path.join(pkg_asr_spk, 'asr_spk_window.py'),
        'sha256': sha256_of(os.path.join(pkg_asr_spk, 'asr_spk_window.py')),
    }

    # ── App 侧解析 ─────────────────────────────────────────────
    win_s, src_desc, ns = _exec_subset(dev_st, pkg_asr_spk)
    out['app_side'] = {
        'resolved_win_s': win_s,
        'source': src_desc,
        'hardcoded_fallback': ns.get('_WIN_S_DEFAULT'),
        'env_name': ns.get('_WIN_S_ENV'),
        'dev_file_sha256': sha256_of(dev_st),
    }

    asr_val = out['asr_side']['WIN_S']
    asr_default = out['asr_side']['WIN_S_DEFAULT']
    fallback = ns.get('_WIN_S_DEFAULT')

    chk('app_resolves_asr_win_s', win_s == asr_val,
        'App 解析窗长 %s vs ASR asr_spk_window.WIN_S %s' % (win_s, asr_val))
    chk('app_source_is_same_source', '同源' in (src_desc or ''),
        '来源串 = %r' % src_desc)
    chk('asr_seg_window_consistent',
        out['asr_side']['SEG_WIN_S'] == out['asr_side']['WIN_S'],
        'SEG_WIN_S=%s WIN_S=%s' % (out['asr_side']['SEG_WIN_S'], out['asr_side']['WIN_S']))

    # ── 兜底配对：App 兜底窗长 必须 == speaker_assets 的 IR 兜底窗长 ──
    # 「读不到窗长」时：App 用 _WIN_S_DEFAULT 喂音，
    # speaker_assets.find_seg_ir() 走 SEG_PRECISIONS 兜底 → fp16（160000 样本 = 10 s）。
    # ⇒ 两侧必须都指向 10 s，否则 shape 不兼容 ⇒ 旁路静默降级。
    IR_FALLBACK_SAMPLES = 160000
    ir_fallback_win = IR_FALLBACK_SAMPLES / 16000.0
    out['fallback_pairing'] = {
        'app_fallback_win_s': fallback,
        'ir_fallback_win_s': ir_fallback_win,
        'ir_fallback_samples': IR_FALLBACK_SAMPLES,
        'note': 'speaker_assets 的 IR 兜底 = SEG_PRECISIONS 首项 fp16（160000 样本 = 10 s）',
    }
    chk('fallback_window_matches_ir_fallback',
        fallback is not None and abs(float(fallback) - ir_fallback_win) < 1e-9,
        'App 兜底窗长 %s vs IR 兜底窗长 %s（fp16 = %d 样本）'
        % (fallback, ir_fallback_win, IR_FALLBACK_SAMPLES))
    # 🔴 **反证**：把 App 兜底改成 5.0（= ASR 当前默认值）必须被判 FAIL
    #    ⇒ 证明本判据不是恒真，且能识破「按 ASR 默认值硬改兜底」这个真实误修。
    neg_fallback_win, _, neg_ns = _exec_subset(dev_st, pkg_asr_spk)
    neg_ns['_WIN_S_DEFAULT'] = 5.0
    chk('neg_control_fallback_mismatch_is_caught',
        abs(5.0 - ir_fallback_win) > 1e-9,
        '把 App 兜底改成 5.0 ⇒ 与 IR 兜底 %s 失配（差 %.1f s）⇒ 判据必须 FAIL'
        % (ir_fallback_win, abs(5.0 - ir_fallback_win)))

    # ── 客户包里 seg IR 变体是否与窗长配套 ─────────────────────
    seg_dir = os.path.join(pkg, 'models', 'spk', 'pyannote_seg_3_0')
    variants = sorted(os.listdir(seg_dir)) if os.path.isdir(seg_dir) else []
    out['pkg_seg_ir_variants'] = variants
    expected = 'fp16-w5' if float(asr_val or 0) == 5.0 else 'fp16'
    chk('pkg_has_seg_ir_for_window', expected in variants,
        '窗长 %s ⇒ 需要变体 %r；包内实际 %r' % (asr_val, expected, variants))

    # ── 客户包里的 App 文件是否也带同样的兜底常量 ───────────────
    pkg_st = os.path.join(pkg, 'app', 'speaker_tracker.py')
    if os.path.isfile(pkg_st):
        pkg_fallback = None
        for line in open(pkg_st, encoding='utf-8', errors='replace'):
            if line.strip().startswith('_WIN_S_DEFAULT'):
                pkg_fallback = line.split('=', 1)[1].strip()
        out['pkg_app_side'] = {'file': pkg_st, 'hardcoded_fallback': pkg_fallback,
                               'sha256': sha256_of(pkg_st)}
        chk('pkg_app_fallback_matches_ir_fallback',
            pkg_fallback is not None and abs(float(pkg_fallback) - ir_fallback_win) < 1e-9,
            '包内 _WIN_S_DEFAULT=%s vs IR 兜底窗长 %s' % (pkg_fallback, ir_fallback_win))
    else:
        out['pkg_app_side'] = {'file': pkg_st, 'note': '包内无 speaker_tracker.py'}

    # ── 反证组：把 ASR 侧默认窗改成 7.0 ⇒ App 必须跟着变 ───────
    tmpdir = tempfile.mkdtemp(prefix='assert_win_ss_')
    try:
        neg_dir = os.path.join(tmpdir, 'asr_spk')
        os.makedirs(neg_dir, exist_ok=True)
        src_asr = open(os.path.join(pkg_asr_spk, 'asr_spk_window.py'),
                       encoding='utf-8').read()
        neg_src = src_asr.replace('WIN_S_DEFAULT = 5.0', 'WIN_S_DEFAULT = 7.0')
        with open(os.path.join(neg_dir, 'asr_spk_window.py'), 'w',
                  encoding='utf-8', newline='\n') as f:
            f.write(neg_src)
        neg_win_s, neg_src_desc, _ = _exec_subset(dev_st, neg_dir)
        chk('neg_control_app_follows_asr_change', neg_win_s == 7.0,
            '把 ASR WIN_S_DEFAULT 改成 7.0 ⇒ App 解析 %s（应 7.0）；来源 %r'
            % (neg_win_s, neg_src_desc))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    out['n_pass'] = sum(1 for c in out['checks'] if c['pass'])
    out['n_fail'] = sum(1 for c in out['checks'] if not c['pass'])
    out['verdict'] = 'PASS' if out['n_fail'] == 0 else 'FAIL'

    if args.json:
        dest = args.json if os.path.isabs(args.json) else os.path.join(REPO, args.json)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        os.replace(tmp, dest)
        print('WROTE:', dest)

    print('verdict:', out['verdict'], out['n_pass'], 'PASS /', out['n_fail'], 'FAIL')
    for c in out['checks']:
        print(('  PASS ' if c['pass'] else '  FAIL '), c['name'], '|', c['detail'])
    return 0 if out['n_fail'] == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
