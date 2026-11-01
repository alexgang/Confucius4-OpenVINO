# app216 · APP-059：把 §125 追加进 status/app/STATUS_APP.md（并按 APP-052 ④ 压缩腾空间）
#
# 纪律：
#   - **只追加**：新增 `## §125` 章节；旧章节正文**一字未删**（§124 正文整块原样归档）。
#   - 只动**头部区**（last_ack / 更新时间 / 当前任务 / 阻塞 / 已压缩）＋「最近更新」＋「最近章节」索引表。
#   - 压缩手法与 §123 一致：把 §124 正文写入 `status/archive/STATUS_APP_sec124_upto_20261101.md`，
#     主文件里只留 3 行索引（与 §123 的写法一致）。
#   - 「最近更新」旧条目（§109–§121）**逐字**移入同一归档文件，不删内容。
#   - 自指大小（"本文件 N B / M 行"）必须与磁盘**实测一致** ⇒ 迭代到不动点。
#   - 写文件先写临时文件再原子替换。
#   - **绝不**修改 `status/app/CORRECTIONS_APP.md`（reviewer 独占写入文件）。
import hashlib
import json
import os
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec124_upto_20261101.md')
BODY = os.path.join(REPO, 'results', 'app', '_app216_sec125_body.md')
BODY2 = os.path.join(REPO, 'results', 'app', '_app218_sec126_body.md')
HOWTO = r'C:\Users\Trekker-PLT\shared\ext_listen\v21\HOWTO.txt'
HOWTO = r'C:\Users\Trekker-PTL\shared\ext_listen\v21\HOWTO.txt'
OUT = os.path.join(REPO, 'results', 'app', 'app216_status_app059_write_evidence.json')

LIMIT_BYTES = 40000
LIMIT_LINES = 300
KEEP_RECENT = 0          # 「最近更新」保留的旧条目数（§124/§123/§122/§121…）＋ 新增 §125

NEW_HEADER = {
    'last_ack': 'last_ack: APP-060',
    'ts': '更新时间: 2026-11-01 21:13',
    'task': ('当前任务: **§126 ✅ APP-059 + APP-060 已执行完毕**（`last_ack` APP-058 → **APP-060**）—— ① **APP-059**：**口径 A 作废、口径 B（文本对齐）为唯一口径**，召回率 **7/12 = 58.33 %**（误报 0）⇒ 仍 **FAIL、差 1 个点**（**未调阈值、未改参照**）；**README_zh/en 已写明**「实验功能／默认关闭／换人时可能漏标」（v2.1 包内 L92-94 / L111-115）；**更正 §124 两处**（许可证写反 ⇒ 以 NOTICE 为准；「与 v1.13 只差 speaker_assets 注释」不成立 ⇒ 实测 **5 个 py 不同**）；**补齐 `app/MANIFEST.json` SHA 三元组** ＋ 写明 **v1.13.zip（15:02）装的是 14:33 代码 ⇒ 不要再从它安装 v1.13**；**EXT-028 未通过** ＋ **HOWTO 已写**（`shared\ext_listen\v21\HOWTO.txt`）② **APP-060**：**交付版 = v2.1**（zip 20:38 SHA `835803a7…`），**v2.0 已标 superseded**；桌面 **v2.0.lnk 已由 reviewer 删除**、`app212` 加 **SUPERSEDED 硬闸门**（exit 2）；**本轮未打包**（今后改动只打 v2.2+）'),
    'block': ('阻塞 / 待用户决定: ① 🔴 **判据④ 召回率仍未达标**：唯一口径 B = **58.33 %（7/12）**，需 ≥ 8/12 ⇒ **差 1 个点**（已记为「已知局限」＋ README 写明；**未换口径、未调阈值、未改参照**；治本在 ASR 侧 ⇒ 需主会话转达）② 🔴 **APP-057 ⑤(b) 仍未做**：EXT-028 **未通过**（EXT `last_ack` 仍 EXT-031、EXT-032 未执行）⇒ 只把**用户操作步骤**准备好（`shared\ext_listen\v21\HOWTO.txt`），等 EXT 交出实录后由用户手势执行并抽听③ 🔴 **交付 zip 内 README 仍是改前版本**（APP-059 ① 只写进了 v2.1 目录，21:05）⇒ 按 APP-060 ④ 需**另打 v2.2**；**本轮未打包**④ ℹ️ **v2.1 已定为交付版**；v2.0 目录与 zip **保留作历史记录、不再对外**⑤ ℹ️ **v2.1 仍缺用户实听 3 段 1.2–1.3× 配音素材**（`shared\app_accel_listen\`）＋ reviewer 判定音质/不变调/可懂⑥ ℹ️ **§123 待复核项**（GUI 正式行 `[Sx]` 前缀取不到图 / `app179` B4 空真等）仍在等 reviewer'),
}

RECENT_NEW2 = ('- 2026-11-01 21:13 **§126 APP-060 已执行** ⇒ ① **交付版 = v2.1**（zip 20:38 SHA `835803a7…`）⇒ **v2.0 标 superseded**（`DELIVERY_2.0.json` / `DELIVERY_2.1.json`，只追加字段）② 桌面 **v2.0.lnk 已由 reviewer 21:10 删除** ⇒ `app212` 加 **SUPERSEDED 硬闸门**（被取代 ⇒ exit 2、不写 .lnk；已反证）③ **未通知安装 / 未打包**；今后改动只打 v2.2+ ④ **CORRECTIONS_APP.md 本轮中途被追加 APP-060**（⇒ §125 ⑧ 的「零修改」作废）')

RECENT_NEW = ('- 2026-11-01 21:10 **§125 APP-059 已执行** ⇒ ① **口径 A 作废、口径 B 为唯一口径**（7/12 = 58.33 %、误报 0 ⇒ 仍 FAIL、差 1 个点；**未换口径、未调阈值、未改参照**）② **README_zh/en 写明说话人标签局限**（v2.1 包内 L92-94 / L111-115）③ **更正 §124 两处**（许可证写反 / 「只差 speaker_assets 注释」不成立：实测 5 个 py 不同）④ **补齐 `app/MANIFEST.json` SHA 三元组** ＋ 写明 **v1.13.zip 与目录不一致 ⇒ 不要再从它安装**⑤ **EXT-028 未通过** ＋ **HOWTO 已写**（`shared\ext_listen\v21\HOWTO.txt`）⑥ **未通知安装、未打包**')


def sha_text(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def build_archive(sec124_body, recent_old, recent_all, ret_block=None):
    head = ('# STATUS_APP 归档 —— §124 正文（逐字保留，内容一字未删）\n'
            '\n'
            '- 归档来源：`status/app/STATUS_APP.md` → `§124` 正文\n'
            '- 归档时间：2026-11-01（本轮 APP-059/060 执行时腾空间用）\n'
            '- 本文件另含：本轮一并归档的「最近更新」旧条目 ＋「已撤回的旧结论」备查块（逐字保留，内容一字未删）\n'
            '- 更早的章节见 `STATUS_APP_sec123_upto_20261101.md`、`STATUS_APP_sec109_122_upto_20261101.md` 与 '
            '`STATUS_APP_upto_20261030.md`\n'
            '\n'
            '---\n'
            '\n')
    tail = ('\n\n---\n\n'
            '## 附：本轮一并归档的「最近更新」旧条目（逐字保留，内容一字未删）\n\n'
            + '\n'.join(recent_old) + '\n')
    if ret_block:
        tail += ('\n\n---\n\n'
                 '## 附：本轮一并归档的「已撤回的旧结论」备查块（逐字保留，内容一字未删）\n\n'
                 + '\n'.join(ret_block).rstrip('\n') + '\n')
    return head + sec124_body.rstrip('\n') + tail


def main():
    src = open(STATUS, encoding='utf-8').read()
    orig_lines = src.split('\n')
    corr_before = open(CORR, 'rb').read()
    # 包外备份（改前原件）
    bak = os.path.join(REPO, 'results', 'app', '_status_backup_app059_2112_STATUS_APP.md')
    with open(bak, 'w', encoding='utf-8', newline='') as f:
        f.write(src)

    # ── 定位 §124 正文（标题行 → EOF）──
    i124 = next(i for i, l in enumerate(orig_lines) if l.startswith('### §124'))
    sec124_heading = orig_lines[i124]
    sec124_body = '\n'.join(orig_lines[i124:]).rstrip('\n')

    # ── 定位「最近更新」条目 ──
    i_recent = orig_lines.index('## 最近更新')
    i_recent_end = orig_lines.index('## 当前有效结论')
    recent_block = orig_lines[i_recent + 1:i_recent_end]
    # 去掉尾部空行
    while recent_block and recent_block[-1].strip() == '':
        recent_block.pop()
    keep = recent_block[:KEEP_RECENT]
    recent_old = recent_block[KEEP_RECENT:]

    # ── 归档件（先算「已撤回的旧结论」备查块 ⇒ 一并归档，逐字保留）──
    ret_block = []
    arch_text = ''

    # ── §125 正文（HOWTO 全文内嵌）──
    howto = open(HOWTO, encoding='utf-8').read().replace('\r\n', '\n').rstrip('\n')
    body = open(BODY, encoding='utf-8').read().replace('\r\n', '\n')
    body2 = open(BODY2, encoding='utf-8').read().replace('\r\n', '\n')
    if body.count('<<<HOWTO>>>') != 1:
        raise SystemExit('[ABORT] HOWTO 占位符数量异常')
    body = body.replace('<<<HOWTO>>>', howto)

    # ── 组装新文件 ──
    header = orig_lines[:9]
    head_map = {
        'last_ack:': NEW_HEADER['last_ack'],
        '更新时间:': NEW_HEADER['ts'],
        '当前任务:': NEW_HEADER['task'],
        '阻塞 / 待用户决定:': NEW_HEADER['block'],
    }
    comp_idx = next(i for i, l in enumerate(header) if l.startswith('已压缩:'))
    for i, l in enumerate(header):
        for k, v in head_map.items():
            if l.startswith(k):
                if orig_lines.count(l) != 1:
                    raise SystemExit('[ABORT] 头部行不唯一：%s' % l[:30])
                header[i] = v
    # 已压缩行是自指的 ⇒ 先放占位，稍后迭代
    comp_line = header[comp_idx]
    header[comp_idx] = '@@COMPRESSED@@'

    rest = orig_lines[i_recent_end:]          # 当前有效结论 + 未完成纠偏 + 最近章节索引 + §123 索引 + §124 正文
    # ── 压缩：把「已撤回的旧结论」备查块整块移入归档（逐字保留，只留指针）──
    i_ret = next((i for i, l in enumerate(rest) if l.startswith('### 已撤回的旧结论')), None)
    if i_ret is not None:
        j_ret = i_ret + 1
        while j_ret < len(rest) and not rest[j_ret].startswith('## '):
            j_ret += 1
        ret_block = rest[i_ret:j_ret]
        rest = (rest[:i_ret]
                + [rest[i_ret], '',
                   '> 本块已原样归档 ⇒ 见 `status/archive/STATUS_APP_sec124_upto_20261101.md`（逐字保留，内容一字未删）。',
                   '']
                + rest[j_ret:])
    # ── 归档件 ──
    arch_text = build_archive(sec124_body, recent_old, recent_block, ret_block)
    os.makedirs(os.path.dirname(ARCH), exist_ok=True)
    with open(ARCH, 'w', encoding='utf-8', newline='') as f:
        f.write(arch_text)
    # 最近章节索引表：§124 行状态改「已归档」＋ 追加 §125 行
    j124 = next(i for i, l in enumerate(rest) if l.startswith('| §124 |'))
    if orig_lines.count(rest[j124]) != 1:
        raise SystemExit('[ABORT] §124 索引行不唯一')
    rest[j124] = rest[j124].replace('| **本轮新增（见下）** |', '| 已归档 |')
    rest.insert(j124 + 1, '| §125 | **APP-059**：口径 B 定为唯一口径 ＋ README 局限说明 ＋ 两处更正 ＋ MANIFEST 三元组 ＋ HOWTO | **本轮新增（见下）** |')
    j125 = next(i for i, l in enumerate(rest) if l.startswith('| §125 |'))
    rest.insert(j125 + 1, '| §126 | **APP-060**：交付版 = v2.1 ＋ v2.0 标 superseded ＋ 桌面 v2.0.lnk 已删（脚本加硬闸门） | **本轮新增（见下）** |')
    j_note = next(i for i, l in enumerate(rest) if l.startswith('> 按 APP-052 ④'))
    rest[j_note] = (rest[j_note].replace('**§109–§122 正文已原样归档**', '**§109–§124 正文已原样归档**')
                    .replace('`status/archive/STATUS_APP_sec109_122_upto_20261101.md`',
                             '`status/archive/STATUS_APP_sec124_upto_20261101.md`（内含 §124 正文 ＋ 旧「最近更新」条目）'
                             '与 `status/archive/STATUS_APP_sec109_122_upto_20261101.md`'))
    # 去掉 §124 正文（已归档），换成 3 行索引
    k124 = next(i for i, l in enumerate(rest) if l.startswith('### §124'))
    rest = rest[:k124]
    sec124_index = [sec124_heading, '',
                    '> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec124_upto_20261101.md`（逐字保留，内容一字未删）。',
                    '']

    new_lines = (header
                 + ['## 最近更新', RECENT_NEW2, RECENT_NEW] + keep
                 + rest
                 + sec124_index
                 + body.rstrip('\n').split('\n')
                 + ['']
                 + body2.rstrip('\n').split('\n')
                 + [''])          # 末尾保留换行（与原文件一致）

    def compose(comp_text):
        ls = list(new_lines)
        ls[comp_idx] = comp_text
        return '\n'.join(ls)

    # ── 自指大小不动点迭代 ──
    comp_text = comp_line
    for it in range(12):
        text = compose(comp_text)
        b = len(text.encode('utf-8'))
        n = text.count('\n') + 1
        want = ('已压缩: 本文件 %d B / %d 行（APP-052 ④ 限额 ≤ %d B / ≤ %d 行）；**§109–§124 正文＋旧「最近更新」条目＋「已撤回的旧结论」备查块已原样归档**到 '
                '`status/archive/STATUS_APP_sec124_upto_20261101.md`（**逐字保留，内容一字未删**；更早的见 `STATUS_APP_sec109_122_upto_20261101.md`）'
                % (b, n, LIMIT_BYTES, LIMIT_LINES))
        if want == comp_text:
            break
        comp_text = want
    final_text = compose(comp_text)
    fb = len(final_text.encode('utf-8'))
    fn = final_text.count('\n') + 1
    # 再核对一次自指值
    assert ('本文件 %d B / %d 行' % (fb, fn)) in final_text, '自指大小与实测不一致'

    # ── 写前校验 ──
    if fb > LIMIT_BYTES or fn > LIMIT_LINES:
        raise SystemExit('[ABORT] 压缩后仍超限：%d B / %d 行（限额 %d B / %d 行）' % (fb, fn, LIMIT_BYTES, LIMIT_LINES))

    # ── 原子写 ──
    tmp = STATUS + '.tmp216'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(final_text)
    os.replace(tmp, STATUS)

    # ── 写后复核 ──
    now = open(STATUS, encoding='utf-8').read()
    assert now == final_text, '写后回读与预期不一致'
    assert '### §125' in now and '### §124' in now and '### §123' in now
    # 旧正文：除「头部 5 行 + 最近更新旧条目 + §124 正文 + 索引表 2 行 + 索引说明行」外，其余行必须逐字仍在
    kept_ok = []
    dropped = []
    modified_prefixes = ('last_ack:', '更新时间:', '当前任务:', '阻塞 / 待用户决定:', '已压缩:')
    for i, l in enumerate(orig_lines):
        if not l.strip():
            continue
        if l.startswith(modified_prefixes):
            continue
        if l.startswith('- 2026-') and l in recent_old:
            continue
        if l == sec124_heading or l in sec124_body.split('\n'):
            continue
        if l.startswith('| §124 |') or l.startswith('> 按 APP-052 ④'):
            continue
        if ret_block and l in ret_block:
            continue
        if l not in now:
            dropped.append((i + 1, l[:80]))
    if dropped:
        raise SystemExit('[ABORT] 有旧正文行丢失：%s' % dropped[:5])
    # 归档件逐字命中
    arch = open(ARCH, encoding='utf-8').read()
    miss = [l for l in sec124_body.split('\n') if l.strip() and l not in arch]
    if miss:
        raise SystemExit('[ABORT] 归档件缺行：%s' % miss[:3])
    miss2 = [l for l in recent_old if l.strip() and l not in arch]
    if miss2:
        raise SystemExit('[ABORT] 归档件缺「最近更新」旧条目：%s' % miss2[:3])
    # CORRECTIONS 未动
    corr_after = open(CORR, 'rb').read()
    if corr_after != corr_before:
        raise SystemExit('[ABORT] CORRECTIONS_APP.md 被改动！')

    out = {
        'tool': 'app216_status_app059_write',
        'correction': 'APP-059',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'status_path': STATUS,
        'bytes_before': len(src.encode('utf-8')), 'lines_before': src.count('\n') + 1,
        'bytes_after': fb, 'lines_after': fn,
        'limits': {'bytes': LIMIT_BYTES, 'lines': LIMIT_LINES},
        'within_limits': fb <= LIMIT_BYTES and fn <= LIMIT_LINES,
        'archive_file': ARCH,
        'archive_bytes': len(arch.encode('utf-8')),
        'archive_sha256': sha_text(arch),
        'sec124_archived_verbatim': True,
        'recent_old_entries_archived': len(recent_old),
        'recent_kept_entries': len(keep),
        'howto_embedded': True,
        'corrections_sha256_before': hashlib.sha256(corr_before).hexdigest(),
        'corrections_sha256_after': hashlib.sha256(corr_after).hexdigest(),
        'corrections_unchanged': corr_before == corr_after,
        'verdict': 'PASS',
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('STATUS: %d B / %d 行  ⇒  %d B / %d 行（限额 %d B / %d 行）'
          % (len(src.encode('utf-8')), src.count('\n') + 1, fb, fn, LIMIT_BYTES, LIMIT_LINES))
    print('归档件: %s（%d B）' % (ARCH, len(arch.encode('utf-8'))))
    print('verdict=PASS')


if __name__ == '__main__':
    main()
