# -*- coding: utf-8 -*-
"""更新 STATUS §169 里「引用路径闸门」那一行的**实测数字**。

🔴 原因：本轮先写 §169、**后**又给 `assert_status_citations.py` 加了
「documented（已如实记录的错误引用）」分类 ⇒ 重跑后数字变了
（引用数 27→35、可定位 26→34、归档件 14→13、坏引用仍 0）⇒ 表格必须同步。

**只改这一行**（唯一命中断言）⇒ 其余正文一字不动。
"""
import json
import os

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CIT = os.path.join(REPO, 'results', 'app', 'status_citations_sweep_20261110.json')
WIN = os.path.join(REPO, 'results', 'app', 'app400_window_samesource_check.json')
CMT = os.path.join(REPO, 'results', 'app', 'app401_comment_only_proof.json')

cit = json.load(open(CIT, encoding='utf-8'))
win = json.load(open(WIN, encoding='utf-8'))
cmt = json.load(open(CMT, encoding='utf-8'))

raw = open(STATUS, 'rb').read()
text = raw.decode('utf-8')
nl = '\r\n' if '\r\n' in text else '\n'
body = text.replace('\r\n', '\n')

OLD = ('| `live_caption/assert_status_citations.py` | **STATUS 引用产物路径必须能在磁盘上定位**'
       '（把 APP-093 ②(d) 机械化） | 活文档 **27 条引用 / 26 条可定位 / 0 条坏引用 ⇒ PASS**；'
       '归档件 14 条旧笔误**只登记不判 FAIL**（归档件是冻结的历史正文） | '
       '`results/app/status_citations_sweep_20261110.json`（18845 B） |')

NEW = ('| `live_caption/assert_status_citations.py` | **STATUS 引用产物路径必须能在磁盘上定位**'
       '（把 APP-093 ②(d) 机械化） | 活文档 **%d 条引用 / %d 条可定位 / %d 条坏引用 ⇒ PASS**；'
       '其中 **%d 条属「已如实记录的错误引用」**（同一行已给出正确路径 ⇒ 不判 FAIL）；'
       '归档件 %d 条旧笔误**只登记不判 FAIL**（归档件是冻结的历史正文） | '
       '`results/app/status_citations_sweep_20261110.json`（%d B） |'
       % (cit['n_cited_unique_live'], cit['n_ok_live'], cit['n_bad_live'],
          cit['n_documented_live'], cit['n_archive_findings'],
          os.path.getsize(CIT)))

assert body.count(OLD) == 1, 'anchor count = %d' % body.count(OLD)
new_body = body.replace(OLD, NEW, 1)

# 同步更新「最近更新」里那句（引用路径闸门的数字）
OLD_RU = ('新增 3 道静态闸门（引用路径可定位 26/26 PASS、窗长同源+兜底配套 8/8 PASS、'
           '注释-only AST 证明）')
assert OLD_RU in new_body, '最近更新行未命中'
NEW_RU = ('新增 3 道静态闸门（引用路径可定位 %d/%d PASS、窗长同源+兜底配套 %d/%d PASS、'
          '注释-only AST 证明）'
          % (cit['n_ok_live'], cit['n_ok_live'] + cit['n_bad_live'],
             win['n_pass'], win['n_pass'] + win['n_fail']))
new_body = new_body.replace(OLD_RU, NEW_RU, 1)

# 反向还原校验
def reconstruct(x):
    x = x.replace(NEW, OLD, 1)
    x = x.replace(NEW_RU, OLD_RU, 1)
    return x

assert reconstruct(new_body) == body, '反向还原 != 旧全文'
assert '\r\n' not in new_body
nb = len(new_body.encode('utf-8'))
assert nb <= 40000, nb
assert len(new_body.split('\n')) <= 300

tmp = STATUS + '.tmp'
with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_body)
os.replace(tmp, STATUS)

after = open(STATUS, 'rb').read().decode('utf-8')
assert after == new_body, '写后逐字节复核不一致'
print(json.dumps({'bytes': nb, 'lines': len(new_body.split('\n')),
                  'n_ok_live': cit['n_ok_live'], 'n_bad_live': cit['n_bad_live'],
                  'n_documented_live': cit['n_documented_live'],
                  'n_archive_findings': cit['n_archive_findings'],
                  'reverse_restore_ok': True}, ensure_ascii=False, indent=2))
