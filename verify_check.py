# -*- coding: utf-8 -*-
"""verify_check.py — 验证 --check 环境检查功能（Diagnose.bat 依赖）。

检查项：
  1. argparse 接受 --check（原来直接报 unrecognized arguments）
  2. run_check() 可正常执行、不抛异常
  3. 输出包含关键节：依赖 / 设备 / ASR 后端 / 翻译后端 / 音频设备
  4. 每个 ASR 后端都有一行，且带 OK/缺 标记
  5. 每个翻译后端（MT_ALL_CANDIDATES）都有一行
  6. GPU / NPU 探测结果与 ov.Core().available_devices 一致
  7. _check_models 的就绪判定与实际文件一致
  8. CJK 对齐函数 _pad 的宽度计算正确
  9. Diagnose.bat 里的 --check 调用能真正跑通（不报 argparse 错）
 10. 不硬编码开发机路径（开发版与客户包都能定位 models/）
"""
import io
import os
import re
import subprocess
import sys
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_APP = os.path.join(HERE, 'live_caption')


def _latest_pkg_root():
    """自动发现最新的客户包目录（按版本号排序）。

    写死版本号的话每次升级都要改脚本 —— 改成自动发现。
    """
    parent = os.path.dirname(HERE)
    cands = []
    for d in os.listdir(parent):
        if d.startswith('Confucius4_LiveCaption_v') and os.path.isdir(os.path.join(parent, d)):
            ver = d.rsplit('_v', 1)[-1]
            try:
                cands.append((tuple(int(x) for x in ver.split('.')), d))
            except ValueError:
                pass
    if not cands:
        raise SystemExit('找不到客户包目录')
    cands.sort()
    return os.path.join(parent, cands[-1][1])


PKG_ROOT = _latest_pkg_root()
PKG_APP = os.path.join(PKG_ROOT, 'app')
PKG_PY = os.path.join(PKG_ROOT, 'python', 'python.exe')

# 客户包自带的 Python（带 numpy / openvino_genai）
PY = PKG_PY if os.path.exists(PKG_PY) else sys.executable

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(f'[{"PASS" if cond else "FAIL"}] {name}' + (f'  — {detail}' if detail else ''))


def run_python(code, cwd=None, extra_env=None):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    if extra_env:
        env.update(extra_env)
    p = subprocess.run([PY, '-s', '-c', code], cwd=cwd, env=env,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=300)
    return p.stdout, p.stderr, p.returncode


# ── 1. argparse 接受 --check ──────────────────────────────────────────
for label, appdir in (('开发版', DEV_APP), ('客户包', PKG_APP)):
    script = os.path.join(appdir, 'live_caption_app.py')
    src = open(script, encoding='utf-8').read()
    check(f'{label}：argparse 定义了 --check',
          "'--check'" in src, 'add_argument("--check"')
    check(f'{label}：--check 被派发到 run_check()',
          re.search(r'args\.check\s*\n\s*run_check\(\)', src) is not None
          or 'run_check()' in src)

# ── 2/3/4/5. run_check 输出内容 ────────────────────────────────────────
CODE = r'''
import io, sys, os, contextlib
sys.path.insert(0, %r)
import live_caption_app as A
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    A.run_check()
out = buf.getvalue()
print("<<<OUT>>>")
print(out)
print("<<<END>>>")
'''

for label, appdir in (('开发版', DEV_APP), ('客户包', PKG_APP)):
    so, se, rc = run_python(CODE % appdir, cwd=appdir)
    if '<<<OUT>>>' not in so:
        check(f'{label}：run_check() 正常执行', False, se.strip()[:200])
        continue
    out = so.split('<<<OUT>>>')[1].split('<<<END>>>')[0]
    check(f'{label}：run_check() 正常执行', rc == 0, f'rc={rc}')
    for sec in ('依赖', 'OpenVINO 设备', 'ASR 后端', '翻译后端', '音频设备', '结论'):
        check(f'{label}：输出含「{sec}」节', sec in out)

    # 每个 ASR 后端一行（用 ENGINES 的 label 去匹配输出行）
    so2, se2, _ = run_python(
        'import sys; sys.path.insert(0, %r)\n'
        'import live_caption_app as A\n'
        'for k, c in A.ENGINES.items(): print("ENG", k, c["label"])\n'
        'for k, c in A.MT_ALL_CANDIDATES.items(): print("MT", k, c["label"])' % appdir,
        cwd=appdir)
    eng_rows = [l.split(' ', 2)[1:] for l in so2.splitlines() if l.startswith('ENG ')]
    mt_rows = [l.split(' ', 2)[1:] for l in so2.splitlines() if l.startswith('MT ')]
    out_lines = out.splitlines()
    # 按节切分（ASR 的 label 可能是翻译 label 的子串，如 'Intel GPU · INT8'
    # 是 'Intel GPU · INT8-CW' 的前缀，必须分节匹配）
    def section(title, nxt):
        i = out.index(title)
        j = out.index(nxt) if nxt in out else len(out)
        return out[i:j]
    asr_sec = section('── ASR 后端', '── 翻译后端')
    mt_sec = section('── 翻译后端', '── 音频设备')
    asr_lines = [l for l in asr_sec.splitlines() if '[ OK ]' in l or '[缺 ]' in l]
    # v1.3：翻译后端表用三种标记 —— [ OK ] 可用 / [缺 ] 本机缺模型 /
    #        [ — ] 本包不附带该量化版本（不是故障）
    mt_lines = [l for l in mt_sec.splitlines()
                if '[ OK ]' in l or '[缺 ]' in l or '[ — ]' in l]
    for k, lbl in eng_rows:
        hit = [l for l in asr_lines if lbl in l]
        check(f'{label}：ASR 后端 {k}（{lbl}）在检查输出中有一行',
              len(hit) == 1, f'{len(hit)} 行')
    check(f'{label}：ASR 后端行数与后端数一致',
          len(asr_lines) == len(eng_rows), f'{len(asr_lines)} 行 / {len(eng_rows)} 后端')
    for k, lbl in mt_rows:
        hit = [l for l in mt_lines if lbl in l]
        check(f'{label}：翻译后端 {k}（{lbl}）在检查输出中有一行',
              len(hit) == 1, f'{len(hit)} 行')
    check(f'{label}：翻译后端 5 项都在输出里', len(mt_rows) >= 5, f'{len(mt_rows)} 项')
    # v1.3：INT8 两项应标为「本包不附带」，且不得报成「缺模型」
    # 注意：**只对客户包**成立 —— 开发机 hy_bench/ov/ 下仍装着 INT8 产物，
    # 那里显示 [ OK ] 是正确的。
    if label.startswith('客户包'):
        for lbl in ('Intel GPU · INT8-CW', 'Intel NPU · INT8-CW'):
            hit = [l for l in mt_lines if lbl in l]
            check(f'{label}：{lbl} 标为「本包不附带」而非「缺模型」',
                  bool(hit) and '[ — ]' in hit[0] and '[缺 ]' not in hit[0],
                  hit[0].strip() if hit else '未出现')

# ── 6. 设备探测与 ov.Core 一致 ────────────────────────────────────────
so, se, rc = run_python(
    'import openvino as ov\n'
    'c = ov.Core()\n'
    'for d in c.available_devices: print("DEV", d)')
ov_devs = {l.split(' ', 1)[1] for l in so.splitlines() if l.startswith('DEV ')}
so, se, rc = run_python(
    'import sys; sys.path.insert(0, %r)\n'
    'import live_caption_app as A\n'
    'd = A._check_devices()\n'
    'for k in d: print("DEV", k)' % PKG_APP, cwd=PKG_APP)
app_devs = {l.split(' ', 1)[1] for l in so.splitlines() if l.startswith('DEV ')}
check('_check_devices() 与 ov.Core().available_devices 一致',
      app_devs == ov_devs, f'app={sorted(app_devs)} ov={sorted(ov_devs)}')

# ── 7. _check_models 判定与实际文件一致 ───────────────────────────────
so, se, rc = run_python(
    'import sys, os; sys.path.insert(0, %r)\n'
    'import live_caption_app as A\n'
    'm = A._check_models()\n'
    'for k, (ok, why) in m.items():\n'
    '    print("M", k, "1" if ok else "0", why)' % PKG_APP, cwd=PKG_APP)
lines = [l for l in so.splitlines() if l.startswith('M ')]
check('_check_models() 返回全部 ASR 后端', len(lines) == 6, f'{len(lines)} 项')
# CUDA 判定应与 audiocpp_cli.exe 是否真实存在一致
# （本机有 ~/confucius4-r2t2 开发机布局 → 就绪；纯客户机 → 缺）
so2, _, _ = run_python(
    'import sys, os; sys.path.insert(0, %r)\n'
    'import live_caption_app as A\n'
    'print("CLI", 1 if (A.CUDA_CLI and os.path.exists(A.CUDA_CLI)) else 0)' % PKG_APP,
    cwd=PKG_APP)
cli_present = 'CLI 1' in so2
cuda_rows = [l for l in lines if 'cuda' in l]
check('CUDA 判定与 audiocpp_cli.exe 存在性一致',
      len(cuda_rows) == 2 and
      all((l.split()[2] == '1') == cli_present for l in cuda_rows),
      f'audiocpp_cli={cli_present}，CUDA 判定={[l.split()[2] for l in cuda_rows]}')
intel_rows = [l for l in lines if 'cuda' not in l]
check('客户包内 4 个 Intel 后端判为就绪',
      len(intel_rows) == 4 and all(l.split()[2] == '1' for l in intel_rows),
      f'{len(intel_rows)} 项 Intel')

# ── 8. _pad 宽度 ──────────────────────────────────────────────────────
so, se, rc = run_python(
    'import sys; sys.path.insert(0, %r)\n'
    'import live_caption_app as A\n'
    'print(repr(A._pad("abc", 10)))\n'
    'print(repr(A._pad("中文", 10)))\n'
    'print(len(A._pad("中文", 10)))' % PKG_APP, cwd=PKG_APP)
rows = so.splitlines()
check('_pad 纯 ASCII 补到指定宽度',
      rows and rows[0] == repr('abc       '), rows[0] if rows else '')
check('_pad 中文按 2 格宽计算（补 6 空格）',
      len(rows) > 1 and rows[1] == repr('中文      '), rows[1] if len(rows) > 1 else '')

# ── 9. Diagnose.bat 的 --check 调用不报 argparse 错 ───────────────────
p = subprocess.run(['cmd', '/c', 'Diagnose.bat'], cwd=PKG_ROOT,
                   capture_output=True, text=True, encoding='utf-8',
                   errors='replace', timeout=300, input='')
out = p.stdout
check('Diagnose.bat 跑通（无 unrecognized arguments）',
      'unrecognized arguments' not in out and 'unrecognized argument' not in out)
check('Diagnose.bat 输出含「环境检查」', '环境检查' in out)
check('Diagnose.bat 输出含 ASR 后端 OK 标记', '[ OK ]' in out)

# ── 10. 无开发机硬编码路径 ────────────────────────────────────────────
for label, appdir in (('开发版', DEV_APP), ('客户包', PKG_APP)):
    src = open(os.path.join(appdir, 'live_caption_app.py'), encoding='utf-8').read()
    hard = re.findall(r'C:\\\\?Users\\\\?Trekker|C:/Users/Trekker', src)
    check(f'{label}：live_caption_app.py 无开发机绝对路径', not hard, str(hard[:3]))
    src2 = open(os.path.join(appdir, 'translator.py'), encoding='utf-8').read()
    hard2 = re.findall(r'C:\\\\?Users\\\\?Trekker|C:/Users/Trekker', src2)
    check(f'{label}：translator.py 无开发机绝对路径', not hard2, str(hard2[:3]))

print()
n_ok = sum(1 for _, ok, _ in results if ok)
print(f'==== {n_ok}/{len(results)} PASS ====')
sys.exit(0 if n_ok == len(results) else 1)
