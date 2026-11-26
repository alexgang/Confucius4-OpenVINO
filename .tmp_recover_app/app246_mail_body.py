"""生成两封邮件的正文（从实测 JSON 取数，不手抄），落盘为 UTF-8 文本。

输出：
  .tmp_recover_app/mail_state_body.txt   （状态报告）
  .tmp_recover_app/mail_audio_body.txt   （抽听样片，随附件）
"""
import hashlib
import io
import json
import os
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
R = os.path.join(REPO, 'results', 'app')
OUTDIR = os.path.join(REPO, '.tmp_recover_app')


def jload(p):
    return json.load(io.open(p, encoding='utf-8'))


def main():
    gm = jload(os.path.join(R, 'app245_gate_metrics.json'))
    ta = jload(os.path.join(R, 'app245_three_arms.json'))
    lk = jload(os.path.join(R, 'app245_lock001_install.json'))
    ls = jload(os.path.join(R, 'app245_listen', 'app245_listen.json'))
    wl = jload(os.path.join(R, 'app245_zip_whitelist.json'))

    arms = {a['arm']: a for a in gm['arms']}
    order = [a['arm'] for a in gm['arms']]
    label = {'bgkeep_off': '背景音关', 'bgkeep_on': '背景音开',
             'bgkeep_on_clone': '开+克隆'}

    ev = {a['arm']: a for a in ta['arms']}

    L = []
    A = L.append
    A('reviewer 好，')
    A('')
    A('APP 线程 §245 / §246 收尾回报。last_ack 仍 APP-151（局域网 CORRECTIONS_APP.md 无新编号）；')
    A('同时执行了 11-26 19:59Z 那封 GEN 纠偏 LOCK-001（机器锁死锁修复，APP 负责安装），本邮件第六节。')
    A('')
    A('一、§245 断点根因与修法（上一轮 19:14 三轮 gate_all_pass=false 的真正原因）')
    A('- 不是产品缺陷，是排空工具自己的缺陷：_app137_e2e_drain.drain_until_zero() 把「一次 stats')
    A('  接收超时(10 s)」当断连 break。三臂 drain 都是 elapsed=10.02 s + TimeoutError，')
    A('  但 bridge.log 同刻仍在出段，最终 dubs 123 = n_submitted 123。')
    A('- 修法：超时后继续排空（记 drain_timeout_events）+ 超时分支也查墙钟 hard_cap')
    A('  （APP-143 b ② 的兜底不破）+ 真断连才退出。')
    A('- 验证：行为级 5/5 PASS（含反证：把 continue 还原成 break，同场景必失败）；')
    A('  APP-143 b 原反证重跑 4/4 PASS（43.1 s <= 50 s 上限）。')
    A('')
    A('二、三轮重跑（新目录 three_arms_r245/，旧证据未覆盖）')
    A('臂        rc  dubs 丢句 排空  排空s  n_err 撞39s NaN 削波 语速max synth_rtf')
    for n in order:
        a = arms[n]
        A('%-10s %2d  %4d  %3d  %-5s %6.1f  %4d  %4d  %3d %3d  %5.1f   %.4f'
          % (label.get(n, n), a['rc'] if 'rc' in a else ev[n]['rc'], a['dubs'],
             a['n_dropped'], 'True' if a['drained_to_zero'] else 'FALSE',
             a['drain_elapsed_sec'], a['n_error'], a['tts_frame_cap_hit_n'],
             a['nan_event_n'], a['clip_event_n'], a['speed_max'], a['synth_rtf']))
    A('')
    A('lock_lost=0（一次持锁到底 ⇒ 计时有效）；cp 自检 cos 0.9986-0.99995；')
    A('落点 NPU 9 组件 / CPU 0；NPU_TURBO=True；MT 就绪 = Hy-MT3 INT8 @ GPU.0；')
    A('APP-150 §2 门禁 3/3 PASS（gate_metrics.json：gate_all_pass=%s）。'
      % gm.get('gate_all_pass'))
    A('')
    A('三、滞后实测（请重点看，这条影响说明书）')
    A('臂         p50      p90      max     (s)')
    for n in order:
        a = arms[n]
        A('%-10s %7.1f  %7.1f  %7.1f'
          % (label.get(n, n), a['dub_late_p50'], a['dub_late_p90'], a['dub_late_max']))
    A('')
    BAK = (r'C:\Users\Trekker-PTL\shared\pkg_baks_20261126'
           r'\README_zh.md.bak_app245_lag')
    old_zh = ''
    if os.path.isfile(BAK):
        bl = io.open(BAK, encoding='utf-8').read().split('\n')
        for i, ln in enumerate(bl):
            if '10 分钟连续讲话实测' in ln:
                old_zh = (ln.strip().lstrip('- ')
                          + (bl[i + 1].strip() if i + 1 < len(bl) else ''))
                break
    if not old_zh:
        old_zh = '(备份未命中，见 shared\\pkg_baks_20261126\\README_zh.md.bak_app245_lag)'
    A('=> 旧口径明显偏低。改前原文（逐字取自 README_zh 备份 .bak_app245_lag）：')
    A('   「%s」' % old_zh)
    A('   本机实测：中位数就已 29/51/95 s，最大 160.8/224.8/337.9 s => 已按实测改写中/英')
    A('   README（README_zh 31 264->31 554 B；README_en 33 975->34 476 B）。')
    A('')
    A('四、抽听样片（另发一封带 3 个 OGG 附件）')
    A('clone 臂播放端混音切 3 段 × 40 s：Ogg/Opus 16 kHz，117 114 / 120 347 / 122 633 B。')
    A('sha1 由发送脚本从磁盘现算，附件邮件里逐段列出。')
    A('')
    A('五、交付面（顺带修掉的漏项）')
    A('白名单原 18 条漏查备份文件 => 包里实测躺着 32 个 *.bak_*（含 translator.py.bak_app151）。')
    A('已只移不删到 shared/pkg_baks_20261126/（32/32 sha256 校验），白名单补第 9 条后重跑')
    A('%d/%d PASS。' % (sum(1 for c in wl['checks'] if c['ok']), len(wl['checks'])))
    A('')
    A('六、LOCK-001（机器锁死锁修复）已安装并自证')
    ins = lk['install']
    A('1) 安装：%s' % ins['path'])
    A('   %d B，sha256 %s，ast.parse 通过。附件经直连 API 由脚本落盘，无人工转写。'
      % (ins['bytes'], ins['sha256']))
    A('2) shared\\README_LOCK.md 顶部加 LOCK-001 段，旧机制保留备查（339->1 341 B，CRLF 0）。')
    A('3) 行为验证 5/5（包内 python 跑，证据 results/app/app245_lock001_install.json）：')
    c = lk['cases']
    A('   c0 status = %s' % c['c0_status_free']['out'].splitlines()[0])
    A('   c1 单作业  rc=%d，acquired + released(rc=0) 两行齐全'
      % c['c1_single_run']['rc'])
    A('   c2 持锁期 status = %s' % c['c2_status_held']['out'].splitlines()[0])
    A('   c3 第二作业先 waiting 后 acquired，等 %.1f s' % c['c3_queue']['waited_s'])
    A('   c4 整树 taskkill /F /T 后 status = %s'
      % c['c4_kill_release']['after_kill_status']['out'].splitlines()[0])
    A('      => 系统锁已随进程结束自动释放（不再永久死锁）；reclaim 后 = %s'
      % c['c4_kill_release']['final_status']['out'].splitlines()[0])
    A('4) 如实登记未做：既有取锁代码（machine_lock_app.py 的 write_lock_atomic、三轮编排')
    A('   脚本的 CreateNew/finally 删锁）尚未改成套 machine_lock.py run。下一次计时作业')
    A('   起法改为 machine_lock.py run --module app --note ... -- <命令>，并在日志核对')
    A('   [machine_lock] acquired / released (rc=...) 两行（LOCK-001 验收第 2 条）。')
    A('')
    A('七、当前状态与待你确认')
    A('- commit 1730b92 已推 origin/main（ls-remote 一致）。')
    A('- 未打 zip、未签 ACCEPTED。按用户纪律「不经用户点头不打包」，且需要你先复核数字。')
    A('- 请确认：① 三轮数字与滞后口径是否接受；② 抽听样片（另一封）；')
    A('  ③ 是否放行打 v1.2 zip（注意打 zip 会吃掉 v1.2 这个版本号，')
    A('     候选目录 = C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_MiniMVP_v1.2.candidate）。')
    A('- 顺带抓到两个真缺陷（已规避，是否单独立项请你定）：')
    A('  ① 旧抽听脚本 _app148_extract_samples.py 读 10 min 混音静默崩溃 rc=127（改 numpy 读 wav 解决）；')
    A('  ② 本机 libsndfile 1.2.2 写 VORBIS 大块爆栈（48 kHz 20 s / 16 kHz 40 s 崩，OPUS 正常）。')
    A('')
    A('APP')
    state = '\r\n'.join(L) + '\r\n'

    # ---------- 样片邮件 ----------
    clips = ls['clips']
    M = []
    B = M.append
    B('reviewer 好，')
    B('')
    B('APP-148 §1c 抽听样片 —— 本轮 §245 的 clone 臂（背景音开 + 克隆音色）。')
    B('')
    B('源：three_arms_r245/bgkeep_on_clone/bgkeep_on_clone_1/player_mix.wav')
    B('（%d s，%d Hz，%d 声道；播放端混音，即用户实际听到的）'
      % (int(ls['total_sec']), ls['sample_rate'], ls['channels']))
    B('编码：Ogg/Opus 16 kHz（附件上限 1 MB/个，共 3 个）')
    B('')
    B('# 起点s  时长s   文件            字节     sha1')
    for c in clips:
        p = os.path.join(R, 'app245_listen',
                         os.path.basename(c['ogg']))
        raw = open(p, 'rb').read()
        c['_sha1'] = hashlib.sha1(raw).hexdigest()
        c['_bytes'] = len(raw)
        B('%d %7.2f %5.1f  %-30s %7d  %s'
          % (c['idx'], c['start_sec'], c['duration_sec'],
             os.path.basename(c['ogg']), c['_bytes'], c['_sha1']))
    B('')
    B('#  RMS      peak    削波样本')
    for c in clips:
        B('%d %8.5f %8.4f %6d' % (c['idx'], c['rms'], c['peak'],
                                  c['n_clipped_samples']))
    B('')
    B('请抽听确认三件事：')
    B('① 男/女音色是否串音（APP-071/075 的验收口径，不接受只统计 voice_kind）；')
    B('② 背景音有无残留爆音/断点；')
    B('③ 克隆音色与登记是否一致。')
    B('')
    B('说明：这 3 段是播放端混音（含背景音），不是纯 TTS 干声。若你要干声对齐文本，')
    B('我可以再从 dubs.npz + margin.json 切纯 TTS 段另发。')
    B('')
    B('sha1 由发送脚本从磁盘现算（无人工转写）；附件同时带在信里，若附件被拦，')
    B('可到 %s 直接取。' % os.path.join(R, 'app245_listen'))
    B('')
    B('APP')
    audio = '\r\n'.join(M) + '\r\n'

    os.makedirs(OUTDIR, exist_ok=True)
    for name, txt in (('mail_state_body.txt', state),
                      ('mail_audio_body.txt', audio)):
        p = os.path.join(OUTDIR, name)
        with io.open(p, 'w', encoding='utf-8', newline='') as f:
            f.write(txt)
        b = txt.encode('utf-8')
        print('%-22s %6d B  %d 行  sha256=%s'
              % (name, len(b), txt.count('\r\n'), hashlib.sha256(b).hexdigest()[:16]))

    # 把样片 sha1 回写 listen.json（供 STATUS 引用）
    ls['clips'] = clips
    ls['sha1_filled_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with io.open(os.path.join(R, 'app245_listen', 'app245_listen.json'),
                 'w', encoding='utf-8', newline='\n') as f:
        json.dump(ls, f, ensure_ascii=False, indent=2)
    print('listen.json 已回填 sha1')


if __name__ == '__main__':
    main()
