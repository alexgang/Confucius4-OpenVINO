"""APP-089/090/091/092：**设备验收跑**（持 MACHINE_LOCK，NPU 闸门）——
**本轮专用编排器**（一次持锁跑完 normal 三素材 + overload 一素材）。

🔴 **为什么单独写**：原 `app369_app089_run_acceptance.py` 每次调用单独拿锁；
   本轮要求 **A/B 两臂在同一次持锁会话内连续跑**（solo 基线跨会话漂移 ±5 %）
   ⇒ 本脚本**一次拿锁 ⇒ 跑完 normal 三素材 ⇒ 再跑 overload ⇒ 才放锁**。

🔴 **纪律**：
  * **持 MACHINE_LOCK**（O_CREAT|O_EXCL 原子拿）⇒ 别的模块会等，不抢锁。
  * **跑影子包**（`_app_shadow/after/`）⇒ 不碰用户正在测试的安装目录。
  * **不在 CPU 上推理/测速**（ASR/MT=GPU.0，TTS=NPU）。
  * **不调 MiniMax**（回转写由 reviewer 在本机做）⇒ 只把 wav/译文**落盘**。
  * 每个数字都写来源 json 的路径和字段名。

🔴 **overload 的口径**（APP-092 §3）：`--speed 0.35`（回放变慢 ⇒ 源音频消费
   慢于墙钟 ⇒ 机器**跟不上** ⇒ 积压）⇒ 这是 APP-090 §2b① 明确写的
   「人为减速」做法 ⇒ **沿用**。
   ⚠️ 目标墙钟的换算已改为**构造期已知的 `pace`**（不再是滑窗实测速率）
      ⇒ `--speed 0.35` ⇒ 目标墙钟 = `t0 + 已消费源秒 / 0.35` ⇒ 不失真。

用法：
  python _app385_run_acceptance_all.py
"""
from __future__ import annotations

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
    'dialog3': 'dialog3.wav',
    'dialog3_tight': 'dialog3_tight.wav',
    'dialog3_dave': 'dialog3_dave.wav',
}


def sha(p: str) -> str:
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def acquire_lock(tag: str) -> int:
    for _t in range(3):
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


def build_cmd(root: str, out: str, wav: str, extra=None):
    cmd = [
        os.path.join(root, 'python', 'python.exe'),
        os.path.join(root, 'app', 'live_caption_app.py'),
        '--cli', '--file', wav,
        '--speaker', 'on', '--tts', 'on', '--tts-voice', 'follow_speaker',
        '--tts-precision', 'f16', '--tts-device', 'NPU',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--out', os.path.join(out, 'subtitles.txt'),
        '--tts-out', os.path.join(out, 'mix.wav'),
        '--tts-jsonl', os.path.join(out, 'tts.jsonl'),
        '--tts-dump-dir', os.path.join(out, 'dump'),
        '--spk-seg-jsonl', os.path.join(out, 'spk_seg.jsonl'),
    ]
    if extra:
        cmd += list(extra)
    return cmd


def run_one(arm: str, mat: str, extra=None, sub=None):
    root = os.path.join(BASE, arm)
    wav = os.path.join(SPKTEST, MATERIALS[mat])
    out = os.path.join(OUTROOT, arm, sub or mat)
    os.makedirs(out, exist_ok=True)
    log_path = os.path.join(out, 'run.log')
    cmd = build_cmd(root, out, wav, extra)
    env = dict(os.environ)
    clone_dir = os.path.join(out, 'clone_voices')
    os.makedirs(clone_dir, exist_ok=True)
    env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir

    started = now()
    print('▶ [%s/%s] %s' % (arm, mat, wav), flush=True)
    rc = -1
    with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
        lf.write('# cmd=%s\n# started=%s\n' % (json.dumps(cmd), started))
        lf.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             encoding='utf-8', errors='replace',
                             bufsize=1, env=env, cwd=root)
        for line in p.stdout:
            lf.write(line)
            lf.flush()
            if ('⏭' in line or '已晚' in line or '音频 ' in line
                    or 'TTS] 收尾' in line):
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
    pid = acquire_lock('after/normal3+overload')
    if pid < 0:
        print('🔴 三次都没拿到 MACHINE_LOCK ⇒ 本轮放弃（不抢锁）')
        return 2
    print('🔒 MACHINE_LOCK pid=%d' % pid, flush=True)
    mans = []
    try:
        # ① normal 三素材（speed=1.0 ⇒ 正常跑 ⇒ APP-092 §3(d)「跳过 ≈ 0」）
        for m in ('dialog3', 'dialog3_tight', 'dialog3_dave'):
            mans.append(run_one('after', m))
        # ② overload（人为减速 ⇒ 积压 ⇒ APP-092 §3(a)(b)(c)）
        mans.append(run_one('after', 'dialog3',
                            extra=['--speed', '0.35'], sub='dialog3_overload'))
    finally:
        release_lock()

    out_path = os.path.join(EVID, 'app385_app089_accept_runs_after.json')
    summary = {'arm': 'after', 'finished': now(), 'runs': mans,
               'note': ('本轮一次持锁连续跑完 normal 三素材 + overload 一素材；'
                        '目标墙钟换算用构造期已知的 pace（确定性）')}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps({'out': out_path, 'n_runs': len(mans)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
