# tests/smoke — 浏览器冒烟测试（**不是**人工验收）

## 这些脚本是什么

4 个**冒烟**脚本 + 1 个夹具，用**真浏览器**（本机只有 Edge 126，没有 Chrome）
验证插件这条链路的**机械正确性**：

| 脚本 | 验证什么 | 占用设备 |
|---|---|---|
| `pw_accept1.py` | 扩展是否装上（service worker 存活）、popup 是否正常渲染 | 无 |
| `pw_accept2.py` | popup 的设置**写入与回填**（语言/音色/压低量/延迟/字幕开关） | 无 |
| `pw_accept3.py` | player 页能否加载、能否读到设置、`storage.onChanged` 是否接上 | 无 |
| `pw_accept4.py` | 插件 ↔ 桥接服务端到端（**回声模式**）⇒ hello 真的到了服务端 | 无（回声模式不加载引擎） |

夹具：`browser_harness.py`（起浏览器 + CDP 连接 + 开扩展页）。

## 这些脚本**不是**什么（EXT-022 已定②）

> 浏览器端人工验收（英文网页视频 + 本地 mp4，各 1 分钟，
> 带**用户手势**的 tabCapture）**由用户亲自做**，
> **不要**用这些脚本替代 Playwright 之外的东西。

这些脚本**没有**做、也**做不到**：

* ❌ 真实用户手势下的 `tabCapture`（脚本没有真人点扩展图标）
* ❌ 真实音视频流的端到端延迟与听感
* ❌ 真实三引擎（ASR/MT/TTS）下的链路验证

⇒ `tabCapture` 生产路径是否被实测过，**只能**由用户的真实验收来确认。

## 怎么跑

在本仓库根目录：

```bash
python tests/smoke/pw_accept1.py
python tests/smoke/pw_accept2.py
python tests/smoke/pw_accept3.py
python tests/smoke/pw_accept4.py
```

依赖：workbuddy 自带 Python 环境（**自带 playwright**）。
`browser_harness.find_browser()` 按 Edge → Chrome 的顺序找可执行文件。

## 注意

* `pw_accept4.py` 会**动态分配端口**（避免与用户自己开着的桥接服务撞端口）；
* 浏览器 profile 落在 `.tmp/pw_ext/<name>/`（**不入库**，`.tmp/` 已在 `.gitignore`）；
* 回声模式**不加载引擎** ⇒ 不占 GPU/NPU，**不需要**共享机器锁。
