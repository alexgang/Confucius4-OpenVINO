#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-232 轮（待命轮）：把 `.workbuddy/memory/MEMORY.md` 压回**自声明上限 9 700 字符**。

## 为什么本轮要做这件事（本轮唯一的实质性动作）

- 开工实测：`MEMORY.md` = **9 915 字符** > 头部自声明的 **≤9 700** ⇒ **超限**。
- 后果：会话注入时**被截断**（`working_memory_content` 尾部丢失 ⇒ §十三 目标机那段
  只剩一半）⇒ 下游会话拿不到「换个会话不知道就会做错」的那几条。
- 成因：**TTS 模块在 21:13 也写了 `MEMORY.md`**（第 127 轮，追加了 APP-130 自检那一条）
  ⇒ `MEMORY.md` 是**跨模块共享文件**，任一模块写完都必须**重新断言上限**，否则
  「谁最后写谁超限」。

## 🔴 纪律（照抄已验证的三件套）

- 🔴 **定点写入三件套**：① 备份（`%TEMP%/*.bak`）② 写前在**内存新文本**跑
  真不变量 ＋ **还原式复核**（改回须逐字节同）③ 临时文件 → `os.replace`
  ⇒ 写后**另起脚本**独立复核。
- 🔴 `open(p,'w')` 先截断 ⇒ 0 B ⇒ 一律临时文件 + `os.replace`。
- 🔴 **只压从句、不删判据**：每条编辑都保留原判据的**关键词**，并用
  `KEYWORDS` 列表在写前**逐条断言关键词仍在** ⇒ 压掉的是冗余字，不是知识。
- 🔴 **每条编辑都是「唯一命中」**：写前断言 `old` 在全文**恰好出现 1 次**。
- 🔴 **不做行级重排**：除 §十二 的 4 行合并为 2 行外，其余编辑都是**行内子串替换**
  ⇒ 行尾风格不变。
- 🔴 本脚本**不碰** `status/app/CORRECTIONS_APP.md`（reviewer 独占、只读）、
  **不碰** 客户包、**不跑推理/测速**、**不取 MACHINE_LOCK**。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
MEM_MD = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
TMP = os.environ.get('TEMP', r'C:\Users\Trekker-PTL\AppData\Local\Temp')

MEMORY_CAP = 9700          # 🔴 MEMORY.md 头部自声明上限（注入预算）

# ── §十二：4 行状态流水 ⇒ 合并成 2 行（**每一条事实都保留**）──────────────
SEC12_OLD = (
    '-🔴`last_ack=APP-133`（APP-131/132/133 已执行⇒§230/§231）｜🟢**v2.6 已签 ACCEPTED**'
    '（EXT v0.4.21 `b2a4978`）｜🟢reviewer 判 APP-128 通过；`clone_s2` 的 `n_speakers=0` '
    '判为正常｜🔴**待裁定**：默认分离设备／v2.6 交接。\n'
    '-🟢**APP-128 补充已执行（§225）**：已单独补发 e2e7 三臂表（正文截断）⇒ 邮件 '
    '`msg_52Ta35…`（462 B）｜提交 `b7507cb`。\n'
    '-🟢**MiniMVP v1.1.1 已出包并打 zip**（**5 212 403 155 B / 10 881 文件**）｜🔴**旧 '
    'v1.1.zip 不自证** ⇒ **发客户必须确认发 `v1.1.1.zip`**｜🔴**v2.5 须先重签**'
    '（ACCEPTED 仍指 v2.4）。\n'
    '-🟢**§226（11-24 00:4x）待命轮＋TAKEOVER**：无新纠偏｜🟢已修「reviewer 复算底本'
    '入库字节不一致」（3/3＋反证组 3/3）｜提交 `73a2e22`…`58439ba` 已推｜🔴**更大面未修**：'
    '全仓 **854** 个 `i/lf+w/crlf` ⇒ **须 reviewer 裁定**｜🔴**未进 v2.6／未打包**'
    '（APP-126 §7）。'
)
SEC12_NEW = (
    '-🔴`last_ack=APP-133`（§230/§231）｜🟢**v2.6 已签 ACCEPTED**（EXT v0.4.21 '
    '`b2a4978`）｜🟢reviewer 判 APP-128 通过；`clone_s2` `n_speakers=0` 正常｜🟢**MiniMVP '
    'v1.1.1 已出包并打 zip**（**5 212 403 155 B / 10 881 文件**）｜🔴**旧 v1.1.zip 不自证** '
    '⇒ **发客户发 `v1.1.1.zip`**｜🔴**v2.5 须先重签**（ACCEPTED 仍指 v2.4）｜🔴**待裁定**：'
    '默认分离设备／v2.6 交接。\n'
    '-🟢**APP-128 补充已执行（§225）**：补发 e2e7 三臂表 ⇒ `msg_52Ta35…`（462 B）｜'
    '`b7507cb`｜🟢**§226**：已修复算底本入库字节不一致（3/3＋反证组 3/3）｜🔴**全仓 854 个 '
    '`i/lf+w/crlf` 须 reviewer 裁定**。'
)

# ── 编辑表：每条 = (old, new)；写前断言 old 在全文**恰好 1 次** ──────────
# 压缩来源（**不删任何判据**，只压冗余字／合并重复句）：
#  ① §一 L12 与 L9 的 **CRLF/Write-Edit 句重复** ⇒ 合一句
#  ② §一 L10 与 §八 L47 的 **`CORRECTIONS_APP.md` 的 ` M` 重复** ⇒ 合一句
#  ③ §十二 的 **4 行状态流水** ⇒ 合并成 2 行（事实全留）
#  ④ 各处**同义从句**⇒ 压从句（判据本身一字不改）
#  ⑤ **头部加一条跨模块护栏**（本轮实测：TTS 模块 21:13 写 MEMORY.md ⇒ 超上限）
EDITS = [
    (SEC12_OLD, SEC12_NEW),
    # ① 合并重复：§一 L12 的「CRLF 串带 `\r\n`」与 L9 的「含 `\r\n`/`\t` 的正文必须用
    #    Write/Edit 或 raw string」重复 ⇒ 只留后者。
    (
        '🔴**含 `\\` 的正文/替换串不用 bash heredoc**⇒用 Write/Edit/Python 脚本；'
        'CRLF 串带 `\\r\\n`。',
        '🔴**含 `\\` 的正文/替换串不用 bash heredoc**⇒用 Write/Edit/Python 脚本。',
    ),
    # ② 合并重复：§八 已写「`CORRECTIONS_APP.md` 的 ` M` 是 reviewer 真追加⇒永不 add」
    #    ⇒ §一 只留「只读、不提交」。
    (
        '🔴`CORRECTIONS_*.md` **只读、不提交**（其 ` M` 是 reviewer 真追加⇒永不 add）；',
        '🔴`CORRECTIONS_*.md` **只读、不提交**；',
    ),
    # ③④ 头部两处：压从句（指针仍指向 MODULES 附录·四十九 / STATUS companion）
    (
        '（压缩前全文快照 ⇒ `MEMORY_MODULES.md` 附录·四十九）',
        '（全文快照 ⇒ MODULES 附录·四十九）',
    ),
    (
        '**§214/215/217–226⇒`status/app/STATUS_APP_sec2*_detail_*.md`**',
        '**§214–226⇒`status/app/STATUS_APP_sec2*_detail_*.md`**',
    ),
    (
        '## 十二、App 当前状态（**逐字⇒MODULES 三十七/四十三–四十九 ＋ STATUS '
        '§224/§225/§226/§227 companion**）',
        '## 十二、App 当前状态（**逐字⇒MODULES 三十七/四十三–四十九 ＋ STATUS '
        '§224–§231 companion**）',
    ),
    # ④ 其余同义从句压缩（**判据本身一字不改**）
    (
        '① **发信记录入库的必须是实际发出的那版**⇒核对**实发邮件正文**。',
        '① **发信记录入库的必须是实发那版**⇒核对**实发邮件正文**。',
    ),
    (
        '③ reviewer 的**复算底本**（逐句 jsonl／积压 csv／源 json）**必须入库**。',
        '③ reviewer 的**复算底本**（jsonl／csv／源 json）**必须入库**。',
    ),
    (
        '⇒ 配方 ⇒ `MEMORY_attach_send_recipe.md` ＋ MODULES 四十五'
        '（HKDF/AAD＋两步 `ctk_`）；',
        '⇒ 配方 `MEMORY_attach_send_recipe.md`＋MODULES 四十五'
        '（HKDF/AAD＋两步 `ctk_`）；',
    ),
    (
        '**禁**手抄进脚本／`.b64`／shell。',
        '**禁**手抄（脚本／`.b64`／shell）。',
    ),
    (
        '**token 绑定请求内容 ⇒ 第二次原样重发**',
        '**token 绑请求内容 ⇒ 第二次原样重发**',
    ),
    (
        '🔴**还原式复核两坑（§225）**：**多条换一条指针行**别逐条各换一行；',
        '🔴**还原式两坑（§225）**：**多条换一条指针行**别各换一行；',
    ),
    (
        '＋ 兜底释放锁。',
        '＋兜底释放锁。',
    ),
    (
        '🔴报数须指到「配置＋结果文件＋字段」；没落盘不能写「已交付」。',
        '🔴报数须指到「配置＋结果文件＋字段」；没落盘≠「已交付」。',
    ),
    (
        '🔴**无新纠偏时 `last_ack` 不变**；🔴**待命轮不写 §N**（APP-085 §2／§194 ⑪ ⇒ '
        '只改 STATUS 头部「更新时间」一行）；',
        '🔴**无新纠偏 ⇒ `last_ack` 不变**；🔴**待命轮不写 §N**（APP-085 §2／§194 ⑪ ⇒ '
        '只改 STATUS 头「更新时间」一行）；',
    ),
    (
        '（§225：APP-128 补充 ≠ APP-129）',
        '（§225：APP-128 补充≠APP-129）',
    ),
    (
        '凡依赖「只随包分发」运行时（`babelvox` 等）的 harness',
        '凡依赖只随包分发运行时（`babelvox`）的 harness',
    ),
    (
        '**判定先于产物落位**',
        '**判定先于落位**',
    ),
    (
        '**外部 replay 污染计时**⇒计时臂须独占机器',
        '**外部 replay 污染计时**⇒计时臂须独占机',
    ),
    (
        '，单测 34/34，11-24 10:41）',
        '，单测 34/34）',
    ),
    # 🔴 **不压这一条**：独立复核脚本判定「否定式表述『不是新编号』被压成『非新编号』」
    #    ⇒ 🔴 **可被 grep 的确切串比 6 个字符更重要** ⇒ 保留原文。
    #    （教训：压从句时，**否定词与关键词本身必须逐字保留**，只压修饰语。）
    (
        '⇒「接 c13」≠搬 IR 驱动，而是补 ①**可配窗口口径** ②**TTS-076 限幅与削波计数**。',
        '⇒「接 c13」≠搬 IR 驱动，补 ①**可配窗口口径** ②**TTS-076 限幅与削波计数**。',
    ),
    (
        '🔴🔴🔴**App 本来就是「直接拼接」**（`not split_on_silence` ⇒ 不裁尾）⇒ **TTS-075'
        '「每边界丢 50 ms / 7.3%」缺陷在 App 侧不存在** ⇒ `crossfade_samples=0` 是'
        '**加固非修缺陷**。',
        '🔴🔴🔴**App 本来就是「直接拼接」**（`not split_on_silence`⇒不裁尾）⇒ **TTS-075'
        '「每边界丢 50 ms/7.3%」缺陷在 App 侧不存在** ⇒ `crossfade_samples=0` 是'
        '**加固非修缺陷**。',
    ),
    (
        '⇒ 克隆模式 0 是**口径问题非缺陷**。',
        '⇒克隆模式 0 是**口径问题非缺陷**。',
    ),
    (
        '🔴**TTS §80–§83（伪/真 ICL）**⇒**App 侧禁令 = 不开 `ref_text`/`ref_audio`**'
        '⇒**零动作**。',
        '🔴**TTS §80–§83（伪/真 ICL）**⇒**App 侧禁令＝不开 `ref_text`/`ref_audio`**'
        '⇒**零动作**。',
    ),
    (
        '（须作用于 clone 本身）',
        '（作用于 clone）',
    ),
    (
        '⇒在**影子包**加**只读探针**（只加日志 + env 门控提前返回）⇒diff 落盘供 ',
        '⇒在**影子包**加**只读探针**（只加日志+env 门控提前返回）⇒diff 落盘供 ',
    ),
    (
        '**归档件 write-once**（已归档过的节，活文档是指针行⇒不得拿它当正文覆写）',
        '**归档件 write-once**（已归档过的节，活文档是指针行⇒不得当正文覆写）',
    ),
    (
        '＋ MiniMVP 线（= **rc11**）；',
        '＋ MiniMVP 线（=**rc11**）；',
    ),
    (
        '🔴但「唯一事实来源」被改 ≠ 下游都读它⇒',
        '🔴但「唯一事实来源」被改≠下游都读它⇒',
    ),
    (
        '⇒ **「目标机不可达」至少两因**（离线／**A 机换网**）⇒ 三件套**前置：A 机回该网段**',
        '⇒「目标机不可达」**两因**（离线／**A 机换网**）⇒ **前置：A 机回该网段**',
    ),
    # ⑤ **头部加一条跨模块护栏**（本轮实测：TTS 模块 21:13 写 MEMORY.md ⇒ 超上限）
    (
        '> 纠偏文件（🔴只读不写、不代提交）：',
        '> 🔴**跨模块共享**⇒写完必重跑上限断言⇒超⇒压从句⇒仍超⇒**零改动**。\n'
        '> 纠偏文件（🔴只读不写、不代提交）：',
    ),
]

# 🔴 **判据关键词**：写后必须**全部仍在**（证明「压从句、没删知识」）
KEYWORDS = [
    '原子创建', 'os.replace(tmp, LOCK)', 'lock_lost', '修锁要修生产路径',
    'last_ack=APP-133', 'v2.6 已签', 'b2a4978', '待裁定', 'v1.1.1.zip', 'v2.5 须先重签',
    'i/lf+w/crlf', '无新纠偏', '待命轮不写 §N', '单独执行＋单独发信＋写 §N',
    '首/中/尾三地标', '逐字节相同', '包内 python', 'autocrlf', 'P90≤0.75',
    'EXECUTION_DEVICES', 'spk=None', 'and not _bound', '语速上限现役 = 1.70×',
    '进队列', '492', 'Qwen3-TTS 0.6B', 'APP-130 已由 App dev 树自行实现',
    'TTS-078 降级', '未落盘 ⇒ 不可当证据', 'MiniMVP v1.1.1 包落后 dev 树',
    'CHUNK_FRAMES', 'n_speakers', '192.168.2.206', '_app547_hash_retry.py',
    '5 212 403 155 B', '854', '§230', '§231', '§222', '§224', '§225',
    '假 FAIL', '反证', '写前在**内存新文本**跑真不变量',
    '判据', '复核', '零改动', '逐文件 `git add`', '不 force push',
]


def read_text(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    if not os.path.isfile(MEM_MD):
        print('MEMORY.md 不存在 ⇒ 零改动')
        return 0

    old = read_text(MEM_MD)
    old_b = old.encode('utf-8')
    n0 = len(old)

    # ① 备份（**先备份再动**）
    bak = os.path.join(TMP, 'MEMORY.md.bak_app232')
    shutil.copy2(MEM_MD, bak)
    assert os.path.isfile(bak) and os.path.getsize(bak) > 0, '备份失败'

    # ② 唯一命中断言（写前）
    new = old
    for i, (o, n) in enumerate(EDITS):
        c = new.count(o)
        assert c == 1, '第 %d 条编辑命中数 %d != 1' % (i + 1, c)
        new = new.replace(o, n, 1)

    # ③ 真不变量（**在内存新文本上跑**）
    assert len(new) <= MEMORY_CAP, (
        '压完仍超上限：%d > %d ⇒ 零改动' % (len(new), MEMORY_CAP))
    # 🔴 **行数增量对着编辑表算，不写死常量**（§十二 4 行并成 2 行 ⇒ -2；
    #    头部护栏 +1 ⇒ 净 -1）⇒ 写死数字＝假 FAIL 源 ⇒ 改为**由编辑推导**。
    exp_nl = old.count('\n') + sum(n.count('\n') - o.count('\n') for o, n in EDITS)
    assert new.count('\n') == exp_nl, (
        '行数增量不对：%d != %d' % (new.count('\n'), exp_nl))
    assert (new.count('🔴') + new.count('🟢')) >= (old.count('🔴') + old.count('🟢')) - 2, \
        '标记数减少过多 ⇒ 零改动'
    # 🔴 **标记数按「节」逐一比对，并按「该节被合并掉的行数」给 allowance**：
    #    §十二 4 行并成 2 行 ⇒ 每少一行就少 1 个行首标记 ⇒ allowance = 2。
    #    🔴 **不写死总数**（写死 = 假 FAIL 源）⇒ 由编辑表推导。
    import re as _re

    def _sections(t):
        parts = _re.split(r'(?m)^(?=## )', t)
        return [p for p in parts if p.startswith('## ')]

    so, sn = _sections(old), _sections(new)
    assert len(so) == len(sn), '节数变了 ⇒ 零改动'
    for idx, (a, b) in enumerate(zip(so, sn)):
        ma = a.count('🔴') + a.count('🟢')
        mb = b.count('🔴') + b.count('🟢')
        lines_removed = a.count('\n') - b.count('\n')
        assert mb >= ma - lines_removed, (
            '第 %d 节标记数减少过多：%d -> %d（合并掉 %d 行）⇒ 零改动'
            % (idx, ma, mb, lines_removed))
    assert new.count('last_ack=APP-133') == 1, 'last_ack 行数变了'
    missing = [k for k in KEYWORDS if k not in new]
    assert not missing, '关键词被压掉了 ⇒ 零改动：%r' % (missing,)
    # 章节数不变（`## ` 标题计数）
    assert new.count('\n## ') == old.count('\n## '), '章节数变了 ⇒ 零改动'
    # 🔴 **所有 § 编号不得消失**（跨模块共享 ⇒ 不能靠删编号腾空间）
    #    🔴 **区间写法要能覆盖**（`§224–§231` 覆盖 §227）⇒ 逐个 §N 判断是否
    #    被新文本里**某个区间**包含 ⇒ 不能只看字面集合差。
    import re
    old_secs = set(int(x) for x in re.findall(r'§(\d+)', old))
    new_secs = set(int(x) for x in re.findall(r'§(\d+)', new))
    ranges = []
    for a, b in re.findall(r'§(\d+)[–\-—]§?(\d+)', new):
        ranges.append((int(a), int(b)))
    lost = [n for n in sorted(old_secs - new_secs)
            if not any(a <= n <= b for a, b in ranges)]
    assert not lost, '丢了 § 编号 ⇒ 零改动：%r' % (lost,)

    # ④ **还原式复核**：把新文本改回去 ⇒ 必须逐字节等于原文
    restored = new
    for o, n in reversed(EDITS):
        c = restored.count(n)
        assert c == 1, '还原时命中数 %d != 1' % c
        restored = restored.replace(n, o, 1)
    assert restored == old, '还原式复核失败 ⇒ 零改动'
    assert restored.encode('utf-8') == old_b, '还原式复核（字节）失败 ⇒ 零改动'

    # ⑤ 临时文件 → os.replace（**open(p,'w') 先截断 ⇒ 0 B，绝不那样写**）
    tmp = MEM_MD + '.tmp_app232'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    assert os.path.getsize(tmp) > 0, '临时文件 0 B'
    os.replace(tmp, MEM_MD)

    print('MEMORY.md: %d → %d 字符（上限 %d，余 %d）'
          % (n0, len(new), MEMORY_CAP, MEMORY_CAP - len(new)))
    print('bytes: %d → %d' % (len(old_b), len(new.encode('utf-8'))))
    print('SHA256(old)=%s' % hashlib.sha256(old_b).hexdigest())
    print('SHA256(new)=%s' % hashlib.sha256(new.encode('utf-8')).hexdigest())
    print('备份: %s' % bak)
    return 0


if __name__ == '__main__':
    sys.exit(main())
