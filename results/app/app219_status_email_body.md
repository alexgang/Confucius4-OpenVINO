[C4][A][STATUS][APP] APP-119 —— 出厂默认 ASR=GPU.0/MT=GPU.0/TTS=NPU；§2 取消 NPU 互斥；三臂验收完成；修掉一个真缺陷；未打 zip

一句话：APP-119 全部落地。§1 出厂默认 = ASR GPU.0 / MT GPU.0 / TTS NPU（代次 9→11；迁移 15/15 PASS）；§2 删掉「MT+TTS 不能同在 NPU ⇒ 自动把 MT 挪到 GPU.0」强制规则，三模块设备自由配置、不再自动改用户选择，只留一条不阻塞的 NPU 共用提示，APP-117 总状态灯未加回；§3 三臂：新默认臂 14/14 PASS、allnpu 臂（唯一 FAIL＝并行，同卡⇒该串行，属设计内）、混合臂 PASS。

🔴 另修掉一个真缺陷：APP-113 §2 的并行加载判定写死「TTS=CUDA」，§1 把默认改成 TTS=NPU 后，默认配置（ASR=GPU.0 与 TTS=NPU 异卡）被静默地永远串行 ⇒ 首次跑唯一 FAIL。改成「同卡才串行」后复跑 14/14 PASS，TTS 就绪 20.4→11.0 s。

默认臂 10 分钟：150 句 == 150 进 TTS + 丢句 0；语速 max 1.4368 ≤ 1.70；synth_rtf 中位 0.9656 / P90 1.0604；积压峰值 88.805 s ⇒ 收尾排空到 69.635 s；整链 678.3 s；并行 on。🔴 timing_valid=false（RTF P90>0.75 计时线；锁未被抢 ⇒ 计数类成立）。

allnpu（ASR=MT=TTS=NPU）：启动/rc=0/不崩；三模块实际设备逐项 = NPU，日志里无任何「自动改到 GPU.0」；synth_rtf 中位 1.065/P90 1.3228；丢句 0；积压峰值 178.163 s；加载 ASR 1.7/翻译 2.4/TTS 引擎 5.7/worker 8.3 s；进程工作集峰值合计 8891.4 MiB。

混合臂（ASR=NPU/MT=NPU/TTS=GPU.0）：9/9 PASS，实际设备逐项相符，MT 未被自动挪走 ⇒ §2 成立。

包：v2.5 目录已更新（device_config.py / live_caption_app.py 与 dev 逐字节一致，48790 文件），v2.4 / rc11 / sp5 逐字节未动，🔴 未打 zip（§3 明令）。预设 A/B 不进包（等抽听）。

🔴 另：包上自检查出 1 项上一轮遗留违规（ext/bridge_token.txt，APP-077 明令不得进包；§217 换嵌 EXT v0.4.18 带进去的）⇒ 已改名挪出包目录（不删除）；桥接自生成 token ⇒ EXT 冒烟复跑 7/7 PASS、洁净度闸门 0 违规。

明细：A 机 status\app\STATUS_APP_sec219_detail_20261121.md；results\app\ 下 app119_* 证据 json。本条需等 reviewer 复核。
