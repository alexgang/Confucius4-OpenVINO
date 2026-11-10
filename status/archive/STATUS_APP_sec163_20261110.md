## §163 MiniMVP rc4 打 zip 完成（用户 2026-11-10 指示「打包 rc4 吧」）

### ① 交付物
* **zip**：`C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip`
  **8 609 378 581 B（8.018 GB）**｜SHA256 `f0ebcc7272ea26776f6b7bd3cd83ebdc94e5a8bfaa8e5aaeb6f5b16d55ccc4ba`｜打包 192.8 s（7-Zip `-mx=5 -mmt=on`，BELOW_NORMAL 优先级）。
* **rc3 的两个 zip 一字节未动**（SHA 前后逐字相同：`dda6f229…`／`90ae8b9d…`）⇒ **新文件名，不覆盖**（APP-055）。
* 清单口径 **`pkg_exclude`（单一数据源）** ⇒ 与 rc3 zip **同口径**
  （实测 rc3：`pkg_exclude` 10 474 == rc3 zip 条目 10 474 ✔）。

### ② 打包后逐条复核（`app302`）
| 项 | 值 |
|---|---|
| 源文件数 / zip 条目数 | 10 480 / **10 480**（`n_entries_match=true`） |
| 缺条目 / 多条目 | **0 / 0** |
| **逐条 CRC32 不符** | **0 / 10 480**（每个条目都比对了源文件 CRC） |
| 清单里 U+FFFD / 绝对路径 / `.bak` | 0 / 0 / 0 |
| NPU IR 齐全 / iGPU 保留 | 6/6 在 / 2/2 在 |

### ③ 🔴 打包前修掉的一个真实缺陷（APP-073(c) 同类）
rc4 的 README **沿用了 rc3 的**「解压后 约 6.7 GB（10 474 个文件）」⇒ 与实际 **9.967 GB / 10 480 个文件**对不上
⇒ **打进 zip 的说明书本身就是错的**。
⇒ `_app301` 按**实测值**定点改写（7 处，唯一命中断言，写前断链）：
① 磁盘 **约 10.0 GB / 10 480 个文件**（zip 条目口径）② 缓存加 `npu_cache ≈ 0.7 GB` ⇒ **合计留 20 GB 以上**
③ 内存段由「尚未实测峰值内存」改为**实测 5 212.6 MB**（含 OV 编译期）④ CPU 要求**补 Meteor Lake / 100 系列**
⑤ NPU 要求**补「ASR 也可走 NPU」**⑥ 下一版号 rc4→**rc5** ⑦ 本机基准段补实测峰值内存。
⇒ `_app300` 审计确认：README 数字 **== 清单实测**（`readme_matches_actual`）。

### ④ 从 zip 解压出来的干净包验收（`app303`，用户要求 3 的原文）
* 解压到**全新目录** `C:\minimvp_rc4_ziptest\`（先删后建 ⇒ 真干净）→ **68.29 s / 10 480 条**。
* **用包内自带的 python** 跑 `--check`（rc=0）⇒
  `[ OK ] **Intel NPU · INT8  模型齐全**` ／ `[ OK ] Intel NPU · INT4（实验）  模型齐全`。
* **执行设备直证**（`npu_delivery_backend` + `EXECUTION_DEVICES`，**跑在解出来的包里**）：
  `encoder = NPU` ／ `decoder = NPU` ⇒ `verdict=EXEC_ON_NPU_OK`
  （enc 编译 28.2 s／dec 9.7 s；OV 2026.4.1 随包自带；缓存写**独立临时目录** ⇒ 未复用本机 Panther Lake 产物冒充证据）。

### ⑤ 与 §161 的关系
§161 建的是**目录**；本条补的是**zip** ⇒ §161 的「① 交付物」现补齐 zip 一项。
§161 的设备级验收数字（WER 15.53 %／RTF 0.803／峰值 5 212.6 MB／EXEC 双 NPU）**不变**，本条只增加「zip 可用性」这一层。

### ⑥ 未做 / 待确认
* **v2.5（APP-087/088/092）仍未打** ⇒ 仍停在 §162 的「等 reviewer 复核」节点（`last_ack` 保持 **APP-092**）。
* **未通知用户**（reviewer 明文；本条是**用户直接指示**打 rc4 zip，不是 APP 流程里的打包）。
* **纠偏 APP-089…092 的验收数字仍在等 reviewer 复核**（见 §162）。

