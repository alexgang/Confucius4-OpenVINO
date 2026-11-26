"""APP-146 第 3 项：**重做 MiniMVP v1.2 候选目录**（就地覆盖 `.candidate`，它还没发出去）。

## 要做的事（APP-146 §3 + APP-138 + APP-141 + APP-144 ② + APP-147）

1. **EXT 升到 v0.4.22**：把 `live_dub_ext/ext/*.py` 的**本次改动点**（mt3 优先、
   `npu_turbo_props()`、version.py）**定点同步**进候选目录的 `ext/bridge/`；
   ⚠️ **禁止整目录覆盖** ⇒ 只同步**本轮改动的文件**，且逐文件做
   「唯一命中断言 + 写后逐字节复核」。
2. **MT 只带 mt3**：`models/mt/` 里删掉 `mt2-int8sym-cw-q`，
   放入 `mt3-int8sym-cw-q`（从 `C:\\Users\\Trekker-PTL\\hy_bench\\ov\\mt3-int8sym-cw-q` 拷）。
   （APP-141：MT2 不进任何客户包。）
3. **NPU turbo 开**：`LIVECAP_NPU_TURBO=1` 进候选目录（默认开 ⇒ 不写也会开，
   但**显式写**便于 reviewer 核对）。
4. **App 侧 turbo 同步**：dev 树的 `npu_turbo.py` + `tts_engine.py` +
   `npu_delivery_backend.py` 的改动**定点同步**进候选目录 `app/`。
5. **profile / README / MANIFEST**：改成 v1.2 / Hy-MT3 / 音色克隆 / 保留背景音；
   并入 `shared\\DRAFT_minimvp_next_docs.md` 的三项。
6. **自检**：包内不得有 mt2 目录；克隆音色目录只有 preset_A.wav；
   除 preset_A.wav 外无 .wav/.ogg/.mp3/.mp4/.flac；无 CUDA DLL；无 c13。

🔴 纪律：
* 仓库 `live_caption/` 与客户包是**两份独立副本** ⇒ **禁止整目录覆盖**；
* 删除（mt2 目录）前**先确认**它不在任何交付清单里；
* 每步写盘用**临时文件 + os.replace**；写后**逐字节复核**。
* `--dry-run` 默认；`--apply` 才落盘。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
HOME = r'C:\Users\Trekker-PTL'
CAND = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.2.candidate')
EXT_SRC = os.path.join(HOME, 'live_dub_ext')
MT3_SRC = os.path.join(HOME, 'hy_bench', 'ov', 'mt3-int8sym-cw-q')
RESULTS = os.path.join(REPO, 'results', 'app')
EVID = os.path.join(RESULTS, 'app146_candidate_rebuild.json')

LOG = []


def log(m):
    print(m, flush=True)
    LOG.append(m)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def write_atomic(p, data: bytes):
    tmp = p + '.tmp_app146'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, p)


def sync_file(src: str, dst: str, label: str, apply: bool):
    """把 src 的内容定点同步到 dst（**整文件级**，但只用于本轮明确改动的文件）。

    纪律：写前备份；写后逐字节复核（dst == src）。
    """
    sb = read(src)
    if os.path.exists(dst):
        db = read(dst)
        if db == sb:
            return {'label': label, 'dst': dst, 'status': 'already_identical',
                    'sha256': sha(sb), 'bytes': len(sb)}
        bak = dst + '.bak_app146'
        if not os.path.exists(bak):
            shutil.copy2(dst, bak)
    else:
        db = None
        bak = None
    if not apply:
        return {'label': label, 'dst': dst, 'status': 'would_update',
                'old_sha256': sha(db) if db is not None else None,
                'new_sha256': sha(sb), 'old_bytes': len(db) if db is not None else 0,
                'new_bytes': len(sb)}
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    write_atomic(dst, sb)
    after = read(dst)
    assert after == sb, '写后逐字节复核失败：%s' % dst
    return {'label': label, 'dst': dst, 'status': 'updated',
            'old_sha256': sha(db) if db is not None else None,
            'new_sha256': sha(sb), 'old_bytes': len(db) if db is not None else 0,
            'new_bytes': len(sb), 'backup': bak}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    apply = args.apply
    log('模式：%s' % ('APPLY（会落盘）' if apply else 'DRY-RUN（不落盘）'))
    log('候选目录：%s' % CAND)
    steps = []

    # ── ① EXT v0.4.22：只同步本轮改动的文件 ─────────────────────────
    ext_files = ['engine_runtime.py', 'version.py']
    for f in ext_files:
        src = os.path.join(EXT_SRC, 'ext', f)
        dst = os.path.join(CAND, 'ext', 'bridge', f)
        r = sync_file(src, dst, 'EXT %s' % f, apply)
        steps.append(r)
        log('  [EXT] %-22s %s  %s' % (f, r['status'], r.get('new_sha256', '')[:16]))

    # extension/manifest.json
    src = os.path.join(EXT_SRC, 'extension', 'manifest.json')
    dst = os.path.join(CAND, 'ext', 'extension', 'manifest.json')
    r = sync_file(src, dst, 'EXT manifest.json', apply)
    steps.append(r)
    log('  [EXT] manifest.json        %s  %s' % (r['status'], r.get('new_sha256', '')[:16]))

    # ── ② App 侧 turbo：npu_turbo.py 是**新文件**（整文件放入）──────────
    src = os.path.join(REPO, 'live_caption', 'npu_turbo.py')
    dst = os.path.join(CAND, 'app', 'npu_turbo.py')
    r = sync_file(src, dst, 'App npu_turbo.py（新文件）', apply)
    steps.append(r)
    log('  [APP] npu_turbo.py         %s  %s' % (r['status'], r.get('new_sha256', '')[:16]))

    # tts_engine.py / npu_delivery_backend.py：只同步**本轮的改动块**
    # （用 difflib 从 dev 树自动导出改写块 ⇒ 不手抄字符串；唯一命中才替换）
    for fname in ('tts_engine.py', 'npu_delivery_backend.py'):
        src = os.path.join(REPO, 'live_caption', fname)
        dst = os.path.join(CAND, 'app', fname)
        r = sync_turbo_block(src, dst, fname, apply)
        steps.append(r)
        log('  [APP] %-20s %s  %s' % (fname, r['status'], r.get('new_sha256', '')[:16]))

    # ── ③ MT3 替换 MT2 ──────────────────────────────────────────────
    mt_dir = os.path.join(CAND, 'models', 'mt')
    mt2 = os.path.join(mt_dir, 'mt2-int8sym-cw-q')
    mt3 = os.path.join(mt_dir, 'mt3-int8sym-cw-q')
    mt_info = {'mt3_src': MT3_SRC, 'mt2_present_before': os.path.isdir(mt2)}
    if apply:
        # 先把 mt2 挪到**包外**备份（不删！记忆：客户包源目录的素材先移出，不删）
        quarantine = os.path.join(HOME, 'pkg_internal_quarantine', 'app146_mt2')
        if os.path.isdir(mt2):
            os.makedirs(quarantine, exist_ok=True)
            shutil.move(mt2, os.path.join(quarantine, 'mt2-int8sym-cw-q'))
            log('  [MT ] mt2 已移出到 %s（**未删**）' % quarantine)
        if os.path.isdir(MT3_SRC):
            shutil.copytree(MT3_SRC, mt3, dirs_exist_ok=True)
            log('  [MT ] mt3 已拷入 %s' % mt3)
    else:
        log('  [MT ] 将把 mt2 移出到 quarantine，并把 mt3 拷入 models/mt/')
    mt_info['mt3_present_after'] = os.path.isdir(mt3)
    mt_info['mt2_present_after'] = os.path.isdir(mt2)
    if apply:
        mt_info['mt3_files'] = sorted(os.listdir(mt3)) if os.path.isdir(mt3) else []
        mt_info['mt3_bin_bytes'] = (os.path.getsize(os.path.join(mt3, 'openvino_model.bin'))
                                    if os.path.isdir(mt3) and os.path.isfile(
                                        os.path.join(mt3, 'openvino_model.bin')) else None)
    steps.append({'label': 'MT mt3 替换 mt2', 'mt_info': mt_info})

    # ── ④ profile：mt_model 改 mt3 ───────────────────────────────────
    prof_p = os.path.join(CAND, 'package_profile.json')
    prof = json.loads(read(prof_p).decode('utf-8'))
    log('  [PROF] 改前 mt_model=%s' % prof.get('mt_model'))
    prof['mt_model'] = 'mt3-int8sym-cw-q'
    prof['ext_version'] = '0.4.22'
    prof['npu_turbo'] = True
    note = prof.get('note', '')
    prof['note'] = (note + ' MT 已换 Hy-MT3（APP-138/APP-141：MT2 不进包）；'
                     'EXT v0.4.22；NPU turbo 默认开（APP-139）。').strip()
    if apply:
        write_atomic(prof_p, (json.dumps(prof, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    steps.append({'label': 'package_profile.json', 'mt_model': 'mt3-int8sym-cw-q',
                  'ext_version': '0.4.22', 'npu_turbo': True})

    # ── ⑤ turbo 开关：Start_Bridge.bat 显式写环境变量 ────────────────
    bat_p = os.path.join(CAND, 'Start_Bridge.bat')
    bat = read(bat_p).decode('utf-8', errors='replace')
    if 'LIVECAP_NPU_TURBO' not in bat:
        anchor = 'setlocal\r\n' if 'setlocal\r\n' in bat else 'setlocal\n'
        nl = '\r\n' if anchor == 'setlocal\r\n' else '\n'
        ins = (anchor + nl +
               'REM APP-139: NPU turbo default on (NPU_TURBO=YES); set 0 to turn off' + nl +
               'set "LIVECAP_NPU_TURBO=1"' + nl)
        assert bat.count(anchor) == 1, 'setlocal anchor not unique'
        bat = bat.replace(anchor, ins, 1)
        if apply:
            write_atomic(bat_p, bat.encode('utf-8'))
        log('  [BAT ] Start_Bridge.bat 已写入 LIVECAP_NPU_TURBO=1')
    else:
        log('  [BAT ] Start_Bridge.bat 已有 LIVECAP_NPU_TURBO')
    steps.append({'label': 'Start_Bridge.bat turbo 开关',
                  'has_turbo': 'LIVECAP_NPU_TURBO' in bat})

    # ── ⑥ 自检 ───────────────────────────────────────────────────────
    checks = run_checks()
    steps.append({'label': '自检', 'checks': checks})

    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'mode': 'apply' if apply else 'dry-run',
        'candidate': CAND,
        'steps': steps,
        'log': LOG,
    }
    os.makedirs(RESULTS, exist_ok=True)
    with open(EVID, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
    log('\n落盘 -> %s' % EVID)
    bad = [c for c in checks if not c['ok']]
    log('自检：%d 项，FAIL %d 项' % (len(checks), len(bad)))
    for c in bad:
        log('  FAIL: %s — %s' % (c['name'], c['detail']))
    return 0 if not bad else 1


def sync_turbo_block(src, dst, fname, apply):
    """只同步 dev 树里**本轮 turbo 改动**的块（difflib 自动导出，不手抄）。"""
    import difflib
    sb = read(src)
    db = read(dst) if os.path.exists(dst) else None
    if db is None:
        return sync_file(src, dst, 'App %s（新文件）' % fname, apply)
    if db == sb:
        return {'label': 'App %s' % fname, 'dst': dst, 'status': 'already_identical',
                'sha256': sha(sb), 'bytes': len(sb)}
    # difflib 自动导出改写块
    a = db.decode('utf-8', errors='replace').splitlines()
    b = sb.decode('utf-8', errors='replace').splitlines()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        blocks.append({'tag': tag, 'old': '\n'.join(a[i1:i2]), 'new': '\n'.join(b[j1:j2]),
                       'old_n': i2 - i1, 'new_n': j2 - j1})
    # 过滤：只保留**含 turbo 关键词**的块（其余是历史差异，不动）
    turbo_blocks = [bl for bl in blocks
                    if 'turbo' in bl['old'].lower() or 'turbo' in bl['new'].lower()
                    or 'NPU_TURBO' in bl['old'] or 'NPU_TURBO' in bl['new']]
    log('    [%s] difflib 块：%d 个，其中含 turbo 的 %d 个' % (fname, len(blocks), len(turbo_blocks)))
    if not turbo_blocks:
        return {'label': 'App %s' % fname, 'dst': dst, 'status': 'no_turbo_block',
                'sha256': sha(db), 'bytes': len(db)}
    text = db.decode('utf-8', errors='replace')
    NL = '\r\n' if '\r\n' in text else '\n'
    applied = 0
    # 🔴 同一 old 文本可能在文件里出现多次（cp_prefill / cp_decode 的编译行相同）
    #    ⇒ 记录「已用过的命中位置」，逐块按**出现顺序**配对（与 difflib 的顺序一致）。
    used = set()
    skipped_empty = 0
    for bl in turbo_blocks:
        old_t = bl['old'].replace('\n', NL)
        new_t = bl['new'].replace('\n', NL)
        # 🔴 空块（old/new 去掉行尾后皆空）**匹配任何位置** ⇒ 必须跳过
        if not old_t.replace(NL, '').strip() and not new_t.replace(NL, '').strip():
            log('    [%s] 跳过空块（old/new 皆空 ⇒ 会匹配任意位置）' % fname)
            skipped_empty += 1
            continue
        idxs = []
        st = 0
        while True:
            k = text.find(old_t, st)
            if k < 0:
                break
            idxs.append(k)
            st = k + 1
        if not idxs:
            log('    [%s] ★ 块在目标里找不到 ⇒ 不替换：%r' % (fname, bl['old'][:60]))
            continue
        # 🔴 同一 old 文本可能在文件里出现多次（cp_prefill / cp_decode 的编译行相同）
        #    ⇒ 记录「已用过的命中位置」，逐块按**出现顺序**配对
        #    （difflib 的 replace 块顺序 == 文件内顺序 ⇒ 第 k 个块对应第 k 个未用命中）。
        free = [k for k in idxs if k not in used]
        if not free:
            log('    [%s] ★ 块没有可用的命中位置 ⇒ 不替换：%r' % (fname, bl['old'][:60]))
            continue
        if len(free) > 1 and len(turbo_blocks) == 1:
            # 单个块却有多处命中 ⇒ 无法唯一定位 ⇒ fail-closed
            log('    [%s] ★ 块有多处命中（%d 处）且只有 1 个块 ⇒ 无法唯一定位 ⇒ 不替换'
                % (fname, len(free)))
            continue
        k = free[0]
        used.add(k)
        text = text[:k] + new_t + text[k + len(old_t):]
        applied += 1
    if applied + skipped_empty != len(turbo_blocks):
        log('    [%s] ★ 只应用了 %d/%d 个块（跳过空块 %d）⇒ **不落盘**（fail-closed）'
            % (fname, applied, len(turbo_blocks), skipped_empty))
        return {'label': 'App %s' % fname, 'dst': dst, 'status': 'partial_blocks_refused',
                'blocks_total': len(blocks), 'blocks_applied': applied,
                'old_sha256': sha(db), 'bytes': len(db)}
    if applied == 0:
        return {'label': 'App %s' % fname, 'dst': dst, 'status': 'no_block_applied',
                'sha256': sha(db), 'bytes': len(db)}
    if not apply:
        return {'label': 'App %s' % fname, 'dst': dst, 'status': 'would_apply_blocks',
                'blocks_total': len(blocks), 'blocks_applied': applied,
                'old_sha256': sha(db), 'new_sha256': sha(text.encode('utf-8'))}
    bak = dst + '.bak_app146'
    if not os.path.exists(bak):
        shutil.copy2(dst, bak)
    write_atomic(dst, text.encode('utf-8'))
    after = read(dst)
    assert after == text.encode('utf-8'), '写后逐字节复核失败：%s' % dst
    return {'label': 'App %s' % fname, 'dst': dst, 'status': 'blocks_applied',
            'blocks_total': len(blocks), 'blocks_applied': applied,
            'old_sha256': sha(db), 'new_sha256': sha(after), 'backup': bak}


def run_checks():
    """候选目录内容自检（APP-147 的自查条件）。"""
    out = []

    def chk(name, ok, detail=''):
        out.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})

    mt_dir = os.path.join(CAND, 'models', 'mt')
    mts = sorted(os.listdir(mt_dir)) if os.path.isdir(mt_dir) else []
    chk('models/mt 只有 mt3（无 mt2）',
        mts == ['mt3-int8sym-cw-q'], str(mts))

    # 克隆音色目录
    clone_dirs = []
    for root, dirs, files in os.walk(CAND):
        low = os.path.basename(root).lower()
        if 'clone' in low or 'voice' in low:
            for fn in files:
                if fn.lower().endswith('.wav'):
                    clone_dirs.append(os.path.relpath(os.path.join(root, fn), CAND))
    chk('克隆音色目录为空（唯一 wav 是 preset_A.wav）',
        all('preset_A.wav' in d for d in clone_dirs), str(clone_dirs[:5]))

    # 媒体文件
    media = []
    for root, dirs, files in os.walk(CAND):
        for fn in files:
            if fn.lower().endswith(('.wav', '.ogg', '.mp3', '.mp4', '.flac')):
                media.append(os.path.relpath(os.path.join(root, fn), CAND))
    non_preset = [m for m in media if 'preset_A.wav' not in m]
    chk('除 preset_A.wav 外无媒体文件', not non_preset, str(non_preset[:5]))

    # CUDA DLL
    cuda = []
    for root, dirs, files in os.walk(CAND):
        for fn in files:
            if 'cuda' in fn.lower() and fn.lower().endswith('.dll'):
                cuda.append(os.path.relpath(os.path.join(root, fn), CAND))
    chk('无 CUDA DLL', not cuda, str(cuda[:5]))

    # profile
    prof_p = os.path.join(CAND, 'package_profile.json')
    prof = json.loads(read(prof_p).decode('utf-8'))
    chk('profile mt_model = mt3', prof.get('mt_model') == 'mt3-int8sym-cw-q',
        prof.get('mt_model'))
    chk('profile tts_c13 = false（不带 c13）', prof.get('tts_c13') is False,
        prof.get('tts_c13'))
    chk('profile allow_cuda = false', prof.get('allow_cuda') is False, prof.get('allow_cuda'))
    chk('profile allow_clone_voice = true', prof.get('allow_clone_voice') is True,
        prof.get('allow_clone_voice'))
    chk('profile allow_bgkeep = true（保留背景音）', prof.get('allow_bgkeep') is True,
        prof.get('allow_bgkeep'))

    # EXT 版本
    ver_p = os.path.join(CAND, 'ext', 'bridge', 'version.py')
    vt = read(ver_p).decode('utf-8', errors='replace')
    chk('候选目录 EXT = 0.4.22', 'EXT_VERSION = "0.4.22"' in vt,
        vt.split('EXT_VERSION = ')[1].split('\n')[0] if 'EXT_VERSION = ' in vt else '?')

    # EXT 的 mt3 优先链
    er_p = os.path.join(CAND, 'ext', 'bridge', 'engine_runtime.py')
    et = read(er_p).decode('utf-8', errors='replace')
    chk('EXT 查找链含 mt3', '"mt", "mt3-int8sym-cw-q"' in et, '')
    chk('EXT 有 npu_turbo_props（turbo 复用 App）', 'def npu_turbo_props' in et, '')

    # App 侧 turbo
    chk('候选目录 app/npu_turbo.py 存在',
        os.path.isfile(os.path.join(CAND, 'app', 'npu_turbo.py')), '')
    tt = read(os.path.join(CAND, 'app', 'tts_engine.py')).decode('utf-8', errors='replace')
    chk('app/tts_engine.py 已接 turbo', '_npu_compile_props(core, on_log)' in tt, '')
    nb = read(os.path.join(CAND, 'app', 'npu_delivery_backend.py')).decode('utf-8', errors='replace')
    chk('app/npu_delivery_backend.py 已接 turbo', '_turbo_compile_props(core' in nb, '')

    # turbo 开关
    bat = read(os.path.join(CAND, 'Start_Bridge.bat')).decode('utf-8', errors='replace')
    chk('Start_Bridge.bat 有 LIVECAP_NPU_TURBO', 'LIVECAP_NPU_TURBO' in bat, '')

    return out


if __name__ == '__main__':
    sys.exit(main())
