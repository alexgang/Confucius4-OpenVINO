# ASR STATUS 归档 —— §76 全文（压缩前原文，逐字保留）

> 由 `asr143_archive_sec76.py` 于 2026-11-11 11:24 写出。
> 依据 ASR-036「STATUS ≤ 40 KB ＋ 只保留最近 3 节」门禁。
> 🔴 **本文件是只读归档**；正文 STATUS_ASR.md 里 §76 只保留一行摘要。

## §76 ASR-048 落地：给 App 的「新说话人登记用干净段」接口说明（a–d）＋ `overlap_ratio_max` 惰性参数的定性（2026-11-05 16:20–16:50）
> 📄 **单页 App 说明（ASR-049 ①，≤1 页）**：`status/asr/notes/asr_for_app_spk_enroll.md`（**33 行**）—— 开头 3 行问答直接回答 **APP-071**；**ASR-050 交接清单**：`status/asr/notes/asr_for_app_asr050_handoff.md`；量化结论见 **§77**。

> 🔴 **明细全文** `status/asr/notes/asr_s76.md`（**已提交**，241 行）＋ 产物 `asr121_overlap_clean_diag.json`（23314 B）；**本节全文已归档** `status/archive/STATUS_ASR_upto_20261030.md`（`## §76 `）⇒ 正文只留摘要。
- 🔴 **`overlap_ratio_max` 是惰性参数（never fires）**：`p_dom` 只取 powerset **单人三类** ⇒ 行和 ≤ 1.0 ⇒ `>1.05` **恒 False** ⇒ `overlap_ratio` **恒 0.0** ⇒ 分支**永不执行**（20000 次复刻 = 0.0，反证并入重叠类 = 0.61835）⇒ **不是「已验证无影响」**。
- 🔴 **`clean_ratio` 全 None** = 内核**算了**（`:347`）但**桥接层白名单只转发 6 字段** ⇒ **`min_clean_ratio` 是生效的**（**不要**读成「没生效」）。
- 🔴 **`spk_conf` = 与已有簇心的最大余弦相似度** ⇒ **低 = 新人**，**不是标签可信度**（首个簇直接返回 1.0）。
- 🔴 **登记用 `clean_ranges` 子区间** ⇒ **换人边界段可能混入上一人**；`is_new_spk` = 「与上一段不同」（基线 **29** 次 vs 换人点 **26** ⇒ 3 次误触发）。
- 🔴 **`spk` ID = 到达序编号** ⇒ 跨臂/跨会话**不可直接比**。
- ✅ **第 3 点 (d)**：「≥1.5 s 取样、攒到 3 s 重算」**已经在用** clean 累计时长 ⇒ **无需再改**。
