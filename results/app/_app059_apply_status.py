# -*- coding: utf-8 -*-
"""把 §59 章节写入 status/app/STATUS_APP.md（只追加章节 + 更新头部 4 字段行）。
纪律：
  - 旧章节 §1..§58 逐字节不变
  - 只改头部 last_ack / 更新时间 / 当前任务 / 阻塞 / 最近更新
  - 最近更新 ≤ 15 行
"""
import io, os, re, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
SEC = os.path.join(ROOT, 'results', 'app', '_app059_status_section.md')
BAK = r'C:\Users\Trekker-PTL\pkg_backup_app_c152\STATUS_APP.md.bak_pre_s59'

TS = '2026-10-27 03:26'
HHMM = '03:26'

NEW_TASK = (
    "**§59 🔴 巡检（APP-022 = `last_ack` ⇒ **本轮无新 APP 纠偏条目**）+ 🔴🔴 修「`submit()` 丢唤醒竞态 ⇒ "
    "命令永久滞留 `_queue` ⇒ 该句永远不被朗读」这个真实缺陷（**本条已完成**）** ⇒ ① **无新条目**："
    "`CORRECTIONS_APP.md` 最大编号 **APP-022** = 头部 `last_ack` ⇒ 编号差 **0** ⇒ 不触发逐条执行 ⇒ "
    "`last_ack` **保持 APP-022**（**第 23 次**同一口径复核，文件**只读零修改**，SHA256 `682aced289a58d18b…` 与 §57/§58 一致）；"
    "② 🔴 **缺陷 A（主）—— 丢唤醒竞态**：`submit()` 拆成两个临界区（锁内读 `state` → 出锁 → 再锁内入队）⇒ 与事件线程的"
    "「`state='ready'` + `_flush_queue()` 补发」之间存在窗口 ⇒ 若 `ready` 恰在窗口内到达 ⇒ 该句被塞进 `_queue` ⇒ "
    "**此后永不再有 ready 事件 ⇒ 命令永久滞留队列 ⇒ 该句永远不被朗读、且 `drain()` 必超时**；"
    "③ 🔴 **缺陷 B（同源）—— 幽灵在途句**：窗口内 worker 判死 ⇒ 那句入队后**永不再 ready** ⇒ 主进程 `_inflight` 多出"
    "**从未在途**的 jid ⇒ `_on_worker_exit()` 取 `lost = sorted(self._inflight)` **把幽灵算成在途丢失** ⇒ `n_dropped` 双记 ⇒ "
    "不变式 `n_played + n_dropped + len(pending) == n_submitted` 破坏；"
    "④ ✅ **修法（4 处，闭合窗口）**：**(a)** `submit()` 的「读状态 + 入队/下发」**合并到同一临界区**；"
    "**(b)** **入队前锁内复查 `state`**（`ready` ⇒ 直接下发 / `error` ⇒ 定案丢句 / 否则入队）—— 这才是闭合窗口的**关键**；"
    "**(c)** `_handle_event('ready')` 的 `state='ready'` 赋值**移进锁内**（事件侧也必须原子）；"
    "**(d)** 窗口内定案的句子**只有它此刻仍在 `pending` 里才计丢句** ⇒ 否则与孤儿清理重复 ⇒ 又一次双记；"
    "⑤ ✅ **验收 `app089` REAL 17/17 全 PASS + 反证 3/3 命中**（基线固定 `421d2d0`，本缺陷在基线**未修** ⇒ "
    "提交后 HEAD 变修复版也不影响反证）；反证实测：`n_queue=1`（命令永久滞留）/ `played=0, pending=1`（永远悬挂）/ "
    "`drain_ok=False, elapsed=6.01 s`（超时）—— 证据 `verdict=\"PASS\"`、`real_fail=[]`、`baseline_commit=\"421d2d0\"`；"
    "⑥ ✅ **回归无回归**：11 个既有套件全 PASS（`app057`/`app086`/`app088`/`test_tts_drop_crash`/`test_tts_close_gui_quit`/"
    "`test_tts_close_leak`/`test_tts_close_orphan`/`test_tts_error_isolation`/`test_tts_exit_played`/"
    "`test_tts_restart_regression`/`test_tts_stderr`）；"
    "⑦ ✅ **客户包定点同步**（双副本纪律：**精确字符串替换 + 唯一命中断言**，禁整目录覆盖；不手抄代码 ⇒ `git show 421d2d0:` + "
    "`difflib` 派生 8 块）⇒ 仓库⇄包 `tts_service.py` **SHA256 逐字节相同**（`db6f2412…` / 80 036 B）；"
    "⚠️ **我自己踩的坑（已修）**：包内是 **CRLF** 而 `git show` 永远 **LF** ⇒ 替换块命中 0 次 ⇒ 报「找不到唯一锚点」"
    "（**误导性报错**，真因是换行不匹配）⇒ 改为**全程归一化匹配 + 写盘还原**；"
    "⑧ ✅ **git**：commit **`36e3d1e`**（**4 个 App 职责内文件**）⇒ `git push origin main` **普通快进** `6235df4..36e3d1e`"
    "（**未 force**）⇒ 🔴 **`CORRECTIONS_APP.md` 未入暂存**（远端 blob 仍 `7082400b…` ⇒ 与 `421d2d0` 逐位一致）⇒ "
    "🔴 **其它模块 465 项未提交改动全部保留**（**未吞**）；"
    "⑨ ✅ **对包内那份单独跑同一套断言 PASS（17/17 + 反证 3/3）**、`check_internal_material.py --pkg` 与 `--staged` **均 PASS（命中 0）**；"
    "⚠️ **未在 CPU 跑推理/测速、未占 GPU、未碰真实 `shared/MACHINE_LOCK`、未调 MiniMax、未改 `CORRECTIONS_APP.md`、未吞其它模块改动**"
)

NEW_BLOCK = (
    "① 🔴 **APP-022 集成阶段需等 ASR-013 + TTS-019 交付**（§55 只做接口预留，**未集成**）；"
    "② 🔴 **APP-021 验收 C 仍需用户配合**（需人）：交互会话里系统音量 ≥ 50%、戴耳机/外放 ⇒ **先点「🔊 测试声音」再点离线朗读念一句** ⇒ "
    "把会话日志路径与遥测行写进本 STATUS；"
    "③ 🔴 **撤回后的口径**：在用户用耳朵确认之前，**不得**再宣称「离线朗读能出声」；"
    "④ 🔴 **v1.5 zip 未重打**（守 APP-020，等 cp_prefill 同步后的最终版 + 机器锁）；"
    "⑤ 🔴 **散包目录仍有第三方素材残留**（babelvox speakers 8 + scipy 测试音频 22）⇒ `pkg_exclude.py` 排除规则**已在**"
    "（APP-018②/APP-019）但**散包目录未物理清理** ⇒ 需重打时由规则覆盖；"
    "⑥ 🔴 **术语表 / `packaging` 默认值待用户决定**（MT 通知 14 建议：术语表只在芯片/半导体语境下开、`packaging` 放可选集 ⇒ 属 App 默认值 ⇒ 本轮**未擅自改**）；"
    "⑦ 🔴 **§50.5 需 TTS 模块配合**（App 不代跑尺子）；"
    "⑧ 🔴 **§49.7 待裁定**（APP-020 明确「先不要定」⇒ 未动）；"
    "⑨ 🔴 **§45.6①–⑤ 等 reviewer 裁定**；"
    "⑩ 🔴 **等裁定**：是否采纳 `MAX_SEG_SPAN = 2`（§44 候选已备好）；"
    "⑪ 🔴 **需回复 MT 通知 13**；"
    "⑫ 🔴 **§46.5** 第三方依赖可满足性闸门；"
    "⑬ 🔴 **§42.3** 修复待用户实机确认；"
    "⑭ ⛔ **FTP 服务仍关闭**（守 APP-009③）；"
    "⑮ ⛔ OV 的 CUDA plugin 不引入（§39.5）；"
    "⑯ ⛔ 包体优化未做（用户已接受）；"
    "⑰ ⛔ V7 残句代价待确认；"
    "⑱ 🔴 **§56.9**：TTS-019 `single` 臂 / TTS-017① `A_CPU` 臂两轮数据**是否重跑由 TTS 自行决定**（App 已修根因，**不代跑尺子**）；"
    "⑲ 🔴 **§56.2**：ASR/TTS 侧锁写法的**独占性**待其自评（`os.replace` 会覆盖 ⇒ 丢独占性）；"
    "⑳ 🔴 **§57**：历史遗留未跟踪文件（`live_caption/sync_c148b_to_pkg.py` / `sync_c150_to_pkg.py` / `results/app/app073*` / `app074*` 等）"
    "**归属未判定** ⇒ 本轮**未提交**（§46「已产出未入库」教训 ⇒ 需单独裁定后再入库）；"
    "㉑ ✅ **§58.8 已闭环**：客户包侧 `test_tts_close_gui_quit_pkg.py` 的 **PE1** 在 §58 提交（`421d2d0`）后**复跑已转 PASS**"
    "（`96118245f4e275f0` vs `96118245f4e275f0`）；"
    "㉒ ✅ **§59 已闭环**：缺陷 A/B 已修并提交 `36e3d1e`（普通 push `6235df4..36e3d1e`，未 force）⇒ 客户包定点同步后 "
    "**仓库⇄包 SHA256 逐字节相同**（`db6f2412…` / 80 036 B）⇒ 包侧单独跑同一套断言 **17/17 + 反证 3/3** PASS ⇒ "
    "🔴 **客户包 `app/` 目录仍未重打 zip**（守 APP-020：等 `cp_prefill` 同步后的最终版 + 机器锁）⇒ **不写「已交付」**"
)

NEW_RECENT = [
    "- 03:26 §59 🔴 **巡检：无新 APP 纠偏条目**（`CORRECTIONS_APP.md` 最大 **APP-022** = 头部 `last_ack` ⇒ 编号差 **0** ⇒ "
    "`last_ack` **保持 APP-022**，**第 23 次**同一口径复核）；`CORRECTIONS_APP.md` 全程**只读零修改**"
    "（SHA256 `682aced289a58d18b…` / 48 457 B / mtime 2026-10-26 16:18:08 / 22 条 / 最大 APP-022）",
    "- 03:26 §59 🔴🔴 **缺陷 A（丢唤醒竞态）**：`submit()` 拆成两个临界区（锁内读 `state` → 出锁 → 再锁内入队）⇒ 与事件线程的"
    "「`state='ready'` + `_flush_queue()` 补发」之间有窗口 ⇒ `ready` 恰在窗口内到达 ⇒ 该句塞进 `_queue` ⇒ "
    "**此后永不再有 ready ⇒ 命令永久滞留 ⇒ 该句永远不被朗读、`drain()` 必超时**",
    "- 03:26 §59 🔴 **缺陷 B（同源，幽灵在途句）**：窗口内 worker 判死 ⇒ 那句入队后**永不再 ready** ⇒ `_inflight` 多出**从未在途**的 jid ⇒ "
    "`_on_worker_exit()` 取 `lost = sorted(self._inflight)` **把幽灵算成在途丢失** ⇒ `n_dropped` 双记 ⇒ 不变式破坏",
    "- 03:26 §59 ✅ **修法 4 处（闭合窗口）**：**(a)** `submit()` 「读状态 + 入队/下发」**合并同一临界区**；"
    "**(b)** **入队前锁内复查 `state`**（`ready`⇒直接下发/`error`⇒定案丢句/否则入队）—— 闭合窗口的**关键**；"
    "**(c)** `_handle_event('ready')` 的 `state='ready'` 赋值**移进锁内**（事件侧也原子）；"
    "**(d)** 窗口内定案的句子**只有仍在 `pending` 里才计丢句**（否则与孤儿清理重复 ⇒ 二次双记）",
    "- 03:26 §59 ✅ **验收 `app089` REAL 17/17 全 PASS + 反证 3/3 命中**（基线固定 `421d2d0`，该缺陷在基线**未修** ⇒ "
    "提交后 HEAD 变修复版也不影响反证）；反证实测 `n_queue=1`（命令永久滞留）/ `played=0, pending=1`（永远悬挂）/ "
    "`drain_ok=False, elapsed=6.01 s`（超时）；证据 `verdict=\"PASS\"`、`real_fail=[]`、`baseline_commit=\"421d2d0\"`",
    "- 03:26 §59 ✅ **回归 11 套全绿**：`app057`/`app086`/`app088`/`test_tts_drop_crash`/`test_tts_close_gui_quit`/"
    "`test_tts_close_leak`/`test_tts_close_orphan`/`test_tts_error_isolation`/`test_tts_exit_played`/"
    "`test_tts_restart_regression`/`test_tts_stderr`",
    "- 03:26 §59 ✅ **客户包定点同步**（**精确字符串替换 + 唯一命中断言**，禁整目录覆盖；不手抄代码 ⇒ `git show 421d2d0:` + "
    "`difflib` 派生 **8 块**）⇒ 仓库⇄包 `tts_service.py` **SHA256 逐字节相同**（`db6f2412…` / 80 036 B，"
    "改前 73 481 B / `3fd81271…`）；⚠️ **我自己踩的坑（已修）**：包内 **CRLF** vs `git show` 永远 **LF** ⇒ 命中 0 次 ⇒ "
    "报「找不到唯一锚点」（**误导性报错**，真因是换行不匹配）⇒ 改为**全程归一化匹配 + 写盘还原**",
    "- 03:26 §59 ✅ **已提交 `36e3d1e` 并推送**（普通 push `6235df4..36e3d1e`，**未 force**）⇒ 4 个 App 职责内文件入暂存；"
    "🔴 **`CORRECTIONS_APP.md` 未入暂存**（远端 blob 仍 `7082400b…` ⇒ 与 `421d2d0` 逐位一致）；"
    "🔴 **其它模块 465 项未提交改动全部保留**（**未吞**）；`check_internal_material.py --pkg` 与 `--staged` **均 PASS（命中 0）**",
]


def main():
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        txt = f.read()
    orig = txt
    lines = txt.split('\n')

    # --- 定位头部区 ---
    i_ack = next(i for i, l in enumerate(lines) if l.startswith('last_ack:'))
    i_time = next(i for i, l in enumerate(lines) if l.startswith('更新时间:'))
    i_task = next(i for i, l in enumerate(lines) if l.startswith('当前任务:'))
    i_block = next(i for i, l in enumerate(lines) if l.startswith('阻塞 / 待用户决定:'))
    i_recent = next(i for i, l in enumerate(lines) if l.startswith('## 最近更新'))
    # 最近更新块的结束：下一个 '## ' 标题
    i_next = next(i for i in range(i_recent + 1, len(lines)) if lines[i].startswith('## '))

    # --- 1) 头部 4 字段 ---
    assert lines[i_ack] == 'last_ack: APP-022', lines[i_ack]
    lines[i_ack] = 'last_ack: APP-022'
    lines[i_time] = '更新时间: ' + TS
    lines[i_task] = '当前任务: ' + NEW_TASK
    lines[i_block] = '阻塞 / 待用户决定: ' + NEW_BLOCK

    # --- 2) 最近更新：新条目置顶，总行数 ≤ 15 ---
    old_bullets = [l for l in lines[i_recent + 1:i_next] if l.startswith('- ')]
    bullets = NEW_RECENT + old_bullets
    bullets = bullets[:15]
    while len(bullets) < 15 and old_bullets:
        bullets.append(old_bullets[len(bullets) - len(NEW_RECENT)])
    lines[i_recent + 1:i_next] = bullets

    txt = '\n'.join(lines)

    # --- 3) 追加 §59 章节（只追加，不动旧章节） ---
    with open(SEC, 'r', encoding='utf-8', newline='') as f:
        sec = f.read().replace('\r\n', '\n').strip('\n')
    if not txt.endswith('\n'):
        txt += '\n'
    txt = txt + '\n' + sec + '\n'

    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(txt)

    # --- 4) 校验：旧章节逐字节不变 ---
    with open(BAK, 'r', encoding='utf-8', newline='') as f:
        old = f.read()
    old_sections = re.split(r'(?m)^## §', old)
    new_sections = re.split(r'(?m)^## §', txt)
    # 头部区域必然变了；逐个旧章节标题+正文对比
    assert len(new_sections) == len(old_sections) + 1, (len(old_sections), len(new_sections))
    for i in range(1, len(old_sections)):
        o = old_sections[i]
        n = new_sections[i]
        # 章节正文必须完全一致（允许末尾换行差异）
        assert o.strip('\n') == n.strip('\n'), ('旧章节被改动: §' + o.split('\n')[0][:40])
    print('OK 旧章节 §1..§58 逐字节未变；新增章节数 =', len(new_sections) - len(old_sections))
    print('最近更新行数 =', len([l for l in txt.split('\n')[i_recent:i_next] if l.startswith('- ')]))
    d = open(STATUS, 'rb').read()
    print('新 STATUS: size=%d  sha256=%s' % (len(d), hashlib.sha256(d).hexdigest()))
    print('章节总数 =', len(re.findall(r'(?m)^## §', txt)))
    print('头部 last_ack =', txt.split('\n')[1])
    print('头部 更新时间 =', txt.split('\n')[2])


if __name__ == '__main__':
    main()
