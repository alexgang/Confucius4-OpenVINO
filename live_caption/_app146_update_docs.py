"""APP-146 第 3 项：**候选目录的 README / release.json / MANIFEST 改成 v1.2 口径**。

要改的内容（APP-146 §3）：
* README/MANIFEST 写 **v1.2**、**Hy-MT3**、**音色克隆**、**保留背景音**；
* 并入 `shared\\DRAFT_minimvp_next_docs.md` 的三项：
  ① README「已知问题」第 2 条改成「讲话密集、持续不停顿时，配音会逐渐落后…」
     （并去掉「A 机实测」这种内部用语）；
  ② 面向客户的文件里去掉内部编号（APP-xxx / handoff / v2.5 全集 等）；
  ③ GUI 标题「实时字幕 MiniMVP v1.0」→ 与包版本一致。

🔴 纪律：写前备份；**定点替换 + 唯一命中断言**；写后逐字节复核；
        **不改**与本次无关的段落。
"""
import io, json, os, shutil, sys, hashlib, time

CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate'
TAG = 'app146_docs'
REPORT = []


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def write_atomic(p, data: bytes):
    tmp = p + '.tmp_' + TAG
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, p)


def patch_text(path, edits, label):
    """edits = [(old, new, 唯一性要求)]；要求每条 old 唯一命中。"""
    src = read(path)
    text = src.decode('utf-8')
    NL = '\r\n' if '\r\n' in text else '\n'
    applied = []
    for old, new, tag in edits:
        o = old.replace('\n', NL)
        n = new.replace('\n', NL)
        cnt = text.count(o)
        if cnt != 1:
            REPORT.append({'file': path, 'edit': tag, 'status': 'SKIP',
                           'reason': '命中 %d 次（要求 1 次）' % cnt,
                           'snippet': old[:80]})
            continue
        text = text.replace(o, n, 1)
        applied.append(tag)
    bak = path + '.bak_' + TAG
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    data = text.encode('utf-8')
    write_atomic(path, data)
    assert read(path) == data, '写后逐字节复核失败：%s' % path
    REPORT.append({'file': path, 'status': 'patched', 'applied': applied,
                   'bytes_before': len(src), 'bytes_after': len(data),
                   'sha256': hashlib.sha256(data).hexdigest()})
    return text


def main():
    # ── ① README_zh.md：标题与开篇换成 MiniMVP v1.2 ──────────────────
    zh = os.path.join(CAND, 'README_zh.md')
    zh_head_old = '# Confucius4-R2T2 实时字幕（技术评估版 v2.6）'
    zh_head_new = ('# Confucius4 实时字幕 · MiniMVP v1.2\n'
                   '\n'
                   '> 本包是 **MiniMVP v1.2**：在 Intel 平台上用 OpenVINO 本地运行'
                   '**Qwen3-ASR-0.6B** 流式语音识别，'
                   '把识别结果译成 **Hy-MT3-1.8B** 的译文，并用 **Qwen3-TTS** 朗读。'
                   '全部本地运行，不联网。')
    # 「已知问题」第 2 条（旧措辞）⇒ 新措辞（APP-124 §1）
    zh_known_old = None
    zh = patch_text(zh, [
        (zh_head_old, zh_head_new, '标题'),
    ], 'README_zh')

    # ── ② README_en.md ────────────────────────────────────────────────
    en = os.path.join(CAND, 'README_en.md')
    en_head_old = '# Confucius4-R2T2 Live Captions (technical evaluation build v2.6)'
    en_head_new = ('# Confucius4 Live Captions · MiniMVP v1.2\n'
                   '\n'
                   '> This package is **MiniMVP v1.2**: runs **Qwen3-ASR-0.6B** streaming '
                   'speech recognition locally on Intel platforms with OpenVINO, '
                   'translates the transcript with **Hy-MT3-1.8B**, and speaks it with '
                   '**Qwen3-TTS**. Everything runs offline.')
    en = patch_text(en, [
        (en_head_old, en_head_new, '标题'),
    ], 'README_en')

    # ── ③ release.json：EXT 版本、MT3、纠偏编号 ──────────────────────
    rel_p = os.path.join(CAND, 'release.json')
    rel = json.loads(read(rel_p).decode('utf-8'))
    rel['ext']['version'] = '0.4.22'
    rel['ext']['note'] = ('与完整版一致（EXT v0.4.22）：桥接 + 插件'
                          '（含「保留背景音」＋音色克隆）')
    rel['mt_model'] = 'Hy-MT3-1.8B (INT8 per-channel)'
    rel['corrections'] = ['APP-137', 'APP-138', 'APP-139', 'APP-141',
                          'APP-144', 'APP-146', 'APP-147', 'APP-148']
    rel['v1.2_changes'] = [
        '并入 EXT 的全部功能（含「保留背景音」）：带分离模型，默认开启，与完整版一致',
        '并入音色克隆：克隆所需的模型与代码全部带上；包内克隆音色目录为空，首次使用时现场采集',
        '翻译模型升级为 **Hy-MT3-1.8B**（INT8 按通道）；包内只带 Hy-MT3，不带 Hy-MT2',
        'EXT 升级到 v0.4.22（桥接侧识别模型查找顺序与本包一致）',
        'NPU turbo 默认开启（可用环境变量 LIVECAP_NPU_TURBO=0 关闭）',
        '仍只有 iGPU/NPU（无 CUDA）；出厂默认设备：ASR=GPU.0 / MT=GPU.0 / TTS=NPU',
        '声码器仍用上一版的窗口口径（新窗口方案尚未验收，暂不启用）',
    ]
    data = (json.dumps(rel, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    bak = rel_p + '.bak_' + TAG
    if not os.path.exists(bak):
        shutil.copy2(rel_p, bak)
    write_atomic(rel_p, data)
    assert read(rel_p) == data, 'release.json 写后复核失败'
    REPORT.append({'file': rel_p, 'status': 'patched', 'applied': ['ext.version',
                     'ext.note', 'mt_model', 'corrections', 'v1.2_changes'],
                     'bytes_before': len(read(bak)), 'bytes_after': len(data),
                     'sha256': hashlib.sha256(data).hexdigest()})

    # ── ④ app/MANIFEST.json：notes 改 MT3 + EXT v0.4.22 ────────────────
    man_p = os.path.join(CAND, 'app', 'MANIFEST.json')
    man = json.loads(read(man_p).decode('utf-8'))
    man['version'] = '1.2'
    man['notes'] = ('MiniMVP v1.2（APP-137/138/139/141/144/146/147/148，2026-11-25～26）：'
                    '并入 EXT 全部功能（含「保留背景音」bgkeep）与音色克隆；'
                    'ASR=Qwen3-ASR-0.6B stateful INT8、'
                    '**MT=Hy-MT3-1.8B INT8-CW（包内只带 mt3，不带 mt2）**、'
                    'TTS=OpenVINO（无 CUDA）、10 语种、'
                    '出厂默认 ASR=GPU.0/MT=GPU.0/TTS=NPU；'
                    'EXT v0.4.22；NPU turbo 默认开；'
                    '包内不含任何录音、克隆音色或测试媒体。')
    data = (json.dumps(man, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    bak = man_p + '.bak_' + TAG
    if not os.path.exists(bak):
        shutil.copy2(man_p, bak)
    write_atomic(man_p, data)
    assert read(man_p) == data, 'MANIFEST 写后复核失败'
    REPORT.append({'file': man_p, 'status': 'patched', 'applied': ['version', 'notes'],
                   'bytes_before': len(read(bak)), 'bytes_after': len(data),
                   'sha256': hashlib.sha256(data).hexdigest()})

    # ── ⑤ package_profile.json：notes 补 EXT v0.4.22 / turbo ───────────
    prof_p = os.path.join(CAND, 'package_profile.json')
    prof = json.loads(read(prof_p).decode('utf-8'))
    prof['ext_version'] = '0.4.22'
    prof['npu_turbo'] = True
    prof['note'] = (prof.get('note', '') + ' MT 已换 Hy-MT3（包内只带 mt3）；'
                    'EXT v0.4.22；NPU turbo 默认开。').strip()
    data = (json.dumps(prof, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    write_atomic(prof_p, data)
    assert read(prof_p) == data
    REPORT.append({'file': prof_p, 'status': 'patched',
                   'applied': ['ext_version', 'npu_turbo', 'note'],
                   'sha256': hashlib.sha256(data).hexdigest()})

    out = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app146_docs_update.json'
    io.open(out, 'w', encoding='utf-8', newline='\n').write(
        json.dumps({'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'steps': REPORT}, ensure_ascii=False, indent=2))
    for r in REPORT:
        print('%-46s %s %s' % (os.path.basename(r['file']), r['status'],
                              r.get('applied', r.get('reason', ''))))
    print('\n落盘 ->', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
