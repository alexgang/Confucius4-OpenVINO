#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §5：把 **dev 树的 App 侧运行时模块**定点同步进 **v2.5 客户包**。

纪律：
  * **不覆盖旧版本目录/zip**（v2.4 原封不动）；
  * **不整目录覆盖** ⇒ 只同步**逐个点名**的运行时 .py（定点、唯一命中）；
  * 写盘走 **临时文件 → os.replace**；写后逐文件 **SHA256 复核 + ast.parse**；
  * **不碰 `app/asr_spk/`**（那是 ASR 模块的文件，不是 App 模块的）。

v2.5 的基底 = v2.4（重型资源：models / python / ext / docs 全部原样带过来）
⇒ 只把 **App 侧代码**换成 dev 树当前版本（dev 树含 APP-114/115 的语速上限等
   11-16/17 才落地的改动，v2.4 包里**没有** ⇒ 必须以 dev 为准）。
"""
import ast
import hashlib
import json
import os
import shutil
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEV = os.path.join(REPO, 'live_caption')
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'
PKG_APP = os.path.join(PKG, 'app')

# App 侧**运行时模块**清单（= sp5 / rc11 已验证在跑的集合
#   ＋ 完整版专用的 clone_voice.py
#   ＋ 交付洁净度闸门需要的 v23_preset_only.py / assert_pkg_clean.py）
RUNTIME_PY = [
    # —— 主程序与引擎 ——
    'live_caption_app.py', 'tts_service.py', 'tts_worker.py', 'tts_engine.py',
    'tts_engine_patch.py', 'time_stretch.py', 'translator.py',
    'device_config.py', 'package_profile.py',
    # —— ASR / MT 侧 App 胶水 ——
    'backends.py', 'asr06b_stateful_backend.py', 'streaming_asr.py',
    'seg_stream.py', 'segment_encoder_backend.py', 'npu_delivery_backend.py',
    'npu_embeds_backend.py', 'speaker_assets.py', 'speaker_tracker.py',
    'speaker_voice.py', 'clone_collector.py',
    # —— 音频 / 界面 ——
    'audio_source.py', 'caption_render.py', 'gui_status.py',
    'offline_reader.py', 'offline_reader_gui.py', 'win_clickthrough.py',
    # —— 完整版专属：克隆策略层（package_profile.allow_clone_voice()==True）——
    'clone_voice.py',
    # —— CUDA 路线（完整版包里仍保留代码；APP-098 已从 GUI 移除该档）——
    'tts_cuda.py', 'tts_cuda_sidecar.py',
    # —— 交付洁净度闸门 ——
    'v23_preset_only.py', 'assert_pkg_clean.py',
    # —— 包内小工具 ——
    'audio_check.py', 'selftest_audio_sources.py',
]

# 🔴 这些**不是** App 模块的文件 ⇒ 一个都不许动
FORBIDDEN_PREFIX = ('asr_spk' + os.sep,)


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'dev': DEV, 'pkg': PKG, 'files': [], 'errors': []}
    if not os.path.isdir(PKG):
        print('FAIL: 目标包目录不存在 %s' % PKG)
        return 2
    if not os.path.isdir(PKG_APP):
        print('FAIL: 包内 app/ 不存在')
        return 2

    for name in RUNTIME_PY:
        src = os.path.join(DEV, name)
        dst = os.path.join(PKG_APP, name)
        if not os.path.isfile(src):
            rep['errors'].append('dev 缺文件: %s' % name)
            print('  [SKIP] dev 缺 %s' % name)
            continue
        if any(name.startswith(p) for p in FORBIDDEN_PREFIX):
            rep['errors'].append('禁止同步: %s' % name)
            continue
        data = open(src, 'rb').read()
        before = sha256(dst) if os.path.isfile(dst) else None
        # 写盘：临时文件 → os.replace（不截断原文件）
        tmp = dst + '.tmp_app116'
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dst)
        # 写后复核
        got = open(dst, 'rb').read()
        ok_bytes = (got == data)
        ok_sha = (sha256(dst) == hashlib.sha256(data).hexdigest())
        try:
            ast.parse(got.decode('utf-8'))
            ok_ast = True
        except Exception as e:
            ok_ast = False
            rep['errors'].append('ast.parse 失败 %s: %s' % (name, e))
        rec = {'file': name, 'bytes': len(data),
               'sha256': hashlib.sha256(data).hexdigest(),
               'sha_before': before, 'changed': before != hashlib.sha256(data).hexdigest(),
               'ok_bytes': ok_bytes, 'ok_sha': ok_sha, 'ok_ast': ok_ast}
        rep['files'].append(rec)
        flag = 'OK  ' if (ok_bytes and ok_sha and ok_ast) else 'FAIL'
        print('  [%s] %-30s %7d B  %s%s'
              % (flag, name, len(data), rec['sha256'][:12],
                 '  (已更新)' if rec['changed'] else '  (本就一致)'))

    # 🔴 复核：包内 app/ 不应再有「本地模块缺失」
    #   🔴 判据必须**排除标准库** ⇒ 用 `sys.stdlib_module_names`（写死清单会漏，
    #      本轮就把 argparse/json/os/… 全报成「缺失」⇒ 假 FAIL）。
    pkg_py = {f for f in os.listdir(PKG_APP) if f.endswith('.py')}
    third_party = {
        'numpy', 'scipy', 'PIL', 'av', 'babelvox', 'openvino', 'openvino_genai',
        'torch', 'transformers', 'soundcard', 'sounddevice', 'soundfile',
        'librosa', 'fitz', 'pypdf', 'safetensors', 'qwen_asr',
        'faster_qwen3_tts', 'backends_torch', 'tts_ov', 'yaml', 'requests',
        'huggingface_hub', 'onnxruntime', 'typing_extensions', 'packaging',
    }
    # app/asr_spk/ 里的（ASR 模块的资产，不在本模块范围）
    asr_assets = {'asr052_speaker_tracker_api', 'asr052_spk_runtime',
                  'asr_thread_defaults', 'asr_spk_window',
                  'asr_runtime_switches', 'asr_spk_cluster_v2'}
    miss = []
    for name in sorted(pkg_py):
        p = os.path.join(PKG_APP, name)
        try:
            t = ast.parse(open(p, encoding='utf-8').read())
        except Exception:
            continue
        for n in ast.walk(t):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name.split('.')[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                mods = [n.module.split('.')[0]]
            for m in mods:
                if (m + '.py') in pkg_py:
                    continue
                if os.path.isdir(os.path.join(PKG_APP, m)):
                    continue
                if m in sys.stdlib_module_names:
                    continue
                if m in third_party or m in asr_assets:
                    continue
                miss.append('%s -> %s' % (name, m))
    rep['missing_local_modules'] = sorted(set(miss))
    print('\n  包内仍缺本地模块：%s' % (rep['missing_local_modules'] or '无'))

    out = os.path.join(REPO, 'results', 'app', 'app116_sync_v25_evidence.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('  证据：%s' % out)
    bad = [r for r in rep['files'] if not (r['ok_bytes'] and r['ok_sha'] and r['ok_ast'])]
    return 1 if (bad or rep['missing_local_modules']) else 0


if __name__ == '__main__':
    sys.exit(main())
