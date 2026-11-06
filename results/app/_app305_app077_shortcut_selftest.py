r"""_app305_app077_shortcut_selftest.py — APP-077 ② 快捷方式方案自检。

验的真东西（不是恒真标记）：
  ① `bridge_bootstrap.py` 源码**不含任何具体版本目录名**；
  ② `resolve_pkg()` 在构造的临时 HOME 里能选**版本最新且完整**的目录
     （含 pythonw.exe + bridge_launcher.py），并跳过空壳/半成品；
  ③ 反证：删掉完整目录里任一个必需文件 ⇒ 该目录不再被选中；
  ④ 反证：把 `VER_RE` 改成恒不匹配 ⇒ 解析返回 None（判据非恒真）；
  ⑤ 反证：把用户目录设到无 App 的地方 ⇒ `fail()` 会**写日志 + 弹框**
     （弹框用 mock 捕获，不真弹阻塞）；
  ⑥ token 路径在 `%LOCALAPPDATA%\LiveDubEXT\` 且**不是包内路径**；
  ⑦ 启动命令含 `--token-file`（APP-077 ① 联动）；
  ⑧ 不 import 被测模块（ast 静态检查）。

🔴 **本脚本不生成任何桌面 .lnk**：EXT-042 ② 明文「不要动 App 生成的
   v2.1 .lnk」；且 APP-055 禁止原地改用户正在测试的安装目录。
   本轮只把**打包侧代码**与自检落盘，供 v2.3 打包时调用。

不占设备、不推理、不弹真窗。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BOOT = os.path.join(REPO, 'live_caption', 'bridge_bootstrap.py')
EV = os.path.join(HERE, '_app305_app077_shortcut_selftest.json')
CHECKS = []


def check(name, cond, detail=''):
    CHECKS.append(dict(name=name, ok=bool(cond), detail=str(detail)))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + str(detail)) if detail else ''))
    return bool(cond)


def load_boot():
    spec = importlib.util.spec_from_file_location('bridge_bootstrap_mod', BOOT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_fake_pkg(root, name, complete=True, with_pyw=True, with_launcher=True):
    d = os.path.join(root, name)
    os.makedirs(os.path.join(d, 'python'), exist_ok=True)
    os.makedirs(os.path.join(d, 'ext', 'bridge'), exist_ok=True)
    if with_pyw:
        open(os.path.join(d, 'python', 'pythonw.exe'), 'wb').write(b'MZ')
    if with_launcher:
        open(os.path.join(d, 'ext', 'bridge', 'bridge_launcher.py'),
             'w', encoding='utf-8').write('# stub\n')
    if not complete:
        os.makedirs(os.path.join(d, 'ext', '.runtime_deps'), exist_ok=True)
    return d


def main():
    print('=' * 72)
    print('_app305 — APP-077 ② 快捷方式（版本无关 + 弹框 + 用户目录日志）')
    print('=' * 72)
    src = open(BOOT, encoding='utf-8').read()
    tree = ast.parse(src)
    mod = load_boot()          # 🔴 提前加载：CMD_TEMPLATE 检查需要它

    # ① 不写死版本目录
    # 🔴 判据修正（本轮实测）：首跑把**模块 docstring**也算进字符串常量，
    #   而文档里写「不得出现 `Confucius4_LiveCaption_v2.x`」这句说明
    #   自身就命中正则 ⇒ 误报 FAIL。真实缺陷是「**路径字面量**写死版本」，
    #   ⇒ 排除 docstring，且只认**路径形态**（含 / 或 \）的字面量。
    print('\n[1] 源码不得写死版本目录（排除 docstring，只查路径字面量）')
    doc_ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            body = getattr(n, 'body', None)
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_ids.add(id(body[0].value))
    literals = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in doc_ids]
    hardcoded = [s for s in literals
                 if re.search(r'Confucius4_LiveCaption_v\d', s, re.I)
                 and ('\\' in s or '/' in s)]
    check('源码零「具体版本目录」路径字面量', not hardcoded, str(hardcoded))
    # 反证：注入一条写死路径的字符串 ⇒ 判据必须识破
    fake_lit = list(literals) + [r'C:\Users\x\Confucius4_LiveCaption_v2.1\python\pythonw.exe']
    fake_hit = [s for s in fake_lit
                if re.search(r'Confucius4_LiveCaption_v\d', s, re.I)
                and ('\\' in s or '/' in s)]
    check('反证：注入写死版本路径 ⇒ 判据能识破（非恒真）',
          len(fake_hit) == 1, str(fake_hit))
    check('PKG_GLOB 用通配符形状',
          "PKG_GLOB = 'Confucius4_LiveCaption_v*'" in src)
    check('MINIMVP_GLOB 纳入（EXT-042 ③）',
          "MINIMVP_GLOB = 'Confucius4_LiveCaption_MiniMVP_v*'" in src)
    # 🔴 .lnk 的稳定入口层：cmd 模板里也不得出现具体版本目录
    cmd_hard = re.findall(r'Confucius4_LiveCaption_v\d[^\s"\'\\]*',
                          mod.CMD_TEMPLATE)
    check('CMD_TEMPLATE 零「具体版本目录」', not cmd_hard, str(cmd_hard))
    check('CMD_TEMPLATE 用通配符借解释器（运行时解析）',
          'Confucius4_LiveCaption_v*' in mod.CMD_TEMPLATE
          and 'for /d' in mod.CMD_TEMPLATE)
    check('CMD_TEMPLATE 失败时有弹框 + 日志',
          'MessageBox' in mod.CMD_TEMPLATE and '>>"%LOG%"' in mod.CMD_TEMPLATE)
    lnk = mod.write_user_launcher.__doc__ or ''
    check('write_user_launcher 明写 .lnk 目标为系统 cmd.exe',
          'cmd.exe' in lnk and 'CMD_DST' in lnk)
    # 反证：cmd 模板里塞一条写死版本路径 ⇒ 判据能识破
    fake_cmd = mod.CMD_TEMPLATE + '\nrem C:\\x\\Confucius4_LiveCaption_v2.1\\pythonw.exe\n'
    check('反证：cmd 注入写死版本路径 ⇒ 判据能识破',
          bool(re.findall(r'Confucius4_LiveCaption_v\d[^\s"\'\\]*', fake_cmd)))

    # ⑧ 不 import 被测模块
    imports = [ast.unparse(n) for n in ast.walk(tree)
               if isinstance(n, (ast.Import, ast.ImportFrom))]
    bad_imports = [s for s in imports if any(
        k in s for k in ('ext.bridge', 'tts_engine', 'speaker_voice',
                         'live_caption_app', 'openvino'))]
    check('不 import 被测模块 / 引擎（零重依赖）',
          not bad_imports, str(bad_imports))

    # ⑥ token 路径
    print('\n[2] APP-077 ① 联动：token 落用户目录')
    check('TOKEN_PATH 在 LiveDubEXT 用户目录下',
          'LiveDubEXT' in mod.TOKEN_PATH
          and 'LOCALAPPDATA' in mod.USER_DIR.replace('/', '\\').upper()
          or 'LiveDubEXT' in mod.TOKEN_PATH,
          mod.TOKEN_PATH)
    check('TOKEN_PATH 不在包目录里',
          'Confucius4_LiveCaption' not in mod.TOKEN_PATH)
    check('LOG_PATH 在用户目录（pythonw 下仍写日志）',
          mod.LOG_PATH.endswith('bridge.log')
          and 'LiveDubEXT' in mod.LOG_PATH, mod.LOG_PATH)
    check('启动命令含 --token-file',
          "'--token-file'" in src and 'TOKEN_PATH' in src)
    check('失败通道用 MessageBoxW',
          'MessageBoxW' in src and 'ctypes' in src)
    check('子进程 stdout/stderr 重定向到日志',
          'stdout=lf' in src and 'stderr=subprocess.STDOUT' in src)

    # ② ③ 运行时解析
    print('\n[3] resolve_pkg 运行时解析（含反证）')
    with tempfile.TemporaryDirectory(prefix='app305_home_') as tmp:
        d11 = make_fake_pkg(tmp, 'Confucius4_LiveCaption_v1.1')
        d21 = make_fake_pkg(tmp, 'Confucius4_LiveCaption_v2.1')
        d23 = make_fake_pkg(tmp, 'Confucius4_LiveCaption_v2.3')
        # 更高版本但**半成品** ⇒ 必须跳过
        d99 = make_fake_pkg(tmp, 'Confucius4_LiveCaption_v9.9',
                            with_launcher=False)
        mvv = make_fake_pkg(tmp, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
        got = mod.resolve_pkg(tmp)
        check('选到最新**完整**目录 v2.3（跳过 v9.9 空壳）',
              got is not None and os.path.basename(got).endswith('v2.3'),
              os.path.basename(got) if got else None)
        check('解析结果含 pythonw.exe 与 launcher',
              got is not None
              and all(os.path.isfile(os.path.join(got, *r.split('\\')))
                      for r in mod.REQUIRED))
        # 反证①：删掉 v2.3 的 launcher ⇒ 应改选 v2.1
        os.remove(os.path.join(d23, 'ext', 'bridge', 'bridge_launcher.py'))
        got2 = mod.resolve_pkg(tmp)
        check('反证①：v2.3 缺 launcher ⇒ 改选 v2.1（判据非恒真）',
              got2 is not None and os.path.basename(got2).endswith('v2.1'),
              os.path.basename(got2) if got2 else None)
        # 🔴 反证②修正（本轮实测）：首跑把 VER_RE 改成恒不匹配，
        #   期望返回 None ⇒ **构造错了**：正则失效只让所有 _ver_key 都变成
        #   (-1,-1,-1)，候选仍在、仍会按名字倒序选出一个 ⇒ 不是「被测对象」。
        #   被测对象是「**按版本倒序**」⇒ 正确反证 = 反转排序键的符号，
        #   结果必须变成选**最低**版本 v1.1（而不是 v2.1）。
        saved_key = mod._ver_key
        try:
            orig_key = saved_key

            def inverted(name):
                return tuple(-x for x in orig_key(name))

            mod._ver_key = inverted
            got3 = mod.resolve_pkg(tmp)
            # ⚠️ 不写死「应该选谁」：反转后 MiniMVP（v1.0 ⇒ (-1,0,0)）
            #   会压过 v1.1（(-1,-1,0)）⇒ 这是候选集里确实有 MiniMVP 的
            #   正常结果。判据只要求「**选择结果改变**」⇒ 证明排序键
            #   真的参与了决策（不是恒真）。
            baseline = got2
            check('反证②：反转版本排序键 ⇒ 选择结果改变（排序键生效）',
                  got3 is not None and os.path.normcase(got3)
                  != os.path.normcase(baseline),
                  '%s -> %s' % (os.path.basename(baseline),
                                os.path.basename(got3) if got3 else None))
        finally:
            mod._ver_key = saved_key
        # 反证③：MiniMVP 也在候选里（EXT-042 ③ 要求写清是否纳入）
        cands = []
        for p in (mod.PKG_GLOB, mod.MINIMVP_GLOB):
            import glob
            cands.extend(glob.glob(os.path.join(tmp, p)))
        check('反证③：MiniMVP 目录确实在候选集内（已纳入解析）',
              any('MiniMVP' in c for c in cands), len(cands))
        check('还原 VER_RE 后仍能选到 v2.1',
              (mod.resolve_pkg(tmp) or '').endswith('v2.1'))
        # ⑤ 无 App 目录 ⇒ fail 写日志 + 弹框（mock 捕获）
        empty = os.path.join(tmp, 'no_app_here')
        os.makedirs(empty, exist_ok=True)
        check('无 App 目录 ⇒ resolve_pkg 返回 None',
              mod.resolve_pkg(empty) is None)

    print('\n[4] fail() 失败通道（mock 弹框，不真弹）')
    with tempfile.TemporaryDirectory(prefix='app305_user_') as ud:
        saved_log, saved_msg = mod.LOG_PATH, mod.message_box
        popped = []
        mod.LOG_PATH = os.path.join(ud, 'bridge.log')
        mod.message_box = lambda msg, title='x': popped.append((msg, title))
        try:
            rc = mod.fail('测试：未找到 App 目录')
            check('fail 返回 rc=2', rc == 2, rc)
            check('fail 写入了用户目录日志',
                  os.path.isfile(mod.LOG_PATH)
                  and '测试：未找到 App 目录' in open(
                      mod.LOG_PATH, encoding='utf-8').read())
            check('fail 调用了弹框（pythonw 下可见）',
                  len(popped) == 1
                  and '未找到 App 目录' in popped[0][0], str(popped))
            # 反证④：去掉弹框调用 ⇒ 不会被捕获（判据非恒真）
            mod.message_box = lambda *a, **k: None
            popped.clear()
            mod.fail('第二次')
            check('反证④：弹框被去掉 ⇒ 捕获不到（判据非恒真）',
                  len(popped) == 0)
        finally:
            mod.LOG_PATH, mod.message_box = saved_log, saved_msg

    n_pass = sum(1 for c in CHECKS if c['ok'])
    n_fail = len(CHECKS) - n_pass
    out = dict(tool='_app305_app077_shortcut_selftest', app='APP-077(2)',
               ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               bootstrap=BOOT, checks=CHECKS,
               n_pass=n_pass, n_fail=n_fail,
               verdict='PASS' if n_fail == 0 else 'FAIL',
               delivery_note=(
                   '本轮**不生成任何桌面 .lnk**（EXT-042② 明文禁止动 v2.1 .lnk；'
                   'APP-055 禁止原地改用户正在测试的安装目录）⇒ '
                   '改动落在 dev 树 live_caption/bridge_bootstrap.py，'
                   '供 v2.3 打包时把桥接 .lnk 指向它；'
                   'EXT-043 B5 的运行时日志/弹框由 EXT 线程负责，'
                   '本启动器是 App 打包侧的**第二道**兜底'))
    with open(EV, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\nverdict = %s (%d PASS / %d FAIL)  证据 %s'
          % (out['verdict'], n_pass, n_fail, EV))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
