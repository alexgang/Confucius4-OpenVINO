# -*- coding: utf-8 -*-
r"""_app410 — **MiniMVP rc6 构建**（APP-098）。

## 这个脚本做什么

在 **rc5** 的基础上产出 **rc6**（**新目录 + 新 zip**）：

1. **复制 rc5 → rc6**（真实拷贝，不用硬链接 ——
   rc4/rc3 曾因硬链接导致「原地写」串到源目录，见 §161 事故）。
2. **代码从开发树 `live_caption/` 定点覆盖**（APP-098 的改动都在 dev 树）⇒
   **MiniMVP 与 v2.5 共用的部分只改一处**：改 dev 树一次，
   rc6 与将来的 v2.5 都从同一份 dev 树取代码。
3. **应用 0.6B ASR 接线**（rc5 的 `_app310` 用字符串替换做的那套）
   ⇒ 现在改成**同样在 dev 树里维护**（`_ASR06B_*` 常量）⇒ 单一来源。
4. **删掉 R2T2 残留** `models/tokenizer/`（hidden 2048，0.6B 不读它）。
5. **写 `package_profile.json`**（包根）⇒ MiniMVP 形态标记
   ⇒ GUI/CLI 的「去 CUDA」「克隆置灰」**由标记驱动**（不是第二份代码）。
6. **写 `package_profile.json` 之外**还要写 MANIFEST + release.json。

## 纪律

* 🔴 **rc5 一字不动**（只读源）⇒ 本脚本**只写 rc6 目录**。
* 🔴 **不覆盖已存在的 rc6 目录**（APP-055）⇒ 存在即 exit 2。
* 🔴 **APP-098 六.5**：MANIFEST 要列出每个模型目录对应的**源模型 + SHA256**；
  ASR 两个 bin 的 SHA 要与 rc5 一致（decoder 7FBEB8EF…／encoder 0B7463D6…）。
* 🔴 **APP-098 二.5**：README_perftest 按**实测**重写。

用法：
    python results/app/_app410_build_minimvp_rc6.py --dry-run
    python results/app/_app410_build_minimvp_rc6.py --run
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
DEV = os.path.join(REPO, 'live_caption')

BASE_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5')
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc6')
VERSION = '1.0-rc6'
REPORT = os.path.join(HERE, 'app410_minimvp_rc6_build_evidence.json')

#: 🔴 APP-098 六.5：ASR 两个 bin 的 SHA256（**必须与 rc5 一致**）
#:    （reviewer 给的基准值；构建后**实测复核**）
EXPECT_ASR_SHA = {
    'decoder': '7FBEB8EF999DDFBA',
    'encoder': '0B7463D6F952DD64',
}

#: 🔴 APP-098 二.2：R2T2 残留（0.6B 读的是 `asr06b-tokenizer`）
#:    ⇒ 这个目录**没人引用** ⇒ 删掉。
DROP_MODEL_DIRS = ('tokenizer',)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def dir_stats(root):
    n = 0
    b = 0
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            n += 1
            try:
                b += os.path.getsize(p)
            except OSError:
                pass
    return n, b


def patch_once(text, old, new, tag):
    """字符串替换 + **唯一命中**断言（项目铁律：不许静默没替换上）。"""
    cnt = text.count(old)
    if cnt != 1:
        raise RuntimeError('patch %s: 期望命中 1 次，实际 %d 次' % (tag, cnt))
    return text.replace(old, new, 1)


def copy_dev_files(dst_app, names):
    """从 dev 树逐字复制到包的 app/（**行尾归一 + 逐字节复核**）。"""
    out = []
    for name in names:
        src = os.path.join(DEV, name)
        dst = os.path.join(dst_app, name)
        if not os.path.isfile(src):
            raise RuntimeError('dev 树缺文件：%s' % src)
        with open(src, 'rb') as f:
            data = f.read()
        # 🔴 包内统一 **LF**（rc5 包内就是 LF；Windows 上被 autocrlf 改过会不一致）
        norm = data.replace(b'\r\n', b'\n')
        with open(dst, 'wb') as f:
            f.write(norm)
        # 逐字节复核（归一化后）
        with open(dst, 'rb') as f:
            again = f.read()
        if again != norm:
            raise RuntimeError('写入后复核不一致：%s' % name)
        out.append(name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    dry = not args.run

    ev = {
        'built_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'version': VERSION,
        'correction': 'APP-098',
        'base_pkg': BASE_PKG,
        'dst_pkg': DST_PKG,
        'dry_run': dry,
        'actions': [],
    }

    # ── 闸门 ①：rc5 在；rc6 不在 ──────────────────────────────────
    if not os.path.isdir(BASE_PKG):
        print('!! rc5 不存在：%s' % BASE_PKG)
        return 2
    if os.path.exists(DST_PKG):
        print('!! rc6 目录已存在（拒绝覆盖，APP-055）：%s' % DST_PKG)
        return 2

    # ── 闸门 ②：rc5 指纹（事后复核「一字未动」）───────────────────
    rc5_zip = os.path.join(HOME, 'shared', 'minimvp',
                           'Confucius4_LiveCaption_MiniMVP_v1.0-rc5_perftest.zip')
    rc5_fp = {'zip_sha256': sha256_file(rc5_zip) if os.path.exists(rc5_zip) else None,
              'zip_bytes': os.path.getsize(rc5_zip) if os.path.exists(rc5_zip) else None}
    n5, b5 = dir_stats(BASE_PKG)
    rc5_fp.update(files=n5, bytes=b5,
                  mtime=datetime.datetime.fromtimestamp(
                      os.path.getmtime(BASE_PKG)).isoformat(timespec='seconds'))
    ev['rc5_fingerprint_before'] = rc5_fp

    # ── 闸门 ③：dev 树必须已含 APP-098 的改动 ─────────────────────
    dev_app = os.path.join(DEV, 'live_caption_app.py')
    with open(dev_app, encoding='utf-8') as f:
        dev_src = f.read()
    required = {
        'package_profile imported': 'import package_profile',
        'no cuda_q8 engine': "'cuda_q8'",
        'no cuda_q4 engine': "'cuda_q4'",
        'stdout reconfigure': "reconfigure(encoding='utf-8'",
    }
    dev_check = {}
    for k, needle in required.items():
        dev_check[k] = (needle not in dev_src) if k.startswith('no ') \
            else (needle in dev_src)
    ev['dev_tree_checks'] = dev_check
    bad = [k for k, v in dev_check.items() if not v]
    if bad:
        print('!! dev 树未含 APP-098 改动：%s' % bad)
        return 2

    if dry:
        print('[dry-run] 将创建：%s' % DST_PKG)
        print('[dry-run] 删 R2T2 残留：%s' % (list(DROP_MODEL_DIRS),))
        print('[dry-run] 从 dev 树覆盖 app/ 全部 .py')
        print('[dry-run] 写 package_profile.json（minimvp 形态）')
        print('[dry-run] 重写 README_perftest.txt')
        print(json.dumps(ev, ensure_ascii=False, indent=1))
        return 0

    t0 = time.time()

    # ── ① 复制 rc5 → rc6（真实拷贝）───────────────────────────────
    print('[1/7] 复制 rc5 → rc6（真实拷贝，不用硬链接）…')
    shutil.copytree(BASE_PKG, DST_PKG, symlinks=True)
    ev['actions'].append('copy rc5 -> rc6 (real copy, no hardlink)')

    dst_app = os.path.join(DST_PKG, 'app')

    # ── ② 从 dev 树覆盖 app/*.py（**共用部分只改一处**）────────────
    # 🔴 覆盖**全部** .py（rc5 的 app/ 是 rc4→rc3 累积的旧副本，
    #    与 dev 树已经分叉 12 个文件 ⇒ 必须**全量对齐**，否则
    #    「包里代码对」与「dev 树代码对」会出现两套真相）。
    print('[2/7] 从 dev 树覆盖 app/*.py（全量对齐）…')
    names = sorted(f for f in os.listdir(dst_app) if f.endswith('.py'))
    # 🔴 `asr06b_backend.py` rc5 已有；dev 树也有 ⇒ 一并覆盖（含 APP-098 二.3 的
    #    EXECUTION_DEVICES 打印）。
    copied = copy_dev_files(dst_app, names)
    ev['actions'].append('overwrite app/*.py from dev tree: %d files' % len(copied))
    ev['copied_from_dev'] = copied

    # 🔴 dev 树**新增**的模块也要带过去（**逐个列举，不自动全带**）。
    #   🔴 **为什么不自动全带**：dev 树有 200+ 个 .py，其中大量是**开发期脚本**
    #      （`diag_*` / `sync_*` / `_app*` / `compress_*` / `gen_*`），
    #      还有**明确不进客户包**的（APP-088：`tts_cuda*` / `backends_torch.py`
    #      —— torch 与 CUDA 不随包分发）。
    #   ⇒ **只带 MiniMVP 真正需要的**（下面逐个写明理由）。
    EXTRA_FROM_DEV = {
        # 🔴 APP-098：包形态标记（**共用代码的唯一开关来源**）
        'package_profile.py': 'APP-098：MiniMVP/完整版形态标记（CUDA/克隆音色开关）',
        # 🔴 APP-086②：克隆策略层 —— 但**只有提供克隆音色的包才 import**
        #    （dev 树已改成条件 import）⇒ MiniMVP **不需要**它 ⇒ 不带。
        #    （因此下面**不列** `clone_voice.py` ⇒ MiniMVP 包里没有这个文件，
        #      而 dev 树的 `live_caption_app.py` 也不会去 import 它。）
    }
    extra = []
    for f, _why in EXTRA_FROM_DEV.items():
        src = os.path.join(DEV, f)
        if not os.path.isfile(src):
            raise RuntimeError('dev 树缺文件：%s' % src)
        extra.append(f)
    if extra:
        copy_dev_files(dst_app, extra)
        ev['actions'].append('add app modules from dev tree: %s' % extra)
    ev['added_from_dev'] = extra
    ev['added_from_dev_why'] = EXTRA_FROM_DEV

    # 🔴 **闸门**：包内**不得**出现 CUDA / torch 相关文件（APP-088 / APP-098 一.1）
    forbidden = [f for f in os.listdir(dst_app)
                 if f.endswith('.py') and ('cuda' in f.lower() or 'torch' in f.lower())]
    ev['forbidden_files_in_app'] = forbidden
    if forbidden:
        print('!! 包内出现 CUDA/torch 相关文件：%s' % forbidden)
        return 2

    # ── ③ 删 R2T2 残留（models/tokenizer）─────────────────────────
    print('[3/7] 删除 R2T2 残留 models/tokenizer…')
    models = os.path.join(DST_PKG, 'models')
    dropped = []
    for d in DROP_MODEL_DIRS:
        p = os.path.join(models, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
            dropped.append(d)
    ev['actions'].append('drop R2T2 residue: %s' % dropped)
    ev['dropped'] = dropped

    # ── ④ 写 package_profile.json（MiniMVP 形态标记）───────────────
    print('[4/7] 写 package_profile.json…')
    profile = {
        'profile': 'minimvp',
        'allow_cuda': False,
        'allow_clone_voice': False,
        'target_langs': 10,
        'note': ('APP-098：MiniMVP 不提供音色克隆、不提供 NVIDIA/CUDA 后端；'
                 '目标语言 10 种。**标记只驱动行为，不复制代码** ⇒ '
                 'MiniMVP 与 v2.5 共用同一份 dev 树代码。'),
    }
    prof_path = os.path.join(DST_PKG, 'package_profile.json')
    with open(prof_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
        f.write('\n')
    ev['actions'].append('write package_profile.json (minimvp)')

    # ── ⑤ MANIFEST：模型目录 → 源模型 + SHA256（APP-098 六.5）──────
    print('[5/7] 生成 MANIFEST（模型身份）…')
    model_identity = build_model_identity(models)
    ev['model_identity'] = model_identity

    # 🔴 ASR 两个 bin 的 SHA 复核（必须与 reviewer 给的基准一致）
    # ⚠️ **两个 bin 的文件名不同**（实测 rc6）：
    #    decoder = `openvino_model.bin`（OV 默认名）
    #    encoder = `ov-encoder-06b-fp16-static.bin`（导出时的名字）
    #    ⇒ 早先按 `openvino_model.bin` 找 encoder ⇒ 找不到 ⇒ SHA 为 None
    #    ⇒ 判据误报「不符」⇒ **不是模型变了，是判据写错了**。
    asr_sha = {
        'decoder': _sha_of(models, 'asr06b-decoder-int8', 'openvino_model.bin'),
        'encoder': _sha_of(models, 'asr06b-encoder-fp16',
                            'ov-encoder-06b-fp16-static.bin'),
    }
    ev['asr_bin_sha'] = asr_sha
    ev['asr_bin_sha_expected_prefix'] = EXPECT_ASR_SHA
    ev['asr_bin_sha_match'] = {
        'decoder': (asr_sha['decoder'] or '').upper().startswith(EXPECT_ASR_SHA['decoder']),
        'encoder': (asr_sha['encoder'] or '').upper().startswith(EXPECT_ASR_SHA['encoder']),
    }
    # 🔴 **「找不到」与「不匹配」必须分开**（判据自身的坑）：
    #   `None` ⇒ 文件不在 ⇒ 那是**构建失败**，不是「SHA 不符」。
    ev['asr_bin_found'] = {k: bool(v) for k, v in asr_sha.items()}
    if not all(ev['asr_bin_found'].values()):
        print('!! ASR bin 文件缺失：%s' % ev['asr_bin_found'])
        return 2
    if not all(ev['asr_bin_sha_match'].values()):
        print('!! ASR bin SHA 与基准不符：%s' % ev['asr_bin_sha_match'])
        return 2

    # ── ⑥ README_perftest（APP-098 二.5：按实测重写）──────────────
    print('[6/7] 重写 README_perftest.txt + bat 加 PYTHONIOENCODING…')
    from _app411_rc6_readme import write_readme
    readme_info = write_readme(DST_PKG, model_identity, ev)
    ev['readme'] = readme_info
    ev['actions'].append('rewrite README_perftest.txt')

    # 🔴🔴🔳 **APP-098 二.1：bat 里设 `PYTHONIOENCODING=utf-8`**。
    #   ⚠️ **为什么 bat 里也要设**（代码里的 reconfigure 是**兜底**）：
    #      `PYTHONIOENCODING` 在**解释器启动时**读 ⇒ 早于 Python 代码里的
    #      `sys.stdout.reconfigure()` ⇒ 两者**互补**：
    #        · bat 里设 ⇒ 启动即生效（含 C 层/子进程）；
    #        · 代码里 reconfigure ⇒ **从命令行直接跑**（不经 bat）也生效。
    #   ⇒ 两个都要有（reviewer 原话：「入口处加 …，bat 里设 PYTHONIOENCODING=utf-8」）。
    bat_edits = []
    for bat_name in ('Start_LiveCaption.bat', 'Diagnose.bat'):
        bp = os.path.join(DST_PKG, bat_name)
        if not os.path.isfile(bp):
            continue
        with open(bp, 'r', encoding='utf-8', newline='') as f:
            bt = f.read()
        if 'PYTHONIOENCODING' in bt:
            continue
        if 'set PYTHONUTF8=1' not in bt:
            raise RuntimeError('bat 缺少 PYTHONUTF8 行，无法安全插入：%s' % bat_name)
        # 🔴 **唯一命中**断言（不静默没替换上）
        cnt = bt.count('set PYTHONUTF8=1')
        if cnt != 1:
            raise RuntimeError('%s: set PYTHONUTF8=1 命中 %d 次' % (bat_name, cnt))
        bt = bt.replace('set PYTHONUTF8=1',
                        'set PYTHONUTF8=1\r\n'
                        'rem APP-098 二.1：中文输出重定向到文件时不再 UnicodeEncodeError\r\n'
                        'set PYTHONIOENCODING=utf-8')
        with open(bp, 'w', encoding='utf-8', newline='') as f:
            f.write(bt)
        bat_edits.append(bat_name)
    ev['bat_edits'] = bat_edits
    ev['actions'].append('bat: set PYTHONIOENCODING=utf-8 in %s' % bat_edits)

    # ── ⑦ release.json + 指纹 ────────────────────────────────────
    print('[7/7] 更新 release.json + 指纹…')
    rel_path = os.path.join(DST_PKG, 'release.json')
    rel = {}
    if os.path.isfile(rel_path):
        try:
            with open(rel_path, encoding='utf-8') as f:
                rel = json.load(f)
        except Exception:
            rel = {}
    rel.update({'release': True, 'version': VERSION,
                'asr_model': 'Qwen3-ASR-0.6B',
                'asr_recipe': 'mask2 INT8 (per-channel weights, FP16 lm_head, attention_mask port)',
                'asr_engines': ['gpu_int8', 'npu_int8'],
                'corrections': ['APP-096', 'APP-098'],
                'package_profile': 'package_profile.json'})
    with open(rel_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
        f.write('\n')
    ev['actions'].append('update release.json')

    n6, b6 = dir_stats(DST_PKG)
    ev['rc6'] = {'files': n6, 'bytes': b6,
                 'gib': round(b6 / (1024 ** 3), 3),
                 'mtime': datetime.datetime.fromtimestamp(
                     os.path.getmtime(DST_PKG)).isoformat(timespec='seconds')}
    ev['rc5_fingerprint_after'] = {
        'zip_sha256': sha256_file(rc5_zip) if os.path.exists(rc5_zip) else None,
        'files': dir_stats(BASE_PKG)[0], 'bytes': dir_stats(BASE_PKG)[1]}
    ev['rc5_unchanged'] = (
        ev['rc5_fingerprint_before']['zip_sha256']
        == ev['rc5_fingerprint_after']['zip_sha256']
        and ev['rc5_fingerprint_before']['files']
        == ev['rc5_fingerprint_after']['files'])
    ev['build_s'] = round(time.time() - t0, 1)

    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[7/7] 完成：%s（%d 文件 / %.3f GB，用时 %.1f s）'
          % (DST_PKG, n6, b6 / (1024 ** 3), ev['build_s']))
    print('rc5 未动：%s' % ev['rc5_unchanged'])
    return 0


def _sha_of(models, subdir, fname):
    p = os.path.join(models, subdir, fname)
    if not os.path.isfile(p):
        return None
    return sha256_file(p)


#: 🔴 APP-098 六.5：模型目录 → **源模型**（人工核对的映射；写进 MANIFEST）
MODEL_SOURCE = {
    'asr06b-decoder-int8': ('Qwen3-ASR-0.6B', 'ov-dec-06b-embed-mask2-int8sym',
                             'OV IR，mask2 INT8（per-channel 权重），含 attention_mask 端口，'
                             '无 KV cache，静态长度 512，右对齐'),
    'asr06b-encoder-fp16': ('Qwen3-ASR-0.6B', 'ov-encoder-06b-fp16-static',
                             'OV IR，FP16 静态形状（[1,128,2400]），iGPU/NPU 共用同一份'),
    'asr06b-tokenizer': ('Qwen3-ASR-0.6B', '（HF 目录，未导出 OV）',
                         'tokenizer + feature extractor（transformers 直接读）'),
    'embed_tokens_06b_f16.npy': ('Qwen3-ASR-0.6B', '（权重表，FP16）',
                                 '文本 embedding 表 [151936, 1024]（hidden=1024，'
                                 '与 R2T2 的 2048 不同 ⇒ 独立文件名）'),
    'mt/mt2-int4sym-cw-q': ('Hy-MT2-1.8B', 'mt2-int4sym-cw-q',
                            'OV IR，INT4 对称按通道（INT4-CW），GPU/NPU 通吃'),
    'qwen3tts': ('Qwen3-TTS', '（BabelVox 运行时目录）',
                 'Qwen3-TTS 权重 + 声码器；codec_language_id 共 10 种'
                 '（chinese 2055 / english 2050 / german 2053 / italian 2070 / '
                 'portuguese 2071 / spanish 2054 / japanese 2058 / korean 2064 / '
                 'french 2061 / russian 2069）'),
}


def build_model_identity(models_root):
    """列出每个模型目录的**源模型 + SHA256**（APP-098 六.5）。"""
    out = {}
    for rel, (src_model, artifact, note) in MODEL_SOURCE.items():
        p = os.path.join(models_root, *rel.split('/'))
        info = {'source_model': src_model, 'artifact': artifact, 'note': note,
                'exists': os.path.exists(p)}
        if os.path.isdir(p):
            files = []
            n = 0
            b = 0
            for dp, _dn, fn in os.walk(p):
                for f in fn:
                    fp = os.path.join(dp, f)
                    n += 1
                    try:
                        b += os.path.getsize(fp)
                    except OSError:
                        pass
                    files.append({'name': os.path.relpath(fp, p).replace('\\', '/'),
                                  'bytes': os.path.getsize(fp),
                                  'sha256': sha256_file(fp)})
            info.update(files=n, bytes=b, file_list=files)
        elif os.path.isfile(p):
            info.update(files=1, bytes=os.path.getsize(p),
                        file_list=[{'name': os.path.basename(p),
                                    'bytes': os.path.getsize(p),
                                    'sha256': sha256_file(p)}])
        out[rel] = info
    return out


if __name__ == '__main__':
    sys.exit(main())
