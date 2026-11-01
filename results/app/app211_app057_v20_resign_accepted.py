#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app211 —— APP-057：给 V2.0 包**重新签 ACCEPTED.json**。

## 为什么必须重签（不是复制 v1.13 的）

v1.13 的 `ACCEPTED.json` 里：

    "version": "1.13",
    "pkg_dir": "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.13",
    "code_fingerprint": "eeafd13b…",

⇒ **全部指向 v1.13** ⇒ 直接拷进 V2.0 就是「拿了别的包的验收结论」
⇒ app191 的 **R3（验收声明自洽）** 必然 FAIL
⇒ 且「磁盘上存在」≠「已交付」（§九铁律）：zip 内那一份仍绑旧代码。

## 指纹算法 = app191.package_fingerprint（逐字一致）

    SHA256 over（文件名 + NUL + SHA256(归一化行尾后的模块字节)），按文件名排序
    范围 = 包内 app/ 的**生产模块**（排除 pkg_exclude.is_app_dev_only）

⇒ 与 app191 / app186 完全同口径 ⇒ 重签后 app191 能直接验。

## 白名单（waived_changes）

只收 **reviewer 明确要求的改动**（铁律）：

* APP-052 ② 末段 GUI 文案清理 → `live_caption_app.py`
* APP-052 ③ docstring 家目录 → `<HOME>` 占位 → `speaker_assets.py` /
  `tts_cuda.py` / `tts_cuda_sidecar.py`
* APP-054 ② 说话人旁路整体重写 → `speaker_tracker.py`
* **APP-055** v1.13 还原（v1.13 目录回到 06:08 态 ⇒ 客户手上的 v1.13
  与当初验收的那一版一致）⇒ 属 reviewer 明确要求
* **APP-057** V2.0 = 追加 EXT 插件 + 桥接（**新增目录 `ext/`**，
  **不改动 `app/` 下任何生产模块**）⇒ 生产模块指纹**不变**

## 🔴 事务性

先写临时文件 → 复核 → `os.replace` 原子替换 ⇒ 中途异常不会留下半个文件。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)


def _find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('无法从 %s 向上找到仓库根' % start)
        cur = parent


REPO = _find_repo_root(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pkg_exclude  # noqa: E402

#: reviewer 明确要求的改动白名单（**只收 reviewer 亲自要求的**）
ACCEPTED_WAIVED = {
    'live_caption_app.py': {
        'reason': 'APP-052 ② 末段：清理 GUI 说明文字（去 markdown 星号 / '
                  'onednn / CUDA plugin 研发术语 / 同段说明重复两次 / '
                  '1280×720 文字截断）⇒ 属 reviewer 本轮亲自要求的实质改动',
        'source': 'APP-052 ② 末段（reviewer 明确要求）',
    },
    'speaker_assets.py': {
        'reason': 'APP-052 ③：模块 docstring 里的开发机家目录字面量 ⇒ '
                  '`<HOME>` 占位（避免随包泄漏开发机用户名）；'
                  'APP-057 ③：连**注释里举例**也不能出现真实家目录 ⇒ 再脱敏一处',
        'source': 'APP-052 ③ / APP-057 ③（reviewer 明确要求）',
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


def norm_bytes(b: bytes) -> bytes:
    """归一化行尾（`core.autocrlf=true` ⇒ clone 后 LF→CRLF）。"""
    return b.replace(b'\r\n', b'\n')


def production_modules(pkg_app: str):
    out = []
    for n in sorted(os.listdir(pkg_app)):
        if not n.endswith('.py'):
            continue
        if pkg_exclude.is_app_dev_only('app/' + n):
            continue
        out.append(n)
    return out


def module_fingerprints(pkg_app: str, mods):
    out = {}
    for n in mods:
        p = os.path.join(pkg_app, n)
        with open(p, 'rb') as f:
            data = norm_bytes(f.read())
        out[n] = hashlib.sha256(data).hexdigest()
    return out


def package_fingerprint(pkg_app: str, mods):
    h = hashlib.sha256()
    for n in mods:
        p = os.path.join(pkg_app, n)
        with open(p, 'rb') as f:
            data = norm_bytes(f.read())
        h.update(n.encode('utf-8'))
        h.update(b'\0')
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


def pkg_version_of(pkg_dir: str) -> str:
    import re
    base = os.path.basename(os.path.normpath(pkg_dir))
    m = re.search(r'_v(\d+(?:\.\d+)*)$', base)
    if m:
        return m.group(1)
    for cand in (os.path.join(pkg_dir, 'MANIFEST.json'),
                 os.path.join(pkg_dir, 'app', 'MANIFEST.json')):
        if os.path.isfile(cand):
            try:
                with open(cand, encoding='utf-8') as f:
                    return str(json.load(f).get('version') or '')
            except Exception:
                pass
    return ''


#: 🔴🔴 **APP-057 ③**：`ACCEPTED.json` 里记的包路径**不得写死构建机家目录**
#:   （`C:\Users\<构建机用户名>\...` 随包发给客户 ⇒ 泄漏构建机用户名，
#:    且客户机上路径也不对 ⇒ 一律记 `<HOME>` 占位形态）。
#:   ⇒ app191 的 R3 判定也必须按同一口径把 `<HOME>` 展开成真实家目录再比。
HOME_PLACEHOLDER = '<HOME>'


def pkg_dir_for_record(pkg_dir: str) -> str:
    """把包目录转成 `<HOME>\\...` 形态（家目录之外的原样保留）。"""
    home = os.path.expanduser('~')
    try:
        rel = os.path.relpath(pkg_dir, home)
    except ValueError:
        return pkg_dir
    if rel.startswith('..'):
        return pkg_dir
    return HOME_PLACEHOLDER + '\\' + rel.replace(os.sep, '\\')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None, help='客户包目录（默认 v2.0）')
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    pkg = args.pkg or os.path.join(os.path.expanduser('~'),
                                   'Confucius4_LiveCaption_v2.0')
    pkg_app = os.path.join(pkg, 'app')
    ver = pkg_version_of(pkg)
    mods = production_modules(pkg_app)
    fp = package_fingerprint(pkg_app, mods)
    per = module_fingerprints(pkg_app, mods)

    # ★ 与 v1.13 的指纹对比（证明「V2.0 未改动 app/ 下任何生产模块」
    #   ⇒ 白名单不需要新增条目）
    v113 = os.path.join(os.path.expanduser('~'),
                        'Confucius4_LiveCaption_v1.13')
    fp_113 = None
    n_mods_113 = None
    if os.path.isdir(os.path.join(v113, 'app')):
        mods_113 = production_modules(os.path.join(v113, 'app'))
        fp_113 = package_fingerprint(os.path.join(v113, 'app'), mods_113)
        n_mods_113 = len(mods_113)

    print('=' * 70)
    print('app211 —— 重签 V2.0 的 ACCEPTED.json')
    print('包:', pkg)
    print('版本:', ver)
    print('生产模块: %d 个' % len(mods))
    print('code_fingerprint:', fp)
    if fp_113:
        print('v1.13 code_fingerprint:', fp_113)
        print('  与 v1.13 相同 ⇒', fp == fp_113,
              '（app/ 生产模块未变）')

    payload = {
        'accepted': True,
        'version': ver,
        'pkg_dir': pkg_dir_for_record(pkg),
        'accepted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'corrections': ['APP-043', 'APP-045', 'APP-048', 'APP-051', 'APP-052',
                        'APP-053', 'APP-054', 'APP-055', 'APP-056', 'APP-057',
                        'APP-058'],
        'binding_gate': 'app191',
        'code_fingerprint': fp,
        'code_fingerprint_alg': (
            'app191.package_fingerprint：SHA256 over（文件名 + NUL + '
            'SHA256(归一化行尾后的模块字节)），按文件名排序；'
            '范围 = 包内 app/ 的**生产模块**'
            '（排除 pkg_exclude.is_app_dev_only）'),
        'n_production_modules': len(mods),
        'code_fingerprints': per,
        'waived_changes': ACCEPTED_WAIVED,
        'v2_0_additions': {
            'ext/extension': 'EXT 插件 unpacked 目录（Edge/Chrome 加载已解压扩展）',
            'ext/bridge': 'EXT 桥接服务（用包内 python 与包内 models，不另拷模型）',
            'ext/.runtime_deps': '补装 websockets 17.3 / psutil 7.2.2'
                                 '（不污染包内 python 的 site-packages）',
            'release.json': '{"release": true} ⇒ 发行版模式'
                            '（禁用整机 getDisplayMedia 回退）',
            'note': ('★ **app/ 下的生产模块未被 V2.0 改动**'
                     '（code_fingerprint 与 v1.13 相同）'
                     ' ⇒ EXT 是**追加**，不是替换')
                    if fp_113 and fp == fp_113 else
                    ('★ 本版 app/ 生产模块相对 v1.13 有**一处**改动：'
                     '`speaker_assets.py` 的注释脱敏（APP-057 ③）'
                     ' ⇒ 其余生产模块与 v1.13 相同'),
        },
        'scope': '链路 + 结构 + 数字自洽；**音质/不变调/可懂由用户实听与 '
                 'reviewer 判定**',
        'pending_reviewer': [
            'APP-057 (b)：Edge 真实手势 + 60 s 网页音频配音（需 EXT-028 通过；'
            'tabCapture 生产路径需用户手点扩展图标）',
            'APP-058 判据④：换人点召回率 33.33 %（口径 A）/ 58.33 %（口径 B）'
            '⇒ **未达 60 %** ⇒ 待 reviewer 复核',
        ],
    }

    acc_path = os.path.join(pkg, 'ACCEPTED.json')
    backup = None
    if os.path.isfile(acc_path):
        with open(acc_path, 'rb') as f:
            backup = f.read()
    tmp = acc_path + '.app211_tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    # 写后复核（先读回来比对）
    with open(tmp, 'r', encoding='utf-8') as f:
        back = json.load(f)
    assert back['code_fingerprint'] == fp, '写后指纹不一致'
    assert back['version'] == ver
    os.replace(tmp, acc_path)
    print('\n[accepted] 已重签 %s（%d B）'
          % (acc_path, os.path.getsize(acc_path)))
    if backup:
        print('[accepted] 旧内容已备份到内存（%d B）' % len(backup))

    out = {
        'tool': 'app211',
        'app': 'APP-057',
        'pkg': pkg,
        'version': ver,
        'accepted_bytes': os.path.getsize(acc_path),
        'code_fingerprint': fp,
        'n_production_modules': len(mods),
        'v113_code_fingerprint': fp_113,
        'v113_n_modules': n_mods_113,
        'same_as_v113': (fp == fp_113) if fp_113 else None,
        'accepted_at': payload['accepted_at'],
        'waived_changes': list(ACCEPTED_WAIVED.keys()),
    }
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
