# -*- coding: utf-8 -*-
"""_app427 —— APP-097 §2-4：把 `_SEC_PER_CHAR` 的 6 种新语言**实测校准**回填到开发树。

## 依据（reviewer 原文，status/app/CORRECTIONS_APP.md → APP-097）
- §1.1：「`_SEC_PER_CHAR`：给 6 种新语言加上每字符秒数（**先用 en 的 0.07 当初值**，
  **按第 2 节第 4 条实测校准**）。」
- §2.4：「每种语言报「合成时长 ÷ 字符数」的 p50，**用它定 `_SEC_PER_CHAR`**。
  再报「译文语音时长 ÷ 英文源段时长」的 p50，给 reviewer 判断新语言要不要像中文那样
  设一个 >1× 的倍率地板。**倍率默认值不改**，只报数字。」

⇒ `_SEC_PER_CHAR` 本体**要回填**（「用它定」）；「只报数字」约束的是**倍率地板**（另一件事）。

## 数据源（已落盘、已被 §167 引用）
`results/app/app326_app097_lang_out/tts.json` ⇒ `per_lang.<lang>.<voice>.rows[]`
⇒ 每行 `out_dur_s`（合成音频秒数）/ `n_chars`（非空白字符数）⇒ 每字符秒数。

## 取值规则（保守：守卫阈值只可能不变或变松，绝不变紧）
    value[lang] = ceil3( max( preset_p50, clone_p50 ) )
- 两种音色**取较大者** ⇒ 失控守卫（RUNAWAY `max(3×est, est+8)`）阈值不会比校准前更紧
  ⇒ 绝不会**更容易误杀**正常长句（校准前 0.07 对 ru 低估约 18 %）。
- `ceil3` 向上取整到 3 位小数 ⇒ 仍然只可能高估真实语速（宁高不低）。
- zh/en/ja/ko **不动**（reviewer 只要求校准这 6 种新语言；APP-030② 的参考值保持不变）。

## 纪律
- 只改**开发树** `live_caption/tts_engine.py`；**不碰任何客户包目录**（APP-055）。
- **精确字符串替换 + 唯一命中断言**（不用整文件重写）。
- 改后用 `ast` 证明：① 6 个新值已变 ② zh/en/ja/ko 逐字未变 ③ 表里只有这 10 个键。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SRC = os.path.join(REPO, 'live_caption', 'tts_engine.py')
EVID = os.path.join(REPO, 'results', 'app', 'app427_sec_per_char_calibration.json')

NEW_LANGS = ('de', 'fr', 'es', 'pt', 'it', 'ru')
KEEP = {'zh': 0.25, 'ja': 0.15, 'ko': 0.18, 'en': 0.07}

OLD_COMMENT = (
    '#: \U0001f534\U0001f534\U0001f533 **APP-097①**：新增的 6 种语言**先用 en 的 0.07 当初值**，\r\n'
    '#:    真实值由 APP-097 §2-4 的「合成时长 ÷ 字符数」p50 **实测校准**后回填。\r\n'
    '#:    ⚠️ 初值偏小 ⇒ 失控守卫阈值偏低 ⇒ **可能误杀正常长句**\r\n'
    '#:    ⇒ 实测校准前，这 6 种语言**只用于目标语言选择**，不用于长文本批量合成。\r\n'
)

NEW_COMMENT = (
    '#: \U0001f534\U0001f534\U0001f533 **APP-097①＋§2-4**：6 种新语言的每字符秒数**已按 §2-4 实测校准回填**\r\n'
    '#:    （初值 en=0.07 → 实测值；来源 `results/app/app326_app097_lang_out/tts.json`\r\n'
    '#:      ⇒ `per_lang.<lang>.<voice>.rows[].out_dur_s / n_chars` 的 p50）。\r\n'
    '#:    \U0001f534 **取值规则 = max(preset_p50, clone_p50) 向上取整到 3 位小数**：\r\n'
    '#:       两种音色**取较大者** ⇒ 失控守卫（RUNAWAY `max(3×est, est+8)`）阈值\r\n'
    '#:       **只可能不变或变松、绝不变紧** ⇒ 绝不会比校准前更容易误杀正常长句。\r\n'
    '#:    ⚠️ zh/en/ja/ko **保持 APP-030② 的参考值不变**（reviewer 只要求校准这 6 种新语言）。\r\n'
    '#:    ⚠️ **倍率地板**（新语言是否照 zh 设 >1× 倍率）**未改**：reviewer §2-4 明文\r\n'
    '#:       「倍率默认值不改，只报数字」⇒ 实测 ratio_p50 已落盘，等 reviewer 裁定。\r\n'
)

OLD_TABLE = (
    "_SEC_PER_CHAR = {\r\n"
    "    'zh': 0.25, 'ja': 0.15, 'ko': 0.18, 'en': 0.07,\r\n"
    "    # \U0001f534 APP-097①：6 种新语言（初值＝en，待实测校准）\r\n"
    "    'de': 0.07, 'fr': 0.07, 'es': 0.07,\r\n"
    "    'pt': 0.07, 'it': 0.07, 'ru': 0.07,\r\n"
    "}\r\n"
)

NEW_TABLE = (
    "_SEC_PER_CHAR = {\r\n"
    "    'zh': 0.25, 'ja': 0.15, 'ko': 0.18, 'en': 0.07,\r\n"
    "    # \U0001f534 APP-097①＋§2-4：6 种新语言 = §2-4 实测校准值（max(preset,clone) p50 向上取整）\r\n"
    "    'de': 0.073, 'fr': 0.070, 'es': 0.085,\r\n"
    "    'pt': 0.080, 'it': 0.081, 'ru': 0.083,\r\n"
    "}\r\n"
)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def table_of(src: str) -> dict:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == '_SEC_PER_CHAR':
                    return ast.literal_eval(node.value)
    raise AssertionError('_SEC_PER_CHAR not found')


def main() -> None:
    raw = open(SRC, 'rb').read()
    before_sha = sha256(raw)
    src = raw.decode('utf-8')

    # ── 0. 旧表必须是「占位初值」形状（防重复执行 / 防夹具错） ──
    old_tbl = table_of(src)
    assert old_tbl.get('de') == 0.07 and old_tbl.get('ru') == 0.07, old_tbl
    for k, v in KEEP.items():
        assert old_tbl[k] == v, (k, old_tbl[k])

    # ── 1. 从已落盘的 §2-3 证据复算期望值（不手抄数字） ──
    tts = json.load(open(os.path.join(
        REPO, 'results', 'app', 'app326_app097_lang_out', 'tts.json'),
        encoding='utf-8'))
    import statistics
    import math
    per = {}
    for lang in NEW_LANGS:
        p50 = {}
        for voice in ('preset', 'clone'):
            rows = tts['per_lang'][lang][voice]['rows']
            ratios = [r['out_dur_s'] / r['n_chars'] for r in rows if r.get('n_chars')]
            p50[voice] = statistics.median(ratios)
        mx = max(p50['preset'], p50['clone'])
        per[lang] = {
            'preset_p50': round(p50['preset'], 6),
            'clone_p50': round(p50['clone'], 6),
            'max_p50': round(mx, 6),
            'value': math.ceil(mx * 1000) / 1000.0,
        }
    expect = {k: per[k]['value'] for k in NEW_LANGS}
    assert expect == {'de': 0.073, 'fr': 0.07, 'es': 0.085,
                      'pt': 0.08, 'it': 0.081, 'ru': 0.083}, expect
    # 硬编码在 NEW_TABLE 里的值必须 == 复算值（防手抄漂移）
    for lang, v in expect.items():
        assert ("'%s': %s" % (lang, ('%.3f' % v))) in NEW_TABLE, (lang, v)

    # ── 2. 精确字符串替换 + 唯一命中断言 ──
    assert src.count(OLD_COMMENT) == 1, 'comment anchor count != 1'
    assert src.count(OLD_TABLE) == 1, 'table anchor count != 1'
    src2 = src.replace(OLD_COMMENT, NEW_COMMENT).replace(OLD_TABLE, NEW_TABLE)
    assert src2 != src

    # ── 3. 改后 AST 证明 ──
    new_tbl = table_of(src2)
    assert set(new_tbl) == set(KEEP) | set(NEW_LANGS), sorted(new_tbl)
    for k, v in KEEP.items():
        assert new_tbl[k] == v, ('KEEP changed', k, new_tbl[k])
    for k in NEW_LANGS:
        assert new_tbl[k] == expect[k], (k, new_tbl[k], expect[k])
        assert new_tbl[k] >= 0.07, ('value must not go below placeholder', k)
    # 行尾风格未破：CRLF 文件里**不允许出现裸 LF**。
    # ⚠️ 不能断言「CRLF 个数不变」——新注释行数与旧注释不同 ⇒ 个数本就会变
    #    （踩过一次：自己写的断言把合法改动判成 FAIL ⇒ 修正为「无裸 LF」这个真正的不变量）。
    def bare_lf(text: str) -> int:
        return text.count('\n') - text.count('\r\n')
    assert bare_lf(src) == 0 and bare_lf(src2) == 0, 'bare LF introduced'

    # ── 4. 落盘（原子替换） ──
    out = src2.encode('utf-8')
    tmp = SRC + '.app427.tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
    os.replace(tmp, SRC)

    after = open(SRC, 'rb').read()
    assert sha256(after) != before_sha
    assert table_of(after.decode('utf-8')) == new_tbl

    ev = {
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'app': 'APP-097 §2-4',
        'action': 'backfill _SEC_PER_CHAR for the 6 new languages (dev tree only)',
        'src_file': 'live_caption/tts_engine.py',
        'evidence_source': 'results/app/app326_app097_lang_out/tts.json',
        'rule': 'value = ceil3(max(preset_p50, clone_p50)) of out_dur_s/n_chars',
        'unchanged_langs': KEEP,
        'per_lang': per,
        'before_sha256': before_sha,
        'after_sha256': sha256(after),
        'before_bytes': len(raw),
        'after_bytes': len(after),
        'pkg_touched': False,
        'ratio_floor_changed': False,
    }
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print(json.dumps(ev, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
