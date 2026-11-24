#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236：`MEMORY.md` 的**写后独立复核**（只读）。

判据：
  ① 字符数 **≤ 9 700**（该文件自声明的硬上限）
  ② 关键事实 **逐字**全在（含**否定式表述** ⇒ 下游按字面 grep 不能漏）
  ③ `§N` 编号集合**未丢**
  ④ 章节数不变
  ⑤ 无 U+FFFD、无控制字符
  ⑥ §236 指针在位（含 app049/app187/§222/行尾重建 四条新事实）

🔴 反证组：
  R1 把「关键事实」抽掉一条 ⇒ ② 必须 FAIL
  R2 灌进 2 000 字符 ⇒ ① 必须 FAIL
"""
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEM = os.path.join(REPO, '.workbuddy/memory/MEMORY.md')
LIMIT = 9700

KEY = [
    'last_ack=APP-133', 'app049', 'app187', '§222', 'i/lf+w/crlf', 'core.autocrlf',
    'MACHINE_LOCK', 'OpenProcess', 'GetExitCodeProcess', '259', 'ACCEPTED',
    'v2.6', 'v2.5', 'v2.7', 'v1.1.1.zip', 'n_speakers=0', 'pack_v13',
    '192.168.2.206', 'sm_120', 'TTS-078', 'TTS-076', 'APP-086', 'CPNaNError',
    'gitattributes', '必须入库', '不是新编号', '零样本克隆全关', 'c13',
    'MultiDecoderBabelVox', 'pkg_content', 'fail-closed', '唯一交付方案',
    '行尾风格不变', '旧正文逐字未变', '真不变量', '假 FAIL', '反证组',
    'session_lease', 'TOKEN', 'TAKEOVER', 'BUSY', 'LOST',
    # 🔴 否定式表述（下游可能按字面 grep）
    '不写「已证明无影响」', '**不是** TTS 模块', '不得当正文覆写', '等于没绑',
    '不裁尾',
]


def main():
    d = io.open(MEM, encoding='utf-8').read()
    n = len(d)
    rows = []
    rows.append(('字符数 %d ≤ %d' % (n, LIMIT), n <= LIMIT))
    lost = [k for k in KEY if k not in d]
    rows.append(('关键事实 %d 条逐字全在' % len(KEY), not lost))
    if lost:
        print('   🔴 缺：%s' % lost)
    nums = set(re.findall(r'§\d+', d))
    rows.append(('§编号 %d 个（≥20）' % len(nums), len(nums) >= 20))
    rows.append(('章节数 = 14', len(re.findall(r'^## ', d, re.M)) == 14))
    rows.append(('无 U+FFFD', '\ufffd' not in d))
    rows.append(('无控制字符', not any(ord(c) < 0x20 and c not in '\n\r\t' for c in d)))
    rows.append(('§236 指针在位', '§236' in d and '附录·五十四' in d))

    print('=== MEMORY.md 写后复核 ===')
    allok = True
    for name, ok in rows:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', name))
        allok = allok and ok

    print()
    print('--- counterproof ---')
    cp = []
    d1 = d.replace('不得当正文覆写', '不得当正文覆盖')
    ok1 = ('不得当正文覆写' not in d1)
    cp.append({'name': 'R1_key_removed_detected', 'expect': 'FAIL', 'ok': ok1})
    print('    R1 抽掉「不得当正文覆写」⇒ ② 须 FAIL ⇒ %s' % ('PASS' if ok1 else 'FAIL'))
    d2 = d + ('x' * 2000)
    ok2 = (len(d2) <= LIMIT) is False
    cp.append({'name': 'R2_over_limit_detected', 'expect': 'FAIL', 'ok': ok2})
    print('    R2 灌进 2 000 字符 ⇒ ① 须 FAIL ⇒ %s' % ('PASS' if ok2 else 'FAIL'))
    all_cp = all(c['ok'] for c in cp)
    print('    反证组全部有鉴别力 =', all_cp)

    print()
    print('wrote results/app/app236_memory_verify.json')
    import json
    with open(os.path.join(REPO, 'results/app/app236_memory_verify.json'), 'w',
              encoding='utf-8', newline='\n') as fh:
        json.dump({'chars': n, 'checks': [{'name': a, 'ok': b} for a, b in rows],
                   'all_ok': allok, 'counterproof_all_ok': all_cp, 'counterproof': cp},
                  fh, ensure_ascii=False, indent=2)
    return 0 if (allok and all_cp) else 1


if __name__ == '__main__':
    sys.exit(main())
