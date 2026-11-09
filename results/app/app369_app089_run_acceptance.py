"""APP-089/090/091/092：**设备验收跑**（持 MACHINE_LOCK，NPU 闸门）。

🔴 reviewer 的验收口径（APP-089 §4 ＋ APP-090 §3 ＋ APP-092 §3）全部**合并一次跑**：
  素材：`C:\\Users\\Trekker-PTL\\_reviewer_tmp\\spktest\\` 下
        dialog3.wav / dialog3_tight.wav / dialog3_dave.wav
  默认摆放：ASR+MT → GPU.0，TTS → NPU。

🔴 纪律：
  * **持 MACHINE_LOCK**（O_CREAT|O_EXCL 原子拿）⇒ 别的模块会等，不抢锁。
  * **跑影子包**（`_app_shadow/<arm>/`）⇒ 不碰用户正在测试的安装目录。
  * **不在 CPU 上推理/测速**（ASR/MT=GPU.0，TTS=NPU）。
  * **不调 MiniMax**（回转写由 reviewer 在本机做）⇒ 本脚本只把 wav/译文**落盘**。
  * 每个数字都写来源 json 的路径和字段名。

用法：
  python app369_app089_run_acceptance.py --arm after --materials dialog3,dialog3_tight
  python app369_app089_run_acceptance.py --arm before --materials dialog3
  python app369_app089_run_acceptance.py --arm after --overload
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

BASE = r'C:\Users\Trekker-PTL\_app_shadow'
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
OUTROOT = os.path.join(BASE, 'runs2')
SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'
EVID = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app'

MATERIALS = {
    'dialog3': ('dialog3.wav', 'truth.json'),
    'dialog3_tight': ('dialog3_tight.wav', 'truth_tight.json'),
    'dialog3_dave': ('dialog3_dave.wav', None),
}


def sha(p: str) -> str:
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def acquire_lock(tag: str) -> int:
    """🔴 原子拿锁（O_CREAT|O_EXCL）⇒ 没有「检查后再创建」的竞态窗口。"""
    for _try in range(3):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write('module=app\npid=%d\nstart=%s\ntag=%s\n'
                        % (os.getpid(), now(), tag))
            return os.getpid()
        except FileExistsError:
            print('🔴 拿锁时发现锁已存在（竞态）⇒ 等 20 s 再试', flush=True)
            time.sleep(20)
    return -1


def release_lock() -> None:
    try:
        if os.path.exists(LOCK):
            cur = open(LOCK, encoding='utf-8', errors='replace').read()
            if ('pid=%d' % os.getpid()) in cur:
                os.remove(LOCK)
                print('🔓 MACHINE_LOCK 已释放', flush=True)
    except Exception as e:
        print('⚠️ 释放 MACHINE_LOCK 失败：%s' % e, flush=True)


def build_cmd(root: str, out: str, wav: str, extra=None) -> list:
    cmd = [
        os.path.join(root, 'python', 'python.exe'),
        os.path.join(root, 'app', 'live_caption_app.py'),
        '--cli',
        '--file', wav,
        '--speaker', 'on',
        '--tts', 'on',
        '--tts-voice', 'follow_speaker',
        '--tts-precision', 'f16',
        '--tts-device', 'NPU',
        '--translate', 'zh',
        '--mt-engine', 'gpu_int8cw',
        '--mt-device', 'GPU.0',
        '--engine', 'gpu_int8',
        '--asr-device', 'GPU.0',
        '--out', os.path.join(out, 'subtitles.txt'),
        '--tts-out', os.path.join(out, 'mix.wav'),
        '--tts-jsonl', os.path.join(out, 'tts.jsonl'),
        '--tts-dump-dir', os.path.join(out, 'dump'),
        '--spk-seg-jsonl', os.path.join(out, 'spk_seg.jsonl'),
    ]
    if extra:
        cmd += list(extra)
    return cmd


def run_one(arm: str, mat: str, extra=None, env_extra=None, sub=None):
    root = os.path.join(BASE, arm)
    wav_name = MATERIALS[mat][0]
    wav = os.path.join(SPKTEST, wav_name)
    # 🔴🔴🔳 **过载跑必须写独立目录**（`sub`）
    #   ⇒ 否则会**覆盖**正常跑同一素材的产物（`runs2/<arm>/<mat>`）
    #   ⇒ 正常跑与过载跑的数字会互相污染（上一轮就踩过：评分文件
    #     比产物跑还早 ⇒ 证据链断裂）。
    out = os.path.join(OUTROOT, arm, sub or mat)
    os.makedirs(out, exist_ok=True)
    log_path = os.path.join(out, 'run.log')
    cmd = build_cmd(root, out, wav, extra)

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    # 🔴 会话开始清空克隆目录（APP-089 §2b）⇒ 每臂每素材**独立目录**，
    #    避免上一轮残留的参考 wav 影响本轮。
    clone_dir = os.path.join(out, 'clone_voices')
    os.makedirs(clone_dir, exist_ok=True)
    env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir

    started = now()
    print('▶ [%s/%s] %s' % (arm, mat, wav), flush=True)
    rc = -1
    with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
        lf.write('# cmd=%s\n' % json.dumps(cmd))
        lf.write('# started=%s\n' % started)
        lf.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             encoding='utf-8', errors='replace',
                             bufsize=1, env=env, cwd=root)
        for line in p.stdout:
            lf.write(line)
            lf.flush()
            if ('[spk]' in line or 'late_drop' in line
                    or 'TTS' in line or '速度' in line):
                print(line.rstrip(), flush=True)
        rc = p.wait()
    finished = now()
    arts = {}
    for dp, _dn, fn in os.walk(out):
        for f in fn:
            p2 = os.path.join(dp, f)
            arts[os.path.relpath(p2, out)] = {
                'bytes': os.path.getsize(p2),
                'sha256': sha(p2),
                'mtime': datetime.datetime.fromtimestamp(
                    os.path.getmtime(p2)).strftime('%Y-%m-%d %H:%M:%S')}
    man = {'arm': arm, 'material': mat, 'rc': rc, 'cmd': cmd,
           'wav': wav, 'wav_sha256': sha(wav), 'wav_bytes': os.path.getsize(wav),
           'started': started, 'finished': finished,
           'clone_dir': clone_dir,
           'n_clone_txt': len([x for x in os.listdir(clone_dir)
                               if x.endswith('.txt')]),
           'artifacts': arts, 'n_artifacts': len(arts)}
    with open(os.path.join(out, 'run_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print('✔ [%s/%s] rc=%d artifacts=%d' % (arm, mat, rc, len(arts)), flush=True)
    return man


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after', choices=('before', 'after'))
    ap.add_argument('--materials', default='dialog3')
    ap.add_argument('--overload', action='store_true',
                    help='过载测试（人为减速 ASR/MT）')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    mats = [x for x in args.materials.split(',') if x]
    extra = []
    env_extra = {}
    sub = None
    if args.overload:
        # 🔴 过载：把回放速度调慢（`--speed` <1 ⇒ 机器跟不上 ⇒ 积压）
        extra += ['--speed', '0.35']
        mats = ['dialog3']
        # 🔴🔴🔳 **独立输出目录**（不覆盖正常跑）
        sub = 'dialog3_overload'

    pid = acquire_lock('%s/%s' % (args.arm, ','.join(mats) +
                                   ('+overload' if args.overload else '')))
    if pid < 0:
        print('🔴 三次都没拿到 MACHINE_LOCK ⇒ 本轮放弃（不抢锁）')
        return 2
    print('🔒 MACHINE_LOCK pid=%d' % pid, flush=True)
    mans = []
    try:
        for m in mats:
            mans.append(run_one(args.arm, m, extra, env_extra, sub=sub))
    finally:
        release_lock()

    out_path = args.out or os.path.join(
        EVID, 'app369_app089_accept_runs_%s%s.json'
        % (args.arm, '_overload' if args.overload else ''))
    summary = {'arm': args.arm, 'overload': args.overload,
               'materials': mats, 'finished': now(), 'runs': mans}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps({'out': out_path, 'n_runs': len(mans)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
