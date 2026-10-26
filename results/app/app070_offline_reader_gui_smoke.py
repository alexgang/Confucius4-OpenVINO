"""app070 — 离线朗读**对话框**的 GUI 冒烟（真实 Tk 控件 + 假 service，不加载模型）。

## 这个脚本证明什么 / 不证明什么

证明：
- 对话框能起来、能填文本、能统计字数/分段；
- 点「▶ 开始朗读」⇒ `OfflineReader` 真的把段喂给 service，进度标签跟着动；
- 点「■ 停止」⇒ 只撤本次朗读的句子，且按钮状态回到正确位置；
- 关闭窗口会停掉喂句线程（不留后台线程往死掉的 service 里 submit）。

**不证明**：真实 TTS 的合成与播放（那要加载模型；本机机器锁被别的模块持着，
按铁律不在别人的计时窗口里起重计算进程）。真实音频由人工朗读冒烟确认。

用包内 python（有 tkinter）跑：
    <PKG>\\python\\python.exe results\\app\\app070_offline_reader_gui_smoke.py
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
import tkinter as tk

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, 'live_caption'))

import offline_reader as OR                    # noqa: E402

OUTDIR = os.path.join(os.environ.get('TEMP', '.'), 'app070_shots')
LINES = []
N_PASS = N_FAIL = 0

SAMPLE = (
    '离线朗读功能已经接入主界面。'
    '用户可以点「选择文件」，把一份文档读进来，也可以直接在文本框里输入要念的内容。'
    '点开始朗读之后，文本会被按句切分，逐段送进语音合成，边念边排队。'
    '这样即使是几十页的长文档，也不会因为一次性塞满队列而被整段丢弃。'
)


def say(s=''):
    print(s)
    LINES.append(s)


def check(name, ok, detail=''):
    global N_PASS, N_FAIL
    if ok:
        N_PASS += 1
        say(f'  PASS  {name}' + (f'  [{detail}]' if detail else ''))
    else:
        N_FAIL += 1
        say(f'  FAIL  {name}' + (f'  [{detail}]' if detail else ''))


def load_fake_svc():
    """复用 app069 里那份「复刻丢句规则」的假 service（避免两份实现漂移）。"""
    p = os.path.join(_HERE, 'app069_offline_reader_selftest.py')
    spec = importlib.util.spec_from_file_location('app069_mod', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FakeTTSService, mod.read_backlog_max_from_source()


def pump(root, seconds, until=None):
    """跑 Tk 事件循环一段时间（不阻塞界面）。until() 为 True 时提前返回。"""
    t_end = time.time() + seconds
    while time.time() < t_end:
        root.update()
        if until is not None and until():
            return True
        time.sleep(0.02)
    return False


def shot(win, path):
    try:
        import PIL.ImageGrab as ImageGrab
        win.update_idletasks()
        x, y = win.winfo_rootx(), win.winfo_rooty()
        w, h = win.winfo_width(), win.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        img.save(path)
        return os.path.getsize(path)
    except Exception as e:
        say(f'  (截图失败：{type(e).__name__}: {e})')
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        _REPO, 'results', 'app', 'app070_offline_reader_gui_smoke.txt'))
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)

    say('=' * 78)
    say('app070 离线朗读对话框 GUI 冒烟（真实 Tk + 假 service，不加载模型）')
    say(f'ts={time.strftime("%Y-%m-%d %H:%M:%S")}  python={sys.version.split()[0]}')
    say('=' * 78)

    FakeTTSService, backlog_max = load_fake_svc()
    say(f'假 service 的积压阈值 = {backlog_max}s（与 tts_service 源码一致）')

    import offline_reader_gui as G

    root = tk.Tk()
    # 🔴 **不能 withdraw 主窗**：父窗被 withdraw 后，`transient` 的子 Toplevel
    #    在 Windows 上不会被正常映射 ⇒ `winfo_width()` 返回 1x1、
    #    ImageGrab 只抓到 69 B 的空图（实测就是这条 FAIL）。
    #    改成「主窗摆到屏幕外」：仍然 mapped，但用户看不见。
    root.geometry('240x120+2600+2600')
    root.update()
    svc = FakeTTSService(backlog_max, speed=15.0)
    svc.start_player()
    logs = []
    dlg = G.OfflineReaderDialog(root, lambda: svc, lambda: svc,
                                on_log=logs.append, initial_dir=OUTDIR)
    root.update()
    # 记录提示文字的变化历史 —— FAIL 时能直接看出「是谁把提示覆盖掉的」
    note_hist = []
    _orig_set = dlg.var_note.set

    def _rec(v):
        note_hist.append(str(v))
        _orig_set(v)
    dlg.var_note.set = _rec

    # ── A. 控件齐备 ──
    say('\n[A] 控件与布局')
    dlg.geometry('920x660+40+40')
    pump(root, 0.6)
    dlg.lift()
    pump(root, 0.3)
    w, h = dlg.winfo_width(), dlg.winfo_height()
    check('对话框已创建且可见', dlg.winfo_exists() and w > 500 and h > 400,
          f'{w}x{h}')
    check('有开始/停止/关闭三个按钮',
          all(hasattr(dlg, n) for n in ('btn_start', 'btn_stop', 'btn_close')))
    check('停止按钮初始为禁用', str(dlg.btn_stop['state']) == 'disabled')

    # ── B. 填入文本 + 统计 ──
    say('\n[B] 文本与统计')
    dlg.txt.insert('1.0', SAMPLE)
    dlg._refresh_stats()
    root.update()
    stat = dlg.var_stat.get()
    n_seg = len(OR.split_for_tts(SAMPLE))
    check('统计标签含字数/时长/分段', '字数' in stat and '分段' in stat, stat)
    check('分段数与模块一致', f'分段 {n_seg}' in stat, f'期望 {n_seg}')
    p1 = os.path.join(OUTDIR, 'app070_dialog_before.png')
    s1 = shot(dlg, p1)
    check('窗口截图（朗读前）', s1 > 8000, f'{p1} {s1} B')

    # ── C. 开始朗读 ⇒ 真的提交 + 进度推进 ──
    say('\n[C] 开始朗读')
    dlg.btn_start.invoke()
    root.update()
    check('开始后按钮状态正确',
          str(dlg.btn_start['state']) == 'disabled'
          and str(dlg.btn_stop['state']) == 'normal')
    rd = dlg._reader
    check('OfflineReader 已建立', rd is not None and rd.n_seg == n_seg,
          f'n_seg={getattr(rd, "n_seg", None)}')
    ok = pump(root, 20.0, until=lambda: svc.n_played >= n_seg)
    # 🔴 界面是 300 ms 轮询的 ⇒ 「播放器念完」时标签还没刷。
    #    必须等到轮询把 `_reader` 清空（这才是「界面已回到空闲态」的判据），
    #    否则读到的是**上一拍**的值（实测两条 FAIL：进度 9/10、按钮没复位）。
    pump(root, 5.0, until=lambda: dlg._reader is None)
    root.update()
    prog = dlg.var_prog.get()
    say(f'  → service 提交 {svc.n_submitted} / 已播 {svc.n_played} / '
        f'丢 {svc.n_dropped}')
    say(f'  → 进度标签：{prog}')
    check('所有段都被提交', svc.n_submitted == n_seg, f'{svc.n_submitted}/{n_seg}')
    check('所有段都真的播到了', svc.n_played == n_seg, f'{svc.n_played}/{n_seg}')
    check('丢句 = 0（节流在 GUI 路径上同样生效）', svc.n_dropped == 0,
          f'dropped={svc.n_dropped}')
    check('进度标签反映「已提交 x/y 段」',
          f'{n_seg}/{n_seg}' in prog, prog)
    check('念完后按钮回到可再点状态',
          str(dlg.btn_start['state']) == 'normal'
          and str(dlg.btn_stop['state']) == 'disabled')
    p2 = os.path.join(OUTDIR, 'app070_dialog_done.png')
    s2 = shot(dlg, p2)
    check('窗口截图（朗读完成）', s2 > 8000, f'{p2} {s2} B')
    check('日志里有「开始朗读」记录',
          any('开始' in m for m in logs), f'{len(logs)} 条日志')

    # ── D. 停止路径 ──
    say('\n[D] 停止')
    svc2 = FakeTTSService(backlog_max, speed=2.0)
    svc2.start_player()
    dlg._get_svc = lambda: svc2
    dlg._ensure_svc = lambda: svc2
    dlg.txt.delete('1.0', 'end')
    dlg.txt.insert('1.0', SAMPLE * 3)
    dlg._refresh_stats()
    dlg.btn_start.invoke()
    pump(root, 1.0)
    n_fed_before_stop = dlg._reader.n_fed if dlg._reader else -1
    dlg.btn_stop.invoke()
    root.update()
    check('停止后按钮状态翻转',
          str(dlg.btn_start['state']) == 'normal'
          and str(dlg.btn_stop['state']) == 'disabled')
    check('停止后撤掉了未播的句子（n_dropped > 0 或本来就播完了）',
          svc2.n_dropped > 0 or svc2.n_played >= svc2.n_submitted,
          f'dropped={svc2.n_dropped} played={svc2.n_played} '
          f'sub={svc2.n_submitted} fed={n_fed_before_stop}')
    check('停止后不变式 n_played + n_dropped == n_submitted',
          svc2.n_played + svc2.n_dropped == svc2.n_submitted,
          f'{svc2.n_played}+{svc2.n_dropped} vs {svc2.n_submitted}')
    check('提示文字说明「不影响会议译文」', '会议' in dlg.var_note.get(),
          dlg.var_note.get()[:40])
    if '会议' not in dlg.var_note.get():
        say(f'  ⚠️ 提示历史（最近 6 条）：{note_hist[-6:]}')
    svc2.stop_player()

    # ── E. 关闭窗口会停线程 ──
    say('\n[E] 关闭')
    svc3 = FakeTTSService(backlog_max, speed=1.0)
    svc3.start_player()
    dlg._get_svc = lambda: svc3
    dlg._ensure_svc = lambda: svc3
    dlg.txt.delete('1.0', 'end')
    dlg.txt.insert('1.0', SAMPLE * 4)
    dlg.btn_start.invoke()
    pump(root, 0.6)
    rd3 = dlg._reader
    dlg._on_close()
    root.update()
    alive = rd3.wait(timeout=5) if rd3 is not None else True
    check('关闭后喂句线程已退出', alive)
    check('关闭后对话框已销毁', not dlg.winfo_exists())
    svc3.stop_player()

    # ── 汇总 ──
    say('\n' + '=' * 78)
    say(f'结果：PASS {N_PASS} / FAIL {N_FAIL}')
    say(f'截图：{OUTDIR}')
    say('⚠️ 本冒烟用假 service（不加载模型）⇒ 只能证明**界面与节流链路**，'
        '不能证明真实音频；真实音频由人工朗读确认。')
    say('=' * 78)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(LINES) + '\n')
    print(f'已写 {args.out}')
    try:
        root.destroy()
    except Exception:
        pass
    return 0 if N_FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
