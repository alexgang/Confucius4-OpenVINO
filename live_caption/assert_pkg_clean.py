r"""assert_pkg_clean.py — **建包阶段**的交付洁净度闸门（APP-077 ① / APP-078 ③）。

## 为什么必须有这道闸（根因，APP-078 实测）
`pack_v13.py` 打 zip 时用 `pkg_exclude.iter_package_files()` ⇒ **zip 干净**；
但 `app206_app057_v20_stage.py` / `app221_app061_v22_build.py` 建**包目录**
时用 `os.walk` **整目录复制、完全不调用 pkg_exclude**
⇒ v2.0/v2.1/v2.2 三个**安装目录**里都带着：
  * `python/Lib/site-packages/babelvox/data/speakers/{cindy,lou,phil,steve}.{json,npy}`
    （第三方音色，APP-078）
  * `ext/bridge_token.txt`（固定鉴权 token，APP-077 ①）
用户从**目录**启动（桌面 .lnk 指向的正是目录）⇒ 两样都会被加载
⇒ 只看 zip 会得出「不违规」的错误结论。

## 用法（v2.3 起，建包脚本复制完目录后立刻调用）
```
python live_caption/assert_pkg_clean.py <新包目录>       # 检查，违规 ⇒ exit 1
```
🔴 **只检查，不删除**：本模块绝不修改任何已发布目录；要修只能在
   **新建包目录**里不复制这些文件（构建脚本侧改），或由人工确认后处理。
🔴 对 v2.0/v2.1/v2.2 等旧目录调用会得到 FAIL ⇒ 这是**预期**
   （如实报告历史违规，不是让你去原地删）。

## 判据（APP-081 第 3 点：单一事实来源）
🔴 **由 `v23_preset_only.PKG_EXCLUDE_PATTERNS` 驱动**，覆盖全部 6 类：
  ① `bridge_token.txt`（APP-077）② babelvox 8 个示例音色（APP-078）
  ③ 克隆音色 `voices/*clone*.wav/npz` ④ 克隆产物目录 `v23_clone*/`
  ⑤ 测试 wav `*_test.wav` ⑥ `*_clone_test.wav`。
  独立运行（同目录拿不到 `v23_preset_only` 时）回落到内置同款 5 条正则，
  ⇒ 绝不出现「规则表有、闸门查不到」的覆盖缺口。
* 不误伤：`preset_A.wav`、babelvox 库代码、tokenizer 配置
"""
from __future__ import annotations

import os
import re
import sys

# 兼容旧判据脚本（results/app/_app326）的导入；**scan() 本身不再依赖它们**，
# 否则「改 TOKEN_RE 做反证」就碰不到被测对象，会变成恒真判据。
TOKEN_RE = re.compile(r'^bridge_token\.txt$', re.I)
SPEAKERS_REL = os.path.join('python', 'Lib', 'site-packages', 'babelvox',
                            'data', 'speakers')
VOICE_RE = re.compile(r'^(cindy|lou|phil|steve)\.(json|npy)$', re.I)

#: 独立运行时的兜底规则（与 v23_preset_only.PKG_EXCLUDE_PATTERNS 逐字一致）。
_FALLBACK_EXCLUDE_PATTERNS = [
    r'(?i)(^|/)bridge_token\.txt$',
    r'(?i)python/Lib/site-packages/babelvox/data/speakers/(cindy|lou|phil|steve)\.(json|npy)$',
    r'(?i)(^|/)voices/.*clone.*\.(wav|npz)$',
    r'(?i)(^|/)v23_clone[^/]*/.*\.(wav|npz)$',
    r'(?i)(^|/).*(_clone_test|_test)\.wav$',
]


def load_exclude_rules():
    """返回 [(compiled_re, label)]；优先取 v23_preset_only 的规则表。"""
    try:
        from v23_preset_only import PKG_EXCLUDE_PATTERNS as _pats
        src = 'PKG_EXCLUDE_PATTERNS'
    except Exception:
        _pats = _FALLBACK_EXCLUDE_PATTERNS
        src = 'FALLBACK'
    return [(re.compile(p), '%s: %s' % (src, p)) for p in _pats]


EXCLUDE_RULES = load_exclude_rules()


def scan(pkg_root: str) -> list:
    """返回违规项列表 [(relpath, reason, bytes)]；空列表 = 干净。

    APP-081 第 3 点：对**每个文件的 posix 相对路径**跑 EXCLUDE_RULES，
    命中即记违规并附命中的规则（不再是硬编码的两类文件名判断）。
    """
    bad = []
    seen = set()
    for dp, _dn, fns in os.walk(pkg_root):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, pkg_root).replace('\\', '/')
            for cre, label in EXCLUDE_RULES:
                if cre.search(rel):
                    key = (rel, label)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        sz = os.path.getsize(full)
                    except OSError:
                        sz = 0
                    bad.append((rel, label, sz))
    return bad


def assert_clean(pkg_root: str) -> int:
    if not os.path.isdir(pkg_root):
        print('!! 包目录不存在：%s' % pkg_root)
        return 2
    bad = scan(pkg_root)
    if not bad:
        print('[PASS] %s 交付洁净度闸门：0 违规' % pkg_root)
        return 0
    print('[FAIL] %s 交付洁净度闸门：%d 项违规' % (pkg_root, len(bad)))
    for rel, why, sz in bad:
        print('   - %s  (%s, %d B)' % (rel, why, sz))
    print('⇒ 该目录**不可交付**；请在建包阶段就剔除（不要原地删旧包）。')
    return 1


if __name__ == '__main__':
    raise SystemExit(assert_clean(sys.argv[1] if len(sys.argv) > 1 else '.'))
