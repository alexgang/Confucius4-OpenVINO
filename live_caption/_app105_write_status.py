#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app105_write_status.py —— §105：把 §105 章节**追加**到 `status/app/STATUS_APP.md`。

## 铁律（记忆 §一 / §九）

1. 🔴 **只追加**到文件末尾；**不改**任何旧章节正文。
2. 🔴 `STATUS_APP.md` 是**纯 CRLF** ⇒ **bytes 级定点替换**。
3. 🔴 头部字段替换**限定在头部区**（第一个 `## §N` 之前）。
4. 🔴 `set_field` 正则用 `[^\r\n]*`；value **不能自带 `key: ` 前缀**。
5. 🔴 「最近更新」≤15 行 ⇒ 超了裁最旧。
6. 🔴 写后验：「原有章节一个不少」＋「旧正文逐字未变」＋「纯 CRLF」＋「本节唯一」。
"""
from __future__ import annotations

import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
NOW = '2026-10-30 11:00'

APPEND_BODY = r'''## §105 🔴🔴🔳 **「等锁守候器」白拿白放**被实测坐实 ⇒ 改为让 `pack_v13.py` 自己等锁；并更正 §103.4「4 产物已入库」的表述（当轮只入脚本，证据由 §104 补交）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-30 11:00）
### 105.1 🔴🔴🔴 **守候器「取得锁就 `exit(0)`」= 白拿白放：本轮拿到它的完整输出坐实**

- 🔴 **§102.5 记的等锁守候器**：`/tmp/app102_lockwait.py`
  —— 逻辑是「探测到锁不存在 ⇒ `MLA.acquire()` ⇒ **打印后 `sys.exit(0)`**」。
- 🔴🔴🔴 **本轮实测（后台 task `d5UrW7` 完整输出，非推测）**：

  ```
  [     0s] 锁状态变化: state=held module=tts pid=32856
  [   920s] 锁状态变化: state=stale_pid module=tts pid=32856
  [   960s] 锁已释放 ⇒ 立即尝试取得
  [lock] 已取得机器锁（第 1 次尝试）
  app-pack PID 34040 started 2026-10-30 10:25:11
  module: app-pack
  pid: 34040
  started: 2026-10-30 10:25:11
  host: LAPTOP-0GDQGD3I

  [   960s] 已取得锁
  LOCKPAYLOAD_BEGIN
  app-pack PID 34040 started 2026-10-30 10:25:11
  ...
  LOCKPAYLOAD_END
  ```

- 🔴 **净效果 = 零**：它在 960 s **确实取得**了锁（`module=app-pack / pid=34040`），
  ⇒ **但随即 `sys.exit(0)` ⇒ 锁被自己释放** ⇒ 紧接着 TTS 重新取得（`pid=28892 / 10:25:39`）
  ⇒ **守候器既没打包，也把窗口让回去了**。
- 🔴 **根因**：守候器只做了「**取得锁**」这一半，**没做「拿到锁之后要干的活」**。
  ⇒ **铁律**：**取得锁之后必须立刻干活**；**只等锁不干活的守候器 = 无效代码**。

### 105.2 ✅ **正确做法：让 `pack_v13.py` 自己等锁（它内置完整链路）**

`pack_v13.py` 的持锁链路（读源码确认）：
`LockHeld(module='app-pack', timeout=--lock-timeout)` → `wait_quiet(quiet_seconds=45)`
→ `_run()`（包路径闸门 → **内部素材闸门** → `refresh_manifest()` →
写 `ZIP + '.tmp'` → 校验 → `os.replace()` **原子改名** → 删临时文件）。

⇒ **本轮实际执行的命令**（后台 task `LvZMW7`）：

```
python pack_v13.py --version 1.12 --lock-timeout 7200 --quiet-seconds 45 --quiet-timeout 1800
```

- ✅ **版本口径正确**：输出 `[version] 本机现存最大版本 = 1.12 ⇒ 本轮打包版本 = **1.12**`
  ⇒ **没有 bump 到 1.13**（因为显式给了 `--version 1.12`；否则 `discover_max_version()` 会推 1.13）。
- 🔴 **实测后台任务可长期存活**：task `LvZMW7` 已运行 **27 min 10 s**
  （PID 23320 = venv 启动器 / 37168 = 真解释器 `Python312`，创建于 10:26:35）
  ⇒ ✅ **两进程 ctypes 实测都 alive（exit 259）**
  ⇒ 🔴 **据此更正 §104.6 里「守候器 16 min 0 s 被终止 ⇒ 宿主后台任务有 16 分钟上限」的推断**：
  **那是守候器自身的退出，不是宿主强杀** ⇒ **长跑作业可以靠后台任务存活**
  （但**绝不能靠「后台轮询 + 拿到锁就退出」**）。

### 105.3 ✅ **打包前 dry-run 已过（只读、不持锁、几秒）**

```
$ python pack_v13.py --version 1.12 --dry-run
  源目录残留: 0 个内部内容文件
======================================================================
内部素材闸门（APP-006 第 6 步）
======================================================================
[待打包目录] C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12
  命中 0 个内部素材

结论：PASS —— 未发现内部素材
结论：PASS（dry-run，未写 zip）
```

⇒ ✅ **包路径写死闸门 PASS** ＋ ✅ **内部素材闸门 0 命中**（§102 脱敏的成果在打包前被再次验证）
＋ ✅ 必备模型文件全 `[OK]`。
⇒ 🔴 **「先 dry-run 后打包」的价值**：dry-run 也在 `_run()` 内触发闸门 ⇒ **几秒暴露不合规，
不必等 10 min 压完才发现** ⇒ 应固化为 App 打包的常驻前置（与 §104.4 的四层判据配套）。

### 105.4 🔴🔴 **更正 §103.4 的表述：「4 产物已入库」当轮不准确**

- 🔴 **§103.4 原表述**：「✅ **本轮新产物（均已入库）**」＋「✅ **4 产物已入库**（`27d5b41` → `f13fd89`，均已普通 push）」。
- 🔴 **实测当轮事实**：`27d5b41` 只含 `results/app/app160_app102_zip_verify.py`、
  `f13fd89` 也只含同 1 个文件 ⇒ **当轮只入了脚本，没入配套证据 JSON**
  ⇒ 该表述**当时不准确**（事后由 §104.2 查���并以 `c82f7e9` 补交 4 个证据文件）。
- 🔴 **根因**：「**N 个产物已入库**」这种**整体表述**最容易漏 ⇒ 必须**逐文件核 `git ls-files`**
  （§104.4 已把它列为「半交付第 ④ 层」，本节**追认该判据**并补充一条）。
- 🔴🔴 **补充判据**：**凡是「已入库 / 已交付」的结论，都必须逐文件给出
  `git ls-files <path>` 的命中数**，不能只给 commit 号（commit 号只能证明「那个 commit 存在」，
  不能证明「**这批文件**在那个 commit 里」）。

### 105.5 🔴 **当前状态：等锁排队中（zip 尚未生成）**

- 🔴 **实测锁**：`module: tts / pid: 28892 / started: 2026-10-30 10:25:39 / host: LAPTOP-0GDQGD3I`
- 🔴 **持有者确证在干活**（不是残留锁）：`Get-Process -Id 28892` ⇒ **CPU 17.00 s / WS 3 296 MB**；
  命令行 = `eval_contention_tts024.py --voice A --tag _thr1 --load-duration 300 --max-rounds 6
  --lock-timeout 7200 --quiet-stable 20 --quiet-max-wait 3600`
  ⇒ **本模块不抢锁、不杀进程**。
- 🔴 **打包任务已等 1 620 s**（`--lock-timeout 7200` 足够覆盖）。
- 🔴 **`Confucius4_LiveCaption_v1.12.zip` 尚不存在** ⇒ **仍不写「已交付」**。

### 105.6 🔴 **reviewer 复核清单（本轮增量）**

1. 🔴 **§105.1 的守候器缺陷请复核**：是否把「**取得锁之后必须立刻干活**」写成 App 的固定约定，
   并**停用 / 删除一次性守候器**（`/tmp/app102_lockwait.py` 这类），避免下次又被当成可用路径。
2. 🔴 **§105.2 的打包口径请复核**：`--version 1.12` ＋ `--lock-timeout 7200` ＋ `--quiet-seconds 45`。
3. 🔴 **§105.3「打包前必跑 dry-run」请复核**是否固化为常驻前置。
4. 🔴🔴 **§105.4 的更正请复核**：「已入库」结论须**逐文件给 `git ls-files` 命中数**
   （本节追认 §104.4 的第 ④ 层判据，并补充「不能只给 commit 号」）。
5. 🔴 **zip 闭环仍未完成** ⇒ 待锁释放 ⇒ 打包 ⇒ `app160` 0 FAIL ⇒ 才可写「已交付」。
6. 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读；工作区 modified 是 reviewer 独占写入的长期状态）。
'''


def main() -> int:
    with open(STATUS, 'rb') as f:
        raw = f.read()

    marker = b'## \xc2\xa7'
    idx = raw.find(marker)
    if idx < 0:
        print('!! 找不到任何 ## §N 章节 ⇒ 拒绝写入')
        return 1
    head_raw = raw[:idx]
    body_old = raw[idx:]

    old_sections = re.findall(rb'(?m)^## \xc2\xa7(\d+)', body_old)
    n_sec_old = len(old_sections)

    head = head_raw.replace(b'\r\n', b'\n').decode('utf-8')

    def set_field(text: str, key: str, value: str) -> str:
        pat = re.compile(r'(?m)^%s: [^\r\n]*' % re.escape(key))
        new, n = pat.subn('%s: %s' % (key, value), text, count=1)
        if n != 1:
            raise SystemExit('[FATAL] 头部字段 `%s` 命中 %d 次（应为 1）' % (key, n))
        return new

    head = set_field(head, '更新时间', NOW)
    head = set_field(
        head, '当前任务',
        '**§105 🔴🔴🔳 守候器「白拿白放」被实测坐实 ⇒ 改为让 `pack_v13.py` 自己等锁；'
        '并更正 §103.4「4 产物已入库」的表述**'
        '（巡检：`CORRECTIONS_APP.md` 44 条 = `last_ack: APP-044` ⇒ **无新纠偏条目**，'
        '第 31 次同一口径复核）'
        '⇒ 🔴🔴🔴 **守候器实测坐实白拿白放**：960 s 确实取得锁（pid 34040）'
        '⇒ **随即 `exit(0)` ⇒ 锁被自己释放** ⇒ TTS 立刻又取得（pid 28892）⇒ **净效果为零**'
        '⇒ 🔴 **铁律**：**取得锁之后必须立刻干活**；只等锁不干活的守候器 = 无效代码'
        '⇒ ✅ **改为让 `pack_v13.py` 自己等锁**（内置 `LockHeld` ＋ 安静窗口 ＋ 原子写 zip）'
        '⇒ ✅ **版本口径正确**：`--version 1.12`（未 bump 到 1.13）'
        '⇒ ✅ **dry-run 双闸门 PASS**（包路径写死 ＋ 内部素材 0 命中 ＋ 必备模型全 OK）'
        '⇒ 🔴 **据此更正 §104.6 的「宿主后台任务 16 分钟上限」推断**（那是守候器自身退出，非宿主强杀）'
        '⇒ 🔴🔴 **更正 §103.4**：「4 产物已入库」当轮**只入了脚本、没入证据 JSON**'
        '⇒ 🔴 **补充判据**：「已入库」结论须**逐文件给 `git ls-files` 命中数**，不能只给 commit 号'
        '⇒ 🔴 **锁仍被 TTS 持有**（pid 28892 / CPU 17 s / 确证在跑）⇒ **不抢锁**'
        '⇒ 🔴 **打包已排队 1 620 s**；🔴 **v1.12 zip 未生成 ⇒ 仍不写「已交付」**'
        '⇒ 🔴 **本条需等 reviewer 复核**')

    blk_pat = re.compile(r'(?m)^阻塞 / 待用户决定: [^\r\n]*')
    blk_new = (
        '阻塞 / 待用户决定: ① 🔴 **zip 半交付仍未闭环**：v1.12 打包已启动并在等锁 '
        '（task `LvZMW7` / `--lock-timeout 7200` / 已等 1 620 s）⇒ 待 TTS 释放锁 '
        '⇒ 打包 ⇒ `app160` 0 FAIL ⇒ **本轮不写「已交付」**；'
        '② 🔴 **锁被 TTS 持有**（pid 28892 / 10:25:39 / CPU 17 s 确证在跑）⇒ **不抢锁**；'
        '③ 🔴 **§105.1 请 reviewer 确认**：把「**取得锁之后必须立刻干活**」写成 App 固定约定，'
        '并**停用一次性守候器**（`/tmp/app102_lockwait.py`）；'
        '④ 🔴 **§105.3 请 reviewer 确认**：把「**打包前必跑 dry-run**」固化为常驻前置；'
        '⑤ 🔴🔴 **§105.4 请 reviewer 确认**：「已入库」结论须**逐文件给 `git ls-files` 命中数**；'
        '⑥ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；'
        '⑦ 🔴 **用户实听 3 段 1.2–1.3× 配音未做**；'
        '⑧ 🔴 **APP-043 真机验收未做**（SPE Q&A densest_5min / APP-041 `pythonw` 冷启动 / '
        'GUI 路径 APP-042 / 3 段 1.2–1.3× 配音）；'
        '⑨ 🔴 **APP-044 精度形态待 reviewer 裁定**（FP16 还是 FP32 ⇒ 代码无需改，换目录重打即可）；'
        '⑩ 🔴 **APP-039/040 真机 NPU 双说话人音色按句切换未做**（仅离线 `app150`/`app155`/'
        '`app157`/`app159`）；'
        '⑪ 🔴 **本轮未修改** `CORRECTIONS_APP.md`（只读）'
    )
    head, n = blk_pat.subn(blk_new, head, count=1)
    if n != 1:
        raise SystemExit('[FATAL] 「阻塞 / 待用户决定」行命中 %d 次' % n)

    lines = head.split('\n')
    ri = None
    for i, ln in enumerate(lines):
        if ln.replace('#', '').strip() == '最近更新':
            ri = i
            break
    if ri is None:
        raise SystemExit('[FATAL] 头部找不到「最近更新」标题')
    j = ri + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    entries = []
    while j < len(lines):
        if not lines[j].strip():
            break
        entries.append(lines[j])
        j += 1
    new_entry = (
        '2026-10-30 11:00 §105 🔴🔴🔳 **守候器「白拿白放」实测坐实**（960 s 取到锁即 `exit(0)` '
        '⇒ 锁被自己释放 ⇒ 净效果为零）⇒ ✅ **改为让 `pack_v13.py` 自己等锁**'
        '（`LockHeld` ＋ 安静窗口 ＋ 原子写 zip）＋ **版本 1.12 未 bump**'
        '⇒ ✅ **dry-run 双闸门 PASS**（包路径写死 ＋ 内部素材 0 命中）'
        '⇒ 🔴 **更正 §104.6**：「宿主后台任务 16 分钟上限」是守候器自身退出、非宿主强杀'
        '⇒ 🔴🔴 **更正 §103.4**：「4 产物已入库」当轮只入脚本、没入证据 JSON'
        '⇒ 🔴 **锁仍被 TTS 持有**（pid 28892 确证在跑）⇒ **不抢锁**'
        '⇒ 🔴 **v1.12 zip 未生成 ⇒ 不写「已交付」** ⇒ 🔴 **本条需等 reviewer 复核**'
    )
    entries.insert(0, new_entry)
    while len(entries) > 15:
        entries.pop()
    head = '\n'.join(lines[:ri + 1] + [''] + entries + [''] + lines[j:])

    head_crlf = head.replace('\n', '\r\n').encode('utf-8')
    head_crlf = head_crlf.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')

    body_new = APPEND_BODY.replace('\n', '\r\n').encode('utf-8')
    if not body_new.endswith(b'\r\n'):
        body_new += b'\r\n'

    # 🔴🔴🔴 **旧正文末尾可能没有换行**（§104 末行以内容结尾）
    #    ⇒ 新章节标题会被拼到旧行尾 ⇒ `(?m)^## §N` **匹配不到** ⇒ 章节计数为 0
    #    ⇒ 拼接时必须补一个 CRLF 当「旧正文 ↔ 新章节」的分隔
    body_old_orig = body_old
    sep = b'' if body_old.endswith(b'\r\n') else b'\r\n'
    out = head_crlf + body_old + sep + body_new

    if b'\r\n' not in out:
        raise SystemExit('[FATAL] 输出不是 CRLF')
    assert out.count(b'\n') == out.count(b'\r\n'), '存在裸 LF'
    assert out[len(head_crlf):len(head_crlf) + len(body_old_orig)] == body_old_orig, '旧正文被改动'
    secs_new = re.findall(rb'(?m)^## \xc2\xa7(\d+)', out)
    old_nums = [int(x) for x in old_sections]
    new_nums = [int(x) for x in secs_new]
    for n_ in old_nums:
        if n_ not in new_nums:
            raise SystemExit('[FATAL] 原有章节 §%d 丢失' % n_)
    assert new_nums.count(105) == 1, '§105 出现 %d 次' % new_nums.count(105)

    with open(STATUS, 'wb') as f:
        f.write(out)

    print('✅ 已追加 §105')
    print('   字节 %d → %d' % (len(raw), len(out)))
    print('   章节数 %d → %d' % (n_sec_old, len(new_nums)))
    print('   纯 CRLF / 旧正文逐字未变 / 原有章节一个不少 / §105 唯一: True')
    print('   最近更新条目数: %d（≤15）' % len(entries))
    return 0


if __name__ == '__main__':
    sys.exit(main())
