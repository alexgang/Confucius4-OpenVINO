# app215 · APP-059 ①：README_zh/en 说话人标签局限说明 + 许可证归属订正
#
# 依据：
#   - APP-059 ①（reviewer）：README_zh/en 中关于说话人标签的段落要写明
#     「实验功能，默认关闭，换人时可能漏标」。
#   - APP-059 ②(a)（reviewer）：许可证以包内 NOTICE 为准（pyannote_seg = MIT，
#     wespeaker = CC BY 4.0）。实测 README_zh L89 / README_en L106-107 把两者写反，
#     与包内 NOTICE（NOTICE L37/L47）及 THIRD_PARTY.md L65-66 矛盾 ⇒ 一并订正。
#   - 数据来源：results/app/app210_app058_recall_diagnosis_evidence.json
#     method_B_text_aligned：n_ref_switches=12 / n_hit=7 / n_false_positive=0。
#
# 纪律：
#   - 只改客户包 v2.1 里的两个**文档**文件（不进 app/ ⇒ 不影响 ACCEPTED.code_fingerprint）；
#   - **不动 zip**（reviewer 明示「都不用重打包」；打包需用户授权）；
#   - 定点替换 + 唯一命中断言 + 写后逐字节复核 + 包外备份；
#   - 脚本**可重入**：已改过的文件识别为 already_applied，备份**不覆盖**（保留改前原件）。
import difflib
import hashlib
import json
import os
import shutil
import time

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.1'
BACKUP = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_pkg_backup_app059_2105'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app215_readme_speaker_note_evidence.json'

DEV_PATH_MARKERS = ['confucius4-openvino', 'live_dub_ext', 'qwen3tts_eval', 'hy_bench',
                    'WorkBuddy\\Worktrees', 'Trekker-PTL']

EDITS = {
    'README_zh.md': [
        {
            'id': 'zh-R1-license',
            'kind': 'replace',
            'old': "  `NOTICE` 已补齐 **pyannote_seg**（CC BY 4.0）与 **wespeaker**（MIT）的署名与来源链接。",
            'new': "  `NOTICE` 已补齐 **pyannote_seg**（MIT）与 **wespeaker**（CC BY 4.0）的署名与来源链接。",
        },
        {
            'id': 'zh-R2-speaker-caveat',
            'kind': 'append',
            'old': ("* 说话人识别（diarization）旁路**默认关闭**，需要时手动开启；\n"
                    "  开启后也在**独立线程**运行，**不会**阻塞字幕主循环。"),
            'new': ("* 说话人识别（diarization）旁路**默认关闭**，需要时手动开启；\n"
                    "  开启后也在**独立线程**运行，**不会**阻塞字幕主循环。\n"
                    "* 字幕上的说话人标签（`S1 / S2 …`）属**实验功能**：旁路**默认关闭**；\n"
                    "  开启后若**换人**（说话人切换）**可能漏标**（内部实测：12 个人工标注的换人点\n"
                    "  只检出 7 个）⇒ 标签仅作参考，**不影响**字幕内容与翻译。"),
        },
    ],
    'README_en.md': [
        {
            'id': 'en-R1-license',
            'kind': 'replace',
            'old': ("  third-party sample voices. `NOTICE` now credits **pyannote_seg** (CC BY 4.0)\n"
                    "  and **wespeaker** (MIT), with source links."),
            'new': ("  third-party sample voices. `NOTICE` now credits **pyannote_seg** (MIT)\n"
                    "  and **wespeaker** (CC BY 4.0), with source links."),
        },
        {
            'id': 'en-R2-speaker-caveat',
            'kind': 'append',
            'old': ("* The speaker-diarization bypass is **off by default** and must be enabled\n"
                    "  manually; when enabled it runs on a **separate thread** and never blocks the\n"
                    "  caption main loop."),
            'new': ("* The speaker-diarization bypass is **off by default** and must be enabled\n"
                    "  manually; when enabled it runs on a **separate thread** and never blocks the\n"
                    "  caption main loop.\n"
                    "* Speaker labels on the subtitles (`S1 / S2 …`) are an **experimental feature**:\n"
                    "  the bypass is **off by default**; once enabled, a **speaker change may be\n"
                    "  missed** (internal measurement: 7 of 12 hand-labelled switch points were\n"
                    "  detected) ⇒ labels are for reference only and do **not** affect the caption\n"
                    "  text or the translation."),
        },
    ],
}


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def eol(b):
    return (b.count(b'\r\n'), b.count(b'\n') - b.count(b'\r\n'))


def main():
    os.makedirs(BACKUP, exist_ok=True)
    rows = []
    for fname, edits in EDITS.items():
        path = os.path.join(PKG, fname)
        bpath = os.path.join(BACKUP, fname)
        # ① 备份（**不覆盖**已有备份 ⇒ 保留改前原件）
        if os.path.isfile(bpath):
            backup_created = False
        else:
            shutil.copy2(path, bpath)
            backup_created = True
        before = open(bpath, 'rb').read()          # 基准 = 改前原件（备份）
        cur = open(path, 'rb').read()
        text = cur.decode('utf-8')
        applied = []
        for e in edits:
            n_old = text.count(e['old'])
            n_new = text.count(e['new'])
            # 已应用判定（**append 型的新文本包含旧文本**，故不能只看 n_old）
            if n_new >= 1 and (e['kind'] == 'append' or n_old == 0):
                applied.append({'id': e['id'], 'kind': e['kind'], 'hits_old': n_old,
                                'hits_new': n_new, 'state': 'already_applied'})
            elif n_old == 1:
                text = text.replace(e['old'], e['new'], 1)
                applied.append({'id': e['id'], 'kind': e['kind'], 'hits_old': n_old,
                                'hits_new': n_new, 'state': 'applied',
                                'old_bytes': len(e['old'].encode('utf-8')),
                                'new_bytes': len(e['new'].encode('utf-8'))})
            else:
                raise SystemExit('[ABORT] %s %s 唯一命中断言失败：old=%d new=%d（期望 old=1 或已应用）'
                                 % (fname, e['id'], n_old, n_new))
        after = text.encode('utf-8')
        if after != cur:
            tmp = path + '.app215tmp'
            with open(tmp, 'wb') as f:
                f.write(after)
            os.replace(tmp, path)
        reread = open(path, 'rb').read()
        if reread != after:
            raise SystemExit('[ABORT] %s 写后回读与预期不一致' % fname)
        # 行尾不变式：不得引入 CRLF
        if eol(before)[0] != eol(reread)[0]:
            raise SystemExit('[ABORT] %s CRLF 数被改动' % fname)
        # 旧正文不变式：相对**改前原件**，delete=0；replace 行数=许可证行数；insert 行数=预期
        old_lines = before.decode('utf-8').split('\n')
        new_lines = reread.decode('utf-8').split('\n')
        ops = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes()
        n_del = sum(i2 - i1 for tag, i1, i2, _, _ in ops if tag == 'delete')
        n_rep = sum(i2 - i1 for tag, i1, i2, _, _ in ops if tag == 'replace')
        n_ins = sum(j2 - j1 for tag, _, _, j1, j2 in ops if tag == 'insert')
        exp_ins = sum(e['new'].count('\n') - e['old'].count('\n') for e in edits)
        exp_rep = sum((e['old'].count('\n') + 1) for e in edits if e['kind'] == 'replace')
        if n_del != 0 or n_rep != exp_rep or n_ins != exp_ins:
            raise SystemExit('[ABORT] %s 旧正文改动超出预期：delete=%d replace=%d insert=%d（期望 0/%d/%d）'
                             % (fname, n_del, n_rep, n_ins, exp_rep, exp_ins))
        # 等价性：以**改前原件**重算期望值，必须与落盘字节完全一致
        expect = before.decode('utf-8')
        for e in edits:
            expect = expect.replace(e['old'], e['new'], 1)
        if expect.encode('utf-8') != reread:
            raise SystemExit('[ABORT] %s 落盘内容与「改前原件+定点替换」重算结果不一致' % fname)
        # 反证：备份（改前）**不得**含新文本；当前文件必须含全部新文本；replace 型的旧文本必须已消失
        bak_txt = before.decode('utf-8')
        cur_txt = reread.decode('utf-8')
        anti = {
            'backup_has_new': any(e['new'] in bak_txt for e in edits),
            'current_has_all_new': all(e['new'] in cur_txt for e in edits),
            'current_has_old_for_replace': [e['id'] for e in edits
                                            if e['kind'] == 'replace' and e['old'] in cur_txt],
        }
        if anti['backup_has_new'] or not anti['current_has_all_new'] or anti['current_has_old_for_replace']:
            raise SystemExit('[ABORT] %s 反证失败：%s' % (fname, anti))
        # 开发机路径标记扫描：**只判「本轮新引入」的**（改前就有的照原样记录，不阻断）
        leak_new = [m for m in DEV_PATH_MARKERS if m in cur_txt and m not in bak_txt]
        leak_pre = [m for m in DEV_PATH_MARKERS if m in cur_txt and m in bak_txt]
        if leak_new:
            raise SystemExit('[ABORT] %s 本轮新引入开发机路径标记：%s' % (fname, leak_new))
        leak = leak_new
        rows.append({
            'file': fname,
            'path': path,
            'backup': bpath,
            'backup_created_this_run': backup_created,
            'bytes_before': len(before), 'sha256_before': sha_bytes(before),
            'bytes_after': len(reread), 'sha256_after': sha_bytes(reread),
            'mtime_after': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(path))),
            'eol_before': {'crlf': eol(before)[0], 'lf': eol(before)[1]},
            'eol_after': {'crlf': eol(reread)[0], 'lf': eol(reread)[1]},
            'old_body_ops': {'delete': n_del, 'replace': n_rep, 'insert': n_ins},
            'edits': applied,
            'anti_falsification': anti,
            'dev_path_leak_new': leak_new,
            'dev_path_leak_preexisting': leak_pre,
        })
        print('[edit] %-14s %d B -> %d B  sha %s -> %s  ops(del/rep/ins)=%d/%d/%d'
              % (fname, len(before), len(reread), sha_bytes(before)[:12], sha_bytes(reread)[:12],
                 n_del, n_rep, n_ins))

    out = {
        'tool': 'app215_readme_speaker_note',
        'correction': 'APP-059 ① + ②(a)',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': PKG,
        'scope': ('仅客户包 v2.1 的两个文档文件（README_zh.md / README_en.md）；app/ 生产模块未动 ⇒ '
                  'ACCEPTED.code_fingerprint（app191 口径，28 个生产模块）不受影响；zip 未动 ⇒ '
                  'zip 内 README 仍是改前版本，下一版本号打包时带入'),
        'recall_evidence': 'results/app/app210_app058_recall_diagnosis_evidence.json（method_B_text_aligned: n_ref_switches=12, n_hit=7, n_false_positive=0）',
        'license_authority': '包内 NOTICE L37（wespeaker=CC BY 4.0）/ L47（pyannote/segmentation-3.0=MIT）+ THIRD_PARTY.md L65-66',
        'rows': rows,
        'verdict': 'PASS',
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\nverdict=PASS  evidence=%s' % OUT)


if __name__ == '__main__':
    main()
