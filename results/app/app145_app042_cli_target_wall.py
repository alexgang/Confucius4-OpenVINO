# -*- coding: utf-8 -*-
"""APP-042 CLI 目标墙钟回归闸门（app145）。

**缺陷背景（真机实测暴露）**
  APP-042 的「自适应加速」依赖 `tts.submit(..., target_play_at=...)`。
  真机 CLI 回放（SPE 前 5 分钟）落盘的逐句 jsonl 里：
      `speed` 有值，但 `target_wall` **恒为 None**
  ⇒ 加速参数**从未下发** ⇒ CLI 下自适应加速链路**永不触发**。
  根因：目标墙钟机制**只做在 GUI `App` 类**
        （`_session_wall0` 只在 `App.start()` 赋值），
        CLI 的三处 `tts.submit(...)` 全都不传 `target_play_at`。

**本闸门要证明**
  ① REAL 组：CLI 的三处 `tts.submit` **都**传了 `target_play_at`；
     CLI 有会话起点墙钟 `_cli_wall0 = time.time()`；
     CLI 有目标墙钟计算 `_cli_target_wall()`；
     `on_final` 在 submit **之前**登记段号→目标墙钟。
  ② 反证组：把三处 `target_play_at=` **整块删掉** ⇒ 必须 FAIL
     ⇒ 证明判据**不恒真**。

**纪律**
  - 🔴 验收脚本**一律不 `import` 被测模块**（顶层 numpy 会让 import 阶段 abort）
    ⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间。
  - 🔴 反证删代码必须删「**整块**」（只删 `if` 行 ⇒ IndentationError
    ⇒ 反证脚本自己崩 ⇒ 看起来像「缺陷没复现」）。
  - 🔴 分组计分：REAL 组须全 PASS 且反证组**须有 FAIL** ⇒ verdict=true。
"""
import ast
import json
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
SRC = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
OUT = os.path.join(REPO, 'results', 'app',
                   'app145_app042_cli_target_wall_evidence.json')

# 🔴 反证组：**在 AST 层面**剥离 CLI 三处 submit 的 `target_play_at` keyword。
#
#   ⚠️ **为什么不用正则删文本行**：GUI 侧那处 `target_play_at=` 是**多行续行**
#     （`target_play_at=self._seg_target_wall.get(\n    ev['seg']))`）
#     ⇒ 按行删会留下孤立括号 ⇒ `SyntaxError` ⇒ **反证脚本自己崩**
#     ⇒ 看起来像「缺陷没复现」⇒ **判据失效**（自踩坑）。
#   ⇒ 改用 `ast` 找到 Call → 删 keyword → `ast.unparse` 回源码
#     ⇒ **语法永远合法**，且反证**精确针对 CLI 的三处**。
def strip_cli_target_play_at(src):
    tree = ast.parse(src)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'run_cli':
            fn = node
            break
    if fn is None:
        return src
    n = 0
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == 'submit'):
            continue
        # 🔴 接收者必须是 `tts`（不是 `mt`）
        recv = f.value
        if not (isinstance(recv, ast.Name) and recv.id == 'tts'):
            continue
        keep = [k for k in node.keywords if k.arg != 'target_play_at']
        if len(keep) != len(node.keywords):
            n += len(node.keywords) - len(keep)
            node.keywords = keep
    if n == 0:
        return src
    return ast.unparse(tree)


def _norm(s):
    return s.replace('\r\n', '\n').replace('\r', '\n')


def load_src():
    with open(SRC, 'r', encoding='utf-8') as f:
        return _norm(f.read())


def find_cli_submit_calls(src):
    """抽出 `run_cli` 函数体里的 **`tts.submit(...)`** 调用。

    🔴 不用正则糊：先用 `ast` 定位 `run_cli` 的 FunctionDef，
    再在其子节点里找 `Call`（func 是 Attribute `submit`）⇒ 位置精确。
    🔴 **必须按接收者名筛选**：CLI 里还有 `mt.submit(...)`（**翻译**）
      ⇒ 只按 `attr == 'submit'` 会把 `mt.submit` 也算进来
      ⇒ 判据恒 FAIL（自踩坑：**判据 FAIL 先怀疑判据**）。
    """
    tree = ast.parse(src)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'run_cli':
            fn = node
            break
    if fn is None:
        return None, None
    calls = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == 'submit'):
            continue
        # 🔴 接收者必须是 `tts`（不是 `mt`）
        recv = f.value
        if not (isinstance(recv, ast.Name) and recv.id == 'tts'):
            continue
        calls.append(node)
    return fn, calls


def kw_names(call):
    return [k.arg for k in call.keywords]


def check_real(src):
    """REAL 组：CLI 路径必须传 target_play_at。"""
    res = []
    fn, calls = find_cli_submit_calls(src)
    res.append(('C1_run_cli_found', fn is not None,
                'run_cli 函数存在' if fn else '找不到 run_cli'))
    if fn is None:
        return res, []
    res.append(('C2_cli_has_submit_calls', len(calls) >= 3,
                'CLI 内 tts.submit 调用数 = %d（期望 >= 3）' % len(calls)))
    # 🔴 每一处 submit 都必须带 target_play_at
    miss = [i for i, c in enumerate(calls) if 'target_play_at' not in kw_names(c)]
    res.append(('C3_all_cli_submit_pass_target_play_at', not miss,
                '缺 target_play_at 的 submit 序号 = %s（期望 []）' % miss))
    # 🔴 会话起点墙钟
    has_wall0 = bool(re.search(r'_cli_wall0\s*=\s*time\.time\(\)', src))
    res.append(('C4_cli_session_wall0_assigned', has_wall0,
                '_cli_wall0 = time.time() 存在' if has_wall0 else '缺少会话起点墙钟'))
    # 🔴 目标墙钟计算函数
    has_fn = 'def _cli_target_wall(' in src
    res.append(('C5_cli_target_wall_fn', has_fn,
                '_cli_target_wall() 存在' if has_fn else '缺少 _cli_target_wall()'))
    # 🔴 on_final 里必须登记段号→目标墙钟
    has_reg = bool(re.search(
        r'_seg_target_wall\[\s*len\(finals\)\s*-\s*1\s*\]\s*=\s*_cli_target_wall\(',
        src))
    res.append(('C6_on_final_registers_target_wall', has_reg,
                'on_final 登记 _seg_target_wall' if has_reg else 'on_final 未登记'))
    # 🔴 登记必须发生在 submit 之前（源码顺序）
    reg_pos = src.find('_seg_target_wall[len(finals) - 1] = _cli_target_wall(')
    sub_pos = src.find('tts.submit(t, seg=len(finals) - 1')
    ok_order = (reg_pos >= 0 and sub_pos >= 0 and reg_pos < sub_pos)
    res.append(('C7_register_before_submit', ok_order,
                '登记位置 %d < submit 位置 %d' % (reg_pos, sub_pos)))
    # 🔴 GUI 侧不能被破坏（回归保护）
    res.append(('C8_gui_still_uses_target_play_at',
                'target_play_at=self._seg_target_wall.get(' in src,
                'GUI App._on_final 路径仍在传 target_play_at'))
    # 🔴 客户端 tts_service 必须支持该 kwarg（否则 TypeError）
    svc = os.path.join(REPO, 'live_caption', 'tts_service.py')
    with open(svc, 'r', encoding='utf-8') as f:
        ssvc = _norm(f.read())
    res.append(('C9_service_accepts_target_play_at',
                'target_play_at: Optional[float] = None' in ssvc,
                'tts_service.submit 签名支持 target_play_at'))
    return res, calls


def check_counterfactual(src):
    """反证组：把 CLI 三处 submit 的 `target_play_at` keyword 剥掉 ⇒ 必须 FAIL。"""
    cut = strip_cli_target_play_at(src)
    res, _ = check_real(cut)
    failed = [n for n, ok, _m in res if not ok]
    return res, failed


def main():
    src = load_src()
    real_res, _ = check_real(src)
    real_failed = [n for n, ok, _m in real_res if not ok]

    cf_res, cf_failed = check_counterfactual(src)

    # 🔴 分组计分：REAL 全 PASS + 反证组**有 FAIL**（证明判据不恒真）
    verdict = (not real_failed) and len(cf_failed) > 0

    ev = {
        'script': 'app145_app042_cli_target_wall',
        'source': SRC,
        'real_group': [{'check': n, 'pass': bool(ok), 'detail': m}
                       for n, ok, m in real_res],
        'real_failed': real_failed,
        'counterfactual_group': [{'check': n, 'pass': bool(ok), 'detail': m}
                                 for n, ok, m in cf_res],
        'counterfactual_failed': cf_failed,
        'verdict': verdict,
        'verdict_rule': 'REAL 组全 PASS 且 反证组有 FAIL',
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)

    print('REAL 组：')
    for n, ok, m in real_res:
        print('  [%s] %s -- %s' % ('PASS' if ok else 'FAIL', n, m))
    print('反证组（整块删掉 target_play_at= 后应 FAIL）：')
    for n, ok, m in cf_res:
        print('  [%s] %s -- %s' % ('PASS' if ok else 'FAIL', n, m))
    print('counterfactual_failed = %s' % cf_failed)
    print('VERDICT: %s' % ('PASS' if verdict else 'FAIL'))
    return 0 if verdict else 1


if __name__ == '__main__':
    sys.exit(main())
