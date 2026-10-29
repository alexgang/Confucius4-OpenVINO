# -*- coding: utf-8 -*-
"""APP-042 `tts_service.submit(target_play_at=...)` 的**端到端计算链**验证（app147）。

**验证什么**：从「调用方给出目标墙钟」到「命令体里出现 `speed` / `target_wall` /
`lag_s`」这条链，在**不启动 worker、不占共享锁**的前提下可测。

**怎么测**：`tts_service.TTSService` 依赖重（会起进程）⇒ 不实例化它 ⇒
改用 `ast` 抽出 `submit` 方法 + `exec` 到独立命名空间 ⇒ 用一个**假 self**
（带 `lock` / `pending` / `_inflight` / `_next_id` / `state` / `lag_s` /
`_last_speed` / `on_log`）调用 ⇒ 断言命令体内容。

**纪律**
- 🔴 不 import 被测模块顶层（`tts_service` 顶层依赖重）⇒ `ast` + `exec`。
- 🔴 `exec` 出的方法要绑到**假实例**上（否则 `self.xxx` → AttributeError）。
- 🔴 判据必须不恒真 ⇒ 带反证组。

## 判据

W1  `target_play_at=None` ⇒ 命令体**不含** `speed`/`target_wall`/`lag_s`
    （旧调用方逐字不变 ⇒ 零风险）
W2  `target_play_at` 有值 ⇒ 命令体含 `speed` / `target_wall` / `lag_s`
W3  lag 小（目标时刻=现在）⇒ `speed = 1.0`
W4  lag 大（目标时刻=60 s 前）⇒ `speed` 被限幅在 **1.1**（单次，0.1× 步长）
    且 `lag_s` 记录 ≈ 60
W5  `target_wall` 字段值 == 传入的 `target_play_at`（round 到 4 位）
W6  连续两句：第二句的 speed 受**上一句**影响（步长限制生效）
    ⇒ 用 `_last_speed` 预置 1.2 再调用 ⇒ 单次最多 +0.1
"""
import ast
import json
import os
import sys
import threading

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
SRC = os.path.join(REPO, 'live_caption', 'tts_service.py')
OUT = os.path.join(REPO, 'results', 'app',
                   'app147_app042_submit_target_wall_evidence.json')


def norm(s):
    return s.replace('\r\n', '\n').replace('\r', '\n')


def extract_submit(src=None):
    """用 `ast` 抽出 `TTSService.submit` 方法 ⇒ 编译成独立函数。

    🔴 只取方法体 ⇒ 不执行 `__init__` ⇒ 不会起任何进程。
    🔴 依赖的模块级常量/函数（`time` / `time_stretch`）由调用方注入 `ns`。
    🔴 **必须支持传入 `src`** ⇒ 否则反证组改的是文本、抽的却还是原 AST
        ⇒ **反证永远不生效** ⇒ 判据「恒真」而不自知（本轮实测踩到）。
    """
    if src is None:
        src = norm(open(SRC, encoding='utf-8').read())
    tree = ast.parse(src)
    cls = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'TTSService':
            cls = node
            break
    if cls is None:
        raise SystemExit('!! 找不到 TTSService')
    fn = None
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'submit':
            fn = node
            break
    if fn is None:
        raise SystemExit('!! 找不到 TTSService.submit')
    # 去掉 decorator（@property 之类），本方法没有
    fn.decorator_list = []
    mod = ast.Module(body=[fn], type_ignores=[])
    return mod


class FakeSelf(object):
    """`submit` 需要的最小假实例。"""

    def __init__(self):
        self.lock = threading.RLock()
        self.pending = {}
        self._inflight = set()
        self._next_id = 1
        self.state = 'ready'          # ⇒ 走 'send' 分支
        self.lag_s = 0.0
        self._last_speed = 1.0
        self.n_submitted = 0
        self.logs = []
        self.sent = []

    def on_log(self, m):
        self.logs.append(m)

    def _send(self, cmd):
        self.sent.append(cmd)
        return True

    def _update_backlog(self):
        # 🔴 `submit` 末尾会调它更新积压 ⇒ 假实现即可
        #   （不启 worker ⇒ 没有真实积压）
        return None


def const_ns(src):
    """抽出被测模块的**模块级常量**（Assign）⇒ 供 exec 出的方法使用。

    🔴 **`submit` 引用了 `MAX_TEXT_CHARS` 等模块级常量**
      ⇒ 只抽方法 ⇒ NameError ⇒ **反证组会因异常而「没识破」**
      ⇒ 判据看起来不恒真，实际是**脚本崩了**（自踩坑：**脚本崩了 ≠ 判据失效**）。
    ⇒ 修法：**逐个常量单独 exec** ⇒ 一个常量出错不影响其它。
    """
    out = {'__name__': 'tsv_mod', 'os': os, '__file__': SRC}
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        # 🔴 排除「重依赖构造器」类常量（TTSService/Path/logging）
        if (isinstance(node.value, ast.Call)
                and getattr(node.value.func, 'id', '')
                in ('TTSService', 'logging', 'Path')):
            continue
        try:
            exec(compile(ast.Module(body=[node], type_ignores=[]), SRC,
                         'exec'), out)
        except Exception:
            continue
    return out


def main():
    import time
    ts_path = os.path.join(REPO, 'live_caption', 'time_stretch.py')
    ts_ns = {'__name__': 'ts_isolated'}
    ts_src = norm(open(ts_path, encoding='utf-8').read())
    ts_tree = ast.parse(ts_src)
    keep = [n for n in ts_tree.body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import,
                              ast.ImportFrom, ast.Assign))]
    exec(compile(ast.Module(body=keep, type_ignores=[]), ts_path, 'exec'), ts_ns)

    # 🔴🔴 `submit` 引用了**模块级常量**（`MAX_TEXT_CHARS` 等）
    #   ⇒ 只抽方法 ⇒ 常量未定义 ⇒ NameError
    #   ⇒ 必须把被测模块的**模块级常量**（Assign）也注入 ns。
    import typing
    mod_ns = const_ns(norm(open(SRC, encoding='utf-8').read()))
    ns = {'__name__': 'tsv_isolated', 'time': time,
          'Optional': typing.Optional}
    for k, v in mod_ns.items():
        if k not in ('__name__', '__builtins__'):
            ns[k] = v
    # `submit` 内部 `import time_stretch as _ts` ⇒ 要能被 import 到
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))
    try:
        mod = extract_submit()
        exec(compile(mod, SRC, 'exec'), ns)
    except Exception as e:
        ev = {'script': 'app147_app042_submit_target_wall', 'verdict': False,
              'fatal': '抽取/编译失败：%r' % (e,)}
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        print('!! %r' % (e,))
        return 1

    submit = ns['submit']
    checks = []

    def ck(cid, name, ok, got, want):
        checks.append({'id': cid, 'name': name, 'pass': bool(ok),
                       'got': got, 'want': want})

    def run(target_play_at, lag_s=0.0, last_speed=1.0):
        fs = FakeSelf()
        fs.lag_s = lag_s
        fs._last_speed = last_speed
        # 🔴 `submit` **不返回命令体** ⇒ 命令体是通过 `_send(cmd)` 送出的
        #   ⇒ 从假实例的 `sent` 里取最后一条。
        submit(fs, 'hello', seg=0, lang='en',
               target_play_at=target_play_at)
        cmd = fs.sent[-1] if fs.sent else {}
        return fs, cmd

    # W1 target_play_at=None ⇒ 命令体不含加速字段
    fs, cmd = run(None)
    ck('W1', 'target_play_at=None ⇒ 命令体不含 speed/target_wall/lag_s',
       ('speed' not in cmd) and ('target_wall' not in cmd) and ('lag_s' not in cmd),
       {k: cmd.get(k) for k in ('speed', 'target_wall', 'lag_s')},
       '三者皆无')

    # W2 target_play_at 有值 ⇒ 三个字段都在
    now = time.time()
    fs, cmd = run(now)
    ck('W2', 'target_play_at 有值 ⇒ 命令体含 speed/target_wall/lag_s',
       ('speed' in cmd) and ('target_wall' in cmd) and ('lag_s' in cmd),
       {k: cmd.get(k) for k in ('speed', 'target_wall', 'lag_s')},
       '三者皆有')

    # W3 lag 小 ⇒ speed = 1.0
    fs, cmd = run(time.time())
    ck('W3', 'lag ≈ 0 ⇒ speed = 1.0', abs(cmd.get('speed', 0) - 1.0) < 1e-6,
       cmd.get('speed'), 1.0)

    # W4 lag 大 ⇒ 单次限幅到 1.1，且 lag_s ≈ 60
    fs, cmd = run(time.time() - 60.0)
    ck('W4', 'lag ≈ 60 s ⇒ 单次限幅 speed = 1.1，lag_s ≈ 60',
       abs(cmd.get('speed', 0) - 1.1) < 1e-6
       and abs(cmd.get('lag_s', 0) - 60.0) < 2.0,
       {'speed': cmd.get('speed'), 'lag_s': cmd.get('lag_s')},
       {'speed': 1.1, 'lag_s': '≈60'})

    # W5 target_wall == 传入值（round 4 位）
    tgt = time.time() - 12.3456789
    fs, cmd = run(tgt)
    ck('W5', 'target_wall == 传入的 target_play_at（round 4 位）',
       abs(cmd.get('target_wall', 0) - round(tgt, 4)) < 1e-6,
       cmd.get('target_wall'), round(tgt, 4))

    # W6 步长限制受上一句影响（_last_speed = 1.2 ⇒ 单次最多 1.3）
    fs, cmd = run(time.time() - 60.0, last_speed=1.2)
    ck('W6', '上一句 1.2 ⇒ 本句单次最多到 1.3',
       abs(cmd.get('speed', 0) - 1.3) < 1e-6,
       cmd.get('speed'), 1.3)

    # ── 反证组：判据不恒真 ──
    cf = []
    # CF1：把 submit 里的 `if target_play_at is not None:` 去掉 ⇒ W1/W2 必须 FAIL
    src = norm(open(SRC, encoding='utf-8').read())
    # 🔴 **反证注入点要选对**：
    #   原想法 = 把 `if target_play_at is not None:` 改成 `if True:`
    #   ⇒ 但 `target_play_at=None` 时 `float(None)` **抛异常**
    #   ⇒ 被 `submit` 内的 `except` 吞掉 ⇒ **命令体里根本没有 speed**
    #   ⇒ 「speed 出现了」这个判据**识破不了** ⇒ 反证无效。
    #   ⇒ 改用**等价的假实现**：`None` 时给 speed=1.0（模拟「无条件下发加速字段」）
    #     ⇒ 这是「旧调用方命令体被污染」的真实失效模式。
    _cf1_inject = '\n'.join([
        'if True:',
        '            target_play_at = (target_play_at if target_play_at is not None',
        '                             else time.time())',
    ])
    cf1_src = src.replace(
        'if target_play_at is not None:',
        _cf1_inject,
        1)
    cf1_ok = False
    try:
        ns1 = {'__name__': 'x', 'time': time,
               'Optional': __import__('typing').Optional}
        for k, v in const_ns(cf1_src).items():
            if k not in ('__name__', '__builtins__'):
                ns1[k] = v
        mod1 = extract_submit(cf1_src)
        exec(compile(mod1, SRC, 'exec'), ns1)
        s1 = ns1['submit']
        fs1 = FakeSelf()
        s1(fs1, 'hello', seg=0, lang='en', target_play_at=None)
        c1 = fs1.sent[-1] if fs1.sent else {}
        # ⇒ 现在 None 也会带 speed ⇒ W1 条件不成立 ⇒ 判据能识破
        cf1_ok = ('speed' in c1)
    except Exception as e:
        cf1_ok = False
        print('[cf1-exc] %r' % (e,))
    cf.append(('CF1', '去掉 `if target_play_at is not None` ⇒ W1 应 FAIL',
               cf1_ok, 'speed 出现在 None 调用里' if cf1_ok else 'n/a', '识破'))

    # CF2：把 `cmd['speed'] = round(_sp, 4)` 去掉 ⇒ W2/W4 应 FAIL
    cf2_src = src.replace("cmd['speed'] = round(_sp, 4)", 'pass', 1)
    cf2_ok = False
    try:
        ns2 = {'__name__': 'x', 'time': time,
               'Optional': __import__('typing').Optional}
        for k, v in const_ns(cf2_src).items():
            if k not in ('__name__', '__builtins__'):
                ns2[k] = v
        mod2 = extract_submit(cf2_src)
        exec(compile(mod2, SRC, 'exec'), ns2)
        s2 = ns2['submit']
        fs2 = FakeSelf()
        s2(fs2, 'hello', seg=0, lang='en', target_play_at=time.time())
        c2 = fs2.sent[-1] if fs2.sent else {}
        cf2_ok = ('speed' not in c2)
    except Exception as e:
        cf2_ok = False
        print('[cf2-exc] %r' % (e,))
    cf.append(('CF2', "去掉 `cmd['speed'] = ...` ⇒ W2 应 FAIL",
               cf2_ok, 'speed 缺失' if cf2_ok else 'n/a', '识破'))

    real_failed = [c['id'] for c in checks if not c['pass']]
    cf_notcaught = [cid for cid, _n, ok, _g, _w in cf if not ok]
    verdict = (not real_failed) and not cf_notcaught

    ev = {
        'script': 'app147_app042_submit_target_wall',
        'checks': checks,
        'real_failed': real_failed,
        'counterfactual': [{'id': cid, 'name': n, 'caught': bool(ok),
                            'got': g, 'want': w}
                           for cid, n, ok, g, w in cf],
        'counterfactual_not_caught': cf_notcaught,
        'verdict': verdict,
        'verdict_rule': 'REAL 组全 PASS 且 反证组的假实现全部被识破',
        'note': '不启 worker、不占共享锁；仅验证命令体计算链',
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)

    for c in checks:
        print('  [{}] {} {} -- got={} want={}'.format(
            'PASS' if c['pass'] else 'FAIL', c['id'], c['name'],
            c['got'], c['want']))
    print('反证组：')
    for cid, n, ok, g, w in cf:
        print('  [{}] {} -- got={} want={}'.format(
            'PASS' if ok else 'FAIL', cid, n, g, w))
    print('counterfactual_not_caught = {} （应为空）'.format(cf_notcaught))
    print('VERDICT: {}'.format('PASS' if verdict else 'FAIL'))
    return 0 if verdict else 1


if __name__ == '__main__':
    sys.exit(main())
