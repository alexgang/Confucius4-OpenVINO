"""offline_reader_gui.py — 离线朗读对话框（Tk Toplevel）。

## 为什么单独一个模块

`offline_reader.py` 只放**纯逻辑**（分段 / 解析 / 节流），**不 import tkinter**
⇒ 自检脚本能在无 GUI、无模型的情况下跑（`results/app/app069_*`）。
本模块才碰 Tk。

## 界面职责

    语音输出分区 → [📖 离线朗读…] → 本对话框
      ┌ 选择文件…（txt/md/srt/vtt/docx/pdf）
      ├ 可编辑的多行文本框（文件解析出来的内容会填进来，也能直接手打）
      └ [▶ 开始朗读] [■ 停止]  + 进度/字数/预计时长

## 🔴 两条线程纪律

1. **喂句在工作线程**（`OfflineReader`），Tk 只在主线程用 `after()` 轮询
   `snapshot()` 更新界面 ⇒ **绝不从工作线程碰控件**（Tk 不是线程安全的，
   跨线程改控件在 Windows 上会偶发卡死）。
2. **关闭窗口要停朗读**：否则用户以为关了，声音还在播；同时要把
   「本次朗读」还没播的句子撤掉（`stop()` 只撤负数 seg 的那些，
   不碰正在进行的会议译文）。
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import offline_reader as OR

_FILE_TYPES = [
    ('支持的文档', '*.txt *.md *.markdown *.log *.srt *.vtt *.docx *.docm *.pdf'),
    ('纯文本', '*.txt *.log'),
    ('Markdown', '*.md *.markdown'),
    ('字幕', '*.srt *.vtt'),
    ('Word 文档', '*.docx *.docm'),
    ('PDF', '*.pdf'),
    ('全部文件', '*.*'),
]


class OfflineReaderDialog(tk.Toplevel):
    """离线朗读对话框。

    参数
    ----
    get_svc()    : 取当前 `TTSService`（可能为 None）
    ensure_svc() : 尽力开启 TTS 并返回 service（None = 开不起来）
    on_log(msg)  : 把日志写进主窗口日志区
    """

    POLL_MS = 300

    def __init__(self, master, get_svc, ensure_svc, on_log=None,
                 initial_dir=None, get_reason=None):
        super().__init__(master)
        self.title('离线朗读 — 文件 / 文本 → 语音播报')
        self.geometry('920x660')
        self.minsize(720, 480)
        self.transient(master)
        self._get_svc = get_svc
        self._ensure_svc = ensure_svc
        self._on_log = on_log or (lambda m: None)
        # 🔴 §52：故障原因提供者 —— 返回 `(last_error, 日志尾巴)`。
        #    没有它，界面只能说「TTS worker 故障（error）」，用户无从下手。
        self._get_reason = get_reason or (lambda: (None, []))
        self._reader = None
        self._last_dir = initial_dir or os.path.expanduser('~')
        self._src_info = ''            # 文件解析信息（用于状态栏）
        self._alive = True

        self._build()
        self._refresh_stats()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.after(self.POLL_MS, self._poll)

    # ── 界面 ────────────────────────────────────────────────────────────
    def _build(self):
        pad = {'padx': 6, 'pady': 4}

        top = ttk.LabelFrame(self, text='来源', padding=(8, 4))
        top.pack(fill='x', **pad)
        row = ttk.Frame(top)
        row.pack(fill='x')
        self.btn_pick = ttk.Button(row, text='📂 选择文件…', width=14,
                                   command=self._pick)
        self.btn_pick.pack(side='left')
        self.var_src = tk.StringVar(value='（可点左侧按钮选文件，也可直接在下面输入文字）')
        ttk.Label(row, textvariable=self.var_src, foreground='#555').pack(
            side='left', padx=(8, 0))
        ttk.Label(top, foreground='#777',
                  text=('支持 .txt / .md / .srt / .vtt / .docx / .pdf'
                        '（.doc、.xls、.ppt 等老格式/表格/Pdf 无解析库时会明确提示）')
                  ).pack(fill='x', pady=(2, 0))

        mid = ttk.LabelFrame(self, text='朗读内容（可编辑）', padding=(8, 4))
        mid.pack(fill='both', expand=True, **pad)
        self.txt = scrolledtext.ScrolledText(
            mid, wrap='word', font=('Microsoft YaHei UI', 12),
            relief='flat', padx=8, pady=6, height=14)
        self.txt.pack(fill='both', expand=True)

        stat = ttk.Frame(self)
        stat.pack(fill='x', padx=8)
        self.var_stat = tk.StringVar(value='字数 0 · 预计 0.0 s')
        ttk.Label(stat, textvariable=self.var_stat, foreground='#555').pack(side='left')
        self.var_prog = tk.StringVar(value='')
        ttk.Label(stat, textvariable=self.var_prog, foreground='#1565c0').pack(side='right')

        bot = ttk.Frame(self, padding=(8, 6))
        bot.pack(fill='x')
        self.btn_start = ttk.Button(bot, text='▶ 开始朗读', width=14,
                                    command=self._start)
        self.btn_start.pack(side='left')
        self.btn_stop = ttk.Button(bot, text='■ 停止', width=10,
                                   command=self._stop, state='disabled')
        self.btn_stop.pack(side='left', padx=(6, 0))
        # 🔴 §52：出错后可一键重启语音输出再念（否则用户只能关掉重开程序）
        self.btn_retry = ttk.Button(bot, text='↻ 重试', width=10,
                                    command=self._retry, state='disabled')
        self.btn_retry.pack(side='left', padx=(6, 0))
        ttk.Button(bot, text='清空', width=8,
                   command=self._clear).pack(side='left', padx=(6, 0))
        self.btn_close = ttk.Button(bot, text='关闭', width=8,
                                    command=self._on_close)
        self.btn_close.pack(side='right')

        self.var_note = tk.StringVar(
            value='提示：朗读**不经过识别与翻译**，直接由 TTS 播报；'
                  '长文档会自动边念边排队（不会一次塞满导致丢句）。')
        ttk.Label(self, textvariable=self.var_note, foreground='#777',
                  wraplength=880, justify='left', padding=(10, 0, 10, 8)
                  ).pack(fill='x')

    # ── 统计 ────────────────────────────────────────────────────────────
    def _refresh_stats(self):
        text = self.txt.get('1.0', 'end-1c')
        n = len(text.strip())
        est = OR.est_seconds(text)
        segs = len(OR.split_for_tts(text)) if n else 0
        extra = f' · {self._src_info}' if self._src_info else ''
        self.var_stat.set(f'字数 {n} · 预计 {est:.1f} s · 分段 {segs}{extra}')

    # ── 文件 ────────────────────────────────────────────────────────────
    def _pick(self):
        p = filedialog.askopenfilename(
            parent=self, title='选择要朗读的文件',
            initialdir=self._last_dir, filetypes=_FILE_TYPES)
        if not p:
            return
        self._last_dir = os.path.dirname(p) or self._last_dir
        try:
            r = OR.extract_text(p)
        except Exception as e:
            self.var_src.set(f'读取失败：{e}')
            self._on_log(f'[offline] 读取失败 {p}: {e}')
            messagebox.showerror('读取失败', str(e), parent=self)
            return
        self.txt.delete('1.0', 'end')
        self.txt.insert('1.0', r['text'])
        self._src_info = (f'{r["name"]}（{r["encoding"]}'
                          f'{("，" + r["note"]) if r["note"] else ""}）')
        self.var_src.set(f'已载入：{r["name"]}')
        self._on_log(f'[offline] 载入 {r["name"]}：{r["n_chars"]} 字 / '
                     f'{r["n_seg"]} 段 / 预计 {r["est_s"]}s')
        self._refresh_stats()

    def _clear(self):
        if self._running():
            self.var_note.set('正在朗读中，先点「停止」再清空。')
            return
        self.txt.delete('1.0', 'end')
        self._src_info = ''
        self.var_src.set('（可点左侧按钮选文件，也可直接在下面输入文字）')
        self.var_prog.set('')
        self._refresh_stats()

    # ── 朗读控制 ────────────────────────────────────────────────────────
    def _running(self) -> bool:
        r = self._reader
        return bool(r and not r.done and not r.stopped)

    def _reason_text(self) -> str:
        """把「TTS 故障原因 + 日志尾巴」拼成给用户看的一段话。

        🔴 不展示原因的话，用户只能看到「worker 故障（error）」——
        这句话对**用户**和**我**都没有任何信息量（§52 的实际教训）。
        """
        try:
            err, tail = self._get_reason()
        except Exception as e:
            err, tail = None, [f'（取原因失败：{e!r}）']
        if not err:
            return ''
        s = f'🔴 TTS 语音输出故障：{err}'
        if tail:
            s += '\n最近日志：' + ' | '.join(t.strip() for t in tail[-4:])
        return s

    def _start(self):
        if self._running():
            return
        text = self.txt.get('1.0', 'end-1c')
        if not text.strip():
            self.var_note.set('文本框是空的：先选文件，或直接输入要朗读的文字。')
            return
        svc = self._get_svc()
        if svc is None or getattr(svc, 'state', '') == 'error':
            svc = self._ensure_svc()
        if svc is None:
            msg = ('语音输出没能启动 ⇒ 请到主界面「语音输出」勾选「开启」，'
                   '并确认设备可用（状态栏会显示原因）。')
            self.var_note.set(msg)
            self._on_log(f'[offline] {msg}')
            return
        # 🔴 §52：重启后仍是 error ⇒ **把原因说出来**，并允许重试，
        #   不要给一句无信息量的「worker 故障」。
        if getattr(svc, 'state', '') == 'error':
            self.var_note.set(self._reason_text() or
                              '🔴 TTS worker 启动失败（没有拿到具体原因）')
            self.btn_retry.configure(state='normal')
            self._on_log('[offline] TTS worker 处于 error 状态，已中止')
            return

        segs = OR.split_for_tts(text)
        if not segs:
            self.var_note.set('没有可朗读的文本（可能只有符号/空白）。')
            return

        self._reader = OR.OfflineReader(
            svc, on_log=lambda m: self._on_log(f'[offline] {m}'))
        n = self._reader.start(segs)
        st = getattr(svc, 'state', '?')
        self.btn_start.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.btn_retry.configure(state='disabled')
        self.var_note.set(
            f'开始朗读：{n} 段 / 预计 {OR.est_seconds(text):.1f} s'
            + ('（TTS 还在加载模型，加载完会自动开始）' if st != 'ready' else ''))
        self._on_log(f'[offline] 开始：{n} 段，TTS 状态 {st}')

    def _retry(self):
        """重启语音输出后再念（worker 卡在 error 时的唯一出路）。"""
        r = self._reader
        if r is not None and not r.done:
            r.stop()
        self._reader = None
        self.var_note.set('正在重启语音输出…（模型加载需要十几到几十秒）')
        self._on_log('[offline] 用户点「重试」⇒ 重启 TTS')
        try:
            svc = self._ensure_svc()
        except Exception as e:
            self.var_note.set(f'🔴 重启失败：{e}')
            return
        if svc is None or getattr(svc, 'state', '') == 'error':
            self.var_note.set(self._reason_text() or
                              '🔴 重启后仍然失败（没有拿到具体原因）')
            self.btn_retry.configure(state='normal')
            return
        self.btn_retry.configure(state='disabled')
        self._start()

    def _stop(self):
        r = self._reader
        if r is None:
            return
        r.stop()
        self.var_note.set('已停止：本次朗读还没播的句子已撤掉'
                          '（会议译文的朗读不受影响）。')
        self.btn_start.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self._on_log('[offline] 用户停止朗读')

    # ── 轮询 ────────────────────────────────────────────────────────────
    def _poll(self):
        if not self._alive:
            return
        try:
            r = self._reader
            if r is not None:
                s = r.snapshot()
                self.var_prog.set(
                    f'已提交 {s["n_fed"]}/{s["n_seg"]} 段 · 待播 '
                    f'{max(0, s["n_pend"])} · TTS {s["state"]}')
                if s['error']:
                    # 🔴 §52：reader 只说「worker 故障」，**真正原因在 service 里**
                    #   （worker 级 error 的原文 + 最近日志）。两句合起来给用户看，
                    #   并打开「↻ 重试」（真的会重启 worker，不是只重发文本）。
                    reason = self._reason_text()
                    self.var_note.set(
                        f'🔴 {s["error"]}' + (('\n' + reason) if reason else ''))
                    self.btn_start.configure(state='normal')
                    self.btn_stop.configure(state='disabled')
                    self.btn_retry.configure(state='normal')
                    self._reader = None
                elif s['done']:
                    if not s['stopped']:
                        self.var_note.set(
                            f'已全部提交（{s["n_seg"]} 段），语音在队列里继续播完。'
                            '可以关闭本窗口，不影响播放。')
                    self.btn_start.configure(state='normal')
                    self.btn_stop.configure(state='disabled')
                    self._reader = None
            else:
                self._refresh_stats()
        except Exception as e:                     # 轮询里绝不抛（会把 UI 卡死）
            self._on_log(f'[offline] poll 异常：{e!r}')
        self.after(self.POLL_MS, self._poll)

    # ── 关闭 ────────────────────────────────────────────────────────────
    def _on_close(self):
        r = self._reader
        if r is not None and not r.done:
            try:
                r.stop()
            except Exception:
                pass
        self._alive = False
        try:
            self.destroy()
        except Exception:
            pass


def open_dialog(master, get_svc, ensure_svc, on_log=None, initial_dir=None,
                get_reason=None):
    """打开（或聚焦已打开的）离线朗读对话框。"""
    win = getattr(master, '_offline_dlg', None)
    if win is not None:
        try:
            if win.winfo_exists():
                # 已开着的窗口要用**新的**回调（换设备/换音色后 self.tts 变了）
                win._get_svc = get_svc
                win._ensure_svc = ensure_svc
                if get_reason is not None:
                    win._get_reason = get_reason
                win.deiconify()
                win.lift()
                win.focus_force()
                return win
        except Exception:
            pass
    win = OfflineReaderDialog(master, get_svc, ensure_svc, on_log=on_log,
                              initial_dir=initial_dir, get_reason=get_reason)
    master._offline_dlg = win
    return win
