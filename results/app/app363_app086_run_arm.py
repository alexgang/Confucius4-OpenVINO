"""APP-086(2)：跑一臂（before / after）的**设备作业**（持 MACHINE_LOCK）。

🔴 纪律：
  * **持锁**：开跑前创建 `C:\\Users\\Trekker-PTL\\shared\\MACHINE_LOCK`
    （内容：模块名 / PID / 开始时间）⇒ 别的模块看到锁会等。
    跑完**自己删**（只删自己创建的那一份）。
  * **不在 CPU 上推理/测速**：ASR=GPU.0、MT=GPU.0、TTS=NPU（交付配置）。
  * **不碰用户正在测试的安装目录**：跑的是**影子包**
    （`_app_shadow/<arm>/`，models/python 是目录联接 ⇒ 零拷贝）。

用法：python app363_app086_run_arm.py <before|after> [wav_path]
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
OUTROOT = r'C:\Users\Trekker-PTL\_app_shadow\runs'
WAV = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest\dialog3.wav'


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main() -> int:
    arm = sys.argv[1] if len(sys.argv) > 1 else 'before'
    # 🔴 参数解析：只把**非选项**当作 wav 路径
    #   （之前把 '--wait' 当成 wav 了 ⇒ 一个脆的 FileNotFoundError）
    wav = WAV
    for _a in sys.argv[2:]:
        if not _a.startswith('--'):
            wav = _a
    wait = '--wait' in sys.argv
    root = os.path.join(BASE, arm)
    out = os.path.join(OUTROOT, arm)
    os.makedirs(out, exist_ok=True)
    log_path = os.path.join(out, 'run.log')
    manifest_path = os.path.join(out, 'run_manifest.json')

    if os.path.exists(LOCK):
        if not wait:
            print('🔴 MACHINE_LOCK 已存在 ⇒ 本臂不跑（等锁）：')
            print(open(LOCK, encoding='utf-8', errors='replace').read())
            return 2
        # 🔴 **排队等待，不抢锁**：别的模块正在占设备 ⇒ 等它释放。
        waited = 0
        print('⏳ MACHINE_LOCK 被占用 ⇒ 排队等待（不抢锁）…', flush=True)
        while os.path.exists(LOCK) and waited < 5400:
            time.sleep(30)
            waited += 30
            print('   …已等 %d s' % waited, flush=True)
        if os.path.exists(LOCK):
            print('🔴 等锁超时（90 min）⇒ 本臂放弃（不抢锁）')
            return 2
        print('🔓 锁已释放 ⇒ 开始本臂', flush=True)

    py = os.path.join(root, 'python', 'python.exe')
    app = os.path.join(root, 'app', 'live_caption_app.py')
    cmd = [
        py, app,
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
        '--tts-dump-dir', os.path.join(out, 'dump'),
        '--spk-seg-jsonl', os.path.join(out, 'spk_seg.jsonl'),
    ]
    started = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 🔴🔴 **原子拿锁**（O_CREAT|O_EXCL）⇒ 没有「检查后再创建」的竞态窗口
    #   （否则别的模块可能在我们 check 与 create 之间抢到锁 ⇒ 两模块同占设备）。
    fd = None
    for _try in range(3):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            print('🔴 拿锁时发现锁已存在（竞态）⇒ 再等一轮', flush=True)
            time.sleep(20)
            if not wait:
                return 2
    if fd is None:
        print('🔴 三次都没拿到锁 ⇒ 本臂放弃（不抢锁）')
        return 2
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write('module=app\npid=%d\nstart=%s\narm=%s\n' %
                (os.getpid(), started, arm))
    print('🔒 MACHINE_LOCK 已创建 pid=%d arm=%s' % (os.getpid(), arm), flush=True)

    rc = -1
    try:
        with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True,
                                 encoding='utf-8', errors='replace',
                                 bufsize=1)
            for line in p.stdout:
                lf.write(line)
                lf.flush()
                if '[spk]' in line or 'TTS' in line:
                    print(line.rstrip(), flush=True)
            rc = p.wait()
    finally:
        try:
            if os.path.exists(LOCK):
                cur = open(LOCK, encoding='utf-8', errors='replace').read()
                if ('pid=%d' % os.getpid()) in cur:
                    os.remove(LOCKER := LOCK)
                    print('🔓 MACHINE_LOCK 已释放', flush=True)
        except Exception as e:
            print('⚠️ 释放 MACHINE_LOCK 失败：%s' % e, flush=True)

    arts = {}
    for dp, _dn, fn in os.walk(out):
        for f in fn:
            p = os.path.join(dp, f)
            arts[os.path.relpath(p, out)] = {
                'bytes': os.path.getsize(p),
                'sha256': sha(p),
                'mtime': datetime.datetime.fromtimestamp(
                    os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S')}
    man = {'arm': arm, 'rc': rc, 'cmd': cmd, 'wav': wav,
           'wav_sha256': sha(wav), 'started': started,
           'finished': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'artifacts': arts, 'n_artifacts': len(arts)}
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(json.dumps({'arm': arm, 'rc': rc, 'n_artifacts': len(arts),
                      'log': log_path}, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
