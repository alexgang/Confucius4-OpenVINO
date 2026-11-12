# -*- coding: utf-8 -*-
r"""_app488 — **APP-102 §3**：rc8 包目录上的 6 项验收（打完 zip 后跑）。

 1. 包内无旧解码器目录；
 2. app/ 里 grep 旧解码器字面 = 0；
 3. MANIFEST 的 decoder=0059531a…d6a3 / encoder=0b7463d6… 且与源目录逐项一致；
 4. EXT 是 v0.4.8（extension/manifest.json + release.json commit）；
 5. 用**包内 python** 跑一次 `--check`；
 6. 在**包目录**再跑一遍 §2 的整链冒烟（ASR NPU + MT GPU.0 + TTS GPU.0）。

另核对：zip 清单文件数与包目录一致、顶层目录名、包内违禁素材登记。
设备作业 ⇒ 持 MACHINE_LOCK；json 写 lock 的 module/pid/started/ended/timing_valid。
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc8')
PKG_NAME = os.path.basename(PKG)
ZIP = os.path.join(HOME, 'shared', 'minimvp', PKG_NAME + '_perftest.zip')
OUTROOT = os.path.join(HERE, 'app488_app102_rc8_acceptance')
REPORT = os.path.join(HERE, 'app488_app102_rc8_acceptance.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
AUDIO = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest\smoke30.wav'
DECODER_SHA = ('0059531a2b4ccd4ceb3f4c1dc3519e68421a310a262'
               'baba4dc55e603b600d6a3')
ENCODER_PREFIX = '0b7463d6f952dd64'
EXT_COMMIT = '817abcbe30c213844cda6f32c81361524ab53de8'
LEGACY_DIR = 'ov-dec-06b-embed-mask2-int8sym'

TTS_FINAL_RE = re.compile(r'\[TTS\] 最终统计（close 后）：提交\s*(\d+)\s+'
                          r'播完\s*(\d+)\s+丢弃\s*(\d+)')
RTF_RE = re.compile(r'RTF\(计算\)\s*([\d.]+)')
EXEC_RE = re.compile(r'\[asr06b-stateful\] EXECUTION_DEVICES：encoder=(\S+?)，decoder=(\S+?)（')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def acquire_lock(tag):
    payload = 'app %d %s %s' % (os.getpid(), now(), tag)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, payload.encode('utf-8'))
        os.close(fd)
        return payload
    except FileExistsError:
        return None


def release_own_lock(payload):
    try:
        if os.path.exists(LOCK) and open(LOCK, encoding='utf-8',
                                         errors='replace').read() == payload:
            os.remove(LOCK)
            return True
    except Exception:
        pass
    return False


def dir_files(root):
    out = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), root).replace('\\', '/'))
    return out


def main():
    os.makedirs(OUTROOT, exist_ok=True)
    py = os.path.join(PKG, 'python', 'python.exe')
    app_py = os.path.join(PKG, 'app', 'live_caption_app.py')
    ev = {'at': now(), 'pkg': PKG, 'zip': ZIP,
          'correction': 'APP-102 §3', 'items': {},
          'lock': {'module': 'app', 'pid': os.getpid(), 'started': None,
                   'ended': None, 'timing_valid': False}}

    # ① 无旧解码器目录
    legacy_dirs = [os.path.relpath(os.path.join(dp, d), PKG)
                   for dp, dn, _ in os.walk(os.path.join(PKG, 'models'))
                   for d in dn if LEGACY_DIR in d]
    ev['items']['1_no_legacy_dir'] = {'pass': not legacy_dirs,
                                      'hits': legacy_dirs}

    # ② app/ 里旧解码器字面
    hits = []
    for dp, _dn, fn in os.walk(os.path.join(PKG, 'app')):
        for f in fn:
            p = os.path.join(dp, f)
            if not f.endswith(('.py', '.json', '.txt', '.md')):
                continue
            try:
                n = open(p, encoding='utf-8', errors='replace').read().count('mask2')
            except OSError:
                continue
            if n:
                hits.append({'file': os.path.relpath(p, PKG), 'count': n})
    ev['items']['2_app_grep_zero'] = {'pass': not hits, 'hits': hits}

    # ③ MANIFEST 与源目录
    mp = os.path.join(PKG, 'app', 'MANIFEST.json')
    m = json.load(open(mp, encoding='utf-8'))
    dec = next((r['sha256'] for r in
                m['models']['asr06b-decoder-int8']['files']
                if r['name'] == 'openvino_model.bin'), None)
    enc = next((r['sha256'] for r in
                m['models']['asr06b-encoder-fp16']['files']
                if r['name'].endswith('.bin')), None)
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))
    import manifest_gen
    ok_verify, bad = manifest_gen.verify_manifest(PKG)
    ev['items']['3_manifest'] = {
        'decoder_sha256': dec, 'encoder_sha256': enc,
        'decoder_ok': dec == DECODER_SHA,
        'encoder_ok': bool(enc and enc.lower().startswith(ENCODER_PREFIX)),
        'decoder_source': m['models']['asr06b-decoder-int8']['source_path'],
        'embed_source': m['models']['embed_tokens_06b_f16.npy']['source_path'],
        'all_match': m['all_match'], 'verify_ok': ok_verify,
        'verify_bad': bad[:5],
        'pass': (dec == DECODER_SHA
                 and bool(enc and enc.lower().startswith(ENCODER_PREFIX))
                 and m['all_match'] and ok_verify),
    }

    # ④ EXT 0.4.8
    emf = json.load(open(os.path.join(PKG, 'ext', 'extension', 'manifest.json'),
                         encoding='utf-8'))
    erel = json.load(open(os.path.join(PKG, 'ext', 'release.json'),
                          encoding='utf-8'))
    ev['items']['4_ext_048'] = {
        'manifest_version': emf.get('version'), 'commit': erel.get('commit'),
        'accel_usage_py': os.path.isfile(
            os.path.join(PKG, 'ext', 'bridge', 'accel_usage.py')),
        'pass': (emf.get('version') == '0.4.8'
                 and erel.get('commit') == EXT_COMMIT),
    }

    # zip 清单（不做 SHA 校验，用户规则）
    pkg_files = dir_files(PKG)
    with zipfile.ZipFile(ZIP) as zf:
        names = zf.namelist()
    top_ok = all(n.startswith(PKG_NAME + '/') for n in names)
    ev['zip_check'] = {
        'zip_bytes': os.path.getsize(ZIP), 'n_pkg_files': len(pkg_files),
        'n_zip_entries': len(names), 'counts_equal': len(names) == len(pkg_files),
        'top_dir_ok': top_ok,
        'zip_has_legacy_path': any(LEGACY_DIR in n for n in names),
    }
    ev['zip_check']['pass'] = (ev['zip_check']['counts_equal'] and top_ok
                               and not ev['zip_check']['zip_has_legacy_path'])

    # 违禁素材（文件名级，如实登记）
    import re as _re
    pat = _re.compile(r'preset_[BC]|clone_[A-Za-z0-9]|_spoken|transcript_|'
                      r'segments_|smoke30|spktest|clip_10min|260902', _re.I)
    name_hits = [os.path.relpath(os.path.join(dp, f), PKG)
                 for dp, _dn, fn in os.walk(PKG) for f in fn
                 if pat.search(f)]
    wavs = [p for p in pkg_files if p.lower().endswith('.wav')]
    ev['forbidden_material'] = {
        'name_hits': name_hits,
        'name_hit_note': ('命中项均为代码文件 / 第三方头文件，不是录音、'
                          '克隆音色或同事声音素材；未改包'),
        'n_wav': len(wavs),
        'package_wavs': [p for p in wavs if not p.startswith('python/')],
        'note': ('包内业务 wav 只有 models/qwen3tts/voices/preset_A.wav'
                 '（预设音色 A）；其余为 python 自带 scipy 测试数据'),
    }

    # ⑤⑥ 设备作业：持锁
    payload = acquire_lock('app102_rc8_acceptance')
    if not payload:
        ev['verdict'] = 'SKIPPED_LOCK_BUSY'
        json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return 1
    ev['lock']['started'] = now()
    try:
        # ⑤ 包内 python --check
        cp = os.path.join(OUTROOT, 'check.log')
        with open(cp, 'wb') as lf:
            p = subprocess.run([py, '-s', app_py, '--check'], cwd=PKG,
                               stdout=lf, stderr=subprocess.STDOUT, timeout=600)
        cl = open(cp, 'rb').read().decode('utf-8', errors='replace')
        ev['items']['5_pkg_check'] = {
            'exit_code': p.returncode, 'log': cp, 'log_bytes': len(cl),
            'asr_section': ('ASR 后端' in cl),
            'n_ok_lines': len(re.findall(r'\[ OK \]', cl)),
            'n_asr_stateful_lines': len(re.findall(r'stateful', cl, re.I)),
            'tail': cl[-1200:],
            'pass': p.returncode == 0 and 'ASR 后端' in cl,
        }
        print('[5] --check exit=%s OK行=%s' %
              (p.returncode, ev['items']['5_pkg_check']['n_ok_lines']), flush=True)

        # ⑥ 包目录再跑整链冒烟
        lp = os.path.join(OUTROOT, 'chain.log')
        tp = os.path.join(OUTROOT, 'chain.txt')
        cmd = [py, '-s', app_py, '--cli', '--file', AUDIO,
               '--max-seconds', '30', '--out', tp,
               '--engine', 'npu_int8', '--asr-device', 'NPU',
               '--translate', 'zh', '--tts', 'on', '--tts-voice', 'A',
               '--mt-device', 'GPU.0', '--tts-device', 'GPU.0']
        t0 = time.time()
        with open(lp, 'wb') as lf:
            cp2 = subprocess.run(cmd, cwd=PKG, stdout=lf,
                                 stderr=subprocess.STDOUT, timeout=900)
        lg = open(lp, 'rb').read().decode('utf-8', errors='replace')
        sub = (open(tp, encoding='utf-8', errors='replace').read().strip()
               if os.path.isfile(tp) else '')
        tf = TTS_FINAL_RE.search(lg)
        rt = RTF_RE.search(lg)
        ex = EXEC_RE.search(lg)
        ev['items']['6_pkg_chain'] = {
            'exit_code': cp2.returncode, 'wall_s': round(time.time() - t0, 1),
            'log': lp, 'output': tp, 'output_chars': len(sub),
            'output_head': sub[:300], 'replacement_chars': sub.count('\ufffd'),
            'asr_rtf': float(rt.group(1)) if rt else None,
            'asr_exec_encoder': ex.group(1) if ex else None,
            'asr_exec_decoder': ex.group(2) if ex else None,
            'tts_submitted': int(tf.group(1)) if tf else None,
            'tts_played': int(tf.group(2)) if tf else None,
            'pass': bool(cp2.returncode == 0 and sub and '\ufffd' not in sub
                         and tf and int(tf.group(2)) >= 1),
        }
        print('[6] chain exit=%s rtf=%s tts_played=%s' %
              (cp2.returncode, ev['items']['6_pkg_chain']['asr_rtf'],
               ev['items']['6_pkg_chain']['tts_played']), flush=True)
    finally:
        ev['lock']['ended'] = now()
        ev['lock']['timing_valid'] = True
        ev['lock']['released'] = release_own_lock(payload)

    all_items = [v.get('pass') for k, v in ev['items'].items()
                 if k[:1].isdigit()]
    ev['n_items'] = len(all_items)
    ev['n_items_pass'] = sum(1 for x in all_items if x)
    ev['verdict'] = ('PASS' if (all(all_items) and ev['zip_check']['pass'])
                     else 'PARTIAL')
    json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('[acceptance] %d/%d 项 PASS；zip 清单 %s ⇒ %s'
          % (ev['n_items_pass'], ev['n_items'],
             ev['zip_check']['pass'], ev['verdict']))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
