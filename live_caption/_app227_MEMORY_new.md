# 项目长期记忆 · confucius4-openvino

> 🔴只留「换个会话不知道就会做错」的判据；**逐条不删，只压从句**；本文件 **≤9 700 字符**（压缩前全文快照 ⇒ `MEMORY_MODULES.md` 附录·四十九）。
> 全文在 `MEMORY_MODULES.md`（模块号见其目录）；**§214/215/217–226⇒`status/app/STATUS_APP_sec2*_detail_*.md`**；存档 `MEMORY_ARCHIVE_*.md`。
> 纠偏文件（🔴只读不写、不代提交）：`status/{asr,app}/CORRECTIONS_*.md`｜`hy_bench/CORRECTIONS_HY.md`｜`qwen3tts_eval/status/CORRECTIONS_TTS.md`。

## 一、写文件／协作／打包
-🔴**定点写入三件套**：① 备份（`%TEMP%/*.bak`）② 写前在**内存新文本**跑真不变量＋**还原式复核**（改回须逐字节同）③ 临时文件→`os.replace` ⇒ 写后**另起脚本复核**＋`numstat`。`open(p,'w')` 先截断⇒0 B。
-🔴**复核三坑**：① 「只改一行」须**对写前备份逐行 diff**＋`numstat`；②**已是 UTF-8 字节的串不可再 `.encode()`**⇒断言**假 FAIL**⇒按 UTF-8 **文本**比；③**还原式反推按「编辑区间替换后长度」定位**⇒行数变时错位⇒假 FAIL。🔴**真不变量**：行尾风格不变／字节等长／行数不变／章节数不变／`last_ack` 唯一／旧正文逐字未变；自检 FAIL⇒零改动。🔴含 `\r\n`/`\t` 的正文**必须用 Write/Edit 或 raw string**（`.replace('\n','\r\n')`⇒孤立 CR/TAB）。🔴**还原式复核两坑（§225）**：**多条换一条指针行**别逐条各换一行；**切片 off-by-one**（`del r[k-1:k+3]` 多删空行⇒少 1 B）。
-🔴**不 force push**；逐文件 `git add`（禁`-A`）；🔴`CORRECTIONS_*.md` **只读、不提交**（其 ` M` 是 reviewer 真追加⇒永不 add）；只写自己 `STATUS_*`；🔴**`.workbuddy/memory/automations/*/memory.md` 只许追加、禁覆盖**（gitignore⇒无副本）。🔴**补丁脚本幂等**（守卫命中即拒）。
-🔴打包前 `--dry-run`；**未经用户通知不打包**（reviewer 点名的包＝例外）；`pack_v13.py` 启动即改源目录名⇒中止白吃版本号。
-🔴仓库 ⇄ 客户包＝两份独立副本⇒只用「精确替换＋唯一命中断言＋`ast.parse`＋逐字节复核」；禁整目录覆盖；验收脚本不 `import` 被检⇒`ast`＋`exec`；🔴**裸 JSON 里找未转义路径恒 False⇒死代码**⇒跨包指针用解码值＋转义形态。🔴**交付口径 =「zip 内含本轮代码」⇒「包里对」≠「已交付」**；🔴**含 `\` 的正文/替换串不用 bash heredoc**⇒用 Write/Edit 或 Python 脚本；CRLF 串带 `\r\n`。
-🔴🔴**入库完整性（§222）**：① **发信记录入库的必须是实际发出的那版**⇒核对**实发邮件正文**。② **证据 json 入库 ⇒ 其产生脚本也要入库**。③ reviewer 的**复算底本**（逐句 jsonl／积压 csv／源 json）**必须入库**。④ **已入库脚本 `import` 的模块必须入库**（否则干净 clone 无法重建包）。
-🔴🔴**base64 人工转写必错**（§222／§224 两实证）⇒ **附件落地/上传走「工具结果落盘 → 脚本扫描 md5/sha1 命中才写出」**，**禁**手抄进脚本／`.b64`／shell。🔴🔴**附件随信发出 ⇒ 走直连 API、从磁盘读文件** ⇒ 配方 ⇒ `MEMORY_attach_send_recipe.md` ＋ MODULES 四十五（HKDF/AAD＋两步 `ctk_`）；**token 绑定请求内容 ⇒ 第二次原样重发**；**用完覆写并删明文 token**。
-🔴**schtasks 不接受 `>` 重定向**（⇒秒退无输出）⇒ 长作业包装器**在脚本内**重定向（`& script *> $log`）＋ **PATH 变体清理**（`Path`/`PATH`/`path` 三键 ⇒ .NET `Process.Start` 抛「字典关键字重复」）＋ 兜底释放锁。

## 二、机器锁（`shared/MACHINE_LOCK`）＋ 模块租约
-🔴锁 fail-closed；死判据 = ctypes `OpenProcess` err==87；探测失败⇒视为存活；绝不手写 `tasklist /FI`。🔴**`OpenProcess` 成功⇒再看 `GetExitCodeProcess`⇒259=STILL_ACTIVE⇒活**（0 才是死）⇒误把 259 当死会抢锁。
-🔴占 GPU/NPU 的作业须先探安静窗口＋排队拿锁；纯静态检查／不载模型的 CPU 单测不锁。🔴后台长作业只用 `run_in_background: true`（`nohup …&`⇒孤儿锁）⇒立刻 `addpid`；被杀后先以 err==87 确证死再回收。
-🔴开工先拿租约（`session_lease.py acquire <模块>`）⇒BUSY(10) 立即结束、一字不改、不碰锁；🔴**TAKEOVER⇒上会话已死⇒从断点继续**（读其 note／STATUS／产物，**别从头重做**）；TOKEN⇒每步 beat（>30 min＝死会话）；LOST(11)⇒立即停；收尾 `release`；🔴Git Bash 路径正斜杠。🔴严禁按 `python.exe` 通配 kill；每段持锁 ≤ 60 min；租约管同模块、锁管跨模块。

## 三、纠偏闭环 / 报数
-🔴一条纠偏改三处：① header `last_ack` ② 追加 `## §N` ③ 主报告＋交接单；有未完成项⇒继续做。🔴报数须指到「配置＋结果文件＋字段」；没落盘不能写「已交付」。🔴`CORRECTIONS_*.md` 中途可能被追加⇒收尾重取 SHA/字节/mtime/条数才可写「SHA 零改动」。
-🔴**无新纠偏时 `last_ack` 不变**；🔴**待命轮不写 §N**（APP-085 §2／§194 ⑪ ⇒ 只改 STATUS 头部「更新时间」一行）；**但 TAKEOVER 接续轮若在闭合上一会话遗留项 ⇒ 可写 §N**（§215／§222 先例）。
-🔴**纠偏来源双通道**（T-MAIL-002/003）：局域网 `CORRECTIONS_*.md` ＋ **QQ 邮箱**（`alexchen7694@agent.qq.com`）；**同一编号两边都到 ⇒ 只执行一次**；**STATUS 邮件改为「必须发」**。
-🔴🔴**reviewer 的「XX 补充」邮件仍算同一编号**（§225：APP-128 补充 ≠ APP-129）⇒ `last_ack` **不变**，但**仍要单独执行＋单独发信＋写 §N**。
-🔴🔴**长邮件正文会被截断**（§224 的 11 KB 正文中间丢失⇒要补发）⇒ **表格类结论单独发短邮件**（正文 ≤~2 KB，只放表）＋ **发完在已发箱核对**：§226 用**内容检索命中首/中/尾三地标**（中段即 §224 丢失点）；正文**由脚本生成**⇒入库件与实发**逐字节相同**。

## 四、判据工程（⇒MODULES 附录·四 ＋ 十五–三十六）
- 🔴🔴🔴PASS ≠ 正确：须能被有缺陷的旧产物识破；FAIL 先怀疑判据/环境；反证须**真改坏被检的那部分**；**「正则没匹配」＝「事实不存在」**⇒跑反证组。🔴🔴**闸门的判据也会错**⇒写闸门前先问「真改生产代码会不会改坏」｜闸门须强制「**证据属于被检对象**」＋「**描述被检对象当前内容**」＋「**绑到包身份**」｜**精确字符串 ≠ 语义判据**⇒证据带 `pkg_content`。🔴🔴🔴**判据改成「行为级真跑」才是定论**⇒**AST 直读表＋桩里 `__file__` 指向包内真实路径＋真跑被测函数＋反证组 AST 定位**。
- 🔴🔴🔴**验收脚本须走「产品同款调用路径」**（假 FAIL 源）：① `make_engine()` **无 `voice` 参** ② 喂引擎**必须用 `map_language()`** ③ `translate(text,tgt)` 的 `tgt` 要**代号** ④ `ext/bridge` 必须 **`-m ext.bridge`** ⑤ 反证组查**产品的闸**。
- 🔴🔴**包级/出包闸门（§203/206–208）**：**枚举须覆盖全部客户包**＋ 缺 `app/tts_worker.py` 的目录单列 `SKIP_NO_TTS_WORKER`｜绑了 X 却不在闸门侧重算 X→Y⇒**等于没绑**｜须**同时**绑「包身份」＋「包内容」｜证据缺 `pkg_content`⇒**fail-closed**｜**判定先于产物落位**。🔴🔴🔴**计时类结论有效性（APP-115）**：`timing_valid` ＝ **锁未被动过**＋**无外部大 IO**＋**逐句 `synth_rtf` P90≤0.75**；**锁丢失 ⇒ 计时作废**（计数类成立）；**外部 replay 污染计时**⇒计时臂须独占机器；**「锁未被抢」≠「机器没被占」**。🔴🔴🔴**探针要能跑在旧包上**（直调新 API⇒**假 FAIL**⇒`getattr` 兜底；**计数器不能求和**⇒取 max）。
- 🔴🔴🔴**「包内 python vs 仓库 venv」是判据正确性的前提**（APP-120 血泪）⇒ 凡依赖「只随包分发」运行时（`babelvox` 等）的 harness ⇒ **必须用包内 python**；用 `.venv` ⇒ **假 FAIL**（非产品缺陷）⇒ **判「包能否用」须用客户解释器**。🔴🔴**跨加速器 md5 差异判据（通用）**：参照 md5 只代表**一种设备口径**（§86＝NPU）⇒换设备转写**必不同**⇒**不是回归**；**证零回归＝与「同模块另一设备臂历史产物」逐字节比**。🔴🔴**A/B 必先播种**（全局 `np.random` 不播种 ⇒ 两臂抽到不同 token ⇒ 比的是采样噪声）。
## 五、设备归属审计
- 🔴🔴🔴「写 device=NPU」≠「真在 NPU」⇒查 `get_property("EXECUTION_DEVICES")`（NPU 档返 `'NPU'`）⇒`list(devs)` 拆 `['N','P','U']`。🔴🔴App 实际解码器是 `_dec_bucket_models`（`talker_buckets` 键=int）⇒只报 `tok_decoder` 会漏；「未启用」≠「落点不明」⇒分 `absent`/`unknown`。

## 六、App 铁律（⇒MODULES 五–八/二十＋三十一）
-🔴🔴音色回落须「模式感知」（`spk=None` 两义）｜🔴🔴旁路不得阻塞主循环（APP-054，默认关）。🔴🔴🔴**APP-086②「男声被配成女声」根因**：`elif self._has_clone_voice():`→`_log_keep_last_clone()` **只改遥测不改音色**⇒收窄为 **`and not _bound`**；🔴**worker 晚到标签通道**：命令里 `spk` **必须为空**⇒只走 `spk_update`。
-🔴🔴🔴**GUI/抓屏/快捷方式**（`ImageGrab` 全黑⇒Win32 `PrintWindow`）｜CUDA 置灰 = **行为性拦截**｜🔴**开发树没有 TTS/MT/说话人模型**⇒设备验收须在**影子包**跑（APP-055）；**影子包 ≠ 客户包**⇒同步只走「新版本号」。
-🔴🔴🔴**语速上限现役 = 1.70×**（中文下限 1.10／非中文 1.00；**RTF 动态封顶 `speed ≤ 1/r`**）｜**APP-113 §1 排队等待**：TTS 未就绪⇒终稿**进队列**⇒就绪后 FIFO 补发⇒**一句不丢**（APP-114 §2.1 取消 120 s 丢弃）｜**TTS 跳句阈值 0.0 s**｜**加新包形态⇒`device_config.current_profile()` 须同步返回它**。
-🔴🔴🔴**Special MVP 第三形态**＝默认 **ASR=GPU.0／MT=NPU／TTS=CUDA**；🔴**OV 官方包无 CUDA plugin**⇒「选到 NVIDIA」≠真 CUDA；**首启 58.7 s**；🔴🔴🔴**本机安全删除 shim 让「删文件」失败**⇒**打包脚本一律不能删**（拷贝排除／改名挪出包外／闸门只断言不 purge）。
## 七、TTS侧要点（⇒MODULES 十三/二十二/三十七/三十九）
-🔴**TTS侧（§7）**：全 NPU/spkonly/INT8 冻结；帧数上限＝**492**；**OV 2026.5 暂停**；**不得**写「vocoder 可上 GPU」；NPU 变慢＝集显/DRAM 被抢⇒判据用 SoC 负载。🔴**TTS §80–§83（伪/真 ICL）**⇒**App 侧禁令 = 不开 `ref_text`/`ref_audio`**⇒**零动作**。
-🔴**TTS-062…077（逐字⇒MODULES 三十七）**：撤回 4 项结论｜**066 GSV 不采用**、**068 Ming 放弃**⇒🔴**零样本克隆全关**⇒🟢**Qwen3-TTS 0.6B（spkonly·全 NPU·INT8）是唯一交付方案**｜**TTS-075 音质终验双通过**｜🔴**APP-123 已下发 ⇒ App 侧接 c13**｜🔴**跑「控制字符自检」**（写路径用 raw string）｜🔴**全库 `TTS-078/079` 命中项＝出站正文的否定式表述 ⇒ 不是新编号**。
## 八、可移植性／影子包／验证纪律
- 🔴🔴🔴`core.autocrlf=true` ＋ 无 `.gitattributes`⇒clone 与 HEAD 逐字节不同⇒①比对归一化行尾 ②锚点恒 0⇒同步失效 ③读入归一化、写回还原行尾。**`git status` 的 ` M` 可能是 autocrlf 假阳性**（⇒ `git diff --numstat` 复核）；**`CORRECTIONS_APP.md` 的 ` M` 是 reviewer 真追加⇒永不 add**。🔴🔴A/B 两臂须同一次持锁会话内连续跑；顺序对照 ≠ ABBA。🔴🔴🔴**§226 修法**（⇒MODULES 四十七）：入库 reviewer 原件⇒同目录 `.gitattributes`(`*.json -text`)＋`git add --renormalize`（只 `git add` 不够）；判据＝真跑 `git -c core.autocrlf=false clone`（须作用于 clone 本身）＋反证组；根治＝仓库根 `.gitattributes`＝跨模块 ⇒ 须 reviewer 裁定。
-🔴测「功能开/关」而无独立开关⇒在**影子包**加**只读探针**（只加日志 + env 门控提前返回）⇒diff 落盘供 reviewer 核对；**开发树一字不改**。🔴**A/B「无影响」须先量噪声地板（ABBA）**⇒详见 §四（**不写「已证明无影响」**）。

## 九、压缩 STATUS／CORRECTIONS（APP-049/052④）
-🔴STATUS 逼近 40 000 B⇒正文放 companion（`status/app/STATUS_APP_secNNN_detail_*.md`）＋活文档留摘要；**新节触顶⇒归档老节（逐字）＋活文档换指针行**；**归档件 write-once**（已归档过的节，活文档是指针行⇒不得拿它当正文覆写）；限额 ≤40 KB/≤300 行。🔴**归档「最近更新」多条⇒合并成 1 行指针**（写明归档件字节数＋SHA256）。

## 十、App 交付纪律（详见 MODULES 十四/二十）
-🔴完整版交付版 **v2.1**（**v2.5 必须带收窄**）＋ MiniMVP 线（= **rc11**）；只打**新版本号**（新目录＋新 zip＋重签 ACCEPTED）；.lnk 版本号派生自包目录名；**旧目录/zip 不覆盖不删**。🔴D1 = 5 s 唯一事实来源 `asr_spk_window.WIN_S`（5.0）⇒App 同源跟随；🔴但「唯一事实来源」被改 ≠ 下游都读它⇒跨模块常量须核对下游；改 dev⇒复跑回归。
-🔴🔴APP-071/075（BLOCKING）：v23_clone 男声听着像女声⇒克隆音色串音⇒**不接受只统计 voice_kind 的验收**；须 ①每音色落盘诊断 ②真 x-vector 余弦矩阵 ③`spk_conf` 门槛＋≥2.5 s 连续干净 ④重交 `v23_clone_r2/`＋F0 闸门。🔴🔴APP-076：`min_clean_ratio` 0.8→0.6 同步进 dev＋下一版包；**克隆登记不放宽**。

## 十一、10 语种（APP-097）`_SEC_PER_CHAR` 校准口径（§172）
-🔴「报 p50 定阈值」＝**要回填**；「只报数」＝**不回头**（MODULES 三十之六）。

## 十二、App 当前状态（**逐字⇒MODULES 三十七/四十三–四十七 ＋ STATUS §224/§225/§226 companion**）
-🔴`last_ack=APP-128`（**APP-128 只走 QQ 邮箱**＝断网）⇒ 🟢EXT v0.4.19 旁路补丁已落码并推送（e2e9 全 `fp16-w5`、提交 `3573b2d`）｜🟢**reviewer 判 APP-128 通过**；🟢**`clone_s2` 的 `n_speakers=0` 判为正常**｜🔴**待裁定**：默认分离设备／v2.6 交接。
-🟢**APP-128 补充已执行（§225）**：**已单独补发 e2e7 三臂表**（正文截断）⇒ 邮件 `msg_52Ta35TCkxRJS1CDLmdVZbCF5yDGbx4gPdFrKHNlMH7bJw`（**462 B**）｜**`last_ack` 仍 APP-128**｜🔴**v2.6 等这张表到达再发**｜提交 **`b7507cb`**。
-🟢**MiniMVP v1.1.1 已出包并打 zip**（**5 212 403 155 B / 10 881 文件**）｜🔴**旧 v1.1.zip 不自证** ⇒ **发客户必须确认发 `v1.1.1.zip`**｜🔴**v2.5 须先重签**（ACCEPTED 仍指 v2.4）。
-🟢**§226（11-24 00:4x）待命轮＋TAKEOVER**：**无新纠偏**（本地 max APP-127）｜🟢**已修「reviewer 复算底本入库字节不一致」**（3/3 复现＋反证组 3/3）｜提交 **`73a2e22`…**`58439ba`** 已推｜邮件 `msg_73akZokC…DRHg`（**2 833 B**）｜🔴**更大面未修**：全仓 **854** 个 `i/lf+w/crlf` ⇒ **须 reviewer 裁定**｜🔴**未进 v2.6／未打包**（APP-126 §7）｜**待裁定**：`n_speakers=0` 口径／**仓库根 `.gitattributes` 根治**／v2.6 交接。
## 十二之补、App OV TTS 路径与 c13（⇒MODULES 四十四）
-🔴🔴🔴**App 的 OV TTS 路径 = BabelVox + `live_caption/tts_engine_patch.py`（`MultiDecoderBabelVox`）**，**不是** TTS 模块那套裸 OV IR 驱动 ⇒「接 c13」≠搬 IR 驱动，而是补 ①**可配窗口口径** ②**TTS-076 限幅与削波计数**。🔴🔴🔴**App 本来就是「直接拼接」**（`not split_on_silence` ⇒ 不裁尾）⇒ **TTS-075「每边界丢 50 ms / 7.3%」缺陷在 App 侧不存在** ⇒ `crossfade_samples=0` 是**加固非修缺陷**。
-🔴🔴🔴**c13 三参数不是一回事**：`n1/n_next=8`＝**说话人每轮产出帧数**；`decoder_chunk_frames=13`＝**块容量**；`decoder_window_len=38`＝**静态窗口** ⇒ 🔴**误设 `CHUNK_FRAMES=13` ⇒ 首包 2.9→4.5 s 劣化（实测）⇒ 正确落地 = 8 帧 ＋ 38 帧窗口**。🔴**桶只在 NPU 生效**（GPU 走动态形状解码器）｜🔴**`stats_full.speaker.n_speakers` ≠ 克隆标签数**（前者只由 `--spk-bypass` 灌；克隆标签来自 `SpeakerBridge`）⇒ 克隆模式 0 是**口径问题非缺陷**。
## 十三、目标机交付（**地址 `192.168.2.206`**；⇒MODULES 三十/三十八）
-🔴**目标机**：**192.168.2.206**⇒目录 `C:\Users\63446`／无真 Python／C: 82 MB；🔴**凭据会话级**⇒**两端 SHA256 闭环不了**；🔴**大文件别走 SFTP**⇒HTTP(range)+`curl -C -`；zip+解压 > 可用⇒**须先删 zip（授权）**；🔴目标 sm_89 vs 验收 sm_120⇒**须实机 `--check`**。🔴🔴**A 机已离开 `192.168.2.0/24`**（11-20：`EmployeeHotspot`＝`10.188.194.152/21`、**路由表无该网段**；`.206` ping 丢包）⇒ **撤回 §200 ⑦前提** ⇒ **「目标机不可达」至少两因**（离线／**A 机换网**）⇒ 三件套**前置：A 机回该网段**；`_app547_hash_retry.py` **HOST 仍 `.194`**。
