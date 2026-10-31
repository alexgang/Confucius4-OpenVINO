# §14 明细 —— T-2「重复启动 → 端口占用 → 整屏 traceback 崩溃」修复

> 本文件是 `status/STATUS_EXT.md` §14 的逐条明细全文（EXT-016 写作规则：精简版只留骨架，明细下沉 notes/）。
> 执行时间：2026-10-30 22:41 → 22:55
> 触发：用户口述「实测无法正常工作，启动报错」。

---

## ① 根因（日志实锤，不是猜测）

用户日志 `%LOCALAPPDATA%\LiveDubEXT\bridge.log`：

```
OSError: [Errno 10048] Only one usage of each socket address ... ('127.0.0.1', 8765)
```

traceback 终点：`ext/bridge.py` → `websockets.serve(...)`（原第 1588 行）绑定 8765 失败。

两个独立成因叠加：

| # | 成因 | 后果 |
|---|---|---|
| A | **启动器完全没有「本模块已在运行」检测** —— 只检查 `_caption_app_running()`（实时字幕 App），**从不检查本模块自己的端口** | 用户重复点「启动」⇒ 拉起第二个子进程 ⇒ bind 8765 失败 ⇒ **整屏 traceback 崩给用户看** |
| B | **端口 bind 发生在模型预热之后**（`engine.warmup()` 先跑，bind 后跑） | 用户**白等 24 秒**加载模型，然后才看到崩溃 |

实测证据（用户那次真实启动）：
- 引擎预热成功 3/3、总耗时 **24.1 s**、TTS 就绪 @ 22:41:38 ⇒ 预热确实跑完了；
- 之后立刻 10048 崩溃 ⇒ **顺序确实是「先预热、后 bind」**。

---

## ② 修复（两道防线）

### 防线 1：启动器前置拦截（`tools/ext_launcher.py`）

新增 4 个辅助函数：

| 函数 | 作用 | 关键实现要点 |
|---|---|---|
| `_port_in_use(host, port)` | 端口是否已被占用 | `socket.connect_ex` 探测；**探测自身异常 ⇒ 返回 False（放行）**，绝不让探测故障挡住正常启动 |
| `_find_port_owner(host, port)` | 找出占用者 PID | 解析 `netstat -ano`；★ **必须先 `line.strip().split()`** —— netstat 行首有空格，用 `startswith("TCP")` 会全部漏掉 |
| `_pid_alive(pid)` | PID 是否真的活着 | ctypes `OpenProcess` + `GetExitCodeProcess`（`STILL_ACTIVE=259`）；**失败 ⇒ 走二次确认，绝不直接判活** |
| `_pid_in_tasklist(pid)` | 二次确认 | `subprocess.run(["tasklist","/FI","PID eq %d"%pid,"/NH","/FO","CSV"])`；★ **必须用参数数组、不经 shell**（Git Bash 会把 `/FI` 当路径）；解析不出 ⇒ **保守判活 True** |

> ⚠️ **踩坑记录**：最初 `_pid_alive` 用「`OpenProcess` 失败 ⇒ 返回 True（保守）」，
> 结果把**已死的 PID 28728** 报成「已经在运行（PID=28728）」。
> 本机 App 自带 `pythonw` **没有 psutil**（实测 `ModuleNotFoundError: No module named 'psutil'`），
> 因此改用 `tasklist` CSV 二次确认。
> 实测判别力：`_pid_alive(5464)=True`（真占用者）/ `_pid_alive(28728)=False`（死 PID）/ `_pid_alive(999999)=False`（不存在）。

`BridgeRunner.start()` 里在**拉子进程之前**拦截（`_caption_app_running()` 检查之后）：

- 端口空闲 ⇒ 行为完全不变（生产路径零影响）；
- 端口被占且 **PID 文件里的 PID 还活着** ⇒ 提示「桥接服务**已经在运行**了（PID=…, 端口=…）」，
  明确告诉用户「**不需要重复启动**，直接在浏览器点扩展图标即可；要重启请先点『停止』」；
- 端口被占但 **PID 不是本模块的 / 那个 PID 已死** ⇒ 提示「端口 N **已被占用**」+ 两条可能原因
  （上次进程没退出 / 别的程序占用）+ 日志路径；
- 两种情况都：**不拉子进程**（`proc is None`）、状态灯切 `err`。

### 防线 2：桥接侧预检前移（`ext/bridge.py`）

新增：

```python
def _probe_port_free(host: str, port: int) -> tuple[bool, str]:
    # 真 bind + listen 试探（不是 connect_ex —— connect_ex 对已监听端口确实返回 0，
    # 但对「端口被 TIME_WAIT 占用」等情形不可靠；bind 才是权威口径）
    # 设 SO_EXCLUSIVEADDRUSE（Windows：否则 bind 成功但 listen 仍可能 10048）
    # 命中 10048 ⇒ (False, "端口 N 已被占用(...)")
    # 其他 OSError ⇒ (False, "端口 N 无法绑定：...")
    # 探测本身抛异常 ⇒ (True, "") 放行，绝不因探测故障阻止启动
```

```python
def _describe_port_owner(port: int) -> str:
    # netstat -ano 解析 LISTENING 行 → "占用者 PID=5464"
    # ★ 先 strip 再 split（行首有空格）
```

`main()` 中插入点 —— **在 `holder: dict = {}` 之后、`engine.warmup()` 之前**：

```python
for _p in (args.port, args.pair_port):
    if not _p: continue
    _port_ok, _port_why = _probe_port_free(args.host, _p)
    if not _port_ok:
        _owner = _describe_port_owner(_p)
        _log(f"❌ {_port_why}{('（' + _owner + '）') if _owner else ''}")
        _log("   这通常意味着**桥接服务已经在运行**（重复启动）。")
        _log("   解决办法：① 在启动器窗口点「停止」后再启动；② 或结束占用该端口的进程；③ 或换一个端口。")
        _log("   （本轮**没有**加载模型 —— 端口检查在预热之前，所以不用白等 20–40 秒）")
        return 6
```

同时给 `asyncio.run(serve(...))` 加 `except OSError` 兜底：命中 10048 ⇒ 人话提示 + `return 6`（不再抛栈）。

⇒ **端口检查在预热之前** ⇒ 用户不再白等 24 秒。

---

## ③ 实测对比（真实进程，非桩）

| 场景 | 修前 | 修后 |
|---|---|---|
| 重复启动（8765 已被 PID 5464 占用） | 预热 **24 s** → 整屏 traceback 崩溃 | **400 ms 退出码 6**，人话提示，**无 Traceback** |
| 启动器 `start()` | 拉起注定失败的子进程 | **0.250 s** 返回 `False`、`proc is None`、状态灯 `err` |

修后真实输出：

```
[bridge 22:47:22] ❌ 端口 8765 已被占用（通常每个套接字地址(协议/网络地址/端口)只允许使用一次。）（占用者 PID=5464）
[bridge 22:47:22]    这通常意味着**桥接服务已经在运行**（重复启动）。
[bridge 22:47:22]    解决办法：① 在启动器窗口点「停止」后再启动；② 或结束占用该端口的进程；③ 或换一个端口。
[bridge 22:47:22]    （本轮**没有**加载模型 —— 端口检查在预热之前，所以不用白等 20–40 秒）
```

---

## ④ 自测：`tests/test_t2_port_guard.py`（28 项）

| 组 | 内容 | 项数 |
|---|---|---|
| A | **启动器行为级**：真占住端口 ⇒ `start()` 返回 False / 不启动子进程 / 提示含端口号 / 含人话 / 快速 ≤ 5 s / 状态灯 `err` | 7 |
| B | `_probe_port_free` 判别力：空闲 ⇒ True；被占 ⇒ False | 4 |
| C | **真起 `ext.bridge --echo`** 打被占端口 ⇒ rc=6 / 无 `Traceback` / 输出含端口号 / ≤ 15 s / 明示未加载模型 | 6 |
| D | 源码契约（`_probe_port_free` 在 `engine.warmup` **之前** / `return 6` / `_pid_alive` 用 `OpenProcess`+`GetExitCodeProcess`）+ `_pid_alive` 判别力（0⇒False、自己⇒True、999999⇒False） | 11 |

⇒ **28 PASS / 0 FAIL**，rc=0。

---

## ⑤ 完整回归（本轮实测，逐套真实退出码）

**15 套 / 805 PASS / 0 FAIL**（全 rc=0）：
echo_roundtrip 11 / ext009 57 / ext010 23 / ext011 29 / ext012 75 / ext013_compare 51 /
ext013_cpu_watch 25 / ext016_compression 39 / ext017_user_report 108 / t1_capture_mode 38 /
**t2_port_guard 28** / browser_contract 102 / selfcheck 103 / next_instruction 19 / p1_plumbing 97。

---

## ⑥ 铁律遵守

- ⛔ **未跑任何真实推理、未占 GPU / NPU**（全程 CPU 侧 + 回声模式 / 端口探测）。
- ⛔ **未 kill 用户自己的桥接进程**（PID 5464 `ext.bridge --real --pipeline --port 8765`，
  父 `pythonw ext_launcher.py` PID 30872）—— 它正做真实推理，不能打断用户操作。
- ⛔ **未回收 `shared/MACHINE_LOCK`**（属 `tts` 模块，PID 15900 已死 ⇒ 陈旧锁，但属他人所有）。
- ⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`.gitignore:34` 仍在）。
- ⛔ **未认领新的 EXT 编号** ⇒ `last_ack` 保持 **EXT-017**（reviewer 未下发新纠偏）。
